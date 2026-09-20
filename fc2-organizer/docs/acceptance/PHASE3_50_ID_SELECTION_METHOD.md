# Phase 3 C3 — 50-ID coverage set: selection method

> **Status: v2 is in force (see "Amendment v2" at the end).** The v1 text below is kept unchanged as history.
> Where v2 differs — pool observability (§3), sampling eligibility (§4) — the v2 rules replace the v1 rules;
> everything else (purpose, validity evidence, freeze / run / what counts in §6) still applies as written.

Method id: `PHASE3-50ID-SELECTION-v1` (historical), now `PHASE3-50ID-SELECTION-v2`. Executable form:
`tools/select_50id_set.py`. The v1 text was committed **before** the candidate pool existed and before any
aggregate lookup was run for acceptance. Nothing below is tuned to engine results, and the engine never sees the pool.

## 1. Purpose and the rule that matters most

The gate asks: *of 50 FC2 IDs that are known to be real, how many does the aggregation engine turn into
canonical number + non-empty title?* That number is meaningless if the 50 were picked by looking at which IDs
the engine can resolve. Therefore:

* The 50 IDs are fixed **before** the primary run and are never changed afterwards.
* Whether an ID is "known-valid" is decided from **public references that are not the engine's sources**
  (`fc2db_net`, `javdb`, `av123`). The pool builder and the selector do not import the engine, the adapters or
  the transport (a test enforces it).
* Selection is a pure function of the pool file: same pool → same 50 IDs. No randomness, no seed, no clock,
  no human judgement.

## 2. Validity evidence ("known-valid")

| Reference | Role | How it is used |
|---|---|---|
| **R1 — `sukebei.nyaa.si` torrent listing** | enumeration + validity | public search `FC2-PPV-<prefix>*` (first result page). An ID counts only if a torrent *name* contains `FC2-PPV-<number>` (usual spellings). |
| **R2 — `netflav.com` search** | corroboration | public search by number. Counts only if an embedded result's `code` is **exactly** that number (fuzzy neighbours never count). |
| Phase 2 frozen set | provenance for the 7 mandatory IDs | recorded in addition to R1/R2 for those IDs. |

Recorded per ID: canonical number, which references confirmed it, a note, the UTC validation date. **Never**
recorded: response bodies, headers, cookies, tokens, account data. An ID confirmed by exactly one external
reference is labelled *single-source validation* in its note.

Known limitation (stated up front, not hidden): R1 and R2 are independent *services* from the three engine
sources, but they are not independent *origins* — all of them ultimately reflect FC2 Content Market catalogue
data, and aggregators partly overlap. Requiring R2 corroboration therefore biases the set towards IDs that are
publicly indexed by more than one site, which may make coverage look somewhat better than for an arbitrary FC2
file. The reviewer should weigh that; the alternative (single-reference IDs) trades it for weaker validity.

## 3. Candidate pool (`PHASE3_CANDIDATE_POOL.json`, built by `tools/build_candidate_pool.py`)

1. For each two-digit prefix `10 … 49` (40 prefixes, covering roughly 1.0 M – 4.99 M) query R1 with
   `FC2-PPV-<prefix>*`. Candidates = 7-digit numbers starting with that prefix that appear in a torrent name.
2. Keep `4` per prefix at an even stride over the ascending list of that prefix's candidates
   (`((2j+1)·n)//(2·4)`); all of them if there are ≤ 4.
3. Look every kept candidate up on R2 (exact-code match).
4. The 7 Phase 2 frozen IDs are looked up on R1 and R2 the same way and are always in the pool, whatever R1/R2
   say about them.
5. Requests are sequential, ≥ 3 s apart, no bypass of any kind; a failed request means "not confirmed by that
   reference" and is counted in the file.

## 4. Selection (`tools/select_50id_set.py`)

1. **Mandatory (7):** `FC2-4825061, FC2-4824605, FC2-4979299, FC2-4976588, FC2-1042815, FC2-4978035,
   FC2-4972767` are always in the set.
2. **Eligible for sampling:** pool entries with `external_reference_count ≥ 2` (R1 **and** R2), excluding the 7,
   canonicalised, de-duplicated, sorted ascending by number.
3. **Bands (fixed numeric ranges) and quotas for the remaining 43:**

| Band | Numbers | Quota |
|---|---|---|
| older | `< 2,000,000` | 14 |
| middle | `2,000,000 – 3,999,999` | 15 |
| recent | `≥ 4,000,000` | 14 |

4. **Within a band** with `m` eligible members and quota `q`, take the members at indices
   `((2j+1)·m) // (2q)` for `j = 0 … q-1` — an even stride over the ascending list.
5. The result is sorted ascending and must be **exactly 50 distinct** IDs. A band with fewer eligible members
   than its quota is an **error**; the algorithm never silently moves a quota or swaps in another ID.

