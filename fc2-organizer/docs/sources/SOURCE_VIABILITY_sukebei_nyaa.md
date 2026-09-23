# SOURCE_VIABILITY - sukebei_nyaa

- **提供方：** Sukebei (sukebei.nyaa.si)
- **状态：** `REJECTED`
- **决定：** REJECT - 自由文本的种子名称不是元数据
- **适配器：** 无
- **是否需要登录/cookie：** 不需要
- **Cloudflare/反爬：** 未观察到 challenge
- **调研日期：** 2026-09-20 (UTC)；机器证据 `docs/source-probes/PHASE2_PROBE_20260920.json`，人工观察 `docs/source-probes/PHASE2_MANUAL_OBSERVATIONS_20260920.md`。

## 摘要

一个种子索引。`?q=<n>` 对已知作品返回许多行，每行的上传者输入标题都不同（`[H265 1080p] FC2-PPV-...`、`FC2PPV-...`、`FC2 PPV ...`、`+++ FC2-PPV-...`，日文/中文混杂）。不存在可提取的 canonical 标题。

## Raw 探测证据（最后一轮，`tools/probe_sources.py raw`）

| UTC | 请求 URL | HTTP | 页面 `<title>` | cf-mitigated | 最终 URL | 传输错误 |
|---|---|---|---|---|---|---|
| 12:58:46 | `https://sukebei.nyaa.si/?f=0&c=0_0&q=4825061` | 200 | `4825061 :: Sukebei` | - | same |  |

## 发现

- 仅可用于佐证某个编号存在，绝不作为元数据来源。

## 风险 / 重新检查触发条件

n/a
