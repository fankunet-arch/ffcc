"""Contract test: ``fc2_organizer.diagnostics`` architecture boundary (P4-C9 contract sections 6, 7, 8, 27.1).

Stage-aware (``_STAGE``): the exact module set, the exact ``__all__`` and the per-module import allow-lists
are asserted for the current construction stage; S2 / S3 only switch ``_STAGE`` and add assertions.

* import allow-lists: standard library per module; only the *bare* public upstream packages and only the
  contract section 8.5 names -- never a submodule, a private name or a package module object;
* forbidden imports (network, filesystem writers, persistence, introspection, ``gc``, ``inspect``, ``sys``,
  ...), forbidden calls (``getattr`` / ``isinstance`` / ``sorted`` / ``min`` / ``max`` / ``str`` / ... ), zero
  attribute access starting with ``_`` (every dunder included), ``os`` / ``math`` / ``types`` / ``json`` member
  allow-lists, no string formatting;
* module level holds immutable constants only; no reverse dependency; ``fc2_organizer/__init__`` does not
  import it; the bare ``import fc2_organizer`` does not load it; the package imports with ``amane`` /
  ``requests`` blocked.
"""

from __future__ import annotations

import ast
import contextlib
import importlib
import sys
from pathlib import Path

import pytest

SRC_ROOT = Path(__file__).resolve().parents[2] / "src"
ORGANIZER_SRC_ROOT = SRC_ROOT / "fc2_organizer"
DIAG_ROOT = ORGANIZER_SRC_ROOT / "diagnostics"
CORE_SRC_ROOT = SRC_ROOT / "fc2_metadata_core"
_PKG = "fc2_organizer.diagnostics"

_STAGE = "S2"
_S1_MODULES = {"__init__.py", "errors.py", "models.py"}
_S2_MODULES = _S1_MODULES | {"validation.py", "projection.py", "build.py"}
_S3_MODULES = _S2_MODULES | {"render.py"}
_MODULE_SETS = {"S1": _S1_MODULES, "S2": _S2_MODULES, "S3": _S3_MODULES}

_S1_ALL = [
    "DiagnosticsKind", "ResultShape", "PathPolicy", "TimingPolicy",
    "BatchDiagnostics", "MetadataBatchCounts", "ItemDiagnostics", "IssueDiagnostics", "MetadataDiagnostics",
    "SourceDiagnostics", "SourceAttemptDiagnostics", "FieldProvenance", "FieldConflictDiagnostics",
    "ImageFailureGroup", "PreflightDiagnostics", "ExecutionDiagnostics", "LeftoverTemporaryDiagnostics",
    "DIAGNOSTICS_SCHEMA", "DIAGNOSTICS_SCHEMA_VERSION", "PROVENANCE_FIELD_ORDER", "MAX_DIAGNOSTIC_ITEMS",
    "MAX_SOURCES_PER_ITEM", "MAX_ATTEMPTS_PER_SOURCE", "MAX_BLOCKERS_PER_ITEM", "MAX_CONFLICTS_PER_ITEM",
    "MAX_LEFTOVER_TEMPORARIES_PER_ITEM", "MAX_PATH_TEXT_CHARS", "MAX_TIMING_MS", "MAX_DIAGNOSTIC_OUTPUT_BYTES",
    "DiagnosticsError", "DiagnosticsInputError", "DiagnosticsIntegrityError", "DiagnosticsContractError",
    "DiagnosticsResourceLimitError", "DiagnosticsUnsafeValueError", "DiagnosticsSerializationError",
]
_S2_ALL = ["build_preview_diagnostics", "build_execution_diagnostics"] + _S1_ALL
_S3_ALL = ["build_preview_diagnostics", "build_execution_diagnostics", "render_diagnostics_json"] + _S1_ALL
_ALL_SETS = {"S1": _S1_ALL, "S2": _S2_ALL, "S3": _S3_ALL}

