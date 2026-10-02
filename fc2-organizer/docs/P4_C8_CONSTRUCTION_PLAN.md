# P4-C8 施工计划（Construction Plan）-- 批量编排 / 预览 / 重试

```text
Phase          = 4
Package        = P4-C8 Batch Orchestration / Preview / Retry（fc2_organizer.orchestration）
Frozen Base    = 586f92f9b96576dbd71c005a6c95b6e7e52210f4（P4-C7 Final Closure Docs；P4-C7 Final Docs-Only Closure Review PASS）
Branch         = claude/phase4-c8-batch-orchestration
规范合同       = docs/specifications/PHASE4_BATCH_ORCHESTRATION_CONTRACT.md
E0 建立时状态 = P4-C8 E0 ESTABLISHED — INDEPENDENT REVIEW REQUIRED；S1-S6 NOT STARTED（历史快照，非当前状态）
当前状态       = 以合同第 38 节“实现状态”为准
E0-R1          = 闭合 P4-C8-E0-R-01 / R-02 / R-03（批级 BatchOutcome、资源硬限制、S1 治理特例）；closure review：R-01、R-03 CLOSED，R-02 OPEN
E0-R2          = 闭合 P4-C8-E0-R1-01（快照之前的有界条目数门）/ R1-02（lineage 固定预算与多代保留不变量）；REMEDIATED — INDEPENDENT REVIEW REQUIRED
S3-A1          = 施工计划范围修订（只补测试文件范围）：授权 S3 更新 S2 阶段的 API 不存在断言；IMPLEMENTED — INDEPENDENT DOCS REVIEW REQUIRED
S4-A1          = 施工计划范围修订（只补测试文件范围）：授权 S4 更新 S4 之前阶段的 API 不存在断言；IMPLEMENTED — INDEPENDENT DOCS REVIEW REQUIRED
S5-A1          = 施工计划范围修订（只补测试辅助范围）：授权 S5-R1 修正既有确定性投影 helper；IMPLEMENTED — INDEPENDENT DOCS REVIEW REQUIRED
```

S3-A1 修订范围（本计划，只改施工范围，不改合同）：S3 开始前发现，S2 阶段专用的 API 不存在回归测试
（`tests/unit/orchestration/test_orchestration_orchestrator.py` 中的 `test_no_execute_or_retry_api_in_s2`，断言
`BatchOrchestrator` 不存在 `execute`、`preview_retry`、`merge_retry`、`summary`）与合同冻结的 S3 公开方法
`BatchOrchestrator.execute(...)` 必然冲突，而第 0.3 节禁止修改既有测试、S3 的允许改动文件也未列出该文件。本修订只在
第 0.3 节增加第二个精确例外，并在 S3 的允许改动文件中加入该文件及其精确限制；不改变 S1-S6 的功能分工、不改变 S3 的合同
语义、不新增批次、不修改合同。

S4-A1 修订范围（本计划，只改施工范围，不改合同）：S4 开始后发现，S3 阶段留下的 S4 之前阶段 API 不存在回归测试
（`tests/unit/orchestration/test_orchestration_orchestrator.py` 中的 `test_no_retry_or_summary_api_before_s4`，断言
`BatchOrchestrator` 不存在 `preview_retry`、`merge_retry`、`summary`）与合同冻结的 S4 公开方法
`BatchOrchestrator.preview_retry(...)` 必然冲突，而第 0.3 节禁止修改既有测试、S4 的允许改动文件也未列出该文件。本修订只在
第 0.3 节增加第三个精确例外，并在 S4 的允许改动文件中加入该文件及其精确限制；不改变 S1-S6 的功能分工、不改变 S4 的合同
语义（`preview_retry` / `merge_retry` / `RetryKind` / 保留预算 / lineage / checkpoint / 一次性登记 / 公开 API 设计均不变）、
不新增批次、不修改合同。`merge_retry` 是模块级公开函数而不是 `BatchOrchestrator` 的方法，`summary` 属于 S5，因此两者在
类上的不存在断言在 S4 之后继续成立。

S5-A1 修订范围（本计划，只改施工范围，不改合同）：S5 独立 Level 1 复查发现 P4-C8-S5-R-01——合同第 29 节只允许确定性投影
排除六类不确定字段（`preview_id`、`result_id`、`BatchLineage.token`、P4-C7 的 `preflight_id`、`checkpoint_id`、`seal`），而
S1 创建的 `tests/unit/orchestration/_helpers.py` 中的 `_execution_projection` / `projection` 额外丢弃了
`LeftoverTemporary.name`（只保留 `directory_role`）。闭合该 finding 必须**修改**这两个既有 helper，而不仅是追加新 helper；但
第 0.5 节与 S5 的允许改动文件只允许后续批次对 `_fakes.py` / `_helpers.py` 做追加。本修订只在第 0.5 节增加一个精确例外，并在
S5 的允许改动文件中注明该例外；不改变合同（第 29 节排除集合保持上述六类，`LeftoverTemporary.name` **不是**豁免字段，必须
被投影）、不改变 S5 的测试矩阵与门槛、不改变 S1-S6 的功能分工、不新增批次或生产模块。P4-C8-S5-R-02（S5 新增的
`tests/unit/orchestration/test_orchestration_fault_injection.py`）与 P4-C8-S5-R-03（`tests/contract/test_orchestration_architecture.py`）
所涉文件本来就在 S5 的允许改动范围内，不需要额外的施工范围授权。

E0-R2 修订范围（本计划）：E0 表（新增 E0-R2 行）；S1、S2、S3（仅结果预算字段的复制与预算相等检查）、S4、S5、S6 中与有界快照和
多代保留直接相关的条目；最终 integrated gate；附录 A、B。批次分工、治理规则（第 0.4 节）与 BatchOutcome 相关内容不变。

E0-R1 修订范围（本计划）：第 0.4 节状态行规则（S1 特例 + S2-S6 通用模板）；E0 表；S1、S2、S4、S5、S6 的交付 / 测试 /
门槛中与批级结果和资源硬限制直接相关的条目；最终 integrated gate；附录 A、B。S1-S6 的总体功能分工不变，没有新增批次。

本计划在 E0 一次性冻结 P4-C8 的全部施工批次。之后的开发**只能执行本计划**：不得重新设计下一批，不得调整批次边界，
不得把本计划或合同中的任何设计项推迟到“开发时再决定”。凡本计划或合同未写明的实现细节（内部 helper 命名、测试 fixture、
断言写法），由开发者按以下优先级自行裁决，并在该批的 commit message 中记录理由：

```text
1. Frozen Contract   2. no silent source loss   3. overwrite NEVER（委托 P4-C7）   4. fail closed
5. item isolation    6. deterministic           7. bounded concurrency             8. minimal dependency   9. testability
```

## 0. 全局规则（适用于每一批）

### 0.1 Git 纪律

* 每一批开始前验证：`HEAD == origin/claude/phase4-c8-batch-orchestration == 上一批被复查接受的 Head`（S1 的输入是 E0-R1
  或其后续修复轮次被复查接受的 Head，即 E0 Final Accepted Docs Head），工作区干净（只允许未跟踪的 `.claude/`）。
* 禁止 rebase、amend、squash、force push、改写已复查的历史。只追加新提交。
* 每一批结束时 push，并记录 Head SHA。
* 除本计划明确列出的文件外，不得修改任何文件。
* 仓库测试 / 守卫文件是 CRLF；编辑既有测试文件时保持其换行风格（用编辑工具做最小改动，不用脚本整体重写）。

### 0.2 测试命令

```text
<python> -m pytest -q -p no:cacheprovider --basetemp=<job tmp>/pt tests/unit/orchestration tests/contract/test_orchestration_architecture.py
<python> -m pytest -q -p no:cacheprovider --basetemp=<job tmp>/pt tests/contract
<python> -m pytest -q -p no:cacheprovider --basetemp=<job tmp>/pt
git diff --check
git status --porcelain
```

* `<python>` 是开发主机上带 pytest 的解释器（本主机：主 checkout 的 `fc2-organizer/.venv/Scripts/python.exe`）；
  `--basetemp` 与 `-p no:cacheprovider` 在开发主机上是必需的（共享 pytest 临时根目录权限被拒绝），`--basetemp` 的父目录必须事先存在。
  worktree 中直接运行的复现脚本需要 `PYTHONPATH=src`。
* 基线（Frozen Base `586f92f`，E0 实测）：全量 `5227 passed, 40 skipped, 0 failed`；`tests/contract` `177 passed, 0 skipped, 0 failed`。
* 每一批的全量结果必须是 `0 failed`，且 passed 数不得低于上一批；新增 skip 必须逐项说明原因，只允许：主机无 symlink 权限、
  非 Windows 主机上的 junction、非 POSIX 主机上的原生 POSIX 语义。skip 不计为通过。

### 0.3 全局禁止范围

* 不修改 `src/fc2_metadata_core/**`、`src/fc2_organizer/{discovery,planning,publication,nfo,images,materialization,execution}/**`、
  `src/fc2_organizer/__init__.py`、`pyproject.toml`、任何 JSON、`upstream/**`、Amane。
