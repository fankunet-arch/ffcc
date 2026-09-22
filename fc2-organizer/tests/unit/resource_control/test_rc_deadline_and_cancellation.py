"""Deadline vs. host queue, and cancellation / fatal cleanup at every stage (contract §5.1, §9).

The deadline is enforced by the event loop's own timer, so the few deadline tests use small *real* deadlines; every
assertion is on behaviour (which outcome, which attempt count), with margins of several times the deadline. Everything
else is driven by gates and loop iterations, not by sleeping.
"""

from __future__ import annotations

import asyncio

import pytest

from fc2_metadata_core.aggregation import AggregateStatus, execute_sources_traced
from fc2_metadata_core.aggregation.retry import RetryPolicy
from fc2_metadata_core.models.source_result import SourceErrorKind, SourceStatus
from fc2_metadata_core.resource_control import (
    BreakerState,
    CircuitBreakerPolicy,
    HostLimitPolicy,
    SourceResourceGovernor,
    host_key_for_base_url,
)

from support.resource_fakes import failed, FakeClock, make_engine, make_target, Meter, NullClient, ok, run, Spec, until

K = SourceErrorKind
S = SourceStatus
N = "FC2-1234567"
SAME = "https://same.example"


def gov(threshold=100, duration=30.0, limit=1, clock=None):
    clock = clock or FakeClock()
    return SourceResourceGovernor(
        host_limits=HostLimitPolicy(limit),
        breaker=CircuitBreakerPolicy(failure_threshold=threshold, open_duration_seconds=duration),
        clock=clock,
    ), clock


def breaker_of(governor, source_id):
    return next(b for b in governor.snapshot().breakers if b.source_id == source_id)


def clean(governor):
    """No permit held, no waiter queued, no breaker in-flight count, no probe slot held."""
    shot = governor.snapshot()
    assert all(h.in_flight == 0 and h.waiting == 0 for h in shot.hosts), shot.hosts
    assert all(b.in_flight == 0 and b.half_open_probes_in_flight == 0 for b in shot.breakers), shot.breakers


class Occupant:
    """Another in-flight request: holds the host permit and its breaker ticket until ``release()``."""

    def __init__(self, governor, admission, permit):
        self._governor, self._admission, self._permit = governor, admission, permit

    def release(self):
        self._permit.release()
        self._governor.release(self._admission)


async def occupy(governor, host_url=SAME):
    """Take the host's permit, standing in for another in-flight request."""
    admission = governor.admit("occupant", host_key_for_base_url(host_url))
    return Occupant(governor, admission, await governor.acquire_host_permit(admission))


# ---- deadline vs. host queue ----------------------------------------------------------------------------------------------


def test_waiting_for_a_host_permit_never_turns_an_unsent_request_into_source_deadline():
    async def main():
        governor, _ = gov(limit=1)
        calls = []

        async def script(number, client):
            calls.append(number)
            return ok("src", number)

        target = make_target("src", SAME, script, deadline_seconds=0.15)
        occupant = await occupy(governor)
        run = asyncio.create_task(execute_sources_traced(N, [target], NullClient(), governor=governor))
        await until(lambda: governor.snapshot().hosts[0].waiting == 1)
        await asyncio.sleep(0.5)  # the queue wait is > 3x the source's whole deadline ...
        assert not run.done() and calls == []
        occupant.release()
        (trace,) = await run
        assert trace.final_result.status is S.SUCCESS, "... and yet the deadline was not spent while queued"
        assert (trace.attempt_count, trace.deadline_exceeded) == (1, False) and calls == [N]
        clean(governor)

    run(main())


def test_the_deadline_still_applies_once_the_permit_is_held_and_excludes_the_queue_time():
    async def main():
        governor, _ = gov(limit=1)

        async def hangs(number, client):
            await asyncio.Event().wait()

        target = make_target("src", SAME, hangs, deadline_seconds=0.2)
        occupant = await occupy(governor)
        run = asyncio.create_task(execute_sources_traced(N, [target], NullClient(), governor=governor))
        await until(lambda: governor.snapshot().hosts[0].waiting == 1)
        await asyncio.sleep(0.5)
        occupant.release()
        (trace,) = await asyncio.wait_for(run, 5)
        assert trace.deadline_exceeded and trace.deadline_during == "attempt"
        assert (trace.final_result.status, trace.final_result.error_kind) == (S.NETWORK_ERROR, K.SOURCE_DEADLINE)
        assert trace.attempt_count == 1 and trace.attempts[0].completed is False
        # 0.2 s of execution + 0.5 s of queueing: the reported time is the execution, not the wait
        assert trace.final_result.elapsed_ms < 450, trace.final_result.elapsed_ms
        clean(governor)
        assert breaker_of(governor, "src").consecutive_failures == 1  # a real deadline IS a breaker failure

    run(main())


