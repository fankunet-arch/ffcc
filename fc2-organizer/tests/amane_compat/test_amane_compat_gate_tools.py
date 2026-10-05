"""P5-C2 S2 工具的主进程单元测试：回环 fixture、宿主内脚本的静态守卫、网关纯逻辑、宿主准备工具。

主进程从不 import ``amane``；宿主相关行为由 ``tools/run_amane_compat_gate.py`` 在**真实宿主**上执行（S2 / S3 证据），
这里只守住“工具本身”的不变量，使真实宿主见证不会因为工具缺陷而悄悄变空洞。
"""

from __future__ import annotations

import ast
import json
import re
import socket
import threading
import urllib.error
import urllib.request

import pytest

from _compat_support import REPO, load_tool

HOST_SCRIPTS = REPO / "tests" / "amane_compat" / "host_scripts"
FIXTURES = REPO / "tests" / "fixtures" / "sources"


def _load_host_script(name: str):
    import importlib.util
    import sys

    module_name = "ffcc_test_host_script_" + name
    if module_name in sys.modules:
        return sys.modules[module_name]
    spec = importlib.util.spec_from_file_location(module_name, HOST_SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def gate():
    return load_tool("run_amane_compat_gate.py")


@pytest.fixture(scope="module")
def loopback_module():
    return _load_host_script("loopback_fixture")


@pytest.fixture(scope="module")
def in_host():
    return _load_host_script("in_host")


def _get(url: str, timeout: float = 5.0):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return response.status, response.read(), dict(response.headers)
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read(), dict(exc.headers)


# ------------------------------------------------------------------ 回环 fixture


def test_loopback_binds_only_to_127_0_0_1_and_serves_the_frozen_fixture_pages(loopback_module):
    with loopback_module.LoopbackFixture(FIXTURES) as server:
        assert server._server.server_address[0] == "127.0.0.1"
        status, body, _ = _get(server.base_url("fc2db_net") + "/work/4979299/")
        assert status == 200 and body == (FIXTURES / "fc2db_net" / "work_4979299.html").read_bytes()
        status, body, _ = _get(server.base_url("javdb") + "/search?q=FC2-PPV-4979299")
        assert status == 200 and body == (FIXTURES / "javdb" / "search_hit_4979299.html").read_bytes()
        status, body, _ = _get(server.base_url("av123") + "/en/v/fc2-ppv-4979299")
        assert status == 200 and body == (FIXTURES / "av123" / "detail_4979299.html").read_bytes()
        assert server.counts_for("4979299") == {"av123": 1, "fc2db_net": 1, "javdb": 1}


@pytest.mark.parametrize(
    ("digits", "source", "path", "status"),
    [
        ("90000001", "fc2db_net", "/work/90000001/", 403),
        ("90000002", "av123", "/en/v/fc2-ppv-90000002", 429),
        ("90000005", "javdb", "/search?q=FC2-PPV-90000005", 503),
        ("4825061", "fc2db_net", "/work/4825061/", 404),
        ("4824605", "av123", "/en/v/fc2-ppv-4824605", 404),
        ("90000010", "fc2db_net", "/work/90000010/", 403),
        ("12345678", "fc2db_net", "/work/12345678/", 404),
    ],
)
def test_loopback_status_behaviours_are_deterministic(loopback_module, digits, source, path, status):
    with loopback_module.LoopbackFixture(FIXTURES) as server:
        observed, _body, _headers = _get(server.base_url(source) + path)
        assert observed == status
        assert server.counts_for(digits) == {source: 1}


def test_loopback_special_bodies(loopback_module):
    with loopback_module.LoopbackFixture(FIXTURES) as server:
        status, body, _ = _get(server.base_url("fc2db_net") + "/work/90000007/")
        assert status == 200 and len(body) == loopback_module.HUGE_BYTES
        status, _body, headers = _get(server.base_url("fc2db_net") + "/work/90000008/")
        assert status == 200 and "x-no-such-charset" in headers["Content-Type"]
        status, body, _ = _get(server.base_url("fc2db_net") + "/work/90000006/")
        assert status == 200 and b"no usable markup" in body
        status, body, _ = _get(server.base_url("fc2db_net") + "/work/90000010/")
        assert status == 403 and body == (FIXTURES / "common" / "cloudflare_challenge.html").read_bytes()


def test_loopback_hang_blocks_until_the_client_gives_up_and_logs_the_request(loopback_module):
    with loopback_module.LoopbackFixture(FIXTURES) as server:
        with pytest.raises((TimeoutError, socket.timeout, urllib.error.URLError)):
            _get(server.base_url("fc2db_net") + "/work/90000003/", timeout=0.4)
        assert server.counts_for("90000003") == {"fc2db_net": 1}


def test_loopback_redirect_loop_never_leaves_the_loopback_origin(loopback_module):
    import http.client

    with loopback_module.LoopbackFixture(FIXTURES) as server:
        connection = http.client.HTTPConnection("127.0.0.1", server.port, timeout=5)
        connection.request("GET", "/fc2db/work/90000009/")
        first = connection.getresponse()
        assert first.status == 302 and first.getheader("Location", "").startswith("/fc2db/r")
        connection.close()
        connection = http.client.HTTPConnection("127.0.0.1", server.port, timeout=5)
        connection.request("GET", first.getheader("Location"))
        second = connection.getresponse()
        assert second.status == 302 and second.getheader("Location", "").startswith("/fc2db/r")
        connection.close()


def test_loopback_unknown_paths_are_404_and_reset_clears_the_log(loopback_module):
    with loopback_module.LoopbackFixture(FIXTURES) as server:
        assert _get(server.base_url("fc2db_net") + "/nothing")[0] == 404
        assert _get(server.base_url("javdb") + "/search?q=nonsense")[0] == 404
        _get(server.base_url("av123") + "/en/v/fc2-ppv-4979299")
        assert server.counts() == {"av123": 1}
        server.reset()
        assert server.counts() == {}


def test_loopback_behaviours_cover_every_inducible_source_error_kind(loopback_module, in_host):
    """E16：请求集里每个可由传输层诱发的 Core 错误类别都有对应的回环行为。"""
    digits_used = {number.rsplit("-", 1)[1] for _case, number, _extra in in_host.FETCH_CASES if isinstance(number, str) and number.startswith("FC2-PPV-")}
    assert digits_used <= set(loopback_module.BEHAVIORS) | {"4979299"}
    behaviours = {spec[1] if isinstance(spec[1], str) else "page" for per_source in loopback_module.BEHAVIORS.values() for spec in per_source.values()}
    assert {"hang", "huge", "badcharset", "redirect", "cloudflare", "text:blocked", "text:rate limited", "text:unavailable"} <= behaviours


# ------------------------------------------------------------------ 宿主内脚本的静态守卫


def test_in_host_script_is_stdlib_only_at_module_level_and_imports_amane_only_inside_functions():
    tree = ast.parse((HOST_SCRIPTS / "in_host.py").read_text(encoding="utf-8"))
    top_level = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            top_level |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom):
            top_level.add((node.module or "").split(".")[0])
    assert top_level <= {"__future__", "asyncio", "builtins", "hashlib", "importlib", "io", "json", "os", "shutil", "stat", "sys", "tempfile", "threading", "types", "zipfile", "zipimport", "pathlib"}, top_level
    assert not top_level & {"amane", "pydantic", "fc2_metadata_core", "httpx", "curl_cffi"}


