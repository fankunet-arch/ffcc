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
_S2_MODULES = _S1_MODULES | {"directories.py"}
_S3_MODULES = _S2_MODULES | {"transfer.py"}
_S4_MODULES = _S3_MODULES | {"executor.py"}
_NOT_YET = ("rollback.py", "orchestrator.py")

_PKG = "fc2_organizer.execution"
_BARE = {"fc2_organizer.planning", "fc2_organizer.materialization"}
_ALLOWED = {
    "__init__.py": {f"{_PKG}.errors", f"{_PKG}.executor", f"{_PKG}.models", f"{_PKG}.preflight"},
    "errors.py": {"__future__", "enum"},
    # models.py also imports the two bare authorised packages (S1 technical ruling: strict-type model checks
    # of plan / artifacts / artifact_kind, contract sections 16 and 27).
    "models.py": {"__future__", "dataclasses", "enum", "re", f"{_PKG}.errors"} | _BARE,
    "paths.py": {"__future__", "ntpath", "os", "posixpath", f"{_PKG}.errors"},
    "validation.py": {"__future__", "ntpath", "os", "posixpath", f"{_PKG}.errors", f"{_PKG}.models",
                      f"{_PKG}.paths"} | _BARE,
    "seal.py": {"__future__", "hashlib", "hmac", "secrets", "threading", f"{_PKG}.errors", f"{_PKG}.models"},
    "_fs.py": {"__future__", "dataclasses", "errno", "os", "secrets", "stat", "typing", f"{_PKG}.models"},
    "preflight.py": {"__future__", _PKG, f"{_PKG}.directories", f"{_PKG}.errors", f"{_PKG}.models",
                     f"{_PKG}.seal", f"{_PKG}.validation"} | _BARE,
    # S2 (contract section 3 table: this package + errno / os / stat); never planning / materialization.
    "directories.py": {"__future__", "os", _PKG, f"{_PKG}.errors", f"{_PKG}.models"},
    # S3 (contract section 3 table: this package + errno / hashlib / os / stat); never planning / materialization.
    "transfer.py": {"__future__", "errno", "hashlib", "os", _PKG, f"{_PKG}.directories", f"{_PKG}.errors",
                    f"{_PKG}.models"},
    # S4 (contract section 3 table: this package + the bare public planning / materialization packages).
    "executor.py": {"__future__", _PKG, f"{_PKG}.directories", f"{_PKG}.errors", f"{_PKG}.models",
                    f"{_PKG}.paths", f"{_PKG}.preflight", f"{_PKG}.seal", f"{_PKG}.transfer",
                    f"{_PKG}.validation", "fc2_organizer.materialization"},
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
_PREFLIGHT_FS_API = {"snapshot", "SnapshotRefused", "REFUSED_LINK", "REFUSED_SPECIAL", "new_token", "os_errno",
                     "read_bounded"}
# S2: no deletion call anywhere in the production package (contract sections 20-22, 28).
_DELETION_CALLS = {"unlink", "remove", "rmdir", "rmtree", "removedirs"}
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


def test_package_has_exactly_the_s4_modules():
    names = {p.name for p in _files(EXEC_SRC_ROOT)}
    assert names == _S4_MODULES
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
    # S4: executor.py alone may reference `materialize_artifact` (its single call site is asserted below).
    for path in _files(EXEC_SRC_ROOT):
        forbidden = _FORBIDDEN_NAMES - ({"materialize_artifact"} if path.name == "executor.py" else set())
        for node in ast.walk(_tree(path)):
            name = node.id if isinstance(node, ast.Name) else node.attr if isinstance(node, ast.Attribute) else None
            assert name not in forbidden, (path.name, name)
            if isinstance(node, ast.alias):
                assert node.name not in forbidden, (path.name, node.name)


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


def test_mutating_seam_is_reached_only_by_the_exclusive_mkdir_helper():
    # Outside _fs.py and transfer.py (S3; its frozen sites are asserted below) the only mutating seam
    # attribute allowed anywhere is `.mkdir`, and only inside directories._mkdir_exclusive (S2).
    # preflight.py references no mutating attribute at all.
    mkdir_sites = []
    for path in _files(EXEC_SRC_ROOT):
        if path.name in {"_fs.py", "transfer.py"}:
            continue
        tree = _tree(path)
        for fn in ast.walk(tree):
            if isinstance(fn, ast.FunctionDef):
                for node in ast.walk(fn):
                    if isinstance(node, ast.Attribute) and node.attr == "mkdir":
                        mkdir_sites.append((path.name, fn.name))
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr in _MUTATING_ATTRS - {"mkdir"}:
                raise AssertionError(f"{path.name}:{node.lineno}: .{node.attr}")
    assert mkdir_sites == [("directories.py", "_mkdir_exclusive")], mkdir_sites
    preflight_fs = {node.attr for node in ast.walk(_tree(EXEC_SRC_ROOT / "preflight.py"))
                    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name)
                    and node.value.id == "_fs"}
    assert preflight_fs <= _PREFLIGHT_FS_API, preflight_fs - _PREFLIGHT_FS_API


