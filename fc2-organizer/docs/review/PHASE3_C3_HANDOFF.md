# PHASE3_C3_HANDOFF.md

```text
Phase: Phase 3 / C3 — Pre-Batch Live Coverage Gate

C3 Base (Phase 3 C2 Docs Head):
3b5ac61a0cc0b2b7467f2f4623c8e9ba94e922fb

Historical C3 Code Head v1 (superseded, kept in history):
5ad00e525d72759dcff3ae0458a90d8f3b6ac464

Historical Selection Method v1 Head (superseded by Amendment v2, kept in history):
74c98659394223642a41a1e78a9fae7011ba7f00

FINAL C3 CODE REVIEW CANDIDATE (Code Head v2):
578ed56aff9e3b823b39da74dc0fc10dae63456c

Selection Method v2 Head (pre-selection amendment):
3e7bd2ed1436b27f24c09e9e71dd71907c141df8

Candidate Pool Head (pool freeze):
7ba331434332338ae085324f61c69270029a5210

50-ID Set Head (set freeze):
bb05b46e8ed896843d6f501bac09e892c676d031

Evidence Head (primary gate evidence):
80a39fff9cdf94a4eb9e83d1be7ef7947692c800

PHASE3_C3_DOCS_HEAD:
the commit "docs(review): add Phase 3 C3 coverage handoff" whose parent is the Evidence Head above and
whose only change is this file (diff EVIDENCE_HEAD..DOCS_HEAD). A commit cannot contain its own hash, so
it is identified by that rule and reported in the hand-back message.

Branch:
claude/phase-0-amane-integration-fnvhpq
```

**这不是 PASS 声明。** 这是提交给 Phase 3 C3 独立复查的候选。50-ID 的数值门槛已经达到，但这本身**并不**解锁
批处理工作。批处理、熔断器、NFO writer、文件系统操作和 Amane 集成都**尚未**开始。

## 冻结链与复查范围

```text
C3 Base 3b5ac61
  → hardening + Code Head v1 5ad00e5 (superseded)
  → Method v1 74c9865 (superseded)
  → Code Head v2 578ed56            ← final code review candidate
  → Method v2 Head 3e7bd2e
  → Pool Head 7ba3314               (pool built after Method v2 was pushed)
  → Set Head bb05b46                (selector run after the pool was pushed)
  → PRIMARY gate                    (run after the set was pushed; ONE run)
  → Evidence Head 80a39ff
  → Docs Head                       (this file)
```

| 复查 | 范围 | 包含的内容 |
|---|---|---|
| 代码 | `3b5ac61..578ed56` | M1 / L1 修复、文档（L3–L5）、候选池构建器 v2、选择器 v2、门槛 runner、全部测试 |
| 方法 | `578ed56..3e7bd2e` | `PHASE3_50_ID_SELECTION_METHOD.md` Amendment v2（只有文档） |
| 候选池冻结 | `3e7bd2e..7ba3314` | 只有 `PHASE3_CANDIDATE_POOL.json` + `.md` |
| 集合冻结 | `7ba3314..bb05b46` | 只有 `PHASE3_50_ID_SET.json` + `.md` |
| 证据 | `bb05b46..80a39ff` | 只有两个主证据文件 |
| 文档 | `80a39ff..DOCS_HEAD` | 只有本 handoff |

复查者可以独立确认这个顺序：`git log --format='%H %aI %s' 3b5ac61..80a39ff`，并确认主证据记录了
`code_head = bb05b46…`（运行时的仓库 HEAD）以及 `worktree_clean = true`。
**`578ed56` 与 `80a39ff` 之间，`src/`、`tools/` 或 `tests/` 下没有任何文件存在差异**
（`git diff --stat 578ed56 80a39ff -- src tools tests` 为空），因此运行门槛的 engine 就是 Code Head v2 的 engine。

