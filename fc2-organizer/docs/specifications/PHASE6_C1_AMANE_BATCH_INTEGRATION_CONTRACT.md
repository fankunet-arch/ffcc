# PHASE 6 / P6-C1 — Amane 真实批量集成与批量收尾（Real Amane Batch Integration & Closure）合同

```text
文档状态                    : DESIGN CANDIDATE — NOT YET ACCEPTED
Phase 6                     : DESIGN CANDIDATE
P6-C1                       : DESIGN CANDIDATE
Frozen Contract             : NOT YET ACCEPTED
Construction Plan           : NOT YET ACCEPTED（docs/P6_C1_CONSTRUCTION_PLAN.md）
Design Accepted Head        : NOT ESTABLISHED
Implementation              : NOT STARTED
Production Modified         : NO
Tests Modified              : NO
Risk Class                  : C
Package Frozen Base         : 4189b9552d26b3cc5273e0ac09e46e5a3759121d（P5-C2 Final Closure Docs Head）
Governance Authority        : docs/PROJECT_GOVERNANCE_ACCELERATION.md @ 3b9d39e9adbcc8a009707486eebbb8736a5b1c4d
Upstream Final Reviewed Head: 1ef23247c2c65649589e9919c00093901bbcb517（P5-C2 Final Reviewed Technical Head）
Phase 6 package count       : 1（P6-C1；P6-C2 默认不存在）
Next                        : INDEPENDENT DESIGN REVIEW（通过之前禁止 Developer 开始 S1）
```

本文是 P6-C1 的 **Frozen Contract 候选**。它只有在独立 Design Review PASS 之后才成为 Frozen Contract；在此之前不得被解读为 FROZEN /
DESIGN PASS / IMPLEMENTATION AUTHORIZED。唯一 authority 转换：独立 Design Review PASS → 该 Design Candidate SHA 成为 Design Accepted Head
（Frozen Contract / Plan Head、Implementation Input）→ 才允许 Developer 开始 S1。

配套文档：

| 文档 | 作用 |
|---|---|
| `docs/PHASE6_MASTER_PLAN.md` | Phase 6 总体裁决（一个 C、不拆 P6-C2、架构、Phase 7 边界、风险登记） |
| 本文 | P6-C1 的 Frozen Contract 候选（行为、接口、不变量、证据门） |
| `docs/P6_C1_CONSTRUCTION_PLAN.md` | S1 / S2 / S3 施工计划候选（Governance v2 强制头、文件清单、允许 / 零 diff 范围、停止条件） |

三者范围、Risk Class、Frozen Base、Governance Authority 必须逐字一致；不一致即设计缺陷（U6-12）。

---

## 1. 目的与用户能力

P6-C1 回答一个问题：**一个真实用户能否在不修改任何已 CLOSED 代码的前提下，把一个“脏”媒体目录经由真实的 Amane 宿主，批量地
走完 “识别番号 → 多来源元数据 → 图片 → NFO → 产物清单 → 执行前预检 → 批量预览与汇总”，并且在失败、重试、取消下行为正确、可审计？**

用户可见的完整纵向能力（Vertical Closure）：

```text
dirty media root
  → 扫描并识别规范 FC2 番号（P4）
  → 有界并发的批量调度（P4 BatchOrchestrator / Phase 3 BatchScheduler）
  → 每个番号向真实 Amane 宿主提交一个 SCRAPE 任务（本合同新增）
  → 宿主 route 中的 ffcc.fc2-metadata 插件（P5，CLOSED）→ Core MultiSourceEngine（Phase 3，CLOSED）
  → Amane Metadata 持久化 → 本合同的“宿主结果 → Core AggregationResult”桥
  → P4 继续：planning → publication → 图片 → NFO → 产物清单 → 执行前预检
  → BatchPreview + 确定性批量汇总 + 运维审计（与语义结果分离）
  → 失败子集重试、取消（精确到任务）、取消不确定性的显式报告
```

P6-C1 **不**执行任何真实文件整理（第 19 节）。真实文件系统验收是 Phase 7。

---

## 2. 权威、坐标与优先级

```text
Frozen Contract (本文，Design Review PASS 之后)
>
Frozen Construction Plan
>
docs/PROJECT_GOVERNANCE_ACCELERATION.md
>
Task Prompt
```

| 坐标 | 值 | 说明 |
|---|---|---|
| Package Frozen Base | `4189b9552d26b3cc5273e0ac09e46e5a3759121d` | P5-C2 Final Closure Docs Head；P6-C1 的 package baseline |
| Governance Authority | `3b9d39e9adbcc8a009707486eebbb8736a5b1c4d` | `docs/PROJECT_GOVERNANCE_ACCELERATION.md` 的 accepted governance head；**不是** Package Frozen Base |
| P5-C2 Final Reviewed Technical Head | `1ef23247c2c65649589e9919c00093901bbcb517` | P5-C2 CLOSED；Independent Level 1 PASS；Risk Class C |
| Amane v0.15.0 | tag object `3292c957a092f85ddde1ba7462ffe9813827f4f1`；peeled commit `45dff2159369883e028a296d775a4598836c1ddd` | P5 已正式支持的最低版本目标 |
| Amane v0.18.0 | tag object `7d2190704fa1e3c0f7f86889111d12b9fa6701c8`；peeled commit `0a8a731d7746bde5e8828d1eb74c7bd9752b42e4` | P5 已正式支持的当前稳定版目标 |

设计期已用 `git rev-parse` 在 `https://github.com/sqzw-x/amane.git` 的 bare clone 上核对以上四个 SHA 全部相符（第 7.1 节）。

支持声明是**坐标级**的（沿用 P5-C2 I-C2-14）：P6-C1 的必需坐标是 **SC-03**（v0.15.0 / source host / Windows x64）与 **SC-04**
（v0.18.0 / source host / Windows x64）；SC-01 / SC-02（冻结桌面包）为**可选**坐标，只有实际运行并 PASS 才可声明，否则保持 `UNVERIFIED`；
macOS / Linux / Docker 保持 `UNVERIFIED`。不得写“支持 v0.15.0 / v0.18.0”这类脱离平台 / 形态的概括。

---

## 3. 范围与非目标

### 3.1 范围（本包交付）

1. 新增独立 package `fc2_amane_batch`（第 5.3 节）：Amane Host 的**外部 HTTP client / bridge**。
2. Amane-backed `AggregationEngine`：满足 Phase 3 `AggregationEngine` Protocol（`async aggregate(number) -> AggregationResult`），注入现有
   `BatchOrchestrator`。
3. 宿主任务生命周期：提交 / 观察 / 精确取消 / 有界超时。
4. 宿主结果 → Core `AggregationResult` 的 fail-closed 映射（含结构化失败映射）。
5. 批量门面：扫描 + 预览 + 失败子集重试 + 汇总 + 运维审计。
6. 真实 Amane v0.15.0 与 v0.18.0 宿主上的确定性纵向验收（≥ 10 个 FC2）、失败 / 重试 / 取消 / 并发 / 确定性 / mutation 证据。
7. 一次真实公网 live smoke 尝试（结果如实记录，缺失则如实声明 UNVERIFIED）。

### 3.2 非目标（明确不做；任何一项出现在实现里都是 STOP 条件，见第 28 节）

```text
× 真实 organize 执行：不调用 BatchOrchestrator.execute / execute_filesystem / 任何会 mkdir、rename、move、copy、delete 的 API
× Amane ORGANIZE / TRASH / CLEANUP / UPSCALE / R18_IMPORT / RESCRAPE / ACTOR_SCRAPE 任务的提交
× 修改 Amane 源码、monkeypatch Amane、import amane.*、读取 Amane SQLite、访问 Amane Repository
× 修改 P5 plugin（ffcc.fc2-metadata）、P5 Core wheel / plugin zip、P5 release 安全机制
× 修改 P4 BatchOrchestrator / BatchScheduler 的任何生产语义
× 第二套 scheduler、隐藏 worker pool、无界 fan-out
× durable batch id / checkpoint 文件 / JSON resume / pickle / SQLite 状态 / 跨进程锁 / 进程崩溃后恢复
× 使用 Amane POST /tasks/batch 的 retry / delete 动作作为重试机制
× 修改用户的 Amane 全局配置；读取 Amane /api/config（含 cookie / token）
× 读取 Amane 日志、解析任何错误文本 / 日志文本 / 异常消息作为控制依据
× 重建跨 P5 边界已丢失的内部 provenance（JavDB / FC2PPVDB / “source X 选了 title”）
× 在 P4 一侧声明 PARTIAL 的细分来源失败
```

---

## 4. 风险分级与 C 粒度裁决

```text
Risk Class: C
```

Risk C **不是**因为 Phase 6 会移动文件（它不会）。Risk C 来自**新的集成边界**：

| 风险点 | 为什么是 Risk C |
|---|---|
| Amane Host HTTP API 边界 | 跨进程、跨版本（v0.15.0 / v0.18.0）的外部系统契约 |
| 宿主认证 / 凭据处理 | Bearer token 的注入、传输、泄漏面（repr / 异常 / 日志 / 预览 / 诊断） |
| 宿主任务所有权 | 只能操作“自己创建的那一个任务”；误操作会影响用户的其它任务 |
| 宿主任务取消 | 取消的语义是**异步且可能不确定**的（第 10 节） |
| 宿主侧持久化 SCRAPE 生命周期 | 宿主会把结果写入用户的 Amane Metadata 库；任务本身持久化在宿主（第 7.6、27 节） |
| 失败歧义 | 提交超时后任务是否已被创建？取消后任务是否已停止？——必须显式建模为“不确定”，不得猜测 |

因此：**新的 Frozen Contract 必须先通过独立 Design Review，之后才允许 S1**；Phase 6 完成后还有**一次** C-level Independent Level 1 Review。
S1 / S2 / S3 默认连续施工，不逐 S Review（除非触发第 28 节的升级门）。

### 4.1 Governance v2 “四问”（针对“是否拆出 P6-C2”）

1. **为什么不能和前一个 C 一起完成？** 前一个 C 是 P5-C2（已 CLOSED）。P6 是新的宿主批量集成边界，不能追溯塞进 P5。
2. **单独拆出 P6-C2（Failure / Retry / Batch Closure）降低了什么具体风险？** 没有。失败映射、重试、取消、汇总与真实集成**使用同一个
   host-task 边界、同一套 client、同一份审计与同一组真实宿主**；拆开后 P6-C1 无法在没有失败 / 取消语义的情况下被独立验收
   （一个只处理成功路径的 Host client 会在 Review 时被要求补齐失败路径，等于把 C2 的内容回退到 C1）。
3. **该风险是否值得额外增加一次“开发停止 + Review + Closure”？** 否。
4. **如果取消这个边界（即不拆），是否影响 correctness / safety / auditability？** 不影响；合并反而提高 auditability（一份证据覆盖完整的
   host-task 生命周期）。

结论：**Phase 6 只有一个 C**。P6-C2 默认不存在；只有出现“无法在同一个 C 内安全控制的、真实且独立的 Risk-C 边界，并且拆分确实提高
correctness / safety / auditability”时才允许重新提出（Master Plan 第 5 节）。代码多 / 测试多 / 文件多 / 模型多 / helper 多**不是**理由。

---

## 5. 复用、不可变性与包位置

### 5.1 CLOSED 边界与复用方式

| CLOSED 边界 | P6-C1 如何使用 | 禁止 |
|---|---|---|
| `fc2_metadata_core`（Phase 1-3） | 只使用公共模型：`AggregationResult` / `AggregateStatus` / `SourceResult` / `SourceStatus` / `SourceErrorKind` / `NormalizedMetadata` / `normalize_fc2_number` / `require_canonical_number` / `validate_base_url` / `BatchConfig` | 修改；构造 Core 内部 `SourceExecutionTrace` 以伪造执行 |
| `fc2_organizer.discovery` | `discover_media` / `DiscoveredMediaItem` / `DiscoveryPolicy`（门面 `preview_root`） | 修改 |
| `fc2_organizer.orchestration`（P4-C8） | **注入** Amane-backed engine 的 `BatchOrchestrator(...).preview(...)`；`OrchestrationConfig`；`BatchPreview` / `ItemPreview` / `PreviewSummary` / `IssueReason` / `OrchestrationStage` / `PreviewState` | 调用 `execute` / `preview_retry` / `merge_retry`（第 13、19 节）；伪造 / 重建其模型 |
| `fc2_organizer.images`（P4-C5） | 调用方传入的 `ImageHttpClient`（生产为 `HttpxImageClient`）；`ImageAcquisitionPolicy` | 重写图片获取；依赖 Amane Resource 文件 |
| `fc2_organizer.planning / publication / nfo / materialization / execution / diagnostics` | 经 `BatchOrchestrator` 间接使用 | 直接调用 `execute_filesystem` 或任何写文件系统 API |
| `adapters/amane/fc2_amane_adapter`、`adapters/amane/shim`、P5 release 机制 | 只**读取**其常量作测试对账（`PLUGIN_ID`），不 import 进 `src/` | 修改；把 `fc2_organizer` 塞进 Core wheel / plugin zip；增加 Amane 不存在的 batch plugin capability |

### 5.2 零 production diff 范围（冻结）

以下路径在 P6-C1 全程**零 diff**（`git diff 4189b9552d26b3cc5273e0ac09e46e5a3759121d..HEAD` 机检）：

```text
src/fc2_metadata_core/**
src/fc2_organizer/**                       （含 discovery / planning / publication / nfo / images / materialization /
                                            execution / orchestration / diagnostics 与 __init__.py）
adapters/amane/**                          （含 fc2_amane_adapter / shim / release / api_manifest / README）
tools/ 中全部既有文件
pyproject.toml
docs/PROJECT_GOVERNANCE_ACCELERATION.md  CLAUDE.md
docs/specifications/ 中全部既有文件       docs/review/ 中全部既有 HANDOFF
docs/acceptance/evidence/ 中全部既有文件
```

如果设计或实现过程证明**必须**修改上述任何 CLOSED production 语义，必须立即停止并返回 `AUTHORITY ESCALATION REQUIRED`
（第 28 节 U6-1），列出：必须改哪个 CLOSED package、为什么不可避免、影响范围、兼容性、security impact、regression scope，由 Governance
Coordinator 裁决。**不得**把它写进普通 P6 施工。设计期结论：**无需修改任何 CLOSED production 语义**。

### 5.3 包位置裁决（冻结）：`src/fc2_amane_batch/`（顶层同级包）

任务书建议的名称形如 `fc2_organizer.amane_batch`，并明确“名称由 Designer 决定”。设计期核查发现：**多个 CLOSED 架构测试逐字钉死了
`fc2_organizer` 的顶层子包集合**：

