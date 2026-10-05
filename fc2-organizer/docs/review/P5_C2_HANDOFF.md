# P5-C2 HANDOFF —— Amane Compatibility & Adapter Closure（实现完成；等待独立 Level 1 Review）

```text
P5-C2                    : IMPLEMENTATION COMPLETE —— NOT YET CLOSED（等待一次独立 Level 1 Review；本文不是 CLOSED / Technical Acceptance）
Branch                   : claude/phase5-c2-amane-compatibility
Package Frozen Base      : 232ece06c1d166929846bc9c63ffc7314ea3a484
Frozen Contract          : docs/specifications/PHASE5_C2_AMANE_COMPATIBILITY_CONTRACT.md @ f358aca1ff6e056f28c3b9b2d0fcaa2f608ac124
Frozen Construction Plan : docs/P5_C2_CONSTRUCTION_PLAN.md @ f358aca1ff6e056f28c3b9b2d0fcaa2f608ac124
Design Accepted Head     : f358aca1ff6e056f28c3b9b2d0fcaa2f608ac124
Governance               : Acceleration v2（docs/PROJECT_GOVERNANCE_ACCELERATION.md；零 diff）
Risk Class               : C（外部可执行 artifact 信任边界；Risk C 不拆分 S1/S2/S3；U2-1..U2-12 均未触发）
S1                       : 3191ffa feat(phase5): implement P5-C2 compatibility supply
S2                       : 7a401c1 test(phase5): complete P5-C2 host compatibility
S3                       : 本提交 docs(phase5): complete P5-C2 acceptance evidence（`git log -1 --format=%H -- fc2-organizer/docs/review/P5_C2_HANDOFF.md`）
Final Implementation Head: 同 S3（线性历史；无 amend / rebase / squash / force push）
Architecture Blocker     : NONE
Authority Escalation     : NONE
Next                     : P5-C2 INDEPENDENT LEVEL 1 REVIEW（Reviewer 必须在自己的 checkout 上独立重跑 E31 与 M2-14..M2-23，不得只引用本文）
```

> 本文只记录实现与证据；不改变 Frozen Contract / Plan 的任何语义、scope、Risk 或 finding authority。
> 支持声明是**坐标级**的：version compatibility target = Amane v0.15.0 与 v0.18.0；**support claim is coordinate-scoped, not version-global**，
> 只在 SC-01..SC-04 上经验证兼容；macOS / Linux / Docker 为 UNVERIFIED。

## 1. 坐标与提交链

| 项 | 值 |
|---|---|
| P5-C1 Final Closure Docs Head | `232ece06c1d166929846bc9c63ffc7314ea3a484`（= Package Frozen Base） |
| P5-C1 adapter tree（零 diff） | `tree_sha256 = 9fe3dc3b9e815ec3768eec636db6747a68192d97112ea42e9a8545440cb40f82` == `P5_C1_HOST_WITNESS.adapter_tree_sha256` |
| 线性提交 | `f358aca` Design Accepted Head → `3191ffa` S1 → `7a401c1` S2 → S3（本提交） |
| Amane v0.15.0 | tag 对象 `3292c957a092f85ddde1ba7462ffe9813827f4f1`，peeled `45dff2159369883e028a296d775a4598836c1ddd`，`requires-python >=3.14`，`PLUGIN_API_VERSION = "1"` |
| Amane v0.18.0（当前稳定版） | tag 对象 `7d2190704fa1e3c0f7f86889111d12b9fa6701c8`，peeled `0a8a731d7746bde5e8828d1eb74c7bd9752b42e4`，GitHub Release 非 draft / 非 prerelease，`published_at = 2026-10-04T14:44:36Z`，`requires-python >=3.14`，`PLUGIN_API_VERSION = "1"` |
| current main | `0a8a731d7746bde5e8828d1eb74c7bd9752b42e4` == v0.18.0 -> SC-05 = `IDENTICAL_TO_STABLE`（不重复计作独立见证） |
| S1 / S3 时刻的漂移核对 | 两次直接核对 upstream（git tag / peeled / GitHub Releases API）：无比 v0.18.0 更新的稳定版；main 未前进；与设计期坐标完全一致，无差异需记录 |
| 排除 | `app-1.0.0` / `app-1.0.1` = Android 客户端 APK 发布线，不是插件宿主，不参与“当前稳定版” |

## 2. 支持坐标（E24；与 `COMPATIBILITY.json` / `INSTALL.zh-CN.md` / 合同第 7.2 节同一张表）

