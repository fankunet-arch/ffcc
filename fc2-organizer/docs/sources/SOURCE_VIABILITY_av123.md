# SOURCE_VIABILITY - av123

- **提供方：** 123AV (123av.com)
- **状态：** `VERIFIED`
- **决定：** ADOPT
- **适配器：** `fc2_metadata_core.sources.adapters.av123.Av123Adapter`
- **是否需要登录/cookie：** 不需要
- **Cloudflare/反爬：** 存在 Cloudflare CDN，未观察到 challenge；若出现 challenge 将映射为 `BLOCKED`
- **调研日期：** 2026-09-20 (UTC)；机器证据 `docs/source-probes/PHASE2_PROBE_20260920.json`，人工观察 `docs/source-probes/PHASE2_MANUAL_OBSERVATIONS_20260920.md`。

## 摘要

每个作品在 `/en/v/fc2-ppv-<digits>` 有一个服务端渲染的详情页；缺失作品返回干净的 HTTP 404。它与 FC2DB 互补而非镜像：它收录了 FC2DB 没有的作品，反之亦然。

## Raw 探测证据（最后一轮，`tools/probe_sources.py raw`）

| UTC | 请求 URL | HTTP | 页面 `<title>` | cf-mitigated | 最终 URL | 传输错误 |
|---|---|---|---|---|---|---|
| 12:57:55 | `https://123av.com/en/v/fc2-ppv-4825061` | 200 | `FC2-PPV-4825061 — [Face Revealed] Half-Japanese Beautiful Wi` | - | same |  |
| 12:57:57 | `https://123av.com/en/v/fc2-ppv-4824605` | 404 | `404 — 123AV` | - | same |  |

## 发现

- 字段：number+title 取自 `<h1 class="watch__title">FC2-PPV-N — Title</h1>`；发行日期、时长和类型取自 Details `<dl>`。
- 标题是该站点的**英文**版本（机器翻译），而非日文原文；记录此点以便 Phase 3 在 `title` 上给它低于日文来源的权重。Maker 始终是通用的 `FC2`，因此有意不映射到 `studio`/`publisher`。页面上没有封面或演员（`og:image` 是站点 logo）。
- `<title>` 标签对实体做了双重编码（`&amp;#039;`）；适配器改为读取 `<h1>`，其解码正确。
- 在 7-ID probe 集合上的覆盖：3/7（`4825061`、`4979299`、`4978035`）。三者中覆盖最弱：是补充来源，而非主要来源。

## 适配器验证（Phase 2 Gate run，`tools/probe_sources.py adapter --source av123`，代码 `3a21c4b`）

通过 `HttpxTransport` 发出真实 HTTP，每次查询一个请求，查询间隔约 2.5 s，不带 cookies。`SUCCESS` 表示适配器的 `SourceResult` 满足最低成功条件（canonical number + 非空标题）。

| UTC | 编号 | HTTP | SourceStatus | 标题（节选） | 已填充字段 |
|---|---|---|---|---|---|
| 13:02:47 | FC2-4825061 | 200 | **success** | [Face Revealed] Half-Japanese Beautiful Wife's F | number, title, release, runtime, tags, source_urls |
| 13:02:50 | FC2-4824605 | 404 | **not_found** |  |  |
| 13:02:53 | FC2-4979299 | 200 | **success** | Her dream is to be an elementary school teacher. | number, title, release, runtime, tags, source_urls |
| 13:02:56 | FC2-4976588 | 404 | **not_found** |  |  |
| 13:02:58 | FC2-1042815 | 404 | **not_found** |  |  |
| 13:03:01 | FC2-4978035 | 200 | **success** | [Discontinued] A beautiful woman from a very fam | number, title, release, tags, source_urls |
| 13:03:04 | FC2-4972767 | 404 | **not_found** |  |  |

更早一次在代码 `45be2b7` 上的相同运行（13:00:30-13:01:38）得到了相同结果。

**Gate 结果：** 3 个 known-valid ID 返回 `SUCCESS`（FC2-4825061, FC2-4979299, FC2-4978035）；要求为 >=2。

## 要求核对清单

| 要求（规格书 section 11 / Phase 2） | 满足 |
|---|---|
| 真实 HTTP 请求（非 mock） | 是 |
| 正式适配器确实被执行 | 是 |
| >=2 个不同的 known-valid ID 返回带编号 + 非空标题的 `SUCCESS` | 是（3） |
| 无私有登录 / cookie | 是 |
| 无 CAPTCHA / Cloudflare 绕过 | 是（未做任何尝试；challenge 映射为 `BLOCKED`） |
| 离线解析器 + 契约测试 | 是（`tests/unit/sources/adapters/test_adapter_av123.py`，真实响应 fixture 位于 `tests/fixtures/sources/` 下） |

## 风险 / 重新检查触发条件

流媒体站点运营方；域名很可能变动（`base_url` 可配置）。对小众/较旧作品的覆盖低。