def test_mkdir_is_exclusive_single_call_without_makedirs_or_exist_ok():
    tree = _tree(EXEC_SRC_ROOT / "directories.py")
    for node in ast.walk(tree):
        if isinstance(node, ast.keyword):
            assert node.arg not in {"exist_ok", "parents"}, node.arg
        if isinstance(node, ast.Name):
            assert node.id not in {"makedirs"}, node.id
    helper = next(fn for fn in ast.walk(tree) if isinstance(fn, ast.FunctionDef) and fn.name == "_mkdir_exclusive")
    calls = [node for node in ast.walk(helper)
             if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "mkdir"]
    assert len(calls) == 1 and len(calls[0].args) == 2 and not calls[0].keywords


def test_no_deletion_call_in_production_outside_the_frozen_transfer_sites():
    # S3: `unlink` exists only in transfer._remove_owned_temp / transfer._unlink_verified_source
    # (asserted exactly by test_transfer_mutation_sites_are_frozen); nothing else deletes anything.
    for path in _files(EXEC_SRC_ROOT):
        for lineno, name, _ in _calls(_tree(path)):
            if path.name == "transfer.py" and name == "unlink":
                continue
            assert name not in _DELETION_CALLS, f"{path.name}:{lineno}: deletion call {name!r}"


def test_listdir_only_through_list_names_and_reads_only_through_read_bounded():
    tree = _tree(EXEC_SRC_ROOT / "_fs.py")
    reached: dict[str, set[str]] = {}
    for fn in ast.walk(tree):
        if isinstance(fn, ast.FunctionDef):
            reached[fn.name] = {node.attr for node in ast.walk(fn)
                                if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name)
                                and node.value.id == "_FS"}
    users = {name for name, ops in reached.items() if "listdir" in ops}
    assert users == {"list_names"}, users
    readers = {name for name, ops in reached.items() if ops & {"open", "read", "close"}}
    assert readers == {"read_bounded"} and reached["read_bounded"] == {"open", "read", "close"}
    from fc2_organizer.execution import _fs

    import os as _os
    flags = _fs._READ_ONLY_FLAGS
    for write_flag in ("O_WRONLY", "O_RDWR", "O_CREAT", "O_TRUNC", "O_APPEND", "O_EXCL"):
        assert not flags & getattr(_os, write_flag, 0), write_flag


def test_seam_functions_used_by_preflight_reach_only_read_only_ops():
    tree = _tree(EXEC_SRC_ROOT / "_fs.py")
    reached: dict[str, set[str]] = {}
    for fn in ast.walk(tree):
        if isinstance(fn, ast.FunctionDef):
            reached[fn.name] = {node.attr for node in ast.walk(fn)
                                if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name)
                                and node.value.id == "_FS"}
    used_by_preflight = {"snapshot", "_lstat_entry", "is_link", "is_directory", "is_regular_file",
                         "_identity_of", "new_token", "os_errno", "list_names", "read_bounded"}
    assert used_by_preflight <= set(reached), used_by_preflight - set(reached)
    for name in used_by_preflight:
        assert reached.get(name, set()) <= {"lstat", "device_of", "token", "listdir", "open", "read", "close"}, (
            name, reached.get(name))


