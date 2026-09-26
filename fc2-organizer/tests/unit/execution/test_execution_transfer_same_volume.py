"""P4-C7 S3: same-volume media move (contract sections 17, 18, 23, 26; construction plan S3).

Windows strategy ``rename`` runs natively on a Windows host; the POSIX strategy ``link`` runs through the
private seam ``transfer._SAME_VOLUME_STRATEGY`` on any host (directory fsync through a fake descriptor where
the host cannot open directories) and natively only on a POSIX host (skipped and recorded otherwise).
"""

from __future__ import annotations

import errno
import hashlib
import os
import stat
from pathlib import Path

import pytest

from fc2_organizer.execution import (
    CompletedEffect,
    EffectKind,
    EntryIdentity,
    EntryType,
    ExecutionFailure,
    ExecutionFailureKind,
    ExecutionInputError,
    ExecutionModelError,
    ExecutionStep,
    LeftoverTemporary,
    PathRole,
    PreflightBlockReason,
    TransferMode,
    TransferStage,
)
from fc2_organizer.execution import _fs, transfer
from fc2_organizer.execution.transfer import ResumePhase, TransferOutcome, transfer_media

from ._builders import make_manifest
from ._helpers import (
    FakeDirectoryFsync,
    SeamLog,
    mismatch_resume_blockers,
    assert_planted_unchanged,
    assert_source_not_lost,
    failing,
    inject,
    lstat_rewriting,
    sha256_of_file,
    temp_names,
    transfer_scene,
    try_junction,
    try_symlink,
    use_strategy,
)

F = ExecutionFailureKind
SAME = TransferMode.SAME_VOLUME
CROSS = TransferMode.CROSS_VOLUME
FULL = ResumePhase.FULL
TAIL = ResumePhase.SOURCE_REMOVAL_ONLY
CONTENT = b"same-volume media bytes \x00\xff" * 97
STRATEGIES = ("rename", "link")


def _run(ts, mode=SAME, phase=FULL):
    return transfer_media(ts.plan, ts.source_identity, ts.target_identity, mode, resume_phase=phase)


def _file_bytes(path) -> bytes:
    with open(path, "rb") as handle:
        return handle.read()


def _assert_success(ts, outcome, *, mode=SAME, sha=None):
    assert outcome.failure is None
    assert outcome.transfer_mode is mode
    assert [e.kind for e in outcome.effects] == [EffectKind.MEDIA_PUBLISHED, EffectKind.SOURCE_REMOVED]
    media, removed = outcome.effects
    assert media.role is PathRole.TARGET_MEDIA and media.path == ts.final and media.size == ts.size
    assert media.identity == _fs.snapshot(ts.final) and media.sha256 == sha
    assert removed == CompletedEffect(EffectKind.SOURCE_REMOVED, PathRole.SOURCE, ts.source, None, None, None,
                                      None, None)
    assert outcome.media_size == ts.size and outcome.media_sha256 == sha and outcome.leftover_temporaries == ()
    assert not os.path.lexists(ts.source)
    assert sha256_of_file(ts.final) == ts.sha256
    assert temp_names(ts.target_directory) == []
    assert_planted_unchanged(ts)
    assert_source_not_lost(ts.source, ts.final, ts.sha256)


def _assert_nothing_moved(ts, outcome, kind, *, stage=None, errno_=None):
    assert outcome.effects == () and outcome.leftover_temporaries == ()
    assert outcome.failure == ExecutionFailure(step=ExecutionStep.MOVE_MEDIA, kind=kind, stage=stage, errno=errno_)
    assert _fs.snapshot(ts.source) == ts.source_identity and sha256_of_file(ts.source) == ts.sha256
    assert temp_names(ts.target_directory) == []
    assert_planted_unchanged(ts)
    assert_source_not_lost(ts.source, ts.final, ts.sha256)


# --------------------------------------------------------------------------- success


@pytest.mark.skipif(os.name != "nt", reason="native Windows rename strategy runs on a Windows host only")
def test_windows_native_rename_publishes_and_removes_source_in_one_atomic_step(tmp_path):
    ts = transfer_scene(tmp_path, content=CONTENT)
    assert transfer._SAME_VOLUME_STRATEGY == "rename"
    outcome = _run(ts)
    _assert_success(ts, outcome)
    assert outcome.effects[0].identity == ts.source_identity  # rename keeps the file id, size and mtime


def test_rename_strategy_call_sequence_has_no_link_unlink_or_directory_fsync(tmp_path, monkeypatch):
    use_strategy(monkeypatch, "rename")
    ts = transfer_scene(tmp_path, content=CONTENT)
    log = SeamLog(monkeypatch)
    _assert_success(ts, _run(ts))
    assert log.ops("rename", "link", "unlink", "open", "fsync", "write") == [("rename", ts.source)]


