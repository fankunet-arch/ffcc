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

import ast as _ast
import os
import pathlib as _pathlib
from collections.abc import Sequence

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


def _planning_src_root() -> _pathlib.Path:
    """The real ``fc2_organizer/planning`` production source directory.

    ``P4-C2-GOV-01``: this file lives at
    ``fc2-organizer/tests/unit/planning/test_planning_synthetic_gate.py``.
    ``.parents``, counted from this file (index 0), are: ``[0] tests/unit/planning``,
    ``[1] tests/unit``, ``[2] tests``, ``[3] fc2-organizer``. The original
    version of this guard used ``parents[2]`` (copied from
    ``tests/contract/test_planning_architecture.py``, where that file is one
    directory shallower -- ``tests/contract`` -- so ``parents[2]`` is correct
    *there*, but wrong here) and so resolved to a nonexistent
    ``tests/src/fc2_organizer/planning``, silently glob-matching zero files.
    The fix is ``parents[3]``, verified non-vacuous by
    ``test_synthetic_gate_planning_src_root_resolves_and_has_production_files``
    below rather than trusted by inspection alone.
    """
    return _pathlib.Path(__file__).resolve().parents[3] / "src" / "fc2_organizer" / "planning"


_FORBIDDEN_NETWORK_IMPORTS = {"socket", "httpx", "urllib", "requests", "asyncio"}


def _scan_forbidden_imports(paths: Sequence[_pathlib.Path], forbidden: set[str]) -> list[str]:
    """Pure AST scan: return one description string per forbidden top-level
    import found in any of ``paths``. Used both for the real production-code
    guard and for the planted-import self-tests below (``_scan_forbidden_imports``
    itself is exercised against known-bad and known-good input, not just
    trusted to work correctly on the one input that happens to currently be
    clean)."""
    violations: list[str] = []
    for path in paths:
        tree = _ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in _ast.walk(tree):
            if isinstance(node, _ast.Import):
                for alias in node.names:
                    top = alias.name.split(".")[0]
                    if top in forbidden:
                        violations.append(f"{path}: forbidden import {alias.name!r}")
            elif isinstance(node, _ast.ImportFrom) and node.module:
                top = node.module.split(".")[0]
                if top in forbidden:
                    violations.append(f"{path}: forbidden import {node.module!r}")
    return violations


def test_synthetic_gate_planning_src_root_resolves_and_has_production_files():
    """Guards against the exact P4-C2-GOV-01 regression: a wrong ``parents[N]``
    silently resolving to a nonexistent directory, so ``rglob`` yields zero
    files and every downstream assertion in a ``for path in ...`` loop never
    runs -- a vacuous PASS that proves nothing."""
    root = _planning_src_root()
    assert root.is_dir(), f"expected the real production source directory to exist at {root}"
    files = sorted(root.rglob("*.py"))
    assert len(files) > 0, (
        "planning source file set must not be empty -- a guard that scans "
        "zero files vacuously passes without checking anything (P4-C2-GOV-01)"
    )
    names = {f.name for f in files}
    assert {"__init__.py", "errors.py", "models.py", "paths.py", "planner.py", "policy.py"} <= names, (
        f"expected all known production modules to be present, got {names}"
    )


def test_synthetic_gate_no_network_import_reachable():
    root = _planning_src_root()
    files = sorted(root.rglob("*.py"))
    assert files, "no production files scanned -- this guard would be vacuous (P4-C2-GOV-01)"
    violations = _scan_forbidden_imports(files, _FORBIDDEN_NETWORK_IMPORTS)
    assert violations == [], "\n".join(violations)


def test_network_guard_fails_on_planted_import_statement(tmp_path):
    """Proves the guard actually detects a violation, not just that it
    passes on today's clean production code (P4-C2-GOV-01: 'must prove FAIL
    on planted forbidden import, not just PASS on correct code'). Writes to
    an isolated ``tmp_path`` file only -- never touches any production file
    -- and leaves nothing behind (pytest owns and cleans up ``tmp_path``)."""
    planted = tmp_path / "hostile_import_statement.py"
    planted.write_text("import socket\n", encoding="utf-8")

    violations = _scan_forbidden_imports([planted], _FORBIDDEN_NETWORK_IMPORTS)

    assert violations, "guard failed to detect a planted 'import socket'"
    assert "socket" in violations[0]


def test_network_guard_fails_on_planted_import_from_form(tmp_path):
    """Same proof for the ``from X import Y`` form specifically -- a scan
    that only inspects ``ast.Import`` (never ``ast.ImportFrom``) would miss
    ``from urllib import request`` entirely."""
    planted = tmp_path / "hostile_import_from.py"
    planted.write_text("from urllib import request\n", encoding="utf-8")

    violations = _scan_forbidden_imports([planted], _FORBIDDEN_NETWORK_IMPORTS)

    assert violations, "guard failed to detect a planted 'from urllib import request'"
    assert "urllib" in violations[0]


def test_network_guard_does_not_false_positive_on_ordinary_stdlib_imports(tmp_path):
    """The other failure mode is a guard so broad it flags legitimate code.
    Proves ordinary, allowed imports (including ones this very package
    uses -- ``os``, ``dataclasses``, ``pathlib``) never trip it."""
    planted = tmp_path / "benign_imports.py"
    planted.write_text(
        "import os\nimport pathlib\nfrom dataclasses import dataclass\nfrom enum import Enum\n",
        encoding="utf-8",
    )

    violations = _scan_forbidden_imports([planted], _FORBIDDEN_NETWORK_IMPORTS)

    assert violations == []
