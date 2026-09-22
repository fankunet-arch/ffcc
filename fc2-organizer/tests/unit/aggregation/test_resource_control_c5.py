"""Offline C5 governor and live execution-boundary tests."""

import asyncio
import ast
from pathlib import Path

import pytest

from fc2_metadata_core.aggregation import AggregationConfig, MultiSourceEngine, RetryPolicy, SourceConfig
from fc2_metadata_core.aggregation import AggregateStatus
from fc2_metadata_core.aggregation.retry import RETRY_ELIGIBLE_KINDS
from fc2_metadata_core.batch import BatchConfig, BatchScheduler
from fc2_metadata_core.models.source_result import SourceErrorKind, SourceStatus
from fc2_metadata_core.resource_control import (
    BreakerPolicy, BreakerState, HostPolicy, SourceResourceGovernor, canonical_host_key,
)
from fc2_metadata_core.sources import SourceRegistry
from support.scripted_adapters import failed, ok, scripted_adapter_class

N = "FC2-1234567"


class Client:
    async def get(self, url, *, headers=None, timeout=None):
        raise AssertionError("scripted adapter does not use transport")


def build(source_id, script, governor, *, base_url=None, retry=None):
    registry = SourceRegistry()
    registry.register(source_id, scripted_adapter_class(source_id, script))
    config = AggregationConfig.create(
        [SourceConfig(source_id, base_url=base_url, retry_policy=retry or RetryPolicy.no_retry())]
    )
    return MultiSourceEngine(config, registry, Client(), governor=governor)


def test_host_key_and_immutable_policy():
    assert SourceErrorKind.CIRCUIT_OPEN not in RETRY_ELIGIBLE_KINDS
    assert canonical_host_key("https://EXAMPLE.com/a") == ("example.com", 443)
    assert canonical_host_key("https://example.com:8443/b") == ("example.com", 8443)
    assert canonical_host_key("http://[2001:0db8::1]/x") == ("2001:db8::1", 80)
    for bad in (True, 0, 65):
        with pytest.raises(ValueError):
            HostPolicy(bad)
    with pytest.raises(ValueError):
        BreakerPolicy(open_duration_seconds=float("nan"))
    policy = HostPolicy.create(1, {"https://A.example/a": 2, "https://b.example/b": 3})
    assert policy.limit_for(("a.example", 443)) == 2
    assert policy.limit_for(("b.example", 443)) == 3
    with pytest.raises(ValueError):
        HostPolicy.create(1, {"https://A.example/a": 2, "https://a.example/b": 3})


def test_breaker_threshold_probe_and_stale_completion():
    now = [0.0]
    gov = SourceResourceGovernor(breaker_policy=BreakerPolicy(2, 10, 1), clock=lambda: now[0])
    gov.register("a", "https://a.example")
    stale = gov.admit("a")
    for _ in range(2):
        token = gov.admit("a")
        gov.record_result(token, failed("a", SourceStatus.BLOCKED))
    assert gov.snapshot("a").state is BreakerState.OPEN
    gov.record_result(stale, ok("a", N))
    assert gov.snapshot("a").state is BreakerState.OPEN
    assert gov.admit("a") is None
    now[0] = 10
    probe = gov.admit("a")
    assert gov.snapshot("a").state is BreakerState.HALF_OPEN
    assert gov.admit("a") is None
    gov.record_result(probe, failed("a", SourceStatus.RATE_LIMITED))
    assert gov.snapshot("a").state is BreakerState.OPEN
    now[0] = 20
    probe = gov.admit("a")
    gov.record_result(probe, failed("a", SourceStatus.NOT_FOUND))
    assert gov.snapshot("a").state is BreakerState.CLOSED
    assert gov.snapshot("a").consecutive_failures == 0


