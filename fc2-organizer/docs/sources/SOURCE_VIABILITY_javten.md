# SOURCE_VIABILITY - javten

- **提供方：** JavTen (javten.com)
- **状态：** `BLOCKED`
- **决定：** REJECT - Cloudflare challenge
- **适配器：** 无
- **是否需要登录/cookie：** 未知
- **Cloudflare/反爬：** **是**
- **调研日期：** 2026-09-20 (UTC)；机器证据 `docs/source-probes/PHASE2_PROBE_20260920.json`，人工观察 `docs/source-probes/PHASE2_MANUAL_OBSERVATIONS_20260920.md`。

## 摘要

整个站点（`/`、`/fc2`、`/search?q=...`）返回 HTTP 403；搜索请求带有 `cf-mitigated: challenge` / `Just a moment...`。

## Raw 探测证据（最后一轮，`tools/probe_sources.py raw`）

| UTC | 请求 URL | HTTP | 页面 `<title>` | cf-mitigated | 最终 URL | 传输错误 |
|---|---|---|---|---|---|---|
| 12:58:29 | `https://javten.com/search?q=FC2-PPV-4825061` | 403 | `Just a moment...` | challenge | same |  |

## 发现

- 规格书的初始候选列表中列出了它（'FC2DB/JavTen'）；今天的证据为 BLOCKED。

## 风险 / 重新检查触发条件

若 challenge 被撤掉则重新检查。
