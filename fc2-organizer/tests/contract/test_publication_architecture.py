"""Contract test: ``fc2_organizer.publication`` architecture boundary (P4-C3 contract section 15).

Allowed dependencies (and nothing else outside the standard library):

* ``fc2_organizer.planning`` -- the public package only;
* ``fc2_metadata_core.aggregation`` -- the public package only (``AggregationResult`` / ``AggregateStatus``);
* ``fc2_metadata_core.models`` -- the public package only (``NormalizedMetadata``);
* its own modules.

Never: ``amane``, source adapters, the HTTP transport, resource control, batch, aggregation internals
(engine / execution / retry / merge modules), discovery, any filesystem / network / clock / randomness module.
Never the reverse either: neither ``fc2_metadata_core`` nor the earlier organizer packages import publication.

Same pattern as ``test_planning_architecture.py``: a static AST scan, plus a runtime proof with ``amane``
blocked at the meta-path level while ``prepare_publication`` runs end to end. (Blocking the core's other
submodules at runtime is not meaningful: ``fc2_metadata_core/__init__.py`` eagerly imports all of them.)
"""

from __future__ import annotations

import ast
import importlib
import sys
from pathlib import Path

import pytest

SRC_ROOT = Path(__file__).resolve().parents[2] / "src"
PUBLICATION_SRC_ROOT = SRC_ROOT / "fc2_organizer" / "publication"
ORGANIZER_SRC_ROOT = SRC_ROOT / "fc2_organizer"
CORE_SRC_ROOT = SRC_ROOT / "fc2_metadata_core"

_ALLOWED_PROJECT_MODULES = {
    "fc2_organizer.planning",
    "fc2_metadata_core.aggregation",
    "fc2_metadata_core.models",
}
_ALLOWED_STDLIB = {"__future__", "dataclasses"}
_FORBIDDEN_CALL_NAMES = {
    "open", "mkdir", "makedirs", "rename", "replace", "remove", "unlink", "rmdir", "write", "write_text",
    "write_bytes", "touch", "exists", "stat", "lstat", "resolve", "realpath", "move", "copy", "copyfile",
    "copytree", "rmtree", "urlopen", "socket", "create_connection", "get", "post", "request", "send",
    "print", "uuid4", "random", "time", "monotonic",
}


def _source_files(root: Path) -> list[Path]:
    return sorted(root.rglob("*.py"))


def _imported_modules(tree: ast.AST) -> set[str]:
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            modules.add(node.module or "")
    return modules


def _tree(path: Path) -> ast.AST:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def test_publication_source_root_exists_and_has_files():
    assert PUBLICATION_SRC_ROOT.is_dir()
    assert {p.name for p in _source_files(PUBLICATION_SRC_ROOT)} == {
        "__init__.py", "boundary.py", "errors.py", "models.py",
    }


@pytest.mark.parametrize("path", _source_files(PUBLICATION_SRC_ROOT), ids=lambda p: p.name)
def test_publication_imports_only_allowed_modules(path: Path):
    for module in _imported_modules(_tree(path)):
        if module.startswith("fc2_organizer.publication"):
            continue
        assert module in _ALLOWED_PROJECT_MODULES or module in _ALLOWED_STDLIB, (
            f"{path.name}: import of {module!r} is outside the publication boundary's allowed dependencies"
        )


@pytest.mark.parametrize("path", _source_files(PUBLICATION_SRC_ROOT), ids=lambda p: p.name)
def test_publication_source_makes_no_io_style_call(path: Path):
    for node in ast.walk(_tree(path)):
        if isinstance(node, ast.Call):
            func = node.func
            name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
            assert name not in _FORBIDDEN_CALL_NAMES, f"{path.name}:{node.lineno}: call to {name!r}"


@pytest.mark.parametrize("path", _source_files(PUBLICATION_SRC_ROOT), ids=lambda p: p.name)
def test_publication_errors_module_is_stdlib_only_and_nothing_mentions_amane(path: Path):
    text = path.read_text(encoding="utf-8")
    assert "import amane" not in text and "from amane" not in text
    if path.name == "errors.py":
        assert _imported_modules(_tree(path)) <= {"__future__"}


def test_no_reverse_dependency_from_the_core_or_earlier_organizer_packages():
    for root in (CORE_SRC_ROOT, ORGANIZER_SRC_ROOT / "planning", ORGANIZER_SRC_ROOT / "discovery"):
        for path in _source_files(root):
            for module in _imported_modules(_tree(path)):
                assert not module.startswith("fc2_organizer.publication"), f"{path}: imports {module!r}"
                if root == CORE_SRC_ROOT:
                    assert not module.startswith("fc2_organizer"), f"{path}: core imports {module!r}"


def test_top_level_organizer_init_does_not_eagerly_import_publication():
    tree = _tree(ORGANIZER_SRC_ROOT / "__init__.py")
    for module in _imported_modules(tree):
        assert "publication" not in module
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            assert all(alias.name != "publication" for alias in node.names)


class _BlockAmaneFinder:
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "amane" or fullname.startswith("amane."):
            raise ImportError(f"fc2_organizer.publication attempted to import forbidden module: {fullname}")
        return None


def _purge() -> None:
    for name in list(sys.modules):
        if name.split(".")[0] in {"fc2_organizer", "fc2_metadata_core"}:
            del sys.modules[name]


def test_importing_fc2_organizer_does_not_load_publication():
    _purge()
    try:
        importlib.import_module("fc2_organizer")
        assert "fc2_organizer.publication" not in sys.modules
    finally:
        _purge()


def test_prepare_publication_runs_end_to_end_with_amane_blocked_at_runtime():
    _purge()
    blocker = _BlockAmaneFinder()
    sys.meta_path.insert(0, blocker)
    try:
        discovery = importlib.import_module("fc2_organizer.discovery")
        models = importlib.import_module("fc2_metadata_core.models")
        aggregation = importlib.import_module("fc2_metadata_core.aggregation")
        planning = importlib.import_module("fc2_organizer.planning")
        publication = importlib.import_module("fc2_organizer.publication")

        number = "FC2-1234567"
        item = discovery.DiscoveredMediaItem(
            index=0, source_path=r"C:\downloads\a.mp4", relative_path="a.mp4", extension=".mp4", size=1,
        )
        metadata = models.NormalizedMetadata(number=number, title="Example")
        plan = planning.build_organize_plan(item, number, metadata, r"C:\library")
        result = models.SourceResult(source_id="a", status=models.SourceStatus.SUCCESS, metadata=metadata, elapsed_ms=1.0)
        aggregate = aggregation.merge_source_results(number, (result,), aggregation.AggregationPolicy(source_order=("a",)))
        record = publication.prepare_publication(plan, aggregate)
        assert record.number == number
        assert not any(name == "amane" or name.startswith("amane.") for name in sys.modules)
    finally:
        sys.meta_path.remove(blocker)
        _purge()


def test_amane_is_not_actually_installed_in_this_test_environment():
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("amane")


def test_organizer_package_now_has_exactly_discovery_planning_and_publication():
    """P4-C3 scope guard: no fourth package (renderer, executor, ...) was started early."""
    top_level_dirs = {p.name for p in ORGANIZER_SRC_ROOT.iterdir() if p.is_dir() and p.name != "__pycache__"}
    assert top_level_dirs == {"discovery", "planning", "publication", "nfo"}  # P4-C4 added nfo
