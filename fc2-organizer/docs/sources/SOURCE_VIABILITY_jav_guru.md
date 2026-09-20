# SOURCE_VIABILITY - jav_guru

- **Provider:** Jav Guru (jav.guru)
- **Status:** `REJECTED`
- **Decision:** REJECT - poor coverage
- **Adapter:** none
- **Login/cookie needed:** not required
- **Cloudflare/anti-bot:** no challenge observed
- **Research date:** 2026-09-20 (UTC); machine evidence `docs/source-probes/PHASE2_PROBE_20260920.json`, human observations `docs/source-probes/PHASE2_MANUAL_OBSERVATIONS_20260920.md`.

## Summary

`/?s=<n>` returns a real result list, but only 1 of 6 known-valid IDs (`4824605`) had a hit (English machine-translated title); nothing for the other five.

## Raw probe evidence (final pass, `tools/probe_sources.py raw`)

| UTC | Requested URL | HTTP | Page `<title>` | cf-mitigated | Final URL | Transport error |
|---|---|---|---|---|---|---|
| 12:58:44 | `https://jav.guru/?s=4825061` | 200 | `You searched for 4825061 &#8902; Jav Guru ⋆ Japanese porn Tu` | - | same |  |

## Findings

- Checked with a selector on the result headings after an initial mis-parse of mine (corrected before judging).

## Risks / re-check trigger

n/a
