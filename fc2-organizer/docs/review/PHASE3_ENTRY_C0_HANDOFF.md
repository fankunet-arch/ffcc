# PHASE3_ENTRY_C0_HANDOFF.md

```text
Phase: Phase 3 Entry Gate — C0 Hardening
(Phase 2 is CLOSED: independent Level 2 review = PASS WITH NON-BLOCKING NOTES.
 This is not a Phase 2 R1, and it is not Phase 3 implementation.)

C0 Base (= Phase 2 Reviewed Docs Head):
4e7883e87bd6195080d1eb5afcefda0a8897600d

Phase 2 Reviewed Code Head:
3a23e6fa9a351b5c3bc6d2159028177616f98371

C0 Code Review Candidate (P3_ENTRY_C0_CODE_HEAD):
8b16bdbc236fac422074994622670905c8d9b2ec

Review range:
4e7883e87bd6195080d1eb5afcefda0a8897600d..8b16bdbc236fac422074994622670905c8d9b2ec

C0 Docs Head (P3_ENTRY_C0_DOCS_HEAD):
the commit "docs(review): add Phase 3 entry C0 handoff" whose only change is
this file and whose parent is the Code Review Candidate above. A commit cannot
contain its own hash, so it is identified by that rule and reported in the
hand-back message; `git log --oneline -2` shows it on top of 8b16bdb.

Branch:
claude/phase-0-amane-integration-fnvhpq
```

**这不是 PASS 声明。** 这是提交给 C0 独立关闭复查的候选。**Phase 3 的功能实现尚未开始（has NOT started）。**

> **更正（在 Phase 3 Entry C0 R1 中添加；下面的原文保持不变）。** 本文在 *C0-02 结果* 以及
> *行为变化* 第 5 项中声称，最坏的 5 MiB 恶意用例耗时约 **10.4 ms**，并且解析器开销
> “**在 5 MiB 上限下为毫秒级**”。独立的 C0 关闭复查（结论：FAIL，finding **C0-R1-01**）
> 推翻了把它当作*总*开销结论的说法：
>
> - 支撑该说法的对抗性测试集只包含*扁平的*恶意输入（一个未闭合的标签加上填充物，或者一个重复出现的
>   marker）。它**没有**覆盖复查者构造的 JavDB 形态：一个接近条目上限的结果列表，其开标签在填充物之间
>   反复拼出 class token marker（`video-title`、`meta`）；
> - 在这种形态下，根据复查者的测量，C0 的 JavDB 解析器（`8b16bdb`）耗时
>   **~732 KiB = 1.2 s，~1.5 MiB = 3.8-4.5 s，~1.8 MiB = ~5.5 s**，而真实 fixture 只需 ~2.8 ms；
> - 因此 “10.4 ms 最坏情况” 和 “在 5 MiB 上限下为毫秒级” 作为整个解析器的上界是**无效的**
>   （每一个原语都有上限，但这些上限会相乘）；
> - C0-01、C0-03、C0-04 和 C0-05 不受影响。C0-02 对*灾难性正则*的修复依然成立（复查者最初 2-4 KB 的
>   复现已被修复）；剩余的*组合性*开销由 **C0 R1** 关闭，见
>   `docs/review/PHASE3_ENTRY_C0_R1_HANDOFF.md`。

## 必须关闭的集合

只触碰了 C0-01..C0-05。P2-R-05..P2-R-12 被刻意保持不动（见*延后的待办*）。

| ID | 复查 finding | 状态 |
|---|---|---|
| C0-01 | P2-R-01 规范 FC2 番号边界 | 已实现 |
| C0-02 | P2-R-02 解析器正则的灾难性行为 | 已实现 |
| C0-03 | P2-R-03 JavDB 页面布局漂移被报告为 `NOT_FOUND` | 已实现 |
| C0-04 | P2-R-04 `runtime` 单位未冻结 | 已实现（单位已冻结） |
| C0-05 | P2-R-13 PHASE2_HANDOFF 中的事实错误 | 已实现 |

### C0-01 — 规范 FC2 番号边界

**根因。** Python `str` 模式中的 `^FC2-\d{5,8}$`：`\d` 匹配所有 Unicode 十进制数字，而 `$` 还会在结尾的
`"\n"` 之前匹配。因此 `"FC2-1234567\n"`、`"FC2-１２３４５６７"`（全角）和 `"FC2-٤٨٢٤٦٠٥"`
（阿拉伯-印度数字）都能通过 `is_valid_fc2_number`，进而通过 `require_canonical_number`；随后换行符到达请求层，
泄漏出一个裸的 `httpx.InvalidURL`。