十个 C3 提交，从旧到新：`2f8bddd` M1 修复 · `d378d84` L1 修复 · `dfc27cd` 文档 L3/L4/L5 · `5ad00e5` 工具 v1 ·
`74c9865` 方法 v1 · `578ed56` 工具 v2 · `3e7bd2e` 方法 v2 · `7ba3314` 候选池 · `bb05b46` 集合 · `80a39ff` 证据。

## 在 C3 中关闭的 C2 复查 finding

| Finding | 状态 | 改动 |
|---|---|---|
| **C2-M1** — non-200 状态下的 Cloudflare challenge 响应体（例如不带 `cf-mitigated` 的 503）被判为 `HTTP_SERVER_ERROR` 并被重试 | **CLOSED** | `classify_page_response`（`sources/adapters/_common.py`）现在在任何状态分类**之前**检查 challenge 的 `<title>`（"Just a moment" / "Attention required"，前 4000 个字符）：任何状态 → `BLOCKED`，恰好 1 次 attempt。顺序：`cf-mitigated` header → `blocked_url_markers` → challenge 响应体 → 状态。普通的 5xx（开头附近没有 challenge 标题，或者该短语只出现在正文中 / 窗口之外）保持不变：`HTTP_SERVER_ERROR`，重试一次。 |
| **C2-L1** — 对于服务器指定的 charset（rot13、base64、hex、zlib、bz2、idna、undefined、NUL …），`HttpxTransport` 会泄漏裸的 `LookupError` / `UnicodeError` / `ValueError` | **CLOSED** | 每一种“响应体转文本”的失败，无论来自最终解码**还是** httpx 自身的 charset 探测，都会变成 `HttpDecodingError` → `NETWORK_ERROR` / `DECODE_ERROR`，按 C2 策略重试。Python 完全不认识的 charset 名称（`charset=nonsense`）保留 httpx 的 UTF-8 回退（一个普通响应）。消息中写出截断后的 charset 名称，绝不包含响应体。 |
| **C2-L2** — 公开模型 `SourceExecutionTrace` 允许 engine 永远不会产生的状态（SUCCESS 之后的退避期间出现 deadline、未完成的 SUCCESS attempt、`SOURCE_DEADLINE` 以外 kind 的未完成 attempt、`NOT_FOUND` 之后重试） | **LOW / DEFERRED（未改变）** | 50-ID 门槛不需要它。**在任何批处理 API 把 trace 暴露给更广泛的调用方之前重新评估。** |
| **C2-L3** — `aggregation/__init__.py` 的 docstring 仍然说重试 / 退避不在范围内 | **CLOSED（文档）** | 按真实的 C1+C2 架构重写。 |
| **C2-L4** — C2 handoff 中说 “the base commit has 732 tests” | **CLOSED（文档）** | 在 `PHASE3_C2_HANDOFF.md` 中添加了可见的更正说明（C1 base 收集到 **731** 个；732 = 在 C2 树中运行的 C1 测试，F4 在那里自动发现了新增的 `retry.py`）。原文和历史都没有被触碰。 |
| **C2-L5** — 同时出现的不同致命 `BaseException` | **已记录** | `PHASE3_RESILIENCE_CONTRACT.md` §4：*只传播一个致命异常，以原始对象传播；实现不会保留多个致命异常。* 由 `test_agg_c3_simultaneous_fatal.py` 固定下来（一个原始对象，没有异常组，相同运行下是确定的）。没有重新设计仲裁机制。 |

**其他待办：** P2-R-07 **部分缓解，仍为 LOW**（没有修复；证据使用的是 engine 的 attempt 计时
`engine_elapsed_ms`，而不是 adapter 上报的 `SourceResult.elapsed_ms`）· P2-R-05 LOW · P2-R-06 LOW · P2-R-10 LOW ·
F3 DEFERRED · F5 DEFERRED · F4 CLOSED。

### 针对这些关闭项的测试

