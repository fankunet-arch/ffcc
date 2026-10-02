# FC2 Organizer -- Phase 4 / P4-C9 结构化诊断合同（Diagnostics Contract）

```text
文档状态                         ：DESIGN-R3 CANDIDATE — IMPLEMENTATION NOT STARTED
P4-C9 Design                     ：DESIGN-R3 IMPLEMENTED — INDEPENDENT DESIGN REVIEW REQUIRED
P4-C9 Frozen Contract            ：NOT YET ACCEPTED
P4-C9 Design Accepted Head       ：NOT ESTABLISHED
Implementation Input             ：NOT ESTABLISHED
P4-C9 Production Implementation  ：NOT STARTED
Package                          ：fc2_organizer.diagnostics（新顶层 package，S1 起创建）
Package Frozen Base              ：a662659dfd6e801531b14af7913d84a5f9f859e2（P4-C8 Final Closure Docs Head）
Governance Authority             ：docs/PROJECT_GOVERNANCE_ACCELERATION.md @ 3b9d39e9adbcc8a009707486eebbb8736a5b1c4d
                                   （Final Reviewed Governance Head / Project Governance Authority Head）
Planning Parent                  ：3b9d39e9adbcc8a009707486eebbb8736a5b1c4d
Original Design Candidate        ：b5e98314eb64101b9da3b8c12a52c9044d73a60d（Original Design Review：FAIL）
Design-R1 Candidate              ：ea32b37bab4c3440b83254466193212ae4be5ba8（Design-R1 Review：FAIL）
Design-R2 Candidate              ：00e5be38e7232e6dc34f3c194472e58470ceadd0（Design-R2 Review：FAIL；亦为 Design-R3 Parent）
Branch                           ：claude/phase4-c9-diagnostics
Governance Mode                  ：ACCELERATED v2
Risk Class                       ：B（第 5 节；受第 5.3 节风险升级门约束）
Python Runtime Authority         ：Python >= 3.11（项目既有 `requires-python`，本合同不改变；第 7 节）
施工计划                         ：docs/P4_C9_CONSTRUCTION_PLAN.md（S1 / S2 / S3，连续施工）
```

本合同一次性冻结 P4-C9 的全部规范语义。本文件经独立 DESIGN / CONTRACT / PLAN Review PASS 后成为 Frozen Contract；
S1-S3 只能**执行**本合同，不得重新设计。S1 / S2 / S3 施工期间**不修改**本文件（包括第 32 节状态行；不创建任何 S 级状态
docs commit）；第 32 节只允许在整个 C9 implementation 完成后、随 HANDOFF / Final Closure 同步状态行。任何语义改动（含公开
API、schema、脱敏、路径策略、输入校验、资源上限、风险边界）都属于 authority docs 改动（治理文档第 11.2 节），必须作为独立
修订轮次提出并经独立复查，不得在实现 commit 中夹带。

坐标说明（冻结，治理文档第 19 节）：

* **Package Frozen Base** 是 P4-C9 的 package baseline，保持 `a662659dfd6e801531b14af7913d84a5f9f859e2`；
* **Governance Authority / Planning Parent** 是 `3b9d39e9adbcc8a009707486eebbb8736a5b1c4d`，是 P4-C9 工作分支的起点，
  **不是** P4-C9 Frozen Base；两者之间只有治理文档提交，没有任何 production / test 改动。

基线状态：

```text
P4-C1 .. P4-C8                   : CLOSED（本合同不修改其中任何一个的生产代码、合同、施工计划或 HANDOFF）
Acceleration Governance v2       : ACCEPTED / CLOSED
P4-C9                            : DESIGN-R3 CANDIDATE；Implementation NOT STARTED
P4-C10                           : NOT STARTED
Phase 4                          : NOT CLOSED
```

### 设计复查与修订记录

| 轮次 | 内容 | 状态 |
|---|---|---|
| Original Design Candidate | `b5e98314eb64101b9da3b8c12a52c9044d73a60d` | Original Design Review：**FAIL** |
| P4-C9-DESIGN-R-01（HIGH / BLOCKING） | 原第 24.3 节授权调用上游 `__post_init__`，与“禁止一切上游 `_` 开头访问”互斥 | **CLOSED**（Design-R1 Review 确认；本轮语义 0 回归） |
| P4-C9-DESIGN-R-02（HIGH / BLOCKING） | 被篡改 / 调用方子类对象可经 P4-C9 对调用方来源容器的分派（`__hash__` / `__eq__` / 容器成员判定 / 多态 property）执行调用方代码；根因：caller-originated 对象在 exact-type 校验完成之前就进入了可能触发分派的操作 | Design-R1 Review：OPEN；Design-R2 Review：OPEN（以 R2-01 为同根因的 public-constructor-reachable 具体实例）；Design-R3：REMEDIATED — INDEPENDENT DESIGN REVIEW REQUIRED |
| P4-C9-DESIGN-R-03（HIGH / BLOCKING） | 被消费对象校验不完整；剩余缺口为 `RetryMaterial` 图一致性与 retained payload / retention budget 关系 | **CLOSED**（Design-R2 Review 确认；本轮语义 0 回归） |
| P4-C9-DESIGN-R-04（HIGH / BLOCKING） | 默认 `PathPolicy.BASENAME` 与绝对脱敏承诺矛盾 | **CLOSED**（Design-R1 Review 确认；本轮语义 0 回归） |
| P4-C9-DESIGN-R-05（MEDIUM / BLOCKING） | 最终 `__all__` 与逐阶段 API 冲突 | **CLOSED**（Design-R1 Review 确认；本轮语义 0 回归） |
| Design-R1 Candidate | `ea32b37bab4c3440b83254466193212ae4be5ba8` | Design-R1 Review：**FAIL** |
| P4-C9-DESIGN-R1-01（HIGH / BLOCKING） | Design-R1 把 `gc.get_referents` 作为 production 校验原语；它是专门的对象图反射 / 审计原语 | **CLOSED**（Design-R2 Review 确认；本轮语义 0 回归） |
| P4-C9-DESIGN-R1-02（HIGH / BLOCKING） | Design-R1 引入对 CPython 3.12 `mappingproxy` referent 形态的规范性依赖，收窄了项目 `>=3.11` 的运行时权威 | **CLOSED**（Design-R2 Review 确认；本轮语义 0 回归） |
| Design-R2 Candidate | `00e5be38e7232e6dc34f3c194472e58470ceadd0` | Design-R2 Review：**FAIL** |
| P4-C9-DESIGN-R2-01（HIGH / BLOCKING） | Design-R2 的 `field_sources` 访问规则（只按固定 known 字段名 `name in proxy` / `proxy[name]` 查询、“不迭代”）在 stored key 尚未验证为 exact `str` 时就触发 hash-dependent lookup；上游 `NormalizedMetadata` 构造器以 `isinstance(key, str)` 接受 `str` 子类 key 并原样写入新建 exact `dict`，因此 `str` 子类 key 可经正常 public constructor 进入 supported public model graph（第 9.0 节 A / B 层，**不是** C 层），固定 exact-`str` 查询会对其执行子类 `__eq__` | Design-R3：REMEDIATED — INDEPENDENT DESIGN REVIEW REQUIRED |

Design-R2 闭合方式（历史摘要；R-03 / R1-01 / R1-02 已由 Design-R2 Review 确认 CLOSED，规范正文以各节为准）：

* **R1-01 / R1-02（统一）**：删除 `gc.get_referents`、`gc` 标准库许可、Mapping-Proxy Unwrap Rule、“恰一个 referent”“被包装 mapping”
  “CPython 3.12 已验证”等全部规范性假设及其对应的架构例外、测试要求与已知局限。P4-C9 production 不 import `gc`，不 introspect
  任何不透明标准库容器的内部；也不以 `inspect` / `ctypes` / `sys._*` / `pickle` / `marshal` / `copyreg` / `weakref` 内部 / 对象布局 /
  `id` 地址运算 / 帧检查等任何替代手段去窥探。`validation.py` 保留（删除 `gc` 依赖）。运行时权威保持 `Python >= 3.11`，不改变
  `pyproject.toml`。
* **R-02（Design-R2 方案；已被 Design-R3 修订，见下）**：新增第 9.0 节 **Input Trust / Tamper Boundary**，把输入校验声明精确收窄到项目真正支持的 public model 边界：A. supported
  public model graph（正式输入权威）；B. detectable structural tampering（按 Validation Map fail closed）；C. opaque implementation
  forging（不使用反射去识别，不属于 supported input graph；这**不是**任意输入信任，也不降低 A / B 的 fail-closed 要求）。“零调用方
  钩子”语义改为可证明的精确陈述（第 5.1、9.0、19 节）。普通嵌套模型的恶意子类 sentinel 测试保留；仅把“`MappingProxyType` 包装恶意
  `dict` 子类”这一不可实现的测试权威移除，替换为上游信任边界测试（第 28.1 节）。
* **R-03**：补齐 `RetryMaterial` 的完整本地校验（新增 M-30）与 `ItemExecution.retry_material` / `retry_kind` 的冻结关系（第 9.6.4
  节），并在读取 `summary` / `outcome` 之前**本地计算** retained payload 字节并校验其与 `retention_budget_bytes` /
  `retry_budget_bytes` 的冻结关系（第 9.6.1、9.6.2 节）；`retry_kind` 先由已校验公开字段本地推导，再与批准的 property 返回值比较。
* **未改动**：R-01（无上游 `__post_init__`、无 private / dunder 例外）、R-04（默认 `NONE`、`BASENAME` 显式 opt-in、词法安全）、R-05
  （阶段化模块集合与 `__all__`、无 stub）语义；`retry_scope` 在 `RETRY` 形态下可以为空（LEGAL）；Risk Class B；风险升级门 A-K；
  目的；无持久化 / 无写文件 / 无网络；bytes 序列化；schema 1.0；排序；资源上限；64 MiB 输出上限；P2-R-07；500-item 门槛；MAX 门槛；
  全量门槛；P4-C8 CLOSED 边界。

**Design-R3 闭合方式（DISPATCH-SAFETY CLOSURE；一次闭合 R-02 + R2-01）**：

* **统一原则：VALIDATE BEFORE DISPATCH**（新增第 9.0.1 节，冻结）：任何可能执行 `__hash__` / `__eq__` / 富比较 / 容器成员判定 /
  多态 property 或方法的操作，必须在相关 caller-originated 对象完成 exact-type 校验**之后**才能发生；容器遵守“Phase V（全部
  元素 / key 的 exact-type 校验）先于 Phase R（成员判定 / 相等 / 查表 / 唯一性）”。本原则不只用于 `field_sources`，第 9.10 节
  Caller-Originated Operation / Dispatch Safety Matrix 与第 9.11 节 Horizontal Dispatch Audit 对 P4-C9 实际执行的全部此类操作逐项
  裁定。
* **R2-01 / `field_sources`**：第 9.2 节第 9 条与 M-18 改为 **BOUNDED ONE-PASS KEY SCAN → EXACT KEY VALIDATION → FIXED KNOWN-KEY
  LOOKUP**：先确认 `type(metadata) is NormalizedMetadata` 与 `type(field_sources) is MappingProxyType`；再对 stored key 做**单遍有界**
  扫描（计数、超过冻结的 `MAX_PROVENANCE_KEYS` 立即 `DiagnosticsResourceLimitError`、在任何成员判定 / 下标 / 相等 / hash 敏感操作之前逐个
  确认 `type(key) is str`）；仅在全部 stored key 扫描并 exact-type PASS 之后，才按 `PROVENANCE_FIELD_ORDER` 做固定 known 字段查询。
  Design-R2 的“禁止迭代 proxy”过宽禁令被删除：迭代仅用于 validation，输出顺序仍完全由 `PROVENANCE_FIELD_ORDER` 决定。未知 exact-`str`
  key 不投影、不输出、不参与 field provenance，但计入资源上限与 key 扫描。
* **`MAX_PROVENANCE_KEYS = 64`**（内部常量，第 8.3 节；理由见该节）。
* **Layer C 保持窄边界**：不透明 `mappingproxy` 隐藏 referent 被 invariant-bypass 替换成 hostile mapping 仍属 C 层，P4-C9 不使用 introspection
  识别；但**公开构造器可产生的** `str` 子类 key 明确不是 C 层。
* **上游 authority 证据**：涉及“上游 public constructor 接受 / 拒绝什么”的断言一律引用稳定 symbol + frozen upstream SHA / package
  authority（第 9.0 节），源码行号只作为 review evidence；施工计划新增 characterization tests 固定这些事实。
* **未改动**：R-01、R-03、R-04、R-05、R1-01、R1-02 语义；public diagnostics schema、`PathPolicy`、`RetryMaterial`、资源模型（除 provenance
  key 上界外）、序列化、S1 / S2 / S3 边界；无上游 production 改动。

**Design-R3 的 Risk Class 裁决**：仍为 **B**。Design-R3 只是为既有本地校验补全 dispatch-safety 证明与一个有界 key 扫描：没有引入持久化、
文件写入、网络、新的 security boundary、新的并发所有权、不可逆迁移，也没有对 CLOSED package 的任何 production 语义修改（风险升级门
A-K 均未触发）。

（Design-R2 的 Risk Class 裁决历史记录：仍为 B；其删除 introspection 假设、收窄输入校验声明的动作同样未触发 A-K。）

---

## 1. 目的与用户能力（冻结）

P4-C9 交付一个完整的纵向能力 **Diagnostics**：

```text
既有 FC2 Organizer / Metadata / Batch / Orchestration 已经产生的、内存中的结构化运行结果
    （BatchPreview / BatchExecutionResult 及其公开可达的下层模型）
        -> 本地只读校验（Local Validation，第 9 节）
        -> 只读、确定性、可审计的投影（projection）
        -> 不可变诊断模型 BatchDiagnostics（batch / item / stage / source / field provenance / failure / retry）
        -> 安全脱敏（redaction）与路径策略（默认 NONE）
        -> 确定性的 JSON 序列化结果（ASCII-only UTF-8 bytes）
```

目标是让用户、后续 Adapter（Phase 5）或 UI 无需读取私有运行状态、无需解析 Python 异常 repr、无需重新运行批次、
无需重新访问网络，就能回答：

| 问题 | 回答所用的诊断字段（第 11 节） |
|---|---|
| 这批任务发生了什么？ | `BatchDiagnostics.kind / shape / generation / preview_summary / execution_summary / outcome / metadata_batch` |
| 哪一项在哪个阶段失败？ | `ItemDiagnostics.index / canonical_number / issue.stage / issue.reason` |
| 为什么失败？ | `issue.reason / issue.error_type / issue.detail`；`execution.failure`（step / kind / stage / errno …）；`preflight.blockers` |
| 哪个 source 提供了哪些字段？ | `metadata.field_provenance`、`SourceDiagnostics.provided_fields` |
| 哪些 source 失败？ | `SourceDiagnostics.status / error_kind / operational_failure / attempts` |
| 出现了哪些 warning？ | `ItemDiagnostics.warnings`、`image_failures` |
| 该项能不能 retry？应该使用哪种 RetryKind？ | `ItemDiagnostics.retry_kind`（P4-C8 冻结的派生值，原样携带） |
| filesystem execution 最终发生了什么？ | `ItemDiagnostics.disposition`、`execution.status / effect_counts / failure / leftover_temporaries / checkpoint_present` |

## 2. 与 v1.0 P0 的关系（冻结）

P4-C9 是 v1.0 规格书 P0 条目“来源级日志、字段来源追踪”的落地，并为以下 P0 条目提供可审计的诊断视图：

| v1.0 P0 条目（`docs/specifications/FC2_Organizer_v1.0_开发规格书.md`） | P4-C9 的对应 |
|---|---|
| 来源级日志 | 第 11.6 / 11.7 节 `SourceDiagnostics` / `SourceAttemptDiagnostics`：每个 source 的最终状态、结构化失败 kind、每次 attempt、deadline、是否参与聚合 |
| 字段来源追踪 | 第 11.8 节 `FieldProvenance`：只取 Phase 3 聚合已经产生的 `NormalizedMetadata.field_sources` |
| 批量状态（`SUCCESS | PARTIAL | FAILED`） | `BatchDiagnostics.outcome`（P4-C8 `BatchOutcome` 原样携带）与冻结 summary |
| 任务隔离与失败子集重试 / 失败项独立重试 | `ItemDiagnostics.retry_kind`、`execution_summary.retryable / deferred / non_retryable` |
| 安全失败、无静默覆盖 | `disposition`、`execution.failure`、`leftover_temporaries`、`checkpoint_present` 的如实呈现；诊断本身零副作用（第 26 节） |

P4-C9 **不是**通用日志框架，**不是** telemetry 平台，**不是**长期任务数据库；它是 FC2 Organizer v1.0 的结构化
diagnostics capability。规格书中的 `PENDING -> RUNNING` 是实时状态，P4-C8 第 11.4 节已冻结“不提供实时状态”，
P4-C9 同样只做事后（post-hoc）诊断。

## 3. 范围（冻结）

* 新顶层 package `src/fc2_organizer/diagnostics/`（模块集合见第 6 节）。
* 两个只读 builder：`build_preview_diagnostics`、`build_execution_diagnostics`；一个序列化函数
  `render_diagnostics_json`。
* 本地只读输入校验（第 9 节）、不可变诊断模型、诊断错误层次、常量。
* 来源级诊断、字段出处、条目诊断、批级诊断、脱敏、路径策略、确定性、资源与输出上界。
* 测试：unit、architecture、integration、本地校验 / 篡改 / 恶意子类门槛、500-item 诊断投影门槛、MAX 边界、非空洞性
  （mutation / canary）。
* 对既有架构守卫的最小授权更新（第 27.3 节，精确列举）。

## 4. 非目标（冻结）

* 不写文件：不自动落盘 JSON，不提供 `path` / `file` 参数，不创建目录，不做 archive。
* 不做 durable persistence：没有 SQLite、shelve、dbm、pickle、marshal、任务数据库、resume store、历史运行档案。
* 不做 live logging：不调用 `logging` / `print`，不注册 handler，不修改全局 logger，不向 P4-C8 执行路径插入钩子。
* 不访问网络，不重新获取 metadata / 图片，不重新运行 preview / execute / retry / preflight。
* 不重新实现 metadata aggregation、RetryKind 判定、summary 计数或 BatchOutcome 判定；全部原样携带 P4-C8 / Phase 3 的
  冻结结果（第 9 节的本地校验只**检查**上游已冻结的不变量，不产生任何新的业务结果）。
* 不提供实时进度 / 事件流 / 回调。
* 不设计 P4-C10、Phase 5 Amane Adapter 或任何 UI。
* 不修改任何已 CLOSED package 的生产代码。

## 5. 治理（冻结）

### 5.1 Risk Class = B

依据：治理文档第 8.2 节明确把 diagnostics 列为 B 类（中风险）。只有在满足本合同冻结的安全边界——零持久化、零文件
写入、零网络、零副作用、只读消费公开模型、遵守 validate-before-dispatch（第 9.0.1 节：任何可能分派到调用方代码的操作都在相关对象
exact-type 校验之后才发生）、不主动调用输入对象的任何多态实例方法 / 回调（第 9.0 节精确语义）、不使用任何反射 / 内省原语、不改变任何
CLOSED package 语义、严格脱敏——时，P4-C9 才保持 B 类。

### 5.2 内部施工与 Review

* 内部 S1 / S2 / S3 连续施工（施工计划第 4 节），S1、S2、S3 均**不**单独 Review、**不**做中间 docs closure。
* 本合同 / 施工计划需要独立 DESIGN / AUTHORITY REVIEW（因为实现建立在新的 Frozen Contract 上，治理文档第 9 节第 2 条）；
  Original Design Review、Design-R1 Review 与 Design-R2 Review 均为 FAIL；Design-R3 之后需要 P4-C9 DESIGN-R3 INCREMENTAL DESIGN /
  CONTRACT / PLAN CLOSURE REVIEW。该 Review PASS 本身建立 Design Accepted Head，不再创建 design closure docs。
* 整个 C9 实现完成后统一一次 **P4-C9 Independent Level 1 Review**；FAIL 时同根因 / 范围明确的 findings 统一进入 C9-R1
  （治理文档第 12 节）。

### 5.3 风险升级门（Risk Escalation Gate，冻结）

施工中出现以下任何一项，必须**立即停止**正常 B 类施工，重新评估为 C 类，并按治理文档第 8.3 节处理（独立安全 Review、
必要时拆分）：

| # | 触发项 |
|---|---|
| A | durable persistence |
| B | diagnostic 数据自动落盘、形成长期记录 |
| C | 敏感信息落盘 |
| D | 修改用户媒体文件 |
| E | 修改 / 删除 / 移动现有 artifact |
| F | 引入 source-loss 风险 |
| G | cross-process locking |
| H | 新的 race / concurrency ownership |
| I | 不可逆 schema migration |
| J | 新的 security boundary |
| K | 需要改变已 CLOSED 的 P4-C8（或任何其它 CLOSED package）的 production semantics |

本清单**不穷尽**：任何其它实际达到治理文档第 8.3 节 C 类定义的风险同样必须升级。不得以“P4-C9 默认 B 类”覆盖真实 C 类
风险；没有治理依据不得降级。

### 5.4 P4-C8 CLOSED 边界与 BLOCKED DESIGN ISSUE 审计结论（冻结）

* P4-C9 是 **observer / projector，不是 controller**：只消费 P4-C8 已返回的公开模型（第 9 节），不修改
  `src/fc2_organizer/orchestration/**`，也不修改任何其它 CLOSED package 的 `src/**`。
* 设计阶段逐项审计了第 1 节问题表所需的全部 evidence：它们全部可经 `fc2_organizer.orchestration` 及其公开可达的下层公开
  模型的公开字段读取（第 9.5 节）。P4-C8 的 `models.revalidate` 与各上游 `__post_init__` **不**被使用；完整性由 P4-C9 自己的
  本地校验（第 9 节）保证，**不需要**修改 P4-C8。
* 审计结论：**不存在 BLOCKED DESIGN ISSUE**；P4-C9 不授权、也不需要任何 CLOSED package 生产语义改动。
* 若实施中发现某项必要诊断必须修改 CLOSED package 生产语义才能交付：不得自行授权、不得夹带；必须在施工计划 / HANDOFF
  记录 `BLOCKED DESIGN ISSUE` 并 STOP（风险升级门第 K 项）。

---

## 6. 包边界与模块划分（冻结，阶段化）

```text
src/fc2_organizer/diagnostics/
    __init__.py      公开 API 汇总（只从本 package 模块 re-export；__all__ 精确等于第 8.1 节对应阶段集合）
    errors.py        错误层次（只 import __future__）
    models.py        常量、诊断枚举、不可变诊断模型、诊断模型的本地校验函数
    validation.py    输入的本地只读校验（第 9 节）：Consumed-Object Validation Map、跨对象检查、安全值检查、校验快照
    projection.py    单条目投影：校验快照 -> 诊断模型（路径策略、计时策略）
    build.py         两个公开 builder：第 24.2 节检查顺序的编排
    render.py        render_diagnostics_json：诊断图本地重检 -> 纯 JSON 树 -> 有界流式编码 -> bytes
```

模块集合按阶段精确冻结（无子目录）：

| 阶段 | 模块集合（精确） |
|---|---|
| S1 | `{__init__.py, errors.py, models.py}` |
| S2 | `{__init__.py, errors.py, models.py, validation.py, projection.py, build.py}` |
| S3（最终） | `{__init__.py, errors.py, models.py, validation.py, projection.py, build.py, render.py}` |

任何阶段都不得创建尚未授权的模块、stub、placeholder function 或假模块。

## 7. 依赖方向与 import 策略（冻结）

```text
fc2_organizer.diagnostics
    |-- fc2_organizer.orchestration     （裸公开 package：第 8.5 节列出的名称）
    |-- fc2_organizer.execution         （裸公开 package：模型与枚举类型）
    |-- fc2_organizer.images            （裸公开 package：ImageCandidateFailure、ImageRole、ImageFailureKind、ImageAcquisitionPolicy）
    |-- fc2_organizer.materialization   （裸公开 package：ArtifactKind、ArtifactWriteRequest、MappingRejectionReason）
    |-- fc2_organizer.discovery         （裸公开 package：DiscoveredMediaItem）
    |-- fc2_organizer.planning          （裸公开 package：OrganizePlan、PlannedPath、PlannedOperation、PlannedOperationKind、OutputPolicy）
    |-- fc2_metadata_core.batch         （裸公开 package：BatchResult、BatchItemResult、BatchItemStatus、BatchItemErrorKind、BatchLineage）
    |-- fc2_metadata_core.aggregation   （裸公开 package：AggregationResult、AggregateStatus、SourceExecutionTrace、SourceAttempt、
    |                                     FieldConflict、OPERATIONAL_FAILURE_STATUSES、CONFLICT_FIELDS、RETRY_ELIGIBLE_KINDS）
    |-- fc2_metadata_core.models        （裸公开 package：SourceResult、SourceStatus、SourceErrorKind、NormalizedMetadata）
    |-- fc2_metadata_core.normalize     （裸公开 package：is_valid_fc2_number）
    '-- 标准库（逐模块限定，见下）
```

* 只允许 `from <裸公开 package> import <第 8.5 节允许名称>`；不允许 import 任何子模块（例如
  `fc2_organizer.orchestration.models`、`fc2_metadata_core.aggregation.policy`、`fc2_organizer.execution._fs`、
  `fc2_organizer.images.acquisition`、`fc2_organizer.materialization.mapping`），不允许 import 以 `_` 开头的名称，
  不允许把 package 模块对象本身 import 进来再做属性访问。
* 逐模块标准库允许清单（AST 强制）：

| 模块 | 允许的标准库（及其唯一允许的成员） |
|---|---|
| `errors.py` | `__future__` |
| `models.py` | `__future__`、`dataclasses`、`enum`、`re` |
| `validation.py` | `__future__`、`re`、`math`（只 `math.isfinite`）、`os`（只 `os.path.isabs`、`os.path.join`、`os.path.basename`、`os.sep`、`os.altsep`）、`types`（只 `types.MappingProxyType`，仅用于 `type(x) is MappingProxyType` 精确类型比较） |
| `projection.py` | `__future__` |
| `build.py` | `__future__` |
| `render.py` | `__future__`、`json`（只 `json.JSONEncoder`） |
| `__init__.py` | 无（只 import 本 package 模块） |

* **生产代码禁止 import / 引用**（静态 AST + 运行时）：`amane`、`httpx`、`requests`、`socket`、`ssl`、`urllib`、`http`、
  `pickle`、`marshal`、`shelve`、`dbm`、`sqlite3`、`csv`、`logging`、`tempfile`、`shutil`、`glob`、`fnmatch`、`pathlib`、`io`、
  `subprocess`、`multiprocessing`、`concurrent`、`threading`、`asyncio`、`ctypes`、`time`、`datetime`、`random`、`secrets`、
  `uuid`、`hashlib`、`hmac`、`traceback`、`inspect`、`sys`、`builtins`、`copy`、`unicodedata`；任何 source adapter
  （`fc2_metadata_core.sources`）、`fc2_metadata_core.http`、`fc2_metadata_core.resource_control`；`json` 只在 `render.py`。
* **No New Introspection（冻结，Design-R2）**：生产代码**不得** import 或使用 `gc`、`inspect`、`ctypes`、`sys`（含 `sys._*`、
  `sys.audit` 与帧函数）、`pickle`、`marshal`、`copyreg`、`weakref`、`traceback`、`builtins`、`copy`，也不得使用对象布局、
  `id` / 地址运算、帧检查、C 扩展技巧或任何其它专门的反射 / 对象图遍历 / 审计原语，来窥探不透明标准库容器（例如
  `MappingProxyType`）的内部。P4-C9 不注册 audit hook、callback、logger hook。若发现不使用这类 introspection 就无法兑现某项
  诊断能力：不得继续叠加 hack，必须在 HANDOFF 中报告 `BLOCKED DESIGN ISSUE` 并 STOP（风险升级门第 J / K 项评估）。
* **Python Runtime Authority（冻结，Design-R2）**：P4-C9 的运行时支持边界是项目既有的 `Python >= 3.11`（`pyproject.toml`
  `requires-python = ">=3.11"`，本合同与 P4-C9 实现**不得**修改它，也不得把支持边界收窄为 CPython-only、CPython 3.12 或 Python
  3.12.x only）。P4-C9 只依赖 Python >= 3.11 的标准公开 API 与项目既有 public model contracts，不产生任何 implementation-specific
  的运行时限制。“Windows 11 / Python 3.12.x”只是 P4-C9 的**验收证据环境**（第 28.7 节、HANDOFF），不等于包的运行时支持边界。
* 禁止的调用 / 访问（AST 强制）：`open`、`print`、`exec`、`eval`、`compile`、`__import__`、`getattr`、`hasattr`、`setattr`、
  `delattr`、`vars`、`dir`、`id`、`hash`、`repr`、`format`、`isinstance`、`issubclass`、`super`、`sorted`、`min`、`max`（P4-C9 不对 caller-originated 值做排序 / 极值比较；
  所有顺序都来自冻结常量的声明顺序，第 9.10 节 D-20）；任何属性名以 `_` 开头的属性
  访问或调用（包括全部 dunder，例如 `__post_init__`、`__dict__`、`__class__`、`__eq__`；`object.__setattr__` 也不例外——
  诊断模型的不可变赋值只使用 dataclass 生成的构造函数）；对异常或任何非 `str` 输入值调用 `str()`；在 f-string / `%` /
  `str.format` 中插入任何输入值；第 9.2 节允许操作之外对输入对象的任何方法调用。
* 没有反向依赖：`src` 下任何其它模块都不 import `fc2_organizer.diagnostics`；`fc2_organizer/__init__.py` 不 import 它；
  裸 `import fc2_organizer` 不加载它。
* 传递加载说明（已冻结的上游事实，不是 P4-C9 的直接依赖）：import `fc2_organizer.orchestration` 会经由 P4-C8 传递加载
  `fc2_organizer.images.acquisition`，进而加载 `httpx`（P4-C8 合同第 6 节）。P4-C9 源码从不**引用** `httpx` 或任何网络
  客户端，从不构造 client；架构测试以静态扫描证明这一点，并以运行时 fake 证明诊断过程中没有任何网络 / 文件系统调用
  （第 26 节）。

---

## 8. 公开 API（冻结）

### 8.1 `fc2_organizer.diagnostics.__all__`（阶段化精确集合与顺序）

**S3 / 最终集合**（S3 起直至 C9 final implementation 一直使用）：