```text
tests/contract/test_discovery_architecture.py:187   top_level_dirs == {discovery, planning, publication, nfo, images, materialization, execution, orchestration, diagnostics}
tests/contract/test_nfo_architecture.py:206         同上
tests/contract/test_planning_architecture.py:212    同上
tests/contract/test_publication_architecture.py:187 同上
tests/phase4_acceptance/test_p4_acceptance_architecture.py:29-30  PUBLIC_PACKAGES = 同一集合
```

在 `fc2_organizer` 下新增 `amane_batch` 会使这些 CLOSED 测试失败，必须修改至少 5 个 CLOSED 测试文件。因此冻结选择**顶层同级包**：

```text
src/fc2_amane_batch/            新增；与 fc2_metadata_core、fc2_organizer 同级
```

* 命名与既有的 `fc2_amane_adapter`（宿主 / 插件侧）形成对照：`fc2_amane_batch` 是**组织器侧**的 Amane 批量集成。
* 依赖方向（冻结）：`fc2_amane_batch → fc2_organizer → fc2_metadata_core`；反向 import 禁止（CLOSED 包不得 import `fc2_amane_batch`）。
* `fc2_amane_batch` **不 import** `amane`、`fc2_amane_adapter`（P5-C1 守卫 `test_core_and_organizer_never_import_amane_and_nothing_else_imports_the_adapter`
  对整个 `src/` 做 AST 检查，本包天然满足）。
* 该包不属于 Core wheel（`tools/build_core_wheel.py` 只打包 `src/fc2_metadata_core/**/*.py`），也不进入 plugin zip；P5 release 机制零影响。
* 其它 `src/` 级别的钉死（逐一核查）：没有 CLOSED 测试枚举 `src/` 顶层包集合；没有按文本扫描 `src/` 中的 “amane” 字样。

### 5.4 历史 diff 门禁碰撞 HG-1（设计期发现；需要 Design Review 明确裁决）

CLOSED 的 P5-C2 测试中有两个**绑定到 `HEAD` 的历史范围门**：

| 文件 | 门禁 |
|---|---|
| `tests/amane_compat/test_amane_compat_scope_gate.py` | `git diff 232ece06…..HEAD` 必须全部落在 P5-C2 allow-list；`src/.+`、`tests/(?!amane_compat/).+`、`pyproject.toml` 等零 diff；工作树改动同样受限 |
| `tests/amane_compat/test_amane_compat_evidence_reconciliation.py`（“范围门：b8480e74..HEAD”） | `b8480e74…..HEAD` ∪ 工作树只能含被授权的证据面；`src/.+`、`tests/(?!amane_compat/).+` 零 diff |

这两个门禁表达的是“**P5-C2 这一个包**的 diff 范围”，但它们的上界写成了 `HEAD`。P6 分支任何新增文件（包括本设计提交的三份 docs）
都会使它们失败。这不是 production 语义问题，但**是对 CLOSED 测试文件的修改**，必须在合同层面冻结，而不是由 Developer 临时决定。

**设计期实测（用两个文件里的真实正则字面量对真实 `git diff --name-only` 求值）**：

| 范围 | 文件数 | scope_gate（`ALLOWED_PATTERNS` / `FROZEN_PATTERNS`） | reconciliation（`RECONCILIATION_ALLOWED` / `RECONCILIATION_ZERO_DIFF`） |
|---|---|---|---|
| `232ece06…..1ef23247…`（Final Reviewed Technical Head） | 33 | 通过（范围外 0；冻结范围被触碰 0） | — |
| `b8480e74…..1ef23247…` | 12 | — | 通过（范围外 0；零 diff 范围被触碰 0） |
| `232ece06…..4189b955…`（Frozen Base） | 33 | 通过 | — |
| `b8480e74…..4189b955…`（Frozen Base） | 13 | — | **失败**：多出的一个文件是 `adapters/amane/README.md`（P5-C2 纯状态 Final Closure 提交修改；该文件落在 `RECONCILIATION_ZERO_DIFF` 的 `adapters/amane/.+`，且不在 `RECONCILIATION_ALLOWED`） |

即：**reconciliation 门禁在 Package Frozen Base 上，按其断言逻辑求值为红**（P5-C2 Final Closure 修改了 `adapters/amane/README.md`；scope_gate 的 allow-list 允许该 README，因此它在 Frozen Base 上求值为绿）。
设计期只做了上述求值，**没有运行 pytest**（本轮是 docs-only）；S1 第 0 步的基线记录会用真实 pytest 结果确认。若确认为红，它是继承的既有红，不是 P6 引入的，
必须如实标为 `PRE-EXISTING RED @ 4189b95`（不得写成回归；它由 HG-1 的重绑恢复为绿，而不是被掩盖）。

**冻结的最小重绑（HG-1，需 Design Review 明确 PASS；若被否决 → AUTHORITY ESCALATION，由 Governance Coordinator 裁决）**：

1. 仅修改上述两个文件；断言逻辑、allow-list、zero-diff 模式字面量**逐字不变**（机检：这四个模块级常量的 AST 与 Frozen Base 版本相同）。
2. 把 `git diff --name-only <BASE>..HEAD` 的上界由 `HEAD` 改为不可变常量
   `P5_C2_REVIEWED_HEAD = "1ef23247c2c65649589e9919c00093901bbcb517"`（P5-C2 Final Reviewed Technical Head；上表实测两个门禁在该上界上都通过，
   且它正是独立 Review 所接受的 P5-C2 技术范围；Final Closure 只追加了纯状态的 `adapters/amane/README.md` 与 `docs/review/P5_C2_HANDOFF.md`）。
   这同时使 reconciliation 门禁恢复为绿。
3. “工作树改动”分量（scope_gate 的 `test_working_tree_changes_are_limited_to_the_allow_list_as_well`，以及 reconciliation 的 `_changed_since_authority()` 中的
   `git status --porcelain`）从这两个**历史**门禁中移除；活跃工作树由 P6 自己的范围门（`tests/amane_batch/test_amane_batch_scope_gate.py`）
   覆盖，其断言形态与 P5-C2 的相同（`4189b95…..HEAD` ∪ 工作树 ⊆ P6 allow-list；闭合范围零 diff）。
4. 两个文件中既有的“Base 可达且是 HEAD 祖先”测试保持不变。
5. 这是 **S1 的第一个提交**（独立 commit，commit message 标注 `HG-1`），其 diff 必须只含这两个文件，并随 C-level Review 一并审查。

> 注意：本设计提交（docs-only）在其自身 HEAD 上**会**使 scope_gate 的两个历史范围测试失败（三份新 docs 不在 P5-C2 allow-list 内），
> reconciliation 的两个范围测试则在 Frozen Base 上就已经是红的。这是本设计无法避免的、已知的后果；在 HG-1 落地之前，这些测试在 P6 分支上预期失败，
> 不属于回归。

---

## 6. 运行时架构（冻结）

### 6.1 纵向链路

```text
dirty media root
    │  discover_media()                                   [fc2_organizer.discovery，CLOSED]
    ▼
DiscoveredMediaItem × N
    │  BatchOrchestrator(engine=AmaneAggregationEngine, image_client, library_root, …).preview(items)
    ▼                                                    [fc2_organizer.orchestration，CLOSED；注入 engine]
P4 识别 + Phase A 冲突  →  Phase 3 BatchScheduler（M 个并发 worker，M = OrchestrationConfig.metadata.max_in_flight_items）
    │  每个 worker：await AmaneAggregationEngine.aggregate("FC2-<digits>")          [fc2_amane_batch，新增]
    ▼
AmaneHostClient（httpx，显式 base URL / 显式凭据，无 cookie / 无 env / 无重定向）
    │  POST /api/tasks   {"type":"scrape","number":N,"content_type":"fc2","use_cache":[]}
    │  GET  /api/tasks/{id}  （有界轮询）
    │  GET  /api/metadata/{metadata_id}
    │  POST /api/tasks/batch {"action":"cancel","task_ids":[id]}   （仅取消路径，精确到该 id）
    ▼
Amane 宿主  →  P5 ffcc.fc2-metadata  →  Core MultiSourceEngine（多来源聚合）  →  P5 MediaMetadata 映射  →  Amane Metadata 持久化
    │
    ▼
host 结果 → 结构化映射（第 11、12 节）
    ▼
合法 Core AggregationResult（SUCCESS，唯一 SourceResult：ffcc.fc2-metadata）或 FAILED（结构化 SourceStatus / SourceErrorKind）
    ▼
P4 继续（CLOSED）：planning → publication → 图片（HttpxImageClient）→ NFO → 产物清单 → 执行前预检 → BatchPreview
    ▼
fc2_amane_batch：AmaneBatchPreview（语义结果）+ AmaneBatchSummary（确定性汇总）+ AmaneHostAuditSnapshot（运维审计，与语义分离）
```

**不进入宿主的东西**：本地源文件路径、本地文件字节、oshash、`media_id`、`library_id`——提交体**只有**第 8.1 节的四个键，且 `number`
是规范 FC2 号。

### 6.2 为什么必须这样连接

* P5-C1 的 plugin 是 `FilmSourcePlugin` / `FilmSourceProvider`，职责止于 `SearchQuery → canonical FC2 → Core aggregate → MediaMetadata`；
  它**没有**批量编排、图片、NFO、整理、文件系统执行、durable resume。不得为 Phase 6 给它增加 Amane 不存在的 batch capability。
* P5 release Core wheel 只含 `fc2_metadata_core`，不含 `fc2_organizer`；不得把 `fc2_organizer` 塞进已 CLOSED 的 Core wheel 或 plugin zip。
* P4-C8 已拥有 `BatchScheduler`、有界并发、取消语义、planning、图片、NFO、materialization、preflight、`BatchPreview`、汇总。
  **禁止写第二套 scheduler**；正确方式是注入一个 Amane-backed `AggregationEngine`。

### 6.3 冻结的模块地图（`src/fc2_amane_batch/`）

| 模块 | 职责 | 公共 / 私有 |
|---|---|---|
| `__init__.py` | 精确的 `__all__`（第 20.1 节）；不 eager import 重模块以外的任何东西 | 公共 |
| `errors.py` | 错误层次（第 20.2 节） | 公共 |
| `credential.py` | `AmaneHostCredential`（redact、不可序列化） | 公共 |
| `config.py` | `AmaneHostConfig`、常量、URL / 数值校验 | 公共 |
| `audit.py` | `HostFailureKind` / `CancelOutcome` / `HostAttemptRecord` / `AmaneHostAuditSnapshot` / 内部 `_AuditLedger` | 公共 + 私有 |
| `_wire.py` | 宿主响应的严格解析（`HostTask` / `HostBatchCancelResult` / `HostMetadata` / `HostWorkerState`） | 私有 |
| `host_client.py` | `AmaneHostClient`：5 个操作（第 7.2 节），传输安全，响应上限 | 公共（便于测试），仅 engine / facade 使用 |
| `_lifecycle.py` | 提交 / 观察 / deadline / 精确取消 / 清理预算（第 9、10 节） | 私有 |
| `_mapping.py` | host 结果 → `NormalizedMetadata` / `AggregationResult`；失败映射表（第 11、12 节） | 私有 |
| `engine.py` | `AmaneAggregationEngine`（唯一的 `async def aggregate`） | 公共 |
| `models.py` | `AmaneBatchRound` / `AmaneBatchPreview` / `AmaneBatchSummary` | 公共 |
| `facade.py` | `AmaneBatchIntegration`：preflight / preview / preview_root / retry_failed / audit / aclose | 公共 |

模块数量与职责是冻结的；Developer 可以在不改变上述公共接口与不变量的前提下增加私有 helper 文件，但**不得**增加新的公共符号，
也不得把职责移到 `fc2_organizer` / `fc2_metadata_core` 一侧。

### 6.4 允许 / 禁止的 import（AST 守卫，第 23 节 E6-03）

```text
允许：标准库（asyncio / dataclasses / enum / ipaddress / json / math / time / types / urllib.parse / http.cookiejar / re / collections / typing）
      httpx（0.27.x，Core 已有依赖）
      fc2_metadata_core 的公共子包：aggregation / models / normalize / batch / sources.base（require_canonical_number）/ errors
      fc2_organizer 的公共子包：discovery / orchestration / images（仅类型：ImageAcquisitionPolicy）/ planning（仅 OutputPolicy）
禁止：amane / amane.* / fc2_amane_adapter / requests / aiohttp / urllib.request / socket / ssl（直接） / subprocess / sqlite3 / pickle / marshal / shelve /
      logging（本包零日志）/ os（环境、文件）/ pathlib（文件 API）/ shutil / tempfile / fc2_organizer.execution / .materialization / .nfo / .publication /
      任何 fc2_* 包的私有（下划线）模块
```

> 实现提示：`secrets` 不需要；`http.cookiejar` 仅用于构造“拒绝一切 cookie”的 jar；`ssl` 由 httpx 内部使用，本包不直接 import。
> 本包既不读取环境变量，也不读取任何文件：凭据与 base URL 只来自显式参数。

---

## 7. Amane Host 公共边界核查（设计期实证）

### 7.1 核查方法与坐标

设计期对 `https://github.com/sqzw-x/amane.git` 做 bare clone，并直接读取两个 release 的**源码树**（`git archive v0.15.0` / `git archive v0.18.0`），
而不是依赖他人的转述。以下事实都来自这两棵树；每一条在第 7.3 节标注了文件。

```text
git rev-parse v0.15.0           = 3292c957a092f85ddde1ba7462ffe9813827f4f1   (tag object)
git rev-parse v0.15.0^{commit}  = 45dff2159369883e028a296d775a4598836c1ddd
git rev-parse v0.18.0           = 7d2190704fa1e3c0f7f86889111d12b9fa6701c8   (tag object)
git rev-parse v0.18.0^{commit}  = 0a8a731d7746bde5e8828d1eb74c7bd9752b42e4
```

实现期必须在 S1 开始时重做一次同样的核查并把结果写进 HANDOFF（U6-6 的基线），P6 的 client 不做任何版本分支。

### 7.2 最小 endpoint 子集（表 H1，冻结；这是 P6 唯一允许的宿主表面）

所有路径都在 `/api` 前缀之下（`routes/__init__.py: API_PREFIX = "/api"`）。

| 操作 | 方法与路径 | 请求体（精确键集） | 成功响应 | 用途 |
|---|---|---|---|---|
| `submit` | `POST /api/tasks` | `{"type":"scrape","number":"FC2-<digits>","content_type":"fc2","use_cache":[]}` | **精确 `202`**，`TaskResponse` | 每个 aggregate 恰好一次，**永不重试** |
| `observe` | `GET /api/tasks/{task_id}` | — | `200`，`TaskResponse` | 有界轮询精确 id |
| `cancel` | `POST /api/tasks/batch` | `{"action":"cancel","task_ids":[<该 id>]}`（**不含** `status` / `type`） | `200`，`{affected,skipped,missing,submitted,task_ids}` | 仅在放弃 / 取消 / 超时时，精确到自己的任务 |
| `metadata` | `GET /api/metadata/{metadata_id}` | — | `200`，`MetadataDetailResponse`（只使用 `.metadata`） | 读取 DONE 任务产生的 Metadata |
| `probe` | `GET /api/tasks/worker` | — | `200`，`{"paused": bool}` | 仅门面 preflight（第 9.5 节），每次 preview 一次 |

