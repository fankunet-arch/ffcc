# FC2 Organizer -- Phase 4 / P4-C9 结构化诊断合同（Diagnostics Contract）

```text
文档状态                         ：DESIGN FREEZE CANDIDATE — IMPLEMENTATION NOT STARTED
P4-C9 Design                     ：IMPLEMENTED — INDEPENDENT DESIGN REVIEW REQUIRED
P4-C9 Frozen Contract            ：NOT YET ACCEPTED
P4-C9 Production Implementation  ：NOT STARTED
Package                          ：fc2_organizer.diagnostics（新顶层 package，S1 起创建）
Package Frozen Base              ：a662659dfd6e801531b14af7913d84a5f9f859e2（P4-C8 Final Closure Docs Head）
Governance Authority             ：docs/PROJECT_GOVERNANCE_ACCELERATION.md @ 3b9d39e9adbcc8a009707486eebbb8736a5b1c4d
                                   （Final Reviewed Governance Head / Project Governance Authority Head）
Planning Parent                  ：3b9d39e9adbcc8a009707486eebbb8736a5b1c4d
Branch                           ：claude/phase4-c9-diagnostics
Governance Mode                  ：ACCELERATED v2
Risk Class                       ：B（第 5 节；受第 5.3 节风险升级门约束）
施工计划                         ：docs/P4_C9_CONSTRUCTION_PLAN.md（S1 / S2 / S3，连续施工）
```

本合同一次性冻结 P4-C9 的全部规范语义。本文件经独立 DESIGN / CONTRACT / PLAN Review PASS 后成为 Frozen Contract；
S1-S3 只能**执行**本合同，不得重新设计。实施期间对本文件唯一允许的改动是第 32 节“实现状态”中的状态行；任何语义
改动（含公开 API、schema、脱敏、路径策略、资源上限、风险边界）都属于 authority docs 改动（治理文档第 11.2 节），
必须作为独立修订轮次提出并经独立复查，不得在实现 commit 中夹带。

坐标说明（冻结，治理文档第 19 节）：

* **Package Frozen Base** 是 P4-C9 的 package baseline，保持 `a662659dfd6e801531b14af7913d84a5f9f859e2`；
* **Governance Authority / Planning Parent** 是 `3b9d39e9adbcc8a009707486eebbb8736a5b1c4d`，是 P4-C9 工作分支的起点，
  **不是** P4-C9 Frozen Base；两者之间只有治理文档提交，没有任何 production / test 改动。

基线状态（本合同建立时）：

```text
P4-C1 .. P4-C8                   : CLOSED（本合同不修改其中任何一个的生产代码、合同、施工计划或 HANDOFF）
Acceleration Governance v2       : ACCEPTED / CLOSED
P4-C9                            : DESIGN FREEZE CANDIDATE；Implementation NOT STARTED
P4-C10                           : NOT STARTED
Phase 4                          : NOT CLOSED
```

---

## 1. 目的与用户能力（冻结）

P4-C9 交付一个完整的纵向能力 **Diagnostics**：

```text
既有 FC2 Organizer / Metadata / Batch / Orchestration 已经产生的、内存中的结构化运行结果
    （BatchPreview / BatchExecutionResult 及其公开可达的下层模型）
        -> 只读、确定性、可审计的投影（projection）
        -> 不可变诊断模型 BatchDiagnostics（batch / item / stage / source / field provenance / failure / retry）
        -> 安全脱敏（redaction）与路径策略
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
* 不可变诊断模型、诊断错误层次、常量。
* 来源级诊断、字段出处、条目诊断、批级诊断、脱敏、路径策略、确定性、资源与输出上界。
* 测试：unit、architecture、integration、500-item 诊断投影门槛、MAX 边界、非空洞性（mutation / canary）。
* 对既有架构守卫的最小授权更新（第 27.3 节，精确列举）。

## 4. 非目标（冻结）

* 不写文件：不自动落盘 JSON，不提供 `path` / `file` 参数，不创建目录，不做 archive。
* 不做 durable persistence：没有 SQLite、shelve、dbm、pickle、marshal、任务数据库、resume store、历史运行档案。
* 不做 live logging：不调用 `logging` / `print`，不注册 handler，不修改全局 logger，不向 P4-C8 执行路径插入钩子。
* 不访问网络，不重新获取 metadata / 图片，不重新运行 preview / execute / retry / preflight。
* 不重新实现 metadata aggregation、RetryKind 判定、summary 计数或 BatchOutcome 判定；全部原样携带 P4-C8 / Phase 3 的
  冻结结果。
* 不提供实时进度 / 事件流 / 回调。
* 不设计 P4-C10、Phase 5 Amane Adapter 或任何 UI。
* 不修改任何已 CLOSED package 的生产代码。

## 5. 治理（冻结）

### 5.1 Risk Class = B

依据：治理文档第 8.2 节明确把 diagnostics 列为 B 类（中风险）。只有在满足本合同冻结的安全边界——零持久化、零文件
写入、零网络、零副作用、只读消费公开模型、不改变任何 CLOSED package 语义、严格脱敏——时，P4-C9 才保持 B 类。

### 5.2 内部施工与 Review

* 内部 S1 / S2 / S3 连续施工（施工计划第 4 节），S1、S2、S3 均**不**单独 Review、**不**做中间 docs closure。
* 本合同 / 施工计划需要一次独立 DESIGN / AUTHORITY REVIEW（因为实现建立在新的 Frozen Contract 上，治理文档第 9 节
  第 2 条）。
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
* 设计阶段逐项审计了第 1 节问题表所需的全部 evidence：它们全部可经 `fc2_organizer.orchestration` 及其公开可达的
  下层公开模型读取（第 9 节输入权威表）。唯一的缺口是 P4-C8 的 `models.revalidate` 不是公开导出；本合同以“对精确
  公开类调用其自身 `__post_init__` 不变量检查”替代（第 24.3 节），**不需要**修改 P4-C8。
* 审计结论：**不存在 BLOCKED DESIGN ISSUE**；P4-C9 不授权、也不需要任何 CLOSED package 生产语义改动。
* 若实施中发现某项必要诊断必须修改 CLOSED package 生产语义才能交付：不得自行授权、不得夹带；必须在施工计划 / HANDOFF
  记录 `BLOCKED DESIGN ISSUE` 并 STOP（风险升级门第 K 项）。

---

## 6. 包边界与模块划分（冻结）

```text
src/fc2_organizer/diagnostics/
    __init__.py      公开 API 汇总（只从本 package 模块 re-export；__all__ 精确等于第 8.1 节）
    errors.py        错误层次（只 import __future__）
    models.py        常量、诊断枚举、不可变诊断模型及其 __post_init__ 校验
    projection.py    单条目投影：下层模型 -> 诊断模型（安全文本规则、路径策略、计时策略、结构上限）
    build.py         两个公开 builder：输入类型检查、条目数上限、P4-C8 / 下层不变量重检、逐条投影、批级组装
    render.py        render_diagnostics_json：诊断图重检 -> 纯 JSON 树 -> 有界流式编码 -> bytes
```

模块集合恰好为上述 6 个文件，没有子目录。S1 创建 `__init__.py`、`errors.py`、`models.py`；S2 创建 `projection.py`、
`build.py`；S3 创建 `render.py`（施工计划第 4 节）。

## 7. 依赖方向与 import 策略（冻结）

```text
fc2_organizer.diagnostics
    |-- fc2_organizer.orchestration     （裸公开 package：第 8.5 节列出的名称）
    |-- fc2_organizer.execution         （裸公开 package：模型与枚举类型）
    |-- fc2_organizer.images            （裸公开 package：ImageCandidateFailure、ImageRole、ImageFailureKind）
    |-- fc2_organizer.materialization   （裸公开 package：ArtifactKind）
    |-- fc2_organizer.discovery         （裸公开 package：DiscoveredMediaItem）
    |-- fc2_organizer.planning          （裸公开 package：OrganizePlan、PlannedPath）
    |-- fc2_metadata_core.batch         （裸公开 package：BatchResult、BatchItemResult、BatchItemStatus、BatchItemErrorKind）
    |-- fc2_metadata_core.aggregation   （裸公开 package：AggregationResult、AggregateStatus、SourceExecutionTrace、
    |                                     SourceAttempt、FieldConflict、OPERATIONAL_FAILURE_STATUSES、CONFLICT_FIELDS）
    |-- fc2_metadata_core.models        （裸公开 package：SourceResult、SourceStatus、SourceErrorKind、NormalizedMetadata）
    |-- fc2_metadata_core.normalize     （裸公开 package：is_valid_fc2_number）
    '-- 标准库（逐模块限定，见下）
