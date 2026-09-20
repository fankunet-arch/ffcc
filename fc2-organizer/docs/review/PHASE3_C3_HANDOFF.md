# PHASE3_C3_HANDOFF.md

```text
Phase: Phase 3 / C3 — Pre-Batch Live Coverage Gate

C3 Base (Phase 3 C2 Docs Head):
3b5ac61a0cc0b2b7467f2f4623c8e9ba94e922fb

Historical C3 Code Head v1 (superseded, kept in history):
5ad00e525d72759dcff3ae0458a90d8f3b6ac464

Historical Selection Method v1 Head (superseded by Amendment v2, kept in history):
74c98659394223642a41a1e78a9fae7011ba7f00

FINAL C3 CODE REVIEW CANDIDATE (Code Head v2):
578ed56aff9e3b823b39da74dc0fc10dae63456c

Selection Method v2 Head (pre-selection amendment):
3e7bd2ed1436b27f24c09e9e71dd71907c141df8

Candidate Pool Head (pool freeze):
7ba331434332338ae085324f61c69270029a5210

50-ID Set Head (set freeze):
bb05b46e8ed896843d6f501bac09e892c676d031

Evidence Head (primary gate evidence):
80a39fff9cdf94a4eb9e83d1be7ef7947692c800

PHASE3_C3_DOCS_HEAD:
the commit "docs(review): add Phase 3 C3 coverage handoff" whose parent is the Evidence Head above and
whose only change is this file (diff EVIDENCE_HEAD..DOCS_HEAD). A commit cannot contain its own hash, so
it is identified by that rule and reported in the hand-back message.

Branch:
claude/phase-0-amane-integration-fnvhpq
```

**Not a PASS declaration.** This is a candidate for independent Phase 3 C3 review. The 50-ID numeric
threshold was met, but that does **not** by itself unlock batch work. Batch, circuit breaker, NFO writer,
filesystem operations and Amane integration have **not** been started.

## Freeze chain and review ranges

```text
C3 Base 3b5ac61
  → hardening + Code Head v1 5ad00e5 (superseded)
  → Method v1 74c9865 (superseded)
  → Code Head v2 578ed56            ← final code review candidate
  → Method v2 Head 3e7bd2e
  → Pool Head 7ba3314               (pool built after Method v2 was pushed)
  → Set Head bb05b46                (selector run after the pool was pushed)
  → PRIMARY gate                    (run after the set was pushed; ONE run)
  → Evidence Head 80a39ff
  → Docs Head                       (this file)
```

| Review | Range | What it contains |
|---|---|---|
| Code | `3b5ac61..578ed56` | M1 / L1 fixes, docs (L3–L5), pool builder v2, selector v2, gate runner, all tests |
| Method | `578ed56..3e7bd2e` | `PHASE3_50_ID_SELECTION_METHOD.md` Amendment v2 (docs only) |
| Pool freeze | `3e7bd2e..7ba3314` | `PHASE3_CANDIDATE_POOL.json` + `.md` only |
| Set freeze | `7ba3314..bb05b46` | `PHASE3_50_ID_SET.json` + `.md` only |
| Evidence | `bb05b46..80a39ff` | the two primary-evidence files only |
| Docs | `80a39ff..DOCS_HEAD` | this handoff only |

The reviewer can confirm the order independently: `git log --format='%H %aI %s' 3b5ac61..80a39ff`, and that
the primary evidence records `code_head = bb05b46…` (the repo HEAD at run time) with `worktree_clean = true`.
**No file under `src/`, `tools/` or `tests/` differs between `578ed56` and `80a39ff`**
(`git diff --stat 578ed56 80a39ff -- src tools tests` is empty), so the engine that ran the gate is exactly
Code Head v2's engine.

The ten C3 commits, oldest first: `2f8bddd` M1 fix · `d378d84` L1 fix · `dfc27cd` docs L3/L4/L5 · `5ad00e5` tooling v1 ·
`74c9865` method v1 · `578ed56` tooling v2 · `3e7bd2e` method v2 · `7ba3314` pool · `bb05b46` set · `80a39ff` evidence.

## C2 review findings closed in C3