**明确禁止的宿主表面**（静态守卫 + mutation 覆盖，M6-08 / M6-09）：

```text
POST /api/tasks 的其它 type（organize / trash / refresh / cleanup / upscale / r18_import / actor_scrape / rescrape）
POST /api/tasks 带 media_id / library_id / path / oshash 等任何本地标识
POST /api/tasks/batch 的 action = delete / retry；或带 status / type 过滤（会取消“别人的”任务）
GET /api/tasks（列表）、/api/tasks/{id}/children|report|record、/api/tasks/schema
/api/ws（WebSocket）、/api/config*（含 cookie / token）、/api/plugins*、/api/files*、/api/resources*、/api/media*、/api/libraries*
POST /api/metadata/batch/*、PUT / PATCH / DELETE 任何 metadata
```

### 7.3 逐项核查结果（表 H2）

| 事实 | v0.15.0（`45dff21…`） | v0.18.0（`0a8a731…`） | 结论 |
|---|---|---|---|
| 提交任务 | `src/amane/api/routes/tasks.py`：`@router.post("", status_code=202)` → `TaskResponse` | 同文件；除 `/batch` 处理函数的取消回调参数（`worker=` → `cancel_task=`）外逐字节相同 | 相同 |
| `TaskSubmission` 判别联合含 `ScrapeSubmission`（`type:"scrape"`，`number` / `media_id` / `content_type` / `use_cache`） | `api/models/tasks.py` | `api/models/tasks.py` **逐字节相同** | 相同 |
| `ScrapeRequest` 校验：`number` 与 `media_id` 至少一个；`number` 去空白；`content_type` 缺省则按番号推断 | 同上 | 同上 | 相同 |
| `use_cache: set[CacheKind]`，缺省 `{metadata, trans}`；`[]` = 全部强制刷新 | `handlers/models.py: CacheKind` | 同 | 相同 |
| 读取任务 | `GET /{task_id}` → `TaskResponse`（404 若不存在） | 相同 | 相同 |
| `TaskResponse` 字段 | `id,type,status,title,payload,result,error,log_file,retries,priority,root_task_id,child_*,created_at,started_at,finished_at`；**无 progress 字段** | `api/models/tasks.py` 相同 | 相同；见第 17 节 |
| `TaskStatus` | `db/models.py`：`QUEUED / RUNNING / DONE / FAILED`（**没有 CANCELLED**） | 相同 | 相同；取消的终态是 `FAILED`（第 10 节） |
| 精确 id 取消 | `POST /tasks/batch` → `support/task_batch.py: execute_task_batch(task_ids=…)`：QUEUED → `repo.fail_queued_tasks(task_ids)`；RUNNING → `worker.cancel_task(id)`，失败则 `repo.fail_task(id, "Cancelled by user")` | 同入口；RUNNING → `runtime.cancel_task`，回退用 `repo.fail_running_task`（**不覆盖已终态**） | **DIFF-P6-01**（第 7.4 节） |
| `task_ids` 与 `status/type` 互斥 | `TaskBatchRequest._exclusive_scope` | 相同 | 相同 |
| 响应 `TaskBatchResponse{affected,skipped,missing,submitted,task_ids}` | 是 | 是 | 相同 |
| 认证 | `api/middleware.py: TokenAuthMiddleware`：`Authorization: Bearer <token>` 或同值 HttpOnly cookie `amane_token`；`runtime.api_token is None` = 关闭；`/api/health` 豁免；失败 `401` | **逐字节相同** | 相同 |
| 认证成功后服务器 `Set-Cookie: amane_token` | 是 | 是 | client 必须**丢弃**（第 8.3 节） |
| SCRAPE 结果 | `handlers/scrape.py: ScrapeResult{metadata_id:int, field_sources:dict[str,str], failed_sites:list[str]}` | `handlers/models.py` 相同 | 相同 |
| `field_sources` 的值 = route 中的站点 id（插件即 `ffcc.fc2-metadata`），键 = `MetadataField` 值（`title` / `poster_urls` …） | `aggregate/engine.py`、`enums.py: MetadataField` | 相同 | 相同；用于归属校验（第 11.3 节） |
| SCRAPE 空结果 | `if not result.field_sources:` → 任务 FAILED（"No metadata found"） | `if not result.raw:` → 标量可全空仍 DONE | **DIFF-P6-02**：v0.18.0 可能 DONE 但没有 title（第 11.2 节会 fail closed） |
| Metadata 详情 | `GET /api/metadata/{metadata_id}` → `MetadataDetailResponse{metadata: MetadataResponse,…}`；404 若不存在 | 相同路由与外层模型 | 相同 |
| `MetadataResponse` | 含 `number,title,actors,studio,publisher,release,runtime,tags,plot,poster_urls,thumb_urls,extrafanart,extrafanart_urls,source_urls,external_ids,field_sources,raw,…` | 相同，**多** `locked_fields` | **DIFF-P6-03**：client 为容忍额外键的 reader |
| Worker 暂停状态 | `GET /tasks/worker` → `{paused}`；`POST /tasks/worker/pause|resume` | 相同 | 相同；P6 只读 |
| SCRAPE 可能自行物化 Resource | `handlers/scrape.py` → `media.materialize_images`，受 `scraping.download_resources`（缺省含 poster / thumb / extrafanart…）控制；`crop_poster` 缺省 True 时 poster 可能被替换为宿主内部 URL（`/api/resources/<hash>`） | 相同 | **DIFF-P6-04** 之外的共同事实；第 18 节 |
| SCRAPE 可能扇出 `ACTOR_SCRAPE` 后继任务 | `actor_scraping.auto_scrape` 缺省 `True` | 相同 | 宿主拥有；第 27 节 L6-08 |
| `ContentType.FC2 = "fc2"` | `parsing/file_info.py` | 相同 | 相同 |

### 7.4 版本差异白名单（只允许这四项；出现其它差异 = U6-6）

| ID | 差异 | P6 处理 |
|---|---|---|
| DIFF-P6-01 | 取消 RUNNING 任务的回退：v0.15.0 用无条件的 `repo.fail_task`（可能把“刚好完成的任务”改写成 FAILED / “Cancelled by user”）；v0.18.0 用 `fail_running_task`（不覆盖终态） | P6 不依赖任何一种：取消路径只用“取消请求之后观察到的结构化终态”（第 10.3 节），不读 `error` 文本；v0.15.0 的改写窗口记入 L6-04 |
| DIFF-P6-02 | v0.18.0 的 SCRAPE 在标量全空时仍可 DONE | 第 11.2 节最低成功门 fail closed（`HOST_METADATA_BELOW_MINIMUM`） |
| DIFF-P6-03 | v0.18.0 的 `MetadataResponse` 多 `locked_fields` | 严格 reader 只要求第 8.5 节的必需键，**忽略**额外键 |
| DIFF-P6-04 | 内部实现：v0.15.0 `worker.cancel_task`（只看 `_running_tasks`）；v0.18.0 `runtime.cancel_task`（`app/runtime.py`：先问当前 worker，再问被退役的旧 worker `_retiring`，覆盖宿主重建 worker 期间仍在运行的任务） | 对 public 表面不可见；P6 只依赖取消后观察到的结构化终态；仅记录 |

### 7.5 P6 不使用的宿主能力（理由）

* **WebSocket 进度**：`/api/ws` 的认证走 cookie / 握手，且 P4-C8 §11.4 没有进度契约；不引入（第 17 节）。
* **Task 列表过滤**：无按 number 过滤；用来“找回丢失提交的任务”会命中用户自己的同号任务，违反“只操作自己的任务”。放弃找回，改为显式的 `submission_ambiguous`（第 10.4 节）。
* **`/api/config`**：返回 site cookie / token；生产代码零读取（U6-5）。验收宿主的配置回读只发生在测试工具里（第 22 节）。
* **`/api/tasks/batch` retry**：会创建新任务并与 P4 重试相乘；禁止。

### 7.6 宿主前置条件（P6 的正确性假设；违反时 fail closed，不静默降级）

```text
H6-1  宿主的 FC2 内容 route 恰好是 [ffcc.fc2-metadata]（独占 route）。
      P6 不读取、不修改宿主配置；它用每个任务结果里的结构化 field_sources 做逐条归属校验（第 11.3 节）。route 含其它站点且其中任何站点贡献了字段
      → 该条目 fail closed（HOST_ATTRIBUTION_FOREIGN）。P5 INSTALL 把插件放在 route 最前并保留原站点——P6 需要把其它站点移出该 route（见 L6-01）。
H6-2  宿主任务 worker 未暂停（preflight 检查；暂停时 SCRAPE 永远 QUEUED）。
H6-3  宿主 token 与 P6 凭据一致（401/403 → 结构化 BLOCKED 失败；preflight 提前拒绝）。
H6-4  用户同意“SCRAPE 会把结果写入 Amane 的 Metadata 库”（AmaneHostConfig.acknowledge_host_metadata_writes=True，第 8.2 节）。
H6-5  宿主 base URL 是 origin（scheme://host[:port]），无路径前缀（反向代理路径前缀不在 P6-C1 范围）。
```

---

## 8. Host Client（`AmaneHostClient`；冻结）

### 8.1 提交体（精确键集，静态 + 运行时双重校验）

```json
{"type": "scrape", "number": "FC2-1234567", "content_type": "fc2", "use_cache": []}
```

* 键集**恰好**这四个；任何其它键（尤其 `media_id`、路径、hash）= 实现缺陷（测试用请求账本逐键断言）。
* `number` 必须先通过 `require_canonical_number`（Core）；非规范号 → `InvalidCanonicalNumberInputError`（调用方 bug，零网络）。
* `use_cache: []`（强制刷新）的理由：宿主缺省会复用 DB 中既有的 per-site 快照（可能由**其它**爬虫写入），那样结果就不能归属于
  `ffcc.fc2-metadata`；强制刷新让每个 aggregate 的元数据都来自本次 route 内的站点。

### 8.2 `AmaneHostConfig`（不可变；构造即校验；零 I/O）

| 字段 | 类型 / 范围 | 缺省 | 说明 |
|---|---|---|---|
| `base_url` | `str`；origin only | 必填 | 先过 Core `validate_base_url`（无 userinfo / query / fragment / 控制字符），再要求 path ∈ {"", "/"}；去掉尾部 `/`。`https` 任意主机；`http` **仅**回环（`127.0.0.0/8` / `::1` / `localhost`）。非回环 `http` → `AmaneBatchConfigError`（不提供关闭开关；L6-02） |
| `credential` | `AmaneHostCredential \| None` | 必填（可显式 `None`） | `None` = 宿主关闭了 token 校验（`AMANE_TOKEN=off`） |
| `request_timeout_seconds` | `float`，`0 < x ≤ 120` | `15.0` | 单个 HTTP 请求（连接 + 读取）的墙钟上限 |
| `poll_interval_seconds` | `float`，`0.05 ≤ x ≤ 10` | `0.5` | 观察间隔 |
| `aggregate_deadline_seconds` | `float`，`1 ≤ x ≤ 3600` | `300.0` | 一次 aggregate 从提交开始的总墙钟预算（**含宿主排队时间**） |
| `cancel_budget_seconds` | `float`，`0.5 ≤ x ≤ 60` | `10.0` | 一次取消 / 放弃清理的总预算（第 10 节） |
| `max_consecutive_poll_errors` | `int`，`1..10` | `3` | 连续观察失败的容忍次数（仅对幂等 GET；第 9.3 节） |
| `acknowledge_host_metadata_writes` | `bool`，**必须为 `True`** | `False` | 显式承认“SCRAPE 会向 Amane Metadata 库 upsert 数据”；`False` → `AmaneBatchConfigError` |

没有 `verify_tls` / `proxy` / `follow_redirects` / `retries` / `concurrency` / `cookies` / `headers` 旋钮：它们是冻结语义，不是选项。
并发预算只有一个来源：`OrchestrationConfig.metadata.max_in_flight_items`（第 14 节）。

### 8.3 `AmaneHostCredential` 与传输安全

```text
AmaneHostCredential(token: str)
  token：非空 str，仅可打印 ASCII（0x21..0x7E），无空白，长度 ≤ 512；违反 → AmaneBatchConfigError（异常文本不含 token）
  __repr__ / __str__ / __format__ → "AmaneHostCredential(<redacted>)"
  __reduce__ / __reduce_ex__ / __getstate__ / __copy__ / __deepcopy__ → TypeError（不可序列化、不可复制；永不落盘）
  __eq__ / __hash__ → 对象身份（不比较 token）
  取值只发生在 host_client 内部构造 Authorization 头的那一行
```

| 规则 | 要求 |
|---|---|
| 显式注入 | 凭据只来自参数；包内**零**环境变量读取、零文件读取、零 `.netrc` |
| 不持久化 | 不写盘、不写日志（本包**零 logging**）、不进入 `repr` / 异常文本 / `__cause__` 链 / `BatchPreview` / 汇总 / 审计 / 诊断 |
| 不泄漏异常 | httpx 异常对象携带 `request`（含 `Authorization` 头）：所有 httpx 异常在边界被**翻译**为 `HostFailureKind` 并以 `raise … from None` 抛出 / 丢弃；异常对象本身永不保存进审计、结果或日志 |
| 无环境代理 | `httpx.AsyncClient(trust_env=False)`：忽略 `HTTP_PROXY` / `ALL_PROXY` / `NO_PROXY` / `SSL_CERT_*` / `.netrc` |
| 无 cookie | 宿主在认证成功后会 `Set-Cookie: amane_token`（两个版本）。client 使用“拒绝一切 cookie”的 cookie jar：`client.cookies` 在任何响应之后保持为空；后续请求**不**带 `Cookie` 头 |
| 无重定向 | `follow_redirects=False`；任何 `3xx` → `HOST_HTTP_UNEXPECTED`；因此凭据永不会被带到另一个 origin |
| TLS | `https` 使用 httpx 缺省证书校验；**不存在**关闭校验的参数；证书 / 握手失败 → `HOST_CONNECTION`（结构上无法降级为明文） |
| 明文策略 | 非回环主机必须 `https`（第 8.2 节） |
| 请求头 | 只有 `Authorization`（若有凭据）、`Accept: application/json`、`Content-Type: application/json`（POST）、固定 `User-Agent: fc2-amane-batch/0.1` |
| 连接池 | 有界（`max_connections ≤ 66`，不随批量大小增长）；一个 `AsyncClient` per `AmaneHostClient`（构造时创建，**不**在 import 时创建；`aclose()` 幂等） |

