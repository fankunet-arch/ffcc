"""Root failure semantics (contract section 12): a root-level problem is
never disguised as an empty success."""

from __future__ import annotations

import pytest

from fc2_organizer.discovery import (
    DiscoveryInputError,
    DiscoveryPolicy,
    DiscoveryRootNotADirectoryError,
    DiscoveryRootNotFoundError,
    discover_media,
)


def test_nonexistent_root_raises_typed_error(tmp_path):
    missing = tmp_path / "does-not-exist"
    with pytest.raises(DiscoveryRootNotFoundError):
        discover_media(missing)


def test_root_that_is_a_file_raises_not_a_directory(tmp_path):
    file_root = tmp_path / "not-a-dir.mp4"
    file_root.write_text("x")
    with pytest.raises(DiscoveryRootNotADirectoryError):
        discover_media(file_root)


def test_root_under_a_file_component_raises_not_a_directory(tmp_path):
    file_root = tmp_path / "leaf.txt"
    file_root.write_text("x")
    with pytest.raises((DiscoveryRootNotADirectoryError, DiscoveryRootNotFoundError)):
        discover_media(file_root / "child")


def test_empty_string_root_is_rejected(tmp_path):
    with pytest.raises(DiscoveryInputError):
        discover_media("")


def test_non_path_root_is_rejected():
    with pytest.raises(DiscoveryInputError):
        discover_media(12345)  # type: ignore[arg-type]


def test_root_accepts_pathlib_path(tmp_path):
    result = discover_media(tmp_path)
    assert result.total_items == 0


def test_root_accepts_str(tmp_path):
    result = discover_media(str(tmp_path))
    assert result.total_items == 0


def test_invalid_policy_type_is_rejected(tmp_path):
    with pytest.raises(DiscoveryInputError):
        discover_media(tmp_path, policy=object())  # type: ignore[arg-type]


def test_valid_policy_is_accepted(tmp_path):
    (tmp_path / "a.mp4").write_text("x")
    result = discover_media(tmp_path, policy=DiscoveryPolicy(supported_extensions=frozenset({".mp4"})))
    assert result.total_items == 1
