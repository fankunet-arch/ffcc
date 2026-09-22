# FC2 Metadata Core — Phase 3 / C5 Shared Host Resource Control & Circuit Breaker Contract

Status: **frozen at Phase 3 C5** (candidate; independent review pending).
Builds on `PHASE3_RESILIENCE_CONTRACT.md` (C1–C3) and `PHASE3_BATCH_CONTRACT.md` (C4).
Package: `fc2_metadata_core.resource_control` (`errors.py`, `host_key.py`, `config.py`, `host_limiter.py`,
`circuit_breaker.py`, `governor.py`). Integration: `aggregation/execution.py`, `aggregation/engine.py`,
`aggregation/models.py` (trace), `models/source_result.py` (`SourceErrorKind.CIRCUIT_OPEN`).

**Out of scope, not implemented:** persistence / DB, NFO writer, image downloader, filesystem
rename/move, Amane adapter, GUI, the final 500-item acceptance run, `Retry-After` parsing,
CAPTCHA / anti-bot bypass, proxy rotation, adaptive (dynamic) limits, live large-batch scraping.

Each rule names the test file that enforces it (all offline and deterministic,
`tests/unit/resource_control/` unless stated; no wall-clock assertion anywhere — breaker time comes from an
injected monotonic clock, waiting from events/gates, never `sleep`-based ordering).

## 1. Architecture and dependency direction

```text
BatchScheduler A ─┐
BatchScheduler B ─┼─> same MultiSourceEngine(s) constructed with the same governor
BatchScheduler C ─┘
                         │  execute_sources_traced(..., governor=g)
                         v
                 SourceResourceGovernor  (one explicit resource domain)
                   /                  \
        per-host limiter          per-source circuit breaker
        (HostKey -> permits)      (source_id -> state machine)
                   \                  /
                    adapter.fetch  /  structured SourceResult
```

* `resource_control` depends on the `SourceResult` contract (`SourceResult`, `SourceStatus`,
  `SourceErrorKind`), `errors` and the standard library. It **never** imports `batch`, `aggregation`,
  `sources.adapters`, `httpx`, `amane`, or any file / network / process module.
