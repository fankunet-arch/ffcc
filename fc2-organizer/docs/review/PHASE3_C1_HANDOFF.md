# PHASE3_C1_HANDOFF.md

```text
Phase: Phase 3 / C1 — Multi-source Aggregation Core

Base (Phase 3 Entry C0 R1 Docs Head; C0 CLOSED, Aggregator Lock RELEASED):
26ac53714c69f7c716cdcbe66783bebe1d2be118

PHASE3_C1_CODE_HEAD (Phase 3 C1 Code Review Candidate):
652f1dea7ec2dd1ca93d278906d0d487e6df2f19
  = 1e12c6b  fix(source): harden SourceRegistry.create boundary (P2-R-11)
  + 26917af  feat(aggregation): add Phase 3 C1 multi-source aggregation core
  + 652f1de  test(aggregation): assert the original BaseException propagates unwrapped

Formal review range:
26ac53714c69f7c716cdcbe66783bebe1d2be118..652f1dea7ec2dd1ca93d278906d0d487e6df2f19

PHASE3_C1_DOCS_HEAD:
the commit "docs(review): add Phase 3 C1 handoff" whose parent is the Code Head
above and whose only change is this file (docs diff: CODE_HEAD..DOCS_HEAD).
A commit cannot contain its own hash, so it is identified by that rule and
reported in the hand-back message.

Branch:
claude/phase-0-amane-integration-fnvhpq
```

**这不是 PASS 声明。** 这是提交给 Phase 3 C1 独立复查的候选。之后的 Phase 3 子阶段（C2+）**尚未**开始。

## 架构

新 package `src/fc2_metadata_core/aggregation/`（不 import `amane`，不 import 任何具体 adapter，除 `defaults.py`
之外不出现任何 provider 名称 — 三者都由测试强制执行）：

```text
canonical FC2 number
   | MultiSourceEngine.aggregate(number)                      engine.py
   v
ordered SourceConfig (configured order = default field priority)   config.py policy.py defaults.py
   | execute_sources(...)  bounded fan-out, per-source wall-clock deadline,
   |                       isolation, fail-closed validation   execution.py
   v
SourceResult x N  (one per enabled source, configuration order)
   | merge_source_results(...)   PURE: no network / clock / asyncio       merge.py
   v
AggregationResult  SUCCESS | PARTIAL | FAILED + every SourceResult        models.py
```

| 模块 | 职责 |
|---|---|
| `policy.py` | 字段常量、`AggregationPolicy`（默认优先级 + 每个字段的完整优先级顺序）、`AggregationConfigError` |
| `config.py` | 不可变的 `SourceConfig` / `AggregationConfig`、`validate_base_url`、各项限制 |
| `defaults.py` | 唯一出现 provider 名称的地方 — 以数据形式给出 `DEFAULT_SOURCE_ORDER = (fc2db_net, javdb, av123)` |
| `execution.py` | `SourceTarget`、`execute_sources`（`Semaphore`、`asyncio.timeout`、`TaskGroup`） |
| `merge.py` | `merge_source_results`、`validate_source_result`（纯函数） |
| `models.py` | `AggregationResult`、`AggregateStatus`、`FieldConflict`、不变量 |
| `engine.py` | `MultiSourceEngine(config, registry, client)`：把上述各部分连接起来 |

其他改动：`SourceRegistry.create` 边界加固（P2-R-11）；`sources/adapters` 中的 `build_default_registry()`；
`tools/probe_aggregate.py`（线上冒烟测试，默认不记录任何内容）。

## 合同决定（全文：`docs/specifications/PHASE3_AGGREGATION_CONTRACT.md`）

- **聚合状态。** `SUCCESS` = 合并后的 metadata 满足最低成功标准，**并且**没有任何启用的来源发生*运行性*失败
  （`BLOCKED`、`RATE_LIMITED`、`NETWORK_ERROR`、`PARSE_ERROR`、`INVALID_RESPONSE`）。**`NOT_FOUND` 是正常的覆盖缺口，
  永远不会降级为 `PARTIAL`。** `PARTIAL` = 满足最低成功标准的 metadata + ≥ 1 次运行性失败。`FAILED` = 没有任何可用
  内容（`metadata is None`），但**保留全部 `SourceResult`**。`AggregationResult.__post_init__` 使不一致的结果无法被构造。
- **来源顺序 / 优先级。** 配置的来源顺序就是每个字段的默认优先级；可以按字段覆盖（经过校验：已知字段、已配置的来源、
  没有重复、`number` 不可覆盖）。覆盖项列出部分来源；其余来源按默认顺序跟在后面 — 每个字段都有一个完整的顺序。
