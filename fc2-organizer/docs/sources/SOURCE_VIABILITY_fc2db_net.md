# SOURCE_VIABILITY - fc2db_net

- **Provider:** FC2DB (fc2db.net)
- **Status:** `VERIFIED`
- **Decision:** ADOPT
- **Adapter:** `fc2_metadata_core.sources.adapters.fc2db_net.Fc2dbNetAdapter`
- **Login/cookie needed:** not required
- **Cloudflare/anti-bot:** Cloudflare CDN present (`cf-ray`), no challenge observed in any request; a challenge would map to `BLOCKED`, never bypassed
- **Research date:** 2026-09-20 (UTC); machine evidence `docs/source-probes/PHASE2_PROBE_20260920.json`, human observations `docs/source-probes/PHASE2_MANUAL_OBSERVATIONS_20260920.md`.

## Summary

Server-rendered WordPress page per work at `/work/<digits>/`. Missing works are a clean HTTP 404 (`作品が削除されたか存在しません`). Richest of the three sources: Japanese title, actors, seller, release, runtime, tags, cover.

## Raw probe evidence (final pass, `tools/probe_sources.py raw`)

| UTC | Requested URL | HTTP | Page `<title>` | cf-mitigated | Final URL | Transport error |
|---|---|---|---|---|---|---|
| 12:57:48 | `https://fc2db.net/work/4825061/` | 404 | `ページが見つかりませんでした &#8211; FC2DB` | - | same |  |
| 12:57:51 | `https://fc2db.net/work/4824605/` | 200 | `※1/11まで初回限定90％OFF※【ハメ撮り】スレンダー美人の人妻に種付け中出し調教 &#8211; FC2DB` | - | same |  |

## Findings

- Fields: number+title from `<h1>[FC2-PPV-N] Title</h1>`; release/runtime/actors/publisher (seller)/thumbnail from the page's schema.org `VideoObject` JSON-LD; tags from `/work-tags/` links. Everything except number/title is optional in the adapter.
- `商品ID` on the page equals the FC2 number, so the page number is checked against the request (a mismatch gives `INVALID_RESPONSE`, never a silent SUCCESS).
- Sibling `fc2db.com` is behind a Cloudflare challenge (403) and is not used; the adapter's `base_url` is configurable if the operator's domains change again (the site itself carries a URL-migration banner in its markup).
- Coverage on the 7-ID probe set: 6/7 (missing only `FC2-4825061`, which JavDB and 123AV have).
- Not an official FC2 service (its footer says so); titles are copied from FC2 Content Market.

## Adapter verification (Phase 2 Gate run, `tools/probe_sources.py adapter --source fc2db_net`, code `3a21c4b`)

Real HTTP through `HttpxTransport`, one request per lookup, about 2.5 s between lookups, no cookies. `SUCCESS` means the adapter's `SourceResult` met minimum success (canonical number + non-empty title).

| UTC | Number | HTTP | SourceStatus | Title (excerpt) | Fields populated |
|---|---|---|---|---|---|
| 13:02:27 | FC2-4825061 | 404 | **not_found** |  |  |
| 13:02:30 | FC2-4824605 | 200 | **success** | ※1/11まで初回限定90％OFF※【ハメ撮り】スレンダー美人の人妻に種付け中出し調教 | number, title, publisher, release, runtime, actors, tags, thumb_urls, source_urls |
| 13:02:34 | FC2-4979299 | 200 | **success** | 夢は小学校の先生。天使のような笑顔と色白美巨乳♡ほのぼの系美女のおじさま２人への体当たり性指導映 | number, title, publisher, release, runtime, actors, tags, thumb_urls, source_urls |
| 13:02:37 | FC2-4976588 | 200 | **success** | ※表に出す予定はなかった映像※ 元有名キッズモデル18才 | number, title, publisher, release, runtime, actors, tags, thumb_urls, source_urls |
| 13:02:40 | FC2-1042815 | 200 | **success** | 【半額】【**JD】うた（20）【眼鏡っこ激イキ編】吸引力が凄いフェラ！おまんこの締め付けとハメ | number, title, publisher, release, runtime, actors, tags, thumb_urls, source_urls |
| 13:02:43 | FC2-4978035 | 200 | **success** | 【廃版】超有名テレビ局の美女A（元女子アナのFカップ美巨乳） | number, title, publisher, release, runtime, actors, thumb_urls, source_urls |
| 13:02:47 | FC2-4972767 | 200 | **success** | ※在庫限り※身長133cm 18歳。日本×ボリビアの芸能界最小ハーフモデル。衝撃の体格差1.3倍 | number, title, publisher, release, runtime, actors, tags, thumb_urls, source_urls |

An earlier identical run at code `45be2b7` (13:00:30-13:01:38) gave the same outcomes except one transient `network_error` (timeout) on `FC2-4978035`; see manual observations section 10.

**Gate result:** 6 known-valid IDs returned `SUCCESS` (FC2-4824605, FC2-4979299, FC2-4976588, FC2-1042815, FC2-4978035, FC2-4972767); requirement is >=2.

## Requirement checklist

| Requirement (spec section 11 / Phase 2) | Met |
|---|---|
| Real HTTP request (not mocked) | yes |
| Formal adapter actually executed | yes |
| >=2 distinct known-valid IDs return `SUCCESS` with number + non-empty title | yes (6) |
| No private login / cookie | yes |
| No CAPTCHA / Cloudflare bypass | yes (none attempted; a challenge maps to `BLOCKED`) |
| Offline parser + contract tests | yes (`tests/unit/sources/adapters/test_adapter_fc2db_net.py`, real-response fixtures under `tests/fixtures/sources/`) |

## Risks / re-check trigger

Single operator, no SLA, no API contract; layout changes break the regexes (offline fixtures pin today's markup). Possible future Cloudflare challenge would give `BLOCKED`.
