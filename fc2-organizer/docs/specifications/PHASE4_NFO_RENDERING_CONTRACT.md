# FC2 Organizer -- Phase 4 / P4-C4 纯 NFO 渲染合同（Pure NFO Rendering Contract）

状态：**在 P4-C4 冻结**（候选；独立复查待进行）。
Package：`fc2_organizer.nfo`（`__init__.py`、`errors.py`、`renderer.py`）。

**范围（对本 package 冻结）：** `PublicationRecord -> str`。一个纯粹、确定的渲染器，产出 Kodi 兼容的
Movie NFO XML *文本值*。它不写文件，不选择路径，不创建目录，不决定是否覆盖，不下载 / 校验 / 选择图片，
也不做 HTTP、数据库、CLI、UI 或 Amane 相关的工作。见第 17 节。

## 1. 架构与依赖方向

```text
fc2_organizer.nfo
    '-- fc2_organizer.publication   (public package only: PublicationRecord)
```

* 标准库：只使用 `__future__`、`re`、`datetime`（`datetime.date.fromisoformat`，一个纯解析器；
  不读取任何时钟）。`errors.py` 只使用标准库（`__future__`）。
* 不直接依赖 `fc2_metadata_core`（任何模块）、`fc2_organizer.planning`、
  `fc2_organizer.discovery`、`amane`、任何 XML/HTML 库，或任何文件系统 / 网络 / 时钟 / 随机数 / 环境 /
  locale 模块。记录的 metadata 只通过属性读取；`PublicationRecord` 本身已经是 P4-C3 冻结的内容边界。
* 没有反向依赖：`fc2_metadata_core`、`planning`、`discovery` 或 `publication` 中都没有任何内容
  import `fc2_organizer.nfo`。
* `fc2_organizer/__init__.py` **不会**急切地 import `nfo`（该文件没有改动）。
  裸 `import fc2_organizer` 既不加载 `nfo`、`publication`，也不加载任何 `fc2_metadata_core` 模块。请显式 import：
  `from fc2_organizer.nfo import render_movie_nfo`。
* `fc2_organizer` 的顶层子 package 现在恰好是
  `{"discovery", "planning", "publication", "nfo"}`。P4-C1 / P4-C2 / P4-C3 的作用域守卫断言各更新了一行
  （只是 package 集合的增长）；它们的禁止 import 守卫、运行时阻断器、允许列表和反向依赖守卫都没有改动。

由 `tests/contract/test_nfo_architecture.py` 强制执行。

## 2. 公开 API

```python
from fc2_organizer.nfo import render_movie_nfo

render_movie_nfo(record: PublicationRecord) -> str
```

同时导出：第 12 节中的错误类。除此之外没有其他内容（没有 `write`、`save`、
`download`、`execute`、`materialize`）。

* 输入：一个**严格的** `PublicationRecord`（`type(record) is PublicationRecord`）。
  子类会被拒绝（`NfoInputError`）：子类可以覆盖 `number` / `metadata`，从而在渲染器内部运行代码。
* 输出：一个严格的 `str`，并且总是满足
  `xml_text.encode("utf-8", errors="strict")`。绝不是 `bytes`、`ElementTree`、DOM 或文件对象。

## 3. XML 外壳（冻结）

```text
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<movie>
  ...
</movie>
```

| 属性 | 取值 |
|---|---|
| XML 版本 | `1.0` |
| 声明的编码 | `UTF-8` |
| standalone | `yes` |
| 换行符 | 只用 `\n`（绝不用 `\r\n`；值中的 `\r` 输出为 `&#13;`） |
| 结尾换行 | 恰好一个 |
| 缩进 | 每级 2 个空格（`movie` 的子元素缩进 2，`actor` 的子元素缩进 4） |
| 根元素 | `movie`，没有属性 |
| 空元素 | 永不输出（缺失的可选字段直接省略，而不是输出 `<x/>`） |
| DOCTYPE / 实体声明 / 注释 / CDATA / 处理指令 | 永不输出（只有声明行） |

