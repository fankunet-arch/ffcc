"""DiscoveryPolicy (contract section 9): the single, centralized place that
controls which extensions are treated as media."""

from __future__ import annotations

import pytest

from fc2_organizer.discovery import DEFAULT_SUPPORTED_EXTENSIONS, DiscoveryConfigError, DiscoveryPolicy


def test_default_policy_uses_documented_default_extensions():
    policy = DiscoveryPolicy()
    assert policy.supported_extensions == frozenset(DEFAULT_SUPPORTED_EXTENSIONS)


def test_default_extensions_include_common_video_containers():
    for ext in (".mp4", ".mkv", ".avi", ".mov", ".wmv", ".m4v", ".ts"):
        assert ext in DEFAULT_SUPPORTED_EXTENSIONS


def test_custom_extensions_are_accepted():
    policy = DiscoveryPolicy(supported_extensions=frozenset({".mp4"}))
    assert policy.supported_extensions == frozenset({".mp4"})


def test_extensions_are_normalized_to_lowercase():
    policy = DiscoveryPolicy(supported_extensions=frozenset({".MP4", ".MKV"}))
    assert policy.supported_extensions == frozenset({".mp4", ".mkv"})


def test_is_supported_extension_matches_case_insensitively_via_normalized_lookup():
    policy = DiscoveryPolicy(supported_extensions=frozenset({".mp4"}))
    assert policy.is_supported_extension(".mp4") is True
    assert policy.is_supported_extension(".jpg") is False


def test_duplicate_extensions_differing_only_by_case_collapse_to_one():
    policy = DiscoveryPolicy(supported_extensions=frozenset({".mp4", ".MP4"}))
    assert policy.supported_extensions == frozenset({".mp4"})


@pytest.mark.parametrize(
    "bad",
    [
        frozenset(),
        frozenset({""}),
        frozenset({"mp4"}),  # missing leading dot
        frozenset({"."}),  # dot alone, no extension body
        frozenset({123}),
        "mp4",  # bare str: iterable of characters, must be rejected outright
        b".mp4",
    ],
)
def test_invalid_extensions_are_rejected(bad):
    with pytest.raises(DiscoveryConfigError):
        DiscoveryPolicy(supported_extensions=bad)


def test_policy_is_frozen():
    policy = DiscoveryPolicy()
    with pytest.raises(Exception):
        policy.supported_extensions = frozenset({".mp4"})  # type: ignore[misc]
