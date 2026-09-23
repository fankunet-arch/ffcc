# Phase 3 C3 — 已冻结的 50-ID 验收集合

机器可读集合：`docs/acceptance/PHASE3_50_ID_SET.json`。本文件是它的人类可读摘要。该集合
由添加这两个文件的提交冻结。**尚未对其中任何 ID 进行过 C3 聚合 / 覆盖运行**
（43 个新选取的 ID 从未交给过聚合引擎；7 个 Phase 2 强制 ID 只有其
历史 Phase 2 / C2 smoke 证据，这些证据不属于本 gate）。primary 覆盖 gate 读取
这个已提交的集合，并且只在本次冻结之后运行。

## 1. 出处与绑定

| 项目 | 值 |
|---|---|
| C3 Code Head v2 | `578ed56aff9e3b823b39da74dc0fc10dae63456c` |
| C3 Selection Method v2 Head | `3e7bd2ed1436b27f24c09e9e71dd71907c141df8` |
| C3 Pool Head | `7ba331434332338ae085324f61c69270029a5210` |
| 选取方法 | `PHASE3-50ID-SELECTION-v2`（`docs/acceptance/PHASE3_50_ID_SELECTION_METHOD.md`，Amendment v2） |
| 选取器 | `tools/select_50id_set.py`（纯函数、离线、确定性） |
| 候选池路径 | `docs/acceptance/PHASE3_CANDIDATE_POOL.json` |
| **权威候选池 SHA-256** = Pool Head 处该 Git blob 精确字节的 SHA-256 | `48e8300031f855e995114c30bf815843d5c61bcdcff42492803766b5b95a82e2` |
| 同一候选池在 Windows 审计 checkout 中的 SHA-256（CRLF） | `ffe0b095793a914c9c12cc5af97f220244d4534853d761b523821d5ac0fd4cb9` |
| 集合创建时间（UTC） | 2026-09-20T23:16:45+00:00 |
| 正式选取器运行 | **RUN**（一次，基于导出的 Pool Head blob） |
| 集合冻结时的 primary 覆盖 gate | **NOT RUN** |

**为何有两个候选池哈希。** 候选池在 Windows 上构建和审计，工作文件为 CRLF
（`ffe0b095…`）。本仓库使用 `core.autocrlf=true`，因此 Git 以 LF 行尾存储相同内容
（`48e83000…`）。两者**仅**在行尾表示上不同；解析后的 JSON 完全相同（已验证：
`json.loads(blob) == json.loads(checkout)` 为真，且 checkout 做 CRLF→LF 规范化后与 blob
逐字节相等）。为使集合不依赖平台与 `autocrlf`，正式选取器**没有**指向
Windows checkout：`PHASE3_CANDIDATE_POOL.json` 的精确字节通过
`git cat-file blob` 从 Pool Head 提交导出（只取字节，不做换行 / 编码转换），经验证其哈希为 `48e83000…`，该文件即
选取器的 `--pool` 输入。集合把 blob 哈希记录为 `candidate_pool.sha256`；记录的
`candidate_pool.file` 为上述仓库路径。候选池未被修改、替换或重建，选取器与方法
也均未改变。

## 2. 构成

* **已选 ID：50 个**，重复 0 个，全部 canonical，按升序排序（FC2-1042815 … FC2-4979299）。
* **Phase 2 强制 ID：7 / 7** 均在集合中。

| 证据层级（`validation_tier`） | 数量 |
|---|---|
| `dual_reference`（≥ 2 个 confirmed 外部参考） | **38** |
| `single_reference_fallback`（恰好 1 个 confirmed 外部参考） | **5** |
| `phase2_mandatory` | **7** —— 其中仅有出处（0 个外部参考）的：**3** |

| 分段 | 区间 | 抽样数（配额） | dual | single fallback | + 分段内强制 ID | 集合内合计 |
|---|---|---|---|---|---|---|
| older | < 2,000,000 | 14 (14) | 9 | 5 | 1 | 15 |
| middle | 2,000,000 – 3,999,999 | 15 (15) | 15 | 0 | 0 | 15 |
| recent | ≥ 4,000,000 | 14 (14) | 14 | 0 | 6 | 20 |

Method v2 的行为（由选取器产出，而非手工构造）：在 **middle** 与 **recent** 分段中，tier 1（≥ 2 个参考）已经填满配额（34 ≥ 15 与 25 ≥ 14），因此这两段**未使用单参考回退**。在 **older** 分段中 tier 1 只有 9 < 14，因此取全部 9 个 dual 候选，再加上按 tier-2 升序列表均匀步长选出的 **5** 个单参考回退。没有任何抽样 ID 的外部参考为 0。

