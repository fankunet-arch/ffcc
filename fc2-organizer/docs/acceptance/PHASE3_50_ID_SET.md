# Phase 3 C3 — frozen 50-ID acceptance set

Machine-readable set: `docs/acceptance/PHASE3_50_ID_SET.json`. This file is its human-readable summary. The set is
frozen by the commit that adds these two files. **No C3 aggregate / coverage run has been made on any of these IDs**
(the 43 newly selected IDs have never been passed to the aggregation engine at all; the 7 Phase 2 mandatory IDs only
have their historical Phase 2 / C2 smoke evidence, which is not part of this gate). The primary coverage gate reads
this committed set and runs only after this freeze.

## 1. Provenance and binding

| Item | Value |
|---|---|
| C3 Code Head v2 | `578ed56aff9e3b823b39da74dc0fc10dae63456c` |
| C3 Selection Method v2 Head | `3e7bd2ed1436b27f24c09e9e71dd71907c141df8` |
| C3 Pool Head | `7ba331434332338ae085324f61c69270029a5210` |
| Selection method | `PHASE3-50ID-SELECTION-v2` (`docs/acceptance/PHASE3_50_ID_SELECTION_METHOD.md`, Amendment v2) |
| Selector | `tools/select_50id_set.py` (pure, offline, deterministic) |
| Pool path | `docs/acceptance/PHASE3_CANDIDATE_POOL.json` |
| **Authoritative pool SHA-256** = SHA-256 of the exact Git blob at the Pool Head | `48e8300031f855e995114c30bf815843d5c61bcdcff42492803766b5b95a82e2` |
| Windows-audited checkout SHA-256 of the same pool (CRLF) | `ffe0b095793a914c9c12cc5af97f220244d4534853d761b523821d5ac0fd4cb9` |
| Set created (UTC) | 2026-09-20T23:16:45+00:00 |
| Formal selector run | **RUN** (once, on the exported Pool Head blob) |
| Primary coverage gate at set freeze | **NOT RUN** |

**Why two pool hashes.** The pool was built and audited on Windows, where the working file is CRLF
(`ffe0b095…`). This repository uses `core.autocrlf=true`, so Git stores the same content with LF endings
(`48e83000…`). The two differ **only** in line-ending representation; the parsed JSON is identical (verified:
`json.loads(blob) == json.loads(checkout)` is true, and the CRLF→LF normalisation of the checkout equals the blob
byte for byte). To make the set independent of platform and `autocrlf`, the formal selector was **not** pointed at a
Windows checkout: the exact bytes of `PHASE3_CANDIDATE_POOL.json` were exported from the Pool Head commit with
`git cat-file blob` (bytes only, no newline / encoding conversion), verified to hash to `48e83000…`, and that file was
the selector's `--pool` input. The set records the blob hash as `candidate_pool.sha256`; the recorded
`candidate_pool.file` is the repository path above. The pool was not modified, replaced or rebuilt, and neither the
selector nor the method changed.

## 2. Composition

* **Selected IDs: 50**, duplicates 0, all canonical, sorted ascending (FC2-1042815 … FC2-4979299).
* **Phase 2 mandatory IDs: 7 / 7** present.

| Evidence tier (`validation_tier`) | Count |
|---|---|
| `dual_reference` (≥ 2 confirmed external references) | **38** |
| `single_reference_fallback` (exactly 1 confirmed external reference) | **5** |
| `phase2_mandatory` | **7** — of which provenance-only (0 external references): **3** |

| Band | Range | Sampled (quota) | dual | single fallback | + mandatory in band | Total in set |
|---|---|---|---|---|---|---|
| older | < 2,000,000 | 14 (14) | 9 | 5 | 1 | 15 |
| middle | 2,000,000 – 3,999,999 | 15 (15) | 15 | 0 | 0 | 15 |
| recent | ≥ 4,000,000 | 14 (14) | 14 | 0 | 6 | 20 |

Method v2 behaviour, as produced by the selector (not hand-built): in the **middle** and **recent** bands tier 1 (≥ 2 references) already filled the quota (34 ≥ 15 and 25 ≥ 14), so **no single-reference fallback** was used there. In the **older** band tier 1 had only 9 < 14, so all 9 dual candidates were taken plus **5** single-reference fallbacks chosen by the even stride over the ascending tier-2 list. No sampled ID has 0 external references.

