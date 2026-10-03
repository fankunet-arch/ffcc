"""P4-C9 contract sections 21.1 - 21.3 / 28.1 "resource" and 28.4: every structural limit succeeds at the limit and
fails with ``DiagnosticsResourceLimitError`` one above it -- *before* the container is iterated (placeholder
elements prove that no element was touched); the ``field_sources`` key boundary end to end; the output byte limit
(exact length succeeds, one byte less fails, encoding stops at the limit, no partial output)."""

from __future__ import annotations

import json

import pytest
from fc2_organizer.diagnostics import (
    MAX_ATTEMPTS_PER_SOURCE,
    MAX_BLOCKERS_PER_ITEM,
    MAX_CONFLICTS_PER_ITEM,
    MAX_DIAGNOSTIC_ITEMS,
    MAX_LEFTOVER_TEMPORARIES_PER_ITEM,
    MAX_SOURCES_PER_ITEM,
    DiagnosticsIntegrityError,
    DiagnosticsResourceLimitError,
    PROVENANCE_FIELD_ORDER,
    PathPolicy,
    build_preview_diagnostics,
    render,
    render_diagnostics_json,
)
from fc2_organizer.diagnostics.models import MAX_PROVENANCE_KEYS
from fc2_organizer.execution import PathRole, PreflightBlocker, PreflightBlockReason

from fc2_organizer.orchestration import IssueReason as R, PreviewState as S
from fc2_organizer.orchestration import ExecutionDisposition as D, ItemWarning as W
from fc2_organizer.execution import ExecutionStatus as X
from fc2_organizer.diagnostics import MAX_DIAGNOSTIC_OUTPUT_BYTES
from . import _builders as b

AGG = ("metadata_batch", "items", 0, "aggregation_result")


def at(root, path):
    node = root
    for step in path:
        node = node[step] if type(step) is int else getattr(node, step)
    return node


# ---- one above the limit: ResourceLimit, raised before any element is looked at


OVER = [  # (label, kind, container path, limit)
    ("preview.items", "preview", ("items",), MAX_DIAGNOSTIC_ITEMS),
    ("metadata_batch.items", "preview", ("metadata_batch", "items"), MAX_DIAGNOSTIC_ITEMS),
    ("source_results", "preview", AGG + ("source_results",), MAX_SOURCES_PER_ITEM),
    ("source_execution_traces", "preview", AGG + ("source_execution_traces",), MAX_SOURCES_PER_ITEM),
    ("contributing_source_ids", "preview", AGG + ("contributing_source_ids",), MAX_SOURCES_PER_ITEM),
    ("disabled_source_ids", "preview", AGG + ("disabled_source_ids",), MAX_SOURCES_PER_ITEM),
    ("attempts", "preview", AGG + ("source_execution_traces", 1, "attempts"), MAX_ATTEMPTS_PER_SOURCE),
    ("conflicts", "preview", AGG + ("conflicts",), MAX_CONFLICTS_PER_ITEM),
    ("alternatives", "preview", AGG + ("conflicts", 0, "alternatives"), MAX_SOURCES_PER_ITEM),
    ("blockers", "preview", ("items", 0, "preflight", "blockers"), MAX_BLOCKERS_PER_ITEM),
    ("leftover_temporaries", "execution", ("items", 1, "execution", "leftover_temporaries"),
     MAX_LEFTOVER_TEMPORARIES_PER_ITEM),
    ("execution.items", "execution", ("items",), MAX_DIAGNOSTIC_ITEMS),
]


@pytest.mark.parametrize(("label", "kind", "path", "limit"), OVER, ids=[o[0] for o in OVER])
def test_one_above_the_limit_fails_before_any_element_is_touched(label, kind, path, limit):
    graph = b.FACTORY[kind]()
    b.BUILD[kind](graph)
    parent = at(graph, path[:-1]) if len(path) > 1 else graph
    # a container of ``limit + 1`` placeholders: an element type test (Integrity) would fire first if the length
    # were not checked before the iteration
    b.poke(parent, **{path[-1]: tuple(object() for _ in range(limit + 1))})
    b.reset_hits()
    with pytest.raises(DiagnosticsResourceLimitError) as caught:
        b.BUILD[kind](graph)
    assert type(caught.value) is DiagnosticsResourceLimitError


@pytest.mark.parametrize(("label", "kind", "path", "limit"), OVER, ids=[o[0] for o in OVER])
def test_exactly_the_limit_is_not_a_resource_error(label, kind, path, limit):
    """At the limit the length gate passes; the placeholder elements then fail the *type* gate (Integrity), which
    proves the boundary is exact: ``limit`` is not ``ResourceLimit``, ``limit + 1`` is."""
    graph = b.FACTORY[kind]()
    parent = at(graph, path[:-1]) if len(path) > 1 else graph
    b.poke(parent, **{path[-1]: tuple(object() for _ in range(limit))})
    with pytest.raises(DiagnosticsIntegrityError):
        b.BUILD[kind](graph)


# ---- legal inputs exactly at the limit build and render


def blocked_graph(count):
    lineage = b.Lineage(1)
    preflight = b.fake_preflight(lineage.plans[0], ready=False)
    b.poke(preflight, blockers=tuple(PreflightBlocker(PreflightBlockReason.TARGET_DIRECTORY_EXISTS,
                                                      PathRole.TARGET_DIRECTORY) for _ in range(count)))

    return lineage.preview([lineage.preview_item(0, state=S.BLOCKED, reason=R.PREFLIGHT_BLOCKED,
                                                 preflight=preflight)])