def test_in_host_and_loopback_scripts_never_reach_a_non_loopback_network_address():
    allowed_hosts = {"127.0.0.1", "fc2db.net", "javdb.com", "123av.com", "mirror.example", "user", "closed.invalid"}
    for name in ("in_host.py", "loopback_fixture.py"):
        text = (HOST_SCRIPTS / name).read_text(encoding="utf-8")
        for host in re.findall(r"https?://([A-Za-z0-9_.:-]+)", text):
            bare = host.split(":")[0].split("@")[-1]
            assert bare in allowed_hosts or bare.startswith("{"), (name, host)
        assert "socket.create_connection" not in text and "urlopen" not in text.replace("urllib.request.urlopen", "")


def test_in_host_script_never_touches_user_paths_or_environment_secrets():
    text = (HOST_SCRIPTS / "in_host.py").read_text(encoding="utf-8")
    for forbidden in ("expanduser", "APPDATA", "USERPROFILE", "os.environ[", "getpass", "Documents", "Downloads"):
        assert forbidden not in text, forbidden


def test_config_samples_cover_every_row_of_contract_section_12_2(in_host):
    ids = {sample_id for sample_id, _ in in_host.CONFIG_SAMPLES}
    required = {
        "default_empty", "sources_custom_order", "source_disabled", "base_url_override", "deadline_upper_bound", "deadline_small_positive",
        "invalid_unknown_source", "invalid_duplicate_source", "invalid_base_url_credentials", "invalid_base_url_query", "invalid_base_url_fragment",
        "invalid_base_url_scheme", "invalid_deadline_zero", "invalid_deadline_negative", "invalid_deadline_too_large", "invalid_deadline_nan",
        "invalid_deadline_inf", "raw_type_enabled_string", "raw_type_enabled_int", "raw_type_deadline_string", "raw_type_deadline_bool",
        "raw_type_sources_dict", "raw_type_id_non_str", "invalid_unknown_top_level_key",
    }
    assert required <= ids and len(ids) == len(in_host.CONFIG_SAMPLES)
    valid = [sample_id for sample_id in ids if not sample_id.startswith(("invalid_", "raw_type_"))]
    assert len(valid) == 6