```python
__all__ = [
    # builders / renderer
    "build_preview_diagnostics",
    "build_execution_diagnostics",
    "render_diagnostics_json",
    # enums
    "DiagnosticsKind",
    "ResultShape",
    "PathPolicy",
    "TimingPolicy",
    # models
    "BatchDiagnostics",
    "MetadataBatchCounts",
    "ItemDiagnostics",
    "IssueDiagnostics",
    "MetadataDiagnostics",
    "SourceDiagnostics",
    "SourceAttemptDiagnostics",
    "FieldProvenance",
    "FieldConflictDiagnostics",
    "ImageFailureGroup",
    "PreflightDiagnostics",
    "ExecutionDiagnostics",
    "LeftoverTemporaryDiagnostics",
    # constants
    "DIAGNOSTICS_SCHEMA",
    "DIAGNOSTICS_SCHEMA_VERSION",
    "PROVENANCE_FIELD_ORDER",
    "MAX_DIAGNOSTIC_ITEMS",
    "MAX_SOURCES_PER_ITEM",
    "MAX_ATTEMPTS_PER_SOURCE",
    "MAX_BLOCKERS_PER_ITEM",
    "MAX_CONFLICTS_PER_ITEM",
    "MAX_LEFTOVER_TEMPORARIES_PER_ITEM",
    "MAX_PATH_TEXT_CHARS",
    "MAX_TIMING_MS",
    "MAX_DIAGNOSTIC_OUTPUT_BYTES",
    # errors
    "DiagnosticsError",
    "DiagnosticsInputError",
    "DiagnosticsIntegrityError",
    "DiagnosticsContractError",
    "DiagnosticsResourceLimitError",
    "DiagnosticsUnsafeValueError",
    "DiagnosticsSerializationError",
]
```

**S1 集合**：最终集合去掉 `build_preview_diagnostics`、`build_execution_diagnostics`、`render_diagnostics_json`，其余保持
最终相对顺序：

```python
__all__ = [
    "DiagnosticsKind", "ResultShape", "PathPolicy", "TimingPolicy",
    "BatchDiagnostics", "MetadataBatchCounts", "ItemDiagnostics", "IssueDiagnostics", "MetadataDiagnostics",
    "SourceDiagnostics", "SourceAttemptDiagnostics", "FieldProvenance", "FieldConflictDiagnostics",
    "ImageFailureGroup", "PreflightDiagnostics", "ExecutionDiagnostics", "LeftoverTemporaryDiagnostics",
    "DIAGNOSTICS_SCHEMA", "DIAGNOSTICS_SCHEMA_VERSION", "PROVENANCE_FIELD_ORDER", "MAX_DIAGNOSTIC_ITEMS",
    "MAX_SOURCES_PER_ITEM", "MAX_ATTEMPTS_PER_SOURCE", "MAX_BLOCKERS_PER_ITEM", "MAX_CONFLICTS_PER_ITEM",
    "MAX_LEFTOVER_TEMPORARIES_PER_ITEM", "MAX_PATH_TEXT_CHARS", "MAX_TIMING_MS", "MAX_DIAGNOSTIC_OUTPUT_BYTES",
    "DiagnosticsError", "DiagnosticsInputError", "DiagnosticsIntegrityError", "DiagnosticsContractError",
    "DiagnosticsResourceLimitError", "DiagnosticsUnsafeValueError", "DiagnosticsSerializationError",
]
```

**S2 集合**：S1 集合前面加上 `"build_preview_diagnostics", "build_execution_diagnostics"`（即最终集合去掉
`render_diagnostics_json`，其余保持最终相对顺序）：

```python
__all__ = [
    "build_preview_diagnostics", "build_execution_diagnostics",
    # 其后与 S1 集合逐项、同顺序相同
]
```

Design Review PASS 后不得增加、删除、重命名或重排任何阶段集合中的公开名称；任何变化都是合同修订。任何阶段都不得以 stub、
placeholder function 或假模块提前凑出后续阶段的名称。

### 8.2 函数签名（冻结）

```python
def build_preview_diagnostics(
    preview: BatchPreview,
    /,
    *,
    path_policy: PathPolicy = PathPolicy.NONE,
    timing_policy: TimingPolicy = TimingPolicy.OMIT,
) -> BatchDiagnostics: ...

def build_execution_diagnostics(
    result: BatchExecutionResult,
    /,
    *,
    path_policy: PathPolicy = PathPolicy.NONE,
    timing_policy: TimingPolicy = TimingPolicy.OMIT,
) -> BatchDiagnostics: ...

def render_diagnostics_json(diagnostics: BatchDiagnostics, /) -> bytes: ...
```

* 三个函数都是同步、纯函数式（对其输入只读）；不接受 callback、文件、路径、流或 logger 参数。
* builder 的第一个参数是 positional-only；策略参数是 keyword-only。默认 `path_policy` 为 **`PathPolicy.NONE`**（第 18 节）。
* `render_diagnostics_json` 返回值类型冻结为 **`bytes`**：ASCII-only（因而也是合法 UTF-8），不带 BOM、不带末尾换行。
  调用者以后是否保存这些 bytes 不属于 P4-C9。

### 8.3 常量（冻结）

| 常量 | 值 | 说明 |
|---|---|---|
| `DIAGNOSTICS_SCHEMA` | `"fc2_organizer.diagnostics"` | schema 名称 |
| `DIAGNOSTICS_SCHEMA_VERSION` | `"1.0"` | schema 版本（第 23 节） |
| `PROVENANCE_FIELD_ORDER` | `("number", "title", "studio", "publisher", "release", "runtime", "plot", "actors", "tags", "poster_urls", "thumb_urls", "fanart_urls", "extrafanart", "source_urls", "external_ids")` | 与 Phase 3 聚合合同第 5.6 节的固定 key 顺序逐项相同（测试断言与 `fc2_metadata_core.aggregation.policy.FIELD_ORDER` 相等；生产代码不 import 该子模块） |
| `MAX_DIAGNOSTIC_ITEMS` | `MAX_BATCH_ITEMS`（`2000`，由 `fc2_organizer.orchestration` 公开导入，不另写数值） | 单个诊断的条目上限；也约束 `metadata_batch.items` 长度 |
| `MAX_SOURCES_PER_ITEM` | `64` | 每个 `AggregationResult` 的 `source_results`、`source_execution_traces`、`disabled_source_ids`、`contributing_source_ids` 各自的上限 |
| `MAX_ATTEMPTS_PER_SOURCE` | `8` | 每个 source trace 的 attempt 上限（Phase 3 `MAX_ATTEMPTS_LIMIT = 5`，留有余量） |
| `MAX_BLOCKERS_PER_ITEM` | `256` | 每条目 preflight blocker 上限 |
| `MAX_CONFLICTS_PER_ITEM` | `256` | 每个 `AggregationResult` 的 `FieldConflict` 上限；每个 conflict 的 alternatives 上限为 `MAX_SOURCES_PER_ITEM` |
| `MAX_LEFTOVER_TEMPORARIES_PER_ITEM` | `256` | 每条目残留临时文件上限 |
| `MAX_PROVENANCE_KEYS`（**内部常量**，不属于任何阶段的 `__all__`） | `64` | 每个 `AggregationResult.metadata.field_sources` 的 stored key 数上限（含 unknown key）；见下方“`MAX_PROVENANCE_KEYS` 冻结说明” |
| `MAX_PATH_TEXT_CHARS` | `255` | 每个路径派生文本（basename）的字符上限 |
| `MAX_TIMING_MS` | `604800000`（7 天） | 计时值上限（毫秒） |
| `MAX_DIAGNOSTIC_OUTPUT_BYTES` | `67108864`（64 MiB） | 单次序列化输出的硬上限 |

**`MAX_PROVENANCE_KEYS` 冻结说明（Design-R3，技术设计裁决，无 TBD，无需 Owner）**：

* **值与位置**：`64`；定义在 `models.py`（与其它 `MAX_*` 同处）作为**内部**模块级常量，由 `validation.py` 从本 package 的 `models` 模块导入；
  **不**加入第 8.1 节任何阶段的 `__all__`（R-05 的阶段集合 0 变更），**不**出现在任何诊断模型字段或 JSON 输出中。其数值与关系由测试断言
  （第 28.1 节“精确公开 API”“资源上限”行）。
* **A. 下界**：`64 >= len(PROVENANCE_FIELD_ORDER) == 15`。
* **B. 覆盖真实 Phase 3 producer**：聚合 merge（`fc2_metadata_core.aggregation.merge`，构造 `NormalizedMetadata(field_sources={name: provenance[name] for name in FIELD_ORDER if name in provenance})`；
  Phase 3 聚合合同第 5.6 节）产生的 `field_sources` key 集合恒为 `FIELD_ORDER` 的子集，至多 15 个；64 为其约 4 倍余量，也足以容纳手工构造 /
  adapter 级 `NormalizedMetadata` 携带的额外 unknown key。characterization 测试固定“真实 producer 的 key 数 `<= 15 <= MAX_PROVENANCE_KEYS`”（第 28.1 节）。
* **C. 资源 rationale**：每个 `AggregationResult.metadata` 一次单遍扫描最坏观察 `MAX_PROVENANCE_KEYS + 1 == 65` 个 key，每个 key 只做 O(1) 计数与
  `type(key) is str`；不物化任何 list / tuple / set / dict；整批最坏 `MAX_DIAGNOSTIC_ITEMS × 65` 次扫描步，与既有 `MAX_SOURCES_PER_ITEM = 64`
  同量级，使 provenance 相关输入处理量与既有逐条目结构上限同阶。
* **D. 语义**：stored key 数 `<= 64` 通过；`== 65` 时在**观察到第 65 个 key 的那一步**立即抛 `DiagnosticsResourceLimitError`（第 21.2 节），
  之后的 key 不再被读取。上限对 known 与 unknown key 一视同仁。
* **E. 测试**：第 28.1 节“资源上限”行与第 28.4 节边界（等于上限通过、上限 + 1 抛错且不先物化、早停非空洞性）。

### 8.4 错误层次（`errors.py`，冻结）

```python
class DiagnosticsError(Exception): ...                                   # 基类
class DiagnosticsInputError(DiagnosticsError, TypeError): ...            # 参数不是精确的公开输入类型 / 策略枚举
class DiagnosticsIntegrityError(DiagnosticsError, ValueError): ...       # 输入对象图未通过本地校验；诊断图被篡改
class DiagnosticsContractError(DiagnosticsError, ValueError): ...        # 诊断模型构造时违反自身不变量
class DiagnosticsResourceLimitError(DiagnosticsError, RuntimeError): ... # 条目数 / 结构上限 / 输出字节上限
class DiagnosticsUnsafeValueError(DiagnosticsError, ValueError): ...     # 某个将被输出的值不满足安全文本 / 数值规则
class DiagnosticsSerializationError(DiagnosticsError, RuntimeError): ... # JSON 编码阶段的其它失败
```

规则（与 P4-C8 合同第 7.4 节同一原则）：

* message 只由固定措辞组成，可以带常量名与条目 index；**绝不**包含路径、标题、URL、source 文本、secret、任何 Validation-Only
  字段的值或任何下层异常的文本。
* 所有诊断错误都在任何 `except` 块之外抛出，`__cause__` / `__context__` 均为 `None`（不链接下层异常）。P4-C9 的本地校验
  本身不依赖捕获上游异常；唯一允许的 `try` 是 `render.py` 对 `json.JSONEncoder.iterencode` 的包裹（第 24.4 节）。
* 诊断错误只表示“调用方错误、输入被篡改或资源超限”；它们**不**改变原 batch result、retry eligibility 或任何文件（第 24 节）。

### 8.5 允许 import 的上游公开名称（冻结，AST 强制）

| 裸 package | 允许名称 |
|---|---|
| `fc2_organizer.orchestration` | `BatchPreview`、`BatchExecutionResult`、`ItemPreview`、`ItemExecution`、`ItemIssue`、`PreviewSummary`、`ExecutionSummary`、`PreviewState`、`ExecutionDisposition`、`OrchestrationStage`、`IssueReason`、`ItemWarning`、`RetryKind`、`BatchOutcome`、`RetryMaterial`、`MAX_BATCH_ITEMS`、`MAX_RETAINED_ARTIFACT_BYTES_LIMIT` |
| `fc2_organizer.execution` | `ExecutionPreflight`、`ExecutionResult`、`ExecutionStatus`、`ExecutionStep`、`ExecutionFailure`、`ExecutionFailureKind`、`TransferStage`、`TransferMode`、`PreflightMode`、`PreflightBlocker`、`PreflightBlockReason`、`PathRole`、`EffectKind`、`CompletedEffect`、`LeftoverTemporary`、`ExecutionUnit`、`ExecutionCheckpoint`、`PlanGraphRejectionReason`、`ManifestRejectionReason`、`CheckpointRejectionReason`、`PreflightIntegrityReason` |
| `fc2_organizer.images` | `ImageCandidateFailure`、`ImageRole`、`ImageFailureKind`、`ImageAcquisitionPolicy` |
| `fc2_organizer.materialization` | `ArtifactKind`、`ArtifactWriteRequest`、`MappingRejectionReason` |
| `fc2_organizer.discovery` | `DiscoveredMediaItem` |
| `fc2_organizer.planning` | `OrganizePlan`、`PlannedPath`、`PlannedOperation`、`PlannedOperationKind`、`OutputPolicy` |
| `fc2_metadata_core.batch` | `BatchResult`、`BatchItemResult`、`BatchItemStatus`、`BatchItemErrorKind`、`BatchLineage` |
| `fc2_metadata_core.aggregation` | `AggregationResult`、`AggregateStatus`、`SourceExecutionTrace`、`SourceAttempt`、`FieldConflict`、`OPERATIONAL_FAILURE_STATUSES`、`CONFLICT_FIELDS`、`RETRY_ELIGIBLE_KINDS` |
| `fc2_metadata_core.models` | `SourceResult`、`SourceStatus`、`SourceErrorKind`、`NormalizedMetadata` |
| `fc2_metadata_core.normalize` | `is_valid_fc2_number` |

导入的类只用于 `type(x) is C` 比较与枚举成员访问；导入的 frozenset 常量（`OPERATIONAL_FAILURE_STATUSES`、
`RETRY_ELIGIBLE_KINDS`）只用于以**已确认精确枚举成员**做 `in` 判定。明确**不**允许：`BatchOrchestrator`、`merge_retry`、
`OrchestrationConfig`、`CancellationToken`、`preflight_execution`、`execute_filesystem`、`build_organize_plan`、任何
`build_*` / `render_*` / `acquire_*` / `materialize_*` 函数、任何 adapter / client / registry。

---

## 9. 输入权威与本地校验策略（INPUT VALIDATION STRATEGY，冻结）

### 9.0 Input Trust / Tamper Boundary（冻结，Design-R2；Design-R3 修订）

P4-C9 的输入信任分三层，本节是全合同关于“输入被信任到什么程度”的唯一权威陈述；任何其它章节的“fail closed / 篡改 / 钩子”表述
都必须按本节理解：

* **A. Supported public model graph（正式输入权威）**：由既有 public constructors / reviewed pipeline（Phase 3 engine /
  scheduler、P4-C1 / C2 / C5 / C6 / C7 / C8 的正常公开构造路径）产生的 frozen public model graph。这是 P4-C9 builder 正式接受
  的输入。对 A 层输入，P4-C9 的诊断结果完整、确定，并且 P4-C9 **自身**不执行任何调用方代码。A 层**包含**经公开构造路径可达、携带调用方子类对象的
  graph（例如 `str` 子类 source id、`str` 子类 `field_sources` key，见下方 U-2 / U-3 / U-4）：它们被上游的 `isinstance` 构造校验接受，P4-C9 不得假定它们是 exact
  类型，必须按第 9.0.1 节 validate-before-dispatch 处理；这类仅可经公开构造器手工构造的子类对象会被 P4-C9 更严格的 exact-type 规则 fail closed
  （第 9.2 节末段、第 31 节），真实 producer 的输出从不含它们。
* **B. Detectable structural tampering（可检测的结构性篡改）**：经由 `object.__setattr__` 等 invariant bypass，把**普通公开
  字段 / 嵌套公开模型字段**替换成错误的 exact type、错误的子类、错误的枚举、错误的 tuple / frozenset 元素类型、错误的 generation /
  index / 跨对象关系（plan 关系、`RetryMaterial` 关系、artifact manifest、`BatchResult`、execution 关系、retained payload 预算
  关系等）。对 B 层，P4-C9 在读取每个对象的字段**之前**按第 9.5 节 Validation Map 逐项做精确类型 / 容器 / 枚举 / 标量 /
  跨对象本地校验，并 **fail closed**（`DiagnosticsIntegrityError`，不返回部分结果，不修改输入）。B 层的要求不因 C 层的排除而降低。
* **C. Opaque implementation forging（不透明实现伪造）**：绕过上游公开合同，把标准库不透明容器（典型：
  `types.MappingProxyType` 的隐藏被包装 mapping）的**内部状态**替换成 hostile 实现。P4-C9 **不**使用任何反射 / 内省 / 实现内部
  手段（第 7 节 No New Introspection）去识别这类状态，因为不存在可移植的、标准公开的、非反射的手段去观察它。这种状态**不属于**
  supported input graph，P4-C9 对它**不提供** sandbox guarantee，也不声称能够检测它。**明确不属于 C 层**：经正常 public constructor 即可产生的对象
  （典型：`str` 子类的 `field_sources` key / source id）属于 A / B 层，必须 fail closed 且不执行其钩子。

**这条排除是窄的、可审的**：它只覆盖 C 层（不透明标准库容器的隐藏内部状态）；它**不是**“输入都被信任”，**也不是**降低对 B 层
（可通过公开、非反射表面观察到的结构）的 fail-closed 要求。凡能通过公开字段、精确类型比较、公开容器的 `len` / 迭代 / 下标观察到的
结构与关系，一律按 B 层检查。

**上游公开合同依据与 authority 证据（Design-R3 重写；不是 P4-C9 重新实现）**。涉及“上游 public constructor 接受 / 拒绝什么”的断言，其
normative authority 是**稳定 symbol / 函数 + frozen upstream SHA / package authority**；源码行号只作为 review evidence，**不是**唯一
normative authority。以下事实的 package authority 为 `a662659dfd6e801531b14af7913d84a5f9f859e2`（Package Frozen Base；`fc2_metadata_core` 自该
SHA 起未被 P4-C9 修改，P4-C9 也不修改它）：

| # | 事实 | Authority（symbol + 合同） | Review evidence（可能漂移，非 normative） | P4-C9 characterization 测试 |
|---|---|---|---|---|
| U-1 | `NormalizedMetadata.field_sources` 在构造时被快照：发布为包在**上游新建的私有 `dict`** 外面的 `types.MappingProxyType`，value 被快照为 `tuple`；调用方持有的输入 mapping 不被别名共享 | `fc2_metadata_core.models.NormalizedMetadata` 构造路径（`__post_init__` → `_freeze_collections` → `_coerce_field_sources_mapping`）；Phase 1 合同 `FC2_METADATA_CORE_CONTRACT.md` 第 2.2 节（深度不可变，“包在新建私有 `dict` 外面的 `types.MappingProxyType`”） | `src/fc2_metadata_core/models/metadata.py` 约第 182-196、262-278 行 | UC-4、UC-5 |
| U-2 | `field_sources` 的 key 被要求是 `str`，**但以 `isinstance(key, str)` 判定**：`str` **子类**实例通过，且**原 key 对象**被写入上游新建的 `dict`（不被规范化为 exact `str`）；非 `str` key 以 `MetadataContractError` 拒绝 | 同上 `_coerce_field_sources_mapping`；Phase 1 合同第 2.1 节表（“`str` key 到有序 `Sequence[str]` value 的 mapping”——合同文字不要求 exact `str`） | 同上 `isinstance(key, str)` 分支 | UC-1、UC-2、UC-3 |
| U-3 | `field_sources` 的 value tuple 的元素同样以 `isinstance(item, str)` 判定：`str` 子类元素被接受并保留 | `fc2_metadata_core.models` 的 `_coerce_str_tuple`（Phase 1 合同第 2.1a 节 `Sequence[str]` 规则） | `metadata.py` 约第 108-150 行 | UC-6 |
| U-4 | `AggregationResult` 的公开构造**不**验证 `metadata.field_sources`（其模块说明明确列为 “Not verified”），其 `isinstance` 构造校验接受 `str` 子类 source id；因此携带 `str` 子类 key 的 `NormalizedMetadata` 经**公开构造路径**即可进入 `AggregationResult.metadata` | `fc2_metadata_core.aggregation.AggregationResult.__post_init__`；Phase 3 聚合合同第 5.6 节（`field_sources` 由 merge 重新计算，但模型构造不重算） | `src/fc2_metadata_core/aggregation/models.py` 约第 50-51、345-420 行 | UC-7 |
| U-5 | 真实 Phase 3 producer 的 `field_sources` key 集合恒为 `FIELD_ORDER` 的子集，至多 15 个 | `fc2_metadata_core.aggregation.merge` 的 `NormalizedMetadata(field_sources={name: provenance[name] for name in FIELD_ORDER if name in provenance})`；Phase 3 聚合合同第 5.6 节 | `src/fc2_metadata_core/aggregation/merge.py` 约第 293-296 行 | UC-8 |

**由此得出的、本合同依赖的精确结论（Design-R3）**：

1. 在 A 层，`field_sources` 的 `MappingProxyType` 包装的是上游自己新建的私有 exact `dict`（U-1，合同层面的陈述，不是 P4-C9 对其内部的反射观察）；
   P4-C9 **不** introspect proxy 的被包装对象（第 7 节 No New Introspection，第 9.0 节 C 层）。
2. 但该 `dict` 的 **key 不保证是 exact `str`**（U-2）；`str` 子类 key 可经正常 public constructor 进入 supported public model graph。
   这属于 **A / B 层**，**不是** C 层（C 层只指绕过公开合同、对不透明容器隐藏状态的 invariant-bypass 伪造）。因此 P4-C9 不能假定 stored key
   是 exact `str`：必须按第 9.2 节第 9 条在任何 hash / 相等敏感操作之前逐个验证。
3. 上游构造过程本身（`isinstance(key, str)`、`dict` 赋值时的 `__hash__` / `__eq__`、错误路径的 `repr(key)`）可能执行调用方子类的钩子；这发生在
   P4-C9 被调用**之前**，**不属于** P4-C9 的责任，也不被 P4-C9 观察（见第 28.1 节：测试在上游构造完成之后必须复位 sentinel）。P4-C9 只保证**自己的**
   读取过程在 A 层输入上不执行调用方代码。

**“零调用方钩子”的精确语义**（取代任何绝对表述）：P4-C9 production **不会主动**调用输入模型的多态实例方法、private 方法、
dunder validator、callback、用户提供的函数或任何动态反射；对 A 层输入，本地校验使用精确类型比较（拒绝子类）并遵守 validate-before-dispatch
（第 9.0.1 节）：在 caller-originated 对象完成 exact-type 校验之前，不对其做任何可能触发 `__hash__` / `__eq__` / 富比较 / 成员判定 /
多态 property 的操作。P4-C9 **不**声称对 C 层伪造的不透明容器内部提供 sandbox guarantee，也**不**声称“整个 Python 进程绝不会运行 audit
hook”或任何调用方安装的钩子（这超出 library 可控范围）；P4-C9 只承诺：不主动调用 `gc.get_referents`、`inspect`、`sys` audit
API 或其它专门的反射 / 内省原语，不注册 audit hook / callback / logger hook，并且在 A 层输入上不调用 caller-provided 多态方法、不在
exact-type 校验之前对 caller-originated 值执行分派敏感操作。

### 9.0.1 Validate-Before-Dispatch（冻结，Design-R3）

**统一规则**：任何可能执行以下之一的操作 ——

* `__hash__`（`dict` / `set` / `frozenset` 的建立、成员判定、下标、`in`、`dict.get`）；
* `__eq__` / `__ne__` / `__lt__` / `__le__` / `__gt__` / `__ge__`（含 tuple / list 的逐元素比较与 `tuple.__contains__`）；
* 容器成员判定（`x in container`）与按值查表；
* 多态 property / 方法 / 属性读取（子类的 `__getattribute__` / property）；
* `__bool__` / `__len__`（对象的真值转换）、`__iter__`（对非精确内建容器的迭代）、`__str__` / `__repr__` / `__format__`（任何文本转换）

—— **必须**在相关 caller-originated 对象完成 **exact-type 校验之后**才能发生。具体拆为四条冻结规则：

* **V-1 对象先行**：读取任何对象的任何字段之前，先 `type(obj) is ExactClass`（第 9.2 节第 1、2 条）。
* **V-2 两阶段（Phase V → Phase R）**：对每个 caller-originated 容器（tuple / frozenset / `MappingProxyType`），**Phase V**：以只含 `type()` 比较、计数与
  公开长度检查的遍历，确认**全部**元素 / key 的 exact type（以及该容器的结构上限，第 21.2 节）；只有该容器的 Phase V **全部完成并通过**之后，才允许
  **Phase R**：成员判定（`in`）、相等 / 唯一性、查表、下标取值、跨对象比较。禁止“边验证边做成员判定”（即对尚未完成 Phase V 的容器或其元素做
  Phase R 操作）。
* **V-3 有界性**：Phase V 本身不得建立无界中间容器：不得先 `list()` / `tuple()` / `set()` / `sorted()` 物化再检查大小；对不能在迭代前以 `len()` 判定
  大小的容器（仅 `field_sources` 的 `MappingProxyType`），以**单遍计数 + 超限立即停止**实现（第 9.2 节第 9 条）。
* **V-4 先出现者**：当同一输入同时违反多条规则（例如 key 数超限且含子类 key），P4-C9 报告**遍历中最先遇到**的那一条违规对应的错误类型（固定措辞、
  无 key / 元素文本）。该规则只影响**失败输入的错误类型**；对**通过校验**的输入，输出与 mapping 插入顺序、对象构造顺序无关（第 15 节）。

适用范围**不限于** `field_sources`：第 9.10 节 Dispatch Safety Matrix 对 P4-C9 实际执行的全部 caller-originated 值操作逐行裁定其前置条件，第 9.11 节
Horizontal Dispatch Audit 逐个检查本合同消费的 caller-originated 容器与批准 property。矩阵中的“Required Precondition”是**规范性**的：实现与测试都按
其逐行执行 / 证明。

### 9.1 可消费的顶层输入

只接受两种**精确类型**（`type(x) is ...`，子类一律拒绝）的顶层输入：`BatchPreview`（`build_preview_diagnostics`）与
`BatchExecutionResult`（`build_execution_diagnostics`）。诊断只读取经由它们的公开字段合法可达、并列在第 9.5 节中的公开模型。

**正式裁决（Design-R1）**：P4-C9 production **不得**调用任何上游对象的 `__post_init__`，不得调用任何其它 private / dunder
validator，不得调用任何上游实例方法（例如 `NormalizedMetadata.meets_minimum_success()`、`AggregationResult.result_for()`）
作为校验手段，不得使用 P4-C8 `revalidate`。没有任何“private-name exception”或“validator exception”。P4-C9 只使用：
公开类型、公开 dataclass 字段、第 9.3 节逐项列出的公开 property / 纯函数，以及 P4-C9 自己的 Local Validation。

### 9.2 Local Validation 定义（冻结）

Local Validation 是 P4-C9 自己实现的纯只读校验，规则如下：

1. **精确类型先行**：任何对象在读取其任何字段之前，先以 `type(x) is ExactExpectedType` 确认；子类一律拒绝。
2. **nested 同样先行**：嵌套对象在读取其字段前同样先做精确类型确认；外层通过校验**不被假设**为已递归校验内层。
3. **容器精确**：容器先确认精确容器类型（`tuple` / `frozenset` / `types.MappingProxyType`，按第 9.5 节逐字段冻结；
   `MappingProxyType` 只出现在 `NormalizedMetadata.field_sources`，见第 9 条）；tuple 元素逐个精确类型确认。
4. **枚举精确**：枚举值必须 `type(v) is FrozenEnum`；枚举比较一律用 `is`。
5. **int 拒绝 bool**：整数字段必须 `type(v) is int`；`bool` 与 `int` 子类拒绝；需要浮点数的计时字段接受 `type(v) is int`
   或 `type(v) is float`，并要求 `math.isfinite(v)`。
6. **str 先精确**：字符串字段必须 `type(v) is str`，之后才执行该字段冻结的规则（非空、正则、长度、`isidentifier()`、
   `strip()` 等内建 `str` 方法只在精确 `str` 上调用）。
7. **跨对象关系显式检查**：第 9.6 节逐项列出；对象身份比较用 `is`；值比较只在两侧都已确认为精确 `str` / `int` / `bool` /
   `None` 时用 `==`。
8. **不调用输入对象上的任何方法**：不调用任何 dunder / private 方法、用户钩子、property（第 9.3 节例外清单除外）；不使用
   `getattr` / `hasattr` / `vars` / `dir` / `isinstance` / `repr` / `str(input_object)` / `format(input_object)` 或任何动态反射。
   允许的操作只有：读取已精确确认类型的 frozen dataclass 公开字段；对精确 `tuple` / `frozenset` 的 `len()`、迭代、下标 /
   成员判定（**成员判定 / 下标取值 / 相等只在该容器的 Phase V 全部完成之后**，第 9.0.1 节 V-2；每一种操作的前置条件见第 9.10 节 Dispatch Safety Matrix）；对精确 `MappingProxyType`（仅 `field_sources`）按第 9 条先做有界 key 扫描（只 `type(key) is str`），**其后**才以固定字面 key 做 `in` / 下标；对精确 `str` 的内建方法与比较；对精确 `int` / `float` 的比较与 `math.isfinite`；`re.fullmatch`（模块级预编译
   pattern，作用于精确 `str`）；`os.path.isabs` / `os.path.join` / `os.path.basename`（作用于精确 `str`，纯字符串处理，不访问
   文件系统）；第 9.3 节的公开纯函数与 property。
