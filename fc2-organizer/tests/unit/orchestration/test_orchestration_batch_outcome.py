"""P4-C8 S1: batch-level ``BatchExecutionResult.outcome`` (contract section 11.5, E0-R1).

Every expectation is the frozen truth table: SUCCESS iff every item is EXECUTED + SUCCESS (the empty
result included); otherwise PARTIAL iff at least one item is EXECUTED + SUCCESS or EXECUTED +
PARTIAL; otherwise FAILED.
"""

from __future__ import annotations

import dataclasses
import itertools

import pytest

from fc2_organizer.execution import ExecutionStatus
from fc2_organizer.orchestration import (
    BatchExecutionResult,
    BatchOutcome,
    ExecutionDisposition as D,
    IssueReason as R,
    PreviewState as S,
    RetryKind,
)

from ._helpers import Lineage, new_id

# category -> how to build one item of it (disposition, status, preview state, reason, kwargs, material)
CATEGORIES = {
    "S": (D.EXECUTED, ExecutionStatus.SUCCESS, S.READY, None, None, None),
    "P": (D.EXECUTED, ExecutionStatus.PARTIAL, S.READY, None, None, True),
    "EXECUTED_FAILED": (D.EXECUTED, ExecutionStatus.FAILED, S.READY, None, None, True),
    "NOT_READY_BLOCKED": (D.NOT_READY, None, S.BLOCKED, R.PREFLIGHT_BLOCKED, None, True),
    "NOT_READY_UNPREPARED": (D.NOT_READY, None, S.UNPREPARED, R.NFO_RENDER_FAILED, {"error_type": "NfoError"},
                             None),
    "NOT_SELECTED": (D.NOT_SELECTED, None, S.READY, None, None, True),
    "CANCELLED": (D.CANCELLED, None, S.READY, None, None, True),
    "REJECTED": (D.REJECTED, None, S.READY, R.EXECUTION_REJECTED, {"error_type": "PreflightIntegrityError"},
                 None),
    "ABORTED": (D.ABORTED, None, S.READY, R.EXECUTION_ABORTED, {"error_type": "RuntimeError"}, None),
}
N_CATEGORIES = [c for c in CATEGORIES if c not in ("S", "P")]


def _item(lineage: Lineage, index: int, category: str, generation: int = 0):
    disposition, status, state, reason, kwargs, material = CATEGORIES[category]
    return lineage.execution_item(index, disposition, status=status, state=state, reason=reason,
                                  issue_kwargs=kwargs, material=material, generation=generation)


def _main(categories: list[str]) -> BatchExecutionResult:
    lineage = Lineage(len(categories))
    return lineage.result([_item(lineage, i, c) for i, c in enumerate(categories)])


def test_outcome_members_are_exactly_the_three():
    assert [m.name for m in BatchOutcome] == ["SUCCESS", "PARTIAL", "FAILED"]
    assert [m.value for m in BatchOutcome] == ["success", "partial", "failed"]


@pytest.mark.parametrize("category, expected", [
    ("S", BatchOutcome.SUCCESS), ("P", BatchOutcome.PARTIAL), *[(c, BatchOutcome.FAILED) for c in N_CATEGORIES]])
def test_each_category_alone(category, expected):
    assert _main([category]).outcome is expected


@pytest.mark.parametrize("category, expected", [
    ("S", BatchOutcome.SUCCESS), ("P", BatchOutcome.PARTIAL), *[(c, BatchOutcome.FAILED) for c in N_CATEGORIES]])
def test_all_items_of_one_category(category, expected):
    assert _main([category] * 3).outcome is expected


def test_empty_main_result_is_success():
    lineage = Lineage(0)
    result = lineage.result([])
    assert result.items == () and result.outcome is BatchOutcome.SUCCESS


def test_empty_retry_round_result_is_success():
    lineage = Lineage(2)
    result = lineage.result([], generation=1, base_result_id=new_id(), retry_scope=frozenset({RetryKind.RESUME}),
                            retry_budget=0)
    assert result.outcome is BatchOutcome.SUCCESS


@pytest.mark.parametrize("other", ["P", *N_CATEGORIES])
def test_success_mixed_with_any_non_success_is_partial(other):
    assert _main(["S", other]).outcome is BatchOutcome.PARTIAL
    assert _main([other, "S", "S"]).outcome is BatchOutcome.PARTIAL


