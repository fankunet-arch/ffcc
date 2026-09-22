"""C5 offline stage gate: 200 items, 2 BatchSchedulers, 3 sources, 2 hosts, one shared governor (contract §13).

NOT a live scrape and NOT the final 500-item acceptance: scripted adapters, no network, breaker time is a fake clock.
The run is phased so every breaker transition is deterministic; inside a phase the two schedulers race freely.

    hosts     h1.example  limit 2   <- source_a, source_b   (two sources, ONE host budget)
              h2.example  limit 3   <- source_c
    breaker   per source_id, threshold 3, cooldown 30 s (fake clock), 1 half-open probe

    A  50 items  healthy mix: SUCCESS / NOT_FOUND / retry-recovery (TIMEOUT then SUCCESS)   -> every breaker stays CLOSED, 0 failures
    B  50 items  source_c outage (BLOCKED, RATE_LIMITED, PARSE_ERROR, ...)                  -> c OPENs after 3; a and b keep going
    C  20 items  c still OPEN, cooldown not over                                            -> ZERO requests to c
    D  40 items  cooldown over, c healthy again                                             -> exactly ONE probe; the rest short-circuit; CLOSED
    E  20 items  source_a: one slow SUCCESS already in flight while 3 fast failures trip it -> stale success cannot close it; in-flight call not cancelled
    F  20 items  a run cancelled mid-flight                                                 -> nothing leaks
                                                                                            = 200 items
"""

from __future__ import annotations

import asyncio
from collections import Counter

import pytest

from fc2_metadata_core.aggregation.retry import RetryPolicy
from fc2_metadata_core.batch import BatchConfig, BatchItemStatus, BatchScheduler
from fc2_metadata_core.models.source_result import SourceErrorKind, SourceStatus
from fc2_metadata_core.resource_control import BreakerState, CircuitBreakerPolicy, HostLimitPolicy, SourceResourceGovernor

from support.batch_fakes import numbers
from support.resource_fakes import failed, FakeClock, make_engine, Meter, ok, run, Spec, until

K = SourceErrorKind
S = SourceStatus
H1, H2 = "h1.example", "h2.example"


class World:
    """Everything the scripted sources consult; mutated between phases."""

    def __init__(self) -> None:
        self.meter = Meter()
        self.clock = FakeClock()
        self.mode = {"a": "mixed", "b": "mixed", "c": "ok"}
        self.attempts: Counter[tuple[str, str]] = Counter()
        self.c_calls = 0
        self.slow_number = ""
        self.slow_gate = asyncio.Event()
        self.probe_gate = asyncio.Event()
        self.governor = SourceResourceGovernor(
            host_limits=HostLimitPolicy.create(4, {f"{H1}:443": 2, f"{H2}:443": 3}),
            breaker=CircuitBreakerPolicy(failure_threshold=3, open_duration_seconds=30.0, half_open_max_calls=1),
            clock=self.clock,
        )

    # -- the three scripted sources -------------------------------------------------------------------------------------

    async def a(self, number, client):
        self.attempts[("a", number)] += 1
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        mode, idx = self.mode["a"], int(number[4:])
        if mode == "trip":
            if number == self.slow_number:
                await self.slow_gate.wait()
                return ok("source_a", number)
            return failed("source_a", S.BLOCKED)
        if mode == "healthy":
            return ok("source_a", number)
        kind = idx % 4  # mixed
        if kind == 1:
            return failed("source_a", S.NOT_FOUND)
        if kind == 2 and self.attempts[("a", number)] == 1:
            return failed("source_a", S.NETWORK_ERROR, error_kind=K.TIMEOUT)  # recovered by the retry
        return ok("source_a", number)

    async def b(self, number, client):
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        return failed("source_b", S.NOT_FOUND) if int(number[4:]) % 2 == 0 else ok("source_b", number)

    async def c(self, number, client):
        self.c_calls += 1
        await asyncio.sleep(0)
        mode = self.mode["c"]
        if mode == "outage":
            cycle = (S.BLOCKED, S.RATE_LIMITED, S.PARSE_ERROR, S.NETWORK_ERROR)
            return failed("source_c", cycle[self.c_calls % 4])
        if mode == "probe":
            await self.probe_gate.wait()  # the single probe stays in flight until the test lets it finish
        return ok("source_c", number)

    def engine(self):
        meter = self.meter
        specs = [
            Spec("source_a", f"https://{H1}/a", meter.wrap("source_a", H1, self.a), retry_policy=RetryPolicy(max_attempts=2, initial_backoff_seconds=0.0)),
            Spec("source_b", f"https://{H1}/b", meter.wrap("source_b", H1, self.b)),
            Spec("source_c", f"https://{H2}", meter.wrap("source_c", H2, self.c)),
        ]
        return Recorder(make_engine(specs, self.governor, max_concurrency=3))

    def breaker(self, source_id):
        return next(b for b in self.governor.snapshot().breakers if b.source_id == source_id)


