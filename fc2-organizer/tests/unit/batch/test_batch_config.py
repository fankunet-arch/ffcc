"""BatchConfig: immutable, validated before any engine call (contract §3)."""

from __future__ import annotations

import dataclasses

import pytest

from fc2_metadata_core.batch import (
    DEFAULT_MAX_IN_FLIGHT_ITEMS,
    MAX_IN_FLIGHT_ITEMS_LIMIT,
    BatchConfig,
    BatchConfigError,
    BatchScheduler,
)
from support.batch_fakes import ScriptedEngine


def test_default_is_four_and_the_documented_range_is_1_to_64():
    assert DEFAULT_MAX_IN_FLIGHT_ITEMS == 4
    assert MAX_IN_FLIGHT_ITEMS_LIMIT == 64
    assert BatchConfig().max_in_flight_items == 4


@pytest.mark.parametrize("value", [1, 2, 4, 63, 64])
def test_valid_values(value):
    assert BatchConfig(max_in_flight_items=value).max_in_flight_items == value


@pytest.mark.parametrize(
    "value",
    [0, -1, 65, 1000, True, False, 1.0, 2.5, "4", None, [4], float("nan"), float("inf")],
    ids=repr,
)
def test_invalid_values_are_rejected(value):
    with pytest.raises(BatchConfigError):
        BatchConfig(max_in_flight_items=value)


def test_bool_is_not_an_int():
    with pytest.raises(BatchConfigError):
        BatchConfig(max_in_flight_items=True)


def test_the_config_is_frozen():
    config = BatchConfig(max_in_flight_items=3)
    with pytest.raises(dataclasses.FrozenInstanceError):
        config.max_in_flight_items = 9  # type: ignore[misc]
    with pytest.raises((AttributeError, TypeError)):
        config.extra = 1  # type: ignore[attr-defined]


def test_there_is_no_switch_to_turn_item_isolation_off():
    """Frozen semantics: an ordinary item failure is always isolated (contract §3)."""
    assert [f.name for f in dataclasses.fields(BatchConfig)] == ["max_in_flight_items"]


def test_the_scheduler_validates_its_arguments_before_any_call():
    engine = ScriptedEngine()
    with pytest.raises(BatchConfigError):
        BatchScheduler(engine, config={"max_in_flight_items": 3})  # type: ignore[arg-type]
    with pytest.raises(BatchConfigError):
        BatchScheduler(object())  # type: ignore[arg-type]
    with pytest.raises(BatchConfigError):
        BatchScheduler(None)  # type: ignore[arg-type]

    class SyncEngine:
        def aggregate(self, number):  # a plain def is rejected, like a sync client.get in the engine
            return None

    with pytest.raises(BatchConfigError):
        BatchScheduler(SyncEngine())  # type: ignore[arg-type]
    assert engine.calls == []


def test_the_scheduler_defaults_to_the_default_config():
    assert BatchScheduler(ScriptedEngine()).config == BatchConfig()
    assert BatchScheduler(ScriptedEngine(), BatchConfig(max_in_flight_items=7)).config.max_in_flight_items == 7
