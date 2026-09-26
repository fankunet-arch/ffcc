"""Shared helpers for the P4-C7 execution tests (seam injection, traps, links, snapshots)."""

from __future__ import annotations

import builtins
import dataclasses
import os
from pathlib import Path

import pytest

from fc2_organizer.execution import _fs

# Every mutating entry of the private seam (S1 must never reach any of them).
MUTATING_SEAM_OPS = ("mkdir", "rename", "link", "unlink", "write", "fsync", "open", "read", "close")
# Mutating / content-reading functions on the os module and builtins (defence in depth).
MUTATING_OS_FUNCS = ("mkdir", "makedirs", "rename", "renames", "replace", "link", "symlink", "unlink",
                     "remove", "rmdir", "removedirs", "write", "truncate", "ftruncate", "chmod", "utime",
                     "open", "fsync")


def inject(monkeypatch: pytest.MonkeyPatch, **ops) -> None:
    """Replace selected private filesystem ops of the execution seam for this test only."""
    monkeypatch.setattr(_fs, "_FS", dataclasses.replace(_fs._FS, **ops))


class Trap:
    """Records forbidden calls; every trapped function raises ``AssertionError``."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def make(self, name: str):
        def trapped(*_args, **_kwargs):
            self.calls.append(name)
            raise AssertionError(f"forbidden call during read-only preflight: {name}")
        return trapped


def trap_mutations(monkeypatch: pytest.MonkeyPatch) -> Trap:
    """Trap every mutating / content-reading seam op, os function and ``builtins.open``."""
    trap = Trap()
    inject(monkeypatch, **{name: trap.make(f"_FS.{name}") for name in MUTATING_SEAM_OPS})
    for name in MUTATING_OS_FUNCS:
        if hasattr(os, name):
            monkeypatch.setattr(os, name, trap.make(f"os.{name}"))
    monkeypatch.setattr(builtins, "open", trap.make("builtins.open"))
    return trap


# --------------------------------------------------------------------------- S2 helpers

_WRITE_FLAGS = (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND | os.O_EXCL)
ALL_SEAM_OPS = ("lstat", "fstat", "open", "read", "write", "fsync", "close", "mkdir", "rename", "link", "unlink",
                "listdir")


def _trap_os(monkeypatch: pytest.MonkeyPatch, trap: Trap) -> None:
    for name in MUTATING_OS_FUNCS:
        if hasattr(os, name):
            monkeypatch.setattr(os, name, trap.make(f"os.{name}"))
    monkeypatch.setattr(builtins, "open", trap.make("builtins.open"))


def trap_mutations_allowing_reads(monkeypatch: pytest.MonkeyPatch) -> tuple[Trap, list[str]]:
    """Like :func:`trap_mutations`, but the seam's ``open`` / ``read`` / ``close`` stay usable for READ-ONLY
    opens (RESUME re-hash of published artifacts). Returns the trap and the list of paths opened."""
    trap = Trap()
    opened: list[str] = []
    real_open = _fs._FS.open

    def read_only_open(path, flags, *rest):
        if flags & _WRITE_FLAGS:
            trap.calls.append("_FS.open(write flags)")
            raise AssertionError("write-capable open during read-only preflight")
        opened.append(path)
        return real_open(path, flags, *rest)

    inject(monkeypatch, open=read_only_open,
           **{name: trap.make(f"_FS.{name}") for name in ("mkdir", "rename", "link", "unlink", "write", "fsync")})
    _trap_os(monkeypatch, trap)
    return trap, opened


def trap_all_io(monkeypatch: pytest.MonkeyPatch) -> Trap:
    """Trap EVERY seam op (reads included) plus os / builtins: proves ZERO filesystem access."""
    trap = Trap()
    inject(monkeypatch, **{name: trap.make(f"_FS.{name}") for name in ALL_SEAM_OPS})
    _trap_os(monkeypatch, trap)
    return trap


class CallCounter:
    """Wraps ``_FS.lstat`` to count filesystem probes."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.paths: list[str] = []
        real = _fs._FS.lstat

        def counting(path):
            self.paths.append(path)
            return real(path)

        inject(monkeypatch, lstat=counting)


def failing(exc: BaseException):
    def op(*_args, **_kwargs):
        raise exc
    return op


def lstat_failing_for(target: str, exc: OSError):
    real = _fs._FS.lstat

    def op(path):
        if path == target:
            raise exc
        return real(path)
    return op


_EXTRA_STAT_FIELDS = ("st_atime", "st_mtime", "st_ctime", "st_atime_ns", "st_mtime_ns", "st_ctime_ns",
                      "st_blksize", "st_blocks", "st_rdev", "st_flags", "st_file_attributes", "st_reparse_tag",
                      "st_birthtime", "st_birthtime_ns")


def with_stat_fields(st: os.stat_result, **overrides) -> os.stat_result:
    """A copy of ``st`` with visible fields (``st_ino``, ``st_dev``, ``st_size``, ``st_mode``) overridden."""
    order = ("st_mode", "st_ino", "st_dev", "st_nlink", "st_uid", "st_gid", "st_size")
    visible = list(tuple(st))
    for index, name in enumerate(order):
        if name in overrides:
            visible[index] = overrides[name]
    extra = {name: getattr(st, name) for name in _EXTRA_STAT_FIELDS if hasattr(st, name)}
    for name in list(overrides):
        if name not in order:
            extra[name] = overrides[name]
    return os.stat_result(tuple(visible), extra)


def lstat_rewriting(target: str, **overrides):
    real = _fs._FS.lstat

    def op(path):
        st = real(path)
        return with_stat_fields(st, **overrides) if path == target else st
    return op


def try_symlink(link: Path, target: Path, *, target_is_directory: bool = False) -> None:
    try:
        os.symlink(target, link, target_is_directory=target_is_directory)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation not permitted on this host")


def try_junction(link: Path, target: Path) -> None:
    if os.name != "nt":
        pytest.skip("junctions are Windows-only")
    import _winapi

    _winapi.CreateJunction(str(target), str(link))


def fingerprint_tree(root: Path) -> dict[str, tuple]:
    """Name -> (is_dir, bytes or None, mtime_ns, inode) for every entry below ``root`` (no link following)."""
    result = {}
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        for name in dirnames + filenames:
            path = os.path.join(dirpath, name)
            st = os.lstat(path)
            content = None
            if os.path.isfile(path) and not os.path.islink(path):
                with open(path, "rb") as handle:
                    content = handle.read()
            result[os.path.relpath(path, root)] = (os.path.isdir(path), content, st.st_mtime_ns, st.st_ino)
    return result