### 8.4 响应处理

* 响应体**流式读取**并设上限 `MAX_RESPONSE_BYTES = 8 * 1024 * 1024`；超限 → `HOST_RESPONSE_TOO_LARGE`（不读完）。
* 只接受 `application/json` 内容（或无 `content-type` 但可被严格 JSON 解析）；JSON 解析使用拒绝 `NaN` / `Infinity` 的严格模式。
* 状态码：`submit` 必须是 `202`；其它四个操作必须是 `200`。其它 `2xx` → `HOST_HTTP_UNEXPECTED`；`401/403` → `HOST_AUTH_REJECTED`；`429` →
  `HOST_RATE_LIMITED`；`5xx` → `HOST_SERVER_ERROR`；`404` 见各操作；其它 `4xx` / `3xx` / `1xx` → `HOST_HTTP_UNEXPECTED`。
* **宿主返回的任何文本**（`error`、`detail`、响应体、日志）都不进入控制逻辑、不进入异常、不进入结果、不进入审计。解析 `error` 字段只用于类型校验，
  之后立即丢弃。

### 8.5 严格 reader（`_wire.py`）

* `HostTask`：必需 `id`（`int`，非 `bool`，`≥ 1`）、`type`（`str`）、`status`（`"queued"|"running"|"done"|"failed"`）、`payload`（`dict`）、
  `result`（`dict | None`）；`error`（`str | None`，只验类型、不保留）。额外键忽略。
* `HostBatchCancelResult`：必需 `affected` / `skipped` / `missing`（非负 `int`，非 `bool`）。
* `HostMetadata`：必需 `id:int`、`number:str`、`title:str|None`、`actors:list[str]`、`studio/publisher/release/plot:str|None`、`runtime:int|None`、
  `tags:list[str]`、`poster_urls/thumb_urls/extrafanart:list[str]`、`source_urls/external_ids:dict`；额外键（含 v0.18.0 的 `locked_fields`、`raw`、`field_sources`）忽略。
* 任一必需键缺失 / 类型不符 → `HOST_SCHEMA_INVALID`（不猜测、不修复、不部分接受）。

---

## 9. Host Task 生命周期（冻结）

### 9.1 状态机（每个 aggregate 一个实例）

```text
SUBMITTING ──202 + echo 校验通过──► OBSERVING ──status=done──► FETCHING_METADATA ──映射成功──► SUCCESS
    │                                  │  │                              │
    │ 请求失败 / 非 202 / echo 失败      │  │ status=failed                │ 任何映射 / 取回失败
    ▼                                  │  ▼                              ▼
 FAILED(HostFailureKind)                │ FAILED(HOST_TASK_FAILED)     FAILED(HostFailureKind)
                                       │
                          deadline 到期 / 连续观察失败 / 取消 / 未预期异常
                                       ▼
                                  ABANDONING ──有界清理（第 10 节）──► FAILED(…) 或 重新抛出 CancelledError
```

* 终态只有三种：`SUCCESS`（返回 SUCCESS `AggregationResult`）、`FAILED`（返回 FAILED `AggregationResult`，**不抛**）、取消（有界清理后重新抛 `CancelledError`）。
* `observe` 的终态判定**只**读取结构化 `status`：`done` / `failed`；`queued` / `running` 继续观察。

### 9.2 提交（`submit`）

1. 记录 `started = clock()`（单调时钟），分配审计 `seq`。
2. 发送 `POST /api/tasks`（第 8.1 节）。**恰好一次，永不重试**——重试一次非幂等创建会产生重复任务。
3. 必须 `202` 且 `HostTask` 通过严格 reader；并做 **echo 校验**：`type == "scrape"`、`payload.number == number`、`payload.content_type == "fc2"`。
   不符 → `HOST_SCHEMA_INVALID`（此时任务 id 已知 → 进入 ABANDONING 清理，因为宿主可能真的创建了任务）。
4. 请求在响应到达之前失败（超时 / 连接中断）→ **`submission_ambiguous = True`**：宿主可能已创建任务而 P6 不知道 id。P6 **不**尝试找回（第 7.5 节）；
   结果为 `FAILED(HOST_TIMEOUT / HOST_CONNECTION / …)`，审计标记 `submission_ambiguous`，取消结果 `UNCERTAIN_SUBMISSION_UNRESOLVED`（不是“没有任务”）。

### 9.3 观察（`observe`）

```text
loop:
    GET /api/tasks/{id}
    成功 → 重置连续错误计数；status ∈ {done, failed} → 终态；否则继续
    失败（HostFailureKind ∈ {TIMEOUT, CONNECTION, NETWORK, SERVER_ERROR, HTTP_UNEXPECTED, RESPONSE_TOO_LARGE, SCHEMA_INVALID, TASK_VANISHED(404)}）
        → 连续错误计数 +1；达到 max_consecutive_poll_errors → ABANDONING（TASK_VANISHED 立即终止，不重试）
    HOST_AUTH_REJECTED（401/403）→ 立即 ABANDONING（凭据问题不会被重试修复）
    若 clock() - started ≥ aggregate_deadline_seconds → ABANDONING(HOST_DEADLINE)
    await sleep(min(poll_interval, 剩余 deadline))
```

* 至少执行一次 `GET`（即使 deadline 极小），避免“刚提交就判超时而没有机会观察到 done”。
* 观察失败重试是**对幂等 GET 的有界重复观察**，不重复执行工作，不创建任务，因而不构成“第二个批量重试所有者”（第 13 节）。
* 一次 aggregate 的请求数上界：`1`（submit）+ `⌈deadline / poll_interval⌉ + max_consecutive_poll_errors`（observe）+ `1`（metadata）+ 清理预算内的请求。

### 9.4 终态处理

* `status == "failed"`（且 P6 **没有**发出过取消）→ `FAILED(HOST_TASK_FAILED)`。**不**读取 `error` 文本，因此无法区分“番号不存在”与“来源故障”（L6-05）。
* `status == "done"`：
  1. `result` 必须是 `dict`，且含 `metadata_id`（`int`，非 `bool`，`≥ 1`）、`field_sources`（`dict[str,str]`）、`failed_sites`（`list[str]`）；否则
     `HOST_RESULT_INVALID`（“DONE 但缺 metadata_id / 结果结构非法”）。
  2. 归属校验（第 11.3 节）。
  3. `GET /api/metadata/{metadata_id}`（单次，不重试）。`404` → `HOST_METADATA_MISSING`；其它失败按第 8.4 节映射。
  4. 映射（第 11 节）。

### 9.5 门面 preflight（`AmaneHostClient.probe_worker`）

`AmaneBatchIntegration.preview / preview_root` 在做任何 item 工作之前执行**一次** `GET /api/tasks/worker`：

| 结果 | 行为 |
|---|---|
| `200 {"paused": false}` | 继续 |
| `200 {"paused": true}` | `AmaneHostPreflightError(WORKER_PAUSED)`（零副作用） |
| `401/403` | `AmaneHostPreflightError(AUTH_REJECTED)` |
| 超时 / 连接失败 | `AmaneHostPreflightError(HOST_UNREACHABLE)` |
| 其它 / 结构不符 | `AmaneHostPreflightError(PROTOCOL_MISMATCH)` |

引擎本身不做 preflight（便于直接注入与单测）。preflight 是**整批前置条件**，在任何任务被创建之前失败，因此不违反“单个条目失败不得拖垮整批”。

---

## 10. 取消合同（冻结）

### 10.1 所有权

* 取消**只**针对 P6 自己创建、并且已知 id 的那一个任务；动作是 `POST /api/tasks/batch {"action":"cancel","task_ids":[id]}`。
* 请求体里**永远不得**出现 `status` / `type`（宿主会把它解释成“取消所有 running 的 scrape”）；永远不得使用 `delete` / `retry`。
* 取消触发源：调用方取消（`CancelledError`）、批量取消（P4 TaskGroup 拆除）、deadline 到期、连续观察失败、echo 校验失败、未预期异常。
  **没有**其它触发源。

### 10.2 清理预算（bounded behavior）

清理在自己的预算里运行，预算是 `cancel_budget_seconds`（总计，不是每个请求）：

```text
1. 若提交请求仍在途（SUBMITTING 期间收到取消）：最多等待 min(剩余预算, request_timeout) 取得响应，使得“如果任务已创建，我们能拿到它的 id”。
   —— 拿不到响应 → UNCERTAIN_SUBMISSION_UNRESOLVED（不是“没有任务”）。
2. 发送一次精确取消请求（超时 = min(request_timeout, 剩余预算)）。
3. 以 poll_interval 观察该 id，直到终态或预算耗尽。
4. 返回 CancelOutcome（第 10.3 节）。
```

* 清理在一个独立的、有界的 task 里运行，并被 shield 以免被同一次取消打断；**无任何分离（detached）的后台 task**：当 `aggregate` 返回或抛出时，
  清理 task 已经完成或已被取消并 await（测试：事件循环里没有残留 task）。
* 第二次取消打断清理 → `UNCERTAIN_CLEANUP_INTERRUPTED`，然后传播。
* 取消不会无限等待：单个 aggregate 的取消延迟上界 ≈ `cancel_budget_seconds`；P4 TaskGroup 并发取消所有 worker，因此整批拆除上界同样 ≈
  `cancel_budget_seconds`（外加调度抖动）。
* 非 `Exception` 的 `BaseException`（`KeyboardInterrupt` / `SystemExit` / `GeneratorExit`）：**不**做任何清理 I/O，原样传播；审计记为 `UNCERTAIN_CLEANUP_INTERRUPTED`（未做任何清理）
  （P4 的致命语义不被改变）。

### 10.3 `CancelOutcome`（封闭枚举；全部来自结构化观察）

| 值 | 含义 | 观察依据 |
|---|---|---|
| `NOT_APPLICABLE` | 没有任务需要取消（取消发生在 `POST` 之前） | 请求账本里没有 submit |
| `CONFIRMED_STOPPED` | 取消请求之后，观察到该 id 的结构化终态 `failed` | `status == "failed"` |
| `COMPLETED_BEFORE_CANCEL` | 观察到终态 `done`（任务在取消生效前完成；宿主已写入 Metadata） | `status == "done"` |
| `UNCERTAIN_NO_RESPONSE` | 取消请求超时 / 连接失败 / 非预期响应 | 传输 / 状态码 |
| `UNCERTAIN_NOT_TERMINAL` | 取消请求已确认，但预算耗尽时任务仍是 `queued` / `running` | 结构化 `status` |
| `UNCERTAIN_SUBMISSION_UNRESOLVED` | 提交请求被取消 / 超时，任务 id 从未获得 | 无 id |
| `UNCERTAIN_TASK_VANISHED` | 取消响应 `missing ≥ 1` 或观察得到 `404` | 结构化计数 / 状态码 |
| `UNCERTAIN_CLEANUP_INTERRUPTED` | 清理被第二次取消打断 | 控制流 |

* “已发送取消请求”**不等于**“任务一定停了”：只有 `CONFIRMED_STOPPED` / `COMPLETED_BEFORE_CANCEL` 是已确认的；其余 `UNCERTAIN_*` 必须在审计里明确
  标注并计入 `uncertain_cancellations`。**不得**写成“已停止”。
* `CONFIRMED_STOPPED` 不区分“因我们取消而 failed”和“恰好自己 failed”——两者对 P6 都意味着“任务已不再运行”，这就是需要的全部信息。不读 `error` 文本。

### 10.4 语义级取消与“不确定”的暴露

* P4 `preview` 被取消：`CancelledError` 原样传播，**不返回部分 preview**（P4 §20.2）。因此取消结果只能通过**审计快照**观察
  （`AmaneBatchIntegration.audit_snapshot()` 在取消后仍可调用）。
* “cancel before admission”：在任何 worker 被准入之前取消（P4 的 `admission_open()` 保证不再准入）→ 零 `POST`，审计无记录。
* 取消不确定性是**一等输出**：`AmaneHostAuditSnapshot.uncertain_cancellations > 0` 时，门面文档与 HANDOFF 要求调用方向用户呈现
  “可能仍有未停止的 Amane SCRAPE 任务”。

---

## 11. Host → Core 桥（冻结；fail closed）

### 11.1 构造什么

* 成功路径：一个合法的 `SourceResult(source_id="ffcc.fc2-metadata", status=SUCCESS, metadata=<NormalizedMetadata>, elapsed_ms=<测量值>)`，
  再构造 `AggregationResult(number, status=SUCCESS, metadata, source_results=(那一个 SourceResult,), contributing_source_ids=("ffcc.fc2-metadata",),
  conflicts=(), disabled_source_ids=(), elapsed_ms, source_execution_traces=())`。
* `source boundary ID` 恒为 `PLUGIN_SOURCE_ID = "ffcc.fc2-metadata"`（常量；测试与 `adapters/amane/fc2_amane_adapter/_settings.py: PLUGIN_ID` 逐字对账）。
* `source_execution_traces` 为空（“纯合并、无执行”，Core 合同允许）：P6 没有运行任何 Core source execution，不得伪造 trace。
* **P6 永远不产生 `AggregateStatus.PARTIAL`**：`PARTIAL` 要求至少一个 SourceResult 是运行性失败，而 P6 只有一个 SourceResult；跨过 P5 边界后，
  内部 JavDB / fc2db_net / av123 的逐来源状态已经丢失，**不得重建**（第 15 节）。因此 `ItemWarning.METADATA_PARTIAL` 在 P6 流程中不会出现。

### 11.2 成功路径的校验清单（缺一即 fail closed，且只能选下列失败种类之一）

按顺序：

| # | 校验 | 失败种类 |
|---|---|---|
| 1 | 任务终态 `done`（第 9.4 节） | `HOST_TASK_FAILED`（`failed`）/ 继续观察 |
| 2 | `result` 结构合法且含合法 `metadata_id` | `HOST_RESULT_INVALID` |
| 3 | 归属校验（第 11.3 节） | `HOST_ATTRIBUTION_FOREIGN` |
| 4 | `GET /metadata/{id}` 返回 200 且 `HostMetadata` 严格 reader 通过 | `HOST_METADATA_MISSING`（404）/ `HOST_SCHEMA_INVALID` |
| 5 | `normalize_fc2_number(metadata.number)` 为 `RECOGNIZED` 且 `canonical == 请求的 canonical` | `HOST_METADATA_NUMBER_MISMATCH` |
| 6 | 字段映射（第 11.4 节）通过，`NormalizedMetadata` 构造成功 | `HOST_METADATA_CONTRACT` |
| 7 | `NormalizedMetadata.meets_minimum_success()` | `HOST_METADATA_BELOW_MINIMUM` |

