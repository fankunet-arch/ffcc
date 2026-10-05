# P5-C2 HANDOFF —— Amane Compatibility & Adapter Closure（Pre-L1 证据对账完成；等待独立 Level 1 Review）

```text
P5-C2 PRE-L1 EVIDENCE RECONCILIATION : COMPLETE
Technical Acceptance                  : NOT YET
P5-C2                                 : NOT CLOSED（本文不是 Level 1 结论，也不是 Technical Acceptance）
Branch                                : claude/phase5-c2-amane-compatibility
Package Frozen Base                   : 232ece06c1d166929846bc9c63ffc7314ea3a484
Original Design Accepted Authority    : f358aca1ff6e056f28c3b9b2d0fcaa2f608ac124
Accepted Pre-L1 Amendment A1          : b8480e74ab2b8d7901a0de98ee396f72e204aba7（独立 Authority Amendment Review：PASS）
Current Accepted Authority Head       : b8480e74ab2b8d7901a0de98ee396f72e204aba7
Previous Implementation Candidate     : 4358b3df3353d634e4c2e8b1ee6b71c0a07b5ace
Governance                            : Acceleration v2（docs/PROJECT_GOVERNANCE_ACCELERATION.md；零 diff）
Risk Class                            : C（外部可执行 artifact 信任边界；不拆分 S1 / S2 / S3；未升级）
U2-5                                  : TRIGGERED（S2 / S3 期间，在送 Level 1 之前发现：冻结设计对宿主 API / 路由 / 环境的 3 项事实假设与观测不符，以及 E16 的证据模型缺陷）
Authority debt                        : RESOLVED by Accepted A1（b8480e74…）；独立 A1 Review：PASS
Architecture Blocker                  : NONE
Next                                  : P5-C2 INDEPENDENT LEVEL 1 REVIEW（Reviewer 必须在自己的 checkout 上独立重跑 E31、M2-14..M2-23 与 E16-B，不得只引用本文）
```

> 本文只记录实现与证据；不改变 Frozen Contract / Plan / Accepted A1 的任何语义、scope、Risk 或 finding authority。
> 支持声明是**坐标级**的：version compatibility target = Amane v0.15.0 与 v0.18.0；**support claim is coordinate-scoped, not version-global**，
> 只在 SC-01..SC-04 上经验证兼容；macOS / Linux / Docker 为 UNVERIFIED。
> 治理历史如实保留：**U2-5 确实被触发过**（见 §0）；本轮没有把它改写成“从未发生”。

## 0. Pre-L1 对账（本轮；evidence-only）

**U2-5 与 A1**：S2 / S3 阶段发现下列事实与冻结设计不符，已在送 Level 1 之前上报并由 Authority Amendment A1 冻结（合同第 11.7、13.2 节；计划附录 E），独立 Review 结论 PASS：

| A1 项 | 冻结的事实 / 方法 | 本轮的对账结果 |
|---|---|---|
| A1-1 | `POST /api/plugins` 成功 = **精确 201 Created**（accepted authority fact；reload 200、PATCH 200、DELETE 204 不变；不泛化为 2xx） | **R-1 PASS**：HC-01 / 09 / 13 / 14 / 16 / 19 的 PASS 分支全部以 201 判定；网关里不再有 `200 <= status < 300` 这类区间判据（PATCH 也改为精确 200），一条机检测试逐处核对 `host.upload` 的状态码只与 201 / 422 / 12a 的冻结值比较；`INSTALL.zh-CN.md` 不含状态码，零 diff |
| A1-2 | HC-12 拆为 12a..12e：**12a** = `.zip` 文件名 + 非 ZIP 字节 -> **宿主实测 HTTP 500**（pinned v0.15.0 / v0.18.0 路由未捕获 `zipfile.BadZipFile`；已知宿主路由缺陷）+ 拒绝 + 无残留 + 无注册 + 插件代码从未执行 + 两版相同；**12b..12e** = 422 + 无残留 | **R-2 PASS**：四个必需宿主上逐变体记录状态码 / `rejected` / `sources_entries` / `registered_plugins` / `plugin_code_executed`（探针确认没有任何 `amane_ext_ffcc_d_fc2_h_metadata*` 模块被导入）；12a = 500，12b..e = 422，不再有“12a 允许 (422, 500)”的集合判据，500 没有被泛化为其它安装失败的允许值；四宿主的变体状态进入跨宿主 parity 载荷（逐字节相等） |
| A1-3 | 符号链接：locator 语义不变；真实宿主子项在无权限环境记为 `ENVIRONMENTALLY_UNAVAILABLE` + 替代证据；**替代证据的充分性已由 A1 Reviewer 裁定为 SUFFICIENT** | **R-3：真实宿主子项 = `ENVIRONMENTALLY_UNAVAILABLE`，`symlink_privilege=false`**（本账户为非管理员 Windows，`os.symlink` 失败，Win32 错误 1314；不改变系统安全设置）。**这不是“真实宿主已执行 PASS”**，也不是 skip。替代证据（已核对，均为现有测试）：E31-i 单元用例在 Python 3.12 与 3.14 上 PASS；`os.lstat` 替身**只**改写 `st_mode`（大小 / 时间戳保持真实）；M2-14 “接受符号链接”变体被 KILLED。MATRIX 校验器只在符号链接子项且 `symlink_privilege=false` 时接受该值，其它任何子项出现 = FAIL |
| A1-4 | E16 双轨：E16-A（传输可诱发 kind 端到端；记录实际观测 kind）+ E16-B（**全部 16 个** `SourceErrorKind` 成员，在**每个必需宿主进程内**经**生产** `map_aggregation` 与**生产** provider 转换，四宿主哈希相等） | **R-4 PASS**：见 §4（E16） |

