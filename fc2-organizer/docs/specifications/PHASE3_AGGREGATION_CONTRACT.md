# FC2 Metadata Core — Phase 3 / C1 Aggregation Contract

Status: **frozen at Phase 3 C1**; **revised at Phase 3 C2** (see the revision note below).

> **Revision note (Phase 3 C2).** Retry / backoff, the fine-grained failure taxonomy and
> attempt diagnostics are specified in `PHASE3_RESILIENCE_CONTRACT.md`. C2 changed this
> document in exactly the places marked "(C2)": section 1 (`retry_policy`, strict direct
> constructor, engine client shape), section 3 (the deadline is a *total* budget including
> retries; adapter-raised `CancelledError`; fatal `BaseException`; `error_kind` of the
> isolation / fail-closed results), section 4 (`source_execution_traces`; the invariant list
> is narrowed to what is actually enforced) and section 7 (P2-R-12 is closed, not deferred).
> Everything else is unchanged and its tests still pass.
Scope: multi-source execution + deterministic field-level aggregation
(`fc2_metadata_core.aggregation`). Explicitly **out of scope** here, and not
implemented: circuit breaker, batch jobs, NFO, images,
filesystem organisation, the Amane adapter (later Phase 3 subphases / Phases 4-5).
(C2 added source-local retry / backoff; see `PHASE3_RESILIENCE_CONTRACT.md`.)

Every rule below is enforced by an automated offline test under
`tests/unit/aggregation/` (and `tests/unit/sources/test_registry_create_boundary.py`);
the test file is named next to each rule.

```text
canonical FC2 number
   |  MultiSourceEngine.aggregate(number)        engine.py
   v
ordered SourceConfig (order = default priority)  config.py, policy.py
   |  execute_sources(...)                       execution.py   bounded fan-out, deadlines, isolation
   v
SourceResult x (one per enabled source, in configuration order)
   |  merge_source_results(...)                  merge.py       PURE, no network
   v
AggregationResult                                models.py
```

## 1. Configuration (`config.py`, `policy.py`) — `test_agg_config.py`

`SourceConfig(source_id, enabled=True, base_url=None, deadline_seconds=20.0)` and
`AggregationConfig(sources, max_concurrency=3, field_priority=())` are frozen
dataclasses of immutable members; `AggregationConfig.create(...)` accepts any
iterable and a plain mapping. **Everything is validated at construction, before
any network request**, and rejected with `AggregationConfigError`:

| Rule | Rejected |
|---|---|
| source set | empty set; **no enabled source**; duplicate `source_id`; non-`SourceConfig` members; a list instead of a tuple |
| `source_id` | empty / whitespace-padded / non-`str` |
| `deadline_seconds` | not a number, `bool`, `<= 0`, `nan`, `inf`, `> 600` |
| `max_concurrency` | not an `int`, `bool`, outside `1..64` |
| `enabled` | not a real `bool` |
| `retry_policy` (C2) | not a `RetryPolicy` (on a `SourceConfig`, `None` means "use the aggregation default") |
| `base_url` | see §1.1 |
| `field_priority` | unknown / non-overridable field (including `number`, `field_sources`); a source that is not configured; a duplicate id in one override; an empty override; a bare `str` |

**Direct constructor (C2, LOW-3).** `AggregationConfig(...)` is exactly as strict as
`create(...)`: `field_priority` must be `tuple[tuple[str, tuple[str, ...]], ...]`; a list,
dict, nested list, non-`str` / unhashable field name or malformed entry is an
`AggregationConfigError` (never a `TypeError`), and later mutation of anything the caller still
holds cannot change the config.

**Client shape (C2, LOW-4).** `MultiSourceEngine(config, registry, client)` requires
`client.get` to be an `async` callable (`is_async_get`), decided without issuing a request; a
synchronous `get` is an `AggregationConfigError` at construction.

**Registered?** Whether a `source_id` exists in the registry is checked when the
`MultiSourceEngine` is built (unknown ids are all listed in one
`AggregationConfigError`). A *disabled* source is never looked up.

### 1.1 `base_url` (closes Phase 2 review finding P2-R-08 on the Phase 3 config path)

