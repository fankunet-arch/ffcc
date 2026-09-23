# FC2 Metadata Core — Phase 3 / C4 批处理调度器合同（Batch Scheduler Contract）

状态：**在 Phase 3 C4 冻结，由 C4-R1 修订**（候选；独立关闭复查待进行）。
C4-R1（本次修订）关闭 finding C4-R1-01 … C4-R1-05，并且**只**修改了下文标注 *(R1)* 的各点；
调度架构（§5 有界准入、排序、重复项身份、取消、generation 模型）没有改变。
以 `PHASE3_AGGREGATION_CONTRACT.md`（C1）和 `PHASE3_RESILIENCE_CONTRACT.md`（C2/C3）为基础。
Package：`fc2_metadata_core.batch`（`config.py`、`models.py`、`scheduler.py`、`retry.py`）。

**不在范围内，未实现（C4）：** 熔断器、按 host 的限流器 / host 速率限制、任何形式的持久化
（JSON / DB）、NFO writer、图片下载器、文件系统重命名 / 移动、Amane adapter、GUI、
最终的 500-item 验收运行。`BatchResult` 只存在于内存中；该库没有副作用。

每条规则都注明了强制执行它的测试文件（全部离线且确定；除非另有说明，均位于 `tests/unit/batch/`；
任何地方都没有墙钟断言）。

## 1. 架构与依赖方向

```text
caller (future CLI / scan layer: dirty filename -> canonical number)
        |  Sequence[str]  (canonical FC2 numbers, order = batch order)
        v
BatchScheduler(engine, BatchConfig)        <- this package
        |  await engine.aggregate(number)   (narrow Protocol; MultiSourceEngine satisfies it)
        v
MultiSourceEngine.aggregate  -> execute_sources_traced -> adapters      (C1/C2, unchanged)
```

* `batch` 依赖聚合层的**公开**合同（`AggregationResult`、`AggregateStatus`）、规范番号边界
  （`sources.base.require_canonical_number`）以及 `errors`。它**从不** import
  `sources.adapters`、`aggregation.execution` 或 `aggregation.engine`，从不重新实现 fan-out 或
  merge，也从不构造 transport 或 registry。
* `aggregation`（以及其他所有 package）**从不** import `batch`。没有循环 import。
* 没有任何模块 import `amane`。
* 调度器**复用注入的 engine**。它不创建 HTTP client / registry / adapter；这些对象的生命周期
  属于调用方（未来的 CLI / 上层）。

由以下测试强制执行：`test_batch_architecture.py`，以及 `tests/contract/test_core_independent_of_amane.py`（F4：
模块发现基于 `rglob`，因此每个 `batch/*.py` 都同时处于静态 AST 扫描和阻断 import 的动态扫描中；
C4 增加了明确断言来确认这一点）。

## 2. 两个并发预算（冻结语义）

| 旋钮 | 所在位置 | 限制的对象 |
|---|---|---|
| `AggregationConfig.max_concurrency = S` | C1/C2，每次 `aggregate(number)` 调用 | **单个条目内部**并发的**来源**执行数 |
| `BatchConfig.max_in_flight_items = M` | C4，每个 `BatchScheduler` | **跨条目**并发的 `aggregate(number)` 调用数（*全局*条目预算） |

同时进行的来源操作理论最大值 = **M × S**，并进一步受启用来源数量、单来源 deadline 和取消的限制。
C4 **没有**实现按 host 的限流器：由同一 host 提供的两个来源，或大量条目访问同一个来源，都**不会被
调度器**按 host 节流。*（C5：这由共享的 `SourceResourceGovernor` 负责 —
`PHASE3_RESOURCE_CONTROL_CONTRACT.md` — engine 通过 `governor=` 选择启用它，调度器完全看不到它；
C5 没有改动批处理代码。）*

`max_in_flight_items` **在调度器边界上以有界准入的方式强制执行**，而不是依靠一个供内部代码争用的
semaphore：任何时刻，该调度器下最多只存在 `M` 个 `aggregate()` 调用。

