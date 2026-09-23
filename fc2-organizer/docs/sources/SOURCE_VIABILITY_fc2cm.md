# SOURCE_VIABILITY - fc2cm

- **提供方：** FC2CM (fc2cm.com；规格书名称 'FC2CMADB')
- **状态：** `PARTIAL`
- **决定：** REJECT - 陈旧、不稳定、soft 404（两个指定 ID 均失败）
- **适配器：** 无
- **是否需要登录/cookie：** 不需要
- **Cloudflare/反爬：** 未观察到 challenge
- **调研日期：** 2026-09-20 (UTC)；机器证据 `docs/source-probes/PHASE2_PROBE_20260920.json`，人工观察 `docs/source-probes/PHASE2_MANUAL_OBSERVATIONS_20260920.md`。

## 摘要

站点存活但实际上已停滞：其列出的最新作品是 No.4699535，能解析较旧的 id（`1042815`、`4699535`）但解析不了任何 2026 id，并且对缺失作品报告 HTTP 200（标题为 `404` 的页面，或 9 字节的响应体 `sql error`）而非 404。

## Raw 探测证据（最后一轮，`tools/probe_sources.py raw`）

| UTC | 请求 URL | HTTP | 页面 `<title>` | cf-mitigated | 最终 URL | 传输错误 |
|---|---|---|---|---|---|---|
| 12:58:22 | `https://fc2cm.com/?p=4825061&nc=0` | 200 | `` | - | same |  |
| 12:58:24 | `https://fc2cm.com/?p=4824605&nc=0` | 200 | `` | - | same |  |
| 12:58:27 | `https://fc2cm.com/?p=1042815&nc=0` | 200 | `` | - | same |  |

## 发现

- `/?p=4825061&nc=0` 返回 200，页面 `<title>` 为 `404`；`/?p=4824605&nc=0` 与 `/?p=4979299&nc=0` 返回 200，响应体为 `sql error`；`/?p=1042815&nc=0` 返回 200，带真实的日文标题。
- 根页面本身在相隔数秒的两次尝试中，一次返回 `sql error`，一次返回真实内容：后端间歇性故障。
- `db.fc2cm.com`（规格书中 'FC2CMADB' 的主机名）只提供 cPanel 默认页重定向。
- 由于 HTTP 状态不提供信息，任何适配器都需要嗅探响应体才能区分缺失与存在。对一个连两个指定 ID 都无法解析的来源而言不值得。

## 风险 / 重新检查触发条件

n/a
