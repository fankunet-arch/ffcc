"""Per-host permits and per-source circuit state, shared by explicit injection.

State transitions are synchronous between asyncio suspension points. Tokens are
opaque, identity checked, and never exposed as diagnostics.
"""

from __future__ import annotations

import asyncio
import ipaddress
import math
import time
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Mapping
from urllib.parse import urlsplit

from fc2_metadata_core.aggregation.config import validate_base_url
from fc2_metadata_core.aggregation.policy import AggregationConfigError
from fc2_metadata_core.models.source_result import SourceErrorKind, SourceResult, SourceStatus


def canonical_host_key(base_url: str) -> tuple[str, int]:
    """Canonical host and effective port of an already configured base URL."""
    validate_base_url(base_url)
    parts = urlsplit(base_url)
    host = parts.hostname.rstrip(".").lower()
    try:
        host = ipaddress.ip_address(host).compressed
    except ValueError:
        pass
    return host, parts.port or (443 if parts.scheme == "https" else 80)


@dataclass(frozen=True, slots=True)
class HostPolicy:
    default_max_in_flight_per_host: int = 3
    per_host_limits: tuple[tuple[tuple[str, int], int], ...] = ()

    def __post_init__(self) -> None:
        value = self.default_max_in_flight_per_host
        if type(value) is not int or not 1 <= value <= 64:
            raise AggregationConfigError("host limit must be an int in 1..64")
        if type(self.per_host_limits) is not tuple:
            raise AggregationConfigError("per_host_limits must be an immutable tuple")
        seen = set()
        for entry in self.per_host_limits:
            if type(entry) is not tuple or len(entry) != 2:
                raise AggregationConfigError("host override must be (host key, limit)")
            key, limit = entry
            if (type(key) is not tuple or len(key) != 2 or type(key[0]) is not str
                    or type(key[1]) is not int or key != canonical_host_key(
                        f"https://[{key[0]}]:{key[1]}" if ":" in key[0]
                        else f"https://{key[0]}:{key[1]}")):
                raise AggregationConfigError("host override key must be canonical (hostname, port)")
            if key in seen or type(limit) is not int or not 1 <= limit <= 64:
                raise AggregationConfigError("duplicate host override or limit outside 1..64")
            seen.add(key)

    @classmethod
    def create(cls, default_max_in_flight_per_host: int = 3,
               per_host_overrides: Mapping[str, int] | None = None) -> HostPolicy:
        entries = []
        seen = set()
        for url, limit in (per_host_overrides or {}).items():
            key = canonical_host_key(url)
            if key in seen:
                raise AggregationConfigError("duplicate canonical host override")
            seen.add(key)
            entries.append((key, limit))
        return cls(default_max_in_flight_per_host, tuple(sorted(entries)))

    def limit_for(self, key: tuple[str, int]) -> int:
        for candidate, limit in self.per_host_limits:
            if candidate == key:
                return limit
        return self.default_max_in_flight_per_host


@dataclass(frozen=True, slots=True)
class BreakerPolicy:
    failure_threshold: int = 3
    open_duration_seconds: float = 30.0
    half_open_max_calls: int = 1

    def __post_init__(self) -> None:
        if type(self.failure_threshold) is not int or not 1 <= self.failure_threshold <= 1000:
            raise AggregationConfigError("failure_threshold must be an int in 1..1000")
        if type(self.half_open_max_calls) is not int or not 1 <= self.half_open_max_calls <= 64:
            raise AggregationConfigError("half_open_max_calls must be an int in 1..64")
        value = self.open_duration_seconds
        if type(value) not in (int, float) or not math.isfinite(value) or not 0 < value <= 86400:
            raise AggregationConfigError("open_duration_seconds must be finite and in (0, 86400]")


class BreakerState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass(frozen=True, slots=True)
class BreakerSnapshot:
    source_id: str
    state: BreakerState
    consecutive_failures: int
    opened_at: float | None
    epoch: int
    in_flight: int
    probes: int


@dataclass(slots=True)
class _Circuit:
    state: BreakerState = BreakerState.CLOSED
    failures: int = 0
    opened_at: float | None = None
    epoch: int = 0
    probes: int = 0
    in_flight: int = 0


class _Token:
    __slots__ = ("owner", "source_id", "epoch", "probe", "active")

    def __init__(self, owner: SourceResourceGovernor, source_id: str, epoch: int, probe: bool) -> None:
        self.owner = owner
        self.source_id = source_id
        self.epoch = epoch
        self.probe = probe
        self.active = True


