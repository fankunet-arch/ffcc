# PHASE2 人工观察记录 — 2026-09-20 (UTC)

机器记录的探测证据位于 `PHASE2_PROBE_20260920.json`
（`tools/probe_sources.py raw|adapter`）。该文件记录状态码、最终
URL、耗时、少量非敏感的 header 线索，以及（对 raw 探测而言）页面
`<title>`。它有意**不**记录重定向*跳转*、响应
体或 cookie 值。本文件保存那些需要人工多看一眼才能得出的
观察。它们由一次性脚本完成，这些脚本复用了同一个 `HttpxTransport`（相同 User-Agent、不带 cookies、不走代理、
默认证书校验），并在此复述，以便复查者能
逐条手工复核。这里没有任何内容取自搜索引擎
摘要或记忆；凡是仅用网络搜索来*发现
候选名称*的情况（见 §9），随后都对该候选做了在线探测。

所有时间均为 UTC，2026-09-20，约 ~12:30 至 ~13:05 之间。

## 1. 网络是真实的公网路径，而非沙箱合成的 403

`GET https://example.com/`、`https://www.wikipedia.org/`、`https://fc2.com/`
都返回了真实的 HTTP 200 页面（以 `--no-record` 运行探测，12:34:16–19）。
经 Cloudflare 前置的响应带有 `cf-ray: …-MAD`（马德里边缘节点），即
出口是西班牙网络，而非沙箱。这一点对
§4 很重要（西班牙法院下令的 IP 封锁解释了两个“证书”失败）。

## 2. FC2 Official：文章页与搜索需要已登录会话

原样记录的重定向链，*未*跟随重定向，12:59:47：

```
302 https://adult.contents.fc2.com/article/4824605/          -> /lk/services/id/login?anlad=3   (sets CONTENTS_FC2_PHPSESSID)
302 https://adult.contents.fc2.com/lk/services/id/login?anlad=3 -> https://fc2.com/ja/login.php?ref=payarticle
302 https://fc2.com/ja/login.php?ref=payarticle              -> https://error.fc2.com/other/
404 https://error.fc2.com/other/                             title: "FC2 - 404 Error"
```

`/search/?keyword=4825061` 走完全相同的链（`anlad=5`）。因此
raw 探测报告的“404”是一次**登录重定向**的终点，而非作品
缺失——两个指定 ID 并非在 FC2 上“不存在”，而是位于
登录墙之后。只有列表页（`/`、`/ranking/`）是公开的（HTTP 200）；它们
展示最新/排行作品，但不能按编号查询。使用
类浏览器 User-Agent 结果相同，因此与 UA 无关。

## 3. JavDB：搜索列表公开，详情页需要登录

```
302 https://javdb.com/v/82ZNYd -> https://javdb.com/login
200 https://javdb.com/login       title: "登入 | JavDB 成人影片數據庫"
```

`/search?q=FC2-PPV-<n>` 是公开的，会列出 `FC2-<n>` 及其标题、发行日期
和封面 URL。搜索是*模糊*的：`4825061` 还列出了 `FC2-1825061`；
`4824605` 只列出了 `FC2-1824605` / `FC2-4724605`。零结果页面包含
`<div class="empty-message">暫無內容</div>`。

## 4. fc2ppvdb.com 与 onejav.com：在此处被法院下令的 ISP IP 封锁拦截

两者都解析到同一组 Cloudflare 地址 `188.114.96.5` / `188.114.97.5`。
HTTPS 证书校验失败（`self-signed certificate`），有一次尝试
超时。明文 `http://fc2ppvdb.com/articles/4824605` 返回 HTTP 200 以及一个
简短通知页，其文字为（西班牙语，节选）：*"El acceso a la presente
dirección IP ha sido bloqueado en cumplimiento de lo dispuesto en la Sentencia
de 18 de diciembre de 2024, dictada por el Juzgado de lo Mercantil nº 6 de
Barcelona … instado por la Liga Nacional de Fútbol Profesional y por
Telefónica Audiovisual Digital"*。因此从本网络出发，应答的是 *IP 封锁*——而不是
这些站点本身。后果：

- 无法在本环境中评判这两个站点。这**不是**它们已失效的
  证据（2024 年的一个 mdcx issue 报告 `fc2ppvdb.com` 因 DMCA 关闭；
  2026 年的一段流量分析摘要暗示它可能已恢复——两者都未
  被当作证据）。
- 证书校验**没有**被关闭，也没有使用其他
  解析器/路由来绕过封锁。
- 同类封锁可能间歇性地影响本网络上任何经 Cloudflare 前置的
  候选；Phase 3 必须把 `NETWORK_ERROR` 视为预期情况。

