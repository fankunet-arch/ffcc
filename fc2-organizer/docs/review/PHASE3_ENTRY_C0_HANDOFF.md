# PHASE3_ENTRY_C0_HANDOFF.md

```text
Phase: Phase 3 Entry Gate — C0 Hardening
(Phase 2 is CLOSED: independent Level 2 review = PASS WITH NON-BLOCKING NOTES.
 This is not a Phase 2 R1, and it is not Phase 3 implementation.)

C0 Base (= Phase 2 Reviewed Docs Head):
4e7883e87bd6195080d1eb5afcefda0a8897600d

Phase 2 Reviewed Code Head:
3a23e6fa9a351b5c3bc6d2159028177616f98371

C0 Code Review Candidate (P3_ENTRY_C0_CODE_HEAD):
8b16bdbc236fac422074994622670905c8d9b2ec

Review range:
4e7883e87bd6195080d1eb5afcefda0a8897600d..8b16bdbc236fac422074994622670905c8d9b2ec

C0 Docs Head (P3_ENTRY_C0_DOCS_HEAD):
the commit "docs(review): add Phase 3 entry C0 handoff" whose only change is
this file and whose parent is the Code Review Candidate above. A commit cannot
contain its own hash, so it is identified by that rule and reported in the
hand-back message; `git log --oneline -2` shows it on top of 8b16bdb.

Branch:
claude/phase-0-amane-integration-fnvhpq
```

**Not a PASS declaration.** This is a candidate for C0 independent closure
review. **Phase 3 functional implementation has NOT started.**

## Required Closure Set

Only C0-01..C0-05 were touched. P2-R-05..P2-R-12 were deliberately left alone
(see *Deferred backlog*).

| ID | Reviewer finding | Status |
|---|---|---|
| C0-01 | P2-R-01 canonical FC2 number boundary | implemented |
| C0-02 | P2-R-02 catastrophic parser regex behaviour | implemented |
| C0-03 | P2-R-03 JavDB layout drift reported as `NOT_FOUND` | implemented |
| C0-04 | P2-R-04 `runtime` unit not frozen | implemented (unit frozen) |
| C0-05 | P2-R-13 PHASE2_HANDOFF factual errors | implemented |

### C0-01 — canonical FC2 number boundary

**Root cause.** `^FC2-\d{5,8}$` in a Python `str` pattern: `\d` matches every
Unicode decimal digit and `$` also matches just before a trailing `"\n"`. So
`"FC2-1234567\n"`, `"FC2-１２３４５６７"` (fullwidth) and `"FC2-٤٨٢٤٦٠٥"`
(Arabic-Indic) passed `is_valid_fc2_number` and therefore
`require_canonical_number`; the newline then reached the request layer and
leaked a bare `httpx.InvalidURL`.

**Fix (`normalize/fc2_number.py`).**
- Frozen grammar: `FC2-[0-9]{5,8}`, full string. `CANONICAL_FC2_PATTERN` is
  now `\AFC2-[0-9]{5,8}\Z` and `is_valid_fc2_number` uses `fullmatch`.
- `normalize_fc2_number`'s token pattern uses `[0-9]` too, plus `(?<!\d)` /
  `(?!\d)` guards, so a clean-looking token glued to a *non-ASCII* digit
  (`"FC2PPV-1234567１"`) is refused rather than truncated at the ASCII part.
  Both functions therefore share one digit semantics. CJK noise glued to a
  token (`[广告]FC2PPV-1234567高画質.mp4`) still works.
- All of `FC2-1234567\n`, `FC2-１２３４５６７`, `FC2-٤٨٢٤٦٠٥`, `FC2-1234567XYZ`,
  `XFC2-1234567` are rejected; `FC2-4825061` still passes.

**Adapters.** `require_canonical_number` already calls `is_valid_fc2_number`
first, so the fix propagates; it is *proved* per adapter:
`tests/unit/sources/adapters/test_adapter_canonical_boundary.py` hands each of
`fc2db_net`, `javdb`, `av123` a recording fake client and 10 bad values
(including `..`/`?` injection attempts and `""`) and asserts
`InvalidCanonicalNumberInputError` **and** `client.requested_urls == []`.

