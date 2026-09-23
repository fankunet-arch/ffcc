# Phase 3 C3 — 候选池 v2（已冻结）

机器可读候选池：`docs/acceptance/PHASE3_CANDIDATE_POOL.json`。本文件是它的人类可读摘要。
候选池由添加这两个文件的提交冻结；正式 50-ID 选取器只读取该已提交的 JSON。

| 项目 | 值 |
|---|---|
| 候选池 `schema_version` | **2** |
| 流程 / 构建器 | `PHASE3-CANDIDATE-POOL-v2` — `tools/build_candidate_pool.py`（三态查询、一次礼貌性重试、前缀完整性守卫） |
| 创建时间（UTC） | 2026-09-20T21:25:38+00:00 |
| **候选池 JSON SHA-256**（审计文件，CRLF 行尾，139,732 字节） | `ffe0b095793a914c9c12cc5af97f220244d4534853d761b523821d5ac0fd4cb9` |
| git 中存储的候选池 JSON SHA-256（LF 行尾，135,276 字节） | `48e8300031f855e995114c30bf815843d5c61bcdcff42492803766b5b95a82e2` |
| C3 Code Head v2（构建器 / 选取器 / gate runner） | `578ed56aff9e3b823b39da74dc0fc10dae63456c` |
| C3 Selection Method v2 Head | `3e7bd2ed1436b27f24c09e9e71dd71907c141df8` |
| 历史 Code Head v1 / Method v1 Head | `5ad00e525d72759dcff3ae0458a90d8f3b6ac464` / `74c98659394223642a41a1e78a9fae7011ba7f00` |
| 候选池冻结时的正式 50-ID 选取器 | **NOT RUN** |
| 候选池冻结时的 50-ID 集合 | **NOT FROZEN** |
| 候选池冻结时的 primary 覆盖 gate | **NOT RUN** |
| 候选池构建期间使用的聚合引擎 / 适配器 | **NO** |
| 候选池中源自引擎的数据 | **NONE** |

**两个哈希，同一内容。** 构建器在 Windows 上运行，其 Python 写出 `\r\n`；因此经审计的磁盘文件
为 CRLF（哈希 `ffe0b095…`）。本仓库以 `core.autocrlf=true` 签入，因此 git 以 LF 行尾存储相同
内容（哈希 `48e83000…`，恰为审计字节做 CRLF→LF 规范化后的结果）。
Windows 上的 checkout 复现第一个哈希，Linux 上的 checkout / `git show` 复现第二个。两者之间
没有其他差异。该文件在审计与冻结之间未被编辑。

## 1. 内容

| 度量 | 值 |
|---|---|
| 候选总数 | **167** |
| 枚举所得（reference 1 = sukebei 种子名称列表，再由 reference 2 = netflav 佐证） | 160 |
| Phase 2 强制 ID | 7（7 / 7 在池中） |
| 重复的 canonical ID | 0 |
| 所有编号均为 canonical | PASS |
| 前缀枚举完成 | **40 / 40**（前缀 `10` … `49`），unavailable **0**，每前缀 `PER_PREFIX = 4` |
| 各数值分段候选数（全部 167 个） | older 41 · middle 80 · recent 46 |

## 2. 请求核算

| 度量 | 值 |
|---|---|
| 发出请求数 | **214**（初始 214，重试 **0**） |
| 构成 | 40 次前缀查询 + 160 次 netflav 查询 + 7 个 Phase 2 ID 的 14 次查询（7 次 sukebei，7 次 netflav） |
| 无法解释的失败 / 未核算的请求 | **0** |
| 三态候选级 check（174 = 167 × 2 − 160 个与前缀查询共享的 check） | confirmed **74** · negative **100** · unavailable **0** |
| netflav（167 次查询） | confirmed 70 · negative 97 · unavailable 0 |
| sukebei 直接查询（7 个强制 ID） | confirmed 4 · negative 3 · unavailable 0 |

`negative` 表示收到了有效响应但无精确证据；`unavailable`（timeout、连接错误、
HTTP 403 / 429 / 5xx 或其他 non-200、不可用的响应体）单独记录，永不记为 `negative`。本次构建
没有任何 unavailable 查询，因此无需重试。

## 3. 验证强度

**只按 confirmed 外部参考**计数（sukebei、netflav 精确 code 匹配）。Phase 2 出处
在强制 ID 的 `validity_sources` 中列出，但**永不**计入 `external_reference_count`。

| 强度 | 候选数 | 其中强制 ID |
|---|---|---|
| ≥ 2 个外部参考（dual） | **70** | FC2-4824605, FC2-4825061 |
| 恰好 1 个外部参考（single） | **94** | FC2-4978035, FC2-4979299（sukebei confirmed；netflav negative） |
| 0 个外部参考——**仅有出处的强制 ID** | **3** | FC2-1042815, FC2-4972767, FC2-4976588 |

### 仅有出处的强制 ID

`FC2-1042815`、`FC2-4972767` 与 `FC2-4976588` 的 `external_reference_count = 0`：两个外部参考都
返回了**有效响应但无精确匹配**（sukebei **与** netflav 均为 `negative`）——它们*并非*
unavailable。它们留在候选池中，并且对 50-ID 集合是强制的，仅因为它们属于
Phase 2 冻结 probe 集合。它们是**仅有出处**的 ID；既不是双参考也不是单参考，
永不具备抽样资格。

## 4. Method v2 下的资格（非冻结候选）

| 分段 | 区间 | Tier 1（≥ 2） | Tier 2（= 1） | 零参考 | 合格（tier 1 + tier 2） | 配额 |
|---|---|---|---|---|---|---|
| older | < 2,000,000 | 9 | 31 | 0 | **40** | 14 |
| middle | 2,000,000 – 3,999,999 | 34 | 46 | 0 | **80** | 15 |
| recent | ≥ 4,000,000 | 25 | 15 | 0 | **40** | 14 |

每个分段都能达到配额。（选取器的结果——选中哪些候选——不属于本文件，
并且在候选池冻结时尚未计算。）

## 5. 历史：Attempt 1 从未冻结

较早一次使用 v1 构建器的构建（创建于 2026-09-20T20:59:28Z，文件 sha256
`098fc71755d24064802d8ced77f5ad4a66082b7590bec42915fcdfdc62416bfa`）**未通过审计**，且**从未提交或
冻结**：167 个候选，46 个 dual / 118 个 single，各分段 dual 数 older 9（需要 14）· middle 34 · recent 2（需要 14），并且
其 214 次请求中有 41 次失败却被记录为“未确认”，与真正的否定结果无法区分。它
仅作为 job 临时目录证据保留；选取器未在其上运行。该失败导致了记录在
`docs/acceptance/PHASE3_50_ID_SELECTION_METHOD.md`（Amendment v2）中的选取前修订以及构建器 v2。**本候选池
使用构建器 v2 从零重建，未复用任何 Attempt 1 数据。**

## 6. 审计结果

只读候选池审计：**PASS**——schema 2；JSON 可解析；所有编号均为 canonical；无重复；7 / 7 个强制 ID；
40 / 40 个前缀枚举完成；每个 check 都是 confirmed / negative / unavailable 之一；每次请求都已
核算；不存在 `unavailable` 查询（因此无重试预算违规），且没有任何 confirmed / negative 查询被重试；
构建器既不 import 聚合引擎，也不 import 来源适配器或 HTTP transport；文件不含任何
源自聚合的字段，也不含任何响应体、cookie、authorization 或私有 header。
