"""BatchScheduler: run many FC2 numbers through one single-item engine (Phase 3 C4).

::

    Sequence[str]  (canonical numbers; order = batch order; duplicates kept)
          |
    validate (all-or-nothing) -> snapshot
          |
    min(M, N) worker tasks  <-- bounded admission: workers pull the next position from a shared cursor and
          |                     ``await engine.aggregate(number)`` directly. No task or coroutine per item is
          |                     ever created up front, so live batch work is O(M), not O(N).
    BatchItemResult per item, stored in its own slot  -> BatchResult (input order, whatever finished first)

The scheduler owns *only* cross-item scheduling. It reuses the injected engine (anything with
``async aggregate(number) -> AggregationResult``, e.g. :class:`~fc2_metadata_core.aggregation.MultiSourceEngine`),
never builds a transport/registry/adapter and never re-implements fan-out or merging.

Semantics (frozen in ``docs/specifications/PHASE3_BATCH_CONTRACT.md``)
----------------------------------------------------------------------
* ``max_in_flight_items`` (M) is the global item budget; the source-level ``max_concurrency`` (S) of the engine
  still applies inside each item, so up to ``M * S`` source operations may run at once.
* An ordinary ``Exception`` from the engine fails **that item only** (class name recorded, never the message).
* ``CancelledError`` from the caller, ``KeyboardInterrupt`` / ``SystemExit`` / ``GeneratorExit`` / any other
  non-``Exception`` ``BaseException`` (and a ``CancelledError`` the engine raises on its own) are *not* item
  failures: admission stops at once, running siblings are cancelled and awaited, and the original exception is
  re-raised. No partial result is returned.
* One active run per scheduler (``BatchBusyError``): a second concurrent run would silently double the budget.
"""

from __future__ import annotations

import asyncio
import inspect
import time
from collections.abc import Mapping, Sequence, Set
from dataclasses import dataclass
from typing import Callable, Protocol

from fc2_metadata_core.aggregation import AggregationResult
from fc2_metadata_core.batch.config import BatchConfig
from fc2_metadata_core.batch.models import (
    BatchBusyError,
    BatchConfigError,
    BatchContractError,
    BatchInputError,
    BatchItemErrorKind,
    BatchItemResult,
    BatchItemStatus,
    BatchResult,
    RetryBatchResult,
    batch_status_for,
)
from fc2_metadata_core.batch.retry import failed_work
from fc2_metadata_core.errors import InvalidCanonicalNumberInputError
from fc2_metadata_core.sources.base import require_canonical_number

__all__ = ["AggregationEngine", "BatchScheduler"]

_MAX_REPORTED_INVALID = 10
_MAX_REPR_CHARS = 40
_MAX_TYPE_NAME_CHARS = 128
_UNKNOWN_TYPE = "UnknownType"


class AggregationEngine(Protocol):
    """The narrow engine contract the scheduler depends on (``MultiSourceEngine`` satisfies it)."""

    async def aggregate(self, number: str) -> AggregationResult: ...


class _FatalSignal(Exception):
    """Carries a fatal ``BaseException`` out of a worker task without ``BaseExceptionGroup`` wrapping.

    (``KeyboardInterrupt`` / ``SystemExit`` raised inside a task would otherwise be re-raised into the event
    loop itself by asyncio, and a self-cancelled task is silently ignored by ``TaskGroup``.)
    """

    def __init__(self, original: BaseException) -> None:
        super().__init__(type(original).__name__)
        self.original = original


@dataclass
class _Run:
    """Run-local scratch: the shared admission cursor and the stop flag (never published)."""

    work: tuple[tuple[int, str], ...]
    generation: int
    slots: list[BatchItemResult | None]
    next_position: int = 0
    stopping: bool = False
    driver: asyncio.Task | None = None  # the task awaiting the run (the caller's, or whatever wraps it)
    cancel_baseline: int = 0  # its pending-cancellation count when the run began

    def admission_open(self) -> bool:
        """May a worker start another item? Not after a fatal signal, and not once the driving task has a NEW
        cancellation request: ``Task.cancel()`` reaches the workers one loop iteration later (through the
        TaskGroup), and in that gap a freed worker must not admit anything."""
        if self.stopping:
            return False
        return self.driver is None or self.driver.cancelling() <= self.cancel_baseline