# Contract section 7: allowed standard library per module.
_STDLIB = {
    "__init__.py": set(),
    "errors.py": {"__future__"},
    "models.py": {"__future__", "dataclasses", "enum", "re"},
    "validation.py": {"__future__", "re", "math", "os", "types"},
    "projection.py": {"__future__"},
    "build.py": {"__future__"},
    "render.py": {"__future__", "json"},
}
# Intra-package imports (contract section 6 module graph).
_SIBLINGS = {
    "__init__.py": {"errors", "models", "build", "render"},
    "errors.py": set(),
    "models.py": {"errors"},
    "validation.py": {"errors", "models"},
    "projection.py": {"errors", "models", "validation"},
    "build.py": {"errors", "models", "validation", "projection"},
    "render.py": {"errors", "models"},
}
# Contract section 8.5: the bare public upstream packages and the only names importable from each.
_UPSTREAM = {
    "fc2_organizer.orchestration": {
        "BatchPreview", "BatchExecutionResult", "ItemPreview", "ItemExecution", "ItemIssue", "PreviewSummary",
        "ExecutionSummary", "PreviewState", "ExecutionDisposition", "OrchestrationStage", "IssueReason",
        "ItemWarning", "RetryKind", "BatchOutcome", "RetryMaterial", "MAX_BATCH_ITEMS",
        "MAX_RETAINED_ARTIFACT_BYTES_LIMIT"},
    "fc2_organizer.execution": {
        "ExecutionPreflight", "ExecutionResult", "ExecutionStatus", "ExecutionStep", "ExecutionFailure",
        "ExecutionFailureKind", "TransferStage", "TransferMode", "PreflightMode", "PreflightBlocker",
        "PreflightBlockReason", "PathRole", "EffectKind", "CompletedEffect", "LeftoverTemporary", "ExecutionUnit",
        "ExecutionCheckpoint", "PlanGraphRejectionReason", "ManifestRejectionReason", "CheckpointRejectionReason",
        "PreflightIntegrityReason"},
    "fc2_organizer.images": {"ImageCandidateFailure", "ImageRole", "ImageFailureKind", "ImageAcquisitionPolicy"},
    "fc2_organizer.materialization": {"ArtifactKind", "ArtifactWriteRequest", "MappingRejectionReason"},
    "fc2_organizer.discovery": {"DiscoveredMediaItem"},
    "fc2_organizer.planning": {"OrganizePlan", "PlannedPath", "PlannedOperation", "PlannedOperationKind",
                               "OutputPolicy"},
    "fc2_metadata_core.batch": {"BatchResult", "BatchItemResult", "BatchItemStatus", "BatchItemErrorKind",
                                "BatchLineage"},
    "fc2_metadata_core.aggregation": {"AggregationResult", "AggregateStatus", "SourceExecutionTrace",
                                      "SourceAttempt", "FieldConflict", "OPERATIONAL_FAILURE_STATUSES",
                                      "CONFLICT_FIELDS", "RETRY_ELIGIBLE_KINDS"},
    "fc2_metadata_core.models": {"SourceResult", "SourceStatus", "SourceErrorKind", "NormalizedMetadata"},
    "fc2_metadata_core.normalize": {"is_valid_fc2_number"},
}
_FORBIDDEN_TOP_LEVEL = {
    "amane", "httpx", "requests", "socket", "ssl", "urllib", "http", "pickle", "marshal", "shelve", "dbm",
    "sqlite3", "csv", "logging", "tempfile", "shutil", "glob", "fnmatch", "pathlib", "io", "subprocess",
    "multiprocessing", "concurrent", "threading", "asyncio", "ctypes", "time", "datetime", "random", "secrets",
    "uuid", "hashlib", "hmac", "traceback", "inspect", "sys", "builtins", "copy", "unicodedata", "gc", "copyreg",
    "weakref", "typing", "functools", "itertools", "collections", "operator", "string", "textwrap", "struct",
}
_FORBIDDEN_UPSTREAM_PREFIXES = ("fc2_metadata_core.sources", "fc2_metadata_core.http",
                                "fc2_metadata_core.resource_control")
