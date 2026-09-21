"""Batch input contract (contract §4): an ordered Sequence of canonical numbers, all-or-nothing."""

from __future__ import annotations

import asyncio
from collections import deque

import pytest

from fc2_metadata_core.batch import BatchConfig, BatchInputError, BatchItemStatus, BatchScheduler
from support.batch_fakes import ScriptedEngine, agg, numbers


def run(coro):
    return asyncio.run(coro)


def scheduler(engine=None, limit=3):
    engine = engine or ScriptedEngine()
    return engine, BatchScheduler(engine, BatchConfig(max_in_flight_items=limit))


# ---- container contract -----------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad",
    [
        "FC2-1234567",  # a str is a Sequence of str: must be rejected as a batch
        b"FC2-1234567",
        bytearray(b"FC2-1234567"),
        memoryview(b"FC2-1234567"),
        {"FC2-1234567"},
        frozenset({"FC2-1234567", "FC2-1234568"}),
        {"FC2-1234567": 1},
        {"FC2-1234567": "FC2-1234567"}.keys(),
        {"FC2-1234567": 1}.values(),
        iter(["FC2-1234567"]),
        (n for n in ["FC2-1234567"]),
        None,
        123,
        object(),
    ],
    ids=lambda v: type(v).__name__,
)
def test_non_sequence_or_unordered_containers_are_rejected_without_any_call(bad):
    engine, sched = scheduler()
    with pytest.raises(BatchInputError):
        run(sched.run(bad))
    assert engine.calls == []


@pytest.mark.parametrize("container", [list, tuple, deque], ids=lambda c: c.__name__)
def test_list_tuple_and_deque_are_accepted_and_keep_order(container):
    batch = numbers(5)
    _, sched = scheduler()
    result = run(sched.run(container(batch)))
    assert [item.number for item in result.items] == batch


def test_the_caller_list_is_snapshotted_so_later_mutation_has_no_effect():
    batch = numbers(6)
    expected = list(batch)

    async def behavior(number, seq):
        batch.append("garbage")  # mutating the caller's list while running
        batch.reverse()
        return agg(number)

    engine = ScriptedEngine(behavior)
    sched = BatchScheduler(engine, BatchConfig(max_in_flight_items=1))
    result = run(sched.run(batch))
    assert [item.number for item in result.items] == expected
    assert engine.calls == expected


# ---- empty ------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("empty", [[], (), deque()], ids=["list", "tuple", "deque"])
def test_empty_input_is_legal_and_never_calls_the_engine(empty):
    engine, sched = scheduler()
    result = run(sched.run(empty))
    assert result.items == ()
    assert (result.total, result.success_count, result.partial_count, result.failed_count) == (0, 0, 0, 0)
    assert result.failed_indices == () and result.failed_numbers == ()
    assert result.generation == 0
    assert engine.calls == []


# ---- canonical boundary -----------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "dirty",
    [
        "abc FC2PPV-1234567.mp4",  # dirty filename: the scan/normalize layer's job, not the scheduler's
        "FC2-PPV-1234567",
        "fc2-1234567",
        "FC2-1234",  # too short
        "FC2-123456789",  # too long
        " FC2-1234567",
        "FC2-1234567\n",
        "1234567",
        "",
        None,
        1234567,
        b"FC2-1234567",
        ["FC2-1234567"],
    ],
    ids=repr,
)
def test_any_non_canonical_element_rejects_the_whole_batch_before_any_call(dirty):
    engine, sched = scheduler()
    batch = numbers(3) + [dirty] + numbers(3, start=2_000_001)
    with pytest.raises(BatchInputError) as caught:
        run(sched.run(batch))
    assert engine.calls == [], "all-or-nothing: no partial execution of the valid items"
    assert "3" in str(caught.value), "the offending index is reported"


def test_all_offending_indices_are_reported_and_the_message_is_bounded():
    engine, sched = scheduler()
    batch = ["FC2-1000001", "bad", "FC2-1000002", "worse"] + ["x" * 5000] * 50
    with pytest.raises(BatchInputError) as caught:
        run(sched.run(batch))
    message = str(caught.value)
    assert "[1] 'bad'" in message and "[3] 'worse'" in message
    assert "52 element(s)" in message and "(+42 more)" in message, "counted in full, listed only up to a cap"
    assert len(message) < 2000, "huge hostile elements must not bloat the message"
    assert engine.calls == []


def test_a_hostile_element_repr_is_never_evaluated():
    class Boom:
        def __repr__(self):
            raise RuntimeError("repr must not be called")

        def __str__(self):
            raise RuntimeError("str must not be called")

    engine, sched = scheduler()
    with pytest.raises(BatchInputError):
        run(sched.run(["FC2-1000001", Boom()]))
    assert engine.calls == []


def test_canonical_numbers_of_5_to_8_digits_are_accepted():
    _, sched = scheduler()
    batch = ["FC2-12345", "FC2-123456", "FC2-1234567", "FC2-12345678"]
    assert [i.number for i in run(sched.run(batch)).items] == batch


# ---- duplicates -------------------------------------------------------------------------------------------------


def test_duplicates_are_preserved_as_separate_items_with_their_own_index():
    dup = "FC2-1000001"
    engine, sched = scheduler(limit=2)
    result = run(sched.run([dup, "FC2-1000002", dup, dup]))
    assert result.total == 4
    assert [(i.index, i.number) for i in result.items] == [
        (0, dup), (1, "FC2-1000002"), (2, dup), (3, dup)
    ]
    assert engine.calls.count(dup) == 3, "no dedupe: one aggregate() call per item"
    assert all(i.status is BatchItemStatus.SUCCESS for i in result.items)
