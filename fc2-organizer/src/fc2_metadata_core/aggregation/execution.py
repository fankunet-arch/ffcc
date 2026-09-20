"""Bounded, isolated, deadline-limited execution of several source adapters.

``execute_sources`` runs ``adapter.fetch(number, client)`` for each configured
source **concurrently** (at most ``max_concurrency`` at once) through one
shared :class:`SourceHttpClient`, and returns exactly one ``SourceResult`` per
source **in configuration order** -- never in completion order. It is the
Phase 3 *source execution boundary*; it does no merging (see ``merge.py``) and
no retry/backoff/circuit-breaking (later Phase 3 subphases).

Guarantees
----------
Isolation
    Any ordinary ``Exception`` an adapter leaks becomes that source's
    ``INVALID_RESPONSE`` (detail: source id + exception *type* only -- never
    the message, which could carry a URL or a secret). One source failing in
    any way never stops another.
Wall-clock deadline (closes Phase 2 review finding P2-R-09)
    ``httpx``'s timeout is per phase, not per lookup. Each source's whole
    ``fetch`` runs under ``asyncio.timeout(deadline_seconds)`` **at this
    boundary** (adapters are untouched). On expiry only that source becomes
    ``NETWORK_ERROR`` ("source execution deadline exceeded ...") with the
    real elapsed time; the others continue. The deadline starts when the
    source starts executing, not while it waits for a concurrency slot.
Cancellation
    ``asyncio.CancelledError`` (a caller cancelling the aggregate lookup),
    ``KeyboardInterrupt``, ``SystemExit`` are never converted into a source
    result: they propagate, and in-flight sibling executions are cancelled.
Fail closed
    Whatever an adapter returns is passed through
    :func:`validate_source_result`: a wrong ``source_id``, a non-``SourceResult``
    or a ``SUCCESS`` for another film becomes ``INVALID_RESPONSE``.
Bounded concurrency
    An ``asyncio.Semaphore(max_concurrency)`` -- the limit is real and
    observable, and the run is not serialised.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Callable, Sequence

from fc2_metadata_core.aggregation.config import DEFAULT_MAX_CONCURRENCY, MAX_CONCURRENCY_LIMIT, SourceConfig
from fc2_metadata_core.aggregation.merge import invalid_response_result, validate_source_result
from fc2_metadata_core.aggregation.policy import AggregationConfigError
from fc2_metadata_core.http.client import SourceHttpClient
from fc2_metadata_core.models.source_result import SourceErrorKind, SourceResult, SourceStatus
from fc2_metadata_core.sources.base import SourceAdapter

__all__ = ["SourceTarget", "execute_sources"]


@dataclass(frozen=True, slots=True)
class SourceTarget:
    """One source to run: its configuration and the adapter built for it."""

    config: SourceConfig
    adapter: SourceAdapter

    def __post_init__(self) -> None:
        if not isinstance(self.config, SourceConfig):
            raise AggregationConfigError("SourceTarget.config must be a SourceConfig")
        if not isinstance(self.adapter, SourceAdapter):
            raise AggregationConfigError("SourceTarget.adapter must be a SourceAdapter")
        if self.adapter.source_id != self.config.source_id:
            raise AggregationConfigError(
                f"adapter source_id {self.adapter.source_id!r} does not match configured "
                f"source_id {self.config.source_id!r}"
            )


def _elapsed_ms(started: float, clock: Callable[[], float]) -> float:
    return max(0.0, (clock() - started) * 1000.0)


def _deadline_result(source_id: str, deadline_seconds: float, elapsed_ms: float) -> SourceResult:
    return SourceResult(
        source_id=source_id,
        status=SourceStatus.NETWORK_ERROR,
        metadata=None,
        elapsed_ms=elapsed_ms,
        error_kind=SourceErrorKind.NETWORK_ERROR,
        error_detail=(
            f"{source_id}: source execution deadline exceeded "
            f"({deadline_seconds:g}s wall clock, {elapsed_ms:.0f} ms elapsed)"
        ),
    )


async def _execute_one(
    number: str,
    target: SourceTarget,
    client: SourceHttpClient,
    semaphore: asyncio.Semaphore,
    clock: Callable[[], float],
) -> SourceResult:
    source_id = target.config.source_id
    async with semaphore:
        started = clock()
        try:
            async with asyncio.timeout(target.config.deadline_seconds) as scope:
                candidate = await target.adapter.fetch(number, client)
        except TimeoutError:
            # asyncio.timeout() converts *its own* expiry into TimeoutError, but an
            # adapter that itself raises the builtin TimeoutError lands here too:
            # only scope.expired() is a deadline.
            elapsed = _elapsed_ms(started, clock)
            if scope.expired():
                return _deadline_result(source_id, target.config.deadline_seconds, elapsed)
            return invalid_response_result(
                source_id,
                f"{source_id}: unexpected adapter exception TimeoutError",
                elapsed_ms=elapsed,
            )
        except Exception as exc:  # CancelledError / KeyboardInterrupt / SystemExit are BaseException
            return invalid_response_result(
                source_id,
                f"{source_id}: unexpected adapter exception {type(exc).__name__}",
                elapsed_ms=_elapsed_ms(started, clock),
            )
        return validate_source_result(
            source_id, number, candidate, elapsed_ms=_elapsed_ms(started, clock)
        )


async def execute_sources(
    number: str,
    targets: Sequence[SourceTarget],
    client: SourceHttpClient,
    *,
    max_concurrency: int = DEFAULT_MAX_CONCURRENCY,
    clock: Callable[[], float] = time.monotonic,
) -> tuple[SourceResult, ...]:
    """Run every target and return one ``SourceResult`` per target, in target order.

    ``number`` must already be canonical (the engine checks it once up front).
    ``clock`` is injectable for tests; production uses ``time.monotonic``.
    """
    if isinstance(max_concurrency, bool) or not isinstance(max_concurrency, int) or not (
        1 <= max_concurrency <= MAX_CONCURRENCY_LIMIT
    ):
        raise AggregationConfigError(f"max_concurrency must be an int in 1..{MAX_CONCURRENCY_LIMIT}")
    if not targets:
        raise AggregationConfigError("no sources to execute")

    semaphore = asyncio.Semaphore(max_concurrency)
    # TaskGroup: if the caller cancels us, every child is cancelled and the
    # CancelledError propagates; no child outlives this call.
    async with asyncio.TaskGroup() as group:
        tasks = [
            group.create_task(_execute_one(number, target, client, semaphore, clock))
            for target in targets
        ]
    return tuple(task.result() for task in tasks)
