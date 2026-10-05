"""P5-C2 E23 / E24 / M2-16：兼容见证 JSON 的 schema 与自洽规则；支持坐标表一致性（合同第 7.2、14 节）。

状态以**坐标** ``(version, host_form, platform)`` 为 key；版本级状态不得覆盖平台状态；UNVERIFIED 不得写成 SUPPORTED；
``IDENTICAL_TO_STABLE`` 的 main 不得伪装成独立见证。S3 会对**已提交的真实 MATRIX** 再跑同一个校验器。
"""

from __future__ import annotations

import copy
import json
import re

import pytest

from _compat_support import REPO, load_tool, synthetic_matrix

ARTIFACTS = {key: format(index + 1, "x") * 64 for index, key in enumerate(("plugin_zip_sha256", "core_wheel_sha256", "core_tree_sha256", "adapter_tree_sha256", "impl_tree_sha256", "shim_tree_sha256", "pin_sha256"))}


@pytest.fixture(scope="module")
def gate():
    return load_tool("run_amane_compat_gate.py")


@pytest.fixture()
def matrix():
    return copy.deepcopy(synthetic_matrix(ARTIFACTS))


def _status(document, coordinate_id):
    return next(row for row in document["status"] if row["coordinate_id"] == coordinate_id)


def test_a_consistent_matrix_validates_and_has_the_frozen_coordinate_table(gate, matrix):
    assert gate.validate_matrix(matrix) == []
    assert [item["id"] for item in matrix["policy"]["support_coordinates"]] == [f"SC-0{i}" for i in range(1, 10)]
    assert {row["coordinate_id"]: row["status"] for row in matrix["status"]} == {
        "SC-01": "SUPPORTED", "SC-02": "SUPPORTED", "SC-03": "SUPPORTED", "SC-04": "SUPPORTED",
        "SC-05": "IDENTICAL_TO_STABLE", "SC-06": "UNVERIFIED", "SC-07": "UNVERIFIED", "SC-08": "UNVERIFIED", "SC-09": "UNVERIFIED",
    }


def test_status_rows_are_keyed_by_coordinate_never_by_version_alone(gate, matrix):
    for row in matrix["status"]:
        assert {"coordinate_id", "amane_version", "host_form", "platform", "status", "reason"} <= set(row)
    two_rows_for_one_version = [row for row in matrix["status"] if row["amane_version"] == "v0.18.0"]
    assert len(two_rows_for_one_version) == 2 and {row["host_form"] for row in two_rows_for_one_version} == {"frozen-desktop", "source"}