```

* 只允许 `from <裸公开 package> import <该 package __all__ 中的公开名称>`；不允许 import 任何子模块（例如
  `fc2_organizer.orchestration.models`、`fc2_metadata_core.aggregation.policy`、`fc2_organizer.execution._fs`、
  `fc2_organizer.images.acquisition`、`fc2_organizer.materialization.mapping`），不允许 import 以 `_` 开头的名称，
  不允许把 package 模块对象本身 import 进来再做属性访问。
* 逐模块标准库允许清单（AST 强制）：

| 模块 | 允许的标准库 |
|---|---|
| `errors.py` | `__future__` |
| `models.py` | `__future__`、`dataclasses`、`enum`、`re` |
| `projection.py` | `__future__`、`math`、`os`（只允许 `os.path.basename`、`os.sep`、`os.altsep`）、`re`、`types`（只允许 `types.MappingProxyType`） |
| `build.py` | `__future__` |
| `render.py` | `__future__`、`json`（只允许 `json.JSONEncoder`） |
| `__init__.py` | 无（只 import 本 package 模块） |

* **生产代码禁止 import / 引用**（静态 AST + 运行时）：`amane`、`httpx`、`requests`、`socket`、`ssl`、`urllib`、`http`、
  `pickle`、`marshal`、`shelve`、`dbm`、`sqlite3`、`csv`、`logging`、`tempfile`、`shutil`、`glob`、`fnmatch`、`pathlib`、`io`、
  `subprocess`、`multiprocessing`、`concurrent`、`threading`、`asyncio`、`ctypes`、`time`、`datetime`、`random`、`secrets`、
  `uuid`、`hashlib`、`hmac`、`traceback`、`inspect`、`gc`、`sys`、`builtins`；任何 source adapter（`fc2_metadata_core.sources`）、
  `fc2_metadata_core.http`、`fc2_metadata_core.resource_control`；`json` 只在 `render.py`。
* 禁止的调用（AST 强制）：`open`、`print`、`exec`、`eval`、`compile`、`__import__`、`getattr`、`setattr`、`delattr`、
  `vars`、`id`、`hash`、`repr`、`format`；`object.__setattr__` 只允许在 `models.py` 内用于诊断模型自身（若实现需要）；
  对精确上游模型的字段读取一律使用普通属性访问；禁止对异常或任何非 `str` 输入值调用 `str()`，禁止在 f-string / `%` /
  `str.format` 中插入任何输入值；`os` 除允许的三项之外的任何属性。
* 没有反向依赖：`src` 下任何其它模块都不 import `fc2_organizer.diagnostics`；`fc2_organizer/__init__.py` 不 import 它；
  裸 `import fc2_organizer` 不加载它。
* 传递加载说明（已冻结的上游事实，不是 P4-C9 的直接依赖）：import `fc2_organizer.orchestration` 会经由 P4-C8 传递加载
  `fc2_organizer.images.acquisition`，进而加载 `httpx`（P4-C8 合同第 6 节）。P4-C9 源码从不**引用** `httpx` 或任何网络
  客户端，从不构造 client；架构测试以静态扫描证明这一点，并以运行时 fake 证明诊断过程中没有任何网络 / 文件系统调用
  （第 26 节）。

---

## 8. 公开 API（冻结）

### 8.1 `fc2_organizer.diagnostics.__all__`（精确集合与顺序）

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

Design Review PASS 后不得增加、删除、重命名或重排任何公开名称；任何变化都是合同修订。

### 8.2 函数签名（冻结）

```python
def build_preview_diagnostics(
    preview: BatchPreview,
    /,
    *,
    path_policy: PathPolicy = PathPolicy.BASENAME,
    timing_policy: TimingPolicy = TimingPolicy.OMIT,
) -> BatchDiagnostics: ...

def build_execution_diagnostics(
    result: BatchExecutionResult,
    /,
    *,
    path_policy: PathPolicy = PathPolicy.BASENAME,
    timing_policy: TimingPolicy = TimingPolicy.OMIT,
) -> BatchDiagnostics: ...

