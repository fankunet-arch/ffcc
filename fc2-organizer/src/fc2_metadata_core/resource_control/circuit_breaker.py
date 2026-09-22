"""Per-source circuit breaker state machine (Phase 3 C5). Pure, synchronous, clock-injected.

The breaker is fed **one observation per source execution: its final ``SourceResult``** -- decided from
``status`` only (plus the single non-observation kind ``CIRCUIT_OPEN``); never from ``error_detail`` text, a trace,
metadata or timings. States ``CLOSED`` / ``OPEN`` / ``HALF_OPEN``; the transition table, the epoch/stale-completion
rule and the half-open probe accounting are frozen in ``docs/specifications/PHASE3_RESOURCE_CONTROL_CONTRACT.md`` §6.

Every transition bumps ``epoch``. An admission stamps the ticket with the epoch it saw; an observation is applied
only when that epoch is still current, so a completion that belongs to an *older* state can never reverse a newer
one (a late success cannot close a breaker that has just opened). All methods are synchronous with no ``await``:
atomic on one event loop, not thread-safe.

Time is whatever monotonic callable is injected (``time.monotonic`` by default); nothing here sleeps or reads a
wall clock.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Callable, Mapping

from fc2_metadata_core.models.source_result import SourceErrorKind, SourceResult, SourceStatus
from fc2_metadata_core.resource_control.config import CircuitBreakerPolicy

__all__ = [
    "BreakerState",
    "Observation",
    "BreakerSnapshot",
    "CircuitBreaker",
    "observation_for",
    "circuit_open_result",
]


class BreakerState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class Observation(Enum):
    """What one final ``SourceResult`` says about the source's health."""

    HEALTHY = "healthy"
    FAILURE = "failure"
    NONE = "none"  # the breaker's own answer (CIRCUIT_OPEN): not a health observation


# Exhaustive over SourceStatus. NOT_FOUND is healthy: the source answered, the catalogue just lacks the id.
_STATUS_OBSERVATION: Mapping[SourceStatus, Observation] = MappingProxyType(
    {
        SourceStatus.SUCCESS: Observation.HEALTHY,
        SourceStatus.NOT_FOUND: Observation.HEALTHY,
        SourceStatus.BLOCKED: Observation.FAILURE,
        SourceStatus.RATE_LIMITED: Observation.FAILURE,
        SourceStatus.NETWORK_ERROR: Observation.FAILURE,
        SourceStatus.PARSE_ERROR: Observation.FAILURE,
        SourceStatus.INVALID_RESPONSE: Observation.FAILURE,
    }
)
if set(_STATUS_OBSERVATION) != set(SourceStatus):  # a new SourceStatus needs an explicit breaker decision
    raise RuntimeError("circuit_breaker._STATUS_OBSERVATION must cover every SourceStatus exactly")


def observation_for(result: SourceResult) -> Observation:
    """The health observation a final ``SourceResult`` carries (structured fields only)."""
    if result.error_kind is SourceErrorKind.CIRCUIT_OPEN:
        return Observation.NONE
    return _STATUS_OBSERVATION[result.status]


def circuit_open_result(source_id: str) -> SourceResult:
    """The structured answer of an open breaker: a ``NETWORK_ERROR`` / ``CIRCUIT_OPEN`` result, no request made."""
    return SourceResult(
        source_id=source_id,
        status=SourceStatus.NETWORK_ERROR,
        metadata=None,
        elapsed_ms=0.0,
        error_kind=SourceErrorKind.CIRCUIT_OPEN,
        error_detail=f"{source_id}: circuit breaker open; lookup not attempted",
    )


@dataclass(frozen=True, slots=True)
class BreakerSnapshot:
    """Immutable public diagnostics of one source's breaker (scalars, an enum and the source id only)."""

    source_id: str
    state: BreakerState
    consecutive_failures: int
    epoch: int
    in_flight: int
    half_open_probes_in_flight: int
    opened_at: float | None
    remaining_cooldown_seconds: float | None
    times_opened: int


