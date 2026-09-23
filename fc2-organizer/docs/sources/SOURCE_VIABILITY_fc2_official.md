# SOURCE_VIABILITY - fc2_official

- **提供方：** FC2 Content Market (adult.contents.fc2.com)
- **状态：** `BLOCKED`
- **决定：** REJECT - 无适配器（登录墙）
- **适配器：** 无
- **是否需要登录/cookie：** 需要（登录）
- **Cloudflare/反爬：** 无 challenge；经 nginx/Cloudflare 提供服务
- **调研日期：** 2026-09-20 (UTC)；机器证据 `docs/source-probes/PHASE2_PROBE_20260920.json`，人工观察 `docs/source-probes/PHASE2_MANUAL_OBSERVATIONS_20260920.md`。

## 摘要

文章页与搜索页重定向到 FC2 登录页（再从那里跳到通用 404 页面）。按编号查询需要私有 FC2 会话，而规格书 section 11 不允许这样做。只有列表页（`/`、`/ranking/`）是公开的，且无法按编号查询。

## Raw 探测证据（最后一轮，`tools/probe_sources.py raw`）

| UTC | 请求 URL | HTTP | 页面 `<title>` | cf-mitigated | 最终 URL | 传输错误 |
|---|---|---|---|---|---|---|
| 12:57:36 | `https://adult.contents.fc2.com/article/4825061/` | 404 | `FC2 - 404 Error` | - | `https://error.fc2.com/other/` |  |
| 12:57:38 | `https://adult.contents.fc2.com/article/4824605/` | 404 | `FC2 - 404 Error` | - | `https://error.fc2.com/other/` |  |
| 12:57:41 | `https://adult.contents.fc2.com/search/?keyword=4825061` | 404 | `FC2 - 404 Error` | - | `https://error.fc2.com/other/` |  |
| 12:57:44 | `https://adult.contents.fc2.com/ranking/` | 200 | `ランキングトップ - アダルト / FC2コンテンツマーケット` | - | same |  |

## 发现

- `/article/4824605/` 的重定向链（未跟随重定向）：302 到 `/lk/services/id/login?anlad=3`，302 到 `https://fc2.com/ja/login.php?ref=payarticle`，302 到 `https://error.fc2.com/other/`，404 `FC2 - 404 Error`。原文见 `docs/source-probes/PHASE2_MANUAL_OBSERVATIONS_20260920.md` section 2。
- 因此 raw 探测的 `404` 是一次**登录重定向**的终点，不能证明作品不存在。两个指定 ID 以及类浏览器 User-Agent 下结果均相同。
- `/search/?keyword=4825061` 走完全相同的链（`anlad=5`）。
- `/ranking/` 返回 200（`ランキングトップ - アダルト | FC2コンテンツマーケット`）；首页列出近期的文章 id（约 4.98M，说明站点是最新的）。可用于发现近期 id，但不能用于查询某一个 id。

## 风险 / 重新检查触发条件

如果 FC2 重新开放匿名文章页，它将成为最佳来源（它是其他所有来源数据的源头）。重新检查触发条件：`/article/<id>/` 在无会话时返回 200。
