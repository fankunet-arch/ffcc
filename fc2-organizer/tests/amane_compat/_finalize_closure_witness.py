"""P5-C2-L1-01：真实 forced phase abort 与发布入口的端到端闭环见证。

通过临时函数替换注入异常；生产文件与宿主代码均不修改。可在 clean checkout 重现。
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from _compat_support import REPO, load_tool


def verify_abort_outputs(gate, wheel, stage1_dir, part_a, details, out):
    matrix = json.loads(part_a.read_text(encoding="utf-8"))
    host = next(host for host in matrix["hosts"] if host["label"] == "a-win")
    assert next(row for row in host["scenarios"] if row["id"] == "HC-08")["passed"] is False
    diagnostic = json.loads(details.read_text(encoding="utf-8"))
    assert diagnostic["scenarios"]["a-win"]["HC-08"]["failures"] == []
    assert diagnostic["scenarios"]["a-win"]["HC-08"]["completed"] is False
    assert "forced phase abort" in diagnostic["extras"]["a-win"]["phase_errors"]["own_stack"]
    assert next(row for row in matrix["status"] if row["coordinate_id"] == "SC-01")["status"] == "BLOCKED"
    assert gate.validate_matrix(matrix)
    validation = subprocess.run([sys.executable, str(REPO / "tools/run_amane_compat_gate.py"), "--validate", str(part_a)],
                                capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
    assert validation.returncode != 0
    results = {"validate_matrix": {"exit": validation.returncode, "stderr": validation.stderr, "stdout": validation.stdout}}
    for name, script in (("gate", "run_amane_compat_gate.py"), ("direct", "build_amane_release.py")):
        destination = out / name
        result = subprocess.run([sys.executable, str(REPO / "tools" / script), "finalize", "--core-wheel", str(wheel),
                                 "--stage1-dir", str(stage1_dir), "--matrix", str(part_a), "--out", str(destination)],
                                capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
        assert result.returncode != 0, result.stdout + result.stderr
        assert "finalize refused:" in result.stderr if name == "gate" else "ReleaseError: finalize:" in result.stderr
        assert not destination.exists(), f"{name} emitted final artifacts"
        results[name] = {"exit": result.returncode, "stderr": result.stderr}
    out.mkdir(parents=True, exist_ok=True)
    (out / "rejection_results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    print("Gate NON-ZERO; Matrix NON-GREEN; validate_matrix REJECT; Gate Finalize REJECT; Direct Builder Finalize REJECT; L2/L3/L4 NONE")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hosts-json", required=True, type=Path)
    parser.add_argument("--core-wheel", required=True, type=Path)
    parser.add_argument("--stage1-dir", required=True, type=Path)
    parser.add_argument("--work", required=True, type=Path)
    options = parser.parse_args()
    gate = load_tool("run_amane_compat_gate.py")
    original = gate.phase_own_stack
    def forced_abort(run, host):
        if run.spec.label == "a-win":
            assert run.results["HC-08"].failures == []
            raise RuntimeError("P5-C2-L1-01 forced phase abort before controlled stack completes")
        return original(run, host)
    gate.phase_own_stack = forced_abort
    part_a, details = options.work / "partA.json", options.work / "details.json"
    try:
        code = gate.main(["run", "--hosts-json", str(options.hosts_json), "--core-wheel", str(options.core_wheel),
                          "--stage1-dir", str(options.stage1_dir), "--work", str(options.work / "host"),
                          "--out", str(part_a), "--details", str(details)])
    finally:
        gate.phase_own_stack = original
    assert code != 0
    matrix = json.loads(part_a.read_text(encoding="utf-8"))
    required = [host for host in matrix["hosts"] if host["role"] == "required"]
    assert {host["coordinate_id"] for host in required} == {"SC-01", "SC-02", "SC-03", "SC-04"}
    assert all(len(host["scenarios"]) == 19 and all(row["passed"] is True for row in host["scenarios"])
               for host in required if host["label"] != "a-win")
    verify_abort_outputs(gate, options.core_wheel, options.stage1_dir, part_a, details, options.work / "rejected")


if __name__ == "__main__":
    main()