**每个调度器实例同时只有一个活动运行。** 在已经有活动运行的调度器上调用 `run()` / `retry_failed()`
会抛出 `BatchBusyError`（fail closed）— 否则两个并发运行会悄悄地把预算翻倍。该标志会在成功、
正常结束、致命异常以及取消时释放。需要独立的预算就需要独立的调度器实例（它们的预算会相加）。

**忙碌检查优先 *(R1, C4-R1-04)*。** 忙碌检查是 `run()` 和 `retry_failed()` 的**第一个**步骤，发生在查看
参数的*任何*操作之前：只要有运行处于活动状态，无论是合法的运行、非法的运行（脏元素、裸 `str`、set、
`None`、`str` 子类 …）、空运行、合法的重试还是非法的重试（`None`、类型错误），**全部**抛出
`BatchBusyError`，engine 调用次数为**零**，并且被拒绝的调用绝不会释放活动运行的占用。
占用在整个调用期间（包括校验）都被持有，并在 `finally` 中释放，因此在*空闲*调度器上传入非法参数
仍然会抛出 `BatchInputError` / `BatchRetryError`，并让调度器保持空闲。

即使守卫失效，忙碌回归测试也**不会挂起**：只有被保持打开的那次运行的番号会被阻塞（因此守卫缺失
会表现为“没有抛出异常”），每一次第二次调用都在 `asyncio.timeout` 看门狗下运行，并且被保持打开的
运行总是在 `finally` 中被释放并 await。一个自测（`UnguardedScheduler`）证明两种失败模式（第二次调用
直接返回 / 第二次调用会阻塞）都会被快速报告，并且不会留下孤儿任务。

`test_batch_concurrency.py`、`test_batch_bounded_admission.py`、`test_batch_config.py`、
`test_batch_r1_closure.py`（C4-R1-04）。

## 3. `BatchConfig`（`config.py`）

frozen dataclass，在 `__post_init__` 中校验，不可变。

* `max_in_flight_items: int`，默认值 **4**，合法范围 **1..64**（`MAX_IN_FLIGHT_ITEMS_LIMIT`）；`bool`
  不算 `int`；其他任何值都会抛出 `BatchConfigError`（在任何 engine 调用之前）。
* **没有** `continue_on_item_failure` 开关。**冻结语义：单个条目的普通失败总是被隔离，批处理总是
  继续执行。** 一个能关闭隔离的旋钮将违背项目规则“单一影片失败不得阻断其它影片”。致命的
  `BaseException`（§7）不属于条目失败，不受此影响。

## 4. 输入合同（`BatchScheduler.run`）

* 批次是一个由 `str` 组成的 `collections.abc.Sequence`：顺序有意义，因此输出是确定的。
  以下情况以 `BatchInputError` **拒绝**（engine 调用次数为零）：裸 `str` / `bytes` / `bytearray` /
  `memoryview`、任何 `Set` / `frozenset`、任何 `Mapping`、任何生成器 / 迭代器 / 其他非 `Sequence`。
* 调度器只做一次**快照**（`tuple(numbers)`）；之后调用方再修改自己的 list 不会产生任何影响。
* 每个元素都必须是**严格的内置 `str`** *(R1, C4-R1-05)*，并且能通过现有的规范番号边界
  （`require_canonical_number`，严格为 `FC2-` + 5..8 位数字，例如 `FC2-1234567`）。**调度器中
  没有第二个 FC2 解析器，也不做任何规范化。** 脏输入（`abc FC2PPV-1234567.mp4`、
  `fc2ppv 1234567`）必须先由上层的扫描 / 规范化层处理；它在这里会被**拒绝**，而不是被修复。
* **`str` 子类会被拒绝 — fail closed — 即使其值是规范的。** 检查方式是
  `type(element) is str`；子类的任何方法（`__repr__`、`__str__`、`__eq__`、`__len__`、
  `__getitem__`、`isidentifier`、…）都绝不会被调用，被拒绝的元素**只以类名**报告
  （`<HostileStr>`），因此调用方控制的任何内容都无法进入 engine、`BatchItemResult.number` 或
  错误消息。（持有子类实例的调用方应在上游转换，例如 `str.__str__(x)`，它会在不调用任何覆盖方法的
  情况下得到一个严格的 `str`。）`BatchItemResult.number` / `error_type` 同样要求严格的 `str`。
