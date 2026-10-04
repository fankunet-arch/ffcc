"""P5-C1 打包骨架（E4 打包部分）：确定性 zip；单一顶层文件夹；无 Core / 无 __pycache__ / 无测试与文档。
真实 ``install_plugin_zip`` 安装见 H-03。"""

from __future__ import annotations

import hashlib
import importlib.util
import io
import shutil
import zipfile
from pathlib import Path

import pytest

from fc2_amane_adapter._settings import PLUGIN_ID

ROOT = Path(__file__).resolve().parents[2]
TREE = ROOT / "adapters" / "amane" / "fc2_amane_adapter"
BUILDER_PATH = ROOT / "tools" / "build_amane_plugin_zip.py"

_spec = importlib.util.spec_from_file_location("build_amane_plugin_zip_under_test", BUILDER_PATH)
builder = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(builder)  # type: ignore[union-attr]

EXPECTED_FILES = sorted(
    f"{PLUGIN_ID}/{name}" for name in ("plugin.py", "_core_gate.py", "_settings.py", "_number.py", "_bridge.py", "_runtime.py", "_outcome.py")
)


def test_builder_plugin_id_equals_the_adapter_plugin_id():
    assert builder.PLUGIN_ID == PLUGIN_ID == "ffcc.fc2-metadata"


def test_build_is_deterministic_byte_for_byte():
    first = builder.build_zip_bytes(TREE)
    for _ in range(3):
        assert builder.build_zip_bytes(TREE) == first
    assert hashlib.sha256(first).hexdigest() == hashlib.sha256(builder.build_zip_bytes(TREE)).hexdigest()


def test_zip_has_one_top_level_folder_named_by_the_plugin_id_and_exactly_the_tree_files():
    with zipfile.ZipFile(io.BytesIO(builder.build_zip_bytes(TREE))) as archive:
        names = archive.namelist()
    assert names == EXPECTED_FILES == sorted(names)
    assert {name.split("/")[0] for name in names} == {PLUGIN_ID}
    assert f"{PLUGIN_ID}/plugin.py" in names
    assert not any("__init__" in name or "__pycache__" in name for name in names)
    assert not any(name.endswith("/") for name in names)


def test_zip_contains_no_core_tests_docs_or_non_python_files():
    with zipfile.ZipFile(io.BytesIO(builder.build_zip_bytes(TREE))) as archive:
        names = archive.namelist()
    assert all(name.endswith(".py") for name in names)
    assert not any("fc2_metadata_core" in name or "test" in name.split("/")[-1] or "docs" in name for name in names)


def test_timestamps_permissions_and_system_are_fixed():
    with zipfile.ZipFile(io.BytesIO(builder.build_zip_bytes(TREE))) as archive:
        for info in archive.infolist():
            assert info.date_time == (1980, 1, 1, 0, 0, 0)
            assert info.external_attr == 0o100644 << 16
            assert info.create_system == 3
            assert info.compress_type == zipfile.ZIP_DEFLATED


def test_zip_contents_equal_the_tree_with_lf_line_endings():
    with zipfile.ZipFile(io.BytesIO(builder.build_zip_bytes(TREE))) as archive:
        for name in archive.namelist():
            expected = (TREE / name.split("/", 1)[1]).read_bytes().replace(b"\r\n", b"\n")
            assert archive.read(name) == expected


def test_crlf_and_lf_checkouts_give_identical_bytes(tmp_path):
    lf, crlf = tmp_path / "lf", tmp_path / "crlf"
    lf.mkdir(), crlf.mkdir()
    for path in TREE.glob("*.py"):
        data = path.read_bytes().replace(b"\r\n", b"\n")
        (lf / path.name).write_bytes(data)
        (crlf / path.name).write_bytes(data.replace(b"\n", b"\r\n"))
    assert builder.build_zip_bytes(lf) == builder.build_zip_bytes(crlf) == builder.build_zip_bytes(TREE)


def test_zip_is_within_the_amane_size_limit_and_contains_no_secrets():
    payload = builder.build_zip_bytes(TREE)
    assert len(payload) < builder.MAX_ZIP_BYTES
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        text = b"\n".join(archive.read(name) for name in archive.namelist()).lower()
    for needle in (b"begin private key", b"api_key=", b"password=", b"secret_key"):
        assert needle not in text


@pytest.mark.parametrize(
    ("setup", "message"),
    [
        (lambda tree: (tree / "__init__.py").write_text(""), "__init__"),
        (lambda tree: (tree / "notes.txt").write_text("x"), "only .py"),
        (lambda tree: (tree / "fc2_metadata_core_copy.py").write_text("x"), "Core"),
        (lambda tree: (tree / "plugin.py").unlink(), "plugin.py"),
        (lambda tree: (tree / "sub").mkdir(), "non-file"),
    ],
)
def test_builder_refuses_trees_that_break_the_frozen_layout(tmp_path, setup, message):
    tree = tmp_path / "tree"
    shutil.copytree(TREE, tree, ignore=shutil.ignore_patterns("__pycache__"))
    setup(tree)
    with pytest.raises(builder.PluginTreeError, match=message):
        builder.build_zip_bytes(tree)


def test_pycache_directories_are_skipped(tmp_path):
    tree = tmp_path / "tree"
    shutil.copytree(TREE, tree, ignore=shutil.ignore_patterns("__pycache__"))
    (tree / "__pycache__").mkdir()
    (tree / "__pycache__" / "plugin.cpython-312.pyc").write_bytes(b"\x00")
    assert builder.build_zip_bytes(tree) == builder.build_zip_bytes(TREE)
