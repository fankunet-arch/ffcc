"""Contract test: ``fc2_organizer.execution`` architecture boundary (P4-C7 contract section 3; plan S1).

* exact S1 module set; no ``directories`` / ``transfer`` / ``executor`` / ``rollback`` / ``orchestrator`` yet;
* per-module import allow-lists; only the *bare* ``fc2_organizer.planning`` / ``fc2_organizer.materialization``
  packages, never their submodules; never ``fc2_metadata_core`` (directly), ``amane``, ``httpx`` or any
  network module, ``discovery`` / ``images`` / ``nfo`` / ``publication``;
* no overwrite / removal / directory-management / globbing / path-guessing / rollback calls;
* no second FC2 parser, no ``mapping.extrafanart_filename`` / ``build_artifact_requests`` reference;
* ``os.<syscall>`` only inside the private seam ``_fs.py``; S1 production code reaches only the read-only
  part of the seam (zero mutation);
* no reverse dependency; ``fc2_organizer/__init__`` does not import it; the S1 public API is exactly the
  frozen contract section 4 set minus ``execute_filesystem`` (added in S5);
* at runtime, with ``amane`` / ``httpx`` / ``images`` / ``nfo`` / ``publication`` / ``mapping`` blocked, the
  package imports and a real preflight runs end to end.
"""

from __future__ import annotations

import ast
import importlib
import os
import sys
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[2] / "src"
ORGANIZER_SRC_ROOT = SRC_ROOT / "fc2_organizer"
EXEC_SRC_ROOT = ORGANIZER_SRC_ROOT / "execution"
CORE_SRC_ROOT = SRC_ROOT / "fc2_metadata_core"

_S1_MODULES = {"__init__.py", "errors.py", "models.py", "paths.py", "validation.py", "seal.py", "_fs.py",
               "preflight.py"}
_NOT_YET = ("directories.py", "transfer.py", "executor.py", "rollback.py", "orchestrator.py")

_PKG = "fc2_organizer.execution"
_BARE = {"fc2_organizer.planning", "fc2_organizer.materialization"}
_ALLOWED = {
    "__init__.py": {f"{_PKG}.errors", f"{_PKG}.models", f"{_PKG}.preflight"},
    "errors.py": {"__future__", "enum"},
    # models.py also imports the two bare authorised packages (S1 technical ruling: strict-type model checks
    # of plan / artifacts / artifact_kind, contract sections 16 and 27).
    "models.py": {"__future__", "dataclasses", "enum", "re", f"{_PKG}.errors"} | _BARE,
    "paths.py": {"__future__", "ntpath", "os", "posixpath", f"{_PKG}.errors"},
    "validation.py": {"__future__", "ntpath", "os", "posixpath", f"{_PKG}.errors", f"{_PKG}.models",
                      f"{_PKG}.paths"} | _BARE,
    "seal.py": {"__future__", "hashlib", "hmac", "secrets", "threading", f"{_PKG}.errors", f"{_PKG}.models"},
    "_fs.py": {"__future__", "dataclasses", "errno", "os", "secrets", "stat", "typing", f"{_PKG}.models"},
    "preflight.py": {"__future__", _PKG, f"{_PKG}.errors", f"{_PKG}.models", f"{_PKG}.seal",
                     f"{_PKG}.validation"} | _BARE,
}
_FORBIDDEN_PREFIXES = (
    "fc2_metadata_core", "amane", "httpx", "requests", "socket", "ssl", "http", "urllib", "shutil", "tempfile",
    "glob", "fnmatch", "pathlib", "asyncio", "subprocess", "ctypes", "time", "random",
    "fc2_organizer.discovery", "fc2_organizer.images", "fc2_organizer.nfo", "fc2_organizer.publication",
    "fc2_organizer.planning.", "fc2_organizer.materialization.",
)
_FORBIDDEN_CALLS = {
    "replace", "makedirs", "rmdir", "removedirs", "rmtree", "remove", "truncate", "ftruncate", "chmod", "utime",
    "copy", "copy2", "copyfile", "copytree", "move", "glob", "iglob", "fnmatch", "walk", "scandir",
    "expanduser", "expandvars", "getcwd", "chdir", "abspath", "realpath", "resolve", "normpath", "symlink",
    "system", "popen", "rollback", "undo", "revert", "print",
}
_FORBIDDEN_NAMES = {"is_valid_fc2_number", "normalize_fc2_number", "extrafanart_filename",
                    "build_artifact_requests", "build_organize_plan", "materialize_atomic_bytes",
                    "materialize_artifact", "render_movie_nfo", "acquire_images", "prepare_publication"}
