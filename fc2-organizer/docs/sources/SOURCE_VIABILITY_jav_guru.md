# SOURCE_VIABILITY - jav_guru

- **提供方：** Jav Guru (jav.guru)
- **状态：** `REJECTED`
- **决定：** REJECT - 覆盖差
- **适配器：** 无
- **是否需要登录/cookie：** 不需要
- **Cloudflare/反爬：** 未观察到 challenge
- **调研日期：** 2026-09-20 (UTC)；机器证据 `docs/source-probes/PHASE2_PROBE_20260920.json`，人工观察 `docs/source-probes/PHASE2_MANUAL_OBSERVATIONS_20260920.md`。

## 摘要

`/?s=<n>` 返回真实结果列表，但 6 个 known-valid ID 中只有 1 个（`4824605`）命中（英文机器翻译标题）；其余五个没有任何结果。

## Raw 探测证据（最后一轮，`tools/probe_sources.py raw`）

| UTC | 请求 URL | HTTP | 页面 `<title>` | cf-mitigated | 最终 URL | 传输错误 |
|---|---|---|---|---|---|---|
| 12:58:44 | `https://jav.guru/?s=4825061` | 200 | `You searched for 4825061 &#8902; Jav Guru ⋆ Japanese porn Tu` | - | same |  |

## 发现

- 在我最初一次误解析之后（已在判断前纠正），改用针对结果标题的选择器进行了核对。

## 风险 / 重新检查触发条件

n/a
