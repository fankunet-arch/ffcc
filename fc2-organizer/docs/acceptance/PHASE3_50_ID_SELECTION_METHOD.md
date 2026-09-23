# Phase 3 C3 — 50-ID 覆盖集合：选取方法

> **状态：v2 现行有效（见文末“Amendment v2”）。** 下方 v1 文本作为历史原样保留。
> v2 与 v1 不同之处——候选池可观测性（§3）、抽样资格（§4）——以 v2 规则取代 v1 规则；
> 其余内容（目的、有效性证据、§6 中的冻结 / 运行 / 计数口径）仍按原文适用。

方法 id：`PHASE3-50ID-SELECTION-v1`（历史），现为 `PHASE3-50ID-SELECTION-v2`。可执行形式：
`tools/select_50id_set.py`。v1 文本在候选池存在**之前**、且在为验收运行任何聚合查询之前即已提交。
下文没有任何内容按引擎结果调整，引擎也从不接触候选池。

## 1. 目的与最重要的规则

该 gate 要回答：*在 50 个已知真实存在的 FC2 ID 中，聚合引擎能把多少个转化为
canonical number + 非空标题？* 如果这 50 个是通过观察引擎能解析哪些 ID 挑出来的，
这个数字就毫无意义。因此：

* 这 50 个 ID 在 primary run **之前**固定，之后永不更改。
* 一个 ID 是否“known-valid”，由**非引擎来源的公开参考**判定
  （引擎来源为 `fc2db_net`、`javdb`、`av123`）。候选池构建器与选取器不 import 引擎、适配器或
  transport（有测试强制约束）。
* 选取是候选池文件的纯函数：相同候选池 → 相同的 50 个 ID。无随机性、无 seed、无时钟、
  无人工判断。

## 2. 有效性证据（“known-valid”）

| 参考 | 作用 | 使用方式 |
|---|---|---|
| **R1 — `sukebei.nyaa.si` 种子列表** | 枚举 + 有效性 | 公开搜索 `FC2-PPV-<prefix>*`（第一页结果）。仅当某个种子*名称*包含 `FC2-PPV-<number>`（常见写法）时该 ID 才计入。 |
| **R2 — `netflav.com` 搜索** | 佐证 | 按编号公开搜索。仅当嵌入结果的 `code` **恰好**等于该编号时才计入（模糊近邻永不计入）。 |
| Phase 2 冻结集合 | 7 个强制 ID 的来源出处 | 对这些 ID 在 R1/R2 之外额外记录。 |

每个 ID 记录：canonical number、哪些参考确认了它、备注、UTC 验证日期。**永不**
记录：响应体、headers、cookies、tokens、账号数据。恰好被一个外部参考确认的 ID
在备注中标注为 *single-source validation*。

已知局限（事先说明，不加隐藏）：R1 与 R2 相对于三个引擎来源是独立的*服务*，
但并非独立的*源头*——它们最终都反映 FC2 Content Market 的目录数据，且聚合站点部分重叠。
因此要求 R2 佐证会使集合偏向被多个站点公开索引的 ID，这可能使覆盖率看起来比任意一个 FC2
文件的情况略好。复查者应权衡这一点；替代方案（单参考 ID）则以更弱的有效性作为代价。

## 3. 候选池（`PHASE3_CANDIDATE_POOL.json`，由 `tools/build_candidate_pool.py` 构建）

1. 对每个两位前缀 `10 … 49`（40 个前缀，大致覆盖 1.0 M – 4.99 M）用
   `FC2-PPV-<prefix>*` 查询 R1。候选 = 出现在种子名称中、以该前缀开头的 7 位编号。
2. 每个前缀按该前缀候选升序列表的均匀步长保留 `4` 个
   （`((2j+1)·n)//(2·4)`）；若 ≤ 4 个则全部保留。
3. 在 R2 上查询每个保留的候选（精确 code 匹配）。
4. 7 个 Phase 2 冻结 ID 以同样方式在 R1 与 R2 上查询，且无论 R1/R2 结果如何，
   它们始终在候选池中。
