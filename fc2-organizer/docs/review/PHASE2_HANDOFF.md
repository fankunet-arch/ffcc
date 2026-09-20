# PHASE2_HANDOFF.md

```text
Phase: Phase 2 — Source adapter framework + live source verification

Review Base:
e6472f948f885c52e6f4c62cf29383e9dcd3d4e3
(docs(review): add Phase 1 R2 handoff)

Phase 2 WIP checkpoint (already pushed; not amended/squashed/reset):
948fc23b672da454e14a577ad7eb7b833d378310

Code Review Candidate (FINAL_PHASE2_CODE_HEAD):
3a23e6fa9a351b5c3bc6d2159028177616f98371

Review range:
e6472f948f885c52e6f4c62cf29383e9dcd3d4e3..3a23e6fa9a351b5c3bc6d2159028177616f98371

Phase 2 Reviewed Docs Head:
4e7883e87bd6195080d1eb5afcefda0a8897600d

Branch:
claude/phase-0-amane-integration-fnvhpq
```

**This is a review candidate, not a PASS declaration.** Phase 3 (aggregation)
has not been started.

> **Corrections applied at Phase 3 Entry C0-05** (facts only, after the
> independent Phase 2 review returned PASS WITH NON-BLOCKING NOTES; nothing
> else in this document was rewritten):
> 1. the header no longer says the Docs Head was "reported externally" (a
>    self-reference placeholder) — it now records the reviewed Docs Head;
> 2. the "all my commits are local / nothing pushed" line was wrong once
>    Phase 2 was pushed and has been replaced (see *Local workspace notes*);
> 3. the live near-misses for `FC2-4824605` are `FC2-1824605` and
>    `FC2-4724605` (an earlier draft wrote `FC2-1825061`, which is the near-miss
>    for `FC2-4825061`);
> 4. the test count is recorded as 309 collected / 309 passed, and the
>    "80 new offline tests" wording in the `45be2b7` commit message is noted as
>    a rough historical description (history is not amended).

## What Phase 2 delivers

| Layer | What | Where |
|---|---|---|
| Framework (in WIP `948fc23`) | `SourceAdapter` contract, `SourceRegistry`, transport-agnostic `SourceHttpClient` Protocol + `HttpxTransport`, `tools/probe_sources.py` | `src/fc2_metadata_core/{sources,http}`, `tools/` |
| Live research | 15 candidate entries probed live; 3 adopted | `docs/sources/SOURCE_VIABILITY_*.md`, `docs/SOURCE_STATUS_MATRIX.md` |
| Probe set | 7 known-valid IDs, each independently corroborated | `docs/PHASE2_PROBE_SET.md` |
| Evidence | machine JSON (raw + adapter probes) and manual observations | `docs/source-probes/` |
| Adapters | `fc2db_net`, `javdb`, `av123` + shared `_common.py` | `src/fc2_metadata_core/sources/adapters/` |
| Offline tests | parser + `fetch` contract against verbatim real-response fixtures | `tests/unit/sources/adapters/`, `tests/fixtures/sources/` |

Commits after the WIP checkpoint, oldest first:

```text
ee14d0b chore: ignore .pytest_cache and *.egg-info local artifacts
45be2b7 feat(source): add fc2db_net, av123 and javdb adapters with offline parser tests
3a21c4b fix(source): name the exception type in transport-error details
3a23e6f docs(source): Phase 2 live source viability research, evidence and probe set
```

## Gate result (spec §11 / Phase 2)

| Requirement | Result | Evidence |
|---|---|---|
| Ordinary public HTTPS is not a sandbox synthetic 403 | met — real 200s from example.com / wikipedia.org / fc2.com; egress is a Spanish network (`cf-ray …-MAD`) | manual observations §1 |
| Real candidate research with `probe_sources.py raw` before any adapter | met — raw probes precede every adapter; final raw pass 12:57–12:58 UTC | `PHASE2_PROBE_20260920.json` |
| >=5 provider families, incl. FC2 Official + several aggregators | met — 15 entries (see matrix) | `SOURCE_STATUS_MATRIX.md` |
| FC2 Official actually investigated | met — **BLOCKED: login wall** (302 chain to `fc2.com/ja/login.php`) | `SOURCE_VIABILITY_fc2_official.md`, manual §2 |
| >=5 known-valid IDs | met — 7 | `PHASE2_PROBE_SET.md` |
| SOURCE_VIABILITY document per candidate | met — 15 documents | `docs/sources/` |
| Adapter only for a live, qualifying source | met — 3 adapters, all for sources that passed raw probing first | — |
| Each VERIFIED source: real adapter run, >=2 IDs `SUCCESS`, number + non-empty title, no login, no CAPTCHA/CF bypass, offline tests | met for all 3 | table below |
| >=2 independent VERIFIED sources (Gate); 3 = strong target | **3 VERIFIED** | table below |
| No Phase 3 aggregation | met — adapters never call each other (asserted by a test) | `test_adapter_registration.py` |

