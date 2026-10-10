# PHASE 6 / P6-C1 — Amane 真实批量集成与批量收尾（Real Amane Batch Integration & Closure）合同

```text
文档状态                    : DESIGN CANDIDATE — NOT YET ACCEPTED
Phase 6                     : DESIGN CANDIDATE
P6-C1                       : DESIGN CANDIDATE — INDEPENDENT DESIGN REVIEW REQUIRED
Frozen Contract             : NOT YET ACCEPTED
Construction Plan           : NOT YET ACCEPTED（docs/P6_C1_CONSTRUCTION_PLAN.md）
Design-R1                   : SUPERSEDED BY DESIGN-R2 CANDIDATE（R1-01..R1-09；Design-R1 Head c05c7ebca04ded9e1853b71e82796a419fadc192；三份增量审查仍有 5 项阻塞）
Design-R2                   : CANDIDATE — REMAINING FINDINGS CLOSURE（R2-01..R2-05；Design-R2 Base c05c7ebca04ded9e1853b71e82796a419fadc192；待独立 Design-R2 增量 Closure Review）
Design Accepted Head        : NOT ESTABLISHED
Implementation              : NOT STARTED
Production Modified         : NO
Tests Modified              : NO
Risk Class                  : C
Package Frozen Base         : 4189b9552d26b3cc5273e0ac09e46e5a3759121d（P5-C2 Final Closure Docs Head）
Governance Authority        : docs/PROJECT_GOVERNANCE_ACCELERATION.md @ 3b9d39e9adbcc8a009707486eebbb8736a5b1c4d
Upstream Final Reviewed Head: 1ef23247c2c65649589e9919c00093901bbcb517（P5-C2 Final Reviewed Technical Head）
Phase 6 package count       : 1（P6-C1；P6-C2 默认不存在）
Branch                      : claude/phase6-c1-amane-batch-integration
Next                        : INDEPENDENT DESIGN-R2 INCREMENTAL CLOSURE REVIEW（通过之前禁止 Developer 开始 S1）
```

**Design-R1 修订索引**（三份独立 Design Review 的合并 findings；本文所有改动都在设计文档内，未改 production / tests / Amane 源码）：

| R1 | 主题 | 主要落点 |
|---|---|---|
| R1-01 | 持久化 Metadata 的字段级 provenance（任务结果 ≠ 持久化记录） | §7.6、§8.5、§11.2–§11.5、§12.1、I6-09..I6-11、E6-07 / E6-16、M6-02 / M6-17 / M6-18、L6-18 |
| R1-02 | 提交尝试 ≠ 已创建任务（`SubmissionState`） | §9.2、§13.1、I6-05、E6-08 / E6-13、M6-16 / M6-19 |
| R1-03 | 异常 `__context__` / 帧局部不得保留凭据 | §8.3、§20.2、I6-14、E6-03 / E6-17、M6-12 |
| R1-04 | 数据库终态 ≠ 执行协程已停止（取消真实性） | §10.3、`CancelOutcome`、L6-04、E6-09 / E6-14、M6-14、Master F-4 |
| R1-05 | 门面 busy-first 不可直接委托 P4 | §9.5、§13.3、I6-21、E6-10、M6-20 |
| R1-06 | 跨轮 Phase B 冲突不被单轮 preview 发现 | §13.3、§20.4（`AmaneBatchSummary`）、§19.3、L6-16、E6-19 |
| R1-07 | JSON 深度 / 节点 / 集合上限 | §8.4–§8.5、I6-15、E6-06 / E6-17、M6-21 |
| R1-08 | Amane 默认 worker concurrency 为 10（不是 3） | §14、L6-07 |
| R1-09 | HG-1 精确化 | §5.4、E6-01 |

**Design-R2 修订索引**（Design-R1 增量审查后剩余的 5 项阻塞；仍然只改设计文档）：

| R2 | 主题 | 主要落点 |
|---|---|---|
| R2-01 | 字段内容的值级来源证明：撤销 E1/E2/E3/R0；改为只从 `raw["ffcc.fc2-metadata"]`（插件原始记录）派生字段值 | §7.3、§7.6、§8.5、§11.2–§11.5、§12.1、§22.3、I6-09 / I6-11 / I6-25、E6-06 / E6-07 / E6-16、M6-17 / M6-18 / M6-23、L6-06 / L6-18 / L6-19 |
| R2-02 | 异常 / 凭据边界扩展到整个 `src/fc2_amane_batch/**`，并区分“新引入的泄漏”与“调用方持有对象本身的认证状态” | §8.3.1（保护面 P1–P3、禁入内容 F、构造规则 C1–C7、失败矩阵）、§20.2、I6-14、E6-17、M6-12 |
| R2-03 | JSON 预扫描成本模型修正为 `O(B)`（`B ≤ MAX_RESPONSE_BYTES`），辅助空间 `O(MAX_JSON_DEPTH)` | §8.4、E6-06、M6-21 |
| R2-04 | 孤儿任务与并发 oracle：区分 A / K / H，不再要求 `\|H\| ≤ M` | §14、E6-10、M6-11、I6-29、L6-07 |
| R2-05 | `SubmissionState` / `CleanupTrigger` / `CancelOutcome` / `AggregateTerminal` 正交模型与合法组合；`NOT_APPLICABLE` ⇔ 未触发清理 | §10.3、§20.5、E6-08 / E6-09、M6-24、I6-28 |

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

P6-C1 **不**执行任何用户媒体的真实文件整理（第 19 节）。真实文件系统验收是 Phase 7。

**副作用声明（不得写成笼统的“Phase 6 只读”）**：Amane SCRAPE 本身会产生**宿主级持久副作用**——持久化的 Task、Metadata upsert，以及在用户配置允许时可能产生的其它宿主所有的副作用
（如 `ACTOR_SCRAPE` 后继任务、Resource 物化）。因此 P6 既**不**宣称 durable resume，也**不**宣称“对 Amane 宿主数据库只读”。验收宿主可以关闭 actor auto scrape / resource download / 翻译以降低不确定性；
生产环境中 P6 **不得**偷偷 PATCH 用户的 Amane 全局配置。

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
* `pyproject.toml` 已有 `[tool.setuptools.packages.find] where = ["src"]`，自动发现新顶层包，**不修改** `pyproject.toml`。
* 其它 `src/` 级别的钉死（逐一核查）：没有 CLOSED 测试枚举 `src/` 顶层包集合；没有按文本扫描 `src/` 中的 “amane” 字样。

### 5.4 历史 diff 门禁碰撞 HG-1（设计期发现；FUTURE S1 TEST-ONLY COMPATIBILITY REPAIR；三份独立 Design Review 的实质裁决：ACCEPTED；Design-R1 精确化文字）

**本 Design Candidate 不执行 HG-1：`Tests Modified = NO`。** 只有 Design-R1 经独立复查被接受（Design Accepted Head 建立）之后，Developer 才允许在 S1 第 0 步按下述精确条款修改那两个历史测试。

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

**冻结的最小重绑（HG-1；实质裁决 ACCEPTED；若精确化后的条款不被接受或无法在 60 行内完成 → `AUTHORITY ESCALATION REQUIRED`，Developer 不得自行换办法）**：

**HG-1 的“已命名的断言移交”（恰好两处）与全部其它约束（Design-R1 精确化，消除“不删除任何 assertion”与“移除一个完整测试函数”的文字冲突）**：

1. **允许修改的文件恰好两个**：`tests/amane_compat/test_amane_compat_scope_gate.py` 与 `tests/amane_compat/test_amane_compat_evidence_reconciliation.py`。HG-1 commit 的 diff 文件集合必须**精确等于**这两个文件。
2. **唯一允许被移交（移除并由 P6 新范围门接管）的工作树断言恰好是下列两处，且仅此两处**：
   * `test_amane_compat_scope_gate.py::test_working_tree_changes_are_limited_to_the_allow_list_as_well`（整个测试函数，约 6 行；它是一个“工作树 ⊆ P5-C2 allow-list”的断言，其语义在 P6 分支上必然为假）；
   * `test_amane_compat_evidence_reconciliation.py::_changed_since_authority()` 中的 `working = [... git status --porcelain ...]` 分量（它是**输入采集**，不是 `assert`；删除后该函数只返回已提交 diff，调用它的两个 `assert` 语句保持原样）。
   这两处的语义由 `tests/amane_batch/test_amane_batch_scope_gate.py` 以 P6 的 allow-list 承接（见第 7 条）。**除这两处之外，不删除、不弱化、不改写任何其它 assertion 或测试函数**；机检：两个文件在 HG-1 后的“测试函数名集合”恰好等于 Frozen Base 版本的集合减去上面那 1 个函数名；两个文件除被移交处外的 `ast.Assert` 节点数与 Frozen Base 相同。
3. **四组历史模式常量逐字不变**：`ALLOWED_PATTERNS` / `FROZEN_PATTERNS`（scope_gate）与 `RECONCILIATION_ALLOWED` / `RECONCILIATION_ZERO_DIFF`（reconciliation）这四个模块级常量的 AST 与 `git show 4189b95…:<path>` 中的版本**相同**；因此 allow-list 覆盖与 frozen-pattern 覆盖都不减少。
4. **唯一的“上界重绑”**：把 `git diff --name-only <BASE>..HEAD` 的上界由浮动 `HEAD` 改为不可变常量 `P5_C2_REVIEWED_HEAD = "1ef23247c2c65649589e9919c00093901bbcb517"`（P5-C2 Final Reviewed Technical Head；上表实测两个门禁在该上界上都通过；Final Closure 只追加了纯状态的 `adapters/amane/README.md` 与 `docs/review/P5_C2_HANDOFF.md`）。这同时使 reconciliation 门禁恢复为绿。该常量是 HG-1 唯一新增的模块级名字。
5. **不新增 `skip` / `xfail`**，不关闭 mutation / non-vacuity，不改变任何夹具、导入或其它测试的行为；“Base 可达且是 HEAD 祖先”测试保持不变。
6. **diff 行数上限冻结为 60 行**：HG-1 commit 相对其 parent 的 `git diff --numstat` 对这两个文件的 `added + deleted` 之和 **≤ 60**。超出 → HG-1 违约，停止并 `AUTHORITY ESCALATION REQUIRED`（不再由 Reviewer 在 S1 之后决定）。
7. **P6 新范围门必须覆盖自身的 diff 与工作树，并承接被重绑后失去活动范围的保护**（`tests/amane_batch/test_amane_batch_scope_gate.py`）：
   * `git diff --name-only 4189b95…..HEAD` ⊆ P6 allow-list，闭合范围零 diff；
   * 工作树（`git status --porcelain=v1 --untracked-files=all`）⊆ P6 allow-list（承接被移交的两处工作树断言）；
   * **文本控制字符检查**：对 `4189b95…..HEAD` ∪ 工作树 内全部 `.py` / `.md` / `.json` / `.toml` 文件检查不含 C0 控制字符（`[\x00-\x08\x0b\x0c\x0e-\x1f]`）。原先的 `test_no_source_file_in_the_change_set_contains_control_characters` 因上界重绑只覆盖到 `1ef23247…`，P6 新增文件不再被它保护；本检查把保护**重新建立**在 P6 的活动范围上，不得省略；
   * 四个历史常量 AST 与 Frozen Base 相同、HG-1 diff 文件集合与行数上限、HG-1 之外的 CLOSED 测试零 diff。
8. 这是 **S1 的第一个提交**（独立 commit，commit message 标注 `HG-1`），随 C-level Review 一并审查。**本设计轮次不执行 HG-1：`Tests Modified = NO`。**

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
| `audit.py` | `HostFailureKind` / `CancelOutcome` / `SubmissionState` / `CleanupTrigger` / `AggregateTerminal` / `RecordFreshness` / `HostAttemptRecord`（含组合校验 `__post_init__`）/ `AmaneHostAuditSnapshot` / 内部 `_AuditLedger` | 公共 + 私有 |
| `_wire.py` | 宿主响应的**有界**严格解析：迭代式 JSON 结构预扫描（第 8.4 节）+ `HostTask` / `HostBatchCancelResult` / `HostMetadata` / `HostWorkerState` | 私有 |
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
允许：标准库（asyncio / dataclasses / datetime（仅用于第 11.3.4 节 `record_freshness` 的 ISO-8601 解析与比较）/ enum / ipaddress / json / math / time / types / urllib.parse / http.cookiejar / re / collections / typing）
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
| `field_sources` 的值 = route 中的站点 id（插件即 `ffcc.fc2-metadata`），键 = `MetadataField` 值（`title` / `poster_urls` …） | `aggregate/engine.py`、`enums.py: MetadataField` | 相同 | 相同；任务结果侧的归属证据（第 11.3 节）。**它只描述 SCRAPE 当时想写入什么，不描述最终持久化的记录**（见下面两行） |
| 持久化 Metadata 的锁定 / 来源保留 | `db/repos/metadata.py: upsert_metadata`（AUTO 写入）直接写入，无字段锁；`field_sources` 随记录持久化；手工 `PATCH`（`update_metadata`）**不修改** `field_sources` | `_locked_fields_of()` / `_filter_locked()`：AUTO 写入**跳过**锁定列，并让 `field_sources` **保留锁定字段的既有来源**；手工 `PATCH` 把写入的列加入 `locked_fields`，同样**不改** `field_sources`；用户解锁后锁不再保护 | **DIFF-P6-03 的扩展**：任务的 `ScrapeResult.field_sources` 不等于最终展示列的来源，**持久化 `field_sources` 也不是展示列实际内容的证明**（手工写入后仍显示旧来源）。因此 P6 不以任何 `field_sources` / 锁 / 时间戳作内容归属证据，改用 `raw`（第 11.3 节） |
| `raw`（插件的原始记录） | `aggregate/engine.py`：`raw = {source_key: MediaMetadata.model_dump()}`；`handlers/scrape.py` 与展示列同一次 `upsert_metadata(raw=…)`；`use_cache=[]` 时每个来源重新抓取；翻译 / FacetRule / 物化不改写 `raw`；公开 `PATCH` 不能写 `raw`（`ignore_fields`） | 相同（`MediaMetadata` 同形；`SearchQuery` 内部字段变化不影响 `raw`） | 相同；`GET /api/metadata/{id}` 返回 `MetadataResponse.raw`。**这是 P6 的内容来源**（第 11.3.2 节） |
| `MetadataField`（`field_sources` 的键空间） | `enums.py`：`title, plot, actors, directors, tags, series, release, runtime, publisher, studio, poster_urls, thumb_urls, trailer_urls, extrafanart, score` | 相同 | 相同；仅用于理解宿主，**P6 不以它作证据**。`source_urls` / `external_ids` 在 P6 中恒为空（第 11.4 节） |
| 默认 worker 并发 | `config/manager.py: WorkerConfig.concurrency = Field(default=10, ge=1, le=64)`；`app/bootstrap.py` 把 `hot.worker.concurrency` 传给 `Worker`。（`scheduler/worker.py` 的构造函数默认值 `3` 只是类默认，**不是**宿主实际配置） | 相同（`WorkerConfig.concurrency` 缺省 10） | 相同；**Amane 缺省并发是 10，不是 3**（第 14 节、L6-07） |
| 任务认领与取消登记 | `Worker._run_loop`：`claim_next_task()`（DB 状态已是 RUNNING）→ `asyncio.create_task(self._execute(task))`；`_running_tasks[task_id]` 仅在 `_execute` 内部、**获得信号量并通过 handler 查找之后**才登记（`worker.py` 约 159–162 行） | `_run_loop` 在 claim 之后同步地 `create_task` 并登记 `_active_tasks`；`_execute` 另有取消落点的条件补写（`fail_running_task`） | **DIFF-P6-01 / DIFF-P6-05**：v0.15.0 存在“DB 已 RUNNING、协程尚未登记”的窗口（含信号量等待），此窗口内取消 API 的回退会把任务记为 FAILED，而执行协程仍会继续；v0.18.0 窗口缩小为 claim 提交返回到登记之间的最小窗口，**设计期无法证明其不存在**。第 10.3 节据此撤销“FAILED ⇒ 已停止” |
| SCRAPE 空结果 | `if not result.field_sources:` → 任务 FAILED（"No metadata found"） | `if not result.raw:` → 标量可全空仍 DONE | **DIFF-P6-02**：v0.18.0 可能 DONE 但没有 title（第 11.2 节会 fail closed） |
| Metadata 详情 | `GET /api/metadata/{metadata_id}` → `MetadataDetailResponse{metadata: MetadataResponse,…}`；404 若不存在 | 相同路由与外层模型 | 相同 |
| `MetadataResponse` | 含 `number,title,actors,studio,publisher,release,runtime,tags,plot,poster_urls,thumb_urls,extrafanart,extrafanart_urls,source_urls,external_ids,field_sources,raw,…` | 相同，**多** `locked_fields` | **DIFF-P6-03**：client 为容忍额外键的 reader |
| Worker 暂停状态 | `GET /tasks/worker` → `{paused}`；`POST /tasks/worker/pause|resume` | 相同 | 相同；P6 只读 |
| SCRAPE 可能自行物化 Resource | `handlers/scrape.py` → `media.materialize_images`，受 `scraping.download_resources`（缺省含 poster / thumb / extrafanart…）控制；`crop_poster` 缺省 True 时 poster 可能被替换为宿主内部 URL（`/api/resources/<hash>`） | 相同 | **DIFF-P6-04** 之外的共同事实；第 18 节 |
| SCRAPE 可能扇出 `ACTOR_SCRAPE` 后继任务 | `actor_scraping.auto_scrape` 缺省 `True` | 相同 | 宿主拥有；第 27 节 L6-08 |
| `ContentType.FC2 = "fc2"` | `parsing/file_info.py` | 相同 | 相同 |

