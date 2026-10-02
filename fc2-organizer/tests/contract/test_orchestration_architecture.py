"""Contract test: ``fc2_organizer.orchestration`` architecture boundary (P4-C8 contract sections 5, 6, 16, 33,
34.1; construction plan S1, S2, S3, S4, S5).

* exact final module set (contract section 5: S1 six + ``stages`` / ``preview`` / ``orchestrator`` + ``execute`` +
  ``retry``; S5 adds no module), cross-checked against the contract's own module table;
* per-module import allow-lists; only the bare public lower packages of contract section 6 (plus the two
  frozen explicit paths, not used before S2); the forbidden module list asserted item by item; zero
  private lower-layer module references;
* no ``os`` use beyond ``os.name`` / ``os.path.basename``; no ``open`` / ``eval`` / ``exec`` / ``compile`` /
  ``__import__`` / ``print`` / ``shutil``; no rollback / persistence / diagnostics names;
* structural zero mutation: ``materialize_*`` never named; ``execute_filesystem`` only in ``execute.py`` (one
  call site, the preview's own preflight); ``threading.Thread`` only in ``execute.py`` (non-daemon, created in a
  ``range(workers)`` comprehension); no thread pools / ``gather`` anywhere; ``TaskGroup.create_task`` only in ``preview.py``,
  exactly once, inside a ``range(min(...))`` loop (bounded workers); ``acquire_images`` only in ``preview.py``;
  the five other stage APIs only in ``stages.py``; the retention ledger only in ``preview.py``;
* ``BatchOrchestrator.preview``, ``execute`` and ``preview_retry`` claim the busy flag as their very first
  statement; ``preview_retry`` only delegates to ``retry.py``;
* S4: ``merge_retry`` / ``base_retained`` live only in ``retry.py``; ``merge_retry`` is synchronous and pure (no
  scheduler, stage, image or preflight name); both one-time registrations are the last step before the return;
  ``retry.py`` reuses ``preview.py``'s ledger / image stage and never names ``acquire_images``;
* no reverse dependency; ``fc2_organizer/__init__`` does not import it; a bare ``import fc2_organizer`` does
  not load it;
* resource ownership (E0-R1 / E0-R2): the four resource constants are defined only in ``models.py``;
  ``outcome`` is never a stored field; ``bounded_snapshot`` only in ``recognition.py``; payload metering
  helpers only in ``models.py``; no ``len`` / ``tuple`` / ``list`` of the ``items`` input; no ``copy`` /
  ``deepcopy``;
* the public API is exactly contract section 7.1 (S5, final): ``__all__`` equals the frozen list item by item and
  in order (also parsed from the contract text); every name exists; no internal name leaks;
* at runtime, with ``amane`` / ``requests`` / ``sqlite3`` / ``shelve`` / ``dbm`` / ``pickle`` blocked, the
  package imports, its S1 functions run and a real ``preview`` runs end to end (scripted engine / client);
* (S5-R1, finding P4-C8-S5-R-03) every test that re-imports the packages runs inside ``_isolated_imports``, which
  restores the exact pre-test ``sys.modules`` objects of ``fc2_organizer`` / ``fc2_metadata_core`` / the blocked
  roots and the exact ``sys.meta_path`` list on every exit (proven for repetition, order and exceptions).
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
ORCH_SRC_ROOT = ORGANIZER_SRC_ROOT / "orchestration"
CORE_SRC_ROOT = SRC_ROOT / "fc2_metadata_core"

_PKG = "fc2_organizer.orchestration"
_S1_MODULES = {"__init__.py", "errors.py", "models.py", "cancellation.py", "_consumption.py", "recognition.py"}
_S2_MODULES = _S1_MODULES | {"stages.py", "preview.py", "orchestrator.py"}
_S3_MODULES = _S2_MODULES | {"execute.py"}
_S4_MODULES = _S3_MODULES | {"retry.py"}
_FINAL_MODULES = _S4_MODULES  # S5 adds no production module (contract section 5)
_FINAL_PUBLIC_API = (  # contract section 7.1, in its order
    "BatchOrchestrator", "OrchestrationConfig", "CancellationToken", "merge_retry",
    "BatchPreview", "ItemPreview", "PreviewState", "PreviewSummary",
    "BatchExecutionResult", "ItemExecution", "ExecutionDisposition", "ExecutionSummary", "BatchOutcome",
    "RetryMaterial", "RetryKind",
    "OrchestrationStage", "IssueReason", "ItemIssue", "ItemWarning", "ResourceLimitReason",
    "DEFAULT_IMAGE_IN_FLIGHT_ITEMS", "MAX_IMAGE_IN_FLIGHT_ITEMS",
    "DEFAULT_FILESYSTEM_WORKERS", "MAX_FILESYSTEM_WORKERS",
    "MAX_BATCH_ITEMS", "MAX_ITEM_IMAGE_BYTES",
    "DEFAULT_MAX_RETAINED_ARTIFACT_BYTES", "MAX_RETAINED_ARTIFACT_BYTES_LIMIT",
    "OrchestrationError", "OrchestrationConfigError", "OrchestrationInputError", "OrchestrationBusyError",
    "OrchestrationContractError", "OrchestrationIntegrityError", "OrchestrationConsumedError",
    "OrchestrationRetryError",
    "OrchestrationResourceLimitError",
)
CONTRACT = Path(__file__).resolve().parents[2] / "docs" / "specifications" / "PHASE4_BATCH_ORCHESTRATION_CONTRACT.md"
_STAGE_APIS = {"build_organize_plan", "prepare_publication", "render_movie_nfo", "build_artifact_requests",
               "preflight_execution"}

_ALLOWED_STDLIB = {"__future__", "asyncio", "collections.abc", "dataclasses", "enum", "ntpath", "os", "posixpath",
                   "re", "secrets", "threading", "typing",
                   "functools", "inspect"}  # S2-R3: orchestrator.py only (its per-module allow-list above)
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
    "__init__.py": {f"{_PKG}.cancellation", f"{_PKG}.errors", f"{_PKG}.models", f"{_PKG}.orchestrator",
                    f"{_PKG}.retry"},
    "errors.py": {"__future__"},
    "cancellation.py": {"__future__", "threading"},
    "_consumption.py": {"__future__", "threading"},
    "models.py": {"__future__", "dataclasses", "enum", f"{_PKG}.errors"} | _LOWER_MODELS,
    "recognition.py": {"__future__", "collections.abc", "dataclasses", "os", f"{_PKG}.errors", f"{_PKG}.models",
                       "fc2_metadata_core.normalize", "fc2_organizer.discovery"},
    # S2 (contract sections 5, 34.1)
    "stages.py": {"__future__", "os", "fc2_metadata_core.batch", "fc2_organizer.execution", "fc2_organizer.images",
                  "fc2_organizer.materialization", "fc2_organizer.materialization.mapping", "fc2_organizer.nfo",
                  "fc2_organizer.planning", "fc2_organizer.publication", f"{_PKG}.models"},
    "preview.py": {"__future__", "asyncio", "dataclasses", "secrets", "fc2_organizer.images.acquisition",
                   f"{_PKG}.errors", f"{_PKG}.models", f"{_PKG}.recognition", f"{_PKG}.stages"},
    "orchestrator.py": {"__future__", "functools", "inspect", "threading", "fc2_metadata_core.batch",
                        "fc2_organizer.images",
                        "fc2_organizer.planning", f"{_PKG}.errors", f"{_PKG}.execute", f"{_PKG}.models",
                        f"{_PKG}.preview", f"{_PKG}.retry"},
    # S3 (contract sections 5, 34.1)
    "execute.py": {"__future__", "secrets", "threading", "fc2_organizer.execution", f"{_PKG}._consumption",
                   f"{_PKG}.cancellation", f"{_PKG}.errors", f"{_PKG}.models"},
    # S4 (contract sections 5, 34.1): retry.py may import stages and preview (never acquire_images)
    "retry.py": {"__future__", "secrets", "fc2_metadata_core.batch", "fc2_organizer.images", "fc2_organizer.planning",
                 f"{_PKG}._consumption", f"{_PKG}.errors", f"{_PKG}.models", f"{_PKG}.preview", f"{_PKG}.stages"},
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


def _contract_section(heading: str, until: str) -> str:
    text = CONTRACT.read_text(encoding="utf-8")
    start = text.index(heading)
    return text[start:text.index(until, start)]


def test_package_has_exactly_the_final_modules():
    names = {p.name for p in _files()}
    assert names == _FINAL_MODULES
    table = _contract_section("## 5. ", "## 6. ")
    frozen = {line.split("`")[1] for line in table.splitlines() if line.startswith("| `") and ".py`" in line}
    assert frozen == _FINAL_MODULES  # the contract's own frozen module table
    assert not [p for p in ORCH_SRC_ROOT.iterdir() if p.is_dir() and p.name != "__pycache__"]


def test_every_module_imports_only_its_allow_list():
    for path in _files():
        imported = _imports(_tree(path))
        assert imported <= _ALLOWED[path.name], (path.name, imported - _ALLOWED[path.name])
        assert imported <= _ALLOWED_STDLIB | _ALLOWED_LOWER | {f"{_PKG}.{m[:-3]}" for m in _FINAL_MODULES}, path.name


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
        for writer in _WRITER_NAMES - ({"execute_filesystem"} if path.name == "execute.py" else set()):
            assert writer not in names | attrs | aliases, (path.name, writer)
        for concurrency in ("gather", "ThreadPoolExecutor", "ProcessPoolExecutor", "run_in_executor",
                            "to_thread", "ensure_future", "Timer"):
            assert concurrency not in names | attrs | aliases, (path.name, concurrency)
        if path.name != "execute.py":
            assert "Thread" not in names | attrs | aliases, path.name
        if path.name != "preview.py":
            assert not {"create_task", "TaskGroup"} & (names | attrs | aliases), path.name
        if path.name not in {"preview.py", "orchestrator.py", "retry.py"}:
            for node in ast.walk(tree):
                assert not isinstance(node, (ast.AsyncFunctionDef, ast.Await)), path.name


def test_image_workers_are_created_once_in_a_bounded_loop():
    tree = _tree(ORCH_SRC_ROOT / "preview.py")
    creates = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and _call_name(n) == "create_task"]
    assert len(creates) == 1
    loops = [n for n in ast.walk(tree) if isinstance(n, ast.For) and creates[0] in list(ast.walk(n))]
    assert len(loops) == 1
    iterator = loops[0].iter
    assert _call_name(iterator) == "range" and len(iterator.args) == 1 and _call_name(iterator.args[0]) == "min"
    assert getattr(creates[0].func.value, "id", None) == "group"


def test_stage_api_and_acquire_images_ownership():
    for path in _files():
        tree = _tree(path)
        names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} | {
            n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)} | {
            a.name for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) for a in n.names}
        if path.name != "stages.py":
            assert not names & _STAGE_APIS, (path.name, names & _STAGE_APIS)
        if path.name != "preview.py":
            assert "acquire_images" not in names, path.name
    assert "fc2_organizer.images.acquisition" not in _imports(_tree(ORCH_SRC_ROOT / "stages.py"))


def test_retention_ledger_lives_only_in_preview_and_is_call_local():
    classes = {path.name: {n.name for n in ast.walk(_tree(path)) if isinstance(n, ast.ClassDef)} for path in _files()}
    assert {name for name, defined in classes.items() if "_Ledger" in defined} == {"preview.py"}
    for module in ("preview.py", "retry.py"):  # S4: retry.py uses preview's ledger, call-locally too
        tree = _tree(ORCH_SRC_ROOT / module)
        for node in tree.body:  # type: ignore[attr-defined]
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                if any(getattr(t, "id", None) == "__all__" for t in targets):
                    continue
                value = node.value
                assert not isinstance(value, (ast.List, ast.Dict, ast.Set, ast.ListComp, ast.DictComp,
                                              ast.SetComp)), module
                assert not (isinstance(value, ast.Call) and _call_name(value) in {"_Ledger", "list", "dict", "set"})
        assert not any(isinstance(n, (ast.Global, ast.Nonlocal)) for n in ast.walk(tree)), module


def test_preview_claims_busy_first():
    tree = _tree(ORCH_SRC_ROOT / "orchestrator.py")
    preview = next(n for n in ast.walk(tree) if isinstance(n, ast.AsyncFunctionDef) and n.name == "preview")
    body = preview.body
    if isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
        body = body[1:]  # docstring
    assert isinstance(body[0], ast.Expr) and _call_name(body[0].value) == "_claim"
    assert isinstance(body[1], ast.Try) and body[1].finalbody
    assert _call_name(body[1].finalbody[0].value) == "_release"
    methods = {n.name for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    assert "merge_retry" not in methods  # module-level, in retry.py
    retry = next(n for n in ast.walk(tree) if isinstance(n, ast.AsyncFunctionDef) and n.name == "preview_retry")
    body = retry.body
    if isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
        body = body[1:]  # docstring
    assert isinstance(body[0], ast.Expr) and _call_name(body[0].value) == "_claim"
    assert isinstance(body[1], ast.Try) and _call_name(body[1].finalbody[0].value) == "_release"
    delegated = [n for n in ast.walk(retry) if isinstance(n, ast.Call) and _call_name(n) == "build_retry_preview"]
    assert len(delegated) == 1  # S4: orchestrator.py only delegates preview_retry
    execute = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "execute")
    body = execute.body
    if isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
        body = body[1:]  # docstring
    assert isinstance(body[0], ast.Expr) and _call_name(body[0].value) == "_claim"
    assert isinstance(body[1], ast.Try) and _call_name(body[1].finalbody[0].value) == "_release"
    delegated = [n for n in ast.walk(execute) if isinstance(n, ast.Call) and _call_name(n) == "execute_preview"]
    assert len(delegated) == 1  # orchestrator.py only delegates; it never names execute_filesystem


def test_execute_filesystem_has_one_call_site_on_the_previews_own_preflight():
    tree = _tree(ORCH_SRC_ROOT / "execute.py")
    calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and _call_name(n) == "execute_filesystem"]
    assert len(calls) == 1 and len(calls[0].args) == 1 and not calls[0].keywords
    argument = calls[0].args[0]
    assert isinstance(argument, ast.Attribute) and argument.attr == "preflight"
    assert getattr(argument.value, "id", None) == "item"
    owner = next(fn for fn in ast.walk(tree) if isinstance(fn, ast.FunctionDef) and calls[0] in list(ast.walk(fn)))
    assert owner.name == "_execute_one"
    for name in _STAGE_APIS | {"acquire_images", "scheduler"}:  # no re-preflight / rebuild before execution
        assert name not in {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}, name


def _function(tree: ast.AST, name: str):
    return next(n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name)


def _registration_is_last(function, registry: str) -> None:
    """The one-time ``<registry>.register(...)`` is the statement right before the final ``return``."""
    *_, guard, final = function.body
    assert isinstance(final, ast.Return), function.name
    calls = [n for n in ast.walk(guard) if isinstance(n, ast.Call) and _call_name(n) == "register"]
    assert isinstance(guard, ast.If) and len(calls) == 1, function.name
    assert getattr(calls[0].func.value, "id", None) == registry, function.name
    registrations = [n for n in ast.walk(function) if isinstance(n, ast.Call) and _call_name(n) == "register"]
    assert registrations == calls, function.name  # no earlier registration anywhere in the function


def test_s4_retry_ownership_purity_and_late_registration():
    definitions: dict[str, set[str]] = {}
    for path in _files():
        for node in ast.walk(_tree(path)):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                definitions.setdefault(node.name, set()).add(path.name)
    for name in ("merge_retry", "base_retained", "build_retry_preview"):
        assert definitions[name] == {"retry.py"}, name
    tree = _tree(ORCH_SRC_ROOT / "retry.py")
    merge = _function(tree, "merge_retry")
    assert isinstance(merge, ast.FunctionDef)  # synchronous, pure composition (contract section 26)
    names = {n.id for n in ast.walk(merge) if isinstance(n, ast.Name)} | {
        n.attr for n in ast.walk(merge) if isinstance(n, ast.Attribute)}
    for forbidden in ("scheduler", "retry_failed", "apply_retry", "image_client", "preflight_stage", "manifest_stage",
                      "plan_stage", "phase_b_conflicts", "_image_stage", "_Ledger", "bytes", "deepcopy"):
        assert forbidden not in names, forbidden
    _registration_is_last(merge, "RETRY_MERGES")
    _registration_is_last(_function(tree, "build_retry_preview"), "RESULT_RETRIES")
    imported = {a.name for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) for a in n.names}
    assert {"_image_stage", "_Ledger"} <= imported and "acquire_images" not in imported
    assert "fc2_organizer.images.acquisition" not in _imports(tree)


def test_worker_threads_are_bounded_non_daemon_and_created_once():
    tree = _tree(ORCH_SRC_ROOT / "execute.py")
    creations = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and _call_name(n) == "Thread"]
    assert len(creations) == 1
    keywords = {k.arg: k.value for k in creations[0].keywords}
    assert isinstance(keywords.get("daemon"), ast.Constant) and keywords["daemon"].value is False
    comprehensions = [n for n in ast.walk(tree) if isinstance(n, ast.ListComp) and creations[0] in list(ast.walk(n))]
    assert len(comprehensions) == 1
    generator = comprehensions[0].generators[0]
    assert _call_name(generator.iter) == "range" and getattr(generator.iter.args[0], "id", None) == "workers"
    for path in _files():
        if path.name != "execute.py":
            assert "threading.Thread" not in path.read_text(encoding="utf-8"), path.name


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


_FC2_ROOTS = frozenset({"fc2_organizer", "fc2_metadata_core"})


def _purge(roots: frozenset[str] = _FC2_ROOTS) -> None:
    for name in list(sys.modules):
        if name.split(".")[0] in roots:
            del sys.modules[name]


@contextlib.contextmanager
def _isolated_imports(*, block: bool = False):
    """Fresh imports of the packages (and, with ``block``, the forbidden roots unloaded behind a trap). On every
    exit -- pass, assertion, import error or any other exception -- the exact pre-test module objects of
    ``fc2_organizer`` / ``fc2_metadata_core`` / the blocked roots and the exact ``sys.meta_path`` list come back, so
    no test leaves a second copy of a package (whose exact-type checks would reject the first copy's objects)."""
    roots = _FC2_ROOTS | _BLOCKED_ROOTS
    saved_modules = {name: module for name, module in sys.modules.items() if name.split(".")[0] in roots}
    saved_meta_path = list(sys.meta_path)
    blocker = _BlockFinder() if block else None
    try:
        _purge(_FC2_ROOTS | (_BLOCKED_ROOTS if block else frozenset()))
        if blocker is not None:
            sys.meta_path.insert(0, blocker)
        yield blocker
    finally:
        sys.meta_path[:] = saved_meta_path
        _purge(roots)
        sys.modules.update(saved_modules)


def _bare_import_body() -> None:
    importlib.import_module("fc2_organizer")
    assert _PKG not in sys.modules


def test_bare_import_of_fc2_organizer_does_not_load_orchestration():
    with _isolated_imports():
        _bare_import_body()


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


def test_public_api_is_exactly_the_final_contract_list():
    block = _contract_section("### 7.1 ", "### 7.2 ").split("```text", 1)[1].split("```", 1)[0]
    parsed = tuple(name.strip() for name in block.replace("\n", ",").split(",") if name.strip())
    assert parsed == _FINAL_PUBLIC_API  # the test's list is the contract's list, in order
    with _isolated_imports():
        _public_api_body()


def _public_api_body() -> None:
    orchestration = importlib.import_module(_PKG)
    assert type(orchestration.__all__) is list and tuple(orchestration.__all__) == _FINAL_PUBLIC_API
    assert len(orchestration.__all__) == len(set(orchestration.__all__)) == 37
    assert set(_FINAL_PUBLIC_API) == _S1_PUBLIC_API | {"BatchOrchestrator", "merge_retry", "PreviewSummary",
                                                       "ExecutionSummary"}
    for name in orchestration.__all__:
        assert hasattr(orchestration, name), name
    assert callable(orchestration.BatchOrchestrator.execute) and callable(orchestration.merge_retry)
    assert callable(orchestration.BatchOrchestrator.preview_retry)
    assert isinstance(orchestration.BatchPreview.summary, property)
    assert isinstance(orchestration.BatchExecutionResult.summary, property)
    for name in ("merge_retry", "summary"):
        assert not hasattr(orchestration.BatchOrchestrator, name), name
    exported = set(_FINAL_PUBLIC_API)
    for name in (_LATER_OR_FORBIDDEN_PUBLIC - exported) | {
            "revalidate", "type_name", "reason_detail", "bounded_snapshot", "retry_payload_bytes",
            "ConsumptionRegistry", "build_retry_preview", "base_retained", "build_preview", "execute_preview"}:
        assert name not in orchestration.__all__ and not hasattr(orchestration, name), name
    public = {name for name in vars(orchestration) if not name.startswith("_")}
    assert public - exported <= {"cancellation", "errors", "models", "orchestrator", "preview", "execute",
                                 "retry", "stages", "recognition"}  # only submodule names besides __all__


_BLOCKED_ROOTS = {"amane", "requests", "sqlite3", "shelve", "dbm", "pickle"}


class _BlockFinder:
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".")[0] in _BLOCKED_ROOTS:
            raise ImportError(f"fc2_organizer.orchestration attempted to import forbidden module: {fullname}")
        return None


