"""P4-C8 S1: ``OrchestrationConfig`` and the frozen constants (contract section 9)."""

from __future__ import annotations

import dataclasses

import pytest

from fc2_metadata_core.batch import BatchConfig
from fc2_organizer.orchestration import (
    DEFAULT_FILESYSTEM_WORKERS,
    DEFAULT_IMAGE_IN_FLIGHT_ITEMS,
    DEFAULT_MAX_RETAINED_ARTIFACT_BYTES,
    MAX_BATCH_ITEMS,
    MAX_FILESYSTEM_WORKERS,
    MAX_IMAGE_IN_FLIGHT_ITEMS,
    MAX_ITEM_IMAGE_BYTES,
    MAX_RETAINED_ARTIFACT_BYTES_LIMIT,
    OrchestrationConfig,
    OrchestrationConfigError,
)

GIB = 1024 ** 3


def test_frozen_constant_values():
    assert DEFAULT_IMAGE_IN_FLIGHT_ITEMS == 4 and MAX_IMAGE_IN_FLIGHT_ITEMS == 16
    assert DEFAULT_FILESYSTEM_WORKERS == 1 and MAX_FILESYSTEM_WORKERS == 8
    assert MAX_BATCH_ITEMS == 2000 and MAX_BATCH_ITEMS >= 500
    assert MAX_ITEM_IMAGE_BYTES == 64 * 1024 * 1024
    assert DEFAULT_MAX_RETAINED_ARTIFACT_BYTES == 2 * GIB
    assert MAX_RETAINED_ARTIFACT_BYTES_LIMIT == 16 * GIB
    for value in (DEFAULT_IMAGE_IN_FLIGHT_ITEMS, MAX_IMAGE_IN_FLIGHT_ITEMS, DEFAULT_FILESYSTEM_WORKERS,
                  MAX_FILESYSTEM_WORKERS, MAX_BATCH_ITEMS, MAX_ITEM_IMAGE_BYTES,
                  DEFAULT_MAX_RETAINED_ARTIFACT_BYTES, MAX_RETAINED_ARTIFACT_BYTES_LIMIT):
        assert type(value) is int


def test_defaults():
    config = OrchestrationConfig()
    assert type(config.metadata) is BatchConfig and config.metadata == BatchConfig()
    assert config.metadata.max_in_flight_items == 4
    assert config.image_in_flight_items == 4
    assert config.filesystem_workers == 1
    assert config.max_retained_artifact_bytes == DEFAULT_MAX_RETAINED_ARTIFACT_BYTES


def test_fields_are_exactly_the_frozen_four():
    names = [f.name for f in dataclasses.fields(OrchestrationConfig)]
    assert names == ["metadata", "image_in_flight_items", "filesystem_workers", "max_retained_artifact_bytes"]


@pytest.mark.parametrize("name, low, high", [
    ("image_in_flight_items", 1, 16),
    ("filesystem_workers", 1, 8),
    ("max_retained_artifact_bytes", 1, 16 * GIB),
])
def test_range_boundaries(name, low, high):
    assert getattr(OrchestrationConfig(**{name: low}), name) == low
    assert getattr(OrchestrationConfig(**{name: high}), name) == high
    for bad in (low - 1, high + 1, 0, -1):
        with pytest.raises(OrchestrationConfigError):
            OrchestrationConfig(**{name: bad})


class _IntSubclass(int):
    pass


@pytest.mark.parametrize("name", ["image_in_flight_items", "filesystem_workers", "max_retained_artifact_bytes"])
@pytest.mark.parametrize("bad", [True, False, 2.0, "2", None, _IntSubclass(2)])
def test_non_exact_int_is_rejected(name, bad):
    with pytest.raises(OrchestrationConfigError):
        OrchestrationConfig(**{name: bad})


def test_max_retained_artifact_bytes_boundaries():
    assert OrchestrationConfig(max_retained_artifact_bytes=1).max_retained_artifact_bytes == 1
    assert (OrchestrationConfig(max_retained_artifact_bytes=MAX_RETAINED_ARTIFACT_BYTES_LIMIT)
            .max_retained_artifact_bytes == MAX_RETAINED_ARTIFACT_BYTES_LIMIT)
    for bad in (0, MAX_RETAINED_ARTIFACT_BYTES_LIMIT + 1, True):
        with pytest.raises(OrchestrationConfigError):
            OrchestrationConfig(max_retained_artifact_bytes=bad)


def test_metadata_must_be_an_exact_batch_config():
    class SubConfig(BatchConfig):
        pass

    assert OrchestrationConfig(metadata=BatchConfig(max_in_flight_items=64)).metadata.max_in_flight_items == 64
    for bad in (None, 4, {"max_in_flight_items": 4}, SubConfig()):
        with pytest.raises(OrchestrationConfigError):
            OrchestrationConfig(metadata=bad)


def test_config_is_immutable():
    config = OrchestrationConfig()
    with pytest.raises(dataclasses.FrozenInstanceError):
        config.filesystem_workers = 2  # type: ignore[misc]
    with pytest.raises((AttributeError, TypeError)):
        config.extra = 1  # type: ignore[attr-defined]


def test_config_error_is_not_chained():
    with pytest.raises(OrchestrationConfigError) as info:
        OrchestrationConfig(filesystem_workers=9)
    assert info.value.__cause__ is None and info.value.__context__ is None


def test_no_forbidden_knobs():
    names = {f.name for f in dataclasses.fields(OrchestrationConfig)}
    for knob in ("continue_on_item_failure", "overwrite", "delete_conflicts", "auto_resume", "persist", "timeout"):
        assert knob not in names
