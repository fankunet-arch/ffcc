# SOURCE_VIABILITY - javbus

- **Provider:** JavBus (www.javbus.com)
- **Status:** `BLOCKED`
- **Decision:** REJECT - age-verification interstitial
- **Adapter:** none
- **Login/cookie needed:** an age-gate click-through cookie would be needed
- **Cloudflare/anti-bot:** no challenge; age gate
- **Research date:** 2026-09-20 (UTC); machine evidence `docs/source-probes/PHASE2_PROBE_20260920.json`, human observations `docs/source-probes/PHASE2_MANUAL_OBSERVATIONS_20260920.md`.

## Summary

`/FC2-PPV-<n>` redirects to `/doc/driver-verify?referer=...` (title `Age Verification JavBus`). Getting past it means presenting a cookie set by the interstitial; not pursued, and JavBus's FC2 coverage was never established.

## Raw probe evidence (final pass, `tools/probe_sources.py raw`)

| UTC | Requested URL | HTTP | Page `<title>` | cf-mitigated | Final URL | Transport error |
|---|---|---|---|---|---|---|
| 12:58:36 | `https://www.javbus.com/FC2-PPV-4825061` | 200 | `Age Verification JavBus - JavBus` | - | `https://www.javbus.com/doc/driver-verify?referer=https%3A%2F%2Fwww.jav` |  |

## Findings

- Not investigated further: adopting it would first require deciding that scripting an age-gate cookie is acceptable, which is a product/policy call rather than a Phase 2 engineering one.

## Risks / re-check trigger

n/a
