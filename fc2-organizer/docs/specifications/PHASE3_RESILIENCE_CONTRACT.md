# FC2 Metadata Core — Phase 3 / C2 韧性与重试合同（Resilience & Retry Contract）

状态：**在 Phase 3 C2 冻结**（候选；独立复查待进行）。
以 `PHASE3_AGGREGATION_CONTRACT.md`（C1）为基础。关闭 Phase 2 复查 finding **P2-R-12**
以及 C1 复查 finding **LOW-1 … LOW-4**。

> **C5 修订**（`PHASE3_RESOURCE_CONTROL_CONTRACT.md`）：在 `NETWORK_ERROR` 下新增
> `SourceErrorKind.CIRCUIT_OPEN`（永不重试）；由已打开的熔断器直接应答的来源，其 `SourceExecutionTrace`
> 包含**零次 attempt**（§5）；等待共享 host 许可的排队时间不计入来源 deadline（§3）；
> 下文中“没有熔断器”的表述描述的是 C2，已被 C5 中可选启用的 `governor=` 取代。

**不在范围内，未实现：** 批处理引擎 / 跨条目调度、失败子集重试、熔断器、感知 `Retry-After`
的调度、jitter、NFO、图片、文件系统、Amane adapter。

每条规则都注明了强制执行它的测试文件（全部离线且确定；除非另有说明，均位于
`tests/unit/aggregation/`）。

## 1. 失败分类（`models/source_result.py`）— `tests/unit/core/test_source_error_taxonomy.py`

`SourceStatus` **没有改变**（粗粒度，对聚合层可见）：`SUCCESS`、`NOT_FOUND`、`BLOCKED`、
`RATE_LIMITED`、`NETWORK_ERROR`、`PARSE_ERROR`、`INVALID_RESPONSE`。`SourceErrorKind` 得到扩充：

| `SourceStatus` | 允许的 `SourceErrorKind`（`ALLOWED_ERROR_KINDS`） |
|---|---|
| `NOT_FOUND` | `NOT_FOUND` |
| `BLOCKED` | `BLOCKED` |
| `RATE_LIMITED` | `RATE_LIMITED` |
| `NETWORK_ERROR` | `NETWORK_ERROR`（通用）、`TIMEOUT`、`CONNECTION_ERROR`、`DECODE_ERROR`、`REDIRECT_ERROR`、`SOURCE_DEADLINE`、`CIRCUIT_OPEN` *(C5)* |
| `PARSE_ERROR` | `PARSE_ERROR` |
| `INVALID_RESPONSE` | `INVALID_RESPONSE`（通用）、`HTTP_SERVER_ERROR`、`RESPONSE_TOO_LARGE`、`ADAPTER_EXCEPTION`、`RESULT_CONTRACT_MISMATCH` |

每个 `SourceErrorKind` 恰好属于一个状态（`status_for_error_kind`）。规则
（`SourceResult.__post_init__`）：非成功结果需要一个**其状态所允许的** `error_kind`，以及非空的
`error_detail`（Phase 1 的不变量，未改变）；`SUCCESS` 两者都不允许有。
**向后兼容：** 保留了六个通用 kind，因此每一个 C2 之前的 `SourceResult`（kind == 其状态本身的名称）
以及每一个没有细化失败类型的 adapter，都仍然能通过校验。

细化后各 kind 的含义及其产生者：

