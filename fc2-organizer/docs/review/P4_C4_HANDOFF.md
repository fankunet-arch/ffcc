# Phase 4 / P4-C4 Handoff -- 纯 NFO 渲染（Pure NFO Rendering）

```text
Phase        = 4
Package      = P4-C4
Role         = Developer
Branch       = claude/phase4-c4-nfo-rendering
```

## 1. 坐标

```text
Frozen Base                  = 8439da97f4e23e475a20619b4adb6bfd4ae30b6a
P4-C4 Code Review Candidate  = 526177b7c4279057633a2fb893fab79804c97835
P4-C4 Docs Head              = <this commit; see `git log -1 -- fc2-organizer/docs/review/P4_C4_HANDOFF.md`>
Remote Head                  = <== Docs Head after push of this commit>

Code Review Range: 8439da97f4e23e475a20619b4adb6bfd4ae30b6a..526177b7c4279057633a2fb893fab79804c97835
Docs Review Range: 526177b7c4279057633a2fb893fab79804c97835..<Docs Head>
```

在任何改动之前已验证：`git fetch --all --tags`；
`origin/claude/phase4-c3-publication-boundary` == `8439da97f4e23e475a20619b4adb6bfd4ae30b6a`；
工作区干净（只有未跟踪的测试框架目录 `.claude/`）；从那个确切的提交在一个隔离的 worktree 中创建了新分支
`claude/phase4-c4-nfo-rendering`。没有 rebase / amend / squash / force push。

Code Review Candidate 包含代码、测试以及冻结的合同（`PHASE4_NFO_RENDERING_CONTRACT.md`）。Docs Head 提交只包含本文件。

## 2. 类型

**NEW PACKAGE**（`fc2_organizer.nfo`）+ 三处一行的 package 集合作用域守卫更新。`fc2_organizer/nfo/` 之外没有任何生产文件被触碰。

## 3. 变更文件（Code Review Candidate `526177b`，15 个文件，+2204 / -3）

新增（12）：
```text
fc2-organizer/docs/specifications/PHASE4_NFO_RENDERING_CONTRACT.md
fc2-organizer/src/fc2_organizer/nfo/__init__.py
fc2-organizer/src/fc2_organizer/nfo/errors.py
fc2-organizer/src/fc2_organizer/nfo/renderer.py
fc2-organizer/tests/contract/test_nfo_architecture.py
fc2-organizer/tests/unit/nfo/__init__.py
fc2-organizer/tests/unit/nfo/_builders.py
fc2-organizer/tests/unit/nfo/_guards.py
fc2-organizer/tests/unit/nfo/test_nfo_no_side_effects.py
fc2-organizer/tests/unit/nfo/test_nfo_render.py
fc2-organizer/tests/unit/nfo/test_nfo_synthetic_gate.py
fc2-organizer/tests/unit/nfo/test_nfo_xml_safety.py
```

修改（3，只是 package 集合的增长）：
```text
fc2-organizer/tests/contract/test_discovery_architecture.py    +1 -1
fc2-organizer/tests/contract/test_planning_architecture.py     +1 -1
fc2-organizer/tests/contract/test_publication_architecture.py  +1 -1
```

没有触碰：`fc2_organizer/__init__.py`、discovery / planning / publication 的生产代码、`NormalizedMetadata`、
`PublicationRecord`、整个 `fc2_metadata_core`、P4-C3 的测试名称 / 拦截覆盖、Amane。

## 4. 公开 API

```python
from fc2_organizer.nfo import render_movie_nfo
render_movie_nfo(record: PublicationRecord) -> str
```

输入必须是严格的 `PublicationRecord`（子类 -> `NfoInputError`）。输出是一个严格的 `str`，总能以 UTF-8 严格编码。
同时导出：`NfoError`、`NfoInputError`、`NfoMetadataError`、`NfoReleaseDateError`、`NfoXmlCharacterError`。

## 5. 冻结的 XML 形态

```xml
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<movie>
  <title>A &amp; B</title>
  <uniqueid type="fc2" default="true">FC2-1234567</uniqueid>
  <plot>Example &lt;plot&gt;</plot>
  <runtime>61</runtime>
  <premiered>2026-09-19</premiered>
  <studio>Example Studio</studio>
  <actor>
    <name>Alice</name>
    <order>0</order>
  </actor>
  <actor>
    <name>Bob</name>
    <order>1</order>
  </actor>
  <tag>Tag A</tag>
  <tag>Tag B</tag>
</movie>
```

