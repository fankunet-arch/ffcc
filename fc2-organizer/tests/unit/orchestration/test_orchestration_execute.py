"""P4-C8 S3: ``BatchOrchestrator.execute`` (contract sections 17, 18, 23, 24, 25.1, 31).

Real ``discover_media`` corpora under ``tmp_path``, real preview, real P4-C7 ``execute_filesystem``. Failures
are injected through the P4-C7 / P4-C6 private seams (``fs_fault``) or, where noted, by replacing the single
name ``execute_filesystem`` inside ``fc2_organizer.orchestration.execute`` (contract section 34.2).
"""

from __future__ import annotations

import asyncio
import errno
import hashlib
import os
import threading

import pytest

from fc2_organizer.execution import (
    ArtifactManifestError,
    CheckpointError,
    CheckpointRejectionReason,
    ExecutionFailureKind,
    ExecutionInputError,
    ExecutionStatus,
    ManifestRejectionReason,
    PlanGraphError,
    PlanGraphRejectionReason,
    PreflightIntegrityError,
    PreflightIntegrityReason,
    PreflightNotReadyError,
    execute_filesystem,
)
from fc2_organizer.materialization import ArtifactKind
from fc2_organizer.orchestration import (
    BatchExecutionResult,
    BatchOutcome,
    CancellationToken,
    ExecutionDisposition as D,
    IssueReason as R,
    ItemWarning as W,
    OrchestrationBusyError,
    OrchestrationConfig,
    OrchestrationConsumedError,
    OrchestrationInputError,
    OrchestrationIntegrityError,
    PreviewState as S,
    RetryKind as K,
)
from fc2_organizer.orchestration import execute as execute_module
from fc2_organizer.images import ImageAcquisitionPolicy
from fc2_organizer.planning import OutputPolicy

from ._helpers import Corpus, Film, assert_source_not_lost, fake_execution, fs_fault, run, tampered, tree_snapshot


def _sha(path) -> str:
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


class _Spy:
    """Wraps the real ``execute_filesystem`` inside the execute module; records every preflight passed."""

    def __init__(self, monkeypatch, replacement=None) -> None:
        self.preflights: list[object] = []
        self._lock = threading.Lock()
        target = replacement or execute_filesystem

        def spy(preflight):
            with self._lock:
                self.preflights.append(preflight)
            return target(preflight)

        monkeypatch.setattr(execute_module, "execute_filesystem", spy)


def _prepared(tmp_path, films, **orchestrator_kwargs):
    corpus = Corpus(tmp_path, films)
    orchestrator = corpus.orchestrator(**orchestrator_kwargs)
    preview = run(orchestrator.preview(corpus.items))
    hashes = {item.index: _sha(item.source_path) for item in preview.items}
    return corpus, orchestrator, preview, hashes


def _expected_tree(item) -> dict[str, bytes]:
    """Every file the manifest and the media move must leave in the item's target directory."""
    files = {os.path.relpath(r.target_path, item.target_directory): r.content for r in item.preflight.artifacts}
    return files


def _actual_files(directory: str) -> dict[str, bytes]:
    found = {}
    for dirpath, _dirnames, filenames in os.walk(directory):
        for name in filenames:
            path = os.path.join(dirpath, name)
            with open(path, "rb") as handle:
                found[os.path.relpath(path, directory)] = handle.read()
    return found


# =========================================================================== real P4-C7 SUCCESS


_COMBOS = [(p, f, t) for p in (False, True) for f in (False, True) for t in (False, True)]


