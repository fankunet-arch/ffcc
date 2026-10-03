"""P4-C9 contract section 28.4: the 500-logical-item diagnostics gate (public constructors, mixed distribution of
every disposition / status / RetryKind / issue class, no real file system) and the ``MAX_BATCH_ITEMS`` boundary:
item order, summary mapping equal to P4-C8, determinism (equal builds, byte-identical renders, identities replaced),
resource bound, redaction canaries, JSON parseable with the section 22 structure, local validation of everything
the real producers made; 2000 items build and render; 2001 fail before any per-item work; 2000 items x 64 provenance
keys still succeed."""

from __future__ import annotations

import json
import time

import pytest
from fc2_organizer.diagnostics import (
    MAX_DIAGNOSTIC_ITEMS,
    MAX_DIAGNOSTIC_OUTPUT_BYTES,
    DiagnosticsResourceLimitError,
    PathPolicy,
    TimingPolicy,
    build_execution_diagnostics,
    build_preview_diagnostics,
    render_diagnostics_json,
)
from fc2_organizer.diagnostics.models import MAX_PROVENANCE_KEYS, PROVENANCE_FIELD_ORDER
from fc2_organizer.execution import ExecutionStatus as X
from fc2_organizer.orchestration import (
    ExecutionDisposition as D,
    IssueReason as R,
    ItemWarning as W,
    PreviewState as S,
)

from . import _builders as b


def execution_items(lineage, count):
    """A mixed distribution: every disposition / status / RetryKind / issue class, repeated across ``count`` items."""
    items = []
    for index in range(count):
        plan = lineage.plans[index]
        slot = index % 8
        if slot == 0:
            items.append(lineage.execution_item(index, D.EXECUTED, execution=b.rich_execution(plan, X.SUCCESS)))
        elif slot == 1:
            items.append(lineage.execution_item(index, D.EXECUTED, execution=b.rich_execution(plan, X.PARTIAL,
                                                                                               leftovers=1),
                                                warnings=(W.LEFTOVER_TEMPORARIES,), material=True))
        elif slot == 2:
            items.append(lineage.execution_item(index, D.EXECUTED, execution=b.rich_execution(plan, X.FAILED),
                                                material=True))
        elif slot == 3:
            items.append(lineage.execution_item(index, D.NOT_SELECTED, material=True))
        elif slot == 4:
            items.append(lineage.execution_item(index, D.CANCELLED, material=True))
        elif slot == 5:
            items.append(lineage.execution_item(index, D.REJECTED, reason=R.EXECUTION_REJECTED,
                                                issue_kwargs={"error_type": "E"}))
        elif slot == 6:
            items.append(lineage.execution_item(index, D.ABORTED, reason=R.EXECUTION_ABORTED,
                                                issue_kwargs={"error_type": "E"}))
        else:
            items.append(lineage.execution_item(index, D.NOT_READY, state=S.BLOCKED, reason=R.PREFLIGHT_BLOCKED,
                                                material=True, execution=None))
    return items


def execution_result(count):
    lineage = b.Lineage(count)
    return lineage.result(execution_items(lineage, count))


def preview_batch(count):
    lineage = b.Lineage(count)
    items = []
    for index in range(count):
        if index % 5 == 4:
            plan = lineage.plans[index]
            items.append(lineage.preview_item(index, state=S.BLOCKED, reason=R.PREFLIGHT_BLOCKED,
                                              preflight=b.fake_preflight(plan, ready=False)))
        else:
            items.append(lineage.preview_item(index))
    return lineage.preview(items)


@pytest.fixture(scope="module")
def preview500():
    return preview_batch(500)


@pytest.fixture(scope="module")
def result500():
    return execution_result(500)


def test_500_logical_items_preview_order_summary_json_and_resources(preview500):
    start = time.perf_counter()
    diagnostics = build_preview_diagnostics(preview500, path_policy=PathPolicy.BASENAME)
    data = render_diagnostics_json(diagnostics)
    assert time.perf_counter() - start < 30
    assert [i.index for i in diagnostics.items] == list(range(500))
    assert diagnostics.preview_summary == preview500.summary
    tree = json.loads(data)
    assert tree["batch_size"] == 500 and len(tree["items"]) == 500 and tree["kind"] == "preview"
    assert [i["index"] for i in tree["items"]] == list(range(500))
    assert sum(1 for i in tree["items"] if i["preview_state"] == "blocked") == 100
    assert len(data) < MAX_DIAGNOSTIC_OUTPUT_BYTES // 10


