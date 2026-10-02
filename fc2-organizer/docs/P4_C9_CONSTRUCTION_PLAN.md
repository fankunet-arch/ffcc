# P4-C9 施工计划（Construction Plan）-- 结构化诊断（Diagnostics）

```text
Governance Mode                    : ACCELERATED v2
Governance Authority               : docs/PROJECT_GOVERNANCE_ACCELERATION.md @ 3b9d39e9adbcc8a009707486eebbb8736a5b1c4d
Package Frozen Base                : a662659dfd6e801531b14af7913d84a5f9f859e2（P4-C8 Final Closure Docs Head）
Planning Parent                    : 3b9d39e9adbcc8a009707486eebbb8736a5b1c4d
Risk Class                         : B
User Capability / Vertical Closure : Diagnostics end-to-end —— 既有 BatchPreview / BatchExecutionResult（及其公开可达的 metadata /
                                     source / execution 模型）-> 只读确定性投影 -> 不可变 BatchDiagnostics（batch / item / stage /
                                     source / field provenance / failure / retry）-> 脱敏与路径策略 -> 确定性 JSON bytes
Why Not Merge With Previous C      : P4-C8 已正式 CLOSED；Batch Orchestration 已独立验收；Diagnostics 是新的、可独立验收的用户
                                     能力边界；不得为减少 C 数量追溯重写 P4-C8 closure（第 1 节 Q1）
Why Not Split Further              : model / integration / JSON+redaction+tests 共同构成同一个 Diagnostics 纵向能力；取消其间的
                                     package boundary 不降低 correctness / safety / auditability（第 1 节 Q3、Q4）
Internal Stages                    : S1 / S2 / S3（连续施工，无中间 Review、无中间 docs closure）
Independent Review Plan            : Design Authority Review（本 Contract + Plan，一次）
                                     + one C-level implementation Independent Level 1 Review（S1-S3 全部完成后，一次）
Owner Question Gate                : BUSINESS DECISIONS ONLY
Evidence Gate                      : 第 8 节（Contract -> implementation -> test 映射、完整 diff scope、P4-C9 专项 / targeted /
                                     contract / full suite、mutation / non-vacuity、脱敏 canary、确定性、资源与输出上界、无副作用、
                                     500-item 诊断门槛、MAX 边界、Windows 11 / Python 3.12.x 平台证据、evidence gaps、known limitations）
```

```text
Package          = P4-C9 Diagnostics（fc2_organizer.diagnostics）
Branch           = claude/phase4-c9-diagnostics（自 Planning Parent 3b9d39e9adbcc8a009707486eebbb8736a5b1c4d 创建）
规范合同         = docs/specifications/PHASE4_DIAGNOSTICS_CONTRACT.md
P4-C9 Design     = IMPLEMENTED — INDEPENDENT DESIGN REVIEW REQUIRED
Frozen Contract  = NOT YET ACCEPTED
Construction Plan= NOT YET ACCEPTED（本文件）
Implementation   = NOT STARTED
```

坐标规则（冻结，治理文档第 19 节）：Package Frozen Base 是 `a662659dfd6e801531b14af7913d84a5f9f859e2`，**不是**
`3b9d39e…`；`3b9d39e…` 是 Governance Authority 与 Planning Parent，即本分支起点。两者之间只有治理文档提交，没有任何
production / test 改动。

本计划与合同一起一次性冻结 P4-C9 的全部施工内容。Design / Authority Review PASS 后，开发者只能**执行**本计划：不得重新设计、
不得调整 S 边界或公开 API、不得把任何设计项推迟到“开发时再决定”。凡合同与本计划未写明的实现细节（内部 helper 命名、文件
内部组织、fixture、断言写法），由开发者按以下优先级自行裁决，并在对应 commit message 中记录理由：

```text
1. Frozen Contract   2. fail closed   3. 只读 / 零副作用   4. 脱敏   5. deterministic
6. 不改变 CLOSED package 语义   7. bounded resources   8. minimal dependency   9. testability
```

