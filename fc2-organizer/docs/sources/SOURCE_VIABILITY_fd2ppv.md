# SOURCE_VIABILITY - fd2ppv

- **提供方：** FD2 (fd2ppv.cc)
- **状态：** `BLOCKED`
- **决定：** REJECT - 作品页有 Cloudflare challenge
- **适配器：** 无
- **是否需要登录/cookie：** 未知（从未到达作品页）
- **Cloudflare/反爬：** **是** - 每个 `/articles/<id>` 与 `/search` 上都有 `cf-mitigated: challenge` / `Just a moment...`
- **调研日期：** 2026-09-20 (UTC)；机器证据 `docs/source-probes/PHASE2_PROBE_20260920.json`，人工观察 `docs/source-probes/PHASE2_MANUAL_OBSERVATIONS_20260920.md`。

## 摘要

站点存活，其列表页（`/`）公开，但每个单作品页都返回 Cloudflare managed challenge（HTTP 403）。去解它就构成绕过，而 Phase 2 禁止绕过。

## Raw 探测证据（最后一轮，`tools/probe_sources.py raw`）

| UTC | 请求 URL | HTTP | 页面 `<title>` | cf-mitigated | 最终 URL | 传输错误 |
|---|---|---|---|---|---|---|
| 12:58:07 | `https://fd2ppv.cc/` | 200 | `All Works - FD2` | - | same |  |
| 12:58:09 | `https://fd2ppv.cc/articles/4825061` | 403 | `Just a moment...` | challenge | same |  |
| 12:58:11 | `https://fd2ppv.cc/articles/4824605` | 403 | `Just a moment...` | challenge | same |  |

## 发现

- `/` 返回 200 `All Works - FD2`，链接到近期作品的 `/articles/<id>`，因此 id 等于 FC2 编号。
- `/articles/4825061`、`/articles/4824605`（以及人工检查中的 `/articles/4979786`、`/articles/4979799`）返回 403 challenge。`/search?q=...` 重定向到 `/actresses/?keyword=`，同样被 challenge。
- 规格书的初始候选列表列出了 FD2PPV；今天的证据为 BLOCKED。

## 风险 / 重新检查触发条件

若站点撤掉 challenge 或发布 API，则重新检查。
