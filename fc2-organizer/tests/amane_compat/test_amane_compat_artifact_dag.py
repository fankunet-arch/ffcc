"""P5-C2 E29 / M2-22：artifact 派生 DAG 严格无环（合同第 10.5 节）。

L0 Core wheel -> L1 plugin zip / INSTALL / VERSION -> （验收运行得到 MATRIX Part A）-> L2 COMPATIBILITY.json
-> L3 SHA256SUMS -> L4 bundle -> L5（MATRIX Part B；外部，不写回 bundle）。
这里使用**合成 Part A**，真实 L0 / L1；真实 Part A 在 S3 的最终证据测试里核对。
"""

from __future__ import annotations

import copy
import hashlib
import io
import json
import zipfile

import pytest

from _compat_support import REPO, load_tool, synthetic_matrix

ROOT = "ffcc.fc2-metadata"
BUNDLE = "ffcc-amane-release-0.1.0.zip"
WHEEL = "fc2_metadata_core-0.1.0-py3-none-any.whl"
SUM_MEMBERS = ["COMPATIBILITY.json", "INSTALL.zh-CN.md", "VERSION", WHEEL, f"{ROOT}-0.1.0.zip"]


@pytest.fixture(scope="module")
def release():
    return load_tool("build_amane_release.py")


@pytest.fixture(scope="module")
def world(release, tmp_path_factory):
    builder = load_tool("build_core_wheel.py")
    name, payload, _tree = builder.build_wheel_bytes(REPO / "src" / "fc2_metadata_core", REPO / "pyproject.toml")
    wheel_path = tmp_path_factory.mktemp("dag") / name
    wheel_path.write_bytes(payload)
    stage1 = release.build_stage1(REPO, wheel_path)
    matrix = synthetic_matrix(stage1["artifacts"])
    produced = release.build_finalize(stage1, name, payload, matrix)
    return {"stage1": stage1, "wheel": payload, "matrix": matrix, "produced": produced, "wheel_name": name, "wheel_path": wheel_path}


def _bundle(produced) -> dict[str, bytes]:
    with zipfile.ZipFile(io.BytesIO(produced[BUNDLE])) as archive:
        return {name: archive.read(name) for name in archive.namelist()}


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def test_bundle_has_exactly_six_members_and_they_equal_the_accepted_level_0_1_bytes(world):
    members = _bundle(world["produced"])
    assert sorted(members) == sorted([*SUM_MEMBERS, "SHA256SUMS"])
    assert members[WHEEL] == world["wheel"]
    for name, data in world["stage1"]["files"].items():
        assert members[name] == data
    assert members["COMPATIBILITY.json"] == world["produced"]["COMPATIBILITY.json"]
    assert members["SHA256SUMS"] == world["produced"]["SHA256SUMS"]


def test_sha256sums_lists_the_five_members_sorted_lf_and_not_itself_and_verifies(world):
    text = world["produced"]["SHA256SUMS"].decode("utf-8")
    assert "\r" not in text and text.endswith("\n")
    lines = text.splitlines()
    assert [line.split("  ", 1)[1] for line in lines] == sorted(SUM_MEMBERS)
    members = _bundle(world["produced"])
    for line in lines:
        digest, name = line.split("  ", 1)
        assert _sha(members[name]) == digest, f"sha256sum -c would fail for {name}"
    assert "SHA256SUMS" not in text


def test_no_member_embeds_a_hash_of_itself_or_of_a_higher_layer(world):
    """拓扑：任何成员的内容不依赖其自身或更高层的哈希。"""
    produced, members = world["produced"], _bundle(world["produced"])
    l4 = _sha(produced[BUNDLE])
    l3 = _sha(produced["SHA256SUMS"])
    l2 = _sha(produced["COMPATIBILITY.json"])
    matrix_hash = _sha(json.dumps(world["matrix"], sort_keys=True).encode("utf-8"))
    higher_for = {
        f"{ROOT}-0.1.0.zip": [l2, l3, l4, matrix_hash],
        "INSTALL.zh-CN.md": [l2, l3, l4, matrix_hash],
        "VERSION": [l2, l3, l4, matrix_hash],
        WHEEL: [l2, l3, l4, matrix_hash],
        "COMPATIBILITY.json": [l2, l3, l4, matrix_hash],
        "SHA256SUMS": [l3, l4, matrix_hash],
    }
    for name, forbidden in higher_for.items():
        for digest in forbidden:
            assert digest.encode("ascii") not in members[name], (name, digest[:12])
    # 同时：L1 成员不含任何 L2+ 层的“字段名”
    for name in ("INSTALL.zh-CN.md", "VERSION"):
        assert not __import__("re").search(rb"\b[0-9a-f]{64}\b", members[name]), name
    for key in ("sha256sums", "release_bundle", "compatibility_json", "final_artifacts"):
        assert key.encode("ascii") not in members["COMPATIBILITY.json"], key


def test_compatibility_json_has_no_volatile_data_and_is_a_pure_projection_of_part_a(world, release):
    text = world["produced"]["COMPATIBILITY.json"].decode("utf-8")
    document = json.loads(text)
    assert text.endswith("\n") and "\r" not in text
    assert document["matrix_part_a"] == release.project_part_a(world["matrix"])
    assert document["kind"] == "ffcc-amane-compatibility" and document["bundle_version"] == "0.1.0+core0.1.0"
    assert "coordinate-scoped, not version-global" in document["support_claim"]
    assert document["known_limitations"][0] == "L-C2-01" and len(document["known_limitations"]) == 13
    assert not __import__("re").search(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}|[A-Za-z]:\\\\|/Users/", text)