---

## 1. 治理四问（治理文档第 15 节）

### Q1 为什么这项工作不能和前一个 C（P4-C8）一起完成？

* P4-C8 已经正式 **CLOSED**（Final Closure Docs Head `a662659…`）；其 Contract、Construction Plan 与 HANDOFF 按治理文档第 5 节
  不受追溯修改。
* Batch Orchestration 本身已独立验收完成（preview / execute / retry / merge / summary / outcome、500-item 文件系统门槛、
  6178 passed / 40 skipped）；P4-C8 合同第 32 节已把诊断明确划为 P4-C9 的边界（“P4-C8 只返回内存中的结构化模型……P4-C9
  决定如何呈现、序列化或导出”）。
* Diagnostics 是一个新的、可独立验收的用户能力：它的验收问题（第 1 节问题表、脱敏、确定性序列化、输出上界）与 orchestration
  正确性完全不同。
* 不得为了减少 C 数量追溯重开、重写 P4-C8 closure。

### Q2 单独拆包降低了什么具体风险？

* diagnostic projection / redaction / serialization 可以在**不重新打开** orchestration 正确性边界的情况下独立设计、实施与验收；
  P4-C9 的全部生产改动被限制在新目录 `src/fc2_organizer/diagnostics/**`（第 5 节）。
* 避免为了“日志”把 filesystem、retry、orchestration execution、metadata acquisition 的行为改动混入同一个改动：P4-C9 没有任何
  这类行为，它是 observer / projector，不是 controller。
* reviewer 可以用一个简单、机器可验证的判据审计 CLOSED 边界：`git diff <Design-Accepted Head>..<C9 Head> -- fc2-organizer/src`
  只包含 `src/fc2_organizer/diagnostics/**`。

### Q3 该风险是否值得额外增加一次“开发停止 + Review + Closure”？

* 值得，但只增加**一次 C 级**的边界：P4-C9 作为一个 C，整体只有一次 Design Authority Review 与一次 implementation Level 1
  Review。
* 不值得在 C 内部继续增加边界：S1 model / schema、S2 integration / provenance mapping、S3 output / redaction / guards / tests
  任何一个单独都不构成可验收的用户能力（没有 S3 就没有安全输出；没有 S2 就没有任何真实 evidence），在它们之间插入 Review
  只会增加等待，不会增加证据。因此 **不**拆成 C9-1 models / C9-2 integration / C9-3 JSON / C9-4 tests。

### Q4 如果取消这个边界，是否影响 correctness、safety 或 auditability？

* 取消 **P4-C8 / P4-C9 之间**的边界：**会**影响——它会要求重开一个 CLOSED package，或者把诊断改动与已验收的编排语义混在一起，
  降低 auditability，并使 P4-C8 的 closure 证据失效。因此 P4-C9 必须是独立 C。
* 取消 **S1 / S2 / S3 之间**的 package boundary：**不会**影响 correctness、safety、auditability——三者共享同一份 Frozen Contract、
  同一套测试矩阵与同一次 C 级 Review；每个 S 仍保留 developer checkpoint、单元测试、非空洞性与独立 commit。按治理文档第 15 节，
  S1-S3 原则上必须合并在一个 C 内，连续施工。

## 2. Risk Class 与风险升级门

* **Risk Class = B**（治理文档第 8.2 节明确列出 diagnostics）。保持 B 的前提是合同第 5.1 节的安全边界全部成立。
* **C 内中间独立 Review：不需要**。治理文档第 9 节五个触发条件中，只有第 2 条“前一步定义新的 Frozen Contract”适用于
  **设计**本身，已由 Design Authority Review 覆盖；实施阶段的 S1-S3 不建立在不可逆安全边界上、不会污染大量既有代码（只新增
  目录与七处测试守卫最小更新）、不涉及 C 类核心边界。
* **风险升级门（冻结，与合同第 5.3 节一致）**：施工中出现以下任何一项，立即停止正常 B 类施工，重新评估为 C 类：

