# FC2 Metadata Core — Phase 3 / C1 聚合合同（Aggregation Contract）

状态：**在 Phase 3 C1 冻结**；**在 Phase 3 C2 修订**（见下方修订说明）。

> **修订说明（Phase 3 C2）。** 重试 / 退避、细粒度失败分类以及 attempt 诊断信息在
> `PHASE3_RESILIENCE_CONTRACT.md` 中规定。C2 只修改了本文中标注 "(C2)" 的位置：
> 第 1 节（`retry_policy`、严格的直接构造函数、engine 的 client 形态）、第 3 节（deadline 是包含
> 重试在内的*总*预算；adapter 自行抛出的 `CancelledError`；致命 `BaseException`；隔离 / fail-closed
> 结果的 `error_kind`）、第 4 节（`source_execution_traces`；不变量列表收窄为实际强制执行的内容）
> 以及第 7 节（P2-R-12 已关闭，而非延后）。
> 其余内容均未改变，相应测试仍然通过。
范围：多来源执行 + 确定性的字段级聚合（`fc2_metadata_core.aggregation`）。以下内容明确**不在**
本合同范围内，也未实现：熔断器（circuit breaker）、批处理任务、NFO、图片、文件系统整理、
Amane adapter（属于后续 Phase 3 子阶段 / Phases 4-5）。
（C2 增加了来源本地的重试 / 退避；见 `PHASE3_RESILIENCE_CONTRACT.md`。）

下列每条规则都由 `tests/unit/aggregation/`（以及 `tests/unit/sources/test_registry_create_boundary.py`）
下的离线自动化测试强制执行；每条规则旁边都注明了对应的测试文件。

```text
canonical FC2 number
   |  MultiSourceEngine.aggregate(number)        engine.py
   v
ordered SourceConfig (order = default priority)  config.py, policy.py
   |  execute_sources(...)                       execution.py   bounded fan-out, deadlines, isolation
   v
SourceResult x (one per enabled source, in configuration order)
   |  merge_source_results(...)                  merge.py       PURE, no network
   v
AggregationResult                                models.py
```

## 1. 配置（`config.py`、`policy.py`）— `test_agg_config.py`

`SourceConfig(source_id, enabled=True, base_url=None, deadline_seconds=20.0)` 与
`AggregationConfig(sources, max_concurrency=3, field_priority=())` 都是成员不可变的 frozen
dataclass；`AggregationConfig.create(...)` 接受任意可迭代对象和普通 mapping。**所有内容都在构造时、
在任何网络请求之前完成校验**，不合法时以 `AggregationConfigError` 拒绝：

| 规则 | 拒绝的情况 |
|---|---|
| 来源集合 | 空集合；**没有任何启用的来源**；重复的 `source_id`；非 `SourceConfig` 成员；用 list 代替 tuple |
| `source_id` | 空 / 首尾带空白 / 非 `str` |
| `deadline_seconds` | 不是数字、`bool`、`<= 0`、`nan`、`inf`、`> 600` |
| `max_concurrency` | 不是 `int`、`bool`、超出 `1..64` |
| `enabled` | 不是真正的 `bool` |
| `retry_policy`（C2） | 不是 `RetryPolicy`（在 `SourceConfig` 上，`None` 表示“使用聚合级默认值”） |
| `base_url` | 见 §1.1 |
| `field_priority` | 未知 / 不可覆盖的字段（包括 `number`、`field_sources`）；未配置的来源；同一覆盖项中出现重复 id；空的覆盖项；裸 `str` |

**直接构造函数（C2，LOW-3）。** `AggregationConfig(...)` 与 `create(...)` 同样严格：
`field_priority` 必须是 `tuple[tuple[str, tuple[str, ...]], ...]`；list、dict、嵌套 list、非 `str` /
不可哈希的字段名或格式错误的条目都会得到 `AggregationConfigError`（绝不会是 `TypeError`），
而且调用方之后修改自己仍持有的任何对象，都不能改变该配置。

