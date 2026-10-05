"""P5-C2 E01（范围门）：``git diff <Package Frozen Base>..HEAD`` 只包含冻结计划第 4 节的 allow-list；冻结范围零 diff。

需要在真实 git 检出里运行（Package Frozen Base 必须可达）；不满足时测试**失败**（不 skip）。
"""

from __future__ import annotations

import re
import subprocess

import pytest

from _compat_support import REPO

BASE = "232ece06c1d166929846bc9c63ffc7314ea3a484"
PREFIX = "fc2-organizer/"

#: 计划第 4 节「新增 / 修改（允许）」+ 已接受的 P5-C2 设计文档（设计历史）
ALLOWED_PATTERNS = (
    r"adapters/amane/shim/(plugin|_ffcc_locator)\.py",
    r"adapters/amane/release/(core_release_ledger\.json|INSTALL\.zh-CN\.md)",
    r"adapters/amane/api_manifest/amane_v[0-9.]+_api_manifest\.json",
    r"adapters/amane/README\.md",
    r"tools/(build_core_wheel|build_amane_release|compare_amane_api|prepare_amane_hosts|run_amane_compat_gate)\.py",
    r"tests/amane_compat/.+",
    r"docs/acceptance/evidence/P5_C2_COMPATIBILITY_MATRIX\.json",
    r"docs/review/P5_C2_HANDOFF\.md",
    r"docs/P5_C2_CONSTRUCTION_PLAN\.md",
    r"docs/specifications/PHASE5_C2_AMANE_COMPATIBILITY_CONTRACT\.md",
)
#: 零 diff 范围（任何改动 = 升级门 U2-1 / U2-6 / U2-7 / U2-8）
FROZEN_PATTERNS = (
    r"src/.+",
    r"adapters/amane/fc2_amane_adapter/.+",
    r"tests/(?!amane_compat/).+",
    r"tools/(amane_api_manifest|build_amane_plugin_zip|run_amane_host_witness)\.py",
    r"pyproject\.toml",
    r"docs/specifications/PHASE5_C1_.+",
    r"docs/P5_C1_CONSTRUCTION_PLAN\.md",
    r"docs/review/P5_C1_HANDOFF\.md",
    r"docs/PROJECT_GOVERNANCE_ACCELERATION\.md",
    r"docs/acceptance/evidence/P5_C1_.+",
)


def _git(*args: str) -> str:
    completed = subprocess.run(["git", "-C", str(REPO), *args], capture_output=True, text=True, encoding="utf-8", check=False)
    assert completed.returncode == 0, f"git {' '.join(args)} failed: {completed.stderr.strip()}"
    return completed.stdout


def _changed() -> list[str]:
    names = [line for line in _git("diff", "--name-only", f"{BASE}..HEAD").splitlines() if line.strip()]
    return [name[len(PREFIX):] if name.startswith(PREFIX) else name for name in names]


def test_package_frozen_base_is_reachable_and_an_ancestor_of_head():
    _git("cat-file", "-e", f"{BASE}^{{commit}}")
    completed = subprocess.run(["git", "-C", str(REPO), "merge-base", "--is-ancestor", BASE, "HEAD"], capture_output=True, check=False)
    assert completed.returncode == 0


def test_every_changed_file_is_in_the_frozen_plan_allow_list():
    outside = [name for name in _changed() if not any(re.fullmatch(pattern, name) for pattern in ALLOWED_PATTERNS)]
    assert outside == [], f"files outside the P5-C2 allow-list: {outside}"


def test_frozen_scopes_have_zero_diff():
    touched = [name for name in _changed() if any(re.fullmatch(pattern, name) for pattern in FROZEN_PATTERNS)]
    assert touched == [], f"frozen files changed: {touched}"


def test_p5_c1_adapter_tree_hash_still_equals_the_c1_witness():
    """U2-6：``tree_sha256(adapters/amane/fc2_amane_adapter)`` == ``P5_C1_HOST_WITNESS.adapter_tree_sha256``（规范化字节）。"""
    import hashlib
    import json

    tree = REPO / "adapters" / "amane" / "fc2_amane_adapter"
    digest = hashlib.sha256()
    for path in sorted(tree.rglob("*.py"), key=lambda item: item.relative_to(tree).as_posix()):
        if "__pycache__" in path.parts:
            continue
        data = path.read_bytes().replace(b"\r\n", b"\n")
        digest.update(path.relative_to(tree).as_posix().encode("utf-8") + b"\0" + hashlib.sha256(data).hexdigest().encode("ascii") + b"\n")
    witness = json.loads((REPO / "docs" / "acceptance" / "evidence" / "P5_C1_HOST_WITNESS.json").read_text(encoding="utf-8"))
    assert digest.hexdigest() == witness["adapter_tree_sha256"]


def test_no_source_file_in_the_change_set_contains_control_characters():
    """防止转义序列误伤（例如反斜杠 + b / r 被吞成控制字符）：新增 / 修改的文本文件不得含 C0 控制字符。"""
    bad = []
    for name in _changed():
        path = REPO / name
        if not path.is_file() or path.suffix not in {".py", ".md", ".json", ".toml"}:
            continue
        data = path.read_bytes()
        if re.search(rb"[\x00-\x08\x0b\x0c\x0e-\x1f]", data):
            bad.append(name)
    assert bad == []


def test_working_tree_changes_are_limited_to_the_allow_list_as_well():
    status = _git("status", "--porcelain=v1", "--untracked-files=all").splitlines()
    paths = [line[3:].strip().strip('"') for line in status]
    paths = [item[len(PREFIX):] if item.startswith(PREFIX) else item for item in paths]
    outside = [name for name in paths if not any(re.fullmatch(pattern, name) for pattern in ALLOWED_PATTERNS)]
    assert outside == [], f"uncommitted files outside the allow-list: {outside}"
