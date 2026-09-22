"""Proof that ``discover_media`` performs no filesystem mutation (contract
section 7.2) and has no network/Amane dependency (test matrix items 25-27).
"""

from __future__ import annotations

import builtins
import os

import pytest

from fc2_organizer.discovery import discover_media

_BLOCKED_OS_FUNCTIONS = [
    "mkdir",
    "makedirs",
    "remove",
    "unlink",
    "rename",
    "replace",
    "rmdir",
    "removedirs",
    "chmod",
    "utime",
    "truncate",
    "symlink",
    "link",
]


def _blocked(name):
    def _raise(*args, **kwargs):
        raise AssertionError(f"discover_media must never call os.{name}(); called with {args!r} {kwargs!r}")

    return _raise


@pytest.fixture
def synthetic_tree(tmp_path):
    (tmp_path / "A" / "B").mkdir(parents=True)
    (tmp_path / "A" / "one.mp4").write_text("x")
    (tmp_path / "A" / "B" / "two.mkv").write_text("xx")
    (tmp_path / "poster.jpg").write_text("x")
    return tmp_path


def test_no_os_level_mutation_functions_are_ever_called(synthetic_tree, monkeypatch):
    for name in _BLOCKED_OS_FUNCTIONS:
        monkeypatch.setattr(os, name, _blocked(name))

    result = discover_media(synthetic_tree)

    assert result.total_items == 2  # proves the scan actually ran under the patched environment


def test_open_is_never_called_in_write_mode(synthetic_tree, monkeypatch):
    real_open = builtins.open

    def guarded_open(file, mode="r", *args, **kwargs):
        if any(flag in mode for flag in ("w", "a", "x", "+")):
            raise AssertionError(f"discover_media must never open a file for writing: mode={mode!r}")
        return real_open(file, mode, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", guarded_open)

    result = discover_media(synthetic_tree)

    assert result.total_items == 2


def test_directory_listing_is_unchanged_after_scan(synthetic_tree):
    def snapshot():
        entries = set()
        for dirpath, dirnames, filenames in os.walk(synthetic_tree):
            for name in dirnames:
                entries.add(os.path.join(dirpath, name))
            for name in filenames:
                entries.add(os.path.join(dirpath, name))
        return entries

    before = snapshot()
    discover_media(synthetic_tree)
    after = snapshot()

    assert before == after


# No-network / no-Amane dependency (test matrix items 26-27) is proven
# structurally, not by a runtime heuristic here -- see
# tests/contract/test_discovery_architecture.py, which statically AST-scans
# every discovery source file and dynamically blocks amane/httpx imports at
# runtime while exercising discover_media end to end.
