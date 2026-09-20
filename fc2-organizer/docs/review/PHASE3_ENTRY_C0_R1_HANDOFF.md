# PHASE3_ENTRY_C0_R1_HANDOFF.md

```text
Phase: Phase 3 Entry Gate — C0 R1 (incremental closure round)
Closes:  C0-R1-01 only
Not touched: C0-01, C0-03, C0-04, C0-05 (CLOSED by the previous closure review)

Base (= previous C0 Docs Head):
c0989062e489898b6d73b0814b251b1841e0c469

Previous C0 Code Head (reviewed, closure verdict FAIL on C0-R1-01):
8b16bdbc236fac422074994622670905c8d9b2ec

C0 R1 Code Review Candidate (C0_R1_CODE_HEAD):
c8e185e02454bcbdcf6c531d15d0985c5a7142b2
  = 7a9020d625b04a90f093b3ce0706f685934f33d5  fix(source): bound JavDB total parse cost
  + c8e185e02454bcbdcf6c531d15d0985c5a7142b2  test: correct the performance claim in the adversarial suite docstring
    (comment/docstring only; code identical to 7a9020d)

Review range:
c0989062e489898b6d73b0814b251b1841e0c469..c8e185e02454bcbdcf6c531d15d0985c5a7142b2

C0 R1 Docs Head (C0_R1_DOCS_HEAD):
the commit "docs(review): add Phase 3 entry C0 R1 handoff" whose parent is the
Code Review Candidate above (it adds this file and the correction note in
PHASE3_ENTRY_C0_HANDOFF.md). A commit cannot contain its own hash, so it is
identified by that rule and reported in the hand-back message.

Branch:
claude/phase-0-amane-integration-fnvhpq
```

**Not a PASS declaration. Phase 3 functional implementation has NOT started;
the Phase 3 Aggregator Lock is not lifted.**

## C0-R1-01 — original reproduction (independent reviewer)

The C0 fix removed the catastrophic regexes, but the JavDB parser's *total* cost
was still unbounded in practice. Reviewer measurements against `8b16bdb`, on a
page built from many JavDB items whose opening tags repeatedly spell the
class-token markers `video-title` / `meta` among filler:

| Page size | Reviewer-measured time |
|---|---|
| ~732 KiB | ~1.2 s |
| ~1.5 MiB | 3.8–4.5 s |
| ~1.8 MiB | ~5.5 s |
| real JavDB fixture | ~2.8 ms |

Conclusion drawn by the reviewer, and accepted here: **a per-primitive cap is not
an acceptable total parser bound.**

My own reconstruction of that shape (the reviewer's exact page was not available to me;
it is rebuilt from the description, see *Reviewer-shaped regression*) reproduced the
slowdown on the **previous C0 parser** on this machine — measured numbers, next to the
fixed parser's, are in *Before / after timing* below.

## Root cause

`parse_javdb_search_page` (C0) found each of `item`, `video-title`, `meta` by
*marker occurrence*: `iter_class_tags(html, token)` did `str.find(token)`, then for
**every** occurrence re-located the enclosing opening tag (`rfind` +
`open_tag_at`, up to 1500 chars) and re-ran `parse_attrs` on it (a Python-level
loop, ~one iteration per attribute token). Per page that is:

```text
~200 items
  x  several lookups per item (video-title, meta, <a>, <img>) each allowed 5-20 attempts
  x  one re-scan + re-parse of the SAME opening tag per marker occurrence
  x  up to ~700 attribute tokens per 1500-char tag (dense one-character "attributes")
```

Each factor was individually capped (`MAX_ATTEMPTS`, `limit=20`, `MAX_TAG_CHARS`),
but the caps multiplied. The C0 adversarial suite only had *flat* inputs and never
combined these factors, which is why it reported 10.4 ms.

## Implementation approach

Principle recorded in `_scan.py` (rule 5): **work must be shared, not repeated.**

`sources/adapters/_scan.py` (additive: existing helpers unchanged except for one
optional argument):
- `collect_class_hits(html, wanted, max_chars, max_probes)` — **one pass** over
  the page's quoted `class="..."` attributes. Each occurrence of the word `class`
  costs one anchored, bounded regex match; nothing is re-scanned. Returns the hits
  for the wanted tokens **and a `truncated` flag** (probe budget exhausted, or the
  page continues past the scan window with more `class` attributes).
- `first_open_tag(html, name, start, end, attempts=3)` — first opening tag in a
  region, a constant number of candidates.
- `parse_attrs(..., max_attrs=None)` — optional cap on attribute tokens parsed;
  JavDB passes 16 (real tags carry 3–6).

