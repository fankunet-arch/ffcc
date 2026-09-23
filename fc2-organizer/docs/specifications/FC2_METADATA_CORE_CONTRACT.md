# FC2 Metadata Core — Phase 1 合同（Contract）

**修订说明（Phase 1 R1）：** §2.1/§2.2/§2.3 在 R1 中新增 / 更新，用于关闭独立复查
finding F1（运行时类型合同漏洞）和 F2（可通过可变 metadata 破坏 `SourceResult` 生命周期不变量）。
复查轮次记录见 `docs/review/PHASE1_R1_HANDOFF.md`。

**修订说明（Phase 1 R2）：** R1 的增量关闭复查发现，R1-01 的修复只是部分修复：集合字段接受任意
`Iterable`，而不仅是有序的 `Sequence` — 这会悄悄丢弃 `dict` 的值（只保留 key），或以依赖 hash seed
的顺序接受 `set`/`frozenset`。下文 §2.1 已更新为 R2 冻结的合同（`Sequence[str]`，而不是 `Iterable[str]`），
并且现在也记录了：一个行为异常的*已接受* Sequence 所抛出的异常会被包装，而不是直接泄漏出去。
见 `docs/review/PHASE1_R2_HANDOFF.md`。
**修订说明（Phase 3 Entry C0）：** §4 现在把规范数字语义冻结为严格的 ASCII `[0-9]` 并要求整串匹配（C0-01），
§2.1b 把 `runtime` 的单位冻结为整分钟（C0-04）。见 `docs/review/PHASE3_ENTRY_C0_HANDOFF.md`。

本文其余内容均与最初的 Phase 1 提交相同。

**范围：** 本文冻结 `fc2_metadata_core`（`fc2-organizer/src/fc2_metadata_core/`）的 Phase 1 公开合同。
它是代码及其测试的配套文档，不能替代其中任何一方 — 这里陈述的每条规则都由
`fc2-organizer/tests/` 下的自动化测试强制执行。

Phase 1 不访问任何真实网站，不实现任何 scraper，不与 Amane 通信，除了正常的 Python 模块 import 之外
也不接触文件系统。本文以及它所描述的代码 100% 离线。

## 1. 独立于 Amane

`fc2_metadata_core` 绝不能直接或间接地 import `amane` 或任何 `amane.*` 模块，并且必须能够在完全没有安装
Amane 的环境中被 import 和完整使用。

由 `tests/contract/test_core_independent_of_amane.py` 强制执行：
- 对每个源文件做静态 AST 扫描，拒绝任何 `import amane` /
  `from amane import ...` 语句；
- 动态测试安装一个 `sys.meta_path` finder，任何 import `amane`/`amane.*` 的尝试都会让它抛出异常，
  然后在该 finder 之下 import 每个 core 模块并调用公开 API（`normalize_fc2_number`、`NormalizedMetadata`、
  `SourceResult`）。

这关闭了 Phase 0 复查者背景说明 1/3：Core 的模型形态（`external_ids`、`source_urls`，复数）刻意**没有**
收窄为与 Amane 当前单数形式的 `MediaMetadata.external_id` /
`MediaMetadata.source_url` 一致。这种收窄是 Phase 5（薄 adapter）的工作，而不是 Phase 1 的工作。

## 2. `NormalizedMetadata`

`fc2_metadata_core.models.NormalizedMetadata` — 一个**深度不可变的值对象**（frozen dataclass；在 R1 中修订，
见 §2.3）。每个字段默认为 `None`（标量）或空的不可变集合，因此不带参数的
`NormalizedMetadata()` 是合法的。

字段：`number`、`title`、`studio`、`publisher`、`release`、`runtime`、
`actors`、`tags`、`plot`、`poster_urls`、`thumb_urls`、`fanart_urls`、
`extrafanart`、`source_urls`、`external_ids`、`field_sources`。

### 最低成功标准（冻结）

```text
minimum success = a valid canonical FC2 number (see §4) + a non-empty title
```

