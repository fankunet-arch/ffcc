# FC2 Organizer -- Phase 4 / P4-C8 批量编排 / 预览 / 重试合同（Batch Orchestration / Preview / Retry Contract）

```text
E0 建立时状态 ：P4-C8 E0 ESTABLISHED — INDEPENDENT REVIEW REQUIRED（历史快照，非当前状态）
当前状态       ：以第 38 节“实现状态”为准
Package        ：fc2_organizer.orchestration（新顶层 package，S1 起创建）
Frozen Base    ：586f92f9b96576dbd71c005a6c95b6e7e52210f4（P4-C7 Final Closure Docs；P4-C7 Final Docs-Only Closure Review PASS）
Branch         ：claude/phase4-c8-batch-orchestration
施工计划       ：docs/P4_C8_CONSTRUCTION_PLAN.md（S1-S6，全部批次已在 E0 冻结）
```

本合同在 E0 一次性冻结 P4-C8 的全部规范语义。S1-S6 只能**执行**本合同，不得重新设计。
后续批次对本文件唯一允许的改动是第 38 节“实现状态”表中的状态行；任何语义改动都必须作为独立的
合同修订轮次提出，并经独立复查。

合同修订记录（每一轮都需独立复查）：

| 轮次 | 修订内容 | 涉及章节 |
|---|---|---|
| E0-R1 | 闭合独立 E0 Review 的三个 finding：P4-C8-E0-R-01（新增派生的批级最终结果 `BatchOutcome` 及完整真值表）；P4-C8-E0-R-02（批量条目数硬上限 `MAX_BATCH_ITEMS`、preview 保留 artifact 字节预算、单条图片预算上限、确定性的预约 / 准入规则、`OrchestrationResourceLimitError`）；P4-C8-E0-R-03（S1 的 E0 / S1 状态行治理特例）。其余已 PASS 的设计不变 | 第 5、7.1、7.2、7.4、8、9、10.1、10.7、11.1、11.4、11.5、15.1、19.1、19.5、19.6、25.4、28.3、28.4、34.1、35、35.1、37、38 节；附录 A 第 21-24 条 |
| E0-R2 | 只闭合 E0-R1 复查的两个资源 finding（因而 P4-C8-E0-R-02 仍 OPEN）：P4-C8-E0-R1-01（输入条目数上限改为**快照之前**的有界迭代准入，不信任 `__len__`）；P4-C8-E0-R1-02（lineage 固定的保留预算 `retention_budget_bytes`；当前完整结果保留不变量；`preview_retry` 以 `B - base_retained` 为可用额度；`merge_retry` 纵深防御；多代归纳证明）。P4-C8-E0-R-01、R-03 已 CLOSED，未改动；资源常量数值不变 | 第 5、8、10.4、10.7、18.1、19.6.1、19.6.2、19.6.6、19.6.7、19.6.8、19.6.10、25.4、26、34.1、35、35.1、37、38 节；附录 A 第 25-28 条 |
| S2-A1 | S2 实施中发现的架构依赖遗漏（architecture dependency omission）：第 7.2 节冻结的构造语义要求构造校验既不执行调用方控制的属性钩子（property、描述符、`__getattr__`、`__getattribute__`、元类钩子），又不得比 Phase 3 冻结边界 `inspect.iscoroutinefunction(candidate)` 的 async 判定更窄（含 `functools.partial(async_fn)` 与运行时标准库正式认可的 coroutine 标记语义），且不得自行复制 `inspect` 的内部 coroutine 规则；而原第 6 节的生产标准库集合不含 `inspect`、`functools`，二者无法同时满足。本轮只把 `inspect`、`functools` 加入生产标准库依赖，并严格限定：只有 `orchestrator.py` 可以 import；`inspect` 只用于 `inspect.iscoroutinefunction`（Phase 3 兼容的 async 可调用判定），`functools` 只用于 `functools.partial`（识别精确的标准库 partial 及其包装的 coroutine 语义，服务于安全的静态可调用形态分类）。不改变公开 API、构造接受的语义边界（只是实现已冻结的边界）、preview / 资源 / 重试 / 文件系统 / 网络 / 持久化语义以及任何 S1 / S2 模型 | 第 6、34.1 节 |

基线状态（E0 建立时）：

```text
P4-C1 .. P4-C7 : CLOSED（本合同不修改其中任何一个的生产代码、合同或 HANDOFF）
P4-C8          : NOT STARTED（E0 之后仍为 Implementation NOT STARTED）
P4-C9          : NOT STARTED
Phase 4        : NOT CLOSED
```

---

## 1. 目的（Purpose）

P4-C8 回答：“给定一批已经发现的媒体条目，如何**批量**地把它们安全地推进到整理完成？”

它把已经关闭的下层 package 串成一个可预览、可显式执行、可重试的批量流程：

```text
DiscoveredMediaItem x N（P4-C1 discover_media 的输出，由调用方传入）
   |  文件名 -> 规范番号（fc2_metadata_core.normalize，Phase 1 冻结语法）
   |  批内冲突检测（同源 / 同目标）
   v
BatchScheduler.run(canonical numbers)            Phase 3 C4：有界 metadata 批量聚合
   v
build_organize_plan                               P4-C2
prepare_publication                               P4-C3
render_movie_nfo                                  P4-C4
acquire_images                                    P4-C5（有界并发）
build_artifact_requests                           P4-C6
preflight_execution                               P4-C7（只读）
   v
BatchPreview（只读、零修改；逐条可确认）
   |  显式调用
   v
execute_filesystem（每个被选中的 READY item 恰好一次；有界并发）     P4-C7
   v
BatchExecutionResult（逐条 disposition + ExecutionResult）
   |  preview_retry（失败 / PARTIAL / 阻断 / 延后子集）-> BatchPreview -> execute -> merge_retry
   v
下一代 BatchExecutionResult
```

P4-C8 是**协调者**：它不重新实现任何下层业务逻辑，也不直接触碰文件系统。

## 2. 范围（Scope）

P4-C8 **做**：

* 以严格、有序的 `Sequence[DiscoveredMediaItem]` 作为批量输入，并快照；
* 从每个条目的**文件 basename** 识别规范 FC2 番号（调用 Phase 1 `normalize_fc2_number`，不实现第二个解析器）；
* 批内同源 / 同目标冲突检测（第 14 节）；
* 通过 Phase 3 `BatchScheduler` 批量获取 metadata（复用其有界准入、隔离、致命异常 / 取消、失败子集重试与 lineage）；
* 逐条组装 plan / publication / NFO / images / artifact manifest / preflight，并把每一阶段的失败映射为结构化的 `ItemIssue`；
* 生成只读的 `BatchPreview`；
* 显式执行：对每个被选中的 READY item 调用一次 `execute_filesystem`，有界线程并发，协作式取消；
* 逐条 disposition、批量汇总（summary）；
* 重试：metadata 失败子集（经 Phase 3 `retry_failed` / `apply_retry`）、preflight 阻断重新检查、零 effect 失败的 fresh 重新执行、PARTIAL 的 checkpoint 续做、未执行（未选中 / 已取消）条目的延后执行；
* 重试结果的 fail-closed 合并（`merge_retry`）；
* 进程内的一次性消费登记（preview 只能执行一次、结果只能被重试一次、重试结果只能被合并一次）。

## 3. 非目标（Non-goals）

P4-C8 **不做**：

* 任何直接的文件系统修改或读取（`os.*` 修改性调用、`open`、`stat`、`scandir` 等）；一切文件系统访问都经由 P4-C7
  `preflight_execution`（只读）与 `execute_filesystem`（唯一的修改入口）；
* 重新实现 discovery、番号解析、metadata 聚合、planning、publication、NFO、图片、artifact 映射、原子落盘、
  preflight、执行、checkpoint、封印、指纹、源所有权占用；
* 调用 `discover_media`（调用方负责扫描并把 `DiscoveryResult.items` 传入；`DiscoveryResult.issues` 由调用方 / 将来
  P4-C9 负责呈现）；
* 持久化 / 磁盘 resume / JSON / pickle / SQLite / 状态文件 / 任务数据库 / durable batch id（第 33 节）；
* 诊断文件、诊断 bundle、日志格式、磁盘报告 schema（P4-C9，第 32 节）；
* 进度回调、实时 `PENDING` / `RUNNING` 状态流（第 11.4 节）；
* 跨进程协调（文件锁、命名互斥量、守护进程）（第 30.3 节）；
* 自动删除 / 覆盖 / 移动 / 重命名任何用户文件来“修好”冲突或阻断；
* 已发布 NFO / 图片的重新刮削或覆盖；metadata `PARTIAL` 的自动重新刮削（第 25.6 节）；
* 空间预估、超时（TTL）、墙钟计时、`elapsed` 统计；
* CLI、UI、Amane adapter、HTTP 服务；
* Phase 4 最终验收、release closure、跨 package 的 Phase 4 500-item 全局门槛（P4-C10）。

## 4. 与 Phase 3 批处理合同的比较与复用（冻结）

### 4.1 Phase 3（C4 / C5）已经负责的内容

`PHASE3_BATCH_CONTRACT.md` 冻结的 `fc2_metadata_core.batch`：

* 输入：严格 `str` 规范番号组成的有序 `Sequence`，全有或全无校验，快照；脏输入被**拒绝**而不是修复
  （§4：“脏输入必须先由上层的扫描 / 规范化层处理”）；
* 有界准入：`BatchConfig.max_in_flight_items = M`（默认 4，范围 1..64），`min(M, N)` 个 worker，`O(M)` 任务；
* 条目隔离：普通 `Exception` 只让该条目 `FAILED`（只记录类名）；
* 致命边界：`CancelledError`（调用方）、`KeyboardInterrupt`、`SystemExit`、`GeneratorExit`、其他非 `Exception`
  的 `BaseException` 以及 engine 自行抛出的 `CancelledError`：停止准入、取消并 await 同级、原样重新抛出原始对象、
  不返回部分结果；
* 结果：`BatchResult`（输入顺序，`index == position`）、`BatchItemResult`、`BatchItemStatus`
  （`SUCCESS | PARTIAL | FAILED`，与 `AggregateStatus` 1:1，描述 **metadata 聚合质量**）；
* 失败子集重试：`retry_failed`（只重试 `FAILED`，按原始 index）、`apply_retry`（纯函数、fail closed、lineage 绑定）；
* `BatchLineage`：每次 `run()` 生成一次的 128 位随机、仅内存的出处令牌；generation `0, 1, 2, ...`；
* 忙碌守卫：`BatchBusyError`，busy-first。

### 4.2 任务文本中提到、但在 Frozen Base 上**不存在**的 Phase 3 名称

`BatchRequest`、`BatchTrace`、`durable_id` 不是 Frozen Base `586f92f` 上 `fc2_metadata_core.batch` 的公开 API
（公开集合见其 `__init__.py` 的 `__all__`）。P4-C8 **不创建**这些名称，也不创建任何等价的持久化标识。
Phase 3 的冻结原则继续有效：lineage 是随机、仅内存的；durable batch id 只为将来的持久化 / 恢复所需
（延续项 C4-N1），v1.0 不启用持久化，因此 C4-N1 保持 CARRIED（第 36 节）。

### 4.3 P4-C8 复用的 Phase 3 公开类型与函数（冻结）

| Phase 3 公开名称 | P4-C8 中的用途 |
|---|---|
| `BatchScheduler` | metadata 阶段唯一的批量执行者：`run(numbers)`；metadata 失败子集重试：`retry_failed(previous)` |
| `BatchConfig` | `OrchestrationConfig.metadata`（metadata 阶段的跨条目预算 M，原样使用其校验与范围） |
| `BatchResult`、`BatchItemResult` | metadata 账本：`BatchPreview.metadata_batch` / `BatchExecutionResult.metadata_batch`、`ItemPreview.metadata` 原样保存 |
| `BatchItemStatus`、`BatchItemErrorKind` | 原样用于描述 metadata 结果（第 11 节）；从不用于描述文件系统结果 |
| `BatchLineage` | P4-C8 的 lineage **就是** metadata 账本的 lineage（第 12.2 节）；不新建 lineage 类型 |
| `apply_retry` | metadata 重试结果的合并（第 25.3 节） |
| `AggregationEngine`（protocol） | `BatchOrchestrator` 的 `engine` 参数形态 |

P4-C8 不修改 Phase 3 的任何语义：重复番号仍是独立工作条目（但见第 14 节：P4-C8 在提交给 scheduler **之前**就把批内
冲突的条目排除在 metadata 阶段之外）；`PARTIAL` metadata 不被 Phase 3 重试（第 25.6 节）；scheduler 的忙碌守卫、
致命异常与取消语义原样生效。

### 4.4 不适合文件系统编排、因此 P4-C8 不复用的 Phase 3 设施

| Phase 3 设施 | 不复用的原因 | P4-C8 的对应物 |
|---|---|---|
| `BatchItemStatus` 用于文件系统结果 | 其语义是 metadata 聚合质量；把它用于文件系统会产生“同名不同义”的 `PARTIAL` | 复用 P4-C7 `ExecutionStatus` 描述文件系统结果；P4-C8 自己的枚举使用不同名称（第 11 节） |
| `BatchResult` / `RetryBatchResult` 作为批量结果容器 | 每个条目必须携带 `AggregationResult` 或 engine 失败；无法表达 preview 状态、文件系统 disposition、checkpoint | `BatchPreview`、`BatchExecutionResult` |
| `retry_failed` 作为文件系统重试 | 只处理 metadata `FAILED`；文件系统重试需要 checkpoint / 保留的 plan 与 manifest | `preview_retry` + `merge_retry`（metadata 部分仍委托 `retry_failed` / `apply_retry`） |
| asyncio 任务取消作为执行取消 | 文件系统 syscall 是同步、不可异步中断的；强行取消会丢失 checkpoint | 同步线程执行 + 协作式 `CancellationToken` + 进行中条目完成后才传播致命异常（第 19、27 节） |
| `BatchBusyError` | 它守卫的是单个 scheduler | `OrchestrationBusyError` 守卫整个 orchestrator；内部 scheduler 的守卫照常生效 |

### 4.5 P4-C8 新增的内容

批量 preview、批内冲突检测、逐条阶段化失败映射、显式执行与 disposition、文件系统重试五类、协作式取消、
批量汇总、一次性消费登记、`merge_retry`。

## 5. 包边界与模块划分（冻结）

新顶层 package `fc2_organizer.orchestration`。模块划分冻结（S1-S5 按此创建，不得增删模块名）：

| 模块 | 职责 | 创建批次 |
|---|---|---|
| `__init__.py` | 公开 API 再导出（第 7.1 节集合） | S1（部分）、S5（最终集合） |
| `errors.py` | 错误层次（第 7.4 节） | S1 |
| `models.py` | 枚举、`OrchestrationConfig`、`ItemIssue`、`ItemPreview`、`BatchPreview`、`RetryMaterial`、`ItemExecution`（含第 25.1 节 `retry_kind` 判定表，模型不变量依赖它）、`BatchExecutionResult`、类名提取 helper；（E0-R1）`BatchOutcome` 与 `outcome` 属性、`ResourceLimitReason`、四个资源常量；（E0-R2）`retention_budget_bytes` / `retry_budget_bytes` 字段、保留载荷计量 helper `retry_payload_bytes(material)` 与派生属性 `retained_retry_payload_bytes` / `retained_artifact_bytes`、结果保留不变量；S5 增加 summary 模型与属性 | S1、S5 |
| `cancellation.py` | `CancellationToken` | S1 |
| `_consumption.py` | 进程内一次性登记表（preview 执行、结果重试、重试结果合并），私有 | S1 |
| `recognition.py` | 输入校验与快照（E0-R2：唯一拥有有界快照 helper `bounded_snapshot`，第 19.6.1 节）、番号识别、Phase A 批内冲突分组（纯函数） | S1 |
| `stages.py` | 逐条同步阶段：plan -> publication -> NFO；manifest；preflight；异常 -> `ItemIssue` 映射；Phase B 冲突 | S2 |
| `preview.py` | 异步 preview 组合：scheduler、有界图片 worker、调用 `stages`；（E0-R1）调用局部的保留预算账本与预约准入门 | S2 |
| `orchestrator.py` | `BatchOrchestrator`：构造校验、忙碌守卫、`preview` / `execute` / `preview_retry` 委托 | S2（构造 + `preview`）、S3、S4 |
| `execute.py` | 同步有界执行、selection、disposition 映射、取消、致命异常排空 | S3 |
| `retry.py` | 重试集合（按 `ItemExecution.retry_kind` 与 scope 选择）、`preview_retry` 组合、`merge_retry`；（E0-R2）lineage 预算校验、`base_retained` / `available_retry_budget` 计算、`merge_retry` 的保留不变量纵深防御 | S4 |

`fc2_organizer/__init__.py` **不**急切 import `orchestration`（该文件不修改）。调用方显式使用
`from fc2_organizer.orchestration import BatchOrchestrator`。

## 6. 依赖方向与私有 import 策略（冻结）

```text
fc2_organizer.orchestration
    |-- fc2_metadata_core.batch            （裸公开 package）
    |-- fc2_metadata_core.normalize        （裸公开 package：normalize_fc2_number、FC2RecognitionStatus、is_valid_fc2_number）
    |-- fc2_metadata_core.aggregation      （裸公开 package：仅类型 AggregateStatus / AggregationResult）
    |-- fc2_organizer.discovery            （裸公开 package：DiscoveredMediaItem）
    |-- fc2_organizer.planning             （裸公开 package：OrganizePlan、OutputPolicy、build_organize_plan、公开错误）
    |-- fc2_organizer.publication          （裸公开 package：prepare_publication、PublicationRecord、公开错误）
    |-- fc2_organizer.nfo                  （裸公开 package：render_movie_nfo、公开错误）
    |-- fc2_organizer.images               （裸公开 package：ImageAcquisitionPolicy、ImageAcquisitionResult、ImageCandidateFailure、公开错误）
    |-- fc2_organizer.images.acquisition   （P4-C5 合同 §14 冻结的显式 import 路径：acquire_images）
    |-- fc2_organizer.materialization      （裸公开 package：ArtifactKind、ArtifactWriteRequest、ArtifactMappingError、MappingRejectionReason、MaterializationError）
    |-- fc2_organizer.materialization.mapping （P4-C6 合同 §17、§23 冻结的显式 import 路径：build_artifact_requests）
    |-- fc2_organizer.execution            （裸公开 package：preflight_execution、execute_filesystem 与第 4 节公开导出）
    '-- 标准库
```

* 允许的标准库（生产）：`__future__`、`asyncio`、`collections.abc`、`dataclasses`、`enum`、`ntpath`、`os`、
  `posixpath`、`re`、`secrets`、`threading`、`typing`；（S2-A1）以及 `inspect`、`functools`。`os` 只允许两种使用：
  `os.name`、`os.path.basename`（AST 强制）。
* （S2-A1）`inspect` 与 `functools` 只允许 `src/fc2_organizer/orchestration/orchestrator.py` 直接 import，其它
  orchestration 生产模块一律不得 import 它们。用途严格限定为第 7.2 节构造校验：
  * `inspect`：只用于 `inspect.iscoroutinefunction`，且只作用于构造校验已经以零钩子静态方式解析出的精确标准对象
    （函数、函数的绑定方法、精确 `functools.partial` 链），使 `engine.aggregate` 的 async 判定与 Phase 3
    冻结边界及当前 Python runtime 的标准库语义一致；不授权 `inspect` 的其它任何接口（例如 `getattr_static`、
    `getmembers`、`stack`、`currentframe`、源码读取、帧遍历）；
  * `functools`：只用于 `functools.partial`（以 `type(x) is functools.partial` 识别精确的标准库 partial，并经其 C 层
    `func` 成员做安全的包装可调用分类）；不授权 `functools` 的其它任何接口。
  * 本授权不放宽零钩子约束：构造校验仍不得执行调用方控制的钩子（不得 `getattr(engine, "aggregate")` /
    `getattr(image_client, "get")` 或任何会执行调用方描述符的检查）。P4-C8 不定义自己的 coroutine 标记语义：
    调用方自行设置的 `_is_coroutine_marker` 键不因“键存在”而被视为 async，async 判定只跟随当前 runtime 标准库的
    正式语义。
* **生产代码禁止 import**（静态 AST + 运行时）：
  * P4-C7 私有模块与任何子模块：`fc2_organizer.execution._fs`、`fc2_organizer.execution.seal`、
    `fc2_organizer.execution.{models,errors,paths,validation,directories,transfer,preflight,executor}`；
  * P4-C6 子模块：`fc2_organizer.materialization.{atomic,artifacts,models,errors}`（`mapping` 除外）；
  * P4-C5 子模块：`fc2_organizer.images.{transport,jpeg,urls,models,policy,errors}`（`acquisition` 除外）；
    P4-C8 从不构造图片 client，从不 import `httpx`；
  * `fc2_organizer.{discovery,planning,publication,nfo}` 的任何子模块；
  * `fc2_metadata_core` 的 `sources`、`http`、`resource_control`、`models` 子模块以及 `aggregation` / `batch` /
    `normalize` 的任何子模块（只允许裸 package）；
  * `amane`、`httpx`、`requests`、`socket`、`ssl`、`urllib`、`http`、`json`、`pickle`、`marshal`、`shelve`、`dbm`、
    `sqlite3`、`csv`、`logging`、`tempfile`、`shutil`、`glob`、`fnmatch`、`pathlib`、`io`、`subprocess`、
    `multiprocessing`、`concurrent`、`ctypes`、`time`、`datetime`、`random`、`hashlib`、`hmac`。
* **测试**可以 import 下层私有接缝（例如 `fc2_organizer.execution._fs._FS`、`fc2_organizer.materialization.atomic._FS`、
  既有测试 helper 模块）用于失败注入；这一许可只适用于 `tests/**`，生产代码一律禁止（第 34 节 AST 强制）。
* 没有反向依赖：`src` 下任何其他模块都不 import `fc2_organizer.orchestration`；`fc2_organizer/__init__.py` 不 import 它；
  裸 `import fc2_organizer` 不加载它。