文本由一个小型的集中式序列化器构建，而不是 XML 库，因此库在格式上的任何选择（属性顺序、引号风格、
空标签风格）都不会导致输出变化。
确切的文本由 golden 测试冻结。

## 4. 元素顺序（冻结）

```text
1. title        mandatory, exactly one
2. uniqueid     mandatory, exactly one
3. plot         optional
4. runtime      optional
5. premiered    optional
6. studio       optional
7. actor        0..N
8. tag          0..N
```

顺序从不依赖 dict / hash / set 的顺序。

## 5. 字段映射（冻结）

| NFO 元素 | 来源 | 规则 |
|---|---|---|
| `<title>` | `record.metadata.title` | 严格 `str`，非空白；内容逐字保留（不 strip、不做大小写折叠、不做 Unicode 规范化、不做 HTML 或 XML 反转义）；只做 XML 转义 |
| `<uniqueid type="fc2" default="true">` | `record.number` | 严格 `str`，非空白；绝不从文件名重新推导，绝不重新解析；`type` / `default` 是常量 |
| `<plot>` | `metadata.plot` | `None` 或 `plot.strip() == ""` -> 省略；否则逐字保留（不做摘要、截断或换行改写） |
| `<runtime>` | `metadata.runtime` | `None` -> 省略；严格 `int`（不能是 `bool`，也不能是 `int` 子类），`>= 0`，整分钟，十进制数字；`0` 会被渲染 |
| `<premiered>` | `metadata.release` | `None` / 仅空白 -> 省略；否则见第 8 节 |
| `<studio>` | `metadata.studio` | `None` / 仅空白 -> 省略；否则逐字保留 |
| `<actor><name/><order/></actor>` | `metadata.actors` | 第 9 节 |
| `<tag>` | `metadata.tags` | 第 9 节 |

恰好输出一个 `<uniqueid>`。

## 6. 明确不做映射的字段（冻结）

以下内容永远不会被读取，也永远不会以任何形式（元素、属性、注释、自定义标签）渲染：

```text
metadata.publisher          (not a studio fallback; no <publisher>)
metadata.poster_urls / thumb_urls / fanart_urls / extrafanart   (no <thumb>/<fanart>, no URL)
metadata.source_urls
metadata.external_ids       (no extra <uniqueid>; source-ID -> Kodi-ID mapping is not frozen here)
metadata.field_sources
record.aggregate_status
```

图片：NFO 不携带任何图片引用。OrganizePlan 已经指定了
`poster.jpg` / `fanart.jpg` / `thumb.jpg` / `extrafanart/` 这些目标；图片的选择和内容是后续 package 的事情。

## 7. 状态隔离（冻结）

`SUCCESS` 和 `PARTIAL` 记录都会被渲染。`aggregate_status` 永远不会被读取，因此计划和 metadata 相同、
只有状态不同的两个记录，渲染出的文本**逐字节相同**。没有 `<status>`，没有注释，任何运行诊断信息
（`SourceResult`、trace、attempt、`error_detail` / `error_kind`、重试或 P2-R-07 计时、HTTP URL / 响应体 /
header / cookie）都无法进入 XML。

## 8. 发行日期校验（冻结）

非空白的 `release` 必须是一个严格的 `str`，完整匹配 ASCII
`[0-9]{4}-[0-9]{2}-[0-9]{2}`，**并且**能被 `datetime.date.fromisoformat` 接受
（一个真实的外推格里历日期，年份 1..9999）。它被原样渲染。

| 输入 | 结果 |
|---|---|
| `2026-09-19`、`2026-02-28`、`2024-02-29`、`2000-02-29` | 渲染 |
| `None`、`""`、`"   "` | 省略 |
| `2026-02-30`、`2023-02-29`、`2026-13-01`、`2026-00-10`、`0000-01-01` | `NfoReleaseDateError` |
| `26-01-01`、`20260101`、`2026/09/19`、`2026-9-19`、`2026-09-19T00:00:00`、`" 2026-09-19"`、`"2026-09-19\n"`、全角 / 阿拉伯-印度数字、ISO 周 / 序数日期形式 | `NfoReleaseDateError` |

