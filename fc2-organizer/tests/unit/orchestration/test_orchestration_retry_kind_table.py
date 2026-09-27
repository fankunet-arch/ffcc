"""P4-C8 S1: ``ItemExecution.retry_kind`` decision table and ``RetryMaterial`` correspondence
(contract sections 10.6 and 25.1). Every expected kind below is stated literally from the frozen table."""

from __future__ import annotations

import pytest

from fc2_metadata_core.batch import BatchItemErrorKind
from fc2_organizer.execution import CheckpointRejectionReason, ExecutionStatus
from fc2_organizer.orchestration import (
    ExecutionDisposition as D,
    IssueReason as R,
    OrchestrationContractError,
    PreviewState as S,
    RetryKind as K,
    RetryMaterial,
)

from ._helpers import Lineage, fake_checkpoint, manifest_for, plan_for, media_item

ERR = {"error_type": "SomeError"}

# name -> (disposition, execution status, preview state, issue reason, issue kwargs, plan?, metadata kind,
#          expected retry kind)
ROWS = {
    "executed_success": (D.EXECUTED, ExecutionStatus.SUCCESS, S.READY, None, None, True, "success", K.NONE),
    "executed_partial": (D.EXECUTED, ExecutionStatus.PARTIAL, S.READY, None, None, True, "success", K.RESUME),
    "executed_failed": (D.EXECUTED, ExecutionStatus.FAILED, S.READY, None, None, True, "success",
                        K.FRESH_REEXECUTE),
    "metadata_unavailable": (D.NOT_READY, None, S.UNPREPARED, R.METADATA_UNAVAILABLE, None, False, "failed",
                             K.METADATA_REFETCH),
    "metadata_engine_failure": (D.NOT_READY, None, S.UNPREPARED, R.METADATA_ENGINE_FAILURE,
                                {"error_type": "RuntimeError", "detail": BatchItemErrorKind.ENGINE_EXCEPTION},
                                False, "engine", K.METADATA_REFETCH),
    "preflight_blocked": (D.NOT_READY, None, S.BLOCKED, R.PREFLIGHT_BLOCKED, None, True, "success",
                          K.PREFLIGHT_RECHECK),
    "number_not_recognized": (D.NOT_READY, None, S.UNPREPARED, R.NUMBER_NOT_RECOGNIZED, None, False, None, K.NONE),
    "planning_rejected": (D.NOT_READY, None, S.UNPREPARED, R.PLANNING_REJECTED, ERR, False, "success", K.NONE),
    "publication_rejected": (D.NOT_READY, None, S.UNPREPARED, R.PUBLICATION_REJECTED, ERR, True, "success",
                             K.NONE),
    "nfo_render_failed": (D.NOT_READY, None, S.UNPREPARED, R.NFO_RENDER_FAILED, ERR, True, "success", K.NONE),
    "image_acquisition_error": (D.NOT_READY, None, S.UNPREPARED, R.IMAGE_ACQUISITION_ERROR, ERR, True, "success",
                                K.NONE),
    "manifest_rejected": (D.NOT_READY, None, S.UNPREPARED, R.MANIFEST_REJECTED, ERR, True, "success", K.NONE),
    "preflight_rejected": (D.NOT_READY, None, S.UNPREPARED, R.PREFLIGHT_REJECTED, ERR, True, "success", K.NONE),
    "checkpoint_rejected": (D.NOT_READY, None, S.UNPREPARED, R.CHECKPOINT_REJECTED,
                            {"error_type": "CheckpointError", "detail": CheckpointRejectionReason.CONSUMED},
                            True, "success", K.NONE),
    "not_selected": (D.NOT_SELECTED, None, S.READY, None, None, True, "success", K.DEFERRED),
    "cancelled": (D.CANCELLED, None, S.READY, None, None, True, "success", K.DEFERRED),
    "rejected": (D.REJECTED, None, S.READY, R.EXECUTION_REJECTED, ERR, True, "success", K.NONE),
    "aborted": (D.ABORTED, None, S.READY, R.EXECUTION_ABORTED, ERR, True, "success", K.NONE),
}
MATERIAL_KINDS = {K.PREFLIGHT_RECHECK, K.FRESH_REEXECUTE, K.RESUME, K.DEFERRED}


def _build(name: str, *, material: bool | None = None, **overrides):
    disposition, status, state, reason, kwargs, with_plan, kind, expected = ROWS[name]
    lineage = Lineage(1, kinds={0: kind or "success"})
    needs_material = expected in MATERIAL_KINDS if material is None else material
    return lineage, lineage.execution_item(
        0, disposition, status=status, state=state, reason=reason, issue_kwargs=kwargs, with_plan=with_plan,
        with_metadata=kind is not None, material=True if needs_material else None, **overrides)