* **全有或全无的校验：** 只要有任何一个元素非法，整个批次都会在任何 `aggregate()` 调用*之前*以
  `BatchInputError` 被拒绝；消息会列出出问题的下标（最多 10 个，总数始终会统计），并附上**仅针对严格
  `str` 元素**截断后的 `repr`（其他元素只显示其类名），绝不会进行部分运行。
* **空输入是合法的**：返回 `BatchResult(items=(), generation=0)`，`total == 0`，所有计数均为 `0`；
  engine 永远不会被调用；任何地方都没有除法。
* **重复项作为独立的工作条目保留**（批次是一个执行列表；同一个番号之后可能来自两个文件）。
  每个条目由其**原始 `index`** 标识，绝不按番号标识；任何地方都没有去重，也没有 `dict[number]`。
  两个相同的番号 ⇒ 两次独立的 `aggregate()` 调用，以及 `index` 为 0 和 1 的两个 `BatchItemResult`。

`test_batch_input.py`、`test_batch_r1_closure.py`（C4-R1-05）。

## 5. 调度模型：有界 worker 准入（`scheduler.py`）

* 创建 `min(M, len(work))` 个 **worker 任务**（绝不会为每个条目创建一个任务）。worker 从共享游标中
  取下一个位置，并**直接在 worker 中** `await engine.aggregate(number)` — 批处理层永远不会创建
  按条目的任务。因此存活的批处理任务数是 `O(M)`，与批次规模无关
  （`N = 10,000` 且 `M = 4` ⇒ 在第一个 barrier 处有 4 个批处理任务 + 调用方的任务）。
  调度器也从不一次性生成 `N` 个 coroutine 对象。
* `M = 1` ⇒ 严格串行；`M > N` ⇒ 峰值 = `N`；峰值永远不超过 `M`。
* 内存只在结果槽位上是 `O(N)`（每个槽位一个指针）；`BatchItemResult` 对象在条目完成时才创建。
* 一旦发现致命异常或取消，准入立即停止（§7）。在**每一次**准入之前，worker 都会检查：
  (a) 运行本地的 `stopping` 标志，它由发现致命信号的那个 worker 同步设置；以及 (b) 驱动任务
  （正在 await `run()` / `retry_failed()` 的那个任务）是否有**新的**待处理取消请求
  （`Task.cancelling()` 大于运行开始时的值）。(a) 消除了这样一种竞争：在同一轮事件循环中已被调度的
  同级 worker 完成了自己的条目，并在 TaskGroup 来得及取消它之前继续循环；(b) 消除了 `task.cancel()`
  与取消通过 TaskGroup 传到各个 worker 之间相差一轮的空窗。两者都由测试固定下来，删除检查会导致测试失败。
* **C4 中没有按条目的批处理级超时。** 单个条目的终止由 engine 内部 C2 的单来源总 deadline 保证。
  永远不返回的用户自定义 engine 会永久占用它的槽位（已记录的局限；现已采用的 `MultiSourceEngine`
  不会如此）。

`test_batch_bounded_admission.py`（包括一个*对照*测试，证明该测量方法能识别出朴素的
`create_task × N + semaphore` 调度器：那种调度器会显示 `N` 个存活任务）。

## 6. 结果模型（`models.py`）与状态映射

全部不可变（`frozen=True, slots=True`），只使用 tuple，不变量在 `__post_init__` 中强制执行
（`BatchContractError`）。

`BatchItemResult`：`index`、`number`、`status: BatchItemStatus`、`aggregation_result | None`、
`error_kind: BatchItemErrorKind | None`、`error_type: str | None`、`generation`、`elapsed_ms`。

| Engine 结果 | `status` | `aggregation_result` | `error_kind` / `error_type` |
|---|---|---|---|
| 返回 `AggregationResult` `SUCCESS` | `SUCCESS` | 该结果 | `None` / `None` |
| 返回 `AggregationResult` `PARTIAL` | `PARTIAL` | 该结果 | `None` / `None` |
| 返回 `AggregationResult` `FAILED` | `FAILED` | 该结果（保留全部 `SourceResult`） | `None` / `None` |
| 抛出普通 `Exception` | `FAILED` | `None` | `ENGINE_EXCEPTION` / 异常的**类名** |
| 返回非 `AggregationResult`，或针对另一个番号的结果 | `FAILED` | `None` | `RESULT_CONTRACT_MISMATCH` / 返回对象的**类名** |

