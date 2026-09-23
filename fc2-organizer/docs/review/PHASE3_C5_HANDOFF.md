# Phase 3 / C5 Handoff — 共享 Host 资源控制与熔断器（Shared Host Resource Control & Circuit Breaker）

**C5 Base:** `83d7d6ff6e9ac21bcb3417cc7d814e9b91a814d0`（Phase 3 C4-R1 Docs Head）
**C5 Code Head:** `fb4dddaf4ef00ed201c94d9a7e29d1e86a20f17d`
**Contract:** `docs/specifications/PHASE3_RESOURCE_CONTROL_CONTRACT.md`
**Python:** 3.12.10

C5 Base 时的基线：1927 collected / 1927 passed / 0 failed / 0 skipped。
Code Head 时：**2361 collected / 2361 passed / 0 failed / 0 skipped**（434 个新测试；运行了三次，外加下面按测试集
的细分运行，全部通过）。

仅为实现者角色 — 本文是一份 handoff，而不是复查结论。确切的验收说明见 §12。

## 1. C5 新增的内容

`fc2_metadata_core.resource_control` — 一个新的叶子 package（`errors.py`、`host_key.py`、`config.py`、
`host_limiter.py`、`circuit_breaker.py`、`governor.py`），提供一个显式的、非单例的资源域：
一个共享的**按 host 的并发限流器**和一个共享的**按 source-id 的熔断器**。它只依赖
`SourceResult`/`SourceStatus`/`SourceErrorKind` 和 `errors`；不从 `batch`、`aggregation`、具体 adapter、`httpx` 或
`amane` import 任何内容（由 `tests/unit/resource_control/test_rc_architecture.py` 中的 AST 守护强制执行）。

集成是**可选启用**的：`MultiSourceEngine(config, registry, client, governor=...)`。不带 `governor=` 时，C4 的行为
逐字节不变（不推导任何 host key，甚至不检查任何 adapter 默认 URL）。带上它时：

- `MultiSourceEngine.__init__` 在构造时一次性地为每个启用的来源推导 `HostKey`，依据是其配置的 `base_url`
  （或 adapter 的 `default_base_url`），经由现有的 `aggregation.validate_base_url` 以及新增的
  `host_key_for_base_url` — 绝不从响应、重定向、错误文本或 trace 推导。无法生成 key 的 base URL 会在任何请求之前
  抛出 `AggregationConfigError`。
- `aggregation/execution.py` 的 `_execute_one` 在重试循环之前调用 `governor.admit(source_id, host)`；打开的熔断器
  会短路为一个结构化的 `NETWORK_ERROR`/`CIRCUIT_OPEN` 结果，attempt 次数为**零**，也不占用 host 许可。否则，每次
  attempt 都会获取 host 许可、重新确认准入仍然有效、执行 fetch，然后释放许可 — 重试的退避暂停期间不持有许可。
  票据在 `finally` 中由恰好一次 `record_result`（最终结果）或 `release`（取消 / 致命 / 未尝试）结算。

## 2. Host key

`HostKey(host: str, port: int)` — frozen、可哈希、有序。`host_key_for_base_url(base_url)`：

- host 转为小写，去掉一个结尾的点，IP 字面量通过 `ipaddress` 规范化（IPv6 结果确定，拒绝 zone id）；
- 有效端口 = 显式端口，否则为 80（`http`）/443（`https`）— `https://x`、`https://x:443`、`https://X.`
  都得到相同的 key；`https://x:8443` 和 `http://x` 不同；
- **忽略路径**：`https://x/a` 和 `https://x/b` 共享一个 key（同一 host 上的两个来源共享一个预算）；
- 拒绝 userinfo/query/fragment（纵深防御 — `aggregation.validate_base_url` 已经在 engine 调用点的上游拒绝了它们）。

`HostKey.parse("host:port")`（IPv6 加方括号）是其逆操作，用于按 host 的覆盖项。`test_rc_host_key.py` 中有 130 个测试。

## 3. 配置

`HostLimitPolicy(default_max_in_flight_per_host=4, overrides=())` — 默认值和每个覆盖值都在 **1..64** 内
（拒绝 `bool`）；`.create(default, {"host:port": limit})` 会规范化并拒绝重复 / 格式错误的 key，最多 256 个覆盖项，
全部在任何网络活动之前完成。`.limit_for(host)` 是静态的 — **C5 中没有自适应限制**。

