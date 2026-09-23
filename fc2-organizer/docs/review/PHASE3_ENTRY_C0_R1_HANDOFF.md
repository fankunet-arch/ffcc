# PHASE3_ENTRY_C0_R1_HANDOFF.md

```text
Phase: Phase 3 Entry Gate — C0 R1 (incremental closure round)
Closes:  C0-R1-01 only
Not touched: C0-01, C0-03, C0-04, C0-05 (CLOSED by the previous closure review)

Base (= previous C0 Docs Head):
c0989062e489898b6d73b0814b251b1841e0c469

Previous C0 Code Head (reviewed, closure verdict FAIL on C0-R1-01):
8b16bdbc236fac422074994622670905c8d9b2ec

C0 R1 Code Review Candidate (C0_R1_CODE_HEAD):
c8e185e02454bcbdcf6c531d15d0985c5a7142b2
  = 7a9020d625b04a90f093b3ce0706f685934f33d5  fix(source): bound JavDB total parse cost
  + c8e185e02454bcbdcf6c531d15d0985c5a7142b2  test: correct the performance claim in the adversarial suite docstring
    (comment/docstring only; code identical to 7a9020d)

Review range:
c0989062e489898b6d73b0814b251b1841e0c469..c8e185e02454bcbdcf6c531d15d0985c5a7142b2

C0 R1 Docs Head (C0_R1_DOCS_HEAD):
the commit "docs(review): add Phase 3 entry C0 R1 handoff" whose parent is the
Code Review Candidate above (it adds this file and the correction note in
PHASE3_ENTRY_C0_HANDOFF.md). A commit cannot contain its own hash, so it is
identified by that rule and reported in the hand-back message.

Branch:
claude/phase-0-amane-integration-fnvhpq
```

**这不是 PASS 声明。Phase 3 的功能实现尚未开始；Phase 3 Aggregator Lock 没有解除。**

## C0-R1-01 — 原始复现（独立复查者）

C0 的修复消除了灾难性正则，但 JavDB 解析器的*总*开销在实践中仍然是无界的。复查者针对 `8b16bdb` 的测量，
所用页面由许多 JavDB 条目构成，这些条目的开标签在填充物之间反复拼出 class token marker `video-title` / `meta`：

| 页面大小 | 复查者测得的耗时 |
|---|---|
| ~732 KiB | ~1.2 s |
| ~1.5 MiB | 3.8–4.5 s |
| ~1.8 MiB | ~5.5 s |
| 真实的 JavDB fixture | ~2.8 ms |

复查者得出、并在这里被接受的结论：**针对单个原语的上限，不能作为可接受的解析器总体上界。**

我自己对这种形态的重建（我无法拿到复查者的原始页面；它是根据描述重建的，见*按复查者形态构造的回归测试*）
在这台机器上对**之前的 C0 解析器**复现了这种变慢 — 测得的数字与修复后解析器的数字一起列在下面的
*修复前 / 修复后的耗时*中。

## 根因

`parse_javdb_search_page`（C0）通过*marker 出现位置*查找 `item`、`video-title`、`meta` 中的每一个：
`iter_class_tags(html, token)` 执行 `str.find(token)`，然后对**每一次**出现都重新定位外层的开标签（`rfind` +
`open_tag_at`，最多 1500 个字符），并对其重新运行 `parse_attrs`（一个 Python 层面的循环，大约每个属性 token
迭代一次）。每个页面的开销是：

```text
~200 items
  x  several lookups per item (video-title, meta, <a>, <img>) each allowed 5-20 attempts
  x  one re-scan + re-parse of the SAME opening tag per marker occurrence
  x  up to ~700 attribute tokens per 1500-char tag (dense one-character "attributes")
```

每个因子各自都有上限（`MAX_ATTEMPTS`、`limit=20`、`MAX_TAG_CHARS`），但这些上限相乘了。C0 的对抗性测试集
只有*扁平的*输入，从未把这些因子组合起来，这就是它报告 10.4 ms 的原因。

## 实现方式

记录在 `_scan.py` 中的原则（rule 5）：**工作必须共享，而不是重复。**