* 传递加载说明：`fc2_organizer.images.acquisition` 会传递加载 `httpx`（P4-C5 transport 的 protocol 定义）；
  `fc2_organizer.planning` 会传递加载 `fc2_metadata_core`。这些是已冻结的上游事实，不是 P4-C8 的直接依赖；静态扫描证明
  P4-C8 源码从不**引用**它们。
* 既有架构守卫的最小授权更新（S1 执行，第 34.3 节）：四个顶层 package 集合断言各加入 `"orchestration"`；
  `test_execution_architecture.py` 与 `test_materialization_architecture.py` 的反向依赖守卫为 `orchestration` 增加豁免，
  并各自新增一条更严格的断言，限定 P4-C8 只能 import 本节列出的名称。

## 7. 公开 API（冻结）

### 7.1 公开导出（`fc2_organizer.orchestration.__all__`，S5 最终精确集合）

```text
BatchOrchestrator, OrchestrationConfig, CancellationToken, merge_retry,
BatchPreview, ItemPreview, PreviewState, PreviewSummary,
BatchExecutionResult, ItemExecution, ExecutionDisposition, ExecutionSummary, BatchOutcome,
RetryMaterial, RetryKind,
OrchestrationStage, IssueReason, ItemIssue, ItemWarning, ResourceLimitReason,
DEFAULT_IMAGE_IN_FLIGHT_ITEMS, MAX_IMAGE_IN_FLIGHT_ITEMS,
DEFAULT_FILESYSTEM_WORKERS, MAX_FILESYSTEM_WORKERS,
MAX_BATCH_ITEMS, MAX_ITEM_IMAGE_BYTES,
DEFAULT_MAX_RETAINED_ARTIFACT_BYTES, MAX_RETAINED_ARTIFACT_BYTES_LIMIT,
OrchestrationError, OrchestrationConfigError, OrchestrationInputError, OrchestrationBusyError,
OrchestrationContractError, OrchestrationIntegrityError, OrchestrationConsumedError, OrchestrationRetryError,
OrchestrationResourceLimitError
```

（E0-R1 新增：`BatchOutcome`、`ResourceLimitReason`、`MAX_BATCH_ITEMS`、`MAX_ITEM_IMAGE_BYTES`、
`DEFAULT_MAX_RETAINED_ARTIFACT_BYTES`、`MAX_RETAINED_ARTIFACT_BYTES_LIMIT`、`OrchestrationResourceLimitError`。）

没有 `run`、`execute_all`、`resume`、`rollback`、`save`、`load`、`to_json`、`to_dict`、`dump`、`write`、`report`、
`progress`、`subscribe` 等名称。

### 7.2 `BatchOrchestrator`

```python
from fc2_organizer.orchestration import BatchOrchestrator, OrchestrationConfig, CancellationToken, merge_retry

orchestrator = BatchOrchestrator(
    engine,                       # Phase 3 AggregationEngine：带 async aggregate(number) 的对象（例如 MultiSourceEngine）
    image_client,                 # P4-C5 ImageHttpClient：带可调用 get 的对象（例如 HttpxImageClient）
    library_root,                 # 严格 str，非空（语义校验由 P4-C2 逐条完成，第 15.3 节）
    *,
    output_policy=None,           # OutputPolicy | None -> OutputPolicy()
    image_policy=None,            # ImageAcquisitionPolicy | None -> ImageAcquisitionPolicy()
    config=None,                  # OrchestrationConfig | None -> OrchestrationConfig()
)

preview: BatchPreview = await orchestrator.preview(items)                     # 只读
result: BatchExecutionResult = orchestrator.execute(preview, selection=None, cancel=None)   # 同步
retry_preview: BatchPreview = await orchestrator.preview_retry(result, scope=None)          # 只读
retry_result: BatchExecutionResult = orchestrator.execute(retry_preview)
merged: BatchExecutionResult = merge_retry(result, retry_result)
```

* 构造：只校验、不执行任何网络 / 文件系统操作。构造时创建**一个** `BatchScheduler(engine, config.metadata)` 并在
  orchestrator 生命周期内复用（其构造校验 `engine.aggregate` 为 async；`BatchConfigError` 被翻译为
  `OrchestrationConfigError`，不链接）。`image_client` 必须具有可调用的 `get`（`OrchestrationConfigError`）；
  （E0-R1）解析后的 `image_policy.max_total_bytes` 必须 `<= MAX_ITEM_IMAGE_BYTES`，否则 `OrchestrationConfigError`
  （单条图片预算上限，第 19.6 节）；
  P4-C8 从不构造、从不关闭 image client 与 engine（资源生命周期属于调用方）。
* 只读属性：`config`、`library_root`、`output_policy`、`image_policy`。
* `preview` 与 `preview_retry` 是 `async`（metadata 与图片是异步网络）；`execute` 是**同步**的（文件系统
  syscall 同步且不可异步中断）。在事件循环中的调用方应以 `await asyncio.to_thread(orchestrator.execute, ...)`
  调用，并用 `CancellationToken` 请求停止（第 27 节）。
* `merge_retry` 是模块级函数（第 26 节）。

### 7.3 忙碌守卫（busy-first）

每个 orchestrator 同一时刻只允许一个活动操作（`preview`、`execute`、`preview_retry` 三者共用一个标志，由
`threading.Lock` 保护）。忙碌检查是每个方法的**第一个**步骤，先于任何参数校验：忙碌时一律抛出
`OrchestrationBusyError`，被拒绝的调用不释放占用。占用在 `finally` 中释放。原因与 Phase 3 §2 相同：并发操作会
悄悄把预算翻倍。需要独立预算就使用独立的 orchestrator 实例（预算相加）。

### 7.4 错误层次（`errors.py`，冻结）

```text
OrchestrationError(Exception)
+-- OrchestrationConfigError(OrchestrationError, ValueError)      构造参数 / OrchestrationConfig 非法
+-- OrchestrationInputError(OrchestrationError, ValueError)       items / selection / cancel / scope / previous 类型或取值非法；
|                                                                 preview / result 与本 orchestrator 的配置不一致
+-- OrchestrationBusyError(OrchestrationError, RuntimeError)      已有活动操作
+-- OrchestrationContractError(OrchestrationError, ValueError)    模型不变量被违反（构造时）
+-- OrchestrationIntegrityError(OrchestrationError, ValueError)   preview / result 对象图在构造后被改写或内部不一致
+-- OrchestrationConsumedError(OrchestrationError, RuntimeError)  preview 已执行 / 结果已重试 / 重试结果已合并
+-- OrchestrationRetryError(OrchestrationError, ValueError)       merge_retry / preview_retry 的 fail-closed 不匹配
'-- OrchestrationResourceLimitError(OrchestrationError, RuntimeError)   （E0-R1）批级资源硬限制被触及（第 19.6 节）
                                                                        .reason: ResourceLimitReason
```

`OrchestrationResourceLimitError`（E0-R1）：

* `.reason` 为 `ResourceLimitReason.BATCH_ITEM_LIMIT` 或 `ResourceLimitReason.RETAINED_BYTES_LIMIT`（第 10.1 节）；
* 消息为固定措辞加 reason 值与限制常量值，例如 `batch resource limit reached: batch_item_limit (MAX_BATCH_ITEMS=2000)`、
  `batch resource limit reached: retained_bytes_limit`；不含路径、番号、URL、标题、字节内容或下层异常文本；
* 在任何 `except` 块之外抛出，不链接任何异常；
* 抛出时机与后果见第 19.6.6 节：整个 `preview` / `preview_retry` 调用 fail closed，不返回任何部分 `BatchPreview`；
  这两个操作只读，因此零文件系统修改。

* 消息只含固定措辞、枚举值、下标与类名：不含路径、标题、URL、番号以外的 metadata、内容字节、异常文本。
* 所有 P4-C8 错误都在任何 `except` 块之外抛出（`__cause__` / `__context__` 为 `None`），不链接下层异常。
* 这些错误表示**调用方错误或篡改**，从不表示单个条目的结果；条目结果一律是数据（第 20 节）。

## 8. 严格类型规则（冻结）

与 P4-C5 / P4-C7 相同的严格性：

* 所有输入身份检查使用 `type(x) is T`：`DiscoveredMediaItem`、`BatchPreview`、`BatchExecutionResult`、
  `CancellationToken`、`OrchestrationConfig`、`OutputPolicy`、`ImageAcquisitionPolicy`、`BatchConfig`、`RetryKind`、
  `tuple`、`frozenset`、`int`（`bool` 不是 `int`）、`str`。子类一律拒绝，被拒绝对象的任何方法 / 属性钩子都不运行。
* `items` 容器：`collections.abc.Sequence`，但拒绝 `str` / `bytes` / `bytearray` / `memoryview`、任何 `Set`、`Mapping`、
  生成器 / 迭代器（与 Phase 3 §4 同一规则）；（E0-R2）唯一的快照由第 19.6.1 节的**有界快照算法**产生——从不调用
  `tuple(items)` / `list(items)` / `len(items)` 完整物化或度量未知长度的输入；快照之后调用方修改自己的 list 无影响。
  元素全有或全无：任何一个元素不是严格 `DiscoveredMediaItem` -> `OrchestrationInputError`，在任何网络 / 文件系统访问之前，
  消息列出至多 10 个出问题的下标（总数始终统计）与类名。
* （E0-R2，取代 E0-R1 的“快照完成后检查长度”）`preview(items)` 的输入错误优先级冻结为：
  `busy-first -> 容器种类校验 -> 有界快照 / 条目数门（BATCH_ITEM_LIMIT）-> 逐元素严格类型校验 -> 其余语义校验`。
  实际可迭代出超过 `MAX_BATCH_ITEMS` 个元素的输入一律得到 `OrchestrationResourceLimitError(BATCH_ITEM_LIMIT)`，
  不再读取第 `MAX_BATCH_ITEMS + 1` 个之后的任何元素，也不为寻找其他非法元素而继续扫描；恰好 `MAX_BATCH_ITEMS` 个合法。
* 所有模型是 `@dataclass(frozen=True, slots=True)`；所有集合字段是严格 `tuple` / `frozenset`；不保存调用方持有的可变容器。
* 类名提取（`error_type`）是全函数，不运行调用方控制的代码：`type(obj)`、经 `type.__dict__["__name__"]` descriptor 读取、
  metaclass 不是 `type` 或名称不是长度 ≤ 128 的严格标识符 `str` 时为 `"UnknownType"`（与 Phase 3 C4-R1-01 相同的规则；
  Phase 3 的 `_type_name` 是私有 helper，P4-C8 在 `models.py` 中持有自己的等价实现）。
* 从下层异常读取 `.reason`：只在 `type(exc)` **恰为** `PlanGraphError`、`ArtifactManifestError`、`CheckpointError`、
  `PreflightIntegrityError`（P4-C7）或 `ArtifactMappingError`（P4-C6）时读取，并校验读到的值是对应冻结枚举的成员；
  否则 `detail = None`。从不读取异常的 `args`、`str()`、`repr()`、traceback。

## 9. 配置（`OrchestrationConfig`，冻结）

```python
DEFAULT_IMAGE_IN_FLIGHT_ITEMS = 4
MAX_IMAGE_IN_FLIGHT_ITEMS = 16
DEFAULT_FILESYSTEM_WORKERS = 1
MAX_FILESYSTEM_WORKERS = 8
MAX_BATCH_ITEMS = 2000                                     # E0-R1：批量条目数硬上限（常量，不可配置）
MAX_ITEM_IMAGE_BYTES = 64 * 1024 * 1024                    # E0-R1：P4-C8 接受的单条 image_policy.max_total_bytes 上限
DEFAULT_MAX_RETAINED_ARTIFACT_BYTES = 2 * 1024 ** 3       # E0-R1：2 GiB
MAX_RETAINED_ARTIFACT_BYTES_LIMIT = 16 * 1024 ** 3        # E0-R1：16 GiB（绝对上限）

@dataclass(frozen=True, slots=True)
class OrchestrationConfig:
    metadata: BatchConfig = field(default_factory=BatchConfig)   # Phase 3：max_in_flight_items 默认 4，1..64
    image_in_flight_items: int = DEFAULT_IMAGE_IN_FLIGHT_ITEMS  # 1..16
    filesystem_workers: int = DEFAULT_FILESYSTEM_WORKERS         # 1..8
    max_retained_artifact_bytes: int = DEFAULT_MAX_RETAINED_ARTIFACT_BYTES   # E0-R1：1..MAX_RETAINED_ARTIFACT_BYTES_LIMIT
```

* `__post_init__` 校验：`metadata` 为严格 `BatchConfig`；三个 int 为严格 `int`（非 `bool`）且在范围内；否则
  `OrchestrationConfigError`。不可变。`max_retained_artifact_bytes` 的下限是 1（测试以小预算模拟边界）；它可以小于
  单条图片预约额，此时任何需要图片阶段的条目都会按第 19.6.6 节确定地 fail closed。
* 没有 `continue_on_item_failure`、`overwrite`、`delete_conflicts`、`auto_resume`、`persist`、`timeout` 等旋钮：
  条目隔离、无覆盖、无持久化都是冻结语义，不是选项。
* `filesystem_workers` 默认 **1**：同卷 rename 近乎瞬时，跨卷复制是 I/O 受限的大文件流式复制，同一磁盘上的并行复制通常
  更慢；串行默认也最容易推理。并发执行的正确性（不同目标、不同源）由 P4-C7 与第 14 节保证，调用方可显式提高到 8。

## 10. 模型（`models.py`，冻结）

### 10.1 枚举

```python
class PreviewState(Enum):
    READY = "ready"              # 有 ready 的 ExecutionPreflight，可执行
    BLOCKED = "blocked"          # 安全门拒绝：preflight 阻断或批内冲突；数据本身没有问题
    UNPREPARED = "unprepared"    # 管线在某一阶段无法产生可执行的 preflight

class ExecutionDisposition(Enum):
    EXECUTED = "executed"            # execute_filesystem 返回了 ExecutionResult；结果见 ExecutionStatus
    NOT_READY = "not_ready"          # preview 状态为 BLOCKED / UNPREPARED，未执行
    NOT_SELECTED = "not_selected"    # READY 但不在 selection 中，未执行
    CANCELLED = "cancelled"          # READY、被选中，但取消请求先于准入，未执行
    REJECTED = "rejected"            # execute_filesystem 在任何文件系统访问之前以冻结的类型化错误拒绝
    ABORTED = "aborted"              # execute_filesystem 抛出外来的普通 Exception；文件系统状态未知

class OrchestrationStage(Enum):
    NUMBER_RECOGNITION = "number_recognition"
    BATCH_CONFLICT = "batch_conflict"
    METADATA = "metadata"
    PLANNING = "planning"
    PUBLICATION = "publication"
    NFO_RENDER = "nfo_render"
    IMAGE_ACQUISITION = "image_acquisition"
    MANIFEST = "manifest"
    PREFLIGHT = "preflight"
    EXECUTION = "execution"

class IssueReason(Enum):
    NUMBER_NOT_RECOGNIZED = "number_not_recognized"
    DUPLICATE_SOURCE_IN_BATCH = "duplicate_source_in_batch"
    DUPLICATE_TARGET_IN_BATCH = "duplicate_target_in_batch"
    METADATA_UNAVAILABLE = "metadata_unavailable"
    METADATA_ENGINE_FAILURE = "metadata_engine_failure"
    PLANNING_REJECTED = "planning_rejected"
    PUBLICATION_REJECTED = "publication_rejected"
    NFO_RENDER_FAILED = "nfo_render_failed"
    IMAGE_ACQUISITION_ERROR = "image_acquisition_error"
    MANIFEST_REJECTED = "manifest_rejected"
    PREFLIGHT_BLOCKED = "preflight_blocked"
    PREFLIGHT_REJECTED = "preflight_rejected"
    CHECKPOINT_REJECTED = "checkpoint_rejected"
    EXECUTION_FAILED = "execution_failed"
    EXECUTION_PARTIAL = "execution_partial"
    EXECUTION_REJECTED = "execution_rejected"
    EXECUTION_ABORTED = "execution_aborted"

class ItemWarning(Enum):
    METADATA_PARTIAL = "metadata_partial"
    POSTER_ABSENT = "poster_absent"
    FANART_ABSENT = "fanart_absent"
    THUMB_ABSENT = "thumb_absent"
    NO_EXTRAFANART = "no_extrafanart"
    IMAGE_CANDIDATE_FAILURES = "image_candidate_failures"
    LEFTOVER_TEMPORARIES = "leftover_temporaries"

class RetryKind(Enum):
    METADATA_REFETCH = "metadata_refetch"
    PREFLIGHT_RECHECK = "preflight_recheck"
    FRESH_REEXECUTE = "fresh_reexecute"
    RESUME = "resume"
    DEFERRED = "deferred"
    NONE = "none"

class BatchOutcome(Enum):                 # E0-R1：批级最终结果（第 11.5 节）；只有这三个成员
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"

class ResourceLimitReason(Enum):          # E0-R1：第 19.6 节
    BATCH_ITEM_LIMIT = "batch_item_limit"
    RETAINED_BYTES_LIMIT = "retained_bytes_limit"
```

`BatchOutcome` 的成员名与 `ExecutionStatus` 相同，但它回答的是**整批**的最终结果，其语义由第 11.5 节从各条目的
`ExecutionStatus` 严格推导，不引入新的条目级状态（第 11.1 节的“条目级不新增同名状态”规则不变）。

### 10.2 `ItemIssue`

```text
stage       : OrchestrationStage
reason      : IssueReason
error_type  : str | None     类名（第 8 节全函数提取）；只用于由异常产生的原因
detail      : Enum | None    下层冻结原因枚举成员
```

原因、阶段、`error_type` 与 `detail` 的合法组合（`__post_init__` 强制，`OrchestrationContractError`）：

| `reason` | `stage` | `error_type` | `detail` 类型 |
|---|---|---|---|
| `NUMBER_NOT_RECOGNIZED` | `NUMBER_RECOGNITION` | `None` | `None` |
| `DUPLICATE_SOURCE_IN_BATCH` | `BATCH_CONFLICT` | `None` | `None` |
| `DUPLICATE_TARGET_IN_BATCH` | `BATCH_CONFLICT` | `None` | `None` |
| `METADATA_UNAVAILABLE` | `METADATA` | `None` | `None` |
| `METADATA_ENGINE_FAILURE` | `METADATA` | 必填（取自 `BatchItemResult.error_type`） | 必填 `BatchItemErrorKind` |
| `PLANNING_REJECTED` | `PLANNING` | 必填 | `None` |
| `PUBLICATION_REJECTED` | `PUBLICATION` | 必填 | `None` |
| `NFO_RENDER_FAILED` | `NFO_RENDER` | 必填 | `None` |
| `IMAGE_ACQUISITION_ERROR` | `IMAGE_ACQUISITION` | 必填 | `None` |
| `MANIFEST_REJECTED` | `MANIFEST` | 必填 | `MappingRejectionReason` 或 `None` |
| `PREFLIGHT_BLOCKED` | `PREFLIGHT` | `None` | `None`（阻断原因见 `preflight.blockers`） |
| `PREFLIGHT_REJECTED` | `PREFLIGHT` | 必填 | `PlanGraphRejectionReason` / `ManifestRejectionReason` 或 `None` |
| `CHECKPOINT_REJECTED` | `PREFLIGHT` | 必填 | 必填 `CheckpointRejectionReason` |
| `EXECUTION_FAILED` | `EXECUTION` | `None` | 必填 `ExecutionFailureKind`（`== execution.failure.kind`） |
| `EXECUTION_PARTIAL` | `EXECUTION` | `None` | 必填 `ExecutionFailureKind`（`== execution.failure.kind`） |
| `EXECUTION_REJECTED` | `EXECUTION` | 必填 | `PreflightIntegrityReason` / `CheckpointRejectionReason` / `PlanGraphRejectionReason` / `ManifestRejectionReason` 或 `None` |
| `EXECUTION_ABORTED` | `EXECUTION` | 必填 | `None` |

`error_type`：严格 `str`，标识符形态，长度 1..128。

### 10.3 `ItemPreview`

```text
index              : int >= 0                    批次内的稳定身份（第 12 节）
generation         : int >= 0                    产生本条 preview 的轮次
media_item         : DiscoveredMediaItem         原对象（严格类型）
canonical_number   : str | None                  None 当且仅当 reason == NUMBER_NOT_RECOGNIZED
metadata_position  : int | None                  在 metadata_batch 中的位置；None 当且仅当未提交给 metadata 阶段
metadata           : BatchItemResult | None      is metadata_batch.items[metadata_position]
plan               : OrganizePlan | None
image_failures     : tuple[ImageCandidateFailure, ...]
preflight          : ExecutionPreflight | None
state              : PreviewState
issue              : ItemIssue | None
conflict_with      : tuple[int, ...]             批内冲突对端的 index，严格递增，不含自身
retry_origin       : RetryKind | None            重试 preview 中产生本条的 RetryKind；主 preview 中为 None
```

不变量（`OrchestrationContractError`）：

* `state is READY` ⇔ `issue is None` ⇔（`preflight is not None` 且 `preflight.ready is True` 且 `conflict_with == ()`）。
* `state is BLOCKED` ⇔ `issue.reason in {PREFLIGHT_BLOCKED, DUPLICATE_SOURCE_IN_BATCH, DUPLICATE_TARGET_IN_BATCH}`；
  `PREFLIGHT_BLOCKED` ⇒ `preflight` 非空、`ready is False`、`blockers` 非空、`conflict_with == ()`；
  `DUPLICATE_*` ⇒ `conflict_with` 非空（`preflight` 可以为空（Phase A）或非空（Phase B），非空时不可执行）。
* `state is UNPREPARED` ⇔ 其他原因；此时 `preflight is None`、`conflict_with == ()`。
* `canonical_number` 非空时为严格 `str` 且 `is_valid_fc2_number`；`metadata` 非空时 `metadata.number == canonical_number`。
* `plan` 非空时：`plan.canonical_number == canonical_number`、`plan.source_path == media_item.source_path`；
  `preflight` 非空时 `preflight.plan is plan`。