**Client 形态（C2，LOW-4）。** `MultiSourceEngine(config, registry, client)` 要求
`client.get` 是一个 `async` 可调用对象（`is_async_get`），判断过程不会发出任何请求；同步的
`get` 在构造时即得到 `AggregationConfigError`。

**是否已注册？** `source_id` 是否存在于 registry 中，是在构建 `MultiSourceEngine` 时检查的
（所有未知 id 会在同一个 `AggregationConfigError` 中一并列出）。*已禁用*的来源永远不会被查找。

### 1.1 `base_url`（在 Phase 3 配置路径上关闭 Phase 2 复查 finding P2-R-08）

`validate_base_url` 只接受带有效 host（DNS 名称或 IP 字面量）的绝对 `http://` / `https://` URL。
以下情况一律拒绝，且不产生任何网络活动：
非 `str`；空值；缺少 scheme（`fc2db.net`）；缺少 host（`http://`、`https://`）；任何其他 scheme
（`ftp:`、`file:`、`javascript:`）；内嵌 userinfo（`user:pw@host`）；带 query 或 fragment
（adapter 会自行追加路径）；端口错误或越界；host 非法（`bad_host`、`-x-`、空 label、过长 label）；
以及**任何**控制字符（CR、LF、NUL、TAB ...）、空格、反斜杠、`<>"`{}|^`、非 ASCII
字符（请使用 punycode），或长度超过 2048。adapter 本身没有改动：格式错误的 `base_url`
已无法再通过配置路径到达 adapter。

### 1.2 优先级

**`sources` 的顺序就是每个字段的默认优先级**（排在前面的优先级最高）；只有启用的来源参与。
`field_priority` 可以覆盖单个字段（`title studio publisher release runtime plot actors tags poster_urls
thumb_urls fanart_urls extrafanart source_urls external_ids`）。覆盖项只列出*部分*来源；其余启用的
来源按默认顺序排在后面，因此每个字段始终有一个完整且确定的顺序。覆盖项可以指定一个已配置但被
禁用的来源（该来源会被跳过）。

provider 名称只出现在一个位置：`defaults.py`
（`DEFAULT_SOURCE_ORDER = ("fc2db_net", "javdb", "av123")`），并且以数据形式出现。
`merge`/`policy`/`execution`/`engine`/`models`/`config` 从不提及任何 provider 名称，
也从不 import 具体的 adapter（`test_agg_guards.py`）。

## 2. Registry 创建边界（关闭 P2-R-11）— `test_registry_create_boundary.py`

`SourceRegistry.create(source_id, **kwargs)` 返回的对象**必须是 `SourceAdapter`，且其 `source_id`
等于请求的 id**；否则抛出 `SourceRegistryError` 的某个子类 — 绝不会是裸 `TypeError` /
`AttributeError`，也绝不会返回来历不明的对象：

| 情况 | 错误 |
|---|---|
| 未知 / 不可哈希的 id | `UnknownSourceIdError`（同时也是 `KeyError`） |
| factory 抛出 `Exception` | `SourceFactoryError`（链接原始异常；`KeyboardInterrupt` / `SystemExit` *不会*被吞掉） |
| factory 返回非 `SourceAdapter`（`42`、`None`、一个类，...） | `InvalidSourceAdapterError` |
| `register("alias_x", Fc2dbNetAdapter)`（adapter 自身的 id 与之不同） | `SourceIdMismatchError` |
| factory 不可调用 | 在 `register` 时抛出 `SourceRegistryError` |

类以外的 factory 仍然受支持。

## 3. 来源执行（`execution.py`）— `test_agg_execution.py`、`test_agg_engine.py`

`execute_sources_traced(number, targets, client, *, max_concurrency=3)`（C2）对每个目标调用
`adapter.fetch(number, shared_client)` -- 按 `PHASE3_RESILIENCE_CONTRACT.md` 的规定进行重试 --
并为每个目标恰好返回一个 `SourceExecutionTrace`（包含每一次 attempt + 最终的 `SourceResult`）；
`execute_sources` 只返回最终的各个 `SourceResult`。

- **共享 client。** 每个 adapter 收到的都是*同一个* `SourceHttpClient` 对象；engine 自己不创建任何
  transport。
- **顺序。** 结果按**配置顺序**排列，绝不按完成顺序排列
  （测试：用 sleep 强制让完成顺序反转 → 输出完全相同）。
- **有界并发。** 使用 `asyncio.Semaphore(max_concurrency)`；这个上限是真实生效的（活跃峰值
  `<= limit`），并且执行不是串行的（来源足够多时峰值 `== limit`）。默认值为 3，可配置范围 `1..64`。
- **墙钟 deadline（在调度路径上关闭 P2-R-09）。** 每个来源的整个执行过程都在**一个**
  `asyncio.timeout(deadline_seconds)` 之下运行，*这个限制施加在本边界上*（adapter 未改动；不依赖 httpx
  的分阶段超时）。**（C2）** 这个预算涵盖第 1 次 attempt + 每一次退避等待 + 每一次重试；它绝不会乘以
  `max_attempts`。deadline 从该来源开始执行时起算，而不是从它等待并发名额时起算。到期时**只有该来源**
  变为 `NETWORK_ERROR` / `SOURCE_DEADLINE`（C2），`error_detail` 为 `"<id>: source execution deadline exceeded
  (<n>s wall clock, <m> ms elapsed)"`，并带有真实的 `elapsed_ms`（不是 0）。*由 adapter 自身*抛出的内置
  `TimeoutError` 不会被误认为是 deadline 到期（由 `scope.expired()` 判定）。局限：吞掉
  `CancelledError` 的 adapter 无法被中断；现已采用的 adapter 都不会这样做。
