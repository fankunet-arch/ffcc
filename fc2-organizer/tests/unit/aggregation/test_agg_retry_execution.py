"""Phase 3 C2: retry inside the execution boundary (scripted adapters, no network).

The behaviours frozen here (docs/specifications/PHASE3_RESILIENCE_CONTRACT.md):
source-local retry decided from the structured ``error_kind``; ``max_attempts`` counts all
attempts; deterministic backoff; the per-source wall-clock deadline covers attempts + backoff
+ retries and is never multiplied; attempts of one source are serial and hold one slot; only
the final result is merged; every attempt is inspectable in the trace.
"""

from __future__ import annotations

import asyncio
import dataclasses
import time

import pytest

from fc2_metadata_core.aggregation import (
    AggregateStatus,
    AggregationConfig,
    MultiSourceEngine,
    RetryPolicy,
    SourceAttempt,
    SourceConfig,
    SourceExecutionTrace,
    SourceTarget,
    execute_sources,
    execute_sources_traced,
)
from fc2_metadata_core.models.metadata import NormalizedMetadata
from fc2_metadata_core.models.source_result import (
    SourceErrorKind,
    SourceResult,
    SourceStatus,
    status_for_error_kind,
)
from fc2_metadata_core.sources import SourceRegistry

from support.fake_http_client import FakeHttpClient
from support.scripted_adapters import failed, ok, scripted_adapter_class

N = "FC2-4979299"
CLIENT = object()
K = SourceErrorKind
S = SourceStatus
FAST = RetryPolicy(max_attempts=2, initial_backoff_seconds=0.01)


def run(coro):
    return asyncio.run(coro)


def fail_kind(source_id, kind, **kw):
    return failed(source_id, status_for_error_kind(kind), error_kind=kind, **kw)


class Script:
    """Scripted adapter behaviour: successive outcomes (SourceResult / Exception), last repeats."""

    def __init__(self, source_id, outcomes, *, delay=0.0):
        self.source_id = source_id
        self.outcomes = list(outcomes)
        self.delay = delay
        self.calls: list[tuple[str, object]] = []
        self.active = 0
        self.peak_active = 0

    async def __call__(self, number, client):
        self.calls.append((number, client))
        self.active += 1
        self.peak_active = max(self.peak_active, self.active)
        try:
            if self.delay:
                await asyncio.sleep(self.delay)
            outcome = self.outcomes.pop(0) if len(self.outcomes) > 1 else self.outcomes[0]
        finally:
            self.active -= 1
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


def target(script, *, deadline=20.0, retry=FAST):
    adapter = scripted_adapter_class(script.source_id, script)()
    return SourceTarget(SourceConfig(script.source_id, deadline_seconds=deadline), adapter, retry)


def one(script, **kw):
    (trace,) = run(execute_sources_traced(N, [target(script, **kw)], CLIENT))
    return trace


# ---- decision matrix (24) -----------------------------------------------------------------------------------------------


NON_RETRYABLE_OUTCOMES = {
    "SUCCESS": lambda sid: ok(sid, N, "T"),
    "NOT_FOUND": lambda sid: failed(sid, S.NOT_FOUND),
    "BLOCKED": lambda sid: failed(sid, S.BLOCKED),
    "RATE_LIMITED": lambda sid: failed(sid, S.RATE_LIMITED),
    "PARSE_ERROR": lambda sid: failed(sid, S.PARSE_ERROR),
    "INVALID_RESPONSE(generic)": lambda sid: failed(sid, S.INVALID_RESPONSE),
    "RESPONSE_TOO_LARGE": lambda sid: fail_kind(sid, K.RESPONSE_TOO_LARGE),
    "REDIRECT_ERROR": lambda sid: fail_kind(sid, K.REDIRECT_ERROR),
    "ADAPTER_EXCEPTION": lambda sid: fail_kind(sid, K.ADAPTER_EXCEPTION),
    "RESULT_CONTRACT_MISMATCH": lambda sid: fail_kind(sid, K.RESULT_CONTRACT_MISMATCH),
    "SOURCE_DEADLINE": lambda sid: fail_kind(sid, K.SOURCE_DEADLINE),
}


