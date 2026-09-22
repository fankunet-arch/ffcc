"""SourceResourceGovernor: one explicit, shared resource domain (Phase 3 C5).

::

    engines / BatchSchedulers that were handed the SAME governor share ONE resource domain:
      * per-host concurrency limiter   (HostKey  -> at most N live network attempts)
      * per-source circuit breaker     (source_id -> CLOSED / OPEN / HALF_OPEN)
    a DIFFERENT governor instance is an independent domain (its budgets simply add up).

There is no module-global singleton: the governor is an ordinary object whose lifetime the caller controls.

Per source execution the caller (``aggregation.execution``) does::

    admission = governor.admit(source_id, host)          # sync; None -> circuit open, do not fetch
    try:
        permit = await governor.acquire_host_permit(admission)   # per network attempt; may wait
        with permit:
            if not governor.is_current(admission): ...            # breaker changed while queued: do not send
            result = await adapter.fetch(...)
        governor.record_result(admission, final_result)          # exactly once, the FINAL result
    finally:
        governor.release(admission)                              # idempotent: cancel / fatal / not attempted

Tickets are opaque, bound to their governor and stamped with the breaker epoch they were admitted under; see
``docs/specifications/PHASE3_RESOURCE_CONTROL_CONTRACT.md`` §6-§7. This module reads only structured fields
(``SourceResult.status`` / ``error_kind`` through ``observation_for``), the configured host key, epochs and the
injected monotonic clock -- never a trace, an ``error_detail`` or an exception's type/message.

Memory: one limiter per distinct host, one breaker per distinct ``source_id``; nothing per item.
Single event loop, not thread-safe.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable

from fc2_metadata_core.models.source_result import SourceResult
from fc2_metadata_core.resource_control.circuit_breaker import (
    BreakerSnapshot,
    CircuitBreaker,
    Observation,
    observation_for,
)
from fc2_metadata_core.resource_control.config import CircuitBreakerPolicy, HostLimitPolicy
from fc2_metadata_core.resource_control.errors import ResourceControlConfigError, ResourceControlError
from fc2_metadata_core.resource_control.host_key import HostKey
from fc2_metadata_core.resource_control.host_limiter import HostLimiter, HostPermit, HostSnapshot

__all__ = ["SourceResourceGovernor", "SourceAdmission", "GovernorSnapshot"]

_ISSUE_KEY = object()  # only the governor holds it: callers cannot construct a ticket


@dataclass(frozen=True, slots=True)
class GovernorSnapshot:
    """Immutable diagnostics of the whole domain, sorted deterministically (hosts by key, breakers by source id)."""

    hosts: tuple[HostSnapshot, ...]
    breakers: tuple[BreakerSnapshot, ...]


class SourceAdmission:
    """An opaque admission ticket. Read-only ``source_id`` / ``host`` / ``is_probe``; everything else is private."""

    __slots__ = ("_owner", "_source_id", "_host", "_epoch", "_probe", "_settled")

    def __init__(self, key: object, owner: "SourceResourceGovernor", source_id: str, host: HostKey, epoch: int, probe: bool):
        if key is not _ISSUE_KEY:
            raise TypeError("SourceAdmission tickets are issued by SourceResourceGovernor.admit() only")
        self._owner = owner
        self._source_id = source_id
        self._host = host
        self._epoch = epoch
        self._probe = probe
        self._settled = False

    @property
    def source_id(self) -> str:
        return self._source_id

    @property
    def host(self) -> HostKey:
        return self._host

    @property
    def is_probe(self) -> bool:
        return self._probe

    @property
    def settled(self) -> bool:
        return self._settled


class SourceResourceGovernor:
    """A shared resource domain: per-host limiter + per-source circuit breaker (see the module docstring)."""

    def __init__(
        self,
        *,
        host_limits: HostLimitPolicy = HostLimitPolicy(),
        breaker: CircuitBreakerPolicy = CircuitBreakerPolicy(),
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if not isinstance(host_limits, HostLimitPolicy):
            raise ResourceControlConfigError("host_limits must be a HostLimitPolicy")
        if not isinstance(breaker, CircuitBreakerPolicy):
            raise ResourceControlConfigError("breaker must be a CircuitBreakerPolicy")
        if not callable(clock):
            raise ResourceControlConfigError("clock must be a callable returning monotonic seconds")
        self._host_limits = host_limits
        self._breaker_policy = breaker
        self._clock = clock
        self._limiters: dict[HostKey, HostLimiter] = {}
        self._breakers: dict[str, CircuitBreaker] = {}

    @property
    def host_limits(self) -> HostLimitPolicy:
        return self._host_limits

    @property
    def breaker_policy(self) -> CircuitBreakerPolicy:
        return self._breaker_policy

    # -- admission ---------------------------------------------------------------------------------------------

    def admit(self, source_id: str, host: HostKey) -> SourceAdmission | None:
        """Breaker admission for one source execution. ``None`` = circuit open: send nothing, take no host permit."""
        if not isinstance(source_id, str) or not source_id:
            raise ResourceControlError("source_id must be a non-empty str")
        if not isinstance(host, HostKey):
            raise ResourceControlError("host must be a HostKey")
        breaker = self._breakers.get(source_id)
        if breaker is None:
            breaker = self._breakers[source_id] = CircuitBreaker(source_id, self._breaker_policy, self._clock)
        granted = breaker.admit()
        if granted is None:
            return None
        epoch, probe = granted
        return SourceAdmission(_ISSUE_KEY, self, source_id, host, epoch, probe)

    def is_current(self, admission: SourceAdmission) -> bool:
        """Is the admission still valid (the breaker has not changed epoch since it was granted)?"""
        self._require_live(admission)
        return self._breakers[admission._source_id].is_current(admission._epoch)

    # -- host permits ------------------------------------------------------------------------------------------

    async def acquire_host_permit(self, admission: SourceAdmission) -> HostPermit:
        """Wait for a permit on the admission's host. Cancellation while waiting propagates; nothing leaks."""
        self._require_live(admission)
        host = admission._host
        limiter = self._limiters.get(host)
        if limiter is None:
            limiter = self._limiters[host] = HostLimiter(host, self._host_limits.limit_for(host))
        return await limiter.acquire()

    # -- settling ----------------------------------------------------------------------------------------------

    def record_result(self, admission: SourceAdmission, result: SourceResult) -> None:
        """Feed the source execution's FINAL result to the breaker (once). A stale ticket changes no state; a
        ``CIRCUIT_OPEN`` result is not an observation. Raises :class:`ResourceControlError` on misuse."""
        self._require_live(admission)
        if not isinstance(result, SourceResult):
            raise ResourceControlError("record_result needs the final SourceResult")
        if result.source_id != admission._source_id:
            raise ResourceControlError("the result belongs to another source than the admission")
        observation: Observation = observation_for(result)
        admission._settled = True
        self._breakers[admission._source_id].settle(admission._epoch, admission._probe, observation)

    def release(self, admission: SourceAdmission) -> None:
        """End a ticket without an observation (cancelled / fatal / request not sent). Idempotent."""
        if not isinstance(admission, SourceAdmission) or admission._owner is not self:
            raise ResourceControlError("admission was not issued by this governor")
        if admission._settled:
            return
        admission._settled = True
        self._breakers[admission._source_id].abandon(admission._epoch, admission._probe)

    def _require_live(self, admission: object) -> None:
        if not isinstance(admission, SourceAdmission) or admission._owner is not self:
            raise ResourceControlError("admission was not issued by this governor")
        if admission._settled:
            raise ResourceControlError("admission is already settled")

    # -- diagnostics -------------------------------------------------------------------------------------------

    def snapshot(self) -> GovernorSnapshot:
        return GovernorSnapshot(
            hosts=tuple(self._limiters[key].snapshot() for key in sorted(self._limiters)),
            breakers=tuple(self._breakers[sid].snapshot() for sid in sorted(self._breakers)),
        )