@pytest.mark.parametrize("extra", [0, 1, 13])
@pytest.mark.parametrize("poster, fanart, thumb", _COMBOS)
def test_real_execution_lays_out_exactly_the_previewed_manifest(tmp_path, poster, fanart, thumb, extra):
    film = Film("FC2-PPV-1000001.mp4", poster=poster, fanart=fanart, thumb=thumb, extra=extra, content=b"M" * 777)
    corpus, orchestrator, preview, hashes = _prepared(tmp_path, [film],  # P4-C5 default caps extrafanart at 12
                                                      image_policy=ImageAcquisitionPolicy(max_extrafanart=13))
    (item,) = preview.items
    source_bytes = b"M" * 777
    expected = _expected_tree(item)
    expected[os.path.relpath(item.final_media_path, item.target_directory)] = source_bytes
    result = orchestrator.execute(preview)
    (executed,) = result.items
    assert executed.disposition is D.EXECUTED and executed.execution_status is ExecutionStatus.SUCCESS
    assert executed.issue is None and executed.retry_kind is K.NONE and executed.retry_material is None
    assert not os.path.exists(item.source_path)
    assert _actual_files(item.target_directory) == expected
    assert os.path.isdir(item.extrafanart_directory)
    kinds = [r.kind for r in item.preflight.artifacts]
    assert (ArtifactKind.POSTER in kinds, ArtifactKind.FANART in kinds, ArtifactKind.THUMB in kinds) == (
        poster, fanart, thumb)
    assert kinds.count(ArtifactKind.EXTRAFANART) == extra
    assert result.outcome is BatchOutcome.SUCCESS


def test_every_ready_item_is_executed_once_with_the_previews_own_preflight(tmp_path, monkeypatch):
    films = [Film(f"FC2-PPV-{1000001 + i}.mp4") for i in range(3)] + [Film("junk.mp4")]
    corpus, orchestrator, preview, hashes = _prepared(tmp_path, films)
    (corpus.library / "FC2-1000003").mkdir()  # not in the preview: the preflight still says ready
    spy = _Spy(monkeypatch)
    result = orchestrator.execute(preview)
    ready = [i for i in preview.items if i.state is S.READY]
    assert len(spy.preflights) == len(ready) == 3
    assert all(a is b.preflight for a, b in zip(spy.preflights, ready))  # identity: no re-preflight
    by_index = {i.index: i for i in result.items}
    junk = next(i for i in preview.items if i.state is not S.READY)
    assert by_index[junk.index].disposition is D.NOT_READY and by_index[junk.index].issue is junk.issue
    drifted = next(i for i in preview.items if i.canonical_number == "FC2-1000003")
    assert by_index[drifted.index].execution_status is ExecutionStatus.FAILED  # drift -> typed failure (17.2)
    assert by_index[drifted.index].issue.detail is ExecutionFailureKind.TARGET_CONFLICT
    assert_source_not_lost(drifted.source_path, drifted.final_media_path, hashes[drifted.index])


def test_blocked_and_unprepared_items_are_never_dispatched(tmp_path, monkeypatch):
    films = [Film("FC2-PPV-1000001.mp4"), Film("FC2PPV1000001.mkv", directory="dup"), Film("FC2-PPV-1000002.mp4"),
             Film("FC2-PPV-1000003.mp4", kind="failed"), Film("junk.mp4")]
    corpus = Corpus(tmp_path, films)
    (corpus.library / "FC2-1000002").mkdir()
    orchestrator = corpus.orchestrator()
    preview = run(orchestrator.preview(corpus.items))
    assert all(i.state is not S.READY for i in preview.items)
    spy = _Spy(monkeypatch)
    result = orchestrator.execute(preview)
    assert spy.preflights == []
    assert all(i.disposition is D.NOT_READY for i in result.items)
    kinds = {i.issue.reason: i.retry_kind for i in result.items}
    assert kinds[R.PREFLIGHT_BLOCKED] is K.PREFLIGHT_RECHECK
    assert kinds[R.DUPLICATE_TARGET_IN_BATCH] is K.NONE and kinds[R.METADATA_UNAVAILABLE] is K.METADATA_REFETCH
    blocked = next(i for i in result.items if i.issue.reason is R.PREFLIGHT_BLOCKED)
    source = next(i for i in preview.items if i.index == blocked.index)
    assert blocked.retry_material.artifacts is source.preflight.artifacts
    assert blocked.retry_material.checkpoint is source.preflight.checkpoint
    assert result.outcome is BatchOutcome.FAILED