def test_link_strategy_success_in_strict_order(tmp_path, monkeypatch):
    use_strategy(monkeypatch, "link")
    ts = transfer_scene(tmp_path, content=CONTENT)
    fake = FakeDirectoryFsync(monkeypatch, ts.target_directory)
    log = SeamLog(monkeypatch)
    outcome = _run(ts)
    transfer_calls = len(log.calls)  # the assertions below probe the filesystem too
    _assert_success(ts, outcome)
    del log.calls[transfer_calls:]
    assert outcome.effects[0].identity == ts.source_identity  # link keeps inode, size and mtime
    linked = log.index("link", ts.source)
    verified = log.index("lstat", ts.final, linked)
    opened = log.index("open", ts.target_directory, verified)
    synced = log.index("fsync", FakeDirectoryFsync.FD, opened)
    closed = log.index("close", FakeDirectoryFsync.FD, synced)
    revalidated = log.index("lstat", ts.source, closed)
    unlinked = log.index("unlink", ts.source, revalidated)
    assert unlinked == len(log.calls) - 1 and fake.events == ["open", "fsync", "close"]
    assert log.ops("rename", "link", "unlink") == [("link", ts.source), ("unlink", ts.source)]


@pytest.mark.skipif(os.name != "nt", reason="the Windows host has no directory fsync")
def test_link_strategy_on_windows_host_performs_no_directory_fsync(tmp_path, monkeypatch):
    use_strategy(monkeypatch, "link")
    ts = transfer_scene(tmp_path, content=CONTENT)
    log = SeamLog(monkeypatch)
    _assert_success(ts, _run(ts))
    assert log.ops("open", "fsync") == []


@pytest.mark.skipif(os.name == "nt", reason="native POSIX link strategy: NOT EXECUTED on a Windows host")
def test_posix_native_link_strategy_with_real_directory_fsync(tmp_path, monkeypatch):
    ts = transfer_scene(tmp_path, content=CONTENT)
    assert transfer._SAME_VOLUME_STRATEGY == "link" and transfer._DIRECTORY_FSYNC
    log = SeamLog(monkeypatch)
    _assert_success(ts, _run(ts))
    linked = log.index("link", ts.source)
    opened = log.index("open", ts.target_directory, linked)
    log.index("unlink", ts.source, opened)


@pytest.mark.parametrize("strategy", STRATEGIES)
def test_zero_byte_media(tmp_path, monkeypatch, strategy):
    use_strategy(monkeypatch, strategy)
    ts = transfer_scene(tmp_path, content=b"")
    outcome = _run(ts)
    _assert_success(ts, outcome)
    assert outcome.media_size == 0 and _file_bytes(ts.final) == b""


UNICODE_NAMES = [
    ("下载-かな-😀.MP4", "库-ライブラリ"),
    ("e\u0301te\u0301-nfd.mkv", "bibliothe\u0300que"),
    ("\u00e9t\u00e9-nfc.Mp4", "biblioth\u00e8que"),
]


@pytest.mark.parametrize("strategy", STRATEGIES)
@pytest.mark.parametrize("source_name,library_name", UNICODE_NAMES)
def test_unicode_paths(tmp_path, monkeypatch, strategy, source_name, library_name):
    use_strategy(monkeypatch, strategy)
    ts = transfer_scene(tmp_path, content=CONTENT, source_name=source_name, library_name=library_name)
    _assert_success(ts, _run(ts))
    assert _file_bytes(ts.final) == CONTENT


# --------------------------------------------------------------------------- target conflicts (never replaced)


def _plant_file(path, data=b"someone else's file"):
    with open(path, "wb") as handle:
        handle.write(data)
    return data, os.lstat(path).st_ino, os.lstat(path).st_mtime_ns


def _planted(path):
    st = os.lstat(path)
    return _file_bytes(path), st.st_ino, st.st_mtime_ns


@pytest.mark.parametrize("strategy", STRATEGIES)
def test_existing_target_file_is_a_conflict_and_untouched(tmp_path, monkeypatch, strategy):
    use_strategy(monkeypatch, strategy)
    ts = transfer_scene(tmp_path, content=CONTENT)
    before = _plant_file(ts.final)
    outcome = _run(ts)
    _assert_nothing_moved(ts, outcome, F.TARGET_CONFLICT)
    assert _planted(ts.final) == before


@pytest.mark.parametrize("strategy", STRATEGIES)
def test_existing_target_directory_is_a_conflict(tmp_path, monkeypatch, strategy):
    use_strategy(monkeypatch, strategy)
    ts = transfer_scene(tmp_path, content=CONTENT)
    os.mkdir(ts.final)
    _assert_nothing_moved(ts, _run(ts), F.TARGET_CONFLICT)
    assert os.path.isdir(ts.final) and os.listdir(ts.final) == []


@pytest.mark.parametrize("strategy", STRATEGIES)
def test_existing_target_junction_is_a_conflict(tmp_path, monkeypatch, strategy):
    use_strategy(monkeypatch, strategy)
    ts = transfer_scene(tmp_path, content=CONTENT)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    try_junction(Path(ts.final), elsewhere)
    _assert_nothing_moved(ts, _run(ts), F.TARGET_CONFLICT)
    assert _fs.is_link(os.lstat(ts.final)) and os.listdir(elsewhere) == []


