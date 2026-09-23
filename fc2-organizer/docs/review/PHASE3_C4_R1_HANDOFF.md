# PHASE3_C4_R1_HANDOFF.md

```text
Phase: Phase 3 / C4-R1 — Incremental Closure Round

Original C4 Base:
03d62702b59a6736a858081bc1e7774d6edb29af

Reviewed-Failed C4 Code Head:
e633b403c0a420d033a6bf9289bdd0d249048368

C4 Docs Head / C4-R1 Base:
adbf56408db2d89b0db7e111f4bdf27e6b500d41

PHASE3_C4_R1_CODE_HEAD (code is FROZEN):
d28e500db57149f03e43746d9f5685fb0b9fac2e

PHASE3_C4_R1_DOCS_HEAD:
the commit "docs(review): add Phase 3 C4 R1 handoff" whose parent is the R1 Code Head above and whose only
change is this file (diff R1_CODE_HEAD..R1_DOCS_HEAD). A commit cannot contain its own hash, so it is identified
by that rule and reported in the hand-back message.

Branch:
claude/phase-0-amane-integration-fnvhpq   (normal fast-forward pushes; no reset / rebase / amend / squash / force;
                                           the original C4 history is intact)

Python: 3.12.10
```

**这不是 PASS / CLOSED 声明。** 这是提交给 C4-R1 独立关闭复查的候选。C5 **NOT
STARTED**，本文件也不解锁 C5。

复查范围：`git diff adbf564 d28e500` — 9 个文件：`batch/{__init__,models,retry,scheduler}.py`、批处理合同规格、
一个新测试文件（`test_batch_r1_closure.py`）以及三个为适应新 API 而调整的现有批处理测试文件。
`aggregation/**`、`sources/**`、`http/**`、`tools/**`、`docs/acceptance/**` 以及冻结的 C3 证据都**没有改变**（diff 为空）。
复查者已经接受的调度架构 — `min(M,N)` 个 worker、有界准入、稳定排序、以原始 index 作为重复项的身份、调用方取消、
同一轮事件循环中的致命停止、调用方取消的准入守卫、retry-only-FAILED、generation 模型、100-item 门槛的结构、大 N 的架构 —
**没有被重写**。

## 测试

| | 计数 |
|---|---|
| R1 base（`adbf564`）collected / passed | 1850 / 1850 |
| R1 Code Head（`d28e500`）collected | **1927** |
| passed / failed / skipped | **1927 / 0 / 0**（`-v` 和 `-q` 都是） |
| 新测试 | 77 = `tests/unit/batch/test_batch_r1_closure.py` 中的 73 个 + `test_batch_models.py` 中的 4 个 |

在冻结的代码树上运行的命令：`python --version`、`python -m pytest --collect-only -q`、`python -m pytest -v`、
`python -m pytest -q`。本轮的任何一次全量运行都没有出现计时失败（原有的 C2 墙钟测试 `test_17_total_deadline…`
每次都通过）。重新检查了与顺序无关性（批处理测试分别在会清理 `sys.modules` 的 `tests/contract` 之前和之后运行）。

## C4-R1-01 — 普通 `Exception` 的元数据提取不得变成批处理级致命错误（MEDIUM）

* **根因。** `_type_name(obj)` 读取 `type(obj).__name__`，并且只捕获 `Exception`。普通异常类上一个恶意的 *metaclass*
  `__name__` property，可以在 `_run_item` 的 `except Exception` 块内部抛出 `KeyboardInterrupt` / `SystemExit` /
  `GeneratorExit` / 自定义 `BaseException`；它以 `BaseException` 的形式逃逸出去，worker 把它当作致命错误，于是一次普通的
  条目失败中止了整个批处理。（`isinstance(candidate, AggregationResult)` 也存在同样的问题，因为它会查询 engine
  返回对象的 `__class__`。）
* **改动。** `_type_name` 现在**不运行任何由调用方控制的代码**，也不会抛出异常：`type(obj)`（从不查询
  `obj.__class__`）→ metaclass 不是普通 `type` 的类不被信任 → `UnknownType`；否则通过
  `type.__dict__["__name__"].__get__(cls, type)`（C 层面的 getter，绕过任何 metaclass property）读取名称，并且只有当它是
  **严格的** `str`、合法标识符、≤ 128 个字符时才使用。engine 的结果用 `type(candidate) is AggregationResult` 检查。
  没有任何地方调用 `str(exc)`、`repr(exc)`、`exc.args` 或接触 traceback。
  `BatchItemResult.error_type` 还额外要求严格的 `str`。
