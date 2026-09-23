# SOURCE_VIABILITY - onejav

- **提供方：** OneJAV (onejav.com)
- **状态：** `BLOCKED`
- **决定：** Phase 2 REJECT - 无法从本网络评估
- **适配器：** 无
- **是否需要登录/cookie：** 未知
- **Cloudflare/反爬：** 未知
- **调研日期：** 2026-09-20 (UTC)；机器证据 `docs/source-probes/PHASE2_PROBE_20260920.json`，人工观察 `docs/source-probes/PHASE2_MANUAL_OBSERVATIONS_20260920.md`。

## 摘要

与 `fc2ppvdb.com` 相同的 ISP 级 IP 封锁（地址完全相同）。无法在此评估。

## Raw 探测证据（最后一轮，`tools/probe_sources.py raw`）

| UTC | 请求 URL | HTTP | 页面 `<title>` | cf-mitigated | 最终 URL | 传输错误 |
|---|---|---|---|---|---|---|
| 12:58:42 | `https://onejav.com/search/fc2-ppv-4825061` | n/a | `` | - | `-` | `HttpConnectionError: [SSL: CERTIFICATE_VERIFY_FAILED] certificate veri` |

## 发现

- `https://onejav.com/search/fc2-ppv-...` 给出 `CERTIFICATE_VERIFY_FAILED: self-signed certificate`（解析到 `188.114.96.5`/`188.114.97.5`）。在公开的 mdcx issue #243 中被列为候选；从未到达。

## 风险 / 重新检查触发条件

应从未被封锁的网络重新探测。
