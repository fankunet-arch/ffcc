"""P4-C8 S1: models and invariants (contract sections 8, 10.2-10.7, 19.6.2, 19.6.10).

Every invariant has at least one accepted and one rejected case. Expected values are stated from the
frozen contract text, never recomputed through production helpers.
"""

from __future__ import annotations

import dataclasses
import os

import pytest

from fc2_metadata_core.batch import BatchItemErrorKind, BatchItemStatus, BatchLineage
from fc2_organizer.discovery import DiscoveredMediaItem
from fc2_organizer.execution import (
    ArtifactManifestError,
    CheckpointError,
    CheckpointRejectionReason,
    ExecutionFailureKind,
    ExecutionStatus,
    ManifestRejectionReason,
    PlanGraphError,
    PlanGraphRejectionReason,
    PreflightIntegrityError,
    PreflightIntegrityReason,
    PreflightMode,
)
from fc2_organizer.images import ImageAcquisitionPolicy
from fc2_organizer.materialization import (
    ArtifactKind,
    ArtifactMappingError,
    ArtifactWriteRequest,
    MappingRejectionReason,
)
from fc2_organizer.orchestration import (
    MAX_BATCH_ITEMS,
    MAX_RETAINED_ARTIFACT_BYTES_LIMIT,
    BatchExecutionResult,
    BatchPreview,
    ExecutionDisposition as D,
    IssueReason as R,
    ItemExecution,
    ItemIssue,
    ItemPreview,
    ItemWarning as W,
    OrchestrationContractError,
    OrchestrationIntegrityError,
    OrchestrationStage as St,
    PreviewState as S,
    ResourceLimitReason,
    RetryKind as K,
    RetryMaterial,
)
from fc2_organizer.orchestration.models import reason_detail, retry_payload_bytes, revalidate, type_name
from fc2_organizer.planning import OutputPolicy

from ._helpers import (
    LIBRARY,
    NFO_BYTES,
    Lineage,
    fake_checkpoint,
    fake_execution,
    fake_preflight,
    image_failure,
    issue,
    manifest_for,
    media_item,
    metadata_batch,
    new_id,
    payload,
    plan_for,
    tampered,
)

LIMIT_B = MAX_RETAINED_ARTIFACT_BYTES_LIMIT


# =========================================================================== ItemIssue (10.2), row by row

_FOREIGN = ResourceLimitReason.BATCH_ITEM_LIMIT
# reason -> (stage, error_type required, accepted details (None = "no detail" accepted), detail required)
ISSUE_TABLE = {
    R.NUMBER_NOT_RECOGNIZED: (St.NUMBER_RECOGNITION, False, [None], False),
    R.DUPLICATE_SOURCE_IN_BATCH: (St.BATCH_CONFLICT, False, [None], False),
    R.DUPLICATE_TARGET_IN_BATCH: (St.BATCH_CONFLICT, False, [None], False),
    R.METADATA_UNAVAILABLE: (St.METADATA, False, [None], False),
    R.METADATA_ENGINE_FAILURE: (St.METADATA, True, [BatchItemErrorKind.ENGINE_EXCEPTION,
                                                    BatchItemErrorKind.RESULT_CONTRACT_MISMATCH], True),
    R.PLANNING_REJECTED: (St.PLANNING, True, [None], False),
    R.PUBLICATION_REJECTED: (St.PUBLICATION, True, [None], False),
    R.NFO_RENDER_FAILED: (St.NFO_RENDER, True, [None], False),
    R.IMAGE_ACQUISITION_ERROR: (St.IMAGE_ACQUISITION, True, [None], False),
    R.MANIFEST_REJECTED: (St.MANIFEST, True, [MappingRejectionReason.NFO_EMPTY, None], False),
    R.PREFLIGHT_BLOCKED: (St.PREFLIGHT, False, [None], False),
    R.PREFLIGHT_REJECTED: (St.PREFLIGHT, True, [PlanGraphRejectionReason.SOURCE_INSIDE_TARGET,
                                               ManifestRejectionReason.ORDER, None], False),
    R.CHECKPOINT_REJECTED: (St.PREFLIGHT, True, [CheckpointRejectionReason.CONSUMED], True),
    R.EXECUTION_FAILED: (St.EXECUTION, False, [ExecutionFailureKind.SOURCE_CHANGED], True),
    R.EXECUTION_PARTIAL: (St.EXECUTION, False, [ExecutionFailureKind.SOURCE_UNLINK_FAILED], True),
    R.EXECUTION_REJECTED: (St.EXECUTION, True, [PreflightIntegrityReason.SEAL_INVALID,
                                               CheckpointRejectionReason.CONSUMED,
                                               PlanGraphRejectionReason.FIELD_TYPE,
                                               ManifestRejectionReason.NFO_MISSING, None], False),
    R.EXECUTION_ABORTED: (St.EXECUTION, True, [None], False),
}


def test_issue_table_covers_every_reason():
    assert set(ISSUE_TABLE) == set(R)


@pytest.mark.parametrize("reason", list(R))
def test_issue_row_accepted_combinations(reason):
    stage, needs_type, details, _ = ISSUE_TABLE[reason]
    for detail in details:
        made = ItemIssue(stage, reason, "SomeError" if needs_type else None, detail)
        assert (made.stage, made.reason, made.detail) == (stage, reason, detail)


@pytest.mark.parametrize("reason", list(R))
def test_issue_row_rejected_combinations(reason):
    stage, needs_type, details, needs_detail = ISSUE_TABLE[reason]
    error_type = "SomeError" if needs_type else None
    detail = details[0]
    wrong_stage = next(s for s in St if s is not stage)
    bad = [
        dict(stage=wrong_stage, error_type=error_type, detail=detail),
        dict(stage=stage, error_type=None if needs_type else "SomeError", detail=detail),
        dict(stage=stage, error_type=error_type, detail=_FOREIGN),
    ]
    if needs_detail:
        bad.append(dict(stage=stage, error_type=error_type, detail=None))
    for fields in bad:
        with pytest.raises(OrchestrationContractError):
            ItemIssue(reason=reason, **fields)


class _StrSub(str):
    pass


@pytest.mark.parametrize("bad", ["", "not an identifier", "x" * 129, "1abc", _StrSub("SomeError"), 42, b"Err"])
def test_issue_error_type_must_be_a_short_identifier_str(bad):
    with pytest.raises(OrchestrationContractError):
        ItemIssue(St.PLANNING, R.PLANNING_REJECTED, bad)
    assert ItemIssue(St.PLANNING, R.PLANNING_REJECTED, "x" * 128).error_type == "x" * 128


