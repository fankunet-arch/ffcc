"""P5-C2 E20 / 合同第 16 节：mutation / non-vacuity（M2-01..M2-23；每个 mutant 必须被指定 killer 杀死）。

方法（与 P5-C1 同法，但对象是整个仓库子集的**临时副本**）：

1. ``make_mutant_repo`` 复制 ``pyproject.toml / src / adapters/amane / tools / evidence / fixtures / host_scripts`` 到临时目录，
   对副本施加**恰好一处**文本补丁（补丁不是恰好命中一次 = mutant 空洞 = 测试失败）；
2. 在子进程里以环境变量 ``FFCC_C2_REPO_ROOT=<副本>`` 运行指定的 killer 测试（P5-C1 的 killer 另用
   ``-o pythonpath=<副本>/adapters/amane src tests``），并附带哨兵测试证明被测的确是被篡改的副本；
3. 至少一个 killer 失败（FAILED / ERROR）= KILLED。仓库内的原文件从不被修改。

``host_killers`` 记录合同指定的**真实宿主**杀手（HC-xx）：它们不能在 pytest 里运行（需要真实 Amane 宿主），
由 ``python tests/amane_compat/test_amane_compat_mutation_nonvacuity.py --hosts``（见文件末尾）在源码宿主上对**被篡改的
artifact** 实际执行并打印结果，HANDOFF 逐条记录。
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from _compat_support import REAL_REPO, REPO, load_tool, make_mutant_repo

LOCATOR = "adapters/amane/shim/_ffcc_locator.py"
SHIM = "adapters/amane/shim/plugin.py"
ADAPTER = "adapters/amane/fc2_amane_adapter"
RELEASE = "tools/build_amane_release.py"
GATE = "tools/run_amane_compat_gate.py"
T = "tests/amane_compat"
SENTINEL = f"{T}/test_amane_compat_mutation_nonvacuity.py::test_the_repository_under_test_is_the_expected_copy"
C1_SENTINEL = "tests/amane_adapter/test_amane_architecture_guards.py::test_the_adapter_under_test_is_the_expected_tree"


def locator_case(case: str) -> str:
    return f"{T}/test_amane_compat_locator.py::test_e31_case_matches_the_frozen_expectation[main-{case}]"


LAYOUT = f"{T}/test_amane_compat_release_layout.py"
ZIP_LAYOUT = f"{LAYOUT}::test_plugin_zip_has_exactly_the_frozen_allow_list_under_one_top_level_folder"
SHIM_SHAPE = f"{LAYOUT}::test_shim_plugin_py_is_exactly_the_frozen_three_lines_plus_the_plugin_import"
E02 = f"{LAYOUT}::test_e02_impl_is_the_lf_normalized_p5_c1_tree_and_matches_the_c1_witness"
E07 = f"{LAYOUT}::test_e07_plugin_id_is_exactly_ffcc_fc2_metadata_everywhere"
E18 = f"{LAYOUT}::test_e18_no_vendoring_no_core_file_or_core_bytes_in_the_plugin_zip"
AST_VERSION_NAMES = f"{T}/test_amane_compat_api_matrix.py::test_m2_07_m2_08_adapter_and_shim_never_use_single_version_host_names_or_version_branches"
DAG_CYCLE = f"{T}/test_amane_compat_artifact_dag.py::test_no_member_embeds_a_hash_of_itself_or_of_a_higher_layer"
JSON_VALID = f"{T}/test_amane_compat_matrix_json.py::test_a_consistent_matrix_validates_and_has_the_frozen_coordinate_table"
JSON_RULES = f"{T}/test_amane_compat_matrix_json.py::test_m2_16_every_self_consistency_violation_is_rejected"
AST_NO_SYS_MODULES = f"{T}/test_amane_compat_locator.py::test_locator_never_mutates_sys_modules"
AST_FINAL_PROOF = f"{T}/test_amane_compat_locator.py::test_every_success_path_has_a_final_actual_resolution_proof_in_the_source"
C1_VERSION_NAMES = "tests/amane_adapter/test_amane_api_manifest.py::test_no_single_version_host_names_are_used_anywhere_in_the_tree"
C1_DESCRIPTOR = "tests/amane_adapter/test_amane_api_manifest.py::test_descriptor_declares_only_the_cross_version_subset"
C1_ARCH = "tests/amane_adapter/test_amane_architecture_guards.py"


@dataclass(frozen=True)
class Mutant:
    mutant_id: str
    variant: str
    description: str
    patches: tuple[tuple[str, str, str], ...]
    killers: tuple[str, ...] = ()
    c1_killers: tuple[str, ...] = ()
    host_killers: tuple[str, ...] = ()
    host_phases: tuple[str, ...] = ()

    @property
    def label(self) -> str:
        return f"{self.mutant_id}-{self.variant}"


def _stale_shim() -> tuple[str, str, str]:
    return (
        SHIM,
        "from ._impl.plugin import Plugin   # noqa: E402",
        'import builtins\nfrom ._impl.plugin import Plugin as _FreshPlugin   # noqa: E402\nPlugin = builtins.__dict__.setdefault("_ffcc_stale_plugin", _FreshPlugin)   # noqa: E402',
    )


MUTANTS = (
    Mutant("M2-01", "id", "shim / adapter declares the wrong plugin id (ffcc.fc2metadata)",
           ((f"{ADAPTER}/_settings.py", 'PLUGIN_ID = "ffcc.fc2-metadata"\n', 'PLUGIN_ID = "ffcc.fc2metadata"\n'),), (E07, ZIP_LAYOUT), host_killers=("HC-01",), host_phases=("success",)),
    Mutant("M2-02", "api", "the descriptor overrides api_version with '2'",
           ((f"{ADAPTER}/plugin.py", "            urls=descriptor_urls(),\n        )", '            urls=descriptor_urls(),\n            api_version="2",\n        )'),),
           (E02,), (C1_DESCRIPTOR,), ("HC-01", "HC-03"), ("success",)),
    Mutant("M2-03", "silent", "the locator silently ignores a sidecar failure (no fail closed)",
           ((LOCATOR, "        if present:\n            _admit_sidecar_wheel(pin, wheel, entry_path_object, entry_path)\n            return\n",
             "        if present:\n            try:\n                _admit_sidecar_wheel(pin, wheel, entry_path_object, entry_path)\n            except ImportError:\n                pass\n            return\n"),),
           (locator_case("i_sidecar_tampered_one_byte"), locator_case("k_shadow_meta_path_finder_with_valid_sidecar"), locator_case("u_existing_wheel_but_resolution_disagrees")),
           host_killers=("HC-11",), host_phases=("failures",)),
    Mutant("M2-04", "vendor", "the Core source is packed into the plugin zip",
           ((RELEASE, "    _scan_artifact_members(members, core_members)\n", '    members[f"{plugin_id}/fc2_metadata_core/__init__.py"] = core_members[0][1]\n'),), (E18, ZIP_LAYOUT)),
    Mutant("M2-05", "stale", "reload reuses a stale Plugin class (cached across purge)", (_stale_shim(),), (SHIM_SHAPE,), host_killers=("HC-07",), host_phases=("success",)),
    Mutant("M2-06", "no-rebuild", "a config change does not rebuild the provider (module-level settings cache)",
           ((f"{ADAPTER}/plugin.py", "        settings = parse_settings(config.model_dump())\n        runtime = AdapterRuntime(",
             '        settings = _STALE.setdefault("s", parse_settings(config.model_dump()))\n        runtime = AdapterRuntime('),
            (f"{ADAPTER}/plugin.py", "class _HostAmaneHttpBridge(AmaneHttpBridge):", "_STALE = {}\n\n\nclass _HostAmaneHttpBridge(AmaneHttpBridge):")),
           (E02,), (), ("HC-08",), ("success", "own_stack")),
    Mutant("M2-07", "version-branch", "a version-dependent branch changes the mapping (reads SearchQuery.raw_results)",
           ((f"{ADAPTER}/plugin.py", "        fields = read_query_fields(query)\n",
             '        fields = read_query_fields(query)\n        _ = query.raw_results if hasattr(query, "raw_results") else None\n'),),
           (AST_VERSION_NAMES, E02), (C1_VERSION_NAMES,)),
    Mutant("M2-08", "newer-api", "a newer-only host keyword leaks into the request (max_attempts)",
           ((f"{ADAPTER}/_bridge.py", "                ok_statuses=OK_STATUSES,\n", "                ok_statuses=OK_STATUSES,\n                max_attempts=1,\n"),),
           (AST_VERSION_NAMES, E02), (C1_VERSION_NAMES,), host_killers=("HC-04",), host_phases=("own_stack",)),
    Mutant("M2-09", "forbidden-file", "the plugin zip contains a __pycache__ / .pyc file",
           ((RELEASE, "    zip_bytes = deterministic_zip(members)\n", '    members[f"{plugin_id}/__pycache__/x.cpython-312.pyc"] = b"\\x00"\n    zip_bytes = deterministic_zip(members)\n'),), (ZIP_LAYOUT,)),
    Mutant("M2-10", "timestamp", "zip timestamps are not fixed",
           ((RELEASE, "FIXED_TIMESTAMP = (1980, 1, 1, 0, 0, 0)\n", "FIXED_TIMESTAMP = (2001, 2, 3, 4, 5, 6)\n"),), (ZIP_LAYOUT,)),
    Mutant("M2-10", "ordering", "zip entries are written in reverse order",
           ((RELEASE, '        for name in sorted(members, key=lambda item: item.encode("utf-8")):\n            info = zipfile.ZipInfo(name, date_time=FIXED_TIMESTAMP)',
             '        for name in sorted(members, key=lambda item: item.encode("utf-8"), reverse=True):\n            info = zipfile.ZipInfo(name, date_time=FIXED_TIMESTAMP)'),), (ZIP_LAYOUT,)),
    Mutant("M2-11", "stale-upgrade", "an upgraded zip still loads the old Plugin class", (_stale_shim(),), (SHIM_SHAPE,), host_killers=("HC-09",), host_phases=("success",)),
    Mutant("M2-12", "pydantic-vs-parser", "the Pydantic before-validator no longer calls parse_settings (raw types are coerced)",
           ((f"{ADAPTER}/plugin.py", "            parse_settings(_raw_for_parse_settings(data))\n", "            pass\n"),),
           (E02,), (), ("HC-05",), ("success", "own_stack")),
    Mutant("M2-13", "own-http", "the bridge imports an HTTP library (httpx) instead of using the host WebClient",
           ((f"{ADAPTER}/_bridge.py", "import codecs\n", "import codecs\nimport httpx\n"),), (E02,), (C1_ARCH,), ("HC-04", "HC-17"), ("own_stack",)),
    Mutant("M2-14", "hash-skip", "the locator does not verify the wheel sha256",
           ((LOCATOR, "        return digest.hexdigest() == pin.CORE_WHEEL_SHA256\n", "        return True\n"),),
           (locator_case("i_sidecar_tampered_one_byte"), locator_case("c_loaded_tampered_same_name_wheel")), host_killers=("HC-11",), host_phases=("failures",)),
    Mutant("M2-14", "accept-symlink", "the locator accepts a non-regular (symlink) wheel",
           ((LOCATOR, "        if not stat.S_ISREG(info.st_mode) or info.st_size > _MAX_WHEEL_BYTES:\n", "        if info.st_size > _MAX_WHEEL_BYTES:\n"),),
           (locator_case("i_sidecar_symlink"),)),
    Mutant("M2-14", "accept-any-name", "the locator accepts any wheel file name",
           ((LOCATOR, "        if os.path.basename(wheel) != pin.CORE_WHEEL_NAME:\n            return False\n", "        if False:\n            return False\n"),),
           (locator_case("b_loaded_wrong_version_wheel"),)),
    Mutant("M2-15", "pin-change-accepted", "a Core loaded from another artifact is still accepted after a pin change",
           ((LOCATOR, "    if wheel_key is None or not _wheel_proof(pin, wheel):\n        return False\n", "    if wheel_key is None:\n        return False\n"),),
           (locator_case("b_loaded_wrong_version_wheel"), locator_case("c_loaded_tampered_same_name_wheel")), host_killers=("HC-16",), host_phases=("core_upgrade",)),
    Mutant("M2-16", "unverified-as-supported", "the status derivation reports an UNVERIFIED coordinate as SUPPORTED",
           ((GATE, '        return {**base, "status": "UNVERIFIED", "reason": "no verification environment; not part of the support claim"}',
             '        return {**base, "status": "SUPPORTED", "reason": "no verification environment; not part of the support claim"}'),), (JSON_VALID, JSON_RULES)),
    Mutant("M2-17", "blind-trust", "an already loaded fc2_metadata_core is trusted without proof",
           ((LOCATOR, "    if _CORE in sys.modules:\n        if not _loaded_core_is_proven(pin):\n            raise _error(_RESTART_TEMPLATE, pin)\n        return\n", "    if _CORE in sys.modules:\n        return\n"),),
           tuple(locator_case(case) for case in ("b_loaded_wrong_version_wheel", "c_loaded_tampered_same_name_wheel", "d_loaded_directory_pip_target", "e_loaded_editable_source", "j_mixed_submodule_other_archive")),
           host_killers=("HC-19",), host_phases=("admission",)),
    Mutant("M2-18", "accept-directory", "any directory-form Core is accepted",
           ((LOCATOR, "    if spec is not None:\n        raise _error(_UNVERIFIABLE_TEMPLATE, pin)\n", "    if False:\n        raise _error(_UNVERIFIABLE_TEMPLATE, pin)\n"),),
           tuple(locator_case(case) for case in ("f_unloaded_directory_pip_target_no_sidecar", "f_unloaded_source_checkout_no_sidecar", "h1_pyc_poc_directory_no_sidecar")),
           host_killers=("HC-19",), host_phases=("admission",)),
    Mutant("M2-19", "no-final-resolution-check", "the resolution proof accepts any spec (no shadowing / loader / archive check)",
           ((LOCATOR, "    if not _in_archive(spec, wheel_key, top_level=True):\n        return False\n    locations = spec.submodule_search_locations\n", "    return True\n    locations = spec.submodule_search_locations\n"),),
           tuple(locator_case(case) for case in ("k_shadow_meta_path_finder_with_valid_sidecar", "l1_rollback_after_insertion_cache_absent_at_entry", "u_existing_wheel_but_resolution_disagrees", "v_subclass_loader_double_in_final_resolution")),
           host_killers=("HC-19",), host_phases=("admission",)),
    Mutant("M2-19", "no-same-root-check", "loaded submodules are not required to share the verified root",
           ((LOCATOR, "        if not _in_archive(spec, wheel_key, top_level=(name == _CORE)):\n            return False\n", "        pass\n"),),
           tuple(locator_case(case) for case in ("j_mixed_submodule_other_archive", "j_mixed_submodule_directory_origin", "j_mixed_submodule_no_spec"))),
    Mutant("M2-20", "no-sys-path-rollback", "a failure after the locator-owned insertion does not restore sys.path",
           ((LOCATOR, "    if entry_path_object != entry_path:\n        entry_path_object[:] = entry_path\n", "    pass\n"),),
           (locator_case("l1_rollback_after_insertion_cache_absent_at_entry"), locator_case("l2_rollback_after_insertion_cache_present_at_entry")),
           host_killers=("HC-19",), host_phases=("admission",)),
    Mutant("M2-20", "purge-on-restart", "the locator purges fc2_metadata_core* from sys.modules before failing",
           ((LOCATOR, "        if not _loaded_core_is_proven(pin):\n            raise _error(_RESTART_TEMPLATE, pin)\n",
             "        if not _loaded_core_is_proven(pin):\n            for key in [key for key in list(sys.modules) if key == _CORE or key.startswith(_CORE + '.')]:\n                del sys.modules[key]\n            raise _error(_RESTART_TEMPLATE, pin)\n"),),
           (locator_case("b_loaded_wrong_version_wheel"), locator_case("d_loaded_directory_pip_target"), AST_NO_SYS_MODULES)),
    Mutant("M2-20", "no-cache-restore", "the verified-wheel importer-cache entry is not restored",
           ((LOCATOR, "        if key not in entry_cache:\n            del sys.path_importer_cache[key]\n", "        pass\n"),), (locator_case("l1_rollback_after_insertion_cache_absent_at_entry"),)),
    Mutant("M2-21", "py-hash-directory", "directory-form Core is accepted when its origin is a .py file (R1: *.py tree hash)",
           ((LOCATOR, "    if spec is not None:\n        raise _error(_UNVERIFIABLE_TEMPLATE, pin)\n", '    if spec is not None and not str(spec.origin).endswith(".py"):\n        raise _error(_UNVERIFIABLE_TEMPLATE, pin)\n'),),
           (locator_case("h1_pyc_poc_directory_no_sidecar"), locator_case("f_unloaded_directory_editable_no_sidecar")), host_killers=("HC-19",), host_phases=("admission",)),
    Mutant("M2-22", "artifact-cycle", "COMPATIBILITY.json embeds a SHA256SUMS hash field (derivation cycle)",
           ((RELEASE, '        "known_limitations": list(KNOWN_LIMITATIONS),\n', '        "known_limitations": list(KNOWN_LIMITATIONS),\n        "sha256sums_sha256": "0" * 64,\n'),), (DAG_CYCLE,)),
    Mutant("M2-23", "existing-wheel-returns-success", "an existing sys.path wheel entry returns success without the final resolution",
           ((LOCATOR, "        if wheel_key not in [_norm(item) for item in list(sys.path)]:\n            sys.path.insert(0, wheel)\n",
             "        if wheel_key not in [_norm(item) for item in list(sys.path)]:\n            sys.path.insert(0, wheel)\n        else:\n            return\n"),),
           (locator_case("u_existing_wheel_but_resolution_disagrees"), locator_case("p_success_single_insertion_and_idempotent_with_final_resolution"), AST_FINAL_PROOF),
           host_killers=("HC-19",), host_phases=("admission",)),
)

FAILED_OR_ERROR = re.compile(r"^(FAILED|ERROR) (\S+)", re.MULTILINE)


@dataclass
class MutantResult:
    label: str
    applied_once: bool
    sentinel_ok: bool
    killed: bool
    failed: list[str] = field(default_factory=list)


def apply_patches(repo: Path, mutant: Mutant) -> bool:
    applied_once = True
    for relative, old, new in mutant.patches:
        target = repo / relative
        text = target.read_text(encoding="utf-8").replace("\r\n", "\n")
        if text.count(old) != 1:
            applied_once = False
            continue
        target.write_text(text.replace(old, new, 1), encoding="utf-8", newline="\n")
    return applied_once


def _pytest(nodes: list[str], env: dict[str, str], extra: list[str] | None = None) -> tuple[list[str], str]:
    command = [sys.executable, "-m", "pytest", *nodes, "-q", "-p", "no:cacheprovider", "--no-header", "--color=no", "-rfE", *(extra or [])]
    completed = subprocess.run(command, cwd=str(REAL_REPO), env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=1200, check=False)
    return [f"{kind} {name}" for kind, name in FAILED_OR_ERROR.findall(completed.stdout)], completed.stdout


def run_mutant(mutant: Mutant) -> MutantResult:
    with tempfile.TemporaryDirectory(prefix="p5c2_" + mutant.label.replace("/", "_") + "_") as work:
        repo = make_mutant_repo(Path(work) / "repo")
        (repo / "MUTANT_MARKER").write_text(mutant.label, encoding="utf-8")
        applied_once = apply_patches(repo, mutant)
        base = {key: value for key, value in os.environ.items() if key != "FFCC_C2_REPO_ROOT"}
        failed: list[str] = []
        sentinel_ok = True
        if mutant.killers:
            env = {**base, "FFCC_C2_REPO_ROOT": str(repo), "FFCC_C2_MUTANT_LABEL": mutant.label}
            items, _out = _pytest([*mutant.killers, SENTINEL], env)
            failed += items
            sentinel_ok = sentinel_ok and not any(SENTINEL.split("::")[1] in item for item in items)
        if mutant.c1_killers:
            env = {**base, "FFCC_C2_REPO_ROOT": str(repo), "P5_C1_MUTANT_ROOT": str(repo / "adapters" / "amane")}
            items, _out = _pytest([*mutant.c1_killers, C1_SENTINEL], env, ["-o", f"pythonpath={(repo / 'adapters' / 'amane').as_posix()} src tests"])
            failed += items
            sentinel_ok = sentinel_ok and not any("test_the_adapter_under_test_is_the_expected_tree" in item for item in items)
        killers_failed = [item for item in failed if "sentinel" not in item and "expected_copy" not in item and "expected_tree" not in item]
        return MutantResult(mutant.label, applied_once, sentinel_ok, bool(killers_failed), killers_failed)


# ------------------------------------------------------------------ 哨兵 / 表守卫


def test_the_repository_under_test_is_the_expected_copy():
    """哨兵：设置了 ``FFCC_C2_MUTANT_LABEL`` 时，被测仓库必须是带该标记的临时副本（而不是真实仓库）。"""
    label = os.environ.get("FFCC_C2_MUTANT_LABEL")
    if label is None:
        assert REPO == REAL_REPO
        return
    assert REPO != REAL_REPO and (REPO / "MUTANT_MARKER").read_text(encoding="utf-8") == label


def test_the_mutant_table_covers_m2_01_to_m2_23_exactly():
    assert sorted({mutant.mutant_id for mutant in MUTANTS}) == [f"M2-{index:02d}" for index in range(1, 24)]
    labels = [mutant.label for mutant in MUTANTS]
    assert len(labels) == len(set(labels)), "mutant labels must be unique"


@pytest.mark.parametrize("mutant", MUTANTS, ids=lambda item: item.label)
def test_every_patch_applies_exactly_once_to_the_real_tree_and_changes_it(mutant):
    for relative, old, new in mutant.patches:
        text = (REAL_REPO / relative).read_text(encoding="utf-8").replace("\r\n", "\n")
        assert text.count(old) == 1, f"{mutant.label}: the patch must match exactly once in {relative} (otherwise the mutant is vacuous)"
        assert new != old
    assert mutant.killers or mutant.c1_killers, f"{mutant.label} has no designated killer"


def test_host_killers_name_real_scenarios_and_phases():
    gate = load_tool("run_amane_compat_gate.py")
    for mutant in MUTANTS:
        assert set(mutant.host_killers) <= set(gate.SCENARIO_IDS), mutant.label
        assert set(mutant.host_phases) <= {"failures", "success", "own_stack", "core_upgrade", "admission"}, mutant.label
        assert bool(mutant.host_killers) == bool(mutant.host_phases), mutant.label


def test_the_harness_never_modifies_the_real_tree():
    for mutant in MUTANTS:
        for relative, old, _new in mutant.patches:
            assert (REAL_REPO / relative).read_text(encoding="utf-8").replace("\r\n", "\n").count(old) == 1
    assert not (REAL_REPO / "MUTANT_MARKER").exists()


@pytest.mark.parametrize("mutant", MUTANTS, ids=lambda item: item.label)
def test_every_mutant_is_killed_by_a_designated_test(mutant):
    result = run_mutant(mutant)
    assert result.applied_once, f"{mutant.label}: the patch must apply exactly once"
    assert result.sentinel_ok, f"{mutant.label}: the sentinel shows the killers did not run against the mutated copy"
    assert result.killed, f"{mutant.label} SURVIVED: designated killers all passed"


# ------------------------------------------------------------------ 真实宿主杀手（HANDOFF 使用）


def _host_mutation_main(argv: list[str]) -> int:  # pragma: no cover - 需要真实 Amane 宿主与网络前提
    """``python test_amane_compat_mutation_nonvacuity.py --hosts <hosts.json> --wheel <whl> [--label b-src] [--only M2-05 ...]``。

    对每个带 ``host_killers`` 的 mutant：在副本上打补丁，构建**被篡改的** plugin zip（L0 wheel 不变），在一台源码宿主上只执行相关阶段，
    断言指定的 HC 场景失败（= KILLED）。结果逐行打印。
    """
    import argparse
    import json
    import shutil

    parser = argparse.ArgumentParser()
    parser.add_argument("--hosts", required=True, type=Path)
    parser.add_argument("--wheel", required=True, type=Path)
    parser.add_argument("--work", required=True, type=Path)
    parser.add_argument("--label", default="b-src")
    parser.add_argument("--only", nargs="*", default=[])
    options = parser.parse_args(argv)
    gate = load_tool("run_amane_compat_gate.py")
    release = load_tool("build_amane_release.py")
    specs, _stable, _main = gate.load_specs(options.hosts, None)
    spec = specs[options.label]
    oracle = gate.build_oracle()
    loopback_module = gate._load_module(gate.HOST_SCRIPTS / "loopback_fixture.py", "ffcc_mut_loopback")
    exit_code = 0
    with loopback_module.LoopbackFixture(gate.REPO_ROOT / "tests" / "fixtures" / "sources") as loopback:
        for mutant in MUTANTS:
            if not mutant.host_killers or (options.only and mutant.mutant_id not in options.only):
                continue
            work = options.work / mutant.label
            shutil.rmtree(work, ignore_errors=True)
            repo = make_mutant_repo(work / "repo")
            if not apply_patches(repo, mutant):
                print(f"{mutant.label}: PATCH DID NOT APPLY")
                exit_code = 1
                continue
            try:
                stage1 = release.build_stage1(repo, options.wheel, check_witness=False)
            except release.ReleaseError as exc:  # 构建器自己的守卫先于宿主杀死它（例如 M2-01 的 id 校验）
                print(json.dumps({"mutant": mutant.label, "host": options.label, "KILLED": True, "killed_at_build": str(exc)[:120]}))
                continue
            stage1_dir = work / "l1"
            stage1_dir.mkdir(parents=True)
            for name, data in stage1["files"].items():
                (stage1_dir / name).write_bytes(data)
            art = gate.Artifacts(options.wheel, stage1_dir, work / "artifacts", repo_root=repo)
            (work / "artifacts").mkdir(parents=True, exist_ok=True)
            run = gate.run_host(spec, art, loopback, oracle, work / "host", log=lambda message: None, only_phases=set(mutant.host_phases))
            failed = sorted({"HC-19" if item.id == "HC-19-host" else item.id for item in run.results.values() if item.failures})
            killed = sorted(set(mutant.host_killers) & set(failed))
            print(json.dumps({"mutant": mutant.label, "host": options.label, "host_killers": list(mutant.host_killers), "failed_scenarios": failed, "killed_by": killed, "KILLED": bool(killed)}))
            exit_code = exit_code or (0 if killed else 1)
    return exit_code


if __name__ == "__main__":  # pragma: no cover
    if "--hosts" in sys.argv:
        raise SystemExit(_host_mutation_main(sys.argv[1:]))
    for item in MUTANTS:
        outcome = run_mutant(item)
        print(f"{outcome.label}: applied_once={outcome.applied_once} sentinel_ok={outcome.sentinel_ok} killed={outcome.killed}")
        for name in outcome.failed[:6]:
            print(f"    {name}")
