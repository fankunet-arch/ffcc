"""P4-C9 contract sections 9.6.2 / 9.6.4 / M-30 and section 28.1 "RetryMaterial tamper" / "retry_kind consistency":
presence versus the locally derived ``retry_kind``, ``material.plan is item.plan``, the RESUME / FRESH checkpoint
identity, artifact tampering, the retained-payload budgets (counted by reference), no ``content`` in the output and
the local derivation of all six ``RetryKind`` values against P4-C8."""

from __future__ import annotations

import dataclasses
import importlib

import pytest
from fc2_organizer.diagnostics import DiagnosticsError, DiagnosticsIntegrityError as Int
from fc2_organizer.execution import ExecutionStatus as X
from fc2_organizer.materialization import ArtifactKind, ArtifactWriteRequest
from fc2_organizer.orchestration import (
    ExecutionDisposition as D,
    IssueReason as R,
    ItemExecution,
    PreviewState as S,
    RetryKind as K,
    RetryMaterial,
)

from fc2_organizer.orchestration import BatchExecutionResult
from . import _builders as b
from . import _builders as h

build_module = importlib.import_module("fc2_organizer.diagnostics.build")
RESUME_ITEM, FRESH_ITEM, DEFERRED_ITEM, RECHECK_ITEM = 1, 2, 3, 7
KIND_OF = {0: K.NONE, 1: K.RESUME, 2: K.FRESH_REEXECUTE, 3: K.DEFERRED, 4: K.DEFERRED, 5: K.NONE, 6: K.NONE,
           7: K.PREFLIGHT_RECHECK}


def graph():
    return h.execution_graph()


def material_of(g, position):
    return g.items[position].retry_material


def counted(monkeypatch):
    """Counters for projection and for the approved ``retry_kind`` / ``summary`` property reads."""

    reached = []
    original = build_module.project_batch
    monkeypatch.setattr(build_module, "project_batch", lambda *a, **k: reached.append(1) or original(*a, **k))
    reads = []
    for cls, name in ((ItemExecution, "retry_kind"), (BatchExecutionResult, "summary"),
                      (BatchExecutionResult, "outcome")):
        real = cls.__dict__[name]
        monkeypatch.setattr(cls, name, property(lambda self, real=real, name=name: reads.append(name) or real.fget(self)))
    return reached, reads


def rejects_before_projection_and_property_reads(monkeypatch, tamper, label):
    g = graph()
    h.BUILD["execution"](g)
    reached, reads = counted(monkeypatch)
    tamper(g)
    before = b.fingerprint(g)
    reads.clear()
    with pytest.raises(DiagnosticsError) as caught:
        h.BUILD["execution"](g)
    assert type(caught.value) is Int, label
    assert reached == [] and reads == [], "%s: projection %s / property reads %s" % (label, reached, reads)
    assert b.fingerprint(g) == before  # the (tampered) input is untouched


# ---- the six RetryKind values: the local derivation equals P4-C8 for every item


def test_the_six_retry_kinds_are_derived_locally_and_equal_p4_c8():
    g = graph()
    diag = h.BUILD["execution"](g)
    assert [i.retry_kind for i in diag.items] == [item.retry_kind for item in g.items]
    assert [i.retry_kind for i in diag.items] == [KIND_OF[i] for i in range(8)]
    # METADATA_REFETCH comes from a metadata-stage NOT_READY item
    lineage = b.Lineage(2, kinds={1: "engine"})
    items = [lineage.execution_item(0, D.EXECUTED, status=X.SUCCESS),
             lineage.execution_item(1, D.NOT_READY, state=S.UNPREPARED, reason=R.METADATA_ENGINE_FAILURE,
                                    with_plan=False,
                                    issue_kwargs={"error_type": "RuntimeError",
                                                  "detail": b.BatchItemErrorKind.ENGINE_EXCEPTION})]
    refetch = h.BUILD["execution"](lineage.result(items))
    assert [i.retry_kind for i in refetch.items] == [K.NONE, K.METADATA_REFETCH]
    assert {*(i.retry_kind for i in diag.items), K.METADATA_REFETCH} == set(K)


def test_retry_material_retained_equals_the_presence_relation():
    diag = h.BUILD["execution"](graph())
    assert [i.retry_material_retained for i in diag.items] == [
        KIND_OF[i] in (K.PREFLIGHT_RECHECK, K.FRESH_REEXECUTE, K.RESUME, K.DEFERRED) for i in range(8)]


# ---- presence versus retry_kind


