# Phase 4 / P4-C8 Handoff -- 批量编排 / 预览 / 重试（Batch Orchestration / Preview / Retry）

```text
Phase        = 4
Package      = P4-C8 Batch Orchestration / Preview / Retry（fc2_organizer.orchestration）
Role         = Developer（S6 执行者）
Branch       = claude/phase4-c8-batch-orchestration
规范合同     = docs/specifications/PHASE4_BATCH_ORCHESTRATION_CONTRACT.md
施工计划     = docs/P4_C8_CONSTRUCTION_PLAN.md（当前权威：S5-A1 0f591ff）
```

**当前状态**：`P4-C8 implementation: COMPLETE — INDEPENDENT REVIEW REQUIRED`；`P4-C8: NOT CLOSED`；`P4-C9: NOT STARTED`；
`Phase 4: NOT CLOSED`。

本文件是 reviewer 证据文档，不是验收结论。S6 与 P4-C8 均须经过 P4-C8 S6 FINAL INDEPENDENT CLOSURE REVIEW；本文件不宣布
S6 ACCEPTED、P4-C8 CLOSED 或 Phase 4 CLOSED，也不包含“P4-C8 最终闭合”一节（那属于复查 PASS 之后的 Final Closure Docs）。

## 1. 坐标

```text
Repo                              = https://github.com/fankunet-arch/ffcc.git
Branch                            = claude/phase4-c8-batch-orchestration
Frozen Base                       = 586f92f9b96576dbd71c005a6c95b6e7e52210f4   P4-C7 Final Closure Docs
E0 Final Accepted Docs Head       = 9e118dea32361ec19b0a84f84b6e5da0fbd134bc   E0-R2（合同 + 施工计划）
S1 Final Reviewed Code Head       = e8f83e986d3cb306a425d666f3bc0a2738dab823
S2 Final Reviewed Code Head       = 8c5ba6e808a6c45ee2342af497458fe88af5ff09   S2-R5
S3 Final Reviewed Code Head       = 7fb6bfb2d230d90d240a0a4b462332d27afe77d5   S3-R2
S4 Final Reviewed Code Head       = 4933f38bd09101766643af0b66757080565a8619   S4-R1
S5 Final Reviewed Code Head       = 78f92c8b77a7ef15f0563decd1773d30cfb65f0e   S5-R1（= S6 Frozen Input）
施工计划修订（均已 ACCEPTED）     = S2-A1 9e45009、S3-A1 570c3d0、S4-A1 b4d8c35、S5-A1 0f591ff
S6 Code Review Candidate          = 4d8efe2fa101316404f97c77395235f8e7a64150   只含 S6 测试
S6 Docs Head                      = 本提交（git log -1 --format=%H -- fc2-organizer/docs/review/P4_C8_HANDOFF.md）

S6 Code Review Range       : 78f92c8b77a7ef15f0563decd1773d30cfb65f0e..4d8efe2fa101316404f97c77395235f8e7a64150
S6 Docs Review Range       : 4d8efe2fa101316404f97c77395235f8e7a64150..<S6 Docs Head>
Final S6 Closure Review    : 78f92c8b77a7ef15f0563decd1773d30cfb65f0e..<S6 Docs Head>
```

关系：`S6 Code Review Candidate^ == 78f92c8`；`S6 Docs Head^ == 4d8efe2`。开始前已验证
`HEAD == origin/claude/phase4-c8-batch-orchestration == 78f92c8` 且工作区干净。没有 rebase、amend、squash、force push 或
改写历史。

**Code Review Candidate 与 Docs Head 严格区分**：代码复查对象是 `4d8efe2`（只含测试）；Docs Head 只新增本文件并修改合同
第 38 节状态行，不含任何代码或测试。

## 2. 变更范围

### 2.1 S6 Code Review Candidate（`4d8efe2`，1 个文件，+771 / -0）

```text
A fc2-organizer/tests/unit/orchestration/test_orchestration_synthetic_gate.py   （771 行）
```

* `tests/unit/orchestration/_fakes.py`、`_helpers.py`：**未修改**（S5-A1 的既有 helper 修改特例只用于 S5-R1，S6 回到“只追加”，
  且本批无需追加）。
