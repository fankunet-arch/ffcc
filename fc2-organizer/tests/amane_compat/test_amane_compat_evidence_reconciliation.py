"""P5-C2 Pre-L1 Evidence Reconciliation（Accepted Authority A1 = ``b8480e74…``）的证据守卫。

只覆盖**证据 schema / 证据见证 / 校验器 / 范围门**；不改变、也不测试任何产品语义（那些由 ``tests/amane_adapter`` 与既有 C2 测试负责）。

* R-1：``POST /api/plugins`` 成功 = 精确 201 Created（不泛化为 2xx）。
* R-2：HC-12a..12e 逐个冻结（12a = 宿主实测 500；12b..e = 422）。
* R-3：符号链接真实宿主子项 = ``ENVIRONMENTALLY_UNAVAILABLE`` + 必需的替代证据（3.12 / 3.14 单元层、``st_mode`` 替身、M2-14）。
* R-4：E16-A 实际观测 kind；E16-B 全部 16 个 kind 经生产映射路径与生产 provider 转换（含 6 个非空洞 guard）。
* R-5：HANDOFF 如实对账。
* 范围门：``b8480e74..HEAD`` 只含被授权的证据面；产品 / 权威文件零 diff；L0 / L1 输入字节不变。
"""

from __future__ import annotations

import ast
import asyncio
import copy
import importlib.util
import re
import subprocess
import sys

import pytest

from _compat_support import HARNESS, REPO, EXPECT, interpreters, load_tool, synthetic_matrix

AUTHORITY_HEAD = "b8480e74ab2b8d7901a0de98ee396f72e204aba7"
#: 被验收候选 4358b3d 的 L0 / L1：本轮不得改变它们的输入字节，因此这两个哈希必须原样不变（改变 = 越权）。
L0_CORE_WHEEL_SHA256 = "0b3db80c9ab9160d9c925b0066ae9b3af72bf22cb4bf2e5278c43c9f47f4b42d"
L1_PLUGIN_ZIP_SHA256 = "2181a12acb9931b4f7cecd4a1ba58b8b01035916979329b3607b4082f4187766"

GATE = REPO / "tools" / "run_amane_compat_gate.py"
IN_HOST = REPO / "tests" / "amane_compat" / "host_scripts" / "in_host.py"
HANDOFF = REPO / "docs" / "review" / "P5_C2_HANDOFF.md"
MATRIX = REPO / "docs" / "acceptance" / "evidence" / "P5_C2_COMPATIBILITY_MATRIX.json"
ARTIFACTS = {key: format(index + 1, "x") * 64 for index, key in enumerate(("plugin_zip_sha256", "core_wheel_sha256", "core_tree_sha256", "adapter_tree_sha256", "impl_tree_sha256", "shim_tree_sha256", "pin_sha256"))}


@pytest.fixture(scope="module")
def gate():
    return load_tool("run_amane_compat_gate.py")


@pytest.fixture(scope="module")
def in_host():
    name = "ffcc_test_reconciliation_in_host"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, IN_HOST)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _function(source: str, name: str) -> ast.FunctionDef:
    return next(node for node in ast.walk(ast.parse(source)) if isinstance(node, ast.FunctionDef) and node.name == name)


# ================================================================== R-1：201 Created


def test_r1_successful_install_is_exactly_201_and_never_generalised(gate):
    source = GATE.read_text(encoding="utf-8")
    assert gate.INSTALLED == 201
    assert len(re.findall(r"\bINSTALLED\b", source)) >= 12
    for forbidden in ("expected 200", "200 <= status", "< 300", "2xx", "(200, 201)", "status in (200"):
        assert forbidden not in source, forbidden


def test_r1_every_upload_result_is_compared_only_with_installed_422_or_the_frozen_12a_status():
    """HC-01 / 09 / 10 / 11 / 12 / 13 / 14 / 16 / 19：``host.upload`` 的状态码只允许与 INSTALLED、422、expected_status（12a..e）比较。"""
    lines = GATE.read_text(encoding="utf-8").splitlines()
    inspected = 0
    for index, line in enumerate(lines):
        match = re.match(r"\s*(\w+)\s*,\s*\w+\s*=\s*host\.upload\(", line)
        if not match:
            continue
        variable = match.group(1)
        for later in lines[index + 1:index + 14]:
            if re.match(rf"\s*{variable}\s*(,|=)", later):  # 变量被重新赋值（下一次宿主调用）
                break
            for operator_and_value in re.findall(rf"\b{variable}\s*(?:==|!=|<=|>=|<|>)\s*(\w+)", later):
                assert operator_and_value in {"INSTALLED", "422", "expected_status"}, (line.strip(), later.strip())
                inspected += 1
    assert inspected >= 12


# ================================================================== R-2：HC-12a..e


