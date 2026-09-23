# PHASE3_C2_HANDOFF.md

```text
Phase: Phase 3 / C2 — Resilience & Retry

Base (Phase 3 C1 Docs Head; C1 handoff commit):
c2a749ec3dae7428a9475b9b2c28ad114c3c0f4b

PHASE3_C2_CODE_HEAD (Phase 3 C2 Code Review Candidate):
81f80c2532732edd8bdb4a5962de347dda66de6e
  = 3baf7d6  feat(source): add structured failure taxonomy and classify transport/HTTP failures (P2-R-12)
  + 895125d  feat(aggregation): add Phase 3 C2 bounded retry, total deadline, attempt diagnostics and C1 LOW-1..4 fixes
  + 81f80c2  docs(aggregation): add Phase 3 C2 resilience contract and probe attempt diagnostics

Formal review range:
c2a749ec3dae7428a9475b9b2c28ad114c3c0f4b..81f80c2532732edd8bdb4a5962de347dda66de6e

PHASE3_C2_DOCS_HEAD:
the commit "docs(review): add Phase 3 C2 handoff" whose parent is the Code Head above
and whose only change is this file (docs diff: CODE_HEAD..DOCS_HEAD). A commit cannot
contain its own hash, so it is identified by that rule and reported in the hand-back message.

Branch:
claude/phase-0-amane-integration-fnvhpq
```

**这不是 PASS 声明。** 这是提交给 Phase 3 C2 独立复查的候选。Phase 3 C3 以及之后的每一个子阶段都**尚未**开始。

权威规格：`docs/specifications/PHASE3_RESILIENCE_CONTRACT.md`（新增）。
只在 C2 改动过的地方做了修订：`PHASE3_AGGREGATION_CONTRACT.md`（标注为 "(C2)"）、
`FC2_METADATA_CORE_CONTRACT.md` §3（`SourceErrorKind`）。

## LOW-1 … LOW-4（C1 复查 finding）— CLOSED，每一项都有自己的回归测试文件

| Finding | 修复 | 回归测试 |
|---|---|---|
| LOW-1 `AggregationResult` 可能被构造得不一致 | 不变量变得精确（`contributing_source_ids == successful_source_ids`；`disabled_source_ids` 的形态 / 不相交性；`FieldConflict` 对照 `CONFLICT_FIELDS` 和贡献来源校验；trace 与结果对齐）。模块 docstring 列出了强制执行的内容，**以及不校验的内容**（值 / `field_sources` / 冲突的完整性）— “无法构造出不一致的结果”这一说法被收窄为该列表 | `test_agg_low1_result_invariants.py` |
| LOW-2 取消 | 调用方取消 → 原始的 `CancelledError`，同级任务被取消，没有残留任务，退避被中断；adapter 自行抛出的 `CancelledError`（`task.cancelling()==0`）→ 被隔离为 `ADAPTER_EXCEPTION`；致命 `BaseException` → **原始对象**（有身份一致性测试，没有异常组） | `test_agg_low2_cancellation.py` |
| LOW-3 直接调用 `AggregationConfig(...)` 时接受了可变的 `field_priority` | 在 `__post_init__` 中校验严格的形态 `tuple[tuple[str, tuple[str, ...]], ...]`；其他任何值 → `AggregationConfigError`（绝不是 `TypeError`） | `test_agg_low3_config_immutability.py` |
| LOW-4 engine 接受了 `get` 不是 async 的 client | 在构造 `MultiSourceEngine` 时、在任何请求之前做 `is_async_get` 检查 | `test_agg_low4_client_shape.py` |

## 失败分类（P2-R-12 — 见下文）

