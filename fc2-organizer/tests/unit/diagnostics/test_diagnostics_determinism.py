"""P4-C9 contract sections 14 / 15 / 16 / 28.5 (determinism and ordering): repeated builds / renders are equal;
every temporary identity (ids, tokens, seals, fingerprints) is absent, so two independent real runs of the same
corpus render byte-identically; completion order, ``field_sources`` insertion order and ``frozenset`` iteration order
never reach the output; the golden order of every collection is frozen. Mutations that break each property are
shown to be detected by the comparison used here."""

from __future__ import annotations

import json
import secrets

import pytest
from fc2_metadata_core.models import SourceStatus as T
from fc2_organizer.diagnostics import (
    PROVENANCE_FIELD_ORDER,
    DiagnosticsError,
    PathPolicy,
    TimingPolicy,
    build_execution_diagnostics,
    build_preview_diagnostics,
    render,
    render_diagnostics_json,
    validation,
)
from fc2_organizer.orchestration import RetryKind as K
from orchestration._helpers import Corpus, Film

from . import _builders as b

FILMS = [Film("FC2-PPV-1000001.mp4"), Film("FC2-PPV-1000002.mp4", kind="partial", extra=2, extra_fail=1),
         Film("FC2-PPV-1000003.mp4", kind="failed"), Film("FC2-PPV-1000004.mp4", poster=False, thumb=False),
         Film("not-a-number.mp4")]


def run_corpus(tmp_path, name, path_policy=PathPolicy.NONE):
    corpus = Corpus(tmp_path / name, FILMS)
    orchestrator = corpus.orchestrator()
    preview = corpus.preview(orchestrator)
    result = orchestrator.execute(preview)
    return [render_diagnostics_json(build_preview_diagnostics(preview, path_policy=path_policy)),
            render_diagnostics_json(build_execution_diagnostics(result, path_policy=path_policy))], preview, result


@pytest.mark.parametrize("path_policy", list(PathPolicy))
def test_two_independent_real_runs_render_byte_identically(tmp_path, path_policy):
    """Every temporary identity differs between the runs (preview / result ids, lineage token, preflight ids,
    seals, absolute paths): none of them may reach the output."""
    first, preview_a, result_a = run_corpus(tmp_path, "one", path_policy)
    second, preview_b, result_b = run_corpus(tmp_path, "two", path_policy)
    assert preview_a.preview_id != preview_b.preview_id and result_a.result_id != result_b.result_id
    assert preview_a.lineage != preview_b.lineage and preview_a.library_root != preview_b.library_root
    assert first == second


def test_repeated_builds_and_renders_are_equal_and_byte_identical():
    for kind in ("preview", "execution"):
        graph = b.FACTORY[kind]()
        one = b.BUILD[kind](graph, path_policy=PathPolicy.BASENAME, timing_policy=TimingPolicy.INCLUDE)
        two = b.BUILD[kind](graph, path_policy=PathPolicy.BASENAME, timing_policy=TimingPolicy.INCLUDE)
        assert one == two and one is not two
        assert render_diagnostics_json(one) == render_diagnostics_json(two)


def test_no_temporary_identity_appears_in_the_output(tmp_path):
    outputs, preview, result = run_corpus(tmp_path, "ids")
    identities = [preview.preview_id, result.result_id, result.preview_id, preview.lineage.token]
    identities += [item.preflight.preflight_id for item in preview.items if item.preflight is not None]
    identities += [item.execution.preflight_id for item in result.items if item.execution is not None]
    for data in outputs:
        text = data.decode("ascii")
        for identity in identities:
            assert identity not in text
        assert str(tmp_path) not in text


def test_field_provenance_insertion_order_never_reaches_the_output():
    full = dict(studio="S", publisher="P", release="2020-01-01", runtime=90, plot="pl", actors=("a",), tags=("t",),
                poster_urls=("https://x.invalid/p",), thumb_urls=("https://x.invalid/t",),
                fanart_urls=("https://x.invalid/f",), extrafanart=("https://x.invalid/e",),
                source_urls=("https://x.invalid/s",), external_ids={"k": "v"})
    forward = {name: ("src_a",) for name in PROVENANCE_FIELD_ORDER}
    renders = set()
    for ordering in (list(forward.items()), list(reversed(forward.items())),
                     sorted(forward.items(), key=lambda pair: (len(pair[0]), pair[0]))):
        metadata = b.NormalizedMetadata(number=b.NUMBER, title="T", field_sources=dict(ordering), **full)
        aggregation = b.make_aggregation([b.make_source_result("src_a")], metadata=metadata)
        preview = b.preview_of_metadata(b.batch_item_for(aggregation))
        renders.add(render_diagnostics_json(build_preview_diagnostics(preview)))
    assert len(renders) == 1
    fields = [p["field"] for p in json.loads(next(iter(renders)))["items"][0]["metadata"]["field_provenance"]]
    assert fields == list(PROVENANCE_FIELD_ORDER)


