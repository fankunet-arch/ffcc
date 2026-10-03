"""P4-C9 contract sections 9.10 (Dispatch Safety Matrix D-01..D-31), 9.11 (H-01..H-15) and 9.3.1 (approved property
dependency graphs). Every non-NOT-USED row has at least one test whose docstring starts with ``[D-xx]``; the NOT
USED rows (D-06, D-20, D-21, D-22) are proven by AST checks plus sentinel runs.

The sentinel discipline is that of ``test_diagnostics_malicious_subclass``: the hostile graph is built through the
upstream constructors, the plant is applied behind them, the counters are reset after the whole graph exists."""

from __future__ import annotations

import ast
import pathlib
import re
import types

import pytest
from fc2_metadata_core.models import SourceStatus as T
from fc2_organizer import diagnostics
from fc2_organizer.diagnostics import DiagnosticsIntegrityError, validation
from fc2_organizer.orchestration import (
    BatchExecutionResult,
    BatchPreview,
    ExecutionDisposition as D,
    ItemExecution,
    ItemPreview,
    RetryKind,
)

from . import _builders as b
from . import _builders as h

AGG = ("metadata_batch", "items", 0, "aggregation_result")
PRODUCTION = pathlib.Path(diagnostics.__file__).parent


def closed(kind, mutate, label):
    graph = h.FACTORY[kind]()
    h.BUILD[kind](graph)
    mutate(graph)
    h.assert_fail_closed(h.BUILD[kind], graph, label)


def set_field(path, value):
    return lambda graph: h.write(graph, path, value() if callable(value) and not isinstance(value, type) else value)


# ---- D-01 .. D-05: containers and lengths


def test_d01_iteration_runs_only_over_exact_tuples_whose_elements_are_type_checked_first():
    """[D-01] a tuple subclass container is rejected before any iteration; an exact tuple holding a hostile element
    is rejected at the element's type test, with no element hook run."""
    closed("preview", lambda g: h.plant_container(g, ("items",)), "subclass tuple")
    closed("preview", lambda g: h.plant_element(g, ("metadata_batch", "items"), h.Hostile()), "hostile element")
    closed("execution", lambda g: h.plant_element(g, ("items", 1, "execution", "completed_effects"), h.Hostile()),
           "hostile effect")


def test_d02_retry_scope_iteration_checks_each_element_first():
    """[D-02] frozenset iteration: a hostile element stops the scan at its own type test."""
    lineage = b.Lineage(2)
    items = [lineage.preview_item(1, generation=1, retry_origin=RetryKind.RESUME)]
    preview = lineage.preview(items, generation=1, base_result_id=b.new_id(), retry_scope=frozenset({RetryKind.RESUME}),
                              retry_budget=10**6)
    h.BUILD["preview"](preview)
    b.poke(preview, retry_scope=frozenset({RetryKind.RESUME, h.Hostile()}))
    h.assert_fail_closed(h.BUILD["preview"], preview, "frozenset element")


def test_d03_the_field_sources_key_scan_touches_a_key_only_through_type():
    """[D-03] one pass over the stored keys; the only operation on a key is ``type(key) is str``."""
    def plant(graph):
        metadata = graph.metadata_batch.items[0].aggregation_result.metadata
        b.poke(metadata, field_sources=types.MappingProxyType({b.EvilStr("zzz"): ("src_a",)}))

    closed("preview", plant, "evil key")


def test_d04_len_of_a_container_is_taken_only_after_its_exact_type_is_confirmed():
    """[D-04] a ``tuple`` / ``frozenset`` subclass whose ``__len__`` counts is never asked for its length."""
    closed("preview", lambda g: h.plant_container(g, ("items", 0, "conflict_with")), "tuple subclass")
    closed("execution", lambda g: h.plant_container(g, ("items", 1, "warnings")), "warnings subclass")
    lineage = b.Lineage(2)
    preview = lineage.preview([lineage.preview_item(1, generation=1, retry_origin=RetryKind.RESUME)], generation=1,
                              base_result_id=b.new_id(), retry_scope=frozenset({RetryKind.RESUME}),
                              retry_budget=10**6)
    b.poke(preview, retry_scope=h.HostileFrozenSet({RetryKind.RESUME}))
    h.assert_fail_closed(h.BUILD["preview"], preview, "frozenset subclass")