def test_issue_stage_and_reason_must_be_members():
    with pytest.raises(OrchestrationContractError):
        ItemIssue("planning", R.PLANNING_REJECTED, "E")  # type: ignore[arg-type]
    with pytest.raises(OrchestrationContractError):
        ItemIssue(St.PLANNING, "planning_rejected", "E")  # type: ignore[arg-type]


# =========================================================================== ItemPreview (10.3)


def _preview_ok(**changes):
    lineage = Lineage(3)
    base = lineage.preview_item(0)
    fields = {f.name: getattr(base, f.name) for f in dataclasses.fields(ItemPreview)}
    fields.update(changes)
    return lineage, fields


def _new_preview_item(**changes) -> ItemPreview:
    _, fields = _preview_ok(**changes)
    return ItemPreview(**fields)


def test_ready_item_is_accepted():
    item = _new_preview_item()
    assert item.state is S.READY and item.issue is None and item.executable is True


@pytest.mark.parametrize("changes", [
    {"issue": issue(R.NFO_RENDER_FAILED, error_type="E")},  # READY with an issue
    {"state": S.BLOCKED},  # no issue but not READY
    {"state": S.UNPREPARED},
])
def test_ready_iff_no_issue(changes):
    with pytest.raises(OrchestrationContractError):
        _new_preview_item(**changes)


def test_ready_requires_a_ready_preflight_without_conflicts():
    lineage = Lineage(2)
    plan = lineage.plans[0]
    with pytest.raises(OrchestrationContractError):
        lineage.preview_item(0, preflight=None)
    with pytest.raises(OrchestrationContractError):
        lineage.preview_item(0, preflight=fake_preflight(plan, ready=False))
    with pytest.raises(OrchestrationContractError):
        lineage.preview_item(0, conflict_with=(1,))


def test_blocked_preflight_item():
    lineage = Lineage(1)
    plan = lineage.plans[0]
    item = lineage.preview_item(0, state=S.BLOCKED, reason=R.PREFLIGHT_BLOCKED,
                                preflight=fake_preflight(plan, ready=False))
    assert item.blockers and item.executable is False
    for bad in (dict(preflight=None), dict(preflight=fake_preflight(plan, ready=True))):
        with pytest.raises(OrchestrationContractError):
            lineage.preview_item(0, state=S.BLOCKED, reason=R.PREFLIGHT_BLOCKED, **bad)
    with pytest.raises(OrchestrationContractError):
        lineage.preview_item(0, state=S.UNPREPARED, reason=R.PREFLIGHT_BLOCKED,
                             preflight=fake_preflight(plan, ready=False))


def test_preflight_blocked_item_has_no_conflicts():
    lineage = Lineage(2)
    with pytest.raises(OrchestrationContractError):
        lineage.preview_item(0, state=S.BLOCKED, reason=R.PREFLIGHT_BLOCKED, conflict_with=(1,),
                             preflight=fake_preflight(lineage.plans[0], ready=False))


@pytest.mark.parametrize("reason", [R.DUPLICATE_SOURCE_IN_BATCH, R.DUPLICATE_TARGET_IN_BATCH])
def test_duplicate_items_phase_a_and_phase_b(reason):
    lineage = Lineage(2)
    phase_a = lineage.preview_item(0, state=S.BLOCKED, reason=reason, conflict_with=(1,), with_plan=False,
                                   with_metadata=False)
    assert phase_a.preflight is None and phase_a.executable is False
    phase_b = lineage.preview_item(0, state=S.BLOCKED, reason=reason, conflict_with=(1,),
                                   preflight=fake_preflight(lineage.plans[0], ready=True))
    assert phase_b.preflight.ready is True and phase_b.executable is False
    with pytest.raises(OrchestrationContractError):
        lineage.preview_item(0, state=S.BLOCKED, reason=reason, conflict_with=(), with_plan=False)
    with pytest.raises(OrchestrationContractError):
        lineage.preview_item(0, state=S.UNPREPARED, reason=reason, conflict_with=(1,), with_plan=False)


def test_unprepared_item_has_no_preflight_and_no_conflicts():
    lineage = Lineage(2)
    ok = lineage.preview_item(0, state=S.UNPREPARED, reason=R.NFO_RENDER_FAILED, issue_kwargs={"error_type": "E"})
    assert ok.preflight is None and ok.plan is not None
    with pytest.raises(OrchestrationContractError):
        lineage.preview_item(0, state=S.UNPREPARED, reason=R.NFO_RENDER_FAILED, issue_kwargs={"error_type": "E"},
                             preflight=fake_preflight(lineage.plans[0], ready=False))
    with pytest.raises(OrchestrationContractError):
        lineage.preview_item(0, state=S.UNPREPARED, reason=R.NFO_RENDER_FAILED, issue_kwargs={"error_type": "E"},
                             conflict_with=(1,))
    with pytest.raises(OrchestrationContractError):
        lineage.preview_item(0, state=S.BLOCKED, reason=R.NFO_RENDER_FAILED, issue_kwargs={"error_type": "E"})


def test_preview_never_carries_an_execution_stage_issue():
    lineage = Lineage(1)
    with pytest.raises(OrchestrationContractError):
        lineage.preview_item(0, state=S.UNPREPARED, reason=R.EXECUTION_ABORTED, issue_kwargs={"error_type": "E"})


def test_canonical_number_rules():
    lineage = Lineage(1)
    unrecognized = lineage.preview_item(0, state=S.UNPREPARED, reason=R.NUMBER_NOT_RECOGNIZED, with_plan=False,
                                        with_metadata=False)
    assert unrecognized.canonical_number is None
    with pytest.raises(OrchestrationContractError):
        _new_preview_item(canonical_number=None)
    for bad in ("FC2-12", "fc2-1000000", _StrSub("FC2-1000000"), 1000000):
        with pytest.raises(OrchestrationContractError):
            _new_preview_item(canonical_number=bad)


def test_metadata_rules():
    lineage, fields = _preview_ok()
    ItemPreview(**fields)
    with pytest.raises(OrchestrationContractError):
        ItemPreview(**{**fields, "metadata_position": None})
    with pytest.raises(OrchestrationContractError):
        ItemPreview(**{**fields, "metadata": None})
    with pytest.raises(OrchestrationContractError):
        ItemPreview(**{**fields, "metadata_position": 1})  # metadata.index != position
    with pytest.raises(OrchestrationContractError):
        ItemPreview(**{**fields, "metadata": lineage.metadata.items[1], "metadata_position": 1})  # other number
    with pytest.raises(OrchestrationContractError):
        ItemPreview(**{**fields, "metadata_position": True})


