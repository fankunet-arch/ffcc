"""Offline tests for SourceRegistry: enumeration, lookup, duplicate/unknown
id handling -- proving Phase 3 can list/find/instantiate sources without an
if/elif chain."""

from __future__ import annotations

import pytest

from fc2_metadata_core.sources.registry import (
    DuplicateSourceIdError,
    SourceRegistry,
    SourceRegistryError,
    UnknownSourceIdError,
)

from support.fake_source_adapter import FakeSourceAdapter


def test_registered_source_is_enumerable():
    registry = SourceRegistry()
    registry.register(FakeSourceAdapter.source_id, FakeSourceAdapter)
    assert registry.source_ids() == ("fake_source",)
    assert "fake_source" in registry
    assert len(registry) == 1


def test_registry_starts_empty():
    registry = SourceRegistry()
    assert registry.source_ids() == ()
    assert len(registry) == 0


def test_duplicate_source_id_rejected():
    registry = SourceRegistry()
    registry.register("fake_source", FakeSourceAdapter)
    with pytest.raises(DuplicateSourceIdError):
        registry.register("fake_source", FakeSourceAdapter)


def test_unknown_source_id_raises_on_create():
    registry = SourceRegistry()
    with pytest.raises(UnknownSourceIdError):
        registry.create("does_not_exist")


def test_unknown_source_id_raises_on_unregister():
    registry = SourceRegistry()
    with pytest.raises(UnknownSourceIdError):
        registry.unregister("does_not_exist")


def test_unknown_source_id_error_is_also_a_key_error():
    # So callers using dict-like error handling patterns still work.
    registry = SourceRegistry()
    with pytest.raises(KeyError):
        registry.create("does_not_exist")


def test_create_instantiates_a_fresh_adapter_each_time():
    registry = SourceRegistry()
    registry.register("fake_source", FakeSourceAdapter)
    first = registry.create("fake_source")
    second = registry.create("fake_source")
    assert isinstance(first, FakeSourceAdapter)
    assert first is not second


def test_create_forwards_base_url_override_to_factory():
    registry = SourceRegistry()
    registry.register("fake_source", FakeSourceAdapter)
    adapter = registry.create("fake_source", base_url="https://mirror.invalid")
    assert adapter.base_url == "https://mirror.invalid"


def test_empty_source_id_rejected_on_register():
    registry = SourceRegistry()
    with pytest.raises(SourceRegistryError):
        registry.register("", FakeSourceAdapter)


def test_multiple_independent_sources_are_all_enumerable():
    class OtherFakeAdapter(FakeSourceAdapter):
        source_id = "other_fake_source"
        display_name = "Other Fake Source"
        default_base_url = "https://other-fake-source.invalid"

    registry = SourceRegistry()
    registry.register(FakeSourceAdapter.source_id, FakeSourceAdapter)
    registry.register(OtherFakeAdapter.source_id, OtherFakeAdapter)

    assert set(registry.source_ids()) == {"fake_source", "other_fake_source"}