_LEXICAL_OS_PATH = {"join", "basename", "splitext", "dirname"}
_MUTATING_ATTRS = {"mkdir", "rename", "link", "unlink", "write", "fsync", "listdir", "open", "read", "close",
                   "fstat"}
_PREFLIGHT_FS_API = {"snapshot", "SnapshotRefused", "REFUSED_LINK", "REFUSED_SPECIAL", "new_token", "os_errno"}
_FROZEN_PUBLIC_API = {
    "preflight_execution", "execute_filesystem", "ExecutionPreflight", "ExecutionResult", "ExecutionCheckpoint",
    "ExecutionStatus", "ExecutionStep", "ExecutionUnit", "PreflightMode", "TransferMode", "EntryIdentity",
    "EntryType", "PathRole", "EffectKind", "CompletedEffect", "LeftoverTemporary", "PreflightBlocker",
    "PreflightBlockReason", "ExecutionFailure", "ExecutionFailureKind", "TransferStage", "ExecutionError",
    "ExecutionInputError", "ExecutionContractError", "PlanGraphError", "PlanGraphRejectionReason",
    "ArtifactManifestError", "ManifestRejectionReason", "CheckpointError", "CheckpointRejectionReason",
    "PreflightIntegrityError", "PreflightIntegrityReason", "PreflightNotReadyError", "ExecutionModelError",
}


def _files(root: Path) -> list[Path]:
    return sorted(root.rglob("*.py"))


def _tree(path: Path) -> ast.AST:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _imports(tree: ast.AST) -> set[str]:
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            modules.add(node.module or "")
    return modules


def _calls(tree: ast.AST):
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
            yield node.lineno, name, func


# --------------------------------------------------------------------------- static


def test_package_has_exactly_the_s1_modules():
    names = {p.name for p in _files(EXEC_SRC_ROOT)}
    assert names == _S1_MODULES
    for later in _NOT_YET:
        assert later not in names


def test_every_module_imports_only_its_allow_list():
    for path in _files(EXEC_SRC_ROOT):
        imported = _imports(_tree(path))
        assert imported <= _ALLOWED[path.name], (path.name, imported - _ALLOWED[path.name])


def test_no_forbidden_dependency():
    for path in _files(EXEC_SRC_ROOT):
        for module in _imports(_tree(path)):
            assert not module.startswith(_FORBIDDEN_PREFIXES), (path.name, module)
            if module.startswith("fc2_organizer.") and not module.startswith(_PKG):
                assert module in _BARE, (path.name, module)
        assert "os.environ" not in path.read_text(encoding="utf-8"), path.name


def test_no_overwrite_removal_directory_glob_guessing_or_rollback_calls():
    for path in _files(EXEC_SRC_ROOT):
        for lineno, name, _ in _calls(_tree(path)):
            assert name not in _FORBIDDEN_CALLS, f"{path.name}:{lineno}: call to {name!r}"


def test_no_second_fc2_parser_and_no_mapping_or_writer_reference():
    for path in _files(EXEC_SRC_ROOT):
        for node in ast.walk(_tree(path)):
            name = node.id if isinstance(node, ast.Name) else node.attr if isinstance(node, ast.Attribute) else None
            assert name not in _FORBIDDEN_NAMES, (path.name, name)
            if isinstance(node, ast.alias):
                assert node.name not in _FORBIDDEN_NAMES, (path.name, node.name)


def test_os_syscalls_only_inside_the_private_seam():
    for path in _files(EXEC_SRC_ROOT):
        if path.name == "_fs.py":
            continue
        for lineno, name, func in _calls(_tree(path)):
            if not isinstance(func, ast.Attribute):
                continue
            base = func.value
            if isinstance(base, ast.Name) and base.id == "os":
                raise AssertionError(f"{path.name}:{lineno}: os.{name}() outside the seam")
            if (isinstance(base, ast.Attribute) and base.attr == "path" and isinstance(base.value, ast.Name)
                    and base.value.id == "os"):
                assert name in _LEXICAL_OS_PATH, f"{path.name}:{lineno}: os.path.{name}()"


def test_s1_production_code_never_references_the_mutating_seam():
    for path in _files(EXEC_SRC_ROOT):
        if path.name == "_fs.py":
            continue
        for node in ast.walk(_tree(path)):
            if isinstance(node, ast.Attribute):
                assert node.attr not in _MUTATING_ATTRS, f"{path.name}:{node.lineno}: .{node.attr}"
    preflight_fs = {node.attr for node in ast.walk(_tree(EXEC_SRC_ROOT / "preflight.py"))
                    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name)
                    and node.value.id == "_fs"}
    assert preflight_fs <= _PREFLIGHT_FS_API, preflight_fs - _PREFLIGHT_FS_API


