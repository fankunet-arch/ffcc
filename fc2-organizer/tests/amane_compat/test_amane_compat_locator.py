"""P5-C2 E31（单元层）：locator 信任边界的 PASS / FAIL 配对矩阵（合同第 8.3 节；Risk C）。

每个用例在**全新子进程**里执行（``_locator_harness.py``），在 3.12（主套件解释器）与 3.14 上各跑一遍（E31-s）；
真实构建的 wheel（``tools/build_core_wheel.py``），``tmp_path``，不依赖 Amane。
找不到 3.14 解释器 -> 对应用例失败（不是 skip）。

E31-a..v 与用例的对应关系见 ``_compat_support.EXPECT``（同一张表也是 mutation killer 的判据）。
"""

from __future__ import annotations

import ast
import re

import pytest

from _compat_support import EXPECT, SHIM_DIR, interpreters, render_template, run_case, violations

ABSOLUTE_PATH = re.compile(r"[A-Za-z]:\\|/(?:Users|home)/")


def _python(label: str, path: str | None) -> str:
    assert path, f"E31-s 需要 {label} 解释器；设置环境变量 FFCC_PY314 或安装 py -3.14（不允许 skip）"
    return path


INTERPRETERS = interpreters()


@pytest.mark.parametrize("case", sorted(EXPECT))
@pytest.mark.parametrize(("label", "python"), INTERPRETERS, ids=[label for label, _ in INTERPRETERS])
def test_e31_case_matches_the_frozen_expectation(case, label, python, tmp_path, core_wheel):
    observation = run_case(_python(label, python), case, tmp_path / "work", core_wheel)
    assert violations(case, observation) == [], observation
    assert observation["error_type"] == "" if "error_type" in observation else True


def test_e31_i_symlink_case_records_the_privilege_flag(tmp_path, core_wheel):
    """无权限创建符号链接时以 ``os.lstat`` 替身执行，并记录 ``symlink_privilege``（不得 skip）。"""
    observation = run_case(_python(*interpreters()[0]), "i_sidecar_symlink", tmp_path / "work", core_wheel)
    assert isinstance(observation["symlink_privilege"], bool)
    assert observation["outcome"] == "FAIL" and observation["template"] == "WHEEL_HASH_MISMATCH"


def test_e31_pyc_poc_control_proves_the_payload_would_have_run(tmp_path, core_wheel):
    """非空洞：不经 locator 时 PoC 目录的 payload **会**执行；h1 / h2 的“sentinel 不存在”因此有意义。"""
    for label, python in interpreters():
        observation = run_case(_python(label, python), "h0_pyc_poc_control_payload_runs_without_locator", tmp_path / label, core_wheel)
        assert observation["sentinel_exists"] is True, label


@pytest.mark.parametrize("case", ["b_loaded_wrong_version_wheel", "f_unloaded_directory_pip_target_no_sidecar", "i_sidecar_tampered_one_byte", "i_sidecar_only_other_version_wheel"])
def test_e31_r_error_messages_are_fixed_bounded_and_path_free(case, tmp_path, core_wheel):
    python = _python(*interpreters()[0])
    first = run_case(python, case, tmp_path / "one", core_wheel)["message"]
    second = run_case(python, case, tmp_path / "two", core_wheel)["message"]
    assert first == second and 0 < len(first) <= 300
    assert not ABSOLUTE_PATH.search(first)
    assert first == render_template(EXPECT[case]["template"])


def test_e31_r_the_four_templates_are_distinct_and_have_no_format_leftovers():
    texts = [render_template(key) for key in ("RESTART", "UNVERIFIABLE", "WHEEL_VERSION_MISMATCH", "WHEEL_HASH_MISMATCH")]
    assert len(set(texts)) == 4
    for text in texts:
        assert "{" not in text and "<CORE_" not in text


# ------------------------------------------------------------------ 静态守卫（E19 / U2-11 / I-C2-3 / I-C2-13 / I-C2-19）

LOCATOR_SOURCE = (SHIM_DIR / "_ffcc_locator.py").read_text(encoding="utf-8")
LOCATOR_TREE = ast.parse(LOCATOR_SOURCE)


def _imports(tree: ast.Module) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom):
            names.add((node.module or "").split(".")[0])
    return names


def test_locator_is_pure_stdlib_and_imports_no_host_or_core_or_network_modules():
    imported = _imports(LOCATOR_TREE)
    assert imported <= {"hashlib", "importlib", "os", "stat", "sys", "zipimport"}, imported
    for forbidden in ("amane", "pydantic", "fc2_metadata_core", "httpx", "requests", "socket", "urllib", "subprocess", "shutil", "tempfile", "ctypes"):
        assert forbidden not in imported