def test_r2_hc12_variants_are_frozen_individually_with_exact_statuses():
    function = _function(GATE.read_text(encoding="utf-8"), "phase_failures")
    assignment = next(node for node in ast.walk(function) if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "variants" for target in node.targets))
    rows = [(item.elts[0].value, item.elts[2].value) for item in assignment.value.elts]
    assert rows == [("12a_not_a_zip", 500), ("12b_path_traversal", 422), ("12c_no_plugin_py", 422), ("12d_multiple_top_level_folders", 422), ("12e_oversize_over_20_mib", 422)]
    source = GATE.read_text(encoding="utf-8")
    assert "status == expected_status" in source and "status in allowed" not in source and "(422, 500)" not in source


def test_r2_hc12_records_rejection_residue_registration_and_that_plugin_code_never_ran():
    source = GATE.read_text(encoding="utf-8")
    for needle in ('"rejected"', '"sources_entries"', '"registered_plugins"', '"plugin_code_executed"', "hc12a_known_pinned_host_route_defect", 'run.extras["hc12"]'):
        assert needle in source, needle


def test_an_aborted_host_phase_fails_the_whole_run_instead_of_leaving_unexecuted_checks_green():
    source = GATE.read_text(encoding="utf-8")
    assert 'and not any(run.extras.get("phase_errors") for run in runs.values())' in source


def test_r2_the_variant_statuses_enter_the_cross_host_parity_payload(gate):
    class Run:
        extras = {"hc12": {"12a_not_a_zip": 500}}

    assert gate.parity_payload(Run())["hc12_variant_statuses"] == {"12a_not_a_zip": 500}


# ================================================================== R-3：符号链接


def test_r3_the_unit_level_substitute_changes_only_st_mode_and_runs_on_both_interpreters():
    harness = HARNESS.read_text(encoding="utf-8")
    assert "os.stat_result((stat.S_IFLNK | 0o777,) + tuple(real)[1:])" in harness  # 只改 st_mode；大小 / 时间戳保持真实
    assert EXPECT["i_sidecar_symlink"]["outcome"] == "FAIL" and EXPECT["i_sidecar_symlink"]["template"] == "WHEEL_HASH_MISMATCH"
    labels = [label for label, _path in interpreters()]
    assert labels == ["main", "py314"]
    assert all(path for _label, path in interpreters()), "E31-s：3.12 与 3.14 都必须可用（不允许 skip）"


def test_r3_the_m2_14_symlink_acceptance_mutant_exists_and_is_killed_by_the_symlink_case():
    text = (REPO / "tests" / "amane_compat" / "test_amane_compat_mutation_nonvacuity.py").read_text(encoding="utf-8")
    assert 'Mutant("M2-14", "accept-symlink"' in text and 'locator_case("i_sidecar_symlink")' in text


def test_r3_the_gate_marks_the_real_host_symlink_sub_case_unavailable_only_when_the_os_refuses_the_symlink():
    source = GATE.read_text(encoding="utf-8")
    assert "except (OSError, NotImplementedError):\n        symlink_privilege = False" in source
    assert '"observed": ENV_UNAVAILABLE' in source and '"symlink_privilege": False' in source
    assert "symlink_executed" not in source  # 旧的“executed = false + 注记”记法已被替换


# ================================================================== R-4：E16-A


def test_r4a_the_three_mislabelled_cases_are_renamed_and_no_case_claims_a_kind(in_host):
    cases = {case_id for case_id, _number, _extra in in_host.FETCH_CASES}
    assert not cases & {"kind_decode_error_bad_charset", "kind_redirect_error_loop", "kind_response_too_large"}
    assert not [case for case in cases if case.startswith("kind_")]


def test_r4a_actual_kinds_are_read_from_the_detail_vocabulary(gate):
    assert gate.kinds_from_detail("FC2 lookup failed: fc2db_net=parse_error; javdb=invalid_response; av123=parse_error") == ["invalid_response", "parse_error"]
    assert gate.kinds_from_detail("FC2 lookup failed: fc2db_net=connection_error; javdb=connection_error; av123=connection_error") == ["connection_error"]
    assert gate.kinds_from_detail("FC2 lookup failed: fc2db_net=blocked; javdb=not_found; av123=not_found") == ["blocked"]
    assert gate.kinds_from_detail("invalid search query") == [] and gate.kinds_from_detail(None) == []
    table = gate.e16a_table({"a": {"class": "SourceError", "reason": "network", "detail": "FC2 lookup failed: x=connection_error"}, "b": {"class": "None"}, "c": {"class": "MediaMetadata"}})
    assert table["a"]["actual_source_error_kind"] == ["connection_error"] and table["b"]["actual_source_error_kind"] == [] and table["c"]["actual_source_error_kind"] == []


def test_r4a_the_frozen_observed_set_is_exactly_the_seven_kinds_and_never_a_label(gate):
    assert gate.E16A_OBSERVED_KINDS == ("blocked", "connection_error", "http_server_error", "invalid_response", "parse_error", "rate_limited", "source_deadline")
    good = {
        "a": {"result_class": "SourceError", "failure_reason": "x", "actual_source_error_kind": list(gate.E16A_OBSERVED_KINDS)},
        "success_all_sources": {"result_class": "MediaMetadata", "failure_reason": None, "actual_source_error_kind": []},
    }
    assert gate.evaluate_e16a(good) == []
    assert gate.evaluate_e16a({**good, "kind_response_too_large": good["a"]}) != []  # 旧标签
    assert gate.evaluate_e16a({"a": {**good["a"], "actual_source_error_kind": ["blocked"]}}) != []  # 观测集合 != K_A
    assert gate.evaluate_e16a({"a": {**good["a"], "actual_source_error_kind": [*gate.E16A_OBSERVED_KINDS, "decode_error"]}}) != []
    assert gate.evaluate_e16a({}) != [] and gate.evaluate_e16a(None) != []


