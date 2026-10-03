"""P4-C9 contract sections 10 / 12.1 / 12.6 / 12.8: ``build_execution_diagnostics`` on real (public-constructor)
P4-C8 execution results -- every disposition, the three statuses, failure mapping, effect / artifact counts,
checkpoint presence, leftovers, the MAIN / RETRY / MERGED shapes and the six ``RetryKind`` values."""

from __future__ import annotations

import pytest
from fc2_organizer.diagnostics import (
    DiagnosticsKind,
    PathPolicy,
    ResultShape,
    build_execution_diagnostics,
)
from fc2_organizer.execution import (
    EffectKind,
    ExecutionFailureKind,
    ExecutionStatus as X,
    ExecutionStep,
    PreflightMode,
    TransferMode,
)
from fc2_organizer.materialization import ArtifactKind
from fc2_organizer.orchestration import (
    BatchOutcome,
    ExecutionDisposition as D,
    IssueReason as R,
    ItemWarning as W,
    OrchestrationStage,
    PreviewState as S,
    RetryKind as K,
)

from . import _builders as b


def build(result, **kwargs):
    return build_execution_diagnostics(result, **kwargs)


def executed(lineage, index, status=X.SUCCESS, **kwargs):
    execution = b.rich_execution(lineage.plans[index], status, **kwargs)
    warnings = (W.LEFTOVER_TEMPORARIES,) if kwargs.get("leftovers") else ()
    return lineage.execution_item(index, D.EXECUTED, execution=execution, warnings=warnings,
                                  material=True if status is not X.SUCCESS else ...)


def test_a_successful_main_result_is_projected_field_by_field():
    lineage = b.Lineage(2)
    result = lineage.result([executed(lineage, 0), executed(lineage, 1)])
    diag = build(result)
    assert diag.kind is DiagnosticsKind.EXECUTION and diag.shape is ResultShape.MAIN
    assert diag.generation == 0 and diag.batch_size == 2 and diag.retry_scope is None
    assert diag.outcome is BatchOutcome.SUCCESS is result.outcome
    assert diag.execution_summary == result.summary and diag.preview_summary is None
    for item in diag.items:
        assert item.disposition is D.EXECUTED and item.retry_kind is K.NONE
        assert item.retry_material_retained is False and item.retry_origin is None and item.preflight is None
        assert item.issue is None and item.preview_state is S.READY
        assert item.execution.status is X.SUCCESS and item.execution.failure is None
        assert item.execution.checkpoint_present is False and item.execution.mode is PreflightMode.FRESH
        assert item.execution.transfer_mode is TransferMode.SAME_VOLUME and item.execution.new_effect_count == 3


def test_effect_and_artifact_counts_list_every_member_in_declaration_order():
    lineage = b.Lineage(1)
    out = build(lineage.result([executed(lineage, 0)])).items[0].execution
    assert [kind for kind, _ in out.effect_counts] == list(EffectKind)
    assert dict(out.effect_counts) == {
        EffectKind.TARGET_DIRECTORY_CREATED: 1, EffectKind.MEDIA_PUBLISHED: 1, EffectKind.SOURCE_REMOVED: 1,
        EffectKind.ARTIFACT_PUBLISHED: 4, EffectKind.EXTRAFANART_DIRECTORY_CREATED: 1}
    assert [kind for kind, _ in out.artifact_counts] == list(ArtifactKind)
    assert dict(out.artifact_counts) == {ArtifactKind.NFO: 1, ArtifactKind.POSTER: 1, ArtifactKind.FANART: 0,
                                         ArtifactKind.THUMB: 0, ArtifactKind.EXTRAFANART: 2}


def test_a_partial_execution_has_a_checkpoint_flag_and_the_failure_object():
    lineage = b.Lineage(1)
    item = executed(lineage, 0, X.PARTIAL, failure_kind=ExecutionFailureKind.ARTIFACT_WRITE_FAILED)
    out = build(lineage.result([item])).items[0]
    assert out.execution.status is X.PARTIAL and out.execution.checkpoint_present is True
    assert out.execution.failure.kind is ExecutionFailureKind.ARTIFACT_WRITE_FAILED
    assert out.execution.failure.errno == 13 and out.execution.failure.step is ExecutionStep.MOVE_MEDIA
    assert out.issue.reason is R.EXECUTION_PARTIAL and out.issue.stage is OrchestrationStage.EXECUTION
    assert out.issue.detail is ExecutionFailureKind.ARTIFACT_WRITE_FAILED and out.issue.error_type is None
    assert out.retry_kind is K.RESUME and out.retry_material_retained is True