| Kind | 含义 | 产生者 |
|---|---|---|
| `TIMEOUT` | transport 超时（connect/read/pool） | `classify_transport_failure`（`HttpTimeoutError`） |
| `CONNECTION_ERROR` | DNS / TCP / TLS / 协议 / 读取错误 | `HttpConnectionError` |
| `DECODE_ERROR` | 响应体解码 / 解压失败（`gzip`/`deflate` 错误） | `HttpDecodingError`（新增；`HttpxTransport` 遇到 `httpx.DecodingError` 时抛出） |
| `REDIRECT_ERROR` | 超过重定向链上限 | `HttpRedirectLimitError` |
| `SOURCE_DEADLINE` | 单个来源的墙钟 deadline 到期 | 聚合执行边界 |
| `CIRCUIT_OPEN` *(C5)* | 该来源的熔断器处于打开状态；**没有发出任何请求** | 仅由聚合执行边界（通过 `resource_control`）产生 — adapter 返回它即视为 `RESULT_CONTRACT_MISMATCH` |
| `HTTP_SERVER_ERROR` | HTTP **500–599** | `classify_page_response`（adapter） |
| `RESPONSE_TOO_LARGE` | 响应体超过 transport 的大小上限 | `HttpResponseTooLargeError` |
| `ADAPTER_EXCEPTION` | adapter 自身抛出异常（包括其自行抛出的 `CancelledError`） | 执行边界 |
| `RESULT_CONTRACT_MISMATCH` | `source_id` 错误、非 `SourceResult`，或针对另一个番号的 `SUCCESS` | fail-closed 校验 |

*此处写明一项决定，因为任务文本曾把 `REDIRECT_ERROR` 同时列在两个类别中：* 它是一个
`NETWORK_ERROR` 状态下的 kind。这正是重定向超限失败在 C2 之前的归类（没有任何现有结果改变状态），
而且此时没有收到任何可供判断的内容。

### 1.1 生产分类（P2-R-12）— `tests/unit/sources/test_failure_classification_c2.py`、`test_agg_retry_http.py`

| 事件 | `SourceStatus` / `SourceErrorKind` | 默认是否重试 |
|---|---|---|
| HTTP 500–599 | `INVALID_RESPONSE` / `HTTP_SERVER_ERROR` | **是** |
| transport 超时 | `NETWORK_ERROR` / `TIMEOUT` | **是** |
| DNS / 连接 / TLS / 协议错误 | `NETWORK_ERROR` / `CONNECTION_ERROR` | **是** |
| 响应体解码 / 解压错误，**包括**服务器指定的 `charset` 是非文本编解码器（`rot13`、`base64`、`hex`、`zlib`、`bz2`、`uu`…）、不可用的编解码器（`idna`、`undefined`、`punycode`）或名称格式错误（内嵌 NUL）— 自 C3-E02 起 | `NETWORK_ERROR` / `DECODE_ERROR` | **是** |
| 通用 transport 失败（较旧的 adapter、遗留的 `transport_error_result`） | `NETWORK_ERROR` / `NETWORK_ERROR` | **是** |
| HTTP 403，或 Cloudflare challenge（`cf-mitigated` header；**在任何 HTTP 状态下** — 200、403、429、5xx… — 响应体开头附近出现 "Just a moment…" / "Attention required" 的 `<title>`，自 C3-E01 起；或登录 / 验证重定向） | `BLOCKED` / `BLOCKED` | **永不** |
| HTTP 404 / “不在该来源的目录中” | `NOT_FOUND` / `NOT_FOUND` | 否 |
| HTTP 429 | `RATE_LIMITED` / `RATE_LIMITED` | 否 |
| 其他 non-200 状态（例如 301、418） | `INVALID_RESPONSE` / `INVALID_RESPONSE` | 否 |
| 无法解析的 200 页面 / 页面布局漂移 | `PARSE_ERROR` 或 `INVALID_RESPONSE`（通用） | 否 |
| 响应体过大 | `INVALID_RESPONSE` / `RESPONSE_TOO_LARGE` | 否 |
| 重定向循环 | `NETWORK_ERROR` / `REDIRECT_ERROR` | 否 |

`classify_transport_failure` / `transport_failure_result`（sources/base.py）是三个已采用的 adapter
现在使用的细化 helper。C2 之前的 `classify_transport_error` /
`transport_error_result` **没有改变**（粗粒度），为较旧的 adapter 及其测试而保留。
每一行 transport 分类在生产路径上的可达性，都用真实的 `HttpxTransport` 搭配
`httpx.MockTransport` 进行测试（httpx 异常 → transport 异常 → adapter 的 `SourceResult`）。