def test_a_retry_that_queues_for_a_permit_keeps_its_remaining_deadline():
    """deadline 0.4: attempt 1 fails at once, backoff 0.1, attempt 2 queues 0.6 s for the permit. Without suspension the
    deadline would fire *in the queue* (attempt 2 never started, deadline_during == 'backoff'); with it, attempt 2 gets
    the ~0.3 s that remained and starts."""

    async def main():
        governor, _ = gov(limit=1)
        seen = []

        async def script(number, client):
            seen.append(len(seen) + 1)
            if len(seen) == 1:
                return failed("src", S.NETWORK_ERROR, error_kind=K.CONNECTION_ERROR)
            await asyncio.Event().wait()  # attempt 2 hangs, so only the deadline can end it

        target = make_target(
            "src", SAME, script, deadline_seconds=0.4, retry_policy=RetryPolicy(max_attempts=2, initial_backoff_seconds=0.1)
        )
        run = asyncio.create_task(execute_sources_traced(N, [target], NullClient(), governor=governor))
        await until(lambda: seen == [1])
        await asyncio.sleep(0)  # attempt 1 is over and its permit released; the source is now in its 0.1 s backoff
        assert governor.snapshot().hosts[0].in_flight == 0
        occupant = await occupy(governor)  # take the free permit *during the backoff*, so attempt 2 has to queue
        await asyncio.sleep(0.2)  # the backoff ends at ~0.1 s; attempt 2 queues
        assert governor.snapshot().hosts[0].waiting == 1 and seen == [1]
        await asyncio.sleep(0.6)  # queued for longer than the whole 0.4 s deadline
        assert not run.done() and seen == [1]
        occupant.release()
        (trace,) = await asyncio.wait_for(run, 5)
        assert trace.attempt_count == 2 and seen == [1, 2], "attempt 2 must have started: the queue did not spend the deadline"
        assert trace.deadline_exceeded and trace.deadline_during == "attempt" and trace.attempts[1].completed is False
        assert trace.final_result.error_kind is K.SOURCE_DEADLINE
        clean(governor)

    run(main())


def test_the_backoff_pause_still_counts_against_the_deadline_and_holds_no_permit():
    async def main():
        governor, _ = gov(limit=1)

        async def script(number, client):
            return failed("src", S.NETWORK_ERROR, error_kind=K.TIMEOUT)

        async def endless_sleep(seconds):
            assert governor.snapshot().hosts[0].in_flight == 0, "a backoff pause must not hold the host permit"
            await asyncio.Event().wait()

        target = make_target(
            "src", SAME, script, deadline_seconds=0.15, retry_policy=RetryPolicy(max_attempts=2, initial_backoff_seconds=1.0)
        )
        (trace,) = await asyncio.wait_for(
            execute_sources_traced(N, [target], NullClient(), governor=governor, sleep=endless_sleep), 5
        )
        assert trace.deadline_exceeded and trace.deadline_during == "backoff"
        assert trace.attempt_count == 1  # attempt 2 never started
        assert trace.final_result.error_kind is K.SOURCE_DEADLINE
        clean(governor)

    run(main())


def test_without_a_governor_the_deadline_behaves_exactly_as_before():
    async def main():
        async def hangs(number, client):
            await asyncio.Event().wait()

        (trace,) = await asyncio.wait_for(execute_sources_traced(N, [make_target("src", SAME, hangs, deadline_seconds=0.1)], NullClient()), 5)
        assert trace.deadline_exceeded and trace.deadline_during == "attempt" and trace.attempt_count == 1

    run(main())


def test_queue_time_of_a_deadline_free_wait_across_many_sources_and_items_does_not_time_anyone_out():
    """limit 1, 6 sources x 5 lookups each contending for one host; every fetch is fast, deadlines are 0.2 s."""
    meter = Meter()

    def fetcher(source_id):
        async def inner(number, client):
            for _ in range(5):
                await asyncio.sleep(0)
            return ok(source_id, number)

        return meter.wrap(source_id, "same.example", inner)

    async def main():
        governor, _ = gov(limit=1)
        specs = [Spec(f"s{i}", SAME, fetcher(f"s{i}"), deadline_seconds=0.2) for i in range(6)]
        engine = make_engine(specs, governor)
        results = await asyncio.gather(*[engine.aggregate(f"FC2-{1000001 + i}") for i in range(5)])
        assert all(r.status is AggregateStatus.SUCCESS for r in results)
        assert all(tr.final_result.error_kind is not K.SOURCE_DEADLINE for r in results for tr in r.source_execution_traces)
        clean(governor)

    run(main())
    assert meter.peak["same.example"] == 1 and meter.requests.total() == 30