def test_100_waiters_cancel_without_capacity_loss():
    async def scenario():
        gov = SourceResourceGovernor(HostPolicy(1))
        gov.register("a", "https://a.example")
        await gov.acquire_host("a")
        waiters = [asyncio.create_task(gov.acquire_host("a")) for _ in range(100)]
        await asyncio.sleep(0)
        for task in waiters[:60]:
            task.cancel()
        await asyncio.gather(*waiters[:60], return_exceptions=True)
        gov.release_host("a")
        for task in waiters[60:]:
            await asyncio.wait_for(task, 1)
            gov.release_host("a")
        await asyncio.wait_for(gov.acquire_host("a"), 1)
        gov.release_host("a")
    asyncio.run(scenario())


def test_shared_governor_two_engines_two_schedulers_and_separate_domains():
    async def scenario(shared):
        active = 0
        peak = 0
        async def script(number, client):
            nonlocal active, peak
            active += 1
            peak = max(peak, active)
            try:
                await asyncio.sleep(0.001)
                return ok("a", number)
            finally:
                active -= 1
        g1 = SourceResourceGovernor(HostPolicy(3))
        g2 = g1 if shared else SourceResourceGovernor(HostPolicy(3))
        e1 = build("a", script, g1, base_url="https://same.example/a")
        e2 = build("a", script, g2, base_url="https://same.example/b")
        b1 = BatchScheduler(e1, BatchConfig(max_in_flight_items=8))
        b2 = BatchScheduler(e2, BatchConfig(max_in_flight_items=8))
        numbers = [f"FC2-{i:07d}" for i in range(1000000, 1000020)]
        await asyncio.gather(b1.run(numbers), b2.run(numbers))
        return peak
    assert asyncio.run(scenario(True)) == 3
    assert asyncio.run(scenario(False)) == 6


def test_open_short_circuit_and_not_found_health():
    async def scenario():
        calls = 0
        async def blocked(number, client):
            nonlocal calls
            calls += 1
            return failed("a", SourceStatus.BLOCKED)
        gov = SourceResourceGovernor(breaker_policy=BreakerPolicy(2, 30, 1))
        engine = build("a", blocked, gov)
        for _ in range(2):
            await engine.aggregate(N)
        result = await engine.aggregate(N)
        assert calls == 2
        assert result.source_results[0].error_kind is SourceErrorKind.CIRCUIT_OPEN
        assert result.source_execution_traces[0].attempt_count == 0
        assert gov.snapshot("a").state is BreakerState.OPEN
    asyncio.run(scenario())


def test_half_open_hundred_calls_only_one_probe():
    async def scenario():
        now = [0.0]
        entered = asyncio.Event()
        release = asyncio.Event()
        calls = 0
        async def script(number, client):
            nonlocal calls
            calls += 1
            if calls == 2:
                entered.set()
                await release.wait()
                return failed("a", SourceStatus.NOT_FOUND)
            return failed("a", SourceStatus.BLOCKED)
        gov = SourceResourceGovernor(breaker_policy=BreakerPolicy(1, 10, 1), clock=lambda: now[0])
        engine = build("a", script, gov)
        await engine.aggregate(N)
        now[0] = 10
        tasks = [asyncio.create_task(engine.aggregate(N)) for _ in range(100)]
        await entered.wait()
        await asyncio.sleep(0)
        release.set()
        results = await asyncio.gather(*tasks)
        assert calls == 2
        assert sum(r.source_results[0].error_kind is SourceErrorKind.CIRCUIT_OPEN for r in results) == 99
        assert gov.snapshot("a").state is BreakerState.CLOSED
    asyncio.run(scenario())