`SourceStatus` 没有改变。`SourceErrorKind` 新增了 `TIMEOUT`、`CONNECTION_ERROR`、`DECODE_ERROR`、
`REDIRECT_ERROR`、`SOURCE_DEADLINE`、`HTTP_SERVER_ERROR`、`RESPONSE_TOO_LARGE`、`ADAPTER_EXCEPTION`、
`RESULT_CONTRACT_MISMATCH`。`ALLOWED_ERROR_KINDS` 冻结了哪些 kind 可以与哪个状态搭配（`SourceResult` 拒绝其他任何组合）；
六个通用 kind 被保留，因此每一个 C2 之前的结果仍然能通过校验。`REDIRECT_ERROR` 是一个 `NETWORK_ERROR` 状态下的 kind
（它原本就是如此；这是一项明确陈述的决定）。

## RetryPolicy

`max_attempts` 统计**全部** attempt（默认 2 = 第一次 attempt + 最多一次重试；`1` = 不重试；上限 5）；
`initial_backoff_seconds=1.0`、`backoff_multiplier=2.0`、`max_backoff_seconds=5.0`；
确定性的，**没有 jitter**。决策**只**依据结构化的 `error_kind`（AST 守护禁止在 `retry.py`/`execution.py` 中读取
`error_detail` 或做字符串嗅探；没有 provider 名称）。
`retryable_error_kinds` 只能在 `{NETWORK_ERROR, TIMEOUT, CONNECTION_ERROR, DECODE_ERROR,
HTTP_SERVER_ERROR}` 的范围内收窄；`BLOCKED`/`RATE_LIMITED` 永远无法被设为可重试。全局默认值在
`AggregationConfig` 上，单来源覆盖值在 `SourceConfig` 上，两者都不可变。

## 重试矩阵（默认策略）

| 结果 | 是否重试 | attempt 次数 |
|---|---|---|
| `SUCCESS` | 否 | 1 |
| `NOT_FOUND`、`BLOCKED`、`RATE_LIMITED`（HTTP 404 / 403+Cloudflare / 429） | **永不** | 1 |
| `PARSE_ERROR`、通用 `INVALID_RESPONSE`、`RESPONSE_TOO_LARGE`、`REDIRECT_ERROR`、`ADAPTER_EXCEPTION`、`RESULT_CONTRACT_MISMATCH` | 否 | 1 |
| `SOURCE_DEADLINE` | 否 | 1 |
| `TIMEOUT`、`CONNECTION_ERROR`、`DECODE_ERROR`、`HTTP_SERVER_ERROR`（500–599）、通用 `NETWORK_ERROR` | 是 | ≤ 2（绝不会有第三次） |

不存在任何 `Retry-After` 处理（也没有新增）。不绕过 CAPTCHA/Cloudflare。细节和理由见：
`PHASE3_RESILIENCE_CONTRACT.md` §2.1。

## Deadline + 重试（总墙钟时间）

`SourceConfig.deadline_seconds` 是第 1 次 attempt + 退避 + 每一次重试共用的**一个**预算（单个
`asyncio.timeout`），绝不是 `deadline × attempts`。已测试：A) deadline 发生在第 1 次 attempt 内 → 1 次 attempt，
不重试，`SOURCE_DEADLINE`；B) deadline 发生在退避期间 → 下一次 attempt 永远不会开始
（`deadline_during == "backoff"`）；C) deadline 发生在重试 attempt 内 → 记录为 `completed=False`；
D) 0.30 s 的预算，0.15 s 的失败 attempt + 0.10 s 的退避 + 挂起的重试，在 ≈0.30 s 时结束，而不是
≈0.55 s。退避是确定性的，并且会占用该来源唯一的并发槽位；同一来源的 attempt 严格串行；即使每个来源都在重试，
fetch 的并发峰值也 ≤ `max_concurrency`。
等待槽位的排队时间不计入 deadline。

## 取消 / BaseException

见上文的 LOW-2 以及 `PHASE3_RESILIENCE_CONTRACT.md` §4。**已记录的局限（未解决）：** 捕获并吞掉 `CancelledError`
后继续运行的 adapter，无法被 `asyncio.timeout` 中断；C2 中没有线程 / 进程隔离。三个已采用的 adapter
（`fc2db_net`、`javdb`、`av123`）已被证明不会吞掉取消 — 从行为上（挂起的 client 会被及时取消，deadline 能让每个都停下）
以及从静态上（它们的模块中没有裸 `except`、没有 `except BaseException`、没有 `CancelledError` 处理器）。

