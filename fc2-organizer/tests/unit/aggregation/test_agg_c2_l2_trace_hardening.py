"""C2-L2 closure (P4-C3): the public ``SourceAttempt`` / ``SourceExecutionTrace`` models reject
engine-impossible states (docs/specifications/PHASE4_PUBLICATION_BOUNDARY_CONTRACT.md, section 14).

History: C2 review found the trace model accepted states ``execution.py`` never produces; C3/C4 carried it as
C2-L2 LOW/OPEN, and the C4-R1 batch contract made it an entry gate for any layer that exposes traces. The four
named states -- incomplete SUCCESS attempt, incomplete attempt that is not ``NETWORK_ERROR``/``SOURCE_DEADLINE``,
retry after ``NOT_FOUND``, deadline "during backoff" after a ``SUCCESS`` -- are now construction errors, and
everything the real engine produces is still accepted (checked against the real engine below).
"""

from __future__ import annotations

import asyncio

import pytest

import fc2_metadata_core.aggregation.models as models_module
from fc2_metadata_core.aggregation import (
    AggregationContractError,
    RetryPolicy,
    SourceAttempt,
    SourceConfig,
    SourceExecutionTrace,
    SourceTarget,
    execute_sources_traced,
)
from fc2_metadata_core.aggregation.retry import RETRY_ELIGIBLE_KINDS
from fc2_metadata_core.models.source_result import (
    ALLOWED_ERROR_KINDS,
    SourceErrorKind,
    SourceStatus,
    status_for_error_kind,
)
from fc2_metadata_core.resource_control import (
    CircuitBreakerPolicy,
    HostLimitPolicy,
    SourceResourceGovernor,
    circuit_open_result,
)

from support.resource_fakes import FakeClock, NullClient, make_target
from support.scripted_adapters import failed, ok, scripted_adapter_class

K = SourceErrorKind
S = SourceStatus
N = "FC2-4979299"

NON_RETRY_ELIGIBLE_KINDS = sorted(
    (k for k in SourceErrorKind if k not in RETRY_ELIGIBLE_KINDS), key=lambda k: k.value
)
EVERY_FAILURE_PAIR = sorted(
    ((status, kind) for status, kinds in ALLOWED_ERROR_KINDS.items() for kind in kinds),
    key=lambda p: (p[0].value, p[1].value),
)


def deadline_result(source_id="a"):
    return failed(source_id, S.NETWORK_ERROR, error_kind=K.SOURCE_DEADLINE)


def kind_result(kind, source_id="a"):
    return failed(source_id, status_for_error_kind(kind), error_kind=kind)


def attempt(seq, status, kind, *, completed=True):
    """An attempt with the engine's backoff shape (none before attempt 1)."""
    return SourceAttempt(seq, status, kind, 5.0, completed=completed, backoff_before_seconds=0.0 if seq == 1 else 1.0)


def attempt_like(seq, result, **kw):
    return attempt(seq, result.status, result.error_kind, **kw)


# ======================================================================================================================
# (1) + (2): incomplete attempts -- SourceAttempt level
# ======================================================================================================================


def test_21_an_incomplete_success_attempt_is_rejected():
    with pytest.raises(AggregationContractError, match="incomplete attempt"):
        SourceAttempt(1, S.SUCCESS, None, 5.0, completed=False)


@pytest.mark.parametrize(
    ("status", "kind"),
    [p for p in EVERY_FAILURE_PAIR if p != (S.NETWORK_ERROR, K.SOURCE_DEADLINE)],
    ids=lambda v: v.value,
)
def test_22_an_incomplete_attempt_that_is_not_network_error_source_deadline_is_rejected(status, kind):
    with pytest.raises(AggregationContractError, match="incomplete attempt"):
        SourceAttempt(1, status, kind, 5.0, completed=False)


@pytest.mark.parametrize(("status", "kind"), [(S.PARSE_ERROR, K.PARSE_ERROR), (S.NOT_FOUND, K.NOT_FOUND),
                                              (S.NETWORK_ERROR, K.CONNECTION_ERROR)], ids=lambda v: v.value)
def test_22_the_briefs_named_incomplete_examples_are_rejected(status, kind):
    with pytest.raises(AggregationContractError):
        SourceAttempt(1, status, kind, 5.0, completed=False)


def test_the_only_incomplete_attempt_shape_is_network_error_source_deadline():
    cut = SourceAttempt(2, S.NETWORK_ERROR, K.SOURCE_DEADLINE, 5.0, completed=False, backoff_before_seconds=1.0)
    assert not cut.completed