- **标量**（`title studio publisher release runtime plot`）：按字段优先级取第一个非空值；相等的值互相佐证；
  不同的值记录为 `FieldConflict`。**`number`** 总是请求的番号。
- **集合**（`actors tags poster_urls thumb_urls fanart_urls extrafanart
  source_urls`）：按优先级做保序去重并集；**只按字符串严格相等去重**（不做大小写折叠 / 翻译 / 模糊匹配）；
  跳过空白项；使用 tuple。
- **`external_ids`**：逐个 key 处理，**先到者胜出**（绝不是最后写入者胜出）；冲突记录在
  `AggregationResult.conflicts` 中（新增了模型，而不仅仅是写进文档）。
- **`field_sources`**：根据*槽位的 source id + 实际的值*重新计算；adapter 自己的 `field_sources` 被忽略
  （伪造的声明无法泄漏 — 有测试）。番号 → 每一个贡献来源（默认顺序）；标量 → 值等于被选中值的来源；
  集合 / `external_ids` → 提供了 ≥ 1 个非空条目的来源。
- **Fail closed。** `source_id` 错误、非 `SourceResult`，或针对另一个番号的 `SUCCESS`，会变成该槽位的
  `INVALID_RESPONSE`，并且不贡献任何内容。
- **确定性。** 输出只取决于 `(number, results in slot order, policy)`。

## 来源执行

- 一个共享的 `SourceHttpClient`（由调用方提供）；engine 不创建任何 transport。
- `asyncio.Semaphore(max_concurrency)`，默认值 **3**，可配置 `1..64`；通过活跃峰值计数器证明
  （既遵守了上限，**也**达到了上限 — 不是串行）。
- 结果按**配置顺序**返回（测试中用 sleep 强制让完成顺序反转）。
- 单来源的**墙钟 deadline**（默认 **20 s**，可配置，`> 0 … ≤ 600`）：
  在 engine 边界上使用 `asyncio.timeout`，adapter 没有改动。从该来源开始运行时起算（而不是排队期间）。
  到期 → 只有该来源变为 `NETWORK_ERROR`，`error_detail` 为 "… source execution deadline exceeded (…)"，
  带有真实的 `elapsed_ms`；其他来源继续执行。adapter 自己抛出的 `TimeoutError` 不会被误认为是 deadline 到期。
- **隔离**：任何普通 `Exception` → 该来源的 `INVALID_RESPONSE`，detail = source id + 异常*类型*
  （绝不包含异常消息 — 其中可能有 URL / secret；已用一条带 secret 的消息测试）。
- **取消**：`CancelledError`、`KeyboardInterrupt`、`SystemExit` 永远不会变成来源结果。已验证：*原始*异常不经包装
  地传播，进行中的同级任务被取消（`TaskGroup`）。

## 已关闭 / 重新延后的 finding

| ID | 结果 |
|---|---|
| **P2-R-08** 格式错误的 `base_url` → 原始异常 | **在 Phase 3 配置边界上 CLOSED。** `validate_base_url` 在构造 `SourceConfig` 时运行，拒绝以下情况（领域错误 `AggregationConfigError`，在任何网络活动之前）：缺少 scheme、缺少 host、非 http(s)、userinfo、query/fragment、端口错误、host 非法、任何控制字符（CR/LF/NUL/TAB）、空格、反斜杠、非 ASCII、> 2048 个字符。adapter 没有被重写。（`test_agg_config.py`：9 个合法 + 33 个非法 URL。） |
| **P2-R-09** httpx 超时不是墙钟上界 | **在调度器边界上 CLOSED。** 每个来源整个 `fetch` 的 deadline（见上文）；一个持续缓慢推进的来源仍然会被切断（有测试）。局限：吞掉 `CancelledError` 的 adapter 无法被中断（已采用的 adapter 都不会这样做）。 |
| **P2-R-11** registry 的创建边界 | **CLOSED。** `create()` 返回一个 `source_id` 等于所请求 id 的 `SourceAdapter`，否则抛出 `SourceFactoryError` / `InvalidSourceAdapterError` / `SourceIdMismatchError`（都是 `SourceRegistryError`）；不可调用的 factory 在 `register` 时被拒绝；仍然支持类以外的 factory。复现并关闭了复查者的两个例子（`alias_x` → `Fc2dbNetAdapter`、`lambda **k: 42`）。 |
| **P2-R-12** 分类上的细微差别（5xx → `INVALID_RESPONSE`、部分解码错误 → `NETWORK_ERROR`、重试语义） | **已重新评估 → 重新延后到 Phase 3 的韧性 / 重试子阶段。** 原因：C1 只对 `SourceStatus` 做*隔离和聚合*；它不根据状态做任何重试、退避或熔断决策，因此 C1 中没有任何内容依赖细粒度分类，而现在重写 Phase 2 的失败词汇只会是投机性的。这不是遗漏。线上观察到的实际影响：一次瞬时的 av123 HTTP 500 会成为 `INVALID_RESPONSE` → 计为运行性失败 → 聚合结果 `PARTIAL`（见下文）。 |