Diversity by construction: with the 7 mandatory IDs the set contains ≥ 15 older, ≥ 15 middle and ≥ 20 recent
IDs and spans the range from the 1.0 M region to the 4.9 M region; it cannot be a single consecutive block.

## 5. Amendment policy (pre-selection only)

If the pool cannot fill a quota, the method may be amended **before the selector is run**, only on the basis of
pool composition (never engine results), by a separate commit that states what changed and why. After the set
file is committed no amendment is possible.

## 6. Freeze, run, and what counts

* The set is committed alone as `docs(acceptance): freeze Phase 3 50-ID coverage set`; that commit
  (`PHASE3_C3_SET_HEAD`) must precede the primary run. The runner refuses a primary run from a dirty tree, with
  an uncommitted/modified set file, or when primary evidence already exists.
* **Primary run — exactly one.** Real `MultiSourceEngine`, C3 code head, default order
  `fc2db_net, javdb, av123`, C2 default `RetryPolicy` (2 attempts; 429 / BLOCKED / NOT_FOUND never retried),
  IDs sequential, ≥ 4 s apart. Its result is the formal numerator/denominator.
* **Covered** = aggregate status ≠ `FAILED`, metadata present, and `metadata.meets_minimum_success()`
  (canonical number + non-empty title). `SUCCESS` and `PARTIAL` can both be covered; every `PARTIAL` and every
  source-level failure is reported separately, so source health is never hidden behind the coverage figure.
* **Gate:** covered ≥ 45 of 50 (90 %). Meeting it is reported as *numeric threshold met* only — never as a C3
  PASS; the independent reviewer decides that.
* **Uncovered IDs are never replaced** and no 51st ID is added. A *diagnostic* re-run may be used to investigate
  a failure, is recorded separately, and never replaces the primary result.
* **If an ID in the set turns out not to be a real FC2 product:** it is not swapped quietly. It stays in the
  denominator of the primary result, is written up as an *invalid-set-item investigation* in the evidence, and the
  reviewer decides whether a dataset-correction round is allowed.

---

# Amendment v2 — `PHASE3-50ID-SELECTION-v2` (pre-selection amendment 1)

Made under §5 ("amendment policy: pre-selection only, only on pool composition, separate commit"). It is **not**
a C3 review round (C3 has not been submitted for independent review) and it is **not** based on any engine result.

## A. Historical facts this amendment does not erase

| Item | Value |
|---|---|
| C3 base | `3b5ac61a0cc0b2b7467f2f4623c8e9ba94e922fb` |
| Historical C3 Code Head v1 | `5ad00e525d72759dcff3ae0458a90d8f3b6ac464` |
| Historical Selection Method v1 Head | `74c98659394223642a41a1e78a9fae7011ba7f00` |
| C3 Code Head v2 (replaces v1 as the code-review candidate) | `578ed56aff9e3b823b39da74dc0fc10dae63456c` |
| Formal 50-ID selector run before this amendment | **NOT RUN** |
| 50-ID set frozen before this amendment | **NO** |
| Primary coverage gate before this amendment | **NOT RUN** |
| Aggregation engine used during pool build (attempt 1) | **NO** |

## B. Attempt 1 of the candidate pool — audit FAIL, never frozen, never committed

Built by the v1 builder (created 2026-09-20T20:59:28Z; file sha256
`098fc71755d24064802d8ced77f5ad4a66082b7590bec42915fcdfdc62416bfa`, kept only as job-scratch evidence):

| Measure | Value |
|---|---|
| total candidates | 167 (160 enumerated + 7 Phase 2 frozen) |
| ≥ 2 external references ("dual") | 46 (45 sampled + FC2-4825061) |
| exactly 1 external reference ("single") | 118 |
| dual per band, sampled candidates | older **9** (quota 14), middle 34 (quota 15), recent **2** (quota 14) |
| requests / failures | 214 requests, **41 failed** — recorded as "not confirmed", i.e. **not distinguished from a genuine negative** |

Two independent defects, neither related to engine results:

