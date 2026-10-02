"""P4-C8 S5: ``PreviewSummary`` / ``ExecutionSummary`` (contract sections 11.5, 28) on deterministically enumerated,
model-valid generated batches (no randomness, no property-testing dependency).

Every item category the frozen models allow is built with the ``Lineage`` builders; the expected counts of each
category are stated here independently of the production code (contract section 28.2 definitions), then every
single-category batch and every pair of categories is checked in the main, retry-round and merged shapes.
"""

from __future__ import annotations

import dataclasses
import itertools

import pytest

from fc2_metadata_core.batch import BatchItemErrorKind
from fc2_organizer.execution import CheckpointRejectionReason, ExecutionStatus
from fc2_organizer.orchestration import (
    DEFAULT_MAX_RETAINED_ARTIFACT_BYTES,
    BatchExecutionResult,
    BatchOutcome,
    BatchPreview,
    ExecutionDisposition as D,
    ExecutionSummary,
    IssueReason as R,
    ItemWarning,
    OrchestrationContractError,
    OrchestrationStage,
    PreviewState as S,
    PreviewSummary,
    RetryKind as K,
)

from ._helpers import Lineage, fake_preflight, image_failure, new_id

# --------------------------------------------------------------------------- the frozen category table

# name -> (builder kwargs for Lineage.execution_item, expected counted fields, retry kind, issue stage or None)
_TE = "RuntimeError"
CATEGORIES = {
    "success": (dict(disposition=D.EXECUTED, status=ExecutionStatus.SUCCESS), ("ready", "executed", "success"),
                K.NONE, None),
    "partial": (dict(disposition=D.EXECUTED, status=ExecutionStatus.PARTIAL, material=True),
                ("ready", "executed", "partial", "retryable"), K.RESUME, OrchestrationStage.EXECUTION),
    "failed": (dict(disposition=D.EXECUTED, status=ExecutionStatus.FAILED, material=True),
               ("ready", "executed", "failed", "retryable"), K.FRESH_REEXECUTE, OrchestrationStage.EXECUTION),
    "not_selected": (dict(disposition=D.NOT_SELECTED, material=True), ("ready", "not_selected", "deferred"),
                     K.DEFERRED, None),
    "cancelled": (dict(disposition=D.CANCELLED, material=True), ("ready", "cancelled", "deferred"), K.DEFERRED, None),
    "rejected": (dict(disposition=D.REJECTED, reason=R.EXECUTION_REJECTED, issue_kwargs={"error_type": _TE}),
                 ("ready", "rejected", "non_retryable"), K.NONE, OrchestrationStage.EXECUTION),
    "aborted": (dict(disposition=D.ABORTED, reason=R.EXECUTION_ABORTED, issue_kwargs={"error_type": _TE}),
                ("ready", "aborted", "non_retryable"), K.NONE, OrchestrationStage.EXECUTION),
    "preflight_blocked": (dict(disposition=D.NOT_READY, state=S.BLOCKED, reason=R.PREFLIGHT_BLOCKED, material=True),
                          ("blocked", "retryable"), K.PREFLIGHT_RECHECK, OrchestrationStage.PREFLIGHT),
    "number": (dict(disposition=D.NOT_READY, state=S.UNPREPARED, reason=R.NUMBER_NOT_RECOGNIZED, with_plan=False,
                    with_metadata=False), ("unprepared", "non_retryable"), K.NONE,
               OrchestrationStage.NUMBER_RECOGNITION),
    "metadata_unavailable": (dict(disposition=D.NOT_READY, state=S.UNPREPARED, reason=R.METADATA_UNAVAILABLE,
                                  with_plan=False), ("unprepared", "retryable"), K.METADATA_REFETCH,
                             OrchestrationStage.METADATA),
    "metadata_engine": (dict(disposition=D.NOT_READY, state=S.UNPREPARED, reason=R.METADATA_ENGINE_FAILURE,
                             with_plan=False,
                             issue_kwargs={"error_type": _TE, "detail": BatchItemErrorKind.ENGINE_EXCEPTION}),
                        ("unprepared", "retryable"), K.METADATA_REFETCH, OrchestrationStage.METADATA),
    "planning": (dict(disposition=D.NOT_READY, state=S.UNPREPARED, reason=R.PLANNING_REJECTED, with_plan=False,
                      issue_kwargs={"error_type": _TE}), ("unprepared", "non_retryable"), K.NONE,
                 OrchestrationStage.PLANNING),
    "publication": (dict(disposition=D.NOT_READY, state=S.UNPREPARED, reason=R.PUBLICATION_REJECTED,
                         issue_kwargs={"error_type": _TE}), ("unprepared", "non_retryable"), K.NONE,
                    OrchestrationStage.PUBLICATION),
    "nfo": (dict(disposition=D.NOT_READY, state=S.UNPREPARED, reason=R.NFO_RENDER_FAILED,
                 issue_kwargs={"error_type": _TE}), ("unprepared", "non_retryable"), K.NONE,
            OrchestrationStage.NFO_RENDER),
    "image": (dict(disposition=D.NOT_READY, state=S.UNPREPARED, reason=R.IMAGE_ACQUISITION_ERROR,
                   issue_kwargs={"error_type": _TE}), ("unprepared", "non_retryable"), K.NONE,
              OrchestrationStage.IMAGE_ACQUISITION),
    "manifest": (dict(disposition=D.NOT_READY, state=S.UNPREPARED, reason=R.MANIFEST_REJECTED,
                      issue_kwargs={"error_type": _TE}), ("unprepared", "non_retryable"), K.NONE,
                 OrchestrationStage.MANIFEST),
    "preflight_rejected": (dict(disposition=D.NOT_READY, state=S.UNPREPARED, reason=R.PREFLIGHT_REJECTED,
                                issue_kwargs={"error_type": _TE}), ("unprepared", "non_retryable"), K.NONE,
                           OrchestrationStage.PREFLIGHT),
    "checkpoint_rejected": (dict(disposition=D.NOT_READY, state=S.UNPREPARED, reason=R.CHECKPOINT_REJECTED,
                                 issue_kwargs={"error_type": "CheckpointError",
                                               "detail": CheckpointRejectionReason.CONSUMED}),
                            ("unprepared", "non_retryable"), K.NONE, OrchestrationStage.PREFLIGHT),
}
COUNTS = ("total", "ready", "blocked", "unprepared", "executed", "success", "partial", "failed", "not_selected",
          "cancelled", "rejected", "aborted", "retryable", "deferred", "non_retryable")