**修复（`normalize/fc2_number.py`）。**
- 冻结的语法：`FC2-[0-9]{5,8}`，整串匹配。`CANONICAL_FC2_PATTERN` 现在是
  `\AFC2-[0-9]{5,8}\Z`，`is_valid_fc2_number` 使用 `fullmatch`。
- `normalize_fc2_number` 的记号模式同样使用 `[0-9]`，外加 `(?<!\d)` / `(?!\d)` 守卫，
  因此一个与*非 ASCII* 数字粘连的看似干净的记号（`"FC2PPV-1234567１"`）会被拒绝，而不是在 ASCII 部分被截断。
  因此两个函数共享同一套数字语义。与记号粘连的 CJK 噪声（`[广告]FC2PPV-1234567高画質.mp4`）仍然可以正常处理。
- `FC2-1234567\n`、`FC2-１２３４５６７`、`FC2-٤٨٢٤٦٠٥`、`FC2-1234567XYZ`、
  `XFC2-1234567` 全部被拒绝；`FC2-4825061` 仍然通过。

**Adapter。** `require_canonical_number` 本来就会先调用 `is_valid_fc2_number`，因此修复会自然传递到 adapter；
并且对每个 adapter 都做了*证明*：
`tests/unit/sources/adapters/test_adapter_canonical_boundary.py` 给
`fc2db_net`、`javdb`、`av123` 各传入一个会记录请求的假 client 以及 10 个非法值
（包括 `..`/`?` 注入尝试和 `""`），并断言抛出
`InvalidCanonicalNumberInputError`，**并且** `client.requested_urls == []`。

**测试。** `tests/unit/core/test_fc2_number_canonical_boundary.py`（36）以及上面的 adapter 测试文件（34）。
已对照旧语法检查：其中 24 个在旧语法下失败（复查者的三个值会到达假 client），修复后全部通过。

### C0-02 — 解析器正则的灾难性行为

**根因。** 三个解析器中都有紧挨着 `\s*` 的惰性 `.*?`、不带锚点的 `[^>]*` 片段以及针对整个页面的 `re.search`：
一个未闭合的相关标签后面跟着空白时，就会出现超线性开销。复查者的测量结果（这里保留下来作为回归目标）：
fc2db_net 2000 个空格 ≈ 2.9 s / 4000 ≈ 63 s；av123 2000 ≈
7.5 s；javdb 2000 ≈ 3.7 s。解析器在 `async fetch` 内部同步运行；Phase 3 会并发运行多个来源。

**评估过的方案及数据。** 在项目使用的 Python 3.12.10 上测量了标准库 `html.parser.HTMLParser`，并**予以否决**：
`"<!--" * 20_000`（80 KB）= 3.2 s，`"<a " * 100_000` 和 `'<a x="' * 50_000` 在
8 s 内都没有完成。没有考虑捕获超时的做法（同步正则无法被中断；必须修复的是复杂度边界）。

**修复。** 新增 `sources/adapters/_scan.py`；三个解析器都在其基础上重写。每一个原语在构造上都是有界的：
1. 用 `str.find` 在一个有辨识度的 marker 上定位候选（C 语言速度，线性）；
2. 限制被检查的候选数量（`MAX_ATTEMPTS = 2000`，外加一些按用途设置的小上限，例如 20 个标题、40 个信息行、
   400 个标签链接、200 个条目）；
3. 只在最多 `MAX_TAG_CHARS = 1500` 或调用方给定 `max_len` 的窗口上运行正则，使用 `match(text, pos, endpos)`
   锚定，绝不在整个页面上做不带锚点的 `search`；
4. 模式没有歧义（首字符互不相交、占有型 `*+`、Python >= 3.11 = 项目的最低版本），因此在窗口内部也无法回溯。
`_common._TAG_RE`（`<[^>]+>` → `<[^<>]*+>`）、Cloudflare 标题检查以及时长正则也都改为线性。
在其窗口内没有闭合的元素视为*未找到*（绝不会是“一直到页面末尾的所有内容”）。transport 的
`DEFAULT_MAX_RESPONSE_BYTES`（5 MiB）没有改动。