- **隔离。** adapter 泄漏出的任何普通 `Exception` 都会变成该来源的
  `INVALID_RESPONSE` / `ADAPTER_EXCEPTION`（C2），`error_detail` = `"<id>: unexpected adapter exception
  <ExceptionType>"` — *绝不包含异常消息*（其中可能带有 URL 或 secret）。adapter 给出的每一个非成功
  `SourceStatus` 都只是数据；任何来源的结果都不会让另一个来源停止。
- **取消（C2，LOW-2；完整表格见 `PHASE3_RESILIENCE_CONTRACT.md` 第 4 节）。** 调用方取消聚合任务时
  会传播 `CancelledError`（同级任务被取消，不会留下任何仍在运行的任务）。adapter *自行*抛出的
  `CancelledError`（并没有人请求取消）会被隔离为该来源的 `INVALID_RESPONSE` / `ADAPTER_EXCEPTION`，
  其他来源继续执行。`KeyboardInterrupt`、`SystemExit`、`GeneratorExit` 以及任何自定义的非
  `Exception` 的 `BaseException` 都是致命的：重新抛出的是**原始对象**（绝不是
  `BaseExceptionGroup`，也绝不会变成来源结果）。已知局限：吞掉取消的 adapter 无法被中断。
- **Fail closed。** adapter 返回的任何内容都要经过
  `validate_source_result(slot_id, number, candidate)`：非 `SourceResult`、标注了不同 `source_id` 的
  结果，或者 `metadata.number != requested number` 的 `SUCCESS`，都会变成该槽位的
  `INVALID_RESPONSE` / `RESULT_CONTRACT_MISMATCH`（C2），并且**不贡献任何内容**。结果按它被执行时
  所在的槽位标注，绝不按它自称的来源标注。
- 非规范化的番号属于调用方 bug：在调用任何来源之前即抛出 `InvalidCanonicalNumberInputError`。

## 4. `AggregationResult`（`models.py`）— `test_agg_guards.py`、`test_agg_merge.py`