* 不修改已冻结的 Phase 3 合同、P4-C1..P4-C7 合同、`docs/P4_C7_CONSTRUCTION_PLAN.md`、既有 HANDOFF、v1.0 规格书、`CLAUDE.md`。
* 不修改既有测试。例外只有三个：（1）合同第 34.3 节授权、在 S1 执行的六处架构守卫更新；（2）（S3-A1）S3 可以修改
  `tests/unit/orchestration/test_orchestration_orchestrator.py`，唯一允许的内容是把 S2 阶段的 API 不存在断言推进到 S3
  阶段：从断言集合中删除 `"execute"`，`"preview_retry"`、`"merge_retry"`、`"summary"` 继续必须不存在；允许把测试函数名
  `test_no_execute_or_retry_api_in_s2` 改为准确表达 S3 状态的名称（例如 `test_no_retry_or_summary_api_before_s4`）。
  除该函数名与该 tuple 的必要最小变化外，该文件不得有任何其它改动。
  （3）（S4-A1）S4 可以修改同一文件 `tests/unit/orchestration/test_orchestration_orchestrator.py`，唯一允许的语义变化是把
  S4 之前阶段的 API 不存在断言推进到 S4 阶段：从断言集合中删除 `"preview_retry"`，`"merge_retry"`（模块级函数，不是
  `BatchOrchestrator` 的方法）与 `"summary"`（S5）继续必须不存在于 `BatchOrchestrator` 上；允许把测试函数名
  `test_no_retry_or_summary_api_before_s4` 改为准确表达 S4 状态的名称。除该函数名与该 tuple 的必要最小变化外，该文件不得有
  任何其它改动。
* 不新增第三方依赖。
* 不创建 CLI、UI、持久化、诊断输出（JSON / bundle / 日志 / 报告 schema）、Amane adapter 或 P4-C9 / P4-C10 的任何占位文件。
* 生产代码不 import 下层私有模块（合同第 6 节）；测试可以使用下层私有接缝做失败注入（合同第 34.2 节）。
* 测试不访问网络、不读取用户文件、不写入 `tmp_path` 之外的位置；engine 与图片 client 一律使用脚本化内存替身。
* 不要求关闭 Windows Defender 或任何系统安全功能。

### 0.4 每批的 commit 结构

每一批恰好一个代码提交（生产 + 测试 + 允许的守卫更新 + 合同第 38 节状态行），消息格式：

```text
feat(orchestration): <本批标题> (P4-C8 S<n>)

<实现摘要；自行裁决的实现细节及理由；测试数字（目标 / contract / 全量）>

Co-Authored-By: ...
```

S6 另有一个 docs 提交（HANDOFF）。批次内修正缺陷只能作为新提交 `fix(orchestration): ... (P4-C8 S<n>)` 追加并在 message 中说明；
复查 FAIL 后的修复轮次为 `fix(orchestration): ... (P4-C8 S<n>-R<k>)`。

合同第 38 节状态行的更新规则（E0-R1 冻结；除此之外任何批次都不改动合同）：

* **S1 特例（只适用于 S1）**：S1 的输入是 E0-R1（或其后续修复轮次）被独立复查 ACCEPTED 的 Head。S1 的代码提交恰好修改
  第 38 节的两行：
  1. `E0` 行改为 `E0 ACCEPTED / CLOSED — FINAL REVIEWED DOCS HEAD <E0-R1 被接受的 SHA>`（SHA 来自 E0-R1 closure review 结论）；
  2. `S1` 行改为 `S1 IMPLEMENTED — INDEPENDENT REVIEW REQUIRED`；
  并同步第 38 节末尾状态块中与之直接对应的行（`P4-C8 E0` 改为 `ACCEPTED / CLOSED`、`P4-C8 S1 Input` 改为该 SHA、
  `P4-C8 Implementation` 改为 `IN PROGRESS`；三个 E0 finding 行改为 `CLOSED`——仅当 closure review 结论已如此判定）。
  不存在 “S0”：S1 不写、不创建任何 `S0` 行或引用。
* **S2-S6 通用模板（只适用于 S2-S6）**：S<n> 的代码提交把**上一批**的行改为
  `S<n-1> ACCEPTED / CLOSED — FINAL REVIEWED CODE HEAD <sha>`（SHA 来自其独立复查结论），把**本批**的行改为
  `S<n> IMPLEMENTED — INDEPENDENT REVIEW REQUIRED`。
* 任何批次都不得把本批写成 ACCEPTED / CLOSED；复查修复轮次（`S<n>-R<k>`）只更新本批行的文字（例如注明 R<k>），不改动其他行。

### 0.5 通用测试辅助（S1 创建，之后各批只追加）

```text
tests/unit/orchestration/__init__.py
tests/unit/orchestration/_fakes.py
    ScriptedEngine          满足 Phase 3 AggregationEngine 协议：async aggregate(number)；按番号脚本返回
                            真实 AggregationResult（SUCCESS / PARTIAL / FAILED）、抛出普通异常、返回错误类型 / 错误番号；
                            记录调用顺序与并发峰值；可用 asyncio.Event 控制完成顺序（不用 sleep 作为正确性机制）
    ScriptedImageClient     满足 P4-C5 ImageHttpClient 协议：async get(url, *, deadline_seconds, max_redirects, max_bytes)；
                            按 URL 返回 ImageHttpResponse（最小合法 JPEG / 非法内容 / 非 200）或抛出 P4-C5 transport 错误；
                            记录并发峰值；可用事件控制完成顺序
    build_metadata(...)     通过公开 API（NormalizedMetadata、SourceResult、merge_source_results / AggregationResult）
                            构造真实、合法的 metadata 与聚合结果
    minimal_jpeg(...)       通过 P4-C5 校验的最小 JPEG 字节（可按尺寸 / 种子生成不同字节）
tests/unit/orchestration/_helpers.py
    make_media_tree(...)    在 tmp_path 下创建脏下载目录与媒体文件，返回 discover_media(...).items
    tree_snapshot(root)     每个条目的相对路径、类型、字节 SHA-256、st_ino、st_mtime_ns
    mutation_traps(...)     拦截合同第 16 节列出的全部修改性 API + 正向对照
    projection(obj)         合同第 29 节“确定性投影”（去掉 preview_id / result_id / lineage token / preflight_id /
                            checkpoint_id / seal 的逐条元组）
    assert_source_not_lost  源路径或最终路径上至少一个是字节相同的普通文件（可复用 tests.unit.execution._helpers 中的同名 helper）
    fs_fault(...)           经 fc2_organizer.execution._fs._FS / fc2_organizer.materialization.atomic._FS 按路径键控注入故障
                            （线程安全，只命中指定条目的路径）
```

测试辅助只存在于 `tests/**`；生产代码不得 import 它们。

（S5-A1）“之后各批只追加”的唯一精确例外：S5-R1 可以修改 `_helpers.py` 中既有的 `_execution_projection(...)` 与
`projection(...)`（及这两个函数直接相关的 docstring / 注释），唯一目的是使实际确定性投影严格符合合同第 29 节：
`ExecutionResult.leftover_temporaries` 的投影必须同时保留 `directory_role` 与 `name`，不得再静默丢弃
`LeftoverTemporary.name`。合同第 29 节的排除集合不变（仍只有 `preview_id`、`result_id`、`BatchLineage.token`、`preflight_id`、
`checkpoint_id`、`seal`）。本例外不授权修改 preview 投影或 execution 投影的其它字段、issue / preflight 投影、artifact 内容
哈希、plan / metadata / warnings / conflict 字段、retry material 投影，也不授权新增任何忽略字段、归一化、掩码、占位符或
随机值剥离；不授权修改其它任何既有 helper（例如 `FsFault`、`Corpus`、`Lineage`）。若后续确需修改其它既有 helper，开发者
必须再次 STOP；按原规则追加新的 helper 仍然允许。

### 0.6 复查流程（每一批）

* 每一批 push 后停止，等待独立复查（Level 1）：复查范围 = 上一批被接受的 Head .. 本批 Head。
* 复查 PASS（含 PASS WITH NON-BLOCKING NOTES）后，下一批才能开始；FAIL 时只在本批内追加 `S<n>-R<k>` 修复提交，
  复查只针对该轮关闭项 + 回归。
* 任何批次都不得自行宣布 ACCEPTED / CLOSED；只能写 `IMPLEMENTED — INDEPENDENT REVIEW REQUIRED`。

---

## E0 -- Docs-Only Establishment

| 项 | 内容 |
|---|---|
| 输入 | Frozen Base `586f92f9b96576dbd71c005a6c95b6e7e52210f4`（新 branch `claude/phase4-c8-batch-orchestration` 从它建立） |
| 允许改动文件 | `docs/specifications/PHASE4_BATCH_ORCHESTRATION_CONTRACT.md`（新增）、`docs/P4_C8_CONSTRUCTION_PLAN.md`（新增） |
| 禁止范围 | `src/**`、`tests/**`、JSON、`pyproject.toml`、任何其他文档 |
| 交付 | 冻结合同第 1-38 节与本计划 S1-S6 |
| 测试 | 无新增测试；运行 `tests/contract` 与全量一次以证明 docs-only（`177 passed` / `5227 passed, 40 skipped`）；`git diff --check` 干净 |
| 验收标准 | `git diff --name-status 586f92f..HEAD` 恰好两行 `A`；正文简体中文；无未决技术决策；状态为 `P4-C8 E0: ESTABLISHED — INDEPENDENT REVIEW REQUIRED` |
| commit | `docs(orchestration): establish P4-C8 batch orchestration contract and construction plan`（父提交 = Frozen Base） |
| 复查 | P4-C8 E0 Independent Architecture / Contract Review：原始候选 `0f2188f` 结论 FAIL（P4-C8-E0-R-01、R-02、R-03） |

E0-R1（docs-only remediation）：

| 项 | 内容 |
|---|---|
| 输入 / 父提交 | `0f2188f5444b0f7c6293607db0132dae0297ee34` |
| 允许改动文件 | 同上两份文档（只修改，`M`） |
| 交付 | 合同：批级 `BatchOutcome`（第 11.5 节）、资源硬限制（第 19.6 节）及其直接受影响的 API / 错误 / 配置 / 测试章节；本计划：第 0.4 节治理规则与各批直接受影响的条目 |
| 测试 | `tests/contract` 与全量各一次（`177 passed` / `5227 passed, 40 skipped, 0 failed`）；`git diff --check 0f2188f..HEAD` 干净 |
| 验收标准 | `git diff --name-status 0f2188f..HEAD` 恰好两行 `M`；其余已 PASS 的设计不变；三个 finding 状态为 `REMEDIATED — REVIEW REQUIRED` |
| commit | `docs(orchestration): close P4-C8 E0 architecture findings (P4-C8 E0-R1)` |
| 复查 | P4-C8 E0-R1 Incremental Architecture / Contract Closure Review：R-01、R-03 CLOSED；R-02 仍 OPEN（新 finding P4-C8-E0-R1-01、R1-02）；E0-R1 Head `fe12d1d` 不成为 S1 输入 |

