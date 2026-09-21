"""C4 offline stage gate: a deterministic 100-item batch with every outcome kind (contract §9).

NOT a live scrape and NOT the final 500-item acceptance: a scripted engine, no network. It verifies that
100 items are all accounted for exactly once, in input order, under a bounded global peak, that ordinary
failures are isolated, that ``retry_failed`` touches exactly the failed subset, and that nothing is lost,
duplicated or left running.

Plan (by the item's base index ``k`` = position of its first occurrence, ``k % 10``); the last 10 items are
duplicates of earlier numbers and share their number's plan:

    0,1  success                       5  ordinary exception, recovers on retry (-> success)
    2    partial                       6  slow success (many suspensions)
    3    deadline-like partial         7  failed aggregation, recovers on retry (-> partial)
    4    failed aggregation, permanent 8  ordinary exception, permanent
                                       9  contract mismatch (result for another number), recovers (-> success)
"""

from __future__ import annotations

import asyncio
from collections import Counter

import pytest

from fc2_metadata_core.batch import (
    BatchConfig,
    BatchItemErrorKind,
    BatchItemStatus,
    BatchScheduler,
    apply_retry,
)
from support.batch_fakes import ScriptedEngine, agg, numbers

S, P, F = BatchItemStatus.SUCCESS, BatchItemStatus.PARTIAL, BatchItemStatus.FAILED
LIMIT = 6

UNIQUE = numbers(90)
BATCH = UNIQUE + [UNIQUE[i * 9] for i in range(10)]  # 10 duplicates of numbers spread over the batch
BASE = {n: UNIQUE.index(n) for n in UNIQUE}

# category -> (outcome in phase 0, outcome in phase >= 1)
PLAN = {
    0: ("success", "success"),
    1: ("success", "success"),
    2: ("partial", "partial"),
    3: ("deadline", "deadline"),
    4: ("failed", "failed"),
    5: ("raise", "success"),
    6: ("slow", "slow"),
    7: ("failed", "partial"),
    8: ("raise", "raise"),
    9: ("mismatch", "success"),
}
STATUS_OF = {"success": S, "slow": S, "partial": P, "deadline": P, "failed": F, "raise": F, "mismatch": F}


def outcome(number: str, phase: int) -> str:
    return PLAN[BASE[number] % 10][min(phase, 1)]


class State:
    phase = 0


async def behavior(number, seq, *, state):
    kind = outcome(number, state.phase)
    if kind == "slow":
        for _ in range(25):
            await asyncio.sleep(0)
    else:
        for _ in range(seq % 4):
            await asyncio.sleep(0)
    if kind == "raise":
        raise RuntimeError("SECRET-100")
    if kind == "mismatch":
        return agg("FC2-9999999")
    return agg(number, "success" if kind == "slow" else kind)


def expected_status(index: int, phase: int) -> BatchItemStatus:
    return STATUS_OF[outcome(BATCH[index], phase)]


def others():
    return [t for t in asyncio.all_tasks() if t is not asyncio.current_task() and not t.done()]


@pytest.fixture(scope="module")
def gate():
    state = State()
    engine = ScriptedEngine(lambda n, s: behavior(n, s, state=state))
    sched = BatchScheduler(engine, BatchConfig(max_in_flight_items=LIMIT))
    out = {"engine": engine}

    async def scenario():
        out["primary"] = await sched.run(BATCH)
        out["primary_calls"] = list(engine.calls)
        out["primary_peak"] = engine.peak
        out["orphans_1"] = others()

        engine.calls.clear()
        engine.peak = 0
        state.phase = 1
        out["retry1"] = await sched.retry_failed(out["primary"])
        out["retry1_calls"] = list(engine.calls)
        out["merged1"] = apply_retry(out["primary"], out["retry1"])

        engine.calls.clear()
        out["retry2"] = await sched.retry_failed(out["merged1"])
        out["retry2_calls"] = list(engine.calls)
        out["merged2"] = apply_retry(out["merged1"], out["retry2"])
        out["orphans_2"] = others()
        out["active_end"] = engine.active

    asyncio.run(scenario())
    return out


def test_all_100_items_are_accounted_for_exactly_once_in_input_order(gate):
    primary = gate["primary"]
    assert len(BATCH) == 100 and primary.total == 100
    assert [i.index for i in primary.items] == list(range(100))
    assert [i.number for i in primary.items] == BATCH
    assert len({i.index for i in primary.items}) == 100, "zero duplicate results"
    assert primary.success_count + primary.partial_count + primary.failed_count == 100, "zero lost items"
    assert primary.generation == 0 and {i.generation for i in primary.items} == {0}