`test_agg_c3_challenge_any_status.py`（143）— 真实 adapter × 基于 `httpx.MockTransport` 的真实 `HttpxTransport`：
三个来源 × 9 种状态 × 2 种 challenge 标题 → `BLOCKED`，每次 attempt 1 个请求；503 challenge 之后跟着一个合法页面
也永远不会恢复；普通 5xx（5 种响应体形态）仍然重试一次；并直接测试分类器。`test_httpx_transport_decode_c3.py`
（73）— 16 种非文本 / 不可用的 charset → `HttpDecodingError`，没有任何裸的标准库类型越过边界；合法的 charset
不受影响；端到端为 `DECODE_ERROR`、重试一次、绝不是 `ADAPTER_EXCEPTION`，并在第二次得到干净响应时恢复。
两个文件都已验证**在修复前的代码上失败**（117 个失败），修复后通过。`test_agg_c3_simultaneous_fatal.py`（3）。

## 候选池的第 1 次尝试 — 审计 FAIL（历史记录，必须阅读）

第一个候选池（构建器 v1，code head v1 `5ad00e5`，方法 v1 `74c9865`；创建于 2026-09-20T20:59:28Z；sha256
`098fc71755d24064802d8ced77f5ad4a66082b7590bec42915fcdfdc62416bfa`）**没有通过只读审计**：

| 指标 | 值 |
|---|---|
| 候选 | 167（160 个枚举得到 + 7 个 Phase 2 强制项） |
| 双引用（≥ 2 个外部引用）/ 单引用（恰好 1 个） | 46 / 118 |
| 每个区间的双引用数（已抽样） | 早期 **9**（需要 14）· 中期 34（需要 15）· 近期 **2**（需要 14） |
| 请求数 / 失败数 | 214 / **41 次查找失败** |

问题：**查找失败与真正的否定结果被混为一谈**（都成了 “not confirmed”），而 v1 只按双引用抽样的规则无法被满足。
当时的状态：正式选择器 **NOT RUN**；50-ID 集合 **NOT FROZEN**；主门槛 **NOT RUN**。
第 1 次尝试的候选池**从未被提交、从未被冻结、从未用于任何正式选择**；它的文件只作为任务临时证据保留
（已从工作区删除），选择器也从未在它上面运行过。没有任何 engine 结果影响后续的任何事情：在整个 C3 期间，
在主门槛之前，聚合 engine 从未在任何被抽样的候选上线上运行过（7 个强制 ID 只有它们在 Phase 2 / C2 冒烟测试中的
历史证据 — 见局限 3）。

应对措施 = **选择前的 Amendment v2**（Method §5 允许这样做，单独提交，`3e7bd2e`）：

* **三态查找：** `confirmed` / `negative` / `unavailable`；`unavailable`（超时、连接错误、
  403 / 429 / 5xx / 其他 non-200、诸如 challenge 页面之类不可用的响应体）**永远不会**被当作 `negative`；
* **只重试一次，而且只对 `unavailable` 重试**，重试前同样等待 ≥ 3 s；confirmed / negative 永远不会被重试；
* **前缀枚举全有或全无：** 40 个前缀查询中只要有任何一个在重试后仍为 `unavailable` → 构建失败，不生成候选池文件；
* **优先双引用选择 + 只有在区间不足时才回退到单引用**；零确认的候选永远不合格；强制的 7 个、各区间及其配额
  14/15/14 以及 `PER_PREFIX = 4` 都没有改变；没有新增第三个引用。

重建候选池时，那 41 次失败**没有**再次出现（0 个 unavailable，0 次重试）；近期区间的双引用数从 2 增加到 25。
这与 v1 的混淆掩盖了真实佐证的解释相符，但最初那 41 次失败的原因不明（v1 文件没有记录哪些请求失败了）。

## 候选池（在 `7ba3314` 冻结）

