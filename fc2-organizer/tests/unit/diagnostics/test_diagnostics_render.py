"""P4-C9 contract sections 17.3 / 21.3 / 22 / 24.4 / 9.12 N-15: ``render_diagnostics_json`` -- frozen JSON shape,
absence as ``null``, enum values, count pairs, the detail-type table, ``sort_keys`` / ASCII / no trailing newline,
the local re-check of a tampered diagnostics graph, the whitelist of every text, the typed encoding failures
(including the int-to-text digit limit) raised outside the ``except`` block, and "bytes only"."""

from __future__ import annotations

import json
import sys

import pytest
from fc2_organizer.diagnostics import (
    DIAGNOSTICS_SCHEMA,
    DIAGNOSTICS_SCHEMA_VERSION,
    DiagnosticsError,
    DiagnosticsInputError,
    DiagnosticsIntegrityError,
    DiagnosticsSerializationError,
    DiagnosticsUnsafeValueError,
    PathPolicy,
    TimingPolicy,
    render,
    render_diagnostics_json,
)

from fc2_organizer.orchestration import RetryKind as K
from fc2_organizer.diagnostics import BatchDiagnostics
from . import _builders as b


def rendered(kind, **kwargs):
    return render_diagnostics_json(b.BUILD[kind](b.FACTORY[kind](), **kwargs))


def parsed(kind, **kwargs):
    return json.loads(rendered(kind, **kwargs))


TOP_KEYS = {"schema", "schema_version", "kind", "shape", "generation", "batch_size", "retry_scope", "path_policy",
            "timing_policy", "metadata_batch", "preview_summary", "execution_summary", "outcome", "items"}
ITEM_KEYS = {"index", "generation", "canonical_number", "source_name", "source_size", "target_directory_name",
             "target_media_name", "preview_state", "issue", "warnings", "conflict_with", "retry_origin",
             "disposition", "retry_kind", "retry_material_retained", "metadata", "image_failures", "preflight",
             "execution"}
METADATA_KEYS = {"status", "generation", "error_kind", "aggregate_status", "traces_available", "sources",
                 "disabled_source_ids", "field_provenance", "conflicts", "elapsed_ms"}
SOURCE_KEYS = {"source_id", "status", "error_kind", "contributed", "operational_failure", "provided_fields",
               "trace_available", "attempt_count", "max_attempts", "deadline_exceeded", "deadline_during", "attempts"}
ATTEMPT_KEYS = {"sequence", "status", "error_kind", "completed", "elapsed_ms", "backoff_before_ms"}
PREFLIGHT_KEYS = {"mode", "ready", "transfer_mode", "blockers", "pending_unit_count", "completed_unit_count",
                  "skipped_steps", "artifact_counts"}
EXECUTION_KEYS = {"status", "mode", "transfer_mode", "new_effect_count", "effect_counts", "artifact_counts",
                  "failure", "checkpoint_present", "skipped_steps", "leftover_temporary_count",
                  "leftover_temporaries"}
FAILURE_KEYS = {"step", "kind", "stage", "write_stage", "errno", "artifact_kind", "ordinal", "target_published"}
ISSUE_KEYS = {"stage", "reason", "error_type", "detail_type", "detail"}
PREVIEW_SUMMARY_KEYS = {"total", "ready", "blocked", "unprepared", "warned", "stage_counts"}
EXECUTION_SUMMARY_KEYS = {"total", "ready", "blocked", "unprepared", "executed", "success", "partial", "failed",
                          "not_selected", "cancelled", "rejected", "aborted", "retryable", "deferred",
                          "non_retryable", "stage_counts"}


# ---- shape


