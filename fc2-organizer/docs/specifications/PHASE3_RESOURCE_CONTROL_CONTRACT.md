# FC2 Metadata Core — Phase 3 / C5 共享 Host 资源控制与熔断器合同（Shared Host Resource Control & Circuit Breaker Contract）

状态：**在 Phase 3 C5 冻结**（候选；独立复查待进行）。
以 `PHASE3_RESILIENCE_CONTRACT.md`（C1–C3）和 `PHASE3_BATCH_CONTRACT.md`（C4）为基础。
Package：`fc2_metadata_core.resource_control`（`errors.py`、`host_key.py`、`config.py`、`host_limiter.py`、
`circuit_breaker.py`、`governor.py`）。集成点：`aggregation/execution.py`、`aggregation/engine.py`、
`aggregation/models.py`（trace）、`models/source_result.py`（`SourceErrorKind.CIRCUIT_OPEN`）。

**不在范围内，未实现：** 持久化 / DB、NFO writer、图片下载器、文件系统重命名 / 移动、Amane adapter、
GUI、最终的 500-item 验收运行、`Retry-After` 解析、CAPTCHA / 反爬绕过、代理轮换、自适应（动态）限制、
实时的大批量抓取。

每条规则都注明了强制执行它的测试文件（全部离线且确定；除非另有说明，均位于
`tests/unit/resource_control/`；任何地方都没有墙钟断言 — 熔断器的时间来自注入的单调时钟，
等待依靠事件 / 闸门，绝不依靠基于 `sleep` 的排序）。

## 1. 架构与依赖方向

```text
BatchScheduler A ─┐
BatchScheduler B ─┼─> same MultiSourceEngine(s) constructed with the same governor
BatchScheduler C ─┘
                         │  execute_sources_traced(..., governor=g)
                         v
                 SourceResourceGovernor  (one explicit resource domain)
                   /                  \
        per-host limiter          per-source circuit breaker
        (HostKey -> permits)      (source_id -> state machine)
                   \                  /
                    adapter.fetch  /  structured SourceResult
```

* `resource_control` 依赖 `SourceResult` 合同（`SourceResult`、`SourceStatus`、
  `SourceErrorKind`）、`errors` 和标准库。它**从不** import `batch`、`aggregation`、
  `sources.adapters`、`httpx`、`amane`，也不 import 任何文件 / 网络 / 进程模块。
* `aggregation.execution` / `aggregation.engine` 通过 governor 狭窄的公开接口依赖它
  （`admit`、`acquire_host_permit`、`is_current`、`record_result`、`release`）。`batch` **没有改变**：它只通过
  自己被注入的 engine 接触 governor（C4 的 `AggregationEngine` protocol）。
* **没有模块级的可变单例。** governor 是一个显式对象：被传入*同一个*实例的 engine / 调度器共享同一个
  资源域；*不同的*实例是独立的资源域，其预算直接相加。由 `test_rc_architecture.py`（没有模块级可变状态）
  和下文的作用域测试强制执行。
* **可选启用。** 不带 `governor=` 的 `MultiSourceEngine(config, registry, client)` 行为与 C4 完全相同
  （没有 host 限制，没有熔断器）— 所有 C5 之前的测试都没有改变。

## 2. 资源域与三个预算（冻结语义）

| 旋钮 | 作用域 | 限制的对象 |
|---|---|---|
| `AggregationConfig.max_concurrency = S` | 一次 `aggregate()` 调用（C1） | 单个条目内部并发的来源执行数 |
| `BatchConfig.max_in_flight_items = M` | 一个 `BatchScheduler`（C4） | 该调度器并发的 `aggregate()` 调用数 |
| `HostLimitPolicy.default_max_in_flight_per_host`（+ 覆盖项） | **一个 governor**（C5） | 针对同一个 host 的并发网络 **attempt**（`adapter.fetch`）数，覆盖该 governor 下的每一次 `aggregate()` 调用、每一个 engine、每一个调度器、每一个来源 |