def test_seam_functions_reach_only_read_only_ops_in_s1():
    tree = _tree(EXEC_SRC_ROOT / "_fs.py")
    reached: dict[str, set[str]] = {}
    for fn in ast.walk(tree):
        if isinstance(fn, ast.FunctionDef):
            reached[fn.name] = {node.attr for node in ast.walk(fn)
                                if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name)
                                and node.value.id == "_FS"}
    used_by_preflight = {"snapshot", "_lstat_entry", "is_link", "is_directory", "is_regular_file",
                         "_identity_of", "new_token", "os_errno"}
    assert used_by_preflight <= set(reached), used_by_preflight - set(reached)
    for name in used_by_preflight:
        assert reached.get(name, set()) <= {"lstat", "device_of", "token"}, (name, reached.get(name))


def test_no_reverse_dependency_on_execution():
    for root in (CORE_SRC_ROOT, *(p for p in ORGANIZER_SRC_ROOT.iterdir() if p.is_dir() and p != EXEC_SRC_ROOT)):
        for path in _files(root):
            for module in _imports(_tree(path)):
                assert not module.startswith(_PKG), f"{path}: imports {module!r}"
    for module in _imports(_tree(ORGANIZER_SRC_ROOT / "__init__.py")):
        assert "execution" not in module


# --------------------------------------------------------------------------- runtime

_BLOCKED_ROOTS = {"amane", "httpx", "requests"}
_BLOCKED_PREFIXES = ("fc2_organizer.images", "fc2_organizer.nfo", "fc2_organizer.publication",
                     "fc2_organizer.materialization.mapping")


class _BlockFinder:
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".")[0] in _BLOCKED_ROOTS or fullname.startswith(_BLOCKED_PREFIXES):
            raise ImportError(f"fc2_organizer.execution attempted to import forbidden module: {fullname}")
        return None


def _purge() -> None:
    for name in list(sys.modules):
        if name.split(".")[0] in {"fc2_organizer", "fc2_metadata_core"}:
            del sys.modules[name]


def test_bare_import_of_fc2_organizer_does_not_load_execution():
    _purge()
    try:
        importlib.import_module("fc2_organizer")
        assert _PKG not in sys.modules
    finally:
        _purge()


def test_public_api_is_the_frozen_set_minus_execute_filesystem():
    _purge()
    try:
        execution = importlib.import_module(_PKG)
        assert set(execution.__all__) == _FROZEN_PUBLIC_API - {"execute_filesystem"}
        assert not hasattr(execution, "execute_filesystem")
        for name in execution.__all__:
            assert hasattr(execution, name), name
        for private in ("_FS", "seal_of", "register_consumption", "PathRejectionReason", "validate_plan"):
            assert private not in execution.__all__
    finally:
        _purge()


def test_execution_imports_and_preflights_with_forbidden_modules_blocked(tmp_path):
    _purge()
    saved = {name: sys.modules.pop(name) for name in list(sys.modules) if name.split(".")[0] in _BLOCKED_ROOTS}
    blocker = _BlockFinder()
    sys.meta_path.insert(0, blocker)
    try:
        execution = importlib.import_module(_PKG)
        planning = importlib.import_module("fc2_organizer.planning")
        materialization = importlib.import_module("fc2_organizer.materialization")
        discovery = importlib.import_module("fc2_organizer.discovery")
        core_models = importlib.import_module("fc2_metadata_core.models")

        library = tmp_path / "library"
        library.mkdir()
        source = tmp_path / "dl" / "raw.mp4"
        source.parent.mkdir()
        source.write_bytes(b"media")
        item = discovery.DiscoveredMediaItem(index=0, source_path=str(source), relative_path="raw.mp4",
                                             extension=".mp4", size=5)
        plan = planning.build_organize_plan(item, "FC2-1234567",
                                            core_models.NormalizedMetadata(number="FC2-1234567", title="t"),
                                            str(library))
        manifest = (materialization.ArtifactWriteRequest(materialization.ArtifactKind.NFO,
                                                         plan.nfo_path.absolute_path, b"<movie/>"),)
        preflight = execution.preflight_execution(plan, manifest)
        assert preflight.ready and not os.path.lexists(plan.target_directory.absolute_path)
        loaded = set(sys.modules)
        assert not any(n.split(".")[0] in _BLOCKED_ROOTS or n.startswith(_BLOCKED_PREFIXES) for n in loaded)
    finally:
        sys.meta_path.remove(blocker)
        _purge()
        sys.modules.update(saved)