只用 `\n`，恰好一个结尾换行，2 空格缩进，顺序为
title、uniqueid、plot、runtime、premiered、studio、actor*、tag*。由 golden 测试（`GOLDEN_FULL`、`GOLDEN_MINIMAL`）以及
解析器往返测试冻结。

## 6. 字段映射

| 元素 | 来源 | 规则 |
|---|---|---|
| title | `metadata.title` | 严格 `str`，非空白，逐字保留，只做 XML 转义 |
| uniqueid `type="fc2" default="true"` | `record.number` | 严格 `str`，非空白；属性为常量；不重新解析 |
| plot | `metadata.plot` | None / 空白 -> 省略 |
| runtime | `metadata.runtime` | None -> 省略；严格 `int` >= 0，整分钟；`0` 会被渲染 |
| premiered | `metadata.release` | None / 空白 -> 省略；否则必须是严格、真实的 `YYYY-MM-DD` |
| studio | `metadata.studio` | None / 空白 -> 省略 |
| actor(name, order) | `metadata.actors` | tuple 顺序，省略空白项，order 从 0 开始连续，不去重 |
| tag | `metadata.tags` | tuple 顺序，省略空白项，不去重 / 不排序，绝不使用 `<genre>` |

## 7. 明确不做映射的字段

从不读取：`publisher`（不作为 studio 的回退，没有 `<publisher>`）、`poster_urls`、
`thumb_urls`、`fanart_urls`、`extrafanart`（没有 `<thumb>` / `<fanart>` / URL）、
`source_urls`、`external_ids`（恰好一个 `<uniqueid>`）、`field_sources`、
`aggregate_status`。没有注释，没有自定义标签，除了两个 `uniqueid` 常量之外没有其他属性。哨兵值测试（`SECRET-PUBLISHER`、
`SECRET-SOURCE-URL`、`SECRET-FIELD-SOURCE`、external ID 和图片 URL 哨兵值、`error_detail` 中的 cookie / bearer 文本）
确认它们都不会进入 XML；把它们全部加上后，输出仍与 golden 文本逐字节相同。

## 8. XML 字符安全

允许：U+0009、U+000A、U+000D、U+0020..U+D7FF、U+E000..U+FFFD、
U+10000..U+10FFFF。被渲染的值中出现其他任何字符 -> `NfoXmlCharacterError`，消息中只有字段名 + 码点
（例如 `metadata.tags[1] contains U+000B ...`）；绝不删除 / 替换 / 忽略。已针对 title、plot、studio、actor、tag
（以及伪造的 number）用 U+0000、U+0001、U+0008、U+000B、U+000C、U+001F、
U+D800、U+DFFF、U+FFFE、U+FFFF 测试；允许范围边界上的字符能完整往返。CR 以 `&#13;` 输出，因此能在解析后保留，
并且永远不会引入原始的 `\r`。空白优先规则：按 `str.strip()` 判断为仅含空白的可选值（其中包括
U+000B / U+000C / U+001C..U+001F）会在字符检查之前被省略（合同第 10 节）。

## 9. 注入安全

一个集中的 `_escape_text`（`&`、`<`、`>`、`\r`）通过 `_text_element` 处理每一个文本节点；标签 / 属性 / 声明都是常量；
没有 CDATA；没有 `html.escape` / `html.unescape`。10 个载荷（`</title><evil>...`、带外部实体的 DOCTYPE、`&xxe;`、
`A & B < C > D`、`]]>`、CDATA、XML 声明、注释、破坏属性的引号）x 5 个字段：解析后的文档只包含冻结的元素名称，属性只出现在
`uniqueid` 上，没有 `<evil>`，没有 DTD（`minidom ... doctype is None`），并且载荷作为文本被逐字还原。
`A &amp; B` 渲染为 `A &amp;amp; B`（不做 HTML 的双重处理）。

## 10. 恶意文本边界

