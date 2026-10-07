"""P5-C2-L1-01 R1：直接发布构建器的行为拒绝与完整中断闭环。"""
from __future__ import annotations

import copy
import json
import subprocess
import sys

import pytest

from _compat_support import REPO, load_tool, synthetic_matrix
from _finalize_closure_witness import verify_abort_outputs


@pytest.fixture
def inputs(core_wheel, tmp_path):
    release = load_tool("build_amane_release.py")
    stage1 = release.build_stage1(REPO, core_wheel)
    directory = tmp_path / "l1"
    directory.mkdir()
    for name, data in stage1["files"].items():
        (directory / name).write_bytes(data)
    return release, stage1, directory, synthetic_matrix(stage1["artifacts"])


CASES = [
    "scenario_false", "scenario_missing", "passed_missing", "passed_integer", "passed_string",
    "scenarios_empty", "scenario_duplicate", "host_missing", "hosts_empty", "host_duplicate",
    "host_identity", "status_blocked", "status_unverified", "status_missing", "status_duplicate",
    "parity_false", "parity_missing", "parity_empty", "pair_missing", "equal_missing", "equal_integer",
    "core_mismatch", "plugin_mismatch", "core_hash_missing", "plugin_hash_missing",
]


def corrupt(matrix, case):
    host = matrix["hosts"][0]
    scenario = host["scenarios"][15]  # HC-16
    status = matrix["status"][0]
    pairs = matrix["parity"]["required_pairs"]
    if case == "scenario_false":
        scenario["passed"] = False
    elif case == "scenario_missing":
        host["scenarios"].pop(15)
    elif case == "passed_missing":
        scenario.pop("passed")
    elif case == "passed_integer":
        scenario["passed"] = 1
    elif case == "passed_string":
        scenario["passed"] = "true"
    elif case == "scenarios_empty":
        host["scenarios"] = []
    elif case == "scenario_duplicate":
        host["scenarios"][15] = copy.deepcopy(host["scenarios"][0])
    elif case == "host_missing":
        matrix["hosts"].pop(0)
    elif case == "hosts_empty":
        matrix["hosts"] = []
    elif case == "host_duplicate":
        matrix["hosts"].append(copy.deepcopy(host))
    elif case == "host_identity":
        host["form"] = "source"
    elif case == "status_blocked":
        status["status"] = "BLOCKED"
    elif case == "status_unverified":
        status["status"] = "UNVERIFIED"
    elif case == "status_missing":
        matrix["status"].pop(0)
    elif case == "status_duplicate":
        matrix["status"].append(copy.deepcopy(status))
    elif case == "parity_false":
        pairs[0]["equal"] = False
    elif case == "parity_missing":
        matrix.pop("parity")
    elif case == "parity_empty":
        matrix["parity"]["required_pairs"] = []
    elif case == "pair_missing":
        pairs.pop()
    elif case == "equal_missing":
        pairs[0].pop("equal")
    elif case == "equal_integer":
        pairs[0]["equal"] = 1
    elif case == "core_mismatch":
        matrix["artifacts"]["core_wheel_sha256"] = "00" * 32
    elif case == "plugin_mismatch":
        matrix["artifacts"]["plugin_zip_sha256"] = "00" * 32
    elif case == "core_hash_missing":
        matrix["artifacts"].pop("core_wheel_sha256")
    elif case == "plugin_hash_missing":
        matrix["artifacts"].pop("plugin_zip_sha256")
    else:
        raise AssertionError(case)


@pytest.mark.parametrize("case", CASES)
def test_direct_finalize_cli_rejects_invalid_evidence_before_writing_any_artifact(inputs, core_wheel, tmp_path, case):
    _release, _stage1, directory, matrix = inputs
    corrupt(matrix, case)
    part_a = tmp_path / "partA.json"
    part_a.write_text(json.dumps(matrix), encoding="utf-8")
    out = tmp_path / "final"
    result = subprocess.run(
        [sys.executable, str(REPO / "tools/build_amane_release.py"), "finalize", "--core-wheel", str(core_wheel),
         "--stage1-dir", str(directory), "--matrix", str(part_a), "--out", str(out)],
        capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
    )
    assert result.returncode != 0 and "ReleaseError: finalize:" in result.stderr
    assert not out.exists(), "invalid evidence must not emit L2 / L3 / L4"


@pytest.mark.parametrize("index", range(4), ids=["SC-01", "SC-02", "SC-03", "SC-04"])
def test_every_required_host_is_checked_by_the_production_builder(inputs, core_wheel, index):
    release, stage1, _directory, matrix = inputs
    matrix["hosts"][index]["scenarios"][15]["passed"] = False
    with pytest.raises(release.ReleaseError, match="not PASS"):
        release.build_finalize(stage1, core_wheel.name, core_wheel.read_bytes(), matrix)