### Provenance-only mandatory IDs

`FC2-1042815`, `FC2-4972767`, `FC2-4976588` are in the set solely because they belong to the Phase 2 frozen probe set. Both external references returned a valid response with no exact match (`negative`, not `unavailable`), so their `external_reference_count` is 0; Phase 2 provenance is never counted as an external reference. They are neither dual- nor single-reference IDs.

The other mandatory IDs carry external evidence: `FC2-4824605`, `FC2-4825061`, `FC2-4978035`, `FC2-4979299` (FC2-4824605 and FC2-4825061 dual; FC2-4978035 and FC2-4979299 single, sukebei-confirmed / netflav-negative).

## 3. Reproducibility (all PASS)

* The selector was run **3 more times** independently on the same exported blob: the ordered `ids[].number` sequence was identical to the formal output every time (`created_at` differs, IDs do not).
* The pure `select()` gave the same 50 (numbers **and** tiers) with the entries reversed, shuffled (5 seeds), with JSON key order reversed, both combined, and with duplicated entries.
* An independent re-implementation of Method v2 written separately from the tool selected the identical 50 IDs.
* Every ID exists in the frozen pool; evidence fields (`validity_sources`, `reference_checks`, `validity_note`, `validation_date`, `external_reference_count`) are byte-identical copies of the pool entries.

## 4. The 50 IDs