E0-R2（docs-only resource model remediation）：

| 项 | 内容 |
|---|---|
| 输入 / 父提交 | `fe12d1d1833b12925c13916bc477ea5e7424aec4` |
| 允许改动文件 | 同上两份文档（只修改，`M`） |
| 交付 | 合同：有界快照算法（第 8、19.6.1 节）、lineage 固定预算与多代保留不变量（第 10.4、10.7、18.1、19.6.2、19.6.6-19.6.10、25.4、26 节）、测试矩阵与门槛（第 35、35.1、35.1.1 节）；本计划：各批直接受影响的条目 |
| 测试 | `tests/contract` 与全量各一次（`177 passed` / `5227 passed, 40 skipped, 0 failed`）；`git diff --check fe12d1d..HEAD` 干净 |
| 验收标准 | `git diff --name-status fe12d1d..HEAD` 恰好两行 `M`；R-01、R-03 相关语义不变；资源常量数值不变；三个资源 finding 状态为 `REMEDIATED — REVIEW REQUIRED` |
| commit | `docs(orchestration): bound P4-C8 input and multi-generation retention (P4-C8 E0-R2)` |
| 复查 | P4-C8 E0-R2 Incremental Resource Architecture Closure Review；PASS 后该 E0-R2 Head 成为 E0 Final Accepted Docs Head 与 S1 输入（第 0.4 节 S1 特例写入该 SHA） |

---

## S1 -- Foundation：models / config / cancellation / consumption / recognition / 架构守卫

### 输入

E0-R1（或其后续修复轮次）被独立复查 ACCEPTED 的 Head（E0 Final Accepted Docs Head）；合同第 4-14（含 11.5）、19.6.1、
20.1、25.1、34 节。

### 允许改动文件

新增：

```text
src/fc2_organizer/orchestration/__init__.py
src/fc2_organizer/orchestration/errors.py
src/fc2_organizer/orchestration/models.py
src/fc2_organizer/orchestration/cancellation.py
src/fc2_organizer/orchestration/_consumption.py
src/fc2_organizer/orchestration/recognition.py
tests/contract/test_orchestration_architecture.py
tests/unit/orchestration/__init__.py
tests/unit/orchestration/_fakes.py
tests/unit/orchestration/_helpers.py
tests/unit/orchestration/test_orchestration_errors.py
tests/unit/orchestration/test_orchestration_config.py
tests/unit/orchestration/test_orchestration_models.py
tests/unit/orchestration/test_orchestration_retry_kind_table.py
tests/unit/orchestration/test_orchestration_cancellation_token.py
tests/unit/orchestration/test_orchestration_consumption.py
tests/unit/orchestration/test_orchestration_recognition.py
tests/unit/orchestration/test_orchestration_batch_outcome.py
```

修改（合同第 34.3 节授权的最小守卫更新，每处只改所列内容）：

```text
tests/contract/test_discovery_architecture.py       顶层 package 集合 + "orchestration"（一行）
tests/contract/test_planning_architecture.py        顶层 package 集合 + "orchestration"（一行）
tests/contract/test_publication_architecture.py     顶层 package 集合 + "orchestration"（一行）
tests/contract/test_nfo_architecture.py             顶层 package 集合 + "orchestration"（一行）
tests/contract/test_execution_architecture.py       反向依赖守卫豁免 orchestration 目录；新增 test_orchestration_consumes_only_the_bare_execution_package
tests/contract/test_materialization_architecture.py 反向依赖守卫豁免 orchestration 目录；新增 test_orchestration_consumes_only_bare_materialization_and_mapping
合同第 38 节 E0 状态行 + S1 状态行（及末尾状态块中对应行），按第 0.4 节 S1 特例
```

### 禁止范围

`stages.py`、`preview.py`、`execute.py`、`retry.py`、`orchestrator.py`（后续批次创建）；任何网络 / 文件系统访问；summary 模型（S5）；
创建或引用任何 `S0` 状态行。

### 接口范围（本批导出）

`OrchestrationConfig`、`CancellationToken`、`BatchPreview`、`ItemPreview`、`PreviewState`、`BatchExecutionResult`、`ItemExecution`、
`ExecutionDisposition`、`BatchOutcome`、`RetryMaterial`、`RetryKind`、`OrchestrationStage`、`IssueReason`、`ItemIssue`、`ItemWarning`、
`ResourceLimitReason`、八个常量（`DEFAULT_IMAGE_IN_FLIGHT_ITEMS`、`MAX_IMAGE_IN_FLIGHT_ITEMS`、`DEFAULT_FILESYSTEM_WORKERS`、
`MAX_FILESYSTEM_WORKERS`、`MAX_BATCH_ITEMS`、`MAX_ITEM_IMAGE_BYTES`、`DEFAULT_MAX_RETAINED_ARTIFACT_BYTES`、
`MAX_RETAINED_ARTIFACT_BYTES_LIMIT`）、九个错误类（含 `OrchestrationResourceLimitError`）。

### 实现要求

1. `errors.py`：合同第 7.4 节层次（含 `OrchestrationResourceLimitError` 与其 `.reason`、固定消息格式）；固定措辞；
   只 import `__future__`（`ResourceLimitReason` 由 `models.py` 定义；`errors.py` 只保存传入的 reason 对象，不 import models）。
2. `models.py`：
   * 第 10.1 节全部枚举（成员名与值逐字一致，含 `BatchOutcome`、`ResourceLimitReason`）；
   * `OrchestrationConfig`（第 9 节，含 `max_retained_artifact_bytes`）与第 9 节全部常量；
   * `BatchExecutionResult.outcome`：第 11.5 节算法的只读派生属性（不存储字段）；
   * （E0-R2）`BatchPreview` / `BatchExecutionResult` 的 `retention_budget_bytes` / `retry_budget_bytes` 字段；保留载荷计量
     helper `retry_payload_bytes(material)` 与派生属性 `retained_retry_payload_bytes`（结果）、`retained_artifact_bytes`
     （preview）；第 10.4、10.7 节的预算范围与保留不变量（主结果 / 合并结果 `<= retention_budget_bytes`，重试轮结果与重试
     preview `<= retry_budget_bytes`）；
   * `ItemIssue` 与第 10.2 节组合表（逐行强制）；
   * `ItemPreview`、`BatchPreview`、`RetryMaterial`、`ItemExecution`、`BatchExecutionResult` 与第 10.3-10.7 节全部不变量、
     派生显示属性、三种结果形态；`preview_id` / `result_id` 只能是 32 位小写 hex，`repr=False`；
   * `ItemExecution.retry_kind`：第 25.1 节判定表（纯函数）；`retry_material` 与 `retry_kind` 的对应关系；
   * 类名提取 helper（第 8 节全函数规则）与“按严格类型读取 `.reason`”helper（第 8 节）；
   * 违规一律 `OrchestrationContractError`，消息不含路径 / 标题。
3. `cancellation.py`：第 10.8 节；只 import `__future__`、`threading`。
4. `_consumption.py`：三个进程内一次性登记表（preview 执行、结果重试、重试结果合并），各自一个 `threading.Lock` 保护的
   `set[str]`，提供原子的 check-and-register 与只读查询；不导出；不持久化。
5. `recognition.py`：输入容器种类校验；（E0-R2）唯一的有界快照 helper `bounded_snapshot(items)`，严格按合同第 19.6.1 节
   算法（`iter` 一次、至多收集 `MAX_BATCH_ITEMS` 个引用、恰好一次溢出探测、溢出即 `OrchestrationResourceLimitError
   (BATCH_ITEM_LIMIT)`、迭代普通异常 -> `OrchestrationInputError`、从不调用 `len(items)` / `tuple(items)` / `list(items)`）；
   其后逐元素严格类型校验（第 8 节优先级，至多 10 个下标 + 总数）；番号识别（第 14.1 节，
   `os.path.basename` + `normalize_fc2_number`）；Phase A 冲突分组（第 14.2 节，输出按 index 升序，`conflict_with` 为升序并集，
   同源优先）。纯函数，零网络、零文件系统。
6. 架构测试（第 34.1 节中适用于本批模块的全部条目，模块集合 = 本批六个模块）与六处守卫更新（第 34.3 节）。

### 测试矩阵