| 坐标 | Amane | 宿主形态 | 平台 | 状态 | 见证 |
|---|---|---|---|---|---|
| SC-01 | v0.15.0 | 官方 Windows x64 冻结桌面版（内置 Python 3.14.7） | Windows x64 | **SUPPORTED** | HOST-A-WIN：HC-01..HC-19 = 19/19 |
| SC-02 | v0.18.0 | 官方 Windows x64 冻结桌面版（内置 Python 3.14.7） | Windows x64 | **SUPPORTED** | HOST-B-WIN：19/19 |
| SC-03 | v0.15.0 | 源码宿主（独立 venv，Python 3.14.7） | Windows x64 | **SUPPORTED**（集成兼容） | HOST-A-SRC：19/19 |
| SC-04 | v0.18.0 | 源码宿主（独立 venv，Python 3.14.7） | Windows x64 | **SUPPORTED**（集成兼容） | HOST-B-SRC：19/19 |
| SC-05 | main（== v0.18.0） | 源码宿主 | Windows x64 | `IDENTICAL_TO_STABLE` | 不重复运行 |
| SC-06 | v0.16.1 / v0.17.0 | 源码宿主 | Windows x64 | `UNVERIFIED`（可选信息见证，未运行） | — |
| SC-07 / SC-08 / SC-09 | v0.15.0 / v0.18.0 | macOS 冻结包 / Linux 源码 / Docker | macOS / Linux | **`UNVERIFIED`**（无环境；不属于支持声明） | — |

宿主准备（`tools/prepare_amane_hosts.py`）：源码宿主 = detached worktree（peeled commit 且干净）+ 独立 3.14.7 venv（v0.15.0：70 个依赖，`pip freeze` 哈希 `9ac49de4…`；v0.18.0：71 个，`faeb4d3a…`）；
冻结包 = 官方 `Amane-v0.15.0-windows-x64.zip`（`dfd20f3b875c891a7a23260b2e9ded7cd99feba9ae933b62fa729263c9e67953`）与 `Amane-v0.18.0-windows-x64.zip`
（`e4abb5b2de93dbde9f5898b80113cb11ba7b1081849ba66fd8f8e6c93d1c9301`），下载后以 GitHub Release 元数据里的 SHA-256 摘要校验。所有验收使用临时 `AMANE_DATA_DIR` / 日志目录、`127.0.0.1`、随机空闲端口；不触碰任何用户的 Amane 数据。

## 3. 变更文件（相对 Package Frozen Base；E01 范围门由 `test_amane_compat_scope_gate.py` 机检）

```text
adapters/amane/README.md                                            （仅状态 / 入口文档）
adapters/amane/api_manifest/amane_v0.18.0_api_manifest.json
adapters/amane/release/INSTALL.zh-CN.md
adapters/amane/release/core_release_ledger.json
adapters/amane/shim/plugin.py
adapters/amane/shim/_ffcc_locator.py
tools/build_core_wheel.py
tools/build_amane_release.py
tools/compare_amane_api.py
tools/prepare_amane_hosts.py
tools/run_amane_compat_gate.py
tests/amane_compat/  conftest.py _compat_support.py _locator_harness.py
                     host_scripts/{in_host.py, loopback_fixture.py}
                     test_amane_compat_{api_matrix, artifact_dag, determinism, gate_tools, install_doc, locator, matrix_json, mutation_nonvacuity, release_layout, scope_gate}.py
docs/acceptance/evidence/P5_C2_COMPATIBILITY_MATRIX.json
docs/review/P5_C2_HANDOFF.md
docs/P5_C2_CONSTRUCTION_PLAN.md、docs/specifications/PHASE5_C2_AMANE_COMPATIBILITY_CONTRACT.md   （已被接受的设计历史；Design 阶段提交）
```

**零 diff（机检：`git diff 232ece06…..HEAD`）**：`src/**`；`adapters/amane/fc2_amane_adapter/**`（树哈希 == C1 witness）；既有 `tests/**`（含 `tests/amane_adapter/**`）；
`tools/amane_api_manifest.py`、`tools/build_amane_plugin_zip.py`、`tools/run_amane_host_witness.py`；`pyproject.toml`；P5-C1 Contract / Plan / HANDOFF / evidence；`docs/PROJECT_GOVERNANCE_ACCELERATION.md`。

## 4. E01..E31 逐项结果

