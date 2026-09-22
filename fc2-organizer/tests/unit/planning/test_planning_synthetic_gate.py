"""P4-C2 Synthetic Planning Gate (contract section 32).

Builds several hundred synthetic ``DiscoveredMediaItem``s across many
extensions and canonical numbers, with Unicode metadata, and plans every
one of them. Verifies: determinism (byte/field-equivalent replay), full
target containment, zero internal target collisions across the whole
batch's own generated targets when numbers are unique, zero filesystem
mutation, and zero network dependency (no ``socket``/``httpx`` import
anywhere reachable from this package).

Entirely offline, fixed (non-random) layout, so the run is exactly
reproducible -- same spirit as P4-C1's
``test_discovery_stage_gate.py::test_large_synthetic_stage_gate``.
"""

from __future__ import annotations

import os

from fc2_metadata_core.models import NormalizedMetadata
from fc2_organizer.discovery import DiscoveredMediaItem
from fc2_organizer.planning.planner import build_organize_plan
from fc2_organizer.planning.policy import OutputPolicy

LIBRARY_ROOT = r"C:\library"
EXTENSIONS = (".mp4", ".mkv", ".avi", ".mov", ".wmv", ".m4v", ".ts")
UNICODE_TITLES = (
    "\u65e5\u672c\u8a9e\u30bf\u30a4\u30c8\u30eb",
    "Caf\u00e9 \u00c9t\u00e9",
    "\u0410\u043b\u0444\u0430 \u0411\u0435\u0442\u0430",
    "\ud83d\ude00 emoji title \ud83c\udf89",
    "T\u00eftle w\u00edth \u00e2cc\u00e9nts",
)


def _build_synthetic_items(count: int) -> list[tuple[DiscoveredMediaItem, str, NormalizedMetadata]]:
    specs = []
    for i in range(count):
        extension = EXTENSIONS[i % len(EXTENSIONS)]
        digits = 5000000 + i  # 7 digits, well inside the 5-8 digit window
        canonical = f"FC2-{digits}"
        title = UNICODE_TITLES[i % len(UNICODE_TITLES)]
        item = DiscoveredMediaItem(
            index=i,
            source_path=f"C:\\downloads\\batch{i // 50}\\file_{i}{extension}",
            relative_path=f"batch{i // 50}/file_{i}{extension}",
            extension=extension,
            size=1000 + i,
        )
        metadata = NormalizedMetadata(number=canonical, title=title, actors=(f"actor_{i}",))
        specs.append((item, canonical, metadata))
    return specs


SYNTHETIC_ITEMS = _build_synthetic_items(400)


def test_synthetic_gate_all_plans_deterministic_on_replay():
    plans_first = [
        build_organize_plan(item, canonical, metadata, LIBRARY_ROOT)
        for item, canonical, metadata in SYNTHETIC_ITEMS
    ]
    plans_second = [
        build_organize_plan(item, canonical, metadata, LIBRARY_ROOT)
        for item, canonical, metadata in SYNTHETIC_ITEMS
    ]
    assert plans_first == plans_second


def test_synthetic_gate_all_targets_contained_in_library_root():
    for item, canonical, metadata in SYNTHETIC_ITEMS:
        plan = build_organize_plan(item, canonical, metadata, LIBRARY_ROOT)
        for planned in (
            plan.target_directory, plan.target_media_path, plan.nfo_path,
            plan.poster_path, plan.fanart_path, plan.thumb_path, plan.extrafanart_directory,
        ):
            assert planned.absolute_path.startswith(LIBRARY_ROOT + "\\"), planned.absolute_path


def test_synthetic_gate_zero_internal_collisions_across_unique_numbers():
    seen_media_targets: set[str] = set()
    for item, canonical, metadata in SYNTHETIC_ITEMS:
        plan = build_organize_plan(item, canonical, metadata, LIBRARY_ROOT)
        key = plan.target_media_path.absolute_path.casefold()
        assert key not in seen_media_targets, f"unexpected collision at {key}"
        seen_media_targets.add(key)
    assert len(seen_media_targets) == len(SYNTHETIC_ITEMS)


def test_synthetic_gate_unicode_titles_never_leak_into_target_paths():
    for item, canonical, metadata in SYNTHETIC_ITEMS:
        plan = build_organize_plan(item, canonical, metadata, LIBRARY_ROOT)
        assert metadata.title not in plan.target_directory.absolute_path
        assert metadata.title not in plan.target_media_path.absolute_path


def test_synthetic_gate_custom_policy_does_not_break_containment_or_determinism():
    policy = OutputPolicy(
        poster_filename="cover.jpg", fanart_filename="backdrop.jpg", thumb_filename="preview.jpg",
    )
    for item, canonical, metadata in SYNTHETIC_ITEMS[:100]:
        plan_a = build_organize_plan(item, canonical, metadata, LIBRARY_ROOT, policy=policy)
        plan_b = build_organize_plan(item, canonical, metadata, LIBRARY_ROOT, policy=policy)
        assert plan_a == plan_b
        assert plan_a.poster_path.absolute_path.endswith("cover.jpg")
        assert plan_a.poster_path.absolute_path.startswith(LIBRARY_ROOT + "\\")


def test_synthetic_gate_zero_filesystem_mutation(tmp_path):
    library_root = str(tmp_path / "library")
    for item, canonical, metadata in SYNTHETIC_ITEMS:
        build_organize_plan(item, canonical, metadata, library_root)
    assert not os.path.exists(library_root)


def test_synthetic_gate_no_network_import_reachable():
    import ast
    import pathlib as _pathlib

    planning_src = _pathlib.Path(__file__).resolve().parents[2] / "src" / "fc2_organizer" / "planning"
    forbidden = {"socket", "httpx", "urllib", "requests", "asyncio"}
    for path in sorted(planning_src.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name.split(".")[0] not in forbidden, f"{path}: forbidden import {alias.name}"
            elif isinstance(node, ast.ImportFrom) and node.module:
                assert node.module.split(".")[0] not in forbidden, f"{path}: forbidden import {node.module}"