def test_each_item_status_matches_its_scripted_outcome(gate):
    assert [i.status for i in gate["primary"].items] == [expected_status(k, 0) for k in range(100)]
    expected = Counter(expected_status(k, 0) for k in range(100))
    primary = gate["primary"]
    assert (primary.success_count, primary.partial_count, primary.failed_count) == (
        expected[S], expected[P], expected[F]
    )
    assert expected[S] and expected[P] and expected[F], "the plan really mixes all three outcomes"


def test_every_item_ran_exactly_once_per_occurrence(gate):
    assert Counter(gate["primary_calls"]) == Counter(BATCH)
    assert len(gate["primary_calls"]) == 100


def test_the_global_peak_is_bounded_by_the_limit_and_actually_reached(gate):
    assert gate["primary_peak"] == LIMIT


def test_ordinary_exceptions_and_contract_mismatches_are_isolated_and_recorded_without_secrets(gate):
    primary = gate["primary"]
    raised = [i for i in primary.items if outcome(i.number, 0) == "raise"]
    mismatched = [i for i in primary.items if outcome(i.number, 0) == "mismatch"]
    assert raised and mismatched
    assert all(i.error_kind is BatchItemErrorKind.ENGINE_EXCEPTION and i.error_type == "RuntimeError" for i in raised)
    assert all(i.error_kind is BatchItemErrorKind.RESULT_CONTRACT_MISMATCH for i in mismatched)
    assert "SECRET-100" not in repr(primary)
    others_ok = [i for i in primary.items if outcome(i.number, 0) not in ("raise", "mismatch")]
    assert all(i.error_kind is None and i.aggregation_result is not None for i in others_ok)


def test_the_deadline_like_and_failed_aggregation_results_are_carried_through(gate):
    primary = gate["primary"]
    deadline = [i for i in primary.items if outcome(i.number, 0) == "deadline"]
    failed = [i for i in primary.items if outcome(i.number, 0) == "failed"]
    assert deadline and failed
    assert all(i.status is P and i.aggregation_result is agg(i.number, "deadline") for i in deadline)
    assert all(i.status is F and i.aggregation_result is agg(i.number, "failed") for i in failed)


def test_retry_failed_reruns_exactly_the_failed_subset_in_batch_order(gate):
    primary, retry = gate["primary"], gate["retry1"]
    failed_indices = tuple(k for k in range(100) if expected_status(k, 0) is F)
    assert primary.failed_indices == failed_indices
    assert retry.indices == failed_indices and retry.generation == 1
    assert gate["retry1_calls"] == [BATCH[k] for k in failed_indices], "no SUCCESS/PARTIAL item was re-run"
    assert [i.status for i in retry.items] == [expected_status(k, 1) for k in failed_indices]


def test_merged_result_after_retry_is_complete_ordered_and_marks_generations(gate):
    merged, primary = gate["merged1"], gate["primary"]
    assert [i.index for i in merged.items] == list(range(100)) and merged.total == 100
    assert [i.status for i in merged.items] == [expected_status(k, 1) for k in range(100)]
    retried = set(primary.failed_indices)
    assert [i.generation for i in merged.items] == [1 if k in retried else 0 for k in range(100)]
    for k in range(100):
        if k not in retried:
            assert merged.items[k] is primary.items[k]
    assert merged.generation == 1


def test_a_second_retry_round_only_touches_what_is_still_failed(gate):
    merged1, retry2, merged2 = gate["merged1"], gate["retry2"], gate["merged2"]
    still_failed = tuple(k for k in range(100) if expected_status(k, 1) is F)
    assert merged1.failed_indices == still_failed and retry2.indices == still_failed
    assert gate["retry2_calls"] == [BATCH[k] for k in still_failed]
    assert retry2.generation == 2 and merged2.generation == 2
    assert merged2.failed_indices == still_failed, "the permanent failures stay failed, honestly"
    assert merged2.total == 100


def test_previous_results_are_never_mutated_by_later_rounds(gate):
    assert gate["primary"].generation == 0 and gate["primary"].failed_count == len(
        [k for k in range(100) if expected_status(k, 0) is F]
    )
    assert gate["merged1"].generation == 1


def test_zero_orphan_tasks_and_no_call_left_running(gate):
    assert gate["orphans_1"] == [] and gate["orphans_2"] == [] and gate["active_end"] == 0
