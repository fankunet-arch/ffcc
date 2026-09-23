"""Contract test: ``fc2_organizer.materialization`` architecture boundary (P4-C6 contract section 12).

Substep 1 is a standalone, stdlib-only primitive:

* allowed imports: ``__future__``, ``dataclasses``, ``enum``, ``errno``, ``hashlib``, ``ntpath``,
  ``os``, ``posixpath``, ``re``, ``secrets``, ``stat``, ``typing`` and its own modules;
* never ``fc2_metadata_core``, ``amane``, ``httpx`` / any network module, ``shutil`` / ``tempfile`` /
  ``glob`` / ``fnmatch`` / ``pathlib``, or any other ``fc2_organizer`` package (planning, nfo, images,
  publication, discovery) -- the primitive knows nothing about plans, NFO or images;
* never ``os.replace``, never any directory creation / removal / listing / globbing call;
* nothing else in ``src`` imports ``materialization``; ``fc2_organizer/__init__.py`` does not
  eagerly import it; no executor / planner / move / orchestrator module exists.

Substep-2 exception (frozen): ``mapping.py`` is the **only** module that may import another
``fc2_organizer`` package, and only the ``fc2_organizer.planning`` / ``fc2_organizer.images``
*public* packages (never their submodules, never ``images.transport`` / ``images.acquisition``)
plus ``os`` (lexical ``os.path.join`` only). It never reads ``operations``, never writes, and is
not imported by ``materialization/__init__.py`` (``planning`` loads ``fc2_metadata_core``).
``artifacts.py`` (single-artifact wrapper) is stdlib/own-package only and only calls the primitive.
"""

from __future__ import annotations

import ast
import importlib
import sys
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[2] / "src"
ORGANIZER_SRC_ROOT = SRC_ROOT / "fc2_organizer"
MAT_SRC_ROOT = ORGANIZER_SRC_ROOT / "materialization"
CORE_SRC_ROOT = SRC_ROOT / "fc2_metadata_core"

_EXPECTED_MODULES = {"__init__.py", "errors.py", "models.py", "atomic.py", "artifacts.py", "mapping.py"}
_MAPPING_MODULE = "mapping.py"
_MAPPING_ALLOWED = {
    "__future__", "os", "fc2_organizer.images", "fc2_organizer.planning",
    "fc2_organizer.materialization.errors", "fc2_organizer.materialization.models",
}
_ARTIFACTS_ALLOWED = {
    "__future__", "fc2_organizer.materialization.atomic", "fc2_organizer.materialization.errors",
    "fc2_organizer.materialization.models",
}
_ALLOWED_STDLIB = {
    "__future__", "dataclasses", "enum", "errno", "hashlib", "ntpath", "os", "posixpath", "re",
    "secrets", "stat", "typing",
}
_PER_MODULE_ALLOWED = {
    "errors.py": {"__future__", "enum"},
    "models.py": {"__future__", "dataclasses", "enum", "re", "fc2_organizer.materialization.errors"},
    "artifacts.py": _ARTIFACTS_ALLOWED,
}
_FOREIGN_NAMES = {
    "OrganizePlan", "PlannedOperation", "PlannedOperationKind", "AcquiredImage", "PublicationRecord",
    "render_movie_nfo",
}
# Call names that would mean overwrite, directory management, wildcard cleanup, path guessing,
# or plan orchestration inside this package.
_FORBIDDEN_CALL_NAMES = {
    "replace", "mkdir", "makedirs", "rmdir", "removedirs", "rmtree", "remove", "truncate", "ftruncate",
    "glob", "iglob", "fnmatch", "listdir", "scandir", "walk", "copy", "copy2", "copyfile", "copytree",
    "move", "expanduser", "expandvars", "getcwd", "chdir", "abspath", "realpath", "resolve", "normpath",
    "getenv", "urlopen", "print", "execute", "run", "apply",
}


def _source_files(root: Path) -> list[Path]:
    return sorted(root.rglob("*.py"))


def _tree(path: Path) -> ast.AST:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _imported_modules(tree: ast.AST) -> set[str]:
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            modules.add(node.module or "")
    return modules


