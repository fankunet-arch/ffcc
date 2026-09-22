"""Contract test: ``fc2_organizer.discovery`` must never import ``amane``,
any HTTP source adapter, aggregation execution internals, or resource
governor internals (contract section 18).

Mirrors the pattern of ``test_core_independent_of_amane.py``: a static AST
scan (catches an import buried in a function body or try/except) plus a
dynamic meta-path-finder block that proves discovery cannot import any of
the forbidden modules even lazily, while actually exercising
``discover_media`` end to end under the block.

``fc2_organizer.discovery`` currently depends on nothing from
``fc2_metadata_core`` at all (media identity here is the filesystem path,
not a parsed FC2 number -- see contract section 8), so the forbidden list
below is broader than strictly necessary today; it pins the *architecture*
(the allowed dependency direction is ``fc2_organizer -> fc2_metadata_core``,
never the reverse, and never through the internals named here) rather than
today's accidental zero-dependency state.
"""

from __future__ import annotations

import ast
import importlib
import sys
from pathlib import Path

import pytest

DISCOVERY_SRC_ROOT = Path(__file__).resolve().parents[2] / "src" / "fc2_organizer" / "discovery"
ORGANIZER_SRC_ROOT = Path(__file__).resolve().parents[2] / "src" / "fc2_organizer"

_FORBIDDEN_TOP_LEVEL = {"amane"}
_FORBIDDEN_PREFIXES = (
    "amane",
    "fc2_metadata_core.sources",
    "fc2_metadata_core.aggregation",
    "fc2_metadata_core.resource_control",
    "fc2_metadata_core.http",
)


def _iter_discovery_source_files() -> list[Path]:
    return sorted(DISCOVERY_SRC_ROOT.rglob("*.py"))


def _iter_organizer_source_files() -> list[Path]:
    return sorted(ORGANIZER_SRC_ROOT.rglob("*.py"))


def _module_name_from_source_file(path: Path) -> str:
    relative = path.relative_to(ORGANIZER_SRC_ROOT.parent).with_suffix("")
    parts = relative.parts
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def test_discovery_source_root_exists_and_has_files():
    assert DISCOVERY_SRC_ROOT.is_dir(), f"expected {DISCOVERY_SRC_ROOT} to exist"
    assert _iter_discovery_source_files(), "fc2_organizer.discovery has no source files to statically check"


def _imported_top_levels(tree: ast.AST) -> set[str]:
    top_levels: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top_levels.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            top_levels.add(module.split(".")[0])
    return top_levels


def _imported_dotted_modules(tree: ast.AST) -> set[str]:
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


@pytest.mark.parametrize(
    "path",
    _iter_discovery_source_files(),
    ids=lambda p: str(p.relative_to(DISCOVERY_SRC_ROOT)) if p.is_absolute() else str(p),
)
def test_no_static_forbidden_import_in_discovery(path: Path):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    top_levels = _imported_top_levels(tree)
    assert not (top_levels & _FORBIDDEN_TOP_LEVEL), f"{path}: forbidden top-level import found in {top_levels}"

    dotted_modules = _imported_dotted_modules(tree)
    for module in dotted_modules:
        for forbidden in _FORBIDDEN_PREFIXES:
            assert not (module == forbidden or module.startswith(forbidden + ".")), (
                f"{path}: forbidden import of {module!r} (matches forbidden prefix {forbidden!r})"
            )


def test_discovery_does_not_import_fc2_metadata_core_at_all():
    """Pins today's actual, stricter state: zero fc2_metadata_core dependency.

    If a future package (still P4, a later increment, or a later phase)
    legitimately needs ``fc2_metadata_core.normalize``, this specific test is
    the one to relax -- the forbidden-prefix tests above must still hold.
    """
    for path in _iter_discovery_source_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for module in _imported_dotted_modules(tree):
            assert not (module == "fc2_metadata_core" or module.startswith("fc2_metadata_core.")), (
                f"{path}: unexpected fc2_metadata_core dependency ({module!r})"
            )


class _BlockForbiddenFinder:
    def find_spec(self, fullname, path=None, target=None):
        if fullname in _FORBIDDEN_TOP_LEVEL or any(
            fullname == prefix or fullname.startswith(prefix + ".") for prefix in _FORBIDDEN_PREFIXES
        ):
            raise ImportError(f"fc2_organizer.discovery attempted to import forbidden module: {fullname}")
        return None


def _purge_organizer_modules() -> None:
    for name in list(sys.modules):
        if name == "fc2_organizer" or name.startswith("fc2_organizer."):
            del sys.modules[name]


def test_discovery_imports_cleanly_with_forbidden_modules_blocked_at_runtime():
    _purge_organizer_modules()
    blocker = _BlockForbiddenFinder()
    sys.meta_path.insert(0, blocker)
    try:
        importlib.import_module("fc2_organizer.discovery")
    finally:
        sys.meta_path.remove(blocker)
        _purge_organizer_modules()


def test_discover_media_runs_end_to_end_with_forbidden_modules_blocked_at_runtime(tmp_path):
    (tmp_path / "movie.mp4").write_text("x")

    _purge_organizer_modules()
    blocker = _BlockForbiddenFinder()
    sys.meta_path.insert(0, blocker)
    try:
        discovery = importlib.import_module("fc2_organizer.discovery")
        result = discovery.discover_media(tmp_path)
        assert result.total_items == 1
    finally:
        sys.meta_path.remove(blocker)
        _purge_organizer_modules()


def test_amane_is_not_actually_installed_in_this_test_environment():
    """Sanity check that the blocks above are meaningful."""
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("amane")


def test_organizer_package_has_no_other_stray_top_level_modules_yet():
    """P4-C1 scope guard: originally pinned "only discovery exists yet"
    (its own docstring anticipated a next package). P4-C2 added
    ``fc2_organizer.planning`` as a sibling, read-only-consuming package
    (never modifying discovery); this assertion is updated accordingly --
    see ``tests/contract/test_planning_architecture.py`` for the equivalent
    P4-C2-side guard and ``docs/review/P4_C2_HANDOFF.md`` for why this one
    line in an otherwise-frozen P4-C1 file was touched."""
    top_level_dirs = {p.name for p in ORGANIZER_SRC_ROOT.iterdir() if p.is_dir() and p.name != "__pycache__"}
    assert top_level_dirs == {"discovery", "planning"}
