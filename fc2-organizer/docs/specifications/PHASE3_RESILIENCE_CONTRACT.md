# FC2 Metadata Core — Phase 3 / C2 Resilience & Retry Contract

Status: **frozen at Phase 3 C2** (candidate; independent review pending).
Builds on `PHASE3_AGGREGATION_CONTRACT.md` (C1). Closes Phase 2 review finding **P2-R-12**
and the C1 review findings **LOW-1 … LOW-4**.

**Out of scope, not implemented:** batch engine / cross-item scheduling, failed-subset retry,
circuit breaker, `Retry-After`-aware scheduling, jitter, NFO, images, filesystem, Amane adapter.

Each rule names the test file that enforces it (all offline, deterministic;
`tests/unit/aggregation/` unless stated).

## 1. Failure taxonomy (`models/source_result.py`) — `tests/unit/core/test_source_error_taxonomy.py`

`SourceStatus` is **unchanged** (coarse, aggregate-visible): `SUCCESS`, `NOT_FOUND`, `BLOCKED`,
`RATE_LIMITED`, `NETWORK_ERROR`, `PARSE_ERROR`, `INVALID_RESPONSE`. `SourceErrorKind` is widened:

| `SourceStatus` | Allowed `SourceErrorKind` (`ALLOWED_ERROR_KINDS`) |
|---|---|
| `NOT_FOUND` | `NOT_FOUND` |
| `BLOCKED` | `BLOCKED` |
| `RATE_LIMITED` | `RATE_LIMITED` |
| `NETWORK_ERROR` | `NETWORK_ERROR` (generic), `TIMEOUT`, `CONNECTION_ERROR`, `DECODE_ERROR`, `REDIRECT_ERROR`, `SOURCE_DEADLINE` |
| `PARSE_ERROR` | `PARSE_ERROR` |
| `INVALID_RESPONSE` | `INVALID_RESPONSE` (generic), `HTTP_SERVER_ERROR`, `RESPONSE_TOO_LARGE`, `ADAPTER_EXCEPTION`, `RESULT_CONTRACT_MISMATCH` |