`CircuitBreakerPolicy(failure_threshold=3, open_duration_seconds=30.0, half_open_max_calls=1)` — 阈值
**1..100**（int，不能是 bool），时长为有限值且在 `(0, 3600]` 内，探测数 **1..16**（int，不能是 bool）。全部为 frozen、
可哈希，在 `__post_init__` 中校验。`test_rc_config.py`。

## 4. Host 限流器语义

`HostLimiter`（每个 host key 一个，惰性创建 — O(distinct hosts)）：严格 FIFO 并直接移交（释放的许可在同一次调用中交给
最早的等待者，绝不交给新来者）；排队期间被取消的等待者会移除自己，不会泄漏许可；在被授予许可的同一轮迭代中被取消的
等待者会把许可交还给许可池。`HostPermit.release()` 是幂等的；`with permit:` 在异常时释放。用一个 100-waiter 测试验证：
在 5 个种子下于随机时间点取消一个随机子集，并断言容量被精确恢复（`test_rc_host_limiter.py`，20 个测试），另外还有
针对“授予后立即取消”竞争的专门测试。

**与 deadline 的交互（冻结的合同，§5.1）：** 等待 host 许可会**暂停**来源的 `asyncio.timeout` deadline
（`Timeout.reschedule(None)`，获得许可后再 `reschedule(now + remaining)`）— 排队时间永远不计入。deadline 仍然像 C2
中那样覆盖每一次 attempt 和每一次退避暂停。在 `test_rc_deadline_and_cancellation.py`（17 个测试）中做了详尽测试：
仅凭 host 争用，一个尚未发出的请求永远不会变成 `SOURCE_DEADLINE`；排队等待许可的重试保留其剩余预算；退避暂停期间
不持有许可。

## 5. 熔断器

**作用域：`source_id`**（不是 host）— 即使两个来源共享一个 host，也被证明相互独立
（`test_rc_shared_scope.py::test_breakers_of_two_sources_on_one_host_are_independent`）。状态为 `CLOSED` / `OPEN`
/ `HALF_OPEN`；使用注入的单调时钟（绝不使用墙钟，也绝不使用基于 `sleep` 的测试）；每次状态转换都会让一个整数
`epoch` 加一。

**观察表（只看最终结果，对 `SourceStatus` 穷举）：**

| 最终结果 | 观察 |
|---|---|
| `SUCCESS`、`NOT_FOUND` | 健康 |
| `BLOCKED`、`RATE_LIMITED`、`NETWORK_ERROR`（任何细化类型，包括 `SOURCE_DEADLINE`）、`PARSE_ERROR`、`INVALID_RESPONSE`（任何细化类型） | 失败 |
| `NETWORK_ERROR`/`CIRCUIT_OPEN` | 不算观察（熔断器自己的答复） |
| 调用方取消、致命 `BaseException` | 不算观察（票据被释放，状态不变） |

一次执行中的两次 attempt（第 1 次 attempt 失败，第 2 次 attempt 成功）是**一次**健康观察，绝不会记录两次。
连续 100 次 `NOT_FOUND` 后 `consecutive_failures == 0`。只依据 `result.status` / `result.error_kind` 判定 —
绝不依据 `error_detail`、trace 或任何字符串（有 AST 守护；见 §8）。

**HALF_OPEN：** 冷却结束后恰好允许 `half_open_max_calls` 次探测准入；其他所有并发查找都被短路
（`test_the_half_open_race_with_100_asyncio_callers_lets_exactly_one_through`，以及 engine 层面的
`test_100_lookups_after_the_cooldown_send_exactly_one_probe_and_99_are_short_circuited`，后者通过真实的
`MultiSourceEngine.aggregate` 调用和一个独立的 fetch 计数器进行观察）。健康的探测会关闭熔断器并重置失败计数；
失败的探测会以从现在开始的**全新**冷却期重新打开熔断器。