# ================================================================== R-4：E16-B（输入、生产映射、期望表）


def test_r4b_the_expected_table_is_exhaustive_and_independently_agrees_with_the_production_table(gate):
    from fc2_amane_adapter._outcome import KIND_TO_REASON
    from fc2_metadata_core.models import SourceErrorKind

    assert set(gate.E16B_EXPECTED_REASON) == {kind.name for kind in SourceErrorKind} and len(gate.E16B_EXPECTED_REASON) == 16
    for kind in SourceErrorKind:
        assert gate.E16B_EXPECTED_REASON[kind.name] == KIND_TO_REASON.get(kind), kind


def test_r4b_harness_inputs_are_valid_core_objects_and_the_production_map_aggregation_yields_the_expected_neutral_results(gate, in_host):
    from fc2_amane_adapter._outcome import AdapterFailure, AdapterNoMatch, map_aggregation
    from fc2_metadata_core.aggregation import AggregateStatus, AggregationResult
    from fc2_metadata_core.models import SourceErrorKind, SourceResult, SourceStatus
    from fc2_metadata_core.models.source_result import status_for_error_kind

    for kind in SourceErrorKind:
        results = in_host._e16b_results(kind, SourceResult, SourceStatus, SourceErrorKind, status_for_error_kind)
        assert all(type(item) is SourceResult for item in results) and [item.source_id for item in results] == list(in_host.SOURCES)
        aggregate = AggregationResult(number=in_host.E16B_CANONICAL, status=AggregateStatus.FAILED, metadata=None, source_results=results)
        neutral = map_aggregation(aggregate, in_host.E16B_CANONICAL)
        expected = gate.e16b_expected_row(kind.name)
        if expected["failure_reason"] is None:
            assert neutral == AdapterNoMatch("all_not_found"), kind
        else:
            assert isinstance(neutral, AdapterFailure) and (neutral.reason, neutral.detail) == (expected["failure_reason"], expected["detail"]), kind


def test_r4b_the_inert_engine_stub_replaces_only_the_upstream_engine_execution_in_the_production_runtime(gate, in_host):
    """生产 ``AdapterRuntime.lookup_with_cause``（含 ``map_aggregation``）在惰性引擎桩上对每个 kind 给出期望的中立结果；只有 ``engine.aggregate`` 被替代。"""
    from fc2_amane_adapter._outcome import AdapterFailure, AdapterNoMatch
    from fc2_amane_adapter._runtime import AdapterRuntime
    from fc2_amane_adapter._settings import parse_settings
    from fc2_metadata_core.aggregation import AggregateStatus, AggregationResult
    from fc2_metadata_core.models import SourceErrorKind, SourceResult, SourceStatus
    from fc2_metadata_core.models.source_result import status_for_error_kind

    runtime = AdapterRuntime(parse_settings({}), object())
    for kind in SourceErrorKind:
        results = in_host._e16b_results(kind, SourceResult, SourceStatus, SourceErrorKind, status_for_error_kind)
        aggregate = AggregationResult(number=in_host.E16B_CANONICAL, status=AggregateStatus.FAILED, metadata=None, source_results=results)
        engine = in_host._InertEngine(aggregate)
        runtime._engine = engine
        outcome, cause = asyncio.run(runtime.lookup_with_cause(in_host.E16B_QUERY_NUMBER, "fc2"))
        expected = gate.e16b_expected_row(kind.name)
        assert cause is None and engine.calls == [in_host.E16B_CANONICAL], kind
        if expected["failure_reason"] is None:
            assert outcome == AdapterNoMatch("all_not_found"), kind
        else:
            assert isinstance(outcome, AdapterFailure) and (outcome.reason, outcome.detail) == (expected["failure_reason"], expected["detail"]), kind


# ================================================================== R-4：E16-B 非空洞 guard（6 项）


def _good_e16b(gate) -> dict:
    kinds = {name: gate.e16b_expected_row(name) for name in gate.E16B_EXPECTED_REASON}
    path = {}
    for name, reason in gate.E16B_EXPECTED_REASON.items():
        operational = reason is not None
        path[name] = {
            "core_objects_built_with_public_constructors": True, "engine_calls": 1, "engine_called_with_canonical": True, "map_aggregation_calls": 1,
            "map_aggregation_input_is_the_core_object": True, "neutral_result_type": "AdapterFailure" if operational else "AdapterNoMatch",
            "reason_is_host_failure_reason": True if operational else None, "provider_class": "_Fc2MetadataProvider",
        }
    return {"kinds": kinds, "production_path": path}


