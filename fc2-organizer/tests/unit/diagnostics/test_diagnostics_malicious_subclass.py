"""P4-C9 contract section 28.1 "malicious nested subclass" row (R-02 non-vacuity), sections 9.0 / 9.11 H-02 / H-03 /
H-04 / H-07 / H-08 / H-11: a hostile subclass / element planted at every implanted position of the input graph
must be rejected with ``DiagnosticsIntegrityError`` *and* with every sentinel hook still at zero.

Discipline (contract "Sentinel reset rule"): every graph below is built through the upstream public constructors
first; the plant is applied behind the constructors with ``object.__setattr__``; the sentinels are reset after the
whole graph exists and read after the builder returns. Layer C (a forged ``mappingproxy`` referent) is out of the
test model."""

from __future__ import annotations

import pytest
from fc2_organizer.diagnostics import DiagnosticsIntegrityError
from fc2_organizer.orchestration import RetryKind

from fc2_metadata_core.models import SourceResult, SourceStatus
from . import _builders as b
from . import _builders as h

AGG = ("metadata_batch", "items", 0, "aggregation_result")

PREVIEW_OBJECTS = [
    ("item", ("items", 0)), ("plan", ("items", 0, "plan")), ("preflight", ("items", 0, "preflight")),
    ("media_item", ("items", 0, "media_item")), ("metadata_batch", ("metadata_batch",)),
    ("batch_item", ("metadata_batch", "items", 0)), ("aggregation", AGG), ("metadata", AGG + ("metadata",)),
    ("source_result", AGG + ("source_results", 0)), ("trace", AGG + ("source_execution_traces", 1)),
    ("attempt", AGG + ("source_execution_traces", 1, "attempts", 0)),
    ("conflict", AGG + ("conflicts", 0)), ("operation", ("items", 0, "plan", "operations", 0)),
    ("artifact_request", ("items", 0, "preflight", "artifacts", 0)), ("lineage", ("lineage",)),
    ("trace_final_result", AGG + ("source_execution_traces", 1, "final_result")),
]
EXECUTION_OBJECTS = [
    ("item", ("items", 0)), ("execution", ("items", 1, "execution")),
    ("effect", ("items", 1, "execution", "completed_effects", 0)),
    ("leftover", ("items", 1, "execution", "leftover_temporaries", 0)),
    ("failure", ("items", 2, "execution", "failure")), ("retry_material", ("items", 1, "retry_material")),
    ("material_plan", ("items", 1, "retry_material", "plan")),
    ("material_artifact", ("items", 1, "retry_material", "artifacts", 0)),
    ("checkpoint", ("items", 1, "retry_material", "checkpoint")),
    ("item_plan", ("items", 0, "plan")), ("metadata_batch", ("metadata_batch",)),
    ("batch_item", ("metadata_batch", "items", 0)),
]
PREVIEW_CONTAINERS = [
    ("items", ("items",)), ("metadata_items", ("metadata_batch", "items")),
    ("conflict_with", ("items", 0, "conflict_with")), ("image_failures", ("items", 0, "image_failures")),
    ("operations", ("items", 0, "plan", "operations")), ("artifacts", ("items", 0, "preflight", "artifacts")),
    ("blockers", ("items", 0, "preflight", "blockers")), ("skipped_steps", ("items", 0, "preflight", "skipped_steps")),
    ("completed_units", ("items", 0, "preflight", "completed_units")),
    ("source_results", AGG + ("source_results",)), ("traces", AGG + ("source_execution_traces",)),
    ("contributing", AGG + ("contributing_source_ids",)), ("disabled", AGG + ("disabled_source_ids",)),
    ("conflicts", AGG + ("conflicts",)), ("alternatives", AGG + ("conflicts", 0, "alternatives")),
    ("attempts", AGG + ("source_execution_traces", 1, "attempts")),
]
EXECUTION_CONTAINERS = [
    ("items", ("items",)), ("warnings", ("items", 1, "warnings")),
    ("completed_effects", ("items", 1, "execution", "completed_effects")),
    ("leftover", ("items", 1, "execution", "leftover_temporaries")),
    ("skipped_steps", ("items", 1, "execution", "skipped_steps")),
    ("material_artifacts", ("items", 1, "retry_material", "artifacts")),
    ("conflict_with", ("items", 0, "conflict_with")), ("image_failures", ("items", 0, "image_failures")),
    ("operations", ("items", 1, "retry_material", "plan", "operations")),
]
# str-id positions: the (public-constructor-reachable) ``str`` subclass of contract UC-6 / UC-7
ID_CONTAINERS = [("contributing", AGG + ("contributing_source_ids",)), ("disabled", AGG + ("disabled_source_ids",))]
ELEMENT_CLASSES = [("hostile_object", h.Hostile), ("evil_str", lambda: b.EvilStr("src_a")),
                   ("hostile_int", lambda: h.HostileInt(1))]