**过期完成 / epoch 隔离（§6.2，关键的正确性要点）：** 准入票据在授予时盖上熔断器当时的 epoch；只有当票据的 epoch
仍然等于熔断器当前的 epoch 时，`record_result` 才会改变状态。合同自己的例子 — A/B/C 一起被准入，B 和 C 失败并触发
熔断，A 迟迟返回 SUCCESS — 由 `test_a_late_success_from_before_the_breaker_opened_cannot_close_it` 固定下来，
另外还有过期失败、过期 half-open 以及进行中调用不被取消等变体（`test_rc_breaker_state_machine.py` 中的 7 个专门测试，
外加阶段门槛的 Phase E 以及 `test_rc_breaker_execution.py` 中“在 epoch 变化期间进行中 / 排队中”的测试）。

**顺序（§7）：** 熔断器准入 → host 许可 → 重新校验 `is_current` → fetch。一个在熔断器触发期间排队等待 host 许可的调用，
会得到 `CIRCUIT_OPEN`（第一次 attempt）或者干脆不被重试（后续 attempt — 之前真实的失败保持为最终结果），而不是发出一个
准入已过期的请求（`test_a_lookup_queued_for_the_host_when_the_breaker_opens_sends_nothing`、
`test_a_retry_is_not_sent_when_the_breaker_opened_during_the_backoff_the_real_failure_stays_final`）。打开的熔断器
永远不会进入 host 队列（`test_an_open_breaker_does_not_queue_for_a_saturated_host`）。

## 6. `SourceErrorKind.CIRCUIT_OPEN`

在 `ALLOWED_ERROR_KINDS` / `status_for_error_kind` 中新增于 `NETWORK_ERROR` 之下。**只**由执行边界上的
`resource_control.circuit_open_result` 产生；返回它的 adapter 会被判为 `RESULT_CONTRACT_MISMATCH`
（fail-closed，与伪造 `source_id` 相同），并且这本身会被记录为一次熔断器*失败*
（`test_an_adapter_returning_circuit_open_is_a_contract_violation`）。**永不可重试**：
`SourceErrorKind.CIRCUIT_OPEN not in RETRY_ELIGIBLE_KINDS`，`RetryPolicy(retryable_error_kinds={CIRCUIT_OPEN})`
会抛出 `AggregationConfigError`。`SourceExecutionTrace.attempts` 可以为空，**当且仅当**
`final_result.error_kind is CIRCUIT_OPEN`（`aggregation/models.py` 中收紧的不变量，不存在其他产生空 attempt trace 的方式）。

聚合语义不需要新规则：`CIRCUIT_OPEN` 是 `NETWORK_ERROR`，本来就是运行性失败状态，因此现有的 merge 规则对于“一个被熔断 /
一个成功”、“全部被熔断”、“被熔断 + `NOT_FOUND`”等情况，都能得出正确的 `SUCCESS`/`PARTIAL`/`FAILED`
（`test_rc_breaker_execution.py` 的聚合语义部分）。

## 7. 取消与致命异常

在任何时间点取消 — 等待聚合槽位时、等待 host 许可时、在 `adapter.fetch` 内部，或在 fetch 完成与熔断器更新之间 —
都不会留下泄漏的许可、卡住的等待者或幽灵般的熔断器 in-flight 计数，并且会让出被持有的 half-open 探测名额；
`CancelledError` 仍然原样传播，并且永远不算作熔断器观察。一个参数化的扫描测试在 26 次循环迭代中的每一次之后，
取消三个相互竞争的查找之一，覆盖 `CLOSED` 和 `HALF_OPEN`（探测）两种配置，并断言资源域在之后是干净的
（`test_cancelling_at_every_loop_iteration_leaves_no_permit_no_waiter_no_inflight_and_no_stuck_probe`，52 个参数化用例）。
致命 `BaseException` 以**原始**对象传播（绝不包装，绝不变成结果）；资源层只释放票据 / 许可，从不读取致命异常的类型或消息。

**专项审计（依据 prompt §33）：** `aggregation.execution._FatalSignal` — 在 C5 之前它在 `super().__init__(...)` 中存储了
`type(original).__name__`，这是对抛出方控制的元数据的读取 — 现在不含任何元数据（`__slots__ = ("original",)`，
完全不读取），与 C4 批处理层的载体一致，并在这第二个边界上关闭了同一类 bug（C4-R1-N2）。通过一个 `__name__` 会抛出
异常的恶意 metaclass 从行为上固定下来（`test_the_fatal_carrier_never_reads_the_raisers_metadata`），并通过 AST 从结构上
固定下来（`test_the_fatal_carrier_is_metadata_free`）。