| Finding | Status | Change |
|---|---|---|
| **C2-M1** — a Cloudflare challenge body under a non-200 status (e.g. 503 without `cf-mitigated`) was `HTTP_SERVER_ERROR` and retried | **CLOSED** | `classify_page_response` (`sources/adapters/_common.py`) now checks the challenge `<title>` ("Just a moment" / "Attention required", first 4000 chars) **before** any status classification: any status → `BLOCKED`, exactly 1 attempt. Order: `cf-mitigated` header → `blocked_url_markers` → challenge body → status. An ordinary 5xx (no challenge title near the top, or the phrase only in the body / beyond the window) is unchanged: `HTTP_SERVER_ERROR`, retried once. |
| **C2-L1** — `HttpxTransport` leaked bare `LookupError` / `UnicodeError` / `ValueError` for server-chosen charsets (rot13, base64, hex, zlib, bz2, idna, undefined, NUL …) | **CLOSED** | every body-to-text failure, from the final decode **and** httpx's own charset probing, becomes `HttpDecodingError` → `NETWORK_ERROR` / `DECODE_ERROR`, retried per the C2 policy. A charset name Python does not know at all (`charset=nonsense`) keeps httpx's UTF-8 fallback (an ordinary response). Message names the truncated charset, never the body. |
| **C2-L2** — `SourceExecutionTrace` public model permits states the engine never produces (deadline in backoff after SUCCESS, incomplete SUCCESS attempt, incomplete attempt of a kind other than `SOURCE_DEADLINE`, retry after `NOT_FOUND`) | **LOW / DEFERRED (unchanged)** | not needed for the 50-ID gate. **Re-evaluate before any batch API exposes traces to wider callers.** |
| **C2-L3** — `aggregation/__init__.py` docstring still said retry/backoff out of scope | **CLOSED (docs)** | rewritten to the real C1+C2 architecture. |
| **C2-L4** — C2 handoff said "the base commit has 732 tests" | **CLOSED (docs)** | visible correction note added to `PHASE3_C2_HANDOFF.md` (the C1 base collects **731**; 732 = the C1 tests run inside the C2 tree, where F4 auto-discovers the new `retry.py`). The original text and history are untouched. |
| **C2-L5** — simultaneous distinct fatal `BaseException`s | **DOCUMENTED** | `PHASE3_RESILIENCE_CONTRACT.md` §4: *one fatal is propagated as the original object; the implementation does not preserve multiple fatal exceptions.* Pinned by `test_agg_c3_simultaneous_fatal.py` (one original, no group, deterministic for identical runs). No arbitration redesign. |

**Other backlog:** P2-R-07 **partially mitigated, still LOW** (not fixed; the evidence uses engine attempt timings,
`engine_elapsed_ms`, not adapter-reported `SourceResult.elapsed_ms`) · P2-R-05 LOW · P2-R-06 LOW · P2-R-10 LOW ·
F3 DEFERRED · F5 DEFERRED · F4 CLOSED.

### Tests for the closures

`test_agg_c3_challenge_any_status.py` (143) — real adapters × real `HttpxTransport` over `httpx.MockTransport`: all
three sources × 9 statuses × 2 challenge titles → `BLOCKED`, 1 request/attempt; a 503 challenge followed by a valid page
never recovers; ordinary 5xx (5 body shapes) still retried once; classifier directly. `test_httpx_transport_decode_c3.py`
(73) — 16 non-text/unusable charsets → `HttpDecodingError`, no bare stdlib type crosses the boundary; legitimate charsets
unchanged; end to end `DECODE_ERROR`, one retry, never `ADAPTER_EXCEPTION`, recovery on a clean second response. Both
files were verified to **fail against the pre-fix code** (117 failures) and pass after. `test_agg_c3_simultaneous_fatal.py` (3).

## Attempt 1 of the candidate pool — audit FAIL (history, must be read)

The first pool (builder v1, code head v1 `5ad00e5`, method v1 `74c9865`; created 2026-09-20T20:59:28Z; sha256
`098fc71755d24064802d8ced77f5ad4a66082b7590bec42915fcdfdc62416bfa`) **failed its read-only audit**:

