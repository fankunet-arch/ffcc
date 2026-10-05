"""P5-C2 E02 / E07 / E18 / E19 / E31-t / M2-01 / M2-02 / M2-04 / M2-09：plugin zip 的包结构与不变量（合同第 9 节）。"""

from __future__ import annotations

import ast
import hashlib
import io
import json
import re
import zipfile

import pytest

from _compat_support import ADAPTER_TREE, REPO, SHIM_DIR, load_tool, make_repo_copy

WITNESS = json.loads((REPO / "docs" / "acceptance" / "evidence" / "P5_C1_HOST_WITNESS.json").read_text(encoding="utf-8"))
ROOT = "ffcc.fc2-metadata"
ALLOWED = sorted(
    f"{ROOT}/{name}"
    for name in (
        "plugin.py", "_ffcc_locator.py", "_ffcc_pin.py",
        "_impl/plugin.py", "_impl/_core_gate.py", "_impl/_settings.py", "_impl/_number.py", "_impl/_bridge.py", "_impl/_runtime.py", "_impl/_outcome.py",
    )
)
SHIM_TEXT = (
    "from ._ffcc_locator import ensure_core\n"
    "from . import _ffcc_pin\n"
    "ensure_core(_ffcc_pin, __file__)\n"
    "from ._impl.plugin import Plugin   # noqa: E402  \u2014\u2014 \u5bbf\u4e3b\u8981\u6c42\u6a21\u5757\u5b57\u5178\u4e2d\u5b58\u5728\u540d\u4e3a Plugin \u7684\u7c7b\n"
)


@pytest.fixture(scope="module")
def release():
    return load_tool("build_amane_release.py")


@pytest.fixture(scope="module")
def stage1(release, tmp_path_factory):
    builder = load_tool("build_core_wheel.py")
    name, payload, _tree = builder.build_wheel_bytes(REPO / "src" / "fc2_metadata_core", REPO / "pyproject.toml")
    path = tmp_path_factory.mktemp("wheel") / name
    path.write_bytes(payload)
    result = release.build_stage1(REPO, path)
    result["wheel_path"] = path
    return result


def _zip_members(stage1) -> dict[str, bytes]:
    data = stage1["files"][f"{ROOT}-0.1.0.zip"]
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        return {name: archive.read(name) for name in archive.namelist()}


def test_plugin_zip_has_exactly_the_frozen_allow_list_under_one_top_level_folder(stage1):
    data = stage1["files"][f"{ROOT}-0.1.0.zip"]
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        names = archive.namelist()
        assert names == ALLOWED
        assert {name.split("/")[0] for name in names} == {ROOT}
        for info in archive.infolist():
            assert info.compress_type == zipfile.ZIP_STORED and info.date_time == (1980, 1, 1, 0, 0, 0)
            assert info.external_attr == 0o100644 << 16 and info.create_system == 3 and not info.is_dir()
    assert len(data) < 20 * 1024 * 1024


def test_shim_plugin_py_is_exactly_the_frozen_three_lines_plus_the_plugin_import(stage1):
    members = _zip_members(stage1)
    assert members[f"{ROOT}/plugin.py"].decode("utf-8") == SHIM_TEXT
    assert (SHIM_DIR / "plugin.py").read_bytes().replace(b"\r\n", b"\n").decode("utf-8") == SHIM_TEXT
    tree = ast.parse(SHIM_TEXT)
    assert [type(node).__name__ for node in tree.body] == ["ImportFrom", "ImportFrom", "Expr", "ImportFrom"]


def test_e02_impl_is_the_lf_normalized_p5_c1_tree_and_matches_the_c1_witness(stage1, release):
    members = _zip_members(stage1)
    impl = {name.split("/", 2)[2]: data for name, data in members.items() if name.startswith(f"{ROOT}/_impl/")}
    assert sorted(impl) == sorted(path.name for path in ADAPTER_TREE.glob("*.py"))
    assert release.tree_sha256(list(impl.items())) == WITNESS["adapter_tree_sha256"]
    for name, data in impl.items():
        assert data == (ADAPTER_TREE / name).read_bytes().replace(b"\r\n", b"\n"), name
        assert b"\r" not in data
    assert stage1["artifacts"]["impl_tree_sha256"] == stage1["artifacts"]["adapter_tree_sha256"] == WITNESS["adapter_tree_sha256"]
    assert not any(name.endswith("__init__.py") for name in members), "_impl is a namespace package without __init__.py (I-C2-5)"


def test_i_c2_1_text_describes_normalized_byte_identity_never_raw_byte_identity():
    """R2-A-05：构建器 / 测试 / 文档中不得出现“字节原样 _impl”（现行表述 = LF 规范化字节同一）。"""
    for path in (REPO / "tools" / "build_amane_release.py", REPO / "adapters" / "amane" / "release" / "INSTALL.zh-CN.md"):
        text = path.read_text(encoding="utf-8")
        assert "字节原样" not in text and "raw-byte identity" not in text.replace('"raw-byte identity"', ""), path.name