其他所有字段都可以部分缺失 / 不存在，不影响这一判断。实现为
`NormalizedMetadata.meets_minimum_success()`，以
`has_valid_canonical_number()` 和 `has_non_empty_title()` 为基础。由
`tests/unit/core/test_metadata.py::TestMinimumSuccess` 覆盖（番号 + 标题通过；
番号 + 空 / 仅空白 / 缺失的标题失败；标题 + 缺失 / 格式错误的番号失败）。这三个方法都是**全谓词**：
对于任何已成功构造的实例，它们总是返回 `bool`，从不抛出异常
（`TestScalarTypeValidation::test_meets_minimum_success_never_raises_for_any_constructed_instance`）。

### 2.1 运行时类型合同（R1-01 / 复查 finding F1）

R1 关闭了这样一个漏洞：构造时任何字段都接受任何值（例如 `title=123`、`actors=[123]`），非法值直到后来
才以 `meets_minimum_success()` 或类似方法抛出的裸 `AttributeError`/`TypeError` 形式暴露出来
— 一个未记录的异常穿过了本应是领域合同边界的地方。

`NormalizedMetadata` 是一个领域对象：每个字段的运行时类型都在 `__post_init__` 中校验，任何违规都会立即以
`MetadataContractError` 拒绝，绝不会拖到之后。

| 字段组 | 要求的运行时形态 | 被拒绝的示例 |
|---|---|---|
| `number`、`title`、`studio`、`publisher`、`release`、`plot` | `str \| None` | `title=123` |
| `runtime` | `int \| None`，排除 `bool`，`>= 0`；单位 = 整分钟（§2.1b） | `runtime=True`、`runtime=-1`、`runtime="1"` |
| `actors`、`tags`、`poster_urls`、`thumb_urls`、`fanart_urls`、`extrafanart`、`source_urls` | 有序的 `collections.abc.Sequence[str]`（见 §2.1a — **不只是** `Iterable[str]`） | `actors=[123]`、`actors="John"`（拒绝裸 str）、`tags=123`（不是 Sequence） |
| `external_ids` | `str` key 到 `str` value 的 mapping | `{123: "x"}`、`{"x": 123}`、用 `list` 代替 mapping |
| `field_sources` | `str` key 到有序 `Sequence[str]` value 的 mapping（与上面相同的 §2.1a 规则，逐个 value 应用） | `{123: [...]}`、`{"title": [123]}`、`{"title": 123}`、`{"title": {"a", "b"}}` |

由 `tests/unit/core/test_metadata.py::TestScalarTypeValidation` 和
`::TestCollectionTypeValidation` 强制执行，其中包括复查者的原始复现
（`test_original_f1_reproduction_title_int_is_rejected_at_construction`）。

`SourceResult` 在自己的边界上采用同样的做法：`metadata` 必须是 `None` 或真正的 `NormalizedMetadata` 实例，
否则构造以 `SourceResultContractError` 被拒绝 — 例如传入 `metadata=123` 的调用方，根本走不到
`metadata.meets_minimum_success()` 抛出 `AttributeError` 那一步
（`tests/unit/core/test_source_result.py::TestMetadataTypeGuard`）。

### 2.1b `runtime` 的单位：整分钟（在 Phase 3 Entry C0-04 冻结）

```text
runtime: int | None
unit     = whole minutes
range    = >= 0
```

当来源给出时钟格式的时长时，秒数会被**截断**（不是四舍五入）：`"55:23"` -> `55`、`"55:59"` -> `55`、
`"1:02:03"` -> `62`。不是 ASCII 时钟时长（`mm:ss` / `h:mm:ss`）的值会变成 `None`
（缺失的 runtime 属于部分字段，绝不算错误）。参考实现为
`fc2_metadata_core.sources.adapters._common.duration_to_minutes`。

理由：最终目标包括 Kodi Movie NFO，其 `<runtime>` 元素只以分钟为单位。Phase 1 只冻结了*类型*
（`int >= 0`，§2.1），**没有**确定单位；单位是在 Phase 3 Entry C0 冻结的。Phase 2 中发布的每个 adapter
本来就输出整分钟，因此没有任何 adapter 的行为发生变化。
因此，Phase 3 可以在不做单位换算的情况下跨来源合并 `runtime` 值。