9. **`field_sources` 的 MappingProxy 访问（冻结，Design-R3 取代 Design-R2；第 12.3 节同）**：算法顺序固定为 **BOUNDED ITERATE → EXACT KEY
   VALIDATION → FIXED KNOWN-KEY LOOKUP**，分为 Step 1-5：

   * **Step 1**：确认 `type(metadata) is NormalizedMetadata`（V-1；否则 `DiagnosticsIntegrityError`）。
   * **Step 2**：读取 `metadata.field_sources`，确认 `type(proxy) is types.MappingProxyType`（否则 `DiagnosticsIntegrityError`）。
   * **Step 3 —— BOUNDED ONE-PASS KEY SCAN**：对 `proxy` 做**一次** `for key in proxy` 迭代；对每个 key **依次**执行：
     **A.** 计数加一；
     **B.** 若计数 `> MAX_PROVENANCE_KEYS`（第 8.3 节，`64`）：**立即**抛 `DiagnosticsResourceLimitError`，不再读取后续 key，也不检查该 key 的类型；
     **C.** 确认 `type(key) is str`（否则 `DiagnosticsIntegrityError`）。
     在整个 Step 3 期间**禁止**：对 `proxy` 做 `in` / 下标 / `.get()` / `.keys()` / `.values()` / `.items()` / `.copy()` / `len()`；先 `list()` / `tuple()` /
     `set()` / `sorted()` 物化 proxy 或其 key 再检查大小或类型（**Unbounded Key Materialization：FORBIDDEN**）；对 key 做 `==`、`!=`、`hash`、
     `in`、`str()`、`repr()`、格式化、任何方法调用或任何富比较——Step 3 对 key **唯一**允许的操作是 `type(key) is str`。进入 Step 4 的**唯一**条件是：Step 3 迭代
     **完整结束**且**每一个** stored key（含不属于 `PROVENANCE_FIELD_ORDER` 的 unknown key）都已通过 C（并且计数始终 `<= MAX_PROVENANCE_KEYS`）。
   * **Step 4 —— FIXED KNOWN-KEY LOOKUP**：仅在 Step 3 完全 PASS 之后，按 `PROVENANCE_FIELD_ORDER` 的声明顺序对每个 `name`（本模块的精确 `str` 常量）
     先 `name in proxy`，存在才 `proxy[name]`；输出顺序**完全**由 `PROVENANCE_FIELD_ORDER` 决定。**安全依据（精确陈述）**：在 A 层，proxy 包装的是上游自己新建的私有
     exact `dict`（第 9.0 节 U-1，合同层面的事实，P4-C9 不 introspect）；其全部 stored key 已在本轮 Step 3 验证为 exact `str`；因此固定 exact-`str` 查询对 stored key 只会
     发生 exact `str` 的 `__hash__` / `__eq__`，**不存在** caller-controlled `str` 子类 hash / equality 分派。不得使用 `gc`、reflection、referent introspection 来获得这一性质。
   * **Step 5 —— value 校验**：每个被找到的 value 先 `type(value) is tuple`；再依 V-2：先**遍历**确认每个元素 `type(sid) is str`（Phase V），之后才做满足第 17.2 节
     安全 id 规则的检查、两两不同与 `in contributing_source_ids`（Phase R；`contributing_source_ids` 已先完成其自身 Phase V，见 M-16）。`PROVENANCE_FIELD_ORDER` 中未出现
     的 known field 就是 schema 定义的 absence。

   **Unknown key**：不属于 `PROVENANCE_FIELD_ORDER` 的 key **不**赋予 diagnostics 语义——不投影、不输出、不参与 field provenance、其 value 不读取；但它们**必须**经过 Step 3
   的有界扫描与 exact-`str` 验证，并**计入** `MAX_PROVENANCE_KEYS`。（Design-R2 的“其它 key 不读取”表述被替换为本条：key 全部被扫描，只有 known key 有语义。）

   **Mapping 迭代范围**：对 A 层 supported graph，`MappingProxyType` 的迭代**仅用于 validation**；允许 validation iteration **不等于**依赖 mapping 的插入顺序——Step 3 的结果
   （通过 / 失败的性质、通过时的全部输出）与 key 的插入顺序无关（失败输入的错误类型遵守第 9.0.1 节 V-4）。Design-R2 的“禁止迭代 proxy”过宽禁令删除。

   **Layer C 不变**：不透明 `mappingproxy` hidden referent 被 invariant-bypass 替换成 hostile mapping 仍属第 9.0 节 C 层；P4-C9 不使用 introspection 识别它，也不为它提供
   sandbox guarantee。**公开构造器可产生的 `str` 子类 key 明确不是 C 层**，由 Step 3 fail closed。
10. **先迭代后成员判定**：对精确 `frozenset`（仅 `retry_scope`），先完整迭代并确认每个元素的精确类型（迭代精确内建容器不调用
    元素的任何方法；遇到第一个非精确 `RetryKind` 元素或 `NONE` 即 `DiagnosticsIntegrityError`，因此迭代天然有界：至多 `len(RetryKind) - 1` 个合法元素之后必然终止），
    之后才允许成员判定（避免哈希碰撞时调用恶意元素的 `__eq__`）。这是第 9.0.1 节 V-2 的一个实例。
11. **校验快照**：Local Validation 产出一个只含 Projection Reads 的内部不可变快照；projection 只读取该快照，不再读取输入对象
    （第 9.3 节的批准 property 例外，其返回值同样先经本地校验）。

本地校验可以比上游模型构造函数更严格（例如上游某些字段用 `isinstance` 接受子类，P4-C9 要求精确类型）；真实 producer
（Phase 3 engine / scheduler、P4-C1 / C2 / C5 / C6 / C7 / C8）的输出总满足本地校验，测试以真实编排结果证明。

### 9.3 批准的公开 property 与纯函数（穷举，冻结）

只允许读取 / 调用以下五个 P4-C8 已冻结的公开派生 property 与一个公开纯函数；不得泛化为“任何 public property 都可以调用”：

| 名称 | 读取前提（其依赖的对象图已完成本地校验） | 返回值本地校验 |
|---|---|---|
| `BatchPreview.summary` | 第 24.2 节第 4-6 步全部通过 | 精确 `PreviewSummary`，按第 9.5 节 M-08 校验 |
| `BatchExecutionResult.summary` | 同上 | 精确 `ExecutionSummary`，按 M-09 校验 |
| `BatchExecutionResult.outcome` | 同上 | 精确 `BatchOutcome` 成员 |
| `ItemPreview.warnings` | 该条目及其 metadata / preflight / artifacts / image_failures 已校验 | 精确 `tuple`，元素为精确 `ItemWarning`，唯一且按声明顺序 |
| `ItemExecution.retry_kind` | 该条目及其 execution / issue / retry_material 已完成本地校验，且已由已校验公开字段本地推导出 `expected_kind`（第 9.6.4 节） | 精确 `RetryKind` 成员，且 `is expected_kind` |
| `is_valid_fc2_number(s)`（`fc2_metadata_core.normalize`） | `type(s) is str` 已确认 | 精确 `bool` |

这些 property 的实现是 CLOSED package 的已冻结代码，作用于已经精确类型确认并通过本地校验的对象图；P4-C9 不读取任何其它
property（例如 `BatchExecutionResult.is_complete`、`BatchResult.total` / `success_count` 等、`ItemPreview.source_path` 等显示
property、`AggregationResult.successful_source_ids` 等），对应信息由本地字段读取与本地计算得到。

#### 9.3.1 批准 property 的依赖图（冻结，Design-R3）

批准 property 是“多态 property”这一 dispatch surface 的**全部**实例（第 9.10 节 D-28）。因为顶层与条目对象都已 `type(x) is ExactClass` 确认，property 的代码是 CLOSED
package 自己的已冻结代码（实例上无法替换 class 级 property）；唯一的分派风险来自**它读取的字段**。因此“读取前提”必须落实为**其完整依赖图已完成本地校验**。下表由 P4-C8 已冻结
实现（symbol 为权威；SHA `a662659dfd6e801531b14af7913d84a5f9f859e2`；P4-C8 合同对应节在括号内）逐个列出该依赖图；表中任一项未通过本地校验时，**不得**读取该 property：

| Property（symbol；P4-C8 合同节） | 依赖图（property 实现读取的全部 caller-originated 字段，及各自必须已通过的校验） | 其它前置条件（避免上游裸异常） |
|---|---|---|
| `ItemPreview.warnings`（经内部 `_manifest_kinds`；第 22.3 节） | `self.metadata`：`None` 或精确 `BatchItemResult` 且其 `status` 为精确 `BatchItemStatus`；`self.preflight`：`None` 或精确 `ExecutionPreflight` 且 `artifacts` 为精确 `tuple`、每项精确 `ArtifactWriteRequest`、其 `kind` 为精确 `ArtifactKind`、其 `content` 为精确 `bytes`（M-23 / M-24）；`self.image_failures`：精确 `tuple`（仅真值转换，等价于 `len`，不触及元素） | 该条目的 M-05 与第 9.6.3 节全部通过 |
| `ItemExecution.retry_kind`（第 25.1 节） | `self.disposition` 精确 `ExecutionDisposition`；`EXECUTED` 时 `self.execution` 精确 `ExecutionResult` 且 `status` 精确 `ExecutionStatus`；`NOT_READY` 时 `self.issue` 精确 `ItemIssue` 且 `stage` 精确 `OrchestrationStage`、`reason` 精确 `IssueReason` | 第 9.6.4 节关系已通过：`(execution is None) == (disposition is not EXECUTED)`、`NOT_READY ⇒ issue is not None`；`expected_kind` 已本地推导 |
| `BatchPreview.summary`（第 28.1 节） | `self.items`：精确 `tuple`；逐条目：`state` 精确 `PreviewState`；`issue` 为 `None` 或精确 `ItemIssue`（`stage` 精确 `OrchestrationStage`）；以及**每个条目的 `ItemPreview.warnings` 依赖图**（上一行第 1 项） | 第 24.2 节第 4-6 步全部通过（含 retained 预算） |
| `BatchExecutionResult.summary`（第 28.2 节） | `self.items`：精确 `tuple`；逐条目：`disposition`、`preview_state` 精确枚举；`EXECUTED` 条目的 `execution.status` 精确 `ExecutionStatus`；`issue` 为 `None` 或精确 `ItemIssue`（`stage` 精确）；以及**每个条目的 `ItemExecution.retry_kind` 依赖图**（上一项） | 同上；且每个条目的 `retry_kind` 一致性（第 24.2 节第 7 步）已先于 `summary` 通过 |
| `BatchExecutionResult.outcome`（第 11.5 节） | `self.items`：精确 `tuple`；逐条目 `disposition` 精确枚举；`EXECUTED` 条目的 `execution.status` 精确 `ExecutionStatus` | 同上 |
| `is_valid_fc2_number(s)`（`fc2_metadata_core.normalize`） | 参数 `s`：精确 `str`（只作正则匹配） | 调用前 `type(s) is str` |

补充说明：`summary` 在返回时由 P4-C8 自己构造 `PreviewSummary` / `ExecutionSummary` 新值（其 `__post_init__` 是该 property 的**内部**实现，作用于 P4-C8 新建的值，**不是** P4-C9 对输入对象的
`__post_init__` 调用，第 9.1 节正式裁决不受影响）；返回值仍须按 M-08 / M-09 本地校验。上表的每一条“依赖图”在第 24.2 节第 4-6 步（对象与跨对象校验）完成之后、第 7 步读取之前即已满足，
因此 P4-C9 在读取批准 property 时不会让 caller-originated 值在未经 exact-type 校验的情况下进入任何分派。

### 9.4 Projection Reads 与 Validation-Only Reads（冻结）

* **Projection Reads**：进入诊断模型或参与输出计算的字段。
* **Validation-Only Reads**：仅用于确认上游公开对象未被篡改、满足其已冻结不变量的字段。它们**绝不**进入诊断模型、JSON 或
  错误 message；不被复制进校验快照；字节载荷只做 `type()` 确认，不读取内容、不计算长度之外的任何东西、不复制。
* 两类读取的**封闭**并集就是第 9.5 节各行列出的字段；任何未列出的字段都不被读取（“不被消费”）。P4-C9 只对它读取的字段及
  这些字段之间的已冻结不变量作出完整性保证；对未读取字段不作声明，它们也不可能影响诊断输出。

### 9.5 Consumed-Object Validation Map（完整，冻结）

下表覆盖 P4-C9 实际消费的**全部** upstream model。通用约定：

* “hex32” = 精确 `str` 且完全匹配 `[0-9a-f]{32}`；“hex64” 同理 64 位；“非空 str” = 精确 `str` 且长度 ≥ 1；“int≥n” = 精确
  `int`（非 bool）且 ≥ n；“opt X” = `None` 或 X。
* 所有失败默认抛 `DiagnosticsIntegrityError`；“资源”行的超限抛 `DiagnosticsResourceLimitError`，且在迭代对应容器**之前**
  检查长度；第 9.7 节的安全输出检查失败抛 `DiagnosticsUnsafeValueError`。
* “类型确认”行的对象：只确认精确类型，不读取其任何字段。
* 本地冻结表（第 9.8 节）的内容逐项抄自对应上游合同；测试断言它们与上游实现相等。

**M-01 `BatchPreview`**（`fc2_organizer.orchestration`）

* Projection：`generation`、`base_result_id`（只作 `is None` 判定 -> `shape`）、`retry_scope`、`batch_size`、`items`、`metadata_batch`。
* Validation-Only：`preview_id`、`lineage`、`library_root`、`output_policy`、`image_policy`、`retention_budget_bytes`、`retry_budget_bytes`。
* 容器：`items` 精确 `tuple`，元素精确 `ItemPreview`；`retry_scope` 为 `None` 或精确 `frozenset`，先迭代确认每个元素为精确 `RetryKind` 且不是 `NONE`。
* 标量 / 枚举：`preview_id` hex32；`generation` int≥0；`base_result_id` opt hex32；`batch_size` int≥0 且 ≤ `MAX_DIAGNOSTIC_ITEMS`；`library_root` 非空 str 且 `os.path.isabs`；`output_policy` 精确 `OutputPolicy`、`image_policy` 精确 `ImageAcquisitionPolicy`（类型确认）；`retention_budget_bytes` int≥1 且 ≤ `MAX_RETAINED_ARTIFACT_BYTES_LIMIT`；`retry_budget_bytes` opt（int≥0 且 ≤ `retention_budget_bytes`）。
* 跨对象：第 9.6.1 节（含本地计算的 retained artifact 字节与预算关系）。
* 资源：`len(items) <= MAX_DIAGNOSTIC_ITEMS`（第 24.2 节第 3 步，任何逐条工作之前）。

**M-02 `BatchExecutionResult`**（`fc2_organizer.orchestration`）

* Projection：`generation`、`base_result_id`（只作 `is None` 判定）、`retry_scope`、`batch_size`、`items`、`metadata_batch`。
* Validation-Only：`result_id`、`preview_id`、`lineage`、`library_root`、`output_policy`、`image_policy`、`retention_budget_bytes`、`retry_budget_bytes`。
* 容器：`items` 精确 `tuple`，元素精确 `ItemExecution`；`retry_scope` 同 M-01。
* 标量 / 枚举：`result_id` hex32；`preview_id` opt hex32；其余同 M-01。
* 跨对象：第 9.6.2 节（含本地 shape 判定，以及本地计算的 retained retry payload 字节与预算关系）。
* 资源：同 M-01。

**M-03 `BatchLineage`**（`fc2_metadata_core.batch`）—— Validation-Only：`token` hex32。不进入任何输出。

**M-04 `OutputPolicy` / `ImageAcquisitionPolicy` / `ExecutionCheckpoint` / `ExecutionUnit`** —— 类型确认
（字段不读取）。`ExecutionCheckpoint` 只用于存在性与对象身份比较（`is`）；`ExecutionUnit` 只用于计数。
（`RetryMaterial` 不在本行：它有完整的 M-30。）

**M-05 `ItemPreview`**（`fc2_organizer.orchestration`）

* Projection：`index`、`generation`、`media_item`、`canonical_number`、`metadata`、`plan`、`image_failures`、`preflight`、`state`、`issue`、`conflict_with`、`retry_origin`（以及第 9.3 节 `warnings`）。
* Validation-Only：`metadata_position`。
* 容器：`image_failures` 精确 `tuple`，元素精确 `ImageCandidateFailure`；`conflict_with` 精确 `tuple`，元素 int≥0。
* 标量 / 枚举：`index`、`generation` int≥0；`canonical_number` opt（精确 `str` 且 `is_valid_fc2_number`）；`metadata_position` opt int≥0；`metadata` opt 精确 `BatchItemResult`；`plan` opt 精确 `OrganizePlan`；`preflight` opt 精确 `ExecutionPreflight`；`state` 精确 `PreviewState`；`issue` opt 精确 `ItemIssue`；`retry_origin` opt（精确 `RetryKind` 且不是 `NONE`）。
* 跨对象：第 9.6.3 节。
* 资源：无单独上限（`image_failures` 只被分组计数，输出上界见第 21.2 节）。

**M-06 `ItemExecution`**（`fc2_organizer.orchestration`）

* Projection：`index`、`generation`、`media_item`、`canonical_number`、`metadata`、`plan`、`image_failures`、`conflict_with`、`preview_state`、`issue`、`warnings`、`disposition`、`execution`、`retry_material`（只作 `is None`），以及第 9.3 节 `retry_kind`。
* Validation-Only：`metadata_position`。
* 容器：同 M-05；`warnings` 精确 `tuple`，元素精确 `ItemWarning`，唯一且按 `ItemWarning` 声明顺序。
* 标量 / 枚举：同 M-05 的公共字段；`preview_state` 精确 `PreviewState`；`disposition` 精确 `ExecutionDisposition`；`execution` opt 精确 `ExecutionResult`；`retry_material` opt 精确 `RetryMaterial`（其字段按 M-30 本地校验）。
* 跨对象：第 9.6.4 节（含 `retry_kind` 的本地推导、`retry_material` 存在性与对象身份 / checkpoint 关系）。

**M-07 `ItemIssue`**（`fc2_organizer.orchestration`）

* Projection：`stage`、`reason`、`error_type`、`detail`。
* 标量 / 枚举：`stage` 精确 `OrchestrationStage`；`reason` 精确 `IssueReason`；`error_type` opt（精确 `str`，`isidentifier()`，长度 1..128）；`detail` opt 枚举成员。
* 跨对象：按第 9.8 节表 T-1（P4-C8 合同第 10.2 节）：`stage is` 该 reason 的冻结 stage；需要 `error_type` 的 reason 必须有，其余必须为 `None`；`detail` 为 `None` 或其类型精确属于该 reason 允许的枚举类型；要求 detail 的 reason 必须有。

**M-08 `PreviewSummary`**（批准 property 的返回值）

* Projection：整体携带。
* 标量：`total`、`ready`、`blocked`、`unprepared`、`warned` int≥0；`stage_counts` 精确 `tuple`，恰有 `len(OrchestrationStage)` 项，每项为精确 2-tuple（精确 `OrchestrationStage`、int≥0），stage 按声明顺序。
* 跨对象：`total == len(items)`；`total == ready + blocked + unprepared`；`warned <= total`；`sum(stage_counts) == blocked + unprepared`。

**M-09 `ExecutionSummary`**（批准 property 的返回值）

* Projection：整体携带。
* 标量：16 个计数字段 int≥0；`stage_counts` 同 M-08。
* 跨对象：`total == len(items)`；以及 P4-C8 合同第 28.2 节五条恒等式：`executed == success + partial + failed`；`ready == executed + not_selected + cancelled + rejected + aborted`；`total == executed + blocked + unprepared + not_selected + cancelled + rejected + aborted`；`total == success + retryable + deferred + non_retryable`；`sum(stage_counts) == blocked + unprepared + partial + failed + rejected + aborted`。

**M-10 `DiscoveredMediaItem`**（`fc2_organizer.discovery`）

* Projection：`size`；`source_path`（**仅** `PathPolicy.BASENAME` 时，作为 basename 来源）。
* Validation-Only：`index`、`source_path`（任何策略下的类型 / 绝对性检查）、`relative_path`、`extension`。
* 标量：`index` int≥0；`source_path` 非空 str 且 `os.path.isabs`；`relative_path` 非空 str；`extension` 精确 `str` 且 `startswith(".")`；`size` int≥0。
* 跨对象：与 `OrganizePlan` 的来源字段相等（M-11）。

**M-11 `OrganizePlan`**（`fc2_organizer.planning`）

* Projection：`target_directory`、`target_media_path`（**仅** `PathPolicy.BASENAME` 时，作为 basename 来源；在任何策略下 `plan is None` 都参与 `preview_state` 等无关字段之外的“plan 是否存在”判断）。
* Validation-Only：`source_path`、`source_relative_path`、`source_extension`、`source_index`、`source_size`、`canonical_number`、`library_root`、`nfo_path`、`poster_path`、`fanart_path`、`thumb_path`、`extrafanart_directory`、`operations`。
* 容器：`operations` 精确 `tuple`，恰 7 项，元素精确 `PlannedOperation`。
* 标量：五个 `source_*` 与 `canonical_number`、`library_root` 为精确 `str`（非空）/ int≥0（`source_index`、`source_size`）；`source_path`、`library_root` 满足 `os.path.isabs`；七个路径字段均为精确 `PlannedPath`（M-12）。
* 跨对象：第 9.6.5 节（P4-C2 合同第 4、7、11、14 节的冻结布局与操作顺序）。

**M-12 `PlannedPath`**（`fc2_organizer.planning`）—— Validation-Only / Projection（basename 来源）：`absolute_path` 非空 str 且 `os.path.isabs`。

**M-13 `PlannedOperation`**（`fc2_organizer.planning`）—— Validation-Only：`kind` 精确 `PlannedOperationKind`；`target` 精确 `PlannedPath`（M-12）；`source` 在 `kind is MOVE_MEDIA` 时为精确 `PlannedPath`，否则为 `None`。

**M-14 `BatchResult`**（`fc2_metadata_core.batch`）

* Projection：`generation`；由 `items` 本地计算的 `total`、`success`、`partial`、`failed`（Phase 3 批处理合同第 6 节的派生计数定义）。
* Validation-Only：`lineage`、`items` 元素的全部 M-15 字段。
* 容器：`items` 精确 `tuple`，元素精确 `BatchItemResult`。
* 标量：`generation` int≥0；`lineage` 精确 `BatchLineage`（M-03）。
* 跨对象：`items[i].index == i`（0..n-1 连续）；每个 `items[i].generation <= generation`；`total == len(items)`；`success + partial + failed == total`（每个元素状态恰属其一）；`lineage.token == 外层 batch.lineage.token`（第 9.6.1 / 9.6.2 节）。
* 资源：`len(items) <= MAX_DIAGNOSTIC_ITEMS`（迭代前）。

**M-15 `BatchItemResult`**（`fc2_metadata_core.batch`）

* Projection：`status`、`aggregation_result`、`error_kind`、`generation`；`elapsed_ms`（仅 `TimingPolicy.INCLUDE`）。
* Validation-Only：`index`、`number`、`error_type`、`elapsed_ms`（任何策略下的数值检查）。
* 标量 / 枚举：`index` int≥0；`number` 精确 `str` 且 `is_valid_fc2_number`；`status` 精确 `BatchItemStatus`；`generation` int≥0；`elapsed_ms` 精确 `int` 或 `float`、有限、≥0；`aggregation_result` opt 精确 `AggregationResult`；`error_kind` opt 精确 `BatchItemErrorKind`；`error_type` opt（非空 str，长度 ≤ 256）。
* 跨对象（Phase 3 批处理合同第 6 节）：有 `aggregation_result` 时 `error_kind is None`、`error_type is None`、`aggregation_result.number == number`、`status` 是 `aggregation_result.status` 的 1:1 映射（SUCCESS / PARTIAL / FAILED 同名）；没有时 `status is FAILED`、`error_kind` 与 `error_type` 均非 `None`。

**M-16 `AggregationResult`**（`fc2_metadata_core.aggregation`）

* Projection：`status`、`metadata`（只经 M-18 读取 `field_sources`）、`source_results`、`contributing_source_ids`、`conflicts`、`disabled_source_ids`、`source_execution_traces`。
* Validation-Only：`number`、`elapsed_ms`、`metadata.number` / `metadata.title`（M-18）。
* 容器：`source_results` 精确 `tuple`、非空、元素精确 `SourceResult`；`contributing_source_ids`、`disabled_source_ids` 精确 `tuple`、元素精确 `str`；`conflicts` 精确 `tuple`、元素精确 `FieldConflict`；`source_execution_traces` 精确 `tuple`、元素精确 `SourceExecutionTrace`。
* 标量 / 枚举：`number` 精确 `str` 且 `is_valid_fc2_number`；`status` 精确 `AggregateStatus`；`metadata` opt 精确 `NormalizedMetadata`；`elapsed_ms` 精确 `int` / `float`、有限、≥0。
* 跨对象：第 9.6.6 节（Phase 3 聚合合同第 3 节 / 模型不变量）。
* 资源：`len(source_results)`、`len(source_execution_traces)`、`len(contributing_source_ids)`、`len(disabled_source_ids)` 各 ≤ `MAX_SOURCES_PER_ITEM`；`len(conflicts) <= MAX_CONFLICTS_PER_ITEM`（均在迭代前）；`metadata.field_sources` 的 stored key 数 ≤ `MAX_PROVENANCE_KEYS`（M-18，单遍有界扫描，第 9.2 节第 9 条）。
* **校验顺序（冻结，Design-R3，第 9.0.1 节 V-2）**：(1) 先对 `source_results`、`contributing_source_ids`、`disabled_source_ids`、`conflicts`、`source_execution_traces` 各容器完成 **Phase V**（精确容器类型、结构上限、全部元素精确类型 / 精确 `str`，包括 source id 的 `strip()` 规则）；(2) 之后才做 **Phase R**：source id 唯一性 / 与 `disabled_source_ids` 的重叠、`contributing_source_ids` 与 `successful` 的逐项比较、conflict id 对 `contributing_source_ids` 的成员判定、`source_execution_traces` 与 `source_results` 的逐位置比较；(3) `metadata` 的 M-18（含 `field_sources` 有界 key 扫描与 known-key 查询）在 `contributing_source_ids` 的 Phase V 完成**之后**执行，其 provenance 成员判定（`in contributing_source_ids`）属于 Phase R。

**M-17 `SourceResult`**（`fc2_metadata_core.models`）

* Projection：`source_id`、`status`、`error_kind`。
* Validation-Only：`metadata`、`elapsed_ms`、`error_detail`、`metadata.number` / `metadata.title`（M-18）。
* 标量 / 枚举：`source_id` 精确 `str` 且 `strip()` 非空；`status` 精确 `SourceStatus`；`elapsed_ms` 精确 `int` / `float`、≥0（Phase 3 只要求非负；P4-C9 额外要求有限）；`metadata` opt 精确 `NormalizedMetadata`；`error_kind` opt 精确 `SourceErrorKind`；`error_detail` opt 精确 `str`。
* 跨对象（Phase 1 / Phase 3 resilience 合同的 `SourceResult` 不变量，第 9.8 节表 T-2）：`SUCCESS` ⇒ `metadata` 满足本地 minimum-success（M-18）、`error_kind is None`、`error_detail is None`；非 `SUCCESS` ⇒ `error_kind in T-2[status]`、`error_detail.strip()` 非空；`status in {NOT_FOUND, BLOCKED, RATE_LIMITED, NETWORK_ERROR}` ⇒ `metadata is None`；`status in {PARSE_ERROR, INVALID_RESPONSE}` ⇒ `metadata is None` 或不满足本地 minimum-success。
* `error_detail` 与 `metadata` 的内容永不进入快照、模型、JSON 或 message。

**M-18 `NormalizedMetadata`**（`fc2_metadata_core.models`）

* Projection：`field_sources`（只在作为 `AggregationResult.metadata` 时）。
* Validation-Only：`number`、`title`（本地 minimum-success：`type(number) is str` 且 `is_valid_fc2_number(number)`，且 `type(title) is str` 且 `title.strip() != ""`；`number` / `title` 为 `None` 时视为不满足；其它类型 -> `DiagnosticsIntegrityError`）。
* 不读取：其余全部字段（标题以外的文本、全部 URL、`external_ids`、`runtime` 等）。
* 容器（`field_sources`，第 9.2 节第 9 条，Design-R3）：`type(metadata) is NormalizedMetadata` 后，要求 `type(metadata.field_sources) is types.MappingProxyType`；然后**按顺序**：(i) **有界单遍 key 扫描**——对 stored key 计数、超过 `MAX_PROVENANCE_KEYS` 立即 `DiagnosticsResourceLimitError`、逐个确认 `type(key) is str`（含 unknown key；扫描期间禁止 `in` / 下标 / 相等 / hash 敏感操作，禁止先物化再检查）；(ii) 仅在全部 stored key 扫描并 exact-`str` PASS 之后，**才**按 `PROVENANCE_FIELD_ORDER` 的固定字段名逐个查询（`name in proxy` / `proxy[name]`），输出顺序只由 `PROVENANCE_FIELD_ORDER` 决定、不依赖插入顺序；(iii) 每个被找到的 value 为精确 `tuple`、非空、元素先逐个确认为精确 `str`（Phase V）、再满足安全 id 规则且两两不同、都在 `contributing_source_ids` 中（Phase R）；未找到的 known field 即 absence；不属于 `PROVENANCE_FIELD_ORDER` 的 unknown key：**被扫描并计入上限，但不投影、不输出、不读取其 value**。**不 introspect proxy 的被包装对象。**
* 资源（`field_sources`）：stored key 数 `<= MAX_PROVENANCE_KEYS`（`64`，第 8.3 节）；第 `65` 个 key 在被观察时立即 `DiagnosticsResourceLimitError`；全程不建立无界 list / tuple / set / dict。
* `SourceResult.metadata`（M-17 内的 `NormalizedMetadata`）**不**读取 `field_sources`（只读 `number` / `title`），因此不对其执行 key 扫描。
* 跨对象：见第 9.6.6 节（provenance 与 contributing 的关系）。
* 绝不调用 `NormalizedMetadata.__post_init__` 或 `meets_minimum_success()`；`number` / `title` 永不进入快照、模型、JSON 或 message。

**M-19 `SourceExecutionTrace`**（`fc2_metadata_core.aggregation`）

* Projection：`attempts`、`max_attempts`、`deadline_exceeded`、`deadline_during`。
* Validation-Only：`source_id`、`final_result`（M-17，完整校验）。
* 容器：`attempts` 精确 `tuple`，元素精确 `SourceAttempt`。
* 标量：`source_id` 非空 str；`max_attempts` int≥1；`deadline_exceeded` 精确 `bool`；`deadline_during` 为 `None`、`"attempt"` 或 `"backoff"`（精确 `str`）。
* 跨对象（Phase 3 resilience 合同 / C2-L2 / C5）：`final_result.source_id == source_id`；`attempts == ()` 当且仅当 `final_result.error_kind is CIRCUIT_OPEN`，此时 `deadline_exceeded is False` 且 `deadline_during is None`；否则：sequence 恰为 `1..n`；`n <= max_attempts`；只有最后一项可 `completed is False`；最后一项之前没有 `SUCCESS`；最后一项之前每项 `error_kind in RETRY_ELIGIBLE_KINDS`；`deadline_exceeded` ⇒ `deadline_during` 非 `None`、`final_result` 为 `NETWORK_ERROR` / `SOURCE_DEADLINE`，`"attempt"` ⇒ 最后一项未完成，`"backoff"` ⇒ 最后一项已完成、`error_kind in RETRY_ELIGIBLE_KINDS`、`n < max_attempts`；非 `deadline_exceeded` ⇒ `deadline_during is None`、最后一项已完成、`final_result.status is last.status` 且 `final_result.error_kind is last.error_kind`。
* 资源：`len(attempts) <= MAX_ATTEMPTS_PER_SOURCE`（迭代前）。

