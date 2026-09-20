# SOURCE_VIABILITY - supjav_missav

- **Provider:** SupJav (supjav.com) and MissAV (missav.ws)
- **Status:** `BLOCKED`
- **Decision:** REJECT - Cloudflare challenge
- **Adapter:** none
- **Login/cookie needed:** unknown
- **Cloudflare/anti-bot:** **yes**
- **Research date:** 2026-09-20 (UTC); machine evidence `docs/source-probes/PHASE2_PROBE_20260920.json`, human observations `docs/source-probes/PHASE2_MANUAL_OBSERVATIONS_20260920.md`.

## Summary

Both return HTTP 403 with `cf-mitigated: challenge` for a per-number lookup URL.

## Raw probe evidence (final pass, `tools/probe_sources.py raw`)

| UTC | Requested URL | HTTP | Page `<title>` | cf-mitigated | Final URL | Transport error |
|---|---|---|---|---|---|---|
| 12:58:38 | `https://supjav.com/?s=FC2-PPV-4825061` | 403 | `Just a moment...` | challenge | same |  |
| 12:58:40 | `https://missav.ws/en/fc2-ppv-4825061` | 403 | `Just a moment...` | challenge | same |  |

## Findings

- Probed as generic aggregator candidates; neither reachable without solving a challenge.

## Risks / re-check trigger

n/a