对 title、number、plot、release、studio 以及每个 actor / tag 条目检查 `type(value) is str`；对 runtime 检查
`type(value) is int`；对 actors / tags 检查 `type(...) is tuple`。检查发生在任何方法调用之前，因此一个覆盖了 29 个钩子
（`__str__`、`__repr__`、`__format__`、`__eq__`、`__hash__`、`strip`、`replace`、`encode`、`translate`、...）的 `str` 子类，
对于 title / plot / release / studio / actors / tags 以及规范番号中的每一个，都会得到 `NfoMetadataError`，钩子调用次数为 **0**
（正向对照证明这些钩子确实是生效的）。伪造的形态（`runtime=True/-1/
"60"/60.0/IntSubclass`、list 类型的 actors / tags、非 str / `None` 条目、frozenset、非 str 的 plot / release / studio、
空白 / 非 str 的 title、未设置的 slot、不是计划的计划、会抛出异常的 metadata property、`10**5000` 的 runtime）全部抛出类型化的
`NfoMetadataError`，以 `from None` 抛出，绝不是裸异常。

## 11. 发行日期校验

ASCII `[0-9]{4}-[0-9]{2}-[0-9]{2}` 整串匹配 + `date.fromisoformat`。接受：
`2026-09-19`、`2026-02-28`、`2024-02-29`、`2000-02-29`、`0001-01-01`、`9999-12-31`。
拒绝（`NfoReleaseDateError`）：`2026-02-30`、`2023-02-29`、`2026-13-01`、
`2026-00-10`、`2026-04-31`、`0000-01-01`、`26-01-01`、`20260101`、`2026/09/19`、
`2026-9-19`、datetime 形式、前导 / 结尾空格或换行、全角和阿拉伯-印度数字、ISO 周 / 序数日期、`+2026-09-19`、`Sep 19, 2026`。
不读取任何时钟。

## 12. 演员 / 标签的顺序

`("Alice", "   ", "", "Bob", "\t")` -> Alice 0，Bob 1。`("Alice", "Bob", "Alice")`
保留全部三个（0, 1, 2）。标签保持 tuple 顺序，保留重复项，并且永远不会变成 `<genre>`。

## 13. 状态隔离

`aggregate_status` 永远不会被读取。相同的计划 + metadata，SUCCESS 与 PARTIAL -> 逐字节相同（模型构建的记录、基于携带 trace +
`error_detail` 的真实聚合结果由真实 `prepare_publication` 产生的记录，以及全部 400 个门槛记录在切换状态后的重新渲染）。
任何输出中都不出现 `success` / `partial` / `status` / 注释文本。

## 14. 确定性

同一个记录渲染 x100 次 -> 只有一个不同的字符串；相等的记录 -> 相等的字符串；渲染之后记录保持不变（与孪生对象 `==`，且 `repr` 相同）。

## 15. 不访问文件系统 / 网络 / 时钟 / 随机数

`tests/unit/nfo/_guards.py::traps()`（作用域限定的 `MonkeyPatch.context`）拦截：builtins / `io.open`、`os` 的文件系统调用
（包括 `getcwd` / `chdir`）、`os.path`（`exists`、`realpath`、`abspath`、...）、`pathlib.Path`（包括 `resolve`、`absolute`、
`cwd`）、`shutil`、`socket`、`urllib.request.urlopen`、`httpx.Client/AsyncClient.send/request`、`requests`（如果存在）、`time.*`、
`datetime.date.today`、`datetime.datetime.now/today/utcnow`（以及渲染器自己的 `date` 绑定）、`random.*`、`uuid.uuid1/uuid4`、
`os.urandom`、`secrets.token_bytes`、`os.environ`、`os.getenv`、`locale.*`。36 个参数化的正向对照（14 个文件系统、
4 个网络、13 个时钟 / 随机数、5 个环境）+ 1 个真实的 `httpx.Client` 对照证明每个拦截都会触发。已证明 `date.fromisoformat`
在这些拦截下仍然可用。在所有拦截下渲染：完整、最小、非法日期、非法字符、非法输入、伪造形态，以及整个合成门槛；输出与未拦截时的输出相等。

## 16. 架构边界

