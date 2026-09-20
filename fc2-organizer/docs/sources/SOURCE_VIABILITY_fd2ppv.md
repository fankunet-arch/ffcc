# SOURCE_VIABILITY - fd2ppv

- **Provider:** FD2 (fd2ppv.cc)
- **Status:** `BLOCKED`
- **Decision:** REJECT - Cloudflare challenge on work pages
- **Adapter:** none
- **Login/cookie needed:** unknown (never reached a work page)
- **Cloudflare/anti-bot:** **yes** - `cf-mitigated: challenge` / `Just a moment...` on every `/articles/<id>` and `/search`
- **Research date:** 2026-09-20 (UTC); machine evidence `docs/source-probes/PHASE2_PROBE_20260920.json`, human observations `docs/source-probes/PHASE2_MANUAL_OBSERVATIONS_20260920.md`.

## Summary

The site is alive and its list page (`/`) is public, but every per-work page returns a Cloudflare managed challenge (HTTP 403). Solving it would be a bypass, which Phase 2 forbids.

## Raw probe evidence (final pass, `tools/probe_sources.py raw`)

| UTC | Requested URL | HTTP | Page `<title>` | cf-mitigated | Final URL | Transport error |
|---|---|---|---|---|---|---|
| 12:58:07 | `https://fd2ppv.cc/` | 200 | `All Works - FD2` | - | same |  |
| 12:58:09 | `https://fd2ppv.cc/articles/4825061` | 403 | `Just a moment...` | challenge | same |  |
| 12:58:11 | `https://fd2ppv.cc/articles/4824605` | 403 | `Just a moment...` | challenge | same |  |

## Findings

- `/` returns 200 `All Works - FD2`, linking `/articles/<id>` for recent works, so ids equal FC2 numbers.
- `/articles/4825061`, `/articles/4824605` (and in manual checks `/articles/4979786`, `/articles/4979799`) return 403 challenge. `/search?q=...` redirects to `/actresses/?keyword=` which is also challenged.
- The spec's initial candidate list names FD2PPV; today's evidence is BLOCKED.

## Risks / re-check trigger

Re-check if the site drops the challenge or publishes an API.