# ---- retry suppression under a stale admission ---------------------------------------------------------------------------------


def test_a_retry_is_not_sent_when_the_breaker_opened_during_the_backoff_the_real_failure_stays_final():
    async def main():
        governor, _ = gov(threshold=2, limit=4)
        fetches = []

        async def script(number, client):
            fetches.append(number)
            if number == "FC2-1000001":  # the retrying call
                return failed("src", S.NETWORK_ERROR, error_kind=K.TIMEOUT) if fetches.count(number) == 1 else ok("src", number)
            return failed("src", S.BLOCKED)

        backoff_started, backoff_release = asyncio.Event(), asyncio.Event()

        async def gated_sleep(seconds):
            backoff_started.set()
            await backoff_release.wait()

        retrying = make_target(
            "src", SAME, script, retry_policy=RetryPolicy(max_attempts=2, initial_backoff_seconds=1.0)
        )
        first = asyncio.create_task(execute_sources_traced("FC2-1000001", [retrying], NullClient(), governor=governor, sleep=gated_sleep))
        await backoff_started.wait()
        for number in ("FC2-2000001", "FC2-2000002"):  # two other lookups of the SAME source trip the breaker meanwhile
            await execute_sources_traced(number, [make_target("src", SAME, script)], NullClient(), governor=governor)
        assert breaker_of(governor, "src").state is BreakerState.OPEN
        backoff_release.set()
        (trace,) = await first
        assert fetches.count("FC2-1000001") == 1, "attempt 2 was NOT sent under the invalidated admission"
        assert trace.attempt_count == 1 and not trace.deadline_exceeded
        assert (trace.final_result.status, trace.final_result.error_kind) == (S.NETWORK_ERROR, K.TIMEOUT)  # the real failure
        assert breaker_of(governor, "src").state is BreakerState.OPEN and breaker_of(governor, "src").epoch == 1
        clean(governor)

    run(main())


# ---- cancellation ------------------------------------------------------------------------------------------------------------------


def test_cancel_while_waiting_for_the_host_permit_propagates_and_leaves_nothing_behind():
    async def main():
        governor, _ = gov(limit=1)
        calls = []

        async def script(number, client):
            calls.append(number)
            return ok("src", number)

        occupant = await occupy(governor)
        run = asyncio.create_task(execute_sources_traced(N, [make_target("src", SAME, script)], NullClient(), governor=governor))
        await until(lambda: governor.snapshot().hosts[0].waiting == 1)
        assert breaker_of(governor, "src").in_flight == 1
        run.cancel()
        with pytest.raises(asyncio.CancelledError):
            await run
        assert calls == []
        host = governor.snapshot().hosts[0]
        assert (host.in_flight, host.waiting) == (1, 0)  # only the occupant remains
        shot = breaker_of(governor, "src")
        assert (shot.in_flight, shot.consecutive_failures, shot.state) == (0, 0, BreakerState.CLOSED)
        occupant.release()
        clean(governor)
        # full capacity: the host serves again
        (trace,) = await execute_sources_traced(N, [make_target("src", SAME, script)], NullClient(), governor=governor)
        assert trace.final_result.status is S.SUCCESS

    run(main())


def test_cancel_inside_the_fetch_releases_everything_and_is_not_a_failure():
    async def main():
        governor, _ = gov(threshold=1, limit=1)
        started = asyncio.Event()

        async def hangs(number, client):
            started.set()
            await asyncio.Event().wait()

        run = asyncio.create_task(execute_sources_traced(N, [make_target("src", SAME, hangs)], NullClient(), governor=governor))
        await started.wait()
        assert governor.snapshot().hosts[0].in_flight == 1
        run.cancel()
        with pytest.raises(asyncio.CancelledError):
            await run
        clean(governor)
        shot = breaker_of(governor, "src")
        assert (shot.state, shot.consecutive_failures, shot.times_opened) == (BreakerState.CLOSED, 0, 0)  # threshold is 1!

    run(main())


