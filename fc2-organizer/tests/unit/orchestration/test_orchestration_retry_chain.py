"""P4-C8 S4: complete retry chains on the real filesystem (contract sections 24, 25.1 A-E, 25.3, 25.5, 26).

Every chain is ``preview -> execute -> preview_retry -> execute -> merge_retry`` against a ``tmp_path`` tree with
the real P4-C7 executor; faults are injected through the private ``_FS`` seams (tests only, contract section
34.2). After every execution the core invariant ``assert_source_not_lost`` holds for every item.
"""

from __future__ import annotations

import dataclasses
import errno
import hashlib
import os

import pytest

from fc2_organizer.execution import (
    CheckpointRejectionReason,
    EffectKind,
    ExecutionFailureKind as F,
    ExecutionStatus,
    PreflightBlockReason,
    PreflightMode,
    execute_filesystem,
    preflight_execution,
)
from fc2_organizer.execution import _fs as execution_fs
from fc2_organizer.execution import transfer as execution_transfer
from fc2_organizer.orchestration import (
    BatchOutcome,
    CancellationToken,
    ExecutionDisposition as D,
    IssueReason as R,
    OrchestrationConsumedError,
    PreviewState as S,
    RetryKind as K,
    merge_retry,
)

from ._helpers import Corpus, Film, assert_source_not_lost, fs_fault, run, tree_snapshot


def _sha(path) -> str:
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


class _Chain:
    """One corpus, one orchestrator, the source hashes and the main preview."""

    def __init__(self, tmp_path, films, **orchestrator_kwargs) -> None:
        self.corpus = Corpus(tmp_path, films)
        self.orchestrator = self.corpus.orchestrator(**orchestrator_kwargs)
        self.hashes = {os.path.basename(i.source_path): _sha(i.source_path) for i in self.corpus.items}
        self.preview = run(self.orchestrator.preview(self.corpus.items))

    def item(self, container, name):
        return next(i for i in container.items if os.path.basename(i.source_path) == name)

    def assert_sources(self, container) -> None:
        for item in container.items:
            original = self.hashes[os.path.basename(item.source_path)]
            assert_source_not_lost(item.source_path, item.final_media_path, original)

    def retry(self, previous, scope=None):
        return run(self.orchestrator.preview_retry(previous, scope=scope))


def _fsync_failure(monkeypatch, directory: str) -> None:
    """Enable the POSIX directory-fsync step on any host and make ``open`` of ``directory`` fail (a private
    policy seam of P4-C7, contract section 34.2)."""
    monkeypatch.setattr(execution_transfer, "_DIRECTORY_FSYNC", True)
    real_open = execution_fs._FS.open

    def failing_open(path, flags, *rest):
        if path == directory:
            raise OSError(errno.EIO, "directory fsync")
        return real_open(path, flags, *rest)

    monkeypatch.setattr(execution_fs, "_FS", dataclasses.replace(execution_fs._FS, open=failing_open))


# --------------------------------------------------------------------------- A / A'


def test_a_zero_effect_failed_fresh_reexecutes_to_success(tmp_path, monkeypatch):
    chain = _Chain(tmp_path, [Film("FC2-PPV-1000001.mp4"), Film("FC2-PPV-1000002.mp4")])
    first = chain.preview.items[0]
    with monkeypatch.context() as m:
        fault = fs_fault(m)
        fault.fail("execution", "mkdir", first.target_directory, OSError(errno.EACCES, "denied"))
        result = chain.orchestrator.execute(chain.preview)
    failed = result.items[0]
    assert failed.execution_status is ExecutionStatus.FAILED and failed.execution.completed_effects == ()
    assert failed.retry_kind is K.FRESH_REEXECUTE and failed.retry_material.checkpoint is None
    assert not os.path.exists(first.target_directory)
    chain.assert_sources(result)
    engine_calls, client_calls = len(chain.corpus.engine.calls), len(chain.corpus.client.calls)
    retry = chain.retry(result)
    assert [i.index for i in retry.items] == [0] and retry.items[0].retry_origin is K.FRESH_REEXECUTE
    assert retry.items[0].preflight_mode is PreflightMode.FRESH and retry.items[0].preflight.checkpoint is None
    assert retry.items[0].plan is failed.retry_material.plan  # the retained plan, not a rebuilt one
    assert retry.items[0].preflight.artifacts is failed.retry_material.artifacts
    assert (len(chain.corpus.engine.calls), len(chain.corpus.client.calls)) == (engine_calls, client_calls)
    round_result = chain.orchestrator.execute(retry)
    assert round_result.items[0].execution_status is ExecutionStatus.SUCCESS
    merged = merge_retry(result, round_result)
    assert [i.execution_status for i in merged.items] == [ExecutionStatus.SUCCESS] * 2
    assert merged.outcome is BatchOutcome.SUCCESS and merged.retained_retry_payload_bytes == 0
    chain.assert_sources(merged)


