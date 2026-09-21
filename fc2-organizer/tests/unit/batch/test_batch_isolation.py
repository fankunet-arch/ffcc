"""Per-item ordinary-failure isolation and no secret leakage (contract §6)."""

from __future__ import annotations

import asyncio
import gc
import weakref

import pytest

from fc2_metadata_core.batch import (
    BatchConfig,
    BatchItemErrorKind,
    BatchItemStatus,
    BatchScheduler,
)
from support.batch_fakes import ScriptedEngine, agg, numbers

SECRET = "SECRET-token=abc123 https://user:pw@evil.example/?key=xyz"


def run(coro):
    return asyncio.run(coro)


@pytest.mark.parametrize("limit", [1, 2, 4])
def test_one_raising_item_fails_alone_and_the_others_complete(limit):
    batch = numbers(9)
    bad = batch[3]

    async def behavior(number, seq):
        await asyncio.sleep(0)
        if number == bad:
            raise RuntimeError(SECRET)
        return agg(number)

    engine = ScriptedEngine(behavior)
    result = run(BatchScheduler(engine, BatchConfig(max_in_flight_items=limit)).run(batch))
    assert len(engine.calls) == 9, "the failure did not stop admission"
    assert [i.status for i in result.items] == [
        BatchItemStatus.FAILED if n == bad else BatchItemStatus.SUCCESS for n in batch
    ]
    failed = result.items[3]
    assert failed.error_kind is BatchItemErrorKind.ENGINE_EXCEPTION
    assert failed.error_type == "RuntimeError"
    assert failed.aggregation_result is None
    assert result.failed_indices == (3,)
    assert result.success_count == 8 and result.failed_count == 1


def test_the_exception_text_is_never_recorded_anywhere():
    class LeakyError(Exception):
        def __init__(self):
            super().__init__(SECRET, {"cookie": SECRET})
            self.token = SECRET

        def __str__(self):
            return SECRET

        def __repr__(self):
            return f"LeakyError({SECRET!r})"

    async def behavior(number, seq):
        raise LeakyError()

    engine = ScriptedEngine(behavior)
    result = run(BatchScheduler(engine).run(numbers(3)))
    blob = repr(result) + str(result) + repr([repr(i) for i in result.items])
    for needle in ("SECRET", "abc123", "evil.example", "pw@", "xyz", "cookie"):
        assert needle not in blob
    assert all(i.error_type == "LeakyError" for i in result.items)


@pytest.mark.parametrize(
    "exc_type",
    [ValueError, KeyError, OSError, ConnectionError, TimeoutError, asyncio.TimeoutError, ZeroDivisionError,
     RecursionError, MemoryError, AssertionError, LookupError, UnicodeError],
    ids=lambda t: t.__name__,
)
def test_every_ordinary_exception_type_is_an_item_failure_recorded_by_class_name(exc_type):
    async def behavior(number, seq):
        raise exc_type(SECRET)

    result = run(BatchScheduler(ScriptedEngine(behavior)).run(numbers(2)))
    assert [i.status for i in result.items] == [BatchItemStatus.FAILED] * 2
    assert all(i.error_type == exc_type.__name__ for i in result.items)
    assert "SECRET" not in repr(result)


def test_an_exception_group_from_the_engine_is_an_ordinary_item_failure():
    async def behavior(number, seq):
        raise ExceptionGroup("grp", [ValueError(SECRET), KeyError(SECRET)])

    (item,) = run(BatchScheduler(ScriptedEngine(behavior)).run(numbers(1))).items
    assert item.status is BatchItemStatus.FAILED and item.error_type == "ExceptionGroup"
    assert "SECRET" not in repr(item)


def test_the_scheduler_keeps_no_reference_to_the_exception_or_its_traceback():
    class Marker(Exception):
        pass

    refs: list[weakref.ref] = []

    async def behavior(number, seq):
        exc = Marker(SECRET)
        refs.append(weakref.ref(exc))
        raise exc

    result = run(BatchScheduler(ScriptedEngine(behavior)).run(numbers(4)))
    gc.collect()
    assert len(refs) == 4 and all(r() is None for r in refs), "exception objects (and tracebacks) were retained"
    assert result.failed_count == 4


def test_unusual_exception_class_names_are_sanitised_not_trusted():
    weird = type("not an identifier!", (Exception,), {})
    long_name = type("L" * 500, (Exception,), {})

    class Meta(type):
        @property
        def __name__(cls):  # a hostile metaclass: reading the name raises
            raise RuntimeError(SECRET)

    hostile = Meta("Hostile", (Exception,), {})

    async def behavior(number, seq):
        raise {"FC2-1000001": weird, "FC2-1000002": long_name, "FC2-1000003": hostile}[number](SECRET)

    result = run(BatchScheduler(ScriptedEngine(behavior)).run(["FC2-1000001", "FC2-1000002", "FC2-1000003"]))
    assert [i.status for i in result.items] == [BatchItemStatus.FAILED] * 3
    for item in result.items:
        assert item.error_type.isidentifier() and len(item.error_type) <= 128
    assert "SECRET" not in repr(result)


def test_many_ordinary_failures_do_not_starve_or_block_the_batch():
    batch = numbers(200)

    async def behavior(number, seq):
        if seq % 3 == 0:
            raise RuntimeError(SECRET)
        await asyncio.sleep(0)
        return agg(number, "partial" if seq % 3 == 1 else "success")

    engine = ScriptedEngine(behavior)
    result = run(BatchScheduler(engine, BatchConfig(max_in_flight_items=5)).run(batch))
    assert result.total == 200 and len(engine.calls) == 200
    assert result.failed_count == len([s for s in range(200) if s % 3 == 0])
    assert engine.active == 0
    assert [i.index for i in result.items] == list(range(200))


def test_a_failing_item_does_not_disturb_items_that_are_in_flight_beside_it():
    a, b, c = numbers(3)
    order = []

    async def behavior(number, seq):
        if number == b:
            await asyncio.sleep(0)
            raise RuntimeError(SECRET)
        for _ in range(5):
            await asyncio.sleep(0)
        order.append(number)
        return agg(number)

    result = run(BatchScheduler(ScriptedEngine(behavior), BatchConfig(max_in_flight_items=3)).run([a, b, c]))
    assert order == [a, c], "the siblings ran to completion beside the failing item"
    assert [i.status for i in result.items] == [
        BatchItemStatus.SUCCESS, BatchItemStatus.FAILED, BatchItemStatus.SUCCESS
    ]