class _Engine:
    """Every source missing: a real FAILED aggregation (no network)."""

    def __init__(self, aggregation):
        self.aggregation = aggregation

    async def aggregate(self, number):
        models = importlib.import_module("fc2_metadata_core.models")
        failed = models.SourceResult(source_id="s", status=models.SourceStatus.NOT_FOUND, metadata=None,
                                     elapsed_ms=0.0, error_kind=models.SourceErrorKind("not_found"),
                                     error_detail="scripted")
        return self.aggregation.merge_source_results(number, [failed], self.aggregation.AggregationPolicy.build(("s",)))


class _Client:
    async def get(self, url, *, deadline_seconds, max_redirects, max_bytes):  # pragma: no cover - no URLs
        raise AssertionError("no image request expected")


def _run_real_preview(orchestration, discovery, tmp_path) -> None:
    import asyncio

    aggregation = importlib.import_module("fc2_metadata_core.aggregation")
    (tmp_path / "dl").mkdir()
    (tmp_path / "dl" / "FC2-PPV-1234567.mp4").write_bytes(b"media")
    (tmp_path / "lib").mkdir()
    items = discovery.discover_media(str(tmp_path / "dl")).items
    orchestrator = orchestration.BatchOrchestrator(_Engine(aggregation), _Client(), str(tmp_path / "lib"))
    preview = asyncio.run(orchestrator.preview(items))
    assert [i.issue.reason for i in preview.items] == [orchestration.IssueReason.METADATA_UNAVAILABLE]
    assert (tmp_path / "dl" / "FC2-PPV-1234567.mp4").read_bytes() == b"media"
    assert not any((tmp_path / "lib").iterdir())