def test_a_failed_execution_has_no_effects_and_no_checkpoint():
    lineage = b.Lineage(1)
    out = build(lineage.result([executed(lineage, 0, X.FAILED)])).items[0]
    assert out.execution.status is X.FAILED and out.execution.checkpoint_present is False
    assert out.execution.new_effect_count == 0 and all(count == 0 for _, count in out.execution.effect_counts)
    assert out.issue.reason is R.EXECUTION_FAILED and out.retry_kind is K.FRESH_REEXECUTE


def test_leftover_temporaries_are_counted_and_their_names_are_not_output_by_default():
    lineage = b.Lineage(1)
    item = executed(lineage, 0, leftovers=2)
    result = lineage.result([item])
    out = build(result).items[0]
    assert out.execution.leftover_temporary_count == 2
    assert [(l.directory_role.name, l.name) for l in out.execution.leftover_temporaries] == [
        ("TARGET_DIRECTORY", None), ("TARGET_DIRECTORY", None)]
    named = build(result, path_policy=PathPolicy.BASENAME).items[0].execution
    assert [l.name for l in named.leftover_temporaries] == [
        l.name for l in item.execution.leftover_temporaries]


def test_skipped_steps_are_carried_in_order():
    lineage = b.Lineage(1)
    skipped = (ExecutionStep.MATERIALIZE_POSTER, ExecutionStep.MATERIALIZE_THUMB)
    out = build(lineage.result([executed(lineage, 0, skipped=skipped)])).items[0]
    assert out.execution.skipped_steps == skipped


# ---- the six dispositions and the six retry kinds


def _items_of_every_kind():
    lineage = b.Lineage(9, kinds={8: "engine"})
    items = [
        executed(lineage, 0, X.SUCCESS),                                                               # NONE
        executed(lineage, 1, X.PARTIAL),                                                               # RESUME
        executed(lineage, 2, X.FAILED),                                                                # FRESH
        lineage.execution_item(3, D.NOT_SELECTED, material=True),                                      # DEFERRED
        lineage.execution_item(4, D.CANCELLED, material=True),                                         # DEFERRED
        lineage.execution_item(5, D.REJECTED, reason=R.EXECUTION_REJECTED, issue_kwargs={"error_type": "E"}),
        lineage.execution_item(6, D.ABORTED, reason=R.EXECUTION_ABORTED, issue_kwargs={"error_type": "E"}),
        lineage.execution_item(7, D.NOT_READY, state=S.BLOCKED, reason=R.PREFLIGHT_BLOCKED, material=True,
                               execution=None),                                                        # RECHECK
        lineage.execution_item(8, D.NOT_READY, state=S.UNPREPARED, reason=R.METADATA_ENGINE_FAILURE,
                               with_plan=False, issue_kwargs={"error_type": "RuntimeError",
                                                              "detail": b.BatchItemErrorKind.ENGINE_EXCEPTION}),
    ]
    return lineage, items


def test_every_disposition_and_retry_kind_equals_the_p4_c8_values():
    lineage, items = _items_of_every_kind()
    result = lineage.result(items)
    diag = build(result)
    assert [i.disposition for i in diag.items] == [item.disposition for item in result.items]
    assert [i.retry_kind for i in diag.items] == [item.retry_kind for item in result.items]
    assert {i.retry_kind for i in diag.items} == set(K)
    assert [i.retry_material_retained for i in diag.items] == [item.retry_material is not None
                                                                 for item in result.items]
    assert [i.preview_state for i in diag.items] == [item.preview_state for item in result.items]
    assert [i.execution is not None for i in diag.items] == [item.execution is not None for item in result.items]
    assert diag.execution_summary == result.summary and diag.outcome is result.outcome


def test_not_ready_items_have_no_execution_diagnostics_and_a_preview_issue():
    lineage, items = _items_of_every_kind()
    diag = build(lineage.result(items))
    blocked = diag.items[7]
    assert blocked.execution is None and blocked.preview_state is S.BLOCKED
    assert blocked.issue.reason is R.PREFLIGHT_BLOCKED and blocked.preflight is None  # no blocker detail on results
    engine = diag.items[8]
    assert engine.preview_state is S.UNPREPARED and engine.issue.reason is R.METADATA_ENGINE_FAILURE
    assert engine.issue.error_type == "RuntimeError"
    assert engine.metadata.error_kind is b.BatchItemErrorKind.ENGINE_EXCEPTION and engine.metadata.sources == ()


