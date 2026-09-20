# SOURCE_VIABILITY - javten

- **Provider:** JavTen (javten.com)
- **Status:** `BLOCKED`
- **Decision:** REJECT - Cloudflare challenge
- **Adapter:** none
- **Login/cookie needed:** unknown
- **Cloudflare/anti-bot:** **yes**
- **Research date:** 2026-09-20 (UTC); machine evidence `docs/source-probes/PHASE2_PROBE_20260920.json`, human observations `docs/source-probes/PHASE2_MANUAL_OBSERVATIONS_20260920.md`.

## Summary

Whole site (`/`, `/fc2`, `/search?q=...`) returns HTTP 403; the search request carries `cf-mitigated: challenge` / `Just a moment...`.

## Raw probe evidence (final pass, `tools/probe_sources.py raw`)

| UTC | Requested URL | HTTP | Page `<title>` | cf-mitigated | Final URL | Transport error |
|---|---|---|---|---|---|---|
| 12:58:29 | `https://javten.com/search?q=FC2-PPV-4825061` | 403 | `Just a moment...` | challenge | same |  |

## Findings

- Named in the spec's initial candidate list ('FC2DB/JavTen'); today's evidence is BLOCKED.

## Risks / re-check trigger

Re-check if the challenge is dropped.