def test_e07_plugin_id_is_exactly_ffcc_fc2_metadata_everywhere(stage1, release):
    members = _zip_members(stage1)
    assert release.read_plugin_constants(ADAPTER_TREE / "_settings.py") == ("ffcc.fc2-metadata", "0.1.0")
    assert b'PLUGIN_ID = "ffcc.fc2-metadata"' in members[f"{ROOT}/_impl/_settings.py"]
    assert {name.split("/")[0] for name in members} == {"ffcc.fc2-metadata"}


def test_m2_01_builder_rejects_a_plugin_id_that_is_not_ffcc_fc2_metadata(tmp_path, release, stage1):
    repo = make_repo_copy(tmp_path / "repo")
    settings = repo / "adapters" / "amane" / "fc2_amane_adapter" / "_settings.py"
    settings.write_bytes(settings.read_bytes().replace(b'PLUGIN_ID = "ffcc.fc2-metadata"', b'PLUGIN_ID = "ffcc.fc2metadata"'))
    with pytest.raises(release.ReleaseError, match="PLUGIN_ID"):
        release.build_stage1(repo, stage1["wheel_path"])


def test_m2_02_api_version_is_never_overridden_by_the_shim_or_the_pin(stage1):
    for name, data in _zip_members(stage1).items():
        if "_impl/" in name:
            continue
        assert b"api_version" not in data, name


def test_e18_no_vendoring_no_core_file_or_core_bytes_in_the_plugin_zip(stage1):
    members = _zip_members(stage1)
    assert not [name for name in members if "fc2_metadata_core" in name.rsplit("/", 1)[-1] or "/fc2_metadata_core/" in name]
    core_files = [path.read_bytes().replace(b"\r\n", b"\n") for path in (REPO / "src" / "fc2_metadata_core").rglob("*.py") if "__pycache__" not in path.parts]
    for data in members.values():
        for core in core_files:
            if len(core) > 64:
                assert core not in data
    wheel_name = f"fc2_metadata_core-0.1.0-py3-none-any.whl"
    assert wheel_name not in members and not any(name.endswith(".whl") for name in members)


def test_e18_fc2_metadata_core_is_imported_only_by_impl_modules(stage1):
    for name, data in _zip_members(stage1).items():
        tree = ast.parse(data.decode("utf-8"))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported |= {alias.name.split(".")[0] for alias in node.names}
            elif isinstance(node, ast.ImportFrom):
                imported.add((node.module or "").split(".")[0])
        if "fc2_metadata_core" in imported:
            assert "/_impl/" in name, name


def test_m2_04_a_vendored_core_file_in_the_adapter_tree_is_rejected(tmp_path, release, stage1):
    repo = make_repo_copy(tmp_path / "repo")
    core_file = (REPO / "src" / "fc2_metadata_core" / "__init__.py").read_bytes().replace(b"\r\n", b"\n")
    target = repo / "adapters" / "amane" / "fc2_amane_adapter" / "_number.py"
    target.write_bytes(target.read_bytes() + b"\n# vendored:\n" + core_file)
    witness = repo / "docs" / "acceptance" / "evidence" / "P5_C1_HOST_WITNESS.json"
    with pytest.raises(release.ReleaseError, match="(embedded|differs)"):
        release.build_stage1(repo, stage1["wheel_path"], check_witness=False)
    with pytest.raises(release.ReleaseError, match="differs from P5-C1"):
        release.build_stage1(repo, stage1["wheel_path"])
    assert witness.exists()


@pytest.mark.parametrize(
    ("kind", "match"),
    [("init_file", "exactly"), ("extra_file", "exactly"), ("pycache_artifact", "(forbidden|exactly)"), ("env_file", "exactly"), ("absolute_path", "absolute path")],
)
def test_m2_09_forbidden_files_and_absolute_paths_are_rejected(tmp_path, release, stage1, kind, match):
    repo = make_repo_copy(tmp_path / "repo")
    tree = repo / "adapters" / "amane" / "fc2_amane_adapter"
    if kind == "init_file":
        (tree / "__init__.py").write_text("", encoding="utf-8")
    elif kind == "extra_file":
        (tree / "notes.py").write_text("X = 1\n", encoding="utf-8")
    elif kind == "pycache_artifact":
        (tree / "plugin.pyc").write_bytes(b"\0")
    elif kind == "env_file":
        (tree / ".env").write_text("TOKEN=x\n", encoding="utf-8")
    else:
        target = tree / "_number.py"
        target.write_bytes(target.read_bytes() + b'\n_LEAK = "C:\\\\Users\\\\someone\\\\secret"\n')
    with pytest.raises(release.ReleaseError, match=match):
        release.build_stage1(repo, stage1["wheel_path"], check_witness=False)


