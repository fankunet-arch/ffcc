"""Source execution boundary: bounded concurrency, order, deadlines, isolation,
cancellation, fail-closed validation. Real ``SourceAdapter`` subclasses, no network.

Closes Phase 2 review finding P2-R-09 on the Phase 3 scheduler path: httpx's
timeout is per phase, so the *whole lookup* gets a wall-clock deadline here, at
the engine boundary, without touching any adapter.
"""

from __future__ import annotations

import asyncio
import time

import pytest

from fc2_metadata_core.aggregation import (
    AggregationConfigError,
    SourceConfig,
    SourceTarget,
    execute_sources,
)
from fc2_metadata_core.models.source_result import SourceStatus

from support.scripted_adapters import failed, ok, scripted_adapter_class

N = "FC2-4979299"
CLIENT = object()  # the shared "client": adapters only see it, never call it


def target(source_id, script, *, deadline=20.0):
    adapter = scripted_adapter_class(source_id, script)()
    return SourceTarget(SourceConfig(source_id, deadline_seconds=deadline), adapter)


def run(coro):
    return asyncio.run(coro)


def execute(targets, **kwargs):
    return run(execute_sources(N, targets, CLIENT, **kwargs))


def instant(source_id, title="T"):
    async def script(number, client):
        return ok(source_id, number, title)

    return script


# ---- order (15) ------------------------------------------------------------------------------------


def test_15_results_follow_configuration_order_even_when_completion_order_is_reversed():
    finished: list[str] = []

    def slow(source_id, delay):
        async def script(number, client):
            await asyncio.sleep(delay)
            finished.append(source_id)
            return ok(source_id, number, f"title-{source_id}")

        return script

    targets = [target("a", slow("a", 0.12)), target("b", slow("b", 0.06)), target("c", slow("c", 0.0))]
    results = execute(targets)
    assert finished == ["c", "b", "a"]  # they really did complete in reverse order
    assert [r.source_id for r in results] == ["a", "b", "c"]
    assert [r.metadata.title for r in results] == ["title-a", "title-b", "title-c"]


def test_a_slow_source_does_not_block_or_lose_the_already_finished_results():
    async def slow(number, client):
        await asyncio.sleep(0.2)
        return ok("slow", number, "slow title")

    started = time.monotonic()
    results = execute([target("fast1", instant("fast1")), target("slow", slow), target("fast2", instant("fast2"))])
    assert [r.source_id for r in results] == ["fast1", "slow", "fast2"]
    assert all(r.status is SourceStatus.SUCCESS for r in results)
    assert time.monotonic() - started < 1.0  # ran together, not one after the other


# ---- bounded concurrency ---------------------------------------------------------------------------


class Gauge:
    def __init__(self):
        self.active = 0
        self.peak = 0
        self.started: list[str] = []

    def script(self, source_id, hold=0.05):
        async def script(number, client):
            self.active += 1
            self.peak = max(self.peak, self.active)
            self.started.append(source_id)
            try:
                await asyncio.sleep(hold)
            finally:
                self.active -= 1
            return ok(source_id, number, source_id)

        return script


@pytest.mark.parametrize("limit, expected_peak", [(1, 1), (2, 2), (3, 3), (5, 5)])
def test_max_concurrency_is_a_real_limit_and_the_run_is_not_serial(limit, expected_peak):
    gauge = Gauge()
    targets = [target(f"s{i}", gauge.script(f"s{i}")) for i in range(5)]
    results = execute(targets, max_concurrency=limit)
    assert gauge.peak <= limit, "concurrency limit exceeded"
    assert gauge.peak == expected_peak, "sources ran serially / below the allowed parallelism"
    assert [r.source_id for r in results] == [f"s{i}" for i in range(5)]


def test_five_sources_with_limit_two_never_exceed_two_and_do_reach_two():
    gauge = Gauge()
    started = time.monotonic()
    execute([target(f"s{i}", gauge.script(f"s{i}", hold=0.08)) for i in range(5)], max_concurrency=2)
    elapsed = time.monotonic() - started
    assert gauge.peak == 2
    assert 0.2 <= elapsed < 0.8  # ceil(5/2)=3 waves of ~0.08 s: bounded but not serial (0.4 s+) nor fully parallel


