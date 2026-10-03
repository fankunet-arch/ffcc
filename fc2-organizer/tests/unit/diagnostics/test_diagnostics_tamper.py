"""P4-C9 contract section 28.1 "tamper" row: ``object.__setattr__`` rewrites of upstream objects *behind their
constructors*, at every consumed model. Each case asserts (A) fail closed with the documented error class, (B) the
failure happens before projection and (for the broken dependency graph) before the approved property read,
(C) no partial diagnostic, (D) no hostile hook ran (the planted values here are plain, the hostile variants live in
the dispatch-safety / malicious-subclass files), (E) the (tampered) input is field-for-field unchanged and keeps
its node identities."""

from __future__ import annotations

import importlib
import types

import pytest
from fc2_metadata_core.aggregation import AggregateStatus
from fc2_metadata_core.batch import BatchItemStatus
from fc2_metadata_core.models import SourceErrorKind as E, SourceStatus as T
from fc2_organizer.diagnostics import DiagnosticsError, DiagnosticsIntegrityError as Int
from fc2_organizer.execution import ExecutionStatus as X
from fc2_organizer.orchestration import (
    ExecutionDisposition as D,
    IssueReason as R,
    ItemIssue,
    ItemPreview,
    OrchestrationStage,
    PreviewState as S,
    RetryKind,
)

from . import _builders as b
from . import _builders as h

build_module = importlib.import_module("fc2_organizer.diagnostics.build")
AGG = ("metadata_batch", "items", 0, "aggregation_result")


def at(root, path):
    return h.read(root, path) if path else root


def set_(path, value):
    return lambda g: h.write(g, path, value)


def set_many(where, **changes):
    return lambda g: b.poke(at(g, where), **changes)