**结果。** `tests/support/adversarial_html.py` 每次运行构建 46 个用例
（未闭合的相关标签 + 2000 / 4000 / 5 MiB 的空白和文本；`<h1 `、
`<a `、`<!--`、`<`、`class="`、`<div class="item">`、`<strong>`、不配对的引号重复到 5 MiB；以及一个*合法的*
真实 fixture 后面跟着恶意尾部：未闭合 / 嵌套的 JSON-LD、`/work-tags/` 刷屏、`watch__info-row` 刷屏、
未闭合的 `<dd>`、`video-title` / `item` / `movie-list` 刷屏）。我这次运行中的最坏情况：
**5 MiB 上 10.4 ms**（三个解析器，所有用例）**[这个数字只适用于那个扁平测试集；它不是总体上界 - 见本文顶部的更正]**。
恶意页面得到 `PARSE_ERROR` / `INVALID_RESPONSE`；追加了垃圾内容的真实页面仍然能被解析。

**回归测试设计。** `test_parser_adversarial.py` 在一个**子进程**中运行这些用例（Python 的 `re` 会持有 GIL，
因此进程内的看门狗无法中断一个灾难性模式），整体超时为 90 s，每个用例的预算为 1.0 s（相对测得的毫秒数约有
~100x 的 CI 余量，但仍比复查者最小的复现*低*约 ~3x）。已对照之前的解析器验证：该测试会**干净地以
"exceeded 90 s" 失败**（旧解析器无法完成）。

### C0-03 — JavDB 页面布局漂移不是 `NOT_FOUND`

冻结的行为（同时写在模块 docstring 和 `test_adapter_javdb_semantics.py` 中，29 个测试）：

| 页面 | 结果 |
|---|---|
| 结果列表，解析出 >=1 个候选番号，其中一个是所请求的番号且带有标题 | `SUCCESS` |
| 结果列表，解析出 >=1 个候选番号，但没有精确匹配（只有模糊的近似未命中项） | `NOT_FOUND` |
| 识别出了所请求的番号，但标题缺失 / 为空 | `PARSE_ERROR`（绝不回退为 `NOT_FOUND`） |
| 零结果页面：明确的 `empty-message` 块 | `NOT_FOUND` |
| 存在结果列表，但**无法**解析出任何候选番号（`item` / `video-title` class 被重命名、`<strong>` 被替换、列表容器为空），或者既没有列表也没有 `empty-message` | `INVALID_RESPONSE`（选择它而不是 `PARSE_ERROR`：该页面已不再满足来源合同） |

- *候选番号*是条目 `video-title` 元素中的一个 `<strong>CODE</strong>`（任何厂牌编号）。`listed N other number(s)`
  中的 `N` 是实际**解析出**的候选数量，而不是 HTML 片段数（测试：4 个条目元素，其中 2 个可读 → "2"）。
- 按完整的 CSS class *token* 匹配：`class="item "`、`" item"`、
  `"item is-x"`、`"is-x item"`、`"video-title is-clamped"`、单引号属性都仍然能解析。*被重命名*的 class 为
  `INVALID_RESPONSE`。
- 只要至少解析出一个番号，页面布局就仍然可以识别，因此一个发生漂移的同级条目不会把一次正常的未命中变成
  `INVALID_RESPONSE`（有测试，并在这里写明，以便复查者提出异议）。
- 真实的模糊页面 `FC2-4824605` → `NOT_FOUND`，"listed 2 other number(s)"
  （`FC2-1824605`、`FC2-4724605`）：有 fixture 测试，**也**有下面的线上冒烟测试。
- 29 个测试中有 17 个在旧解析器下失败（漂移时返回的是 `NOT_FOUND`）。

### C0-04 — `runtime` 单位冻结为整分钟

决定记录在 `docs/specifications/FC2_METADATA_CORE_CONTRACT.md`
§2.1b（新增；§2.1 表格的对应行已更新）以及 `NormalizedMetadata` 的 docstring 中：

```text
runtime: int | None, unit = whole minutes, >= 0
seconds are truncated (not rounded) when converting clock-duration values
"55:23" -> 55   "1:02:03" -> 62   "55:59" -> 55   invalid -> None
```

理由：Kodi 的 `<runtime>` 只以分钟为单位。单位是**在 Phase 3 Entry C0 冻结的**；Phase 1 只冻结了类型。
`_common.duration_to_minutes` 中关于 Core 已经有一个 “NFO-facing minutes” 约定的错误 docstring 说法已被删除
（仓库中没有其他地方出现这一说法）。三个 adapter 本来就输出分钟，因此它们的行为没有改变。
`duration_to_minutes` 也变得更严格，并且只接受 ASCII（`[0-9]`，秒数
<= 59，h:mm:ss 需要两位数的分钟且 <= 59，输入超过 64 个字符 → `None`）：
`"55:75"`、`"1:2:03"`、阿拉伯-印度 / 全角数字、ISO-8601 `PT55M23S` 都得到 `None`。测试：
`test_runtime_minutes.py`（45）+ 现有的 `test_adapter_common.py`，包括经由 fc2db_net 和 av123 解析器的端到端测试。

