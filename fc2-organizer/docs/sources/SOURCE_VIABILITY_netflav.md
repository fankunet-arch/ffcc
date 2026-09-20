# SOURCE_VIABILITY - netflav

- **Provider:** Netflav (netflav.com)
- **Status:** `EXPERIMENTAL`
- **Decision:** NOT ADOPTED - reachable, but surplus to the Gate and low-quality titles
- **Adapter:** none
- **Login/cookie needed:** not required
- **Cloudflare/anti-bot:** no challenge observed
- **Research date:** 2026-09-20 (UTC); machine evidence `docs/source-probes/PHASE2_PROBE_20260920.json`, human observations `docs/source-probes/PHASE2_MANUAL_OBSERVATIONS_20260920.md`.

## Summary

`/search?keyword=<n>` returns 200 and embeds a `__NEXT_DATA__` JSON; for `4825061` and `4824605` it lists a hit (`code: 'fc2-ppv <n>'`, machine-translated Chinese title, date), for `4979299` (a 2026-09-19 release) it lists none.

## Raw probe evidence (final pass, `tools/probe_sources.py raw`)

| UTC | Requested URL | HTTP | Page `<title>` | cf-mitigated | Final URL | Transport error |
|---|---|---|---|---|---|---|
| 12:58:31 | `https://netflav.com/search?keyword=4825061` | 200 | `Netflav - 搜尋 / Search` | - | same |  |
| 12:58:33 | `https://netflav.com/search?keyword=4824605` | 200 | `Netflav - 搜尋 / Search` | - | same |  |

## Findings

- Coverage on 3 IDs tried: 2/3. The title is a machine translation prefixed with the code and would need cleaning. The Gate was met by three better sources, so no adapter was written (Phase 2 rule: probe first, adopt only what is needed and verified).

## Risks / re-check trigger

Candidate reserve if one of the adopted three is lost.