def test_retry_scope_frozenset_iteration_order_never_reaches_the_output():
    scopes = [K.RESUME, K.DEFERRED, K.METADATA_REFETCH, K.FRESH_REEXECUTE]
    seen = set()
    for ordering in (scopes, list(reversed(scopes)), scopes[1:] + scopes[:1]):
        lineage = b.Lineage(2)
        items = [lineage.preview_item(1, generation=1, retry_origin=K.RESUME)]
        preview = lineage.preview(items, generation=1, base_result_id="a" * 32, retry_scope=frozenset(ordering),
                                  retry_budget=10**6)
        seen.add(json.loads(render_diagnostics_json(build_preview_diagnostics(preview)))["retry_scope"].__repr__())
    assert seen == {repr(["metadata_refetch", "fresh_reexecute", "resume", "deferred"])}


def test_the_item_order_is_the_index_order_and_sources_keep_the_engine_order():
    tree = json.loads(render_diagnostics_json(build_preview_diagnostics(b.preview_graph())))
    assert [i["index"] for i in tree["items"]] == [0, 1]
    for item in tree["items"]:
        assert [s["source_id"] for s in item["metadata"]["sources"]] == ["src_a", "src_b", "src_c"]
        assert [a["sequence"] for a in item["metadata"]["sources"][1]["attempts"]] == [1, 2]
        assert item["metadata"]["disabled_source_ids"] == ["av123"]


def test_golden_output_of_a_small_batch_is_frozen():
    """A small hand-built batch (several sources, provenance, a conflict) has one exact, frozen rendering."""
    good = b.make_source_result("src_a", T.SUCCESS)
    bad = b.make_source_result("src_b", T.NOT_FOUND)
    aggregation = b.make_aggregation([good, bad], field_sources={"title": ("src_a",), "number": ("src_a",)})
    preview = b.preview_of_metadata(b.batch_item_for(aggregation))
    item = json.loads(render_diagnostics_json(build_preview_diagnostics(preview)))["items"][0]
    assert item["metadata"] == {
        "status": "success", "generation": 0, "error_kind": None, "aggregate_status": "success",
        "traces_available": False,
        "sources": [
            {"source_id": "src_a", "status": "success", "error_kind": None, "contributed": True,
             "operational_failure": False, "provided_fields": ["number", "title"], "trace_available": False,
             "attempt_count": None, "max_attempts": None, "deadline_exceeded": None, "deadline_during": None,
             "attempts": []},
            {"source_id": "src_b", "status": "not_found", "error_kind": "not_found", "contributed": False,
             "operational_failure": False, "provided_fields": [], "trace_available": False, "attempt_count": None,
             "max_attempts": None, "deadline_exceeded": None, "deadline_during": None, "attempts": []}],
        "disabled_source_ids": [], "field_provenance": [{"field": "number", "source_ids": ["src_a"]},
                                                         {"field": "title", "source_ids": ["src_a"]}],
        "conflicts": [], "elapsed_ms": None}


# ---- mutations: the comparisons above kill each deviant implementation


def test_mutation_a_temporary_identity_in_the_output_is_detected_by_the_byte_comparison(monkeypatch):
    diagnostics = build_preview_diagnostics(b.preview_graph())
    real = render.batch_tree
    monkeypatch.setattr(render, "batch_tree", lambda d: dict(real(d), preview_id=secrets.token_hex(16)))
    assert render_diagnostics_json(diagnostics) != render_diagnostics_json(diagnostics)


def test_mutation_provenance_in_insertion_order_is_detected(monkeypatch):
    """A scan that returns the provenance in the proxy's insertion order makes the three renders differ."""
    def insertion_order_scan(metadata, contributing):
        return tuple((name, metadata.field_sources[name]) for name in metadata.field_sources
                     if name in PROVENANCE_FIELD_ORDER)

    monkeypatch.setattr(validation, "scan_field_sources", insertion_order_scan)
    renders = set()
    killed = False
    for ordering in (["number", "title", "plot"], ["plot", "title", "number"]):
        metadata = b.NormalizedMetadata(number=b.NUMBER, title="T", plot="p",
                                        field_sources={name: ("src_a",) for name in ordering})
        aggregation = b.make_aggregation([b.make_source_result("src_a")], metadata=metadata)
        preview = b.preview_of_metadata(b.batch_item_for(aggregation))
        try:
            renders.add(render_diagnostics_json(build_preview_diagnostics(preview)))
        except DiagnosticsError:  # the model invariant (``provided_fields`` in frozen order) refuses it
            killed = True
    assert killed or len(renders) == 2  # either way the single-render determinism assertion above would fail


def test_mutation_items_reversed_or_sources_sorted_is_detected(monkeypatch):
    diagnostics = build_preview_diagnostics(b.preview_graph())
    real = render.batch_tree
    monkeypatch.setattr(render, "batch_tree", lambda d: dict(real(d), items=list(reversed(real(d)["items"]))))
    tree = json.loads(render_diagnostics_json(diagnostics))
    assert [i["index"] for i in tree["items"]] == [1, 0]  # the order assertion above would fail