**C3 对本表的加固**（`tests/unit/aggregation/test_agg_c3_challenge_any_status.py`、
`tests/unit/http/test_httpx_transport_decode_c3.py`）：

* **challenge 优先（C3-E01，关闭 C2 复查 M1）。** 在 `classify_page_response` 中，challenge 检查
  排在任何状态分类*之前*：`cf-mitigated: challenge` → `blocked_url_markers` →
  前 4000 个字符中的 challenge `<title>`（任何状态下）。因此，没有 `cf-mitigated` header 的
  `503` + "Just a moment…" 响应体会被判为 `BLOCKED`，且恰好只有**一次** attempt，绝不会成为被重试的
  `HTTP_SERVER_ERROR`；404/429 下出现的 challenge 同样判为 `BLOCKED`。普通的 5xx（开头没有 challenge
  `<title>`）保持不变：`HTTP_SERVER_ERROR`，重试一次。
* **解码边界（C3-E02，关闭 C2 复查 L1）。** `HttpxTransport` 把每一种“响应体转文本”的失败
  （`LookupError` / `UnicodeError` / `ValueError`，无论来自最终解码*还是*来自 httpx 自身的
  charset 探测）都转换为 `HttpDecodingError` → `DECODE_ERROR` → 按 §2.1 重试。Python 完全不认识的
  charset 名称（`charset=nonsense`）不算失败：httpx 会回退到 UTF-8，页面以替换字符解码，与之前完全相同。
  错误消息会写出 charset 名称（截断），但绝不包含响应体。

## 2. `RetryPolicy`（`retry.py`）— `test_agg_retry_policy.py`

不可变、可哈希。默认值：`max_attempts = 2`、`initial_backoff_seconds = 1.0`、
`backoff_multiplier = 2.0`、`max_backoff_seconds = 5.0`、`retryable_error_kinds = RETRY_ELIGIBLE_KINDS`。

- **`max_attempts` 统计的是全部 attempt：** `2` = 第一次 attempt **加上最多一次重试**（不是
  1 + 2 次重试）；`1` 表示禁用重试。取值为 `1..5` 范围内的 `int`（不能是 `bool`）。
- 在第 `n >= 2` 次 attempt 之前的退避：`min(max_backoff_seconds, initial_backoff_seconds *
  backoff_multiplier ** (n - 2))`。**确定性，没有 jitter。** 使用默认策略时只有一次
  暂停（1.0 s）。校验（`AggregationConfigError`）：退避值必须有限、`>= 0`、`<= 600`；
  乘数必须有限、`>= 1`；`bool` 永远不被当作数字接受。
- **重试决策只看结构化的 `error_kind`** — `is_retryable(result)` / `should_retry(result,
  attempts_made)`。绝不看 `error_detail` 文本，也绝不看 provider 名称（`test_agg_guards.py` 中的
  AST 守护：`retry.py` / `execution.py` 中没有读取 `.error_detail`，没有字符串嗅探调用或字面量；
  `retry.py` 既不 import `httpx`，也不 import 任何 adapter）。
- `retryable_error_kinds` 只能**收窄**默认值：它必须是一个 `frozenset` ⊆
  `RETRY_ELIGIBLE_KINDS = {NETWORK_ERROR, TIMEOUT, CONNECTION_ERROR, DECODE_ERROR,
  HTTP_SERVER_ERROR}`。在 C2 中，`BLOCKED` 和 `RATE_LIMITED`（以及其他所有 kind）无法通过配置
  变成可重试。
- 配置：`AggregationConfig.retry_policy`（全局默认值）和 `SourceConfig.retry_policy`
  （单来源覆盖，`None` = 默认），两者都不可变；`AggregationConfig.retry_policy_for(id)`。
  provider 特有的行为是*数据*，绝不是针对某个 provider 的 `if/elif`。

### 2.1 重试决策矩阵（默认策略，`max_attempts = 2`）

