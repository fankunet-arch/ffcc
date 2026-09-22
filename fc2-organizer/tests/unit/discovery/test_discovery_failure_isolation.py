"""Subtree / item failure isolation (contract section 13) -- test matrix
items 16-18.

Real permission denial and real time-of-check/time-of-use races are
unreliable to construct deterministically (especially for the invoking
user's own files on Windows). Instead these tests inject the failure at the
exact filesystem seam (``scanner._list_directory_sorted`` /
``scanner._stat_entry``) via monkeypatch, which exercises the identical
except-branches a real OS-level failure would hit.
"""

from __future__ import annotations

import os

from fc2_organizer.discovery import DiscoveryIssueKind, DiscoveryStage, discover_media
from fc2_organizer.discovery import scanner


def test_permission_denied_subtree_is_isolated_scan_continues(tmp_path, monkeypatch):
    (tmp_path / "ok").mkdir()
    (tmp_path / "ok" / "visible.mp4").write_text("x")
    blocked = tmp_path / "blocked"
    blocked.mkdir()
    (blocked / "hidden.mp4").write_text("x")

    real_list = scanner._list_directory_sorted

    def fake_list(path):
        if os.fspath(path) == os.fspath(blocked):
            raise PermissionError("simulated permission denied")
        return real_list(path)

    monkeypatch.setattr(scanner, "_list_directory_sorted", fake_list)

    result = discover_media(tmp_path)

    assert [item.relative_path for item in result.items] == ["ok/visible.mp4"]
    assert len(result.issues) == 1
    issue = result.issues[0]
    assert issue.kind is DiscoveryIssueKind.PERMISSION_DENIED
    assert issue.stage is DiscoveryStage.LIST_DIRECTORY
    assert issue.path == str(blocked)


def test_directory_disappears_during_scan_is_isolated(tmp_path, monkeypatch):
    (tmp_path / "ok").mkdir()
    (tmp_path / "ok" / "visible.mp4").write_text("x")
    vanished = tmp_path / "vanished"
    vanished.mkdir()

    real_list = scanner._list_directory_sorted

    def fake_list(path):
        if os.fspath(path) == os.fspath(vanished):
            raise FileNotFoundError("simulated vanished directory")
        return real_list(path)

    monkeypatch.setattr(scanner, "_list_directory_sorted", fake_list)

    result = discover_media(tmp_path)

    assert [item.relative_path for item in result.items] == ["ok/visible.mp4"]
    assert result.issues[0].kind is DiscoveryIssueKind.PATH_VANISHED
    assert result.issues[0].stage is DiscoveryStage.LIST_DIRECTORY


def test_file_disappears_between_enumeration_and_stat_is_isolated(tmp_path, monkeypatch):
    (tmp_path / "keep.mp4").write_text("x")
    (tmp_path / "vanish.mp4").write_text("x")

    real_stat = scanner._stat_entry

    def fake_stat(entry):
        if entry.name == "vanish.mp4":
            raise FileNotFoundError("simulated vanished file")
        return real_stat(entry)

    monkeypatch.setattr(scanner, "_stat_entry", fake_stat)

    result = discover_media(tmp_path)

    assert [item.relative_path for item in result.items] == ["keep.mp4"]
    assert result.issues[0].kind is DiscoveryIssueKind.PATH_VANISHED
    assert result.issues[0].stage is DiscoveryStage.STAT_ENTRY
    assert result.issues[0].path.endswith("vanish.mp4")


def test_permission_denied_on_stat_is_isolated(tmp_path, monkeypatch):
    (tmp_path / "keep.mp4").write_text("x")
    (tmp_path / "denied.mp4").write_text("x")

    real_stat = scanner._stat_entry

    def fake_stat(entry):
        if entry.name == "denied.mp4":
            raise PermissionError("simulated stat permission denied")
        return real_stat(entry)

    monkeypatch.setattr(scanner, "_stat_entry", fake_stat)

    result = discover_media(tmp_path)

    assert [item.relative_path for item in result.items] == ["keep.mp4"]
    assert result.issues[0].kind is DiscoveryIssueKind.PERMISSION_DENIED
    assert result.issues[0].stage is DiscoveryStage.STAT_ENTRY


def test_multiple_independent_failures_are_all_isolated(tmp_path, monkeypatch):
    for name in ("a", "b", "c"):
        (tmp_path / name).mkdir()
    (tmp_path / "a" / "ok.mp4").write_text("x")

    real_list = scanner._list_directory_sorted

    def fake_list(path):
        name = os.path.basename(os.fspath(path))
        if name == "b":
            raise PermissionError("simulated")
        if name == "c":
            raise FileNotFoundError("simulated")
        return real_list(path)

    monkeypatch.setattr(scanner, "_list_directory_sorted", fake_list)

    result = discover_media(tmp_path)

    assert [item.relative_path for item in result.items] == ["a/ok.mp4"]
    assert len(result.issues) == 2
    kinds = {issue.kind for issue in result.issues}
    assert kinds == {DiscoveryIssueKind.PERMISSION_DENIED, DiscoveryIssueKind.PATH_VANISHED}


def test_classify_stat_failure_on_entry_is_isolated(tmp_path, monkeypatch):
    (tmp_path / "keep.mp4").write_text("x")
    (tmp_path / "odd.mp4").write_text("x")

    real_is_symlink = scanner._is_symlink

    def fake_is_symlink(entry):
        if entry.name == "odd.mp4":
            raise OSError("simulated classify failure")
        return real_is_symlink(entry)

    monkeypatch.setattr(scanner, "_is_symlink", fake_is_symlink)

    result = discover_media(tmp_path)

    assert [item.relative_path for item in result.items] == ["keep.mp4"]
    assert result.issues[0].kind is DiscoveryIssueKind.STAT_FAILED
    assert result.issues[0].stage is DiscoveryStage.CLASSIFY_ENTRY