class SourceResourceGovernor:
    """One explicit resource domain; one event loop at a time."""

    def __init__(
        self,
        host_policy: HostPolicy = HostPolicy(),
        breaker_policy: BreakerPolicy = BreakerPolicy(),
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if not isinstance(host_policy, HostPolicy) or not isinstance(breaker_policy, BreakerPolicy):
            raise AggregationConfigError("governor policies must be HostPolicy and BreakerPolicy")
        if not callable(clock):
            raise AggregationConfigError("clock must be callable")
        self.host_policy = host_policy
        self.breaker_policy = breaker_policy
        self._clock = clock
        self._hosts: dict[tuple[str, int], asyncio.Semaphore] = {}
        self._sources: dict[str, tuple[str, int]] = {}
        self._circuits: dict[str, _Circuit] = {}
        self._active_tokens: set[_Token] = set()

    def register(self, source_id: str, base_url: str) -> None:
        if type(source_id) is not str or not source_id or source_id != source_id.strip():
            raise AggregationConfigError("source_id must be a non-empty plain string without outer whitespace")
        key = canonical_host_key(base_url)
        previous = self._sources.get(source_id)
        if previous is not None and previous != key:
            raise AggregationConfigError(f"source {source_id!r} has conflicting host identity in shared governor")
        if previous is None:
            self._sources[source_id] = key
            self._circuits[source_id] = _Circuit()
            self._hosts.setdefault(key, asyncio.Semaphore(self.host_policy.limit_for(key)))

    def snapshot(self, source_id: str) -> BreakerSnapshot:
        circuit = self._circuits[source_id]
        return BreakerSnapshot(source_id, circuit.state, circuit.failures, circuit.opened_at,
                               circuit.epoch, circuit.in_flight, circuit.probes)

    @property
    def state_size(self) -> tuple[int, int]:
        return len(self._hosts), len(self._circuits)

    def admit(self, source_id: str) -> _Token | None:
        circuit = self._circuits[source_id]
        if circuit.state is BreakerState.OPEN:
            if self._clock() - circuit.opened_at < self.breaker_policy.open_duration_seconds:
                return None
            circuit.state = BreakerState.HALF_OPEN
            circuit.epoch += 1
            circuit.probes = 0
        if circuit.state is BreakerState.HALF_OPEN and circuit.probes >= self.breaker_policy.half_open_max_calls:
            return None
        probe = circuit.state is BreakerState.HALF_OPEN
        if probe:
            circuit.probes += 1
        circuit.in_flight += 1
        token = _Token(self, source_id, circuit.epoch, probe)
        self._active_tokens.add(token)
        return token

    def valid(self, token: _Token) -> bool:
        if token.owner is not self or not token.active or token not in self._active_tokens:
            return False
        circuit = self._circuits[token.source_id]
        return token.epoch == circuit.epoch and circuit.state is (BreakerState.HALF_OPEN if token.probe else BreakerState.CLOSED)

    def abandon(self, token: _Token) -> None:
        if token.owner is not self or not token.active or token not in self._active_tokens:
            return
        token.active = False
        self._active_tokens.remove(token)
        circuit = self._circuits[token.source_id]
        circuit.in_flight -= 1
        if token.probe and token.epoch == circuit.epoch and circuit.state is BreakerState.HALF_OPEN:
            circuit.probes -= 1

    def record_result(self, token: _Token, result: SourceResult) -> None:
        if (token.owner is not self or not token.active or token not in self._active_tokens
                or result.source_id != token.source_id):
            raise ValueError("invalid governor admission token or result")
        valid = self.valid(token)
        self.abandon(token)
        if not valid:
            return  # stale completion from an earlier circuit epoch
        circuit = self._circuits[token.source_id]
        healthy = result.status in (SourceStatus.SUCCESS, SourceStatus.NOT_FOUND)
        if token.probe:
            circuit.epoch += 1
            circuit.probes = 0
            if healthy:
                circuit.state = BreakerState.CLOSED
                circuit.failures = 0
                circuit.opened_at = None
            else:
                circuit.state = BreakerState.OPEN
                circuit.failures = self.breaker_policy.failure_threshold
                circuit.opened_at = self._clock()
        elif healthy:
            circuit.failures = 0
        else:
            circuit.failures += 1
            if circuit.failures >= self.breaker_policy.failure_threshold:
                circuit.state = BreakerState.OPEN
                circuit.opened_at = self._clock()
                circuit.epoch += 1

    async def acquire_host(self, source_id: str) -> None:
        await self._hosts[self._sources[source_id]].acquire()

    def release_host(self, source_id: str) -> None:
        self._hosts[self._sources[source_id]].release()

    @staticmethod
    def circuit_open_result(source_id: str) -> SourceResult:
        return SourceResult(source_id, SourceStatus.NETWORK_ERROR, None, 0.0,
                            SourceErrorKind.CIRCUIT_OPEN, f"{source_id}: circuit open")