def test_plan_and_preflight_rules():
    lineage, fields = _preview_ok()
    other_source = plan_for(media_item(0, "FC2-PPV-1000000.mkv", directory=LIBRARY + "x"), "FC2-1000000")
    with pytest.raises(OrchestrationContractError):
        ItemPreview(**{**fields, "plan": other_source, "preflight": fake_preflight(other_source)})
    other_number = plan_for(lineage.media[0], "FC2-7777777")
    with pytest.raises(OrchestrationContractError):
        ItemPreview(**{**fields, "plan": other_number, "preflight": fake_preflight(other_number)})
    equal_copy = plan_for(lineage.media[0], "FC2-1000000")
    assert equal_copy == fields["plan"]
    with pytest.raises(OrchestrationContractError):
        ItemPreview(**{**fields, "preflight": fake_preflight(equal_copy)})  # preflight.plan is not plan
    with pytest.raises(OrchestrationContractError):
        ItemPreview(**{**fields, "plan": None})


def test_retry_origin_rules():
    lineage = Lineage(1)
    retry = lineage.preview_item(0, generation=1, retry_origin=K.DEFERRED)
    assert retry.retry_origin is K.DEFERRED
    for bad in (dict(generation=1, retry_origin=None), dict(generation=0, retry_origin=K.DEFERRED),
                dict(generation=1, retry_origin=K.NONE), dict(generation=1, retry_origin="deferred")):
        with pytest.raises(OrchestrationContractError):
            lineage.preview_item(0, **bad)


@pytest.mark.parametrize("bad", [[], [image_failure()], (object(),), None])
def test_image_failures_are_a_strict_tuple(bad):
    with pytest.raises(OrchestrationContractError):
        _new_preview_item(image_failures=bad)
    assert _new_preview_item(image_failures=(image_failure(),)).image_failures


@pytest.mark.parametrize("bad", [(2, 1), (1, 1), (0,), (True,), (-1,), [1], ("1",)])
def test_conflict_with_is_strictly_increasing_peers_without_self(bad):
    lineage = Lineage(3)
    with pytest.raises(OrchestrationContractError):
        lineage.preview_item(0, state=S.BLOCKED, reason=R.DUPLICATE_TARGET_IN_BATCH, conflict_with=bad,
                             with_plan=False, with_metadata=False)


@pytest.mark.parametrize("field, bad", [("index", -1), ("index", True), ("generation", -1), ("generation", 1.0),
                                        ("state", "ready")])
def test_item_scalar_fields(field, bad):
    with pytest.raises(OrchestrationContractError):
        _new_preview_item(**{field: bad})


def test_media_item_must_be_exact():
    class Sub(DiscoveredMediaItem):
        pass

    lineage, fields = _preview_ok()
    source = fields["media_item"]
    sub = Sub(index=0, source_path=source.source_path, relative_path="a.mp4", extension=".mp4", size=100)
    with pytest.raises(OrchestrationContractError):
        ItemPreview(**{**fields, "media_item": sub})


def test_display_properties_with_a_full_manifest():
    lineage = Lineage(1)
    plan = lineage.plans[0]
    artifacts = manifest_for(plan, extra=(b"e1", b"e2"))
    item = lineage.preview_item(0, preflight=fake_preflight(plan, artifacts))
    assert item.source_path == lineage.media[0].source_path and item.source_size == 100
    assert item.target_directory == plan.target_directory.absolute_path
    assert item.final_media_path == plan.target_media_path.absolute_path
    assert item.nfo_target == plan.nfo_path.absolute_path
    assert item.extrafanart_directory == plan.extrafanart_directory.absolute_path
    assert item.poster_target == plan.poster_path.absolute_path
    assert item.fanart_target == plan.fanart_path.absolute_path
    assert item.thumb_target == plan.thumb_path.absolute_path
    assert item.artifact_kinds == (ArtifactKind.NFO, ArtifactKind.POSTER, ArtifactKind.FANART, ArtifactKind.THUMB,
                                   ArtifactKind.EXTRAFANART, ArtifactKind.EXTRAFANART)
    assert item.extrafanart_count == 2
    assert item.preflight_mode is PreflightMode.FRESH
    assert item.planned_units == () and item.completed_units == () and item.skipped_steps == ()
    assert item.predicted_transfer_mode is None and item.blockers == ()
    assert item.warnings == () and item.executable is True


def test_display_properties_with_missing_images():
    lineage = Lineage(1)
    plan = lineage.plans[0]
    item = lineage.preview_item(0, preflight=fake_preflight(plan, manifest_for(plan, poster=None, thumb=None)))
    assert item.poster_target is None and item.thumb_target is None
    assert item.fanart_target == plan.fanart_path.absolute_path
    assert item.extrafanart_count == 0
    assert item.warnings == (W.POSTER_ABSENT, W.THUMB_ABSENT, W.NO_EXTRAFANART)


def test_display_properties_with_a_plan_but_no_preflight_and_without_a_plan():
    lineage = Lineage(1)
    with_plan = lineage.preview_item(0, state=S.UNPREPARED, reason=R.NFO_RENDER_FAILED,
                                     issue_kwargs={"error_type": "E"})
    assert with_plan.target_directory == lineage.plans[0].target_directory.absolute_path
    for name in ("poster_target", "fanart_target", "thumb_target", "artifact_kinds", "extrafanart_count",
                 "preflight_mode", "planned_units", "completed_units", "skipped_steps", "predicted_transfer_mode",
                 "blockers"):
        assert getattr(with_plan, name) is None, name
    assert with_plan.warnings == ()  # no preflight: no image-absence warnings
    without = lineage.preview_item(0, state=S.UNPREPARED, reason=R.PLANNING_REJECTED,
                                   issue_kwargs={"error_type": "InvalidLibraryRootError"}, with_plan=False)
    for name in ("target_directory", "final_media_path", "nfo_target", "extrafanart_directory"):
        assert getattr(without, name) is None
    assert without.source_path == lineage.media[0].source_path


def test_warnings_follow_declaration_order():
    lineage = Lineage(1, kinds={0: "partial"})
    plan = lineage.plans[0]
    item = lineage.preview_item(0, preflight=fake_preflight(plan, manifest_for(plan, fanart=None)),
                                image_failures=(image_failure(),))
    assert item.warnings == (W.METADATA_PARTIAL, W.FANART_ABSENT, W.NO_EXTRAFANART, W.IMAGE_CANDIDATE_FAILURES)
    assert "warnings" not in {f.name for f in dataclasses.fields(ItemPreview)}


