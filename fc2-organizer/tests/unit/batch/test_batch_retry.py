"""Failed-subset retry, generations and fail-closed merge (contract §8)."""

from __future__ import annotations

import asyncio
import dataclasses

import pytest

from fc2_metadata_core.batch import (
    BatchConfig,
    BatchItemStatus,
    BatchLineage,
    BatchResult,
    BatchRetryError,
    BatchScheduler,
    RetryBatchResult,
    apply_retry,
)
from support.batch_fakes import ScriptedEngine, agg, numbers

S, P, F = BatchItemStatus.SUCCESS, BatchItemStatus.PARTIAL, BatchItemStatus.FAILED


def run(coro):
    return asyncio.run(coro)


class Plan:
    """Outcome per (number, phase). ``phase`` is bumped by the test between rounds."""

    def __init__(self, outcomes):
        self.outcomes = outcomes  # number -> list of outcomes by phase; last one repeats
        self.phase = 0

    async def __call__(self, number, seq):
        await asyncio.sleep(0)
        options = self.outcomes.get(number, ["success"])
        outcome = options[min(self.phase, len(options) - 1)]
        if outcome == "raise":
            raise RuntimeError("SECRET")
        return agg(number, outcome)


def make(outcomes, limit=1):
    plan = Plan(outcomes)
    engine = ScriptedEngine(plan)
    return plan, engine, BatchScheduler(engine, BatchConfig(max_in_flight_items=limit))


# ---- selection --------------------------------------------------------------------------------------------------


def test_only_failed_items_are_retried_success_and_partial_are_not():
    n = numbers(6)
    plan, engine, sched = make(
        {n[1]: ["failed", "success"], n[2]: ["partial"], n[3]: ["raise", "partial"], n[4]: ["deadline"], n[5]: ["failed", "failed"]}
    )
    primary = run(sched.run(n))
    assert [i.status for i in primary.items] == [S, F, P, F, P, F]
    engine.calls.clear()
    plan.phase = 1
    retry = run(sched.retry_failed(primary))
    assert engine.calls == [n[1], n[3], n[5]], "exactly the FAILED items, in batch order"
    assert isinstance(retry, RetryBatchResult)
    assert retry.indices == (1, 3, 5) and retry.generation == 1
    assert [i.status for i in retry.items] == [S, P, F]
    assert retry.total == 3 and retry.success_count == 1 and retry.partial_count == 1 and retry.failed_count == 1
    assert all(i.generation == 1 for i in retry.items)


def test_partial_is_never_retried_by_default_and_there_is_no_partial_switch():
    n = numbers(3)
    _, engine, sched = make({x: ["partial"] for x in n})
    primary = run(sched.run(n))
    engine.calls.clear()
    retry = run(sched.retry_failed(primary))
    assert engine.calls == [] and retry.items == () and retry.generation == 1
    import inspect

    assert list(inspect.signature(BatchScheduler.retry_failed).parameters) == ["self", "previous"]


def test_an_all_success_batch_retries_nothing_but_is_still_a_generation():
    n = numbers(4)
    _, engine, sched = make({})
    primary = run(sched.run(n))
    engine.calls.clear()
    retry = run(sched.retry_failed(primary))
    assert engine.calls == [] and retry.items == () and retry.generation == 1
    merged = apply_retry(primary, retry)
    assert merged.items == primary.items and merged.generation == 1
    assert all(a is b for a, b in zip(merged.items, primary.items))


def test_retry_uses_the_bounded_worker_model_and_keeps_batch_order():
    n = numbers(40)
    plan, engine, sched = make({x: ["raise", "success"] for x in n}, limit=4)
    primary = run(sched.run(n))
    engine.peak = 0
    plan.phase = 1
    retry = run(sched.retry_failed(primary))
    assert engine.peak <= 4
    assert retry.indices == tuple(range(40))
    assert [i.number for i in retry.items] == n


def test_retry_failed_rejects_anything_that_is_not_a_batch_result():
    _, engine, sched = make({})
    for bad in (None, [], (), "x", RetryBatchResult((), generation=1, lineage=BatchLineage.new()), object()):
        with pytest.raises(BatchRetryError):
            run(sched.retry_failed(bad))  # type: ignore[arg-type]
    assert engine.calls == []