def test_same_host_two_sources_share_limit_but_not_breaker():
    async def scenario():
        active = peak = 0
        async def script_a(number, client):
            nonlocal active, peak
            active += 1
            peak = max(peak, active)
            try:
                await asyncio.sleep(0.001)
                return failed("a", SourceStatus.PARSE_ERROR)
            finally:
                active -= 1
        async def script_b(number, client):
            nonlocal active, peak
            active += 1
            peak = max(peak, active)
            try:
                await asyncio.sleep(0.001)
                return ok("b", number)
            finally:
                active -= 1
        gov = SourceResourceGovernor(HostPolicy(2), BreakerPolicy(1, 30, 1))
        registry = SourceRegistry()
        registry.register("a", scripted_adapter_class("a", script_a))
        registry.register("b", scripted_adapter_class("b", script_b))
        config = AggregationConfig.create([
            SourceConfig("a", base_url="https://same.example/a", retry_policy=RetryPolicy.no_retry()),
            SourceConfig("b", base_url="https://same.example/b", retry_policy=RetryPolicy.no_retry()),
        ])
        engine = MultiSourceEngine(config, registry, Client(), governor=gov)
        await asyncio.gather(*(engine.aggregate(N) for _ in range(20)))
        assert peak == 2
        assert gov.snapshot("a").state is BreakerState.OPEN
        assert gov.snapshot("b").state is BreakerState.CLOSED
    asyncio.run(scenario())


def test_retry_releases_host_permit_during_backoff_and_counts_final_only():
    async def scenario():
        first_done = asyncio.Event()
        backoff_gate = asyncio.Event()
        calls = 0
        async def script(number, client):
            nonlocal calls
            calls += 1
            if calls == 1:
                first_done.set()
                return failed("a", SourceStatus.NETWORK_ERROR)
            return ok("a", number)
        gov = SourceResourceGovernor(HostPolicy(1), BreakerPolicy(1, 30, 1))
        engine = build("a", script, gov, retry=RetryPolicy(max_attempts=2, initial_backoff_seconds=0.05))
        task = asyncio.create_task(engine.aggregate(N))
        await first_done.wait()
        # The first attempt has completed; another same-host permit is available during backoff.
        await asyncio.wait_for(gov.acquire_host("a"), 0.1)
        gov.release_host("a")
        result = await task
        assert result.source_results[0].status is SourceStatus.SUCCESS
        assert gov.snapshot("a").consecutive_failures == 0
        assert calls == 2
    asyncio.run(scenario())


def test_cancelled_probe_and_fetch_release_all_state():
    async def scenario():
        now = [0.0]
        entered = asyncio.Event()
        async def script(number, client):
            entered.set()
            await asyncio.Event().wait()
        gov = SourceResourceGovernor(HostPolicy(1), BreakerPolicy(1, 10, 1), clock=lambda: now[0])
        gov.register("a", "https://a.example")
        t = gov.admit("a")
        gov.record_result(t, failed("a", SourceStatus.BLOCKED))
        now[0] = 10
        engine = build("a", script, gov, base_url="https://a.example")
        task = asyncio.create_task(engine.aggregate(N))
        await entered.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        snap = gov.snapshot("a")
        assert snap.in_flight == snap.probes == 0
        await asyncio.wait_for(gov.acquire_host("a"), 0.1)
        gov.release_host("a")
    asyncio.run(scenario())


def test_host_queue_does_not_spend_source_deadline():
    async def scenario():
        gov = SourceResourceGovernor(HostPolicy(1))
        async def script(number, client):
            return ok("a", number)
        registry = SourceRegistry()
        registry.register("a", scripted_adapter_class("a", script))
        config = AggregationConfig.create([
            SourceConfig("a", base_url="https://a.example", deadline_seconds=0.01,
                         retry_policy=RetryPolicy.no_retry())
        ])
        engine = MultiSourceEngine(config, registry, Client(), governor=gov)
        await gov.acquire_host("a")
        task = asyncio.create_task(engine.aggregate(N))
        await asyncio.sleep(0.03)  # longer than source deadline, entirely in host queue
        gov.release_host("a")
        result = await task
        assert result.source_results[0].status is SourceStatus.SUCCESS
    asyncio.run(scenario())