C4 的 M 和 C1 的 S 没有改变，仍然生效；C5 的 host 预算是一个额外的、更紧或相等的上限，
限制的是实际发到网络上的请求。`test_rc_shared_scope.py`：两个调度器（各自 M=8）+ 两个 engine +
一个 host 限制为 3 的 governor → 观察到的 host 峰值为 **3**（不是 6，也不是 16）；两个 governor → 峰值最高可达
6（独立的资源域）；位于 `https://same.example/a` 和 `/b` 的两个来源、限制为 2 → 合计峰值
**2**；host `a.example`（限制 2）和 `b.example`（限制 3）同时运行 2 + 3 = 5 个，各自不超过自己的
限制。

**这到底保证了什么。** host 许可的容量**按 `HostKey`** 相互独立：一个 host 饱和，永远不会消耗或
减少另一个 host 的许可容量；只要有聚合层的来源槽位可以使用，不同的 host 就可以各自在自己的限制内
并发执行。这是一个**容量隔离**保证。它**不是**跨 host 的**延迟**隔离保证，C5 也不提供这种保证：
`AggregationConfig.max_concurrency`（S，C1）仍然是外层的、未改变的按 `aggregate()` 调用的调度预算，
而一个正在排队等待 *host* 许可的来源，在等待期间会一直占用它在*聚合本地*的来源槽位（§5、§5.1）。
因此，当 `S` 小于一次查找中可运行来源的数量时，一个 host 上的争用可能间接推迟另一个面向*不同* host 的
后续来源的准入，即使那个 host 自己的许可容量完全空闲。这不是 host 许可泄漏，也不是跨 host 的预算耦合 —
这是在未改变的 C1 semaphore 下普通的聚合层队头调度，它与 host 限流器自身的记账相互正交（并且位于其之外），
而后者仍然严格保持上文所述的隔离。

## 3. Host 身份（`host_key.py`）— `test_rc_host_key.py`

`HostKey(host: str, port: int)` — frozen、可哈希、按 `(host, port)` 排序。**只从 engine 所构建的 adapter
已配置、已校验的 `base_url` 推导**（有 `SourceConfig.base_url` 时用它，否则用 adapter 的
`default_base_url`）— 绝不从响应 URL、重定向目标、错误文本、trace、标题或请求体推导。
规则（`host_key_for_base_url`）：

* scheme 必须是 `http` 或 `https`；host 转为小写；去掉**一个**结尾的点
  （`example.com.` ≡ `example.com`）；
* **有效端口**：显式指定的端口，否则为 `80`（http）/ `443`（https）— `https://x`、`https://x:443`
  和 `https://X.` 是同一个 key；`https://x:8443` 和 `http://x` 是不同的 key；
* **忽略路径**：`https://x/a` 和 `https://x/b` 共享一个 key（因此同一 host 上的两个来源共享
  一个 host 预算）；
* IP 字面量由 `ipaddress` 规范化（`::1`、`0:0:0:0:0:0:0:1` → `::1`）；可打印形式
  `str(HostKey)` 为 `host:port`，IPv6 加方括号（`[::1]:443`）；IPv6 zone id（`%eth0`）会被拒绝；
* 不可能出现 userinfo、query 和 fragment（`aggregation.validate_base_url` 已经拒绝它们；key 构建器会
  再拒绝一次 — 它也可以单独使用），非 `str` / 空 / 缺少 host / 端口错误的值会抛出
  `ResourceControlConfigError` — **在任何网络活动之前**。

`HostKey.parse("host:port")` 是其逆操作，用于按 host 的覆盖项（端口必填，IPv6 加方括号）。

**运行时 key 从哪里来。** 当提供了 governor 时，`MultiSourceEngine.__init__` 会**在构造时一次性**地为每个
启用的来源推导 key：从 `adapter.base_url`（已配置的 `SourceConfig.base_url`，否则为 adapter 的
`default_base_url`）经 `aggregation.validate_base_url` → `host_key_for_base_url` 推导，并存放在
`SourceTarget` 上（`host`）。无法生成 key 的 base URL（例如格式错误的 adapter 默认值）会**在任何请求之前**
抛出 `AggregationConfigError("… cannot derive a host identity …")`；没有 governor 时不做任何推导，也不检查
任何默认 URL（C4 行为不变）。`execute_sources_traced(..., governor=g)` 要求每个目标都带有 host
（否则抛出 `AggregationConfigError`）。响应、重定向目标或错误文本永远不会被参考
（`test_rc_shared_scope.py::test_the_host_key_is_taken_from_configuration_never_from_the_response`）。

