"""P5-C2（合同第 9、10 节）：最终分发物构建器（确定性；严格无环的派生 DAG，第 10.5 节）。

两个子命令（冻结顺序，不得调整）::

    python tools/build_amane_release.py stage1   --core-wheel <whl> --out <dir>
        L1：plugin zip（含由 L0 wheel 哈希生成的 ``_ffcc_pin.py``）、``INSTALL.zh-CN.md``、``VERSION``。
    python tools/build_amane_release.py finalize --core-wheel <whl> --stage1-dir <dir> --matrix <json> --out <dir>
        L2：``COMPATIBILITY.json``（只读 MATRIX Part A 的字段白名单投影）-> L3：``SHA256SUMS`` -> L4：release bundle。

``_impl/`` = P5-C1 树的 **LF 规范化字节**（normalized-byte identity；不是磁盘原始字节逐位相同）。
本构建器**不** import C1 构建器 / adapter；不写 ``--out`` 之外的任何位置。
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import io
import json
import re
import sys
import tomllib
import zipfile
from pathlib import Path

PLUGIN_ID = "ffcc.fc2-metadata"
CORE_PACKAGE = "fc2_metadata_core"
DIST_NAME = "fc2-metadata-core"
SIDECAR_DIRNAME = "_ffcc_core"
PIN_SCHEMA_VERSION = 1
FIXED_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
FIXED_ATTRIBUTES = 0o100644 << 16
MAX_PLUGIN_ZIP_BYTES = 20 * 1024 * 1024
IMPL_FILES = ("_bridge.py", "_core_gate.py", "_number.py", "_outcome.py", "_runtime.py", "_settings.py", "plugin.py")
SHIM_FILES = ("plugin.py", "_ffcc_locator.py")
WITNESS_RELATIVE = Path("docs") / "acceptance" / "evidence" / "P5_C1_HOST_WITNESS.json"
INSTALL_RELATIVE = Path("adapters") / "amane" / "release" / "INSTALL.zh-CN.md"
KNOWN_LIMITATIONS = tuple(f"L-C2-{index:02d}" for index in range(1, 14))
FORBIDDEN_NAME_PARTS = ("__pycache__", ".pyc", ".pyd", ".so", ".pth", ".env", "tests/", ".venv", "venv/")
_ABSOLUTE_PATH = re.compile(r"(?<![A-Za-z0-9])[A-Za-z]:\\|/(?:Users|home)/[A-Za-z0-9_.-]+")


class ReleaseError(ValueError):
    """输入或产物不满足冻结的发布规则。"""


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def lf(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n")


def tree_sha256(entries: list[tuple[str, bytes]]) -> str:
    """与 C1 ``tree_sha256`` 同一算法；输入为 (相对路径, LF 规范化字节)。"""
    digest = hashlib.sha256()
    for relative, data in sorted(entries, key=lambda item: item[0]):
        digest.update(relative.encode("utf-8") + b"\0" + sha256_hex(data).encode("ascii") + b"\n")
    return digest.hexdigest()


def read_plugin_constants(settings_path: Path) -> tuple[str, str]:
    """以 AST 读取 ``PLUGIN_ID`` / ``PLUGIN_VERSION``（不 import adapter）。"""
    found: dict[str, str] = {}
    for node in ast.parse(settings_path.read_text(encoding="utf-8")).body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            if node.targets[0].id in ("PLUGIN_ID", "PLUGIN_VERSION"):
                found[node.targets[0].id] = ast.literal_eval(node.value)
    if set(found) != {"PLUGIN_ID", "PLUGIN_VERSION"}:
        raise ReleaseError("PLUGIN_ID / PLUGIN_VERSION not found in _settings.py")
    if found["PLUGIN_ID"] != PLUGIN_ID:
        raise ReleaseError("PLUGIN_ID must be exactly ffcc.fc2-metadata")
    return found["PLUGIN_ID"], found["PLUGIN_VERSION"]


def _checked_text(relative: str, raw: bytes) -> bytes:
    data = lf(raw)
    if data.startswith(b"\xef\xbb\xbf") or b"\r" in data:
        raise ReleaseError(f"BOM / CR is not allowed: {relative}")
    try:
        data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ReleaseError(f"not UTF-8: {relative}") from exc
    return data


def collect_impl_entries(adapter_tree: Path) -> list[tuple[str, bytes]]:
    names = sorted(path.name for path in adapter_tree.iterdir() if path.name != "__pycache__")
    if names != sorted(IMPL_FILES):
        raise ReleaseError(f"adapter tree must contain exactly {sorted(IMPL_FILES)}, found {names}")
    return [(name, _checked_text(name, (adapter_tree / name).read_bytes())) for name in sorted(IMPL_FILES)]


def collect_shim_entries(shim_dir: Path) -> list[tuple[str, bytes]]:
    return [(name, _checked_text(name, (shim_dir / name).read_bytes())) for name in SHIM_FILES]


def render_pin(*, core_version: str, wheel_name: str, wheel_sha256: str, core_tree_sha256: str) -> bytes:
    """``_ffcc_pin.py``：只含字面量。"""
    lines = [
        "# 构建期生成（tools/build_amane_release.py）；只含字面量。",
        f"PIN_SCHEMA_VERSION = {PIN_SCHEMA_VERSION}",
        f'CORE_DIST_NAME = "{DIST_NAME}"',
        f'CORE_VERSION = "{core_version}"',
        f'CORE_WHEEL_NAME = "{wheel_name}"',
        f'CORE_WHEEL_SHA256 = "{wheel_sha256}"',
        f'CORE_TREE_SHA256 = "{core_tree_sha256}"',
        f'SIDECAR_DIRNAME = "{SIDECAR_DIRNAME}"',
    ]
    return ("\n".join(lines) + "\n").encode("utf-8")


def inspect_core_wheel(wheel: bytes, wheel_name: str, core_version: str) -> tuple[str, list[tuple[str, bytes]]]:
    """校验 L0 wheel 只含 ``fc2_metadata_core/*.py`` + 4 个 dist-info 文件；返回 (成员的 ``tree_sha256``, 成员列表)。"""
    if wheel_name != f"{CORE_PACKAGE}-{core_version}-py3-none-any.whl":
        raise ReleaseError("unexpected Core wheel file name")
    dist_info = f"{CORE_PACKAGE}-{core_version}.dist-info/"
    members: list[tuple[str, bytes]] = []
    seen: set[str] = set()
    with zipfile.ZipFile(io.BytesIO(wheel)) as archive:
        for info in archive.infolist():
            name = info.filename
            if name.startswith(dist_info):
                seen.add(name[len(dist_info):])
            elif name.startswith(CORE_PACKAGE + "/") and name.endswith(".py") and "__pycache__" not in name:
                members.append((name[len(CORE_PACKAGE) + 1:], archive.read(name)))
            else:
                raise ReleaseError(f"unexpected Core wheel member: {name}")
    if seen != {"METADATA", "WHEEL", "RECORD", "top_level.txt"}:
        raise ReleaseError("Core wheel dist-info must be exactly METADATA, WHEEL, RECORD, top_level.txt")
    return tree_sha256(members), members


def _scan_artifact_members(members: dict[str, bytes], core_members: list[tuple[str, bytes]]) -> None:
    """allow-list / forbidden 扫描与 E18 的整文件包含扫描（不 vendor）。"""
    for name, data in members.items():
        if any(part in name for part in FORBIDDEN_NAME_PARTS):
            raise ReleaseError(f"forbidden member: {name}")
        if _ABSOLUTE_PATH.search(data.decode("utf-8")):
            raise ReleaseError(f"absolute path string in: {name}")
        for core_name, core_data in core_members:
            if len(core_data) > 64 and core_data in data:
                raise ReleaseError(f"Core source {core_name} is embedded in {name}")


def deterministic_zip(members: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_STORED) as archive:
        for name in sorted(members, key=lambda item: item.encode("utf-8")):
            info = zipfile.ZipInfo(name, date_time=FIXED_TIMESTAMP)
            info.compress_type = zipfile.ZIP_STORED
            info.external_attr = FIXED_ATTRIBUTES
            info.create_system = 3
            archive.writestr(info, members[name], compress_type=zipfile.ZIP_STORED)
    return buffer.getvalue()


def build_stage1(repo_root: Path, wheel_path: Path, *, check_witness: bool = True) -> dict[str, object]:
    """L1：返回 ``{files: {名: 字节}, artifacts: {...}, plugin_version, core_version}``（不写盘）。"""
    adapter_tree = repo_root / "adapters" / "amane" / "fc2_amane_adapter"
    plugin_id, plugin_version = read_plugin_constants(adapter_tree / "_settings.py")
    project = tomllib.loads((repo_root / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    core_version = str(project["version"])
    wheel = wheel_path.read_bytes()
    core_tree, core_members = inspect_core_wheel(wheel, wheel_path.name, core_version)
    impl = collect_impl_entries(adapter_tree)
    impl_tree = tree_sha256(impl)
    if check_witness:
        witness = json.loads((repo_root / WITNESS_RELATIVE).read_text(encoding="utf-8"))
        if impl_tree != witness["adapter_tree_sha256"]:
            raise ReleaseError("_impl tree hash differs from P5-C1 adapter_tree_sha256 (U2-6)")
        if core_tree != witness["core_tree_sha256"]:
            raise ReleaseError("Core wheel tree hash differs from P5-C1 core_tree_sha256")
    pin = render_pin(core_version=core_version, wheel_name=wheel_path.name, wheel_sha256=sha256_hex(wheel), core_tree_sha256=core_tree)
    shim = dict(collect_shim_entries(repo_root / "adapters" / "amane" / "shim"))
    shim_entries = [("plugin.py", shim["plugin.py"]), ("_ffcc_locator.py", shim["_ffcc_locator.py"]), ("_ffcc_pin.py", pin)]
    members: dict[str, bytes] = {f"{plugin_id}/{name}": data for name, data in shim_entries}
    members.update({f"{plugin_id}/_impl/{name}": data for name, data in impl})
    _scan_artifact_members(members, core_members)
    zip_bytes = deterministic_zip(members)
    if len(zip_bytes) > MAX_PLUGIN_ZIP_BYTES:
        raise ReleaseError("plugin zip exceeds the Amane size limit")
    install = _checked_text("INSTALL.zh-CN.md", (repo_root / INSTALL_RELATIVE).read_bytes())
    version_text = f"bundle {plugin_version}+core{core_version}\n".encode("utf-8")
    zip_name = f"{plugin_id}-{plugin_version}.zip"
    return {
        "plugin_version": plugin_version,
        "core_version": core_version,
        "files": {zip_name: zip_bytes, "INSTALL.zh-CN.md": install, "VERSION": version_text},
        "artifacts": {
            "plugin_zip_sha256": sha256_hex(zip_bytes),
            "core_wheel_sha256": sha256_hex(wheel),
            "core_tree_sha256": core_tree,
            "adapter_tree_sha256": tree_sha256(impl),
            "impl_tree_sha256": impl_tree,
            "shim_tree_sha256": tree_sha256(shim_entries),
            "pin_sha256": sha256_hex(pin),
        },
    }


_PART_A_HOST_FIELDS = (
    "label", "coordinate_id", "role", "form", "tag", "tag_object", "peeled_commit", "release_version",
    "requires_python", "plugin_api_version", "platform", "identical_to_stable",
)


def project_part_a(matrix: dict) -> dict:
    """L2 的投影：**只读** Part A 的字段白名单（绝不读取 ``final_artifacts`` 等 Part B 字段）。"""
    hosts = []
    for host in matrix["hosts"]:
        item = {key: host[key] for key in _PART_A_HOST_FIELDS if key in host}
        item["scenarios"] = [{"id": scenario["id"], "passed": scenario["passed"]} for scenario in host["scenarios"]]
        hosts.append(item)
    return {
        "schema_version": matrix["schema_version"],
        "policy": matrix["policy"],
        "hosts": hosts,
        "artifacts": matrix["artifacts"],
        "status": matrix["status"],
        "platforms_unverified": matrix["platforms_unverified"],
        "core_admission": {
            "core_wheel_sha256": matrix["core_admission"]["core_wheel_sha256"],
            "cases": [{key: case[key] for key in ("id", "mode", "python", "expected", "observed", "template")} for case in matrix["core_admission"]["cases"]],
        },
        "parity": {"all_required_pairs_equal": all(pair["equal"] for pair in matrix["parity"]["required_pairs"]),
                   "allowed_diffs_observed": matrix["parity"]["allowed_diffs_observed"]},
    }


def render_compatibility_json(matrix: dict, stage1: dict[str, object]) -> bytes:
    projection = project_part_a(matrix)
    document = {
        "kind": "ffcc-amane-compatibility",
        "bundle_version": f"{stage1['plugin_version']}+core{stage1['core_version']}",
        "support_claim": "support claim is coordinate-scoped, not version-global; verified coordinates are SC-01..SC-04 only",
        "known_limitations": list(KNOWN_LIMITATIONS),
        "matrix_part_a": projection,
    }
    return (json.dumps(document, indent=2, sort_keys=True, ensure_ascii=True) + "\n").encode("utf-8")


def render_sha256sums(members: dict[str, bytes]) -> bytes:
    """5 个成员；按文件名排序；LF；``<sha256>␣␣<name>``；不含自身。"""
    if "SHA256SUMS" in members:
        raise ReleaseError("SHA256SUMS must not list itself")
    return "".join(f"{sha256_hex(data)}  {name}\n" for name, data in sorted(members.items())).encode("utf-8")


def build_finalize(stage1: dict[str, object], wheel_name: str, wheel: bytes, matrix: dict) -> dict[str, bytes]:
    """L2 -> L3 -> L4；返回 ``{COMPATIBILITY.json, SHA256SUMS, <bundle 名>}``。"""
    files: dict[str, bytes] = dict(stage1["files"])  # type: ignore[arg-type]
    files[wheel_name] = wheel
    files["COMPATIBILITY.json"] = render_compatibility_json(matrix, stage1)
    sums = render_sha256sums(files)
    bundle_members = dict(files)
    bundle_members["SHA256SUMS"] = sums
    if len(bundle_members) != 6:
        raise ReleaseError("bundle must have exactly 6 members")
    bundle_name = f"ffcc-amane-release-{stage1['plugin_version']}.zip"
    return {"COMPATIBILITY.json": files["COMPATIBILITY.json"], "SHA256SUMS": sums, bundle_name: deterministic_zip(bundle_members)}


def _write(out: Path, files: dict[str, bytes]) -> None:
    out.mkdir(parents=True, exist_ok=True)
    for name, data in files.items():
        (out / name).write_bytes(data)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    sub = parser.add_subparsers(dest="command", required=True)
    one = sub.add_parser("stage1")
    one.add_argument("--core-wheel", required=True, type=Path)
    one.add_argument("--out", required=True, type=Path)
    two = sub.add_parser("finalize")
    two.add_argument("--core-wheel", required=True, type=Path)
    two.add_argument("--stage1-dir", required=True, type=Path)
    two.add_argument("--matrix", required=True, type=Path)
    two.add_argument("--out", required=True, type=Path)
    options = parser.parse_args(argv)
    root = options.repo_root.resolve()
    stage1 = build_stage1(root, options.core_wheel)
    if options.command == "stage1":
        _write(options.out, stage1["files"])  # type: ignore[arg-type]
        for key, value in stage1["artifacts"].items():  # type: ignore[union-attr]
            print(f"{key}={value}")
        return 0
    for name, data in stage1["files"].items():  # type: ignore[union-attr]
        existing = (options.stage1_dir / name).read_bytes()
        if existing != data:
            raise ReleaseError(f"stage1 artifact differs from a fresh rebuild: {name}")
    matrix = json.loads(options.matrix.read_text(encoding="utf-8"))
    produced = build_finalize(stage1, options.core_wheel.name, options.core_wheel.read_bytes(), matrix)
    _write(options.out, produced)
    for name, data in produced.items():
        print(f"{name} sha256={sha256_hex(data)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