_FORBIDDEN_NAMES = {
    "open", "print", "exec", "eval", "compile", "__import__", "getattr", "hasattr", "setattr", "delattr", "vars",
    "dir", "id", "hash", "repr", "format", "isinstance", "issubclass", "super", "sorted", "min", "max", "str",
    "globals", "locals", "input", "breakpoint", "memoryview", "bytearray", "iter", "next", "map", "filter",
}
_FORBIDDEN_SOURCE_NAMES = {"BatchOrchestrator", "merge_retry", "revalidate", "preflight_execution",
                           "execute_filesystem", "build_organize_plan", "OrchestrationConfig", "CancellationToken",
                           "discover_media"}
_OS_ALLOWED = {("path", "isabs"), ("path", "join"), ("path", "basename"), ("sep",), ("altsep",)}
_DISPATCH_METHODS = {"keys", "values", "items", "get", "copy"}


def _files() -> list[Path]:
    return sorted(DIAG_ROOT.glob("*.py"))


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _modules():
    return [(path.name, _tree(path)) for path in _files()]


def _imports(tree: ast.AST) -> list[ast.stmt]:
    return [n for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom))]


# --------------------------------------------------------------------------- module set / __all__


def test_module_set_is_exactly_the_stage_set_without_subdirectories():
    assert {p.name for p in DIAG_ROOT.glob("*.py")} == _MODULE_SETS[_STAGE]
    assert {p.name for p in DIAG_ROOT.iterdir() if p.is_dir()} <= {"__pycache__"}
    assert {p.name for p in DIAG_ROOT.iterdir() if p.is_file()} <= _MODULE_SETS[_STAGE] | {"__init__.pyc"}


def test_no_stub_or_placeholder_module_of_a_later_stage_exists():
    later = set().union(*_MODULE_SETS.values()) - _MODULE_SETS[_STAGE]
    for name in later:
        assert not (DIAG_ROOT / name).exists(), name


def test_dunder_all_is_exactly_the_stage_set_in_order():
    module = importlib.import_module(_PKG)
    assert module.__all__ == _ALL_SETS[_STAGE]
    for name in module.__all__:
        assert hasattr(module, name), name
    init_tree = _tree(DIAG_ROOT / "__init__.py")
    assigned = [n for n in init_tree.body if isinstance(n, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == "__all__" for t in n.targets)]
    assert len(assigned) == 1
    assert [e.value for e in assigned[0].value.elts] == _ALL_SETS[_STAGE]


def test_internal_constants_are_not_in_any_stage_all():
    for names in _ALL_SETS.values():
        assert "MAX_PROVENANCE_KEYS" not in names and "MAX_TIMING_SECONDS" not in names


def test_package_modules_expose_no_gc_or_introspection_attribute_at_runtime():
    for name in _MODULE_SETS[_STAGE]:
        module = importlib.import_module(_PKG if name == "__init__.py" else f"{_PKG}.{name[:-3]}")
        for forbidden in ("gc", "inspect", "ctypes", "sys", "pickle", "marshal", "copyreg", "weakref", "traceback",
                          "builtins", "copy"):
            assert forbidden not in vars(module), (name, forbidden)


# --------------------------------------------------------------------------- imports


def test_imports_come_only_from_the_per_module_allow_lists():
    for name, tree in _modules():
        stdlib, siblings = _STDLIB[name], _SIBLINGS[name]
        for node in _imports(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name in stdlib, (name, alias.name)  # `import x` is stdlib only
                continue
            assert node.level == 0, (name, "relative import")
            module = node.module or ""
            top = module.split(".")[0]
            if module in stdlib:
                continue
            if module in _UPSTREAM:
                names = {alias.name for alias in node.names}
                assert names <= _UPSTREAM[module], (name, module, names - _UPSTREAM[module])
                assert not any(n.startswith("_") for n in names), (name, module)
            elif module.startswith(_PKG + "."):
                assert module[len(_PKG) + 1:] in siblings, (name, module)
                assert not any(alias.name.startswith("_") for alias in node.names), (name, module)
            elif top == "fc2_organizer" and module == "fc2_organizer":
                raise AssertionError(f"{name}: imports the package module object {node.names}")
            else:
                raise AssertionError(f"{name}: forbidden import {module!r}")


def test_init_imports_only_package_modules():
    for node in _imports(_tree(DIAG_ROOT / "__init__.py")):
        assert isinstance(node, ast.ImportFrom)
        assert (node.module or "").startswith(_PKG + "."), node.module


def test_forbidden_modules_are_never_imported():
    for name, tree in _modules():
        for node in _imports(tree):
            modules = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""]
            for module in modules:
                assert module.split(".")[0] not in _FORBIDDEN_TOP_LEVEL, (name, module)
                assert not module.startswith(_FORBIDDEN_UPSTREAM_PREFIXES), (name, module)