1. **Composition.** v1 required every sampled ID to have ≥ 2 external references. That was an *extra*
   strengthening, not part of the original gate ("known-valid IDs; prefer ≥ 2 references; if only one public
   reference exists, say so explicitly as single-source validation"). With Attempt 1's composition v1 cannot run.
2. **Observability.** A failed lookup (timeout / 403 / 429 / 5xx) and a successful "no exact match" were both stored
   as "not confirmed". That can bias which IDs look single- or dual-referenced, and it hides operational failure.

## C. What changes in v2

### C.1 Builder (§3 replaced)

* Every reference lookup ends in **`confirmed`** (valid response, exact evidence), **`negative`** (valid response,
  no exact evidence) or **`unavailable`** (timeout, connection error, HTTP 403 / 429 / 5xx / any non-200, or an
  unusable body such as a challenge page). `unavailable` is **never** turned into `negative`.
* `unavailable` gets **one** polite retry after the same ≥ 3 s delay (no proxy rotation, no bypass, no cookies);
  `confirmed` and `negative` are never retried. The final state, the attempt count (1 or 2) and a bounded,
  non-sensitive detail (HTTP status / exception *type* / `exact_match` / `no_exact_match`) are recorded.
* **Prefix enumeration is all-or-nothing:** if any of the 40 `FC2-PPV-<prefix>*` queries is still `unavailable`
  after its retry the build fails (non-zero exit, no pool file). It is never read as "zero candidates".
* An enumerated candidate is R1-confirmed by construction; its R2 (netflav) state is recorded truthfully. R2
  `unavailable` leaves the candidate a *single-reference* candidate (`external_reference_count = 1`) with the
  unavailability visible — it is not an R2 negative.
* The 7 Phase 2 IDs use the same tri-state lookups. Their Phase 2 provenance stays in `validity_sources` but is
  **never counted** as an external reference (`external_reference_count` counts confirmed R1/R2 only).
* Pool schema v2: `candidates[]` (each with `number`, `band`, `origin`, `validation_date`, `validity_sources`,
  `external_reference_count`, `validity_note`, `reference_checks{sukebei,netflav}`), top-level `requests_made`,
  `retry_requests`, `initial_requests`, `confirmed_checks`, `negative_checks`, `unavailable_checks`,
  `prefix_enumeration_complete`, and a per-prefix table. Every request is accounted for by exactly one recorded check.
* **Unchanged:** `PER_PREFIX = 4` (the population is large enough; the deficit is corroboration sparsity, and
  enlarging the pool would add many requests without fixing it), the 40 prefixes, R1/R2 and their exact-match rules
  (fuzzy hits, partial numeric matches, title mentions and substrings never count). **No third reference is added**
  in this round: it would introduce a new parser / network dependency and its own exact-match semantics during
  acceptance. If the independent reviewer finds single-reference validity too weak for the gate they may require a
  dataset-strengthening round.

### C.2 Selection (§4 replaced): dual-first, transparent single-reference fallback

Mandatory 7, the three numeric bands and the quotas (older 14 / middle 15 / recent 14 = 43) are **unchanged**.
Sampling eligibility is now two tiers per band, counted from *confirmed* external references only:

| Tier | Rule | `validation_tier` |
|---|---|---|
| 1 — preferred | ≥ 2 confirmed external references | `dual_reference` |
| 2 — fallback | exactly 1 confirmed external reference | `single_reference_fallback` |
| never eligible | 0 confirmed: zero-reference, negative-only, unavailable-only, Phase-2-provenance-only | — |

Per band with quota `q` and ascending tier-1 list `T1` (`m = |T1|`):

* `m ≥ q` → take `q` from `T1` at indices `((2j+1)·m) // (2q)`; **tier 2 is not used at all**.
* `m < q` → take **all** of `T1`, then `deficit = q − m` from the ascending tier-2 list `T2` (`m' = |T2|`) at indices
  `((2j+1)·m') // (2·deficit)`. If `m' < deficit` the selection is an **error** (widen the pool; never shift a quota).

Illustration only (the formal counts come from the rebuilt, frozen v2 pool): with Attempt 1's shape the older
band would take its 9 dual + 5 single, middle 15 from its 34 dual only, recent its 2 dual + 12 single.

Mandatory IDs carry `validation_tier = phase2_mandatory`. Each selected ID's `validation_tier`,
`reference_checks`, `validity_sources` and `validity_note` are in the set file, so a reviewer sees exactly how many of
the 50 are dual, single-fallback or mandatory. The selector refuses a pool with an incomplete prefix enumeration,
an old schema, or a candidate whose stored `external_reference_count` disagrees with its own `reference_checks`.
It stays pure: offline, no randomness, no clock in the selection, no engine, no adapters.

### C.3 Why single-reference fallback is admissible, and its cost

The original requirement was known-valid IDs, *preferably* corroborated by ≥ 2 independent public references, with
single-reference IDs explicitly labelled. v1's "dual only" was stricter than that. v2 keeps dual-first and uses a
labelled single-reference fallback only to fill a band's deficit. The trade-off is weaker validity evidence for
those IDs (one torrent-name reference, no aggregator corroboration); it is disclosed per ID, and the fallback is
chosen by the same blind stride, never by engine outcome. A side effect worth knowing: because tier 1 requires
netflav corroboration, dual IDs are likelier to be aggregator-indexed than fallback IDs.

## D. New freeze chain

`C3 Code Head v2` → `Selection Method v2 Head` (this amendment) → **candidate pool rebuilt with builder v2** →
`Candidate Pool Freeze Head` → selector → `50-ID Set Freeze Head` → **PRIMARY gate** → evidence / handoff docs.
The pool is rebuilt only after this amendment is committed and pushed; the selector reads only the committed pool;
the primary gate runs only after the set file is committed. If the v2 pool still cannot fill a band from tier 1 +
tier 2 the process stops for a decision (third reference / enumeration expansion); nothing is adjusted silently.