```text
A. durable persistence
B. diagnostic 数据自动落盘，形成长期记录
C. 敏感信息落盘
D. 修改用户媒体文件
E. 修改 / 删除 / 移动现有 artifact
F. 引入 source-loss 风险
G. cross-process locking
H. 新的 race / concurrency ownership
I. 不可逆 schema migration
J. 新的 security boundary
K. 需要改变已 CLOSED 的 P4-C8（或任何其它 CLOSED package）production semantics
```

  本清单不穷尽；任何达到治理文档第 8.3 节 C 类定义的风险同样升级。升级时：停止施工，在 HANDOFF / 状态说明中记录触发项与
  证据，等待治理裁决；不得以“P4-C9 默认 B 类”覆盖。没有治理依据不得降级。

## 3. P4-C8 CLOSED 边界保护（Critical）

* P4-C9 只 read-only 消费 `fc2_organizer.orchestration` 的公开 API 与其公开可达的下层公开模型（合同第 8.5、9 节）。
* **不得修改** `src/fc2_organizer/orchestration/**`，也不得修改任何其它 CLOSED package 的 `src/**`、合同、施工计划或 HANDOFF。
* **不得**把 live logging hooks、事件回调、计时埋点塞回 P4-C8 核心执行路径。
* 设计阶段审计结论：**不存在 BLOCKED DESIGN ISSUE**（合同第 5.4 节）。唯一缺口——P4-C8 `revalidate` 非公开——以“对精确公开类
  调用其自身 `__post_init__`”替代（合同第 24.3 节），不需要修改 P4-C8。
* 若实施中确认没有修改 CLOSED package 生产语义就无法交付某项必要诊断：**不得自行授权**；在 HANDOFF / 状态说明中记录
  `BLOCKED DESIGN ISSUE`（说明为什么必须修改、影响哪个历史 Contract、回归范围、兼容性与安全影响，治理文档第 13 节）并 **STOP**。
  这自动构成高风险治理事件（风险升级门第 K 项）。

---

## 4. 内部施工模型（S1 -> S2 -> S3，连续施工）

规则（全部 S 适用）：

* S1 -> S2 -> S3 **连续施工**：S1、S2 完成后不 STOP、不等待 Review、不创建 docs closure commit，直接进入下一 S。
* 每个 S 结束时执行 **developer checkpoint**（不是治理节点）：该 S 的新测试全部通过；`tests/unit/orchestration` +
  `tests/contract` 无回归；`git diff --check` 干净；diff 只触及该 S 允许的文件。checkpoint 结果写入该 S 的 commit message。
* 每个 S 可以有一个或多个线性 commit；禁止 rebase、amend、squash、force push、历史改写；禁止 rebase 已被 Review 的 design
  commit。
* 合同在实施期间只允许改第 32 节“实现状态”的状态行；本计划只允许改第 10 节“状态”的状态行。任何语义改动 = authority 修订，
  必须 STOP 并走独立复查（治理文档第 11.2 节）。

### S1 —— Diagnostic model / schema / projection skeleton

交付：

* `src/fc2_organizer/diagnostics/__init__.py`（S1 时 `__all__` 只含 S1 已存在的名称，按合同第 8.1 节顺序的子序列；S3 时为完整集合）、
  `errors.py`（合同第 8.4 节全部错误）、`models.py`（四个诊断枚举、合同第 8.3 节全部常量、第 11 节全部不可变模型及
  `__post_init__` 校验、安全文本正则常量）。
* 安全文本 / 数值校验 helper（`models.py` 内，供 S2 投影与 S3 renderer 共用），包括安全 id、`error_type`、路径文本、残留文件名、
  计时范围。
* 合同第 27.3 节七处既有架构守卫的最小授权更新（新顶层目录在 S1 出现，守卫必须在 S1 同步更新，否则全量回归失败）。
* `tests/contract/test_diagnostics_architecture.py`：S1 时断言模块集合恰为 `{__init__, errors, models}`，以及 import / 禁止清单 /
  反向依赖 / 无全局可变状态；后续 S 只扩展模块集合与新增断言。