**M-20 `SourceAttempt`**（`fc2_metadata_core.aggregation`）

* Projection：`sequence`、`status`、`error_kind`、`completed`；`elapsed_ms`、`backoff_before_seconds`（仅 `TimingPolicy.INCLUDE`）。
* Validation-Only：`elapsed_ms`、`backoff_before_seconds`（任何策略下的数值检查）。
* 标量 / 枚举：`sequence` int≥1；`status` 精确 `SourceStatus`；`error_kind` opt 精确 `SourceErrorKind`；`elapsed_ms`、`backoff_before_seconds` 精确 `int` / `float`、有限、≥0；`completed` 精确 `bool`。
* 跨对象：`SUCCESS` ⇔ `error_kind is None`；非 `SUCCESS` ⇒ `error_kind in T-2[status]`；`completed is False` ⇒ `NETWORK_ERROR` / `SOURCE_DEADLINE`；`sequence == 1` ⇒ `backoff_before_seconds == 0`。

**M-21 `FieldConflict`**（`fc2_metadata_core.aggregation`）

* Projection：`field`、`selected_source_id`、`alternatives` 中每对的第 0 项（source id）。
* Validation-Only：`key`、`selected_value`、`alternatives` 中每对的第 1 项（value）。
* 容器：`alternatives` 精确 `tuple`、非空，元素为精确 2-tuple。
* 标量：`field` 精确 `str` 且 `in CONFLICT_FIELDS`；`selected_source_id` 非空 str；`selected_value` 精确 `str` 或精确 `int`（非 bool）；每个 alternative 的 id 非空 str、value 精确 `str` 或精确 `int`；`key`：`field == "external_ids"` 时精确 `str` 且 `strip()` 非空，否则 `None`。
* 跨对象：alternative id 唯一且都 `!= selected_source_id`；不存在与 `selected_value` 类型相同且相等的 alternative value；selected 与全部 alternative id 都在所属 `AggregationResult.contributing_source_ids` 中（第 9.6.6 节）。
* 资源：`len(alternatives) <= MAX_SOURCES_PER_ITEM`（迭代前）。

**M-22 `ImageCandidateFailure`**（`fc2_organizer.images`）

* Projection：`role`、`kind`、`http_status`。
* Validation-Only：`candidate_index`。
* 标量：`role` 精确 `ImageRole`；`candidate_index` int≥0；`kind` 精确 `ImageFailureKind`；`http_status`：`kind is HTTP_STATUS` 时为 int 且 `100..599`，否则 `None`。

**M-23 `ExecutionPreflight`**（`fc2_organizer.execution`）

* Projection：`mode`、`ready`、`blockers`、`transfer_mode`、`pending_units` / `completed_units`（只取长度）、`skipped_steps`、`artifacts`（只经 M-24 读取 `kind`）。
* Validation-Only：`preflight_id`、`plan`、`checkpoint`、`plan_fingerprint`、`manifest_fingerprint`、`seal`。
* 容器：`artifacts` 精确 `tuple`，元素精确 `ArtifactWriteRequest`；`blockers` 精确 `tuple`，元素精确 `PreflightBlocker`；`pending_units`、`completed_units` 精确 `tuple`，元素精确 `ExecutionUnit`（类型确认）；`skipped_steps` 精确 `tuple`，元素精确 `ExecutionStep` 且属于 `{MATERIALIZE_POSTER, MATERIALIZE_FANART, MATERIALIZE_THUMB}`。
* 标量：`preflight_id` hex32；`mode` 精确 `PreflightMode`；`plan` 精确 `OrganizePlan`；`checkpoint` opt 精确 `ExecutionCheckpoint`（类型确认）；两个 fingerprint 与 `seal` hex64；`ready` 精确 `bool`；`transfer_mode` opt 精确 `TransferMode`。
* 跨对象：`(mode is RESUME) == (checkpoint is not None)`；`ready == (blockers == ())`；`plan is` 所属条目的 `plan`；artifacts 与 plan 的 manifest 关系见第 9.6.5 节。
* 资源：`len(blockers) <= MAX_BLOCKERS_PER_ITEM`（迭代前）。

**M-24 `ArtifactWriteRequest`**（`fc2_organizer.materialization`）

* Projection：`kind`（只计数）。
* Validation-Only：`target_path`、`content`（只 `type()`）、`ordinal`。
* 标量：`kind` 精确 `ArtifactKind`；`target_path` 非空 str；`content` 精确 `bytes`（只确认类型；不读取、不复制、不切片、不计算哈希）；`ordinal`：`kind is EXTRAFANART` 时 int≥1，否则 `None`。
* 跨对象：manifest 顺序与目标路径关系（第 9.6.5 节，P4-C6 合同第 18 节）。

**M-25 `PreflightBlocker`**（`fc2_organizer.execution`）

* Projection：整体携带（第 20 节）。
* 标量：`reason` 精确 `PreflightBlockReason`；`role` 精确 `PathRole`；`errno` opt 精确 `int`；`ordinal` opt int≥1。

**M-26 `ExecutionResult`**（`fc2_organizer.execution`）

* Projection：`status`、`mode`、`transfer_mode`、`completed_effects`（只经 M-27 读取 `kind` / `artifact_kind`）、`new_effect_count`、`failure`、`checkpoint`（只作 `is None`）、`leftover_temporaries`、`skipped_steps`。
* Validation-Only：`preflight_id`、`media_sha256`。
* 容器：`completed_effects` 精确 `tuple`，元素精确 `CompletedEffect`；`leftover_temporaries` 精确 `tuple`，元素精确 `LeftoverTemporary`；`skipped_steps` 同 M-23。
* 标量：`status` 精确 `ExecutionStatus`；`mode` 精确 `PreflightMode`；`preflight_id` hex32；`transfer_mode` opt 精确 `TransferMode`；`new_effect_count` int≥0 且 `<= len(completed_effects)`；`failure` opt 精确 `ExecutionFailure`；`checkpoint` opt 精确 `ExecutionCheckpoint`（类型确认）；`media_sha256` opt hex64。
* 跨对象（P4-C7 合同第 27 节）：`(status is SUCCESS) == (failure is None)`；`(status is PARTIAL) == (checkpoint is not None)`；`FAILED` ⇒ `completed_effects == ()`；非 `FAILED` ⇒ `completed_effects != ()`。
* 资源：`len(leftover_temporaries) <= MAX_LEFTOVER_TEMPORARIES_PER_ITEM`（迭代前）。`completed_effects` 只被计数，无单独上限。

**M-27 `CompletedEffect`**（`fc2_organizer.execution`）

* Projection：`kind`、`artifact_kind`（只计数）。
* Validation-Only：`role`、`ordinal`。
* 不读取：`path`、`identity`、`size`、`sha256`。
* 标量 / 跨字段（P4-C7 合同第 14.2 节，第 9.8 节表 T-3）：`kind` 精确 `EffectKind`；`role` 精确 `PathRole`；`artifact_kind` opt 精确 `ArtifactKind`；`ordinal` opt 精确 `int`；`kind is ARTIFACT_PUBLISHED` ⇔ `artifact_kind is not None`；`ARTIFACT_PUBLISHED` ⇒ `role is T-3[artifact_kind]`，`ordinal` 在 `EXTRAFANART` 时 int≥1、否则 `None`；其它 kind ⇒ `ordinal is None` 且 `role is` 该 kind 的冻结 role（`SOURCE_REMOVED` -> `SOURCE`、`MEDIA_PUBLISHED` -> `TARGET_MEDIA`、`TARGET_DIRECTORY_CREATED` -> `TARGET_DIRECTORY`、`EXTRAFANART_DIRECTORY_CREATED` -> `EXTRAFANART_DIRECTORY`）。

**M-28 `ExecutionFailure`**（`fc2_organizer.execution`）

* Projection：整体携带（第 20 节）。
* 标量 / 跨字段（P4-C7 合同第 27 节）：`step` 精确 `ExecutionStep`；`kind` 精确 `ExecutionFailureKind`；`stage` opt 精确 `TransferStage`；`write_stage` 为 `None` 或精确 `str` 且属于 `{"write", "flush", "close"}`，且非 `None` 时 `kind is ARTIFACT_WRITE_FAILED`；`errno` opt 精确 `int`；`artifact_kind` opt 精确 `ArtifactKind`；`ordinal` opt int≥1，且非 `None` 时 `artifact_kind is EXTRAFANART`；`target_published` 为 `None` 或精确 `bool`，且非 `None` 时 `kind in {ARTIFACT_CLEANUP_FAILED, MEDIA_TEMP_CLEANUP_FAILED}`。

**M-29 `LeftoverTemporary`**（`fc2_organizer.execution`）

* Projection：`directory_role`；`name`（**仅** `PathPolicy.BASENAME`）。
* Validation-Only：`name`（任何策略下的格式检查）。
* 标量：`directory_role` 精确 `PathRole` 且属于 `{TARGET_DIRECTORY, EXTRAFANART_DIRECTORY}`；`name` 精确 `str` 且完全匹配 `\.fc2tmp-[0-9a-f]{32}\.part`。

**M-30 `RetryMaterial`**（`fc2_organizer.orchestration`；仅作为 `ItemExecution.retry_material`，P4-C8 合同第 10.5、10.6 节）

* Projection：无（诊断只输出 `retry_material_retained = (retry_material is not None)`）。
* Validation-Only：`plan`、`artifacts`、`checkpoint`；其中 `artifacts` 的每项只经 M-24 校验，`len(content)` 只用于本地 retained 字节求和（第 9.6.1 / 9.6.2 节），**不复制、不序列化、不输出** `content`。
* 容器：`artifacts` 精确 `tuple`，元素精确 `ArtifactWriteRequest`（M-24：含 `type(content) is bytes`）。
* 标量 / 枚举：`type(material) is RetryMaterial`；`plan` 精确 `OrganizePlan`（M-11 校验）；`checkpoint` 为 `None` 或精确 `ExecutionCheckpoint`（M-04，类型确认）。
* 跨对象：`material.plan is item.plan`（同一对象，不是 `==`、不是路径相同、不是内容相同）；与 `retry_kind` / `execution.checkpoint` 的关系见第 9.6.4 节。
* 资源：`artifacts` 无单独条数上限（与既有 `ExecutionPreflight.artifacts` 同；其总字节受第 9.6.1 / 9.6.2 节预算约束）。
* 不得调用 `RetryMaterial.__post_init__`、`retry_payload_bytes` 或 `BatchExecutionResult.retained_retry_payload_bytes` / `BatchPreview.retained_artifact_bytes`（这些 property / 函数的实现依赖尚未验证的图）；必须本地计算。

以上 30 行覆盖原第 9.2 节全部类型（`BatchPreview`、`BatchExecutionResult`、`ItemPreview`、`ItemExecution`、`ItemIssue`、
`PreviewSummary`、`ExecutionSummary`、`DiscoveredMediaItem`、`OrganizePlan`、`PlannedPath`、`BatchResult`、`BatchItemResult`、
`AggregationResult`、`SourceResult`、`SourceExecutionTrace`、`SourceAttempt`、`NormalizedMetadata`、`FieldConflict`、
`ImageCandidateFailure`、`ExecutionPreflight`、`ArtifactWriteRequest`、`PreflightBlocker`、`ExecutionResult`、`CompletedEffect`、
`ExecutionFailure`、`LeftoverTemporary`），以及为完整性新增的 `BatchLineage`、`PlannedOperation`、`OutputPolicy`、
`ImageAcquisitionPolicy`、`RetryMaterial`、`ExecutionCheckpoint`、`ExecutionUnit`。表外没有任何被消费的上游类型。

### 9.6 跨对象检查（冻结）

#### 9.6.1 `BatchPreview`（P4-C8 合同第 10.4 节）

* `is_main := base_result_id is None`；`(retry_scope is None) == is_main`；`(generation == 0) == is_main`；`(retry_budget_bytes is None) == is_main`。
* `lineage.token == metadata_batch.lineage.token`。
* 条目 index：`is_main` 时恰为 `0..batch_size-1`（`len(items) == batch_size`，第 i 项 `index == i`）；否则严格递增且每个 `< batch_size`。
* 每个条目 `generation == batch.generation`；`not is_main` 时每个条目 `retry_origin in retry_scope`（先完成 frozenset 元素迭代确认）。
* 每个有 metadata 的条目：`metadata_position < len(metadata_batch.items)` 且 `item.metadata is metadata_batch.items[metadata_position]`。
* 冲突图：每个 `conflict_with` 中的 index 都是同一 `items` 中某条目的 index，且对称（对方的 `conflict_with` 含本条目 index）。
* 每个有 plan 的条目：`plan.library_root == batch.library_root`。
* **retained artifact 预算（本地计算，P4-C8 合同第 10.4 节）**：对每个有 `preflight` 的条目，遍历（已按 M-23 / M-24 校验的）精确
  tuple `preflight.artifacts`，只读 `len(request.content)`（`type(content) is bytes` 已确认）并求和——每个 request 按**引用**逐个
  计数（共享 bytes 重复计数）；总和 `retained` 必须满足：`is_main` 时 `retained <= retention_budget_bytes`，否则
  `retained <= retry_budget_bytes`（此时 `retry_budget_bytes` 已确认非 `None`）。不得复制 / 序列化 / 输出 bytes，不得调用
  `BatchPreview.retained_artifact_bytes`。此检查在读取 `summary` 之前完成（第 24.2 节第 5 步）。

#### 9.6.2 `BatchExecutionResult`（P4-C8 合同第 10.7 节）

* 本地 shape 判定（恰一种成立，否则 `DiagnosticsIntegrityError`）：
  * `MAIN`：`generation == 0`、`base_result_id is None`、`retry_scope is None`、`retry_budget_bytes is None`、`preview_id is not None`；
  * `RETRY`：`generation >= 1`，`base_result_id`、`retry_scope`、`preview_id`、`retry_budget_bytes` 均非 `None`；
  * `MERGED`：`generation >= 1`、`base_result_id is None`、`retry_scope is None`、`retry_budget_bytes is None`、`preview_id is None`。
* `lineage.token == metadata_batch.lineage.token`。
* 条目 index：`MAIN` / `MERGED` 时恰为 `0..batch_size-1`；`RETRY` 时严格递增且每个 `< batch_size`。
* `MAIN` / `RETRY` 时每个条目 `generation == batch.generation`；`MERGED` 时每个条目 `generation <= batch.generation`。
* 冲突图对称（同 9.6.1）；每个有 plan 的条目 `plan.library_root == batch.library_root`。
* **retained retry payload 预算（本地计算，P4-C8 合同第 10.7 节）**：对每个 `retry_material is not None` 的条目，遍历其（已按
  M-30 / M-24 校验的）精确 tuple `material.artifacts`，只读 `len(request.content)` 并求和，每个 request 按**引用**逐个计数（共享
  bytes 重复计数，与 P4-C8 冻结语义一致）；总和 `retained` 必须满足：本地 shape 为 `MAIN` / `MERGED`（complete）时
  `retained <= retention_budget_bytes`；`RETRY` 时 `retained <= retry_budget_bytes`。同时 `retention_budget_bytes`、
  `retry_budget_bytes` 自身的冻结范围 / shape 关系按 M-02 / 第 9.6.2 节 shape 判定先行检查（`retry_budget_bytes` 非 `None` 时
  `0 <= retry_budget_bytes <= retention_budget_bytes`）。不得复制 / 序列化 / 输出 bytes，不得调用
  `BatchExecutionResult.retained_retry_payload_bytes` 或 `retry_payload_bytes`，并且该检查**不得**留给上游 `__post_init__`；它在
  读取 `summary` / `outcome` 之前完成（第 24.2 节第 5 步）。
* （P4-C8 的 metadata 身份关系只对 preview 冻结；merged 结果的条目可来自不同代的 metadata 批，因此 execution 不检查
  `metadata is metadata_batch.items[...]`。）

#### 9.6.3 `ItemPreview`（P4-C8 合同第 10.3 节）

* `(canonical_number is None) == (issue is not None and issue.reason is NUMBER_NOT_RECOGNIZED)`。
* `(metadata_position is None) == (metadata is None)`；有 metadata 时 `metadata.number == canonical_number`、`metadata.index == metadata_position`。
* 有 plan 时：`plan.canonical_number == canonical_number`；`plan.source_path == media_item.source_path`、`plan.source_relative_path == media_item.relative_path`、`plan.source_extension == media_item.extension`、`plan.source_index == media_item.index`、`plan.source_size == media_item.size`。
* `conflict_with` 严格递增且不含自身 index。
* 有 preflight 时：`plan is not None` 且 `preflight.plan is plan`。
* `issue` 有值时 `issue.stage is not EXECUTION`。
* `executable := preflight is not None and preflight.ready is True and conflict_with == ()`；`(state is READY) == (issue is None) == executable`。
* 有 issue 时：`(state is BLOCKED) == (issue.reason in T-4 BLOCKED_REASONS)`；`PREFLIGHT_BLOCKED` ⇒ `preflight is not None`、`preflight.ready is False`、`blockers != ()`、`conflict_with == ()`；`DUPLICATE_SOURCE_IN_BATCH` / `DUPLICATE_TARGET_IN_BATCH` ⇒ `conflict_with != ()`；其它 reason ⇒ `preflight is None` 且 `conflict_with == ()`。
* `(retry_origin is None) == (generation == 0)`。

#### 9.6.4 `ItemExecution`（P4-C8 合同第 10.6 节）

* 与 9.6.3 相同的 canonical / metadata / plan / `conflict_with` 规则（除 preflight 相关项外）。
* `(execution is None) == (disposition is not EXECUTED)`。
* `NOT_READY` ⇒ `preview_state is not READY`、`issue is not None`、`issue.stage is not EXECUTION`、`(preview_state is BLOCKED) == (issue.reason in BLOCKED_REASONS)`。
* 其它 disposition ⇒ `preview_state is READY`；`EXECUTED` 且 `execution.status is SUCCESS` ⇒ `issue is None`；`EXECUTED` 且 `FAILED` / `PARTIAL` ⇒ `issue.reason is EXECUTION_FAILED` / `EXECUTION_PARTIAL`、`execution.failure is not None`、`issue.detail is execution.failure.kind`；`NOT_SELECTED` / `CANCELLED` ⇒ `issue is None`；`REJECTED` ⇒ `issue.reason is EXECUTION_REJECTED`；`ABORTED` ⇒ `issue.reason is EXECUTION_ABORTED`。
* **`retry_kind` 的本地推导（冻结，P4-C8 合同第 25.1 节纯函数；P4-C9 只验证、不重新定义业务规则）**：在上面的 disposition /
  issue / execution 关系已确认后，由已精确校验的公开字段本地推导 `expected_kind`：
  * `EXECUTED`：`execution.status is SUCCESS` -> `NONE`；`PARTIAL` -> `RESUME`；`FAILED` -> `FRESH_REEXECUTE`；
  * `NOT_READY`：`issue.stage is METADATA` -> `METADATA_REFETCH`；否则 `issue.reason is PREFLIGHT_BLOCKED` -> `PREFLIGHT_RECHECK`；
    否则 `NONE`；
  * `NOT_SELECTED` / `CANCELLED` -> `DEFERRED`；`REJECTED` / `ABORTED` -> `NONE`。
  P4-C9 **不能只信任** `ItemExecution.retry_kind` property：该 property 只在第 24.2 节第 7 步读取，并要求其返回值 `is expected_kind`
  （精确 `RetryKind` 成员），否则 `DiagnosticsIntegrityError`。
* **`retry_material` 关系（冻结，P4-C8 合同第 10.6 节；以 `expected_kind` 判定，在 projection 之前）**：
  * 存在性：`(retry_material is not None) == (expected_kind in {PREFLIGHT_RECHECK, FRESH_REEXECUTE, RESUME, DEFERRED})`；
    `NONE` 与 `METADATA_REFETCH` 不保留 material。
  * 当 material 存在：按 M-30 本地校验（`type(material) is RetryMaterial`、`type(material.plan) is OrganizePlan`、
    `type(material.artifacts) is tuple` 且每项精确 `ArtifactWriteRequest`、`checkpoint` 为 `None` 或精确 `ExecutionCheckpoint`）；
    **`material.plan is item.plan`**（同一对象，不是 `==`、不是路径相同、不是内容相同）。
  * `RESUME`：`execution is not None`、`execution.checkpoint is not None`、`material.checkpoint is not None` 且
    `material.checkpoint is execution.checkpoint`（同一对象）。
  * `FRESH_REEXECUTE`：`material.checkpoint is None`。
  * `PREFLIGHT_RECHECK` / `DEFERRED`：P4-C8 合同第 10.6 节冻结其 `checkpoint is` 该条目 preview preflight 的 `checkpoint`（可为
    `None`）；但 `ItemExecution` 不携带 preflight，P4-C9 无从核对，且 P4-C8 对这两种 kind 没有任何额外的 checkpoint 状态约束。
    因此 P4-C9 对它们**只**要求 M-30 的类型约束（`None` 或精确 `ExecutionCheckpoint`），**不得**擅自增加更严格的规则。
  * `retry_material_retained`（诊断输出）因此恒等于上述已校验的存在性关系；任何矛盾在 projection 之前 fail closed。
* `(conflict_with != ()) == (issue is not None and issue.reason in DUPLICATE_REASONS)`；`preview_state is READY` ⇒ `plan is not None`。
* warnings：`(METADATA_PARTIAL in warnings) == (metadata is not None and metadata.status is PARTIAL)`；`(IMAGE_CANDIDATE_FAILURES in warnings) == (image_failures != ())`；`(LEFTOVER_TEMPORARIES in warnings) == (execution is not None and execution.leftover_temporaries != ())`；`preview_state is UNPREPARED` 或 `plan is None` ⇒ warnings 不含 `POSTER_ABSENT` / `FANART_ABSENT` / `THUMB_ABSENT` / `NO_EXTRAFANART`。

#### 9.6.5 plan / media / manifest（P4-C2 合同第 4、7、11、14 节；P4-C6 合同第 18 节）

* `td := plan.target_directory.absolute_path`；`td == os.path.join(plan.library_root, plan.canonical_number)`。
* `plan.target_media_path.absolute_path == os.path.join(td, plan.canonical_number + plan.source_extension.lower())`。
* 对 `nfo_path`、`poster_path`、`fanart_path`、`thumb_path`、`extrafanart_directory` 中每个 `p`：`b := os.path.basename(p.absolute_path)` 非空，且 `os.path.join(td, b) == p.absolute_path`。七个路径字符串两两不同。
* `operations` 的 kind 依次恰为 `CREATE_DIRECTORY`、`MOVE_MEDIA`、`MATERIALIZE_NFO`、`MATERIALIZE_POSTER`、`MATERIALIZE_FANART`、`MATERIALIZE_THUMB`、`ENSURE_EXTRAFANART_DIRECTORY`，其 `target.absolute_path` 依次等于 `td`、target media、nfo、poster、fanart、thumb、extrafanart 目录；`MOVE_MEDIA.source.absolute_path == plan.source_path`；其余 `source is None`。
* manifest（`ExecutionPreflight.artifacts`）：第 0 项 `kind is NFO` 且 `target_path == plan.nfo_path.absolute_path`；随后为 `POSTER`、`FANART`、`THUMB` 中各至多一项、按此顺序，`target_path` 分别等于对应 plan 路径；再随后全部为 `EXTRAFANART`，`ordinal` 依次恰为 `1..k`，每项 `os.path.join(plan.extrafanart_directory.absolute_path, os.path.basename(target_path)) == target_path`；不存在其它项。
* 由此，一个被篡改的 plan 不会仅因“目标路径字段看起来像 str”就被接受：目标目录、目标媒体名、全部子路径与操作序列都必须与冻结的结构性布局逐字符一致。

#### 9.6.6 metadata / source / provenance（Phase 3 聚合合同第 3、5.6 节；resilience 合同）

* `source_results` 的 `source_id` 两两不同；`disabled_source_ids` 每项 `strip()` 非空、两两不同、不与 `source_results` 的 id 重叠。
* `successful := [r.source_id for r in source_results if r.status is SUCCESS]`（按原顺序）；`status is FAILED` ⇒ `contributing_source_ids == ()`、`metadata is None`、`successful == []`；否则 `contributing_source_ids` 与 `successful` 逐项相等、`metadata` 满足本地 minimum-success、`metadata.number == number`、`successful` 非空；`SUCCESS` ⇒ 没有 `status in OPERATIONAL_FAILURE_STATUSES` 的 source；`PARTIAL` ⇒ 至少一个。
* `source_execution_traces` 为空，或与 `source_results` 等长且逐位置 `trace.source_id == result.source_id`、`trace.final_result.status is result.status`、`trace.final_result.error_kind is result.error_kind`。
* 每个 `FieldConflict` 的 selected 与全部 alternative id 都在 `contributing_source_ids` 中。
* provenance：`metadata` 非 `None` 时，先完成 `field_sources` 的有界单遍 key 扫描与 exact-`str` 验证（第 9.2 节第 9 条 Step 1-3），其后才按 `PROVENANCE_FIELD_ORDER` 的固定字段名逐个查询（Step 4），每个被找到的 value 非空、元素（先精确类型、后）两两不同且都在 `contributing_source_ids` 中（Step 5）；不属于 `PROVENANCE_FIELD_ORDER` 的 unknown key 被扫描并计入 `MAX_PROVENANCE_KEYS`，但不投影、不输出（投影白名单，不是静默丢失必需 schema 字段）；`metadata is None` 时没有 provenance，也不执行 key 扫描。

### 9.7 安全输出检查（第 24.2 节第 6 步，冻结）

对**将要进入诊断模型**的值（只针对 Projection Reads）：source id（含 provenance、conflict、disabled、trace）满足第 17.2 节安全 id
规则；`error_type` 满足标识符规则；`PathPolicy.BASENAME` 下的每个 basename 满足第 18.2 节词法安全规则；`TimingPolicy.INCLUDE`
下的计时值满足 `0 <= v <= MAX_TIMING_MS`（转换后）。失败抛 `DiagnosticsUnsafeValueError`。`PathPolicy.NONE` 下不计算任何
basename。

### 9.8 本地冻结表（冻结；测试断言与上游实现相等）

* **T-1** `ItemIssue` reason 表：逐项抄自 P4-C8 合同第 10.2 节（reason -> stage、是否需要 `error_type`、允许的 detail 枚举类型、
  是否需要 detail）。
* **T-2** `SourceStatus` -> 允许的 `SourceErrorKind` 集合：逐项抄自 Phase 3 resilience 合同（`ALLOWED_ERROR_KINDS`；该常量不在
  裸 package 公开导出中，因此本地冻结）。
* **T-3** `ArtifactKind` -> `PathRole`：`NFO -> NFO`、`POSTER -> POSTER`、`FANART -> FANART`、`THUMB -> THUMB`、
  `EXTRAFANART -> EXTRAFANART_FILE`（P4-C7 合同第 14.2 节）。
* **T-4** `BLOCKED_REASONS = {PREFLIGHT_BLOCKED, DUPLICATE_SOURCE_IN_BATCH, DUPLICATE_TARGET_IN_BATCH}`；
  `DUPLICATE_REASONS = {DUPLICATE_SOURCE_IN_BATCH, DUPLICATE_TARGET_IN_BATCH}`（P4-C8 合同第 10.3 节）。
* 第 11.4 节 detail 类型名表。

### 9.9 禁止读取（冻结）

* 任何以 `_` 开头的属性或方法（含全部 dunder），模块级私有 registry（例如 P4-C8 `_consumption`），线程或 asyncio 状态。
* 第 9.5 节未列出的任何字段，包括：`SourceResult` 的 metadata 文本字段、`NormalizedMetadata` 中除 `number` / `title` /
  `field_sources` 外的全部字段、`ArtifactWriteRequest.content` 的内容、`CompletedEffect.path` / `identity` / `size` / `sha256`、
  `ExecutionCheckpoint` / `RetryMaterial` / `ExecutionUnit` / `OutputPolicy` / `ImageAcquisitionPolicy` 的字段、
  `ExecutionPreflight.library_root_identity` / `source_identity`。
* Validation-Only 字段（含 `error_detail`、`number` / `title`、`library_root`、各类 id / fingerprint / seal / token、
  `target_path`、`FieldConflict` 的值与 key）永不进入快照、模型、JSON 或 message。

### 9.10 Caller-Originated Operation / Dispatch Safety Matrix（冻结，Design-R3）

本矩阵**只**覆盖 P4-C9 production **实际执行**的、作用于 caller-originated 值（输入模型图中的对象、容器、标量）的操作；P4-C9 不对 caller-originated 值执行的操作类别，以“**NOT USED**”行
明确冻结为禁止。列含义：**Operand** = 被操作的 caller-originated 值的类型；**Dispatch Surface** = 该操作可能执行的 Python 级分派（调用方代码入口）；**Required Precondition** = 该
操作之前**必须**已完成的 exact-type 校验（规范性，第 9.0.1 节）；**Why Safe** = 满足前置条件后为什么不存在调用方代码分派；**Failure** = 前置条件不满足时 P4-C9 的行为（均在该操作发生**之前**
fail closed，固定措辞，无值文本）。