`sources/adapters/_scan.py`（纯增量：除了一个可选参数之外，现有 helper 都没有改变）：
- `collect_class_hits(html, wanted, max_chars, max_probes)` — 对页面中带引号的 `class="..."` 属性做**一次遍历**。
  单词 `class` 的每一次出现只消耗一次有锚点、有界的正则匹配；不做任何重新扫描。返回所需 token 的命中结果
  **以及一个 `truncated` 标志**（探测预算用尽，或者页面在扫描窗口之外仍有更多 `class` 属性）。
- `first_open_tag(html, name, start, end, attempts=3)` — 一个区域中的第一个开标签，候选数量为常数。
- `parse_attrs(..., max_attrs=None)` — 对解析的属性 token 数量设置可选上限；JavDB 传入 16（真实标签带有 3–6 个）。

`sources/adapters/javdb.py`：重写了 `parse_javdb_search_page`：
1. 对 `movie-list`、`empty-message`、`item`、`video-title`、`meta` 只做一次 `collect_class_hits` 遍历；
2. 每个条目做**固定**数量的有界查找，位置通过 `bisect` 从已收集的命中结果中取得：`video-title` 标签只解析
   **一次**（`open_tag_containing`），它的 `<strong>` 编号从一个有界窗口中读取，最多尝试 3 个锚点和 3 张图片，
   `meta` 只解析一次。没有任何开标签被解析两次，也没有任何内容按 marker 出现位置去定位。

因此总工作量是一个由具名常量构成的公式，而不取决于页面内容：

```text
<= _MAX_CLASS_PROBES (8000) small anchored matches           [one pass]
 + _MAX_ITEMS (200) x (constant number of windows, each <= 8000 / 3000 / 1500 chars)
```

**显式预算，根据真实数据确定大小。** 本轮在线上抓取的一个真实结果页面（`q=FC2-PPV-48250`，8 个条目）：
**总共 31,459 个字符，列表从第 23,159 个字符开始，最大的条目区域为 779 个字符，整个页面有 290 个 `class` 属性
（每个条目约 ~25 个），444 个标签**。外推到一个完整的 40-item 页面：约 ~1200 个 `class` 单词，约 ~36 KB。
预算（`javdb.py`）：扫描窗口 **512 KiB**（~15x），class 探测次数 **8000**（~6x 一个 40-item 页面；即使是
200 个条目 x 25 也有 ~1.5x），条目数 **200**。我**没有**为了掩盖问题而降低 200-item 的上限。
*（更宽泛的查询，例如 `q=FC2` 和 `q=FC2-PPV-49`，返回的是带 8-byte 响应体的 HTTP 403，因此没有获得更大的真实
页面；上面的余量是从 8-item 页面外推出来的。）*

**预算用尽永远不是 `NOT_FOUND`。** 如果扫描在某个上限处停止（超过 8000 个 `class` 单词、页面长于 512 KiB 且
仍然有 `class` 属性，或者超过 200 个条目）并且没有找到精确命中，解析器就没有看到整个页面，因此结果为
`INVALID_RESPONSE`（"scan budget reached … cannot conclude not found"）。在预算用尽之前找到的精确命中仍然是
`SUCCESS`；明确的 `empty-message` 仍然是 `NOT_FOUND`；一个*窗口之外不再有 `class` 属性*的大页面不会被视为
被截断。（测试：`test_javdb_total_cost.py`。）

同步解析器外面没有包任何线程 / 信号 / asyncio 超时；有界的是复杂度本身。

## 按复查者形态构造的回归测试

`tests/support/adversarial_javdb.py`（以程序方式构建；没有大型 fixture 文件）
和 `tests/unit/sources/adapters/test_javdb_total_cost.py`（14 个测试）。

各种形态，每种都在 **~750 KiB、~1.5 MiB、~3 MiB 和 ~5 MiB**（transport 上限）下，经由**真实的
`parse_javdb_search_page`** 运行；主要形态还经由**带假 HTTP client 的真实 `JavdbAdapter.fetch()`** 运行：

