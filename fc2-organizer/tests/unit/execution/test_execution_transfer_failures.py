"""P4-C7 S3: failure injection for media transfer (contract sections 19, 20, 25, 29; construction plan S3).

Every ``TransferStage`` receives an injected ``OSError`` through the private seam ``execution._fs._FS``.
Every test here asserts the core invariant with :func:`assert_source_not_lost` (a meta-test at the end scans
this file's AST), plus the failure, the effect set, the owned temporary (removed, or recorded as leftover) and
the unrelated planted ``.fc2tmp-*.part`` / ``.part`` / ``.tmp`` files (unchanged). Fatal / foreign exceptions
propagate as the same object after descriptors are closed and the owned temporary is removed exactly once.
"""

from __future__ import annotations

import ast
import errno
import hashlib
import os
from pathlib import Path

import pytest

from fc2_organizer.execution import (
    EffectKind,
    EntryType,
    ExecutionFailure,
    ExecutionFailureKind,
    ExecutionStep,
    LeftoverTemporary,
    PathRole,
    PreflightBlockReason,
    TransferMode,
    TransferStage,
)
from fc2_organizer.execution import _fs, transfer
from fc2_organizer.execution.transfer import ResumePhase, transfer_media

from ._builders import make_manifest
from ._helpers import (
    MIB,
    PLANTED_NAMES,
    FakeDirectoryFsync,
    FdTracker,
    SeamLog,
    assert_planted_unchanged,
    assert_source_not_lost,
    failing,
    inject,
    lstat_rewriting,
    mismatch_resume_blockers,
    sha256_of_file,
    temp_names,
    transfer_scene,
    use_strategy,
    with_stat_fields,
)

F = ExecutionFailureKind
T = TransferStage
CROSS = TransferMode.CROSS_VOLUME
SAME = TransferMode.SAME_VOLUME
FULL = ResumePhase.FULL
TAIL = ResumePhase.SOURCE_REMOVAL_ONLY
SIZE = 3 * MIB + 17
PLANTED_TEMP = PLANTED_NAMES[0]