| 某次 attempt 的最终结果 | 是否重试？ | attempt 次数（假设下一次 attempt 会成功） |
|---|---|---|
| `SUCCESS` | 否 | 1 |
| `NOT_FOUND`、`BLOCKED`、`RATE_LIMITED` | **否** | 1 |
| `PARSE_ERROR`、通用 `INVALID_RESPONSE` | 否 | 1 |
| `RESPONSE_TOO_LARGE`、`REDIRECT_ERROR` | 否 | 1 |
| `ADAPTER_EXCEPTION`、`RESULT_CONTRACT_MISMATCH` | 否 | 1 |
| `SOURCE_DEADLINE` | 否（预算已用完） | 1 |
| `TIMEOUT`、`CONNECTION_ERROR`、`DECODE_ERROR`、`HTTP_SERVER_ERROR`、通用 `NETWORK_ERROR` | **是** | 2 |
| 连续两次可重试失败 | — | 恰好 2 次，最终结果 = 第二次失败，**绝不会有第三次** |

各“否”行的理由：`NOT_FOUND` 是覆盖缺口，而不是失败（缺少某部影片的来源，永远不会因为另一个来源
有这部影片而被再次询问）；`BLOCKED`（403 / 反爬）绝不能被自动再次访问，这里也没有任何内容会绕过
Cloudflare/CAPTCHA；`RATE_LIMITED`（429）目前在 `SourceResult` 中不携带 `Retry-After`
信息，因此立即重复请求可能加剧限流 —
**C2 没有感知 `Retry-After` 的调度器，也没有新增**；解析 / 页面布局失败和合同失败是稳定的
（同一个页面每次都以同样方式解析）；响应体过大和重定向循环属于 provider / 配置层面的问题；
`SOURCE_DEADLINE` 表示时间预算已经用完。（`test_agg_retry_execution.py`、
`test_agg_retry_http.py`。）

## 3. 带重试的执行（`execution.py`）— `test_agg_retry_execution.py`

- **来源本地。** 重试在*同一个*执行槽位内重复调用 `adapter.fetch`；绝不会重新执行另一个来源。
  每次 attempt 都收到相同的规范番号和同一个共享 client。
- **每个来源严格串行；只占一个槽位。** 同一来源的各次 attempt 从不重叠，并且该来源在完成之前
  （包括退避期间）一直持有自己的并发槽位。因此，即使许多来源都在重试，adapter 并发 fetch 的峰值也
  `<= max_concurrency`（5 个来源、`max_concurrency=2` → 峰值 2；3 个各自重试的来源绝不会产生 4 个并发 fetch）。
- **总墙钟 deadline（C2 的关键不变量）。** `SourceConfig.deadline_seconds` 是整个来源的**一个**
  预算：第 1 次 attempt **+ 各次退避暂停 + 每一次重试**，由单个
  `asyncio.timeout` 强制执行。它**绝不是** `deadline × attempts`。测试：deadline 0.30 s，第 1 次 attempt = 0.15 s
  的可重试失败，退避 0.10 s，第 2 次 attempt 挂起 → 该来源在 ≈0.30 s 时结束（不是 ≈0.55 s）。
  * *deadline 发生在第 1 次 attempt 内* → `attempt_count == 1`，不重试，`NETWORK_ERROR`/`SOURCE_DEADLINE`。
  * *deadline 发生在退避暂停期间* → 下一次 attempt **根本不会开始**；trace 会如实记录
    （`deadline_during == "backoff"`，从未开始的 attempt 不出现在 `attempts` 中）。
  * *deadline 发生在某次重试 attempt 内* → 该 attempt 记录为 `completed=False`
    （`deadline_during == "attempt"`）；总耗时 ≈ 所配置的 deadline。
  * 等待并发槽位的排队时间**不**计入 deadline（沿用 C1 规则）。*（C5：等待共享 host 许可的排队时间同样不计入 — `PHASE3_RESOURCE_CONTROL_CONTRACT.md` §5.1。）*
- deadline 到期时的最终结果是 `NETWORK_ERROR`/`SOURCE_DEADLINE`，并带有真实的已耗时间。