def _call_names(tree: ast.AST) -> list[tuple[int, str | None, ast.AST]]:
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
            out.append((node.lineno, name, func))
    return out


def _non_mapping_files() -> list[Path]:
    return [p for p in _source_files(MAT_SRC_ROOT) if p.name != _MAPPING_MODULE]


def test_package_has_exactly_the_substep1_and_substep2_modules():
    assert MAT_SRC_ROOT.is_dir()
    names = {p.name for p in _source_files(MAT_SRC_ROOT)}
    assert names == _EXPECTED_MODULES
    for forbidden in ("executor.py", "planner.py", "move.py", "orchestrator.py"):
        assert forbidden not in names


def test_imports_only_allowed_stdlib_and_itself():
    for path in _non_mapping_files():
        for module in _imported_modules(_tree(path)):
            if module.startswith("fc2_organizer.materialization"):
                continue
            assert module in _ALLOWED_STDLIB, f"{path.name}: import of {module!r} is outside the boundary"


def test_errors_and_models_have_narrower_allow_lists():
    for name, allowed in _PER_MODULE_ALLOWED.items():
        assert _imported_modules(_tree(MAT_SRC_ROOT / name)) <= allowed, name


def test_no_forbidden_dependency_text():
    for path in _non_mapping_files():
        tree = _tree(path)
        for module in _imported_modules(tree):
            assert not module.startswith((
                "fc2_metadata_core", "amane", "httpx", "requests", "socket", "ssl", "http", "urllib",
                "shutil", "tempfile", "glob", "fnmatch", "pathlib", "asyncio", "threading",
                "fc2_organizer.planning", "fc2_organizer.nfo", "fc2_organizer.images",
                "fc2_organizer.publication", "fc2_organizer.discovery",
            )), (path.name, module)
        for node in ast.walk(tree):
            # no code references a plan / NFO / image / publication type
            assert not (isinstance(node, ast.Name) and node.id in _FOREIGN_NAMES), (path.name, node.id)
        assert "os.environ" not in path.read_text(encoding="utf-8"), path.name


def test_no_overwrite_directory_glob_or_path_guessing_calls():
    for path in _source_files(MAT_SRC_ROOT):
        for lineno, name, _ in _call_names(_tree(path)):
            assert name not in _FORBIDDEN_CALL_NAMES, f"{path.name}:{lineno}: call to {name!r}"


def test_os_rename_and_link_are_only_used_by_the_no_replace_publish():
    tree = _tree(MAT_SRC_ROOT / "atomic.py")
    sites = []
    for fn in ast.walk(tree):
        if isinstance(fn, ast.FunctionDef):
            for lineno, name, _ in _call_names(fn):
                if name in {"rename", "link"}:
                    sites.append((fn.name, name))
    assert sorted(sites) == [("_publish_no_replace", "link"), ("_publish_no_replace", "rename")]
    for path in _source_files(MAT_SRC_ROOT):
        if path.name != "atomic.py":
            assert all(name not in {"rename", "link", "unlink", "open"} for _, name, _ in _call_names(_tree(path)))


def test_unlink_is_only_reached_through_the_owned_temp_helper():
    tree = _tree(MAT_SRC_ROOT / "atomic.py")
    for fn in ast.walk(tree):
        if isinstance(fn, ast.FunctionDef) and fn.name != "_remove_owned_temp":
            for node in ast.walk(fn):
                if isinstance(node, ast.Attribute) and node.attr == "unlink":
                    raise AssertionError(f"{fn.name}: references .unlink outside _remove_owned_temp")


def test_temp_open_is_exclusive_create():
    import os

    from fc2_organizer.materialization import atomic

    assert atomic._TEMP_FLAGS & os.O_CREAT and atomic._TEMP_FLAGS & os.O_EXCL
    assert not atomic._TEMP_FLAGS & getattr(os, "O_TRUNC", 0)


