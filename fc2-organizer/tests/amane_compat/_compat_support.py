"""P5-C2 测试共享支撑（不是 pytest 文件）：路径、工具加载、解释器发现、locator 用例运行与统一期望表。

主进程从不 import ``amane``，也从不 import ``fc2_metadata_core`` 之外的宿主代码；
locator 用例一律在子进程（``_locator_harness.py``）中执行。
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

#: mutation 测试通过环境变量把整个“被测仓库”换成带补丁的临时副本（见 test_amane_compat_mutation_nonvacuity.py）；
#: 缺省 = 本文件所在的真实仓库。
REAL_REPO = Path(__file__).resolve().parents[2]
REPO = Path(os.environ.get("FFCC_C2_REPO_ROOT") or REAL_REPO)
TOOLS = REPO / "tools"
SHIM_DIR = REPO / "adapters" / "amane" / "shim"
ADAPTER_TREE = REPO / "adapters" / "amane" / "fc2_amane_adapter"
HARNESS = Path(__file__).resolve().parent / "_locator_harness.py"
MARK = "@@CASE@@"

PIN_CORE_VERSION = "0.1.0"

#: 合同第 8.3 节冻结的 4 个模板（测试里**独立**硬编码；``<CORE_*>`` 以 pin 字面量代入，``<Amane 数据目录>`` 保持字面）。
TEMPLATES = {
    "RESTART": "FC2 Metadata Core 已加载的版本与插件不配对（或无法验证）：请先卸载旧版插件并重启 Amane，再安装与之配对的新版（需要 Core {version}）",
    "UNVERIFIABLE": "FC2 Metadata Core 的来源不受支持或无法验证（已拒绝加载）：请把官方发布包中的 {wheel} 放入 <Amane 数据目录>/plugins/_ffcc_core/，不要使用 pip / 源码 / editable 形态的 Core",
    "WHEEL_VERSION_MISMATCH": "FC2 Metadata Core 随附包版本与插件不配对：请在 <Amane 数据目录>/plugins/_ffcc_core/ 中放入 {wheel}",
    "WHEEL_HASH_MISMATCH": "FC2 Metadata Core 随附包校验失败（sha256 与插件配对记录不一致）：请重新获取官方发布包中的 {wheel}",
}


def render_template(key: str) -> str:
    return TEMPLATES[key].format(version=PIN_CORE_VERSION, wheel=f"fc2_metadata_core-{PIN_CORE_VERSION}-py3-none-any.whl")


def load_tool(filename: str):
    """按文件路径加载 ``tools/`` 下的脚本（不修改 ``sys.path`` / ``pyproject``）。"""
    name = "ffcc_tool_" + Path(filename).stem
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, TOOLS / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def find_python314() -> str | None:
    explicit = os.environ.get("FFCC_PY314")
    if explicit and Path(explicit).exists():
        return explicit
    for command in (["py", "-3.14", "-c", "import sys;print(sys.executable)"],):
        try:
            completed = subprocess.run(command, capture_output=True, text=True, timeout=30, check=False)
        except (OSError, subprocess.SubprocessError):
            continue
        path = completed.stdout.strip()
        if completed.returncode == 0 and path and Path(path).exists():
            return path
    return shutil.which("python3.14")


def interpreters() -> list[tuple[str, str | None]]:
    """E31-s：主套件解释器（3.12）与 3.14。找不到 3.14 -> 对应用例**失败**（不是 skip）。"""
    return [("main", sys.executable), ("py314", find_python314())]


def run_case(python: str, case: str, work: Path, wheel: Path, *, locator: Path | None = None) -> dict:
    command = [python, "-S", str(HARNESS), "--case", case, "--work", str(work), "--wheel", str(wheel), "--repo", str(REPO)]
    if locator is not None:
        command += ["--locator", str(locator)]
    # 隔离：``-S`` 不加载 site（避免宿主环境里的 editable / .pth Core 干扰），并清掉可能注入 sys.path 的环境变量。
    env = {key: value for key, value in os.environ.items() if key not in ("PYTHONPATH", "PYTHONSTARTUP", "PYTHONHOME", "FFCC_REEXEC")}
    completed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300, check=False, env=env)
    for line in completed.stdout.splitlines():
        if line.startswith(MARK):
            return json.loads(line[len(MARK):])
    raise AssertionError(f"case {case} produced no observation (exit {completed.returncode}):\n{completed.stdout[-800:]}\n{completed.stderr[-1200:]}")


RESTORED = {
    "path_equals_entry": True,
    "path_same_object": True,
    "cache_keys_equal_entry": True,
    "cache_same_objects": True,
    "core_modules_unchanged": True,
    "locator_imported_core": False,
    "sentinel_exists": False,
}


def fail(template: str, **extra) -> dict:
    return {"outcome": "FAIL", "template": template, "message": render_template(template), **RESTORED, **extra}


def no_change_pass(**extra) -> dict:
    return {"outcome": "PASS", "message": "", "path_mutations": 0, **RESTORED, **extra}


#: case id -> 期望观测（所有键必须相等）。同一张表既用于 E31 单元层，也用于 mutation killer 判定。
EXPECT: dict[str, dict] = {
    "a_loaded_exact_wheel": no_change_pass(),
    "b_loaded_wrong_version_wheel": fail("RESTART"),
    "c_loaded_tampered_same_name_wheel": fail("RESTART"),
    "d_loaded_directory_pip_target": fail("RESTART"),
    "e_loaded_editable_source": fail("RESTART"),
    "f_unloaded_directory_pip_target_no_sidecar": fail("UNVERIFIABLE", core_modules_added=[]),
    "f_unloaded_directory_editable_no_sidecar": fail("UNVERIFIABLE", core_modules_added=[]),
    "f_unloaded_source_checkout_no_sidecar": fail("UNVERIFIABLE", core_modules_added=[]),
    "f_unloaded_pythonpath_directory_no_sidecar": fail("UNVERIFIABLE", core_modules_added=[]),
    "g_directory_core_with_valid_sidecar_loads_wheel": {
        "outcome": "PASS", "path_mutations": 1, "wheel_index_in_path": 0, "wheel_count_in_path": 1,
        "loaded_archive_is_wheel": True, "loaded_loader_type": "zipimporter", "sentinel_exists": False, "locator_imported_core": False,
    },
    "h0_pyc_poc_control_payload_runs_without_locator": {"outcome": "CONTROL", "sentinel_exists": True},
    "h1_pyc_poc_directory_no_sidecar": fail("UNVERIFIABLE", core_modules_added=[]),
    "h2_pyc_poc_directory_with_valid_sidecar_loads_wheel": {
        "outcome": "PASS", "path_mutations": 1, "wheel_index_in_path": 0, "loaded_archive_is_wheel": True,
        "loaded_loader_type": "zipimporter", "sentinel_exists": False, "locator_imported_core": False,
    },
    "h3_loaded_directory_with_benign_pyc": fail("RESTART"),
    "i_sidecar_tampered_one_byte": fail("WHEEL_HASH_MISMATCH"),
    "i_sidecar_symlink": fail("WHEEL_HASH_MISMATCH"),
    "i_sidecar_oversize": fail("WHEEL_HASH_MISMATCH"),
    "i_sidecar_same_name_directory": fail("WHEEL_HASH_MISMATCH"),
    "i_sidecar_only_other_version_wheel": fail("WHEEL_VERSION_MISMATCH"),
    "j_mixed_submodule_other_archive": fail("RESTART"),
    "j_mixed_submodule_directory_origin": fail("RESTART"),
    "j_mixed_submodule_no_spec": fail("RESTART"),
    "j_mixed_submodule_namespace_package": fail("RESTART"),
    "j_mixed_submodule_subclass_loader": fail("RESTART"),
    "k_shadow_meta_path_finder_with_valid_sidecar": fail("UNVERIFIABLE", path_mutations=0),
    "k_shadow_meta_path_finder_no_sidecar": fail("UNVERIFIABLE", path_mutations=0),
    "l1_rollback_after_insertion_cache_absent_at_entry": fail("UNVERIFIABLE", entry_cache_had_wheel=False),
    "l2_rollback_after_insertion_cache_present_at_entry": fail("UNVERIFIABLE", entry_cache_had_wheel=True, cache_entry_is_original_object=True),
    "m_sidecar_same_name_directory_with_directory_core": fail("WHEEL_HASH_MISMATCH"),
    "o_no_core_no_sidecar": no_change_pass(),
    "o_empty_sidecar_directory": no_change_pass(),
    "o_module_file_outside_plugins_sources": no_change_pass(),
    "p_success_single_insertion_and_idempotent_with_final_resolution": {
        "outcome": "PASS", "path_mutations": 1, "wheel_index_in_path": 0, "wheel_count_in_path": 1,
        "second_outcome": "PASS", "second_path_equals_first": True, "second_path_mutations": 0, "second_wheel_count": 1,
        "loaded_archive_is_wheel": True, "sentinel_exists": False,
    },
    "p_success_from_staging_module_file": {"outcome": "PASS", "path_mutations": 1, "wheel_index_in_path": 0, "wheel_count_in_path": 1, "locator_imported_core": False},
    "u_existing_wheel_but_resolution_disagrees": fail("UNVERIFIABLE", inert_package_never_imported=True),
    "u_existing_wheel_first_and_resolution_matches": {
        "outcome": "PASS", "path_equals_entry": True, "path_same_object": True, "path_mutations": 0, "wheel_index_in_path": 0,
        "wheel_count_in_path": 1, "core_modules_unchanged": True, "locator_imported_core": False, "sentinel_exists": False,
    },
    "v_subclass_loader_double_in_final_resolution": fail("UNVERIFIABLE"),
    "v_subclass_loader_double_in_pre_resolution": fail("UNVERIFIABLE", path_mutations=0),
    "v_loaded_core_with_subclass_loader_double": fail("RESTART"),
}


def violations(case: str, observation: dict) -> list[str]:
    """期望表与观测不一致的键（空列表 = 符合）。``second_final_resolution_calls`` 单独要求 >= 2。"""
    problems = []
    for key, expected in EXPECT[case].items():
        if observation.get(key, "<missing>") != expected:
            problems.append(f"{key}: expected {expected!r}, observed {observation.get(key, '<missing>')!r}")
    if case.startswith("p_success_single"):
        calls = observation.get("second_final_resolution_calls", 0)
        if not isinstance(calls, int) or calls < 2:
            problems.append(f"second_final_resolution_calls: expected >= 2, observed {calls!r}")
    return problems


# ------------------------------------------------------------------ 仓库副本 / 合成 MATRIX（E06 / E29 / E23 / E24）

COPY_PATHS = (
    "pyproject.toml",
    "src/fc2_metadata_core",
    "adapters/amane/fc2_amane_adapter",
    "adapters/amane/shim",
    "adapters/amane/release",
    "docs/acceptance/evidence/P5_C1_HOST_WITNESS.json",
)
TEXT_SUFFIXES = {".py", ".md", ".json", ".toml"}


def make_repo_copy(destination: Path, *, crlf: bool = False) -> Path:
    """复制构建器所需的最小仓库子集；``crlf=True`` 模拟 ``autocrlf`` 的 Windows 检出（文本文件全部 CRLF）。"""
    for relative in COPY_PATHS:
        source = REPO / relative
        target = destination / relative
        files = [source] if source.is_file() else [item for item in sorted(source.rglob("*")) if item.is_file() and "__pycache__" not in item.parts]
        for item in files:
            out = target if source.is_file() else target / item.relative_to(source)
            out.parent.mkdir(parents=True, exist_ok=True)
            data = item.read_bytes().replace(b"\r\n", b"\n")
            if crlf and item.suffix in TEXT_SUFFIXES:
                data = data.replace(b"\n", b"\r\n")
            out.write_bytes(data)
    return destination


def synthetic_matrix(artifacts: dict[str, str], *, identical_main: bool = True) -> dict:
    """schema 合法、自洽的合成 MATRIX（只用于单元测试；不是见证）。"""
    gate = load_tool("run_amane_compat_gate.py")
    digest = "ab" * 32

    def host(label, coordinate_id, form, version, commit):
        scenarios = [] if (label == "main" and identical_main) else [{"id": name, "passed": True, "observations_sha256": digest} for name in gate.SCENARIO_IDS]
        return {
            "label": label, "coordinate_id": coordinate_id, "role": gate.coordinate(coordinate_id)["role"], "form": form,
            "tag": version, "tag_object": "cd" * 20, "peeled_commit": commit, "release_version": version.lstrip("v"),
            "requires_python": ">=3.14", "plugin_api_version": "1", "python_version": "3.14.7", "platform": gate.PLATFORM_WINDOWS,
            "api_fingerprint_sha256": digest, "adapter_used_subset_fingerprint_sha256": digest, "deps_lock_sha256": digest,
            "identical_to_stable": label == "main" and identical_main, "scenarios": scenarios,
        }

    hosts = [
        host("a-win", "SC-01", "frozen-desktop", "v0.15.0", "45" * 20),
        host("b-win", "SC-02", "frozen-desktop", "v0.18.0", "0a" * 20),
        host("a-src", "SC-03", "source", "v0.15.0", "45" * 20),
        host("b-src", "SC-04", "source", "v0.18.0", "0a" * 20),
        host("main", "SC-05", "source", "main", ("0a" * 20) if identical_main else "ee" * 20),
    ]
    stable = "0a" * 20
    status = [gate.derive_status(spec["id"], hosts, parity_equal=True, stable_peeled_commit=stable) for spec in gate.SUPPORT_COORDINATES]
    outcomes = {name: gate.e16b_expected_row(name) for name in gate.E16B_EXPECTED_REASON}
    stimuli = {
        "stimulus_http_403": ("http_error", ["blocked"]), "stimulus_http_429": ("rate_limited", ["rate_limited"]),
        "stimulus_hang_with_1s_source_deadline": ("timeout", ["source_deadline"]), "stimulus_closed_port": ("network", ["connection_error"]),
        "stimulus_http_503": ("server_error", ["http_server_error"]), "stimulus_no_usable_markup": ("parse_error", ["parse_error"]),
        "stimulus_unknown_charset": ("parse_error", ["invalid_response", "parse_error"]),
    }
    e16a_cases = {name: {"result_class": "SourceError", "failure_reason": reason, "actual_source_error_kind": kinds} for name, (reason, kinds) in stimuli.items()}
    e16a_cases["success_all_sources"] = {"result_class": "MediaMetadata", "failure_reason": None, "actual_source_error_kind": []}
    labels = list(gate.REQUIRED_LABELS)
    e16 = {
        "e16_a": {"observed_kinds": sorted(gate.E16A_OBSERVED_KINDS), "cases": e16a_cases, "per_host_sha256": {label: gate.canonical_hash(e16a_cases) for label in labels}, "equal": True},
        "e16_b": {"kind_count": 16, "outcomes": outcomes, "per_host_sha256": {label: gate.canonical_hash(outcomes) for label in labels}, "equal": True,
                  "production_path_verified_on_hosts": sorted(labels)},
    }
    symlink_rows = [
        {"id": f"{label}:{gate.SYMLINK_CASE}", "mode": "wheel", "python": "3.14.7", "expected": "FAIL", "observed": gate.ENV_UNAVAILABLE, "template": "WHEEL_HASH_MISMATCH",
         "sys_path_unchanged_on_fail": True, "sys_modules_unchanged_on_fail": True, "payload_executed": False, "symlink_privilege": False}
        for label in labels
    ]
    return {
        "schema_version": 1,
        "tool": {"name": "run_amane_compat_gate", "sha256": digest},
        "policy": {
            "minimum": "v0.15.0", "main_role": "informational",
            "stable_definition": "latest non-draft non-prerelease GitHub Release whose tag is v<semver>",
            "support_coordinates": [dict(item) for item in gate.SUPPORT_COORDINATES],
        },
        "hosts": hosts,
        "artifacts": dict(artifacts),
        "parity": {"required_pairs": [{"a": a, "b": b, "fields": ["result"], "equal": True, "sha256_a": digest, "sha256_b": digest}
                                      for a, b in (("a-src", "b-src"), ("a-win", "b-win"), ("a-src", "a-win"), ("b-src", "b-win"))], "allowed_diffs_observed": ["DIFF-01"], "e16": e16},
        "status": status,
        "platforms_unverified": ["macos", "linux", "docker"],
        "core_admission": {
            "core_wheel_sha256": artifacts["core_wheel_sha256"],
            "cases": [
                {"id": "E31-a", "mode": "loaded", "python": "3.14.7", "expected": "PASS", "observed": "PASS", "template": None, "sys_path_unchanged_on_fail": True, "sys_modules_unchanged_on_fail": True, "payload_executed": False},
                {"id": "E31-u", "mode": "wheel", "python": "3.14.7", "expected": "FAIL", "observed": "FAIL", "template": "UNVERIFIABLE", "sys_path_unchanged_on_fail": True, "sys_modules_unchanged_on_fail": True, "payload_executed": False},
                *symlink_rows,
            ],
        },
    }


MUTANT_COPY_PATHS = (
    "pyproject.toml",
    "src/fc2_metadata_core",
    "adapters/amane",
    "tools",
    "docs/acceptance/evidence",
    "docs/specifications/PHASE5_C2_AMANE_COMPATIBILITY_CONTRACT.md",
    "tests/fixtures/sources",
    "tests/amane_compat/host_scripts",
)


def make_mutant_repo(destination: Path) -> Path:
    """mutation 用的完整仓库子集副本（LF 规范化文本；不含 __pycache__ / .git）。"""
    for relative in MUTANT_COPY_PATHS:
        source = REAL_REPO / relative
        files = [source] if source.is_file() else [item for item in sorted(source.rglob("*")) if item.is_file() and "__pycache__" not in item.parts]
        for item in files:
            out = destination / relative if source.is_file() else destination / relative / item.relative_to(source)
            out.parent.mkdir(parents=True, exist_ok=True)
            data = item.read_bytes()
            if item.suffix in TEXT_SUFFIXES:
                data = data.replace(b"\r\n", b"\n")
            out.write_bytes(data)
    return destination