def test_a_prime_narrow_mkdir_case_is_reported_by_the_fresh_preflight_and_never_deleted(tmp_path, monkeypatch):
    """Stand-in for P4-C7's narrow exception: the directory is created, then the step fails (ownership
    unverifiable) and the directory stays. The fresh preflight reports it; nothing is removed."""
    chain = _Chain(tmp_path, [Film("FC2-PPV-1000001.mp4")])
    target = chain.preview.items[0].target_directory
    real_mkdir = execution_fs._FS.mkdir

    def mkdir_then_fail(path, *args):
        real_mkdir(path, *args)
        if path == target:
            raise OSError(errno.EIO, "ownership check failed")

    with monkeypatch.context() as m:
        m.setattr(execution_fs, "_FS", dataclasses.replace(execution_fs._FS, mkdir=mkdir_then_fail))
        result = chain.orchestrator.execute(chain.preview)
    assert result.items[0].execution_status is ExecutionStatus.FAILED
    assert result.items[0].retry_kind is K.FRESH_REEXECUTE and os.path.isdir(target)
    before = tree_snapshot(tmp_path)
    retry = chain.retry(result)
    item = retry.items[0]
    assert item.state is S.BLOCKED and item.issue.reason is R.PREFLIGHT_BLOCKED
    assert PreflightBlockReason.TARGET_DIRECTORY_EXISTS in {b.reason for b in item.blockers}
    round_result = chain.orchestrator.execute(retry)
    assert round_result.items[0].disposition is D.NOT_READY
    assert round_result.items[0].retry_kind is K.PREFLIGHT_RECHECK
    assert tree_snapshot(tmp_path) == before and os.path.isdir(target)  # reported, never removed
    chain.assert_sources(round_result)


# --------------------------------------------------------------------------- B: RESUME


def _artifact_stats(item) -> dict[str, tuple[int, int]]:
    stats = {}
    for effect in item.execution.completed_effects:
        if effect.kind is EffectKind.ARTIFACT_PUBLISHED:
            st = os.stat(effect.path)
            stats[effect.path] = (st.st_ino, st.st_mtime_ns)
    return stats


def _resume_to_success(chain, result, partial_index: int):
    partial = result.items[partial_index]
    checkpoint = partial.execution.checkpoint
    assert partial.retry_kind is K.RESUME and partial.retry_material.checkpoint is checkpoint
    artifacts_before = _artifact_stats(partial)
    media = partial.final_media_path
    media_before = os.stat(media) if os.path.exists(media) else None
    engine_calls, client_calls = len(chain.corpus.engine.calls), len(chain.corpus.client.calls)
    retry = chain.retry(result, frozenset({K.RESUME}))
    item = retry.items[0]
    assert item.retry_origin is K.RESUME and item.preflight_mode is PreflightMode.RESUME
    assert item.preflight.checkpoint is checkpoint  # the very object, handed back opaquely
    assert item.preflight.artifacts is partial.retry_material.artifacts and item.plan is partial.plan
    assert (len(chain.corpus.engine.calls), len(chain.corpus.client.calls)) == (engine_calls, client_calls)
    round_result = chain.orchestrator.execute(retry)
    resumed = round_result.items[0]
    assert resumed.execution_status is ExecutionStatus.SUCCESS
    old_effects = partial.execution.completed_effects
    assert resumed.execution.completed_effects[:len(old_effects)] == old_effects  # monotone prefix
    assert len(resumed.execution.completed_effects) > len(old_effects)
    for path, identity in artifacts_before.items():  # completed artifacts are never rewritten
        st = os.stat(path)
        assert (st.st_ino, st.st_mtime_ns) == identity
    if media_before is not None:  # the media is never moved again
        st = os.stat(media)
        assert (st.st_ino, st.st_mtime_ns) == (media_before.st_ino, media_before.st_mtime_ns)
    merged = merge_retry(result, round_result)
    chain.assert_sources(merged)
    return merged


