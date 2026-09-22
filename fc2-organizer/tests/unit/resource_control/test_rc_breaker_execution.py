"""The breaker through the real execution boundary / engine (contract §6-§8).

All offline. Breaker time is the injected ``FakeClock``; ordering comes from gates and explicit yields.
"""

from __future__ import annotations

import asyncio

import pytest

from fc2_metadata_core.aggregation import (
    AggregateStatus,
    AggregationConfigError,
    AggregationContractError,
    SourceAttempt,
    SourceExecutionTrace,
    execute_sources_traced,
)
from fc2_metadata_core.aggregation.retry import RETRY_ELIGIBLE_KINDS, RetryPolicy
from fc2_metadata_core.models.metadata import NormalizedMetadata
from fc2_metadata_core.models.source_result import (
    ALLOWED_ERROR_KINDS,
    SourceErrorKind,
    SourceResult,
    SourceStatus,
    status_for_error_kind,
)
from fc2_metadata_core.resource_control import (
    BreakerState,
    CircuitBreakerPolicy,
    HostLimitPolicy,
    SourceResourceGovernor,
    circuit_open_result,
    host_key_for_base_url,
)

from support.resource_fakes import failed, FakeClock, make_engine, make_target, Meter, NullClient, ok, run, Spec, until

K = SourceErrorKind
S = SourceStatus
N = "FC2-1234567"
HOST = "https://x.example"


def gov(threshold=3, duration=30.0, probes=1, limit=4, clock=None):
    clock = clock or FakeClock()
    return SourceResourceGovernor(
        host_limits=HostLimitPolicy(limit),
        breaker=CircuitBreakerPolicy(failure_threshold=threshold, open_duration_seconds=duration, half_open_max_calls=probes),
        clock=clock,
    ), clock


def breaker_of(governor, source_id="src"):
    return next(b for b in governor.snapshot().breakers if b.source_id == source_id)


def scripted(meter: Meter, status: S | None, source_id="src", *, kind: K | None = None):
    async def inner(number, client):
        await asyncio.sleep(0)
        if status is None:
            return ok(source_id, number)
        return failed(source_id, status, error_kind=kind)

    return meter.wrap(source_id, "x.example", inner)


def lookups(engine, count, start=1_000_001):
    async def main():
        return [await engine.aggregate(f"FC2-{start + i}") for i in range(count)]

    return run(main())


# ---- failures open it, and an open breaker sends nothing ------------------------------------------------------------------


@pytest.mark.parametrize("status", [S.BLOCKED, S.RATE_LIMITED, S.PARSE_ERROR, S.NETWORK_ERROR, S.INVALID_RESPONSE], ids=lambda s: s.value)
def test_threshold_consecutive_final_failures_open_the_breaker_and_then_zero_requests_are_made(status):
    meter, (governor, _) = Meter(), gov(threshold=3)
    engine = make_engine([Spec("src", HOST, scripted(meter, status))], governor)
    results = lookups(engine, 10)
    assert meter.requests["src"] == 3, "exactly `threshold` requests, then the breaker is open: 0 network requests"
    assert breaker_of(governor).state is BreakerState.OPEN
    assert [r.source_results[0].error_kind is K.CIRCUIT_OPEN for r in results] == [False] * 3 + [True] * 7
    for open_result in results[3:]:
        assert open_result.status is AggregateStatus.FAILED
        (source_result,) = open_result.source_results
        assert source_result.status is S.NETWORK_ERROR and source_result.metadata is None
        (trace,) = open_result.source_execution_traces
        assert trace.attempt_count == 0 and trace.attempts == () and not trace.retried and not trace.deadline_exceeded
    # nothing was held: the open breaker never touched the host
    assert all(h.in_flight == 0 and h.waiting == 0 for h in governor.snapshot().hosts)
    assert breaker_of(governor).in_flight == 0