VERIFIED sources (Gate run 2026-09-20 13:02:27–13:03:21 UTC, code `3a21c4b`;
adapter runs went through the real `HttpxTransport`, one request per lookup,
~2.5 s apart, no cookies):

| Source ID | Provider | `SUCCESS` IDs (of 7) | Fields beyond number/title |
|---|---|---|---|
| `fc2db_net` | fc2db.net | 6 (`4824605 4979299 4976588 1042815 4978035 4972767`) | release, runtime, actors, publisher(seller), tags, thumb |
| `javdb` | javdb.com public search listing | 6 (`4825061 4979299 4976588 1042815 4978035 4972767`) | release, thumb, external id |
| `av123` | 123av.com | 3 (`4825061 4979299 4978035`) | release, runtime, tags |

Each source also returned `NOT_FOUND` for IDs the *others* carry (a real 404
or "no exact hit"), which is the point of having three: see the per-ID table
in `SOURCE_STATUS_MATRIX.md`.

**Also honestly recorded:** one transient timeout (`fc2db_net`,
`FC2-4978035`, 13:01, first gate pass at `45be2b7`). It exposed an
`error_detail` of just `transport error: ` (httpx timeouts stringify to `""`);
fixed in `3a21c4b` (`transport error: HttpTimeoutError`), the whole gate was
re-run at `3a21c4b` and passed. Both passes are in the JSON.

## Decisions that a reviewer should challenge

1. **`javdb` is search-listing only.** Its detail pages redirect to `/login`
   (manual §3), so the adapter never requests them and cannot supply
   actors/tags/runtime. It still satisfies the Gate (number + Japanese title +
   release + cover) without any private session. If you consider a
   fields-poor source unacceptable as a "VERIFIED", the Gate still holds with
   `fc2db_net` + `av123` alone (2 sources), but with only one Japanese-title
   source.
2. **`javdb` search is fuzzy.** The adapter accepts only the hit whose number
   equals the request; near-misses (`FC2-1824605`, `FC2-4724605` for
   `4824605`) give `NOT_FOUND`. Tested offline against the real fuzzy page
   and live (`FC2-4824605` → `NOT_FOUND`).
3. **`NormalizedMetadata.runtime` unit.** The Core contract only says
   `int >= 0`. The adapters emit **whole minutes** (`"55:23"` → 55,
   `"1:02:03"` → 62; seconds dropped). This is my choice, documented in
   `_common.duration_to_minutes`; Phase 1's contract does not settle it and
   the Phase 5 NFO writer must agree.
4. **`123av` titles are English machine translations**, and its "Maker" is the
   constant bucket `FC2`, deliberately *not* mapped to `studio`/`publisher`.
   Phase 3 should weight it below JP-title sources for `title`.
5. **`fc2db_net.thumb_urls` vs `poster_urls`.** The cover is a 600×600 crop
   labelled as a thumbnail, so it goes to `thumb_urls`; no source here
   provides a poster/fanart.
6. **One change to Phase-2 framework code after the WIP checkpoint:**
   `sources/base.py::transport_error_result` now names the exception type in
   `error_detail` (+1 test in `tests/unit/sources/test_base.py`). Everything
   else in the framework/WIP is untouched.
7. **Probe tool change:** `tools/probe_sources.py raw` now also records page
   `<title>`, `server` and `cf-mitigated` (still no bodies/cookies), so the
   evidence file says what kind of 200/403/404 it saw. Records written before
   that lack the three fields (noted in the manual-observations file).

## Independence — read this before relying on "3 sources"

The three VERIFIED sources are independent *services* (different operators,
hosts, page formats, and each carries works the others lack). They are **not**
independent *origins*: all copy FC2 Content Market data, and all three sit
behind Cloudflare's CDN. An FC2 takedown wave or a Cloudflare-wide incident
would hit all three. FC2 Official itself is the only origin and is login-gated.

## Environment facts that shaped the research

- **Spanish ISP-level IP block.** `fc2ppvdb.com` and `onejav.com` resolve to
  `188.114.96.5`/`188.114.97.5`; from this network HTTPS fails with
  `self-signed certificate` and plain HTTP returns a notice citing a
  Barcelona commercial-court judgement (18 Dec 2024, LaLiga/Telefónica).
  Both are therefore **unevaluated, not dead** (manual §4). Certificate
  verification was not disabled and no alternative route was used. They should
  be re-probed from another network before Phase 3 fixes its source list.