## 4. `HostLimitPolicy` 与 `CircuitBreakerPolicy`（`config.py`）— `test_rc_config.py`

frozen、可哈希、在构造时校验（`ResourceControlConfigError`）、永不修改；`bool` 永远不被当作
数字 / int 接受；每个数值都是有限且有界的。

`HostLimitPolicy(default_max_in_flight_per_host=4, overrides=())`

* 默认值 **4**，范围 **1..64**（`HOST_LIMIT_MAX`）；`overrides` 是由 `(HostKey, int)` 对组成的 tuple（每个
  int 在 1..64 内），**最多 256 个**，**不允许重复的 host key**；`HostLimitPolicy.create(default, mapping)` 是
  便利构造函数（key 是 `"host:port"` 字符串，经 `HostKey.parse` 规范化；格式错误的 key，或规范化后
  指向同一 host 的两个 key — `"A.example:443"` 和 `"a.example:443"` — 会被拒绝）。
  所有内容都复制到不可变的 tuple 中，因此调用方仍然持有的任何对象都无法改变该策略。
* `limit_for(HostKey)` → 覆盖值或默认值。**静态**：C5 中没有自适应限制。

`CircuitBreakerPolicy(failure_threshold=3, open_duration_seconds=30.0, half_open_max_calls=1)`

* `failure_threshold`：int（不能是 bool），范围 **1..100**；
* `open_duration_seconds`：有限数值，**> 0** 且 **<= 3600**；
* `half_open_max_calls`：int（不能是 bool），范围 **1..16**。

## 5. Host 许可语义（`host_limiter.py`）— `test_rc_host_limiter.py`

每个 host key 对应一个 `HostLimiter`（由 governor 惰性创建 — O(hosts) 的状态，§12）。

* 许可**按网络 attempt** 获取：`permit = await governor.acquire_host_permit(admission)` →
  `adapter.fetch` → `permit.release()`。**重试的退避暂停期间不持有许可**（一秒的退避
  永远不会阻塞该 host 上的其他条目）；第 2 次 attempt 会重新获取。
* 在任何时刻，对于同一个 governor 和同一个 host key，**存活的许可数 ≤ 该 host 的限制**；不同 host 的
  许可*容量*永远不会相互阻塞（§2 的容量隔离保证）— 不过，能否首先进入聚合层的来源槽位，
  仍然由未改变的外层 C1 `max_concurrency` 控制（§2）。
* **FIFO** 且公平：新来者永远不会插队到等待者前面。释放时把许可直接交给最早的存活等待者
  （不存在可以被第三方抢走的时间窗口）。
* `HostPermit.release()` 是幂等的；`with permit:` 在退出时释放（异常 / 取消时也是如此）。
* **等待期间被取消**会立即抛出 `CancelledError` 并移除该等待者。如果一个等待者在其任务被取消的同一轮
  事件循环中*被授予*了许可，它会把许可交还给下一个等待者 / 许可池（没有许可泄漏，没有幽灵持有者）。
  100 个等待者，在不同时间点取消其中一部分 → 限流器的容量完全恢复（`in_flight == 0`、`waiting == 0`，
  之后恰好准入 `limit` 个新的持有者）。

### 5.1 排队时间与来源 deadline（冻结；C5 的关键合同）

C2 已经把等待**聚合本地** semaphore 的时间排除在来源的 `deadline_seconds` 之外。C5 扩展了
这条规则：**等待 host 许可不消耗来源的执行 deadline。**
实现方式：来源 deadline 是一个 `asyncio.timeout`；当某次 attempt *正在排队等待 host 许可*时，
deadline 被暂停（`Timeout.reschedule(None)`），许可一旦授予，就以恰好剩余的时间重新设定
（`reschedule(loop.time() + remaining)`）。推论（全部在
`test_rc_deadline_and_cancellation.py` 中测试）：

* host 争用永远不会让一个**尚未发出请求**的来源变成 `SOURCE_DEADLINE`；
* deadline 仍然覆盖：每一次网络 attempt、每一次退避暂停，此外不含其他任何内容 — 一个 0.30 s 的 deadline，
  第 1 次 attempt（0.15 s）+ 退避（0.10 s）+ 挂起的第 2 次 attempt，即使第 2 次 attempt 先排队等待了许可，
  仍然会在*执行*时间 ≈ 0.30 s 时结束；