def test_no_source_adapter_orchestration_owner_or_discovery_name_is_referenced():
    for name, tree in _modules():
        for node in ast.walk(tree):
            used = node.id if isinstance(node, ast.Name) else node.attr if isinstance(node, ast.Attribute) else None
            assert used not in _FORBIDDEN_SOURCE_NAMES, (name, used)
            if isinstance(node, ast.ImportFrom):
                assert not ({a.name for a in node.names} & _FORBIDDEN_SOURCE_NAMES), name


# --------------------------------------------------------------------------- calls / attributes


def test_no_forbidden_name_is_referenced_or_called():
    for name, tree in _modules():
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                assert node.func.id not in _FORBIDDEN_NAMES, (name, node.func.id, node.lineno)
            elif isinstance(node, ast.Name):
                # `str` appears as a type annotation (`str | None`); it is never called (checked above)
                assert node.id not in _FORBIDDEN_NAMES - {"str"}, (name, node.id, node.lineno)


def test_no_attribute_access_starts_with_an_underscore():
    for name, tree in _modules():
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute):
                assert not node.attr.startswith("_"), (name, node.attr, node.lineno)


def test_no_string_formatting_of_any_value():
    for name, tree in _modules():
        for node in ast.walk(tree):
            assert not isinstance(node, ast.JoinedStr), (name, node.lineno)
            if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mod):
                assert not (isinstance(node.left, ast.Constant) and isinstance(node.left.value, str)), (name,)
            if isinstance(node, ast.Attribute):
                assert node.attr != "format", (name, node.lineno)


def test_validation_calls_no_mapping_methods():
    """contract section 9.2 item 9 Step 3 (AST proxy): no keys / values / items / get / copy in validation.py."""
    path = DIAG_ROOT / "validation.py"
    if not path.exists():
        pytest.skip("validation.py is added in S2 (this assertion is part of the S2 module set)")
    for node in ast.walk(_tree(path)):
        # a *call* of such a method (the upstream models have fields named ``items``: reading them is fine)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            assert node.func.attr not in _DISPATCH_METHODS, node.lineno


def _chain(node: ast.Attribute) -> tuple[str, ...] | None:
    parts = [node.attr]
    current = node.value
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if isinstance(current, ast.Name):
        return (current.id, *reversed(parts))
    return None


def test_os_math_types_json_members_are_whitelisted():
    for name, tree in _modules():
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute):
                chain = _chain(node)
                if chain is None:
                    continue
                if chain[0] == "os":
                    assert name == "validation.py", name
                    assert chain[1:] in _OS_ALLOWED or chain[1:2] == ("path",) and len(chain) == 2, (name, chain)
                elif chain[0] == "math":
                    assert name == "validation.py" and chain == ("math", "isfinite"), (name, chain)
                elif chain[0] == "types":
                    assert name == "validation.py" and chain == ("types", "MappingProxyType"), (name, chain)
                elif chain[0] == "json":
                    assert name == "render.py" and chain == ("json", "JSONEncoder"), (name, chain)


def test_from_imports_of_os_math_types_json_are_not_used():
    for name, tree in _modules():
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                assert (node.module or "") not in {"os", "os.path", "math", "types", "json"}, (name, node.module)


def test_no_unbounded_or_dynamic_construct_is_used():
    for name, tree in _modules():
        for node in ast.walk(tree):
            assert not isinstance(node, (ast.Global, ast.Nonlocal, ast.AsyncFunctionDef, ast.Await, ast.Yield,
                                         ast.YieldFrom)), (name, node.lineno)


# --------------------------------------------------------------------------- module level state