## 8. 不依赖 trace / 不依赖文本（C2-L2 保持 LOW/OPEN）

`test_rc_architecture.py` 对每个 `resource_control/*.py` 文件做 AST 遍历，断言：它们都不读取
`source_execution_traces`、`SourceExecutionTrace`、`SourceAttempt`、`.attempts`、`attempt_count`、
`deadline_during`、`deadline_exceeded`、`error_detail`、`.metadata`、`.elapsed_ms`，也不 import `BatchLineage`；
在 `circuit_breaker.py`/`governor.py` 中，从 `SourceResult` 形态的对象上读取的属性只有
`status`、`error_kind`、`source_id`；限流器 / 熔断器 / governor 模块中不出现任何字符串嗅探方法（`.startswith`、`.lower`、
`.split`、…），也不对结果 / 异常做 `str(...)`/`repr(...)`；并且没有任何枚举成员通过 `.value`/`.name` 比较
（决策依据身份）。**C5 在任何地方都不读取 trace 字段** — 因此，C4-R1 中关于 `BatchItemResult` 暴露 trace 的 finding
在 C5 中仍然没有消费者，**C2-L2 保持
LOW / OPEN**，没有改变。

## 9. 共享 governor 的作用域

通过真实的 `MultiSourceEngine` + `BatchScheduler` 对象证明（从不 mock），峰值从假 adapter 内部独立测量
（一个 `Meter`，而不是 governor 自己的计数器）：

- **两个 `BatchScheduler`、两个 engine、一个 governor**，host 限制 3，各自 M=8：观察到的 host 峰值为 **3**（不是 6，
  也不是 16）；每个调度器仍然各自独立达到其 M=8 的条目峰值。
- **两个 governor**，各自 host 限制 3，并发运行同一场景：峰值 **6** — 独立的资源域，预算相加。
- **同一 host 上的两个来源**（`.../a`、`.../b`），host 限制 2：合计峰值 **2**，而不是各自 2；它们的熔断器相互独立
  （一个来源的 `PARSE_ERROR` 让它的熔断器打开，永远不会影响另一个来源，后者继续为每个条目服务）。
- **两个 host**（限制 2 和 3）：同时达到 2 和 3 的峰值，合计 5。host 许可容量保持相互独立：一个 host 饱和不会消耗
  另一个 host 的许可预算。聚合层的 `max_concurrency` 仍然是外层的调度上限，因此当所有聚合来源槽位都被占用时，
  一个 host 上的争用仍可能间接推迟另一个 host 上后续来源的准入（这是容量隔离，而不是跨 host 的延迟隔离 — 见合同 §2）。
- engine 构造时只从*配置的* base URL 推导 host（`test_the_host_key_is_taken_from_configuration_never_from_the_response`）；
  有 governor 时，格式错误的默认 URL 会被拒绝；没有 governor 时则根本不会被参考。

## 10. 200-item 离线阶段门槛

`test_rc_stage_gate_200.py` — 2 个 `BatchScheduler`，3 个来源（`source_a`/`source_b` 位于 `h1.example`，限制 2；
`source_c` 位于 `h2.example`，限制 3），一个共享 governor，分阶段进行，使每一次熔断器状态转换都是确定的：

- **A**（50）：健康的混合情况，包括重试恢复（`TIMEOUT`→`SUCCESS`）— 每个熔断器都保持 `CLOSED`，0 次失败；
  host 峰值恰好为 2 和 3，合计峰值 5。
- **B**（50）：`source_c` 故障（`BLOCKED`/`RATE_LIMITED`/`PARSE_ERROR`/`NETWORK_ERROR` 轮换）— 恰好在
  `threshold` 次真实请求之后打开；`source_a`/`source_b` 继续服务（`PARTIAL`，而不是 `FAILED`）。
- **C**（20）：冷却期未结束 — 对 `source_c` 的请求为**零**，每个结果都是 `CIRCUIT_OPEN`/空 attempt。
- **D**（40）：冷却期已结束 — 在两个调度器之间**恰好一次**探测 fetch；其余都被短路；
  探测成功 → `CLOSED`，`consecutive_failures == 0`。
