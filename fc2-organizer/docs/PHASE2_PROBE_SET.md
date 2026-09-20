# PHASE2_PROBE_SET.md

Status: **SKELETON — not yet populated with verified evidence.**

Per Phase 2 requirements, this document must record at least 5 known-valid
FC2 numbers used as the live probe set, each with a stated reason for why it
is believed genuinely valid (never a randomly guessed number whose 404 gets
misread as "source unavailable"). It must **not** be filled in from memory
or a search-engine snippet — each entry's "why known-valid" must point at
independently-checkable evidence gathered during live probing (e.g. the
number resolving successfully on more than one independent source, or
independent confirmation found during candidate research), recorded with a
real timestamp.

This session could not populate it: this sandbox's outbound network policy
currently blocks all non-allowlisted hosts (see
`docs/review/PHASE2_HANDOFF.md`), so no live request to any FC2 metadata
site — and therefore no independent verification of any candidate number —
could be performed. Fabricating "why known-valid" justifications without
that verification would violate the explicit requirement in spec section 8
("不要随机猜号码然后把 404 误判成 source 不可用" / do not guess numbers and
misread a 404 as source-unavailable) and section 40 (no fabricated
success). Once network access is available, this document must be filled
in per the template below and the mandatory pre-flight in
`docs/review/PHASE2_HANDOFF.md` re-run.

## Required entries (template)

| # | Canonical number | Why believed known-valid | Probe date/time (UTC) | Used in probes |
|---|---|---|---|---|
| 1 | `FC2-4825061` | **Mandated by spec** — must still be independently corroborated during live probing before being trusted as a positive control, not just asserted because it was named in the prompt. | _pending_ | _pending_ |
| 2 | `FC2-4824605` | **Mandated by spec** — same caveat as above. | _pending_ | _pending_ |
| 3 | _pending_ | _pending — must be corroborated by at least one independent live source lookup during Phase 2 research, not by search-engine snippet alone_ | _pending_ | _pending_ |
| 4 | _pending_ | _pending_ | _pending_ | _pending_ |
| 5 | _pending_ | _pending_ | _pending_ | _pending_ |

## Process once network access is available

1. For each candidate provider under investigation (see
   `docs/SOURCE_STATUS_MATRIX.md`), run
   `python3 tools/probe_sources.py raw <candidate lookup URL for FC2-4825061 and FC2-4824605>`
   first, since those two are mandated regardless of provider.
2. For the additional >=3 numbers, only add a row here once at least one
   live source lookup (not a snippet, not a memory guess) has returned a
   plausible, internally-consistent metadata page for it. Record which
   probe(s) corroborated it.
3. Re-run every `docs/sources/SOURCE_VIABILITY_<SOURCE_ID>.md` probe pass
   against the final 5+ IDs in this table, so every candidate is judged
   against the same number set.
4. Update this document's status line from **SKELETON** to **POPULATED**
   only once every row above has a real timestamp and a real, checkable
   justification.
