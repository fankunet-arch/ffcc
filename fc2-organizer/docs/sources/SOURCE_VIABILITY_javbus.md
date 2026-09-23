# SOURCE_VIABILITY - javbus

- **提供方：** JavBus (www.javbus.com)
- **状态：** `BLOCKED`
- **决定：** REJECT - 年龄验证中间页
- **适配器：** 无
- **是否需要登录/cookie：** 需要一个点击通过年龄验证后获得的 cookie
- **Cloudflare/反爬：** 无 challenge；有年龄验证
- **调研日期：** 2026-09-20 (UTC)；机器证据 `docs/source-probes/PHASE2_PROBE_20260920.json`，人工观察 `docs/source-probes/PHASE2_MANUAL_OBSERVATIONS_20260920.md`。

## 摘要

`/FC2-PPV-<n>` 重定向到 `/doc/driver-verify?referer=...`（标题 `Age Verification JavBus`）。要通过它就得出示中间页设置的 cookie；未继续深入，JavBus 的 FC2 覆盖情况也从未确定。

## Raw 探测证据（最后一轮，`tools/probe_sources.py raw`）

| UTC | 请求 URL | HTTP | 页面 `<title>` | cf-mitigated | 最终 URL | 传输错误 |
|---|---|---|---|---|---|---|
| 12:58:36 | `https://www.javbus.com/FC2-PPV-4825061` | 200 | `Age Verification JavBus - JavBus` | - | `https://www.javbus.com/doc/driver-verify?referer=https%3A%2F%2Fwww.jav` |  |

## 发现

- 未进一步调查：采用它首先需要判定用脚本处理年龄验证 cookie 是否可接受，这是产品/政策层面的决定，而非 Phase 2 的工程决定。

## 风险 / 重新检查触发条件

n/a