def test_fetch_cases_cover_the_contract_13_2_request_set(in_host):
    cases = {case_id for case_id, _number, _extra in in_host.FETCH_CASES}
    assert {
        "success_all_sources", "partial_one_source_missing", "not_found_everywhere", "invalid_query_number_not_a_string",
        "invalid_query_foreign_object", "cancellation_mid_flight", "kind_blocked_403", "kind_rate_limited_429", "kind_timeout_source_deadline",
        "kind_connection_error_closed_port", "kind_http_server_error_503", "kind_parse_error", "kind_response_too_large", "kind_redirect_error_loop",
    } <= cases


def test_admission_expectations_cover_the_contract_hc_19_source_host_matrix(in_host):
    names = set(in_host.ADMISSION_EXPECT)
    assert {
        "exact_wheel_sidecar", "dir_pip_target_no_sidecar", "dir_source_no_sidecar", "dir_pyc_poc_no_sidecar", "dir_pyc_poc_with_sidecar",
        "dir_canary_with_sidecar", "preloaded_exact_wheel", "preloaded_wrong_version_wheel", "preloaded_tampered_same_name", "preloaded_directory",
        "tampered_same_name_sidecar", "shadow_meta_path_finder", "e31u_wheel_in_path_resolution_disagrees", "e31v_subclass_loader_in_final_resolution",
        "e31l_rollback_cache_absent", "e31l_rollback_cache_present", "mixed_origin_loaded",
    } <= names
    assert {template for _outcome, template in in_host.ADMISSION_EXPECT.values()} == {None, "UNVERIFIABLE", "RESTART", "WHEEL_HASH_MISMATCH"}


# ------------------------------------------------------------------ 网关纯逻辑


class _Art:
    """最小的 Artifacts 替身：只提供模板渲染。"""

    wheel_name = "fc2_metadata_core-0.1.0-py3-none-any.whl"

    def __init__(self, gate):
        self._gate = gate

    def rejection(self, key, **kwargs):
        return "插件导入失败: " + self._gate.TEMPLATES[key].format(version="0.1.0", wheel=kwargs.get("wheel", self.wheel_name))


