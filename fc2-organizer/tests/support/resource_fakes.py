"""Offline fakes for the Phase 3 C5 resource-control tests.

``FakeClock``   a manual monotonic clock (breaker time is *never* real time in these tests).
``Meter``       counts, from inside the fake adapters, how many ``fetch`` calls are live per host label and per
                source, the peaks, the total requests -- independent evidence that does not trust the governor's
                own counters.
``Spec`` / ``make_engine``  build a real ``MultiSourceEngine`` (real registry, real config) from scripted adapters.
"""

from __future__ import annotations

import asyncio
from collections import Counter
from dataclasses import dataclass
from typing import Awaitable, Callable

from fc2_metadata_core.aggregation import AggregationConfig, MultiSourceEngine, SourceConfig
from fc2_metadata_core.aggregation.execution import SourceTarget
from fc2_metadata_core.aggregation.retry import RetryPolicy
from fc2_metadata_core.models.source_result import SourceResult, SourceStatus
from fc2_metadata_core.resource_control import SourceResourceGovernor, host_key_for_base_url
from fc2_metadata_core.sources import SourceRegistry

from support.batch_fakes import until
from support.scripted_adapters import failed, ok, scripted_adapter_class

__all__ = ["run", "FakeClock", "Meter", "Spec", "make_engine", "make_target", "until", "ok", "failed", "NullClient", "always"]

Script = Callable[[str, object], Awaitable[SourceResult]]


def run(coro, timeout: float = 60.0):
    """``asyncio.run`` with a watchdog: a regression that deadlocks (a leaked permit, a lost wake-up) fails fast with
    ``TimeoutError`` instead of hanging the whole suite."""

    async def bounded():
        return await asyncio.wait_for(coro, timeout)

    return asyncio.run(bounded())


class FakeClock:
    """A manual monotonic clock: ``clock()`` returns ``now``; ``advance`` moves it."""

    def __init__(self, start: float = 1000.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        assert seconds >= 0
        self.now += seconds


class NullClient:
    """A SourceHttpClient whose ``get`` must never be reached (the scripted adapters do not use it)."""

    async def get(self, url, *, headers=None, timeout=None):  # pragma: no cover - reaching it is a test bug
        raise AssertionError("scripted adapters never use the client")


class Meter:
    """Counts live / peak / total fetches per label (host) and per source, from inside the adapters."""

    def __init__(self) -> None:
        self.live: Counter[str] = Counter()
        self.peak: Counter[str] = Counter()
        self.requests: Counter[str] = Counter()  # per source_id: fetch calls actually made
        self.by_host: Counter[str] = Counter()  # per host label: fetch calls actually made
        self.total_live = 0
        self.total_peak = 0

    def enter(self, source_id: str, host: str) -> None:
        self.requests[source_id] += 1
        self.by_host[host] += 1
        self.live[host] += 1
        self.peak[host] = max(self.peak[host], self.live[host])
        self.total_live += 1
        self.total_peak = max(self.total_peak, self.total_live)

    def leave(self, host: str) -> None:
        self.live[host] -= 1
        self.total_live -= 1

    def wrap(self, source_id: str, host: str, inner: Script) -> Script:
        """A script that records the fetch (entry .. exit, also on cancellation) around ``inner``."""

        async def script(number: str, client: object) -> SourceResult:
            self.enter(source_id, host)
            try:
                return await inner(number, client)
            finally:
                self.leave(host)

        return script


def always(source_id: str, status: SourceStatus | None = None, **fields) -> Script:
    """A script that always returns SUCCESS (``status=None``) or the given failure status."""

    async def script(number: str, client: object) -> SourceResult:
        await asyncio.sleep(0)
        if status is None:
            return ok(source_id, number, **fields)
        return failed(source_id, status)

    return script


@dataclass(frozen=True)
class Spec:
    """One scripted source: id, base URL (defines its host), script, optional retry policy / deadline."""

    source_id: str
    base_url: str
    script: Script
    retry_policy: RetryPolicy | None = None
    deadline_seconds: float = 20.0


def make_engine(
    specs: list[Spec],
    governor: SourceResourceGovernor | None = None,
    *,
    max_concurrency: int = 8,
    retry_policy: RetryPolicy | None = None,
) -> MultiSourceEngine:
    """A real ``MultiSourceEngine`` over scripted adapters (default: no retry, so attempt counts are exact)."""
    registry = SourceRegistry()
    sources = []
    for spec in specs:
        registry.register(spec.source_id, scripted_adapter_class(spec.source_id, spec.script))
        sources.append(
            SourceConfig(
                spec.source_id,
                base_url=spec.base_url,
                deadline_seconds=spec.deadline_seconds,
                retry_policy=spec.retry_policy,
            )
        )
    config = AggregationConfig.create(
        sources,
        max_concurrency=max_concurrency,
        retry_policy=retry_policy if retry_policy is not None else RetryPolicy.no_retry(),
    )
    return MultiSourceEngine(config, registry, NullClient(), governor=governor)


def make_target(
    source_id: str,
    base_url: str,
    script: Script,
    *,
    retry_policy: RetryPolicy | None = None,
    deadline_seconds: float = 20.0,
) -> SourceTarget:
    """A ``SourceTarget`` (real adapter class, real host key) for driving ``execute_sources_traced`` directly."""
    adapter = scripted_adapter_class(source_id, script)(base_url=base_url)
    return SourceTarget(
        SourceConfig(source_id, base_url=base_url, deadline_seconds=deadline_seconds),
        adapter,
        retry_policy if retry_policy is not None else RetryPolicy.no_retry(),
        host_key_for_base_url(base_url),
    )
