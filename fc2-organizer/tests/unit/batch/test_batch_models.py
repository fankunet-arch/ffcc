"""Immutable batch result models and their invariants (contract §6)."""

from __future__ import annotations

import dataclasses

import pytest

from fc2_metadata_core.batch import (
    BatchContractError,
    BatchItemErrorKind,
    BatchItemResult,
    BatchItemStatus,
    BatchLineage,
    BatchResult,
    RetryBatchResult,
)
from support.batch_fakes import agg

N1, N2, N3 = "FC2-1000001", "FC2-1000002", "FC2-1000003"
LINEAGE = BatchLineage.new()
S, P, F = BatchItemStatus.SUCCESS, BatchItemStatus.PARTIAL, BatchItemStatus.FAILED


def item(index=0, number=N1, kind="success", generation=0, elapsed_ms=1.0):
    result = agg(number, kind)
    status = {"success": S, "partial": P, "deadline": P, "failed": F}[kind]
    return BatchItemResult(index, number, status, result, None, None, generation, elapsed_ms)


def errored(index=0, number=N1, generation=0, kind=BatchItemErrorKind.ENGINE_EXCEPTION, type_name="RuntimeError"):
    return BatchItemResult(index, number, F, None, kind, type_name, generation, 0.5)


# ---- BatchItemResult invariants ---------------------------------------------------------------------------------


def test_valid_items_construct():
    assert item(kind="success").status is S
    assert item(kind="partial").status is P
    assert item(kind="failed").status is F
    assert errored().aggregation_result is None


@pytest.mark.parametrize(
    "kwargs",
    [
        dict(index=-1),
        dict(index=True),
        dict(index=1.0),
        dict(index="0"),
        dict(number="FC2-12"),
        dict(number=None),
        dict(status="success"),
        dict(generation=-1),
        dict(generation=True),
        dict(generation=1.5),
        dict(elapsed_ms=-0.1),
        dict(elapsed_ms=float("nan")),
        dict(elapsed_ms=float("inf")),
        dict(elapsed_ms=True),
        dict(elapsed_ms="1"),
    ],
    ids=lambda k: next(iter(k)) + "=" + repr(next(iter(k.values()))),
)
def test_scalar_field_validation(kwargs):
    base = dict(
        index=0, number=N1, status=S, aggregation_result=agg(N1), error_kind=None, error_type=None,
        generation=0, elapsed_ms=1.0,
    )
    base.update(kwargs)
    with pytest.raises(BatchContractError):
        BatchItemResult(**base)


def test_status_must_be_the_mapping_of_the_aggregation_status():
    for kind, wrong in (("success", P), ("success", F), ("partial", S), ("failed", S), ("failed", P)):
        with pytest.raises(BatchContractError):
            BatchItemResult(0, N1, wrong, agg(N1, kind), None, None, 0, 1.0)


def test_the_aggregation_result_must_be_for_the_same_number():
    with pytest.raises(BatchContractError):
        BatchItemResult(0, N1, S, agg(N2), None, None, 0, 1.0)


def test_aggregation_result_must_be_an_aggregation_result():
    with pytest.raises(BatchContractError):
        BatchItemResult(0, N1, S, "not a result", None, None, 0, 1.0)  # type: ignore[arg-type]


def test_a_result_and_an_error_are_mutually_exclusive_and_one_is_required():
    with pytest.raises(BatchContractError):  # both
        BatchItemResult(0, N1, F, agg(N1, "failed"), BatchItemErrorKind.ENGINE_EXCEPTION, "X", 0, 1.0)
    with pytest.raises(BatchContractError):  # result with a stray error_type
        BatchItemResult(0, N1, S, agg(N1), None, "X", 0, 1.0)
    with pytest.raises(BatchContractError):  # neither
        BatchItemResult(0, N1, F, None, None, None, 0, 1.0)


def test_an_errored_item_is_always_failed_and_has_a_type_name():
    for bad_status in (S, P):
        with pytest.raises(BatchContractError):
            BatchItemResult(0, N1, bad_status, None, BatchItemErrorKind.ENGINE_EXCEPTION, "X", 0, 1.0)
    for bad_kind in ("engine_exception", None, 1):
        with pytest.raises(BatchContractError):
            BatchItemResult(0, N1, F, None, bad_kind, "X", 0, 1.0)  # type: ignore[arg-type]
    for bad_name in (None, "", 5, "x" * 300):
        with pytest.raises(BatchContractError):
            BatchItemResult(0, N1, F, None, BatchItemErrorKind.ENGINE_EXCEPTION, bad_name, 0, 1.0)  # type: ignore[arg-type]


def test_items_are_frozen_and_slotted():
    it = item()
    with pytest.raises(dataclasses.FrozenInstanceError):
        it.status = F  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        it.generation = 5  # type: ignore[misc]
    with pytest.raises((AttributeError, TypeError)):
        it.extra = 1  # type: ignore[attr-defined]


# ---- BatchResult ------------------------------------------------------------------------------------------------


def make_batch():
    return BatchResult(
        (item(0, N1, "success"), item(1, N2, "partial"), errored(2, N3), item(3, N1, "failed"), item(4, N2, "deadline"))
    )


def test_counts_and_failed_views_are_derived_tuples():
    batch = make_batch()
    assert (batch.total, batch.success_count, batch.partial_count, batch.failed_count) == (5, 1, 2, 2)
    assert batch.failed_indices == (2, 3)
    assert batch.failed_numbers == (N3, N1)
    assert [i.index for i in batch.failed_items] == [2, 3]
    for view in (batch.items, batch.failed_indices, batch.failed_numbers, batch.failed_items):
        assert isinstance(view, tuple)
    assert batch.success_count + batch.partial_count + batch.failed_count == batch.total


