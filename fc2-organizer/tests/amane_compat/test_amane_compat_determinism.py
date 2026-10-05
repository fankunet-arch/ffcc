"""P5-C2 E06 / E31-q / E29（构建确定性）：Core wheel、plugin zip、bundle 的“同输入 -> 同字节”。

确定性矩阵：两个解释器（3.12 与 3.14）× 两个不同输出目录 × LF / CRLF（autocrlf）检出副本。
所有构建通过**真实 CLI**（``python tools/<tool>.py``）执行。
"""

from __future__ import annotations

import base64
import hashlib
import io
import json
import subprocess
import zipfile
from pathlib import Path

import pytest

from _compat_support import REPO, TOOLS, interpreters, load_tool, make_repo_copy, synthetic_matrix

WITNESS = json.loads((REPO / "docs" / "acceptance" / "evidence" / "P5_C1_HOST_WITNESS.json").read_text(encoding="utf-8"))
FIXED_TIME = (1980, 1, 1, 0, 0, 0)


def _run(python: str, script: str, *args: str) -> str:
    completed = subprocess.run([python, str(TOOLS / script), *args], capture_output=True, text=True, encoding="utf-8", timeout=300, check=False)
    assert completed.returncode == 0, completed.stderr[-1500:]
    return completed.stdout


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _python(label: str, path: str | None) -> str:
    assert path, f"E06 需要 {label} 解释器（不允许 skip）"
    return path


def test_wheel_contents_are_core_only_py_plus_four_dist_info_files(core_wheel):
    """E31-q：仅 ``*.py`` + 4 个 dist-info 文件；无 pyc / pyd / so / pth / fc2_organizer / 测试；成员 tree 哈希 == C1 ``core_tree_sha256``。"""
    names = []
    members = []
    with zipfile.ZipFile(core_wheel) as archive:
        for info in archive.infolist():
            names.append(info.filename)
            assert info.compress_type == zipfile.ZIP_STORED and info.date_time == FIXED_TIME
            assert info.external_attr == 0o100644 << 16 and info.create_system == 3
            if info.filename.startswith("fc2_metadata_core/"):
                assert info.filename.endswith(".py") and "__pycache__" not in info.filename
                members.append((info.filename[len("fc2_metadata_core/"):], archive.read(info.filename)))
    dist_info = [name for name in names if name.startswith("fc2_metadata_core-0.1.0.dist-info/")]
    assert sorted(dist_info) == [f"fc2_metadata_core-0.1.0.dist-info/{item}" for item in ("METADATA", "RECORD", "WHEEL", "top_level.txt")]
    assert len(names) == len(dist_info) + len(members) and len(members) == 40
    assert not [name for name in names if "fc2_organizer" in name or name.endswith((".pyc", ".pyd", ".so", ".pth"))]
    assert names == sorted(names, key=lambda item: item.encode("utf-8")), "entries must be in posix byte order"
    release = load_tool("build_amane_release.py")
    assert release.tree_sha256(members) == WITNESS["core_tree_sha256"]


def test_wheel_record_metadata_and_wheel_files_are_exact(core_wheel):
    with zipfile.ZipFile(core_wheel) as archive:
        record = archive.read("fc2_metadata_core-0.1.0.dist-info/RECORD").decode("utf-8")
        lines = record.splitlines()
        assert record.endswith("\n") and "\r" not in record
        assert lines[-1] != "" and "fc2_metadata_core-0.1.0.dist-info/RECORD,," in lines
        for line in lines:
            path, digest, size = line.rsplit(",", 2)
            if path.endswith("/RECORD"):
                assert (digest, size) == ("", "")
                continue
            data = archive.read(path)
            assert digest == "sha256=" + base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=").decode("ascii")
            assert int(size) == len(data)
        assert len(lines) == len(archive.namelist())
        assert archive.read("fc2_metadata_core-0.1.0.dist-info/WHEEL").decode("utf-8") == (
            "Wheel-Version: 1.0\nGenerator: ffcc-build-core-wheel (1)\nRoot-Is-Purelib: true\nTag: py3-none-any\n"
        )
        metadata = archive.read("fc2_metadata_core-0.1.0.dist-info/METADATA").decode("utf-8")
        assert "Name: fc2-metadata-core\n" in metadata and "Version: 0.1.0\n" in metadata
        assert "Requires-Python: >=3.11\n" in metadata and "Requires-Dist: httpx<0.28,>=0.27\n" in metadata
        assert archive.read("fc2_metadata_core-0.1.0.dist-info/top_level.txt") == b"fc2_metadata_core\n"


