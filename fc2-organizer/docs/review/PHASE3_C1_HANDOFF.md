# PHASE3_C1_HANDOFF.md

```text
Phase: Phase 3 / C1 — Multi-source Aggregation Core

Base (Phase 3 Entry C0 R1 Docs Head; C0 CLOSED, Aggregator Lock RELEASED):
26ac53714c69f7c716cdcbe66783bebe1d2be118

PHASE3_C1_CODE_HEAD (Phase 3 C1 Code Review Candidate):
652f1dea7ec2dd1ca93d278906d0d487e6df2f19
  = 1e12c6b  fix(source): harden SourceRegistry.create boundary (P2-R-11)
  + 26917af  feat(aggregation): add Phase 3 C1 multi-source aggregation core
  + 652f1de  test(aggregation): assert the original BaseException propagates unwrapped

Formal review range:
26ac53714c69f7c716cdcbe66783bebe1d2be118..652f1dea7ec2dd1ca93d278906d0d487e6df2f19

PHASE3_C1_DOCS_HEAD:
the commit "docs(review): add Phase 3 C1 handoff" whose parent is the Code Head
above and whose only change is this file (docs diff: CODE_HEAD..DOCS_HEAD).
A commit cannot contain its own hash, so it is identified by that rule and
reported in the hand-back message.

Branch:
claude/phase-0-amane-integration-fnvhpq
```

**Not a PASS declaration.** This is a candidate for independent Phase 3 C1 review.
Later Phase 3 subphases (C2+) have **not** started.

## Architecture

New package `src/fc2_metadata_core/aggregation/` (no import of `amane`, no import of
a concrete adapter, no provider name outside `defaults.py` — all three enforced by
tests):

```text
canonical FC2 number
   | MultiSourceEngine.aggregate(number)                      engine.py
   v
ordered SourceConfig (configured order = default field priority)   config.py policy.py defaults.py
   | execute_sources(...)  bounded fan-out, per-source wall-clock deadline,
   |                       isolation, fail-closed validation   execution.py
   v
SourceResult x N  (one per enabled source, configuration order)
   | merge_source_results(...)   PURE: no network / clock / asyncio       merge.py
   v
AggregationResult  SUCCESS | PARTIAL | FAILED + every SourceResult        models.py
```

| Module | Responsibility |
|---|---|
| `policy.py` | field constants, `AggregationPolicy` (default + per-field total priority orders), `AggregationConfigError` |
| `config.py` | immutable `SourceConfig` / `AggregationConfig`, `validate_base_url`, limits |
| `defaults.py` | the only place providers are named — `DEFAULT_SOURCE_ORDER = (fc2db_net, javdb, av123)` as data |
| `execution.py` | `SourceTarget`, `execute_sources` (`Semaphore`, `asyncio.timeout`, `TaskGroup`) |
| `merge.py` | `merge_source_results`, `validate_source_result` (pure) |
| `models.py` | `AggregationResult`, `AggregateStatus`, `FieldConflict`, invariants |
| `engine.py` | `MultiSourceEngine(config, registry, client)`: wires the above |

Other changes: `SourceRegistry.create` boundary hardening (P2-R-11);
`build_default_registry()` in `sources/adapters`; `tools/probe_aggregate.py`
(live smoke, records nothing by default).

## Contract decisions (full text: `docs/specifications/PHASE3_AGGREGATION_CONTRACT.md`)

- **Aggregate status.** `SUCCESS` = merged metadata meets minimum success **and** no
  enabled source had an *operational* failure (`BLOCKED`, `RATE_LIMITED`,
  `NETWORK_ERROR`, `PARSE_ERROR`, `INVALID_RESPONSE`). **`NOT_FOUND` is a normal
  coverage gap and never downgrades to `PARTIAL`.** `PARTIAL` = min-success metadata
  + ≥ 1 operational failure. `FAILED` = nothing usable (`metadata is None`), but
  **every `SourceResult` is kept**. `AggregationResult.__post_init__` makes an
  inconsistent result unconstructible.
