"""RetryPolicy: validation, deterministic backoff, and the retry decision matrix (pure, no asyncio)."""

from __future__ import annotations

import dataclasses

import pytest

from fc2_metadata_core.aggregation import (
    DEFAULT_MAX_ATTEMPTS,
    DEFAULT_RETRYABLE_ERROR_KINDS,
    RETRY_ELIGIBLE_KINDS,
    AggregationConfig,
    AggregationConfigError,
    RetryPolicy,
    SourceConfig,
)
from fc2_metadata_core.models.source_result import (
    ALLOWED_ERROR_KINDS,
    SourceErrorKind,
    SourceStatus,
    status_for_error_kind,
)

from support.scripted_adapters import failed, ok

K = SourceErrorKind
S = SourceStatus


def result_for(kind):
    return failed("x", status_for_error_kind(kind), error_kind=kind)


# ---- defaults & validation ------------------------------------------------------------------------------


def test_defaults_are_frozen_by_the_contract():
    policy = RetryPolicy()
    assert DEFAULT_MAX_ATTEMPTS == policy.max_attempts == 2  # first try + at most ONE retry
    assert policy.initial_backoff_seconds == 1.0
    assert policy.backoff_multiplier == 2.0 and policy.max_backoff_seconds == 5.0
    assert policy.retryable_error_kinds == DEFAULT_RETRYABLE_ERROR_KINDS == RETRY_ELIGIBLE_KINDS
    assert RETRY_ELIGIBLE_KINDS == {K.NETWORK_ERROR, K.TIMEOUT, K.CONNECTION_ERROR, K.DECODE_ERROR, K.HTTP_SERVER_ERROR}


def test_the_policy_is_immutable_and_hashable():
    policy = RetryPolicy()
    with pytest.raises(dataclasses.FrozenInstanceError):
        policy.max_attempts = 9  # type: ignore[misc]
    assert hash(policy) == hash(RetryPolicy()) and policy == RetryPolicy()


@pytest.mark.parametrize("value", [0, -1, 6, 100, 2.0, True, None, "2"])
def test_bad_max_attempts_are_rejected(value):
    with pytest.raises(AggregationConfigError):
        RetryPolicy(max_attempts=value)  # type: ignore[arg-type]


@pytest.mark.parametrize("value", [1, 2, 3, 5])
def test_good_max_attempts_are_accepted(value):
    assert RetryPolicy(max_attempts=value).max_attempts == value


@pytest.mark.parametrize("field", ["initial_backoff_seconds", "max_backoff_seconds"])
@pytest.mark.parametrize("value", [-0.1, float("nan"), float("inf"), -float("inf"), True, "1", None, 601])
def test_bad_backoff_seconds_are_rejected(field, value):
    with pytest.raises(AggregationConfigError):
        RetryPolicy(**{field: value})  # type: ignore[arg-type]


@pytest.mark.parametrize("value", [0.99, 0, -1, float("nan"), float("inf"), True, "2", None, 101])
def test_bad_multiplier_is_rejected(value):
    with pytest.raises(AggregationConfigError):
        RetryPolicy(backoff_multiplier=value)  # type: ignore[arg-type]


@pytest.mark.parametrize("value", [0, 0.0, 0.01, 1, 2.5])
def test_zero_and_fractional_backoffs_are_fine(value):
    assert RetryPolicy(initial_backoff_seconds=value).initial_backoff_seconds == value


def test_the_retryable_set_can_only_be_narrowed_never_widened():
    assert RetryPolicy(retryable_error_kinds=frozenset({K.TIMEOUT})).retryable_error_kinds == {K.TIMEOUT}
    assert RetryPolicy(retryable_error_kinds=frozenset()).retryable_error_kinds == frozenset()
    for forbidden in (K.BLOCKED, K.RATE_LIMITED, K.NOT_FOUND, K.PARSE_ERROR, K.INVALID_RESPONSE, K.SOURCE_DEADLINE,
                      K.ADAPTER_EXCEPTION, K.RESULT_CONTRACT_MISMATCH, K.RESPONSE_TOO_LARGE, K.REDIRECT_ERROR):
        with pytest.raises(AggregationConfigError):
            RetryPolicy(retryable_error_kinds=frozenset({K.TIMEOUT, forbidden}))


@pytest.mark.parametrize("bad", [{K.TIMEOUT}, [K.TIMEOUT], (K.TIMEOUT,), frozenset({"timeout"}), None])
def test_retryable_error_kinds_must_be_a_frozenset_of_kinds(bad):
    with pytest.raises(AggregationConfigError):
        RetryPolicy(retryable_error_kinds=bad)  # type: ignore[arg-type]


def test_no_retry_policy():
    assert RetryPolicy.no_retry().max_attempts == 1
    assert RetryPolicy.no_retry().should_retry(result_for(K.TIMEOUT), 1) is False


# ---- deterministic backoff ---------------------------------------------------------------------------------


def test_default_backoff_has_exactly_one_pause_of_one_second():
    policy = RetryPolicy()
    assert policy.backoff_before_attempt(1) == 0.0
    assert policy.backoff_before_attempt(2) == 1.0
    assert not policy.should_retry(result_for(K.TIMEOUT), 2)  # no third attempt, so no second pause


def test_backoff_grows_by_the_multiplier_and_is_capped():
    policy = RetryPolicy(max_attempts=5, initial_backoff_seconds=1.0, backoff_multiplier=2.0, max_backoff_seconds=5.0)
    assert [policy.backoff_before_attempt(n) for n in (1, 2, 3, 4, 5)] == [0.0, 1.0, 2.0, 4.0, 5.0]


