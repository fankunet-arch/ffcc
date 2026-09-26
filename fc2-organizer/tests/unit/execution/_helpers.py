"""Shared helpers for the P4-C7 execution tests (seam injection, traps, links, snapshots)."""

from __future__ import annotations

import builtins
import dataclasses
import hashlib
import os
import stat
from pathlib import Path

import pytest

from fc2_organizer.execution import _fs, preflight_execution, transfer
from fc2_organizer.execution.models import CompletedEffect, EffectKind, PathRole
from fc2_organizer.execution.seal import issue_checkpoint, manifest_fingerprint, plan_fingerprint
from fc2_organizer.execution.directories import create_target_directory

from ._builders import make_plan, scene

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


# --------------------------------------------------------------------------- S3 helpers (media transfer)

MIB = 1 << 20
_HASH_BLOCK = 1 << 20


def sha256_of_file(path) -> str:
    """Streaming SHA-256 of a file (never loads a large file into memory at once)."""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while True:
            block = handle.read(_HASH_BLOCK)
            if not block:
                return digest.hexdigest()
            digest.update(block)


def _regular_file_with_hash(path, expected_sha256: str) -> bool:
    try:
        st = os.lstat(path)
    except OSError:
        return False
    if stat.S_ISLNK(st.st_mode) or not stat.S_ISREG(st.st_mode) or _fs.is_link(st):
        return False
    return sha256_of_file(path) == expected_sha256


def assert_source_not_lost(source_path, final_path, original_sha256: str) -> None:
    """Contract section 31 core invariant (construction plan 0.5): after any failure, the source path or the
    final path (or both) holds a regular, non-link file whose bytes equal the original source bytes."""
    at_source = _regular_file_with_hash(source_path, original_sha256)
    at_final = _regular_file_with_hash(final_path, original_sha256)
    assert at_source or at_final, "source media was lost: neither the source nor the final holds its bytes"


def write_generated_media(path, size: int, seed: bytes = b"fc2-p4-c7-s3") -> str:
    """Write ``size`` deterministic bytes in 1 MiB blocks; returns their SHA-256 (no whole-file buffer)."""
    base = hashlib.sha256(seed).digest() * (MIB // 32)
    digest = hashlib.sha256()
    with open(path, "wb") as handle:
        written, index = 0, 0
        while written < size:
            block = (index.to_bytes(8, "big") + base[8:])[: min(MIB, size - written)]
            handle.write(block)
            digest.update(block)
            written += len(block)
            index += 1
    return digest.hexdigest()


@dataclasses.dataclass
class TransferScene:
    """A real on-disk U2 starting point: library root, source media, created target directory."""

    root: Path
    plan: object
    source: str
    final: str
    target_directory: str
    source_identity: object
    target_identity: object
    sha256: str
    size: int
    planted: dict


PLANTED_NAMES = (".fc2tmp-" + "a" * 32 + ".part", "user-download.part", "user-note.tmp")


def transfer_scene(tmp_path: Path, *, content: bytes | None = None, size: int | None = None,
                   source_name: str = "random-name.MP4", library_name: str = "library",
                   plant: bool = True) -> TransferScene:
    """Build a real scene (``_builders.scene``), create the target directory with the production helper,
    and plant unrelated temp-looking / user files in the target and source directories."""
    generated = content is None
    s = scene(tmp_path, content=b"" if generated else content, source_name=source_name,
              library_name=library_name)
    if generated:
        digest = write_generated_media(s.source_path, size)
        plan = make_plan(s.library_root, s.source_path, extension=os.path.splitext(source_name)[1], size=size)
    else:
        digest, size, plan = hashlib.sha256(content).hexdigest(), len(content), s.plan
    library_identity = _fs.snapshot(s.library_root)
    target_identity, failure = create_target_directory(plan, library_identity)
    assert failure is None
    target_directory = plan.target_directory.absolute_path
    planted = {}
    if plant:
        for directory in (target_directory, os.path.dirname(s.source_path)):
            for name in PLANTED_NAMES:
                path = os.path.join(directory, name)
                with open(path, "wb") as handle:
                    handle.write(b"unrelated " + name.encode())
        planted = planted_state(target_directory, os.path.dirname(s.source_path))
    return TransferScene(tmp_path, plan, s.source_path, plan.target_media_path.absolute_path, target_directory,
                         _fs.snapshot(s.source_path), target_identity, digest, size, planted)


def planted_state(*directories) -> dict:
    state = {}
    for directory in directories:
        for name in PLANTED_NAMES:
            path = os.path.join(directory, name)
            if os.path.lexists(path):
                st = os.lstat(path)
                with open(path, "rb") as handle:
                    state[path] = (handle.read(), st.st_ino, st.st_mtime_ns)
            else:
                state[path] = None
    return state


def assert_planted_unchanged(ts: TransferScene) -> None:
    assert planted_state(ts.target_directory, os.path.dirname(ts.source)) == ts.planted


def temp_names(directory) -> list[str]:
    return sorted(n for n in os.listdir(directory) if n.startswith(".fc2tmp-") and n not in PLANTED_NAMES)


def use_strategy(monkeypatch: pytest.MonkeyPatch, strategy: str) -> None:
    monkeypatch.setattr(transfer, "_SAME_VOLUME_STRATEGY", strategy)


class SeamLog:
    """Records the ordered seam calls of one transfer: ``(op, arg)`` with ``arg`` a path or an fd."""

    OPS = ("lstat", "fstat", "open", "read", "write", "fsync", "close", "rename", "link", "unlink")

    def __init__(self, monkeypatch: pytest.MonkeyPatch, *, wrap: dict | None = None) -> None:
        self.calls: list[tuple[str, object]] = []
        wrap = wrap or {}
        ops = {}
        for name in self.OPS:
            inner = wrap.get(name, getattr(_fs._FS, name))
            ops[name] = self._recording(name, inner)
        inject(monkeypatch, **ops)

    def _recording(self, name, inner):
        def op(*args):
            self.calls.append((name, args[0] if args else None))
            return inner(*args)
        return op

    def ops(self, *names) -> list[tuple[str, object]]:
        return [call for call in self.calls if call[0] in names]

    def index(self, op: str, arg=None, start: int = 0) -> int:
        for position in range(start, len(self.calls)):
            name, value = self.calls[position]
            if name == op and (arg is None or value == arg):
                return position
        raise AssertionError(f"{op}({arg!r}) not called after position {start}: {self.calls}")


class FakeDirectoryFsync:
    """Enables the POSIX directory-fsync path on any host: ``open`` of ``directory`` yields a fake fd whose
    ``fsync`` / ``close`` are recorded (Windows cannot open a directory, contract section 26.1)."""

    FD = 987654

    def __init__(self, monkeypatch: pytest.MonkeyPatch, directory: str, *, fsync_error: OSError | None = None,
                 close_error: OSError | None = None) -> None:
        monkeypatch.setattr(transfer, "_DIRECTORY_FSYNC", True)
        self.events: list[str] = []
        real_open, real_fsync, real_close = _fs._FS.open, _fs._FS.fsync, _fs._FS.close

        def open_(path, flags, *rest):
            if path == directory:
                assert not flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC)
                self.events.append("open")
                return self.FD
            return real_open(path, flags, *rest)

        def fsync_(fd):
            if fd == self.FD:
                self.events.append("fsync")
                if fsync_error is not None:
                    raise fsync_error
                return None
            return real_fsync(fd)

        def close_(fd):
            if fd == self.FD:
                self.events.append("close")
                if close_error is not None:
                    raise close_error
                return None
            return real_close(fd)

        inject(monkeypatch, open=open_, fsync=fsync_, close=close_)


