"""P4-C9 contract sections 10 / 12.1 / 12.8: ``build_preview_diagnostics`` on real (public-constructor) P4-C8
previews -- READY / BLOCKED / UNPREPARED, every preview-reachable ``IssueReason``, warnings, conflict groups and the
retry-round shape."""

from __future__ import annotations

import pytest
from fc2_metadata_core.batch import BatchItemErrorKind
from fc2_organizer.diagnostics import (
    DiagnosticsKind,
    PathPolicy,
    ResultShape,
    TimingPolicy,
    build_preview_diagnostics,
)
from fc2_organizer.execution import CheckpointRejectionReason, PlanGraphRejectionReason
from fc2_organizer.materialization import ArtifactKind, MappingRejectionReason
from fc2_organizer.orchestration import (
    IssueReason as R,
    ItemWarning as W,
    OrchestrationStage,
    PreviewState as S,
    RetryKind as K,
)

from . import _builders as b


def build(preview, **kwargs):
    return build_preview_diagnostics(preview, **kwargs)


def test_a_ready_main_preview_is_projected_field_by_field():
    lineage = b.Lineage(2)
    preview = lineage.preview([lineage.preview_item(0), lineage.preview_item(1)])
    diag = build(preview)
    assert diag.kind is DiagnosticsKind.PREVIEW and diag.shape is ResultShape.MAIN
    assert diag.generation == 0 and diag.batch_size == 2 and diag.retry_scope is None
    assert diag.path_policy is PathPolicy.NONE and diag.timing_policy is TimingPolicy.OMIT
    assert diag.preview_summary == preview.summary and diag.execution_summary is None and diag.outcome is None
    assert (diag.metadata_batch.generation, diag.metadata_batch.total, diag.metadata_batch.success,
            diag.metadata_batch.partial, diag.metadata_batch.failed) == (0, 2, 2, 0, 0)
    for source, item in zip(preview.items, diag.items):
        assert (item.index, item.generation, item.canonical_number) == (source.index, 0, source.canonical_number)
        assert item.source_size == source.media_item.size
        assert item.preview_state is S.READY and item.issue is None and item.conflict_with == ()
        assert item.retry_origin is None
        assert (item.disposition, item.retry_kind, item.retry_material_retained, item.execution) == (None,) * 4
        assert item.metadata is not None and item.metadata.status is source.metadata.status
        assert item.preflight is not None and item.preflight.ready is True
        assert item.source_name is item.target_directory_name is item.target_media_name is None


def test_preflight_diagnostics_carry_counts_and_the_manifest_kinds():
    lineage = b.Lineage(1)
    plan = lineage.plans[0]
    manifest = b.manifest_for(plan, poster=None, extra=(b"1", b"2"))
    preview = lineage.preview([lineage.preview_item(0, preflight=b.fake_preflight(plan, manifest))])
    preflight = build(preview).items[0].preflight
    assert dict(preflight.artifact_counts) == {ArtifactKind.NFO: 1, ArtifactKind.POSTER: 0, ArtifactKind.FANART: 1,
                                               ArtifactKind.THUMB: 1, ArtifactKind.EXTRAFANART: 2}
    assert [kind for kind, _ in preflight.artifact_counts] == list(ArtifactKind)
    assert (preflight.pending_unit_count, preflight.completed_unit_count, preflight.blockers) == (0, 0, ())


def test_blocked_preview_items_expose_the_preflight_blockers():
    lineage = b.Lineage(1)
    blocked_preflight = b.fake_preflight(lineage.plans[0], ready=False)
    item = lineage.preview_item(0, state=S.BLOCKED, reason=R.PREFLIGHT_BLOCKED, preflight=blocked_preflight)
    diag = build(lineage.preview([item]))
    out = diag.items[0]
    assert out.preview_state is S.BLOCKED and out.issue.reason is R.PREFLIGHT_BLOCKED
    assert out.issue.stage is OrchestrationStage.PREFLIGHT and out.issue.error_type is None
    assert out.preflight.ready is False and out.preflight.blockers == blocked_preflight.blockers
    assert diag.preview_summary.blocked == 1 and diag.preview_summary.ready == 0


# ---- every IssueReason a preview can carry (contract 10.3 / T-1)