文件：`docs/acceptance/PHASE3_CANDIDATE_POOL.json`（+ `.md` 摘要）。构建器 `tools/build_candidate_pool.py` v2 —
从不 import 聚合 engine、adapter 或 transport（有 AST 测试）；引用 1 = sukebei.nyaa.si 的 torrent 名称列表
（`FC2-PPV-<prefix>*`，前缀 `10 … 49`），引用 2 = netflav.com（只接受 `code` 精确匹配 — 模糊的相邻项、
部分数字匹配和标题中的提及都不算数）。

| 指标 | 值 |
|---|---|
| schema / 流程 | 2 / `PHASE3-CANDIDATE-POOL-v2`，创建于 2026-09-20T21:25:38Z |
| 候选 | **167** = 160 个枚举得到 + **7** 个 Phase 2 强制项；重复 0；全部为规范形式 |
| 前缀枚举 | **40 / 40** 完成，unavailable 0 |
| 请求数 / 重试数 / 无法解释的失败 | **214** / **0** / 0（= 40 个前缀 + 160 个 netflav + 14 个强制 ID 查找） |
| 候选级检查 | confirmed 74 · negative 100 · **unavailable 0** |
| 验证强度 | **≥ 2 个外部引用：70** · **恰好 1 个：94** · **0 个：3** |
| 在 Method v2 下合格的（非冻结） | 早期 40（tier 1：9 + tier 2：31）· 中期 80（34 + 46）· 近期 40（25 + 15） |

**只有出处的强制 ID**（0 个外部引用；*两个*引用都返回了合法响应，但没有精确匹配 — 属于 `negative`，而不是
`unavailable`；Phase 2 的出处永远不计为外部引用）：`FC2-1042815`、
`FC2-4972767`、`FC2-4976588`。它们之所以是强制项，是因为它们在 Phase 2 冻结的探测集合中，它们既不是双引用 ID，
也不是单引用 ID。

**候选池 hash — 两个值，同一份内容。** 权威值 = Pool Head 处确切 Git blob 的 SHA-256：
`48e8300031f855e995114c30bf815843d5c61bcdcff42492803766b5b95a82e2`（LF，135,276 字节）。在 Windows 上审计的工作文件
（CRLF，139,732 字节）：`ffe0b095793a914c9c12cc5af97f220244d4534853d761b523821d5ac0fd4cb9`。语义相等性 **PASS**
（`json.loads` 相等；检出文件做 CRLF→LF 后与 blob 逐字节相同）。正式选择器读取的是用 `git cat-file blob` 导出的 blob，
而不是 Windows 上的检出文件，因此集合不依赖 `core.autocrlf`。

## 冻结的 50-ID 集合（在 `bb05b46` 冻结）

文件：`docs/acceptance/PHASE3_50_ID_SET.json`（+ `.md`，列出全部 50 个 ID 及其 tier 和引用状态）。选择器
`tools/select_50id_set.py`，方法 `PHASE3-50ID-SELECTION-v2`：纯函数、离线，不使用随机数 / 时钟 / 网络 / engine。

| 指标 | 值 |
|---|---|
| ID | **恰好 50 个**，0 个重复，全部为规范形式；**强制 7 个**（Phase 2 冻结的 7 个 — 7/7 都在）+ **抽样 43 个** |
| `dual_reference` / `single_reference_fallback` / `phase2_mandatory` | **38 / 5 / 7**（7 个强制项中有 3 个只有出处） |
| 早期（< 2,000,000） | **15** = 14 个抽样（9 个双引用 + 5 个单引用回退）+ 1 个强制项 |
| 中期（2,000,000–3,999,999） | **15** = 15 个抽样（15 个双引用，0 个回退） |
| 近期（≥ 4,000,000） | **20** = 14 个抽样（14 个双引用，0 个回退）+ 6 个强制项 |
| 零外部引用的抽样 ID | **无** |