def test_200_item_offline_resource_gate():
    async def scenario():
        active = {"one.example": 0, "two.example": 0}
        peak = {"one.example": 0, "two.example": 0}
        calls = {"a": 0, "b": 0, "c": 0}
        b_attempts = {}
        async def script(sid, host, number):
            calls[sid] += 1
            active[host] += 1
            peak[host] = max(peak[host], active[host])
            try:
                await asyncio.sleep(0)
                if sid == "a":
                    return failed(sid, SourceStatus.NOT_FOUND) if int(number[-1]) % 4 == 0 else ok(sid, number)
                if sid == "b":
                    b_attempts[number] = b_attempts.get(number, 0) + 1
                    if int(number[-1]) % 5 == 0 and b_attempts[number] == 1:
                        return failed(sid, SourceStatus.NETWORK_ERROR)
                    return ok(sid, number)
                return failed(sid, (SourceStatus.BLOCKED, SourceStatus.RATE_LIMITED,
                                    SourceStatus.PARSE_ERROR)[(calls[sid] - 1) % 3])
            finally:
                active[host] -= 1
        registry = SourceRegistry()
        for sid, host in (("a", "one.example"), ("b", "one.example"), ("c", "two.example")):
            async def script_for(number, client, sid=sid, host=host):
                return await script(sid, host, number)
            registry.register(sid, scripted_adapter_class(sid, script_for))
        config = AggregationConfig.create([
            SourceConfig(sid, base_url=f"https://{host}/{sid}",
                         retry_policy=(RetryPolicy(max_attempts=2, initial_backoff_seconds=0)
                                       if sid == "b" else RetryPolicy.no_retry()))
            for sid, host in (("a", "one.example"), ("b", "one.example"), ("c", "two.example"))
        ])
        gov = SourceResourceGovernor(HostPolicy.create(3, {"https://one.example": 2,
                                                          "https://two.example": 3}),
                                     BreakerPolicy(3, 30, 1))
        e1 = MultiSourceEngine(config, registry, Client(), governor=gov)
        e2 = MultiSourceEngine(config, registry, Client(), governor=gov)
        numbers = [f"FC2-{i:07d}" for i in range(1000000, 1000100)]
        b1 = BatchScheduler(e1, BatchConfig(max_in_flight_items=8))
        b2 = BatchScheduler(e2, BatchConfig(max_in_flight_items=8))
        r1, r2 = await asyncio.gather(b1.run(numbers), b2.run(numbers))
        assert len(r1.items) + len(r2.items) == 200
        assert peak["one.example"] <= 2 and peak["two.example"] <= 3
        assert calls["c"] < 200  # OPEN short-circuits without fetch
        assert any(count == 2 for count in b_attempts.values())
        assert gov.snapshot("c").state is BreakerState.OPEN
        assert gov.state_size == (2, 3)
    asyncio.run(scenario())


def test_10000_items_shared_governor_bounded_state():
    async def scenario():
        active = peak = 0
        items_active = items_peak = 0
        async def script(number, client):
            nonlocal active, peak
            active += 1
            peak = max(peak, active)
            try:
                await asyncio.sleep(0)
                return ok("a", number)
            finally:
                active -= 1
        gov = SourceResourceGovernor(HostPolicy(3))
        e1 = build("a", script, gov, base_url="https://shared.example/a")
        e2 = build("a", script, gov, base_url="https://shared.example/b")
        class MeteredEngine:
            def __init__(self, wrapped):
                self.wrapped = wrapped

            async def aggregate(self, number):
                nonlocal items_active, items_peak
                items_active += 1
                items_peak = max(items_peak, items_active)
                try:
                    return await self.wrapped.aggregate(number)
                finally:
                    items_active -= 1
        nums = [f"FC2-{i:07d}" for i in range(1000000, 1010000)]
        b1 = BatchScheduler(MeteredEngine(e1), BatchConfig(max_in_flight_items=8))
        b2 = BatchScheduler(MeteredEngine(e2), BatchConfig(max_in_flight_items=8))
        a, b = await asyncio.gather(b1.run(nums[:5000]), b2.run(nums[5000:]))
        assert len(a.items) + len(b.items) == 10000
        assert peak == 3
        assert items_peak <= 16
        assert gov.state_size == (1, 1)
        assert gov.snapshot("a").in_flight == 0
    asyncio.run(scenario())