def test_blocked_and_rate_limited_are_never_retried_but_are_breaker_failures():
    meter, (governor, _) = Meter(), gov(threshold=2)
    retrying = RetryPolicy(max_attempts=3, initial_backoff_seconds=0.0)
    for status in (S.BLOCKED, S.RATE_LIMITED):
        engine = make_engine([Spec("src", HOST, scripted(meter, status), retry_policy=retrying)], gov(threshold=2)[0])
        lookups(engine, 6)
    assert meter.requests["src"] == 4  # 2 + 2: one attempt per lookup (never retried), then open


def test_100_consecutive_not_found_keep_the_breaker_closed_with_zero_failures():
    meter, (governor, _) = Meter(), gov(threshold=3)
    engine = make_engine([Spec("src", HOST, scripted(meter, S.NOT_FOUND))], governor)
    results = lookups(engine, 100)
    shot = breaker_of(governor)
    assert (shot.state, shot.consecutive_failures, shot.epoch, shot.times_opened) == (BreakerState.CLOSED, 0, 0, 0)
    assert meter.requests["src"] == 100 and all(r.status is AggregateStatus.FAILED for r in results)
    assert all(r.source_results[0].error_kind is K.NOT_FOUND for r in results)


def test_success_between_failures_resets_the_count_through_the_engine():
    meter, (governor, _) = Meter(), gov(threshold=3)
    plan = iter([S.BLOCKED, S.BLOCKED, None] * 10)

    async def script(number, client):
        status = next(plan)
        return ok("src", number) if status is None else failed("src", status)

    engine = make_engine([Spec("src", HOST, meter.wrap("src", "x.example", script))], governor)
    lookups(engine, 30)
    assert meter.requests["src"] == 30 and breaker_of(governor).state is BreakerState.CLOSED


def test_partial_parse_metadata_is_not_read_only_the_status_matters():
    """A PARSE_ERROR that carries partial metadata is a failure exactly like one that does not."""
    meter, (governor, _) = Meter(), gov(threshold=2)

    async def script(number, client):
        partial = NormalizedMetadata(number=number)  # no title: does not meet minimum success
        return SourceResult("src", S.PARSE_ERROR, partial, 1.0, K.PARSE_ERROR, "layout drift")

    engine = make_engine([Spec("src", HOST, meter.wrap("src", "x.example", script))], governor)
    lookups(engine, 5)
    assert meter.requests["src"] == 2 and breaker_of(governor).state is BreakerState.OPEN


# ---- retry interaction ---------------------------------------------------------------------------------------------------


def test_a_retry_that_recovers_is_one_healthy_observation_not_a_failure():
    meter, (governor, _) = Meter(), gov(threshold=2)
    calls = {}

    async def script(number, client):
        calls[number] = calls.get(number, 0) + 1
        if calls[number] == 1:
            return failed("src", S.NETWORK_ERROR, error_kind=K.TIMEOUT)
        return ok("src", number)

    fast_retry = RetryPolicy(max_attempts=2, initial_backoff_seconds=0.0)
    engine = make_engine([Spec("src", HOST, meter.wrap("src", "x.example", script), retry_policy=fast_retry)], governor)
    results = lookups(engine, 10)
    assert all(r.status is AggregateStatus.SUCCESS for r in results)
    assert meter.requests["src"] == 20  # two attempts per lookup ...
    shot = breaker_of(governor)
    assert (shot.state, shot.consecutive_failures, shot.times_opened) == (BreakerState.CLOSED, 0, 0)  # ... one healthy each


def test_two_failed_attempts_of_one_execution_are_one_failure_not_two():
    meter, (governor, _) = Meter(), gov(threshold=2)
    fast_retry = RetryPolicy(max_attempts=2, initial_backoff_seconds=0.0)
    engine = make_engine(
        [Spec("src", HOST, scripted(meter, S.NETWORK_ERROR, kind=K.TIMEOUT), retry_policy=fast_retry)], governor
    )
    first = lookups(engine, 1)[0]
    assert meter.requests["src"] == 2 and first.source_execution_traces[0].attempt_count == 2
    assert breaker_of(governor).consecutive_failures == 1 and breaker_of(governor).state is BreakerState.CLOSED
    lookups(engine, 1, start=2_000_001)
    assert meter.requests["src"] == 4 and breaker_of(governor).state is BreakerState.OPEN
    lookups(engine, 3, start=3_000_001)
    assert meter.requests["src"] == 4  # open: no attempt at all, in particular no "retry" of a circuit-open answer


