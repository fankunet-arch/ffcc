# PHASE2_PROBE_SET.md

状态：**POPULATED**（2026-09-20 UTC）。

用于评判每个候选来源的 known-valid FC2 编号。每一行的依据都可独立核查：它列出解析出该编号的在线来源，时间戳见 JSON 证据文件。没有任何编号是猜测的；在没有其他来源解析出同一编号的情况下，从不把某个候选来源的 404/无命中解读为“来源不可用”。

| # | Canonical number | 认定为 known-valid 的理由（独立证据） | 被已采用适配器解析（Gate run 2026-09-20 13:02-13:03 UTC） |
|---|---|---|---|
| 1 | `FC2-4825061` | 规格书指定，**且经独立佐证**：JavDB 列出了它（`【顔出し】ハーフ美人妻 ...`，2026-01-02，176 个评分），123AV 提供详情页（发行日 2026-01-02）。FC2 Official 无法佐证（登录墙）。fc2db.net 对它返回 404，这是该来源的覆盖缺口，不是无效的证据。 | javdb, av123 |
| 2 | `FC2-4824605` | 规格书指定，**且经独立佐证**：fc2db.net 提供完整页面（`※1/11まで初回限定90％OFF※【ハメ撮り】...`，2026-01-04）。人工还在 Sukebei 种子、Netflav 和 Jav Guru 上看到其标题（未由适配器记录）。JavDB（只有近似命中）与 123AV（404）没有收录它。 | fc2db_net |
| 3 | `FC2-4979299` | 在 fc2db.net 首页作品列表中看到（2026-09-19 发行）；随后在全部三个已采用来源上 SUCCESS，fc2db_net 与 javdb 上的日文标题相同。 | fc2db_net, javdb, av123 |
| 4 | `FC2-4976588` | 在 fc2db.net 首页作品列表中看到；在 fc2db_net 与 javdb 上 SUCCESS，标题一致。 | fc2db_net, javdb |
| 5 | `FC2-1042815` | 从 fc2db.net 首页选作 **old-id** 对照（约 1M 区间）；在 fc2db_net 与 javdb 上 SUCCESS（日文标题一致）；在 fc2cm.com 上也能解析（人工，section 5）。 | fc2db_net, javdb |
| 6 | `FC2-4978035` | 在 fc2db.net 首页作品列表中看到；在全部三个已采用来源上 SUCCESS。 | fc2db_net, javdb, av123 |
| 7 | `FC2-4972767` | 在 fc2db.net 首页作品列表中看到；在 fc2db_net 与 javdb 上 SUCCESS，标题一致。 | fc2db_net, javdb |

## 有意排除

- `FC2-4974437`：只被 fc2db.net 解析，而其标题是类似占位符的 `Searching for Your XXX`；JavDB 无精确命中，123AV 返回 404。未获第二个来源佐证，因此**不**在 probe 集合中（保留在证据 JSON 中：fc2db_net run 12:52:57）。
- `FC2-9999999` / `FC2-99999999` / `FC2-4000000`：仅用作否定对照，以观察各站点“缺失”页面的格式，从不作为有效性证据。

## 集合的构建方式

1. 先用两个指定编号探测每个候选来源。
2. 其他编号取自 fc2db.net 首页当前的作品列表（近期作品，2026 年九月），外加一个 old-id 对照，然后要求至少被两个已采用来源解析，或（对两个指定编号而言）至少被提示词之外的一个独立来源解析。
3. 随后对整个集合一次性运行每个已采用适配器（见各 `docs/sources/SOURCE_VIABILITY_<id>.md`）。