def test_backoff_is_deterministic_no_jitter():
    policy = RetryPolicy(max_attempts=4, initial_backoff_seconds=0.7, backoff_multiplier=1.5, max_backoff_seconds=9)
    assert [policy.backoff_before_attempt(3) for _ in range(50)] == [policy.backoff_before_attempt(3)] * 50
    assert policy.backoff_before_attempt(3) == pytest.approx(0.7 * 1.5)


def test_zero_backoff_and_constant_multiplier():
    assert RetryPolicy(initial_backoff_seconds=0).backoff_before_attempt(2) == 0.0
    flat = RetryPolicy(max_attempts=4, initial_backoff_seconds=2, backoff_multiplier=1, max_backoff_seconds=10)
    assert [flat.backoff_before_attempt(n) for n in (2, 3, 4)] == [2.0, 2.0, 2.0]


# ---- decision matrix ------------------------------------------------------------------------------------------


RETRYABLE = [K.NETWORK_ERROR, K.TIMEOUT, K.CONNECTION_ERROR, K.DECODE_ERROR, K.HTTP_SERVER_ERROR]
NOT_RETRYABLE = [
    K.NOT_FOUND, K.BLOCKED, K.RATE_LIMITED, K.PARSE_ERROR, K.INVALID_RESPONSE, K.RESPONSE_TOO_LARGE,
    K.REDIRECT_ERROR, K.ADAPTER_EXCEPTION, K.RESULT_CONTRACT_MISMATCH, K.SOURCE_DEADLINE, K.CIRCUIT_OPEN,
]


def test_the_matrix_covers_every_kind_exactly_once():
    assert set(RETRYABLE) | set(NOT_RETRYABLE) == set(SourceErrorKind)
    assert not set(RETRYABLE) & set(NOT_RETRYABLE)


@pytest.mark.parametrize("kind", RETRYABLE, ids=lambda k: k.value)
def test_default_policy_retries_these_kinds_while_attempts_remain(kind):
    policy = RetryPolicy()
    assert policy.is_retryable(result_for(kind)) is True
    assert policy.should_retry(result_for(kind), 1) is True
    assert policy.should_retry(result_for(kind), 2) is False  # budget spent: never a third attempt


@pytest.mark.parametrize("kind", NOT_RETRYABLE, ids=lambda k: k.value)
def test_default_policy_never_retries_these_kinds(kind):
    policy = RetryPolicy(max_attempts=5)
    assert policy.is_retryable(result_for(kind)) is False
    assert policy.should_retry(result_for(kind), 1) is False


def test_a_success_is_never_retried():
    assert RetryPolicy(max_attempts=5).should_retry(ok("x", "FC2-1234567"), 1) is False


def test_retry_decision_ignores_the_error_detail_text():
    """P2-R-12: the decision is structural. Text that *says* 'HTTP 500 / timeout' on a
    non-retryable kind changes nothing; retryable kinds with unrelated text still retry."""
    policy = RetryPolicy()
    looks_transient = failed("x", S.INVALID_RESPONSE, detail="x: HTTP 500 timeout connection reset")
    assert looks_transient.error_kind is K.INVALID_RESPONSE and policy.is_retryable(looks_transient) is False
    plain_text = failed("x", S.INVALID_RESPONSE, error_kind=K.HTTP_SERVER_ERROR, detail="something unrelated")
    assert policy.is_retryable(plain_text) is True


def test_a_narrowed_policy_stops_retrying_the_removed_kinds():
    policy = RetryPolicy(retryable_error_kinds=frozenset({K.HTTP_SERVER_ERROR}))
    assert policy.is_retryable(result_for(K.HTTP_SERVER_ERROR)) and not policy.is_retryable(result_for(K.TIMEOUT))


# ---- configuration: global default + per-source override -----------------------------------------------------------


def test_global_default_and_per_source_override_are_configuration_data():
    fast = RetryPolicy(max_attempts=3, initial_backoff_seconds=0.01)
    config = AggregationConfig.create(
        [SourceConfig("a"), SourceConfig("b", retry_policy=RetryPolicy.no_retry()), SourceConfig("c", retry_policy=fast)],
        retry_policy=RetryPolicy(max_attempts=2),
    )
    assert config.retry_policy_for("a") == RetryPolicy(max_attempts=2)
    assert config.retry_policy_for("b").max_attempts == 1
    assert config.retry_policy_for("c") is fast
    with pytest.raises(AggregationConfigError):
        config.retry_policy_for("nope")


def test_default_config_uses_the_default_policy():
    assert AggregationConfig.create([SourceConfig("a")]).retry_policy == RetryPolicy()


@pytest.mark.parametrize("bad", ["retry", 3, {"max_attempts": 2}, object()])
def test_a_non_policy_is_rejected_everywhere(bad):
    with pytest.raises(AggregationConfigError):
        SourceConfig("a", retry_policy=bad)  # type: ignore[arg-type]
    with pytest.raises(AggregationConfigError):
        AggregationConfig(sources=(SourceConfig("a"),), retry_policy=bad)  # type: ignore[arg-type]


def test_every_kind_in_the_allowed_table_is_classified():
    for status, kinds in ALLOWED_ERROR_KINDS.items():
        for kind in kinds:
            assert kind in set(RETRYABLE) | set(NOT_RETRYABLE), f"{kind} is not classified in the retry matrix"
