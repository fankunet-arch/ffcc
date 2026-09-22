"""Shared host resource control and circuit breaker (Phase 3 C5).

A :class:`SourceResourceGovernor` is one explicit resource domain: a per-host concurrency limiter (bounding
concurrent network attempts across every ``aggregate()`` call, engine and ``BatchScheduler`` that shares the
governor) plus a per-source circuit breaker fed by each source execution's final ``SourceResult``.

Depends only on the ``SourceResult`` contract and the standard library -- never on ``batch``, ``aggregation``,
concrete adapters, ``httpx`` or ``amane``. Contract: ``docs/specifications/PHASE3_RESOURCE_CONTROL_CONTRACT.md``.
"""

from fc2_metadata_core.resource_control.circuit_breaker import (
    BreakerSnapshot,
    BreakerState,
    Observation,
    circuit_open_result,
    observation_for,
)
from fc2_metadata_core.resource_control.config import (
    DEFAULT_FAILURE_THRESHOLD,
    DEFAULT_HALF_OPEN_MAX_CALLS,
    DEFAULT_MAX_IN_FLIGHT_PER_HOST,
    DEFAULT_OPEN_DURATION_SECONDS,
    FAILURE_THRESHOLD_MAX,
    HALF_OPEN_MAX_CALLS_LIMIT,
    HOST_LIMIT_MAX,
    MAX_HOST_OVERRIDES,
    OPEN_DURATION_MAX_SECONDS,
    CircuitBreakerPolicy,
    HostLimitPolicy,
)
from fc2_metadata_core.resource_control.errors import ResourceControlConfigError, ResourceControlError
from fc2_metadata_core.resource_control.governor import GovernorSnapshot, SourceAdmission, SourceResourceGovernor
from fc2_metadata_core.resource_control.host_key import HostKey, host_key_for_base_url
from fc2_metadata_core.resource_control.host_limiter import HostLimiter, HostPermit, HostSnapshot

__all__ = [
    "SourceResourceGovernor",
    "SourceAdmission",
    "GovernorSnapshot",
    "HostKey",
    "host_key_for_base_url",
    "HostLimiter",
    "HostPermit",
    "HostSnapshot",
    "HostLimitPolicy",
    "CircuitBreakerPolicy",
    "BreakerState",
    "BreakerSnapshot",
    "Observation",
    "observation_for",
    "circuit_open_result",
    "ResourceControlError",
    "ResourceControlConfigError",
    "DEFAULT_MAX_IN_FLIGHT_PER_HOST",
    "HOST_LIMIT_MAX",
    "MAX_HOST_OVERRIDES",
    "DEFAULT_FAILURE_THRESHOLD",
    "FAILURE_THRESHOLD_MAX",
    "DEFAULT_OPEN_DURATION_SECONDS",
    "OPEN_DURATION_MAX_SECONDS",
    "DEFAULT_HALF_OPEN_MAX_CALLS",
    "HALF_OPEN_MAX_CALLS_LIMIT",
]