# =========================================================================== BatchPreview (10.4)


def _main_preview(size: int = 3, **kwargs):
    lineage = Lineage(size)
    return lineage, lineage.preview([lineage.preview_item(i) for i in range(size)], **kwargs)


def test_main_preview_is_accepted():
    lineage, preview = _main_preview()
    assert preview.generation == 0 and preview.base_result_id is None and preview.retry_scope is None
    assert preview.retry_budget_bytes is None and preview.lineage == lineage.metadata.lineage
    assert "preview_id" not in repr(preview) and preview.preview_id not in repr(preview)


@pytest.mark.parametrize("bad", ["A" * 32, "0" * 31, "g" * 32, 1, None, _StrSub("0" * 32)])
def test_preview_id_is_32_lowercase_hex(bad):
    lineage, preview = _main_preview()
    with pytest.raises(OrchestrationContractError):
        BatchPreview(**{**_fields(preview), "preview_id": bad})


def _fields(model) -> dict:
    return {f.name: getattr(model, f.name) for f in dataclasses.fields(model)}


def test_main_preview_must_cover_every_index_in_order():
    lineage = Lineage(3)
    items = [lineage.preview_item(i) for i in range(3)]
    with pytest.raises(OrchestrationContractError):
        lineage.preview(items[:2])
    with pytest.raises(OrchestrationContractError):
        lineage.preview([items[1], items[0], items[2]])


def test_main_preview_couples_base_scope_and_generation():
    lineage, preview = _main_preview()
    fields = _fields(preview)
    for bad in (dict(base_result_id=new_id()), dict(retry_scope=frozenset({K.DEFERRED})), dict(generation=1),
                dict(retry_budget_bytes=5)):
        with pytest.raises(OrchestrationContractError):
            BatchPreview(**{**fields, **bad})


def test_retry_preview_rules():
    lineage = Lineage(4)
    scope = frozenset({K.DEFERRED, K.RESUME})
    items = [lineage.preview_item(i, generation=1, retry_origin=K.DEFERRED) for i in (1, 3)]
    preview = lineage.preview(items, generation=1, base_result_id=new_id(), retry_scope=scope, retry_budget=10 ** 6)
    assert [i.index for i in preview.items] == [1, 3]
    fields = _fields(preview)
    bad_cases = [
        dict(items=tuple(reversed(items))),
        dict(items=(items[0], items[0])),
        dict(batch_size=3),  # index 3 >= batch_size
        dict(retry_scope=frozenset({K.RESUME})),  # retry_origin not in scope
        dict(retry_scope=frozenset({K.DEFERRED, K.NONE})),
        dict(retry_scope={K.DEFERRED}),
        dict(retry_budget_bytes=None),
        dict(base_result_id=None),
        dict(generation=2),  # items carry generation 1
        dict(base_result_id="X" * 32),
    ]
    for bad in bad_cases:
        with pytest.raises(OrchestrationContractError):
            BatchPreview(**{**fields, **bad})
    empty = lineage.preview([], generation=1, base_result_id=new_id(), retry_scope=frozenset(), retry_budget=0)
    assert empty.items == ()


def test_preview_metadata_ledger_rules():
    lineage, preview = _main_preview()
    fields = _fields(preview)
    with pytest.raises(OrchestrationContractError):
        BatchPreview(**{**fields, "lineage": BatchLineage.new()})
    other = metadata_batch(tuple(lineage.metadata.items), lineage=lineage.metadata.lineage)
    with pytest.raises(OrchestrationContractError):  # equal ledger, but items are not `is` metadata_batch.items
        BatchPreview(**{**fields, "metadata_batch": other.__class__(
            tuple(dataclasses.replace(i) for i in lineage.metadata.items), lineage=lineage.metadata.lineage)})
    short = metadata_batch(lineage.metadata.items[:1], lineage=lineage.metadata.lineage)
    with pytest.raises(OrchestrationContractError):
        BatchPreview(**{**fields, "metadata_batch": short})


def test_preview_top_level_field_types():
    lineage, preview = _main_preview()
    fields = _fields(preview)

    class Policy(OutputPolicy):
        pass

    for bad in (dict(library_root=""), dict(library_root=None), dict(output_policy=Policy()),
                dict(image_policy=None), dict(batch_size=MAX_BATCH_ITEMS + 1), dict(items=list(preview.items)),
                dict(generation=-1)):
        with pytest.raises(OrchestrationContractError):
            BatchPreview(**{**fields, **bad})


def test_preview_conflict_graph_is_symmetric_within_the_preview():
    lineage = Lineage(3)
    a = lineage.preview_item(0, state=S.BLOCKED, reason=R.DUPLICATE_TARGET_IN_BATCH, conflict_with=(1,),
                             with_plan=False, with_metadata=False)
    b = lineage.preview_item(1, state=S.BLOCKED, reason=R.DUPLICATE_TARGET_IN_BATCH, conflict_with=(0,),
                             with_plan=False, with_metadata=False)
    lineage.preview([a, b, lineage.preview_item(2)])
    lonely = lineage.preview_item(1, state=S.BLOCKED, reason=R.DUPLICATE_TARGET_IN_BATCH, conflict_with=(2,),
                                  with_plan=False, with_metadata=False)
    with pytest.raises(OrchestrationContractError):
        lineage.preview([a, lonely, lineage.preview_item(2)])


@pytest.mark.parametrize("budget, ok", [(0, False), (1, True), (LIMIT_B, True), (LIMIT_B + 1, False),
                                        (True, False), (1.0, False)])
def test_preview_retention_budget_range(budget, ok):
    lineage = Lineage(0)
    if ok:
        assert lineage.preview([], budget=budget).retention_budget_bytes == budget
    else:
        with pytest.raises(OrchestrationContractError):
            lineage.preview([], budget=budget)


def test_preview_retained_artifact_bytes_exact_and_bounded():
    lineage = Lineage(3)
    plan0, plan1 = lineage.plans[0], lineage.plans[1]
    shared = b"S" * 1000
    art0 = manifest_for(plan0, poster=shared, fanart=shared, thumb=None)  # one bytes object, two references
    art1 = manifest_for(plan1, extra=(b"x" * 7,))
    items = [lineage.preview_item(0, preflight=fake_preflight(plan0, art0)),
             lineage.preview_item(1, state=S.BLOCKED, reason=R.PREFLIGHT_BLOCKED,
                                  preflight=fake_preflight(plan1, art1, ready=False)),
             lineage.preview_item(2, state=S.UNPREPARED, reason=R.NFO_RENDER_FAILED,
                                  issue_kwargs={"error_type": "E"})]
    exact = len(NFO_BYTES) * 2 + 2000 + (10 + 20 + 30 + 7)
    assert payload(art0) + payload(art1) == exact
    preview = lineage.preview(items, budget=exact)
    assert preview.retained_artifact_bytes == exact
    with pytest.raises(OrchestrationContractError):
        lineage.preview(items, budget=exact - 1)