## Attempt 诊断信息

`AggregationResult.source_execution_traces` = 每个启用的来源一个 `SourceExecutionTrace`（按配置顺序）：
`attempts`（`SourceAttempt(sequence, status, error_kind, elapsed_ms, completed,
backoff_before_seconds)`）、`final_result`、`max_attempts`、`deadline_exceeded`、`deadline_during`、
`attempt_count`、`retried`。只有状态、结构化 kind 和计时 — 没有响应体 / cookie / header / 错误文本。
**只有最终结果会被合并**：第 1 次 attempt 瞬时失败 + 第 2 次 attempt 成功 ⇒ 该来源算作成功，聚合结果为 `SUCCESS`
（不是 `PARTIAL`），第一次失败在 trace 中可见；两次都失败 ⇒ 该来源算作失败，聚合结果为 `PARTIAL`。

## P2-R-07 — 未关闭

已重新评估：**部分缓解，仍为 LOW。** engine 现在自己测量每次 attempt 的 `elapsed_ms`，因此即使 adapter 上报
`SourceResult.elapsed_ms == 0.0`，诊断信息也是正确的；adapter 上报的这个字段本身被刻意保持不变。

## P2-R-12 — CLOSED

这是结构性的关闭，而不是对映射的微调：(1) 结构化的分类，并强制执行状态 ↔ kind 的关系；(2) 生产分类：
HTTP 500–599 → `INVALID_RESPONSE`/`HTTP_SERVER_ERROR`；transport 的超时 / 连接 / 解码 / 重定向 / 超大响应 →
各自不同的 kind；403/Cloudflare 为 `BLOCKED`，404 为 `NOT_FOUND`，429 为 `RATE_LIMITED`，其他 non-200 以及语义漂移
保持为不可重试的通用 kind；(3) `HttpxTransport` 现在对 `httpx.DecodingError` 确实会抛出 `HttpDecodingError`
（通过 `httpx.MockTransport` 复现了垃圾 gzip/deflate；未知 charset 不会泄漏）；(4) 重试决策只读取 `error_kind`。
经由生产路径的证明（真实 adapter + 基于 `httpx.MockTransport` 的真实 `HttpxTransport`）：
`test_agg_retry_http.py`（84 个测试）以及 `tests/unit/sources/test_failure_classification_c2.py`（38）。
遗留的粗粒度 helper 没有改变。

## 离线测试

```text
python --version                      Python 3.12.10
python -m pytest --collect-only -q    1305 tests collected
python -m pytest -v                   1305 passed, 0 failed, 0 skipped (0 xfail/error)
python -m pytest -q                   1305 passed
```

先按顺序运行了针对性测试集，全部通过：Phase 1 SourceResult/分类/metadata（284）→
transport（8）→ source/base/common 分类（302）→ 聚合 config/models/重试策略
（259）→ execution/重试（190）→ merge/engine/guards（96）→ LOW-1..4（134）。冻结基线：base 提交有 732 个测试；
在 C2 源码上运行，**731 个通过**，1 个失败 —
`test_agg_guards.py::test_no_retry_backoff_or_circuit_breaker_in_c1`，即断言“不存在重试”的 C1 守卫。该守卫被
**有意替换**为只针对熔断器的守卫，外加针对 `error_detail`/字符串嗅探的 AST 守卫（重试现在按设计存在）。
除了测试支持 helper 之外（纯增量：`failed(..., error_kind=)`、`add_sequence`、`request_count`），base 测试集中
没有其他内容被修改。新增的 C2 测试：分类、重试策略、重试执行（deadline A–D、矩阵、取消、并发）、生产路径 HTTP、
分类、LOW-1..4 以及探测摘要。