在构造时冻结并校验。**（C2）** `__post_init__` 强制执行什么、不强制执行什么，其精确列表写在
`aggregation/models.py` 的模块 docstring 中；C1 中“无法构造出不一致的结果”这一说法收窄为该列表。
简而言之：id 唯一；`successful_source_ids` = 所有 `SUCCESS` 的 id；`FAILED` 没有 metadata，也没有贡献来源；
`SUCCESS`/`PARTIAL` 带有针对所请求番号、满足最低成功标准的 metadata，并且
`contributing_source_ids == successful_source_ids` 严格成立；`disabled_source_ids` 互不重复，且与结果集合
不相交；每个 `FieldConflict` 都指向一个可以产生冲突的字段，并且只引用贡献来源；
`source_execution_traces` 要么为空，要么与 `source_results` 一一对齐。**不**校验的内容（校验它们意味着
重新执行一次 merge）：metadata 的值、`field_sources` 和冲突列表是否正是 merge 规则应当产生的结果。

```text
number                    requested canonical number
status                    AggregateStatus.SUCCESS | PARTIAL | FAILED
metadata                  merged NormalizedMetadata | None
source_results            every per-source SourceResult, enabled sources, configuration order
contributing_source_ids   sources whose data participated (SUCCESS + valid), default order
conflicts                 resolved disagreements (FieldConflict), deterministic order
disabled_source_ids       configured-but-disabled sources (never executed)
elapsed_ms                wall time of the whole aggregate lookup
source_execution_traces   (C2) one SourceExecutionTrace per enabled source: every attempt + final result
```

### 4.1 状态语义（冻结）

*运行性失败*（operational failure）= 某个来源最终为 `BLOCKED`、`RATE_LIMITED`、
`NETWORK_ERROR`、`PARSE_ERROR` 或 `INVALID_RESPONSE`（包括上文的 fail-closed 替换结果以及 deadline
到期）。`NOT_FOUND` **不是**运行性失败：它表示该来源已作答，只是没有这部影片。

| 状态 | 定义 | `metadata` |
|---|---|---|
| `SUCCESS` | 合并后的 metadata 满足最低成功标准（规范番号 + 非空标题），**并且**没有任何启用的来源发生运行性失败 | 存在 |
| `PARTIAL` | 合并后的 metadata 满足最低成功标准，但至少有一个启用的来源发生了运行性失败 | 存在 |
| `FAILED` | 没有任何来源产生可用数据（因此不满足最低成功标准） | `None` |

推论（全部有测试）：`SUCCESS` + `NOT_FOUND` + `NOT_FOUND` → `SUCCESS`；
`SUCCESS` + `NETWORK_ERROR` → `PARTIAL`；`SUCCESS` + `BLOCKED` + `NOT_FOUND` →
`PARTIAL`；全部 `NOT_FOUND` → `FAILED`；`NOT_FOUND` + `NETWORK_ERROR` + `BLOCKED` →
`FAILED`。`FAILED` 仍然携带**全部** `SourceResult`。
`__post_init__` 强制执行：`FAILED` ⇒ 没有 metadata，也没有贡献来源；
`SUCCESS`/`PARTIAL` ⇒ 满足最低成功标准的 metadata，其 `number` 就是请求的番号，
≥ 1 个贡献来源，并且（`SUCCESS`：没有运行性失败 / `PARTIAL`：至少有一个运行性失败）。
只有来源的**最终**结果才计数（C2）：先失败一次、重试后成功的来源算作成功；它第一次的失败仍然
在其 trace 中可见。
只有 `SUCCESS` 状态的结果才会贡献数据：附着在 `PARSE_ERROR` / `INVALID_RESPONSE` 上的部分
metadata 永远不会被使用。

## 5. 合并（`merge.py`）— 纯函数，`test_agg_merge.py`

`merge_source_results(number, source_results, policy, ...)` 是一个**纯函数**：
不访问网络、不读时钟、不使用 asyncio，也不 import adapter。`source_results` 与
`policy.source_order` **按位置**对应；长度不同即为 `AggregationInputError`。
它从不修改输入，而是构建一个**新的**不可变 `NormalizedMetadata`
（不使用 `object.__setattr__`，不做原地修改 — 由测试守护）。