## 变更文件（`26ac537..652f1de`，21 个文件，+3341/−7）

```text
A docs/specifications/PHASE3_AGGREGATION_CONTRACT.md
M src/fc2_metadata_core/__init__.py                     (imports aggregation)
A src/fc2_metadata_core/aggregation/{__init__,config,defaults,engine,execution,merge,models,policy}.py
M src/fc2_metadata_core/sources/__init__.py             (exports new registry errors)
M src/fc2_metadata_core/sources/adapters/__init__.py    (+build_default_registry)
M src/fc2_metadata_core/sources/registry.py             (create boundary)
A tests/support/scripted_adapters.py
A tests/unit/aggregation/test_agg_{config,engine,execution,guards,merge}.py
A tests/unit/sources/test_registry_create_boundary.py
A tools/probe_aggregate.py
```

没有改动任何 adapter、`_scan.py`、transport、模型、Phase 2 证据 JSON 或任何已关闭的 C0/C0-R1 项。

## 离线测试

```text
Python 3.12.10
python -m pytest --collect-only -q   -> 731 tests collected
python -m pytest -v                  -> 731 passed
python -m pytest -q                  -> 731 passed
```

| | 计数 |
|---|---|
| collected | **731** |
| passed | **731** |
| failed | 0 |
| skipped | 0 |

**相比冻结的 473 个 +258** = 250 个新测试（config 94、merge 46 — 纯 merge 测试是除 config 之外最大的一组 —
execution 50、engine 20、guards 22、registry boundary 18）+ 8 个，因为
`tests/contract/test_core_independent_of_amane.py` 对每个模块做参数化（F4 保持通过，现在还覆盖了八个新模块）。
全部 473 个原有测试原样通过。计时测试使用短暂的真实 sleep（≤ 0.3 s），并留有很宽的余量。
C1 要求的测试列表（1–24）都已覆盖；编号出现在测试名称中（`test_01…` … `test_24…`），包括并发
（5 个来源，`max_concurrency=2` → peak == 2）、反转的完成顺序、deadline、取消、伪造的 `field_sources`、
错误的番号 / `source_id`、垃圾 / 不匹配的 registry factory、格式错误的 `base_url`。**三个真实 adapter**
也通过默认配置、基于逐字摘录的真实响应 fixture 做了端到端测试（不访问网络）。

*测试隔离说明：* F4 合同测试会重新 import 整个 package，因此**在函数内部** import core 类的测试，拿到的类对象与
在模块顶部 import 的测试不同（`isinstance` 会失败）。我最初写的两个测试就是这样，只在全量运行时失败；
改为在模块顶部 import 后修复。后续编写测试的人值得了解这一点。

## 线上聚合冒烟测试（`tools/probe_aggregate.py`，不记录任何内容）

默认配置 `fc2db_net > javdb > av123`，一个共享的 `HttpxTransport`，番号之间间隔 3 s，每个番号每个来源一个请求；
Windows 公网。Phase 2 证据 JSON 没有被触碰。

**在 `652f1de` 上，2026-09-20 16:47:00–16:47:24 UTC — 7/7 `SUCCESS`：**

| 番号 | 聚合结果 | 各来源结果（fc2db_net / javdb / av123） | 标题来源 | 备注 |
|---|---|---|---|---|
| **FC2-4825061** | SUCCESS | not_found / success / success | `javdb`（日文） | 已知的 fc2db_net 覆盖缺口*不算*失败；runtime 39 + 标签来自 av123 |
| **FC2-4824605** | SUCCESS | success / not_found / not_found | `fc2db_net` | javdb 模糊近似未命中 ⇒ not_found；av123 缺口 |
| **FC2-4979299** | SUCCESS | success / success / success | `fc2db_net`、`javdb` | `number`←3 个来源；tags = 并集（23），source_urls 3，thumbs 2，external id 来自 javdb；冲突：`title`（av123 英文）和 `runtime`（av123）以 fc2db_net 为准解决 |
| FC2-4976588 | SUCCESS | success / success / not_found | `fc2db_net` | |
| FC2-1042815 | SUCCESS | success / success / not_found | `fc2db_net` | 旧 id |
| FC2-4978035 | SUCCESS | success / success / success | `fc2db_net` | |
| FC2-4972767 | SUCCESS | success / success / not_found | `fc2db_net` | |