| 文件 | 覆盖 |
|---|---|
| `test_orchestration_errors.py` | 层次与基类；消息固定、不含敏感文本；不链接；`OrchestrationResourceLimitError` 的 `.reason` 与两种固定消息 |
| `test_orchestration_config.py` | 默认值；范围边界（0 / 1 / 上限 / 上限 + 1）；`bool`、`float`、`int` 子类、`BatchConfig` 子类被拒绝；不可变；`max_retained_artifact_bytes` 的 0 / 1 / `MAX_RETAINED_ARTIFACT_BYTES_LIMIT` / 上限 + 1 / `bool`；八个常量的冻结值（`MAX_BATCH_ITEMS == 2000 >= 500`、`MAX_ITEM_IMAGE_BYTES == 64 MiB`、默认 2 GiB、上限 16 GiB） |
| `test_orchestration_batch_outcome.py` | 合同第 11.5 节真值表逐行：每种条目类别单独成批、“全部为某类”九种、空结果、`S` 与每种非 `S` 类混合、`P` 与每种类别混合、`ABORTED` 与 `S` 混合；三种结果形态；纯函数（重复求值相等、相同条目序列的不同结果对象相等）；`outcome` 不是 dataclass 字段 |
| `test_orchestration_models.py` | 第 10.2 节组合表逐行正反例；`ItemPreview` / `BatchPreview` / `ItemExecution` / `BatchExecutionResult` 每条不变量一正一反；显示属性（有 / 无 plan、有 / 无 preflight、manifest 缺 poster 等）；三种结果形态互斥；`object.__setattr__` 改写后的对象能被第 18.1 节第 3 步重新检查识别（提供 `revalidate()` 形式的内部校验入口并测试）；类名提取对恶意 metaclass / `__name__` / 非标识符 / 超长名称返回 `"UnknownType"` 且不运行其代码 |
| `test_orchestration_retry_kind_table.py` | 第 25.1 节判定表逐行（含 `PREFLIGHT_REJECTED`、`CHECKPOINT_REJECTED`、冲突 -> `NONE`）；`retry_material` 存在性与 checkpoint 身份规则 |
| `test_orchestration_cancellation_token.py` | 单向、幂等；多线程并发 `cancel()` / 读取；不是 asyncio 取消 |
| `test_orchestration_consumption.py` | 每个登记表：首次登记成功、重复登记失败；多线程竞争恰好一个成功；查询不登记 |
| `test_orchestration_recognition.py` | 容器规则（list / tuple 接受；str / bytes / set / frozenset / dict / 生成器 / 迭代器 / `None` 拒绝）；元素严格类型（子类、钩子零调用）；快照；空输入；Phase 1 语法用例（`FC2-PPV-1234567`、`FC2PPV1234567`、`[广告]FC2PPV-1234567.mp4`、`xxx@FC2PPV-1234567.mkv`、无番号、父目录有番号而文件名无番号 -> 不识别、两个番号取第一个）；Phase A：同番号不同文件、同一对象两次、Windows 大小写不同的同一路径（仅 `os.name == "nt"`）、三方组、同时属于同源与同目标组、`conflict_with` 升序并集；条目数：`MAX_BATCH_ITEMS` 个（直接构造的极小 `DiscoveredMediaItem`，不申请大内存）接受、`MAX_BATCH_ITEMS + 1` -> `OrchestrationResourceLimitError(BATCH_ITEM_LIMIT)` 且先于元素校验；（E0-R2）合同第 35 节 “bounded snapshot” 行 A-H 全部（计数型自定义 `Sequence`：读取元素数、`next` 调用数、`__len__` 调用 0 次、惰性声称 1 000 000 个元素只读取 2001 个、说谎长度序列、超限优先于元素非法、迭代异常映射），不能只用普通 2001 元素 list 证明 |
| `test_orchestration_models.py`（E0-R2 追加） | `retention_budget_bytes` 范围（0 / 1 / 上限 / 上限 + 1 / `bool`）；`retry_budget_bytes` 与形态的对应；`retry_payload_bytes` / `retained_retry_payload_bytes` / `retained_artifact_bytes` 的精确值（含共享 bytes 按引用重复计入、`SUCCESS` / `ABORTED` / `NONE` / `METADATA_REFETCH` 贡献 0）；主结果保留载荷恰好 `B` 接受、`B + 1` -> `OrchestrationContractError`；合并结果同；重试轮结果以 `retry_budget_bytes` 为界 |
| `test_orchestration_architecture.py` | 第 34.1 节适用条目（含 E0-R1 资源常量 / `outcome` 规则）；本批公开导出集合精确相等；六处守卫更新后的既有测试全部通过 |

### 验收标准（gate）

* 目标测试、`tests/contract`、全量均 `0 failed`；全量 passed 数高于基线 `5227`。
* 新 package 的静态扫描：零私有下层模块引用、零文件系统 / 网络 / 持久化 import。
* 既有测试除六处授权守卫外零改动（`git diff --name-status` 核对）。
* 合同只改动第 38 节 E0 行、S1 行及末尾状态块对应行（第 0.4 节 S1 特例）；没有 `S0`。
* `git diff --check` 干净。

### commit

`feat(orchestration): add P4-C8 foundation models, recognition and architecture guards (P4-C8 S1)`

### 复查

S1 Independent Review（范围 E0 Final Accepted Docs Head..S1 Head）；重点另含：`BatchOutcome` 真值表、资源常量与条目数上限、
S1 治理特例的执行；重点：模型不变量完整性、`ItemIssue` 组合表、`retry_kind` 表、守卫更新的最小性。

---

## S2 -- Preview composition：stages / preview / orchestrator.preview

### 输入

S1 被接受的 Head；合同第 7.2、7.3、12-17、19.1、19.2、19.6、20.2、21、22 节。

### 允许改动文件

新增：

```text
src/fc2_organizer/orchestration/stages.py
src/fc2_organizer/orchestration/preview.py
src/fc2_organizer/orchestration/orchestrator.py
tests/unit/orchestration/test_orchestration_orchestrator.py
tests/unit/orchestration/test_orchestration_stages.py
tests/unit/orchestration/test_orchestration_preview.py
tests/unit/orchestration/test_orchestration_preview_no_mutation.py
tests/unit/orchestration/test_orchestration_preview_concurrency.py
tests/unit/orchestration/test_orchestration_preview_fatal.py
tests/unit/orchestration/test_orchestration_preview_resources.py
```

修改：

```text
src/fc2_organizer/orchestration/__init__.py       + BatchOrchestrator
tests/contract/test_orchestration_architecture.py（追加：模块集合、stages / preview / orchestrator 的逐模块规则、结构性零修改）
tests/unit/orchestration/_fakes.py、_helpers.py（追加）
合同第 38 节 S1 / S2 状态行
```

### 禁止范围

`execute_filesystem` 的任何引用；`execute.py`、`retry.py`；线程；任何文件系统修改；summary（S5）。

### 接口范围

`BatchOrchestrator(engine, image_client, library_root, *, output_policy=None, image_policy=None, config=None)`、
只读属性、`async preview(items) -> BatchPreview`。`execute` / `preview_retry` 在本批**不存在**（不得提供占位实现）。

### 实现要求

1. `orchestrator.py`：构造校验（第 7.2 节；`BatchConfigError` 翻译为 `OrchestrationConfigError`，不链接；E0-R1：解析后的
   `image_policy.max_total_bytes > MAX_ITEM_IMAGE_BYTES` -> `OrchestrationConfigError`）；构造一个复用的
   `BatchScheduler`；忙碌守卫（第 7.3 节，`threading.Lock` + 标志，busy-first，`finally` 释放）；`preview` 委托 `preview.py`。
2. `stages.py`：第 15.2 节六个阶段各一个同步函数，返回“成功产物或 `ItemIssue`”；普通 `Exception` -> 对应原因
   （`error_type` 用 S1 的类名 helper，`detail` 用 S1 的 `.reason` helper）；非 `Exception` 的 `BaseException` 不捕获；
   Phase B 冲突（第 14.3 节）纯函数。
3. `preview.py`：第 15.1 节九步顺序；metadata 阶段只调用 `scheduler.run(numbers)`（即使为空）；第 11.3 节映射；图片阶段
   `min(K, n)` 个 worker（第 19.2 节，准入检查 `stopping` 与驱动任务的新取消请求；私有、不读取元数据的致命载体；
   `asyncio.TaskGroup`）；第 5、7 步同步内联；组装 generation 0 的 `BatchPreview`。
4. （E0-R1；E0-R2 补充）`preview.py` 中调用局部的保留预算账本（合同第 19.6.2-19.6.6 节；账本上限作为参数传入，主 preview
   传入 `config.max_retained_artifact_bytes` 并把它写入 `BatchPreview.retention_budget_bytes`，S4 的 `preview_retry` 传入
   `available_retry_budget`）：第 5 步每个 NFO 立即计入 `4 * len(nfo_text)`；
   第 6 步经串行化准入门（`asyncio.Condition`）按 index 升序预约 `R`、完成时转为实际 `images.total_bytes`；无进行中调用仍不满足
   -> 停止准入、取消并 await 全部 worker、抛出 `OrchestrationResourceLimitError(RETAINED_BYTES_LIMIT)`；`total_bytes > R` 的违约
   结果按第 19.6.4 节处理；账本对象可由测试替身只读观测（私有属性，不导出）。preview 的其余语义（第 15-17 节）不变。
5. 公开 `BatchOrchestrator` 之后，`__init__` 导出集合 = S1 集合 + `BatchOrchestrator`。

### 测试矩阵

