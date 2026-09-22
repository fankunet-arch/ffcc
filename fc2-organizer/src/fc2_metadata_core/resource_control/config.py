"""Immutable resource-control configuration (Phase 3 C5).

``HostLimitPolicy``
    the static per-host concurrency budget (default + immutable per-host overrides).
``CircuitBreakerPolicy``
    the per-source breaker thresholds and cooldown.

Both are frozen, hashable and validated at construction (:class:`ResourceControlConfigError`), before any
network use. ``bool`` is never accepted as a number, every number is finite and bounded.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Mapping

from fc2_metadata_core.resource_control.errors import ResourceControlConfigError
from fc2_metadata_core.resource_control.host_key import HostKey

__all__ = [
    "HostLimitPolicy",
    "CircuitBreakerPolicy",
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

DEFAULT_MAX_IN_FLIGHT_PER_HOST = 4
HOST_LIMIT_MAX = 64
MAX_HOST_OVERRIDES = 256

DEFAULT_FAILURE_THRESHOLD = 3
FAILURE_THRESHOLD_MAX = 100
DEFAULT_OPEN_DURATION_SECONDS = 30.0
OPEN_DURATION_MAX_SECONDS = 3600.0
DEFAULT_HALF_OPEN_MAX_CALLS = 1
HALF_OPEN_MAX_CALLS_LIMIT = 16


def _bounded_int(label: str, value: object, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= maximum:
        raise ResourceControlConfigError(f"{label} must be an int in 1..{maximum}")
    return value


@dataclass(frozen=True, slots=True)
class HostLimitPolicy:
    """Static per-host budget of concurrent network attempts (one governor = one resource domain).

    ``overrides`` is an immutable tuple of ``(HostKey, limit)`` pairs, sorted by key, with no duplicate key;
    use :meth:`create` to pass a plain ``{"host:port": limit}`` mapping.
    """

    default_max_in_flight_per_host: int = DEFAULT_MAX_IN_FLIGHT_PER_HOST
    overrides: tuple[tuple[HostKey, int], ...] = ()

    def __post_init__(self) -> None:
        _bounded_int("default_max_in_flight_per_host", self.default_max_in_flight_per_host, HOST_LIMIT_MAX)
        if not isinstance(self.overrides, tuple) or len(self.overrides) > MAX_HOST_OVERRIDES:
            raise ResourceControlConfigError(
                f"overrides must be a tuple of at most {MAX_HOST_OVERRIDES} (HostKey, limit) pairs"
            )
        seen: set[HostKey] = set()
        for entry in self.overrides:
            if not (isinstance(entry, tuple) and len(entry) == 2 and isinstance(entry[0], HostKey)):
                raise ResourceControlConfigError("each override must be a (HostKey, limit) 2-tuple")
            key, limit = entry
            _bounded_int(f"override limit for {key}", limit, HOST_LIMIT_MAX)
            if key in seen:
                raise ResourceControlConfigError(f"duplicate host override {key}")
            seen.add(key)

    @classmethod
    def create(
        cls, default_max_in_flight_per_host: int = DEFAULT_MAX_IN_FLIGHT_PER_HOST, overrides: Mapping[str, int] | None = None
    ) -> "HostLimitPolicy":
        """Friendly constructor: ``overrides`` maps ``"host:port"`` strings to limits; keys are canonicalised
        (so ``"A.example:443"`` and ``"a.example:443"`` collide and are rejected)."""
        entries: list[tuple[HostKey, int]] = []
        if overrides is not None:
            if not isinstance(overrides, Mapping):
                raise ResourceControlConfigError("overrides must be a mapping of 'host:port' to limit")
            entries = [(HostKey.parse(key), limit) for key, limit in overrides.items()]
        entries.sort(key=lambda entry: entry[0])
        return cls(default_max_in_flight_per_host, tuple(entries))

    def limit_for(self, host: HostKey) -> int:
        for key, limit in self.overrides:
            if key == host:
                return limit
        return self.default_max_in_flight_per_host


@dataclass(frozen=True, slots=True)
class CircuitBreakerPolicy:
    """Per-source breaker: ``failure_threshold`` consecutive final failures open it for
    ``open_duration_seconds``; then at most ``half_open_max_calls`` probe executions decide."""

    failure_threshold: int = DEFAULT_FAILURE_THRESHOLD
    open_duration_seconds: float = DEFAULT_OPEN_DURATION_SECONDS
    half_open_max_calls: int = DEFAULT_HALF_OPEN_MAX_CALLS

    def __post_init__(self) -> None:
        _bounded_int("failure_threshold", self.failure_threshold, FAILURE_THRESHOLD_MAX)
        _bounded_int("half_open_max_calls", self.half_open_max_calls, HALF_OPEN_MAX_CALLS_LIMIT)
        duration = self.open_duration_seconds
        if isinstance(duration, bool) or not isinstance(duration, (int, float)):
            raise ResourceControlConfigError("open_duration_seconds must be a number")
        if not math.isfinite(duration) or not 0 < duration <= OPEN_DURATION_MAX_SECONDS:
            raise ResourceControlConfigError(
                f"open_duration_seconds must be finite and in (0, {OPEN_DURATION_MAX_SECONDS:g}]"
            )
