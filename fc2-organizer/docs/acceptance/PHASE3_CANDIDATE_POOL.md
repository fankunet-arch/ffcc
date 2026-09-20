# Phase 3 C3 — candidate pool v2 (frozen)

Machine-readable pool: `docs/acceptance/PHASE3_CANDIDATE_POOL.json`. This file is its human-readable summary.
The pool is frozen by the commit that adds these two files; the formal 50-ID selector reads only that committed JSON.

| Item | Value |
|---|---|
| Pool `schema_version` | **2** |
| Procedure / builder | `PHASE3-CANDIDATE-POOL-v2` — `tools/build_candidate_pool.py` (tri-state lookups, one polite retry, prefix-completeness guard) |
| Created (UTC) | 2026-09-20T21:25:38+00:00 |
| **Pool JSON SHA-256** (audited file, CRLF line endings, 139,732 bytes) | `ffe0b095793a914c9c12cc5af97f220244d4534853d761b523821d5ac0fd4cb9` |
| Pool JSON SHA-256 as stored in git (LF line endings, 135,276 bytes) | `48e8300031f855e995114c30bf815843d5c61bcdcff42492803766b5b95a82e2` |
| C3 Code Head v2 (builder / selector / gate runner) | `578ed56aff9e3b823b39da74dc0fc10dae63456c` |
| C3 Selection Method v2 Head | `3e7bd2ed1436b27f24c09e9e71dd71907c141df8` |
| Historical Code Head v1 / Method v1 Head | `5ad00e525d72759dcff3ae0458a90d8f3b6ac464` / `74c98659394223642a41a1e78a9fae7011ba7f00` |
| Formal 50-ID selector at pool freeze | **NOT RUN** |
| 50-ID set at pool freeze | **NOT FROZEN** |
| Primary coverage gate at pool freeze | **NOT RUN** |
| Aggregation engine / adapters used during pool build | **NO** |
| Engine-derived data in the pool | **NONE** |

**Two hashes, one content.** The builder ran on Windows, whose Python writes `\r\n`; the audited on-disk file is
therefore CRLF (hash `ffe0b095…`). This repository is checked in with `core.autocrlf=true`, so git stores the same
content with LF endings (hash `48e83000…`, which is exactly the CRLF→LF normalisation of the audited bytes). A
checkout on Windows reproduces the first hash, a checkout on Linux / `git show` the second. There is no other
difference between the two. The file was not edited between the audit and the freeze.

## 1. Contents

| Measure | Value |
|---|---|
| Total candidates | **167** |
| Enumerated (reference 1 = sukebei torrent-name listing, then corroborated on reference 2 = netflav) | 160 |
| Phase 2 mandatory IDs | 7 (7 / 7 present) |
| Duplicate canonical IDs | 0 |
| All numbers canonical | PASS |
| Prefix enumerations complete | **40 / 40** (prefixes `10` … `49`), unavailable **0**, per prefix `PER_PREFIX = 4` |
| Candidates per numeric band (all 167) | older 41 · middle 80 · recent 46 |

## 2. Request accounting

| Measure | Value |
|---|---|
| Requests made | **214** (initial 214, retry **0**) |
| Explained by | 40 prefix queries + 160 netflav lookups + 14 lookups for the 7 Phase 2 IDs (7 sukebei, 7 netflav) |
| Unexplained failures / unaccounted requests | **0** |
| Tri-state, candidate-level checks (174 = 167 × 2 − 160 checks shared with prefix queries) | confirmed **74** · negative **100** · unavailable **0** |
| netflav (167 lookups) | confirmed 70 · negative 97 · unavailable 0 |
| sukebei direct lookups (7 mandatory IDs) | confirmed 4 · negative 3 · unavailable 0 |

`negative` means a valid response was received with no exact evidence; `unavailable` (timeout, connection error,
HTTP 403 / 429 / 5xx or other non-200, unusable body) is recorded separately and never as `negative`. This build
had no unavailable lookup, so no retry was needed.

## 3. Validation strength

Counted from **confirmed external references only** (sukebei, netflav exact code match). Phase 2 provenance is
listed in `validity_sources` for the mandatory IDs but is **never** counted in `external_reference_count`.

| Strength | Candidates | of which mandatory |
|---|---|---|
| ≥ 2 external references (dual) | **70** | FC2-4824605, FC2-4825061 |
| exactly 1 external reference (single) | **94** | FC2-4978035, FC2-4979299 (sukebei confirmed; netflav negative) |
| 0 external references — **mandatory provenance-only** | **3** | FC2-1042815, FC2-4972767, FC2-4976588 |

### Provenance-only mandatory IDs

`FC2-1042815`, `FC2-4972767` and `FC2-4976588` have `external_reference_count = 0`: both external references
returned a **valid response with no exact match** (`negative` on sukebei **and** netflav) — they were *not*
unavailable. They remain in the pool and are mandatory for the 50-ID set solely because they are members of the
Phase 2 frozen probe set. They are **provenance-only** IDs; they are neither dual-reference nor single-reference and
are never eligible for sampling.

## 4. Eligibility under Method v2 (non-frozen candidates)

| Band | Range | Tier 1 (≥ 2) | Tier 2 (= 1) | Zero-reference | Eligible (tier 1 + tier 2) | Quota |
|---|---|---|---|---|---|---|
| older | < 2,000,000 | 9 | 31 | 0 | **40** | 14 |
| middle | 2,000,000 – 3,999,999 | 34 | 46 | 0 | **80** | 15 |
| recent | ≥ 4,000,000 | 25 | 15 | 0 | **40** | 14 |

Every band can reach its quota. (The selector's result — which candidates are chosen — is not part of this file and
had not been computed when the pool was frozen.)

## 5. History: Attempt 1 was never frozen

An earlier build with the v1 builder (created 2026-09-20T20:59:28Z, file sha256
`098fc71755d24064802d8ced77f5ad4a66082b7590bec42915fcdfdc62416bfa`) **failed its audit** and was **never committed or
frozen**: 167 candidates, 46 dual / 118 single, dual per band older 9 (needs 14) · middle 34 · recent 2 (needs 14), and
41 of its 214 requests failed but were recorded as "not confirmed", indistinguishable from genuine negatives. It was
kept only as job-scratch evidence; the selector was not run on it. That failure led to the pre-selection amendment
recorded in `docs/acceptance/PHASE3_50_ID_SELECTION_METHOD.md` (Amendment v2) and to builder v2. **This pool was
rebuilt from scratch with builder v2 and does not reuse any Attempt 1 data.**

## 6. Audit result

Read-only pool audit: **PASS** — schema 2; JSON parses; all numbers canonical; no duplicates; 7 / 7 mandatory IDs;
40 / 40 prefix enumerations complete; every check is confirmed / negative / unavailable; every request accounted
for; no `unavailable` lookup exists (so no retry-budget violation) and no confirmed / negative lookup was retried;
the builder imports neither the aggregation engine, the source adapters nor the HTTP transport; the file contains no
aggregate-derived field and no response body, cookie, authorization or private header.