def test_circuit_open_is_never_retried_even_by_a_generous_policy():
    meter, (governor, _) = Meter(), gov(threshold=1)
    generous = RetryPolicy(max_attempts=5, initial_backoff_seconds=0.0)
    engine = make_engine([Spec("src", HOST, scripted(meter, S.BLOCKED), retry_policy=generous)], governor)
    lookups(engine, 8)
    assert meter.requests["src"] == 1
    result = lookups(engine, 1, start=9_000_001)[0]
    assert result.source_execution_traces[0].attempt_count == 0
    assert meter.requests["src"] == 1


def test_circuit_open_can_never_be_made_retryable():
    assert K.CIRCUIT_OPEN not in RETRY_ELIGIBLE_KINDS
    with pytest.raises(AggregationConfigError):
        RetryPolicy(retryable_error_kinds=frozenset({K.CIRCUIT_OPEN}))
    with pytest.raises(AggregationConfigError):
        RetryPolicy(retryable_error_kinds=RETRY_ELIGIBLE_KINDS | {K.CIRCUIT_OPEN})
    assert RetryPolicy().is_retryable(circuit_open_result("src")) is False
    assert RetryPolicy().should_retry(circuit_open_result("src"), 1) is False


def test_no_host_permit_is_held_during_a_retry_backoff():
    """Attempt 1 fails retryably; while it backs off (gated `sleep`) another source on the SAME host (limit 1) must be
    able to fetch. Attempt 2 then acquires a permit again."""

    async def main():
        governor, _ = gov(limit=1)
        log: list[str] = []

        async def flaky(number, client):
            log.append("flaky-fetch")
            if log.count("flaky-fetch") == 1:
                return failed("flaky", S.NETWORK_ERROR, error_kind=K.CONNECTION_ERROR)
            return ok("flaky", number)

        async def other(number, client):
            log.append("other-fetch")
            return ok("other", number)

        backoff_started, backoff_release = asyncio.Event(), asyncio.Event()

        async def gated_sleep(seconds):
            log.append(f"backoff({seconds:g})")
            backoff_started.set()
            await backoff_release.wait()

        targets = [
            make_target("flaky", "https://same.example/a", flaky, retry_policy=RetryPolicy(max_attempts=2, initial_backoff_seconds=1.0)),
        ]
        first = asyncio.create_task(
            execute_sources_traced(N, targets, NullClient(), governor=governor, sleep=gated_sleep)
        )
        await backoff_started.wait()
        assert governor.snapshot().hosts[0].in_flight == 0, "the backoff pause must not hold the host permit"
        # a different source on the same host runs to completion while `flaky` is backing off
        (other_trace,) = await execute_sources_traced(
            N, [make_target("other", "https://same.example/b", other)], NullClient(), governor=governor
        )
        assert other_trace.final_result.status is S.SUCCESS and log[-1] == "other-fetch"
        backoff_release.set()
        (trace,) = await first
        assert log == ["flaky-fetch", "backoff(1)", "other-fetch", "flaky-fetch"]
        assert trace.attempt_count == 2 and trace.final_result.status is S.SUCCESS
        assert breaker_of(governor, "flaky").consecutive_failures == 0  # final SUCCESS: one healthy observation
        assert governor.snapshot().hosts[0].in_flight == 0

    run(main())


# ---- HALF_OPEN through the engine -----------------------------------------------------------------------------------------


def trip_through_engine(engine, count=3):
    lookups(engine, count, start=8_000_001)