def test_no_reverse_dependency_on_execution():
    # P4-C8 (contract section 34.3): the orchestration package is the one authorised consumer; it is held to
    # the stricter test_orchestration_consumes_only_the_bare_execution_package below.
    exempt = (EXEC_SRC_ROOT, ORGANIZER_SRC_ROOT / "orchestration")
    for root in (CORE_SRC_ROOT, *(p for p in ORGANIZER_SRC_ROOT.iterdir() if p.is_dir() and p not in exempt)):
        for path in _files(root):
            for module in _imports(_tree(path)):
                assert not module.startswith(_PKG), f"{path}: imports {module!r}"
    for module in _imports(_tree(ORGANIZER_SRC_ROOT / "__init__.py")):
        assert "execution" not in module


def test_orchestration_consumes_only_the_bare_execution_package():
    # P4-C8 contract sections 6 and 34.3: only `from fc2_organizer.execution import <public name>`; never a
    # submodule (`_fs`, `seal`, `models`, `executor`, ...), never a private name, never the module object.
    orchestration_root = ORGANIZER_SRC_ROOT / "orchestration"
    assert orchestration_root.is_dir() and _files(orchestration_root)
    for path in _files(orchestration_root):
        for node in ast.walk(_tree(path)):
            if isinstance(node, ast.Import):
                assert not any(alias.name.startswith(_PKG) for alias in node.names), path.name
            elif isinstance(node, ast.ImportFrom) and (node.module or "").startswith(_PKG):
                assert node.module == _PKG, (path.name, node.module)
                names = {alias.name for alias in node.names}
                assert names <= _FROZEN_PUBLIC_API, (path.name, names - _FROZEN_PUBLIC_API)
            elif isinstance(node, ast.ImportFrom) and node.module == "fc2_organizer":
                assert "execution" not in {alias.name for alias in node.names}, path.name  # no module object
            elif isinstance(node, ast.Name):
                assert node.id not in {"_fs", "_FS", "seal", "seal_of", "register_consumption"}, path.name


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


def test_public_api_is_exactly_the_frozen_set():
    # S5: the final public API (contract section 4), no more and no less.
    _purge()
    try:
        execution = importlib.import_module(_PKG)
        assert len(execution.__all__) == len(set(execution.__all__)) == len(_FROZEN_PUBLIC_API) == 34
        assert set(execution.__all__) == _FROZEN_PUBLIC_API
        assert execution.execute_filesystem is importlib.import_module(f"{_PKG}.executor").execute_filesystem
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


# --------------------------------------------------------------------------- S3: transfer.py


def _attribute_sites(path: Path, attrs: set[str]) -> dict[str, set[str]]:
    """attr -> names of the innermost functions in which ``<x>.<attr>`` appears (module level: "<module>")."""
    sites: dict[str, set[str]] = {attr: set() for attr in attrs}

    def visit(node: ast.AST, owner: str) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                visit(child, child.name)
                continue
            if isinstance(child, ast.Attribute) and child.attr in attrs:
                sites[child.attr].add(owner)
            visit(child, owner)

    visit(_tree(path), "<module>")
    return sites


def _function(tree: ast.AST, name: str) -> ast.FunctionDef:
    return next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == name)


def test_transfer_mutation_sites_are_frozen():
    # Construction plan S3 item 4: unlink only in the two private helpers; rename / link only in the two
    # no-replace primitives; no mkdir / replace in transfer.py; no rename / link / unlink anywhere else.
    sites = _attribute_sites(EXEC_SRC_ROOT / "transfer.py", {"unlink", "rename", "link", "mkdir", "replace"})
    assert sites["unlink"] == {"_remove_owned_temp", "_unlink_verified_source"}, sites["unlink"]
    assert sites["rename"] == {"_same_volume_primitive", "_publish_no_replace"}, sites["rename"]
    assert sites["link"] == {"_same_volume_primitive", "_publish_no_replace"}, sites["link"]
    assert sites["mkdir"] == set() and sites["replace"] == set()
    for other in _files(EXEC_SRC_ROOT):
        if other.name in {"_fs.py", "transfer.py"}:
            continue
        found = _attribute_sites(other, {"unlink", "rename", "link"})
        assert found == {"unlink": set(), "rename": set(), "link": set()}, (other.name, found)
    tree = _tree(EXEC_SRC_ROOT / "transfer.py")
    for name in ("_remove_owned_temp", "_unlink_verified_source"):
        calls = [n for n in ast.walk(_function(tree, name)) if isinstance(n, ast.Call)
                 and isinstance(n.func, ast.Attribute) and n.func.attr == "unlink"]
        assert len(calls) == 1 and len(calls[0].args) == 1 and not calls[0].keywords, name


