"""P4-C2 mandatory No-Mutation Contract Test (contract section 30).

Proves ``build_organize_plan`` never touches the filesystem, two
independent ways:

1. A before/after directory snapshot (path -> content) around real calls,
   including the synthetic-gate-sized batch, must be byte-identical.
2. Every common mutation API (``os.mkdir``/``os.makedirs``/``os.rename``/
   ``os.replace``/``os.remove``/``os.unlink``/``os.rmdir``/``os.chmod``/
   ``os.utime``/``shutil.move``/``shutil.copy*``/``shutil.rmtree``/
   ``pathlib.Path.mkdir``/``write_text``/``write_bytes``/``touch``/
   ``rename``/``replace``/``unlink``/builtin ``open`` in a write mode) is
   monkeypatched to raise if called; ``build_organize_plan`` must run to
   completion under every one of these traps without tripping any of them.
"""

from __future__ import annotations

import os
import pathlib
import shutil

import pytest

from fc2_metadata_core.models import NormalizedMetadata
from fc2_organizer.discovery import DiscoveredMediaItem
from fc2_organizer.planning.planner import build_organize_plan


def _snapshot(root: pathlib.Path) -> dict[str, bytes]:
    snapshot: dict[str, bytes] = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            snapshot[str(path.relative_to(root))] = path.read_bytes()
    return snapshot


def _build_several_plans(library_root: str) -> None:
    for i in range(5):
        item = DiscoveredMediaItem(
            index=i,
            source_path=rf"C:\downloads\movie{i}.mp4",
            relative_path=f"movie{i}.mp4",
            extension=".mp4",
            size=100 + i,
        )
        metadata = NormalizedMetadata(number=f"FC2-{1000000 + i}", title=f"Title {i}")
        build_organize_plan(item, f"FC2-{1000000 + i}", metadata, library_root)


def test_no_filesystem_mutation_via_before_after_snapshot(tmp_path):
    watched_dir = tmp_path / "watched"
    watched_dir.mkdir()
    (watched_dir / "existing.txt").write_text("unchanged", encoding="utf-8")
    (watched_dir / "subdir").mkdir()
    (watched_dir / "subdir" / "nested.bin").write_bytes(b"\x00\x01\x02")

    before = _snapshot(watched_dir)

    library_root = str(tmp_path / "library")  # deliberately does not exist on disk
    _build_several_plans(library_root)

    after = _snapshot(watched_dir)
    assert before == after
    # The planned library root itself was never created either.
    assert not os.path.exists(library_root)


class _MutationAttempted(AssertionError):
    pass


def test_no_filesystem_mutation_with_common_mutation_apis_blocked(tmp_path, monkeypatch):
    def _trap(name):
        def _raise(*args, **kwargs):
            raise _MutationAttempted(f"blocked mutation API called: {name}(args={args!r}, kwargs={kwargs!r})")
        return _raise

    blocked_os_functions = [
        "mkdir", "makedirs", "rename", "replace", "remove", "unlink",
        "rmdir", "removedirs", "chmod", "utime", "symlink", "link",
    ]
    for name in blocked_os_functions:
        if hasattr(os, name):
            monkeypatch.setattr(os, name, _trap(f"os.{name}"))

    blocked_shutil_functions = ["move", "copy", "copy2", "copyfile", "copytree", "rmtree"]
    for name in blocked_shutil_functions:
        if hasattr(shutil, name):
            monkeypatch.setattr(shutil, name, _trap(f"shutil.{name}"))

    blocked_path_methods = [
        "mkdir", "write_text", "write_bytes", "touch", "rename", "replace", "unlink", "rmdir", "symlink_to",
    ]
    for name in blocked_path_methods:
        if hasattr(pathlib.Path, name):
            monkeypatch.setattr(pathlib.Path, name, _trap(f"Path.{name}"))

    real_open = open

    def _guarded_open(file, mode="r", *args, **kwargs):
        if any(flag in mode for flag in ("w", "a", "x", "+")):
            raise _MutationAttempted(f"blocked open() in write-capable mode: mode={mode!r} file={file!r}")
        return real_open(file, mode, *args, **kwargs)

    monkeypatch.setattr("builtins.open", _guarded_open)

    library_root = str(tmp_path / "library")
    # Must run to completion: no trap above may fire during planning.
    _build_several_plans(library_root)

    item = DiscoveredMediaItem(
        index=0, source_path=r"C:\downloads\a.mp4", relative_path="a.mp4", extension=".mp4", size=1,
    )
    metadata = NormalizedMetadata(number="FC2-1234567", title="Example")
    plan = build_organize_plan(item, "FC2-1234567", metadata, library_root)
    assert plan.target_media_path.absolute_path.endswith("FC2-1234567.mp4")


def test_blocked_mutation_trap_is_itself_effective(tmp_path, monkeypatch):
    """Self-test: proves the trap in the previous test would actually catch
    a real mutation, the same way P4-C1's busy-guard self-test proves its
    own guard is effective rather than trivially vacuous."""

    def _raise(*args, **kwargs):
        raise AssertionError("blocked mutation API called: os.mkdir")

    monkeypatch.setattr(os, "mkdir", _raise)
    with pytest.raises(AssertionError):
        os.mkdir(str(tmp_path / "should_not_be_created"))
    assert not (tmp_path / "should_not_be_created").exists()
