"""P5-C2（合同第 7.4 节 / E04）：比较 Amane 公共 API 清单，输出“适配器可控子集指纹”。

清单由 C1 的 ``tools/amane_api_manifest.py`` 生成（本工具不改它、不 import amane，只读 JSON 与 adapter 源码 AST）。
“适配器可控子集”= adapter 实际使用的 Amane 名字 / 关键字 / 字段 / 枚举成员在清单里的存在性与签名；
生产代码不得有版本字符串分支、异常文本解析、私有 monkeypatch、feature detection（U2-9）——本工具只在**见证 / 测试工具侧**记录结构事实。

用法::

    python tools/compare_amane_api.py --manifest a=<json> --manifest b=<json> [--adapter-tree <dir>] [--require-equal a,b]
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import sys
from pathlib import Path

DEFAULT_ADAPTER_TREE = Path(__file__).resolve().parents[1] / "adapters" / "amane" / "fc2_amane_adapter"
CONSTRUCTED_CLASSES = ("SourceDescriptor", "MediaMetadata", "FilmActor", "SourceError")
SUBCLASS_METHODS = (("FilmSourcePlugin", "build"), ("FilmSourceProvider", "fetch"))
QUERY_ATTRIBUTE_FILE = "_number.py"


def _tree(adapter_tree: Path, name: str) -> ast.Module:
    return ast.parse((adapter_tree / name).read_text(encoding="utf-8"), filename=name)


def _call_label(node: ast.Call) -> str | None:
    func = node.func
    return func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else None


def _call_keywords(tree: ast.Module, callee: str) -> set[str]:
    return {keyword.arg for node in ast.walk(tree) if isinstance(node, ast.Call) and _call_label(node) == callee
            for keyword in node.keywords if keyword.arg is not None}


def used_names(adapter_tree: Path) -> dict[str, object]:
    """从 adapter 源码 AST 机械提取其使用的 Amane 名字（与 C1 ``test_amane_api_manifest.py`` 的使用清单同源）。"""
    plugin = _tree(adapter_tree, "plugin.py")
    imported: set[str] = set()
    for node in ast.walk(plugin):
        if isinstance(node, ast.ImportFrom) and node.module == "amane.plugin":
            imported |= {alias.name for alias in node.names}
    query_attributes = {node.attr for node in ast.walk(_tree(adapter_tree, QUERY_ATTRIBUTE_FILE))
                        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "query"}
    enum_members: dict[str, set[str]] = {}
    for node in ast.walk(plugin):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id[:1].isupper():
            enum_members.setdefault(node.value.id, set()).add(node.attr)
    return {
        "imports": sorted(imported),
        "constructor_keywords": {name: sorted(_call_keywords(plugin, name)) for name in CONSTRUCTED_CLASSES},
        "request_keywords": sorted(_call_keywords(_tree(adapter_tree, "_bridge.py"), "request")),
        "query_attributes": sorted(query_attributes),
        "enum_members": {name: sorted(members) for name, members in sorted(enum_members.items())},
        "context_attributes": ["web_client"],
    }


def _params(entry: dict, names: set[str] | None = None) -> list[dict]:
    return [param for param in entry["params"] if names is None or param["name"] in names]


def adapter_subset(manifest: dict, used: dict[str, object]) -> dict[str, object]:
    """adapter 使用面在该清单中的存在性与签名（缺失的名字记为 ``None``，因此版本差异会改变指纹）。"""
    classes, enums = manifest["classes"], manifest["enums"]
    subset: dict[str, object] = {"plugin_all_contains": {name: name in manifest["plugin_all"] for name in used["imports"]}}  # type: ignore[union-attr]
    keywords = used["constructor_keywords"]  # type: ignore[index]
    subset["fields"] = {
        cls: {name: classes[cls]["fields"].get(name) for name in keywords[cls]} for cls in ("SourceDescriptor", "MediaMetadata", "FilmActor")  # type: ignore[index]
    }
    init = classes["SourceError"]["methods"].get("__init__")
    subset["SourceError.__init__"] = {name: next((p for p in _params(init, {name})), None) for name in keywords["SourceError"]} if init else None  # type: ignore[index]
    request = classes["WebClient"]["methods"]["request"]
    wanted = {"method", "url", *used["request_keywords"]}  # type: ignore[misc]
    subset["WebClient.request"] = {"async": request["async"], "used": {name: next((p for p in _params(request, {name})), None) for name in sorted(wanted)}}
    subset["subclass_methods"] = {f"{cls}.{method}": classes[cls]["methods"].get(method) for cls, method in SUBCLASS_METHODS}
    subset["PluginContext"] = {name: classes["PluginContext"]["fields"].get(name) for name in used["context_attributes"]}  # type: ignore[union-attr]
    subset["SearchQuery"] = {name: classes["SearchQuery"]["fields"].get(name) for name in used["query_attributes"]}  # type: ignore[union-attr]
    subset["enum_members"] = {
        name: {member: enums.get(name, {}).get("members", {}).get(member) for member in members}
        for name, members in used["enum_members"].items()  # type: ignore[union-attr]
        if name in enums
    }
    return subset


def fingerprint(value: object) -> str:
    text = json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def full_fingerprint(manifest: dict) -> str:
    """整份清单的指纹（不含 ``amane.commit`` / ``checkout_clean``，只比较 API 结构）。"""
    return fingerprint({key: value for key, value in manifest.items() if key != "amane"})


def forbidden_leaks(manifest: dict, names: set[str]) -> list[str]:
    """该清单是否仍声明仅在另一版本存在的名字（用于 E04 的逐行差异断言）。"""
    found: list[str] = []
    for cls, entry in manifest["classes"].items():
        found += [f"{cls}.{name}" for name in entry["fields"] if name in names]
        found += [f"{cls}.{name}()" for name in entry["methods"] if name in names]
    return found


def compare(manifests: dict[str, dict], adapter_tree: Path) -> dict[str, object]:
    used = used_names(adapter_tree)
    subsets = {label: adapter_subset(manifest, used) for label, manifest in manifests.items()}
    prints = {label: fingerprint(subset) for label, subset in subsets.items()}
    return {
        "used": used,
        "adapter_used_subset_fingerprints": prints,
        "api_fingerprints": {label: full_fingerprint(manifest) for label, manifest in manifests.items()},
        "subsets_equal": len(set(prints.values())) == 1,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", action="append", required=True, metavar="LABEL=PATH")
    parser.add_argument("--adapter-tree", type=Path, default=DEFAULT_ADAPTER_TREE)
    parser.add_argument("--require-equal", action="store_true", help="adapter 可控子集指纹不相等 -> 退出码 1")
    options = parser.parse_args(argv)
    manifests = {}
    for item in options.manifest:
        label, _, path = item.partition("=")
        manifests[label] = json.loads(Path(path).read_text(encoding="utf-8"))
    report = compare(manifests, options.adapter_tree)
    print(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=True))
    return 1 if options.require_equal and not report["subsets_equal"] else 0


if __name__ == "__main__":
    sys.exit(main())