def test_b_source_unlink_failed_resumes_without_moving_the_media_again(tmp_path, monkeypatch):
    chain = _Chain(tmp_path, [Film("FC2-PPV-1000001.mp4")])
    monkeypatch.setattr(execution_transfer, "_SAME_VOLUME_STRATEGY", "link")
    source = chain.preview.items[0].source_path
    with monkeypatch.context() as m:
        fault = fs_fault(m)
        fault.fail("execution", "unlink", os.path.basename(source), OSError(errno.EACCES, "locked"))
        result = chain.orchestrator.execute(chain.preview)
    item = result.items[0]
    assert item.execution_status is ExecutionStatus.PARTIAL and item.issue.detail is F.SOURCE_UNLINK_FAILED
    assert os.path.exists(source) and os.path.exists(item.final_media_path)
    chain.assert_sources(result)
    merged = _resume_to_success(chain, result, 0)
    assert not os.path.exists(source) and merged.outcome is BatchOutcome.SUCCESS


def test_b_artifact_write_failure_resumes_and_keeps_completed_artifacts(tmp_path, monkeypatch):
    chain = _Chain(tmp_path, [Film("FC2-PPV-1000001.mp4", extra=1)])
    thumb = chain.preview.items[0].thumb_target
    with monkeypatch.context() as m:
        fault = fs_fault(m)
        fault.fail("materialization", "publish", os.path.basename(thumb), OSError(errno.EIO, "io"))
        result = chain.orchestrator.execute(chain.preview)
    item = result.items[0]
    assert item.execution_status is ExecutionStatus.PARTIAL and item.issue.detail is F.ARTIFACT_PUBLISH_FAILED
    assert _artifact_stats(item)  # some artifacts were already published
    merged = _resume_to_success(chain, result, 0)
    assert os.path.isfile(thumb) and merged.outcome is BatchOutcome.SUCCESS


def test_b_target_directory_fsync_failure_seam_resumes(tmp_path, monkeypatch):
    chain = _Chain(tmp_path, [Film("FC2-PPV-1000001.mp4")])
    monkeypatch.setattr(execution_transfer, "_SAME_VOLUME_STRATEGY", "link")
    target = chain.preview.items[0].target_directory
    with monkeypatch.context() as m:
        _fsync_failure(m, target)
        result = chain.orchestrator.execute(chain.preview)
    item = result.items[0]
    assert item.execution_status is ExecutionStatus.PARTIAL
    assert item.issue.detail is F.TARGET_DIRECTORY_FSYNC_FAILED and os.path.exists(item.source_path)
    merged = _resume_to_success(chain, result, 0)
    assert not os.path.exists(item.source_path) and merged.outcome is BatchOutcome.SUCCESS


# --------------------------------------------------------------------------- C: PREFLIGHT_RECHECK


