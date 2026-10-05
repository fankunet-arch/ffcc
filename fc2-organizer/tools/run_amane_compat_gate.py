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
    for item in admission["cases"]:
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


def main(argv: list[str] | None = None) -> int:
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