@pytest.mark.parametrize(
    "mutation",
    [
        "unverified_marked_supported", "version_keyed_status", "main_counted_as_independent_witness", "conditionally_on_sc01",
        "supported_without_full_scenarios", "parity_flag_disagrees", "observed_differs_from_expected", "payload_executed",
        "volatile_local_path", "platform_list_changed", "support_table_changed", "final_artifact_bad_hash", "duplicate_status_row",
        "failure_left_path_changed", "wrong_core_hash", "non_whitelisted_diff",
        "e16_missing", "e16b_missing_kind", "e16b_extra_kind", "e16b_not_found_wrong_category", "e16b_not_found_as_source_error", "e16b_wrong_reason", "e16b_detail_dropped",
        "e16b_missing_required_host", "e16b_hosts_disagree", "e16b_path_not_verified_on_a_host", "e16a_old_false_label", "e16a_kind_set_changed", "e16a_missing_required_host",
        "symlink_unavailable_without_privilege_false", "symlink_unavailable_with_privilege_true", "unavailable_on_a_non_symlink_case", "unavailable_row_with_payload_executed",
        "symlink_row_missing_for_a_host", "symlink_row_duplicated", "symlink_privilege_on_a_non_symlink_case", "required_host_missing",
    ],
)
def test_m2_16_every_self_consistency_violation_is_rejected(gate, matrix, mutation):
    if mutation == "unverified_marked_supported":
        _status(matrix, "SC-07")["status"] = "SUPPORTED"
    elif mutation == "version_keyed_status":
        for row in matrix["status"]:
            row.pop("host_form")
    elif mutation == "main_counted_as_independent_witness":
        matrix["hosts"][-1]["scenarios"] = [{"id": "HC-01", "passed": True, "observations_sha256": "ab" * 32}]
    elif mutation == "conditionally_on_sc01":
        _status(matrix, "SC-01")["status"] = "CONDITIONALLY_SUPPORTED"
    elif mutation == "supported_without_full_scenarios":
        matrix["hosts"][0]["scenarios"] = matrix["hosts"][0]["scenarios"][:5]
    elif mutation == "parity_flag_disagrees":
        matrix["parity"]["required_pairs"][0]["sha256_b"] = "cd" * 32
    elif mutation == "observed_differs_from_expected":
        matrix["core_admission"]["cases"][1]["observed"] = "PASS"
    elif mutation == "payload_executed":
        matrix["core_admission"]["cases"][1]["payload_executed"] = True
    elif mutation == "volatile_local_path":
        matrix["policy"]["stable_definition"] = "C:\\Users\\someone\\amane"
    elif mutation == "platform_list_changed":
        matrix["platforms_unverified"] = ["macos", "linux"]
    elif mutation == "support_table_changed":
        matrix["policy"]["support_coordinates"][6]["claim_class"] = "deployment"
    elif mutation == "final_artifact_bad_hash":
        matrix["final_artifacts"] = {"compatibility_json_sha256": "xyz", "sha256sums_sha256": "00" * 32, "release_bundle_sha256": "00" * 32}
    elif mutation == "duplicate_status_row":
        matrix["status"].append(copy.deepcopy(matrix["status"][0]))
    elif mutation == "failure_left_path_changed":
        matrix["core_admission"]["cases"][1]["sys_path_unchanged_on_fail"] = False
    elif mutation == "wrong_core_hash":
        matrix["core_admission"]["core_wheel_sha256"] = "00" * 32
    elif mutation == "non_whitelisted_diff":
        matrix["parity"]["allowed_diffs_observed"] = ["DIFF-99"]
    else:
        _apply_evidence_mutation(matrix, mutation)
    assert gate.validate_matrix(matrix) != [], mutation


def _symlink_rows(document):
    return [row for row in document["core_admission"]["cases"] if row["id"].endswith(":sidecar_symlink_to_the_exact_wheel")]


def _apply_evidence_mutation(matrix, mutation):
    """A1：E16-A / E16-B / 符号链接 ``ENVIRONMENTALLY_UNAVAILABLE`` 的每一种违例；每个都必须被校验器拒绝。"""
    e16 = matrix["parity"]["e16"]
    outcomes = e16["e16_b"]["outcomes"]
    if mutation == "e16_missing":
        del matrix["parity"]["e16"]
    elif mutation == "e16b_missing_kind":
        del outcomes["CIRCUIT_OPEN"]
    elif mutation == "e16b_extra_kind":
        outcomes["BRAND_NEW_KIND"] = dict(outcomes["BLOCKED"])
    elif mutation == "e16b_not_found_wrong_category":
        outcomes["NOT_FOUND"]["result_category"] = "SourceError"
    elif mutation == "e16b_not_found_as_source_error":
        outcomes["NOT_FOUND"] = {"result_category": "SourceError", "failure_reason": "unexpected", "detail": "internal adapter error: X"}
    elif mutation == "e16b_wrong_reason":
        outcomes["TIMEOUT"]["failure_reason"] = "network"
    elif mutation == "e16b_detail_dropped":
        outcomes["BLOCKED"]["detail"] = None
    elif mutation == "e16b_missing_required_host":
        del e16["e16_b"]["per_host_sha256"]["b-win"]
    elif mutation == "e16b_hosts_disagree":
        e16["e16_b"]["per_host_sha256"]["a-src"] = "00" * 32
    elif mutation == "e16b_path_not_verified_on_a_host":
        e16["e16_b"]["production_path_verified_on_hosts"] = ["a-src", "a-win", "b-src"]
    elif mutation == "e16a_old_false_label":
        e16["e16_a"]["cases"]["kind_response_too_large"] = {"result_class": "SourceError", "failure_reason": "parse_error", "actual_source_error_kind": ["invalid_response", "parse_error"]}
        for label in e16["e16_a"]["per_host_sha256"]:
            e16["e16_a"]["per_host_sha256"][label] = load_tool("run_amane_compat_gate.py").canonical_hash(e16["e16_a"]["cases"])
    elif mutation == "e16a_kind_set_changed":
        e16["e16_a"]["observed_kinds"] = sorted([*e16["e16_a"]["observed_kinds"], "decode_error"])
    elif mutation == "e16a_missing_required_host":
        del e16["e16_a"]["per_host_sha256"]["a-win"]
    elif mutation == "symlink_unavailable_without_privilege_false":
        row = _symlink_rows(matrix)[0]
        del row["symlink_privilege"]
    elif mutation == "symlink_unavailable_with_privilege_true":
        _symlink_rows(matrix)[0]["symlink_privilege"] = True
    elif mutation == "unavailable_on_a_non_symlink_case":
        matrix["core_admission"]["cases"][1]["observed"] = "ENVIRONMENTALLY_UNAVAILABLE"
        matrix["core_admission"]["cases"][1]["symlink_privilege"] = False
    elif mutation == "unavailable_row_with_payload_executed":
        _symlink_rows(matrix)[0]["payload_executed"] = True
    elif mutation == "symlink_row_missing_for_a_host":
        matrix["core_admission"]["cases"].remove(_symlink_rows(matrix)[0])
    elif mutation == "symlink_row_duplicated":
        matrix["core_admission"]["cases"].append(copy.deepcopy(_symlink_rows(matrix)[0]))
    elif mutation == "symlink_privilege_on_a_non_symlink_case":
        matrix["core_admission"]["cases"][0]["symlink_privilege"] = False
    elif mutation == "required_host_missing":
        matrix["hosts"] = [host for host in matrix["hosts"] if host["label"] != "b-win"]
    else:
        raise AssertionError(mutation)