def test_c_blocked_item_stays_blocked_until_the_user_removes_the_blocker(tmp_path):
    films = [Film("FC2-PPV-1000001.mp4"), Film("FC2-PPV-1000002.mp4")]
    probe = _Chain(tmp_path / "probe", films)  # learn the target directory of the first film
    target = os.path.join(str(tmp_path / "c" / "lib"), os.path.basename(probe.preview.items[0].target_directory))
    os.makedirs(target)  # the user's own directory is already there
    blocker = os.path.join(target, "keep.txt")
    with open(blocker, "wb") as handle:
        handle.write(b"user bytes")
    chain = _Chain(tmp_path / "c", films)
    assert chain.preview.items[0].target_directory == target
    assert chain.preview.items[0].issue.reason is R.PREFLIGHT_BLOCKED
    result = chain.orchestrator.execute(chain.preview)
    assert result.items[0].retry_kind is K.PREFLIGHT_RECHECK
    assert result.items[1].execution_status is ExecutionStatus.SUCCESS
    snapshot = tree_snapshot(chain.corpus.root)
    still = chain.retry(result)  # blocker not removed: still PREFLIGHT_BLOCKED, bytes untouched
    assert still.items[0].retry_origin is K.PREFLIGHT_RECHECK and still.items[0].issue.reason is R.PREFLIGHT_BLOCKED
    assert still.items[0].preflight.artifacts is result.items[0].retry_material.artifacts
    still_result = chain.orchestrator.execute(still)
    assert tree_snapshot(chain.corpus.root) == snapshot
    merged = merge_retry(result, still_result)
    assert merged.items[0].retry_kind is K.PREFLIGHT_RECHECK
    with open(blocker, "rb") as handle:
        assert handle.read() == b"user bytes"
    os.remove(blocker)  # the test plays the user
    os.rmdir(target)
    retry = chain.retry(merged, frozenset({K.PREFLIGHT_RECHECK}))
    assert retry.items[0].state is S.READY and retry.generation == 2
    final = merge_retry(merged, chain.orchestrator.execute(retry))
    assert [i.execution_status for i in final.items] == [ExecutionStatus.SUCCESS] * 2
    chain.assert_sources(final)


# --------------------------------------------------------------------------- D: consumed checkpoint


def test_d_a_checkpoint_consumed_elsewhere_is_rejected_and_then_not_retryable(tmp_path, monkeypatch):
    chain = _Chain(tmp_path, [Film("FC2-PPV-1000001.mp4")])
    nfo = chain.preview.items[0].nfo_target
    with monkeypatch.context() as m:
        fault = fs_fault(m)
        fault.fail("materialization", "publish", os.path.basename(nfo), OSError(errno.EIO, "io"))
        result = chain.orchestrator.execute(chain.preview)
    material = result.items[0].retry_material
    elsewhere = execute_filesystem(preflight_execution(material.plan, material.artifacts, material.checkpoint))
    assert elsewhere.status is ExecutionStatus.SUCCESS  # the checkpoint was consumed outside P4-C8
    snapshot = tree_snapshot(chain.corpus.root)
    retry = chain.retry(result)
    item = retry.items[0]
    assert item.state is S.UNPREPARED and item.issue.reason is R.CHECKPOINT_REJECTED
    assert item.issue.detail is CheckpointRejectionReason.CONSUMED and item.preflight is None
    round_result = chain.orchestrator.execute(retry)
    assert round_result.items[0].disposition is D.NOT_READY and round_result.items[0].retry_kind is K.NONE
    merged = merge_retry(result, round_result)
    assert merged.items[0].retry_kind is K.NONE and merged.retained_retry_payload_bytes == 0
    assert tree_snapshot(chain.corpus.root) == snapshot


# --------------------------------------------------------------------------- E: process exit


def test_e_after_a_simulated_process_exit_a_new_preview_only_reports(tmp_path, monkeypatch):
    chain = _Chain(tmp_path, [Film("FC2-PPV-1000001.mp4"), Film("FC2-PPV-1000002.mp4")])
    monkeypatch.setattr(execution_transfer, "_SAME_VOLUME_STRATEGY", "link")
    first, second = chain.preview.items
    with monkeypatch.context() as m:
        fault = fs_fault(m)
        fault.fail("execution", "unlink", os.path.basename(first.source_path), OSError(errno.EACCES, "locked"))
        fault.fail("materialization", "publish", os.path.basename(second.nfo_target), OSError(errno.EIO, "io"))
        result = chain.orchestrator.execute(chain.preview)
    assert [i.execution_status for i in result.items] == [ExecutionStatus.PARTIAL] * 2
    del result  # "process exit": every result and checkpoint is gone
    orchestrator = chain.corpus.orchestrator()  # a new orchestrator, same scripted answers
    snapshot = tree_snapshot(chain.corpus.root)
    preview = run(orchestrator.preview(chain.corpus.items))
    for item in preview.items:
        assert (item.state, item.issue.reason) in {(S.BLOCKED, R.PREFLIGHT_BLOCKED),
                                                   (S.UNPREPARED, R.PREFLIGHT_REJECTED)}
    assert preview.items[0].issue.reason is R.PREFLIGHT_BLOCKED  # its target directory exists
    result = orchestrator.execute(preview)
    assert all(i.disposition is D.NOT_READY for i in result.items)
    assert tree_snapshot(chain.corpus.root) == snapshot  # no takeover, no deletion, no move
    chain.assert_sources(result)