| E | 结果 | 证据 |
|---|---|---|
| E01 范围 | PASS | `test_amane_compat_scope_gate.py`（allow-list / 零 diff / 控制字符 / adapter 树哈希 / 工作树） |
| E02 C1 语义不变 | PASS | `_impl/` 的 `tree_sha256`（LF 规范化字节）== `9fe3dc3b…` == witness；`tests/amane_adapter/**` 全绿（539） |
| E03 坐标 | PASS | §1；两份 manifest 的 commit / version / `PLUGIN_API_VERSION`；`test_amane_compat_api_matrix.py` |
| E04 API 矩阵 | PASS | 合同 §6.2 每个清单可见的差异均有机检断言；适配器可控子集指纹两版**相等**（`13b70ba8…`）、全量指纹不同 |
| E05 供给 / 安装 | PASS | HC-01/10/11/16/19 在 SC-01..SC-04 上通过；“文档即测试”：`test_amane_compat_install_doc.py`（INSTALL 每步 -> 见证场景，MATRIX 中四个必需宿主均 passed）；INSTALL 不含把 pip / 目录形态当作受支持来源的步骤 |
| E06 确定性 | PASS | 3.12 与 3.14 × 两个输出目录 × LF / CRLF 检出副本：wheel / plugin zip / bundle 哈希全等（8 个构建）；最终树上再次用 3.14 + 不同输出目录重建 L0..L4 逐字节相同 |
| E07 clean install | PASS | HC-01 / HC-03；`descriptor().id` 恒为 `ffcc.fc2-metadata` |
| E08 discovery | PASS | HC-02（重启后仍被发现、配置仍生效）/ HC-03 / HC-14 |
| E09 配置往返 | PASS | HC-05：24 个样本 × 四个布尔（PATCH / `validate_plugin_config` / `parse_settings` / `build_plugin_provider`）全真或全假；raw string / bool / numeric 强制转换**不再出现**（C1 L1-01）；HC-08 |
| E10 provider build | PASS | HC-04：真实 `PluginManager` + `CrawlerFactory` + 真实 `WebClient`（curl_cffi）-> 回环 fixture；成功用例与 C1 H-07 冻结映射逐字段相等 |
| E11 reload | PASS | HC-06（11 个 `amane_ext*` 模块全部重建为新对象；Core 对象未被重建）/ HC-07（哨兵版本在 reload 后可见，还原后消失） |
| E12 upgrade | PASS | HC-09（版本 +1；已加载 `_settings` 版本更新，无陈旧模块）/ HC-16 |
| E13 missing Core | PASS | HC-10：422，detail == P5-C1 §22 冻结消息；`items` 无该插件；`sources/` 无残留；`sys.path` 不变；未回退内置爬虫 |
| E14 incompatible Core | PASS | HC-11 / HC-19：tampered / wrong-version / 同名目录 / 超大 / directory-form / already-loaded-wrong / mixed-origin 全部 fail closed 且无半装 |
| E15 跨版本结果等价 | PASS | 17 个请求用例（成功 / PARTIAL / 未命中 / 10 种由传输层诱发的错误 / 非法 SearchQuery / 外来对象 / 非 FC2 类型 / 取消）的规范化结果在四个宿主对（a-src↔b-src、a-win↔b-win、a-src↔a-win、b-src↔b-win）上哈希**相等**；回环端口已从证据中规范化 |
| E16 跨版本错误等价 | PASS（见 §9 说明） | 每个由传输层可诱发的 Core 错误类别一例；`SourceErrorKind` 全部 16 个成员在宿主内映射到宿主 `FailureReason` 值；宿主 `FailureReason` 全部成员（v0.15.0：16；v0.18.0：17，多 `API_ERROR`）经桥分类为确定的三桶（timeout / network / 其它），是**全函数** |
| E17 HTTP 生命周期 | PASS | provider 持有宿主 `web_client` 的**同一对象**（`bridge._web_client is web_client` 等 3 项身份）；成功用例每来源恰好 1 次请求（L1 = S）；所有用例 per-source ≤ H=3 |
| E18 无 vendor | PASS | plugin zip 10 个成员，无 Core 文件名 / 无 Core 整文件字节；`fc2_metadata_core` 仅被 `_impl` 导入；wheel 与 zip 是两个独立文件 |
| E19 无新持久化 | PASS | locator / shim AST 守卫（无写 API、无网络、无 amane / pydantic / Core import、无 `sys.modules` 修改）；HC-18 文件系统快照 + adapter 未写任何文件 |
| E20 mutation | PASS | M2-01..M2-23 全部 KILLED（§7） |
| E21 v0.15.0 宿主集成 | PASS | SC-01 / SC-03：HC-01..HC-19 19/19 |
| E22 v0.18.0 宿主集成 | PASS | SC-02 / SC-04：HC-01..HC-19 19/19 |
| E23 current main | `IDENTICAL_TO_STABLE` | main == v0.18.0（`0a8a731d…`）；不重复计作独立见证 |
| E24 平台 / 坐标矩阵 | PASS | 3.14.x（源码宿主）/ 3.14.7（冻结包）/ 主套件 3.12.10 / Windows 11；SC-07..SC-09 = UNVERIFIED；`status` 以坐标为 key |
| E25 targeted | PASS | `tests/amane_compat` 290 个（见 §6） |
| E26 既有契约 | PASS | `tests/amane_adapter` 539、`tests/contract` 全绿 |
| E27 full suite | PASS（见 §6） | 3.12.10：失败 0；与 P5-C1 基线 8448 / 40 对账，差额 = 新增 targeted 测试数 |
| E28 skip 对账 | PASS | 40 个 skip（22 组）与基线逐条相同；新增 skip = 0 |
| E29 artifact 哈希与 DAG | PASS | §5；DAG 测试（拓扑、禁止字段、Part B 不影响 L2–L4、`sha256sum -c`、重建逐字节一致）；已提交 MATRIX 的 artifacts == 由当前树重建 |
| E30 gaps / limitations | 见 §9 | 如实列出 |
| E31 locator 信任边界 | PASS | E31-a..v：单元层 3.12 与 3.14 各 43 个用例（共 86 个子进程用例）+ 真实宿主（源码宿主 17 个宿主内 `install_plugin_zip` 用例 + 真实 `PYTHONPATH` 用例；冻结包 sidecar 各分支）；Reviewer 的 `.pyc` PoC 与**非空洞对照**（不经 locator 时 payload 会执行）；威胁模型措辞守卫 |