def test_the_only_legal_unavailable_row_is_the_symlink_sub_case_with_symlink_privilege_false(gate, matrix):
    rows = _symlink_rows(matrix)
    assert sorted(row["id"].split(":")[0] for row in rows) == sorted(gate.REQUIRED_LABELS)
    assert all(row["observed"] == "ENVIRONMENTALLY_UNAVAILABLE" and row["symlink_privilege"] is False and row["expected"] == "FAIL" for row in rows)
    assert gate.validate_matrix(matrix) == []
    executed = copy.deepcopy(matrix)
    for row in _symlink_rows(executed):  # 有权限的环境：真实执行 -> FAIL == expected，symlink_privilege = true
        row.update({"observed": "FAIL", "symlink_privilege": True})
    assert gate.validate_matrix(executed) == []


def test_every_e16_b_kind_and_every_required_host_is_expressed_mechanically(gate, matrix):
    e16 = matrix["parity"]["e16"]
    assert sorted(e16["e16_b"]["outcomes"]) == sorted(name for name in gate.E16B_EXPECTED_REASON) and e16["e16_b"]["kind_count"] == 16
    assert e16["e16_b"]["outcomes"]["NOT_FOUND"] == {"result_category": "None", "failure_reason": None, "detail": None}
    assert set(e16["e16_b"]["per_host_sha256"]) == set(e16["e16_a"]["per_host_sha256"]) == set(gate.REQUIRED_LABELS)
    assert e16["e16_a"]["observed_kinds"] == sorted(gate.E16A_OBSERVED_KINDS) and len(gate.E16A_OBSERVED_KINDS) == 7


def test_blocked_when_a_required_witness_fails_or_is_missing(gate, matrix):
    matrix["hosts"][1]["scenarios"][3]["passed"] = False
    derived = gate.derive_status("SC-02", matrix["hosts"], parity_equal=True, stable_peeled_commit="0a" * 20)
    assert derived["status"] == "BLOCKED" and "HC-04" in derived["reason"]
    assert gate.derive_status("SC-03", [], parity_equal=True, stable_peeled_commit="0a" * 20)["status"] == "BLOCKED"
    assert gate.derive_status("SC-01", matrix["hosts"], parity_equal=False, stable_peeled_commit="0a" * 20)["status"] == "BLOCKED"


def test_a_failing_required_coordinate_cannot_be_reported_as_supported(gate, matrix):
    matrix["hosts"][1]["scenarios"][3]["passed"] = False
    assert any("SUPPORTED is not backed" in problem for problem in gate.validate_matrix(matrix))
    _status(matrix, "SC-02")["status"] = "BLOCKED"
    assert gate.validate_matrix(matrix) == []


