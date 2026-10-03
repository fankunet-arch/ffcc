"""P4-C9 contract sections 9.5 (M-01..M-30) and 9.6 (cross-object relations), tables T-1..T-4: the local validation
map. A *field coverage* sweep proves that every field of every consumed upstream object is either type-confirmed
(a hostile ``object()`` in it fails closed) or is one of the documented "not read" fields (the output then does not
change at all); a boundary table pins the numeric ranges; the T-tables are exercised relation by relation."""

from __future__ import annotations

import dataclasses

import pytest
from fc2_metadata_core.batch import BatchItemErrorKind
from fc2_metadata_core.models import SourceErrorKind as E, SourceStatus as T
from fc2_organizer.diagnostics import DiagnosticsError, DiagnosticsIntegrityError as Int
from fc2_organizer.execution import (
    EffectKind,
    EntryIdentity,
    ExecutionFailureKind,
    ExecutionStatus as X,
    PathRole,
)
from fc2_organizer.orchestration import (
    ExecutionDisposition as D,
    IssueReason as R,
    ItemIssue,
    OrchestrationStage as O,
    PreviewState as S,
)
from fc2_organizer.images import ImageAcquisitionPolicy
from fc2_organizer.planning import OutputPolicy
from fc2_organizer.materialization import ArtifactKind

from . import _builders as b
from . import _builders as h

AGG = ("metadata_batch", "items", 0, "aggregation_result")
SHARED = (EntryIdentity,)  # module-level constants shared by every graph: never tampered in place


def dataclass_nodes(root, path=(), seen=None, found=None):
    found = [] if found is None else found
    seen = set() if seen is None else seen
    if dataclasses.is_dataclass(root) and not isinstance(root, type):
        if id(root) in seen or type(root) in SHARED:
            return found
        seen.add(id(root))
        found.append((path, root))
        for field in dataclasses.fields(root):
            dataclass_nodes(getattr(root, field.name), path + (field.name,), seen, found)
    elif type(root) is tuple:
        for position, member in enumerate(root):
            dataclass_nodes(member, path + (position,), seen, found)
    return found


def locate(root, path):
    node = root
    for step in path:
        node = node[step] if type(step) is int else getattr(node, step)
    return node


# fields the contract does not read (M-04 / M-18 / M-23 / M-27 and the type-only policy objects)
def unread(path, node, field):
    kind = type(node)
    if "checkpoint" in path:  # M-04: ExecutionCheckpoint (and its content) is type-confirmed only
        return True
    if isinstance(node, (OutputPolicy, ImageAcquisitionPolicy)):  # M-04
        return True
    if kind.__name__ == "ExecutionPreflight" and field in ("library_root_identity", "source_identity"):
        return True  # M-23: not read
    if kind.__name__ == "CompletedEffect" and field in ("path", "identity", "size", "sha256"):
        return True  # M-27: not read
    if kind.__name__ == "NormalizedMetadata":  # M-18
        if field == "field_sources":
            return "source_results" in path  # only AggregationResult.metadata's provenance is read
        return field not in ("number", "title")
    return False


@pytest.mark.parametrize("kind", ["preview", "execution"])
def test_every_consumed_field_is_type_confirmed_or_documented_as_not_read(kind):
    pristine = h.BUILD[kind](h.FACTORY[kind]())
    checked = confirmed = ignored = 0
    for path, node in dataclass_nodes(h.FACTORY[kind]()):
        for field in dataclasses.fields(node):
            graph = h.FACTORY[kind]()
            target = locate(graph, path)
            b.poke(target, **{field.name: object()})
            checked += 1
            if unread(path, target, field.name):
                assert h.BUILD[kind](graph) == pristine, "%s.%s is documented as not read" % (type(target).__name__,
                                                                                                field.name)
                ignored += 1
                continue
            with pytest.raises(DiagnosticsError) as caught:
                h.BUILD[kind](graph)
            assert type(caught.value) is Int, "%s.%s" % (type(target).__name__, field.name)
            confirmed += 1
    assert checked == confirmed + ignored and confirmed > 150 and ignored > 20


# ---- numeric ranges (exact int; bool / float / str impersonation is rejected for every one of them)


class IntSub(int):
    pass


