"""Every shipped adapter obeys the SourceAdapter identity contract and registers cleanly."""

from __future__ import annotations

import importlib
import inspect

from fc2_metadata_core.sources import SourceRegistry
from fc2_metadata_core.sources.adapters import ALL_ADAPTER_CLASSES

EXPECTED_IDS = {"fc2db_net", "av123", "javdb"}


def test_adapter_list_matches_adopted_sources():
    assert {cls.source_id for cls in ALL_ADAPTER_CLASSES} == EXPECTED_IDS
    assert len(ALL_ADAPTER_CLASSES) == len(EXPECTED_IDS)


def test_all_adapters_register_and_instantiate_offline():
    registry = SourceRegistry()
    for cls in ALL_ADAPTER_CLASSES:
        registry.register(cls.source_id, cls)
    for source_id in EXPECTED_IDS:
        adapter = registry.create(source_id)
        assert adapter.source_id == source_id
        assert adapter.base_url.startswith("https://")
        assert adapter.display_name.strip()


def test_adapters_do_not_depend_on_another_source():
    # Cross-source merging is Phase 3: no adapter module may import a sibling adapter.
    for cls in ALL_ADAPTER_CLASSES:
        module_source = inspect.getsource(importlib.import_module(cls.__module__))
        for other in EXPECTED_IDS - {cls.source_id}:
            assert f"adapters.{other}" not in module_source, (cls.__module__, other)