* `retry_origin is None` ⇔ `generation == 0`；非空时不能是 `RetryKind.NONE`。
* `image_failures` 是严格 `tuple`，元素为严格 `ImageCandidateFailure`。

派生的显示属性（只读 property，不存储，因此不可能与数据矛盾；数据不可得时为 `None`）：

| 属性 | 来源 | 条件 |
|---|---|---|
| `source_path` / `source_size` | `media_item` | 总是可得 |
| `target_directory`、`final_media_path`、`nfo_target`、`extrafanart_directory` | `plan` 的对应 `PlannedPath.absolute_path` | `plan` 非空 |
| `poster_target`、`fanart_target`、`thumb_target` | `plan` 路径，且 manifest 含对应 kind；manifest 不含该 kind 时为 `None` | `preflight` 非空 |
| `artifact_kinds` | manifest 中各请求的 `ArtifactKind`（按 manifest 顺序） | `preflight` 非空 |
| `extrafanart_count` | manifest 中 `EXTRAFANART` 请求数 | `preflight` 非空 |
| `preflight_mode` | `preflight.mode`（`FRESH` / `RESUME`） | `preflight` 非空 |
| `planned_units` | `preflight.pending_units` | `preflight` 非空 |
| `completed_units` | `preflight.completed_units` | `preflight` 非空 |
| `skipped_steps` | `preflight.skipped_steps` | `preflight` 非空 |
| `predicted_transfer_mode` | `preflight.transfer_mode`（预测值，第 17.3 节） | `preflight` 非空 |
| `blockers` | `preflight.blockers` | `preflight` 非空 |
| `warnings` | 第 22 节规则，按 `ItemWarning` 声明顺序 | 总是可得（可能为空 tuple） |
| `executable` | `state is READY` | 总是可得 |

### 10.4 `BatchPreview`

```text
preview_id      : str       32 位小写 hex（secrets.token_hex(16)）；repr=False
lineage         : BatchLineage   == metadata_batch.lineage
generation      : int >= 0
base_result_id  : str | None     重试 preview：被重试的 BatchExecutionResult.result_id；主 preview：None
retry_scope     : frozenset[RetryKind] | None    重试 preview：本轮**解析后**的范围（scope=None 时存储除 NONE 以外的全部成员）；主 preview：None
library_root    : str
output_policy   : OutputPolicy
image_policy    : ImageAcquisitionPolicy
batch_size      : int >= 0   本 lineage 的输入条目总数 N
items           : tuple[ItemPreview, ...]
metadata_batch  : BatchResult    Phase 3 metadata 账本（最新）
retention_budget_bytes : int     （E0-R2）lineage 固定的保留预算 B（第 19.6.2 节）
retry_budget_bytes     : int | None   （E0-R2）重试 preview：本轮可用额度 B - base_retained；主 preview：None
```

（E0-R2）派生属性 `retained_artifact_bytes` = 全部 `preflight is not None` 的条目的 `Σ len(req.content)`（对 `preflight.artifacts`；
共享的 bytes 对象按引用次数重复计入，保守，不会少计）。不变量：`1 <= retention_budget_bytes <= MAX_RETAINED_ARTIFACT_BYTES_LIMIT`；
`retry_budget_bytes is None` ⇔ 主 preview；重试 preview 满足 `0 <= retry_budget_bytes <= retention_budget_bytes`；
`retained_artifact_bytes <= retention_budget_bytes`（主 preview）或 `<= retry_budget_bytes`（重试 preview）。

不变量：`base_result_id is None` ⇔ `retry_scope is None` ⇔ `generation == 0`（主 preview）；主 preview 的
`[i.index for i in items] == list(range(batch_size))`；重试 preview 的 index 严格递增且均 `< batch_size`，`generation >= 1`；
每个 `item.generation == generation`；`metadata_batch.lineage == lineage`；每个 `metadata` 非空的 item 满足
`item.metadata is metadata_batch.items[item.metadata_position]`。`summary` 属性见第 28 节。

### 10.5 `RetryMaterial`

```text
plan        : OrganizePlan
artifacts   : tuple[ArtifactWriteRequest, ...]
checkpoint  : ExecutionCheckpoint | None
```

保留重试所需的**原对象**（不复制、不重建）：`plan` 与 `artifacts` 取自该条目最近一次 `ExecutionPreflight` 的
`preflight.plan` / `preflight.artifacts`（P4-C7 指纹绑定要求 resume 时两者与原执行相同，第 24 节）。

### 10.6 `ItemExecution`

```text
index, generation, media_item, canonical_number, metadata_position, metadata, plan, image_failures, conflict_with
                    : 与该条目被执行（或未执行）时的 ItemPreview 相同（同一对象）
preview_state       : PreviewState
issue               : ItemIssue | None
warnings            : tuple[ItemWarning, ...]      执行时 preview.warnings + 执行产生的警告（第 22 节）
disposition         : ExecutionDisposition
execution           : ExecutionResult | None       当且仅当 disposition is EXECUTED
retry_material      : RetryMaterial | None
```

不变量：

| `disposition` | `preview_state` | `execution` | `issue` |
|---|---|---|---|
| `EXECUTED`，`status SUCCESS` | `READY` | 非空 | `None` |
| `EXECUTED`，`status FAILED` | `READY` | 非空 | `EXECUTION_FAILED`，`detail == execution.failure.kind` |
| `EXECUTED`，`status PARTIAL` | `READY` | 非空 | `EXECUTION_PARTIAL`，`detail == execution.failure.kind` |
| `NOT_READY` | `BLOCKED` / `UNPREPARED` | `None` | preview 的 `issue`（非空） |
| `NOT_SELECTED`、`CANCELLED` | `READY` | `None` | `None` |
| `REJECTED` | `READY` | `None` | `EXECUTION_REJECTED` |
| `ABORTED` | `READY` | `None` | `EXECUTION_ABORTED` |

`retry_material is not None` ⇔ `retry_kind in {PREFLIGHT_RECHECK, FRESH_REEXECUTE, RESUME, DEFERRED}`（第 25.1 节）；
`RESUME` ⇒ `retry_material.checkpoint is execution.checkpoint`；`FRESH_REEXECUTE` ⇒ `checkpoint is None`；
`PREFLIGHT_RECHECK` / `DEFERRED` ⇒ `checkpoint is` 该条目 preview preflight 的 `checkpoint`（可为 `None`）。
派生属性：`execution_status`（`ExecutionStatus | None`）、`retry_kind`（第 25.1 节纯函数）、与 `ItemPreview` 相同的
路径类显示属性（基于 `plan`；`poster_target` 等 manifest 相关属性不提供）。

结算后释放：`SUCCESS` 与 `RetryKind.NONE` 的条目不保留 `RetryMaterial`，因此不再引用 artifact 字节（第 19.5 节）。

### 10.7 `BatchExecutionResult`

```text
result_id       : str   32 位小写 hex；repr=False
preview_id      : str | None     被执行的 BatchPreview.preview_id；merge_retry 产物为 None
lineage         : BatchLineage
generation      : int >= 0
base_result_id  : str | None     重试轮结果：被重试的结果 id；主结果 / 合并结果：None
retry_scope     : frozenset[RetryKind] | None
library_root, output_policy, image_policy, batch_size
items           : tuple[ItemExecution, ...]
metadata_batch  : BatchResult
retention_budget_bytes : int          （E0-R2）lineage 固定的 B，从被执行的 preview 原样复制；合并结果从 previous 复制
retry_budget_bytes     : int | None   （E0-R2）重试轮结果：从重试 preview 原样复制；主结果 / 合并结果：None
```

（E0-R2）派生属性（`models.py` 中的纯 helper，不存储）：

* `retry_payload_bytes(material)` = `Σ len(req.content) for req in material.artifacts`（NFO、poster、fanart、thumb、
  每张 extrafanart 的 `ArtifactWriteRequest.content`）；
* `retained_retry_payload_bytes` = 全部 `retry_material is not None` 的条目的 `retry_payload_bytes` 之和。`SUCCESS`、
  `ABORTED`、`REJECTED` 以及其他 `RetryKind.NONE` 条目不持有 `RetryMaterial`，贡献 0；`METADATA_REFETCH` 条目不持有
  `RetryMaterial`，贡献 0。共享的 bytes 对象按引用重复计入（保守，不会少计）。

（E0-R2）结果保留不变量（`__post_init__` 强制，`OrchestrationContractError`）：

* `1 <= retention_budget_bytes <= MAX_RETAINED_ARTIFACT_BYTES_LIMIT`；
* 主结果与合并结果：`retry_budget_bytes is None` 且 `retained_retry_payload_bytes <= retention_budget_bytes`
  （**当前完整结果保留不变量**，第 19.6.10 节）；
* 重试轮结果：`0 <= retry_budget_bytes <= retention_budget_bytes` 且 `retained_retry_payload_bytes <= retry_budget_bytes`。

三种形态（互斥，`__post_init__` 强制）：

* **主结果**：`generation == 0`、`base_result_id is None`、`preview_id` 非空、items 覆盖 `0..batch_size-1`；
* **重试轮结果**：`base_result_id` 非空、`retry_scope` 非空、`preview_id` 非空、index 严格递增的子集、`generation >= 1`；
* **合并结果**：`generation >= 1`、`base_result_id is None`、`retry_scope is None`、`preview_id is None`、items 覆盖
  `0..batch_size-1`。

属性 `is_complete`（主结果或合并结果）、`summary`（第 28 节）、`outcome`（E0-R1，第 11.5 节；只读派生属性，
不存储，对三种形态都有定义：重试轮结果的 `outcome` 只描述该轮子集，合并结果与主结果描述整个 lineage 的当前状态）。

### 10.8 `CancellationToken`（`cancellation.py`）

```python
token = CancellationToken()
token.cancel()        # 线程安全、幂等、单向（不能复位）
token.cancelled       # bool
```

内部只持有一个 `threading.Event`。不是 asyncio 取消，不中断任何进行中的 syscall。

## 11. 状态体系与映射（冻结）

### 11.1 三套状态、三种语义，没有同名不同义的新体系

| 问题 | 使用的枚举 | 所属 |
|---|---|---|
| 这部影片的 metadata 聚合质量如何？ | `BatchItemStatus`（`SUCCESS` / `PARTIAL` / `FAILED`） | Phase 3（原样复用） |
| 这部影片的文件系统累计状态如何？ | `ExecutionStatus`（`SUCCESS` / `PARTIAL` / `FAILED`） | P4-C7（原样复用） |
| 这部影片在本批中处于哪个编排位置？ | `PreviewState`（`READY` / `BLOCKED` / `UNPREPARED`）、`ExecutionDisposition`（`EXECUTED` / `NOT_READY` / `NOT_SELECTED` / `CANCELLED` / `REJECTED` / `ABORTED`） | P4-C8（名称与前两者**不重叠**） |

P4-C8 **不**定义任何名为 `SUCCESS` / `PARTIAL` / `FAILED` 的新**条目级**枚举成员。（E0-R1）唯一的例外是**批级**的
`BatchOutcome`（第 11.5 节）：它不描述任何单个条目，只由条目的 `ExecutionStatus` 按冻结真值表确定地推导，因此不构成
第二套条目状态体系。汇总中的 `success` / `partial` / `failed`
计数**只**统计 `disposition is EXECUTED` 的条目按 `ExecutionStatus` 的分布（第 28 节），语义与 P4-C7 第 8 节完全一致。
metadata 的 `PARTIAL` 只以 `ItemWarning.METADATA_PARTIAL` 出现，永远不计入文件系统 `partial`。

### 11.2 与 v1.0 规格书批量状态的映射

规格书：`PENDING → RUNNING → SUCCESS | PARTIAL | FAILED`，失败 / 部分条目可单独 `RETRY`。

| 规格书状态 | P4-C8 表达 |
|---|---|
| `PENDING` | 执行开始后、准入之前的条目（瞬时，不物化到结果中；未准入即取消的条目最终为 `CANCELLED`） |
| `RUNNING` | 已准入、`execute_filesystem` 进行中的条目（瞬时，不物化） |
| `SUCCESS` | `EXECUTED` + `ExecutionStatus.SUCCESS` |
| `PARTIAL` | `EXECUTED` + `ExecutionStatus.PARTIAL`（携带 checkpoint） |
| `FAILED` | `EXECUTED` + `ExecutionStatus.FAILED`；以及未能执行的条目（`NOT_READY`、`REJECTED`、`ABORTED`）按 `issue.stage` / `issue.reason` 区分 |
| `RETRY` | `preview_retry` 按 `RetryKind` 选择子集（第 25 节） |
| 取消（实施总提示词 Phase 4：支持取消尚未开始的 item） | `CANCELLED` |

### 11.3 与 Phase 3 metadata 状态的映射

| Phase 3 `BatchItemResult` | P4-C8 |
|---|---|
| `SUCCESS`（带 `AggregationResult`） | 进入 planning；无 metadata 警告 |
| `PARTIAL`（带 `AggregationResult`） | 进入 planning（P4-C3 允许发布 `PARTIAL`）；`ItemWarning.METADATA_PARTIAL` |
| `FAILED` 且带 `AggregationResult`（聚合 `FAILED`） | `UNPREPARED`，`METADATA_UNAVAILABLE` |
| `FAILED` 且 `error_kind` 非空（`ENGINE_EXCEPTION` / `RESULT_CONTRACT_MISMATCH`） | `UNPREPARED`，`METADATA_ENGINE_FAILURE`（`detail = error_kind`，`error_type` 原样） |

### 11.4 不提供实时状态

P4-C8 v1.0 没有进度回调、订阅、事件流或可轮询的实时状态；结果只在操作结束时一次性返回。进度展示属于将来的 UI / CLI，
不在本合同内。（E0-R1）`PENDING` / `RUNNING` 仍只是运行时瞬时状态，永远不物化，也永远不是 `BatchOutcome`。

### 11.5 批级最终结果 `BatchExecutionResult.outcome`（E0-R1，冻结）

`outcome` 是 `BatchExecutionResult` 的只读派生属性（不存储字段，因此不可能与 `items` / `summary` 自相矛盾）。它**只**依据
`result.items` 与已冻结的条目语义（`disposition` 与 `ExecutionStatus`）计算；相同的 `items` 永远得到相同的 `outcome`，
调用方没有任何参数可以改变它。

**条目分类**（对每个条目恰好属于一类，互斥且全覆盖）：

| 条目 | 类别 |
|---|---|
| `EXECUTED` + `ExecutionStatus.SUCCESS` | `S`（已整理） |
| `EXECUTED` + `ExecutionStatus.PARTIAL` | `P`（部分文件系统进展，持有 checkpoint） |
| `EXECUTED` + `ExecutionStatus.FAILED` | `N`（无进展） |
| `NOT_READY`（preview `BLOCKED`） | `N` |
| `NOT_READY`（preview `UNPREPARED`） | `N` |
| `NOT_SELECTED` | `N` |
| `CANCELLED` | `N` |
| `REJECTED` | `N` |
| `ABORTED` | `N`（状态未知；永远不计为进展或成功） |

记 `total = len(items)`、`s = |S|`、`p = |P|`。

**推导算法**（按顺序，第一条命中即为结果；三条互斥且覆盖全部 `(total, s, p)`）：

```text
1  s == total                      -> SUCCESS      （包括 total == 0）
2  s + p >= 1                      -> PARTIAL      （此时必有 s < total）
3  否则（total >= 1 且 s == p == 0）-> FAILED
```

等价的汇总形式（S5 以恒等式测试强制）：`SUCCESS ⇔ summary.success == summary.total`；
`PARTIAL ⇔ summary.success + summary.partial >= 1 且 summary.success < summary.total`；
`FAILED ⇔ summary.total >= 1 且 summary.success + summary.partial == 0`。

**语义**：`SUCCESS` = 本结果中的每一个条目都已整理完成；`PARTIAL` = 至少一个条目已整理完成或已产生部分文件系统进展，但
不是全部完成；`FAILED` = 本结果中没有任何条目完成或产生文件系统进展。`FAILED` 描述的是“没有整理进展”，不是“发生了故障”
（例如全部未选中也是 `FAILED`）。

**逐项结论**：

| 情形 | `outcome` |
|---|---|
| 全部 `EXECUTED + SUCCESS` | `SUCCESS` |
| 空结果（`total == 0`：空批次的主结果、空重试轮结果） | `SUCCESS`（没有任何未完成的条目；与 `s == total` 一致） |
| `SUCCESS` 与任何非 `SUCCESS` 条目混合 | `PARTIAL` |
| 至少一个 `EXECUTED + PARTIAL`（无论其他条目如何） | `PARTIAL`（`p >= 1` 时必有 `s < total`，规则 1 不可能命中；没有例外） |
| 全部 `EXECUTED + PARTIAL` | `PARTIAL` |
| 全部 `EXECUTED + FAILED` | `FAILED` |
| 全部 `NOT_READY / BLOCKED` | `FAILED` |
| 全部 `NOT_READY / UNPREPARED` | `FAILED` |
| 全部 `NOT_SELECTED` | `FAILED` |
| 全部 `CANCELLED` | `FAILED` |
| 全部 `REJECTED` | `FAILED` |
| 全部 `ABORTED` | `FAILED` |
| `ABORTED` 与 `SUCCESS` 混合 | `PARTIAL`（`ABORTED` 永不计为成功） |
| 任意 `N` 类条目的组合（无 `S`、无 `P`） | `FAILED` |

最低语义要求的满足：(A) 全部 `SUCCESS` -> `SUCCESS`；(B) `SUCCESS` 与非 `SUCCESS` 混合时 `s < total`，不可能是
`SUCCESS`；(C) 存在文件系统 `PARTIAL` 时 `s < total`，不可能是 `SUCCESS`；(D)(E) `ABORTED` 与 `PARTIAL` 都不属于 `S`；
(F) `outcome` 是 `items` 的纯函数，没有参数。

重试轮结果的 `outcome` 只描述该轮的子集；合并结果的 `outcome` 描述整个 lineage 的当前累计状态。`BatchPreview` 没有
`outcome`（它不是最终结果）。

## 12. Item 身份（冻结）

### 12.1 index

* 条目身份是 `index`：该条目在 `preview(items)` 输入快照中的位置 `0..N-1`。它在整个 lineage 的所有 preview、执行、重试、
  合并中保持不变。
* 从不以番号、源路径、`DiscoveredMediaItem.index`（它是 discovery 的计数，多个 `DiscoveryResult` 拼接时会重复）或目标路径
  标识条目。同一个 `DiscoveredMediaItem` 对象出现两次就是两个条目（随后按第 14 节作为冲突被阻断）。
* 不存在 `dict[number, ...]` / `dict[path, ...]` 形式的条目身份；冲突分组中使用的 key 只用于分组，输出一律按 index 排序。

### 12.2 lineage 与 generation

* lineage = 主 preview 中 `BatchScheduler.run(numbers)` 返回的 `metadata_batch.lineage`（即使 `numbers` 为空，
  Phase 3 仍返回一个带新 lineage 的空 `BatchResult`）。P4-C8 不创建自己的 lineage 类型或令牌。
* P4-C8 generation：主 preview / 主结果为 `0`；每次 `preview_retry` 得到 `previous.generation + 1`；合并结果取重试轮的
  generation。它与 Phase 3 metadata 账本自己的 generation 相互独立（metadata generation 只在 `METADATA_REFETCH` 执行时增加）。
* `preview_id`、`result_id` 是 `secrets.token_hex(16)`：进程内的一次性消费键（第 18.1、25.4、26 节），不是持久化 id。
* 同一条目的多次重试形成链：generation 0 → 1 → 2 → …；每个 `ItemExecution.generation` 表明它由哪一轮产生。

### 12.3 重试间的身份校验

`merge_retry` 与 `preview_retry` 要求同一 index 上的 `media_item` 是**同一对象**（`is`），`canonical_number` 相等；
否则 `OrchestrationRetryError` / `OrchestrationIntegrityError`。

## 13. 批次顺序（冻结）

* 输入顺序即批次顺序；输出 `items` 永远按 index 升序（主 preview / 主结果 / 合并结果为 `0..N-1` 连续；重试 preview /
  重试轮结果为严格递增子集）。
* metadata 提交顺序：未被 Phase A 排除的已识别条目，按 index 升序构成 `numbers`；`metadata_position` 即其在 `numbers`
  中的位置。
* 图片阶段、执行阶段的**准入**顺序都是 index 升序；结果写入按 index 预分配的槽位。输出与线程 / 任务完成顺序无关。
* 重试集合按 index 升序；`warnings` 按 `ItemWarning` 声明顺序；`conflict_with` 升序；汇总中的阶段计数按
  `OrchestrationStage` 声明顺序。
* 任何地方都不以 `set` / `dict` 的迭代顺序或 hash 决定输出顺序。

## 14. 番号识别与批内冲突（冻结）

### 14.1 番号识别

* 对每个条目：`normalize_fc2_number(os.path.basename(media_item.source_path))`（Phase 1 冻结语法：大小写不敏感、
  `FC2[-_]*(PPV[-_]*)?` + 5..8 位 ASCII 数字、不与字母数字粘连、字符串中**第一个**匹配胜出）。
* 只看文件 **basename**（含扩展名）。从不读取父目录名、`relative_path` 的其他组件、文件内容或 metadata 来“猜”番号；
  不做第二个解析器，不修复脏输入。
* `NOT_FC2` -> `UNPREPARED`，`ItemIssue(NUMBER_RECOGNITION, NUMBER_NOT_RECOGNIZED)`，`canonical_number = None`，
  不参与冲突分组，不提交 metadata。

### 14.2 Phase A 冲突（metadata 之前，词法）

在已识别的条目之间：

1. **同源**：按源路径 key 分组。Windows（`os.name == "nt"`）上 key = `source_path.casefold()`，POSIX 上为精确字符串。
2. **同目标**：按 `canonical_number` 分组（目标目录恒为 `join(library_root, canonical_number)`，规范番号相同 ⇔ 目标相同）。

