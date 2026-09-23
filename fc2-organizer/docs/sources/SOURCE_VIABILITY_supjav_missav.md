# SOURCE_VIABILITY - supjav_missav

- **提供方：** SupJav (supjav.com) 与 MissAV (missav.ws)
- **状态：** `BLOCKED`
- **决定：** REJECT - Cloudflare challenge
- **适配器：** 无
- **是否需要登录/cookie：** 未知
- **Cloudflare/反爬：** **是**
- **调研日期：** 2026-09-20 (UTC)；机器证据 `docs/source-probes/PHASE2_PROBE_20260920.json`，人工观察 `docs/source-probes/PHASE2_MANUAL_OBSERVATIONS_20260920.md`。

## 摘要

两者对按编号查询的 URL 都返回带 `cf-mitigated: challenge` 的 HTTP 403。

## Raw 探测证据（最后一轮，`tools/probe_sources.py raw`）

| UTC | 请求 URL | HTTP | 页面 `<title>` | cf-mitigated | 最终 URL | 传输错误 |
|---|---|---|---|---|---|---|
| 12:58:38 | `https://supjav.com/?s=FC2-PPV-4825061` | 403 | `Just a moment...` | challenge | same |  |
| 12:58:40 | `https://missav.ws/en/fc2-ppv-4825061` | 403 | `Just a moment...` | challenge | same |  |

## 发现

- 作为通用聚合站点候选进行了探测；不解 challenge 就都无法访问。

## 风险 / 重新检查触发条件

n/a