def test_a_completed_attempt_of_any_allowed_status_kind_pair_is_still_accepted():
    """Not over-tightened: completed attempts keep the pre-C2-L2 rules (any allowed pair)."""
    SourceAttempt(1, S.SUCCESS, None, 5.0)
    for status, kind in EVERY_FAILURE_PAIR:
        SourceAttempt(1, status, kind, 5.0)


# ======================================================================================================================
# (3): no attempt after a non-retry-eligible outcome -- SourceExecutionTrace level
# ======================================================================================================================


def test_23_retry_after_not_found_is_rejected():
    final = kind_result(K.TIMEOUT)
    attempts = (attempt(1, S.NOT_FOUND, K.NOT_FOUND), attempt_like(2, final))
    with pytest.raises(AggregationContractError, match="retry-eligible"):
        SourceExecutionTrace("a", attempts, final, max_attempts=2)


def test_23_retry_after_not_found_then_success_is_rejected():
    final = ok("a", N)
    attempts = (attempt(1, S.NOT_FOUND, K.NOT_FOUND), attempt_like(2, final))
    with pytest.raises(AggregationContractError):
        SourceExecutionTrace("a", attempts, final, max_attempts=2)


@pytest.mark.parametrize("kind", NON_RETRY_ELIGIBLE_KINDS, ids=lambda k: k.value)
def test_no_attempt_may_follow_any_non_retry_eligible_failure(kind):
    final = kind_result(K.TIMEOUT)
    attempts = (attempt(1, status_for_error_kind(kind), kind), attempt_like(2, final))
    with pytest.raises(AggregationContractError):
        SourceExecutionTrace("a", attempts, final, max_attempts=3)


def test_a_non_eligible_failure_in_the_middle_of_a_longer_trace_is_rejected():
    final = kind_result(K.TIMEOUT)
    attempts = (attempt(1, S.NETWORK_ERROR, K.TIMEOUT), attempt(2, S.BLOCKED, K.BLOCKED), attempt_like(3, final))
    with pytest.raises(AggregationContractError):
        SourceExecutionTrace("a", attempts, final, max_attempts=3)


def test_no_attempt_may_follow_a_success_still_holds():
    final = kind_result(K.TIMEOUT)
    with pytest.raises(AggregationContractError):
        SourceExecutionTrace("a", (attempt(1, S.SUCCESS, None), attempt_like(2, final)), final, max_attempts=2)


def test_the_retry_after_not_found_shape_is_also_rejected_when_the_deadline_cut_attempt_2():
    attempts = (attempt(1, S.NOT_FOUND, K.NOT_FOUND), attempt(2, S.NETWORK_ERROR, K.SOURCE_DEADLINE, completed=False))
    with pytest.raises(AggregationContractError):
        SourceExecutionTrace("a", attempts, deadline_result(), max_attempts=2, deadline_exceeded=True, deadline_during="attempt")


# ======================================================================================================================
# (4): no backoff after a non-retry-eligible outcome
# ======================================================================================================================


def test_24_deadline_during_backoff_after_success_is_rejected():
    with pytest.raises(AggregationContractError, match="backoff"):
        SourceExecutionTrace(
            "a", (attempt(1, S.SUCCESS, None),), deadline_result(), max_attempts=2,
            deadline_exceeded=True, deadline_during="backoff",
        )


@pytest.mark.parametrize("kind", NON_RETRY_ELIGIBLE_KINDS, ids=lambda k: k.value)
def test_deadline_during_backoff_after_any_non_retry_eligible_failure_is_rejected(kind):
    with pytest.raises(AggregationContractError):
        SourceExecutionTrace(
            "a", (attempt(1, status_for_error_kind(kind), kind),), deadline_result(), max_attempts=2,
            deadline_exceeded=True, deadline_during="backoff",
        )


# ======================================================================================================================
# 25-28: legal engine shapes, built directly
# ======================================================================================================================


def test_25_deadline_during_attempt_1_is_accepted():
    trace = SourceExecutionTrace(
        "a", (attempt(1, S.NETWORK_ERROR, K.SOURCE_DEADLINE, completed=False),), deadline_result(), max_attempts=2,
        deadline_exceeded=True, deadline_during="attempt",
    )
    assert trace.attempt_count == 1 and not trace.attempts[0].completed