def test_orchestration_imports_and_runs_with_forbidden_modules_blocked(tmp_path):
    with _isolated_imports(block=True):
        _forbidden_run_body(tmp_path)


def _forbidden_run_body(tmp_path) -> None:
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
    _run_real_preview(orchestration, discovery, tmp_path)
    loaded = set(sys.modules)
    assert not any(n.split(".")[0] in _BLOCKED_ROOTS for n in loaded)


def test_the_full_lifecycle_runs_with_forbidden_modules_blocked(tmp_path):
    """S5: preview -> execute -> preview_retry -> execute -> merge_retry -> summaries, end to end, while ``amane`` /
    ``requests`` / ``sqlite3`` / ``shelve`` / ``dbm`` / ``pickle`` cannot be imported (positive control included)."""
    with _isolated_imports(block=True):
        _lifecycle_body(tmp_path)


def _lifecycle_body(tmp_path) -> None:
    for root in sorted(_BLOCKED_ROOTS):  # positive control: the trap really fires
        try:
            importlib.import_module(root)
        except ImportError:
            continue
        raise AssertionError(f"the forbidden-module trap did not fire for {root}")
    import asyncio

    orchestration = importlib.import_module(_PKG)
    discovery = importlib.import_module("fc2_organizer.discovery")
    aggregation = importlib.import_module("fc2_metadata_core.aggregation")
    (tmp_path / "dl").mkdir()
    (tmp_path / "dl" / "FC2-PPV-1234567.mp4").write_bytes(b"media")
    (tmp_path / "lib").mkdir()
    items = discovery.discover_media(str(tmp_path / "dl")).items
    orchestrator = orchestration.BatchOrchestrator(_Engine(aggregation), _Client(), str(tmp_path / "lib"))
    preview = asyncio.run(orchestrator.preview(items))
    result = orchestrator.execute(preview)
    retry = asyncio.run(orchestrator.preview_retry(result))
    merged = orchestration.merge_retry(result, orchestrator.execute(retry))
    assert preview.summary.unprepared == 1 and merged.summary.retryable == 1 and merged.generation == 1
    assert merged.outcome is orchestration.BatchOutcome.FAILED
    assert (tmp_path / "dl" / "FC2-PPV-1234567.mp4").read_bytes() == b"media"
    assert not any(n.split(".")[0] in _BLOCKED_ROOTS for n in sys.modules)