`validate_base_url` accepts only an absolute `http://` / `https://` URL with a
valid host (DNS name or IP literal). It rejects, without any network activity:
non-`str`; empty; no scheme (`fc2db.net`); no host (`http://`, `https://`); any other
scheme (`ftp:`, `file:`, `javascript:`); embedded userinfo (`user:pw@host`);
a query or fragment (adapters append their own path); a bad or out-of-range
port; an invalid host (`bad_host`, `-x-`, empty label, over-long label); and **any**
control character (CR, LF, NUL, TAB ...), space, backslash, `<>"`{}|^`, non-ASCII
character (use punycode) or a length over 2048. The adapters themselves were not
changed: a malformed `base_url` can no longer reach them through the config path.

### 1.2 Priority

The **order of `sources` is the default priority for every field** (highest
first); only enabled sources take part. `field_priority` may override individual
fields (`title studio publisher release runtime plot actors tags poster_urls
thumb_urls fanart_urls extrafanart source_urls external_ids`). An override lists
*some* sources; the remaining enabled sources follow in default order, so every
field always has a total, deterministic order. An override may name a
configured-but-disabled source (it is skipped).

Provider names appear in exactly one place, `defaults.py`
(`DEFAULT_SOURCE_ORDER = ("fc2db_net", "javdb", "av123")`), as data.
`merge`/`policy`/`execution`/`engine`/`models`/`config` never name a provider and
never import a concrete adapter (`test_agg_guards.py`).

## 2. Registry create boundary (closes P2-R-11) — `test_registry_create_boundary.py`

`SourceRegistry.create(source_id, **kwargs)` returns an object that **is a
`SourceAdapter` and whose `source_id` equals the requested id**, or raises a
`SourceRegistryError` subclass — never a bare `TypeError` / `AttributeError`, never
a foreign object:

| Situation | Error |
|---|---|
| unknown / unhashable id | `UnknownSourceIdError` (also a `KeyError`) |
| factory raises an `Exception` | `SourceFactoryError` (original chained; `KeyboardInterrupt` / `SystemExit` are *not* swallowed) |
| factory returns a non-`SourceAdapter` (`42`, `None`, a class, ...) | `InvalidSourceAdapterError` |
| `register("alias_x", Fc2dbNetAdapter)` (adapter's own id differs) | `SourceIdMismatchError` |
| non-callable factory | `SourceRegistryError` at `register` |

Factories other than classes remain supported.

## 3. Source execution (`execution.py`) — `test_agg_execution.py`, `test_agg_engine.py`

`execute_sources_traced(number, targets, client, *, max_concurrency=3)` (C2) calls
`adapter.fetch(number, shared_client)` for every target -- retrying per
`PHASE3_RESILIENCE_CONTRACT.md` -- and returns exactly one `SourceExecutionTrace`
(every attempt + the final `SourceResult`) per target; `execute_sources` returns only the
final `SourceResult`s.

- **Shared client.** Every adapter receives the *same* `SourceHttpClient` object;
  the engine creates no transport of its own.
- **Order.** Results are in **configuration order**, never completion order
  (test: completion order forced reverse by sleeps → identical output).
- **Bounded concurrency.** An `asyncio.Semaphore(max_concurrency)`; the limit is
  real (peak active `<= limit`) and the run is not serial (peak `== limit` when
  enough sources exist). Default 3, configurable `1..64`.
- **Wall-clock deadline (closes P2-R-09 on the scheduler path).** Each source's
  whole execution runs under **one** `asyncio.timeout(deadline_seconds)` *at this
  boundary* (adapters unchanged; httpx's per-phase timeout is not relied on). **(C2)** That
  budget covers attempt 1 + every backoff pause + every retry; it is never multiplied by
  `max_attempts`. The deadline starts when the source starts executing, not while it waits
  for a concurrency slot. On expiry **only that source** becomes
  `NETWORK_ERROR` / `SOURCE_DEADLINE` (C2) with `error_detail` `"<id>: source execution deadline exceeded
  (<n>s wall clock, <m> ms elapsed)"` and a real `elapsed_ms` (not 0). A builtin
  `TimeoutError` raised *by the adapter itself* is not mistaken for the deadline
  (`scope.expired()` decides). Limitation: an adapter that swallows
  `CancelledError` cannot be interrupted; the adopted adapters do not.
