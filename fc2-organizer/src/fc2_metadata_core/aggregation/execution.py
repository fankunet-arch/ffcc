"""Bounded, isolated, deadline-limited, retrying execution of several source adapters.

``execute_sources_traced`` runs ``adapter.fetch(number, client)`` for each configured
source **concurrently** (at most ``max_concurrency`` at once) through one shared
:class:`SourceHttpClient`, and returns exactly one :class:`SourceExecutionTrace`
per source **in configuration order** -- never in completion order. It is the
Phase 3 *source execution boundary*; it does no merging (see ``merge.py``) and no
cross-item scheduling. ``execute_sources`` is the same run reduced to the final ``SourceResult``s.
Phase 3 C5 (``resource_control``, opt-in through ``governor=``): a shared per-host attempt limiter and a
per-source circuit breaker wrap this boundary; without a governor nothing below changes.

Guarantees
----------
Isolation
    Any ordinary ``Exception`` an adapter leaks becomes that source's
    ``INVALID_RESPONSE`` / ``ADAPTER_EXCEPTION`` (detail: source id + exception
    *type* only -- never the message, which could carry a URL or a secret). One
    source failing in any way never stops another.
Retry (Phase 3 C2, ``retry.py``)
    A failed attempt whose **structured** ``error_kind`` the source's
    :class:`RetryPolicy` marks retryable is repeated *inside the same slot*, after a
    deterministic backoff, up to ``max_attempts`` (default 2 = one retry). A source's
    attempts are strictly serial and hold one concurrency slot until the source is
    finished, so peak concurrent adapter calls never exceed ``max_concurrency``. Only
    the **final** result is returned for merging; every attempt is kept in the trace.
Wall-clock deadline (closes Phase 2 review finding P2-R-09)
    ``SourceConfig.deadline_seconds`` is the **total** budget for the source: attempt
    1 **+ every backoff pause + every retry**, enforced by one ``asyncio.timeout`` at
    this boundary (adapters untouched). It is never multiplied by ``max_attempts``.
    On expiry only that source becomes ``NETWORK_ERROR`` / ``SOURCE_DEADLINE`` with
    the real elapsed time. If it runs out during a backoff pause the next attempt is
    never started (the trace says so). The clock starts when the source starts
    executing, not while it waits for a concurrency slot -- and (C5) not while an
    attempt waits for a shared *host permit* either: the deadline is suspended for
    that wait and re-armed with exactly the time that remained.
Shared resource control (Phase 3 C5, ``governor=``)
    Per source execution: breaker admission (an open breaker returns a structured
    ``NETWORK_ERROR`` / ``CIRCUIT_OPEN`` result with no host permit and no ``adapter.fetch``);
    per attempt: a host permit (never held across a retry backoff), then a re-check that the
    admission is still current (a stale one sends nothing); finally the FINAL result is
    recorded once. Cancellation / fatal exceptions only release the ticket and permit.
Cancellation and fatal exceptions
    * The awaiting task being cancelled (a caller cancelling the aggregate lookup)
      propagates ``asyncio.CancelledError`` unchanged; siblings are cancelled, no
      task is left running, and cancellation is never treated as a retryable failure
      or interrupts into "attempt 2".
    * An adapter *itself* raising ``CancelledError`` while its task has **no**
      pending cancellation request is a misbehaving adapter: that source becomes
      ``INVALID_RESPONSE`` / ``ADAPTER_EXCEPTION`` and the other sources continue.
    * ``KeyboardInterrupt``, ``SystemExit``, ``GeneratorExit`` and any other
      non-``Exception`` ``BaseException`` are *fatal control flow*: the **original**
      exception object is re-raised to the caller (never wrapped in a
      ``BaseExceptionGroup``, never turned into a source result); siblings are
      cancelled first.
    * Known limit: an adapter that catches and swallows ``CancelledError`` and keeps
      running cannot be interrupted by ``asyncio.timeout``; stronger isolation
      (thread/process) is out of scope for the adopted, in-repo adapters, which do
      not swallow cancellation (tested).
Fail closed
    Every attempt's return value goes through :func:`validate_source_result`: a wrong
    ``source_id``, a non-``SourceResult`` or a ``SUCCESS`` for another film becomes
    ``INVALID_RESPONSE`` / ``RESULT_CONTRACT_MISMATCH`` (never retried).
Bounded concurrency
    An ``asyncio.Semaphore(max_concurrency)``.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Awaitable, Callable, Sequence

from fc2_metadata_core.aggregation.config import DEFAULT_MAX_CONCURRENCY, MAX_CONCURRENCY_LIMIT, SourceConfig
from fc2_metadata_core.aggregation.merge import invalid_response_result, validate_source_result
from fc2_metadata_core.aggregation.models import SourceAttempt, SourceExecutionTrace
from fc2_metadata_core.aggregation.policy import AggregationConfigError
from fc2_metadata_core.aggregation.retry import RetryPolicy
from fc2_metadata_core.http.client import SourceHttpClient
from fc2_metadata_core.models.source_result import SourceErrorKind, SourceResult, SourceStatus
from fc2_metadata_core.resource_control import (
    HostKey,
    HostPermit,
    SourceAdmission,
    SourceResourceGovernor,
    circuit_open_result,
)
from fc2_metadata_core.sources.base import SourceAdapter

__all__ = ["SourceTarget", "execute_sources", "execute_sources_traced"]


@dataclass(frozen=True, slots=True)
class SourceTarget:
    """One source to run: its configuration, the adapter built for it, its retry policy and (C5) the host identity
    its requests go to (taken from the configured, validated base URL; needed only when a governor is used)."""

    config: SourceConfig
    adapter: SourceAdapter
    retry_policy: RetryPolicy = field(default_factory=RetryPolicy)
    host: HostKey | None = None

    def __post_init__(self) -> None:
        if self.host is not None and not isinstance(self.host, HostKey):
            raise AggregationConfigError("SourceTarget.host must be a HostKey or None")
        if not isinstance(self.config, SourceConfig):
            raise AggregationConfigError("SourceTarget.config must be a SourceConfig")
        if not isinstance(self.adapter, SourceAdapter):
            raise AggregationConfigError("SourceTarget.adapter must be a SourceAdapter")
        if not isinstance(self.retry_policy, RetryPolicy):
            raise AggregationConfigError("SourceTarget.retry_policy must be a RetryPolicy")
        if self.adapter.source_id != self.config.source_id:
            raise AggregationConfigError(
                f"adapter source_id {self.adapter.source_id!r} does not match configured "
                f"source_id {self.config.source_id!r}"
            )


class _FatalSignal(Exception):
    """Carries a fatal ``BaseException`` out of a child task without ``BaseExceptionGroup`` wrapping.

    **Metadata-free by construction** (C5 audit, same rule as the C4 batch carrier): it only *holds* the original
    object and never reads its class name, text or args -- a hostile metaclass / ``__name__`` on a fatal
    exception must not be able to replace the fatal itself with an error raised from here.
    """

    __slots__ = ("original",)

    def __init__(self, original: BaseException) -> None:
        super().__init__()
        self.original = original


@dataclass
class _Progress:
    """Mutable, task-local scratch for one source's execution (never published)."""

    attempts: list[SourceAttempt] = field(default_factory=list)
    phase: str = "idle"  # "attempt" | "backoff" | "waiting" (queued for a host permit) | "idle"
    sequence: int = 0
    attempt_started: float = 0.0
    backoff_before: float = 0.0
    scope: asyncio.Timeout | None = None  # the source-deadline scope (suspended while queued for a host permit)
    queued_seconds: float = 0.0  # time spent queued for host permits: not charged to the deadline