def _failing_row(gate, art, template="UNVERIFIABLE", **overrides):
    row = {"outcome": "FAIL", "message": art.rejection(template), "path_equals_entry": True, "path_same_object": True, "cache_unchanged": True,
           "core_objects_unchanged": True, "sentinel_exists": False, "installed_tree_exists": False, "half_install_residue": []}
    row.update(overrides)
    return row


def test_gate_accepts_a_correct_fail_closed_row_and_rejects_every_deviation(gate):
    art = _Art(gate)
    assert gate.evaluate_admission_case(art, "dir_pip_target_no_sidecar", "FAIL", "UNVERIFIABLE", _failing_row(gate, art)) == []
    for override in (
        {"outcome": "PASS"}, {"message": "something else"}, {"path_equals_entry": False}, {"path_same_object": False}, {"cache_unchanged": False},
        {"core_objects_unchanged": False}, {"sentinel_exists": True}, {"installed_tree_exists": True}, {"half_install_residue": ["ffcc.fc2-metadata"]},
    ):
        assert gate.evaluate_admission_case(art, "dir_pip_target_no_sidecar", "FAIL", "UNVERIFIABLE", _failing_row(gate, art, **override)) != [], override


def test_gate_requires_the_exact_wheel_for_pass_rows_and_the_original_cache_object(gate):
    art = _Art(gate)
    good = {"outcome": "PASS", "loaded_from_exact_wheel": True, "sentinel_exists": False, "wheel_entries_in_path": 1}
    assert gate.evaluate_admission_case(art, "exact_wheel_sidecar", "PASS", None, good) == []
    assert gate.evaluate_admission_case(art, "exact_wheel_sidecar", "PASS", None, {**good, "loaded_from_exact_wheel": False}) != []
    assert gate.evaluate_admission_case(art, "exact_wheel_sidecar", "PASS", None, {**good, "wheel_entries_in_path": 2}) != []
    assert gate.evaluate_admission_case(art, "dir_pyc_poc_with_sidecar", "PASS", None, {**good, "sentinel_exists": True}) != []
    row = _failing_row(gate, art, cache_entry_is_original_object=False)
    assert gate.evaluate_admission_case(art, "e31l_rollback_cache_present", "FAIL", "UNVERIFIABLE", row) != []
    row = _failing_row(gate, art, inert_package_never_imported=False)
    assert gate.evaluate_admission_case(art, "e31u_wheel_in_path_resolution_disagrees", "FAIL", "UNVERIFIABLE", row) != []


def test_gate_templates_are_independent_of_the_locator_and_equal_to_the_contract(gate):
    for key in ("RESTART", "UNVERIFIABLE", "WHEEL_VERSION_MISMATCH", "WHEEL_HASH_MISMATCH"):
        assert gate.TEMPLATES[key].count("{") <= 1
    assert "需要 Core {version}" in gate.TEMPLATES["RESTART"] and "{wheel}" in gate.TEMPLATES["UNVERIFIABLE"]
    import tomllib  # noqa: F401  # 3.11+：网关自身不需要，只确认测试解释器与合同要求一致


def test_gate_never_imports_amane_or_third_party_modules_at_module_level(gate):
    tree = ast.parse((REPO / "tools" / "run_amane_compat_gate.py").read_text(encoding="utf-8"))
    imported = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            imported |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom):
            imported.add((node.module or "").split(".")[0])
    assert not imported & {"amane", "pydantic", "httpx", "curl_cffi", "fc2_metadata_core", "requests", "pytest"}, imported


def test_parity_is_never_vacuous_when_a_host_payload_is_incomplete(gate):
    runs = {}

    class FakeRun:
        def __init__(self, cases):
            self.extras = {"fetch_cases": cases, "enumerations": {"source_error_kinds": {"X": 1}, "host_failure_reason_members": ["a"]}, "config_booleans": {"s": True},
                           "descriptor": {"id": "x"}, "config_schema_sha256": "ab" * 32, "hc13": {"status": 201}, "identity": {"bridge_holds_host_web_client": True}}

            class Spec:
                form = "source"

            self.spec = Spec()

    runs["a-src"], runs["b-src"] = FakeRun({"c": 1}), FakeRun({"c": 1})
    assert gate.build_parity(runs)["required_pairs"][0]["equal"] is True
    runs["b-src"] = FakeRun(None)
    pair = gate.build_parity(runs)["required_pairs"][0]
    assert pair["equal"] is False and pair["sha256_a"] != pair["sha256_b"]
    runs["b-src"] = FakeRun({"c": 2})
    assert gate.build_parity(runs)["required_pairs"][0]["equal"] is False