- **E**（20）：当 3 个快速的 `BLOCKED` 触发熔断时，一个慢速的 `SUCCESS` 已经在进行中 — 这个进行中的调用**不会**被
  取消，而是正常完成，但它的迟到完成（一个过期的、打开之前的 epoch）**不会**关闭刚刚打开的熔断器；随后的冷却 + 探测
  才真正将其关闭。
- **F**（20）：一整次批处理运行在中途被取消 — 两个调度器的结果中都没有落下任何条目（0 个，没有部分结果），并且 governor
  之后完全干净。

合计 180 个被统计的条目 + 20 个被取消的 = 200。最终断言：每一个 host / 熔断器的 in-flight / waiting / 探测计数器都为 0；
host 峰值恰好为 `{h1: 2, h2: 3}`；没有残留的 asyncio 孤儿任务。

## 11. 大 N 结构压力测试

`test_rc_large_n_stress.py`，N=10,000，没有墙钟断言：

- 一个调度器，M=16，host 限制 3：全部 10,000 个都成功，按顺序，每个恰好一次；观察到的 host 峰值为 **3**；
  观察到的调度器峰值为 **16**；存活任务采样保持在 `O(M)`；运行结束后的 governor 快照恰好显示一个 host 和一个熔断器，
  两者都处于空闲（`in_flight == waiting == 0`）；基于 `gc` 的对象普查（相对于运行前的基线，因此无关测试无法干扰它）
  显示存活的 `SourceAdmission`/`HostPermit` 对象为**零**，并且恰好只有一个 `HostLimiter` 和一个 `CircuitBreaker` —
  没有任何按条目的资源控制对象存活下来。
- 两个调度器 × 5,000，共享一个 governor：合计 host 峰值仍为 **3**。
- 一次 10,000-item 的抖动运行（熔断器通过一个自动前进的假时钟反复打开 / 恢复）：`times_opened` 证实确实发生了循环；
  之后的状态仍然是同一个固定的 9-field 标量快照，与 N 无关 — 没有失败历史列表，也不按条目保留任何内容。

## 12. C5 期间修复的测试基础设施问题（不是资源控制的缺陷）

在准备冻结时，全量测试（2361 个测试）间歇性地让 `test_rc_breaker_execution.py` 中的 4 个测试失败
（`test_an_open_breaker_does_not_queue_for_a_saturated_host` 以及三个基于 `open_and_ok_engine`/`force_open` 的测试）—
但只有在作为**整个**测试集的一部分运行时才会失败，单独运行从不失败。根因：
`tests/contract/test_core_independent_of_amane.py` 的 F4 动态清理测试会有意从 `sys.modules` 中删除每一个
`fc2_metadata_core.*` 条目（以证明该 package 能在一个恶意的、阻断 `amane` 的 meta path finder 下存活），并且之后让它们
保持被清理的状态。`test_rc_breaker_execution.py` 中的两个测试 helper 函数做了一次**局部的、函数体内的**
`from fc2_metadata_core.resource_control import host_key_for_base_url` — 在测试运行时执行，也就是在合同测试已经清理了
`sys.modules` *之后* — 这触发了一次新的重新 import，产生了**第二个、不同的 `HostKey` 类**。已经构造好的 `governor` 对象
（由在模块顶部 import 的名称构建，也就是*原始*的类）随后在对一个形状相同但类不同的 key 做 `isinstance(host, HostKey)`
时失败。这是一个**测试文件 bug**（一个本应放在模块顶层的局部 import，与代码库中其他所有 import 的写法一致），
而不是 `resource_control` 或 `aggregation` 的缺陷：通过一个独立的复现脚本，以及在真实测试中插桩打印跨清理边界的类身份，
得到了确认。修复方式是把该 import 提升到模块顶层（与该文件其余部分以及整个代码库已经使用的风格相同）。审计了本阶段
新增的其他每一个局部 `fc2_metadata_core` import（`test_rc_architecture.py`、`test_rc_breaker_execution.py` 中的
`NormalizedMetadata` 用例、`test_rc_deadline_and_cancellation.py`），确认剩下的都不会与已存在的对象跨越类身份边界
（每一个都是自包含的：由来自*同一次*新 import 的名称构造和使用）。修复之后全量测试又通过了三次，其中包括曾经暴露该问题的
`tests/contract` → `tests/unit/resource_control` 这一确切顺序。