- **Source order / priority.** Configured source order is the default priority for every
  field; optional per-field overrides (validated: known field, configured source,
  no duplicates, `number` not overridable). An override lists some sources; the rest
  follow in default order — a total order per field.
- **Scalars** (`title studio publisher release runtime plot`): first non-empty value by
  the field's priority; equal values corroborate; differing values are recorded as a
  `FieldConflict`. **`number`** is always the requested number.
- **Collections** (`actors tags poster_urls thumb_urls fanart_urls extrafanart
  source_urls`): ordered unique union by priority; **exact string equality only** (no
  case-fold / translation / fuzzy); blanks skipped; tuples.
- **`external_ids`**: key by key, **first-wins** (never last-write-wins); conflicts are
  recorded in `AggregationResult.conflicts` (model added, not just documented).
- **`field_sources`**: recomputed from *slot source id + actual values*; the adapter's
  own `field_sources` are ignored (a forged claim cannot leak — tested). Number →
  every contributing source (default order); scalar → sources whose value equals the
  selected one; collection / `external_ids` → sources that supplied ≥ 1 non-blank item.
- **Fail closed.** A result with a wrong `source_id`, a non-`SourceResult`, or a `SUCCESS`
  for another number becomes `INVALID_RESPONSE` for that slot and contributes nothing.
- **Determinism.** Output depends only on `(number, results in slot order, policy)`.

## Source execution