def test_main_is_informational_when_it_differs_from_stable_and_identical_otherwise(gate):
    hosts = synthetic_matrix(ARTIFACTS, identical_main=False)["hosts"]
    assert gate.derive_status("SC-05", hosts, parity_equal=True, stable_peeled_commit="0a" * 20)["status"] == "INFORMATIONAL"
    same = synthetic_matrix(ARTIFACTS, identical_main=True)["hosts"]
    assert gate.derive_status("SC-05", same, parity_equal=True, stable_peeled_commit="0a" * 20)["status"] == "IDENTICAL_TO_STABLE"
    assert gate.derive_status("SC-05", [], parity_equal=True, stable_peeled_commit="0a" * 20)["status"] == "UNVERIFIED"


def test_rendering_is_deterministic_sorted_lf_and_ascii(gate, matrix):
    first, second = gate.render(matrix), gate.render(copy.deepcopy(matrix))
    assert first == second and first.endswith("\n") and "\r" not in first and first.isascii()
    assert json.loads(first) == matrix


def test_part_a_and_part_b_split_is_by_the_frozen_key_sets(gate, matrix):
    matrix["final_artifacts"] = {"compatibility_json_sha256": "11" * 32, "sha256sums_sha256": "22" * 32, "release_bundle_sha256": "33" * 32}
    part_a, part_b = gate.split_parts(matrix)
    assert set(part_b) == {"final_artifacts"} and "final_artifacts" not in part_a
    assert set(part_a) == set(gate.PART_A_KEYS)
    assert gate.validate_matrix(matrix) == []


# ------------------------------------------------------------------ E24：INSTALL / COMPATIBILITY / 合同使用同一份坐标表

def test_e24_install_table_rows_equal_the_frozen_coordinate_table(gate):
    text = (REPO / "adapters" / "amane" / "release" / "INSTALL.zh-CN.md").read_text(encoding="utf-8")
    rows = re.findall(r"^\| (SC-0[1-4]) \| (v[0-9.]+) \| (.+?) \| (.+?) \|$", text, re.MULTILINE)
    assert [row[0] for row in rows] == ["SC-01", "SC-02", "SC-03", "SC-04"]
    for coordinate_id, version, form, platform in rows:
        spec = gate.coordinate(coordinate_id)
        assert version == spec["amane_version"]
        assert ("冻结桌面版" in form) == (spec["host_form"] == "frozen-desktop")
        assert ("源码宿主" in form) == (spec["host_form"] == "source")
        assert platform == "Windows x64"
    for unverified in ("macOS", "Linux", "Docker"):
        assert unverified in text
    assert "UNVERIFIED" in text


def test_e24_contract_support_table_matches_the_frozen_coordinate_table(gate):
    contract = (REPO / "docs" / "specifications" / "PHASE5_C2_AMANE_COMPATIBILITY_CONTRACT.md").read_text(encoding="utf-8")
    for spec in gate.SUPPORT_COORDINATES:
        row = re.search(rf"^\| {spec['id']} \| (.+?) \| (.+?) \| (.+?) \| (.+?) \| (.+?) \|$", contract, re.MULTILINE)
        assert row, spec["id"]
        platform_text = row.group(3)
        assert {"windows-x64": "Windows x64", "macos": "macOS", "linux": "Linux"}[spec["platform"]] in platform_text
        if spec["id"] in gate.UNVERIFIED_COORDINATES:
            assert "UNVERIFIED" in row.group(5)
        assert spec["claim_class"] in row.group(4) or spec["claim_class"] == "unverified" or row.group(4) == "—"


def test_e24_compatibility_json_uses_the_same_coordinate_table_and_forbidden_wording_is_absent(gate):
    release = load_tool("build_amane_release.py")
    document = synthetic_matrix(ARTIFACTS)
    projection = release.project_part_a(document)
    assert projection["policy"]["support_coordinates"] == [dict(item) for item in gate.SUPPORT_COORDINATES]
    rendered = json.dumps(projection, ensure_ascii=False)
    for banned in (r"v0\.1[58]\.0 (SUPPORTED|CONDITIONALLY)", r"支持\s*v0\.1[58]", r"支持\s*(Docker|macOS|Linux)"):
        assert not re.search(banned, rendered)
    assert [row["status"] for row in projection["status"] if row["coordinate_id"] in gate.UNVERIFIED_COORDINATES] == ["UNVERIFIED"] * 3