Every `SourceErrorKind` belongs to exactly one status (`status_for_error_kind`). Rules
(`SourceResult.__post_init__`): a non-success result needs an `error_kind` **allowed for its
status** and a non-empty `error_detail` (Phase 1 invariant, unchanged); `SUCCESS` forbids both.
**Backward compatible:** the six generic kinds are kept, so every pre-C2 `SourceResult` (kind == the
status's own name) and every adapter that does not refine its failures still validates.

Meaning of the refined kinds and who produces them:

| Kind | Meaning | Produced by |
|---|---|---|
| `TIMEOUT` | transport timeout (connect/read/pool) | `classify_transport_failure` (`HttpTimeoutError`) |
| `CONNECTION_ERROR` | DNS / TCP / TLS / protocol / read error | `HttpConnectionError` |
| `DECODE_ERROR` | body decode / decompress failure (`gzip`/`deflate` error) | `HttpDecodingError` (new; raised by `HttpxTransport` on `httpx.DecodingError`) |
| `REDIRECT_ERROR` | redirect chain limit exceeded | `HttpRedirectLimitError` |
| `SOURCE_DEADLINE` | the per-source wall-clock deadline expired | aggregation execution boundary |
| `HTTP_SERVER_ERROR` | HTTP **500–599** | `classify_page_response` (adapters) |
| `RESPONSE_TOO_LARGE` | body over the transport's size cap | `HttpResponseTooLargeError` |
| `ADAPTER_EXCEPTION` | the adapter itself raised (incl. a self-raised `CancelledError`) | execution boundary |
| `RESULT_CONTRACT_MISMATCH` | wrong `source_id`, non-`SourceResult`, or `SUCCESS` for another number | fail-closed validation |

*Decision, stated because the task text listed `REDIRECT_ERROR` in both families:* it is a
`NETWORK_ERROR`-status kind. That is what redirect-limit failures already were before C2 (no
existing result changes status), and nothing was received to judge.

### 1.1 Production classification (P2-R-12) — `tests/unit/sources/test_failure_classification_c2.py`, `test_agg_retry_http.py`

| Event | `SourceStatus` / `SourceErrorKind` | Retried by default |
|---|---|---|
| HTTP 500–599 | `INVALID_RESPONSE` / `HTTP_SERVER_ERROR` | **yes** |
| transport timeout | `NETWORK_ERROR` / `TIMEOUT` | **yes** |
| DNS / connect / TLS / protocol error | `NETWORK_ERROR` / `CONNECTION_ERROR` | **yes** |
| body decode / decompress error | `NETWORK_ERROR` / `DECODE_ERROR` | **yes** |
| generic transport failure (older adapters, legacy `transport_error_result`) | `NETWORK_ERROR` / `NETWORK_ERROR` | **yes** |
| HTTP 403, or a Cloudflare challenge (`cf-mitigated`, "Just a moment…" page, login/verification redirect) | `BLOCKED` / `BLOCKED` | no |
| HTTP 404 / "not in this source's catalogue" | `NOT_FOUND` / `NOT_FOUND` | no |
| HTTP 429 | `RATE_LIMITED` / `RATE_LIMITED` | no |
| other non-200 (e.g. 301, 418) | `INVALID_RESPONSE` / `INVALID_RESPONSE` | no |
| 200 page that does not parse / layout drift | `PARSE_ERROR` or `INVALID_RESPONSE` (generic) | no |
| body too large | `INVALID_RESPONSE` / `RESPONSE_TOO_LARGE` | no |
| redirect loop | `NETWORK_ERROR` / `REDIRECT_ERROR` | no |

`classify_transport_failure` / `transport_failure_result` (sources/base.py) are the refined
helpers the three adopted adapters now use. The pre-C2 `classify_transport_error` /
`transport_error_result` are **unchanged** (coarse), kept for older adapters and their tests.
The production reachability of every transport row is tested with a real `HttpxTransport` over
`httpx.MockTransport` (httpx exception → transport exception → adapter `SourceResult`).

## 2. `RetryPolicy` (`retry.py`) — `test_agg_retry_policy.py`

Immutable, hashable. Defaults: `max_attempts = 2`, `initial_backoff_seconds = 1.0`,
`backoff_multiplier = 2.0`, `max_backoff_seconds = 5.0`, `retryable_error_kinds = RETRY_ELIGIBLE_KINDS`.

- **`max_attempts` counts ALL attempts:** `2` = the first attempt **plus at most one retry** (not
  1 + 2 retries); `1` disables retrying. `int` (not `bool`) in `1..5`.
- Backoff before attempt `n >= 2`: `min(max_backoff_seconds, initial_backoff_seconds *
  backoff_multiplier ** (n - 2))`. **Deterministic, no jitter.** With the default policy there is one
  pause (1.0 s). Validation (`AggregationConfigError`): backoff values finite, `>= 0`, `<= 600`;
  multiplier finite, `>= 1`; `bool` never accepted as a number.
- **Retry decision = structured `error_kind` only** — `is_retryable(result)` / `should_retry(result,
  attempts_made)`. Never `error_detail` text, never a provider name (AST guards in
  `test_agg_guards.py`: no `.error_detail` read, no string-sniffing calls or literals in `retry.py` /
  `execution.py`; `retry.py` imports neither `httpx` nor any adapter).
- `retryable_error_kinds` may only **narrow** the default: it must be a `frozenset` ⊆
  `RETRY_ELIGIBLE_KINDS = {NETWORK_ERROR, TIMEOUT, CONNECTION_ERROR, DECODE_ERROR,
  HTTP_SERVER_ERROR}`. `BLOCKED` and `RATE_LIMITED` (and every other kind) cannot be made
  retryable by configuration in C2.
- Configuration: `AggregationConfig.retry_policy` (global default) and `SourceConfig.retry_policy`
  (per-source override, `None` = default), both immutable; `AggregationConfig.retry_policy_for(id)`.
  Provider-specific behaviour is *data*, never `if/elif` on a provider.

### 2.1 Retry decision matrix (default policy, `max_attempts = 2`)

| Final outcome of an attempt | Retry? | Attempts (when the next attempt would succeed) |
|---|---|---|
| `SUCCESS` | no | 1 |
| `NOT_FOUND`, `BLOCKED`, `RATE_LIMITED` | **no** | 1 |
| `PARSE_ERROR`, generic `INVALID_RESPONSE` | no | 1 |
| `RESPONSE_TOO_LARGE`, `REDIRECT_ERROR` | no | 1 |
| `ADAPTER_EXCEPTION`, `RESULT_CONTRACT_MISMATCH` | no | 1 |
| `SOURCE_DEADLINE` | no (budget spent) | 1 |
| `TIMEOUT`, `CONNECTION_ERROR`, `DECODE_ERROR`, `HTTP_SERVER_ERROR`, generic `NETWORK_ERROR` | **yes** | 2 |
| a retryable failure twice in a row | — | exactly 2, final = the second failure, **never a third** |

Reasons for the "no" rows: `NOT_FOUND` is a coverage gap, not a failure (a source that lacks a film
is never re-asked because another source has it); `BLOCKED` (403 / anti-bot) must never be hit again
automatically and nothing here bypasses Cloudflare/CAPTCHA; `RATE_LIMITED` (429) carries no
`Retry-After` information in `SourceResult` yet, so an immediate repeat could worsen throttling —
**C2 has no `Retry-After`-aware scheduler and adds none**; parse/layout and contract failures are stable
(the same page parses the same way); too-large bodies and redirect loops are provider/configuration
problems; `SOURCE_DEADLINE` means the time budget is already spent. (`test_agg_retry_execution.py`,
`test_agg_retry_http.py`.)

## 3. Execution with retry (`execution.py`) — `test_agg_retry_execution.py`

- **Source-local.** A retry repeats `adapter.fetch` inside the *same* execution slot; it never
  re-runs another source. Every attempt receives the same canonical number and the same shared client.
- **Strictly serial per source; one slot.** A source's attempts never overlap, and the source holds its
  concurrency slot (through backoff) until it is finished. Therefore peak concurrent adapter fetches
  `<= max_concurrency` even when many sources retry (5 sources, `max_concurrency=2` → peak 2; 3
  sources that each retry never produce 4 concurrent fetches).
- **Total wall-clock deadline (the C2 key invariant).** `SourceConfig.deadline_seconds` is **one**
  budget for the whole source: attempt 1 **+ backoff pauses + every retry**, enforced by a single
  `asyncio.timeout`. It is **never** `deadline × attempts`. Tested: deadline 0.30 s, attempt 1 = 0.15 s
  retryable failure, backoff 0.10 s, attempt 2 hangs → the source ends at ≈0.30 s (not ≈0.55 s).
  * *Deadline inside attempt 1* → `attempt_count == 1`, no retry, `NETWORK_ERROR`/`SOURCE_DEADLINE`.
  * *Deadline inside a backoff pause* → the next attempt **never starts**; the trace says so
    (`deadline_during == "backoff"`, the never-started attempt is absent from `attempts`).
  * *Deadline inside a retry attempt* → that attempt is recorded `completed=False`
    (`deadline_during == "attempt"`); total time ≈ the configured deadline.
  * Queue time for a concurrency slot is **not** charged to the deadline (C1 rule kept).
- The final result of a deadline expiry is `NETWORK_ERROR`/`SOURCE_DEADLINE` with the real elapsed time.

## 4. Cancellation and fatal exceptions (LOW-2) — `test_agg_low2_cancellation.py`

| Situation | Behaviour |
|---|---|
| The aggregate task is cancelled by the **caller** (during an attempt or during a backoff pause) | `asyncio.CancelledError` propagates unchanged; every sibling is cancelled; **no background task is left**; no further attempt starts; the backoff sleep is interrupted at once; cancellation is never a retryable failure |
| An **adapter itself** raises `CancelledError` while no cancellation was requested for its task (`task.cancelling() == 0`) | that source → `INVALID_RESPONSE`/`ADAPTER_EXCEPTION` (detail: source id + `CancelledError`, no message); **other sources continue**; not retried; the aggregate is not cancelled |
| `KeyboardInterrupt`, `SystemExit`, `GeneratorExit`, or any custom non-`Exception` `BaseException` from an adapter | fatal control flow: siblings are cancelled first, then the **original exception object** is re-raised (identity-tested) — never a `BaseExceptionGroup`/`ExceptionGroup`, never a `SourceResult` |
| an ordinary `Exception` from an adapter | isolated: `INVALID_RESPONSE`/`ADAPTER_EXCEPTION`, message never included |

**Known limitation (documented, not solved; no thread/process isolation in C2):** a plugin adapter
that catches and swallows `CancelledError` and keeps running cannot be interrupted by
`asyncio.timeout` — if it eventually returns, its own result is used (the current behaviour is pinned by
`test_documented_limitation_…`). The three adopted adapters (`fc2db_net`, `javdb`, `av123`) do not
swallow cancellation: tested behaviourally (a hung client is cancelled promptly; the engine deadline
stops each) **and** statically (no bare `except`, no `except BaseException`, no `CancelledError`
handler anywhere in the adapter modules). Stronger isolation would be considered if third-party plugin
adapters are ever run.

## 5. Attempt diagnostics (`models.py`) — `test_agg_retry_execution.py`, `test_agg_low1_result_invariants.py`

`AggregationResult.source_execution_traces`: one immutable `SourceExecutionTrace` per **enabled**
source, in `source_results` order (empty only for a pure merge with no execution); disabled sources
have none; each `trace.final_result == source_results[i]`.

`SourceExecutionTrace(source_id, attempts, final_result, max_attempts, deadline_exceeded,
deadline_during)`, properties `attempt_count` (attempts *started*) and `retried`.
`SourceAttempt(sequence, status, error_kind, elapsed_ms, completed, backoff_before_seconds)`.
Invariants enforced at construction: sequences `1..n` in order and `n <= max_attempts`; only the last
attempt may be incomplete; no attempt after a `SUCCESS`; an unfinished last attempt ⇔
`deadline_during == "attempt"`; `"backoff"` ⇒ the last attempt completed and fewer than
`max_attempts` were made; an expired deadline ends in `NETWORK_ERROR`/`SOURCE_DEADLINE`, otherwise
`final_result` matches the last attempt's status and kind.

`elapsed_ms` of an attempt is **measured by the engine**. It is real even when the adapter-returned
`SourceResult.elapsed_ms` is `0.0` (**P2-R-07: re-evaluated, partially mitigated, still LOW** — the
adapter-reported value is deliberately left unchanged; only the trace carries the true duration).
The models can hold only status, structured kind and timings — **no** response body, cookie,
authorization header or credential (field set asserted by a test).

## 6. Aggregate semantics use the final result only — `test_agg_retry_execution.py`, `test_agg_retry_http.py`

Only each source's **final** `SourceResult` reaches `merge_source_results`. Consequently:

* attempt 1 `NETWORK_ERROR`/`TIMEOUT`, attempt 2 `SUCCESS` + another healthy source ⇒ aggregate
  **`SUCCESS`** (not `PARTIAL`); the first failure stays visible in the trace;
* attempt 1 and 2 both `HTTP_SERVER_ERROR` + another `SUCCESS` ⇒ aggregate **`PARTIAL`**;
* failed attempts' partial metadata, a retry that returns another number or another `source_id`
  (fail-closed → `RESULT_CONTRACT_MISMATCH`), or a forged provenance claim never reach the aggregate.

The real-world case that motivated C2 — a transient `av123` HTTP 500 followed by 200 — is covered
end to end: final `SUCCESS`, `attempt_count == 2`, aggregate `SUCCESS`; without retry the same
sequence is the C1 `PARTIAL` (both tested).

## 7. C1 hardening closed in C2

* **LOW-1** (`test_agg_low1_result_invariants.py`): `AggregationResult` invariants strengthened — see the
  list in `aggregation/models.py` and `PHASE3_AGGREGATION_CONTRACT.md` §4.
* **LOW-2**: §4 above.
* **LOW-3** (`test_agg_low3_config_immutability.py`): the *direct* `AggregationConfig(...)` constructor
  accepts only `field_priority` of shape `tuple[tuple[str, tuple[str, ...]], ...]`; any list/dict/set/
  nested-list/None-or-unhashable-or-non-`str` field name/malformed tuple → `AggregationConfigError`
  (never `TypeError`/`KeyError`/`AttributeError`). Mutating caller-owned objects after `create()`
  cannot change the config, its hash or its policy.
* **LOW-4** (`test_agg_low4_client_shape.py`): `MultiSourceEngine(...)` rejects at construction, before
  any request, a client whose `get` is not an `async` callable (`is_async_get`: coroutine function,
  bound async method, `functools.partial` of one, object with `async def __call__`, `AsyncMock` are
  accepted; plain `def get`, even one returning a coroutine, is rejected).

## 8. Batch planning note (required for C3)

`max_concurrency` is a semaphore **per `aggregate()` call**. A future batch that runs many
`aggregate()` calls concurrently therefore has *no* global concurrency limit — `gather(500 ×
engine.aggregate())` would give every item its own semaphore. Phase 3 batch **must** introduce a
cross-item global concurrency/resource budget (and, together with it, per-host limits and a circuit
breaker). C2 implements none of this.