* 活性由*持有者*的 deadline 保证（每个持有者的 fetch 本身都受其来源 deadline 约束）。

## 6. 熔断器的作用域与状态机（`circuit_breaker.py`）— `test_rc_breaker_state_machine.py`

**作用域：`source_id`**（默认且唯一的模式）。一个 host 可能同时服务两个来源（`same.example/a`、
`/b`）；来源 A 的页面布局解析失败不能让来源 B 被熔断。host 限流器按 host 划分，熔断器按来源划分 —
两个作用域相互正交。熔断器状态按 `source_id` 惰性创建（O(已配置的来源数)）；同一个 governor 下
配置了相同 `source_id` 的两个 engine 共享该来源的熔断器。

状态为 `CLOSED`、`OPEN`、`HALF_OPEN`。时间来自**注入的单调时钟**（默认 `clock=time.monotonic`；
测试注入一个假时钟）。永远不使用墙钟（`datetime`、`time.time`）和 `sleep`。

每个来源的内部状态是可变且私有的；对外的视图是不可变的 `BreakerSnapshot`。
每次状态转换都会让 `epoch` 加一（一个 int，单调递增，从 0 开始）。所有转换都是同步的 Python 代码，
**内部没有任何 `await`** — 在同一个事件循环上它们是原子的；governor 的文档明确说明它是
**单事件循环的，不是线程安全的**。

| 起始状态 | 事件 | 目标状态 | 效果 |
|---|---|---|---|
| `CLOSED` | 准入 | `CLOSED` | 授予一张*普通*票据，盖上当前 epoch |
| `CLOSED` | 当前 epoch 的**健康**观察 | `CLOSED` | `consecutive_failures = 0` |
| `CLOSED` | 当前 epoch 的**失败**，计数 `< threshold` | `CLOSED` | `consecutive_failures += 1` |
| `CLOSED` | 当前 epoch 的**失败**，计数达到 `failure_threshold` | `OPEN` | `epoch += 1`，`opened_at = now` |
| `OPEN` | 准入，`now - opened_at < open_duration_seconds` | `OPEN` | **拒绝**（短路） |
| `OPEN` | 准入，`now - opened_at >= open_duration_seconds` | `HALF_OPEN` | `epoch += 1`，尚无探测，随后对同一次调用应用 `HALF_OPEN` 的准入规则 |
| `HALF_OPEN` | 准入，`probes_in_flight < half_open_max_calls` | `HALF_OPEN` | 授予一张*探测*票据（`probes_in_flight += 1`） |
| `HALF_OPEN` | 准入，`probes_in_flight == half_open_max_calls` | `HALF_OPEN` | **拒绝** — 不会出现惊群 |
| `HALF_OPEN` | 当前 epoch 的探测**健康** | `CLOSED` | `epoch += 1`，`consecutive_failures = 0` |
| `HALF_OPEN` | 当前 epoch 的探测**失败** | `OPEN` | `epoch += 1`，`opened_at = now`（重新开始冷却） |
| 任意 | **过期**的观察（票据的 epoch ≠ 当前 epoch） | 不变 | 只释放该票据的 in-flight 记账 |
| 任意 | 票据未经观察就被释放（取消 / 致命 / 未尝试） | 不变 | 释放 in-flight 记账；当前 epoch 的探测会让出其探测名额 |

`OPEN → HALF_OPEN` 的转换是**惰性的**（由冷却结束后的第一次准入完成；快照永远不会修改状态）：
对一个已过冷却期但尚未探测的熔断器取快照，报告的是 `OPEN`，且 `remaining_cooldown_seconds == 0.0`。

### 6.1 什么算作一次观察（只看最终结果）— `test_rc_breaker_state_machine.py`

熔断器**每次来源执行只接收一次观察：该来源的 FINAL `SourceResult`** — 在重试之后、deadline 之后、
fail-closed 校验之后。依据是 `result.status`（对于下面那个不算观察的 kind，还依据 `result.error_kind`）；
绝不依据 `error_detail`，也绝不依据 trace。