`sources/adapters/javdb.py`: `parse_javdb_search_page` rewritten:
1. one `collect_class_hits` pass for `movie-list`, `empty-message`, `item`,
   `video-title`, `meta`;
2. per item a **fixed** number of bounded lookups, positions from the
   already-collected hits via `bisect`: the `video-title` tag parsed **once**
   (`open_tag_containing`), its `<strong>` code read from a bounded window,
   at most 3 anchors and 3 images tried, `meta` parsed once. No opening tag is
   parsed twice and nothing is located per marker occurrence.

Total work is therefore a formula of named constants, not of page content:

```text
<= _MAX_CLASS_PROBES (8000) small anchored matches           [one pass]
 + _MAX_ITEMS (200) x (constant number of windows, each <= 8000 / 3000 / 1500 chars)
```

**Explicit budgets, sized from real data.** A real result page fetched live during
this round (`q=FC2-PPV-48250`, 8 items): **31,459 chars total, list starts at char
23,159, largest item region 779 chars, 290 `class` attributes on the whole page
(~25 per item), 444 tags**. Extrapolating to a full 40-item page: ~1200 `class`
words, ~36 KB. Budgets (`javdb.py`): scan window **512 KiB** (~15x), class probes
**8000** (~6x a 40-item page; ~1.5x even 200 items x 25), **200** items. I did **not**
lower the 200-item cap to hide the problem. *(Wider queries such as `q=FC2` and
`q=FC2-PPV-49` returned HTTP 403 with an 8-byte body, so no larger real page was
obtained; the headroom above is extrapolation from the 8-item page.)*

