"""HostLimitPolicy / CircuitBreakerPolicy (contract §4): immutable, bounded, no bool-as-number."""

from __future__ import annotations

import dataclasses
import math

import pytest

from fc2_metadata_core.resource_control import (
    CircuitBreakerPolicy,
    HostKey,
    HostLimitPolicy,
    ResourceControlConfigError,
)

A = HostKey("a.example", 443)
B = HostKey("b.example", 443)


# ---- HostLimitPolicy ---------------------------------------------------------------------------------------------


def test_defaults_are_frozen_and_documented():
    policy = HostLimitPolicy()
    assert policy.default_max_in_flight_per_host == 4
    assert policy.overrides == ()
    assert policy.limit_for(A) == 4


@pytest.mark.parametrize("value", [1, 2, 4, 63, 64])
def test_valid_default_limits(value):
    assert HostLimitPolicy(value).default_max_in_flight_per_host == value


@pytest.mark.parametrize("value", [0, -1, 65, 1000, True, False, 2.0, "3", None, float("nan")])
def test_invalid_default_limits(value):
    with pytest.raises(ResourceControlConfigError):
        HostLimitPolicy(value)  # type: ignore[arg-type]


def test_overrides_via_create_are_canonical_sorted_and_used():
    policy = HostLimitPolicy.create(3, {"B.example:443": 7, "a.example:443": 2, "[::1]:8080": 5})
    assert policy.overrides == (
        (HostKey("::1", 8080), 5),
        (HostKey("a.example", 443), 2),
        (HostKey("b.example", 443), 7),
    )
    assert policy.limit_for(A) == 2
    assert policy.limit_for(B) == 7
    assert policy.limit_for(HostKey("other.example", 443)) == 3
    assert policy.limit_for(HostKey("a.example", 8443)) == 3  # a different port is a different host


def test_duplicate_override_keys_are_rejected_after_canonicalisation():
    with pytest.raises(ResourceControlConfigError):
        HostLimitPolicy.create(3, {"A.example:443": 2, "a.example:443": 3})
    with pytest.raises(ResourceControlConfigError):
        HostLimitPolicy(3, ((A, 2), (A, 3)))
    with pytest.raises(ResourceControlConfigError):
        HostLimitPolicy.create(3, {"a.example:443": 2, "a.example.:443": 3})


@pytest.mark.parametrize("key", ["a.example", "a.example:0", ":443", "not a host:443", "a.example:99999", 5, None])
def test_malformed_override_keys_fail_before_any_network(key):
    with pytest.raises(ResourceControlConfigError):
        HostLimitPolicy.create(3, {key: 2})  # type: ignore[dict-item]


@pytest.mark.parametrize("limit", [0, 65, True, 2.5, "2", None])
def test_invalid_override_limits(limit):
    with pytest.raises(ResourceControlConfigError):
        HostLimitPolicy.create(3, {"a.example:443": limit})  # type: ignore[dict-item]
    with pytest.raises(ResourceControlConfigError):
        HostLimitPolicy(3, ((A, limit),))  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "overrides",
    [[(A, 2)], ((A, 2, 3),), ((A.host, 2),), (("a.example:443", 2),), ((A, 2), "x"), {A: 2}, None],
)
def test_direct_construction_accepts_only_the_immutable_shape(overrides):
    with pytest.raises(ResourceControlConfigError):
        HostLimitPolicy(3, overrides)  # type: ignore[arg-type]


def test_too_many_overrides_are_rejected():
    many = {f"h{i}.example:443": 2 for i in range(257)}
    with pytest.raises(ResourceControlConfigError):
        HostLimitPolicy.create(3, many)
    assert len(HostLimitPolicy.create(3, {f"h{i}.example:443": 2 for i in range(256)}).overrides) == 256


def test_create_rejects_a_non_mapping():
    with pytest.raises(ResourceControlConfigError):
        HostLimitPolicy.create(3, [("a.example:443", 2)])  # type: ignore[arg-type]


def test_the_policy_is_immutable_hashable_and_detached_from_the_callers_mapping():
    source = {"a.example:443": 2}
    policy = HostLimitPolicy.create(3, source)
    source["a.example:443"] = 50
    source["b.example:443"] = 9
    assert policy.limit_for(A) == 2 and policy.limit_for(B) == 3
    with pytest.raises(dataclasses.FrozenInstanceError):
        policy.default_max_in_flight_per_host = 9  # type: ignore[misc]
    assert isinstance(policy.overrides, tuple)
    assert hash(policy) == hash(HostLimitPolicy.create(3, {"a.example:443": 2}))


# ---- CircuitBreakerPolicy ----------------------------------------------------------------------------------------


def test_breaker_defaults_are_frozen_and_documented():
    policy = CircuitBreakerPolicy()
    assert (policy.failure_threshold, policy.open_duration_seconds, policy.half_open_max_calls) == (3, 30.0, 1)


@pytest.mark.parametrize("value", [1, 3, 100])
def test_valid_thresholds(value):
    assert CircuitBreakerPolicy(failure_threshold=value).failure_threshold == value


@pytest.mark.parametrize("value", [0, -3, 101, True, False, 3.0, "3", None])
def test_invalid_thresholds(value):
    with pytest.raises(ResourceControlConfigError):
        CircuitBreakerPolicy(failure_threshold=value)  # type: ignore[arg-type]


@pytest.mark.parametrize("value", [1, 16])
def test_valid_half_open_calls(value):
    assert CircuitBreakerPolicy(half_open_max_calls=value).half_open_max_calls == value


@pytest.mark.parametrize("value", [0, -1, 17, True, 1.0, "1", None])
def test_invalid_half_open_calls(value):
    with pytest.raises(ResourceControlConfigError):
        CircuitBreakerPolicy(half_open_max_calls=value)  # type: ignore[arg-type]


@pytest.mark.parametrize("value", [0.001, 1, 30, 30.5, 3600, 3600.0])
def test_valid_open_durations(value):
    assert CircuitBreakerPolicy(open_duration_seconds=value).open_duration_seconds == value


@pytest.mark.parametrize(
    "value", [0, 0.0, -1, -0.5, 3600.001, 10**9, math.inf, -math.inf, math.nan, True, False, "30", None]
)
def test_invalid_open_durations(value):
    with pytest.raises(ResourceControlConfigError):
        CircuitBreakerPolicy(open_duration_seconds=value)  # type: ignore[arg-type]


def test_breaker_policy_is_immutable_and_hashable():
    policy = CircuitBreakerPolicy(failure_threshold=5)
    with pytest.raises(dataclasses.FrozenInstanceError):
        policy.failure_threshold = 1  # type: ignore[misc]
    assert hash(policy) == hash(CircuitBreakerPolicy(failure_threshold=5))
    assert policy != CircuitBreakerPolicy()