* **测试**（`test_batch_r1_closure.py`）：metaclass 的 `__name__` 会抛出
  `RuntimeError` / `KeyboardInterrupt` / `SystemExit` / `GeneratorExit` / 自定义 `BaseException` 的普通 `Exception` →
  `FAILED`、`ENGINE_EXCEPTION`、`error_type == "UnknownType"`，同级任务继续，批处理正常返回，恶意代码从未运行
  （一个共享的 `HOSTILE` 日志由 autouse fixture 断言为空），没有 secret 文本，通过 weakref 证明没有保留任何异常对象；
  带恶意 `__class__` property 的 engine 结果 → `RESULT_CONTRACT_MISMATCH`（×5 raisers）；`_type_name` 在同样五种
  抛出方、普通名称、过长 / 非标识符名称、一个会运行 `isidentifier`/`__str__`/`__len__` 的 `str` 子类 `__name__`，
  以及一个 `ABCMeta` 类上的全函数性。
* **关闭声明。** 在条目失败路径上，任何类元数据或返回值元数据都无法执行调用方代码，因此普通的条目失败不再可能被
  升级为批处理级致命错误。
* **明确陈述的设计取舍。** metaclass 不是普通 `type` 的类（恶意的，但也包括 `ABCMeta`）以 `UnknownType` 报告，
  而不是报告其真实名称 — 这是刻意的保守做法；descriptor 读取本身已经是安全的，但任务文本要求为恶意元数据提供一个
  *安全的回退*，而且这里不会丢失任何重要的诊断价值。

## C4-R1-02 — 致命异常的载体必须不含元数据（MEDIUM）

* **根因。** `_FatalSignal.__init__` 调用了 `super().__init__(type(original).__name__)`。因此，一个带有恶意 metaclass
  `__name__` 的致命 `BaseException` 会*从载体中*抛出异常，用另一个不同的异常替换掉真正的致命异常。
* **改动。** `_FatalSignal` 是 `__slots__ = ("original",)`，`__init__` 为 `super().__init__(); self.original =
  original` — 它不从该对象读取任何内容。
* **测试。** 直接测试载体：`.original is` 该对象，且 `.args == ()`（×5 raisers）；针对一个其恶意元数据会抛出
  `RuntimeError`/`KeyboardInterrupt`/`SystemExit`/`GeneratorExit`/自定义异常的致命异常做端到端测试，串行以及带四个
  被阻塞的同级任务两种方式：`caught is original`，没有 `ExceptionGroup`/`BaseExceptionGroup`，没有部分 `BatchResult`，
  同级任务被取消**并被 await**，致命异常之后没有准入任何条目，没有孤儿任务，调度器可复用（一个恢复正常的 engine 能运行
  一个新的批次）；另外还有同一轮事件循环的竞争测试（一个事件唤醒两个 worker，第一个抛出恶意致命异常，第二个不得准入
  item 2）×5 raisers。
* **关闭声明。** 无论致命异常的类元数据做什么，调用方收到的都是那个对象本身。

## C4-R1-03 — 重试的 lineage（LOW）

* **根因。** `apply_retry` 只能比较*形状*（generation、失败下标、番号）。由批次 A 产生的重试会被任何形状相同的
  批次 B 接受。
* **改动（不是“更多的形状比较”）。** `BatchLineage(token)`：一个不透明、不可变、**按值比较**的身份
  （128 个随机位，表示为 32 个十六进制字符，经过校验），**每次 `run()` 创建一次**。`BatchResult.lineage`（默认：一个新的，
  因此手工构建的结果自成一个批次）和 `RetryBatchResult.lineage`（**必填**，没有默认值）。`retry_failed` 复制
  `previous.lineage`；`apply_retry` 要求 `retry.lineage == previous.lineage`（在类型检查之后的第一项检查），并把
  `previous.lineage` 赋给合并后的结果，因此身份会沿 0 → 1 → 2 → … 一直延续。`lineage` 不参与相等比较，也不出现在
  `repr` 中。重复项的身份没有改变（仍然是原始 index）。**合同陈述：** 它是一个内存中的出处令牌，不是持久化格式；
  持久化 / 恢复需要真正的批次 id（记录为 C4-N1）。
* **测试。** 对*相同*输入、带*相同*失败（包括重复项）的两次独立运行：旧检查能看到的一切都被断言为完全相同
  （失败下标、番号、generation、重试下标），而 `apply_retry(B, retry_A)` → `BatchRetryError("… lineage …")`，
  `apply_retry(A, retry_A)` 则被接受；在同一个调度器上对相同输入的第二次运行是不同的 lineage；lineage 在
  主运行 → 重试 → 合并 → retry₂ → merged₂ 的过程中保持相等，并且在 generation 2 时跨链会被拒绝；正确的重试被接受，
  `previous` 不被触碰；重复番号的身份没有改变；按值相等重建的 lineage 仍然匹配，而手工构建的、条目相同的批次则不匹配；
  以及针对 `BatchLineage` 校验 / 不可变性 / 互不相同，和必填的 `RetryBatchResult.lineage` 的模型测试。
