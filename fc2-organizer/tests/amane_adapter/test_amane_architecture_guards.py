"""P5-C1 §8 / §18 / §23 / §25（E17 E18 E19 静态 E27）：插件树布局、依赖方向与禁用模式的 AST 守护。

全部是静态检查（AST）；不 import amane，不修改 ``sys.modules``。
"""

from __future__ import annotations

import ast
import os
from pathlib import Path

import pytest

from fc2_amane_adapter import _settings as _module_under_test

ROOT = Path(__file__).resolve().parents[2]
REPO_TREE = ROOT / "adapters" / "amane" / "fc2_amane_adapter"
#: 被检查的树 = 被测模块实际所在的树（mutation 运行时是被篡改的副本；平时是仓库内的插件树）。
TREE = Path(_module_under_test.__file__).resolve().parent
TESTS = ROOT / "tests"
NEW_TESTS = TESTS / "amane_adapter"
HOST_SCRIPTS = NEW_TESTS / "host_scripts"

REQUIRED_MODULES = {"plugin.py", "_core_gate.py", "_settings.py", "_number.py", "_bridge.py", "_runtime.py", "_outcome.py"}
OPTIONAL_MODULES: set[str] = set()

#: 合同 §8.4：adapter 允许使用的 Core 名字白名单。
CORE_WHITELIST = {
    "fc2_metadata_core.normalize": {"normalize_fc2_number", "FC2RecognitionStatus"},
    "fc2_metadata_core.aggregation": {
        "AggregationConfig", "SourceConfig", "RetryPolicy", "MultiSourceEngine", "AggregateStatus", "AggregationResult",
        "AggregationConfigError", "DEFAULT_MAX_CONCURRENCY", "DEFAULT_SOURCE_DEADLINE_SECONDS", "DEFAULT_SOURCE_ORDER",
        "validate_base_url",
    },
    "fc2_metadata_core.sources": {"SourceRegistry"},
    "fc2_metadata_core.sources.adapters": {"build_default_registry", "ALL_ADAPTER_CLASSES"},
    "fc2_metadata_core.resource_control": {"SourceResourceGovernor"},
    "fc2_metadata_core.http": {
        "HttpResponse", "HttpTransportError", "HttpTimeoutError", "HttpConnectionError", "HttpResponseTooLargeError",
    },
    "fc2_metadata_core.http.client": {"HttpDecodingError"},
    "fc2_metadata_core.models": {"NormalizedMetadata", "SourceResult", "SourceStatus", "SourceErrorKind"},
}

PURE_STDLIB = {"__future__", "codecs", "collections.abc", "dataclasses", "logging", "math", "time", "typing", "enum", "urllib.parse"}
FORBIDDEN_ROOTS = {
    "amane", "pydantic", "httpx", "requests", "aiohttp", "curl_cffi", "urllib3", "socket", "subprocess", "sqlite3",
    "shelve", "pickle", "tempfile", "os", "shutil", "pathlib", "asyncio", "threading", "fc2_organizer",
}
FS_WRITE_CALLS = {
    "open", "write_text", "write_bytes", "mkdir", "makedirs", "rename", "replace", "remove", "unlink", "rmtree",
    "system", "Popen", "touch", "chmod",
}


def _modules() -> dict[str, ast.Module]:
    return {path.name: ast.parse(path.read_text(encoding="utf-8"), filename=path.name) for path in sorted(TREE.glob("*.py"))}


def _imports(tree: ast.Module):
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            yield node


def _nested_in_function(tree: ast.Module):
    """逐个产出位于函数 / lambda 体内的 import 节点。"""

    def visit(node: ast.AST, inside: bool):
        for child in ast.iter_child_nodes(node):
            now_inside = inside or isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda))
            if isinstance(child, (ast.Import, ast.ImportFrom)) and inside:
                yield child
            yield from visit(child, now_inside)

    yield from visit(tree, False)