任何大小 ≥ 2 的组中的**全部**成员：`BLOCKED`，`ItemIssue(BATCH_CONFLICT, DUPLICATE_SOURCE_IN_BATCH)`（同源优先）
或 `DUPLICATE_TARGET_IN_BATCH`；`conflict_with` = 该条目在两类组中的全部对端 index 的升序并集；**不**提交 metadata，
不访问网络，不 preflight。

### 14.3 Phase B 冲突（preflight 之后，身份）

在同一 preview（主 preview 或重试 preview 的子集）中所有 `preflight is not None` 的条目之间：

1. **同源身份**：`preflight.source_identity` 非空时，按 `(device, inode)` 分组（捕获 hardlink、不同拼写、经 junction /
   不同根重复发现的同一文件）；
2. **同目标**：按 `plan.target_directory.absolute_path`（Windows `casefold`，POSIX 精确）分组（纵深防御；正常情况下已被
   Phase A 捕获）。

任何大小 ≥ 2 的组中的全部成员改为 `BLOCKED` / `BATCH_CONFLICT`（原因优先级：同源 > 同目标），保留其 `preflight`
（不可执行），`conflict_with` 取两类组对端的升序并集。Phase B 覆盖原先的 `READY` 或 `PREFLIGHT_BLOCKED`
（原 preflight 的 blockers 仍可通过 `blockers` 属性查看）。

### 14.4 冻结裁决：冲突组全部阻断，不选“胜者”

P4-C8 从不在冲突组中挑选一个条目执行（不按 index、大小、时间、路径选择）：任何选择都是在替用户决定哪一份文件成为库中
副本，而 fail closed 的默认是全部不执行。用户解决冲突的方式是用不含重复项的条目子集重新 `preview`。冲突条目
`RetryKind.NONE`。这也是 P4-C7 第 30 节交给 P4-C8 的“批量去重”职责在 v1.0 的全部含义：同一次编排内，**同一源、同一目标
永远不会被派发两次**。

## 15. Preview 语义（冻结）

### 15.1 操作顺序（`preview(items)`）

```text
1  busy-first（第 7.3 节）
2  输入校验与快照（第 8 节）
3  番号识别（14.1），Phase A 冲突（14.2）
4  metadata：metadata_batch = await scheduler.run(numbers)       Phase 3（M 个条目并发，致命 / 取消原样传播）
5  逐条（index 升序，同步）：plan -> publication -> NFO           （stages.py）
     E0-R1：每个 NFO 渲染成功后立即计入保留预算（第 19.6.3 节）；超限 -> OrchestrationResourceLimitError，整个 preview fail closed
6  图片：对第 5 步成功的条目，min(K, n) 个 asyncio worker，每条 await acquire_images(record, image_client, policy=image_policy)
     E0-R1：每条在准入前按确定性预约规则取得预约（第 19.6.4 节）；无法预约 -> OrchestrationResourceLimitError
7  逐条（index 升序，同步）：manifest -> preflight_execution(plan, artifacts)
8  Phase B 冲突（14.3）
9  组装 BatchPreview（generation 0）
```

* 第 4 步总是调用（即使 `numbers` 为空），以获得 lineage。
* 第 5、7 步在调用协程所在线程中同步执行（不创建线程）：它们是纯计算或只读 `lstat`，preflight 的 FRESH 模式只做少量
  `lstat`。第 7 步紧接在全部图片完成之后执行，使 preflight 快照尽量新鲜。
* 一个条目在第一个失败阶段停止，后续阶段不再对它执行。

### 15.2 各阶段调用（逐条）

| 阶段 | 调用 | 成功产物 | 普通 `Exception` -> `ItemIssue` |
|---|---|---|---|
| PLANNING | `build_organize_plan(media_item, canonical_number, aggregation_result.metadata, library_root, policy=output_policy)` | `OrganizePlan` | `PLANNING_REJECTED`（`error_type` = 异常类名） |
| PUBLICATION | `prepare_publication(plan, aggregation_result)` | `PublicationRecord` | `PUBLICATION_REJECTED` |
| NFO_RENDER | `render_movie_nfo(record)` | `str` | `NFO_RENDER_FAILED` |
| IMAGE_ACQUISITION | `await acquire_images(record, image_client, policy=image_policy)` | `ImageAcquisitionResult` | `IMAGE_ACQUISITION_ERROR` |
| MANIFEST | `build_artifact_requests(plan, nfo_text, images)` | `tuple[ArtifactWriteRequest, ...]` | `MANIFEST_REJECTED`（`ArtifactMappingError` 时 `detail = .reason`） |
| PREFLIGHT | `preflight_execution(plan, artifacts)` | `ExecutionPreflight` | `PREFLIGHT_REJECTED`（`PlanGraphError` / `ArtifactManifestError` 时 `detail = .reason`） |

* `preflight.ready is False` -> `BLOCKED`，`ItemIssue(PREFLIGHT, PREFLIGHT_BLOCKED)`（全部阻断原因在 `preflight.blockers`，
  P4-C7 已按固定顺序列出全部可检测原因）。
* `image_failures = images.failures`；图片字节只存在于 manifest（经 `preflight.artifacts`）中，不另存
  `ImageAcquisitionResult`。
* NFO 在图片之前渲染：NFO 失败的条目不访问图片网络。

### 15.3 library_root 的语义校验

`library_root` 的“完全限定绝对路径”语义校验由 P4-C2 `build_organize_plan` 逐条完成（P4-C2 §11a；其 helper 不是公开 API，
P4-C8 不复制它）。非法根目录使每个到达 PLANNING 的条目都成为 `PLANNING_REJECTED`（`error_type = "InvalidLibraryRootError"`）；
根目录不存在 / 是链接等文件系统状态由 P4-C7 preflight 以 blocker 报告。构造时 P4-C8 只校验 `type(library_root) is str`
且非空。已知代价：非法根目录会在 metadata / 图片网络阶段之后才暴露（第 37 节已知局限）。

### 15.4 Preview 的最小可确认信息（冻结）

每个 `ItemPreview` 至少让调用方（未来 UI / CLI）看出：条目身份（`index`）、规范番号、源媒体（`source_path`、
`source_size`）、目标目录、最终媒体路径、NFO 目标、poster / fanart / thumb 目标（缺失时为 `None`）、extrafanart 目录与数量、
计划中的文件系统操作（`planned_units` / `completed_units` / `skipped_steps`）、preflight 是否 ready、阻断原因（`blockers` 或
`issue`）、预测传输模式、警告与批内冲突（`warnings` / `conflict_with`）、是否可执行（`executable`）、失败阶段
（`issue.stage`）。这些全部是第 10.3 节的字段或派生属性；preview 永远不会只返回一个布尔值。

## 16. Preview 零修改规则（冻结）

* `preview` 与 `preview_retry` **绝对不修改文件系统**：不创建目录、不移动媒体、不写 NFO、不写图片、不创建临时文件、
  不删除任何东西。
* 它们只调用只读的下层 API：`normalize_fc2_number`、`BatchScheduler.run` / `retry_failed`（网络 + 内存）、
  `build_organize_plan`、`prepare_publication`、`render_movie_nfo`、`acquire_images`（网络 + 内存）、
  `build_artifact_requests`、`apply_retry`、`preflight_execution`（P4-C7 冻结：只 `lstat` / 只读 `open` + `read` /
  `listdir`）。
* 结构保证（AST，第 34 节）：`preview.py`、`stages.py`、`retry.py`、`recognition.py`、`models.py` 中不出现
  `execute_filesystem`、`materialize_artifact`、`materialize_atomic_bytes` 的名称；`execute_filesystem` 只出现在
  `execute.py`；P4-C8 任何模块都不调用 `os` 的修改性函数、`open`、`shutil`。
* 行为证明（测试，第 35 节）：在拦截全部修改性 API（`os.mkdir`、`makedirs`、`rename`、`replace`、`remove`、`unlink`、
  `rmdir`、`link`、`symlink`、`truncate`、`chmod`、`utime`、带写标志的 `os.open`、写模式 `open`、`shutil` 的
  copy / move / rmtree、`execute_filesystem`、`materialize_artifact`、`materialize_atomic_bytes`）并附正向对照的条件下
  运行 `preview` 与 `preview_retry`，命中次数为 **0**；前后目录树快照（每个条目的相对路径、类型、字节 SHA-256、
  `st_ino`、`st_mtime_ns`）逐项相等。

## 17. 与 preflight 的关系：preview 与 execute（冻结）

### 17.1 选择：execute 消费 preview 中保存的 `ExecutionPreflight`（方案 A）

`execute(preview)` 对每个被选中的 READY 条目，把 **preview 中保存的那个 `ExecutionPreflight` 对象**原样交给
`execute_filesystem`。P4-C8 在执行前**不**重新生成 preflight，也不重新获取 metadata / 图片 / 重新渲染 NFO / 重新映射 manifest。

理由（全部来自已冻结的 P4-C7 合同）：

1. **用户看到的就是被执行的**：preview 的全部显示属性都派生自该 preflight 的 `plan` 与 `artifacts`；P4-C7 的 HMAC 封印
   （§15.3）覆盖 preflight 的全部字段，`execute_filesystem` 在任何文件系统访问之前重新验证封印、重新验证 plan / manifest
   结构并重新计算两个指纹（§15.5）。任何在 preview 之后对 plan / manifest 对象图的改写都会以
   `PreflightIntegrityError(SEAL_INVALID | FINGERPRINT_MISMATCH)` 被拒绝，零文件系统访问。因此“preview A、用户看到 A、
   execute 执行 B”在 plan / manifest 层面不可能发生。
2. **文件系统漂移由执行时重新校验捕获**：`execute_filesystem` 在修改之前做整体只读重新校验（library root 身份、源身份、
   FRESH 时目标目录不存在 / RESUME 时身份与列举），并在每个修改性 syscall 之前再次重新校验（P4-C7 §13、§14.3、§18-§25）。
   preview 之后发生的漂移成为类型化的 `FAILED` / `PARTIAL`（例如 `TARGET_CONFLICT`、`SOURCE_CHANGED`、
   `LIBRARY_ROOT_CHANGED`），绝不会变成“执行了另一件事”。
3. **一次性消费**：`execute_filesystem` 原子地登记 `preflight_id`（resume 时连同 `checkpoint_id`），同一 preflight 不能被
   执行两次（§15.4）。P4-C8 另在批级登记 `preview_id`（第 18.1 节）。
4. 方案 B（执行前重新 preflight）会生成一个用户从未看过的新 preflight，并丢弃 P4-C7 为 preview 设计的“preflight 不消费、
   可多次预览”语义（§15.4）的意义；方案 A 在不增加任何新机制的前提下同时满足“所见即所执行”与“执行时重新校验”。

### 17.2 preview 陈旧

P4-C8 不为 preview 设置 TTL，也不读取时钟。任意久之后执行的 preview 仍按第 17.1 节执行：漂移由 P4-C7 执行时重新校验
以类型化失败报告。想要最新的阻断视图，调用方重新 `preview`（或对已执行结果 `preview_retry`）。

### 17.3 允许的差异（冻结，诚实声明）

* `predicted_transfer_mode` 是预测值；实际传输模式以 `ExecutionResult.transfer_mode` 为准（P4-C7 §17：U1 之后按新目录
  `st_dev` 重新判定；同卷原语 `EXDEV` 时回退跨卷一次）。
* preview 中 `ready` 的条目在执行时可能因漂移而 `FAILED` / `PARTIAL`；preview 中 `BLOCKED` 的条目永远不会被执行。

## 18. Execution 语义（`execute(preview, *, selection=None, cancel=None)`，冻结）

### 18.1 执行前检查顺序（冻结，任何一步失败都不执行任何条目）

```text
1  busy-first
2  type(preview) is BatchPreview                                    否则 OrchestrationInputError
3  preview 对象图完整性重新检查                                     否则 OrchestrationIntegrityError
     对每个条目重跑 ItemPreview 不变量；READY 条目：type(preflight) is ExecutionPreflight、preflight.ready is True、
     preflight.plan is item.plan、plan.source_path == media_item.source_path、plan.canonical_number == canonical_number；
     BatchPreview 不变量
4  preview.library_root / output_policy / image_policy 与本 orchestrator 相等，且（E0-R2）
   preview.retention_budget_bytes == 本 orchestrator 的 config.max_retained_artifact_bytes    否则 OrchestrationInputError
5  cancel：None 或严格 CancellationToken                             否则 OrchestrationInputError
6  selection：None（= 全部 READY 条目）或严格 tuple[int, ...]：严格 int、严格递增、每个都是本 preview 中某个 READY 条目的 index
                                                                    否则 OrchestrationInputError（不执行任何条目）
7  原子登记 preview_id（进程内一次性）                              已登记 -> OrchestrationConsumedError
8  有界执行（18.2）
9  组装 BatchExecutionResult
```

* `selection == ()` 合法：不执行任何条目，全部 READY 条目为 `NOT_SELECTED`（可用于“未执行即重试”，第 25.5 节）。
* 第 7 步之后 preview 被消费，即使之后发生致命异常；这与 P4-C7 “开始即消费”一致。

### 18.2 逐条执行与 disposition

对准入的每个条目，恰好一次：

```python
result = execute_filesystem(item.preflight)
```

| 结果 | disposition | `issue` | `retry_material` |
|---|---|---|---|
| 返回严格 `ExecutionResult` 且 `result.preflight_id == item.preflight.preflight_id` | `EXECUTED` | 按 `ExecutionStatus`（第 10.6 节表） | 按第 25.1 节 |
| 抛出 `type(exc)` 恰为 `ExecutionInputError`、`PreflightIntegrityError`、`PreflightNotReadyError`、`CheckpointError`、`PlanGraphError`、`ArtifactManifestError` | `REJECTED` | `EXECUTION_REJECTED`（`error_type`、可得时 `detail = .reason`） | `None` |
| 抛出其他任何普通 `Exception`（包括 `ExecutionModelError`、P4-C7 私有的所有权完整性错误、`RuntimeError`、`MemoryError`、`OSError`），或返回值不是严格 `ExecutionResult` / `preflight_id` 不符 | `ABORTED` | `EXECUTION_ABORTED`（`error_type`） | `None` |
| 非 `Exception` 的 `BaseException` | 致命（第 20.3 节） | — | — |

`ABORTED` 的 `error_type`：异常时为异常类名；返回值不是严格 `ExecutionResult` 时为该返回值的类名；`preflight_id` 不符时为
`"ExecutionResult"`（后两种只可能来自违反合同的测试替身，仍 fail closed）。

理由：P4-C7 §15.5 冻结了“严格类型 -> 封印 -> ready -> 结构与指纹 -> 消费登记 -> 文件系统”的顺序，上表 `REJECTED` 行的
六种类型只可能在第一次文件系统访问之前抛出，因此 `REJECTED` 表示“零文件系统访问”。其余异常可能发生在 effect 之后
（例如结果组装、所有权转换失败），P4-C7 §29 规定此时不返回结果、不签发 checkpoint，文件系统状态对 P4-C8 未知，因此是
`ABORTED`，永不自动重试（第 25.1 节）。

### 18.3 未执行的条目

* preview 中 `BLOCKED` / `UNPREPARED` -> `NOT_READY`（`issue` 为 preview 的 issue）；
* READY 但不在 selection 中 -> `NOT_SELECTED`；
* 被选中但取消请求先于准入 -> `CANCELLED`（第 27 节）。

## 19. 并发（冻结）

### 19.1 三个预算

| 旋钮 | 作用域 | 限制的对象 |
|---|---|---|
| `OrchestrationConfig.metadata.max_in_flight_items = M`（Phase 3，默认 4，1..64） | 一次 preview / preview_retry 的 metadata 阶段 | 并发的 `engine.aggregate` 调用数（Phase 3 有界准入；每次调用内部另有 C1 的 S 与可选的 C5 governor） |
| `OrchestrationConfig.image_in_flight_items = K`（默认 4，1..16） | 一次 preview / preview_retry 的图片阶段 | 并发的 `acquire_images` 调用数；每次调用内部严格串行（P4-C5 §14.3），因此图片 HTTP 请求峰值 ≤ K；（E0-R1）实际并发还受第 19.6.4 节预约准入约束（可能小于 K，从不大于 K） |
| `OrchestrationConfig.filesystem_workers = W`（默认 1，1..8） | 一次 execute | 并发的 `execute_filesystem` 调用数 |

* 阶段在一次操作内顺序进行（metadata 全部完成 -> 同步阶段 -> 图片全部完成 -> 同步阶段），因此三个预算不同时生效，不共享
  limiter；orchestrator 的忙碌守卫保证同一 orchestrator 的两个操作不会重叠。多个 orchestrator 的预算相加（与 Phase 3 相同）。
  跨 orchestrator 的 host 级网络限制由调用方注入的 engine 的 C5 governor 负责（图片没有 host 级 governor，P4-C5 未提供）。
* preview 的 preflight 阶段不使用线程（第 15.1 节）；execute 的 `W` 只约束执行。

### 19.2 图片 worker（asyncio）

与 Phase 3 §5 相同的有界准入模型：创建 `min(K, n)` 个 worker 任务（从不按条目创建任务），worker 从共享游标取下一个位置
（index 升序），在 worker 中直接 `await acquire_images(...)`，结果写入预分配槽位。准入前检查运行本地的 `stopping` 标志与
驱动任务的新取消请求（Phase 3 §5 (a)(b)）。存活任务数 `O(K)`。

### 19.3 执行 worker（线程）

* `W_eff = min(W, 被选中且 READY 的条目数)`。`W_eff <= 1` 时在调用线程中内联执行（不创建线程）。否则创建恰好 `W_eff` 个
  非 daemon 的 `threading.Thread`，从一个由 `threading.Lock` 保护的共享游标按 index 升序取下一个条目；从不为每个条目创建线程，
  从不使用无界线程池。
* 每次准入之前（在锁内）检查：`stopping`（已发生致命异常）或 `cancel.cancelled` -> 不再准入。
* 所有线程在返回或传播之前都被 `join`；没有线程活得比 `execute` 调用更久。
* 结果写入按位置预分配的槽位；输出与完成顺序无关。

### 19.4 与 P4-C7 竞争安全的关系

* 同一次执行中不同条目的目标目录互不相同、源身份互不相同（第 14 节 Phase A / B），因此并发执行不会形成 P4-C7 意义上的
  同目标或同源竞争；P4-C7 的独占 `mkdir`、进程内源所有权占用、一次性消费仍是最终的硬保证（例如另一个 orchestrator 在同一
  进程内并发执行重叠的条目时）。
* P4-C8 不持有、不读取、不操作 P4-C7 的任何登记表或锁。

### 19.5 内存

* preview 持有每个可执行 / 被阻断条目的 manifest（NFO 字节 + 图片字节，经 `preflight.artifacts`）。（E0-R1）这部分
  保留载荷受第 19.6 节的批级硬预算约束；条目数受 `MAX_BATCH_ITEMS` 约束。P4-C8 不把图片落盘缓存（那是持久化）。
* `BatchExecutionResult` 只为需要重试的条目保留 `RetryMaterial`；`SUCCESS` 与不可重试条目不再引用 artifact 字节。调用方在
  execute 之后释放对 `BatchPreview` 的引用即可回收已结算条目的字节。

### 19.6 资源硬限制：条目数与保留 artifact 字节（E0-R1，冻结）

有界的 worker 数不等于有界的内存。P4-C8 的硬资源合同针对两个维度，二者同时成立：**条目数**与**保留 artifact 载荷字节**。
CPython 对象头、tuple / dataclass 开销不做精确计量；由于条目数有硬上限、每个条目的模型对象数有限（extrafanart 数量受字节
预算约束，因为每张 JPEG 至少若干字节），这些开销也因此有限。metadata 模型（`AggregationResult` 等）的大小由条目数与
Phase 2 / 3 transport 的响应大小上限约束，不计入本节的字节预算。

#### 19.6.1 条目数硬上限

* `MAX_BATCH_ITEMS = 2000`（常量，不可配置；`>= 500`，正式支持 v1.0 的 500-item 要求）。
* （E0-R2）条目数门在 P4-C8 创建任何完整快照**之前**生效，由 `recognition.bounded_snapshot(items)`（唯一实现位置）按以下
  **有界快照算法**完成（`preview` 的第 8 节顺序中，它紧接在 busy-first 与容器种类校验之后）：

```text
1  （已完成）busy-first；容器种类校验：必须是 collections.abc.Sequence，且不是 str / bytes / bytearray / memoryview、
   任何 Set、任何 Mapping、生成器 / 迭代器
2  it = iter(items)                                   只调用一次；从不调用 len(items) / items.__len__
3  collected = []；重复至多 MAX_BATCH_ITEMS 次：
       取 next(it)；StopIteration -> 转到第 5 步；否则 collected.append(元素)
4  溢出探测：再调用恰好一次 next(it)
       StopIteration          -> 转到第 5 步
       得到第 MAX_BATCH_ITEMS + 1 个元素 -> 立即丢弃该引用，抛出 OrchestrationResourceLimitError(BATCH_ITEM_LIMIT)，
                                 不再调用 next(it)
5  snapshot = tuple(collected)（最多 MAX_BATCH_ITEMS 个元素；这是唯一的不可变快照），随后释放 collected
6  之后才做逐元素严格类型校验（第 8 节）与其余校验
```

  * 迭代异常：`iter()` / `next()` 抛出的普通 `Exception`（`StopIteration` 除外）-> `OrchestrationInputError`
    （固定消息，只含异常类名，不链接）；非 `Exception` 的 `BaseException` 原样传播。
  * **不信任 `__len__`**：资源正确性只由第 2-4 步的有界迭代保证，不依赖调用方 `__len__` 的诚实性；P4-C8 完全不调用
    `len(items)`（没有非规范的 `len` 预判），因此 `__len__` 报小但实际可迭代出超过 `MAX_BATCH_ITEMS` 个元素的“说谎序列”
    同样得到 `BATCH_ITEM_LIMIT`，`__len__` 报大但实际很短的序列按实际元素数处理。
  * **P4-C8 自身分配上界**：P4-C8 为输入最多同时持有 `MAX_BATCH_ITEMS` 个已收集引用（`collected`；第 5 步转换期间
    `collected` 与 `snapshot` 两个各至多 `MAX_BATCH_ITEMS` 个指针的数组短暂并存）加 1 个溢出探测临时引用。对 2001、10000、
    1000000 个元素的输入，P4-C8 至多读取 `MAX_BATCH_ITEMS + 1` 个元素，从不先复制完整输入再拒绝。调用方在调用前自己持有的
    超大容器不属于 P4-C8 的额外分配。
  * 零网络、零文件系统、零 engine / 图片 client 调用；`== MAX_BATCH_ITEMS` 合法。
