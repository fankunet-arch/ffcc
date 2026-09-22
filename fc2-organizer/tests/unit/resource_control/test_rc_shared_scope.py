"""Resource-domain scope (contract §2): one governor = one shared budget, across engines and BatchSchedulers.

Peaks are measured from *inside the fake adapters* (``Meter``): independent of the governor's own counters.
"""

from __future__ import annotations

import asyncio

import pytest

from fc2_metadata_core.aggregation import AggregateStatus, AggregationConfig, AggregationConfigError, MultiSourceEngine, SourceConfig
from fc2_metadata_core.batch import BatchConfig, BatchItemStatus, BatchScheduler
from fc2_metadata_core.models.source_result import SourceErrorKind, SourceStatus
from fc2_metadata_core.resource_control import (
    BreakerState,
    CircuitBreakerPolicy,
    HostKey,
    HostLimitPolicy,
    SourceResourceGovernor,
)
from fc2_metadata_core.sources import SourceRegistry

from support.batch_fakes import numbers
from support.resource_fakes import failed, FakeClock, make_engine, Meter, NullClient, ok, run, Spec
from support.scripted_adapters import scripted_adapter_class


def hold(meter: Meter, source_id: str, host: str, *, yields: int = 3, status: SourceStatus | None = None):
    """A fetch that stays live for ``yields`` loop iterations (so concurrent fetches genuinely overlap)."""

    async def inner(number, client):
        for _ in range(yields):
            await asyncio.sleep(0)
        return ok(source_id, number) if status is None else failed(source_id, status)

    return meter.wrap(source_id, host, inner)


class Counting:
    """Wraps an engine to observe the scheduler's own item concurrency (its ``M``)."""

    def __init__(self, engine):
        self.engine, self.live, self.peak, self.calls = engine, 0, 0, 0

    async def aggregate(self, number):
        self.calls += 1
        self.live += 1
        self.peak = max(self.peak, self.live)
        try:
            return await self.engine.aggregate(number)
        finally:
            self.live -= 1