def test_the_adapter_under_test_is_the_expected_tree():
    """哨兵：被测的 ``fc2_amane_adapter`` 来自预期的树。mutation 运行时（``P5_C1_MUTANT_ROOT``）必须来自被篡改的副本，
    证明被杀死的测试确实测的是被篡改的代码；平时必须来自仓库内的插件树。"""
    located = Path(_module_under_test.__file__).resolve()
    mutant_root = os.environ.get("P5_C1_MUTANT_ROOT")
    expected_parent = (Path(mutant_root) / "fc2_amane_adapter") if mutant_root else REPO_TREE
    assert located.parent == expected_parent.resolve(), (located, expected_parent)


def test_layout_is_exactly_the_frozen_plugin_tree():
    present = {path.name for path in TREE.iterdir() if path.name != "__pycache__"}
    assert REQUIRED_MODULES <= present <= REQUIRED_MODULES | OPTIONAL_MODULES, sorted(present)
    assert not (TREE / "__init__.py").exists(), "the plugin tree must not have __init__.py"
    assert (TREE / "plugin.py").is_file()
    assert not (ROOT / "adapters" / "amane" / "__init__.py").exists()


def test_every_tree_file_is_python_3_11_compatible_syntax():
    for path in sorted(TREE.glob("*.py")):
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=path.name, feature_version=(3, 11))
        compile(source, path.name, "exec")
        assert not any(isinstance(node, ast.TypeAlias) for node in ast.walk(tree)), path.name
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef)):
                assert not getattr(node, "type_params", None), path.name


def test_imports_are_module_level_only_never_inside_functions():
    for name, tree in _modules().items():
        assert not list(_nested_in_function(tree)), f"{name}: function-body import"


def test_intra_tree_imports_are_relative_only():
    for name, tree in _modules().items():
        for node in _imports(tree):
            if isinstance(node, ast.ImportFrom):
                if node.level:
                    assert node.level == 1 and node.module and (node.module.startswith("_") or node.module == "plugin"), (name, node.module)
                    assert (TREE / f"{node.module}.py").is_file(), (name, node.module)
                else:
                    assert (node.module or "").split(".")[0] != "fc2_amane_adapter", name
            else:
                assert not any(alias.name.split(".")[0] == "fc2_amane_adapter" for alias in node.names), name


def test_core_names_are_limited_to_the_contract_whitelist():
    for name, tree in _modules().items():
        for node in _imports(tree):
            if isinstance(node, ast.Import):
                assert not any(alias.name.split(".")[0] == "fc2_metadata_core" for alias in node.names), (name, "plain import")
                continue
            if node.level or not node.module or node.module.split(".")[0] != "fc2_metadata_core":
                continue
            assert node.module in CORE_WHITELIST, (name, node.module)
            used = {alias.name for alias in node.names}
            assert used <= CORE_WHITELIST[node.module], (name, node.module, sorted(used - CORE_WHITELIST[node.module]))
            assert "httpx_client" not in node.module


def test_pure_modules_import_only_stdlib_subset_core_and_siblings():
    for name, tree in _modules().items():
        if name == "plugin.py":
            continue
        for node in _imports(tree):
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            else:
                modules = [("." * node.level) + (node.module or "")]
            for module in modules:
                if module.startswith("."):
                    continue
                root = module.split(".")[0]
                assert root not in FORBIDDEN_ROOTS, (name, module)
                assert root == "fc2_metadata_core" or module in PURE_STDLIB, (name, module)


def test_plugin_py_is_the_only_module_allowed_amane_and_pydantic():
    plugin = _modules()["plugin.py"]
    roots = set()
    for node in _imports(plugin):
        if isinstance(node, ast.Import):
            roots |= {alias.name.split(".")[0] for alias in node.names}
        elif not node.level:
            roots.add((node.module or "").split(".")[0])
    assert {"amane", "pydantic"} <= roots <= {"amane", "pydantic", "fc2_metadata_core"}
    assert not roots & (FORBIDDEN_ROOTS - {"amane", "pydantic"})