* 一个 lineage 的 `batch_size` 在主 preview 中确定，之后的重试 / 合并只处理其子集，因此整个 lineage 的条目数都
  `<= MAX_BATCH_ITEMS`。

#### 19.6.2 保留预算：计量什么

* 预算 `B = config.max_retained_artifact_bytes`（默认 `DEFAULT_MAX_RETAINED_ARTIFACT_BYTES = 2 GiB`，范围
  `1..MAX_RETAINED_ARTIFACT_BYTES_LIMIT = 16 GiB`）。
* （E0-R2）**lineage 固定预算**：主 preview 把当时的 `config.max_retained_artifact_bytes` 记为不可变的
  `BatchPreview.retention_budget_bytes = B`；此后该 lineage 的每个执行结果、重试 preview、重试轮结果、合并结果都原样携带
  同一个 `B`（第 10.4、10.7 节），从不重新读取、放大或缩小。`execute`、`preview_retry` 要求执行它们的 orchestrator 的
  `config.max_retained_artifact_bytes` 与 `B` 严格相等，否则 `OrchestrationInputError`（第 18.1、25.4 节；跨 orchestrator
  重试时不静默采用新 orchestrator 的预算；M / K / W 的既有冻结语义不变）；`merge_retry` 要求 `previous` 与 `retry` 的 `B`
  相等（第 26 节）。
* 预算作用域：**一次** `preview` 或 `preview_retry` 调用各有一个私有账本（位于 `preview.py`，调用结束即丢弃；没有模块级
  状态）。主 preview 的账本上限为 `B`；`preview_retry` 的账本上限为 `available_retry_budget = B - base_retained`
  （第 19.6.7 节），而不是重新获得完整的 `B`。下文 19.6.3-19.6.4 节中的 `B` 在 `preview_retry` 中一律读作该可用额度。
* 账本 `L = charged + reserved`：
  * `charged`：已计入、从不在调用内减少的字节；
  * `reserved`：进行中图片调用的预约额。
* 计量对象（覆盖 P4-C8 为后续 execution 持续保留的全部 artifact 载荷）：NFO 的 UTF-8 字节（第 19.6.3 节）、poster /
  fanart / thumb / 每张 extrafanart 的图片字节（第 19.6.4 节），以及 `preview_retry` 中被带入新 preview 的保留材料的全部
  manifest 字节（第 19.6.7 节）。
* 不变量：任何时刻 `L <= B`；preview 返回时，其全部条目 `preflight.artifacts` 的 `len(content)` 之和（即实际保留载荷）
  `<= charged <= B`。

#### 19.6.3 NFO 计量

* 第 15.1 节第 5 步中，每个条目的 NFO 渲染成功后**立即**计入：`charged += 4 * len(nfo_text)`（UTF-8 每个码点最多 4 字节，
  因此它是该 NFO 最终编码字节数的确定上界；不需要在此处编码，也不会因编码错误而改变计量）。
* 计入后若 `charged + reserved > B` -> `OrchestrationResourceLimitError(RETAINED_BYTES_LIMIT)`：此时图片阶段尚未开始，
  不会发出任何图片请求。
* NFO 计量按 index 升序进行，因此是否超限、在哪个 index 超限是确定的。

#### 19.6.4 图片预约与准入（确定性）

* 单条预约额 `R = image_policy.max_total_bytes`；构造时已保证 `R <= MAX_ITEM_IMAGE_BYTES = 64 MiB`（第 7.2 节；等于 P4-C5
  的默认值）。P4-C5 §14.7 保证 `acquire_images` 返回的 `total_bytes <= R`。
* 准入严格按 index 升序、经过一个串行化的准入门（`asyncio.Condition`）：下一个待准入的图片条目 `j` 被准入，当且仅当
  `charged + reserved + R <= B`；准入时 `reserved += R`。游标只在准入成功后前进，任何 worker 都不能越过 `j` 准入更靠后的条目。
* 不满足时：
  * 若仍有进行中的图片调用（`reserved > 0`），准入门等待，直到某个调用完成（完成会使 `reserved` 减少、`charged` 最多增加同量，
    `L` 不增），然后重新检查；
  * 若没有进行中的调用（`reserved == 0`）仍不满足 -> `OrchestrationResourceLimitError(RETAINED_BYTES_LIMIT)`。
    准入门从不等待一个不可能再下降的账本。
* 条目 `j` 的调用完成时：`reserved -= R`；
  * 正常返回且 `images.total_bytes <= R`：`charged += images.total_bytes`（预约转为实际保留，未用部分释放）；
  * `acquire_images` 抛出普通 `Exception`：`charged` 不变（`IMAGE_ACQUISITION_ERROR`，字节不保留）；
  * 返回的 `total_bytes > R`（违反 P4-C5 合同，只可能来自替身）：`charged` 不变，该条目为 `UNPREPARED` /
    `IMAGE_ACQUISITION_ERROR`（`error_type = "ImageAcquisitionResult"`），其图片字节不进入 manifest。
* 确定性证明：设 `A_nfo` 为全部 NFO 计量之和（图片阶段开始前已确定）、`a_i` 为条目 `i` 的实际计入字节（由脚本化 / 下层确定的
  响应决定）。条目 `j` 最终被准入 ⇔ `A_nfo + Σ_{i<j} a_i + R <= B`：若在他人仍在进行时已满足（预约额 `>=` 实际），则所有
  更早条目完成后仍满足；若不满足，则等待到所有更早条目完成（更靠后的条目尚未准入），此时检查的恰好是该式。因此失败与否、
  在哪个 index 失败，与完成顺序和 K 无关。

#### 19.6.5 manifest 与 preflight 阶段

第 15.1 节第 7 步不再新增计量：manifest 中的 NFO 字节 `<=` 已计入的 `4 * len(nfo_text)`，图片字节就是已计入的
`images.total_bytes` 的同一批对象。在 manifest / preflight 阶段失败的条目丢弃其载荷，但计量不回退（保守）。

#### 19.6.6 超限行为（冻结）

| 触发 | 检查时机 | 行为 |
|---|---|---|
| 输入可迭代出第 `MAX_BATCH_ITEMS + 1` 个元素（E0-R2：有界快照的溢出探测） | `preview` 输入校验（第 8 节、第 19.6.1 节），零网络 / 零文件系统 | `OrchestrationResourceLimitError(BATCH_ITEM_LIMIT)` |
| `image_policy.max_total_bytes > MAX_ITEM_IMAGE_BYTES` | `BatchOrchestrator` 构造（第 7.2 节） | `OrchestrationConfigError` |
| `max_retained_artifact_bytes` 越界 / 类型错误 | `OrchestrationConfig` 构造（第 9 节） | `OrchestrationConfigError` |
| NFO 计量超预算 | 第 5 步，图片请求之前 | `OrchestrationResourceLimitError(RETAINED_BYTES_LIMIT)` |
| 图片预约无法满足且无进行中调用 | 第 6 步准入门 | 停止准入，取消并 await 全部图片 worker，然后抛出 `OrchestrationResourceLimitError(RETAINED_BYTES_LIMIT)` |
| `preview_retry` 的保留材料或新载荷计量超过 `available_retry_budget`（E0-R2） | 第 25.4 节第 7a 步及其后的 NFO / 图片计量 | `OrchestrationResourceLimitError(RETAINED_BYTES_LIMIT)` |
| `available_retry_budget < 0`（E0-R2；只可能来自被篡改的 previous） | 第 25.4 节第 7a 步 | `OrchestrationIntegrityError` |
| orchestrator 预算与 lineage `B` 不相等（E0-R2） | `execute` 第 18.1 节第 4 步 / `preview_retry` 第 25.4 节第 4 步 | `OrchestrationInputError` |
| `merge_retry` 预算不一致或合并后保留载荷 `> B`（E0-R2，纵深防御） | 第 26 节第 9a、9b 步，登记之前 | `OrchestrationRetryError` / `OrchestrationIntegrityError`，不登记 `retry.result_id` |

共同规则：

* 整个 `preview` / `preview_retry` 调用 fail closed，**不返回任何部分 `BatchPreview`**；资源耗尽是批级调用约束，不是某一部
  影片的业务失败，因此不映射为任何 `ItemIssue`，不影响条目顺序、重试、汇总与 `outcome` 的既有语义（它们只定义在成功返回的
  模型上）。
* 零文件系统修改（这两个操作只读，第 16 节）。`preview_retry` 超限时 `previous` 不被登记为已重试（登记在最后，第 25.4 节），
  不消费任何 checkpoint（preflight 不消费，P4-C7 §15.4），不产生任何部分重试 preview；调用方可以改变重试范围（例如先执行 /
  结算其他持有保留材料的条目以降低 `base_retained`）后再次重试。（E0-R2）lineage 的 `B` 固定，不能通过换用更大预算的
  orchestrator 绕过。
* orchestrator 在 `finally` 中恢复空闲；错误不链接、不含路径 / URL / secret。
* 它是普通 `Exception`，不是致命控制流：调用方可以拆分批次或调整配置后重试。

#### 19.6.7 `preview_retry` 的计量

（E0-R2 重写）第 25.4 节第 7 步确定本轮重试的 index 集合 `R` 之后：

```text
B                        = previous.retention_budget_bytes（lineage 固定）
base_retained            = Σ retry_payload_bytes(item.retry_material)
                           对 previous.items 中 index ∉ R 且 retry_material is not None 的条目
                           （即合并后仍原样保留、未参加本轮重试的条目的保留载荷）
available_retry_budget   = B - base_retained
```

* `R` 中条目的旧 `ItemExecution` / 旧 `RetryMaterial` 在合并结果中会被本轮条目**替换**，因此不计入 `base_retained`；合并结果
  从不同时长期强引用同一 index 的旧载荷与新载荷。
* `available_retry_budget < 0` 只可能来自违反第 10.7 节不变量的 previous（被篡改）-> `OrchestrationIntegrityError`。
* 本轮账本上限为 `available_retry_budget`：按 index 升序先对 `R` 中每个保留材料条目（`PREFLIGHT_RECHECK` / `FRESH_REEXECUTE` /
  `RESUME` / `DEFERRED`）计入 `retry_payload_bytes(retry_material)`（精确值）；随后 `METADATA_REFETCH` 恢复的条目的 NFO 与图片按
  第 19.6.3、19.6.4 节计入同一账本。任何一步使账本超过 `available_retry_budget` -> `OrchestrationResourceLimitError
  (RETAINED_BYTES_LIMIT)`，不返回重试 preview（第 19.6.6 节）。
* 成功返回的重试 preview 携带 `retry_budget_bytes = available_retry_budget`，且 `retained_artifact_bytes <= available_retry_budget`。
* 资源可合并性在 `preview_retry` 成功返回之前就已保证；`merge_retry` 中的检查只是纵深防御（第 26 节），从不是第一道资源发现点
  （否则 `previous.result_id` 已被登记为已重试，lineage 可能陷入无法重新选择范围的死路）。

#### 19.6.8 硬上界证明

对默认与任意合法配置：

```text
条目数（整个 lineage）                        <= MAX_BATCH_ITEMS = 2000
一个 BatchPreview 的保留 artifact 载荷          <= charged <= B <= MAX_RETAINED_ARTIFACT_BYTES_LIMIT = 16 GiB
preview 期间的峰值 artifact 字节（含下载中未保留的临时字节）
                                              <= B + K * MAX_ITEM_IMAGE_BYTES
                                              <= 16 GiB + 16 * 64 MiB = 17 GiB（默认配置：2 GiB + 4 * 64 MiB）
```

最后一行的依据：P4-C5 §14.7 保证一次 `acquire_images` 的瞬时内存不超过“已接受字节 + `max_image_bytes`”，其中已接受字节
包含在该条目的预约额内，`max_image_bytes <= max_total_bytes = R <= MAX_ITEM_IMAGE_BYTES`；进行中的调用至多 K 个。

（E0-R2 取代 E0-R1 中“参与合并的 preview 个数 × B / MAX_BATCH_ITEMS × B”的结果上界，该上界作废）：

```text
任意当前完整结果（主结果、合并结果 g1..gn）  retained_retry_payload_bytes <= B <= 16 GiB   （第 19.6.10 节归纳；与 generation 数无关）
任意重试轮结果                               retained_retry_payload_bytes <= B - base_retained <= B
preview_retry 期间的瞬时峰值（诚实上界，previous 在调用期间仍然存活）
    previous 完整结果的保留载荷                          <= B
  + 新重试 preview 的保留载荷                             <= B - base_retained  （与 previous 共享的保留材料按引用计入，实际更少）
  + 进行中图片调用的临时字节                              <= K * MAX_ITEM_IMAGE_BYTES
                                                          <= 2B + K * 64 MiB <= 32 GiB + 1 GiB（默认：4 GiB + 256 MiB）
```

#### 19.6.9 与 v1.0 500-item 验收的兼容性

默认配置下：500 `<= MAX_BATCH_ITEMS`；默认 `R = 64 MiB`、`B = 2 GiB`，准入条件 `A_nfo + Σ a_i + 64 MiB <= 2 GiB` 在实际
载荷约为每条数 MiB 时可容纳数百条（例如每条约 3 MiB 时约 660 条）。S6 的 500-item 合成门槛在**默认资源配置**下完整运行
（第 35.1 节）。需要更大批量的调用方在 `16 GiB` 内提高 `B` 或拆分批次。

#### 19.6.10 当前完整结果保留不变量与归纳证明（E0-R2，冻结）

**CURRENT COMPLETE RESULT RETENTION INVARIANT**：对任意主结果与任意合并结果 `r`，

```text
retained_retry_payload_bytes(r) <= r.retention_budget_bytes = B <= MAX_RETAINED_ARTIFACT_BYTES_LIMIT
```

它由第 10.7 节的模型不变量在构造时强制，并由以下归纳保证合法路径永远不会触发：

1. **基例（g0 主结果）**：主 preview 的保留载荷 `<= B`（第 19.6.2-19.6.5 节）。`execute` 不产生任何新的 artifact 载荷：每个
   `RetryMaterial.artifacts` 都是该条目 preview preflight 中的**同一个** tuple，`SUCCESS` / `NONE` 条目不保留材料（第 10.6、
   25.1 节）。因此 `charge(g0) <= preview retained <= B`。
2. **归纳步**：设 `charge(previous) <= B`。`preview_retry` 只允许重试 preview 使用 `available = B - base_retained`（第 19.6.7 节），
   得到 `retry preview retained <= available`；`execute` 同样不增加载荷，故 `charge(retry result) <= available`。`merge_retry`
   只组合引用：`R` 之外的条目是 previous 中的同一 `ItemExecution` 对象（其载荷恰为 `base_retained`），`R` 中的条目是 retry result
   中的同一对象（旧载荷被替换）。于是
   `charge(merged) = base_retained + charge(retry result) <= base_retained + (B - base_retained) = B`。
3. 由归纳，g0、g1、g2、……、gn 的每一个当前完整结果都 `<= B`；上界不随 generation 数量增长，不存在 `generation × B` 或
   `MAX_BATCH_ITEMS × B` 形式的累积。
4. **不复制载荷**：`merge_retry` 不深拷贝 artifacts、不调用 `bytes(...)`、不重建任何 payload；合并本身不产生新的字节副本。
5. **调用方所有权**：上述不变量约束的是**当前结果对象图自身**。调用方若同时继续强引用 previous、重试轮结果或更早的合并结果，
   由此产生的累计内存属于调用方所有权；P4-C8 内部不持有任何历史 generation。进程内一次性登记表（`_consumption.py`）只保存
   32 位 hex id 字符串，不保存 `BatchPreview`、`BatchExecutionResult`、`RetryMaterial` 或 artifact 字节。

## 20. Item 隔离与致命边界（冻结）

### 20.1 普通失败一律是条目数据

任何单个条目的普通 `Exception`（任何阶段、任何下层）、下层返回的失败状态、阻断、冲突、`FAILED` / `PARTIAL`，都只进入
该条目的 `ItemPreview` / `ItemExecution`，**永远不终止整批**，也永远不抛给调用方。没有 `continue_on_item_failure` 开关。

### 20.2 preview / preview_retry 的致命边界（asyncio，与 Phase 3 §7 一致）

* 调用方取消（`CancelledError`）：原样传播；图片 worker 全部被取消并被 await；不返回部分 preview。只读操作，被取消不产生
  任何文件系统后果。
* `KeyboardInterrupt`、`SystemExit`、`GeneratorExit`、其他非 `Exception` 的 `BaseException`，以及下层自行抛出的
  `CancelledError`（没有人请求取消）：致命控制流。停止准入，取消并 await 同级任务，重新抛出**原始对象**（绝不是
  `BaseExceptionGroup`，绝不变成条目结果）；多个致命异常竞争时只传播一个（Phase 3 C2-L5 同一规则）。worker 用私有、
  不读取任何元数据的载体把致命异常带出任务组（Phase 3 C4-R1-02 同一规则）。
* metadata 阶段的致命 / 取消由 Phase 3 scheduler 自身按其合同处理并传播。
* 同步阶段（5、7）中抛出的非 `Exception` 的 `BaseException` 直接传播。

### 20.3 execute 的致命边界（线程）

* 条目线程中 `execute_filesystem` 抛出非 `Exception` 的 `BaseException`（`KeyboardInterrupt`、`SystemExit`、`GeneratorExit`、
  自定义）：该线程记录**第一个**致命对象（只持有，不读取其任何元数据），设置 `stopping`，结束自身；其他线程完成各自进行中的
  条目后停止准入；全部线程 `join` 之后，`execute` 在调用线程中原样重新抛出该对象。
* 调用线程在等待（`join`）期间收到 `KeyboardInterrupt` / `SystemExit`（信号只投递给主线程）：设置 `stopping`，继续 `join`
  全部线程（进行中的 `execute_filesystem` 不被中断，第 27.2 节），然后重新抛出该对象。
* 致命异常传播时不返回部分 `BatchExecutionResult`；preview 已被消费。已完成条目的文件系统状态由 P4-C7 保证一致（P4-C7 §29：
  任何中断点上源媒体至少以一个完整副本存在）；这些条目的结果与 checkpoint 随致命异常丢失，其后 fresh preview 会以
  `TARGET_DIRECTORY_EXISTS` 等阻断 fail closed（第 24.3 节）。这与 P4-C7 §29、Phase 3 §7 “致命异常后不返回部分结果”一致。
* 这里对 `BaseException` 的捕获只用于“停止准入 + 排空线程 + 原样重新抛出”，从不吞掉、从不继续执行后续条目、从不映射为条目
  结果。
* 内联模式（`W_eff <= 1`）：致命异常直接从 `execute_filesystem` 传播到 `execute` 之外（无线程需要排空）。

## 21. 失败映射（冻结）

### 21.1 阶段与原因

每个未成功的条目都恰好有一个 `ItemIssue`，`issue.stage` 回答“失败发生在哪个阶段”，`issue.reason` 回答“是什么”，
不存在把不同原因压成一个 `FAILED` 或一个字符串的情况：

| 类别 | 阶段 | 原因 | 典型来源 |
|---|---|---|---|
| 番号不可识别 | `NUMBER_RECOGNITION` | `NUMBER_NOT_RECOGNIZED` | 文件名中没有 FC2 番号 |
| 批内冲突 | `BATCH_CONFLICT` | `DUPLICATE_SOURCE_IN_BATCH` / `DUPLICATE_TARGET_IN_BATCH` | 同一文件出现两次；两个文件同一番号 |
| metadata 不可得 | `METADATA` | `METADATA_UNAVAILABLE` / `METADATA_ENGINE_FAILURE` | 全部来源失败 / engine 异常 |
| plan 非法 | `PLANNING` | `PLANNING_REJECTED` | 非法 library_root、不安全的 `OutputPolicy` 组件、内部冲突 |
| publication 拒绝 | `PUBLICATION` | `PUBLICATION_REJECTED` | 身份不一致（理论上不可能） |
| NFO 渲染失败 | `NFO_RENDER` | `NFO_RENDER_FAILED` | 非法发行日期、非 XML 字符 |
| 图片获取错误 | `IMAGE_ACQUISITION` | `IMAGE_ACQUISITION_ERROR` | 伪造的 metadata 集合（候选级失败不是错误，第 22 节） |
| manifest 拒绝 | `MANIFEST` | `MANIFEST_REJECTED` | `ArtifactMappingError` |
| preflight 阻断 | `PREFLIGHT` | `PREFLIGHT_BLOCKED` | 目标目录已存在、源缺失 / 变化、library root 缺失 / 是链接 |
| preflight 拒绝 | `PREFLIGHT` | `PREFLIGHT_REJECTED` / `CHECKPOINT_REJECTED` | `PlanGraphError`（例如 `SOURCE_INSIDE_TARGET`）、checkpoint 已消费 / 封印无效 |
| 文件系统失败（零 effect） | `EXECUTION` | `EXECUTION_FAILED` | `ExecutionStatus.FAILED` |
| 文件系统部分完成 | `EXECUTION` | `EXECUTION_PARTIAL` | `ExecutionStatus.PARTIAL` |
| 执行被拒绝（零访问） | `EXECUTION` | `EXECUTION_REJECTED` | 第 18.2 节六种类型 |
| 执行中止（状态未知） | `EXECUTION` | `EXECUTION_ABORTED` | 外来异常 |

### 21.2 不含敏感信息

`ItemIssue` 只含枚举、类名；P4-C8 从不保存异常对象、消息、traceback、URL、响应、路径文本（路径只以下层模型字段的形式
出现在 `plan` / `preflight` / `execution` 中，这些是下层合同规定的字段）。