_UNPREPARED_CASES = [
    (R.NUMBER_NOT_RECOGNIZED, dict(with_plan=False, with_metadata=False), None),
    (R.METADATA_UNAVAILABLE, dict(with_plan=False), None),
    (R.METADATA_ENGINE_FAILURE, dict(with_plan=False, issue_kwargs=dict(
        error_type="RuntimeError", detail=BatchItemErrorKind.ENGINE_EXCEPTION)), BatchItemErrorKind.ENGINE_EXCEPTION),
    (R.PLANNING_REJECTED, dict(with_plan=False, issue_kwargs=dict(error_type="InvalidLibraryRootError")), None),
    (R.PUBLICATION_REJECTED, dict(issue_kwargs=dict(error_type="PublicationError")), None),
    (R.NFO_RENDER_FAILED, dict(issue_kwargs=dict(error_type="NfoRenderError")), None),
    (R.IMAGE_ACQUISITION_ERROR, dict(issue_kwargs=dict(error_type="ImageError")), None),
    (R.MANIFEST_REJECTED, dict(issue_kwargs=dict(error_type="ArtifactMappingError")), None),
    (R.MANIFEST_REJECTED, dict(issue_kwargs=dict(error_type="ArtifactMappingError",
                                                 detail=next(iter(MappingRejectionReason)))),
     next(iter(MappingRejectionReason))),
    (R.PREFLIGHT_REJECTED, dict(issue_kwargs=dict(error_type="PlanGraphError",
                                                  detail=next(iter(PlanGraphRejectionReason)))),
     next(iter(PlanGraphRejectionReason))),
    (R.CHECKPOINT_REJECTED, dict(issue_kwargs=dict(error_type="CheckpointError",
                                                   detail=next(iter(CheckpointRejectionReason)))),
     next(iter(CheckpointRejectionReason))),
]


@pytest.mark.parametrize(("reason", "kwargs", "detail"), _UNPREPARED_CASES)
def test_every_unprepared_issue_reason_is_projected_with_its_stage_error_type_and_detail(reason, kwargs, detail):
    lineage = b.Lineage(1)
    item = lineage.preview_item(0, state=S.UNPREPARED, reason=reason, preflight=None, **kwargs)
    diag = build(lineage.preview([item]))
    out = diag.items[0]
    assert out.preview_state is S.UNPREPARED and out.preflight is None
    assert out.issue.reason is reason and out.issue.stage is item.issue.stage
    assert out.issue.error_type == item.issue.error_type and out.issue.detail is detail
    assert (out.canonical_number is None) == (reason is R.NUMBER_NOT_RECOGNIZED)
    assert diag.preview_summary.unprepared == 1


def test_number_not_recognized_has_no_metadata_and_no_number():
    lineage = b.Lineage(1)
    item = lineage.preview_item(0, state=S.UNPREPARED, reason=R.NUMBER_NOT_RECOGNIZED, preflight=None,
                                with_plan=False, with_metadata=False)
    out = build(lineage.preview([item])).items[0]
    assert out.canonical_number is None and out.metadata is None


def test_batch_conflict_groups_are_symmetric_conflict_with_tuples():
    lineage = b.Lineage(3)
    items = [
        lineage.preview_item(0, state=S.BLOCKED, reason=R.DUPLICATE_SOURCE_IN_BATCH, preflight=None,
                             conflict_with=(1, 2)),
        lineage.preview_item(1, state=S.BLOCKED, reason=R.DUPLICATE_SOURCE_IN_BATCH, preflight=None,
                             conflict_with=(0,)),
        lineage.preview_item(2, state=S.BLOCKED, reason=R.DUPLICATE_TARGET_IN_BATCH, preflight=None,
                             conflict_with=(0,)),
    ]
    items[2] = lineage.preview_item(2, state=S.BLOCKED, reason=R.DUPLICATE_TARGET_IN_BATCH, preflight=None,
                                    conflict_with=(0,))
    items[0] = lineage.preview_item(0, state=S.BLOCKED, reason=R.DUPLICATE_SOURCE_IN_BATCH, preflight=None,
                                    conflict_with=(1, 2))
    diag = build(lineage.preview(items))
    assert [i.conflict_with for i in diag.items] == [(1, 2), (0,), (0,)]
    assert [i.issue.reason for i in diag.items] == [R.DUPLICATE_SOURCE_IN_BATCH, R.DUPLICATE_SOURCE_IN_BATCH,
                                                    R.DUPLICATE_TARGET_IN_BATCH]
    assert all(i.preview_state is S.BLOCKED for i in diag.items)


def test_warnings_come_from_the_approved_property_in_declaration_order():
    lineage = b.Lineage(3, kinds={1: "partial"})
    plan0, plan1 = lineage.plans[0], lineage.plans[1]
    bare = b.manifest_for(plan0, poster=None, fanart=None, thumb=None)
    first = lineage.preview_item(0, preflight=b.fake_preflight(plan0, bare), image_failures=(b.image_failure(),))
    second = lineage.preview_item(1, preflight=b.fake_preflight(plan1))
    third = lineage.preview_item(2)
    preview = lineage.preview([first, second, third])
    diag = build(preview)
    assert diag.items[0].warnings == (W.POSTER_ABSENT, W.FANART_ABSENT, W.THUMB_ABSENT, W.NO_EXTRAFANART,
                                      W.IMAGE_CANDIDATE_FAILURES)
    assert diag.items[1].warnings == (W.METADATA_PARTIAL, W.NO_EXTRAFANART)
    assert diag.items[2].warnings == (W.NO_EXTRAFANART,)
    assert tuple(i.warnings for i in diag.items) == tuple(i.warnings for i in preview.items)
    assert diag.preview_summary.warned == 3