def planted(kind, mutate):
    graph = h.FACTORY[kind]()
    h.BUILD[kind](graph)  # the unplanted graph builds: a rejection is attributable to the plant
    mutate(graph)
    return graph


@pytest.mark.parametrize(("label", "path"), PREVIEW_OBJECTS, ids=[x[0] for x in PREVIEW_OBJECTS])
def test_a_hostile_subclass_object_in_the_preview_graph_is_rejected_unread(label, path):
    graph = planted("preview", lambda g: h.plant_object(g, path))
    h.assert_fail_closed(h.BUILD["preview"], graph, label)


@pytest.mark.parametrize(("label", "path"), EXECUTION_OBJECTS, ids=[x[0] for x in EXECUTION_OBJECTS])
def test_a_hostile_subclass_object_in_the_execution_graph_is_rejected_unread(label, path):
    graph = planted("execution", lambda g: h.plant_object(g, path))
    h.assert_fail_closed(h.BUILD["execution"], graph, label)


@pytest.mark.parametrize(("label", "path"), PREVIEW_CONTAINERS, ids=[x[0] for x in PREVIEW_CONTAINERS])
@pytest.mark.parametrize(("element_label", "element"), ELEMENT_CLASSES, ids=[x[0] for x in ELEMENT_CLASSES])
def test_a_hostile_element_in_a_preview_container_is_rejected_unread(label, path, element_label, element):
    graph = planted("preview", lambda g: h.plant_element(g, path, element()))
    h.assert_fail_closed(h.BUILD["preview"], graph, "%s/%s" % (label, element_label))


@pytest.mark.parametrize(("label", "path"), EXECUTION_CONTAINERS, ids=[x[0] for x in EXECUTION_CONTAINERS])
@pytest.mark.parametrize(("element_label", "element"), ELEMENT_CLASSES, ids=[x[0] for x in ELEMENT_CLASSES])
def test_a_hostile_element_in_an_execution_container_is_rejected_unread(label, path, element_label, element):
    graph = planted("execution", lambda g: h.plant_element(g, path, element()))
    h.assert_fail_closed(h.BUILD["execution"], graph, "%s/%s" % (label, element_label))


@pytest.mark.parametrize("kind", ["preview", "execution"])
@pytest.mark.parametrize("path", [("items",)], ids=["items"])
def test_a_tuple_subclass_container_is_rejected_before_iteration(kind, path):
    graph = planted(kind, lambda g: h.plant_container(g, path))
    h.assert_fail_closed(h.BUILD[kind], graph, "items")


@pytest.mark.parametrize(("label", "path"), PREVIEW_CONTAINERS, ids=[x[0] for x in PREVIEW_CONTAINERS])
def test_a_tuple_subclass_container_in_the_preview_graph_is_rejected_before_iteration(label, path):
    graph = planted("preview", lambda g: h.plant_container(g, path))
    h.assert_fail_closed(h.BUILD["preview"], graph, label)


@pytest.mark.parametrize(("label", "path"), EXECUTION_CONTAINERS, ids=[x[0] for x in EXECUTION_CONTAINERS])
def test_a_tuple_subclass_container_in_the_execution_graph_is_rejected_before_iteration(label, path):
    graph = planted("execution", lambda g: h.plant_container(g, path))
    h.assert_fail_closed(h.BUILD["execution"], graph, label)


# ---- H-02 / H-03: str-subclass source ids reached through the *public* constructors (UC-6 / UC-7)


@pytest.mark.parametrize(("label", "path"), ID_CONTAINERS, ids=[x[0] for x in ID_CONTAINERS])
def test_an_evil_str_source_id_in_an_id_container_is_rejected_unread(label, path):
    graph = planted("preview", lambda g: h.plant_element(g, path, b.EvilStr("src_a")))
    h.assert_fail_closed(h.BUILD["preview"], graph, label)


