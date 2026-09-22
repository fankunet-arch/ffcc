"""Contract test: ``fc2_organizer.nfo`` architecture boundary (P4-C4 contract section 15).

Allowed dependencies (and nothing else):

* ``fc2_organizer.publication`` -- the public package only (``PublicationRecord``);
* standard library: ``__future__``, ``re``, ``datetime``;
* its own modules.

Never: ``fc2_metadata_core`` (any module, directly), ``amane``, ``fc2_organizer.planning`` /
``discovery`` directly, any filesystem / network / clock / randomness / XML-library module.
Never the reverse either: ``fc2_metadata_core``, ``planning``, ``discovery`` and ``publication``
never import ``nfo``; ``fc2_organizer/__init__.py`` does not eagerly import it.
"""

from __future__ import annotations

import ast
import importlib
import sys
from pathlib import Path

import pytest

SRC_ROOT = Path(__file__).resolve().parents[2] / "src"
NFO_SRC_ROOT = SRC_ROOT / "fc2_organizer" / "nfo"
ORGANIZER_SRC_ROOT = SRC_ROOT / "fc2_organizer"
CORE_SRC_ROOT = SRC_ROOT / "fc2_metadata_core"

_ALLOWED_PROJECT_MODULES = {"fc2_organizer.publication"}
_ALLOWED_STDLIB = {"__future__", "re", "datetime"}
_FORBIDDEN_CALL_NAMES = {
    "open", "mkdir", "makedirs", "rename", "replace", "remove", "unlink", "rmdir", "write", "write_text",
    "write_bytes", "touch", "exists", "stat", "lstat", "resolve", "realpath", "move", "copy", "copyfile",
    "copytree", "rmtree", "urlopen", "socket", "create_connection", "get", "post", "request", "send",
    "print", "uuid4", "random", "time", "monotonic", "now", "today", "utcnow", "getenv", "getcwd",
    "unescape", "escape", "CDATA",
}
_FORBIDDEN_NAMES_IN_SOURCE = ("html.", "import html", "CDATA", "os.environ", "locale")


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


def test_nfo_source_root_exists_and_has_exactly_the_three_modules():
    assert NFO_SRC_ROOT.is_dir()
    assert {p.name for p in _source_files(NFO_SRC_ROOT)} == {"__init__.py", "errors.py", "renderer.py"}


@pytest.mark.parametrize("path", _source_files(NFO_SRC_ROOT), ids=lambda p: p.name)
def test_nfo_imports_only_publication_public_api_and_minimal_stdlib(path: Path):
    for module in _imported_modules(_tree(path)):
        if module.startswith("fc2_organizer.nfo"):
            continue
        assert module in _ALLOWED_PROJECT_MODULES or module in _ALLOWED_STDLIB, (
            f"{path.name}: import of {module!r} is outside the nfo boundary's allowed dependencies"
        )


@pytest.mark.parametrize("path", _source_files(NFO_SRC_ROOT), ids=lambda p: p.name)
def test_nfo_has_no_direct_core_sources_http_batch_resource_discovery_or_amane_dependency(path: Path):
    for module in _imported_modules(_tree(path)):
        assert not module.startswith("fc2_metadata_core"), f"{path.name}: direct core import {module!r}"
        assert not module.startswith(("amane", "fc2_organizer.discovery", "fc2_organizer.planning")), module
        assert not module.startswith(("xml", "lxml", "html", "os", "pathlib", "io", "socket", "urllib", "httpx",
                                      "requests", "time", "random", "uuid", "locale", "shutil")), module
    text = path.read_text(encoding="utf-8")
    assert "import amane" not in text and "from amane" not in text