def test_100_lookups_after_the_cooldown_send_exactly_one_probe_and_99_are_short_circuited():
    meter, (governor, clock) = Meter(), gov(threshold=3, duration=30.0)
    healthy = {"now": False}
    release = asyncio.Event()

    async def script(number, client):
        if not healthy["now"]:
            return failed("src", S.BLOCKED)
        await release.wait()  # the probe stays in flight while the other 99 arrive
        return ok("src", number)

    engine = make_engine([Spec("src", HOST, meter.wrap("src", "x.example", script))], governor)
    trip_through_engine(engine)
    assert breaker_of(governor).state is BreakerState.OPEN and meter.requests["src"] == 3
    healthy["now"] = True
    clock.advance(30.0)

    async def main():
        tasks = [asyncio.create_task(engine.aggregate(f"FC2-{4_000_000 + i}")) for i in range(100)]
        await until(lambda: meter.requests["src"] == 4 and sum(t.done() for t in tasks) == 99)
        assert meter.total_live == 1, "exactly one probe is in flight"
        assert breaker_of(governor).state is BreakerState.HALF_OPEN and breaker_of(governor).half_open_probes_in_flight == 1
        release.set()
        return await asyncio.gather(*tasks)

    results = run(main())
    assert meter.requests["src"] == 4, "one probe fetch in total: no thundering herd"
    kinds = [r.source_results[0].error_kind for r in results]
    assert kinds.count(K.CIRCUIT_OPEN) == 99 and kinds.count(None) == 1
    assert sum(r.status is AggregateStatus.SUCCESS for r in results) == 1
    assert breaker_of(governor).state is BreakerState.CLOSED
    assert lookups(engine, 5, start=5_000_000)[0].status is AggregateStatus.SUCCESS  # traffic resumes


def test_a_failed_probe_reopens_and_the_cooldown_restarts():
    meter, (governor, clock) = Meter(), gov(threshold=2, duration=30.0)
    engine = make_engine([Spec("src", HOST, scripted(meter, S.PARSE_ERROR))], governor)
    trip_through_engine(engine, 2)
    clock.advance(30)
    lookups(engine, 1, start=6_000_001)  # the probe: fails again
    assert meter.requests["src"] == 3 and breaker_of(governor).state is BreakerState.OPEN
    clock.advance(29.9)
    lookups(engine, 5, start=6_100_001)
    assert meter.requests["src"] == 3  # still cooling down (from the probe's failure, not from the first opening)
    clock.advance(0.1)
    lookups(engine, 1, start=6_200_001)
    assert meter.requests["src"] == 4


def test_a_cancelled_probe_frees_the_probe_slot_for_the_next_lookup():
    meter, (governor, clock) = Meter(), gov(threshold=1, duration=10.0)
    mode = {"hang": False}

    async def script(number, client):
        if mode["hang"]:
            await asyncio.Event().wait()
        return failed("src", S.BLOCKED)

    engine = make_engine([Spec("src", HOST, meter.wrap("src", "x.example", script))], governor)
    lookups(engine, 1)  # opens (threshold 1)
    clock.advance(10)
    mode["hang"] = True

    async def main():
        probe = asyncio.create_task(engine.aggregate("FC2-7000001"))
        await until(lambda: meter.total_live == 1)
        assert breaker_of(governor).half_open_probes_in_flight == 1
        short = await engine.aggregate("FC2-7000002")  # rejected: the only probe slot is taken
        assert short.source_results[0].error_kind is K.CIRCUIT_OPEN
        probe.cancel()
        with pytest.raises(asyncio.CancelledError):
            await probe
        shot = breaker_of(governor)
        assert (shot.state, shot.half_open_probes_in_flight, shot.in_flight) == (BreakerState.HALF_OPEN, 0, 0)
        mode["hang"] = False
        return await engine.aggregate("FC2-7000003")  # the slot is free again: a new probe is admitted

    result = run(main())
    assert result.source_results[0].error_kind is K.BLOCKED  # a real probe request was made (and failed)
    assert breaker_of(governor).state is BreakerState.OPEN