* Production Files Changed：**NONE**（`src/**` 相对 S5 Final Head 零差异）。

### 2.2 S6 Docs Head（2 个文件）

```text
A fc2-organizer/docs/review/P4_C8_HANDOFF.md
M fc2-organizer/docs/specifications/PHASE4_BATCH_ORCHESTRATION_CONTRACT.md   仅第 38 节
```

第 38 节：S5 行 `S5-R1 IMPLEMENTED — INDEPENDENT REVIEW REQUIRED` -> `S5 ACCEPTED / CLOSED — FINAL REVIEWED CODE HEAD 78f92c8…`；
S6 行 `NOT STARTED` -> `S6 IMPLEMENTED — INDEPENDENT REVIEW REQUIRED`；状态块同步，并把 `P4-C8 Implementation` 记为
`COMPLETE — INDEPENDENT REVIEW REQUIRED`。第 1-37 节零差异。

### 2.3 S6 期间的生产缺陷

S6 门槛**没有**发现任何生产正确性缺陷；没有 `fix(orchestration): … (P4-C8 S6)` 提交。

### 2.4 E0..S6 全部变更文件（`git diff --name-status 586f92f..<S6 Docs Head>`）

```text
生产（11，全部新增）     src/fc2_organizer/orchestration/{__init__,_consumption,cancellation,errors,execute,models,
                         orchestrator,preview,recognition,retry,stages}.py
测试（新增）             tests/unit/orchestration/__init__.py、_fakes.py、_helpers.py 与 29 个 test_orchestration_*.py：
                         batch_outcome、cancellation_token、config、consumption、determinism、errors、execute、
                         execute_cancellation、execute_concurrency、execute_fatal、fault_injection、integration、merge、
                         models、orchestrator、preview、preview_concurrency、preview_fatal、preview_no_mutation、
                         preview_resources、preview_retry、race、recognition、retention、retry_chain、retry_kind_table、
                         stages、summary、synthetic_gate
架构守卫（新增）         tests/contract/test_orchestration_architecture.py
既有架构守卫（合同 34.3 授权，S1，各一处最小修改）
                         tests/contract/test_{discovery,planning,publication,nfo,execution,materialization}_architecture.py
合同                     docs/specifications/PHASE4_BATCH_ORCHESTRATION_CONTRACT.md（新增；之后只改第 38 节）
施工计划                 docs/P4_C8_CONSTRUCTION_PLAN.md（新增；S2-A1 / S3-A1 / S4-A1 / S5-A1 范围修订）
HANDOFF                  docs/review/P4_C8_HANDOFF.md（本文件）
```

P4-C1..P4-C7 的生产代码、合同、HANDOFF 均未修改（除上表六个经合同第 34.3 节授权的既有架构守卫）。

## 3. 合同章节映射（合同节 -> 实现 -> 测试证据）

