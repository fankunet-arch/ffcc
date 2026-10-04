"""P5-C1：真实 Amane v0.15.0 宿主见证运行器（脚本，不是 pytest 测试）。

必须在 **Python >= 3.14** 且已安装 Amane v0.15.0 的解释器中运行；每个场景（H-01..H-15）在独立子进程中执行
``tests/amane_adapter/host_scripts/h_scenarios.py``；传输层是脚本化的 ``WebClient._session``（无真实网络；
唯一的网络活动是 H-09 的 127.0.0.1 回环服务器）。输出 JSON 不含时间戳 / 耗时 / 端口 / 临时路径，保证同一环境可复现::

    <py314> tools/run_amane_host_witness.py --amane-src <amane-checkout> --core-src src \
        --adapter-tree adapters/amane/fc2_amane_adapter --out docs/acceptance/evidence/P5_C1_HOST_WITNESS.json

本模块顶层只依赖标准库（主进程测试 ``test_amane_host_witness_log.py`` 会导入它来重算树哈希，且从不 import amane）。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

SCHEMA_VERSION = 1
SCENARIO_IDS = tuple(f"H-{index:02d}" for index in range(1, 16))
MARKER = "@@WITNESS@@"
SCENARIO_TIMEOUT_SECONDS = 900


def tree_sha256(root: Path) -> str:
    """``root`` 下全部 ``*.py``（排除 ``__pycache__``）的内容哈希；``\\r\\n`` 规范化为 ``\\n``（与 autocrlf 无关）。"""
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*.py"), key=lambda item: item.relative_to(root).as_posix()):
        if "__pycache__" in path.parts:
            continue
        data = path.read_bytes().replace(b"\r\n", b"\n")
        digest.update(path.relative_to(root).as_posix().encode("utf-8") + b"\0" + hashlib.sha256(data).hexdigest().encode("ascii") + b"\n")
    return digest.hexdigest()


def render(report: dict) -> str:
    return json.dumps(report, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def run_scenario(scenario: str, *, repo_root: Path, amane_src: Path, core_src: Path, adapter_tree: Path) -> dict:
    script = repo_root / "tests" / "amane_adapter" / "host_scripts" / "h_scenarios.py"
    with tempfile.TemporaryDirectory(prefix=f"p5c1_{scenario}_") as work:
        completed = subprocess.run(
            [sys.executable, str(script), "--scenario", scenario, "--repo-root", str(repo_root), "--amane-src", str(amane_src),
             "--core-src", str(core_src), "--adapter-tree", str(adapter_tree), "--work-dir", work],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=SCENARIO_TIMEOUT_SECONDS,
        )
    for line in completed.stdout.splitlines():
        if line.startswith(MARKER):
            return json.loads(line[len(MARKER):])
    return {"id": scenario, "passed": False, "observations": {},
            "failure": f"no result line (exit {completed.returncode}): {completed.stderr[-600:]}"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--amane-src", required=True, type=Path)
    parser.add_argument("--core-src", required=True, type=Path)
    parser.add_argument("--adapter-tree", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    options = parser.parse_args(argv)
    repo_root = options.repo_root.resolve()
    amane_src, core_src, adapter_tree = (path.resolve() for path in (options.amane_src, options.core_src, options.adapter_tree))
    scenarios = []
    for scenario in SCENARIO_IDS:
        result = run_scenario(scenario, repo_root=repo_root, amane_src=amane_src, core_src=core_src, adapter_tree=adapter_tree)
        scenarios.append(result)
        print(f"{scenario}: {'PASS' if result['passed'] else 'FAIL'}", file=sys.stderr)
        if not result["passed"]:
            print(result.get("failure", ""), file=sys.stderr)
    first = next((item for item in scenarios if item["id"] == "H-01" and item["passed"]), None)
    environment = (first or {}).get("observations", {})
    report = {
        "schema_version": SCHEMA_VERSION,
        "python": ".".join(str(part) for part in sys.version_info[:3]),
        "amane": {"version": environment.get("amane_version"), "commit": environment.get("amane_commit")},
        "adapter_tree_sha256": tree_sha256(adapter_tree),
        "core_tree_sha256": tree_sha256(core_src / "fc2_metadata_core"),
        "scenarios": sorted(scenarios, key=lambda item: item["id"]),
    }
    options.out.parent.mkdir(parents=True, exist_ok=True)
    options.out.write_text(render(report), encoding="utf-8", newline="\n")
    passed = sum(1 for item in scenarios if item["passed"])
    print(f"{passed}/{len(scenarios)} scenarios passed; sha256(out)={hashlib.sha256(render(report).encode()).hexdigest()}", file=sys.stderr)
    return 0 if passed == len(scenarios) else 1


if __name__ == "__main__":
    sys.exit(main())