| 形态 | 相乘的是什么 |
|---|---|
| **按复查者形态构造**：200 个条目，真实的 `video-title` 在前，没有 `meta` 元素，每个条目的 `<a>` 开标签塞入约 ~1.4 KB 的单字符属性 token，拼出 `meta` / `video-title` / `item` | `meta` 查找 x marker 出现次数 x 属性 token x 条目 |
| 每个条目的密集标签：在单个条目窗口内尽可能多地放入密集的非详情页 `<a>` / `<img>` 标签 | 锚点 / 图片查找 |
| 每个开标签中都拼出 `item` marker | 条目列表扫描 |
| 每个条目的一个长引号属性值中含有 marker | （对照：即使在旧代码上也很便宜） |
| **合法的精确命中后面跟着恶意形态** | 真实数据必须保留下来 |
| 填满窗口的最大工作量：200 个条目塞进 512 KiB 的扫描窗口，每个条目都把每一次固定查找用满 | 新上界允许的最坏情况 |
| class 属性刷屏 | 探测预算用尽 |

运行发生在一个**带 120 s 硬超时的子进程**中（`re` 会持有 GIL；回归必须从外部杀掉，绝不能等待它完成）。
预算：每个恶意用例 **0.5 s**（约为修复后解析器最坏情况的 ~10x），并且始终低于 C0 测试集现有的 **1.0 s**。
守卫测试还会断言生成器保持恶意性（条目 >= 200、>= 9000 次 marker 出现、大小与标称值相差不超过 2 %），
因此它不可能空洞地通过。5 MiB 的 C0 测试集（`adversarial_html.py`，现在有 51 个用例）为 `av123` /
`fc2db_net` 新增了五个 “dense-attribute” 守卫用例（它们测得的最坏情况约为 ~13 ms；它们不存在“条目 x 查找”的相乘）。

## 修复前 / 修复后的耗时（同一台机器，同一批用例）

Windows 11，Python 3.12.10，每项只运行一次；绝对数字因机器而异，重点在于比率和数量级。可用
`PYTHONPATH="src;tests" python -m support.adversarial_javdb` 复现（每个用例打印一行 JSON）。

主要形态（按复查者形态构造），`parse` 路径 / `fetch` 路径：

| 大小 | **修复前**（C0 `8b16bdb`） | **修复后**（`c8e185e`） | 预算 |
|---|---|---|---|
| ~750 KiB | 864 ms / 862 ms | 16.4 ms / 15.8 ms | 500 ms |
| ~1.5 MiB | 815 ms / 1738 ms | 5.5 ms / 5.5 ms | 500 ms |
| ~3 MiB | 2154 ms / 2038 ms | 2.3 ms / 5.0 ms | 500 ms |
| ~5 MiB | 2158 ms / 2361 ms | 1.4 ms / 3.8 ms | 500 ms |

全部 26 个用例：**修复前 — 26 个中有 21 个超出预算，最坏 2.36 s；修复后 — 0 个超出预算，最坏 40.4 ms**
（填满窗口的最大工作量，200 个条目全部解析）。其他形态修复后：每条目密集标签 6–24 ms，每个标签中都有 `item`
2–10 ms，合法命中 + 恶意尾部 2–12 ms（全部 `SUCCESS`），class 刷屏 6 ms。真实 fixture 的解析耗时约 ~0.5 ms。
（注意：在 >= 750 KiB 时，修复后的解析器在 512 KiB 扫描窗口之后就返回，因此大尺寸的几行反而比填满窗口那一行
*更便宜*，后者才是真正的最坏情况。）

对照复查者自己的数字（732 KiB 时 1.2 s，1.5 MiB 时 3.8–4.5 s），我的重建在 C0 代码上复现了同样的*模式*
（这里为 0.9–2.4 s，可能是机器更快或 token 密度略有不同），修复之后不超过约 ~46 ms。**复查者应当针对 `c8e185e`
重新运行他们自己的复现**；我不能声称使用了他们的原始页面。

验证新测试能捕获旧代码：把 C0 的 `javdb.py` / `_scan.py` 换回来后，`test_javdb_total_cost.py` 得到
**5 failed / 9 passed**（预算测试加上四个预算用尽语义测试），耗时约 ~33 s。