# ---- duplicate numbers: identity is the original index -----------------------------------------------------------


def test_duplicate_numbers_retry_by_index_not_by_number():
    x, y = "FC2-1000001", "FC2-1000002"
    seen_by_seq = {0: "success", 1: "failed"}  # primary: index 0 succeeds, index 1 (same number) fails

    async def behavior(number, seq):
        await asyncio.sleep(0)
        if number == x:
            return agg(x, seen_by_seq.get(seq, "success"))
        return agg(number)

    engine = ScriptedEngine(behavior)
    sched = BatchScheduler(engine, BatchConfig(max_in_flight_items=1))
    primary = run(sched.run([x, x, y]))
    assert [(i.index, i.status) for i in primary.items] == [(0, S), (1, F), (2, S)]
    assert primary.failed_indices == (1,) and primary.failed_numbers == (x,)
    engine.calls.clear()
    retry = run(sched.retry_failed(primary))
    assert engine.calls == [x], "the SUCCESS duplicate at index 0 was not re-run"
    assert retry.indices == (1,)
    merged = apply_retry(primary, retry)
    assert [(i.index, i.number, i.status, i.generation) for i in merged.items] == [
        (0, x, S, 0), (1, x, S, 1), (2, y, S, 0)
    ]
    assert merged.items[0] is primary.items[0], "the untouched duplicate is the very same object"


def test_two_failed_duplicates_are_both_retried_as_separate_items():
    x = "FC2-1000001"
    plan, engine, sched = make({x: ["raise", "success"]})
    primary = run(sched.run([x, x, x]))
    assert primary.failed_indices == (0, 1, 2)
    engine.calls.clear()
    plan.phase = 1
    retry = run(sched.retry_failed(primary))
    assert engine.calls == [x, x, x] and retry.indices == (0, 1, 2)


# ---- generation, immutability, merge ------------------------------------------------------------------------------


def test_generation_counts_batch_execution_rounds_and_previous_is_never_mutated():
    n = numbers(5)
    plan, engine, sched = make(
        {n[0]: ["raise", "raise", "success"], n[1]: ["failed", "success"], n[2]: ["success"]}
    )
    primary = run(sched.run(n))
    snapshot = (primary, primary.items)
    assert primary.generation == 0 and {i.generation for i in primary.items} == {0}

    plan.phase = 1
    retry1 = run(sched.retry_failed(primary))
    merged1 = apply_retry(primary, retry1)
    assert retry1.generation == 1 and merged1.generation == 1
    assert primary is snapshot[0] and primary.items is snapshot[1] and primary.generation == 0
    assert [i.generation for i in merged1.items] == [1, 1, 0, 0, 0]
    assert merged1.failed_indices == (0,)

    plan.phase = 2
    retry2 = run(sched.retry_failed(merged1))
    merged2 = apply_retry(merged1, retry2)
    assert retry2.generation == 2 and retry2.indices == (0,) and merged2.generation == 2
    assert [i.generation for i in merged2.items] == [2, 1, 0, 0, 0]
    assert merged2.failed_count == 0
    # every earlier result is untouched
    assert merged1.generation == 1 and merged1.items[0].status is F
    assert primary.items[0].status is F and primary.items[1].status is F


def test_merge_replaces_only_the_retried_items_and_keeps_original_order():
    n = numbers(6)
    plan, engine, sched = make({n[1]: ["failed", "success"], n[4]: ["raise", "partial"]})
    primary = run(sched.run(n))
    plan.phase = 1
    retry = run(sched.retry_failed(primary))
    merged = apply_retry(primary, retry)
    assert [i.index for i in merged.items] == list(range(6))
    assert [i.number for i in merged.items] == n
    for index in (0, 2, 3, 5):
        assert merged.items[index] is primary.items[index]
    assert merged.items[1] is retry.items[0] and merged.items[4] is retry.items[1]
    assert [i.status for i in merged.items] == [S, S, S, S, P, S]
    assert isinstance(merged, BatchResult) and merged is not primary


# ---- apply_retry fails closed --------------------------------------------------------------------------------------


def base_case():
    n = numbers(4)
    plan, engine, sched = make({n[1]: ["failed", "success"], n[3]: ["raise", "success"]})
    primary = run(sched.run(n))
    plan.phase = 1
    retry = run(sched.retry_failed(primary))
    return n, primary, retry