@pytest.mark.parametrize("strategy", STRATEGIES)
def test_existing_target_symlink_is_a_conflict(tmp_path, monkeypatch, strategy):
    use_strategy(monkeypatch, strategy)
    ts = transfer_scene(tmp_path, content=CONTENT)
    try_symlink(Path(ts.final), tmp_path / "dangling")
    _assert_nothing_moved(ts, _run(ts), F.TARGET_CONFLICT)
    assert os.path.islink(ts.final)


@pytest.mark.parametrize("strategy", STRATEGIES)
@pytest.mark.parametrize("planted", ["file", "directory"])
def test_target_planted_after_the_early_check_is_refused_by_the_primitive_itself(tmp_path, monkeypatch, strategy,
                                                                                 planted):
    # The no-overwrite guarantee comes from the primitive, not from the early check (contract section 18.1).
    use_strategy(monkeypatch, strategy)
    ts = transfer_scene(tmp_path, content=CONTENT)
    real = getattr(_fs._FS, strategy)

    def racing(source, final):
        if planted == "file":
            _plant_file(final)
        else:
            os.mkdir(final)
        return real(source, final)

    inject(monkeypatch, **{strategy: racing})
    outcome = _run(ts)
    _assert_nothing_moved(ts, outcome, F.TARGET_CONFLICT, stage=TransferStage.SAME_VOLUME_PRIMITIVE)
    if planted == "file":
        assert _file_bytes(ts.final) == b"someone else's file"
    else:
        assert os.path.isdir(ts.final) and os.listdir(ts.final) == []


# --------------------------------------------------------------------------- EXDEV fallback


@pytest.mark.parametrize("strategy", STRATEGIES)
@pytest.mark.parametrize("exdev", [
    OSError(errno.EXDEV, "cross-device"),
    OSError(errno.EXDEV, "not same device", None, 17),
])
def test_exdev_falls_back_to_cross_volume_exactly_once(tmp_path, monkeypatch, strategy, exdev):
    use_strategy(monkeypatch, strategy)
    ts = transfer_scene(tmp_path, content=CONTENT)
    real = getattr(_fs._FS, strategy)
    primitive_calls = []

    def primitive(source, final):
        if source == ts.source:
            primitive_calls.append(source)
            raise exdev
        return real(source, final)

    inject(monkeypatch, **{strategy: primitive})
    outcome = _run(ts)
    _assert_success(ts, outcome, mode=CROSS, sha=hashlib.sha256(CONTENT).hexdigest())
    assert primitive_calls == [ts.source]
    assert _file_bytes(ts.final) == CONTENT


@pytest.mark.parametrize("strategy", STRATEGIES)
def test_exdev_again_during_the_fallback_publish_is_not_retried(tmp_path, monkeypatch, strategy):
    use_strategy(monkeypatch, strategy)
    ts = transfer_scene(tmp_path, content=CONTENT)
    calls = []

    def always_exdev(source, final):
        calls.append(source)
        raise OSError(errno.EXDEV, "cross-device")

    inject(monkeypatch, **{strategy: always_exdev})
    outcome = _run(ts)
    assert outcome.transfer_mode is CROSS and outcome.effects == ()
    assert outcome.failure.kind is F.MEDIA_PUBLISH_FAILED and outcome.failure.errno == errno.EXDEV
    assert len(calls) == 2 and calls[0] == ts.source and os.path.basename(calls[1]).startswith(".fc2tmp-")
    assert temp_names(ts.target_directory) == [] and not os.path.lexists(ts.final)
    assert_planted_unchanged(ts)
    assert_source_not_lost(ts.source, ts.final, ts.sha256)


# --------------------------------------------------------------------------- primitive failures


def _sharing_violation():
    return PermissionError(errno.EACCES, "sharing violation", None, 32)


@pytest.mark.parametrize("strategy", STRATEGIES)
@pytest.mark.parametrize("error", [
    PermissionError(errno.EPERM, "operation not permitted"),
    OSError(errno.ENOTSUP, "not supported"),
    OSError(getattr(errno, "EOPNOTSUPP", errno.ENOTSUP), "op not supported"),
    OSError(errno.EMLINK, "too many links"),
    _sharing_violation(),
])
def test_other_primitive_errors_are_media_transfer_failed_without_effect(tmp_path, monkeypatch, strategy, error):
    use_strategy(monkeypatch, strategy)
    ts = transfer_scene(tmp_path, content=CONTENT)
    inject(monkeypatch, **{strategy: failing(error)})
    log = SeamLog(monkeypatch)
    outcome = _run(ts)
    _assert_nothing_moved(ts, outcome, F.MEDIA_TRANSFER_FAILED, stage=TransferStage.SAME_VOLUME_PRIMITIVE,
                          errno_=error.errno)
    assert log.ops("rename", "link", "unlink", "open") == [(strategy, ts.source)]  # never a rename fallback
    assert not os.path.lexists(ts.final)