def test_no_reverse_dependency_on_materialization():
    for root in (CORE_SRC_ROOT, *(p for p in ORGANIZER_SRC_ROOT.iterdir() if p.is_dir() and p != MAT_SRC_ROOT)):
        for path in _source_files(root):
            for module in _imported_modules(_tree(path)):
                assert "materialization" not in module, f"{path}: imports {module!r}"
    for module in _imported_modules(_tree(ORGANIZER_SRC_ROOT / "__init__.py")):
        assert "materialization" not in module


_BLOCKED_ROOTS = {
    "amane", "httpx", "requests", "socket", "ssl", "fc2_metadata_core", "shutil", "tempfile", "glob",
}
_BLOCKED_EXACT = {"urllib.request", "http.client"}
_BLOCKED_ORGANIZER = ("fc2_organizer.planning", "fc2_organizer.nfo", "fc2_organizer.images",
                      "fc2_organizer.publication")


class _BlockFinder:
    def find_spec(self, fullname, path=None, target=None):
        if (fullname.split(".")[0] in _BLOCKED_ROOTS or fullname in _BLOCKED_EXACT
                or fullname.startswith(_BLOCKED_ORGANIZER)):
            raise ImportError(f"fc2_organizer.materialization attempted to import forbidden module: {fullname}")
        return None


def _purge() -> None:
    for name in list(sys.modules):
        if name.split(".")[0] in {"fc2_organizer", "fc2_metadata_core"}:
            del sys.modules[name]


def test_materialization_imports_and_works_with_forbidden_modules_blocked(tmp_path):
    _purge()
    saved = {name: sys.modules.pop(name) for name in list(sys.modules)
             if name.split(".")[0] in _BLOCKED_ROOTS or name in _BLOCKED_EXACT}
    blocker = _BlockFinder()
    sys.meta_path.insert(0, blocker)
    try:
        mat = importlib.import_module("fc2_organizer.materialization")
        result = mat.materialize_atomic_bytes(str(tmp_path / "a.bin"), b"blocked-run")
        assert (tmp_path / "a.bin").read_bytes() == b"blocked-run" and result.size_bytes == 11
        loaded = set(sys.modules)
        assert not any(n.split(".")[0] in _BLOCKED_ROOTS or n in _BLOCKED_EXACT for n in loaded)
        assert not any(n.startswith(_BLOCKED_ORGANIZER) for n in loaded)
    finally:
        sys.meta_path.remove(blocker)
        _purge()
        sys.modules.update(saved)


def test_bare_import_of_fc2_organizer_does_not_load_materialization():
    _purge()
    try:
        importlib.import_module("fc2_organizer")
        assert "fc2_organizer.materialization" not in sys.modules
    finally:
        _purge()


def test_public_api_is_the_substep1_primitive_plus_substep2_single_artifact_api():
    _purge()
    try:
        mat = importlib.import_module("fc2_organizer.materialization")
        assert set(mat.__all__) == {
            "materialize_atomic_bytes", "MaterializedArtifact", "MaterializationError",
            "MaterializationInputError", "InvalidTargetPathError", "TargetPathRejectionReason",
            "MaterializationModelError", "ParentDirectoryError", "ParentDirectoryMissingError",
            "ParentNotDirectoryError", "ParentRejectionReason", "TargetExistsError", "TargetInaccessibleError",
            "TemporaryCreateError", "ArtifactWriteError", "ArtifactWriteStage", "ArtifactPublishError",
            "ArtifactCleanupError", "ArtifactMappingError", "MappingRejectionReason", "ArtifactKind",
            "ArtifactWriteRequest", "materialize_artifact",
        }
        assert "fc2_organizer.materialization.mapping" not in sys.modules
        assert "fc2_organizer.planning" not in sys.modules and "fc2_organizer.images" not in sys.modules
        assert not hasattr(mat, "build_artifact_requests")
        for deferred in ("materialize_plan", "materialize_nfo", "materialize_images", "execute", "move_media",
                         "ensure_directory", "overwrite", "materialize_all", "execute_plan", "apply_operations",
                         "transaction", "rollback_all"):
            assert not hasattr(mat, deferred)
    finally:
        _purge()


# --------------------------------------------------------------------------- substep 2