### 0.1 场景完成语义（对账后追加）：阶段中断 -> 场景保持 false -> 不能 SUPPORTED -> validator 拒绝 -> finalize 拒绝

对账期间暴露一个网关缺陷：`Scenario` 以“没有失败记录”为 PASS。阶段在中途被中断时，尚未执行的检查没有任何失败记录，该场景仍被记为 PASS（`b-win` 的一次宿主瞬时无响应就留下了这样的“绿色”场景，只有 HC-18 间接失败）。现在：

* **场景初始不是 PASS**：`Scenario.passed = completed and 没有失败记录`；`completed` 只由 `complete_scenarios` 在**完整运行末尾**设置，条件是该场景依赖的**所有阶段**（`SCENARIO_PHASES`：failures / success / own_stack / core_upgrade / admission）都**正常返回**。阶段异常 -> 依赖它的场景保持 false；从未创建的场景在 Part A 里是 `passed = false`。
* 阶段内部的提前 `return` 一律改为 `raise`（中断不能伪装成正常结束；AST 守卫禁止 `phase_*` 函数出现提前 `return`）；`Scenario.complete()` 只允许被 `complete_scenarios` 调用（AST 守卫）。
* 因此该坐标不可能是 `SUPPORTED`（`derive_status` -> `BLOCKED`）；声称 `SUPPORTED` 的 MATRIX 被 `validate_matrix` 拒绝。
* **finalize 拒绝**：网关新增 `run_amane_compat_gate.py finalize`（`finalize_problems`）：Part A 必须自洽，并且四个必需宿主各有 HC-01..HC-19 **全部 passed**、四个必需坐标均为 SUPPORTED / CONDITIONALLY_SUPPORTED、全部 parity 对相等、`artifacts` 等于由当前树重建的 L0 / L1；否则**拒绝且不写任何产物**。通过后才生成 L2 -> L3 -> L4 -> Part B（本轮最终产物即由它生成）。
* 证据：18 个新 guard（场景初始 false、逐个阶段中断、host_row、validator、`finalize_problems`、`finalize` 命令对中断 / 缺失场景的拒绝并且不写文件、正向路径）；**真实宿主证明**：在一次性临时检出里，`a-win` 的控制栈阶段中断（该次恰好是同一个 Windows `WinError 5` 瞬时错误自然触发的）-> `HC-04 / 05 / 08 / 17 / 18` 为 false，其中 `HC-08` **没有任何失败记录**（正是旧缺陷会误判为 PASS 的情形）-> `SC-01` = `BLOCKED` -> `finalize` 拒绝，退出码 1，没有写出任何文件。
* 这一改动**没有改变任何真实宿主观测**：重新生成后的 Part A 与上一次相比只有 `tool.sha256` 不同，L2 / L3 / L4 逐字节相同。

**本轮改了什么 / 没改什么**

* 只修改被授权的证据面：`tools/run_amane_compat_gate.py`、`tests/amane_compat/**`（只为 evidence schema / witness / 校验器）、`P5_C2_COMPATIBILITY_MATRIX.json`、本文。
* **零 diff**：`src/**`、`adapters/amane/**`（adapter、shim、INSTALL、ledger、manifest）、`build_core_wheel.py`、`build_amane_release.py`、`compare_amane_api.py`、`prepare_amane_hosts.py`、`pyproject.toml`、P5-C1 全部文件 / evidence、P5-C2 合同与施工计划、治理文档（范围门测试 `b8480e74..HEAD` 机检）。
* **L0 Core wheel 与 L1 plugin zip 的输入字节未变**：两个哈希与被验收候选 `4358b3d` 完全相同（§5）。

## 1. 坐标与提交链

| 项 | 值 |
|---|---|
| P5-C1 Final Closure Docs Head | `232ece06c1d166929846bc9c63ffc7314ea3a484`（= Package Frozen Base） |
| P5-C1 adapter tree（零 diff） | `tree_sha256 = 9fe3dc3b9e815ec3768eec636db6747a68192d97112ea42e9a8545440cb40f82` == `P5_C1_HOST_WITNESS.adapter_tree_sha256` |
| 线性提交 | `f358aca` Design Accepted Head → `3191ffa` S1 → `7a401c1` S2 → `b518363` S3 → `4358b3d` 被验收的 Implementation Candidate → `b8480e7` Accepted Amendment A1（docs-only）→ `9550788` 对账（网关 / 测试）→ `12bd5b8` 网关在任何阶段异常时判失败 → `1dcdd02` 场景“完成才 PASS”+ finalize 拒绝不完整证据 → 分支 HEAD（MATRIX 与本文的 evidence 刷新；之后若有仅追加 §5.1 的 docs-only 提交，只改本文） |
| Amane v0.15.0 | tag 对象 `3292c957a092f85ddde1ba7462ffe9813827f4f1`，peeled `45dff2159369883e028a296d775a4598836c1ddd`，`requires-python >=3.14`，`PLUGIN_API_VERSION = "1"` |
| Amane v0.18.0（当前稳定版） | tag 对象 `7d2190704fa1e3c0f7f86889111d12b9fa6701c8`，peeled `0a8a731d7746bde5e8828d1eb74c7bd9752b42e4`，GitHub Release 非 draft / 非 prerelease，`published_at = 2026-10-04T14:44:36Z`，`requires-python >=3.14`，`PLUGIN_API_VERSION = "1"` |
| current main | `0a8a731d7746bde5e8828d1eb74c7bd9752b42e4` == v0.18.0 -> SC-05 = `IDENTICAL_TO_STABLE`（不重复计作独立见证） |
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