def test_unlink_verified_source_revalidates_before_unlinking():
    fn = _function(_tree(EXEC_SRC_ROOT / "transfer.py"), "_unlink_verified_source")
    body = fn.body[1:] if isinstance(fn.body[0], ast.Expr) else fn.body  # skip the docstring
    assert isinstance(body[0], ast.Assign) and isinstance(body[0].value, ast.Call)
    assert getattr(body[0].value.func, "id", None) == "_source_state"
    assert isinstance(body[1], ast.If) and isinstance(body[1].body[0], ast.Return)
    assert isinstance(body[2], ast.Try)  # the unlink comes only after the early return


def test_transfer_uses_no_replace_truncate_shutil_or_directory_walks():
    path = EXEC_SRC_ROOT / "transfer.py"
    tree = _tree(path)
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    attrs = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    for forbidden in ("replace", "O_TRUNC", "renameat", "renameat2", "rmtree", "rmdir", "makedirs", "walk",
                      "glob", "iglob", "scandir", "listdir", "list_names", "shutil", "copyfile", "sendfile",
                      "copy_file_range", "remove"):
        assert forbidden not in names and forbidden not in attrs, forbidden
    text = path.read_text(encoding="utf-8")
    assert "O_TRUNC" not in text.replace("never ``O_TRUNC``", "") and "shutil" not in text


def test_temp_flags_are_exclusive_create_without_truncate_and_source_flags_are_read_only():
    _purge()
    try:
        _fs = importlib.import_module(f"{_PKG}._fs")
        transfer = importlib.import_module(f"{_PKG}.transfer")
        _check_transfer_flags(_fs, transfer)
    finally:
        _purge()


def _check_transfer_flags(_fs, transfer) -> None:
    flags = transfer._TEMP_FLAGS
    assert flags & os.O_CREAT and flags & os.O_EXCL and flags & os.O_WRONLY
    for bad in ("O_TRUNC", "O_APPEND", "O_RDWR"):
        assert not flags & getattr(os, bad, 0), bad
    assert transfer._CHUNK == 1 << 20 and transfer._MAX_TEMP_ATTEMPTS == 8 and transfer._TEMP_MODE == 0o666
    for write_flag in ("O_WRONLY", "O_RDWR", "O_CREAT", "O_TRUNC", "O_APPEND", "O_EXCL"):
        assert not _fs._READ_ONLY_FLAGS & getattr(os, write_flag, 0), write_flag
        assert not transfer._DIRECTORY_FLAGS & getattr(os, write_flag, 0), write_flag
    assert _fs._READ_ONLY_FLAGS & getattr(os, "O_NOFOLLOW", 0) == getattr(os, "O_NOFOLLOW", 0)
    assert transfer._SAME_VOLUME_STRATEGY == ("rename" if os.name == "nt" else "link")
    assert transfer._DIRECTORY_FSYNC is (os.name != "nt")


def test_transfer_translates_only_oserror_and_reraises_fatal_exceptions():
    # Contract section 29: only OSError becomes a typed failure. `except BaseException` appears only on the
    # fatal cleanup paths, which either re-raise the same object (bare `raise`) or swallow cleanup noise.
    tree = _tree(EXEC_SRC_ROOT / "transfer.py")
    owners: dict[str, set[str]] = {}
    for fn in ast.walk(tree):
        if not isinstance(fn, ast.FunctionDef):
            continue
        for node in ast.walk(fn):
            if isinstance(node, ast.ExceptHandler):
                caught = node.type.id if isinstance(node.type, ast.Name) else ast.dump(node.type or ast.Pass())
                owners.setdefault(caught, set()).add(fn.name)
                if caught == "BaseException":
                    reraises = any(isinstance(n, ast.Raise) and n.exc is None for n in node.body)
                    swallows = all(isinstance(n, ast.Pass) for n in node.body)
                    assert reraises or swallows, fn.name
    assert set(owners) == {"OSError", "BaseException"}, owners
    assert owners["BaseException"] == {"_close_quietly", "_fsync_directory", "_cross_volume", "_abandon"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Raise):
            assert node.cause is None, node.lineno