def test_mapping_imports_only_planning_and_images_public_packages():
    modules = _imported_modules(_tree(MAT_SRC_ROOT / _MAPPING_MODULE))
    assert modules <= _MAPPING_ALLOWED, modules - _MAPPING_ALLOWED
    for module in modules:
        assert not module.startswith((
            "fc2_metadata_core", "amane", "httpx", "fc2_organizer.images.", "fc2_organizer.planning.",
            "fc2_organizer.nfo", "fc2_organizer.publication", "fc2_organizer.discovery",
            "fc2_organizer.materialization.atomic", "fc2_organizer.materialization.artifacts",
        )), module


def test_mapping_is_pure_never_reads_operations_and_never_writes():
    tree = _tree(MAT_SRC_ROOT / _MAPPING_MODULE)
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            assert node.attr != "operations", f"mapping.py:{node.lineno}: reads .operations"
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            assert node.value != "operations", f"mapping.py:{node.lineno}: 'operations' literal"
    forbidden = _FORBIDDEN_CALL_NAMES | {
        "open", "stat", "lstat", "exists", "isdir", "isfile", "lexists", "link", "rename", "unlink",
        "materialize_atomic_bytes", "materialize_artifact", "render_movie_nfo", "acquire_images",
        "build_organize_plan", "is_valid_fc2_number", "normalize", "sha256", "token_hex", "now", "random",
    }
    for lineno, name, func in _call_names(tree):
        assert name not in forbidden, f"mapping.py:{lineno}: call to {name!r}"
        if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name) and func.value.id == "os":
            raise AssertionError(f"mapping.py:{lineno}: os.{func.attr} call")
        if (isinstance(func, ast.Attribute) and isinstance(func.value, ast.Attribute)
                and isinstance(func.value.value, ast.Name) and func.value.value.id == "os"):
            # the only os.* call is the lexical os.path.join
            assert (func.value.attr, func.attr) == ("path", "join"), (lineno, func.attr)


def test_artifacts_wrapper_only_calls_the_primitive():
    tree = _tree(MAT_SRC_ROOT / "artifacts.py")
    names = {name for _, name, _ in _call_names(tree)}
    assert names <= {"type", "MaterializationInputError", "materialize_atomic_bytes"}, names


def test_package_init_never_imports_mapping():
    modules = _imported_modules(_tree(MAT_SRC_ROOT / "__init__.py"))
    assert "fc2_organizer.materialization.mapping" not in modules
    assert not any(m.startswith(("fc2_organizer.planning", "fc2_organizer.images")) for m in modules)


class _BlockTransportFinder:
    def find_spec(self, fullname, path=None, target=None):
        if (fullname.split(".")[0] in {"amane", "httpx", "requests", "socket", "ssl"}
                or fullname in _BLOCKED_EXACT
                or fullname.startswith(("fc2_organizer.images.transport", "fc2_organizer.images.acquisition",
                                        "fc2_organizer.nfo", "fc2_organizer.publication"))):
            raise ImportError(f"materialization.mapping attempted to import forbidden module: {fullname}")
        return None


def test_mapping_works_with_transport_nfo_publication_and_amane_blocked():
    _purge()
    saved = {name: sys.modules.pop(name) for name in list(sys.modules)
             if name.split(".")[0] in {"amane", "httpx", "requests"}}
    blocker = _BlockTransportFinder()
    sys.meta_path.insert(0, blocker)
    try:
        mapping = importlib.import_module("fc2_organizer.materialization.mapping")
        images = importlib.import_module("fc2_organizer.images")
        planning = importlib.import_module("fc2_organizer.planning")
        assert mapping.extrafanart_filename(1) == "extrafanart-001.jpg"
        assert callable(mapping.build_artifact_requests) and images.ImageAcquisitionResult().extrafanart == ()
        assert hasattr(planning, "OrganizePlan")
        loaded = set(sys.modules)
        assert not any(n.startswith(("fc2_organizer.images.transport", "fc2_organizer.images.acquisition",
                                     "fc2_organizer.nfo", "fc2_organizer.publication", "httpx", "amane"))
                       for n in loaded)
    finally:
        sys.meta_path.remove(blocker)
        _purge()
        sys.modules.update(saved)
