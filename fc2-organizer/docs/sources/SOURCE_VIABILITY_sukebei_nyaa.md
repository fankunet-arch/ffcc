# SOURCE_VIABILITY - sukebei_nyaa

- **Provider:** Sukebei (sukebei.nyaa.si)
- **Status:** `REJECTED`
- **Decision:** REJECT - free-text torrent names are not metadata
- **Adapter:** none
- **Login/cookie needed:** not required
- **Cloudflare/anti-bot:** no challenge observed
- **Research date:** 2026-09-20 (UTC); machine evidence `docs/source-probes/PHASE2_PROBE_20260920.json`, human observations `docs/source-probes/PHASE2_MANUAL_OBSERVATIONS_20260920.md`.

## Summary

A torrent index. `?q=<n>` returns many rows for a known work, each with a different uploader-typed title (`[H265 1080p] FC2-PPV-...`, `FC2PPV-...`, `FC2 PPV ...`, `+++ FC2-PPV-...`, mixed JP/CN). There is no canonical title to extract.

## Raw probe evidence (final pass, `tools/probe_sources.py raw`)

| UTC | Requested URL | HTTP | Page `<title>` | cf-mitigated | Final URL | Transport error |
|---|---|---|---|---|---|---|
| 12:58:46 | `https://sukebei.nyaa.si/?f=0&c=0_0&q=4825061` | 200 | `4825061 :: Sukebei` | - | same |  |

## Findings

- Useful only as corroboration that a number exists, never as a metadata source.

## Risks / re-check trigger

n/a
