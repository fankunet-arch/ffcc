"""Aggregation -> batch status mapping and fail-closed engine results (contract §6)."""

from __future__ import annotations

import asyncio
import inspect

import pytest

from fc2_metadata_core.aggregation import AggregateStatus, AggregationConfig, MultiSourceEngine, SourceConfig
from fc2_metadata_core.batch import (
    BatchConfig,
    BatchItemErrorKind,
    BatchItemStatus,
    BatchScheduler,
)
from fc2_metadata_core.sources import SourceRegistry
from support.batch_fakes import ScriptedEngine, agg, numbers
from support.scripted_adapters import ok, scripted_adapter_class


def run(coro):
    return asyncio.run(coro)


@pytest.mark.parametrize(
    "kind, aggregate_status, batch_status",
    [
        ("success", AggregateStatus.SUCCESS, BatchItemStatus.SUCCESS),
        ("partial", AggregateStatus.PARTIAL, BatchItemStatus.PARTIAL),
        ("deadline", AggregateStatus.PARTIAL, BatchItemStatus.PARTIAL),
        ("failed", AggregateStatus.FAILED, BatchItemStatus.FAILED),
    ],
)
def test_aggregation_status_maps_one_to_one(kind, aggregate_status, batch_status):
    (number,) = numbers(1)
    engine = ScriptedEngine(lambda n, s: _return(agg(n, kind)))
    (item,) = run(BatchScheduler(engine).run([number])).items
    assert agg(number, kind).status is aggregate_status
    assert item.status is batch_status
    assert item.aggregation_result is agg(number, kind), "the AggregationResult is carried through untouched"
    assert item.error_kind is None and item.error_type is None


async def _return(value):
    return value


def test_a_failed_aggregation_keeps_every_source_result():
    (number,) = numbers(1)
    engine = ScriptedEngine(lambda n, s: _return(agg(n, "failed")))
    (item,) = run(BatchScheduler(engine).run([number])).items
    assert item.status is BatchItemStatus.FAILED
    assert len(item.aggregation_result.source_results) == 2
    assert item.error_kind is None


@pytest.mark.parametrize(
    "returned",
    [None, "FC2-1000001", {"status": "success"}, 42, object(), agg("FC2-1000001").metadata],
    ids=lambda v: type(v).__name__,
)
def test_a_non_aggregation_result_is_a_fail_closed_contract_mismatch(returned):
    engine = ScriptedEngine(lambda n, s: _return(returned))
    other = numbers(2, start=1_000_001)
    result = run(BatchScheduler(engine).run(other))
    for item in result.items:
        assert item.status is BatchItemStatus.FAILED
        assert item.error_kind is BatchItemErrorKind.RESULT_CONTRACT_MISMATCH
        assert item.aggregation_result is None
        assert item.error_type == type(returned).__name__


def test_a_result_for_another_number_is_a_contract_mismatch_not_a_success():
    engine = ScriptedEngine(lambda n, s: _return(agg("FC2-9999999")))
    (item,) = run(BatchScheduler(engine).run(["FC2-1000001"])).items
    assert item.status is BatchItemStatus.FAILED
    assert item.error_kind is BatchItemErrorKind.RESULT_CONTRACT_MISMATCH
    assert item.aggregation_result is None
    assert item.number == "FC2-1000001"


def test_a_mismatching_item_does_not_disturb_its_neighbours():
    good, wrong = "FC2-1000001", "FC2-1000002"

    async def behavior(number, seq):
        return agg(number) if number == good else agg("FC2-9999999")

    result = run(BatchScheduler(ScriptedEngine(behavior), BatchConfig(max_in_flight_items=2)).run([good, wrong, good]))
    assert [i.status for i in result.items] == [
        BatchItemStatus.SUCCESS, BatchItemStatus.FAILED, BatchItemStatus.SUCCESS
    ]


def test_elapsed_ms_uses_the_injected_clock_and_is_per_item():
    ticks = iter(range(0, 1000))

    def clock():
        return next(ticks) * 0.5  # deterministic: each read advances 0.5 s

    engine = ScriptedEngine()
    sched = BatchScheduler(engine, BatchConfig(max_in_flight_items=1), clock=clock)
    result = run(sched.run(numbers(3)))
    assert [i.elapsed_ms for i in result.items] == [500.0, 500.0, 500.0]


def test_the_real_multisource_engine_satisfies_the_narrow_engine_protocol():
    """Production compatibility without building a network: the scheduler only needs ``async aggregate``."""
    assert inspect.iscoroutinefunction(MultiSourceEngine.aggregate)
    sig = inspect.signature(MultiSourceEngine.aggregate)
    assert list(sig.parameters) == ["self", "number"]


def test_an_engine_built_from_a_real_multisource_engine_is_accepted_by_the_scheduler():
    async def script(number, client):
        return ok("only", number, "T")

    registry = SourceRegistry()
    registry.register("only", scripted_adapter_class("only", script))

    class Client:
        async def get(self, url, *, headers=None, timeout=None):  # pragma: no cover - never called
            raise AssertionError

    engine = MultiSourceEngine(AggregationConfig(sources=(SourceConfig("only"),)), registry, Client())
    result = run(BatchScheduler(engine, BatchConfig(max_in_flight_items=2)).run(numbers(4)))
    assert [i.status for i in result.items] == [BatchItemStatus.SUCCESS] * 4
    assert [i.aggregation_result.number for i in result.items] == numbers(4)