@pytest.mark.parametrize("kind", sorted(RETRY_ELIGIBLE_KINDS, key=lambda k: k.value), ids=lambda k: k.value)
def test_25_deadline_during_a_retry_attempt_is_accepted(kind):
    attempts = (attempt(1, status_for_error_kind(kind), kind), attempt(2, S.NETWORK_ERROR, K.SOURCE_DEADLINE, completed=False))
    trace = SourceExecutionTrace(
        "a", attempts, deadline_result(), max_attempts=2, deadline_exceeded=True, deadline_during="attempt"
    )
    assert trace.retried


@pytest.mark.parametrize("kind", sorted(RETRY_ELIGIBLE_KINDS, key=lambda k: k.value), ids=lambda k: k.value)
def test_26_deadline_during_backoff_after_a_retry_eligible_failure_is_accepted(kind):
    trace = SourceExecutionTrace(
        "a", (attempt(1, status_for_error_kind(kind), kind),), deadline_result(), max_attempts=2,
        deadline_exceeded=True, deadline_during="backoff",
    )
    assert trace.attempt_count == 1


def test_27_circuit_open_with_zero_attempts_is_still_accepted():
    trace = SourceExecutionTrace("a", (), circuit_open_result("a"), max_attempts=2)
    assert trace.attempt_count == 0 and trace.attempts == ()


@pytest.mark.parametrize("kind", sorted(RETRY_ELIGIBLE_KINDS, key=lambda k: k.value), ids=lambda k: k.value)
def test_28_retryable_failure_then_success_is_accepted(kind):
    final = ok("a", N)
    trace = SourceExecutionTrace("a", (attempt(1, status_for_error_kind(kind), kind), attempt_like(2, final)), final, max_attempts=2)
    assert trace.retried


@pytest.mark.parametrize("final_kind", [K.TIMEOUT, K.NOT_FOUND, K.BLOCKED, K.PARSE_ERROR], ids=lambda k: k.value)
def test_retryable_failure_then_final_failure_of_any_kind_is_accepted(final_kind):
    final = kind_result(final_kind)
    trace = SourceExecutionTrace("a", (attempt(1, S.NETWORK_ERROR, K.CONNECTION_ERROR), attempt_like(2, final)), final, max_attempts=2)
    assert trace.retried


def test_three_attempt_retry_chain_is_accepted():
    final = ok("a", N)
    attempts = (attempt(1, S.NETWORK_ERROR, K.TIMEOUT), attempt(2, status_for_error_kind(K.DECODE_ERROR), K.DECODE_ERROR), attempt_like(3, final))
    SourceExecutionTrace("a", attempts, final, max_attempts=3)


@pytest.mark.parametrize(
    "result",
    [ok("a", N), failed("a", S.NOT_FOUND), failed("a", S.BLOCKED), kind_result(K.TIMEOUT), kind_result(K.ADAPTER_EXCEPTION)],
    ids=["success", "not_found", "blocked", "timeout", "adapter_exception"],
)
def test_single_attempt_traces_are_accepted(result):
    SourceExecutionTrace("a", (attempt_like(1, result),), result, max_attempts=2)


# ======================================================================================================================
# 29: every trace the REAL engine produces is still accepted (it goes through the hardened __post_init__)
# ======================================================================================================================


class Script:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = 0

    async def __call__(self, number, client):
        self.calls += 1
        outcome = self.outcomes.pop(0) if len(self.outcomes) > 1 else self.outcomes[0]
        if outcome == "hang":
            await asyncio.Event().wait()
        return outcome


def run_one(outcomes, *, deadline=20.0, policy=RetryPolicy(max_attempts=2, initial_backoff_seconds=0.01)):
    script = Script(outcomes)
    tgt = SourceTarget(SourceConfig("a", deadline_seconds=deadline), scripted_adapter_class("a", script)(), policy)
    (trace,) = asyncio.run(execute_sources_traced(N, [tgt], object()))
    return trace


def rebuild(trace):
    """Re-run the hardened validators on an engine trace field by field (as a hand-built copy would)."""
    attempts = tuple(
        SourceAttempt(a.sequence, a.status, a.error_kind, a.elapsed_ms, a.completed, a.backoff_before_seconds)
        for a in trace.attempts
    )
    return SourceExecutionTrace(
        trace.source_id, attempts, trace.final_result, trace.max_attempts, trace.deadline_exceeded, trace.deadline_during
    )