def _content(size: int = SIZE) -> bytes:
    block = hashlib.sha256(b"failure-injection").digest()
    return (block * (size // len(block) + 1))[:size]


def _scene(tmp_path, monkeypatch, strategy="rename", size=SIZE):
    use_strategy(monkeypatch, strategy)
    return transfer_scene(tmp_path, content=_content(size))


def _run(ts, mode=CROSS, phase=FULL):
    return transfer_media(ts.plan, ts.source_identity, ts.target_identity, mode, resume_phase=phase)


def _failure(kind, stage=None, errno_=None, published=None):
    return ExecutionFailure(step=ExecutionStep.MOVE_MEDIA, kind=kind, stage=stage, errno=errno_,
                            target_published=published)


def _source_intact(ts):
    return _fs.snapshot(ts.source) == ts.source_identity and sha256_of_file(ts.source) == ts.sha256


def _assert_pre_publish_failure(ts, outcome, failure, *, leftovers=()):
    """Nothing published: no effect, source intact, no final, owned temp gone (or recorded), planted intact."""
    assert outcome.failure == failure
    assert outcome.effects == () and outcome.media_sha256 is None and outcome.media_size is None
    assert outcome.leftover_temporaries == leftovers
    assert outcome.transfer_mode is CROSS
    assert _source_intact(ts)
    assert not os.path.lexists(ts.final)
    assert temp_names(ts.target_directory) == sorted(item.name for item in leftovers)
    assert_planted_unchanged(ts)


def _only_for(path, op, error):
    """A seam op that raises ``error`` only for ``path`` (first positional argument)."""
    real = getattr(_fs._FS, op)

    def injected(*args):
        if args[0] == path:
            raise error
        return real(*args)

    return injected


def _is_temp(path) -> bool:
    return isinstance(path, str) and os.path.basename(path).startswith(".fc2tmp-") \
        and os.path.basename(path) != PLANTED_TEMP


class TempFd:
    """Learns the temporary's descriptor so tests can inject faults on it."""

    def __init__(self, monkeypatch):
        self.fd = None
        self.path = None
        real = _fs._FS.open

        def open_(path, flags, *rest):
            fd = real(path, flags, *rest)
            if _is_temp(path):
                self.fd, self.path = fd, path
            return fd

        inject(monkeypatch, open=open_)


class SourceFd:
    def __init__(self, monkeypatch, source):
        self.fd = None
        real = _fs._FS.open

        def open_(path, flags, *rest):
            fd = real(path, flags, *rest)
            if path == source:
                self.fd = fd
            return fd

        inject(monkeypatch, open=open_)


# --------------------------------------------------------------------------- SOURCE_OPEN / SOURCE_FD_VALIDATE


def test_source_open_failure(tmp_path, monkeypatch):
    ts = _scene(tmp_path, monkeypatch)
    inject(monkeypatch, open=_only_for(ts.source, "open", PermissionError(errno.EACCES, "denied")))
    outcome = _run(ts)
    _assert_pre_publish_failure(ts, outcome, _failure(F.MEDIA_SOURCE_OPEN_FAILED, T.SOURCE_OPEN, errno.EACCES))
    assert_source_not_lost(ts.source, ts.final, ts.sha256)


def test_source_fd_fstat_failure(tmp_path, monkeypatch):
    ts = _scene(tmp_path, monkeypatch)
    tracker = FdTracker(monkeypatch)
    inject(monkeypatch, fstat=failing(OSError(errno.EIO, "io")))
    outcome = _run(ts)
    _assert_pre_publish_failure(ts, outcome, _failure(F.MEDIA_SOURCE_OPEN_FAILED, T.SOURCE_FD_VALIDATE, errno.EIO))
    tracker.assert_all_closed()
    assert_source_not_lost(ts.source, ts.final, ts.sha256)


def test_source_fd_identity_differs_from_snapshot(tmp_path, monkeypatch):
    ts = _scene(tmp_path, monkeypatch)
    real = _fs._FS.fstat
    inject(monkeypatch, fstat=lambda fd: with_stat_fields(real(fd), st_ino=real(fd).st_ino + 5))
    tracker = FdTracker(monkeypatch)
    outcome = _run(ts)
    _assert_pre_publish_failure(ts, outcome, _failure(F.SOURCE_CHANGED, T.SOURCE_FD_VALIDATE))
    tracker.assert_all_closed()
    assert_source_not_lost(ts.source, ts.final, ts.sha256)


# --------------------------------------------------------------------------- TEMP_CREATE


def _tokens(monkeypatch, values):
    queue = list(values)
    real = _fs._FS.token
    inject(monkeypatch, token=lambda n: queue.pop(0) if queue else real(n))


def test_temp_name_collision_retries_with_a_new_token(tmp_path, monkeypatch):
    ts = _scene(tmp_path, monkeypatch)
    _tokens(monkeypatch, ["a" * 32])  # the planted unrelated temp already has this name
    log = SeamLog(monkeypatch)
    outcome = _run(ts)
    assert outcome.failure is None and [e.kind for e in outcome.effects] == [EffectKind.MEDIA_PUBLISHED,
                                                                           EffectKind.SOURCE_REMOVED]
    temp_opens = [c for c in log.ops("open") if os.path.basename(c[1]).startswith(".fc2tmp-")]
    assert len(temp_opens) == 2 and os.path.basename(temp_opens[0][1]) == PLANTED_TEMP
    assert all(c[1] != os.path.join(ts.target_directory, PLANTED_TEMP) for c in log.ops("unlink"))
    assert temp_names(ts.target_directory) == []
    assert_planted_unchanged(ts)
    assert_source_not_lost(ts.source, ts.final, ts.sha256)


def test_temp_name_collisions_exhausted_after_eight_names(tmp_path, monkeypatch):
    ts = _scene(tmp_path, monkeypatch)
    _tokens(monkeypatch, ["a" * 32] * 20)
    log = SeamLog(monkeypatch)
    tracker = FdTracker(monkeypatch)
    outcome = _run(ts)
    _assert_pre_publish_failure(ts, outcome, _failure(F.MEDIA_TEMP_CREATE_FAILED, T.TEMP_CREATE, errno.EEXIST))
    temp_opens = [c for c in log.ops("open") if os.path.basename(c[1]).startswith(".fc2tmp-")]
    assert len(temp_opens) == 8
    assert log.ops("unlink") == []  # the colliding file is not ours: never deleted
    tracker.assert_all_closed()
    assert_source_not_lost(ts.source, ts.final, ts.sha256)


def test_temp_create_other_error(tmp_path, monkeypatch):
    ts = _scene(tmp_path, monkeypatch)
    real = _fs._FS.open
    inject(monkeypatch, open=lambda path, flags, *rest: (_ for _ in ()).throw(PermissionError(errno.EACCES, "x"))
           if _is_temp(path) else real(path, flags, *rest))
    tracker = FdTracker(monkeypatch)
    outcome = _run(ts)
    _assert_pre_publish_failure(ts, outcome, _failure(F.MEDIA_TEMP_CREATE_FAILED, T.TEMP_CREATE, errno.EACCES))
    tracker.assert_all_closed()
    assert_source_not_lost(ts.source, ts.final, ts.sha256)


def test_malformed_token_fails_closed(tmp_path, monkeypatch):
    ts = _scene(tmp_path, monkeypatch)
    _tokens(monkeypatch, ["../../evil" + "0" * 22])
    outcome = _run(ts)
    _assert_pre_publish_failure(ts, outcome, _failure(F.MEDIA_TEMP_CREATE_FAILED, T.TEMP_CREATE, errno.EINVAL))
    assert_source_not_lost(ts.source, ts.final, ts.sha256)


def test_target_directory_replaced_before_temp_create(tmp_path, monkeypatch):
    ts = _scene(tmp_path, monkeypatch)
    real = _fs._FS.fstat
    calls = []

    def fstat(fd):
        calls.append(fd)
        if len(calls) == 1:  # right after the source fd validation, before the temp is created
            os.rename(ts.target_directory, ts.target_directory + "-moved")
            os.mkdir(ts.target_directory)
        return real(fd)

    inject(monkeypatch, fstat=fstat)
    outcome = _run(ts)
    assert outcome.failure == _failure(F.TARGET_DIRECTORY_CHANGED, T.TEMP_CREATE) and outcome.effects == ()
    assert os.listdir(ts.target_directory) == [] and _source_intact(ts)
    assert_source_not_lost(ts.source, ts.final, ts.sha256)


# --------------------------------------------------------------------------- READ


@pytest.mark.parametrize("fail_at", [1, 3])  # the first block / a middle block of four
def test_read_failure(tmp_path, monkeypatch, fail_at):
    ts = _scene(tmp_path, monkeypatch)
    real = _fs._FS.read
    count = []

    def read(fd, n):
        count.append(n)
        if len(count) == fail_at:
            raise OSError(errno.EIO, "read error")
        return real(fd, n)

    inject(monkeypatch, read=read)
    tracker = FdTracker(monkeypatch)
    outcome = _run(ts)
    _assert_pre_publish_failure(ts, outcome, _failure(F.MEDIA_READ_FAILED, T.READ, errno.EIO))
    tracker.assert_all_closed()
    assert_source_not_lost(ts.source, ts.final, ts.sha256)


def test_oversized_read_from_the_seam_fails_closed(tmp_path, monkeypatch):
    ts = _scene(tmp_path, monkeypatch)
    inject(monkeypatch, read=lambda fd, n: b"x" * (n + 1))
    outcome = _run(ts)
    _assert_pre_publish_failure(ts, outcome, _failure(F.MEDIA_READ_FAILED, T.READ, errno.EIO))
    assert_source_not_lost(ts.source, ts.final, ts.sha256)


# --------------------------------------------------------------------------- WRITE


def test_write_error(tmp_path, monkeypatch):
    ts = _scene(tmp_path, monkeypatch)
    real = _fs._FS.write
    count = []

    def write(fd, data):
        count.append(1)
        if len(count) == 2:
            raise OSError(errno.ENOSPC, "no space")
        return real(fd, data)

    inject(monkeypatch, write=write)
    tracker = FdTracker(monkeypatch)
    outcome = _run(ts)
    _assert_pre_publish_failure(ts, outcome, _failure(F.MEDIA_WRITE_FAILED, T.WRITE, errno.ENOSPC))
    tracker.assert_all_closed()
    assert_source_not_lost(ts.source, ts.final, ts.sha256)


def test_short_writes_continue_with_the_remainder(tmp_path, monkeypatch):
    ts = _scene(tmp_path, monkeypatch)
    real = _fs._FS.write
    sizes = []

    def short(fd, data):
        sizes.append(len(data))
        return real(fd, data[: max(1, len(data) // 3)])

    inject(monkeypatch, write=short)
    outcome = _run(ts)
    assert outcome.failure is None and outcome.media_sha256 == ts.sha256
    assert max(sizes) <= MIB and len(sizes) > 4 * 3
    assert sha256_of_file(ts.final) == ts.sha256 and not os.path.lexists(ts.source)
    assert temp_names(ts.target_directory) == []
    assert_planted_unchanged(ts)
    assert_source_not_lost(ts.source, ts.final, ts.sha256)


@pytest.mark.parametrize("bad_return", [0, -1, MIB + 1, None])
def test_zero_or_invalid_write_is_eio_and_never_loops(tmp_path, monkeypatch, bad_return):
    ts = _scene(tmp_path, monkeypatch)
    calls = []

    def write(fd, data):
        calls.append(len(data))
        return bad_return

    inject(monkeypatch, write=write)
    outcome = _run(ts)
    _assert_pre_publish_failure(ts, outcome, _failure(F.MEDIA_WRITE_FAILED, T.WRITE, errno.EIO))
    assert len(calls) == 1
    assert_source_not_lost(ts.source, ts.final, ts.sha256)


# --------------------------------------------------------------------------- FSYNC / CLOSE (temp)


def test_temp_fsync_failure(tmp_path, monkeypatch):
    ts = _scene(tmp_path, monkeypatch)
    inject(monkeypatch, fsync=failing(OSError(errno.EIO, "fsync")))
    tracker = FdTracker(monkeypatch)
    outcome = _run(ts)
    _assert_pre_publish_failure(ts, outcome, _failure(F.MEDIA_FSYNC_FAILED, T.FSYNC, errno.EIO))
    tracker.assert_all_closed()
    assert_source_not_lost(ts.source, ts.final, ts.sha256)


def test_temp_fstat_failure_after_fsync(tmp_path, monkeypatch):
    ts = _scene(tmp_path, monkeypatch)
    temp = TempFd(monkeypatch)
    real = _fs._FS.fstat
    inject(monkeypatch, fstat=lambda fd: (_ for _ in ()).throw(OSError(errno.EIO, "x")) if fd == temp.fd
           else real(fd))
    outcome = _run(ts)
    _assert_pre_publish_failure(ts, outcome, _failure(F.MEDIA_FSYNC_FAILED, T.FSYNC, errno.EIO))
    assert_source_not_lost(ts.source, ts.final, ts.sha256)


def test_temp_size_differs_after_fsync(tmp_path, monkeypatch):
    ts = _scene(tmp_path, monkeypatch)
    temp = TempFd(monkeypatch)
    real = _fs._FS.fstat
    inject(monkeypatch, fstat=lambda fd: with_stat_fields(real(fd), st_size=1) if fd == temp.fd else real(fd))
    outcome = _run(ts)
    _assert_pre_publish_failure(ts, outcome, _failure(F.MEDIA_WRITE_FAILED, T.FSYNC, errno.EIO))
    assert_source_not_lost(ts.source, ts.final, ts.sha256)


def test_temp_close_failure(tmp_path, monkeypatch):
    ts = _scene(tmp_path, monkeypatch)
    temp = TempFd(monkeypatch)
    real = _fs._FS.close

    def close(fd):
        real(fd)  # the descriptor is released, but the close reports an error
        if fd == temp.fd:
            raise OSError(errno.EIO, "close")

    inject(monkeypatch, close=close)
    tracker = FdTracker(monkeypatch)
    outcome = _run(ts)
    _assert_pre_publish_failure(ts, outcome, _failure(F.MEDIA_CLOSE_FAILED, T.CLOSE, errno.EIO))
    tracker.assert_all_closed()
    assert_source_not_lost(ts.source, ts.final, ts.sha256)


def test_source_close_failure(tmp_path, monkeypatch):
    ts = _scene(tmp_path, monkeypatch)
    source = SourceFd(monkeypatch, ts.source)
    real = _fs._FS.close

    def close(fd):
        real(fd)
        if fd == source.fd:
            raise OSError(errno.EIO, "close")

    inject(monkeypatch, close=close)
    outcome = _run(ts)
    _assert_pre_publish_failure(ts, outcome, _failure(F.MEDIA_CLOSE_FAILED, T.CLOSE, errno.EIO))
    assert_source_not_lost(ts.source, ts.final, ts.sha256)


# --------------------------------------------------------------------------- source mutation during copy


def _mutate_after_first_read(monkeypatch, mutate):
    real = _fs._FS.read
    count = []

    def read(fd, n):
        data = real(fd, n)
        count.append(1)
        if len(count) == 1:
            mutate()
        return data

    inject(monkeypatch, read=read)


def test_source_appended_during_copy(tmp_path, monkeypatch):
    ts = _scene(tmp_path, monkeypatch)

    def append():
        with open(ts.source, "ab") as handle:
            handle.write(b"appended while copying")

    _mutate_after_first_read(monkeypatch, append)
    outcome = _run(ts)
    assert outcome.failure == _failure(F.SOURCE_CHANGED_DURING_COPY, T.READ) and outcome.effects == ()
    assert not os.path.lexists(ts.final) and temp_names(ts.target_directory) == []
    with open(ts.source, "rb") as handle:
        assert handle.read() == _content() + b"appended while copying"  # source kept, never deleted
    assert_planted_unchanged(ts)
    assert_source_not_lost(ts.source, ts.final, hashlib.sha256(_content() + b"appended while copying").hexdigest())


def test_growing_source_aborts_as_soon_as_the_snapshot_size_is_exceeded(tmp_path, monkeypatch):
    # A source that never reaches EOF (e.g. still being written): the copy stops at the first block that
    # exceeds the snapshot size and never writes a byte beyond it into the temporary.
    ts = _scene(tmp_path, monkeypatch)
    reads, written = [], []
    real_write = _fs._FS.write

    def endless(fd, n):
        reads.append(n)
        if len(reads) > 50:
            raise AssertionError("the copy kept reading past the snapshot size")
        return b"g" * n

    def write(fd, data):
        written.append(len(data))
        return real_write(fd, data)

    inject(monkeypatch, read=endless, write=write)
    outcome = _run(ts)
    _assert_pre_publish_failure(ts, outcome, _failure(F.SOURCE_CHANGED_DURING_COPY, T.READ))
    assert len(reads) == SIZE // MIB + 1 and sum(written) <= SIZE
    assert_source_not_lost(ts.source, ts.final, ts.sha256)


def test_source_truncated_during_copy(tmp_path, monkeypatch):
    ts = _scene(tmp_path, monkeypatch)

    def truncate():
        with open(ts.source, "r+b") as handle:
            handle.truncate(MIB + 3)

    _mutate_after_first_read(monkeypatch, truncate)
    outcome = _run(ts)
    assert outcome.failure == _failure(F.SOURCE_CHANGED_DURING_COPY, T.READ) and outcome.effects == ()
    assert not os.path.lexists(ts.final) and temp_names(ts.target_directory) == []
    assert os.path.getsize(ts.source) == MIB + 3
    assert_planted_unchanged(ts)
    assert_source_not_lost(ts.source, ts.final, hashlib.sha256(_content()[: MIB + 3]).hexdigest())


def test_source_mtime_changed_during_copy(tmp_path, monkeypatch):
    ts = _scene(tmp_path, monkeypatch)
    st = os.lstat(ts.source)
    _mutate_after_first_read(monkeypatch, lambda: os.utime(ts.source, ns=(st.st_atime_ns,
                                                                           st.st_mtime_ns + 5_000_000_000)))
    tracker = FdTracker(monkeypatch)
    outcome = _run(ts)
    assert outcome.failure == _failure(F.SOURCE_CHANGED_DURING_COPY, T.SOURCE_FD_REVALIDATE)
    assert outcome.effects == () and not os.path.lexists(ts.final)
    assert temp_names(ts.target_directory) == [] and sha256_of_file(ts.source) == ts.sha256
    tracker.assert_all_closed()
    assert_planted_unchanged(ts)
    assert_source_not_lost(ts.source, ts.final, ts.sha256)


def test_source_fd_reports_another_inode_after_copy(tmp_path, monkeypatch):
    ts = _scene(tmp_path, monkeypatch)
    source = SourceFd(monkeypatch, ts.source)
    real = _fs._FS.fstat
    calls = []

    def fstat(fd):
        st = real(fd)
        if fd == source.fd:
            calls.append(fd)
            if len(calls) == 2:
                return with_stat_fields(st, st_ino=st.st_ino + 1)
        return st

    inject(monkeypatch, fstat=fstat)
    outcome = _run(ts)
    _assert_pre_publish_failure(ts, outcome, _failure(F.SOURCE_CHANGED_DURING_COPY, T.SOURCE_FD_REVALIDATE))
    assert_source_not_lost(ts.source, ts.final, ts.sha256)


def test_source_fd_revalidation_fstat_error(tmp_path, monkeypatch):
    ts = _scene(tmp_path, monkeypatch)
    source = SourceFd(monkeypatch, ts.source)
    real = _fs._FS.fstat
    calls = []

    def fstat(fd):
        if fd == source.fd:
            calls.append(fd)
            if len(calls) == 2:
                raise OSError(errno.EIO, "io")
        return real(fd)

    inject(monkeypatch, fstat=fstat)
    outcome = _run(ts)
    _assert_pre_publish_failure(ts, outcome, _failure(F.MEDIA_READ_FAILED, T.SOURCE_FD_REVALIDATE, errno.EIO))
    assert_source_not_lost(ts.source, ts.final, ts.sha256)


@pytest.mark.parametrize("strategy", ["rename", "link"])
def test_source_path_replaced_after_copy_is_never_deleted(tmp_path, monkeypatch, strategy):
    # The fd copy saw the original inode; the path now names a replacement (inode replacement).
    ts = _scene(tmp_path, monkeypatch, strategy)
    real = getattr(_fs._FS, strategy)

    def publish(temp, final):
        os.rename(ts.source, ts.source + ".original")
        with open(ts.source, "wb") as handle:
            handle.write(b"replacement")
        return real(temp, final)

    inject(monkeypatch, **{strategy: publish})
    outcome = _run(ts)
    assert [e.kind for e in outcome.effects] == [EffectKind.MEDIA_PUBLISHED]
    assert outcome.failure == _failure(F.SOURCE_CHANGED, T.SOURCE_PATH_REVALIDATE)
    with open(ts.source, "rb") as handle:
        assert handle.read() == b"replacement"
    assert sha256_of_file(ts.final) == ts.sha256 and outcome.media_sha256 == ts.sha256
    assert temp_names(ts.target_directory) == []
    assert_planted_unchanged(ts)
    assert_source_not_lost(ts.source, ts.final, ts.sha256)


def test_source_path_missing_after_publish(tmp_path, monkeypatch):
    ts = _scene(tmp_path, monkeypatch)
    real = _fs._FS.rename

    def publish(temp, final):
        os.rename(ts.source, ts.source + ".elsewhere")
        return real(temp, final)

    inject(monkeypatch, rename=publish)
    outcome = _run(ts)
    assert [e.kind for e in outcome.effects] == [EffectKind.MEDIA_PUBLISHED]
    assert outcome.failure == _failure(F.SOURCE_MISSING, T.SOURCE_PATH_REVALIDATE)
    assert_source_not_lost(ts.source, ts.final, ts.sha256)


# --------------------------------------------------------------------------- PUBLISH / PUBLISH_VERIFY


@pytest.mark.parametrize("strategy", ["rename", "link"])
@pytest.mark.parametrize("thief", ["file", "directory"])
def test_publish_race_target_stolen(tmp_path, monkeypatch, strategy, thief):
    ts = _scene(tmp_path, monkeypatch, strategy)
    real = getattr(_fs._FS, strategy)

    def publish(temp, final):
        if thief == "file":
            with open(final, "wb") as handle:
                handle.write(b"thief")
        else:
            os.mkdir(final)
        return real(temp, final)

    inject(monkeypatch, **{strategy: publish})
    tracker = FdTracker(monkeypatch)
    outcome = _run(ts)
    assert outcome.failure == _failure(F.TARGET_CONFLICT, T.PUBLISH) and outcome.effects == ()
    if thief == "file":
        with open(ts.final, "rb") as handle:
            assert handle.read() == b"thief"  # never replaced
    else:
        assert os.listdir(ts.final) == []
    assert temp_names(ts.target_directory) == [] and _source_intact(ts)
    tracker.assert_all_closed()
    assert_planted_unchanged(ts)
    assert_source_not_lost(ts.source, ts.final, ts.sha256)


@pytest.mark.parametrize("strategy", ["rename", "link"])
def test_publish_other_error(tmp_path, monkeypatch, strategy):
    ts = _scene(tmp_path, monkeypatch, strategy)
    inject(monkeypatch, **{strategy: failing(PermissionError(errno.EACCES, "denied"))})
    outcome = _run(ts)
    _assert_pre_publish_failure(ts, outcome, _failure(F.MEDIA_PUBLISH_FAILED, T.PUBLISH, errno.EACCES))
    assert_source_not_lost(ts.source, ts.final, ts.sha256)


def test_target_directory_replaced_before_publish(tmp_path, monkeypatch):
    ts = _scene(tmp_path, monkeypatch)
    temp = TempFd(monkeypatch)
    real = _fs._FS.close

    def close(fd):
        real(fd)
        if fd == temp.fd:  # after the temp is complete: replace the parent directory by a junction-free copy
            os.rename(ts.target_directory, ts.target_directory + "-moved")
            os.mkdir(ts.target_directory)

    inject(monkeypatch, close=close)
    log = SeamLog(monkeypatch)
    outcome = _run(ts)
    assert outcome.failure == _failure(F.TARGET_DIRECTORY_CHANGED, T.PUBLISH) and outcome.effects == ()
    assert log.ops("rename", "link") == [] and os.listdir(ts.target_directory) == []
    assert outcome.leftover_temporaries == ()  # ENOENT at the exact path: nothing left behind there
    assert _source_intact(ts)
    assert_source_not_lost(ts.source, ts.final, ts.sha256)


class TempIdentity:
    """Captures the verified temp identity of step 5 (fstat of the temp fd after fsync)."""

    def __init__(self, monkeypatch):
        self.temp = TempFd(monkeypatch)
        self.identity = None
        real = _fs._FS.fstat

        def fstat(fd):
            st = real(fd)
            if fd == self.temp.fd:
                self.identity = _fs._identity_of(st, EntryType.FILE)
            return st

        inject(monkeypatch, fstat=fstat)


@pytest.mark.parametrize("strategy", ["rename", "link"])
@pytest.mark.parametrize("field,value", [("st_ino", 1), ("st_size", 2)])
def test_publish_verification_failure_records_media_published_and_keeps_source(tmp_path, monkeypatch, strategy,
                                                                                field, value):
    # R-01 C: the no-replace publish succeeded -> MEDIA_PUBLISHED happened (verified temp identity, hash,
    # size); PUBLISHED_MEDIA_MISMATCH stops before the directory fsync / source unlink tail.
    ts = _scene(tmp_path, monkeypatch, strategy)
    captured = TempIdentity(monkeypatch)
    fake = FakeDirectoryFsync(monkeypatch, ts.target_directory)
    inject(monkeypatch, lstat=lstat_rewriting(ts.final, **{field: value}))
    log = SeamLog(monkeypatch)
    outcome = _run(ts)
    assert outcome.failure == _failure(F.PUBLISHED_MEDIA_MISMATCH, T.PUBLISH_VERIFY)
    assert [e.kind for e in outcome.effects] == [EffectKind.MEDIA_PUBLISHED]
    media = outcome.effects[0]
    assert captured.identity is not None and media.identity == captured.identity
    assert media.identity.inode != ts.source_identity.inode and media.size == ts.size
    assert media.sha256 == ts.sha256 == outcome.media_sha256 and outcome.media_size == ts.size
    assert outcome.leftover_temporaries == () and outcome.transfer_mode is CROSS
    assert all(c[1] != ts.source and c[1] != ts.final for c in log.ops("unlink"))  # no rollback, no source unlink
    last_verify = max(i for i, call in enumerate(log.calls) if call == ("lstat", ts.final))
    assert fake.events == [] and ("lstat", ts.source) not in log.calls[last_verify:]
    inject(monkeypatch, lstat=os.lstat)
    assert sha256_of_file(ts.final) == ts.sha256 and _source_intact(ts)
    assert temp_names(ts.target_directory) == []
    assert_source_not_lost(ts.source, ts.final, ts.sha256)


def test_really_changed_cross_volume_final_fails_closed_on_resume(tmp_path, monkeypatch):
    ts = _scene(tmp_path, monkeypatch, "rename")
    real = _fs._FS.rename

    def publish(temp, final):
        real(temp, final)
        with open(final, "ab") as handle:
            handle.write(b"changed")

    inject(monkeypatch, rename=publish)
    outcome = _run(ts)
    assert outcome.failure.kind is F.PUBLISHED_MEDIA_MISMATCH
    assert [e.kind for e in outcome.effects] == [EffectKind.MEDIA_PUBLISHED] and _source_intact(ts)
    blockers = mismatch_resume_blockers(ts, outcome, make_manifest(ts.plan), CROSS)
    assert PreflightBlockReason.COMPLETED_EFFECT_CHANGED in blockers
    assert_source_not_lost(ts.source, ts.final, ts.sha256)


# --------------------------------------------------------------------------- TEMP_CLEANUP


def test_posix_publish_temp_unlink_failure_is_partial_with_a_leftover(tmp_path, monkeypatch):
    ts = _scene(tmp_path, monkeypatch, "link")
    real = _fs._FS.unlink
    inject(monkeypatch, unlink=lambda path: (_ for _ in ()).throw(PermissionError(errno.EACCES, "x"))
           if _is_temp(path) else real(path))
    log = SeamLog(monkeypatch)
    outcome = _run(ts)
    [name] = temp_names(ts.target_directory)
    assert outcome.failure == _failure(F.MEDIA_TEMP_CLEANUP_FAILED, T.TEMP_CLEANUP, errno.EACCES, published=True)
    assert [e.kind for e in outcome.effects] == [EffectKind.MEDIA_PUBLISHED]
    assert outcome.leftover_temporaries == (LeftoverTemporary(PathRole.TARGET_DIRECTORY, name),)
    assert outcome.media_sha256 == ts.sha256 and outcome.media_size == ts.size
    assert [c for c in log.ops("unlink") if _is_temp(c[1])] == [("unlink", os.path.join(ts.target_directory,
                                                                                      name))]
    assert ("unlink", ts.source) not in log.calls and _source_intact(ts)  # the source is kept
    assert sha256_of_file(ts.final) == ts.sha256
    assert_planted_unchanged(ts)
    assert_source_not_lost(ts.source, ts.final, ts.sha256)


@pytest.mark.parametrize("cleanup_error", [PermissionError(errno.EACCES, "x"), OSError(errno.EIO, "y")])
def test_cleanup_failure_before_publish_keeps_the_primary_failure(tmp_path, monkeypatch, cleanup_error):
    ts = _scene(tmp_path, monkeypatch)
    real_unlink = _fs._FS.unlink
    inject(monkeypatch, unlink=lambda path: (_ for _ in ()).throw(cleanup_error) if _is_temp(path)
           else real_unlink(path))
    inject(monkeypatch, fsync=failing(OSError(errno.EIO, "fsync")))
    outcome = _run(ts)
    [name] = temp_names(ts.target_directory)
    _assert_pre_publish_failure(ts, outcome, _failure(F.MEDIA_FSYNC_FAILED, T.FSYNC, errno.EIO),
                                leftovers=(LeftoverTemporary(PathRole.TARGET_DIRECTORY, name),))
    assert_source_not_lost(ts.source, ts.final, ts.sha256)


# --------------------------------------------------------------------------- DIRECTORY_FSYNC


@pytest.mark.parametrize("where", ["open", "fsync", "close"])
def test_directory_fsync_failure_keeps_final_and_source_then_resume(tmp_path, monkeypatch, where):
    ts = _scene(tmp_path, monkeypatch, "link")
    error = OSError(errno.EIO, "dir")
    if where == "open":
        monkeypatch.setattr(transfer, "_DIRECTORY_FSYNC", True)
        inject(monkeypatch, open=_only_for(ts.target_directory, "open", error))
    else:
        FakeDirectoryFsync(monkeypatch, ts.target_directory, **{f"{where}_error": error})
    outcome = _run(ts)
    assert outcome.failure == _failure(F.TARGET_DIRECTORY_FSYNC_FAILED, T.DIRECTORY_FSYNC, errno.EIO)
    assert [e.kind for e in outcome.effects] == [EffectKind.MEDIA_PUBLISHED]
    assert _source_intact(ts) and sha256_of_file(ts.final) == ts.sha256
    assert temp_names(ts.target_directory) == []
    assert_source_not_lost(ts.source, ts.final, ts.sha256)
    fake = FakeDirectoryFsync(monkeypatch, ts.target_directory)
    inject(monkeypatch, open=fake_open_passthrough(ts.target_directory, fake))
    resumed = _run(ts, phase=TAIL)
    assert resumed.failure is None and [e.kind for e in resumed.effects] == [EffectKind.SOURCE_REMOVED]
    assert "fsync" in fake.events and not os.path.lexists(ts.source)
    assert_source_not_lost(ts.source, ts.final, ts.sha256)


def fake_open_passthrough(directory, fake):
    """Re-route ``open(directory)`` to the fake descriptor even if an earlier injection wraps it."""
    real = _fs._FS.open

    def open_(path, flags, *rest):
        if path == directory:
            fake.events.append("open")
            return FakeDirectoryFsync.FD
        return real(path, flags, *rest)

    return open_


# --------------------------------------------------------------------------- SOURCE_UNLINK / SAME_VOLUME_PRIMITIVE


@pytest.mark.parametrize("strategy", ["rename", "link"])
def test_source_unlink_failure_then_resume(tmp_path, monkeypatch, strategy):
    ts = _scene(tmp_path, monkeypatch, strategy)
    inject(monkeypatch, unlink=_only_for(ts.source, "unlink", PermissionError(errno.EACCES, "busy")))
    outcome = _run(ts)
    assert outcome.failure == _failure(F.SOURCE_UNLINK_FAILED, T.SOURCE_UNLINK, errno.EACCES)
    assert [e.kind for e in outcome.effects] == [EffectKind.MEDIA_PUBLISHED]
    assert _source_intact(ts) and sha256_of_file(ts.final) == ts.sha256  # final kept: no rollback
    assert temp_names(ts.target_directory) == []
    assert_source_not_lost(ts.source, ts.final, ts.sha256)
    inject(monkeypatch, unlink=os.unlink)
    resumed = _run(ts, phase=TAIL)
    assert resumed.failure is None and [e.kind for e in resumed.effects] == [EffectKind.SOURCE_REMOVED]
    assert resumed.transfer_mode is CROSS and not os.path.lexists(ts.source)
    assert_source_not_lost(ts.source, ts.final, ts.sha256)


@pytest.mark.parametrize("strategy", ["rename", "link"])
def test_same_volume_primitive_failure(tmp_path, monkeypatch, strategy):
    ts = _scene(tmp_path, monkeypatch, strategy)
    inject(monkeypatch, **{strategy: failing(PermissionError(errno.EPERM, "no hard links"))})
    outcome = _run(ts, mode=SAME)
    assert outcome.failure == _failure(F.MEDIA_TRANSFER_FAILED, T.SAME_VOLUME_PRIMITIVE, errno.EPERM)
    assert outcome.effects == () and outcome.transfer_mode is SAME and _source_intact(ts)
    assert not os.path.lexists(ts.final)
    assert_source_not_lost(ts.source, ts.final, ts.sha256)


def test_every_transfer_stage_is_injected_in_this_file():
    text = Path(__file__).read_text(encoding="utf-8")
    for stage in TransferStage:
        assert f"T.{stage.name}" in text, stage
    assert callable(assert_source_not_lost)


# --------------------------------------------------------------------------- fatal / foreign exceptions


class CustomFatal(BaseException):
    pass


FATALS = [KeyboardInterrupt, SystemExit, GeneratorExit, CustomFatal, RuntimeError, MemoryError]


def _raise_on(monkeypatch, op, exc, *, when):
    real = getattr(_fs._FS, op)
    count = []

    def injected(*args):
        if when(*args):
            count.append(1)
            if len(count) == 1:
                raise exc
        return real(*args)

    inject(monkeypatch, **{op: injected})


def _point(ts, name):
    """(seam op, predicate) for each pre-publish interruption point."""
    reads = []
    return {
        "source_open": ("open", lambda path, *a: path == ts.source),
        "temp_create": ("open", lambda path, *a: _is_temp(path)),
        "read_block_1": ("read", lambda fd, n: True),
        "read_block_3": ("read", lambda fd, n: reads.append(1) or len(reads) == 3),
        "write": ("write", lambda fd, data: True),
        "fsync": ("fsync", lambda fd: True),
        "publish": ("rename", lambda src, dst: _is_temp(src)),
    }[name]


PRE_PUBLISH_POINTS = ["source_open", "temp_create", "read_block_1", "read_block_3", "write", "fsync", "publish"]


@pytest.mark.parametrize("point", PRE_PUBLISH_POINTS)
@pytest.mark.parametrize("fatal", FATALS)
def test_fatal_exception_before_publish_propagates_same_object(tmp_path, monkeypatch, point, fatal):
    ts = _scene(tmp_path, monkeypatch)
    exc = fatal("interrupted")
    op, when = _point(ts, point)
    _raise_on(monkeypatch, op, exc, when=when)
    tracker = FdTracker(monkeypatch)
    log = SeamLog(monkeypatch)
    with pytest.raises(fatal) as info:
        _run(ts)
    assert info.value is exc and exc.__cause__ is None
    tracker.assert_all_closed()
    temp_unlinks = [c for c in log.ops("unlink") if _is_temp(c[1])]
    temp_creates = [c for c in log.ops("open") if _is_temp(c[1])]
    created = point not in ("source_open", "temp_create")
    assert len(temp_unlinks) == (1 if created else 0)  # the owned temp is removed exactly once
    if created:
        assert temp_unlinks[0][1] == temp_creates[-1][1]
    assert ("unlink", ts.source) not in log.calls
    assert temp_names(ts.target_directory) == [] and not os.path.lexists(ts.final)
    assert _source_intact(ts)
    assert_planted_unchanged(ts)
    assert_source_not_lost(ts.source, ts.final, ts.sha256)


@pytest.mark.parametrize("fatal", [KeyboardInterrupt, CustomFatal, RuntimeError])
def test_fatal_during_posix_publish_temp_unlink_keeps_the_final(tmp_path, monkeypatch, fatal):
    ts = _scene(tmp_path, monkeypatch, "link")
    exc = fatal("stop")
    _raise_on(monkeypatch, "unlink", exc, when=lambda path: _is_temp(path))
    log = SeamLog(monkeypatch)
    with pytest.raises(fatal) as info:
        _run(ts)
    assert info.value is exc
    assert len([c for c in log.ops("unlink") if _is_temp(c[1])]) == 1  # ownership ended: not retried
    assert sha256_of_file(ts.final) == ts.sha256 and _source_intact(ts)  # the final is never deleted
    assert_planted_unchanged(ts)
    assert_source_not_lost(ts.source, ts.final, ts.sha256)


@pytest.mark.parametrize("point", ["directory_fsync", "source_revalidate", "source_unlink"])
@pytest.mark.parametrize("fatal", [KeyboardInterrupt, SystemExit, CustomFatal])
def test_fatal_after_publish_keeps_final_and_source(tmp_path, monkeypatch, point, fatal):
    ts = _scene(tmp_path, monkeypatch, "link")
    exc = fatal("late")
    fake = FakeDirectoryFsync(monkeypatch, ts.target_directory)
    if point == "directory_fsync":
        _raise_on(monkeypatch, "fsync", exc, when=lambda fd: fd == FakeDirectoryFsync.FD)
    elif point == "source_revalidate":
        _raise_on(monkeypatch, "lstat", exc, when=lambda path: path == ts.source and os.path.exists(ts.final))
    else:
        _raise_on(monkeypatch, "unlink", exc, when=lambda path: path == ts.source)
    with pytest.raises(fatal) as info:
        _run(ts)
    assert info.value is exc
    if point == "directory_fsync":
        assert fake.events == ["open", "close"]  # the directory descriptor is closed before propagating
    assert sha256_of_file(ts.final) == ts.sha256 and _source_intact(ts)
    assert temp_names(ts.target_directory) == []
    assert_planted_unchanged(ts)
    assert_source_not_lost(ts.source, ts.final, ts.sha256)


@pytest.mark.parametrize("secondary", [OSError(errno.EACCES, "x"), KeyboardInterrupt("second")])
def test_cleanup_failure_never_masks_the_fatal_exception(tmp_path, monkeypatch, secondary):
    ts = _scene(tmp_path, monkeypatch)
    exc = CustomFatal("primary")
    _raise_on(monkeypatch, "write", exc, when=lambda fd, data: True)
    real_unlink, real_close = _fs._FS.unlink, _fs._FS.close

    def unlink(path):
        if _is_temp(path):
            raise secondary
        return real_unlink(path)

    closes = []

    def close(fd):
        closes.append(fd)
        real_close(fd)
        raise secondary

    inject(monkeypatch, unlink=unlink, close=close)
    with pytest.raises(CustomFatal) as info:
        _run(ts)
    assert info.value is exc and len(closes) == 2  # both descriptors were still closed
    [name] = temp_names(ts.target_directory)  # the failed cleanup leaves the named temp behind
    assert name.startswith(".fc2tmp-") and _source_intact(ts) and not os.path.lexists(ts.final)
    assert_planted_unchanged(ts)
    assert_source_not_lost(ts.source, ts.final, ts.sha256)


@pytest.mark.parametrize("strategy", ["rename", "link"])
@pytest.mark.parametrize("fatal", [KeyboardInterrupt, CustomFatal, RuntimeError])
def test_fatal_in_same_volume_primitive_propagates(tmp_path, monkeypatch, strategy, fatal):
    ts = _scene(tmp_path, monkeypatch, strategy)
    exc = fatal("sv")
    inject(monkeypatch, **{strategy: failing(exc)})
    with pytest.raises(fatal) as info:
        _run(ts, mode=SAME)
    assert info.value is exc and _source_intact(ts) and not os.path.lexists(ts.final)
    assert_planted_unchanged(ts)
    assert_source_not_lost(ts.source, ts.final, ts.sha256)


def test_failures_carry_no_path_token_or_exception_text(tmp_path, monkeypatch):
    ts = _scene(tmp_path, monkeypatch, "link")
    secret = "SECRET-OSERROR-TEXT"
    inject(monkeypatch, unlink=lambda path: (_ for _ in ()).throw(PermissionError(errno.EACCES, secret, path)))
    outcome = _run(ts)
    text = repr(outcome.failure) + str(outcome.failure)
    assert secret not in text and ts.target_directory not in text and ".fc2tmp-" not in text
    for value in (getattr(outcome.failure, name) for name in outcome.failure.__slots__):
        assert not isinstance(value, BaseException)
    assert outcome.failure.kind is F.MEDIA_TEMP_CLEANUP_FAILED
    assert_source_not_lost(ts.source, ts.final, ts.sha256)


# --------------------------------------------------------------------------- meta


def test_every_failure_test_asserts_the_core_invariant():
    tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
    tests = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")]
    assert len(tests) >= 40 and callable(assert_source_not_lost)
    for fn in tests:
        names = {n.id for n in ast.walk(fn) if isinstance(n, ast.Name)}
        assert "assert_source_not_lost" in names, fn.name


# --------------------------------------------------------------------------- R-02: foreign exception from close()


def _close_raising_once(monkeypatch, fd_of, exc):
    """``close(fd)`` raises ``exc`` the first time it is called for ``fd_of()`` WITHOUT releasing the
    descriptor (an interrupted close); every other close is real. Returns the ordered close log."""
    real = _fs._FS.close
    log: list[tuple[int, str]] = []

    def close(fd):
        if fd == fd_of() and not any(entry[0] == fd for entry in log):
            log.append((fd, "raised"))
            raise exc
        log.append((fd, "closed"))
        return real(fd)

    inject(monkeypatch, close=close)
    return log


def _assert_released(*fds):
    for fd in fds:
        with pytest.raises(OSError):
            os.fstat(fd)


def test_foreign_exception_from_temp_fd_close_keeps_fd_ownership(tmp_path, monkeypatch):
    # R-02 A: step 5 close(temp) raises; the temp fd is still owned, so the fatal cleanup closes it again.
    ts = _scene(tmp_path, monkeypatch)
    temp = TempFd(monkeypatch)
    source = SourceFd(monkeypatch, ts.source)
    exc = CustomFatal("temp close")
    closes = _close_raising_once(monkeypatch, lambda: temp.fd, exc)
    log = SeamLog(monkeypatch)
    with pytest.raises(CustomFatal) as info:
        _run(ts)
    assert info.value is exc
    assert closes == [(temp.fd, "raised"), (temp.fd, "closed"), (source.fd, "closed")]
    _assert_released(temp.fd, source.fd)
    assert [c for c in log.ops("unlink") if _is_temp(c[1])] == [("unlink", temp.path)]  # exactly once
    assert log.ops("rename", "link") == [] and not os.path.lexists(ts.final)
    assert temp_names(ts.target_directory) == [] and _source_intact(ts)
    assert_planted_unchanged(ts)
    assert_source_not_lost(ts.source, ts.final, ts.sha256)


@pytest.mark.parametrize("foreign", [RuntimeError, KeyboardInterrupt, GeneratorExit])
def test_foreign_exception_from_source_fd_close_keeps_fd_ownership(tmp_path, monkeypatch, foreign):
    # R-02 B: step 6 close(source) raises; the fatal cleanup closes the source fd again, the temp once.
    ts = _scene(tmp_path, monkeypatch)
    temp = TempFd(monkeypatch)
    source = SourceFd(monkeypatch, ts.source)
    exc = foreign("source close")
    closes = _close_raising_once(monkeypatch, lambda: source.fd, exc)
    log = SeamLog(monkeypatch)
    with pytest.raises(foreign) as info:
        _run(ts)
    assert info.value is exc
    assert closes == [(temp.fd, "closed"), (source.fd, "raised"), (source.fd, "closed")]
    _assert_released(temp.fd, source.fd)
    assert [c for c in log.ops("unlink") if _is_temp(c[1])] == [("unlink", temp.path)]
    assert log.ops("rename", "link") == [] and not os.path.lexists(ts.final)  # not yet published
    assert _source_intact(ts)
    assert_planted_unchanged(ts)
    assert_source_not_lost(ts.source, ts.final, ts.sha256)


@pytest.mark.parametrize("mode", [SAME, CROSS])
def test_foreign_exception_from_directory_fd_close_gets_a_quiet_close(tmp_path, monkeypatch, mode):
    # R-02 C: the directory fd close raises; one quiet close attempt, then the same object propagates.
    ts = _scene(tmp_path, monkeypatch, "link")
    exc = CustomFatal("directory close")
    fake = FakeDirectoryFsync(monkeypatch, ts.target_directory, close_error=exc)
    log = SeamLog(monkeypatch)
    with pytest.raises(CustomFatal) as info:
        _run(ts, mode=mode)
    assert info.value is exc
    assert fake.events == ["open", "fsync", "close", "close"]
    closes = [c for c in log.ops("close") if c[1] == FakeDirectoryFsync.FD]
    assert len(closes) == 2
    assert ("unlink", ts.source) not in log.calls  # stopped before the source unlink; nothing rolled back
    assert sha256_of_file(ts.final) == ts.sha256 and _source_intact(ts)
    assert temp_names(ts.target_directory) == []
    assert_planted_unchanged(ts)
    assert_source_not_lost(ts.source, ts.final, ts.sha256)


def test_foreign_exception_from_typed_failure_cleanup_close_propagates(tmp_path, monkeypatch):
    # R-02 D: a typed OSError (temp fsync) starts the typed cleanup; its close(temp) raises a foreign
    # exception, which propagates as the same object (not swallowed into MEDIA_FSYNC_FAILED), and the
    # remaining cleanup still happens: temp fd closed again, source fd closed, owned temp unlinked once.
    ts = _scene(tmp_path, monkeypatch)
    temp = TempFd(monkeypatch)
    source = SourceFd(monkeypatch, ts.source)
    inject(monkeypatch, fsync=failing(OSError(errno.EIO, "fsync")))
    exc = KeyboardInterrupt("cleanup close")
    closes = _close_raising_once(monkeypatch, lambda: temp.fd, exc)
    log = SeamLog(monkeypatch)
    with pytest.raises(KeyboardInterrupt) as info:
        _run(ts)
    assert info.value is exc
    assert closes == [(temp.fd, "raised"), (temp.fd, "closed"), (source.fd, "closed")]
    _assert_released(temp.fd, source.fd)
    assert [c for c in log.ops("unlink") if _is_temp(c[1])] == [("unlink", temp.path)]
    assert temp_names(ts.target_directory) == [] and not os.path.lexists(ts.final) and _source_intact(ts)
    assert_planted_unchanged(ts)
    assert_source_not_lost(ts.source, ts.final, ts.sha256)


def test_oserror_from_close_is_still_a_typed_failure_without_retry(tmp_path, monkeypatch):
    # OSError close semantics are unchanged: MEDIA_CLOSE_FAILED, ownership ends, no second close.
    ts = _scene(tmp_path, monkeypatch)
    temp = TempFd(monkeypatch)
    real = _fs._FS.close
    temp_closes = []

    def close(fd):
        real(fd)  # released, but reported as failed
        if fd == temp.fd:
            temp_closes.append(fd)
            raise OSError(errno.EIO, "close")

    inject(monkeypatch, close=close)
    outcome = _run(ts)
    _assert_pre_publish_failure(ts, outcome, _failure(F.MEDIA_CLOSE_FAILED, T.CLOSE, errno.EIO))
    assert temp_closes == [temp.fd]  # ownership ended with the OSError: no second close of that fd
    assert_source_not_lost(ts.source, ts.final, ts.sha256)