@dataclass(frozen=True, slots=True)
class _Resources:
    """The governor and this execution's admission ticket (C5). Absent when no governor is configured."""

    governor: SourceResourceGovernor
    admission: SourceAdmission


def _elapsed_ms(started: float, clock: Callable[[], float]) -> float:
    return max(0.0, (clock() - started) * 1000.0)


def _deadline_result(source_id: str, deadline_seconds: float, elapsed_ms: float) -> SourceResult:
    return SourceResult(
        source_id=source_id,
        status=SourceStatus.NETWORK_ERROR,
        metadata=None,
        elapsed_ms=elapsed_ms,
        error_kind=SourceErrorKind.SOURCE_DEADLINE,
        error_detail=(
            f"{source_id}: source execution deadline exceeded "
            f"({deadline_seconds:g}s wall clock, {elapsed_ms:.0f} ms elapsed)"
        ),
    )


async def _run_attempt(
    number: str, target: SourceTarget, client: SourceHttpClient, clock: Callable[[], float]
) -> SourceResult:
    """One ``adapter.fetch`` -> a validated ``SourceResult``; only a caller cancellation or a fatal
    exception ever escapes."""
    source_id = target.config.source_id
    started = clock()
    try:
        candidate = await target.adapter.fetch(number, client)
    except asyncio.CancelledError:
        task = asyncio.current_task()
        if task is not None and task.cancelling() > 0:
            raise  # a real cancellation request (caller, sibling teardown or our own deadline)
        return invalid_response_result(
            source_id,
            f"{source_id}: unexpected adapter exception CancelledError (no cancellation was requested)",
            elapsed_ms=_elapsed_ms(started, clock),
            error_kind=SourceErrorKind.ADAPTER_EXCEPTION,
        )
    except Exception as exc:
        return invalid_response_result(
            source_id,
            f"{source_id}: unexpected adapter exception {type(exc).__name__}",
            elapsed_ms=_elapsed_ms(started, clock),
            error_kind=SourceErrorKind.ADAPTER_EXCEPTION,
        )
    except BaseException as exc:  # KeyboardInterrupt, SystemExit, GeneratorExit, custom BaseException
        raise _FatalSignal(exc) from None
    if isinstance(candidate, SourceResult) and candidate.error_kind is SourceErrorKind.CIRCUIT_OPEN:
        # Only this boundary may say "circuit open"; an adapter claiming it is a contract violation (fail closed).
        return invalid_response_result(
            source_id,
            f"{source_id}: adapter returned a CIRCUIT_OPEN result, which only the execution boundary may produce",
            elapsed_ms=candidate.elapsed_ms,
        )
    return validate_source_result(source_id, number, candidate, elapsed_ms=_elapsed_ms(started, clock))