## 4. 取消与致命异常（LOW-2）— `test_agg_low2_cancellation.py`

| 情况 | 行为 |
|---|---|
| 聚合任务被**调用方**取消（在某次 attempt 期间或退避暂停期间） | `asyncio.CancelledError` 原样传播；每个同级任务都被取消；**不留下任何后台任务**；不再开始新的 attempt；退避 sleep 立即被中断；取消永远不是可重试失败 |
| **adapter 自身**在其任务并未被请求取消时（`task.cancelling() == 0`）抛出 `CancelledError` | 该来源 → `INVALID_RESPONSE`/`ADAPTER_EXCEPTION`（detail：source id + `CancelledError`，不含消息）；**其他来源继续执行**；不重试；聚合任务不会被取消 |
| adapter 抛出 `KeyboardInterrupt`、`SystemExit`、`GeneratorExit` 或任何自定义的非 `Exception` 的 `BaseException` | 致命控制流：先取消同级任务，然后重新抛出**原始异常对象**（有身份一致性测试）— 绝不是 `BaseExceptionGroup`/`ExceptionGroup`，也绝不是 `SourceResult` |
| **多个**子任务（几乎）同时抛出*不同的*致命 `BaseException` | **同时出现的致命信号：只传播其中一个致命异常；实现不会保留多个致命异常。** engine 选中的第一个致命异常以原始对象重新抛出（不构建异常组），其余的被丢弃 — 调用方无法检查全部致命异常。对于给定的调度顺序，结果是确定的；由 `tests/unit/aggregation/test_agg_c3_simultaneous_fatal.py` 固定下来。（在 C3 中记录，复查 C2-L5；未重新设计。） |
| adapter 抛出的普通 `Exception` | 被隔离：`INVALID_RESPONSE`/`ADAPTER_EXCEPTION`，绝不包含异常消息 |

**已知局限（已记录，未解决；C2 中没有线程 / 进程隔离）：** 捕获并吞掉 `CancelledError` 后继续运行的
插件 adapter，无法被 `asyncio.timeout` 中断 — 如果它最终返回，则使用它自己的结果（当前行为由
`test_documented_limitation_…` 固定下来）。三个已采用的 adapter（`fc2db_net`、`javdb`、`av123`）不会
吞掉取消：已通过行为测试（挂起的 client 会被及时取消；engine 的 deadline 能让每个 adapter 停下）**和**
静态检查（adapter 模块中任何地方都没有裸 `except`、没有 `except BaseException`、没有 `CancelledError`
处理器）验证。如果将来要运行第三方插件 adapter，会考虑更强的隔离。

## 5. Attempt 诊断信息（`models.py`）— `test_agg_retry_execution.py`、`test_agg_low1_result_invariants.py`

`AggregationResult.source_execution_traces`：每个**启用的**来源对应一个不可变的 `SourceExecutionTrace`，
顺序与 `source_results` 一致（只有在没有执行、纯 merge 的情况下才为空）；禁用的来源没有 trace；
每个 `trace.final_result == source_results[i]`。

`SourceExecutionTrace(source_id, attempts, final_result, max_attempts, deadline_exceeded,
deadline_during)`，属性 `attempt_count`（*已开始*的 attempt 数）和 `retried`。
`SourceAttempt(sequence, status, error_kind, elapsed_ms, completed, backoff_before_seconds)`。
构造时强制执行的不变量 *（C5：`attempts` 可以为空，**当且仅当** `final_result.error_kind is CIRCUIT_OPEN` — 没有发出任何请求 — 此时不得记录任何 deadline）*：sequence 按顺序为 `1..n`，且 `n <= max_attempts`；只有最后一次
attempt 可以未完成；`SUCCESS` 之后不能再有 attempt；最后一次 attempt 未完成 ⇔
`deadline_during == "attempt"`；`"backoff"` ⇒ 最后一次 attempt 已完成，且已进行的次数少于
`max_attempts`；deadline 到期的结果为 `NETWORK_ERROR`/`SOURCE_DEADLINE`，否则
`final_result` 与最后一次 attempt 的状态和 kind 一致。

