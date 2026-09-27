"""Contract test: ``fc2_organizer.orchestration`` architecture boundary (P4-C8 contract sections 5, 6, 16, 33,
34.1; construction plan S1).

* exact S1 module set; no ``stages`` / ``preview`` / ``orchestrator`` / ``execute`` / ``retry`` yet;
* per-module import allow-lists; only the bare public lower packages of contract section 6 (plus the two
  frozen explicit paths, not used before S2); the forbidden module list asserted item by item; zero
  private lower-layer module references;
* no ``os`` use beyond ``os.name`` / ``os.path.basename``; no ``open`` / ``eval`` / ``exec`` / ``compile`` /
  ``__import__`` / ``print`` / ``shutil``; no rollback / persistence / diagnostics names;
* structural zero mutation: ``execute_filesystem`` / ``materialize_*`` never named (S1 has no ``execute.py``);
  no ``threading.Thread`` / ``asyncio.create_task`` / ``TaskGroup`` / ``gather`` / thread pools;
* no reverse dependency; ``fc2_organizer/__init__`` does not import it; a bare ``import fc2_organizer`` does
  not load it;
* resource ownership (E0-R1 / E0-R2): the four resource constants are defined only in ``models.py``;
  ``outcome`` is never a stored field; ``bounded_snapshot`` only in ``recognition.py``; payload metering
  helpers only in ``models.py``; no ``len`` / ``tuple`` / ``list`` of the ``items`` input; no ``copy`` /
  ``deepcopy``;
* the S1 public API is exactly the construction plan S1 set;
* at runtime, with ``amane`` / ``requests`` / ``sqlite3`` / ``shelve`` / ``dbm`` / ``pickle`` blocked, the
  package imports and its S1 functions run.
"""

from __future__ import annotations

import ast
import importlib
import sys
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[2] / "src"
ORGANIZER_SRC_ROOT = SRC_ROOT / "fc2_organizer"
ORCH_SRC_ROOT = ORGANIZER_SRC_ROOT / "orchestration"
CORE_SRC_ROOT = SRC_ROOT / "fc2_metadata_core"

_PKG = "fc2_organizer.orchestration"
_S1_MODULES = {"__init__.py", "errors.py", "models.py", "cancellation.py", "_consumption.py", "recognition.py"}
_NOT_YET = ("stages.py", "preview.py", "orchestrator.py", "execute.py", "retry.py")

_ALLOWED_STDLIB = {"__future__", "asyncio", "collections.abc", "dataclasses", "enum", "ntpath", "os", "posixpath",
                   "re", "secrets", "threading", "typing"}
_ALLOWED_LOWER = {
    "fc2_metadata_core.batch", "fc2_metadata_core.normalize", "fc2_metadata_core.aggregation",
    "fc2_organizer.discovery", "fc2_organizer.planning", "fc2_organizer.publication", "fc2_organizer.nfo",
    "fc2_organizer.images", "fc2_organizer.images.acquisition", "fc2_organizer.materialization",
    "fc2_organizer.materialization.mapping", "fc2_organizer.execution",
}
_LOWER_MODELS = {"fc2_metadata_core.batch", "fc2_metadata_core.normalize", "fc2_organizer.discovery",
                 "fc2_organizer.planning", "fc2_organizer.images", "fc2_organizer.materialization",
                 "fc2_organizer.execution"}