def test_changing_part_b_does_not_change_level_2_to_4_bytes(world, release):
    stage1, matrix = world["stage1"], copy.deepcopy(world["matrix"])
    baseline = world["produced"]
    matrix["final_artifacts"] = {"compatibility_json_sha256": "11" * 32, "sha256sums_sha256": "22" * 32, "release_bundle_sha256": "33" * 32}
    again = release.build_finalize(stage1, world["wheel_name"], world["wheel"], matrix)
    assert again == baseline
    matrix["final_artifacts"] = {"compatibility_json_sha256": "99" * 32, "sha256sums_sha256": "88" * 32, "release_bundle_sha256": "77" * 32}
    assert release.build_finalize(stage1, world["wheel_name"], world["wheel"], matrix) == baseline
    matrix.pop("final_artifacts")
    assert release.build_finalize(stage1, world["wheel_name"], world["wheel"], matrix) == baseline


def test_changing_part_a_changes_level_2_to_4_but_never_level_0_or_1(world, release):
    matrix = copy.deepcopy(world["matrix"])
    matrix["hosts"][0]["scenarios"][0]["passed"] = False
    changed = release.build_finalize(world["stage1"], world["wheel_name"], world["wheel"], matrix)
    for name in ("COMPATIBILITY.json", "SHA256SUMS", BUNDLE):
        assert changed[name] != world["produced"][name], name
    # L0 / L1 没有任何输入来自 Part A：finalize 只读取它们，也不改变它们（stage1 在 finalize 之前已固定）。
    assert changed["COMPATIBILITY.json"] != world["produced"]["COMPATIBILITY.json"]
    assert release.build_stage1(REPO, world["wheel_path"])["files"] == world["stage1"]["files"]


def test_the_projection_reads_only_the_part_a_whitelist(world, release):
    """L2 的投影只读取 Part A 的白名单：投毒的 Part B / 未知键 / 主机内部观测哈希不影响输出。"""
    poisoned = copy.deepcopy(world["matrix"])
    poisoned["final_artifacts"] = {"compatibility_json_sha256": "ff" * 32}
    for host in poisoned["hosts"]:
        for scenario in host["scenarios"]:
            scenario["observations_sha256"] = "cd" * 32
        host["deps_lock_sha256"] = "ee" * 32
        host["api_fingerprint_sha256"] = "dd" * 32
    assert release.project_part_a(poisoned) == release.project_part_a(world["matrix"])
    projected = json.dumps(release.project_part_a(world["matrix"]))
    assert "observations_sha256" not in projected and "deps_lock_sha256" not in projected


def test_rebuild_from_the_repository_tree_is_byte_identical(world, release):
    again = release.build_finalize(world["stage1"], world["wheel_name"], world["wheel"], world["matrix"])
    assert again == world["produced"]


def test_a_cyclic_variant_never_reaches_a_fixed_point(world, release):
    """证明原设计的环：若 COMPATIBILITY.json 内嵌 SHA256SUMS 的哈希，重新计算后该哈希立即过期。"""
    stage1, matrix = world["stage1"], copy.deepcopy(world["matrix"])
    embedded = "0" * 64
    seen = []
    for _ in range(4):
        files = dict(stage1["files"])
        files[world["wheel_name"]] = world["wheel"]
        compat = json.loads(release.render_compatibility_json(matrix, stage1))
        compat["sha256sums_sha256"] = embedded
        files["COMPATIBILITY.json"] = (json.dumps(compat, sort_keys=True) + "\n").encode("utf-8")
        recomputed = _sha(release.render_sha256sums(files))
        seen.append((embedded, recomputed))
        if recomputed == embedded:
            break
        embedded = recomputed
    assert all(old != new for old, new in seen), "a self-referential hash must never be a fixed point"


def test_sha256sums_refuses_to_list_itself(release):
    with pytest.raises(release.ReleaseError):
        release.render_sha256sums({"SHA256SUMS": b"x", "VERSION": b"y"})


def test_finalize_cli_refuses_a_stage1_directory_that_differs_from_a_fresh_rebuild(tmp_path, world, release):
    import subprocess
    import sys

    out1 = tmp_path / "l1"
    out1.mkdir()
    wheel = tmp_path / world["wheel_name"]
    wheel.write_bytes(world["wheel"])
    for name, data in world["stage1"]["files"].items():
        (out1 / name).write_bytes(data)
    (out1 / "VERSION").write_bytes(b"bundle 9.9.9+core9.9.9\n")
    matrix = tmp_path / "matrix.json"
    matrix.write_text(json.dumps(world["matrix"], sort_keys=True), encoding="utf-8")
    completed = subprocess.run(
        [sys.executable, str(REPO / "tools" / "build_amane_release.py"), "finalize", "--core-wheel", str(wheel), "--stage1-dir", str(out1), "--matrix", str(matrix), "--out", str(tmp_path / "l4")],
        capture_output=True, text=True, check=False,
    )
    assert completed.returncode != 0 and "differs from a fresh rebuild" in completed.stderr