由 `tests/unit/sources/adapters/test_adapter_common.py` 和
`tests/unit/sources/adapters/test_runtime_minutes.py` 强制执行。

### 2.1a 集合输入合同是 `Sequence[str]`，而不是 `Iterable[str]`（R2-01 / 复查 finding F1）

上面 R1 的修复校验了集合的*元素*，但通过裸的 `isinstance(value, Iterable)` 检查进行转换，
这过于宽松：`dict` 是 `Iterable`（迭代它只会悄悄产出 key，丢弃 value 且不报错），而
`set`/`frozenset` 是 `Iterable` 但没有确定的顺序，把它冻结为 `tuple` 会固化一个调用方从未要求过的、
依赖 hash seed 的任意元素顺序。

**R2 把上述七个序列字段中每一个的、以及每个 `field_sources` value 的输入合同，明确冻结为
`collections.abc.Sequence[str]`：**

| 输入类型 | 结果 | 原因 |
|---|---|---|
| `list[str]` / `tuple[str, ...]` / 任何真正的 `Sequence` | **接受**，快照为 `tuple[str, ...]` | 有序，与调用方写入的完全一致 |
| `str` / `bytes` | **拒绝**（`MetadataContractError`） | 否则会被逐字符迭代 |
| `Mapping`（`dict`、...） | **拒绝**（`MetadataContractError`） | 迭代只产出 key，悄悄丢弃 value |
| `set` / `frozenset` | **拒绝**（`MetadataContractError`） | 无序；Core 不会替调用方发明一个顺序（例如通过排序）— 字段顺序可能携带来源 / 展示上的含义 |
| 生成器 / 迭代器 / 任何不是 `Sequence` 的其他 `Iterable` | **拒绝**（`MetadataContractError`），*而且在消费它之前就拒绝* | 一次性的；先消费再拒绝，可能导致部分消费，或因一个本来就不是合法输入的东西而在中途抛出异常 |

这关闭了 R1 增量复查中的复现：
`NormalizedMetadata(actors={"Alice": 1, "Bob": 2})`（一个 `dict`）和
`NormalizedMetadata(actors={"Alice", "Bob"})`（一个 `set`）现在都会抛出
`MetadataContractError`，而不是悄悄产出 `("Alice", "Bob")`（只有 key）或一个依赖 hash 顺序的 tuple。

**R2-02 / 复查 finding F2 — 行为异常的*已接受* Sequence 不得原样泄漏其异常。** 即使收窄为
`Sequence`，自定义的 `Sequence` 实现仍然可能在迭代中途抛出异常（例如 `__getitem__` 有缺陷）。
现在读取这样的值时，会捕获*在迭代已接受的 Sequence 时*抛出的任何异常，并以
`MetadataContractError` 重新抛出，同时链接原始异常（`raise MetadataContractError(...) from exc`），
既为调试保留根因，又不会泄漏裸的 `RuntimeError`/`ValueError` 等。我们自己的元素类型
`MetadataContractError`（例如 `actors=[123]`）会原样重新抛出 — 绝不会被重复包装。

由 `tests/unit/core/test_metadata.py::TestSequenceContractRejectsNonSequenceIterables`
（对每个序列字段以及 `field_sources` 的 value 拒绝 dict/set/frozenset/生成器，生成器函数体从不执行，
list/tuple 仍然被接受且顺序稳定）和 `::TestBrokenAcceptedSequenceIsWrapped`
（一个在迭代中途抛出异常的 `collections.abc.Sequence` 测试替身被包装，且链接了 `__cause__`；我们自己的
校验错误不会被重复包装）强制执行。

### 2.2 深度不可变（R1-02 / 复查 finding F2）

