# PHASE2_PROBE_SET.md

Status: **POPULATED** (2026-09-20 UTC).

Known-valid FC2 numbers used to judge every candidate. Each row's justification is independently checkable: it names the live source(s) that resolved the number, with timestamps in the JSON evidence file. No number was guessed; a candidate's 404/no-hit was never read as 'source unavailable' without another source resolving the same number.

| # | Canonical number | Why believed known-valid (independent evidence) | Resolved by adopted adapter (Gate run 2026-09-20 13:02-13:03 UTC) |
|---|---|---|---|
| 1 | `FC2-4825061` | Mandated by the spec **and independently corroborated**: JavDB lists it (`【顔出し】ハーフ美人妻 ...`, 2026-01-02, 176 ratings) and 123AV serves a detail page (release 2026-01-02). FC2 Official cannot corroborate (login wall). fc2db.net answers 404 for it, which is a coverage gap of that source, not evidence of invalidity. | javdb, av123 |
| 2 | `FC2-4824605` | Mandated by the spec **and independently corroborated**: fc2db.net serves the full page (`※1/11まで初回限定90％OFF※【ハメ撮り】...`, 2026-01-04). Manually also seen as titles on Sukebei torrents, Netflav and Jav Guru (not adapter-recorded). JavDB (only near-misses) and 123AV (404) do not carry it. | fc2db_net |
| 3 | `FC2-4979299` | Seen on the fc2db.net front-page work list (a 2026-09-19 release); then SUCCESS on all three adopted sources, with the same Japanese title on fc2db_net and javdb. | fc2db_net, javdb, av123 |
| 4 | `FC2-4976588` | Seen on the fc2db.net front-page work list; SUCCESS on fc2db_net and javdb with matching titles. | fc2db_net, javdb |
| 5 | `FC2-1042815` | Chosen as an **old-id** control (about 1M range) from the fc2db.net front page; SUCCESS on fc2db_net and javdb (matching JP title); also resolves on fc2cm.com (manual, section 5). | fc2db_net, javdb |
| 6 | `FC2-4978035` | Seen on the fc2db.net front-page work list; SUCCESS on all three adopted sources. | fc2db_net, javdb, av123 |
| 7 | `FC2-4972767` | Seen on the fc2db.net front-page work list; SUCCESS on fc2db_net and javdb with matching titles. | fc2db_net, javdb |

## Deliberately excluded

- `FC2-4974437`: resolved only by fc2db.net, whose title for it is the placeholder-like `Searching for Your XXX`; JavDB has no exact hit and 123AV 404s. Not corroborated by a second source, so it is **not** in the probe set (kept in the evidence JSON: fc2db_net run 12:52:57).
- `FC2-9999999` / `FC2-99999999` / `FC2-4000000`: used only as negative controls to observe each site's 'missing' page format, never as evidence of validity.

## How the set was built

1. The two mandated numbers were probed first against every candidate.
2. Additional numbers were taken from current work lists on fc2db.net's front page (recent works, September 2026) plus one old-id control, then required to be resolved by at least two adopted sources, or (for the mandated two) by at least one independent source other than the prompt.
3. Every adopted adapter was then run against the whole set in one pass (see each `docs/sources/SOURCE_VIABILITY_<id>.md`).