### C0-05 — `PHASE2_HANDOFF.md` 的事实更正

只更正复查者指出的事实，并在该文件中附上一段简短、可见的更正说明：(1) 删除了
“Current Docs Head: reported externally” 占位符 → `Phase 2 Reviewed Docs Head: 4e7883e8…`；
(2) 把 “all my commits are local; nothing pushed” 替换为真实的推送 / 复查状态；(3) `FC2-4824605` 的线上
近似未命中项是 `FC2-1824605` / `FC2-4724605`（而不是 `FC2-1825061`）；
(4) 测试数量记录为 **309 collected / 309 passed**，并把 `45be2b7` 的
“80 new offline tests” 说法注明为一种粗略的历史提交信息描述。**没有 amend 任何 Git 历史。**

## 变更文件（`4e7883e..8b16bdb`）

```text
M docs/review/PHASE2_HANDOFF.md
M docs/specifications/FC2_METADATA_CORE_CONTRACT.md
M src/fc2_metadata_core/models/metadata.py                 (docstring only)
M src/fc2_metadata_core/normalize/fc2_number.py
M src/fc2_metadata_core/sources/adapters/_common.py
A src/fc2_metadata_core/sources/adapters/_scan.py
M src/fc2_metadata_core/sources/adapters/av123.py          (parser rewritten)
M src/fc2_metadata_core/sources/adapters/fc2db_net.py      (parser rewritten)
M src/fc2_metadata_core/sources/adapters/javdb.py          (parser rewritten, semantics)
A tests/support/adversarial_html.py
A tests/unit/core/test_fc2_number_canonical_boundary.py
A tests/unit/sources/adapters/test_adapter_canonical_boundary.py
A tests/unit/sources/adapters/test_adapter_javdb_semantics.py
A tests/unit/sources/adapters/test_parser_adversarial.py
A tests/unit/sources/adapters/test_runtime_minutes.py
```

没有改动 `http/`、`models/source_result.py`、registry、探测工具或任何 Phase 2 证据 JSON。

## 离线测试

```text
Python 3.12.10
python -m pytest --collect-only -q   -> 459 tests collected
python -m pytest -v                  -> 459 passed
python -m pytest -q                  -> 459 passed, 1 warning
```

| | 计数 |
|---|---|
| collected | **459** |
| passed | **459** |
| failed | 0 |
| skipped | 0 |

（那一条 warning 是已知的、无关的 `PytestCacheWarning`，来自无法删除且已被 git 忽略的 `.pytest_cache` 目录 —
见 Phase 2 handoff。）

相对于 C0 Base 时的 309：**+150** = 五个新测试文件中的 149 个
（36 + 34 + 29 + 5 + 45）+ 1，因为
`tests/contract/test_core_independent_of_amane.py` 对每个模块做参数化，现在也覆盖了 `_scan`。

**回归保持（全部包含在 459 个之中）：** Phase 0 F-02/F-03 的脏文件名正向 / 反向集合
（`test_normalize_fc2_number.py`，41，未改变）；Phase 1 R1/R2 的关闭（`test_metadata.py` 68、
`test_source_result.py` 47，未改变）；F4 的关闭（`test_core_independent_of_amane.py`，模块集合参数化现在为 27，
包括新模块）；Phase 2 的 adapter 与框架测试（fc2db_net 17、javdb 17、av123 15、common 24、registration 3、
base 24、registry 10、fake e2e 9、transport 8 — 全部未改变且通过）。

## 线上冒烟测试（解析器改动之后）

在 Code Head `8b16bdb` 上运行 `tools/probe_sources.py adapter --no-record`
（`--delay-seconds 2.5`，每次查找一个请求，不带 cookie），时间 2026-09-20
15:10:23–15:10:37 UTC。**`docs/source-probes/PHASE2_PROBE_20260920.json` 没有被触碰**（`--no-record`）。