不猜测，不修复，也不会悄悄省略一个非空白的非法值。不读取任何时钟。

## 9. 演员 / 标签的顺序（冻结）

* `actors` / `tags` 必须是严格的 `tuple`；每个条目都必须是严格的 `str`
  （`None` 或任何其他类型都是错误，绝不会被跳过）。
* `item.strip() == ""` 的条目会被省略；其余条目按 tuple 顺序保留。不去重，不排序。
* 演员的 `<order>` 按**实际输出的**演员依次为 `0, 1, 2, ...`（省略之后保持连续）：
  `("Alice", "   ", "Bob")` -> Alice `0`、Bob `1`。
* 每个演员恰好由 `<actor>`、`<name>`、`<order>`、`</actor>` 四行组成。
* 标签使用 `<tag>`，绝不使用 `<genre>`。

## 10. XML 字符安全与转义（冻结）

任何被渲染的值中允许出现的字符（XML 1.0 `Char`）：

```text
U+0009  U+000A  U+000D  U+0020..U+D7FF  U+E000..U+FFFD  U+10000..U+10FFFF
```

在一个将被渲染的值中出现其他任何字符（例如 `U+0000`、`U+0001`、`U+0008`、`U+000B`、`U+000C`、`U+001F`、
代理项 `U+D800..U+DFFF`、`U+FFFE`、`U+FFFF`），都会抛出 `NfoXmlCharacterError`，消息中只写出字段名和码点
（`metadata.plot contains U+0000 ...`）。字符永远不会被删除、替换或忽略。检查的字段：title、number、plot、
studio、每个被输出的 actor / tag（release 由其 ASCII 形态规则覆盖）。

空白优先规则：按 `str.strip()` 判断为仅含空白的可选值 / 集合条目，会在字符检查*之前*被省略（它不会被渲染）。
`str.strip()` 把 `U+000B`、`U+000C` 和 `U+001C..U+001F` 视为空白，因此只由这类字符组成的可选值会被省略，
而不是被拒绝；但出现在被渲染值内部的任何这类字符都会被拒绝。

转义：每个文本节点都经过唯一的 `_escape_text` helper：
`&` -> `&amp;`、`<` -> `&lt;`、`>` -> `&gt;`、`\r` -> `&#13;`。双引号和单引号保持原样（在文本节点中是合法的）。
从不调用 `html.escape` / `html.unescape`：metadata 中的 `A &amp; B` 是字面字符串
`A &amp; B`，它会被渲染为 `A &amp;amp; B`（P2-R-10 中 HTML 与 XML 的分离）。
不使用 CDATA。

## 11. 注入安全与恶意文本边界（冻结）

* metadata 只会变成文本节点。标签名、属性名和属性值、声明、DOCTYPE 以及实体声明都是模块常量；
  不存在任何未转义数据的原始插值。
* 诸如 `</title><evil>true</evil><title>`、
  `<!DOCTYPE movie [...]>`、`&xxe;`、`]]>`、`<![CDATA[...]]>`、`<!-- -->`、
  `" type="evil"` 这样的载荷都会被渲染为文本：解析后的文档中没有多出任何元素、属性、DTD 或实体。
* 每一个可能进入 XML 的文本值（title、number、plot、release、studio、每个 actor / tag 条目）都必须满足
  `type(value) is str`。`str` 子类会在其任何方法被调用**之前**抛出 `NfoMetadataError`：
  它的 `__str__`、`__repr__`、`__format__`、`__eq__`、`__hash__`、`strip`、
  `replace`、`encode`、`translate`、... 等钩子都不会被调用。`runtime` 必须满足
  `type(value) is int`。
* 防御性的形态校验（通过 `object.__new__` / `object.__setattr__` 伪造的记录）：渲染器读取的每个属性都在
  守卫中读取；任何失败都会变成 `NfoMetadataError`（绝不是裸的
  `AttributeError` / `TypeError` / `UnicodeEncodeError` / `ValueError`），并以 `from None` 抛出。
  `NormalizedMetadata` 和 `PublicationRecord` 没有改动。