def _is_async_callable(candidate: object) -> bool:
    if inspect.iscoroutinefunction(candidate):
        return True
    return inspect.iscoroutinefunction(getattr(candidate, "__call__", None))


def _type_name(obj: object) -> str:
    """The class name of ``obj`` -- never its text. Anything odd collapses to ``UnknownType``."""
    try:
        name = type(obj).__name__
        if isinstance(name, str) and name.isidentifier() and len(name) <= _MAX_TYPE_NAME_CHARS:
            return str(name)
    except Exception:  # a hostile metaclass; never let error reporting itself raise
        pass
    return _UNKNOWN_TYPE


def _short(value: object) -> str:
    """A bounded, side-effect-free description of a rejected element (never calls its ``repr``)."""
    if isinstance(value, str):
        text = value if len(value) <= _MAX_REPR_CHARS else value[:_MAX_REPR_CHARS] + "..."
        return repr(text)
    return f"<{_type_name(value)}>"


def validate_batch(numbers: object) -> tuple[str, ...]:
    """Snapshot ``numbers`` and check the input contract; return the canonical numbers as a tuple.

    ``BatchInputError`` (zero engine calls) for a non-``Sequence`` / unordered / text-like container or for any
    element that is not already a canonical FC2 number. No normalisation and no second parser: elements go
    through the existing ``require_canonical_number`` boundary.
    """
    if isinstance(numbers, (str, bytes, bytearray, memoryview)):
        raise BatchInputError("a batch must be a Sequence of FC2 numbers, not a single text/bytes value")
    if isinstance(numbers, (Set, Mapping)) or not isinstance(numbers, Sequence):
        raise BatchInputError(
            f"a batch must be an ordered Sequence (list/tuple) of FC2 numbers, not {_type_name(numbers)}"
        )
    snapshot = tuple(numbers)
    invalid: list[tuple[int, str]] = []
    invalid_count = 0
    for index, element in enumerate(snapshot):
        if isinstance(element, str):
            try:
                require_canonical_number(element)
                continue
            except InvalidCanonicalNumberInputError:
                pass
        invalid_count += 1
        if len(invalid) < _MAX_REPORTED_INVALID:
            invalid.append((index, _short(element)))
    if invalid_count:
        shown = ", ".join(f"[{index}] {text}" for index, text in invalid)
        more = f" (+{invalid_count - len(invalid)} more)" if invalid_count > len(invalid) else ""
        raise BatchInputError(
            f"{invalid_count} element(s) are not canonical FC2 numbers (e.g. 'FC2-1234567'); normalise upstream: "
            f"{shown}{more}"
        )
    return snapshot