def test_d05_bytes_and_str_are_only_measured_after_their_exact_type_is_confirmed():
    """[D-05] ``content`` is only ``len``-measured when it is exact ``bytes``; ``str`` fields when exact ``str``."""
    def plant(graph):
        b.poke(graph.items[0].preflight.artifacts[0], content=h.HostileBytes(b"x"))

    closed("preview", plant, "bytes subclass")
    closed("preview", lambda g: b.poke(g.items[0].plan, source_path=b.EvilStr("/lib/x.mp4")), "evil path")


# ---- D-07 .. D-13: subscripts, hashed lookups, membership


@pytest.mark.parametrize("position", [-1, 5, 10**400, True, 1.0])
def test_d07_a_metadata_position_is_range_checked_before_it_indexes_anything(position):
    """[D-07] ``metadata_batch.items[metadata_position]``: an out-of-range / non-int position never raises a bare
    ``IndexError`` / ``TypeError``."""
    graph = h.preview_graph()
    b.poke(graph.items[0], metadata_position=position)
    b.reset_hits()
    with pytest.raises(DiagnosticsIntegrityError) as caught:
        h.BUILD["preview"](graph)
    assert type(caught.value) is DiagnosticsIntegrityError


def test_d08_provenance_lookups_start_only_after_every_stored_key_passed_the_scan():
    """[D-08] normal exact keys are looked up (positive control); one hostile key anywhere stops the build before any
    lookup (see test_diagnostics_provenance for the key-position variants)."""
    graph = h.preview_graph()
    keys = {name: ("src_a",) for name in ("number", "title", "unknown_a")}
    b.poke(graph.metadata_batch.items[0].aggregation_result.metadata, field_sources=types.MappingProxyType(keys))
    out = h.BUILD["preview"](graph)
    assert [p.field for p in out.items[0].metadata.field_provenance] == ["number", "title"]


def test_d09_local_tables_are_keyed_only_by_exact_enum_members_str_and_int():
    """[D-09] the T-1..T-4 lookups never see a hostile key."""
    closed("preview", lambda g: b.poke(g.items[0], state=h.Hostile()), "hostile state")
    closed("execution", lambda g: b.poke(g.items[1], disposition=h.Hostile()), "hostile disposition")
    closed("preview", lambda g: b.poke(g.metadata_batch.items[0].aggregation_result.source_results[1],
                                       error_kind=h.Hostile()), "hostile error kind")


def test_d10_locally_built_sets_and_dicts_only_receive_validated_exact_values():
    """[D-10] uniqueness sets over ids / indices: a hostile id never reaches ``set(...)``."""
    closed("preview", lambda g: h.plant_element(g, AGG + ("disabled_source_ids",), b.EvilStr("zzz")), "disabled id")
    closed("preview", lambda g: b.poke(g.items[1], index=h.HostileInt(1)), "hostile index")


def test_d11_membership_in_a_tuple_runs_only_after_that_tuples_phase_v():
    """[D-11] ``contributing_source_ids = ("src_a", EvilSID(...))``: the membership tests of the later phases never run
    the hostile ``__eq__``."""
    def plant(graph):
        aggregation = graph.metadata_batch.items[0].aggregation_result
        b.poke(aggregation, contributing_source_ids=("src_a", b.EvilStr("src_c")))

    closed("preview", plant, "evil contributing id")


def test_d12_retry_origin_membership_runs_only_after_the_scope_iteration_completed():
    """[D-12] ``retry_origin in retry_scope`` with a hostile scope element never runs a hook."""
    lineage = b.Lineage(2)
    preview = lineage.preview([lineage.preview_item(1, generation=1, retry_origin=RetryKind.RESUME)], generation=1,
                              base_result_id=b.new_id(), retry_scope=frozenset({RetryKind.RESUME}),
                              retry_budget=10**6)
    b.poke(preview, retry_scope=frozenset({h.Hostile(), RetryKind.RESUME}))
    h.assert_fail_closed(h.BUILD["preview"], preview, "retry scope member")


def test_d13_membership_against_frozen_constants_only_receives_exact_members():
    """[D-13] ``status in {...}`` / ``error_kind in RETRY_ELIGIBLE_KINDS`` style tests never see a hostile value."""
    closed("preview", lambda g: b.poke(g.metadata_batch.items[0].aggregation_result.source_results[1],
                                       status=h.Hostile()), "hostile status")
    closed("preview", lambda g: b.poke(g.metadata_batch.items[0].aggregation_result.source_execution_traces[1]
                                       .attempts[0], error_kind=h.Hostile()), "hostile attempt kind")