def test_transfer_is_private_to_the_package():
    _purge()
    try:
        execution = importlib.import_module(_PKG)
        importlib.import_module(f"{_PKG}.transfer")
        for name in ("transfer_media", "TransferOutcome", "ResumePhase", "_SAME_VOLUME_STRATEGY"):
            assert name not in execution.__all__ and not hasattr(execution, name), name
    finally:
        _purge()


# --------------------------------------------------------------------------- S4: executor.py (artifact units only)


def test_executor_is_the_single_synchronous_single_film_entry():
    # S5: execute_filesystem has exactly one production definition (executor.py); no batch / async /
    # thread / process machinery, no multi-film API, no persistence, no rollback names.
    definitions = [(path.name, n.name) for path in _files(EXEC_SRC_ROOT) for n in ast.walk(_tree(path))
                   if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == "execute_filesystem"]
    assert definitions == [("executor.py", "execute_filesystem")]
    tree = _tree(EXEC_SRC_ROOT / "executor.py")
    assert not any(isinstance(n, (ast.AsyncFunctionDef, ast.Await)) for n in ast.walk(tree))
    for module in _imports(tree):
        assert module.split(".")[0] not in {"threading", "concurrent", "multiprocessing", "asyncio", "queue",
                                            "json", "pickle", "shelve", "sqlite3"}, module
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} | {
        n.name for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
    for forbidden in ("rollback", "undo", "revert", "transaction", "cleanup_all", "execute_batch", "execute_many",
                      "preflight_execution", "Thread", "ThreadPoolExecutor", "ProcessPoolExecutor"):
        assert forbidden not in names, forbidden
    exported = [n for n in ast.walk(tree) if isinstance(n, ast.Assign)
                and any(getattr(t, "id", "") == "__all__" for t in n.targets)]
    assert len(exported) == 1 and [e.value for e in exported[0].value.elts] == ["execute_filesystem"]
    signature = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "execute_filesystem")
    assert [a.arg for a in signature.args.args] == ["preflight"] and not signature.args.kwonlyargs
    assert signature.args.vararg is None and signature.args.kwarg is None and not signature.args.defaults


def test_execute_filesystem_checks_before_consuming_and_consumes_before_the_filesystem():
    # Frozen section 15.5 order inside execute_filesystem: type -> seal -> ready -> validate_plan ->
    # validate_manifest -> fingerprints -> consumption -> the run (the first filesystem access).
    tree = _tree(EXEC_SRC_ROOT / "executor.py")
    fn = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "execute_filesystem")
    order = []
    for node in ast.walk(fn):
        if isinstance(node, ast.Call):
            name = getattr(node.func, "id", getattr(node.func, "attr", None))
            if name in {"type", "verify_seal", "validate_plan", "validate_manifest", "plan_fingerprint",
                        "manifest_fingerprint", "_consume", "_Run"}:
                order.append((node.lineno, node.col_offset, name))
        if isinstance(node, ast.Attribute) and node.attr == "ready":
            order.append((node.lineno, node.col_offset, "ready"))
    sequence = [name for *_, name in sorted(order)]
    assert sequence == ["type", "verify_seal", "ready", "validate_plan", "validate_manifest", "plan_fingerprint",
                        "manifest_fingerprint", "_consume", "_Run"], sequence
    fs_names = {n.attr for n in ast.walk(fn) if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name)
                and n.value.id == "_fs"}
    assert fs_names == set()  # no filesystem access inside the pre-consumption part itself


