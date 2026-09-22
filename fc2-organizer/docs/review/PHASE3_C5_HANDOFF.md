# Phase 3 / C5 Handoff — Shared Host Resource Control & Circuit Breaker

**C5 Base:** `83d7d6ff6e9ac21bcb3417cc7d814e9b91a814d0` (Phase 3 C4-R1 Docs Head)
**C5 Code Head:** `fb4dddaf4ef00ed201c94d9a7e29d1e86a20f17d`
**Contract:** `docs/specifications/PHASE3_RESOURCE_CONTROL_CONTRACT.md`
**Python:** 3.12.10

Baseline at C5 Base: 1927 collected / 1927 passed / 0 failed / 0 skipped.
At Code Head: **2361 collected / 2361 passed / 0 failed / 0 skipped** (434 new tests; run three times, plus
per-suite breakdown below, all green).

Implementer role only — this document is a handoff, not a review verdict. See §12 for the exact acceptance
statement.

## 1. What C5 adds

`fc2_metadata_core.resource_control` — a new leaf package (`errors.py`, `host_key.py`, `config.py`,
`host_limiter.py`, `circuit_breaker.py`, `governor.py`) providing one explicit, non-singleton resource domain:
a shared **per-host concurrency limiter** and a shared **per-source-id circuit breaker**. It depends only on
`SourceResult`/`SourceStatus`/`SourceErrorKind` and `errors`; it imports nothing from `batch`, `aggregation`,
concrete adapters, `httpx` or `amane` (enforced by AST guards in `tests/unit/resource_control/test_rc_architecture.py`).

Integration is **opt-in**: `MultiSourceEngine(config, registry, client, governor=...)`. Without `governor=`, C4
behaviour is byte-for-byte unchanged (no host key is derived, no adapter default URL is even inspected). With it:

- `MultiSourceEngine.__init__` derives each enabled source's `HostKey` once, at construction, from its configured
  `base_url` (or the adapter's `default_base_url`), through the existing `aggregation.validate_base_url` and the
  new `host_key_for_base_url` — never from a response, redirect, error text or trace. A base URL that cannot be
  keyed raises `AggregationConfigError` before any request.
- `aggregation/execution.py`'s `_execute_one` calls `governor.admit(source_id, host)` before the retry loop; an
  open breaker short-circuits to a structured `NETWORK_ERROR`/`CIRCUIT_OPEN` result with **zero** attempts and
  no host permit. Otherwise every attempt acquires a host permit, re-validates the admission is still current,
  fetches, and releases the permit — a retry's backoff pause holds no permit. Exactly one `record_result` (the
  final result) or `release` (cancel/fatal/not attempted) settles the ticket, in a `finally`.

## 2. Host key

`HostKey(host: str, port: int)` — frozen, hashable, ordered. `host_key_for_base_url(base_url)`:

- host lower-cased, one trailing dot stripped, IP literals canonicalised via `ipaddress` (IPv6 deterministic,
  zone ids rejected);
- effective port = explicit port, else 80 (`http`)/443 (`https`) — `https://x`, `https://x:443`, `https://X.`
  all key identically; `https://x:8443` and `http://x` differ;