# =========================================================================== selection (18.1 step 6)


def _three_ready(tmp_path):
    films = [Film(f"FC2-PPV-{1000001 + i}.mp4") for i in range(3)] + [Film("junk.mp4")]
    return _prepared(tmp_path, films)


def test_selection_subset_executes_only_the_selected_items(tmp_path, monkeypatch):
    corpus, orchestrator, preview, _ = _three_ready(tmp_path)
    ready = [i.index for i in preview.items if i.state is S.READY]
    spy = _Spy(monkeypatch)
    result = orchestrator.execute(preview, selection=(ready[0], ready[2]))
    assert [p.preflight_id for p in spy.preflights] == [
        i.preflight.preflight_id for i in preview.items if i.index in (ready[0], ready[2])]
    by_index = {i.index: i for i in result.items}
    assert by_index[ready[1]].disposition is D.NOT_SELECTED and by_index[ready[1]].retry_kind is K.DEFERRED
    source = next(i for i in preview.items if i.index == ready[1])
    assert by_index[ready[1]].retry_material.artifacts is source.preflight.artifacts
    assert by_index[ready[1]].retry_material.plan is source.plan
    assert result.outcome is BatchOutcome.PARTIAL


def test_empty_selection_executes_nothing_but_consumes_the_preview(tmp_path, monkeypatch):
    corpus, orchestrator, preview, _ = _three_ready(tmp_path)
    spy = _Spy(monkeypatch)
    result = orchestrator.execute(preview, selection=())
    assert spy.preflights == []
    assert all(i.disposition in (D.NOT_SELECTED, D.NOT_READY) for i in result.items)
    assert sum(i.disposition is D.NOT_SELECTED for i in result.items) == 3
    with pytest.raises(OrchestrationConsumedError):
        orchestrator.execute(preview)
    assert spy.preflights == []


class _TupleSub(tuple):
    pass


def test_invalid_selections_are_rejected_before_consumption(tmp_path, monkeypatch):
    corpus, orchestrator, preview, _ = _three_ready(tmp_path)
    ready = [i.index for i in preview.items if i.state is S.READY]
    not_ready = next(i.index for i in preview.items if i.state is not S.READY)
    spy = _Spy(monkeypatch)
    bad = [list(ready), set(ready), (ready[1], ready[0]), (ready[0], ready[0]), (not_ready,), (99,), (-1,),
           (True,), (float(ready[0]),), _TupleSub(ready), iter(ready), "0", ready[0]]
    for selection in bad:
        with pytest.raises(OrchestrationInputError) as info:
            orchestrator.execute(preview, selection=selection)
        assert info.value.__context__ is None
    assert spy.preflights == []
    result = orchestrator.execute(preview, selection=(ready[0],))  # not consumed by the rejected calls
    assert len(spy.preflights) == 1 and type(result) is BatchExecutionResult


# =========================================================================== consumption / type / config / integrity


def test_a_preview_is_executed_at_most_once(tmp_path, monkeypatch):
    corpus, orchestrator, preview, _ = _three_ready(tmp_path)
    orchestrator.execute(preview)
    spy = _Spy(monkeypatch)
    with pytest.raises(OrchestrationConsumedError) as info:
        orchestrator.execute(preview)
    assert spy.preflights == [] and info.value.__context__ is None
    other = corpus.orchestrator()
    with pytest.raises(OrchestrationConsumedError):  # the registry is process-wide, not per orchestrator
        other.execute(preview)


@pytest.mark.parametrize("bad", [None, "preview", object()])
def test_non_preview_arguments_are_input_errors(tmp_path, bad):
    corpus = Corpus(tmp_path, [])
    with pytest.raises(OrchestrationInputError):
        corpus.orchestrator().execute(bad)


