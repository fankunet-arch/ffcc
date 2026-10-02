"""P4-C8 S5: P4-C7 fault injection across the orchestration (contract sections 18.2, 21, 25.1, 28.2, 35 "fault
injection").

Faults are injected through the private seams ``execution._fs._FS`` / ``materialization.atomic._FS`` (tests only,
contract section 34.2), one per P4-C7 execution unit / transfer stage (P4-C7 contract section 9: U1 create
directory, U2 move media, U3-U6 NFO / poster / fanart / thumb, U7 extrafanart directory, U8.. extrafanart files;
``TransferStage`` for U2). Cross-volume transfer stages use P4-C7's ``device_of`` seam from the preview on, so the
preflight itself predicts ``CROSS_VOLUME`` (mocked devices -- never native cross-volume evidence).

S5-R1 (finding P4-C8-S5-R-02): every one of the frozen ``TransferStage`` members is the *primary* ``failure.stage``
of at least one U2 case -- checked against ``set(TransferStage)`` exactly, from each case's expected stage, which the
run then has to reproduce; every case also proves its seam was really hit. Stages reached only late in the transfer
(second source ``fstat``, post-publish verification, owned-temporary cleanup after publish, source path
revalidation) use test-local, call-counting seams; the shared ``FsFault`` helper is unchanged.

Each case runs three items: the target, an executed bystander and a not-selected bystander. The disposition,
``ExecutionStatus``, failure step / kind / stage, issue, ``RetryKind``, warnings and summary agree; the fault is then
cleared and the item retried (``preview_retry -> execute -> merge_retry``) to ``SUCCESS``. Every source is never lost
and the bystanders are unchanged.
"""

from __future__ import annotations

import dataclasses
import errno
import hashlib
import os
import stat
import threading

import pytest

from fc2_organizer.execution import EffectKind
from fc2_organizer.execution import ExecutionFailureKind as F, ExecutionStatus, ExecutionStep as U, TransferStage as T
from fc2_organizer.execution import _fs as execution_fs
from fc2_organizer.execution import transfer as execution_transfer
from fc2_organizer.orchestration import (
    BatchOutcome,
    ExecutionDisposition as D,
    IssueReason as R,
    ItemWarning,
    RetryKind as K,
    merge_retry,
)

from ._helpers import Corpus, Film, assert_source_not_lost, fs_fault, run

EIO = OSError(errno.EIO, "injected")
TMP = ".fc2tmp-"


def _cross_volume(m) -> None:
    real = execution_fs._FS.device_of

    def device_of(st):
        return real(st) + 7 if stat.S_ISREG(st.st_mode) else real(st)

    m.setattr(execution_fs, "_FS", dataclasses.replace(execution_fs._FS, device_of=device_of))


_FAKE_DIRECTORY_FD = 987654