| 合同节 | 实现（文件 / 函数） | 测试证据 |
|---|---|---|
| §4 Phase 3 复用 | `orchestrator.py`（一个 `BatchScheduler`、`_EngineAdapter`）；`retry.py`（`retry_failed` + `apply_retry`） | `test_orchestration_orchestrator.py`、`test_orchestration_preview.py`、`test_orchestration_retry_chain.py::test_metadata_failure_retries_until_success_consistently_with_phase_3` |
| §5 模块划分 | 11 个模块（无新增） | `test_orchestration_architecture.py::test_package_has_exactly_the_final_modules`（并与合同第 5 节模块表比对） |
| §6 依赖方向 | 各模块 import | `test_every_module_imports_only_its_allow_list`、`test_no_private_lower_layer_module_reference`、`test_forbidden_modules_item_by_item`、运行时阻断（`test_the_full_lifecycle_runs_with_forbidden_modules_blocked`、`test_orchestration_integration.py::test_the_real_lifecycle_runs_with_forbidden_modules_blocked`） |
| §7 公开 API / busy-first / 错误层次 | `__init__.py`（`__all__` == 第 7.1 节 37 名）、`orchestrator._claim/_release`、`errors.py` | `test_public_api_is_exactly_the_final_contract_list`（与合同原文解析比对）、`test_orchestration_orchestrator.py`（busy-first 全方法）、`test_orchestration_errors.py` |
| §8 严格类型 | `models.type_name` / `reason_detail`、`recognition.validate_media_items` | `test_orchestration_models.py`、`test_orchestration_recognition.py` |
| §9 配置 | `models.OrchestrationConfig` | `test_orchestration_config.py` |
| §10 模型与不变量 | `models.py` | `test_orchestration_models.py`、`test_orchestration_merge.py`（hostile 图） |
| §11 状态 / `BatchOutcome` | `BatchExecutionResult.outcome` | `test_orchestration_batch_outcome.py`、`test_orchestration_summary.py`（28.4 交叉验证）、门槛九个 outcome 断言 |
| §12 身份 / lineage / generation | `models`、`retry.merge_retry` | `test_orchestration_merge.py`、`test_orchestration_retry_chain.py::test_a_chain_g0_to_g3_advances_one_generation_per_merge` |
| §13 顺序 | `preview.build_preview`、`execute` 位置槽 | `test_orchestration_determinism.py`、`test_orchestration_execute_concurrency.py` |
| §14 识别与冲突（Phase A / B） | `recognition.recognize`、`stages.phase_b_conflicts` | `test_orchestration_recognition.py`、`test_orchestration_race.py`（hardlink / 同文件两次 / 重叠根）、门槛 C 组（Phase A 在 metadata 之前阻断、Phase B 在 preflight 之后） |
| §15 preview 语义 | `preview.build_preview`、`stages.*` | `test_orchestration_preview.py`、`test_orchestration_stages.py`、`test_orchestration_integration.py` |
| §16 零修改 | 结构上只读 | `test_orchestration_preview_no_mutation.py`、门槛每次 preview / preview_retry 的树快照 |
| §17 方案 A | `execute._execute_one`（preview 自己的 preflight） | `test_orchestration_execute.py`、架构 `test_execute_filesystem_has_one_call_site_on_the_previews_own_preflight` |
| §18 execute 语义 | `execute.execute_preview`（九步） | `test_orchestration_execute.py`、`test_orchestration_fault_injection.py` |
| §19 并发与资源 | `preview._Ledger` / `_image_stage`、`execute._execute_threaded`、`recognition.bounded_snapshot`、`retry` 可用额度 | `test_orchestration_preview_concurrency.py`、`test_orchestration_execute_concurrency.py`、`test_orchestration_preview_resources.py`、`test_orchestration_retention.py`、门槛资源子门槛 |
| §20 隔离与致命边界 | `preview._FatalCarrier`、`execute._drain` | `test_orchestration_preview_fatal.py`、`test_orchestration_execute_fatal.py` |
| §21 失败映射 | `stages.*`、`execute._raised_outcome` / `_returned_outcome` | `test_orchestration_stages.py`、`test_orchestration_execute.py`、`test_orchestration_fault_injection.py`（15 / 15 `TransferStage`） |
| §22 图片部分获取与警告 | `ItemPreview.warnings`、`execute._warnings` | `test_orchestration_preview.py`、`test_orchestration_summary.py` |
| §23 PARTIAL | `models._check_retry_material` | `test_orchestration_retry_chain.py`（B） |
| §24 checkpoint 所有权 | `retry._retained_preflight`（原对象交回） | `test_orchestration_retry_chain.py`（B / D / E）、`test_orchestration_preview_retry.py` |
| §25 retry 规则 | `ItemExecution.retry_kind`、`retry.build_retry_preview`（12 步，登记最后） | `test_orchestration_retry_kind_table.py`、`test_orchestration_preview_retry.py`、`test_orchestration_retry_chain.py` |
| §26 merge_retry | `retry.merge_retry`（1-11 步，9a / 9b，完整 revalidate） | `test_orchestration_merge.py`、`test_orchestration_retention.py`、`test_orchestration_race.py` |
| §27 取消 | `execute._Run.admit`、`cancellation.CancellationToken` | `test_orchestration_execute_cancellation.py`、`test_orchestration_cancellation_token.py` |
| §28 汇总 | `PreviewSummary` / `ExecutionSummary`（派生属性） | `test_orchestration_summary.py`（确定性枚举） |
| §29 确定性 | 位置槽、index 顺序 | `test_orchestration_determinism.py`（含 `LeftoverTemporary.name` 投影回归）、门槛全新树反转重跑 |
| §30 安全 / 路径 / 跨进程 | 委托 P4-C7 | `test_orchestration_race.py`（漂移、跨 orchestrator 同源） |
| §31 P4-C7 委托 | `stages.preflight_stage`、`execute._execute_one` | 架构 `test_stage_api_and_acquire_images_ownership`、`test_structural_zero_mutation_and_no_unbounded_concurrency` |
| §32-33 P4-C9 边界 / 持久化非目标 | 无 | 架构 `test_no_persistence_or_diagnostics_output`、`test_no_forbidden_calls_or_definitions` |
| §34 架构测试 | -- | `test_orchestration_architecture.py`（含 S5-R1 的精确 import 状态恢复）与六个既有守卫 |
| §35 / 35.1 / 35.1.1 测试矩阵与门槛 | -- | 上表全部文件；`test_orchestration_synthetic_gate.py`（第 4-6 节） |
| §36 / §37 / §38 | -- | 本文件第 10、11 节；合同第 38 节 |