def _mutate_leaf_function_only(result):
    """E16-B 误只调用叶子函数 ``reason_for_kind``：结果也许“对”，但没有任何生产映射 / provider 转换的痕迹。"""
    for row in result["production_path"].values():
        row.update({"engine_calls": 0, "engine_called_with_canonical": False, "map_aggregation_calls": 0, "map_aggregation_input_is_the_core_object": False,
                    "neutral_result_type": None, "provider_class": None})


def _mutate_kind_omitted(result):
    result["kinds"].pop("TIMEOUT")
    result["production_path"].pop("TIMEOUT")


def _mutate_not_found_as_source_error(result):
    result["kinds"]["NOT_FOUND"] = {"result_category": "SourceError", "failure_reason": "unexpected", "detail": "internal adapter error: X"}


def _mutate_detail_unverified_short(result):
    result["kinds"]["BLOCKED"]["detail"] = "FC2 lookup failed: fc2db_net=blocked"


def _mutate_detail_dropped(result):
    result["kinds"]["HTTP_SERVER_ERROR"]["detail"] = None


def _mutate_handwritten_mapping(result):
    for row in result["production_path"].values():
        row.update({"core_objects_built_with_public_constructors": False, "map_aggregation_input_is_the_core_object": False})


def _mutate_provider_not_production(result):
    result["production_path"]["BLOCKED"]["provider_class"] = "FakeProvider"


def _mutate_wrong_reason(result):
    result["kinds"]["RATE_LIMITED"]["failure_reason"] = "http_error"


def _mutate_reason_not_a_host_member(result):
    result["production_path"]["TIMEOUT"]["reason_is_host_failure_reason"] = False


@pytest.mark.parametrize(
    "mutation",
    [_mutate_leaf_function_only, _mutate_kind_omitted, _mutate_not_found_as_source_error, _mutate_detail_unverified_short, _mutate_detail_dropped,
     _mutate_handwritten_mapping, _mutate_provider_not_production, _mutate_wrong_reason, _mutate_reason_not_a_host_member],
    ids=lambda function: function.__name__.removeprefix("_mutate_"),
)
def test_r4b_guard_every_vacuous_or_wrong_e16_b_result_is_rejected(gate, mutation):
    assert gate.evaluate_e16b(_good_e16b(gate)) == []
    result = _good_e16b(gate)
    mutation(result)
    assert gate.evaluate_e16b(result) != [], mutation.__name__


def test_r4b_guard_an_empty_or_malformed_result_is_rejected(gate):
    for value in (None, {}, {"kinds": {}}, {"kinds": {}, "production_path": {}}, "x"):
        assert gate.evaluate_e16b(value) != []


class _FakeRun:
    def __init__(self, e16a, e16b):
        self.extras = {"e16a": e16a, "e16b": e16b}


def _runs(gate, omit=None, tamper=None):
    good_a = {"stimulus_http_403": {"result_class": "SourceError", "failure_reason": "http_error", "actual_source_error_kind": ["blocked"]}}
    runs = {}
    for label in gate.REQUIRED_LABELS:
        if label == omit:
            continue
        result = _good_e16b(gate)
        if label == tamper:
            result["kinds"]["BLOCKED"]["failure_reason"] = "network"
        runs[label] = _FakeRun(copy.deepcopy(good_a), result)
    return runs


def test_r4b_guard_one_required_host_form_omitted_or_disagreeing_is_rejected(gate):
    required = set(gate.REQUIRED_LABELS)
    assert gate.build_e16(_runs(gate))["e16_b"]["equal"] is True
    assert gate.build_e16(_runs(gate))["e16_b"]["production_path_verified_on_hosts"] == sorted(required)
    omitted = gate.build_e16(_runs(gate, omit="b-win"))
    assert gate.validate_e16(omitted, required) != [] and "b-win" not in omitted["e16_b"]["per_host_sha256"]
    tampered = gate.build_e16(_runs(gate, tamper="a-win"))
    assert tampered["e16_b"]["equal"] is False and gate.validate_e16(tampered, required) != []


# ---- 源码层 guard：宿主内 op_e16b 的结构（经生产路径、不用叶子函数、不手写映射表、不漏 kind）


def e16b_source_problems(source: str) -> list[str]:
    function = _function(source, "op_e16b")
    names = {node.id for node in ast.walk(function) if isinstance(node, ast.Name)}
    attributes = {node.attr for node in ast.walk(function) if isinstance(node, ast.Attribute)}
    problems = []
    if "reason_for_kind" in names | attributes:
        problems.append("calls the leaf function reason_for_kind")
    for needed in ("map_aggregation", "fetch", "AggregationResult", "SourceResult", "status_for_error_kind"):
        if needed not in names | attributes:
            problems.append(f"does not reference {needed}")
    loops = [node for node in ast.walk(function) if isinstance(node, ast.For) and isinstance(node.target, ast.Name) and node.target.id == "kind"]
    if len(loops) != 1 or not isinstance(loops[0].iter, ast.Name) or loops[0].iter.id != "SourceErrorKind":
        problems.append("must iterate over every member of SourceErrorKind")
    if any(isinstance(node, (ast.Continue, ast.Break)) for node in ast.walk(function)):
        problems.append("must not skip a kind")
    reasons = {"http_error", "rate_limited", "parse_error", "server_error", "timeout", "network", "unexpected"}
    for node in ast.walk(function):
        if isinstance(node, ast.Dict) and reasons & {item.value for item in [*node.keys, *node.values] if isinstance(item, ast.Constant) and isinstance(item.value, str)}:
            problems.append("contains a handwritten kind -> reason table")
    return problems