# ---- stale completion & in-flight calls through the engine ----------------------------------------------------------------------


def test_a_late_success_of_an_older_admission_does_not_close_a_breaker_that_just_opened():
    async def main():
        meter, (governor, _) = Meter(), gov(threshold=2, limit=8)
        gates = {n: asyncio.Event() for n in ("A", "B", "C")}
        outcome = {"A": S.SUCCESS, "B": S.BLOCKED, "C": S.BLOCKED}
        which = {"1": "A", "2": "B", "3": "C"}  # the number's first digit says which scripted call this is

        async def script(number, client):
            name = which[number[4]]
            await gates[name].wait()
            return ok("src", number) if outcome[name] is S.SUCCESS else failed("src", outcome[name])

        engine = make_engine([Spec("src", HOST, meter.wrap("src", "x.example", script))], governor)
        call_a = asyncio.create_task(engine.aggregate("FC2-1000001"))
        call_b = asyncio.create_task(engine.aggregate("FC2-2000001"))
        call_c = asyncio.create_task(engine.aggregate("FC2-3000001"))
        await until(lambda: meter.total_live == 3)  # all three admitted in the same epoch, all fetching
        gates["B"].set()
        gates["C"].set()
        await asyncio.gather(call_b, call_c)
        assert breaker_of(governor).state is BreakerState.OPEN and breaker_of(governor).epoch == 1
        assert meter.total_live == 1, "A is still in flight: opening the breaker does not cancel it"
        gates["A"].set()
        result_a = await call_a
        assert result_a.status is AggregateStatus.SUCCESS  # the in-flight call finishes and returns normally
        shot = breaker_of(governor)
        assert (shot.state, shot.epoch, shot.in_flight, shot.times_opened) == (BreakerState.OPEN, 1, 0, 1)
        after = await engine.aggregate("FC2-9000001")
        assert after.source_results[0].error_kind is K.CIRCUIT_OPEN
        assert meter.requests["src"] == 3

    run(main())


def test_a_lookup_queued_for_the_host_when_the_breaker_opens_sends_nothing():
    """Contract §7 step 3: breaker admission -> host permit -> re-validate. Host limit 1; call 1 fetches, calls 2 and 3
    were admitted (CLOSED) and queue for the permit; call 1 fails and trips the breaker; the queued calls get their
    permits but must NOT fetch."""

    async def main():
        meter, (governor, _) = Meter(), gov(threshold=1, limit=1)
        gate = asyncio.Event()

        async def script(number, client):
            await gate.wait()
            return failed("src", S.BLOCKED)

        engine = make_engine([Spec("src", HOST, meter.wrap("src", "x.example", script))], governor)
        tasks = [asyncio.create_task(engine.aggregate(f"FC2-{1000001 + i}")) for i in range(3)]
        await until(lambda: meter.total_live == 1 and governor.snapshot().hosts[0].waiting == 2)
        assert breaker_of(governor).in_flight == 3  # all three admitted while CLOSED
        gate.set()
        results = await asyncio.gather(*tasks)
        assert meter.requests["src"] == 1, "the queued lookups were fenced off by the new epoch: no request"
        kinds = [r.source_results[0].error_kind for r in results]
        assert kinds == [K.BLOCKED, K.CIRCUIT_OPEN, K.CIRCUIT_OPEN]
        for stale in results[1:]:
            assert stale.source_execution_traces[0].attempts == ()
        shot = breaker_of(governor)
        assert (shot.in_flight, shot.state, shot.times_opened) == (0, BreakerState.OPEN, 1)
        host = governor.snapshot().hosts[0]
        assert (host.in_flight, host.waiting) == (0, 0)

    run(main())