# ------------------------------------------------------------------ 已提交的真实 MATRIX 与仓库树的一致性（E23 / E24 / E29）

MATRIX_PATH = REPO / "docs" / "acceptance" / "evidence" / "P5_C2_COMPATIBILITY_MATRIX.json"


def _committed_matrix():
    return json.loads(MATRIX_PATH.read_text(encoding="utf-8"))


def test_committed_matrix_passes_the_validator_and_is_deterministically_rendered(gate):
    document = _committed_matrix()
    assert gate.validate_matrix(document) == []
    assert MATRIX_PATH.read_bytes().replace(b"\r\n", b"\n") == gate.render(document).encode("utf-8")


def test_committed_matrix_records_all_four_required_coordinates_as_supported_and_the_rest_unverified(gate):
    document = _committed_matrix()
    status = {row["coordinate_id"]: row["status"] for row in document["status"]}
    assert [status[key] for key in ("SC-01", "SC-02", "SC-03", "SC-04")] == ["SUPPORTED"] * 4
    assert status["SC-05"] == "IDENTICAL_TO_STABLE" and {status[key] for key in ("SC-07", "SC-08", "SC-09")} == {"UNVERIFIED"}
    required_hosts = {host["label"]: host for host in document["hosts"] if host["role"] == "required"}
    assert set(required_hosts) == {"a-src", "b-src", "a-win", "b-win"}
    for host in required_hosts.values():
        assert [item["id"] for item in host["scenarios"]] == list(gate.SCENARIO_IDS) and all(item["passed"] for item in host["scenarios"])
        assert host["python_version"].startswith("3.14") and host["requires_python"] == ">=3.14" and host["plugin_api_version"] == "1"
    main = next(host for host in document["hosts"] if host["label"] == "main")
    assert main["identical_to_stable"] is True and main["scenarios"] == []
    assert {host["peeled_commit"] for host in required_hosts.values()} == {"45dff2159369883e028a296d775a4598836c1ddd", "0a8a731d7746bde5e8828d1eb74c7bd9752b42e4"}


def test_committed_matrix_parity_is_complete_equal_and_whitelisted(gate):
    parity = _committed_matrix()["parity"]
    assert [(pair["a"], pair["b"]) for pair in parity["required_pairs"]] == [("a-src", "b-src"), ("a-win", "b-win"), ("a-src", "a-win"), ("b-src", "b-win")]
    assert all(pair["equal"] and pair["sha256_a"] == pair["sha256_b"] for pair in parity["required_pairs"])
    assert {"fetch_cases", "e16a_actual_source_error_kind", "e16b_kind_outcomes", "hc12_variant_statuses", "config_booleans", "descriptor_subset", "config_schema_sha256", "identity"} <= set(parity["required_pairs"][0]["fields"])
    assert "source_error_kind_mapping" not in parity["required_pairs"][0]["fields"]  # 旧的叶子函数映射（reason_for_kind）不是 E16-B
    assert set(parity["allowed_diffs_observed"]) <= set(gate.DIFF_WHITELIST)


def test_committed_matrix_records_e16_a_actual_kinds_and_e16_b_all_16_kinds_on_four_hosts(gate):
    e16 = _committed_matrix()["parity"]["e16"]
    assert e16["e16_b"]["kind_count"] == 16 and e16["e16_b"]["equal"] is True and set(e16["e16_b"]["per_host_sha256"]) == set(gate.REQUIRED_LABELS)
    assert len(set(e16["e16_b"]["per_host_sha256"].values())) == 1 and len(set(e16["e16_a"]["per_host_sha256"].values())) == 1
    assert e16["e16_b"]["production_path_verified_on_hosts"] == sorted(gate.REQUIRED_LABELS)
    assert e16["e16_b"]["outcomes"]["NOT_FOUND"] == {"result_category": "None", "failure_reason": None, "detail": None}
    assert e16["e16_a"]["observed_kinds"] == sorted(gate.E16A_OBSERVED_KINDS)
    assert not [case for case in e16["e16_a"]["cases"] if case.startswith("kind_")]
    old_labels = {"kind_decode_error_bad_charset", "kind_redirect_error_loop", "kind_response_too_large"}
    assert not old_labels & set(e16["e16_a"]["cases"])
    assert e16["e16_a"]["cases"]["stimulus_redirect_loop"]["actual_source_error_kind"] == ["connection_error"]
    assert e16["e16_a"]["cases"]["stimulus_oversize_body_3mib"]["actual_source_error_kind"] == ["invalid_response", "parse_error"]
    assert e16["e16_a"]["cases"]["stimulus_unknown_charset"]["actual_source_error_kind"] == ["invalid_response", "parse_error"]