def _mutated(source: str, old: str, new: str) -> str:
    assert source.count(old) == 1, old
    return source.replace(old, new, 1)


def test_r4b_guard_the_real_op_e16b_source_has_the_required_production_structure():
    assert e16b_source_problems(IN_HOST.read_text(encoding="utf-8")) == []
    leftover = _function(IN_HOST.read_text(encoding="utf-8"), "op_enumerations")
    assert "reason_for_kind" not in {node.attr for node in ast.walk(leftover) if isinstance(node, ast.Attribute)}


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ("                            value = await provider.fetch(query)\n", "                            value = outcome_reason_for_kind = kind\n"),
        ("                    for kind in SourceErrorKind:\n", "                    for kind in list(SourceErrorKind)[1:]:\n"),
        ("                    for kind in SourceErrorKind:\n", "                    for kind in SourceErrorKind:\n                        if kind is SourceErrorKind.BLOCKED:\n                            continue\n"),
        ("                        kinds[kind.name] = row\n", "                        kinds[kind.name] = {\"BLOCKED\": \"http_error\", \"TIMEOUT\": \"timeout\"}\n"),
        ("                        results = _e16b_results(kind, SourceResult, SourceStatus, SourceErrorKind, source_result_module.status_for_error_kind)\n",
         "                        results = _e16b_results(kind, SourceResult, SourceStatus, SourceErrorKind, lambda kind: None)\n"),
    ],
    ids=["leaf_only_no_provider_fetch", "one_kind_omitted", "kind_skipped_by_continue", "handwritten_mapping_table", "status_derivation_bypassed"],
)
def test_r4b_guard_every_structural_defect_in_op_e16b_is_detected(old, new):
    source = IN_HOST.read_text(encoding="utf-8")
    assert e16b_source_problems(_mutated(source, old, new)) != []


def test_r4b_guard_inputs_use_core_public_constructors_not_handwritten_dicts():
    function = _function(IN_HOST.read_text(encoding="utf-8"), "_e16b_results")
    calls = {node.func.id for node in ast.walk(function) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}
    assert "SourceResult" in calls and not [node for node in ast.walk(function) if isinstance(node, ast.Dict)]


# ================================================================== R-5：HANDOFF 与 L0 / L1


def test_r5_handoff_records_the_governance_history_and_the_frozen_amendment_facts():
    text = HANDOFF.read_text(encoding="utf-8")
    for needle in ("U2-5", "TRIGGERED", AUTHORITY_HEAD, "201 Created", "ENVIRONMENTALLY_UNAVAILABLE", "E16-A", "E16-B", "12a", "symlink_privilege=false", "Technical Acceptance", "NOT YET", "NOT CLOSED"):
        assert needle in text, needle


@pytest.mark.parametrize(
    "stale",
    ["U2-1..U2-12 均未触发", "Authority Escalation     : NONE", "无法由传输层诱发的成员", "real-host symlink PASS", "LEVEL 1 PASS", "TECHNICALLY ACCEPTED", "S3 follow-up（docs-only）"],
)
def test_r5_handoff_has_no_stale_or_overclaiming_statement(stale):
    assert stale not in HANDOFF.read_text(encoding="utf-8")


def test_the_reconciliation_does_not_change_the_l0_core_wheel_or_the_l1_plugin_zip_input_bytes():
    import json

    artifacts = json.loads(MATRIX.read_text(encoding="utf-8"))["artifacts"]
    assert artifacts["core_wheel_sha256"] == L0_CORE_WHEEL_SHA256
    assert artifacts["plugin_zip_sha256"] == L1_PLUGIN_ZIP_SHA256


def test_the_synthetic_matrix_used_by_the_validator_tests_is_valid_and_carries_the_new_evidence(gate):
    document = synthetic_matrix(ARTIFACTS)
    assert gate.validate_matrix(document) == []
    assert "e16" in document["parity"] and sum(1 for case in document["core_admission"]["cases"] if case["observed"] == "ENVIRONMENTALLY_UNAVAILABLE") == 4


# ================================================================== 范围门：b8480e74..HEAD