def test_cancel_during_the_retry_backoff_releases_everything_and_is_not_a_failure():
    async def main():
        governor, _ = gov(threshold=2, limit=1)

        async def script(number, client):
            return failed("src", S.NETWORK_ERROR, error_kind=K.TIMEOUT)

        in_backoff = asyncio.Event()

        async def blocked_sleep(seconds):
            in_backoff.set()
            await asyncio.Event().wait()

        target = make_target("src", SAME, script, retry_policy=RetryPolicy(max_attempts=2, initial_backoff_seconds=1.0))
        run = asyncio.create_task(execute_sources_traced(N, [target], NullClient(), governor=governor, sleep=blocked_sleep))
        await in_backoff.wait()
        run.cancel()
        with pytest.raises(asyncio.CancelledError):
            await run
        clean(governor)
        assert breaker_of(governor, "src").consecutive_failures == 0  # the first attempt's failure is NOT a final result

    run(main())


@pytest.mark.parametrize("probe", [False, True], ids=["closed", "half_open_probe"])
@pytest.mark.parametrize("cancel_after", range(0, 26))
def test_cancelling_at_every_loop_iteration_leaves_no_permit_no_waiter_no_inflight_and_no_stuck_probe(probe, cancel_after):
    """Cancel one of three contending lookups (two sources on one host, limit 1, with a retry) after k loop
    iterations, for every k: wherever the cancellation lands -- waiting for the aggregate slot, waiting for the host
    permit, inside the fetch, in the retry backoff, or right after the fetch returned -- the resource domain must be
    clean afterwards and cancellation must never have counted as a failure."""

    async def main():
        governor, clock = gov(threshold=1, limit=1)
        meter = Meter()
        seen = {}

        async def slow_ok(number, client):
            seen[number] = seen.get(number, 0) + 1
            for _ in range(2):
                await asyncio.sleep(0)
            if number.endswith("1") and seen[number] == 1:
                return failed("s1", S.NETWORK_ERROR, error_kind=K.TIMEOUT)  # retried once
            return ok("s1" if "s1" in str(client) else "sx", number)

        async def fetch1(number, client):
            r = await slow_ok(number, client)
            return r if r.source_id == "s1" else ok("s1", number) if r.status is S.SUCCESS else failed("s1", r.status, error_kind=r.error_kind)

        async def fetch2(number, client):
            for _ in range(2):
                await asyncio.sleep(0)
            return ok("s2", number)

        fast_retry = RetryPolicy(max_attempts=2, initial_backoff_seconds=0.0)
        specs = [
            Spec("s1", SAME, meter.wrap("s1", "same.example", fetch1), retry_policy=fast_retry),
            Spec("s2", SAME + "/other", meter.wrap("s2", "same.example", fetch2)),
        ]
        engine = make_engine(specs, governor)
        if probe:
            # open the breaker of s1 with a forced failure and let the cooldown pass: the next s1 lookup is the probe
            key = host_key_for_base_url(SAME)
            governor.record_result(governor.admit("s1", key), failed("s1", S.BLOCKED))
            assert breaker_of(governor, "s1").state is BreakerState.OPEN
            clock.advance(30.0)
        tasks = [asyncio.create_task(engine.aggregate(f"FC2-{1000001 + i}")) for i in range(3)]
        for _ in range(cancel_after):
            await asyncio.sleep(0)
        tasks[1].cancel()
        outcomes = await asyncio.gather(*tasks, return_exceptions=True)
        assert isinstance(outcomes[0], BaseException) is False and isinstance(outcomes[2], BaseException) is False
        assert outcomes[1] is not None
        clean(governor)
        for source_id in ("s1", "s2"):
            shot = breaker_of(governor, source_id)
            assert shot.in_flight == 0 and shot.half_open_probes_in_flight == 0
        assert meter.total_live == 0
        if not probe:
            assert breaker_of(governor, "s1").consecutive_failures == 0  # threshold=1: a counted cancellation would open it
            assert breaker_of(governor, "s1").state is BreakerState.CLOSED
        else:
            # never stuck HALF_OPEN with a phantom probe: some later lookup can always probe
            shot = breaker_of(governor, "s1")
            if shot.state is BreakerState.HALF_OPEN:
                retry_probe = governor.admit("s1", host_key_for_base_url(SAME))
                assert retry_probe is not None and retry_probe.is_probe
                governor.release(retry_probe)

    run(main())


def test_cancelling_a_whole_batch_run_leaves_the_shared_governor_clean():
    from fc2_metadata_core.batch import BatchConfig, BatchScheduler
    from support.batch_fakes import numbers

    async def main():
        governor, _ = gov(limit=2)
        meter = Meter()
        gate = asyncio.Event()

        async def script(number, client):
            await gate.wait()
            return ok("src", number)

        engine = make_engine([Spec("src", SAME, meter.wrap("src", "same.example", script))], governor)
        run = asyncio.create_task(BatchScheduler(engine, BatchConfig(max_in_flight_items=10)).run(numbers(50)))
        await until(lambda: meter.total_live == 2 and governor.snapshot().hosts[0].waiting == 8)
        run.cancel()
        with pytest.raises(asyncio.CancelledError):
            await run
        clean(governor)
        assert meter.total_live == 0 and breaker_of(governor, "src").consecutive_failures == 0

    run(main())