## 正确性保持不变（C0-03 冻结的语义）

未改变，并由现有的 29-test `test_adapter_javdb_semantics.py` 加上真实 fixture 重新验证：

| 页面 | 结果 |
|---|---|
| 列表 + 解析出的候选，没有精确匹配 | `NOT_FOUND` |
| 列表，没有可解析的候选 | `INVALID_RESPONSE` |
| 精确番号，没有标题 | `PARSE_ERROR` |
| 明确的 `empty-message` | `NOT_FOUND` |
| 精确且合法的结果 | `SUCCESS` |
| 真实的模糊页面 `FC2-4824605`（近似未命中项 `FC2-1824605`、`FC2-4724605`） | `NOT_FOUND`，"listed 2 other number(s)" |

class token 的容错（`class="item "`、额外的 CSS class、单引号、`video-title is-x`）以及 `NOT_FOUND` detail
中的已解析候选数量都没有改变（同样的测试，全部通过）。

需要注意的行为变化（欢迎质疑）：
1. `class` 必须是小写、**带引号**的属性（`class="…"` / `class='…'`）；不带引号的 `class=item` 和 `CLASS=`
   不再被识别。JavDB 输出的是小写带引号的 `class`；这一点写在 `collect_class_hits` 的文档中。
2. 每个条目只检查**前 3 个** `<a>` / `<img>` 标签来寻找详情链接 / 封面（之前为 10 / 5）。真实条目中这两者都是
   最前面的标签。
3. 预算用尽且没有精确命中时为 `INVALID_RESPONSE`（新增，见上文）。
4. JavDB 的 title 属性仍然被反转义两次 — **刻意保持不变**（P2-R-10 被延后）。

## 离线测试

```text
Python 3.12.10
python -m pytest --collect-only -q   -> 473 tests collected
python -m pytest -v                  -> 473 passed
python -m pytest -q                  -> 473 passed, 1 warning
```

| | 计数 |
|---|---|
| collected | **473** |
| passed | **473** |
| failed | 0 |
| skipped | 0 |

（相比之前 C0 候选的 459 个 +14：全部位于 `test_javdb_total_cost.py`。那一条 warning 是已知的、来自无法删除且已被
git 忽略的 `.pytest_cache` 的 `PytestCacheWarning`。）

在这 473 个测试中保持不变且通过的：Phase 0 F-02/F-03 脏文件名集合
（`test_normalize_fc2_number.py`，41）；Phase 1 R1/R2（`test_metadata.py` 68、
`test_source_result.py` 47）；**F4**（`test_core_independent_of_amane.py`，27，模块参数化覆盖 `_scan`）；
Phase 2 的 adapter / 框架（fc2db_net 17、javdb 17、av123 15、common 24、registration 3、base 24、registry 10、
fake e2e 9、transport 8）；**C0-01**（`test_fc2_number_canonical_boundary.py` 36、`test_adapter_canonical_boundary.py`
34）；**C0-03**（`test_adapter_javdb_semantics.py` 29）；**C0-04**
（`test_runtime_minutes.py` 45）；**C0-02** 扁平测试集（`test_parser_adversarial.py` 5）。
C0-05（`PHASE2_HANDOFF.md` 的更正）没有被触碰。

## 线上冒烟测试（JavDB 解析器 / `_scan.py` 改动之后）

在 Code Head `c8e185e` 上运行 `tools/probe_sources.py adapter --no-record`
（`--delay-seconds 2.5`，每次查找一个请求，不带 cookie，不绕过 Cloudflare/CAPTCHA），
时间 2026-09-20 15:56:47–15:57:01 UTC。**`docs/source-probes/PHASE2_PROBE_20260920.json`
没有被触碰。**（在 `7a9020d` 上的一次相同运行，15:55:27–15:55:41，得到了同样的结果。）