* `aggregation.execution` / `aggregation.engine` depend on the governor through its narrow public surface
  (`admit`, `acquire_host_permit`, `is_current`, `record_result`, `release`). `batch` is **unchanged**: it
  reaches the governor only through the engine it was given (C4's `AggregationEngine` protocol).
* **No module-global mutable singleton.** The governor is an explicit object: engines/schedulers that were
  handed the *same* instance share one resource domain; a *different* instance is an independent domain
  whose budgets simply add up. Enforced by `test_rc_architecture.py` (no module-level mutable state) and the
  scope tests below.
* **Opt-in.** `MultiSourceEngine(config, registry, client)` without `governor=` behaves exactly as at C4
  (no host limit, no breaker) — every pre-C5 test is unchanged.

## 2. Resource domain and the three budgets (frozen semantics)

| Knob | Scope | Bounds |
|---|---|---|
| `AggregationConfig.max_concurrency = S` | one `aggregate()` call (C1) | concurrent source executions inside one item |
| `BatchConfig.max_in_flight_items = M` | one `BatchScheduler` (C4) | concurrent `aggregate()` calls of that scheduler |
| `HostLimitPolicy.default_max_in_flight_per_host` (+ overrides) | **one governor** (C5) | concurrent network **attempts** (`adapter.fetch`) to one host, across every `aggregate()` call, every engine, every scheduler, every source of that governor |

C4's M and C1's S are unchanged and still apply; C5's host budget is an additional, tighter-or-equal cap
on what actually reaches the wire. `test_rc_shared_scope.py`: two schedulers (M=8 each) + two engines +
one governor with host limit 3 → observed host peak **3** (not 6, not 16); two governors → peak up to
6 (independent domains); two sources on `https://same.example/a` and `/b` with limit 2 → combined peak
**2**; hosts `a.example` (limit 2) and `b.example` (limit 3) run 2 + 3 = 5 at once, each up to its own
limit.

**What this guarantees, precisely.** Host permit capacities are independent **per `HostKey`**: saturation
of one host never consumes or reduces another host's permit capacity, and different hosts may execute
concurrently up to their own respective limits whenever an aggregate source slot is available to use them.
This is a **capacity-isolation** guarantee. It is **not** a cross-host **latency**-isolation guarantee, and
C5 does not provide one: `AggregationConfig.max_concurrency` (S, C1) remains an outer, unchanged
per-`aggregate()` scheduling budget, and a source that is queued waiting for a *host* permit continues to
occupy its *aggregate-local* source slot for as long as it waits (§5, §5.1). Consequently, when `S` is
smaller than the number of runnable sources of one lookup, contention on one host can indirectly delay the
admission of a later source targeting a *different* host, even while that other host's own permit capacity
sits completely idle. This is not a host-permit leak and not cross-host budget coupling — it is ordinary
aggregate-level head-of-line scheduling under the unchanged C1 semaphore, orthogonal to (and outside) the
host limiter's own accounting, which stays exactly as isolated as described above.

## 3. Host identity (`host_key.py`) — `test_rc_host_key.py`

`HostKey(host: str, port: int)` — frozen, hashable, ordered by `(host, port)`. **Derived only from the
configured, validated `base_url`** of the adapter the engine built (`SourceConfig.base_url` if given, else the
adapter's `default_base_url`) — never from a response URL, redirect target, error text, trace, title or
request body. Rules (`host_key_for_base_url`):

* scheme must be `http` or `https`; the host is lower-cased; **one** trailing dot is stripped
  (`example.com.` ≡ `example.com`);
* **effective port**: the explicit port, else `80` (http) / `443` (https) — `https://x`, `https://x:443`
  and `https://X.` are the same key; `https://x:8443` and `http://x` are different keys;
* the **path is ignored**: `https://x/a` and `https://x/b` share one key (so two sources on one host share
  one host budget);
* IP literals are canonicalised by `ipaddress` (`::1`, `0:0:0:0:0:0:0:1` → `::1`); the printable
  form `str(HostKey)` is `host:port`, IPv6 in brackets (`[::1]:443`); IPv6 zone ids (`%eth0`) are rejected;
* userinfo, query and fragment are impossible (`aggregation.validate_base_url` already rejects them; the key
  builder rejects them again — it is also usable on its own) and a non-`str` / empty / host-less / bad-port
  value raises `ResourceControlConfigError` — **before any network**.

`HostKey.parse("host:port")` is the inverse used for per-host overrides (port mandatory, IPv6 bracketed).

**Where the key comes from at run time.** When a governor is given, `MultiSourceEngine.__init__` derives each
enabled source's key **once, at construction**, from `adapter.base_url` (the configured `SourceConfig.base_url`, else
the adapter's `default_base_url`) through `aggregation.validate_base_url` → `host_key_for_base_url`, and stores it on
the `SourceTarget` (`host`). A base URL that cannot be keyed (e.g. a malformed adapter default) raises
`AggregationConfigError("… cannot derive a host identity …")` **before any request**; without a governor nothing is
derived and no default URL is inspected (unchanged C4 behaviour). `execute_sources_traced(..., governor=g)` requires
every target to carry a host (`AggregationConfigError` otherwise). A response, redirect target or error text is never
consulted (`test_rc_shared_scope.py::test_the_host_key_is_taken_from_configuration_never_from_the_response`).

## 4. `HostLimitPolicy` and `CircuitBreakerPolicy` (`config.py`) — `test_rc_config.py`

Frozen, hashable, validated at construction (`ResourceControlConfigError`), never mutated; `bool` is never
accepted as a number/int; every number is finite and bounded.

`HostLimitPolicy(default_max_in_flight_per_host=4, overrides=())`

* default **4**, range **1..64** (`HOST_LIMIT_MAX`); `overrides` is a tuple of `(HostKey, int)` pairs (each
  int in 1..64), **at most 256**, **no duplicate host key**; `HostLimitPolicy.create(default, mapping)` is the
  friendly constructor (keys are `"host:port"` strings, canonicalised via `HostKey.parse`; a malformed key or
  two keys that canonicalise to the same host — `"A.example:443"` and `"a.example:443"` — is rejected).
  Everything is copied into immutable tuples, so nothing the caller still holds can change the policy.
* `limit_for(HostKey)` → the override or the default. **Static**: no adaptive limit in C5.

`CircuitBreakerPolicy(failure_threshold=3, open_duration_seconds=30.0, half_open_max_calls=1)`

* `failure_threshold`: int (not bool) in **1..100**;
* `open_duration_seconds`: finite number, **> 0** and **<= 3600**;
* `half_open_max_calls`: int (not bool) in **1..16**.

## 5. Host permit semantics (`host_limiter.py`) — `test_rc_host_limiter.py`

One `HostLimiter` per host key (created lazily by the governor — O(hosts) state, §12).

* A permit is acquired **per network attempt**: `permit = await governor.acquire_host_permit(admission)` →
  `adapter.fetch` → `permit.release()`. **A retry's backoff pause holds no permit** (a one-second backoff
  never blocks another item on that host); attempt 2 acquires again.
* At any instant, for one governor and one host key, **live permits ≤ the host's limit**; different hosts'
  permit *capacities* never block each other (§2's capacity-isolation guarantee) — though admission into an
  aggregate source slot in the first place is still governed by the unchanged, outer C1 `max_concurrency`
  (§2).
* **FIFO** and fair: a newcomer never overtakes a waiter. Release hands the permit directly to the oldest
  live waiter (no window in which a third party can steal it).
* `HostPermit.release()` is idempotent; `with permit:` releases on exit (also on exception/cancellation).
* **Cancellation while waiting** raises `CancelledError` at once and removes the waiter. A waiter that was
  *granted* the permit in the same loop iteration in which its task was cancelled returns the permit to
  the next waiter/pool (no permit leak, no phantom holder). 100 waiters, a subset cancelled at assorted
  points → the limiter's capacity is fully restored (`in_flight == 0`, `waiting == 0`, and it then admits
  exactly `limit` new holders).

### 5.1 Queue time vs. the source deadline (frozen; the C5 key contract)

C2 already excludes the **aggregate-local** semaphore wait from a source's `deadline_seconds`. C5 extends
that rule: **waiting for a host permit does not consume the source's execution deadline.**
Implementation: the source deadline is one `asyncio.timeout`; while an attempt is *queued for a host permit*
the deadline is suspended (`Timeout.reschedule(None)`) and, once the permit is granted, re-armed with
exactly the time that remained (`reschedule(loop.time() + remaining)`). Consequences (all tested in
`test_rc_deadline_and_cancellation.py`):

* host contention can never turn a source that has **not yet sent a request** into `SOURCE_DEADLINE`;
* the deadline still covers: every network attempt, every backoff pause, and nothing else — a 0.30 s deadline
  with attempt 1 (0.15 s) + backoff (0.10 s) + a hanging attempt 2 still ends at ≈ 0.30 s of *executing* time
  even if attempt 2 first queued for a permit;
* liveness is bounded by the *holders'* deadlines (each holder's fetch is itself under its source deadline).