def governor(limit=3, *, overrides=None, threshold=1000 // 10, clock=None, **breaker):
    return SourceResourceGovernor(
        host_limits=HostLimitPolicy.create(limit, overrides),
        breaker=CircuitBreakerPolicy(failure_threshold=threshold, **breaker),
        clock=clock or FakeClock(),
    )


# ---- one governor across two engines and two schedulers --------------------------------------------------------------


def test_two_schedulers_two_engines_one_governor_share_one_host_budget():
    meter = Meter()
    shared = governor(3)
    host = "https://same.example"
    engine1 = Counting(make_engine([Spec("src1", host, hold(meter, "src1", "same.example"))], shared))
    engine2 = Counting(make_engine([Spec("src2", host, hold(meter, "src2", "same.example"))], shared))
    batch1, batch2 = numbers(60), numbers(60, start=2_000_001)

    async def main():
        s1 = BatchScheduler(engine1, BatchConfig(max_in_flight_items=8))
        s2 = BatchScheduler(engine2, BatchConfig(max_in_flight_items=8))
        return await asyncio.gather(s1.run(batch1), s2.run(batch2))

    r1, r2 = run(main())
    assert meter.peak["same.example"] == 3, "the two schedulers must share ONE host budget of 3 (not 6, not 16)"
    assert (engine1.peak, engine2.peak) == (8, 8)  # each scheduler still runs its own M=8 items at once
    assert r1.total == r2.total == 60 and r1.success_count == r2.success_count == 60
    assert meter.requests["src1"] == meter.requests["src2"] == 60
    (host_shot,) = shared.snapshot().hosts
    assert (host_shot.limit, host_shot.in_flight, host_shot.waiting, host_shot.peak_in_flight) == (3, 0, 0, 3)


def test_without_a_governor_nothing_limits_the_host_c4_behaviour_is_unchanged():
    meter = Meter()
    engine = make_engine([Spec("src", "https://same.example", hold(meter, "src", "same.example"))], None)
    assert engine.governor is None

    async def main():
        return await BatchScheduler(engine, BatchConfig(max_in_flight_items=8)).run(numbers(40))

    assert run(main()).success_count == 40
    assert meter.peak["same.example"] == 8  # only M limits it


def test_two_different_governors_are_independent_domains_their_budgets_add_up():
    meter = Meter()
    g1, g2 = governor(3), governor(3)
    host = "https://same.example"
    engine1 = make_engine([Spec("src1", host, hold(meter, "src1", "same.example"))], g1)
    engine2 = make_engine([Spec("src2", host, hold(meter, "src2", "same.example"))], g2)

    async def main():
        s1 = BatchScheduler(engine1, BatchConfig(max_in_flight_items=8))
        s2 = BatchScheduler(engine2, BatchConfig(max_in_flight_items=8))
        return await asyncio.gather(s1.run(numbers(60)), s2.run(numbers(60, start=2_000_001)))

    run(main())
    assert meter.peak["same.example"] == 6, "scope is the governor domain, not a process singleton"
    assert g1.snapshot().hosts[0].peak_in_flight == 3 and g2.snapshot().hosts[0].peak_in_flight == 3


def test_engines_built_on_one_governor_at_different_times_still_share_it():
    meter = Meter()
    shared = governor(2)
    first = make_engine([Spec("src", "https://same.example", hold(meter, "src", "same.example"))], shared)

    async def main():
        run_first = asyncio.create_task(BatchScheduler(first, BatchConfig(max_in_flight_items=6)).run(numbers(30)))
        await asyncio.sleep(0)
        late = make_engine([Spec("other", "https://same.example", hold(meter, "other", "same.example"))], shared)
        run_late = asyncio.create_task(BatchScheduler(late, BatchConfig(max_in_flight_items=6)).run(numbers(30, start=9_000_001)))
        await asyncio.gather(run_first, run_late)

    run(main())
    assert meter.peak["same.example"] == 2


# ---- one host, several sources ----------------------------------------------------------------------------------------


def test_two_sources_on_one_host_share_one_budget_of_two_not_two_each():
    meter = Meter()
    shared = governor(2)
    specs = [
        Spec("source_a", "https://same.example/a", hold(meter, "source_a", "same.example")),
        Spec("source_b", "https://same.example/b", hold(meter, "source_b", "same.example")),
    ]
    engine = make_engine(specs, shared)

    async def main():
        return await BatchScheduler(engine, BatchConfig(max_in_flight_items=6)).run(numbers(30))

    result = run(main())
    assert result.success_count == 30
    assert meter.peak["same.example"] == 2, "different paths/sources on one host must share the host budget"
    assert len(shared.snapshot().hosts) == 1
    assert meter.requests["source_a"] == meter.requests["source_b"] == 30


def test_breakers_of_two_sources_on_one_host_are_independent():
    meter = Meter()
    shared = governor(2, threshold=3)
    specs = [
        Spec("source_a", "https://same.example/a", hold(meter, "source_a", "same.example", status=SourceStatus.PARSE_ERROR)),
        Spec("source_b", "https://same.example/b", hold(meter, "source_b", "same.example")),
    ]
    engine = make_engine(specs, shared)

    async def main():
        return await BatchScheduler(engine, BatchConfig(max_in_flight_items=6)).run(numbers(40))

    result = run(main())
    states = {b.source_id: b for b in shared.snapshot().breakers}
    assert states["source_a"].state is BreakerState.OPEN and states["source_b"].state is BreakerState.CLOSED
    assert states["source_b"].consecutive_failures == 0
    assert meter.requests["source_b"] == 40, "source_b keeps serving every item; a parse failure of source_a never closes it"
    assert 3 <= meter.requests["source_a"] <= 5, "source_a stops being asked once its breaker opened"
    assert result.partial_count == 40 and result.failed_count == 0  # source_b's data survives every item
    assert meter.peak["same.example"] <= 2


# ---- different hosts ----------------------------------------------------------------------------------------------------


def test_different_hosts_do_not_block_each_other_and_each_keeps_its_own_limit():
    meter = Meter()
    shared = governor(1, overrides={"a.example:443": 2, "b.example:443": 3})
    specs = [
        Spec("source_a", "https://a.example", hold(meter, "source_a", "a.example", yields=4)),
        Spec("source_b", "https://b.example", hold(meter, "source_b", "b.example", yields=4)),
    ]
    engine = make_engine(specs, shared)

    async def main():
        return await BatchScheduler(engine, BatchConfig(max_in_flight_items=10)).run(numbers(40))

    assert run(main()).success_count == 40
    assert meter.peak["a.example"] == 2 and meter.peak["b.example"] == 3
    assert meter.total_peak == 5, "2 + 3 requests may be in flight at once: hosts never block each other"
    assert {s.host.host: s.limit for s in shared.snapshot().hosts} == {"a.example": 2, "b.example": 3}


def test_a_saturated_host_never_delays_another_host():
    meter = Meter()
    shared = governor(1)
    slow_gate = asyncio.Event()

    async def slow(number, client):
        await slow_gate.wait()
        return ok("slow", number)

    async def fast(number, client):
        return ok("fast", number)

    async def main():
        slow_engine = make_engine([Spec("slow", "https://slow.example", meter.wrap("slow", "slow.example", slow))], shared)
        fast_engine = make_engine([Spec("fast", "https://fast.example", meter.wrap("fast", "fast.example", fast))], shared)
        blocked = [asyncio.create_task(slow_engine.aggregate(n)) for n in numbers(5)]
        await asyncio.sleep(0)
        for _ in range(3):
            await asyncio.sleep(0)
        results = [await asyncio.wait_for(fast_engine.aggregate(n), 5) for n in numbers(5, start=7_000_001)]
        assert all(r.status is AggregateStatus.SUCCESS for r in results)
        assert meter.by_host["slow.example"] == 1  # one live, four queued behind it
        slow_gate.set()
        await asyncio.gather(*blocked)

    run(main())
    assert meter.peak["slow.example"] == 1


# ---- breaker state is shared per source_id across the engines of one governor -------------------------------------------------


def test_two_engines_of_one_governor_share_a_sources_breaker_state():
    meter = Meter()
    shared = governor(4, threshold=2)
    first = make_engine([Spec("src", "https://x.example", hold(meter, "src", "x.example", status=SourceStatus.BLOCKED))], shared)
    second = make_engine([Spec("src", "https://x.example", hold(meter, "src", "x.example"))], shared)  # would succeed

    async def main():
        for n in numbers(2):
            assert (await first.aggregate(n)).status is AggregateStatus.FAILED
        before = meter.requests["src"]
        blocked = await second.aggregate("FC2-5555555")  # a different engine, the same governor and source_id
        return before, blocked

    before, blocked = run(main())
    assert before == 2 and meter.requests["src"] == 2, "the second engine's lookup was short-circuited: no request"
    assert blocked.status is AggregateStatus.FAILED
    assert blocked.source_results[0].error_kind is SourceErrorKind.CIRCUIT_OPEN


def test_a_different_governor_does_not_see_that_breaker():
    meter = Meter()
    tripped, fresh = governor(4, threshold=1), governor(4, threshold=1)
    a = make_engine([Spec("src", "https://x.example", hold(meter, "src", "x.example", status=SourceStatus.BLOCKED))], tripped)
    b = make_engine([Spec("src", "https://x.example", hold(meter, "src", "x.example"))], fresh)

    async def main():
        await a.aggregate("FC2-1000001")
        return await b.aggregate("FC2-1000002")

    assert run(main()).status is AggregateStatus.SUCCESS


# ---- engine construction ---------------------------------------------------------------------------------------------------------


def test_engine_derives_the_host_from_the_configured_base_url_or_the_adapters_default():
    registry = SourceRegistry()
    registry.register("cfg", scripted_adapter_class("cfg", lambda n, c: None))  # default https://cfg.invalid
    registry.register("dflt", scripted_adapter_class("dflt", lambda n, c: None))
    config = AggregationConfig.create([SourceConfig("cfg", base_url="http://Configured.EXAMPLE:8080/p"), SourceConfig("dflt")])
    shared = governor(2)
    engine = MultiSourceEngine(config, registry, NullClient(), governor=shared)
    assert engine.governor is shared
    assert [t.host for t in engine._targets] == [HostKey("configured.example", 8080), HostKey("dflt.invalid", 443)]


def test_engine_rejects_a_governor_of_the_wrong_type_and_a_default_base_url_it_cannot_key():
    registry = SourceRegistry()
    registry.register("s", scripted_adapter_class("s", lambda n, c: None))
    config = AggregationConfig.create([SourceConfig("s")])
    for junk in (object(), "governor", 5, {}):
        with pytest.raises(AggregationConfigError):
            MultiSourceEngine(config, registry, NullClient(), governor=junk)  # type: ignore[arg-type]

    class BadDefault(scripted_adapter_class("bad", lambda n, c: None)):  # type: ignore[misc]
        default_base_url = "not a url"

    bad_registry = SourceRegistry()
    bad_registry.register("bad", BadDefault)
    bad_config = AggregationConfig.create([SourceConfig("bad")])
    MultiSourceEngine(bad_config, bad_registry, NullClient())  # without a governor nothing is derived: unchanged behaviour
    with pytest.raises(AggregationConfigError, match="host identity"):
        MultiSourceEngine(bad_config, bad_registry, NullClient(), governor=governor(2))


def test_the_host_key_is_taken_from_configuration_never_from_the_response():
    """A redirect/response naming another host must not change which host budget a request counts against."""
    meter = Meter()
    shared = governor(1)

    async def script(number, client):
        result = ok("src", number, source_urls=("https://elsewhere.example/page",))
        return result

    engine = make_engine([Spec("src", "https://configured.example", meter.wrap("src", "configured.example", script))], shared)
    run(engine.aggregate("FC2-1234567"))
    assert [s.host for s in shared.snapshot().hosts] == [HostKey("configured.example", 443)]