| # | Number | Band | Origin | Tier | Ext. refs | Reference checks |
|---|---|---|---|---|---|---|
| 1 | FC2-1042815 | older | phase2_frozen | phase2_mandatory | 0 | sukebei negative / netflav negative |
| 2 | FC2-1097500 | older | sampled:older | single_reference_fallback | 1 | sukebei confirmed / netflav negative |
| 3 | FC2-1261799 | older | sampled:older | single_reference_fallback | 1 | sukebei confirmed / netflav negative |
| 4 | FC2-1395953 | older | sampled:older | single_reference_fallback | 1 | sukebei confirmed / netflav negative |
| 5 | FC2-1528279 | older | sampled:older | single_reference_fallback | 1 | sukebei confirmed / netflav negative |
| 6 | FC2-1692217 | older | sampled:older | single_reference_fallback | 1 | sukebei confirmed / netflav negative |
| 7 | FC2-1713543 | older | sampled:older | dual_reference | 2 | sukebei confirmed / netflav confirmed |
| 8 | FC2-1737461 | older | sampled:older | dual_reference | 2 | sukebei confirmed / netflav confirmed |
| 9 | FC2-1782986 | older | sampled:older | dual_reference | 2 | sukebei confirmed / netflav confirmed |
| 10 | FC2-1817510 | older | sampled:older | dual_reference | 2 | sukebei confirmed / netflav confirmed |
| 11 | FC2-1841311 | older | sampled:older | dual_reference | 2 | sukebei confirmed / netflav confirmed |
| 12 | FC2-1858921 | older | sampled:older | dual_reference | 2 | sukebei confirmed / netflav confirmed |
| 13 | FC2-1879883 | older | sampled:older | dual_reference | 2 | sukebei confirmed / netflav confirmed |
| 14 | FC2-1940353 | older | sampled:older | dual_reference | 2 | sukebei confirmed / netflav confirmed |
| 15 | FC2-1977836 | older | sampled:older | dual_reference | 2 | sukebei confirmed / netflav confirmed |
| 16 | FC2-2050468 | middle | sampled:middle | dual_reference | 2 | sukebei confirmed / netflav confirmed |
| 17 | FC2-2086710 | middle | sampled:middle | dual_reference | 2 | sukebei confirmed / netflav confirmed |
| 18 | FC2-2172250 | middle | sampled:middle | dual_reference | 2 | sukebei confirmed / netflav confirmed |
| 19 | FC2-2278260 | middle | sampled:middle | dual_reference | 2 | sukebei confirmed / netflav confirmed |
| 20 | FC2-2570996 | middle | sampled:middle | dual_reference | 2 | sukebei confirmed / netflav confirmed |
| 21 | FC2-2629560 | middle | sampled:middle | dual_reference | 2 | sukebei confirmed / netflav confirmed |
| 22 | FC2-2733270 | middle | sampled:middle | dual_reference | 2 | sukebei confirmed / netflav confirmed |
| 23 | FC2-2807093 | middle | sampled:middle | dual_reference | 2 | sukebei confirmed / netflav confirmed |
| 24 | FC2-2865991 | middle | sampled:middle | dual_reference | 2 | sukebei confirmed / netflav confirmed |
| 25 | FC2-2909140 | middle | sampled:middle | dual_reference | 2 | sukebei confirmed / netflav confirmed |
| 26 | FC2-2954603 | middle | sampled:middle | dual_reference | 2 | sukebei confirmed / netflav confirmed |
| 27 | FC2-3078940 | middle | sampled:middle | dual_reference | 2 | sukebei confirmed / netflav confirmed |
| 28 | FC2-3084171 | middle | sampled:middle | dual_reference | 2 | sukebei confirmed / netflav confirmed |
| 29 | FC2-3119265 | middle | sampled:middle | dual_reference | 2 | sukebei confirmed / netflav confirmed |
| 30 | FC2-3178581 | middle | sampled:middle | dual_reference | 2 | sukebei confirmed / netflav confirmed |
| 31 | FC2-4070093 | recent | sampled:recent | dual_reference | 2 | sukebei confirmed / netflav confirmed |
| 32 | FC2-4134556 | recent | sampled:recent | dual_reference | 2 | sukebei confirmed / netflav confirmed |
| 33 | FC2-4174411 | recent | sampled:recent | dual_reference | 2 | sukebei confirmed / netflav confirmed |
| 34 | FC2-4266906 | recent | sampled:recent | dual_reference | 2 | sukebei confirmed / netflav confirmed |
| 35 | FC2-4336025 | recent | sampled:recent | dual_reference | 2 | sukebei confirmed / netflav confirmed |
| 36 | FC2-4385140 | recent | sampled:recent | dual_reference | 2 | sukebei confirmed / netflav confirmed |
| 37 | FC2-4493606 | recent | sampled:recent | dual_reference | 2 | sukebei confirmed / netflav confirmed |
| 38 | FC2-4499275 | recent | sampled:recent | dual_reference | 2 | sukebei confirmed / netflav confirmed |
| 39 | FC2-4547366 | recent | sampled:recent | dual_reference | 2 | sukebei confirmed / netflav confirmed |
| 40 | FC2-4548410 | recent | sampled:recent | dual_reference | 2 | sukebei confirmed / netflav confirmed |
| 41 | FC2-4655045 | recent | sampled:recent | dual_reference | 2 | sukebei confirmed / netflav confirmed |
| 42 | FC2-4699133 | recent | sampled:recent | dual_reference | 2 | sukebei confirmed / netflav confirmed |
| 43 | FC2-4791899 | recent | sampled:recent | dual_reference | 2 | sukebei confirmed / netflav confirmed |
| 44 | FC2-4824605 | recent | phase2_frozen | phase2_mandatory | 2 | sukebei confirmed / netflav confirmed |
| 45 | FC2-4825061 | recent | phase2_frozen | phase2_mandatory | 2 | sukebei confirmed / netflav confirmed |
| 46 | FC2-4835063 | recent | sampled:recent | dual_reference | 2 | sukebei confirmed / netflav confirmed |
| 47 | FC2-4972767 | recent | phase2_frozen | phase2_mandatory | 0 | sukebei negative / netflav negative |
| 48 | FC2-4976588 | recent | phase2_frozen | phase2_mandatory | 0 | sukebei negative / netflav negative |
| 49 | FC2-4978035 | recent | phase2_frozen | phase2_mandatory | 1 | sukebei confirmed / netflav negative |
| 50 | FC2-4979299 | recent | phase2_frozen | phase2_mandatory | 1 | sukebei confirmed / netflav negative |

## 5. Rules that now apply

* This set is **never** changed because of a result. An uncovered ID is not replaced and no 51st ID is added.
* An ID later found not to be a real FC2 product stays in the primary denominator and is written up as an
  *invalid-set-item investigation*; only the independent reviewer may allow a dataset-correction round.
* The primary gate (`tools/run_50id_coverage_gate.py --run-kind primary`) runs **once**, from a clean tree whose HEAD
  contains this committed set; its result is the formal numerator / denominator. Diagnostic re-runs are recorded
  separately and never replace it.