def test_apply_retry_happy_path_baseline():
    _, primary, retry = base_case()
    merged = apply_retry(primary, retry)
    assert merged.success_count == 4 and merged.generation == 1


def test_apply_retry_rejects_wrong_types():
    _, primary, retry = base_case()
    for bad_prev, bad_retry in ((None, retry), (primary, None), (retry, retry), (primary, primary), ([], [])):
        with pytest.raises(BatchRetryError):
            apply_retry(bad_prev, bad_retry)  # type: ignore[arg-type]


@pytest.mark.parametrize("generation", [2, 3, 5])
def test_apply_retry_rejects_a_stale_or_future_generation(generation):
    _, primary, retry = base_case()
    wrong = RetryBatchResult(
        tuple(dataclasses.replace(i, generation=generation) for i in retry.items),
        generation=generation,
        lineage=retry.lineage,
    )
    with pytest.raises(BatchRetryError):
        apply_retry(primary, wrong)


def test_replaying_the_same_retry_twice_is_rejected():
    _, primary, retry = base_case()
    merged = apply_retry(primary, retry)
    with pytest.raises(BatchRetryError):
        apply_retry(merged, retry)  # generation 1 again, but merged is already generation 1
    assert merged.generation == 1 and merged.success_count == 4


def test_apply_retry_rejects_a_retry_that_misses_a_failed_item():
    _, primary, retry = base_case()
    partial_retry = RetryBatchResult(retry.items[:1], generation=1, lineage=retry.lineage)
    with pytest.raises(BatchRetryError):
        apply_retry(primary, partial_retry)


def test_apply_retry_rejects_an_extra_index_that_was_not_failed():
    n, primary, retry = base_case()
    extra = dataclasses.replace(primary.items[0], generation=1)  # index 0 was SUCCESS, never retried
    forged = RetryBatchResult((extra,) + retry.items, generation=1, lineage=retry.lineage)
    with pytest.raises(BatchRetryError):
        apply_retry(primary, forged)


def test_apply_retry_rejects_an_index_outside_the_batch():
    _, primary, retry = base_case()
    outside = dataclasses.replace(retry.items[0], index=99)
    with pytest.raises(BatchRetryError):
        apply_retry(primary, RetryBatchResult((retry.items[0], outside), generation=1, lineage=retry.lineage))


def test_apply_retry_rejects_a_number_mismatch_at_an_index():
    _, primary, retry = base_case()
    wrong_number = "FC2-7777777"
    swapped = dataclasses.replace(retry.items[0], number=wrong_number, aggregation_result=agg(wrong_number))
    with pytest.raises(BatchRetryError):
        apply_retry(primary, RetryBatchResult((swapped,) + retry.items[1:], generation=1, lineage=retry.lineage))


def test_a_retry_from_one_batch_cannot_be_applied_to_a_different_batch():
    _, primary_a, retry_a = base_case()
    other = numbers(4, start=3_000_001)
    plan, engine, sched = make({other[1]: ["failed", "success"], other[3]: ["raise", "success"]})
    primary_b = run(sched.run(other))
    with pytest.raises(BatchRetryError):
        apply_retry(primary_b, retry_a)


def test_apply_retry_failure_leaves_previous_untouched():
    _, primary, retry = base_case()
    before = primary.items
    with pytest.raises(BatchRetryError):
        apply_retry(primary, RetryBatchResult(retry.items[:1], generation=1, lineage=retry.lineage))
    assert primary.items is before and primary.generation == 0


# ---- retry and fatal / cancellation ---------------------------------------------------------------------------------


def test_a_fatal_during_retry_propagates_and_no_result_is_produced():
    n = numbers(6)
    plan, engine, sched = make({x: ["raise", "success"] for x in n})
    primary = run(sched.run(n))
    boom = KeyboardInterrupt()

    async def fatal(number, seq):
        raise boom

    engine._behavior = fatal
    engine.calls.clear()

    async def scenario():
        try:
            await sched.retry_failed(primary)
        except BaseException as exc:  # noqa: BLE001
            return exc

    caught = run(scenario())
    assert caught is boom
    assert engine.calls == [n[0]], "admission stopped at the first fatal"
    assert primary.failed_count == 6, "the previous result is unchanged"