* 第 5 步使用 Core 的 `normalize_fc2_number`（不是第二个解析器）：宿主的 Metadata 唯一键大小写不敏感，用户先前以别的写法保存过同一番号时仍应等价；
  构造出的 `NormalizedMetadata.number` **一律是请求的 canonical**。
* 第 7 步对应 DIFF-P6-02：v0.18.0 可能 `done` 但没有 title。

### 11.3 归属校验（FC2 route ownership 的运行时证明）

`result.field_sources`（宿主在 SCRAPE 完成时写入的“字段 → 站点 id”结构化映射）必须满足：

```text
非空；"title" ∈ keys；所有 values == "ffcc.fc2-metadata"
```

任何其它站点 id 出现，或 `title` 没有归属，都意味着“这条元数据不能声称来自 ffcc.fc2-metadata”→ `HOST_ATTRIBUTION_FOREIGN`（fail closed）。
这把“最后有 Metadata”替换成了**每个条目**的结构化归属证明；验收环境另外用 route 回读与上游请求账本做互相印证（第 22 节）。

### 11.4 字段映射表（冻结；守卫测试穷举 `HostMetadata` 与 `NormalizedMetadata` 的字段集合）

| `NormalizedMetadata` 字段 | 来源 | 规则 |
|---|---|---|
| `number` | 请求的 canonical | 固定 |
| `title` | `title` | 原样；`None` / 空白 → 第 7 步失败 |
| `studio` / `publisher` / `release` / `plot` | 同名 | `str \| None` 原样（`release` 的合法性由 P4 NFO 渲染负责） |
| `runtime` | `runtime` | `int \| None`，负数 → `HOST_METADATA_CONTRACT` |
| `actors` / `tags` | 同名 | 保持宿主顺序；元素必须是 `str`，否则 `HOST_METADATA_CONTRACT` |
| `poster_urls` / `thumb_urls` / `extrafanart` | 同名 | 仅保留“干净的绝对 http(s) URL”（有 host、无控制字符、无首尾空白；与 P5 I22 规则同义，测试逐样本对账）；**被剔除的数量记入审计 `dropped_url_count`**，不静默 |
| `fanart_urls` | — | 空元组（Amane 无此概念，P5 同） |
| `source_urls` | `source_urls`（dict） | 按键排序后取值，保留干净 http(s) URL |
| `external_ids` | `external_ids`（dict） | 仅保留键值均为非空 `str` 的条目（键为宿主站点 id，如 `ffcc.fc2-metadata`） |
| `field_sources` | 派生 | 对每个**非空**的已映射字段 `f`：`{f: ("ffcc.fc2-metadata",)}`（值必须 ⊆ `contributing_source_ids`，P4-C9 诊断校验要求） |
| （宿主字段）`series` / `directors` / `trailer_urls` / `score` / `locked_fields` / `raw` / `extrafanart_urls` / `id` / `file_*` / 时间戳 | — | **不映射**（Core 无对应字段或属宿主运维信息）；`metadata_id` 仅进入审计 |

* 容器类型不对（例如 `actors` 不是 list）= schema 违规 → fail closed；元素级的 URL 卫生是确定性过滤（并计数），不是失败。
* 映射是**纯函数**：同样的 `HostMetadata` 总得到同样的 `NormalizedMetadata`；不读取时钟、随机数、环境。

### 11.5 用户自己的 Amane 配置会流入结果（诚实声明）

宿主在写库前会应用用户的 Amane 设置（FacetRule 规范化 actors / tags、LLM 翻译 title / plot、v0.18.0 的字段锁、Resource 物化）。P6 映射的是
**宿主持久化后的 Metadata**，不声称它与插件原始输出逐字节相同——**验收宿主**使用无翻译、无锁、无 FacetRule、禁止物化的配置，在该配置下逐字段可对账。
生产环境里这些用户配置的影响记入 L6-06。

---

## 12. 失败映射（冻结；全部基于结构化信号）

### 12.1 `HostFailureKind` → Core 结构化失败（唯一映射表）

所有失败都构造 `FAILED AggregationResult`：`metadata=None`，`source_results=(SourceResult(source_id="ffcc.fc2-metadata", status, None, elapsed_ms, error_kind,
error_detail),)`，`contributing_source_ids=()`。`error_detail` 是**封闭词汇**：`"amane host: " + <HostFailureKind.value>`，绝不含 URL / 宿主文本 / token / 任务 id。

| `HostFailureKind` | 结构化触发 | `SourceStatus` | `SourceErrorKind` |
|---|---|---|---|
| `HOST_TIMEOUT` | `httpx.TimeoutException`（含 Connect / Read / Write / Pool Timeout） | `NETWORK_ERROR` | `TIMEOUT` |
| `HOST_CONNECTION` | `httpx.ConnectError`（含 DNS / 拒绝连接 / TLS 握手与证书失败） | `NETWORK_ERROR` | `CONNECTION_ERROR` |
| `HOST_NETWORK` | 其它 `httpx.TransportError` / `httpx.StreamError` / `httpx.DecodingError` / `httpx.TooManyRedirects` | `NETWORK_ERROR` | `NETWORK_ERROR` |
| `HOST_AUTH_REJECTED` | HTTP `401` / `403` | `BLOCKED` | `BLOCKED` |
| `HOST_RATE_LIMITED` | HTTP `429` | `RATE_LIMITED` | `RATE_LIMITED` |
| `HOST_SERVER_ERROR` | HTTP `5xx` | `INVALID_RESPONSE` | `HTTP_SERVER_ERROR` |
| `HOST_HTTP_UNEXPECTED` | 其它 `4xx` / `3xx` / `1xx` / 非预期 `2xx` | `INVALID_RESPONSE` | `INVALID_RESPONSE` |
| `HOST_RESPONSE_TOO_LARGE` | 响应体超过 `MAX_RESPONSE_BYTES` | `INVALID_RESPONSE` | `RESPONSE_TOO_LARGE` |
| `HOST_SCHEMA_INVALID` | 非 JSON / 严格 reader 违规 / echo 校验失败 | `INVALID_RESPONSE` | `INVALID_RESPONSE` |
| `HOST_TASK_VANISHED` | 观察时 `404`（任务被用户 / 宿主删除） | `INVALID_RESPONSE` | `INVALID_RESPONSE` |
| `HOST_TASK_FAILED` | 观察到终态 `failed`（P6 未发出取消） | `INVALID_RESPONSE` | `ADAPTER_EXCEPTION` |
| `HOST_DEADLINE` | `aggregate_deadline_seconds` 到期（随后有界清理） | `NETWORK_ERROR` | `SOURCE_DEADLINE` |
| `HOST_RESULT_INVALID` | `done` 但 `result` 缺失 / 缺 `metadata_id` / 类型非法 | `INVALID_RESPONSE` | `RESULT_CONTRACT_MISMATCH` |
| `HOST_ATTRIBUTION_FOREIGN` | `field_sources` 含其它站点或缺 `title` | `INVALID_RESPONSE` | `RESULT_CONTRACT_MISMATCH` |
| `HOST_METADATA_MISSING` | `GET /metadata/{id}` → `404` | `INVALID_RESPONSE` | `RESULT_CONTRACT_MISMATCH` |
| `HOST_METADATA_NUMBER_MISMATCH` | 第 11.2 节第 5 步 | `INVALID_RESPONSE` | `RESULT_CONTRACT_MISMATCH` |
| `HOST_METADATA_CONTRACT` | 字段类型 / 构造 `NormalizedMetadata` 被拒 | `INVALID_RESPONSE` | `RESULT_CONTRACT_MISMATCH` |
| `HOST_METADATA_BELOW_MINIMUM` | 不满足 minimum success | `INVALID_RESPONSE` | `RESULT_CONTRACT_MISMATCH` |

* 每个 `(SourceStatus, SourceErrorKind)` 配对都在 Core 的 `ALLOWED_ERROR_KINDS` 内（测试穷举验证）。
* **无法证明的细分类一律不猜**：例如无法区分“番号在所有来源都不存在”与“来源故障”（宿主只给 `failed` + 文本），统一为 `HOST_TASK_FAILED`；P6 从不产生
  `NOT_FOUND`。
* **不存在**基于子串 / 正则 / 日志 / 异常消息的分支（AST 守卫：控制流中不得出现对 `error` / `detail` / `str(exc)` / `exc.args` 的比较或匹配）。
* 非 `Exception` 的 `BaseException` 不被映射，保持 P4 致命语义；P6 自身的编程错误（`AmaneBatchContractError`）作为普通 `Exception` 抛出，
  由 P4 隔离为 `METADATA_ENGINE_FAILURE`（`error_type` = 类名），并仍执行有界清理。

---

## 13. 重试所有权（冻结：唯一的批量重试所有者）

### 13.1 三层重试的归属

| 层 | 所有者 | P6-C1 的态度 |
|---|---|---|
| 宿主 `WebClient` 的传输级重试（插件向来源站点发请求时） | Amane / P5 已冻结 | 不触碰；P6 不感知 |
| Core 语义级来源重试 | **disabled**（P5 冻结：`RetryPolicy.no_retry()`） | 不触碰 |
| 条目级重试（再次获取失败条目的元数据） | **P4 `BatchOrchestrator`**（唯一所有者） | 见 13.2 |
| `POST /api/tasks` 的重试 | **无人**（永不重试） | 第 9.2 节 |
| 观察 `GET` 的有界重复 | engine（只重复幂等观察，不重复工作） | 第 9.3 节 |
| Amane `POST /tasks/batch` 的 `retry` / `delete` | **永不使用** | 第 7.2 节 |

冻结：**一次 P6 aggregate 尝试 = 恰好一个新的 Amane SCRAPE 任务。**

### 13.2 设计期发现 F-1：P4 `preview_retry` 在“禁止 execute”的 Phase 6 中不可用

`BatchOrchestrator.preview_retry(previous, *, scope=None)` 的 `previous` 必须是一个**完整的 `BatchExecutionResult`**（`retry.py` 步骤 2
“exact complete previous result”，其 `RetryMaterial` / `retry_kind` / `result_id` 注册全部来自 `execute`）。而 Phase 6 的安全不变量是**绝不调用
`execute`**（第 19 节）。用 `execute(preview, selection=frozenset())` 绕过会违反该不变量的字面（并且会消费 preview），伪造 `BatchExecutionResult`
则是重建 CLOSED 模型——两者都被禁止。

**冻结裁决（保持“P4 是唯一的批量重试所有者”）**：失败子集重试 = 对失败条目的**原始 `DiscoveredMediaItem`** 再调用一次同一个
`BatchOrchestrator.preview(subset)`。

* P6 **只做子集选择**（一个纯函数，输入是上一轮已有的 `ItemPreview`），不运行任何 scheduler、不重试、不循环。
* 真正重新执行元数据获取、planning、图片、NFO、预检的仍然是 P4 `preview`；并发预算仍然是 P4 `BatchScheduler`。
* 不修改 P4。不引入第二套 scheduler。不使用 `preview_retry` / `merge_retry` / `RetryMaterial`（它们只对 `execute` 之后的结果有意义；Phase 7 引入 `execute` 后沿用 P4 原有机制）。

### 13.3 `AmaneBatchIntegration.retry_failed(previous) -> AmaneBatchPreview`

1. busy-first：与 P4 一致（委托 P4 的 busy 守卫；P6 不新增锁）。
2. `previous` 必须是 `type(previous) is AmaneBatchPreview`，且最新一轮的 `library_root` / `output_policy` / `image_policy` 与门面一致，否则
   `AmaneBatchRetryError(FOREIGN_PREVIEW)`。
3. **可重试集合 R**（纯函数，按原始下标升序）：最新视图中，`ItemPreview.state is UNPREPARED` 且 `issue.stage is METADATA` 且
   `issue.reason ∈ {METADATA_UNAVAILABLE, METADATA_ENGINE_FAILURE}` 的条目。
   * 成功条目（READY / BLOCKED / 其它阶段的 UNPREPARED）**不会**被重跑：它们的元数据是确定的，重取不会改变 planning / 冲突 / 预检结论。
   * 图片候选级部分失败是 P4 的**警告**（`IMAGE_CANDIDATE_FAILURES` 等），不是失败；P6-C1 不重试它们（L6-09）。
4. `R` 为空 → `AmaneBatchRetryError(NO_RETRYABLE_ITEMS)`（不创建空轮次）。`generation + 1 > MAX_RETRY_ROUNDS (16)` → `AmaneBatchRetryError(ROUND_LIMIT)`。
5. 执行 `await orchestrator.preview([原始 DiscoveredMediaItem for i in R])` → 新一轮 `AmaneBatchRound(generation=k, origin_indices=R, preview=…)`。
6. 返回**新的** `AmaneBatchPreview`（`rounds + (新轮次,)`）；`previous` 不被修改。

* P6 不维护“已重试”注册表（无全局可变状态）；同一 `previous` 可被重试多次，每次都是调用方显式的新操作。**没有自动重试循环。**
* 轮内的 Phase A 冲突只在子集内计算；与成功条目的冲突不可能存在（它们在主轮已作为 `BATCH_CONFLICT` 被排除、不会进入元数据阶段）。
* 宿主任务账本期望（real-host 证据 E6-13）：每个**成功**番号在整个多轮过程中恰好 1 个 SCRAPE 任务；每个**失败后恢复**的番号恰好 2 个；
  永不为成功条目新增任务（mutation M6-07）。

---

## 14. 并发合同（冻结）

1. **跨条目并发的唯一所有者是 P4 `BatchScheduler`**（`OrchestrationConfig.metadata.max_in_flight_items = M`，缺省 4，范围 1..64）。
   P6 没有信号量 / 线程池 / worker 池 / `asyncio.gather` / `TaskGroup` / `create_task`（清理 task 例外，且有界、被 await，第 10.2 节）。
2. **每个 active aggregate 最多对应一个 active 宿主 SCRAPE 任务。** 一个 aggregate 不 fan-out 多个宿主任务。
3. 因此 `P6 观察到的 active 宿主任务数 ≤ active aggregate 数 ≤ M`。机检：
   * engine 维护 `in_flight` 计数器（`aggregate` 入口 `+1`，`finally` `-1`）与 `peak_in_flight`（审计快照）；
   * 真实宿主验证：独立观察者（测试工具自己的 client，不是 P6 的）以 ≤ 20 ms 间隔采样 `GET /api/tasks?type=scrape&status=queued&status=running`，
     只统计 payload 号属于本批的任务，`max ≤ M`；
   * 覆盖：完成顺序反转、慢条目、失败条目、被取消条目——都不改变 `max ≤ M`，也不改变语义结果。