def test_default_concurrency_is_three():
    gauge = Gauge()
    execute([target(f"s{i}", gauge.script(f"s{i}")) for i in range(6)])
    assert gauge.peak == 3


@pytest.mark.parametrize("bad", [0, -1, 65, 2.0, True, None, "2"])
def test_invalid_concurrency_is_a_config_error_and_starts_nothing(bad):
    gauge = Gauge()
    with pytest.raises(AggregationConfigError):
        execute([target("a", gauge.script("a"))], max_concurrency=bad)
    assert gauge.started == []


def test_no_targets_is_a_config_error():
    with pytest.raises(AggregationConfigError):
        execute([])


def test_target_adapter_must_match_its_config():
    adapter = scripted_adapter_class("a", instant("a"))()
    with pytest.raises(AggregationConfigError):
        SourceTarget(SourceConfig("not_a"), adapter)
    with pytest.raises(AggregationConfigError):
        SourceTarget(SourceConfig("a"), object())  # type: ignore[arg-type]


def test_every_adapter_receives_the_one_shared_client():
    seen = []

    def script(source_id):
        async def s(number, client):
            seen.append(client)
            return ok(source_id, number, "T")

        return s

    execute([target("a", script("a")), target("b", script("b"))])
    assert len(seen) == 2 and all(c is CLIENT for c in seen)


# ---- deadline (20) ---------------------------------------------------------------------------------


async def hang(number, client):
    await asyncio.Event().wait()


def test_20_deadline_expiry_affects_only_that_source():
    started = time.monotonic()
    results = execute(
        [target("stuck", hang, deadline=0.15), target("good", instant("good", "Good Title"))]
    )
    wall = time.monotonic() - started
    stuck, good = results
    assert stuck.status is SourceStatus.NETWORK_ERROR and stuck.metadata is None
    assert "source execution deadline exceeded" in stuck.error_detail and "stuck" in stuck.error_detail
    assert good.status is SourceStatus.SUCCESS and good.metadata.title == "Good Title"
    assert 0.12 <= wall < 1.5  # the deadline is what ended the run


def test_deadline_result_reports_real_elapsed_time_not_zero():
    (stuck,) = execute([target("stuck", hang, deadline=0.2)])
    assert 150 <= stuck.elapsed_ms < 1500


def test_deadline_is_wall_clock_for_the_whole_lookup_not_per_step():
    async def dribble(number, client):
        for _ in range(100):  # many short awaits, each "active": an inactivity timeout would never fire
            await asyncio.sleep(0.02)
        return ok("dribble", number, "too late")

    (result,) = execute([target("dribble", dribble, deadline=0.2)])
    assert result.status is SourceStatus.NETWORK_ERROR
    assert "deadline exceeded" in result.error_detail and result.elapsed_ms < 1500


def test_deadline_does_not_include_time_spent_waiting_for_a_concurrency_slot():
    async def takes(seconds, source_id):
        async def script(number, client):
            await asyncio.sleep(seconds)
            return ok(source_id, number, source_id)

        return script

    async def build():
        return await takes(0.25, "first"), await takes(0.05, "second")

    first, second = run(build())
    # "second" queues ~0.25 s behind "first" but only needs 0.05 s of its own 0.15 s deadline.
    results = execute([target("first", first, deadline=5.0), target("second", second, deadline=0.15)], max_concurrency=1)
    assert [r.status for r in results] == [SourceStatus.SUCCESS, SourceStatus.SUCCESS]


def test_a_source_that_finishes_within_its_deadline_is_untouched():
    (result,) = execute([target("a", instant("a", "ok"), deadline=5.0)])
    assert result.status is SourceStatus.SUCCESS and result.metadata.title == "ok"


# ---- isolation (18) ----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "exc",
    [RuntimeError("secret-token=abc123 https://user:pw@evil.example/x"), TypeError("t"), KeyError("k"), ValueError("v"),
     AttributeError("a"), ZeroDivisionError("z"), OSError("o"), ExceptionGroup("g", [ValueError("x")])],
    ids=lambda e: type(e).__name__,
)
def test_18_unexpected_adapter_exception_is_isolated_and_the_other_source_still_runs(exc):
    async def boom(number, client):
        raise exc

    results = execute([target("boom", boom), target("good", instant("good"))])
    bad, good = results
    assert bad.status is SourceStatus.INVALID_RESPONSE and bad.metadata is None
    assert "boom" in bad.error_detail and type(exc).__name__ in bad.error_detail
    assert good.status is SourceStatus.SUCCESS