def test_execution_diagnostics_never_carry_preflight_blockers():
    lineage, items = _items_of_every_kind()
    assert all(i.preflight is None for i in build(lineage.result(items)).items)


def test_execution_warnings_are_the_item_field_in_declaration_order():
    lineage = b.Lineage(1, kinds={0: "partial"})
    item = lineage.execution_item(0, D.EXECUTED, execution=b.rich_execution(lineage.plans[0], leftovers=1),
                                  warnings=(W.METADATA_PARTIAL, W.POSTER_ABSENT, W.LEFTOVER_TEMPORARIES))
    out = build(lineage.result([item])).items[0]
    assert out.warnings == (W.METADATA_PARTIAL, W.POSTER_ABSENT, W.LEFTOVER_TEMPORARIES)


# ---- the three shapes


def test_main_shape():
    lineage = b.Lineage(2)
    diag = build(lineage.result([executed(lineage, 0), executed(lineage, 1)]))
    assert diag.shape is ResultShape.MAIN and diag.generation == 0 and diag.retry_scope is None


def test_retry_shape_has_scope_generation_and_partial_indices():
    lineage = b.Lineage(5)
    scope = frozenset({K.RESUME, K.FRESH_REEXECUTE})
    items = [lineage.execution_item(1, D.EXECUTED, status=X.SUCCESS, generation=1),
             lineage.execution_item(3, D.EXECUTED, status=X.SUCCESS, generation=1)]
    result = lineage.result(items, generation=1, base_result_id=b.new_id(), retry_scope=scope, retry_budget=1000)
    diag = build(result)
    assert diag.shape is ResultShape.RETRY and diag.generation == 1
    assert diag.retry_scope == (K.FRESH_REEXECUTE, K.RESUME)
    assert [i.index for i in diag.items] == [1, 3] and diag.batch_size == 5
    assert all(i.generation == 1 and i.retry_origin is None for i in diag.items)


def test_merged_shape_allows_items_of_older_generations():
    lineage = b.Lineage(3)
    items = [lineage.execution_item(0, D.EXECUTED, status=X.SUCCESS, generation=0),
             lineage.execution_item(1, D.EXECUTED, status=X.SUCCESS, generation=2),
             lineage.execution_item(2, D.EXECUTED, status=X.SUCCESS, generation=1)]
    result = lineage.result(items, generation=2, preview_id=None)
    diag = build(result)
    assert diag.shape is ResultShape.MERGED and diag.generation == 2 and diag.retry_scope is None
    assert [i.generation for i in diag.items] == [0, 2, 1]


def test_shape_is_derived_locally_and_agrees_with_every_p4_c8_produced_form():
    lineage = b.Lineage(2)
    main = lineage.result([executed(lineage, 0), executed(lineage, 1)])
    retry = lineage.result([lineage.execution_item(1, D.EXECUTED, status=X.SUCCESS, generation=1)], generation=1,
                           base_result_id=b.new_id(), retry_scope=frozenset(), retry_budget=1000)
    merged = lineage.result([lineage.execution_item(0, D.EXECUTED, status=X.SUCCESS, generation=1),
                             lineage.execution_item(1, D.EXECUTED, status=X.SUCCESS, generation=0)],
                            generation=1, preview_id=None)
    assert [build(r).shape for r in (main, retry, merged)] == [ResultShape.MAIN, ResultShape.RETRY,
                                                               ResultShape.MERGED]
    assert [r.is_complete for r in (main, retry, merged)] == [True, False, True]


def test_an_empty_execution_result_builds_with_outcome_success():
    lineage = b.Lineage(0)
    diag = build(lineage.result([]))
    assert diag.items == () and diag.outcome is BatchOutcome.SUCCESS and diag.execution_summary.total == 0


def test_the_outcome_is_carried_for_partial_and_failed_batches():
    lineage = b.Lineage(2)
    partial = lineage.result([executed(lineage, 0), executed(lineage, 1, X.FAILED)])
    failed = lineage.result([executed(lineage, 0, X.FAILED), executed(lineage, 1, X.FAILED)])
    assert build(partial).outcome is BatchOutcome.PARTIAL is partial.outcome
    assert build(failed).outcome is BatchOutcome.FAILED is failed.outcome


def test_build_is_deterministic_for_the_same_input():
    lineage, items = _items_of_every_kind()
    result = lineage.result(items)
    assert build(result) == build(result)