Method v2 的行为：仅 tier 1 就填满了中期（34 ≥ 15）和近期（25 ≥ 14），因此那里没有使用回退；早期只有
9 < 14 个双引用，因此 9 个全部选入，再由 5 个单引用回退按同样的均匀步长补足缺口。
**可复现性（全部 PASS）：** 在同一个 blob 上另外做了 3 次独立的 CLI 运行，得到完全相同的有序 `ids[].number`；
纯函数 `select()` 在条目反转 / 打乱（5 个种子）/ JSON key 顺序反转 / 两者兼有 / 重复的情况下，都得到相同的 50 个
（番号**以及** tier 都相同）；一个独立重写的方法实现（与该工具分开编写）也选出了完全相同的 50 个。
集合中的 `candidate_pool.sha256` = `48e83000…82e2`（blob hash）。

集合 hash：工作区（CRLF）`dc6f4af58b3af3df0fe84c6e704be38ae048ecb286333df929fbcd484a78c9a8`；**`bb05b46` 处的
Git blob**（权威）`43beeb6658203d173f6b218729263e674c00fbe1f52a5186690fbec5ded1d2c6`；CRLF→LF 相等性与语义相等性
都为真。证据记录的是工作区 hash（`dc6f4af5…`）；身份由 Set Head +
`set_last_commit = bb05b46` + “committed unchanged” 绑定。

## PRIMARY 50-ID 门槛 — 只运行一次

| 项目 | 值 |
|---|---|
| Runner | `tools/run_50id_coverage_gate.py --run-kind primary --set docs/acceptance/PHASE3_50_ID_SET.json --out-dir docs/acceptance/evidence --delay-seconds 4` |
| 开始 / 结束时间（UTC） | **2026-09-20T23:21:40Z / 2026-09-20T23:25:41Z** |
| 检查过的前提条件 | HEAD = `bb05b46`，工作区干净，集合的最后一次提交 = `bb05b46` 且未修改，此前没有主证据 |
| 配置（冻结的默认值） | 来源顺序 `fc2db_net, javdb, av123`；`max_concurrency` 3；每个来源 20 s deadline；C2 默认 `RetryPolicy`（2 次 attempt，1 s 退避；429 / BLOCKED / NOT_FOUND 永不重试）；ID 严格顺序执行，间隔 4 s |
| **结果** | **共 50 个 · 覆盖 49 个 · 未覆盖 1 个 · 98.0%** — 门槛 ≥ 45/50：**NUMERIC THRESHOLD MET** |
| 聚合结果 | SUCCESS **49** · PARTIAL **0** · FAILED **1** · ENGINE_EXCEPTION **0** |
| 已覆盖但为 PARTIAL | **0** |
| 指标（冻结） | COVERED = 聚合结果 ≠ `FAILED`，metadata 存在，并且 `metadata.meets_minimum_success()`（规范番号 + 非空标题） |

证据（只有 id / 状态 / 结构化错误 kind / attempt 次数 / engine 计时 / 结论 — 没有响应体、cookie、凭据、URL、
标题或错误文本）：
`docs/acceptance/evidence/PHASE3_50_ID_GATE_PRIMARY_20260920T232140Z.json` 和 `.md`。

| 文件 | 工作区 SHA-256（CRLF） | **`80a39ff` 处的 Git-blob SHA-256（权威）** |
|---|---|---|
| `.json` | `822b7705180139945a9b57a8d3de5d4d32125cd7f839806f024a19e1957f1a11` | `2a83de01eadf6ac1ecf611780baeca40cc33f6747f491f760684aed501d3ecf7` |
| `.md` | `66f104be801d23ae5e602f1deb95fddf5efc5f89006065af1426cd361b040185` | `f0da1d68daebb57fb7f6b49549d154c2ed02a9d6a4c9c688676a4bc6f2ad3f8b` |

证据按生成时的原样逐字节提交（从未编辑）；每个工作区文件做 CRLF→LF 后都等于其 blob。
一次只读审计从原始的逐 ID 记录重新计算了所有内容并通过：`run_kind == primary`；50 个结果严格按冻结集合的顺序排列，
没有重复；覆盖 49 + 未覆盖 1 = 50；98.0%；门槛标志；聚合计数；逐来源统计（每个来源 50 个 ID）以及 attempt trace；
重试统计；`m1_violations`；没有任何被禁止的内容。