批处理状态与 `AggregateStatus` 是 1:1 映射；没有发明新的来源状态。不变量：`aggregation_result` /
`error_kind` 两者恰好设置其一；`aggregation_result.number == number`；`status` 是
`aggregation_result.status` 的映射结果。

**不泄漏 secret：** 对于普通异常，只记录其**类名** — 绝不记录 `str(exc)`、`repr(exc)`、`args`、
traceback 或异常对象本身。调度器不保留对该异常的任何引用。

**元数据提取是全函数 *(R1, C4-R1-01)*。** `_type_name(obj)` **不运行任何由调用方控制的代码**，也不会
抛出异常：先取 `type(obj)`（它从不查询 `obj.__class__`），再通过 `type.__name__` 自身的 descriptor
读取类名（这会绕过恶意 *metaclass* 定义的任何 `__name__` property），最后才检查该名称是否是**严格的**
`str`、是否为合法标识符且 ≤ 128 个字符。metaclass 不是普通 `type` 的类（恶意的，但也包括例如
`ABCMeta`）**不被信任**，得到 `UnknownType`；任何异常的名称也是如此。因此，任何类元数据都无法把一次
普通的条目失败变成批处理级致命错误。同一规则也适用于 `RESULT_CONTRACT_MISMATCH`：
engine 的返回值用 `type(candidate) is AggregationResult` 检查（严格类型；`isinstance` 会查询
候选对象的 `__class__`，也就是 engine 所控制的代码），其类型名用 `_type_name` 获取。

**血统（Lineage）*(R1, C4-R1-03)*。** `BatchLineage(token)` 是一次批处理执行链的不透明、不可变、
**按值比较**的身份标识：128 个随机位（32 个十六进制字符），**每次 `run()` 创建一次**。由该次运行派生出的
每一个 `BatchResult` 和 `RetryBatchResult` 都携带相同的 lineage（主运行 → 重试 → 合并 → 下一次重试 → …）；
`retry_failed` 把 `previous.lineage` 复制到自己的结果中，`apply_retry` 把它复制到合并后的结果中。
手工构建的 `BatchResult` 会得到一个新的 lineage；`RetryBatchResult.lineage` 是必填项（没有默认值），因此
出处总是显式的。`lineage` 不参与相等比较，也不出现在 `repr` 中（相等性按内容判断）。它是一个
**内存中的出处令牌，而不是持久化格式**；如果将来要持久化或恢复结果，届时必须设计真正的批次 id
及其存储合同（C4-N1）。

`BatchResult(items, generation, lineage)`：`items` 按**输入顺序**排列，`index == position`（`0..n-1`，连续）；
派生属性有 `total`、`success_count`、`partial_count`、`failed_count`、`failed_items`、`failed_indices`、
`failed_numbers`（与 `failed_indices` 对齐的 tuple；可以包含重复番号）。不存储冗余的计数
（因此不会出现自相矛盾）。**没有引入批次级的整体状态枚举**：`AggregateStatus.PARTIAL`
已经有其含义，而计数本身没有歧义。

`RetryBatchResult(items, generation, lineage)`：只包含被重试的条目，`index` 严格递增，每个
`item.generation == generation >= 1`；派生计数相同。

`test_batch_models.py`、`test_batch_status_mapping.py`、`test_batch_r1_closure.py`（C4-R1-01/03）。

## 7. 致命异常与取消（与 C1/C2 §4 一致）

* **调用方取消批处理**（`run()` 任务被取消）：`CancelledError` 原样传播；每个正在运行的 worker
  （并经由它取消 engine 自己的任务组）都会被取消**并被 await**；尚未准入的条目**永远不会开始**；
  没有任何任务的生命周期超过这次调用。