# ---- D-14 .. D-19: equality, identity, ordering


def test_d14_equality_is_only_evaluated_between_exact_same_typed_scalars():
    """[D-14] conflict values: ``bool`` / ``int`` / subclass values are rejected before any ``==``."""
    for value in (True, h.HostileInt(3), b.EvilStr("v")):
        def plant(graph, value=value):
            conflict = graph.metadata_batch.items[0].aggregation_result.conflicts[0]
            b.poke(conflict, selected_value=value)

        closed("preview", plant, repr(type(value)))


def test_d15_comparison_with_the_empty_tuple_is_a_length_test():
    """[D-15] a tuple subclass whose ``__eq__`` / ``__len__`` count never reaches a ``t == ()`` style test."""
    closed("preview", lambda g: b.poke(g.items[0].preflight, blockers=h.HostileTuple()), "empty subclass")
    closed("execution", lambda g: b.poke(g.items[1].execution, leftover_temporaries=h.HostileTuple()), "empty subclass")


def test_d16_element_wise_comparisons_follow_phase_v_of_both_sides():
    """[D-16] ``contributing_source_ids`` vs the successful ids; attempt sequence numbers."""
    closed("preview", lambda g: b.poke(g.metadata_batch.items[0].aggregation_result.source_execution_traces[1]
                                       .attempts[1], sequence=h.HostileInt(2)), "hostile sequence")
    closed("preview", lambda g: h.plant_element(g, AGG + ("contributing_source_ids",), b.EvilStr("src_a")),
           "evil contributing")


def test_d17_identity_tests_never_dispatch_so_a_non_identical_equal_plan_is_simply_rejected():
    """[D-17] ``material.plan is item.plan``: an *equal but distinct* plan object is rejected, an ``__eq__`` is not
    consulted (a hostile subclass would be rejected by its exact-type test first)."""
    def plant(graph):
        item = graph.items[1]
        import dataclasses

        clone = dataclasses.replace(item.plan)
        b.poke(item.retry_material, plan=clone)

    closed("execution", plant, "equal-not-identical plan")


def test_d18_enums_are_compared_by_identity_and_must_be_exact_members():
    """[D-18] a look-alike whose ``__eq__`` always answers ``True`` is never consulted for an enum comparison."""
    for path, kind in ((("items", 0, "state"), "preview"), (("items", 1, "preview_state"), "execution"),
                       (("items", 0, "disposition"), "execution")):
        closed(kind, set_field(path, h.Hostile()), "/".join(map(str, path)))


def test_d19_ordering_comparisons_only_see_exact_ints_and_floats():
    """[D-19] counts / indices / sequence / timings: ``bool`` and subclasses are rejected before any ``<`` / ``>=``."""
    closed("preview", lambda g: b.poke(g.items[0], metadata_position=h.HostileInt(0)), "hostile position")
    closed("preview", lambda g: b.poke(g.metadata_batch.items[0].aggregation_result.source_results[0],
                                       elapsed_ms=h.HostileInt(3)), "hostile elapsed")
    closed("preview", lambda g: b.poke(g.metadata_batch.items[0], elapsed_ms=True), "bool elapsed")


# ---- D-23 .. D-27: regex, path / str operations, field reads, type tests


def test_d23_regex_matches_only_exact_str():
    """[D-23] safe-id / hex patterns: a ``str`` subclass or a non-str never reaches ``re``."""
    closed("preview", lambda g: b.poke(g, preview_id=b.EvilStr("0" * 32)), "evil hex32")
    closed("preview", lambda g: b.poke(g.metadata_batch.items[0].aggregation_result.source_results[0],
                                       source_id=b.EvilStr("src_a")), "evil source id")


def test_d24_path_string_operations_never_receive_a_path_like_object():
    """[D-24] no ``__fspath__`` protocol call: a path-like object in a plan field is a type error, not a path."""
    class PathLike:
        def __fspath__(self):
            b.HITS["call"] += 1
            return "/x"

    closed("preview", lambda g: b.poke(g.items[0].plan, source_path=PathLike()), "path-like")
    closed("preview", lambda g: b.poke(g.items[0].plan, source_path=b.EvilStr("/lib/a.mp4")), "evil path")


def test_d25_str_methods_run_only_on_exact_str():
    """[D-25] ``strip`` / ``startswith`` / ``lower`` on a ``str`` subclass would run subclass code: never reached."""
    closed("preview", lambda g: b.poke(g.items[0].plan, source_extension=b.EvilStr(".mp4")), "evil extension")
    closed("preview", lambda g: b.poke(g.metadata_batch.items[0].aggregation_result.source_results[0],
                                       source_id=b.EvilStr(" ")), "evil blank id")