### 7.4 版本差异白名单（只允许这五项；出现其它差异 = U6-6）

| ID | 差异 | P6 处理 |
|---|---|---|
| DIFF-P6-01 | 取消 RUNNING 任务的回退：v0.15.0 用无条件的 `repo.fail_task`（可能把“刚好完成的任务”改写成 FAILED / “Cancelled by user”）；v0.18.0 用 `fail_running_task`（不覆盖终态） | P6 不依赖任何一种：取消路径只使用“取消请求之后观察到的结构化数据库终态”（第 10.3 节），**该终态只证明任务记录的状态，不证明执行协程已停止**；不读 `error` 文本；v0.15.0 的改写窗口记入 L6-04 |
| DIFF-P6-02 | v0.18.0 的 SCRAPE 在标量全空时仍可 DONE | 第 11.2 节最低成功门 fail closed（`HOST_METADATA_BELOW_MINIMUM`） |
| DIFF-P6-03 | v0.18.0 的 `MetadataResponse` 多 `locked_fields`，且 AUTO 写入保留锁定字段的既有 `field_sources`（见 7.3 表） | P6 的 reader **不读取** `locked_fields` / `field_sources`（它们不是内容证据，第 11.3 节），多余键被忽略；因此两个版本走**同一条代码路径**，无版本分支 |
| DIFF-P6-04 | 内部实现：v0.15.0 `worker.cancel_task`（只看 `_running_tasks`）；v0.18.0 `runtime.cancel_task`（`app/runtime.py`：先问当前 worker，再问被退役的旧 worker `_retiring`，覆盖宿主重建 worker 期间仍在运行的任务） | 对 public 表面不可见；P6 只依赖取消后观察到的结构化数据库终态（且不据此推断协程已停止）；仅记录 |
| DIFF-P6-05 | “DB 已 RUNNING、执行协程尚未登记”的窗口：v0.15.0 的 `_running_tasks` 在 `_execute` 内信号量与 handler 查找**之后**才登记（窗口含信号量等待）；v0.18.0 在 claim 后同步登记，窗口缩小为 claim 提交返回到登记之间 | 取消 API 在该窗口内只能经回退把记录改为 FAILED，**协程仍可能继续运行并写 Metadata**。P6 不读 worker 私有运行表，因此无法区分；第 10.3 节把“数据库终态已观察到”与“执行已停止”解耦，`execution stop` 永远是 UNVERIFIED，记入 L6-04 |

### 7.5 P6 不使用的宿主能力（理由）

* **WebSocket 进度**：`/api/ws` 的认证走 cookie / 握手，且 P4-C8 §11.4 没有进度契约；不引入（第 17 节）。
* **Task 列表过滤**：无按 number 过滤；用来“找回丢失提交的任务”会命中用户自己的同号任务，违反“只操作自己的任务”。放弃找回，改为显式的 `submission_ambiguous`（第 10.4 节）。
* **`/api/config`**：返回 site cookie / token；生产代码零读取（U6-5）。验收宿主的配置回读只发生在测试工具里（第 22 节）。
* **`/api/tasks/batch` retry**：会创建新任务并与 P4 重试相乘；禁止。

### 7.6 宿主前置条件（P6 的正确性假设；违反时 fail closed，不静默降级）