## 22. 图片部分获取与警告（冻结）

### 22.1 P4-C5 / P4-C6 / P4-C7 已冻结的语义（P4-C8 不重新定义）

* P4-C5 §14：每个候选问题只成为 `ImageCandidateFailure`，`acquire_images` 不因候选失败而抛出；角色可以没有图片；
  `failures` 按处理顺序排列。
* P4-C6 §20：缺失（`None`）的图片**不产生请求，也不算失败**；没有跨角色回退。§18：manifest 恒含 NFO，poster / fanart /
  thumb 可选，extrafanart `0..N`。
* P4-C7 §7.2、§9：可选图片缺失时对应单元为 `SKIPPED_ABSENT`，不是失败；U7（extrafanart 目录）总是执行。

### 22.2 P4-C8 的判定

| 情形 | 是否阻断 | P4-C8 表达 |
|---|---|---|
| 缺 poster / fanart / thumb | **否** | 可 preview、可执行；`POSTER_ABSENT` / `FANART_ABSENT` / `THUMB_ABSENT` |
| 没有任何 extrafanart | **否** | `NO_EXTRAFANART` |
| 部分 extrafanart 候选失败 | **否** | 成功的按 P4-C5 顺序全部写入；`IMAGE_CANDIDATE_FAILURES` |
| 全部图片都缺失 | **否** | 只写 NFO；四个警告全部出现 |
| `acquire_images` 抛出普通 `Exception`（只可能来自伪造输入 / 违反 protocol） | 是（该条目） | `UNPREPARED`，`IMAGE_ACQUISITION_ERROR` |

图片缺失永远不是阻断，也永远不单独可重试（执行之后再补图片需要写入已存在的目标目录，P4-C7 不允许；执行之前补图片等于
重新 preview）。

### 22.3 警告规则（派生，按声明顺序）

* `METADATA_PARTIAL`：`metadata.status is BatchItemStatus.PARTIAL`；
* `POSTER_ABSENT` / `FANART_ABSENT` / `THUMB_ABSENT` / `NO_EXTRAFANART`：`preflight` 非空且 manifest 不含对应 kind / 不含
  `EXTRAFANART`；
* `IMAGE_CANDIDATE_FAILURES`：`image_failures` 非空；
* `LEFTOVER_TEMPORARIES`（仅 `ItemExecution`）：`execution` 非空且 `execution.leftover_temporaries` 非空（P4-C6 / P4-C7
  遗留的本执行临时文件，永不被自动删除）。

## 23. PARTIAL 语义（冻结）

* P4-C8 的 `PARTIAL` 一律指 P4-C7 `ExecutionStatus.PARTIAL`：失败发生时累计存在至少一个已验证、可记录的 final effect，
  `ExecutionResult.checkpoint` 非空（P4-C7 §8）。
* 汇总中 `partial` 与 `success` 分开计数；`PARTIAL` 永远不被计为 `success`，也不被计为 `failed`（第 28 节）。
* `PARTIAL` 条目保持 P4-C7 留下的磁盘状态：P4-C8 不删除、不回滚、不“清理”任何 effect 或遗留临时文件。
* metadata 的 `PARTIAL`（Phase 3）只以 `ItemWarning.METADATA_PARTIAL` 出现，与文件系统 `PARTIAL` 无关。

## 24. Checkpoint 所有权（冻结）

### 24.1 P4-C8 只携带、不解读

* `ExecutionCheckpoint` 由 P4-C7 签发、封印、消费；P4-C8 只把它作为不透明值保存在 `ItemExecution.execution.checkpoint` 与
  `RetryMaterial.checkpoint` 中，并在重试时原样传回 `preflight_execution(plan, artifacts, checkpoint=cp)`。
* P4-C8 从不构造、复制、修改、比较、序列化 checkpoint，从不读取其 `seal`，从不推测其所有权状态（`ACTIVE` / `RESERVED` /
  `POISONED` 是 P4-C7 私有概念）。

### 24.2 同进程 PARTIAL

同一进程内，`PARTIAL` 条目以 `RetryKind.RESUME` 重试：`preflight_execution(retry_material.plan, retry_material.artifacts,
checkpoint=retry_material.checkpoint)`，其中 `plan` / `artifacts` 是原执行 preflight 中的同一对象（P4-C7 指纹绑定），
`checkpoint` 是 `ExecutionResult.checkpoint` 本身。已完成的 effect 由 P4-C7 只校验、跳过，永不重做、永不覆盖、永不删除
（P4-C7 §14.4）；前进是单调的：累计 effect 只增不减，媒体永不被重新移动，已写 artifact 永不被重新写入。

### 24.3 进程退出（v1.0 不做 durable resume）

* checkpoint 只在创建它的 Python 进程内有效（P4-C7 §14.1、§15.3：进程密钥）。进程退出后，所有 P4-C8 结果、checkpoint、
  登记表随之消失；P4-C8 不写任何能在进程之间传递状态的东西（第 33 节）。
* 之后对同一批文件的任何编排都只能是新的 `preview`：已有 P4-C7 部分 effect 的条目会以 `PREFLIGHT_BLOCKED`
  （例如 `TARGET_DIRECTORY_EXISTS`）或 `PREFLIGHT_REJECTED`（例如 `SOURCE_INSIDE_TARGET`）报告。
* P4-C8 的责任是**准确报告**这些阻断：它从不根据磁盘内容推测“以前做过一部分”，从不接管、删除或移动已有的目标目录，
  也不提供“强制 / 忽略阻断”的选项。人工处理属于用户。

## 25. Retry 规则（冻结）

### 25.1 `RetryKind` 判定（纯函数，`ItemExecution.retry_kind`）

| `disposition` | 条件 | `RetryKind` | 重试机制 | `RetryMaterial` |
|---|---|---|---|---|
| `EXECUTED` | `SUCCESS` | `NONE`（已结算） | — | `None` |
| `EXECUTED` | `PARTIAL` | `RESUME` | `preflight_execution(plan, artifacts, checkpoint=execution.checkpoint)` | 保留 |
| `EXECUTED` | `FAILED` | `FRESH_REEXECUTE` | `preflight_execution(plan, artifacts)`（fresh） | 保留，`checkpoint=None` |
| `NOT_READY` | `issue.stage is METADATA` | `METADATA_REFETCH` | Phase 3 `retry_failed` + 其后全部阶段 | `None` |
| `NOT_READY` | `issue.reason is PREFLIGHT_BLOCKED` | `PREFLIGHT_RECHECK` | `preflight_execution(plan, artifacts, checkpoint=原 preflight.checkpoint)` | 保留 |
| `NOT_READY` | 其他任何原因（番号、冲突、planning、publication、NFO、图片、manifest、`PREFLIGHT_REJECTED`、`CHECKPOINT_REJECTED`） | `NONE` | — | `None` |
| `NOT_SELECTED`、`CANCELLED` | — | `DEFERRED` | `preflight_execution(plan, artifacts, checkpoint=原 preflight.checkpoint)` | 保留 |
| `REJECTED` | — | `NONE` | — | `None` |
| `ABORTED` | — | `NONE` | — | `None` |

对任务所列五种情形的回答：

* **A 零 effect 的 FAILED**：`FRESH_REEXECUTE`，复用保留的 plan / manifest 做 fresh preflight（不重新获取 metadata /
  图片，执行的仍是用户确认过的内容）。若 P4-C7 §8 的窄例外在目标路径上留下了条目，fresh preflight 会以
  `TARGET_DIRECTORY_EXISTS` 阻断并如实报告。
* **B 带 checkpoint 的 PARTIAL**：`RESUME`（第 24.2 节）。
* **C preflight 阻断**：`PREFLIGHT_RECHECK`，只重新 preflight，不重新获取任何网络数据；阻断仍在则继续报告为
  `PREFLIGHT_BLOCKED`。P4-C8 从不通过删除 / 移动用户文件来消除阻断。
* **D checkpoint 失效 / 已消费**：重新 preflight 时 P4-C7 抛出 `CheckpointError`（`CONSUMED`、`SEAL_INVALID`、
  `PLAN_MISMATCH`、`MANIFEST_MISMATCH`、`EFFECTS_NOT_PREFIX`、`ALREADY_COMPLETE`）-> `UNPREPARED`，
  `CHECKPOINT_REJECTED`（`detail = .reason`），此后 `RetryKind.NONE`，交由人工处理。
* **E 进程退出后没有 checkpoint**：第 24.3 节。

### 25.2 不可重试的原因为什么不可重试

番号不可识别、批内冲突、planning / publication / NFO / 图片 / manifest 拒绝，在相同输入下是确定的；重试不会改变结果，
需要用户改变输入（重命名文件、去掉重复项、修正配置）并重新 preview。`REJECTED` 表示 preflight 被篡改或已被别处消费；
`ABORTED` 表示文件系统状态未知（P4-C7 可能已把源标记为 `POISONED`）。这些都 fail closed，只报告。

### 25.3 metadata 重试（`METADATA_REFETCH`）

* 当范围包含 `METADATA_REFETCH` 且存在此类条目时：`retry = await scheduler.retry_failed(previous.metadata_batch)`，
  `metadata_batch = apply_retry(previous.metadata_batch, retry)`（Phase 3 原样语义：只重试 `FAILED`，按原始位置，generation
  递增，lineage 绑定，fail closed）。
* 一致性要求（fail closed，`OrchestrationIntegrityError`）：`retry.indices` 必须恰好等于所有 `METADATA_REFETCH` 条目的
  `metadata_position` 升序集合（P4-C8 把每一个 Phase 3 `FAILED` 都映射为 METADATA 阶段的 `NOT_READY`，因此两者必然相等）。
* 对重试后 `SUCCESS` / `PARTIAL` 的条目，从 PLANNING 开始重新执行第 15.2 节全部阶段（新 plan、NFO、图片、manifest、fresh
  preflight）；仍为 `FAILED` 的条目保持 `METADATA` 阶段的 `UNPREPARED`，可再次重试。
* 范围不含 `METADATA_REFETCH` 时 metadata 账本原样传递。

### 25.4 `preview_retry(previous, *, scope=None)` 操作顺序（冻结）

```text
1  busy-first
2  type(previous) is BatchExecutionResult 且 previous.is_complete        否则 OrchestrationInputError
3  previous 对象图完整性重新检查（重跑模型不变量）                        否则 OrchestrationIntegrityError
4  配置相等（library_root / output_policy / image_policy；E0-R2：config.max_retained_artifact_bytes == previous.retention_budget_bytes）
                                                                        否则 OrchestrationInputError
5  scope：None（= 除 NONE 以外的全部 RetryKind）或严格 frozenset[RetryKind]，不含 NONE（可为空）   否则 OrchestrationInputError
6  previous.result_id 未被重试过（查询登记表）                            否则 OrchestrationConsumedError
7  重试集合 R = [item for item in previous.items if item.retry_kind in scope]，index 升序
7a （E0-R1；E0-R2 修订）保留预算：按第 19.6.7 节计算 base_retained 与 available_retry_budget = B - base_retained
   （< 0 -> OrchestrationIntegrityError），以 available_retry_budget 为本轮账本上限计入保留材料字节；
   超限 -> OrchestrationResourceLimitError（不登记 previous、不消费 checkpoint、不返回部分 preview）
8  METADATA_REFETCH 子集：25.3（其 NFO 与图片按第 19.6.3、19.6.4 节计量）
9  保留材料子集（PREFLIGHT_RECHECK / FRESH_REEXECUTE / RESUME / DEFERRED）：逐条同步 preflight_execution（25.1 表）
     CheckpointError -> CHECKPOINT_REJECTED；PlanGraphError / ArtifactManifestError / 其他普通 Exception -> PREFLIGHT_REJECTED；
     ready is False -> PREFLIGHT_BLOCKED
10 Phase B 冲突（14.3），范围为 R
11 原子登记 previous.result_id（一次性）；已登记 -> OrchestrationConsumedError，丢弃本次产物
12 返回重试 BatchPreview：generation = previous.generation + 1、base_result_id = previous.result_id、retry_scope = scope、
   items = R 对应的新 ItemPreview（retry_origin = 各自的 RetryKind）、metadata_batch = 第 8 步结果或原账本、
   （E0-R2）retention_budget_bytes = B、retry_budget_bytes = available_retry_budget
```

* 登记放在最后（第 11 步）：`preview_retry` 只读、不消费 checkpoint（P4-C7 §15.4），中途因致命异常 / 取消终止时 previous
  仍可再次重试；成功返回时才原子登记，防止从同一结果产生两个重试 preview。
* 空范围或空集合合法：返回 `items == ()` 的重试 preview（与 Phase 3 “没有可重试条目的重试轮次仍算一轮”一致）。

### 25.5 未执行即重试

对一个尚未执行的 preview 做 metadata 重试的方式：`orchestrator.execute(preview, selection=())`（不执行任何条目，全部 READY
条目为 `NOT_SELECTED`）-> `preview_retry(result, scope=frozenset({RetryKind.METADATA_REFETCH}))`；之后
`preview_retry(..., scope={DEFERRED})` 把未执行的 READY 条目带回（重新 preflight）。这是一条组合路径，不是新 API。

### 25.6 metadata `PARTIAL` 不被重新刮削（冻结裁决）

Phase 3 C4 冻结“`SUCCESS` 和 `PARTIAL` 条目永远不会被重试（C4 刻意没有提供 `retry_partial` 选项）”，P4-C3 冻结 `PARTIAL`
metadata 可发布。P4-C8 不推翻这两条：metadata `PARTIAL` 条目正常 preview / 执行，并带 `METADATA_PARTIAL` 警告。执行**之前**
希望重新刮削的调用方，可把这些条目从 selection 中排除，再以它们的子集调用新的 `preview`（新的 lineage）；执行**之后**
重新刮削需要覆盖已发布的 NFO，违反 overwrite = NEVER，不在 v1.0 范围内。规格书“Failed/Partial 可单独批量重刮”中的
Partial 在 P4-C8 中由文件系统 `PARTIAL` 的 `RESUME` 与上述子集 preview 路径满足。

## 26. Retry 子集与合并（`merge_retry(previous, retry)`，冻结）

纯组合 + 一次性登记；不访问网络 / 文件系统。按以下顺序检查，任何一步失败都抛出 `OrchestrationRetryError`（身份 /
图完整性问题抛出 `OrchestrationIntegrityError`），不返回任何内容：

```text
1  type(previous) is BatchExecutionResult 且 previous.is_complete
2  type(retry) is BatchExecutionResult 且 retry 是重试轮结果
3  retry.base_result_id == previous.result_id            （不是由这个结果产生的重试一律拒绝，包括形状完全相同的结果）
4  retry.lineage == previous.lineage
5  retry.generation == previous.generation + 1           （拒绝过期 / 重放的重试）
6  library_root / output_policy / image_policy 相等
7  [i.index for i in retry.items] == [i.index for i in previous.items if i.retry_kind in retry.retry_scope]
8  每个被重试 index：retry 条目的 media_item is previous 条目的 media_item，canonical_number 相等
9  retry.metadata_batch.lineage == previous.lineage 且 generation >= previous.metadata_batch.generation
9a （E0-R2）lineage 预算一致：retry.retention_budget_bytes == previous.retention_budget_bytes，且
   retry.retry_budget_bytes == previous.retention_budget_bytes - base_retained(previous, R)      否则 OrchestrationRetryError
9b （E0-R2）合并后保留载荷：base_retained(previous, R) + retry.retained_retry_payload_bytes <= B  否则 OrchestrationIntegrityError
   （正常合同路径下不可能失败，preview_retry 已提前保证；这是纵深防御，不是第一道资源发现点）
10 原子登记 retry.result_id 为“已合并”（一次性）；已登记 -> OrchestrationConsumedError
   （第 1-9b 步任何失败都发生在登记之前：retry.result_id 不被登记，可在修正后重新合并）
11 返回合并结果：被重试的 index 替换为 retry 的条目，其余是 previous 中的同一对象；generation = retry.generation；
   新 result_id；preview_id / base_result_id / retry_scope = None；metadata_batch = retry.metadata_batch；
   （E0-R2）retention_budget_bytes = B、retry_budget_bytes = None；只组合引用，不复制任何 artifact 载荷
```

* 重试结果永远不会被隐式合并；调用方负责调用 `merge_retry`（与 Phase 3 `apply_retry` 相同）。
* 重试链：`merged_g1 = merge_retry(result_g0, retry_g1)`，`merged_g2 = merge_retry(merged_g1, retry_g2)`，……
* 从同一结果只能产生一个重试 preview（第 25.4 节第 11 步）、每个重试结果只能合并一次（第 10 步），因此一个 lineage 在进程内
  只有一条向前推进的链。P4-C7 的一次性消费、独占 `mkdir` 与源所有权占用仍是文件系统层面的最终保证。

## 27. 取消（冻结）

### 27.1 分析

实施总提示词 Phase 4 要求“支持取消尚未开始的 item”；Phase 3 以 asyncio 取消实现 metadata 批处理的取消（未准入的条目永远不会
开始）。文件系统执行不同：P4-C7 的 syscall 是同步的、不可异步中断，强行中断会让 P4-C8 丢失结果与 checkpoint。因此：

### 27.2 冻结规则

* **preview / preview_retry**：asyncio 取消（第 20.2 节）。未准入的 metadata / 图片条目永远不会开始；只读，无文件系统后果。
* **execute**：协作式 `CancellationToken`。
  * `cancel.cancel()` 之后，任何尚未准入的被选中条目都不再执行，disposition 为 `CANCELLED`（`RetryKind.DEFERRED`，可在以后
    重试）；
  * 已经进入 `execute_filesystem` 的条目**永远不被中断**：它运行到 P4-C7 返回结果或抛出异常为止；P4-C8 从不使用线程中断、
    异步异常注入、进程终止或任何“kill”手段；
  * 取消后 `execute` 正常返回完整的 `BatchExecutionResult`（已执行条目的结果与 checkpoint 全部保留）；
  * 准入按 index 升序进行，因此被执行的条目集合总是 selection 顺序的一个前缀（加上并发时已在进行中的条目），其余全部是
    `CANCELLED`；
  * `cancel` 在 `execute` 开始前已被设置：零条目执行，全部被选中条目为 `CANCELLED`（preview 仍被消费）。
* 在事件循环中以 `asyncio.to_thread(orchestrator.execute, ...)` 调用时，取消外层 asyncio 任务**不会**停止执行线程；调用方必须
  使用 `CancellationToken` 请求停止，并继续等待（例如 `asyncio.shield`）以取得结果。这是文件系统同步性的直接后果，已在第 7.2 节
  声明。
* `KeyboardInterrupt` / `SystemExit` 是致命的，不是取消：第 20.3 节（排空进行中条目后原样传播，不返回结果）。

## 28. 汇总（冻结）

汇总是派生属性（不存储计数，因此不可能自相矛盾），全部为 `int`。

### 28.1 `PreviewSummary`（`BatchPreview.summary`）

```text
total, ready, blocked, unprepared, warned, stage_counts
```

* `total == len(items)`；`total == ready + blocked + unprepared`；
* `warned` = `warnings` 非空的条目数；
* `stage_counts`：`tuple[tuple[OrchestrationStage, int], ...]`，按 `OrchestrationStage` 声明顺序列出**全部**阶段（计数可为 0），
  统计 `issue.stage`；其总和 `== blocked + unprepared`。

### 28.2 `ExecutionSummary`（`BatchExecutionResult.summary`）

```text
total, ready, blocked, unprepared,
executed, success, partial, failed,
not_selected, cancelled, rejected, aborted,
retryable, deferred, non_retryable,
stage_counts
```

定义与恒等式（S5 以属性测试强制）：

* `ready` = `preview_state is READY` 的条目数；`blocked` / `unprepared` = `disposition is NOT_READY` 且对应 `preview_state`；
* `executed` = `disposition is EXECUTED`；`success` / `partial` / `failed` = `EXECUTED` 且 `ExecutionStatus` 分别为
  `SUCCESS` / `PARTIAL` / `FAILED`；
* `total == success + partial + failed + blocked + unprepared + not_selected + cancelled + rejected + aborted`；
* `executed == success + partial + failed`；`ready == executed + not_selected + cancelled + rejected + aborted`；
* `retryable` = `retry_kind in {METADATA_REFETCH, PREFLIGHT_RECHECK, FRESH_REEXECUTE, RESUME}`；`deferred` = `retry_kind is DEFERRED`；
  `non_retryable` = `retry_kind is NONE` 且不是 `SUCCESS`；
* `total == success + retryable + deferred + non_retryable`；
* `stage_counts`：同 28.1，统计有 `issue` 的条目。

### 28.3 No silent loss 在汇总中的体现

* `PARTIAL` 永远不计入 `success`；`ABORTED`（状态未知）单独计数，永远不计入 `success` / `failed` / `retryable`；
* 任何未以 `EXECUTED + SUCCESS` 结束的条目都在某个非 `success` 计数中，并有 `issue` 或 disposition 说明原因；
* `success` 只来自 P4-C7 的 `ExecutionStatus.SUCCESS`，P4-C8 从不自行推断成功。
* （E0-R1）批级 `outcome` 只有在 `success == total` 时才是 `SUCCESS`，因此存在任何 `PARTIAL`、`ABORTED` 或其他未完成条目时
  整批不可能被报告为 `SUCCESS`。

### 28.4 `outcome` 与汇总的一致性（E0-R1）

`BatchExecutionResult.outcome`（第 11.5 节）与 `summary` 由同一组 `items` 派生，S5 以恒等式强制：
`outcome is SUCCESS ⇔ success == total`；`outcome is PARTIAL ⇔ success + partial >= 1 且 success < total`；
`outcome is FAILED ⇔ total >= 1 且 success + partial == 0`。`summary` 不另存 `outcome` 字段。

## 29. 确定性（冻结）

* 对相同的输入、配置与相同的下层确定性结果（脚本化 engine / 图片 client / 文件系统状态）：preview 条目顺序、状态、阶段、
  原因、detail、`error_type`、警告、冲突、目标路径、计划单元、阻断；执行 disposition、`ExecutionStatus`、失败 kind、effect
  种类序列；重试集合与顺序；汇总计数——全部相等，与 asyncio 任务 / 线程完成顺序无关。
