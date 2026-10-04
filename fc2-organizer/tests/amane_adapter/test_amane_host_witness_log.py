"""P5-C1 计划第 8 节：真实宿主见证日志的新鲜度与完整性（主进程；恒执行，不 skip；不 import amane）。

日志由 ``tools/run_amane_host_witness.py`` 在 Python >= 3.14 + 真实 Amane v0.15.0 中产出并提交。
本测试防止陈旧日志 / 被手工编辑的日志 / Core 或插件树在见证之后被改动而日志未更新。
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from fc2_amane_adapter import _settings as _module_under_test

ROOT = Path(__file__).resolve().parents[2]
LOG_PATH = ROOT / "docs" / "acceptance" / "evidence" / "P5_C1_HOST_WITNESS.json"
RUNNER_PATH = ROOT / "tools" / "run_amane_host_witness.py"
ADAPTER_TREE = Path(_module_under_test.__file__).resolve().parent
CORE_TREE = ROOT / "src" / "fc2_metadata_core"

_spec = importlib.util.spec_from_file_location("run_amane_host_witness_under_test", RUNNER_PATH)
runner = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(runner)  # type: ignore[union-attr]

LOG_TEXT = LOG_PATH.read_text(encoding="utf-8")
LOG = json.loads(LOG_TEXT)
SCENARIOS = {item["id"]: item for item in LOG["scenarios"]}


def test_scenario_ids_are_exactly_h01_to_h15_and_match_the_runner_constant():
    assert list(runner.SCENARIO_IDS) == [f"H-{index:02d}" for index in range(1, 16)]
    assert [item["id"] for item in LOG["scenarios"]] == list(runner.SCENARIO_IDS)
    assert set(SCENARIOS) == set(runner.SCENARIO_IDS)


def test_every_scenario_passed_with_observations_and_no_failure_record():
    for scenario_id, item in SCENARIOS.items():
        assert item["passed"] is True, (scenario_id, item.get("failure"))
        assert item["observations"], scenario_id
        assert "failure" not in item and "traceback" not in item


def test_log_records_the_exact_amane_commit_and_a_python_314_host():
    assert LOG["schema_version"] == runner.SCHEMA_VERSION == 1
    assert LOG["amane"] == {"version": "0.15.0", "commit": "45dff2159369883e028a296d775a4598836c1ddd"}
    major, minor = (int(part) for part in LOG["python"].split(".")[:2])
    assert (major, minor) >= (3, 14)
    environment = SCENARIOS["H-01"]["observations"]
    assert environment["amane_commit"] == LOG["amane"]["commit"] and environment["amane_version"] == "0.15.0"
    assert environment["checkout_clean"] is True and environment["imported_from_checkout"] is True
    assert environment["manifest_equals_regenerated"] is True


def test_tree_hashes_equal_the_current_repository_state():
    """陈旧日志 / 见证之后 Core 或插件树被改动：哈希不再相等。"""
    assert LOG["adapter_tree_sha256"] == runner.tree_sha256(ADAPTER_TREE)
    assert LOG["core_tree_sha256"] == runner.tree_sha256(CORE_TREE)


def test_log_is_canonical_reproducible_output_without_clock_or_environment_data():
    assert runner.render(LOG) == LOG_TEXT.replace("\r\n", "\n")
    for forbidden in ("timestamp", "duration", "elapsed", "Temp\\\\", "/tmp/", "AppData", "127.0.0.1:"):
        assert forbidden not in LOG_TEXT, forbidden


def test_key_witness_observations_match_the_frozen_contract():
    nine = SCENARIOS["H-09"]["observations"]
    assert nine["bounds"] == {"default_S3_H3": {"L1": 3, "L2": 9, "L3": 189}, "maximum_S3_H10": {"L1": 3, "L2": 30, "L3": 630}}
    assert nine["redirect_loop"]["S3_H3"] == {"network_hops": 189, "bound_S_x_H_x_21": 189, "hops_per_attempt": 21}
    assert nine["redirect_loop"]["S1_H10"]["network_hops"] == 210 <= nine["redirect_loop"]["S1_H10"]["bound_S_x_H_x_21"]
    assert nine["transport_paths"]["curl_error_H3"] == {"host_attempts": 9, "bound_S_x_H": 9}
    assert nine["transport_paths"]["curl_error_H10"] == {"host_attempts": 30, "bound_S_x_H": 30}
    assert set(nine["status_paths"]) == {"200", "403", "404", "429", "503", "500", "599"}
    assert nine["status_600"]["host_attempts"] == 3
    assert SCENARIOS["H-15"]["observations"]["host_attempts"] == 0
    assert SCENARIOS["H-13"]["observations"]["hash_seeds"] == [0, 1, 2]
    assert SCENARIOS["H-12"]["observations"]["source_urls_keys"] == ["ffcc.fc2-metadata"]
    assert SCENARIOS["H-12"]["observations"]["external_ids_keys"] == ["ffcc.fc2-metadata"]
    assert SCENARIOS["H-07"]["observations"]["metadata"]["external_id"] == "4979299"
    assert SCENARIOS["H-11"]["observations"]["recorded_outcomes"] == 0