PREVIEW_TAMPERS = {
    # ---- BatchPreview / BatchResult
    "preview.items_list": lambda g: b.poke(g, items=list(g.items)),
    "preview.batch_size_negative": set_many((), batch_size=-1),
    "preview.batch_size_bool": set_many((), batch_size=True),
    "preview.generation_str": set_many((), generation="0"),
    "preview.base_result_id_without_scope": set_many((), base_result_id="a" * 32),
    "preview.preview_id_short": set_many((), preview_id="abc"),
    "preview.retention_budget_zero": set_many((), retention_budget_bytes=0),
    "preview.retry_budget_over_retention": set_many((), retry_budget_bytes=10**9),
    "preview.metadata_batch_none": set_many((), metadata_batch=None),
    "metadata_batch.items_list": set_many(("metadata_batch",), items=list(h.preview_graph().metadata_batch.items)),
    "metadata_batch.generation_negative": set_many(("metadata_batch",), generation=-1),
    "metadata_batch.lineage_none": set_many(("metadata_batch",), lineage=None),
    # ---- BatchItemResult
    "batch_item.index_mismatch": set_many(("metadata_batch", "items", 0), index=1),
    "batch_item.number_invalid": set_many(("metadata_batch", "items", 0), number="not-a-number"),
    "batch_item.status_str": set_many(("metadata_batch", "items", 0), status="SUCCESS"),
    "batch_item.status_failed_with_aggregation": set_many(("metadata_batch", "items", 0),
                                                          status=BatchItemStatus.FAILED),
    "batch_item.elapsed_nan": set_many(("metadata_batch", "items", 0), elapsed_ms=float("nan")),
    "batch_item.aggregation_wrong_type": set_many(("metadata_batch", "items", 0), aggregation_result=object()),
    # ---- AggregationResult nested
    "aggregation.status_wrong": set_many(AGG, status=AggregateStatus.SUCCESS),
    "aggregation.source_results_list": set_many(AGG, source_results=list(at(h.preview_graph(), AGG).source_results)),
    "aggregation.source_results_empty": set_many(AGG, source_results=()),
    "aggregation.contributing_list": set_many(AGG, contributing_source_ids=["src_a", "src_c"]),
    "aggregation.contributing_unknown": set_many(AGG, contributing_source_ids=("src_a", "ghost")),
    "aggregation.contributing_duplicate": set_many(AGG, contributing_source_ids=("src_a", "src_a")),
    "aggregation.disabled_overlaps_result": set_many(AGG, disabled_source_ids=("src_a",)),
    "aggregation.disabled_duplicate": set_many(AGG, disabled_source_ids=("av123", "av123")),
    "aggregation.traces_wrong_length": set_many(AGG, source_execution_traces=at(h.preview_graph(), AGG)
                                                .source_execution_traces[:1]),
    "aggregation.conflicts_none": set_many(AGG, conflicts=None),
    "aggregation.elapsed_negative": set_many(AGG, elapsed_ms=-1.0),
    "aggregation.metadata_none": set_many(AGG, metadata=None),
    "aggregation.metadata_wrong_type": set_many(AGG, metadata=object()),
    "source_result.status_str": set_many(AGG + ("source_results", 0), status="SUCCESS"),
    "source_result.success_without_metadata": set_many(AGG + ("source_results", 0), metadata=None),
    "source_result.failure_with_metadata": set_many(AGG + ("source_results", 1), metadata=b.make_metadata_core()),
    "source_result.failure_without_kind": set_many(AGG + ("source_results", 1), error_kind=None),
    "source_result.kind_status_mismatch": set_many(AGG + ("source_results", 1), error_kind=E.NOT_FOUND),
    "source_result.blank_id": set_many(AGG + ("source_results", 0), source_id=" "),
    "source_result.detail_wrong_type": set_many(AGG + ("source_results", 1), error_detail=5),
    "source_result.success_metadata_without_valid_number": set_many(
        AGG + ("source_results", 0), metadata=b.make_metadata_core("FC2-7654321", title="  ")),
    "trace.source_id_mismatch": set_many(AGG + ("source_execution_traces", 0), source_id="src_b"),
    "trace.attempts_list": set_many(AGG + ("source_execution_traces", 1), attempts=[]),
    "trace.final_result_contradicts_last_attempt": set_many(
        AGG + ("source_execution_traces", 0), final_result=b.make_source_result("src_a", T.NOT_FOUND)),
    "trace.max_attempts_zero": set_many(AGG + ("source_execution_traces", 1), max_attempts=0),
    "trace.deadline_during_bad": set_many(AGG + ("source_execution_traces", 1), deadline_during="later"),
    "attempt.sequence_gap": set_many(AGG + ("source_execution_traces", 1, "attempts", 1), sequence=5),
    "attempt.status_str": set_many(AGG + ("source_execution_traces", 1, "attempts", 0), status="x"),
    "attempt.first_backoff": set_many(AGG + ("source_execution_traces", 1, "attempts", 0),
                                      backoff_before_seconds=1.0),
    "attempt.completed_int": set_many(AGG + ("source_execution_traces", 1, "attempts", 0), completed=1),
    "conflict.field_unknown": set_many(AGG + ("conflicts", 0), field="not_a_field"),
    "conflict.selected_not_contributing": set_many(AGG + ("conflicts", 0), selected_source_id="src_x"),
    "conflict.alternatives_list": set_many(AGG + ("conflicts", 0), alternatives=[("src_c", "x")]),
    "conflict.alternative_is_selected": set_many(AGG + ("conflicts", 0),
                                                 alternatives=(("src_a", "Other Title"),)),
    "conflict.alternative_equals_selected_value": set_many(AGG + ("conflicts", 0), selected_value="Other Title"),
    "conflict.value_bool": set_many(AGG + ("conflicts", 0), selected_value=True),
    "metadata.field_sources_dict": set_many(AGG + ("metadata",), field_sources={"number": ("src_a",)}),
    "metadata.provenance_unknown_source": lambda g: b.poke(
        at(g, AGG + ("metadata",)), field_sources=types.MappingProxyType({"number": ("ghost",)})),
    # ---- ItemPreview and its plan / preflight / artifacts
    "item.state_str": set_many(("items", 0), state="READY"),
    "item.index_gap": set_many(("items", 1), index=5),
    "item.generation_negative": set_many(("items", 0), generation=-1),
    "item.number_mismatch": set_many(("items", 0), canonical_number="FC2-7654321"),
    "item.metadata_position_wrong": set_many(("items", 0), metadata_position=1),
    "item.metadata_not_identical": set_many(("items", 0), metadata=b.full_lineage(2).metadata.items[0]),
    "item.ready_without_plan": set_many(("items", 0), plan=None),
    "item.ready_with_issue": set_many(("items", 0), issue=ItemIssue(OrchestrationStage.PLANNING, R.PLANNING_REJECTED, "E",
                                                                    None)),
    "item.conflict_with_asymmetric": set_many(("items", 0), conflict_with=(1,)),
    "item.conflict_with_self": set_many(("items", 0), conflict_with=(0,)),
    "item.image_failures_list": set_many(("items", 0), image_failures=[]),
    "item.retry_origin_none_on_retry": set_many(("items", 0), retry_origin=RetryKind.RESUME),
    "plan.source_path_relative": set_many(("items", 0, "plan"), source_path="relative/x.mp4"),
    "plan.source_size_negative": set_many(("items", 0, "plan"), source_size=-1),
    "plan.operations_list": set_many(("items", 0, "plan"), operations=[]),
    "plan.operations_wrong_kinds": set_many(("items", 0, "plan"), operations=()),
    "plan.number_mismatch": set_many(("items", 0, "plan"), canonical_number="FC2-7654321"),
    "plan.extension_no_dot": set_many(("items", 0, "plan"), source_extension="mp4"),
    "plan.target_path_not_planned_path": set_many(("items", 0, "plan"), target_media_path="/x/y.mp4"),
    "operation.kind_str": set_many(("items", 0, "plan", "operations", 0), kind="move"),
    "operation.target_str": set_many(("items", 0, "plan", "operations", 1), target="/x"),
    "preflight.artifacts_list": set_many(("items", 0, "preflight"), artifacts=[]),
    "preflight.ready_str": set_many(("items", 0, "preflight"), ready="yes"),
    "preflight.id_short": set_many(("items", 0, "preflight"), preflight_id="x"),
    "preflight.fingerprint_not_hex": set_many(("items", 0, "preflight"), plan_fingerprint="Z" * 64),
    "preflight.blockers_wrong_element": set_many(("items", 0, "preflight"), blockers=(1,)),
    "preflight.skipped_steps_wrong": set_many(("items", 0, "preflight"), skipped_steps=("x",)),
    "artifact.kind_str": set_many(("items", 0, "preflight", "artifacts", 0), kind="nfo"),
    "artifact.content_str": set_many(("items", 0, "preflight", "artifacts", 0), content="text"),
    "artifact.content_bytearray": set_many(("items", 0, "preflight", "artifacts", 0), content=bytearray(b"x")),
    "artifact.ordinal_bool": set_many(("items", 0, "preflight", "artifacts", 0), ordinal=True),
    "artifact.target_relative": set_many(("items", 0, "preflight", "artifacts", 0), target_path="rel/x.nfo"),
}