* 不确定且被排除在确定性投影之外的只有：`preview_id`、`result_id`、`BatchLineage.token`、P4-C7 的 `preflight_id` /
  `checkpoint_id` / `seal`。
* 取消的确定性边界：被执行的条目集合是 selection 顺序的前缀；在 `W_eff == 1` 时前缀长度完全由 token 被设置的时刻（相对于
  准入）决定。
* 测试以“确定性投影”（S1 在 `_helpers.py` 中定义：去掉上述随机字段的逐条元组）比较两次运行与反转完成顺序的运行。

## 30. 安全 / 路径安全边界（冻结）

### 30.1 no silent loss 完全委托给 P4-C7

P4-C8 自己不删除、不覆盖、不移动、不回滚任何用户媒体或文件；所有修改都通过 `execute_filesystem`，其 no-overwrite、
no-silent-source-loss、revalidate-before-mutation、forward-only 保证由 P4-C7 §23、§25、§28、§29 冻结。P4-C8 的附加义务是：
不削弱它们（永不对同一源 / 目标在一次编排中派发两次；永不在未 ready 的 preflight 上调用执行；永不吞掉致命异常后继续执行；
永不把 `PARTIAL` / `ABORTED` 报告为成功）。

### 30.2 路径

P4-C8 不构造、不规范化、不解析任何路径：目标路径来自 P4-C2 plan，artifact 路径来自 P4-C6 mapping，一切路径安全校验由
P4-C2 / P4-C6 / P4-C7 完成。P4-C8 对路径唯一的操作是 `os.path.basename`（番号识别）与 `casefold` / 精确比较（冲突分组）。

### 30.3 跨进程

P4-C8 v1.0 不提供跨进程协调（没有文件锁、命名互斥量、数据库、守护进程——它们等同于持久化或超出 v1.0 依赖边界）。同一进程内：
一次编排内不重复派发（第 14 节）；同进程的多个 orchestrator 之间由 P4-C7 的进程内源所有权占用、独占 `mkdir`、一次性消费保证
安全。跨进程对同一源的并发编排属于 P4-C7 §25 已声明的剩余风险：仍然不覆盖、无静默源丢失、fail closed，但不保证最多一个
`SUCCESS`。调用方应避免在多个进程中编排同一媒体目录。

### 30.4 TOCTOU

preview 与 execute 之间以及执行内部的 TOCTOU 边界与 P4-C7 §25 完全相同；P4-C8 不扩大也不缩小它。

## 31. P4-C7 委托（冻结）

| 事项 | 负责者 |
|---|---|
| 单影片预检（只读）与阻断原因 | P4-C7 `preflight_execution` |
| 单影片执行、单元顺序、forward-only、无回滚 | P4-C7 `execute_filesystem` |
| 封印、指纹、一次性消费、执行时重新校验 | P4-C7 |
| checkpoint 签发 / 验证 / 消费、源所有权占用 | P4-C7 |
| 类型化失败词汇 `ExecutionFailureKind`、`PreflightBlockReason` | P4-C7（P4-C8 原样携带） |
| 多影片编排、选择、并发、取消、批内去重、重试选择、汇总 | P4-C8 |

P4-C8 不把 P4-C7 变成批量 API：P4-C7 的公开 API、模块与语义在 P4-C8 中一行不改；P4-C8 只按 P4-C7 §30 的接口使用它
（preview 只调用 `preflight_execution` 并读取 `ready`、`blockers`、`mode`、`transfer_mode`、`pending_units`、
`completed_units`、`skipped_steps`；execution 对每个 ready preflight 调用一次 `execute_filesystem`；retry 携带
`ExecutionResult.checkpoint`，plan 与 artifacts 与原执行相同；manifest 由 `build_artifact_requests` 构建）。

## 32. P4-C9 诊断边界（冻结）

* P4-C8 只返回**内存中的**结构化模型（第 10 节）。这些模型就是留给 P4-C9 的接口：P4-C9 可以读取它们（以及其中引用的下层
  模型），决定如何呈现、序列化或导出。
* P4-C8 不写诊断 JSON、不生成诊断 bundle、不定义日志格式或磁盘报告 schema、不调用 `logging` / `print`、不提供
  `to_json` / `to_dict` / `dump` / `report` 之类的方法。
* P4-C8 不发布任何计时（没有 `elapsed_ms`）：P2-R-07 要求将来的诊断发布使用 engine 测量的 `SourceAttempt.elapsed_ms`，
  那是 P4-C9 的事情。
* P4-C8 模型中可达的下层对象（`AggregationResult` 及其 trace、`ExecutionResult`、`PreflightBlocker`、`ExecutionFailure`）
  都按其各自合同已经不含 secret；P4-C8 自己新增的字段只含枚举与类名。

## 33. 持久化非目标（冻结）

* 不新增 checkpoint JSON、pickle、SQLite、resume 文件、磁盘任务状态、durable id、缓存目录、图片落盘缓存。
* 所有 P4-C8 状态（模型、`_consumption` 登记表）只存在于当前进程内存中；进程退出即消失。
* 第 24.3 节是 v1.0 对“进程退出后”的完整回答。durable resume 不属于 v1.0。
* AST 强制：P4-C8 生产代码不 import `json`、`pickle`、`marshal`、`shelve`、`dbm`、`sqlite3`、`csv`、`tempfile`、`pathlib`、
  `io`，不调用 `open`。

## 34. 架构测试（冻结）

### 34.1 新文件 `tests/contract/test_orchestration_architecture.py`

* 模块集合恰好等于第 5 节中截至该批已创建的集合（S5 时为完整集合）。
* 每个模块的 import 只来自第 6 节允许集合；逐模块允许清单：`errors.py` 只 `__future__`；`cancellation.py` 只
  `__future__`、`threading`；`_consumption.py` 只 `__future__`、`threading`；`recognition.py` 不 import 任何
  `fc2_organizer.execution` / `materialization` / `images` / `nfo` / `publication` / `planning`；`execute.py` 是唯一
  import `execute_filesystem` 的模块；`preview.py` 是唯一 import `acquire_images` 的模块；`retry.py` 与 `preview.py`
  可以 import `stages`，`retry.py` 可以 import `preview`（复用其图片阶段与组合 helper，从不自行 import `acquire_images`）；
  `orchestrator.py` 只 import 本 package 模块、`fc2_metadata_core.batch`、`fc2_organizer.planning`（`OutputPolicy`）与
  `fc2_organizer.images`（`ImageAcquisitionPolicy`），（S2-A1）以及第 6 节只授权给它的标准库 `inspect`、`functools`；
  其它模块的允许清单不含 `inspect`、`functools`；`stages.py` 是唯一 import `build_organize_plan`、`prepare_publication`、`render_movie_nfo`、
  `build_artifact_requests`、`preflight_execution` 的模块。
* 禁止 import 清单（第 6 节）逐项断言；私有模块（`_fs`、`seal`、`atomic` 等）零引用。
* 禁止调用：任何 `os.*` 属性访问中除 `os.name`、`os.path.basename` 以外的名称；`open`、`eval`、`exec`、`compile`、
  `__import__`、`print`；`shutil.*`；函数 / 方法名 `rollback`、`undo`、`revert`、`delete`、`remove`、`unlink`、`rmtree`、
  `save`、`load`、`dump`、`dumps`、`to_json`、`to_dict`、`write`。
* 结构性零修改（第 16 节）：`execute_filesystem`、`materialize_artifact`、`materialize_atomic_bytes` 的名称不出现在
  `execute.py` 以外的任何模块。
* 线程与任务有界性：`threading.Thread(` 只出现在 `execute.py`；`asyncio.create_task` / `TaskGroup.create_task` 只出现在
  `preview.py`；源码中没有 `ThreadPoolExecutor`、`gather(*` 于条目列表的用法（AST：`asyncio.gather` 不出现）。
* 无反向依赖：`src` 下其他模块与 `fc2_organizer/__init__.py` 不引用 `orchestration`；裸 `import fc2_organizer` 不加载它。
* 运行时：在 meta-path 阻断 `amane`、`requests`、`sqlite3`、`shelve`、`dbm`、`pickle` 的条件下 import 并端到端运行一次
  preview + execute（脚本化 engine / client、`tmp_path`）。
* 公开 API：`__all__` 恰好等于第 7.1 节集合（S5 起；S1-S4 断言截至该批的子集）。
* （E0-R1）资源控制：`MAX_BATCH_ITEMS` 等四个资源常量只在 `models.py` 定义；保留预算账本只存在于 `preview.py` 的调用局部
  对象中（`preview.py` / `retry.py` 没有模块级可变状态）；`BatchOutcome` 只由 `BatchExecutionResult.outcome` 属性产生，
  没有任何存储 `outcome` 的字段。
* （E0-R2）资源 helper 归属冻结（不新增任何生产模块）：有界快照只在 `recognition.py`（`bounded_snapshot`）；保留载荷计量
  （`retry_payload_bytes`、`retained_retry_payload_bytes`、`retained_artifact_bytes`）与结果 / preview 保留不变量只在
  `models.py`；lineage 预算校验、`base_retained` / `available_retry_budget` 与 `merge_retry` 纵深防御只在 `retry.py`；调用局部账本
  只在 `preview.py`。AST 断言：P4-C8 生产源码中不出现对 `preview` 输入参数的 `tuple(...)` / `list(...)` / `len(...)` 调用
  （`recognition.py` 只对内部 `collected` 调用 `tuple`）；`copy` 模块与 `deepcopy` 不出现。

### 34.2 生产 / 测试的私有接缝许可

生产代码对下层私有模块零引用（AST）；测试可以使用 `fc2_organizer.execution._fs._FS`、`fc2_organizer.materialization.atomic._FS`
等接缝，并可以 monkeypatch `fc2_organizer.orchestration.execute.execute_filesystem`（测试替身包装真实函数以计数并发 / 注入异常）。

### 34.3 既有守卫的授权更新（S1，逐项最小改动）

```text
tests/contract/test_discovery_architecture.py      顶层 package 集合 + "orchestration"（一行）
tests/contract/test_planning_architecture.py       顶层 package 集合 + "orchestration"（一行）
tests/contract/test_publication_architecture.py    顶层 package 集合 + "orchestration"（一行）
tests/contract/test_nfo_architecture.py            顶层 package 集合 + "orchestration"（一行）
tests/contract/test_execution_architecture.py      test_no_reverse_dependency_on_execution 豁免 orchestration 目录；
                                                   新增 test_orchestration_consumes_only_the_bare_execution_package
tests/contract/test_materialization_architecture.py test_no_reverse_dependency_on_materialization 豁免 orchestration 目录；
                                                   新增 test_orchestration_consumes_only_bare_materialization_and_mapping
```

这些更新与 P4-C3..P4-C7 新增 package 时的先例一致；豁免只针对本合同授权的唯一新消费者，并各自新增更严格的断言。
除此之外不修改任何既有测试。

## 35. 必需测试矩阵（冻结）

全部测试离线、只在 pytest `tmp_path` 下创建文件、不读取用户文件、不访问网络；engine 与图片 client 是脚本化的内存替身
（满足 Phase 3 `AggregationEngine` 与 P4-C5 `ImageHttpClient` 协议），文件系统是真实的 `tmp_path`，执行走真实的 P4-C7。
测试文件与分批见施工计划。

| 类别 | 必须覆盖 |
|---|---|
| unit | 全部模型不变量（每条不变量一个正例 + 一个反例）；`ItemIssue` 组合表逐行；配置范围 / `bool` / 子类；`CancellationToken` 线程安全与幂等；类名提取全函数（恶意 metaclass / `__name__`）；`RetryKind` 判定表逐行 |
| contract | 输入容器规则（与 Phase 3 §4 同形）；busy-first（合法 / 非法 / 空参数都抛 `OrchestrationBusyError`，被拒调用不释放占用，且回归测试不会挂起）；错误消息不含路径 / 标题 / URL；错误不链接 |
| architecture | 第 34 节全部 |
| integration | 真实 `discover_media` 扫描 `tmp_path` 树 -> preview -> execute -> 最终目录精确列举、字节、sha256、源不存在；8 种可选主图组合 × extrafanart {0, 1, 13}；Unicode / 大小写扩展名；library root 不存在 / 是 junction 时的阻断 |
| batch synthetic | 第 35.1 节 500-item 门槛 |
| fault injection | 通过 `execution._fs._FS` / `materialization.atomic._FS` 在每类可注入位置（U1 前、U1 后、U2 各阶段、artifact、U7、extrafanart）注入 -> 正确的 disposition / `ExecutionStatus` / `issue` / `RetryKind`；外来异常 -> `ABORTED`；pre-FS 类型化拒绝 -> `REJECTED`；每次注入后 `assert_source_not_lost` |
| retry | 五种 `RetryKind` 各自的完整链（preview_retry -> execute -> merge_retry）；A-E 五种情形；metadata 重试与 Phase 3 `retry_failed` / `apply_retry` 的一致性；scope 子集（只 `RESUME`、只失败类、只 `DEFERRED`、空 scope）；重试链 g0 -> g1 -> g2 -> g3；从同一结果第二次 `preview_retry` -> `OrchestrationConsumedError`；第二次 `merge_retry` -> `OrchestrationConsumedError`；过期 / 外来 lineage / 错误 base / 错误 generation / 错误 index 集合 -> `OrchestrationRetryError`；RESUME 不重写已完成 artifact（inode / mtime 不变）、不重新移动媒体 |
| concurrency | metadata 峰值 ≤ M、图片峰值 ≤ K、执行峰值 ≤ W（M/K/W ∈ {1, 2, 4, > N}，峰值在足够条目时达到上限）；存活任务 `O(K)`、线程数 `== min(W, n)`（对照测试：朴素“一条一线程”实现会被检测出）；busy 守卫防预算翻倍 |
| determinism | 同一输入两次运行、以及用事件强制反转 engine / 图片 / 执行完成顺序的运行，确定性投影逐项相等；汇总相等 |
| preview no-mutation | 第 16 节：全部修改性 API 拦截 + 正向对照 + 前后树快照；覆盖主 preview、带阻断 / 冲突 / 失败的 preview、每种 `RetryKind` 的 `preview_retry` |
| cancellation | token 在开始前 / 中途 / 结束后设置；`W = 1` 时 CANCELLED 恰为后缀；`W > 1` 时进行中的条目完成、之后不再准入；取消的条目 `DEFERRED` 并可重试至 `SUCCESS`；preview 的 asyncio 取消：worker 被 await、无孤儿任务、零修改 |
| fatal | preview：`KeyboardInterrupt` / `SystemExit` / `GeneratorExit` / 自定义 `BaseException` / 自行 `CancelledError` 来自 engine、图片 client、同步阶段 -> 原始对象、不返回 preview、同级被 await；execute：条目线程与调用线程两种来源 -> 进行中条目完成、`join` 全部线程、原始对象传播、无结果、preview 已消费；恶意元数据的致命异常不被读取 |
| 500-item mixed-outcome | 第 35.1 节 |
| race regression | 同一 preview 被两个线程同时 `execute` -> 恰好一个运行、另一个 `OrchestrationConsumedError`；两个 orchestrator 在同一进程并发执行重叠条目 -> 每个源最多一个 `SUCCESS`、失败者 fail closed、源不丢失；hardlink / 同文件两次 / 重叠根目录 -> Phase A / B 冲突；preview 之后、execute 之前对源 / 目标的漂移 -> 类型化失败而非执行另一件事 |
| public API exact-set | `__all__` 与第 7.1 节逐项相等；每个名称可 import；没有第 7.1 节禁止的名称 |
| batch outcome（E0-R1） | 第 11.5 节真值表逐行（每种条目类别单独、每种“全部为某类”、空结果、`S` 与各类混合、`P` 与各类混合、`ABORTED` 与 `S` 混合）；主结果、重试轮结果、合并结果三种形态；`outcome` 是纯函数（同一 `items` 重复求值相等、不同对象但相同条目序列相等）；第 28.4 节与 summary 的恒等式在 S5 的生成批次上全部成立；没有存储字段 |
| resource limits（E0-R1） | 条目数：`MAX_BATCH_ITEMS` 条接受、`MAX_BATCH_ITEMS + 1` 条 -> `BATCH_ITEM_LIMIT` 且 engine / client 调用 0 次、零文件系统访问（使用不可识别番号或极小条目，不申请大内存）；`image_policy.max_total_bytes == MAX_ITEM_IMAGE_BYTES` 接受、`+ 1` -> `OrchestrationConfigError`；`max_retained_artifact_bytes` 边界（0 / 1 / 上限 / 上限 + 1 / `bool`）；字节预算（小预算、小 `R`，由用例定义精确推导 `B_exact`）：`B == B_exact` 接受、`B == B_exact - 1` -> `RETAINED_BYTES_LIMIT`；NFO 计量超限时图片请求 0 次；预约准入：`K = 4` 而 `B` 只容纳 2 个预约时，进行中的 `acquire_images` 峰值 `<= 2`，账本观测（测试替身在每次准入 / 完成时读取私有账本）始终 `<= B`；失败 index 在反转完成顺序与 `K ∈ {1, 2, 4}` 下相同；`total_bytes > R` 的违约替身 -> `IMAGE_ACQUISITION_ERROR`；超限时不返回 preview、零修改、orchestrator 恢复空闲、错误不链接且消息不含路径 / URL；`preview_retry` 保留材料计量超限 -> 不登记 previous，改变重试范围（降低 `base_retained`）后可再次重试 |
| bounded snapshot（E0-R2） | 输入以计数型自定义 `Sequence`（记录 `__iter__` / `__getitem__` / `__len__` 调用与读取的元素数）提供：A `MAX_BATCH_ITEMS` 个元素 -> 接受，读取恰好 `MAX_BATCH_ITEMS` 个元素 + 1 次 `StopIteration`；B `MAX_BATCH_ITEMS + 1` 个 -> `BATCH_ITEM_LIMIT`，读取恰好 `MAX_BATCH_ITEMS + 1` 个元素、之后 `next` 调用 0 次；C 惰性生成、声称 1 000 000 个元素的自定义序列 -> `BATCH_ITEM_LIMIT`，读取元素数 `== MAX_BATCH_ITEMS + 1`（证明没有完整遍历 / 复制）；D 说谎长度序列（`__len__` 返回 1，实际迭代出 3000 个）-> `BATCH_ITEM_LIMIT`；E `__len__` 从不被调用（计数为 0），`__len__` 返回很大值但实际只有 5 个元素的序列按 5 个处理；F 超限输入中第 2001 个之后放置非 `DiscoveredMediaItem` 元素 -> 仍是 `BATCH_ITEM_LIMIT`（优先级）；G 前 2000 个中有非法元素且总数 `<= 2000` -> `OrchestrationInputError`；H 迭代中抛普通异常 -> `OrchestrationInputError`（不链接），抛 `KeyboardInterrupt` -> 原样传播；全部情形 engine / 图片 client 调用 0 次、零文件系统访问 |
| result retention（E0-R2） | 边界：A 主结果保留载荷恰好 `B` -> 接受；B 构造保留载荷 `> B` 的主结果 / 合并结果 -> `OrchestrationContractError`（合法 preview 不可能产生）；C previous 未重试部分载荷接近 `B`、可用额度只剩少量；D 重试载荷恰好等于可用额度 -> 接受；E 可用额度 + 1 -> `preview_retry` `RETAINED_BYTES_LIMIT`；F 失败后 previous 未被登记、checkpoint 未被消费，改变范围后可再次 `preview_retry`；G 合并后保留载荷恰好 `B` -> `merge_retry` 成功；H 以 `object.__setattr__` 篡改重试轮结果使合并后 `> B` 或篡改 `retry_budget_bytes` -> `merge_retry` fail closed 且不登记 `retry.result_id`（修正后的正确结果仍可合并）；I lineage 预算不同（不同 `max_retained_artifact_bytes` 的 orchestrator 调用 `execute` / `preview_retry`；`merge_retry` 两侧 `retention_budget_bytes` 不同）-> 拒绝；`available_retry_budget < 0`（篡改 previous）-> `OrchestrationIntegrityError`；合并不复制载荷（合并结果条目与来源条目 `is` 相同，`RetryMaterial.artifacts` 为同一 tuple）；登记表只保存 id 字符串 |
| multi-generation retention（E0-R2） | 第 35.1.1 节冻结场景（g0-g4，每代作用于不同条目子集；若每代使用独立完整 `B`，g2 的合并结果将 `> B`）：每个当前完整结果 `retained_retry_payload_bytes <= B`，逐代数值与场景定义精确相等；g2 的越界重试以 `RETAINED_BYTES_LIMIT` 失败且 previous 可改变范围后继续 |

**核心不变量（每个执行 / 注入 / 门槛测试都必须断言）：** 每个输入条目的源视频要么仍在源路径上且字节不变，要么在最终路径上
且字节相同（或两者都有）；任何非本执行创建的条目的字节、inode、mtime 不变；汇总恒等式成立。

### 35.1 500-item 批量编排合成门槛（S6，`tests/unit/orchestration/test_orchestration_synthetic_gate.py`）

只验证**编排**；不重复 P4-C7 的 1000 extrafanart、平台 syscall、原子发布等底层测试。

* 500 个确定性合成媒体文件，位于 `tmp_path` 下的脏下载目录，由真实 `discover_media` 发现；每个文件几字节到几 KB。
* 分组（静态断言组成）：