@pytest.mark.parametrize("name", list(NON_RETRYABLE_OUTCOMES))
def test_non_retryable_outcomes_make_exactly_one_attempt(name):
    script = Script("a", [NON_RETRYABLE_OUTCOMES[name]("a")])
    trace = one(script)
    assert trace.attempt_count == 1 and len(script.calls) == 1
    assert not trace.retried and not trace.deadline_exceeded
    expected = NON_RETRYABLE_OUTCOMES[name]("a")
    assert (trace.final_result.status, trace.final_result.error_kind) == (expected.status, expected.error_kind)


RETRYABLE_KINDS = [
    ("TIMEOUT", K.TIMEOUT),
    ("CONNECTION_ERROR", K.CONNECTION_ERROR),
    ("DECODE_ERROR", K.DECODE_ERROR),
    ("HTTP_SERVER_ERROR", K.HTTP_SERVER_ERROR),
    ("generic NETWORK_ERROR", K.NETWORK_ERROR),
]


@pytest.mark.parametrize("name, kind", RETRYABLE_KINDS, ids=[n for n, _ in RETRYABLE_KINDS])
def test_a_retryable_failure_then_success_takes_exactly_two_attempts(name, kind):
    script = Script("a", [fail_kind("a", kind), ok("a", N, "recovered")])
    trace = one(script)
    assert trace.attempt_count == 2 and len(script.calls) == 2
    assert trace.final_result.status is S.SUCCESS and trace.final_result.metadata.title == "recovered"
    first, second = trace.attempts
    assert (first.sequence, first.status, first.error_kind, first.backoff_before_seconds) == (1, status_for_error_kind(kind), kind, 0.0)
    assert (second.sequence, second.status, second.error_kind) == (2, S.SUCCESS, None)
    assert second.backoff_before_seconds == FAST.backoff_before_attempt(2) == 0.01
    assert trace.retried and all(a.completed for a in trace.attempts)


@pytest.mark.parametrize("name, kind", RETRYABLE_KINDS, ids=[n for n, _ in RETRYABLE_KINDS])
def test_two_retryable_failures_with_max_attempts_2_stop_at_exactly_two_attempts(name, kind):
    script = Script("a", [fail_kind("a", kind, detail="a: first"), fail_kind("a", kind, detail="a: second"), ok("a", N, "never reached")])
    trace = one(script)
    assert trace.attempt_count == 2 and len(script.calls) == 2, "a third attempt must never happen"
    assert trace.final_result.status is status_for_error_kind(kind) and "second" in trace.final_result.error_detail


def test_max_attempts_counts_all_attempts_not_retries():
    assert RetryPolicy().max_attempts == 2  # 1 try + at most 1 retry, NOT 1 + 2
    one_try = one(Script("a", [fail_kind("a", K.TIMEOUT), ok("a", N)]), retry=RetryPolicy.no_retry())
    assert one_try.attempt_count == 1 and one_try.final_result.status is S.NETWORK_ERROR


def test_max_attempts_3_uses_growing_deterministic_backoffs_and_stops_at_three():
    policy = RetryPolicy(max_attempts=3, initial_backoff_seconds=0.01, backoff_multiplier=3.0, max_backoff_seconds=1.0)
    script = Script("a", [fail_kind("a", K.TIMEOUT)])
    trace = one(script, retry=policy)
    assert trace.attempt_count == 3 and len(script.calls) == 3
    assert [a.backoff_before_seconds for a in trace.attempts] == [0.0, 0.01, 0.03]


def test_a_non_retryable_failure_after_a_retryable_one_ends_the_sequence():
    script = Script("a", [fail_kind("a", K.TIMEOUT), failed("a", S.PARSE_ERROR), ok("a", N)])
    trace = one(script, retry=RetryPolicy(max_attempts=5, initial_backoff_seconds=0.001))
    assert trace.attempt_count == 2 and trace.final_result.status is S.PARSE_ERROR


def test_a_narrowed_policy_stops_retrying_kinds_it_no_longer_lists():
    policy = RetryPolicy(initial_backoff_seconds=0.001, retryable_error_kinds=frozenset({K.HTTP_SERVER_ERROR}))
    assert one(Script("a", [fail_kind("a", K.TIMEOUT), ok("a", N)]), retry=policy).attempt_count == 1
    assert one(Script("a", [fail_kind("a", K.HTTP_SERVER_ERROR), ok("a", N)]), retry=policy).attempt_count == 2