class _Hits:
    """Thread-safe hit counter of a test-local seam (the evidence that the fault really fired)."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.count = 0

    def hit(self) -> None:
        with self.lock:
            self.count += 1

    def __call__(self) -> bool:
        return self.count > 0


def _directory_fsync_failure(m, directory: str) -> _Hits:
    """Enable P4-C7's POSIX directory-fsync step on any host (its private policy seam): the target's directory
    cannot be opened; every other directory gets a recorded fake descriptor (Windows cannot open directories)."""
    hits = _Hits()
    m.setattr(execution_transfer, "_DIRECTORY_FSYNC", True)
    real_open, real_fsync, real_close = execution_fs._FS.open, execution_fs._FS.fsync, execution_fs._FS.close

    def open_(path, flags, *rest):
        if path == directory:
            hits.hit()
            raise OSError(errno.EIO, "directory fsync")
        if os.path.isdir(path):
            return _FAKE_DIRECTORY_FD
        return real_open(path, flags, *rest)

    def fsync_(fd):
        return None if fd == _FAKE_DIRECTORY_FD else real_fsync(fd)

    def close_(fd):
        return None if fd == _FAKE_DIRECTORY_FD else real_close(fd)

    m.setattr(execution_fs, "_FS", dataclasses.replace(execution_fs._FS, open=open_, fsync=fsync_, close=close_))
    return hits


def _source_fstat_failure(m, source: str, nth: int) -> _Hits:
    """Fail only the ``nth`` ``fstat`` of the descriptor opened on ``source`` (1: the first validation after open,
    2: the revalidation after the copy, temporary fsync / fstat / close included)."""
    hits = _Hits()
    real_open, real_fstat = execution_fs._FS.open, execution_fs._FS.fstat
    source_fds: set[int] = set()
    seen = {"count": 0}

    def open_(path, flags, *rest):
        fd = real_open(path, flags, *rest)
        if path == source:
            source_fds.add(fd)
        return fd

    def fstat_(fd):
        if fd in source_fds:
            seen["count"] += 1
            if seen["count"] == nth:
                hits.hit()
                raise OSError(errno.EIO, "source fd fstat")
        return real_fstat(fd)

    m.setattr(execution_fs, "_FS", dataclasses.replace(execution_fs._FS, open=open_, fstat=fstat_))
    return hits


def _after_publish_lstat_failure(m, final: str, path: str) -> _Hits:
    """Once the media has been published to ``final`` (a ``rename`` / ``link`` onto it succeeded), fail the next
    ``lstat`` of ``path``: ``final`` -> post-publish verification, the source -> source path revalidation."""
    hits = _Hits()
    real_rename, real_link, real_lstat = execution_fs._FS.rename, execution_fs._FS.link, execution_fs._FS.lstat
    state = {"published": False, "fired": False}

    def rename_(src, dst):
        real_rename(src, dst)
        if dst == final:
            state["published"] = True

    def link_(src, dst):
        real_link(src, dst)
        if dst == final:
            state["published"] = True

    def lstat_(candidate):
        if state["published"] and not state["fired"] and candidate == path:
            state["fired"] = True
            hits.hit()
            raise OSError(errno.EIO, "late lstat")
        return real_lstat(candidate)

    m.setattr(execution_fs, "_FS", dataclasses.replace(execution_fs._FS, rename=rename_, link=link_, lstat=lstat_))
    return hits


def _temp_cleanup_after_publish(m, fault, item) -> _Hits:
    """P4-C7 unlinks its owned temporary after a ``link`` publish (the cross-volume strategy follows the same-volume
    strategy seam); that unlink fails while the published media is already in place."""
    m.setattr(execution_transfer, "_SAME_VOLUME_STRATEGY", "link")
    hits = _Hits()
    real_unlink = execution_fs._FS.unlink
    prefix = os.path.normcase(os.path.join(item.target_directory, TMP))

    def unlink_(path):
        if os.path.normcase(path).startswith(prefix):
            hits.hit()
            raise OSError(errno.EACCES, "temporary is locked")
        return real_unlink(path)

    m.setattr(execution_fs, "_FS", dataclasses.replace(execution_fs._FS, unlink=unlink_))
    return hits


def _src(item) -> str:
    return os.path.basename(item.source_path)


def _tmp(item) -> str:
    """Temporaries of this item only (its own target directory), never a bystander's."""
    return os.path.join(item.target_directory, TMP)


def _fs(*rules):
    """An ``FsFault``-based injector: ``rules`` are ``(seam, op, where(item), times)``; the hit evidence is the
    fault's own hit log."""
    def inject(m, fault, item):
        for seam, op, where, times in rules:
            fault.fail(seam, op, where(item), EIO, times=times)
        return lambda: bool(fault.hits)
    return inject


def _src_path(item) -> str:
    return item.source_path


