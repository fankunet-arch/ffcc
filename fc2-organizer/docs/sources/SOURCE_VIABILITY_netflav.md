# SOURCE_VIABILITY - netflav

- **提供方：** Netflav (netflav.com)
- **状态：** `EXPERIMENTAL`
- **决定：** NOT ADOPTED - 可访问，但对 Gate 而言属于多余，且标题质量低
- **适配器：** 无
- **是否需要登录/cookie：** 不需要
- **Cloudflare/反爬：** 未观察到 challenge
- **调研日期：** 2026-09-20 (UTC)；机器证据 `docs/source-probes/PHASE2_PROBE_20260920.json`，人工观察 `docs/source-probes/PHASE2_MANUAL_OBSERVATIONS_20260920.md`。

## 摘要

`/search?keyword=<n>` 返回 200 并内嵌 `__NEXT_DATA__` JSON；对 `4825061` 与 `4824605` 列出命中（`code: 'fc2-ppv <n>'`、机器翻译的中文标题、日期），对 `4979299`（2026-09-19 发行）没有列出任何结果。

## Raw 探测证据（最后一轮，`tools/probe_sources.py raw`）

| UTC | 请求 URL | HTTP | 页面 `<title>` | cf-mitigated | 最终 URL | 传输错误 |
|---|---|---|---|---|---|---|
| 12:58:31 | `https://netflav.com/search?keyword=4825061` | 200 | `Netflav - 搜尋 / Search` | - | same |  |
| 12:58:33 | `https://netflav.com/search?keyword=4824605` | 200 | `Netflav - 搜尋 / Search` | - | same |  |

## 发现

- 在尝试的 3 个 ID 上的覆盖：2/3。标题是带 code 前缀的机器翻译，需要清洗。Gate 已由三个更好的来源满足，因此未编写适配器（Phase 2 规则：先探测，只采用确有需要且已验证的来源）。

## 风险 / 重新检查触发条件

若三个已采用来源之一失效，可作为候补储备。