def test_cancel_must_be_an_exact_token(tmp_path, monkeypatch):
    corpus, orchestrator, preview, _ = _three_ready(tmp_path)

    class SubToken(CancellationToken):
        __slots__ = ()

    spy = _Spy(monkeypatch)
    for cancel in (True, object(), SubToken(), threading.Event()):
        with pytest.raises(OrchestrationInputError):
            orchestrator.execute(preview, cancel=cancel)
    assert spy.preflights == []
    orchestrator.execute(preview, cancel=CancellationToken())  # still unconsumed


@pytest.mark.parametrize("mismatch", ["library_root", "output_policy", "image_policy", "budget"])
def test_configuration_mismatch_is_an_input_error(tmp_path, monkeypatch, mismatch):
    corpus, orchestrator, preview, _ = _three_ready(tmp_path)

    kwargs = {"library_root": dict(library_root=str(corpus.root / "elsewhere")),
              "output_policy": dict(output_policy=OutputPolicy(poster_filename="cover.jpg")),
              "image_policy": dict(image_policy=ImageAcquisitionPolicy(max_redirects=1)),
              "budget": dict(config=OrchestrationConfig(max_retained_artifact_bytes=10 ** 9))}[mismatch]
    spy = _Spy(monkeypatch)
    with pytest.raises(OrchestrationInputError):
        corpus.orchestrator(**kwargs).execute(preview)
    assert spy.preflights == []
    orchestrator.execute(preview)  # still unconsumed


def test_tampered_preview_graphs_are_integrity_errors_with_zero_dispatch(tmp_path, monkeypatch):
    corpus, orchestrator, preview, _ = _three_ready(tmp_path)
    ready = [i for i in preview.items if i.state is S.READY]
    spy = _Spy(monkeypatch)
    object.__setattr__(ready[0], "preflight", ready[1].preflight)  # another item's preflight
    with pytest.raises(OrchestrationIntegrityError):
        orchestrator.execute(preview)
    object.__setattr__(ready[0], "preflight", ready[2].preflight)
    object.__setattr__(ready[0], "plan", ready[2].plan)  # a consistent pair from another item
    with pytest.raises(OrchestrationIntegrityError):
        orchestrator.execute(preview)
    fresh_corpus, fresh_orchestrator, fresh, _ = _three_ready(tmp_path / "fresh")
    object.__setattr__(fresh, "generation", 3)  # breaks the preview-shape invariant
    with pytest.raises(OrchestrationIntegrityError):
        fresh_orchestrator.execute(fresh)
    assert spy.preflights == []


# =========================================================================== P4-C7 FAILED / PARTIAL via the private seams


def test_failure_before_the_first_effect_is_failed_and_fresh_reexecutable(tmp_path, monkeypatch):
    corpus, orchestrator, preview, hashes = _prepared(tmp_path, [Film("FC2-PPV-1000001.mp4")])
    (item,) = preview.items
    fault = fs_fault(monkeypatch)
    fault.fail("execution", "mkdir", item.target_directory, OSError(errno.EACCES, "denied"))
    (executed,) = orchestrator.execute(preview).items
    assert executed.disposition is D.EXECUTED and executed.execution_status is ExecutionStatus.FAILED
    assert executed.issue.reason is R.EXECUTION_FAILED and executed.issue.detail is executed.execution.failure.kind
    assert executed.retry_kind is K.FRESH_REEXECUTE and executed.retry_material.checkpoint is None
    assert executed.retry_material.artifacts is item.preflight.artifacts and executed.retry_material.plan is item.plan
    assert_source_not_lost(item.source_path, item.final_media_path, hashes[item.index])


