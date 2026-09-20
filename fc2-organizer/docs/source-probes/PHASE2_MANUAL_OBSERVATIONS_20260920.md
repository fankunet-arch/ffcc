# PHASE2 manual observations — 2026-09-20 (UTC)

Machine-recorded probe evidence lives in `PHASE2_PROBE_20260920.json`
(`tools/probe_sources.py raw|adapter`). That file records status code, final
URL, timing, a few non-sensitive header hints and (for raw probes) the page
`<title>`. It deliberately does **not** record redirect *hops*, response
bodies, or cookie values. This file holds the observations that needed a
human look at more than that. They were made with throw-away scripts that
reused the same `HttpxTransport` (same User-Agent, no cookies, no proxy,
default certificate verification) and are reproduced here so a reviewer can
re-check each one by hand. Nothing here was taken from a search-engine
snippet or from memory; where a web search was used only to *discover a
candidate name* (see §9) the candidate was then probed live.

All times UTC, 2026-09-20, between ~12:30 and ~13:05.

## 1. Network is a real public path, not a sandbox synthetic 403

`GET https://example.com/`, `https://www.wikipedia.org/`, `https://fc2.com/`
all returned real HTTP 200 pages (probe run with `--no-record`, 12:34:16–19).
Cloudflare-fronted responses carry `cf-ray: …-MAD` (Madrid edge), i.e. the
egress is a Spanish network, not a sandbox. That matters
for §4 (a Spanish court-ordered IP block explains two "certificate" failures).

## 2. FC2 Official: article and search need a logged-in session

Verbatim redirect chain, redirects *not* followed, 12:59:47:

```
302 https://adult.contents.fc2.com/article/4824605/          -> /lk/services/id/login?anlad=3   (sets CONTENTS_FC2_PHPSESSID)
302 https://adult.contents.fc2.com/lk/services/id/login?anlad=3 -> https://fc2.com/ja/login.php?ref=payarticle
302 https://fc2.com/ja/login.php?ref=payarticle              -> https://error.fc2.com/other/
404 https://error.fc2.com/other/                             title: "FC2 - 404 Error"
```

`/search/?keyword=4825061` follows the identical chain (`anlad=5`). So the
"404" the raw probe reports is the end of a **login redirect**, not a missing
work — the two mandated IDs are not "absent" from FC2, they are behind the
login wall. Only list pages (`/`, `/ranking/`) are public (HTTP 200); they
show recent/ranked works but cannot be queried by number. Same result with a
browser-like User-Agent, so this is not UA-dependent.

## 3. JavDB: search listing public, detail page requires login

```
302 https://javdb.com/v/82ZNYd -> https://javdb.com/login
200 https://javdb.com/login       title: "登入 | JavDB 成人影片數據庫"
```

`/search?q=FC2-PPV-<n>` is public and lists `FC2-<n>` with title, release date
and cover URL. A search is *fuzzy*: `4825061` also listed `FC2-1825061`;
`4824605` listed only `FC2-1824605` / `FC2-4724605`. A zero-result page has
`<div class="empty-message">暫無內容</div>`.

## 4. fc2ppvdb.com and onejav.com: blocked by a court-ordered ISP IP block here

Both resolve to the same Cloudflare addresses `188.114.96.5` / `188.114.97.5`.
HTTPS fails certificate verification (`self-signed certificate`), one attempt
timed out. Plain `http://fc2ppvdb.com/articles/4824605` returns HTTP 200 with a
short notice page whose text is (Spanish, abridged): *"El acceso a la presente
dirección IP ha sido bloqueado en cumplimiento de lo dispuesto en la Sentencia
de 18 de diciembre de 2024, dictada por el Juzgado de lo Mercantil nº 6 de
Barcelona … instado por la Liga Nacional de Fútbol Profesional y por
Telefónica Audiovisual Digital"*. So from this network the *IP block* — not
the sites — is what answers. Consequences:

- Neither site can be judged from this environment. This is **not** evidence
  that they are dead (a 2024 mdcx issue reports `fc2ppvdb.com` closed by DMCA;
  a 2026 traffic-analytics snippet suggests it may be back — neither was
  treated as evidence).
- Certificate verification was **not** disabled and no alternative
  resolver/route was used to get around the block.