EXECUTION_TAMPERS = {
    "result.items_list": lambda g: b.poke(g, items=list(g.items)),
    "result.result_id_bad": set_many((), result_id="zz"),
    "result.preview_id_bad": set_many((), preview_id="zz"),
    "result.batch_size_wrong": set_many((), batch_size=3),
    "result.retention_budget_zero": set_many((), retention_budget_bytes=0),
    "item.disposition_str": set_many(("items", 0), disposition="EXECUTED"),
    "item.preview_state_str": set_many(("items", 0), preview_state="READY"),
    "item.executed_without_execution": set_many(("items", 0), execution=None),
    "item.not_selected_with_execution": set_many(("items", 3), execution=b.rich_execution(
        h.execution_graph().items[0].plan, X.SUCCESS)),
    "item.not_ready_without_issue": set_many(("items", 7), issue=None),
    "item.warnings_list": set_many(("items", 1), warnings=[]),
    "item.warnings_missing_leftover": set_many(("items", 1), warnings=()),
    "item.retry_material_for_success": set_many(("items", 0), retry_material=h.execution_graph().items[1]
                                                .retry_material),
    "item.retry_material_missing_for_partial": set_many(("items", 1), retry_material=None),
    "item.index_gap": set_many(("items", 2), index=7),
    "execution.status_str": set_many(("items", 1, "execution"), status="PARTIAL"),
    "execution.failure_missing_for_partial": set_many(("items", 1, "execution"), failure=None),
    "execution.failure_for_success": set_many(("items", 0, "execution"),
                                              failure=h.execution_graph().items[2].execution.failure),
    "execution.effects_list": set_many(("items", 1, "execution"), completed_effects=[]),
    "execution.new_effect_count_over": set_many(("items", 1, "execution"), new_effect_count=999),
    "execution.new_effect_count_negative": set_many(("items", 1, "execution"), new_effect_count=-1),
    "execution.checkpoint_for_success": set_many(("items", 0, "execution"),
                                                 checkpoint=h.execution_graph().items[1].execution.checkpoint),
    "execution.checkpoint_missing_for_partial": set_many(("items", 1, "execution"), checkpoint=None),
    "execution.leftover_list": set_many(("items", 1, "execution"), leftover_temporaries=[]),
    "execution.media_sha_short": set_many(("items", 1, "execution"), media_sha256="abc"),
    "execution.preflight_id_bad": set_many(("items", 1, "execution"), preflight_id="x"),
    "execution.skipped_steps_wrong": set_many(("items", 1, "execution"), skipped_steps=("x",)),
    "effect.kind_str": set_many(("items", 1, "execution", "completed_effects", 0), kind="x"),
    "effect.role_wrong": set_many(("items", 1, "execution", "completed_effects", 0), role="x"),
    "effect.ordinal_bool": set_many(("items", 1, "execution", "completed_effects", 6), ordinal=True),
    "failure.kind_str": set_many(("items", 2, "execution", "failure"), kind="x"),
    "failure.step_str": set_many(("items", 2, "execution", "failure"), step="x"),
    "failure.errno_bool": set_many(("items", 2, "execution", "failure"), errno=True),
    "failure.target_published_int": set_many(("items", 2, "execution", "failure"), target_published=1),
    "leftover.name_not_tmp": set_many(("items", 1, "execution", "leftover_temporaries", 0), name="movie.mp4"),
    "leftover.role_str": set_many(("items", 1, "execution", "leftover_temporaries", 0), directory_role="x"),
    "material.plan_not_item_plan": lambda g: b.poke(g.items[1].retry_material, plan=g.items[2].plan),
    "material.artifacts_list": set_many(("items", 1, "retry_material"), artifacts=[]),
    "material.checkpoint_wrong_type": set_many(("items", 1, "retry_material"), checkpoint=object()),
    "material.artifact_content_str": set_many(("items", 1, "retry_material", "artifacts", 0), content="x"),
    "material.artifact_wrong_type": set_many(("items", 1, "retry_material"), artifacts=(object(),)),
}