def test_wheel_is_byte_identical_across_in_process_rebuilds(core_wheel):
    builder = load_tool("build_core_wheel.py")
    name, payload, _tree = builder.build_wheel_bytes(REPO / "src" / "fc2_metadata_core", REPO / "pyproject.toml")
    assert name == core_wheel.name and payload == core_wheel.read_bytes()


def test_e06_wheel_plugin_zip_and_bundle_are_identical_across_interpreters_output_dirs_and_crlf(tmp_path):
    """3.12 与 3.14 × 两个输出目录 × LF / CRLF 检出 -> L0 / L1 / L4 哈希全部相等。"""
    results: dict[str, dict[str, str]] = {}
    matrix_path = tmp_path / "matrix.json"
    for label, python in interpreters():
        python = _python(label, python)
        for crlf in (False, True):
            repo = make_repo_copy(tmp_path / f"repo-{label}-{crlf}", crlf=crlf)
            for variant, order in (("A", "wheel-first"), ("B", "wheel-first")):
                out = tmp_path / f"out-{label}-{crlf}-{variant}"
                _run(python, "build_core_wheel.py", "--repo-root", str(repo), "--out", str(out / "l0"))
                wheel = next((out / "l0").glob("*.whl"))
                _run(python, "build_amane_release.py", "--repo-root", str(repo), "stage1", "--core-wheel", str(wheel), "--out", str(out / "l1"))
                artifacts = {}
                if not matrix_path.exists():
                    release = load_tool("build_amane_release.py")
                    stage1 = release.build_stage1(repo, wheel)
                    matrix_path.write_text(json.dumps(synthetic_matrix(stage1["artifacts"]), sort_keys=True), encoding="utf-8")
                _run(python, "build_amane_release.py", "--repo-root", str(repo), "finalize", "--core-wheel", str(wheel), "--stage1-dir", str(out / "l1"), "--matrix", str(matrix_path), "--out", str(out / "l4"))
                key = f"{label}-crlf{crlf}-{variant}"
                results[key] = {
                    "wheel": _sha(wheel),
                    **{path.name: _sha(path) for path in sorted((out / "l1").iterdir())},
                    **{path.name: _sha(path) for path in sorted((out / "l4").iterdir())},
                }
    reference = next(iter(results.values()))
    assert len(results) == 8
    for key, value in results.items():
        assert value == reference, key
    assert {"wheel", "ffcc.fc2-metadata-0.1.0.zip", "INSTALL.zh-CN.md", "VERSION", "COMPATIBILITY.json", "SHA256SUMS", "ffcc-amane-release-0.1.0.zip"} <= set(reference)


def test_build_order_does_not_change_the_bytes(tmp_path, core_wheel):
    """“不同的构建顺序”：先 plugin zip 后 wheel，与先 wheel 后 plugin zip 的结果相同（二者都只依赖仓库树）。"""
    release = load_tool("build_amane_release.py")
    first = release.build_stage1(REPO, core_wheel)
    builder = load_tool("build_core_wheel.py")
    _name, payload, _tree = builder.build_wheel_bytes(REPO / "src" / "fc2_metadata_core", REPO / "pyproject.toml")
    second = release.build_stage1(REPO, core_wheel)
    assert first["files"] == second["files"] and payload == core_wheel.read_bytes()