- The same class of block can hit any Cloudflare-fronted candidate on this
  network intermittently; Phase 3 must treat `NETWORK_ERROR` as expected.

## 5. FC2CM (`fc2cm.com`): only pre-2026 works, flaky, soft 404

Root page returned real content once (title "FC2 コンテンツ マーケット アダルト
最新 動画 画像 販売 - FC2CM.com") and a 9-byte body `sql error` on another
attempt seconds apart. Its newest listed work on the front page is
`No.4699535`. Item URLs are `/?p=<id>&nc=0`:

| id | result |
|---|---|
| 4699535 | 200, page with matching `<title>` |
| 1042815 | 200, page with matching `<title>` (Japanese title) |
| 4825061 | 200 with a 5.8 KB page whose `<title>` is literally `404` (**soft 404**) |
| 4824605 | 200 with the 9-byte body `sql error` |
| 4979299 | 200 with the 9-byte body `sql error` |
| 4700100, 4650000 | 200 with `<title>404</title>` |

`db.fc2cm.com` (the spec's "FC2CMADB" host name) served a cPanel default-page
redirect (`/cgi-sys/defaultwebpage.cgi`) → nothing there.

## 6. FD2 (`fd2ppv.cc`): list pages public, work pages behind a Cloudflare challenge

`/` → 200 `All Works - FD2`, linking `/articles/<id>` for recent works. Every
`/articles/<id>` request (4825061, 4824605, 4979786, 4979799) → 403,
`cf-mitigated: challenge`, title `Just a moment...`. `/search?q=…` redirects to
`/actresses/?keyword=` → also challenged. Not bypassed.

## 7. Other Cloudflare-challenged hosts

`javten.com`, `supjav.com`, `missav.ws`, `fc2db.com` (the `.com` sibling of the
adopted `fc2db.net`): HTTP 403, `cf-mitigated: challenge`, title
`Just a moment...` (recorded in the JSON for the lookup URLs of the final raw
pass). For `javten.com` the earlier `/` and `/fc2` probes (recorded before the
title/header capture was added) show 403 with the anti-bot hint only.

## 8. Age-gate and coverage-only findings

- `www.javbus.com/FC2-PPV-<n>` → 200 but ends on `/doc/driver-verify?referer=…`
  (title "Age Verification JavBus"), an interstitial that needs a click-through
  cookie. Not pursued.
- `jav.guru/?s=<n>` returns a real result list, but only for 1 of 6 known-valid
  IDs (`4824605`, English machine-translated title); nothing for
  `4825061 4979299 4976588 1042815 4978035`.
- `netflav.com/search?keyword=<n>`: page embeds a `__NEXT_DATA__` JSON with
  hits for `4825061` and `4824605` (titles are Chinese machine translations,
  prefixed `fc2-ppv <n>`), none for `4979299` (a 2026-09-19 release).
- `sukebei.nyaa.si/?q=4824605` returns at least 6 torrent rows carrying that number,
  each with a *different* uploader-supplied title spelling (`[H265 1080p]
  FC2-PPV-…`, `FC2PPV-…`, `FC2 PPV …`, `+++ FC2-PPV-…`, mixed JP/CN).

## 9. How candidates were discovered

Spec §"初始来源候选" names FC2CMADB, FD2PPV, FC2DB/JavTen, FC2 official.
Additional names came from: the JavDB search page itself; a web search for
"FC2-PPV database … alternative" (surfaced `fc2db.com` / `fc2db.net` /
`fc2ppvdb.com`); the public GitHub issue `sqzw-x/mdcx#243` (mentions
`fc2ppvdb.com`, `onejav.com`); links found on the fc2db.net front page; and
generic aggregator names. Every name was then probed live before any judgement.

## 10. One transient failure worth recording

During the first final gate run (13:00:30–13:01:38, code at `45be2b7`)
`fc2db_net` on `FC2-4978035` failed once with `network_error` after ~15 s (the
transport's 15 s timeout). The empty exception text exposed that
`error_detail` said only `transport error: `; that was fixed in `3a21c4b`
(exception type is now named) and the whole gate was re-run at 13:02:27–13:03:21
with `3a21c4b`, where the same lookup succeeded. Both runs are in the JSON.