@pytest.mark.skipif(os.name != "nt", reason="native Windows sharing violation")
def test_windows_native_sharing_violation_on_an_open_source(tmp_path, monkeypatch):
    import _winapi

    ts = transfer_scene(tmp_path, content=CONTENT)
    handle = _winapi.CreateFile(ts.source, _winapi.GENERIC_READ, 0, 0, _winapi.OPEN_EXISTING, 0, 0)
    try:
        outcome = _run(ts)
    finally:
        _winapi.CloseHandle(handle)
    assert outcome.effects == () and outcome.failure.kind is F.MEDIA_TRANSFER_FAILED
    assert outcome.failure.stage is TransferStage.SAME_VOLUME_PRIMITIVE and outcome.failure.errno is not None
    assert not os.path.lexists(ts.final)
    assert_source_not_lost(ts.source, ts.final, ts.sha256)


# --------------------------------------------------------------------------- after the primitive


VERIFY_FAULTS = {
    "identity_mismatch": lambda ts: lstat_rewriting(ts.final, st_ino=ts.source_identity.inode + 99),
    "lstat_error": lambda ts: _lstat_failing_for_after_publish(ts),
}


def _lstat_failing_for_after_publish(ts):
    # The early check needs lstat(final) -> FileNotFoundError; once the final exists, lstat fails with EIO.
    real = _fs._FS.lstat

    def lstat(candidate):
        if candidate == ts.final and os.path.lexists(ts.final):
            raise OSError(errno.EIO, "io")
        return real(candidate)

    return lstat


@pytest.mark.parametrize("fault", sorted(VERIFY_FAULTS))
def test_rename_post_publish_mismatch_records_both_real_effects(tmp_path, monkeypatch, fault):
    # R-01 A (Frozen 18.2): the atomic rename already published the final AND removed the source name.
    use_strategy(monkeypatch, "rename")
    ts = transfer_scene(tmp_path, content=CONTENT)
    inject(monkeypatch, lstat=VERIFY_FAULTS[fault](ts))
    log = SeamLog(monkeypatch)
    outcome = _run(ts)
    assert outcome.failure == ExecutionFailure(step=ExecutionStep.MOVE_MEDIA, kind=F.PUBLISHED_MEDIA_MISMATCH,
                                               stage=TransferStage.PUBLISH_VERIFY)
    assert [e.kind for e in outcome.effects] == [EffectKind.MEDIA_PUBLISHED, EffectKind.SOURCE_REMOVED]
    media, removed = outcome.effects
    assert media.identity == ts.source_identity and media.size == ts.size and media.sha256 is None
    assert media.path == ts.final and removed.path == ts.source
    assert outcome.media_size == ts.size and outcome.media_sha256 is None and outcome.transfer_mode is SAME
    assert log.ops("unlink", "link", "open") == [] and log.ops("rename") == [("rename", ts.source)]  # no rollback
    assert not os.path.lexists(ts.source) and os.path.lexists(ts.final)
    inject(monkeypatch, lstat=os.lstat)
    assert sha256_of_file(ts.final) == ts.sha256  # the final is never deleted
    assert_planted_unchanged(ts)
    assert_source_not_lost(ts.source, ts.final, ts.sha256)


@pytest.mark.parametrize("fault", sorted(VERIFY_FAULTS))
def test_link_post_link_mismatch_records_media_published_and_keeps_source(tmp_path, monkeypatch, fault):
    # R-01 B: link succeeded -> MEDIA_PUBLISHED happened; the source is kept and never unlinked.
    use_strategy(monkeypatch, "link")
    ts = transfer_scene(tmp_path, content=CONTENT)
    fake = FakeDirectoryFsync(monkeypatch, ts.target_directory)
    inject(monkeypatch, lstat=VERIFY_FAULTS[fault](ts))
    log = SeamLog(monkeypatch)
    outcome = _run(ts)
    assert outcome.failure == ExecutionFailure(step=ExecutionStep.MOVE_MEDIA, kind=F.PUBLISHED_MEDIA_MISMATCH,
                                               stage=TransferStage.PUBLISH_VERIFY)
    assert [e.kind for e in outcome.effects] == [EffectKind.MEDIA_PUBLISHED]
    assert outcome.effects[0].identity == ts.source_identity and outcome.media_size == ts.size
    assert log.ops("unlink") == [] and fake.events == []  # no directory fsync / source unlink tail
    inject(monkeypatch, lstat=os.lstat)
    assert sha256_of_file(ts.source) == ts.sha256 and sha256_of_file(ts.final) == ts.sha256
    assert_planted_unchanged(ts)
    assert_source_not_lost(ts.source, ts.final, ts.sha256)