R1 关闭了一个生命周期漏洞：`SourceResult` 是 frozen 的，但它引用的 `NormalizedMetadata` 是可变的，
因此 `SUCCESS` 结果的 `metadata.meets_minimum_success()` 保证（在 `SourceResult.__post_init__` 中建立），
可以在构造*之后*通过修改仍被引用的 `NormalizedMetadata` 而失效 — 这发生在任何合同边界之外。
同样的问题也存在于 `PARSE_ERROR`/`INVALID_RESPONSE` 结果的部分 metadata 上：它可以事后被修改成
满足最低成功标准的内容。

**修复：** `NormalizedMetadata` 现在是深度不可变的，而不仅仅是浅层 frozen：

- dataclass 本身为 `frozen=True`；对标量属性（重新）赋值会抛出 `dataclasses.FrozenInstanceError`。
- 每个序列字段（`actors`、`tags`、`poster_urls`、`thumb_urls`、
  `fanart_urls`、`extrafanart`、`source_urls`）都在 `__post_init__` 中快照为 `tuple`
  — 存储的值上根本没有 `list.append`/`list[i] = ...` 可用。
- `external_ids` 和 `field_sources` 快照为包在新建私有 `dict` 外面的
  `types.MappingProxyType` — 条目赋值 / 删除会抛出 `TypeError`。
- `field_sources` 的 value 本身也快照为 `tuple`，因此
  `field_sources["title"].append(...)` 会像序列字段一样失败。
- 调用方持有的输入容器在构造时被复制（逐个元素复制，而不仅仅是重新包装），因此在构造
  `NormalizedMetadata` *之后*修改原始的 `list`/`dict`，永远不会影响已经构建好的实例（没有别名共享）。

由于 `SourceResult` 自身的 `metadata` 字段不能被重新赋值（frozen），而它引用的 `NormalizedMetadata`
在任何深度上都不能被修改，`SourceResult` 的不变量现在在整个对象图的生命周期内都成立，
而不仅仅在 `__post_init__` 运行的那一刻成立。

由 `tests/unit/core/test_metadata.py::TestImmutability` 和
`::TestCallerOwnedInputAliasSafety` 强制执行，并由
`tests/unit/core/test_source_result.py::TestSuccessLifetimeInvariant`、
`::TestPartialFailureLifetimeInvariant` 和
`::TestCallerOwnedAliasSafetyThroughSourceResult` 经由 `SourceResult` 做端到端验证。

### 2.3 对 Phase 3（聚合）的影响 — 方向在 R1 中改变

Phase 1 HANDOFF 最初让 `NormalizedMetadata` 保持非 frozen，给出的理由是“Phase 3 可能需要增量的
原地合并”。**自 R1 起撤回这一理由。** 从此以后，`NormalizedMetadata` 是冻结的架构：

```text
NormalizedMetadata = immutable value object
```

Phase 3 的字段级聚合必须是**函数式 / 写时复制**的：读取一个或多个不可变的 `NormalizedMetadata` 输入，
计算合并结果，然后产出一个*新的* `NormalizedMetadata` 实例。它绝不能尝试原地修改一个已经构造 / 发布的
`NormalizedMetadata` — 通过公开 API 做不到这一点（见 §2.2），也不得在本模块之外通过访问私有属性或
`object.__setattr__` 来绕过。

## 3. `SourceResult` / `SourceStatus` / `SourceErrorKind`

`fc2_metadata_core.models.SourceResult` — 一个 frozen dataclass，承载某个来源解析某个 FC2 番号这一次
尝试的结果：`source_id`、`status`、`metadata`、`elapsed_ms`、`error_kind`、`error_detail`。

`SourceStatus`（7 个成员，依据规格）：`SUCCESS`、`NOT_FOUND`、`BLOCKED`、
`RATE_LIMITED`、`NETWORK_ERROR`、`PARSE_ERROR`、`INVALID_RESPONSE`。

`SourceErrorKind` 最初与六个非成功状态一一对应。
**修订（Phase 3 C2）：** 它扩充了更细粒度的 kind（`TIMEOUT`、
`CONNECTION_ERROR`、`DECODE_ERROR`、`REDIRECT_ERROR`、`SOURCE_DEADLINE`、
`HTTP_SERVER_ERROR`、`RESPONSE_TOO_LARGE`、`ADAPTER_EXCEPTION`、
`RESULT_CONTRACT_MISMATCH`），正如本段原先所预期的那样：状态词汇没有改动，六个通用 kind 被保留
（因此之前的每一个结果仍然能通过校验），允许的状态 / kind 组合冻结在 `ALLOWED_ERROR_KINDS` 中（见
`PHASE3_RESILIENCE_CONTRACT.md` section 1）。它在成功结果上仍然没有意义（并且被禁止）。