def test_loopback_normalization_removes_the_random_port_from_evidence(gate):
    base = {"fc2db_net": "http://127.0.0.1:54321/fc2db", "javdb": "http://127.0.0.1:54321/javdb", "av123": "http://127.0.0.1:54321/av123", "closed": "http://127.0.0.1:1"}
    value = {"source_url": "http://127.0.0.1:54321/fc2db/work/1/", "urls": ["http://127.0.0.1:54321/javdb/x"], "n": 3}
    normalized = gate.normalize_loopback(value, base)
    assert normalized == {"source_url": "https://fc2db.net/work/1/", "urls": ["https://javdb.com/x"], "n": 3}
    assert "127.0.0.1" not in json.dumps(normalized)


def test_hc_12_non_zip_deviation_is_recorded_not_hidden():
    """宿主路由对非 zip 返回 500（两版本相同，宿主缺陷）：网关只对该变体放宽状态码，并在源码里写明原因。"""
    text = (REPO / "tools" / "run_amane_compat_gate.py").read_text(encoding="utf-8")
    assert '(422, 500) if label == "not_a_zip"' in text and "BadZipFile" in text


def test_matrix_snapshot_helpers_detect_added_removed_and_changed_files(gate, tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    (root / "a.txt").write_text("1", encoding="utf-8")
    before = gate.snapshot_roots({"r": root})
    (root / "b.txt").write_text("2", encoding="utf-8")
    (root / "a.txt").write_text("changed", encoding="utf-8")
    (root / "__pycache__").mkdir()
    (root / "__pycache__" / "x.pyc").write_bytes(b"0")
    after = gate.snapshot_roots({"r": root})
    diff = gate.snapshot_diff(before, after)
    assert diff == {"r": {"added": ["b.txt"], "removed": [], "changed": ["a.txt"]}}
    assert gate.snapshot_diff(before, before) == {}


# ------------------------------------------------------------------ 宿主准备工具


def test_prepare_hosts_tool_is_stdlib_only_and_verifies_digests():
    text = (REPO / "tools" / "prepare_amane_hosts.py").read_text(encoding="utf-8")
    tree = ast.parse(text)
    imported = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            imported |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom):
            imported.add((node.module or "").split(".")[0])
    assert imported <= {"__future__", "argparse", "hashlib", "json", "subprocess", "sys", "urllib", "zipfile", "pathlib"}
    assert "does not match the release digest" in text and "sha256:" in text
    assert "draft" in text and "prerelease" in text


def test_prepare_hosts_tool_checks_out_exactly_the_peeled_tag_commit():
    tool = load_tool("prepare_amane_hosts.py")
    text = (REPO / "tools" / "prepare_amane_hosts.py").read_text(encoding="utf-8")
    assert "peeled" in text and 'rev-parse", f"{tag}^{{commit}}"' in text
    assert tool.ASSET_TEMPLATE.format(tag="v0.18.0") == "Amane-v0.18.0-windows-x64.zip"
    assert str(tool.FROZEN_EXE).replace("\\", "/") == "Amane/onedir/Amane.Server.exe"


def test_host_scripts_directory_is_never_collected_as_tests():
    """``host_scripts/`` 里的文件只在真实宿主内 / 网关里执行；文件名不以 ``test_`` 开头，pytest 不会收集它们。"""
    assert not [path for path in HOST_SCRIPTS.glob("*.py") if path.name.startswith("test_") or path.name.endswith("_test.py")]
