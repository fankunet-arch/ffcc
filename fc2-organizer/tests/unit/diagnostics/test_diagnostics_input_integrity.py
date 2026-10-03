"""P4-C9 contract sections 8.2 / 9.1 / 24.1 / 24.2 / 24.5: top-level input validation, the builder check order, the
item-count limit before any per-item work, and "a failed diagnostic never changes the input"."""

from __future__ import annotations

import pytest
from fc2_organizer.diagnostics import (
    DiagnosticsError,
    DiagnosticsInputError,
    DiagnosticsIntegrityError,
    DiagnosticsResourceLimitError,
    PathPolicy,
    TimingPolicy,
    build_execution_diagnostics,
    build_preview_diagnostics,
)
from fc2_organizer.execution import ExecutionStatus
from fc2_organizer.orchestration import BatchExecutionResult, BatchPreview, ExecutionDisposition as D

from . import _builders as b


def preview_graph(size: int = 2):
    lineage = b.Lineage(size)
    return lineage.preview([lineage.preview_item(i) for i in range(size)])


def result_graph(size: int = 2):
    lineage = b.Lineage(size)
    return lineage.result([lineage.execution_item(i, D.EXECUTED, status=ExecutionStatus.SUCCESS)
                           for i in range(size)])


BUILDERS = [(build_preview_diagnostics, preview_graph), (build_execution_diagnostics, result_graph)]


@pytest.mark.parametrize(("build", "graph"), BUILDERS)
@pytest.mark.parametrize("bad", [None, 1, "x", object(), (), [], {}, b"x"])
def test_the_top_level_argument_must_be_the_exact_public_type(build, graph, bad):
    with pytest.raises(DiagnosticsInputError):
        build(bad)


def test_a_preview_is_not_accepted_by_the_execution_builder_and_vice_versa():
    with pytest.raises(DiagnosticsInputError):
        build_execution_diagnostics(preview_graph())
    with pytest.raises(DiagnosticsInputError):
        build_preview_diagnostics(result_graph())


def test_a_subclass_of_the_top_level_type_is_rejected():
    class PreviewSub(BatchPreview):
        pass

    class ResultSub(BatchExecutionResult):
        pass

    preview, result = preview_graph(), result_graph()
    with pytest.raises(DiagnosticsInputError):
        build_preview_diagnostics(b.poke_subclass(PreviewSub, preview))
    with pytest.raises(DiagnosticsInputError):
        build_execution_diagnostics(b.poke_subclass(ResultSub, result))


@pytest.mark.parametrize(("build", "graph"), BUILDERS)
@pytest.mark.parametrize("name", ["path_policy", "timing_policy"])
@pytest.mark.parametrize("bad", ["none", "omit", 0, None, True, object()])
def test_policy_arguments_must_be_exact_enum_members(build, graph, name, bad):
    with pytest.raises(DiagnosticsInputError):
        build(graph(), **{name: bad})


@pytest.mark.parametrize(("build", "graph"), BUILDERS)
def test_a_policy_of_the_wrong_enum_is_rejected(build, graph):
    with pytest.raises(DiagnosticsInputError):
        build(graph(), path_policy=TimingPolicy.OMIT)
    with pytest.raises(DiagnosticsInputError):
        build(graph(), timing_policy=PathPolicy.NONE)


@pytest.mark.parametrize(("build", "graph"), BUILDERS)
def test_the_first_argument_is_positional_only_and_the_policies_keyword_only(build, graph):
    with pytest.raises(TypeError):
        build(**{"preview" if build is build_preview_diagnostics else "result": graph()})
    with pytest.raises(TypeError):
        build(graph(), PathPolicy.NONE)


@pytest.mark.parametrize(("build", "graph"), BUILDERS)
def test_items_that_is_not_an_exact_tuple_is_an_integrity_error(build, graph):
    model = graph()
    b.poke(model, items=list(model.items))
    with pytest.raises(DiagnosticsIntegrityError):
        build(model)
    b.poke(model, items="x")
    with pytest.raises(DiagnosticsIntegrityError):
        build(model)


class Sentinel:
    """An element that must never be touched: every attribute access is counted."""

    touched = 0

    def __getattribute__(self, name):
        Sentinel.touched += 1
        return object.__getattribute__(self, name)


@pytest.mark.parametrize(("build", "graph"), BUILDERS)
def test_2001_items_fail_before_any_per_item_work(build, graph):
    model = graph()
    Sentinel.touched = 0
    b.poke(model, items=tuple(Sentinel() for _ in range(2001)))
    with pytest.raises(DiagnosticsResourceLimitError):
        build(model)
    assert Sentinel.touched == 0


@pytest.mark.parametrize(("build", "graph"), BUILDERS)
def test_check_order_reports_the_earliest_violated_step(build, graph):
    """Contract 24.2: top-level type (1) -> policies (2) -> items tuple / limit (3) -> recursive validation (4)."""
    model = graph()
    b.poke(model, items=list(model.items))
    with pytest.raises(DiagnosticsInputError):  # step 2 beats step 3
        build(model, path_policy="none")
    with pytest.raises(DiagnosticsInputError):  # step 1 beats everything
        build(object(), path_policy="none")
    b.poke(model, items=tuple(b.placeholder_items(2001)))
    with pytest.raises(DiagnosticsResourceLimitError):  # step 3 (limit) beats step 4 (the items are not items)
        build(model)


@pytest.mark.parametrize(("build", "graph"), BUILDERS)
def test_every_diagnostics_error_is_a_diagnostics_error(build, graph):
    for bad in (None, 1):
        with pytest.raises(DiagnosticsError):
            build(bad)


@pytest.mark.parametrize(("build", "graph"), BUILDERS)
def test_a_failed_diagnostic_leaves_the_input_graph_unchanged(build, graph):
    model = graph(3)
    b.poke(b.first_item(model), index=7)  # an inconsistent graph: item index 7 in a 3-item batch
    before_fingerprint, before_ids = b.fingerprint(model), b.identities(model)
    with pytest.raises(DiagnosticsIntegrityError):
        build(model)
    assert b.fingerprint(model) == before_fingerprint
    assert b.identities(model) == before_ids


@pytest.mark.parametrize(("build", "graph"), BUILDERS)
def test_a_successful_diagnostic_leaves_the_input_graph_unchanged(build, graph):
    model = graph(3)
    before_fingerprint, before_ids = b.fingerprint(model), b.identities(model)
    build(model)
    build(model, path_policy=PathPolicy.BASENAME, timing_policy=TimingPolicy.INCLUDE)
    assert b.fingerprint(model) == before_fingerprint
    assert b.identities(model) == before_ids


@pytest.mark.parametrize(("build", "graph"), BUILDERS)
def test_error_messages_never_contain_input_text(build, graph):
    model = graph(2)
    b.poke(b.first_item(model), canonical_number="C9CANARY-NUMBER")
    with pytest.raises(DiagnosticsIntegrityError) as caught:
        build(model)
    assert "C9CANARY" not in str(caught.value)
    assert caught.value.__cause__ is None and caught.value.__context__ is None


@pytest.mark.parametrize(("build", "graph"), BUILDERS)
def test_a_diagnostic_does_not_consume_the_input(build, graph):
    """Contract 24.3: diagnosing never registers P4-C8 one-shot consumption (the same object diagnoses twice)."""
    model = graph(2)
    assert build(model) == build(model)
