"""P4-C8 S5: P4-C7 fault injection across the orchestration (contract sections 18.2, 21, 25.1, 28.2, 35 "fault
injection").

Faults are injected through the private seams ``execution._fs._FS`` / ``materialization.atomic._FS`` (tests only,
contract section 34.2), one per P4-C7 execution unit / transfer stage (P4-C7 contract section 9: U1 create
directory, U2 move media, U3-U6 NFO / poster / fanart / thumb, U7 extrafanart directory, U8.. extrafanart files;
``TransferStage`` for U2). Cross-volume transfer stages use P4-C7's ``device_of`` seam from the preview on, so the
preflight itself predicts ``CROSS_VOLUME`` (mocked devices -- never native cross-volume evidence).

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

import pytest

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


def _directory_fsync_failure(m, directory: str) -> None:
    """Enable P4-C7's POSIX directory-fsync step on any host (its private policy seam): the target's directory
    cannot be opened; every other directory gets a recorded fake descriptor (Windows cannot open directories)."""
    m.setattr(execution_transfer, "_DIRECTORY_FSYNC", True)
    real_open, real_fsync, real_close = execution_fs._FS.open, execution_fs._FS.fsync, execution_fs._FS.close

    def open_(path, flags, *rest):
        if path == directory:
            raise OSError(errno.EIO, "directory fsync")
        if os.path.isdir(path):
            return _FAKE_DIRECTORY_FD
        return real_open(path, flags, *rest)

    def fsync_(fd):
        return None if fd == _FAKE_DIRECTORY_FD else real_fsync(fd)

    def close_(fd):
        return None if fd == _FAKE_DIRECTORY_FD else real_close(fd)

    m.setattr(execution_fs, "_FS", dataclasses.replace(execution_fs._FS, open=open_, fsync=fsync_, close=close_))


def _src(item) -> str:
    return os.path.basename(item.source_path)


def _tmp(item) -> str:
    """Temporaries of this item only (its own target directory), never a bystander's."""
    return os.path.join(item.target_directory, TMP)