def test_an_open_breaker_does_not_queue_for_a_saturated_host():
    async def main():
        governor, _ = gov(threshold=1, limit=1)
        calls = []

        async def dead(number, client):
            calls.append(number)
            return failed("dead", S.BLOCKED)

        target = make_target("dead", "https://same.example/b", dead)
        (first,) = await execute_sources_traced(N, [target], NullClient(), governor=governor)
        assert first.final_result.status is S.BLOCKED and breaker_of(governor, "dead").state is BreakerState.OPEN
        # saturate the host's only slot with someone else, then ask the open source again
        occupant = await governor.acquire_host_permit(governor.admit("holder", host_key_for_base_url("https://same.example")))
        assert governor.snapshot().hosts[0].in_flight == 1
        (short,) = await asyncio.wait_for(execute_sources_traced(N, [target], NullClient(), governor=governor), 5)
        assert short.final_result.error_kind is K.CIRCUIT_OPEN and short.attempts == ()
        assert governor.snapshot().hosts[0].waiting == 0, "an open breaker must not join the host queue"
        assert calls == [N]
        occupant.release()

    run(main())


# ---- aggregation semantics of a circuit-open source --------------------------------------------------------------------------------


def open_and_ok_engine(meter, governor, *, a_status=None, b_status=None):
    a_script = scripted(meter, a_status if a_status is not None else S.BLOCKED, "source_a")
    b_script = scripted(meter, b_status, "source_b")
    return make_engine(
        [Spec("source_a", "https://a.example", a_script), Spec("source_b", "https://b.example", b_script)], governor
    )


def force_open(governor, source_id, host="https://a.example"):
    key = host_key_for_base_url(host)
    for _ in range(governor.breaker_policy.failure_threshold):
        governor.record_result(governor.admit(source_id, key), failed(source_id, S.BLOCKED))
    assert governor.admit(source_id, key) is None


def test_one_source_open_and_another_successful_aggregates_to_partial():
    meter, (governor, _) = Meter(), gov(threshold=1)
    engine = open_and_ok_engine(meter, governor, b_status=None)
    force_open(governor, "source_a")
    result = lookups(engine, 1)[0]
    assert result.status is AggregateStatus.PARTIAL
    a, b = result.source_results
    assert (a.status, a.error_kind) == (S.NETWORK_ERROR, K.CIRCUIT_OPEN) and b.status is S.SUCCESS
    assert result.contributing_source_ids == ("source_b",) and result.metadata is not None
    assert meter.requests["source_a"] == 0 and meter.requests["source_b"] == 1
    assert [t.attempt_count for t in result.source_execution_traces] == [0, 1]


def test_every_source_open_is_failed_with_every_source_result_kept():
    meter, (governor, _) = Meter(), gov(threshold=1)
    engine = open_and_ok_engine(meter, governor)
    force_open(governor, "source_a")
    force_open(governor, "source_b", "https://b.example")
    result = lookups(engine, 1)[0]
    assert result.status is AggregateStatus.FAILED and result.metadata is None
    assert [r.error_kind for r in result.source_results] == [K.CIRCUIT_OPEN, K.CIRCUIT_OPEN]
    assert meter.requests["source_a"] == meter.requests["source_b"] == 0


def test_open_plus_not_found_is_failed_and_success_plus_not_found_is_still_success():
    meter, (governor, _) = Meter(), gov(threshold=1)
    engine = open_and_ok_engine(meter, governor, b_status=S.NOT_FOUND)
    force_open(governor, "source_a")
    assert lookups(engine, 1)[0].status is AggregateStatus.FAILED
    meter2, (governor2, _) = Meter(), gov(threshold=1)
    engine2 = open_and_ok_engine(meter2, governor2, a_status=S.NOT_FOUND, b_status=None)
    assert lookups(engine2, 1)[0].status is AggregateStatus.SUCCESS  # no operational failure: unchanged rule


# ---- adapter can never claim CIRCUIT_OPEN, and the trace model ----------------------------------------------------------------------