@pytest.mark.parametrize("name", list(ROWS))
def test_each_row_of_the_decision_table(name):
    _, item = _build(name)
    assert item.retry_kind is ROWS[name][-1]
    assert (item.retry_material is not None) == (ROWS[name][-1] in MATERIAL_KINDS)


@pytest.mark.parametrize("name, reason", [("blocked_duplicate_source", R.DUPLICATE_SOURCE_IN_BATCH),
                                          ("blocked_duplicate_target", R.DUPLICATE_TARGET_IN_BATCH)])
def test_batch_conflicts_are_never_retried(name, reason):
    lineage = Lineage(2)
    item = lineage.execution_item(0, D.NOT_READY, state=S.BLOCKED, reason=reason, conflict_with=(1,),
                                  with_plan=False, with_metadata=False)
    assert item.retry_kind is K.NONE and item.retry_material is None


def test_metadata_stage_wins_for_every_metadata_reason():
    for name in ("metadata_unavailable", "metadata_engine_failure"):
        _, item = _build(name)
        assert item.retry_kind is K.METADATA_REFETCH and item.retry_material is None


def test_retry_kind_is_a_pure_function_of_the_item():
    _, item = _build("executed_partial")
    assert item.retry_kind is item.retry_kind is K.RESUME
    assert "retry_kind" not in {f for f in type(item).__dataclass_fields__}


@pytest.mark.parametrize("name", [n for n in ROWS if ROWS[n][-1] in MATERIAL_KINDS])
def test_material_is_required_for_material_kinds(name):
    with pytest.raises(OrchestrationContractError):
        _build(name, material=False)


@pytest.mark.parametrize("name", [n for n in ROWS if ROWS[n][-1] not in MATERIAL_KINDS])
def test_material_is_forbidden_for_every_other_kind(name):
    if ROWS[name][5] is False:  # no plan: material cannot even be built for it
        lineage = Lineage(1)
        plan = lineage.plans[0]
        disposition, status, state, reason, kwargs, _, kind, _ = ROWS[name]
        with pytest.raises(OrchestrationContractError):
            lineage.execution_item(0, disposition, status=status, state=state, reason=reason, issue_kwargs=kwargs,
                                   with_plan=False, with_metadata=kind is not None,
                                   material=RetryMaterial(plan, manifest_for(plan), None))
        return
    with pytest.raises(OrchestrationContractError):
        _build(name, material=True)


def test_resume_material_carries_the_execution_checkpoint_itself():
    lineage, item = _build("executed_partial")
    assert item.retry_material.checkpoint is item.execution.checkpoint
    other = fake_checkpoint(lineage.plans[0])
    with pytest.raises(OrchestrationContractError):
        _build("executed_partial", checkpoint=other)
    with pytest.raises(OrchestrationContractError):
        _build("executed_partial", checkpoint=None)


def test_fresh_reexecute_material_has_no_checkpoint():
    lineage, item = _build("executed_failed")
    assert item.retry_material.checkpoint is None
    with pytest.raises(OrchestrationContractError):
        _build("executed_failed", checkpoint=fake_checkpoint(lineage.plans[0]))


@pytest.mark.parametrize("name", ["preflight_blocked", "not_selected", "cancelled"])
def test_recheck_and_deferred_material_keeps_the_preview_checkpoint_or_none(name):
    lineage, item = _build(name)
    assert item.retry_material.checkpoint is None
    checkpoint = fake_checkpoint(lineage.plans[0])
    _, resumed = _build(name, checkpoint=checkpoint)
    assert resumed.retry_material.checkpoint is checkpoint


def test_material_plan_must_be_the_item_plan_itself():
    lineage = Lineage(1)
    foreign = plan_for(media_item(0, "FC2-PPV-1000000.mp4"), "FC2-1000000")
    assert foreign == lineage.plans[0] and foreign is not lineage.plans[0]
    with pytest.raises(OrchestrationContractError):
        lineage.execution_item(0, D.NOT_SELECTED, material=RetryMaterial(foreign, manifest_for(foreign), None))


def test_material_artifacts_are_the_given_tuple_without_copy():
    lineage = Lineage(1)
    artifacts = manifest_for(lineage.plans[0])
    item = lineage.execution_item(0, D.CANCELLED, material=True, artifacts=artifacts)
    assert item.retry_material.artifacts is artifacts
    assert all(a is b for a, b in zip(item.retry_material.artifacts, artifacts))