| ID | Operation | Operand | Possible Dispatch Surface | Required Precondition | Why Safe | Failure If Precondition Not Met |
|---|---|---|---|---|---|---|
| D-01 | iteration | exact `tuple`（`items`、`source_results`、`source_execution_traces`、`contributing_source_ids`、`disabled_source_ids`、`conflicts`、`alternatives`、`attempts`、`blockers`、`leftover_temporaries`、`artifacts`、`completed_effects`、units、`skipped_steps`、`image_failures`、`conflict_with`、`operations`、`warnings`） | tuple 迭代器（内建）；元素的任何方法都不被调用 | `type(c) is tuple`；第 21.2 节结构上限已在迭代前检查；迭代体内对每个元素的**第一个**操作是 `type(e) is X` | 内建 tuple 迭代只交出元素引用，不调用元素的 `__iter__` / `__eq__` / `__hash__` / `__bool__` / `__getattribute__` | 非 exact tuple → `DiagnosticsIntegrityError`；超上限 → `DiagnosticsResourceLimitError`（均在迭代前） |
| D-02 | iteration | exact `frozenset`（仅 `retry_scope`） | frozenset 迭代器（内建）；不重新哈希、不比较元素 | `type(c) is frozenset`；迭代体内第一个操作为 `type(e) is RetryKind` 且 `e is not RetryKind.NONE`；遇首个违规立即失败（天然有界，第 9.2 节第 10 条） | 内建 frozenset 迭代只交出元素引用 | `DiagnosticsIntegrityError` |
| D-03 | iteration（仅 key，仅 validation） | exact `types.MappingProxyType`（仅 `NormalizedMetadata.field_sources`；仅作为 `AggregationResult.metadata` 时） | proxy → 被包装 mapping 的 key 迭代器；A 层被包装对象是上游新建的私有 exact `dict`，其 key 迭代不调用 key 的任何方法 | `type(metadata) is NormalizedMetadata`；`type(proxy) is MappingProxyType`；单遍计数且计数 `<= MAX_PROVENANCE_KEYS`；对每个 key 的**唯一**操作是 `type(key) is str`（第 9.2 节第 9 条 Step 3） | dict key 迭代只交出 key 引用，不执行 `__hash__` / `__eq__` / `__repr__`；`type(key)` 不读取 `__class__`；C 层 hidden-referent 伪造不在支持范围（第 9.0 节） | key 数超限 → `DiagnosticsResourceLimitError`（观察到第 65 个 key 时立即）；非 exact `str` key → `DiagnosticsIntegrityError` |
| D-04 | `len` | exact `tuple` / `frozenset` | 内建 `len`，无元素分派 | 精确容器类型已确认 | 内建容器 `len` 不调用元素方法 | `DiagnosticsIntegrityError` |
| D-05 | `len` | exact `bytes`（`ArtifactWriteRequest.content`）、exact `str` | 内建 | `type(content) is bytes` / `type(s) is str`；`content` 只求 `len`（不读取、不切片、不复制、不哈希、不比较） | exact `bytes` / `str` 的 `len` 是内建 | `DiagnosticsIntegrityError` |
| D-06 | `len` | `MappingProxyType` | — | **NOT USED**：`len(proxy)` 与“先 `len` 后迭代”的两段式都不使用；Step 3 以单遍计数代替（第 9.2 节第 9 条） | N/A | N/A |
| D-07 | subscript | exact `tuple` 按 exact `int` 下标（`metadata_batch.items[metadata_position]`、`operations[i]`、计数对 `pair[0]` / `pair[1]`） | tuple `__getitem__`（内建） | exact tuple；下标 `type(i) is int` 且 `0 <= i < len(t)` 已先检查 | 内建；不依赖捕获 `IndexError` | `DiagnosticsIntegrityError` |
| D-08 | subscript + membership | `proxy[name]` / `name in proxy`，`name` 为 `PROVENANCE_FIELD_ORDER` 的本模块 exact-`str` 常量 | dict 的 hash 查找：对 stored key 做 `==`；若 stored key 是 `str` 子类则分派其 `__eq__`（其 `__hash__` 已在上游建立 dict 时发生） | **全部** stored key 已完成 D-03 并 exact-`str` PASS（Step 3 完整结束）；先 `in` 后下标 | 此时 stored key 全是 exact `str`，只发生 `str.__hash__` / `str.__eq__`；A 层 proxy 的 dict 是上游新建的私有 exact dict（第 9.0 节 U-1），不是调用方持有的映射；不使用 `gc` / 反射 / referent introspection | 未完成 D-03 不得到达本行（Integrity / ResourceLimit 已先抛出） |
| D-09 | hash-dependent lookup | 本地冻结 dict / set（T-1..T-4、枚举成员集合、`{"write","flush","close"}` 等）按 exact 枚举成员 / exact `str` / exact `int` 取值 | 枚举成员 `__hash__`（上游枚举，类含成员不可被继承）；`str` / `int` 内建 hash | 查表键已 `type(k) is Enum / str / int` 确认 | 键 exact；表是本地 / 上游冻结常量，不含 caller-originated 元素 | `DiagnosticsIntegrityError`（查表前拒绝） |
| D-10 | hash-dependent lookup | P4-C9 **本地**构造的 set / dict，其元素 / 键来自 caller-originated 值（id 唯一性集合、按 `index` 的条目索引、`(role, kind)` 分组、`http_status` 集合） | 内建 hash；键若是子类则分派 | 放入 set / dict 之前该值已 `type(v) is str / int / ImageRole / ImageFailureKind` 确认（该来源容器 Phase V 已完成） | 键 exact | `DiagnosticsIntegrityError` |
| D-11 | membership `in` | exact `tuple` 容纳 caller-originated id / `int`（`x in contributing_source_ids`、`idx in other.conflict_with`、`warning in warnings`） | `tuple.__contains__` → 逐元素 `==`（元素若为子类则分派其 `__eq__`） | 该容器的 **Phase V 已全部完成**（全部元素 exact `str` / exact `int` / exact 枚举）；被查值 exact | 双方 exact；`str.__eq__` / `int.__eq__` / 枚举身份相等 | Phase V 失败 → `DiagnosticsIntegrityError`，不到达 Phase R |
| D-12 | membership `in` | exact `frozenset`（`retry_origin in retry_scope`；第 12.8 节按声明顺序逐个判定成员） | frozenset hash 查找 → 元素 `__hash__` / `__eq__` | D-02 迭代已**完整**通过（全部元素 exact `RetryKind` 且非 `NONE`）；被查值 exact `RetryKind` | 元素与被查值都是枚举成员，只发生 `Enum.__hash__` / 身份相等 | 迭代失败 → `DiagnosticsIntegrityError`，不做成员判定 |
| D-13 | membership `in` | 上游 / 本地冻结常量容器（`CONFLICT_FIELDS`、`OPERATIONAL_FAILURE_STATUSES`、`RETRY_ELIGIBLE_KINDS`、T-2 / T-3 / T-4、`PROVENANCE_FIELD_ORDER`） | 内建 | 被查值已 exact（枚举成员 / exact `str`） | 容器元素是冻结常量，不含 caller-originated 值 | `DiagnosticsIntegrityError` |
| D-14 | equality `==` / `!=` | exact `str` / `int` / `bool`（含 `selected_value` 与 alternative value 的比较：先 `type(a) is type(b)`）；`None` 一律用 `is` | 内建 | 两侧都已 `type(x) is str / int / bool` 确认 | 内建比较，不分派到用户代码 | `DiagnosticsIntegrityError` |
| D-15 | equality | exact `tuple` 与空 tuple（本合同中所有 `t == ()` / `t != ()`） | tuple 富比较（与空 tuple 比较不触发任何元素比较） | exact tuple。**规范性等价**：本合同全部 `t == ()` / `t != ()` 的含义是 `len(t) == 0` / `len(t) != 0`，实现以 `len` 表达 | 不做通用 tuple 比较 | `DiagnosticsIntegrityError` |
| D-16 | equality | 两个 exact `tuple` / `list` 的逐元素比较（`contributing_source_ids` 与 `successful`；attempts 序号 `1..n`） | 逐元素 `==` | 两侧容器 Phase V 均已完成，元素全部 exact `str` / exact `int` | 内建 | `DiagnosticsIntegrityError` |
| D-17 | identity | `is` / `is not`（枚举成员、`None`、`plan is item.plan`、`checkpoint is ...`、`item.metadata is metadata_batch.items[pos]`） | 无（`is` 不可重载） | 无 | `is` 不执行任何调用方代码 | — |
| D-18 | enum comparison | 枚举成员 | 写成 `==` 会走 `Enum.__eq__`（或子类） | 一律用 `is`（第 9.2 节第 4 条）；枚举值先 `type(v) is Enum` | `is` 不分派 | `DiagnosticsIntegrityError` |
| D-19 | ordering comparison `<` `<=` `>` `>=` | exact `int` / exact `float`（`0 <= v <= MAX`、index / `sequence` 严格递增、预算 `<=`、计时范围） | 内建数值比较 | `type(v) is int` 或 `type(v) is float`（`bool` 已排除）；`float` 另需 `math.isfinite`（D-29） | 内建 | `DiagnosticsIntegrityError`；计时超出 `MAX_TIMING_MS` → `DiagnosticsUnsafeValueError` |
| D-20 | sorting / extremum | `sorted` / `min` / `max` / `list.sort` 作用于 caller-originated 值 | 富比较分派 | **NOT USED**（AST 禁止 `sorted` / `min` / `max`，第 7 节）；所有输出顺序来自冻结常量的声明顺序（第 16 节） | N/A | AST 架构测试失败 |
| D-21 | bool conversion | caller-originated 对象的真值（`if x:`、`not x`、`x and y`、`while x`、`filter`） | `__bool__` / `__len__` | **NOT USED**：只对 exact `bool`（`type(v) is bool`）、比较 / `is None` 的结果、`len(...)` 的比较结果做条件判断；“非空 `str`”以 `len(s) >= 1` 表达，“`strip()` 非空”以 `len(s.strip()) >= 1` 表达（作用于 exact `str`） | N/A | 带 `__bool__` / `__len__` sentinel 的测试失败（第 28.1 节） |
| D-22 | str formatting / text conversion | 任何 caller-originated 值 | `__str__` / `__repr__` / `__format__` | **NOT USED**：不 `str()` / `repr()` / `format()` / f-string / `%` 插入 caller-originated 值；错误 message 只含固定措辞、常量名与 **P4-C9 自有循环计数器**（`enumerate` 位置，**不是**输入的 `item.index` 值） | N/A | AST + sentinel 测试失败 |
| D-23 | regex | `re.fullmatch(<模块级预编译 pattern>, s)`（hex32 / hex64 / 安全 id / `.fc2tmp-…` 名 / BASENAME 之外的固定 grammar） | `re` 引擎 | `type(s) is str`；pattern 是模块级预编译常量（从不由调用方提供）；pattern 为线性（无嵌套量词），不引入灾难性回溯 | exact `str` + 固定线性 pattern | `DiagnosticsIntegrityError` / `DiagnosticsUnsafeValueError` |
| D-24 | path string operation | `os.path.isabs` / `join` / `basename`、`os.sep` / `os.altsep`、`str.startswith`、`str.lower`（`source_extension.lower()`）、`in` 对 exact `str` 的子串判定 | `os.fspath` 协议（仅对非 `str`）；`str` 方法 | `type(p) is str`；纯字符串处理，不 `stat` / `exists` / `resolve` / `open`（第 18.1 节） | exact `str` 不触发 `__fspath__`；不访问文件系统 | `DiagnosticsIntegrityError` |
| D-25 | str method | exact `str`（`strip()`、`isidentifier()`、`startswith`、`lower`、`len`） | 内建 | `type(s) is str` 已先确认 | 内建 | `DiagnosticsIntegrityError` |
| D-26 | dataclass field read | `obj.field`（frozen `slots=True` dataclass 的公开字段，且该字段在第 9.5 节被列出） | 子类的 `__getattribute__` / property / 描述符 | `type(obj) is ExactClass`（V-1） | 精确类的 slot 描述符，无调用方代码；未列出字段不被读取（第 9.9 节） | 子类 → `DiagnosticsIntegrityError`，字段不被读取 |
| D-27 | type test | `type(x) is C`；`type(x) in <本地 frozenset of classes>` | `type()` 不读取 `__class__`；`is` 不可重载；类对象 hash 为身份 hash | 无 | hostile `__class__` / `__eq__` 不影响 `type(x)` | — |
| D-28 | public property | 第 9.3 节五个批准 property（`BatchPreview.summary`、`BatchExecutionResult.summary` / `outcome`、`ItemPreview.warnings`、`ItemExecution.retry_kind`） | CLOSED package 的已冻结 property 代码；经其读取的字段分派 | 第 9.3.1 节依赖图**全部**已本地校验 PASS；在第 24.2 节第 7 步读取；返回值再本地校验 | 依赖图中每个值 exact 且关系已验证；property 是上游冻结代码，实例上不可替换 | 依赖图未通过时已在到达第 7 步之前 `DiagnosticsIntegrityError` |
| D-29 | pure function | `math.isfinite(v)` | 数值 | `type(v) is float` 或 `type(v) is int`（`bool` 已排除） | 内建数值 | `DiagnosticsIntegrityError` |
| D-30 | pure function | `is_valid_fc2_number(s)`（`fc2_metadata_core.normalize`） | 内部正则 / 字符串处理 | `type(s) is str` | exact `str` | `DiagnosticsIntegrityError` |
| D-31 | aggregation | `sum(...)` 作用于 exact `int` | 内建 | 来源容器 Phase V 已确认元素为 exact `int`（`bool` 已排除） | 内建 | `DiagnosticsIntegrityError` |

**使用规则**：

* 矩阵中任何“Required Precondition”都不得被实现为“事后检查”——前置检查必须在对应操作**之前**完成（V-1 / V-2）。
* 每个非 NOT USED 行至少对应一个测试用例（测试 docstring 标记 `[D-xx]`，第 28.1 节“Dispatch Safety Matrix 覆盖”）；NOT USED 行（D-06、D-20、D-21、D-22）由 AST 架构测试与 sentinel 测试证明。
* 本矩阵只裁定**调用方代码分派**；它不改变任何公开 schema、`PathPolicy`、`RetryMaterial`、资源模型（除 provenance key 上界外）、序列化或 S1 / S2 / S3 边界。

### 9.11 Horizontal Dispatch Audit（冻结，Design-R3）

按第 9.10 节矩阵，对本合同消费的全部 caller-originated 容器与批准 property 重新逐项审计（审计范围只含 P4-C9 **实际执行**的操作）。结论：

| # | 审计对象 | P4-C9 对其执行的 element-sensitive 操作（矩阵行） | Gate（该操作之前必须先完成的校验） | 结论 |
|---|---|---|---|---|
| H-01 | `retry_scope`（`BatchPreview` / `BatchExecutionResult`） | 迭代 D-02；`retry_origin in retry_scope` D-12；按声明顺序逐个成员判定（第 12.8 节）D-12 | 迭代完整通过（全部元素 exact `RetryKind`、非 `NONE`）后才成员判定（第 9.2 节第 10 条） | **PASS**（既有设计已满足；本轮仅显式化为 V-2） |
| H-02 | `contributing_source_ids` | 迭代 D-01；被 provenance / conflict 的成员判定 D-11；与 `successful` 逐项比较 D-16；唯一性 D-10 | M-16 校验顺序：先 Phase V（精确 `tuple`、元素 exact `str`、上限），后 Phase R | **PASS**（顺序由第 24.2 节第 4 / 5 步隐含；本轮把它显式冻结进 M-16） |
| H-03 | `disabled_source_ids` | 迭代 D-01；唯一性 / 与 `source_results` id 重叠 D-10 / D-11 / D-14 | M-16 同上 | **PASS**（同 H-02） |
| H-04 | conflict source ids（`FieldConflict.selected_source_id`、`alternatives` 的 id） | 迭代 D-01；唯一性 / `!= selected` D-10 / D-14；对 `contributing_source_ids` 的成员判定 D-11 | M-21：标量 / 容器 Phase V 先于跨对象；`contributing_source_ids` 已先完成 Phase V | **PASS** |
| H-05 | `NormalizedMetadata.field_sources` | 迭代 D-03；`name in proxy` / `proxy[name]` D-08；value 元素对 `contributing_source_ids` 的成员判定 D-11 | Design-R2：**缺口**——D-08 在 stored key 尚未验证为 exact `str` 时就发生；Design-R3：Step 1-3（类型、有界单遍扫描、exact key 验证）先于 Step 4 / 5 | **FINDING = P4-C9-DESIGN-R2-01**（同根因：R-02）——**Design-R3 REMEDIATED — REVIEW REQUIRED** |
| H-06 | `FieldConflict.alternatives` 的 value / `selected_value` | 迭代 D-01；“同类型相等”判定 D-14 | M-21：每个 value 先 `type(v) is str / int`（`bool` 排除）；比较前 `type(a) is type(b)` | **PASS** |
| H-07 | warnings：`ItemExecution.warnings`（字段）与 `ItemPreview.warnings`（批准 property） | 字段：迭代 D-01、唯一性 / 顺序 D-18 / D-11；property：D-28 | 字段：Phase V（exact `ItemWarning`）先于唯一性 / `(X in warnings)` 的成员判定；property：第 9.3.1 节依赖图（`metadata.status`、`preflight.artifacts[*].kind` / `content` 类型、`image_failures` 为 exact tuple）已通过 | **PASS**（依赖图本轮显式化） |
| H-08 | source sets / tuples（`source_results`、`source_execution_traces`、`attempts`、`provided_fields` 的本地推导） | 迭代 D-01；`trace.source_id == result.source_id` D-14；`status in {…}` D-13；`error_kind in RETRY_ELIGIBLE_KINDS` D-13；序号 `1..n` D-19 | M-17 / M-19 / M-20 标量与枚举 Phase V 先于关系 | **PASS** |
| H-09 | `summary` / `outcome`（批准 property） | D-28 | 第 9.3.1 节依赖图 + 第 24.2 节第 4-6 步全部通过 + 每条目 `retry_kind` 一致性先行（第 7 步顺序） | **PASS**（依赖图本轮显式化） |
| H-10 | `retry_kind`（批准 property） | D-28 | 第 9.3.1 节依赖图 + 第 9.6.4 节关系（`(execution is None) == (disposition is not EXECUTED)`、`NOT_READY ⇒ issue is not None`）先于读取；`expected_kind` 先本地推导 | **PASS**（前置关系本轮显式化） |
| H-11 | `conflict_with`（`ItemPreview` / `ItemExecution`） | 迭代 D-01；对称性 `idx in other.conflict_with` D-11；按 `index` 的条目索引 D-10 | M-05 / M-06 的 exact `int` 元素 Phase V 先于对称检查 | **PASS** |
| H-12 | `RetryMaterial.artifacts` / `ExecutionPreflight.artifacts` / retained 字节求和 | 迭代 D-01；`len(content)` D-05；`sum` D-31 | M-24：`type(request) is ArtifactWriteRequest` 且 `type(content) is bytes` 先于 `len` | **PASS** |
| H-13 | `OrganizePlan` 路径 / `operations` / `LeftoverTemporary.name` / `PlannedPath` | D-24、D-25、D-23、D-14 | `type(p) is str`、`PlannedPath` exact 先于路径字符串操作 | **PASS** |
| H-14 | 计时字段 | D-19、D-29 | `type(v) is int / float` 先于比较 / `math.isfinite` | **PASS** |
| H-15 | 错误 message 构造 | D-22 | 固定措辞；只含 P4-C9 自有循环计数器 | **PASS** |

**审计结论**：`PASS WITH ONE FINDING`——唯一发现项是 H-05（= R2-01），已在本轮闭合；**未发现第二个同类（dispatch-before-validate）真实漏洞**。R2-01 不是只修一个点：同类别的全部 dispatch surface（容器迭代、成员判定、
相等、hash 查表、真值转换、文本转换、property）已由第 9.0.1 节统一原则与第 9.10 节矩阵系统审计；H-02 / H-03 / H-04 / H-07 / H-09 / H-10 中被发现“依赖隐含顺序”的位置已被显式冻结（不改变其语义，
只把隐含顺序写成规范性前置条件）。

---

## 10. 诊断种类与形态（判别模型，冻结）

`BatchDiagnostics` 是**一个带显式判别字段的统一模型**：

* `kind: DiagnosticsKind` —— `PREVIEW`（由 `build_preview_diagnostics` 产生）或 `EXECUTION`（由
  `build_execution_diagnostics` 产生）。消费者**只能**依据 `kind` 判断阶段，不得依据字段是否为 `None` 猜测。
* `shape: ResultShape` —— `BatchPreview`：`base_result_id is None` -> `MAIN`，否则 `RETRY`；`BatchExecutionResult`：第 9.6.2 节
  本地 shape 判定。`PREVIEW` 永远不是 `MERGED`。测试以 P4-C8 产生的三种形态逐一交叉验证。
* 字段适用表（冻结；“必为 None / 空”是 schema 定义的不适用，不是缺失 evidence）：

| 字段 | `PREVIEW` | `EXECUTION` |
|---|---|---|
| `BatchDiagnostics.preview_summary` | 必有 | 必为 `None` |
| `BatchDiagnostics.execution_summary` / `outcome` | 必为 `None` | 必有 |
| `ItemDiagnostics.retry_origin` | 按输入（`generation == 0` 时 `None`） | 必为 `None`（`ItemExecution` 不携带） |
| `ItemDiagnostics.disposition` / `retry_kind` / `retry_material_retained` | 必为 `None` | 必有 |
| `ItemDiagnostics.preflight` | 当且仅当输入 `preflight` 存在 | 必为 `None`（`ItemExecution` 不携带 preflight，见第 13 节） |
| `ItemDiagnostics.execution` | 必为 `None` | 当且仅当 `disposition is EXECUTED` |

---

## 11. 模型（`models.py`，冻结）

全部模型为 `@dataclass(frozen=True, slots=True)`；每个模型的校验逻辑实现为 `models.py` 中的模块级本地校验函数，由该模型的
`__post_init__` 调用（`__post_init__` 只作为本 package 自己的类定义存在，P4-C9 代码从不以属性方式访问或调用任何
`__post_init__`）；违反抛 `DiagnosticsContractError`（固定措辞）。校验以精确类型（`type(x) is T`，`bool` 不算 `int`）进行。
模型不提供 `to_dict` / `to_json` / `dump` / `save` 之类的方法，不定义 `__getattr__`、property 钩子或自定义 `__eq__` /
`__hash__`。tuple 字段只接受精确 `tuple`。下文“枚举”均指上游或本 package 的精确枚举成员。

新增的诊断枚举：

```python
class DiagnosticsKind(Enum):  PREVIEW = "preview";  EXECUTION = "execution"
class ResultShape(Enum):      MAIN = "main";        RETRY = "retry";      MERGED = "merged"
class PathPolicy(Enum):       NONE = "none";        BASENAME = "basename"
class TimingPolicy(Enum):     OMIT = "omit";        INCLUDE = "include"
```

其余枚举一律**原样复用**上游冻结枚举（`OrchestrationStage`、`IssueReason`、`ItemWarning`、`PreviewState`、
`ExecutionDisposition`、`RetryKind`、`BatchOutcome`、`BatchItemStatus`、`BatchItemErrorKind`、`AggregateStatus`、
`SourceStatus`、`SourceErrorKind`、`ImageRole`、`ImageFailureKind`、`PreflightMode`、`TransferMode`、`ExecutionStatus`、
`ExecutionStep`、`EffectKind`、`ArtifactKind`、`PathRole`），不发明平行状态词汇。

### 11.1 `BatchDiagnostics`

| 字段 | 类型 | 不变量 |
|---|---|---|
| `kind` | `DiagnosticsKind` | — |
| `shape` | `ResultShape` | `PREVIEW` 时不为 `MERGED` |
| `generation` | `int >= 0` | `MAIN` 时为 0，否则 `>= 1` |
| `batch_size` | `int`，`0..MAX_DIAGNOSTIC_ITEMS` | — |
| `retry_scope` | `tuple[RetryKind, ...] \| None` | `RETRY` 时非 `None`：元素唯一、按 `RetryKind` 声明顺序、不含 `NONE`（可以为空，与 P4-C8 scope 校验一致）；`MAIN` / `MERGED` 时为 `None` |
| `path_policy` | `PathPolicy` | — |
| `timing_policy` | `TimingPolicy` | — |
| `metadata_batch` | `MetadataBatchCounts` | — |
| `preview_summary` | `PreviewSummary \| None` | 精确 P4-C8 类型；适用性见第 10 节 |
| `execution_summary` | `ExecutionSummary \| None` | 精确 P4-C8 类型；适用性见第 10 节 |
| `outcome` | `BatchOutcome \| None` | 适用性见第 10 节 |
| `items` | `tuple[ItemDiagnostics, ...]` | 长度 `<= batch_size`；`index` 严格递增且 `< batch_size`；`MAIN` / `MERGED` 时 `index` 恰为 `0..batch_size-1`；summary 的 `total == len(items)`；每个条目的 kind 相关字段满足第 10 节适用表；`PREVIEW` 时每条 `generation == generation`；`EXECUTION` 且非 `MERGED` 时每条 `generation == generation`，`MERGED` 时每条 `generation <= generation`；`path_policy is NONE` 时每个条目的全部路径派生文本为 `None` |

`BatchDiagnostics` 只做上述结构一致性检查，**不**重新计算 summary / outcome 的业务语义（它们是 P4-C8 冻结派生值，原样
携带；第 12.8 节）。

### 11.2 `MetadataBatchCounts`

`generation: int >= 0`、`total`、`success`、`partial`、`failed`（`int >= 0`）；不变量 `total == success + partial + failed`。

### 11.3 `ItemDiagnostics`

| 字段 | 类型 | 说明 |
|---|---|---|
| `index` | `int >= 0` | 稳定批内 index（P4-C8 第 12.1 节） |
| `generation` | `int >= 0` | — |
| `canonical_number` | `str \| None` | `None` 当且仅当 `issue.reason is NUMBER_NOT_RECOGNIZED`；非 `None` 时满足 `is_valid_fc2_number` |
| `source_name` | `str \| None` | 路径策略（第 18 节）；`PathPolicy.NONE` 时必为 `None`，`BASENAME` 时必非 `None` |
| `source_size` | `int >= 0` | `DiscoveredMediaItem.size`（字节） |
| `target_directory_name` | `str \| None` | 路径策略；`plan` 缺失或 `NONE` 时为 `None` |
| `target_media_name` | `str \| None` | 同上 |
| `preview_state` | `PreviewState` | 预览状态（`EXECUTION` 时为 `ItemExecution.preview_state`） |
| `issue` | `IssueDiagnostics \| None` | — |
| `warnings` | `tuple[ItemWarning, ...]` | 唯一、按 `ItemWarning` 声明顺序 |
| `conflict_with` | `tuple[int, ...]` | 严格递增、不含自身 index |
| `retry_origin` | `RetryKind \| None` | 第 10 节；非 `None` 时不是 `NONE` |
| `disposition` | `ExecutionDisposition \| None` | 第 10 节 |
| `retry_kind` | `RetryKind \| None` | 第 10 节 |
| `retry_material_retained` | `bool \| None` | 第 10 节；`ItemExecution.retry_material is not None` |
| `metadata` | `MetadataDiagnostics \| None` | `None` 当且仅当输入条目的 `metadata is None`（未进入 / 未取得 metadata 批结果） |
| `image_failures` | `tuple[ImageFailureGroup, ...]` | 第 12.5 节分组与排序；`(role, kind)` 唯一 |
| `preflight` | `PreflightDiagnostics \| None` | 第 10 节 |
| `execution` | `ExecutionDiagnostics \| None` | 第 10 节 |

### 11.4 `IssueDiagnostics`

`stage: OrchestrationStage`、`reason: IssueReason`、`error_type: str | None`、`detail: Enum | None`。不变量：

* `error_type` 为 `None`，或为 `str.isidentifier()` 为真、长度 `1..128` 的精确 `str`；
* `detail` 为 `None`，或其类型精确属于冻结集合 `{BatchItemErrorKind, MappingRejectionReason, PlanGraphRejectionReason,
  ManifestRejectionReason, CheckpointRejectionReason, ExecutionFailureKind, PreflightIntegrityReason}`；
* `stage` / `error_type` 必需性 / `detail` 类型满足表 T-1（投影时原样复制已校验的值）。

### 11.5 `MetadataDiagnostics`

| 字段 | 类型 | 不变量 / 说明 |
|---|---|---|
| `status` | `BatchItemStatus` | — |
| `generation` | `int >= 0` | `BatchItemResult.generation` |
| `error_kind` | `BatchItemErrorKind \| None` | 非 `None` 当且仅当没有 `AggregationResult`（此时 `status is FAILED`） |
| `aggregate_status` | `AggregateStatus \| None` | 非 `None` 当且仅当有 `AggregationResult` |
| `traces_available` | `bool` | `AggregationResult.source_execution_traces` 非空；无 `AggregationResult` 时为 `False` |
| `sources` | `tuple[SourceDiagnostics, ...]` | 按 `source_results` 顺序；`source_id` 唯一；无 `AggregationResult` 时为空；长度 `<= MAX_SOURCES_PER_ITEM` |
| `disabled_source_ids` | `tuple[str, ...]` | 原顺序；唯一；不与 `sources` 重叠；每个满足安全 id 规则；长度 `<= MAX_SOURCES_PER_ITEM` |
| `field_provenance` | `tuple[FieldProvenance, ...]` | 第 12.3 节 |
| `conflicts` | `tuple[FieldConflictDiagnostics, ...]` | 第 12.4 节；长度 `<= MAX_CONFLICTS_PER_ITEM` |
| `elapsed_ms` | `int \| None` | `BatchItemResult.elapsed_ms`（scheduler 测量）；`TimingPolicy.OMIT` 时必为 `None`，`INCLUDE` 时必非 `None` |

### 11.6 `SourceDiagnostics`

| 字段 | 类型 | 不变量 / 说明 |
|---|---|---|
| `source_id` | `str` | 安全 id 规则（第 17.2 节） |
| `status` | `SourceStatus` | 最终结果状态 |
| `error_kind` | `SourceErrorKind \| None` | `status is SUCCESS` 当且仅当为 `None` |
| `contributed` | `bool` | `source_id in contributing_source_ids` |
| `operational_failure` | `bool` | `status in OPERATIONAL_FAILURE_STATUSES`（Phase 3 公开常量） |
| `provided_fields` | `tuple[str, ...]` | 该 source 出现在其 `field_provenance` 中的字段名，按 `PROVENANCE_FIELD_ORDER`；`contributed` 为假时必为空 |
| `trace_available` | `bool` | 是否有对应的 `SourceExecutionTrace` |
| `attempt_count` | `int \| None` | `trace_available` 时为 `len(trace.attempts)`，否则 `None` |
| `max_attempts` | `int \| None` | 同上规则 |
| `deadline_exceeded` | `bool \| None` | 同上规则 |
| `deadline_during` | `str \| None` | 只能是 `None`、`"attempt"`、`"backoff"`；`deadline_exceeded` 为真当且仅当非 `None` |
| `attempts` | `tuple[SourceAttemptDiagnostics, ...]` | 按 `sequence` 顺序；`len == attempt_count`（无 trace 时为空）；`<= MAX_ATTEMPTS_PER_SOURCE` |

### 11.7 `SourceAttemptDiagnostics`

`sequence: int >= 1`、`status: SourceStatus`、`error_kind: SourceErrorKind | None`、`completed: bool`、
`elapsed_ms: int | None`、`backoff_before_ms: int | None`。计时字段在 `OMIT` 时必为 `None`，`INCLUDE` 时必为
`0..MAX_TIMING_MS` 的精确 `int`。

### 11.8 `FieldProvenance`

