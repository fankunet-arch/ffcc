# PHASE3_C4_HANDOFF.md

```text
Phase: Phase 3 / C4 — Batch Scheduler Core

C4 Base (Phase 3 C3 Docs Head):
03d62702b59a6736a858081bc1e7774d6edb29af

PHASE3_C4_CODE_HEAD (final code review candidate; code is FROZEN):
e633b403c0a420d033a6bf9289bdd0d249048368

PHASE3_C4_DOCS_HEAD:
the commit "docs(review): add Phase 3 C4 batch scheduler handoff" whose parent is the Code Head above and
whose only change is this file (diff CODE_HEAD..DOCS_HEAD). A commit cannot contain its own hash, so it is
identified by that rule and reported in the hand-back message.

Branch:
claude/phase-0-amane-integration-fnvhpq   (fast-forward only; C3 history untouched)

Python: 3.12.10
```

**这不是 PASS 声明。** 这是提交给 Phase 3 C4 独立复查的候选。熔断器、按 host 的限流器、持久化、NFO writer、
图片下载器、文件系统操作、Amane adapter、GUI 以及最终的 500-item 验收都**NOT STARTED / NOT RUN**。

复查范围：`git diff 03d6270 e633b40`（21 个文件：5 个新源文件 + 顶层 `__init__.py` 中一行重新导出、1 份规格、
13 个新的测试 / 支持文件、对 F4 合同测试的 1 处修改）。
`src/fc2_metadata_core/aggregation/**`、`sources/**`、`http/**`、`tools/**` 以及每一个冻结的 C3 证据文件都**没有改变**
（`git diff --stat 03d6270 e633b40 -- src/fc2_metadata_core/aggregation src/fc2_metadata_core/sources
src/fc2_metadata_core/http tools docs/acceptance` 为空）。对现有源码的唯一修改，是
`src/fc2_metadata_core/__init__.py` 中的一行（重新导出 `batch`）。

## 测试

| | 计数 |
|---|---|
| C4 Base（`03d6270`）collected / passed | 1595 / 1595 |
| Code Head（`e633b40`）collected | **1850** |
| passed / failed / skipped | **1850 / 0 / 0** |
| 新测试 | 255 = `tests/unit/batch/` 中的 247 个 + `tests/contract/` 中的 8 个（3 个明确的 F4/Amane 测试 + 5 个新的参数化静态扫描用例，每个新的 `batch/*.py` 一个） |

在冻结的代码树上运行的命令：`python --version`、`python -m pytest --collect-only -q`、`python -m pytest -v`、
`python -m pytest -q` — 全部通过。**如实说明：** 同一代码树较早的一次全量运行中，*原有的* C2 墙钟测试
`test_agg_retry_execution.py::test_17_total_deadline_covers_attempt_backoff_and_retry_not_deadline_times_attempts`
报告了一次失败（那次运行耗时 74 s，而不是约 ~30 s）。当时机器上正在运行两个与本任务无关的 `atk_fuzz.py` python 进程
（前一天启动，不属于本任务）。该测试单独运行时通过（其文件中 56/56），在接下来的三次全量运行中也都通过。C4 的测试中
没有任何墙钟断言；C4 的测试文件被重复运行了 6×（每次 291 个通过），并且相对于会清理 `sys.modules` 的
`tests/contract` 以两种顺序都运行过。

## C4 新增的内容（`src/fc2_metadata_core/batch/`）

| 文件 | 作用 |
|---|---|
| `config.py` | `BatchConfig(max_in_flight_items)` — frozen，1..64，默认 4，拒绝 `bool` |
| `models.py` | `BatchItemResult`、`BatchResult`、`RetryBatchResult`、`BatchItemStatus`、`BatchItemErrorKind`、错误类型 |
| `scheduler.py` | `BatchScheduler.run` / `.retry_failed`、`validate_batch`、`AggregationEngine` Protocol |
| `retry.py` | `failed_work`、`apply_retry`（纯函数，fail-closed） |
| `__init__.py` | 公开接口 |

合同：`docs/specifications/PHASE3_BATCH_CONTRACT.md`（规则 → 测试文件的矩阵见 §9）。
依赖方向：`batch → aggregation (public package) + sources.base.require_canonical_number + errors + normalize`。
除了顶层 package 门面之外，没有任何模块 import `batch`；`batch` 不 import 任何 adapter，不 import
`execution`/`engine`/`merge` 内部实现，不 import transport，也不 import `os`/`pathlib`/`json`/`sqlite3`/…
（`test_batch_architecture.py`）。

## 全局并发语义