@pytest.mark.parametrize("kind", ["preview", "execution"])
def test_the_top_level_object_has_the_frozen_key_set_and_schema_constants(kind):
    tree = parsed(kind)
    assert set(tree) == TOP_KEYS
    assert tree["schema"] == DIAGNOSTICS_SCHEMA == "fc2_organizer.diagnostics"
    assert tree["schema_version"] == DIAGNOSTICS_SCHEMA_VERSION == "1.0"
    assert tree["kind"] == kind and tree["shape"] == "main" and tree["path_policy"] == "none"
    assert tree["timing_policy"] == "omit"
    assert set(tree["metadata_batch"]) == {"generation", "total", "success", "partial", "failed"}


def test_preview_and_execution_outputs_carry_exactly_one_summary_each():
    preview, execution = parsed("preview"), parsed("execution")
    assert set(preview["preview_summary"]) == PREVIEW_SUMMARY_KEYS and preview["execution_summary"] is None
    assert preview["outcome"] is None
    assert set(execution["execution_summary"]) == EXECUTION_SUMMARY_KEYS and execution["preview_summary"] is None
    assert execution["outcome"] in {"success", "partial", "failed"}
    for tree in (preview, execution):
        summary = tree["preview_summary"] or tree["execution_summary"]
        assert [pair["stage"] for pair in summary["stage_counts"]] == [
            "number_recognition", "batch_conflict", "metadata", "planning", "publication", "nfo_render",
            "image_acquisition", "manifest", "preflight", "execution"]
        assert all(set(pair) == {"stage", "count"} for pair in summary["stage_counts"])


@pytest.mark.parametrize("kind", ["preview", "execution"])
def test_every_item_has_the_constant_key_set_and_nested_key_sets(kind):
    tree = parsed(kind, path_policy=PathPolicy.BASENAME, timing_policy=TimingPolicy.INCLUDE)
    seen = {"metadata": 0, "source": 0, "attempt": 0, "preflight": 0, "execution": 0, "failure": 0, "issue": 0}
    for item in tree["items"]:
        assert set(item) == ITEM_KEYS
        if item["metadata"] is not None:
            seen["metadata"] += 1
            assert set(item["metadata"]) == METADATA_KEYS
            for source in item["metadata"]["sources"]:
                seen["source"] += 1
                assert set(source) == SOURCE_KEYS
                for attempt in source["attempts"]:
                    seen["attempt"] += 1
                    assert set(attempt) == ATTEMPT_KEYS
        if item["preflight"] is not None:
            seen["preflight"] += 1
            assert set(item["preflight"]) == PREFLIGHT_KEYS
            assert [p["artifact_kind"] for p in item["preflight"]["artifact_counts"]] == [
                "nfo", "poster", "fanart", "thumb", "extrafanart"]
        if item["execution"] is not None:
            seen["execution"] += 1
            assert set(item["execution"]) == EXECUTION_KEYS
            assert all(set(p) == {"effect_kind", "count"} for p in item["execution"]["effect_counts"])
            if item["execution"]["failure"] is not None:
                seen["failure"] += 1
                assert set(item["execution"]["failure"]) == FAILURE_KEYS
        if item["issue"] is not None:
            seen["issue"] += 1
            assert set(item["issue"]) == ISSUE_KEYS
    assert seen["metadata"] and (kind == "execution" or seen["source"] and seen["attempt"] and seen["preflight"])
    if kind == "execution":
        assert seen["execution"] and seen["failure"] and seen["issue"]


def test_absence_is_null_never_a_missing_key():
    tree = parsed("execution")
    rejected = tree["items"][5]
    assert rejected["preflight"] is None and rejected["execution"] is None
    assert rejected["source_name"] is None and rejected["retry_origin"] is None and set(rejected) == ITEM_KEYS
    assert tree["items"][0]["issue"] is None


def test_enum_members_are_output_by_value_and_counts_as_named_pairs():
    tree = parsed("execution")
    item = tree["items"][1]
    assert item["disposition"] == "executed" and item["retry_kind"] == "resume"
    assert item["execution"]["status"] == "partial" and item["execution"]["failure"]["step"] == "move_media"
    assert item["execution"]["failure"]["errno"] == 13
    assert {"effect_kind": "media_published", "count": 1} in item["execution"]["effect_counts"]
    assert {"artifact_kind": "extrafanart", "count": 2} in item["execution"]["artifact_counts"]
    assert item["warnings"] == ["leftover_temporaries"]