def test_no_independent_http_client_anywhere_in_the_tree():
    banned_roots = {"httpx", "requests", "aiohttp", "curl_cffi", "urllib3", "socket", "http"}
    banned_modules = {"urllib.request", "urllib.error", "http.client"}
    for name, tree in _modules().items():
        for node in _imports(tree):
            if isinstance(node, ast.Import):
                modules = {alias.name for alias in node.names}
            elif node.level:
                modules = set()
            else:
                modules = {node.module or ""} | {f"{node.module}.{alias.name}" for alias in node.names}
            assert not {m.split(".")[0] for m in modules} & banned_roots, (name, modules)
            assert not modules & banned_modules, (name, modules)
        names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} | {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
        assert "httpx_client" not in names and "HttpxTransport" not in names, name


def test_pure_modules_have_no_filesystem_write_or_process_side_effects():
    for name, tree in _modules().items():
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                label = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else None
                assert label not in FS_WRITE_CALLS, (name, label)
        names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
        assert "print" not in names, f"{name}: print"
        assert "environ" not in {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}


def test_cancellation_is_never_swallowed_no_broad_except_outside_runtime():
    for name, tree in _modules().items():
        for node in ast.walk(tree):
            if not isinstance(node, ast.ExceptHandler):
                continue
            assert node.type is not None, f"{name}: bare except"
            caught = {n.id for n in ast.walk(node.type) if isinstance(n, ast.Name)} | {
                n.attr for n in ast.walk(node.type) if isinstance(n, ast.Attribute)
            }
            assert "BaseException" not in caught, f"{name}: except BaseException"
            assert "CancelledError" not in caught, f"{name}: except CancelledError"
            if name != "_runtime.py":
                assert "Exception" not in caught, f"{name}: except Exception outside _runtime.py"


def test_runtime_has_a_single_broad_except_wrapping_only_engine_aggregate():
    tree = _modules()["_runtime.py"]
    handlers = [n for n in ast.walk(tree) if isinstance(n, ast.ExceptHandler)]
    assert len(handlers) == 1
    (handler,) = handlers
    assert isinstance(handler.type, ast.Name) and handler.type.id == "Exception"
    try_node = next(n for n in ast.walk(tree) if isinstance(n, ast.Try) and handler in n.handlers)
    awaited = [n for stmt in try_node.body for n in ast.walk(stmt) if isinstance(n, ast.Await)]
    assert len(awaited) == 1
    call = awaited[0].value
    assert isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute) and call.func.attr == "aggregate"
    assert len(try_node.body) == 1


def test_no_set_iteration_in_mapping_modules():
    for name in ("_outcome.py", "_runtime.py"):
        tree = _modules()[name]
        set_names: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                value = node.value
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                is_set = isinstance(value, (ast.Set, ast.SetComp)) or (
                    isinstance(value, ast.Call) and isinstance(value.func, ast.Name) and value.func.id in {"set", "frozenset"}
                )
                if is_set:
                    set_names |= {t.id for t in targets if isinstance(t, ast.Name)}
        for node in ast.walk(tree):
            iterables = []
            if isinstance(node, (ast.For, ast.AsyncFor)):
                iterables.append(node.iter)
            if isinstance(node, ast.comprehension):
                iterables.append(node.iter)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in {"list", "tuple", "next", "iter"}:
                iterables.extend(node.args)
            for iterable in iterables:
                assert not (isinstance(iterable, ast.Name) and iterable.id in set_names), (name, iterable.id)
                assert not isinstance(iterable, (ast.Set, ast.SetComp)), name
                assert not (
                    isinstance(iterable, ast.Call) and isinstance(iterable.func, ast.Name) and iterable.func.id in {"set", "frozenset"}
                ), name


def test_plugin_py_has_the_frozen_entry_shape():
    tree = _modules()["plugin.py"]
    classes = {n.name: n for n in tree.body if isinstance(n, ast.ClassDef)}
    assert "Plugin" in classes
    bases = {ast.unparse(base) for base in classes["Plugin"].bases}
    assert bases == {"FilmSourcePlugin"}
    methods = {n.name: n for n in classes["Plugin"].body if isinstance(n, ast.FunctionDef)}
    assert {"descriptor", "build"} <= set(methods)
    assert any(ast.unparse(d) == "classmethod" for d in methods["descriptor"].decorator_list)
    assert not any(isinstance(n, ast.AsyncFunctionDef) for n in classes["Plugin"].body), "build() must be synchronous"


# ---------------------------------------------------------------- 测试树守护（E22 静态 / E27）