def test_retry_preview_retained_bytes_are_bounded_by_the_retry_budget():
    lineage = Lineage(2)
    plan = lineage.plans[1]
    artifacts = manifest_for(plan)
    item = lineage.preview_item(1, generation=1, retry_origin=K.DEFERRED, preflight=fake_preflight(plan, artifacts))
    size = payload(artifacts)
    scope = frozenset({K.DEFERRED})
    ok = lineage.preview([item], generation=1, base_result_id=new_id(), retry_scope=scope, budget=size * 3,
                         retry_budget=size)
    assert ok.retained_artifact_bytes == size
    with pytest.raises(OrchestrationContractError):
        lineage.preview([item], generation=1, base_result_id=new_id(), retry_scope=scope, budget=size * 3,
                        retry_budget=size - 1)
    for bad_budget in (-1, size * 3 + 1, True):
        with pytest.raises(OrchestrationContractError):
            lineage.preview([], generation=1, base_result_id=new_id(), retry_scope=scope, budget=size * 3,
                            retry_budget=bad_budget)


# =========================================================================== RetryMaterial (10.5)


def test_retry_material_types():
    plan = Lineage(1).plans[0]
    artifacts = manifest_for(plan)
    material = RetryMaterial(plan, artifacts, None)
    assert material.artifacts is artifacts
    assert RetryMaterial(plan, artifacts, fake_checkpoint(plan)).checkpoint is not None
    for bad in (dict(plan=None), dict(artifacts=list(artifacts)), dict(artifacts=(object(),)),
                dict(checkpoint=object())):
        with pytest.raises(OrchestrationContractError):
            RetryMaterial(**{"plan": plan, "artifacts": artifacts, "checkpoint": None, **bad})


def test_retry_payload_bytes_is_exact_and_counts_shared_bytes_per_reference():
    plan = Lineage(1).plans[0]
    shared = b"z" * 333
    artifacts = manifest_for(plan, poster=shared, fanart=shared, thumb=shared, extra=(shared, b"q"))
    assert retry_payload_bytes(RetryMaterial(plan, artifacts, None)) == len(NFO_BYTES) + 4 * 333 + 1
    with pytest.raises(OrchestrationContractError):
        retry_payload_bytes(object())  # type: ignore[arg-type]


# =========================================================================== ItemExecution (10.6)


def test_item_execution_rows_accepted():
    lineage = Lineage(2)
    assert lineage.execution_item(0, D.EXECUTED, status=ExecutionStatus.SUCCESS).issue is None
    failed = lineage.execution_item(0, D.EXECUTED, status=ExecutionStatus.FAILED, material=True)
    assert failed.issue.reason is R.EXECUTION_FAILED and failed.issue.detail is failed.execution.failure.kind
    partial = lineage.execution_item(0, D.EXECUTED, status=ExecutionStatus.PARTIAL, material=True)
    assert partial.issue.reason is R.EXECUTION_PARTIAL and partial.execution_status is ExecutionStatus.PARTIAL
    assert lineage.execution_item(0, D.NOT_SELECTED, material=True).issue is None
    assert lineage.execution_item(0, D.CANCELLED, material=True).execution is None
    assert lineage.execution_item(0, D.REJECTED, reason=R.EXECUTION_REJECTED,
                                  issue_kwargs={"error_type": "PreflightIntegrityError",
                                                "detail": PreflightIntegrityReason.CONSUMED}).issue
    assert lineage.execution_item(0, D.ABORTED, reason=R.EXECUTION_ABORTED,
                                  issue_kwargs={"error_type": "RuntimeError"}).execution_status is None
    blocked = lineage.execution_item(0, D.NOT_READY, state=S.BLOCKED, reason=R.PREFLIGHT_BLOCKED, material=True)
    assert blocked.preview_state is S.BLOCKED


def test_item_execution_rows_rejected():
    lineage = Lineage(2)
    plan = lineage.plans[0]
    ERR = {"error_type": "E"}
    bad_calls = [
        dict(disposition=D.EXECUTED, execution=None),
        dict(disposition=D.NOT_SELECTED, execution=fake_execution(plan, ExecutionStatus.SUCCESS)),
        dict(disposition=D.EXECUTED, status=ExecutionStatus.SUCCESS, reason=R.EXECUTION_ABORTED, issue_kwargs=ERR),
        dict(disposition=D.EXECUTED, status=ExecutionStatus.FAILED, material=True,
             issue_kwargs={"detail": ExecutionFailureKind.SOURCE_MISSING}),  # detail != failure.kind
        dict(disposition=D.EXECUTED, execution=fake_execution(plan, ExecutionStatus.FAILED), material=True,
             reason=R.EXECUTION_PARTIAL, issue_kwargs={"detail": ExecutionFailureKind.MEDIA_TRANSFER_FAILED}),
        dict(disposition=D.EXECUTED, status=ExecutionStatus.SUCCESS, state=S.BLOCKED),
        dict(disposition=D.NOT_READY, state=S.READY, reason=R.NFO_RENDER_FAILED, issue_kwargs=ERR),
        dict(disposition=D.NOT_READY, state=S.UNPREPARED),  # no issue
        dict(disposition=D.NOT_READY, state=S.BLOCKED, reason=R.NFO_RENDER_FAILED, issue_kwargs=ERR),
        dict(disposition=D.NOT_READY, state=S.UNPREPARED, reason=R.PREFLIGHT_BLOCKED, material=True),
        dict(disposition=D.NOT_READY, state=S.UNPREPARED, reason=R.EXECUTION_ABORTED, issue_kwargs=ERR),
        dict(disposition=D.NOT_SELECTED, reason=R.EXECUTION_ABORTED, issue_kwargs=ERR, material=True),
        dict(disposition=D.CANCELLED, state=S.BLOCKED, material=True),
        dict(disposition=D.REJECTED, reason=R.EXECUTION_ABORTED, issue_kwargs=ERR),
        dict(disposition=D.REJECTED),
        dict(disposition=D.ABORTED),
        dict(disposition=D.ABORTED, reason=R.EXECUTION_REJECTED, issue_kwargs=ERR),
        dict(disposition=D.NOT_SELECTED, material=RetryMaterial(plan, manifest_for(plan), None),
             with_plan=False),  # READY without a plan
    ]
    for kwargs in bad_calls:
        disposition = kwargs.pop("disposition")
        with pytest.raises(OrchestrationContractError):
            lineage.execution_item(0, disposition, **kwargs)
    with pytest.raises(OrchestrationContractError):
        lineage.execution_item(0, "executed", status=ExecutionStatus.SUCCESS)  # type: ignore[arg-type]