def test_different_hosts_reach_independent_two_plus_three_capacity():
    async def scenario():
        active = {"a": 0, "b": 0}
        peak = {"a": 0, "b": 0}
        ready = asyncio.Event()
        release = asyncio.Event()
        async def script(sid, number):
            active[sid] += 1
            peak[sid] = max(peak[sid], active[sid])
            if sum(active.values()) == 5:
                ready.set()
            try:
                await release.wait()
                return ok(sid, number)
            finally:
                active[sid] -= 1
        gov = SourceResourceGovernor(HostPolicy.create(1, {
            "https://a.example": 2, "https://b.example": 3,
        }))
        async def a(number, client):
            return await script("a", number)
        async def b(number, client):
            return await script("b", number)
        ea = build("a", a, gov, base_url="https://a.example/a")
        eb = build("b", b, gov, base_url="https://b.example/b")
        tasks = [asyncio.create_task(ea.aggregate(N)) for _ in range(3)] + [
            asyncio.create_task(eb.aggregate(N)) for _ in range(4)
        ]
        try:
            await asyncio.wait_for(ready.wait(), 1)
            assert peak == {"a": 2, "b": 3}
        finally:
            release.set()
            await asyncio.gather(*tasks)
    asyncio.run(scenario())


def test_resource_control_has_no_trace_or_error_text_decision_dependency():
    root = Path(__file__).resolve().parents[3] / "src" / "fc2_metadata_core" / "resource_control"
    forbidden = {"source_execution_traces", "attempts", "deadline_during", "attempt_count",
                 "error_detail", "response", "body"}
    for path in root.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        attrs = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
        assert not attrs & forbidden, (path.name, attrs & forbidden)


def test_fatal_fetch_propagates_original_and_releases_permit():
    async def scenario():
        fatal = GeneratorExit("fatal")
        async def script(number, client):
            raise fatal
        gov = SourceResourceGovernor(HostPolicy(1))
        engine = build("a", script, gov)
        with pytest.raises(GeneratorExit) as caught:
            await engine.aggregate(N)
        assert caught.value is fatal
        assert gov.snapshot("a").in_flight == 0
        await asyncio.wait_for(gov.acquire_host("a"), 0.1)
        gov.release_host("a")
    asyncio.run(scenario())


def test_open_source_aggregation_uses_existing_partial_and_failed_semantics():
    async def scenario():
        async def broken(number, client):
            return failed("a", SourceStatus.PARSE_ERROR)
        async def healthy(number, client):
            return ok("b", number)
        gov = SourceResourceGovernor(breaker_policy=BreakerPolicy(1, 30, 1))
        registry = SourceRegistry()
        registry.register("a", scripted_adapter_class("a", broken))
        registry.register("b", scripted_adapter_class("b", healthy))
        config = AggregationConfig.create([
            SourceConfig("a", retry_policy=RetryPolicy.no_retry()),
            SourceConfig("b", retry_policy=RetryPolicy.no_retry()),
        ])
        engine = MultiSourceEngine(config, registry, Client(), governor=gov)
        await engine.aggregate(N)
        result = await engine.aggregate(N)
        assert result.status is AggregateStatus.PARTIAL
        assert result.source_results[0].error_kind is SourceErrorKind.CIRCUIT_OPEN
        assert result.source_results[1].status is SourceStatus.SUCCESS
        # An all-open circuit yields the existing FAILED aggregate state.
        gov2 = SourceResourceGovernor(breaker_policy=BreakerPolicy(1, 30, 1))
        single = build("a", broken, gov2)
        await single.aggregate(N)
        assert (await single.aggregate(N)).status is AggregateStatus.FAILED
    asyncio.run(scenario())