def test_failed_numbers_keep_duplicates_aligned_with_failed_indices():
    batch = BatchResult((item(0, N1, "failed"), item(1, N1, "success"), item(2, N1, "failed")))
    assert batch.failed_indices == (0, 2)
    assert batch.failed_numbers == (N1, N1)


def test_the_batch_is_frozen_and_items_cannot_be_appended():
    batch = make_batch()
    with pytest.raises(dataclasses.FrozenInstanceError):
        batch.items = ()  # type: ignore[misc]
    with pytest.raises(AttributeError):
        batch.items.append(item())  # type: ignore[attr-defined]
    with pytest.raises((AttributeError, TypeError)):
        batch.total = 3  # type: ignore[misc]


def test_items_must_be_a_tuple_of_items_with_contiguous_indices():
    with pytest.raises(BatchContractError):
        BatchResult([item(0)])  # type: ignore[arg-type]  # a list is mutable
    with pytest.raises(BatchContractError):
        BatchResult((item(0), "x"))  # type: ignore[arg-type]
    with pytest.raises(BatchContractError):
        BatchResult((item(1),))  # does not start at 0
    with pytest.raises(BatchContractError):
        BatchResult((item(0), item(2)))  # gap
    with pytest.raises(BatchContractError):
        BatchResult((item(1), item(0)))  # out of order
    with pytest.raises(BatchContractError):
        BatchResult((item(0), item(0)))  # duplicate index


def test_generation_rules():
    assert BatchResult(()).generation == 0
    assert BatchResult((item(0, generation=1),), generation=1).generation == 1
    assert BatchResult((item(0, generation=0), item(1, generation=2)), generation=2).generation == 2
    for bad in (-1, True, 1.0, "0"):
        with pytest.raises(BatchContractError):
            BatchResult((), generation=bad)  # type: ignore[arg-type]
    with pytest.raises(BatchContractError):  # an item newer than the batch itself
        BatchResult((item(0, generation=2),), generation=1)


# ---- RetryBatchResult -------------------------------------------------------------------------------------------


def test_a_retry_result_is_a_strictly_increasing_subset_of_one_generation():
    retry = RetryBatchResult((item(2, N3, "failed", 1), item(7, N1, "success", 1)), generation=1, lineage=LINEAGE)
    assert retry.total == 2 and retry.success_count == 1 and retry.failed_count == 1
    assert retry.failed_indices == (2,)
    assert retry.indices == (2, 7)
    assert isinstance(retry.items, tuple)
    assert RetryBatchResult((), generation=3, lineage=LINEAGE).total == 0


def test_retry_result_validation():
    with pytest.raises(BatchContractError):
        RetryBatchResult((), generation=0, lineage=LINEAGE)  # generation 0 is the primary run
    with pytest.raises(BatchContractError):  # wrong item generation
        RetryBatchResult((item(2, generation=0),), generation=1, lineage=LINEAGE)
    with pytest.raises(BatchContractError):  # not increasing
        RetryBatchResult((item(3, generation=1), item(2, generation=1)), generation=1, lineage=LINEAGE)
    with pytest.raises(BatchContractError):  # duplicate index
        RetryBatchResult((item(2, generation=1), item(2, generation=1)), generation=1, lineage=LINEAGE)
    with pytest.raises(BatchContractError):  # a list is mutable
        RetryBatchResult([item(2, generation=1)], generation=1, lineage=LINEAGE)  # type: ignore[arg-type]
    with pytest.raises(BatchContractError):
        RetryBatchResult((), generation=True, lineage=LINEAGE)  # type: ignore[arg-type]
    with pytest.raises(dataclasses.FrozenInstanceError):
        RetryBatchResult((), generation=1, lineage=LINEAGE).generation = 2  # type: ignore[misc]


def test_a_retry_needs_a_real_lineage():
    for bad in (None, "0" * 32, object()):
        with pytest.raises(BatchContractError):
            RetryBatchResult((), generation=1, lineage=bad)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        RetryBatchResult((), generation=1)  # type: ignore[call-arg]  # no default: provenance must be explicit


# ---- BatchLineage --------------------------------------------------------------------------------------------------


def test_lineages_are_opaque_immutable_values_and_distinct_per_creation():
    a, b = BatchLineage.new(), BatchLineage.new()
    assert a != b and a == BatchLineage(a.token) and hash(a) == hash(BatchLineage(a.token))
    with pytest.raises(dataclasses.FrozenInstanceError):
        a.token = "0" * 32  # type: ignore[misc]
    for bad in ("", "abc", "G" * 32, "A" * 32, "0" * 31, "0" * 33, None, 5, b"0" * 32):
        with pytest.raises(BatchContractError):
            BatchLineage(bad)  # type: ignore[arg-type]


def test_a_hand_built_batch_gets_its_own_fresh_lineage_and_lineage_is_not_part_of_equality_or_repr():
    one, two = BatchResult((item(0),)), BatchResult((item(0),))
    assert one.lineage != two.lineage
    assert one == two, "value equality is by content; lineage is provenance, not content"
    assert "lineage" not in repr(one)
    with pytest.raises(BatchContractError):
        BatchResult((item(0),), lineage="x")  # type: ignore[arg-type]


def test_an_item_number_must_be_an_exact_str():
    class Sub(str):
        pass

    for bad in (Sub(N1),):
        with pytest.raises(BatchContractError):
            BatchItemResult(0, bad, S, agg(N1), None, None, 0, 1.0)
    with pytest.raises(BatchContractError):
        BatchItemResult(0, N1, F, None, BatchItemErrorKind.ENGINE_EXCEPTION, Sub("X"), 0, 1.0)
