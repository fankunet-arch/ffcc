# SOURCE_VIABILITY - fc2ppvdb

- **Provider:** FC2PPVDB (fc2ppvdb.com)
- **Status:** `BLOCKED`
- **Decision:** REJECT for Phase 2 - cannot be evaluated from this network
- **Adapter:** none
- **Login/cookie needed:** unknown
- **Cloudflare/anti-bot:** unknown (never reached the origin)
- **Research date:** 2026-09-20 (UTC); machine evidence `docs/source-probes/PHASE2_PROBE_20260920.json`, human observations `docs/source-probes/PHASE2_MANUAL_OBSERVATIONS_20260920.md`.

## Summary

Unreachable from this network: HTTPS fails certificate verification and plain HTTP returns a Spanish court-ordered IP-block notice. This is an environment fact, not proof the site is dead.

## Raw probe evidence (final pass, `tools/probe_sources.py raw`)

| UTC | Requested URL | HTTP | Page `<title>` | cf-mitigated | Final URL | Transport error |
|---|---|---|---|---|---|---|
| 12:58:16 | `https://fc2ppvdb.com/articles/4825061` | n/a | `` | - | `-` | `HttpConnectionError: [SSL: CERTIFICATE_VERIFY_FAILED] certificate veri` |
| 12:58:19 | `http://fc2ppvdb.com/articles/4825061` | 200 | `...` | - | same |  |

## Findings

- Resolves to `188.114.96.5`/`188.114.97.5` (shared with `onejav.com`). HTTPS gives `CERTIFICATE_VERIFY_FAILED: self-signed certificate`; the root page once timed out.
- `http://fc2ppvdb.com/articles/4825061` returns an HTTP 200 notice page: access to this IP blocked per the judgement of 18 Dec 2024 of Juzgado de lo Mercantil nº 6 de Barcelona (LaLiga / Telefónica). Text in manual observations section 4.
- Certificate verification was **not** disabled and no other route was used. Third-party reports (a 2024 mdcx issue: 'closed by DMCA'; a 2026 analytics page: traffic) are contradictory and were not used as evidence.
- Because it cannot be probed here it cannot count toward the Gate; re-probe from a network without this block.

## Risks / re-check trigger

If it is alive it is a rich source (actors curated by users, per the mdcx issue); worth re-checking from another network before Phase 3 finalizes its source list.