def _expected(categories: list[str], duplicates: int = 0) -> dict:
    counts = dict.fromkeys(COUNTS, 0)
    stages = dict.fromkeys(OrchestrationStage, 0)
    for name in categories:
        _, fields, _, stage = CATEGORIES[name]
        counts["total"] += 1
        for field in fields:
            counts[field] += 1
        if stage is not None:
            stages[stage] += 1
    counts["total"] += duplicates
    counts["blocked"] += duplicates
    counts["non_retryable"] += duplicates
    stages[OrchestrationStage.BATCH_CONFLICT] += duplicates
    counts["stage_counts"] = tuple(stages.items())
    return counts


def _items(lin: Lineage, categories: list[str], generation: int = 0) -> list:
    items = []
    for index, name in enumerate(categories):
        kwargs = dict(CATEGORIES[name][0])
        kwargs.setdefault("state", S.READY)
        disposition = kwargs.pop("disposition")
        items.append(lin.execution_item(index, disposition, generation=generation, **kwargs))
    return items


def _duplicates(lin: Lineage, first: int, generation: int = 0) -> list:
    pair = (first, first + 1)
    return [lin.execution_item(i, D.NOT_READY, state=S.BLOCKED, reason=R.DUPLICATE_SOURCE_IN_BATCH,
                               conflict_with=tuple(p for p in pair if p != i), generation=generation) for i in pair]


def _shapes(categories: list[str], duplicates: bool = False):
    """The same items as a main, a retry-round and a merged result."""
    size = len(categories) + (2 if duplicates else 0)
    for shape in ("main", "retry", "merged"):
        lin = Lineage(size)
        generation = 0 if shape == "main" else 1
        items = _items(lin, categories, generation)
        if duplicates:
            items += _duplicates(lin, len(categories), generation)
        if shape == "main":
            yield shape, lin.result(items)
        elif shape == "retry":
            yield shape, lin.result(items, generation=1, base_result_id=new_id(), retry_scope=frozenset({K.RESUME}),
                                    retry_budget=DEFAULT_MAX_RETAINED_ARTIFACT_BYTES)
        else:
            yield shape, lin.result(items, generation=1, preview_id=None)


def _check(result: BatchExecutionResult, expected: dict) -> ExecutionSummary:
    summary = result.summary
    assert type(summary) is ExecutionSummary
    assert {name: getattr(summary, name) for name in COUNTS} | {"stage_counts": summary.stage_counts} == expected
    # contract section 28.2 identities
    t = summary
    assert t.total == len(result.items)
    assert t.total == (t.success + t.partial + t.failed + t.blocked + t.unprepared + t.not_selected + t.cancelled
                       + t.rejected + t.aborted)
    assert t.executed == t.success + t.partial + t.failed
    assert t.ready == t.executed + t.not_selected + t.cancelled + t.rejected + t.aborted
    assert t.total == t.success + t.retryable + t.deferred + t.non_retryable
    assert [stage for stage, _ in t.stage_counts] == list(OrchestrationStage)  # every stage, declaration order
    # contract section 28.4: outcome <-> summary
    outcome = result.outcome
    assert (outcome is BatchOutcome.SUCCESS) == (t.success == t.total)
    assert (outcome is BatchOutcome.PARTIAL) == (t.success + t.partial >= 1 and t.success < t.total)
    assert (outcome is BatchOutcome.FAILED) == (t.total >= 1 and t.success + t.partial == 0)
    assert result.summary == summary and result.summary is not summary  # derived anew, equal every time
    return summary