_ALLOWED = {
    "__init__.py": {f"{_PKG}.cancellation", f"{_PKG}.errors", f"{_PKG}.models"},
    "errors.py": {"__future__"},
    "cancellation.py": {"__future__", "threading"},
    "_consumption.py": {"__future__", "threading"},
    "models.py": {"__future__", "dataclasses", "enum", f"{_PKG}.errors"} | _LOWER_MODELS,
    "recognition.py": {"__future__", "collections.abc", "dataclasses", "os", f"{_PKG}.errors", f"{_PKG}.models",
                       "fc2_metadata_core.normalize", "fc2_organizer.discovery"},
}
_FORBIDDEN_MODULES = (
    "amane", "httpx", "requests", "socket", "ssl", "urllib", "http", "json", "pickle", "marshal", "shelve", "dbm",
    "sqlite3", "csv", "logging", "tempfile", "shutil", "glob", "fnmatch", "pathlib", "io", "subprocess",
    "multiprocessing", "concurrent", "ctypes", "time", "datetime", "random", "hashlib", "hmac", "copy",
)
_PRIVATE_LOWER = (
    "fc2_organizer.execution._fs", "fc2_organizer.execution.seal", "fc2_organizer.execution.models",
    "fc2_organizer.execution.errors", "fc2_organizer.execution.paths", "fc2_organizer.execution.validation",
    "fc2_organizer.execution.directories", "fc2_organizer.execution.transfer", "fc2_organizer.execution.preflight",
    "fc2_organizer.execution.executor", "fc2_organizer.materialization.atomic",
    "fc2_organizer.materialization.artifacts", "fc2_organizer.materialization.models",
    "fc2_organizer.materialization.errors", "fc2_organizer.images.transport", "fc2_organizer.images.jpeg",
    "fc2_organizer.images.urls", "fc2_organizer.images.models", "fc2_organizer.images.policy",
    "fc2_organizer.images.errors", "fc2_metadata_core.sources", "fc2_metadata_core.http",
    "fc2_metadata_core.resource_control", "fc2_metadata_core.models",
)
_FORBIDDEN_CALLS = {"open", "eval", "exec", "compile", "__import__", "print", "rollback", "undo", "revert", "delete",
                    "remove", "unlink", "rmtree", "save", "load", "dump", "dumps", "to_json", "to_dict", "write",
                    "deepcopy"}
_FORBIDDEN_DEFINITIONS = {"rollback", "undo", "revert", "delete", "remove", "unlink", "rmtree", "save", "load",
                          "dump", "dumps", "to_json", "to_dict", "write", "run", "execute_all", "resume", "report",
                          "progress", "subscribe"}
_WRITER_NAMES = {"execute_filesystem", "materialize_artifact", "materialize_atomic_bytes"}
_RESOURCE_CONSTANTS = {"MAX_BATCH_ITEMS", "MAX_ITEM_IMAGE_BYTES", "DEFAULT_MAX_RETAINED_ARTIFACT_BYTES",
                       "MAX_RETAINED_ARTIFACT_BYTES_LIMIT"}
_S1_PUBLIC_API = {
    "OrchestrationConfig", "CancellationToken", "BatchPreview", "ItemPreview", "PreviewState",
    "BatchExecutionResult", "ItemExecution", "ExecutionDisposition", "BatchOutcome", "RetryMaterial", "RetryKind",
    "OrchestrationStage", "IssueReason", "ItemIssue", "ItemWarning", "ResourceLimitReason",
    "DEFAULT_IMAGE_IN_FLIGHT_ITEMS", "MAX_IMAGE_IN_FLIGHT_ITEMS", "DEFAULT_FILESYSTEM_WORKERS",
    "MAX_FILESYSTEM_WORKERS", "MAX_BATCH_ITEMS", "MAX_ITEM_IMAGE_BYTES", "DEFAULT_MAX_RETAINED_ARTIFACT_BYTES",
    "MAX_RETAINED_ARTIFACT_BYTES_LIMIT",
    "OrchestrationError", "OrchestrationConfigError", "OrchestrationInputError", "OrchestrationBusyError",
    "OrchestrationContractError", "OrchestrationIntegrityError", "OrchestrationConsumedError",
    "OrchestrationRetryError", "OrchestrationResourceLimitError",
}
_LATER_OR_FORBIDDEN_PUBLIC = {"BatchOrchestrator", "merge_retry", "PreviewSummary", "ExecutionSummary", "run",
                              "execute_all", "resume", "rollback", "save", "load", "to_json", "to_dict", "dump",
                              "write", "report", "progress", "subscribe"}


def _files() -> list[Path]:
    return sorted(ORCH_SRC_ROOT.glob("*.py"))


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


def _call_name(node: ast.Call) -> str | None:
    func = node.func
    return func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)