* **由 `engine.aggregate` 抛出的 `KeyboardInterrupt`、`SystemExit`、`GeneratorExit`、任何其他非
  `Exception` 的 `BaseException`**，以及 engine **自行**抛出的 `CancelledError`（没有人取消它）：
  均为致命控制流。准入立即停止，同级任务被取消并被 await，**原始异常对象**被重新抛给调用方 —
  绝不是 `BaseExceptionGroup`/`ExceptionGroup`，绝不是 `BatchItemResult`，也绝不是 `FAILED`。
  （与*来源* adapter 不同：C2 会把 adapter 自行抛出的 `CancelledError` 变成来源失败；而批处理级的
  `CancelledError` 总是被传播：在这里吞掉它会让整个批处理丢失取消语义。）
* **致命异常的载体不含元数据 *(R1, C4-R1-02)*。** worker 把致命异常装在内部的 `_FatalSignal` 中交给
  任务组，该载体只是*持有*原始对象：它**不从中读取任何内容**（不读类名、文本、`args`、`repr`）。
  因此，带有恶意 metaclass / `__name__` / `__repr__` 的致命异常，无法用载体抛出的错误替换掉自身：
  调用方收到的仍然是**原始对象**（身份一致），同级任务被取消并被 await，此后不再准入任何条目，
  不返回任何部分结果，调度器仍可复用 — 对于恶意代码会抛出 `RuntimeError`、`KeyboardInterrupt`、
  `SystemExit`、`GeneratorExit` 或自定义 `BaseException` 的恶意元数据 `BaseException` 均是如此。
* 如果多个致命异常发生竞争，其中一个以原始对象传播（C2-L5）；其余的不予保留。
* 发生致命异常后，不返回任何部分 `BatchResult`。
* 已知局限（与 C2 相同）：吞掉 `CancelledError` 并继续运行的 engine 无法被中断。

`test_batch_fatal_and_cancellation.py`、`test_batch_isolation.py`、`test_batch_r1_closure.py`（C4-R1-01/02）。

## 8. 失败子集重试（`retry.py`、`BatchScheduler.retry_failed`）

* `retry_failed(previous: BatchResult) -> RetryBatchResult` **只重新执行 `FAILED` 条目**，按
  **原始 index** 选择（绝不按番号选择：若为 `index0 SUCCESS FC2-X` 和 `index1 FAILED FC2-X`，则只重试 index 1）。
  `SUCCESS` 和 `PARTIAL` 条目永远不会被重试（C4 刻意没有提供 `retry_partial` 选项）。
  它使用同样的有界 worker 模型以及同样的致命异常 / 取消规则。
* **Generation：** 主运行 = generation `0`；对 generation 为 `g` 的结果做重试，得到 generation `g + 1`。
  每个 `BatchItemResult.generation` 表明它是由哪一轮产生的。没有任何可重试条目的重试轮次
  仍然算一轮（`RetryBatchResult(items=(), generation=g+1)`）。`previous` 永远不会被修改。
* `apply_retry(previous, retry) -> BatchResult` 是一个**纯**函数，按原始顺序生成一个**新的**结果，
  其中只有被重试的条目被替换（未重试的条目是同一批对象）。除非满足以下全部条件，否则它
  **fail closed**（`BatchRetryError`，不返回任何内容）：两者类型正确；
  **`retry.lineage == previous.lineage`** *(R1, C4-R1-03：由批次 A 产生的重试会被任何其他批次拒绝，
  包括番号、失败下标和 generation 完全相同的批次 — 仅比较形状永远无法区分它们)*；
  `retry.generation == previous.generation + 1`（拒绝过期 / 重放的重试）；重试的下标
  **严格等于** `previous.failed_indices`；并且每个被重试条目的 `number` 与原结果在该下标处的番号相同。
  合并后的结果保留 `previous.lineage`，因此 lineage 会沿 generation 0 → 1 → 2 → … 一直延续；
  重复番号不受影响（身份仍然是原始 index）。
* 重试结果永远不会被隐式合并：由调用方负责应用。

`test_batch_retry.py`、`test_batch_r1_closure.py`（C4-R1-03）。

## 9. 测试矩阵

