"""Fatal BaseException propagation and caller cancellation (contract §7).

Rules pinned here (consistent with the C1/C2 aggregation contract):

* CancelledError from the *caller* -> propagates unchanged; running items are cancelled AND awaited; items not
  yet admitted never start; no task outlives the call.
* KeyboardInterrupt / SystemExit / GeneratorExit / any custom BaseException from an item -> the ORIGINAL
  exception object reaches the caller (never a group, never a FAILED item), admission stops at once, siblings
  are cancelled and awaited.
* A CancelledError the engine raises on its own (nobody cancelled) also propagates (it is never a FAILED item).
* No partial BatchResult after a fatal exception; the scheduler is reusable afterwards.
"""

from __future__ import annotations

import asyncio

import pytest

from fc2_metadata_core.aggregation import AggregationConfig, MultiSourceEngine, SourceConfig
from fc2_metadata_core.batch import BatchConfig, BatchItemStatus, BatchScheduler
from fc2_metadata_core.sources import SourceRegistry
from support.batch_fakes import Gate, ScriptedEngine, agg, numbers, until
from support.scripted_adapters import ok, scripted_adapter_class


class CustomFatal(BaseException):
    pass


FATALS = [KeyboardInterrupt, SystemExit, GeneratorExit, CustomFatal]


def run(coro):
    return asyncio.run(coro)


def others():
    """Tasks alive other than the one running the current coroutine."""
    return [t for t in asyncio.all_tasks() if t is not asyncio.current_task() and not t.done()]


async def capture(awaitable):
    """Await ``awaitable``; return (exception-or-None, result-or-None, leftover tasks)."""
    caught = value = None
    try:
        value = await awaitable
    except BaseException as exc:  # noqa: BLE001 - the whole point is to observe what escapes
        caught = exc
    await asyncio.sleep(0)
    return caught, value, others()


# ---- fatal BaseException ----------------------------------------------------------------------------------------


@pytest.mark.parametrize("exc_type", FATALS, ids=lambda t: t.__name__)
def test_a_fatal_exception_propagates_as_the_original_object_and_admission_stops_serial(exc_type):
    batch = numbers(10)
    boom = exc_type("fatal-secret")

    async def behavior(number, seq):
        await asyncio.sleep(0)
        if seq == 2:
            raise boom
        return agg(number)

    engine = ScriptedEngine(behavior)

    async def scenario():
        return await capture(BatchScheduler(engine, BatchConfig(max_in_flight_items=1)).run(batch))

    caught, value, leftover = run(scenario())
    assert caught is boom, "the ORIGINAL exception object, not a wrapper"
    assert not isinstance(caught, BaseExceptionGroup)
    assert value is None, "no partial BatchResult"
    assert engine.calls == batch[:3], "no item admitted after the fatal one"
    assert leftover == [] and engine.active == 0


@pytest.mark.parametrize("exc_type", FATALS, ids=lambda t: t.__name__)
def test_a_fatal_exception_cancels_and_awaits_running_siblings_and_admits_nothing_new(exc_type):
    batch = numbers(40)
    boom = exc_type()
    gate = {}

    async def behavior(number, seq):
        if seq == 2:
            await asyncio.sleep(0)
            raise boom
        await gate["g"].wait()  # siblings are blocked when the fatal happens
        return agg(number)

    engine = ScriptedEngine(behavior)

    async def scenario():
        gate["g"] = Gate()
        return await capture(BatchScheduler(engine, BatchConfig(max_in_flight_items=4)).run(batch))

    caught, value, leftover = run(scenario())
    assert caught is boom
    assert engine.calls == batch[:4], "only the initially admitted items were ever started"
    assert sorted(engine.cancelled) == sorted(n for i, n in enumerate(batch[:4]) if i != 2), (
        "the running siblings were cancelled (and their cleanup ran to completion)"
    )
    assert engine.active == 0 and leftover == []


def test_a_fatal_after_some_items_completed_still_returns_no_partial_result():
    batch = numbers(20)

    async def behavior(number, seq):
        if seq == 12:
            raise KeyboardInterrupt
        await asyncio.sleep(0)
        return agg(number)

    async def scenario():
        return await capture(BatchScheduler(ScriptedEngine(behavior), BatchConfig(max_in_flight_items=3)).run(batch))

    caught, value, leftover = run(scenario())
    assert isinstance(caught, KeyboardInterrupt) and value is None and leftover == []


@pytest.mark.parametrize("exc_type", FATALS, ids=lambda t: t.__name__)
def test_a_fatal_is_never_recorded_as_a_failed_item(exc_type):
    async def behavior(number, seq):
        raise exc_type()

    async def scenario():
        return await capture(BatchScheduler(ScriptedEngine(behavior)).run(numbers(5)))

    caught, value, _ = run(scenario())
    assert isinstance(caught, exc_type) and value is None