4. 取消后 `UNCERTAIN_*` 的任务**不计入** active aggregate（P6 已放弃观察它），但计入审计的 `uncertain_cancellations`；这是对第 3 条的诚实限定：
   P6 保证的是“**P6 正在等待的**宿主任务数 ≤ M”，不是“宿主上不可能有遗留任务”。
5. 宿主自身的 worker 并发（Amane 缺省 3）独立于 M：当 M 大于宿主并发时，多出的任务在宿主排队，其排队时间计入 `aggregate_deadline_seconds`（L6-07）。
6. 门面不创建任何 event loop / 线程；全部在调用方的 loop 里运行。

---

## 15. Partial 语义（冻结；两个层次必须区分）

| 层次 | 内容 | P6 的立场 |
|---|---|---|
| A. Core 内部多来源 `PARTIAL` | 例如 `javdb` 失败、`fc2db_net` 成功 | 发生在 **P5 边界之内**。P5 把它映射为可用的 Amane `MediaMetadata`（PARTIAL 是可用结果，不是错误），仅在**宿主进程**里记一条 WARNING 日志。P6 **无法**也**不得**重建每个内部来源的失败分类 |
| B. P6 边界级的条目成功 / 失败 | 宿主 SCRAPE 是否产生了可映射、可归属的 Metadata | 唯一可证明的边界。内部来源降级但仍得到合法 `MediaMetadata` → **P6 条目成功**（`AggregateStatus.SUCCESS`，唯一 SourceResult） |

* P6 **不**把日志文本当证据，**不**读宿主日志，**不**声称某内部来源失败。
* “one source degraded, item still usable”的**证据**来自受控上游 fixture 的结构化请求账本（哪个来源页被请求、被指示返回了 5xx / 404）加上该条目最终
  READY——这证明的是“在上游降级下条目仍可用”，**不是** P6 的 provenance 声明（E6-12）。
* 因此在 P6 流程里不会出现 `ItemWarning.METADATA_PARTIAL`；任何测试若观察到它，都是缺陷。

---

## 16. Persistence / Resume（冻结：没有）

P6-C1 **不新增**：P6 batch 数据库、checkpoint 文件、JSON resume 文件、pickle、SQLite 状态、durable batch id、跨进程锁、进程崩溃后的恢复。

* Amane 自己把 Task 持久化在宿主库里——这属于 **Host ownership**，不是 P6 的 durable resume 契约。不得因为 Amane 任务落库就宣称 P6 支持 durable batch resume。
* 内存里存在的只有：`AmaneBatchPreview`（调用方持有）、有界审计账本（`MAX_AUDIT_RECORDS = 20000`，溢出置 `overflowed=True`，不无界增长）。
  它们**不是**持久化格式，没有序列化保证。
* P4 的进程内 `RetryMaterial` 继续按 CLOSED 合同使用（P6 不使用它，13.2）。
* 进程退出后：宿主上可能遗留 QUEUED / RUNNING 的 P6 任务（尤其 `UNCERTAIN_*`）；P6 不在下次启动时寻找或取消它们（那需要持久化任务 id，违反本节）。记入 L6-03。

---

## 17. Progress（冻结：不新增公共 progress 契约）

* Amane 的 `TaskResponse` 在两个版本里都**没有** progress 字段（见 7.3）；进度只通过 WebSocket（cookie 握手）事件到达。P6-C1 不使用 WebSocket。
* P4-C8 §11.4 明确：批量操作没有进度回调 / 订阅 / 可轮询的实时状态。P6 不修改 P4，也不新造“全局 progress 状态机”。
* 可观察、可用于测试 / 运维证据的只有：宿主任务的结构化 `status`、`AmaneHostAuditSnapshot` 的计数（`submitted` / `in_flight` / `peak_in_flight` /
  `failure_counts` / `uncertain_cancellations`）。它们是**运维观察**，不是语义结果的一部分（第 21 节）。
* 最终必须有确定性的 batch summary（第 20.4、21 节）。

---

## 18. 图片 / NFO / 物化所有权（冻结）

* P4 下游（`HttpxImageClient` 图片获取、NFO 渲染、产物清单、执行前预检、`BatchPreview`）**保持 CLOSED 原样**，由调用方传入的 `ImageHttpClient` 驱动；P6 不重写任何一步。
* Amane SCRAPE 可能按用户的 `scraping.download_resources` 自行把图片物化为宿主 Resource，且 `crop_poster` 缺省会把 poster 替换为宿主内部 URL
  （`/api/resources/<hash>`）。P6：
  * **不依赖**这些 Resource 文件，不把它们当作 P4 图片获取的替代；
  * 只接受**绝对 http(s) URL** 候选（第 11.4 节）；宿主内部相对 URL 被确定性剔除并计入审计 `dropped_url_count`；
  * **不修改**用户的 Amane 全局配置（零 `/api/config` 访问）。
* 因此生产环境里，若用户的 Amane 开启了海报裁剪，poster 候选可能只剩 thumb 系列——这会体现为 P4 的 `POSTER_ABSENT` / `FANART_ABSENT` 警告，而不是 P6 错误（L6-10）。
* **验收宿主**可以（也必须）明确关闭 Amane 自身的 resource download（`scraping.download_resources = []`）与演员扇出（`actor_scraping.auto_scrape = false`），
  以减少重复网络与不确定性（第 22 节）；这只发生在测试工具里，对象是一次性的临时宿主。
* 图片候选级部分失败（P4 §22）保持为条目**警告**；“image partial failure”场景由 P4 的真实 `HttpxImageClient`（`httpx.MockTransport`）驱动，P6 只证明它们
  与真实宿主元数据组合时语义不变。

---

## 19. Phase 7 边界与“不执行”安全不变量（冻结）

Phase 6 的目标终点是 `… → NFO → organize preview`。宿主侧：Coordinator 与设计期核查一致确认 v0.15.0 / v0.18.0 存在 ORGANIZE 任务但**没有**可依赖的 dry-run /
organize preview 公共 API，因此 organize preview 由 **P4 `BatchPreview` / 执行前预检** 提供。Phase 7 才做真实文件系统验收（mkdir / rename / move /
collision / subtitle pairing / source preservation）。

### 19.1 安全不变量（机检；缺一即 FAIL）

```text
S6-1  P6 流程绝不调用 BatchOrchestrator.execute / fc2_organizer.execution.execute_filesystem / execute_preview
S6-2  P6 绝不提交 ORGANIZE / TRASH（或任何非 scrape 类型）宿主任务；请求账本的 type 恒为 "scrape"
S6-3  P6 绝不移动 / 重命名 / 删除 / 覆盖 / 创建 用户媒体根与 library root 下的任何文件或目录
S6-4  门面不暴露 BatchOrchestrator 或其 execute（Phase 7 才会增加执行入口）
S6-5  P6 不写任何文件（本包零文件 API、零日志、零临时文件）
```

### 19.2 机检方式

1. **静态（AST）**：`src/fc2_amane_batch/**` 中不得出现标识符 `execute`、`execute_filesystem`、`execute_preview`、`BatchExecutionResult`、`merge_retry`、
   `preview_retry`；不得 import `os` / `shutil` / `pathlib` / `tempfile` / `fc2_organizer.execution` / `.materialization` / `.nfo` / `.publication`；不得调用内建 `open`；
   请求构造中不得出现字符串字面量 `"organize"` / `"trash"` / `"delete"` / `"retry"`（`"cancel"` 与 `"scrape"` 除外）。
2. **运行时 tripwire**：`tests/amane_batch` 的 autouse fixture 把 `BatchOrchestrator.execute`、`fc2_organizer.orchestration.execute.execute_preview`、
   `fc2_organizer.execution.execute_filesystem` 替换为立即 `AssertionError` 的桩；任何一次调用即测试失败（mutation M6-10 证明它非空）。
3. **文件系统树摘要**：每个真实宿主场景前后对“媒体根 + library root”计算递归树摘要（相对路径 + 类型 + 大小 + 内容 sha256），必须逐字节相等。宿主自己的数据目录不在其中。

### 19.3 对 Phase 7 的输入语义（非约束性说明）

Phase 7 将通过 P4 原有路径对某个 `AmaneBatchRound.preview` 调用 `execute`；每一轮的 `BatchPreview` 都是独立、可按 P4 合同执行的对象；P6 **不**提供多轮合并语义。
Phase 7 需要为门面增加执行入口（并为此做自己的 Contract），不属于 P6。

---

## 20. 公共 API（冻结）

### 20.1 `fc2_amane_batch.__all__`（精确集合与顺序）

```python
__all__ = [
    # 门面与引擎
    "AmaneBatchIntegration", "AmaneAggregationEngine", "AmaneHostClient",
    # 配置与凭据
    "AmaneHostConfig", "AmaneHostCredential",
    # 结果模型
    "AmaneBatchPreview", "AmaneBatchRound", "AmaneBatchSummary",
    # 运维审计模型
    "AmaneHostAuditSnapshot", "HostAttemptRecord", "HostFailureKind", "CancelOutcome", "HostPreflightReason", "RetryRefusal",
    # 常量
    "PLUGIN_SOURCE_ID", "MAX_RESPONSE_BYTES", "MAX_AUDIT_RECORDS", "MAX_RETRY_ROUNDS",
    "DEFAULT_REQUEST_TIMEOUT_SECONDS", "DEFAULT_POLL_INTERVAL_SECONDS", "DEFAULT_AGGREGATE_DEADLINE_SECONDS",
    "DEFAULT_CANCEL_BUDGET_SECONDS", "DEFAULT_MAX_CONSECUTIVE_POLL_ERRORS",
    # 错误
    "AmaneBatchError", "AmaneBatchConfigError", "AmaneBatchInputError", "AmaneBatchContractError",
    "AmaneHostCallError", "AmaneHostPreflightError", "AmaneBatchRetryError",
]
```

任何增减都是合同修订（需 Design Review）。`fc2_organizer/__init__.py` 与 `fc2_metadata_core/__init__.py` 不 import 本包（零 diff）。

### 20.2 错误层次

```text
AmaneBatchError(Exception)                      基类；消息固定、不含 URL / 宿主文本 / token / 任务 id
├─ AmaneBatchConfigError(AmaneBatchError, ValueError)     构造参数非法（base_url / 数值范围 / 凭据格式 / 未确认写入）
├─ AmaneBatchInputError(AmaneBatchError, ValueError)      门面输入类型非法（items 不是 list/tuple 等）
├─ AmaneBatchContractError(AmaneBatchError, RuntimeError) P6 内部不变量被破坏（缺陷，不是外部失败）
├─ AmaneHostCallError(AmaneBatchError)                    client 单次调用失败；只有结构化属性 .kind: HostFailureKind
├─ AmaneHostPreflightError(AmaneBatchError)               整批前置条件失败；只有 .reason: HostPreflightReason
└─ AmaneBatchRetryError(AmaneBatchError, ValueError)      retry_failed 被拒绝；只有 .reason: RetryRefusal
```

`HostPreflightReason = {AUTH_REJECTED, HOST_UNREACHABLE, WORKER_PAUSED, PROTOCOL_MISMATCH}`；
`RetryRefusal = {FOREIGN_PREVIEW, NO_RETRYABLE_ITEMS, ROUND_LIMIT}`。错误对象不保存、不链接任何 httpx 异常（`from None`）。

### 20.3 引擎与 client

```python
class AmaneHostClient:
    def __init__(self, config: AmaneHostConfig, *, transport: httpx.AsyncBaseTransport | None = None) -> None
    # transport 仅供测试注入 httpx.MockTransport；生产保持 None。构造零 I/O，不发请求。
    async def submit_scrape(self, number: str) -> HostTask
    async def observe_task(self, task_id: int) -> HostTask
    async def cancel_task(self, task_id: int) -> HostBatchCancelResult
    async def fetch_metadata(self, metadata_id: int) -> HostMetadata
    async def probe_worker(self) -> HostWorkerState
    async def aclose(self) -> None          # 幂等；aclose 之后任何调用 → AmaneBatchContractError
    # 每个方法失败时只抛 AmaneHostCallError(kind)；HostTask / HostMetadata / … 是私有 _wire 类型（不进入 __all__）

class AmaneAggregationEngine:
    def __init__(self, client: AmaneHostClient, *, _clock=time.monotonic, _sleep=asyncio.sleep) -> None
    # _clock / _sleep：关键字专用的测试接缝（确定性单测）；生产不得传入
    async def aggregate(self, number: str) -> AggregationResult      # 类属性中的普通 async def（P4 静态形态检查要求）
    def audit_snapshot(self) -> AmaneHostAuditSnapshot
```

* `aggregate` 的返回 / 抛出契约：成功 → SUCCESS 结果；**所有宿主侧失败 → 返回 FAILED 结果（不抛）**；非规范号 → `InvalidCanonicalNumberInputError`（零网络）；
  P6 内部缺陷 → `AmaneBatchContractError`（普通 `Exception`，仍先做有界清理）；`CancelledError` → 有界清理后原样重新抛出；其它 `BaseException` → 不做 I/O、原样传播。
* engine 不关闭传入的 client（所有权在创建者）。

### 20.4 门面与结果模型

```python
class AmaneBatchIntegration:
    def __init__(self, host: AmaneHostConfig, image_client, library_root: str, *,
                 output_policy=None, image_policy=None, config: OrchestrationConfig | None = None,
                 transport: httpx.AsyncBaseTransport | None = None) -> None
    # 构造：校验 + 创建 AmaneHostClient / AmaneAggregationEngine / BatchOrchestrator；零网络、零文件系统访问
    # image_client 属于调用方（P4 约定）；门面只拥有自己创建的 AmaneHostClient
    async def preview(self, items) -> AmaneBatchPreview           # items: list|tuple[DiscoveredMediaItem]；先 preflight（9.5）
    async def preview_root(self, media_root, policy=None) -> AmaneBatchPreview   # discover_media(read-only) + preview；保留 discovery issues
    async def retry_failed(self, previous: AmaneBatchPreview) -> AmaneBatchPreview   # 13.3
    def audit_snapshot(self) -> AmaneHostAuditSnapshot            # 取消后仍可调用
    async def aclose(self) -> None                                # 幂等；async with 支持
```

```python
@dataclass(frozen=True, slots=True)
class AmaneBatchRound:
    generation: int                   # 0 = 主轮；k = 第 k 次失败子集重试
    origin_indices: tuple[int, ...]   # 严格递增；origin_indices[i] 是 preview.items[i] 在原始输入中的下标
    preview: BatchPreview             # P4 对该轮输入子集给出的、未经改动的 BatchPreview（同一对象）

@dataclass(frozen=True, slots=True)
class AmaneBatchPreview:
    items: tuple[DiscoveredMediaItem, ...]     # 原始输入快照（下标即原始下标）
    discovery_issues: tuple[DiscoveryIssue, ...]   # preview_root 的 DiscoveryResult.issues；preview(items) 时为空
    rounds: tuple[AmaneBatchRound, ...]        # rounds[0] 覆盖全部条目；其后为失败子集重试轮次
    # 派生（不存储）：
    #   latest(i) -> (generation, ItemPreview)   原始下标 i 的最新结果
    #   retryable_indices -> tuple[int, ...]     13.3 的可重试集合 R
    #   summary -> AmaneBatchSummary
```