| 要求 | 测试文件 |
|---|---|
| 配置校验 | `test_batch_config.py` |
| Sequence 合同、拒绝无序集合、空输入、规范番号边界、脏输入、重复项、快照 | `test_batch_input.py` |
| 不可变模型 / 不变量 / 计数 | `test_batch_models.py` |
| 状态映射、`RESULT_CONTRACT_MISMATCH`、protocol | `test_batch_status_mapping.py` |
| 稳定排序、全局并发 1 / M / >N、忙碌守卫 | `test_batch_concurrency.py` |
| 有界准入（`O(M)` 个任务）、对照测试 | `test_batch_bounded_admission.py` |
| 普通异常隔离、不泄漏 secret | `test_batch_isolation.py` |
| 取消、KeyboardInterrupt / SystemExit / GeneratorExit / 自定义 / 自行抛出的 CancelledError、同级任务清理、无孤儿任务、停止后不再准入 | `test_batch_fatal_and_cancellation.py` |
| 失败子集重试、重复番号的选择性重试、generation、不匹配时 fail-closed、`apply_retry` | `test_batch_retry.py` |
| 100-item 离线阶段门槛 | `test_batch_stage_gate_100.py` |
| 大 N 压力测试（10,000 个条目，`M = 4`） | `test_batch_large_n_stress.py` |
| C4-R1-01 普通异常上的恶意元数据；C4-R1-02 致命异常上的恶意元数据；C4-R1-03 lineage；C4-R1-04 忙碌检查优先 + 不会挂起的守卫回归；C4-R1-05 严格 `str` 元素 | `test_batch_r1_closure.py` |
| 没有 `aggregation → batch`、没有 adapter import、独立于 Amane、F4 模块发现 | `test_batch_architecture.py`、`tests/contract/test_core_independent_of_amane.py` |

## 10. 延续的待办（C4 没有修复这里的任何一项）

* **C3-N1 — OPEN / LOW。** 50-ID 主门槛的防重跑 / 集合绑定守卫依靠流程约束，而不是全局强制。
  **在将来复用 `tools/run_50id_coverage_gate.py` 之前：** 固定预期集合的路径 / blob，**并且**通过*已提交*的
  证据来检测是否已存在 Primary 运行，而不能只依赖传入的 `--out-dir`。C4 不触碰冻结的 C3 runner 或证据。
* C3-N2 LOW（证据集合的 hash 依赖工作区的换行符）· C3-N3 LOW（attempt-1 候选池的可追溯性不完整）·
  **C3-N4 LOW：50-ID 验收总体来自 torrent 索引 / 首页前缀抽样。文档中出现的任何 "98%" 都表示
  “在冻结的 C3 50-ID 验收总体上 98% 的聚合并集覆盖率”，绝不表示 FC2 目录覆盖率。**
* P2-R-05、P2-R-06、P2-R-10 LOW · P2-R-07 部分缓解 LOW · F3 DEFERRED · F5 DEFERRED · F4 CLOSED。
* **C2-L2 — LOW / OPEN**（`SourceExecutionTrace` 允许 engine 永远不会产生的状态）。**它的触发条件
  现在已经出现：** `BatchItemResult.aggregation_result` 透明地暴露了 `AggregationResult`，
  包括其 `source_execution_traces`。批处理层本身既不读取也不依赖 trace 字段。
  **C2-L2 必须在以下任何一项发生之前关闭**（收紧 `SourceExecutionTrace` 的校验器，或冻结一条明确的
  “可信生产者诊断信息”声明）：(1) 持久化 / 报告 / UI / NFO / CLI 序列化或展示 trace；
  (2) C5 的熔断器或按 host 限流器读取 trace 字段；(3) 生产环境接受一个 trace 不可信的
  非 `MultiSourceEngine` 生产者。如果 C5 从不读取 trace，则可以继续携带这一项。
* **C4-N1（跨持久化的出处）：** lineage 令牌只存在于内存中；在持久化或恢复结果之前，需要设计真正的
  批次 id 和存储合同。
* 下一步（尚未开始）：C5 = 熔断器 + 按 host 限流器（各自需要独立的冻结合同）；
  最终的 500-item 失败注入验收；NFO / 文件系统 / Amane adapter。