### 不变量（全部在 `__post_init__` 中强制执行，全部有测试）

| 规则 | 由谁强制执行 |
|---|---|
| `source_id` 必须非空 / 不能只含空白 | `TestSourceIdInvariant` |
| `elapsed_ms` 不能为负数（int/float，不能是 bool） | `TestElapsedMsInvariant` |
| `metadata` 必须是 `None` 或真正的 `NormalizedMetadata` 实例（R1-01/F1） | `TestMetadataTypeGuard` |
| `status == SUCCESS` 要求 `metadata` 存在，**并且** `metadata.meets_minimum_success()` | `TestSuccessInvariants` |
| `status == SUCCESS` 禁止出现 `error_kind`/`error_detail` | `TestSuccessInvariants` |
| 每个非成功状态都需要一个**该状态所允许的** `error_kind`（C2：`ALLOWED_ERROR_KINDS`；与状态同名的通用 kind 总是被允许） | `TestErrorKindAndDetailConsistency` |
| 每个非成功状态都需要非空的 `error_detail` | `TestErrorKindAndDetailConsistency` |
| `NOT_FOUND` / `BLOCKED` / `RATE_LIMITED` / `NETWORK_ERROR` **不得**携带 `metadata` | `TestNoMetadataFailureStatuses` |
| `PARSE_ERROR` / `INVALID_RESPONSE` **可以**携带部分 `metadata`，但不能是已经满足最低成功标准的 metadata（那意味着状态本应是 `SUCCESS`） | `TestPartialMetadataAllowedStatuses` |

这就是对“不要写裸 `except Exception: return None`”的具体回答：
来源实现（Phase 2+）在结构上被强制从七个状态中选择一个，并且对每一次失败都提供一个相匹配的 `error_kind`
和一个人类可读的 `error_detail` — 不存在没有状态的失败路径。

## 4. FC2 番号规范化（NORM-01）

`fc2_metadata_core.normalize.normalize_fc2_number(text: str) -> FC2NumberResult`。

### NORM-01 — 本 Phase 关闭的硬性不变量（Phase 0 复查者 F-02）

Phase 0 发现，Amane 的 `parse_file_info(path=...)` 总是带有一个强制性的回退，因此对真实文件从不返回
`number=None` — 一个无法识别的文件仍可能以 `TOTALLY-998` /
`ContentType.WESTERN` 这类结果出现，而不是一个明确的“未识别”信号。

**FC2 Metadata Core 依据自身的语法独立做出这一判断，绝不委托给 Amane 的回退。** 每次调用
`normalize_fc2_number` 都恰好返回以下两种结果之一：

- `FC2RecognitionStatus.RECOGNIZED`，并带有格式正确的 `canonical` 字符串；或
- `FC2RecognitionStatus.NOT_FC2`，并且 `canonical=None`。

不存在第三种、捏造出来的结果。`FC2NumberResult.__post_init__` 本身就断言
`canonical is not None` 当且仅当 `status is RECOGNIZED`，因此这个不变量在构造层面就无法被违反，
而不仅仅是依靠约定。

### 规范语法

```text
FC2 [-_]* (PPV [-_]*)? DIGITS{5,8}
```

- 不区分大小写地匹配，可以出现在更长的、带噪声的字符串中的任何位置。
- `FC2` 与可选的 `PPV` 字面量之间可以用零个或多个 `-`/`_` 分隔符连接，也可以没有分隔符。
  覆盖 `FC2-PPV-1234567`、`FC2PPV-1234567`、
  `FC2PPV1234567`、`FC2-1234567`、`FC2_1234567`。