| 来源 | 番号 | HTTP | 结果 | 备注 |
|---|---|---|---|---|
| `fc2db_net` | FC2-4824605 | 200 | **SUCCESS** | 规范番号、非空日文标题、9 个字段 |
| `fc2db_net` | FC2-4979299 | 200 | **SUCCESS** | 9 个字段 |
| `javdb` | FC2-4825061 | 200 | **SUCCESS** | 6 个字段 |
| `javdb` | FC2-4979299 | 200 | **SUCCESS** | 6 个字段 |
| `av123` | FC2-4825061 | 200 | **SUCCESS** | 6 个字段 |
| `av123` | FC2-4979299 | 200 | **SUCCESS** | 6 个字段 |
| `javdb`（反向） | FC2-4824605 | 200 | **NOT_FOUND** | "search for FC2-4824605 listed 2 other number(s), none exact" |

每个来源填充的字段与 Phase 2 门槛运行时完全相同（重写改变的是页面的扫描方式，而不是提取的内容）。

## 复查者可能想要质疑的行为变化

1. `<h1>` 标题现在必须在 2000 个字符以内*闭合*；未闭合的标题视为“未找到”（`PARSE_ERROR`），绝不会被读成一个
   巨大的标题。
2. 扫描上限（2000 次 marker 命中、200 个 javdb 条目、400 个标签链接、...）会悄悄截断大得离谱的合法页面。
   真实页面远低于这些上限（fc2db ~60 KB、av123 ~43 KB、javdb 列表 ~30 KB，~40 个条目）。
3. 标签名 / 闭合标签按**小写**匹配，与已采用来源的输出一致（旧的正则除了 JSON-LD 的 `<script type>` 匹配之外，
   本来也是区分大小写的）。
4. `duration_to_minutes` 比以前拒绝更多格式错误的输入（秒数 > 59
   等）— 这是一种收紧，而且只会产出 `None`。
5. 解析器仍然是 `async fetch` 内部的同步 CPU 工作；C0 让这部分开销变得*有界*（在 5 MiB 上限下为毫秒级
   **[作为 JavDB 的总体上界是错误的 - 已在 C0 R1 中更正，见顶部的说明]**），但没有把它移出事件循环。
6. javdb 仍然对 title 属性做了两次反转义（刻意保持原样：P2-R-10 被延后，而且改动它不在 C0 的集合之内）。

## 延后的待办（这里没有关闭 — 保持不变）

| ID | Finding | 备注 |
|---|---|---|
| P2-R-05 | 探测工具的 `anti_bot_hint` 仅凭 `cf-ray` 就会触发 | LOW，工具层面 |
| P2-R-06 | 探测记录中的 `requested_url` 实际上是最终 URL | LOW，工具层面 |
| P2-R-07 | transport 层的失败结果带有 `elapsed_ms = 0` | LOW |
| P2-R-08 | 格式错误的 `base_url` 会暴露原始异常 | 当 Phase 3 的配置 / 来源设置开始提供 `base_url` 时**重新评估** |
| P2-R-09 | 超时是分阶段的，而不是墙钟 deadline | 当 Phase 3 的调度依赖单来源 deadline 时**重新评估** |
| P2-R-10 | javdb 标题被重复反转义 | LOW（见上文） |
| P2-R-11 | registry factory 的校验 | 当 Phase 3 的分派依赖它时**重新评估** |
| P2-R-12 | 分类上的细微差别 | 当 Phase 3 在重试决策中使用 `SourceStatus` 语义时**重新评估** |

P2-R-08、P2-R-09、P2-R-11 和 P2-R-12 必须在某个 Phase 3 组件开始*依赖*相应行为时重新评估，而不是之前。

**F3 — DEFERRED（未改变）。** **F5 — DEFERRED（未改变）。** 两者都是 Phase 0 /
Phase 1 独立复查中的非阻塞 finding，其定义位于那些复查报告中（本仓库只记录它们的 id：见
`PHASE1_R1_HANDOFF.md`、`PHASE1_R2_HANDOFF.md`）；它们必须最迟在 Phase 5 集成之前关闭。
**F4 保持 CLOSED**（仍由按模块参数化的合同测试强制执行，该测试现在也覆盖 `_scan`）。

## Phase 3 功能实现：NOT STARTED

本轮没有实现、也不存在以下任何内容的代码：多来源 fan-out、优先级调度器、字段合并、聚合、重试 / 退避、
熔断器、批处理、Amane adapter。C0 是 Phase 3 的*入口门槛*，而不是聚合器。

**READY FOR C0 INDEPENDENT CLOSURE REVIEW** — 不是 “C0 PASS”，也不是 “Phase 3 PASS”。