def test_simultaneous_distinct_fatals_propagate_exactly_one_original_and_no_group():
    """Same rule as C2-L5: one fatal is propagated as the original; the others are not preserved."""
    first, second = KeyboardInterrupt("one"), SystemExit("two")
    excs = [first, second]

    async def behavior(number, seq):
        await asyncio.sleep(0)
        raise excs[seq]

    async def scenario():
        return await capture(BatchScheduler(ScriptedEngine(behavior), BatchConfig(max_in_flight_items=2)).run(numbers(2)))

    caught, value, leftover = run(scenario())
    assert caught is first or caught is second
    assert not isinstance(caught, BaseExceptionGroup) and value is None and leftover == []


@pytest.mark.parametrize(
    "make_boom",
    [KeyboardInterrupt, SystemExit, GeneratorExit, CustomFatal, lambda: asyncio.CancelledError("engine-self")],
    ids=["KeyboardInterrupt", "SystemExit", "GeneratorExit", "CustomFatal", "self-CancelledError"],
)
def test_a_sibling_resuming_in_the_same_loop_iteration_admits_nothing_after_the_fatal(make_boom):
    """Race: one event wakes two workers together. The first raises the fatal; the second was already scheduled
    to run *before* the TaskGroup can cancel it, finishes its item and loops. It must not admit item 2."""
    boom = make_boom()

    async def scenario():
        go = asyncio.Event()

        async def behavior(number, seq):
            if seq in (0, 1):
                await go.wait()
            if seq == 0:
                raise boom
            return agg(number)

        engine = ScriptedEngine(behavior)

        async def observe():  # a KeyboardInterrupt must be caught in-frame, never left to escape a Task step
            try:
                return None, await BatchScheduler(engine, BatchConfig(max_in_flight_items=2)).run(numbers(20))
            except BaseException as exc:  # noqa: BLE001
                return exc, None

        task = asyncio.create_task(observe())
        await until(lambda: engine.active == 2)
        go.set()
        caught, value = await task
        await asyncio.sleep(0)
        return engine, caught, value, others()

    engine, caught, value, leftover = run(scenario())
    assert caught is boom and value is None and leftover == []
    assert engine.calls == numbers(2), "no item was admitted after the fatal exception"


def test_the_scheduler_is_reusable_after_a_fatal_exception():
    async def boom(number, seq):
        raise CustomFatal()

    async def scenario():
        engine = ScriptedEngine(boom)
        sched = BatchScheduler(engine, BatchConfig(max_in_flight_items=2))
        caught, _, _ = await capture(sched.run(numbers(3)))
        assert isinstance(caught, CustomFatal)
        engine._behavior = ScriptedEngine._default  # heal the fake
        return await sched.run(numbers(3))

    assert run(scenario()).success_count == 3


def test_an_engine_raising_cancelled_error_on_its_own_is_propagated_not_turned_into_a_failed_item():
    """Nobody cancelled the batch. A source adapter doing this is isolated (C2); at batch level it must propagate."""
    boom = asyncio.CancelledError("engine-self-cancel")
    gate = {}

    async def behavior(number, seq):
        if seq == 1:
            await asyncio.sleep(0)
            raise boom
        await gate["g"].wait()
        return agg(number)

    engine = ScriptedEngine(behavior)

    async def scenario():
        gate["g"] = Gate()
        return await capture(BatchScheduler(engine, BatchConfig(max_in_flight_items=3)).run(numbers(30)))

    caught, value, leftover = run(scenario())
    assert caught is boom and value is None and leftover == []
    assert len(engine.calls) == 3 and engine.active == 0


# ---- caller cancellation ----------------------------------------------------------------------------------------


@pytest.mark.parametrize("limit, count", [(1, 1000), (3, 100), (8, 8), (4, 3)])
def test_cancelling_the_batch_cancels_and_awaits_running_items_and_never_starts_the_rest(limit, count):
    batch = numbers(count)
    gate = {}

    async def behavior(number, seq):
        await gate["g"].wait()
        return agg(number)

    engine = ScriptedEngine(behavior)

    async def scenario():
        gate["g"] = Gate()
        task = asyncio.create_task(BatchScheduler(engine, BatchConfig(max_in_flight_items=limit)).run(batch))
        admitted = min(limit, count)
        await until(lambda: engine.active == admitted)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert task.cancelled()
        await asyncio.sleep(0)
        return others()

    leftover = run(scenario())
    admitted = min(limit, count)
    assert engine.calls == batch[:admitted], "items that were never admitted never started"
    assert sorted(engine.cancelled) == sorted(batch[:admitted]), "every running item was cancelled ..."
    assert engine.active == 0, "... and its cleanup completed before run() returned"
    assert engine.completed == []
    assert leftover == [], "no orphan task"