| 文件 | 覆盖 |
|---|---|
| `test_orchestration_orchestrator.py` | 构造：engine 同步 `aggregate` / 无 `aggregate` / image client 无 `get` / 非法 `library_root` 类型 / 策略子类 / 非法 config -> `OrchestrationConfigError`；构造零网络零文件系统；busy-first：preview 进行中时第二次 `preview`（合法 / 非法 / 空参数）一律 `OrchestrationBusyError`，被拒绝调用不释放占用；非法参数在空闲 orchestrator 上抛 `OrchestrationInputError` 且保持空闲；回归测试在守卫失效时不挂起（看门狗 + 对照实现，同 Phase 3 C4-R1-04 形态） |
| `test_orchestration_stages.py` | 每个阶段：成功；下层冻结错误 -> 对应原因、`error_type`、`detail`；普通外来异常 -> 同一原因；`BaseException` 原样传播；`ArtifactMappingError.reason` / `PlanGraphError.reason` 被读取为 `detail`；恶意元数据异常不运行其代码；Phase B：hardlink（同 inode 不同名）、同目标、组合、覆盖 `PREFLIGHT_BLOCKED` |
| `test_orchestration_preview.py` | 端到端（真实 `discover_media`、`tmp_path`、脚本化 engine / client、真实 P4-C7 preflight）：READY 条目的第 15.4 节全部信息与 plan / manifest 一致；每个阶段的失败各一例（番号、冲突 A / B、metadata 两种、planning（非法 `OutputPolicy` 组件、非法 library_root）、publication（替身制造身份不符）、NFO（非法 release）、图片（伪造集合）、manifest、preflight 阻断（目标已存在、library root 不存在 / 是 junction、源被删除）、preflight 拒绝（`SOURCE_INSIDE_TARGET`））；NFO 失败的条目图片请求数为 0；冲突条目 metadata 调用数为 0；图片部分获取：第 22.2 节表逐行；警告顺序；空批次；输出 index 顺序 |
| `test_orchestration_preview_no_mutation.py` | 第 16 节：全部修改性 API 拦截（含 `execute_filesystem` / `materialize_*`）命中 0 次 + 正向对照证明拦截有效 + 前后树快照相等；覆盖 READY / 阻断 / 冲突 / 各阶段失败混合的批次 |
| `test_orchestration_preview_concurrency.py` | metadata 峰值 ≤ M 且足够条目时 == M；图片峰值 ≤ K 且 == K；`K = 1` 严格串行；存活图片任务 `O(K)`（对照：朴素“每条一任务”实现被检测出）；以事件反转 engine / 图片完成顺序后确定性投影相等 |
| `test_orchestration_preview_fatal.py` | 调用方取消（metadata 阶段、图片阶段）：`CancelledError` 传播、worker 被 await、无孤儿任务、零修改；engine / 图片 client / 同步阶段抛出 `KeyboardInterrupt`、`SystemExit`、`GeneratorExit`、自定义 `BaseException`、自行 `CancelledError` -> 原始对象（身份）、不返回 preview、此后不再准入、orchestrator 恢复空闲；恶意元数据致命异常不被读取 |
| `test_orchestration_preview_resources.py`（E0-R1） | 合同第 35 节 “resource limits” 行中适用于 preview 的全部条目：构造时 `image_policy.max_total_bytes` 等于 / 超过 `MAX_ITEM_IMAGE_BYTES`；`MAX_BATCH_ITEMS` / `+ 1` 经 `preview` 端到端（engine / client 调用 0 次、零修改）；小预算 `B_exact` 接受、`B_exact - 1` -> `RETAINED_BYTES_LIMIT`；NFO 计量超限时图片请求 0 次；`K = 4` 而 `B` 只容纳 2 个预约时峰值 `<= 2`、观测账本始终 `<= B`；失败 index 在反转完成顺序与 `K ∈ {1, 2, 4}` 下相同；无进行中调用时立即失败（不挂起，看门狗）；违约替身 `total_bytes > R` -> `IMAGE_ACQUISITION_ERROR`；超限后不返回 preview、orchestrator 恢复空闲、错误不链接且消息不含路径 / URL；全部使用小配置，不申请大内存 |

### 验收标准（gate）

* 目标 / contract / 全量 `0 failed`，passed 数不低于 S1。
* （E0-R1）资源测试全部通过：条目数与字节预算边界精确、预约准入下账本从不超过 `B`、结论与完成顺序无关。
* 零修改测试：拦截命中 0、正向对照命中 > 0、树快照相等。
* 结构性：`execute_filesystem` / `materialize_*` 名称在 package 中出现 0 次（S2 尚无 `execute.py`）。
* 并发峰值与对照测试通过。

### commit

`feat(orchestration): add read-only batch preview composition (P4-C8 S2)`

### 复查

S2 Independent Review（范围 S1 Head..S2 Head）；重点：零修改证明、阶段映射、冲突两阶段、有界图片 worker、致命边界。

---

## S3 -- Execution orchestration：execute / selection / 取消 / 致命排空

### 输入

S2 被接受的 Head；合同第 17-20、23、24、27、31 节。

### 允许改动文件

新增：

```text
src/fc2_organizer/orchestration/execute.py
tests/unit/orchestration/test_orchestration_execute.py
tests/unit/orchestration/test_orchestration_execute_concurrency.py
tests/unit/orchestration/test_orchestration_execute_cancellation.py
tests/unit/orchestration/test_orchestration_execute_fatal.py
```

修改：

```text
src/fc2_organizer/orchestration/orchestrator.py   + execute(preview, *, selection=None, cancel=None)
tests/contract/test_orchestration_architecture.py（追加：execute.py 规则、execute_filesystem 唯一出现位置、threading.Thread 唯一出现位置）
tests/unit/orchestration/_fakes.py、_helpers.py（追加）
tests/unit/orchestration/test_orchestration_orchestrator.py（S3-A1：仅更新 S2 阶段的 API 不存在断言，见下）
合同第 38 节 S2 / S3 状态行
```

（S3-A1）`test_orchestration_orchestrator.py` 的唯一允许改动：从 S2 阶段 API 不存在断言的集合中删除 `"execute"`，
`preview_retry`、`merge_retry`、`summary` 继续必须不存在（可按第 0.3 节例外 2 改测试函数名）。不得修改该文件中的构造测试、
busy-first 测试、钩子安全测试、partial 测试、资源测试或其它任何 S1 / S2 回归测试。

### 禁止范围

`retry.py`、`preview_retry`、`merge_retry`；在执行前重新 preflight；任何直接文件系统访问；中断进行中的条目；线程池 / 每条目线程；
summary（S5）。

### 接口范围

`BatchOrchestrator.execute(preview, *, selection=None, cancel=None) -> BatchExecutionResult`（同步）。

### 实现要求

1. 第 18.1 节九步顺序（busy-first、类型、完整性重新检查、配置相等、cancel、selection、`preview_id` 原子登记、执行、组装）。
2. 第 18.2 节逐条 disposition 表：`REJECTED` 只针对六种精确类型；其余普通异常 / 非法返回 -> `ABORTED`；`issue` 按第 10.6 节；
   `retry_material` 按第 25.1 节（本批只需产生，重试在 S4）。
3. 第 19.3 节：`W_eff <= 1` 内联；否则恰好 `W_eff` 个非 daemon 线程，锁保护的共享游标，index 升序准入，准入前检查
   `stopping` / `cancel.cancelled`，全部 `join`。
4. 第 20.3 节致命排空：第一个致命对象被持有（不读取元数据），停止准入，`join` 全部线程，原样重新抛出；调用线程等待期间的
   `KeyboardInterrupt` / `SystemExit` 同样排空后重新抛出；不返回部分结果。
5. 第 27.2 节取消：未准入的被选中条目 -> `CANCELLED`；已准入条目运行到结束；正常返回完整结果。
6. 生成主结果（generation 0）或重试轮结果（S4 才会传入重试 preview；本批按 `BatchPreview` 的形态照常组装，测试只覆盖主 preview）。
7. （E0-R2）第 18.1 节第 4 步包含 `preview.retention_budget_bytes == config.max_retained_artifact_bytes`；组装结果时把 preview 的
   `retention_budget_bytes`（及重试 preview 的 `retry_budget_bytes`）原样复制到结果，`RetryMaterial.artifacts` 使用 preview
   preflight 中的同一 tuple（不复制载荷）；测试（`test_orchestration_execute.py`）覆盖预算不相等 -> `OrchestrationInputError`、
   主结果保留载荷 `<=` preview 保留载荷。

### 测试矩阵

| 文件 | 覆盖 |
|---|---|
| `test_orchestration_execute.py` | 全部 READY 执行 -> 真实 P4-C7 `SUCCESS`，最终目录精确、字节、源不存在；8 种主图组合 × extrafanart {0, 1, 13}；selection：`None` / 子集 / `()` / 非 READY index / 重复 / 未排序 / 越界 / `bool` / 列表 -> 规则；未 ready 条目永不传给 `execute_filesystem`（替身计数）；同一 preview 第二次 `execute` -> `OrchestrationConsumedError` 且零 `execute_filesystem` 调用；配置不一致 -> `OrchestrationInputError`；改写 preview 对象图（换 preflight、换 plan、`object.__setattr__`）-> `OrchestrationIntegrityError`，零执行；经 `_FS` 注入：U1 前失败 -> `EXECUTED` + `FAILED` + `EXECUTION_FAILED` + `FRESH_REEXECUTE`；U1 后失败 -> `PARTIAL` + `RESUME` + checkpoint 身份；六种 pre-FS 类型化错误（通过篡改 / 预先消费 preflight 真实触发）-> `REJECTED`、零 effect；外来异常（`_FS` 注入 `RuntimeError`）-> `ABORTED`；每次注入后 `assert_source_not_lost`；`LEFTOVER_TEMPORARIES` 警告；`issue.detail == execution.failure.kind` |
| `test_orchestration_execute_concurrency.py` | `W ∈ {1, 2, 4, 8}`：峰值 ≤ W 且足够条目时 == W（测试替身包装真实 `execute_filesystem`，事件同步）；线程数 == `min(W, n)`，`W_eff == 1` 时不创建线程；对照：朴素“每条目一线程”实现被检测出；完成顺序反转时结果投影相等；并发执行的不同条目全部 `SUCCESS` 且目标互不干扰 |
| `test_orchestration_execute_cancellation.py` | 开始前取消 -> 全部 `CANCELLED`、零执行、preview 已消费；`W = 1` 在第 k 条准入后取消 -> 恰好前 k 条执行、其余 `CANCELLED`（后缀）；`W > 1` 取消 -> 进行中条目完成（结果与 checkpoint 保留）、之后零准入；已进入 `execute_filesystem` 的条目从不被中断（替身阻塞期间取消，放行后其结果为 `EXECUTED`）；取消后返回完整结果；`CANCELLED` 的 `retry_kind == DEFERRED` 且 `retry_material` 保留 |
| `test_orchestration_execute_fatal.py` | 条目线程中的 `KeyboardInterrupt` / `SystemExit` / `GeneratorExit` / 自定义 `BaseException`：其他进行中条目完成、全部线程被 `join`（无存活线程）、原始对象（身份）传播、无结果、preview 已消费、无后续准入；调用线程等待期间收到 `KeyboardInterrupt`（替身在主线程触发）：同样排空后传播；内联模式直接传播；恶意元数据致命异常不被读取；致命后 orchestrator 恢复空闲；每例 `assert_source_not_lost` |