def test_500_logical_items_execution_distribution_summary_and_retry_kinds(result500):
    diagnostics = build_execution_diagnostics(result500)
    assert diagnostics.execution_summary == result500.summary and diagnostics.outcome is result500.outcome
    assert [i.retry_kind for i in diagnostics.items] == [item.retry_kind for item in result500.items]
    assert [i.disposition for i in diagnostics.items] == [item.disposition for item in result500.items]
    tree = json.loads(render_diagnostics_json(diagnostics))
    assert len(tree["items"]) == 500 and tree["execution_summary"]["total"] == 500
    assert {i["retry_kind"] for i in tree["items"]} >= {"none", "resume", "fresh_reexecute", "deferred",
                                                        "preflight_recheck"}


def test_500_items_are_deterministic_and_identity_free(preview500, result500):
    for build, graph in ((build_preview_diagnostics, preview500), (build_execution_diagnostics, result500)):
        one, two = build(graph), build(graph)
        assert one == two and render_diagnostics_json(one) == render_diagnostics_json(two)
    other = preview_batch(500)  # fresh ids / tokens
    assert other.preview_id != preview500.preview_id
    assert render_diagnostics_json(build_preview_diagnostics(other)) == render_diagnostics_json(
        build_preview_diagnostics(preview500))
    text = render_diagnostics_json(build_preview_diagnostics(preview500)).decode("ascii")
    assert preview500.preview_id not in text and preview500.lineage.token not in text


def test_500_items_canary_scan_is_clean(result500):
    for path_policy in PathPolicy:
        data = render_diagnostics_json(build_execution_diagnostics(result500, path_policy=path_policy))
        assert b"C9CANARY" not in data and b"/" not in data


# ---- the MAX boundary


def test_2000_items_build_and_render_below_the_output_limit():
    preview = preview_batch(MAX_DIAGNOSTIC_ITEMS)
    diagnostics = build_preview_diagnostics(preview, path_policy=PathPolicy.BASENAME, timing_policy=TimingPolicy.INCLUDE)
    data = render_diagnostics_json(diagnostics)
    assert len(diagnostics.items) == 2000 and len(data) < MAX_DIAGNOSTIC_OUTPUT_BYTES
    result = execution_result(MAX_DIAGNOSTIC_ITEMS)
    data = render_diagnostics_json(build_execution_diagnostics(result))
    assert len(json.loads(data)["items"]) == 2000 and len(data) < MAX_DIAGNOSTIC_OUTPUT_BYTES


def test_2001_items_fail_before_any_per_item_work():
    """The fake items count every attribute access: the limit check precedes all of them."""
    touched = []

    class Counting:
        def __getattribute__(self, name):
            touched.append(name)
            return object.__getattribute__(self, name)

    for kind, graph in (("preview", preview_batch(2)), ("execution", execution_result(2))):
        b.poke(graph, items=tuple(Counting() for _ in range(MAX_DIAGNOSTIC_ITEMS + 1)))
        with pytest.raises(DiagnosticsResourceLimitError):
            b.BUILD[kind](graph)
    assert touched == []


def test_2000_items_each_with_64_provenance_keys_still_succeed():
    """The worst legal input under the limits: one shared aggregation whose ``field_sources`` holds exactly
    ``MAX_PROVENANCE_KEYS`` keys, referenced by 2000 items."""
    keys = {name: ("src_a",) for name in PROVENANCE_FIELD_ORDER}
    keys.update({"u%d" % i: ("src_a",) for i in range(MAX_PROVENANCE_KEYS - len(keys))})
    full = dict(studio="S", publisher="P", release="2020-01-01", runtime=90, plot="pl", actors=("a",), tags=("t",),
                poster_urls=("https://x.invalid/p",), thumb_urls=("https://x.invalid/t",),
                fanart_urls=("https://x.invalid/f",), extrafanart=("https://x.invalid/e",),
                source_urls=("https://x.invalid/s",), external_ids={"k": "v"})
    count = MAX_DIAGNOSTIC_ITEMS
    lineage = b.Lineage(count)
    items = []
    for index in range(count):
        metadata = b.NormalizedMetadata(number=lineage.numbers[index], title="T", field_sources=keys, **full)
        aggregation = b.make_aggregation([b.make_source_result("src_a", number=lineage.numbers[index])],
                                         metadata=metadata, number=lineage.numbers[index])
        items.append(b.batch_item_for(aggregation, index=index))
    lineage.metadata = b.metadata_batch(tuple(items))
    lineage.plans = [b.plan_for(lineage.media[i], lineage.numbers[i]) for i in range(count)]
    preview = lineage.preview([lineage.preview_item(i) for i in range(count)])
    diagnostics = build_preview_diagnostics(preview)
    assert all(len(i.metadata.field_provenance) == 15 for i in diagnostics.items)
    assert len(render_diagnostics_json(diagnostics)) < MAX_DIAGNOSTIC_OUTPUT_BYTES
