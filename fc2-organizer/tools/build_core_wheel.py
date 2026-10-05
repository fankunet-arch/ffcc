"""P5-C2（合同第 10.2 / 10.3 / 8.5 节）：确定性的 Core-only wheel 构建器（L0）。

只构建 ``fc2_metadata_core``（输入：``src/fc2_metadata_core/**/*.py`` + ``pyproject.toml [project]``）；
不含 ``fc2_organizer`` / 测试 / 缓存 / 非 ``.py`` 文件。产物是标准 ``py3-none-any`` wheel：
``.dist-info/{METADATA, WHEEL, RECORD, top_level.txt}`` 固定格式；``ZIP_STORED``、固定时间戳 / 权限 / 排序，
同一输入 -> 同一字节（与构建平台、Python 版本、输出目录、CRLF 检出无关）。

``core_release_ledger.json``（发布台账）：同一 Core 版本、不同 tree 哈希 -> 构建失败（改了 Core 源码就必须 bump 版本）。

用法::

    python tools/build_core_wheel.py --out <dir> [--update-ledger]
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import re
import sys
import tomllib
import zipfile
from pathlib import Path

CORE_PACKAGE = "fc2_metadata_core"
FIXED_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
FIXED_ATTRIBUTES = 0o100644 << 16
GENERATOR = "ffcc-build-core-wheel (1)"
LEDGER_RELATIVE = Path("adapters") / "amane" / "release" / "core_release_ledger.json"
LEDGER_SCHEMA_VERSION = 1


class CoreWheelError(ValueError):
    """Core 输入不满足冻结的构建规则。"""


def tree_sha256_of_entries(entries: list[tuple[str, bytes]]) -> str:
    """与 C1 ``tree_sha256`` 同一算法（按路径字节序、``path\\0sha256(content)\\n``；输入已是 LF 规范化字节）。"""
    digest = hashlib.sha256()
    for relative, data in sorted(entries, key=lambda item: item[0]):
        digest.update(relative.encode("utf-8") + b"\0" + hashlib.sha256(data).hexdigest().encode("ascii") + b"\n")
    return digest.hexdigest()


def _normalize_source(relative: str, raw: bytes) -> bytes:
    data = raw.replace(b"\r\n", b"\n")
    if data.startswith(b"\xef\xbb\xbf"):
        raise CoreWheelError(f"BOM is not allowed: {relative}")
    try:
        data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise CoreWheelError(f"not UTF-8: {relative}") from exc
    if b"\r" in data:
        raise CoreWheelError(f"stray CR is not allowed: {relative}")
    return data


def collect_core_entries(core_dir: Path) -> list[tuple[str, bytes]]:
    """``<core_dir>`` 下全部 ``*.py``（排除 ``__pycache__``），条目名为 ``fc2_metadata_core/...``；其它文件 -> 失败。"""
    if not core_dir.is_dir() or core_dir.name != CORE_PACKAGE:
        raise CoreWheelError("core source must be the fc2_metadata_core directory")
    entries: list[tuple[str, bytes]] = []
    for path in sorted(core_dir.rglob("*"), key=lambda item: item.relative_to(core_dir).as_posix()):
        relative = path.relative_to(core_dir).as_posix()
        if "__pycache__" in path.relative_to(core_dir).parts:
            continue
        if path.is_dir():
            continue
        if path.is_symlink() or path.suffix != ".py":
            raise CoreWheelError(f"only regular .py files may be packaged: {relative}")
        entries.append((f"{CORE_PACKAGE}/{relative}", _normalize_source(relative, path.read_bytes())))
    if not entries or f"{CORE_PACKAGE}/__init__.py" not in {name for name, _ in entries}:
        raise CoreWheelError("fc2_metadata_core/__init__.py is required")
    return entries


def tree_sha256_of_core(core_dir: Path) -> str:
    return tree_sha256_of_entries([(name[len(CORE_PACKAGE) + 1:], data) for name, data in collect_core_entries(core_dir)])


def read_project(pyproject: Path) -> dict[str, object]:
    project = tomllib.loads(pyproject.read_text(encoding="utf-8"))["project"]
    for key in ("name", "version", "requires-python", "description"):
        if not isinstance(project.get(key), str) or not project[key]:
            raise CoreWheelError(f"pyproject [project].{key} is required")
    return project


def _canonical_requirement(requirement: str) -> str:
    match = re.fullmatch(r"\s*([A-Za-z0-9][A-Za-z0-9._-]*)\s*([<>=!~].*)?", requirement)
    if match is None:
        raise CoreWheelError("unsupported dependency declaration")
    name, specifiers = match.group(1), match.group(2) or ""
    clauses = sorted(clause.strip().replace(" ", "") for clause in specifiers.split(",") if clause.strip())
    return name + ",".join(clauses)


def _metadata_text(project: dict[str, object]) -> str:
    lines = [
        "Metadata-Version: 2.1",
        f"Name: {project['name']}",
        f"Version: {project['version']}",
        f"Summary: {project['description']}",
        f"Requires-Python: {project['requires-python']}",
    ]
    lines += [f"Requires-Dist: {_canonical_requirement(item)}" for item in sorted(project.get("dependencies", []))]  # type: ignore[union-attr]
    return "\n".join(lines) + "\n"


def _wheel_text() -> str:
    return "\n".join(["Wheel-Version: 1.0", f"Generator: {GENERATOR}", "Root-Is-Purelib: true", "Tag: py3-none-any"]) + "\n"


def _record_hash(data: bytes) -> str:
    return "sha256=" + base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=").decode("ascii")


def wheel_filename(project: dict[str, object]) -> str:
    return f"{CORE_PACKAGE}-{project['version']}-py3-none-any.whl"


def build_wheel_bytes(core_dir: Path, pyproject: Path) -> tuple[str, bytes, str]:
    """返回 (wheel 文件名, wheel 字节, ``tree_sha256(src/fc2_metadata_core)``)。"""
    project = read_project(pyproject)
    entries = collect_core_entries(core_dir)
    tree_hash = tree_sha256_of_entries([(name[len(CORE_PACKAGE) + 1:], data) for name, data in entries])
    dist_info = f"{CORE_PACKAGE}-{project['version']}.dist-info"
    files: dict[str, bytes] = dict(entries)
    files[f"{dist_info}/METADATA"] = _metadata_text(project).encode("utf-8")
    files[f"{dist_info}/WHEEL"] = _wheel_text().encode("utf-8")
    files[f"{dist_info}/top_level.txt"] = (CORE_PACKAGE + "\n").encode("utf-8")
    record_name = f"{dist_info}/RECORD"
    record_lines = [f"{name},{_record_hash(data)},{len(data)}" for name, data in sorted(files.items(), key=lambda item: item[0].encode("utf-8"))]
    record_lines.append(f"{record_name},,")
    files[record_name] = ("\n".join(sorted(record_lines, key=lambda line: line.split(",", 1)[0].encode("utf-8"))) + "\n").encode("utf-8")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_STORED) as archive:
        for name in sorted(files, key=lambda item: item.encode("utf-8")):
            info = zipfile.ZipInfo(name, date_time=FIXED_TIMESTAMP)
            info.compress_type = zipfile.ZIP_STORED
            info.external_attr = FIXED_ATTRIBUTES
            info.create_system = 3
            archive.writestr(info, files[name], compress_type=zipfile.ZIP_STORED)
    return wheel_filename(project), buffer.getvalue(), tree_hash


def check_ledger(ledger_path: Path, version: str, tree_hash: str, wheel_hash: str, *, update: bool) -> None:
    """同一 Core 版本、不同 tree 哈希 -> 失败；台账中没有该版本 -> 失败（除非显式 ``--update-ledger``）。"""
    ledger = json.loads(ledger_path.read_text(encoding="utf-8")) if ledger_path.exists() else {"schema_version": LEDGER_SCHEMA_VERSION, "versions": {}}
    recorded = ledger["versions"].get(version)
    if recorded is None:
        if not update:
            raise CoreWheelError(f"core version {version} is not in the release ledger (use --update-ledger when releasing)")
        ledger["versions"][version] = {"core_tree_sha256": tree_hash, "wheel_sha256": wheel_hash}
        ledger_path.parent.mkdir(parents=True, exist_ok=True)
        ledger_path.write_text(json.dumps(ledger, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8", newline="\n")
        return
    if recorded["core_tree_sha256"] != tree_hash:
        raise CoreWheelError(f"core version {version} was already released with a different tree hash; bump the Core version")
    if recorded["wheel_sha256"] != wheel_hash:
        raise CoreWheelError(f"core version {version} wheel bytes differ from the release ledger")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--update-ledger", action="store_true")
    options = parser.parse_args(argv)
    root = options.repo_root.resolve()
    name, payload, tree_hash = build_wheel_bytes(root / "src" / CORE_PACKAGE, root / "pyproject.toml")
    version = str(read_project(root / "pyproject.toml")["version"])
    wheel_hash = hashlib.sha256(payload).hexdigest()
    check_ledger(root / LEDGER_RELATIVE, version, tree_hash, wheel_hash, update=options.update_ledger)
    options.out.mkdir(parents=True, exist_ok=True)
    (options.out / name).write_bytes(payload)
    print(f"{options.out / name} sha256={wheel_hash} tree_sha256={tree_hash} bytes={len(payload)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