@pytest.mark.parametrize("strategy", STRATEGIES)
def test_really_changed_final_after_mismatch_fails_closed_on_resume(tmp_path, monkeypatch, strategy):
    # Mismatch resume safety: the recorded effect carries the trusted identity; the RESUME preflight
    # re-snapshots the final and blocks with COMPLETED_EFFECT_CHANGED.
    use_strategy(monkeypatch, strategy)
    ts = transfer_scene(tmp_path, content=CONTENT, plant=False)
    real = getattr(_fs._FS, strategy)

    def primitive(source, final):
        real(source, final)
        with open(final, "ab") as handle:
            handle.write(b"changed right after the publish")

    inject(monkeypatch, **{strategy: primitive})
    outcome = _run(ts)
    assert outcome.failure.kind is F.PUBLISHED_MEDIA_MISMATCH
    assert outcome.effects[0].identity == ts.source_identity
    blockers = mismatch_resume_blockers(ts, outcome, make_manifest(ts.plan), SAME)
    assert PreflightBlockReason.COMPLETED_EFFECT_CHANGED in blockers
    assert_source_not_lost(ts.source, ts.final, hashlib.sha256(CONTENT + b"changed right after the publish")
                           .hexdigest())


def _replace_source_after(monkeypatch, ts, op_name, replacement: bytes | None):
    real = getattr(_fs._FS, op_name)

    def op(*args):
        result = real(*args)
        if args[0] == ts.source and os.path.lexists(ts.source):
            os.unlink(ts.source)  # the original bytes live on under the final name (same inode)
            if replacement is not None:
                with open(ts.source, "wb") as handle:
                    handle.write(replacement)
        return result

    inject(monkeypatch, **{op_name: op})


def test_source_replaced_before_unlink_is_not_deleted(tmp_path, monkeypatch):
    use_strategy(monkeypatch, "link")
    ts = transfer_scene(tmp_path, content=CONTENT)
    _replace_source_after(monkeypatch, ts, "link", b"a different file now")
    outcome = _run(ts)
    assert [e.kind for e in outcome.effects] == [EffectKind.MEDIA_PUBLISHED]
    assert outcome.failure == ExecutionFailure(step=ExecutionStep.MOVE_MEDIA, kind=F.SOURCE_CHANGED,
                                               stage=TransferStage.SOURCE_PATH_REVALIDATE)
    assert _file_bytes(ts.source) == b"a different file now"  # the replacement is never deleted
    assert sha256_of_file(ts.final) == ts.sha256
    assert_source_not_lost(ts.source, ts.final, ts.sha256)


def test_source_missing_before_unlink(tmp_path, monkeypatch):
    use_strategy(monkeypatch, "link")
    ts = transfer_scene(tmp_path, content=CONTENT)
    _replace_source_after(monkeypatch, ts, "link", None)
    outcome = _run(ts)
    assert [e.kind for e in outcome.effects] == [EffectKind.MEDIA_PUBLISHED]
    assert outcome.failure.kind is F.SOURCE_MISSING and outcome.failure.stage is TransferStage.SOURCE_PATH_REVALIDATE
    assert_source_not_lost(ts.source, ts.final, ts.sha256)


def test_source_unlink_failure_keeps_both_names(tmp_path, monkeypatch):
    use_strategy(monkeypatch, "link")
    ts = transfer_scene(tmp_path, content=CONTENT)
    inject(monkeypatch, unlink=failing(PermissionError(errno.EACCES, "denied")))
    outcome = _run(ts)
    assert [e.kind for e in outcome.effects] == [EffectKind.MEDIA_PUBLISHED]
    assert outcome.failure == ExecutionFailure(step=ExecutionStep.MOVE_MEDIA, kind=F.SOURCE_UNLINK_FAILED,
                                               stage=TransferStage.SOURCE_UNLINK, errno=errno.EACCES)
    assert os.lstat(ts.source).st_ino == os.lstat(ts.final).st_ino  # two names of one inode: no data loss
    assert_source_not_lost(ts.source, ts.final, ts.sha256)
    # Resume only removes the source (contract section 14.4).
    inject(monkeypatch, unlink=os.unlink)
    resumed = _run(ts, phase=TAIL)
    assert resumed.failure is None and [e.kind for e in resumed.effects] == [EffectKind.SOURCE_REMOVED]
    assert resumed.media_sha256 is None and resumed.media_size is None
    assert not os.path.lexists(ts.source) and sha256_of_file(ts.final) == ts.sha256


@pytest.mark.skipif(os.name != "nt", reason="native Windows read-only source unlink failure")
def test_windows_native_read_only_source_unlink_fails_and_is_never_chmodded(tmp_path, monkeypatch):
    use_strategy(monkeypatch, "link")
    ts = transfer_scene(tmp_path, content=CONTENT)
    os.chmod(ts.source, stat.S_IREAD)
    ts.source_identity = _fs.snapshot(ts.source)
    try:
        outcome = _run(ts)
        assert outcome.failure.kind is F.SOURCE_UNLINK_FAILED and outcome.failure.errno == errno.EACCES
        assert os.stat(ts.source).st_mode & stat.S_IWRITE == 0  # P4-C7 never chmods
        assert_source_not_lost(ts.source, ts.final, ts.sha256)
    finally:
        os.chmod(ts.source, stat.S_IREAD | stat.S_IWRITE)