## 5. FC2CM（`fc2cm.com`）：仅有 pre-2026 时期的作品，不稳定，soft 404

根页面有一次返回了真实内容（标题 "FC2 コンテンツ マーケット アダルト
最新 動画 画像 販売 - FC2CM.com"），而相隔数秒的另一次尝试返回了 9 字节的响应体 `sql error`。
首页列出的最新作品是
`No.4699535`。条目 URL 形如 `/?p=<id>&nc=0`：

| id | 结果 |
|---|---|
| 4699535 | 200，`<title>` 匹配的页面 |
| 1042815 | 200，`<title>` 匹配的页面（日文标题） |
| 4825061 | 200，5.8 KB 的页面，其 `<title>` 字面就是 `404`（**soft 404**） |
| 4824605 | 200，9 字节响应体 `sql error` |
| 4979299 | 200，9 字节响应体 `sql error` |
| 4700100, 4650000 | 200，含 `<title>404</title>` |

`db.fc2cm.com`（规格书中 "FC2CMADB" 的主机名）返回的是 cPanel 默认页
重定向（`/cgi-sys/defaultwebpage.cgi`）→ 该处没有内容。

## 6. FD2（`fd2ppv.cc`）：列表页公开，作品页位于 Cloudflare challenge 之后

`/` → 200 `All Works - FD2`，链接到近期作品的 `/articles/<id>`。每一个
`/articles/<id>` 请求（4825061, 4824605, 4979786, 4979799）→ 403，
`cf-mitigated: challenge`，标题 `Just a moment...`。`/search?q=…` 重定向到
`/actresses/?keyword=` → 同样被 challenge。未做绕过。

## 7. 其他被 Cloudflare challenge 的主机

`javten.com`、`supjav.com`、`missav.ws`、`fc2db.com`（已采用的 `fc2db.net` 的 `.com` 姊妹站）：
HTTP 403，`cf-mitigated: challenge`，标题
`Just a moment...`（已在 JSON 中针对最后一轮 raw
探测的查询 URL 记录）。对 `javten.com`，更早的 `/` 与 `/fc2` 探测（记录于
加入标题/header 捕获之前）只显示 403 及反爬线索。

## 8. 年龄验证与仅涉及覆盖面的发现

- `www.javbus.com/FC2-PPV-<n>` → 200，但最终落在 `/doc/driver-verify?referer=…`
  （标题 "Age Verification JavBus"），这是一个需要点击通过才能获得
  cookie 的中间页。未继续深入。
- `jav.guru/?s=<n>` 返回真实结果列表，但 6 个 known-valid ID 中只有 1 个有结果
  （`4824605`，英文机器翻译标题）；对
  `4825061 4979299 4976588 1042815 4978035` 无任何结果。
- `netflav.com/search?keyword=<n>`：页面内嵌 `__NEXT_DATA__` JSON，其中有
  `4825061` 与 `4824605` 的命中（标题为中文机器翻译，
  前缀为 `fc2-ppv <n>`），`4979299`（2026-09-19 发行）则没有。
- `sukebei.nyaa.si/?q=4824605` 返回至少 6 条带有该编号的种子行，
  每条的上传者提供的标题写法都*不同*（`[H265 1080p]
  FC2-PPV-…`、`FC2PPV-…`、`FC2 PPV …`、`+++ FC2-PPV-…`，日文/中文混杂）。

## 9. 候选的发现方式

规格书 §"初始来源候选" 列出了 FC2CMADB、FD2PPV、FC2DB/JavTen、FC2 official。
其他名称来自：JavDB 搜索页本身；一次针对
"FC2-PPV database … alternative" 的网络搜索（得到 `fc2db.com` / `fc2db.net` /
`fc2ppvdb.com`）；公开的 GitHub issue `sqzw-x/mdcx#243`（提到
`fc2ppvdb.com`、`onejav.com`）；fc2db.net 首页上的链接；以及
通用的聚合站点名称。每个名称在作出任何判断之前都经过了在线探测。

## 10. 一次值得记录的瞬时失败

在第一次最终 gate run 期间（13:00:30–13:01:38，代码位于 `45be2b7`），
`fc2db_net` 对 `FC2-4978035` 的查询在约 ~15 s 后以 `network_error` 失败了一次（即
transport 的 15 s 超时）。空的异常文本暴露出
`error_detail` 只写了 `transport error: `；这一点已在 `3a21c4b` 中修复
（现在会写出异常类型），整个 gate 于 13:02:27–13:03:21
使用 `3a21c4b` 重新运行，同一查询成功。两次运行都记录在 JSON 中。