def test_an_adapter_returning_circuit_open_is_a_contract_violation():
    meter, (governor, _) = Meter(), gov(threshold=1)

    async def liar(number, client):
        return circuit_open_result("src")

    for use_governor in (governor, None):
        engine = make_engine([Spec("src", HOST, meter.wrap("src", "x.example", liar))], use_governor)
        result = lookups(engine, 1)[0]
        (source_result,) = result.source_results
        assert (source_result.status, source_result.error_kind) == (S.INVALID_RESPONSE, K.RESULT_CONTRACT_MISMATCH)
        assert result.source_execution_traces[0].attempt_count == 1
    assert breaker_of(governor).state is BreakerState.OPEN  # the fabricated answer was recorded as the failure it is


def attempt(status=S.NETWORK_ERROR, kind=K.CIRCUIT_OPEN):
    return SourceAttempt(sequence=1, status=status, error_kind=kind, elapsed_ms=1.0)


def test_a_trace_without_attempts_is_valid_only_for_a_circuit_open_final_result():
    circuit_open = circuit_open_result("src")
    trace = SourceExecutionTrace("src", (), circuit_open, max_attempts=2)
    assert (trace.attempt_count, trace.retried, trace.deadline_exceeded) == (0, False, False)
    with pytest.raises(AggregationContractError):
        SourceExecutionTrace("src", (), failed("src", S.NETWORK_ERROR, error_kind=K.TIMEOUT), max_attempts=2)
    with pytest.raises(AggregationContractError):
        SourceExecutionTrace("src", (), ok("src", N), max_attempts=2)
    with pytest.raises(AggregationContractError):  # a circuit-open answer with an attempt is a lie: no request was made
        SourceExecutionTrace("src", (attempt(),), circuit_open, max_attempts=2)
    with pytest.raises(AggregationContractError):
        SourceExecutionTrace("src", (), circuit_open, max_attempts=2, deadline_exceeded=True, deadline_during="attempt")
    with pytest.raises(AggregationContractError):
        SourceExecutionTrace("src", (), circuit_open, max_attempts=2, deadline_during="backoff")
    with pytest.raises(AggregationContractError):
        SourceExecutionTrace("src", [], circuit_open, max_attempts=2)  # type: ignore[arg-type]


def test_circuit_open_is_a_network_error_kind_in_the_frozen_relation():
    assert K.CIRCUIT_OPEN in ALLOWED_ERROR_KINDS[S.NETWORK_ERROR]
    assert status_for_error_kind(K.CIRCUIT_OPEN) is S.NETWORK_ERROR
    result = circuit_open_result("src")
    assert (result.status, result.error_kind, result.metadata, result.elapsed_ms) == (S.NETWORK_ERROR, K.CIRCUIT_OPEN, None, 0.0)
    assert "src" in result.error_detail and "http" not in result.error_detail.lower()
    with pytest.raises(Exception):
        SourceResult("src", S.BLOCKED, None, 0.0, K.CIRCUIT_OPEN, "x")  # only NETWORK_ERROR may carry it


# ---- argument validation ---------------------------------------------------------------------------------------------------------------


def test_execute_sources_traced_validates_the_governor_and_the_hosts_before_any_request():
    calls = []

    async def script(number, client):
        calls.append(number)
        return ok("src", number)

    with_host = make_target("src", HOST, script)
    from dataclasses import replace

    no_host = replace(with_host, host=None)
    governor, _ = gov()
    for bad_governor in (object(), "g", 5):
        with pytest.raises(AggregationConfigError):
            run(execute_sources_traced(N, [with_host], NullClient(), governor=bad_governor))  # type: ignore[arg-type]
    with pytest.raises(AggregationConfigError, match="host identity"):
        run(execute_sources_traced(N, [no_host], NullClient(), governor=governor))
    with pytest.raises(AggregationConfigError):
        replace(with_host, host="x.example:443")  # type: ignore[arg-type]
    assert calls == []
    # without a governor a host-less target is fine (C4 behaviour)
    (trace,) = run(execute_sources_traced(N, [no_host], NullClient()))
    assert trace.final_result.status is S.SUCCESS and calls == [N]