`fc2_organizer.nfo -> fc2_organizer.publication`（公开 package）+ `__future__`、
`re`、`datetime`。`tests/contract/test_nfo_architecture.py`（17 个测试）：只允许特定的 import；不直接 import
`fc2_metadata_core` / sources / aggregation / batch / resource_control / http / discovery / planning / Amane / XML / HTML / I/O；
没有 I/O、时钟、环境、`escape` / `unescape` / CDATA 调用；`errors.py` 只使用标准库；core / planning / discovery / publication
没有反向依赖；`fc2_organizer/__init__.py` 中没有急切 import；裸 `import fc2_organizer` 不加载任何 nfo / publication /
`fc2_metadata_core` 模块；在 `amane` 被阻断的情况下，显式 import 后能渲染；公开 API 严格一致；package 集合严格一致。

架构中“严格集合”的修改：P4-C1 / P4-C2 / P4-C3 的作用域守卫从
`{"discovery", "planning", "publication"}` 改为
`{"discovery", "planning", "publication", "nfo"}` -- 各一行，没有其他改动
（`git diff 8439da9..526177b -- fc2-organizer/tests/contract/test_{discovery,planning,publication}_architecture.py`）。

## 17. 合成门槛

`test_nfo_synthetic_gate.py`：400 个模型构建的记录 + 20 个真实的 `prepare_publication` 记录（420）。变化维度：
SUCCESS / PARTIAL、5-8 位数字的番号、12 个标题族（Unicode、XML 特殊字符、注入、CR / 制表符 / 换行、DOCTYPE + 实体）、
6 种 plot、runtime 为 None / 0 / N、6 种 release、5 种 studio、6 组演员（0..4 个，含空白项和重复项）、5 组标签，
每三个记录中有一个带出处 / 图片 / URL 字段的哨兵值。每个记录都在所有拦截下渲染两次（结果相同），严格 UTF-8 编码，然后解析
（`root == movie`、title、uniqueid、每一个可选元素、演员顺序、标签，与记录的 metadata 对照），没有任何哨兵值 / 状态泄漏；
切换状态后重新渲染的结果逐字节相同。PASS。

## 18. 测试

针对性测试：
```text
python -m pytest tests/unit/nfo tests/contract/test_nfo_architecture.py \
  tests/contract/test_discovery_architecture.py tests/contract/test_planning_architecture.py \
  tests/contract/test_publication_architecture.py tests/unit/publication \
  -q -p no:cacheprovider --basetemp=<job-owned tmp>
433 passed, 0 failed, 0 skipped
  unit/nfo: render 88, xml_safety 142, no_side_effects 46, synthetic_gate 3 (= 279)
  contract: nfo 17, discovery 12, planning 13, publication 19
  unit/publication: 93
```

全量测试（在 `fc2-organizer/` 下运行）：
```text
python -m pytest -q -p no:cacheprovider --basetemp=<job-owned tmp>
3220 passed, 14 skipped, 0 failed
```

14 个跳过都是原有的主机 / 平台跳过，没有一个在 P4-C4 代码中：
4 个 discovery symlink 测试（本主机没有 Windows symlink 权限）以及
10 个仅限 POSIX 的 planning 路径形式。使用 `--basetemp` / `-p no:cacheprovider` 是因为已知的本地 pytest 临时目录权限问题。
P4-C1、P4-C2、P4-C3 以及 Phase 3 的测试集：没有回归。

直接复现（在 pytest 之外的普通 `python` 脚本，import worktree 中的 `src`）：
```text
A exact minimal : '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<movie>\n  <title>Example</title>\n  <uniqueid type="fc2" default="true">FC2-1234567</uniqueid>\n</movie>\n'
B injection     : evil found = False | title = 'A </title><evil>true</evil>'
C U+0000        : NfoXmlCharacterError: metadata.title contains U+0000, which is not a legal XML 1.0 character
D status        : SUCCESS vs PARTIAL identical = True
E hostile       : title / plot -> NfoMetadataError ("must be an exact str, got H"), hooks called = []
F release       : 2024-02-29 -> rendered; 2026-02-30 -> NfoReleaseDateError
G provenance    : leaked sentinels = []
```

## 19. 已知局限

* `fc2db_net` 把 schema.org 的 `uploadDate` 未经形态校验就存入 `release`；那里如果是一个 ISO datetime 值，会让该影片的
  NFO 渲染 fail closed（`NfoReleaseDateError`）。按照设计，这里不做修复；在 adapter 一侧做规范化将是一项独立的、需要订立合同的改动。