S1 测试（`tests/unit/diagnostics/`）：

* `__init__.py`（空）、`_builders.py`（以公开构造函数手工构建合法 P4-C8 / Phase 3 / P4-C7 输入模型与诊断模型的工厂，供全部 S 使用）；
* `test_diagnostics_errors.py`：层次、多重继承、固定 message、无链接；
* `test_diagnostics_models.py`：合同第 11 节每个模型每个字段的正 / 反例、跨字段不变量、`bool` / 子类冒充、frozen / slots；
* `test_diagnostics_public_api.py`：`__all__`（S1 子集）、常量数值、`MAX_DIAGNOSTIC_ITEMS == MAX_BATCH_ITEMS`、
  `PROVENANCE_FIELD_ORDER == fc2_metadata_core.aggregation.policy.FIELD_ORDER`、四个新枚举、复用上游枚举 value 集合快照。

S1 允许改动文件：

```text
A src/fc2_organizer/diagnostics/__init__.py
A src/fc2_organizer/diagnostics/errors.py
A src/fc2_organizer/diagnostics/models.py
A tests/unit/diagnostics/__init__.py
A tests/unit/diagnostics/_builders.py
A tests/unit/diagnostics/test_diagnostics_errors.py
A tests/unit/diagnostics/test_diagnostics_models.py
A tests/unit/diagnostics/test_diagnostics_public_api.py
A tests/contract/test_diagnostics_architecture.py
M tests/contract/test_discovery_architecture.py        （仅合同第 27.3 节授权改动）
M tests/contract/test_planning_architecture.py         （同上）
M tests/contract/test_publication_architecture.py      （同上）
M tests/contract/test_nfo_architecture.py              （同上）
M tests/contract/test_execution_architecture.py        （同上）
M tests/contract/test_materialization_architecture.py  （同上）
M tests/contract/test_orchestration_architecture.py    （同上）
M docs/specifications/PHASE4_DIAGNOSTICS_CONTRACT.md   （仅第 32 节状态行）
M docs/P4_C9_CONSTRUCTION_PLAN.md                      （仅第 10 节状态行）
```

S1 完成：继续 S2，不等待 Review。

### S2 —— Existing-result integration / source + field provenance mapping

交付：

* `src/fc2_organizer/diagnostics/projection.py`：合同第 12 节全部单条目映射——条目、issue、metadata、source / attempt、
  field provenance（按 `PROVENANCE_FIELD_ORDER` 查询，不迭代 mapping）、conflicts（只取 source id）、图片失败分组、preflight、
  execution、路径策略（第 18 节）、计时策略（第 12.7 节）、结构上限（第 21.2 节）、下层不变量重检（第 24.3 节，含
  `NormalizedMetadata.__post_init__` 例外）。
* `src/fc2_organizer/diagnostics/build.py`：`build_preview_diagnostics`、`build_execution_diagnostics`；合同第 24.2 节检查顺序；
  `shape` 判定（第 10 节）；批级字段与 summary / outcome 原样携带（第 12.8 节）。
* `__init__.py` 导出扩展到 S2 已存在的名称；架构测试模块集合扩展到 `{__init__, errors, models, projection, build}`。
* 必须 read-only、deterministic；不读取合同第 9.3 节任何字段。

S2 测试：

* `test_diagnostics_preview.py`：READY / BLOCKED / UNPREPARED、每个 preview 可达的 `IssueReason`、warnings、冲突组、retry preview；
* `test_diagnostics_execution.py`：每个 `ExecutionDisposition`、三种 `ExecutionStatus`、failure、effect / artifact 计数、
  checkpoint_present、leftover、MAIN / RETRY / MERGED、`retry_kind` 与 P4-C8 逐条相等（六种 RetryKind）；