`AmaneBatchPreview.__post_init__` 校验：`rounds` 非空；`rounds[0].origin_indices == tuple(range(len(items)))`；`rounds[k].generation == k`；
每个 `origin_indices` 严格递增且与对应 `preview.items` 等长；`rounds[k>0].origin_indices ⊆` 上一视图的 `retryable_indices`；
每个 `preview.items[i].media_item is items[origin_indices[i]]`（同一对象）。任一违反 → `AmaneBatchContractError`。

```python
@dataclass(frozen=True, slots=True)
class AmaneBatchSummary:            # 确定性、纯语义；由最新视图的 ItemPreview 派生，从不存储
    total: int; ready: int; blocked: int; unprepared: int; warned: int
    retried: int                    # 出现在任一 generation ≥ 1 轮次的不同原始条目数
    rounds: int
    stage_counts: tuple[tuple[OrchestrationStage, int], ...]            # 与 P4 PreviewSummary 同口径：Σ == blocked + unprepared
    metadata_failures: tuple[tuple[IssueReason, int], ...]               # 仅 METADATA 阶段原因
    retryable: int                  # == len(retryable_indices)
```

不变量：`total == ready + blocked + unprepared`；`warned ≤ total`；`Σ stage_counts == blocked + unprepared`；`retryable ≤ unprepared`；`rounds == len(rounds)`；
当 `rounds == 1` 时，`total / ready / blocked / unprepared / warned / stage_counts` 与 `rounds[0].preview.summary` **逐项相等**（交叉校验，E6-19）。
元组均按枚举声明顺序排序，保证确定性。

### 20.5 审计模型（运维，非确定性，与语义分离）

```python
class HostFailureKind(Enum):  # 第 12.1 节的 18 个 HOST_* 成员；value = 去掉 HOST_ 前缀的小写（HOST_TASK_FAILED.value == "task_failed"）
class CancelOutcome(Enum):    # 第 10.3 节的 8 个成员

@dataclass(frozen=True, slots=True)
class HostAttemptRecord:
    seq: int                          # 1.. 本 engine 内的逻辑序号（提交先后），不是时间
    number: str
    host_task_id: int | None
    outcome: HostFailureKind | None   # None = 成功
    terminal_status: str | None       # 观察到的结构化终态 "done" | "failed" | None
    cancel: CancelOutcome             # 无取消时为 NOT_APPLICABLE
    submission_ambiguous: bool
    polls: int; requests: int; dropped_url_count: int
    metadata_id: int | None
    elapsed_ms: float
    begin_event: int; end_event: int  # 逻辑事件计数（aggregate 开始 / 结束），用于机检并发区间，不是时间

@dataclass(frozen=True, slots=True)
class AmaneHostAuditSnapshot:
    records: tuple[HostAttemptRecord, ...]     # 按 seq 升序；至多 MAX_AUDIT_RECORDS
    submitted: int; in_flight: int; peak_in_flight: int
    failure_counts: tuple[tuple[HostFailureKind, int], ...]
    uncertain_cancellations: int
    overflowed: bool                           # True = 超过 MAX_AUDIT_RECORDS，较旧记录已被丢弃（计数仍准确）
```

---

## 21. 语义输出 vs 运维输出（确定性分离，冻结）

| 类别 | 内容 | 是否参与确定性比较 |
|---|---|---|
| **语义输出** | 每轮 `BatchPreview` 的语义投影（条目下标、规范番号、`PreviewState`、`ItemIssue`（stage / reason / error_type / detail）、`warnings`、plan 路径（相对 library root）、产物种类与目标、**NFO 字节**、产物 sha256、`conflict_with`、`retry_origin`）、`AmaneBatchSummary`、问题的出现顺序 | **是** |
| **运维输出** | Amane task id、`metadata_id`、时间戳、`elapsed_ms`、轮询次数、请求次数、逻辑事件序号、随机标识（`BatchLineage.token`、`preview_id`）、墙钟耗时 | **否**（永不进入语义输出） |

* `AggregationResult` / `SourceResult` 内只有封闭词汇（`error_detail`）与测量耗时；任务 id / metadata_id **只**出现在审计里。
* 确定性判据（E6-15）：同一组确定性宿主 / 上游输入，仅**完成顺序**不同（例如上游按番号逆序放行），则：每轮 `BatchPreview` 的语义投影、NFO 字节、artifact requests、
  issue 顺序、`AmaneBatchSummary` 完全相等。测试侧的 `semantic_projection()` 必须显式列出排除项（上表“运维输出”），且有一个非空性控制：改变上游内容必须使投影改变。

---

## 22. 验收环境（冻结）

### 22.1 宿主坐标

| 标签 | 坐标 | 要求 |
|---|---|---|
| HOST-A-SRC | SC-03：v0.15.0 / source host（`python -m amane.server`，独立 venv，Python 3.14.x）/ Windows x64 | **必需** |
| HOST-B-SRC | SC-04：v0.18.0 / source host / Windows x64 | **必需** |
| HOST-A-WIN / HOST-B-WIN | SC-01 / SC-02：官方冻结桌面包 | **可选**：运行并 PASS 才可声明；否则 `UNVERIFIED`，不扩大支持声明 |

两个必需宿主是**真实 Amane 进程**（真实 task worker、真实 P5 plugin、真实 Core、真实 P4 下游）；不是 fake Amane 对象。宿主准备**只读复用** P5-C2 已 CLOSED 的工具
（`tools/prepare_amane_hosts.py`、`tools/build_core_wheel.py`、`tools/build_amane_release.py`）；P6 不修改它们。

### 22.2 宿主准备（仅在测试工具里，对一次性临时宿主）

1. 环境：`AMANE_DATA_DIR` / `AMANE_LOG_DIR`（临时目录）、`AMANE_PORT`（空闲端口）、`AMANE_HOST=127.0.0.1`、`AMANE_TOKEN=<canary token>`、`AMANE_SAFE_DIRS=ALLOW_ALL`。
2. 把 P5 构建的 sidecar Core wheel 放入 `<data>/plugins/_ffcc_core/`（INSTALL 文档流程），经 `POST /api/plugins`（`201`）安装 plugin zip；wheel 的 sha256 必须等于
   `adapters/amane/release/core_release_ledger.json` 的 pin（E6-23）。
3. `PATCH /api/plugins/ffcc.fc2-metadata`：`sources` 为 `fc2db_net` / `javdb` / `av123` 三项，各自 `base_url` 指向 P6 上游 fixture 的对应前缀（回环 `http://127.0.0.1:<port>/…`）；
   `source_deadline_seconds` 取小值（如 5）。
4. `PATCH /api/config`：`scraping.content_routes.fc2 = ["ffcc.fc2-metadata"]`、`scraping.download_resources = []`、`actor_scraping.auto_scrape = false`；LLM 翻译保持关闭。
   随后 `GET /api/config` **回读并断言**（回读只存在于测试工具，宿主是一次性且无任何真实 cookie / token）。

### 22.3 FC2 route ownership 的机械证明（E6-16）

不得以“最后有 Metadata”代替归属。必须同时具备：

1. **配置事实**：route 回读 `== ["ffcc.fc2-metadata"]`；`GET /api/plugins/ffcc.fc2-metadata` 显示已安装且启用。
2. **逐条结构化归属**：每个成功条目的 `result.field_sources` 全部为 `ffcc.fc2-metadata`（第 11.3 节，生产代码内强制）。
3. **上游请求账本**：Core 三个来源适配器的 URL 形状（`/fc2db/work/<digits>/`、`/javdb/search?q=FC2-PPV-<digits>`、`/av123/en/v/fc2-ppv-<digits>`）只会由“配置了这些 base_url 的 plugin”产生；
   账本逐号记录被请求的来源页，成功条目的号必须出现。
4. **反事实控制**：同一宿主上卸载 / 禁用 plugin（或把 route 清空）→ 同一批号全部在 METADATA 阶段失败（M6-01 / M6-02）。
5. **构件同一性**：plugin zip / sidecar wheel 的哈希与 P5 台账 / 构建器输出一致。

### 22.4 确定性上游 fixture（P6 自有，`tests/amane_batch/`）

* **只读复用** P5-C2 的回环 fixture 语料（`tests/amane_compat/host_scripts/loopback_fixture.py` 所服务的 HTML 夹具）；P6 在自己的目录里写包装层，**不修改**该文件。
* ≥ 10 个互异、满足 canonical 的号：以确定性的数字替换从 VERIFIED 夹具页派生（派生页必须先通过 Core 解析器的预检测试，防止夹具本身无效）。
* 行为类别：`ALL_OK`（≥ 10 个互异号）、`DEGRADED_ONE_SOURCE`（一个来源 5xx / 404，其余命中）、`TOTAL_FAILURE`（全部来源失败）、`HOLD`（响应被扣留直到测试释放；
  用于“宿主任务运行中”的取消）、`SLOW`（可控延迟；用于完成顺序反转）。
* 请求账本只记录（来源、digits、方法、行为），不记录端口 / 时间 / 绝对路径。
* 图片：`HttpxImageClient(transport=httpx.MockTransport(...))`，对元数据里的绝对 URL 返回确定性图片字节；单个候选的失败行为由 URL 令牌选择（沿用 P4-C10 harness 的约定，只读复用）。

### 22.5 故障注入代理（测试工具；“真实宿主 + 受控网络 / 响应故障”）

回环 TCP/HTTP 代理，位于 P6 client 与真实宿主之间，按脚本施加**记录在案**的故障：丢弃 / 延迟第 n 个匹配请求的响应、关闭连接、**改写**真实宿主响应中的某个 JSON 字段
（删除 `result.metadata_id`、改 `metadata.number`、清空 `title`、向 `field_sources` 注入外来站点）。用途：传输超时、取消不确定性（丢弃取消响应）、DONE 缺 `metadata_id`、
号不匹配、低于最低成功、外来归属。故障脚本进入证据 JSON。

### 22.6 旁观任务（bystander）

在取消场景里，测试工具先用**自己的** client 在同一宿主上直接创建一个与批量无关的 SCRAPE 任务（保持 QUEUED / RUNNING）。取消完成后断言它**未被取消**；
这是 M6-08 的非空性依据。

---

## 23. Evidence Gate（冻结；根据 Governance v2 第 17 节，较大的 C 证据必须更完整）

| ID | 证据 | 载体 |
|---|---|---|
| E6-01 | 范围门：`git diff 4189b95…..HEAD` ⊆ P6 allow-list；闭合范围零 diff；HG-1 的两个文件改动**仅限**第 5.4 节所述 | `tests/amane_batch/test_amane_batch_scope_gate.py` |
| E6-02 | Contract → implementation → test 映射表（逐条合同条款 / 不变量） | HANDOFF |
| E6-03 | 架构守卫（AST）：import 允许 / 禁止清单；禁用标识符（19.2）；endpoint 常量集合 **等于** 表 H1；无 logging / 文件 API；控制流不比较 `error` / `detail` / `str(exc)` / `exc.args` | `test_amane_batch_architecture.py` |
| E6-04 | 配置 / 凭据：校验矩阵（base_url 全部非法形态、数值边界、凭据字符集）；redaction；不可 pickle / copy | `test_amane_batch_config.py` |
| E6-05 | client 协议（`httpx.MockTransport`）：**请求账本逐键断言**（方法 / 路径 / 体键集 / 头集）；无 cookie 回传、无重定向跟随、无环境代理 / `.netrc`、响应上限、状态码映射表穷举 | `test_amane_batch_client.py` |
| E6-06 | 严格 reader：必需键缺失 / 类型错误 / 额外键容忍（v0.18.0 `locked_fields`） | `test_amane_batch_wire.py` |
| E6-07 | 映射：字段表穷举（守卫 `HostMetadata` / `NormalizedMetadata` 字段集合）、URL 卫生与 P5 I22 逐样本对账、最低成功、号等价、归属、每个 `HostFailureKind` → 合法 Core 配对（`ALLOWED_ERROR_KINDS`）、产出的 `AggregationResult` 通过 Core 校验且能被 P4-C9 诊断投影接受 | `test_amane_batch_mapping.py` |
| E6-08 | 生命周期：状态机、deadline（含“至少一次观察”）、观察失败容忍、**提交永不重试**、`submission_ambiguous` | `test_amane_batch_lifecycle.py` |
| E6-09 | 取消：精确 id、请求体不含 `status` / `type`、清理预算、`CancelOutcome` 全部 8 种、shield、无分离 task、二次取消、致命 `BaseException` 无 I/O | `test_amane_batch_cancellation.py` |
| E6-10 | 并发：`peak_in_flight ≤ M`；完成顺序反转 / 慢 / 失败 / 取消下不变；无隐藏 fan-out | `test_amane_batch_concurrency.py` |
| E6-11 | **真实宿主纵向门**：≥ 10 个 FC2，HOST-A-SRC 与 HOST-B-SRC 各一次，完整链（scan → … → BatchPreview → summary） | `tools/run_amane_batch_gate.py` → `P6_C1_HOST_MATRIX.json` |
| E6-12 | 真实宿主失败矩阵：来源降级仍可用；整体失败；混合；宿主任务 FAILED；宿主 API 传输失败；图片部分失败；坏 / 缺 metadata（经代理改写）；精确的条目隔离 | 同上 |
| E6-13 | 真实宿主重试：仅失败子集、成功条目不重跑、retry → success、宿主任务账本计数（13.3） | 同上 |
| E6-14 | 真实宿主取消：准入前、运行中、确认、不确定（代理丢弃取消响应）、旁观任务未受影响 | 同上 |
| E6-15 | 真实宿主确定性：完成顺序反转 → 语义投影 / NFO 字节 / artifact requests / issue 顺序 / summary 相等；上游内容变化 → 投影变化（非空性） | 同上 |
| E6-16 | route ownership 机械证明（22.3） | 同上 |
| E6-17 | 安全 canary：token 不出现在 `repr` / 异常 / `__cause__` 链 / traceback / `BatchPreview` / 汇总 / 审计 / 诊断投影；cookie 不回传；跨源重定向不带凭据；`.netrc` / 环境代理被忽略；TLS 不可降级（自签证书 → `HOST_CONNECTION`，上游零请求） | `test_amane_batch_security.py` + 真实宿主 canary |
| E6-18 | 不执行：S6-1..S6-5 三层机检（静态 / tripwire / 文件系统树摘要） | 架构测试 + 宿主场景 |
| E6-19 | `AmaneBatchSummary` 精确计数，并与 P4 `PreviewSummary` 逐项交叉校验 | `test_amane_batch_summary.py` + 宿主场景 |
| E6-20 | 语义 / 运维分离：语义投影中不含任何运维字段 | `test_amane_batch_determinism.py` |
| E6-21 | mutation / non-vacuity：第 24 节全部 M6-xx 必须使对应门**变红**，且未变异孪生保持绿 | `test_amane_batch_mutation_nonvacuity.py` |
| E6-22 | 全量回归：既有全部套件（adapter / compat（HG-1 之后）/ contract / unit / phase4_acceptance …）通过，**与 Frozen Base 的基线通过数对账**（S1 第一件事是在 `4189b95…` 上记录各目录基线） | HANDOFF |
| E6-23 | 构件同一性：sidecar wheel sha256 == P5 台账 pin；plugin zip 由 CLOSED 构建器产出且 P5 构件零变化 | 宿主矩阵 JSON |
| E6-24 | live-network smoke 记录（第 25 节） | `P6_C1_LIVE_SMOKE.json` |
| E6-25 | 解释器覆盖：P6 包与其测试在 Python 3.12 与 3.14 上运行（受影响测试）；只覆盖一个则作为 evidence gap 明示 | HANDOFF |
| E6-26 | 证据 JSON 自洽 + 禁止声明校验（UNVERIFIED 不得被写成 SUPPORTED；坐标级声明；无“durable resume / 已执行整理 / 全版本支持”字样） | `test_amane_batch_matrix_json.py` |
| E6-27 | HANDOFF：Contract 映射、完整 diff scope、命令与输出、evidence gaps、known limitations（L6-xx）、Phase 7 输入 | `docs/review/P6_C1_HANDOFF.md` |