| Measure | Value |
|---|---|
| candidates | 167 (160 enumerated + 7 Phase 2 mandatory) |
| dual (≥ 2 external references) / single (exactly 1) | 46 / 118 |
| dual per band (sampled) | older **9** (needs 14) · middle 34 (needs 15) · recent **2** (needs 14) |
| requests / failures | 214 / **41 failed lookups** |

Problem: **a failed lookup and a genuine negative were conflated** ("not confirmed"), and v1's dual-only sampling rule
could not be satisfied. At that moment: formal selector **NOT RUN**; 50-ID set **NOT FROZEN**; primary gate **NOT RUN**.
The Attempt 1 pool was **never committed, never frozen, never used for any formal selection**; its file was kept only as
job-scratch evidence (deleted from the worktree) and the selector was never run on it. No engine result influenced
anything that followed: during all of C3 the aggregation engine was never run live on any sampled candidate before the
primary gate (the 7 mandatory IDs only have their historical Phase 2 / C2 smoke evidence — see limitation 3).

Response = **pre-selection Amendment v2** (allowed by Method §5, committed separately, `3e7bd2e`):

* **tri-state lookups:** `confirmed` / `negative` / `unavailable`; `unavailable` (timeout, connection error,
  403 / 429 / 5xx / other non-200, unusable body such as a challenge page) is **never** turned into `negative`;
* **one retry only, only for `unavailable`**, after the same ≥ 3 s delay; confirmed / negative are never retried;
* **prefix enumeration is all-or-nothing:** any of the 40 prefix queries still `unavailable` after its retry → build
  fails, no pool file;
* **dual-first selection + single-reference fallback only for a band deficit**; zero-confirmed candidates are never
  eligible; mandatory 7, bands and quotas 14/15/14 and `PER_PREFIX = 4` unchanged; no third reference added.

The 41 failures did **not** recur when the pool was rebuilt (0 unavailable, 0 retries); the recent band's dual count
went from 2 to 25. That is consistent with v1's conflation having hidden real corroboration, but the cause of the
original 41 is unknown (the v1 file did not record which requests failed).

## Candidate pool (frozen at `7ba3314`)

Files: `docs/acceptance/PHASE3_CANDIDATE_POOL.json` (+ `.md` summary). Builder `tools/build_candidate_pool.py` v2 —
never imports the aggregation engine, adapters or transport (AST-tested); reference 1 = sukebei.nyaa.si torrent-name
listing (`FC2-PPV-<prefix>*`, prefixes `10 … 49`), reference 2 = netflav.com (exact `code` match only — fuzzy neighbours,
partial numeric matches and title mentions never count).

| Measure | Value |
|---|---|
| schema / procedure | 2 / `PHASE3-CANDIDATE-POOL-v2`, created 2026-09-20T21:25:38Z |
| candidates | **167** = 160 enumerated + **7** Phase 2 mandatory; duplicates 0; all canonical |
| prefix enumeration | **40 / 40** complete, unavailable 0 |
| requests / retries / unexplained failures | **214** / **0** / 0 (= 40 prefix + 160 netflav + 14 mandatory-ID lookups) |
| candidate-level checks | confirmed 74 · negative 100 · **unavailable 0** |
| validation strength | **≥ 2 external refs: 70** · **exactly 1: 94** · **0: 3** |
| eligible under Method v2 (non-frozen) | older 40 (tier 1: 9 + tier 2: 31) · middle 80 (34 + 46) · recent 40 (25 + 15) |

**Provenance-only mandatory IDs** (0 external references; *both* references returned a valid response with no exact match —
`negative`, not `unavailable`; Phase 2 provenance is never counted as an external reference): `FC2-1042815`,
`FC2-4972767`, `FC2-4976588`. They are mandatory because they are in the Phase 2 frozen probe set, and are neither
dual- nor single-reference IDs.