* `test_diagnostics_sources.py`：SUCCESS / NOT_FOUND / 五种 operational failure、refined kinds、CIRCUIT_OPEN、deadline during
  attempt / backoff、retried、无 trace、disabled sources、安全 id 规则、结构上限边界；
* `test_diagnostics_provenance.py`：四类字段出处、优先级顺序、FAILED 为空、完整性 fail closed（表外 key、非 MappingProxyType、
  非 contributing id）、插入顺序反转不改变结果；
* `test_diagnostics_input_integrity.py`：错误顶层类型 / 子类 / 策略类型；`object.__setattr__` 篡改 P4-C8 与下层字段；
  `items` 非 tuple；条目数 2001（在逐条工作前失败，计数证明）；检查顺序；诊断失败后输入模型逐字段不变；
* `test_diagnostics_no_side_effects.py`：合同第 28.6 节（文件系统快照、fake 调用计数 0、被禁止的 API 全部 monkeypatch 为抛错仍成功、
  输入图逐字段相等且嵌套对象身份不变、诊断后 preview / result 仍可被 P4-C8 消费）；
* `test_diagnostics_timing.py`：OMIT / INCLUDE、截断、范围与非法值。

S2 允许改动文件：

```text
A src/fc2_organizer/diagnostics/projection.py
A src/fc2_organizer/diagnostics/build.py
M src/fc2_organizer/diagnostics/__init__.py
M src/fc2_organizer/diagnostics/models.py               （只允许为 S2 需要的 helper / 常量做追加或修复 S1 缺陷，不得改变合同语义）
A tests/unit/diagnostics/test_diagnostics_preview.py
A tests/unit/diagnostics/test_diagnostics_execution.py
A tests/unit/diagnostics/test_diagnostics_sources.py
A tests/unit/diagnostics/test_diagnostics_provenance.py
A tests/unit/diagnostics/test_diagnostics_input_integrity.py
A tests/unit/diagnostics/test_diagnostics_no_side_effects.py
A tests/unit/diagnostics/test_diagnostics_timing.py
M tests/unit/diagnostics/_builders.py
M tests/unit/diagnostics/test_diagnostics_public_api.py
M tests/contract/test_diagnostics_architecture.py
M docs/specifications/PHASE4_DIAGNOSTICS_CONTRACT.md   （仅第 32 节状态行）
M docs/P4_C9_CONSTRUCTION_PLAN.md                      （仅第 10 节状态行）
```

S2 完成：继续 S3，不等待独立 Review。

### S3 —— Safe output / redaction / architecture guards / tests / HANDOFF evidence

交付：

* `src/fc2_organizer/diagnostics/render.py`：`render_diagnostics_json`；合同第 24.4 节检查顺序；诊断图重检；显式 JSON 树转换
  （第 22.2 节，不用 `asdict`）；第 17.2 节允许 `str` 的最终白名单检查；有界流式编码（第 21.3 节）；固定编码参数（第 22.1 节）。
* `__init__.py` 的 `__all__` 精确等于合同第 8.1 节；架构测试模块集合为完整 6 个文件，并补齐合同第 27.1 节全部断言。
* `docs/review/P4_C9_HANDOFF.md`（第 8 节要求）。

S3 测试：

* `test_diagnostics_render.py`：顶层 key 集合、每类对象 key 集合恒定、`null` absence、enum `.value`、计数对形式、detail_type 表、
  `sort_keys`、ASCII-only、无末尾换行、schema 常量、篡改诊断图 -> `DiagnosticsIntegrityError`、非法 `str` -> `DiagnosticsUnsafeValueError`；
* `test_diagnostics_redaction.py`：合同第 28.5 节全部 canary 与 mutation；路径策略 `BASENAME` / `NONE`；
* `test_diagnostics_determinism.py`：重复构建 / 渲染相等；临时身份全部替换、完成顺序反转、`field_sources` 插入顺序反转后逐字节
  相同；golden 期望输出；排序 mutation；
