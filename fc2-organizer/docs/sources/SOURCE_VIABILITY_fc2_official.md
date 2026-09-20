# SOURCE_VIABILITY - fc2_official

- **Provider:** FC2 Content Market (adult.contents.fc2.com)
- **Status:** `BLOCKED`
- **Decision:** REJECT - no adapter (login wall)
- **Adapter:** none
- **Login/cookie needed:** required (login)
- **Cloudflare/anti-bot:** no challenge; served via nginx/Cloudflare
- **Research date:** 2026-09-20 (UTC); machine evidence `docs/source-probes/PHASE2_PROBE_20260920.json`, human observations `docs/source-probes/PHASE2_MANUAL_OBSERVATIONS_20260920.md`.

## Summary

Article and search pages redirect to the FC2 login page (and from there to a generic 404 page). Lookup by number needs a private FC2 session, which spec section 11 disqualifies. Only list pages (`/`, `/ranking/`) are public and they cannot be queried by number.

## Raw probe evidence (final pass, `tools/probe_sources.py raw`)

| UTC | Requested URL | HTTP | Page `<title>` | cf-mitigated | Final URL | Transport error |
|---|---|---|---|---|---|---|
| 12:57:36 | `https://adult.contents.fc2.com/article/4825061/` | 404 | `FC2 - 404 Error` | - | `https://error.fc2.com/other/` |  |
| 12:57:38 | `https://adult.contents.fc2.com/article/4824605/` | 404 | `FC2 - 404 Error` | - | `https://error.fc2.com/other/` |  |
| 12:57:41 | `https://adult.contents.fc2.com/search/?keyword=4825061` | 404 | `FC2 - 404 Error` | - | `https://error.fc2.com/other/` |  |
| 12:57:44 | `https://adult.contents.fc2.com/ranking/` | 200 | `ランキングトップ - アダルト / FC2コンテンツマーケット` | - | same |  |

## Findings

- Redirect chain for `/article/4824605/` (redirects not followed): 302 to `/lk/services/id/login?anlad=3`, 302 to `https://fc2.com/ja/login.php?ref=payarticle`, 302 to `https://error.fc2.com/other/`, 404 `FC2 - 404 Error`. Verbatim in `docs/source-probes/PHASE2_MANUAL_OBSERVATIONS_20260920.md` section 2.
- The raw probe's `404` is therefore the end of a **login redirect**, not proof the work is absent. It is the same for both mandated IDs and for a browser-like User-Agent.
- `/search/?keyword=4825061` follows the identical chain (`anlad=5`).
- `/ranking/` returns 200 (`ランキングトップ - アダルト | FC2コンテンツマーケット`); the front page lists recent article ids (about 4.98M, so the site is current). Usable for discovering recent ids, not for looking one up.

## Risks / re-check trigger

If FC2 ever re-opens anonymous article pages this becomes the best source (it is the origin of every other source's data). Re-check trigger: `/article/<id>/` returning 200 without a session.
