# SOURCE_VIABILITY - fc2db_com

- **提供方：** FC2DB (fc2db.com - `.com` 姊妹站)
- **状态：** `BLOCKED`
- **决定：** REJECT - Cloudflare challenge（使用 `fc2db.net`）
- **适配器：** 无（`fc2db_net` 已覆盖该运营方）
- **是否需要登录/cookie：** 未知
- **Cloudflare/反爬：** **是** - `cf-mitigated: challenge`
- **调研日期：** 2026-09-20 (UTC)；机器证据 `docs/source-probes/PHASE2_PROBE_20260920.json`，人工观察 `docs/source-probes/PHASE2_MANUAL_OBSERVATIONS_20260920.md`。

## 摘要

`https://fc2db.com/...` 对 `/work/<id>/` 返回 Cloudflare challenge（403），而 `fc2db.net` 无 challenge 地提供同一目录。

## Raw 探测证据（最后一轮，`tools/probe_sources.py raw`）

| UTC | 请求 URL | HTTP | 页面 `<title>` | cf-mitigated | 最终 URL | 传输错误 |
|---|---|---|---|---|---|---|
| 12:57:53 | `https://fc2db.com/work/4824605/` | 403 | `Just a moment...` | challenge | same |  |

## 发现

- `/work/4824605/` 返回 403，`cf-mitigated: challenge`，`Just a moment...`。`/` 与 `www.fc2db.com/` 也是 403（更早的探测）。
- 从独立性角度看不算单独的提供方：与 `fc2db_net` 同一品牌。

## 风险 / 重新检查触发条件

n/a
