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
    r"tests/amane_compat/.+",
    r"docs/acceptance/evidence/P5_C2_COMPATIBILITY_MATRIX\.json",
    r"docs/review/P5_C2_HANDOFF\.md",
)
#: 零 diff：产品实现、L0 / L1 输入文件、构建器、P5-C1、权威文件、治理文件。
RECONCILIATION_ZERO_DIFF = (
    r"src/.+",
    r"adapters/amane/.+",
    r"tools/(build_core_wheel|build_amane_release|compare_amane_api|prepare_amane_hosts|amane_api_manifest|build_amane_plugin_zip|run_amane_host_witness)\.py",
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