@pytest.mark.parametrize("level", ["L0", "L1"])
def test_artifact_identity_uses_actual_bytes_even_if_stage1_metadata_claims_the_old_hash(inputs, core_wheel, level):
    release, stage1, _directory, matrix = inputs
    wheel = core_wheel.read_bytes()
    if level == "L0":
        wheel += b"different bytes"
    else:
        stage1["files"]["ffcc.fc2-metadata-0.1.0.zip"] += b"different bytes"
    with pytest.raises(release.ReleaseError, match="actual input bytes"):
        release.build_finalize(stage1, core_wheel.name, wheel, matrix)


def test_valid_direct_finalize_retains_all_frozen_l0_to_l4_hashes(inputs, core_wheel):
    release, stage1, _directory, _matrix = inputs
    matrix = json.loads((REPO / "docs/acceptance/evidence/P5_C2_COMPATIBILITY_MATRIX.json").read_text(encoding="utf-8"))
    produced = release.build_finalize(stage1, core_wheel.name, core_wheel.read_bytes(), matrix)
    assert release.sha256_hex(core_wheel.read_bytes()) == "0b3db80c9ab9160d9c925b0066ae9b3af72bf22cb4bf2e5278c43c9f47f4b42d"
    assert release.sha256_hex(stage1["files"]["ffcc.fc2-metadata-0.1.0.zip"]) == "2181a12acb9931b4f7cecd4a1ba58b8b01035916979329b3607b4082f4187766"
    assert {name: release.sha256_hex(data) for name, data in produced.items()} == {
        "COMPATIBILITY.json": "fc7c7caf945f0dd4cb0a6b623422dc13149396035e4b5ade515b63d672740476",
        "SHA256SUMS": "1d1bf436b1d992af47cf585f7e64e21f19682b85f087e8c76fa634ab9e28f525",
        "ffcc-amane-release-0.1.0.zip": "86c1ded8f1013dc8b60dda3cd0873c387ba95eda578cc5d78d963365435bb52c",
    }


def test_green_input_does_not_require_optional_coordinates_or_scenario_observations(inputs, core_wheel):
    release, stage1, _directory, matrix = inputs
    for host in matrix["hosts"]:
        for scenario in host["scenarios"]:
            scenario["observations_sha256"] = ""
    assert release.build_finalize(stage1, core_wheel.name, core_wheel.read_bytes(), matrix)


def test_forced_phase_abort_persists_non_green_evidence_and_both_finalize_paths_reject(inputs, core_wheel, tmp_path, monkeypatch):
    gate = load_tool("run_amane_compat_gate.py")
    _release, _stage1, directory, matrix = inputs
    row = matrix["hosts"][0]
    spec = gate.HostSpec(**{key: row[key] for key in ("label", "coordinate_id", "form", "tag", "tag_object", "peeled_commit", "release_version",
                                                    "requires_python", "plugin_api_version", "python_version", "api_fingerprint_sha256", "adapter_used_subset_fingerprint_sha256")},
                         executable="unused", install_dir=str(tmp_path))
    class Host:
        data_dir = tmp_path
        def start(self): pass
        def stop(self): pass
        def probe(self, _request): return {"ok": False}
    monkeypatch.setattr(gate.HostRun, "host", lambda *_args, **_kwargs: Host())
    monkeypatch.setattr(gate, "snapshot_roots", lambda *_args, **_kwargs: {})
    def successful_phase(run, *_args):
        for name in gate.SCENARIO_IDS:
            if name not in run.results:
                run.scenario(name)
    def abort(run, *_args):
        assert run.results["HC-08"].failures == []
        raise RuntimeError("P5-C2-L1-01 forced phase abort")
    for name in ("phase_failures", "phase_success", "phase_core_upgrade"):
        monkeypatch.setattr(gate, name, successful_phase)
    monkeypatch.setattr(gate, "phase_own_stack", abort)
    monkeypatch.setattr(gate, "hc18_scan_data_dir", lambda *_args: [])
    monkeypatch.setattr(gate, "finish_side_effects", lambda *_args: None)
    monkeypatch.setattr(gate, "finish_admission", lambda *_args: None)
    monkeypatch.setattr(gate, "load_specs", lambda *_args: ({"a-win": spec}, spec.peeled_commit, ""))
    monkeypatch.setattr(gate, "build_oracle", lambda: {})
    out = tmp_path / "partA.json"
    details = tmp_path / "details.json"
    code = gate.main(["run", "--hosts-json", "unused", "--core-wheel", str(core_wheel), "--stage1-dir", str(directory),
                      "--work", str(tmp_path / "host"), "--out", str(out), "--details", str(details)])
    assert code != 0
    verify_abort_outputs(gate, core_wheel, directory, out, details, tmp_path / "rejected")