def test_failure_after_the_first_effect_is_partial_with_the_checkpoint_itself(tmp_path, monkeypatch):
    corpus, orchestrator, preview, hashes = _prepared(tmp_path, [Film("FC2-PPV-1000001.mp4")])
    (item,) = preview.items
    fault = fs_fault(monkeypatch)
    fault.fail("materialization", "publish", os.path.basename(item.nfo_target), OSError(errno.EIO, "io"))
    (executed,) = orchestrator.execute(preview).items
    assert executed.execution_status is ExecutionStatus.PARTIAL and executed.issue.reason is R.EXECUTION_PARTIAL
    assert executed.issue.detail is executed.execution.failure.kind
    assert executed.retry_kind is K.RESUME
    assert executed.retry_material.checkpoint is executed.execution.checkpoint  # carried, never copied (24.1)
    assert executed.retry_material.artifacts is item.preflight.artifacts
    assert_source_not_lost(item.source_path, item.final_media_path, hashes[item.index])


def test_leftover_temporaries_become_a_warning_and_are_not_deleted(tmp_path, monkeypatch):
    corpus, orchestrator, preview, hashes = _prepared(tmp_path, [Film("FC2-PPV-1000001.mp4")])
    (item,) = preview.items
    fault = fs_fault(monkeypatch)
    fault.fail("materialization", "write", item.target_directory, OSError(errno.ENOSPC, "full"), times=1)
    fault.fail("materialization", "unlink", ".fc2tmp-", OSError(errno.EACCES, "locked"))
    (executed,) = orchestrator.execute(preview).items
    assert executed.execution.leftover_temporaries
    assert W.LEFTOVER_TEMPORARIES in executed.warnings and executed.warnings[-1] is W.LEFTOVER_TEMPORARIES
    monkeypatch.undo()
    names = [t.name for t in executed.execution.leftover_temporaries]
    remaining = os.listdir(item.target_directory)
    assert all(name in remaining for name in names)  # P4-C8 never cleans up
    assert_source_not_lost(item.source_path, item.final_media_path, hashes[item.index])


# =========================================================================== REJECTED (six exact types) / ABORTED


def test_tampered_seal_is_rejected_by_p4c7_with_zero_effect(tmp_path, monkeypatch):
    corpus, orchestrator, preview, hashes = _prepared(tmp_path, [Film("FC2-PPV-1000001.mp4")])
    (item,) = preview.items
    object.__setattr__(item.preflight, "seal", "0" * 64)  # still model-valid: only P4-C7 can tell
    before = tree_snapshot(corpus.root)
    (executed,) = orchestrator.execute(preview).items
    assert executed.disposition is D.REJECTED and executed.issue.reason is R.EXECUTION_REJECTED
    assert executed.issue.error_type == "PreflightIntegrityError"
    assert executed.issue.detail is PreflightIntegrityReason.SEAL_INVALID
    assert executed.retry_kind is K.NONE and executed.retry_material is None
    assert tree_snapshot(corpus.root) == before  # zero filesystem effect


def test_a_preflight_consumed_elsewhere_is_rejected_with_zero_effect(tmp_path):
    corpus, orchestrator, preview, hashes = _prepared(tmp_path, [Film("FC2-PPV-1000001.mp4"),
                                                                 Film("FC2-PPV-1000002.mp4")])
    first, second = preview.items
    execute_filesystem(first.preflight)  # consumed by someone else first (real P4-C7 registry)
    before = tree_snapshot(corpus.root)
    result = orchestrator.execute(preview)
    by_index = {i.index: i for i in result.items}
    assert by_index[first.index].disposition is D.REJECTED
    assert by_index[first.index].issue.detail is PreflightIntegrityReason.CONSUMED
    assert by_index[second.index].execution_status is ExecutionStatus.SUCCESS
    after = tree_snapshot(corpus.root)
    untouched = {k: v for k, v in before.items() if "FC2-1000001" in k or "FC2-PPV-1000001" in k}
    assert all(after.get(k) == v for k, v in untouched.items())