def test_locator_has_no_write_api():
    forbidden_calls = {"makedirs", "mkdir", "remove", "unlink", "rmdir", "rename", "write_text", "write_bytes", "copyfile", "copytree", "rmtree", "symlink", "chmod", "utime", "truncate"}
    for node in ast.walk(LOCATOR_TREE):
        if isinstance(node, ast.Call):
            func = node.func
            label = func.attr if isinstance(func, ast.Attribute) else func.id if isinstance(func, ast.Name) else None
            assert label not in forbidden_calls, label
            if label == "replace":  # ``str.replace``（模板代入）允许；``os.replace`` / ``Path.replace`` 不允许
                assert not (isinstance(func, ast.Attribute) and ast.unparse(func.value) in {"os", "os.path", "shutil"}), ast.unparse(node)
            if label == "open":
                mode = node.args[1] if len(node.args) > 1 else next((kw.value for kw in node.keywords if kw.arg == "mode"), None)
                assert isinstance(mode, ast.Constant) and mode.value == "rb", "only open(..., 'rb') is allowed"


def test_locator_never_mutates_sys_modules():
    """U2-11：不 purge / 热切换：没有 ``del sys.modules[...]``、``sys.modules.pop``、对 ``sys.modules`` 的赋值。"""
    for node in ast.walk(LOCATOR_TREE):
        if isinstance(node, (ast.Delete, ast.Assign, ast.AugAssign)):
            targets = node.targets if hasattr(node, "targets") else [node.target]
            for target in targets:
                text = ast.unparse(target)
                assert "sys.modules" not in text, text
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            owner = ast.unparse(node.func.value)
            assert not (owner == "sys.modules" and node.func.attr in {"pop", "clear", "update", "setdefault", "popitem"}), ast.unparse(node)


def test_locator_has_no_tree_hash_or_pyc_logic_and_no_directory_acceptance():
    forbidden_words = ("rglob", "os.walk", "__pycache__", ".pyc", "cache_from_source", "unverified-path", "tree_sha256", "CORE_TREE_SHA256")
    for word in forbidden_words:
        assert word not in LOCATOR_SOURCE, word


def test_trusted_loader_check_is_an_exact_type_test_and_never_isinstance():
    """A-04 / I-C2-19：所有 loader 判断都是 ``type(...) is zipimport.zipimporter``；没有任何 ``isinstance(..., zipimporter)``。"""
    exact = 0
    for node in ast.walk(LOCATOR_TREE):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in {"isinstance", "issubclass"}:
            assert "zipimport" not in ast.unparse(node), ast.unparse(node)
        if isinstance(node, ast.Compare) and "zipimport.zipimporter" in ast.unparse(node):
            assert isinstance(node.ops[0], (ast.Is, ast.IsNot)) and ast.unparse(node.left).startswith("type("), ast.unparse(node)
            exact += 1
    assert exact >= 2, "both the loaded-Core proof and the resolution proof must use the exact type test"


def test_every_success_path_has_a_final_actual_resolution_proof_in_the_source():
    """I-C2-18：2E 使用真实 ``importlib.util.find_spec``；2D 之后没有直接 ``return``（“wheel 已在 sys.path -> 立即成功”不存在）。"""
    admit = next(node for node in ast.walk(LOCATOR_TREE) if isinstance(node, ast.FunctionDef) and node.name == "_admit_sidecar_wheel")
    text = ast.unparse(admit)
    assert text.count("importlib.util.find_spec(_CORE)") == 1
    assert not any(isinstance(node, ast.Return) for node in ast.walk(admit)), "_admit_sidecar_wheel must not return before the final proof completes"
    insertion = text.index("sys.path.insert(0, wheel)")
    assert text.index("importlib.util.find_spec(_CORE)") > insertion


def test_locator_pin_attributes_used_are_only_the_frozen_literals():
    used = {node.attr for node in ast.walk(LOCATOR_TREE) if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "pin"}
    assert used <= {"CORE_VERSION", "CORE_WHEEL_NAME", "CORE_WHEEL_SHA256", "SIDECAR_DIRNAME"}, used


def test_locator_file_is_utf8_without_bom():
    """工作树换行取决于 autocrlf；构建器按 LF 规范化字节打包（见 release_layout 测试），这里只守 UTF-8 / BOM。"""
    raw = (SHIM_DIR / "_ffcc_locator.py").read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf")
    raw.decode("utf-8")
