# SOURCE_VIABILITY - javdb

- **提供方：** JavDB (javdb.com) - 仅公开搜索列表
- **状态：** `VERIFIED`
- **决定：** ADOPT（仅搜索列表；部分字段）
- **适配器：** `fc2_metadata_core.sources.adapters.javdb.JavdbAdapter`
- **是否需要登录/cookie：** 搜索列表不需要（详情页需要登录，且从不请求）
- **Cloudflare/反爬：** 存在 Cloudflare CDN，未观察到 challenge；challenge 或 `/login` 重定向映射为 `BLOCKED`
- **调研日期：** 2026-09-20 (UTC)；机器证据 `docs/source-probes/PHASE2_PROBE_20260920.json`，人工观察 `docs/source-probes/PHASE2_MANUAL_OBSERVATIONS_20260920.md`。

## 摘要

`/search?q=FC2-PPV-<digits>` 是公开的服务端渲染列表，每个命中带有编号、日文标题、发行日期和封面 URL。**详情页重定向到 `/login`**，因此该来源有意不提供 actors/tags/runtime。

## Raw 探测证据（最后一轮，`tools/probe_sources.py raw`）

| UTC | 请求 URL | HTTP | 页面 `<title>` | cf-mitigated | 最终 URL | 传输错误 |
|---|---|---|---|---|---|---|
| 12:58:00 | `https://javdb.com/search?q=FC2-PPV-4825061` | 200 | `JavDB 成人影片數據庫` | - | same |  |
| 12:58:02 | `https://javdb.com/search?q=FC2-PPV-4824605` | 200 | `JavDB 成人影片數據庫` | - | same |  |
| 12:58:04 | `https://javdb.com/v/82ZNYd` | 200 | `登入 / JavDB 成人影片數據庫` | - | `https://javdb.com/login` |  |

## 发现

- 搜索是模糊的（`4825061` 还会返回 `FC2-1825061`；`4824605` 只返回无关的 `FC2-1824605`/`FC2-4724605`）。适配器**只**接受编号与请求相等的命中，否则为 `NOT_FOUND`。已在线验证：尽管页面列出了两个近似命中，`FC2-4824605` 仍给出 `NOT_FOUND`。
- 零结果页面带有 `<div class="empty-message">暫無內容</div>`；既无结果列表也无该标记的 200 页面判为 `INVALID_RESPONSE`，而非 `NOT_FOUND`。
- 详情页重定向：`302 https://javdb.com/v/82ZNYd` 到 `https://javdb.com/login`（人工观察 section 3）。
- 在 7-ID probe 集合上的覆盖：6/7（只缺 `FC2-4824605`）。
- 返回字段：编号、标题、发行日期、封面缩略图、来源 URL、JavDB 视频 id（`external_ids['javdb']`）。

## 适配器验证（Phase 2 Gate run，`tools/probe_sources.py adapter --source javdb`，代码 `3a21c4b`）

通过 `HttpxTransport` 发出真实 HTTP，每次查询一个请求，查询间隔约 2.5 s，不带 cookies。`SUCCESS` 表示适配器的 `SourceResult` 满足最低成功条件（canonical number + 非空标题）。

| UTC | 编号 | HTTP | SourceStatus | 标题（节选） | 已填充字段 |
|---|---|---|---|---|---|
| 13:03:04 | FC2-4825061 | 200 | **success** | 【顔出し】ハーフ美人妻 最初で最後の顔出し未公開動画×2本 ※SNS認証者限定 | number, title, release, thumb_urls, source_urls, external_ids |
| 13:03:07 | FC2-4824605 | 200 | **not_found** |  |  |
| 13:03:10 | FC2-4979299 | 200 | **success** | 夢は小学校の先生。天使のような笑顔と色白美巨乳♡ほのぼの系美女のおじさま２人への体当たり性指導映 | number, title, release, thumb_urls, source_urls, external_ids |
| 13:03:13 | FC2-4976588 | 200 | **success** | 表に出す予定はなかった映像※ 元有名キッズモデル18才 ''139cm/Fカップ''の神得体に容 | number, title, release, thumb_urls, source_urls, external_ids |
| 13:03:16 | FC2-1042815 | 200 | **success** | 【50％オフ】【20歳のビッチ×眼鏡】うた【眼鏡っこ激イキ編】吸引力が凄いフェラ！おまんこの締め | number, title, release, thumb_urls, source_urls, external_ids |
| 13:03:18 | FC2-4978035 | 200 | **success** | 【廃版】大手テレビ局の美女アナウンサーA（元女子アナのFカップ美巨乳） | number, title, release, thumb_urls, source_urls, external_ids |
| 13:03:21 | FC2-4972767 | 200 | **success** | 身長133cm 18歳。日本×ボリビアの芸能界最小ハーフモデル。衝撃の体格差1.3倍！破壊寸前ま | number, title, release, thumb_urls, source_urls, external_ids |

更早一次在代码 `45be2b7` 上的相同运行（13:00:30-13:01:38）得到了相同结果。

**Gate 结果：** 6 个 known-valid ID 返回 `SUCCESS`（FC2-4825061, FC2-4979299, FC2-4976588, FC2-1042815, FC2-4978035, FC2-4972767）；要求为 >=2。

## 要求核对清单

| 要求（规格书 section 11 / Phase 2） | 满足 |
|---|---|
| 真实 HTTP 请求（非 mock） | 是 |
| 正式适配器确实被执行 | 是 |
| >=2 个不同的 known-valid ID 返回带编号 + 非空标题的 `SUCCESS` | 是（6） |
| 无私有登录 / cookie | 是 |
| 无 CAPTCHA / Cloudflare 绕过 | 是（未做任何尝试；challenge 映射为 `BLOCKED`） |
| 离线解析器 + 契约测试 | 是（`tests/unit/sources/adapters/test_adapter_javdb.py`，真实响应 fixture 位于 `tests/fixtures/sources/` 下） |

## 风险 / 重新检查触发条件

三者中最可能限流或引入登录/年龄验证的一个；适配器每次查询恰好发出一个请求，Phase 3 必须加入按主机的节流。该适配器每次查询读取一个公开页面，不用于批量爬取。