@pytest.mark.parametrize("position", [RESUME_ITEM, FRESH_ITEM, DEFERRED_ITEM, RECHECK_ITEM])
def test_a_missing_material_where_one_is_required_is_rejected(monkeypatch, position):
    rejects_before_projection_and_property_reads(
        monkeypatch, lambda g: b.poke(g.items[position], retry_material=None), "missing %d" % position)


@pytest.mark.parametrize("position", [0, 5, 6])
def test_a_material_where_none_is_allowed_is_rejected(monkeypatch, position):
    rejects_before_projection_and_property_reads(
        monkeypatch, lambda g: b.poke(g.items[position], retry_material=material_of(graph(), RESUME_ITEM)),
        "extra %d" % position)


# ---- material.plan is item.plan (identity, not equality)


@pytest.mark.parametrize("position", [RESUME_ITEM, FRESH_ITEM, DEFERRED_ITEM, RECHECK_ITEM])
def test_material_plan_must_be_the_items_own_plan_object(monkeypatch, position):
    def tamper(g):
        material = material_of(g, position)
        b.poke(material, plan=dataclasses.replace(g.items[position].plan))  # equal, not identical

    rejects_before_projection_and_property_reads(monkeypatch, tamper, "plan identity %d" % position)


def test_material_plan_of_another_item_is_rejected(monkeypatch):
    rejects_before_projection_and_property_reads(
        monkeypatch, lambda g: b.poke(material_of(g, RESUME_ITEM), plan=g.items[FRESH_ITEM].plan), "foreign plan")


# ---- the checkpoint relations


def test_resume_requires_the_execution_checkpoint_object_itself(monkeypatch):
    other = graph().items[RESUME_ITEM].execution.checkpoint
    rejects_before_projection_and_property_reads(
        monkeypatch, lambda g: b.poke(material_of(g, RESUME_ITEM), checkpoint=other), "other checkpoint object")
    rejects_before_projection_and_property_reads(
        monkeypatch, lambda g: b.poke(material_of(g, RESUME_ITEM), checkpoint=None), "resume without checkpoint")


def test_resume_requires_the_execution_to_carry_a_checkpoint(monkeypatch):
    rejects_before_projection_and_property_reads(
        monkeypatch, lambda g: b.poke(g.items[RESUME_ITEM].execution, checkpoint=None), "execution checkpoint gone")


def test_fresh_reexecute_must_not_carry_a_checkpoint(monkeypatch):
    checkpoint = graph().items[RESUME_ITEM].execution.checkpoint
    rejects_before_projection_and_property_reads(
        monkeypatch, lambda g: b.poke(material_of(g, FRESH_ITEM), checkpoint=checkpoint), "fresh with checkpoint")


@pytest.mark.parametrize("position", [DEFERRED_ITEM, RECHECK_ITEM])
def test_deferred_and_recheck_accept_none_or_an_exact_checkpoint(position):
    """P4-C9 adds no stricter rule than P4-C8 for these two kinds (contract 9.6.4)."""
    g = graph()
    h.BUILD["execution"](g)
    b.poke(material_of(g, position), checkpoint=None)
    h.BUILD["execution"](g)
    b.poke(material_of(g, position), checkpoint=graph().items[RESUME_ITEM].execution.checkpoint)
    out = h.BUILD["execution"](g)
    assert out.items[position].retry_material_retained is True


@pytest.mark.parametrize("position", [DEFERRED_ITEM, RECHECK_ITEM])
def test_deferred_and_recheck_reject_a_non_checkpoint_object(monkeypatch, position):
    rejects_before_projection_and_property_reads(
        monkeypatch, lambda g: b.poke(material_of(g, position), checkpoint=object()), "foreign checkpoint")


# ---- artifact tampering


ARTIFACT_TAMPERS = {
    "content_str": lambda r: b.poke(r, content="text"),
    "content_bytearray": lambda r: b.poke(r, content=bytearray(b"x")),
    "content_none": lambda r: b.poke(r, content=None),
    "content_bytes_subclass": lambda r: b.poke(r, content=h.HostileBytes(b"x")),
    "kind_str": lambda r: b.poke(r, kind="nfo"),
    "target_empty": lambda r: b.poke(r, target_path=""),
    "target_not_str": lambda r: b.poke(r, target_path=7),
    "ordinal_on_non_extrafanart": lambda r: b.poke(r, ordinal=1),
}


@pytest.mark.parametrize("label", sorted(ARTIFACT_TAMPERS))
def test_a_tampered_retained_artifact_is_rejected(monkeypatch, label):
    rejects_before_projection_and_property_reads(
        monkeypatch, lambda g: ARTIFACT_TAMPERS[label](material_of(g, RESUME_ITEM).artifacts[0]), label)