- **Isolation.** Any ordinary `Exception` an adapter leaks becomes that source's
  `INVALID_RESPONSE` / `ADAPTER_EXCEPTION` (C2) with `error_detail` = `"<id>: unexpected adapter exception
  <ExceptionType>"` — the *message is never included* (it may carry a URL or a
  secret). Every non-success `SourceStatus` from an adapter is just data; no
  source outcome stops another source.
- **Cancellation (C2, LOW-2; full table in `PHASE3_RESILIENCE_CONTRACT.md` section 4).** The
  caller cancelling the aggregate task propagates `CancelledError` (siblings cancelled,
  nothing left running). A `CancelledError` an adapter raises *on its own* (no cancellation
  requested) is isolated as that source's `INVALID_RESPONSE` / `ADAPTER_EXCEPTION` and the
  other sources carry on. `KeyboardInterrupt`, `SystemExit`, `GeneratorExit` and any custom
  non-`Exception` `BaseException` are fatal: the **original object** is re-raised (never a
  `BaseExceptionGroup`, never a source result). Known limit: an adapter that swallows
  cancellation cannot be interrupted.
- **Fail closed.** Whatever an adapter returns goes through
  `validate_source_result(slot_id, number, candidate)`: a non-`SourceResult`, a
  result labelled with a different `source_id`, or a `SUCCESS` whose
  `metadata.number != requested number` becomes an `INVALID_RESPONSE` /
  `RESULT_CONTRACT_MISMATCH` (C2) for that slot and contributes **nothing**. The result is labelled by the slot it was executed
  for, never by what it claims.
- A non-canonical number is a caller bug: `InvalidCanonicalNumberInputError`
  before any source is called.

## 4. `AggregationResult` (`models.py`) — `test_agg_guards.py`, `test_agg_merge.py`

Frozen and validated at construction. **(C2)** The precise list of what `__post_init__`
enforces -- and what it does not -- is the module docstring of `aggregation/models.py`;
the C1 claim "an inconsistent result cannot be built" is narrowed to that list. In short:
unique ids; `successful_source_ids` = the `SUCCESS` ids; `FAILED` has no metadata and no
contributors; `SUCCESS`/`PARTIAL` have min-success metadata for the requested number and
`contributing_source_ids == successful_source_ids` exactly; `disabled_source_ids` distinct and
disjoint from the results; every `FieldConflict` names a conflict-capable field and refers
only to contributing sources; `source_execution_traces` is empty or aligned one-to-one with
`source_results`. **Not** verified (it would mean re-running the merge): that the metadata
values, `field_sources` and the conflict list are what the merge rules would produce.

```text
number                    requested canonical number
status                    AggregateStatus.SUCCESS | PARTIAL | FAILED
metadata                  merged NormalizedMetadata | None
source_results            every per-source SourceResult, enabled sources, configuration order
contributing_source_ids   sources whose data participated (SUCCESS + valid), default order
conflicts                 resolved disagreements (FieldConflict), deterministic order
disabled_source_ids       configured-but-disabled sources (never executed)
elapsed_ms                wall time of the whole aggregate lookup
source_execution_traces   (C2) one SourceExecutionTrace per enabled source: every attempt + final result
```

### 4.1 Status semantics (frozen)

*Operational failure* = a source ending `BLOCKED`, `RATE_LIMITED`,
`NETWORK_ERROR`, `PARSE_ERROR` or `INVALID_RESPONSE` (this includes the
fail-closed replacements above and deadline expiry). `NOT_FOUND` is **not** an
operational failure: it means the source answered and does not carry the film.

| Status | Definition | `metadata` |
|---|---|---|
| `SUCCESS` | merged metadata meets minimum success (canonical number + non-empty title) **and** no enabled source had an operational failure | present |
| `PARTIAL` | merged metadata meets minimum success, but at least one enabled source had an operational failure | present |
| `FAILED` | no source produced usable data (so minimum success is not met) | `None` |