def test_materialize_artifact_is_the_only_artifact_writer_and_gets_the_original_request():
    tree = _tree(EXEC_SRC_ROOT / "executor.py")
    calls = [(fn.name, node) for fn in ast.walk(tree) if isinstance(fn, ast.FunctionDef)
             for node in ast.walk(fn) if isinstance(node, ast.Call)
             and getattr(node.func, "id", getattr(node.func, "attr", None)) == "materialize_artifact"]
    assert [name for name, _ in calls] == ["_execute_artifact_unit"]
    call = calls[0][1]
    assert len(call.args) == 1 and not call.keywords
    assert isinstance(call.args[0], ast.Name) and call.args[0].id == "request"  # the manifest's own object
    fn = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "_execute_artifact_unit")
    for node in ast.walk(fn):  # `request` is never rebound before the call
        if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign, ast.NamedExpr)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            assert all(getattr(t, "id", None) != "request" for t in targets)
    # No content copy / conversion / direct write anywhere in executor.py.
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = getattr(node.func, "id", getattr(node.func, "attr", None))
            assert name not in {"open", "write", "writelines", "materialize_atomic_bytes", "copy", "deepcopy",
                                "bytes", "bytearray", "memoryview", "encode", "decode", "ArtifactWriteRequest",
                                "replace", "mkstemp", "NamedTemporaryFile"}, name
        if isinstance(node, ast.Subscript):
            base = node.value
            assert not (isinstance(base, ast.Attribute) and base.attr == "content"), "content slicing"


def test_executor_reaches_only_read_only_seam_helpers():
    tree = _tree(EXEC_SRC_ROOT / "executor.py")
    used = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name)
            and n.value.id == "_fs"}
    assert used <= {"snapshot", "SnapshotRefused", "list_names", "read_bounded", "os_errno"}, used
    attrs = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    assert not attrs & (_MUTATING_ATTRS | {"_FS"}), attrs & (_MUTATING_ATTRS | {"_FS"})


def test_executor_translates_only_materialization_errors_and_never_chains():
    tree = _tree(EXEC_SRC_ROOT / "executor.py")
    handlers = [n for n in ast.walk(tree) if isinstance(n, ast.ExceptHandler)]
    materialization = [h for h in handlers if isinstance(h.type, ast.Name) and h.type.id == "MaterializationError"]
    fatal = [h for h in handlers if isinstance(h.type, ast.Name) and h.type.id == "BaseException"]
    assert materialization and len(materialization) + len(fatal) == len(handlers)
    # S5-R1 (contract section 15.6): exactly one `except BaseException`, in _Run.execute, that only poisons the
    # owned source claim and re-raises the same object (bare `raise`); it never builds a result or checkpoint.
    execute = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "execute"
                   and any(h in fatal for h in ast.walk(n)))
    assert len(fatal) == 1 and fatal[0].name is None
    body = fatal[0].body
    assert len(body) == 2 and isinstance(body[1], ast.Raise) and body[1].exc is None
    assert isinstance(body[0], ast.Expr) and getattr(body[0].value.func, "attr", None) == "_poison"
    assert execute is not None
    for node in ast.walk(tree):
        if isinstance(node, ast.Raise):
            assert node.cause is None, node.lineno
    for node in ast.walk(tree):  # dispatch by type: no message / class-name inspection
        if isinstance(node, ast.Attribute):
            assert node.attr not in {"__name__", "__qualname__", "args", "__str__", "message"}, node.attr
        if isinstance(node, ast.Call):
            assert getattr(node.func, "id", None) not in {"str", "repr", "format"}


def test_execute_filesystem_end_to_end_with_forbidden_modules_blocked(tmp_path):
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
        result = execution.execute_filesystem(execution.preflight_execution(plan, manifest))
        assert result.status is execution.ExecutionStatus.SUCCESS and not source.exists()
        loaded = set(sys.modules)
        assert not any(n.split(".")[0] in _BLOCKED_ROOTS or n.startswith(_BLOCKED_PREFIXES) for n in loaded)
    finally:
        sys.meta_path.remove(blocker)
        _purge()
        sys.modules.update(saved)


def test_executor_imports_with_forbidden_modules_blocked():
    _purge()
    saved = {name: sys.modules.pop(name) for name in list(sys.modules) if name.split(".")[0] in _BLOCKED_ROOTS}
    blocker = _BlockFinder()
    sys.meta_path.insert(0, blocker)
    try:
        importlib.import_module(f"{_PKG}.executor")
        loaded = set(sys.modules)
        assert not any(n.split(".")[0] in _BLOCKED_ROOTS or n.startswith(_BLOCKED_PREFIXES) for n in loaded)
        assert "fc2_organizer.materialization.atomic" in loaded  # through the bare public package only
    finally:
        sys.meta_path.remove(blocker)
        _purge()
        sys.modules.update(saved)