* `test_diagnostics_resources.py`：每个结构上限的等于 / 超过边界；输出字节上限（精确长度成功、减 1 失败、超限后停止编码、无部分输出）；
* `test_diagnostics_integration.py`：合同第 28.3 节全部场景（真实 `BatchOrchestrator` + 既有 `tests/unit/orchestration/_fakes.py` /
  `_helpers.py` 的脚本化 fake + 临时目录），对每个场景断言模型与 JSON，并证明第 1 节问题表每一行可被回答；
* `test_diagnostics_scale_gate.py`：500 逻辑条目诊断投影门槛与 `MAX_BATCH_ITEMS` 边界（合同第 28.4 节）；
* `test_diagnostics_mutations.py`（可选拆分）：合同第 28.5 节中不便放在上面文件里的 fail-closed / 无副作用 mutation。

S3 允许改动文件：

```text
A src/fc2_organizer/diagnostics/render.py
M src/fc2_organizer/diagnostics/__init__.py
M src/fc2_organizer/diagnostics/models.py                （仅修复缺陷 / renderer 需要的只读 helper，不改合同语义）
M src/fc2_organizer/diagnostics/projection.py            （同上）
M src/fc2_organizer/diagnostics/build.py                 （同上）
A tests/unit/diagnostics/test_diagnostics_render.py
A tests/unit/diagnostics/test_diagnostics_redaction.py
A tests/unit/diagnostics/test_diagnostics_determinism.py
A tests/unit/diagnostics/test_diagnostics_resources.py
A tests/unit/diagnostics/test_diagnostics_integration.py
A tests/unit/diagnostics/test_diagnostics_scale_gate.py
A tests/unit/diagnostics/test_diagnostics_mutations.py   （可选）
M tests/unit/diagnostics/**                              （S1 / S2 已建立的 P4-C9 测试文件，可补强）
M tests/contract/test_diagnostics_architecture.py
A docs/review/P4_C9_HANDOFF.md
M docs/specifications/PHASE4_DIAGNOSTICS_CONTRACT.md    （仅第 32 节状态行）
M docs/P4_C9_CONSTRUCTION_PLAN.md                       （仅第 10 节状态行）
```

S3 完成后：整个 P4-C9 统一进入一次 **P4-C9 Independent Level 1 Review**，STOP 等待。

## 5. 全局 diff scope 规则（冻结）

在 `<Design-Accepted Head>..<C9 Implementation Head>` 范围内：

* `fc2-organizer/src/**` 的改动只允许位于 `src/fc2_organizer/diagnostics/**`；
* `fc2-organizer/tests/**` 的改动只允许：新增 / 修改 `tests/unit/diagnostics/**`、`tests/contract/test_diagnostics_architecture.py`，
  以及合同第 27.3 节七个文件中的授权改动；
* `tests/unit/orchestration/_fakes.py`、`_helpers.py` 等既有 helper **只读复用，不修改**；
* docs 只允许：`docs/review/P4_C9_HANDOFF.md`（新增）、合同第 32 节与本计划第 10 节的状态行；
* 禁止修改：`CLAUDE.md`、`docs/PROJECT_GOVERNANCE_ACCELERATION.md`、任何其它合同 / 施工计划 / HANDOFF、`pyproject.toml`、依赖、
  `upstream/**`；
* 不新增第三方依赖；不新增任何会写文件、访问网络或持久化的代码；
* 任何超出上述范围的改动需求 = 施工范围修订（authority docs），STOP 并走独立复查。

## 6. Implementation Commit 策略

* 允许 S1 / S2 / S3 各自一个或多个线性 commit，例如：
  * `feat(diagnostics): S1 models, errors, constants and architecture guards (P4-C9)`
  * `feat(diagnostics): S2 read-only projection of preview/execution results (P4-C9)`
  * `feat(diagnostics): S3 deterministic redacted JSON rendering, gates and HANDOFF (P4-C9)`