### 未覆盖的 ID

**`FC2-4493606`** — 聚合结果 `FAILED`，没有标题。`fc2db_net` NOT_FOUND / NOT_FOUND ×1 次 attempt · `javdb` NOT_FOUND /
NOT_FOUND ×1 · `av123` NOT_FOUND / NOT_FOUND ×1。**没有网络、封锁、限流、解析或非法响应失败；**
这是一次干净的三重“不在该目录中”。在冻结集合中，它是一个**`dual_reference`**的近期区间抽样 ID；在主运行之前，
两个独立引用都于 2026-09-20 确认过它（sukebei：1 行 torrent，名称精确匹配；netflav：code 精确命中）。
它被记录为一个**真实观察到的聚合覆盖缺口**。它没有被替换、没有被删除，分母没有被改变，没有进行任何其他主运行，
也**没有进行任何诊断运行**（诊断：NOT RUN — 干净的三重 NOT_FOUND 不是瞬时异常，诊断运行也不能替代主运行）。
这个 ID 的数据集有效性证据是否充分，由独立复查者裁定。

### 来源级统计（最终结果，每个来源 50 个 ID）

| 来源 | success | not_found | 其他运行性失败 | attempt 数 | 重试过的 ID | engine 平均毫秒数 |
|---|---|---|---|---|---|---|
| `fc2db_net` | **27** | **23** | 0 | 50 | 0 | 895 |
| `javdb` | **40** | **10** | 0 | 50 | 0 | 284 |
| `av123` | **44** | **6** | 0 | 50 | 0 | 207 |

（blocked、rate_limited、network_error、parse_error、invalid_response：每个来源都是 0。）
**线上重试：0。M1 违规：0。> 1 次 attempt 之后才 BLOCKED 的：0（没有任何来源以 `BLOCKED` 结束）。**

**M1 和 L1 没有被线上 50-ID 流量自然触发** — 没有出现 challenge、5xx 或解码错误。它们的关闭依据的是上面的离线
生产路径测试，而不是线上证据；重试路径也是如此（线上重试为 0，因此 C2 的重试 engine 也没有在线上被触发）。

### 98% 意味着什么、不意味着什么

98% 是在冻结的 50-ID 集合上的**聚合并集覆盖率**：只要*任何*一个来源提供了规范番号 + 标题，该 ID 就算覆盖。
**它不是单个来源的数字，本 handoff 也不声称“每个来源 ≥ 90%”。** 观察到的各来源成功率为 `fc2db_net` 27/50（54%）、
`javdb` 40/50（80%）、`av123` 44/50（88%）。该门槛有意评估的是多来源聚合 engine。来源级的 NOT_FOUND 计数是目录缺口，
而不是失败，因此从未出现 `PARTIAL`（没有任何来源发生运行性失败）。

## 离线回归（最终，在 `80a39ff` 上；自 `578ed56` 起没有代码改动）

```text
python --version                      Python 3.12.10
python -m pytest --collect-only -q    1595 tests collected
python -m pytest -v                   1595 passed, 0 failed, 0 skipped (0 xfail/xpass/error)
python -m pytest -q                   1595 passed
```

C2 冻结基线的 **1305 passed** 保持不变且通过。**+290 个新的 C3 测试**：challenge-any-status 143、
transport decode 73、simultaneous fatal 3、gate runner 13、gate live path（离线，精确的 `_live` 路径）4、候选池构建器
v2 34、选择器 v2 20。（在 Code Head v1 之前编写的 v1 候选池 / 选择器测试已被 v2 模块替换。）测试隔离说明
（未改变）：在模块顶部 import core 类 — F4 合同测试会重新 import 整个 package；由于本环境中 Windows 临时目录 symlink
的权限问题，测试避免使用 pytest 的 `tmp_path` fixture（改用 `tempfile`）。

## 局限以及复查者应当权衡的事项