# ------------------------------------------------------------------ 台账与输入守卫（E29 / 合同 8.5）

def test_ledger_rejects_the_same_version_with_a_different_tree_hash(tmp_path):
    repo = make_repo_copy(tmp_path / "repo")
    core_file = repo / "src" / "fc2_metadata_core" / "__init__.py"
    core_file.write_bytes(core_file.read_bytes() + b"\n# changed Core source without bumping the version\n")
    completed = subprocess.run([interpreters()[0][1], str(TOOLS / "build_core_wheel.py"), "--repo-root", str(repo), "--out", str(tmp_path / "out")], capture_output=True, text=True, check=False)
    assert completed.returncode != 0 and "different tree hash" in completed.stderr


def test_ledger_rejects_an_unreleased_version_unless_explicitly_updated(tmp_path):
    repo = make_repo_copy(tmp_path / "repo")
    pyproject = repo / "pyproject.toml"
    pyproject.write_bytes(pyproject.read_bytes().replace(b'version = "0.1.0"', b'version = "0.2.0"'))
    python = interpreters()[0][1]
    rejected = subprocess.run([python, str(TOOLS / "build_core_wheel.py"), "--repo-root", str(repo), "--out", str(tmp_path / "out")], capture_output=True, text=True, check=False)
    assert rejected.returncode != 0 and "not in the release ledger" in rejected.stderr
    accepted = subprocess.run([python, str(TOOLS / "build_core_wheel.py"), "--repo-root", str(repo), "--out", str(tmp_path / "out"), "--update-ledger"], capture_output=True, text=True, check=False)
    assert accepted.returncode == 0, accepted.stderr
    ledger = json.loads((repo / "adapters" / "amane" / "release" / "core_release_ledger.json").read_text(encoding="utf-8"))
    assert set(ledger["versions"]) == {"0.1.0", "0.2.0"}


def test_committed_ledger_matches_the_frozen_core_and_the_real_wheel(core_wheel):
    ledger = json.loads((REPO / "adapters" / "amane" / "release" / "core_release_ledger.json").read_text(encoding="utf-8"))
    entry = ledger["versions"]["0.1.0"]
    assert entry["core_tree_sha256"] == WITNESS["core_tree_sha256"]
    assert entry["wheel_sha256"] == hashlib.sha256(core_wheel.read_bytes()).hexdigest()


@pytest.mark.parametrize("mutation", ["pyc_file", "non_py_file", "bom", "non_utf8", "pth_file"])
def test_builder_rejects_forbidden_core_inputs(tmp_path, mutation):
    builder = load_tool("build_core_wheel.py")
    repo = make_repo_copy(tmp_path / "repo")
    core = repo / "src" / "fc2_metadata_core"
    if mutation == "pyc_file":
        (core / "stray.pyc").write_bytes(b"\0")
    elif mutation == "non_py_file":
        (core / "data.txt").write_text("x", encoding="utf-8")
    elif mutation == "bom":
        (core / "bom.py").write_bytes(b"\xef\xbb\xbfX = 1\n")
    elif mutation == "non_utf8":
        (core / "latin.py").write_bytes(b"X = '\xe9'\n")
    else:
        (core / "x.pth").write_text("import os\n", encoding="utf-8")
    with pytest.raises(builder.CoreWheelError):
        builder.build_wheel_bytes(core, repo / "pyproject.toml")


def test_builder_ignores_pycache_directories_but_never_packages_them(tmp_path):
    builder = load_tool("build_core_wheel.py")
    repo = make_repo_copy(tmp_path / "repo")
    cache = repo / "src" / "fc2_metadata_core" / "__pycache__"
    cache.mkdir()
    (cache / "x.cpython-312.pyc").write_bytes(b"\0")
    _name, payload, _tree = builder.build_wheel_bytes(repo / "src" / "fc2_metadata_core", repo / "pyproject.toml")
    assert "__pycache__" not in "".join(zipfile.ZipFile(io.BytesIO(payload)).namelist())