```text
H6-1  宿主的 FC2 内容 route 恰好是 [ffcc.fc2-metadata]（独占 route）。
      P6 不读取、不修改宿主配置；独占 route **只是前提，不是证明**。每个条目的证明链（第 11.3 节）：任务侧 field_sources 只含插件且含 title（必要条件）；
      字段内容**只**来自 Metadata 的 raw["ffcc.fc2-metadata"]（插件的原始记录，公开 PATCH 不能改写）。任务侧出现非插件来源，或 raw 中没有插件键
      → 该条目 fail closed（HOST_ATTRIBUTION_FOREIGN）。P5 INSTALL 把插件放在 route 最前并保留原站点——P6 需要把其它站点移出该 route（见 L6-01）。
H6-2  宿主任务 worker 未暂停（preflight 检查；暂停时 SCRAPE 永远 QUEUED）。
H6-3  宿主 token 与 P6 凭据一致（401/403 → 结构化 BLOCKED 失败；preflight 提前拒绝）。
H6-4  用户同意“SCRAPE 会把结果写入 Amane 的 Metadata 库”（AmaneHostConfig.acknowledge_host_metadata_writes=True，第 8.2 节）。
H6-5  宿主 base URL 是 origin（scheme://host[:port]），无路径前缀（反向代理路径前缀不在 P6-C1 范围）。
H6-6  宿主 Metadata 是**按番号唯一、跨任务共享**的记录：用户手工编辑、其它任务（含遗留孤儿任务）、字段锁都可能在 SCRAPE 完成与 P6 读取之间改变它。
      P6 只能保证“读取那一刻 raw 中的插件记录被确定性映射为输出”，**不能**证明该记录是本任务的独占产物或不可变快照（第 11.3.4 节、L6-18）。
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
| 不持久化 | 不写盘、不写日志（本包**零 logging**）、不进入 `repr` / 异常文本 / `__cause__` 或 `__context__` 链 / `BatchPreview` / 汇总 / 审计 / 诊断 |
| 不泄漏异常（Design-R1 / R1-03；Design-R2 / R2-02 扩展到整个包） | 见下面第 8.3.1 节。要点：`raise … from None` **不清除** `__context__`，不是安全证明；规则适用于 `src/fc2_amane_batch/**` 的**全部**文件（credential / config / engine / _lifecycle / models / facade / host_client / 任何私有 helper），不只是 `host_client.py` 与 `facade.py` |
| 无环境代理 | `httpx.AsyncClient(trust_env=False)`：忽略 `HTTP_PROXY` / `ALL_PROXY` / `NO_PROXY` / `SSL_CERT_*` / `.netrc` |
| 无 cookie | 宿主在认证成功后会 `Set-Cookie: amane_token`（两个版本）。client 使用“拒绝一切 cookie”的 cookie jar：`client.cookies` 在任何响应之后保持为空；后续请求**不**带 `Cookie` 头 |
| 无重定向 | `follow_redirects=False`；任何 `3xx` → `HOST_HTTP_UNEXPECTED`；因此凭据永不会被带到另一个 origin |
| TLS | `https` 使用 httpx 缺省证书校验；**不存在**关闭校验的参数；证书 / 握手失败 → `HOST_CONNECTION`（结构上无法降级为明文） |
| 明文策略 | 非回环主机必须 `https`（第 8.2 节） |
| 请求头 | 只有 `Authorization`（若有凭据）、`Accept: application/json`、`Content-Type: application/json`（POST）、固定 `User-Agent: fc2-amane-batch/0.1` |
| 连接池 | 有界（`max_connections ≤ 66`，不随批量大小增长）；一个 `AsyncClient` per `AmaneHostClient`（构造时创建，**不**在 import 时创建；`aclose()` 幂等） |

### 8.3.1 异常与凭据边界（整个包；Design-R2 / R2-02）

**1. 保护面（Protected Surface）——合同承诺的对象，逐项可测：**

* **P1 出口异常**：由 `src/fc2_amane_batch/**` 的任何公共入口（含各类 `__init__`）抛出并到达调用方的每个异常 `E`。
* **P2 可达集合 `G(E)`**：以 `E` 为根，沿 `__cause__`、`__context__`（链深至多 8 级，visited 集合防环）、`args`（元素；`list` / `tuple` / `dict` / `set` 再展开一层）、`__notes__`、`E.__dict__` 的值（一层）、以及 `__traceback__` 链上**属于本包的栈帧**（`f_code.co_filename` 位于 `fc2_amane_batch` 包目录内）的 `f_locals` 值（浅层：值本身，容器再展开一层）。调用方 / 测试自己的栈帧不在保护面内。
* **P3 输出文本与结构**：`str(E)`、`repr(E)`、`traceback.format_exception(E)` 的全文；`AmaneBatchPreview` / `AmaneBatchSummary` / `AggregationResult` / `AmaneHostAuditSnapshot` / P4-C9 诊断投影的 `repr` 及可序列化结果。

**2. 禁入内容 `F`**：`G(E)` 与 P3 中不得出现：(a) 任何等于或**包含** token canary 的 `str` / `bytes`；(b) 任何 `httpx.Request`、`httpx.Response`、`httpx.Headers`、`httpx.HTTPError` 及其子类实例；(c) 任何 `UnicodeError` 实例及任何持有其 `.object` 的对象；(d) 响应体 `bytes`；(e) 宿主返回的文本、URL、任务 id（异常文本）。

**3. 所有权状态不在承诺内（区分“新引入的泄漏”与“对象本身持有的认证状态”）**：`AmaneHostCredential`（持有 token）、`AmaneHostConfig`、`AmaneHostClient`、`AmaneAggregationEngine`、`AmaneBatchIntegration` 以及它们内部的 `httpx.AsyncClient` / `httpx.Auth` 对象，是**调用方自己创建并持有、本来就含认证状态**的对象。它们可以作为帧局部 `self` 出现在 `G(E)` 中，遍历**不进入**这些对象（视为不透明）。合同**不**承诺“从这些对象出发不可达凭据”——调用方持有 client，就能经其属性到达凭据，这不是异常泄漏。合同承诺的只有：**异常、输出文本与结果对象没有新引入 `F` 中的任何内容**，且凭据对象本身的 `repr` / `str` / `format` 恒为 redacted、不可 pickle / copy（第 8.3 节）。

**4. 构造规则（冻结；AST 守卫扫描 `src/fc2_amane_batch/**/*.py` 的每个文件，含未来新增的私有 helper）：**

| # | 规则 |
|---|---|
| C1 | 任何 `except` 处理体内**不得**出现 `raise <表达式>` 或 `raise … from <任何>`（含 `from None`）。允许的唯一例外是 `except asyncio.CancelledError:` 内的**裸** `raise`（重新抛出同一个 `CancelledError`，其中不含凭据）。需要转换时：处理体内只做赋值（分类为枚举 / 布尔局部），**离开处理体之后**再 `raise` 固定异常 |
| C2 | 本包异常的构造实参只允许：闭合枚举成员、固定字符串字面量、整数计数；禁止传入 token、URL、宿主文本、`str(exc)`、`exc.args` 或任何变量字符串（AST 守卫） |
| C3 | 凭据 / 配置校验必须用**不抛异常的纯谓词**（`str.isascii()`、`str.isprintable()`、`len`、字符区间判断等）；**禁止**对 token 调用 `.encode()` / `.decode()` / `int()` 等可能抛 `UnicodeError` / `ValueError` 的转换，也不得用 `try/except` 包裹对 token 的操作（`UnicodeEncodeError.object` 会保留原始 token） |
| C4 | **栈帧局部**：接收原始 token 的本包函数（`AmaneHostCredential.__init__` 及其 helper）在校验失败路径上，必须在 `raise` **之前**把持有 token 的局部名（含形参名）重新绑定为 `None`；因此 `E.__traceback__` 中本包帧的 `f_locals` 不含 token。成功路径只把 token 存入凭据对象的私有属性。`httpx.Auth.auth_flow` 内的 token 局部随函数返回而失效 |
| C5 | **传输两层**：`host_client` 的内层 `_transport(...)` 只返回纯数据 `(kind \| None, status \| None, body_bytes \| None)`，**永不抛出本包异常**，且 `httpx.Request` / `Response` / 异常对象不出现在其返回值或外层帧局部；响应流读取（含流中途的 httpx 异常）在内层完成、分类并关闭 `Response`。外层 `_call(...)` 只持有纯数据，**离开全部 `except` 之后**才 `raise AmaneHostCallError(kind)` |
| C6 | engine / `_lifecycle` / facade / models：捕获 `AmaneHostCallError` 只读取 `.kind` 赋给局部；`AmaneHostPreflightError`、`AmaneBatchRetryError`、`AmaneBatchContractError`、`AmaneBatchInputError` 一律在 `except` 之外构造；`aggregate` 的 `except Exception` 兜底只做分类（记录类名常量）并在块外决定返回 FAILED 或抛 `AmaneBatchContractError`（固定文本） |
| C7 | 本包永不调用 `add_note()`（`__notes__` 恒不存在） |

**5. 强制失败矩阵（E6-17；每一条适用路径逐项检查 `__cause__` / `__context__` / `args` / `__notes__` / 本包帧 `f_locals` / `str` / `repr` / traceback 文本 / 审计·汇总·preview，并断言 `F` 不出现）：**

| 对象 | 必须覆盖的失败 |
|---|---|
| `AmaneHostCredential` / `AmaneHostConfig` | 非法 ASCII（控制字符）、非 ASCII、含空白、空串、超长（> 512）token；非法 base_url（userinfo / 非回环 http / 带路径）；数值越界；`acknowledge_host_metadata_writes=False` |
| `AmaneHostClient` 全部 5 个公共方法 | `401` / `403`、`5xx`、超时、连接失败（含 TLS 证书失败）、响应体过大、非 JSON、严格 reader 违规、结构超限（`HOST_RESPONSE_TOO_COMPLEX`）、流中途断开 |
| `AmaneHostPreflightError` | 4 个 reason 全部 |
| `AmaneAggregationEngine` | 内部契约错误（`AmaneBatchContractError`）、非规范号、未预期 `Exception`、`CancelledError`（含清理期间） |
| `AmaneBatchIntegration` | 非法输入、retry 拒绝（3 个 reason）、`aclose` 之后调用、门面把 `AmaneHostCallError` 转换为 `AmaneHostPreflightError` 的路径 |

**红绿孪生**：① 凭据路径——`try: token.encode("ascii") except UnicodeEncodeError: raise AmaneBatchConfigError(…) from None` 的变体必须被判红（`__context__` 持有带 `.object=token` 的 `UnicodeEncodeError`）；纯谓词 + 块外抛出的实现为绿；② 校验失败时 `token` 形参仍留在本包帧局部的变体为红，已重新绑定为 `None` 的为绿；③ `_transport` 在 `except` 内 `raise AmaneHostCallError(...) from None` 的变体为红；④ 外层 `_call` 帧局部仍持有 `Response` / `Request` 的变体为红。

### 8.4 响应处理

* 响应体**流式读取**并设上限 `MAX_RESPONSE_BYTES = 8 * 1024 * 1024`；超限 → `HOST_RESPONSE_TOO_LARGE`（不读完）。
* 只接受 `application/json` 内容（或无 `content-type` 但可被严格 JSON 解析）；JSON 解析使用拒绝 `NaN` / `Infinity` 的严格模式。
* **有界 JSON 结构（Design-R1 / R1-07；Design-R2 / R2-03 修正成本模型）**：字节数上限不等于结构上限（`[[[[…` 几 MB 就可使递归解析器耗尽栈，数百万个 `[]` 可耗尽内存）。字节检查通过后、`json.loads` **之前**，必须对原始字节做一次**迭代式（非递归）预扫描**，并强制下列确定常量（均进入 `__all__`，测试逐值断言）：

  | 常量 | 值 | 度量（冻结定义） |
  |---|---|---|
  | `MAX_JSON_DEPTH` | `32` | 当前打开的数组 / 对象的嵌套层数；顶层容器深度为 1；第 33 层即超限 |
  | `MAX_JSON_NODES` | `200_000` | 累计 token 数：每个容器（含空对象 / 空数组）、每个字符串（含对象键）、每个数字 / `true` / `false` / `null` 字面量各计 1 |
  | `MAX_JSON_COLLECTION_ITEMS` | `20_000` | 单个数组的元素数、单个对象的成员数（空容器为 0）各自的上限 |

  各自“= 上限”通过、“= 上限 + 1”拒绝。数值选择依据不变：两个版本的合法响应——`TaskResponse`（含 `payload` / `result`）与 `MetadataDetailResponse`（含 `raw`，其中是插件原始记录与可能存在的其它来源记录）——在真实宿主上的实测最大值须低于上限的 **1/4**（S1 第 0 步实测并写入 HANDOFF；任何一项超过 1/4 → 停止并提交修订，不得悄悄放宽）。

  **成本模型（修正）**：设 `B` = 实际被扫描的输入字节数，`B ≤ MAX_RESPONSE_BYTES`。扫描必须逐字节（或等价地按 token 跳转）经过字符串内部与空白，所以一个超长字符串或长空白即使只有一个结构节点也要付出其长度的代价。因此：**正常通过扫描时 Time = O(B)**；触达任一结构上限时可以**提前拒绝**，但**不声称**成本只取决于 token 数。**辅助空间**：O(`MAX_JSON_DEPTH`)（每层一个元素计数器的栈）+ 固定个数的标量计数器 / 状态位；不递归、不复制响应体、不为每个 token 或字符串物化子串（只保留位置）。
  **扫描语义**：对语法合法的 JSON，三个计数与上面的定义**完全一致**（测试以独立的递归参考计数器在小输入上逐项对账）；对非法 JSON，预扫描只需在 O(B) 内终止且辅助空间不超界（深度下溢取 0、未闭合字符串扫到末尾即停），随后由 `json.loads` 拒绝为 `HOST_SCHEMA_INVALID`。预扫描必须正确处理：字符串内部的 `{ } [ ] , :`、转义引号 `\"`、连续反斜杠 `\\`、`\uXXXX`、对象键、空对象 / 空数组、未知嵌套字段。
  **时序与失败**：超限在 `json.loads` **之前**拒绝 → `HOST_RESPONSE_TOO_COMPLEX`（封闭枚举，映射见第 12.1 节），不保留原始响应；`json.loads` 的 `RecursionError`（纵深防御，理论上不应发生）映射为 `HOST_SCHEMA_INVALID`，**不得**把 Python 默认递归限制当作主要防护；`_wire.py` 之后的遍历只读取已知键，不对任意嵌套结构做递归遍历。
* 状态码：`submit` 必须是 `202`；其它四个操作必须是 `200`。其它 `2xx` → `HOST_HTTP_UNEXPECTED`；`401/403` → `HOST_AUTH_REJECTED`；`429` →
  `HOST_RATE_LIMITED`；`5xx` → `HOST_SERVER_ERROR`；`404` 见各操作；其它 `4xx` / `3xx` / `1xx` → `HOST_HTTP_UNEXPECTED`。
* **宿主返回的任何文本**（`error`、`detail`、响应体、日志）都不进入控制逻辑、不进入异常、不进入结果、不进入审计。解析 `error` 字段只用于类型校验，
  之后立即丢弃。

### 8.5 严格 reader（`_wire.py`）

* `HostTask`：必需 `id`（`int`，非 `bool`，`≥ 1`）、`type`（`str`）、`status`（`"queued"|"running"|"done"|"failed"`）、`payload`（`dict`）、
  `result`（`dict | None`）；`finished_at`（**可选**，`str | None`；仅用于审计 `record_freshness`，缺失 / 不可解析不是失败）；`error`（`str | None`，只验类型、不保留）。额外键忽略。
* `HostBatchCancelResult`：必需 `affected` / `skipped` / `missing`（非负 `int`，非 `bool`）。
* `HostMetadata`（Design-R2 / R2-01 缩小为内容证据所需的最小集合）：必需 `id:int`、`number:str`、`raw:dict`（其中只会进一步读取精确键 `ffcc.fc2-metadata`，由第 11.3.3 节 `PluginRaw` reader 解析）；
  **可选** `title:str|None`（仅用于审计 `display_title_diverged`，类型非法 ⇒ `HOST_SCHEMA_INVALID`）、`updated_at:str|None`（仅用于审计 `record_freshness`）。
  **所有其它展示列与键（`actors` / `tags` / `*_urls` / `studio` / `field_sources` / `locked_fields` / `source_urls` / `external_ids` / 时间戳 …）一律忽略且不保留**；它们不是内容证据，也不进入输出。
* **`files` 等宿主返回的文件系统路径**（`MetadataDetailResponse` 的 `files` 可能含用户本机路径）：reader 不读取、不存入任何 P6 对象，因此不得出现在输出、异常、日志、审计、诊断中；E6-17 用含 canary 路径的 `files` 响应断言此点。
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

### 9.2 提交（`submit`）与创建基数（Design-R1 / R1-02）

**撤销旧不变量**：旧稿写“一次 aggregate 尝试 = 恰好一个新创建的 SCRAPE 任务”。这在 401 / 连接失败 / 响应丢失下不成立（请求可能没抵达宿主，也可能已创建而响应丢失）。把“尝试了几次 POST”与“宿主实际创建了几个任务”混为一谈会让任务账本、重试与取消的结论失真。冻结为下列**四个封闭状态**（`SubmissionState`，进入审计，不进入语义输出）：

| `SubmissionState` | 含义 | 任务数 |
|---|---|---|
| `SUBMISSION_NOT_ATTEMPTED` | `POST` 从未发出（非规范号、准入前取消、门面 / admission 在发请求之前终止等） | P6 创建了 **0** 个 |
| `SUBMISSION_ATTEMPTED` | `POST` 已开始发送、结果尚未知；**仅作为 aggregate 进行中的瞬态存在，终态审计记录不得停在此值** | 未定 |
| `CREATION_CONFIRMED` | 响应为精确 `202`，且 `HostTask` 通过严格 reader（得到合法 `id`） | 宿主确认存在 id 为该值的任务（回显不符时仍是此状态，第 3 步） |
| `CREATION_UNKNOWN` | `POST` 已发出，但没有 `202` + 合法 `id`：超时 / 连接中断 / 响应丢失 / 响应过大或过于复杂 / 非 JSON / schema 非法，或宿主给出了非 `202` 状态（含 `401` / `403` / `429` / `4xx` / `5xx`） | **未知**：可能 0 个，也可能 ≥ 1 个 |

冻结规则：

1. **每个进入提交阶段的 aggregate 最多发送一次 `POST /api/tasks`；永不自动重试**（包括传输层：`httpx` 不得配置 `retries`；engine / facade 也不得因为任何失败或不确定状态而再次提交）。重试一次非幂等创建会产生重复任务。
2. 记录 `started = clock()`（单调时钟），分配审计 `seq`，状态置 `SUBMISSION_ATTEMPTED`，发送 `POST /api/tasks`（第 8.1 节）。
3. `202` 且 `HostTask` 通过严格 reader → `CREATION_CONFIRMED`；并做 **echo 校验**：`type == "scrape"`、`payload.number == number`、`payload.content_type == "fc2"`。
   不符 → `HOST_SCHEMA_INVALID`，状态**仍是** `CREATION_CONFIRMED`（任务 id 已知 → 进入 ABANDONING 清理，因为宿主确实对这次 `POST` 创建了任务）。
4. 其它所有结果 → `CREATION_UNKNOWN`。**`CREATION_UNKNOWN` 不得被自动折算为“零个”或“一个”**：
   * `401` / `403`：宿主的认证中间件先于路由执行，期望零个任务，但 P6 **不据此断言**为零（仍记 `CREATION_UNKNOWN`，失败种类 `HOST_AUTH_REJECTED` 单独说明原因）；
   * 超时 / 连接失败 / 响应丢失：宿主可能已创建任务而 P6 不知道 id。P6 **不**尝试找回（第 7.5 节：列表过滤会命中用户自己的同号任务）；
   * 结果为 `FAILED(HOST_TIMEOUT / HOST_CONNECTION / HOST_AUTH_REJECTED / …)`，审计 `submission = CREATION_UNKNOWN`、取消结果 `UNCERTAIN_SUBMISSION_UNRESOLVED`（不是“没有任务”）。
5. **不得以“状态不确定”为由重试**：engine 在 `CREATION_UNKNOWN` 之后不会再提交；`retry_failed` 是调用方显式发起的新操作（第 13.3 节），每个被选入的条目会发起**新的** aggregate 与新的 `POST`，它可能与此前未解析的遗留任务并存。审计快照的 `creation_unknown` 计数用于让调用方知情，P6 不据此自动阻止或自动放行重试。
6. 任务账本不变量（用于 E6-13 / E6-14 的宿主账本对账，按番号、跨全部轮次累计）：
   `CREATION_CONFIRMED 次数 ≤ 宿主上由 P6 创建的该号 SCRAPE 任务数 ≤ CREATION_CONFIRMED 次数 + CREATION_UNKNOWN 次数`；
   无任何 `CREATION_UNKNOWN` 的番号：宿主上该号任务数 **恰好等于** `CREATION_CONFIRMED` 次数（成功番号恰好 1 个；失败后恢复的番号恰好 2 个）。

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
* 观察失败重试是**对幂等 GET 的有界重复观察**，不重复执行工作，不创建任务，因而不构成第二个重试执行者（第 13 节）。
* 一次 aggregate 的请求数上界：`1`（submit）+ `⌈deadline / poll_interval⌉ + max_consecutive_poll_errors`（observe）+ `1`（metadata）+ 清理预算内的请求。

### 9.4 终态处理

* `status == "failed"`（且 P6 **没有**发出过取消）→ `FAILED(HOST_TASK_FAILED)`。**不**读取 `error` 文本，因此无法区分“番号不存在”与“来源故障”（L6-05）。
* `status == "done"`：
  1. `result` 必须是 `dict`，且含 `metadata_id`（`int`，非 `bool`，`≥ 1`）、`field_sources`（`dict[str,str]`）、`failed_sites`（`list[str]`）；否则
     `HOST_RESULT_INVALID`（“DONE 但缺 metadata_id / 结果结构非法”）。
  2. 任务侧归属校验（第 11.3.1 节）。
  3. `GET /api/metadata/{metadata_id}`（单次，不重试）。`404` → `HOST_METADATA_MISSING`；其它失败按第 8.4 节映射。
  4. 插件原始记录证据（第 11.3.2 节）与映射（第 11.4 节）。

### 9.5 门面 preflight（`AmaneHostClient.probe_worker`）与门面调用顺序（Design-R1 / R1-05）

**撤销旧声明**：旧稿声称门面 busy-first、“与 P4 一致，委托 P4 的 busy 守卫”。这无法实现：P4 `BatchOrchestrator._claim()` 是**私有**方法，只在其公开 `preview()` / `execute()` / `preview_retry()` 内部使用；P6 不得调用私有符号（第 6.4 节），也**不会**为保留这句话而复制 P4 的内部锁、引入第二套 admission 机制或 scheduler。冻结的是**实际调用顺序**，而不是无法实现的错误优先级：

```text
preview(items):
    1. 输入形态校验（items 为 list / tuple 且元素均为 DiscoveredMediaItem）→ AmaneBatchInputError      本地，零网络
    2. worker preflight：一次 GET /api/tasks/worker                                                       只读
    3. await orchestrator.preview(items)        ← P4 的 busy claim 只发生在这一步的入口；P4 已忙则其公开拒绝原样传播
preview_root(media_root, policy):
    参数校验（本地）→ worker preflight → discover_media（只读）→ await orchestrator.preview(items)
retry_failed(previous):
    previous 校验（FOREIGN_PREVIEW）→ 子集选择（NO_RETRYABLE_ITEMS / ROUND_LIMIT；纯函数、本地）
    → worker preflight → await orchestrator.preview(subset)
```

由此得到的、可测试的后果：

* P4 已忙（另一个 `preview` 正在运行）时，后到的调用可能已完成第 1、2 步——其中包含一次只读 `GET`——随后才被 P4 的公开接口拒绝。**不声称零网络访问**；声称的只是：被拒绝的调用**不提交任何 `POST /api/tasks`**，P4 的 busy 拒绝由 P4 原样给出，P6 不吞、不转换。
* 同时存在非法参数与 P4 busy 时，按上面的实际顺序，P6 自身的校验（第 1 步）先于 P4 busy，因此返回 `AmaneBatchInputError`；P6 **不承诺**“busy 优先于参数错误”或反之的全局优先级。
* preflight 不提交 SCRAPE、不创建任何宿主任务、不修改业务数据。“零副作用”的准确含义仅是**不创建 SCRAPE / 其它任务，也不修改 Task / Metadata 等业务数据**；宿主可能记录访问日志或指标，P6 不对此作任何声明。
* P6 门面**不绕过** P4 的并发控制：宿主 SCRAPE 只会由 P4 `BatchScheduler` 驱动的 `engine.aggregate` 发出；门面不直接调用 `engine.aggregate`，也不自行 `gather` / 开 task（AST 守卫，M6-20）。
* 若实现者发现“不新增操作 admission guard 就无法满足某条必需安全不变量”，**停止**并报告设计升级需求（U6-10），不得悄悄引入锁。

| 结果 | 行为 |
|---|---|
| `200 {"paused": false}` | 继续 |
| `200 {"paused": true}` | `AmaneHostPreflightError(WORKER_PAUSED)`（未创建任何宿主任务） |
| `401/403` | `AmaneHostPreflightError(AUTH_REJECTED)` |
| 超时 / 连接失败 | `AmaneHostPreflightError(HOST_UNREACHABLE)` |
| 其它 / 结构不符 | `AmaneHostPreflightError(PROTOCOL_MISMATCH)` |

引擎本身不做 preflight（便于直接注入与单测）。preflight 是**整批前置条件**，在任何任务被创建之前失败，因此不违反“单个条目失败不得拖垮整批”。`AmaneHostPreflightError` 在捕获 `AmaneHostCallError` 的 `except` 块**之外**构造（第 8.3 节：`__context__` 为 `None`）。

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

### 10.3 提交、清理与取消结果的正交模型（Design-R2 / R2-05 重写）

**三个必须分开的层次（Design-R1 保留，不得互相推断）**：

| 层次 | 含义 | P6 能否通过公开结构化 API 观察 |
|---|---|---|
| L1 请求层 | 取消请求已发出 / 被宿主受理（`affected` / `skipped` / `missing`） | 能 |
| L2 记录层 | 宿主**数据库里的任务记录**到达终态（`done` / `failed`） | 能（`GET /api/tasks/{id}` 的 `status`） |
| L3 执行层 | 宿主里**执行该任务的协程已经停止**，不会再写 Metadata 或产生其它宿主副作用 | **不能**：P6 不读 worker 私有运行表、不读 SQLite、不解析错误文本 |

`CONFIRMED_STOPPED` 保持撤销（DIFF-P6-01 / DIFF-P6-05）：`failed` 只证明 L2；**不存在任何会断言 L3 已达成的枚举值**；L3 对每一次放弃 / 取消都是 `UNVERIFIED`。

**R1 的矛盾**：旧稿一边把 `NOT_APPLICABLE` 绑定到 `SUBMISSION_NOT_ATTEMPTED`（§10.3），一边又写“无取消时为 `NOT_APPLICABLE`”（§20.5）。正常成功路径是 `CREATION_CONFIRMED` 且**没有任何取消**，其 `cancel` 应是 `NOT_APPLICABLE`——任务已创建不等于发生了取消。本版把四个维度**正交**冻结：

```text
S  SubmissionState     SUBMISSION_NOT_ATTEMPTED | CREATION_CONFIRMED | CREATION_UNKNOWN         （终态记录不得为 SUBMISSION_ATTEMPTED）
T  CleanupTrigger      NONE | CALLER_CANCEL | DEADLINE | OBSERVATION_FAILURE | ECHO_MISMATCH |
                       SUBMISSION_UNRESOLVED | INTERNAL_ERROR | FATAL_BASEEXCEPTION             是什么触发了清理 / 放弃路径；NONE = 没有触发
C  CancelOutcome       见下表（9 个成员）                                                       清理路径的结果；NOT_APPLICABLE ⇔ T == NONE
R  AggregateTerminal   SUCCESS | FAILED | RAISED | CANCELLED                                      aggregate 对 P4 的终态
```

#### `CancelOutcome`（封闭枚举，9 个成员；全部来自结构化观察）

| 值 | 含义 | 观察依据 |
|---|---|---|
| `NOT_APPLICABLE` | **没有触发任何清理 / 取消路径**（`T == NONE`）。正常成功与未取消的失败（含 `HOST_TASK_FAILED`、`done` 之后的映射失败）都是此值，**不论任务是否已创建** | 无 |
| `NOTHING_TO_CANCEL` | 清理被触发，但宿主上没有可取消的东西：`S == SUBMISSION_NOT_ATTEMPTED`（`POST` 从未发出） | 请求账本里没有 submit |
| `TERMINAL_FAILED_OBSERVED` | 取消请求之后，观察到该 id 的数据库终态 `failed`。**仅证明记录为 FAILED；不证明协程已停止，不证明之后不会再有宿主侧写入** | `status == "failed"` |
| `TERMINAL_DONE_OBSERVED` | 取消请求之后观察到数据库终态 `done`（宿主已写入 Metadata；是否发生在取消之前 P6 无法区分）。**不会**被当作本次 aggregate 的成功使用 | `status == "done"` |
| `UNCERTAIN_NO_RESPONSE` | 取消请求超时 / 连接失败 / 非预期响应 | 传输 / 状态码 |
| `UNCERTAIN_NOT_TERMINAL` | 取消请求已确认，但预算耗尽时记录仍是 `queued` / `running` | 结构化 `status` |
| `UNCERTAIN_SUBMISSION_UNRESOLVED` | `S == CREATION_UNKNOWN`：任务 id 从未获得（可能 0 个，也可能 ≥ 1 个），无法取消 | 无 id |
| `UNCERTAIN_TASK_VANISHED` | 取消响应 `missing ≥ 1` 或观察得到 `404` | 结构化计数 / 状态码 |
| `UNCERTAIN_CLEANUP_INTERRUPTED` | 清理被第二次取消打断，或致命 `BaseException` 之后未做任何清理 I/O | 控制流 |

#### 合法组合规则（`HostAttemptRecord.__post_init__` 强制；违反 ⇒ `AmaneBatchContractError`）

* **LC1** `C == NOT_APPLICABLE` ⇔ `T == NONE`。
* **LC2** `R == SUCCESS` ⇒ `S == CREATION_CONFIRMED` ∧ `T == NONE` ∧ `outcome is None`。
* **LC3** `R == FAILED` ⇒ `outcome` 是某个 `HostFailureKind`；`R ∈ {RAISED, CANCELLED}` ⇒ `outcome is None`；`R == CANCELLED` ⇒ `T ∈ {CALLER_CANCEL, FATAL_BASEEXCEPTION}`。
* **LC4** `S == SUBMISSION_NOT_ATTEMPTED` ⇒ `host_task_id is None`，`C ∈ {NOT_APPLICABLE, NOTHING_TO_CANCEL}`，`T ∈ {NONE, CALLER_CANCEL, INTERNAL_ERROR, FATAL_BASEEXCEPTION}`。
* **LC5** `S == CREATION_UNKNOWN` ⇒ `host_task_id is None`，`T ≠ NONE`，`C ∈ {UNCERTAIN_SUBMISSION_UNRESOLVED, UNCERTAIN_CLEANUP_INTERRUPTED}`（不可能是 `NOT_APPLICABLE` 或任何 `TERMINAL_*`，因为没有 id）。
* **LC6** `S == CREATION_CONFIRMED` ⇒ `host_task_id is not None`，`C ∉ {NOTHING_TO_CANCEL, UNCERTAIN_SUBMISSION_UNRESOLVED}`。
* **LC7** `C ∈ {TERMINAL_FAILED_OBSERVED, TERMINAL_DONE_OBSERVED}` ⇒ `S == CREATION_CONFIRMED` ∧ `T ≠ NONE` ∧ 取消请求已发出（L1）∧ `terminal_status` 与之相符。正常路径（`T == NONE`）观察到的 `done` / `failed` **不是** `TERMINAL_*_OBSERVED`，`C` 仍为 `NOT_APPLICABLE`。
* **LC8** 终态记录的 `S` 永不为 `SUBMISSION_ATTEMPTED`；`R == SUCCESS` 时 `C == NOT_APPLICABLE`。
* 记录只在 `seq` 已分配之后产生；`aggregate` 在分配 `seq` 之前因非规范号抛出 `InvalidCanonicalNumberInputError` 时**没有记录**（零网络、不计入任何计数）。

#### 计数口径（精确；`AmaneHostAuditSnapshot` 的字段由记录推导，测试逐项对账）

```text
submitted               = #{ S ≠ SUBMISSION_NOT_ATTEMPTED }
creation_confirmed      = #{ S == CREATION_CONFIRMED }
creation_unknown        = #{ S == CREATION_UNKNOWN }
abandoned_attempts      = #{ T ≠ NONE ∧ S ≠ SUBMISSION_NOT_ATTEMPTED }      每一个的 L3 都是 UNVERIFIED
uncertain_cancellations = #{ C ∈ UNCERTAIN_* }
```

正常 `SUCCESS`、未取消的 `HOST_TASK_FAILED`、`done` 之后的映射失败**绝不**计入 `abandoned_attempts` / `uncertain_cancellations`。

#### 命名场景 → 合法组合与计数（E6-08 / E6-09 的表驱动用例；每行都有“合法”正例与至少一个“非法变体”反例）

| 场景 | S | T | C | R | abandoned | uncertain | creation_unknown |
|---|---|---|---|---|---|---|---|
| NORMAL_SUCCESS | CONFIRMED | NONE | NOT_APPLICABLE | SUCCESS | 否 | 否 | 否 |
| NORMAL_HOST_FAILED（宿主任务 `failed`，P6 未取消） | CONFIRMED | NONE | NOT_APPLICABLE | FAILED(`TASK_FAILED`) | 否 | 否 | 否 |
| NORMAL_MAPPING_FAILED（`done` 之后映射 / 归属失败） | CONFIRMED | NONE | NOT_APPLICABLE | FAILED(`ATTRIBUTION_FOREIGN` 等) | 否 | 否 | 否 |
| PRE_SUBMISSION_REJECTION（准入前取消 / 内部错误于 `POST` 之前） | NOT_ATTEMPTED | CALLER_CANCEL 或 INTERNAL_ERROR | NOTHING_TO_CANCEL | CANCELLED 或 RAISED | 否 | 否 | 否 |
| SUBMISSION_UNKNOWN（超时 / 连接失败 / 响应丢失 / `401` / `5xx`） | UNKNOWN | SUBMISSION_UNRESOLVED | UNCERTAIN_SUBMISSION_UNRESOLVED | FAILED(`TIMEOUT` 等) | 是 | 是 | 是 |
| DEADLINE_ABANDON | CONFIRMED | DEADLINE | TERMINAL_FAILED_OBSERVED / TERMINAL_DONE_OBSERVED / UNCERTAIN_* | FAILED(`DEADLINE`) | 是 | 仅 UNCERTAIN_* | 否 |
| CALLER_CANCEL（运行中） | CONFIRMED | CALLER_CANCEL | 任一非 `NOT_APPLICABLE` / `NOTHING_TO_CANCEL` 的值 | CANCELLED | 是 | 仅 UNCERTAIN_* | 否 |
| CALLER_CANCEL（提交在途，取消后拿到 id） | CONFIRMED | CALLER_CANCEL | 同上 | CANCELLED | 是 | 仅 UNCERTAIN_* | 否 |
| CALLER_CANCEL（提交在途，拿不到响应） | UNKNOWN | CALLER_CANCEL | UNCERTAIN_SUBMISSION_UNRESOLVED | CANCELLED | 是 | 是 | 是 |
| CANCEL_RESPONSE_UNKNOWN | CONFIRMED | 任一非 NONE | UNCERTAIN_NO_RESPONSE | FAILED 或 CANCELLED | 是 | 是 | 否 |
| TERMINAL_FAILED_OBSERVED / TERMINAL_DONE_OBSERVED | CONFIRMED | 任一非 NONE | 对应值 | FAILED 或 CANCELLED | 是 | 否 | 否 |
| FATAL_BASEEXCEPTION（`CONFIRMED` 时无清理 I/O） | CONFIRMED | FATAL_BASEEXCEPTION | UNCERTAIN_CLEANUP_INTERRUPTED | CANCELLED | 是 | 是 | 否 |

#### 语义与限制（Design-R1 保留）

* “已发送取消请求”**不等于**“任务记录已终止”，“记录已终止”**也不等于**“执行已停止”。审计、门面文档、HANDOFF 与任何用户可见文字**不得**使用“已停止 / confirmed stopped”措辞，只能写“终态已观察到（TERMINAL_*_OBSERVED）”或“不确定（UNCERTAIN_*）”。
* **晚到写入（late write）不可排除**：除 `NOT_APPLICABLE` / `NOTHING_TO_CANCEL` 之外的每一次放弃 / 取消之后，宿主里该任务的协程仍可能写 Metadata（包括 `FAILED` 已被记录之后）。因此 ① P6 对已放弃的 aggregate **永不使用**其之后写入的 Metadata；② 同号后续重试读到的 `raw` 可能是晚到写入的结果——由第 11.3.4 节“非任务独占”声明覆盖；③ 取消保证（精确 id、请求体不含 `status` / `type`、有界预算、不影响旁观任务）不意味着“宿主上没有遗留执行”，二者不矛盾。
* `TERMINAL_FAILED_OBSERVED` 不区分“因我们取消而 failed”和“恰好自己 failed”。不读 `error` 文本。

### 10.4 语义级取消与“不确定”的暴露

* P4 `preview` 被取消：`CancelledError` 原样传播，**不返回部分 preview**（P4 §20.2）。因此取消结果只能通过**审计快照**观察
  （`AmaneBatchIntegration.audit_snapshot()` 在取消后仍可调用）。
* “cancel before admission”：在任何 worker 被准入之前取消（P4 的 `admission_open()` 保证不再准入）→ 零 `POST`，审计无记录。
* 取消不确定性是**一等输出**：`AmaneHostAuditSnapshot.abandoned_attempts > 0`（L3 未验证）或 `uncertain_cancellations > 0` 或 `creation_unknown > 0` 时，门面文档与 HANDOFF 要求调用方向用户呈现
  “可能仍有未停止的 Amane SCRAPE 任务，且它们仍可能写入 Amane Metadata”。

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
| 3 | 任务侧归属校验（第 11.3.1 节） | `HOST_ATTRIBUTION_FOREIGN` |
| 4 | `GET /metadata/{id}` 返回 200 且 `HostMetadata` 严格 reader 通过（第 8.5 节：`id` / `number` / `raw`） | `HOST_METADATA_MISSING`（404）/ `HOST_SCHEMA_INVALID` |
| 5 | 持久化记录的 `number` **与** `raw["ffcc.fc2-metadata"].number` 经 `normalize_fc2_number` 均为 `RECOGNIZED` 且 `canonical == 请求的 canonical` | `HOST_METADATA_NUMBER_MISMATCH` |
| 6 | **插件原始记录证据**（第 11.3.2 节）：`raw` 中存在**精确键** `ffcc.fc2-metadata`（缺失 ⇒ 内容来源不可证明） | `HOST_ATTRIBUTION_FOREIGN` |
| 7 | 该键的值通过 `PluginRaw` 严格 reader（第 11.3.3 节），并按第 11.4 节映射得到 `NormalizedMetadata` | `HOST_METADATA_CONTRACT` |
| 8 | `NormalizedMetadata.meets_minimum_success()` | `HOST_METADATA_BELOW_MINIMUM` |

* 第 5 步使用 Core 的 `normalize_fc2_number`（不是第二个解析器）：宿主的 Metadata 唯一键大小写不敏感，用户先前以别的写法保存过同一番号时仍应等价；构造出的 `NormalizedMetadata.number` **一律是请求的 canonical**。
* 第 8 步对应 DIFF-P6-02：v0.18.0 可能 `done` 但标量全空（此时 `raw` 内的插件记录 `title` 为空，由第 8 步拒绝）。

### 11.3 字段内容的来源证明（Design-R2 / R2-01 重写；冻结唯一一套方案）

#### 11.3.0 为什么 Design-R1 的证据链不成立

Design-R1 用 `E1`（任务 `field_sources`）、`E2`（持久化 `field_sources`）、`E3`（未被锁定）与 `R0`（`updated_at ≤ finished_at`）判定“字段可归属于插件”。它们**全都是来源标签或时间戳，没有一个读取字段的实际值**，因此无法证明持久化展示列里的内容来自插件。明确反例：

```text
SCRAPE 写入 title=A（field_sources[title] = ffcc.fc2-metadata）
  → 用户 PATCH 把 title 改成 B（PATCH 不改 field_sources；v0.15.0 无字段锁，v0.18.0 在用户解锁之后也不再受保护）
  → SCRAPE 任务被标记 done（updated_at 仍 ≤ finished_at：写入发生在标记 done 之前）
  → P6 GET Metadata → E1/E2/E3/R0 全部成立 → 错误地把 B 归属于插件
```

再叠加一条时间戳条件无法消除这类竞争，且 R0 受墙钟回拨与时间戳精度影响。**本版撤销 E1/E2/E3/R0 作为内容归属证据的地位。**

#### 11.3.1 任务侧证据（必要条件，不充分）

`result.field_sources` 必须满足：非空；`"title" ∈ keys`；`所有 values == "ffcc.fc2-metadata"`。任何其它站点 id 出现，或 `title` 没有归属，说明 route 不独占或任务没有用插件解析出标题 → `HOST_ATTRIBUTION_FOREIGN`（整条目 fail closed）。它只证明“**这个任务的 route 内是插件在贡献**”，**不**证明持久化展示列里现在的内容是什么。

#### 11.3.2 冻结方案：从插件的原始记录 `raw["ffcc.fc2-metadata"]` 派生字段值（方案 A）

**设计期对两个 pinned release 的源码核查结果**（`v0.15.0` = `45dff215…`，`v0.18.0` = `0a8a731d…`；S1 第 0 步用行为测试复核）：

| 事实 | 依据 | 两个版本 |
|---|---|---|
| `raw` 是 `dict[SourceKey, dict]`，值为各来源的 `MediaMetadata.model_dump()`；`SourceKey` 为站点 id（多语言来源才带 `:lang` 后缀，插件不是多语言来源）。因此插件的原始记录在精确键 `ffcc.fc2-metadata` 之下 | `aggregate/engine.py`：`raw = {k: v.model_dump() for k, v in state.fetched.items() if v is not None}` | 相同 |
| `MediaMetadata` 字段：`number, title, actors[{name,gender}], studio, publisher, release(str), runtime, tags, series, plot, poster_urls, thumb_urls, trailer_urls, score, external_id, source_url, directors, extrafanart` | `crawlers/models.py` | 相同（v0.18.0 仅调整 `SearchQuery` 内部字段） |
| `raw` 由 SCRAPE 在 `upsert_metadata(..., raw=result.raw)` 中与展示列**同一次写入** | `handlers/scrape.py` | 相同 |
| `raw` 取自本次任务的抓取：`use_cache=[]` ⇒ `CacheKind.metadata ∉ use_cache` ⇒ 不读 DB 快照，每个来源重新抓取 | `handlers/scrape.py`：`use_metadata_cache = CacheKind.metadata in payload.use_cache` | 相同 |
| 翻译、FacetRule 规范化、Resource 物化、字段清洗**只作用于 `result.metadata` / 展示列**，不改写 `raw` | `handlers/scrape.py` 先取 `result.raw` 后翻译 / 物化；`apply_facet_rules_to_metadata` 作用于 Metadata 列 | 相同 |
| 公开 `PATCH /api/metadata/{id}` **不能**写 `raw`：`PartialMetadata` 的 `ignore_fields` 含 `raw`、`field_sources`（v0.18.0 另含 `locked_fields`），路由只提交模型字段 | `api/models/metadata.py`、`api/routes/metadata.py` | 相同 |
| 公开 merge 端点只**读取** `raw` 去改写展示列与 `field_sources` | `aggregate/merge.py: compute_merge_updates` | 相同 |
| 并发的同号 SCRAPE 会整体替换 `raw`（与展示列一起） | `upsert_metadata` | 相同 |
| `GET /api/metadata/{id}` 的 `MetadataResponse.raw` 返回该字典 | `api/models/metadata.py` | 相同 |

**冻结规则**：

1. `NormalizedMetadata` 的每一个字段值**只**来自 `raw["ffcc.fc2-metadata"]`（经第 11.3.3 节严格 reader 与第 11.4 节确定性映射）。**持久化展示列（`title` / `actors` / `tags` / `poster_urls` …）不参与内容输出**，用户的 PATCH、字段锁、merge 选择、翻译、FacetRule、Resource 物化对输出**没有影响**。
2. 持久化记录只用于三件事：① `number` 等价校验（11.2 第 5 步）；② 展示 `title` 与 `raw` 的 `title` 是否不同的**审计信号** `display_title_diverged`（只进入审计，不影响语义输出，不 fail）；③ 可选的新鲜度提示 `record_freshness`（11.3.4，非门禁）。持久化 `field_sources` / `locked_fields` 不再被读取，也不再作为证据。
3. `raw` 中缺少精确键 `ffcc.fc2-metadata`（例如 route 不含插件、只有外来站点的记录、旧版本遗留）→ `HOST_ATTRIBUTION_FOREIGN`；键存在但结构非法 → `HOST_METADATA_CONTRACT`。**不得**回退去读展示列，也不得改读其它 `raw` 键或带 `:lang` 后缀的键。
4. **放弃的宿主后处理语义（显式声明，不静默）**：LLM 翻译结果、FacetRule 对演员 / 标签的规范化、Resource 物化与海报裁剪后的内部 URL、用户手工编辑、merge 选择。P6 的输出是**插件的原始数据**（已经过 P5 自己的 I22 URL 卫生），而不是 Amane 展示库里“最终呈现”的版本；二者在用户配置了上述功能或手工编辑过时可以不同，这是有意的、写入 L6-06 / L6-18 的取舍。**保留**的语义：插件在 Core 聚合之后给出的全部可映射字段。
5. 不采用“方案 B（持久化展示值与 raw 逐值比较）”的理由：翻译、FacetRule、物化都会合法地改变展示值，要判定“合法转换”必须枚举一个无界的变换集合，无法在公开 API 内验证；比较失败时只能二选一（拒绝或排除），都会让用户的正常配置导致大面积失败。方案 A 的前提（`raw` 不可被公开 PATCH 改写）已由源码核查支持。

#### 11.3.3 `PluginRaw` 严格 reader（`_wire.py`；解析 `raw["ffcc.fc2-metadata"]`）

必需键：`number: str`；`title: str | None`；`actors: list`，元素为 `str` 或 `{"name": str, ...}`（`name` 必须是非空白 `str`；`gender` 等其它键忽略）；`studio / publisher / release / plot: str | None`；`runtime: int | None`（非 `bool`，非负）；`tags: list[str]`；`poster_urls / thumb_urls / extrafanart: list[str]`。其余键（`series`、`trailer_urls`、`score`、`external_id`、`source_url`、`directors` 及未知键）忽略且不保留。任一必需键缺失 / 类型不符 → `HOST_METADATA_CONTRACT`（不猜测、不修复、不部分接受）。列表元素个数与整体结构受第 8.4 节 `MAX_JSON_*` 约束。

#### 11.3.4 保证范围与不可证明的部分（诚实声明；写入 HANDOFF 与 L6-18）

区分两种性质：

```text
插件来源的字段内容   —— 可以支持：输出值完全由 raw["ffcc.fc2-metadata"] 派生，而 raw 不能被公开 PATCH / 字段锁 / merge 改写
当前任务独占产生的内容 —— 不可证明：宿主 Metadata 是按番号唯一的共享记录
```

P6 **声称**：读取那一刻的 `raw["ffcc.fc2-metadata"]` 里的值，经确定性映射得到输出；任务 route 内只有插件（11.3.1）；输出不含任何来自用户展示列的值。P6 **不声称**：① 该 `raw` 一定来自刚完成的这个任务——并发的同号插件 SCRAPE（含遗留孤儿任务）可能在任务完成后整体替换 `raw`，内容仍是插件的一次独立抓取（`use_cache=[]` 的任务总是重新抓取，但他人的任务不一定），证据上无法与本任务区分；② Amane 的 `raw` 与插件 Core 输出逐字节相同——这是 S1 第 0 步用确定性上游夹具核对的事实，核对失败 ⇒ U6-6；③ 防住对 Amane 数据库的直接篡改或 Amane 自身缺陷（公开 API 之外）。

`record_freshness`（审计，非门禁）：`UNMODIFIED_SINCE_TASK` = 记录 `updated_at` 与任务 `finished_at` 都存在、能被严格 ISO-8601 解析、时区属性一致且 `updated_at ≤ finished_at`；`MODIFIED_AFTER_TASK` = 两者可比且 `updated_at > finished_at`；其它（缺失 / 不可解析 / 时区不一致）= `UNKNOWN`。它**只是提示**：墙钟回拨会使“之后的写入”显得更早，时间戳分辨率会掩盖同一刻内的写入，任务内部“写入 → 标 done”的极短间隔内的他人写入也不可分辨；因此它**不得**充当字段来源证明，也不得改变语义输出。

### 11.4 字段映射表（冻结；守卫测试穷举 `PluginRaw` 与 `NormalizedMetadata` 的字段集合）

| `NormalizedMetadata` 字段 | 来源（`raw["ffcc.fc2-metadata"]`） | 规则 |
|---|---|---|
| `number` | 请求的 canonical | 固定；`raw.number` 与持久化 `number` 须等价（11.2 第 5 步） |
| `title` | `title` | 原样；`None` / 空白 → 第 8 步失败 |
| `studio` / `publisher` / `release` / `plot` | 同名 | `str \| None` 原样（`release` 已被 Amane 规范为 `YYYY-MM-DD` 或空；其合法性由 P4 NFO 渲染负责） |
| `runtime` | `runtime` | `int \| None`，负数或 `bool` → `HOST_METADATA_CONTRACT` |
| `actors` | `actors[*]` 的 `name`（或字符串元素本身） | 保持顺序；去除 `gender` |
| `tags` | `tags` | 保持顺序；元素必须是 `str` |
| `poster_urls` / `thumb_urls` / `extrafanart` | 同名 | 仅保留“干净的绝对 http(s) URL”（有 host、无控制字符、无首尾空白；与 P5 I22 规则同义，测试逐样本对账）；**被剔除的数量记入审计 `dropped_url_count`**，不静默 |
| `fanart_urls` | — | 空元组（Amane 无此概念，P5 同） |
| `source_urls` / `external_ids` | — | **恒为空**：P6 不重建来源 provenance，NFO 渲染器也不读取它们（`raw` 里的 `source_url` / `external_id` 不映射） |
| `field_sources` | 派生 | 对每个**非空**的已映射字段 `f`：`{f: ("ffcc.fc2-metadata",)}`（值必须 ⊆ `contributing_source_ids`，P4-C9 诊断校验要求）；内容确实来自插件的原始记录，所以该标签现在有值级证据 |
| （其余 `MediaMetadata` 字段与全部宿主展示列）`series` / `directors` / `trailer_urls` / `score` / `external_id` / `source_url` / `locked_fields` / `field_sources` / `files` / 时间戳 / `id` | — | **不映射**；`metadata_id`、`display_title_diverged`、`record_freshness` 仅进入审计 |

* 容器类型不对（例如 `actors` 不是 list）= schema 违规 → fail closed；元素级的 URL 卫生是确定性过滤（并计数），不是失败。
* 映射是**纯函数**：同样的 `PluginRaw` 总得到同样的 `NormalizedMetadata`；不读取时钟、随机数、环境、持久化展示列。

### 11.5 宿主配置与用户编辑**不**流入结果（诚实声明）

因为输出只来自插件的原始记录（11.3.2 规则 1、4）：用户的 Amane 翻译、FacetRule、Resource 物化、手工编辑、字段锁和 merge 选择**都不会**出现在 P6 的结果里。若用户期望“Amane 里编辑后的标题”进入 NFO，P6-C1 不支持（记入 L6-06）。`display_title_diverged` 审计信号让调用方知道展示列与插件原始标题不同。验收宿主仍使用无翻译、无 FacetRule、禁止物化的配置，使展示列与 `raw` 可逐字段对账（用于独立 oracle 的交叉验证，而不是内容来源）。

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
| `HOST_RESPONSE_TOO_COMPLEX` | 字节数未超限，但 JSON 结构超过 `MAX_JSON_DEPTH` / `MAX_JSON_NODES` / `MAX_JSON_COLLECTION_ITEMS`（第 8.4 节预扫描） | `INVALID_RESPONSE` | `INVALID_RESPONSE` |
| `HOST_SCHEMA_INVALID` | 非 JSON / 严格 reader 违规 / echo 校验失败 / `json.loads` 的 `RecursionError`（纵深防御） | `INVALID_RESPONSE` | `INVALID_RESPONSE` |
| `HOST_TASK_VANISHED` | 观察时 `404`（任务被用户 / 宿主删除） | `INVALID_RESPONSE` | `INVALID_RESPONSE` |
| `HOST_TASK_FAILED` | 观察到终态 `failed`（P6 未发出取消） | `INVALID_RESPONSE` | `ADAPTER_EXCEPTION` |
| `HOST_DEADLINE` | `aggregate_deadline_seconds` 到期（随后有界清理） | `NETWORK_ERROR` | `SOURCE_DEADLINE` |
| `HOST_RESULT_INVALID` | `done` 但 `result` 缺失 / 缺 `metadata_id` / 类型非法 | `INVALID_RESPONSE` | `RESULT_CONTRACT_MISMATCH` |
| `HOST_ATTRIBUTION_FOREIGN` | **内容来源无法证明属于插件**：任务侧 `field_sources` 含其它站点或缺 `title`；`raw` 中缺少精确键 `ffcc.fc2-metadata`（第 11.3 节）。名称沿用，语义是“归属不可证明”，不只是“有外来站点” | `INVALID_RESPONSE` | `RESULT_CONTRACT_MISMATCH` |
| `HOST_METADATA_MISSING` | `GET /metadata/{id}` → `404` | `INVALID_RESPONSE` | `RESULT_CONTRACT_MISMATCH` |
| `HOST_METADATA_NUMBER_MISMATCH` | 第 11.2 节第 5 步 | `INVALID_RESPONSE` | `RESULT_CONTRACT_MISMATCH` |
| `HOST_METADATA_CONTRACT` | `PluginRaw` 结构非法 / 字段类型 / 构造 `NormalizedMetadata` 被拒 | `INVALID_RESPONSE` | `RESULT_CONTRACT_MISMATCH` |
| `HOST_METADATA_BELOW_MINIMUM` | 不满足 minimum success | `INVALID_RESPONSE` | `RESULT_CONTRACT_MISMATCH` |

* 每个 `(SourceStatus, SourceErrorKind)` 配对都在 Core 的 `ALLOWED_ERROR_KINDS` 内（测试穷举验证）。
* **无法证明的细分类一律不猜**：例如无法区分“番号在所有来源都不存在”与“来源故障”（宿主只给 `failed` + 文本），统一为 `HOST_TASK_FAILED`；P6 从不产生
  `NOT_FOUND`。
* **不存在**基于子串 / 正则 / 日志 / 异常消息的分支（AST 守卫：控制流中不得出现对 `error` / `detail` / `str(exc)` / `exc.args` 的比较或匹配）。
* 非 `Exception` 的 `BaseException` 不被映射，保持 P4 致命语义；P6 自身的编程错误（`AmaneBatchContractError`）作为普通 `Exception` 抛出，
  由 P4 隔离为 `METADATA_ENGINE_FAILURE`（`error_type` = 类名），并仍执行有界清理。

---

## 13. 重试所有权（冻结：eligibility 归 P6，执行 / 调度 / 并发归 P4）

### 13.1 三层重试的归属

| 层 | 所有者 | P6-C1 的态度 |
|---|---|---|
| 宿主 `WebClient` 的传输级重试（插件向来源站点发请求时） | Amane / P5 已冻结 | 不触碰；P6 不感知 |
| Core 语义级来源重试 | **disabled**（P5 冻结：`RetryPolicy.no_retry()`） | 不触碰 |
| 条目级重试：**哪些**上一轮 METADATA 阶段失败的条目有资格进入一次新的显式重试轮次（eligibility / subset selection） | **P6 门面**（纯函数，13.3） | 见 13.3 |
| 条目级重试：**真正再次运行**元数据获取、planning、图片、NFO、预检及其并发预算 | **P4 `BatchOrchestrator` + `BatchScheduler`**（唯一执行者） | 见 13.2 |
| `POST /api/tasks` 的重试 | **无人**（永不重试） | 第 9.2 节 |
| 观察 `GET` 的有界重复 | engine（只重复幂等观察，不重复工作） | 第 9.3 节 |
| Amane `POST /tasks/batch` 的 `retry` / `delete` | **永不使用** | 第 7.2 节 |

冻结（Design-R1 / R1-02 重写）：**一次 P6 aggregate 最多发送一次 `POST /api/tasks`；`POST` 永不自动重试。** 旧稿“一次尝试 = 恰好一个新任务”已撤销：尝试次数（0 或 1 次 `POST`）与宿主实际创建的任务数（0、1 或未知）是两件事，由 `SubmissionState`（第 9.2 节）区分。`CREATION_UNKNOWN` 永不被折算为 0 或 1，也不得成为自动重新提交的理由。

### 13.2 设计期发现 F-1：P4 `preview_retry` 在“禁止 execute”的 Phase 6 中不可用

`BatchOrchestrator.preview_retry(previous, *, scope=None)` 的 `previous` 必须是一个**完整的 `BatchExecutionResult`**（`retry.py` 步骤 2
“exact complete previous result”，其 `RetryMaterial` / `retry_kind` / `result_id` 注册全部来自 `execute`）。而 Phase 6 的安全不变量是**绝不调用
`execute`**（第 19 节）。用 `execute(preview, selection=frozenset())` 绕过会违反该不变量的字面（并且会消费 preview），伪造 `BatchExecutionResult`
则是重建 CLOSED 模型——两者都被禁止。

**冻结裁决（ownership 拆成两个、互不重叠：P6 拥有 retry eligibility / failed-subset selection；P4 拥有 retry execution / scheduling / concurrency）**：失败子集重试 = 对失败条目的**原始 `DiscoveredMediaItem`** 再调用一次同一个
`BatchOrchestrator.preview(subset)`。

* P6 **只做子集选择**（一个纯函数，输入是上一轮已有的 `ItemPreview`），不运行任何 scheduler、不重试、不循环。
* 真正重新执行元数据获取、planning、图片、NFO、预检的仍然是 P4 `preview`；并发预算仍然是 P4 `BatchScheduler`。
* 不修改 P4。不引入第二套 scheduler。不使用 `preview_retry` / `merge_retry` / `RetryMaterial`（它们只对 `execute` 之后的结果有意义；Phase 7 引入 `execute` 后沿用 P4 原有机制）。

### 13.3 `AmaneBatchIntegration.retry_failed(previous) -> AmaneBatchPreview`

1. 调用顺序见第 9.5 节：`previous` 校验 → 子集选择 → worker preflight → `await orchestrator.preview(subset)`。P4 的 busy claim 只发生在 `preview` 入口，其拒绝原样传播；P6 不新增锁，也**不**声称“busy 优先于本节的参数 / 子集错误”（第 9.5 节）。
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
* 宿主任务账本期望（real-host 证据 E6-13）：按第 9.2 节第 6 条的不等式对账——无 `CREATION_UNKNOWN` 的番号，成功番号在整个多轮过程中恰好 1 个 SCRAPE 任务，失败后恢复的番号恰好 2 个；
  永不为成功条目新增任务（mutation M6-07）；含 `CREATION_UNKNOWN` 的番号只断言上下界。
* 对上一轮属于 `CREATION_UNKNOWN` 的条目，`retry_failed` 不会自动放行或阻止：它是调用方显式发起的新 aggregate，新 `POST` 可能与遗留的未知任务并存；调用方可用 `audit_snapshot().creation_unknown` 知情（第 9.2 节第 5 条）。

### 13.4 跨轮冲突（Design-R1 / R1-06 新增；撤销旧的“成功条目与重试子集不可能冲突”断言）

旧稿断言“重试子集与成功条目之间不可能存在冲突”。该断言被 CLOSED 测试证伪：P4 Phase B 以 `(device, inode)` 与目标目录检测冲突，**不同番号可以对应同一个 hardlink 源文件**（`tests/phase4_acceptance/test_p4_acceptance_safety.py::test_s10_in_batch_conflicts_block_every_member_and_select_no_winner`，S-10 / SI-10：两个不同番号共享一个 hardlink 源文件，在 Phase B 以 `duplicate_source_in_batch` 被发现）。单独重试失败子集时，P4 的单轮 `preview` 只看见子集，**看不见**前一轮已经 READY 的条目；前轮的 READY 与新轮的 READY 因此可能形成跨轮冲突，而没有任何一轮的 `BatchPreview` 会报告它。冻结：

* 每个 `BatchPreview` 的 READY / 冲突结论**只对其本轮输入集合有效**。P6 **不**提供跨轮的全局 READY / 冲突安全保证，也不新增 filesystem executor 或跨轮冲突检测器。
* 多轮 `AmaneBatchPreview` **不是**一个全局可执行的 preview；汇总必须区分逐轮计数与可被证明的全局状态（第 20.4 节：`ready_round_local`、`cross_round_verified`、逐轮计数），**不得**把各轮 READY 相加后当作全局安全 READY。
* 仅当 `rounds == 1` 时，该唯一一轮的结论覆盖全部输入条目，`cross_round_verified = True`；`rounds > 1` 时恒为 `False`，包括主轮里未被重试的 READY 条目（它们可能与重试轮的 READY 条目冲突）。
* Phase 7 若要跨轮执行，**必须**对合并范围重新验证源文件身份（device / inode）与目标冲突；这是 Phase 7 必须理解的已知局限（L6-16、第 19.3 节）。
* 证据：E6-19 用该 CLOSED S-10 hardlink 反例构造“前轮 READY + 重试轮 READY 实为同一源文件”，断言汇总**不**声称 `cross_round_verified`；孪生：单轮同样输入时 P4 报告冲突。

---

## 14. 并发合同（冻结）

1. **跨条目并发的唯一所有者是 P4 `BatchScheduler`**（`OrchestrationConfig.metadata.max_in_flight_items = M`，缺省 4，范围 1..64）。
   P6 没有信号量 / 线程池 / worker 池 / `asyncio.gather` / `TaskGroup` / `create_task`（清理 task 例外，且有界、被 await，第 10.2 节）。
2. **每个 aggregate 最多发送一次 `POST /api/tasks`，且同一时刻最多等待一个宿主 SCRAPE 任务。** 一个 aggregate 不 fan-out 多个宿主任务，也不会在任何失败 / `CREATION_UNKNOWN` 之后自动再提交（第 9.2 节）。
3. **三个独立集合（Design-R2 / R2-04；不得混为一谈）**：

   ```text
   A  = P6 当前活跃的 aggregate 尝试（引擎 in_flight：入口 +1，finally -1；含正在 ABANDONING 清理的 aggregate）
   K  = P6 当前正在等待的、id 已知的宿主任务（A 中已拿到 CREATION_CONFIRMED id 且尚未结束观察 / 清理的那些）
   H  = 与本批番号关联的全部宿主任务，包括已放弃、CREATION_UNKNOWN 遗留的孤儿任务
   ```

   **冻结的不等式**：`|A| ≤ M`；`|K| ≤ |A|`。**不要求、也不保证** `|H| ≤ M`：遗留的孤儿任务仍可能在宿主上 `queued` / `running`（第 4 条）。
4. **机检 oracle（四个相互独立的来源）：**
   * **O1 引擎计数**：`peak_in_flight`（审计快照），并用各记录的 `begin_event` / `end_event` 重新计算最大重叠区间，二者一致且 `≤ M`；
   * **O2 独立 POST 账本**：故障代理（或传输层 ledger）按到达顺序记录每个 `POST /api/tasks` 的请求体，与 P6 自己的审计**无关**。断言每个 `(番号, generation)` 至多一个 `POST`，总数 `== audit.submitted`；
   * **O3 K 观察器**：测试工具自己的 client 以 ≤ 20 ms 间隔采样（工具专用的 `GET /api/tasks`，不是 P6 的表面）。**只**对账本里已记录 `202` 的 id 统计：某 id 在“P6 尚未对其结束等待”期间处于 `queued` / `running` 的个数 `≤ M`；“P6 结束等待”的时刻由代理账本的顺序定义（对该 id 的最后一次 `GET` 返回终态、或对该 id 的取消 `POST` 已发出并得到处理、或 aggregate 返回）。**未知 id（`CREATION_UNKNOWN`）不被假装归类**，既不计入 `K`，也不用于任何 `|H|` 断言；
   * **O4 纯净对照**：只在**没有** `CREATION_UNKNOWN` / 放弃 / 孤儿的场景里，额外断言宿主上本批 `queued + running` 的任务数 `≤ M`（此时 `H == K`），并明确这只是该场景的实证，**不推广**为所有异常路径的全局保证。
5. **强制孤儿用例 `ORPHAN-M1`（M = 1）**：故障代理使第 1 个 `POST` 在宿主创建任务之后丢弃响应；该宿主任务被 `HOLD` 保持 `running`（孤儿）；P6 记 `CREATION_UNKNOWN`、该 aggregate 返回 `FAILED`；随后下一个 aggregate 创建并完成另一个任务。**未变异实现必须 PASS**：`|A| ≤ 1`、`|K| ≤ 1`、O2 账本里每个 aggregate 恰好一个 `POST`、`|H| == 2 > M` **被允许**。**以下实现错误必须 FAIL**：绕过 P4 scheduler 使 `|A| > M`（O1）；单个 aggregate 在 `UNKNOWN` 之后自动再 `POST`（O2）；隐藏 scheduler / 无界 fan-out 使 `|A| > M` 或账本 `POST` 数超过 aggregate 数（O1 / O2）；孤儿被错误归入 `K`（O3 的 `HOLD` 孤儿 id 不在账本 `202` 里，不得被计数）。
6. **三个并发数必须区分**：① P4 metadata 并发 `M = OrchestrationConfig.metadata.max_in_flight_items`（缺省 4；P4 是唯一 owner，不变）；② Amane 宿主**配置的** worker 并发——`WorkerConfig.concurrency` 缺省是 **10**（两个版本相同，`config/manager.py`；`scheduler/worker.py` 构造函数里的 `concurrency=3` 只是类默认，宿主实际由配置传入），验收宿主若明确配置了其它数值，以**实际配置**为准；③ 孤儿任务占用的并发。当 `M` 大于宿主实际并发，或孤儿任务占满并发时，多出的任务在宿主排队，其排队时间计入 `aggregate_deadline_seconds`（L6-07）。被放弃 / 取消的任务（`abandoned_attempts`）**不计入** `A` / `K`，但其执行协程可能仍在宿主上运行（第 10.3 节，L3 永远 UNVERIFIED）。
7. 门面不创建任何 event loop / 线程；全部在调用方的 loop 里运行。

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

Phase 7 将通过 P4 原有路径对某个 `AmaneBatchRound.preview` 调用 `execute`；每一轮的 `BatchPreview` 都是独立、可按 P4 合同执行的对象；P6 **不**提供多轮合并语义，也**不**提供跨轮的 READY / 冲突安全保证（第 13.4 节：不同番号可共享同一个 hardlink 源文件，单轮 preview 看不见别的轮次）。**Phase 7 若需跨轮执行，必须对合并范围重新验证源文件身份与目标冲突**，这是 Phase 7 必须理解的已知局限（L6-16）。
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
    "AmaneHostAuditSnapshot", "HostAttemptRecord", "HostFailureKind", "CancelOutcome", "SubmissionState", "HostPreflightReason", "RetryRefusal",
    "AmaneRoundCounts", "CleanupTrigger", "AggregateTerminal", "RecordFreshness",
    # 常量
    "PLUGIN_SOURCE_ID", "MAX_RESPONSE_BYTES", "MAX_JSON_DEPTH", "MAX_JSON_NODES", "MAX_JSON_COLLECTION_ITEMS",
    "MAX_AUDIT_RECORDS", "MAX_RETRY_ROUNDS",
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
`RetryRefusal = {FOREIGN_PREVIEW, NO_RETRYABLE_ITEMS, ROUND_LIMIT}`。

**异常图封闭（Design-R1 / R1-03；Design-R2 / R2-02 重述）**：保护面、禁入内容、所有权状态例外与构造规则 C1–C7 全部以第 8.3.1 节为准，适用于**整个** `src/fc2_amane_batch/**`。本包抛出的每个异常的 `__cause__` / `__context__` 只能是 `None` 或另一个 `AmaneBatchError` 子类；绝不链到 httpx 异常或 `UnicodeError`；`raise … from None` **不被视为**满足要求（它不清除 `__context__`）。不得声称“任何对象都不可能引用认证信息”：调用方持有的 client / config / credential 本身含认证状态（第 8.3.1 节第 3 点）。

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
class AmaneRoundCounts:             # 每轮一行；直接取自该轮 BatchPreview.summary 的计数（该轮自己的口径）
    generation: int
    total: int; ready: int; blocked: int; unprepared: int

@dataclass(frozen=True, slots=True)
class AmaneBatchSummary:            # 确定性、纯语义；由最新视图的 ItemPreview 派生，从不存储
    total: int
    ready_round_local: int          # 最新视图中，在各自所属那一轮内为 READY 的条目数；**不是**全局可执行 READY（见 cross_round_verified）
    blocked: int; unprepared: int; warned: int
    retried: int                    # 出现在任一 generation ≥ 1 轮次的不同原始条目数
    rounds: int
    cross_round_verified: bool      # == (rounds == 1)；rounds > 1 时 P6 未做、也不提供跨轮冲突验证（第 13.4 节）
    per_round: tuple[AmaneRoundCounts, ...]                              # 长度 == rounds，按 generation 升序
    stage_counts: tuple[tuple[OrchestrationStage, int], ...]            # 与 P4 PreviewSummary 同口径：Σ == blocked + unprepared
    metadata_failures: tuple[tuple[IssueReason, int], ...]               # 仅 METADATA 阶段原因
    retryable: int                  # == len(retryable_indices)
```

不变量：`total == ready_round_local + blocked + unprepared`；`warned ≤ total`；`Σ stage_counts == blocked + unprepared`；`retryable ≤ unprepared`；`rounds == len(rounds) == len(per_round)`；
`cross_round_verified == (rounds == 1)`；`per_round[k]` 与 `rounds[k].preview.summary` 的对应计数逐项相等（逐轮口径，**不得相加后冒充全局**）；
当 `rounds == 1` 时，`total / ready_round_local / blocked / unprepared / warned / stage_counts` 与 `rounds[0].preview.summary` **逐项相等**（交叉校验，E6-19）。
元组均按枚举声明顺序排序，保证确定性。`ready_round_local` 的命名与文档必须显式表明它是“轮内”口径；任何把它描述为“全局可执行 / 无冲突”的文字都违反本合同（M6-22）。

### 20.5 审计模型（运维，非确定性，与语义分离）

```python
class HostFailureKind(Enum):  # 第 12.1 节的 19 个 HOST_* 成员；value = 去掉 HOST_ 前缀的小写（HOST_TASK_FAILED.value == "task_failed"）
class CancelOutcome(Enum):    # 第 10.3 节的 9 个成员（含 NOT_APPLICABLE / NOTHING_TO_CANCEL；无任何会断言“执行已停止”的成员）
class SubmissionState(Enum):  # 第 9.2 节的 4 个成员：SUBMISSION_NOT_ATTEMPTED / SUBMISSION_ATTEMPTED / CREATION_CONFIRMED / CREATION_UNKNOWN
class CleanupTrigger(Enum):   # 第 10.3 节：NONE / CALLER_CANCEL / DEADLINE / OBSERVATION_FAILURE / ECHO_MISMATCH / SUBMISSION_UNRESOLVED / INTERNAL_ERROR / FATAL_BASEEXCEPTION
class AggregateTerminal(Enum):# SUCCESS / FAILED / RAISED / CANCELLED
class RecordFreshness(Enum):  # 第 11.3.4 节：UNMODIFIED_SINCE_TASK / MODIFIED_AFTER_TASK / UNKNOWN（仅提示，非门禁）

@dataclass(frozen=True, slots=True)
class HostAttemptRecord:
    seq: int                          # 1.. 本 engine 内的逻辑序号（提交先后），不是时间
    number: str
    host_task_id: int | None
    outcome: HostFailureKind | None   # R == FAILED 时必为某个失败种类，其余为 None
    terminal_status: str | None       # 观察到的结构化终态 "done" | "failed" | None
    submission: SubmissionState       # S；终态记录不得为 SUBMISSION_ATTEMPTED；CREATION_UNKNOWN 不折算为 0 或 1
    cleanup_trigger: CleanupTrigger   # T；NONE = 没有触发清理 / 放弃路径
    cancel: CancelOutcome             # C；NOT_APPLICABLE ⇔ cleanup_trigger == NONE（与任务是否已创建无关）
    terminal: AggregateTerminal       # R
    polls: int; requests: int; dropped_url_count: int
    display_title_diverged: bool      # 展示列 title 与 raw 插件记录的 title 不同（第 11.3.2 节；仅审计，不影响语义输出）
    record_freshness: RecordFreshness # 第 11.3.4 节；仅提示
    metadata_id: int | None
    elapsed_ms: float
    begin_event: int; end_event: int  # 逻辑事件计数（aggregate 开始 / 结束），用于机检并发区间，不是时间
    # __post_init__：强制第 10.3 节 LC1–LC8；任一违反 → AmaneBatchContractError（固定文本）

@dataclass(frozen=True, slots=True)
class AmaneHostAuditSnapshot:
    records: tuple[HostAttemptRecord, ...]     # 按 seq 升序；至多 MAX_AUDIT_RECORDS
    submitted: int                             # == #{S ≠ NOT_ATTEMPTED}；是“发出 POST 的次数”，不是“创建的任务数”
    in_flight: int; peak_in_flight: int        # 即第 14 节的 |A| 与 peak |A|；不是宿主上的任务数
    failure_counts: tuple[tuple[HostFailureKind, int], ...]
    creation_confirmed: int; creation_unknown: int
    abandoned_attempts: int                    # == #{T ≠ NONE ∧ S ≠ NOT_ATTEMPTED}；每一个的执行层（L3）都是 UNVERIFIED；正常成功 / 未取消的失败不计入
    uncertain_cancellations: int               # == #{C ∈ UNCERTAIN_*}
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
2. **内容来源的值级证明**：每个成功条目的输出必须能由 `raw["ffcc.fc2-metadata"]`（第 11.3.2 节）确定性重算；harness 用自己的 client 回读同一条记录，**独立**复算一遍 `NormalizedMetadata`（独立 oracle，不复用生产映射代码），二者必须逐字段一致；并与确定性上游夹具经 Core 规范化后的期望值核对（验收宿主无翻译 / 无 FacetRule / 禁止物化时，展示列与 `raw` 也应一致，`display_title_diverged == False`）。
3. **上游请求账本**：Core 三个来源适配器的 URL 形状（`/fc2db/work/<digits>/`、`/javdb/search?q=FC2-PPV-<digits>`、`/av123/en/v/fc2-ppv-<digits>`）只会由“配置了这些 base_url 的 plugin”产生；
   账本逐号记录被请求的来源页，成功条目的号必须出现。
4. **反事实控制**：同一宿主上卸载 / 禁用 plugin（或把 route 清空）→ 同一批号全部在 METADATA 阶段失败（M6-01 / M6-02）。
   **值级 provenance 反事实（Design-R2 / R2-01；每一项都必须非空地使对应门变红，并带绿色孪生）：**
   ① *v0.15.0 手工覆盖*：SCRAPE upsert A → harness 手工 `PATCH` title=B → 任务 `done` → P6 `GET`（`PATCH` 发生在 P6 读取之前；真实宿主上用故障代理在 metadata `GET` 之前挂起请求来实现，宿主可观察状态与“`PATCH` 发生在任务内部写入与标 done 之间”相同；宿主替身另作精确交错的补充用例）；断言输出 title == A，绝不是 B，`display_title_diverged == True`；
   ② *v0.18.0 手工覆盖并解锁*：SCRAPE upsert A → `PATCH` B（title 被锁定）→ harness 经公开锁接口**解锁** → 任务 `done` → P6 `GET`；此时展示列 B 的持久化 `field_sources` 仍指向插件、未被锁定、`updated_at ≤ finished_at`，Design-R1 的 E1/E2/E3/R0 会全部通过——断言输出仍是 A；
   ③ *同号 plugin SCRAPE 竞争覆盖*：另一个同号 SCRAPE（上游夹具内容已切换）在任务完成后整体替换 `raw`；断言输出与**当时读取到的** `raw` 一致（插件来源的另一次抓取），不与过期展示列混合，`record_freshness` 为 `MODIFIED_AFTER_TASK`（时间戳可比时）或 `UNKNOWN`，且 HANDOFF 如实声明“非任务独占”；
   ④ *外来 persisted field_sources*：代理改写展示记录的 `field_sources` / `locked_fields` 注入外来站点 → 输出不变（这些字段不被读取）；孪生：把读取它们作证据的变体（M6-17）判红；
   ⑤ *plugin raw 缺失或非法*：`raw` 无 `ffcc.fc2-metadata` 键（或只有外来站点键 / 带 `:lang` 的键）→ `HOST_ATTRIBUTION_FOREIGN`；键存在但结构非法（`title` 非字符串、`actors` 非列表等）→ `HOST_METADATA_CONTRACT`；不得回退读展示列（M6-18）；
   ⑥ *raw 与 persisted title 不一致*：展示 title ≠ raw title → 输出取 raw，`display_title_diverged == True`，条目不失败；
   ⑦ *干净 plugin raw 正向孪生*：展示列与 `raw` 一致、无竞争 → 输出与独立 oracle 一致，`display_title_diverged == False`，`record_freshness == UNMODIFIED_SINCE_TASK`。
   **关键验收**：任何场景都不得把仅由用户手工覆盖产生的值作为插件字段内容输出。某个版本上无法通过公开 API 构造的格子，用代理改写代替并在矩阵 JSON 标明构造方式；无法构造的如实标 `NOT_RUN`，不得写 PASS。
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
（删除 `result.metadata_id`、改 `metadata.number`、清空 / 删除 / 改写 `raw` 中的插件记录或其键、向任务侧 `field_sources` 注入外来站点、改写展示列的 `field_sources` / `locked_fields` / `updated_at`）、并**同时充当独立 POST 账本**（按到达顺序记录每个 `POST /api/tasks` 的请求体与宿主返回的 `202` id，供第 14 节 O2 / O3 使用）、**挂起**第 n 个匹配请求直到 harness 放行（用于“任务完成之后、P6 读取 Metadata 之前”的手工更新）、以及把响应体替换为**字节数未超限但结构超限**的 JSON（深层嵌套 / 海量节点 / 超大集合）。用途：传输超时、取消不确定性（丢弃取消响应）、DONE 缺 `metadata_id`、
号不匹配、低于最低成功、外来归属。故障脚本进入证据 JSON。

### 22.6 旁观任务（bystander）

在取消场景里，测试工具先用**自己的** client 在同一宿主上直接创建一个与批量无关的 SCRAPE 任务（保持 QUEUED / RUNNING）。取消完成后断言它**未被取消**；
这是 M6-08 的非空性依据。

---

## 23. Evidence Gate（冻结；根据 Governance v2 第 17 节，较大的 C 证据必须更完整）

| ID | 证据 | 载体 |
|---|---|---|
| E6-01 | 范围门：`git diff 4189b95…..HEAD` ∪ 工作树 ⊆ P6 allow-list；闭合范围零 diff；**HG-1 精确约束**（第 5.4 节：文件集合恰为两个；唯一移交的两处工作树断言；测试函数名集合 = Base 集合减 1；四个历史常量 AST 逐字相同；无新增 skip / xfail；diff 行数 ≤ 60）；**P6 自有的 C0 控制字符检查覆盖 `4189b95…..HEAD` ∪ 工作树内全部文本文件**（承接被重绑的历史检查） | `tests/amane_batch/test_amane_batch_scope_gate.py` |
| E6-02 | Contract → implementation → test 映射表（逐条合同条款 / 不变量） | HANDOFF |
| E6-03 | 架构守卫（AST）：import 允许 / 禁止清单；禁用标识符（19.2）；endpoint 常量集合 **等于** 表 H1；无 logging / 文件 API；控制流不比较 `error` / `detail` / `str(exc)` / `exc.args`；**`host_client.py` / `facade.py` 的 `except` 处理体内不得出现带参数的 `raise`（第 8.3 节）**；JSON 预扫描无递归（无自调用、无递归下降）；门面不直接调用 `engine.aggregate` / 不含 `gather` / `TaskGroup` / `create_task`（第 9.5 节） | `test_amane_batch_architecture.py` |
| E6-04 | 配置 / 凭据：校验矩阵（base_url 全部非法形态、数值边界、凭据字符集）；redaction；不可 pickle / copy | `test_amane_batch_config.py` |
| E6-05 | client 协议（`httpx.MockTransport`）：**请求账本逐键断言**（方法 / 路径 / 体键集 / 头集）；无 cookie 回传、无重定向跟随、无环境代理 / `.netrc`、响应上限、状态码映射表穷举 | `test_amane_batch_client.py` |
| E6-06 | 严格 reader：必需键缺失 / 类型错误 / 额外键容忍（`HostMetadata` 仅 `id` / `number` / `raw`，其余展示列与 `locked_fields` / `field_sources` 被忽略且不保留）；`PluginRaw` reader（第 11.3.3 节）；**有界 JSON（R1-07 / R2-03）**：深度 / 节点 / 集合项各自“恰在上限（绿）/ 超一（红）”孪生，字节数均远低于 8 MiB；输入矩阵覆盖长字符串、长空白、转义引号、连续反斜杠、字符串内部的 `{ } [ ]`、对象键、空对象、空数组、未知嵌套字段；预扫描计数与独立递归参考计数器在小输入上逐项对账；超限在 `json.loads` **之前**拒绝（对 `json.loads` 的 spy 断言未被调用）；深层嵌套不触发 `RecursionError`；超限映射 `HOST_RESPONSE_TOO_COMPLEX` 且不保留原始响应；**成本**：正常通过时扫描的操作计数随 `B` 线性（`B` 与 `2B` 的比值有界，用操作计数而非墙钟），辅助栈深度 ≤ `MAX_JSON_DEPTH`，不物化子串；两个版本的真实合法响应（含 `raw`）实测值低于上限的 1/4 | `test_amane_batch_wire.py` |
| E6-07 | 映射：字段表穷举（守卫 `PluginRaw` / `NormalizedMetadata` 字段集合）、URL 卫生与 P5 I22 逐样本对账、最低成功、号等价、每个 `HostFailureKind` → 合法 Core 配对（`ALLOWED_ERROR_KINDS`）、产出的 `AggregationResult` 通过 Core 校验且能被 P4-C9 诊断投影接受；**值级 provenance（R2-01）**：输出完全由 `raw["ffcc.fc2-metadata"]` 派生，展示列的任何改动（title / actors / tags / URL / `field_sources` / `locked_fields` / `updated_at`）都不改变输出；第 22.3 节 ①–⑦ 七类反事实的单测层红 / 绿孪生；`source_urls` / `external_ids` 恒为空；`display_title_diverged` / `record_freshness` 只进审计 | `test_amane_batch_mapping.py` |
| E6-08 | 生命周期：状态机、deadline（含“至少一次观察”）、观察失败容忍、**提交永不重试**；**`SubmissionState`（R1-02）**：非规范号 ⇒ 无记录（零 `POST`）；准入前取消 ⇒ `NOT_ATTEMPTED`；`202` ⇒ `CREATION_CONFIRMED`；超时 / 连接中断 / 响应丢失 / `401` / `403` / `5xx` / schema 非法 ⇒ `CREATION_UNKNOWN`（不折算为 0 或 1）；任一 `CREATION_UNKNOWN` 之后请求账本里零次再提交；终态记录永不停在 `SUBMISSION_ATTEMPTED`；**组合合同（R2-05）**：对 `S × T × C × R` 的笛卡尔积做穷举——第 10.3 节 LC1–LC8 定义的合法组合全部被接受，所有非法组合（如 `NORMAL_SUCCESS` 却 `C != NOT_APPLICABLE`、`S=CONFIRMED` 且 `T=NONE` 却 `C=TERMINAL_*`、`S=UNKNOWN` 却 `C=NOT_APPLICABLE`）都被 `HostAttemptRecord.__post_init__` 拒绝；命名场景表的计数逐项对账（正常成功 / 未取消失败不计入 `abandoned_attempts`） | `test_amane_batch_lifecycle.py` |
| E6-09 | 取消：精确 id、请求体不含 `status` / `type`、清理预算、`CancelOutcome` 全部 9 种（**无 `CONFIRMED_STOPPED`**；任何输出不含“已停止”断言）、shield、无分离 task、二次取消、致命 `BaseException` 无 I/O；**取消真实性（R1-04）**：① *claimed-but-not-registered window*（宿主替身的 v0.15.0 / v0.18.0 两种变体）；② *FAILED recorded while handler may run* 及 *late Metadata write*：aggregate 结果仍为 FAILED、永不使用晚到数据、`abandoned_attempts` 计数；③ *normal running cancellation* 正向孪生（协程确实停止，P6 仍只报 `TERMINAL_FAILED_OBSERVED`）；④ *race-DONE* ⇒ `TERMINAL_DONE_OBSERVED`；**组合（R2-05）**：命名场景表中每个取消 / 放弃场景的 `S/T/C/R` 与 `abandoned` / `uncertain` / `creation_unknown` 计数精确；`C == NOT_APPLICABLE` 当且仅当 `T == NONE` | `test_amane_batch_cancellation.py` |
| E6-10 | 并发（R2-04）：O1 `peak_in_flight` 与记录区间重算一致且 `≤ M`；O2 独立 POST 账本——每个 `(番号, generation)` 至多一个 `POST` 且总数 `== audit.submitted`；O3 K 观察器——只统计账本里已记录 `202` 的 id，`≤ M`，未知 id 不被归类；O4 纯净对照（无孪生孤儿时 `queued + running ≤ M`，不推广）；**强制 `ORPHAN-M1`**（M=1，第 1 个 `POST` 响应丢失、孤儿保持 `running`、下一个 aggregate 另建任务）：未变异实现 PASS（`|A| ≤ 1`、每 aggregate 一个 `POST`、`|H| == 2` 被允许）；绕过 P4 / 自动再 `POST` / 隐藏 scheduler 的变体 FAIL；完成顺序反转 / 慢 / 失败 / 取消下不变；**门面并发（R1-05）**：一个 `preview` 运行时，① 第二个合法调用被 P4 公开接口拒绝且**零次 `POST /api/tasks`**（可有一次只读 preflight，不声称零网络）；② 非法参数 ⇒ `AmaneBatchInputError`；③ 非法参数 + P4 busy 同时发生时与冻结顺序一致；④ 绕过 P4 的变体必须变红（M6-20） | `test_amane_batch_concurrency.py` |
| E6-11 | **真实宿主纵向门**：≥ 10 个 FC2，HOST-A-SRC 与 HOST-B-SRC 各一次，完整链（scan → … → BatchPreview → summary） | `tools/run_amane_batch_gate.py` → `P6_C1_HOST_MATRIX.json` |
| E6-12 | 真实宿主失败矩阵：来源降级仍可用；整体失败；混合；宿主任务 FAILED；宿主 API 传输失败；图片部分失败；坏 / 缺 metadata（经代理改写）；精确的条目隔离 | 同上 |
| E6-13 | 真实宿主重试：仅失败子集、成功条目不重跑、retry → success、宿主任务账本按第 9.2 节第 6 条不等式对账（无 `CREATION_UNKNOWN` 的番号：成功恰好 1 个、失败后恢复恰好 2 个；含 `CREATION_UNKNOWN` 的番号只断言上下界） | 同上 |
| E6-14 | 真实宿主取消：准入前、运行中、终态已观察（`TERMINAL_*_OBSERVED`）、不确定（代理丢弃取消响应）、旁观任务未受影响；*claimed-but-not-registered window* 与晚到写入在真实宿主上尽力复现（HOLD 上游 + 立即取消），无法稳定复现则以替身证据为准并在 evidence gaps 中如实标注，**不得**因此写“已停止” | 同上 |
| E6-15 | 真实宿主确定性：完成顺序反转 → 语义投影 / NFO 字节 / artifact requests / issue 顺序 / summary 相等；上游内容变化 → 投影变化（非空性） | 同上 |
| E6-16 | route ownership 与**值级**内容来源的机械证明（22.3，含 ①–⑦ 七类反事实） | 同上 |
| E6-17 | 安全 canary（R2-02，**整个包**）：保护面 P1–P3 与禁入内容 `F`（第 8.3.1 节）——对第 8.3.1 节第 5 点“强制失败矩阵”中**每一条适用路径**（`AmaneHostCredential` / `AmaneHostConfig` 的非法 ASCII、非 ASCII、空白、超长；`AmaneHostClient` 全部 5 个公共方法的 `401` / `403` / `5xx` / 超时 / 连接失败 / 畸形响应 / 结构超限；`AmaneHostPreflightError` 全部 4 个 reason；`AmaneAggregationEngine` 内部契约错误；`AmaneBatchIntegration` 的非法输入 / retry 拒绝 / 门面转换）递归检查 `__cause__` / `__context__`（visited 集合、深度 ≤ 8）、`args`、`__notes__`、本包栈帧 `f_locals`（浅层）、`str` / `repr` / traceback 文本、审计 / 汇总 / preview，断言 `F` 不出现；所有权对象（credential / config / client / engine / facade）作为不透明节点不遍历，且测试明确区分“新引入的泄漏”与“对象自身持有认证状态”。**红绿孪生**：凭据路径 `try: token.encode(...) except UnicodeEncodeError: raise … from None` 变体判红、纯谓词 + 块外抛出为绿；校验失败时 `token` 形参仍留在本包帧局部为红、已重新绑定 `None` 为绿；`_transport` 内 `raise … from None` 为红；外层 `_call` 帧局部仍持有 `Response` / `Request` 为红；响应的 `files` 字段含 canary 路径时，该路径不出现在任何输出；cookie 不回传；跨源重定向不带凭据；`.netrc` / 环境代理被忽略；TLS 不可降级（自签证书 → `HOST_CONNECTION`，上游零请求）；结构超限响应经真实宿主代理映射为封闭失败且不泄漏响应体 | `test_amane_batch_security.py` + 真实宿主 canary |
| E6-18 | 不执行：S6-1..S6-5 三层机检（静态 / tripwire / 文件系统树摘要） | 架构测试 + 宿主场景 |
| E6-19 | `AmaneBatchSummary` 精确计数，并与 P4 `PreviewSummary` 逐项交叉校验；**跨轮（R1-06）**：`ready_round_local` / `per_round` / `cross_round_verified` 精确；用 CLOSED S-10 的 hardlink 反例构造“前轮 READY + 重试轮 READY 实为同一源文件”，汇总在 `rounds > 1` 时 `cross_round_verified == False`，不虚增全局 READY，单轮孪生由 P4 报告冲突 | `test_amane_batch_summary.py` + 宿主场景 |
| E6-20 | 语义 / 运维分离：语义投影中不含任何运维字段 | `test_amane_batch_determinism.py` |
| E6-21 | mutation / non-vacuity：第 24 节全部 24 项 M6-xx 必须使对应门**变红**，且未变异孪生保持绿 | `test_amane_batch_mutation_nonvacuity.py` |
| E6-22 | 全量回归：既有全部套件（adapter / compat（HG-1 之后）/ contract / unit / phase4_acceptance …）通过，**与 Frozen Base 的基线通过数对账**（S1 第一件事是在 `4189b95…` 上记录各目录基线） | HANDOFF |
| E6-23 | 构件同一性：sidecar wheel sha256 == P5 台账 pin；plugin zip 由 CLOSED 构建器产出且 P5 构件零变化 | 宿主矩阵 JSON |
| E6-24 | live-network smoke 记录（第 25 节） | `P6_C1_LIVE_SMOKE.json` |
| E6-25 | 解释器覆盖：P6 包与其测试在 Python 3.12 与 3.14 上运行（受影响测试）；只覆盖一个则作为 evidence gap 明示 | HANDOFF |
| E6-26 | 证据 JSON 自洽 + 禁止声明校验（UNVERIFIED 不得被写成 SUPPORTED；坐标级声明；无“durable resume / 已执行整理 / 全版本支持”字样） | `test_amane_batch_matrix_json.py` |
| E6-27 | HANDOFF：Contract 映射、完整 diff scope、命令与输出、evidence gaps、known limitations（L6-xx）、Phase 7 输入 | `docs/review/P6_C1_HANDOFF.md` |

### 23.1 声明纪律

* 支持声明只能写：“在 SC-03 / SC-04 上经确定性真实宿主验收”，并按 live smoke 记录单独陈述公网状态。
* 禁止：“支持 v0.15.0 / v0.18.0”（无坐标）；“支持 durable resume / 跨进程恢复”；“已执行 / 已验证真实整理”；“公网已验证”（无 VERIFIED 记录）；
  “P6 保证宿主上无遗留任务”；“任务已停止 / confirmed stopped”（P6 只能报告数据库终态已观察）；“每次尝试恰好创建一个任务”（只有无 `CREATION_UNKNOWN` 且 `CREATION_CONFIRMED` 的番号可断言任务数）；
  “跨轮全局 READY / 无冲突”；“元数据是本任务的不可变快照 / 因果归属于本任务”（只声称读取时刻的字段级插件来源）；“宿主进程上全部 SCRAPE 任务数 ≤ M”。
* `UNVERIFIED` / `ENVIRONMENTALLY_BLOCKED` 不得出现在支持声明里。

---

## 24. Mutation / Non-vacuity 控制（冻结；每项都必须让门真正变红）

每个控制都有**孪生**：未变异版本运行同一断言必须绿；变异版本必须红。变异在进程内通过替换被测生产函数 / 类实现（共享同一个 oracle），宿主级控制通过门工具的变体运行（退出码非 0）。

| ID | 变异 | 必须变红的门 |
|---|---|---|
| M6-01 | plugin 未加载（卸载 / 禁用） | E6-11 / E6-16：全部条目 METADATA 阶段失败 |
| M6-02 | FC2 route 改为空 / 非 plugin；（单测）还原任务侧归属校验使外来 `field_sources` 被接受 | E6-16 / E6-07 |
| M6-03 | 返回错误号（代理改写 `metadata.number`）；（单测）去掉号等价校验 | E6-12 / E6-07 |
| M6-04 | `DONE` 缺 `metadata_id` 被当作成功 | E6-12 / E6-07 |
| M6-05 | metadata 不满足最低成功（title 空白）被接受 | E6-12 / E6-07 |
| M6-06 | 宿主任务 `FAILED` 被当作成功 | E6-08 / E6-12 |
| M6-07 | 重试意外重跑成功条目（可重试集合包含全部） | E6-13（宿主任务账本计数） |
| M6-08 | 取消错误地取消别人的任务（用 `status` / `type` 的宽泛取消） | E6-09 / E6-14（旁观任务被取消） |
| M6-09 | 提交体带 `media_id` / 路径 / hash | E6-05（请求账本键集） |
| M6-10 | 调用 `execute` / 文件系统执行 | E6-18（tripwire + AST） |
| M6-11 | 并发超预算：一个 aggregate 提交两个任务 / `UNKNOWN` 之后自动再 `POST` / 绕过 P4 预算 / 隐藏 scheduler 或无界 fan-out（`ORPHAN-M1` 下未变异实现 PASS，这些变体 FAIL） | E6-10 / E6-14 |
| M6-12 | 凭据泄漏进 `repr` / 异常文本；**在任何 `except` 块内 `raise … from None`（`__context__` 仍保留 httpx 异常与 `Authorization`）**；**凭据 / 配置校验路径**：`token.encode("ascii")` + `except UnicodeEncodeError: raise … from None`（`.object` 保留 token）、校验失败时 `token` 形参仍留在帧局部；`_transport` / `_call` 帧局部保留 `Request` / `Response`；token 存入异常属性 | E6-17 / E6-03 |
| M6-13 | 启用重定向跟随 / cookie 回传 | E6-17 / E6-05 |
| M6-14 | 取消把“请求已发送”或数据库 `FAILED` 当成“执行已停止”（输出 `CONFIRMED_STOPPED` 类结论，或忽略 claimed-window / 晚到写入） | E6-09 / E6-14（不确定性场景、claimed window、晚到写入） |
| M6-15 | 控制流引入错误文本解析（`"timeout" in str(exc)`） | E6-03（AST） |
| M6-16 | 提交超时后重试 `POST /api/tasks`；或把 `CREATION_UNKNOWN` 折算为 0 / 1 并据此再提交 | E6-08 / E6-13（重复任务） |
| M6-17 | 字段值取自持久化展示列，或把展示列的 `field_sources` / `locked_fields` / `updated_at` 当内容证据（Design-R1 的 E1/E2/E3/R0 做法）：手工覆盖 B 被当作插件内容输出 | E6-07 / E6-16（①②④⑥） |
| M6-18 | `raw` 缺少插件键时回退到展示列，或改读其它 `raw` 键 / 带 `:lang` 的键 / 不校验 `PluginRaw` 结构 | E6-07 / E6-16（⑤） |
| M6-19 | 把 `SubmissionState` 记错（响应丢失记为 `CREATION_CONFIRMED`；`CREATION_UNKNOWN` 记为零任务 / `NOT_ATTEMPTED`） | E6-08 / E6-13 |
| M6-20 | 门面绕过 P4 并发控制（直接对 engine 并发 `aggregate`，或在 P4 busy 时仍发 `POST`） | E6-10 / E6-03 |
| M6-21 | 删除 / 放宽 JSON 结构预扫描（无上限，或改成递归实现，或在 `json.loads` 之后才检查，或计数口径与第 8.4 节不符） | E6-06 / E6-17 / E6-03 |
| M6-22 | 汇总把各轮 READY 相加并在 `rounds > 1` 时声称 `cross_round_verified` | E6-19 |
| M6-23 | 映射把 `source_urls` / `external_ids`、`raw` 的非映射字段或展示列送入 `NormalizedMetadata` / `field_sources` | E6-07 |
| M6-24 | 审计记录组合校验被删除或放宽（正常成功被计入 `abandoned_attempts`；`C == NOT_APPLICABLE` 与 `T` 不一致；`S=UNKNOWN` 记为 `NOT_APPLICABLE`） | E6-08 / E6-09 |

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
I6-05  每个进入提交阶段的 aggregate 最多发送一次 POST，POST 永不自动重试；仅 202 + 严格 schema 才是 CREATION_CONFIRMED，其余 CREATION_UNKNOWN 不折算为 0 / 1，也不得成为重新提交的理由
I6-06  每个 active aggregate 最多一个 active 宿主任务；无 fan-out、无隐藏 worker；P6 正在等待的宿主任务数 peak_in_flight ≤ M（不推广为宿主全部存活任务 ≤ M）
I6-07  取消只针对已知 id 的自己的任务；请求体绝不含 status / type；绝不使用 delete / retry
I6-08  取消有界（cancel_budget_seconds）；无分离后台 task；请求已发送（L1）≠ 数据库终态已观察（L2）≠ 执行已停止（L3，永远 UNVERIFIED，无 CONFIRMED_STOPPED）；UNCERTAIN_* 与 abandoned_attempts 显式暴露
I6-09  成功必须同时满足第 11.2 节八项校验（含 raw 中的插件原始记录）；缺一 fail closed，且失败种类唯一
I6-10  唯一 SourceResult source_id == "ffcc.fc2-metadata"；永不产生 PARTIAL；永不伪造 trace / 内部来源 provenance
I6-11  field_sources 值 ⊆ contributing_source_ids == ("ffcc.fc2-metadata",)；输出的每个字段值只来自 raw["ffcc.fc2-metadata"]（值级证据），不来自展示列；source_urls / external_ids 恒为空
I6-12  所有控制逻辑只基于 HTTP 状态码 / 枚举 / 结构化 schema / 异常类型；绝不基于文本
I6-13  error_detail 是封闭词汇；不含 URL / 宿主文本 / token / 任务 id
I6-14  凭据：显式注入、redacted、不可序列化、不落盘；整个 src/fc2_amane_batch/** 抛出的异常及输出文本（保护面 P1–P3）不新引入禁入内容 F（token 及其子串、httpx Request/Response/HTTPError、UnicodeError.object、响应体），经 __cause__ / __context__ / args / __notes__ / 本包帧 f_locals 浅层均不可达（from None 不算证明）；承诺不涵盖调用方持有的 credential/config/client/engine 对象自身所含的认证状态（所有权状态）；无 cookie jar 持久化；无环境代理 / netrc；无重定向；TLS 不可降级
I6-15  响应流式读取且字节、深度、节点数、集合项数均有上限（MAX_RESPONSE_BYTES / MAX_JSON_DEPTH / MAX_JSON_NODES / MAX_JSON_COLLECTION_ITEMS）；严格 reader；未知额外键容忍但同样受结构上限约束、必需键缺失 fail closed；超限为封闭结构化失败
I6-16  语义输出确定；运维输出（task id / 时间 / 计数 / 随机标识）永不进入语义输出
I6-17  P6 只拥有重试 eligibility / 子集选择，P4 独占重试执行 / 调度 / 并发；retry_failed 仅选择子集并调用 P4 preview；永不重跑成功条目；无自动重试循环
I6-18  无 durable resume / checkpoint / 持久化 / 跨进程锁；审计账本有界
I6-19  不执行：S6-1..S6-5
I6-20  不修改用户 Amane 配置；生产代码零 /api/config 访问
I6-21  门面 preflight 在任何任务被创建之前失败（整批前置条件）；“零副作用”仅指不创建 SCRAPE / 其它任务、不修改业务数据（宿主访问日志不在声明内）
I6-22  本包零 logging、零文件 API、零环境变量读取
I6-23  AmaneBatchPreview 不可变；其轮次中的 BatchPreview 是 P4 原对象（不复制、不改写）
I6-24  普通条目失败不拖垮其它条目；致命 / 取消保持 P4 现有语义
I6-25  值级内容来源：输出字段值只由 raw["ffcc.fc2-metadata"] 确定性派生（展示列、持久化 field_sources / locked_fields / 时间戳都不是内容证据）；保证范围仅为“读取那一刻的插件原始记录”，不声称任务独占或不可变快照（11.3.4）；record_freshness / display_title_diverged 只是审计提示
I6-28  审计记录的 S/T/C/R 四维组合必须满足第 10.3 节 LC1–LC8；abandoned_attempts / uncertain_cancellations / creation_unknown 按第 10.3 节口径精确计数，正常成功与未取消的失败不计入
I6-29  并发 oracle 区分 A / K / H：|A| ≤ M，|K| ≤ |A|；不要求 |H| ≤ M；独立 POST 账本证明每个 aggregate 至多一个 POST
I6-26  门面调用顺序冻结（9.5）：本地校验 → preflight → P4 公开 preview；busy claim 只在 P4 入口；门面不复制 P4 锁、不绕过 P4 并发控制、不承诺零网络访问或 busy 优先级
I6-27  每个 BatchPreview 的 READY / 冲突结论仅对本轮有效；P6 不提供跨轮全局 READY 保证；汇总区分逐轮计数与 cross_round_verified
```

---

## 27. 已知局限（如实记录；进入 E6-27）

| ID | 局限 |
|---|---|
| L6-01 | **独占 route 前提**（H6-1）：P5 INSTALL 把 plugin 放在 FC2 route 最前并保留原站点；P6 需要其它站点不再贡献字段，否则任务侧证据出现外来站点，该条目 fail closed（`HOST_ATTRIBUTION_FOREIGN`）。P6 不读取也不修改用户配置，所以由用户自行满足；独占 route 只是前提，真正的归属证明是逐字段的双侧证据（第 11.3 节）；审计里的 `failure_counts` 用于诊断 |
| L6-02 | 非回环主机必须 `https`；不支持明文局域网、自定义 CA、代理、路径前缀；回环可用 `http` |
| L6-03 | 遗留任务：`CREATION_UNKNOWN`（提交歧义，含 401 / 超时 / 响应丢失）、`abandoned_attempts`（`UNCERTAIN_*` 与 `TERMINAL_*_OBSERVED`）、进程退出，都可能在宿主上留下仍在运行或排队的 SCRAPE 任务，**它们的执行协程可能继续写 Metadata 并占用宿主 worker 并发**；P6 不找回、不跨进程清理（无持久化） |
| L6-04 | **取消只证明数据库记录，不证明执行停止**（R1-04）：DIFF-P6-01 / DIFF-P6-05 —— v0.15.0 在“已认领、协程尚未登记”（含信号量等待）的窗口内取消会把记录改成 `FAILED` 而协程继续运行；v0.15.0 的无条件 `fail_task` 还可把“恰好完成”的任务改写成 FAILED（“Cancelled by user”），此时 Metadata 可能已被写入；v0.18.0 窗口更小但无法证明不存在。P6 的 `TERMINAL_FAILED_OBSERVED` / `TERMINAL_DONE_OBSERVED` 因此都不是“已停止”，每次放弃的 L3 都是 `UNVERIFIED`，晚到的 Metadata 写入不可排除 |
| L6-05 | 无法区分“番号在所有来源都不存在”与“来源 / 宿主故障”（宿主只给 `failed` + 文本；不解析文本）；统一 `HOST_TASK_FAILED` |
| L6-06 | **用户的 Amane 配置与手工编辑不流入结果**（R2-01）：LLM 翻译、FacetRule 规范化、Resource 物化 / 海报裁剪、用户在 Amane 里手工编辑、字段锁、merge 选择都只作用于展示列，P6 的输出只来自插件的原始记录 `raw["ffcc.fc2-metadata"]`；若用户期望“Amane 中编辑后的标题”进入 NFO，P6-C1 不支持。展示列与 `raw` 的 `title` 不同时只在审计里置 `display_title_diverged`，不失败也不改变输出 |
| L6-07 | 宿主排队时间计入 `aggregate_deadline_seconds`；Amane 宿主 worker 并发的**缺省是 10**（`WorkerConfig.concurrency`，两个版本；验收宿主若明确配置其它值则以实际配置为准）；M 大于宿主实际并发、或被遗弃的孤儿任务占用并发时，任务会排队；P4 并发 M 与宿主并发是两个独立的数。**P6 只保证 `\|A\| ≤ M` 与 `\|K\| ≤ \|A\|`，不保证宿主上与本批相关的全部任务数 `\|H\| ≤ M`**（孤儿任务可使 `\|H\| > M`，第 14 节） |
| L6-08 | SCRAPE 会 **upsert 宿主 Metadata 库**：P6 的 preview 对用户**媒体 / library 文件系统**只读，但对 **Amane 数据库不是只读**；宿主可能扇出 `ACTOR_SCRAPE` 后继任务（`actor_scraping.auto_scrape` 缺省 True），P6 不跟踪也不取消 |
| L6-09 | 重试只覆盖 METADATA 阶段失败；图片候选级部分失败是警告，不重试 |
| L6-10 | 若用户的 Amane 开启海报裁剪，poster 可能被替换为宿主内部 URL 而被剔除，体现为 P4 的 `POSTER_ABSENT` / `FANART_ABSENT` 警告 |
| L6-11 | 公网证据可能是 `UNVERIFIED_ENVIRONMENT` / `NOT_RUN` |
| L6-12 | SC-01 / SC-02（冻结桌面）可选；macOS / Linux / Docker `UNVERIFIED` |
| L6-13 | `use_cache=[]` 强制刷新：对来源站点的请求量更大，每次运行都会重写宿主 Metadata |
| L6-14 | 无 progress API，不使用 WebSocket |
| L6-15 | 号等价按 Core `normalize_fc2_number`；用户宿主里以非常规写法保存的旧行会被等价接受（映射后一律是请求的 canonical） |
| L6-16 | 重试由调用方显式驱动，最多 `MAX_RETRY_ROUNDS = 16` 轮；多轮视图不能作为单个 `BatchPreview` 执行（Phase 7 逐轮执行）；**跨轮 READY / 冲突无全局保证**（R1-06）：不同番号可共享同一个 hardlink 源文件或目标，单轮 preview 看不见别的轮次，Phase 7 若跨轮执行必须对合并范围重新验证源身份与目标冲突 |
| L6-17 | P5 已记录的局限继续成立（C1 L-01..L-15、C2 L-C2-01..16），尤其 L-C2-13（sidecar 的 admission-time integrity，不是 runtime immutability） |
| L6-18 | **内容来源的保证范围**（R2-01，第 11.3.4 节）：P6 声称“输出值完全由 Amane `raw` 中插件的原始记录确定性派生，而公开 PATCH / 字段锁 / merge 不能改写 `raw`”；**不**声称：① 该 `raw` 是刚完成的这个任务独占写入的——并发的同号插件 SCRAPE（含遗留孤儿任务）可在任务完成后整体替换 `raw`，内容仍是插件的一次独立抓取，证据上无法与本任务区分；② Amane `raw` 与插件 Core 输出逐字节相同（S1 第 0 步用确定性夹具核对，不符 ⇒ U6-6）；③ 防住对 Amane 数据库的直接篡改或 Amane 自身缺陷；④ `raw` 的形状在 v0.15.0 / v0.18.0 之外的版本上成立。`source_urls` / `external_ids` 恒为空（NFO 不读取它们） |
| L6-19 | `record_freshness` 只是提示而不是证明：墙钟回拨会使“任务之后的写入”显得更早，时间戳分辨率会掩盖同一时刻内的写入，任务内部“写入 → 标 done”之间的极短间隔内他人的写入不可分辨；时间戳缺失 / 不可解析 / 时区不一致时为 `UNKNOWN`。它不改变语义输出，也不得被当作字段来源的唯一或充分证据 |
| L6-20 | 当 P4 已忙时，被拒绝的门面调用可能已完成本地校验与一次只读 preflight `GET`（第 9.5 节）：不声称零网络访问，也不承诺 busy 与参数错误之间的全局优先级；宿主可能记录 preflight 的访问日志 |

---

## 28. 升级门 / 停止条件（出现任一项必须停止并上报，不得在普通施工中自行解决）

```text
U6-1   需要修改任何 CLOSED production 语义 → AUTHORITY ESCALATION REQUIRED（列出 package / 原因 / 影响 / 兼容 / 安全 / 回归范围）
U6-2   需要调用 execute / ORGANIZE / TRASH，或修改用户文件
U6-3   需要任何持久化 / durable resume / checkpoint / 跨进程锁
U6-4   需要表 H1 之外的 endpoint，或需要版本分支 / feature detection
U6-5   需要读取 / 修改 Amane 配置，或解析宿主日志 / 错误文本 / 异常消息
U6-6   真实宿主观测与第 7 节的事实不一致（出现 DIFF-P6-01..05 之外的差异；含：`raw["ffcc.fc2-metadata"]` 缺失或与插件 Core 输出（确定性夹具）不等价、`MediaMetadata` 形状与 11.3.3 不符、公开 `PATCH` 竟能改写 `raw`、成功 SCRAPE 的任务 `field_sources` 缺 `title`、JSON 实测规模超过上限 1/4）
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
P6-C1                         : DESIGN CANDIDATE — INDEPENDENT DESIGN REVIEW REQUIRED
Frozen Contract               : NOT YET ACCEPTED
Construction Plan             : NOT YET ACCEPTED
Design Accepted Head          : NOT ESTABLISHED
Implementation                : NOT STARTED
Production Modified           : NO
Tests Modified                : NO
Risk Class                    : C
Phase 6 package count         : 1
HG-1 (historical gate rebind) : ACCEPTED（三份独立 Design Review 一致裁决）— NOT EXECUTED（未来 S1 test-only repair；本轮 Tests Modified = NO）
Design-R1                     : SUPERSEDED BY DESIGN-R2 CANDIDATE（c05c7eb）
Design-R2                     : CANDIDATE — REMAINING FINDINGS CLOSURE（R2-01..R2-05）
```

本文不得被解读为 FROZEN / DESIGN PASS / IMPLEMENTATION AUTHORIZED / CLOSED。唯一 authority 转换：独立 Design Review PASS → 该 Design Candidate SHA 成为
Design Accepted Head（Frozen Contract / Plan Head、Implementation Input）→ 才允许 Developer 开始 S1。

---

## 30. Independent Design Reviewer 的强制审查点

下一位 Independent Design Reviewer **至少**必须审：

```text
DR-01  F-1：`preview_retry` 是否真的要求完整 `BatchExecutionResult`（P4 `retry.py` / `orchestrator.py` 源码核对）
DR-02  F-2：`fc2_organizer` 顶层子包集合是否被多个 CLOSED 测试精确钉死；同级包 `fc2_amane_batch` 的选择
DR-03  HG-1：历史 P5-C2 浮动 `HEAD` 门禁，以及最小重绑是否降低历史验收强度
DR-04  重试所有权拆分：P6 拥有 eligibility / 子集选择；P4 拥有执行 / 调度 / 并发
DR-05  真实 Amane v0.15.0 / v0.18.0 的 endpoint / schema 事实（表 H1 / H2）
DR-06  `TaskStatus` 无 `CANCELLED` 与取消不确定性模型（`CancelOutcome`）
DR-07  宿主 Metadata 库写入 / 不得声称“对宿主数据库只读”
DR-08  route / provenance fail-closed 规则（独占 route 前提、`field_sources` 归属校验）
DR-09  凭据 / 安全边界（redaction、无 cookie / 代理 / netrc、无重定向、TLS）
DR-10  不执行文件系统 / Phase 7 隔离（S6-1..S6-5 三层机检）
```

HG-1（DR-03）的实质裁决已被三份独立 Design Review 一致接受，本轮只精确化其文字（第 5.4 节）；Design-R1 Closure Reviewer 需确认精确化后的条款与实质裁决一致。

Design-R1 追加审查点：

```text
DR-11  R1-01 / R2-01：值级来源——输出只由 raw["ffcc.fc2-metadata"] 派生；E1/E2/E3/R0 已撤销；公开 PATCH 不能写 raw 的源码依据；放弃的宿主后处理语义是否被诚实声明；保证范围（非任务独占）是否诚实
DR-12  R1-02：SubmissionState 四态；CREATION_UNKNOWN 不折算；任务账本不等式
DR-13  R1-03：异常图封闭（__cause__ / __context__ / __traceback__ 帧局部）；from None 不被当作证明
DR-14  R1-04：取消三层（L1/L2/L3）；无 CONFIRMED_STOPPED；claimed-window 与晚到写入
DR-15  R1-05：门面调用顺序；不复制 P4 锁；无法承诺的优先级已撤销
DR-16  R1-06：跨轮冲突无全局保证；AmaneBatchSummary 的 cross_round_verified
DR-17  R1-07：JSON 结构上限（MAX_JSON_*）与迭代式预扫描
DR-18  R1-08：Amane 缺省 worker concurrency = 10 的修正与三个并发数的区分
DR-19  R2-02：异常 / 凭据边界覆盖整个包；保护面 P1–P3、禁入内容 F、所有权状态例外、C1–C7、失败矩阵与红绿孪生
DR-20  R2-03：JSON 预扫描 O(B) 成本模型、辅助空间 O(MAX_JSON_DEPTH)、边界矩阵
DR-21  R2-04：A / K / H 三集合与孤儿安全的并发 oracle，ORPHAN-M1
DR-22  R2-05：S/T/C/R 正交模型、LC1–LC8、计数口径、NOT_APPLICABLE ⇔ T=NONE
```
