"""Large-N structural stress (contract §12): N = 10 000, M = 16, host limit 3, one shared governor.

Structural, not a benchmark: no wall-clock assertion. It proves that the host budget holds at scale, that the
scheduler budget still holds, that every item is accounted for, and that the governor keeps O(hosts + sources) state
-- no ticket, permit or per-item resource object survives a finished item.
"""

from __future__ import annotations

import asyncio
import gc

from fc2_metadata_core.batch import BatchConfig, BatchItemStatus, BatchScheduler
from fc2_metadata_core.models.source_result import SourceStatus
from fc2_metadata_core.resource_control import (
    BreakerState,
    CircuitBreakerPolicy,
    HostLimiter,
    HostLimitPolicy,
    HostPermit,
    SourceAdmission,
    SourceResourceGovernor,
)
from fc2_metadata_core.resource_control.circuit_breaker import CircuitBreaker

from support.batch_fakes import numbers
from support.resource_fakes import failed, FakeClock, make_engine, Meter, ok, run, Spec

N, M, LIMIT = 10_000, 16, 3
RESOURCE_TYPES = (SourceAdmission, HostPermit, HostLimiter, CircuitBreaker)


def live_resource_objects() -> dict[str, int]:
    gc.collect()
    counts = {t.__name__: 0 for t in RESOURCE_TYPES}
    for obj in gc.get_objects():
        for t in RESOURCE_TYPES:
            if type(obj) is t:
                counts[t.__name__] += 1
    return counts


def only_one_domain_left(baseline: dict[str, int]) -> bool:
    """After a run: no ticket or permit survived, and exactly this run's one limiter and one breaker exist
    (relative to ``baseline`` so unrelated tests in the same process cannot matter)."""
    now = live_resource_objects()
    return now == {
        "SourceAdmission": baseline["SourceAdmission"],
        "HostPermit": baseline["HostPermit"],
        "HostLimiter": baseline["HostLimiter"] + 1,
        "CircuitBreaker": baseline["CircuitBreaker"] + 1,
    }


class Recorder:
    def __init__(self, engine, clock=None):
        self.engine, self.live, self.peak, self.clock = engine, 0, 0, clock

    async def aggregate(self, number):
        self.live += 1
        self.peak = max(self.peak, self.live)
        if self.clock is not None:
            self.clock.advance(1.0)  # one simulated second per item, whether or not a request is made
        try:
            return await self.engine.aggregate(number)
        finally:
            self.live -= 1


def test_10000_items_shared_governor_host_limit_3_scheduler_16():
    baseline = live_resource_objects()
    meter = Meter()
    governor = SourceResourceGovernor(
        host_limits=HostLimitPolicy(LIMIT),
        breaker=CircuitBreakerPolicy(failure_threshold=3),
        clock=FakeClock(),
    )
    samples = {"tasks": 0, "waiting": 0, "in_flight": 0, "calls": 0}

    async def inner(number, client):
        samples["calls"] += 1
        if samples["calls"] % 25 == 0:  # sample the structure of the run as it goes
            host = governor.snapshot().hosts[0]
            samples["tasks"] = max(samples["tasks"], len(asyncio.all_tasks()))
            samples["waiting"] = max(samples["waiting"], host.waiting)
            samples["in_flight"] = max(samples["in_flight"], host.in_flight)
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        return ok("src", number)

    engine = Recorder(make_engine([Spec("src", "https://same.example", meter.wrap("src", "same.example", inner))], governor))
    batch = numbers(N)

    async def main():
        return await BatchScheduler(engine, BatchConfig(max_in_flight_items=M)).run(batch)

    result = run(main())

    # complete, ordered, exactly once
    assert result.total == N and result.success_count == N
    assert [i.number for i in result.items] == batch and [i.index for i in result.items] == list(range(N))
    assert all(i.status is BatchItemStatus.SUCCESS for i in result.items)
    assert meter.requests["src"] == N

    # both budgets held, and were both actually reached
    assert meter.peak["same.example"] == LIMIT, f"observed host peak {meter.peak['same.example']}"
    assert engine.peak == M
    assert samples["in_flight"] <= LIMIT and samples["waiting"] <= M
    assert samples["tasks"] <= 2 * M + 4, f"live tasks stayed O(M), saw {samples['tasks']}"

    # O(hosts + sources) state; nothing per item survives
    shot = governor.snapshot()
    assert len(shot.hosts) == 1 and len(shot.breakers) == 1
    (host,) = shot.hosts
    assert (host.limit, host.in_flight, host.waiting, host.peak_in_flight) == (LIMIT, 0, 0, LIMIT)
    (breaker,) = shot.breakers
    assert (breaker.state, breaker.consecutive_failures, breaker.in_flight, breaker.epoch) == (BreakerState.CLOSED, 0, 0, 0)
    assert only_one_domain_left(baseline)


def test_two_schedulers_5000_items_each_share_one_host_budget_of_3():
    baseline = live_resource_objects()
    meter = Meter()
    governor = SourceResourceGovernor(host_limits=HostLimitPolicy(LIMIT), clock=FakeClock())

    async def inner(number, client):
        await asyncio.sleep(0)
        return ok("src", number)

    def build():
        return Recorder(make_engine([Spec("src", "https://same.example", meter.wrap("src", "same.example", inner))], governor))

    e1, e2 = build(), build()
    b1, b2 = numbers(N // 2), numbers(N // 2, start=5_000_000)

    async def main():
        s1, s2 = BatchScheduler(e1, BatchConfig(max_in_flight_items=M)), BatchScheduler(e2, BatchConfig(max_in_flight_items=M))
        return await asyncio.gather(s1.run(b1), s2.run(b2))

    r1, r2 = run(main())
    assert r1.total + r2.total == N and r1.success_count + r2.success_count == N
    assert [i.number for i in r1.items] == b1 and [i.number for i in r2.items] == b2
    assert meter.peak["same.example"] == LIMIT, "32 items in flight across two schedulers, still 3 requests at once"
    assert (e1.peak, e2.peak) == (M, M)
    assert only_one_domain_left(baseline)


def test_a_long_flapping_run_keeps_only_counters_no_failure_history():
    """10 000 items, one source that fails in bursts; the breaker opens and recovers over and over (fake clock advanced
    per item). State stays a fixed handful of scalars: nothing accumulates per failure or per item."""
    baseline = live_resource_objects()
    clock = FakeClock()
    governor = SourceResourceGovernor(
        host_limits=HostLimitPolicy(2), breaker=CircuitBreakerPolicy(failure_threshold=3, open_duration_seconds=5.0), clock=clock
    )
    meter = Meter()
    calls = {"n": 0}

    async def flaky(number, client):
        calls["n"] += 1
        await asyncio.sleep(0)
        return failed("src", SourceStatus.BLOCKED) if (calls["n"] // 4) % 2 == 0 else ok("src", number)

    engine = Recorder(
        make_engine([Spec("src", "https://same.example", meter.wrap("src", "same.example", flaky))], governor), clock
    )

    async def main():
        return await BatchScheduler(engine, BatchConfig(max_in_flight_items=8)).run(numbers(N))

    result = run(main())
    assert result.total == N and meter.peak["same.example"] <= 2
    (breaker,) = governor.snapshot().breakers
    assert breaker.times_opened > 5, "the breaker really did cycle"
    assert breaker.in_flight == 0 and breaker.half_open_probes_in_flight == 0
    assert 0 <= breaker.consecutive_failures <= 3
    assert only_one_domain_left(baseline)
    import dataclasses

    assert len(dataclasses.fields(breaker)) == 9  # a fixed set of scalars, whatever N is