def render_diagnostics_json(diagnostics: BatchDiagnostics, /) -> bytes: ...
```

* 三个函数都是同步、纯函数式（对其输入只读）；不接受 callback、文件、路径、流或 logger 参数。
* builder 的第一个参数是 positional-only；策略参数是 keyword-only。
* `render_diagnostics_json` 返回值类型冻结为 **`bytes`**：ASCII-only（因而也是合法 UTF-8），不带 BOM、不带末尾换行。
  调用者以后是否保存这些 bytes 不属于 P4-C9。

### 8.3 常量（冻结）

| 常量 | 值 | 说明 |
|---|---|---|
| `DIAGNOSTICS_SCHEMA` | `"fc2_organizer.diagnostics"` | schema 名称 |
| `DIAGNOSTICS_SCHEMA_VERSION` | `"1.0"` | schema 版本（第 23 节） |
| `PROVENANCE_FIELD_ORDER` | `("number", "title", "studio", "publisher", "release", "runtime", "plot", "actors", "tags", "poster_urls", "thumb_urls", "fanart_urls", "extrafanart", "source_urls", "external_ids")` | 与 Phase 3 聚合合同第 5.6 节的固定 key 顺序逐项相同（测试断言与 `fc2_metadata_core.aggregation.policy.FIELD_ORDER` 相等；生产代码不 import 该子模块） |
| `MAX_DIAGNOSTIC_ITEMS` | `MAX_BATCH_ITEMS`（`2000`，由 `fc2_organizer.orchestration` 公开导入，不另写数值） | 单个诊断的条目上限 |
| `MAX_SOURCES_PER_ITEM` | `64` | 每条目 `source_results` 与 `disabled_source_ids` 各自的上限 |
| `MAX_ATTEMPTS_PER_SOURCE` | `8` | 每个 source trace 的 attempt 上限（Phase 3 `MAX_ATTEMPTS_LIMIT = 5`，留有余量） |
| `MAX_BLOCKERS_PER_ITEM` | `256` | 每条目 preflight blocker 上限 |
| `MAX_CONFLICTS_PER_ITEM` | `256` | 每条目 `FieldConflict` 上限 |
| `MAX_LEFTOVER_TEMPORARIES_PER_ITEM` | `256` | 每条目残留临时文件上限 |
| `MAX_PATH_TEXT_CHARS` | `255` | 每个路径派生文本（basename）的字符上限 |
| `MAX_TIMING_MS` | `604800000`（7 天） | 计时值上限（毫秒） |
| `MAX_DIAGNOSTIC_OUTPUT_BYTES` | `67108864`（64 MiB） | 单次序列化输出的硬上限 |

### 8.4 错误层次（`errors.py`，冻结）

```python
class DiagnosticsError(Exception): ...                                   # 基类
class DiagnosticsInputError(DiagnosticsError, TypeError): ...            # 参数不是精确的公开输入类型 / 策略枚举
class DiagnosticsIntegrityError(DiagnosticsError, ValueError): ...       # 输入对象图被篡改或内部不一致；诊断图被篡改
class DiagnosticsContractError(DiagnosticsError, ValueError): ...        # 诊断模型构造时违反自身不变量
class DiagnosticsResourceLimitError(DiagnosticsError, RuntimeError): ... # 条目数 / 结构上限 / 输出字节上限
class DiagnosticsUnsafeValueError(DiagnosticsError, ValueError): ...     # 某个将被输出的值不满足安全文本 / 数值规则
class DiagnosticsSerializationError(DiagnosticsError, RuntimeError): ... # JSON 编码阶段的其它失败
```

规则（与 P4-C8 合同第 7.4 节同一原则）：

* message 只由固定措辞组成，可以带常量名与条目 index；**绝不**包含路径、标题、URL、source 文本、secret 或任何下层异常的
  文本。
* 所有诊断错误都在任何 `except` 块之外抛出，`__cause__` / `__context__` 均为 `None`（不链接下层异常）。
* 诊断错误只表示“调用方错误、输入被篡改或资源超限”；它们**不**改变原 batch result、retry eligibility 或任何文件（第 24 节）。

### 8.5 允许 import 的上游公开名称（冻结，AST 强制）

| 裸 package | 允许名称 |
|---|---|
| `fc2_organizer.orchestration` | `BatchPreview`、`BatchExecutionResult`、`ItemPreview`、`ItemExecution`、`ItemIssue`、`PreviewSummary`、`ExecutionSummary`、`PreviewState`、`ExecutionDisposition`、`OrchestrationStage`、`IssueReason`、`ItemWarning`、`RetryKind`、`BatchOutcome`、`RetryMaterial`、`MAX_BATCH_ITEMS` |
| `fc2_organizer.execution` | `ExecutionPreflight`、`ExecutionResult`、`ExecutionStatus`、`ExecutionStep`、`ExecutionFailure`、`ExecutionFailureKind`、`TransferStage`、`TransferMode`、`PreflightMode`、`PreflightBlocker`、`PreflightBlockReason`、`PathRole`、`EffectKind`、`CompletedEffect`、`LeftoverTemporary`、`ExecutionUnit`、`ExecutionCheckpoint`、`PlanGraphRejectionReason`、`ManifestRejectionReason`、`CheckpointRejectionReason`、`PreflightIntegrityReason` |
| `fc2_organizer.images` | `ImageCandidateFailure`、`ImageRole`、`ImageFailureKind` |
| `fc2_organizer.materialization` | `ArtifactKind`、`ArtifactWriteRequest`、`MappingRejectionReason` |
| `fc2_organizer.discovery` | `DiscoveredMediaItem` |
| `fc2_organizer.planning` | `OrganizePlan`、`PlannedPath` |
| `fc2_metadata_core.batch` | `BatchResult`、`BatchItemResult`、`BatchItemStatus`、`BatchItemErrorKind` |
| `fc2_metadata_core.aggregation` | `AggregationResult`、`AggregateStatus`、`SourceExecutionTrace`、`SourceAttempt`、`FieldConflict`、`OPERATIONAL_FAILURE_STATUSES`、`CONFLICT_FIELDS` |
| `fc2_metadata_core.models` | `SourceResult`、`SourceStatus`、`SourceErrorKind`、`NormalizedMetadata` |
| `fc2_metadata_core.normalize` | `is_valid_fc2_number` |

明确**不**允许：`BatchOrchestrator`、`merge_retry`、`OrchestrationConfig`、`CancellationToken`、`preflight_execution`、
`execute_filesystem`、任何 `build_*` / `render_*` / `acquire_*` / `materialize_*` 函数、任何 adapter / client / registry。

---

## 9. 输入权威（冻结）

### 9.1 可消费的顶层输入

只接受两种**精确类型**（`type(x) is ...`，子类一律拒绝）的顶层输入：`BatchPreview`（`build_preview_diagnostics`）与
`BatchExecutionResult`（`build_execution_diagnostics`）。诊断只读取经由它们公开字段 / 公开 property 合法可达的公开模型。

### 9.2 读取字段表（冻结；表外的字段一律不读取）

| 公开模型 | 允许读取的字段 / property |
|---|---|
| `BatchPreview` | `generation`、`base_result_id`（只判断是否为 `None`）、`retry_scope`、`batch_size`、`items`、`metadata_batch`、`summary` |
| `BatchExecutionResult` | `generation`、`base_result_id`（只判断是否为 `None`）、`retry_scope`、`batch_size`、`items`、`metadata_batch`、`is_complete`、`summary`、`outcome` |
| `ItemPreview` | `index`、`generation`、`media_item`、`canonical_number`、`metadata`、`plan`、`image_failures`、`preflight`、`state`、`issue`、`conflict_with`、`retry_origin`、`warnings` |
| `ItemExecution` | `index`、`generation`、`media_item`、`canonical_number`、`metadata`、`plan`、`image_failures`、`conflict_with`、`preview_state`、`issue`、`warnings`、`disposition`、`execution`、`retry_material`（只判断是否为 `None`）、`retry_kind` |
| `ItemIssue` | `stage`、`reason`、`error_type`、`detail` |
| `PreviewSummary` / `ExecutionSummary` | 原对象整体携带（第 11.1 节） |
| `DiscoveredMediaItem` | `source_path`（只用于路径策略，第 18 节）、`size` |
| `OrganizePlan` | `target_directory`、`target_media_path`（只用于路径策略） |
| `PlannedPath` | `absolute_path`（只用于路径策略） |
| `BatchResult` | `generation`、`total`、`success_count`、`partial_count`、`failed_count` |
| `BatchItemResult` | `status`、`aggregation_result`、`error_kind`、`generation`、`elapsed_ms`（仅 `TimingPolicy.INCLUDE`） |
| `AggregationResult` | `status`、`metadata`（只读 `field_sources`）、`source_results`、`contributing_source_ids`、`conflicts`、`disabled_source_ids`、`source_execution_traces` |
| `SourceResult` | `source_id`、`status`、`error_kind` |
| `SourceExecutionTrace` | `source_id`、`attempts`、`max_attempts`、`deadline_exceeded`、`deadline_during` |
| `SourceAttempt` | `sequence`、`status`、`error_kind`、`completed`、`elapsed_ms` / `backoff_before_seconds`（仅 `TimingPolicy.INCLUDE`） |
| `NormalizedMetadata` | **只**读 `field_sources` |
| `FieldConflict` | `field`、`selected_source_id`、`alternatives` 中每对的 **source id**（第 0 项） |
| `ImageCandidateFailure` | `role`、`kind`、`http_status` |
| `ExecutionPreflight` | `mode`、`ready`、`blockers`、`transfer_mode`、`pending_units`、`completed_units`（只取长度）、`skipped_steps`、`artifacts`（只读每项 `kind`） |
| `ArtifactWriteRequest` | **只**读 `kind` |
| `PreflightBlocker` | 原对象整体携带（全部字段为枚举 / `int` / `None`） |
| `ExecutionResult` | `status`、`mode`、`transfer_mode`、`completed_effects`、`new_effect_count`、`failure`、`checkpoint`（只判断是否为 `None`）、`leftover_temporaries`、`skipped_steps` |
| `CompletedEffect` | **只**读 `kind`、`artifact_kind` |
| `ExecutionFailure` | 原对象整体携带（全部字段为枚举 / `int` / `bool` / 冻结字面量 / `None`） |
| `LeftoverTemporary` | `directory_role`、`name`（`name` 受路径策略约束，第 18 节） |

### 9.3 禁止读取（冻结）

* 任何以 `_` 开头的属性或方法（例如 P4-C8 `BatchExecutionResult._shape`、`ItemPreview._manifest_kinds`）、模块级私有
  registry（例如 P4-C8 `_consumption`）、线程或 asyncio 状态。
* 自由文本或载荷字段：`SourceResult.error_detail`、`SourceResult.metadata`、`SourceResult.elapsed_ms`（adapter 自报，
  P2-R-07）、`NormalizedMetadata` 中除 `field_sources` 外的全部字段（标题、简介、演员、标签、所有 URL、`external_ids`）、
  `FieldConflict.selected_value` / alternatives 的值 / `key`、`ArtifactWriteRequest.content`、`DiscoveredMediaItem.relative_path`、
  `OrganizePlan.library_root` 与其它路径、`BatchPreview.library_root` / `output_policy` / `image_policy`、
  `CompletedEffect.path` / `identity` / `size` / `sha256`、`ExecutionResult.media_sha256`、`RetryMaterial` 的内容。
* 临时身份（第 14 节）：`preview_id`、`result_id`、`base_result_id` 的值、`BatchLineage.token`、`preflight_id`、
  `checkpoint_id`、`seal`、`plan_fingerprint`、`manifest_fingerprint`、`EntryIdentity`（device / inode / mtime_ns）。
* `BatchItemResult.error_type`（自由长度 `str`；同一信息已由 P4-C8 `ItemIssue.error_type` 以受校验的标识符形式提供）。

---

## 10. 诊断种类与形态（判别模型，冻结）

`BatchDiagnostics` 是**一个带显式判别字段的统一模型**：

* `kind: DiagnosticsKind` —— `PREVIEW`（由 `build_preview_diagnostics` 产生）或 `EXECUTION`（由
  `build_execution_diagnostics` 产生）。消费者**只能**依据 `kind` 判断阶段，不得依据字段是否为 `None` 猜测。
* `shape: ResultShape` —— 由公开字段确定：

| 输入 | `shape` 判定（只用公开字段） |
|---|---|
| `BatchPreview` | `base_result_id is None` -> `MAIN`；否则 `RETRY` |
| `BatchExecutionResult` | `generation == 0` -> `MAIN`；`generation >= 1 且 is_complete` -> `MERGED`；否则 `RETRY` |

  上表与 P4-C8 合同第 10.4 / 10.7 节的形态定义逐项一致（P4-C8 已在构造时保证三种形态互斥）；测试以 P4-C8 产生的三种
  形态逐一交叉验证。`PREVIEW` 永远不是 `MERGED`。

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

全部模型为 `@dataclass(frozen=True, slots=True)`；`__post_init__` 以精确类型（`type(x) is T`，`bool` 不算 `int`）校验
每个字段，任一违反抛 `DiagnosticsContractError`（固定措辞）。模型不提供 `to_dict` / `to_json` / `dump` / `save` 之类的方法，
不定义 `__getattr__`、property 钩子或自定义 `__eq__` / `__hash__`。tuple 字段只接受精确 `tuple`。下文“枚举”均指上游或本
package 的精确枚举成员。

新增的诊断枚举：

```python
class DiagnosticsKind(Enum):  PREVIEW = "preview";  EXECUTION = "execution"
class ResultShape(Enum):      MAIN = "main";        RETRY = "retry";      MERGED = "merged"
class PathPolicy(Enum):       BASENAME = "basename"; NONE = "none"
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
| `retry_scope` | `tuple[RetryKind, ...] \| None` | `RETRY` 时非 `None`：非空、元素唯一、按 `RetryKind` 声明顺序、不含 `NONE`；`MAIN` / `MERGED` 时为 `None` |
| `path_policy` | `PathPolicy` | — |
| `timing_policy` | `TimingPolicy` | — |
| `metadata_batch` | `MetadataBatchCounts` | — |
| `preview_summary` | `PreviewSummary \| None` | 精确 P4-C8 类型；适用性见第 10 节 |
| `execution_summary` | `ExecutionSummary \| None` | 精确 P4-C8 类型；适用性见第 10 节 |
| `outcome` | `BatchOutcome \| None` | 适用性见第 10 节 |
| `items` | `tuple[ItemDiagnostics, ...]` | 长度 `<= batch_size`；`index` 严格递增且 `< batch_size`；`MAIN` / `MERGED` 时 `index` 恰为 `0..batch_size-1`；summary 的 `total == len(items)`；每个条目的 kind 相关字段满足第 10 节适用表；`PREVIEW` 时每条 `generation == generation`；`EXECUTION` 且非 `MERGED` 时每条 `generation == generation`，`MERGED` 时每条 `generation <= generation` |

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
* `stage` / `error_type` 必需性 / `detail` 类型与 P4-C8 合同第 10.2 节 `ItemIssue` 表一致（投影时原样复制，故恒成立；
  诊断模型不重复实现该表，只校验类型与上述集合）。

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
| `blockers` | `tuple[PreflightBlocker, ...]` | 原 P4-C7 对象、原顺序；`<= MAX_BLOCKERS_PER_ITEM` |
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
| `failure` | `ExecutionFailure \| None` | 原 P4-C7 对象；`status is SUCCESS` 当且仅当为 `None` |
| `checkpoint_present` | `bool` | `status is PARTIAL` 当且仅当为真 |
| `skipped_steps` | `tuple[ExecutionStep, ...]` | 原顺序 |
| `leftover_temporary_count` | `int >= 0` | `len(leftover_temporaries)`（输入），`<= MAX_LEFTOVER_TEMPORARIES_PER_ITEM` |
| `leftover_temporaries` | `tuple[LeftoverTemporaryDiagnostics, ...]` | 原顺序；长度恒等于 `leftover_temporary_count` |