* `BatchConfig.max_in_flight_items = M` 限制**跨条目**并发的 `aggregate(number)` 调用数；现有的
  `AggregationConfig.max_concurrency = S` 限制**单个条目内部**的来源执行数。同时进行的来源操作理论最大值 =
  **M × S**（还受来源数量 / deadline / 取消的限制）。
  **没有按 host 的限流器** — 延后到 C5。
* `M = 1` 是严格串行的（调用按输入顺序开始和结束）；`M > N` 时峰值为 `N`；峰值永远不超过 `M`。
* **每个调度器同时只有一个活动运行**：并发的 `run()`/`retry_failed()` 会抛出 `BatchBusyError`（否则两次运行会悄悄地
  把预算翻倍）。在成功、致命异常和取消时释放。需要独立的预算就需要独立的调度器实例（它们的预算会相加）。
* 明确陈述的设计选择：**没有** `continue_on_item_failure` 开关 — 普通的条目失败总是被隔离。

## 有界准入的证明（不是“N 个任务 + semaphore”）

`min(M, N)` 个 worker 任务从一个共享游标中取下一个位置，并直接 `await engine.aggregate(number)`。
批处理层从不为每个条目创建任务或 coroutine。证明全部基于计数，与机器速度无关
（`test_batch_bounded_admission.py`）：`M` 个调用被保持在一个 barrier（一个 `Event`）处，然后

| 在 barrier 处测量的指标 | N = 10,000, M = 4 |
|---|---|
| 存活的 asyncio 任务 | **6** = asyncio.run 主任务 + `run()` 任务 + 4 个 worker |
| 存活的 `ScriptedEngine.aggregate` coroutine 对象（通过 `gc`） | **4** |
| 已准入的条目（已开始的 engine 调用） | **4** |

在 `N = 3000` 下对 `M ∈ {1, 4, 16, 64}` 参数化，并覆盖 `N < M`（5 个条目，M = 64 ⇒ 5 个 worker）。两个**对照**测试
用*同样的*测量方法运行一个刻意朴素的设计，证明两者可以区分：`create_task × N +
Semaphore` 报告 ≥ 2000 个存活任务（N = 2000, M = 4）；预先构建 N 个 `aggregate` coroutine 则报告 ≥ 2000 个存活
coroutine。`test_admission_is_completion_driven_one_new_item_per_freed_slot` 证明每完成一个条目，恰好准入一个新条目。

## 输入、重复项、排序

* 输入是一个有序的 `Sequence[str]`。以下情况以 `BatchInputError` 拒绝（engine 调用次数为零）：裸 `str`/`bytes`/
  `bytearray`/`memoryview`、`set`/`frozenset`、`Mapping` 及其视图、生成器 / 迭代器、`None`、其他对象。
  调度器对输入做快照（`tuple(...)`）。
* 每个元素都经过现有的 `require_canonical_number`（`FC2-` + 5..8 位数字）。**没有第二个解析器，不做规范化。**
  脏输入（`abc FC2PPV-1234567.mp4`）会被拒绝，而不是被修复 — 那是上游扫描层的工作。
  校验在任何调用之前以**全有或全无**的方式进行；消息列出出问题的下标（前 10 个），附带截断的 `repr`，并且从不调用
  恶意元素的 `repr`/`str`。
* 空输入是合法的：`BatchResult(items=(), generation=0)`，`total == 0`，engine 从不被调用。
* **重复项是独立的工作条目**，以其原始 `index` 标识（绝不用 `dict[number]`）；两个相同的番号 ⇒ 两次 `aggregate()`
  调用，以及下标为 0 和 1 的两个结果。
* **稳定排序：** 完成顺序可以是任意的（测试强制为 `E C A D B`）；`BatchResult.items` 总是按输入顺序排列；
  `failed_indices` / `failed_numbers` 遵循批次顺序。

## 状态映射、失败隔离、不泄漏

`AggregateStatus` 与 `BatchItemStatus` 是 1:1 映射（SUCCESS/PARTIAL/FAILED）；一个 FAILED 的聚合结果保留全部 `SourceResult`。

| Engine 结果 | 条目 |
|---|---|
| 返回 `AggregationResult` | 状态 = 映射结果；结果原样传递 |
| 普通 `Exception`（包括 `RecursionError`、`MemoryError`、`ExceptionGroup`） | `FAILED`、`ENGINE_EXCEPTION`、`error_type` = 类名；**同级任务和准入继续进行** |
| 非 `AggregationResult`，或针对另一个番号的结果 | `FAILED`、`RESULT_CONTRACT_MISMATCH`（fail closed） |

