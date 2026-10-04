"""P5-C1：从一个 Amane 检出做 AST 提取，输出确定性的公共 API 清单（JSON）。

不 import amane；只读源码。用法::

    python tools/amane_api_manifest.py --amane-src <amane-checkout> [--out <file>] [--expect-commit <sha>]

清单记录合同表 A 涉及的类 / 字段 / 枚举成员 / 方法签名 / 常量、``amane.plugin.__all__`` 与检出的 commit SHA。
``tests/amane_adapter/test_amane_api_manifest.py`` 以已提交的清单核对 adapter 对 Amane 名字与关键字的使用。
"""

from __future__ import annotations

import argparse
import ast
import json
import subprocess
import sys
from pathlib import Path

SCHEMA_VERSION = 1

#: (名字, 相对 Amane 仓库根的文件)；``class`` 条目提取字段与方法，``enum`` 条目提取成员。
CLASSES = (
    ("FilmSourcePlugin", "src/amane/plugins/api.py"),
    ("FilmSourceProvider", "src/amane/plugins/api.py"),
    ("PluginContext", "src/amane/plugins/api.py"),
    ("SearchQuery", "src/amane/crawlers/models.py"),
    ("FetchOptions", "src/amane/crawlers/models.py"),
    ("MediaMetadata", "src/amane/crawlers/models.py"),
    ("FilmActor", "src/amane/crawlers/models.py"),
    ("SourceDescriptor", "src/amane/plugins/models.py"),
    ("SourceError", "src/amane/net/errors.py"),
    ("RequestError", "src/amane/net/errors.py"),
    ("WebClient", "src/amane/net/http.py"),
    ("HttpClient", "src/amane/crawlers/http.py"),
)
ENUMS = (
    ("ContentType", "src/amane/parsing/file_info.py"),
    ("SourceCapability", "src/amane/plugins/models.py"),
    ("FailureReason", "src/amane/net/errors.py"),
    ("ActorGender", "src/amane/enums.py"),
)
CONSTANTS = (("PLUGIN_API_VERSION", "src/amane/plugins/models.py"),)
PLUGIN_INIT = "src/amane/plugin/__init__.py"


def _parse(root: Path, relative: str) -> ast.Module:
    return ast.parse((root / relative).read_text(encoding="utf-8"), filename=relative)


def _find_class(tree: ast.Module, name: str) -> ast.ClassDef:
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == name:
            return node
    raise LookupError(f"class {name} not found")


def _params(args: ast.arguments) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    positional = [*args.posonlyargs, *args.args]
    defaults = [None] * (len(positional) - len(args.defaults)) + list(args.defaults)
    for index, (arg, default) in enumerate(zip(positional, defaults)):
        kind = "positional_only" if index < len(args.posonlyargs) else "positional_or_keyword"
        result.append({"name": arg.arg, "kind": kind, "default": None if default is None else ast.unparse(default)})
    if args.vararg is not None:
        result.append({"name": args.vararg.arg, "kind": "var_positional", "default": None})
    for arg, default in zip(args.kwonlyargs, args.kw_defaults):
        result.append({"name": arg.arg, "kind": "keyword_only", "default": None if default is None else ast.unparse(default)})
    if args.kwarg is not None:
        result.append({"name": args.kwarg.arg, "kind": "var_keyword", "default": None})
    return result


def _class_entry(node: ast.ClassDef, relative: str) -> dict[str, object]:
    fields: dict[str, dict[str, object]] = {}
    methods: dict[str, dict[str, object]] = {}
    for item in node.body:
        if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
            fields[item.target.id] = {
                "annotation": ast.unparse(item.annotation),
                "default": None if item.value is None else ast.unparse(item.value),
            }
        elif isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
            methods[item.name] = {
                "async": isinstance(item, ast.AsyncFunctionDef),
                "decorators": [ast.unparse(decorator) for decorator in item.decorator_list],
                "params": _params(item.args),
                "returns": None if item.returns is None else ast.unparse(item.returns),
            }
    return {
        "file": relative,
        "bases": [ast.unparse(base) for base in node.bases],
        "fields": fields,
        "methods": methods,
    }


def _enum_entry(node: ast.ClassDef, relative: str) -> dict[str, object]:
    members: dict[str, object] = {}
    for item in node.body:
        if isinstance(item, ast.Assign) and len(item.targets) == 1 and isinstance(item.targets[0], ast.Name):
            try:
                members[item.targets[0].id] = ast.literal_eval(item.value)
            except ValueError:
                members[item.targets[0].id] = ast.unparse(item.value)
    return {"file": relative, "bases": [ast.unparse(base) for base in node.bases], "members": members}


def _constant(tree: ast.Module, name: str) -> object:
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
            return ast.literal_eval(node.value)
    raise LookupError(f"constant {name} not found")


def _plugin_all(root: Path) -> list[str]:
    tree = _parse(root, PLUGIN_INIT)
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "__all__" for t in node.targets):
            return sorted(ast.literal_eval(node.value))
    raise LookupError("amane.plugin.__all__ not found")


def _git(root: Path, *args: str) -> str:
    completed = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, check=True)
    return completed.stdout.strip()


def _project_version(root: Path) -> str:
    for line in (root / "pyproject.toml").read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("version") and "=" in stripped:
            return stripped.split("=", 1)[1].strip().strip('"')
    raise LookupError("project version not found")


def build_manifest(root: Path) -> dict[str, object]:
    trees: dict[str, ast.Module] = {}

    def tree_for(relative: str) -> ast.Module:
        if relative not in trees:
            trees[relative] = _parse(root, relative)
        return trees[relative]

    return {
        "schema_version": SCHEMA_VERSION,
        "amane": {
            "version": _project_version(root),
            "commit": _git(root, "rev-parse", "HEAD"),
            "checkout_clean": _git(root, "status", "--porcelain") == "",
        },
        "plugin_all": _plugin_all(root),
        "classes": {name: _class_entry(_find_class(tree_for(rel), name), rel) for name, rel in CLASSES},
        "enums": {name: _enum_entry(_find_class(tree_for(rel), name), rel) for name, rel in ENUMS},
        "constants": {name: _constant(tree_for(rel), name) for name, rel in CONSTANTS},
    }


def render(manifest: dict[str, object]) -> str:
    return json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--amane-src", required=True, type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--expect-commit")
    options = parser.parse_args(argv)
    manifest = build_manifest(options.amane_src)
    commit = manifest["amane"]["commit"]  # type: ignore[index]
    if options.expect_commit and commit != options.expect_commit:
        print(f"commit mismatch: {commit} != {options.expect_commit}", file=sys.stderr)
        return 2
    text = render(manifest)
    if options.out:
        options.out.parent.mkdir(parents=True, exist_ok=True)
        options.out.write_text(text, encoding="utf-8", newline="\n")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