class BatchScheduler:
    """Run batches of canonical FC2 numbers through one injected single-item engine.

    Construction validates ``engine`` (an ``async aggregate`` is required; a plain ``def`` is rejected up front,
    like a synchronous ``client.get`` in the engine) and ``config``; nothing is executed.
    """

    def __init__(
        self,
        engine: AggregationEngine,
        config: BatchConfig | None = None,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if config is None:
            config = BatchConfig()
        if not isinstance(config, BatchConfig):
            raise BatchConfigError("config must be a BatchConfig")
        if not _is_async_callable(getattr(engine, "aggregate", None)):
            raise BatchConfigError("engine.aggregate must be an async function: `async def aggregate(number)`")
        self._engine = engine
        self._config = config
        self._clock = clock
        self._busy = False

    @property
    def config(self) -> BatchConfig:
        return self._config

    async def run(self, numbers: Sequence[str]) -> BatchResult:
        """Aggregate every number (generation 0). Returns items in **input order**.

        Raises ``BatchInputError`` (before any call) for invalid input and ``BatchBusyError`` if this scheduler
        already has an active run. Ordinary per-item failures never raise; fatal ``BaseException`` and
        cancellation propagate (see the module docstring).
        """
        snapshot = validate_batch(numbers)
        work = tuple(enumerate(snapshot))
        items = await self._execute(work, generation=0)
        return BatchResult(items, generation=0)

    async def retry_failed(self, previous: BatchResult) -> RetryBatchResult:
        """Re-run only the ``FAILED`` items of ``previous`` (by original index); return the retry round.

        ``SUCCESS`` / ``PARTIAL`` items are not retried. The round's generation is ``previous.generation + 1``.
        ``previous`` is not modified; combine the two with :func:`fc2_metadata_core.batch.apply_retry`.
        """
        work = failed_work(previous)  # BatchRetryError for a non-BatchResult
        generation = previous.generation + 1
        items = await self._execute(work, generation=generation)
        return RetryBatchResult(items, generation=generation)

    # -- internals -----------------------------------------------------------------------------------------------

    async def _execute(self, work: tuple[tuple[int, str], ...], *, generation: int) -> tuple[BatchItemResult, ...]:
        if self._busy:
            raise BatchBusyError(
                "this scheduler already has an active run; use one scheduler per concurrent run "
                "(independent budgets add up)"
            )
        self._busy = True
        try:
            return await self._drive(_Run(work, generation, [None] * len(work)))
        finally:
            self._busy = False

    async def _drive(self, run: _Run) -> tuple[BatchItemResult, ...]:
        count = len(run.work)
        if count == 0:
            return ()
        workers = min(self._config.max_in_flight_items, count)
        run.driver = asyncio.current_task()
        run.cancel_baseline = run.driver.cancelling() if run.driver is not None else 0
        try:
            # TaskGroup: a caller cancellation or a fatal signal cancels every worker and awaits them all.
            async with asyncio.TaskGroup() as group:
                for _ in range(workers):
                    group.create_task(self._worker(run))
        except ExceptionGroup as group_error:
            signals = [e for e in group_error.exceptions if isinstance(e, _FatalSignal)]
            if signals and len(signals) == len(group_error.exceptions):
                raise signals[0].original  # the ORIGINAL fatal exception object, unwrapped
            raise
        if any(slot is None for slot in run.slots):  # cannot happen; a lost item must never be silent
            raise BatchContractError("internal error: a batch item was lost")
        return tuple(slot for slot in run.slots if slot is not None)

    async def _worker(self, run: _Run) -> None:
        while run.admission_open():
            position = run.next_position
            if position >= len(run.work):
                return
            run.next_position = position + 1  # admission: no await between check and claim
            index, number = run.work[position]
            try:
                run.slots[position] = await self._run_item(index, number, run.generation)
            except asyncio.CancelledError as cancelled:
                run.stopping = True
                task = asyncio.current_task()
                if task is not None and task.cancelling() > 0:
                    raise  # a real cancellation request: the caller's, or the group tearing us down
                raise _FatalSignal(cancelled) from None  # the engine cancelled itself: never a FAILED item
            except BaseException as fatal:  # KeyboardInterrupt, SystemExit, GeneratorExit, custom, or a bug
                run.stopping = True
                raise _FatalSignal(fatal) from None

    async def _run_item(self, index: int, number: str, generation: int) -> BatchItemResult:
        started = self._clock()
        try:
            candidate = await self._engine.aggregate(number)
        except Exception as exc:  # ordinary failure: isolated, class name only (never the text)
            return BatchItemResult(
                index=index,
                number=number,
                status=BatchItemStatus.FAILED,
                error_kind=BatchItemErrorKind.ENGINE_EXCEPTION,
                error_type=_type_name(exc),
                generation=generation,
                elapsed_ms=self._elapsed_ms(started),
            )
        elapsed_ms = self._elapsed_ms(started)
        if not isinstance(candidate, AggregationResult) or candidate.number != number:
            return BatchItemResult(
                index=index,
                number=number,
                status=BatchItemStatus.FAILED,
                error_kind=BatchItemErrorKind.RESULT_CONTRACT_MISMATCH,
                error_type=_type_name(candidate),
                generation=generation,
                elapsed_ms=elapsed_ms,
            )
        return BatchItemResult(
            index=index,
            number=number,
            status=batch_status_for(candidate.status),
            aggregation_result=candidate,
            generation=generation,
            elapsed_ms=elapsed_ms,
        )

    def _elapsed_ms(self, started: float) -> float:
        return max(0.0, (self._clock() - started) * 1000.0)