class FdTracker:
    """Wraps the seam's ``open`` / ``close`` to prove every descriptor opened by a transfer is closed."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.opened: list[int] = []
        self.closed: list[int] = []
        real_open, real_close = _fs._FS.open, _fs._FS.close

        def open_(*args):
            fd = real_open(*args)
            self.opened.append(fd)
            return fd

        def close_(fd):
            self.closed.append(fd)
            return real_close(fd)

        inject(monkeypatch, open=open_, close=close_)

    def assert_all_closed(self) -> None:
        assert sorted(self.opened) == sorted(self.closed), (self.opened, self.closed)
        for fd in self.opened:
            with pytest.raises(OSError):
                os.fstat(fd)


def force_cross_volume_devices(monkeypatch: pytest.MonkeyPatch, offset: int = 7) -> None:
    """``device_of`` seam: regular files report another device than directories, so preflight predicts
    CROSS_VOLUME for a same-disk test tree (mocked -- never native cross-volume evidence)."""
    real = _fs._FS.device_of

    def device_of(st):
        return real(st) + offset if stat.S_ISREG(st.st_mode) else real(st)

    inject(monkeypatch, device_of=device_of)


def mismatch_resume_blockers(ts: TransferScene, outcome, manifest, transfer_mode) -> tuple:
    """TESTS-ONLY: issue a real sealed checkpoint whose effects are U1 + the transfer's recorded effects and
    return the RESUME preflight's blocker reasons (proves a recorded-but-changed effect fails closed)."""
    directory = CompletedEffect(EffectKind.TARGET_DIRECTORY_CREATED, PathRole.TARGET_DIRECTORY,
                                ts.target_directory, ts.target_identity, None, None, None, None)
    checkpoint = issue_checkpoint(
        plan_fingerprint=plan_fingerprint(ts.plan), manifest_fingerprint=manifest_fingerprint(manifest),
        library_root_identity=_fs.snapshot(ts.plan.library_root), source_identity=ts.source_identity,
        transfer_mode=transfer_mode, target_directory_identity=ts.target_identity,
        extrafanart_directory_identity=None, completed_effects=(directory, *outcome.effects),
        leftover_temporaries=outcome.leftover_temporaries)
    preflight = preflight_execution(ts.plan, manifest, checkpoint)
    return tuple(blocker.reason for blocker in preflight.blockers)