# --------------------------------------------------------------------------- enumeration


@pytest.mark.parametrize("name", sorted(CATEGORIES))
def test_every_single_category_batch(name):
    for _, result in _shapes([name]):
        _check(result, _expected([name]))
        assert result.items[0].retry_kind is CATEGORIES[name][2]


def test_every_pair_of_categories_in_every_result_shape():
    checked = 0
    for pair in itertools.combinations_with_replacement(sorted(CATEGORIES), 2):
        for _, result in _shapes(list(pair)):
            _check(result, _expected(list(pair)))
            checked += 1
    assert checked == 3 * len(list(itertools.combinations_with_replacement(CATEGORIES, 2)))


def test_a_batch_with_every_category_and_a_conflict_pair():
    every = sorted(CATEGORIES)
    for _, result in _shapes(every, duplicates=True):
        summary = _check(result, _expected(every, duplicates=2))
        assert all(count > 0 for stage, count in summary.stage_counts)  # every stage occurs at least once


def test_an_empty_result_follows_the_frozen_truth_table():
    lin = Lineage(0)
    for result in (lin.result([]), lin.result([], generation=1, preview_id=None),
                   lin.result([], generation=1, base_result_id=new_id(), retry_scope=frozenset(), retry_budget=1)):
        summary = _check(result, _expected([]))
        assert summary.total == 0 and result.outcome is BatchOutcome.SUCCESS
        assert summary.stage_counts == tuple((stage, 0) for stage in OrchestrationStage)


# --------------------------------------------------------------------------- explicit no-silent-loss regressions


def test_partial_is_never_success():
    for _, result in _shapes(["partial", "partial"]):
        summary = result.summary
        assert (summary.success, summary.partial, summary.executed) == (0, 2, 2)
        assert result.outcome is BatchOutcome.PARTIAL  # never SUCCESS while anything is PARTIAL


def test_aborted_is_never_success_failed_or_retryable():
    for _, result in _shapes(["aborted", "success"]):
        summary = result.summary
        assert (summary.aborted, summary.success, summary.failed, summary.retryable) == (1, 1, 0, 0)
        assert summary.non_retryable == 1 and result.outcome is BatchOutcome.PARTIAL
    for _, result in _shapes(["aborted"]):
        assert result.summary.aborted == 1 and result.outcome is BatchOutcome.FAILED


def test_success_comes_only_from_an_executed_p4c7_success():
    for _, result in _shapes(["not_selected", "cancelled", "rejected", "preflight_blocked"]):
        assert result.summary.success == 0 and result.outcome is BatchOutcome.FAILED


# --------------------------------------------------------------------------- PreviewSummary


def _preview_items(lin: Lineage):
    """index 0 READY (no warning), 1 READY with an image candidate failure, 2 READY metadata PARTIAL, 3 BLOCKED,
    4-5 a duplicate pair, then one UNPREPARED item per pre-execution stage."""
    plain = fake_preflight(lin.plans[0], None)
    items = [lin.preview_item(0, preflight=plain),
             lin.preview_item(1, image_failures=(image_failure(),)),
             lin.preview_item(2),
             lin.preview_item(3, state=S.BLOCKED, reason=R.PREFLIGHT_BLOCKED,
                              preflight=fake_preflight(lin.plans[3], ready=False)),
             lin.preview_item(4, state=S.BLOCKED, reason=R.DUPLICATE_TARGET_IN_BATCH, preflight=None,
                              conflict_with=(5,)),
             lin.preview_item(5, state=S.BLOCKED, reason=R.DUPLICATE_TARGET_IN_BATCH, preflight=None,
                              conflict_with=(4,))]
    unprepared = [(R.NUMBER_NOT_RECOGNIZED, dict(with_plan=False, with_metadata=False)),
                  (R.METADATA_UNAVAILABLE, dict(with_plan=False)),
                  (R.PLANNING_REJECTED, dict(with_plan=False, issue_kwargs={"error_type": _TE})),
                  (R.PUBLICATION_REJECTED, dict(issue_kwargs={"error_type": _TE})),
                  (R.NFO_RENDER_FAILED, dict(issue_kwargs={"error_type": _TE})),
                  (R.IMAGE_ACQUISITION_ERROR, dict(issue_kwargs={"error_type": _TE})),
                  (R.MANIFEST_REJECTED, dict(issue_kwargs={"error_type": _TE})),
                  (R.PREFLIGHT_REJECTED, dict(issue_kwargs={"error_type": _TE}))]
    for offset, (reason, kwargs) in enumerate(unprepared):
        items.append(lin.preview_item(6 + offset, state=S.UNPREPARED, reason=reason, preflight=None, **kwargs))
    return items