### 11.13 `LeftoverTemporaryDiagnostics`

`directory_role: PathRole`（只能是 `TARGET_DIRECTORY` 或 `EXTRAFANART_DIRECTORY`）、`name: str | None`（`BASENAME` 时为
满足 `\.fc2tmp-[0-9a-f]{32}\.part` 的精确 `str`；`NONE` 时为 `None`）。

---

## 12. 映射规则（冻结）

### 12.1 条目

| 诊断字段 | 来源 |
|---|---|
| `index`、`generation`、`canonical_number`、`conflict_with` | 输入条目同名字段（原样） |
| `preview_state` | `ItemPreview.state` / `ItemExecution.preview_state` |
| `issue` | `ItemIssue` 四个字段原样复制；`None` -> `None` |
| `warnings` | `ItemPreview.warnings`（P4-C8 派生 property）/ `ItemExecution.warnings`（字段），原样 |
| `retry_origin` | `ItemPreview.retry_origin` |
| `disposition`、`retry_kind` | `ItemExecution.disposition`、`ItemExecution.retry_kind`（P4-C8 第 25.1 节派生 property，原样；诊断不重新判定） |
| `retry_material_retained` | `ItemExecution.retry_material is not None` |
| `source_size` | `media_item.size` |
| `source_name`、`target_directory_name`、`target_media_name` | 第 18 节 |

条目的“编排阶段”即 `issue.stage`；没有 issue 的条目没有失败阶段，诊断**不**推断“最远到达阶段”（没有公开 evidence）。

### 12.2 metadata 与 source

* `BatchItemResult` -> `MetadataDiagnostics`：`status`、`generation`、`error_kind` 原样；有 `AggregationResult` 时
  `aggregate_status = aggregation_result.status`。
* `sources`：对 `aggregation_result.source_results` 按原顺序逐个投影；`trace` 取 `source_execution_traces` 中同位置项
  （Phase 3 已保证一一对应、同顺序；`traces_available` 为假时所有 trace 字段为 `None` / 空）。
* `contributed`、`operational_failure`、`provided_fields` 按第 11.6 节定义。
* attempt：`SourceAttempt` 的 `sequence`、`status`、`error_kind`、`completed` 原样；计时见第 12.7 节。
* 诊断**不**读取、**不**输出 `SourceResult.error_detail` 与 adapter 自报的 `SourceResult.elapsed_ms`。

### 12.3 字段出处（Field Provenance，P0）

* 唯一 evidence：`AggregationResult.metadata.field_sources`（Phase 3 聚合合同第 5.6 节：由 merge 从零重新计算，adapter 无法
  伪造；scalar 字段被选中的 source 排第一，集合 / `external_ids` 按优先级列出全部提供者，`number` 列出全部贡献者）。
* 投影：按 `PROVENANCE_FIELD_ORDER` 逐个字段查询 `field_sources`（`key in mapping` / `mapping[key]`，**从不**按 mapping 的
  迭代 / 插入顺序遍历）；存在的字段产生一个 `FieldProvenance(field, source_ids)`，`source_ids` 保持 Phase 3 给出的优先级
  顺序。
* 完整性（fail closed，`DiagnosticsIntegrityError`）：`field_sources` 必须是精确 `types.MappingProxyType`；其条目数必须等于
  在 `PROVENANCE_FIELD_ORDER` 中找到的字段数（即不存在表外 key）；每个值是精确 `tuple` 的精确 `str`；每个 source id 必须在
  `contributing_source_ids` 中。
* `metadata is None`（`AggregateStatus.FAILED`）时 `field_provenance == ()`。
* P4-C9 **不**重新执行任何 metadata aggregation，不比较字段值，不验证“值是否由该 source 提供”（Phase 3 合同第 3 节已声明
  该项只由 merge 保证）。

### 12.4 字段冲突

`AggregationResult.conflicts` 按原顺序（Phase 3 已按字段顺序与 key 排序）逐个投影为
`FieldConflictDiagnostics(field, selected_source_id, alternative_source_ids)`，只取 source id；值与 `external_ids` 的 key
一律丢弃。

### 12.5 图片失败

`image_failures` 按 `(role, kind)` 分组计数：分组顺序为 `ImageRole` 声明顺序，再按 `ImageFailureKind` 声明顺序；只输出
`count >= 1` 的分组；`HTTP_STATUS` 分组附带去重升序的 `http_status` 列表。`candidate_index` 不输出（分组后不再需要；也使输出
上界只依赖枚举大小与 HTTP 状态码范围）。

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
  `BatchItemResult.elapsed_ms` -> `MetadataDiagnostics.elapsed_ms`。转换一律为 `int(value)`（向零截断）；值必须有限且
  `0 <= v <= MAX_TIMING_MS`，否则 `DiagnosticsUnsafeValueError`。`AggregationResult.elapsed_ms` 与 adapter 自报的
  `SourceResult.elapsed_ms` 不发布。
* 计时值是输入 evidence：诊断对相同输入仍确定；但两次真实运行的计时不同，因此需要跨运行比较的消费者应使用默认 `OMIT`。

### 12.8 批级

* `kind`、`shape`、`generation`、`batch_size` 见第 10 / 11.1 节；`retry_scope` 为输入 frozenset 按 `RetryKind` 声明顺序转成
  tuple（**从不**迭代 frozenset 产生输出顺序；以声明顺序逐个判断成员资格）。
* `metadata_batch`：`BatchResult.generation / total / success_count / partial_count / failed_count`。
* `preview_summary` = `BatchPreview.summary`；`execution_summary` = `BatchExecutionResult.summary`；`outcome` =
  `BatchExecutionResult.outcome`：均为 P4-C8 冻结派生值，原对象 / 原成员携带。诊断**不**另行计算 ready / retryable /
  deferred / non-retryable / stage_counts，从而不可能产生与 P4-C8 summary 矛盾的第二套语义。

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
| 路径文本 | `PathPolicy.NONE` 时为 `None`；`plan` 不存在时目标名为 `None` |
| HTTP response body、header、完整 traceback、异常 message、source URL、单个 source 的 adapter 自报耗时、wall-clock 时间戳 | 公开模型中不存在或被禁止读取：schema 中**没有**对应字段 |

---

## 14. 临时身份与非确定值审计（冻结）

