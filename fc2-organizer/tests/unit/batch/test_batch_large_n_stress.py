"""Large-N stress: the architecture never holds N live tasks (contract §5).

Not a benchmark and no wall-clock assertion: every check is a count (tasks alive, calls active) taken *inside*
the engine on every call, so it is machine-speed independent. The deterministic barrier version of this proof
(``test_batch_bounded_admission.py``) holds ``limit`` items open and measures tasks and coroutines.
"""

from __future__ import annotations

import asyncio

import pytest

from fc2_metadata_core.batch import BatchConfig, BatchItemStatus, BatchScheduler, apply_retry
from support.batch_fakes import ScriptedEngine, agg, numbers

S, P, F = BatchItemStatus.SUCCESS, BatchItemStatus.PARTIAL, BatchItemStatus.FAILED
START = 1_000_001


def position(number: str) -> int:
    return int(number[4:]) - START


def kind_of(k: int, healed: bool) -> str:
    if healed:
        return "success"
    if k % 7 == 0:
        return "raise"
    if k % 11 == 0:
        return "failed"
    if k % 5 == 0:
        return "partial"
    return "success"


EXPECT = {"success": S, "partial": P, "failed": F, "raise": F}


@pytest.mark.parametrize("count, limit", [(10_000, 4), (5_000, 1), (5_000, 64)])
def test_large_batches_stay_bounded_ordered_and_complete(count, limit):
    batch = numbers(count, start=START)
    state = {"healed": False}
    task_samples: list[int] = []

    async def behavior(number, seq):
        # taken from INSIDE the engine call, i.e. at the exact moment `active` calls exist
        task_samples.append(sum(1 for t in asyncio.all_tasks() if not t.done()))
        if seq % 3 == 0:  # some items suspend, some finish without ever yielding
            await asyncio.sleep(0)
        kind = kind_of(position(number), state["healed"])
        if kind == "raise":
            raise RuntimeError("SECRET")
        return agg(number, kind)

    engine = ScriptedEngine(behavior)
    sched = BatchScheduler(engine, BatchConfig(max_in_flight_items=limit))

    async def scenario():
        primary = await sched.run(batch)
        primary_peak, primary_tasks = engine.peak, max(task_samples)
        calls = len(engine.calls)
        state["healed"] = True
        engine.calls.clear()
        engine.peak = 0
        task_samples.clear()
        retry = await sched.retry_failed(primary)
        merged = apply_retry(primary, retry)
        return primary, primary_peak, primary_tasks, calls, retry, merged, engine.peak, max(task_samples or [0])

    primary, primary_peak, primary_tasks, calls, retry, merged, retry_peak, retry_tasks = asyncio.run(scenario())

    # bounded admission: the caller's task + at most `limit` workers, at every one of `count` samples
    assert primary_tasks <= limit + 1, f"{primary_tasks} live tasks for limit={limit}, N={count}"
    assert primary_peak == limit if count >= limit else primary_peak == count
    assert retry_peak <= limit and retry_tasks <= limit + 1

    # complete, ordered, exactly once
    assert calls == count and primary.total == count
    assert [i.index for i in primary.items] == list(range(count))
    assert [i.number for i in primary.items] == batch
    assert [i.status for i in primary.items] == [EXPECT[kind_of(k, False)] for k in range(count)]
    assert engine.active == 0

    # failed-subset retry over N items: only FAILED were re-run
    failed = tuple(k for k in range(count) if EXPECT[kind_of(k, False)] is F)
    assert primary.failed_indices == failed and retry.indices == failed
    assert merged.total == count and merged.failed_count == 0 and merged.generation == 1
    assert merged.success_count + merged.partial_count == count
