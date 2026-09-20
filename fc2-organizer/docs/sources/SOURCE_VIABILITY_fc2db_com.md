# SOURCE_VIABILITY - fc2db_com

- **Provider:** FC2DB (fc2db.com - `.com` sibling)
- **Status:** `BLOCKED`
- **Decision:** REJECT - Cloudflare challenge (use `fc2db.net`)
- **Adapter:** none (`fc2db_net` covers this operator)
- **Login/cookie needed:** unknown
- **Cloudflare/anti-bot:** **yes** - `cf-mitigated: challenge`
- **Research date:** 2026-09-20 (UTC); machine evidence `docs/source-probes/PHASE2_PROBE_20260920.json`, human observations `docs/source-probes/PHASE2_MANUAL_OBSERVATIONS_20260920.md`.

## Summary

`https://fc2db.com/...` returns the Cloudflare challenge (403) for `/work/<id>/`, while `fc2db.net` serves the same catalogue without one.

## Raw probe evidence (final pass, `tools/probe_sources.py raw`)

| UTC | Requested URL | HTTP | Page `<title>` | cf-mitigated | Final URL | Transport error |
|---|---|---|---|---|---|---|
| 12:57:53 | `https://fc2db.com/work/4824605/` | 403 | `Just a moment...` | challenge | same |  |

## Findings

- `/work/4824605/` returns 403, `cf-mitigated: challenge`, `Just a moment...`. `/` and `www.fc2db.com/` also 403 (earlier probes).
- Not a separate provider for independence purposes: same brand as `fc2db_net`.

## Risks / re-check trigger

n/a