class CircuitBreaker:
    """The mutable state machine of one ``source_id``. Owned by the governor; never handed to callers."""

    __slots__ = (
        "_source_id",
        "_policy",
        "_clock",
        "_state",
        "_epoch",
        "_failures",
        "_opened_at",
        "_in_flight",
        "_probes",
        "_times_opened",
    )

    def __init__(self, source_id: str, policy: CircuitBreakerPolicy, clock: Callable[[], float]) -> None:
        self._source_id = source_id
        self._policy = policy
        self._clock = clock
        self._state = BreakerState.CLOSED
        self._epoch = 0
        self._failures = 0
        self._opened_at: float | None = None
        self._in_flight = 0
        self._probes = 0
        self._times_opened = 0

    @property
    def epoch(self) -> int:
        return self._epoch

    @property
    def state(self) -> BreakerState:
        return self._state

    # -- admission ---------------------------------------------------------------------------------------------

    def admit(self) -> tuple[int, bool] | None:
        """``(epoch, is_probe)`` for a granted admission, ``None`` when the call must short-circuit."""
        if self._state is BreakerState.OPEN:
            opened_at = self._opened_at
            if opened_at is not None and self._clock() - opened_at < self._policy.open_duration_seconds:
                return None
            self._enter(BreakerState.HALF_OPEN)
        if self._state is BreakerState.HALF_OPEN:
            if self._probes >= self._policy.half_open_max_calls:
                return None
            self._probes += 1
            self._in_flight += 1
            return self._epoch, True
        self._in_flight += 1
        return self._epoch, False

    def is_current(self, epoch: int) -> bool:
        return epoch == self._epoch

    # -- settling ----------------------------------------------------------------------------------------------

    def settle(self, epoch: int, is_probe: bool, observation: Observation) -> None:
        """Apply one final observation for a ticket; a stale ticket (older epoch) changes no state."""
        current = epoch == self._epoch
        self._retire(epoch, is_probe)
        if not current or observation is Observation.NONE:
            return
        if self._state is BreakerState.HALF_OPEN:
            if observation is Observation.HEALTHY:
                self._enter(BreakerState.CLOSED)
            else:
                self._enter(BreakerState.OPEN)
        elif self._state is BreakerState.CLOSED:
            if observation is Observation.HEALTHY:
                self._failures = 0
            else:
                self._failures += 1
                if self._failures >= self._policy.failure_threshold:
                    self._enter(BreakerState.OPEN)

    def abandon(self, epoch: int, is_probe: bool) -> None:
        """A ticket ended without an observation (cancel / fatal / request not sent): free its accounting only."""
        self._retire(epoch, is_probe)

    def _retire(self, epoch: int, is_probe: bool) -> None:
        self._in_flight -= 1
        if is_probe and epoch == self._epoch:
            self._probes -= 1

    def _enter(self, state: BreakerState) -> None:
        self._state = state
        self._epoch += 1
        self._probes = 0
        if state is BreakerState.OPEN:
            self._opened_at = self._clock()
            self._times_opened += 1
        elif state is BreakerState.CLOSED:
            self._failures = 0
            self._opened_at = None

    # -- diagnostics -------------------------------------------------------------------------------------------

    def snapshot(self) -> BreakerSnapshot:
        remaining: float | None = None
        if self._state is BreakerState.OPEN and self._opened_at is not None:
            remaining = max(0.0, self._policy.open_duration_seconds - (self._clock() - self._opened_at))
        return BreakerSnapshot(
            source_id=self._source_id,
            state=self._state,
            consecutive_failures=self._failures,
            epoch=self._epoch,
            in_flight=self._in_flight,
            half_open_probes_in_flight=self._probes,
            opened_at=self._opened_at if self._state is not BreakerState.CLOSED else None,
            remaining_cooldown_seconds=remaining,
            times_opened=self._times_opened,
        )