class Recorder:
    """Wraps an engine: item concurrency (the scheduler's M) and every finished result, as it finishes."""

    def __init__(self, engine):
        self.engine, self.live, self.peak, self.done = engine, 0, 0, []

    async def aggregate(self, number):
        self.live += 1
        self.peak = max(self.peak, self.live)
        try:
            result = await self.engine.aggregate(number)
            self.done.append(result)
            return result
        finally:
            self.live -= 1


def c_kinds(*batch_results):
    """source_c's final error_kind for every item of the given BatchResults (None = SUCCESS)."""
    return Counter(
        next(r.error_kind for r in item.aggregation_result.source_results if r.source_id == "source_c")
        for result in batch_results
        for item in result.items
    )


def split(count, start):
    batch = numbers(count, start=start)
    return batch[: count // 2], batch[count // 2 :]


async def run_two(world, engines, batch1, batch2, m=(6, 5)):
    s1 = BatchScheduler(engines[0], BatchConfig(max_in_flight_items=m[0]))
    s2 = BatchScheduler(engines[1], BatchConfig(max_in_flight_items=m[1]))
    return await asyncio.gather(s1.run(batch1), s2.run(batch2))


def accounted(result, batch):
    assert [i.number for i in result.items] == batch and [i.index for i in result.items] == list(range(len(batch)))
    assert all(i.aggregation_result is not None and i.aggregation_result.number == i.number for i in result.items)
    assert result.success_count + result.partial_count + result.failed_count == len(batch)
    return len(batch)


def test_the_200_item_resource_control_stage_gate():
    async def main():
        world = World()
        gov = world.governor
        e1, e2 = world.engine(), world.engine()
        total = 0
        all_numbers: list[str] = []

        # ---- Phase A: 50 healthy items ---------------------------------------------------------------------------------------
        b1, b2 = split(50, 1_000_000)
        r1, r2 = await run_two(world, (e1, e2), b1, b2)
        total += accounted(r1, b1) + accounted(r2, b2)
        all_numbers += b1 + b2
        assert r1.failed_count == r2.failed_count == 0  # NOT_FOUND on some sources never fails an item
        for source_id in ("source_a", "source_b", "source_c"):
            shot = world.breaker(source_id)
            assert (shot.state, shot.consecutive_failures, shot.times_opened, shot.epoch) == (BreakerState.CLOSED, 0, 0, 0), source_id
        retried = [n for (s, n), c in world.attempts.items() if s == "a" and c == 2]
        assert retried, "retry recovery must have happened (TIMEOUT then SUCCESS) and left the breaker healthy"
        assert world.meter.peak[H1] == 2 and world.meter.peak[H2] == 3, "each host reached, and never exceeded, its own limit"
        assert world.meter.total_peak == 5, "2 + 3 at once: the hosts do not block each other"

        # ---- Phase B: source_c outage --------------------------------------------------------------------------------------------
        world.mode["c"] = "outage"
        c_before = world.meter.requests["source_c"]
        b1, b2 = split(50, 2_000_000)
        r1, r2 = await run_two(world, (e1, e2), b1, b2)
        total += accounted(r1, b1) + accounted(r2, b2)
        all_numbers += b1 + b2
        assert world.breaker("source_c").state is BreakerState.OPEN and world.breaker("source_c").times_opened == 1
        c_phase_b = world.meter.requests["source_c"] - c_before
        assert 3 <= c_phase_b <= 3 + 3, f"only the requests already in flight when it tripped (limit 3) may exceed the threshold: {c_phase_b}"
        kinds = c_kinds(r1, r2)
        assert kinds[K.CIRCUIT_OPEN] == 50 - c_phase_b, "every item either made a real request or was turned away, nothing else"
        assert sum(kinds.values()) == 50 and kinds[K.CIRCUIT_OPEN] > 0
        assert world.breaker("source_a").state is BreakerState.CLOSED and world.breaker("source_b").state is BreakerState.CLOSED
        assert r1.partial_count + r2.partial_count > 0  # a / b data survives the outage of c
        assert world.meter.peak[H1] <= 2 and world.meter.peak[H2] <= 3

        # ---- Phase C: still OPEN -> zero requests to c ----------------------------------------------------------------------------
        c_before = world.meter.requests["source_c"]
        epoch_before = world.breaker("source_c").epoch
        b1, b2 = split(20, 3_000_000)
        r1, r2 = await run_two(world, (e1, e2), b1, b2)
        total += accounted(r1, b1) + accounted(r2, b2)
        all_numbers += b1 + b2
        assert world.meter.requests["source_c"] == c_before, "an OPEN breaker sends ZERO network requests"
        assert world.breaker("source_c").epoch == epoch_before and world.breaker("source_c").state is BreakerState.OPEN
        for result in (r1, r2):
            for item in result.items:
                (c_result,) = [r for r in item.aggregation_result.source_results if r.source_id == "source_c"]
                assert c_result.error_kind is K.CIRCUIT_OPEN
                assert [t for t in item.aggregation_result.source_execution_traces if t.source_id == "source_c"][0].attempt_count == 0

        # ---- Phase D: cooldown over, c healthy: exactly ONE probe ------------------------------------------------------------------
        world.mode["c"] = "probe"
        world.clock.advance(30.0)
        c_before = world.meter.requests["source_c"]
        b1, b2 = split(40, 4_000_000)
        s1 = BatchScheduler(e1, BatchConfig(max_in_flight_items=6))
        s2 = BatchScheduler(e2, BatchConfig(max_in_flight_items=5))
        run = asyncio.gather(s1.run(b1), s2.run(b2))
        await until(lambda: world.meter.requests["source_c"] - c_before == 1 and world.breaker("source_c").state is BreakerState.HALF_OPEN)
        for _ in range(200):
            await asyncio.sleep(0)  # let every other in-flight item reach source_c and be turned away
        shot = world.breaker("source_c")
        assert world.meter.requests["source_c"] - c_before == 1, "half_open_max_calls=1: ONE probe, no thundering herd"
        assert (shot.state, shot.half_open_probes_in_flight) == (BreakerState.HALF_OPEN, 1)
        world.mode["c"] = "ok"
        world.probe_gate.set()
        r1, r2 = await run
        total += accounted(r1, b1) + accounted(r2, b2)
        all_numbers += b1 + b2
        shot = world.breaker("source_c")
        assert (shot.state, shot.consecutive_failures, shot.half_open_probes_in_flight, shot.times_opened) == (BreakerState.CLOSED, 0, 0, 1)
        assert shot.epoch == 3  # CLOSED(0) -> OPEN(1) -> HALF_OPEN(2) -> CLOSED(3)
        d_kinds = c_kinds(r1, r2)
        assert d_kinds[K.CIRCUIT_OPEN] >= 1 and d_kinds[None] >= 1  # some turned away; the probe and the recovery succeeded
        assert d_kinds[K.CIRCUIT_OPEN] + d_kinds[None] == 40

        # ---- Phase E: stale success cannot close a just-opened breaker ---------------------------------------------------------------
        b_e = numbers(20, start=5_000_000)
        world.mode["a"], world.slow_number = "trip", b_e[0]
        a_before = world.meter.requests["source_a"]
        s1 = BatchScheduler(e1, BatchConfig(max_in_flight_items=6))
        run = asyncio.create_task(s1.run(b_e))
        await until(lambda: world.breaker("source_a").state is BreakerState.OPEN)
        # everything except the slow item finishes; the slow one is STILL in flight (opening did not cancel it)
        await until(lambda: e1.live == 1, spins=50_000)
        opened = world.breaker("source_a")
        assert opened.state is BreakerState.OPEN and opened.in_flight == 1
        a_requests = world.meter.requests["source_a"] - a_before
        assert a_requests <= 1 + 3 + 2, f"slow + threshold + at most the in-flight ones: {a_requests}"
        world.slow_gate.set()  # the old admission now completes with SUCCESS ...
        r_e = await run
        total += accounted(r_e, b_e)
        all_numbers += b_e
        after = world.breaker("source_a")
        assert (after.state, after.epoch, after.times_opened, after.in_flight) == (BreakerState.OPEN, opened.epoch, 1, 0), (
            "... and, being stale, it must not have closed the breaker"
        )
        assert r_e.items[0].aggregation_result.source_results[0].status is S.SUCCESS  # the in-flight call finished normally
        world.mode["a"] = "healthy"
        world.clock.advance(30.0)
        (recover,) = await s1.run(numbers(1, start=5_100_000)),
        assert world.breaker("source_a").state is BreakerState.CLOSED  # the probe closed it

        # ---- Phase F: a run cancelled mid-flight ----------------------------------------------------------------------------------------
        gate = asyncio.Event()

        async def hang_c(number, client):
            await gate.wait()
            return ok("source_c", number)

        world.c = hang_c  # type: ignore[method-assign]  (engines built below see the hanging source)
        e3 = world.engine()
        f_batch = numbers(20, start=6_000_000)
        run = asyncio.create_task(BatchScheduler(e3, BatchConfig(max_in_flight_items=8)).run(f_batch))
        await until(lambda: world.governor.snapshot().hosts and any(h.in_flight > 0 for h in world.governor.snapshot().hosts))
        run.cancel()
        with pytest.raises(asyncio.CancelledError):
            await run
        started_f = e3.live
        assert started_f == 0 and len(e3.done) == 0

        # ---- global accounting -----------------------------------------------------------------------------------------------------------
        assert len(all_numbers) == total == 180 and len(set(all_numbers)) == 180
        assert total + len(f_batch) == 200, "200 items submitted: 180 accounted results + 20 cancelled (no partial result)"
        shot = gov.snapshot()
        assert all(h.in_flight == 0 and h.waiting == 0 for h in shot.hosts)
        assert all(b.in_flight == 0 and b.half_open_probes_in_flight == 0 for b in shot.breakers)
        assert [h.host.host for h in shot.hosts] == [H1, H2] and [b.source_id for b in shot.breakers] == ["source_a", "source_b", "source_c"]
        assert {h.host.host: h.peak_in_flight for h in shot.hosts} == {H1: 2, H2: 3}
        assert world.meter.total_live == 0
        assert max(e1.peak, e3.peak) <= 8 and e1.peak <= 6 and e2.peak <= 5
        return len(asyncio.all_tasks())

    assert run(main()) == 1, "no orphan task is left behind"
