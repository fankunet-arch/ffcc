"""P5-C2：Amane 兼容见证门（合同第 11、14 节）。顶层只依赖标准库。

本文件分两部分：

1. **纯逻辑**（S1）：支持坐标表（第 7.2 节）、状态推导、``P5_C2_COMPATIBILITY_MATRIX.json`` 的 schema 与自洽规则校验
   （E23 / E24 / M2-16）、确定性渲染。主进程测试直接 import 本部分。
2. **宿主运行器**（S2）：对真实 Amane 服务进程执行 HC-01..HC-19（见本文件下半部分 ``run_*``）。

用法（校验已提交的矩阵）::

    python tools/run_amane_compat_gate.py --validate docs/acceptance/evidence/P5_C2_COMPATIBILITY_MATRIX.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

SCHEMA_VERSION = 1
SCENARIO_IDS = tuple(f"HC-{index:02d}" for index in range(1, 20))
PLATFORM_WINDOWS = "windows-x64"
HASH64 = re.compile(r"[0-9a-f]{64}")

#: 合同第 7.2 节的支持坐标表（``COMPATIBILITY.json`` / ``INSTALL.zh-CN.md`` / E24 使用同一份）。
SUPPORT_COORDINATES = (
    {"id": "SC-01", "amane_version": "v0.15.0", "host_form": "frozen-desktop", "platform": PLATFORM_WINDOWS, "claim_class": "deployment", "role": "required"},
    {"id": "SC-02", "amane_version": "v0.18.0", "host_form": "frozen-desktop", "platform": PLATFORM_WINDOWS, "claim_class": "deployment", "role": "required"},
    {"id": "SC-03", "amane_version": "v0.15.0", "host_form": "source", "platform": PLATFORM_WINDOWS, "claim_class": "integration", "role": "required"},
    {"id": "SC-04", "amane_version": "v0.18.0", "host_form": "source", "platform": PLATFORM_WINDOWS, "claim_class": "integration", "role": "required"},
    {"id": "SC-05", "amane_version": "main", "host_form": "source", "platform": PLATFORM_WINDOWS, "claim_class": "informational", "role": "informational"},
    {"id": "SC-06", "amane_version": "v0.16.1|v0.17.0", "host_form": "source", "platform": PLATFORM_WINDOWS, "claim_class": "informational", "role": "informational"},
    {"id": "SC-07", "amane_version": "v0.15.0|v0.18.0", "host_form": "frozen-desktop", "platform": "macos", "claim_class": "unverified", "role": "unverified"},
    {"id": "SC-08", "amane_version": "v0.15.0|v0.18.0", "host_form": "source", "platform": "linux", "claim_class": "unverified", "role": "unverified"},
    {"id": "SC-09", "amane_version": "v0.15.0|v0.18.0", "host_form": "docker", "platform": "linux", "claim_class": "unverified", "role": "unverified"},
)
REQUIRED_COORDINATES = ("SC-01", "SC-02", "SC-03", "SC-04")
UNVERIFIED_COORDINATES = ("SC-07", "SC-08", "SC-09")
STATUS_WORDS = frozenset({"SUPPORTED", "CONDITIONALLY_SUPPORTED", "BLOCKED", "UNVERIFIED", "INFORMATIONAL", "IDENTICAL_TO_STABLE"})
PLATFORMS_UNVERIFIED = ["macos", "linux", "docker"]
DIFF_WHITELIST = tuple(f"DIFF-{index:02d}" for index in range(1, 8))
PART_A_KEYS = ("schema_version", "tool", "policy", "hosts", "artifacts", "parity", "status", "platforms_unverified", "core_admission")
PART_B_KEYS = ("final_artifacts",)
ARTIFACT_KEYS = ("plugin_zip_sha256", "core_wheel_sha256", "core_tree_sha256", "adapter_tree_sha256", "impl_tree_sha256", "shim_tree_sha256", "pin_sha256")
FINAL_ARTIFACT_KEYS = ("compatibility_json_sha256", "sha256sums_sha256", "release_bundle_sha256")
HOST_KEYS = (
    "label", "coordinate_id", "role", "form", "tag", "tag_object", "peeled_commit", "release_version", "requires_python",
    "plugin_api_version", "python_version", "platform", "api_fingerprint_sha256", "adapter_used_subset_fingerprint_sha256",
    "deps_lock_sha256", "identical_to_stable", "scenarios",
)
_VOLATILE = re.compile(r"[A-Za-z]:\\|/(?:Users|home|tmp|var)/|\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}|127\.0\.0\.1:\d+|localhost:\d+")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def render(document: dict) -> str:
    """确定性渲染：排序键、``ensure_ascii``、LF。"""
    return json.dumps(document, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def split_parts(document: dict) -> tuple[dict, dict]:
    """(Part A, Part B)。"""
    return {key: document[key] for key in PART_A_KEYS if key in document}, {key: document[key] for key in PART_B_KEYS if key in document}


def coordinate(coordinate_id: str) -> dict:
    return next(item for item in SUPPORT_COORDINATES if item["id"] == coordinate_id)


def derive_status(coordinate_id: str, hosts: list[dict], *, parity_equal: bool, stable_peeled_commit: str) -> dict:
    """由见证推导一个坐标的状态（key = 坐标；版本状态不得覆盖平台状态）。"""
    spec = coordinate(coordinate_id)
    base = {"coordinate_id": coordinate_id, "amane_version": spec["amane_version"], "host_form": spec["host_form"], "platform": spec["platform"]}
    host = next((item for item in hosts if item["coordinate_id"] == coordinate_id), None)
    if coordinate_id in UNVERIFIED_COORDINATES:
        return {**base, "status": "UNVERIFIED", "reason": "no verification environment; not part of the support claim"}
    if coordinate_id == "SC-05":
        if host is not None and host["peeled_commit"] == stable_peeled_commit:
            return {**base, "status": "IDENTICAL_TO_STABLE", "reason": "main resolves to the same commit as the current stable release; not an independent witness"}
        if host is None:
            return {**base, "status": "UNVERIFIED", "reason": "no main witness was run"}
        return {**base, "status": "INFORMATIONAL", "reason": "informational compatibility witness; failures do not block"}
    if coordinate_id == "SC-06":
        return {**base, "status": "INFORMATIONAL" if host is not None else "UNVERIFIED", "reason": "optional informational witness"}
    if host is None:
        return {**base, "status": "BLOCKED", "reason": "required witness missing"}
    failed = [item["id"] for item in host["scenarios"] if not item["passed"]]
    missing = [name for name in SCENARIO_IDS if name not in {item["id"] for item in host["scenarios"]}]
    if failed or missing or not parity_equal:
        return {**base, "status": "BLOCKED", "reason": f"failed={failed} missing={missing} parity_equal={parity_equal}"}
    return {**base, "status": "SUPPORTED", "reason": "HC-01..HC-19 passed and cross-version parity holds on this coordinate"}


def _is_hash(value: object) -> bool:
    return isinstance(value, str) and HASH64.fullmatch(value) is not None


def _walk_strings(value: object):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, item in value.items():
            yield key
            yield from _walk_strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_strings(item)


# ------------------------------------------------------------------------------------------------ 证据规则（A1：E16 双轨 / 符号链接 / HC-12）
# 以下全是**纯逻辑**：期望值是对 P5-C1 冻结表 F / 表 G / 合同第 17.3 节与 P5-C2 合同 A1 的**独立转录**，不读取、不调用被测实现。

ENV_UNAVAILABLE = "ENVIRONMENTALLY_UNAVAILABLE"
#: ``core_admission.cases[].observed`` 的**唯一**额外取值只能用于这个子项，并且必须与 ``symlink_privilege == false`` 同时出现（A1-3）。
SYMLINK_CASE = "sidecar_symlink_to_the_exact_wheel"
REQUIRED_LABELS = ("a-src", "b-src", "a-win", "b-win")

#: P5-C1 表 G：每个 Core ``SourceErrorKind`` 成员 -> ``FailureReason`` 字符串；``None`` = 非运行性（``NOT_FOUND`` -> 中立 no-match -> 宿主 ``None``）。
#: 键 = 枚举成员名（16 个；缺一 = E16-B FAIL）。
E16B_EXPECTED_REASON = {
    "NOT_FOUND": None,
    "BLOCKED": "http_error",
    "RATE_LIMITED": "rate_limited",
    "NETWORK_ERROR": "network",
    "PARSE_ERROR": "parse_error",
    "INVALID_RESPONSE": "parse_error",
    "TIMEOUT": "timeout",
    "CONNECTION_ERROR": "network",
    "DECODE_ERROR": "network",
    "REDIRECT_ERROR": "network",
    "SOURCE_DEADLINE": "timeout",
    "CIRCUIT_OPEN": "network",
    "HTTP_SERVER_ERROR": "server_error",
    "RESPONSE_TOO_LARGE": "parse_error",
    "ADAPTER_EXCEPTION": "unexpected",
    "RESULT_CONTRACT_MISMATCH": "unexpected",
}
E16B_SOURCES = ("fc2db_net", "javdb", "av123")
#: E16-A（A1-4）：4358b3d 的受控传输栈**端到端实际观测**到的 kind 集合 ``K_A``（7 个）；其余 9 个未被观测到（不是“不可诱发”的证明）。
E16A_OBSERVED_KINDS = ("blocked", "connection_error", "http_server_error", "invalid_response", "parse_error", "rate_limited", "source_deadline")
E16A_FORBIDDEN_LABEL_PREFIX = "kind_"  # 旧标签（kind_xxx）会虚称一个未必被观测到的 kind；E16-A 用例名只描述刺激
_DETAIL_PAIR = re.compile(r"(?:^|; )[A-Za-z0-9_]+=([a-z_]+)")


def e16b_expected_row(name: str) -> dict:
    """一个 kind 的期望 {result_category, failure_reason, detail}（detail 格式 = P5-C1 合同第 17.3 节；混合失败夹具：首个来源 = 该 kind，其余 = not_found）。"""
    reason = E16B_EXPECTED_REASON[name]
    if reason is None:
        return {"result_category": "None", "failure_reason": None, "detail": None}
    pairs = [f"{E16B_SOURCES[0]}={name.lower()}", *(f"{source}=not_found" for source in E16B_SOURCES[1:])]
    return {"result_category": "SourceError", "failure_reason": reason, "detail": "FC2 lookup failed: " + "; ".join(pairs)}


def kinds_from_detail(detail: object) -> list[str]:
    """从 ``FC2 lookup failed: <source_id>=<kind>; ...`` 读出**实际观测**的 kind 词汇（排序、去重；排除“来源回答了没有这部影片”的 ``not_found``）。"""
    if not isinstance(detail, str) or not detail.startswith("FC2 lookup failed: "):
        return []
    body = detail[len("FC2 lookup failed: "):]
    return sorted({kind for kind in _DETAIL_PAIR.findall(body) if kind != "not_found"})


def e16a_table(cases: dict) -> dict:
    """E16-A：每个用例记录 ``actual_source_error_kind``（实际观测到的 kind；非 SourceError 的结果 = 空列表）。"""
    table = {}
    for case_id, item in sorted(cases.items()):
        is_error = item.get("class") == "SourceError"
        table[case_id] = {
            "result_class": item.get("class"), "failure_reason": item.get("reason") if is_error else None,
            "actual_source_error_kind": kinds_from_detail(item.get("detail")) if is_error else [],
        }
    return table


def evaluate_e16a(table: object) -> list[str]:
    if not isinstance(table, dict) or not table:
        return ["E16-A: no per-case table"]
    problems = []
    observed: set[str] = set()
    for case_id, row in table.items():
        kinds = row.get("actual_source_error_kind") if isinstance(row, dict) else None
        if not isinstance(kinds, list):
            problems.append(f"E16-A {case_id}: actual_source_error_kind must be recorded")
            continue
        if case_id.startswith(E16A_FORBIDDEN_LABEL_PREFIX):
            problems.append(f"E16-A {case_id}: case labels must describe the stimulus and never claim a SourceErrorKind")
        observed |= set(kinds)
    if sorted(observed) != sorted(E16A_OBSERVED_KINDS):
        problems.append(f"E16-A observed kinds {sorted(observed)} differ from the frozen K_A {sorted(E16A_OBSERVED_KINDS)}")
    return problems


def evaluate_e16b(result: object) -> list[str]:
    """E16-B 单宿主判据：16 个成员齐全；每个成员的 {结果类别, FailureReason, detail} == 期望；每个成员都**实际**经过生产映射与生产 provider 转换。"""
    if not isinstance(result, dict) or not isinstance(result.get("kinds"), dict) or not isinstance(result.get("production_path"), dict):
        return ["E16-B: no result"]
    problems = []
    kinds, path = result["kinds"], result["production_path"]
    for name in sorted(set(E16B_EXPECTED_REASON) - set(kinds)):
        problems.append(f"E16-B: SourceErrorKind.{name} is missing")
    for name in sorted(set(kinds) - set(E16B_EXPECTED_REASON)):
        problems.append(f"E16-B: unexpected member {name}")
    for name in sorted(set(E16B_EXPECTED_REASON) & set(kinds)):
        if kinds[name] != e16b_expected_row(name):
            problems.append(f"E16-B {name}: observed {kinds[name]!r}, expected {e16b_expected_row(name)!r}")
        row = path.get(name) or {}
        operational = E16B_EXPECTED_REASON[name] is not None
        expected_path = {
            "core_objects_built_with_public_constructors": True, "engine_calls": 1, "engine_called_with_canonical": True,
            "map_aggregation_calls": 1, "map_aggregation_input_is_the_core_object": True,
            "neutral_result_type": "AdapterFailure" if operational else "AdapterNoMatch",
            "reason_is_host_failure_reason": True if operational else None, "provider_class": "_Fc2MetadataProvider",
        }
        if row != expected_path:
            problems.append(f"E16-B {name}: the production mapping / provider path was not exercised as required: {row!r}")
    return problems


def validate_e16(e16: object, required_labels: set[str]) -> list[str]:
    """Matrix Part A ``parity.e16`` 的 schema 与自洽规则（缺 kind / 缺必需宿主 / NOT_FOUND 类别错误 / 旧标签虚称均被拒绝）。"""
    if not isinstance(e16, dict) or set(e16) != {"e16_a", "e16_b"}:
        return ["parity.e16 must hold exactly e16_a and e16_b"]
    problems = []
    part_b, part_a = e16["e16_b"], e16["e16_a"]
    if not isinstance(part_b, dict) or set(part_b) != {"kind_count", "outcomes", "per_host_sha256", "equal", "production_path_verified_on_hosts"}:
        problems.append("parity.e16.e16_b has the wrong keys")
    else:
        outcomes = part_b["outcomes"]
        if not isinstance(outcomes, dict):
            problems.append("parity.e16.e16_b.outcomes must be an object")
        else:
            problems += [f"parity.e16.e16_b: SourceErrorKind.{name} is missing" for name in sorted(set(E16B_EXPECTED_REASON) - set(outcomes))]
            problems += [f"parity.e16.e16_b: unexpected member {name}" for name in sorted(set(outcomes) - set(E16B_EXPECTED_REASON))]
            for name in sorted(set(E16B_EXPECTED_REASON) & set(outcomes)):
                if outcomes[name] != e16b_expected_row(name):
                    problems.append(f"parity.e16.e16_b {name}: {outcomes[name]!r} differs from the frozen P5-C1 mapping {e16b_expected_row(name)!r}")
            if part_b["kind_count"] != len(E16B_EXPECTED_REASON) or len(outcomes) != len(E16B_EXPECTED_REASON):
                problems.append("parity.e16.e16_b must cover all 16 SourceErrorKind members")
            hosts = part_b["per_host_sha256"]
            if not isinstance(hosts, dict) or set(hosts) != required_labels:
                problems.append("parity.e16.e16_b must cover every required host (a-src, b-src, a-win, b-win)")
            elif part_b["equal"] is not True or any(value != canonical_hash(outcomes) for value in hosts.values()):
                problems.append("parity.e16.e16_b: the four required hosts must produce identical normalized outcomes")
            if part_b["production_path_verified_on_hosts"] != sorted(required_labels):
                problems.append("parity.e16.e16_b: the production mapping / provider path must be verified on every required host")
    if not isinstance(part_a, dict) or set(part_a) != {"observed_kinds", "cases", "per_host_sha256", "equal"}:
        problems.append("parity.e16.e16_a has the wrong keys")
    else:
        problems += [f"parity.e16.e16_a: {item}" for item in evaluate_e16a(part_a["cases"])]
        if part_a["observed_kinds"] != sorted(E16A_OBSERVED_KINDS):
            problems.append("parity.e16.e16_a.observed_kinds must be exactly the frozen K_A")
        hosts = part_a["per_host_sha256"]
        if not isinstance(hosts, dict) or set(hosts) != required_labels:
            problems.append("parity.e16.e16_a must cover every required host (a-src, b-src, a-win, b-win)")
        elif part_a["equal"] is not True or any(value != canonical_hash(part_a["cases"]) for value in hosts.values()):
            problems.append("parity.e16.e16_a: the four required hosts must produce identical normalized results")
    return problems


def validate_symlink_rows(cases: list[dict], required_labels: set[str]) -> list[str]:
    """A1-3：``ENVIRONMENTALLY_UNAVAILABLE`` 只对符号链接子项合法，并且必须与 ``symlink_privilege == false`` 同时出现；每个必需宿主恰有一行。"""
    problems = []
    seen: dict[str, int] = {}
    for item in cases:
        label, _, name = item["id"].partition(":")
        is_symlink = name == SYMLINK_CASE
        if item["observed"] == ENV_UNAVAILABLE:
            if not is_symlink or item.get("symlink_privilege") is not False or item["expected"] != "FAIL":
                problems.append(f"core_admission {item['id']}: {ENV_UNAVAILABLE} is legal only for the symlink sub-case and only together with symlink_privilege=false")
        elif is_symlink and item.get("symlink_privilege") is not True:
            problems.append(f"core_admission {item['id']}: an executed symlink row must record symlink_privilege=true (otherwise it is {ENV_UNAVAILABLE})")
        elif not is_symlink and "symlink_privilege" in item:
            problems.append(f"core_admission {item['id']}: symlink_privilege belongs to the symlink sub-case only")
        if is_symlink:
            seen[label] = seen.get(label, 0) + 1
    if set(seen) != required_labels or any(count != 1 for count in seen.values()):
        problems.append("core_admission must hold exactly one symlink sub-case row for every required host")
    return problems


def validate_matrix(document: dict) -> list[str]:
    """schema + 自洽规则（E23 / E24 / M2-16）。返回问题列表（空 = 合格）。"""
    problems: list[str] = []
    extra = set(document) - set(PART_A_KEYS) - set(PART_B_KEYS)
    missing = [key for key in PART_A_KEYS if key not in document]
    if extra or missing:
        return [f"top-level keys: extra={sorted(extra)} missing={missing}"]
    if document["schema_version"] != SCHEMA_VERSION:
        problems.append("schema_version")
    if document["policy"].get("support_coordinates") != list(SUPPORT_COORDINATES):
        problems.append("policy.support_coordinates differs from the frozen coordinate table")
    if document["platforms_unverified"] != PLATFORMS_UNVERIFIED:
        problems.append("platforms_unverified must be exactly [macos, linux, docker]")
    artifacts = document["artifacts"]
    if sorted(artifacts) != sorted(ARTIFACT_KEYS) or not all(_is_hash(value) for value in artifacts.values()):
        problems.append("artifacts must hold exactly the 7 Level-0/1 sha256 fields")
    if "final_artifacts" in document:
        final = document["final_artifacts"]
        if sorted(final) != sorted(FINAL_ARTIFACT_KEYS) or not all(_is_hash(value) for value in final.values()):
            problems.append("final_artifacts must hold exactly the 3 outer sha256 fields")

    hosts = document["hosts"]
    labels = [host["label"] for host in hosts]
    if len(labels) != len(set(labels)):
        problems.append("duplicate host label")
    for host in hosts:
        if sorted(host) != sorted(HOST_KEYS):
            problems.append(f"host {host.get('label')}: unexpected keys")
            continue
        spec = coordinate(host["coordinate_id"]) if host["coordinate_id"] in {item["id"] for item in SUPPORT_COORDINATES} else None
        if spec is None:
            problems.append(f"host {host['label']}: unknown coordinate")
            continue
        if host["role"] != spec["role"] or host["form"] != spec["host_form"] or host["platform"] != spec["platform"]:
            problems.append(f"host {host['label']}: role / form / platform differ from coordinate {spec['id']}")
        if host["identical_to_stable"] and (host["scenarios"] or host["coordinate_id"] != "SC-05"):
            problems.append(f"host {host['label']}: IDENTICAL_TO_STABLE must not be counted as an independent witness")
        for field in ("api_fingerprint_sha256", "adapter_used_subset_fingerprint_sha256", "deps_lock_sha256"):
            if host[field] is not None and not _is_hash(host[field]):
                problems.append(f"host {host['label']}: {field}")
        for scenario in host["scenarios"]:
            if scenario["id"] not in SCENARIO_IDS or not isinstance(scenario["passed"], bool) or not _is_hash(scenario["observations_sha256"]):
                problems.append(f"host {host['label']}: malformed scenario {scenario.get('id')}")

    stable_commits = {host["peeled_commit"] for host in hosts if host["coordinate_id"] in ("SC-02", "SC-04")}
    stable = next(iter(stable_commits), "")
    pairs = document["parity"]["required_pairs"]
    parity_equal = bool(pairs) and all(pair["equal"] for pair in pairs)
    for pair in pairs:
        if pair["equal"] != (pair["sha256_a"] == pair["sha256_b"]):
            problems.append(f"parity pair {pair['a']}/{pair['b']}: equal flag disagrees with the hashes")
    if not set(document["parity"]["allowed_diffs_observed"]) <= set(DIFF_WHITELIST):
        problems.append("parity.allowed_diffs_observed contains a non-whitelisted difference")
    required_labels = {host["label"] for host in hosts if host.get("role") == "required"}
    if required_labels != set(REQUIRED_LABELS):
        problems.append("the four required hosts a-src / b-src / a-win / b-win must all be present")
    problems += validate_e16(document["parity"].get("e16"), required_labels)

    rows = document["status"]
    status_keys = {"coordinate_id", "amane_version", "host_form", "platform", "status", "reason"}
    if any(set(row) != status_keys for row in rows):
        return [*problems, "every status row must be keyed by coordinate (coordinate_id, amane_version, host_form, platform) with status and reason"]
    keyed = {row.get("coordinate_id"): row for row in rows}
    if len(keyed) != len(rows) or set(keyed) != {item["id"] for item in SUPPORT_COORDINATES}:
        problems.append("status must have exactly one row per coordinate SC-01..SC-09 (keyed by coordinate, never by version alone)")
        return problems
    for spec in SUPPORT_COORDINATES:
        row = keyed[spec["id"]]
        if (row["amane_version"], row["host_form"], row["platform"]) != (spec["amane_version"], spec["host_form"], spec["platform"]):
            problems.append(f"status {spec['id']}: (version, host_form, platform) differ from the coordinate table")
        if row["status"] not in STATUS_WORDS or not row.get("reason"):
            problems.append(f"status {spec['id']}: bad status word or empty reason")
            continue
        expected = derive_status(spec["id"], hosts, parity_equal=parity_equal, stable_peeled_commit=stable)
        if spec["id"] in REQUIRED_COORDINATES:
            if row["status"] == "SUPPORTED" and expected["status"] != "SUPPORTED":
                problems.append(f"status {spec['id']}: SUPPORTED is not backed by a fully passing required witness")
            if row["status"] == "CONDITIONALLY_SUPPORTED" and spec["id"] not in ("SC-02", "SC-04"):
                problems.append(f"status {spec['id']}: CONDITIONALLY_SUPPORTED is only a design default for SC-02 / SC-04")
            if row["status"] not in ("SUPPORTED", "CONDITIONALLY_SUPPORTED", "BLOCKED"):
                problems.append(f"status {spec['id']}: required coordinates may only be SUPPORTED / CONDITIONALLY_SUPPORTED / BLOCKED")
        elif row["status"] != expected["status"]:
            problems.append(f"status {spec['id']}: expected {expected['status']}, found {row['status']}")
    for spec_id in UNVERIFIED_COORDINATES:
        if keyed[spec_id]["status"] != "UNVERIFIED":
            problems.append(f"status {spec_id}: unverified platforms must stay UNVERIFIED")

    admission = document["core_admission"]
    if not _is_hash(admission["core_wheel_sha256"]) or admission["core_wheel_sha256"] != artifacts["core_wheel_sha256"]:
        problems.append("core_admission.core_wheel_sha256 must equal artifacts.core_wheel_sha256")
    problems += validate_symlink_rows(admission["cases"], required_labels)
    for item in admission["cases"]:
        if item["observed"] == ENV_UNAVAILABLE:
            if item["expected"] != "FAIL" or item["payload_executed"]:
                problems.append(f"core_admission {item['id']}: bad {ENV_UNAVAILABLE} row")
            continue  # 该子项没有被真实执行：不套用 observed == expected；替代证据由单元层 + M2-14 提供（A1-3）
        if item["expected"] not in ("PASS", "FAIL") or item["observed"] != item["expected"]:
            problems.append(f"core_admission {item['id']}: observed differs from expected")
        if item["expected"] == "FAIL" and not (item["sys_path_unchanged_on_fail"] and item["sys_modules_unchanged_on_fail"]) :
            problems.append(f"core_admission {item['id']}: failure left sys.path / sys.modules changed")
        if item["payload_executed"]:
            problems.append(f"core_admission {item['id']}: a payload was executed")
    for text in _walk_strings(document):
        if _VOLATILE.search(text):
            problems.append(f"volatile / local data in the matrix: {text[:60]!r}")
    return problems




# ====================================================================================================== S2：宿主运行器
# 以下代码只在“跑真实宿主”时使用（HC-01..HC-19）；纯逻辑部分（上文）不依赖它们。

import importlib.util
import io
import os
import shutil
import socket
import subprocess
import time
import urllib.error
import urllib.request
import uuid
import zipfile
from dataclasses import dataclass, field

REPO_ROOT = Path(__file__).resolve().parents[1]
HOST_SCRIPTS = REPO_ROOT / "tests" / "amane_compat" / "host_scripts"
PLUGIN_ID = "ffcc.fc2-metadata"
PROBE_ID = "ffcc.probe"
PROBE_MARK = "PROBE@@"
TOKEN = "ffcc-gate-token"
INSTALLED = 201  # POST /api/plugins 是创建资源：成功 = 201 Created（两个宿主版本相同）
READY_TIMEOUT = {"source": 180, "frozen-desktop": 90}
C1_MISSING_CORE_MESSAGE = (
    "插件导入失败: FC2 Metadata Core 未安装或版本不兼容：请在 Amane 所在的 Python 环境中安装 "
    "fc2-metadata-core（缺失模块：fc2_metadata_core）"
)
#: 合同第 8.3 节模板（网关**独立**硬编码；与 locator 的实现无共享代码）。
TEMPLATES = {
    "RESTART": "FC2 Metadata Core 已加载的版本与插件不配对（或无法验证）：请先卸载旧版插件并重启 Amane，再安装与之配对的新版（需要 Core {version}）",
    "UNVERIFIABLE": "FC2 Metadata Core 的来源不受支持或无法验证（已拒绝加载）：请把官方发布包中的 {wheel} 放入 <Amane 数据目录>/plugins/_ffcc_core/，不要使用 pip / 源码 / editable 形态的 Core",
    "WHEEL_VERSION_MISMATCH": "FC2 Metadata Core 随附包版本与插件不配对：请在 <Amane 数据目录>/plugins/_ffcc_core/ 中放入 {wheel}",
    "WHEEL_HASH_MISMATCH": "FC2 Metadata Core 随附包校验失败（sha256 与插件配对记录不一致）：请重新获取官方发布包中的 {wheel}",
}
DESCRIPTOR_KEYS = ("api_version", "capabilities", "content_types", "id", "languages", "metadata_fields", "name", "rate_limit", "urls", "version")


class GateError(RuntimeError):
    """网关自身无法继续（环境 / 宿主启动失败）；与场景 ``passed = false`` 不同。"""


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def free_port() -> int:
    with socket.socket() as handle:
        handle.bind(("127.0.0.1", 0))
        return handle.getsockname()[1]


@dataclass
class HostSpec:
    label: str
    coordinate_id: str
    form: str
    tag: str
    tag_object: str
    peeled_commit: str
    release_version: str
    requires_python: str
    plugin_api_version: str
    python_version: str
    executable: str
    install_dir: str
    deps_lock_sha256: str | None = None
    api_fingerprint_sha256: str | None = None
    adapter_used_subset_fingerprint_sha256: str | None = None
    platform: str = PLATFORM_WINDOWS


def _clean_environment(extra: dict[str, str] | None = None) -> dict[str, str]:
    """宿主环境：去掉会改变日志格式 / sys.path 的外部变量；不继承用户的 Amane 配置。"""
    drop = {"FORCE_COLOR", "CLICOLOR_FORCE", "PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV", "PYTHONSTARTUP", "PYTHONINSPECT"}
    env = {key: value for key, value in os.environ.items() if key not in drop and not key.startswith("AMANE_")}
    env.update({"NO_COLOR": "1", "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"})
    env.update(extra or {})
    return env


class HostProcess:
    """一个真实的 Amane 服务进程：``python -m amane.server``（源码宿主）或 ``Amane.Server.exe``（冻结桌面）。"""

    def __init__(self, spec: HostSpec, data_dir: Path, log_dir: Path, work_dir: Path, *, extra_env: dict[str, str] | None = None):
        self.spec, self.data_dir, self.log_dir, self.work_dir = spec, data_dir, log_dir, work_dir
        self.extra_env = dict(extra_env or {})
        self.port = 0
        self.process: subprocess.Popen | None = None
        self.output_path = work_dir / f"{uuid.uuid4().hex[:8]}.out"

    def start(self) -> "HostProcess":
        self.port = free_port()
        self.work_dir.mkdir(parents=True, exist_ok=True)
        env_vars = {
            "AMANE_DATA_DIR": str(self.data_dir), "AMANE_LOG_DIR": str(self.log_dir), "AMANE_PORT": str(self.port),
            "AMANE_HOST": "127.0.0.1", "AMANE_TOKEN": TOKEN, "AMANE_SAFE_DIRS": "ALLOW_ALL",
        }
        if self.spec.form == "frozen-desktop":
            env_vars["AMANE_WEB_DIST"] = str(Path(self.spec.executable).parents[1] / "web")
            command = [self.spec.executable]
        else:
            command = [self.spec.executable, "-m", "amane.server"]
        env_vars.update(self.extra_env)
        handle = self.output_path.open("wb")
        self.process = subprocess.Popen(command, cwd=self.work_dir, env=_clean_environment(env_vars), stdout=handle, stderr=subprocess.STDOUT)
        deadline = time.time() + READY_TIMEOUT[self.spec.form]
        while time.time() < deadline:
            if self.process.poll() is not None:
                raise GateError(f"{self.spec.label}: host exited early ({self.process.returncode}): {self.tail()}")
            status, _body = self.request("GET", "/api/health", timeout=5)
            if status == 200:
                return self
            time.sleep(0.4)
        raise GateError(f"{self.spec.label}: host not ready: {self.tail()}")

    def tail(self) -> str:
        try:
            return self.output_path.read_bytes()[-1500:].decode("utf-8", "replace")
        except OSError:
            return ""

    def stop(self) -> None:
        if self.process is None:
            return
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=25)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=15)
        self.process = None

    def __enter__(self) -> "HostProcess":
        return self.start()

    def __exit__(self, *exc) -> bool:
        self.stop()
        return False

    def request(self, method: str, path: str, *, body: bytes | None = None, headers: dict[str, str] | None = None, timeout: float = 300):
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}", method=method, data=body, headers={"Authorization": f"Bearer {TOKEN}", **(headers or {})})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                return response.status, response.read()
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read()
        except (urllib.error.URLError, ConnectionError, TimeoutError, OSError):
            return None, b""

    def api(self, method: str, path: str, *, json_body=None, timeout: float = 300):
        data = None if json_body is None else json.dumps(json_body).encode("utf-8")
        status, raw = self.request(method, path, body=data, headers={"Content-Type": "application/json"} if data is not None else None, timeout=timeout)
        try:
            return status, json.loads(raw.decode("utf-8")) if raw else None
        except (ValueError, UnicodeDecodeError):
            return status, raw.decode("utf-8", "replace")

    def upload(self, payload: bytes, filename: str = "plugin.zip"):
        boundary = "----ffccgate" + uuid.uuid4().hex
        head = f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{filename}"\r\nContent-Type: application/zip\r\n\r\n'
        body = head.encode("utf-8") + payload + f"\r\n--{boundary}--\r\n".encode("utf-8")
        status, raw = self.request("POST", "/api/plugins", body=body, headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
        try:
            return status, json.loads(raw.decode("utf-8")) if raw else None
        except (ValueError, UnicodeDecodeError):
            return status, raw.decode("utf-8", "replace")

    # ------------------------------------------------------------------ 便捷读取
    def plugin_ids(self) -> list[str]:
        status, body = self.api("GET", "/api/plugins")
        return sorted(item["descriptor"]["id"] for item in (body or {}).get("items", [])) if status == 200 else []

    def failures(self) -> list[dict]:
        status, body = self.api("GET", "/api/plugins")
        return list((body or {}).get("failures", [])) if status == 200 else []

    # ------------------------------------------------------------------ 探针插件（宿主进程内执行 host_scripts/in_host.py）
    def probe(self, payload: dict) -> dict:
        source = (HOST_SCRIPTS / "in_host.py").read_text(encoding="utf-8")
        probe_dir = self.data_dir / "plugins" / "sources" / PROBE_ID
        probe_dir.mkdir(parents=True, exist_ok=True)
        code = (
            "import json as _json\n"
            f"_SRC = {source!r}\n"
            f"_PAYLOAD = _json.loads({json.dumps(payload, ensure_ascii=True, allow_nan=True)!r})\n"
            "_ns = {'__name__': 'ffcc_in_host'}\n"
            "exec(compile(_SRC, 'in_host.py', 'exec'), _ns)\n"
            "try:\n"
            "    _result = {'ok': True, 'result': _ns['run'](_PAYLOAD)}\n"
            "except BaseException as _exc:\n"
            "    _result = {'ok': False, 'error': type(_exc).__name__ + ': ' + str(_exc)[:600]}\n"
            f"raise RuntimeError({PROBE_MARK!r} + _json.dumps(_result, sort_keys=True, default=repr))\n"
        )
        (probe_dir / "plugin.py").write_text(code, encoding="utf-8", newline="\n")
        try:
            status, _ = self.api("POST", "/api/plugins/reload")
            if status != 200:
                raise GateError(f"probe reload failed: {status}")
            found = [item for item in self.failures() if item.get("name") == PROBE_ID]
            if not found or PROBE_MARK not in str(found[0].get("error")):
                raise GateError(f"probe produced no result: {found}")
            return json.loads(str(found[0]["error"]).split(PROBE_MARK, 1)[1])
        finally:
            shutil.rmtree(probe_dir, ignore_errors=True)
            self.api("POST", "/api/plugins/reload")


# ------------------------------------------------------------------------------------------------ 构建产物与变体


def _tool(name: str):
    return _load_module(REPO_ROOT / "tools" / name, "ffcc_gate_tool_" + Path(name).stem)


class Artifacts:
    """被验收的 L0 / L1 确切字节 + 由它们派生的测试变体（临时副本；绝不修改被验收的字节）。"""

    def __init__(self, wheel_path: Path, stage1_dir: Path, work: Path, *, repo_root: Path | None = None):
        self.repo_root = Path(repo_root) if repo_root is not None else REPO_ROOT  # mutation 运行时 = 被篡改的仓库副本
        self.release = _tool("build_amane_release.py")
        self.wheel_path = wheel_path
        self.wheel_name = wheel_path.name
        self.wheel_bytes = wheel_path.read_bytes()
        self.zip_name = f"{PLUGIN_ID}-0.1.0.zip"
        self.zip_path = stage1_dir / self.zip_name
        self.zip_bytes = self.zip_path.read_bytes()
        self.work = work
        self._pin_b: tuple[bytes, Path] | None = None

    # ---- 模板（以 pin 字面量代入）
    def template(self, key: str, *, version: str = "0.1.0", wheel: str | None = None) -> str:
        return TEMPLATES[key].format(version=version, wheel=wheel or self.wheel_name)

    def rejection(self, key: str, **kwargs) -> str:
        return "插件导入失败: " + self.template(key, **kwargs)

    # ---- plugin zip 变体
    def members(self) -> dict[str, bytes]:
        with zipfile.ZipFile(io.BytesIO(self.zip_bytes)) as archive:
            return {name: archive.read(name) for name in archive.namelist()}

    def rezip(self, members: dict[str, bytes]) -> bytes:
        return self.release.deterministic_zip(members)

    def with_replacement(self, member: str, old: bytes, new: bytes) -> bytes:
        members = self.members()
        assert old in members[member], (member, old)
        members[member] = members[member].replace(old, new)
        return self.rezip(members)

    def version_bumped_zip(self) -> bytes:
        return self.with_replacement(f"{PLUGIN_ID}/_impl/_settings.py", b'PLUGIN_VERSION = "0.1.0"', b'PLUGIN_VERSION = "0.1.1"')

    def wrong_id_zip(self) -> bytes:
        return self.with_replacement(f"{PLUGIN_ID}/_impl/_settings.py", b'PLUGIN_ID = "ffcc.fc2-metadata"', b'PLUGIN_ID = "other.id"')

    def file_set(self) -> dict[str, str]:
        return {name.split("/", 1)[1]: sha256_hex(data) for name, data in self.members().items()}

    # ---- wheel 变体
    def tampered_wheel(self) -> bytes:
        data = bytearray(self.wheel_bytes)
        data[len(data) // 2] ^= 0x01
        return bytes(data)

    # ---- 第二个 Core（pin 变化；HC-16）
    def pin_b(self) -> tuple[bytes, Path]:
        """从仓库树的临时副本构建 Core 0.1.1（Core 源码多一行注释）与配对的 plugin zip B；被验收的字节不受影响。"""
        if self._pin_b is not None:
            return self._pin_b
        copy = self.work / "pin_b_repo"
        for relative in ("pyproject.toml", "src/fc2_metadata_core", "adapters/amane/fc2_amane_adapter", "adapters/amane/shim", "adapters/amane/release", "docs/acceptance/evidence/P5_C1_HOST_WITNESS.json"):
            source = self.repo_root / relative
            if source.is_file():
                (copy / relative).parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, copy / relative)
            else:
                shutil.copytree(source, copy / relative, ignore=shutil.ignore_patterns("__pycache__"))
        pyproject = copy / "pyproject.toml"
        pyproject.write_bytes(pyproject.read_bytes().replace(b'version = "0.1.0"', b'version = "0.1.1"'))
        init = copy / "src" / "fc2_metadata_core" / "__init__.py"
        init.write_bytes(init.read_bytes() + b"\n# core B (pin-change fixture)\n")
        builder = _tool("build_core_wheel.py")
        name, payload, _tree = builder.build_wheel_bytes(copy / "src" / "fc2_metadata_core", pyproject)
        wheel_b = self.work / "pin_b" / name
        wheel_b.parent.mkdir(parents=True, exist_ok=True)
        wheel_b.write_bytes(payload)
        stage1 = self.release.build_stage1(copy, wheel_b, check_witness=False)
        self._pin_b = (stage1["files"][f"{PLUGIN_ID}-0.1.0.zip"], wheel_b)
        return self._pin_b


# ------------------------------------------------------------------------------------------------ 场景记录


class Scenario:
    def __init__(self, scenario_id: str):
        self.id = scenario_id
        self.failures: list[str] = []
        self.observations: dict[str, object] = {}

    def check(self, condition: object, message: str) -> bool:
        if not condition:
            self.failures.append(message)
        return bool(condition)

    def record(self, key: str, value: object) -> None:
        self.observations[key] = value

    def result(self) -> dict:
        return {"id": self.id, "passed": not self.failures, "observations": self.observations, "failures": self.failures}


def canonical_hash(value: object) -> str:
    return sha256_hex(json.dumps(value, sort_keys=True, ensure_ascii=True, default=repr).encode("utf-8"))


def tree_files(root: Path, *, ignore_cache: bool = True) -> dict[str, str]:
    result: dict[str, str] = {}
    if not root.exists():
        return result
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if ignore_cache and ("__pycache__" in path.parts or path.suffix == ".pyc"):
            continue
        if path.is_file():
            result[relative] = sha256_hex(path.read_bytes())
    return result


def sources_entries(data_dir: Path) -> list[str]:
    root = data_dir / "plugins" / "sources"
    return sorted(item.name for item in root.iterdir()) if root.exists() else []


def sidecar_dir(data_dir: Path) -> Path:
    return data_dir / "plugins" / "_ffcc_core"


def place_sidecar(data_dir: Path, name: str, data: bytes) -> None:
    directory = sidecar_dir(data_dir)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / name).write_bytes(data)


def clear_sidecar(data_dir: Path) -> None:
    shutil.rmtree(sidecar_dir(data_dir), ignore_errors=True)


def descriptor_subset(descriptor: dict) -> dict:
    subset = {key: descriptor.get(key) for key in DESCRIPTOR_KEYS}
    for key in ("capabilities", "content_types", "metadata_fields", "languages"):
        subset[key] = sorted(subset[key] or [])
    return subset


def snapshot_roots(roots: dict[str, Path], excludes: tuple[str, ...] = ()) -> dict[str, dict[str, list[int]]]:
    """HC-18 / E19：文件系统快照（相对路径 -> [大小, mtime_ns]）；排除缓存目录与 ``excludes`` 下的路径。"""
    skip = {"__pycache__", ".git", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
    result: dict[str, dict[str, list[int]]] = {}
    for label, root in roots.items():
        files: dict[str, list[int]] = {}
        if root.exists():
            for current, directories, names in os.walk(root):
                directories[:] = [name for name in directories if name not in skip and not any((Path(current) / name).as_posix().startswith(prefix) for prefix in excludes)]
                for name in names:
                    path = Path(current) / name
                    try:
                        info = path.stat()
                    except OSError:
                        continue
                    files[path.relative_to(root).as_posix()] = [info.st_size, info.st_mtime_ns]
        result[label] = files
    return result


def snapshot_diff(before: dict, after: dict) -> dict[str, dict[str, list[str]]]:
    difference: dict[str, dict[str, list[str]]] = {}
    for label in before:
        added = sorted(set(after[label]) - set(before[label]))
        removed = sorted(set(before[label]) - set(after[label]))
        changed = sorted(name for name in set(before[label]) & set(after[label]) if before[label][name] != after[label][name])
        if added or removed or changed:
            difference[label] = {"added": added[:10], "removed": removed[:10], "changed": changed[:10]}
    return difference


# ------------------------------------------------------------------------------------------------ 一次宿主运行的上下文


@dataclass
class HostRun:
    spec: HostSpec
    work: Path
    art: Artifacts
    loopback: object
    oracle: dict
    results: dict[str, Scenario] = field(default_factory=dict)
    extras: dict[str, object] = field(default_factory=dict)

    def scenario(self, scenario_id: str) -> Scenario:
        self.results[scenario_id] = Scenario(scenario_id)
        return self.results[scenario_id]

    def host(self, name: str, *, extra_env: dict[str, str] | None = None) -> HostProcess:
        base = self.work / name
        (base / "data").mkdir(parents=True, exist_ok=True)
        (base / "logs").mkdir(parents=True, exist_ok=True)
        (base / "cwd").mkdir(parents=True, exist_ok=True)
        return HostProcess(self.spec, base / "data", base / "logs", base / "cwd", extra_env=extra_env)


# ------------------------------------------------------------------------------------------------ Group A：失败分支（Core 尚未被加载时）


def admission_row(run: "HostRun", case: str, *, mode: str, expected: str, observed: str, template: str | None, before: dict, after: dict) -> dict:
    """``core_admission.cases[]``：失败后 sys.path 与 fc2_metadata_core* 对象身份相对入口是否不变（经宿主内探针实测）。"""
    return {
        "id": f"{run.spec.label}:{case}", "mode": mode, "python": run.spec.python_version, "expected": expected, "observed": observed,
        "template": template,
        "sys_path_unchanged_on_fail": before.get("path_sha") == after.get("path_sha"),
        "sys_modules_unchanged_on_fail": before.get("core_ids") == after.get("core_ids") and before.get("core_loaded") == after.get("core_loaded"),
        "payload_executed": False,
    }


def host_state(host: HostProcess) -> dict:
    answer = host.probe({"op": "state"})
    return answer["result"] if answer.get("ok") else {}


def phase_failures(run: HostRun, host: HostProcess) -> None:
    art, data = run.art, host.data_dir
    rows: list[dict] = run.extras.setdefault("admission_rows", [])  # type: ignore[assignment]
    # ---- HC-10：Core 缺失
    sc = run.scenario("HC-10")
    before = host_state(host)
    status, body = host.upload(art.zip_bytes)
    after = host_state(host)
    sc.check(status == 422, f"missing Core must be HTTP 422, got {status}")
    sc.check(isinstance(body, dict) and body.get("detail") == C1_MISSING_CORE_MESSAGE, f"detail must be the P5-C1 section 22 message, got {body!r}")
    sc.check(host.plugin_ids() == [], "the plugin must not be listed")
    sc.check(sources_entries(data) == [], f"no half install: {sources_entries(data)}")
    sc.check(before.get("core_loaded") is False and after.get("core_loaded") is False and before.get("path_sha") == after.get("path_sha"), "locator must not touch sys.path / import Core when no Core exists")
    config_status, config = host.api("GET", "/api/config")
    sc.check(config_status == 200 and PLUGIN_ID not in json.dumps(config), "no fallback / route may reference the missing plugin")
    sc.record("http_status", status)
    sc.record("detail_equals_c1_section_22", isinstance(body, dict) and body.get("detail") == C1_MISSING_CORE_MESSAGE)
    sc.record("listed", host.plugin_ids())
    sc.record("sources_entries", sources_entries(data))
    sc.record("sys_path_unchanged", before.get("path_sha") == after.get("path_sha"))
    sc.record("core_not_imported", after.get("core_loaded") is False)

    # ---- HC-11：Core 不兼容（sidecar 各分支；目录形态由 S-D 在源码宿主上补充）
    sc = run.scenario("HC-11")
    cases: dict[str, dict] = {}

    def expect(label: str, key: str, **kwargs) -> None:
        state_before = host_state(host)
        status, body = host.upload(art.zip_bytes)
        state_after = host_state(host)
        detail = body.get("detail") if isinstance(body, dict) else body
        row = admission_row(run, f"sidecar_{label}", mode="wheel", expected="FAIL", observed="FAIL" if status == 422 else "PASS", template=key, before=state_before, after=state_after)
        ok = status == 422 and detail == art.rejection(key, **kwargs) and sources_entries(data) == [] and host.plugin_ids() == []
        ok = ok and row["sys_path_unchanged_on_fail"] and row["sys_modules_unchanged_on_fail"]
        sc.check(ok, f"{label}: expected 422 + {key} + unchanged state, got {status} {detail!r} sources={sources_entries(data)} row={row}")
        rows.append(row)
        cases[label] = {"http_status": status, "template": key if ok else "MISMATCH", "half_install": sources_entries(data) != [],
                        "sys_path_unchanged": row["sys_path_unchanged_on_fail"], "core_objects_unchanged": row["sys_modules_unchanged_on_fail"]}

    place_sidecar(data, art.wheel_name, art.tampered_wheel())
    expect("tampered_same_name_one_byte", "WHEEL_HASH_MISMATCH")
    clear_sidecar(data)
    place_sidecar(data, "fc2_metadata_core-9.9.9-py3-none-any.whl", art.wheel_bytes)
    expect("only_other_version_wheel", "WHEEL_VERSION_MISMATCH")
    clear_sidecar(data)
    directory = sidecar_dir(data)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / art.wheel_name).mkdir()
    expect("same_name_directory", "WHEEL_HASH_MISMATCH")
    clear_sidecar(data)
    place_sidecar(data, art.wheel_name, art.wheel_bytes + b"\0" * (16 * 1024 * 1024 + 1))
    expect("oversize_over_16_mib", "WHEEL_HASH_MISMATCH")
    clear_sidecar(data)
    directory.mkdir(parents=True, exist_ok=True)
    target = data / "plugins" / "linktarget.whl"
    target.write_bytes(art.wheel_bytes)
    try:
        os.symlink(target, directory / art.wheel_name)
        symlink_privilege = True
    except (OSError, NotImplementedError):
        symlink_privilege = False
    if symlink_privilege:
        expect("symlink_to_the_exact_wheel", "WHEEL_HASH_MISMATCH")
        rows[-1]["symlink_privilege"] = True
        cases["symlink_to_the_exact_wheel"]["symlink_privilege"] = True
    else:
        # A1-3：本账户没有创建 file symlink 的 OS 权限（我们不改变系统安全设置）-> 真实宿主子项记为 ENVIRONMENTALLY_UNAVAILABLE：
        # 既不是 PASS，也不是 FAIL，更不是“当作通过的 skip”。必需的替代证据在单元层：E31-i（3.12 与 3.14；``os.lstat`` 替身只改写 st_mode）+ M2-14 killer。
        rows.append({
            "id": f"{run.spec.label}:{SYMLINK_CASE}", "mode": "wheel", "python": run.spec.python_version, "expected": "FAIL", "observed": ENV_UNAVAILABLE,
            "template": "WHEEL_HASH_MISMATCH", "sys_path_unchanged_on_fail": True, "sys_modules_unchanged_on_fail": True, "payload_executed": False,
            "symlink_privilege": False,
        })
        cases["symlink_to_the_exact_wheel"] = {
            "observed": ENV_UNAVAILABLE, "symlink_privilege": False, "real_host_executed": False,
            "substitute_evidence": "unit E31-i on Python 3.12 and 3.14 (lstat stand-in changes only st_mode) + M2-14 symlink-acceptance mutant KILLED",
        }
    clear_sidecar(data)
    target.unlink(missing_ok=True)
    sc.record("cases", cases)
    run.extras["hc11_sidecar_cases"] = cases

    # ---- HC-12：畸形 plugin zip
    sc = run.scenario("HC-12")
    forged = io.BytesIO()
    with zipfile.ZipFile(forged, "w") as archive:
        archive.writestr("../evil.py", "x = 1\n")
        archive.writestr(f"{PLUGIN_ID}/plugin.py", "x = 1\n")
    no_entry = io.BytesIO()
    with zipfile.ZipFile(no_entry, "w") as archive:
        archive.writestr(f"{PLUGIN_ID}/readme.txt", "x")
    multi = io.BytesIO()
    with zipfile.ZipFile(multi, "w") as archive:
        archive.writestr("a/plugin.py", "x = 1\n")
        archive.writestr("b/plugin.py", "x = 1\n")
    # A1-2：HC-12 = 12a..12e，判据逐个冻结。12a = ``.zip`` 文件名 + 非 ZIP 字节：宿主路由只捕获 (ValueError, TypeError, OSError)，
    # ``zipfile.BadZipFile`` 不是它们的子类 -> 未被捕获 -> HTTP 500（pinned v0.15.0 / v0.18.0 逐字节相同的**已知宿主路由缺陷**；
    # 在解压 / 导入之前；与本插件 / shim / Core 无关）。12b..12e 仍为 422。**不**把 500 泛化成任何其它安装失败的允许值。
    variants = (
        ("12a_not_a_zip", b"this is not a zip archive", 500),
        ("12b_path_traversal", forged.getvalue(), 422),
        ("12c_no_plugin_py", no_entry.getvalue(), 422),
        ("12d_multiple_top_level_folders", multi.getvalue(), 422),
        ("12e_oversize_over_20_mib", b"0" * (20 * 1024 * 1024 + 1), 422),
    )
    rows_http = {}
    for label, payload, expected_status in variants:
        status, _body = host.upload(payload)
        residue, registered = sources_entries(data), host.plugin_ids()
        rows_http[label] = {"http_status": status, "expected_http_status": expected_status, "rejected": status == expected_status and residue == [] and registered == [],
                            "sources_entries": residue, "registered_plugins": registered}
        sc.check(status == expected_status and residue == [] and registered == [], f"{label}: expected exactly HTTP {expected_status} with no residue and no registration, got {status} {residue} {registered}")
    modules = host.probe({"op": "modules"})
    imported = modules["result"]["ext_names"] if modules.get("ok") else None
    sc.check(imported == [], f"a rejected upload must never import / execute plugin code: {imported}")
    for item in rows_http.values():
        item["plugin_code_executed"] = imported != []
    sc.record("variants", rows_http)
    sc.record("hc12a_known_pinned_host_route_defect", {"http_status": rows_http["12a_not_a_zip"]["http_status"], "cause": "uncaught zipfile.BadZipFile in the host route (not a plugin / artifact defect)"})
    run.extras["hc12"] = {label: item["http_status"] for label, item in sorted(rows_http.items())}
    clear_sidecar(data)


# ------------------------------------------------------------------------------------------------ Group A：成功路径（Core 随 sidecar 到位之后）

BASELINE_CONFIG = {"sources": None, "source_deadline_seconds": 20}


def _plugin_response(host: HostProcess):
    status, body = host.api("GET", f"/api/plugins/{PLUGIN_ID}")
    return status, body


def _schema_names(schema: dict) -> list[str]:
    names = set((schema.get("properties") or {}))
    for definition in (schema.get("$defs") or {}).values():
        names |= set((definition.get("properties") or {}))
    return sorted(names)


def phase_success(run: HostRun, host: HostProcess) -> None:
    art, data = run.art, host.data_dir
    place_sidecar(data, art.wheel_name, art.wheel_bytes)
    plugin_dir = data / "plugins" / "sources" / PLUGIN_ID

    # ---- HC-01：clean install
    sc = run.scenario("HC-01")
    status, body = host.upload(art.zip_bytes)
    ids = sorted(item["descriptor"]["id"] for item in (body or {}).get("items", [])) if isinstance(body, dict) else []
    sc.check(status == INSTALLED, f"install must be {INSTALLED} Created, got {status}: {body!r}")
    sc.check(ids == [PLUGIN_ID], f"items must contain exactly {PLUGIN_ID}, got {ids}")
    sc.check(isinstance(body, dict) and body.get("failures") == [], f"failures must be empty, got {body!r}")
    disk = tree_files(plugin_dir)
    sc.check(disk == art.file_set(), "installed file set / bytes must equal the plugin zip")
    sc.record("http_status", status)
    sc.record("items", ids)
    sc.record("failures", (body or {}).get("failures") if isinstance(body, dict) else None)
    sc.record("installed_files_equal_zip_files", disk == art.file_set())
    sc.record("file_count", len(disk))
    # INSTALL 第 3 节第 4 步：把插件加入 FC2 内容类型的来源列表（宿主的内容路由；真实 PATCH /api/config）
    _cs, config = host.api("GET", "/api/config")
    original_route = list(((config or {}).get("scraping", {}).get("content_routes", {}) or {}).get("fc2", [])) if _cs == 200 else []
    patch_status, _ = host.api("PATCH", "/api/config", json_body={"scraping": {"content_routes": {"fc2": [PLUGIN_ID, *original_route]}}})
    _cs, config = host.api("GET", "/api/config")
    route_after = list(((config or {}).get("scraping", {}).get("content_routes", {}) or {}).get("fc2", [])) if _cs == 200 else []
    sc.check(patch_status == 200 and route_after[:1] == [PLUGIN_ID], f"INSTALL step 4 (add the plugin to the FC2 route) must work: {patch_status} {route_after[:3]}")
    host.api("PATCH", "/api/config", json_body={"scraping": {"content_routes": {"fc2": original_route}}})
    sc.record("fc2_content_route_accepts_the_plugin", patch_status == 200 and route_after[:1] == [PLUGIN_ID])

    # ---- HC-03：descriptor / capabilities / schema
    sc = run.scenario("HC-03")
    status, plugin = _plugin_response(host)
    descriptor = descriptor_subset((plugin or {}).get("descriptor", {})) if status == 200 else {}
    sc.check(status == 200, f"GET plugin must be 200, got {status}")
    sc.check(descriptor == run.oracle["descriptor"], f"descriptor subset differs from the C1 record: {descriptor}")
    schema = (plugin or {}).get("config_schema", {}) if status == 200 else {}
    sc.check(_schema_names(schema) == run.oracle["schema_fields"], f"config schema fields differ: {_schema_names(schema)}")
    sc.record("descriptor_subset", descriptor)
    sc.record("config_schema_fields", _schema_names(schema))
    sc.record("config_schema_sha256", canonical_hash(schema))
    run.extras["descriptor"] = descriptor
    run.extras["config_schema_sha256"] = canonical_hash(schema)

    # ---- HC-05（HTTP 一半；宿主内三项在 Group B 合并）
    patch_ok: dict[str, bool] = {}
    for sample_id, sample in run.oracle["config_samples"]:
        status, _body = host.api("PATCH", f"/api/plugins/{PLUGIN_ID}", json_body={"config": sample})
        patch_ok[sample_id] = status == 200  # PATCH 成功 = 精确 200（A1-1：不放宽为状态码区间）
        if patch_ok[sample_id]:
            host.api("PATCH", f"/api/plugins/{PLUGIN_ID}", json_body={"config": BASELINE_CONFIG})
    run.extras["patch_ok"] = patch_ok

    # ---- HC-08（HTTP 一半：顶层浅合并 + rebuild 不报错；行为 oracle 在 Group B）
    sc = run.scenario("HC-08")
    disabled = {"sources": [{"id": "fc2db_net", "enabled": False}, {"id": "javdb"}, {"id": "av123"}]}
    status1, _ = host.api("PATCH", f"/api/plugins/{PLUGIN_ID}", json_body={"config": disabled})
    status2, _ = host.api("PATCH", f"/api/plugins/{PLUGIN_ID}", json_body={"config": {"source_deadline_seconds": 30}})
    _status, merged = _plugin_response(host)
    config_after = (merged or {}).get("config", {}).get("config", {})
    sc.check(status1 == 200 and status2 == 200, f"PATCH must be 200: {status1} {status2}")
    sc.check(config_after.get("sources") == disabled["sources"] and config_after.get("source_deadline_seconds") == 30, f"shallow merge must keep sources: {config_after}")
    status3, _ = host.api("PATCH", f"/api/plugins/{PLUGIN_ID}", json_body={"config": {"sources": [{"id": "javdb"}]}})
    _status, replaced = _plugin_response(host)
    sc.check(status3 == 200 and (replaced or {}).get("config", {}).get("config", {}).get("sources") == [{"id": "javdb"}], f"sources replaced as a whole: {replaced!r}")
    host.api("PATCH", f"/api/plugins/{PLUGIN_ID}", json_body={"config": BASELINE_CONFIG})
    sc.record("shallow_merge_keeps_unrelated_keys", True)
    sc.record("sources_replaced_as_a_whole", True)

    # ---- HC-02：重启后仍被发现（restart persistence）
    sc = run.scenario("HC-02")
    persisted = {"source_deadline_seconds": 45}
    host.api("PATCH", f"/api/plugins/{PLUGIN_ID}", json_body={"config": persisted})
    host.stop()
    host.start()
    status, plugin = _plugin_response(host)
    sc.check(status == 200 and host.plugin_ids() == [PLUGIN_ID], f"plugin must be discovered after restart: {host.plugin_ids()}")
    sc.check(host.failures() == [], "no failures after restart")
    after = descriptor_subset((plugin or {}).get("descriptor", {})) if status == 200 else {}
    sc.check(after == run.extras["descriptor"], "descriptor subset must equal HC-01 after restart")
    stored = (plugin or {}).get("config", {}).get("config", {}) if status == 200 else {}
    sc.check(stored.get("source_deadline_seconds") == 45, f"persisted config must survive the restart: {stored}")
    sc.record("discovered_after_restart", host.plugin_ids())
    sc.record("descriptor_equals_hc01", after == run.extras["descriptor"])
    sc.record("config_persisted", stored.get("source_deadline_seconds") == 45)
    host.api("PATCH", f"/api/plugins/{PLUGIN_ID}", json_body={"config": BASELINE_CONFIG})

    # ---- HC-06：reload 不改文件
    sc = run.scenario("HC-06")
    first = host.probe({"op": "modules"})
    second = host.probe({"op": "modules"})
    sc.check(first.get("ok") and second.get("ok"), f"probe failed: {first} {second}")
    if first.get("ok") and second.get("ok"):
        one, two = first["result"], second["result"]
        sc.check(one["ext_names"] == two["ext_names"] and len(one["ext_names"]) >= 8, f"amane_ext modules: {one['ext_names']}")
        sc.check(all(one["ext_ids"][name] != two["ext_ids"][name] for name in one["ext_ids"]), "every amane_ext* module must be rebuilt as a new object")
        sc.check(one["core_loaded"] and one["core_ids"] == two["core_ids"], "fc2_metadata_core must NOT be rebuilt by reload (W2-02)")
        sc.check(one["core_loader_exact_zipimporter"] is True and one["core_archive_basename"] == art.wheel_name, "Core must be loaded from the exact pinned wheel via zipimporter")
        sc.record("ext_modules_rebuilt", True)
        sc.record("core_objects_unchanged", one["core_ids"] == two["core_ids"])
        sc.record("core_loader_exact_zipimporter", one["core_loader_exact_zipimporter"])
        sc.record("core_loaded_from_pinned_wheel", one["core_archive_basename"] == art.wheel_name)
        sc.record("ext_module_count", len(one["ext_names"]))
    status, _ = host.api("POST", "/api/plugins/reload")
    sc.check(status == 200 and host.plugin_ids() == [PLUGIN_ID], "reload must keep the plugin")

    # ---- HC-07：reload 执行新代码（stale-module 守卫；只改临时数据目录里的副本）
    sc = run.scenario("HC-07")
    settings_path = plugin_dir / "_impl" / "_settings.py"
    original = settings_path.read_bytes()
    settings_path.write_bytes(original.replace(b'PLUGIN_VERSION = "0.1.0"', b'PLUGIN_VERSION = "0.1.0-sentinel"'))
    host.api("POST", "/api/plugins/reload")
    status, plugin = _plugin_response(host)
    seen = (plugin or {}).get("descriptor", {}).get("version") if status == 200 else None
    sc.check(seen == "0.1.0-sentinel", f"reload must execute the new code, saw {seen!r}")
    settings_path.write_bytes(original)
    host.api("POST", "/api/plugins/reload")
    status, plugin = _plugin_response(host)
    restored = (plugin or {}).get("descriptor", {}).get("version") if status == 200 else None
    sc.check(restored == "0.1.0", f"restoring the file must restore the version, saw {restored!r}")
    sc.record("sentinel_visible_after_reload", seen == "0.1.0-sentinel")
    sc.record("restored_after_second_reload", restored == "0.1.0")

    # ---- HC-09：插件替换 / 升级（pin 不变）
    sc = run.scenario("HC-09")
    status, body = host.upload(art.version_bumped_zip())
    sc.check(status == INSTALLED, f"upgrade upload must be {INSTALLED}, got {status}: {body!r}")
    _status, plugin = _plugin_response(host)
    sc.check((plugin or {}).get("descriptor", {}).get("version") == "0.1.1", "descriptor.version must be updated")
    probe = host.probe({"op": "modules"})
    if probe.get("ok"):
        sc.check(probe["result"]["plugin_version_in_loaded_settings"] == "0.1.1", "no stale module: the loaded _settings must carry the new version")
        sc.check(probe["result"]["core_loaded"] and probe["result"]["core_archive_basename"] == art.wheel_name, "Core is unchanged by a plugin-only upgrade")
    status, _ = host.upload(art.zip_bytes)
    _status, plugin = _plugin_response(host)
    sc.check(status == INSTALLED and (plugin or {}).get("descriptor", {}).get("version") == "0.1.0", "re-uploading the accepted zip restores 0.1.0")
    sc.record("version_after_upgrade", "0.1.1")
    sc.record("loaded_settings_version_after_upgrade", probe["result"]["plugin_version_in_loaded_settings"] if probe.get("ok") else None)
    sc.record("version_after_restore", "0.1.0")

    # ---- HC-13：错误 plugin id（宿主按 descriptor.id 提交目录；行为被记录且两版本相同）
    sc = run.scenario("HC-13")
    status, _body = host.upload(art.wrong_id_zip())
    ids_after = host.plugin_ids()
    _cstatus, config = host.api("GET", "/api/config")
    sc.check(status == INSTALLED and ids_after == sorted(["other.id", PLUGIN_ID]), f"host commits the tree under descriptor.id: {status} {ids_after}")
    sc.check(_cstatus == 200 and "other.id" not in json.dumps((config or {}).get("scraping", {})), "content routes / config must not reference the wrong id")
    dstatus, _ = host.api("DELETE", "/api/plugins/other.id")
    sc.check(dstatus == 204 and host.plugin_ids() == [PLUGIN_ID], f"cleanup of the foreign id: {dstatus}")
    sc.record("http_status", status)
    sc.record("ids_after_upload", ids_after)
    run.extras["hc13"] = {"status": status, "ids": ids_after}

    # ---- HC-14：重复 plugin
    sc = run.scenario("HC-14")
    status, body = host.upload(art.zip_bytes)
    ids_after = host.plugin_ids()
    sc.check(status == INSTALLED and ids_after == [PLUGIN_ID], f"second upload replaces the tree and leaves one entry: {status} {ids_after}")
    duplicate = data / "plugins" / "sources" / "ffcc.dup"
    shutil.copytree(plugin_dir, duplicate, ignore=shutil.ignore_patterns("__pycache__"))
    host.api("POST", "/api/plugins/reload")
    failures = host.failures()
    mismatch = [item for item in failures if item.get("name") == "ffcc.dup"]
    sc.check(host.plugin_ids() == [PLUGIN_ID] and len(mismatch) == 1 and "does not match directory name" in str(mismatch[0].get("error")), f"descriptor.id != directory name must be a discover failure: {failures}")
    shutil.rmtree(duplicate, ignore_errors=True)
    host.api("POST", "/api/plugins/reload")
    sc.check(host.failures() == [], "failures cleared after removing the duplicate directory")
    sc.record("entries_after_second_upload", ids_after)
    sc.record("duplicate_directory_failure", "descriptor id does not match directory name" if mismatch else None)

    # ---- HC-15：卸载
    sc = run.scenario("HC-15")
    runtime_dir = data / "plugins" / PLUGIN_ID
    runtime_dir.mkdir(parents=True, exist_ok=True)
    (runtime_dir / "runtime.marker").write_text("keep", encoding="utf-8")
    sidecar_before = tree_files(sidecar_dir(data))
    status, _ = host.api("DELETE", f"/api/plugins/{PLUGIN_ID}")
    sc.check(status == 204, f"DELETE must be 204, got {status}")
    sc.check(not plugin_dir.exists() and host.plugin_ids() == [], "the source tree must be gone")
    sc.check((runtime_dir / "runtime.marker").exists(), "runtime data under plugins/<id>/ must be kept")
    sc.check(tree_files(sidecar_dir(data)) == sidecar_before, "the sidecar directory must not be touched")
    sc.record("http_status", status)
    sc.record("source_tree_removed", not plugin_dir.exists())
    sc.record("runtime_data_kept", (runtime_dir / "runtime.marker").exists())
    sc.record("sidecar_untouched", tree_files(sidecar_dir(data)) == sidecar_before)
    shutil.rmtree(runtime_dir, ignore_errors=True)


# ------------------------------------------------------------------------------------------------ Group B：受控宿主栈（真实 PluginManager / CrawlerFactory / WebClient -> 回环 fixture）

NORMALIZED_ORIGINS = {"fc2db_net": "https://fc2db.net", "javdb": "https://javdb.com", "av123": "https://123av.com"}


def normalize_loopback(value, base_urls: dict[str, str]):
    """把回环 base_url 还原成站点缺省 origin，使结果可与 C1 记录逐字段对拍。"""
    if isinstance(value, str):
        for source, base in base_urls.items():
            value = value.replace(base, NORMALIZED_ORIGINS.get(source, "http://closed.invalid"))
        return value
    if isinstance(value, list):
        return [normalize_loopback(item, base_urls) for item in value]
    if isinstance(value, dict):
        return {key: normalize_loopback(item, base_urls) for key, item in value.items()}
    return value


def phase_own_stack(run: HostRun, host: HostProcess) -> None:
    art, loopback = run.art, run.loopback
    base_urls = {source: loopback.base_url(source) for source in ("fc2db_net", "javdb", "av123")}
    closed = f"http://127.0.0.1:{free_port()}"
    common = {"work": str(host.work_dir / "stack"), "zip_path": str(art.zip_path), "wheel_path": str(art.wheel_path), "base_urls": base_urls, "closed_base": closed}

    # ---- HC-04 / HC-17 / E15 / E16：同一请求集
    loopback.reset()
    answer = host.probe({"op": "fetch_matrix", **common})
    counts = {digits: loopback.counts_for(digits) for digits in ("4979299", "4825061", "4824605", "90000001", "90000002", "90000003", "90000004", "90000005", "90000006", "90000007", "90000008", "90000009", "90000010")}
    sc4, sc17 = run.scenario("HC-04"), run.scenario("HC-17")
    if not sc4.check(answer.get("ok"), f"fetch_matrix probe failed: {answer}"):
        sc17.check(False, "fetch_matrix unavailable")
        return
    result = answer["result"]
    cases, identity = result["cases"], result["identity"]
    success = cases.get("success_all_sources", {})
    sc4.check(success.get("class") == "MediaMetadata", f"success case must map to MediaMetadata: {success.get('class')}")
    expected = run.oracle["h07_metadata"]
    payload = normalize_loopback(success.get("payload", {}), base_urls)
    mismatched = [key for key, value in expected.items() if key != "tags_count" and payload.get(key) != value]
    sc4.check(not mismatched and len(payload.get("tags", [])) == expected["tags_count"], f"result differs from the frozen P5-C1 mapping on: {mismatched}")
    sc4.check(all(identity.get(key) is True for key in ("context_web_client_is_host_web_client", "context_http_client_web_client_is_host_web_client", "bridge_holds_host_web_client")), f"E17 identity: {identity}")
    sc4.check(cases.get("partial_one_source_missing", {}).get("class") == "MediaMetadata", "partial result still maps to MediaMetadata")
    sc4.check(cases.get("not_found_everywhere", {}).get("class") == "None", "not found maps to None")
    sc4.record("success_equals_c1_mapping", not mismatched)
    sc4.record("result_classes", {case: item.get("class") for case, item in sorted(cases.items())})
    sc4.record("identity", identity)
    sc17.check(counts["4979299"] == {"av123": 1, "fc2db_net": 1, "javdb": 1}, f"L1 = S: one request per source on success, got {counts['4979299']}")
    sc17.check(all(max(value.values(), default=0) <= 3 for value in counts.values()), f"L2 bound S x H (H = 3) violated: {counts}")
    sc17.check(all(identity.get(key) is True for key in ("context_web_client_is_host_web_client", "bridge_holds_host_web_client")), "all requests must come through the host WebClient (same object)")
    sc17.record("requests_per_source_by_case_digits", counts)
    sc17.record("bridge_holds_host_web_client", identity.get("bridge_holds_host_web_client"))
    run.extras["fetch_cases"] = normalize_loopback(cases, {**base_urls, "closed": closed})  # 回环端口是每次运行随机的：不得进入可复现的证据
    run.extras["identity"] = identity

    # ---- HC-05（宿主内三项）
    answer = host.probe({"op": "config_roundtrip", **common})
    run.extras["config_rows"] = answer["result"]["rows"] if answer.get("ok") else None
    if not answer.get("ok"):
        run.extras["config_rows_error"] = answer.get("error")

    # ---- HC-08（行为 oracle：配置变化 -> 新构建的 provider 行为变化；回环请求日志）
    sc8 = run.results.get("HC-08") or run.scenario("HC-08")
    plans = {
        "disable_fc2db": {"sources": [{"id": "fc2db_net", "enabled": False, "base_url": "@loopback"}, {"id": "javdb", "base_url": "@loopback"}, {"id": "av123", "base_url": "@loopback"}]},
        "all_enabled_reordered": {"sources": [{"id": "av123", "base_url": "@loopback"}, {"id": "javdb", "base_url": "@loopback"}, {"id": "fc2db_net", "base_url": "@loopback"}]},
        "only_javdb_override": {"sources": [{"id": "fc2db_net", "enabled": False, "base_url": "@loopback"}, {"id": "javdb", "base_url": "@loopback"}, {"id": "av123", "enabled": False, "base_url": "@loopback"}]},
    }
    observed = {}
    loopback.reset()
    answer = host.probe({"op": "config_behavior", **common, "plans": [[plan_id, config, "FC2-PPV-4979299"] for plan_id, config in plans.items()]})
    if sc8.check(answer.get("ok"), f"config_behavior: {answer}"):
        segments = loopback.segments()
        for plan_id in plans:
            item = answer["result"]["plans"].get(plan_id, {})
            observed[plan_id] = {"counts": segments.get(plan_id, {}), "class": item.get("class"),
                                 "payload_sha256": canonical_hash(normalize_loopback(item.get("payload"), base_urls))}
    sc8.check(observed.get("disable_fc2db", {}).get("counts") == {"av123": 1, "javdb": 1}, f"a disabled source must get no request: {observed.get('disable_fc2db')}")
    sc8.check(observed.get("all_enabled_reordered", {}).get("counts") == {"av123": 1, "fc2db_net": 1, "javdb": 1}, f"all enabled: {observed.get('all_enabled_reordered')}")
    sc8.check(observed.get("only_javdb_override", {}).get("counts") == {"javdb": 1}, f"base_url override reaches the loopback fixture: {observed.get('only_javdb_override')}")
    sc8.check(len({item.get("payload_sha256") for item in observed.values()}) >= 2, "a config change must change the rebuilt provider's observable behaviour")
    sc8.record("behaviour_by_plan", {plan: {"counts": item.get("counts"), "class": item.get("class")} for plan, item in sorted(observed.items())})
    sc8.record("config_change_changes_behaviour", len({item.get("payload_sha256") for item in observed.values()}) >= 2)

    # ---- E16-A（A1-4）：传输可诱发的 kind，端到端；逐用例记录**实际观测**的 kind（来自 detail 词汇），标签不虚称
    e16a = e16a_table(run.extras["fetch_cases"])  # type: ignore[arg-type]
    run.extras["e16a"] = e16a
    for problem in evaluate_e16a(e16a):
        sc4.check(False, problem)
    sc4.record("e16a_actual_source_error_kind_by_case", {case: row["actual_source_error_kind"] for case, row in e16a.items()})
    sc4.record("e16a_observed_kinds", sorted({kind for row in e16a.values() for kind in row["actual_source_error_kind"]}))

    # ---- E16-B（A1-4）：全部 16 个 SourceErrorKind，在宿主进程内经生产 map_aggregation + 生产 provider 转换
    answer = host.probe({"op": "e16b", **common})
    run.extras["e16b"] = answer["result"] if answer.get("ok") else None
    if not answer.get("ok"):
        run.extras["e16b_error"] = answer.get("error")
    problems = evaluate_e16b(run.extras["e16b"])
    sc4.check(not problems, f"E16-B: {problems[:3]}{' ...' if len(problems) > 3 else ''} {run.extras.get('e16b_error')}")
    if not problems:
        outcomes = run.extras["e16b"]["kinds"]  # type: ignore[index]
        sc4.record("e16b_kind_count", len(outcomes))
        sc4.record("e16b_outcomes", dict(sorted(outcomes.items())))
        sc4.record("e16b_every_kind_went_through_the_production_mapping_and_provider_conversion", True)

    # ---- E16（原有要求，保持）：宿主 FailureReason 全部成员经桥分类是全函数且确定
    answer = host.probe({"op": "enumerations", **common})
    run.extras["enumerations"] = answer["result"] if answer.get("ok") else None
    if not answer.get("ok"):
        run.extras["enumerations_error"] = answer.get("error")
    enumeration = run.extras["enumerations"]
    if sc4.check(isinstance(enumeration, dict), f"E16 enumeration unavailable: {run.extras.get('enumerations_error')}"):
        bridge = enumeration["host_failure_reason_to_http_error"]
        expected_bridge = {name: ("HttpTimeoutError" if name == "TIMEOUT" else "HttpConnectionError" if name == "NETWORK" else "HttpTransportError") for name in bridge}
        sc4.check(bridge == expected_bridge, f"the bridge classification must be a total deterministic function of the structured reason: {bridge}")
        sc4.record("host_failure_reason_count", len(bridge))
        sc4.record("bridge_classification", dict(sorted(bridge.items())))

    # ---- 副作用：宿主的 CrawlerFactory 会为 PluginContext.data_dir 创建 plugins/<id>/（宿主行为）；adapter 不得往里写任何文件
    run.extras["stack_runtime_leftovers"] = adapter_written_files(host.work_dir / "stack")


def finish_config_scenario(run: HostRun) -> None:
    """HC-05：四个布尔（HTTP PATCH / validate_plugin_config / parse_settings / build）全真或全假；原始类型不得被强制转换后接受。"""
    sc = run.scenario("HC-05")
    rows, patch_ok = run.extras.get("config_rows"), run.extras.get("patch_ok")
    if not sc.check(isinstance(rows, dict) and isinstance(patch_ok, dict), f"config round-trip data missing: {run.extras.get('config_rows_error')}"):
        return
    table = {}
    for sample_id, _sample in run.oracle["config_samples"]:
        row = rows.get(sample_id, {})
        flags = {"patch": patch_ok.get(sample_id), "validate": row.get("validate"), "parse": row.get("parse"), "build": row.get("build")}
        consistent = len(set(flags.values())) == 1 and None not in flags.values()
        expected_valid = not sample_id.startswith(("invalid_", "raw_type_"))
        sc.check(consistent, f"{sample_id}: Pydantic / runtime parser / host route disagree: {flags}")
        sc.check(flags["patch"] is expected_valid, f"{sample_id}: expected accepted={expected_valid}, got {flags}")
        table[sample_id] = {"accepted": flags["patch"], "all_four_agree": consistent}
    sc.record("samples", table)
    run.extras["config_booleans"] = {sample: item["accepted"] for sample, item in table.items()}


# ------------------------------------------------------------------------------------------------ Group C：Core 升级（pin 变化）


def phase_core_upgrade(run: HostRun) -> None:
    art = run.art
    zip_b, wheel_b = art.pin_b()
    wheel_b_bytes = wheel_b.read_bytes()
    sc = run.scenario("HC-16")
    rows: list[dict] = run.extras.setdefault("admission_rows", [])  # type: ignore[assignment]
    host = run.host("core_upgrade")
    with host:
        data = host.data_dir
        place_sidecar(data, art.wheel_name, art.wheel_bytes)
        status, _ = host.upload(art.zip_bytes)
        sc.check(status == INSTALLED and host.plugin_ids() == [PLUGIN_ID], f"install the old pair: {status}")
        # 误操作 1：新 plugin（pin B）+ sidecar 里已放新 wheel，但旧 Core 仍在内存 -> RESTART
        place_sidecar(data, wheel_b.name, wheel_b_bytes)
        state_before = host_state(host)
        status, body = host.upload(zip_b)
        state_after = host_state(host)
        detail = body.get("detail") if isinstance(body, dict) else body
        restart = art.rejection("RESTART", version="0.1.1", wheel=wheel_b.name)
        sc.check(status == 422 and detail == restart, f"old Core in memory must give RESTART_TEMPLATE: {status} {detail!r}")
        sc.check(host.plugin_ids() == [PLUGIN_ID], "the installed old plugin must be unchanged by the rejected upload")
        rows.append(admission_row(run, "loaded_old_core_with_new_pin", mode="loaded", expected="FAIL", observed="FAIL" if status == 422 else "PASS", template="RESTART", before=state_before, after=state_after))
        sc.check(rows[-1]["sys_path_unchanged_on_fail"] and rows[-1]["sys_modules_unchanged_on_fail"], "RESTART failure must leave sys.path and Core objects untouched")
        # 正确流程：卸载 -> 重启 -> 只有旧 wheel（误操作 2）-> 放新 wheel -> 安装
        status, _ = host.api("DELETE", f"/api/plugins/{PLUGIN_ID}")
        sc.check(status == 204, "uninstall the old plugin")
        host.stop()
        host.start()
        clear_sidecar(data)
        place_sidecar(data, art.wheel_name, art.wheel_bytes)
        state_before = host_state(host)
        status, body = host.upload(zip_b)
        state_after = host_state(host)
        detail = body.get("detail") if isinstance(body, dict) else body
        wrong = art.rejection("WHEEL_VERSION_MISMATCH", version="0.1.1", wheel=wheel_b.name)
        sc.check(status == 422 and detail == wrong, f"only the old wheel in the sidecar must give WHEEL_VERSION_MISMATCH: {status} {detail!r}")
        rows.append(admission_row(run, "sidecar_only_old_wheel_with_new_pin", mode="wheel", expected="FAIL", observed="FAIL" if status == 422 else "PASS", template="WHEEL_VERSION_MISMATCH", before=state_before, after=state_after))
        place_sidecar(data, wheel_b.name, wheel_b_bytes)
        status, _ = host.upload(zip_b)
        sc.check(status == INSTALLED and host.plugin_ids() == [PLUGIN_ID], f"install the new pair after the restart: {status}")
        modules = host.probe({"op": "modules"})
        sc.check(modules.get("ok") and modules["result"]["core_archive_basename"] == wheel_b.name, "the new Core must be the one loaded")
        rows.append({"id": f"{run.spec.label}:new_pair_after_restart", "mode": "wheel", "python": run.spec.python_version, "expected": "PASS", "observed": "PASS" if status == INSTALLED else "FAIL",
                     "template": None, "sys_path_unchanged_on_fail": True, "sys_modules_unchanged_on_fail": True, "payload_executed": False})
        sc.record("misoperation_old_core_in_memory", {"http_status": 422, "template": "RESTART"})
        sc.record("misoperation_only_old_wheel", {"http_status": 422, "template": "WHEEL_VERSION_MISMATCH"})
        sc.record("upgrade_flow", "uninstall -> restart -> replace sidecar wheel -> install: success")
        sc.record("new_core_loaded", bool(modules.get("ok") and modules["result"]["core_archive_basename"] == wheel_b.name))


# ------------------------------------------------------------------------------------------------ 一台宿主的完整运行


def adapter_written_files(root: Path) -> list[str]:
    """``root`` 之下任意深度的 ``plugins/<id>/``（宿主为 ``PluginContext.data_dir`` 创建）里的文件，以及 ``plugins/`` 下除
    ``sources/`` / ``_ffcc_core/`` / ``<id>/`` 之外的任何条目。adapter 从不使用 ``context.data_dir``，所以结果必须为空（HC-18 / E19）。"""
    found: list[str] = []
    if not root.exists():
        return found
    for plugins_dir in sorted(path for path in root.rglob("plugins") if path.is_dir()):
        for item in plugins_dir.iterdir():
            if item.name in ("sources", "_ffcc_core"):
                continue
            if item.name == PLUGIN_ID and item.is_dir():
                found += [f"{PLUGIN_ID}/{child.relative_to(item).as_posix()}" for child in item.rglob("*") if child.is_file()]
            else:
                found.append(item.name)
    return sorted(found)


def hc18_scan_data_dir(run: HostRun, data_dir: Path) -> list[str]:
    return adapter_written_files(data_dir)


def run_host(spec: HostSpec, art: Artifacts, loopback, oracle: dict, work: Path, *, log=print, only_phases: set[str] | None = None) -> HostRun:
    """``only_phases``（mutation 的真实宿主杀手使用）：只执行指定阶段；``None`` = 完整运行（验收）。"""
    def wanted(name: str) -> bool:
        return only_phases is None or name in only_phases

    run = HostRun(spec=spec, work=work / spec.label, art=art, loopback=loopback, oracle=oracle)
    run.work.mkdir(parents=True, exist_ok=True)
    roots = {"repo": REPO_ROOT, "host_install": Path(spec.install_dir)}
    before = snapshot_roots(roots, excludes=((REPO_ROOT / "docs" / "acceptance" / "evidence").as_posix(),))

    def guarded(name: str, function, *args) -> None:
        try:
            function(*args)
        except Exception as exc:  # noqa: BLE001 - 网关把任何阶段异常记为相关场景失败，而不是崩溃
            log(f"{spec.label}: phase {name} raised {type(exc).__name__}: {exc}")
            run.extras.setdefault("phase_errors", {})[name] = f"{type(exc).__name__}: {str(exc)[:300]}"  # type: ignore[index]

    if wanted("failures") or wanted("success"):
        log(f"{spec.label}: lifecycle")
        host = run.host("lifecycle")
        try:
            host.start()
            described = host.probe({"op": "describe"})
            if described.get("ok"):
                spec.python_version = described["result"]["python"]
                run.extras["frozen_flag"] = described["result"]["frozen"]
            if wanted("failures"):
                guarded("failures", phase_failures, run, host)
            if wanted("success"):
                guarded("success", phase_success, run, host)
                run.extras["lifecycle_plugins_leftovers"] = hc18_scan_data_dir(run, host.data_dir)
        except GateError as exc:
            run.extras.setdefault("phase_errors", {})["lifecycle"] = str(exc)[:400]  # type: ignore[index]
        finally:
            host.stop()
    if wanted("own_stack"):
        log(f"{spec.label}: controlled stack")
        host = run.host("own_stack")
        try:
            host.start()
            guarded("own_stack", phase_own_stack, run, host)
        except GateError as exc:
            run.extras.setdefault("phase_errors", {})["own_stack"] = str(exc)[:400]  # type: ignore[index]
        finally:
            host.stop()
        if "patch_ok" in run.extras:
            finish_config_scenario(run)
    if wanted("core_upgrade"):
        log(f"{spec.label}: core upgrade")
        guarded("core_upgrade", phase_core_upgrade, run)
    if spec.form == "source" and wanted("admission"):
        log(f"{spec.label}: admission matrix")
        guarded("admission", phase_admission, run)
    if only_phases is None:
        finish_side_effects(run, before, roots)
        finish_admission(run)
    return run


# ------------------------------------------------------------------------------------------------ HC-19：Core 来源准入矩阵（宿主级）


def _in_host_module():
    return _load_module(HOST_SCRIPTS / "in_host.py", "ffcc_gate_in_host_constants")


def evaluate_admission_case(art: Artifacts, case: str, expected: str, template: str | None, row: dict) -> list[str]:
    """一个宿主内准入用例的判据（E31 / HC-19）；返回违反项列表。"""
    problems = []
    if row.get("outcome") != expected:
        return [f"outcome {row.get('outcome')!r} != {expected!r}: {row.get('message')}"]
    if expected == "FAIL":
        if row.get("message") != art.rejection(template):
            problems.append(f"message differs from the frozen template {template}: {row.get('message')!r}")
        for key in ("path_equals_entry", "path_same_object", "cache_unchanged", "core_objects_unchanged"):
            if row.get(key) is not True:
                problems.append(f"{key} is {row.get(key)!r}")
        if row.get("installed_tree_exists") or row.get("half_install_residue"):
            problems.append(f"half install: {row.get('half_install_residue')}")
    else:
        if row.get("loaded_from_exact_wheel") is not True:
            problems.append("Core must be loaded from the exact pinned wheel via zipimporter")
        if row.get("wheel_entries_in_path", 0) > 1:
            problems.append("at most one wheel entry in sys.path")
    if row.get("sentinel_exists"):
        problems.append("a payload sentinel exists: unsupported code was executed")
    if case == "e31l_rollback_cache_present" and row.get("cache_entry_is_original_object") is not True:
        problems.append("the entry importer-cache object must be restored")
    if case == "e31u_wheel_in_path_resolution_disagrees" and row.get("inert_package_never_imported") is not True:
        problems.append("the unsupported (inert) package must never be imported")
    return problems


def phase_admission(run: HostRun) -> None:
    """源码宿主：真实 ``install_plugin_zip`` + 宿主进程内夹具（in_host.op_admission），再加真实 ``PYTHONPATH`` 环境的两个用例。"""
    art = run.art
    module = _in_host_module()
    rows: list[dict] = run.extras.setdefault("admission_rows", [])  # type: ignore[assignment]
    sc = run.scenario("HC-19-host")
    host = run.host("admission")
    with host:
        answer = host.probe({"op": "admission", "work": str(host.work_dir / "adm"), "zip_path": str(art.zip_path), "wheel_path": str(art.wheel_path)})
    if not sc.check(answer.get("ok"), f"admission probe failed: {answer}"):
        return
    cases = answer["result"]["cases"]
    observed_cases = {}
    for case, (expected, template) in module.ADMISSION_EXPECT.items():
        row = cases.get(case, {"outcome": "MISSING"})
        problems = evaluate_admission_case(art, case, expected, template, row)
        sc.check(not problems, f"{case}: {problems}")
        observed_cases[case] = {"expected": expected, "observed": row.get("outcome"), "template": template if expected == "FAIL" and not problems else None}
        rows.append({
            "id": f"{run.spec.label}:{case}", "mode": "loaded" if case.startswith(("preloaded", "mixed")) else "directory" if case.startswith("dir_") else "shadow" if case.startswith(("shadow", "e31")) else "wheel",
            "python": run.spec.python_version, "expected": expected, "observed": row.get("outcome") if not problems else f"MISMATCH:{row.get('outcome')}", "template": template,
            "sys_path_unchanged_on_fail": row.get("path_equals_entry") is not False, "sys_modules_unchanged_on_fail": row.get("core_objects_unchanged") is not False,
            "payload_executed": bool(row.get("sentinel_exists")),
        })
    sc.record("cases", observed_cases)

    # ---- 真实 PYTHONPATH：宿主进程启动时 sys.path 就带有目录形态 Core（含 .pyc PoC）
    poc = module._pyc_poc_dir(run.work / "pythonpath_dir", run.work / "pythonpath_sentinel")
    sentinel = run.work / "pythonpath_sentinel"
    host = run.host("pythonpath", extra_env={"PYTHONPATH": poc})
    with host:
        watch = host.probe({"op": "paths", "watch": [poc]})
        sc.check(watch.get("ok") and watch["result"]["present"][os.path.normcase(os.path.realpath(poc))], "the PYTHONPATH directory must be on the host's sys.path (fixture is effective)")
        state_before = host_state(host)
        status, body = host.upload(art.zip_bytes)
        state_after = host_state(host)
        detail = body.get("detail") if isinstance(body, dict) else body
        sc.check(status == 422 and detail == art.rejection("UNVERIFIABLE") and not sentinel.exists() and host.plugin_ids() == [], f"PYTHONPATH directory Core without sidecar: {status} {detail!r}")
        rows.append(admission_row(run, "pythonpath_pyc_poc_no_sidecar", mode="directory", expected="FAIL", observed="FAIL" if status == 422 else "PASS", template="UNVERIFIABLE", before=state_before, after=state_after))
        place_sidecar(host.data_dir, art.wheel_name, art.wheel_bytes)
        status, _ = host.upload(art.zip_bytes)
        modules = host.probe({"op": "modules"})
        sc.check(status == INSTALLED and modules.get("ok") and modules["result"]["core_archive_basename"] == art.wheel_name and not sentinel.exists(), "with a valid sidecar the wheel (not the PYTHONPATH directory) must be loaded; the payload must not run")
        rows.append({"id": f"{run.spec.label}:pythonpath_pyc_poc_with_sidecar", "mode": "directory", "python": run.spec.python_version, "expected": "PASS", "observed": "PASS" if status == INSTALLED else "FAIL",
                     "template": None, "sys_path_unchanged_on_fail": True, "sys_modules_unchanged_on_fail": True, "payload_executed": sentinel.exists()})
        sc.record("pythonpath_no_sidecar", {"http_status": 422, "template": "UNVERIFIABLE", "payload_executed": sentinel.exists()})
        sc.record("pythonpath_with_sidecar", {"http_status": INSTALLED, "loaded_from_exact_wheel": bool(modules.get("ok") and modules["result"]["core_archive_basename"] == art.wheel_name)})


def finish_side_effects(run: HostRun, before: dict, roots: dict[str, Path]) -> None:
    sc = run.scenario("HC-18")
    after = snapshot_roots(roots, excludes=((REPO_ROOT / "docs" / "acceptance" / "evidence").as_posix(),))
    difference = snapshot_diff(before, after)
    sc.check(not difference, f"files outside the temporary data directory changed: {difference}")
    sc.check(run.extras.get("lifecycle_plugins_leftovers") == [], f"the adapter wrote files under plugins/: {run.extras.get('lifecycle_plugins_leftovers')}")
    sc.check(run.extras.get("stack_runtime_leftovers") == [], f"the controlled stack's adapter wrote files: {run.extras.get('stack_runtime_leftovers')}")
    sc.record("changes_outside_data_dir", sorted(difference))
    sc.record("files_written_by_the_adapter", sorted(set(run.extras.get("lifecycle_plugins_leftovers") or []) | set(run.extras.get("stack_runtime_leftovers") or [])))
    sc.record("runtime_dir_plugins_id_is_created_by_the_host_not_the_adapter", True)
    sc.record("plugin_tree_written_only_by_the_host_under_sources", True)


def finish_admission(run: HostRun) -> None:
    sc = run.scenario("HC-19")
    for dependency in ("HC-10", "HC-11", "HC-16"):
        sc.check(dependency in run.results and not run.results[dependency].failures, f"{dependency} (sidecar branches) must pass")
    sc.check("HC-01" in run.results and not run.results["HC-01"].failures, "the exact pinned wheel must install (PASS branch)")
    if run.spec.form == "source":
        host_part = run.results.get("HC-19-host")
        sc.check(host_part is not None and not host_part.failures, f"in-host admission matrix: {host_part.failures if host_part else 'not run'}")
        sc.record("scope", "sidecar branches over HTTP + in-host E31 matrix (real install_plugin_zip) + real PYTHONPATH cases")
        sc.record("in_host_cases", sorted((host_part.observations.get("cases") or {}).keys()) if host_part else [])
    else:
        sc.record("scope", "sidecar branches over HTTP only (frozen hosts cannot stage sys.path fixtures in the host process; E31-u / E31-v are covered by the source hosts and the unit matrix)")
    run.results.pop("HC-19-host", None)
    rows = run.extras.get("admission_rows", [])
    sc.record("sidecar_cases", sorted(run.extras.get("hc11_sidecar_cases", {})))
    def legal_unavailable(row: dict) -> bool:
        return row["observed"] == ENV_UNAVAILABLE and row["id"].endswith(":" + SYMLINK_CASE) and row.get("symlink_privilege") is False
    sc.check(all(row["observed"] == row["expected"] or legal_unavailable(row) for row in rows), f"admission rows mismatch: {[row['id'] for row in rows if row['observed'] != row['expected'] and not legal_unavailable(row)]}")
    symlink_rows = [row for row in rows if row["id"].endswith(":" + SYMLINK_CASE)]
    sc.check(len(symlink_rows) == 1, f"exactly one symlink sub-case row per host: {len(symlink_rows)}")
    if symlink_rows:
        # A1-3：不得把未执行的真实宿主子项表述为 PASS
        sc.record("real_host_symlink_subcase", symlink_rows[0]["observed"])
        sc.record("symlink_privilege", symlink_rows[0].get("symlink_privilege"))
    sc.record("admission_row_count", len(rows))


# ------------------------------------------------------------------------------------------------ 跨版本等价（E15 / E16）与 MATRIX Part A 装配


def parity_payload(run: HostRun) -> dict:
    e16b = run.extras.get("e16b") or {}
    return {
        "fetch_cases": run.extras.get("fetch_cases"),
        "e16a_actual_source_error_kind": run.extras.get("e16a"),
        "e16b_kind_outcomes": e16b.get("kinds"),
        "hc12_variant_statuses": run.extras.get("hc12"),
        "config_booleans": run.extras.get("config_booleans"),
        "descriptor_subset": run.extras.get("descriptor"),
        "config_schema_sha256": run.extras.get("config_schema_sha256"),
        "hc13_wrong_id_behaviour": run.extras.get("hc13"),
        "identity": {key: value for key, value in (run.extras.get("identity") or {}).items() if key != "provider_class"},
    }


def build_parity(runs: dict[str, HostRun]) -> dict:
    pairs = []
    for left, right in (("a-src", "b-src"), ("a-win", "b-win"), ("a-src", "a-win"), ("b-src", "b-win")):
        if left not in runs or right not in runs:
            continue
        one, two = parity_payload(runs[left]), parity_payload(runs[right])
        sha_a, sha_b = canonical_hash(one), canonical_hash(two)
        complete = all(value is not None for value in (*one.values(), *two.values()))  # 缺失的字段不得被当作“相等”
        if not complete:
            sha_b = canonical_hash({"incomplete_parity_payload": True, "right": two})
        pairs.append({"a": left, "b": right, "fields": sorted(one), "equal": complete and sha_a == sha_b, "sha256_a": sha_a, "sha256_b": sha_b})
    members = {label: tuple((run.extras.get("enumerations") or {}).get("host_failure_reason_members") or ()) for label, run in runs.items()}
    observed = ["DIFF-01"]
    if len(set(members.values())) > 1:
        observed.append("DIFF-05")
    if len({run.spec.form for run in runs.values()}) > 1:
        observed.append("DIFF-07")
    return {"required_pairs": pairs, "allowed_diffs_observed": sorted(observed), "e16": build_e16(runs)}


def build_e16(runs: dict[str, "HostRun"]) -> dict:
    """Matrix Part A ``parity.e16``：E16-A 实际观测 kind + E16-B 全部 16 个 kind，逐必需宿主取哈希；四宿主必须相等。"""
    labels = [label for label in REQUIRED_LABELS if label in runs]
    a_tables = {label: runs[label].extras.get("e16a") for label in labels}
    b_results = {label: runs[label].extras.get("e16b") for label in labels}
    reference = labels[0] if labels else None
    a_ref = a_tables.get(reference) or {}
    b_ref = (b_results.get(reference) or {}).get("kinds") or {}
    a_hash = {label: canonical_hash(a_tables[label]) for label in labels}
    b_hash = {label: canonical_hash((b_results[label] or {}).get("kinds")) for label in labels}
    return {
        "e16_a": {
            "observed_kinds": sorted({kind for row in a_ref.values() for kind in row["actual_source_error_kind"]}), "cases": a_ref,
            "per_host_sha256": a_hash, "equal": bool(labels) and len(set(a_hash.values())) == 1 and all(a_tables.values()),
        },
        "e16_b": {
            "kind_count": len(b_ref), "outcomes": b_ref, "per_host_sha256": b_hash,
            "equal": bool(labels) and len(set(b_hash.values())) == 1 and all(b_results.values()),
            "production_path_verified_on_hosts": sorted(label for label in labels if not evaluate_e16b(b_results[label])),
        },
    }


def host_row(run: HostRun) -> dict:
    spec = run.spec
    scenarios = []
    for scenario_id in SCENARIO_IDS:
        scenario = run.results.get(scenario_id)
        if scenario is None:
            scenarios.append({"id": scenario_id, "passed": False, "observations_sha256": canonical_hash({"missing": scenario_id})})
        else:
            scenarios.append({"id": scenario_id, "passed": not scenario.failures, "observations_sha256": canonical_hash(scenario.observations)})
    return {
        "label": spec.label, "coordinate_id": spec.coordinate_id, "role": coordinate(spec.coordinate_id)["role"], "form": spec.form,
        "tag": spec.tag, "tag_object": spec.tag_object, "peeled_commit": spec.peeled_commit, "release_version": spec.release_version,
        "requires_python": spec.requires_python, "plugin_api_version": spec.plugin_api_version, "python_version": spec.python_version,
        "platform": spec.platform, "api_fingerprint_sha256": spec.api_fingerprint_sha256,
        "adapter_used_subset_fingerprint_sha256": spec.adapter_used_subset_fingerprint_sha256, "deps_lock_sha256": spec.deps_lock_sha256,
        "identical_to_stable": False, "scenarios": scenarios,
    }


def build_part_a(runs: dict[str, HostRun], stage1: dict, *, main_commit: str, stable_commit: str, stable_spec: HostSpec | None) -> dict:
    hosts = [host_row(run) for run in runs.values()]
    parity = build_parity(runs)
    if stable_spec is not None:
        main_row = {
            "label": "main", "coordinate_id": "SC-05", "role": "informational", "form": "source", "tag": "main", "tag_object": None,
            "peeled_commit": main_commit, "release_version": stable_spec.release_version, "requires_python": stable_spec.requires_python,
            "plugin_api_version": stable_spec.plugin_api_version, "python_version": stable_spec.python_version, "platform": PLATFORM_WINDOWS,
            "api_fingerprint_sha256": stable_spec.api_fingerprint_sha256, "adapter_used_subset_fingerprint_sha256": stable_spec.adapter_used_subset_fingerprint_sha256,
            "deps_lock_sha256": None, "identical_to_stable": main_commit == stable_commit, "scenarios": [],
        }
        if main_commit == stable_commit:
            hosts.append(main_row)
    parity_equal = bool(parity["required_pairs"]) and all(pair["equal"] for pair in parity["required_pairs"])
    status = [derive_status(item["id"], hosts, parity_equal=parity_equal, stable_peeled_commit=stable_commit) for item in SUPPORT_COORDINATES]
    rows = [row for run in runs.values() for row in run.extras.get("admission_rows", [])]
    gate_hash = sha256_hex(Path(__file__).read_bytes().replace(b"\r\n", b"\n"))
    return {
        "schema_version": SCHEMA_VERSION,
        "tool": {"name": "run_amane_compat_gate", "sha256": gate_hash},
        "policy": {
            "minimum": "v0.15.0", "main_role": "informational",
            "stable_definition": "latest non-draft non-prerelease GitHub Release whose tag is v<semver>; app-* and main do not qualify",
            "support_coordinates": [dict(item) for item in SUPPORT_COORDINATES],
        },
        "hosts": hosts,
        "artifacts": dict(stage1["artifacts"]),
        "parity": parity,
        "status": status,
        "platforms_unverified": list(PLATFORMS_UNVERIFIED),
        "core_admission": {"core_wheel_sha256": stage1["artifacts"]["core_wheel_sha256"], "cases": sorted(rows, key=lambda item: item["id"])},
    }


# ------------------------------------------------------------------------------------------------ 命令行


def build_oracle() -> dict:
    """C1 冻结记录（P5_C1_HOST_WITNESS.json）作为 HC-03 / HC-04 的 oracle。"""
    witness = json.loads((REPO_ROOT / "docs" / "acceptance" / "evidence" / "P5_C1_HOST_WITNESS.json").read_text(encoding="utf-8"))
    by_id = {item["id"]: item["observations"] for item in witness["scenarios"]}
    descriptor = {key: by_id["H-02"]["zip"]["descriptor"][key] for key in DESCRIPTOR_KEYS}
    return {
        "descriptor": descriptor_subset(descriptor),
        "schema_fields": by_id["H-02"]["zip"]["schema_fields"],
        "h07_metadata": by_id["H-07"]["metadata"],
        "config_samples": [list(item) for item in _in_host_module().CONFIG_SAMPLES],
    }


def _git(repo: Path, *args: str) -> str:
    completed = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, encoding="utf-8", check=False)
    if completed.returncode != 0:
        raise GateError(f"git {' '.join(args)} failed: {completed.stderr[-300:]}")
    return completed.stdout.strip()


def load_specs(hosts_json: Path, amane_repo: Path | None) -> tuple[dict[str, HostSpec], str, str]:
    import tomllib

    prepared = json.loads(hosts_json.read_text(encoding="utf-8"))
    compare = _tool("compare_amane_api.py")
    adapter_tree = REPO_ROOT / "adapters" / "amane" / "fc2_amane_adapter"
    specs: dict[str, HostSpec] = {}
    for label, tag, form, coordinate_id in (("a-src", "v0.15.0", "source", "SC-03"), ("b-src", "v0.18.0", "source", "SC-04"), ("a-win", "v0.15.0", "frozen-desktop", "SC-01"), ("b-win", "v0.18.0", "frozen-desktop", "SC-02")):
        entry = prepared.get(tag)
        if entry is None:
            continue
        source = Path(entry["source_dir"])
        project = tomllib.loads((source / "pyproject.toml").read_text(encoding="utf-8"))["project"]
        manifest = json.loads((REPO_ROOT / "adapters" / "amane" / "api_manifest" / f"amane_{tag}_api_manifest.json").read_text(encoding="utf-8"))
        if manifest["amane"]["commit"] != entry["peeled_commit"]:
            raise GateError(f"{tag}: committed API manifest commit differs from the prepared checkout")
        subset = compare.compare({tag: manifest}, adapter_tree)["adapter_used_subset_fingerprints"][tag]
        specs[label] = HostSpec(
            label=label, coordinate_id=coordinate_id, form=form, tag=tag, tag_object=entry["tag_object"], peeled_commit=entry["peeled_commit"],
            release_version=str(project["version"]), requires_python=str(project["requires-python"]), plugin_api_version=str(manifest["constants"]["PLUGIN_API_VERSION"]),
            python_version=entry.get("python_version", "unknown") if form == "source" else "3.14.7",
            executable=entry["venv_python"] if form == "source" else entry["frozen_exe"],
            install_dir=entry["source_dir"] if form == "source" else entry["frozen_dir"],
            deps_lock_sha256=entry.get("deps_lock_sha256") if form == "source" else None,
            api_fingerprint_sha256=compare.full_fingerprint(manifest), adapter_used_subset_fingerprint_sha256=subset,
        )
    stable_commit = prepared["v0.18.0"]["peeled_commit"] if "v0.18.0" in prepared else ""
    main_commit = _git(amane_repo, "rev-parse", "origin/main") if amane_repo is not None else ""
    return specs, stable_commit, main_commit


def cmd_run(options) -> int:
    release = _tool("build_amane_release.py")
    wheel = options.core_wheel.resolve()
    stage1 = release.build_stage1(REPO_ROOT, wheel)
    for name, data in stage1["files"].items():
        if (options.stage1_dir / name).read_bytes() != data:
            raise GateError(f"{name}: the stage1 directory differs from a fresh rebuild; refusing to validate non-accepted bytes")
    work = options.work.resolve()
    if REPO_ROOT in work.parents:
        raise GateError("--work must be outside the repository")
    work.mkdir(parents=True, exist_ok=True)
    specs, stable_commit, main_commit = load_specs(options.hosts_json, options.amane_repo)
    wanted = [label for label in ("a-src", "b-src", "a-win", "b-win") if (not options.labels or label in options.labels) and label in specs]
    loopback_module = _load_module(HOST_SCRIPTS / "loopback_fixture.py", "ffcc_gate_loopback")
    oracle = build_oracle()
    art = Artifacts(wheel, options.stage1_dir.resolve(), work / "artifacts")
    (work / "artifacts").mkdir(parents=True, exist_ok=True)
    runs: dict[str, HostRun] = {}
    with loopback_module.LoopbackFixture(REPO_ROOT / "tests" / "fixtures" / "sources") as loopback:
        for label in wanted:
            started = time.time()
            runs[label] = run_host(specs[label], art, loopback, oracle, work, log=lambda message: print(message, file=sys.stderr, flush=True))
            failed = [(item.id, item.failures) for item in runs[label].results.values() if item.failures]
            print(f"{label}: {sum(1 for item in runs[label].results.values() if not item.failures)}/{len(runs[label].results)} scenarios passed in {time.time() - started:.0f}s", file=sys.stderr, flush=True)
            for scenario_id, failures in failed:
                print(f"  {label} {scenario_id} FAILED: {failures[:3]}", file=sys.stderr, flush=True)
            for phase, error in (runs[label].extras.get("phase_errors") or {}).items():  # type: ignore[union-attr]
                print(f"  {label} phase {phase}: {error}", file=sys.stderr, flush=True)
    stable_spec = next((spec for spec in specs.values() if spec.tag == "v0.18.0" and spec.form == "source"), None)
    part_a = build_part_a(runs, stage1, main_commit=main_commit, stable_commit=stable_commit, stable_spec=stable_spec)
    problems = validate_matrix(part_a)
    for problem in problems:
        print(f"matrix problem: {problem}", file=sys.stderr)
    if options.details is not None:
        details = {label: {scenario.id: {"observations": scenario.observations, "failures": scenario.failures} for scenario in run.results.values()} for label, run in runs.items()}
        extras = {label: {key: value for key, value in run.extras.items() if key in ("phase_errors", "fetch_cases", "e16a", "e16b", "e16b_error", "hc12", "enumerations", "enumerations_error", "config_rows_error", "config_booleans", "identity", "admission_rows")} for label, run in runs.items()}
        options.details.parent.mkdir(parents=True, exist_ok=True)
        options.details.write_text(json.dumps({"scenarios": details, "extras": extras}, indent=1, sort_keys=True, ensure_ascii=False, default=repr), encoding="utf-8")
    options.out.parent.mkdir(parents=True, exist_ok=True)
    options.out.write_text(render(part_a), encoding="utf-8", newline="\n")
    all_passed = all(not item.failures for run in runs.values() for item in run.results.values())
    print(f"matrix Part A written; sha256={sha256_hex(render(part_a).encode('utf-8'))}; all_scenarios_passed={all_passed}; problems={len(problems)}", file=sys.stderr)
    return 0 if all_passed and not problems else 1


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "run":
        parser = argparse.ArgumentParser(prog="run_amane_compat_gate.py run")
        parser.add_argument("--hosts-json", required=True, type=Path, help="tools/prepare_amane_hosts.py 的输出")
        parser.add_argument("--core-wheel", required=True, type=Path)
        parser.add_argument("--stage1-dir", required=True, type=Path)
        parser.add_argument("--work", required=True, type=Path, help="临时工作目录（必须在仓库之外）")
        parser.add_argument("--amane-repo", type=Path, help="本地 upstream 克隆（用于判定 main 是否 == 稳定版）")
        parser.add_argument("--labels", nargs="*", default=[])
        parser.add_argument("--out", required=True, type=Path)
        parser.add_argument("--details", type=Path, help="（诊断，不入库）每个场景的完整观测与失败原因")
        return cmd_run(parser.parse_args(argv[1:]))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--validate", type=Path, help="校验一份 MATRIX JSON 的 schema 与自洽规则")
    options = parser.parse_args(argv)
    if options.validate is not None:
        problems = validate_matrix(json.loads(options.validate.read_text(encoding="utf-8")))
        for problem in problems:
            print(problem, file=sys.stderr)
        return 1 if problems else 0
    parser.error("nothing to do")
    return 2


if __name__ == "__main__":
    sys.exit(main())
