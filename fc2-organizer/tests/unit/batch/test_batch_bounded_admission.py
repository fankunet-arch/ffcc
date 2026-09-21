"""Bounded admission: live batch work is O(limit), not O(N) (contract §5).

Not a timing test. At a deterministic barrier (``limit`` calls held open by an Event) we count, exactly:

* live asyncio tasks (``asyncio.all_tasks()``),
* live ``aggregate`` coroutine objects (``gc``): an implementation that builds N coroutines up front and
  hands them to a semaphore would show N even if only ``limit`` of them ever *started*,
* ``engine.calls``: how many items were actually admitted.

A control test runs a deliberately naive "create_task x N + Semaphore" scheduler through the very same
measurement to prove the check can tell the two designs apart.
"""

from __future__ import annotations

import asyncio
import gc
import inspect

import pytest

from fc2_metadata_core.batch import BatchConfig, BatchScheduler
from support.batch_fakes import Gate, ScriptedEngine, agg, numbers, until

BASELINE_TASKS = 2  # the asyncio.run main task + the task running scheduler.run()


def run(coro):
    return asyncio.run(coro)


def live_tasks() -> int:
    return sum(1 for t in asyncio.all_tasks() if not t.done())


def live_aggregate_coroutines() -> int:
    code = ScriptedEngine.aggregate.__code__
    return sum(1 for o in gc.get_objects() if inspect.iscoroutine(o) and o.cr_code is code)


async def measure_at_barrier(schedule, count, limit):
    """Hold ``limit`` calls open, then measure. ``schedule(engine, numbers)`` returns an awaitable."""
    gate = Gate()

    async def behavior(number, seq):
        await gate.wait()
        return agg(number)

    engine = ScriptedEngine(behavior)
    batch = numbers(count)
    task = asyncio.create_task(schedule(engine, batch))
    await until(lambda: engine.active >= min(limit, count))
    for _ in range(50):  # let anything eager get going: a naive scheduler would have started far more by now
        await asyncio.sleep(0)
    gc.collect()
    measured = {
        "tasks": live_tasks(),
        "coroutines": live_aggregate_coroutines(),
        "admitted": len(engine.calls),
        "active": engine.active,
    }
    gate.release.set()
    result = await task
    return measured, engine, result


@pytest.mark.parametrize("limit", [1, 4, 16, 64])
def test_live_tasks_and_coroutines_are_order_of_limit_not_order_of_n(limit):
    count = 3000

    def schedule(engine, batch):
        return BatchScheduler(engine, BatchConfig(max_in_flight_items=limit)).run(batch)

    measured, engine, result = run(measure_at_barrier(schedule, count, limit))
    assert measured["admitted"] == limit, "only `limit` items were admitted at the barrier"
    assert measured["active"] == limit
    assert measured["tasks"] <= limit + BASELINE_TASKS, measured
    assert measured["coroutines"] <= limit, measured
    assert result.total == count and engine.peak == limit


def test_ten_thousand_items_with_limit_four_admit_four_at_the_first_barrier():
    measured, engine, result = run(
        measure_at_barrier(
            lambda e, b: BatchScheduler(e, BatchConfig(max_in_flight_items=4)).run(b), 10_000, 4
        )
    )
    assert measured == {"tasks": 4 + BASELINE_TASKS, "coroutines": 4, "admitted": 4, "active": 4}
    assert result.total == 10_000 and engine.peak == 4
    assert [i.index for i in result.items] == list(range(10_000))


def test_when_there_are_fewer_items_than_the_limit_only_that_many_workers_exist():
    measured, engine, result = run(
        measure_at_barrier(
            lambda e, b: BatchScheduler(e, BatchConfig(max_in_flight_items=64)).run(b), 5, 64
        )
    )
    assert measured["tasks"] == 5 + BASELINE_TASKS
    assert measured["admitted"] == 5


def test_control_a_naive_task_per_item_scheduler_is_visible_to_the_same_measurement():
    """Proof the task measurement discriminates: create_task x N + Semaphore shows ~N live tasks."""
    count, limit = 2000, 4

    async def naive(engine, batch):
        semaphore = asyncio.Semaphore(limit)

        async def one(number):
            async with semaphore:
                return await engine.aggregate(number)

        tasks = [asyncio.create_task(one(n)) for n in batch]
        return await asyncio.gather(*tasks)

    measured, engine, _ = run(measure_at_barrier(naive, count, limit))
    assert engine.peak == limit, "the naive design also honours the limit ..."
    assert measured["admitted"] == limit
    assert measured["tasks"] >= count, "... but it holds N live tasks, which the real scheduler must never do"
    assert measured["tasks"] > 100 * (limit + BASELINE_TASKS)


def test_control_pre_building_n_coroutines_is_visible_to_the_coroutine_measurement():
    """Proof the coroutine measurement discriminates: N unstarted ``aggregate`` coroutines are counted."""
    count, limit = 2000, 4

    async def prebuilt(engine, batch):
        coroutines = [engine.aggregate(n) for n in batch]  # N frames created up front
        semaphore = asyncio.Semaphore(limit)

        async def one(coro):
            async with semaphore:
                return await coro

        try:
            return await asyncio.gather(*(one(c) for c in coroutines))
        finally:
            for c in coroutines:
                c.close()

    measured, engine, _ = run(measure_at_barrier(prebuilt, count, limit))
    assert measured["coroutines"] >= count
    assert measured["coroutines"] > 100 * limit


def test_admission_is_completion_driven_one_new_item_per_freed_slot():
    count, limit = 500, 3

    async def scenario():
        events = [asyncio.Event() for _ in range(count)]  # indexed by the order calls START

        async def behavior(number, seq):
            await events[seq].wait()
            return agg(number)

        engine = ScriptedEngine(behavior)
        sched = BatchScheduler(engine, BatchConfig(max_in_flight_items=limit))
        task = asyncio.create_task(sched.run(numbers(count)))
        await until(lambda: engine.active == limit)
        assert len(engine.calls) == limit
        for step in range(1, 40):
            events[step - 1].set()  # finish exactly one running item
            await until(lambda: len(engine.calls) == limit + step)
            for _ in range(10):
                await asyncio.sleep(0)
            assert len(engine.calls) == limit + step, "exactly one new item per freed slot"
            assert engine.active == limit
        for event in events:
            event.set()
        return engine, await task

    engine, result = run(scenario())
    assert result.total == count and engine.peak == limit
