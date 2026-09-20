# SOURCE_VIABILITY - javdb

- **Provider:** JavDB (javdb.com) - public search listing only
- **Status:** `VERIFIED`
- **Decision:** ADOPT (search listing only; partial fields)
- **Adapter:** `fc2_metadata_core.sources.adapters.javdb.JavdbAdapter`
- **Login/cookie needed:** not required for the search listing (detail pages require login and are never requested)
- **Cloudflare/anti-bot:** Cloudflare CDN present, no challenge observed; a challenge or a `/login` redirect maps to `BLOCKED`
- **Research date:** 2026-09-20 (UTC); machine evidence `docs/source-probes/PHASE2_PROBE_20260920.json`, human observations `docs/source-probes/PHASE2_MANUAL_OBSERVATIONS_20260920.md`.

## Summary

`/search?q=FC2-PPV-<digits>` is a public, server-rendered listing carrying number, Japanese title, release date and cover URL per hit. The **detail page redirects to `/login`**, so actors/tags/runtime are deliberately unavailable from this source.

## Raw probe evidence (final pass, `tools/probe_sources.py raw`)

| UTC | Requested URL | HTTP | Page `<title>` | cf-mitigated | Final URL | Transport error |
|---|---|---|---|---|---|---|
| 12:58:00 | `https://javdb.com/search?q=FC2-PPV-4825061` | 200 | `JavDB 成人影片數據庫` | - | same |  |
| 12:58:02 | `https://javdb.com/search?q=FC2-PPV-4824605` | 200 | `JavDB 成人影片數據庫` | - | same |  |
| 12:58:04 | `https://javdb.com/v/82ZNYd` | 200 | `登入 / JavDB 成人影片數據庫` | - | `https://javdb.com/login` |  |

## Findings

- Search is fuzzy (`4825061` also returns `FC2-1825061`; `4824605` returns only unrelated `FC2-1824605`/`FC2-4724605`). The adapter accepts **only** the hit whose number equals the request, otherwise `NOT_FOUND`. Verified live: `FC2-4824605` gives `NOT_FOUND` even though the page lists two near-misses.
- A zero-result page carries `<div class="empty-message">暫無內容</div>`; a 200 page with neither a result list nor that marker is `INVALID_RESPONSE`, not `NOT_FOUND`.
- Detail redirect: `302 https://javdb.com/v/82ZNYd` to `https://javdb.com/login` (manual observations section 3).
- Coverage on the 7-ID probe set: 6/7 (missing only `FC2-4824605`).
- Fields returned: number, title, release, cover thumbnail, source URL, JavDB video id (`external_ids['javdb']`).

## Adapter verification (Phase 2 Gate run, `tools/probe_sources.py adapter --source javdb`, code `3a21c4b`)

Real HTTP through `HttpxTransport`, one request per lookup, about 2.5 s between lookups, no cookies. `SUCCESS` means the adapter's `SourceResult` met minimum success (canonical number + non-empty title).

| UTC | Number | HTTP | SourceStatus | Title (excerpt) | Fields populated |
|---|---|---|---|---|---|
| 13:03:04 | FC2-4825061 | 200 | **success** | 【顔出し】ハーフ美人妻 最初で最後の顔出し未公開動画×2本 ※SNS認証者限定 | number, title, release, thumb_urls, source_urls, external_ids |
| 13:03:07 | FC2-4824605 | 200 | **not_found** |  |  |
| 13:03:10 | FC2-4979299 | 200 | **success** | 夢は小学校の先生。天使のような笑顔と色白美巨乳♡ほのぼの系美女のおじさま２人への体当たり性指導映 | number, title, release, thumb_urls, source_urls, external_ids |
| 13:03:13 | FC2-4976588 | 200 | **success** | 表に出す予定はなかった映像※ 元有名キッズモデル18才 ''139cm/Fカップ''の神得体に容 | number, title, release, thumb_urls, source_urls, external_ids |
| 13:03:16 | FC2-1042815 | 200 | **success** | 【50％オフ】【20歳のビッチ×眼鏡】うた【眼鏡っこ激イキ編】吸引力が凄いフェラ！おまんこの締め | number, title, release, thumb_urls, source_urls, external_ids |
| 13:03:18 | FC2-4978035 | 200 | **success** | 【廃版】大手テレビ局の美女アナウンサーA（元女子アナのFカップ美巨乳） | number, title, release, thumb_urls, source_urls, external_ids |
| 13:03:21 | FC2-4972767 | 200 | **success** | 身長133cm 18歳。日本×ボリビアの芸能界最小ハーフモデル。衝撃の体格差1.3倍！破壊寸前ま | number, title, release, thumb_urls, source_urls, external_ids |

An earlier identical run at code `45be2b7` (13:00:30-13:01:38) gave the same outcomes.

**Gate result:** 6 known-valid IDs returned `SUCCESS` (FC2-4825061, FC2-4979299, FC2-4976588, FC2-1042815, FC2-4978035, FC2-4972767); requirement is >=2.

## Requirement checklist

| Requirement (spec section 11 / Phase 2) | Met |
|---|---|
| Real HTTP request (not mocked) | yes |
| Formal adapter actually executed | yes |
| >=2 distinct known-valid IDs return `SUCCESS` with number + non-empty title | yes (6) |
| No private login / cookie | yes |
| No CAPTCHA / Cloudflare bypass | yes (none attempted; a challenge maps to `BLOCKED`) |
| Offline parser + contract tests | yes (`tests/unit/sources/adapters/test_adapter_javdb.py`, real-response fixtures under `tests/fixtures/sources/`) |

## Risks / re-check trigger

The most likely of the three to rate-limit or introduce a login/age gate; the adapter makes exactly one request per lookup and Phase 3 must add per-host throttling. This adapter reads one public page per lookup and is not meant for bulk crawling.