async def _one_attempt(
    number: str,
    target: SourceTarget,
    client: SourceHttpClient,
    clock: Callable[[], float],
    progress: _Progress,
    sequence: int,
    backoff: float,
) -> SourceResult:
    """Run attempt ``sequence`` (the permit, if any, is already held) and record it in ``progress``."""
    progress.phase = "attempt"
    progress.backoff_before = backoff
    progress.attempt_started = clock()
    result = await _run_attempt(number, target, client, clock)
    progress.attempts.append(
        SourceAttempt(
            sequence=sequence,
            status=result.status,
            error_kind=result.error_kind,
            elapsed_ms=_elapsed_ms(progress.attempt_started, clock),
            completed=True,
            backoff_before_seconds=backoff,
        )
    )
    progress.phase = "idle"
    return result


async def _acquire_host_permit(
    resources: _Resources, progress: _Progress, clock: Callable[[], float]
) -> HostPermit:
    """Wait for a host permit WITHOUT spending the source's execution deadline (C5 contract §5.1).

    The deadline scope is suspended while queued and re-armed with exactly the time that remained, so host
    contention can never make a source that has not sent a request time out. A cancellation while waiting
    propagates (the limiter removes the waiter); nothing is held afterwards."""
    scope = progress.scope
    loop = asyncio.get_running_loop()
    when = scope.when() if scope is not None else None
    remaining = None if when is None else max(0.0, when - loop.time())
    queued_from = clock()
    progress.phase = "waiting"
    if scope is not None and remaining is not None:
        scope.reschedule(None)
    permit = await resources.governor.acquire_host_permit(resources.admission)
    try:
        progress.queued_seconds += max(0.0, clock() - queued_from)
        if scope is not None and remaining is not None:
            scope.reschedule(loop.time() + remaining)
    except BaseException:
        permit.release()  # never return holding a permit the caller will not own
        raise
    return permit


