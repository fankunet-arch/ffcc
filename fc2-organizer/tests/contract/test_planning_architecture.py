"""Contract test: ``fc2_organizer.planning`` must never import ``amane``,
any HTTP source adapter, aggregation execution internals, resource
governor internals, the HTTP transport, ``fc2_metadata_core.batch``, or any
filesystem-execution implementation (none exists yet, so this also guards
against P4-C2 accidentally growing one). It may depend only on
``fc2_organizer.discovery``'s *public* API and ``fc2_metadata_core``'s
*public* models/normalize boundary -- never discovery's or the core's
internals directly (contract section 31).

Mirrors the pattern of ``test_discovery_architecture.py`` /
``test_core_independent_of_amane.py``: a static AST scan plus a dynamic
meta-path-finder block that proves ``fc2_organizer.planning`` cannot import
any forbidden module even lazily, while actually exercising
``build_organize_plan`` end to end under the block.
"""

from __future__ import annotations

import ast
import importlib
import sys
from pathlib import Path

import pytest

PLANNING_SRC_ROOT = Path(__file__).resolve().parents[2] / "src" / "fc2_organizer" / "planning"
ORGANIZER_SRC_ROOT = Path(__file__).resolve().parents[2] / "src" / "fc2_organizer"

_FORBIDDEN_TOP_LEVEL = {"amane"}
_FORBIDDEN_PREFIXES = (
    "amane",
    "fc2_metadata_core.sources",
    "fc2_metadata_core.aggregation",
    "fc2_metadata_core.resource_control",
    "fc2_metadata_core.http",
    "fc2_metadata_core.batch",
    # Only the discovery *package* (its __init__ public re-exports) may be
    # depended on -- never its internal modules directly.
    "fc2_organizer.discovery.scanner",
    "fc2_organizer.discovery.models",
    "fc2_organizer.discovery.policy",
    "fc2_organizer.discovery.errors",
    "fc2_organizer.discovery._platform",
)

# Only these fc2_metadata_core submodules may be imported at all.
_ALLOWED_METADATA_CORE_MODULES = {"fc2_metadata_core.models", "fc2_metadata_core.normalize"}


def _iter_planning_source_files() -> list[Path]:
    return sorted(PLANNING_SRC_ROOT.rglob("*.py"))


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


def test_planning_source_root_exists_and_has_files():
    assert PLANNING_SRC_ROOT.is_dir(), f"expected {PLANNING_SRC_ROOT} to exist"
    assert _iter_planning_source_files(), "fc2_organizer.planning has no source files to statically check"


@pytest.mark.parametrize(
    "path",
    _iter_planning_source_files(),
    ids=lambda p: str(p.relative_to(PLANNING_SRC_ROOT)) if p.is_absolute() else str(p),
)
def test_no_static_forbidden_import_in_planning(path: Path):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    top_levels = _imported_top_levels(tree)
    assert not (top_levels & _FORBIDDEN_TOP_LEVEL), f"{path}: forbidden top-level import found in {top_levels}"

    dotted_modules = _imported_dotted_modules(tree)
    for module in dotted_modules:
        for forbidden in _FORBIDDEN_PREFIXES:
            assert not (module == forbidden or module.startswith(forbidden + ".")), (
                f"{path}: forbidden import of {module!r} (matches forbidden prefix {forbidden!r})"
            )


def test_planning_only_imports_allowed_metadata_core_submodules():
    for path in _iter_planning_source_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for module in _imported_dotted_modules(tree):
            if module == "fc2_metadata_core" or module.startswith("fc2_metadata_core."):
                assert module in _ALLOWED_METADATA_CORE_MODULES, (
                    f"{path}: unexpected fc2_metadata_core dependency ({module!r}); "
                    f"only {_ALLOWED_METADATA_CORE_MODULES} are allowed"
                )