* **关闭声明。** 重试只能被合并到产生它的那条执行链中，无论另一个批次看起来多么相似。**已知局限：** 调用方可以用
  复制来的 token 构造 `BatchLineage(token)`，从而伪造一个匹配的 lineage；按设计，这防范的是意外，而不是对手（仅在内存中）。

## C4-R1-04 — 忙碌检查优先的语义，以及不会挂起的忙碌回归测试（LOW）

* **根因。** 忙碌检查在参数预处理之后才运行，因此忙碌时的 `run(invalid)` 返回 `BatchInputError`，忙碌时的
  `retry_failed(invalid)` 返回 `BatchRetryError`。并且如果去掉守卫，忙碌回归测试会永远阻塞在它的闸门上。
* **改动。** `run()` 和 `retry_failed()` 都以 `self._claim()` 开始（它要么抛出 `BatchBusyError`，要么设置标志），
  其余一切 — 包括校验 — 都在 `try … finally: self._busy = False` 之内运行。被拒绝的调用永远不会触碰活动运行的标志。
  空闲调度器上的校验错误没有改变，并且让调度器保持空闲。
* **测试。** `busy_probe`：保持一个运行处于打开状态，发起十一种第二次调用（合法运行、空运行、脏元素、裸 `str`、set、
  `None`、`str` 子类、合法重试、`None` 重试、`object()` 重试、`RetryBatchResult` 重试）→ 每一种都必须是
  `BatchBusyError`，额外的 engine 调用为**零**，之后占用必须仍然被持有，被保持的运行能够完成（没有孤儿任务）。
  该探测不会挂起：只有被保持运行的番号会被闸门阻塞（守卫缺失会表现为“直接返回”），第二次调用处于 `asyncio.timeout`
  之下，释放 / await 在 `finally` 中进行。`test_batch_concurrency.py` 中原有的忙碌测试也做了同样的处理。一个使用
  `UnguardedScheduler` 的自测证明两种守卫失效的模式都会被**报告**（第二次调用直接返回 / 第二次调用会阻塞 → 看门狗 0.2 s），
  并且 `leftover == []`。
* **关闭声明。** 忙碌检查优先已在合同中冻结（§2）并被固定下来；现在去掉守卫会在约 ~5.6 s 内失败，而不是挂起。

## C4-R1-05 — 严格的字符串元素（LOW）

* **根因。** `isinstance(element, str)` 接受了 `str` 子类：错误报告可能调用恶意的 `__repr__`，而一个值为规范形式的
  子类实例会在未被转换的情况下流入 engine 和 `BatchItemResult.number`。
* **改动（合同：拒绝，fail closed）。** 批次元素必须满足 `type(element) is str`（然后才经过现有的
  `require_canonical_number`）。子类 — 无论值是否规范 — 都以 `BatchInputError` 拒绝；它的任何方法都不会运行；
  它只以类名报告（`<HostileStr>`）；`_short` 只对严格的 `str` 调用 `repr`。
  `BatchItemResult.number` 同样要求严格的 `str`。文档中给出的上游补救方式是 `str.__str__(x)`（得到严格的 `str`
  副本，不调用任何覆盖方法）。
* **测试。** 恶意子类（每个方法都会记录并抛出 `RuntimeError` / `KeyboardInterrupt` / `SystemExit` /
  `GeneratorExit` / 自定义异常）× 规范值与非法值 → `BatchInputError`，消息写出 `<HostileStr>`，没有 `SECRET` 文本，
  engine 调用为零，恶意日志为空；即使值规范，良性子类也会被拒绝；只有严格的 `str` 对象才会到达 engine 和结果；
  `str.__str__` 补救方式有效；200 个恶意非法元素仍使消息保持有界（`200 element(s)`，< 2 KB）；模型层的严格 `str` 检查。
* **关闭声明。** 任何由调用方控制的字符串子类都无法把 `__repr__` / `__str__` / 切片 / 类型元数据带入批处理核心。

## 变异检查