# --------------------------------------------------------------------------- module set / imports


def test_package_has_exactly_the_s1_modules():
    names = {p.name for p in _files()}
    assert names == _S1_MODULES
    for later in _NOT_YET:
        assert later not in names
    assert not [p for p in ORCH_SRC_ROOT.iterdir() if p.is_dir() and p.name != "__pycache__"]


def test_every_module_imports_only_its_allow_list():
    for path in _files():
        imported = _imports(_tree(path))
        assert imported <= _ALLOWED[path.name], (path.name, imported - _ALLOWED[path.name])
        assert imported <= _ALLOWED_STDLIB | _ALLOWED_LOWER | {f"{_PKG}.{m[:-3]}" for m in _S1_MODULES}, path.name


def test_errors_cancellation_and_consumption_import_boundaries():
    assert _imports(_tree(ORCH_SRC_ROOT / "errors.py")) == {"__future__"}
    assert _imports(_tree(ORCH_SRC_ROOT / "cancellation.py")) == {"__future__", "threading"}
    assert _imports(_tree(ORCH_SRC_ROOT / "_consumption.py")) == {"__future__", "threading"}
    recognition = _imports(_tree(ORCH_SRC_ROOT / "recognition.py"))
    for package in ("execution", "materialization", "images", "nfo", "publication", "planning"):
        assert not any(m.startswith(f"fc2_organizer.{package}") for m in recognition), package


def test_forbidden_modules_item_by_item():
    for path in _files():
        for module in _imports(_tree(path)):
            root = module.split(".")[0]
            for forbidden in _FORBIDDEN_MODULES:
                assert root != forbidden and not module.startswith(forbidden + "."), (path.name, module)


def test_no_private_lower_layer_module_reference():
    for path in _files():
        text = path.read_text(encoding="utf-8")
        for module in _imports(_tree(path)):
            assert not module.startswith(_PRIVATE_LOWER), (path.name, module)
            if module.startswith(("fc2_organizer.", "fc2_metadata_core.")) and not module.startswith(_PKG):
                assert module in _ALLOWED_LOWER, (path.name, module)
        for private in ("_fs", "_FS", "seal", "atomic", "transport"):
            names = {n.id for n in ast.walk(_tree(path)) if isinstance(n, ast.Name)} | {
                n.attr for n in ast.walk(_tree(path)) if isinstance(n, ast.Attribute)}
            assert private not in names, (path.name, private)
        assert "fc2_organizer.execution._fs" not in text and "materialization.atomic" not in text


# --------------------------------------------------------------------------- forbidden calls / names


def test_os_is_used_only_for_name_and_path_basename():
    for path in _files():
        tree = _tree(path)
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "os":
                assert node.attr in {"name", "path"}, (path.name, node.attr)
            if (isinstance(node, ast.Attribute) and isinstance(node.value, ast.Attribute)
                    and isinstance(node.value.value, ast.Name) and node.value.value.id == "os"):
                assert node.value.attr == "path" and node.attr == "basename", (path.name, node.attr)
        assert "from os" not in path.read_text(encoding="utf-8")


def test_no_forbidden_calls_or_definitions():
    for path in _files():
        tree = _tree(path)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                assert _call_name(node) not in _FORBIDDEN_CALLS, (path.name, node.lineno, _call_name(node))
                func = node.func
                if isinstance(func, ast.Attribute) and getattr(func.value, "id", None) == "shutil":
                    raise AssertionError(f"{path.name}: shutil call")
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                assert node.name not in _FORBIDDEN_DEFINITIONS, (path.name, node.name)


def test_structural_zero_mutation_and_no_unbounded_concurrency():
    for path in _files():
        tree = _tree(path)
        names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
        attrs = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
        aliases = {a.name for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) for a in n.names}
        for writer in _WRITER_NAMES:
            assert writer not in names | attrs | aliases, (path.name, writer)
        for concurrency in ("Thread", "create_task", "TaskGroup", "gather", "ThreadPoolExecutor",
                            "ProcessPoolExecutor"):
            assert concurrency not in names | attrs | aliases, (path.name, concurrency)
        for node in ast.walk(tree):
            assert not isinstance(node, (ast.AsyncFunctionDef, ast.Await)), path.name