只记录 `type(exc).__name__`（经过净化：非标识符 / 过长 / 恶意 metaclass 的名称会变成 `UnknownType`）— 绝不记录
`str`/`repr`/`args`/traceback；一个 weakref 测试证明调度器不保留任何异常对象。

## 致命异常与取消

* 调用方取消批处理 → `CancelledError` 原样传播；正在运行的条目被取消**并被 await**（也经由真实的 `MultiSourceEngine`
  验证，因此 engine 的嵌套任务组也被覆盖到）；未准入的条目永远不会开始；没有孤儿任务；调度器之后仍可复用。
* `KeyboardInterrupt` / `SystemExit` / `GeneratorExit` / 自定义 `BaseException`（以及 *engine* 自行抛出的
  `CancelledError`）→ 准入立即停止，同级任务被取消并被 await，重新抛出**原始对象**（断言了身份一致；绝不是异常组，
  绝不是一个 FAILED item，也没有部分 `BatchResult`）。同时发生的多个致命异常：传播其中一个原始对象（与 C2-L5 规则相同）。
* 明确陈述的与 C2 的刻意差异：*来源 adapter* 自行抛出的 `CancelledError` 被隔离为 adapter 失败（C2）；而在*批处理*
  层面，engine 自行抛出的 `CancelledError` 按任务要求被传播。
* **在我自己编写测试的过程中**发现并关闭了两个准入竞争：(1) 与致命异常处于同一轮事件循环中、已被调度的同级 worker
  会完成它的条目、继续循环，并在 TaskGroup 来得及取消它之前准入下一个条目 → 增加了同步设置的运行本地 `stopping` 标志；
  (2) 在 `task.cancel()` 之后，取消要晚一轮事件循环才能到达 worker，因此一个空出来的 worker 可能再准入一个条目 →
  worker 还会把驱动任务的 `Task.cancelling()` 与运行开始时的值进行比较。

## `retry_failed` / `apply_retry`

* `retry_failed(previous: BatchResult) -> RetryBatchResult` **只重新运行 `FAILED`** 条目，按**原始 index** 选择
  （绝不按番号）；SUCCESS 和 PARTIAL 永远不会被重试；不存在 `retry_partial` 选项。使用同样的有界 worker 模型
  以及同样的致命异常 / 取消规则。
* **Generation：** 主运行 = 0；对 generation 为 `g` 的结果做重试 = `g+1`；每个条目携带它所属的轮次；空的重试轮次
  仍然算一轮。`previous` 永远不会被修改。
* `apply_retry(previous, retry) -> BatchResult` 是纯函数，保持原始顺序，并且除非满足以下条件，否则
  **fail closed**（`BatchRetryError`）：类型正确；`retry.generation == previous.generation + 1`（拒绝过期 / 重放的重试）；
  重试的下标**严格等于** `previous.failed_indices`；每个被重试的番号与原结果在该下标处的番号相同。
  未重试的条目是同一批对象。
* 重复番号的情况：`[X SUCCESS, X FAILED]` → 只有 index 1 被重试和替换。
* 没有引入：批次级的整体状态枚举（只有计数；`PARTIAL` 在条目层面已经有其含义）。

## 100-item 离线阶段门槛 — PASS

`test_batch_stage_gate_100.py`（脚本化 engine，**不是**线上抓取）：100 个条目（90 个唯一 + 10 个重复），共 10 种
计划类别 — 成功、部分成功、类似 deadline 的部分成功、永久失败的聚合、重试后恢复的普通异常、慢速成功、恢复为部分成功的
失败聚合、永久的普通异常、恢复的合同不匹配。`M = 6`。检查项：100 个条目每个恰好统计一次，下标为 `0..99`，按输入顺序，
状态与计划一致（独立于运行结果计算），每个番号的调用次数恰好等于其重复次数，peak == 6，异常 / 不匹配被记录且不含 secret，
`retry_failed` 按批次顺序恰好重新运行了失败子集（engine 调用日志），合并后的结果完整且有序，带有每个条目的 generation，
未被触碰的条目是同一批对象，第二轮重试只触碰仍然失败的条目，零孤儿任务，`engine.active == 0`。

## 大 N 压力测试 — PASS

`test_batch_large_n_stress.py`，参数化 `(N, M) ∈ {(10,000, 4), (5,000, 1), (5,000, 64)}`；没有墙钟断言。
存活任务数在**engine 内部的每一次调用时**采样：

```text
N = 10,000   configured limit M = 4   peak admitted (engine.peak) = 4   calls = 10,000
max live tasks sampled = 5  (1 caller task + ≤ 4 workers)
```