- One shared `SourceHttpClient` (the caller's); no transport is created by the engine.
- `asyncio.Semaphore(max_concurrency)`, default **3**, configurable `1..64`; proven
  by peak-active counters (limit respected **and** reached — not serial).
- Results are returned in **configuration order** (completion order forced reverse by
  sleeps in tests).
- Per-source **wall-clock deadline** (default **20 s**, configurable, `> 0 … ≤ 600`):
  `asyncio.timeout` at the engine boundary, adapters untouched. Starts when the source
  starts running (not while queued). Expiry → only that source `NETWORK_ERROR`,
  `error_detail` "… source execution deadline exceeded (…)", real `elapsed_ms`; others
  continue. A `TimeoutError` raised by the adapter itself is not mistaken for it.
- **Isolation**: any ordinary `Exception` → that source's `INVALID_RESPONSE`, detail =
  source id + exception *type* only (the message — possible URL/secret — is never
  included; tested with a secret-bearing message).
- **Cancellation**: `CancelledError`, `KeyboardInterrupt`, `SystemExit` are never turned
  into a source result. Verified: the *original* exception propagates unwrapped, and
  in-flight siblings are cancelled (`TaskGroup`).

## Findings closed / re-deferred

| ID | Result |
|---|---|
| **P2-R-08** malformed `base_url` → raw exception | **CLOSED at the Phase 3 config boundary.** `validate_base_url`, run when a `SourceConfig` is constructed, rejects (domain `AggregationConfigError`, before any network): no scheme, no host, non-http(s), userinfo, query/fragment, bad port, invalid host, any control character (CR/LF/NUL/TAB), space, backslash, non-ASCII, > 2048 chars. Adapters were not rewritten. (`test_agg_config.py`: 9 valid + 33 invalid URLs.) |
| **P2-R-09** httpx timeout is not a wall-clock bound | **CLOSED at the scheduler boundary.** Whole-`fetch` deadline per source (see above); a dribbling source that keeps making progress is still cut off (tested). Limitation: an adapter that swallows `CancelledError` cannot be interrupted (none of the adopted ones do). |
| **P2-R-11** registry create boundary | **CLOSED.** `create()` returns a `SourceAdapter` whose `source_id` equals the requested id, else `SourceFactoryError` / `InvalidSourceAdapterError` / `SourceIdMismatchError` (all `SourceRegistryError`); non-callable factories rejected at `register`; factories other than classes still supported. Reproduces and closes both reviewer examples (`alias_x` → `Fc2dbNetAdapter`, `lambda **k: 42`). |
| **P2-R-12** classification nuances (5xx → `INVALID_RESPONSE`, some decode errors → `NETWORK_ERROR`, retry semantics) | **RE-EVALUATED → RE-DEFERRED to the Phase 3 resilience/retry subphase.** Reason: C1 only *isolates and aggregates* `SourceStatus`; it makes no retry, backoff or circuit-breaker decision from a status, so nothing in C1 depends on the fine classification, and rewriting the Phase 2 failure vocabulary now would be speculative. Not an omission. Practical effect seen live: a transient av123 HTTP 500 is `INVALID_RESPONSE` → counts as an operational failure → aggregate `PARTIAL` (see below). |

## Files changed (`26ac537..652f1de`, 21 files, +3341/−7)

```text
A docs/specifications/PHASE3_AGGREGATION_CONTRACT.md
M src/fc2_metadata_core/__init__.py                     (imports aggregation)
A src/fc2_metadata_core/aggregation/{__init__,config,defaults,engine,execution,merge,models,policy}.py
M src/fc2_metadata_core/sources/__init__.py             (exports new registry errors)
M src/fc2_metadata_core/sources/adapters/__init__.py    (+build_default_registry)
M src/fc2_metadata_core/sources/registry.py             (create boundary)
A tests/support/scripted_adapters.py
A tests/unit/aggregation/test_agg_{config,engine,execution,guards,merge}.py
A tests/unit/sources/test_registry_create_boundary.py
A tools/probe_aggregate.py
```

No change to any adapter, `_scan.py`, the transport, the models, the Phase 2 evidence
JSON, or any C0/C0-R1 closed item.

## Offline tests

```text
Python 3.12.10
python -m pytest --collect-only -q   -> 731 tests collected
python -m pytest -v                  -> 731 passed
python -m pytest -q                  -> 731 passed
```

| | count |
|---|---|
| collected | **731** |
| passed | **731** |
| failed | 0 |
| skipped | 0 |

**+258 vs the frozen 473** = 250 new tests (config 94, merge 46 — the pure-merge tests are
the largest group besides config — execution 50, engine 20, guards 22, registry boundary
18) + 8 because `tests/contract/test_core_independent_of_amane.py` is parametrized over
every module (F4 stays green and now covers the eight new modules). All 473 existing
tests pass unchanged. Timing tests use short real sleeps (≤ 0.3 s) with wide margins.
The C1 required-test list (1–24) is covered; the numbers appear in test names
(`test_01…` … `test_24…`), incl. concurrency (5 sources, `max_concurrency=2` → peak == 2),
reversed completion order, deadline, cancellation, forged `field_sources`, wrong number /
`source_id`, junk / mismatched registry factories, malformed `base_url`. **Three real
adapters** are also exercised end-to-end through the default config from the verbatim
real-response fixtures (no network).

*Test-isolation note:* the F4 contract test re-imports the package, so a test that imports
core classes **inside a function** gets different class objects than one imported at module
top (`isinstance` fails). Two of my first tests did this and failed only in the full run;
fixed by importing at module top. Worth knowing for later test authors.

## Live aggregate smoke (`tools/probe_aggregate.py`, records nothing)

Default config `fc2db_net > javdb > av123`, one shared `HttpxTransport`, 3 s between
numbers, one request per source per number; Windows public network. Phase 2 evidence JSON
untouched.

**At `652f1de`, 2026-09-20 16:47:00–16:47:24 UTC — 7/7 `SUCCESS`:**

| Number | Aggregate | Source outcomes (fc2db_net / javdb / av123) | Title from | Notes |
|---|---|---|---|---|
| **FC2-4825061** | SUCCESS | not_found / success / success | `javdb` (JP) | the known fc2db_net coverage gap is *not* a failure; runtime 39 + tag from av123 |
| **FC2-4824605** | SUCCESS | success / not_found / not_found | `fc2db_net` | javdb fuzzy near-miss ⇒ not_found; av123 gap |
| **FC2-4979299** | SUCCESS | success / success / success | `fc2db_net`, `javdb` | `number`←3 sources; tags = union (23), source_urls 3, thumbs 2, external id from javdb; conflicts: `title` (av123 English) and `runtime` (av123) resolved for fc2db_net |
| FC2-4976588 | SUCCESS | success / success / not_found | `fc2db_net` | |
| FC2-1042815 | SUCCESS | success / success / not_found | `fc2db_net` | old id |
| FC2-4978035 | SUCCESS | success / success / success | `fc2db_net` | |
| FC2-4972767 | SUCCESS | success / success / not_found | `fc2db_net` | |

An identical 7/7 run at `26917af` (the code is identical; `652f1de` changes only a test and a
contract sentence) gave the same statuses. Uneven coverage never made a film fail.

**A transient failure observed and kept on record.** In my *first* live run (three headline
numbers, before the code freeze) `av123` answered **HTTP 500** for FC2-4825061 and
FC2-4824605 (also for a direct single-adapter probe at the same moment; recovered a few
minutes later — 200 at 16:43). The engine behaved as designed: `FC2-4825061` came out
**PARTIAL** (`javdb` succeeded, title from `javdb`, `av123` = `INVALID_RESPONSE`
"unexpected HTTP 500", `fc2db_net` = not_found), and `FC2-4824605` **PARTIAL** with the
title from `fc2db_net`. This is the intended `PARTIAL` semantics and also a concrete
instance of why P2-R-12 (5xx classification) matters once retry exists.

## 50-ID acceptance gate — NOT RUN, DEFERRED

The v1.0 gate (frozen 50-ID valid set, ≥ 90 % obtain `number + title`) is **not** run
and **not** claimed. It needs a frozen ID list and a live-coverage subphase; no numbers
were assembled just to satisfy it here. The 7 probe-set IDs above are a smoke check, not
that gate.

## Decisions a reviewer may want to challenge

1. `AggregationConfig.field_priority` is stored as a tuple of `(field, source_ids)` pairs
   (immutability without `object.__setattr__`); `AggregationConfig.create(...)` is the
   friendly constructor taking a mapping.
2. `merge_source_results` matches results **by position** to the policy's enabled-source
   order (a result labelled with another id is fail-closed, not re-routed).
3. Fail-closed replacements and unexpected adapter exceptions are `INVALID_RESPONSE`, hence
   *operational failures* → `PARTIAL` when another source succeeded.
4. `runtime = 0` counts as a value (no special-casing); strings are "empty" when blank.
5. `validate_base_url` is strict: non-ASCII (IDN must be punycode), userinfo, query and
   fragment are rejected.
6. Aggregation results keep each adapter's own `elapsed_ms`; only engine-produced results
   (deadline, exception) carry engine-measured time. P2-R-07 (transport-level `elapsed_ms = 0`)
   is untouched.
7. A source id may be *configured* but unregistered only if it is **disabled**; an enabled
   unknown id makes engine construction fail with all unknown ids listed.

## Remaining backlog (unchanged / not touched)

- **P2-R-05** probe `anti_bot_hint` fires on `cf-ray` alone — LOW.
- **P2-R-06** probe `requested_url` is the final URL — LOW.
- **P2-R-07** transport-level failure `elapsed_ms = 0` — LOW (C1's own deadline/exception results
  do carry real elapsed time).
- **P2-R-10** JavDB title double-unescape — LOW, kept as-is.
- **P2-R-12** — re-deferred (above), to the resilience/retry subphase.
- **F3, F5** — DEFERRED (definitions in the earlier review reports; must close before Phase 5
  integration); nothing in C1 touched their mechanisms. **F4** stays CLOSED.

## Not started (Phase 3 C2+ and beyond)

Retry / backoff — **NOT STARTED**. Circuit breaker — **NOT STARTED**. Batch engine /
500-item batch / failed-subset retry — **NOT STARTED**. NFO writer, image download, file
rename/move, directory organisation — **NOT STARTED**. Amane adapter, GUI — **NOT STARTED**.
The 50-ID coverage gate — **NOT RUN**.

**READY FOR PHASE 3 C1 INDEPENDENT REVIEW** — not "C1 PASS", not "Phase 3 PASS", not
"50-ID gate passed".