def _immutable(node: ast.AST) -> bool:
    if isinstance(node, (ast.Constant, ast.Name)):
        return True
    if isinstance(node, ast.Attribute):
        return isinstance(node.value, (ast.Name, ast.Attribute))
    if isinstance(node, ast.Tuple):
        return all(_immutable(e) for e in node.elts)
    if isinstance(node, ast.Set):
        return all(_immutable(e) for e in node.elts)
    if isinstance(node, ast.UnaryOp):
        return _immutable(node.operand)
    if isinstance(node, ast.BinOp):
        return _immutable(node.left) and _immutable(node.right)
    if isinstance(node, ast.Call):
        func = node.func
        callee = func.id if isinstance(func, ast.Name) else _chain(func) if isinstance(func, ast.Attribute) else None
        return callee in {"frozenset", "float", "tuple", ("re", "compile")} and all(
            _immutable(a) for a in node.args) and not node.keywords
    return False


def test_module_level_assignments_are_immutable_constants_only():
    for name, tree in _modules():
        for node in tree.body:
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                if any(isinstance(t, ast.Name) and t.id == "__all__" for t in targets):
                    assert isinstance(node.value, ast.List) and all(
                        isinstance(e, ast.Constant) and type(e.value) is str for e in node.value.elts), name
                    continue
                assert node.value is not None and _immutable(node.value), (name, node.lineno)
            else:
                assert isinstance(node, (ast.Expr, ast.Import, ast.ImportFrom, ast.ClassDef, ast.FunctionDef)), (
                    name, type(node).__name__)


# --------------------------------------------------------------------------- dependency direction / runtime


def test_no_reverse_dependency_on_diagnostics():
    for root in (CORE_SRC_ROOT, *(p for p in ORGANIZER_SRC_ROOT.iterdir() if p.is_dir() and p != DIAG_ROOT)):
        for path in sorted(root.rglob("*.py")):
            assert _PKG not in path.read_text(encoding="utf-8"), path
            for node in _imports(_tree(path)):
                modules = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""]
                for module in modules:
                    assert not module.startswith(_PKG), f"{path}: imports {module!r}"
    for node in _imports(_tree(ORGANIZER_SRC_ROOT / "__init__.py")):
        names = [a.name for a in node.names]
        assert "diagnostics" not in (node.module or "") and "diagnostics" not in names


_FC2_ROOTS = frozenset({"fc2_organizer", "fc2_metadata_core"})
_BLOCKED_ROOTS = {"amane", "requests"}


class _BlockFinder:
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".")[0] in _BLOCKED_ROOTS:
            raise ImportError(f"fc2_organizer.diagnostics attempted to import a forbidden module: {fullname}")
        return None


def _purge(roots: frozenset[str]) -> None:
    for name in list(sys.modules):
        if name.split(".")[0] in roots:
            del sys.modules[name]


@contextlib.contextmanager
def _isolated_imports(*, block: bool = False):
    """Fresh imports; on every exit the exact pre-test module objects and ``sys.meta_path`` come back (a second
    copy of a package would make the exact-type checks reject the first copy's objects)."""
    roots = _FC2_ROOTS | _BLOCKED_ROOTS
    saved_modules = {name: module for name, module in sys.modules.items() if name.split(".")[0] in roots}
    saved_meta_path = list(sys.meta_path)
    try:
        _purge(_FC2_ROOTS | (_BLOCKED_ROOTS if block else frozenset()))
        if block:
            sys.meta_path.insert(0, _BlockFinder())
        yield
    finally:
        sys.meta_path[:] = saved_meta_path
        _purge(roots)
        sys.modules.update(saved_modules)


def test_bare_import_of_fc2_organizer_does_not_load_diagnostics():
    with _isolated_imports():
        importlib.import_module("fc2_organizer")
        assert _PKG not in sys.modules


def test_diagnostics_imports_with_amane_and_requests_blocked():
    with _isolated_imports(block=True):
        module = importlib.import_module(_PKG)
        assert module.__all__ == _ALL_SETS[_STAGE]
        assert not any(name.split(".")[0] in _BLOCKED_ROOTS for name in sys.modules)