| 值 | 所在模型 | 诊断中的处理 |
|---|---|---|
| `preview_id` | `BatchPreview`、`BatchExecutionResult` | 不读取、不输出 |
| `result_id`、`base_result_id` | `BatchExecutionResult`、`BatchPreview` | 只读取 `base_result_id is None` 用于 `shape`；值不输出 |
| `BatchLineage.token` | `lineage`、`metadata_batch.lineage` | 不读取、不输出（它也是 P4-C8 合并授权的进程内能力令牌） |
| `preflight_id` | `ExecutionPreflight`、`ExecutionResult` | 不读取、不输出 |
| `checkpoint_id`、`seal`、`plan_fingerprint`、`manifest_fingerprint` | `ExecutionCheckpoint`、`ExecutionPreflight` | 不读取、不输出；只输出 `checkpoint_present` |
| `EntryIdentity`（device / inode / mtime_ns） | preflight / checkpoint / effect | 不读取、不输出 |
| `CompletedEffect.sha256`、`ExecutionResult.media_sha256` | execution | 不读取、不输出 |
| 计时 | `SourceAttempt`、`BatchItemResult` | 只在 `INCLUDE` 时输出（第 12.7 节） |
| `LeftoverTemporary.name`（含随机 32 hex） | execution | 只在 `BASENAME` 时输出：这是用户清理残留文件所需的真实 evidence；它是输入的确定函数，不破坏“相同输入 -> 相同输出” |

诊断自身不生成任何 id、时间戳、随机数、`id()` / 内存地址或 hash 值。

## 15. 确定性（冻结）

* 对同一组输入模型与同一组策略：`build_*` 产生相等（`==`）的 `BatchDiagnostics`；`render_diagnostics_json` 产生逐字节相同的
  bytes。
* 对**语义相同**的输入——仅在上表临时身份、`field_sources` mapping 插入顺序、对象构造顺序、asyncio / 线程完成顺序上不同——
  在 `TimingPolicy.OMIT` 下产生相等的模型与逐字节相同的输出。
* 禁止：`datetime` / `time`、随机数、uuid、`id()`、`hash()`、内存地址、对 `set` / `frozenset` / `dict` / mapping 的迭代顺序
  决定输出顺序。
* JSON 编码固定参数（第 22 节），浮点数永不出现在输出中（计时已转换为 `int`）。

## 16. 排序（冻结）

| 集合 | 顺序 |
|---|---|
| `items` | `index` 升序（即输入 tuple 顺序；P4-C8 已保证严格递增） |
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
| `stage_counts` | P4-C8 summary 已按 `OrchestrationStage` 声明顺序给出 |
| JSON object key | 字典序（`sort_keys=True`）；所有有序集合都用 JSON array 表达 |

---

## 17. 脱敏（Redaction）与安全文本规则（冻结）

### 17.1 绝不出现在诊断模型或输出中的内容

credentials、`Authorization`、`Cookie`、session token、secret header、任何 HTTP header / body、URL（含 query）、原始异常
对象、异常 repr / message / args、traceback、网页文本 / HTML、metadata 字段值（标题、简介、演员、标签、`external_ids`）、
冲突值、`BatchLineage.token` 与第 14 节全部临时身份、absolute path、library root、目录名（除第 18 节允许的 basename 外）、
任何字节载荷。

实现方式是**白名单投影**：诊断模型只有第 11 节列出的字段，每个字段的来源在第 12 节冻结；第 9.3 节的字段从不被读取，因此
不存在“先读取再过滤”的路径。

### 17.2 允许输出的 `str` 值（穷举）

| 类别 | 规则（不满足即 `DiagnosticsUnsafeValueError`） |
|---|---|
| 枚举值 | 只经由冻结枚举成员的 `.value` 输出（由 `render.py` 统一转换） |
| schema 常量 | `DIAGNOSTICS_SCHEMA`、`DIAGNOSTICS_SCHEMA_VERSION` |
| 安全 id（source id） | 精确 `str`，完全匹配 `[A-Za-z0-9][A-Za-z0-9_.\-]{0,63}` |
| `error_type` | 精确 `str`，`isidentifier()` 为真，长度 `1..128` |
| detail 类型名 | 来自第 11.4 节冻结集合的类名，由 `render.py` 的冻结表给出（不调用 `type(x).__name__`） |
| 字段名 | `PROVENANCE_FIELD_ORDER` / `CONFLICT_FIELDS` 的成员 |
| `canonical_number` | `is_valid_fc2_number` 为真 |
| `deadline_during` | `"attempt"` 或 `"backoff"` |
| 路径派生文本 | 第 18 节 |
| 残留临时文件名 | 完全匹配 `\.fc2tmp-[0-9a-f]{32}\.part` |

规则说明：source id 来自运营配置（Phase 3 `SourceConfig`），通常是 `fc2db_net` 之类的短标识；不满足安全 id 规则的配置在诊断
中 fail closed（已知局限，第 31 节），而不是被截断或改写。

### 17.3 编码规则

输出为 JSON，`ensure_ascii=True`：所有非 ASCII 字符（含 Windows / POSIX 文件名中的代理项）以 `\uXXXX` 转义；控制字符按 JSON
规则转义。因此输出 bytes 恒为 ASCII，不存在编码失败或终端注入的原始控制字符。

## 18. 路径策略（`PathPolicy`，冻结）

| 策略 | `source_name` | `target_directory_name` / `target_media_name` | 残留临时文件 `name` | library root / 目录 / absolute path |
|---|---|---|---|---|
| `BASENAME`（默认） | `os.path.basename(media_item.source_path)` | `os.path.basename(plan.target_directory.absolute_path)` / `os.path.basename(plan.target_media_path.absolute_path)` | 原文件名（固定格式） | **从不**输出 |
| `NONE` | `None` | `None` | `None` | **从不**输出 |

* basename 必须：非空；长度 `<= MAX_PATH_TEXT_CHARS`；不含 `os.sep`、`os.altsep`（若存在）、`"\x00"`；否则
  `DiagnosticsUnsafeValueError`（不截断、不替换）。
* 不提供 absolute path 或 relative path 选项。裁决理由：(1) diagnostics 的输出被设计为可以交给他人或附在 issue 中，目录层级
  可能含用户名、私人目录名；(2) 需要完整路径的 UI 与诊断处于同一进程，可以用稳定 `index` 回到同一个 `BatchPreview` /
  `BatchExecutionResult` 读取 P4-C8 的公开路径 property；(3) basename 已足够定位媒体与目标目录。若将来需要 absolute path
  opt-in，属于合同修订（并且是安全边界变化，触发第 5.3 节第 J 项评估）。
* 文件名是用户自己的媒体名称；诊断无法、也不尝试识别文件名中可能含有的敏感词。需要完全不含文件名的输出时使用 `NONE`。
* `source_size` 与 `artifact_counts` 等数值不受路径策略影响。
* `os.path.basename` 使用运行平台的路径语义，与 P4-C8 番号识别（P4-C8 合同第 30.2 节）一致；输入路径由同平台产生。

## 19. 异常安全（冻结）

* 诊断从不调用 `str(exception)`、`repr(exception)`、`format(exception)`、`exception.args`、`traceback.*`、`sys.exc_info`；
  不在 f-string / `%` / `format` 中插入任何输入值。
* 诊断从不执行调用方控制的钩子：所有对象先以 `type(x) is T` 精确确认属于第 8.5 节的上游公开类，然后才读取第 9.2 节的字段；
  上游类是 CLOSED package 的 `@dataclass(frozen=True, slots=True)`，字段读取不执行任何调用方代码。唯一调用的上游方法是这些精确
  类自身的 `__post_init__` 不变量检查（第 24.3 节）与第 9.2 节列出的 P4-C8 / Phase 3 公开派生 property。
* 失败原因只来自既有 frozen evidence：`ItemIssue.error_type`（类名）、`detail`（冻结枚举）、`ExecutionFailure`、
  `PreflightBlocker`、`SourceErrorKind`、`BatchItemErrorKind`。
* 诊断自身的错误遵守第 8.4 节规则（固定措辞、不链接）。

## 20. 载荷边界（冻结）

诊断从不复制或引用：video bytes、image bytes、NFO bytes、任何 `ArtifactWriteRequest.content`、HTTP body。只记录枚举、计数、
安全标量（`int` / `bool`）与第 17.2 节允许的文本。诊断模型不持有任何上游对象的引用，**除了**以下三种全字段安全、不可变的
上游值对象：`PreviewSummary` / `ExecutionSummary`（计数与枚举）、`PreflightBlocker`（枚举 / `int`）、`ExecutionFailure`
（枚举 / `int` / `bool` / 冻结字面量）。它们都不持有 bytes、路径或自由文本。

## 21. 资源边界与输出上界（冻结）

### 21.1 时间与内存

* builder：时间 `O(E)`，`E` 为诊断条目总数（条目 + source + attempt + provenance 项 + conflict + blocker + 图片失败 + effect +
  残留文件）；每个输入对象只访问常数次。
* renderer：时间 `O(E)`；内存有界于诊断模型大小与 `MAX_DIAGNOSTIC_OUTPUT_BYTES`。
* 没有无界历史、没有全局 registry、没有跨调用缓存；模块级状态只包含不可变常量（`tuple`、`frozenset`、`str`、`int`、枚举类、
  已编译的 `re.Pattern`）。