def test_d26_a_listed_field_of_a_subclass_instance_is_never_read():
    """[D-26] V-1: the hostile subclass's ``__getattribute__`` counter stays at zero."""
    closed("preview", lambda g: h.plant_object(g, ("items", 0, "plan")), "subclass plan")
    closed("execution", lambda g: h.plant_object(g, ("items", 1, "execution")), "subclass execution")


def test_d27_a_forged_class_attribute_does_not_change_the_exact_type_test():
    """[D-27] ``type(x)`` ignores a hostile ``__class__``."""
    class Liar:
        @property
        def __class__(self):
            b.HITS["getattribute"] += 1
            return type(h.preview_graph().items[0].plan)

    closed("preview", lambda g: b.poke(g.items[0], plan=Liar()), "liar")


# ---- D-28: approved properties (section 9.3.1 dependency graphs)


def counting(monkeypatch, cls, name):
    original = cls.__dict__[name]
    reads = []

    def getter(self):
        reads.append(name)
        return original.fget(self)

    monkeypatch.setattr(cls, name, property(getter))
    return reads


APPROVED = [
    (ItemPreview, "warnings", "preview"), (BatchPreview, "summary", "preview"),
    (BatchExecutionResult, "summary", "execution"), (BatchExecutionResult, "outcome", "execution"),
    (ItemExecution, "retry_kind", "execution"),
]


@pytest.mark.parametrize(("cls", "name", "kind"), APPROVED, ids=["%s.%s" % (a[0].__name__, a[1]) for a in APPROVED])
def test_d28_every_approved_property_is_read_on_a_clean_input(monkeypatch, cls, name, kind):
    """[D-28] non-vacuity: the property-read counter does fire for a valid graph."""
    reads = counting(monkeypatch, cls, name)
    h.BUILD[kind](h.FACTORY[kind]())
    assert reads, "%s.%s was never read" % (cls.__name__, name)


DEPENDENCY_TAMPER = [  # (property, kind, tamper) -- a broken value of the property's own dependency graph
    (ItemPreview, "warnings", "preview", lambda g: b.poke(g.items[0].metadata, status=h.Hostile())),
    (ItemPreview, "warnings", "preview",
     lambda g: b.poke(g.items[0].preflight, artifacts=list(g.items[0].preflight.artifacts))),
    (ItemPreview, "warnings", "preview",
     lambda g: b.poke(g.items[0].preflight.artifacts[0], kind=h.Hostile())),
    (ItemPreview, "warnings", "preview",
     lambda g: b.poke(g.items[0].preflight.artifacts[0], content=h.HostileBytes(b"x"))),
    (ItemPreview, "warnings", "preview", lambda g: b.poke(g.items[0], image_failures=h.HostileTuple())),
    (BatchPreview, "summary", "preview", lambda g: b.poke(g.items[1], state=h.Hostile())),
    (BatchPreview, "summary", "preview", lambda g: b.poke(g, items=list(g.items))),
    (ItemExecution, "retry_kind", "execution", lambda g: b.poke(g.items[0], disposition=h.Hostile())),
    (ItemExecution, "retry_kind", "execution", lambda g: b.poke(g.items[1].execution, status=h.Hostile())),
    (ItemExecution, "retry_kind", "execution", lambda g: b.poke(g.items[7], issue=None)),
    (ItemExecution, "retry_kind", "execution", lambda g: b.poke(g.items[1], execution=None)),
    (BatchExecutionResult, "summary", "execution", lambda g: b.poke(g.items[2], preview_state=h.Hostile())),
    (BatchExecutionResult, "outcome", "execution", lambda g: b.poke(g, items=list(g.items))),
    (BatchExecutionResult, "summary", "execution", lambda g: b.poke(g.items[1].execution, status=h.Hostile())),
]


@pytest.mark.parametrize(("cls", "name", "kind", "tamper"), DEPENDENCY_TAMPER,
                         ids=["%s.%s-%d" % (a[0].__name__, a[1], i) for i, a in enumerate(DEPENDENCY_TAMPER)])