def test_committed_matrix_symlink_sub_case_is_environmentally_unavailable_on_every_required_host(gate):
    cases = _committed_matrix()["core_admission"]["cases"]
    rows = [case for case in cases if case["id"].endswith(":sidecar_symlink_to_the_exact_wheel")]
    assert sorted(row["id"].split(":")[0] for row in rows) == sorted(gate.REQUIRED_LABELS)
    assert all(row["observed"] == "ENVIRONMENTALLY_UNAVAILABLE" and row["symlink_privilege"] is False for row in rows)
    assert [case["id"] for case in cases if case["observed"] == "ENVIRONMENTALLY_UNAVAILABLE"] == [row["id"] for row in rows]


def test_committed_matrix_core_admission_covers_the_e31_branches_on_every_required_host():
    admission = _committed_matrix()["core_admission"]
    cases = [case for case in admission["cases"] if case["observed"] != "ENVIRONMENTALLY_UNAVAILABLE"]  # 唯一的例外 = 符号链接真实宿主子项（见上一个测试）
    assert all(case["observed"] == case["expected"] and case["payload_executed"] is False for case in cases)
    assert all(case["sys_path_unchanged_on_fail"] and case["sys_modules_unchanged_on_fail"] for case in cases if case["expected"] == "FAIL")
    for label in ("a-src", "b-src"):
        names = {case["id"].split(":", 1)[1] for case in cases if case["id"].startswith(label + ":")}
        assert {"e31u_wheel_in_path_resolution_disagrees", "e31v_subclass_loader_in_final_resolution", "dir_pyc_poc_no_sidecar", "dir_pyc_poc_with_sidecar", "preloaded_directory",
                "e31l_rollback_cache_absent", "e31l_rollback_cache_present", "shadow_meta_path_finder", "pythonpath_pyc_poc_no_sidecar"} <= names, label
    for label in ("a-win", "b-win"):
        names = {case["id"].split(":", 1)[1] for case in cases if case["id"].startswith(label + ":")}
        assert {"sidecar_tampered_same_name_one_byte", "sidecar_only_other_version_wheel", "sidecar_oversize_over_16_mib", "sidecar_same_name_directory", "loaded_old_core_with_new_pin"} <= names, label


def test_committed_matrix_artifacts_equal_a_fresh_rebuild_from_the_tree(gate, tmp_path):
    """E29：Part A 的 Level-0 / Level-1 哈希必须等于由当前仓库树重新构建的字节；工具哈希必须等于当前网关文件。"""
    document = _committed_matrix()
    builder = load_tool("build_core_wheel.py")
    release = load_tool("build_amane_release.py")
    name, payload, tree_hash = builder.build_wheel_bytes(REPO / "src" / "fc2_metadata_core", REPO / "pyproject.toml")
    wheel = tmp_path / name
    wheel.write_bytes(payload)
    stage1 = release.build_stage1(REPO, wheel)
    assert document["artifacts"] == stage1["artifacts"]
    assert document["core_admission"]["core_wheel_sha256"] == stage1["artifacts"]["core_wheel_sha256"]
    assert document["tool"]["sha256"] == gate.sha256_hex((REPO / "tools" / "run_amane_compat_gate.py").read_bytes().replace(b"\r\n", b"\n"))
    witness = json.loads((REPO / "docs" / "acceptance" / "evidence" / "P5_C1_HOST_WITNESS.json").read_text(encoding="utf-8"))
    assert document["artifacts"]["adapter_tree_sha256"] == witness["adapter_tree_sha256"] and document["artifacts"]["core_tree_sha256"] == witness["core_tree_sha256"] == tree_hash


def test_committed_matrix_contains_no_volatile_or_local_data():
    text = MATRIX_PATH.read_text(encoding="utf-8")
    assert not re.search(r"[A-Za-z]:\\|/Users/|127\.0\.0\.1:\d+|\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}", text)