def test_pin_is_literals_only_and_agrees_with_the_real_wheel(stage1):
    pin_source = _zip_members(stage1)[f"{ROOT}/_ffcc_pin.py"].decode("utf-8")
    tree = ast.parse(pin_source)
    values = {}
    for node in tree.body:
        assert isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant), ast.dump(node)
        values[node.targets[0].id] = node.value.value
    assert values == {
        "PIN_SCHEMA_VERSION": 1, "CORE_DIST_NAME": "fc2-metadata-core", "CORE_VERSION": "0.1.0",
        "CORE_WHEEL_NAME": "fc2_metadata_core-0.1.0-py3-none-any.whl",
        "CORE_WHEEL_SHA256": hashlib.sha256(stage1["wheel_path"].read_bytes()).hexdigest(),
        "CORE_TREE_SHA256": WITNESS["core_tree_sha256"], "SIDECAR_DIRNAME": "_ffcc_core",
    }
    assert stage1["artifacts"]["pin_sha256"] == hashlib.sha256(pin_source.encode("utf-8")).hexdigest()


def test_e19_shim_files_have_no_write_network_or_host_imports(stage1):
    shim_names = (f"{ROOT}/plugin.py", f"{ROOT}/_ffcc_locator.py", f"{ROOT}/_ffcc_pin.py")
    members = _zip_members(stage1)
    for name in shim_names:
        tree = ast.parse(members[name].decode("utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert not {alias.name.split(".")[0] for alias in node.names} & {"amane", "pydantic", "httpx", "requests", "socket", "subprocess", "shutil"}, name
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                assert node.func.attr not in {"write_text", "write_bytes", "mkdir", "makedirs", "unlink", "rmtree", "copyfile"}, name


def test_u2_9_production_files_have_no_version_branches_or_feature_detection(stage1):
    """I-C2-6 / U2-9：shim + locator + pin 不含版本字符串分支、异常文本解析、feature detection。"""
    forbidden_names = {"__version__", "version_info", "traits", "multi_language", "max_attempts", "check_connectivity", "raw_results", "inspect", "signature", "hasattr"}
    for name in (f"{ROOT}/plugin.py", f"{ROOT}/_ffcc_locator.py", f"{ROOT}/_ffcc_pin.py"):
        tree = ast.parse(_zip_members(stage1)[name].decode("utf-8"))
        used = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                used.add(node.id)
            elif isinstance(node, ast.Attribute):
                used.add(node.attr)
            elif isinstance(node, ast.Import):
                used |= {alias.name for alias in node.names}
        assert not used & forbidden_names, (name, sorted(used & forbidden_names))
        assert not re.search(r"str\(\s*(exc|e|err|error)\b", ast.unparse(tree)), "exception text parsing is forbidden"


def test_install_text_threat_model_wording_and_directory_form_guard():
    """E31-t / E05：INSTALL 必须写明运行期间不要替换 / 删除 wheel；不含未被设计支持的承诺；不把 pip / 目录形态当作受支持来源。"""
    text = (REPO / "adapters" / "amane" / "release" / "INSTALL.zh-CN.md").read_text(encoding="utf-8")
    assert "运行期间不要替换或删除 sidecar wheel" in text
    for banned in ("publisher authenticity", "发布者认证", "数字签名", "防篡改"):
        assert banned not in text, banned
    for line in text.splitlines():
        if "pip" in line.lower():
            assert any(marker in line for marker in ("不要", "不再", "只可用于", "不是", "不会", "（不要", "**不要**")), f"pip may only appear in a negative / non-supported sense: {line}"
    assert "不要使用 pip" in text or "不要用 pip" in text or "不要用 `pip install`" in text
    assert "UNVERIFIED / informational — 不在本发布验收覆盖范围内" in text
    assert re.search(r"support claim is coordinate-scoped, not version-global", text)
    for banned in (r"v0\.1[58]\.0\s+(SUPPORTED|CONDITIONALLY)", r"支持\s*v0\.1[58]", r"支持\s*(Docker|macOS|Linux)", r"Docker\s*(已验证|SUPPORTED)"):
        assert not re.search(banned, text, re.IGNORECASE), banned


def test_install_text_contains_no_hashes_and_no_timestamps():
    text = (REPO / "adapters" / "amane" / "release" / "INSTALL.zh-CN.md").read_text(encoding="utf-8")
    assert not re.search(r"\b[0-9a-f]{40,64}\b", text)
    assert not re.search(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}", text)


def test_install_text_is_zh_cn_and_names_the_exact_artifacts():
    text = (REPO / "adapters" / "amane" / "release" / "INSTALL.zh-CN.md").read_text(encoding="utf-8")
    assert "ffcc.fc2-metadata-0.1.0.zip" in text and "fc2_metadata_core-0.1.0-py3-none-any.whl" in text
    assert "plugins/_ffcc_core/" in text and "uninstall → restart → replace artifact → install" in text
    assert sum(1 for char in text if "\u4e00" <= char <= "\u9fff") > 300