ENGINE_SHAPES = {
    "single_success": dict(outcomes=[ok("a", N)]),
    "single_not_found": dict(outcomes=[failed("a", S.NOT_FOUND)]),
    "single_blocked": dict(outcomes=[failed("a", S.BLOCKED)]),
    "single_parse_error": dict(outcomes=[failed("a", S.PARSE_ERROR)]),
    "retry_then_success": dict(outcomes=[kind_result(K.TIMEOUT), ok("a", N)]),
    "retry_then_not_found": dict(outcomes=[kind_result(K.CONNECTION_ERROR), failed("a", S.NOT_FOUND)]),
    "retry_then_final_failure": dict(outcomes=[kind_result(K.HTTP_SERVER_ERROR), kind_result(K.TIMEOUT)]),
    "three_attempts": dict(
        outcomes=[kind_result(K.TIMEOUT), kind_result(K.DECODE_ERROR), ok("a", N)],
        policy=RetryPolicy(max_attempts=3, initial_backoff_seconds=0.01),
    ),
    "narrowed_policy_stops_on_eligible_kind": dict(
        outcomes=[kind_result(K.DECODE_ERROR)],
        policy=RetryPolicy(max_attempts=3, initial_backoff_seconds=0.01, retryable_error_kinds=frozenset({K.TIMEOUT})),
    ),
    "deadline_during_attempt_1": dict(outcomes=["hang"], deadline=0.1),
    "deadline_during_retry_attempt": dict(outcomes=[kind_result(K.TIMEOUT), "hang"], deadline=0.2),
    "deadline_during_backoff": dict(
        outcomes=[kind_result(K.TIMEOUT), ok("a", N)], deadline=0.1,
        policy=RetryPolicy(max_attempts=2, initial_backoff_seconds=5.0, max_backoff_seconds=5.0),
    ),
}


@pytest.mark.parametrize("name", list(ENGINE_SHAPES))
def test_29_every_real_engine_trace_shape_is_valid_under_the_hardened_model(name):
    trace = run_one(**ENGINE_SHAPES[name])
    assert rebuild(trace) == trace
    if name.startswith("deadline_during_backoff"):
        assert trace.deadline_during == "backoff" and trace.attempts[-1].completed
    elif name.startswith("deadline_during"):
        assert trace.deadline_during == "attempt" and not trace.attempts[-1].completed
        assert (trace.attempts[-1].status, trace.attempts[-1].error_kind) == (S.NETWORK_ERROR, K.SOURCE_DEADLINE)


def test_29_real_engine_circuit_open_zero_attempt_trace_is_valid():
    async def main():
        governor = SourceResourceGovernor(
            host_limits=HostLimitPolicy(4),
            breaker=CircuitBreakerPolicy(failure_threshold=1, open_duration_seconds=30.0, half_open_max_calls=1),
            clock=FakeClock(),
        )

        async def dead(number, client):
            return failed("dead", S.BLOCKED)

        target = make_target("dead", "https://dead.example", dead)
        (first,) = await execute_sources_traced(N, [target], NullClient(), governor=governor)
        (short,) = await execute_sources_traced(N, [target], NullClient(), governor=governor)
        return first, short

    first, short = asyncio.run(main())
    assert first.final_result.status is S.BLOCKED
    assert short.final_result.error_kind is K.CIRCUIT_OPEN and short.attempts == ()
    assert rebuild(short) == short and rebuild(first) == first


# ======================================================================================================================
# mutation-style proof: revert exactly the C2-L2 checks and the invalid-state tests above lose their teeth
# ======================================================================================================================


def _invalid_constructions():
    final_timeout = kind_result(K.TIMEOUT)
    return {
        "incomplete_success": lambda: SourceAttempt(1, S.SUCCESS, None, 5.0, completed=False),
        "incomplete_parse_error": lambda: SourceAttempt(1, S.PARSE_ERROR, K.PARSE_ERROR, 5.0, completed=False),
        "retry_after_not_found": lambda: SourceExecutionTrace(
            "a", (attempt(1, S.NOT_FOUND, K.NOT_FOUND), attempt_like(2, final_timeout)), final_timeout, max_attempts=2
        ),
        "backoff_after_success": lambda: SourceExecutionTrace(
            "a", (attempt(1, S.SUCCESS, None),), deadline_result(), max_attempts=2,
            deadline_exceeded=True, deadline_during="backoff",
        ),
    }


@pytest.mark.parametrize("name", list(_invalid_constructions()))
def test_mutation_reverting_the_c2_l2_checks_makes_each_invalid_state_constructible_again(name, monkeypatch):
    build = _invalid_constructions()[name]
    with pytest.raises(AggregationContractError):
        build()  # hardened: rejected
    monkeypatch.setattr(models_module, "_check_incomplete_attempt", lambda attempt: None)
    monkeypatch.setattr(models_module, "_check_retry_shape", lambda attempts, deadline_during: None)
    build()  # the pre-P4-C3 validator logic: accepted -- so the rejection above is due to the new checks
