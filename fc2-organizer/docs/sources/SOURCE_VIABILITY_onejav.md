# SOURCE_VIABILITY - onejav

- **Provider:** OneJAV (onejav.com)
- **Status:** `BLOCKED`
- **Decision:** REJECT for Phase 2 - cannot be evaluated from this network
- **Adapter:** none
- **Login/cookie needed:** unknown
- **Cloudflare/anti-bot:** unknown
- **Research date:** 2026-09-20 (UTC); machine evidence `docs/source-probes/PHASE2_PROBE_20260920.json`, human observations `docs/source-probes/PHASE2_MANUAL_OBSERVATIONS_20260920.md`.

## Summary

Same ISP-level IP block as `fc2ppvdb.com` (identical addresses). Not evaluable here.

## Raw probe evidence (final pass, `tools/probe_sources.py raw`)

| UTC | Requested URL | HTTP | Page `<title>` | cf-mitigated | Final URL | Transport error |
|---|---|---|---|---|---|---|
| 12:58:42 | `https://onejav.com/search/fc2-ppv-4825061` | n/a | `` | - | `-` | `HttpConnectionError: [SSL: CERTIFICATE_VERIFY_FAILED] certificate veri` |

## Findings

- `https://onejav.com/search/fc2-ppv-...` gives `CERTIFICATE_VERIFY_FAILED: self-signed certificate` (resolves to `188.114.96.5`/`188.114.97.5`). Named in the public mdcx issue #243 as a candidate; never reached.

## Risks / re-check trigger

Re-probe from an unblocked network.