在 `26917af` 上一次相同的 7/7 运行（代码相同；`652f1de` 只改了一个测试和一句合同文字）得到了相同的状态。
覆盖不均衡从未导致任何影片失败。

**观察到并留档的一次瞬时失败。** 在我*第一次*线上运行时（三个主要番号，在代码冻结之前），`av123` 对 FC2-4825061 和
FC2-4824605 返回了 **HTTP 500**（同一时刻对单个 adapter 的直接探测也是如此；几分钟后恢复 — 16:43 时为 200）。
engine 的行为符合设计：`FC2-4825061` 的结果为 **PARTIAL**（`javdb` 成功，标题来自 `javdb`，`av123` = `INVALID_RESPONSE`
"unexpected HTTP 500"，`fc2db_net` = not_found），`FC2-4824605` 为 **PARTIAL**，标题来自 `fc2db_net`。
这正是预期的 `PARTIAL` 语义，也是一个具体的例子，说明一旦有了重试，P2-R-12（5xx 分类）为什么重要。

## 50-ID 验收门槛 — 未运行，延后

v1.0 门槛（冻结的 50-ID 有效集合，≥ 90 % 获得 `number + title`）**没有**运行，也**没有**作出任何声明。
它需要一份冻结的 ID 列表和一个实时覆盖子阶段；这里没有为了满足它而临时拼凑番号。上面的 7 个探测集合 ID 只是冒烟检查，
而不是那个门槛。

## 复查者可能想要质疑的决定

1. `AggregationConfig.field_priority` 以 `(field, source_ids)` 对组成的 tuple 存储
   （不借助 `object.__setattr__` 实现不可变）；`AggregationConfig.create(...)` 是接受 mapping 的便利构造函数。
2. `merge_source_results` **按位置**把结果与策略中启用来源的顺序对应（标注了其他 id 的结果会 fail-closed，而不是被重新路由）。
3. fail-closed 替换结果以及意外的 adapter 异常都是 `INVALID_RESPONSE`，因此在另一个来源成功时属于*运行性失败* → `PARTIAL`。
4. `runtime = 0` 算作一个值（不做特殊处理）；字符串为空白时视为“空”。
5. `validate_base_url` 很严格：非 ASCII（IDN 必须使用 punycode）、userinfo、query 和 fragment 都会被拒绝。
6. 聚合结果保留每个 adapter 自己的 `elapsed_ms`；只有 engine 产生的结果（deadline、异常）才带有 engine 测量的时间。
   P2-R-07（transport 层的 `elapsed_ms = 0`）没有被触碰。
7. 一个 source id 只有在**被禁用**时才可以*已配置*但未注册；启用的未知 id 会让 engine 构造失败，并列出所有未知 id。

## 剩余的待办（未改变 / 未触碰）

- **P2-R-05** 探测工具的 `anti_bot_hint` 仅凭 `cf-ray` 就会触发 — LOW。
- **P2-R-06** 探测工具的 `requested_url` 是最终 URL — LOW。
- **P2-R-07** transport 层失败的 `elapsed_ms = 0` — LOW（C1 自己产生的 deadline / 异常结果确实带有真实的耗时）。
- **P2-R-10** JavDB 标题被重复反转义 — LOW，保持原样。
- **P2-R-12** — 重新延后（见上文），到韧性 / 重试子阶段。
- **F3、F5** — DEFERRED（定义位于更早的复查报告中；必须在 Phase 5 集成之前关闭）；C1 没有触碰它们的机制。
  **F4** 保持 CLOSED。

## 尚未开始（Phase 3 C2+ 及之后）

重试 / 退避 — **NOT STARTED**。熔断器 — **NOT STARTED**。批处理引擎 /
500-item 批次 / 失败子集重试 — **NOT STARTED**。NFO writer、图片下载、文件重命名 / 移动、目录整理 — **NOT STARTED**。
Amane adapter、GUI — **NOT STARTED**。
50-ID 覆盖门槛 — **NOT RUN**。

**READY FOR PHASE 3 C1 INDEPENDENT REVIEW** — 不是 “C1 PASS”，不是 “Phase 3 PASS”，也不是
“50-ID gate passed”。