def test_directory_fsync_failure_keeps_final_and_source_then_resume_removes_source(tmp_path, monkeypatch):
    use_strategy(monkeypatch, "link")
    ts = transfer_scene(tmp_path, content=CONTENT)
    FakeDirectoryFsync(monkeypatch, ts.target_directory, fsync_error=OSError(errno.EIO, "io"))
    log = SeamLog(monkeypatch)
    outcome = _run(ts)
    assert [e.kind for e in outcome.effects] == [EffectKind.MEDIA_PUBLISHED]
    assert outcome.failure == ExecutionFailure(step=ExecutionStep.MOVE_MEDIA, kind=F.TARGET_DIRECTORY_FSYNC_FAILED,
                                               stage=TransferStage.DIRECTORY_FSYNC, errno=errno.EIO)
    assert log.ops("unlink") == [] and ("close", FakeDirectoryFsync.FD) in log.calls
    assert sha256_of_file(ts.source) == ts.sha256 and sha256_of_file(ts.final) == ts.sha256
    assert_source_not_lost(ts.source, ts.final, ts.sha256)
    fake = FakeDirectoryFsync(monkeypatch, ts.target_directory)
    resumed = _run(ts, phase=TAIL)
    assert resumed.failure is None and [e.kind for e in resumed.effects] == [EffectKind.SOURCE_REMOVED]
    assert fake.events == ["open", "fsync", "close"] and not os.path.lexists(ts.source)


# --------------------------------------------------------------------------- early exits


@pytest.mark.parametrize("strategy", STRATEGIES)
def test_changed_source_before_the_primitive(tmp_path, monkeypatch, strategy):
    use_strategy(monkeypatch, strategy)
    ts = transfer_scene(tmp_path, content=CONTENT)
    with open(ts.source, "ab") as handle:
        handle.write(b"appended after preflight")
    outcome = _run(ts)
    assert outcome.effects == () and outcome.failure.kind is F.SOURCE_CHANGED and outcome.failure.stage is None
    assert not os.path.lexists(ts.final) and _file_bytes(ts.source).startswith(CONTENT)


@pytest.mark.parametrize("strategy", STRATEGIES)
def test_missing_source_before_the_primitive(tmp_path, monkeypatch, strategy):
    use_strategy(monkeypatch, strategy)
    ts = transfer_scene(tmp_path, content=CONTENT)
    os.rename(ts.source, ts.source + ".moved-away")
    outcome = _run(ts)
    assert outcome.effects == () and outcome.failure.kind is F.SOURCE_MISSING
    assert not os.path.lexists(ts.final)
    assert_source_not_lost(ts.source + ".moved-away", ts.final, ts.sha256)


@pytest.mark.parametrize("strategy", STRATEGIES)
def test_replaced_target_directory_is_refused_before_any_mutation(tmp_path, monkeypatch, strategy):
    use_strategy(monkeypatch, strategy)
    ts = transfer_scene(tmp_path, content=CONTENT, plant=False)
    os.rmdir(ts.target_directory)
    os.mkdir(ts.target_directory)  # a different directory now
    log = SeamLog(monkeypatch)
    outcome = _run(ts)
    assert outcome.effects == () and outcome.failure.kind is F.TARGET_DIRECTORY_CHANGED
    assert log.ops("rename", "link", "unlink", "open") == []
    assert_source_not_lost(ts.source, ts.final, ts.sha256)


def test_inaccessible_target_probe_fails_closed(tmp_path, monkeypatch):
    ts = transfer_scene(tmp_path, content=CONTENT)
    real = _fs._FS.lstat

    def lstat(path):
        if path == ts.final:
            raise PermissionError(errno.EACCES, "denied")
        return real(path)

    inject(monkeypatch, lstat=lstat)
    outcome = _run(ts)
    assert outcome.effects == () and outcome.failure.kind is F.MEDIA_TRANSFER_FAILED
    assert outcome.failure.errno == errno.EACCES
    assert_source_not_lost(ts.source, ts.final, ts.sha256)


def test_source_removal_only_refuses_a_changed_source(tmp_path, monkeypatch):
    use_strategy(monkeypatch, "link")
    ts = transfer_scene(tmp_path, content=CONTENT)
    os.link(ts.source, ts.final)
    with open(ts.source, "ab") as handle:
        handle.write(b"changed")  # same inode for both names now differs from the snapshot
    log = SeamLog(monkeypatch)
    outcome = _run(ts, phase=TAIL)
    assert outcome.effects == () and outcome.failure.kind is F.SOURCE_CHANGED
    assert log.ops("unlink", "link", "rename") == []
    assert os.path.exists(ts.source) and os.path.exists(ts.final)


# --------------------------------------------------------------------------- inputs / model