## 4. 500-item 门槛（`test_orchestration_synthetic_gate.py::test_the_500_item_gate_with_a_deterministic_reversed_rerun`）

### 4.1 构成（静态断言；默认资源配置，`M = K = W = 4`，P4-C7 同卷策略接缝设为 `link`）

| 组 | 数量 | 构造 | g0 preview | g0 执行 / RetryKind | 处理轮次 |
|---|---|---|---|---|---|
| A 正常 | 310 | metadata SUCCESS / PARTIAL 混合；8 种主图组合 × extrafanart 0..3；部分候选失败 | READY | SUCCESS / NONE | g0 |
| B 番号不可识别 | 40 | 文件名无 FC2 番号 | UNPREPARED / `NUMBER_NOT_RECOGNIZED` | NOT_READY / NONE | -- |
| C 批内冲突 | 30 | 10 对同番号不同文件（20）+ 3 个条目重复出现（6）+ 2 对 hardlink 且番号不同（4） | BLOCKED / `DUPLICATE_*` | NOT_READY / NONE | -- |
| D metadata 失败 | 40 | 25 聚合 FAILED + 10 engine 异常 + 5 结果合同不符；30 个在 g2 成功 | UNPREPARED / `METADATA_*` | NOT_READY / METADATA_REFETCH | g2（30）、g4（10 仍失败） |
| E NFO 失败 | 10 | 非法 release（真实 NFO 阶段） | UNPREPARED / `NFO_RENDER_FAILED` | NOT_READY / NONE | -- |
| F preflight 阻断 | 20 | 预先植入目标目录；g2 前测试移除 15 个 | BLOCKED / `PREFLIGHT_BLOCKED` | NOT_READY / PREFLIGHT_RECHECK | g2（15）、g4（5 仍阻断） |
| G 执行故障 | 30 | 15 个 U1 前（源重新校验 lstat）-> FAILED；15 个 U1 后（5 `SOURCE_UNLINK_FAILED`、5 NFO publish、5 NFO write）-> PARTIAL | READY | FAILED / FRESH_REEXECUTE；PARTIAL / RESUME | g1（RESUME 15）、g2（FRESH 15） |
| H 外来异常 | 10 | 经 `_FS` 在 U2 link 注入 `RuntimeError` | READY | ABORTED / NONE | -- |
| I 未选中 | 10 | 主轮 selection 排除 | READY | NOT_SELECTED / DEFERRED | g3 |

输入为 497 个由真实 `discover_media` 发现的合成文件（几字节）加 3 个重复条目，共 500。

### 4.2 各轮计数（全部精确断言）