（由一个一次性脚本在冻结的代码树上测得；测试断言 `≤ M + 1` 以及 `peak == M`。）它还检查完整性、顺序、恰好一次，
以及针对 N 个条目的失败子集重试。

## 变异检查（证明测试确实有效）

每个变异都应用在一份干净的 `scheduler.py` / `retry.py` 上，然后运行批处理测试集；每次之后都恢复源码。全部 11 个都被捕获：
去掉驱动任务的取消检查 · 致命异常时不设置 `stopping` · 自我取消时不设置 `stopping` · 每个条目一个任务 ·
`workers = M+1` · 吞掉 engine 的自我取消 · 泄漏异常文本 · 按完成顺序给出结果 · 按番号去重 · 连 PARTIAL 也重试
（其中 10 个由一个失败的断言捕获）— 以及“去掉忙碌守卫”，它只以*挂起*的形式被捕获（并发运行测试会阻塞；挂起是一种
糟糕的失败模式，但它确实算是一种检测）。测试集的第一个版本让“致命异常时不设置 `stopping`”这个变异**存活了下来**；
我增加了同一轮事件循环竞争的测试
（`test_a_sibling_resuming_in_the_same_loop_iteration_admits_nothing_after_the_fatal`）来关闭这个缺口，并在冻结之前修复了
这个新测试中的一个测试框架 bug（它把自己的外层任务算成了残留任务）。变异脚本位于任务临时目录，没有提交。

## 已知局限（已记录，未修复）

* 吞掉 `CancelledError` 并继续运行的 engine 无法被中断（与 C2 相同）。
* 没有批处理级的单条目超时；单个条目的终止依赖 C2 的单来源总 deadline。一个永不返回的用户自定义 engine 会一直占用
  它的槽位。
* `apply_retry` 无法区分来自*另一个*批次、但失败下标、番号和 generation 完全相同的重试。它会拒绝所有它能观察到的不匹配。
* `BatchItemResult.aggregation_result` 携带完整的 `AggregationResult`，**包括其执行 trace**。
  C3 说过，C2-L2（公开的 trace 模型允许 engine 永远不会产生的状态）应当在*任何批处理 API 把 trace 暴露给更广泛的
  调用方之前*重新评估；C4 把这个 finding 保持为 **LOW / DEFERRED**，因为它既不读取也不依赖 trace 的不变量，
  但同时指出触发条件可以说现在已经出现 — 由复查者决定。
* 结果只存在于内存中。

## 延续的待办（以下各项都没有由 C4 修复）

* **C3-N1 — OPEN / LOW。** 主门槛的防重跑 / 集合绑定守卫依靠流程约束，而不是全局强制。
  **在将来复用 `tools/run_50id_coverage_gate.py` 之前：固定预期集合的路径 / blob，并通过*已提交*的证据来检测是否已存在
  Primary 运行，而不能只依赖传入的 `--out-dir`。** 冻结的 C3 runner 和证据没有被触碰。
* C3-N2 LOW（证据集合的 hash 依赖工作区的换行符）· C3-N3 LOW（attempt-1 候选池的可追溯性不完整）·
  **C3-N4 LOW** — 50-ID 验收总体来自 torrent 索引 / 首页前缀抽样；任何 “98%” 都表示
  **在冻结的 C3 50-ID 验收总体上 98% 的聚合并集覆盖率**，绝不表示 FC2 目录覆盖率。
* P2-R-05 LOW · P2-R-06 LOW · P2-R-07 部分缓解 LOW · P2-R-10 LOW · C2-L2 LOW / DEFERRED（见上文）·
  F3 DEFERRED · F5 DEFERRED · F4 CLOSED。

**新 package 的 F4：** `tests/contract/test_core_independent_of_amane.py` 中的模块发现基于 `rglob`，因此全部五个
`batch/*.py` 文件无需任何修改就已经被静态 AST 扫描和阻断 import 扫描覆盖；C4 增加了明确的断言来确认这一点
（这样该 package 就不会成为盲区），并增加了一个测试，在任何 `amane` import 都会抛出异常的情况下运行一次真实的批处理
（调度器 + 重试 + 合并）。

## 尚未开始

熔断器（C5）· 按 host 的限流器（C5）· 持久化 / DB · NFO writer · 图片下载器 · 文件系统重命名 / 移动 ·
Amane adapter · GUI · 最终的 500-item 失败注入验收 · 任何线上批量抓取。

READY FOR PHASE 3 C4 INDEPENDENT REVIEW