def test_each_attempt_gets_the_same_number_and_the_same_shared_client():
    script = Script("a", [fail_kind("a", K.TIMEOUT), ok("a", N)])
    one(script)
    assert [c for c in script.calls] == [(N, CLIENT), (N, CLIENT)]


@pytest.mark.parametrize(
    "outcomes, expected_kind",
    [([RuntimeError("x"), ok("a", N)], K.ADAPTER_EXCEPTION), ([None, ok("a", N)], K.RESULT_CONTRACT_MISMATCH)],
    ids=["adapter-raises", "adapter-returns-junk"],
)
def test_adapter_exceptions_and_junk_returns_are_never_retried(outcomes, expected_kind):
    script = Script("a", outcomes)
    trace = one(script)
    assert trace.attempt_count == 1 and len(script.calls) == 1
    assert trace.final_result.status is S.INVALID_RESPONSE and trace.final_result.error_kind is expected_kind


def test_a_retry_is_source_local_it_never_reruns_another_source():
    flaky = Script("flaky", [fail_kind("flaky", K.TIMEOUT), ok("flaky", N, "T")])
    steady = Script("steady", [ok("steady", N, "S")])
    traces = run(execute_sources_traced(N, [target(flaky), target(steady)], CLIENT))
    assert [t.attempt_count for t in traces] == [2, 1]
    assert len(flaky.calls) == 2 and len(steady.calls) == 1


def test_per_source_policy_override_in_one_run():
    a = Script("a", [fail_kind("a", K.TIMEOUT), ok("a", N)])
    b = Script("b", [fail_kind("b", K.TIMEOUT), ok("b", N)])
    traces = run(execute_sources_traced(N, [target(a, retry=RetryPolicy.no_retry()), target(b, retry=FAST)], CLIENT))
    assert [t.attempt_count for t in traces] == [1, 2]


# ---- deadline is TOTAL and is never multiplied by retries (17, 18) --------------------------------------------------------


def test_17_total_deadline_covers_attempt_backoff_and_retry_not_deadline_times_attempts():
    """deadline 0.30 s; attempt 1 = 0.15 s retryable failure; backoff 0.10 s; attempt 2 would
    hang. The source must end at ~0.30 s, not ~0.55 s (0.30 + a fresh 0.30 for the retry)."""
    outcomes = iter([True])

    async def script(number, client):
        if next(outcomes, False):
            await asyncio.sleep(0.15)
            return fail_kind("a", K.TIMEOUT)
        await asyncio.Event().wait()

    policy = RetryPolicy(max_attempts=2, initial_backoff_seconds=0.10)
    tgt = SourceTarget(SourceConfig("a", deadline_seconds=0.30), scripted_adapter_class("a", script)(), policy)
    started = time.monotonic()
    (trace,) = run(execute_sources_traced(N, [tgt], CLIENT))
    wall = time.monotonic() - started
    assert 0.27 <= wall < 0.45, f"total deadline must cut the source at ~0.30 s, took {wall:.3f}s"
    assert trace.deadline_exceeded and trace.deadline_during == "attempt"
    assert trace.final_result.status is S.NETWORK_ERROR and trace.final_result.error_kind is K.SOURCE_DEADLINE
    assert 250 <= trace.final_result.elapsed_ms < 450
    assert trace.attempt_count == 2
    assert trace.attempts[0].completed and not trace.attempts[1].completed
    assert trace.attempts[1].error_kind is K.SOURCE_DEADLINE and trace.attempts[1].backoff_before_seconds == pytest.approx(0.10)
    assert trace.attempts[1].elapsed_ms < 150  # started at ~0.25 s, cut at ~0.30 s