### 21.2 结构上限（fail closed，`DiagnosticsResourceLimitError`）

| 检查 | 时点 |
|---|---|
| `len(items) > MAX_DIAGNOSTIC_ITEMS`（继承 `MAX_BATCH_ITEMS`） | 在任何逐条工作与 P4-C8 不变量重检**之前**（`items` 先确认为精确 `tuple`） |
| `len(source_results) > MAX_SOURCES_PER_ITEM`、`len(disabled_source_ids) > MAX_SOURCES_PER_ITEM` | 投影该条目 metadata 前 |
| `len(trace.attempts) > MAX_ATTEMPTS_PER_SOURCE` | 投影该 source 前 |
| `len(conflicts) > MAX_CONFLICTS_PER_ITEM` | 投影 conflicts 前 |
| `len(blockers) > MAX_BLOCKERS_PER_ITEM` | 投影 preflight 前 |
| `len(leftover_temporaries) > MAX_LEFTOVER_TEMPORARIES_PER_ITEM` | 投影 execution 前 |

`field_provenance` 至多 15 项、每项至多 `MAX_SOURCES_PER_ITEM` 个 id；`image_failures` 至多
`len(ImageRole) × len(ImageFailureKind)`（Frozen Base 上为 `4 × 13`）组、每组至多 500 个 HTTP 状态码；`artifact_counts` / `effect_counts` 定长。因此单条目大小由常量上界约束。

### 21.3 输出字节上限

* `MAX_DIAGNOSTIC_OUTPUT_BYTES = 64 MiB` 是单次 `render_diagnostics_json` 的硬上限。
* 编码以 `json.JSONEncoder(...).iterencode(tree)` 流式产生 chunk，逐 chunk 累加长度（ASCII，故字符数 = 字节数）；累计超过上限时
  立即停止并抛 `DiagnosticsResourceLimitError`，不返回部分输出。输出恰好等于上限时成功。
* 裁决理由：结构上限已使输出有限，但其理论最大值（2000 条 × 64 source × 8 attempt …）远大于实际需要；显式字节上限是更简单、
  可证明的安全方案，并保证 renderer 的内存峰值有界。实际批量（3 个 source、默认 2 attempt）在 2000 条时远低于上限。

## 22. 序列化（冻结）

### 22.1 编码参数

`json.JSONEncoder(skipkeys=False, ensure_ascii=True, check_circular=True, allow_nan=False, sort_keys=True, indent=None,
separators=(",", ":"))`；`iterencode` 结果拼接后 `.encode("ascii")`。没有 BOM、没有末尾换行、没有 `default=` 回调。

### 22.2 JSON 树