@pytest.mark.parametrize("other", list(CATEGORIES))
def test_partial_mixed_with_every_category_is_partial(other):
    assert _main(["P", other]).outcome is BatchOutcome.PARTIAL
    assert _main([other, other, "P"]).outcome is BatchOutcome.PARTIAL


def test_aborted_mixed_with_success_is_partial_never_success():
    assert _main(["ABORTED", "S"]).outcome is BatchOutcome.PARTIAL
    assert _main(["S"] * 5 + ["ABORTED"]).outcome is BatchOutcome.PARTIAL


@pytest.mark.parametrize("pair", list(itertools.combinations_with_replacement(N_CATEGORIES, 2)))
def test_any_combination_of_no_progress_items_is_failed(pair):
    assert _main(list(pair)).outcome is BatchOutcome.FAILED


def test_all_no_progress_categories_together_are_failed():
    assert _main(N_CATEGORIES).outcome is BatchOutcome.FAILED
    assert _main(N_CATEGORIES + ["P"]).outcome is BatchOutcome.PARTIAL
    assert _main(N_CATEGORIES + ["S"]).outcome is BatchOutcome.PARTIAL


def test_retry_round_outcome_describes_only_its_subset():
    lineage = Lineage(3)
    scope = frozenset({RetryKind.DEFERRED})
    retry_round = lineage.result([_item(lineage, 1, "S", generation=1)], generation=1, base_result_id=new_id(),
                                 retry_scope=scope, retry_budget=10)
    assert not retry_round.is_complete and retry_round.outcome is BatchOutcome.SUCCESS
    failed_round = lineage.result([_item(lineage, 0, "EXECUTED_FAILED", generation=1),
                                   _item(lineage, 2, "CANCELLED", generation=1)], generation=1,
                                  base_result_id=new_id(), retry_scope=scope, retry_budget=10 ** 6)
    assert failed_round.outcome is BatchOutcome.FAILED


def test_merged_result_outcome_describes_the_whole_lineage():
    lineage = Lineage(3)
    merged = lineage.result([_item(lineage, 0, "NOT_READY_UNPREPARED"), _item(lineage, 1, "S", generation=1),
                             _item(lineage, 2, "ABORTED")], generation=1, preview_id=None)
    assert merged.is_complete and merged.base_result_id is None and merged.preview_id is None
    assert merged.outcome is BatchOutcome.PARTIAL
    all_done = lineage.result([_item(lineage, i, "S", generation=i % 2) for i in range(3)], generation=1,
                              preview_id=None)
    assert all_done.outcome is BatchOutcome.SUCCESS
    none_done = lineage.result([_item(lineage, i, "REJECTED", generation=1) for i in range(3)], generation=2,
                               preview_id=None)
    assert none_done.outcome is BatchOutcome.FAILED


def test_main_retry_and_merged_shapes_agree_on_the_same_item_categories():
    for categories, expected in ((["S", "S"], BatchOutcome.SUCCESS), (["S", "CANCELLED"], BatchOutcome.PARTIAL),
                                 (["ABORTED", "REJECTED"], BatchOutcome.FAILED)):
        lineage = Lineage(2)
        main = lineage.result([_item(lineage, i, c) for i, c in enumerate(categories)])
        retry = lineage.result([_item(lineage, i, c, generation=1) for i, c in enumerate(categories)],
                               generation=1, base_result_id=new_id(), retry_scope=frozenset({RetryKind.DEFERRED}),
                               retry_budget=10 ** 6)
        merged = lineage.result([_item(lineage, i, c, generation=1) for i, c in enumerate(categories)],
                                generation=1, preview_id=None)
        assert main.outcome is retry.outcome is merged.outcome is expected


def test_outcome_is_pure_and_repeatable():
    lineage = Lineage(3)
    items = [_item(lineage, 0, "S"), _item(lineage, 1, "P"), _item(lineage, 2, "CANCELLED")]
    first = lineage.result(items)
    second = lineage.result(items)
    assert first.result_id != second.result_id
    assert first.outcome is first.outcome is second.outcome is BatchOutcome.PARTIAL


def test_outcome_is_a_derived_property_never_a_field():
    names = {f.name for f in dataclasses.fields(BatchExecutionResult)}
    assert "outcome" not in names
    assert isinstance(BatchExecutionResult.__dict__["outcome"], property)
    assert BatchExecutionResult.__dict__["outcome"].fset is None
    result = _main(["S"])
    with pytest.raises((AttributeError, TypeError)):
        result.outcome = BatchOutcome.FAILED  # type: ignore[misc]