def test_256_blockers_build_and_render_and_257_fail():
    diagnostics = build_preview_diagnostics(blocked_graph(MAX_BLOCKERS_PER_ITEM))
    assert len(diagnostics.items[0].preflight.blockers) == 256
    assert len(json.loads(render_diagnostics_json(diagnostics))["items"][0]["preflight"]["blockers"]) == 256
    with pytest.raises(DiagnosticsResourceLimitError):
        build_preview_diagnostics(blocked_graph(MAX_BLOCKERS_PER_ITEM + 1))


def test_256_leftover_temporaries_build_and_257_fail():

    for count, ok in ((MAX_LEFTOVER_TEMPORARIES_PER_ITEM, True), (MAX_LEFTOVER_TEMPORARIES_PER_ITEM + 1, False)):
        lineage = b.Lineage(1)
        execution = b.rich_execution(lineage.plans[0], X.PARTIAL, leftovers=count)
        item = lineage.execution_item(0, D.EXECUTED, execution=execution, warnings=(W.LEFTOVER_TEMPORARIES,),
                                      material=True)
        result = lineage.result([item])
        if ok:
            out = b.build_execution_diagnostics(result, path_policy=PathPolicy.BASENAME)
            assert out.items[0].execution.leftover_temporary_count == 256
            render_diagnostics_json(out)
        else:
            with pytest.raises(DiagnosticsResourceLimitError):
                b.build_execution_diagnostics(result)


# ---- field_sources key boundary (end to end through build and render)


SRC = ("src_a",)


def keyed_preview(keys):
    metadata = b.NormalizedMetadata(number=b.NUMBER, title="T", field_sources=keys)
    aggregation = b.make_aggregation([b.make_source_result("src_a")], metadata=metadata)
    return b.preview_of_metadata(b.batch_item_for(aggregation))


def test_exactly_64_keys_build_and_render_but_65_fail_and_ten_times_the_limit_fails():
    keys = {name: SRC for name in PROVENANCE_FIELD_ORDER if name in ("number", "title")}
    keys.update({"unknown_%d" % i: SRC for i in range(MAX_PROVENANCE_KEYS - len(keys))})
    assert len(keys) == MAX_PROVENANCE_KEYS == 64
    out = render_diagnostics_json(build_preview_diagnostics(keyed_preview(keys)))
    assert [p["field"] for p in json.loads(out)["items"][0]["metadata"]["field_provenance"]] == ["number", "title"]
    for count in (65, 10 * MAX_PROVENANCE_KEYS):
        many = {"k%d" % i: SRC for i in range(count)}
        with pytest.raises(DiagnosticsResourceLimitError):
            build_preview_diagnostics(keyed_preview(many))


def test_the_65th_key_stops_the_scan_so_a_hostile_key_after_it_is_never_read():
    keys = {"k%d" % i: SRC for i in range(MAX_PROVENANCE_KEYS)}
    keys[b.EvilStr("beyond")] = SRC  # the 65th key
    keys["after"] = SRC
    preview = keyed_preview(keys)
    b.reset_hits()
    with pytest.raises(DiagnosticsResourceLimitError):
        build_preview_diagnostics(preview)
    assert b.total_hits() == 0


# ---- the output byte limit


def sized():
    diagnostics = b.build_preview_diagnostics(b.preview_graph())
    return diagnostics, len(render_diagnostics_json(diagnostics))


def test_the_limit_equal_to_the_output_length_succeeds_and_one_less_fails(monkeypatch):
    diagnostics, length = sized()
    monkeypatch.setattr(render, "MAX_DIAGNOSTIC_OUTPUT_BYTES", length)
    assert len(render_diagnostics_json(diagnostics)) == length
    monkeypatch.setattr(render, "MAX_DIAGNOSTIC_OUTPUT_BYTES", length - 1)
    with pytest.raises(DiagnosticsResourceLimitError) as caught:
        render_diagnostics_json(diagnostics)
    assert type(caught.value) is DiagnosticsResourceLimitError


def test_encoding_stops_after_the_limit_and_returns_no_partial_output(monkeypatch):
    diagnostics, length = sized()
    chunks = []
    real = render.json.JSONEncoder

    class Counting:
        def __init__(self, **kwargs):
            self.inner = real(**kwargs)

        def iterencode(self, tree):
            for chunk in self.inner.iterencode(tree):
                chunks.append(chunk)
                yield chunk

    class Json:
        JSONEncoder = Counting

    monkeypatch.setattr(render, "json", Json)
    total_chunks = len(list(real(sort_keys=True, separators=(",", ":")).iterencode(render.batch_tree(diagnostics))))
    monkeypatch.setattr(render, "MAX_DIAGNOSTIC_OUTPUT_BYTES", 100)
    with pytest.raises(DiagnosticsResourceLimitError):
        render_diagnostics_json(diagnostics)
    assert 0 < len(chunks) < total_chunks  # the generator was abandoned shortly after the limit
    assert sum(len(c) for c in chunks[:-1]) <= 100 < sum(len(c) for c in chunks)


def test_the_real_limit_is_64_mib_and_a_normal_batch_is_far_below_it():

    assert MAX_DIAGNOSTIC_OUTPUT_BYTES == 64 * 1024 * 1024
    assert sized()[1] < MAX_DIAGNOSTIC_OUTPUT_BYTES // 1000