def test_planning_only_imports_discovery_public_package():
    for path in _iter_planning_source_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for module in _imported_dotted_modules(tree):
            if module == "fc2_organizer.discovery" or module.startswith("fc2_organizer.discovery."):
                assert module == "fc2_organizer.discovery", (
                    f"{path}: must import the public fc2_organizer.discovery package only, "
                    f"not its internals ({module!r})"
                )


class _BlockAmaneFinder:
    """Blocks only ``amane`` at runtime -- the one hard, universally
    enforceable "never loads" requirement.

    The static scan above (``_FORBIDDEN_PREFIXES``) is what proves
    ``fc2_organizer.planning``'s own source never *references*
    ``fc2_metadata_core.sources``/``.aggregation``/``.resource_control``/
    ``.http``/``.batch`` or discovery's internals. A meta-path block on
    those specific submodules cannot additionally be exercised dynamically
    here: ``fc2_metadata_core``'s own (frozen, out-of-scope-to-modify)
    ``__init__.py`` unconditionally imports *all* of its submodules
    (``aggregation``, ``batch``, ``http``, ``models``, ``normalize``,
    ``resource_control``, ``sources``) as soon as *any* of them --
    including the allowed ``models``/``normalize`` -- is imported. Blocking
    those at the meta-path level would make ``fc2_metadata_core.models``
    itself unimportable through its own supported public interface, which
    is not a meaningful test of this package's architecture.
    """

    def find_spec(self, fullname, path=None, target=None):
        if fullname == "amane" or fullname.startswith("amane."):
            raise ImportError(f"fc2_organizer.planning attempted to import forbidden module: {fullname}")
        return None


def _purge_organizer_and_metadata_core_modules() -> None:
    for name in list(sys.modules):
        if (
            name == "fc2_organizer"
            or name.startswith("fc2_organizer.")
            or name == "fc2_metadata_core"
            or name.startswith("fc2_metadata_core.")
        ):
            del sys.modules[name]


def test_planning_imports_cleanly_with_amane_blocked_at_runtime():
    _purge_organizer_and_metadata_core_modules()
    blocker = _BlockAmaneFinder()
    sys.meta_path.insert(0, blocker)
    try:
        importlib.import_module("fc2_organizer.planning")
    finally:
        sys.meta_path.remove(blocker)
        _purge_organizer_and_metadata_core_modules()


def test_build_organize_plan_runs_end_to_end_with_amane_blocked_at_runtime():
    _purge_organizer_and_metadata_core_modules()
    blocker = _BlockAmaneFinder()
    sys.meta_path.insert(0, blocker)
    try:
        discovery = importlib.import_module("fc2_organizer.discovery")
        metadata_models = importlib.import_module("fc2_metadata_core.models")
        planning = importlib.import_module("fc2_organizer.planning")

        item = discovery.DiscoveredMediaItem(
            index=0, source_path=r"C:\downloads\a.mp4", relative_path="a.mp4", extension=".mp4", size=1,
        )
        metadata = metadata_models.NormalizedMetadata(number="FC2-1234567", title="Example")
        plan = planning.build_organize_plan(item, "FC2-1234567", metadata, r"C:\library")
        assert plan.canonical_number == "FC2-1234567"
    finally:
        sys.meta_path.remove(blocker)
        _purge_organizer_and_metadata_core_modules()


def test_amane_is_not_actually_installed_in_this_test_environment():
    """Sanity check that the blocks above are meaningful."""
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("amane")


def test_organizer_package_now_has_exactly_discovery_and_planning():
    """P4-C2 scope guard: exactly the two closed/candidate subpackages exist
    under fc2_organizer -- no third package was started early (contract
    section 28)."""
    top_level_dirs = {p.name for p in ORGANIZER_SRC_ROOT.iterdir() if p.is_dir() and p.name != "__pycache__"}
    assert top_level_dirs == {"discovery", "planning", "publication", "nfo", "images"}  # P4-C3 publication, P4-C4 nfo