> **更正（在 Phase 3 C3 中添加，finding C2-L4；上面的原文保持原样）。**
> “base 提交有 732 个测试”是错误的。C1 base 提交（`c2a749e`）本身收集到的是 **731** 个测试。
> 732 这个数字来自在 C2 *源码树*中运行 C1-base 的*测试树*：F4 合同测试会自动发现 `src/` 下的每个模块，
> 因此新增的 `aggregation/retry.py` 增加了一个按模块参数化的用例（731 + 1 = 732）。因此 “731 pass, 1 fails”
> 是 C1 测试针对 C2 源码的结果，其中唯一的失败就是被有意替换的 C1 “无重试”守卫。

测试隔离说明（与 C1 相同）：在测试中应在模块顶部 import core 类 — F4 合同测试会重新 import 整个 package。

## 线上 7-ID 冒烟测试（`tools/probe_aggregate.py`，低频率，ID 之间间隔 3 s，不记录任何内容）

在代码稳定之后、冻结 head 之前运行了一次。输出只在一个任务临时文件中查看；**没有写入任何证据文件，
也没有触碰 Phase 2 证据 JSON**。

| ID | 聚合结果 | fc2db_net | javdb | av123 |
|---|---|---|---|---|
| FC2-4825061 | success | not_found (404) ×1 | success ×1 | success ×1 |
| FC2-4824605 | success | success ×1 | not_found ×1 | not_found (404) ×1 |
| FC2-4979299 | success | success ×1 | success ×1 | success ×1 |
| FC2-4976588 | success | success ×1 | success ×1 | not_found (404) ×1 |
| FC2-1042815 | success | success ×1 | success ×1 | not_found (404) ×1 |
| FC2-4978035 | success | success ×1 | success ×1 | success ×1 |
| FC2-4972767 | success | success ×1 | success ×1 | not_found (404) ×1 |

7/7 聚合结果为 `success`；每个来源的 `attempt_count == 1`。**这次运行中没有自然发生瞬时失败，因此没有观察到线上的
重试行为** — 重试已通过离线测试证明（包括使用真实 transport 的生产路径），并没有声称经过线上验证。
`not_found` 结果正确地从未被重试。这是一次冒烟检查，而不是覆盖率声明。

## 50-ID 门槛 — 未运行 / 延后

在冻结的 50-ID 集合上 ≥ 90 % `number + title` 的门槛**没有运行**，也没有作出任何声明。

## 批处理 / 熔断器 / NFO / Amane — NOT STARTED

没有批处理引擎、全局批处理 semaphore、500-item 批次、失败子集重试、熔断器、NFO writer、图片下载、文件重命名 /
移动 / 整理、Amane adapter 或 GUI。**给 C3 的规划说明：**
`max_concurrency` 是每次 `aggregate()` 调用各自的；批处理必须引入跨条目的全局并发 / 资源预算（外加按 host 的限制
和熔断器）— 它不能是 `gather(500 × aggregate())`。

## 剩余的待办

- **P2-R-05** 探测工具的 `anti_bot_hint` 仅凭 `cf-ray` 就会触发 — LOW。
- **P2-R-06** 探测工具的 `requested_url` 是最终 URL — LOW。
- **P2-R-10** JavDB 标题被重复反转义 — LOW，保持原样。
- **P2-R-07** 部分缓解，仍为 LOW（见上文）。
- **F3、F5** — DEFERRED（必须在 Phase 5 集成之前关闭）；C2 没有触碰它们的机制。
  **F4** 保持 CLOSED。

## 建议的复查重点

1. `aggregation/execution.py`：总 deadline 的作用范围与退避 / 重试的关系；`_FatalSignal` 的解包；确认没有任何路径
   吞掉来自调用方的 `CancelledError`。
2. `models/source_result.py` 中 `ALLOWED_ERROR_KINDS` 的关系，以及 `REDIRECT_ERROR` 归属的决定。
3. 确认 `retry.py`/`execution.py` 只依据 `error_kind` 做决策（`test_agg_guards.py` 中的 AST 守护）。
4. `AggregationResult`/`SourceExecutionTrace` 的不变量与“不校验的内容”列表之间的对照。