def test_the_exception_message_never_leaks_into_the_result():
    async def boom(number, client):
        raise RuntimeError("secret-token=abc123 https://user:pw@evil.example/x")

    (bad,) = execute([target("boom", boom)])
    for leaked in ("secret-token", "abc123", "user:pw", "evil.example"):
        assert leaked not in bad.error_detail


def test_a_builtin_timeout_error_raised_by_the_adapter_is_not_mistaken_for_the_deadline():
    async def raises_timeout(number, client):
        raise TimeoutError("the adapter's own")

    (result,) = execute([target("t", raises_timeout, deadline=5.0)])
    assert result.status is SourceStatus.INVALID_RESPONSE
    assert "deadline" not in result.error_detail and "TimeoutError" in result.error_detail


@pytest.mark.parametrize("status", [s for s in SourceStatus if s is not SourceStatus.SUCCESS], ids=lambda s: s.value)
def test_every_kind_of_source_failure_leaves_the_others_running(status):
    async def fails(number, client):
        return failed("x", status)

    results = execute([target("x", fails), target("good", instant("good"))])
    assert results[0].status is status and results[1].status is SourceStatus.SUCCESS


@pytest.mark.parametrize("junk", [None, 42, "text", object(), {"status": "success"}], ids=lambda j: type(j).__name__)
def test_a_non_source_result_return_value_fails_closed(junk):
    async def returns_junk(number, client):
        return junk

    results = execute([target("junk", returns_junk), target("good", instant("good"))])
    assert results[0].status is SourceStatus.INVALID_RESPONSE and "SourceResult" in results[0].error_detail
    assert results[1].status is SourceStatus.SUCCESS


def test_success_for_another_number_or_labelled_with_another_source_id_fails_closed():
    async def wrong_number(number, client):
        return ok("num", "FC2-1111111", "other film")

    async def wrong_id(number, client):
        return ok("someone_else", number, "stolen")

    results = execute([target("num", wrong_number), target("idx", wrong_id), target("good", instant("good"))])
    assert [r.status for r in results] == [SourceStatus.INVALID_RESPONSE, SourceStatus.INVALID_RESPONSE, SourceStatus.SUCCESS]
    assert all(r.metadata is None for r in results[:2])
    assert [r.source_id for r in results] == ["num", "idx", "good"]  # labelled by slot, not by claim


# ---- cancellation and BaseException (19) ---------------------------------------------------------------


def test_19_caller_cancellation_propagates_and_cancels_in_flight_sources():
    cancelled: list[str] = []

    def hanging(source_id):
        async def script(number, client):
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                cancelled.append(source_id)
                raise

        return script

    async def scenario():
        task = asyncio.create_task(execute_sources(N, [target("a", hanging("a")), target("b", hanging("b"))], CLIENT))
        await asyncio.sleep(0.1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert task.cancelled()

    run(scenario())
    assert sorted(cancelled) == ["a", "b"]  # nothing left running


def test_cancellation_is_not_turned_into_a_source_result_even_with_a_finished_sibling():
    async def scenario():
        task = asyncio.create_task(
            execute_sources(N, [target("done", instant("done")), target("hang", hang)], CLIENT)
        )
        await asyncio.sleep(0.1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    run(scenario())


@pytest.mark.parametrize("exc_type", [KeyboardInterrupt, SystemExit])
def test_keyboard_interrupt_and_system_exit_are_never_swallowed_as_source_failures(exc_type):
    async def raises(number, client):
        raise exc_type()

    with pytest.raises((exc_type, BaseExceptionGroup)):
        execute([target("x", raises), target("good", instant("good"))])


def test_cancelled_error_raised_by_an_outer_wait_for_still_propagates():
    async def scenario():
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(execute_sources(N, [target("a", hang)], CLIENT), timeout=0.1)

    run(scenario())