5. 请求串行、间隔 ≥ 3 s，不做任何形式的绕过；失败的请求视为“未被该参考确认”，
   并在文件中计数。

## 4. 选取（`tools/select_50id_set.py`）

1. **强制（7 个）：** `FC2-4825061, FC2-4824605, FC2-4979299, FC2-4976588, FC2-1042815, FC2-4978035,
   FC2-4972767` 始终在集合中。
2. **抽样资格：** `external_reference_count ≥ 2`（R1 **且** R2）的候选池条目，排除这 7 个，
   经 canonical 化、去重、按编号升序排序。
3. **分段（固定数值区间）及其余 43 个的配额：**

| 分段 | 编号 | 配额 |
|---|---|---|
| older | `< 2,000,000` | 14 |
| middle | `2,000,000 – 3,999,999` | 15 |
| recent | `≥ 4,000,000` | 14 |

4. **分段内**若有 `m` 个合格成员、配额为 `q`，则取下标
   `((2j+1)·m) // (2q)`（`j = 0 … q-1`）处的成员——即在升序列表上均匀步长抽取。
5. 结果按升序排序，且必须是**恰好 50 个互不相同**的 ID。合格成员少于配额的分段是**错误**；
   算法从不静默挪动配额，也不替换为其他 ID。

多样性由构造保证：连同 7 个强制 ID，集合包含 ≥ 15 个 older、≥ 15 个 middle 和 ≥ 20 个 recent
ID，范围从 1.0 M 区域跨到 4.9 M 区域；它不可能是单个连续区块。

## 5. 修订政策（仅限选取前）

若候选池无法填满某个配额，方法可以在**运行选取器之前**修订，只能依据候选池构成
（绝不依据引擎结果），并通过一个说明改动内容及原因的独立提交完成。集合文件
提交后不再允许任何修订。

## 6. 冻结、运行与计数口径

* 集合以 `docs(acceptance): freeze Phase 3 50-ID coverage set` 单独提交；该提交
  （`PHASE3_C3_SET_HEAD`）必须先于 primary run。runner 在以下情况拒绝 primary run：工作树不干净、
  集合文件未提交/已修改，或 primary 证据已存在。
* **Primary run——恰好一次。** 使用真实 `MultiSourceEngine`、C3 代码 head、默认顺序
  `fc2db_net, javdb, av123`、C2 默认 `RetryPolicy`（2 次尝试；429 / BLOCKED / NOT_FOUND 永不重试），
  ID 串行、间隔 ≥ 4 s。其结果即正式的分子/分母。
* **Covered** = 聚合状态 ≠ `FAILED`、metadata 存在，且 `metadata.meets_minimum_success()`
  （canonical number + 非空标题）。`SUCCESS` 与 `PARTIAL` 都可以算 covered；每个 `PARTIAL` 以及每个
  来源级失败都单独报告，因此来源健康状况永远不会被覆盖率数字掩盖。
* **Gate：** 50 个中 covered ≥ 45 个（90 %）。达到时只报告为*达到数值阈值*——绝不报告为 C3
  PASS；由独立复查者裁定。
* **未覆盖的 ID 永不替换**，也不增加第 51 个 ID。可以用*诊断性*重跑调查失败原因，
  但其单独记录，且永不取代 primary 结果。
* **若集合中某个 ID 被证实并非真实的 FC2 产品：** 不会被悄悄替换。它仍留在
  primary 结果的分母中，在证据中以 *invalid-set-item investigation* 形式记录，并由
  复查者决定是否允许一轮数据集修正。

---

# Amendment v2 — `PHASE3-50ID-SELECTION-v2`（选取前修订 1）

依据 §5（“修订政策：仅限选取前、仅依据候选池构成、独立提交”）作出。它**不是**
一轮 C3 复查（C3 尚未提交独立复查），也**不**基于任何引擎结果。

## A. 本修订不抹除的历史事实