# --------------------------------------------------------------------------- S5-R1: import-state isolation


def _import_state():
    roots = _FC2_ROOTS | _BLOCKED_ROOTS
    return {name: module for name, module in sys.modules.items() if name.split(".")[0] in roots}, list(sys.meta_path)


def _assert_restored(before) -> None:
    modules, meta_path = before
    now_modules, now_meta_path = _import_state()
    assert now_modules.keys() == modules.keys()
    assert all(now_modules[name] is modules[name] for name in modules)  # the very same objects
    assert len(now_meta_path) == len(meta_path) and all(a is b for a, b in zip(now_meta_path, meta_path))


def _baseline():
    importlib.import_module(_PKG)  # the packages as a normal test session holds them
    importlib.import_module("pickle")  # a blocked root loaded beforehand must come back as the same object
    before = _import_state()
    assert _PKG in before[0] and "fc2_metadata_core" in before[0] and "pickle" in before[0]
    return before


def test_import_isolation_restores_the_exact_module_objects_and_meta_path_repeatedly(tmp_path):
    before = _baseline()
    for round_number in range(2):  # repeated lifecycles accumulate no residue
        with _isolated_imports(block=True) as blocker:
            assert sys.meta_path[0] is blocker and "pickle" not in sys.modules
            workspace = tmp_path / f"round{round_number}"
            workspace.mkdir()
            _lifecycle_body(workspace)
            assert sys.modules[_PKG] is not before[0][_PKG]  # it really ran on a fresh copy
        _assert_restored(before)


def test_import_isolation_is_independent_of_test_order(tmp_path):
    before = _baseline()
    for order in (("api", "lifecycle"), ("lifecycle", "api")):
        for step in order:
            if step == "api":
                with _isolated_imports():
                    _public_api_body()
            else:
                workspace = tmp_path / "-".join(order)
                workspace.mkdir()
                with _isolated_imports(block=True):
                    _lifecycle_body(workspace)
            _assert_restored(before)


class _Interrupted(Exception):
    pass


class _ExtraFinder:
    def find_spec(self, fullname, path=None, target=None):
        return None


def test_import_isolation_restores_after_an_exception_and_a_disturbed_meta_path():
    before = _baseline()
    with pytest.raises(_Interrupted):
        with _isolated_imports(block=True) as blocker:
            assert sys.meta_path[0] is blocker
            importlib.import_module(_PKG)
            sys.meta_path.append(_ExtraFinder())
            sys.meta_path.insert(1, sys.meta_path.pop())  # another finder, and a different order
            raise _Interrupted()
    _assert_restored(before)
    assert not any(isinstance(finder, (_BlockFinder, _ExtraFinder)) for finder in sys.meta_path)