**Pool hash — two values, one content.** Authoritative = SHA-256 of the exact Git blob at the Pool Head:
`48e8300031f855e995114c30bf815843d5c61bcdcff42492803766b5b95a82e2` (LF, 135,276 bytes). Windows-audited working file
(CRLF, 139,732 bytes): `ffe0b095793a914c9c12cc5af97f220244d4534853d761b523821d5ac0fd4cb9`. Semantic equality **PASS**
(`json.loads` equal; CRLF→LF of the checkout equals the blob byte for byte). The formal selector read the blob exported
with `git cat-file blob`, not a Windows checkout, so the set does not depend on `core.autocrlf`.

## Frozen 50-ID set (frozen at `bb05b46`)

Files: `docs/acceptance/PHASE3_50_ID_SET.json` (+ `.md`, which lists all 50 with tier and reference states). Selector
`tools/select_50id_set.py`, method `PHASE3-50ID-SELECTION-v2`: pure, offline, no randomness / clock / network / engine.

| Measure | Value |
|---|---|
| IDs | **exactly 50**, 0 duplicates, all canonical; **mandatory 7** (the Phase 2 frozen 7 — 7/7 present) + **sampled 43** |
| `dual_reference` / `single_reference_fallback` / `phase2_mandatory` | **38 / 5 / 7** (of the 7 mandatory, 3 are provenance-only) |
| older (< 2,000,000) | **15** = 14 sampled (9 dual + 5 single fallback) + 1 mandatory |
| middle (2,000,000–3,999,999) | **15** = 15 sampled (15 dual, 0 fallback) |
| recent (≥ 4,000,000) | **20** = 14 sampled (14 dual, 0 fallback) + 6 mandatory |
| zero-external-reference sampled IDs | **none** |

Method v2 behaviour: tier 1 alone filled middle (34 ≥ 15) and recent (25 ≥ 14), so no fallback was used there; older had
only 9 < 14 dual so all 9 were taken and 5 single-reference fallbacks filled the deficit by the same even stride.
**Reproducibility (all PASS):** 3 further independent CLI runs on the same blob gave the identical ordered `ids[].number`;
the pure `select()` gave the same 50 (numbers **and** tiers) with entries reversed / shuffled (5 seeds) / JSON key order
reversed / both / duplicated; an independent re-implementation of the method (written separately from the tool)
selected the identical 50. Set `candidate_pool.sha256` = `48e83000…82e2` (the blob hash).

Set hashes: working tree (CRLF) `dc6f4af58b3af3df0fe84c6e704be38ae048ecb286333df929fbcd484a78c9a8`; **Git blob at
`bb05b46`** (authoritative) `43beeb6658203d173f6b218729263e674c00fbe1f52a5186690fbec5ded1d2c6`; CRLF→LF equality and
semantic equality both true. The evidence records the working-tree hash (`dc6f4af5…`); identity is bound by Set Head +
`set_last_commit = bb05b46` + "committed unchanged".

## PRIMARY 50-ID gate — one and only one run

| Item | Value |
|---|---|
| Runner | `tools/run_50id_coverage_gate.py --run-kind primary --set docs/acceptance/PHASE3_50_ID_SET.json --out-dir docs/acceptance/evidence --delay-seconds 4` |
| Started / finished (UTC) | **2026-09-20T23:21:40Z / 2026-09-20T23:25:41Z** |
| Preconditions checked | HEAD = `bb05b46`, tree clean, set last commit = `bb05b46` and unmodified, no prior primary evidence |
| Config (frozen defaults) | source order `fc2db_net, javdb, av123`; `max_concurrency` 3; 20 s deadline/source; C2 default `RetryPolicy` (2 attempts, 1 s backoff; 429 / BLOCKED / NOT_FOUND never retried); IDs strictly sequential, 4 s apart |
| **Result** | **50 total · 49 covered · 1 uncovered · 98.0%** — threshold ≥ 45/50: **NUMERIC THRESHOLD MET** |
| Aggregate | SUCCESS **49** · PARTIAL **0** · FAILED **1** · ENGINE_EXCEPTION **0** |
| Covered-but-PARTIAL | **0** |
| Metric (frozen) | COVERED = aggregate ≠ `FAILED` and metadata present and `metadata.meets_minimum_success()` (canonical number + non-empty title) |