### 23.1 声明纪律

* 支持声明只能写：“在 SC-03 / SC-04 上经确定性真实宿主验收”，并按 live smoke 记录单独陈述公网状态。
* 禁止：“支持 v0.15.0 / v0.18.0”（无坐标）；“支持 durable resume / 跨进程恢复”；“已执行 / 已验证真实整理”；“公网已验证”（无 VERIFIED 记录）；
  “P6 保证宿主上无遗留任务”。
* `UNVERIFIED` / `ENVIRONMENTALLY_BLOCKED` 不得出现在支持声明里。

---

## 24. Mutation / Non-vacuity 控制（冻结；每项都必须让门真正变红）

每个控制都有**孪生**：未变异版本运行同一断言必须绿；变异版本必须红。变异在进程内通过替换被测生产函数 / 类实现（共享同一个 oracle），宿主级控制通过门工具的变体运行（退出码非 0）。

| ID | 变异 | 必须变红的门 |
|---|---|---|
| M6-01 | plugin 未加载（卸载 / 禁用） | E6-11 / E6-16：全部条目 METADATA 阶段失败 |
| M6-02 | FC2 route 改为空 / 非 plugin；（单测）还原归属校验使外来 `field_sources` 被接受 | E6-16 / E6-07 |
| M6-03 | 返回错误号（代理改写 `metadata.number`）；（单测）去掉号等价校验 | E6-12 / E6-07 |
| M6-04 | `DONE` 缺 `metadata_id` 被当作成功 | E6-12 / E6-07 |
| M6-05 | metadata 不满足最低成功（title 空白）被接受 | E6-12 / E6-07 |
| M6-06 | 宿主任务 `FAILED` 被当作成功 | E6-08 / E6-12 |
| M6-07 | 重试意外重跑成功条目（可重试集合包含全部） | E6-13（宿主任务账本计数） |
| M6-08 | 取消错误地取消别人的任务（用 `status` / `type` 的宽泛取消） | E6-09 / E6-14（旁观任务被取消） |
| M6-09 | 提交体带 `media_id` / 路径 / hash | E6-05（请求账本键集） |
| M6-10 | 调用 `execute` / 文件系统执行 | E6-18（tripwire + AST） |
| M6-11 | 并发超预算（一个 aggregate 提交两个任务 / 绕过 P4 预算） | E6-10 / E6-14 |
| M6-12 | 凭据泄漏进 `repr` / 异常文本 | E6-17 |
| M6-13 | 启用重定向跟随 / cookie 回传 | E6-17 / E6-05 |
| M6-14 | 取消把“请求已发送”当成“已停止”（跳过确认） | E6-09 / E6-14（不确定性场景） |
| M6-15 | 控制流引入错误文本解析（`"timeout" in str(exc)`） | E6-03（AST） |
| M6-16 | 提交超时后重试 `POST /api/tasks` | E6-08 / E6-13（重复任务） |

---

## 25. Live Network Smoke（冻结）

P5-C2 把真实公网 scrape 留给 Phase 6（L-C2-10）。P6-C1 的 evidence 必须包含一次 **live-network smoke 尝试**，且**不得**把外部站点可用性混进确定性正确性门。

* 载体：`tools/run_amane_batch_gate.py --live`，对一个**一次性**的 source host（plugin 使用**默认**公网 base_url，route 为 `["ffcc.fc2-metadata"]`），对
  `docs/acceptance/PHASE3_50_ID_SET.md` 中**按文件顺序的前 3 个号**运行完整的 `preview_root` 链（图片使用真实 `HttpxImageClient`，不用 MockTransport）。
* 记录（`P6_C1_LIVE_SMOKE.json`，允许含时间戳）：状态词表如下。

| 状态 | 条件 |
|---|---|
| `VERIFIED` | 至少 1 个号到达 METADATA 阶段成功（宿主任务 DONE、归属为 plugin、最低成功），并记录 P4 下游条目状态 |
| `UNVERIFIED_ENVIRONMENT` | 宿主已启动，但 0 个号成功；**无法区分**站点 / 网络不可用与缺陷；对应的 live 支持声明**不得扩大** |
| `NOT_RUN` | 无法启动 live 宿主（无网络 / 缺 Python 3.14 / 端口等）；必须写明原因 |

* 禁止：没跑 → PASS；用回环 deterministic 测试冒充公网证据。缺失的 live 证据必须写进 HANDOFF 的 evidence gaps 与 known limitations。
* live smoke 不是 correctness gate：其结果不改变 E6-11..E6-21 的判定。

---

## 26. 不变量（冻结）

```text
I6-01  零 diff：第 5.2 节的闭合范围；本包 import 白名单（6.4）
I6-02  不 import amane / fc2_amane_adapter；不读 Amane 源码、SQLite、日志；不 monkeypatch Amane
I6-03  宿主表面 == 表 H1（5 个操作）；请求体键集精确；绝不含本地路径 / media_id / hash
I6-04  number 在提交前已是 canonical；echo 校验（type / number / content_type）
I6-05  一次 aggregate 尝试 = 恰好一个新 SCRAPE 任务；POST 永不重试
I6-06  每个 active aggregate 最多一个 active 宿主任务；无 fan-out、无隐藏 worker；peak_in_flight ≤ M
I6-07  取消只针对已知 id 的自己的任务；请求体绝不含 status / type；绝不使用 delete / retry
I6-08  取消有界（cancel_budget_seconds）；无分离后台 task；“请求已发送” ≠ “已停止”；UNCERTAIN_* 显式暴露
I6-09  成功必须同时满足第 11.2 节七项校验；缺一 fail closed，且失败种类唯一
I6-10  唯一 SourceResult source_id == "ffcc.fc2-metadata"；永不产生 PARTIAL；永不伪造 trace / 内部来源 provenance
I6-11  field_sources 值 ⊆ contributing_source_ids == ("ffcc.fc2-metadata",)
I6-12  所有控制逻辑只基于 HTTP 状态码 / 枚举 / 结构化 schema / 异常类型；绝不基于文本
I6-13  error_detail 是封闭词汇；不含 URL / 宿主文本 / token / 任务 id
I6-14  凭据：显式注入、redacted、不可序列化、不落盘、不进任何输出；无 cookie jar 持久化；无环境代理 / netrc；无重定向；TLS 不可降级
I6-15  响应流式读取且有上限；严格 reader；未知额外键容忍、必需键缺失 fail closed
I6-16  语义输出确定；运维输出（task id / 时间 / 计数 / 随机标识）永不进入语义输出
I6-17  P4 是唯一的批量重试所有者；retry_failed 仅选择子集并调用 P4 preview；永不重跑成功条目；无自动重试循环
I6-18  无 durable resume / checkpoint / 持久化 / 跨进程锁；审计账本有界
I6-19  不执行：S6-1..S6-5
I6-20  不修改用户 Amane 配置；生产代码零 /api/config 访问
I6-21  门面 preflight 在任何任务被创建之前失败（整批前置条件），零副作用
I6-22  本包零 logging、零文件 API、零环境变量读取
I6-23  AmaneBatchPreview 不可变；其轮次中的 BatchPreview 是 P4 原对象（不复制、不改写）
I6-24  普通条目失败不拖垮其它条目；致命 / 取消保持 P4 现有语义
```

---

## 27. 已知局限（如实记录；进入 E6-27）

| ID | 局限 |
|---|---|
| L6-01 | **独占 route 前提**（H6-1）：P5 INSTALL 把 plugin 放在 FC2 route 最前并保留原站点；P6 需要其它站点不再贡献字段，否则该条目 fail closed（`HOST_ATTRIBUTION_FOREIGN`）。P6 不读取也不修改用户配置，所以由用户自行满足；审计里的 `failure_counts` 用于诊断 |
| L6-02 | 非回环主机必须 `https`；不支持明文局域网、自定义 CA、代理、路径前缀；回环可用 `http` |
| L6-03 | 遗留任务：提交歧义（`submission_ambiguous`）、`UNCERTAIN_*` 取消、进程退出，都可能在宿主上留下 QUEUED / RUNNING 的 SCRAPE 任务；P6 不找回、不跨进程清理（无持久化） |
| L6-04 | DIFF-P6-01：v0.15.0 取消回退可把“恰好完成”的任务改写成 FAILED（“Cancelled by user”），而宿主 Metadata 可能已被写入；P6 的 `CONFIRMED_STOPPED` 在该窗口内可能掩盖“已写入” |
| L6-05 | 无法区分“番号在所有来源都不存在”与“来源 / 宿主故障”（宿主只给 `failed` + 文本；不解析文本）；统一 `HOST_TASK_FAILED` |
| L6-06 | 用户的 Amane 配置（FacetRule、LLM 翻译、v0.18.0 字段锁）会流入映射结果；仅验收宿主可逐字段对账 |
| L6-07 | 宿主排队时间计入 `aggregate_deadline_seconds`；M 大于宿主 worker 并发（缺省 3）时任务会排队 |
| L6-08 | SCRAPE 会 **upsert 宿主 Metadata 库**：P6 的 preview 对用户**媒体 / library 文件系统**只读，但对 **Amane 数据库不是只读**；宿主可能扇出 `ACTOR_SCRAPE` 后继任务（`actor_scraping.auto_scrape` 缺省 True），P6 不跟踪也不取消 |
| L6-09 | 重试只覆盖 METADATA 阶段失败；图片候选级部分失败是警告，不重试 |
| L6-10 | 若用户的 Amane 开启海报裁剪，poster 可能被替换为宿主内部 URL 而被剔除，体现为 P4 的 `POSTER_ABSENT` / `FANART_ABSENT` 警告 |
| L6-11 | 公网证据可能是 `UNVERIFIED_ENVIRONMENT` / `NOT_RUN` |
| L6-12 | SC-01 / SC-02（冻结桌面）可选；macOS / Linux / Docker `UNVERIFIED` |
| L6-13 | `use_cache=[]` 强制刷新：对来源站点的请求量更大，每次运行都会重写宿主 Metadata |
| L6-14 | 无 progress API，不使用 WebSocket |
| L6-15 | 号等价按 Core `normalize_fc2_number`；用户宿主里以非常规写法保存的旧行会被等价接受（映射后一律是请求的 canonical） |
| L6-16 | 重试由调用方显式驱动，最多 `MAX_RETRY_ROUNDS = 16` 轮；多轮视图不能作为单个 `BatchPreview` 执行（Phase 7 逐轮执行） |
| L6-17 | P5 已记录的局限继续成立（C1 L-01..L-15、C2 L-C2-01..16），尤其 L-C2-13（sidecar 的 admission-time integrity，不是 runtime immutability） |

---

## 28. 升级门 / 停止条件（出现任一项必须停止并上报，不得在普通施工中自行解决）

```text
U6-1   需要修改任何 CLOSED production 语义 → AUTHORITY ESCALATION REQUIRED（列出 package / 原因 / 影响 / 兼容 / 安全 / 回归范围）
U6-2   需要调用 execute / ORGANIZE / TRASH，或修改用户文件
U6-3   需要任何持久化 / durable resume / checkpoint / 跨进程锁
U6-4   需要表 H1 之外的 endpoint，或需要版本分支 / feature detection
U6-5   需要读取 / 修改 Amane 配置，或解析宿主日志 / 错误文本 / 异常消息
U6-6   真实宿主观测与第 7 节的事实不一致（出现 DIFF-P6-01..04 之外的差异）
U6-7   HG-1 被否决，或需要修改第 5.4 节所列之外的 CLOSED 测试
U6-8   凭据需要持久化 / 从环境或文件读取
U6-9   重试语义需要修改 P4（preview_retry / BatchScheduler）
U6-10  并发上界无法在不引入新 scheduler 的前提下证明
U6-11  取消无法被有界化（宿主取消无响应时没有放弃路径）
U6-12  三份设计文档互相矛盾，或设计冻结后出现 Contract 语义修订 / 范围修订 / 安全不变量修订（需独立 Design Review，Governance v2 第 11.2 节）
U6-13  试图在没有证据的情况下扩大支持声明（含 live smoke）
```

---

## 29. 状态

```text
Phase 6                       : DESIGN CANDIDATE
P6-C1                         : DESIGN CANDIDATE
Frozen Contract               : NOT YET ACCEPTED
Construction Plan             : NOT YET ACCEPTED
Design Accepted Head          : NOT ESTABLISHED
Implementation                : NOT STARTED
Production Modified           : NO
Tests Modified                : NO
Risk Class                    : C
Phase 6 package count         : 1
HG-1 (historical gate rebind) : DESIGN-REVIEW RULING REQUIRED
```

本文不得被解读为 FROZEN / DESIGN PASS / IMPLEMENTATION AUTHORIZED / CLOSED。唯一 authority 转换：独立 Design Review PASS → 该 Design Candidate SHA 成为
Design Accepted Head（Frozen Contract / Plan Head、Implementation Input）→ 才允许 Developer 开始 S1。