# name -> (cross volume?, inject(m, fault, item), status, step, kind, stage, leftovers?)
CASES = {
    "before_u1_source_revalidation": (False, lambda m, f, i: f.fail("execution", "lstat", _src(i), EIO),
                                      ExecutionStatus.FAILED, U.CREATE_DIRECTORY, F.SOURCE_CHANGED, None, False),
    "u1_create_directory": (False, lambda m, f, i: f.fail("execution", "mkdir", i.target_directory, EIO),
                            ExecutionStatus.FAILED, U.CREATE_DIRECTORY, F.DIRECTORY_CREATE_FAILED, None, False),
    "u2_same_volume_primitive": (False, lambda m, f, i: f.fail("execution", "rename", _src(i), EIO),
                                 ExecutionStatus.PARTIAL, U.MOVE_MEDIA, F.MEDIA_TRANSFER_FAILED,
                                 T.SAME_VOLUME_PRIMITIVE, False),
    "u2_source_open": (True, lambda m, f, i: f.fail("execution", "open", _src(i), EIO),
                       ExecutionStatus.PARTIAL, U.MOVE_MEDIA, F.MEDIA_SOURCE_OPEN_FAILED, T.SOURCE_OPEN, False),
    "u2_temp_create": (True, lambda m, f, i: f.fail("execution", "open", _tmp(i), EIO),
                       ExecutionStatus.PARTIAL, U.MOVE_MEDIA, F.MEDIA_TEMP_CREATE_FAILED, T.TEMP_CREATE, False),
    "u2_read": (True, lambda m, f, i: f.fail("execution", "read", _src(i), EIO),
                ExecutionStatus.PARTIAL, U.MOVE_MEDIA, F.MEDIA_READ_FAILED, T.READ, False),
    "u2_write": (True, lambda m, f, i: f.fail("execution", "write", _tmp(i), EIO),
                 ExecutionStatus.PARTIAL, U.MOVE_MEDIA, F.MEDIA_WRITE_FAILED, T.WRITE, False),
    "u2_fsync": (True, lambda m, f, i: f.fail("execution", "fsync", _tmp(i), EIO),
                 ExecutionStatus.PARTIAL, U.MOVE_MEDIA, F.MEDIA_FSYNC_FAILED, T.FSYNC, False),
    "u2_close": (True, lambda m, f, i: f.fail("execution", "close", _tmp(i), EIO),
                 ExecutionStatus.PARTIAL, U.MOVE_MEDIA, F.MEDIA_CLOSE_FAILED, T.CLOSE, True),
    "u2_publish": (True, lambda m, f, i: (f.fail("execution", "link", _tmp(i), EIO),
                                          f.fail("execution", "rename", _tmp(i), EIO)),
                   ExecutionStatus.PARTIAL, U.MOVE_MEDIA, F.MEDIA_PUBLISH_FAILED, T.PUBLISH, False),
    "u2_temp_cleanup": (True, lambda m, f, i: (f.fail("execution", "write", _tmp(i), EIO),
                                               f.fail("execution", "unlink", _tmp(i), EIO)),
                        ExecutionStatus.PARTIAL, U.MOVE_MEDIA, F.MEDIA_WRITE_FAILED, T.WRITE, True),
    "u2_directory_fsync": (True, lambda m, f, i: _directory_fsync_failure(m, i.target_directory),
                           ExecutionStatus.PARTIAL, U.MOVE_MEDIA, F.TARGET_DIRECTORY_FSYNC_FAILED, T.DIRECTORY_FSYNC,
                           False),
    "u2_source_unlink": (True, lambda m, f, i: f.fail("execution", "unlink", _src(i), EIO),
                         ExecutionStatus.PARTIAL, U.MOVE_MEDIA, F.SOURCE_UNLINK_FAILED, T.SOURCE_UNLINK, False),
    "u3_nfo": (False, lambda m, f, i: f.fail("materialization", "publish", os.path.basename(i.nfo_target), EIO),
               ExecutionStatus.PARTIAL, U.MATERIALIZE_NFO, F.ARTIFACT_PUBLISH_FAILED, None, False),
    "u4_poster": (False, lambda m, f, i: f.fail("materialization", "publish", i.poster_target, EIO),
                  ExecutionStatus.PARTIAL, U.MATERIALIZE_POSTER, F.ARTIFACT_PUBLISH_FAILED, None, False),
    "u5_fanart": (False, lambda m, f, i: f.fail("materialization", "publish", i.fanart_target, EIO),
                  ExecutionStatus.PARTIAL, U.MATERIALIZE_FANART, F.ARTIFACT_PUBLISH_FAILED, None, False),
    "u6_thumb": (False, lambda m, f, i: f.fail("materialization", "publish", i.thumb_target, EIO),
                 ExecutionStatus.PARTIAL, U.MATERIALIZE_THUMB, F.ARTIFACT_PUBLISH_FAILED, None, False),
    "u7_extrafanart_directory": (False, lambda m, f, i: f.fail("execution", "mkdir", i.extrafanart_directory, EIO),
                                 ExecutionStatus.PARTIAL, U.ENSURE_EXTRAFANART_DIRECTORY, F.DIRECTORY_CREATE_FAILED,
                                 None, False),
    "u8_extrafanart_1": (False, lambda m, f, i: f.fail("materialization", "publish", "extrafanart-001.jpg", EIO),
                         ExecutionStatus.PARTIAL, U.MATERIALIZE_EXTRAFANART, F.ARTIFACT_PUBLISH_FAILED, None, False),
    "u8_extrafanart_2": (False, lambda m, f, i: f.fail("materialization", "publish", "extrafanart-002.jpg", EIO),
                         ExecutionStatus.PARTIAL, U.MATERIALIZE_EXTRAFANART, F.ARTIFACT_PUBLISH_FAILED, None, False),
    "artifact_cleanup": (False, lambda m, f, i: (f.fail("materialization", "write", i.target_directory, EIO, times=1),
                                                 f.fail("materialization", "unlink", _tmp(i), EIO)),
                         ExecutionStatus.PARTIAL, U.MATERIALIZE_NFO, F.ARTIFACT_CLEANUP_FAILED, None, True),
}


def _sha(path) -> str:
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


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
        inject(m, fault, target)
        result = orchestrator.execute(preview, selection=(0, 1))
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
    assert _sha(untouched.source_path) == hashes[untouched.source_path]
    for each in preview.items:
        assert_source_not_lost(each.source_path, each.final_media_path, hashes[each.source_path])