> “SUPPORTED”的含义：HC-01..HC-19 在该坐标上**已执行的子项**全部通过且跨版本 parity 成立；符号链接的真实宿主子项按 A1-3 记为 `ENVIRONMENTALLY_UNAVAILABLE`（见 §0），HC-11 / HC-19 的 `passed` 只对已执行子项计算，替代证据见 §0。

宿主准备（`tools/prepare_amane_hosts.py`）：源码宿主 = detached worktree（peeled commit 且干净）+ 独立 3.14.7 venv（v0.15.0：70 个依赖，`pip freeze` 哈希 `9ac49de4…`；v0.18.0：71 个，`faeb4d3a…`）；
冻结包 = 官方 `Amane-v0.15.0-windows-x64.zip`（`dfd20f3b875c891a7a23260b2e9ded7cd99feba9ae933b62fa729263c9e67953`）与 `Amane-v0.18.0-windows-x64.zip`
（`e4abb5b2de93dbde9f5898b80113cb11ba7b1081849ba66fd8f8e6c93d1c9301`），下载后以 GitHub Release 元数据里的 SHA-256 摘要校验。所有验收使用临时 `AMANE_DATA_DIR` / 日志目录、`127.0.0.1`、随机空闲端口；不触碰任何用户的 Amane 数据。

## 3. 变更文件

相对 Package Frozen Base 的累计清单（E01 范围门由 `test_amane_compat_scope_gate.py` 机检）：

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
                     test_amane_compat_{api_matrix, artifact_dag, determinism, evidence_reconciliation, gate_tools, install_doc, locator, matrix_json, mutation_nonvacuity, release_layout, scope_gate}.py