# name -> (cross volume?, inject(m, fault, item) -> hit evidence, status, step, kind, stage, leftovers?)
CASES = {
    "before_u1_source_revalidation": (False, _fs(("execution", "lstat", _src, None)),
                                      ExecutionStatus.FAILED, U.CREATE_DIRECTORY, F.SOURCE_CHANGED, None, False),
    "u1_create_directory": (False, _fs(("execution", "mkdir", lambda i: i.target_directory, None)),
                            ExecutionStatus.FAILED, U.CREATE_DIRECTORY, F.DIRECTORY_CREATE_FAILED, None, False),
    "u2_same_volume_primitive": (False, _fs(("execution", "rename", _src, None)),
                                 ExecutionStatus.PARTIAL, U.MOVE_MEDIA, F.MEDIA_TRANSFER_FAILED,
                                 T.SAME_VOLUME_PRIMITIVE, False),
    "u2_source_open": (True, _fs(("execution", "open", _src, None)),
                       ExecutionStatus.PARTIAL, U.MOVE_MEDIA, F.MEDIA_SOURCE_OPEN_FAILED, T.SOURCE_OPEN, False),
    "u2_source_fd_validate": (True, lambda m, f, i: _source_fstat_failure(m, i.source_path, 1),
                              ExecutionStatus.PARTIAL, U.MOVE_MEDIA, F.MEDIA_SOURCE_OPEN_FAILED,
                              T.SOURCE_FD_VALIDATE, False),
    "u2_temp_create": (True, _fs(("execution", "open", _tmp, None)),
                       ExecutionStatus.PARTIAL, U.MOVE_MEDIA, F.MEDIA_TEMP_CREATE_FAILED, T.TEMP_CREATE, False),
    "u2_read": (True, _fs(("execution", "read", _src, None)),
                ExecutionStatus.PARTIAL, U.MOVE_MEDIA, F.MEDIA_READ_FAILED, T.READ, False),
    "u2_write": (True, _fs(("execution", "write", _tmp, None)),
                 ExecutionStatus.PARTIAL, U.MOVE_MEDIA, F.MEDIA_WRITE_FAILED, T.WRITE, False),
    "u2_write_with_failed_temp_removal": (True, _fs(("execution", "write", _tmp, None),
                                                    ("execution", "unlink", _tmp, None)),
                                          ExecutionStatus.PARTIAL, U.MOVE_MEDIA, F.MEDIA_WRITE_FAILED, T.WRITE, True),
    "u2_fsync": (True, _fs(("execution", "fsync", _tmp, None)),
                 ExecutionStatus.PARTIAL, U.MOVE_MEDIA, F.MEDIA_FSYNC_FAILED, T.FSYNC, False),
    "u2_close": (True, _fs(("execution", "close", _tmp, None)),
                 ExecutionStatus.PARTIAL, U.MOVE_MEDIA, F.MEDIA_CLOSE_FAILED, T.CLOSE, True),
    "u2_source_fd_revalidate": (True, lambda m, f, i: _source_fstat_failure(m, i.source_path, 2),
                                ExecutionStatus.PARTIAL, U.MOVE_MEDIA, F.MEDIA_READ_FAILED,
                                T.SOURCE_FD_REVALIDATE, False),
    "u2_publish": (True, _fs(("execution", "link", _tmp, None), ("execution", "rename", _tmp, None)),
                   ExecutionStatus.PARTIAL, U.MOVE_MEDIA, F.MEDIA_PUBLISH_FAILED, T.PUBLISH, False),
    "u2_publish_verify": (True, lambda m, f, i: _after_publish_lstat_failure(m, i.final_media_path,
                                                                              i.final_media_path),
                          ExecutionStatus.PARTIAL, U.MOVE_MEDIA, F.PUBLISHED_MEDIA_MISMATCH, T.PUBLISH_VERIFY,
                          False),
    "u2_temp_cleanup": (True, _temp_cleanup_after_publish,
                        ExecutionStatus.PARTIAL, U.MOVE_MEDIA, F.MEDIA_TEMP_CLEANUP_FAILED, T.TEMP_CLEANUP, True),
    "u2_directory_fsync": (True, lambda m, f, i: _directory_fsync_failure(m, i.target_directory),
                           ExecutionStatus.PARTIAL, U.MOVE_MEDIA, F.TARGET_DIRECTORY_FSYNC_FAILED, T.DIRECTORY_FSYNC,
                           False),
    "u2_source_path_revalidate": (True, lambda m, f, i: _after_publish_lstat_failure(m, i.final_media_path,
                                                                                      i.source_path),
                                  ExecutionStatus.PARTIAL, U.MOVE_MEDIA, F.SOURCE_CHANGED, T.SOURCE_PATH_REVALIDATE,
                                  False),
    "u2_source_unlink": (True, _fs(("execution", "unlink", _src, None)),
                         ExecutionStatus.PARTIAL, U.MOVE_MEDIA, F.SOURCE_UNLINK_FAILED, T.SOURCE_UNLINK, False),
    "u3_nfo": (False, _fs(("materialization", "publish", lambda i: os.path.basename(i.nfo_target), None)),
               ExecutionStatus.PARTIAL, U.MATERIALIZE_NFO, F.ARTIFACT_PUBLISH_FAILED, None, False),
    "u4_poster": (False, _fs(("materialization", "publish", lambda i: i.poster_target, None)),
                  ExecutionStatus.PARTIAL, U.MATERIALIZE_POSTER, F.ARTIFACT_PUBLISH_FAILED, None, False),
    "u5_fanart": (False, _fs(("materialization", "publish", lambda i: i.fanart_target, None)),
                  ExecutionStatus.PARTIAL, U.MATERIALIZE_FANART, F.ARTIFACT_PUBLISH_FAILED, None, False),
    "u6_thumb": (False, _fs(("materialization", "publish", lambda i: i.thumb_target, None)),
                 ExecutionStatus.PARTIAL, U.MATERIALIZE_THUMB, F.ARTIFACT_PUBLISH_FAILED, None, False),
    "u7_extrafanart_directory": (False, _fs(("execution", "mkdir", lambda i: i.extrafanart_directory, None)),
                                 ExecutionStatus.PARTIAL, U.ENSURE_EXTRAFANART_DIRECTORY, F.DIRECTORY_CREATE_FAILED,
                                 None, False),
    "u8_extrafanart_1": (False, _fs(("materialization", "publish", lambda i: "extrafanart-001.jpg", None)),
                         ExecutionStatus.PARTIAL, U.MATERIALIZE_EXTRAFANART, F.ARTIFACT_PUBLISH_FAILED, None, False),
    "u8_extrafanart_2": (False, _fs(("materialization", "publish", lambda i: "extrafanart-002.jpg", None)),
                         ExecutionStatus.PARTIAL, U.MATERIALIZE_EXTRAFANART, F.ARTIFACT_PUBLISH_FAILED, None, False),
    "artifact_cleanup": (False, _fs(("materialization", "write", lambda i: i.target_directory, 1),
                                    ("materialization", "unlink", _tmp, None)),
                         ExecutionStatus.PARTIAL, U.MATERIALIZE_NFO, F.ARTIFACT_CLEANUP_FAILED, None, True),
}
PUBLISHED_BEFORE_FAILURE = {T.PUBLISH_VERIFY, T.TEMP_CLEANUP, T.DIRECTORY_FSYNC, T.SOURCE_PATH_REVALIDATE,
                            T.SOURCE_UNLINK}