def _test_files(include_host_scripts: bool = False) -> list[Path]:
    files = sorted(TESTS.rglob("*.py"))
    if not include_host_scripts:
        files = [f for f in files if HOST_SCRIPTS not in f.parents]
    return files


def test_no_test_imports_amane_except_host_scripts():
    for path in _test_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert not any(alias.name.split(".")[0] == "amane" for alias in node.names), path
            elif isinstance(node, ast.ImportFrom):
                assert (node.module or "").split(".")[0] != "amane" or node.level, path
    for path in sorted(NEW_TESTS.glob("*.py")) + [TESTS / "support" / "amane_host_fakes.py"]:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                label = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else None
                if label in {"import_module", "__import__"} and node.args and isinstance(node.args[0], ast.Constant):
                    assert not str(node.args[0].value).startswith("amane"), path


def _is_sys_modules(node: ast.AST) -> bool:
    return isinstance(node, ast.Attribute) and node.attr == "modules" and isinstance(node.value, ast.Name) and node.value.id == "sys"


def test_new_tests_never_clear_replace_or_inject_sys_modules_or_stub_amane():
    """P5-C1 §25.1：新测试不使用 ``sys.modules`` 清理 / 替换 / 注入（只读的哨兵断言，如 ``"amane" not in sys.modules``，允许）。"""
    mutators = {"pop", "update", "setdefault", "clear", "popitem", "__setitem__", "__delitem__"}
    for path in sorted(NEW_TESTS.glob("*.py")):
        if path.name == Path(__file__).name:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        parents = {child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}
        for node in ast.walk(tree):
            if not _is_sys_modules(node):
                continue
            parent = parents[node]
            if isinstance(parent, ast.Subscript):
                assert isinstance(parent.ctx, ast.Load), f"{path.name}: sys.modules[...] write/delete"
            if isinstance(parent, ast.Attribute) and parent.attr in mutators:
                raise AssertionError(f"{path.name}: sys.modules.{parent.attr}")
            if isinstance(parent, ast.Call):  # 例如 monkeypatch.setitem(sys.modules, ...) / patch.dict(sys.modules, ...)
                raise AssertionError(f"{path.name}: sys.modules passed to a call")
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in {"ModuleType"}:
                raise AssertionError(f"{path.name}: stub module")


def test_new_tests_have_no_skip_or_xfail():
    """E27：新增测试不得 skip / xfail。"""
    own = Path(__file__).name
    for path in sorted(NEW_TESTS.glob("*.py")) + [TESTS / "support" / "amane_host_fakes.py"]:
        if path.name == own:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr in {"skip", "skipif", "xfail", "importorskip"}:
                raise AssertionError(f"{path.name}: {node.attr}")
            if isinstance(node, ast.Name) and node.id in {"skip", "skipif", "xfail", "importorskip"}:
                raise AssertionError(f"{path.name}: {node.id}")


def test_new_test_modules_are_named_uniquely_and_host_scripts_are_not_collectable():
    new = sorted(NEW_TESTS.glob("*.py"))
    helpers = [path for path in new if path.name.startswith("_")]  # 下划线前缀的共享 helper / 子进程探针：不被 pytest 收集
    assert {path.name for path in helpers} == {"_amane_scenarios.py", "_determinism_probe.py"}
    tests = [path for path in new if path not in helpers]
    assert all(path.name.startswith("test_amane_") for path in tests), [p.name for p in tests if not p.name.startswith("test_amane_")]
    basenames = [path.name for path in TESTS.rglob("test_*.py")]
    assert len(basenames) == len(set(basenames)), "test basenames must be globally unique (no __init__.py in those dirs)"
    assert not (NEW_TESTS / "__init__.py").exists()
    for path in HOST_SCRIPTS.glob("*.py"):
        assert not path.name.startswith("test_") and not path.name.endswith("_test.py") and path.name != "conftest.py", path.name


def test_core_and_organizer_never_import_amane_and_nothing_else_imports_the_adapter():
    for path in (ROOT / "src").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert not any(alias.name.split(".")[0] in {"amane", "fc2_amane_adapter"} for alias in node.names), path
            elif isinstance(node, ast.ImportFrom) and not node.level:
                assert (node.module or "").split(".")[0] not in {"amane", "fc2_amane_adapter"}, path