**Budget exhaustion is never `NOT_FOUND`.** If the scan stopped at a cap (more than
8000 `class` words, a page longer than 512 KiB that still holds `class`
attributes, or more than 200 items) and no exact hit was found, the parser has not
seen the whole page, so the result is `INVALID_RESPONSE` ("scan budget reached …
cannot conclude not found"). An exact hit found before the budget ran out is still
`SUCCESS`; an explicit `empty-message` is still `NOT_FOUND`; a large page with
*no more `class` attributes past the window* is not treated as truncated. (Tests:
`test_javdb_total_cost.py`.)

No thread / signal / asyncio timeout wraps the synchronous parser; the complexity
itself is bounded.

## Reviewer-shaped regression

`tests/support/adversarial_javdb.py` (built programmatically; no large fixture files)
and `tests/unit/sources/adapters/test_javdb_total_cost.py` (14 tests).

Shapes, each at **~750 KiB, ~1.5 MiB, ~3 MiB and ~5 MiB** (the transport cap), through the
**real `parse_javdb_search_page`**; the headline shape also through the **real
`JavdbAdapter.fetch()` with a fake HTTP client**:

| Shape | What multiplies |
|---|---|
| **reviewer-shaped**: 200 items, real `video-title` first, `meta` element absent, each item's `<a>` opening tag stuffed with ~1.4 KB of one-character attribute tokens spelling `meta` / `video-title` / `item` | `meta` lookup x marker occurrences x attribute tokens x items |
| dense tags per item: as many dense non-detail `<a>` / `<img>` tags as fit the per-item window | anchor / image lookups |
| `item` marker spelled in every opening tag | the item-list scan |
| markers inside one long quoted attribute value per item | (control: cheap even on old code) |
| **valid exact hit followed by the hostile shape** | real data must survive |
| window-filling max work: 200 items packed into the 512 KiB scan window, each using every fixed lookup to the full | the worst case the new bound allows |
| class-attribute spam | probe-budget exhaustion |

The run happens in a **child process with a 120 s hard timeout** (`re` holds the
GIL; a regression must be killed from outside, never waited on). Budgets: **0.5 s**
per hostile case (~10x the fixed parser's worst), and always below the C0 suite's
existing **1.0 s**. Guard tests also assert the generator stays hostile (items >= 200,
>= 9000 marker occurrences, sizes within 2 % of the label) so it cannot pass vacuously.
The 5 MiB C0 suite (`adversarial_html.py`, now 51 cases) gained five
"dense-attribute" guard cases for `av123` / `fc2db_net` (their measured worst is
~13 ms; they have no items x lookups multiplication).

## Before / after timing (same machine, same cases)

Windows 11, Python 3.12.10, single run each; absolute numbers vary by machine, the
ratio and the order of magnitude are the point. Reproduce with
`PYTHONPATH="src;tests" python -m support.adversarial_javdb` (prints one JSON row
per case).

Headline shape (reviewer-shaped), `parse` path / `fetch` path:

| Size | **Before** (C0 `8b16bdb`) | **After** (`c8e185e`) | Budget |
|---|---|---|---|
| ~750 KiB | 864 ms / 862 ms | 16.4 ms / 15.8 ms | 500 ms |
| ~1.5 MiB | 815 ms / 1738 ms | 5.5 ms / 5.5 ms | 500 ms |
| ~3 MiB | 2154 ms / 2038 ms | 2.3 ms / 5.0 ms | 500 ms |
| ~5 MiB | 2158 ms / 2361 ms | 1.4 ms / 3.8 ms | 500 ms |

All 26 cases: **before — 21 of 26 over budget, worst 2.36 s; after — 0 over budget,
worst 40.4 ms** (window-filling max work, 200 items fully parsed). The other shapes
after: dense tags per item 6–24 ms, `item` in every tag 2–10 ms, valid hit + hostile
tail 2–12 ms (all `SUCCESS`), class spam 6 ms. The real fixture parses in ~0.5 ms.
(Note: at >= 750 KiB the fixed parser returns after the 512 KiB scan window, so the
large-size rows are *cheaper* than the window-filling row, which is the true worst.)

On the reviewer's own numbers (1.2 s at 732 KiB, 3.8–4.5 s at 1.5 MiB), my
reconstruction reproduced the *pattern* on the C0 code (0.9–2.4 s here, faster machine or
slightly different token density) and does not exceed ~46 ms afterwards. **The
reviewer should re-run their own reproduction against `c8e185e`**; I cannot claim to
have used their exact page.

Verification that the new tests catch the old code: with the C0 `javdb.py` / `_scan.py`
swapped back in, `test_javdb_total_cost.py` gives **5 failed / 9 passed** (the budget
test plus the four budget-exhaustion semantics tests), completing in ~33 s.

## Correctness preserved (C0-03 frozen semantics)

Unchanged and re-verified by the existing 29-test
`test_adapter_javdb_semantics.py` plus the real fixtures:

| Page | Result |
|---|---|
| list + parsed candidate(s), none exact | `NOT_FOUND` |
| list, zero parseable candidate | `INVALID_RESPONSE` |
| exact number, no title | `PARSE_ERROR` |
| explicit `empty-message` | `NOT_FOUND` |
| exact valid result | `SUCCESS` |
| real fuzzy page `FC2-4824605` (near-misses `FC2-1824605`, `FC2-4724605`) | `NOT_FOUND`, "listed 2 other number(s)" |

Class-token tolerance (`class="item "`, extra CSS classes, single quotes,
`video-title is-x`) and the parsed-candidate count in the `NOT_FOUND` detail are
unchanged (same tests, all green).

Behaviour changes to be aware of (challenge them):
1. `class` must be a lower-case, **quoted** attribute (`class="…"` / `class='…'`);
   unquoted `class=item` and `CLASS=` are no longer recognised. JavDB emits
   lower-case quoted `class`; this is documented in `collect_class_hits`.
2. Per item only the **first 3** `<a>` / `<img>` tags are examined for the detail
   link / cover (was 10 / 5). The real item has both as its first tags.
3. Budget exhaustion with no exact hit is `INVALID_RESPONSE` (new, see above).
4. The JavDB title attribute is still unescaped twice — **unchanged on purpose**
   (P2-R-10 is deferred).

## Offline tests

```text
Python 3.12.10
python -m pytest --collect-only -q   -> 473 tests collected
python -m pytest -v                  -> 473 passed
python -m pytest -q                  -> 473 passed, 1 warning
```

| | count |
|---|---|
| collected | **473** |
| passed | **473** |
| failed | 0 |
| skipped | 0 |

(+14 vs the 459 of the previous C0 candidate: all in `test_javdb_total_cost.py`. The
one warning is the known `PytestCacheWarning` from the undeletable, git-ignored
`.pytest_cache`.)

Preserved and green inside the 473: Phase 0 F-02/F-03 dirty-filename set
(`test_normalize_fc2_number.py`, 41); Phase 1 R1/R2 (`test_metadata.py` 68,
`test_source_result.py` 47); **F4** (`test_core_independent_of_amane.py`, 27, module
parametrization covers `_scan`); Phase 2 adapters/framework (fc2db_net 17, javdb 17,
av123 15, common 24, registration 3, base 24, registry 10, fake e2e 9, transport 8);
**C0-01** (`test_fc2_number_canonical_boundary.py` 36, `test_adapter_canonical_boundary.py`
34); **C0-03** (`test_adapter_javdb_semantics.py` 29); **C0-04**
(`test_runtime_minutes.py` 45); **C0-02** flat suite (`test_parser_adversarial.py` 5).
C0-05 (`PHASE2_HANDOFF.md` corrections) is untouched.

## Live smoke (after the JavDB parser / `_scan.py` change)

At Code Head `c8e185e`, `tools/probe_sources.py adapter --no-record`
(`--delay-seconds 2.5`, one request per lookup, no cookies, no Cloudflare/CAPTCHA
bypass), 2026-09-20 15:56:47–15:57:01 UTC. **`docs/source-probes/PHASE2_PROBE_20260920.json`
was not touched.** (An identical run at `7a9020d`, 15:55:27–15:55:41, gave the same
outcomes.)

| Source | Number | HTTP | Result | Notes |
|---|---|---|---|---|
| `fc2db_net` | FC2-4824605 | 200 | **SUCCESS** | canonical number, non-empty JP title, 9 fields |
| `fc2db_net` | FC2-4979299 | 200 | **SUCCESS** | 9 fields |
| `javdb` | FC2-4825061 | 200 | **SUCCESS** | 6 fields |
| `javdb` | FC2-4979299 | 200 | **SUCCESS** | 6 fields |
| `av123` | FC2-4825061 | 200 | **SUCCESS** | 6 fields |
| `av123` | FC2-4979299 | 200 | **SUCCESS** | 6 fields |
| `javdb` (negative) | FC2-4824605 | 200 | **NOT_FOUND** | "search for FC2-4824605 listed 2 other number(s), none exact" |

No `av123` HTTP 500 occurred, so no retry was needed. Populated fields per source
are identical to the previous rounds.

## Files changed (`c098906..c8e185e`)

```text
M src/fc2_metadata_core/sources/adapters/_scan.py        (+collect_class_hits, +first_open_tag, parse_attrs max_attrs; docs)
M src/fc2_metadata_core/sources/adapters/javdb.py        (parser rewritten; semantics unchanged)
M tests/support/adversarial_html.py                      (+5 dense-attribute guard cases)
A tests/support/adversarial_javdb.py                     (reviewer-shaped generator, child-process runner)
A tests/unit/sources/adapters/test_javdb_total_cost.py   (14 tests)
M tests/unit/sources/adapters/test_parser_adversarial.py (docstring correction only)
```

Plus, in the docs commit: this file, and the CORRECTION note added to
`docs/review/PHASE3_ENTRY_C0_HANDOFF.md` (original text kept; the two incorrect
performance statements are annotated in place; no Git history amended).

Not changed: `normalize/`, `models/`, `_common.py`, `fc2db_net.py`, `av123.py`,
`http/`, the contract document, `PHASE2_HANDOFF.md`, any evidence JSON.

## Known limitations

- The bound is *by construction* (named constants), not a formal proof; it is
  demonstrated by the regression suite and the timing above. The parser is still
  synchronous CPU work inside `async fetch`; it is now bounded to a few tens of
  milliseconds in the worst constructed case, not moved off the event loop.
- Budgets are sized from an 8-item real page plus extrapolation (wider live queries
  were blocked with HTTP 403). If JavDB starts returning far larger pages, a
  legitimate page could hit a budget and be reported as `INVALID_RESPONSE`
  (never as a false `NOT_FOUND`); the caps are named constants at the top of `javdb.py`.
- `av123` / `fc2db_net` keep the per-primitive caps of C0; their measured worst on
  dense-attribute shapes is ~13 ms and they have no per-item multiplication, but they
  were not restructured.

## Deferred backlog (unchanged)

P2-R-05, P2-R-06, P2-R-07, P2-R-08, P2-R-09, P2-R-10 (JavDB double-unescape kept as-is),
P2-R-11, P2-R-12 — untouched, as instructed. P2-R-08, P2-R-09, P2-R-11, P2-R-12 are to be
re-evaluated when a Phase 3 component starts to depend on the behaviour.

**F3 — DEFERRED. F5 — DEFERRED.** (definitions live in the earlier review reports;
must be closed no later than before Phase 5 integration.) **F4 — CLOSED** (still enforced).

## Closure status

| ID | Status |
|---|---|
| C0-R1-01 | implemented — awaiting independent closure review |
| C0-01 / C0-03 / C0-04 / C0-05 | CLOSED (not modified) |
| F4 | CLOSED |

## Phase 3 functional implementation: NOT STARTED

No fan-out, aggregator, priority, field merge, retry/backoff, circuit breaker, batch,
or Amane adapter was implemented. **The Phase 3 Aggregator Lock is NOT lifted** until
this round passes independent closure review.

**READY FOR C0 R1 INDEPENDENT CLOSURE REVIEW** — not "C0 PASS", not "Phase 3 PASS", not
"Aggregator unlocked".