Consequences (all tested): `SUCCESS` + `NOT_FOUND` + `NOT_FOUND` → `SUCCESS`;
`SUCCESS` + `NETWORK_ERROR` → `PARTIAL`; `SUCCESS` + `BLOCKED` + `NOT_FOUND` →
`PARTIAL`; all `NOT_FOUND` → `FAILED`; `NOT_FOUND` + `NETWORK_ERROR` + `BLOCKED` →
`FAILED`. `FAILED` still carries **every** `SourceResult`.
`__post_init__` enforces: `FAILED` ⇒ no metadata and no contributors;
`SUCCESS`/`PARTIAL` ⇒ min-success metadata whose `number` is the requested one,
≥ 1 contributor, and (`SUCCESS`: no operational failure / `PARTIAL`: at least one).
Only a source's **final** result counts (C2): a source that failed once and then
succeeded on a retry is a success; its first failure stays visible in its trace.
Only `SUCCESS`-status results contribute: partial metadata attached to a
`PARSE_ERROR` / `INVALID_RESPONSE` is never used.

## 5. Merge (`merge.py`) — pure, `test_agg_merge.py`

`merge_source_results(number, source_results, policy, ...)` is a **pure function**:
no network, clock, asyncio or adapter import. `source_results` is matched **by
position** to `policy.source_order`; a different length is `AggregationInputError`.
It never mutates its inputs and builds a **new** immutable `NormalizedMetadata`
(no `object.__setattr__`, no in-place edits — guarded by a test).

### 5.1 Non-empty

`None` and blank/whitespace-only strings are empty. An `int` `runtime` of `0` **is**
a value (deterministic, documented; not special-cased).

### 5.2 Scalars — `title studio publisher release runtime plot`

The **first non-empty value in that field's priority order** wins. Equal values
(exact `==` and same type) from other sources are *corroborating*; different values
are recorded as a `FieldConflict(field, selected_source_id, selected_value,
alternatives=((source_id, value), ...))`, alternatives in priority order.
Independent of `set`/`dict` order and of async completion order.

### 5.3 `number`

Never chosen from a source: always the requested canonical number.

### 5.4 Collections — `actors tags poster_urls thumb_urls fanart_urls extrafanart source_urls`

**Ordered unique union** following the field's priority order (source A's items,
then B's new items, ...). Deduplication is **exact string equality only** — no
case-folding, whitespace normalisation, translation or fuzzy matching, so people
and tags are never merged wrongly. Blank items are skipped. Result is a `tuple`.

### 5.5 `external_ids`

Merged key by key, **first (highest-priority) value wins** — never last-write-wins.
The same key with a different value is recorded as a `FieldConflict(field=
"external_ids", key=<key>, ...)`; the same key with the same value is not a
conflict. Blank keys/values are skipped.

### 5.6 `field_sources` (provenance)

Recomputed from scratch for the aggregate; **the adapter's own `field_sources` are
ignored entirely** (an adapter cannot forge provenance; test forges
`("other_source",)` and it does not leak). Authority = the slot's configured
`source_id` + the *actual* values. Keys appear in a fixed order
(`number title studio publisher release runtime plot actors tags poster_urls
thumb_urls fanart_urls extrafanart source_urls external_ids`); only populated
fields have an entry; the source tuples are in **priority order**:

| Field | `field_sources[field]` |
|---|---|
| `number` | every contributing source, in **default source order** |
| scalar | every contributing source whose value equals the selected value (priority order); the selected source first |
| collection | every source that supplied ≥ 1 non-blank item (priority order) |
| `external_ids` | every source that supplied ≥ 1 non-blank pair (priority order) |

## 6. Determinism

Output depends only on `(number, results in slot order, policy)`. Not on `set` /
hash order, async completion order, wall time or the number of runs (tested by
repetition, reversed completion order, and random priority permutations).

## 7. What C1 deliberately does not do

- ~~No retry, backoff or circuit breaking.~~ **(C2)** Source-local retry and deterministic
  backoff now exist (`PHASE3_RESILIENCE_CONTRACT.md`). **P2-R-12 is CLOSED** there: a
  structured `SourceErrorKind` taxonomy (HTTP 5xx -> `INVALID_RESPONSE` /
  `HTTP_SERVER_ERROR`, transport exceptions -> `TIMEOUT` / `CONNECTION_ERROR` /
  `DECODE_ERROR` / `REDIRECT_ERROR` / `RESPONSE_TOO_LARGE`), and the retry decision reads only
  that kind. **Circuit breaking is still not implemented** (it belongs with batch scheduling).
- No batch engine, no 50-ID acceptance run (the ≥ 90 % `number + title` gate on the
  frozen 50-ID set is still to be run in a later live-coverage subphase; nothing here
  claims it).
- No NFO writer, image download, file moves, Amane adapter, GUI.