def test_the_issue_detail_is_output_as_a_frozen_type_name_and_a_value():
    tree = parsed("execution")
    failed = tree["items"][2]["issue"]
    assert failed == {"stage": "execution", "reason": "execution_failed", "error_type": None,
                      "detail_type": "ExecutionFailureKind", "detail": "media_transfer_failed"}
    rejected = tree["items"][5]["issue"]
    assert rejected["detail_type"] is None and rejected["detail"] is None and rejected["error_type"] == "E"


def test_a_retry_scope_is_a_list_of_values_in_declaration_order_else_null():
    lineage = b.Lineage(2)

    items = [lineage.preview_item(1, generation=1, retry_origin=K.RESUME)]
    preview = lineage.preview(items, generation=1, base_result_id=b.new_id(),
                              retry_scope=frozenset({K.RESUME, K.DEFERRED, K.METADATA_REFETCH}), retry_budget=10**6)
    tree = json.loads(render_diagnostics_json(b.build_preview_diagnostics(preview)))
    assert tree["retry_scope"] == ["metadata_refetch", "resume", "deferred"] and tree["shape"] == "retry"
    assert parsed("preview")["retry_scope"] is None


# ---- encoding


@pytest.mark.parametrize("kind", ["preview", "execution"])
def test_the_output_is_compact_sorted_ascii_bytes_without_a_trailing_newline(kind):
    data = rendered(kind, path_policy=PathPolicy.BASENAME, timing_policy=TimingPolicy.INCLUDE)
    assert type(data) is bytes and data.isascii() and not data.endswith(b"\n") and not data.startswith(b"\xef\xbb")
    text = data.decode("ascii")
    assert ": " not in text and ", " not in text and "\n" not in text
    tree = json.loads(text)
    assert text == json.dumps(tree, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def test_non_ascii_text_is_escaped():
    graph = b.preview_graph()
    item = graph.items[0]
    name = "映画.mp4"
    old = item.media_item.source_path
    new = old.rsplit("/", 1)[0] + "/" + name
    b.poke(item.media_item, source_path=new)
    b.poke(item.plan, source_path=new)
    for path in (item.plan.operations[1].source, ):
        b.poke(path, absolute_path=new)
    data = render_diagnostics_json(b.build_preview_diagnostics(graph, path_policy=PathPolicy.BASENAME))
    assert data.isascii() and b"\\u6620\\u753b.mp4" in data
    assert json.loads(data)["items"][0]["source_name"] == name


def test_the_output_is_a_pure_function_of_the_diagnostics():
    diagnostics = b.build_preview_diagnostics(b.preview_graph())
    assert render_diagnostics_json(diagnostics) == render_diagnostics_json(diagnostics)


# ---- argument and graph checks (24.4 steps 1 and 2)


@pytest.mark.parametrize("bad", [None, 1, "x", {}, b"{}", object(), b.preview_graph()])
def test_the_argument_must_be_an_exact_batch_diagnostics(bad):
    with pytest.raises(DiagnosticsInputError):
        render_diagnostics_json(bad)


def test_a_subclass_of_batch_diagnostics_is_rejected():

    sub = type("Sub", (BatchDiagnostics,), {})
    with pytest.raises(DiagnosticsInputError):
        render_diagnostics_json(b.poke_subclass(sub, b.make_preview_diagnostics()))


TAMPERS = {
    "kind_str": lambda d: b.poke(d, kind="preview"),
    "generation_negative": lambda d: b.poke(d, generation=-1),
    "items_list": lambda d: b.poke(d, items=list(d.items)),
    "item_wrong_type": lambda d: b.poke(d, items=(object(),) + d.items[1:]),
    "summary_total": lambda d: b.poke(d.preview_summary or d.execution_summary, total=99),
    "item_index": lambda d: b.poke(d.items[1], index=5),
    "item_state_str": lambda d: b.poke(d.items[0], preview_state="ready"),
    "metadata_status_str": lambda d: b.poke(d.items[0].metadata, status="x"),
    "source_id_unsafe": lambda d: b.poke(d.items[0].metadata.sources[0], source_id="bad id"),
    "name_under_none": lambda d: b.poke(d.items[0], source_name="x.mp4"),
}


@pytest.mark.parametrize("label", sorted(TAMPERS))
def test_a_tampered_diagnostics_graph_fails_the_local_recheck(label):
    diagnostics = b.build_preview_diagnostics(b.preview_graph())
    TAMPERS[label](diagnostics)
    with pytest.raises(DiagnosticsIntegrityError) as caught:
        render_diagnostics_json(diagnostics)
    assert type(caught.value) is DiagnosticsIntegrityError


def test_a_tampered_carried_upstream_value_is_rechecked():
    diagnostics = b.build_execution_diagnostics(b.execution_graph())
    failing = next(i for i in diagnostics.items if i.execution is not None and i.execution.failure is not None)
    b.poke(failing.execution.failure, errno=True)
    with pytest.raises(DiagnosticsIntegrityError):
        render_diagnostics_json(diagnostics)
    other = b.build_execution_diagnostics(b.execution_graph())
    b.poke(other, outcome="success")
    with pytest.raises(DiagnosticsIntegrityError):
        render_diagnostics_json(other)


# ---- 17.2 whitelist (defence in depth: reached when the graph re-check is bypassed)


@pytest.mark.parametrize("label", ["source_id", "error_type", "canonical_number", "deadline", "basename",
                                   "leftover", "write_stage", "field"])
def test_a_text_outside_the_whitelist_is_an_unsafe_value_error(monkeypatch, label):
    monkeypatch.setattr(render, "batch_problem", lambda value: None)  # isolate the tree-conversion whitelist
    diagnostics = b.build_execution_diagnostics(b.execution_graph(), path_policy=PathPolicy.BASENAME)
    item = next(i for i in diagnostics.items if i.execution is not None and i.execution.leftover_temporaries)
    failing = next(i for i in diagnostics.items if i.execution is not None and i.execution.failure is not None)
    rejected = next(i for i in diagnostics.items if i.issue is not None and i.issue.error_type is not None)
    previewed = b.build_preview_diagnostics(b.preview_graph())
    target = {
        "source_id": lambda: (previewed, b.poke(previewed.items[0].metadata.sources[0], source_id="bad id")),
        "error_type": lambda: (diagnostics, b.poke(rejected.issue, error_type="not an identifier")),
        "canonical_number": lambda: (diagnostics, b.poke(item, canonical_number="nope")),
        "deadline": lambda: (previewed, b.poke(previewed.items[0].metadata.sources[0], deadline_during="never")),
        "basename": lambda: (diagnostics, b.poke(item, source_name="a\x00b")),
        "leftover": lambda: (diagnostics, b.poke(item.execution.leftover_temporaries[0], name="x.part")),
        "write_stage": lambda: (diagnostics, b.poke(failing.execution.failure, write_stage="later")),
        "field": lambda: (previewed, b.poke(previewed.items[0].metadata.field_provenance[0], field="zzz")),
    }[label]
    graph, _ = target()
    with pytest.raises(DiagnosticsUnsafeValueError) as caught:
        render_diagnostics_json(graph)
    assert type(caught.value) is DiagnosticsUnsafeValueError


def test_the_tampered_text_is_never_echoed_in_the_error_message(monkeypatch):
    monkeypatch.setattr(render, "batch_problem", lambda value: None)
    diagnostics = b.build_preview_diagnostics(b.preview_graph())
    b.poke(diagnostics.items[0].metadata.sources[0], source_id="C9CANARY secret")
    with pytest.raises(DiagnosticsUnsafeValueError) as caught:
        render_diagnostics_json(diagnostics)
    assert "C9CANARY" not in str(caught.value) and caught.value.__cause__ is None


# ---- encoding failures (24.4 step 4) and N-15


class FakeJson:
    def __init__(self, error):
        self.error = error

    def JSONEncoder(self, **kwargs):  # noqa: N802 -- mirrors json.JSONEncoder
        error = self.error

        class Encoder:
            def iterencode(self, tree):
                raise error
                yield  # pragma: no cover

        return Encoder()


@pytest.mark.parametrize("error", [ValueError("x"), TypeError("x"), RecursionError("x"), OverflowError("x")])
def test_the_four_encoding_exceptions_become_a_serialization_error_without_chaining(monkeypatch, error):
    monkeypatch.setattr(render, "json", FakeJson(error))
    with pytest.raises(DiagnosticsSerializationError) as caught:
        render_diagnostics_json(b.build_preview_diagnostics(b.preview_graph()))
    assert type(caught.value) is DiagnosticsSerializationError
    assert caught.value.__cause__ is None and caught.value.__context__ is None and caught.value.__suppress_context__ is False


def test_any_other_exception_is_not_swallowed(monkeypatch):
    monkeypatch.setattr(render, "json", FakeJson(KeyError("x")))
    with pytest.raises(KeyError):
        render_diagnostics_json(b.build_preview_diagnostics(b.preview_graph()))


def huge_size_graph(size):
    graph = b.preview_graph()
    b.poke(graph.items[0].media_item, size=size)
    b.poke(graph.items[0].plan, source_size=size)
    return graph


def test_n15_a_huge_legal_int_builds_but_rendering_raises_the_typed_serialization_error():
    old = sys.get_int_max_str_digits()
    huge = 10**1000
    try:
        sys.set_int_max_str_digits(640)
        diagnostics = b.build_preview_diagnostics(huge_size_graph(huge))  # the builder never converts an int to text
        assert diagnostics.items[0].source_size == huge
        with pytest.raises(DiagnosticsSerializationError) as caught:
            render_diagnostics_json(diagnostics)
        assert type(caught.value) is DiagnosticsSerializationError
        assert type(caught.value) not in (OverflowError, ValueError, TypeError)
        assert caught.value.__cause__ is None and caught.value.__context__ is None
    finally:
        sys.set_int_max_str_digits(old)
    assert b"1" + b"0" * 1000 in render_diagnostics_json(diagnostics)  # under the default limit it renders


def test_a_legal_int_below_the_digit_limit_renders_unchanged():
    out = render_diagnostics_json(b.build_preview_diagnostics(huge_size_graph(10**300)))
    assert b"1" + b"0" * 300 in out


# ---- bytes only


def test_the_renderer_only_returns_bytes_and_touches_nothing(tmp_path, monkeypatch):
    import builtins
    import os

    monkeypatch.chdir(tmp_path)
    diagnostics = b.build_preview_diagnostics(b.preview_graph())
    with monkeypatch.context() as patch:
        patch.setattr(builtins, "open", lambda *a, **k: (_ for _ in ()).throw(AssertionError("open")))
        for name in ("mkdir", "rename", "replace", "unlink", "remove", "rmdir", "stat", "scandir", "listdir"):
            patch.setattr(os, name, lambda *a, **k: (_ for _ in ()).throw(AssertionError("fs")))
        data = render_diagnostics_json(diagnostics)
    assert type(data) is bytes and list(tmp_path.iterdir()) == []


def test_the_rendered_output_contains_no_tuple_enum_or_non_json_type():
    def check(node):
        assert type(node) in (dict, list, str, int, bool, type(None))
        if type(node) is dict:
            assert all(type(k) is str for k in node)
            for value in node.values():
                check(value)
        elif type(node) is list:
            for value in node:
                check(value)

    for kind in ("preview", "execution"):
        check(parsed(kind, path_policy=PathPolicy.BASENAME, timing_policy=TimingPolicy.INCLUDE))