@pytest.mark.parametrize("error, detail", [
    (ExecutionInputError("preflight must be an exact ExecutionPreflight"), None),
    (PreflightNotReadyError(), None),
    (CheckpointError(CheckpointRejectionReason.PLAN_MISMATCH), CheckpointRejectionReason.PLAN_MISMATCH),
    (PlanGraphError(PlanGraphRejectionReason.FIELD_TYPE), PlanGraphRejectionReason.FIELD_TYPE),
    (ArtifactManifestError(ManifestRejectionReason.ORDER), ManifestRejectionReason.ORDER),
    (PreflightIntegrityError(PreflightIntegrityReason.FINGERPRINT_MISMATCH),
     PreflightIntegrityReason.FINGERPRINT_MISMATCH),
])
def test_each_exact_pre_filesystem_type_is_rejected(tmp_path, monkeypatch, error, detail):
    """Exact seam for the four types the preview integrity check already makes unreachable through
    orchestration (not-ready / wrong-type preflights, checkpoints, plan / manifest structure)."""
    corpus, orchestrator, preview, hashes = _prepared(tmp_path, [Film("FC2-PPV-1000001.mp4")])

    def raising(preflight):
        raise error

    _Spy(monkeypatch, raising)
    (executed,) = orchestrator.execute(preview).items
    assert executed.disposition is D.REJECTED and executed.issue.error_type == type(error).__name__
    assert executed.issue.detail is detail and executed.retry_material is None
    assert executed.issue.__class__.__name__ == "ItemIssue" and executed.issue.stage.value == "execution"


def test_a_subclass_of_a_rejected_type_is_aborted(tmp_path, monkeypatch):
    corpus, orchestrator, preview, hashes = _prepared(tmp_path, [Film("FC2-PPV-1000001.mp4")])

    class SubIntegrity(PreflightIntegrityError):
        pass

    def raising(preflight):
        raise SubIntegrity(PreflightIntegrityReason.SEAL_INVALID)

    _Spy(monkeypatch, raising)
    (executed,) = orchestrator.execute(preview).items
    assert executed.disposition is D.ABORTED and executed.issue.error_type == "SubIntegrity"


def test_foreign_exception_inside_p4c7_is_aborted_and_the_source_survives(tmp_path, monkeypatch):
    corpus, orchestrator, preview, hashes = _prepared(tmp_path, [Film("FC2-PPV-1000001.mp4")])
    (item,) = preview.items
    fault = fs_fault(monkeypatch)
    for op in ("rename", "link", "open"):
        fault.fail("execution", op, os.path.basename(item.source_path), RuntimeError("injected"))
    (executed,) = orchestrator.execute(preview).items
    assert executed.disposition is D.ABORTED and executed.issue.reason is R.EXECUTION_ABORTED
    assert executed.issue.error_type == "RuntimeError" and executed.retry_kind is K.NONE
    assert executed.retry_material is None and fault.hits
    monkeypatch.undo()
    assert_source_not_lost(item.source_path, item.final_media_path, hashes[item.index])


@pytest.mark.parametrize("shape", ["none", "string", "foreign preflight id"])
def test_contract_violating_returns_are_aborted(tmp_path, monkeypatch, shape):
    corpus, orchestrator, preview, hashes = _prepared(tmp_path, [Film("FC2-PPV-1000001.mp4")])
    (item,) = preview.items

    def returning(preflight):
        if shape == "none":
            return None
        if shape == "string":
            return "done"
        return fake_execution(item.plan, ExecutionStatus.SUCCESS)  # another preflight's result

    _Spy(monkeypatch, returning)
    (executed,) = orchestrator.execute(preview).items
    assert executed.disposition is D.ABORTED
    assert executed.issue.error_type == {"none": "NoneType", "string": "str",
                                         "foreign preflight id": "ExecutionResult"}[shape]


# =========================================================================== result shape / retention / busy