docs/acceptance/evidence/P5_C2_COMPATIBILITY_MATRIX.json
docs/review/P5_C2_HANDOFF.md
docs/P5_C2_CONSTRUCTION_PLAN.md、docs/specifications/PHASE5_C2_AMANE_COMPATIBILITY_CONTRACT.md   （已被接受的设计 / Amendment 历史）
```

**本轮对账（`b8480e74..HEAD`）实际改动的文件，且仅这些**：

```text
tools/run_amane_compat_gate.py
tests/amane_compat/_compat_support.py                         （合成 MATRIX：加入 parity.e16 与符号链接行）
tests/amane_compat/host_scripts/in_host.py                    （E16-A 用例改名；新增 op_e16b；删除只调用叶子函数的枚举）
tests/amane_compat/test_amane_compat_gate_tools.py            （HC-12 / 用例名 / parity 载荷）
tests/amane_compat/test_amane_compat_matrix_json.py           （校验器的新拒绝规则 + 已提交 MATRIX 的新断言）
tests/amane_compat/test_amane_compat_evidence_reconciliation.py（新增；证据 guard 与范围门）
docs/acceptance/evidence/P5_C2_COMPATIBILITY_MATRIX.json
docs/review/P5_C2_HANDOFF.md
```

**零 diff（机检：`git diff 232ece06…..HEAD` 与 `git diff b8480e74..HEAD`）**：`src/**`；`adapters/amane/fc2_amane_adapter/**`（树哈希 == C1 witness）；既有 `tests/**`（含 `tests/amane_adapter/**`）；
`tools/amane_api_manifest.py`、`tools/build_amane_plugin_zip.py`、`tools/run_amane_host_witness.py`；`pyproject.toml`；P5-C1 Contract / Plan / HANDOFF / evidence；`docs/PROJECT_GOVERNANCE_ACCELERATION.md`。

## 4. E01..E31 逐项结果

| E | 结果 | 证据 |
|---|---|---|
| E01 范围 | PASS | `test_amane_compat_scope_gate.py`（allow-list / 零 diff / 控制字符 / adapter 树哈希 / 工作树）+ `test_amane_compat_evidence_reconciliation.py`（`b8480e74..HEAD` 只含被授权的证据面；产品 / 构建器 / 权威 / 治理文件零 diff） |
| E02 C1 语义不变 | PASS | `_impl/` 的 `tree_sha256`（LF 规范化字节）== `9fe3dc3b…` == witness；`tests/amane_adapter/**` 全绿（539） |
| E03 坐标 | PASS | §1；两份 manifest 的 commit / version / `PLUGIN_API_VERSION`；`test_amane_compat_api_matrix.py` |
| E04 API 矩阵 | PASS | 合同 §6.2 每个清单可见的差异均有机检断言；适配器可控子集指纹两版**相等**（`13b70ba8…`）、全量指纹不同 |
| E05 供给 / 安装 | PASS | HC-01/10/11/16/19 在 SC-01..SC-04 上通过（成功 = 201）；“文档即测试”：`test_amane_compat_install_doc.py`；INSTALL 不含把 pip / 目录形态当作受支持来源的步骤 |
| E06 确定性 | PASS | 3.12 与 3.14 × 两个输出目录 × LF / CRLF 检出副本：wheel / plugin zip / bundle 哈希全等；最终树上再次重建 L0..L4 逐字节相同 |
| E07 clean install | PASS | HC-01（201）/ HC-03；`descriptor().id` 恒为 `ffcc.fc2-metadata` |
| E08 discovery | PASS | HC-02 / HC-03 / HC-14 |
| E09 配置往返 | PASS | HC-05：24 个样本 × 四个布尔（PATCH 精确 200 / `validate_plugin_config` / `parse_settings` / `build_plugin_provider`）全真或全假；HC-08 |
| E10 provider build | PASS | HC-04：真实 `PluginManager` + `CrawlerFactory` + 真实 `WebClient`（curl_cffi）-> 回环 fixture；成功用例与 C1 H-07 冻结映射逐字段相等 |
| E11 reload | PASS | HC-06 / HC-07 |
| E12 upgrade | PASS | HC-09 / HC-16 |
| E13 missing Core | PASS | HC-10：422，detail == P5-C1 §22 冻结消息；无残留；`sys.path` 不变 |
| E14 incompatible Core | PASS（符号链接真实宿主子项除外，见 §0） | HC-11 / HC-19：tampered / wrong-version / 同名目录 / 超大 / directory-form / already-loaded-wrong / mixed-origin 全部 fail closed 且无半装；符号链接子项：`ENVIRONMENTALLY_UNAVAILABLE` + 经 A1 Reviewer 裁定充分的替代证据 |
| E15 跨版本结果等价 | PASS | 17 个请求用例的规范化结果在四个宿主对（a-src↔b-src、a-win↔b-win、a-src↔a-win、b-src↔b-win）上哈希**相等**；回环端口已从证据中规范化；parity 载荷现在还包含 E16-A / E16-B 与 HC-12 变体状态 |
| E16 跨版本错误等价 | PASS（双轨；A1-4） | **E16-A**：用例名只描述刺激（`stimulus_*`），逐用例记录 `actual_source_error_kind`；端到端**实际观测到 7 个 kind**：`blocked`、`connection_error`、`http_server_error`、`invalid_response`、`parse_error`、`rate_limited`、`source_deadline`；其余 9 个（`adapter_exception`、`circuit_open`、`decode_error`、`network_error`、`not_found`、`redirect_error`、`response_too_large`、`result_contract_mismatch`、`timeout`）**未被端到端观测到**（观测，不是“不可诱发”的证明）。三个旧标签已被纠正：`kind_decode_error_bad_charset` -> `stimulus_unknown_charset`（实际 `invalid_response` + `parse_error`）、`kind_redirect_error_loop` -> `stimulus_redirect_loop`（实际 `connection_error`）、`kind_response_too_large` -> `stimulus_oversize_body_3mib`（实际 `invalid_response` + `parse_error`）；另有 `kind_timeout_source_deadline`、`kind_cloudflare_challenge_403` 等标签一并改为刺激名（实际分别为 `source_deadline`、`blocked`）。<br>**E16-B**：**全部 16 个** `SourceErrorKind` 成员，在 SC-01..SC-04 的**每个宿主进程内**：用 Core 公共构造器（`SourceResult` / `AggregationResult`）构造输入 -> **生产** `AdapterRuntime.lookup_with_cause` -> **生产** `map_aggregation`（计数包装器证明每个 kind 都实际经过它，且输入就是该 Core 对象）-> **生产** `_Fc2MetadataProvider.fetch` 转换为宿主 `SourceError(FailureReason(...), detail=...)`；唯一被替代的是上游引擎的执行（惰性桩只返回预置的 `AggregationResult`）。`NOT_FOUND` -> 中立 `AdapterNoMatch("all_not_found")` -> 宿主 `None`（category `None`，`failure_reason = null`），不是 `SourceError`。期望值是对 P5-C1 表 G / 合同 17.3 的独立转录（并由测试与生产表交叉核对）；`detail` 全文逐 kind 校验。四宿主的规范化结果哈希全部等于 `9c36bf27…`。<br>保持不变：宿主 `FailureReason` **全部成员**（v0.15.0：16；v0.18.0：17，多 `API_ERROR`）经桥分类为确定的三桶，是**全函数**。旧的 `op_enumerations` 只调用叶子函数 `reason_for_kind`，不满足 E16-B，已删除该部分 |
| E17 HTTP 生命周期 | PASS | provider 持有宿主 `web_client` 的**同一对象**；成功用例每来源恰好 1 次请求（L1 = S）；所有用例 per-source ≤ H=3 |
| E18 无 vendor | PASS | plugin zip 10 个成员，无 Core 文件名 / 无 Core 整文件字节 |
| E19 无新持久化 | PASS | locator / shim AST 守卫；HC-18 文件系统快照 + adapter 未写任何文件 |
| E20 mutation | PASS | M2-01..M2-23 全部 KILLED（§7；本轮重跑 `tests/amane_compat` 内的原 mutation suite） |
| E21 v0.15.0 宿主集成 | PASS | SC-01 / SC-03：HC-01..HC-19 19/19 |
| E22 v0.18.0 宿主集成 | PASS | SC-02 / SC-04：HC-01..HC-19 19/19 |
| E23 current main | `IDENTICAL_TO_STABLE` | main == v0.18.0（`0a8a731d…`）；不重复计作独立见证 |
| E24 平台 / 坐标矩阵 | PASS | 3.14.x（源码宿主）/ 3.14.7（冻结包）/ 主套件 3.12.10 / Windows 11；SC-07..SC-09 = UNVERIFIED；`status` 以坐标为 key |
| E25 targeted | PASS | `tests/amane_compat`（见 §6） |
| E26 既有契约 | PASS | `tests/amane_adapter` 539、`tests/contract` 全绿 |
| E27 full suite | PASS（见 §6） | 3.12.10：失败 0 |
| E28 skip 对账 | PASS | 与基线逐条相同；新增 skip = 0 |
| E29 artifact 哈希与 DAG | PASS | §5；DAG 测试；已提交 MATRIX 的 artifacts == 由当前树重建；L0 / L1 与被验收候选相同 |
| E30 gaps / limitations | 见 §9 | 如实列出 |
| E31 locator 信任边界 | PASS（符号链接真实宿主子项除外，见 §0） | E31-a..v：单元层 3.12 与 3.14 各 43 个用例（共 86 个子进程用例）+ 真实宿主（源码宿主 17 个宿主内 `install_plugin_zip` 用例 + 真实 `PYTHONPATH` 用例；冻结包 sidecar 各分支）；Reviewer 的 `.pyc` PoC 与非空洞对照；本轮 locator / admission 语义零改动，结果与上一版一致 |

### E31-a..v 对应表（单元层用例名 = `_compat_support.EXPECT`）

| 子项 | 用例 | 子项 | 用例 |
|---|---|---|---|
| a | `a_loaded_exact_wheel` | l | `l1_… _cache_absent_at_entry` / `l2_… _cache_present_at_entry` |
| b / c | `b_loaded_wrong_version_wheel` / `c_loaded_tampered_same_name_wheel` | m | `m_sidecar_same_name_directory_with_directory_core` |
| d / e | `d_loaded_directory_pip_target` / `e_loaded_editable_source` | n | 每个 FAIL 用例的 `RESTORED` 断言 |
| f | `f_unloaded_directory_{pip_target,editable,source_checkout,pythonpath_directory}_no_sidecar` | o | `o_no_core_no_sidecar` 等 3 个 |
| g | `g_directory_core_with_valid_sidecar_loads_wheel` | p | `p_success_single_insertion_and_idempotent_with_final_resolution` / `p_success_from_staging_module_file` |
| h | `h0_…control` / `h1_…no_sidecar` / `h2_…with_valid_sidecar_loads_wheel` / `h3_loaded_directory_with_benign_pyc` | q / r / t | wheel 构建内容 / 4 个模板有界无路径 / INSTALL 措辞守卫 |
| i | `i_sidecar_{tampered_one_byte, symlink, oversize, same_name_directory, only_other_version_wheel}`（**`i_sidecar_symlink` = 符号链接子项的单元层替身；3.12 与 3.14 均 PASS**） | u | `u_existing_wheel_but_resolution_disagrees` + `u_existing_wheel_first_and_resolution_matches` |
| j | `j_mixed_submodule_{other_archive, directory_origin, no_spec, namespace_package, subclass_loader}` | v | `v_subclass_loader_double_in_{final,pre}_resolution` / `v_loaded_core_with_subclass_loader_double` |
| k | `k_shadow_meta_path_finder_{with_valid_sidecar, no_sidecar}` | s | 以上全部在 3.12 与 3.14 上执行 |

## 5. 最终 artifact 与哈希（合同第 10.5 节冻结顺序；在最终树上重新生成）

```text
L0  Core wheel   fc2_metadata_core-0.1.0-py3-none-any.whl  sha256 = 0b3db80c9ab9160d9c925b0066ae9b3af72bf22cb4bf2e5278c43c9f47f4b42d   UNCHANGED（== 被验收候选 4358b3d）
L1  plugin zip   ffcc.fc2-metadata-0.1.0.zip               sha256 = 2181a12acb9931b4f7cecd4a1ba58b8b01035916979329b3607b4082f4187766   UNCHANGED（== 被验收候选 4358b3d；`_ffcc_pin.py` sha256 = 96a80189…d2463）
L1  INSTALL.zh-CN.md / VERSION（静态文本，不含任何哈希；零 diff）
-   MATRIX Part A   在 L0 + L1 的确切字节上执行真实宿主见证（4 个必需宿主 × 19 个场景；网关文件 sha256 = efc9ab9c1a1b71dec07f0bc0d62f798161e8012c22c26abec325084580dcd37a）
L2  COMPATIBILITY.json  sha256 = fc7c7caf945f0dd4cb0a6b623422dc13149396035e4b5ade515b63d672740476   （旧：9af6eae2…；Part A 变化所致）
L3  SHA256SUMS          sha256 = 1d1bf436b1d992af47cf585f7e64e21f19682b85f087e8c76fa634ab9e28f525   （旧：7900b840…）
L4  release bundle      ffcc-amane-release-0.1.0.zip  sha256 = 86c1ded8f1013dc8b60dda3cd0873c387ba95eda578cc5d78d963365435bb52c   （旧：8297037f…）
L5  MATRIX Part B（final_artifacts）只记录上面三个外层哈希，不写回 bundle
P5_C2_COMPATIBILITY_MATRIX.json（Part A + Part B）文件 sha256 = 86d4a0c04303b9336b9358af0fafaae9844adf9117034edc6d22cae63daa8d04   （旧：b5250b73…）
注：相对上一次对账运行，只有网关文件哈希（Part A 的 `tool.sha256`）变化；L2 / L3 / L4 与上一次逐字节相同（它们的投影不含网关哈希）。
```

验证（`final_pipeline`，不入库的编排脚本）：L0 / L1 在重新生成后与被验收候选的哈希**逐字节相同**（若不同即为越权，脚本会停止）；`pin` 中的 wheel 哈希 == 实际 wheel 哈希；L2 -> L3 -> L4 在同一 Part A 上两次独立构建逐字节相同；最终的 L2 -> L3 -> L4 -> Part B 由网关自己的 `finalize` 命令生成（它拒绝不完整 / 非全绿的 Part A 且不写任何产物，见 §0.1）；Part B 的取值不影响 L2–L4（E29 测试）。`core_admission` 共 70 行（旧 66 行 + 4 个必需宿主各 1 行符号链接子项，其中 4 行 = `ENVIRONMENTALLY_UNAVAILABLE`）。

@@CLEAN@@

## 6. 测试数字（E25 / E26 / E27 / E28）

```text
基线（P5-C2 S1 起始 / 被验收候选 4358b3d；3.12.10 项目 venv）: 8738 passed / 40 skipped / 0 failed
本轮新增 targeted 测试 : +89 = tests/amane_compat 290 -> 379
                          （test_amane_compat_matrix_json 32 -> 57：+25；新增 test_amane_compat_evidence_reconciliation：+64；其余文件数量不变；没有删除任何测试）
tests/amane_compat      : @@T_COMPAT@@
tests/amane_adapter     : **539 passed**（零 diff）
tests/amane_compat + amane_adapter : @@T_BOTH@@
python -m pytest tests -q（3.12） : @@T_FULL@@
新增 skip               : 0（`-rs` 清单与基线逐条比较：基线 `b8480e7` 同一命令的 `-rs` 输出：22 组 / 40 个，nodeid / 原因 / 数量逐条相同；`tests/amane_compat` 内 0 个 skip）
```

**Python 3.14 回归（P5-C1 冻结的 exact 命令、显式路径、无任何筛选参数；环境 = Python 3.14.7 + Amane v0.15.0 editable + pytest + httpx，Core 经 `PYTHONPATH=src`；实际重跑）**

| 集合 | 结果 |
|---|---|
| A（30 个显式路径） | **1833 passed**（31.60 s）——与 C1 终点一致 |
| B（22 个显式文件） | **520 passed**；3.12 与 3.14 的 `collected` 均为 520 |
| C（真实宿主见证 H-01..H-15） | **15/15 PASS**；输出写到临时路径，与已提交的冻结 `P5_C1_HOST_WITNESS.json`（LF 规范化）**逐字节相同**（`sha256(out) = 920cec8bd9b137e2e83e8cc1807c626568b2182a77c5c8177aa62e603ff5da58`）；该冻结文件零 diff |

**数字对账**：本轮全量 passed = 旧 8738 + 本轮新增的 89 个 targeted 测试 = **8827**；skip 仍为 40。

## 7. Mutation / non-vacuity（M2-01..M2-23；方法：对**临时仓库副本**打恰好一处补丁，子进程运行 killer；原树从不被修改）

本轮重跑 `tests/amane_compat/test_amane_compat_mutation_nonvacuity.py`（62 个测试，单元层 29 个变体）：**M2-01..M2-23 全部仍为 KILLED**（含 M2-14 的“接受符号链接”变体，它是符号链接替代证据的一部分）。本轮不修改任何产品实现，E31 的安全语义与上一版完全相同。上一版记录的**真实宿主** killer（`--hosts` 模式；M2-02/03/05/06/08/11/12/13/14/15/17..21/23）针对的是 locator / adapter / 构建器行为，本轮这些文件零 diff，因此**未重跑**，其结论沿用上一版 HANDOFF（`4358b3d`）的记录（Reviewer 应自行重跑，见 §10）：

| mutant | 变体 | 单元层 killer（KILLED） | 真实宿主 killer（沿用） |
|---|---|---|---|
| M2-01 | 错误 plugin id | E07、ZIP 布局、构建器 id 校验 | 构建期即被杀 |
| M2-02 | descriptor 覆盖 `api_version="2"` | E02、C1 `test_descriptor_declares_only_the_cross_version_subset` | HC-01、HC-03 |
| M2-03 | locator 静默忽略 sidecar 失败 | E31 i_tampered / k_shadow / u | HC-11 |
| M2-04 | Core 源码打进 plugin zip | E18、ZIP 布局 | — |
| M2-05 | reload 复用陈旧 Plugin 类 | shim 形状守卫 | HC-07 |
| M2-06 | 配置变更不重建 provider | E02 | HC-08 |
| M2-07 | 版本分支（读 `raw_results`） | AST 守卫 | — |
| M2-08 | 泄漏仅新版存在的 `max_attempts` | 同上 | HC-04（v0.15.0 宿主） |
| M2-09 | zip 含 `__pycache__` / `.pyc` | ZIP 布局 | — |
| M2-10 | 时间戳 / 条目顺序不确定（2 个变体） | ZIP 布局 | — |
| M2-11 | 升级后旧模块残留 | shim 形状守卫 | HC-09 |
| M2-12 | Pydantic 接受而 runtime parser 拒绝 | E02 | HC-05 |
| M2-13 | 引入自带 HTTP 库 / 绕过宿主 HTTP | E02、C1 架构守卫 | HC-04、HC-17 |
| M2-14 | 不校验 sha256 / **接受符号链接** / 接受任意文件名（3 个变体） | E31 i_tampered + c_loaded_tampered / **i_symlink** / b_loaded_wrong_version | HC-11 |
| M2-15 | pin 变化仍放行旧 Core | E31 b / c | HC-16 |
| M2-16 | UNVERIFIED 写成 SUPPORTED | matrix_json 自洽规则 | — |
| M2-17 | 已加载 Core 盲信 | E31 b / c / d / e / j | HC-19 |
| M2-18 | 接受任何目录形态 | E31 f×2 / h1 | HC-19 |
| M2-19 | 无最终真实解析 / 无同根检查（2 个变体） | E31 k / l1 / u / v；j×3 | HC-19 |
| M2-20 | 不回滚 `sys.path` / purge `fc2_metadata_core*` / 不恢复 importer-cache（3 个变体） | E31 l1 / l2；b / d + AST；l1 | HC-19 |
| M2-21 | 目录形态含恶意 `.pyc`（`*.py` 哈希接受） | E31-h1 / f_editable | HC-19 |
| M2-22 | artifact 派生环 | E29 DAG 测试 | — |
| M2-23 | existing-wheel 分支不做最终真实解析就返回成功 | **E31-u** + E31-p + AST | HC-19（E31-u） |

**本轮新增的证据非空洞 guard**（不是新的 M2 编号；`test_amane_compat_evidence_reconciliation.py` / `test_amane_compat_matrix_json.py`）：E16-B 的结果若 (1) 只调用 `reason_for_kind` 叶子函数、(2) 漏掉任一 kind、(3) 把 `NOT_FOUND` 变成 `SourceError`、(4) 不校验 / 篡改 `detail`、(5) 少一个必需宿主形态、(6) 用手写映射替代生产映射路径——全部被拒绝；对宿主内 `op_e16b` 的源码另有结构性 guard 与 5 个源码变体（漏 kind、`continue` 跳过、手写映射表、绕过 `provider.fetch`、绕过状态推导）全部被检出；MATRIX 校验器拒绝：缺 E16-B kind、缺必需宿主、`NOT_FOUND` 类别错误、旧的虚称 case 标签、非符号链接子项的 `ENVIRONMENTALLY_UNAVAILABLE`、缺 `symlink_privilege=false` 的 `ENVIRONMENTALLY_UNAVAILABLE` 等共 21 种违例；场景完成语义另有 18 个 guard（§0.1）。

## 8. 真实宿主见证 HC-01..HC-19（`docs/acceptance/evidence/P5_C2_COMPATIBILITY_MATRIX.json`）

四个必需宿主（HOST-A-SRC / HOST-B-SRC / HOST-A-WIN / HOST-B-WIN）**各 19/19**（最终树上的完整运行；四个宿主对的 parity 全部 `equal`，`allowed_diffs_observed = DIFF-01 / DIFF-05 / DIFF-07`）。

方法要点：
* 启动**真实 Amane 服务进程**（`python -m amane.server` / `Amane.Server.exe`），经**真实 HTTP API** 操作；不 mock `PluginManager / install_plugin_zip / purge / CrawlerFactory`。
* 宿主进程内观测使用**临时探针插件**（只存在于临时数据目录，不属于任何发布物）：它在 `discover()` 时执行 `tests/amane_compat/host_scripts/in_host.py` 并经宿主自己的 `failures` 通道回传 JSON；冻结桌面宿主与源码宿主走同一代码路径。
* HC-04 / HC-05 / HC-08 / HC-17 与 E15 / E16 在宿主进程内构建**受控宿主栈**（真实 `install_plugin_zip` -> `PluginManager.discover` -> `CrawlerFactory` + 真实 `WebClient` -> `127.0.0.1` 回环 fixture）。
* HC-19：所有宿主 = sidecar 各分支（HTTP）；源码宿主另在宿主进程内用真实 `install_plugin_zip` 执行 17 个 E31 用例，并以真实 `PYTHONPATH` 启动宿主执行 `.pyc` PoC 两个用例。冻结包只覆盖 sidecar 各分支，E31-u / E31-v 由源码宿主 + 单元层覆盖（合同第 11.2 节原文）。
* 场景**初始不是 PASS**，只有它依赖的阶段全部正常完成才置 PASS；阶段中断 -> 场景 false -> 坐标 BLOCKED -> finalize 拒绝（§0.1）。

### 8.1 已冻结的宿主事实（均为 Accepted A1 事实；不改变合同语义）

1. `POST /api/plugins` 成功返回 **201 Created**（两个版本相同；accepted authority fact；见 §0 A1-1）。
2. **HC-12a**（`.zip` 名 + 非 ZIP 字节）= 宿主 **HTTP 500**（宿主路由只捕获 `ValueError / TypeError / OSError`，`zipfile.BadZipFile` 未被捕获；两个版本相同；无残留 / 无注册 / 插件代码从未执行）；**12b..12e** = 422。这是 pinned 宿主的已知路由缺陷，不是允许 plugin / artifact 返回 500。
3. HC-13：错误 id 的 zip 被宿主以 `descriptor().id` 为目录名提交（`other.id`），内容路由 / 配置不引用它；两个版本相同。
4. `CrawlerFactory` 为 `PluginContext.data_dir` **创建** `plugins/<id>/`（宿主行为）；adapter 从不使用 `data_dir`；HC-18 断言这些运行期目录内没有任何文件。
5. 宿主 `reload` 先 `purge_imported_plugin_modules()`（清空 `sys.path_importer_cache`）；Core 常驻。
6. **符号链接真实宿主子项 = `ENVIRONMENTALLY_UNAVAILABLE`（`symlink_privilege=false`）**；替代证据已由 A1 Reviewer 裁定充分（§0）。不是真实宿主执行 PASS。
7. 源码宿主启动需要去掉继承的 `FORCE_COLOR`；网关对宿主环境做了清理。

## 9. 偏差、实现裁决、运行记录与 Evidence Gaps

偏差 / 裁决：
1. **`prefix == ""` 只对顶层 `fc2_metadata_core` 的 spec 要求**（合同本来只要求顶层 spec；非 amendment 事项）。
2. 单元层 locator 用例在 `python -S` 子进程里运行并清理环境。
3. `in_host.py` 用 `importlib.import_module` 取宿主对象（P5-C1 的测试树守卫禁止 `tests/` 下出现 amane 的 import 语句）。
4. 宿主内 HC-08 不是“调用宿主自己的 factory”（没有任何 HTTP 路由能在没有媒体库的情况下触发一次 fetch；真实 scrape 属 Phase 6，L-C2-10）。
5. **E16-B 的惰性引擎桩**：只替代上游 `MultiSourceEngine.aggregate` 的执行；生产 `map_aggregation` 与生产 provider 转换不被替代，并以计数包装器证明（见 §4 E16）。
6. **HC-11(c)**（冻结包无法布置目录形态夹具）按 Authority Review 的裁定“无需修改”；本轮未触及。

**运行记录（如实）**：对账的第一次完整 4 宿主运行中，冻结 v0.18.0 宿主（`b-win`）的控制栈阶段在**最后一个探针**（`enumerations`，E16-B 已成功之后）处出现一次宿主瞬时无响应（探针 reload 请求超时返回空，约 500 s），该阶段被中断；HC-04 当时没有失败记录，仅 HC-18 间接失败。这暴露了网关的“没有失败记录 = PASS”缺陷，已按 §0.1 修复（场景初始 false；完成才 PASS；finalize 拒绝）。此后观察到的瞬时宿主错误共 3 次，均**未复现**、未定位根因、视为宿主进程 / Windows 文件占用的偶发：上述 `b-win` 无响应 1 次；以及 2 次 Windows `PermissionError [WinError 5]`（宿主在 `fetch_matrix` 的某个用例里把自己的暂存目录 `.ffcc.fc2-metadata.new` 重命名为正式目录时被拒绝：一次在干净检出的第一次运行里的 `b-win`，一次在 §0.1 的临时中断证明里的 `a-win`）。每次出现时，该运行都被判失败并被丢弃（现在会得到 false 场景、BLOCKED 与 finalize 拒绝），未改任何文件即完整重跑；**所有最终产物只来自完整、四宿主均 19/19 的运行**。若 Reviewer 重跑时遇到，请先单独重跑该宿主确认。

Evidence Gaps（如实）：
* **E16-A**：端到端只观测到 7 个 kind（`K_A`），其余 9 个**未被端到端观测到**；它们由 E16-B（宿主进程内、生产映射与生产 provider 转换、全部 16 个成员 × 4 个必需宿主）覆盖——E16-B 不是传输层证据（L-C2-16）。
* **符号链接真实宿主子项**：`ENVIRONMENTALLY_UNAVAILABLE`（L-C2-15）；若 Reviewer 日后要求补证，条件见合同第 11.7 节 A1-3 第 4 条。
* **L-C2-14**：HC-12a 的 500 是 pinned 宿主（v0.15.0 / v0.18.0）的已知路由缺陷，仅对该 exact 变体与这两个版本冻结。
* **L-C2-02 / SC-06**：v0.16.1 / v0.17.0 未运行（可选信息见证）。
* **macOS / Linux / Docker**：UNVERIFIED（SC-07..SC-09；无环境）。
* **L-C2-13（ACCEPTED SECURITY LIMITATION）**：校验只保证准入时刻的完整性；运行期间对 wheel 的持续写入者不被防御；已加载 Core 的证明是 current-origin + current-artifact proof；INSTALL 要求“运行期间不要替换或删除 sidecar wheel”。
* L-C2-03、L-C2-05、L-C2-07、L-C2-09、L-C2-10、L-C2-12 按合同如实保留；C1 L-01..L-15 继续成立。
* 宿主依赖安装（联网）与官方冻结包下载属环境前提；网关 / 受控栈对站点的所有请求都只到 `127.0.0.1`。

## 10. 状态与下一步

```text
git diff --check          : CLEAN
git status                : CLEAN（提交后）
Frozen scopes             : ZERO DIFF（src/**、C1 adapter 树、shim、INSTALL、构建器、既有 tests/**、P5-C1 文件 / evidence、合同 / 施工计划、治理文档）
L0 / L1 输入字节          : UNCHANGED
Risk Class                : C（未升级）
Authority debt            : U2-5 已记录并由 Accepted A1 偿还
P5-C2 PRE-L1 EVIDENCE RECONCILIATION : COMPLETE
Technical Acceptance      : NOT YET
P5-C2                     : NOT CLOSED
Next                      : P5-C2 INDEPENDENT LEVEL 1 REVIEW（C 级；必须独立执行 E31、M2-14..M2-23 与 E16-B；不得只引用本文）
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