* 规范番号只检查为严格 `str`、非空白、XML 安全；它的 FC2 形态由上游（planning / P4-C3）保证，这里不重新校验。
* 空白优先规则：由 `str.strip()` 视为空白的控制字符（U+000B、U+000C、U+001C..U+001F）组成的仅空白可选值会被省略，而不是被拒绝，
  因为它们不会被渲染（合同第 10 节）。
* 在开发过程中，伪造形态测试在提交之前捕获了一个真实缺陷：伪造的 `actors` tuple 中的一个 `None` 条目曾被当作空白项跳过；
  现在会在省略空白项之前先做类型检查。

## 20. 延续的债务

仍然延续、未改变：P4-C3-R-01（LOW）、P4-C3-R-02（LOW）；P4-C2-R1-02（LOW）、OrganizePlan 操作图加固、覆盖执行器语义
（冻结为 `NEVER`）、扩展的 Windows 保留名；P4-C1-R-02..R-05；P2-R-05、P2-R-06、
P2-R-07（LOW / CARRIED -- 没有消费任何 `elapsed_ms`）；C3-N1..N4；C4-N1；
C4-R1-N1..N3；F3；F5；C5-R1-L1。

更早之前已关闭、不再延续：P4-C2 metadata 身份缺口、C2-L2、P2-R-10。

## 21. 整洁性

```text
git diff --check (code candidate, staged)  -> clean (exit 0)
git status --porcelain after push           -> clean (empty)
```

## 22. 状态

```text
Independent Review : REQUIRED
P4-C4              : NOT CLOSED
Phase 4            : NOT CLOSED
```

开发者不宣布 P4-C4 PASS / CLOSED。没有开始任何后续 package。

---

# 最终关闭 -- P4-C4 纯 NFO 渲染（Pure NFO Rendering）

独立复查之后追加的纯文档关闭记录。上面的第 1-22 节是未改动的开发者 handoff（历史记录）。

```text
Phase                      = 4
Package                    = P4-C4 Pure NFO Rendering
Status                     = CLOSED
Final Level                = Level 1 PASS
Final Reviewed Code Head   = 526177b7c4279057633a2fb893fab79804c97835
Previous Docs Head         = 79f74d6b94602a030a45f305a3aad04a66401234
Blocking Findings          = NONE
```

## C.1 独立复查的治理（两份复查）

**复查者 A。** 对 XML 合同、字段映射、XML 1.0 字符安全、XML 注入、恶意文本输入、状态 / 出处隔离、架构以及已知局限做了
静态 / 语义复查：没有发现任何实现层面的阻塞项。复查者 A 给出 FAIL 结论只有一个原因：它的复查环境无法获得本地检出，
因此无法独立运行针对性 pytest、完整 pytest 测试集或一次真正的 `git diff --check`。这是复查执行证据上的缺口，而不是实现、
合同或安全上的缺陷。

**复查者 B。** 在一个临时的 detached worktree 中检出了被复查的确切代码，并独立执行了：

```text
Targeted       : 433 passed, 0 failed, 0 skipped
Full Suite     : 3220 passed, 14 skipped, 0 failed
git diff --check: both ranges clean
```

它还独立运行了直接复现、XML 安全检查、恶意字符串测试、拦截检查、状态隔离检查以及架构检查。结论：**PASS**。

**治理结果。** 复查者 A 所缺少的唯一证据，后来由另一位独立复查者在被复查的确切 worktree 上补足：

```text
Independent Review Evidence Gap (Reviewer A: pytest / full suite / diff-check not run)
Status: SATISFIED / CLOSED by later independent execution evidence (Reviewer B)
```

这个缺口不是产品 finding，不带任何 finding ID。

## C.2 Finding ID 规范化

两位复查者都把一个不同的项目标为 `P4-C4-R-01`。为了保持每个问题一个 ID：

* 复查者 A 的 “无法运行 pytest / diff-check” 项**不**保留为 finding ID。它只作为 C.1 中的独立复查证据缺口记录
  （SATISFIED / CLOSED）。
* **`P4-C4-R-01`** 只指复查者 B 的 LOW finding（C.3）。

## C.3 P4-C4-R-01 -- 容器子类的纵深防御不对称