### 仅有出处的强制 ID

`FC2-1042815`、`FC2-4972767`、`FC2-4976588` 之所以在集合中，仅因为它们属于 Phase 2 冻结 probe 集合。两个外部参考都返回了有效响应但无精确匹配（`negative`，而非 `unavailable`），因此其 `external_reference_count` 为 0；Phase 2 出处永不计为外部参考。它们既不是 dual 也不是单参考 ID。

其余强制 ID 带有外部证据：`FC2-4824605`、`FC2-4825061`、`FC2-4978035`、`FC2-4979299`（FC2-4824605 与 FC2-4825061 为 dual；FC2-4978035 与 FC2-4979299 为 single，sukebei-confirmed / netflav-negative）。

## 3. 可复现性（全部 PASS）

* 选取器又在同一导出 blob 上独立运行了 **3 次**：每次有序的 `ids[].number` 序列都与正式输出完全相同（`created_at` 不同，ID 不变）。
* 纯函数 `select()` 在条目反转、打乱（5 个 seed）、JSON 键顺序反转、两者组合，以及条目重复的情况下，都给出相同的 50 个（编号**与**层级）。
* 与该工具分开编写的 Method v2 独立重实现选出了完全相同的 50 个 ID。
* 每个 ID 都存在于冻结候选池中；证据字段（`validity_sources`、`reference_checks`、`validity_note`、`validation_date`、`external_reference_count`）是候选池条目的逐字节副本。

## 4. 这 50 个 ID