def test_preview_summary_counts_and_stage_order():
    lin = Lineage(14, kinds={2: "partial"})
    preview = lin.preview(_preview_items(lin))
    summary = preview.summary
    assert type(summary) is PreviewSummary
    assert (summary.total, summary.ready, summary.blocked, summary.unprepared) == (14, 3, 3, 8)
    expected_warned = sum(1 for item in preview.items if item.warnings)
    assert summary.warned == expected_warned
    assert ItemWarning.IMAGE_CANDIDATE_FAILURES in preview.items[1].warnings
    assert ItemWarning.METADATA_PARTIAL in preview.items[2].warnings
    expected_stages = {stage: 0 for stage in OrchestrationStage}
    for stage in (OrchestrationStage.PREFLIGHT, OrchestrationStage.BATCH_CONFLICT, OrchestrationStage.BATCH_CONFLICT,
                  OrchestrationStage.NUMBER_RECOGNITION, OrchestrationStage.METADATA, OrchestrationStage.PLANNING,
                  OrchestrationStage.PUBLICATION, OrchestrationStage.NFO_RENDER, OrchestrationStage.IMAGE_ACQUISITION,
                  OrchestrationStage.MANIFEST, OrchestrationStage.PREFLIGHT):
        expected_stages[stage] += 1
    assert summary.stage_counts == tuple(expected_stages.items())
    assert summary.total == summary.ready + summary.blocked + summary.unprepared
    assert sum(count for _, count in summary.stage_counts) == summary.blocked + summary.unprepared
    assert preview.summary == summary


def test_preview_summary_of_a_retry_preview_and_an_empty_one():
    lin = Lineage(3)
    retry = lin.preview([lin.preview_item(1, generation=1, retry_origin=K.DEFERRED)], generation=1,
                        base_result_id=new_id(), retry_scope=frozenset({K.DEFERRED}),
                        retry_budget=DEFAULT_MAX_RETAINED_ARTIFACT_BYTES)
    assert retry.summary.total == 1 and retry.summary.ready == 1
    empty = Lineage(0).preview([])
    assert empty.summary == PreviewSummary(0, 0, 0, 0, 0, tuple((s, 0) for s in OrchestrationStage))


# --------------------------------------------------------------------------- derived, never stored


def test_summaries_are_derived_properties_not_fields():
    for model in (BatchPreview, BatchExecutionResult):
        assert isinstance(model.__dict__["summary"], property)
        assert "summary" not in {f.name for f in dataclasses.fields(model)}
        assert not {"outcome", "counts", "stage_counts"} & {f.name for f in dataclasses.fields(model)}
    assert "outcome" not in {f.name for f in dataclasses.fields(ExecutionSummary)}
    assert [f.name for f in dataclasses.fields(ExecutionSummary)] == [*COUNTS, "stage_counts"]
    assert [f.name for f in dataclasses.fields(PreviewSummary)] == ["total", "ready", "blocked", "unprepared",
                                                                    "warned", "stage_counts"]


def test_summary_models_validate_their_own_identities():
    stages = tuple((stage, 0) for stage in OrchestrationStage)
    with pytest.raises(OrchestrationContractError):
        PreviewSummary(1, 0, 0, 0, 0, stages)  # total != ready + blocked + unprepared
    with pytest.raises(OrchestrationContractError):
        PreviewSummary(0, 0, 0, 0, 0, stages[:-1])  # a stage missing
    with pytest.raises(OrchestrationContractError):
        PreviewSummary(0, 0, 0, 0, 0, tuple(reversed(stages)))  # wrong order
    with pytest.raises(OrchestrationContractError):
        PreviewSummary(True, 1, 0, 0, 0, stages)  # bool is not an int count
    good = _shapes(["partial"]).__next__()[1].summary
    with pytest.raises(OrchestrationContractError):
        dataclasses.replace(good, success=1, partial=0)  # PARTIAL counted as success breaks the identities
    with pytest.raises(OrchestrationContractError):
        dataclasses.replace(good, stage_counts=tuple(pair for pair in good.stage_counts if pair[1]))  # sparse