| 项目 | 值 |
|---|---|
| C3 base | `3b5ac61a0cc0b2b7467f2f4623c8e9ba94e922fb` |
| 历史 C3 Code Head v1 | `5ad00e525d72759dcff3ae0458a90d8f3b6ac464` |
| 历史 Selection Method v1 Head | `74c98659394223642a41a1e78a9fae7011ba7f00` |
| C3 Code Head v2（取代 v1 作为代码复查候选） | `578ed56aff9e3b823b39da74dc0fc10dae63456c` |
| 本修订之前运行过的正式 50-ID 选取器 | **NOT RUN** |
| 本修订之前已冻结的 50-ID 集合 | **NO** |
| 本修订之前的 primary 覆盖 gate | **NOT RUN** |
| 候选池构建期间（attempt 1）使用了聚合引擎 | **NO** |

## B. 候选池 Attempt 1——审计 FAIL，从未冻结，从未提交

由 v1 构建器生成（创建于 2026-09-20T20:59:28Z；文件 sha256
`098fc71755d24064802d8ced77f5ad4a66082b7590bec42915fcdfdc62416bfa`，仅作为 job 临时目录证据保留）：

| 度量 | 值 |
|---|---|
| 候选总数 | 167（160 个枚举所得 + 7 个 Phase 2 冻结） |
| ≥ 2 个外部参考（“dual”） | 46（45 个抽样 + FC2-4825061） |
| 恰好 1 个外部参考（“single”） | 118 |
| 各分段 dual 数（抽样候选） | older **9**（配额 14）、middle 34（配额 15）、recent **2**（配额 14） |
| 请求 / 失败 | 214 次请求，**41 次失败**——记录为“未确认”，即**未与真正的否定结果区分** |

两个彼此独立的缺陷，均与引擎结果无关：

1. **构成。** v1 要求每个抽样 ID 都有 ≥ 2 个外部参考。这是一项*额外*加强，
   并非原始 gate 的一部分（“known-valid ID；优先 ≥ 2 个参考；若只有一个公开
   参考，须明确标注为 single-source validation”）。以 Attempt 1 的构成，v1 无法运行。
2. **可观测性。** 查询失败（timeout / 403 / 429 / 5xx）与成功返回的“无精确匹配”都被存为
   “未确认”。这可能使哪些 ID 看起来是单参考或双参考产生偏差，并掩盖运行层面的失败。

## C. v2 的变更

### C.1 构建器（取代 §3）

* 每次参考查询的结果只能是 **`confirmed`**（有效响应，存在精确证据）、**`negative`**（有效响应，
  无精确证据）或 **`unavailable`**（timeout、连接错误、HTTP 403 / 429 / 5xx / any non-200，或
  不可用的响应体，例如 challenge 页面）。`unavailable` **永不**被转换为 `negative`。
* `unavailable` 在同样 ≥ 3 s 延迟后获得**一次**礼貌性重试（不轮换代理、不绕过、不带 cookies）；
  `confirmed` 与 `negative` 永不重试。记录最终状态、尝试次数（1 或 2）以及有界的、
  非敏感的细节（HTTP 状态 / 异常*类型* / `exact_match` / `no_exact_match`）。
* **前缀枚举全有或全无：** 若 40 个 `FC2-PPV-<prefix>*` 查询中任何一个在重试后仍为 `unavailable`，
  构建即失败（非零退出码，不产生候选池文件）。它绝不会被解读为“零候选”。
* 枚举所得候选按构造即为 R1-confirmed；其 R2（netflav）状态如实记录。R2
  `unavailable` 使该候选成为*单参考*候选（`external_reference_count = 1`），且不可用状态
  可见——它不是 R2 否定结果。
* 7 个 Phase 2 ID 使用同样的三态查询。它们的 Phase 2 出处保留在 `validity_sources` 中，但
  **永不计为**外部参考（`external_reference_count` 只统计 confirmed 的 R1/R2）。
* 候选池 schema v2：`candidates[]`（每项含 `number`、`band`、`origin`、`validation_date`、`validity_sources`、
  `external_reference_count`、`validity_note`、`reference_checks{sukebei,netflav}`），顶层 `requests_made`、
  `retry_requests`、`initial_requests`、`confirmed_checks`、`negative_checks`、`unavailable_checks`、
  `prefix_enumeration_complete`，以及一张按前缀的表。每次请求都恰好对应一条已记录的 check。