@pytest.mark.parametrize("path", _source_files(NFO_SRC_ROOT), ids=lambda p: p.name)
def test_nfo_source_makes_no_io_clock_html_or_cdata_style_call(path: Path):
    for node in ast.walk(_tree(path)):
        if isinstance(node, ast.Call):
            func = node.func
            name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
            assert name not in _FORBIDDEN_CALL_NAMES, f"{path.name}:{node.lineno}: call to {name!r}"
    code_only = "\n".join(
        line for line in path.read_text(encoding="utf-8").splitlines() if not line.lstrip().startswith("#")
    )
    tree = _tree(path)
    docstrings = {
        ast.get_docstring(n, clean=False)
        for n in ast.walk(tree)
        if isinstance(n, (ast.Module, ast.FunctionDef, ast.ClassDef)) and ast.get_docstring(n, clean=False)
    }
    for doc in docstrings:
        code_only = code_only.replace(doc, "")
    for forbidden in _FORBIDDEN_NAMES_IN_SOURCE:
        assert forbidden not in code_only, f"{path.name}: {forbidden!r} in code"


def test_errors_module_is_stdlib_only():
    assert _imported_modules(_tree(NFO_SRC_ROOT / "errors.py")) <= {"__future__"}


def test_no_reverse_dependency_on_nfo_from_core_planning_discovery_or_publication():
    for root in (
        CORE_SRC_ROOT,
        ORGANIZER_SRC_ROOT / "planning",
        ORGANIZER_SRC_ROOT / "discovery",
        ORGANIZER_SRC_ROOT / "publication",
    ):
        for path in _source_files(root):
            for module in _imported_modules(_tree(path)):
                assert not module.startswith("fc2_organizer.nfo"), f"{path}: imports {module!r}"
            text = path.read_text(encoding="utf-8")
            assert "fc2_organizer.nfo" not in text and "render_movie_nfo" not in text, path


def test_top_level_organizer_init_does_not_eagerly_import_nfo():
    tree = _tree(ORGANIZER_SRC_ROOT / "__init__.py")
    for module in _imported_modules(tree):
        assert "nfo" not in module
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            assert all(alias.name != "nfo" for alias in node.names)


class _BlockAmaneFinder:
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "amane" or fullname.startswith("amane."):
            raise ImportError(f"fc2_organizer.nfo attempted to import forbidden module: {fullname}")
        return None


def _purge() -> None:
    for name in list(sys.modules):
        if name.split(".")[0] in {"fc2_organizer", "fc2_metadata_core"}:
            del sys.modules[name]


def test_bare_import_of_fc2_organizer_loads_neither_nfo_nor_publication_nor_core():
    _purge()
    try:
        importlib.import_module("fc2_organizer")
        assert "fc2_organizer.nfo" not in sys.modules
        assert "fc2_organizer.publication" not in sys.modules
        assert not any(name.split(".")[0] == "fc2_metadata_core" for name in sys.modules)
    finally:
        _purge()


def test_explicit_import_of_fc2_organizer_nfo_works_and_renders_with_amane_blocked():
    _purge()
    blocker = _BlockAmaneFinder()
    sys.meta_path.insert(0, blocker)
    try:
        nfo = importlib.import_module("fc2_organizer.nfo")
        from fc2_organizer.nfo import render_movie_nfo  # noqa: F401 - the documented import form

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
        record = publication.PublicationRecord(
            plan=plan, metadata=metadata, aggregate_status=aggregation.AggregateStatus.SUCCESS
        )
        xml = nfo.render_movie_nfo(record)
        assert xml.startswith('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<movie>\n')
        assert not any(name == "amane" or name.startswith("amane.") for name in sys.modules)
    finally:
        sys.meta_path.remove(blocker)
        _purge()


def test_nfo_public_api_is_exactly_the_renderer_and_the_error_classes():
    _purge()
    try:
        nfo = importlib.import_module("fc2_organizer.nfo")
        assert set(nfo.__all__) == {
            "render_movie_nfo", "NfoError", "NfoInputError", "NfoMetadataError", "NfoReleaseDateError",
            "NfoXmlCharacterError",
        }
        for forbidden in ("write", "save", "write_nfo", "download", "execute", "materialize"):
            assert not hasattr(nfo, forbidden)
    finally:
        _purge()


def test_organizer_package_now_has_exactly_discovery_planning_publication_and_nfo():
    """P4-C4 scope guard: no fifth package (writer, executor, downloader, ...) was started early."""
    top_level_dirs = {p.name for p in ORGANIZER_SRC_ROOT.iterdir() if p.is_dir() and p.name != "__pycache__"}
    assert top_level_dirs == {"discovery", "planning", "publication", "nfo"}