## 6. Circuit-breaker domain and state machine (`circuit_breaker.py`) — `test_rc_breaker_state_machine.py`

**Domain: `source_id`** (default and only mode). One host may serve two sources (`same.example/a`,
`/b`); a parse failure of source A's layout must not close source B. The host limiter is per host, the
breaker per source — the two domains are orthogonal. Breaker state is created lazily per `source_id`
(O(configured sources)); two engines of one governor that configure the same `source_id` share its breaker.

States `CLOSED`, `OPEN`, `HALF_OPEN`. Time is an **injected monotonic clock** (`clock=time.monotonic` by
default; tests inject a fake). Wall clock (`datetime`, `time.time`) and `sleep` are never used.

Internal per-source state is mutable and private; the public view is the immutable `BreakerSnapshot`.
Every state transition increments `epoch` (an int, monotone, starts at 0). All transitions are synchronous
Python with **no `await` inside** — on one event loop they are atomic; the governor is documented as
**single-event-loop, not thread-safe**.

| From | Event | To | Effects |
|---|---|---|---|
| `CLOSED` | admission | `CLOSED` | grant a *normal* ticket stamped with the current epoch |
| `CLOSED` | current-epoch **healthy** observation | `CLOSED` | `consecutive_failures = 0` |
| `CLOSED` | current-epoch **failure**, count `< threshold` | `CLOSED` | `consecutive_failures += 1` |
| `CLOSED` | current-epoch **failure**, count reaches `failure_threshold` | `OPEN` | `epoch += 1`, `opened_at = now` |
| `OPEN` | admission, `now - opened_at < open_duration_seconds` | `OPEN` | **reject** (short-circuit) |
| `OPEN` | admission, `now - opened_at >= open_duration_seconds` | `HALF_OPEN` | `epoch += 1`, no probe yet, then the `HALF_OPEN` admission rule applies to this same call |
| `HALF_OPEN` | admission, `probes_in_flight < half_open_max_calls` | `HALF_OPEN` | grant a *probe* ticket (`probes_in_flight += 1`) |
| `HALF_OPEN` | admission, `probes_in_flight == half_open_max_calls` | `HALF_OPEN` | **reject** — no thundering herd |
| `HALF_OPEN` | current-epoch probe **healthy** | `CLOSED` | `epoch += 1`, `consecutive_failures = 0` |
| `HALF_OPEN` | current-epoch probe **failure** | `OPEN` | `epoch += 1`, `opened_at = now` (fresh cooldown) |
| any | a **stale** observation (ticket epoch ≠ current epoch) | unchanged | only the ticket's in-flight accounting is released |
| any | ticket released without observation (cancel / fatal / not attempted) | unchanged | in-flight accounting released; a current-epoch probe frees its probe slot |

