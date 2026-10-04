"""P5-C1 表 A / I2 / I26（E3）：adapter 只使用 Amane v0.15.0 公共 API 清单里的名字与关键字。

清单由 ``tools/amane_api_manifest.py`` 从 exact v0.15.0（``45dff21…``）源码的 AST 生成并提交；
本测试**不** import amane，只读清单与 adapter 源码的 AST。真实 import 见证见 H-01。
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from fc2_amane_adapter import _settings as _module_under_test

ROOT = Path(__file__).resolve().parents[2]
#: 被检查的树 = 被测模块实际所在的树（mutation 运行时是被篡改的副本）。
TREE = Path(_module_under_test.__file__).resolve().parent
MANIFEST = json.loads((ROOT / "adapters" / "amane" / "api_manifest" / "amane_v0.15.0_api_manifest.json").read_text(encoding="utf-8"))

AMANE_COMMIT = "45dff2159369883e028a296d775a4598836c1ddd"
FORBIDDEN_SINGLE_VERSION_NAMES = {"max_attempts", "traits", "multi_language", "raw_results", "partial_result", "check_connectivity"}


def _tree(name: str) -> ast.Module:
    return ast.parse((TREE / name).read_text(encoding="utf-8"), filename=name)


def _all_tree_files() -> list[Path]:
    return sorted(TREE.glob("*.py"))


def _call_keywords(tree: ast.Module, callee: str) -> list[str]:
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            label = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else None
            if label == callee:
                names.extend(keyword.arg for keyword in node.keywords if keyword.arg is not None)
    return names


def _fields(cls: str) -> set[str]:
    return set(MANIFEST["classes"][cls]["fields"])


def _params(cls: str, method: str) -> set[str]:
    return {param["name"] for param in MANIFEST["classes"][cls]["methods"][method]["params"]}


def test_manifest_is_generated_from_exact_v0_15_0():
    assert MANIFEST["schema_version"] == 1
    assert MANIFEST["amane"]["commit"] == AMANE_COMMIT
    assert MANIFEST["amane"]["version"] == "0.15.0"
    assert MANIFEST["amane"]["checkout_clean"] is True
    assert MANIFEST["constants"]["PLUGIN_API_VERSION"] == "1"


def test_manifest_records_the_contract_table_a_facts():
    assert set(MANIFEST["classes"]) >= {
        "FilmSourcePlugin", "FilmSourceProvider", "PluginContext", "SearchQuery", "FetchOptions", "MediaMetadata",
        "FilmActor", "SourceDescriptor", "SourceError", "RequestError", "WebClient", "HttpClient",
    }
    assert _fields("PluginContext") == {"source_id", "http_client", "web_client", "data_dir"}
    assert _fields("SearchQuery") == {"number", "file_path", "file_hash", "content_type", "partial_result", "raw_results"}
    assert _fields("MediaMetadata") == {
        "number", "title", "actors", "studio", "publisher", "release", "runtime", "tags", "series", "plot",
        "poster_urls", "thumb_urls", "trailer_urls", "score", "external_id", "source_url", "directors", "extrafanart",
    }
    assert "fanart_urls" not in _fields("MediaMetadata")
    assert _fields("SourceDescriptor") == {
        "id", "name", "version", "api_version", "capabilities", "content_types", "metadata_fields", "languages", "urls",
        "multi_language", "rate_limit",
    }
    fetch = MANIFEST["classes"]["FilmSourceProvider"]["methods"]["fetch"]
    assert fetch["async"] is True and [p["name"] for p in fetch["params"]] == ["self", "query", "options"]
    build = MANIFEST["classes"]["FilmSourcePlugin"]["methods"]["build"]
    assert build["async"] is False and [p["name"] for p in build["params"]] == ["self", "context", "config"]
    assert MANIFEST["classes"]["WebClient"]["methods"]["request"]["async"] is True
    assert "max_attempts" not in _params("WebClient", "request")
    assert MANIFEST["enums"]["ContentType"]["members"]["FC2"] == "fc2"
    assert MANIFEST["enums"]["SourceCapability"]["members"]["FILM_METADATA"] == "film_metadata"
    assert MANIFEST["classes"]["FilmActor"]["fields"]["gender"]["default"] == "ActorGender.UNKNOWN"


def test_plugin_py_imports_only_public_amane_plugin_names_from_the_manifest():
    tree = _tree("plugin.py")
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.module.split(".")[0] == "amane":
            assert node.module == "amane.plugin", node.module
            imported |= {alias.name for alias in node.names}
        elif isinstance(node, ast.Import):
            assert not any(alias.name.split(".")[0] == "amane" for alias in node.names)
    assert imported, "plugin.py must import from amane.plugin"
    assert imported <= set(MANIFEST["plugin_all"]), sorted(imported - set(MANIFEST["plugin_all"]))


def test_no_other_adapter_module_imports_amane():
    for path in _all_tree_files():
        if path.name == "plugin.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert not any(alias.name.split(".")[0] == "amane" for alias in node.names), path.name
            if isinstance(node, ast.ImportFrom):
                assert (node.module or "").split(".")[0] != "amane", path.name


@pytest.mark.parametrize(
    ("callee", "allowed"),
    [
        ("SourceDescriptor", lambda: _fields("SourceDescriptor")),
        ("MediaMetadata", lambda: _fields("MediaMetadata")),
        ("FilmActor", lambda: _fields("FilmActor")),
        ("SourceError", lambda: _params("SourceError", "__init__")),
    ],
)
def test_keywords_used_with_amane_constructors_exist_in_the_manifest(callee, allowed):
    used = _call_keywords(_tree("plugin.py"), callee)
    assert set(used) <= allowed(), sorted(set(used) - allowed())


def test_web_client_request_keywords_exist_in_the_manifest():
    used = _call_keywords(_tree("_bridge.py"), "request")
    assert used, "the bridge must call web_client.request"
    assert set(used) <= _params("WebClient", "request"), sorted(set(used) - _params("WebClient", "request"))
    assert "ok_statuses" in used


def test_descriptor_declares_only_the_cross_version_subset():
    used = set(_call_keywords(_tree("plugin.py"), "SourceDescriptor"))
    assert not used & {"api_version", "multi_language", "traits", "rate_limit"}
    assert used == {"id", "name", "version", "capabilities", "content_types", "metadata_fields", "languages", "urls"}


def test_no_single_version_host_names_are_used_anywhere_in_the_tree():
    """I26：不用 max_attempts / traits / multi_language / raw_results / partial_result / check_connectivity。"""
    for path in _all_tree_files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        used: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                used.add(node.id)
            elif isinstance(node, ast.Attribute):
                used.add(node.attr)
            elif isinstance(node, ast.keyword) and node.arg:
                used.add(node.arg)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                used.add(node.name)
        assert not used & FORBIDDEN_SINGLE_VERSION_NAMES, (path.name, sorted(used & FORBIDDEN_SINGLE_VERSION_NAMES))


def test_enum_members_used_by_the_plugin_exist_in_the_manifest():
    tree = _tree("plugin.py")
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id in MANIFEST["enums"]:
            assert node.attr in MANIFEST["enums"][node.value.id]["members"], (node.value.id, node.attr)