RANGES = [  # (label, kind, path, field, accepted values, rejected values)
    ("item.index", "preview", ("items", 1), "index", [], [-1, 2, 5]),
    ("item.generation", "preview", ("items", 0), "generation", [], [-1]),
    ("plan.source_size", "preview", ("items", 0, "plan"), "source_size", [], [-1]),
    ("attempt.sequence", "preview", AGG + ("source_execution_traces", 1, "attempts", 1), "sequence", [], [0, -1, 3]),
    ("trace.max_attempts", "preview", AGG + ("source_execution_traces", 1), "max_attempts", [2, 10**400],
     [0, -1, 1]),
    ("failure.errno", "execution", ("items", 2, "execution", "failure"), "errno", [0, 10**400], [-1, -5]),
    ("execution.new_effect_count", "execution", ("items", 1, "execution"), "new_effect_count", [0, 3, 8],
     [-1, 9, 10**400]),
    ("effect.ordinal", "execution", ("items", 1, "execution", "completed_effects", 6), "ordinal", [1, 2, 10**400],
     [0, -1]),
    ("batch.retention_budget", "preview", (), "retention_budget_bytes", [10**9], [0, -1, 16 * 1024 ** 3 + 1]),
]


NULLABLE = {"failure.errno", "effect.ordinal"}  # optional ints: ``None`` is a legal value


@pytest.mark.parametrize(("label", "kind", "path", "field", "accepted", "rejected"), RANGES, ids=[r[0] for r in RANGES])
def test_numeric_range_boundaries(label, kind, path, field, accepted, rejected):
    for value in accepted:
        graph = h.FACTORY[kind]()
        b.poke(locate(graph, path), **{field: value})
        h.BUILD[kind](graph)
    nullable = label in NULLABLE
    for value in rejected + [True, 1.5, "1", IntSub(1)] + ([] if nullable else [None]):
        graph = h.FACTORY[kind]()
        b.poke(locate(graph, path), **{field: value})
        with pytest.raises(Int):
            h.BUILD[kind](graph)


def test_the_maximum_retention_budget_is_accepted():
    graph = h.preview_graph()
    b.poke(graph, retention_budget_bytes=16 * 1024 ** 3)
    h.BUILD["preview"](graph)


# ---- T-1: the ItemIssue reason table


def issue_graph(**fields):
    graph = h.execution_graph()
    item = graph.items[5]  # REJECTED / EXECUTION_REJECTED
    b.poke(item.issue, **fields)
    return graph


@pytest.mark.parametrize("stage", [s for s in O if s is not O.EXECUTION])
def test_t1_the_stage_must_be_the_reasons_frozen_stage(stage):
    with pytest.raises(Int):
        h.BUILD["execution"](issue_graph(stage=stage))


def test_t1_error_type_presence_follows_the_reason():
    h.BUILD["execution"](issue_graph(error_type="ValueError"))
    with pytest.raises(Int):
        h.BUILD["execution"](issue_graph(error_type=None))  # EXECUTION_REJECTED requires an error type
    graph = h.execution_graph()
    b.poke(graph.items[2].issue, error_type="ValueError")  # EXECUTION_FAILED must not carry one
    with pytest.raises(Int):
        h.BUILD["execution"](graph)


@pytest.mark.parametrize("detail", [BatchItemErrorKind.ENGINE_EXCEPTION, ExecutionFailureKind.MEDIA_TRANSFER_FAILED,
                                    "text", 1, object()])
def test_t1_the_detail_type_must_be_one_the_reason_allows(detail):
    with pytest.raises(Int):
        h.BUILD["execution"](issue_graph(detail=detail))


def test_t1_failure_issues_must_carry_the_failure_kind_as_detail():
    graph = h.execution_graph()
    b.poke(graph.items[2].issue, detail=ExecutionFailureKind.ARTIFACT_WRITE_FAILED)
    with pytest.raises(Int):
        h.BUILD["execution"](graph)


# ---- T-2: SourceStatus -> allowed SourceErrorKind


@pytest.mark.parametrize(("status", "kind"), [
    (T.NOT_FOUND, E.TIMEOUT), (T.BLOCKED, E.NOT_FOUND), (T.RATE_LIMITED, E.BLOCKED), (T.NETWORK_ERROR, E.PARSE_ERROR),
    (T.PARSE_ERROR, E.NETWORK_ERROR), (T.INVALID_RESPONSE, E.TIMEOUT), (T.NETWORK_ERROR, E.HTTP_SERVER_ERROR),
    (T.INVALID_RESPONSE, E.CIRCUIT_OPEN)])
def test_t2_an_error_kind_outside_the_status_set_is_rejected(status, kind):
    graph = h.preview_graph()
    source = graph.metadata_batch.items[0].aggregation_result.source_results[1]
    b.poke(source, status=status, error_kind=kind)
    with pytest.raises(Int):
        h.BUILD["preview"](graph)


def test_t2_success_has_no_error_kind_or_detail():
    graph = h.preview_graph()
    source = graph.metadata_batch.items[0].aggregation_result.source_results[0]
    for changes in ({"error_kind": E.TIMEOUT}, {"error_detail": "x"}):
        fresh = h.preview_graph()
        b.poke(fresh.metadata_batch.items[0].aggregation_result.source_results[0], **changes)
        with pytest.raises(Int):
            h.BUILD["preview"](fresh)
    assert source.error_kind is None