```text
主 preview   total 500 / ready 360 / blocked 50 / unprepared 90
主结果 g0    success 310 / partial 15 / failed 15 / aborted 10 / not_selected 10 / blocked 50 / unprepared 90
             retryable 90（RESUME 15、FRESH_REEXECUTE 15、METADATA_REFETCH 40、PREFLIGHT_RECHECK 20）/ deferred 10 / non_retryable 90
g1 {RESUME}                                 15 READY -> 15 SUCCESS；合并后 success 325
g2 {METADATA_REFETCH, FRESH_REEXECUTE, PREFLIGHT_RECHECK}
                                            75 条 -> preview ready 60 / blocked 5 / unprepared 10 -> 60 SUCCESS；合并后 success 385
g3 {DEFERRED}                               10 READY -> 10 SUCCESS；合并后 success 395
g4 scope=None                               15 条（D 10 + F 5）-> ready 0，执行 0 条
最终         success 395 / blocked 35 / unprepared 60 / aborted 10 / retryable 15 / deferred 0 / non_retryable 90
```

### 4.3 outcome 表（九个断言，逐项 `assert`）

| 结果 | outcome |
|---|---|
| g0 主结果 | PARTIAL |
| g1 重试轮 / 合并 | SUCCESS / PARTIAL |
| g2 重试轮 / 合并 | PARTIAL / PARTIAL |
| g3 重试轮 / 合并 | SUCCESS / PARTIAL |
| g4 重试轮 / 最终 | FAILED / PARTIAL |

### 4.4 安全与正确性断言

* 峰值：metadata（engine）、图片（client）、文件系统执行均 `== 4`（`<= 4`）。
* 每次 preview / preview_retry 前后树快照完全相等；retained-material 重试（g1）engine / client 调用 0 次。
* 每轮执行后：全部 500 条的核心不变量（`assert_source_not_lost`；无 plan 的条目源字节不变）；非本执行拥有的文件字节 / inode /
  mtime 不变；H 组 10 条显式 `assert_source_not_lost`。
* 同一 preview 再次 `execute` -> `OrchestrationConsumedError`。
* RESUME（g1）：G 组 15 条已发布的 artifact 与媒体在 g1 前后 inode / mtime 不变（不重写、不重新移动）。
* 最终库目录精确列举：395 个成功影片目录（每个文件的字节：媒体 = 源字节，NFO = 真实 P4-C4 渲染结果，图片 = 实际获取的字节，
  extrafanart 名称 `extrafanart-001.jpg …` 与顺序）、用户保留的 5 个阻断目录（`user-note.txt` 不变）、10 个 ABORTED 条目的空目标
  目录（P4-C7 U1 后停止）；没有任何 `.fc2tmp-*` 临时残留（本门槛没有记录任何 `LeftoverTemporary`）。
* 每个当前完整结果 `retained_retry_payload_bytes <= retention_budget_bytes`。

### 4.5 确定性重跑

整个门槛在全新的第二棵树中再完整运行一次：engine 与图片的完成顺序以门控事件反转（后开始者先完成），前四个执行以条件变量按
反向开始顺序完成。两轮共 14 个模型（主 preview、主结果、4 × 重试 preview / 重试轮 / 合并）的确定性投影、summary 与 outcome
逐项相等（只把各自的根路径替换为占位符；排除字段严格按合同第 29 节）。

## 5. 资源边界子门槛（小配置）