PREFIX = "fc2-organizer/"
#: 本轮唯一被授权修改的证据面（任务书第 4 节）；``tests/amane_compat/`` 内的修改只为 evidence schema / witness / validator。
RECONCILIATION_ALLOWED = (
    r"tools/run_amane_compat_gate\.py",
    r"tools/build_amane_release\.py",  # P5-C2-L1-01 R1：明确授权 direct finalize 安全门
    r"tests/amane_compat/.+",
    r"docs/acceptance/evidence/P5_C2_COMPATIBILITY_MATRIX\.json",
    r"docs/review/P5_C2_HANDOFF\.md",
)
#: 零 diff：产品实现、L0 / L1 输入文件、其它构建器、P5-C1、权威文件、治理文件。
RECONCILIATION_ZERO_DIFF = (
    r"src/.+",
    r"adapters/amane/.+",
    r"tools/(build_core_wheel|compare_amane_api|prepare_amane_hosts|amane_api_manifest|build_amane_plugin_zip|run_amane_host_witness)\.py",
    r"pyproject\.toml",
    r"tests/(?!amane_compat/).+",
    r"docs/specifications/.+",
    r"docs/P5_C[12]_CONSTRUCTION_PLAN\.md",
    r"docs/review/P5_C1_.+",
    r"docs/acceptance/evidence/P5_C1_.+",
    r"docs/PROJECT_GOVERNANCE_ACCELERATION\.md",
)


def _git(*args: str) -> str:
    completed = subprocess.run(["git", "-C", str(REPO), *args], capture_output=True, text=True, encoding="utf-8", check=False)
    assert completed.returncode == 0, f"git {' '.join(args)} failed: {completed.stderr.strip()}"
    return completed.stdout


def _changed_since_authority() -> list[str]:
    committed = [line for line in _git("diff", "--name-only", f"{AUTHORITY_HEAD}..HEAD").splitlines() if line.strip()]
    working = [line[3:].strip().strip('"') for line in _git("status", "--porcelain=v1", "--untracked-files=all").splitlines()]
    return sorted({name[len(PREFIX):] if name.startswith(PREFIX) else name for name in [*committed, *working]})


def test_the_authority_head_is_reachable_and_an_ancestor_of_head():
    _git("cat-file", "-e", f"{AUTHORITY_HEAD}^{{commit}}")
    completed = subprocess.run(["git", "-C", str(REPO), "merge-base", "--is-ancestor", AUTHORITY_HEAD, "HEAD"], capture_output=True, check=False)
    assert completed.returncode == 0


def test_the_reconciliation_diff_is_limited_to_the_authorised_evidence_surface():
    outside = [name for name in _changed_since_authority() if not any(re.fullmatch(pattern, name) for pattern in RECONCILIATION_ALLOWED)]
    assert outside == [], f"files outside the authorised evidence surface: {outside}"


def test_the_reconciliation_leaves_product_builders_authority_and_governance_files_at_zero_diff():
    touched = [name for name in _changed_since_authority() if any(re.fullmatch(pattern, name) for pattern in RECONCILIATION_ZERO_DIFF)]
    assert touched == [], f"frozen files changed: {touched}"


# ================================================================== 场景完成语义：阶段中断 -> 未完成场景 false -> 不能 SUPPORTED -> validator 拒绝 -> finalize 拒绝


class _FakeHostRun:
    """``complete_scenarios`` / ``scenario_passes`` / ``host_row`` 只读取这些属性。"""

    def __init__(self, gate, form="source", phases=()):
        import types

        self.results = {scenario_id: gate.Scenario(scenario_id) for scenario_id in gate.SCENARIO_IDS}
        self.completed_phases = set(phases)
        self.extras = {}
        self.spec = types.SimpleNamespace(
            label="a-src", coordinate_id="SC-03", form=form, tag="v0.15.0", tag_object="cd" * 20, peeled_commit="45" * 20, release_version="0.15.0",
            requires_python=">=3.14", plugin_api_version="1", python_version="3.14.7", platform="windows-x64", api_fingerprint_sha256="ab" * 32,
            adapter_used_subset_fingerprint_sha256="ab" * 32, deps_lock_sha256="ab" * 32,
        )


def test_a_scenario_is_not_pass_at_creation_and_only_pass_after_it_is_really_completed(gate):
    scenario = gate.Scenario("HC-04")
    assert scenario.failures == [] and scenario.completed is False and scenario.passed is False  # “没有失败记录”不是通过
    scenario.complete()
    assert scenario.passed is True and scenario.result()["passed"] is True
    failing = gate.Scenario("HC-04")
    failing.check(False, "x")
    failing.complete()
    assert failing.passed is False


def test_the_scenario_phase_table_covers_hc_01_to_hc_19_and_only_known_phases(gate):
    assert set(gate.SCENARIO_PHASES) == set(gate.SCENARIO_IDS)
    assert all(set(phases) <= gate.KNOWN_PHASES and phases for phases in gate.SCENARIO_PHASES.values())
    run_host = _function(GATE.read_text(encoding="utf-8"), "run_host")
    guarded_names = {node.args[0].value for node in ast.walk(run_host) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "guarded"}
    assert guarded_names == set(gate.KNOWN_PHASES)  # 表里的阶段名必须就是 run_host 真正执行并登记的阶段名
    assert gate.required_phases("HC-19", "source") == gate.required_phases("HC-19", "frozen-desktop") | {"admission"}
    assert "admission" not in gate.required_phases("HC-18", "frozen-desktop")