def test_item_execution_conflicts_only_for_duplicates():
    lineage = Lineage(2)
    dup = lineage.execution_item(0, D.NOT_READY, state=S.BLOCKED, reason=R.DUPLICATE_SOURCE_IN_BATCH,
                                 conflict_with=(1,), with_plan=False, with_metadata=False)
    assert dup.conflict_with == (1,)
    with pytest.raises(OrchestrationContractError):
        lineage.execution_item(0, D.NOT_READY, state=S.BLOCKED, reason=R.DUPLICATE_SOURCE_IN_BATCH,
                               with_plan=False, with_metadata=False)
    with pytest.raises(OrchestrationContractError):
        lineage.execution_item(0, D.NOT_SELECTED, material=True, conflict_with=(1,))


def test_item_execution_warning_rules():
    lineage = Lineage(1, kinds={0: "partial"})
    ok = lineage.execution_item(0, D.EXECUTED, status=ExecutionStatus.SUCCESS,
                                execution=fake_execution(lineage.plans[0], ExecutionStatus.SUCCESS, leftovers=True),
                                warnings=(W.METADATA_PARTIAL, W.POSTER_ABSENT, W.IMAGE_CANDIDATE_FAILURES,
                                          W.LEFTOVER_TEMPORARIES),
                                image_failures=(image_failure(),))
    assert ok.warnings[-1] is W.LEFTOVER_TEMPORARIES
    bad = [
        dict(warnings=(W.METADATA_PARTIAL,) * 2),  # duplicate
        dict(warnings=(W.POSTER_ABSENT, W.METADATA_PARTIAL)),  # order
        dict(warnings=()),  # METADATA_PARTIAL missing although metadata is PARTIAL
        dict(warnings=(W.METADATA_PARTIAL, W.IMAGE_CANDIDATE_FAILURES)),  # no image failures
        dict(warnings=(W.METADATA_PARTIAL, W.LEFTOVER_TEMPORARIES)),  # no leftovers
        dict(warnings=[W.METADATA_PARTIAL]),
    ]
    for kwargs in bad:
        with pytest.raises(OrchestrationContractError):
            lineage.execution_item(0, D.EXECUTED, status=ExecutionStatus.SUCCESS, **kwargs)
    with pytest.raises(OrchestrationContractError):
        lineage.execution_item(0, D.NOT_READY, state=S.UNPREPARED, reason=R.NFO_RENDER_FAILED,
                               issue_kwargs={"error_type": "E"}, warnings=(W.METADATA_PARTIAL, W.POSTER_ABSENT))
    unprepared = lineage.execution_item(0, D.NOT_READY, state=S.UNPREPARED, reason=R.NFO_RENDER_FAILED,
                                        issue_kwargs={"error_type": "E"}, warnings=(W.METADATA_PARTIAL,))
    assert unprepared.warnings == (W.METADATA_PARTIAL,)


def test_item_execution_display_properties():
    lineage = Lineage(1)
    plan = lineage.plans[0]
    item = lineage.execution_item(0, D.EXECUTED, status=ExecutionStatus.SUCCESS)
    assert item.execution_status is ExecutionStatus.SUCCESS
    assert item.target_directory == plan.target_directory.absolute_path
    assert item.final_media_path == plan.target_media_path.absolute_path
    assert item.nfo_target == plan.nfo_path.absolute_path
    assert item.extrafanart_directory == plan.extrafanart_directory.absolute_path
    assert item.source_path == lineage.media[0].source_path and item.source_size == 100
    assert not hasattr(item, "poster_target")


# =========================================================================== BatchExecutionResult (10.7)


def _deferred_items(lineage: Lineage, generation: int = 0, artifacts=None):
    return [lineage.execution_item(i, D.NOT_SELECTED, material=True, generation=generation,
                                   artifacts=None if artifacts is None else artifacts[i])
            for i in range(lineage.size)]


def test_three_result_shapes_are_accepted():
    lineage = Lineage(2)
    main = lineage.result(_deferred_items(lineage))
    retry = lineage.result([_deferred_items(lineage, 1)[1]], generation=1, base_result_id=new_id(),
                           retry_scope=frozenset({K.DEFERRED}), retry_budget=10 ** 6)
    merged = lineage.result(_deferred_items(lineage, 1), generation=1, preview_id=None)
    assert (main.is_complete, retry.is_complete, merged.is_complete) == (True, False, True)
    assert main.result_id not in repr(main)


@pytest.mark.parametrize("changes", [
    dict(preview_id=None),  # generation 0 without a preview id
    dict(generation=1),  # main items carry generation 0 -> but shape needs base/preview coherence
    dict(base_result_id=new_id()),
    dict(retry_scope=frozenset({K.DEFERRED})),
    dict(retry_budget_bytes=10),
    dict(result_id="0" * 31),
    dict(preview_id="Z" * 32),
])
def test_invalid_main_result_shapes(changes):
    lineage = Lineage(2)
    main = lineage.result(_deferred_items(lineage))
    with pytest.raises(OrchestrationContractError):
        BatchExecutionResult(**{**_fields(main), **changes})


def test_invalid_retry_and_merged_shapes():
    lineage = Lineage(3)
    items1 = _deferred_items(lineage, 1)
    retry = lineage.result([items1[0], items1[2]], generation=1, base_result_id=new_id(),
                           retry_scope=frozenset({K.DEFERRED}), retry_budget=10 ** 6)
    fields = _fields(retry)
    for bad in (dict(retry_scope=None), dict(preview_id=None), dict(retry_budget_bytes=None),
                dict(items=(items1[2], items1[0])), dict(batch_size=2), dict(generation=2),
                dict(retry_scope=frozenset({K.NONE}))):
        with pytest.raises(OrchestrationContractError):
            BatchExecutionResult(**{**fields, **bad})
    merged = lineage.result(items1, generation=1, preview_id=None)
    fields = _fields(merged)
    for bad in (dict(items=tuple(items1[:2])), dict(generation=0), dict(retry_budget_bytes=5),
                dict(base_result_id=new_id())):
        with pytest.raises(OrchestrationContractError):
            BatchExecutionResult(**{**fields, **bad})
    newer = _deferred_items(lineage, 2)
    with pytest.raises(OrchestrationContractError):  # an item newer than the merged generation
        lineage.result(newer, generation=1, preview_id=None)
    mixed = [_deferred_items(lineage, 0)[0], items1[1], newer[2]]
    assert lineage.result(mixed, generation=2, preview_id=None).is_complete