Evidence (only ids / statuses / structured error kinds / attempt counts / engine timings / verdict — no body, cookie,
credential, URL, title or error text):
`docs/acceptance/evidence/PHASE3_50_ID_GATE_PRIMARY_20260920T232140Z.json` and `.md`.

| File | Working-tree SHA-256 (CRLF) | **Git-blob SHA-256 at `80a39ff` (authoritative)** |
|---|---|---|
| `.json` | `822b7705180139945a9b57a8d3de5d4d32125cd7f839806f024a19e1957f1a11` | `2a83de01eadf6ac1ecf611780baeca40cc33f6747f491f760684aed501d3ecf7` |
| `.md` | `66f104be801d23ae5e602f1deb95fddf5efc5f89006065af1426cd361b040185` | `f0da1d68daebb57fb7f6b49549d154c2ed02a9d6a4c9c688676a4bc6f2ad3f8b` |

The evidence was committed byte-for-byte as generated (never edited); CRLF→LF of each working-tree file equals its blob.
A read-only audit recomputed everything from the raw per-ID records and passed: `run_kind == primary`; 50 results in
exactly the frozen set's order, no duplicates; covered 49 + not covered 1 = 50; 98.0%; threshold flag; aggregate counts;
per-source accounting (50 IDs each) and attempt traces; retry statistics; `m1_violations`; no forbidden content.

### The uncovered ID

**`FC2-4493606`** — aggregate `FAILED`, no title. `fc2db_net` NOT_FOUND / NOT_FOUND ×1 attempt · `javdb` NOT_FOUND /
NOT_FOUND ×1 · `av123` NOT_FOUND / NOT_FOUND ×1. **No network, blocked, rate-limit, parse or invalid-response failure;**
a clean triple "not in this catalogue". In the frozen set it is a **`dual_reference`** sampled recent-band ID; both
independent references confirmed it on 2026-09-20 before the primary run (sukebei: 1 torrent row, exact name match;
netflav: exact code hit).
It is recorded as a **real observed aggregate coverage gap**. It was not replaced, not removed, the denominator was not
changed, no other primary run was made, and **no diagnostic run was made** (Diagnostic: NOT RUN — a clean triple
NOT_FOUND is not a transient anomaly and a diagnostic would not replace the primary). Whether the dataset-validity
evidence for this ID is adequate is for the independent reviewer to adjudicate.

### Source-level statistics (final results, 50 IDs each)

| Source | success | not_found | other operational failures | attempts | IDs retried | mean engine ms |
|---|---|---|---|---|---|---|
| `fc2db_net` | **27** | **23** | 0 | 50 | 0 | 895 |
| `javdb` | **40** | **10** | 0 | 50 | 0 | 284 |
| `av123` | **44** | **6** | 0 | 50 | 0 | 207 |

(blocked, rate_limited, network_error, parse_error, invalid_response: 0 for every source.)
**Live retries: 0. M1 violations: 0. BLOCKED after > 1 attempt: 0 (no source ended `BLOCKED` at all).**

**M1 and L1 were NOT naturally exercised by the live 50-ID traffic** — there was no challenge, no 5xx and no decode
error. Their closure rests on the offline production-path tests above, not on live evidence; the same holds for the
retry path (0 live retries, so the C2 retry engine was not exercised live either).

### What 98% does and does not mean

98% is **aggregate union coverage** over the frozen 50-ID set: an ID counts if *any* source supplies canonical number +
title. **It is not a per-source figure and this handoff does not claim "each source ≥ 90%".** Observed individual source
success is `fc2db_net` 27/50 (54%), `javdb` 40/50 (80%), `av123` 44/50 (88%). The gate intentionally evaluates the
multi-source aggregation engine. Source-level NOT_FOUND counts are catalogue gaps, not failures, so `PARTIAL` never
occurred (no source failed operationally).

## Offline regression (final, on `80a39ff`; no code changed since `578ed56`)

```text
python --version                      Python 3.12.10
python -m pytest --collect-only -q    1595 tests collected
python -m pytest -v                   1595 passed, 0 failed, 0 skipped (0 xfail/xpass/error)
python -m pytest -q                   1595 passed
```