每次 attempt 的 `elapsed_ms` **由 engine 测量**。即使 adapter 返回的
`SourceResult.elapsed_ms` 为 `0.0`，它也是真实值（**P2-R-07：已重新评估，部分缓解，仍为 LOW** —
adapter 上报的值被刻意保持不变；只有 trace 携带真实耗时）。
这些模型只能保存状态、结构化 kind 和计时 — **不**保存响应体、cookie、authorization header 或凭据
（字段集合由测试断言）。

## 6. 聚合语义只使用最终结果 — `test_agg_retry_execution.py`、`test_agg_retry_http.py`

只有每个来源的**最终** `SourceResult` 会进入 `merge_source_results`。因此：

* 第 1 次 attempt 为 `NETWORK_ERROR`/`TIMEOUT`，第 2 次 attempt 为 `SUCCESS`，外加另一个正常来源 ⇒ 聚合结果
  **`SUCCESS`**（不是 `PARTIAL`）；第一次失败仍在 trace 中可见；
* 第 1 次和第 2 次 attempt 都是 `HTTP_SERVER_ERROR`，外加另一个 `SUCCESS` ⇒ 聚合结果 **`PARTIAL`**；
* 失败 attempt 的部分 metadata、返回了另一个番号或另一个 `source_id` 的重试
  （fail-closed → `RESULT_CONTRACT_MISMATCH`），或伪造的出处声明，都永远不会进入聚合结果。

促成 C2 的真实案例 — `av123` 先出现一次瞬时 HTTP 500，随后返回 200 — 已端到端覆盖：
最终 `SUCCESS`，`attempt_count == 2`，聚合结果 `SUCCESS`；不做重试时，同样的序列就是 C1 的
`PARTIAL`（两者都有测试）。

## 7. 在 C2 中关闭的 C1 加固项

* **LOW-1**（`test_agg_low1_result_invariants.py`）：加强了 `AggregationResult` 的不变量 — 见
  `aggregation/models.py` 中的列表以及 `PHASE3_AGGREGATION_CONTRACT.md` §4。
* **LOW-2**：见上文 §4。
* **LOW-3**（`test_agg_low3_config_immutability.py`）：*直接*调用 `AggregationConfig(...)` 构造函数时，
  只接受形如 `tuple[tuple[str, tuple[str, ...]], ...]` 的 `field_priority`；任何 list/dict/set/
  嵌套 list/None 或不可哈希或非 `str` 的字段名/格式错误的 tuple → `AggregationConfigError`
  （绝不是 `TypeError`/`KeyError`/`AttributeError`）。在 `create()` 之后修改调用方持有的对象，
  不能改变配置本身、其 hash 或其策略。
* **LOW-4**（`test_agg_low4_client_shape.py`）：`MultiSourceEngine(...)` 在构造时、在任何请求之前，
  拒绝 `get` 不是 `async` 可调用对象的 client（`is_async_get`：接受 coroutine function、
  绑定的 async 方法、对其做的 `functools.partial`、带 `async def __call__` 的对象以及 `AsyncMock`；
  拒绝普通的 `def get`，即使它返回的是 coroutine）。

## 8. 批处理规划说明（C3 必需）

`max_concurrency` 是**每次 `aggregate()` 调用**各自的 semaphore。因此，未来并发执行大量
`aggregate()` 调用的批处理*没有*全局并发上限 — `gather(500 ×
engine.aggregate())` 会让每个条目都拥有自己的 semaphore。Phase 3 的批处理**必须**引入跨条目的
全局并发 / 资源预算（并随之引入按 host 的限制和熔断器）。C2 对此一项都没有实现。
*（C4 增加了按调度器的条目预算；C5 以可选启用的 `governor=` 形式增加了共享的按 host 限流器和
按来源的熔断器 — `PHASE3_RESOURCE_CONTROL_CONTRACT.md`。）*
