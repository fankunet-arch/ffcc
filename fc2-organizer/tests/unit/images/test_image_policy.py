"""P4-C5 substep 1: immutable ImageAcquisitionPolicy (contract section 7)."""

from __future__ import annotations

import dataclasses

import pytest

from fc2_organizer.images import ImageAcquisitionPolicy, ImageError, ImagePolicyError

_INT_FIELDS = ("max_redirects", "max_image_bytes", "max_total_bytes", "max_candidates_per_role", "max_extrafanart")


def test_policy_defaults_are_frozen():
    policy = ImageAcquisitionPolicy()
    assert policy.request_deadline_seconds == 15.0
    assert policy.max_redirects == 5
    assert policy.max_image_bytes == 16 * 1024 * 1024
    assert policy.max_total_bytes == 64 * 1024 * 1024
    assert policy.max_candidates_per_role == 16
    assert policy.max_extrafanart == 12


def test_policy_is_frozen_and_slotted():
    policy = ImageAcquisitionPolicy()
    with pytest.raises(dataclasses.FrozenInstanceError):
        policy.max_redirects = 1  # type: ignore[misc]
    assert not hasattr(policy, "__dict__")


def test_policy_accepts_positive_custom_values():
    policy = ImageAcquisitionPolicy(
        request_deadline_seconds=3, max_redirects=1, max_image_bytes=1, max_total_bytes=1,
        max_candidates_per_role=1, max_extrafanart=1,
    )
    assert policy.request_deadline_seconds == 3


class _FloatSub(float):
    pass


class _IntSub(int):
    pass


@pytest.mark.parametrize(
    "bad", [True, False, 0, 0.0, -1, -0.5, float("nan"), float("inf"), float("-inf"), "15", None, _FloatSub(1.0)]
)
def test_policy_deadline_invalid(bad):
    with pytest.raises(ImagePolicyError):
        ImageAcquisitionPolicy(request_deadline_seconds=bad)


def test_policy_deadline_huge_int_does_not_overflow():
    assert ImageAcquisitionPolicy(request_deadline_seconds=10**400).request_deadline_seconds == 10**400


@pytest.mark.parametrize("name", _INT_FIELDS)
@pytest.mark.parametrize("bad", [True, False, 0, -1, 1.0, float("inf"), "1", None, _IntSub(1)])
def test_policy_int_fields_invalid(name, bad):
    with pytest.raises(ImagePolicyError):
        ImageAcquisitionPolicy(**{name: bad})


def test_policy_image_cap_may_not_exceed_total_cap():
    with pytest.raises(ImagePolicyError):
        ImageAcquisitionPolicy(max_image_bytes=2, max_total_bytes=1)


def test_policy_error_is_typed_image_error():
    with pytest.raises(ImageError) as info:
        ImageAcquisitionPolicy(max_redirects=0)
    assert type(info.value) is ImagePolicyError