def test_an_aborted_phase_leaves_every_scenario_that_depends_on_it_false_even_without_a_recorded_failure(gate):
    run = _FakeHostRun(gate, phases={"failures", "success", "core_upgrade", "admission"})  # own_stack 被中断
    gate.complete_scenarios(run)
    assert all(not run.results[scenario_id].failures for scenario_id in gate.SCENARIO_IDS)  # 没有任何失败记录（这正是原先被误判为 PASS 的情形）
    incomplete = {scenario_id for scenario_id in gate.SCENARIO_IDS if not run.results[scenario_id].passed}
    assert incomplete == {"HC-04", "HC-05", "HC-08", "HC-17", "HC-18"}
    assert run.results["HC-01"].passed and run.results["HC-10"].passed and run.results["HC-19"].passed
    assert gate.scenario_passes(run, "HC-01") is True and gate.scenario_passes(run, "HC-04") is False


@pytest.mark.parametrize("missing", ["failures", "success", "core_upgrade", "admission"])
def test_every_single_aborted_phase_is_detected(gate, missing):
    run = _FakeHostRun(gate, phases=gate.KNOWN_PHASES - {missing})
    gate.complete_scenarios(run)
    assert [scenario_id for scenario_id in gate.SCENARIO_IDS if not run.results[scenario_id].passed] != []
    frozen = _FakeHostRun(gate, form="frozen-desktop", phases=gate.KNOWN_PHASES - {missing})
    gate.complete_scenarios(frozen)
    assert (missing == "admission") == all(frozen.results[scenario_id].passed for scenario_id in gate.SCENARIO_IDS)  # 冻结包没有 admission 阶段


def test_a_fully_completed_run_passes_all_nineteen_scenarios(gate):
    run = _FakeHostRun(gate, phases=gate.KNOWN_PHASES)
    gate.complete_scenarios(run)
    assert all(run.results[scenario_id].passed for scenario_id in gate.SCENARIO_IDS)


def test_the_host_row_reports_false_for_incomplete_and_never_started_scenarios(gate):
    run = _FakeHostRun(gate, phases={"failures", "success", "core_upgrade", "admission"})
    del run.results["HC-17"]  # 阶段在该场景创建之前就中断
    gate.complete_scenarios(run)
    row = gate.host_row(run)
    passed = {item["id"]: item["passed"] for item in row["scenarios"]}
    assert [scenario_id for scenario_id, value in passed.items() if not value] == ["HC-04", "HC-05", "HC-08", "HC-17", "HC-18"]
    assert len(row["scenarios"]) == 19


def test_phase_functions_abort_by_raising_and_never_return_early():
    tree = ast.parse(GATE.read_text(encoding="utf-8"))
    for function in (node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name.startswith("phase_")):
        direct_returns = []

        class Visitor(ast.NodeVisitor):
            def visit_FunctionDef(self, node):  # noqa: N802 - 不进入嵌套函数
                if node is function:
                    self.generic_visit(node)

            def visit_Return(self, node):  # noqa: N802
                direct_returns.append(node.lineno)

        Visitor().visit(function)
        assert direct_returns == [], f"{function.name} returns early at {direct_returns}: an aborted phase must raise, never look like a normal end"


def test_a_phase_counts_as_completed_only_when_it_returned_normally_and_only_complete_scenarios_marks_a_scenario():
    tree = ast.parse(GATE.read_text(encoding="utf-8"))
    guarded = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == "guarded")
    attempt = next(node for node in ast.walk(guarded) if isinstance(node, ast.Try))
    assert any("completed_phases" in ast.dump(item) for item in attempt.orelse), "the phase must be registered in the try's else branch (normal return only)"
    assert not any("completed_phases" in ast.dump(handler) for handler in attempt.handlers)
    marks = [(function.name, node) for function in ast.walk(tree) if isinstance(function, ast.FunctionDef)
             for node in ast.walk(function) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "complete"]
    assert {name for name, _node in marks} == {"complete_scenarios"}, "Scenario.complete() may only be called by complete_scenarios"


# ---- scenario false -> coordinate not SUPPORTED -> validator rejects -> finalize rejects


def _interrupt(matrix, how):
    """用 synthetic MATRIX 模拟“必需宿主 a-src 的某个场景因阶段中断而没有 PASS”。"""
    host = next(item for item in matrix["hosts"] if item["label"] == "a-src")
    if how == "scenario_false":
        host["scenarios"][3]["passed"] = False
    elif how == "scenarios_missing":
        host["scenarios"] = host["scenarios"][:3]
    else:
        raise AssertionError(how)


def _rederive(matrix, gate):
    matrix["status"] = [gate.derive_status(spec["id"], matrix["hosts"], parity_equal=True, stable_peeled_commit="0a" * 20) for spec in gate.SUPPORT_COORDINATES]


