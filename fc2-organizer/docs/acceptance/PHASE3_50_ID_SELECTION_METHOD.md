# Phase 3 C3 — 50-ID coverage set: selection method (frozen before the pool was built)

Method id: `PHASE3-50ID-SELECTION-v1`. Executable form: `tools/select_50id_set.py` (frozen in the C3 code head).
This document is committed **before** the candidate pool exists and before any aggregate lookup is run for
acceptance. Nothing below is tuned to engine results, and the engine never sees the pool.

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