def test_18_backoff_counts_against_the_deadline_and_the_next_attempt_never_starts():
    script = Script("a", [fail_kind("a", K.TIMEOUT), ok("a", N)])
    policy = RetryPolicy(max_attempts=2, initial_backoff_seconds=2.0, max_backoff_seconds=2.0)
    started = time.monotonic()
    trace = one(script, deadline=0.25, retry=policy)
    wall = time.monotonic() - started
    assert wall < 1.0, "the deadline must cut the 2 s backoff"
    assert trace.deadline_exceeded and trace.deadline_during == "backoff"
    assert trace.final_result.error_kind is K.SOURCE_DEADLINE and trace.final_result.status is S.NETWORK_ERROR
    assert trace.attempt_count == 1 and len(script.calls) == 1, "attempt 2 must never start"
    assert trace.attempts[0].completed and trace.attempts[0].status is S.NETWORK_ERROR


def test_deadline_A_exhausted_inside_attempt_1_means_one_attempt_and_no_retry():
    async def hang(number, client):
        await asyncio.Event().wait()

    calls = []

    async def counting_hang(number, client):
        calls.append(1)
        await hang(number, client)

    tgt = SourceTarget(SourceConfig("a", deadline_seconds=0.15), scripted_adapter_class("a", counting_hang)(), FAST)
    started = time.monotonic()
    (trace,) = run(execute_sources_traced(N, [tgt], CLIENT))
    assert time.monotonic() - started < 0.6
    assert calls == [1], "a deadline that expires during attempt 1 must not start attempt 2"
    assert trace.attempt_count == 1 and trace.deadline_exceeded and trace.deadline_during == "attempt"
    only = trace.attempts[0]
    assert (only.sequence, only.status, only.error_kind, only.completed) == (1, S.NETWORK_ERROR, K.SOURCE_DEADLINE, False)
    assert trace.final_result.status is S.NETWORK_ERROR and trace.final_result.error_kind is K.SOURCE_DEADLINE


def test_deadline_D_time_spent_queued_for_a_concurrency_slot_is_not_charged_to_the_source():
    """max_concurrency=1: 'second' waits ~0.3 s behind 'first', then needs ~0.10 s of its own
    (attempt, backoff, attempt) inside a 0.20 s deadline. Queue time must not count."""
    slow = Script("first", [ok("first", N, "F")], delay=0.3)
    tight = Script("second", [fail_kind("second", K.TIMEOUT), ok("second", N, "S")], delay=0.03)
    tight_policy = RetryPolicy(max_attempts=2, initial_backoff_seconds=0.03)
    first_trace, second_trace = run(
        execute_sources_traced(
            N,
            [target(slow, deadline=5.0), target(tight, deadline=0.20, retry=tight_policy)],
            CLIENT,
            max_concurrency=1,
        )
    )
    assert first_trace.final_result.status is S.SUCCESS
    assert not second_trace.deadline_exceeded, "queue time was wrongly charged to the source deadline"
    assert second_trace.attempt_count == 2 and second_trace.final_result.status is S.SUCCESS


def test_a_generous_deadline_does_not_hide_a_retry():
    trace = one(Script("a", [fail_kind("a", K.TIMEOUT), ok("a", N)]), deadline=5.0)
    assert not trace.deadline_exceeded and trace.final_result.status is S.SUCCESS and trace.attempt_count == 2


def test_the_deadline_is_not_multiplied_by_max_attempts():
    """5 attempts of 0.1 s each with no backoff would take 0.5 s; deadline 0.25 s must win."""
    script = Script("a", [fail_kind("a", K.TIMEOUT)], delay=0.1)
    policy = RetryPolicy(max_attempts=5, initial_backoff_seconds=0.0)
    started = time.monotonic()
    trace = one(script, deadline=0.25, retry=policy)
    assert time.monotonic() - started < 0.45
    assert trace.deadline_exceeded and trace.attempt_count <= 3
    assert trace.final_result.error_kind is K.SOURCE_DEADLINE


def test_deadline_result_does_not_get_retried_and_other_sources_are_unaffected():
    async def hang(number, client):
        await asyncio.Event().wait()

    stuck = SourceTarget(SourceConfig("stuck", deadline_seconds=0.1), scripted_adapter_class("stuck", hang)(), FAST)
    good = Script("good", [ok("good", N, "G")])
    started = time.monotonic()
    stuck_trace, good_trace = run(execute_sources_traced(N, [stuck, target(good)], CLIENT))
    assert time.monotonic() - started < 0.6
    assert stuck_trace.attempt_count == 1 and stuck_trace.final_result.error_kind is K.SOURCE_DEADLINE
    assert good_trace.final_result.status is S.SUCCESS