def test_strict_inputs(tmp_path):
    ts = transfer_scene(tmp_path, content=CONTENT, plant=False)
    directory = ts.target_identity
    with pytest.raises(ExecutionInputError):
        transfer_media(ts.plan, directory, directory, SAME, resume_phase=FULL)
    with pytest.raises(ExecutionInputError):
        transfer_media(ts.plan, ts.source_identity, ts.source_identity, SAME, resume_phase=FULL)
    with pytest.raises(ExecutionInputError):
        transfer_media(ts.plan, ts.source_identity, directory, "same_volume", resume_phase=FULL)
    with pytest.raises(ExecutionInputError):
        transfer_media(ts.plan, ts.source_identity, directory, SAME, resume_phase=ResumePhase("FULL"))
    with pytest.raises(TypeError):
        transfer_media(ts.plan, ts.source_identity, directory, SAME)  # resume_phase is keyword-only, required
    assert os.path.exists(ts.source) and not os.path.lexists(ts.final)


def test_private_strategy_seam_rejects_unknown_values(tmp_path, monkeypatch):
    ts = transfer_scene(tmp_path, content=CONTENT, plant=False)
    use_strategy(monkeypatch, "replace")
    with pytest.raises(ExecutionInputError):
        _run(ts)
    assert os.path.exists(ts.source) and not os.path.lexists(ts.final)


def _media_effect(path="C:\\x" if os.name == "nt" else "/x"):
    identity = EntryIdentity(1, 2, EntryType.FILE, 3, 4)
    return CompletedEffect(EffectKind.MEDIA_PUBLISHED, PathRole.TARGET_MEDIA, path, identity, 3, None, None, None)


def _removed_effect(path="C:\\s" if os.name == "nt" else "/s"):
    return CompletedEffect(EffectKind.SOURCE_REMOVED, PathRole.SOURCE, path, None, None, None, None, None)


def test_transfer_outcome_is_immutable_and_strict():
    failure = ExecutionFailure(step=ExecutionStep.MOVE_MEDIA, kind=F.SOURCE_UNLINK_FAILED)
    ok = TransferOutcome((_media_effect(), _removed_effect()), None, SAME, None, 3, ())
    partial = TransferOutcome((_media_effect(),), failure, SAME, None, 3, ())
    assert ok == TransferOutcome((_media_effect(), _removed_effect()), None, SAME, None, 3, ()) and ok != partial
    assert hash(ok) == hash(TransferOutcome((_media_effect(), _removed_effect()), None, SAME, None, 3, ()))
    assert "TransferOutcome(" in repr(ok)
    with pytest.raises(ExecutionModelError):
        ok.failure = failure
    with pytest.raises(ExecutionModelError):
        del ok.effects
    with pytest.raises(ExecutionModelError):
        ResumePhase.FULL.name = "x"
    leftover = LeftoverTemporary(PathRole.TARGET_DIRECTORY, ".fc2tmp-" + "0" * 32 + ".part")
    TransferOutcome((_media_effect(),), ExecutionFailure(step=ExecutionStep.MOVE_MEDIA,
                                                         kind=F.MEDIA_TEMP_CLEANUP_FAILED, target_published=True),
                    CROSS, "a" * 64, 3, (leftover,))
    bad = [
        dict(effects=[_media_effect(), _removed_effect()]),                       # not a tuple
        dict(effects=(_removed_effect(), _media_effect())),                       # wrong order
        dict(effects=(_media_effect(),), failure=None),                           # success without removal
        dict(failure=failure),                                                    # failure after removal
        dict(failure=ExecutionFailure(step=ExecutionStep.CREATE_DIRECTORY, kind=F.TARGET_CONFLICT)),
        dict(transfer_mode="same_volume"),
        dict(media_sha256="a" * 64),                                              # sha256 only cross-volume
        dict(transfer_mode=CROSS, media_sha256="A" * 64),
        dict(media_size=True),
        dict(media_size=None),                                                    # published needs a size
        dict(leftover_temporaries=[leftover]),
    ]
    for override in bad:
        values = dict(effects=(_media_effect(), _removed_effect()), failure=None, transfer_mode=SAME,
                      media_sha256=None, media_size=3, leftover_temporaries=())
        values.update(override)
        with pytest.raises(ExecutionModelError):
            TransferOutcome(**values)
    with pytest.raises(ExecutionModelError):
        TransferOutcome((), failure, SAME, None, 3, ())                           # size without a publish


# --------------------------------------------------------------------------- R2: atomic-rename outcome invariant


def _mismatch(stage=TransferStage.PUBLISH_VERIFY, kind=F.PUBLISHED_MEDIA_MISMATCH):
    return ExecutionFailure(step=ExecutionStep.MOVE_MEDIA, kind=kind, stage=stage)