| # | 编号 | 分段 | 来源 | 层级 | 外部参考数 | 参考检查 |
|---|---|---|---|---|---|---|
| 1 | FC2-1042815 | older | phase2_frozen | phase2_mandatory | 0 | sukebei negative / netflav negative |
| 2 | FC2-1097500 | older | sampled:older | single_reference_fallback | 1 | sukebei confirmed / netflav negative |
| 3 | FC2-1261799 | older | sampled:older | single_reference_fallback | 1 | sukebei confirmed / netflav negative |
| 4 | FC2-1395953 | older | sampled:older | single_reference_fallback | 1 | sukebei confirmed / netflav negative |
| 5 | FC2-1528279 | older | sampled:older | single_reference_fallback | 1 | sukebei confirmed / netflav negative |
| 6 | FC2-1692217 | older | sampled:older | single_reference_fallback | 1 | sukebei confirmed / netflav negative |
| 7 | FC2-1713543 | older | sampled:older | dual_reference | 2 | sukebei confirmed / netflav confirmed |
| 8 | FC2-1737461 | older | sampled:older | dual_reference | 2 | sukebei confirmed / netflav confirmed |
| 9 | FC2-1782986 | older | sampled:older | dual_reference | 2 | sukebei confirmed / netflav confirmed |
| 10 | FC2-1817510 | older | sampled:older | dual_reference | 2 | sukebei confirmed / netflav confirmed |
| 11 | FC2-1841311 | older | sampled:older | dual_reference | 2 | sukebei confirmed / netflav confirmed |
| 12 | FC2-1858921 | older | sampled:older | dual_reference | 2 | sukebei confirmed / netflav confirmed |
| 13 | FC2-1879883 | older | sampled:older | dual_reference | 2 | sukebei confirmed / netflav confirmed |
| 14 | FC2-1940353 | older | sampled:older | dual_reference | 2 | sukebei confirmed / netflav confirmed |
| 15 | FC2-1977836 | older | sampled:older | dual_reference | 2 | sukebei confirmed / netflav confirmed |
| 16 | FC2-2050468 | middle | sampled:middle | dual_reference | 2 | sukebei confirmed / netflav confirmed |
| 17 | FC2-2086710 | middle | sampled:middle | dual_reference | 2 | sukebei confirmed / netflav confirmed |
| 18 | FC2-2172250 | middle | sampled:middle | dual_reference | 2 | sukebei confirmed / netflav confirmed |
| 19 | FC2-2278260 | middle | sampled:middle | dual_reference | 2 | sukebei confirmed / netflav confirmed |
| 20 | FC2-2570996 | middle | sampled:middle | dual_reference | 2 | sukebei confirmed / netflav confirmed |
| 21 | FC2-2629560 | middle | sampled:middle | dual_reference | 2 | sukebei confirmed / netflav confirmed |
| 22 | FC2-2733270 | middle | sampled:middle | dual_reference | 2 | sukebei confirmed / netflav confirmed |
| 23 | FC2-2807093 | middle | sampled:middle | dual_reference | 2 | sukebei confirmed / netflav confirmed |
| 24 | FC2-2865991 | middle | sampled:middle | dual_reference | 2 | sukebei confirmed / netflav confirmed |
| 25 | FC2-2909140 | middle | sampled:middle | dual_reference | 2 | sukebei confirmed / netflav confirmed |
| 26 | FC2-2954603 | middle | sampled:middle | dual_reference | 2 | sukebei confirmed / netflav confirmed |
| 27 | FC2-3078940 | middle | sampled:middle | dual_reference | 2 | sukebei confirmed / netflav confirmed |
| 28 | FC2-3084171 | middle | sampled:middle | dual_reference | 2 | sukebei confirmed / netflav confirmed |
| 29 | FC2-3119265 | middle | sampled:middle | dual_reference | 2 | sukebei confirmed / netflav confirmed |
| 30 | FC2-3178581 | middle | sampled:middle | dual_reference | 2 | sukebei confirmed / netflav confirmed |
| 31 | FC2-4070093 | recent | sampled:recent | dual_reference | 2 | sukebei confirmed / netflav confirmed |
| 32 | FC2-4134556 | recent | sampled:recent | dual_reference | 2 | sukebei confirmed / netflav confirmed |
| 33 | FC2-4174411 | recent | sampled:recent | dual_reference | 2 | sukebei confirmed / netflav confirmed |
| 34 | FC2-4266906 | recent | sampled:recent | dual_reference | 2 | sukebei confirmed / netflav confirmed |
| 35 | FC2-4336025 | recent | sampled:recent | dual_reference | 2 | sukebei confirmed / netflav confirmed |
| 36 | FC2-4385140 | recent | sampled:recent | dual_reference | 2 | sukebei confirmed / netflav confirmed |
| 37 | FC2-4493606 | recent | sampled:recent | dual_reference | 2 | sukebei confirmed / netflav confirmed |
| 38 | FC2-4499275 | recent | sampled:recent | dual_reference | 2 | sukebei confirmed / netflav confirmed |
| 39 | FC2-4547366 | recent | sampled:recent | dual_reference | 2 | sukebei confirmed / netflav confirmed |
| 40 | FC2-4548410 | recent | sampled:recent | dual_reference | 2 | sukebei confirmed / netflav confirmed |
| 41 | FC2-4655045 | recent | sampled:recent | dual_reference | 2 | sukebei confirmed / netflav confirmed |
| 42 | FC2-4699133 | recent | sampled:recent | dual_reference | 2 | sukebei confirmed / netflav confirmed |
| 43 | FC2-4791899 | recent | sampled:recent | dual_reference | 2 | sukebei confirmed / netflav confirmed |
| 44 | FC2-4824605 | recent | phase2_frozen | phase2_mandatory | 2 | sukebei confirmed / netflav confirmed |
| 45 | FC2-4825061 | recent | phase2_frozen | phase2_mandatory | 2 | sukebei confirmed / netflav confirmed |
| 46 | FC2-4835063 | recent | sampled:recent | dual_reference | 2 | sukebei confirmed / netflav confirmed |
| 47 | FC2-4972767 | recent | phase2_frozen | phase2_mandatory | 0 | sukebei negative / netflav negative |
| 48 | FC2-4976588 | recent | phase2_frozen | phase2_mandatory | 0 | sukebei negative / netflav negative |
| 49 | FC2-4978035 | recent | phase2_frozen | phase2_mandatory | 1 | sukebei confirmed / netflav negative |
| 50 | FC2-4979299 | recent | phase2_frozen | phase2_mandatory | 1 | sukebei confirmed / netflav negative |

## 5. 现行规则

* 本集合**永不**因结果而更改。未覆盖的 ID 不被替换，也不增加第 51 个 ID。
* 之后被发现并非真实 FC2 产品的 ID 仍留在 primary 分母中，并以
  *invalid-set-item investigation* 形式记录；只有独立复查者可以允许一轮数据集修正。
* primary gate（`tools/run_50id_coverage_gate.py --run-kind primary`）只运行**一次**，且须在 HEAD
  包含这个已提交集合的干净工作树上运行；其结果即正式的分子 / 分母。诊断性重跑单独
  记录，且永不取代它。