### 5.1 非空

`None` 以及空白 / 仅含空白字符的字符串都视为空。`int` 类型的 `runtime` 为 `0` 时**是**一个有效值
（行为确定且有文档说明；不做特殊处理）。

### 5.2 标量 — `title studio publisher release runtime plot`

**按该字段优先级顺序排列的第一个非空值**胜出。其他来源给出的相等值（严格 `==` 且类型相同）
属于*佐证*；不同的值记录为 `FieldConflict(field, selected_source_id, selected_value,
alternatives=((source_id, value), ...))`，alternatives 按优先级排序。
结果与 `set`/`dict` 的顺序以及异步完成顺序无关。

### 5.3 `number`

永远不从来源中选取：始终使用请求的规范番号。

### 5.4 集合字段 — `actors tags poster_urls thumb_urls fanart_urls extrafanart source_urls`

按该字段的优先级顺序做**保序去重并集**（先是来源 A 的条目，然后是 B 新增的条目，...）。
去重**只按字符串严格相等** — 不做大小写折叠、空白规范化、翻译或模糊匹配，因此人名和标签
永远不会被错误合并。空白条目会被跳过。结果为 `tuple`。

### 5.5 `external_ids`

逐个 key 合并，**第一个（优先级最高的）值胜出** — 绝不是“最后写入者胜出”。
同一个 key 出现不同值时记录为 `FieldConflict(field=
"external_ids", key=<key>, ...)`；同一个 key 出现相同值不算冲突。空白的 key / value 会被跳过。

### 5.6 `field_sources`（来源出处）

为聚合结果从零重新计算；**adapter 自己的 `field_sources` 被完全忽略**（adapter 无法伪造出处；
测试伪造了 `("other_source",)`，它不会泄漏出来）。依据 = 槽位配置的 `source_id` + *实际*的值。
key 按固定顺序出现（`number title studio publisher release runtime plot actors tags poster_urls
thumb_urls fanart_urls extrafanart source_urls external_ids`）；只有已填充的字段才有条目；
来源 tuple 按**优先级顺序**排列：

| 字段 | `field_sources[field]` |
|---|---|
| `number` | 所有贡献来源，按**默认来源顺序** |
| 标量 | 所有值等于被选中值的贡献来源（按优先级顺序）；被选中的来源排第一 |
| 集合 | 所有提供了 ≥ 1 个非空条目的来源（按优先级顺序） |
| `external_ids` | 所有提供了 ≥ 1 个非空键值对的来源（按优先级顺序） |

## 6. 确定性

输出只取决于 `(number, results in slot order, policy)`。与 `set` / hash 顺序、异步完成顺序、
墙钟时间以及运行次数都无关（通过重复运行、反转完成顺序和随机的优先级排列来测试）。

## 7. C1 刻意不做的事情

- ~~不做重试、退避或熔断。~~ **（C2）** 现在已经有来源本地的重试和确定性退避
  （`PHASE3_RESILIENCE_CONTRACT.md`）。**P2-R-12 已在该合同中 CLOSED**：提供了结构化的
  `SourceErrorKind` 分类（HTTP 5xx -> `INVALID_RESPONSE` /
  `HTTP_SERVER_ERROR`，transport 异常 -> `TIMEOUT` / `CONNECTION_ERROR` /
  `DECODE_ERROR` / `REDIRECT_ERROR` / `RESPONSE_TOO_LARGE`），并且重试决策只读取该分类。
  **熔断仍未实现**（它属于批处理调度的范畴）。
- 没有批处理引擎，也没有运行 50-ID 验收（在冻结的 50-ID 集合上 ≥ 90 % `number + title` 的门槛
  仍需在后续的实时覆盖子阶段中运行；本文不对此作任何声明）。
- 没有 NFO writer、图片下载、文件移动、Amane adapter、GUI。