def fail_closed_untouched(kind, tamper, label, *, error=Int):
    graph = h.FACTORY[kind]()
    h.BUILD[kind](graph)  # the pristine graph builds: any rejection below is attributable to the tamper
    tamper(graph)
    before, ids = b.fingerprint(graph), b.identities(graph)
    b.reset_hits()
    reached = []
    original = build_module.project_batch
    build_module.project_batch = lambda *args, **kwargs: reached.append(1) or original(*args, **kwargs)
    try:
        with pytest.raises(DiagnosticsError) as caught:
            h.BUILD[kind](graph)
    finally:
        build_module.project_batch = original
    assert type(caught.value) is error, "%s: %r" % (label, caught.value)  # (A)
    assert reached == [], "%s: projection ran" % label  # (B) + (C): nothing was projected / returned
    assert sum(b.HITS.values()) == 0  # (D)
    assert b.fingerprint(graph) == before and b.identities(graph) == ids  # (E)


@pytest.mark.parametrize("label", sorted(PREVIEW_TAMPERS))
def test_a_tampered_preview_graph_fails_closed(label):
    fail_closed_untouched("preview", PREVIEW_TAMPERS[label], label)


@pytest.mark.parametrize("label", sorted(EXECUTION_TAMPERS))
def test_a_tampered_execution_graph_fails_closed(label):
    fail_closed_untouched("execution", EXECUTION_TAMPERS[label], label)


def test_the_tamper_catalog_is_not_vacuous_the_pristine_graphs_build():
    for kind in ("preview", "execution"):
        out = h.BUILD[kind](h.FACTORY[kind]())
        assert out.batch_size > 0


# ---- fields the contract does not read (M-04 checkpoint, M-27 path / identity / size / sha256) are not consumed:
# tampering them neither fails the build nor changes the output (contract 9.4 "not consumed")

UNREAD = {
    "effect.path": set_many(("items", 1, "execution", "completed_effects", 1), path="relative"),
    "effect.identity": set_many(("items", 1, "execution", "completed_effects", 1), identity=None),
    "effect.size": set_many(("items", 1, "execution", "completed_effects", 1), size=-5),
    "effect.sha256": set_many(("items", 1, "execution", "completed_effects", 1), sha256=None),
    "checkpoint.id": set_many(("items", 1, "retry_material", "checkpoint"), checkpoint_id="x"),
    "checkpoint.effects": set_many(("items", 1, "retry_material", "checkpoint"), completed_effects=[]),
}


@pytest.mark.parametrize("label", sorted(UNREAD))
def test_a_field_the_contract_does_not_read_cannot_influence_the_output(label):
    pristine = h.BUILD["execution"](h.execution_graph())
    graph = h.execution_graph()
    UNREAD[label](graph)
    assert h.BUILD["execution"](graph).items[1] == pristine.items[1]