`field: str`（`PROVENANCE_FIELD_ORDER` 的成员）、`source_ids: tuple[str, ...]`（非空、唯一、每个满足安全 id 规则）。

### 11.9 `FieldConflictDiagnostics`

`field: str`（`CONFLICT_FIELDS` 的成员）、`selected_source_id: str`、`alternative_source_ids: tuple[str, ...]`（非空、唯一、
不含 `selected_source_id`）。**不**包含被选中值、候选值或 `external_ids` 的 key。

### 11.10 `ImageFailureGroup`

`role: ImageRole`、`kind: ImageFailureKind`、`count: int >= 1`、`http_statuses: tuple[int, ...]`（升序、唯一、每个
`100..599`；非空当且仅当 `kind is HTTP_STATUS`）。

### 11.11 `PreflightDiagnostics`

| 字段 | 类型 | 说明 |
|---|---|---|
| `mode` | `PreflightMode` | — |
| `ready` | `bool` | `ready` 为真当且仅当 `blockers == ()` |
| `transfer_mode` | `TransferMode \| None` | — |
| `blockers` | `tuple[PreflightBlocker, ...]` | 原 P4-C7 对象（已按 M-25 校验）、原顺序；`<= MAX_BLOCKERS_PER_ITEM` |
| `pending_unit_count` | `int >= 0` | `len(pending_units)` |
| `completed_unit_count` | `int >= 0` | `len(completed_units)` |
| `skipped_steps` | `tuple[ExecutionStep, ...]` | 原顺序 |
| `artifact_counts` | `tuple[tuple[ArtifactKind, int], ...]` | 每个 `ArtifactKind` 按声明顺序恰好一项（含 0），计数 `preflight.artifacts` 中各 `kind` |

### 11.12 `ExecutionDiagnostics`

| 字段 | 类型 | 说明 |
|---|---|---|
| `status` | `ExecutionStatus` | — |
| `mode` | `PreflightMode` | — |
| `transfer_mode` | `TransferMode \| None` | — |
| `new_effect_count` | `int >= 0` | `<= sum(effect_counts)` |
| `effect_counts` | `tuple[tuple[EffectKind, int], ...]` | 每个 `EffectKind` 按声明顺序恰好一项（含 0） |
| `artifact_counts` | `tuple[tuple[ArtifactKind, int], ...]` | 每个 `ArtifactKind` 按声明顺序恰好一项，计数 `ARTIFACT_PUBLISHED` effect 的 `artifact_kind` |
| `failure` | `ExecutionFailure \| None` | 原 P4-C7 对象（已按 M-28 校验）；`status is SUCCESS` 当且仅当为 `None` |
| `checkpoint_present` | `bool` | `status is PARTIAL` 当且仅当为真 |
| `skipped_steps` | `tuple[ExecutionStep, ...]` | 原顺序 |
| `leftover_temporary_count` | `int >= 0` | `len(leftover_temporaries)`（输入），`<= MAX_LEFTOVER_TEMPORARIES_PER_ITEM` |
| `leftover_temporaries` | `tuple[LeftoverTemporaryDiagnostics, ...]` | 原顺序；长度恒等于 `leftover_temporary_count` |

### 11.13 `LeftoverTemporaryDiagnostics`

`directory_role: PathRole`（只能是 `TARGET_DIRECTORY` 或 `EXTRAFANART_DIRECTORY`）、`name: str | None`（`BASENAME` 时为
满足 `\.fc2tmp-[0-9a-f]{32}\.part` 的精确 `str`；`NONE` 时为 `None`）。

---

## 12. 映射规则（冻结）

所有映射都从第 9.2 节第 11 条的校验快照读取。

### 12.1 条目

| 诊断字段 | 来源 |
|---|---|
| `index`、`generation`、`canonical_number`、`conflict_with` | 输入条目同名字段（原样） |
| `preview_state` | `ItemPreview.state` / `ItemExecution.preview_state` |
| `issue` | `ItemIssue` 四个字段原样复制；`None` -> `None` |
| `warnings` | `ItemPreview.warnings`（第 9.3 节批准 property）/ `ItemExecution.warnings`（字段），原样 |
| `retry_origin` | `ItemPreview.retry_origin` |
| `disposition`、`retry_kind` | `ItemExecution.disposition`、`ItemExecution.retry_kind`（第 9.3 节批准 property，原样；诊断不重新判定） |
| `retry_material_retained` | `ItemExecution.retry_material is not None` |
| `source_size` | `media_item.size` |
| `source_name`、`target_directory_name`、`target_media_name` | 第 18 节（默认 `NONE` -> `None`） |

条目的“编排阶段”即 `issue.stage`；没有 issue 的条目没有失败阶段，诊断**不**推断“最远到达阶段”（没有公开 evidence）。

### 12.2 metadata 与 source

* `BatchItemResult` -> `MetadataDiagnostics`：`status`、`generation`、`error_kind` 原样；有 `AggregationResult` 时
  `aggregate_status = aggregation_result.status`。
* `sources`：对 `aggregation_result.source_results` 按原顺序逐个投影；`trace` 取 `source_execution_traces` 中同位置项
  （第 9.6.6 节已校验一一对应）；`traces_available` 为假时所有 trace 字段为 `None` / 空。
* `contributed`、`operational_failure`、`provided_fields` 按第 11.6 节定义。
* attempt：`SourceAttempt` 的 `sequence`、`status`、`error_kind`、`completed` 原样；计时见第 12.7 节。
* 诊断**不**输出 `SourceResult.error_detail` 与 adapter 自报的 `SourceResult.elapsed_ms`（二者仅为 Validation-Only）。

### 12.3 字段出处（Field Provenance，P0）

* 唯一 evidence：`AggregationResult.metadata.field_sources`（Phase 3 聚合合同第 5.6 节：由 merge 从零重新计算，adapter 无法
  伪造；scalar 字段被选中的 source 排第一，集合 / `external_ids` 按优先级列出全部提供者，`number` 列出全部贡献者）。
* 投影（Design-R3；算法权威见第 9.2 节第 9 条）：`type(metadata) is NormalizedMetadata`、`type(metadata.field_sources) is types.MappingProxyType` 之后，**先**完成**有界单遍 key 扫描**（计数、
  超过 `MAX_PROVENANCE_KEYS` 立即 `DiagnosticsResourceLimitError`、逐个 `type(key) is str`；含 unknown key；扫描期间无 `in` / 下标 / 相等 / hash 敏感操作，无物化），并完成第 9.5 节
  M-18 / 第 9.6.6 节校验；**仅在全部 stored key 扫描并 exact-`str` PASS 之后**，才**按 `PROVENANCE_FIELD_ORDER` 的固定字段名逐个**查询（`name in proxy` / `proxy[name]`）。
  输出顺序**只**由 `PROVENANCE_FIELD_ORDER` 决定（**从不**按 mapping 的迭代 / 插入顺序产生输出；key 扫描的迭代仅用于 validation，不产生输出顺序；不整体取出再排序）；存在的字段产生一个
  `FieldProvenance(field, source_ids)`，`source_ids` 保持 Phase 3 给出的优先级顺序；`PROVENANCE_FIELD_ORDER` 中未出现的 known field 是 schema 定义的 absence；mapping 中其它（unknown
  exact-`str`）key：被扫描、计入 `MAX_PROVENANCE_KEYS`，但不投影、不输出、不赋予诊断语义（投影白名单：P4-C9 只负责冻结的 known provenance 字段）。P4-C9 不 introspect `MappingProxyType`
  的被包装对象（第 9.0 节 C 层）。
* `metadata is None`（`AggregateStatus.FAILED`）时 `field_provenance == ()`。
* P4-C9 **不**重新执行任何 metadata aggregation，不比较字段值，不验证“值是否由该 source 提供”（Phase 3 合同第 3 节已声明
  该项只由 merge 保证）。

### 12.4 字段冲突

`AggregationResult.conflicts` 按原顺序（Phase 3 已按字段顺序与 key 排序）逐个投影为
`FieldConflictDiagnostics(field, selected_source_id, alternative_source_ids)`，只取 source id；值与 `external_ids` 的 key
只作 Validation-Only 检查，一律不输出。

### 12.5 图片失败

`image_failures` 按 `(role, kind)` 分组计数：分组顺序为 `ImageRole` 声明顺序，再按 `ImageFailureKind` 声明顺序；只输出
`count >= 1` 的分组；`HTTP_STATUS` 分组附带去重升序的 `http_status` 列表。`candidate_index` 不输出（Validation-Only）。

### 12.6 preflight 与 execution

* `PreflightDiagnostics`（只在 `PREVIEW` 且输入 `preflight` 存在时）：第 11.11 节逐字段映射；`artifact_counts` 只读
  `ArtifactWriteRequest.kind`。
* `ExecutionDiagnostics`（只在 `EXECUTION` 且 `disposition is EXECUTED` 时）：第 11.12 节逐字段映射；`effect_counts` /
  `artifact_counts` 只读 `CompletedEffect.kind` / `artifact_kind`；`checkpoint_present = execution.checkpoint is not None`；
  `leftover_temporaries` 按路径策略处理 `name`。

### 12.7 计时（`TimingPolicy`）

* `OMIT`（默认）：所有计时字段为 `None`。
* `INCLUDE`：只发布 engine / scheduler 测量的计时（P2-R-07）：`SourceAttempt.elapsed_ms` -> `elapsed_ms`；
  `SourceAttempt.backoff_before_seconds` -> `backoff_before_ms = int(backoff_before_seconds * 1000)`；
  `BatchItemResult.elapsed_ms` -> `MetadataDiagnostics.elapsed_ms`。转换一律为 `int(value)`（向零截断）；非有限或负值在本地
  校验阶段（M-15 / M-20，任何计时策略下）已以 `DiagnosticsIntegrityError` 拒绝；转换后超过 `MAX_TIMING_MS` 的值在安全输出检查
  （第 9.7 节）以 `DiagnosticsUnsafeValueError` 拒绝。`AggregationResult.elapsed_ms` 与 adapter 自报的
  `SourceResult.elapsed_ms` 不发布。
* 计时值是输入 evidence：诊断对相同输入仍确定；但两次真实运行的计时不同，因此需要跨运行比较的消费者应使用默认 `OMIT`。

### 12.8 批级

* `kind`、`shape`、`generation`、`batch_size` 见第 10 / 11.1 节；`retry_scope` 为输入 frozenset 按 `RetryKind` 声明顺序转成
  tuple（以声明顺序逐个判断成员资格，**从不**以 frozenset 迭代顺序产生输出）。
* `metadata_batch`：`BatchResult.generation` 与按 M-14 本地计算的 `total / success / partial / failed`。
* `preview_summary` = `BatchPreview.summary`；`execution_summary` = `BatchExecutionResult.summary`；`outcome` =
  `BatchExecutionResult.outcome`：均为第 9.3 节批准 property，原对象 / 原成员携带（返回值先经 M-08 / M-09 本地校验）。
  诊断**不**另行计算 ready / retryable / deferred / non-retryable / stage_counts，从而不可能产生与 P4-C8 summary 矛盾的第二套
  语义。

---

## 13. 不可推断的 evidence 与缺失表达（冻结）

诊断只报告输入模型真实持有的 evidence；缺失一律以 schema 定义的形式表达，绝不推断、伪造或重新查询：

| 缺失情形 | 表达 |
|---|---|
| 没有 metadata 批结果（识别失败、批内冲突等） | `ItemDiagnostics.metadata = None` |
| engine 异常 / 结果契约不符，没有 `AggregationResult` | `aggregate_status = None`、`sources = ()`、`error_kind` 非 `None` |
| `AggregationResult` 没有 trace（纯 merge） | `traces_available = False`；每个 source 的 `trace_available = False`、trace 字段为 `None` / 空 |
| 计时未发布 | 计时字段为 `None`，批级 `timing_policy = OMIT` |
| 执行结果中的 preflight blocker | **不可用**：`ItemExecution` 不携带 preflight；`EXECUTION` 诊断中 `preflight = None`。需要 blocker 明细的消费者对同一 preview 调用 `build_preview_diagnostics` |
| 路径文本 | 默认 `PathPolicy.NONE` 时为 `None`；`plan` 不存在时目标名为 `None` |
| HTTP response body、header、完整 traceback、异常 message、source URL、单个 source 的 adapter 自报耗时、wall-clock 时间戳 | 公开模型中不存在或只作 Validation-Only：schema 中**没有**对应字段 |

---

## 14. 临时身份与非确定值审计（冻结）

| 值 | 所在模型 | 诊断中的处理 |
|---|---|---|
| `preview_id` | `BatchPreview`、`BatchExecutionResult` | Validation-Only（hex32 / shape 判定），不输出 |
| `result_id`、`base_result_id` | `BatchExecutionResult`、`BatchPreview` | Validation-Only；`base_result_id is None` 用于 `shape`；值不输出 |
| `BatchLineage.token` | `lineage`、`metadata_batch.lineage` | Validation-Only（hex32 与相等关系），不输出（它也是 P4-C8 合并授权的进程内能力令牌） |
| `preflight_id` | `ExecutionPreflight`、`ExecutionResult` | Validation-Only，不输出 |
| `seal`、`plan_fingerprint`、`manifest_fingerprint` | `ExecutionPreflight` | Validation-Only，不输出 |
| `checkpoint_id`、`ExecutionCheckpoint.seal` | `ExecutionCheckpoint` | 不读取（类型确认）；只输出 `checkpoint_present` |
| `EntryIdentity`（device / inode / mtime_ns） | preflight / checkpoint / effect | 不读取、不输出 |
| `CompletedEffect.sha256`、`ExecutionResult.media_sha256` | execution | 前者不读取；后者 Validation-Only；均不输出 |
| 计时 | `SourceAttempt`、`BatchItemResult` | 只在 `INCLUDE` 时输出（第 12.7 节） |
| `LeftoverTemporary.name`（含随机 32 hex） | execution | 只在显式 `BASENAME` 时输出：这是用户清理残留文件所需的真实 evidence；它是输入的确定函数，不破坏“相同输入 -> 相同输出” |

诊断自身不生成任何 id、时间戳、随机数、`id()` / 内存地址或 hash 值。

## 15. 确定性（冻结）

* 对同一组输入模型与同一组策略：`build_*` 产生相等（`==`）的 `BatchDiagnostics`；`render_diagnostics_json` 产生逐字节相同的
  bytes。
* 对**语义相同**的输入——仅在上表临时身份、`field_sources` mapping 插入顺序、对象构造顺序、asyncio / 线程完成顺序上不同——
  在 `TimingPolicy.OMIT` 下产生相等的模型与逐字节相同的输出。
* 禁止：`datetime` / `time`、随机数、uuid、`id()`、`hash()`、内存地址、对 `set` / `frozenset` / `dict` / mapping 的迭代顺序
  决定输出顺序（第 9.2 节第 10 条的“先迭代”与第 9 条 Step 3 的 key 扫描只用于类型确认 / validation，不产生输出顺序）。
* **失败输入的错误类型**：对通过校验的输入，输出与 `field_sources` 插入顺序无关；对**同时违反多条规则**的失败输入，错误类型遵守第 9.0.1 节 V-4（遍历中最先遇到的违规）。这只影响失败输入的错误类，不影响任何成功输出。
* JSON 编码固定参数（第 22 节），浮点数永不出现在输出中（计时已转换为 `int`）。

## 16. 排序（冻结）

| 集合 | 顺序 |
|---|---|
| `items` | `index` 升序（即输入 tuple 顺序；已校验严格递增） |
| `issue` | 每条目至多一个（P4-C8 模型）；无排序问题 |
| `warnings` | `ItemWarning` 声明顺序 |
| `conflict_with` | 升序（输入顺序） |
| `retry_scope` | `RetryKind` 声明顺序 |
| `sources` | `AggregationResult.source_results` 顺序（Phase 3 配置 / 优先级顺序） |
| `disabled_source_ids` | 输入顺序 |
| `attempts` | `sequence` 升序（输入顺序） |
| `field_provenance` | `PROVENANCE_FIELD_ORDER` |
| `FieldProvenance.source_ids` | Phase 3 给出的优先级顺序 |
| `provided_fields` | `PROVENANCE_FIELD_ORDER` |
| `conflicts` | 输入顺序（Phase 3 按字段顺序与 key 排序） |
| `alternative_source_ids` | 输入顺序（优先级） |
| `image_failures` | `ImageRole` 声明顺序，再 `ImageFailureKind` 声明顺序；`http_statuses` 升序 |
| `blockers`、`skipped_steps`、`leftover_temporaries` | 输入顺序 |
| `artifact_counts` / `effect_counts` | `ArtifactKind` / `EffectKind` 声明顺序，0 计数也列出 |
| `stage_counts` | P4-C8 summary 已按 `OrchestrationStage` 声明顺序给出（M-08 / M-09 已校验） |
| JSON object key | 字典序（`sort_keys=True`）；所有有序集合都用 JSON array 表达 |

---

## 17. 脱敏（Redaction）与安全文本规则（冻结）

### 17.1 两类输出渠道（Design-R1 重写）

**A. 永不输出的结构化渠道（任何路径策略、任何计时策略下都禁止）**：credentials、`Authorization` header、`Cookie` 字段、
session token、secret header、任何 HTTP header / body、URL（含 query）、原始异常对象、异常 repr / message / args、traceback、
网页文本 / HTML、metadata 字段值（标题、简介、演员、标签、URL、`external_ids` 的 key 与 value）、`SourceResult.error_detail`、
冲突值、`BatchLineage.token` 与第 14 节全部临时身份、absolute path、library root、目录层级、任何字节载荷。这些渠道要么从不
被读取，要么只作 Validation-Only（第 9.4 节），因此不存在“先读取再过滤”的路径。对 A 类渠道，P4-C9 作出绝对承诺：其内容
在任何策略下都不出现在诊断模型、JSON 或错误 message 中。

**B. 路径派生的用户文本**（`source_name`、`target_directory_name`、`target_media_name`、残留临时文件 `name`）：

* 默认 `PathPolicy.NONE`：**完全不输出**；这些字段为 `None`；P4-C9 不计算任何 basename。默认情况下诊断不释放任何用户
  控制的路径文本。
* 显式 `PathPolicy.BASENAME`：调用方**明确选择**释放经第 18.2 节词法安全检查的 basename。这是**披露（disclosure）策略，不是
  脱敏保证**：用户自己写进文件名的文本可能包含敏感内容；P4-C9 不做关键词扫描，不判断 `Authorization`、`token`、`secret`
  之类的词是否真的是 credential。因此第 A 类的绝对承诺**不**延伸到显式 BASENAME 下的 basename 内容。

### 17.2 允许输出的 `str` 值（穷举）

| 类别 | 规则（不满足即 `DiagnosticsUnsafeValueError`） |
|---|---|
| 枚举值 | 只经由冻结枚举成员的 `.value` 输出（由 `render.py` 统一转换） |
| schema 常量 | `DIAGNOSTICS_SCHEMA`、`DIAGNOSTICS_SCHEMA_VERSION` |
| 安全 id（source id） | 精确 `str`，完全匹配 `[A-Za-z0-9][A-Za-z0-9_.\-]{0,63}` |
| `error_type` | 精确 `str`，`isidentifier()` 为真，长度 `1..128` |
| detail 类型名 | 来自第 11.4 节冻结集合的类名，由冻结表给出（不调用 `type(x).__name__`） |
| 字段名 | `PROVENANCE_FIELD_ORDER` / `CONFLICT_FIELDS` 的成员 |
| `canonical_number` | `is_valid_fc2_number` 为真 |
| `deadline_during` | `"attempt"` 或 `"backoff"` |
| 路径派生文本 | **仅**显式 `PathPolicy.BASENAME`，且满足第 18.2 节 |
| 残留临时文件名 | **仅**显式 `PathPolicy.BASENAME`，且完全匹配 `\.fc2tmp-[0-9a-f]{32}\.part` |

规则说明：source id 来自运营配置（Phase 3 `SourceConfig`），通常是 `fc2db_net` 之类的短标识；不满足安全 id 规则的配置在诊断
中 fail closed（已知局限，第 31 节），而不是被截断或改写。

### 17.3 编码规则

输出为 JSON，`ensure_ascii=True`：所有非 ASCII 字符以 `\uXXXX` 转义。第 18.2 节已禁止控制字符进入模型；因此输出 bytes 恒为
ASCII，不存在编码失败或终端注入的原始控制字符。

## 18. 路径策略（`PathPolicy`，冻结）

### 18.1 策略表

| 策略 | `source_name` | `target_directory_name` / `target_media_name` | 残留临时文件 `name` | library root / 目录 / absolute path |
|---|---|---|---|---|
| `NONE`（**默认**，v1.0 安全策略） | `None` | `None` | `None` | **从不**输出 |
| `BASENAME`（显式 opt-in 路径披露） | `os.path.basename(media_item.source_path)` | `os.path.basename(plan.target_directory.absolute_path)` / `os.path.basename(plan.target_media_path.absolute_path)` | 原文件名（固定格式） | **从不**输出 |

* `NONE` 下，路径字符串只作 Validation-Only 检查（类型、绝对性、第 9.6.5 节结构关系），从不传给 basename 计算、从不进入快照。
* basename 计算是纯字符串处理：只作用于已确认精确 `str` 的输入；不 `stat`、不 `exists`、不 `resolve` / `realpath`、不
  `open`、不 `readlink`、不做任何文件系统查询。`os.path.basename` 使用运行平台的路径语义，与 P4-C8 番号识别（P4-C8 合同
  第 30.2 节）一致；输入路径由同平台产生。
* 不提供 absolute path 或 relative path 选项。裁决理由：(1) 输出被设计为可以交给他人或附在 issue 中，目录层级可能含用户名、
  私人目录名；(2) 需要完整路径的 UI 与诊断处于同一进程，可以用稳定 `index` 回到同一个 `BatchPreview` /
  `BatchExecutionResult` 读取 P4-C8 的公开路径 property；(3) basename 已足够定位媒体与目标目录。若将来需要 absolute path
  opt-in，属于合同修订（并且是安全边界变化，触发第 5.3 节第 J 项评估）。
* `source_size` 与 `artifact_counts` 等数值不受路径策略影响。

### 18.2 BASENAME 词法安全 grammar（冻结）

即使是显式 opt-in，每个将输出的 basename `b` 也必须同时满足，否则 `DiagnosticsUnsafeValueError`（不截断、不替换、不转义修复）：

1. `type(b) is str`；
2. `1 <= len(b) <= MAX_PATH_TEXT_CHARS`；
3. `b not in (".", "..")`；
4. 不含 `"/"`、不含 `"\\"`（两者在任何平台都禁止，保证跨平台、跨输出一致），也不含 `os.sep` 与 `os.altsep`（若非 `None`）；
5. 不含以下任何码点（明确、确定、不依赖 Unicode 数据库版本）：
   * C0 控制字符 `U+0000..U+001F`（含 NUL、TAB、LF、CR）、DEL `U+007F`、C1 控制字符 `U+0080..U+009F`；
   * 代理项 `U+D800..U+DFFF`（例如 surrogateescape 解码产生的孤立代理）；
   * 行 / 段分隔符 `U+2028`、`U+2029`；
   * 双向文本控制符 `U+061C`、`U+200E`、`U+200F`、`U+202A..U+202E`、`U+2066..U+2069`；
   * BOM / 零宽不换行空格 `U+FEFF`。

其它可打印字符（含 ASCII 空格、全角空格、日文 / 中文等）允许。残留临时文件名另受第 17.2 节固定格式约束（自然满足上述 grammar）。

## 19. 异常安全（冻结）

* 诊断从不调用 `str(exception)`、`repr(exception)`、`format(exception)`、`exception.args`、`traceback.*`、`sys.exc_info`；
  不在 f-string / `%` / `format` 中插入任何输入值。
* 诊断不会主动调用调用方控制的代码（精确语义见第 9.0 节，不是绝对 sandbox 承诺）：所有对象先以 `type(x) is T` 精确确认属于
  第 8.5 节的上游公开类，然后才读取第 9.5 节的字段；上游类是 CLOSED package 的 `@dataclass(frozen=True, slots=True)`，对 A 层
  输入其字段读取不执行任何调用方代码。不调用任何上游 `__post_init__`、private / dunder 方法或实例方法；唯一调用的上游代码是第
  9.3 节逐项列出的五个 P4-C8 公开 property 与 `is_valid_fc2_number`，且只在其依赖的对象图完成本地校验之后。容器只按第 9.2 节
  第 3、9、10 条访问，并遵守第 9.0.1 节 validate-before-dispatch 与第 9.10 节 Dispatch Safety Matrix；不 introspect 任何不透明标准库容器的内部（第 9.0 节 C 层、第 7 节 No New Introspection）。
* 本地校验不依赖“捕获上游异常”：它不调用会抛出上游异常的上游校验代码。
* 失败原因只来自既有 frozen evidence：`ItemIssue.error_type`（类名）、`detail`（冻结枚举）、`ExecutionFailure`、
  `PreflightBlocker`、`SourceErrorKind`、`BatchItemErrorKind`。
* 诊断自身的错误遵守第 8.4 节规则（固定措辞、不链接）。

## 20. 载荷边界（冻结）

诊断从不复制或引用：video bytes、image bytes、NFO bytes、任何 `ArtifactWriteRequest.content`（只确认 `type(content) is bytes`）、
HTTP body。只记录枚举、计数、安全标量（`int` / `bool`）与第 17.2 节允许的文本。诊断模型不持有任何上游对象的引用，**除了**
以下三种全字段安全、不可变、且已按第 9.5 节本地校验的上游值对象：`PreviewSummary` / `ExecutionSummary`（M-08 / M-09）、
`PreflightBlocker`（M-25）、`ExecutionFailure`（M-28）。它们都不持有 bytes、路径或自由文本。

## 21. 资源边界与输出上界（冻结）

### 21.1 时间与内存

* builder：时间 `O(N)`，`N` 为被消费输入对象与诊断条目总数；每个输入对象只访问常数次（`field_sources`：至多 `MAX_PROVENANCE_KEYS + 1` 个 key 被单遍扫描，其后按至多 15 个固定字段名查询）。
* renderer：时间 `O(E)`（`E` 为诊断条目总数）；内存有界于诊断模型大小与 `MAX_DIAGNOSTIC_OUTPUT_BYTES`。
* 没有无界历史、没有全局 registry、没有跨调用缓存；模块级状态只包含不可变常量（`tuple`、`frozenset`、`str`、`int`、枚举类、
  已编译的 `re.Pattern`）。

### 21.2 结构上限（fail closed，`DiagnosticsResourceLimitError`）

| 检查 | 时点 |
|---|---|
| `len(items) > MAX_DIAGNOSTIC_ITEMS`（继承 `MAX_BATCH_ITEMS`） | 在任何逐条工作与本地校验**之前**（`items` 先确认为精确 `tuple`） |
| `len(metadata_batch.items) > MAX_DIAGNOSTIC_ITEMS` | 迭代 `metadata_batch.items` 前 |
| `len(source_results)` / `len(source_execution_traces)` / `len(contributing_source_ids)` / `len(disabled_source_ids)` `> MAX_SOURCES_PER_ITEM` | 迭代对应 tuple 前 |
| `len(trace.attempts) > MAX_ATTEMPTS_PER_SOURCE` | 迭代 attempts 前 |
| `len(conflicts) > MAX_CONFLICTS_PER_ITEM`；`len(conflict.alternatives) > MAX_SOURCES_PER_ITEM` | 迭代对应 tuple 前 |
| `field_sources` 的 stored key 数 `> MAX_PROVENANCE_KEYS` | **单遍计数**：观察到第 `MAX_PROVENANCE_KEYS + 1` 个 key 时立即停止（该 key 的类型都不再检查；之后的 key 不再被读取）；不先 `list()` / `tuple()` / `set()` / `sorted()` 物化再检查；不使用 `len(proxy)`（D-06）：以单遍计数代替，不依赖被包装 mapping 的 `__len__` |
| `len(blockers) > MAX_BLOCKERS_PER_ITEM` | 迭代 blockers 前 |
| `len(leftover_temporaries) > MAX_LEFTOVER_TEMPORARIES_PER_ITEM` | 迭代 leftovers 前 |

`field_provenance` 至多 15 项（known 字段；unknown key 不产生项）、每项至多 `MAX_SOURCES_PER_ITEM` 个 id（每个 id 必须在已受限的 `contributing_source_ids` 中）；
`image_failures` 至多 `len(ImageRole) × len(ImageFailureKind)`（Frozen Base 上为 `4 × 13`）组、每组至多 500 个 HTTP 状态码；
`artifact_counts` / `effect_counts` 定长。只被计数、不逐项投影的输入 tuple（`image_failures`、`artifacts`、`completed_effects`、
units）没有单独上限：它们的处理时间与已驻留内存的输入大小成线性，输出大小为常数。因此单条目输出大小由常量上界约束。

### 21.3 输出字节上限

* `MAX_DIAGNOSTIC_OUTPUT_BYTES = 64 MiB` 是单次 `render_diagnostics_json` 的硬上限。
* 编码以 `json.JSONEncoder(...).iterencode(tree)` 流式产生 chunk，逐 chunk 累加长度（ASCII，故字符数 = 字节数）；累计超过上限时
  立即停止并抛 `DiagnosticsResourceLimitError`，不返回部分输出。输出恰好等于上限时成功。
* 裁决理由：结构上限已使输出有限，但其理论最大值远大于实际需要；显式字节上限是更简单、可证明的安全方案，并保证 renderer 的
  内存峰值有界。实际批量（3 个 source、默认 2 attempt）在 2000 条时远低于上限。

## 22. 序列化（冻结）

### 22.1 编码参数

`json.JSONEncoder(skipkeys=False, ensure_ascii=True, check_circular=True, allow_nan=False, sort_keys=True, indent=None,
separators=(",", ":"))`；`iterencode` 结果拼接后 `.encode("ascii")`。没有 BOM、没有末尾换行、没有 `default=` 回调。

### 22.2 JSON 树

renderer 先本地重检诊断图（第 24.4 节），再**显式**把模型转换为只由 `dict`（`str` key）、`list`、`str`、`int`、`bool`、`None`
组成的树（不使用 `dataclasses.asdict`，不对任何对象调用 `vars()` / `__dict__`）。转换规则：

* 模型 -> object，key 为第 11 节字段名，**每个字段总是出现**（不适用 / 缺失为 `null`，schema 定义的 absence）；
* 枚举成员 -> `.value`；`tuple` -> array；
* `(枚举, int)` 计数对 -> `{"<名>": value, "count": n}`，其中 `<名>` 为 `"stage"`（stage_counts）、`"artifact_kind"`、
  `"effect_kind"`；