# ---- concurrency + retry -----------------------------------------------------------------------------------------------------


def test_a_sources_attempts_are_strictly_serial_and_never_overlap():
    script = Script("a", [fail_kind("a", K.TIMEOUT), fail_kind("a", K.TIMEOUT), ok("a", N)], delay=0.03)
    trace = one(script, retry=RetryPolicy(max_attempts=3, initial_backoff_seconds=0.005))
    assert trace.attempt_count == 3 and script.peak_active == 1


@pytest.mark.parametrize("limit", [1, 2, 3])
def test_peak_active_adapter_fetches_never_exceed_max_concurrency_even_with_retries(limit):
    active = 0
    peak = 0
    per_source_peak: dict[str, int] = {}
    per_source_active: dict[str, int] = {}

    def make(source_id):
        outcomes = [fail_kind(source_id, K.HTTP_SERVER_ERROR), ok(source_id, N, source_id)]

        async def script(number, client):
            nonlocal active, peak
            active += 1
            peak = max(peak, active)
            per_source_active[source_id] = per_source_active.get(source_id, 0) + 1
            per_source_peak[source_id] = max(per_source_peak.get(source_id, 0), per_source_active[source_id])
            try:
                await asyncio.sleep(0.04)
            finally:
                active -= 1
                per_source_active[source_id] -= 1
            return outcomes.pop(0) if len(outcomes) > 1 else outcomes[0]

        return script

    ids = [f"s{i}" for i in range(5)]
    targets = [
        SourceTarget(SourceConfig(sid), scripted_adapter_class(sid, make(sid))(), RetryPolicy(max_attempts=2, initial_backoff_seconds=0.02))
        for sid in ids
    ]
    traces = run(execute_sources_traced(N, targets, CLIENT, max_concurrency=limit))
    assert [t.attempt_count for t in traces] == [2] * 5 and all(t.final_result.status is S.SUCCESS for t in traces)
    assert peak <= limit, f"{peak} concurrent adapter fetches with max_concurrency={limit} (retries must not add concurrency)"
    assert peak == limit, "the run was not parallel up to the limit"
    assert all(v == 1 for v in per_source_peak.values()), "a single source had two attempts at once"


def test_three_sources_that_each_retry_never_produce_four_concurrent_fetches():
    active = peak = 0

    def make(sid):
        outcomes = [fail_kind(sid, K.TIMEOUT), ok(sid, N, sid)]

        async def script(number, client):
            nonlocal active, peak
            active += 1
            peak = max(peak, active)
            try:
                await asyncio.sleep(0.03)
            finally:
                active -= 1
            return outcomes.pop(0) if len(outcomes) > 1 else outcomes[0]

        return script

    targets = [SourceTarget(SourceConfig(s), scripted_adapter_class(s, make(s))(), FAST) for s in ("a", "b", "c")]
    run(execute_sources_traced(N, targets, CLIENT, max_concurrency=3))
    assert peak == 3


# ---- attempt diagnostics ---------------------------------------------------------------------------------------------------------


def test_engine_observed_attempt_elapsed_is_real_even_when_the_result_says_zero():
    """P2-R-07: a SourceResult may carry elapsed_ms=0.0; the trace records what the engine saw."""
    script = Script("a", [failed("a", S.NETWORK_ERROR, elapsed_ms=0.0, error_kind=K.TIMEOUT), ok("a", N, elapsed_ms=0.0)], delay=0.05)
    trace = one(script)
    assert all(a.elapsed_ms >= 40 for a in trace.attempts)
    assert trace.attempts[0].elapsed_ms < 500
    assert trace.final_result.elapsed_ms == 0.0  # the SourceResult itself is unchanged (not "fixed" here)