@pytest.mark.parametrize("how", ["scenario_false", "scenarios_missing"])
def test_the_chain_incomplete_scenario_blocks_the_coordinate_the_validator_and_finalize(gate, how):
    matrix = synthetic_matrix(ARTIFACTS)
    assert gate.finalize_problems(matrix) == []
    _interrupt(matrix, how)
    # 1) 该坐标不可能是 SUPPORTED（SC-03 = a-src）
    assert gate.derive_status("SC-03", matrix["hosts"], parity_equal=True, stable_peeled_commit="0a" * 20)["status"] == "BLOCKED"
    # 2) 声称它 SUPPORTED 的 MATRIX 被校验器拒绝；finalize 同样拒绝
    assert any("SUPPORTED is not backed" in problem for problem in gate.validate_matrix(matrix))
    assert gate.finalize_problems(matrix) != []
    # 3) 诚实地标成 BLOCKED 的 MATRIX 自洽，但 finalize 仍然拒绝
    _rederive(matrix, gate)
    assert [row["status"] for row in matrix["status"] if row["coordinate_id"] == "SC-03"] == ["BLOCKED"]
    assert gate.validate_matrix(matrix) == []
    problems = gate.finalize_problems(matrix)
    assert problems and any("SC-03" in problem for problem in problems) and any("a-src" in problem for problem in problems)


def test_finalize_refuses_a_matrix_without_all_four_required_hosts_or_without_parity(gate):
    matrix = synthetic_matrix(ARTIFACTS)
    matrix["hosts"] = [host for host in matrix["hosts"] if host["label"] != "b-win"]
    _rederive(matrix, gate)
    assert any("b-win" in problem for problem in gate.finalize_problems(matrix))
    matrix = synthetic_matrix(ARTIFACTS)
    matrix["parity"]["required_pairs"][0].update({"equal": False, "sha256_b": "cd" * 32})
    assert any("parity" in problem for problem in gate.finalize_problems(matrix))
    matrix = synthetic_matrix(ARTIFACTS)
    matrix["final_artifacts"] = {"compatibility_json_sha256": "11" * 32, "sha256sums_sha256": "22" * 32, "release_bundle_sha256": "33" * 32}
    assert any("Part A only" in problem for problem in gate.finalize_problems(matrix))


def _stage1(tmp_path, core_wheel):
    release = load_tool("build_amane_release.py")
    stage1 = release.build_stage1(REPO, core_wheel)
    directory = tmp_path / "l1"
    directory.mkdir()
    for name, data in stage1["files"].items():
        (directory / name).write_bytes(data)
    return stage1, directory


def _finalize(gate, tmp_path, core_wheel, matrix, directory):
    import json

    part_a = tmp_path / "partA.json"
    part_a.write_text(json.dumps(matrix), encoding="utf-8")
    out = tmp_path / "out"
    code = gate.main(["finalize", "--core-wheel", str(core_wheel), "--stage1-dir", str(directory), "--matrix", str(part_a), "--out", str(out)])
    return code, out


def test_finalize_cli_writes_l2_l3_l4_and_part_b_for_a_complete_green_part_a(gate, core_wheel, tmp_path):
    import json

    stage1, directory = _stage1(tmp_path, core_wheel)
    code, out = _finalize(gate, tmp_path, core_wheel, synthetic_matrix(stage1["artifacts"]), directory)
    assert code == 0
    assert sorted(path.name for path in out.iterdir()) == ["COMPATIBILITY.json", "P5_C2_COMPATIBILITY_MATRIX.json", "SHA256SUMS", "ffcc-amane-release-0.1.0.zip"]
    final = json.loads((out / "P5_C2_COMPATIBILITY_MATRIX.json").read_text(encoding="utf-8"))
    assert gate.validate_matrix(final) == []
    assert final["final_artifacts"]["compatibility_json_sha256"] == gate.sha256_hex((out / "COMPATIBILITY.json").read_bytes())
    assert final["final_artifacts"]["release_bundle_sha256"] == gate.sha256_hex((out / "ffcc-amane-release-0.1.0.zip").read_bytes())


@pytest.mark.parametrize("how", ["scenario_false", "scenarios_missing"])
def test_finalize_cli_refuses_an_interrupted_part_a_and_writes_nothing(gate, core_wheel, tmp_path, how):
    stage1, directory = _stage1(tmp_path, core_wheel)
    matrix = synthetic_matrix(stage1["artifacts"])
    _interrupt(matrix, how)
    code, out = _finalize(gate, tmp_path, core_wheel, matrix, directory)  # 声称 SUPPORTED 但场景未通过
    assert code == 1 and not out.exists()
    _rederive(matrix, gate)  # 诚实的 BLOCKED 也不能 finalize
    code, out = _finalize(gate, tmp_path, core_wheel, matrix, directory)
    assert code == 1 and not out.exists()


def test_finalize_cli_refuses_part_a_whose_artifacts_are_not_the_rebuilt_ones(gate, core_wheel, tmp_path):
    stage1, directory = _stage1(tmp_path, core_wheel)
    matrix = synthetic_matrix(stage1["artifacts"])
    matrix["artifacts"]["plugin_zip_sha256"] = "00" * 32
    code, out = _finalize(gate, tmp_path, core_wheel, matrix, directory)
    assert code == 1 and not out.exists()