```text
ID        : P4-C4-R-01
Severity  : LOW
Status    : CARRIED / non-blocking
Topic     : container subclass defence-in-depth asymmetry
```

`render_movie_nfo` 要求严格的 `PublicationRecord`，并且每一个被渲染的文本值都必须是严格的 `str`。但记录内部的容器
（`NormalizedMetadata`、`OrganizePlan`）仍然可以是子类。一个 `NormalizedMetadata` 子类可以在渲染器读取字段时，通过自定义的
`__getattribute__` 运行代码。渲染器仍然会对读取返回的每一个值做严格类型检查。

这并不违反冻结的 P4-C4 合同。它没有产生任何已被证明的 XML 注入、文件系统、网络或出处泄漏。这是一项关于纵深防御一致性的观察。
之后的决定应当要么冻结容器层面的严格类型语义，要么明确把这些容器子类定义为可信输入。本次关闭没有做任何代码改动。

## C.4 对已知局限的裁定

```text
KL-1 Optional Control-Whitespace  = NON-BLOCKING / NOT A DEFECT (contract-defined behavior)
```

冻结的合同（第 10 节）使用空白优先语义。`str.strip() == ""` 的可选值、演员条目或标签条目会被省略，因为它永远不会到达 XML。
只有实际被渲染的值才会经过 XML 字符边界。因此，省略一个只由 U+000B、U+000C 或 U+001C..U+001F 组成的 strip 后为空的可选值，
是符合合同的。不产生任何 finding。

```text
KL-2 fc2db_net uploadDate         = NON-BLOCKING / NOT A P4-C4 DEFECT
```

`fc2db_net` 可能把 schema.org 的 `uploadDate` 直接传入 `metadata.release`。例如给定 `2026-01-01T12:34:56Z`，P4-C4 会抛出
`NfoReleaseDateError`。这是正确的：冻结的合同（第 8 节）要求非空白的 release 必须是严格的 ASCII `YYYY-MM-DD` 真实格里历日期，
并禁止截断、`split("T")`、格式猜测、自动修复和静默省略。渲染器没有改变。

未编号的将来观察：*fc2db_net 的 release 规范化可能需要将来在上游 / 来源层做出决定。* 这不是 P4-C4 的 finding。

## C.5 P2-R-07

```text
P2-R-07 = LOW / CARRIED
```

P4-C4 渲染器既不读取 `SourceResult.elapsed_ms`，也不读取 `SourceAttempt.elapsed_ms`，并且不输出任何计时，因此 P4-C4 不会为这项
债务增加任何新的关闭要求。

## C.6 独立 Level 1 证据

```text
Independent Level 1                                   : PASS
Execution-capable independent reviewer evidence:
  Targeted                                            : 433 passed / 0 failed / 0 skipped
  Full Suite                                          : 3220 passed / 14 skipped / 0 failed
  Direct semantic / security reproductions            : PASS
  Architecture                                        : PASS
  XML contract                                        : PASS
  XML injection                                       : PASS
  XML 1.0 character boundary                          : PASS
  Hostile textual value boundary                      : PASS
  Status isolation                                    : PASS
  Provenance exclusion                                : PASS
  No filesystem / network / clock / random / env / locale : PASS
  git diff --check                                    : clean
```

## C.7 关闭后延续的债务

```text
P4-C4-R-01 -- LOW (new, C.3)
P4-C3-R-01 -- LOW
P4-C3-R-02 -- LOW
P4-C2-R1-02 -- LOW
OrganizePlan operation-graph hardening
overwrite executor semantics = frozen NEVER
extended Windows reserved names
P4-C1-R-02..R-05
P2-R-05
P2-R-06
P2-R-07
C3-N1..N4
C4-N1
C4-R1-N1..N3
F3
F5
C5-R1-L1
```

更早之前已关闭、不再延续：P4-C2 metadata 身份缺口、C2-L2、P2-R-10。

## C.8 本次关闭的范围

这只关闭 **P4-C4**。它不关闭 Phase 4，也不开始任何后续 package。每一个后续 package 都需要自己的冻结合同和复查周期。
本次关闭没有修改任何 `src/**`、`tests/**` 或 `docs/specifications/**` 文件。

## C.9 最终状态

```text
P4-C4: CLOSED
Phase 4: NOT CLOSED
Next Package: NOT STARTED
```