- 数字**只能是 ASCII `[0-9]`**（在 Phase 3 Entry C0-01 冻结）。Python 的
  `\d` 和 `$` 比这个语法更宽（`\d` 匹配所有 Unicode 十进制数字；`$` 还会在结尾换行符之前匹配），
  因此不使用它们：全角（`１２３`）和阿拉伯-印度（`٤٨٢`）数字不是 FC2 数字，紧挨着这类数字的数字串
  也不是干净的记号。
- 数字串的长度必须是 5 到 8 位（`fc2_number.py` 中的 `MIN_FC2_DIGITS` /
  `MAX_FC2_DIGITS`）。当前真实的 FC2 PPV 番号是 6-7 位数字；5-8 位留出了余量，同时仍能拒绝不合理的数字块
  （粘在一起的日期、分辨率、hash、时间戳）。这是 Phase 1 的设计决定，而不是上游事实 — 后续阶段可以
  凭证据重新审视。
- **单词边界规则：** 紧挨在 `FC2` 之前的字符（如果有）以及紧挨在数字串之后的字符（如果有）都不能是
  `[A-Za-z0-9]`。正是这一点，让任意噪声（`[广告]`、`xxx@`、括号、空白、其他前缀、扩展名、`-CD1` 后缀）
  可以包围该记号，同时拒绝 `SUPERFC2-1234567`（与前面的字母粘连）或 `FC2-1234567EXTRA`（与后面的字母粘连）。
- 规范输出总是 `FC2-<digits>`（大写，单个短横线）。

`is_valid_fc2_number(value)` 检查一个字符串是否*已经*是这种严格的规范形态，采用 `FC2-[0-9]{5,8}` 的
**整串**匹配（不接受结尾换行，也不接受其他前导 / 结尾字符）；它不会从带噪声的文本中提取。
`NormalizedMetadata.has_valid_canonical_number()` 以及每个来源 adapter 的
`require_canonical_number` 使用的都是它，因此不能通过它的值永远不会进入请求 URL。
`"FC2-1234567\n"`、`"FC2-１２３４５６７"`、`"FC2-٤٨٢٤٦٠٥"`、
`"FC2-1234567XYZ"` 和 `"XFC2-1234567"` 全部被拒绝
（`tests/unit/core/test_fc2_number_canonical_boundary.py`、
`tests/unit/sources/adapters/test_adapter_canonical_boundary.py`）。
`normalize_fc2_number` 使用同样的 ASCII 数字语义，因此两者在“什么是数字”这一点上永远不会有分歧。

### 正向回归集（`tests/unit/core/test_normalize_fc2_number.py`）

覆盖规格 §10 中的所有形式，包括 Phase 0 复查者说明 F-03 明确要求用真实自动化测试（而不仅仅是文档）
关闭的两种形式：`[广告]FC2PPV-1234567` 和 `xxx@FC2PPV-1234567`，以及扩展名 / CD 后缀噪声、
混合分隔符、重复短横线和前导 / 结尾空白。

### 反向回归集

直接攻击语法本身，而不是照搬规格中的要点列表：纯数字文件名、其他厂牌的编号、日期、分辨率、
没有 FC2 记号的 CD 标记、不带数字的裸 `FC2`、`FC2` 后跟过短（<5）或长得离谱（粘连的数字块，>8，
或越过了边界）的数字串，以及 — 针对朴素解析器的关键用例 — 与前面字母粘连的 `FC2`
（`SUPERFC2-...`、`PERFC2PPV...`）和与后面字母粘连的数字串（`FC2-1234567EXTRA`）。这些用例专门证明
解析器并不只是“看到 `FC2` + 任意数字 = 匹配”。

## 5. 明确不属于 Phase 1 的范围

没有任何针对特定站点的逻辑（没有 FC2CMADB/FC2DB/JavTen 选择器，没有 FC2 官方接口处理，
没有 Cloudflare 绕过，没有 cookie / HTTP session），没有 scraper，没有多来源聚合，没有批处理引擎，
没有 Amane 插件 adapter，没有 NFO 写入，没有文件移动，没有 Amane DB 访问。
这些属于 Phase 2 及之后。