* **不变：** `PER_PREFIX = 4`（总体足够大；缺口在于佐证稀疏，扩大候选池
  会增加大量请求却无法解决问题）、40 个前缀、R1/R2 及其精确匹配规则
  （模糊命中、部分数字匹配、标题提及和子串永不计入）。本轮**不增加第三个参考**：
  那会在验收期间引入新的解析器 / 网络依赖及其自身的精确匹配语义。若独立复查者认为
  单参考有效性对 gate 而言过弱，可以要求一轮数据集加强。

### C.2 选取（取代 §4）：dual 优先，透明的单参考回退

强制 7 个、三个数值分段及配额（older 14 / middle 15 / recent 14 = 43）**不变**。
抽样资格现在在每个分段内分为两层，只按 *confirmed* 外部参考计数：

| 层级 | 规则 | `validation_tier` |
|---|---|---|
| 1 — 优先 | ≥ 2 个 confirmed 外部参考 | `dual_reference` |
| 2 — 回退 | 恰好 1 个 confirmed 外部参考 | `single_reference_fallback` |
| 永不合格 | 0 个 confirmed：零参考、仅 negative、仅 unavailable、仅有 Phase-2 出处 | — |

对配额为 `q`、tier-1 升序列表为 `T1`（`m = |T1|`）的每个分段：

* `m ≥ q` → 在下标 `((2j+1)·m) // (2q)` 处从 `T1` 取 `q` 个；**完全不使用 tier 2**。
* `m < q` → 取 `T1` **全部**，再从 tier-2 升序列表 `T2`（`m' = |T2|`）在下标
  `((2j+1)·m') // (2·deficit)` 处取 `deficit = q − m` 个。若 `m' < deficit`，选取即为**错误**（应扩大候选池；绝不挪动配额）。

仅作示意（正式计数来自重建并冻结的 v2 候选池）：按 Attempt 1 的形态，older
分段将取其 9 个 dual + 5 个 single，middle 仅从其 34 个 dual 中取 15 个，recent 取其 2 个 dual + 12 个 single。

强制 ID 带 `validation_tier = phase2_mandatory`。每个被选 ID 的 `validation_tier`、
`reference_checks`、`validity_sources` 与 `validity_note` 都在集合文件中，因此复查者能准确看到
50 个中有多少是 dual、single-fallback 或 mandatory。选取器拒绝前缀枚举不完整、
schema 过旧，或某候选存储的 `external_reference_count` 与其自身 `reference_checks` 不一致的候选池。
它保持纯函数：离线、无随机性、选取中无时钟、无引擎、无适配器。

### C.3 单参考回退为何可接受，及其代价

原始要求是 known-valid ID，*优先*由 ≥ 2 个独立公开参考佐证，
单参考 ID 须明确标注。v1 的“仅 dual”比这更严格。v2 保持 dual 优先，仅在填补分段缺口时
使用带标注的单参考回退。代价是这些 ID 的有效性证据较弱（只有一个种子名称参考，
无聚合站点佐证）；这一点按 ID 逐一披露，且回退项由同样的盲步长选出，绝不依据引擎结果。
一个值得了解的副作用：由于 tier 1 要求 netflav 佐证，dual ID 比回退 ID 更可能被聚合站点索引。

## D. 新的冻结链

`C3 Code Head v2` → `Selection Method v2 Head`（本修订）→ **用构建器 v2 重建候选池** →
`Candidate Pool Freeze Head` → 选取器 → `50-ID Set Freeze Head` → **PRIMARY gate** → 证据 / handoff 文档。
候选池只在本修订提交并推送之后重建；选取器只读取已提交的候选池；
primary gate 只在集合文件提交之后运行。若 v2 候选池仍无法由 tier 1 + tier 2 填满某个分段，
流程即停止等待决策（第三个参考 / 扩大枚举）；不做任何静默调整。