### E31-a..v 对应表（单元层用例名 = `_compat_support.EXPECT`）

| 子项 | 用例 | 子项 | 用例 |
|---|---|---|---|
| a | `a_loaded_exact_wheel` | l | `l1_… _cache_absent_at_entry` / `l2_… _cache_present_at_entry` |
| b / c | `b_loaded_wrong_version_wheel` / `c_loaded_tampered_same_name_wheel` | m | `m_sidecar_same_name_directory_with_directory_core` |
| d / e | `d_loaded_directory_pip_target` / `e_loaded_editable_source` | n | 每个 FAIL 用例的 `RESTORED` 断言（`sys.path` 逐元素 + 同一 list 对象 / importer-cache 条目 / Core 对象身份 / 未 import Core） |
| f | `f_unloaded_directory_{pip_target,editable,source_checkout,pythonpath_directory}_no_sidecar` | o | `o_no_core_no_sidecar` 等 3 个 |
| g | `g_directory_core_with_valid_sidecar_loads_wheel` | p | `p_success_single_insertion_and_idempotent_with_final_resolution`（第二次调用仍执行最终真实解析，计数 ≥ 2）/ `p_success_from_staging_module_file` |
| h | `h0_…control` / `h1_…no_sidecar` / `h2_…with_valid_sidecar_loads_wheel` / `h3_loaded_directory_with_benign_pyc` | q / r / t | wheel 构建内容 / 4 个模板有界无路径 / INSTALL 措辞守卫 |
| i | `i_sidecar_{tampered_one_byte, symlink, oversize, same_name_directory, only_other_version_wheel}` | u | `u_existing_wheel_but_resolution_disagrees`（惰性目录包从未被导入）+ `u_existing_wheel_first_and_resolution_matches` |
| j | `j_mixed_submodule_{other_archive, directory_origin, no_spec, namespace_package, subclass_loader}` | v | `v_subclass_loader_double_in_{final,pre}_resolution` / `v_loaded_core_with_subclass_loader_double` |
| k | `k_shadow_meta_path_finder_{with_valid_sidecar, no_sidecar}`（预解析阶段拒绝，`sys.path` 修改次数 0） | s | 以上全部在 3.12 与 3.14 上执行 |

## 5. 最终 artifact 与哈希（合同第 10.5 节冻结顺序；在最终树上生成）

```text
L0  Core wheel   fc2_metadata_core-0.1.0-py3-none-any.whl  sha256 = 0b3db80c9ab9160d9c925b0066ae9b3af72bf22cb4bf2e5278c43c9f47f4b42d  （tree = 6077cd67…da026 == C1 core_tree_sha256）
L1  plugin zip   ffcc.fc2-metadata-0.1.0.zip               sha256 = 2181a12acb9931b4f7cecd4a1ba58b8b01035916979329b3607b4082f4187766  （10 个成员；`_ffcc_pin.py` sha256 = 96a80189…d2463）
L1  INSTALL.zh-CN.md / VERSION（静态文本，不含任何哈希）
-   MATRIX Part A   在 L0 + L1 的确切字节上执行真实宿主见证（4 个必需宿主 × 19 个场景）
L2  COMPATIBILITY.json  sha256 = 9af6eae22c727bcbb110dfa18e29bdae1a0bfd027d0b6d8d680668c53b121d06
L3  SHA256SUMS          sha256 = 7900b8401e057f480b5e1ed9bb47f139565588a1a69d0a48d84867b0ec3a0c70   （5 个成员；不含自身）
L4  release bundle      ffcc-amane-release-0.1.0.zip  sha256 = 8297037faf900a2ac45635cfbd2751acff51274f8cba40782a60e4c63de1e010   （6 个成员）
L5  MATRIX Part B（final_artifacts）只记录上面三个外层哈希，不写回 bundle
P5_C2_COMPATIBILITY_MATRIX.json（Part A + Part B）文件 sha256 = b5250b730d8121654852e93fcff74a8b1d9f8819535bf198d95b75eb30473615
```