- **path is ignored**: `https://x/a` and `https://x/b` share one key (two sources on one host share one budget);
- userinfo/query/fragment rejected (defence in depth — `aggregation.validate_base_url` already rejects them
  upstream of the engine's call site).

`HostKey.parse("host:port")` (IPv6 bracketed) is the inverse used for per-host overrides. 130 tests in
`test_rc_host_key.py`.

## 3. Configuration

`HostLimitPolicy(default_max_in_flight_per_host=4, overrides=())` — default and every override in **1..64**
(`bool` rejected); `.create(default, {"host:port": limit})` canonicalises and rejects duplicate/malformed keys,
at most 256 overrides, before any network. `.limit_for(host)` is static — **no adaptive limit in C5**.

`CircuitBreakerPolicy(failure_threshold=3, open_duration_seconds=30.0, half_open_max_calls=1)` — threshold
**1..100** (int, not bool), duration finite `(0, 3600]`, probes **1..16** (int, not bool). All frozen, hashable,
validated in `__post_init__`. `test_rc_config.py`.

## 4. Host limiter semantics

`HostLimiter` (per host key, created lazily — O(distinct hosts)): strict FIFO with direct hand-off (a released
permit goes to the oldest waiter in the same call, never to a newcomer); a waiter cancelled while queued removes
itself with no permit leak; a waiter cancelled in the very iteration it was granted the permit gives it back to
the pool. `HostPermit.release()` is idempotent; `with permit:` releases on exception. Verified with a 100-waiter
test cancelling a random subset at random points across 5 seeds and asserting exact capacity restoration
(`test_rc_host_limiter.py`, 20 tests) plus targeted grant-then-cancel races.

**Deadline interaction (the frozen contract, §5.1):** waiting for a host permit **suspends** the source's
`asyncio.timeout` deadline (`Timeout.reschedule(None)`, then `reschedule(now + remaining)` once granted) —
queue time is never charged. The deadline still covers every attempt and every backoff pause exactly as at C2.
Tested exhaustively in `test_rc_deadline_and_cancellation.py` (17 tests): an unsent request can never become
`SOURCE_DEADLINE` from host contention alone; a retry that queues for a permit keeps its remaining budget; a
backoff pause holds no permit.

## 5. Circuit breaker

**Domain: `source_id`** (not host) — proven independent even when two sources share one host
(`test_rc_shared_scope.py::test_breakers_of_two_sources_on_one_host_are_independent`). States `CLOSED` / `OPEN`
/ `HALF_OPEN`; injected monotonic clock (never wall clock, never `sleep`-based tests); every transition
increments an integer `epoch`.

**Observation table (final result only, exhaustive over `SourceStatus`):**

| Final outcome | Observation |
|---|---|
| `SUCCESS`, `NOT_FOUND` | healthy |
| `BLOCKED`, `RATE_LIMITED`, `NETWORK_ERROR` (any refinement incl. `SOURCE_DEADLINE`), `PARSE_ERROR`, `INVALID_RESPONSE` (any refinement) | failure |
| `NETWORK_ERROR`/`CIRCUIT_OPEN` | not an observation (the breaker's own answer) |
| caller cancellation, fatal `BaseException` | not an observation (ticket released, no state change) |

Two attempts of one execution (attempt 1 fails, attempt 2 succeeds) are **one** healthy observation, never two
records. 100 consecutive `NOT_FOUND` leave `consecutive_failures == 0`. Decided from `result.status` /
`result.error_kind` only — never `error_detail`, a trace, or any string (AST-guarded; see §8).

**HALF_OPEN:** exactly `half_open_max_calls` probe admissions after the cooldown; every other concurrent
lookup short-circuits (`test_the_half_open_race_with_100_asyncio_callers_lets_exactly_one_through` and the
engine-level `test_100_lookups_after_the_cooldown_send_exactly_one_probe_and_99_are_short_circuited`, which
observes it through real `MultiSourceEngine.aggregate` calls with an independent fetch-count meter). A healthy
probe closes and resets the failure counter; a failed probe reopens with a **fresh** cooldown from now.

**Stale completion / epoch fencing (§6.2, the key correctness point):** an admission ticket is stamped with the
breaker's epoch at grant time; `record_result` only changes state when the ticket's epoch still equals the
breaker's current epoch. The contract's own example — A/B/C admitted together, B and C fail and trip the
breaker, A returns SUCCESS late — is pinned by `test_a_late_success_from_before_the_breaker_opened_cannot_close_it`,
plus stale-failure, stale-half-open, and in-flight-not-cancelled variants (7 dedicated tests in
`test_rc_breaker_state_machine.py`, plus the stage gate's Phase E and `test_rc_breaker_execution.py`'s
in-flight/queued-under-a-changing-epoch tests).

**Ordering (§7):** breaker admission → host permit → re-validate `is_current` → fetch. A call that queued for a
host permit while the breaker tripped is answered `CIRCUIT_OPEN` (first attempt) or simply not retried (later
attempt — the real prior failure stays final) rather than sending a stale-admission request
(`test_a_lookup_queued_for_the_host_when_the_breaker_opens_sends_nothing`,
`test_a_retry_is_not_sent_when_the_breaker_opened_during_the_backoff_the_real_failure_stays_final`). An open
breaker never joins the host queue (`test_an_open_breaker_does_not_queue_for_a_saturated_host`).

## 6. `SourceErrorKind.CIRCUIT_OPEN`

Added under `NETWORK_ERROR` in `ALLOWED_ERROR_KINDS` / `status_for_error_kind`. Produced **only** by
`resource_control.circuit_open_result` at the execution boundary; an adapter that returns it is rejected as
`RESULT_CONTRACT_MISMATCH` (fail-closed, like a forged `source_id`), and is itself recorded as a breaker
*failure* (`test_an_adapter_returning_circuit_open_is_a_contract_violation`). **Never retryable**:
`SourceErrorKind.CIRCUIT_OPEN not in RETRY_ELIGIBLE_KINDS`, `RetryPolicy(retryable_error_kinds={CIRCUIT_OPEN})`
raises `AggregationConfigError`. `SourceExecutionTrace.attempts` may be empty **iff**
`final_result.error_kind is CIRCUIT_OPEN` (tightened invariant in `aggregation/models.py`, with no other way to
produce an empty-attempts trace).

Aggregation semantics needed no new rule: `CIRCUIT_OPEN` is a `NETWORK_ERROR`, already an operational-failure
status, so existing merge rules produce the right `SUCCESS`/`PARTIAL`/`FAILED` for one-open/one-success,
all-open, open+`NOT_FOUND`, etc. (`test_rc_breaker_execution.py`, aggregation-semantics section).

## 7. Cancellation and fatal exceptions

Cancelling at any point — waiting for the aggregate slot, waiting for a host permit, inside `adapter.fetch`, or
between fetch completion and the breaker update — leaves no leaked permit, no stuck waiter, no phantom breaker
in-flight count, and frees a held half-open probe slot; `CancelledError` still propagates unchanged and is never
a breaker observation. A parametrised sweep cancels one of three contending lookups after every one of 26 loop
iterations, in both `CLOSED` and `HALF_OPEN` (probe) configurations, and asserts the domain is clean afterward
(`test_cancelling_at_every_loop_iteration_leaves_no_permit_no_waiter_no_inflight_and_no_stuck_probe`, 52
parametrised cases). Fatal `BaseException` propagates as the **original** object (never wrapped, never a
result); the resource layer only releases tickets/permits, never reads the fatal's type or message.

**Focused audit (per prompt §33):** `aggregation.execution._FatalSignal` — which pre-C5 stored
`type(original).__name__` in `super().__init__(...)`, a read of raiser-controlled metadata — is now
metadata-free (`__slots__ = ("original",)`, no read at all), matching the C4 batch-layer carrier and closing the
same class of bug (C4-R1-N2) at this second boundary. Pinned behaviourally with a hostile metaclass whose
`__name__` raises (`test_the_fatal_carrier_never_reads_the_raisers_metadata`) and structurally by AST
(`test_the_fatal_carrier_is_metadata_free`).

## 8. No trace / no text dependency (C2-L2 stays LOW/OPEN)

`test_rc_architecture.py` AST-walks every `resource_control/*.py` file and asserts none of them read
`source_execution_traces`, `SourceExecutionTrace`, `SourceAttempt`, `.attempts`, `attempt_count`,
`deadline_during`, `deadline_exceeded`, `error_detail`, `.metadata`, `.elapsed_ms`, or import `BatchLineage`;
that the only attributes ever read off a `SourceResult`-shaped object in `circuit_breaker.py`/`governor.py` are
`status`, `error_kind`, `source_id`; that no string-sniffing method (`.startswith`, `.lower`, `.split`, …) or
`str(...)`/`repr(...)` of a result/exception appears in the limiter/breaker/governor modules; and that no enum
member is compared by `.value`/`.name` (decisions are by identity). **C5 reads no trace fields anywhere** — the
C4-R1 finding that `BatchItemResult` exposes traces therefore still has no C5 consumer, and **C2-L2 remains
LOW / OPEN**, unchanged.

## 9. Shared-governor scope

Proven through real `MultiSourceEngine` + `BatchScheduler` objects (never mocked), with peaks measured
independently from inside the fake adapters (a `Meter`, not the governor's own counters):

- **Two `BatchScheduler`s, two engines, one governor**, host limit 3, M=8 each: observed host peak **3** (not 6,
  not 16); each scheduler still independently reaches its own M=8 item peak.
- **Two governors**, host limit 3 each, running the same scenario concurrently: peak **6** — independent domains
  whose budgets add.
- **Two sources on one host** (`.../a`, `.../b`), host limit 2: combined peak **2**, not 2 each; their breakers
  are independent (one source's `PARSE_ERROR`s opening its breaker never affects the other, which keeps serving
  every item).
- **Two hosts** (limits 2 and 3): peaks of 2 and 3 simultaneously, total 5, neither blocks the other; a
  saturated host never delays a different host.
- Engine construction derives the host from the *configured* base URL only (`test_the_host_key_is_taken_from_configuration_never_from_the_response`);
  malformed default URLs are rejected with a governor, and are simply not consulted without one.

## 10. 200-item offline stage gate

`test_rc_stage_gate_200.py` — 2 `BatchScheduler`s, 3 sources (`source_a`/`source_b` on `h1.example` limit 2,
`source_c` on `h2.example` limit 3), one shared governor, phased so every breaker transition is deterministic:

- **A** (50): healthy mix incl. retry recovery (`TIMEOUT`→`SUCCESS`) — every breaker stays `CLOSED`, 0 failures;
  host peaks exactly 2 and 3, combined peak 5.
- **B** (50): `source_c` outage (`BLOCKED`/`RATE_LIMITED`/`PARSE_ERROR`/`NETWORK_ERROR` cycling) — opens after
  exactly `threshold` real requests; `source_a`/`source_b` keep serving (`PARTIAL`, not `FAILED`).
- **C** (20): cooldown not elapsed — **zero** requests to `source_c`, every result `CIRCUIT_OPEN`/empty-attempts.
- **D** (40): cooldown elapsed — **exactly one** probe fetch across both schedulers; the rest short-circuit;
  probe succeeds → `CLOSED`, `consecutive_failures == 0`.
- **E** (20): a slow `SUCCESS` already in flight when 3 fast `BLOCKED`s trip the breaker — the in-flight call is
  **not** cancelled and finishes normally, but its late completion (a stale, pre-opening epoch) does **not**
  close the just-opened breaker; a subsequent cooldown + probe closes it for real.
- **F** (20): a whole batch run cancelled mid-flight — 0 items land in either scheduler's result (no partial
  result), and the governor is fully clean afterward.

Total 180 accounted items + 20 cancelled = 200. Final assertions: every host/breaker in-flight/waiting/probe
counter is 0; host peaks are exactly `{h1: 2, h2: 3}`; no orphan asyncio task remains.

## 11. Large-N structural stress

`test_rc_large_n_stress.py`, N=10,000, no wall-clock assertion:

- One scheduler, M=16, host limit 3: all 10,000 succeed, in order, exactly once; observed host peak **3**;
  observed scheduler peak **16**; live-task sample stayed `O(M)`; governor snapshot after the run shows exactly
  one host and one breaker, both idle (`in_flight == waiting == 0`); `gc`-based object census (relative to a
  pre-run baseline, so unrelated tests can't skew it) shows **zero** live `SourceAdmission`/`HostPermit` objects
  and exactly one `HostLimiter` and one `CircuitBreaker` — no per-item resource-control object survives.
- Two schedulers × 5,000 sharing one governor: combined host peak still **3**.
- A 10,000-item flapping run (breaker opens/recovers repeatedly via a self-advancing fake clock): `times_opened`
  confirms real cycling; state afterward is still the same fixed 9-field scalar snapshot regardless of N — no
  failure-history list, no per-item retention.

## 12. Test-infrastructure finding fixed during C5 (not a resource-control defect)

While preparing the freeze, the full suite (2361 tests) intermittently failed 4 tests in
`test_rc_breaker_execution.py` (`test_an_open_breaker_does_not_queue_for_a_saturated_host` and three
`open_and_ok_engine`/`force_open`-based tests) — but only when run as part of the **whole** suite, never in
isolation. Root cause: `tests/contract/test_core_independent_of_amane.py`'s F4 dynamic-purge tests intentionally
delete every `fc2_metadata_core.*` entry from `sys.modules` (to prove the package survives a hostile
`amane`-blocking meta path finder) and leave them purged afterward. Two test-helper functions in
`test_rc_breaker_execution.py` did a **local, function-body** `from fc2_metadata_core.resource_control import
host_key_for_base_url` — executed at test-run time, i.e. *after* the contract tests had already purged
`sys.modules` — which triggered a fresh reimport producing a **second, distinct `HostKey` class**. The
already-constructed `governor` object (built from names imported at module top, i.e. the *original* classes)
then failed `isinstance(host, HostKey)` against a same-shaped-but-different-class key. This was a **test-file
bug** (a local import that should have been a module-level one, matching every other import in the codebase),
not a defect in `resource_control` or `aggregation`: confirmed by an isolated repro script and by instrumenting
the real test to print class identities across the purge boundary. Fixed by hoisting the import to module level
(the same style the rest of the file and the whole codebase already uses). Audited every other local
`fc2_metadata_core` import newly added in this phase (`test_rc_architecture.py`, `test_rc_breaker_execution.py`'s
`NormalizedMetadata` case, `test_rc_deadline_and_cancellation.py`) and confirmed none of the remaining ones cross
a class-identity boundary with a pre-existing object (each is self-contained: constructed and consumed by names
from the *same* fresh import). Full suite reran green three times after the fix, including the exact
`tests/contract` → `tests/unit/resource_control` ordering that had exposed it.

## 13. Backlog carried forward

- **C2-L2** — LOW / OPEN, unchanged (§8: C5 reads no trace fields).
- **C4-N1** — `BatchLineage` is in-memory-only provenance; a durable batch id is still needed before
  persistence/resume. `resource_control` does **not** reuse `BatchLineage` for tickets/epochs (verified by
  `test_batch_and_the_scheduler_do_not_know_about_resource_control`).
- **C4-R1-N1 / N2 / N3** — carried unchanged (untrusted non-`MultiSourceEngine` producers; hostile
  `BaseException` metaclass `__subclasscheck__` at Python's `raise` boundary; non-plain-metaclass diagnostic
  loss). C5 does not touch these.
- **New, documented, not fixed (C5):** breaker/host state is per-governor, in-memory only, lost on restart; no
  `Retry-After`-aware cooldown; host limits are static (no adaptive limiting); the governor is single-event-loop
  and not thread-safe; a stale (superseded-epoch) observation is discarded, never down-weighted.
- Not started: persistence/DB, NFO writer, image downloader, filesystem, Amane adapter, GUI, final 500-item
  acceptance, `Retry-After` parsing, CAPTCHA/anti-bot bypass, proxy rotation, live large-batch scrape.

## 14. Files

```
docs/specifications/PHASE3_RESOURCE_CONTROL_CONTRACT.md   (new)
docs/specifications/PHASE3_RESILIENCE_CONTRACT.md          (amended: CIRCUIT_OPEN, deadline/queue note)
docs/specifications/PHASE3_BATCH_CONTRACT.md               (amended: per-host limiter note points at C5)

src/fc2_metadata_core/resource_control/__init__.py
src/fc2_metadata_core/resource_control/errors.py
src/fc2_metadata_core/resource_control/host_key.py
src/fc2_metadata_core/resource_control/config.py
src/fc2_metadata_core/resource_control/host_limiter.py
src/fc2_metadata_core/resource_control/circuit_breaker.py
src/fc2_metadata_core/resource_control/governor.py

src/fc2_metadata_core/__init__.py                          (exports resource_control)
src/fc2_metadata_core/models/source_result.py              (SourceErrorKind.CIRCUIT_OPEN)
src/fc2_metadata_core/aggregation/models.py                (trace: zero attempts iff CIRCUIT_OPEN)
src/fc2_metadata_core/aggregation/execution.py              (governor= integration; metadata-free _FatalSignal)
src/fc2_metadata_core/aggregation/engine.py                 (governor= construction, host derivation)
src/fc2_metadata_core/aggregation/retry.py                  (docstring: CIRCUIT_OPEN never retried)

tests/support/resource_fakes.py                             (new: FakeClock, Meter, Spec/make_engine/make_target, run())
tests/unit/resource_control/test_rc_host_key.py
tests/unit/resource_control/test_rc_config.py
tests/unit/resource_control/test_rc_host_limiter.py
tests/unit/resource_control/test_rc_breaker_state_machine.py
tests/unit/resource_control/test_rc_governor_tokens.py
tests/unit/resource_control/test_rc_shared_scope.py
tests/unit/resource_control/test_rc_breaker_execution.py
tests/unit/resource_control/test_rc_deadline_and_cancellation.py
tests/unit/resource_control/test_rc_architecture.py
tests/unit/resource_control/test_rc_stage_gate_200.py
tests/unit/resource_control/test_rc_large_n_stress.py

tests/unit/aggregation/test_agg_guards.py                   (amended: circuit-breaker-vocabulary guard scoped to C5)
tests/unit/aggregation/test_agg_retry_policy.py             (amended: CIRCUIT_OPEN in the not-retryable set)
tests/unit/core/test_source_error_taxonomy.py               (amended: CIRCUIT_OPEN in the frozen relation)
```

---

READY FOR PHASE 3 C5 INDEPENDENT REVIEW