@pytest.mark.parametrize("case", [
    "A_cross_volume",
    "B_wrong_stage",
    "B_no_stage",
    "C_source_unlink_failed",
    "D_source_removed_only",
    "E_same_volume_link_semantics",
    "E_with_leftover",
])
def test_public_constructor_never_builds_failed_outcome_with_source_removed(case):
    both = (_media_effect(), _removed_effect())
    args = {
        "A_cross_volume": (both, _mismatch(), CROSS, None, 3, ()),
        "B_wrong_stage": (both, _mismatch(stage=TransferStage.SAME_VOLUME_PRIMITIVE), SAME, None, 3, ()),
        "B_no_stage": (both, _mismatch(stage=None), SAME, None, 3, ()),
        "C_source_unlink_failed": (both, _mismatch(stage=TransferStage.SOURCE_UNLINK,
                                                   kind=F.SOURCE_UNLINK_FAILED), SAME, None, 3, ()),
        "D_source_removed_only": ((_removed_effect(),), _mismatch(), SAME, None, None, ()),
        # Exactly the atomic-rename shape, but built by the public constructor (e.g. POSIX link semantics):
        # without the rename path's private witness it is refused.
        "E_same_volume_link_semantics": (both, _mismatch(), SAME, None, 3, ()),
        "E_with_leftover": (both, _mismatch(), SAME, None, 3,
                            (LeftoverTemporary(PathRole.TARGET_DIRECTORY, ".fc2tmp-" + "1" * 32 + ".part"),)),
    }[case]
    with pytest.raises(ExecutionModelError):
        TransferOutcome(*args)
    assert callable(assert_source_not_lost)


def _context(ts, strategy):
    return transfer._Context(ts.plan, ts.source_identity, ts.target_identity, strategy)


def test_atomic_rename_factory_checks_its_provenance(tmp_path):
    ts = transfer_scene(tmp_path, content=CONTENT, plant=False)
    media = CompletedEffect(EffectKind.MEDIA_PUBLISHED, PathRole.TARGET_MEDIA, ts.final, ts.source_identity,
                            ts.size, None, None, None)
    built = transfer._atomic_rename_mismatch_outcome(_context(ts, "rename"), media, _mismatch())
    assert [e.kind for e in built.effects] == [EffectKind.MEDIA_PUBLISHED, EffectKind.SOURCE_REMOVED]
    assert built.failure == _mismatch() and built.transfer_mode is SAME and built.media_sha256 is None
    assert built.media_size == ts.size and built.leftover_temporaries == ()
    other = EntryIdentity(ts.source_identity.device, ts.source_identity.inode + 1, EntryType.FILE,
                          ts.size, ts.source_identity.mtime_ns)
    refused = [
        (_context(ts, "link"), media, _mismatch()),                                  # POSIX link path
        (object(), media, _mismatch()),                                              # no real context
        (_context(ts, "rename"), media, _mismatch(stage=TransferStage.PUBLISH)),     # wrong stage
        (_context(ts, "rename"), media, _mismatch(kind=F.SOURCE_UNLINK_FAILED)),     # wrong kind
        (_context(ts, "rename"), CompletedEffect(EffectKind.MEDIA_PUBLISHED, PathRole.TARGET_MEDIA, ts.final,
                                                 other, ts.size, None, None, None), _mismatch()),
        (_context(ts, "rename"), CompletedEffect(EffectKind.MEDIA_PUBLISHED, PathRole.TARGET_MEDIA, ts.final,
                                                 ts.source_identity, ts.size, "a" * 64, None, None), _mismatch()),
    ]
    for args in refused:
        with pytest.raises(ExecutionModelError):
            transfer._atomic_rename_mismatch_outcome(*args)
    assert os.path.exists(ts.source) and not os.path.lexists(ts.final)
    assert_source_not_lost(ts.source, ts.final, ts.sha256)


def test_atomic_rename_witness_is_reachable_only_from_the_rename_mismatch_path():
    import ast

    tree = ast.parse(Path(transfer.__file__).read_text(encoding="utf-8"))
    witness_users, factory_callers = set(), []
    for fn in ast.walk(tree):
        if not isinstance(fn, ast.FunctionDef):
            continue
        for node in ast.walk(fn):
            if isinstance(node, ast.Name) and node.id == "_ATOMIC_RENAME_WITNESS":
                witness_users.add(fn.name)
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id == "_atomic_rename_mismatch_outcome"):
                factory_callers.append(fn.name)
    assert witness_users == {"_init_outcome", "_atomic_rename_mismatch_outcome"}
    assert factory_callers == ["_same_volume"]
    same_volume = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "_same_volume")
    guarded = [n for n in ast.walk(same_volume) if isinstance(n, ast.If)
               and ast.unparse(n.test) == "ctx.strategy == 'rename'"
               and any(isinstance(c, ast.Call) and getattr(c.func, "id", None) == "_atomic_rename_mismatch_outcome"
                       for c in ast.walk(n))]
    assert len(guarded) == 1
    assert "_ATOMIC_RENAME_WITNESS" not in transfer.__all__ and "_atomic_rename_mismatch_outcome" not in transfer.__all__
    assert callable(assert_source_not_lost)