验证（`final_pipeline`，不入库的编排脚本；步骤均已执行并通过）：`pin` 中的 wheel 哈希 == 实际 wheel 哈希；bundle 解出后 `sha256sum -c SHA256SUMS` 等价检查通过；成员字节 == 被验收的 L0 / L1 字节；
在同一树上用 **Python 3.14 + 不同输出目录** 重建 L0 / L1 / L2 / L3 / L4 与上表**逐字节相同**；Part B 的取值不影响 L2–L4（E29 测试）。提交之后另在**干净检出**上再次重建并核对（见 §10）。

## 6. 测试数字（E25 / E26 / E27 / E28）

```text
基线（S1 起始；3.12.10 项目 venv，pytest 9.1.1，httpx 0.27.2）: 8448 passed / 40 skipped / 0 failed（与 P5-C1 终点相同）
targeted（tests/amane_compat）          : 290 collected（api_matrix 13 / artifact_dag 11 / determinism 14 / gate_tools 30 / install_doc 8 / locator 93 / matrix_json 32 / mutation 62 / release_layout 21 / scope_gate 6）
tests/amane_adapter                     : 539 collected
tests/amane_compat + amane_adapter      : 829 passed / 0 skipped / 0 failed（最终树；290 + 539）
python -m pytest tests -q（3.12）       : 8738 passed / 40 skipped / 0 failed（最终树；717 s）= 基线 8448 + 290 个新增 targeted 测试；`-rs` skip 清单与基线 22 组 / 40 个**逐条相同**
新增 skip                               : 0
```

**Python 3.14 回归（P5-C1 冻结的 exact 命令、显式路径、无任何筛选参数；环境 = Python 3.14.7 + Amane v0.15.0 editable + pytest 9.1.1 + httpx 0.27.2，Core 经 `PYTHONPATH=src`；实际重跑，不是引用旧报告）**

| 集合 | 结果 |
|---|---|
| A（30 个显式路径） | **1833 passed**（0 failed / 0 error / 0 skipped / 0 xfailed）—— 与 C1 终点 `collected == passed == 1833` 一致 |
| B（22 个显式文件） | **520 passed**；3.12 与 3.14 的 `collected` 均为 520；冻结 nodeid `…test_core_runtime_objects_and_one_fake_bridge_aggregate` 通过 |
| C（真实宿主见证 H-01..H-15） | 15/15 PASS；输出写到**临时路径**，与已提交的冻结 `P5_C1_HOST_WITNESS.json`（LF 规范化）**逐字节相同**（`sha256(out) = 920cec8bd9b137e2e83e8cc1807c626568b2182a77c5c8177aa62e603ff5da58`）；该冻结文件零 diff |

**skip 对账**：基线日志（`-rs`）22 组、合计 40 个 skip（符号链接权限 / POSIX 与跨卷原生证据在 Windows 上不可执行等）；最终全量日志逐组比对，nodeid / 原因 / 数量完全相同。`tests/amane_compat` 内**没有任何 skip**（包括 3.14 缺失 -> 失败而不是 skip）。

## 7. Mutation / non-vacuity（M2-01..M2-23；方法：对**临时仓库副本**打恰好一处补丁，子进程运行 killer；原树从不被修改）

工具：`python -m pytest tests/amane_compat/test_amane_compat_mutation_nonvacuity.py`（单元层，29 个变体，**全部 KILLED**；哨兵证明被测的确是被篡改的副本；每个补丁恰好命中一次，否则 mutant 空洞）。
真实宿主杀手：`python tests/amane_compat/test_amane_compat_mutation_nonvacuity.py --hosts <hosts.json> --wheel <whl> --work <dir> --label b-src`（对**被篡改的 artifact** 在真实源码宿主上执行相关阶段；M2-08 在 v0.15.0 宿主 a-src 上执行，因为该泄漏只在 v0.15.0 上有害）。

