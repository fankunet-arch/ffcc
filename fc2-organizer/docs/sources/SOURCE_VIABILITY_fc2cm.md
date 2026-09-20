# SOURCE_VIABILITY - fc2cm

- **Provider:** FC2CM (fc2cm.com; spec name 'FC2CMADB')
- **Status:** `PARTIAL`
- **Decision:** REJECT - stale, flaky, soft 404 (fails both mandated IDs)
- **Adapter:** none
- **Login/cookie needed:** not required
- **Cloudflare/anti-bot:** no challenge observed
- **Research date:** 2026-09-20 (UTC); machine evidence `docs/source-probes/PHASE2_PROBE_20260920.json`, human observations `docs/source-probes/PHASE2_MANUAL_OBSERVATIONS_20260920.md`.

## Summary

Alive but effectively frozen: its newest listed work is No.4699535, it resolves older ids (`1042815`, `4699535`) but no 2026 id, and reports missing works as HTTP 200 (a page titled `404`, or a 9-byte body `sql error`) instead of 404.

## Raw probe evidence (final pass, `tools/probe_sources.py raw`)

| UTC | Requested URL | HTTP | Page `<title>` | cf-mitigated | Final URL | Transport error |
|---|---|---|---|---|---|---|
| 12:58:22 | `https://fc2cm.com/?p=4825061&nc=0` | 200 | `` | - | same |  |
| 12:58:24 | `https://fc2cm.com/?p=4824605&nc=0` | 200 | `` | - | same |  |
| 12:58:27 | `https://fc2cm.com/?p=1042815&nc=0` | 200 | `` | - | same |  |

## Findings

- `/?p=4825061&nc=0` gives 200 with a page whose `<title>` is `404`; `/?p=4824605&nc=0` and `/?p=4979299&nc=0` give 200 with body `sql error`; `/?p=1042815&nc=0` gives 200 with the real Japanese title.
- The root page itself returned `sql error` on one attempt and real content on another seconds apart: intermittent backend failure.
- `db.fc2cm.com` (the spec's 'FC2CMADB' host name) serves only a cPanel default-page redirect.
- Any adapter would need body sniffing to tell missing from present because the HTTP status is uninformative. Not worth it for a source that cannot resolve either mandated ID.

## Risks / re-check trigger

n/a