| 来源 | 番号 | HTTP | 结果 | 备注 |
|---|---|---|---|---|
| `fc2db_net` | FC2-4824605 | 200 | **SUCCESS** | 规范番号、非空日文标题、9 个字段 |
| `fc2db_net` | FC2-4979299 | 200 | **SUCCESS** | 9 个字段 |
| `javdb` | FC2-4825061 | 200 | **SUCCESS** | 6 个字段 |
| `javdb` | FC2-4979299 | 200 | **SUCCESS** | 6 个字段 |
| `av123` | FC2-4825061 | 200 | **SUCCESS** | 6 个字段 |
| `av123` | FC2-4979299 | 200 | **SUCCESS** | 6 个字段 |
| `javdb`（反向） | FC2-4824605 | 200 | **NOT_FOUND** | "search for FC2-4824605 listed 2 other number(s), none exact" |

`av123` 没有出现 HTTP 500，因此不需要重试。每个来源填充的字段与之前各轮完全相同。

## 变更文件（`c098906..c8e185e`）

```text
M src/fc2_metadata_core/sources/adapters/_scan.py        (+collect_class_hits, +first_open_tag, parse_attrs max_attrs; docs)
M src/fc2_metadata_core/sources/adapters/javdb.py        (parser rewritten; semantics unchanged)
M tests/support/adversarial_html.py                      (+5 dense-attribute guard cases)
A tests/support/adversarial_javdb.py                     (reviewer-shaped generator, child-process runner)
A tests/unit/sources/adapters/test_javdb_total_cost.py   (14 tests)
M tests/unit/sources/adapters/test_parser_adversarial.py (docstring correction only)
```

此外，在 docs 提交中：本文件，以及添加到 `docs/review/PHASE3_ENTRY_C0_HANDOFF.md` 的 CORRECTION 说明
（原文保留；两处错误的性能陈述在原位加了注解；没有 amend 任何 Git 历史）。

没有改动：`normalize/`、`models/`、`_common.py`、`fc2db_net.py`、`av123.py`、
`http/`、合同文档、`PHASE2_HANDOFF.md`、任何证据 JSON。

## 已知局限

- 这个上界是*构造性的*（具名常量），而不是形式化证明；它由回归测试集和上面的耗时数据加以证明。解析器仍然是
  `async fetch` 内部的同步 CPU 工作；现在在构造出的最坏情况下被限制在几十毫秒以内，但没有被移出事件循环。
- 预算的大小依据一个 8-item 的真实页面加上外推确定（更宽泛的线上查询被 HTTP 403 阻断）。如果 JavDB 开始返回
  大得多的页面，合法页面可能触及某个预算并被报告为 `INVALID_RESPONSE`（绝不会是错误的 `NOT_FOUND`）；
  这些上限是 `javdb.py` 顶部的具名常量。
- `av123` / `fc2db_net` 保留了 C0 的按原语上限；它们在 dense-attribute 形态上测得的最坏情况约为 ~13 ms，
  也不存在按条目的相乘，但它们没有被重构。

## 延后的待办（未改变）

P2-R-05、P2-R-06、P2-R-07、P2-R-08、P2-R-09、P2-R-10（JavDB 的重复反转义保持原样）、
P2-R-11、P2-R-12 — 按照指示没有触碰。P2-R-08、P2-R-09、P2-R-11、P2-R-12 要在某个 Phase 3 组件开始依赖相应
行为时重新评估。

**F3 — DEFERRED。F5 — DEFERRED。**（定义位于更早的复查报告中；必须最迟在 Phase 5 集成之前关闭。）
**F4 — CLOSED**（仍然被强制执行）。

## 关闭状态

| ID | 状态 |
|---|---|
| C0-R1-01 | 已实现 — 等待独立关闭复查 |
| C0-01 / C0-03 / C0-04 / C0-05 | CLOSED（未修改） |
| F4 | CLOSED |

## Phase 3 功能实现：NOT STARTED

没有实现任何 fan-out、聚合器、优先级、字段合并、重试 / 退避、熔断器、批处理或 Amane adapter。
**在本轮通过独立关闭复查之前，Phase 3 Aggregator Lock 不会解除（NOT lifted）。**

**READY FOR C0 R1 INDEPENDENT CLOSURE REVIEW** — 不是 “C0 PASS”，不是 “Phase 3 PASS”，也不是
“Aggregator unlocked”。