def test_image_failures_are_grouped_by_role_and_kind_with_distinct_ascending_http_statuses():
    from fc2_organizer.images import ImageCandidateFailure, ImageFailureKind, ImageRole

    def failure(role, kind, index, status=None):
        return ImageCandidateFailure(role=role, candidate_index=index, kind=kind, http_status=status)

    failures = (
        failure(ImageRole.EXTRAFANART, ImageFailureKind.HTTP_STATUS, 0, 500),
        failure(ImageRole.POSTER, ImageFailureKind.TIMEOUT, 0),
        failure(ImageRole.EXTRAFANART, ImageFailureKind.HTTP_STATUS, 1, 404),
        failure(ImageRole.EXTRAFANART, ImageFailureKind.HTTP_STATUS, 2, 404),
        failure(ImageRole.POSTER, ImageFailureKind.TIMEOUT, 1),
        failure(ImageRole.FANART, ImageFailureKind.INVALID_URL, 0),
        failure(ImageRole.POSTER, ImageFailureKind.HTTP_STATUS, 0, 403),
    )
    lineage = b.Lineage(1)
    diag = build(lineage.preview([lineage.preview_item(0, image_failures=failures)]))
    groups = diag.items[0].image_failures
    assert [(g.role, g.kind, g.count, g.http_statuses) for g in groups] == [
        (ImageRole.POSTER, ImageFailureKind.TIMEOUT, 2, ()),
        (ImageRole.POSTER, ImageFailureKind.HTTP_STATUS, 1, (403,)),
        (ImageRole.FANART, ImageFailureKind.INVALID_URL, 1, ()),
        (ImageRole.EXTRAFANART, ImageFailureKind.HTTP_STATUS, 3, (404, 500)),
    ]


def test_a_retry_preview_has_the_retry_shape_scope_and_retry_origin():
    lineage = b.Lineage(5)
    scope = frozenset({K.RESUME, K.METADATA_REFETCH, K.DEFERRED})
    items = [lineage.preview_item(1, generation=1, retry_origin=K.RESUME),
             lineage.preview_item(4, generation=1, retry_origin=K.DEFERRED)]
    preview = lineage.preview(items, generation=1, base_result_id=b.new_id(), retry_scope=scope, retry_budget=10**6)
    diag = build(preview)
    assert diag.shape is ResultShape.RETRY and diag.generation == 1 and diag.batch_size == 5
    assert diag.retry_scope == (K.METADATA_REFETCH, K.RESUME, K.DEFERRED)  # RetryKind declaration order
    assert [i.index for i in diag.items] == [1, 4]
    assert [i.retry_origin for i in diag.items] == [K.RESUME, K.DEFERRED]
    assert all(i.generation == 1 for i in diag.items)


def test_an_empty_retry_scope_is_legal_and_renders_as_an_empty_tuple():
    lineage = b.Lineage(2)
    preview = lineage.preview([], generation=1, base_result_id=b.new_id(), retry_scope=frozenset(),
                              retry_budget=1000)
    diag = build(preview)
    assert diag.shape is ResultShape.RETRY and diag.retry_scope == () and diag.items == ()
    assert diag.preview_summary.total == 0


def test_an_empty_main_preview_builds():
    lineage = b.Lineage(0)
    diag = build(lineage.preview([]))
    assert diag.batch_size == 0 and diag.items == () and diag.preview_summary.total == 0
    assert (diag.metadata_batch.total, diag.metadata_batch.success) == (0, 0)


def test_retry_scope_output_does_not_depend_on_frozenset_iteration_order():
    lineage = b.Lineage(2)
    items = [lineage.preview_item(0, generation=1, retry_origin=K.RESUME)]
    outputs = set()
    for ordering in ([K.DEFERRED, K.RESUME, K.FRESH_REEXECUTE], [K.FRESH_REEXECUTE, K.DEFERRED, K.RESUME],
                     [K.RESUME, K.FRESH_REEXECUTE, K.DEFERRED]):
        preview = lineage.preview(items, generation=1, base_result_id="a" * 32, retry_scope=frozenset(ordering),
                                  retry_budget=1000)
        outputs.add(build(preview).retry_scope)
    assert outputs == {(K.FRESH_REEXECUTE, K.RESUME, K.DEFERRED)}


def test_the_preview_summary_is_carried_not_recomputed():
    lineage = b.Lineage(3)
    preview = lineage.preview([
        lineage.preview_item(0), lineage.preview_item(1, state=S.UNPREPARED, reason=R.METADATA_UNAVAILABLE,
                                                      preflight=None, with_plan=False),
        lineage.preview_item(2, state=S.BLOCKED, reason=R.PREFLIGHT_BLOCKED,
                             preflight=b.fake_preflight(lineage.plans[2], ready=False))])
    diag = build(preview)
    assert diag.preview_summary == preview.summary
    assert (diag.preview_summary.ready, diag.preview_summary.blocked, diag.preview_summary.unprepared) == (1, 1, 1)


def test_build_is_deterministic_for_the_same_input():
    lineage = b.full_lineage(3)
    preview = lineage.preview([lineage.preview_item(i) for i in range(3)])
    assert build(preview) == build(preview)
    assert build(preview, path_policy=PathPolicy.BASENAME) == build(preview, path_policy=PathPolicy.BASENAME)