**Tests.** `tests/unit/core/test_fc2_number_canonical_boundary.py` (36) and the
adapter file above (34). Checked against the old grammar: 24 of these fail
(the reviewer's three values reach the fake client), all pass after the fix.

### C0-02 — parser catastrophic regex behaviour

**Root cause.** Lazy `.*?` next to `\s*`, unanchored `[^>]*` runs and
whole-page `re.search` in all three parsers: an unclosed relevant tag followed
by whitespace is super-linear. Reviewer measurements (kept here as the
regression targets): fc2db_net 2000 spaces ≈ 2.9 s / 4000 ≈ 63 s; av123 2000 ≈
7.5 s; javdb 2000 ≈ 3.7 s. The parsers run synchronously inside `async fetch`;
Phase 3 will run several sources concurrently.

**Options evaluated, with data.** The stdlib `html.parser.HTMLParser` was
measured on the project's Python 3.12.10 and **rejected**: `"<!--" * 20_000`
(80 KB) = 3.2 s, `"<a " * 100_000` and `'<a x="' * 50_000` did not finish in
8 s. Catching a timeout was not considered (a synchronous regex cannot be
interrupted; the complexity boundary is what must be fixed).

**Fix.** New `sources/adapters/_scan.py`; the three parsers are rewritten on it.
Every primitive is bounded by construction:
1. locate candidates with `str.find` on a distinctive marker (C speed, linear);
2. cap how many candidates are examined (`MAX_ATTEMPTS = 2000`, plus small
   per-use caps such as 20 headings, 40 info rows, 400 tag links, 200 items);
3. run regexes only on windows of at most `MAX_TAG_CHARS = 1500` or a caller
   `max_len`, anchored with `match(text, pos, endpos)`, never an unanchored
   `search` over the page;
4. patterns are unambiguous (disjoint first characters, possessive `*+`,
   Python >= 3.11 = the project minimum), so they cannot backtrack inside a
   window either.
`_common._TAG_RE` (`<[^>]+>` → `<[^<>]*+>`), the Cloudflare-title check and
the duration regex were made linear too. An element that is not closed inside
its window is *not found* (never "everything to end of page"). Transport
`DEFAULT_MAX_RESPONSE_BYTES` (5 MiB) is untouched.

**Result.** `tests/support/adversarial_html.py` builds 46 cases per run
(unclosed relevant tag + 2000 / 4000 / 5 MiB whitespace and text; `<h1 `,
`<a `, `<!--`, `<`, `class="`, `<div class="item">`, `<strong>`, unbalanced
quotes repeated to 5 MiB; and a *valid* real fixture followed by hostile
tails: unclosed / nested JSON-LD, `/work-tags/` spam, `watch__info-row` spam,
unclosed `<dd>`, `video-title` / `item` / `movie-list` spam). Worst case in my
run: **10.4 ms on 5 MiB** (all three parsers, all cases). Hostile pages give
`PARSE_ERROR` / `INVALID_RESPONSE`; a genuine page with junk appended still
parses.

**Regression test design.** `test_parser_adversarial.py` runs the cases in a
**child process** (Python's `re` holds the GIL, so an in-process watchdog
cannot interrupt a catastrophic pattern) with a 90 s overall timeout and a
1.0 s per-case budget (~100x CI headroom over the measured ms, still ~3x
*below* the reviewer's smallest reproduction). Verified against the previous
parsers: the test **fails cleanly with "exceeded 90 s"** (they do not finish).

### C0-03 — JavDB layout drift is not `NOT_FOUND`

Frozen behaviour (also the module docstring and
`test_adapter_javdb_semantics.py`, 29 tests):

| Page | Result |
|---|---|
| result list, >=1 candidate number parsed, one is the requested number with a title | `SUCCESS` |
| result list, >=1 candidate number parsed, none exact (fuzzy near-misses only) | `NOT_FOUND` |
| requested number identified but title missing/blank | `PARSE_ERROR` (never falls back to `NOT_FOUND`) |
| zero-result page: explicit `empty-message` block | `NOT_FOUND` |
| result list present but **no** candidate number parseable (renamed `item` / `video-title` class, `<strong>` replaced, empty list container), or neither list nor `empty-message` | `INVALID_RESPONSE` (chosen over `PARSE_ERROR`: the page no longer satisfies the source contract) |

- A *candidate number* is a `<strong>CODE</strong>` in the item's `video-title`
  element (any studio code). The `N` in `listed N other number(s)` is the
  number of candidates actually **parsed**, not HTML chunks (test: 4 item
  elements, 2 readable → "2").
- Matching is by whole CSS class *token*: `class="item "`, `" item"`,
  `"item is-x"`, `"is-x item"`, `"video-title is-clamped"`, single-quoted
  attributes all still parse. A *renamed* class is `INVALID_RESPONSE`.
- If at least one number parses, the layout is still recognisable, so a
  drifted sibling item does not turn a normal miss into `INVALID_RESPONSE`
  (tested, and stated here so a reviewer can disagree).
- Real fuzzy page `FC2-4824605` → `NOT_FOUND`, "listed 2 other number(s)"
  (`FC2-1824605`, `FC2-4724605`): fixture test **and** live smoke below.
- 17 of the 29 fail against the previous parser (drift returned `NOT_FOUND`).

### C0-04 — `runtime` unit frozen: whole minutes

Decision recorded in `docs/specifications/FC2_METADATA_CORE_CONTRACT.md`
§2.1b (new; §2.1 table row updated) and the `NormalizedMetadata` docstring:

```text
runtime: int | None, unit = whole minutes, >= 0
seconds are truncated (not rounded) when converting clock-duration values
"55:23" -> 55   "1:02:03" -> 62   "55:59" -> 55   invalid -> None
```

Rationale: Kodi `<runtime>` is minutes only. The unit was **frozen at Phase 3
Entry C0**; Phase 1 froze only the type. The incorrect docstring claim that
the Core already had an "NFO-facing minutes" convention was removed from
`_common.duration_to_minutes` (no other occurrence exists in the repo).
The three adapters already emitted minutes, so their behaviour is unchanged.
`duration_to_minutes` was also made stricter and ASCII-only (`[0-9]`, seconds
<= 59, h:mm:ss needs two-digit minutes <= 59, input longer than 64 chars → `None`):
`"55:75"`, `"1:2:03"`, Arabic-Indic / fullwidth digits, ISO-8601 `PT55M23S`
are `None`. Tests: `test_runtime_minutes.py` (45) + existing
`test_adapter_common.py`, incl. end-to-end through the fc2db_net and av123
parsers.

### C0-05 — `PHASE2_HANDOFF.md` factual corrections

Only the reviewer-identified facts, with a short visible correction note in the
file: (1) removed the "Current Docs Head: reported externally" placeholder →
`Phase 2 Reviewed Docs Head: 4e7883e8…`; (2) replaced "all my commits are
local; nothing pushed" with the true push/review status; (3) live near-misses
of `FC2-4824605` are `FC2-1824605` / `FC2-4724605` (not `FC2-1825061`);
(4) test count recorded as **309 collected / 309 passed**, with the `45be2b7`
"80 new offline tests" wording noted as a rough historical commit-message
description. **No Git history was amended.**

## Files changed (`4e7883e..8b16bdb`)

```text
M docs/review/PHASE2_HANDOFF.md
M docs/specifications/FC2_METADATA_CORE_CONTRACT.md
M src/fc2_metadata_core/models/metadata.py                 (docstring only)
M src/fc2_metadata_core/normalize/fc2_number.py
M src/fc2_metadata_core/sources/adapters/_common.py
A src/fc2_metadata_core/sources/adapters/_scan.py
M src/fc2_metadata_core/sources/adapters/av123.py          (parser rewritten)
M src/fc2_metadata_core/sources/adapters/fc2db_net.py      (parser rewritten)
M src/fc2_metadata_core/sources/adapters/javdb.py          (parser rewritten, semantics)
A tests/support/adversarial_html.py
A tests/unit/core/test_fc2_number_canonical_boundary.py
A tests/unit/sources/adapters/test_adapter_canonical_boundary.py
A tests/unit/sources/adapters/test_adapter_javdb_semantics.py
A tests/unit/sources/adapters/test_parser_adversarial.py
A tests/unit/sources/adapters/test_runtime_minutes.py
```

No change to `http/`, `models/source_result.py`, the registry, the probe tool,
or any Phase 2 evidence JSON.

## Offline tests

```text
Python 3.12.10
python -m pytest --collect-only -q   -> 459 tests collected
python -m pytest -v                  -> 459 passed
python -m pytest -q                  -> 459 passed, 1 warning
```

| | count |
|---|---|
| collected | **459** |
| passed | **459** |
| failed | 0 |
| skipped | 0 |

(The one warning is the known, unrelated `PytestCacheWarning` from the
undeletable, git-ignored `.pytest_cache` directory — see the Phase 2 handoff.)

Change from the 309 at the C0 Base: **+150** = 149 in the five new test files
(36 + 34 + 29 + 5 + 45) + 1 because
`tests/contract/test_core_independent_of_amane.py` is parametrized over every
module and now also covers `_scan`.

**Regression preserved (all in the 459):** Phase 0 F-02/F-03 dirty-filename
positive/negative set (`test_normalize_fc2_number.py`, 41, unchanged);
Phase 1 R1/R2 closure (`test_metadata.py` 68, `test_source_result.py` 47,
unchanged); F4 closure (`test_core_independent_of_amane.py`, module-set
parametrization now 27, includes the new module); Phase 2 adapter and
framework tests (fc2db_net 17, javdb 17, av123 15, common 24, registration 3,
base 24, registry 10, fake e2e 9, transport 8 — all unchanged and green).

## Live smoke (after the parser changes)

At Code Head `8b16bdb`, `tools/probe_sources.py adapter --no-record`
(`--delay-seconds 2.5`, one request per lookup, no cookies), 2026-09-20
15:10:23–15:10:37 UTC. **`docs/source-probes/PHASE2_PROBE_20260920.json` was not
touched** (`--no-record`).

| Source | Number | HTTP | Result | Notes |
|---|---|---|---|---|
| `fc2db_net` | FC2-4824605 | 200 | **SUCCESS** | canonical number, non-empty JP title, 9 fields |
| `fc2db_net` | FC2-4979299 | 200 | **SUCCESS** | 9 fields |
| `javdb` | FC2-4825061 | 200 | **SUCCESS** | 6 fields |
| `javdb` | FC2-4979299 | 200 | **SUCCESS** | 6 fields |
| `av123` | FC2-4825061 | 200 | **SUCCESS** | 6 fields |
| `av123` | FC2-4979299 | 200 | **SUCCESS** | 6 fields |
| `javdb` (negative) | FC2-4824605 | 200 | **NOT_FOUND** | "search for FC2-4824605 listed 2 other number(s), none exact" |

Populated fields per source are identical to the Phase 2 Gate run (the
rewrites changed how pages are scanned, not what is extracted).

## Behaviour changes a reviewer may want to challenge

1. `<h1>` headings must now be *closed* within 2000 characters; an unclosed
   heading is "not found" (`PARSE_ERROR`), never read as a giant title.
2. Scan caps (2000 marker hits, 200 javdb items, 400 tag links, ...) silently
   truncate absurdly large legitimate pages. Real pages are far below them
   (fc2db ~60 KB, av123 ~43 KB, javdb list ~30 KB, ~40 items).
3. Tag names / closing tags are matched **lowercase**, as the adopted sources
   emit them (the old regexes were case-sensitive too, except JSON-LD's
   `<script type>` match).
4. `duration_to_minutes` rejects more malformed input than before (seconds > 59
   etc.) — a tightening, and only ever yields `None`.
5. The parsers are still synchronous CPU work inside `async fetch`; C0 makes
   the cost *bounded* (milliseconds at the 5 MiB cap), it does not move it off
   the event loop.
6. javdb still unescapes the title attribute twice (kept as-is on purpose:
   P2-R-10 is deferred, and changing it is outside the C0 set).

## Deferred backlog (NOT closed here — unchanged)

| ID | Finding | Note |
|---|---|---|
| P2-R-05 | probe `anti_bot_hint` fires on `cf-ray` alone | LOW, tooling |
| P2-R-06 | probe record `requested_url` is really the final URL | LOW, tooling |
| P2-R-07 | transport-level failure results carry `elapsed_ms = 0` | LOW |
| P2-R-08 | malformed `base_url` surfaces a raw exception | **re-evaluate** when Phase 3 config/source settings feed `base_url` |
| P2-R-09 | timeout is per-phase, not a wall-clock deadline | **re-evaluate** when Phase 3 scheduling depends on per-source deadlines |
| P2-R-10 | javdb title double-unescape | LOW (see above) |
| P2-R-11 | registry factory validation | **re-evaluate** when Phase 3 dispatch depends on it |
| P2-R-12 | classification nuances | **re-evaluate** when Phase 3 consumes `SourceStatus` semantics for retry decisions |

P2-R-08, P2-R-09, P2-R-11 and P2-R-12 must be re-assessed when a Phase 3
component starts to *depend* on the behaviour in question, not before.

**F3 — DEFERRED (unchanged).** **F5 — DEFERRED (unchanged).** Both are Phase 0 /
Phase 1 independent-review non-blocking findings whose definitions live in
those review reports (this repository only records the ids: see
`PHASE1_R1_HANDOFF.md`, `PHASE1_R2_HANDOFF.md`); they must be closed no later
than before Phase 5 integration. **F4 stays CLOSED** (still enforced by the
module-parametrized contract test, which now also covers `_scan`).

## Phase 3 functional implementation: NOT STARTED

Not implemented in this round, and no code for them exists: multi-source
fan-out, priority scheduler, field merge, aggregation, retry/backoff, circuit
breaker, batch processing, Amane adapter. C0 is the Phase 3 *entry gate*, not
the aggregator.

**READY FOR C0 INDEPENDENT CLOSURE REVIEW** — not "C0 PASS", not "Phase 3 PASS".