def test_t2_a_failure_needs_a_non_blank_detail():
    for detail in (None, "", "   "):
        graph = h.preview_graph()
        b.poke(graph.metadata_batch.items[0].aggregation_result.source_results[1], error_detail=detail)
        with pytest.raises(Int):
            h.BUILD["preview"](graph)


# ---- T-3: artifact kind -> path role and effect kind -> role


@pytest.mark.parametrize("role", [r for r in PathRole if r is not PathRole.POSTER])
def test_t3_an_artifact_effect_must_carry_its_kinds_role(role):
    graph = h.execution_graph()
    effects = graph.items[1].execution.completed_effects
    poster = next(e for e in effects if e.artifact_kind is ArtifactKind.POSTER)
    b.poke(poster, role=role)
    with pytest.raises(Int):
        h.BUILD["execution"](graph)


@pytest.mark.parametrize(("kind", "wrong"), [
    (EffectKind.SOURCE_REMOVED, PathRole.TARGET_MEDIA), (EffectKind.MEDIA_PUBLISHED, PathRole.SOURCE),
    (EffectKind.TARGET_DIRECTORY_CREATED, PathRole.TARGET_MEDIA),
    (EffectKind.EXTRAFANART_DIRECTORY_CREATED, PathRole.TARGET_DIRECTORY)])
def test_t3_a_non_artifact_effect_must_carry_its_frozen_role(kind, wrong):
    graph = h.execution_graph()
    effect = next(e for e in graph.items[1].execution.completed_effects if e.kind is kind)
    b.poke(effect, role=wrong)
    with pytest.raises(Int):
        h.BUILD["execution"](graph)


def test_t3_artifact_kind_and_effect_kind_must_agree():
    graph = h.execution_graph()
    effect = next(e for e in graph.items[1].execution.completed_effects if e.kind is EffectKind.MEDIA_PUBLISHED)
    b.poke(effect, artifact_kind=ArtifactKind.NFO)
    with pytest.raises(Int):
        h.BUILD["execution"](graph)


# ---- T-4 and the 9.6.3 / 9.6.4 relations between state, issue and preflight


def test_t4_blocked_state_iff_a_blocked_reason():
    graph = h.execution_graph()
    b.poke(graph.items[7], preview_state=S.UNPREPARED)  # PREFLIGHT_BLOCKED requires BLOCKED
    with pytest.raises(Int):
        h.BUILD["execution"](graph)
    graph = h.execution_graph()
    b.poke(graph.items[5], preview_state=S.BLOCKED)  # a READY item that was rejected: state must stay READY
    with pytest.raises(Int):
        h.BUILD["execution"](graph)


def test_executed_items_relate_status_failure_and_issue():
    for position, changes in ((0, {"issue": ItemIssue(O.EXECUTION, R.EXECUTION_FAILED, None,
                                                       ExecutionFailureKind.MEDIA_TRANSFER_FAILED)}),
                              (2, {"issue": None}),
                              (1, {"issue": h.execution_graph().items[2].issue})):
        graph = h.execution_graph()
        b.poke(graph.items[position], **changes)
        with pytest.raises(Int):
            h.BUILD["execution"](graph)


def test_disposition_must_agree_with_the_presence_of_an_execution():
    for position, disposition in ((0, D.NOT_SELECTED), (3, D.EXECUTED), (5, D.CANCELLED), (6, D.REJECTED)):
        graph = h.execution_graph()
        b.poke(graph.items[position], disposition=disposition)
        with pytest.raises(Int):
            h.BUILD["execution"](graph)


# ---- 9.6.1 / 9.6.2 batch-level relations


def test_the_lineage_token_must_match_the_metadata_batch():
    for kind in ("preview", "execution"):
        graph = h.FACTORY[kind]()
        other = b.Lineage(8).metadata.lineage
        b.poke(graph, lineage=other)
        with pytest.raises(Int):
            h.BUILD[kind](graph)


def test_item_generations_and_indices_follow_the_shape():
    graph = h.execution_graph()
    b.poke(graph.items[3], generation=1)  # a MAIN result: every item has the batch generation
    with pytest.raises(Int):
        h.BUILD["execution"](graph)
    graph = h.execution_graph()
    b.poke(graph.items[4], index=3)  # duplicate index
    with pytest.raises(Int):
        h.BUILD["execution"](graph)


def test_every_plan_must_live_under_the_batch_library_root():
    graph = h.execution_graph()
    b.poke(graph, library_root=graph.library_root + "-other")
    with pytest.raises(Int):
        h.BUILD["execution"](graph)