1. **集合有效性证据是两个公开站点的快照，而不是基本事实。** Sukebei（torrent 名称）和 netflav 是独立于三个 engine
   来源的*服务*，但不是独立的*源头*（它们都镜像 FC2 目录数据）。Tier 1 要求有 netflav 的佐证，因此双引用 ID 比
   回退 ID 更可能被聚合站收录 — 与一个任意的 FC2 文件相比，这可能会让覆盖率显得更好。50 个 ID 中有 5 个（早期区间）
   是单引用回退；3 个只有出处。认为单引用有效性太弱的复查者可以要求一轮数据集加强（在验收期间刻意**没有**新增
   第三个引用）。
2. **Code Head 被重新打开过一次（v1 → v2）**，原因有两个且都有证据说明（三态可观测性；区间构成），发生在任何选择或
   验收运行之前；v1 保留在历史中，修订写在 Method v2 中。
3. **7 个 Phase 2 强制 ID 已经有历史的聚合证据**（Phase 2 探测和 C2 线上冒烟测试）。根据任务定义它们是强制项，
   而不是 C3 的预检。43 个抽样 ID 在主运行之前从未被传给聚合 engine。
4. **Hash 的双重性**（候选池、集合、证据）：Windows 检出文件是 CRLF，Git 存储的是 LF（`core.autocrlf=true`）。
   权威身份是指定 head 处的 Git blob；两个值都被记录；没有为了让它们相等而改写任何内容。
5. **临时审计脚本不在仓库中。** 只读审计（候选池审计 v1/v2、blob 导出 + 语义相等性、集合可复现性 / 独立重写实现、
   主证据重新计算）是从任务临时目录运行的；它们产出的数字记录在本文件中，从已提交的产物重新计算的成本很低。
6. 候选池内容是 **2026-09-20 的线上快照**：之后重建会得到不同的候选。验收产物是冻结的候选池 / 集合文件，而不是流程本身。

## 建议的复查重点

1. 冻结顺序：构建器 / 选择器 / runner 代码（`578ed56`）→ Method v2（`3e7bd2e`）→ 候选池（`7ba3314`）→ 集合（`bb05b46`）→
   从干净的 `bb05b46` 进行主运行 → 证据（`80a39ff`）；每一次冻结的 diff 只包含它自己的文件。
2. 选择是已提交候选池 blob 的纯函数：在
   `git cat-file blob 7ba3314:fc2-organizer/docs/acceptance/PHASE3_CANDIDATE_POOL.json` 上重新运行 `select_50id_set.py`，
   并比较 ID 序列。
3. 门槛 runner：没有 ID / attempt / 顺序 / deadline 覆盖，≥ 3 s 的节奏，只允许一次主运行的守卫，覆盖判定谓词。
4. `_common.classify_page_response` 的顺序以及 `HttpxTransport` 的解码边界（M1 / L1），包括普通 5xx 仍然会重试。
5. Method v2 的理由以及已披露的有效性取舍（局限 1）；裁定 `FC2-4493606` 的有效性证据。
6. 鉴于各来源的数字（50 个中分别为 27 / 40 / 44），并集覆盖率这种表述方式是否可以接受。

## 尚未开始 / 未声明

* **批处理引擎、全局批处理并发预算、失败子集重试：** NOT STARTED。
* **熔断器：** NOT STARTED。**NFO writer / 图片下载：** NOT STARTED。
* **文件系统重命名 / 移动 / 整理：** NOT STARTED。**Amane adapter / 集成 / GUI：** NOT STARTED。
* 延续自 C2 的规划说明：`max_concurrency` 是每次 `aggregate()` 调用各自的；批处理必须增加跨条目的全局预算
  （外加按 host 的限制和熔断器）— 绝不能是 `gather(500 × aggregate())`。
* 50-ID 数值门槛已达到，但这**并不**解锁批处理；必须先通过独立的 C3 复查。
* 诊断运行：**NOT RUN**。主运行永远不得重跑。