* `IssueDiagnostics.detail` -> 两个 key：`"detail_type"`（第 17.2 节冻结类名表）与 `"detail"`（`.value`）；`None` 时两者为
  `null`；
* `PreviewSummary` -> `{"total", "ready", "blocked", "unprepared", "warned", "stage_counts"}`；`ExecutionSummary` -> 其全部 16 个
  字段（P4-C8 合同第 28.2 节）；
* `PreflightBlocker` -> `{"reason", "role", "errno", "ordinal"}`；`ExecutionFailure` -> `{"step", "kind", "stage", "write_stage",
  "errno", "artifact_kind", "ordinal", "target_published"}`。

### 22.3 顶层 object

```json
{
  "schema": "fc2_organizer.diagnostics",
  "schema_version": "1.0",
  "kind": "preview | execution",
  "shape": "main | retry | merged",
  "generation": 0,
  "batch_size": 0,
  "retry_scope": null,
  "path_policy": "none | basename",
  "timing_policy": "omit | include",
  "metadata_batch": {"generation": 0, "total": 0, "success": 0, "partial": 0, "failed": 0},
  "preview_summary": {},
  "execution_summary": null,
  "outcome": null,
  "items": []
}
```

（上例只示意结构；实际输出无空白、key 按字典序。默认输出中 `path_policy` 为 `"none"`。）

### 22.4 serialization ≠ persistence

`render_diagnostics_json` 只返回 bytes：不 `open`、不 `write`、不 `mkdir`、不 `rename`、不 `unlink`、不 `fsync`、不上传。调用方
是否、何时、写到哪里不属于 P4-C9；P4-C9 不提供任何 helper 来做这件事。

## 23. Schema version 与兼容规则（冻结）

* 每份输出都带 `"schema": "fc2_organizer.diagnostics"` 与 `"schema_version": "1.0"`；值来自模块常量，不由运行时对象决定。
* 版本格式 `MAJOR.MINOR`。v1 消费者必须忽略未知 key。
* **MINOR** 升级只允许新增 key（其缺失语义等同 `null`）；**MAJOR** 升级用于：删除 / 重命名 key、改变类型或语义、改变排序规则、
  改变任何枚举的 value 集合、改变脱敏或路径策略语义。
* P4-C9 复用的每个上游枚举的 value 集合由测试快照固定（第 28.1 节）；上游任何枚举变化都会使测试失败，从而强制 schema 版本
  审查与合同修订。v1.0 没有 schema migration（输出不落盘，没有需要迁移的存量数据）。

## 24. 失败模型（冻结）

### 24.1 错误映射

| 情形 | 错误 |
|---|---|
| 顶层参数不是精确 `BatchPreview` / `BatchExecutionResult` / `BatchDiagnostics`；策略参数不是精确枚举成员 | `DiagnosticsInputError` |
| 输入对象图未通过第 9 节本地校验（类型不符、子类、篡改、内部不一致、跨对象关系不成立、不支持的枚举 / 模型类型）；批准 property 返回值未通过校验 | `DiagnosticsIntegrityError` |
| 条目数 / 结构上限 / 输出字节上限 | `DiagnosticsResourceLimitError` |
| 将被输出的值违反第 17.2 / 18.2 节或计时范围 | `DiagnosticsUnsafeValueError` |
| 诊断模型构造违反自身不变量（实现缺陷或调用方手工构造了非法模型） | `DiagnosticsContractError` |
| 渲染前诊断图未通过本地重检 | `DiagnosticsIntegrityError` |
| JSON 编码阶段的其它 `ValueError` / `TypeError` / `RecursionError` | `DiagnosticsSerializationError` |

### 24.2 builder 检查顺序（冻结）

1. 顶层输入精确类型 -> `DiagnosticsInputError`；
2. `path_policy` / `timing_policy` 精确枚举 -> `DiagnosticsInputError`；
3. `items` 是精确 `tuple`（否则 `DiagnosticsIntegrityError`），`len(items) <= MAX_DIAGNOSTIC_ITEMS`（否则
   `DiagnosticsResourceLimitError`）；
4. 递归 Consumed-Object 本地校验（第 9.5 节）：批级标量 -> `metadata_batch`（M-14 及其全部嵌套）-> 按 `index` 顺序逐条目
   （M-05 / M-06 及其全部嵌套）；各结构上限在迭代对应容器前检查；**每个 caller-originated 容器在本步完成其 Phase V**（全部元素 / key 的 exact-type 校验；
   `field_sources` 的有界单遍 key 扫描与 exact-`str` key 验证也在本步完成，第 9.2 节第 9 条 Step 1-3），第 9.0.1 节 V-2；
5. 跨对象一致性（Phase R：成员判定 / 相等 / 唯一性 / 查表，只作用于本步之前已完成 Phase V 的容器；`field_sources` 的 known-key 查询与 value 校验即本步，Step 4-5）（第 9.6 节），含：`retry_kind` 的本地推导 `expected_kind`、`retry_material` 的存在性 / 对象身份 / checkpoint 关系
   （第 9.6.4 节）、retained artifact / retry payload 字节的**本地计算**及其与 `retention_budget_bytes` / `retry_budget_bytes` 的预算
   关系（第 9.6.1 / 9.6.2 节）；
6. 安全输出检查（第 9.7 节：source id、`error_type`、`BASENAME` 下的 basename、`INCLUDE` 下的计时）；
7. **此后才**读取第 9.3 节批准 property，按此**固定顺序**：逐条目 `ItemPreview.warnings`（`PREVIEW`）/ `ItemExecution.retry_kind`（`EXECUTION`），然后 `summary`，然后（`EXECUTION`）`outcome`；读取每个 property 的前置条件是其
   第 9.3.1 节依赖图已全部通过本地校验；并对其返回值做本地校验（`retry_kind` 须 `is expected_kind`；`summary` 须通过 M-08 / M-09 且 `total == len(items)`）；
8. projection（只读校验快照与第 7 步已校验的返回值）；
9. 构造 `BatchDiagnostics`。

第 1-6 步之前不读取任何 summary / outcome / retry_kind / warnings / 公开 property、不做任何路径投影、不调用任何上游方法。任何一步
失败都不返回部分结果；失败后输入对象逐字段不变。

### 24.3 输入完整性：本地校验（替代原“上游 `__post_init__` 重检”，冻结）

P4-C9 不调用 P4-C8 `revalidate`，也不调用任何上游 `__post_init__` 或其它上游 validator / 实例方法。输入完整性**完全**由第 9 节
Local Validation 保证：第 9.5 节 Consumed-Object Validation Map 逐类型覆盖全部被消费对象，第 9.6 节逐项覆盖跨对象关系。本节与
第 27.1 节完全一致：生产代码对上游对象 0 private attribute、0 dunder 调用、0 `__post_init__`、0 实例校验方法、0 反射逃逸；
没有任何例外。

* 本地校验只读取对象，不触发 P4-C8 的一次性消费登记：对一个 preview / result 生成诊断之后，它仍然可以被 `execute` /
  `preview_retry` / `merge_retry` 消费（测试固定）。

### 24.4 renderer 检查顺序（冻结）

1. 参数精确为 `BatchDiagnostics` -> 否则 `DiagnosticsInputError`；
2. 本地重检整个诊断图：每个节点精确类型 + 调用 `models.py` 中该模型的模块级本地校验函数（不以属性方式访问 `__post_init__`）；
   诊断图中携带的三种上游值对象按第 9.5 节 M-08 / M-09 / M-25 / M-28 本地校验 -> 失败 `DiagnosticsIntegrityError`；
3. 转换 JSON 树（第 22.2 节；遇到第 17.2 节之外的 `str` -> `DiagnosticsUnsafeValueError`）；
4. 有界流式编码（第 21.3 节）；编码异常（`ValueError` / `TypeError` / `RecursionError`）-> 在 `except` 块之外抛
   `DiagnosticsSerializationError`，不链接。

### 24.5 诊断失败不影响原结果

诊断错误从不：修改输入模型、改变 retry eligibility、改变 summary / outcome、触发 retry、修改源文件或目标文件。原
`BatchPreview` / `BatchExecutionResult` 在诊断成功或失败后都逐字段相等、仍可按 P4-C8 合同使用。

## 25. Fail closed（冻结）

输入图被篡改、类型不符、资源超限、出现不支持的枚举 / 模型、或 renderer 发现不安全字段时，**整体失败**并抛对应的类型化错误。
诊断从不静默丢弃字段后输出“看似完整”的报告；第 13 节表中由 schema 明确定义的 absence 是唯一允许的缺省。

## 26. 无副作用（冻结）

`build_*` 与 `render_diagnostics_json` 是只读的。它们不触发：metadata fetch、图片获取、preview、execute、retry、merge、
preflight、filesystem 访问（读或写；basename 是纯字符串处理）、网络、`sleep`、线程创建、asyncio task / loop 创建、子进程、全局
logger 修改、环境变量读写、`sys.modules` 修改；不修改任何输入对象；不执行任何调用方钩子；不登记 P4-C8 一次性消费。

---

## 27. 架构边界与架构测试（冻结）

### 27.1 新文件 `tests/contract/test_diagnostics_architecture.py`（阶段化）

* **模块集合**按第 6 节阶段表精确断言：S1 断言 S1 集合，S2 断言 S2 集合，S3 断言最终集合；没有子目录。
* **`__all__`** 按第 8.1 节阶段集合精确断言（集合与顺序）：S1 断言 S1 `__all__`，S2 断言 S2 `__all__`，S3 断言最终 `__all__`；
  每个名称可解析。
* 每个模块的 import 只来自第 7 节逐模块允许清单与第 8.5 节允许名称；禁止子模块、私有名称、package 模块对象。
* 禁止 import / 引用第 7 节禁止清单（no network、no filesystem writer、no persistence、no Amane、no logging、no threads / async、
  no time / random、no unicodedata / inspect / sys / copy）。
* 禁止调用 / 访问：第 7 节列出的全部调用；**任何**以 `_` 开头的属性访问（AST：`ast.Attribute.attr` 以 `_` 开头即失败，包括
  `__post_init__`、`__dict__`、`__class__`、`object.__setattr__`），没有任何豁免；`os` 只允许 `os.path.isabs`、`os.path.join`、
  `os.path.basename`、`os.sep`、`os.altsep`，且只在 `validation.py`；**任何模块都不得 import `gc`**，也不得 import / 使用
  `inspect`、`ctypes`、`sys`、`pickle`、`marshal`、`copyreg`、`weakref`、`traceback`、`builtins`、`copy`（No New Introspection，
  第 7 节；AST 静态断言 + 运行时断言 `gc` 未被 `fc2_organizer.diagnostics` 的任何模块作为属性引用）；`math` 只允许 `math.isfinite`；`json` 只允许在 `render.py` 中使用 `json.JSONEncoder`；`types` 只允许 `types.MappingProxyType`；`sorted`、`min`、`max` 不得被调用（第 9.10 节 D-20）；内部常量 `MAX_PROVENANCE_KEYS` 定义在 `models.py`、不得出现在任何阶段的 `__all__`（第 8.3 节）；`validation.py` 不得调用方法名为 `keys` / `values` / `items` / `get` / `copy` 的方法（第 9.2 节第 9 条 Step 3 的 AST 代理）。
* 不 import / 调用 `BatchOrchestrator`、`merge_retry`、`preflight_execution`、`execute_filesystem`、任何 builder / acquirer /
  materializer / adapter（no orchestration ownership）。
* 模块级赋值只允许不可变常量（no global mutable registry）。
* 没有反向依赖：`src` 下其它模块不 import / 不提及 `fc2_organizer.diagnostics`；`fc2_organizer/__init__.py` 不 import 它；
  裸 `import fc2_organizer` 不加载它（运行时检查）。
* 运行时：在阻断 `amane`、`requests` 的 import hook 下，`fc2_organizer.diagnostics` 可以导入（S2 起完成一次 build，S3 起完成一次
  build + render）。

### 27.2 生产 / 测试私有接缝许可

测试可以 import 下层私有接缝与既有测试 helper（例如 `tests/unit/orchestration/_fakes.py`、`_helpers.py`、
`fc2_metadata_core.aggregation.policy.FIELD_ORDER`、上游私有表）用于构造输入与交叉验证，也可以 monkeypatch 上游类的
`__post_init__` 以证明生产代码不调用它；该许可只适用于 `tests/**`，生产代码一律禁止。测试只**读取 / 调用**既有 helper，不修改它们。

### 27.3 既有架构守卫的授权更新（S1 执行，逐项最小改动）

新顶层 package 会使以下既有守卫失败；本合同授权且**只**授权以下最小改动（不得放宽任何其它断言）：

| 文件 | 守卫 | 授权改动 |
|---|---|---|
| `tests/contract/test_discovery_architecture.py` | `test_organizer_package_has_no_other_stray_top_level_modules_yet` | 顶层集合加入 `"diagnostics"` |
| `tests/contract/test_planning_architecture.py` | 顶层集合断言（约第 200 行） | 同上 |
| `tests/contract/test_publication_architecture.py` | 顶层集合断言（约第 174 行） | 同上 |
| `tests/contract/test_nfo_architecture.py` | 顶层集合断言（约第 206 行） | 同上 |
| `tests/contract/test_execution_architecture.py` | `test_no_reverse_dependency_on_execution` | `exempt` 加入 `ORGANIZER_SRC_ROOT / "diagnostics"`；并新增一条更严格断言：diagnostics 只能 `from fc2_organizer.execution import <第 8.5 节名称>` |
| `tests/contract/test_materialization_architecture.py` | `test_no_reverse_dependency_on_materialization` | 排除集合加入 diagnostics 根目录；并新增一条更严格断言：diagnostics 只能从裸 `fc2_organizer.materialization` import `ArtifactKind`、`ArtifactWriteRequest`、`MappingRejectionReason` |
| `tests/contract/test_orchestration_architecture.py` | `test_no_reverse_dependency_on_orchestration` | 跳过 diagnostics 根目录；并新增一条更严格断言：diagnostics 只能 `from fc2_organizer.orchestration import <第 8.5 节名称>`，不得引用 `BatchOrchestrator` / `merge_retry` / `revalidate` / 任何私有名称 |

这些是测试守卫的范围扩展，不改变任何 CLOSED package 的生产语义；P4-C8 合同第 34.3 节已有同类先例。

---

## 28. 测试矩阵（冻结）

所有 P4-C9 测试位于 `tests/unit/diagnostics/` 与 `tests/contract/test_diagnostics_architecture.py`。核心测试（Windows、脱敏、
确定性、资源、架构、本地校验）**不得** skip；任何平台不可用的 evidence 必须在 HANDOFF 标记为 `EVIDENCE GAP`，不得伪 PASS。

### 28.1 Unit