def test_d28_a_broken_dependency_graph_fails_closed_before_the_property_is_read(monkeypatch, cls, name, kind, tamper):
    """[D-28] section 9.3.1: the dependency graph is validated locally *before* the property is read."""
    reads = counting(monkeypatch, cls, name)
    graph = h.FACTORY[kind]()
    h.BUILD[kind](graph)
    reads.clear()
    tamper(graph)
    h.assert_fail_closed(h.BUILD[kind], graph, "%s.%s" % (cls.__name__, name))
    assert reads == [], "%s.%s was read from a broken dependency graph" % (cls.__name__, name)


def test_d28_retry_kind_is_checked_against_the_locally_derived_kind_before_summary(monkeypatch):
    """[D-28] section 24.2 step 7: per-item ``retry_kind`` consistency precedes ``summary`` / ``outcome``."""
    order = []
    for cls, name in ((ItemExecution, "retry_kind"), (BatchExecutionResult, "summary"),
                      (BatchExecutionResult, "outcome")):
        original = cls.__dict__[name]

        def getter(self, original=original, name=name):
            order.append(name)
            return original.fget(self)

        monkeypatch.setattr(cls, name, property(getter))
    h.BUILD["execution"](h.execution_graph())
    first_derived = min(order.index("summary"), order.index("outcome"))
    # every item's own ``retry_kind`` was read (and compared) before the first batch-level property read; the
    # later ``retry_kind`` reads are the P4-C8 ``summary`` implementation's own
    assert order[:first_derived].count("retry_kind") >= 8 and set(order[:first_derived]) == {"retry_kind"}


# ---- D-29 .. D-31


def test_d29_isfinite_is_only_applied_to_floats():
    """[D-29] see test_diagnostics_numeric_totality (tripwire); a huge int is accepted without ``OverflowError``."""
    graph = h.preview_graph()
    b.poke(graph.metadata_batch.items[0], elapsed_ms=10**400)
    h.BUILD["preview"](graph)


def test_d30_the_number_validator_only_receives_exact_str():
    """[D-30] ``is_valid_fc2_number``: a ``str`` subclass number is rejected without its hooks running."""
    closed("preview", lambda g: b.poke(g.items[0], canonical_number=b.EvilStr(b.NUMBER)), "evil number")
    closed("preview", lambda g: b.poke(g.metadata_batch.items[0], number=b.EvilStr(b.NUMBER)), "evil item number")


def test_d31_sums_and_budget_comparisons_only_receive_exact_ints():
    """[D-31] counters / sizes that feed ``sum`` and the retained-byte budget comparison: a hostile int is rejected
    before any arithmetic."""
    closed("preview", lambda g: b.poke(g, batch_size=h.HostileInt(2)), "hostile batch_size")
    closed("preview", lambda g: b.poke(g, retention_budget_bytes=h.HostileInt(1000)), "hostile budget")
    closed("execution", lambda g: b.poke(g, retention_budget_bytes=h.HostileInt(1000)), "hostile budget")
    closed("execution", lambda g: b.poke(g.items[1].execution, new_effect_count=h.HostileInt(3)), "hostile count")


# ---- NOT USED rows: D-06, D-20, D-21, D-22


def production_trees():
    return {path.name: ast.parse(path.read_text(encoding="utf-8")) for path in sorted(PRODUCTION.glob("*.py"))}


def calls(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            yield node


def test_d06_len_is_never_applied_to_the_field_sources_proxy():
    """[D-06] NOT USED: AST -- no ``len(<proxy>)`` and no two-step "len then iterate" in the key scan."""
    tree = production_trees()["validation.py"]
    scan = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "scan_field_sources")
    for call in calls(scan):
        if isinstance(call.func, ast.Name) and call.func.id == "len":
            argument = call.args[0]
            assert not (isinstance(argument, ast.Name) and argument.id == "proxy")
            assert not (isinstance(argument, ast.Attribute) and argument.attr == "field_sources")


@pytest.mark.parametrize("name", ["sorted", "min", "max"])
def test_d20_no_sorting_or_extremum_anywhere(name):
    """[D-20] NOT USED: AST -- ``sorted`` / ``min`` / ``max`` are never called; ``.sort`` neither."""
    for module, tree in production_trees().items():
        for call in calls(tree):
            assert not (isinstance(call.func, ast.Name) and call.func.id == name), module
            assert not (isinstance(call.func, ast.Attribute) and call.func.attr in ("sort", name)), module