| 子门槛 | 结果 |
|---|---|
| `MAX_BATCH_ITEMS`（2000 个不可识别番号的手工条目） | 接受，2000 条 UNPREPARED |
| `MAX_BATCH_ITEMS + 1` | `OrchestrationResourceLimitError(BATCH_ITEM_LIMIT)`；engine 调用 0、client 调用 0、修改拦截 0 |
| 有界快照（计数型自定义 `Sequence` 经 `preview`）：`MAX + 1`、惰性 1 000 000、说谎长度（`__len__ == 1`，实际 3000） | 三者均 `BATCH_ITEM_LIMIT`；读取元素数 `== 2001`；`__len__` 调用 0、`__getitem__` 调用 0 |
| `B_exact`（500-item 语料，`R = 714`，387 个图片条目，`A_nfo = 255420`） | `B_exact = 396197`：preview 成功，条目投影与默认配置主 preview 相等 |
| `B_exact - 1 = 396196` | `RETAINED_BYTES_LIMIT`，不返回 preview，零修改 |
| 并发预约（6 条，`K = 4`，`R = 623`，`A_nfo = 3960`，`B = 5206` 只容纳 2 个预约） | `RETAINED_BYTES_LIMIT`；进行中的 `acquire_images` 峰值 `== 2`；账本最大值 `5206 <= B`；自然与反转完成顺序下准入的条目集合相同（前两个） |
| 多代保留（合同第 35.1.1 节；`L = 165`、`I = 40123`、`pay = 40288`、`need = 40783`、`payD = 161152`、`B = 201935`） | g0 `161152`；g1 恰好准入，合并 `201440`；g2 越界尝试 `RETAINED_BYTES_LIMIT` 且 g1 合并结果未被登记；g2 结算 `161152`；g3 恰好准入，合并 `201440`；g4 `0`（M3、M4 仍 metadata FAILED）；每代 `<= B` |

## 6. 非空洞性（mutation）门槛

全部十种变异都未提交；每种变异后运行整个门槛文件，撤销后以 `git hash-object --no-filters` 与 HEAD blob 比对确认逐字节恢复
（全部 `True`），最终工作区只剩正式 S6 工作。

| # | 变异 | 文件 | 杀死机制（行为层断言） | 失败用例 | 失败数 |
|---|---|---|---|---|---|
| (a) | 去掉 Phase A 冲突阻断 | `preview.py` | C 组 Phase A 条目“无 metadata、无 preflight、engine 未被询问”的断言失败 | 500-item 门槛 | 1 |
| (b) | `execute` 不登记 `preview_id` | `execute.py` | 再次 `execute` 同一 preview 不再抛 `OrchestrationConsumedError` | 500-item 门槛 | 1 |
| (c) | summary 把 PARTIAL 计入 success | `models.py` | `ExecutionSummary` 恒等式（`total == success + retryable + …`）与计数断言失败 | 500-item 门槛 | 1 |
| (d) | RetryKind 对调 RESUME / FRESH_REEXECUTE | `models.py` | 主执行结果的 RESUME 材料不变量失败（结果无法构造） | 500-item 门槛 | 1 |
| (e) | 执行 worker 改为每条目一个线程 | `execute.py` | 文件系统执行峰值 `181 != 4` | 500-item 门槛 | 1 |
| (f) | 图片预约无条件准入（不检查预算） | `preview.py` | `B_exact` 预期成功却失败、`B_exact - 1` 不再是 `RETAINED_BYTES_LIMIT`；并发预约峰值 / 账本断言失败 | B_exact、并发预约 × 2 | 3 |
| (g) | 移除 `MAX_BATCH_ITEMS` 检查 | `recognition.py` | `MAX + 1` 被接受；三个有界快照用例不再抛 `BATCH_ITEM_LIMIT` | MAX_BATCH_ITEMS、有界快照 × 3 | 4 |
| (h) | 非空全 SUCCESS 结果不判为 SUCCESS | `models.py` | g1 重试轮 outcome `PARTIAL != SUCCESS` | 500-item 门槛 | 1 |
| (i) | 恢复 snapshot-first（先 `tuple(items)`） | `recognition.py` | 读取元素数远大于 `MAX + 1`（惰性 1 000 000 全部读取） | 有界快照 × 3 | 3 |
| (j) | `preview_retry` 可用额度改为完整 `B` | `retry.py` | 35.1.1 g2 越界重试不再以 `RETAINED_BYTES_LIMIT` 拒绝（重试 preview 载荷超过 retry 预算） | 多代保留 | 1 |

## 7. 测试数字（全部在 S6 Code Review Candidate 工作树上；Windows 11 10.0.26200；Python 3.12.10；`-p no:cacheprovider --basetemp=<job tmp>/…`）