| 主题 | 要求 |
|---|---|
| 模型校验 | 每个模型的每个字段：合法值、错误类型、`bool` 冒充 `int`、子类冒充、越界、跨字段不变量；全部为 `DiagnosticsContractError` 且 message 固定 |
| 精确公开 API（阶段化） | 当前阶段 `__all__` 集合与顺序（S1 / S2 / 最终）；函数签名（positional-only / keyword-only / 默认值，含默认 `PathPolicy.NONE`）；常量数值；`MAX_DIAGNOSTIC_ITEMS == MAX_BATCH_ITEMS`；`PROVENANCE_FIELD_ORDER == aggregation.policy.FIELD_ORDER`；内部常量 `MAX_PROVENANCE_KEYS == 64`、`MAX_PROVENANCE_KEYS >= len(PROVENANCE_FIELD_ORDER)`、定义在 `models.py`、**不**在任何阶段 `__all__`、不出现在任何诊断模型字段或 JSON 输出中 |
| 错误 | 层次与多重继承；固定 message；`__cause__` / `__context__` 为 `None`；message 不含任何 Validation-Only 值 |
| 枚举快照 | 四个新枚举的成员与 value；第 11 节复用的全部上游枚举 value 集合快照 |
| 本地冻结表 | 表 T-1..T-4 与上游实现（P4-C8 `_ISSUE_TABLE`、Phase 3 `ALLOWED_ERROR_KINDS`、P4-C7 `_ARTIFACT_ROLE`、P4-C8 `_BLOCKED_REASONS` / `_DUPLICATE_REASONS`）逐项相等 |
| 本地校验（逐模型） | 第 9.5 节 M-01..M-30 每一行：精确类型（子类拒绝）、每个列出字段的类型 / 范围、容器精确类型、枚举精确、bool 冒充 int、跨对象关系（第 9.6 节每一条）各有正例与反例；错误类型符合第 9.5 节 |
| 篡改（`object.__setattr__`） | 至少篡改 `BatchResult`（index、generation、items 类型、lineage）、`OrganizePlan`（target_directory、target_media_path、子路径、operations、library_root、source 字段）、`ArtifactWriteRequest`（kind、target_path、content 类型、ordinal、manifest 顺序）、`SourceResult.metadata`、`AggregationResult` 嵌套（source_results、traces、conflicts、contributing、`field_sources` 的容器类型与值类型）、`ExecutionResult` / `CompletedEffect` / `ExecutionFailure` / `LeftoverTemporary`、`RetryMaterial`（见下一行）、`ItemPreview` / `ItemExecution` 关键关系；每例验证：(A) fail closed；(B) 发生在 projection 与批准 property 读取之前（以 sentinel / 计数证明）；(C) 不返回部分诊断；(D) 不执行恶意钩子；(E) 输入对象逐字段不变 |
| 恶意嵌套子类（R-02 non-vacuity） | 以 test-local 子类覆写方法 / property / `__eq__` / `__hash__` / `__bool__` / `__len__` / `__repr__` / `__str__` / `__getattribute__`（对 frozen dataclass 允许的方式）并设置 sentinel，经 `object.__setattr__` 植入：`SourceResult.metadata`（`NormalizedMetadata` 子类覆写 `meets_minimum_success` 等）、`AggregationResult.metadata` / `source_results` 元素 / traces 元素 / conflicts 元素、`BatchItemResult.aggregation_result`、`ItemPreview.plan` / `preflight` / `media_item`、`ExecutionPreflight.artifacts` 元素、`ItemExecution.execution`、`ItemExecution.retry_material` 及其 `plan` / `artifacts` 元素 / `checkpoint`、`retry_scope`（含覆写 `__eq__` / `__hash__` 的恶意元素）、`field_sources` 某个 known 字段值 tuple 中的 `str` 子类 source id，以及第 9.11 节 H-02 / H-03 / H-04 / H-07 / H-08 / H-11 列出的每个 caller-originated 容器的恶意元素（`str` 子类 source id 出现在 `contributing_source_ids`、`disabled_source_ids`、`alternatives`、`SourceResult.source_id`、trace `source_id`；`int` / 枚举 / `ItemWarning` 位置上的恶意子类元素）；断言：抛 `DiagnosticsIntegrityError`，且全部 sentinel 未触发。**Sentinel 复位规则（冻结，Design-R3）**：凡对象经**上游公开构造器**构造（`str` 子类 key / id、`NormalizedMetadata`、`SourceResult`、`AggregationResult` 等），上游构造本身可能执行子类钩子（第 9.0 节 U-2 / U-4、UC-2）；测试必须在**全部上游构造完成之后、调用 P4-C9 builder 之前**把全部 sentinel 复位为 0，并断言**从复位点起**为 0 —— 这证明 P4-C9 自己未执行 caller hook。**范围说明（Design-R2；Design-R3 澄清）**：本行只覆盖第 9.0 节 A / B 层（公开字段、精确类型可观察；含公开构造器可产生的 `str` 子类）的恶意子类；“`MappingProxyType` 隐藏 referent 被替换为 hostile mapping”属于第 9.0 节 C 层，**不**在测试模型内，也不测试 / 不承诺 opaque referent introspection；公开构造器可产生的 `str` 子类 key **不是** C 层，由下方 R2-01 gate 行覆盖 |
| RetryMaterial 篡改（R-03 non-vacuity） | 全部在 projection 与批准 property 读取之前 fail closed（`DiagnosticsIntegrityError`）：(1) material 存在性与 `retry_kind`（由已校验字段推导）矛盾（该有无 / 不该有有）；(2) `material.plan` 不是 `item.plan`（`==` 相等但非同一对象、路径相同但非同一对象）；(3) `RESUME` 的 `material.checkpoint` 不是 `execution.checkpoint`（相等的另一对象 / 不同对象）；(4) `RESUME` 的 `material.checkpoint` 缺失；(5) `FRESH_REEXECUTE` 错误携带 checkpoint；(6) material 的 artifact 元素类型 / `content` 类型被篡改（非 `ArtifactWriteRequest`、非 `bytes`）；(7) retained payload 超过 `retention_budget_bytes`（complete）/ `retry_budget_bytes`（retry shape）；另有正例：`PREFLIGHT_RECHECK` / `DEFERRED` 的 `checkpoint` 为 `None` 与为精确 `ExecutionCheckpoint` 均被接受（不增加 P4-C8 没有的约束）；retained 字节按引用重复计数（共享 bytes）的正例；诊断输出不含任何 `content` 字节 |
| `retry_kind` 一致性 | `ItemExecution.retry_kind` property 返回值被替换为与本地推导不同的 `RetryKind`（test-local 子类不可用——类型精确；以 monkeypatch 类 property 的方式）-> 第 24.2 节第 7 步 `DiagnosticsIntegrityError`；六种 `RetryKind` 的本地推导与 P4-C8 产生值逐条相等 |
| 无上游 `__post_init__` 调用 | 测试期间把第 9.5 节所有上游类的 `__post_init__` 替换为“触发即失败”的 sentinel（并把 `NormalizedMetadata.meets_minimum_success`、`AggregationResult.result_for` / `trace_for`、`retained_retry_payload_bytes` / `retained_artifact_bytes` 等实例方法 / property 同样替换），合法输入的 build + render 全部成功且 sentinel 计数为 0；mutation“生产代码调用某个上游 `__post_init__`”被杀死 |
| 无反射原语 | 架构测试（AST）：全部 diagnostics 模块不 import `gc`、`inspect`、`ctypes`、`sys`、`pickle`、`marshal`、`copyreg`、`weakref`、`traceback`、`builtins`、`copy`；运行时在测试期间把 `gc.get_referents` 替换为“触发即失败”的 sentinel，合法输入的 build + render 全部成功且计数为 0 |
| preview 诊断 | READY / BLOCKED / UNPREPARED；每个 preview 可达的 `IssueReason`；warnings；冲突组；retry preview（`RETRY` shape、`retry_origin`、`retry_scope` 顺序、空 scope） |
| execution 诊断 | 每个 `ExecutionDisposition`；`ExecutionStatus` SUCCESS / PARTIAL / FAILED；failure 映射；effect / artifact 计数；checkpoint_present；leftover；MAIN / RETRY / MERGED 三种 shape（本地判定与 P4-C8 产生的形态逐一一致） |
| source 诊断 | SUCCESS / NOT_FOUND / 五种 operational failure；refined `SourceErrorKind`；CIRCUIT_OPEN（无 attempt）；deadline during attempt / backoff；retried；无 trace（纯 merge）；disabled sources |
| field provenance（上游信任边界测试） | (1) `field_sources` 不是精确 `MappingProxyType`（例如普通 `dict`、`MappingProxyType` 子类不可构造故以普通 `dict` / 自定义 mapping 对象）-> `DiagnosticsIntegrityError`；(2) 某 known key 的值不是精确 `tuple` / 元素不是精确 `str`（含 `str` 子类 source id，经 `NormalizedMetadata` 公开构造器构造后复位 sentinel）-> `DiagnosticsIntegrityError`；(3) known source id 不属于 `contributing_source_ids` -> `DiagnosticsIntegrityError`；(4) 固定字段顺序投影不依赖插入顺序（以反转 / 打乱插入顺序的 `NormalizedMetadata` 构造证明输出逐字节相同）；(5) 正常 public 构造的 `NormalizedMetadata` 稳定完成 provenance 投影（每个字段类别：number / scalar / collection / external_ids；只出现已填充字段；优先级顺序；FAILED 时为空，且 FAILED（`metadata is None`）不执行 key 扫描）；(6) `field_sources` 中含不属于 `PROVENANCE_FIELD_ORDER` 的 unknown **exact-`str`** key：被扫描并计入上限，但不投影、不输出、不影响结果；(7) `MappingProxyType` 迭代仅用于 validation：成功输出不依赖 key 插入顺序（与 (4) 合并证明）。**不**测试 / 不承诺 opaque referent introspection |
| **R2-01 `field_sources` key-subclass gate（EvilStr Public-Constructor Gate；non-vacuity，冻结）** | (1) 定义 `EvilStr(str)`，覆写 `__hash__`、`__eq__`、`__ne__`、`__lt__`、`__bool__`、`__len__`、`__repr__`、`__str__` 并各自累加 sentinel；(2) 通过**正常 upstream public constructor** 构造输入：`NormalizedMetadata(field_sources={EvilStr("title"): ("src1",)})`，并经公开构造路径放入 `AggregationResult`（UC-7 证明可行）及真实 `BatchItemResult` / `ItemPreview` / `ItemExecution` 图（`NormalizedMetadata` 本身**必须**由公开构造器构造；其外层某一层若只能以 `object.__setattr__` 嵌入，须在测试注释中注明）；(3) **上游构造完成之后、调用 P4-C9 builder 之前，把全部 sentinel 复位为 0**（上游构造会执行 `EvilStr.__hash__` / `__repr__`，UC-2，不属于 P4-C9）；(4) 调用 `build_preview_diagnostics` / `build_execution_diagnostics`，断言 `DiagnosticsIntegrityError`、message 固定且不含 key 文本，且**从复位点起** `__hash__` sentinel `== 0`、`__eq__` sentinel `== 0`（其余 sentinel 同为 0）——证明 P4-C9 自己未执行 caller hook；(5) 变体：(a) 与 known 字段同名的 `EvilStr("title")`；(b) unknown 名 `EvilStr("zzz")`（证明 scan 覆盖全部 stored key，不只 known key）；(c) hash-collision 变体：`__hash__` 返回 `hash("title")`、`__eq__` 返回 `False`，与 exact `"title"` key 共存于同一 dict；(d) `EvilStr` key 位于第一 / 中间 / 最后；(e) 与合法 known key 同批；(f) 构造 `EvilStr` key 后其 value 合法（排除 value 校验先失败的假阳性）；(g) V-4：`EvilStr` key 在前、其后另有 `MAX_PROVENANCE_KEYS + 1` 个 exact key -> 先遇到者决定错误类型（`DiagnosticsIntegrityError`）。**Normal-Key Positive Control（必须同时存在）**：全部 key 为 exact `str`，包含全部 15 个 known key 与若干合法 unknown exact-`str` key（例如 `"unknown_field_1"`）；builder 正常通过，输出的 `field_provenance` 恰为 known 字段（unknown 不出现在模型 / JSON），反转 / 打乱插入顺序后输出逐字节相同——证明 key-scan gate 不是只会拒绝输入。|
| **R2-01 `MAX_PROVENANCE_KEYS` 边界与 Unbounded Key Materialization（non-vacuity，冻结）** | (1) **exact limit**：恰 `MAX_PROVENANCE_KEYS`（64）个 exact-`str` key（15 known + 49 unknown）-> 通过；(2) **limit + 1**（65）-> `DiagnosticsResourceLimitError`；(3) **早停**：65 个 exact-`str` key 之后**再**追加一个 `EvilStr` key（第 66 个）-> 抛 `DiagnosticsResourceLimitError`（**不是** `DiagnosticsIntegrityError`），且 `EvilStr` sentinel 自复位点起为 0（证明在观察到第 65 个 key 时即停止，未读取之后的 key）；(4) key 数远超上限（`10 × MAX_PROVENANCE_KEYS`）-> `DiagnosticsResourceLimitError`；(5) **不物化**：测试以 tripwire 证明——在 `fc2_organizer.diagnostics.validation` 模块命名空间内把 `list`、`tuple`、`set`、`frozenset`、`sorted`、`dict`、`len` 临时遮蔽为“若实参是 `MappingProxyType`（即 `field_sources`）则失败”的包装（`monkeypatch.setattr(..., raising=False)`；包装对其它实参透传），合法输入与超限输入的 build 均不触发 tripwire；(6) AST（第 27.1 节）：`validation.py` 不调用 `.keys()` / `.values()` / `.items()` / `.get()` / `.copy()`。 |
| **上游 characterization（Design-R3，固定第 9.0 节 U-1..U-5）** | `tests/unit/diagnostics/test_diagnostics_upstream_characterization.py`：**UC-1** `NormalizedMetadata(field_sources={EvilStr("title"): ("a",)})` 经公开构造器成功，stored key `type(k) is EvilStr`（未被规范化为 exact `str`）；**UC-2** 上游构造本身执行了 `EvilStr` 钩子（`__hash__` 计数 `> 0`），证明测试必须在构造后复位 sentinel；**UC-3** 非 `str` key（`int`、`bytes`、`None`、`tuple`）以 `MetadataContractError` 拒绝；**UC-4** `type(md.field_sources) is MappingProxyType`，赋值 / 删除抛 `TypeError`，value 为精确 `tuple`；**UC-5** 快照隔离：构造后增删 / 修改调用方传入的 `dict` 或自定义 `Mapping` 不影响 `md.field_sources`（“新建私有 dict”的行为证据，不 introspect proxy）；**UC-6** value tuple 的 `str` 子类元素被接受并保留；**UC-7** `AggregationResult` 公开构造器接受携带 `EvilStr` key 的 `metadata`，且 `SourceResult` / `AggregationResult` 公开构造器接受 `str` 子类 source id（public-constructor reachability）；**UC-8** 真实 Phase 3 producer（经公开管线 / `merge`，三 source 全字段 populate）产生的 `field_sources` key 集合 `⊆ FIELD_ORDER` 且 `len <= 15 <= MAX_PROVENANCE_KEYS`（全字段 populate 恰为 15）；**UC-9** 语言级分派事实（Python >= 3.11）：对含 `EvilStr` key 的 proxy，`for key in proxy` + `type(key) is str` 不触发任何钩子，而 `"title" in proxy` 触发子类 `__eq__`（固定“必须先扫描后查询”的原因）。这些测试固定本合同引用的上游事实；上游变化使其失败即强制合同修订，**不是**对上游的修改授权。 |
| Dispatch Safety Matrix 覆盖（Design-R3） | 第 9.10 节每个非 NOT USED 行（D-01..D-05、D-07..D-19、D-23..D-31）至少一个测试，docstring 标记 `[D-xx]`；hostile 对象携带 `__hash__` / `__eq__` / `__ne__` / `__lt__` / `__bool__` / `__len__` / `__iter__` / `__repr__` / `__str__` / `__format__` / `__getattribute__` sentinel（上游构造后复位）；覆盖第 9.11 节 H-01..H-15 的每个 caller-originated 容器；Phase V→Phase R 非空洞性：`contributing_source_ids = ("src1", EvilSID("src2"))` 且被查 id 不等于首个元素的构型下，“成员判定先于 Phase V 全部完成”的实现会触发 `EvilSID.__eq__` 而被杀死；NOT USED 行（D-06、D-20、D-21、D-22）由 AST 与 sentinel（`__bool__` / `__len__` / `__repr__` / `__str__` / `__format__` 不被调用）证明；批准 property 的依赖图（第 9.3.1 节）逐行：依赖图任一元素被篡改 -> 在读取该 property 之前 `DiagnosticsIntegrityError`（以 property 读取 sentinel / 计数证明未读取）。 |
| issues / warnings | 原样复制；detail 类型名表；`error_type` 规则 |
| failure / retry 映射 | `retry_kind` 与 P4-C8 `ItemExecution.retry_kind` 逐条相等（全部六种 RetryKind） |
| 排序 | 第 16 节每一行 |
| 确定性 | 第 15 节；重复构建 / 渲染逐字节相同 |
| 路径策略 | 默认（不传参）为 `NONE`：全部路径派生字段为 `None`、输出不含任何文件名；显式 `BASENAME` 输出 basename；第 18.2 节 grammar 每一条的边界（长度 255 / 256、`.` / `..`、`/` 与 `\`、每类禁止码点）-> `DiagnosticsUnsafeValueError`；`NONE` 下即使文件名含禁止码点也不失败（不计算 basename） |
| 脱敏 | 第 17 节；canary（第 28.5 节） |
| JSON / schema | 顶层 key 集合；每类对象 key 集合恒定；`null` 表达；`sort_keys`；ASCII-only；无末尾换行；schema 常量 |
| 资源上限 | 第 21.2 节每项的边界（等于上限成功、上限 + 1 失败、且失败发生在迭代前；`MAX_PROVENANCE_KEYS` 按上一行“R2-01 `MAX_PROVENANCE_KEYS` 边界”：单遍计数、第 65 个 key 即停、不物化）；输出字节上限（第 28.4 节） |
| 非法输入与检查顺序 | 错误顶层类型、子类、错误策略类型；`items` 非 tuple；第 24.2 节检查顺序（同时违反多条时报告最先的一步） |
| 计时策略 | OMIT 时全部为 `None`；INCLUDE 时截断规则、范围、NaN / 负数 / 超限 -> `DiagnosticsIntegrityError`（输入不合法）或 `DiagnosticsUnsafeValueError`（超出 `MAX_TIMING_MS`） |
| 无副作用 | 第 28.6 节 |

### 28.2 Architecture

第 27.1 节全部条目（阶段化 module set / `__all__`、forbidden private / dunder access 零豁免、forbidden imports、no network、no
filesystem write、no persistence、no Amane、no orchestration ownership、no thread / task creation、no global mutable registry、
`os` / `math` / `json` / `types` 成员白名单、no `gc` / no introspection primitive、no reverse dependency）；以及第 27.3 节的授权更新。

### 28.3 Integration（真实 P4-C8 编排 + 脚本化 fake engine / 图片 client + 临时目录文件系统）

至少覆盖并对每个场景同时断言模型与 JSON：SUCCESS batch；PARTIAL batch；FAILED batch；BLOCKED 条目；UNPREPARED 条目；ABORTED 条目；
metadata failure（engine 异常、FAILED aggregate）；metadata partial；图片 warning（缺失 poster / fanart / thumb、无 extrafanart、
候选失败）；execution PARTIAL；execution FAILED；RESUME 候选；FRESH_REEXECUTE；METADATA_REFETCH；PREFLIGHT_RECHECK；DEFERRED
（NOT_SELECTED 与 CANCELLED）；NONE；retry preview 与 merged result；诊断后 preview 仍可 `execute`、result 仍可 `preview_retry`、
retry result 仍可 `merge_retry`（未被消费）。每个场景同时证明真实 producer 的输出全部通过本地校验（第 9.2 节末段），并在默认
`PathPolicy.NONE` 与显式 `BASENAME` 下各渲染一次。

### 28.4 500-item 诊断门槛与 MAX 边界

* **500 逻辑条目诊断投影门槛**（`tests/unit/diagnostics/test_diagnostics_scale_gate.py`）：以公开构造函数（及真实 planner /
  mapping 产生的 plan / manifest）构建合法的 P4-C8 `BatchPreview` 与 `BatchExecutionResult`（覆盖全部 disposition / status /
  RetryKind / issue 类别的混合分布，不执行真实文件系统；不重复 P4-C8 S6 的 500-item 文件系统验收），验证：条目顺序、summary
  映射（与 P4-C8 summary 逐字段相等）、确定性（两次构建相等、两次渲染逐字节相同、临时身份全部替换后逐字节相同）、资源上界、
  脱敏（canary 扫描）、序列化（JSON 可被 `json.loads` 解析且结构符合第 22 节）、本地校验全部通过。
* **MAX 边界**：`MAX_BATCH_ITEMS`（2000）条目的 preview 与 execution 诊断成功构建并渲染（且低于输出上限）；以
  `object.__setattr__` 把 `items` 篡改为 2001 条后，builder 在任何逐条工作之前抛 `DiagnosticsResourceLimitError`（以计数 fake
  证明没有逐条访问）。
* **provenance key 边界（Design-R3）**：`field_sources` stored key 数恰为 `MAX_PROVENANCE_KEYS`（64）成功；`MAX_PROVENANCE_KEYS + 1`（65）抛 `DiagnosticsResourceLimitError`；第 65 个 key 之后的 `EvilStr` key 不被读取（早停非空洞性）；`validation` 命名空间 tripwire 证明不物化 proxy（第 28.1 节“R2-01 `MAX_PROVENANCE_KEYS` 边界”行）；2000 条目 × 每条 64 个 key 的批仍成功构建（上限内的最坏输入）。
* **输出字节上限**：以 monkeypatch 把 `MAX_DIAGNOSTIC_OUTPUT_BYTES` 设为某个真实输出的精确长度 -> 成功；设为该长度 − 1 ->
  `DiagnosticsResourceLimitError` 且未返回部分输出；并证明编码在超限后停止（计数 chunk）。

### 28.5 非空洞性（Non-Vacuity，冻结）

测试必须植入 canary，并以 mutation（测试内 monkeypatch 投影 / 校验函数，不提交生产改动）证明断言会失败：

| 类别 | canary / mutation | 必须的杀死结果 |
|---|---|---|
| 结构化渠道脱敏（A 类） | 在 `SourceResult.error_detail` 植入 `Authorization: Bearer C9CANARY-AUTH` 与 `Cookie: session=C9CANARY-COOKIE`；在 metadata 标题 / 简介 / URL query 植入 `C9CANARY-TEXT` / `token=C9CANARY-URL`；在冲突值、`external_ids` key / value 植入 canary；engine 抛出 message 为 `C9CANARY-EXC` 的异常；源路径父目录与 library root 植入 `C9CANARYDIR` / `C9CANARYROOT` | 在 `NONE` **与** 显式 `BASENAME` 下输出都不含任何 A 类 canary；mutation “投影时附带 `error_detail`”、“附带异常 message / repr”、“输出 absolute path / 父目录”、“输出冲突值”各自使 canary 扫描失败 |
| 默认 NONE 的 secret-like basename（R-04） | 媒体文件名为 `Authorization-C9CANARY.mp4`、`Cookie-C9CANARY.mp4`、`token-C9CANARY.mp4` | 默认（不传 `path_policy`）输出完全不含 `C9CANARY`；mutation “默认改为 `BASENAME`”、“`NONE` 下仍计算 / 输出 basename” 各自被杀死 |
| 显式 BASENAME opt-in | 同上文件名，显式 `PathPolicy.BASENAME` | 输出包含这些可打印 basename（符合第 17.1 节 B 类 opt-in 合同：P4-C9 不做关键词扫描），且不含父目录 canary |
| 控制字符 basename | 文件名含 `\x01`、`\x1b`、`\x7f`、`\x85`、`U+2028`、`U+202E`、`U+FEFF`、孤立代理（平台允许时；不允许时以 hand-built 合法上游模型构造） | 显式 `BASENAME` -> `DiagnosticsUnsafeValueError`；默认 `NONE` -> 成功且输出不含这些码点；mutation “去掉禁止码点检查” 被杀死 |
| 排序 | golden 期望输出（小批量，含多 source、多字段出处、多 conflict、多图片失败组） | mutation “source 按字母排序”、“按 `field_sources` dict 迭代顺序输出”、“items 反转”、“image 失败组按出现顺序”、“`retry_scope` 迭代 frozenset” 各自被杀死；构造时反转 `field_sources` 插入顺序不改变输出 |
| 确定性 | 临时身份全部替换、完成顺序反转 | mutation “输出 `preview_id` / `result_id` / lineage token / `preflight_id` / `seal`” 被逐字节比较杀死 |
| 无副作用 | 见第 28.6 节 | mutation “投影时调用 `preflight_execution` / orchestrator / `open`” 被杀死 |
| fail closed / 本地校验 | 篡改输入、恶意子类 | mutation “跳过某个 M-xx 精确类型检查”（至少覆盖 `SourceResult.metadata`、`OrganizePlan`、`ArtifactWriteRequest`、`BatchResult`）、“跳过第 9.6.5 节 plan 布局检查”、“跳过第 9.6.4 节 `retry_material` 存在性 / 身份 / checkpoint 关系检查”（逐项：存在性、`material.plan is item.plan`、RESUME checkpoint 身份、FRESH 无 checkpoint）、“跳过第 9.6.1 / 9.6.2 节 retained 预算检查”、“信任 `retry_kind` property 而不做本地推导比较”、“跳过条目数上限”、“在第 7 步之前读取 summary” 各自被杀死（sentinel 触发或 fail closed 断言失败） |
| **R2-01 key 扫描 / dispatch-safety** | R2-01 gate 与边界测试（第 28.1 节） | mutation（测试内 monkeypatch 校验函数，不提交生产改动）各自被杀死：“在 Step 3 之前或之中执行 `name in proxy` / `proxy[name]`（边验边查）”-> `EvilStr` 变体 (a) / (c) 的 `__eq__` sentinel 触发；“跳过 `type(key) is str`”或“只检查 known key 的类型”-> 变体 (b) 不再抛 `DiagnosticsIntegrityError` 或 sentinel 触发；“先 `list()` / `tuple()` / `set()` / `sorted()` / `len()` 物化 proxy 再检查大小”-> tripwire 触发；“去掉 `MAX_PROVENANCE_KEYS` 上限 / `>` 改 `>=` / 计数在检查之后 / unknown key 不计数”-> exact-limit 与 limit + 1 边界失败；“在第 65 个 key 之后继续读取”-> 早停测试得到错误类型 `DiagnosticsIntegrityError` 或 sentinel 触发；“Phase R 成员判定先于同一容器 Phase V 全部完成”-> Phase V→Phase R 非空洞性用例的 `EvilSID.__eq__` sentinel 触发；“不复位 sentinel”不是 mutation（是测试纪律）——测试断言复位后计数的**起点**（UC-2 证明构造期确有触发） |

### 28.6 无副作用证据

* 对 integration 场景：诊断前后对临时目录树做完整快照（路径、类型、大小、mtime_ns、内容 hash）——完全相等。
* fake engine / 图片 client / P4-C7 文件系统接缝的调用计数在诊断期间增量为 0。
* 在诊断调用期间以 monkeypatch 让 `BatchOrchestrator.preview` / `execute` / `preview_retry`、`merge_retry`、`preflight_execution`、
  `execute_filesystem`、`builtins.open`、`os` 的变更与查询类函数（`stat`、`lstat`、`listdir`、`scandir`、`mkdir`、`rename`、
  `replace`、`unlink`、`remove`、`rmdir`）、`os.path.exists` / `realpath` / `islink`、`socket.socket`、`threading.Thread.start`、
  `asyncio.new_event_loop` / `asyncio.run`、`logging.Logger.handle` 一律抛错 —— 诊断仍成功。
* 输入对象图在诊断前后逐字段相等，嵌套对象身份（`is`）不变。

### 28.7 Full Test Gates

* P4-C9 专项：`tests/unit/diagnostics` + `tests/contract/test_diagnostics_architecture.py`；
* targeted organizer：`tests/unit/orchestration` + `tests/contract`（含第 27.3 节更新后的守卫）；
* contract：`tests/contract`；
* 全量：整个测试套件；
* 验收证据环境：Windows 11 / Python 3.12.x（这是 acceptance evidence environment，**不是**包的运行时支持边界；运行时权威仍是
  项目既有的 `Python >= 3.11`，第 7 节）；命令 `python -m pytest -q -p no:cacheprovider --basetemp=<job tmp>`（`fc2-organizer/` 下）。
* 全量 passed 数不得低于 accepted baseline **6178 passed / 40 skipped**（P4-C8 Final；若 Design Review 前 accepted parent 的
  基线合法变化，以实际 accepted parent 重新记录）；skipped 不得增加（新增 skip = NONE）。

## 29. 验收标准（冻结）

P4-C9 Independent Level 1 Review 以下列全部满足为 PASS 前提：

1. 公开 API（阶段化 `__all__`、默认 `PathPolicy.NONE`）、模块集合、模型、常量、错误与本合同逐项一致；
2. 第 12 节每条映射有对应测试；第 1 节问题表每一行可由诊断输出回答（integration 证据）；
3. 第 9 节输入校验策略逐项实现：0 上游 `__post_init__` / private / dunder / 实例校验方法调用（AST + 运行时 sentinel 双重证明）；
   M-01..M-30 与第 9.6 节每一条有正反例；第 9.0 节 A / B 层的恶意嵌套子类门槛全部 sentinel 未触发；`RetryMaterial` / retained
   预算门槛通过；0 个 `gc` / 反射原语 import；第 9.0.1 节 validate-before-dispatch 与第 9.10 节 Dispatch Safety Matrix 全部行有对应测试 / AST 证据；R2-01 EvilStr public-constructor gate、Normal-Key Positive Control、`MAX_PROVENANCE_KEYS` 边界与上游 characterization 测试通过；
4. 字段出处只来自 Phase 3 `field_sources`（先有界单遍 key 扫描与 exact key 验证，再按固定 known 字段名查询；不 introspect `MappingProxyType`）；没有重新聚合；
5. 没有重新计算 summary / outcome / RetryKind；与 P4-C8 值逐项相等；
6. 确定性、排序、脱敏（A 类绝对、B 类默认 NONE）、路径策略、异常安全、载荷边界、资源 / 输出上界、fail closed、无副作用全部有
   正向测试与第 28.5 节非空洞性证据；
7. 架构测试全部通过；第 27.3 节之外没有修改任何既有测试；
8. 没有修改任何 CLOSED package 的 `src/**`（`git diff --stat <Design-Accepted Head>..<C9 Head> -- fc2-organizer/src` 只含
   `src/fc2_organizer/diagnostics/**`）；
9. 第 28.7 节全部门槛通过，无新增 skip；
10. HANDOFF 提供 Contract -> implementation -> test 映射、diff scope、mutation 结果、evidence gaps、known limitations；
11. 风险升级门（第 5.3 节）未被触发，或已按 C 类处理。

## 30. 延续项（Deferred，冻结）

| 项 | 去向 |
|---|---|
| absolute / relative path opt-in | 不在 v1.0；若需要，合同修订 + 安全评估 |
| 诊断文件落盘、archive、历史比较 | 不在 v1.0（调用方自行处理 bytes；涉及落盘即触发第 5.3 节 A / B / C） |
| 实时进度 / 事件流 | 不在 v1.0（P4-C8 第 11.4 节） |
| 人类可读文本 / 表格渲染、本地化文案 | Phase 5+ 的 Adapter / UI 职责，消费本 JSON |
| P4-C10 跨包集成门槛对 diagnostics 的覆盖 | P4-C10 自行规划 |

## 31. 已知局限（冻结）

* `EXECUTION` 诊断不包含 preflight blocker 明细（`ItemExecution` 不携带 preflight）；需要时对 preview 生成诊断。
* 诊断不包含“最远到达阶段”、单个 source 的 adapter 自报耗时、HTTP 状态之外的 HTTP 细节、异常 message / traceback——公开
  evidence 不存在或被安全规则禁止。
* source id 不满足安全 id 规则（第 17.2 节）时诊断 fail closed，而不是改写。默认配置（`fc2db_net`、`javdb`、`av123`）满足规则。
* 显式 `BASENAME` 是披露策略：文件名可能包含用户自己写入的敏感文字，P4-C9 不做关键词扫描；需要零文件名输出时使用默认 `NONE`。
* 显式 `BASENAME` 下，含 `\`（POSIX 合法文件名字符）、控制字符、双向控制符等第 18.2 节禁止码点的文件名会 fail closed；此时可改用
  默认 `NONE`。
* 同一失败输入同时违反多条规则时，错误类型由遍历中最先遇到的违规决定（第 9.0.1 节 V-4）；这只影响失败输入的错误类，不影响任何成功输出。
* `field_sources` 的 stored key 数超过 `MAX_PROVENANCE_KEYS`（64）时 fail closed（`DiagnosticsResourceLimitError`），即使其中只有 known key；真实 Phase 3 producer 至多 15 个 key，不受影响。
* 本地校验比部分上游构造函数更严格（精确类型、有限计时值）；真实 producer 输出总满足它（integration 证明），但手工构造的、
  上游接受的边缘对象（例如 `int` 子类字段）会被诊断拒绝。
* 本地校验只覆盖被读取的字段及其冻结不变量（第 9.4 节）；未读取字段（例如 `NormalizedMetadata` 的文本字段、`EntryIdentity`）
  的篡改不被检测，但它们不可能影响诊断输出。
* 不透明实现伪造（第 9.0 节 C 层）不在 supported input graph 内：绕过上游公开合同把 `NormalizedMetadata.field_sources` 的
  `MappingProxyType` 隐藏被包装 mapping 替换成 hostile 实现，P4-C9 不使用反射 / 内省去识别，也不提供 sandbox guarantee。**公开构造器可产生的 `str` 子类 `field_sources` key / source id 不属于此局限**：它们是 A / B 层，由第 9.2 节第 9 条的有界 key 扫描与第 9.0.1 节 validate-before-dispatch fail closed。这不是
  “输入都被信任”：A / B 层（公开可检查的结构）仍按第 9.5 / 9.6 节 fail closed。P4-C9 同样不声称调用方安装的 audit hook /
  钩子在进程内不会运行；它只承诺自己不调用反射原语、不注册钩子、不在 A 层输入上调用 caller-provided 多态方法。
* P4-C9 假定单次 build 调用期间没有其它线程篡改输入对象图；校验快照（第 9.2 节第 11 条）消除了“校验后再读输入”的窗口，但第
  9.3 节批准 property 在校验后读取输入，若此间被并发篡改，其返回值仍经本地校验（M-08 / M-09 等）。
* 图片失败按 `(role, kind)` 分组，不保留 `candidate_index`；`external_ids` 冲突不输出 key。
* `TimingPolicy.INCLUDE` 输出依赖真实计时，跨运行不可逐字节比较（对相同输入仍确定）。
* 导入 `fc2_organizer.orchestration` 会传递加载 `httpx`（上游已冻结事实）；P4-C9 从不引用或使用它。
* 路径 basename 语义随运行平台；POSIX 原生行为若未在 POSIX 主机上运行，HANDOFF 标记为 `EVIDENCE GAP`。

## 32. 实现状态

S1 / S2 / S3 施工期间本节**不更新**（不创建 S 级状态 docs commit）；整个 C9 implementation 完成后，状态行随 HANDOFF / Final
Closure 一次同步。

| 项 | 状态 |
|---|---|
| P4-C9 Design（本合同 + 施工计划） | DESIGN-R3 IMPLEMENTED — INDEPENDENT DESIGN REVIEW REQUIRED |
| Original Design Review / Design-R1 Review / Design-R2 Review | FAIL / FAIL / FAIL |
| P4-C9-DESIGN-R-01 / R-04 / R-05 | CLOSED（Design-R1 Review 确认；Design-R3 语义 0 回归） |
| P4-C9-DESIGN-R-03 | CLOSED（Design-R2 Review 确认；Design-R3 语义 0 回归） |
| P4-C9-DESIGN-R1-01 / R1-02 | CLOSED（Design-R2 Review 确认；Design-R3 语义 0 回归） |
| P4-C9-DESIGN-R-02 | OPEN → Design-R3 REMEDIATED — REVIEW REQUIRED |
| P4-C9-DESIGN-R2-01（HIGH / BLOCKING；R-02 的 public-constructor-reachable 具体实例） | Design-R3 REMEDIATED — REVIEW REQUIRED |
| P4-C9 Frozen Contract | NOT YET ACCEPTED |
| P4-C9 Construction Plan | NOT YET ACCEPTED |
| P4-C9 Design Accepted Head | NOT ESTABLISHED |
| Implementation Input | NOT ESTABLISHED |
| S1 Diagnostic model / schema / projection skeleton | NOT STARTED |
| S2 Existing-result integration / local validation / source + field provenance mapping | NOT STARTED |
| S3 Safe output / redaction / architecture guards / tests / HANDOFF | NOT STARTED |
| P4-C9 Independent Level 1 Review | NOT STARTED |
| P4-C9 Production | NOT STARTED |

DESIGN-R3 INCREMENTAL DESIGN / CONTRACT / PLAN CLOSURE REVIEW PASS 本身建立 Design Accepted Head；之后不创建“design closure /
design accepted”之类的纯状态 docs commit，实现分支直接继续（治理文档第 11.1 节）。

---

## 附录 A. 裁决记录（设计者自行裁决；Owner Question Gate：BUSINESS DECISIONS ONLY，本合同无需外部业务决策）

| # | 问题 | 裁决 | 理由 |
|---|---|---|---|
| 1 | 统一模型还是两个模型 | 统一 `BatchDiagnostics` + 显式 `kind` 判别字段 + 字段适用表 | 消费者只需一个 schema；判别字段消除“靠 None 猜阶段” |
| 2 | 输出类型 `str` 还是 `bytes` | `bytes`（ASCII-only） | 逐字节确定性直接可比；无编码歧义；调用方可直接保存或发送 |
| 3 | JSON key 顺序 | `sort_keys=True`，有序集合一律用 array | 最简单、可证明的确定性；顺序语义全部落在 array 上 |
| 4 | 输出上界 | 显式 `MAX_DIAGNOSTIC_OUTPUT_BYTES` + 流式计数 | 比证明结构最大值更简单，内存峰值有界 |
| 5 | 路径默认（Design-R1 修订） | 默认 `NONE`；`BASENAME` 为显式 opt-in 披露；不提供 absolute | 闭合 R-04：默认不释放任何用户控制的路径文本；完整路径可由同进程 UI 经 index 回查 P4-C8 模型 |
| 6 | 计时默认 | `OMIT`；`INCLUDE` 只发布 engine / scheduler 测量值 | 跨运行可比；遵守 P2-R-07 |
| 7 | 输入完整性（Design-R1 修订） | 只用 P4-C9 自己的 Local Validation；0 上游 `__post_init__` / private / dunder / 实例校验方法 | 闭合 R-01 / R-02：无例外复杂度、无嵌套动态分派、完整覆盖 |
| 8 | `NormalizedMetadata` | 不调用 `__post_init__` / `meets_minimum_success()`；本地 minimum-success 只读 `number` / `title`（Validation-Only） | 前者会写对象、后者是实例方法分派 |
| 9 | summary / outcome / RetryKind | 原样携带 P4-C8 值（第 9.3 节批准 property，校验后读取） | 杜绝第二套业务语义 |
| 10 | 上游安全值对象（`PreflightBlocker`、`ExecutionFailure`、summary） | 原对象携带，本地校验 | 全字段安全；减少平行模型 |
| 11 | 图片失败 | `(role, kind)` 分组计数 | 输出上界只依赖枚举；保留诊断价值 |
| 12 | 冲突值 / `external_ids` key | 不输出（Validation-Only） | 来自网页的自由文本 |
| 13 | 不合规 source id | fail closed | 不改写 evidence；默认配置合规 |
| 14 | 结构上限数值 | 64 / 8 / 256 / 256 / 256 / 255 / 7 天 | 高于上游实际与默认值并留余量，同时使单条目大小有常量上界 |
| 15 | 既有架构守卫 | 第 27.3 节七处最小授权更新 | 与 P4-C8 第 34.3 节同类先例；不放宽其它断言 |
| 16 | 本地校验放在哪里（Design-R1） | 新增内部模块 `validation.py`（S2） | 第 9.5 节校验图规模大，与投影分离便于审计；不改变公开 API |
| 17 | `field_sources` 的 `MappingProxyType`（Design-R2 取代 Design-R1 的 unwrap 方案；其“不迭代 / 其它 key 不读取”部分已被 #26 取代） | 不 introspect 被包装对象；`type(...) is MappingProxyType` 后只按 `PROVENANCE_FIELD_ORDER` 固定字段名查询；不迭代、不 `len()`、不依赖插入顺序；其它 key 不读取；不透明实现伪造列为 9.0 节 C 层（不在 supported input graph） | 不存在可移植、标准公开、非反射的手段观察 proxy 的隐藏 referent；依赖 `gc.get_referents` 是 CPython 实现细节且是反射 / 审计原语（R1-01 / R1-02）；上游 `NormalizedMetadata` 公开构造合同已保证快照与不可变发布 |
| 18 | 上游未公开导出的不变量表（Design-R1） | 本地冻结表 T-1..T-4，测试断言与上游相等 | 不 import 私有名称，同时不发明新规则 |
| 19 | `OrganizePlan` 的包含关系（Design-R1） | 以 P4-C2 冻结的 `os.path.join` 结构性布局与操作顺序逐字符核对 | P4-C2 的 `is_contained_within` 不在公开导出中；结构性布局是 P4-C2 第 11 节本身给出的包含关系依据 |
| 20 | BASENAME 控制字符（Design-R1） | 显式码点黑名单（C0、DEL、C1、代理项、U+2028/2029、bidi 控制符、U+FEFF）+ 任何平台禁止 `/` 与 `\` | 确定、不依赖 Unicode 数据库版本；不误伤全角空格等常见日文文件名字符 |
| 21 | `__all__` 阶段化（Design-R1） | S1 / S2 / 最终三个精确集合，不允许 stub | 闭合 R-05 |
| 22 | `RETRY` 形态 `retry_scope` 非空要求（Design-R1） | 取消“非空”要求（Design-R2 不再改动：空 RETRY scope LEGAL；RETRY shape 由 `retry_scope is not None` 等 shape 证据决定，不使用真值判断） | 校验图审计发现 P4-C8 scope 校验不要求非空；原条款比上游更严，会误拒合法输入 |
| 23 | 运行时权威（Design-R2） | 保持项目既有 `Python >= 3.11`；“Windows 11 / Python 3.12.x”仅为验收证据环境；不改 `pyproject.toml` | 闭合 R1-02：不得自行把包的支持边界收窄为 CPython-only / 3.12 only |
| 24 | 输入信任三层（Design-R2） | 第 9.0 节：A supported public graph / B detectable structural tampering（fail closed）/ C opaque implementation forging（不在 supported input graph，不使用反射识别） | 闭合 R-02：准确收窄“零调用方钩子 / 篡改检测”声明到项目真正支持的 public model 边界，且不降低 A / B 的要求 |
| 25 | `RetryMaterial` 与 retained 预算（Design-R2） | M-30；`retry_kind` 先由已校验公开字段本地推导再与 property 比较；material 存在性 / 对象身份 / RESUME 与 FRESH 的 checkpoint 关系；`PREFLIGHT_RECHECK` / `DEFERRED` 不增加 P4-C8 没有的约束；retained 字节本地计算并校验预算 | 闭合 R-03：`retry_material_retained` 输出前必须与 `retry_kind` 一致；预算关系不得留给上游 `__post_init__` 或依赖未验证图的 property |
| 26 | `field_sources` 的访问顺序（Design-R3，取代 #17 中“不迭代 / 其它 key 不读取”） | **BOUNDED ONE-PASS KEY SCAN → EXACT KEY VALIDATION → FIXED KNOWN-KEY LOOKUP**：先单遍有界扫描并验证全部 stored key 为 exact `str`，之后才按 `PROVENANCE_FIELD_ORDER` 做固定 known-key 查询；iteration 仅为 validation，输出顺序仍由 `PROVENANCE_FIELD_ORDER` 决定；unknown exact-`str` key 被扫描、计数，但不投影；不使用 `gc` / 反射 / referent introspection；Layer C 保持窄边界 | 闭合 R2-01：上游 `NormalizedMetadata` 构造器以 `isinstance(key, str)` 接受 `str` 子类 key 并原样写入 exact `dict`（`str` 子类 key 经公开构造路径可达，A / B 层，不是 C 层）；Design-R2 在 key 未验证前就 `name in proxy`，会对其执行子类 `__eq__`；先扫描后查询使固定 exact-`str` 查询不存在 caller-controlled 分派 |
| 27 | `MAX_PROVENANCE_KEYS`（Design-R3） | `64`，内部常量（`models.py`，不进 `__all__`，不出现在输出）；超限 `DiagnosticsResourceLimitError`，观察到第 65 个 key 即停；known 与 unknown key 同等计数 | `>= 15`；覆盖真实 Phase 3 producer（至多 15 个 key）并留约 4 倍余量；每个 `AggregationResult` 最坏 65 个 `type()` 检查，不物化；与 `MAX_SOURCES_PER_ITEM = 64` 同量级；技术设计裁决，无需 Owner |
| 28 | Dispatch Safety Matrix / Horizontal Audit（Design-R3） | 新增第 9.0.1 节 validate-before-dispatch（V-1..V-4）、第 9.10 节 Dispatch Safety Matrix（D-01..D-31）、第 9.11 节 Horizontal Dispatch Audit（H-01..H-15）；批准 property 的依赖图（第 9.3.1 节）显式化；禁止 `sorted` / `min` / `max`（AST）；`validation.py` 禁止 `keys` / `values` / `items` / `get` / `copy` 方法调用（AST 代理） | 闭合 R-02 的根因（“caller-originated 对象在 exact-type 校验前进入分派”）而不是只修一个点；审计只发现 H-05（= R2-01）一处同类缺口，其余位置把隐含顺序写成规范性前置条件，语义不变 |
| 29 | 上游 authority 引用方式（Design-R3） | 以稳定 symbol / 函数 + frozen upstream SHA（`a662659…`）+ 上游合同节为 normative authority，源码行号仅为 review evidence；`test_diagnostics_upstream_characterization.py`（UC-1..UC-9）固定所引事实 | 行号会漂移；characterization 使上游行为变化触发合同修订而不是静默失配；不修改上游 |