def test_d21_no_truthiness_test_of_a_caller_originated_object_runs_a_hook():
    """[D-21] NOT USED: sentinel -- hostile ``__bool__`` / ``__len__`` objects planted in every kind of position never
    run (see test_diagnostics_malicious_subclass for the full catalog); here the explicit statement."""
    closed("preview", lambda g: h.plant_object(g, ("items", 0)), "hostile item")
    closed("preview", lambda g: b.poke(g.items[0], issue=h.Hostile()), "hostile issue")
    closed("preview", lambda g: b.poke(g.items[0], media_item=h.Hostile()), "hostile media_item")
    closed("execution", lambda g: b.poke(g.items[1], retry_material=h.Hostile()), "hostile retry_material")


def test_d22_no_text_conversion_of_caller_values_ast_and_sentinel():
    """[D-22] NOT USED: AST -- the validating / projecting modules never call ``str`` / ``repr`` / ``format`` /
    ``ascii`` / ``print`` and contain no f-string / ``%`` formatting / ``.format``; sentinel -- the hostile
    ``__str__`` / ``__repr__`` / ``__format__`` hooks never run (every ``closed`` test above)."""
    for module in ("validation.py", "projection.py", "build.py"):
        tree = production_trees()[module]
        for call in calls(tree):
            if isinstance(call.func, ast.Name):
                assert call.func.id not in ("str", "repr", "format", "ascii", "print"), module
            if isinstance(call.func, ast.Attribute):
                assert call.func.attr != "format", module
        for node in ast.walk(tree):
            assert not isinstance(node, ast.JoinedStr), module
            if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mod):
                assert not (isinstance(node.left, ast.Constant) and isinstance(node.left.value, str)), module


# ---- Phase V -> Phase R non-vacuity (V-2)


def test_phase_v_to_phase_r_a_hostile_member_is_rejected_before_any_membership_test():
    """[D-11] ``contributing_source_ids = ("src_a", EvilSID("src_c"))``: rejected, ``__eq__`` sentinel zero."""
    def plant(graph):
        aggregation = graph.metadata_batch.items[0].aggregation_result
        b.poke(aggregation, contributing_source_ids=("src_a", b.EvilStr("src_c")))

    graph = h.preview_graph()
    plant(graph)
    exc, hits = h.run_hostile(h.BUILD["preview"], graph)
    assert type(exc) is DiagnosticsIntegrityError and hits["eq"] == 0 and hits["hash"] == 0


def test_phase_v_to_phase_r_the_harness_does_detect_a_membership_test_that_precedes_phase_v(monkeypatch):
    """Mutation: a ``check_aggregation`` that probes membership *before* Phase V completed makes the sentinel fire,
    so the test above is not vacuous."""
    real = validation.check_aggregation

    def membership_first(aggregation):
        probe = aggregation.source_results[1].source_id
        _ = probe in aggregation.contributing_source_ids  # Phase R before Phase V
        return real(aggregation)

    monkeypatch.setattr(validation, "check_aggregation", membership_first)
    graph = h.preview_graph()
    aggregation = graph.metadata_batch.items[0].aggregation_result
    b.poke(aggregation, contributing_source_ids=("src_a", b.EvilStr("src_c")))
    exc, hits = h.run_hostile(h.BUILD["preview"], graph)
    assert hits["eq"] > 0 or not isinstance(exc, DiagnosticsIntegrityError)


def test_phase_v_to_phase_r_the_hostile_element_may_sit_anywhere_in_the_container():
    for position in (0, 1, 2):
        def plant(graph, position=position):
            aggregation = graph.metadata_batch.items[0].aggregation_result
            ids = ["src_a", "src_c", "src_x"]
            ids[position] = b.EvilStr(ids[position])
            b.poke(aggregation, contributing_source_ids=tuple(ids))

        closed("preview", plant, "position %d" % position)


# ---- horizontal audit: every H-row has a sentinel scenario somewhere; this file checks the [D-xx] tag coverage

REQUIRED = [1, 2, 3, 4, 5, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 23, 24, 25, 26, 27, 28, 29, 30, 31]
NOT_USED = [6, 20, 21, 22]


def test_every_dispatch_matrix_row_has_a_tagged_test():
    source = pathlib.Path(__file__).read_text(encoding="utf-8")
    tags = {int(match) for match in re.findall(r'"""\[D-(\d\d)\]', source)}
    assert set(REQUIRED + NOT_USED) <= tags, sorted(set(REQUIRED + NOT_USED) - tags)
    assert not (set(REQUIRED) | set(NOT_USED)) - set(range(1, 32)) - {22, 6, 20, 21}