The C2 frozen baseline of **1305 passed** is unchanged and green. **+290 new C3 tests**: challenge-any-status 143,
transport decode 73, simultaneous fatal 3, gate runner 13, gate live path (offline, exact `_live` path) 4, pool builder
v2 34, selector v2 20. (The v1 pool/selector tests written before Code Head v1 were replaced by the v2 modules.) Test
isolation note (unchanged): import core classes at module top — the F4 contract test re-imports the package; tests avoid
the pytest `tmp_path` fixture because of a Windows temp-symlink permission problem in this environment (`tempfile` is used).

## Limitations and things the reviewer should weigh

1. **Set validity evidence is a snapshot of two public sites, not ground truth.** Sukebei (torrent names) and netflav are
   independent *services* from the three engine sources but not independent *origins* (all mirror FC2 catalogue data). Tier 1
   requires netflav corroboration, so dual IDs are likelier to be aggregator-indexed than fallback IDs — this may flatter
   coverage compared with an arbitrary FC2 file. 5 of 50 IDs (older band) are single-reference fallbacks; 3 are
   provenance-only. A reviewer who finds single-reference validity too weak may require a dataset-strengthening round (a
   third reference was deliberately **not** added during acceptance).
2. **Code Head was reopened once (v1 → v2)** for two evidence-explained reasons (tri-state observability; band composition),
   before any selection or acceptance run; v1 stays in history and the amendment is documented in Method v2.
3. **The 7 Phase 2 mandatory IDs already had historical aggregate evidence** (Phase 2 probes and the C2 live smoke). They are
   mandatory by the task definition and are not a C3 pre-check. The 43 sampled IDs were never passed to the aggregation
   engine before the primary run.
4. **Hash duality** (pool, set, evidence): Windows checkouts are CRLF, Git stores LF (`core.autocrlf=true`). Authoritative
   identity is the Git blob at the named head; both values are recorded; nothing was rewritten to make them equal.
5. **Scratch audit scripts are not in the repository.** The read-only audits (pool audit v1/v2, blob export + semantic
   equality, set reproducibility/independent re-implementation, primary-evidence recomputation) were run from job scratch; the
   figures they produced are in this file and are cheap to recompute from the committed artifacts.
6. Pool contents are a **2026-09-20 live snapshot**: rebuilding later would give different candidates. The frozen pool/set
   files, not the procedure, are the acceptance artifacts.

## Suggested review focus

1. Freeze order: builder/selector/runner code (`578ed56`) → Method v2 (`3e7bd2e`) → pool (`7ba3314`) → set (`bb05b46`) →
   primary run from a clean `bb05b46` → evidence (`80a39ff`); each freeze diff contains only its own files.
2. The selection is a pure function of the committed pool blob: re-run `select_50id_set.py` on
   `git cat-file blob 7ba3314:fc2-organizer/docs/acceptance/PHASE3_CANDIDATE_POOL.json` and compare the ID sequence.
3. The gate runner: no ID/attempt/order/deadline override, ≥ 3 s pacing, one-primary guard, covered predicate.
4. `_common.classify_page_response` ordering and the `HttpxTransport` decode boundary (M1 / L1), including that ordinary
   5xx still retries.
5. Method v2 rationale and the disclosed validity trade-offs (limitation 1); adjudicate `FC2-4493606`'s validity evidence.
6. Whether the union-coverage framing is acceptable given per-source figures (27 / 40 / 44 of 50).

## Not started / not claimed

* **Batch engine, global batch concurrency budget, failed-subset retry:** NOT STARTED.
* **Circuit breaker:** NOT STARTED. **NFO writer / image download:** NOT STARTED.
* **Filesystem rename / move / organisation:** NOT STARTED. **Amane adapter / integration / GUI:** NOT STARTED.
* Planning note carried from C2: `max_concurrency` is per-`aggregate()` call; a batch must add a cross-item global budget
  (plus per-host limits and a circuit breaker) — never `gather(500 × aggregate())`.
* 50-ID numeric threshold met **does not** unlock batch; the independent C3 review must pass first.
* Diagnostic run: **NOT RUN**. Primary must never be re-run.