* 不要求每个 S 的 docs closure；不要求每个 S 的独立 Review。
* 最终只有一个 C9 Review Range：`<Design-Accepted Head>..<C9 Implementation Head>`。
* 禁止 rebase / amend / squash / force push；禁止改写已 Review 的 design commit。
* Design Review PASS 后**不**创建“E0 closure / design accepted”之类的纯状态 docs commit：Review PASS 本身建立 Design Accepted
  Head，实现直接在本分支继续（治理文档第 11.1 节）。

## 7. 测试矩阵 -> 文件映射（冻结）

| 合同要求 | 测试文件 |
|---|---|
| 模型校验（第 11 节） | `test_diagnostics_models.py` |
| 精确公开 API / 常量 / 枚举快照（第 8、23 节） | `test_diagnostics_public_api.py`、`test_diagnostics_architecture.py` |
| 错误（第 8.4、24 节） | `test_diagnostics_errors.py`、`test_diagnostics_input_integrity.py` |
| preview 诊断 | `test_diagnostics_preview.py`、`test_diagnostics_integration.py` |
| execution 诊断 / failure / retry 映射 | `test_diagnostics_execution.py`、`test_diagnostics_integration.py` |
| source 诊断（来源级日志） | `test_diagnostics_sources.py` |
| field provenance（字段来源追踪） | `test_diagnostics_provenance.py` |
| issues / warnings | `test_diagnostics_preview.py`、`test_diagnostics_execution.py` |
| ordering + ordering non-vacuity | `test_diagnostics_determinism.py` |
| determinism + 临时身份排除 | `test_diagnostics_determinism.py`、`test_diagnostics_scale_gate.py` |
| redaction + 路径策略 + canary non-vacuity | `test_diagnostics_redaction.py` |
| JSON / schema | `test_diagnostics_render.py` |
| 计时策略 | `test_diagnostics_timing.py` |
| resource / output limits | `test_diagnostics_resources.py`、`test_diagnostics_scale_gate.py` |
| invalid / tampered / fail closed | `test_diagnostics_input_integrity.py`、`test_diagnostics_render.py`、`test_diagnostics_mutations.py` |
| no side effect + non-vacuity | `test_diagnostics_no_side_effects.py`、`test_diagnostics_integration.py` |
| architecture（module set、API set、private imports、no network / write / persistence / Amane / ownership / thread / registry、反向依赖） | `tests/contract/test_diagnostics_architecture.py` + 第 27.3 节七处守卫 |
| integration 场景（SUCCESS / PARTIAL / FAILED batch、BLOCKED、UNPREPARED、ABORTED、metadata failure / partial、image warnings、execution PARTIAL / FAILED、RESUME、FRESH_REEXECUTE、METADATA_REFETCH、PREFLIGHT_RECHECK、DEFERRED、NONE） | `test_diagnostics_integration.py` |
| 500-item 诊断门槛 + MAX 边界 | `test_diagnostics_scale_gate.py` |

不得用 skip 绕过 Windows、脱敏、确定性、资源、架构或其它核心测试。P4-C9 不需要重新执行 P4-C8 的真实文件系统 500-item
门槛（它已在 P4-C8 S6 验收）；P4-C9 的规模门槛是逻辑条目的诊断投影门槛。

## 8. Evidence Gate 与 HANDOFF（冻结）

`docs/review/P4_C9_HANDOFF.md`（S3 新增，中文）必须包含：

1. 坐标：Package Frozen Base `a662659…`、Governance Authority / Planning Parent `3b9d39e…`、Design Candidate、Design Accepted
   Head、C9 Implementation Head（Code Review Candidate）、Review Range；
2. 完整 diff scope（`git diff --stat` 与按第 5 节规则的逐项核对，含 `-- fc2-organizer/src` 只含 diagnostics 的证明）；
3. Contract -> implementation -> test 映射（合同每个编号节 -> 生产位置 -> 测试用例）；
4. 测试数字（Windows 11 / Python 3.12.x；命令 `python -m pytest -q -p no:cacheprovider --basetemp=<job tmp>`，在 `fc2-organizer/` 下）：
   * P4-C9 专项：`tests/unit/diagnostics` + `tests/contract/test_diagnostics_architecture.py`；
   * targeted organizer：`tests/unit/orchestration` + `tests/contract`；
   * contract：`tests/contract`；
   * full suite：passed 不低于 **6178**、skipped 恒为 **40**（新增 skip = NONE），collected = passed + skipped；
   若 Design Review 前 accepted parent 的基线合法变化，以实际 accepted parent 重新记录；