# --------------------------------------------------------------------------- DEFERRED


def test_not_selected_and_cancelled_items_are_deferred_and_retry_to_success(tmp_path):
    chain = _Chain(tmp_path, [Film(f"FC2-PPV-{1000001 + i}.mp4") for i in range(3)])
    result = chain.orchestrator.execute(chain.preview, selection=(1,))
    assert [i.disposition for i in result.items] == [D.NOT_SELECTED, D.EXECUTED, D.NOT_SELECTED]
    token = CancellationToken()
    token.cancel()
    engine_calls, client_calls = len(chain.corpus.engine.calls), len(chain.corpus.client.calls)
    retry = chain.retry(result, frozenset({K.DEFERRED}))
    assert [i.index for i in retry.items] == [0, 2] and {i.retry_origin for i in retry.items} == {K.DEFERRED}
    for item in retry.items:
        assert item.preflight.artifacts is result.items[item.index].retry_material.artifacts
    cancelled = chain.orchestrator.execute(retry, cancel=token)
    assert [i.disposition for i in cancelled.items] == [D.CANCELLED, D.CANCELLED]
    merged = merge_retry(result, cancelled)
    assert [i.retry_kind for i in merged.items] == [K.DEFERRED, K.NONE, K.DEFERRED]
    again = chain.retry(merged, frozenset({K.DEFERRED}))
    final = merge_retry(merged, chain.orchestrator.execute(again))
    assert [i.execution_status for i in final.items] == [ExecutionStatus.SUCCESS] * 3
    assert final.generation == 2
    assert (len(chain.corpus.engine.calls), len(chain.corpus.client.calls)) == (engine_calls, client_calls)
    chain.assert_sources(final)


def test_a_deferred_resume_mode_preflight_keeps_its_original_checkpoint(tmp_path, monkeypatch):
    chain = _Chain(tmp_path, [Film("FC2-PPV-1000001.mp4")])
    nfo = chain.preview.items[0].nfo_target
    with monkeypatch.context() as m:
        fault = fs_fault(m)
        fault.fail("materialization", "publish", os.path.basename(nfo), OSError(errno.EIO, "io"))
        result = chain.orchestrator.execute(chain.preview)
    checkpoint = result.items[0].execution.checkpoint
    resume = chain.retry(result, frozenset({K.RESUME}))
    assert resume.items[0].preflight_mode is PreflightMode.RESUME
    unexecuted = chain.orchestrator.execute(resume, selection=())
    deferred = unexecuted.items[0]
    assert deferred.retry_kind is K.DEFERRED and deferred.retry_material.checkpoint is checkpoint
    merged = merge_retry(result, unexecuted)
    again = chain.retry(merged, frozenset({K.DEFERRED}))
    assert again.items[0].preflight_mode is PreflightMode.RESUME and again.items[0].preflight.checkpoint is checkpoint
    final = merge_retry(merged, chain.orchestrator.execute(again))
    assert final.items[0].execution_status is ExecutionStatus.SUCCESS and final.generation == 2
    chain.assert_sources(final)


# --------------------------------------------------------------------------- metadata


