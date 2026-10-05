"""P5-C2 E05「文档即测试」：``INSTALL.zh-CN.md`` 的每一步都被真实宿主见证执行。

``tools/run_amane_compat_gate.py`` 在**真实 Amane 宿主**上逐步执行文档里的操作（放置 sidecar wheel、上传 plugin zip、把插件加入 FC2
内容路由、配置、升级 / 卸载、各故障分支）。本测试把文档的每一步 / 每一行与产生它的见证场景一一绑定：

* 文档结构变化（步骤数 / 升级行 / 故障条目）会使本测试失败，迫使映射与网关一起更新；
* 每个被映射的场景在**已提交的 MATRIX** 里，对四个必需宿主（SC-01..SC-04）都必须是 ``passed``；
* 文档中的故障消息必须与网关实际断言过的 P5-C1 §22 冻结消息逐字相同。
"""

from __future__ import annotations

import json
import re

import pytest

from _compat_support import REPO, load_tool

INSTALL = (REPO / "adapters" / "amane" / "release" / "INSTALL.zh-CN.md").read_text(encoding="utf-8")
MATRIX = json.loads((REPO / "docs" / "acceptance" / "evidence" / "P5_C2_COMPATIBILITY_MATRIX.json").read_text(encoding="utf-8"))

#: 第 3 节「安装」的 5 个步骤 -> 执行它们的见证场景
INSTALL_STEP_COVERAGE = {
    1: ("HC-18",),          # 数据目录 = 临时目录；用户目录零接触
    2: ("HC-01",),          # 创建 plugins/_ffcc_core/ 并原样复制 wheel
    3: ("HC-01", "HC-06"),  # 上传 plugin zip；无需重启（reload 不重建 Core）
    4: ("HC-01",),          # 把插件加入 FC2 内容路由（真实 PATCH /api/config）
    5: ("HC-05", "HC-08"),  # 配置往返
}
#: 第 5 节「升级」表的两行
UPGRADE_COVERAGE = {"只升级插件": ("HC-09",), "升级 Core": ("HC-16",)}
#: 其它章节
SECTION_COVERAGE = {"缺失 Core 的提示": ("HC-10",), "不兼容 Core": ("HC-11", "HC-19"), "卸载": ("HC-15",), "运行期间不要替换或删除 sidecar wheel": ("HC-15", "HC-19")}


@pytest.fixture(scope="module")
def gate():
    return load_tool("run_amane_compat_gate.py")


def _section(title_prefix: str) -> str:
    match = re.search(rf"^## {re.escape(title_prefix)}.*?$(.*?)(?=^## |\Z)", INSTALL, re.MULTILINE | re.DOTALL)
    assert match, title_prefix
    return match.group(1)


def test_install_section_3_has_exactly_the_five_documented_steps():
    steps = re.findall(r"^(\d+)\. ", _section("3. 安装"), re.MULTILINE)
    assert [int(item) for item in steps] == sorted(INSTALL_STEP_COVERAGE), "INSTALL 的步骤变化时必须同步更新网关与本映射"


def test_install_step_texts_name_the_actions_the_gate_really_performs():
    section = _section("3. 安装")
    assert "plugins/_ffcc_core/" in section and "原样复制" in section                       # 步骤 2
    assert "上传" in section and "无需重启" in section and "运行期间不要替换或删除 sidecar wheel" in section  # 步骤 3
    assert "内容路由" in section and "FC2" in section                                      # 步骤 4
    assert "管理 → 插件" in section and "按需修改配置" in section                           # 步骤 5
    assert "先放 Core，再装插件" in section                                                 # 顺序要求（W2-01）


def test_install_upgrade_table_rows_are_exactly_the_two_documented_flows():
    rows = re.findall(r"^\| (.+?) \| .+? \| (是|否) \|$", _section("5. 升级"), re.MULTILINE)
    labels = [label for label, _restart in rows if label not in ("变更",)]
    assert any(label.startswith("只升级插件") for label in labels) and any(label.startswith("升级 Core") for label in labels)
    restart = {label.split("（")[0]: flag for label, flag in rows}
    assert restart["只升级插件"] == "否" and restart["升级 Core"] == "是"
    assert "uninstall → restart → replace artifact → install" in INSTALL


def test_every_documented_step_is_covered_by_a_passing_scenario_on_every_required_host(gate):
    required = [host for host in MATRIX["hosts"] if host["role"] == "required"]
    assert len(required) == 4
    covered = {name for names in (*INSTALL_STEP_COVERAGE.values(), *UPGRADE_COVERAGE.values(), *SECTION_COVERAGE.values()) for name in names}
    assert covered <= set(gate.SCENARIO_IDS)
    for host in required:
        passed = {item["id"] for item in host["scenarios"] if item["passed"]}
        assert covered <= passed, (host["label"], sorted(covered - passed))


def test_documented_missing_core_message_is_the_p5_c1_frozen_message_the_gate_asserts(gate):
    documented = re.search(r"`(FC2 Metadata Core 未安装或版本不兼容：[^`]+)`", INSTALL)
    assert documented, "INSTALL must quote the P5-C1 frozen message"
    assert gate.C1_MISSING_CORE_MESSAGE == "插件导入失败: " + documented.group(1)


def test_install_documents_each_sidecar_failure_without_inventing_a_pip_or_directory_route():
    for phrase in ("不要使用 pip", "即使其中的字节完全正确", "plugins/_ffcc_core/"):
        assert phrase in INSTALL or phrase.replace("不要使用 pip", "不要用 `pip install`") in INSTALL, phrase
    assert "一律不被接受" in INSTALL


def test_documented_file_names_equal_the_artifacts_the_matrix_was_produced_from():
    release = load_tool("build_amane_release.py")
    builder = load_tool("build_core_wheel.py")
    name, payload, _tree = builder.build_wheel_bytes(REPO / "src" / "fc2_metadata_core", REPO / "pyproject.toml")
    assert name in INSTALL and f"{release.PLUGIN_ID}-0.1.0.zip" in INSTALL
    assert MATRIX["core_admission"]["core_wheel_sha256"] == __import__("hashlib").sha256(payload).hexdigest()


def test_install_documents_unverified_platforms_and_the_coordinate_scope():
    assert "UNVERIFIED" in INSTALL and "macOS、Linux、Docker" in INSTALL
    assert "support claim is coordinate-scoped, not version-global" in INSTALL
    for coordinate in ("SC-01", "SC-02", "SC-03", "SC-04"):
        assert coordinate in INSTALL