## 12. 错误分类（`errors.py`）

| 错误 | 基类 | 抛出时机 |
|---|---|---|
| `NfoError` | `Exception` | 以下所有错误的基类 |
| `NfoInputError` | `NfoError`、`TypeError` | 输入不是严格的 `PublicationRecord` |
| `NfoMetadataError` | `NfoError`、`ValueError` | 某个被使用的字段形态无法渲染（类型错误 / 子类类型、用 list 代替 tuple、runtime 为负数或非 `int`、属性无法读取、title / number 为空白） |
| `NfoReleaseDateError` | `NfoMetadataError` | 非空白的 release 不是严格、真实的 `YYYY-MM-DD` 日期 |
| `NfoXmlCharacterError` | `NfoMetadataError` | 某个被渲染的值包含 non-XML-1.0 字符 |

消息只包含字段名（`metadata.actors[2]`）、Python 类型名和码点。它们从不包含 title、plot、actor、tag、
studio 或 release 的值。任何 NFO 错误都不做异常链接（`__cause__ is None`）。

## 13. 纯粹性与确定性（冻结）

`render_movie_nfo` 不修改记录，不保留任何全局可变状态，也不读取环境变量、locale、时区、cwd、文件系统、网络、
时钟、`random`、`uuid` 或 `os.urandom`。同一个记录渲染 100 次得到 100 个相同的字符串；相等的记录得到相等的字符串。
这是通过在上述所有内容都被拦截的情况下进行渲染来证明的（成功、最小记录、非法日期、非法字符、非法输入、伪造形态，
以及整个合成门槛）；每一类拦截都有一个正向对照来证明它确实会触发。`date.fromisoformat` 刻意没有被拦截。

## 14. 合成门槛

`tests/unit/nfo/test_nfo_synthetic_gate.py`：400 个多样化的记录（SUCCESS / PARTIAL、
5-8 位数字的番号、Unicode / XML 特殊字符 / 注入型标题、有 plot / 无 plot、
runtime 为 None / 0 / N、有 release / 无、有 studio / 无、0..4 个演员（含空白项和重复项）、
0..3 个标签、每三个记录中带一个出处 / 图片 / 来源 URL 哨兵值），外加 20 个由真实的
`prepare_publication` 基于携带 trace 和 `error_detail` 的真实合并聚合结果生成的记录。每个记录都在所有拦截下
渲染两次（结果相同），严格按 UTF-8 编码，然后解析（`root == movie`、
`title == metadata.title`、`uniqueid == record.number`，每个可选元素、演员顺序和标签列表都与记录的 metadata
对照检查），并检查其中不存在任何哨兵值和状态字面量。每个门槛记录改用相反的状态重新渲染后，结果逐字节相同。

## 15. 架构测试

`tests/contract/test_nfo_architecture.py`：允许 import 的 AST 扫描（publication +
`__future__` / `re` / `datetime`）；没有直接 import core / sources / aggregation / batch /
resource-control / http / discovery / planning / Amane / XML / I/O；没有 I/O、时钟、`escape` / `unescape` /
CDATA 类调用；`errors.py` 只使用标准库；没有反向依赖；`fc2_organizer/__init__.py` 中没有急切 import；
裸 `import fc2_organizer` 不加载任何 nfo / publication / core 模块；在 `amane` 被阻断的情况下，显式 import 后能端到端
渲染；公开 API 严格一致；package 集合严格一致。

## 16. 测试矩阵