def test_cancellation_is_not_turned_into_failed_items_and_the_scheduler_is_reusable():
    gate = {}

    async def behavior(number, seq):
        await gate["g"].wait()
        return agg(number)

    async def scenario():
        gate["g"] = Gate()
        engine = ScriptedEngine(behavior)
        sched = BatchScheduler(engine, BatchConfig(max_in_flight_items=2))
        task = asyncio.create_task(sched.run(numbers(6)))
        await until(lambda: engine.active == 2)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        gate["g"].release.set()
        return await sched.run(numbers(3, start=7_000_001))  # not BatchBusyError

    result = run(scenario())
    assert result.success_count == 3


def test_cancelling_while_a_run_is_between_items_still_admits_nothing_more():
    """Cancel right after an item finished: the freed slot must not admit the next item."""
    async def scenario():
        events = [asyncio.Event() for _ in range(50)]

        async def behavior(number, seq):
            await events[seq].wait()
            return agg(number)

        engine = ScriptedEngine(behavior)
        task = asyncio.create_task(BatchScheduler(engine, BatchConfig(max_in_flight_items=1)).run(numbers(50)))
        await until(lambda: engine.active == 1)
        events[0].set()  # item 0 can finish ...
        task.cancel()  # ... but the caller cancels in the same loop iteration
        with pytest.raises(asyncio.CancelledError):
            await task
        await asyncio.sleep(0)
        return engine, others()

    engine, leftover = run(scenario())
    assert engine.calls == numbers(1), "the freed slot never admitted item 1"
    assert leftover == []


def test_cancelling_retry_failed_has_the_same_guarantees():
    async def scenario():
        gate = Gate()
        phase = {"n": 0}

        async def behavior(number, seq):
            if phase["n"] == 0:
                raise RuntimeError("primary failure")
            await gate.wait()
            return agg(number)

        engine = ScriptedEngine(behavior)
        sched = BatchScheduler(engine, BatchConfig(max_in_flight_items=2))
        primary = await sched.run(numbers(10))
        assert primary.failed_count == 10
        phase["n"] = 1
        calls_before = len(engine.calls)
        task = asyncio.create_task(sched.retry_failed(primary))
        await until(lambda: engine.active == 2)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        await asyncio.sleep(0)
        return engine, calls_before, others()

    engine, calls_before, leftover = run(scenario())
    assert len(engine.calls) - calls_before == 2 and engine.active == 0 and leftover == []
    assert len(engine.cancelled) == 2


# ---- through the REAL MultiSourceEngine (nested task group inside every item) -------------------------------------


class _Client:
    async def get(self, url, *, headers=None, timeout=None):  # pragma: no cover - adapters are scripted
        raise AssertionError("no network in tests")


def real_engine(script):
    registry = SourceRegistry()
    registry.register("only", scripted_adapter_class("only", script))
    return MultiSourceEngine(AggregationConfig(sources=(SourceConfig("only"),)), registry, _Client())


def test_cancelling_a_batch_over_the_real_engine_cancels_the_adapters_and_leaves_no_task():
    started, cancelled = [], []

    async def hang(number, client):
        started.append(number)
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            cancelled.append(number)
            raise

    async def scenario():
        sched = BatchScheduler(real_engine(hang), BatchConfig(max_in_flight_items=3))
        task = asyncio.create_task(sched.run(numbers(50)))
        await until(lambda: len(started) == 3)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        await asyncio.sleep(0)
        return others()

    leftover = run(scenario())
    assert sorted(cancelled) == sorted(started) == numbers(3)
    assert leftover == []


@pytest.mark.parametrize("exc_type", FATALS, ids=lambda t: t.__name__)
def test_a_fatal_raised_inside_an_adapter_reaches_the_batch_caller_as_the_original_object(exc_type):
    boom = exc_type("adapter-fatal")

    async def script(number, client):
        await asyncio.sleep(0)
        if number == numbers(3)[1]:
            raise boom
        return ok("only", number, "T")

    async def scenario():
        return await capture(BatchScheduler(real_engine(script), BatchConfig(max_in_flight_items=1)).run(numbers(6)))

    caught, value, leftover = run(scenario())
    assert caught is boom and value is None and leftover == []


def test_ordinary_adapter_failures_over_the_real_engine_are_source_level_not_batch_level():
    async def script(number, client):
        if number.endswith("2"):
            raise RuntimeError("adapter bug " + "SECRET")
        return ok("only", number, "T")

    result = run(BatchScheduler(real_engine(script), BatchConfig(max_in_flight_items=2)).run(numbers(4)))
    # the engine already isolates adapter exceptions: the item is FAILED via its AggregationResult, no batch error
    assert [i.status for i in result.items] == [
        BatchItemStatus.SUCCESS, BatchItemStatus.FAILED, BatchItemStatus.SUCCESS, BatchItemStatus.SUCCESS
    ]
    failed = result.items[1]
    assert failed.error_kind is None and failed.aggregation_result is not None
    assert "SECRET" not in repr(result)