```text
Synthetic gate                 9 passed, 0 skipped, 0 failed   （115.92 s）
tests/unit/orchestration + architecture   949 passed, 0 skipped, 0 failed   （S5 Final 基线 940）
tests/contract                 209 passed, 0 skipped, 0 failed  （基线 209）
Full suite                     6178 passed, 40 skipped, 0 failed；collected 6218 = 6178 + 40   （基线 6169 / 40 / 6209）
```

新增 skip：**NONE**（S6 门槛 9 个用例全部执行；junction 等 Windows 用例实际运行）。全量的 40 个 skip 与 S5 基线相同、全部是既有的
平台 / 环境 skip，没有任何一个在 orchestration 测试中：execution symlink 权限 14、discovery symlink 权限 4、materialization
symlink 权限 5、P4-C7 POSIX 原生证据 4 + 原生 POSIX link 1、原生跨卷 2（未配置 `FC2_EXECUTION_CROSS_VOLUME_ROOT`）、planning 的
POSIX 路径形式 10（14 + 4 + 5 + 5 + 2 + 10 = 40）。skip 不计为通过。

如实记录一次瞬时失败：第一次全量运行中，与 P4-C8 无关的 Phase 3 C2 墙钟测试
`tests/unit/aggregation/test_agg_retry_execution.py::test_17_total_deadline_covers_attempt_backoff_and_retry_not_deadline_times_attempts`
（0.3 s 墙钟预算）在主机高负载下失败（deadline 落在 backoff 而非 attempt）；单独运行连续 3 次 PASS，全量重跑 `6178 passed`。
未对该测试或任何非 S6 文件做修改。

`git diff --check`：Code Range（`78f92c8..4d8efe2`）、Docs Range、`78f92c8..<S6 Docs Head>` 均干净。

## 8. 直接复现表

所有命令在 `fc2-organizer/` 下以 `python -m pytest -q -p no:cacheprovider --basetemp=<tmp>` 运行（下称 `PT`）。

| 场景 | 命令 / 测试 | 预期 | 实际 |
|---|---|---|---|
| 500-item 门槛 + 反转重跑 | `PT tests/unit/orchestration/test_orchestration_synthetic_gate.py::test_the_500_item_gate_with_a_deterministic_reversed_rerun` | 第 4 节全部断言 | PASS |
| MAX / MAX+1 | `PT …::test_max_batch_items_is_accepted_and_one_more_fails_before_any_work` | 接受 / `BATCH_ITEM_LIMIT`，调用与修改 0 | PASS |
| 有界快照 | `PT …::test_the_bounded_snapshot_reads_at_most_limit_plus_one_through_preview` | 读取 2001、`__len__` 0 | PASS（3 个参数） |
| `B_exact` / `B_exact - 1` | `PT …::test_b_exact_admits_the_500_item_preview_and_one_byte_less_fails` | 成功且投影相等 / `RETAINED_BYTES_LIMIT` | PASS |
| 并发预约 | `PT …::test_reservation_admission_holds_two_in_flight_when_b_fits_two` | 峰值 2、账本 `<= B`、顺序无关 | PASS（自然 / 反转） |
| 35.1.1 g2 越界 | `PT …::test_multi_generation_retention_g0_to_g4` | g2 `RETAINED_BYTES_LIMIT`，g0-g4 精确字节 | PASS |
| RESUME inode / mtime | 500-item 门槛 g1 段 | G 组 15 条不变 | PASS |
| 确定性重跑 | 500-item 门槛第二轮 | 14 个模型投影 / summary / outcome 相等 | PASS |
| 目标 / contract / 全量 | `PT tests/unit/orchestration tests/contract/test_orchestration_architecture.py`；`PT tests/contract`；`PT` | 0 failed | 949 / 209 / 6178 + 40 skipped |

## 9. 证据缺口（如实列出；不是 FAIL，也不是 PASS）