| mutant | 变体 | 单元层 killer（KILLED） | 真实宿主 killer（KILLED） |
|---|---|---|---|
| M2-01 | 错误 plugin id | E07、ZIP 布局、构建器 id 校验 | 构建期即被杀（`PLUGIN_ID must be exactly ffcc.fc2-metadata`） |
| M2-02 | descriptor 覆盖 `api_version="2"` | E02（树哈希）、C1 `test_descriptor_declares_only_the_cross_version_subset` | HC-01、HC-03 |
| M2-03 | locator 静默忽略 sidecar 失败 | E31 用例 i_tampered / k_shadow / u | HC-11 |
| M2-04 | Core 源码打进 plugin zip | E18、ZIP 布局 | —（构建期可观察） |
| M2-05 | reload 复用陈旧 Plugin 类 | shim 形状守卫 | HC-07 |
| M2-06 | 配置变更不重建 provider | E02 | HC-08 |
| M2-07 | 版本分支（读 `raw_results`） | AST 守卫（C2 + C1 `test_no_single_version_host_names…`） | —（AST） |
| M2-08 | 泄漏仅新版存在的 `max_attempts` | 同上 | HC-04（v0.15.0 宿主） |
| M2-09 | zip 含 `__pycache__` / `.pyc` | ZIP 布局 | — |
| M2-10 | 时间戳 / 条目顺序不确定（2 个变体） | ZIP 布局 | — |
| M2-11 | 升级后旧模块残留 | shim 形状守卫 | HC-09 |
| M2-12 | Pydantic 接受而 runtime parser 拒绝 | E02 | HC-05 |
| M2-13 | 引入自带 HTTP 库 / 绕过宿主 HTTP | E02、C1 架构守卫 | HC-04、HC-17 |
| M2-14 | 不校验 sha256 / 接受符号链接 / 接受任意文件名（3 个变体） | E31 i_tampered + c_loaded_tampered / i_symlink / b_loaded_wrong_version | HC-11 |
| M2-15 | pin 变化仍放行旧 Core | E31 b / c | HC-16 |
| M2-16 | UNVERIFIED 写成 SUPPORTED | matrix_json 自洽规则 | — |
| M2-17 | 已加载 Core 盲信 | E31 b / c / d / e / j | HC-19 |
| M2-18 | 接受任何目录形态 | E31 f×2 / h1 | HC-19 |
| M2-19 | 无最终真实解析 / 无同根检查（2 个变体） | E31 k / l1 / u / v；j×3 | HC-19 |
| M2-20 | 不回滚 `sys.path` / purge `fc2_metadata_core*` / 不恢复 importer-cache（3 个变体） | E31 l1 / l2；b / d + AST；l1 | HC-19 |
| M2-21 | 目录形态含恶意 `.pyc`（`*.py` 哈希接受） | E31-h1 / f_editable | HC-19 |
| M2-22 | artifact 派生环（COMPATIBILITY.json 内嵌 SHA256SUMS 哈希字段） | E29 DAG 测试 | — |
| M2-23 | existing-wheel 分支不做最终真实解析就返回成功 | **E31-u** + E31-p + AST | HC-19（E31-u） |

真实宿主杀手的原始输出（节选；全部 `"KILLED": true`）：

```text
{"mutant": "M2-02-api", "failed_scenarios": ["HC-01","HC-02","HC-03","HC-06","HC-07","HC-08","HC-09","HC-13","HC-14","HC-15"], "killed_by": ["HC-01","HC-03"]}
{"mutant": "M2-03-silent", "failed_scenarios": ["HC-11"]}        {"mutant": "M2-05-stale", "failed_scenarios": ["HC-07","HC-09","HC-13"]}
{"mutant": "M2-06-no-rebuild", "failed_scenarios": ["HC-08"]}     {"mutant": "M2-11-stale-upgrade", "failed_scenarios": ["HC-07","HC-09","HC-13"]}
{"mutant": "M2-12-pydantic-vs-parser", "failed_scenarios": ["HC-05"]}   {"mutant": "M2-13-own-http", "failed_scenarios": ["HC-04","HC-17"]}
{"mutant": "M2-14-hash-skip", "failed_scenarios": ["HC-11"]}       {"mutant": "M2-15-pin-change-accepted", "failed_scenarios": ["HC-16"]}
{"mutant": "M2-17/18/19/20/21/23 (admission)", "failed_scenarios": ["HC-19"]}   {"mutant": "M2-08-newer-api (a-src, v0.15.0)", "failed_scenarios": ["HC-04","HC-08","HC-17"]}
```

两次真实宿主运行中，M2-08（在 v0.18.0 宿主上不会失败，设计上正确）与 M2-15（pin-B zip 起初由未篡改的树构建，没有带上被篡改的 locator）**首次“存活”**：均为杀手执行条件的缺陷，不是产品缺陷；已分别改为在 v0.15.0 宿主上执行 / 让 `Artifacts.pin_b` 使用被篡改的仓库副本，之后均 KILLED。
单元层另有一个“存活”被发现并修复：`M2-14-accept-symlink` 因 `lstat` 替身返回虚假大小而被偶然拒绝；已改为只改写 `st_mode`，之后 KILLED（非空洞）。