# ---- fatal exceptions ----------------------------------------------------------------------------------------------------------------


class Fatal(BaseException):
    """A custom non-Exception BaseException (fatal control flow)."""


def test_a_fatal_exception_propagates_as_the_original_and_releases_every_resource_without_a_breaker_update():
    async def main():
        governor, _ = gov(threshold=1, limit=1)
        boom = Fatal("stop")
        started = asyncio.Event()

        async def dies(number, client):
            started.set()
            raise boom

        async def waits(number, client):
            await asyncio.Event().wait()

        targets = [make_target("dies", SAME, dies), make_target("waits", "https://other.example", waits)]
        with pytest.raises(Fatal) as info:
            await execute_sources_traced(N, targets, NullClient(), governor=governor)
        assert info.value is boom  # the ORIGINAL object, not wrapped, not a result
        clean(governor)
        for source_id in ("dies", "waits"):
            shot = breaker_of(governor, source_id)
            assert (shot.state, shot.consecutive_failures, shot.times_opened) == (BreakerState.CLOSED, 0, 0)  # threshold 1

    run(main())


def test_a_fatal_from_a_source_queued_behind_the_host_releases_the_queue():
    async def main():
        governor, _ = gov(limit=1)

        async def dies(number, client):
            raise KeyboardInterrupt

        async def queued(number, client):  # pragma: no cover - never reached
            return ok("queued", number)

        targets = [make_target("dies", SAME, dies), make_target("queued", SAME + "/b", queued)]
        with pytest.raises(KeyboardInterrupt):
            await execute_sources_traced(N, targets, NullClient(), governor=governor)
        clean(governor)

    run(main())


def test_the_fatal_carrier_never_reads_the_raisers_metadata():
    """C4-R1 class of bug at the C5 boundary: a fatal exception whose metaclass makes ``__name__`` raise must still
    reach the caller as itself (the carrier used to read ``type(original).__name__``)."""

    class HostileMeta(type):
        @property
        def __name__(cls):  # type: ignore[override]
            raise RuntimeError("hostile __name__ must never be read")

    class HostileFatal(BaseException, metaclass=HostileMeta):
        pass

    async def main():
        governor, _ = gov(limit=1)
        boom = HostileFatal()

        async def dies(number, client):
            raise boom

        for use_governor in (governor, None):
            with pytest.raises(HostileFatal) as info:
                await execute_sources_traced(N, [make_target("dies", SAME, dies)], NullClient(), governor=use_governor)
            assert info.value is boom
        clean(governor)

    run(main())


def test_an_adapter_raising_cancelled_error_by_itself_is_a_failure_and_releases_the_permit():
    async def main():
        governor, _ = gov(threshold=2, limit=1)

        async def self_cancel(number, client):
            raise asyncio.CancelledError  # no cancellation was requested for the task: a misbehaving adapter

        target = make_target("src", SAME, self_cancel)
        for _ in range(2):
            (trace,) = await execute_sources_traced(N, [target], NullClient(), governor=governor)
            assert (trace.final_result.status, trace.final_result.error_kind) == (S.INVALID_RESPONSE, K.ADAPTER_EXCEPTION)
        assert breaker_of(governor, "src").state is BreakerState.OPEN  # ordinary failures: counted
        clean(governor)

    run(main())


def test_an_ordinary_adapter_exception_is_isolated_counted_and_releases_the_permit():
    async def main():
        governor, _ = gov(threshold=2, limit=1)

        async def broken(number, client):
            raise ValueError("secret-token-123 must not leak")

        async def fine(number, client):
            return ok("fine", number)

        targets = [make_target("src", SAME, broken), make_target("fine", SAME + "/b", fine)]
        for _ in range(2):
            traces = await execute_sources_traced(N, targets, NullClient(), governor=governor)
            assert traces[0].final_result.error_kind is K.ADAPTER_EXCEPTION and traces[1].final_result.status is S.SUCCESS
            assert "secret-token-123" not in traces[0].final_result.error_detail
        assert breaker_of(governor, "src").state is BreakerState.OPEN
        assert breaker_of(governor, "fine").state is BreakerState.CLOSED
        clean(governor)

    run(main())