| 组 | 数量 | 构造 | 主轮 preview | 主轮执行 |
|---|---|---|---|---|
| A 正常 | 310 | metadata `SUCCESS` / `PARTIAL` 混合；8 种主图组合 × extrafanart 0..3；部分图片候选失败 | READY | `SUCCESS` |
| B 番号不可识别 | 40 | 文件名无 FC2 番号 | UNPREPARED / `NUMBER_NOT_RECOGNIZED` | `NOT_READY` |
| C 批内冲突 | 30 | 10 对同番号不同文件（20）+ 3 个条目重复出现（6）+ 2 对 hardlink 且番号不同（4） | BLOCKED / `DUPLICATE_*` | `NOT_READY` |
| D metadata 失败 | 40 | 25 聚合 `FAILED` + 10 engine 异常 + 5 结果合同不符；其中 30 个在重试时成功 | UNPREPARED / `METADATA_*` | `NOT_READY` |
| E NFO 失败 | 10 | 非法 release | UNPREPARED / `NFO_RENDER_FAILED` | `NOT_READY` |
| F preflight 阻断 | 20 | 预先植入目标目录；测试在第 2 轮前移除其中 15 个（测试扮演用户） | BLOCKED / `PREFLIGHT_BLOCKED` | `NOT_READY` |
| G 执行故障 | 30 | 15 个 U1 前注入（`FAILED`）+ 15 个 U1 后注入（`PARTIAL`，含 `SOURCE_UNLINK_FAILED` 与 artifact 写入失败） | READY | `FAILED` 15 / `PARTIAL` 15 |
| H 外来异常 | 10 | 经 `_FS` 在 U2 注入 `RuntimeError` | READY | `ABORTED` |
| I 未选中 | 10 | 主轮 selection 排除 | READY | `NOT_SELECTED` |

* 期望计数（全部由分组表静态推导，逐项断言）：
  * 主 preview：`ready 360 / blocked 50 / unprepared 90`；
  * 主结果：`success 310 / partial 15 / failed 15 / aborted 10 / not_selected 10 / blocked 50 / unprepared 90`；
    `retryable 90（RESUME 15 + FRESH_REEXECUTE 15 + METADATA_REFETCH 40 + PREFLIGHT_RECHECK 20）/ deferred 10 / non_retryable 90`；
  * g1 `scope={RESUME}`：15 READY -> 15 `SUCCESS`；合并后 `success 325`；
  * g2 `scope={METADATA_REFETCH, FRESH_REEXECUTE, PREFLIGHT_RECHECK}`（此前移除 15 个植入目录、清除 G 的故障注入）：75 条 ->
    preview `ready 60 / blocked 5 / unprepared 10` -> 60 `SUCCESS`；合并后 `success 385`；
  * g3 `scope={DEFERRED}`：10 -> 10 `SUCCESS`；合并后 `success 395`；
  * g4 `scope=None`：15 条（D 10 + F 5）-> `ready 0`，执行 0 条；合并后最终：`success 395 / blocked 35 / unprepared 60 /
    aborted 10`，`retryable 15 / deferred 0 / non_retryable 90`。
* （E0-R1）批级 `outcome` 断言（由第 11.5 节真值表对上述计数推导）：

| 结果 | 计数依据 | `outcome` |
|---|---|---|
| 主结果（g0） | `s = 310 < 500`，`s + p = 325 >= 1` | `PARTIAL` |
| g1 重试轮结果 | 15 条全部 `SUCCESS` | `SUCCESS` |
| g1 合并结果 | `s = 325 < 500` | `PARTIAL` |
| g2 重试轮结果 | 75 条中 `s = 60`，`p = 0` | `PARTIAL` |
| g2 合并结果 | `s = 385 < 500` | `PARTIAL` |
| g3 重试轮结果 | 10 条全部 `SUCCESS` | `SUCCESS` |
| g3 合并结果 | `s = 395 < 500` | `PARTIAL` |
| g4 重试轮结果 | 15 条，`s = 0`，`p = 0` | `FAILED` |
| g4 合并结果（最终） | `s = 395 < 500`，`s + p >= 1` | `PARTIAL` |

* （E0-R1）资源配置：门槛在**默认资源配置**下运行（`MAX_BATCH_ITEMS`、`DEFAULT_MAX_RETAINED_ARTIFACT_BYTES`、默认
  `ImageAcquisitionPolicy`），只按既有冻结覆盖执行并发 `W = 4`；主 preview 与每个 `preview_retry` 都必须成功返回
  （不得触发 `OrchestrationResourceLimitError`）。
* 执行使用 `W = 4`、`K = 4`、`M = 4`；以测试替身包装记录的峰值分别 `<= 4` 且 `== 4`。
* （E0-R1）资源边界子门槛（同一测试文件；使用小配置，不申请大内存）：
  * 条目数：`MAX_BATCH_ITEMS` 个条目（不可识别番号的极小文件）-> preview 成功返回；`MAX_BATCH_ITEMS + 1` ->
    `OrchestrationResourceLimitError(BATCH_ITEM_LIMIT)`，engine / 图片 client 调用 0 次，零修改；
  * （E0-R2）有界快照：以计数型自定义 `Sequence` 经 `preview` 端到端验证第 35 节 “bounded snapshot” 行的 B、C、D（读取元素数
    `== MAX_BATCH_ITEMS + 1`、说谎长度被拒绝、`__len__` 调用 0 次）；
  * （E0-R2）多代保留：第 35.1.1 节场景完整运行，g0-g4 每个当前完整结果的 `retained_retry_payload_bytes` 与定义值精确相等且
    `<= B`；
  * 字节预算：取 500-item 语料的主 preview，设置小 `R`（能容纳合成图片）与由用例定义推导的 `B_exact`（第 19.6.4 节准入式
    在最紧的条目处取等号）：`B_exact` -> 成功，且结果与默认配置下的主 preview 投影相等；`B_exact - 1` ->
    `RETAINED_BYTES_LIMIT`，不返回 preview，零修改；
  * 并发预约：`K = 4`、`B` 只容纳 2 个预约 -> 进行中的图片调用峰值 `<= 2`、观测到的账本始终 `<= B`；反转完成顺序后失败 / 成功
    结论与失败 index 不变。
* 每次 `preview` / `preview_retry` 前后树快照相等（零修改）；每轮执行后对全部 500 个条目断言核心不变量；H 组源不丢失。
* 每次 `preview` / `preview_retry` 前后树快照相等（零修改）；每轮执行后对全部 500 个条目断言核心不变量；H 组源不丢失。
* RESUME 条目：已完成 artifact 的 inode / mtime 在 g1 前后不变；媒体未被重新移动。
* 最终库目录的精确列举（395 个影片目录及其内容）与用例定义一致；没有临时文件残留（G 中记录的 leftover 名称除外，且名称精确）。
* 确定性：整个门槛在全新的 `tmp_path` 中再运行一次（engine / 图片完成顺序以事件反转），全部确定性投影与每轮汇总相等。
* 非空洞性（不提交，记录于 HANDOFF）：至少以下生产变异各自使门槛失败——(a) 去掉 Phase A 冲突阻断；(b) preview 路径调用
  `execute_filesystem`（或 `execute` 不登记 `preview_id`）；(c) 汇总把 `PARTIAL` 计入 `success`；(d) `RetryKind` 判定把
  `RESUME` 与 `FRESH_REEXECUTE` 对调；(e) 执行 worker 改为每条目一个线程；（E0-R1）(f) 移除图片阶段的保留预算预约准入
  （无条件准入）-> 资源边界子门槛在行为层失败（`B_exact - 1` 不再抛出和 / 或并发预约峰值 / 账本超过 `B`）；(g) 移除
  `MAX_BATCH_ITEMS` 检查 -> `MAX_BATCH_ITEMS + 1` 被接受，子门槛失败；(h) `outcome` 把含 `PARTIAL` 的结果判为
  `SUCCESS`（或把空结果以外的全 `SUCCESS` 判为其他值）-> outcome 断言失败；（E0-R2）(i) 恢复 snapshot-first（先
  `tuple(items)` 完整快照再检查长度）-> 有界快照子门槛失败（读取元素数远大于 `MAX_BATCH_ITEMS + 1`）；(j) 把
  `preview_retry` 的可用额度从 `B - base_retained` 改为 `B` -> 第 35.1.1 节 g2 越界重试不再失败，其合并结果保留载荷 `> B`，
  多代保留子门槛失败。变异只能以行为层断言失败证明，不能只靠 AST 检测常量消失。

#### 35.1.1 多代保留场景（E0-R2，冻结；S4 以单元测试实现，S6 作为子门槛再运行）

小配置：`M = K = W = 1`；`image_policy.max_total_bytes = R = I`，其中 `I` 为每个图片条目的精确图片字节数；NFO 为纯 ASCII，
记其长度为 `L`，要求 `I > 2 * L`（使错误实现可被检测）。条目：

* `D1..D4`：主 preview 中 READY，每个的保留载荷 `pay(D) = L + I`（精确，`retry_payload_bytes`）；记 `payD = 4 * pay(D)`；
* `M1..M4`：主 preview 中 metadata `FAILED`；脚本化 engine 在指定的 generation 才让 `Mk` 成功；每个恢复后的准入需求
  `need(M) = 4 * L + I`（第 19.6.3、19.6.4 节账本），实际保留载荷 `pay(M) = L + I`。
* `B = payD + need(M)`（经 `OrchestrationConfig.max_retained_artifact_bytes` 设定）。

| 代 | 操作 | 期望 |
|---|---|---|
| g0 | `preview`；`execute(selection=())` | 主结果 `retained_retry_payload_bytes == payD <= B`（D1-D4 为 `DEFERRED`） |
| g1 | `preview_retry(scope={METADATA_REFETCH})`，engine 只让 M1 成功；`execute(selection=())`；合并 | 可用额度 `B - payD == need(M)`，M1 恰好准入（边界 D）；合并结果 `== payD + pay(M) <= B` |
| g2（失败尝试） | `preview_retry(scope={METADATA_REFETCH})`，engine 让 M2 成功 | 可用额度 `B - payD - pay(M) = need(M) - pay(M) < need(M)` -> `RETAINED_BYTES_LIMIT`；g1 合并结果未被登记为已重试 |
| g2 | `preview_retry(scope={DEFERRED})`；`execute(selection=(M1 的 index,))`；合并 | M1 `SUCCESS`（释放其载荷），D1-D4 仍 `NOT_SELECTED`；合并结果 `== payD` |
| g3 | `preview_retry(scope={METADATA_REFETCH})`，engine 让 M2 成功；`execute(selection=())`；合并 | 可用额度 `== need(M)`，M2 恰好准入；合并结果 `== payD + pay(M) <= B` |
| g4 | `preview_retry(scope={DEFERRED})`；`execute()`（全部 READY）；合并 | D1-D4、M2 `SUCCESS`；合并结果 `== 0`；M3、M4 仍为 metadata `FAILED` |

若实现错误地让每代重新获得完整 `B`（变异 (j)），g2 的 M2 重试会成功，执行 `selection=()` 并合并后保留载荷
`payD + 2 * pay(M) = payD + 2L + 2I > payD + 4L + I = B`（因为 `I > 2L`），被第 10.7 节不变量或测试断言拒绝。

## 36. 延续项（冻结）

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

## 37. 范围之外与已知局限（冻结）

范围之外：第 3 节全部；P4-C9 诊断输出；P4-C10 Phase 4 最终验收 / release closure / 跨 package 全局门槛；修改 P4-C1..P4-C7
的任何生产代码、合同或 HANDOFF；修改 Phase 3 合同；修改 v1.0 规格书与 `CLAUDE.md`。

已知局限（设计选择，不是缺陷）：

* 非法 `library_root` 在 metadata / 图片网络阶段之后才以 `PLANNING_REJECTED` 暴露（第 15.3 节）；
* （E0-R1）资源硬限制：条目数 `<= MAX_BATCH_ITEMS`、每个 preview 的保留 artifact 载荷 `<= max_retained_artifact_bytes`；
  超过时整个 `preview` / `preview_retry` fail closed，调用方需拆分批次或在绝对上限内提高预算（第 19.6 节）；预约准入可能使
  图片并发低于 K；（E0-R2）预算在一个 lineage 内固定，当前完整结果保留载荷 `<= B`，因此当未结算条目占满预算时，新的
  `METADATA_REFETCH` 重试可能需要先执行 / 结算其他条目；调用方自己同时持有多代结果的内存属于调用方所有权；
* 执行中的条目不可中断，取消只停止准入（第 27 节）；
* 致命异常后不返回部分结果，已执行条目的 checkpoint 随之丢失（第 20.3 节）；
* 无跨进程协调（第 30.3 节）；无 durable resume（第 24.3、33 节）；无进度流（第 11.4 节）；
* 番号只从文件 basename 识别，父目录名不参与（第 14.1 节）；
* 冲突组全部阻断，不自动选择胜者（第 14.4 节）；metadata `PARTIAL` 不被自动重新刮削（第 25.6 节）。

## 38. 实现状态

本表是 P4-C8 各批次的**当前**权威状态（头部的 E0 建立时状态仅为历史快照）。后续批次只能按施工计划第 0.4 节的规则
（S1 特例 / S2-S6 通用模板）更新本表的状态行。

| 批次 | 内容 | 状态 |
|---|---|---|
| E0 | 本合同 + 施工计划（docs-only） | E0 ACCEPTED / CLOSED — FINAL REVIEWED DOCS HEAD `9e118dea32361ec19b0a84f84b6e5da0fbd134bc` |
| S1 | Foundation：errors / models / config / cancellation / consumption / recognition / 架构守卫 | S1 ACCEPTED / CLOSED — FINAL REVIEWED CODE HEAD `e8f83e986d3cb306a425d666f3bc0a2738dab823` |
| S2 | Preview composition：stages / preview / orchestrator.preview | S2 ACCEPTED / CLOSED — FINAL REVIEWED CODE HEAD `8c5ba6e808a6c45ee2342af497458fe88af5ff09` |
| S3 | Execution orchestration：execute / selection / cancellation / fatal drain | S3 ACCEPTED / CLOSED — FINAL REVIEWED CODE HEAD `7fb6bfb2d230d90d240a0a4b462332d27afe77d5` |
| S4 | Retry：RetryKind / preview_retry / merge_retry | S4 ACCEPTED / CLOSED — FINAL REVIEWED CODE HEAD `4933f38bd09101766643af0b66757080565a8619` |
| S5 | Summary / determinism / race / integration hardening + 最终公开 API | S5 IMPLEMENTED — INDEPENDENT REVIEW REQUIRED |
| S6 | 500-item batch orchestration gate + HANDOFF | NOT STARTED |

```text
P4-C8-E0-R-01        : CLOSED（批级 BatchOutcome，第 11.5 节；E0-R1 closure review）
P4-C8-E0-R-02        : CLOSED（资源硬限制，第 19.6 节；经 E0-R2 修订，E0-R2 closure review）
P4-C8-E0-R-03        : CLOSED（S1 治理特例，施工计划第 0.4 节；E0-R1 closure review）
P4-C8-E0-R1-01       : CLOSED（快照之前的有界条目数门，第 19.6.1 节；E0-R2 closure review）
P4-C8-E0-R1-02       : CLOSED（lineage 固定预算与多代保留不变量，第 19.6.7、19.6.10、26 节；E0-R2 closure review）
P4-C8 E0-R1          : REVIEWED — R-01 / R-03 CLOSED，R-02 OPEN
P4-C8 E0-R2          : REVIEWED — PASS（R-02、R1-01、R1-02 CLOSED）
P4-C8 E0             : ACCEPTED / CLOSED（FINAL REVIEWED DOCS HEAD 9e118dea32361ec19b0a84f84b6e5da0fbd134bc）
P4-C8 S1 Input       : 9e118dea32361ec19b0a84f84b6e5da0fbd134bc
P4-C8 S1             : ACCEPTED / CLOSED（FINAL REVIEWED CODE HEAD e8f83e986d3cb306a425d666f3bc0a2738dab823）
P4-C8 S2             : ACCEPTED / CLOSED（FINAL REVIEWED CODE HEAD 8c5ba6e808a6c45ee2342af497458fe88af5ff09）
P4-C8 S3             : ACCEPTED / CLOSED（FINAL REVIEWED CODE HEAD 7fb6bfb2d230d90d240a0a4b462332d27afe77d5）
P4-C8 S4             : ACCEPTED / CLOSED（FINAL REVIEWED CODE HEAD 4933f38bd09101766643af0b66757080565a8619）
P4-C8 S5             : IMPLEMENTED — INDEPENDENT REVIEW REQUIRED
P4-C8 Implementation : IN PROGRESS
P4-C8                : NOT CLOSED
P4-C9                : NOT STARTED
Phase 4              : NOT CLOSED
```

## 附录 A. 裁决记录（E0）

| # | 裁决 | 理由 |
|---|---|---|
| 1 | 新顶层 package `fc2_organizer.orchestration` | 与既有 package 职责分离；P4-C7 §30 / §34 把批量编排明确划给 P4-C8 |
| 2 | execute 消费 preview 中的 sealed preflight（方案 A） | 所见即所执行（封印 + 指纹）；漂移由 P4-C7 执行时重新校验捕获；不引入新机制 |
| 3 | 复用 Phase 3 `BatchScheduler` / `BatchConfig` / `BatchResult` / `BatchLineage` / `retry_failed` / `apply_retry` | 不重复造 Phase 3 已冻结的机制 |
| 4 | P4-C8 lineage = metadata 账本 lineage | 一条链只有一个出处令牌 |
| 5 | 不新增 `SUCCESS` / `PARTIAL` / `FAILED` 枚举；复用 `ExecutionStatus` 与 `BatchItemStatus`，P4-C8 枚举用不同名称 | 杜绝同名不同义 |
| 6 | 番号只从文件 basename 识别 | 不猜测；与 Phase 1 语法和 P4-C1 “发现不解析” 的分工一致 |
| 7 | 批内冲突：两阶段检测、全部阻断、不选胜者 | fail closed；选择胜者等于替用户决定库副本 |
| 8 | preview 的同步阶段内联、不用线程 | 只读、快速、确定；无孤儿线程 |
| 9 | execute 同步 + 有界线程 + 协作式取消 | 文件系统 syscall 不可异步中断；保留结果与 checkpoint |
| 10 | `filesystem_workers` 默认 1 | 大文件复制在同一磁盘并行通常更慢；最易推理；可配置到 8 |
| 11 | `REJECTED` 仅限 P4-C7 §15.5 保证在文件系统访问之前抛出的六种类型；其他异常 `ABORTED` | 零访问与状态未知必须区分 |
| 12 | 致命异常：排空进行中条目后原样传播，不返回部分结果 | 与 Phase 3 §7、P4-C7 §29 一致；从不放弃正在修改文件系统的线程 |
| 13 | 五类可重试 + `NONE`；`ABORTED` / `REJECTED` / 确定性拒绝不可重试 | 只有能改变结果的重试才被提供；未知状态交给人工 |
| 14 | 重试复用保留的 plan / manifest，不重新获取网络数据（metadata 失败除外） | 执行的仍是用户确认过的内容；RESUME 必须如此（指纹绑定） |
| 15 | 进程内一次性登记：preview 执行、结果重试、重试结果合并 | 一个 lineage 在进程内只有一条前进的链；fail fast |
| 16 | 结算条目释放 `RetryMaterial` | 限制结果对象的内存占用 |
| 17 | 不做进度流、跨进程协调、持久化、诊断输出 | 超出 v1.0 或属于 P4-C9 / 调用方 |
| 18 | metadata `PARTIAL` 不自动重新刮削 | Phase 3 C4 冻结；执行后重刮需要覆盖 |
| 19 | library_root 语义校验留给 P4-C2 逐条完成 | 其 helper 非公开 API；不复制校验逻辑 |
| 20 | 既有架构守卫六处最小授权更新 | 与 P4-C3..P4-C7 先例一致；新增更严格断言 |
| 21 | （E0-R1）批级 `BatchOutcome`（`SUCCESS` / `PARTIAL` / `FAILED`）为 `items` 的纯派生属性；`SUCCESS ⇔ s == total`，`PARTIAL ⇔ s + p >= 1 且 s < total`，否则 `FAILED`；空结果为 `SUCCESS` | 满足 v1.0 批级最终状态要求；不存储、不可能与 summary 矛盾；只有“全部完成”才是 SUCCESS；FAILED 精确表示“没有任何整理进展”；空结果没有未完成条目 |
| 22 | （E0-R1）`MAX_BATCH_ITEMS = 2000`（常量）与每次 preview 的保留 artifact 预算（默认 2 GiB，绝对上限 16 GiB）；单条图片预算上限 64 MiB | 两个维度同时有界；2000 覆盖 500-item 验收并留有余量；64 MiB 等于 P4-C5 默认值；默认预算在真实载荷下可容纳数百条 |
| 23 | （E0-R1）NFO 以 `4 × len` 立即计入；图片按 index 升序、以单条上限预约后才准入，完成时转为实际字节；无进行中调用仍不满足则 fail closed | 确定性（失败 index 与完成顺序、K 无关）；不等待不可能下降的账本；图片请求前就能发现 NFO 超限 |
| 24 | （E0-R1）资源超限以 `OrchestrationResourceLimitError` 使整个 `preview` / `preview_retry` fail closed；S1 的 E0 / S1 状态行治理特例 | 资源耗尽是批级调用约束，不是条目业务失败；消除不存在的 “S0” |
| 25 | （E0-R2）条目数门改为快照之前的有界迭代（至多 `MAX_BATCH_ITEMS` 个引用 + 1 次溢出探测），完全不调用 `len(items)` | 真正的硬上界；资源正确性不依赖调用方 `__len__`；超大输入只读取 2001 个元素 |
| 26 | （E0-R2）lineage 固定预算 `retention_budget_bytes`，由主 preview 记录并被所有后续模型原样携带；跨 orchestrator 预算必须相等 | 杜绝代际之间预算漂移；`merge_retry` 可仅凭模型自身验证 |
| 27 | （E0-R2）`preview_retry` 可用额度 `B - base_retained`，`base_retained` 只计未参加本轮重试的条目 | 归纳保证每个当前完整结果 `<= B`，上界与 generation 数无关；在 `preview_retry` 成功返回前就保证可合并 |
| 28 | （E0-R2）`merge_retry` 在登记之前做预算一致与合并后载荷的纵深防御；模型构造时强制结果保留不变量 | 纵深防御而非第一道发现点；失败不消费重试结果 |

无需项目所有者决定的外部业务问题：以上裁决全部落在“仓库 / 合同 / 历史已有答案”或“存在明显更安全的 fail-closed 默认方案”
的情形内（Owner Question Gate 三条件不同时满足）。
