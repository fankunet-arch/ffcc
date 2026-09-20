# SOURCE_STATUS_MATRIX.md

Status: **SKELETON — no rows populated yet.**

Every row in this table must come from an actual live probe recorded under
`docs/source-probes/PHASE2_PROBE_<YYYYMMDD>.json` and detailed in a
`docs/sources/SOURCE_VIABILITY_<SOURCE_ID>.md` document. No row may be
filled in from a search-engine result, a name recognized from training
data, or an assumption that a site named in the spec is still live today.

This session could not populate any row: this sandbox's outbound network
policy blocks all non-allowlisted hosts, so no live request to any FC2
metadata site could be performed (see `docs/review/PHASE2_HANDOFF.md` for
the exact evidence). This file, the framework, and the probe tool are
ready; only the actual probing step is blocked pending wider network
access.

## Columns

| Column | Meaning |
|---|---|
| Source ID | Stable logical id (`SourceAdapter.source_id`); never changes with mirror domain. |
| Provider | Human-readable provider/site name. |
| Status | One of `VERIFIED`, `PARTIAL`, `BLOCKED`, `RATE_LIMITED`, `DEAD`, `REJECTED`, `EXPERIMENTAL` — must come from an actual probe, never guessed. |
| Verified IDs | Which of the probe-set numbers returned `SourceStatus.SUCCESS` (number + non-empty title) through the real adapter, if any. |
| Cookie | Whether any cookie is required for the lookup to work (`required` / `not required`). A source requiring a private login cookie cannot be `VERIFIED` per spec section 11. |
| CF | Whether a Cloudflare/anti-bot challenge was observed (`yes` / `no`). A source requiring bypass cannot be `VERIFIED`. |
| Adopted | Whether a real `SourceAdapter` subclass exists in `fc2_metadata_core/sources/adapters/` for this source. |

## Candidates to investigate (per spec section 6 — names only, not pre-approved)

- [ ] FC2 Official
- [ ] Aggregate/index candidate #1
- [ ] Aggregate/index candidate #2
- [ ] FC2CMADB
- [ ] FD2PPV
- [ ] FC2DB
- [ ] JavTen
- [ ] JavDB
- [ ] (any other 2026-current FC2 metadata/index source found during research)

## Status matrix (to be filled in from real probes)

| Source ID | Provider | Status | Verified IDs | Cookie | CF | Adopted |
|---|---|---|---|---|---|---|
| _pending_ | _pending_ | _pending_ | _pending_ | _pending_ | _pending_ | _pending_ |