| 最终结果 | 观察 |
|---|---|
| `SUCCESS` | **健康** |
| `NOT_FOUND` | **健康** — 该来源已作答；只是其目录中没有这个 id（连续 100 次 `NOT_FOUND` 会让熔断器保持 `CLOSED`，失败计数为 0） |
| `BLOCKED`、`RATE_LIMITED`、`NETWORK_ERROR`（任何细化类型，包括 `SOURCE_DEADLINE`）、`PARSE_ERROR`、`INVALID_RESPONSE`（任何细化类型） | **失败** |
| `error_kind == CIRCUIT_OPEN` 的 `NETWORK_ERROR` | **不算观察**（它是熔断器自己给出的答复） |
| 调用方取消、致命 `BaseException` | **不算观察** — 票据被释放 |

`attempt 1 NETWORK_ERROR → attempt 2 SUCCESS` 是**一次健康观察**（两次 attempt 永远不会算成两次
失败）。完整的“状态 → 观察”表会在 import 时与 `SourceStatus` 对照检查（新增了状态却没有给出
判定时，会显式报错）。

### 6.2 Epoch、票据与过期完成（冻结）

`SourceResourceGovernor.admit(source_id, host)` 返回一个不透明的 `SourceAdmission`（或 `None` = 熔断器
打开）。票据记录 `source_id`、`host`、准入时熔断器的 **epoch**、它是否为**探测**，并绑定到签发它的
governor。调用方无法自行构造票据（构造函数需要一个私有 key）；来自另一个 governor 的票据、伪造的票据、
已结算却又用于 `record_result` 的票据，或者非 `SourceResult`，都会抛出 `ResourceControlError`。

* 只有当**票据的 epoch 等于熔断器当前的 epoch** 时，观察才会被应用。例如：
  调用 A、B、C 在 `CLOSED` epoch 4 时被准入；B 和 C 失败，达到阈值 → `OPEN` epoch 5；A
  迟迟返回 `SUCCESS` — 它的 epoch（4）已经过期，因此被丢弃，**不能重置 / 关闭**熔断器
  （过期的*失败*也不能重新打开、延长或重复计数任何东西）。
* 熔断器打开时，进行中的调用**永远不会被取消**；它们正常完成并返回，只是它们对熔断器*状态*的影响
  被屏蔽。只有**新的**准入会被短路。
* `record_result` / `release` **在记账层面是幂等安全的**：对已结算的票据调用 `release` 是
  空操作（因此 `finally: release` 总是正确的）；对已结算的票据调用 `record_result` 会抛出异常。

## 7. 顺序：熔断器 → host 许可 → 重新校验（冻结）

每次来源执行（`execution._execute_one`）：

1. 等待聚合本地的槽位（C1，未改变）；
2. `admission = governor.admit(source_id, host)` — 同步调用。`None` → 该来源的结果为
   `circuit_open_result`（§8），**不**占用 host 许可，也**不**调用 `adapter.fetch`；
3. 对于**每一次** attempt：`permit = await governor.acquire_host_permit(admission)`（deadline 暂停，§5.1）；
   **然后** `governor.is_current(admission)`：
   * 仍是当前的 → `adapter.fetch` → 释放许可；
   * **已过期**（在该调用排队期间或重试退避期间，熔断器的 epoch 发生了变化）→ **不发送**请求：
     第 1 次 attempt → 结果为 `CIRCUIT_OPEN`（没有进行任何 attempt）；第 *n ≥ 2* 次 attempt → **不再
     继续重试** — 上一次 attempt 的真实失败保持为最终结果；
4. 调用一次 `governor.record_result(admission, final_result)`（取消 / 致命 / 未尝试时则调用 `release`）。

因此，`OPEN` 状态的熔断器永远不会占用 host 槽位，排队中的调用也永远不会在一个已被更新的熔断器状态
作废的准入下发出请求。

## 8. `CIRCUIT_OPEN` 词汇与 trace — `test_source_error_taxonomy.py`、`test_rc_breaker_execution.py`

`SourceStatus` **没有改变**（七个状态）。在 **`NETWORK_ERROR`** 下新增
`SourceErrorKind.CIRCUIT_OPEN = "circuit_open"`（`ALLOWED_ERROR_KINDS`、`status_for_error_kind`；
`PHASE3_RESILIENCE_CONTRACT.md` §1 中的文档表格已修订）。它**只**由执行边界产生
（`circuit_open_result`：`error_detail = "<source_id>: circuit breaker open; lookup not attempted"`，`elapsed_ms = 0`）。
返回它的 adapter 会被视为违反合同（`INVALID_RESPONSE` /
`RESULT_CONTRACT_MISMATCH`，与伪造 `source_id` 完全相同）。

