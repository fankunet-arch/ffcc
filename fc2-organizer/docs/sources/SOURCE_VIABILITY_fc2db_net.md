# SOURCE_VIABILITY - fc2db_net

- **提供方：** FC2DB (fc2db.net)
- **状态：** `VERIFIED`
- **决定：** ADOPT
- **适配器：** `fc2_metadata_core.sources.adapters.fc2db_net.Fc2dbNetAdapter`
- **是否需要登录/cookie：** 不需要
- **Cloudflare/反爬：** 存在 Cloudflare CDN（`cf-ray`），任何请求中均未观察到 challenge；若出现 challenge 将映射为 `BLOCKED`，绝不绕过
- **调研日期：** 2026-09-20 (UTC)；机器证据 `docs/source-probes/PHASE2_PROBE_20260920.json`，人工观察 `docs/source-probes/PHASE2_MANUAL_OBSERVATIONS_20260920.md`。

## 摘要

每个作品在 `/work/<digits>/` 有一个服务端渲染的 WordPress 页面。缺失作品返回干净的 HTTP 404（`作品が削除されたか存在しません`）。三个来源中信息最丰富：日文标题、演员、卖家、发行日期、时长、标签、封面。

## Raw 探测证据（最后一轮，`tools/probe_sources.py raw`）

| UTC | 请求 URL | HTTP | 页面 `<title>` | cf-mitigated | 最终 URL | 传输错误 |
|---|---|---|---|---|---|---|
| 12:57:48 | `https://fc2db.net/work/4825061/` | 404 | `ページが見つかりませんでした &#8211; FC2DB` | - | same |  |
| 12:57:51 | `https://fc2db.net/work/4824605/` | 200 | `※1/11まで初回限定90％OFF※【ハメ撮り】スレンダー美人の人妻に種付け中出し調教 &#8211; FC2DB` | - | same |  |

## 发现

- 字段：number+title 取自 `<h1>[FC2-PPV-N] Title</h1>`；release/runtime/actors/publisher（卖家）/thumbnail 取自页面的 schema.org `VideoObject` JSON-LD；tags 取自 `/work-tags/` 链接。在适配器中，除 number/title 外一切均为可选。
- 页面上的 `商品ID` 等于 FC2 编号，因此会将页面编号与请求核对（不一致时给出 `INVALID_RESPONSE`，绝不静默 SUCCESS）。
- 姊妹站 `fc2db.com` 位于 Cloudflare challenge（403）之后，未被使用；若运营方域名再次变更，适配器的 `base_url` 可配置（站点自身的 markup 中带有 URL 迁移横幅）。
- 在 7-ID probe 集合上的覆盖：6/7（只缺 `FC2-4825061`，而 JavDB 与 123AV 有它）。
- 并非 FC2 官方服务（其页脚如此声明）；标题复制自 FC2 Content Market。

## 适配器验证（Phase 2 Gate run，`tools/probe_sources.py adapter --source fc2db_net`，代码 `3a21c4b`）

通过 `HttpxTransport` 发出真实 HTTP，每次查询一个请求，查询间隔约 2.5 s，不带 cookies。`SUCCESS` 表示适配器的 `SourceResult` 满足最低成功条件（canonical number + 非空标题）。

| UTC | 编号 | HTTP | SourceStatus | 标题（节选） | 已填充字段 |
|---|---|---|---|---|---|
| 13:02:27 | FC2-4825061 | 404 | **not_found** |  |  |
| 13:02:30 | FC2-4824605 | 200 | **success** | ※1/11まで初回限定90％OFF※【ハメ撮り】スレンダー美人の人妻に種付け中出し調教 | number, title, publisher, release, runtime, actors, tags, thumb_urls, source_urls |
| 13:02:34 | FC2-4979299 | 200 | **success** | 夢は小学校の先生。天使のような笑顔と色白美巨乳♡ほのぼの系美女のおじさま２人への体当たり性指導映 | number, title, publisher, release, runtime, actors, tags, thumb_urls, source_urls |
| 13:02:37 | FC2-4976588 | 200 | **success** | ※表に出す予定はなかった映像※ 元有名キッズモデル18才 | number, title, publisher, release, runtime, actors, tags, thumb_urls, source_urls |
| 13:02:40 | FC2-1042815 | 200 | **success** | 【半額】【**JD】うた（20）【眼鏡っこ激イキ編】吸引力が凄いフェラ！おまんこの締め付けとハメ | number, title, publisher, release, runtime, actors, tags, thumb_urls, source_urls |
| 13:02:43 | FC2-4978035 | 200 | **success** | 【廃版】超有名テレビ局の美女A（元女子アナのFカップ美巨乳） | number, title, publisher, release, runtime, actors, thumb_urls, source_urls |
| 13:02:47 | FC2-4972767 | 200 | **success** | ※在庫限り※身長133cm 18歳。日本×ボリビアの芸能界最小ハーフモデル。衝撃の体格差1.3倍 | number, title, publisher, release, runtime, actors, tags, thumb_urls, source_urls |

更早一次在代码 `45be2b7` 上的相同运行（13:00:30-13:01:38）得到了相同结果，唯一例外是 `FC2-4978035` 上一次瞬时 `network_error`（超时）；见人工观察 section 10。

**Gate 结果：** 6 个 known-valid ID 返回 `SUCCESS`（FC2-4824605, FC2-4979299, FC2-4976588, FC2-1042815, FC2-4978035, FC2-4972767）；要求为 >=2。

## 要求核对清单

| 要求（规格书 section 11 / Phase 2） | 满足 |
|---|---|
| 真实 HTTP 请求（非 mock） | 是 |
| 正式适配器确实被执行 | 是 |
| >=2 个不同的 known-valid ID 返回带编号 + 非空标题的 `SUCCESS` | 是（6） |
| 无私有登录 / cookie | 是 |
| 无 CAPTCHA / Cloudflare 绕过 | 是（未做任何尝试；challenge 映射为 `BLOCKED`） |
| 离线解析器 + 契约测试 | 是（`tests/unit/sources/adapters/test_adapter_fc2db_net.py`，真实响应 fixture 位于 `tests/fixtures/sources/` 下） |

## 风险 / 重新检查触发条件

单一运营方，无 SLA，无 API 契约；布局变化会破坏正则（离线 fixture 固定了当前的 markup）。未来若出现 Cloudflare challenge 将给出 `BLOCKED`。