| # | 要求 | 测试（`tests/unit/nfo/`） |
|---|---|---|
| 1 | 最小记录 | `test_nfo_render.py::test_01_*` |
| 2 | 完整 metadata 精确一致 + 可解析 | `test_02_*`（golden + 解析器） |
| 3-7 | Unicode、`&`、`<>`、引号、非 BMP 字符 | `test_03_*` .. `test_07_*` |
| 8-10 | 结尾换行、没有 CR、根元素 / 外壳 | `test_08_*` .. `test_10_*` |
| 11-24 | 可选字段 | `test_11_12_*` .. `test_24_*`、`test_optional_elements_keep_frozen_relative_order_*` |
| 25-33 | 演员 / 标签 | `test_25_26_*` .. `test_33_*` |
| 34-38 | 不做映射的字段 | `test_34_*` .. `test_38_*`、`test_publisher_is_never_used_as_studio_fallback`、`test_no_sentinel_of_any_kind_leaks` |
| 39-42 | 状态隔离 | `test_39_40_*`、`test_41_*`（模型 + 真实的 `prepare_publication`）、`test_42_*` |
| 43-55 | XML 字符边界 | `test_nfo_xml_safety.py::test_43_48_*`、`test_49_55_*`、`test_illegal_character_propagates_from_every_rendered_text_field`（title / plot / studio / actor / tag） |
| 恶意输入 | `str` 子类，钩子调用次数为零 | `test_hostile_str_subclass_is_rejected_without_calling_any_hook`（title / plot / release / studio / actors / tags）、`..._as_canonical_number_...`、正向对照 `test_hostile_hooks_really_are_armed` |
| 56-65 | 伪造形态 | `test_56_65_*`、`test_huge_runtime_*`、`test_metadata_missing_attribute_*`、`test_record_with_unset_slots_*`、`test_forged_*` |
| 66-70 | 注入 | `test_66_70_*`（10 个载荷 x 5 个字段）、`test_66_repro_b_*`、`test_67_70_*`、`test_69_*` |
| 输入 / 分类 | | `test_non_publication_record_input_*`、`test_publication_record_subclass_*`、`test_error_taxonomy_*`、`test_each_failure_category_*`、`test_error_messages_never_echo_*` |
| 纯粹性 | 没有 I/O / 时钟 / 随机数 / 环境 | `test_nfo_no_side_effects.py`（正向对照 + 6 个场景） |
| 确定性 | | `test_same_record_rendered_100_times_*`、`test_rendering_does_not_modify_the_record` |
| 门槛 | | `test_nfo_synthetic_gate.py` |
| 架构 | | `tests/contract/test_nfo_architecture.py` |

## 17. P4-C4 范围之外

文件路径选择、文件创建 / 写入、目录创建、覆盖决策、OrganizePlan 执行、图片下载 / 校验 / 选择、
`<thumb>` / `<fanart>` / 图片、额外的 `<uniqueid>` 映射、`<genre>`、
`<publisher>`、HTTP、数据库、CLI、UI、JSON / 诊断信息导出、Amane。不存在任何占位文件
（`writer.py`、`filesystem.py`、`downloader.py`、`executor.py`）。

## 18. 已知局限

* `fc2db_net` 把 schema.org 的 `uploadDate` 未经形态校验就传入 `release`；如果线上页面提供的是 ISO datetime
  （`2026-09-19T...`），渲染器会对这部影片以 `NfoReleaseDateError` fail closed（这是设计使然：这里不做修复）。
  在 adapter 中规范化 release 是一项独立的、尚未订立合同的改动。
* 对规范番号只检查它是严格的 `str`、非空白且 XML 安全；它的规范 FC2 形态由上游（planning / P4-C3）保证，
  这里不会重新校验或重新解析。

## 19. 延续的债务

未改变、仍然延续：P4-C3-R-01（LOW）、P4-C3-R-02（LOW）；P4-C2-R1-02
（LOW）、OrganizePlan 操作图加固、覆盖执行器语义（冻结为 `NEVER`）、扩展的 Windows 保留名；
P4-C1-R-02..R-05；P2-R-05、P2-R-06、P2-R-07（没有用到：渲染器不读取任何 `elapsed_ms`）；C3-N1..N4；
C4-N1；C4-R1-N1..N3；F3；F5；C5-R1-L1。

已经关闭、不再延续：P4-C2 metadata 身份缺口、C2-L2、P2-R-10。