def test_no_persistence_or_diagnostics_output():
    for path in _files():
        text = path.read_text(encoding="utf-8")
        for token in ("json.", "pickle.", "sqlite3", "shelve.", "logging.", "print("):
            assert token not in text, (path.name, token)


# --------------------------------------------------------------------------- reverse dependency


def test_no_reverse_dependency_on_orchestration():
    for root in (CORE_SRC_ROOT, *(p for p in ORGANIZER_SRC_ROOT.iterdir() if p.is_dir() and p != ORCH_SRC_ROOT)):
        for path in sorted(root.rglob("*.py")):
            for module in _imports(_tree(path)):
                assert not module.startswith(_PKG), f"{path}: imports {module!r}"
            assert _PKG not in path.read_text(encoding="utf-8"), path
    for module in _imports(_tree(ORGANIZER_SRC_ROOT / "__init__.py")):
        assert "orchestration" not in module


def _purge() -> None:
    for name in list(sys.modules):
        if name.split(".")[0] in {"fc2_organizer", "fc2_metadata_core"}:
            del sys.modules[name]


def test_bare_import_of_fc2_organizer_does_not_load_orchestration():
    _purge()
    try:
        importlib.import_module("fc2_organizer")
        assert _PKG not in sys.modules
    finally:
        _purge()


# --------------------------------------------------------------------------- resource ownership (E0-R1 / E0-R2)


def _module_level_definitions(tree: ast.AST) -> set[str]:
    names = set()
    for node in tree.body:  # type: ignore[attr-defined]
        targets = node.targets if isinstance(node, ast.Assign) else [node.target] if isinstance(
            node, ast.AnnAssign) else []
        names.update(t.id for t in targets if isinstance(t, ast.Name))
    return names


def test_resource_constants_are_defined_only_in_models():
    for path in _files():
        defined = _module_level_definitions(_tree(path)) & _RESOURCE_CONSTANTS
        assert defined == (_RESOURCE_CONSTANTS if path.name == "models.py" else set()), (path.name, defined)


def test_outcome_is_never_a_stored_field():
    tree = _tree(ORCH_SRC_ROOT / "models.py")
    for cls in (n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)):
        for node in cls.body:
            if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                assert node.target.id != "outcome", cls.name
    result = next(n for n in ast.walk(tree) if isinstance(n, ast.ClassDef) and n.name == "BatchExecutionResult")
    outcome = next(n for n in result.body if isinstance(n, ast.FunctionDef) and n.name == "outcome")
    assert any(getattr(d, "id", None) == "property" for d in outcome.decorator_list)


def test_resource_helpers_have_their_frozen_homes():
    definitions: dict[str, set[str]] = {}
    for path in _files():
        for node in ast.walk(_tree(path)):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                definitions.setdefault(node.name, set()).add(path.name)
    assert definitions["bounded_snapshot"] == {"recognition.py"}
    assert definitions["retry_payload_bytes"] == {"models.py"}
    assert definitions["retained_retry_payload_bytes"] == {"models.py"}
    assert definitions["retained_artifact_bytes"] == {"models.py"}


def test_items_input_is_never_measured_or_materialized():
    for path in _files():
        for node in ast.walk(_tree(path)):
            if isinstance(node, ast.Call) and _call_name(node) in {"len", "tuple", "list"}:
                for arg in node.args:
                    assert not (isinstance(arg, ast.Name) and arg.id == "items"), (path.name, node.lineno)
            if isinstance(node, ast.Attribute):
                assert node.attr != "__len__", path.name
    fn = next(n for n in ast.walk(_tree(ORCH_SRC_ROOT / "recognition.py"))
              if isinstance(n, ast.FunctionDef) and n.name == "bounded_snapshot")
    iter_calls = [n for n in ast.walk(fn) if isinstance(n, ast.Call) and _call_name(n) == "iter"]
    assert len(iter_calls) == 1
    tuple_args = [n.args[0].id for n in ast.walk(fn) if isinstance(n, ast.Call) and _call_name(n) == "tuple"]
    assert tuple_args == ["collected"]