### 验收标准（gate）

* 目标 / contract / 全量 `0 failed`，passed 数不低于 S2。
* `execute_filesystem` 只在 `execute.py` 中出现，且每个被准入条目恰好调用一次（替身计数）。
* 并发峰值、线程数、取消后缀性质、致命排空（无存活线程）全部通过。

### commit

`feat(orchestration): add bounded batch execution with cooperative cancellation (P4-C8 S3)`

### 复查

S3 Independent Review（范围 S2 Head..S3 Head）；重点：`REJECTED` / `ABORTED` 划分、线程有界与排空、取消不中断、preview 一次性消费。

---

## S4 -- Retry：preview_retry / merge_retry

### 输入

S3 被接受的 Head；合同第 12.2、12.3、19.6.7、19.6.10、24-26、35.1.1 节。

### 允许改动文件

新增：

```text
src/fc2_organizer/orchestration/retry.py
tests/unit/orchestration/test_orchestration_preview_retry.py
tests/unit/orchestration/test_orchestration_merge.py
tests/unit/orchestration/test_orchestration_retry_chain.py
tests/unit/orchestration/test_orchestration_retention.py
```

修改：

```text
src/fc2_organizer/orchestration/orchestrator.py   + async preview_retry(previous, *, scope=None)
src/fc2_organizer/orchestration/__init__.py       + merge_retry
tests/contract/test_orchestration_architecture.py（追加：retry.py 规则）
tests/unit/orchestration/_fakes.py、_helpers.py（追加）
tests/unit/orchestration/test_orchestration_orchestrator.py（S4-A1：仅更新 S4 之前阶段的 API 不存在断言，见下）
合同第 38 节 S3 / S4 状态行
```

（S4-A1）`test_orchestration_orchestrator.py` 的唯一允许改动：把 `test_no_retry_or_summary_api_before_s4` 推进到 S4 阶段边界，
从其断言集合中删除 `"preview_retry"`，`"merge_retry"` 与 `"summary"` 继续必须不存在于 `BatchOrchestrator` 上（可按第 0.3 节
例外 3 改测试函数名）。不得修改该文件中的构造测试、busy-first 测试、钩子安全测试、partial 测试、资源测试、preview / execute
测试或其它任何 S1 / S2 / S3 回归测试。

### 禁止范围

修改 `RetryKind` 判定表（S1 已冻结）；在重试中重新获取保留材料条目的 metadata / 图片；任何直接文件系统访问；自动合并；
summary（S5）。

### 接口范围

`BatchOrchestrator.preview_retry(previous, *, scope=None) -> BatchPreview`（async）、`merge_retry(previous, retry) -> BatchExecutionResult`。

### 实现要求

1. （E0-R2）第 25.4 节第 4 步的 lineage 预算相等检查；第 7a 步按合同第 19.6.7 节计算 `base_retained`（只计 index 不在本轮
   `R` 中、持有 `RetryMaterial` 的 previous 条目）与 `available_retry_budget = B - base_retained`（`< 0` ->
   `OrchestrationIntegrityError`），并以它作为本轮账本上限（`preview.py` 账本参数）；返回的重试 preview 携带
   `retention_budget_bytes = B`、`retry_budget_bytes = available_retry_budget`。
   第 25.4 节顺序（含 E0-R1 第 7a 步：按合同第 19.6.7 节计入保留材料字节，超限 -> `OrchestrationResourceLimitError`、不登记
   previous；`METADATA_REFETCH` 恢复的条目复用 `preview.py` 的账本与准入门）；登记在最后（原子 check-and-register；已登记则丢弃
   产物并抛 `OrchestrationConsumedError`）。
2. 第 25.3 节 metadata 重试：`scheduler.retry_failed` + `apply_retry`；`retry.indices` 与 `METADATA_REFETCH` 条目位置集合的一致性检查；
   对恢复的条目从 PLANNING 重新执行第 15.2 节阶段（复用 `preview.py` 的图片阶段与组合 helper）。
3. 保留材料条目：按第 25.1 节表调用 `preflight_execution(plan, artifacts, checkpoint=...)`（经 `stages.py`）；
   `CheckpointError` -> `CHECKPOINT_REJECTED`；其余异常 -> `PREFLIGHT_REJECTED`；`ready is False` -> `PREFLIGHT_BLOCKED`。
4. Phase B 冲突在重试子集内执行。
5. `merge_retry`：第 26 节步骤（含 E0-R2 第 9a 步预算一致、第 9b 步合并后保留载荷 `<= B`，二者都在登记之前，失败不登记）；
   一次性合并登记；未重试条目保持同一对象；不复制任何载荷；合并结果 `retention_budget_bytes = B`、`retry_budget_bytes = None`。
6. `execute` 对重试 preview 生成重试轮结果（第 10.7 节形态）。

### 测试矩阵

| 文件 | 覆盖 |
|---|---|
| `test_orchestration_preview_retry.py` | 五种 `RetryKind` 各自的 preview_retry 产物（retry_origin、preflight mode：`RESUME` 为 RESUME 模式、其余为 FRESH / 原 checkpoint）；scope：`None`（解析后存储）、单一种类、组合、空集合、含 `NONE` / 非 frozenset / 子类 -> `OrchestrationInputError`；`previous` 非完整结果（重试轮结果）-> `OrchestrationInputError`；配置不一致；从同一结果第二次 `preview_retry` -> `OrchestrationConsumedError`；preview_retry 中途致命 / 取消后同一结果仍可重试（登记在最后）；零修改（第 16 节拦截 + 树快照）；metadata 重试一致性被破坏（伪造账本）-> `OrchestrationIntegrityError`；保留材料条目零网络调用（engine / client 计数为 0）；D 类：已消费 checkpoint -> `CHECKPOINT_REJECTED`（`detail CONSUMED`）且之后 `NONE`；（E0-R1；E0-R2 修订）保留材料计量：以 `available_retry_budget` 为上限，恰好容纳时接受、多 1 字节 -> `RETAINED_BYTES_LIMIT`、previous 未被登记、checkpoint 未被消费、改变重试范围（降低 `base_retained`）后可再次 `preview_retry`；预算不同的 orchestrator -> `OrchestrationInputError`（lineage 预算固定，不能以更大预算绕过）；`METADATA_REFETCH` 条目的 NFO / 图片计量与 preview 相同；重试轮结果与合并结果的 `outcome` 与合同第 11.5 节一致；（E0-R2）`base_retained` 只计 index 不在 `R` 中的条目（`R` 中旧材料不计入）、篡改 previous 使 `available < 0` -> `OrchestrationIntegrityError` |
| `test_orchestration_retention.py`（E0-R2） | 合同第 35 节 “result retention” 行 C-I 与第 35.1.1 节多代场景 g0-g4 的全部期望（逐代 `retained_retry_payload_bytes` 精确值、g1 / g3 边界恰好准入、g2 越界失败后改变范围继续、g4 归零）；合并不复制载荷（`is` 同一对象 / 同一 tuple） |
| `test_orchestration_merge.py` | 合法合并：被重试 index 替换、其余同一对象、generation、新 `result_id`、metadata 账本；拒绝：类型错误、previous 非完整、retry 非重试轮、`base_result_id` 不符（包括形状完全相同的另一结果）、lineage 不符、generation 过期 / 重放、index 集合不符（多 / 少 / 顺序）、`media_item` 不是同一对象、配置不符、metadata 账本 lineage / generation 不符 -> `OrchestrationRetryError` / `OrchestrationIntegrityError`，均不返回内容；第二次合并同一重试结果 -> `OrchestrationConsumedError` |
| `test_orchestration_retry_chain.py` | 合同第 25.1 节 A-E：A `FAILED`（U1 前注入）-> 清除注入 -> `FRESH_REEXECUTE` -> `SUCCESS`；A' 窄例外（替身模拟 mkdir 后归属校验失败留下目录）-> fresh preflight `TARGET_DIRECTORY_EXISTS` -> 如实报告、不删除；B `PARTIAL`（`SOURCE_UNLINK_FAILED`、artifact 写入失败、`TARGET_DIRECTORY_FSYNC_FAILED` 策略接缝）-> `RESUME` -> `SUCCESS`，已完成 artifact 的 inode / mtime 不变、媒体未被重新移动、effect 单调增长；C preflight 阻断 -> 测试移除阻断物 -> `PREFLIGHT_RECHECK` -> `SUCCESS`，阻断未移除时继续 `PREFLIGHT_BLOCKED` 且阻断物字节不变；D checkpoint 已被别处消费 -> `CHECKPOINT_REJECTED`；E 模拟“进程退出”（丢弃全部结果、新 orchestrator 对同一文件重新 preview）-> 带部分 effect 的条目为 `PREFLIGHT_BLOCKED` / `PREFLIGHT_REJECTED`，零修改；metadata：失败 -> 重试成功 -> 执行 `SUCCESS`，重试仍失败 -> 可再次重试，Phase 3 账本 generation 与失败下标一致；`DEFERRED`：`NOT_SELECTED` 与 `CANCELLED`（含 RESUME 模式的未执行 preflight，用原 checkpoint 重新 preflight）-> `SUCCESS`；多代链 g0 -> g1 -> g2 -> g3，每代 `merge_retry`；“未执行即重试”组合路径（第 25.5 节） |

### 验收标准（gate）

