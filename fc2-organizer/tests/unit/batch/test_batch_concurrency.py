"""Stable ordering and the GLOBAL cross-item concurrency budget (contract §2, §5)."""

from __future__ import annotations

import asyncio

import pytest

from fc2_metadata_core.batch import BatchBusyError, BatchConfig, BatchItemStatus, BatchScheduler
from support.batch_fakes import Gate, ScriptedEngine, agg, numbers, until


def run(coro):
    return asyncio.run(coro)


def scheduler(engine, limit):
    return BatchScheduler(engine, BatchConfig(max_in_flight_items=limit))


# ---- stable ordering --------------------------------------------------------------------------------------------


def test_output_keeps_input_order_even_when_completion_order_is_E_C_A_D_B():
    a, b, c, d, e = numbers(5)
    completion_order = [e, c, a, d, b]
    done = {n: asyncio.Event() for n in completion_order}

    async def behavior(number, seq):
        position = completion_order.index(number)
        if position:
            await done[completion_order[position - 1]].wait()  # forces E, then C, then A, then D, then B
        done[number].set()
        return agg(number, "failed" if number in (c, a) else "success")

    engine = ScriptedEngine(behavior)
    result = run(scheduler(engine, 5).run([a, b, c, d, e]))
    assert engine.completed == [e, c, a, d, b], "the scenario really finished out of order"
    assert [i.number for i in result.items] == [a, b, c, d, e]
    assert [i.index for i in result.items] == [0, 1, 2, 3, 4]
    assert result.failed_indices == (0, 2), "failed subset is in batch order too"
    assert result.failed_numbers == (a, c)


def test_random_looking_completion_order_never_changes_the_output_order():
    batch = numbers(60)

    async def behavior(number, seq):
        for _ in range((seq * 7) % 11):  # deterministic pseudo-random amount of suspension
            await asyncio.sleep(0)
        return agg(number)

    engine = ScriptedEngine(behavior)
    result = run(scheduler(engine, 8).run(batch))
    assert engine.completed != batch, "completion order was shuffled"
    assert [i.number for i in result.items] == batch
    assert [i.index for i in result.items] == list(range(60))


# ---- global concurrency budget ----------------------------------------------------------------------------------


def test_100_inputs_with_limit_3_peak_is_exactly_3_and_never_more():
    seen: list[int] = []

    async def behavior(number, seq):
        seen.append(engine.active)
        for _ in range(3):
            await asyncio.sleep(0)
        return agg(number)

    engine = ScriptedEngine(behavior)
    result = run(scheduler(engine, 3).run(numbers(100)))
    assert engine.peak == 3
    assert max(seen) <= 3
    assert result.total == 100 and engine.active == 0


def test_limit_1_is_strictly_serial_and_in_input_order():
    batch = numbers(25)
    overlap: list[int] = []

    async def behavior(number, seq):
        overlap.append(engine.active)
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        return agg(number)

    engine = ScriptedEngine(behavior)
    run(scheduler(engine, 1).run(batch))
    assert engine.peak == 1
    assert overlap == [1] * 25
    assert engine.calls == batch, "with one slot, execution order is input order"
    assert engine.completed == batch


@pytest.mark.parametrize("count, limit", [(1, 4), (3, 4), (4, 4), (5, 64)])
def test_limit_larger_than_items_peak_is_the_item_count(count, limit):
    gate_holder: dict[str, Gate] = {}

    async def behavior(number, seq):
        await gate_holder["gate"].wait()  # hold every item open so all overlap
        return agg(number)

    async def scenario():
        gate_holder["gate"] = Gate()
        task = asyncio.create_task(scheduler(engine, limit).run(numbers(count)))
        await until(lambda: engine.active == count)
        assert engine.peak == count
        gate_holder["gate"].release.set()
        return await task

    engine = ScriptedEngine(behavior)
    result = run(scenario())
    assert engine.peak == count
    assert result.total == count


@pytest.mark.parametrize("limit", [1, 2, 5, 16, 64])
def test_peak_equals_the_limit_when_there_is_enough_work(limit):
    async def behavior(number, seq):
        for _ in range(4):
            await asyncio.sleep(0)
        return agg(number)

    engine = ScriptedEngine(behavior)
    run(scheduler(engine, limit).run(numbers(limit * 3 + 1)))
    assert engine.peak == limit


def test_a_slot_freed_by_a_finished_item_is_reused_immediately():
    """Work-conserving: a slow item must not idle the other slots (no batch-by-batch lockstep)."""
    batch = numbers(6)
    slow = batch[0]
    gate = {}

    async def behavior(number, seq):
        if number == slow:
            await gate["g"].wait()
        return agg(number)

    async def scenario():
        gate["g"] = Gate()
        task = asyncio.create_task(scheduler(engine, 2).run(batch))
        await until(lambda: len(engine.completed) == 5)  # the other slot drained the other five
        assert engine.completed == batch[1:]
        gate["g"].release.set()
        return await task

    engine = ScriptedEngine(behavior)
    result = run(scenario())
    assert [i.number for i in result.items] == batch
    assert engine.peak == 2


# ---- one active run per scheduler ------------------------------------------------------------------------------


def test_a_second_concurrent_run_on_the_same_scheduler_is_rejected_not_silently_doubled():
    gate = {}

    async def behavior(number, seq):
        await gate["g"].wait()
        return agg(number)

    async def scenario():
        gate["g"] = Gate()
        sched = scheduler(engine, 2)
        first = asyncio.create_task(sched.run(numbers(4)))
        await until(lambda: engine.active == 2)
        with pytest.raises(BatchBusyError):
            await sched.run(numbers(3, start=5_000_001))
        with pytest.raises(BatchBusyError):
            await sched.run([])  # uniform: busy is busy, even for an empty batch
        assert engine.active == 2 and len(engine.calls) == 2, "the rejected runs started nothing"
        gate["g"].release.set()
        await first
        # released afterwards: the scheduler is reusable
        again = await sched.run(numbers(2, start=6_000_001))
        assert again.total == 2
        return engine.peak

    engine = ScriptedEngine(behavior)
    assert run(scenario()) == 2


def test_the_busy_flag_is_released_after_an_ordinary_run_and_an_empty_run():
    engine = ScriptedEngine()
    sched = scheduler(engine, 2)

    async def scenario():
        for _ in range(3):
            assert (await sched.run(numbers(3))).total == 3
            assert (await sched.run([])).total == 0

    run(scenario())


def test_all_results_are_success_in_the_plain_happy_path():
    result = run(scheduler(ScriptedEngine(), 4).run(numbers(30)))
    assert result.success_count == 30 and result.failed_count == 0 and result.partial_count == 0
    assert all(i.status is BatchItemStatus.SUCCESS and i.generation == 0 for i in result.items)