async def _attempt_loop(
    number: str,
    target: SourceTarget,
    client: SourceHttpClient,
    clock: Callable[[], float],
    sleep: Callable[[float], Awaitable[None]],
    progress: _Progress,
    resources: _Resources | None = None,
) -> SourceResult:
    policy = target.retry_policy
    previous: SourceResult | None = None
    while True:
        progress.sequence += 1
        sequence = progress.sequence
        backoff = policy.backoff_before_attempt(sequence)
        if sequence > 1:
            progress.phase = "backoff"
            await sleep(backoff)  # no host permit is held across the pause
        if resources is None:
            result = await _one_attempt(number, target, client, clock, progress, sequence, backoff)
        else:
            with await _acquire_host_permit(resources, progress, clock):
                if not resources.governor.is_current(resources.admission):
                    # The breaker changed state while this call queued / backed off: send nothing. A first attempt
                    # is answered "circuit open"; a retry is simply not made (the real earlier failure stands).
                    progress.phase = "idle"
                    return previous if previous is not None else circuit_open_result(target.config.source_id)
                result = await _one_attempt(number, target, client, clock, progress, sequence, backoff)
        if not policy.should_retry(result, sequence):
            return result
        previous = result


async def _run_source(
    number: str,
    target: SourceTarget,
    client: SourceHttpClient,
    clock: Callable[[], float],
    sleep: Callable[[float], Awaitable[None]],
    resources: _Resources | None,
) -> SourceExecutionTrace:
    source_id = target.config.source_id
    deadline = target.config.deadline_seconds
    max_attempts = target.retry_policy.max_attempts
    started = clock()
    progress = _Progress()
    try:
        async with asyncio.timeout(deadline) as scope:
            progress.scope = scope
            final = await _attempt_loop(number, target, client, clock, sleep, progress, resources)
    except TimeoutError:
        # Only the scope's own expiry can surface here: an adapter's TimeoutError is
        # caught inside _run_attempt and becomes ADAPTER_EXCEPTION.
        elapsed = max(0.0, _elapsed_ms(started, clock) - progress.queued_seconds * 1000.0)
        attempts = list(progress.attempts)
        if progress.phase == "attempt":
            attempts.append(
                SourceAttempt(
                    sequence=progress.sequence,
                    status=SourceStatus.NETWORK_ERROR,
                    error_kind=SourceErrorKind.SOURCE_DEADLINE,
                    elapsed_ms=_elapsed_ms(progress.attempt_started, clock),
                    completed=False,
                    backoff_before_seconds=progress.backoff_before,
                )
            )
            during = "attempt"
        else:
            during = "backoff"  # attempt (sequence) never started
        if not scope.expired():  # cannot happen; never mislabel a foreign TimeoutError as our deadline
            raise
        return SourceExecutionTrace(
            source_id=source_id,
            attempts=tuple(attempts),
            final_result=_deadline_result(source_id, deadline, elapsed),
            max_attempts=max_attempts,
            deadline_exceeded=True,
            deadline_during=during,
        )
    return SourceExecutionTrace(
        source_id=source_id,
        attempts=tuple(progress.attempts),
        final_result=final,
        max_attempts=max_attempts,
    )


