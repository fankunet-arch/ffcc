"""C1 review LOW-1: AggregationResult cannot be built self-contradictory (C2 hardening).

The reviewer built ``AggregationResult(status=FAILED, metadata=None,
contributing_source_ids=(), source_results=(<a SUCCESS result>,))`` successfully,
although FAILED is defined as "no source produced usable data". These tests build
every kind of contradictory object directly, bypassing ``merge_source_results``.
"""

from __future__ import annotations

import pytest

from fc2_metadata_core.aggregation import (
    AggregateStatus,
    AggregationContractError,
    AggregationResult,
    FieldConflict,
    SourceAttempt,
    SourceExecutionTrace,
)
import fc2_metadata_core.aggregation.models as models_module
from fc2_metadata_core.models.metadata import NormalizedMetadata
from fc2_metadata_core.models.source_result import SourceErrorKind, SourceStatus

from support.scripted_adapters import failed, ok

N = "FC2-4979299"
A_OK = ok("a", N, "T")
B_OK = ok("b", N, "T2")
C_NF = failed("c", SourceStatus.NOT_FOUND)
D_NET = failed("d", SourceStatus.NETWORK_ERROR)


def md(title="T"):
    return NormalizedMetadata(number=N, title=title)


def build(**kwargs):
    base = dict(
        number=N, status=AggregateStatus.SUCCESS, metadata=md(),
        source_results=(A_OK, C_NF), contributing_source_ids=("a",),
    )
    base.update(kwargs)
    return AggregationResult(**base)


# ---- the reviewer's exact reproduction ------------------------------------------------------------------


def test_the_reviewers_failed_result_with_a_success_source_is_rejected():
    with pytest.raises(AggregationContractError):
        AggregationResult(
            number=N, status=AggregateStatus.FAILED, metadata=None,
            contributing_source_ids=(), source_results=(A_OK,),
        )


# ---- contributors == SUCCESS results, exactly ------------------------------------------------------------


def test_a_success_source_can_never_be_silently_left_out_of_the_contributors():
    with pytest.raises(AggregationContractError):
        build(source_results=(A_OK, B_OK), contributing_source_ids=("a",))  # b succeeded but is missing
    with pytest.raises(AggregationContractError):
        build(source_results=(A_OK, B_OK), contributing_source_ids=())


def test_contributors_must_be_exactly_the_successful_sources_in_source_results_order():
    ok_pair = build(source_results=(A_OK, B_OK), contributing_source_ids=("a", "b"))
    assert ok_pair.successful_source_ids == ("a", "b") == ok_pair.contributing_source_ids
    with pytest.raises(AggregationContractError):
        build(source_results=(A_OK, B_OK), contributing_source_ids=("b", "a"))  # wrong order
    with pytest.raises(AggregationContractError):
        build(source_results=(A_OK, C_NF), contributing_source_ids=("a", "c"))  # c did not succeed
    with pytest.raises(AggregationContractError):
        build(source_results=(A_OK, C_NF), contributing_source_ids=("a", "a"))  # duplicate


def test_a_non_contributing_id_or_a_ghost_is_rejected():
    with pytest.raises(AggregationContractError):
        build(contributing_source_ids=("ghost",))
    with pytest.raises(AggregationContractError):
        build(contributing_source_ids=["a"])  # type: ignore[arg-type]  # a list, not a tuple


def test_failed_needs_no_metadata_no_contributors_and_no_success_result():
    AggregationResult(N, AggregateStatus.FAILED, None, (C_NF, D_NET))
    with pytest.raises(AggregationContractError):
        AggregationResult(N, AggregateStatus.FAILED, md(), (C_NF,))  # metadata
    with pytest.raises(AggregationContractError):
        AggregationResult(N, AggregateStatus.FAILED, None, (C_NF,), ("c",))  # contributor
    with pytest.raises(AggregationContractError):
        AggregationResult(N, AggregateStatus.FAILED, None, (C_NF, A_OK))  # a SUCCESS result


def test_success_and_partial_need_a_success_source_and_matching_operational_failure():
    with pytest.raises(AggregationContractError):
        AggregationResult(N, AggregateStatus.SUCCESS, md(), (C_NF,), ())  # no success source
    with pytest.raises(AggregationContractError):
        AggregationResult(N, AggregateStatus.SUCCESS, md(), (A_OK, D_NET), ("a",))  # operational failure present
    with pytest.raises(AggregationContractError):
        AggregationResult(N, AggregateStatus.PARTIAL, md(), (A_OK, C_NF), ("a",))  # none present
    AggregationResult(N, AggregateStatus.PARTIAL, md(), (A_OK, D_NET), ("a",))


def test_metadata_must_meet_minimum_success_and_carry_the_requested_number():
    with pytest.raises(AggregationContractError):
        build(metadata=NormalizedMetadata(number=N))  # no title
    with pytest.raises(AggregationContractError):
        build(metadata=NormalizedMetadata(number="FC2-1111111", title="x"))  # wrong number
    with pytest.raises(AggregationContractError):
        build(metadata=None)


# ---- disabled_source_ids ------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "disabled",
    [["z"], {"z"}, "z", ("z", "z"), ("",), ("  ",), (5,), (None,), ("a",), ("c", "z")],
    ids=lambda d: repr(d),
)
def test_bad_disabled_source_ids_are_rejected(disabled):
    with pytest.raises(AggregationContractError):
        build(disabled_source_ids=disabled)  # type: ignore[arg-type]


def test_good_disabled_source_ids_are_accepted_and_may_not_overlap_results():
    assert build(disabled_source_ids=("x", "y")).disabled_source_ids == ("x", "y")
    assert build(disabled_source_ids=()).disabled_source_ids == ()