def test_result_lineage_and_ledger():
    lineage = Lineage(1)
    main = lineage.result(_deferred_items(lineage))
    with pytest.raises(OrchestrationContractError):
        BatchExecutionResult(**{**_fields(main), "lineage": BatchLineage.new()})


def test_result_conflict_graph_is_symmetric():
    lineage = Lineage(2)
    a = lineage.execution_item(0, D.NOT_READY, state=S.BLOCKED, reason=R.DUPLICATE_TARGET_IN_BATCH,
                               conflict_with=(1,), with_plan=False, with_metadata=False)
    b = lineage.execution_item(1, D.NOT_READY, state=S.BLOCKED, reason=R.DUPLICATE_TARGET_IN_BATCH,
                               conflict_with=(0,), with_plan=False, with_metadata=False)
    lineage.result([a, b])
    with pytest.raises(OrchestrationContractError):
        lineage.result([a, lineage.execution_item(1, D.NOT_SELECTED, material=True)])


# ---- retention (E0-R2)


@pytest.mark.parametrize("budget, ok", [(0, False), (1, True), (LIMIT_B, True), (LIMIT_B + 1, False),
                                        (True, False)])
def test_result_retention_budget_range(budget, ok):
    lineage = Lineage(0)
    if ok:
        assert lineage.result([], budget=budget).retention_budget_bytes == budget
    else:
        with pytest.raises(OrchestrationContractError):
            lineage.result([], budget=budget)


def test_retry_budget_bytes_matches_the_shape():
    lineage = Lineage(2)
    with pytest.raises(OrchestrationContractError):
        lineage.result(_deferred_items(lineage), retry_budget=0)  # main
    with pytest.raises(OrchestrationContractError):
        lineage.result(_deferred_items(lineage, 1), generation=1, preview_id=None, retry_budget=0)  # merged
    scope = frozenset({K.DEFERRED})
    for bad in (None, -1, 101, True):
        with pytest.raises(OrchestrationContractError):
            lineage.result([], generation=1, base_result_id=new_id(), retry_scope=scope, budget=100,
                           retry_budget=bad)
    assert lineage.result([], generation=1, base_result_id=new_id(), retry_scope=scope, budget=100,
                          retry_budget=100).retry_budget_bytes == 100


def test_retained_retry_payload_bytes_is_exact_and_zero_for_non_material_items():
    lineage = Lineage(6, kinds={3: "failed"})
    plan = lineage.plans
    shared = b"s" * 50
    art = {i: manifest_for(plan[i], poster=shared, fanart=shared, thumb=None) for i in range(6)}
    items = [
        lineage.execution_item(0, D.EXECUTED, status=ExecutionStatus.SUCCESS),
        lineage.execution_item(1, D.ABORTED, reason=R.EXECUTION_ABORTED, issue_kwargs={"error_type": "E"}),
        lineage.execution_item(2, D.NOT_READY, state=S.UNPREPARED, reason=R.NFO_RENDER_FAILED,
                               issue_kwargs={"error_type": "E"}),
        lineage.execution_item(3, D.NOT_READY, state=S.UNPREPARED, reason=R.METADATA_UNAVAILABLE, with_plan=False),
        lineage.execution_item(4, D.NOT_SELECTED, material=True, artifacts=art[4]),
        lineage.execution_item(5, D.EXECUTED, status=ExecutionStatus.PARTIAL, material=True, artifacts=art[5]),
    ]
    assert [i.retry_kind for i in items] == [K.NONE, K.NONE, K.NONE, K.METADATA_REFETCH, K.DEFERRED, K.RESUME]
    per_item = len(NFO_BYTES) + 100  # shared bytes counted once per reference
    result = lineage.result(items)
    assert result.retained_retry_payload_bytes == 2 * per_item
    assert all(i.retry_material is None for i in items[:4])


def test_main_result_charge_equal_to_budget_is_accepted_and_one_more_is_rejected():
    lineage = Lineage(3)
    items = _deferred_items(lineage)
    charge = sum(payload(i.retry_material.artifacts) for i in items)
    assert lineage.result(items, budget=charge).retained_retry_payload_bytes == charge
    with pytest.raises(OrchestrationContractError):
        lineage.result(items, budget=charge - 1)


def test_merged_result_is_bounded_by_the_retention_budget():
    lineage = Lineage(3)
    items = _deferred_items(lineage, 1)
    charge = sum(payload(i.retry_material.artifacts) for i in items)
    assert lineage.result(items, generation=1, preview_id=None, budget=charge).is_complete
    with pytest.raises(OrchestrationContractError):
        lineage.result(items, generation=1, preview_id=None, budget=charge - 1)


def test_retry_round_result_is_bounded_by_the_retry_budget():
    lineage = Lineage(3)
    items = _deferred_items(lineage, 1)[1:]
    charge = sum(payload(i.retry_material.artifacts) for i in items)
    scope = frozenset({K.DEFERRED})
    ok = lineage.result(items, generation=1, base_result_id=new_id(), retry_scope=scope, budget=charge * 10,
                        retry_budget=charge)
    assert ok.retained_retry_payload_bytes == charge
    with pytest.raises(OrchestrationContractError):
        lineage.result(items, generation=1, base_result_id=new_id(), retry_scope=scope, budget=charge * 10,
                       retry_budget=charge - 1)


# =========================================================================== revalidate (18.1 step 3)


def test_revalidate_accepts_untouched_graphs():
    lineage, preview = _main_preview()
    revalidate(preview)
    revalidate(lineage.result(_deferred_items(lineage)))


def _expect_integrity(model):
    with pytest.raises(OrchestrationIntegrityError) as info:
        revalidate(model)
    assert info.value.__cause__ is None and info.value.__context__ is None