## 8. 真实宿主见证 HC-01..HC-19（`docs/acceptance/evidence/P5_C2_COMPATIBILITY_MATRIX.json`）

四个必需宿主（HOST-A-SRC / HOST-B-SRC / HOST-A-WIN / HOST-B-WIN）**各 19/19**；Part A 在两次完整运行之间**逐字节相同**（最终树上再次生成）。

方法要点：
* 启动**真实 Amane 服务进程**（`python -m amane.server` / `Amane.Server.exe`），经**真实 HTTP API** 操作（`/api/plugins`、上传、reload、PATCH、DELETE、`/api/config`）；不 mock `PluginManager / install_plugin_zip / purge / CrawlerFactory`。
* 宿主进程内观测使用**临时探针插件**（只存在于临时数据目录，不属于任何发布物；W2-04 / W2-05 同法）：它在 `discover()` 时执行 `tests/amane_compat/host_scripts/in_host.py` 并经宿主自己的 `failures` 通道回传 JSON；因此**冻结桌面宿主与源码宿主走同一代码路径**。
* HC-04 / HC-05 / HC-08 / HC-17 与 E15 / E16 在宿主进程内构建**受控宿主栈**（真实 `install_plugin_zip` -> `PluginManager.discover` -> `CrawlerFactory` + 真实 `WebClient` -> `127.0.0.1` 回环 fixture；宿主退避的 `asyncio.sleep` 以模块局部代理跳过，同 C1）。HC-08 在**同一个 `PluginManager`**（模块常驻）上用新的 `CrawlerFactory` 重建 provider，与宿主 PATCH 后的 `apply_rebuild` 同法，因此“模块级缓存”类 mutant 会被杀死。
* HC-19：所有宿主 = sidecar 各分支（HTTP）；源码宿主另在宿主进程内用真实 `install_plugin_zip` 执行 17 个 E31 用例，并以真实 `PYTHONPATH` 启动宿主执行 `.pyc` PoC 两个用例。冻结包无法在宿主进程里布置 `sys.path` 夹具 -> 只覆盖 sidecar 各分支，E31-u / E31-v 由源码宿主 + 单元层覆盖（合同第 11.2 节原文）。
* `core_admission` 共 66 行（每个 FAIL 行：`sys.path` 与入口相同、`fc2_metadata_core*` 对象身份不变、`payload_executed = false`）。

### 8.1 观测到的宿主事实（如实记录；均不改变合同语义）

1. `POST /api/plugins` 成功返回 **201 Created**（两个版本相同）；合同表中的“200”按宿主实际语义判定为 201。
2. **非 zip 上传返回 HTTP 500**（宿主路由只捕获 `ValueError / TypeError / OSError`，`zipfile.BadZipFile` 未被捕获；两个版本相同；无残留）。合同 HC-12 期望 422；该变体的判据放宽为“被拒绝且无半装”，其余 4 个畸形变体均为 422。这是宿主缺陷，与本插件无关，不为迁就而伪造。
3. HC-13：错误 id 的 zip 被宿主以 `descriptor().id` 为目录名提交（`other.id`），`/api/plugins` 同时列出 `ffcc.fc2-metadata` 与 `other.id`，内容路由 / 配置不引用它；两个版本相同。
4. `CrawlerFactory` 为 `PluginContext.data_dir` **创建** `plugins/<id>/`（宿主行为，v0.15.0 `factory.py:107` / v0.18.0 `:131`）；adapter 从不使用 `data_dir`；HC-18 断言这些运行期目录内**没有任何文件**。
5. 宿主 `reload` 先 `purge_imported_plugin_modules()`（清空 `sys.path_importer_cache`）；Core 常驻（`fc2_metadata_core` 对象在 reload 前后相同）。
6. 本账户无创建符号链接的权限：HC-11 的 symlink 变体在宿主层记为 `executed = false`；**单元层**用 `os.lstat` 替身执行（E31-i，不得 skip；替身只改 `st_mode`，其余字段保持真实）。
7. 源码宿主启动需要去掉继承的 `FORCE_COLOR`（structlog 在 Windows 上要求 colorama）；网关对宿主环境做了清理（不继承任何 `AMANE_*` / `PYTHONPATH` / `FORCE_COLOR`）。

## 9. 偏差与实现裁决记录（均在 Frozen Contract 之内；合同 / 计划未被修改）与 Evidence Gaps