## 13. 延续的待办

- **C2-L2** — LOW / OPEN，未改变（§8：C5 不读取任何 trace 字段）。
- **C4-N1** — `BatchLineage` 是仅存在于内存中的出处；在持久化 / 恢复之前仍然需要一个持久的批次 id。
  `resource_control` **没有**为票据 / epoch 复用 `BatchLineage`（由
  `test_batch_and_the_scheduler_do_not_know_about_resource_control` 验证）。
- **C4-R1-N1 / N2 / N3** — 原样延续（不可信的非 `MultiSourceEngine` 生产者；Python `raise` 边界上恶意
  `BaseException` metaclass 的 `__subclasscheck__`；非普通 metaclass 带来的诊断信息丢失）。C5 没有触碰这些。
- **新增、已记录、未修复（C5）：** 熔断器 / host 状态按 governor 保存，只在内存中，重启即丢失；没有感知 `Retry-After`
  的冷却；host 限制是静态的（没有自适应限制）；governor 是单事件循环的，不是线程安全的；过期的（已被取代的 epoch）
  观察会被丢弃，而不是降低权重。
- 尚未开始：持久化 / DB、NFO writer、图片下载器、文件系统、Amane adapter、GUI、最终的 500-item 验收、`Retry-After`
  解析、CAPTCHA / 反爬绕过、代理轮换、线上的大批量抓取。

## 14. 文件

```
docs/specifications/PHASE3_RESOURCE_CONTROL_CONTRACT.md   (new)
docs/specifications/PHASE3_RESILIENCE_CONTRACT.md          (amended: CIRCUIT_OPEN, deadline/queue note)
docs/specifications/PHASE3_BATCH_CONTRACT.md               (amended: per-host limiter note points at C5)

src/fc2_metadata_core/resource_control/__init__.py
src/fc2_metadata_core/resource_control/errors.py
src/fc2_metadata_core/resource_control/host_key.py
src/fc2_metadata_core/resource_control/config.py
src/fc2_metadata_core/resource_control/host_limiter.py
src/fc2_metadata_core/resource_control/circuit_breaker.py
src/fc2_metadata_core/resource_control/governor.py

src/fc2_metadata_core/__init__.py                          (exports resource_control)
src/fc2_metadata_core/models/source_result.py              (SourceErrorKind.CIRCUIT_OPEN)
src/fc2_metadata_core/aggregation/models.py                (trace: zero attempts iff CIRCUIT_OPEN)
src/fc2_metadata_core/aggregation/execution.py              (governor= integration; metadata-free _FatalSignal)
src/fc2_metadata_core/aggregation/engine.py                 (governor= construction, host derivation)
src/fc2_metadata_core/aggregation/retry.py                  (docstring: CIRCUIT_OPEN never retried)

tests/support/resource_fakes.py                             (new: FakeClock, Meter, Spec/make_engine/make_target, run())
tests/unit/resource_control/test_rc_host_key.py
tests/unit/resource_control/test_rc_config.py
tests/unit/resource_control/test_rc_host_limiter.py
tests/unit/resource_control/test_rc_breaker_state_machine.py
tests/unit/resource_control/test_rc_governor_tokens.py
tests/unit/resource_control/test_rc_shared_scope.py
tests/unit/resource_control/test_rc_breaker_execution.py
tests/unit/resource_control/test_rc_deadline_and_cancellation.py
tests/unit/resource_control/test_rc_architecture.py
tests/unit/resource_control/test_rc_stage_gate_200.py
tests/unit/resource_control/test_rc_large_n_stress.py

tests/unit/aggregation/test_agg_guards.py                   (amended: circuit-breaker-vocabulary guard scoped to C5)
tests/unit/aggregation/test_agg_retry_policy.py             (amended: CIRCUIT_OPEN in the not-retryable set)
tests/unit/core/test_source_error_taxonomy.py               (amended: CIRCUIT_OPEN in the frozen relation)
```

---

READY FOR PHASE 3 C5 INDEPENDENT REVIEW