async def _execute_one(
    number: str,
    target: SourceTarget,
    client: SourceHttpClient,
    semaphore: asyncio.Semaphore,
    clock: Callable[[], float],
    sleep: Callable[[float], Awaitable[None]],
    governor: SourceResourceGovernor | None = None,
) -> SourceExecutionTrace:
    source_id = target.config.source_id
    async with semaphore:  # held for the whole retry sequence of this source
        if governor is None:
            return await _run_source(number, target, client, clock, sleep, None)
        admission = None
        try:
            admission = governor.admit(source_id, target.host)  # type: ignore[arg-type]  # host checked up front
            if admission is None:  # circuit open: no host permit, no request, no attempt
                return SourceExecutionTrace(
                    source_id=source_id,
                    attempts=(),
                    final_result=circuit_open_result(source_id),
                    max_attempts=target.retry_policy.max_attempts,
                )
            trace = await _run_source(number, target, client, clock, sleep, _Resources(governor, admission))
            governor.record_result(admission, trace.final_result)  # exactly once: the FINAL result
            return trace
        finally:
            if admission is not None:
                governor.release(admission)  # no-op once recorded; frees the ticket on cancel / fatal


def _validate_arguments(
    targets: Sequence[SourceTarget], max_concurrency: object, governor: object = None
) -> None:
    if isinstance(max_concurrency, bool) or not isinstance(max_concurrency, int) or not (
        1 <= max_concurrency <= MAX_CONCURRENCY_LIMIT
    ):
        raise AggregationConfigError(f"max_concurrency must be an int in 1..{MAX_CONCURRENCY_LIMIT}")
    if not targets:
        raise AggregationConfigError("no sources to execute")
    if governor is not None:
        if not isinstance(governor, SourceResourceGovernor):
            raise AggregationConfigError("governor must be a SourceResourceGovernor or None")
        missing = [t.config.source_id for t in targets if t.host is None]
        if missing:
            raise AggregationConfigError(
                f"a governor needs every target's host identity (from its configured base URL); missing for {missing!r}"
            )


async def execute_sources_traced(
    number: str,
    targets: Sequence[SourceTarget],
    client: SourceHttpClient,
    *,
    max_concurrency: int = DEFAULT_MAX_CONCURRENCY,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    governor: SourceResourceGovernor | None = None,
) -> tuple[SourceExecutionTrace, ...]:
    """Run every target; return one trace (attempts + final result) per target, in target order.

    ``number`` must already be canonical (the engine checks it once up front).
    ``clock`` and ``sleep`` are injectable for tests; production uses
    ``time.monotonic`` / ``asyncio.sleep``. Note that ``sleep`` is only the backoff
    pause: the total deadline is enforced by the event loop's own timer.

    ``governor`` (Phase 3 C5, optional): the shared resource domain -- per-host attempt limiter and per-source
    circuit breaker. Every target must then carry its ``host``. ``None`` = no resource control (C4 behaviour).
    """
    _validate_arguments(targets, max_concurrency, governor)
    semaphore = asyncio.Semaphore(max_concurrency)
    try:
        # TaskGroup: if the caller cancels us, every child is cancelled and the
        # CancelledError propagates; no child outlives this call.
        async with asyncio.TaskGroup() as group:
            tasks = [
                group.create_task(_execute_one(number, target, client, semaphore, clock, sleep, governor))
                for target in targets
            ]
    except ExceptionGroup as group_error:
        signals = [e for e in group_error.exceptions if isinstance(e, _FatalSignal)]
        if signals and len(signals) == len(group_error.exceptions):
            raise signals[0].original  # the ORIGINAL fatal exception object, unwrapped
        raise
    return tuple(task.result() for task in tasks)


async def execute_sources(
    number: str,
    targets: Sequence[SourceTarget],
    client: SourceHttpClient,
    *,
    max_concurrency: int = DEFAULT_MAX_CONCURRENCY,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    governor: SourceResourceGovernor | None = None,
) -> tuple[SourceResult, ...]:
    """:func:`execute_sources_traced` reduced to each source's final ``SourceResult`` (config order)."""
    traces = await execute_sources_traced(
        number, targets, client, max_concurrency=max_concurrency, clock=clock, sleep=sleep, governor=governor
    )
    return tuple(trace.final_result for trace in traces)