每次只对干净的源码应用一个变异（超时 120 s，测量耗时）；全部被**杀死**：
恢复只捕获 `except Exception` 的 `_type_name` · 去掉不可信 metaclass 检查 · 对 engine 结果使用 `isinstance` ·
在载体中重新引入 `type(original).__name__` · 去掉 lineage 检查 · `retry_failed` 生成新的 lineage ·
合并结果生成新的 lineage · 在 `run()` 中把忙碌检查移到校验之后 · 在 `retry_failed()` 中也这样做 · **完全去掉忙碌守卫
→ 在 5.6 s 内失败，没有挂起** · 在 `validate_batch` 中使用 `isinstance(element, str)`（也会被其后模型的严格 `str`
检查捕获）· `_short` 对 `str` 子类调用 repr。原来的 11 个 C4 变异体（驱动任务取消检查、`stopping` 标志、每个条目一个
任务、`M+1` 个 worker、吞掉的自我取消、泄漏的异常文本、按完成顺序给出结果、去重、重试 PARTIAL、忙碌守卫）被重新运行，
仍然全部被杀死。恶意抛出方以 `RuntimeError` 排在第一个进行参数化，这样回归会以干净的断言失败，而不是中止测试运行器。
变异脚本位于任务临时目录，没有提交。

## 冻结前重新运行的离线门槛（结果未变）

* **100-item 阶段门槛**（`test_batch_stage_gate_100.py`，未改动）：PASS — 100 个条目各统计一次，按输入顺序，peak ==
  limit，隔离，精确的失败子集重试，两轮重试，零孤儿任务。
* **大 N**，由一个一次性脚本在冻结的代码树上测得：`N = 10,000`、`M = 4` → 10,000 个条目被统计，10,000 个唯一下标，
  顺序稳定，**peak 4**，在 engine 内部采样到的最大存活任务数为 **5**（1 个调用方 + 4 个 worker），0 个孤儿任务。
  barrier 测量（4 个调用被保持打开）：存活任务 **6**（= `asyncio.run` 主任务 + `run()` 任务 + 4 个 worker），存活的
  `aggregate` coroutine 对象 **4**，已准入条目 **4**；两个对照测试（每个条目一个任务、预先构建 N 个 coroutine）
  通过同样的测量仍然显示 ≥ 2000 个存活任务 / coroutine。

## 延续的待办 — R1 未修复

* **C2-L2 — LOW / OPEN。** **触发条件已经出现**：`BatchItemResult.aggregation_result` 透明地暴露了
  `AggregationResult`，包括其 `source_execution_traces`（批处理层从不读取也不依赖它们；R1 没有触碰
  `SourceExecutionTrace`）。它必须在以下任何一项发生**之前**被**关闭** — 收紧 `SourceExecutionTrace` 的校验器，或冻结
  一条明确的“可信生产者诊断信息”声明：(1) 持久化 / 报告 / UI / NFO / CLI 序列化或展示 trace；(2) C5 的熔断器 /
  按 host 限流器读取 trace 字段；(3) 生产环境接受一个 trace 不可信的非 `MultiSourceEngine` 生产者。
  如果 C5 从不读取 trace，则可以继续携带这一项。
* **C3-N1 OPEN LOW** — 在将来复用 `tools/run_50id_coverage_gate.py` 之前：固定预期集合的路径 / blob，**并且**通过
  *已提交*的证据检测是否已存在 Primary 运行，而不能只依赖传入的 `--out-dir`。· **C3-N2 LOW**（证据集合的 hash
  依赖工作区的换行符）· **C3-N3 LOW**（attempt-1 候选池的可追溯性不完整）· **C3-N4 LOW**
  （50-ID 验收总体来自 torrent 索引 / 首页前缀抽样；任何 “98%” 都表示 **在冻结的 C3 50-ID 验收总体上 98% 的聚合并集
  覆盖率**，绝不表示 FC2 目录覆盖率）。
* P2-R-05 LOW · P2-R-06 LOW · P2-R-07 部分缓解 LOW · P2-R-10 LOW · F3 DEFERRED · F5 DEFERRED · F4 CLOSED ·
  **C4-N1**（lineage 令牌只存在于内存中；在持久化或恢复结果之前需要设计真正的批次 id）。
* 超出 R1 范围的残留观察：`validate_batch` 的*容器*检查（`isinstance(numbers, …)`、`tuple(numbers)`）仍然会查询调用方
  自己的容器对象；恶意容器会在任何 engine 调用之前从 `run()` 中抛出异常，这属于调用方参数错误，而不是被升级的条目失败。

## 尚未开始

熔断器（**C5 NOT STARTED**）· 按 host 的限流器 · 持久化 / DB · NFO writer · 图片下载器 · 文件系统重命名 / 移动 ·
Amane adapter · GUI · 最终的 500-item 失败注入验收 · 任何线上批量抓取。

READY FOR C4-R1 INDEPENDENT CLOSURE REVIEW