def _sha(path) -> str:
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def test_every_frozen_transfer_stage_is_the_primary_stage_of_a_u2_case():
    """The U2 cases' expected primary stages are exactly ``set(TransferStage)`` (no subset, nothing unknown);
    each case's run asserts that the real P4-C7 failure has that very stage."""
    stages = {case[5] for case in CASES.values() if case[3] is U.MOVE_MEDIA}
    assert stages == set(T) and len(set(T)) == 15
    assert all(case[5] is None for case in CASES.values() if case[3] is not U.MOVE_MEDIA)


@pytest.mark.parametrize("name", list(CASES))
def test_a_p4c7_fault_maps_consistently_and_retries_to_success(tmp_path, monkeypatch, name):
    cross, inject, status, step, kind, stage, leftovers = CASES[name]
    corpus = Corpus(tmp_path, [Film("FC2-PPV-1000001.mp4", extra=2), Film("FC2-PPV-1000002.mp4"),
                               Film("FC2-PPV-1000003.mp4")])
    hashes = {item.source_path: _sha(item.source_path) for item in corpus.items}
    if cross:
        _cross_volume(monkeypatch)  # from the preview on: the preflight predicts CROSS_VOLUME
    orchestrator = corpus.orchestrator()
    preview = run(orchestrator.preview(corpus.items))
    target, executed, untouched = preview.items
    with monkeypatch.context() as m:
        fault = fs_fault(m)
        hit = inject(m, fault, target)
        result = orchestrator.execute(preview, selection=(0, 1))
        assert hit(), "the injected fault never fired"
    item = result.items[0]
    failure = item.execution.failure
    assert item.disposition is D.EXECUTED and item.execution_status is status
    assert (failure.step, failure.kind, failure.stage) == (step, kind, stage)
    expected_reason = R.EXECUTION_FAILED if status is ExecutionStatus.FAILED else R.EXECUTION_PARTIAL
    assert item.issue.reason is expected_reason and item.issue.detail is kind
    assert item.retry_kind is (K.FRESH_REEXECUTE if status is ExecutionStatus.FAILED else K.RESUME)
    assert (ItemWarning.LEFTOVER_TEMPORARIES in item.warnings) is leftovers
    if status is ExecutionStatus.FAILED:
        assert item.execution.completed_effects == () and item.retry_material.checkpoint is None
    else:
        assert item.retry_material.checkpoint is item.execution.checkpoint
    published = stage in PUBLISHED_BEFORE_FAILURE
    if published:  # the media was already published: never rolled back, the source never removed
        kinds = [effect.kind for effect in item.execution.completed_effects]
        assert EffectKind.MEDIA_PUBLISHED in kinds and EffectKind.SOURCE_REMOVED not in kinds
        assert _sha(target.final_media_path) == hashes[target.source_path] and os.path.exists(target.source_path)
        final_identity = os.stat(target.final_media_path)
    summary = result.summary
    assert (summary.executed, summary.success, summary.not_selected, summary.retryable, summary.deferred) == (
        2, 1, 1, 1, 1)
    assert (summary.partial, summary.failed) == ((1, 0) if status is ExecutionStatus.PARTIAL else (0, 1))
    assert result.outcome is BatchOutcome.PARTIAL
    assert result.items[1].execution_status is ExecutionStatus.SUCCESS  # the executed bystander is unaffected
    assert _sha(executed.final_media_path) == hashes[executed.source_path]
    assert _sha(untouched.source_path) == hashes[untouched.source_path]
    assert not os.path.exists(untouched.target_directory)
    for each in preview.items:
        assert_source_not_lost(each.source_path, each.final_media_path, hashes[each.source_path])

    retry = run(orchestrator.preview_retry(result, scope=frozenset({item.retry_kind})))  # the fault is cleared
    assert [i.index for i in retry.items] == [0]
    merged = merge_retry(result, orchestrator.execute(retry))
    assert merged.items[0].execution_status is ExecutionStatus.SUCCESS
    assert merged.items[1] is result.items[1] and merged.items[2] is result.items[2]
    assert merged.summary.success == 2 and merged.summary.deferred == 1
    assert merged.retained_retry_payload_bytes <= merged.retention_budget_bytes
    assert _sha(target.final_media_path) == hashes[target.source_path] and not os.path.exists(target.source_path)
    if published:  # resumed without copying again: the published media is the very same file
        after = os.stat(target.final_media_path)
        assert (after.st_ino, after.st_mtime_ns) == (final_identity.st_ino, final_identity.st_mtime_ns)
    assert _sha(untouched.source_path) == hashes[untouched.source_path]
    for each in preview.items:
        assert_source_not_lost(each.source_path, each.final_media_path, hashes[each.source_path])