* 目标 / contract / 全量 `0 failed`，passed 数不低于 S3。
* A-E 全部覆盖；RESUME 不重写已完成 effect 的证据（inode / mtime / 调用计数）。
* 所有 fail-closed 拒绝不返回内容、零文件系统修改。
* （E0-R2）第 35.1.1 节 g0-g4 场景全部通过，每个当前完整结果 `retained_retry_payload_bytes <= B` 且与定义值精确相等；
  `merge_retry` 第 9a / 9b 步失败时不登记 `retry.result_id`。

### commit

`feat(orchestration): add retry kinds, preview_retry and merge_retry (P4-C8 S4)`

### 复查

S4 Independent Review（范围 S3 Head..S4 Head）；重点：checkpoint 只携带不解读、RESUME 单调前进、metadata 重试与 Phase 3 一致、
一次性登记、`merge_retry` fail closed。

---

## S5 -- Summary / determinism / race / integration hardening + 最终公开 API

### 输入

S4 被接受的 Head；合同第 7.1、28、29、30、34、35 节。

### 允许改动文件

修改：

```text
src/fc2_organizer/orchestration/models.py      + PreviewSummary、ExecutionSummary、summary 属性、stage_counts（第 28 节）
src/fc2_organizer/orchestration/__init__.py    导出集合 == 合同第 7.1 节最终集合
tests/contract/test_orchestration_architecture.py（追加：公开 API 精确集合、完整模块集合、运行时端到端阻断测试）
tests/unit/orchestration/_fakes.py、_helpers.py（追加；S5-A1：另外唯一允许修改既有的
    _helpers.py::_execution_projection 与 _helpers.py::projection，仅用于闭合 P4-C8-S5-R-01，见第 0.5 节）
合同第 38 节 S4 / S5 状态行
```

新增：

```text
tests/unit/orchestration/test_orchestration_summary.py
tests/unit/orchestration/test_orchestration_determinism.py
tests/unit/orchestration/test_orchestration_race.py
tests/unit/orchestration/test_orchestration_integration.py
tests/unit/orchestration/test_orchestration_fault_injection.py
```

### 禁止范围

新增模块；改变 S1-S4 已冻结的行为；summary 以存储计数实现（必须是派生属性）；诊断输出。

### 接口范围

`PreviewSummary`、`ExecutionSummary`、`BatchPreview.summary`、`BatchExecutionResult.summary`；最终 `__all__`。

### 实现要求

1. 第 28 节全部字段与恒等式；`stage_counts` 按 `OrchestrationStage` 声明顺序列出全部阶段。
2. `__init__.__all__` 与合同第 7.1 节逐项相等（含 E0-R1 新增的 `BatchOutcome`、`ResourceLimitReason`、四个资源常量、
   `OrchestrationResourceLimitError`）。
3. （E0-R1）`BatchExecutionResult.outcome` 已在 S1 实现；本批以第 28.4 节恒等式把它与 summary 交叉验证（不改变其算法）。
4. （E0-R2）结果保留不变量（S1 模型）与 `merge_retry` 纵深防御（S4）的加固测试：在生成批次与竞争场景上验证每个当前完整结果
   `retained_retry_payload_bytes <= retention_budget_bytes`；篡改（`object.__setattr__` 修改 `retry_budget_bytes`、
   `retention_budget_bytes` 或把载荷更大的材料塞入重试轮结果）-> `merge_retry` fail closed 且 `retry.result_id` 未登记、修正后的
   真实重试结果仍可合并；两个线程并发 `merge_retry` 同一重试结果恰好一个成功，结果仍 `<= B`。不改变 S1 / S4 的算法。
3. 若本批测试发现 S1-S4 的生产缺陷：按 0.4 节以 `fix(orchestration): ... (P4-C8 S5)` 独立提交，只改相关文件 + 回归测试，
   不改变合同语义，并在 commit message 与 S6 HANDOFF 中记录。

### 测试矩阵

| 文件 | 覆盖 |
|---|---|
| `test_orchestration_summary.py` | 每个字段的定义；第 28.2 节全部恒等式在所有 disposition × `ExecutionStatus` × `RetryKind` 组合的生成批次（确定性枚举，而非随机）上成立；`PARTIAL` 永不计入 `success`；`ABORTED` 永不计入 `success` / `failed` / `retryable`；preview summary 恒等式；`stage_counts` 顺序与总和；（E0-R1）同一批生成批次上第 28.4 节 `outcome` ⇔ summary 三条恒等式全部成立，并覆盖主结果、重试轮结果、合并结果三种形态；公开 API 精确集合含 E0-R1 新增名称；（E0-R2）第 4 条实现要求中的保留不变量与 merge 纵深防御加固测试（可放在本文件或 `test_orchestration_race.py`，二者都在本批允许列表中） |
| `test_orchestration_determinism.py` | 同一混合批次（全部阶段的成功与失败）运行两次、以事件反转 engine / 图片 / 执行完成顺序、`M/K/W` 取不同值：确定性投影与 summary 逐项相等；重试集合顺序；`warnings` / `conflict_with` 顺序 |
| `test_orchestration_race.py` | 同一 preview 两个线程同时 `execute`（barrier）-> 恰好一个运行、另一个 `OrchestrationConsumedError`、零重复 `execute_filesystem`；两个 orchestrator 在同一进程并发执行重叠条目（各自的 preview）-> 每个源最多一个 `SUCCESS`、失败者为 P4-C7 类型化失败 / 阻断、源不丢失、非本执行条目不变；hardlink / 同文件两次 / 重叠根目录（同一目录经两个根发现）-> 冲突阻断；preview 之后 execute 之前：源改写 / 删除 / 目标被植入 / library root 被替换为 junction -> 类型化失败或阻断，从不执行另一件事；两个线程同时对同一结果 `preview_retry`（不同 orchestrator）-> 恰好一个成功；同一重试结果并发 `merge_retry` -> 恰好一个成功 |
| `test_orchestration_integration.py` | 真实 `discover_media` 扫描脏目录（嵌套、Unicode、大小写扩展名、伴随文件）-> preview -> execute -> 最终库目录精确列举与字节、NFO 与 P4-C4 渲染一致、图片与 P4-C5 结果一致、extrafanart 命名；library root 缺失 / 是 junction；运行时阻断 `amane` / `requests` / `sqlite3` / `shelve` / `dbm` / `pickle` 下的端到端运行 |
| `test_orchestration_fault_injection.py` | 按 P4-C7 单元与阶段逐项注入（U1 前、U1、U2 各 `TransferStage`、U3-U6、U7、U8..、清理失败）-> 每项的 disposition / `ExecutionStatus` / `issue` / `RetryKind` / summary；注入后重试至 `SUCCESS`（可重试者）；每项 `assert_source_not_lost` 与非本执行条目不变 |

### 验收标准（gate）

* 目标 / contract / 全量 `0 failed`，passed 数不低于 S4。
* 公开 API 精确集合、完整模块集合断言通过。
* 恒等式在生成批次上全部成立；确定性投影在所有顺序 / 并发变体下相等。

### commit

`feat(orchestration): add batch summaries and finalize public API with determinism and race hardening (P4-C8 S5)`

### 复查

S5 Independent Review（范围 S4 Head..S5 Head）；重点：summary 无静默丢失、确定性、竞争回归、公开 API。

---

## S6 -- 500-item batch orchestration gate + HANDOFF

### 输入

S5 被接受的 Head；合同第 35、35.1 节。

### 允许改动文件

新增：

```text
tests/unit/orchestration/test_orchestration_synthetic_gate.py
docs/review/P4_C8_HANDOFF.md
```

修改：

```text
tests/unit/orchestration/_fakes.py、_helpers.py（追加）
合同第 38 节 S5 / S6 状态行
```

生产代码：**不允许修改**。若门槛发现生产缺陷，必须先作为 `fix(orchestration): ... (P4-C8 S6)` 独立提交修复（只改相关生产文件 +
回归测试），并在 HANDOFF 中逐项记录；任何修复不得改变合同语义。

### 禁止范围

新增生产功能；修改合同第 1-37 节；重复 P4-C7 的 1000 extrafanart / 平台 syscall / 原子发布底层门槛；P4-C9 / P4-C10 任何内容。

### 实现要求

1. `test_orchestration_synthetic_gate.py`：合同第 35.1 节全部内容——分组表（A 310 / B 40 / C 30 / D 40 / E 10 / F 20 / G 30 /
   H 10 / I 10，组成静态断言）；主轮与 g1-g4 的全部期望计数（由分组表静态推导）；`M = K = W = 4` 的峰值断言；每次 preview /
   preview_retry 的零修改；每轮后全部 500 条的核心不变量；RESUME 不重写已完成 effect；最终库目录精确列举；无临时残留
   （leftover 名称精确）；全新 `tmp_path` 中以反转完成顺序重跑一次，投影与每轮 summary 相等。
   （E0-R1）另含：合同第 35.1 节 `outcome` 表的九个断言（主结果 `PARTIAL`；g1 / g3 重试轮 `SUCCESS`；g2 重试轮 `PARTIAL`；
   g4 重试轮 `FAILED`；g1-g4 合并结果与最终结果均为 `PARTIAL`）；门槛在默认资源配置下运行（只覆盖 `W = 4`），主 preview 与
   每个 `preview_retry` 都不得触发 `OrchestrationResourceLimitError`；资源边界子门槛（`MAX_BATCH_ITEMS` / `+ 1`、`B_exact` /
   `B_exact - 1`、并发预约峰值与账本 `<= B`、完成顺序无关），全部使用小配置；（E0-R2）有界快照子门槛（计数型自定义
   `Sequence` 经 `preview` 端到端：读取元素数 `== MAX_BATCH_ITEMS + 1`、说谎长度被拒绝、`__len__` 调用 0 次）与多代保留子门槛
   （合同第 35.1.1 节 g0-g4）。