- Cloudflare-challenged (403, `cf-mitigated: challenge`), **not bypassed**:
  `fd2ppv.cc` work pages, `javten.com`, `supjav.com`, `missav.ws`, `fc2db.com`.
- `fc2cm.com` is stale (newest work 4699535), flaky (`sql error` bodies) and
  reports missing works as HTTP 200 — rejected.

## Tests

Offline suite (no network):

```text
cd fc2-organizer
python -m pytest -q
309 collected / 309 passed
```

Breakdown of the change from the 228 at the WIP checkpoint: **+76** new tests in
`tests/unit/sources/adapters/` (common 24, fc2db_net 17, javdb 17, av123 15,
registration 3), **+1** in `tests/unit/sources/test_base.py`, and **+4**
because `tests/contract/test_core_independent_of_amane.py` is parametrized
over every module in the package and therefore automatically covers the four
new modules (`_common`, `fc2db_net`, `av123`, `javdb`) — so none of them
imports Amane. (The `45be2b7` commit message says "80 new offline tests"; that
is only a rough description in a historical commit message, which is
deliberately not amended. The numbers above are the record: 309 collected /
309 passed.)

Adapter tests use fixtures under `tests/fixtures/sources/`, each a *verbatim
excerpt of a real response* (provenance comment at the top of each file);
only ads/scripts/navigation were removed. They cover, per adapter: exact field
extraction on two real pages, real 404 page, every failure status
(403/429/5xx/Cloudflare-challenge-under-200/login redirect), transport errors,
wrong-number page (`INVALID_RESPONSE`, never a silent success), missing/blank
title (`PARSE_ERROR`), non-canonical input rejected before any request, and
`base_url` override.

Live checks are **not** part of the offline suite (they depend on the network
and on third-party sites). To repeat them:

```text
python tools/probe_sources.py adapter --source fc2db_net FC2-4824605 FC2-4979299
python tools/probe_sources.py adapter --source javdb     FC2-4825061 FC2-4979299
python tools/probe_sources.py adapter --source av123     FC2-4825061 FC2-4979299
```

(2.0 s between requests by default; each run appends to
`docs/source-probes/PHASE2_PROBE_<date>.json` unless `--no-record`.)

## Known limitations / deliberately deferred

- No throttling, retry, backoff, per-host concurrency or circuit breaking:
  Phase 3. Each `fetch` makes exactly one request. `javdb` is the most likely
  to rate-limit; a `429` maps to `RATE_LIMITED`.
- The parsers are regex/JSON-LD based against today's markup. Layout changes
  will surface as `PARSE_ERROR`/`INVALID_RESPONSE`, not as wrong data (number is
  always cross-checked against the page); fixtures pin the current markup.
- The 15 s default transport timeout produced one transient failure in live use;
  retry policy is a Phase 3 concern.
- Terms-of-service: these are third-party adult index sites. The adapters read
  one public page per lookup at a low rate and are not bulk crawlers; whether
  to ship them enabled by default is a product decision for later phases.
- Coverage is uneven (see the per-ID table): no single source carries all 7 IDs;
  `av123` covers 3/7. Phase 3 must treat `NOT_FOUND` from one source as normal.

## Local workspace notes

- `.gitignore` now ignores `.pytest_cache/` and `*.egg-info/` (`ee14d0b`);
  the stray `src/fc2_metadata_core.egg-info/` was deleted.
- `fc2-organizer/.pytest_cache/` could **not** be deleted: it is unreadable to
  the current (non-elevated, medium-integrity) user — `Get-ChildItem`,
  `icacls`, `Get-Acl` all return *Access denied*; `dir /q` shows an
  unresolvable owner (`...`); the parent directory grants `Ctg` full control.
  `.venv` next to it is owned by `BUILTIN\Administrators`, suggesting an
  earlier elevated run created these. It is git-ignored now and only produces
  a `PytestCacheWarning`; all tests pass. Minimal fix (elevated PowerShell,
  this directory only):
  `takeown /f .pytest_cache /r /d y; icacls .pytest_cache /reset /t; Remove-Item -Recurse -Force .pytest_cache`.
- Push status: Phase 2 (through Docs Head `4e7883e87bd6195080d1eb5afcefda0a8897600d`)
  has been pushed to `origin/claude/phase-0-amane-integration-fnvhpq` and
  independently reviewed (PASS WITH NON-BLOCKING NOTES).

## Phase 3 NOT started

No aggregation, no cross-source scheduling, no field-level merge, no retry
policy, no Amane adapter work has been done.