def test_traces_are_immutable_and_hold_only_status_kind_and_timings():
    trace = one(Script("a", [fail_kind("a", K.TIMEOUT), ok("a", N)]))
    assert {f.name for f in dataclasses.fields(SourceAttempt)} == {
        "sequence", "status", "error_kind", "elapsed_ms", "completed", "backoff_before_seconds",
    }
    assert {f.name for f in dataclasses.fields(SourceExecutionTrace)} == {
        "source_id", "attempts", "final_result", "max_attempts", "deadline_exceeded", "deadline_during",
    }
    with pytest.raises(dataclasses.FrozenInstanceError):
        trace.attempts[0].status = S.SUCCESS  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        trace.final_result = None  # type: ignore[misc]
    assert isinstance(trace.attempts, tuple)


def test_trace_order_is_deterministic_config_order_whatever_the_completion_order():
    async def make(delay, sid):
        async def script(number, client):
            await asyncio.sleep(delay)
            return ok(sid, number, sid)

        return script

    async def scenario():
        targets = [
            SourceTarget(SourceConfig(sid), scripted_adapter_class(sid, await make(delay, sid))(), FAST)
            for sid, delay in (("a", 0.09), ("b", 0.03), ("c", 0.0))
        ]
        return await execute_sources_traced(N, targets, CLIENT)

    assert [t.source_id for t in run(scenario())] == ["a", "b", "c"]


def test_execute_sources_is_the_final_results_of_the_traced_run():
    script = Script("a", [fail_kind("a", K.TIMEOUT), ok("a", N, "final")])
    (result,) = run(execute_sources(N, [target(script)], CLIENT))
    assert result.status is S.SUCCESS and result.metadata.title == "final"


# ---- aggregate semantics use the FINAL result only (31, 32) --------------------------------------------------------------------------


def engine_for(scripts, *, retry=FAST, extra=None):
    registry = SourceRegistry()
    for sid, script in scripts.items():
        registry.register(sid, scripted_adapter_class(sid, script))
    config = AggregationConfig.create([SourceConfig(sid) for sid in scripts], retry_policy=retry, **(extra or {}))
    return MultiSourceEngine(config, registry, FakeHttpClient())


def test_31_a_source_that_recovers_on_retry_does_not_make_the_aggregate_partial():
    engine = engine_for({
        "a": Script("a", [fail_kind("a", K.TIMEOUT), ok("a", N, "A after retry")]),
        "b": Script("b", [ok("b", N, "B")]),
    })
    result = run(engine.aggregate(N))
    assert result.status is AggregateStatus.SUCCESS
    assert result.contributing_source_ids == ("a", "b") and result.metadata.title == "A after retry"
    trace = result.trace_for("a")
    assert trace.attempt_count == 2 and trace.attempts[0].error_kind is K.TIMEOUT and trace.attempts[0].status is S.NETWORK_ERROR
    assert result.trace_for("b").attempt_count == 1


def test_31b_two_failed_attempts_plus_a_healthy_source_is_partial():
    engine = engine_for({
        "a": Script("a", [fail_kind("a", K.HTTP_SERVER_ERROR)]),
        "b": Script("b", [ok("b", N, "B")]),
    })
    result = run(engine.aggregate(N))
    assert result.status is AggregateStatus.PARTIAL and result.metadata.title == "B"
    assert result.trace_for("a").attempt_count == 2
    assert result.result_for("a").error_kind is K.HTTP_SERVER_ERROR


def test_a_not_found_source_is_asked_once_and_stays_a_coverage_gap():
    nf = Script("nf", [failed("nf", S.NOT_FOUND)])
    engine = engine_for({"nf": nf, "b": Script("b", [ok("b", N, "B")])})
    result = run(engine.aggregate(N))
    assert result.status is AggregateStatus.SUCCESS and result.trace_for("nf").attempt_count == 1 and len(nf.calls) == 1


def test_a_blocked_or_rate_limited_source_is_never_hit_again():
    for status in (S.BLOCKED, S.RATE_LIMITED):
        script = Script("x", [failed("x", status), ok("x", N)])
        result = run(engine_for({"x": script, "b": Script("b", [ok("b", N, "B")])}).aggregate(N))
        assert len(script.calls) == 1 and result.status is AggregateStatus.PARTIAL