* **永不重试**：`CIRCUIT_OPEN` 不在 `RETRY_ELIGIBLE_KINDS` 中（AST / 合同守护；
  `RetryPolicy(retryable_error_kinds={CIRCUIT_OPEN})` 会被拒绝），而且短路本来就发生在
  attempt 循环之前。
* **Trace：** 被短路的来源拥有一个 `attempts == ()`、`attempt_count == 0`、
  `deadline_exceeded == False` 的 `SourceExecutionTrace`。`SourceExecutionTrace` 的不变量（C2 §5）随之修订：
  `attempts` 可以为空，**当且仅当** `final_result.error_kind is CIRCUIT_OPEN`（此时不允许任何其他内容）；
  其他所有 trace 仍然需要 `≥ 1` 次 attempt。
* **聚合：** `NETWORK_ERROR` 是运行性失败，因此没有任何 merge 规则需要改变：一个来源
  `CIRCUIT_OPEN` + 一个 `SUCCESS` → 聚合结果 `PARTIAL`；所有来源都被熔断 → `FAILED`；`CIRCUIT_OPEN` +
  `NOT_FOUND`（没有数据）→ `FAILED`；`SUCCESS` + `NOT_FOUND` → `SUCCESS`（未改变）。
* **批处理：** 因来源被熔断而以 `FAILED`/`PARTIAL` 结束的批处理条目就是普通的失败条目；
  C4 的失败子集重试照常适用（冷却期后重新运行可能成功）。

## 9. 取消与致命异常 — `test_rc_deadline_and_cancellation.py`

在**任何**时间点被取消（由调用方、同级任务的清理或来源 deadline 触发）— 无论是在等待聚合槽位、
等待 host 许可、`adapter.fetch` 内部，还是 fetch 刚刚返回之后：

* 不会有 host 许可继续被持有；不会有等待者继续排队；熔断器的 in-flight 计数不会停留在递增状态；
  half-open 的探测名额会被**让出**（另一次查找可以进行探测）；`CancelledError` 仍然原样传播
  （绝不会变成结果，也绝不会算作失败）；
* 来源 **deadline** *不是*对调用方的取消：它是一个真实的最终结果
  `NETWORK_ERROR/SOURCE_DEADLINE`，并且**算作**一次熔断器失败。

致命 `BaseException`（`KeyboardInterrupt`、`SystemExit`、自定义）：C2/C3 的规则不变 — 取消同级任务，
重新抛出**原始**对象，绝不包装，绝不变成结果 — 资源层只会*释放*自己的票据 / 许可（在 `finally` 中）；
它从不读取致命异常的类型、名称、消息或 args。
**针对该边界的专项审计（C5）：** `execution._FatalSignal` 以前存储
`type(original).__name__`（这是对抛出方控制的元数据的读取，恶意 metaclass 可以借此制造一个错误来
替换原本的致命异常 — 属于 C4-R1 那一类 bug）。现在它不含任何元数据（`__slots__ = ("original",)`，
不做任何读取）；由 `test_rc_architecture.py` 和 `test_rc_deadline_and_cancellation.py` 固定下来。

## 10. 不依赖 trace，不依赖文本（C2-L2 保持 LOW/OPEN）— `test_rc_architecture.py`

资源控制 package 的 AST 中**完全没有**读取以下内容：`source_execution_traces`、`SourceExecutionTrace`、
`SourceAttempt`、`.attempts`、`attempt_count`、`deadline_during`、`deadline_exceeded`、`error_detail`、`.metadata`、
`.elapsed_ms`；没有对异常或结果做 `str()`/`repr()`/`format`/`in` 字符串测试；没有针对错误文本的
字符串字面量匹配。决策只使用 `SourceStatus`、`SourceErrorKind`、`source_id`、已配置的 host key、
epoch 以及注入的单调时钟。因此，C4-R1 中的那项观察（`BatchItemResult` 暴露了 trace）不会延伸到 C5：
**C2-L2 仍为 LOW / OPEN，C5 中不存在对 trace 的依赖。**
*没有*复用 `BatchLineage`：票据、epoch 和许可都有各自独立的身份。