renderer 先重检诊断图（第 24.4 节），再**显式**把模型转换为只由 `dict`（`str` key）、`list`、`str`、`int`、`bool`、`None` 组成的
树（不使用 `dataclasses.asdict`，不对任何对象调用 `vars()` / `__dict__`）。转换规则：

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
  "path_policy": "basename | none",
  "timing_policy": "omit | include",
  "metadata_batch": {"generation": 0, "total": 0, "success": 0, "partial": 0, "failed": 0},
  "preview_summary": {},
  "execution_summary": null,
  "outcome": null,
  "items": []
}
```

（上例只示意结构；实际输出无空白、key 按字典序。）

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
| 输入对象图被篡改、类型不符、内部不一致；P4-C8 / 下层不变量重检失败；字段出处完整性失败；遇到不在冻结集合中的枚举 / 模型类型 | `DiagnosticsIntegrityError` |
| 条目数 / 结构上限 / 输出字节上限 | `DiagnosticsResourceLimitError` |
| 将被输出的值违反第 17.2 / 18 节或计时范围 | `DiagnosticsUnsafeValueError` |
| 诊断模型构造违反自身不变量（实现缺陷或调用方手工构造了非法模型） | `DiagnosticsContractError` |
| 渲染前诊断图被篡改（重检失败） | `DiagnosticsIntegrityError` |
| JSON 编码阶段的其它 `ValueError` / `TypeError` / `RecursionError` | `DiagnosticsSerializationError` |

### 24.2 builder 检查顺序（冻结）

1. 顶层输入精确类型 -> `DiagnosticsInputError`；
2. `path_policy` / `timing_policy` 精确枚举 -> `DiagnosticsInputError`；
3. `items` 是精确 `tuple`（否则 `DiagnosticsIntegrityError`），`len(items) <= MAX_DIAGNOSTIC_ITEMS`（否则
   `DiagnosticsResourceLimitError`）；
4. P4-C8 不变量重检（第 24.3 节）-> `DiagnosticsIntegrityError`；
5. 读取 `summary` / `outcome`（失败 -> `DiagnosticsIntegrityError`）；
6. 按 `index` 顺序逐条：下层不变量重检 -> 结构上限 -> 安全值规则 -> 构造条目诊断；第一个失败的条目决定错误；
7. 构造 `BatchDiagnostics`。

任何一步失败都不返回部分结果。

### 24.3 输入不变量重检（冻结）

P4-C8 的 `revalidate` 不是公开 API，诊断不 import 它。等价做法：对第 8.5 节中**精确类型已确认**的上游公开类，调用该类自身的
`__post_init__`（例如 `BatchPreview.__post_init__(preview)`、`BatchExecutionResult.__post_init__(result)`，以及被读取的
`BatchItemResult`、`AggregationResult`、`SourceResult`、`SourceExecutionTrace`、`SourceAttempt`、`FieldConflict`、
`ImageCandidateFailure`、`ExecutionPreflight`、`PreflightBlocker`、`ExecutionResult`、`ExecutionFailure`、`CompletedEffect`、
`LeftoverTemporary`、`DiscoveredMediaItem`、`PlannedPath`、`ItemIssue`）。这些 `__post_init__` 是 CLOSED package 已冻结的纯校验，
不修改对象、不做 I/O。

* **例外**：`NormalizedMetadata.__post_init__` 会以 `object.__setattr__` 重新冻结集合字段（对输入的写操作），诊断**绝不**调用
  它；`field_sources` 的完整性由第 12.3 节的只读检查保证，其余字段诊断不读取。
* 调用被包裹在只覆盖该次调用的 `try` 中；捕获 `Exception`（不捕获 `BaseException` 的其它子类），在 `except` 块之外抛
  `DiagnosticsIntegrityError`，不链接、不读取被捕获的异常。
* 重检只读取对象，不触发 P4-C8 的一次性消费登记：对一个 preview / result 生成诊断之后，它仍然可以被 `execute` /
  `preview_retry` / `merge_retry` 消费（测试固定）。

### 24.4 renderer 检查顺序（冻结）

1. 参数精确为 `BatchDiagnostics` -> 否则 `DiagnosticsInputError`；
2. 重检整个诊断图：每个节点精确类型 + 重新运行其 `__post_init__`（诊断模型）/ 上游 `__post_init__`（第 20 节三种上游值对象）->
   失败 `DiagnosticsIntegrityError`；
3. 转换 JSON 树（第 22.2 节；遇到第 17.2 节之外的 `str` -> `DiagnosticsUnsafeValueError`）；
4. 有界流式编码（第 21.3 节）。

### 24.5 诊断失败不影响原结果

诊断错误从不：修改输入模型、改变 retry eligibility、改变 summary / outcome、触发 retry、修改源文件或目标文件。原
`BatchPreview` / `BatchExecutionResult` 在诊断成功或失败后都逐字段相等、仍可按 P4-C8 合同使用。

## 25. Fail closed（冻结）

输入图被篡改、类型不符、资源超限、出现不支持的枚举 / 模型、或 renderer 发现不安全字段时，**整体失败**并抛对应的类型化错误。
诊断从不静默丢弃字段后输出“看似完整”的报告；第 13 节表中由 schema 明确定义的 absence 是唯一允许的缺省。

## 26. 无副作用（冻结）

`build_*` 与 `render_diagnostics_json` 是只读的。它们不触发：metadata fetch、图片获取、preview、execute、retry、merge、
preflight、filesystem 访问（读或写）、网络、`sleep`、线程创建、asyncio task / loop 创建、子进程、全局 logger 修改、环境变量
读写、`sys.modules` 修改；不修改任何输入对象，不调用 `object.__setattr__` 于输入；不登记 P4-C8 一次性消费。

---

## 27. 架构边界与架构测试（冻结）

### 27.1 新文件 `tests/contract/test_diagnostics_architecture.py`

* 模块集合恰好等于第 6 节中截至该 S 已创建的集合（S3 时为完整 6 个文件），没有子目录。
* `fc2_organizer.diagnostics.__all__` 精确等于第 8.1 节（集合与顺序）；每个名称可解析。
* 每个模块的 import 只来自第 7 节逐模块允许清单与第 8.5 节允许名称；禁止子模块、私有名称、package 模块对象。
* 禁止 import / 引用第 7 节禁止清单（no network、no filesystem writer、no persistence、no Amane、no logging、no threads / async、
  no time / random）。
* 禁止调用：第 7 节列出的全部调用（`open`、`print`、`exec`、`eval`、`compile`、`__import__`、`getattr`、`setattr`、`delattr`、
  `vars`、`id`、`hash`、`repr`、`format`）；`object.__setattr__` 只允许出现在 `models.py`（且只在诊断模型自身内部，若实现需要）；
  `os` 只允许 `os.path.basename`、`os.sep`、`os.altsep`；`json` 只允许在 `render.py` 中使用 `json.JSONEncoder`；`types` 只允许
  `types.MappingProxyType`。
* 不引用上游私有名称（任何 `_` 开头的属性访问，包括 `_shape`、`_manifest_kinds`、`_consumption`、`revalidate`）。
* 不 import / 调用 `BatchOrchestrator`、`merge_retry`、`preflight_execution`、`execute_filesystem`、任何 builder / acquirer /
  materializer / adapter（no orchestration ownership）。
* 模块级赋值只允许不可变常量（no global mutable registry）。
* 没有反向依赖：`src` 下其它模块不 import / 不提及 `fc2_organizer.diagnostics`；`fc2_organizer/__init__.py` 不 import 它；
  裸 `import fc2_organizer` 不加载它（运行时检查）。
* 运行时：在阻断 `amane`、`requests` 的 import hook 下，`fc2_organizer.diagnostics` 可以导入并完成一次 build + render。

### 27.2 生产 / 测试私有接缝许可

测试可以 import 下层私有接缝与既有测试 helper（例如 `tests/unit/orchestration/_fakes.py`、`_helpers.py`、
`fc2_metadata_core.aggregation.policy.FIELD_ORDER`）用于构造输入与交叉验证；该许可只适用于 `tests/**`，生产代码一律禁止。
测试只**读取 / 调用**既有 helper，不修改它们。

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
| `tests/contract/test_orchestration_architecture.py` | `test_no_reverse_dependency_on_orchestration` | 跳过 diagnostics 根目录；并新增一条更严格断言：diagnostics 只能 `from fc2_organizer.orchestration import <第 8.5 节名称>`，不得引用 `BatchOrchestrator` / `merge_retry` / 任何私有名称 |

这些是测试守卫的范围扩展，不改变任何 CLOSED package 的生产语义；P4-C8 合同第 34.3 节已有同类先例。

---

## 28. 测试矩阵（冻结）

所有 P4-C9 测试位于 `tests/unit/diagnostics/` 与 `tests/contract/test_diagnostics_architecture.py`。核心测试（Windows、脱敏、
确定性、资源、架构）**不得** skip；任何平台不可用的 evidence 必须在 HANDOFF 标记为 `EVIDENCE GAP`，不得伪 PASS。

### 28.1 Unit

| 主题 | 要求 |
|---|---|
| 模型校验 | 每个模型的每个字段：合法值、错误类型、`bool` 冒充 `int`、子类冒充、越界、跨字段不变量；全部为 `DiagnosticsContractError` 且 message 固定 |
| 精确公开 API | `__all__` 集合与顺序；函数签名（positional-only / keyword-only / 默认值）；常量数值；`MAX_DIAGNOSTIC_ITEMS is`/`==` `MAX_BATCH_ITEMS`；`PROVENANCE_FIELD_ORDER == aggregation.policy.FIELD_ORDER` |
| 错误 | 层次与多重继承；固定 message；`__cause__` / `__context__` 为 `None` |
| 枚举快照 | 四个新枚举的成员与 value；第 11 节复用的全部上游枚举 value 集合快照 |
| preview 诊断 | READY / BLOCKED / UNPREPARED；每个 `IssueReason`（preview 可达者）；warnings；冲突组；retry preview（`RETRY` shape、`retry_origin`、`retry_scope` 顺序） |
| execution 诊断 | 每个 `ExecutionDisposition`；`ExecutionStatus` SUCCESS / PARTIAL / FAILED；failure 映射；effect / artifact 计数；checkpoint_present；leftover；MAIN / RETRY / MERGED 三种 shape |
| source 诊断 | SUCCESS / NOT_FOUND / 五种 operational failure；refined `SourceErrorKind`；CIRCUIT_OPEN（无 attempt）；deadline during attempt / backoff；retried；无 trace（纯 merge）；disabled sources |
| field provenance | 每个字段类别（number / scalar / collection / external_ids）；只出现已填充字段；优先级顺序；FAILED 时为空；表外 key、非 MappingProxyType、非 contributing id -> `DiagnosticsIntegrityError` |
| issues / warnings | 原样复制；detail 类型名表；`error_type` 规则 |
| failure / retry 映射 | `retry_kind` 与 P4-C8 `ItemExecution.retry_kind` 逐条相等（全部六种 RetryKind） |
| 排序 | 第 16 节每一行 |
| 确定性 | 第 15 节；重复构建 / 渲染逐字节相同 |
| 脱敏 | 第 17-18 节；canary（第 28.5 节） |
| JSON / schema | 顶层 key 集合；每类对象 key 集合恒定；`null` 表达；`sort_keys`；ASCII-only；无末尾换行；schema 常量 |
| 资源上限 | 第 21.2 节每项的边界（等于上限成功、上限 + 1 失败）；输出字节上限（第 28.4 节） |
| 非法 / 篡改输入 | 错误顶层类型、子类、错误策略类型；`object.__setattr__` 篡改 P4-C8 / 下层字段；`items` 非 tuple；不支持的枚举 -> 第 24.1 节对应错误；检查顺序（第 24.2 节） |
| 计时策略 | OMIT 时全部为 `None`；INCLUDE 时截断规则、范围、NaN / 负数 / 超限 -> `DiagnosticsUnsafeValueError` |
| 无副作用 | 第 28.6 节 |

### 28.2 Architecture

第 27.1 节全部条目：module exact set、public API exact set、forbidden private imports、no network、no filesystem write、no
persistence、no Amane、no orchestration ownership、no thread / task creation、no global mutable registry、no reverse dependency；
以及第 27.3 节的授权更新。

### 28.3 Integration（真实 P4-C8 编排 + 脚本化 fake engine / 图片 client + 临时目录文件系统）

至少覆盖并对每个场景同时断言模型与 JSON：SUCCESS batch；PARTIAL batch；FAILED batch；BLOCKED 条目；UNPREPARED 条目；ABORTED 条目；
metadata failure（engine 异常、FAILED aggregate）；metadata partial；图片 warning（缺失 poster / fanart / thumb、无 extrafanart、
候选失败）；execution PARTIAL；execution FAILED；RESUME 候选；FRESH_REEXECUTE；METADATA_REFETCH；PREFLIGHT_RECHECK；DEFERRED
（NOT_SELECTED 与 CANCELLED）；NONE；retry preview 与 merged result；诊断后 preview 仍可 `execute`、result 仍可 `preview_retry`、
retry result 仍可 `merge_retry`（未被消费）。

### 28.4 500-item 诊断门槛与 MAX 边界

* **500 逻辑条目诊断投影门槛**（`tests/unit/diagnostics/test_diagnostics_scale_gate.py`）：以公开构造函数手工构建合法的
  P4-C8 `BatchPreview` 与 `BatchExecutionResult`（覆盖全部 disposition / status / RetryKind / issue 类别的混合分布，不执行真实
  文件系统；不重复 P4-C8 S6 的 500-item 文件系统验收），验证：条目顺序、summary 映射（与 P4-C8 summary 逐字段相等）、确定性
  （两次构建相等、两次渲染逐字节相同、临时身份全部替换后逐字节相同）、资源上界、脱敏（canary 扫描）、序列化（JSON 可被
  `json.loads` 解析且结构符合第 22 节）。
* **MAX 边界**：`MAX_BATCH_ITEMS`（2000）条目的 preview 与 execution 诊断成功构建并渲染（且低于输出上限）；以
  `object.__setattr__` 把 `items` 篡改为 2001 条后，builder 在任何逐条工作之前抛 `DiagnosticsResourceLimitError`（以计数 fake
  证明没有逐条访问）。
* **输出字节上限**：以 monkeypatch 把 `MAX_DIAGNOSTIC_OUTPUT_BYTES` 设为某个真实输出的精确长度 -> 成功；设为该长度 − 1 ->
  `DiagnosticsResourceLimitError` 且未返回部分输出；并证明编码在超限后停止（计数 chunk）。

### 28.5 非空洞性（Non-Vacuity，冻结）

测试必须植入 canary，并以 mutation（测试内 monkeypatch 投影函数，不提交生产改动）证明断言会失败：

| 类别 | canary / mutation | 必须的杀死结果 |
|---|---|---|
| 脱敏 | 在 `SourceResult.error_detail` 植入 `Authorization: Bearer C9CANARY-AUTH` 与 `Cookie: session=C9CANARY-COOKIE`；在 metadata 标题 / 简介 / URL query 植入 `C9CANARY-TEXT` / `token=C9CANARY-URL`；在冲突值、`external_ids` key / value 植入 canary；engine 抛出 message 为 `C9CANARY-EXC` 的异常；源路径父目录与 library root 植入 `C9CANARYDIR` / `C9CANARYROOT` | 默认输出不含任何 canary；mutation “投影时附带 `error_detail`”、“附带异常 message / repr”、“输出 absolute path”、“输出冲突值” 各自使 canary 扫描失败 |
| 路径策略 | `NONE` 策略下文件名 canary 不出现；`BASENAME` 下只出现 basename | mutation “`NONE` 仍输出 basename” 被杀死 |
| 排序 | golden 期望输出（小批量，含多 source、多字段出处、多 conflict、多图片失败组） | mutation “source 按字母排序”、“按 `field_sources` 迭代顺序输出”、“items 反转”、“image 失败组按出现顺序”、“`retry_scope` 迭代 frozenset” 各自被杀死；构造时反转 `field_sources` 插入顺序不改变输出 |
| 确定性 | 临时身份全部替换、完成顺序反转 | mutation “输出 `preview_id` / `result_id` / lineage token / `preflight_id` / `checkpoint_id`” 被逐字节比较杀死 |
| 无副作用 | 见第 28.6 节 | mutation “投影时调用 `preflight_execution` / orchestrator / `open`” 被杀死 |
| fail closed | 篡改输入 | mutation “跳过 P4-C8 重检”、“跳过 `field_sources` 完整性检查”、“跳过条目数上限” 各自被杀死 |

### 28.6 无副作用证据

* 对 integration 场景：诊断前后对临时目录树做完整快照（路径、类型、大小、mtime_ns、内容 hash）——完全相等。
* fake engine / 图片 client / P4-C7 文件系统接缝的调用计数在诊断期间增量为 0。
* 在诊断调用期间以 monkeypatch 让 `BatchOrchestrator.preview` / `execute` / `preview_retry`、`merge_retry`、`preflight_execution`、
  `execute_filesystem`、`builtins.open`、`os` 的变更类函数、`socket.socket`、`threading.Thread.start`、`asyncio.new_event_loop` /
  `asyncio.run`、`logging.Logger.handle` 一律抛错 —— 诊断仍成功。
* 输入对象图在诊断前后逐字段相等，嵌套对象身份（`is`）不变。

### 28.7 Full Test Gates

* P4-C9 专项：`tests/unit/diagnostics` + `tests/contract/test_diagnostics_architecture.py`；
* targeted organizer：`tests/unit/orchestration` + `tests/contract`（含第 27.3 节更新后的守卫）；
* contract：`tests/contract`；
* 全量：整个测试套件；
* 平台：Windows 11 / Python 3.12.x；命令 `python -m pytest -q -p no:cacheprovider --basetemp=<job tmp>`（`fc2-organizer/` 下）。
* 全量 passed 数不得低于 accepted baseline **6178 passed / 40 skipped**（P4-C8 Final；若 Design Review 前 accepted parent 的
  基线合法变化，以实际 accepted parent 重新记录）；skipped 不得增加（新增 skip = NONE）。

## 29. 验收标准（冻结）

P4-C9 Independent Level 1 Review 以下列全部满足为 PASS 前提：

1. 公开 API、模块集合、模型、常量、错误与本合同逐项一致；
2. 第 12 节每条映射有对应测试；第 1 节问题表每一行可由诊断输出回答（integration 证据）；
3. 字段出处只来自 Phase 3 `field_sources`；没有重新聚合；
4. 没有重新计算 summary / outcome / RetryKind；与 P4-C8 值逐项相等；
5. 确定性、排序、脱敏、路径策略、异常安全、载荷边界、资源 / 输出上界、fail closed、无副作用全部有正向测试与第 28.5 节
   非空洞性证据；
6. 架构测试全部通过；第 27.3 节之外没有修改任何既有测试；
7. 没有修改任何 CLOSED package 的 `src/**`（`git diff --stat <Design-Accepted Head>..<C9 Head> -- fc2-organizer/src` 只含
   `src/fc2_organizer/diagnostics/**`）；
8. 第 28.7 节全部门槛通过，无新增 skip；
9. HANDOFF 提供 Contract -> implementation -> test 映射、diff scope、mutation 结果、evidence gaps、known limitations；
10. 风险升级门（第 5.3 节）未被触发，或已按 C 类处理。

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
* 文件名 basename 可能包含用户自己写入的任意文字；需要零文件名输出时使用 `PathPolicy.NONE`。
* 图片失败按 `(role, kind)` 分组，不保留 `candidate_index`。
* `external_ids` 冲突不输出 key。
* `TimingPolicy.INCLUDE` 输出依赖真实计时，跨运行不可逐字节比较（对相同输入仍确定）。
* 导入 `fc2_organizer.orchestration` 会传递加载 `httpx`（上游已冻结事实）；P4-C9 从不引用或使用它。
* 路径 basename 语义随运行平台；POSIX 原生行为若未在 POSIX 主机上运行，HANDOFF 标记为 `EVIDENCE GAP`。

## 32. 实现状态

| 项 | 状态 |
|---|---|
| P4-C9 Design（本合同 + 施工计划） | IMPLEMENTED — INDEPENDENT DESIGN REVIEW REQUIRED |
| P4-C9 Frozen Contract | NOT YET ACCEPTED |
| P4-C9 Construction Plan | NOT YET ACCEPTED |
| S1 Diagnostic model / schema / projection skeleton | NOT STARTED |
| S2 Existing-result integration / source + field provenance mapping | NOT STARTED |
| S3 Safe output / redaction / architecture guards / tests / HANDOFF | NOT STARTED |
| P4-C9 Independent Level 1 Review | NOT STARTED |
| P4-C9 | NOT STARTED（Design Freeze Candidate；production implementation NOT STARTED） |

Design Review PASS 本身建立 Design Accepted Head；之后不创建“E0 closure / design accepted”之类的纯状态 docs commit，实现分支
直接继续（治理文档第 11.1 节）。

---

## 附录 A. 裁决记录（设计者自行裁决；Owner Question Gate：BUSINESS DECISIONS ONLY，本合同无需外部业务决策）

| # | 问题 | 裁决 | 理由 |
|---|---|---|---|
| 1 | 统一模型还是两个模型 | 统一 `BatchDiagnostics` + 显式 `kind` 判别字段 + 字段适用表 | 消费者只需一个 schema；判别字段消除“靠 None 猜阶段” |
| 2 | 输出类型 `str` 还是 `bytes` | `bytes`（ASCII-only） | 逐字节确定性直接可比；无编码歧义；调用方可直接保存或发送 |
| 3 | JSON key 顺序 | `sort_keys=True`，有序集合一律用 array | 最简单、可证明的确定性；顺序语义全部落在 array 上 |
| 4 | 输出上界 | 显式 `MAX_DIAGNOSTIC_OUTPUT_BYTES` + 流式计数 | 比证明结构最大值更简单，内存峰值有界 |
| 5 | 路径默认 | `BASENAME`；另有 `NONE`；不提供 absolute | 安全展示；完整路径可由同进程 UI 经 index 回查 P4-C8 模型 |
| 6 | 计时默认 | `OMIT`；`INCLUDE` 只发布 engine / scheduler 测量值 | 跨运行可比；遵守 P2-R-07 |
| 7 | P4-C8 `revalidate` 非公开 | 对精确公开类调用其自身 `__post_init__` | 不修改 CLOSED package；不 import 私有名称 |
| 8 | `NormalizedMetadata.__post_init__` | 不调用 | 它会写对象；只读检查 `field_sources` |
| 9 | summary / outcome / RetryKind | 原样携带 P4-C8 值 | 杜绝第二套业务语义 |
| 10 | 上游安全值对象（`PreflightBlocker`、`ExecutionFailure`、summary） | 原对象携带 | 全字段安全；减少平行模型；renderer 重检 |
| 11 | 图片失败 | `(role, kind)` 分组计数 | 输出上界只依赖枚举；保留诊断价值 |
| 12 | 冲突值 / `external_ids` key | 不输出 | 来自网页的自由文本 |
| 13 | 不合规 source id | fail closed | 不改写 evidence；默认配置合规 |
| 14 | 结构上限数值 | 64 / 8 / 256 / 256 / 256 / 255 / 7 天 | 高于上游实际与默认值并留余量，同时使单条目大小有常量上界 |
| 15 | 既有架构守卫 | 第 27.3 节七处最小授权更新 | 与 P4-C8 第 34.3 节同类先例；不放宽其它断言 |