def test_32_failed_attempts_partial_data_and_wrong_numbers_cannot_reach_the_aggregate():
    evil_partial = NormalizedMetadata(number=N, tags=("EVIL-TAG",), actors=("EVIL-ACTOR",), external_ids={"evil": "1"})
    attempt1 = SourceResult(
        source_id="a", status=S.INVALID_RESPONSE, metadata=evil_partial, elapsed_ms=1.0,
        error_kind=K.HTTP_SERVER_ERROR, error_detail="a: server error carrying partial data",
    )
    engine = engine_for({
        "a": Script("a", [attempt1, ok("a", N, "Clean title", tags=("clean",))]),
        "b": Script("b", [ok("b", N, "B")]),
    })
    result = run(engine.aggregate(N))
    assert result.status is AggregateStatus.SUCCESS and result.trace_for("a").attempt_count == 2
    md = result.metadata
    assert md.tags == ("clean",) and md.actors == () and "evil" not in dict(md.external_ids)
    assert all("EVIL" not in str(v) for v in (md.tags, md.actors))


def test_32b_a_retry_that_returns_another_films_data_is_failed_closed_not_merged():
    engine = engine_for({
        "a": Script("a", [fail_kind("a", K.TIMEOUT), ok("a", "FC2-1111111", "A DIFFERENT FILM", tags=("evil",))]),
        "b": Script("b", [ok("b", N, "B")]),
    })
    result = run(engine.aggregate(N))
    a = result.result_for("a")
    assert a.status is S.INVALID_RESPONSE and a.error_kind is K.RESULT_CONTRACT_MISMATCH
    assert result.metadata.title == "B" and result.metadata.tags == ()
    assert result.trace_for("a").attempt_count == 2 and result.status is AggregateStatus.PARTIAL


def test_32c_a_retry_returning_the_wrong_source_id_is_failed_closed():
    engine = engine_for({
        "a": Script("a", [fail_kind("a", K.TIMEOUT), ok("someone_else", N, "stolen")]),
        "b": Script("b", [ok("b", N, "B")]),
    })
    result = run(engine.aggregate(N))
    assert result.result_for("a").error_kind is K.RESULT_CONTRACT_MISMATCH and result.metadata.title == "B"


def test_engine_aggregate_exposes_one_trace_per_enabled_source_in_config_order_and_none_for_disabled():
    registry = SourceRegistry()
    for sid in ("a", "b", "off"):
        registry.register(sid, scripted_adapter_class(sid, Script(sid, [ok(sid, N, sid)])))
    config = AggregationConfig.create([SourceConfig("a"), SourceConfig("off", enabled=False), SourceConfig("b")], retry_policy=FAST)
    result = run(MultiSourceEngine(config, registry, FakeHttpClient()).aggregate(N))
    assert [t.source_id for t in result.source_execution_traces] == ["a", "b"] == list(result.source_order)
    assert result.trace_for("off") is None and result.disabled_source_ids == ("off",)


def test_a_failed_aggregate_keeps_every_trace_and_result():
    engine = engine_for({
        "a": Script("a", [fail_kind("a", K.CONNECTION_ERROR)]),
        "b": Script("b", [failed("b", S.NOT_FOUND)]),
    })
    result = run(engine.aggregate(N))
    assert result.status is AggregateStatus.FAILED and result.metadata is None
    assert [t.attempt_count for t in result.source_execution_traces] == [2, 1]
    assert [t.final_result for t in result.source_execution_traces] == list(result.source_results)


def test_the_engine_uses_the_per_source_policy_from_configuration_data():
    a = Script("a", [fail_kind("a", K.TIMEOUT), ok("a", N)])
    b = Script("b", [fail_kind("b", K.TIMEOUT), ok("b", N)])
    registry = SourceRegistry()
    registry.register("a", scripted_adapter_class("a", a))
    registry.register("b", scripted_adapter_class("b", b))
    config = AggregationConfig.create(
        [SourceConfig("a", retry_policy=RetryPolicy.no_retry()), SourceConfig("b")], retry_policy=FAST
    )
    result = run(MultiSourceEngine(config, registry, FakeHttpClient()).aggregate(N))
    assert (result.trace_for("a").attempt_count, result.trace_for("b").attempt_count) == (1, 2)