def test_an_evil_str_source_id_built_through_the_public_constructors_is_rejected_unread():
    """The upstream constructors accept the ``str`` subclass in ``SourceResult.source_id``, in the contributing ids
    and in the provenance value tuple (UC-6 / UC-7); the sentinels are reset after *all* of them ran."""
    evil = b.EvilStr("src_a")

    result = SourceResult(source_id=evil, status=SourceStatus.SUCCESS, metadata=b.make_metadata_core(), elapsed_ms=1.0)
    aggregation = b.make_aggregation([result], field_sources={"number": (evil,), "title": (evil,)})
    assert type(aggregation.contributing_source_ids[0]) is b.EvilStr
    preview = b.preview_of_metadata(b.batch_item_for(aggregation))
    h.assert_fail_closed(h.BUILD["preview"], preview, "public evil source id")


def test_an_evil_str_in_a_provenance_value_tuple_is_rejected_unread():
    preview = h.preview_graph()
    metadata = read_metadata(preview)
    import types

    b.poke(metadata, field_sources=types.MappingProxyType({"number": (b.EvilStr("src_a"),)}))
    h.assert_fail_closed(h.BUILD["preview"], preview, "provenance value")


def read_metadata(preview):
    return preview.metadata_batch.items[0].aggregation_result.metadata


def test_an_evil_str_in_a_conflict_alternative_is_rejected_unread():
    def mutate(graph):
        conflict = graph.metadata_batch.items[0].aggregation_result.conflicts[0]
        b.poke(conflict, alternatives=((b.EvilStr("src_c"), "Other Title"),))

    h.assert_fail_closed(h.BUILD["preview"], planted("preview", mutate), "alternatives")


# ---- H-01: a retry scope with hostile elements / a hostile frozenset


def retry_preview():
    lineage = b.Lineage(2)
    items = [lineage.preview_item(1, generation=1, retry_origin=RetryKind.RESUME)]
    return lineage.preview(items, generation=1, base_result_id=b.new_id(),
                           retry_scope=frozenset({RetryKind.RESUME}), retry_budget=10**6)


@pytest.mark.parametrize("element", [h.Hostile, lambda: b.EvilStr("RESUME"), lambda: h.HostileInt(1)],
                         ids=["object", "evil_str", "int"])
def test_a_hostile_element_in_retry_scope_is_rejected_unread(element):
    preview = retry_preview()
    h.BUILD["preview"](preview)
    b.poke(preview, retry_scope=frozenset({RetryKind.RESUME, element()}))
    h.assert_fail_closed(h.BUILD["preview"], preview, "retry_scope")


def test_a_frozenset_subclass_retry_scope_is_rejected_unread():
    preview = retry_preview()
    b.poke(preview, retry_scope=h.HostileFrozenSet({RetryKind.RESUME}))
    h.assert_fail_closed(h.BUILD["preview"], preview, "retry_scope subclass")


def test_retry_scope_none_member_is_rejected():
    preview = retry_preview()
    b.poke(preview, retry_scope=frozenset({RetryKind.NONE}))
    exc, hits = h.run_hostile(h.BUILD["preview"], preview)
    assert type(exc) is DiagnosticsIntegrityError and sum(hits.values()) == 0


# ---- the artifact payload (bytes subclass)


def test_a_bytes_subclass_content_is_rejected_unread():
    graph = h.preview_graph()
    request = graph.items[0].preflight.artifacts[0]
    b.poke(request, content=h.HostileBytes(b"x"))
    h.assert_fail_closed(h.BUILD["preview"], graph, "bytes content")


def test_the_harness_is_not_vacuous_a_clean_graph_builds_and_a_hook_does_fire_when_called():
    for kind in ("preview", "execution"):
        h.BUILD[kind](h.FACTORY[kind]())
    b.reset_hits()
    hostile = h.Hostile()
    hash(hostile)
    hostile == 1
    bool(hostile)
    assert b.HITS["hash"] == 1 and b.HITS["eq"] == 1 and b.HITS["bool"] == 1
    subclass = h.hostile_instance(h.preview_graph().items[0].plan)
    b.reset_hits()
    repr(subclass)
    assert b.HITS["repr"] == 1