The `OPEN → HALF_OPEN` move is **lazy** (made by the first admission after the cooldown; a snapshot never
mutates): a snapshot of an expired-but-unprobed breaker reports `OPEN` with `remaining_cooldown_seconds == 0.0`.

### 6.1 What counts as an observation (final results only) — `test_rc_breaker_state_machine.py`

The breaker is fed **one observation per source execution: its FINAL `SourceResult`** — after retries, after
the deadline, after fail-closed validation. Decided from `result.status` (and, for the one non-observation
kind below, `result.error_kind`); never from `error_detail`, never from a trace.

| Final outcome | Observation |
|---|---|
| `SUCCESS` | **healthy** |
| `NOT_FOUND` | **healthy** — the source answered; the catalogue just lacks the id (100 consecutive `NOT_FOUND` keep the breaker `CLOSED` with 0 failures) |
| `BLOCKED`, `RATE_LIMITED`, `NETWORK_ERROR` (any refinement, incl. `SOURCE_DEADLINE`), `PARSE_ERROR`, `INVALID_RESPONSE` (any refinement) | **failure** |
| `NETWORK_ERROR` with `error_kind == CIRCUIT_OPEN` | **not an observation** (it is the breaker's own answer) |
| caller cancellation, fatal `BaseException` | **not an observation** — the ticket is released |

`attempt 1 NETWORK_ERROR → attempt 2 SUCCESS` is **one healthy observation** (two attempts never make two
failures). The exhaustive status→observation table is checked against `SourceStatus` at import (a new status
without a decision fails loudly).

### 6.2 Epochs, tickets and stale completion (frozen)

`SourceResourceGovernor.admit(source_id, host)` returns an opaque `SourceAdmission` (or `None` = circuit
open). The ticket records `source_id`, `host`, the breaker **epoch** at admission, whether it is a **probe**,
and is bound to the issuing governor. Callers cannot construct one (the constructor demands a private
key); a ticket of another governor, a forged one, a settled one used for `record_result`, or a non-`SourceResult`
raise `ResourceControlError`.

* An observation is applied **only if the ticket's epoch equals the breaker's current epoch**. Example:
  call A, B, C are admitted in `CLOSED` epoch 4; B and C fail and the threshold trips → `OPEN` epoch 5; A
  returns `SUCCESS` late — its epoch (4) is stale, so it is discarded and **cannot reset/close** the breaker
  (and a stale *failure* cannot re-open, extend or double-count anything).
* In-flight calls are **never cancelled** when the breaker opens; they finish and return normally, only their
  effect on breaker *state* is fenced off. Only **new** admissions short-circuit.
* `record_result` / `release` are **idempotent-safe at the accounting level**: `release` of a settled ticket is
  a no-op (so `finally: release` is always correct); `record_result` of a settled ticket raises.

## 7. Ordering: breaker → host permit → revalidate (frozen)

Per source execution (`execution._execute_one`):

1. wait for the aggregate-local slot (C1, unchanged);
2. `admission = governor.admit(source_id, host)` — synchronous. `None` → the source's result is
   `circuit_open_result` (§8) with **no** host permit taken and **no** `adapter.fetch`;
3. for **every** attempt: `permit = await governor.acquire_host_permit(admission)` (deadline suspended, §5.1);
   **then** `governor.is_current(admission)`:
   * current → `adapter.fetch` → release the permit;
   * **stale** (the breaker changed epoch while this call queued, or during the retry backoff) → the request
     is **not sent**: attempt 1 → the result is `CIRCUIT_OPEN` (no attempt made); attempt *n ≥ 2* → **no
     further retry** — the previous attempt's real failure stays the final result;
4. one `governor.record_result(admission, final_result)` (or `release` on cancel/fatal/not-attempted).

An `OPEN` breaker therefore never occupies a host slot, and a queued call never sends a request under an
admission that a newer breaker state has invalidated.

## 8. `CIRCUIT_OPEN` vocabulary and trace — `test_source_error_taxonomy.py`, `test_rc_breaker_execution.py`

`SourceStatus` is **unchanged** (seven statuses). `SourceErrorKind.CIRCUIT_OPEN = "circuit_open"` is added
under **`NETWORK_ERROR`** (`ALLOWED_ERROR_KINDS`, `status_for_error_kind`; docs table in
`PHASE3_RESILIENCE_CONTRACT.md` §1 amended). It is produced **only** by the execution boundary
(`circuit_open_result`: `error_detail = "<source_id>: circuit breaker open; lookup not attempted"`, `elapsed_ms = 0`).
An adapter that returns it is treated as a contract violation (`INVALID_RESPONSE` /
`RESULT_CONTRACT_MISMATCH`, exactly like a forged `source_id`).

* **Never retried**: `CIRCUIT_OPEN` is not in `RETRY_ELIGIBLE_KINDS` (AST/contract guard;
  `RetryPolicy(retryable_error_kinds={CIRCUIT_OPEN})` is rejected) and a short-circuit happens before the
  attempt loop anyway.
* **Trace:** a short-circuited source has a `SourceExecutionTrace` with `attempts == ()`,
  `attempt_count == 0`, `deadline_exceeded == False`. `SourceExecutionTrace` invariants (C2 §5) are amended:
  `attempts` may be empty **iff** `final_result.error_kind is CIRCUIT_OPEN` (and then nothing else is allowed);
  every other trace still needs `≥ 1` attempt.
* **Aggregation:** `NETWORK_ERROR` is an operational failure, so no merge rule changes: one source
  `CIRCUIT_OPEN` + one `SUCCESS` → aggregate `PARTIAL`; all sources open → `FAILED`; `CIRCUIT_OPEN` +
  `NOT_FOUND` (no data) → `FAILED`; `SUCCESS` + `NOT_FOUND` → `SUCCESS` (unchanged).
* **Batch:** a batch item that ends `FAILED`/`PARTIAL` because sources were open is an ordinary failed item;
  C4 failed-subset retry applies unchanged (a re-run after the cooldown can succeed).

## 9. Cancellation and fatal exceptions — `test_rc_deadline_and_cancellation.py`

Cancelled (by the caller, a sibling teardown, or the source deadline) at **any** point — waiting for the
aggregate slot, waiting for a host permit, inside `adapter.fetch`, or right after the fetch returned:

* no host permit stays held; no waiter stays queued; no breaker in-flight count stays incremented; a
  half-open probe slot is **freed** (another lookup can probe); `CancelledError` still propagates unchanged
  (never turned into a result, never counted as a failure);
* a source **deadline** is *not* a cancellation of the caller: it is a real final result
  `NETWORK_ERROR/SOURCE_DEADLINE` and **is** a breaker failure.

Fatal `BaseException` (`KeyboardInterrupt`, `SystemExit`, custom): the C2/C3 rules are unchanged — siblings
cancelled, the **original** object re-raised, never wrapped, never a result — and the resource layer only
*releases* its tickets/permits (in `finally`); it never reads a fatal's type, name, message or args.
**Focused audit at this boundary (C5):** `execution._FatalSignal` previously stored
`type(original).__name__` (a read of raiser-controlled metadata that a hostile metaclass could turn into
an error replacing the fatal — the C4-R1 class of bug). It is now metadata-free (`__slots__ = ("original",)`,
no read); pinned in `test_rc_architecture.py` and `test_rc_deadline_and_cancellation.py`.

## 10. No trace, no text dependency (C2-L2 stays LOW/OPEN) — `test_rc_architecture.py`

The resource-control package's AST contains **no** read of: `source_execution_traces`, `SourceExecutionTrace`,
`SourceAttempt`, `.attempts`, `attempt_count`, `deadline_during`, `deadline_exceeded`, `error_detail`, `.metadata`,
`.elapsed_ms`; no `str()`/`repr()`/`format`/`in`-string test of an exception or a result; no string literal
matching against error text. Decisions use only `SourceStatus`, `SourceErrorKind`, `source_id`, the configured host
key, epochs and the injected monotonic clock. The C4-R1 observation (`BatchItemResult` exposes traces) therefore
does not extend to C5: **C2-L2 remains LOW / OPEN with no trace dependency in C5.**
`BatchLineage` is *not* reused: tickets, epochs and permits have their own identities.

## 11. Diagnostics — `test_rc_governor_tokens.py`

`governor.snapshot()` → immutable `GovernorSnapshot(hosts: tuple[HostSnapshot, ...], breakers:
tuple[BreakerSnapshot, ...])`, sorted deterministically. `HostSnapshot(host, limit, in_flight, waiting,
peak_in_flight)`; `BreakerSnapshot(source_id, state, consecutive_failures, epoch, in_flight,
half_open_probes_in_flight, opened_at, remaining_cooldown_seconds, times_opened)`. Only scalars, enums and
`source_id`/host strings — no URL with a path, no response text, no exception object, no internal mutable
container (`test_rc_governor_tokens.py` asserts the field sets and that mutating a snapshot is impossible).

## 12. Memory bound — `test_rc_large_n_stress.py`

State is `O(distinct hosts + distinct source_ids)`; no per-item, per-number or per-attempt object is
retained after the item completes; no failure history list exists (only counters). Tickets are
short-lived (their in-flight accounting is released on settle) and are not stored in the governor.

## 13. Test matrix

| Area | File |
|---|---|
| host key canonical form | `test_rc_host_key.py` |
| policies (types, ranges, `bool`, overrides, immutability) | `test_rc_config.py` |
| host limiter (FIFO, peak, cancel, 100-waiter restore, grant-then-cancel) | `test_rc_host_limiter.py` |
| breaker state machine, clocks, epochs, half-open race (100 callers, 1 probe), threshold race, stale completion | `test_rc_breaker_state_machine.py` |
| tickets, foreign/forged/double settle, status table, snapshots | `test_rc_governor_tokens.py` |
| shared governor / different governor / same-host sources / different hosts | `test_rc_shared_scope.py` |
| breaker through the real engine: BLOCKED/RATE_LIMITED/PARSE, NOT_FOUND, retry, open ⇒ zero requests, aggregation semantics, `CIRCUIT_OPEN` trace | `test_rc_breaker_execution.py` |
| deadline vs. queue, cancel/fatal cleanup at every stage | `test_rc_deadline_and_cancellation.py` |
| AST/architecture guards | `test_rc_architecture.py` |
| 200-item offline stage gate (2 schedulers, 3 sources, 2 hosts, mixed failures, breaker cycle) | `test_rc_stage_gate_200.py` |
| N = 10 000, M = 16, host limit 3, O(hosts + sources) state | `test_rc_large_n_stress.py` |
| taxonomy / retry matrix updated for `CIRCUIT_OPEN` | `tests/unit/core/test_source_error_taxonomy.py`, `tests/unit/aggregation/test_agg_retry_policy.py` |

## 14. Backlog carried forward (nothing here is fixed by C5)

* **C2-L2** (LOW/OPEN): `BatchItemResult` exposes `AggregationResult.source_execution_traces`; C5 does not read
  traces, so the trigger tightening is unchanged.
* **C4-N1** durable batch id (before persistence/resume); **C4-R1-N1** untrusted non-`MultiSourceEngine` producers of
  forged `AggregationResult` internals; **C4-R1-N2** hostile `BaseException` metaclass `__subclasscheck__` at Python's
  `raise` boundary; **C4-R1-N3** non-plain metaclass → `UnknownType` diagnostic loss / subclass strictness; **C3-N1…N4**,
  **P2-R-05/06/07/10**, **F3/F5**.
* New C5 limits (documented, not fixed): breaker state is per governor and in memory (no persistence across runs);
  `open_duration_seconds` is static (no `Retry-After`); host limits are static; the governor is single-event-loop and not
  thread-safe; a stale observation is *discarded*, not down-weighted (a late real failure from a superseded epoch is
  intentionally not counted).
