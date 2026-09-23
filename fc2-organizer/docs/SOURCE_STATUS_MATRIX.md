# SOURCE_STATUS_MATRIX.md

状态：**POPULATED** - 每一行都来自记录在
`docs/source-probes/PHASE2_PROBE_20260920.json` 中、并在 `docs/sources/SOURCE_VIABILITY_<id>.md` 中详述的在线探测。
这里没有任何内容来自搜索摘要、记忆中的名称，或“规格书中提到的站点仍然在线”的假设。

## 列说明

| 列 | 含义 |
|---|---|
| Source ID | 稳定的逻辑 id（`SourceAdapter.source_id`）；不随镜像域名变化。 |
| Provider | 人类可读的提供方/站点。 |
| Status | `VERIFIED`、`PARTIAL`、`BLOCKED`、`RATE_LIMITED`、`DEAD`、`REJECTED`、`EXPERIMENTAL`。 |
| Verified IDs | 在 Gate run 中经真实适配器返回 `SourceStatus.SUCCESS`（编号 + 非空标题）的 probe 集合编号。`-` = 无适配器。 |
| Cookie | 查询是否需要私有 cookie/登录。 |
| CF | 查询路径上是否观察到 Cloudflare/反爬 challenge。 |
| Adopted | 是否存在真实的 `SourceAdapter`。 |

## 状态矩阵

| Source ID | Provider | Status | Verified IDs | Cookie | CF | Adopted |
|---|---|---|---|---|---|---|
| `fc2db_net` | FC2DB (fc2db.net) | **VERIFIED** | 4824605, 4979299, 4976588, 1042815, 4978035, 4972767 | 不需要 | 否 | 是 |
| `javdb` | JavDB (javdb.com) - 仅公开搜索列表 | **VERIFIED** | 4825061, 4979299, 4976588, 1042815, 4978035, 4972767 | 不需要（搜索列表） | 否 | 是 |
| `av123` | 123AV (123av.com) | **VERIFIED** | 4825061, 4979299, 4978035 | 不需要 | 否 | 是 |
| `fc2_official` | FC2 Content Market (adult.contents.fc2.com) | **BLOCKED** | - | **需要登录** | 否 | 否 |
| `fd2ppv` | FD2 (fd2ppv.cc) | **BLOCKED** | - | 未知 | **是**（作品页） | 否 |
| `fc2db_com` | FC2DB (fc2db.com - `.com` 姊妹站) | **BLOCKED** | - | 未知 | **是** | 否 |
| `javten` | JavTen (javten.com) | **BLOCKED** | - | 未知 | **是** | 否 |
| `supjav_missav` | SupJav (supjav.com) 与 MissAV (missav.ws) | **BLOCKED** | - | 未知 | **是** | 否 |
| `fc2ppvdb` | FC2PPVDB (fc2ppvdb.com) | **BLOCKED** | - | 未知 | n/a（此处 IP 被封） | 否 |
| `onejav` | OneJAV (onejav.com) | **BLOCKED** | - | 未知 | n/a（此处 IP 被封） | 否 |
| `fc2cm` | FC2CM (fc2cm.com；规格书名称 'FC2CMADB') | **PARTIAL** | - | 不需要 | 否 | 否 |
| `javbus` | JavBus (www.javbus.com) | **BLOCKED** | - | 年龄验证 cookie | 否（年龄验证） | 否 |
| `netflav` | Netflav (netflav.com) | **EXPERIMENTAL** | - | 不需要 | 否 | 否 |
| `jav_guru` | Jav Guru (jav.guru) | **REJECTED** | - | 不需要 | 否 | 否 |
| `sukebei_nyaa` | Sukebei (sukebei.nyaa.si) | **REJECTED** | - | 不需要 | 否 | 否 |

## Gate 摘要

- 调查的提供方条目：**15** 个（fc2db.com 是 fc2db.net 的姊妹站；supjav/missav 共用一行）。满足 >=5 的下限；达到了 >=3 VERIFIED。
- **VERIFIED：3** 个（`fc2db_net`、`javdb`、`av123`）：运营方与主机彼此独立，页面格式各不相同。Phase 2 Gate 需要 >=2；3 个的强目标已达成。
- FC2 Official 确实做了调查，结果为 **BLOCKED（登录墙）**；除三个已采用来源外，还调查了若干聚合/索引类候选。
- 两个候选（`fc2ppvdb`、`onejav`）因本网络存在 ISP 级 IP 封锁而无法评估；它们是*未验证*，而非失效。应在 Phase 3 确定来源列表前从其他网络重新探测。
- 独立性说明：三者最终都镜像 FC2 Content Market 数据，且三者都位于 Cloudflare 的 CDN 之后。它们是独立的*服务*，而非独立的*源头*；Cloudflare 范围的故障或 FC2 的下架潮会同时影响三者。Phase 3 应记住 FC2 Official（需登录）及其他已记录的备选来源。

## Gate run 中的逐 ID 覆盖（7-ID probe 集合）

| ID | fc2db_net | javdb | av123 |
|---|---|---|---|
| FC2-4825061 | NOT_FOUND | SUCCESS | SUCCESS |
| FC2-4824605 | SUCCESS | NOT_FOUND | NOT_FOUND |
| FC2-4979299 | SUCCESS | SUCCESS | SUCCESS |
| FC2-4976588 | SUCCESS | SUCCESS | NOT_FOUND |
| FC2-1042815 | SUCCESS | SUCCESS | NOT_FOUND |
| FC2-4978035 | SUCCESS | SUCCESS | SUCCESS |
| FC2-4972767 | SUCCESS | SUCCESS | NOT_FOUND |

此处的 `NOT_FOUND` 是各站点自身的回答（真实的 404 或无精确命中），从不是传输失败。
