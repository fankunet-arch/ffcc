"""P5-C2 E03 / E04 / E15（静态部分）/ M2-07 / M2-08：Amane 坐标与公共 API 兼容矩阵（合同第 6、7 节）。

只读已提交的 AST 清单（``tools/amane_api_manifest.py`` 生成）与 adapter 源码；**不 import amane**。
合同第 6.2 节每一行“清单可见”的差异都有机检断言；非清单可见的行（``packaging.py`` 逐字节相同等）由 S2 宿主见证核对。
"""

from __future__ import annotations

import ast
import copy
import json
import subprocess
import sys

import pytest

from _compat_support import ADAPTER_TREE, REPO, TOOLS, load_tool

MANIFEST_DIR = REPO / "adapters" / "amane" / "api_manifest"
OLD = json.loads((MANIFEST_DIR / "amane_v0.15.0_api_manifest.json").read_text(encoding="utf-8"))
NEW = json.loads((MANIFEST_DIR / "amane_v0.18.0_api_manifest.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def compare():
    return load_tool("compare_amane_api.py")


def test_e03_manifest_coordinates_match_the_frozen_design_time_witness():
    assert OLD["amane"] == {"checkout_clean": True, "commit": "45dff2159369883e028a296d775a4598836c1ddd", "version": "0.15.0"}
    assert NEW["amane"] == {"checkout_clean": True, "commit": "0a8a731d7746bde5e8828d1eb74c7bd9752b42e4", "version": "0.18.0"}
    assert OLD["constants"]["PLUGIN_API_VERSION"] == NEW["constants"]["PLUGIN_API_VERSION"] == "1"
    assert OLD["schema_version"] == NEW["schema_version"] == 1


def test_e04_section_6_2_rows_visible_in_the_manifests():
    # amane.plugin 导出：只新增 4 个名字，没有移除
    assert set(NEW["plugin_all"]) - set(OLD["plugin_all"]) == {"ConnectivityOutcome", "ConnectivityStatus", "SkipReason", "SourceTrait"}
    assert not set(OLD["plugin_all"]) - set(NEW["plugin_all"])
    # SourceDescriptor：multi_language -> traits
    assert "multi_language" in OLD["classes"]["SourceDescriptor"]["fields"] and "traits" not in OLD["classes"]["SourceDescriptor"]["fields"]
    assert "traits" in NEW["classes"]["SourceDescriptor"]["fields"] and "multi_language" not in NEW["classes"]["SourceDescriptor"]["fields"]
    # FilmSourceProvider：新增非抽象 check_connectivity
    assert set(NEW["classes"]["FilmSourceProvider"]["methods"]) - set(OLD["classes"]["FilmSourceProvider"]["methods"]) == {"check_connectivity"}
    # PluginContext：字段完全相同
    assert OLD["classes"]["PluginContext"]["fields"] == NEW["classes"]["PluginContext"]["fields"]
    assert set(OLD["classes"]["PluginContext"]["fields"]) == {"source_id", "http_client", "web_client", "data_dir"}
    # SearchQuery：raw_results 被移除
    assert set(OLD["classes"]["SearchQuery"]["fields"]) - set(NEW["classes"]["SearchQuery"]["fields"]) == {"raw_results"}
    assert not set(NEW["classes"]["SearchQuery"]["fields"]) - set(OLD["classes"]["SearchQuery"]["fields"])
    # FetchOptions / MediaMetadata / FilmActor：字段无变化
    for name in ("FetchOptions", "MediaMetadata", "FilmActor"):
        assert OLD["classes"][name]["fields"] == NEW["classes"][name]["fields"], name
    # FailureReason：新增 API_ERROR，没有移除
    assert set(NEW["enums"]["FailureReason"]["members"]) - set(OLD["enums"]["FailureReason"]["members"]) == {"API_ERROR"}
    assert set(OLD["enums"]["FailureReason"]["members"]) <= set(NEW["enums"]["FailureReason"]["members"])
    # WebClient.request：新增 max_attempts（v0.15.0 没有）
    old_params = {p["name"] for p in OLD["classes"]["WebClient"]["methods"]["request"]["params"]}
    new_params = {p["name"] for p in NEW["classes"]["WebClient"]["methods"]["request"]["params"]}
    assert "max_attempts" not in old_params and "max_attempts" in new_params and old_params <= new_params
    # WebClient：新增 acquire / resolve_final_url
    assert {"acquire", "resolve_final_url"} <= set(NEW["classes"]["WebClient"]["methods"]) - set(OLD["classes"]["WebClient"]["methods"])
    # HttpClient：新增 for_source（按来源浏览器回退）
    assert "for_source" in NEW["classes"]["HttpClient"]["methods"] and "for_source" not in OLD["classes"]["HttpClient"]["methods"]
    # 其余已追踪类的方法集合不变
    for name in ("FilmSourcePlugin", "PluginContext", "SourceError", "RequestError", "FetchOptions", "MediaMetadata", "FilmActor", "SourceDescriptor"):
        assert set(OLD["classes"][name]["methods"]) == set(NEW["classes"][name]["methods"]), name


def test_e04_adapter_controlled_subset_fingerprint_is_equal_across_the_two_required_versions(compare):
    report = compare.compare({"a": OLD, "b": NEW}, ADAPTER_TREE)
    assert report["subsets_equal"] is True
    assert report["api_fingerprints"]["a"] != report["api_fingerprints"]["b"], "the full API did change between the two versions"
    used = report["used"]
    assert used["request_keywords"] == ["headers", "ok_statuses", "timeout"]
    assert used["query_attributes"] == ["content_type", "number"]
    assert used["constructor_keywords"]["SourceDescriptor"] == ["capabilities", "content_types", "id", "languages", "metadata_fields", "name", "urls", "version"]


@pytest.mark.parametrize(
    "mutation",
    ["drop_ok_statuses", "rename_number_field", "drop_fetch_method", "change_context_field", "drop_enum_member", "drop_descriptor_field"],
)
def test_e04_non_vacuity_a_change_in_the_used_surface_changes_the_fingerprint(compare, mutation):
    changed = copy.deepcopy(NEW)
    if mutation == "drop_ok_statuses":
        params = changed["classes"]["WebClient"]["methods"]["request"]["params"]
        changed["classes"]["WebClient"]["methods"]["request"]["params"] = [p for p in params if p["name"] != "ok_statuses"]
    elif mutation == "rename_number_field":
        changed["classes"]["SearchQuery"]["fields"]["numero"] = changed["classes"]["SearchQuery"]["fields"].pop("number")
    elif mutation == "drop_fetch_method":
        changed["classes"]["FilmSourceProvider"]["methods"].pop("fetch")
    elif mutation == "change_context_field":
        changed["classes"]["PluginContext"]["fields"]["web_client"]["annotation"] = "Other"
    elif mutation == "drop_enum_member":
        changed["enums"]["ContentType"]["members"].pop("FC2")
    else:
        changed["classes"]["SourceDescriptor"]["fields"].pop("urls")
    report = compare.compare({"a": OLD, "b": changed}, ADAPTER_TREE)
    assert report["subsets_equal"] is False, mutation


def test_e04_changes_outside_the_used_surface_do_not_change_the_fingerprint(compare):
    """适配器不使用的差异（traits / API_ERROR / check_connectivity / max_attempts …）不应使子集指纹改变（它们就是白名单差异）。"""
    changed = copy.deepcopy(OLD)
    changed["classes"]["SourceDescriptor"]["fields"].pop("multi_language")
    changed["classes"]["SourceDescriptor"]["fields"]["traits"] = {"annotation": "frozenset[str]", "default": "frozenset()"}
    changed["enums"]["FailureReason"]["members"]["API_ERROR"] = "api_error"
    assert compare.compare({"a": OLD, "b": changed}, ADAPTER_TREE)["subsets_equal"] is True


def test_compare_cli_returns_zero_for_equal_subsets_and_one_otherwise(tmp_path):
    base = [sys.executable, str(TOOLS / "compare_amane_api.py"), "--manifest", f"a={MANIFEST_DIR / 'amane_v0.15.0_api_manifest.json'}", "--require-equal"]
    ok = subprocess.run([*base, "--manifest", f"b={MANIFEST_DIR / 'amane_v0.18.0_api_manifest.json'}"], capture_output=True, text=True, check=False)
    assert ok.returncode == 0 and json.loads(ok.stdout)["subsets_equal"] is True
    broken = copy.deepcopy(NEW)
    broken["classes"]["WebClient"]["methods"]["request"]["params"] = [p for p in broken["classes"]["WebClient"]["methods"]["request"]["params"] if p["name"] != "timeout"]
    bad_path = tmp_path / "bad.json"
    bad_path.write_text(json.dumps(broken), encoding="utf-8")
    bad = subprocess.run([*base, "--manifest", f"b={bad_path}"], capture_output=True, text=True, check=False)
    assert bad.returncode == 1


def test_m2_07_m2_08_adapter_and_shim_never_use_single_version_host_names_or_version_branches():
    """U2-9 / I26：adapter + shim 全部文件不使用仅一个版本存在的宿主名字，也没有版本字符串 / 异常文本 / 私有模块分支。"""
    forbidden = {"max_attempts", "traits", "multi_language", "raw_results", "partial_result", "check_connectivity", "__version__", "version_info", "SourceTrait", "ConnectivityOutcome"}
    for tree_dir in (ADAPTER_TREE, REPO / "adapters" / "amane" / "shim"):
        for path in sorted(tree_dir.glob("*.py")):
            used = set()
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                if isinstance(node, ast.Name):
                    used.add(node.id)
                elif isinstance(node, ast.Attribute):
                    used.add(node.attr)
                elif isinstance(node, ast.keyword) and node.arg:
                    used.add(node.arg)
            assert not used & forbidden, (path.name, sorted(used & forbidden))
            source = path.read_text(encoding="utf-8")
            for private in ("amane._", "amane.plugins.packaging", "_session", "_limiters"):
                assert private not in source, (path.name, private)


def test_e04_the_four_tracked_new_names_are_not_imported_by_the_adapter():
    plugin = ast.parse((ADAPTER_TREE / "plugin.py").read_text(encoding="utf-8"))
    imported = {alias.name for node in ast.walk(plugin) if isinstance(node, ast.ImportFrom) and node.module == "amane.plugin" for alias in node.names}
    assert imported <= set(OLD["plugin_all"]) & set(NEW["plugin_all"])
