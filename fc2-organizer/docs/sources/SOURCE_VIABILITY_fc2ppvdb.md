# SOURCE_VIABILITY - fc2ppvdb

- **提供方：** FC2PPVDB (fc2ppvdb.com)
- **状态：** `BLOCKED`
- **决定：** Phase 2 REJECT - 无法从本网络评估
- **适配器：** 无
- **是否需要登录/cookie：** 未知
- **Cloudflare/反爬：** 未知（从未到达源站）
- **调研日期：** 2026-09-20 (UTC)；机器证据 `docs/source-probes/PHASE2_PROBE_20260920.json`，人工观察 `docs/source-probes/PHASE2_MANUAL_OBSERVATIONS_20260920.md`。

## 摘要

从本网络无法访问：HTTPS 证书校验失败，明文 HTTP 返回西班牙法院下令的 IP 封锁通知。这是环境事实，不能证明站点已失效。

## Raw 探测证据（最后一轮，`tools/probe_sources.py raw`）

| UTC | 请求 URL | HTTP | 页面 `<title>` | cf-mitigated | 最终 URL | 传输错误 |
|---|---|---|---|---|---|---|
| 12:58:16 | `https://fc2ppvdb.com/articles/4825061` | n/a | `` | - | `-` | `HttpConnectionError: [SSL: CERTIFICATE_VERIFY_FAILED] certificate veri` |
| 12:58:19 | `http://fc2ppvdb.com/articles/4825061` | 200 | `...` | - | same |  |

## 发现

- 解析到 `188.114.96.5`/`188.114.97.5`（与 `onejav.com` 共用）。HTTPS 给出 `CERTIFICATE_VERIFY_FAILED: self-signed certificate`；根页面有一次超时。
- `http://fc2ppvdb.com/articles/4825061` 返回 HTTP 200 通知页：依据 Juzgado de lo Mercantil nº 6 de Barcelona 于 18 Dec 2024 作出的判决（LaLiga / Telefónica），对该 IP 的访问已被封锁。原文见人工观察 section 4。
- 证书校验**没有**被关闭，也没有使用其他路由。第三方报告（2024 年的一个 mdcx issue：'closed by DMCA'；2026 年的一个分析页面：有流量）相互矛盾，未被用作证据。
- 由于无法在此探测，它不能计入 Gate；应从没有该封锁的网络重新探测。

## 风险 / 重新检查触发条件

若它仍存活，则是一个信息丰富的来源（据 mdcx issue，演员由用户整理）；值得在 Phase 3 确定来源列表前从其他网络重新检查。