* **EVIDENCE GAP**：真实跨进程并发——P4-C8 不提供跨进程协调（合同第 30.3 节），门槛只在单进程内验证。
* **EVIDENCE GAP**：POSIX 原生主机——本批全部在 Windows 11 上运行。
* **EVIDENCE GAP**：kernel `O_NOFOLLOW` 原生证据、原生跨卷真实设备、Windows native symlink——属于 P4-C7 既有缺口；P4-C8 的跨卷
  用例使用 P4-C7 的 `device_of` 接缝（模拟设备号），S6 **不声称**补足任何 P4-C7 证据缺口。

## 10. 延续项（合同第 36 节，原样）

| 延续项 | P4-C8 的处理 |
|---|---|
| C4-N1（跨持久化的出处 / durable batch id） | 不触及：P4-C8 复用内存 lineage，不持久化；保持 CARRIED |
| P2-R-07（adapter `elapsed_ms` 不可信） | P4-C8 不发布任何计时；保持 CARRIED，留给 P4-C9 |
| P4-C7 §30 “批量去重（包括避免跨进程派发同一源）属于 P4-C8” | 批内去重由第 14 节实现；跨进程协调在 v1.0 不提供（第 30.3 节），作为已声明边界延续 |
| P4-C7 §25 TOCTOU 剩余风险、进程内源所有权占用的跨进程边界 | 不变；P4-C8 不扩大不缩小 |
| P4-C7 证据缺口（Windows native symlink、POSIX native、kernel `O_NOFOLLOW`、native cross-volume） | 不触及；P4-C8 测试不声称补足 |
| fc2db_net release 规范化（未编号的上游观察） | P4-C8 以 `NFO_RENDER_FAILED` 如实报告受影响条目；不修复 |
| P4-C4-R-01、P4-C3-R-01、P4-C3-R-02、P4-C2-R1-02、P4-C1-R-02..R-05、P2-R-05、P2-R-06、C3-N1..N4、C4-R1-N1..N3、F3、F5、C5-R1-L1、扩展的 Windows 保留名（planning finding） | 不触及、不修改相应模块；保持 CARRIED |

P4-C8 不关闭、不降级、不重新打开任何延续项。

## 11. 已知局限（合同第 37 节）

* 非法 `library_root` 在 metadata / 图片网络阶段之后才以 `PLANNING_REJECTED` 暴露（第 15.3 节）。
* 资源硬限制：条目数 `<= MAX_BATCH_ITEMS`、每个 preview 的保留 artifact 载荷 `<= max_retained_artifact_bytes`；超过时整个
  `preview` / `preview_retry` fail closed（第 19.6 节）；预约准入可能使图片并发低于 K；预算在一个 lineage 内固定，当未结算
  条目占满预算时，新的 `METADATA_REFETCH` 重试可能需要先执行 / 结算其他条目；调用方自己同时持有多代结果的内存属于调用方所有权。
* 执行中的条目不可中断，取消只停止准入（第 27 节）。
* 致命异常后不返回部分结果，已执行条目的 checkpoint 随之丢失（第 20.3 节）。
* 无跨进程协调（第 30.3 节）；无 durable resume（第 24.3、33 节）；无进度流（第 11.4 节）。
* 番号只从文件 basename 识别（第 14.1 节）；冲突组全部阻断，不自动选择胜者（第 14.4 节）；metadata `PARTIAL` 不被自动重新
  刮削（第 25.6 节）。

## 12. 未决事项

* 未解决技术决策：NONE。
* 需要外部业务决策：NONE。

## 13. 状态

```text
E0                            : ACCEPTED / CLOSED（9e118de）
S1 / S2 / S3 / S4 / S5        : ACCEPTED / CLOSED（e8f83e9 / 8c5ba6e / 7fb6bfb / 4933f38 / 78f92c8）
S6                            : IMPLEMENTED — INDEPENDENT REVIEW REQUIRED
S6 Final Reviewed Code Head   : NOT ESTABLISHED
P4-C8 implementation          : COMPLETE — INDEPENDENT REVIEW REQUIRED
P4-C8                         : NOT CLOSED
P4-C9                         : NOT STARTED
Phase 4                       : NOT CLOSED
```

下一步：P4-C8 S6 FINAL INDEPENDENT CLOSURE REVIEW（范围 `78f92c8..<S6 Docs Head>`，并对 E0..S6 做闭合审计）。