def test_an_artifact_that_is_not_an_artifact_write_request_is_rejected(monkeypatch):
    rejects_before_projection_and_property_reads(
        monkeypatch, lambda g: b.poke(material_of(g, RESUME_ITEM), artifacts=(object(),)), "foreign artifact")
    rejects_before_projection_and_property_reads(
        monkeypatch, lambda g: b.poke(material_of(g, RESUME_ITEM), artifacts=list(material_of(g, 1).artifacts)),
        "artifacts list")


def test_the_material_itself_must_be_an_exact_retry_material(monkeypatch):
    for bad in (object(), h.Hostile()):
        rejects_before_projection_and_property_reads(
            monkeypatch, lambda g, bad=bad: b.poke(g.items[RESUME_ITEM], retry_material=bad), "material type")
    subclass = type("Sub", (RetryMaterial,), {})
    rejects_before_projection_and_property_reads(
        monkeypatch, lambda g: b.poke(g.items[RESUME_ITEM], retry_material=b.poke_subclass(
            subclass, material_of(g, RESUME_ITEM))), "material subclass")


# ---- retained budgets


def retained_total(g):
    return sum(len(request.content) for item in g.items if item.retry_material is not None
               for request in item.retry_material.artifacts)


def test_retained_bytes_exactly_at_the_budget_pass_and_one_less_budget_fails(monkeypatch):
    g = graph()
    total = retained_total(g)
    assert total > 0
    b.poke(g, retention_budget_bytes=total)
    h.BUILD["execution"](g)
    rejects_before_projection_and_property_reads(
        monkeypatch, lambda g: b.poke(g, retention_budget_bytes=total - 1), "budget one below")


def test_a_payload_over_the_budget_is_rejected_before_any_property_read(monkeypatch):
    def tamper(g):
        big = ArtifactWriteRequest(kind=ArtifactKind.NFO, target_path=material_of(g, 1).artifacts[0].target_path,
                                   content=b"x" * 5000, ordinal=None)
        b.poke(material_of(g, FRESH_ITEM), artifacts=(big,))
        b.poke(g, retention_budget_bytes=100)

    rejects_before_projection_and_property_reads(monkeypatch, tamper, "payload over budget")


def test_shared_bytes_are_counted_once_per_reference():
    g = graph()
    payload = b"y" * 100
    request = material_of(g, RESUME_ITEM).artifacts[0]
    clone = ArtifactWriteRequest(kind=request.kind, target_path=request.target_path, content=payload,
                                 ordinal=request.ordinal)
    b.poke(material_of(g, RESUME_ITEM), artifacts=(clone, clone, clone))
    b.poke(material_of(g, FRESH_ITEM), artifacts=())
    b.poke(material_of(g, DEFERRED_ITEM), artifacts=())
    for position in (4, RECHECK_ITEM):
        b.poke(g.items[position].retry_material, artifacts=())
    assert retained_total(g) == 300  # three references to one bytes object are 300 bytes
    b.poke(g, retention_budget_bytes=300)
    h.BUILD["execution"](g)
    b.poke(g, retention_budget_bytes=299)
    with pytest.raises(Int):
        h.BUILD["execution"](g)


def test_the_retry_round_budget_is_the_smaller_retry_budget():
    lineage = b.Lineage(3)
    plan = lineage.plans[1]
    execution = b.rich_execution(plan, X.PARTIAL)
    item = lineage.execution_item(1, D.EXECUTED, execution=execution, material=True, generation=1,
                                  warnings=())
    total = sum(len(r.content) for r in item.retry_material.artifacts)
    result = lineage.result([item], generation=1, base_result_id=b.new_id(), retry_scope=frozenset({K.RESUME}),
                            retry_budget=total)
    h.BUILD["execution"](result)
    b.poke(result, retry_budget_bytes=total - 1)
    with pytest.raises(Int):
        h.BUILD["execution"](result)


# ---- the output never carries material content; inputs are unchanged


def test_the_output_never_contains_retained_content_or_paths():
    g = graph()
    out = h.BUILD["execution"](g)
    text = repr(out)
    for item in g.items:
        if item.retry_material is not None:
            for request in item.retry_material.artifacts:
                assert request.content.decode("utf-8", "ignore")[:20] not in text or not request.content
                assert request.target_path not in text
    assert "content" not in {f.name for f in dataclasses.fields(type(out.items[1]))}


def test_a_failed_build_does_not_alter_the_material_or_the_item():
    g = graph()
    b.poke(material_of(g, RESUME_ITEM), plan=g.items[FRESH_ITEM].plan)
    before, ids = b.fingerprint(g), b.identities(g)
    with pytest.raises(Int):
        h.BUILD["execution"](g)
    assert b.fingerprint(g) == before and b.identities(g) == ids