偏差 / 裁决：
1. **`prefix == ""` 只对顶层 `fc2_metadata_core` 的 spec 要求**：zipimport 为包内子模块使用 `prefix = "fc2_metadata_core/"` 的 importer；对子模块也要求 `""` 会让合法的 exact pinned wheel 在已加载分支被误拒绝（E31-a 暴露）。其余判据（精确 `zipimporter` 类型、archive 同根、origin 在归档内）对所有 `fc2_metadata_core*` 模块照常要求。
2. 单元层 locator 用例在 `python -S` 子进程里运行并清理环境（`PYTHONPATH` 等）：项目 venv 里存在 editable 的 Core（`.pth`），会被 locator **正确地**当作目录形态拒绝，从而干扰“无 Core”用例。
3. `tests/amane_compat/host_scripts/in_host.py` 用 `importlib.import_module` 取宿主对象，而不是 import 语句：P5-C1 的测试树守卫（CLOSED 测试，不得修改）禁止 `tests/` 下（C1 自己的 host_scripts 除外）出现 amane 的 import 语句。pytest 从不导入该目录。
4. 宿主内 HC-08 不是“调用宿主自己的 factory”：没有任何 HTTP 路由能在没有媒体库的情况下触发一次 fetch（真实 scrape 任务端到端属 Phase 6，L-C2-10）；因此行为 oracle 在受控栈里观察，PATCH / 浅合并 / 持久化则在真实服务进程上观察。
5. 真实宿主 mutation 的杀手执行细节见 §7（两次首次“存活”均为杀手条件缺陷，已修正并记录）。

Evidence Gaps（如实）：
* **E16**：`SourceErrorKind` 中无法由传输层诱发的成员（`ADAPTER_EXCEPTION`、`RESULT_CONTRACT_MISMATCH`、`CIRCUIT_OPEN`、`NOT_FOUND`、`NETWORK_ERROR`、`DECODE_ERROR` 的纯 decode 路径）没有“端到端一例”；它们由宿主内的**映射全函数枚举**（16/16 成员）与 P5-C1 的单元 / 契约测试覆盖。`kind_decode_error_bad_charset` 实际落入 `parse_error` 桶（宿主 / Core 对未知 charset 的容错解码），结果在四个宿主上相同。
* **L-C2-02 / SC-06**：v0.16.1 / v0.17.0 未运行（可选信息见证）。
* **macOS / Linux / Docker**：UNVERIFIED（SC-07..SC-09；无环境；不为扩大声明增加环境依赖）。
* **L-C2-13（ACCEPTED SECURITY LIMITATION）**：校验只保证准入时刻的完整性；运行期间对 wheel 的持续写入者不被防御；已加载 Core 的证明是 current-origin + current-artifact proof，不是历史已执行字节证明；INSTALL 要求“运行期间不要替换或删除 sidecar wheel”。
* L-C2-03（桌面用户忘记 sidecar 时看到 P5-C1 冻结消息）、L-C2-05（Core 升级需重启）、L-C2-07（PATCH 浅合并）、L-C2-09、L-C2-10（真实站点冒烟 / 批量任务属 Phase 6）、L-C2-12（“选择服务器路径”安装到数据目录之外时找不到 sidecar）按合同如实保留；C1 L-01..L-15 继续成立。
* 宿主依赖安装（`pip install` 的联网）与官方冻结包下载属环境前提；网关 / 受控栈对站点的所有请求都只到 `127.0.0.1`。

## 10. 状态与下一步

```text
git diff --check          : CLEAN
git status                : CLEAN（提交后）
Frozen scopes             : ZERO DIFF（src/**、C1 adapter 树、既有 tests/**、C1 工具、pyproject.toml、C1 文档 / evidence、治理文档）
Risk Class                : C（未升级；U2-1..U2-12 未触发）
P5-C2                     : IMPLEMENTATION COMPLETE —— NOT YET CLOSED
Next                      : P5-C2 INDEPENDENT LEVEL 1 REVIEW（C 级；必须独立执行 E31 与 M2-14..M2-23；不得只引用本文）
```

Reviewer 复核命令（均在自己的 checkout 上）：

```powershell
python -m pytest tests/amane_compat tests/amane_adapter -q -p no:cacheprovider                  # targeted（3.12）
python -m pytest tests -q -p no:cacheprovider                                                   # full（3.12）
python tools\build_core_wheel.py --out <d>/l0 ; python tools\build_amane_release.py stage1 --core-wheel <whl> --out <d>/l1
python tools\run_amane_compat_gate.py run --hosts-json <hosts.json> --core-wheel <whl> --stage1-dir <d>/l1 --work <临时目录> --out <MATRIX.json>
python tools\prepare_amane_hosts.py --work <dir> --python <py3.14> --amane-repo <clone> --tags v0.15.0 v0.18.0 --out <hosts.json>
```

不要开始 Phase 6。