def test_no_copy_module_or_deepcopy():
    for path in _files():
        tree = _tree(path)
        assert "copy" not in {m.split(".")[0] for m in _imports(tree)}, path.name
        names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} | {
            n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
        assert "deepcopy" not in names, path.name


def test_no_production_module_has_mutable_state_except_the_consumption_registries():
    for path in _files():
        for node in _tree(path).body:  # type: ignore[attr-defined]
            targets = node.targets if isinstance(node, ast.Assign) else [getattr(node, "target", None)]
            if any(getattr(t, "id", None) == "__all__" for t in targets):
                continue
            if isinstance(node, (ast.Assign, ast.AnnAssign)) and isinstance(node.value, (ast.List, ast.Set,
                                                                                          ast.ListComp)):
                raise AssertionError(f"{path.name}: module-level mutable container")
    registries = _module_level_definitions(_tree(ORCH_SRC_ROOT / "_consumption.py"))
    assert {"PREVIEW_EXECUTIONS", "RESULT_RETRIES", "RETRY_MERGES"} <= registries


# --------------------------------------------------------------------------- public API / runtime


def test_public_api_is_exactly_the_s1_set():
    _purge()
    try:
        orchestration = importlib.import_module(_PKG)
        assert len(orchestration.__all__) == len(set(orchestration.__all__)) == len(_S1_PUBLIC_API) == 33
        assert set(orchestration.__all__) == _S1_PUBLIC_API
        for name in orchestration.__all__:
            assert hasattr(orchestration, name), name
        for name in _LATER_OR_FORBIDDEN_PUBLIC | {"revalidate", "type_name", "reason_detail", "bounded_snapshot",
                                                   "retry_payload_bytes", "ConsumptionRegistry"}:
            assert name not in orchestration.__all__ and not hasattr(orchestration, name), name
    finally:
        _purge()


_BLOCKED_ROOTS = {"amane", "requests", "sqlite3", "shelve", "dbm", "pickle"}


class _BlockFinder:
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".")[0] in _BLOCKED_ROOTS:
            raise ImportError(f"fc2_organizer.orchestration attempted to import forbidden module: {fullname}")
        return None


def test_orchestration_imports_and_runs_with_forbidden_modules_blocked():
    _purge()
    saved = {name: sys.modules.pop(name) for name in list(sys.modules) if name.split(".")[0] in _BLOCKED_ROOTS}
    blocker = _BlockFinder()
    sys.meta_path.insert(0, blocker)
    try:
        orchestration = importlib.import_module(_PKG)
        recognition = importlib.import_module(f"{_PKG}.recognition")
        discovery = importlib.import_module("fc2_organizer.discovery")
        import os

        root = "C:\\dl" if os.name == "nt" else "/dl"
        items = [discovery.DiscoveredMediaItem(index=i, source_path=os.path.join(root, name), relative_path=name,
                                               extension=".mp4", size=1)
                 for i, name in enumerate(("FC2-PPV-1234567.mp4", "FC2PPV1234567.mp4", "other.mp4"))]
        verdicts = recognition.recognize(recognition.validate_media_items(recognition.bounded_snapshot(items)))
        assert [v.reason for v in verdicts] == [orchestration.IssueReason.DUPLICATE_TARGET_IN_BATCH,
                                                orchestration.IssueReason.DUPLICATE_TARGET_IN_BATCH,
                                                orchestration.IssueReason.NUMBER_NOT_RECOGNIZED]
        token = orchestration.CancellationToken()
        token.cancel()
        assert token.cancelled and orchestration.OrchestrationConfig().filesystem_workers == 1
        loaded = set(sys.modules)
        assert not any(n.split(".")[0] in _BLOCKED_ROOTS for n in loaded)
    finally:
        sys.meta_path.remove(blocker)
        _purge()
        sys.modules.update(saved)