5. mutation / non-vacuity 表（合同第 28.5 节每一类：变异、文件、杀死机制、失败用例、失败数；每个变异未提交、撤销后以
   `git hash-object --no-filters` 与 HEAD blob 比对逐字节恢复）；
6. 脱敏证据：canary 清单与扫描结果；
7. 确定性证据：重复 / 反转 / 临时身份替换后的逐字节比较结果；
8. 资源证据：结构上限与输出上限边界结果、2000 条输出大小与耗时；
9. 无副作用证据：文件系统快照、fake 调用计数、被禁止 API 列表；
10. 风险升级门核对（A-K 逐项“未触发”或处理记录）；`BLOCKED DESIGN ISSUE`：NONE（或记录）；
11. evidence gaps（例如 POSIX 原生 basename 行为若未在 POSIX 主机运行）与 known limitations（合同第 31 节）；
12. 如实记录任何瞬时失败及重跑结果（与 P4-C8 HANDOFF 相同标准）。

`git diff --check <Design-Accepted Head> HEAD` 必须干净；`git status --porcelain` 必须为空（仓库既有约定的未跟踪 `.claude/` 除外）。

## 9. Independent Review Plan

```text
1. P4-C9 INDEPENDENT DESIGN / CONTRACT / PLAN REVIEW（本 design candidate commit）
     PASS -> Contract 与本计划成为 Frozen Authority；该 Review 的 head 即 Design Accepted Head
     FAIL -> 设计修订（authority docs），再次独立复查
2. S1 -> S2 -> S3 连续施工（不单独 Review）
3. P4-C9 Independent Level 1 Review（Review Range = Design Accepted Head .. C9 Implementation Head）
     PASS -> Final Closure（状态 docs 与 Final Closure 合并）
     FAIL -> 同根因 / 范围明确的 findings 统一进入 C9-R1；需要 Contract amendment、Plan scope amendment、新安全设计或新公开 API
             裁决的 findings 先解决 authority（治理文档第 12.2 节）
```

Per-S Independent Review：**NO**。C-Level Independent Review：**YES**。Design Authority Review Required：**YES**。

## 10. 状态

```text
P4-C8                         : CLOSED
Acceleration Governance v2    : ACCEPTED / CLOSED
P4-C9 Frozen Base             : a662659dfd6e801531b14af7913d84a5f9f859e2
Governance Authority          : 3b9d39e9adbcc8a009707486eebbb8736a5b1c4d
P4-C9 Design                  : IMPLEMENTED — INDEPENDENT DESIGN REVIEW REQUIRED
P4-C9 Frozen Contract         : NOT YET ACCEPTED
P4-C9 Construction Plan       : NOT YET ACCEPTED
S1                            : NOT STARTED
S2                            : NOT STARTED
S3                            : NOT STARTED
P4-C9 Production              : NOT STARTED
P4-C9 Independent L1 Review   : NOT STARTED
P4-C10                        : NOT STARTED
Phase 4                       : NOT CLOSED
```

本 design commit 之后 **STOP**：不开始 S1、不写 production、不写 tests、不规划 P4-C10，等待 P4-C9 INDEPENDENT DESIGN /
CONTRACT / PLAN REVIEW。

## 11. Owner Question Gate

```text
Owner Question Gate : BUSINESS DECISIONS ONLY
需要外部业务决策     : NONE
未解决技术决策       : NONE
```

class 名、文件拆分、fixture、JSON key 命名、测试 helper、fail-closed 默认等均已由设计者裁决并记录于合同附录 A；实施中同类细节
按本计划开头的优先级自行裁决，不询问 Owner。