def test_revalidate_detects_tampered_preview_graphs():
    lineage, preview = _main_preview()
    object.__setattr__(preview.items[1], "index", 7)
    _expect_integrity(preview)
    lineage, preview = _main_preview()
    object.__setattr__(preview.items[0], "preflight", fake_preflight(lineage.plans[1]))  # foreign plan
    _expect_integrity(preview)
    lineage, preview = _main_preview()
    object.__setattr__(preview.items[0].preflight, "ready", False)
    _expect_integrity(preview)
    lineage, preview = _main_preview()
    object.__setattr__(preview, "retention_budget_bytes", 1)
    _expect_integrity(preview)
    lineage, preview = _main_preview()
    object.__setattr__(preview.items[0].preflight, "artifacts", (b"not a request",))
    _expect_integrity(preview)
    lineage, preview = _main_preview()
    object.__setattr__(preview.items[2], "issue", "hostile")
    _expect_integrity(preview)
    lineage, preview = _main_preview()
    object.__setattr__(preview, "items", list(preview.items))
    _expect_integrity(preview)


def test_revalidate_detects_tampered_result_graphs():
    lineage = Lineage(2)
    result = lineage.result(_deferred_items(lineage))
    object.__setattr__(result.items[0], "retry_material", None)
    _expect_integrity(result)
    result = lineage.result([lineage.execution_item(0, D.EXECUTED, status=ExecutionStatus.FAILED, material=True),
                             lineage.execution_item(1, D.NOT_SELECTED, material=True)])
    object.__setattr__(result.items[0].execution, "failure", object())
    _expect_integrity(result)
    result = lineage.result(_deferred_items(lineage))
    object.__setattr__(result, "retry_budget_bytes", 5)
    _expect_integrity(result)
    result = lineage.result(_deferred_items(lineage))
    object.__setattr__(result.items[1].retry_material.artifacts[0], "content", "not bytes")
    _expect_integrity(result)


def test_revalidate_rejects_foreign_objects_without_running_hooks():
    calls = []

    class Hostile:
        def __getattribute__(self, name):
            calls.append(name)
            raise AssertionError("hook ran")

    for foreign in (Hostile(), None, object()):
        _expect_integrity(foreign)
    assert calls == []
    lineage, preview = _main_preview()
    revalidate(tampered(preview))  # an unchanged shallow copy of an exact type is still intact
    _expect_integrity(tampered(preview, generation=1))


def test_constructing_a_preview_from_tampered_items_is_rejected():
    lineage = Lineage(2)
    items = [lineage.preview_item(i) for i in range(2)]
    object.__setattr__(items[1], "state", object())
    with pytest.raises(OrchestrationContractError):
        lineage.preview(items)


# =========================================================================== strict helpers (section 8)


def test_type_name_of_ordinary_objects():
    assert type_name(ValueError("x")) == "ValueError" and type_name(3) == "int"


def test_type_name_ignores_a_hostile_metaclass_and_never_runs_it():
    ran = []

    class Meta(type):
        @property
        def __name__(cls):  # pragma: no cover - must never run
            ran.append(1)
            return "Spoofed"

    class Victim(metaclass=Meta):
        pass

    assert type_name(Victim()) == "UnknownType" and ran == []


def test_type_name_ignores_instance_class_spoofing():
    class Spoof:
        @property
        def __class__(self):  # pragma: no cover - must never run
            raise AssertionError("ran")

    assert type_name(Spoof()) == "Spoof"


@pytest.mark.parametrize("name", ["not an identifier", "x" * 129, "", "1abc"])
def test_type_name_rejects_non_identifier_or_long_names(name):
    cls = type("Placeholder", (), {})
    cls.__name__ = name
    assert type_name(cls()) == "UnknownType"
    cls.__name__ = "x" * 128
    assert type_name(cls()) == "x" * 128


def test_reason_detail_reads_only_exact_typed_errors():
    assert reason_detail(PlanGraphError(PlanGraphRejectionReason.SOURCE_INSIDE_TARGET)) is \
        PlanGraphRejectionReason.SOURCE_INSIDE_TARGET
    assert reason_detail(ArtifactManifestError(ManifestRejectionReason.ORDER)) is ManifestRejectionReason.ORDER
    assert reason_detail(CheckpointError(CheckpointRejectionReason.CONSUMED)) is CheckpointRejectionReason.CONSUMED
    assert reason_detail(PreflightIntegrityError(PreflightIntegrityReason.SEAL_INVALID)) is \
        PreflightIntegrityReason.SEAL_INVALID
    assert reason_detail(ArtifactMappingError(MappingRejectionReason.NFO_EMPTY)) is MappingRejectionReason.NFO_EMPTY


def test_reason_detail_rejects_subclasses_wrong_values_and_foreign_errors():
    touched = []

    class SubError(PlanGraphError):
        def __getattribute__(self, name):  # pragma: no cover - must never run
            touched.append(name)
            return object.__getattribute__(self, name)

    sub = SubError(PlanGraphRejectionReason.FIELD_TYPE)
    touched.clear()
    assert reason_detail(sub) is None and touched == []
    wrong = PlanGraphError(PlanGraphRejectionReason.FIELD_TYPE)
    wrong.reason = ManifestRejectionReason.ORDER  # a member of another enum
    assert reason_detail(wrong) is None
    wrong.reason = "field_type"
    assert reason_detail(wrong) is None
    del wrong.reason
    assert reason_detail(wrong) is None
    assert reason_detail(ValueError("x")) is None and reason_detail(None) is None


def test_models_are_frozen_slotted_dataclasses():
    for model in (ItemIssue, ItemPreview, BatchPreview, RetryMaterial, ItemExecution, BatchExecutionResult):
        assert dataclasses.is_dataclass(model)
        assert model.__dataclass_params__.frozen is True
        assert "__slots__" in model.__dict__
    item = _new_preview_item()
    with pytest.raises((dataclasses.FrozenInstanceError, AttributeError, TypeError)):
        item.index = 3  # type: ignore[misc]


def test_image_policy_field_exactness():
    class Sub(ImageAcquisitionPolicy):
        pass

    lineage, preview = _main_preview()
    with pytest.raises(OrchestrationContractError):
        BatchPreview(**{**_fields(preview), "image_policy": Sub()})


def test_metadata_engine_failure_issue_with_real_engine_item():
    lineage = Lineage(1, kinds={0: "engine"})
    item = lineage.preview_item(0, state=S.UNPREPARED, reason=R.METADATA_ENGINE_FAILURE, with_plan=False,
                                issue_kwargs={"error_type": "RuntimeError",
                                              "detail": BatchItemErrorKind.ENGINE_EXCEPTION})
    assert item.metadata.status is BatchItemStatus.FAILED