def test_result_copies_the_preview_shape_and_lineage_budget(tmp_path):
    corpus, orchestrator, preview, _ = _three_ready(tmp_path)
    result = orchestrator.execute(preview, selection=())
    assert result.preview_id == preview.preview_id and result.lineage == preview.lineage
    assert result.generation == 0 and result.base_result_id is None and result.retry_scope is None
    assert result.retention_budget_bytes == preview.retention_budget_bytes and result.retry_budget_bytes is None
    assert result.metadata_batch is preview.metadata_batch and result.batch_size == preview.batch_size
    assert result.is_complete and result.result_id != preview.preview_id
    assert 0 < result.retained_retry_payload_bytes <= preview.retained_artifact_bytes
    for executed, source in zip(result.items, preview.items):
        assert executed.media_item is source.media_item and executed.plan is source.plan
        assert executed.metadata is source.metadata and executed.image_failures is source.image_failures
        if executed.retry_material is not None:
            assert executed.retry_material.artifacts is source.preflight.artifacts  # no payload copy


def test_successful_items_release_their_payload(tmp_path):
    corpus, orchestrator, preview, _ = _three_ready(tmp_path)
    result = orchestrator.execute(preview)
    assert all(i.retry_material is None for i in result.items if i.execution_status is ExecutionStatus.SUCCESS)
    assert result.retained_retry_payload_bytes == 0


def test_execute_is_busy_first_and_releases_on_every_exit(tmp_path, monkeypatch):
    corpus, orchestrator, preview, _ = _three_ready(tmp_path)
    entered, release = threading.Event(), threading.Event()

    def blocking(preflight):
        entered.set()
        assert release.wait(30)
        return execute_filesystem(preflight)

    _Spy(monkeypatch, blocking)
    outcome: list[object] = []
    worker = threading.Thread(target=lambda: outcome.append(orchestrator.execute(preview)))
    worker.start()
    assert entered.wait(30)
    for argument in (preview, None, "junk"):
        with pytest.raises(OrchestrationBusyError):
            orchestrator.execute(argument)
    with pytest.raises(OrchestrationBusyError):
        run(orchestrator.preview(()))
    with pytest.raises(OrchestrationBusyError):  # the rejected calls did not release the claim
        orchestrator.execute(None)
    release.set()
    worker.join()
    assert type(outcome[0]) is BatchExecutionResult and orchestrator._busy is False
    with pytest.raises(OrchestrationConsumedError):
        orchestrator.execute(preview)
    assert orchestrator._busy is False
    with pytest.raises(OrchestrationInputError):
        orchestrator.execute(None)
    assert orchestrator._busy is False


def test_execute_can_run_in_a_worker_thread_from_an_event_loop(tmp_path):
    corpus, orchestrator, preview, _ = _three_ready(tmp_path)

    async def scenario():
        return await asyncio.to_thread(orchestrator.execute, preview)

    result = run(scenario())
    assert sum(i.execution_status is ExecutionStatus.SUCCESS for i in result.items) == 3


def test_warnings_carry_the_preview_warnings_in_declaration_order(tmp_path):
    film = Film("FC2-PPV-1000001.mp4", kind="partial", poster=False, extra=1, extra_fail=1)
    corpus, orchestrator, preview, _ = _prepared(tmp_path, [film])
    (executed,) = orchestrator.execute(preview).items
    assert executed.warnings == preview.items[0].warnings == (W.METADATA_PARTIAL, W.POSTER_ABSENT,
                                                              W.IMAGE_CANDIDATE_FAILURES)


def test_execution_result_objects_are_the_p4c7_results(tmp_path, monkeypatch):
    corpus, orchestrator, preview, _ = _three_ready(tmp_path)
    returned: list[object] = []

    def recording(preflight):
        result = execute_filesystem(preflight)
        returned.append(result)
        return result

    _Spy(monkeypatch, recording)
    result = orchestrator.execute(preview)
    executed = [i.execution for i in result.items if i.execution is not None]
    assert len(executed) == 3 and all(any(a is b for b in returned) for a in executed)
    assert tampered(preview) is not preview  # helper sanity (shallow copy)