# ---- conflicts ------------------------------------------------------------------------------------------------------


def conflict(**kw):
    base = dict(field="title", selected_source_id="a", selected_value="T", alternatives=(("b", "T2"),))
    base.update(kw)
    return FieldConflict(**base)


def two_success(**kw):
    return build(source_results=(A_OK, B_OK), contributing_source_ids=("a", "b"), **kw)


def test_a_consistent_conflict_is_accepted():
    result = two_success(conflicts=(conflict(),))
    assert result.conflicts[0].selected_source_id == "a"
    two_success(conflicts=(FieldConflict("external_ids", "a", "v", (("b", "w"),), key="k"),))


@pytest.mark.parametrize("field", ["actors", "tags", "poster_urls", "source_urls", "number", "field_sources", "nonsense", ""])
def test_only_conflict_capable_fields_are_accepted(field):
    with pytest.raises(AggregationContractError):
        conflict(field=field)


def test_scalar_conflicts_must_have_no_key_and_external_ids_conflicts_must_have_one():
    with pytest.raises(AggregationContractError):
        conflict(key="title")
    for bad in (None, "", "  ", 3):
        with pytest.raises(AggregationContractError):
            FieldConflict("external_ids", "a", "v", (("b", "w"),), key=bad)  # type: ignore[arg-type]


def test_a_conflict_may_only_reference_contributing_sources():
    with pytest.raises(AggregationContractError):
        two_success(conflicts=(conflict(selected_source_id="c", alternatives=(("b", "T2"),)),))  # c did not succeed
    with pytest.raises(AggregationContractError):
        two_success(conflicts=(conflict(alternatives=(("ghost", "T2"),)),))
    with pytest.raises(AggregationContractError):
        build(conflicts=(conflict(alternatives=(("c", "T2"),)),))  # c (NOT_FOUND) cannot be an alternative


def test_the_selected_source_cannot_reappear_among_its_alternatives():
    with pytest.raises(AggregationContractError):
        conflict(alternatives=(("a", "other"),))


def test_alternative_source_ids_must_be_distinct():
    with pytest.raises(AggregationContractError):
        conflict(alternatives=(("b", "x"), ("b", "y")))


def test_alternatives_must_be_non_empty_pairs_of_str_and_value():
    for bad in ((), (("b",),), ("b",), (("b", None),), (("", "x"),), (("b", True),), [("b", "x")]):
        with pytest.raises(AggregationContractError):
            conflict(alternatives=bad)  # type: ignore[arg-type]


def test_an_alternative_equal_to_the_selected_value_is_not_a_conflict():
    with pytest.raises(AggregationContractError):
        conflict(alternatives=(("b", "T"),))
    conflict(selected_value=55, alternatives=(("b", 56),), field="runtime")
    conflict(selected_value=55, alternatives=(("b", "55"),), field="runtime")  # different type is different


def test_conflicts_must_be_a_tuple_of_field_conflicts():
    with pytest.raises(AggregationContractError):
        build(conflicts=[conflict()])  # type: ignore[arg-type]
    with pytest.raises(AggregationContractError):
        build(conflicts=("title",))  # type: ignore[arg-type]


# ---- source_execution_traces -----------------------------------------------------------------------------------------


def trace_for(result, **kw):
    attempt = SourceAttempt(1, result.status, result.error_kind, 5.0)
    return SourceExecutionTrace(result.source_id, (attempt,), result, max_attempts=2, **kw)


def test_traces_must_align_one_to_one_in_source_results_order_and_end_in_the_same_result():
    good = build(source_execution_traces=(trace_for(A_OK), trace_for(C_NF)))
    assert good.trace_for("a").attempt_count == 1 and good.trace_for("zzz") is None
    with pytest.raises(AggregationContractError):
        build(source_execution_traces=(trace_for(C_NF), trace_for(A_OK)))  # wrong order
    with pytest.raises(AggregationContractError):
        build(source_execution_traces=(trace_for(A_OK),))  # missing
    with pytest.raises(AggregationContractError):
        build(source_execution_traces=(trace_for(A_OK), trace_for(C_NF), trace_for(D_NET)))  # extra (a disabled/ghost source)
    with pytest.raises(AggregationContractError):
        build(source_execution_traces=(trace_for(A_OK), trace_for(D_NET)))  # final_result differs from source_results[1]
    with pytest.raises(AggregationContractError):
        build(source_execution_traces=[trace_for(A_OK), trace_for(C_NF)])  # type: ignore[arg-type]


def test_a_pure_merge_may_carry_no_traces():
    assert build().source_execution_traces == ()


# ---- basic shape ----------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "kwargs",
    [
        {"number": "FC2-1234567\n"}, {"number": "1234567"}, {"status": "success"}, {"source_results": ()},
        {"source_results": [A_OK]}, {"source_results": (A_OK, A_OK)}, {"elapsed_ms": -1}, {"elapsed_ms": float("nan")},
        {"elapsed_ms": True}, {"elapsed_ms": "1"},
    ],
    ids=lambda k: repr(k)[:50],
)
def test_malformed_results_cannot_be_constructed(kwargs):
    with pytest.raises(AggregationContractError):
        build(**kwargs)


def test_the_documented_scope_of_the_invariants_is_stated_honestly():
    """The claim is narrowed to what is enforced; the docstring lists what is NOT verified."""
    assert "Not** verified" in models_module.__doc__
    assert "What ``AggregationResult.__post_init__`` enforces" in models_module.__doc__