2. 非空洞性检查（不提交）：合同第 35.1 节 (a)-(j) 十种生产变异（其中 (f)(g)(i)(j) 为资源控制变异——(i) 恢复 snapshot-first、
   (j) 把重试可用额度改为完整 `B`——(h) 为 outcome 变异，全部必须在行为层而不是只靠 AST 使门槛失败），每种都必须使门槛失败；
   记录失败用例数后撤销，工作区恢复干净
   （恢复后以 `git hash-object --no-filters` 与 HEAD blob 比对确认）。
3. `docs/review/P4_C8_HANDOFF.md`（简体中文）：坐标（Frozen Base、E0 Head、S1-S6 Heads、Code Review Candidate、Docs Head、
   Code Review Range 与 Docs Review Range）；变更文件清单；合同各节 -> 实现 / 测试映射；测试数字（目标 / contract / 全量 / skip
   明细）；500-item 门槛组成与各轮计数；直接复现表；非空洞性结果；证据缺口（例如真实跨进程并发、POSIX 原生主机，如未执行）；
   延续项（合同第 36 节原样）；已知局限（合同第 37 节）；状态
   `P4-C8 implementation: COMPLETE — INDEPENDENT REVIEW REQUIRED / P4-C8: NOT CLOSED / P4-C9: NOT STARTED / Phase 4: NOT CLOSED`。

### 测试矩阵

| 文件 | 覆盖 |
|---|---|
| `test_orchestration_synthetic_gate.py` | 合同第 35.1 节逐项 |

### 验收标准（gate）

* 门槛、contract、全量 `0 failed`；skip 逐项说明。
* 十种变异（(a)-(j)）全部被门槛在行为层杀死（失败用例数记录在 HANDOFF）。
* （E0-R2）有界快照子门槛与多代保留子门槛全部通过。
* （E0-R1）九个 `outcome` 断言与资源边界子门槛全部通过；默认资源配置下 500-item 门槛完整运行。
* Code Review Candidate（测试提交）与 Docs Head（HANDOFF 提交，只含 HANDOFF 与合同第 38 节状态行）分离。

### commit

```text
test(orchestration): add P4-C8 500-item batch orchestration gate (P4-C8 S6)
docs(review): add P4-C8 handoff
```

### 复查

P4-C8 S6 FINAL INDEPENDENT CLOSURE REVIEW（范围 S5 Head..S6 Docs Head；并对 E0..S6 做闭合审计）。

---

## 最终 integrated gate（冻结）

P4-C8 的闭合门槛 = 以下全部同时成立：

1. S1-S6 每一批都有独立复查 PASS 结论（合同第 38 节逐行 `ACCEPTED / CLOSED — FINAL REVIEWED CODE HEAD <sha>`）；
2. 合同第 35 节测试矩阵的每一类都有对应测试文件且在 S6 Head 上 `0 failed`；
3. 第 35.1 节 500-item 门槛全部断言通过（含 E0-R1 的 `outcome` 断言与资源边界子门槛，默认资源配置；E0-R2 的有界快照与多代保留子门槛），(a)-(j) 十种变异
   全部被杀死；
4. 全量测试 `0 failed`，passed 数不低于 S5；
5. 生产代码对下层私有模块零引用、零直接文件系统修改、零持久化 / 诊断输出（架构测试）；
6. P4-C1..P4-C7 的生产代码、合同、HANDOFF 零改动（`git diff --name-status 586f92f..<S6 Docs Head>` 核对：只有
   `src/fc2_organizer/orchestration/**`、`tests/unit/orchestration/**`、`tests/contract/test_orchestration_architecture.py`、
   合同第 34.3 节授权的六个既有守卫文件、两份 P4-C8 文档、`docs/review/P4_C8_HANDOFF.md`）。

## Final HANDOFF（冻结要求）

`docs/review/P4_C8_HANDOFF.md` 由 S6 创建，内容见 S6 实现要求第 3 条；闭合时由闭合 docs 提交追加“P4-C8 最终闭合”一节
（第 1 至 N 节作为实现时证据原样保留，状态表述标注为实现时快照）。

## P4-C8 闭合流程（冻结）

```text
1  S6 FINAL INDEPENDENT CLOSURE REVIEW = PASS
2  P4-C8 Final Closure Docs 提交（docs-only；父提交 = S6 Docs Head）：
     合同第 38 节：S6 ACCEPTED / CLOSED、P4-C8 implementation REVIEWED COMPLETE、P4-C8 CLOSED、Phase 4 NOT CLOSED，
       并追加“P4-C8 最终闭合记录”（治理记录，不改变第 1-37 节语义）
     HANDOFF：追加“P4-C8 最终闭合”一节
     本计划：追加“P4-C8 最终闭合记录”（治理记录）
3  P4-C8 Final Docs-Only Closure Review = PASS
4  该 Final Closure Docs 提交成为 P4-C9 Frozen Base；P4-C9 此前 NOT STARTED
```

S6 的 Code Review Candidate 与 Docs Head 都**不是** P4-C9 Frozen Base。P4-C8 闭合不关闭 Phase 4（P4-C9、P4-C10 尚未完成）。

---

## 附录 A. 合同条款 -> 批次映射

| 合同节 | 批次 |
|---|---|
| 4 Phase 3 比较与复用 | S1（类型）、S2（scheduler.run）、S4（retry_failed / apply_retry） |
| 5-6 模块与依赖 | S1（守卫 + 部分模块），S2-S5 追加 |
| 7 公开 API | S1（部分）、S2（`BatchOrchestrator.preview`）、S3（`execute`）、S4（`preview_retry`、`merge_retry`）、S5（最终集合） |
| 8-10 类型 / 配置 / 模型 | S1（summary 在 S5） |
| 11 状态映射 | S1（枚举与不变量；E0-R1 11.5 `BatchOutcome` 与 `outcome` 属性）、S2（metadata 映射）、S3（disposition）、S5（outcome × summary 恒等式）、S6（outcome 门槛断言） |
| 12-14 身份 / 顺序 / 识别与冲突 | S1（Phase A）、S2（Phase B） |
| 15-17 preview / 零修改 / 与 preflight 的关系 | S2 |
| 18 execution | S3 |
| 19 并发 | S2（图片）、S3（执行）、S5（回归） |
| 19.6 资源硬限制（E0-R1；E0-R2 修订） | S1（常量、配置、错误；E0-R2：`recognition.bounded_snapshot`、预算字段、保留载荷 helper 与结果保留不变量）、S2（构造时单条上限、保留预算账本与预约准入、主 preview 记录 `retention_budget_bytes`）、S3（结果复制预算字段、预算相等检查）、S4（`base_retained` / `available_retry_budget`、`merge_retry` 纵深防御、多代场景）、S5（保留不变量与 merge 纵深防御加固）、S6（资源边界、有界快照、多代保留子门槛与变异 (f)(g)(i)(j)） |
| 20 隔离与致命 | S2（preview）、S3（execute） |
| 21-22 失败映射 / 图片部分获取 | S2、S3 |
| 23-24 PARTIAL / checkpoint | S3（产生）、S4（重试） |
| 25-26 retry / merge | S1（判定表）、S4 |
| 27 取消 | S2（asyncio）、S3（token） |
| 28 汇总 | S5（含 28.4 outcome 一致性） |
| 29 确定性 | S2-S5（逐批），S5（集中），S6（门槛） |
| 30-33 安全 / P4-C7 委托 / P4-C9 边界 / 持久化 | S1（AST），S2-S6（行为） |
| 34 架构测试 | S1-S5 |
| 35 测试矩阵 | S1-S6（按上表），S6（500-item） |
| 36-38 延续项 / 范围之外 / 状态 | 全部批次（只更新第 38 节状态行） |

## 附录 B. 裁决记录（E0）

合同附录 A 的 20 条裁决即本计划的裁决记录；本计划额外裁决：

| # | 裁决 | 理由 |
|---|---|---|
| P1 | 六个施工批次 S1-S6，每批一个代码提交 + 独立复查 | 与 P4-C7 的成功先例一致；每批可独立验证 |
| P2 | summary 放在 S5 | 它依赖 S2-S4 产生的全部 disposition；集中以恒等式测试 |
| P3 | 守卫更新集中在 S1 | 第一批就引入对 execution / materialization 的依赖，后续批次不再触碰既有测试 |
| P4 | 每批更新合同第 38 节状态行（上一批 ACCEPTED + 本批 IMPLEMENTED） | 治理状态始终单一来源 |
| P5 | S6 禁止生产改动，缺陷修复必须独立提交 | Code Review Candidate 与门槛证据可分离审计 |
| P6 | （E0-R1）S1 状态行治理特例：更新 E0 行（FINAL REVIEWED DOCS HEAD）+ S1 行；S2-S6 使用通用模板；不存在 S0 | 消除通用模板在 S1 上产生的不存在的 “S0”，并授权 S1 修改 E0 行 |
| P7 | （E0-R1）`outcome` 在 S1 实现（模型属性），S5 交叉验证，S6 门槛断言 | 它只依赖 S1 已有的条目模型；不新增批次 |
| P8 | （E0-R1）资源常量 / 配置 / 条目数上限归 S1，账本与预约准入归 S2（`preview.py`），重试计量归 S4 | 按现有模块职责归属，不新增模块或批次 |
| P9 | （E0-R2）有界快照归 S1 `recognition.py`；预算字段、载荷计量 helper 与保留不变量归 S1 `models.py`；lineage 预算校验、`base_retained`、可用额度与 merge 纵深防御归 S4 `retry.py`；S3 只复制字段并检查预算相等；S5 只加固测试 | 沿用现有模块职责，不新增生产模块或批次，施工时无需再决定归属 |

无需项目所有者决定的外部业务问题。