## 11. 诊断信息 — `test_rc_governor_tokens.py`

`governor.snapshot()` → 不可变的 `GovernorSnapshot(hosts: tuple[HostSnapshot, ...], breakers:
tuple[BreakerSnapshot, ...])`，按确定的方式排序。`HostSnapshot(host, limit, in_flight, waiting,
peak_in_flight)`；`BreakerSnapshot(source_id, state, consecutive_failures, epoch, in_flight,
half_open_probes_in_flight, opened_at, remaining_cooldown_seconds, times_opened)`。只包含标量、枚举以及
`source_id`/host 字符串 — 没有带路径的 URL，没有响应文本，没有异常对象，没有内部可变容器
（`test_rc_governor_tokens.py` 断言了字段集合，并断言无法修改快照）。

## 12. 内存上界 — `test_rc_large_n_stress.py`

状态规模为 `O(distinct hosts + distinct source_ids)`；条目完成后，不保留任何按条目、按番号或按 attempt
的对象；不存在失败历史列表（只有计数器）。票据生命周期很短（结算时释放其 in-flight 记账），
也不会存放在 governor 中。

## 13. 测试矩阵

| 领域 | 文件 |
|---|---|
| host key 规范形式 | `test_rc_host_key.py` |
| 策略（类型、范围、`bool`、覆盖项、不可变性） | `test_rc_config.py` |
| host 限流器（FIFO、峰值、取消、100-waiter 恢复、授予后立即取消） | `test_rc_host_limiter.py` |
| 熔断器状态机、时钟、epoch、half-open 竞争（100 个调用方，1 个探测）、阈值竞争、过期完成 | `test_rc_breaker_state_machine.py` |
| 票据、外来 / 伪造 / 重复结算、状态表、快照 | `test_rc_governor_tokens.py` |
| 共享 governor / 不同 governor / 同 host 的来源 / 不同 host | `test_rc_shared_scope.py` |
| 经由真实 engine 的熔断器：BLOCKED/RATE_LIMITED/PARSE、NOT_FOUND、重试、打开 ⇒ 零请求、聚合语义、`CIRCUIT_OPEN` trace | `test_rc_breaker_execution.py` |
| deadline 与排队、各阶段的取消 / 致命异常清理 | `test_rc_deadline_and_cancellation.py` |
| AST / 架构守护 | `test_rc_architecture.py` |
| 200-item 离线阶段门槛（2 个调度器、3 个来源、2 个 host、混合失败、熔断周期） | `test_rc_stage_gate_200.py` |
| N = 10 000，M = 16，host 限制 3，O(hosts + sources) 状态 | `test_rc_large_n_stress.py` |
| 针对 `CIRCUIT_OPEN` 更新的分类 / 重试矩阵 | `tests/unit/core/test_source_error_taxonomy.py`、`tests/unit/aggregation/test_agg_retry_policy.py` |

## 14. 延续的待办（C5 没有修复这里的任何一项）

* **C2-L2**（LOW/OPEN）：`BatchItemResult` 暴露了 `AggregationResult.source_execution_traces`；C5 不读取
  trace，因此收紧的触发条件没有改变。
* **C4-N1** 持久化的批次 id（在持久化 / 恢复之前）；**C4-R1-N1** 伪造 `AggregationResult` 内部内容的
  不可信非 `MultiSourceEngine` 生产者；**C4-R1-N2** Python `raise` 边界上恶意 `BaseException` metaclass 的
  `__subclasscheck__`；**C4-R1-N3** 非普通 metaclass → `UnknownType` 带来的诊断信息丢失 / 子类严格性；**C3-N1…N4**、
  **P2-R-05/06/07/10**、**F3/F5**。
* C5 新增的局限（已记录，未修复）：熔断器状态按 governor 保存在内存中（运行之间不持久化）；
  `open_duration_seconds` 是静态的（不读取 `Retry-After`）；host 限制是静态的；governor 是单事件循环的，
  不是线程安全的；过期的观察会被*丢弃*，而不是降低权重（来自已被取代的 epoch 的迟到真实失败，
  刻意不计入）。