def test_metadata_failure_retries_until_success_consistently_with_phase_3(tmp_path):
    chain = _Chain(tmp_path, [Film("FC2-PPV-1000001.mp4"), Film("FC2-PPV-1000002.mp4", kind="failed")])
    result = chain.orchestrator.execute(chain.preview)
    assert result.items[1].retry_kind is K.METADATA_REFETCH
    failed_position = result.items[1].metadata_position
    assert result.metadata_batch.failed_indices == (failed_position,)
    still = chain.retry(result)  # the engine still fails
    assert still.metadata_batch.generation == 1 and still.metadata_batch.lineage == result.lineage
    assert still.metadata_batch.failed_indices == (failed_position,)
    assert still.items[0].state is S.UNPREPARED and still.items[0].issue.stage.name == "METADATA"
    merged = merge_retry(result, chain.orchestrator.execute(still))
    assert merged.items[1].retry_kind is K.METADATA_REFETCH  # retryable again
    chain.corpus.engine.script["FC2-1000002"] = "success"
    recovered = chain.retry(merged)
    assert recovered.metadata_batch.generation == 2 and recovered.metadata_batch.failed_indices == ()
    item = recovered.items[0]
    assert item.state is S.READY and item.metadata is recovered.metadata_batch.items[failed_position]
    final = merge_retry(merged, chain.orchestrator.execute(recovered))
    assert [i.execution_status for i in final.items] == [ExecutionStatus.SUCCESS] * 2
    assert final.metadata_batch is recovered.metadata_batch and final.generation == 2
    chain.assert_sources(final)


def test_retry_before_execution_is_a_composition_of_execute_selection_empty(tmp_path):
    """Contract section 25.5: execute(selection=()) -> METADATA_REFETCH -> DEFERRED."""
    chain = _Chain(tmp_path, [Film("FC2-PPV-1000001.mp4"), Film("FC2-PPV-1000002.mp4", kind="failed")])
    result = chain.orchestrator.execute(chain.preview, selection=())
    assert [i.retry_kind for i in result.items] == [K.DEFERRED, K.METADATA_REFETCH]
    chain.corpus.engine.script["FC2-1000002"] = "success"
    metadata = chain.retry(result, frozenset({K.METADATA_REFETCH}))
    merged = merge_retry(result, chain.orchestrator.execute(metadata, selection=()))
    assert [i.retry_kind for i in merged.items] == [K.DEFERRED, K.DEFERRED]
    deferred = chain.retry(merged, frozenset({K.DEFERRED}))
    final = merge_retry(merged, chain.orchestrator.execute(deferred))
    assert [i.execution_status for i in final.items] == [ExecutionStatus.SUCCESS] * 2
    chain.assert_sources(final)


# --------------------------------------------------------------------------- multi-generation chain


def test_a_chain_g0_to_g3_advances_one_generation_per_merge(tmp_path, monkeypatch):
    chain = _Chain(tmp_path, [Film("FC2-PPV-1000001.mp4"), Film("FC2-PPV-1000002.mp4", kind="failed"),
                              Film("FC2-PPV-1000003.mp4"), Film("FC2-PPV-1000004.mp4")])
    first = chain.preview.items[0]
    with monkeypatch.context() as m:
        fault = fs_fault(m)
        fault.fail("materialization", "publish", os.path.basename(first.nfo_target), OSError(errno.EIO, "io"))
        g0 = chain.orchestrator.execute(chain.preview, selection=(0, 2))
    assert [i.retry_kind for i in g0.items] == [K.RESUME, K.METADATA_REFETCH, K.NONE, K.DEFERRED]
    current = g0
    for generation, scope in enumerate((frozenset({K.RESUME}), frozenset({K.DEFERRED}),
                                        frozenset({K.METADATA_REFETCH})), start=1):
        if K.METADATA_REFETCH in scope:
            chain.corpus.engine.script["FC2-1000002"] = "success"
        retry = chain.retry(current, scope)
        assert retry.generation == generation and retry.base_result_id == current.result_id
        assert retry.lineage == g0.lineage
        round_result = chain.orchestrator.execute(retry)
        merged = merge_retry(current, round_result)
        assert merged.generation == generation and merged.lineage == g0.lineage
        assert merged.retained_retry_payload_bytes <= merged.retention_budget_bytes
        for item in merged.items:
            if item.index not in {i.index for i in retry.items}:
                assert item is current.items[item.index]
        current = merged
    assert [i.execution_status for i in current.items] == [ExecutionStatus.SUCCESS] * 4
    assert [i.generation for i in current.items] == [1, 3, 0, 2]
    chain.assert_sources(current)
    with pytest.raises(OrchestrationConsumedError):  # g0 was retried once; it cannot fork a second chain
        chain.retry(g0)
