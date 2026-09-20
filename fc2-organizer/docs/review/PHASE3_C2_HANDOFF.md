# PHASE3_C2_HANDOFF.md

```text
Phase: Phase 3 / C2 — Resilience & Retry

Base (Phase 3 C1 Docs Head; C1 handoff commit):
c2a749ec3dae7428a9475b9b2c28ad114c3c0f4b

PHASE3_C2_CODE_HEAD (Phase 3 C2 Code Review Candidate):
81f80c2532732edd8bdb4a5962de347dda66de6e
  = 3baf7d6  feat(source): add structured failure taxonomy and classify transport/HTTP failures (P2-R-12)
  + 895125d  feat(aggregation): add Phase 3 C2 bounded retry, total deadline, attempt diagnostics and C1 LOW-1..4 fixes
  + 81f80c2  docs(aggregation): add Phase 3 C2 resilience contract and probe attempt diagnostics

Formal review range:
c2a749ec3dae7428a9475b9b2c28ad114c3c0f4b..81f80c2532732edd8bdb4a5962de347dda66de6e

PHASE3_C2_DOCS_HEAD:
the commit "docs(review): add Phase 3 C2 handoff" whose parent is the Code Head above
and whose only change is this file (docs diff: CODE_HEAD..DOCS_HEAD). A commit cannot
contain its own hash, so it is identified by that rule and reported in the hand-back message.

Branch:
claude/phase-0-amane-integration-fnvhpq
```

**Not a PASS declaration.** This is a candidate for independent Phase 3 C2 review.
Phase 3 C3 and every later subphase have **not** started.

Authoritative specification: `docs/specifications/PHASE3_RESILIENCE_CONTRACT.md` (new).
Revised only where C2 changed them: `PHASE3_AGGREGATION_CONTRACT.md` (marked "(C2)"),
`FC2_METADATA_CORE_CONTRACT.md` §3 (`SourceErrorKind`).

## LOW-1 … LOW-4 (C1 review findings) — CLOSED, each with its own regression file

| Finding | Fix | Regression |
|---|---|---|
| LOW-1 `AggregationResult` could be built inconsistently | invariants made exact (`contributing_source_ids == successful_source_ids`; `disabled_source_ids` shape/disjointness; `FieldConflict` validated against `CONFLICT_FIELDS` and contributing sources; traces aligned with results). The module docstring lists what is enforced **and what is not verified** (values / `field_sources` / conflict completeness) — the "cannot be built inconsistently" claim is narrowed to that list | `test_agg_low1_result_invariants.py` |
| LOW-2 cancellation | caller cancel → original `CancelledError`, siblings cancelled, no leftover tasks, backoff interrupted; adapter self-raised `CancelledError` (`task.cancelling()==0`) → isolated `ADAPTER_EXCEPTION`; fatal `BaseException` → the **original object** (identity-tested, no exception group) | `test_agg_low2_cancellation.py` |
| LOW-3 direct `AggregationConfig(...)` accepted a mutable `field_priority` | strict shape `tuple[tuple[str, tuple[str, ...]], ...]` validated in `__post_init__`; anything else → `AggregationConfigError` (never `TypeError`) | `test_agg_low3_config_immutability.py` |
| LOW-4 engine accepted a client with a non-async `get` | `is_async_get` check at `MultiSourceEngine` construction, before any request | `test_agg_low4_client_shape.py` |

## Failure taxonomy (P2-R-12 — see below)

`SourceStatus` is unchanged. `SourceErrorKind` gained `TIMEOUT`, `CONNECTION_ERROR`, `DECODE_ERROR`,
`REDIRECT_ERROR`, `SOURCE_DEADLINE`, `HTTP_SERVER_ERROR`, `RESPONSE_TOO_LARGE`, `ADAPTER_EXCEPTION`,
`RESULT_CONTRACT_MISMATCH`. `ALLOWED_ERROR_KINDS` freezes which kinds may accompany which status
(`SourceResult` rejects any other pair); the six generic kinds are kept, so every pre-C2 result still
validates. `REDIRECT_ERROR` is a `NETWORK_ERROR`-status kind (what it already was; stated decision).

## RetryPolicy

`max_attempts` counts **all** attempts (default 2 = first attempt + at most one retry; `1` = no retry;
limit 5); `initial_backoff_seconds=1.0`, `backoff_multiplier=2.0`, `max_backoff_seconds=5.0`;
deterministic, **no jitter**. Decision from the structured `error_kind` **only** (AST guards forbid
reading `error_detail` or string-sniffing in `retry.py`/`execution.py`; no provider name).
`retryable_error_kinds` can only narrow `{NETWORK_ERROR, TIMEOUT, CONNECTION_ERROR, DECODE_ERROR,
HTTP_SERVER_ERROR}`; `BLOCKED`/`RATE_LIMITED` can never be made retryable. Global default on
`AggregationConfig`, per-source override on `SourceConfig`, both immutable.

## Retry matrix (default policy)

| Outcome | Retried | Attempts |
|---|---|---|
| `SUCCESS` | no | 1 |
| `NOT_FOUND`, `BLOCKED`, `RATE_LIMITED` (HTTP 404 / 403+Cloudflare / 429) | **never** | 1 |
| `PARSE_ERROR`, generic `INVALID_RESPONSE`, `RESPONSE_TOO_LARGE`, `REDIRECT_ERROR`, `ADAPTER_EXCEPTION`, `RESULT_CONTRACT_MISMATCH` | no | 1 |
| `SOURCE_DEADLINE` | no | 1 |
| `TIMEOUT`, `CONNECTION_ERROR`, `DECODE_ERROR`, `HTTP_SERVER_ERROR` (500–599), generic `NETWORK_ERROR` | yes | ≤ 2 (never a third) |

No `Retry-After` handling exists (none added). No CAPTCHA/Cloudflare bypass. Details and reasons:
`PHASE3_RESILIENCE_CONTRACT.md` §2.1.

## Deadline + retry (total wall clock)

`SourceConfig.deadline_seconds` is **one** budget for attempt 1 + backoff + every retry (single
`asyncio.timeout`), never `deadline × attempts`. Tested: A) deadline inside attempt 1 → 1 attempt, no
retry, `SOURCE_DEADLINE`; B) deadline inside backoff → next attempt never starts
(`deadline_during == "backoff"`); C) deadline inside the retry attempt → recorded `completed=False`;
D) 0.30 s budget with 0.15 s failing attempt + 0.10 s backoff + hanging retry ends at ≈0.30 s, not
≈0.55 s. Backoff is deterministic and holds the source's one concurrency slot; attempts are strictly
serial per source; peak concurrent fetches ≤ `max_concurrency` even when every source retries.
Queue time waiting for a slot is not charged to the deadline.

## Cancellation / BaseException

See LOW-2 above and `PHASE3_RESILIENCE_CONTRACT.md` §4. **Documented limitation (not solved):** an
adapter that catches and swallows `CancelledError` and keeps running cannot be interrupted by
`asyncio.timeout`; there is no thread/process isolation in C2. The three adopted adapters
(`fc2db_net`, `javdb`, `av123`) were proven not to swallow cancellation — behaviourally (a hung client
is cancelled promptly and the deadline stops each) and statically (no bare `except`, no
`except BaseException`, no `CancelledError` handler in their modules).

## Attempt diagnostics

`AggregationResult.source_execution_traces` = one `SourceExecutionTrace` per enabled source (config
order): `attempts` (`SourceAttempt(sequence, status, error_kind, elapsed_ms, completed,
backoff_before_seconds)`), `final_result`, `max_attempts`, `deadline_exceeded`, `deadline_during`,
`attempt_count`, `retried`. Only status, structured kind and timings — no body/cookie/header/error
text. **Only the final result is merged**: attempt 1 transient failure + attempt 2 success ⇒ that
source is a success and the aggregate is `SUCCESS` (not `PARTIAL`), the first failure is visible in the
trace; two failures ⇒ that source is failed and the aggregate is `PARTIAL`.

## P2-R-07 — NOT closed

Re-evaluated: **partially mitigated, still LOW.** The engine now measures each attempt's `elapsed_ms`
itself, so diagnostics are correct even when an adapter reports `SourceResult.elapsed_ms == 0.0`;
the adapter-reported field itself is deliberately unchanged.

## P2-R-12 — CLOSED

Structural closure, not a mapping tweak: (1) a structured taxonomy with an enforced status↔kind
relation; (2) production classification: HTTP 500–599 → `INVALID_RESPONSE`/`HTTP_SERVER_ERROR`;
transport timeout/connection/decode/redirect/oversize → distinct kinds; 403/Cloudflare `BLOCKED`,
404 `NOT_FOUND`, 429 `RATE_LIMITED`, other non-200 and semantic drift stay non-retryable generic kinds;
(3) `HttpxTransport` now really raises `HttpDecodingError` for `httpx.DecodingError` (garbage
gzip/deflate reproduced over `httpx.MockTransport`; unknown charsets do not leak); (4) the retry
decision reads only `error_kind`. Proof through the production path (real adapters + real
`HttpxTransport` over `httpx.MockTransport`): `test_agg_retry_http.py` (84 tests) and
`tests/unit/sources/test_failure_classification_c2.py` (38). Legacy coarse helpers are unchanged.

## Offline tests

```text
python --version                      Python 3.12.10
python -m pytest --collect-only -q    1305 tests collected
python -m pytest -v                   1305 passed, 0 failed, 0 skipped (0 xfail/error)
python -m pytest -q                   1305 passed
```

Targeted suites were run first, in order, all green: Phase 1 SourceResult/taxonomy/metadata (284) →
transport (8) → source/base/common classification (302) → aggregation config/models/retry policy
(259) → execution/retry (190) → merge/engine/guards (96) → LOW-1..4 (134). Frozen baseline: the base
commit has 732 tests; run against the C2 source, **731 pass** and 1 fails —
`test_agg_guards.py::test_no_retry_backoff_or_circuit_breaker_in_c1`, the C1 guard asserting "no retry
exists". That guard is **intentionally replaced** by a circuit-breaker-only guard plus AST
`error_detail`/string-sniffing guards (retry now exists by design). Nothing else in the base suite was
edited except the test support helpers (additive: `failed(..., error_kind=)`, `add_sequence`,
`request_count`). New C2 tests: taxonomy, retry policy, retry execution (deadline A–D, matrix,
cancellation, concurrency), production-path HTTP, classification, LOW-1..4, and the probe summary.

Test-isolation note (unchanged from C1): import core classes at module top in tests — the F4 contract
test re-imports the package.

## Live 7-ID smoke (`tools/probe_aggregate.py`, low frequency, 3 s between IDs, nothing recorded)

Run once after the code was stable, before freezing the head. Output was inspected in a job-scratch
file only; **no evidence file was written and Phase 2 evidence JSON was not touched**.

| ID | Aggregate | fc2db_net | javdb | av123 |
|---|---|---|---|---|
| FC2-4825061 | success | not_found (404) ×1 | success ×1 | success ×1 |
| FC2-4824605 | success | success ×1 | not_found ×1 | not_found (404) ×1 |
| FC2-4979299 | success | success ×1 | success ×1 | success ×1 |
| FC2-4976588 | success | success ×1 | success ×1 | not_found (404) ×1 |
| FC2-1042815 | success | success ×1 | success ×1 | not_found (404) ×1 |
| FC2-4978035 | success | success ×1 | success ×1 | success ×1 |
| FC2-4972767 | success | success ×1 | success ×1 | not_found (404) ×1 |

7/7 aggregate `success`; every source `attempt_count == 1`. **No transient failure occurred naturally
in this run, so live retry behaviour was not observed** — retry is proven offline (including the
production path with the real transport) and is not claimed as live-verified. `not_found` results were
correctly never retried. This is a smoke check, not a coverage claim.

## 50-ID gate — NOT RUN / DEFERRED

The ≥ 90 % `number + title` gate on the frozen 50-ID set was **not run** and is not claimed.

## Batch / Circuit breaker / NFO / Amane — NOT STARTED

No batch engine, global batch semaphore, 500-item batch, failed-subset retry, circuit breaker, NFO
writer, image download, file rename/move/organisation, Amane adapter or GUI. **Planning note for C3:**
`max_concurrency` is per-`aggregate()` call; a batch must introduce a cross-item global
concurrency/resource budget (plus per-host limits and a circuit breaker) — it must not be
`gather(500 × aggregate())`.

## Remaining backlog

- **P2-R-05** probe `anti_bot_hint` fires on `cf-ray` alone — LOW.
- **P2-R-06** probe `requested_url` is the final URL — LOW.
- **P2-R-10** JavDB title double-unescape — LOW, kept as-is.
- **P2-R-07** partially mitigated, still LOW (above).
- **F3, F5** — DEFERRED (must close before Phase 5 integration); nothing in C2 touched their mechanisms.
  **F4** stays CLOSED.

## Suggested review focus

1. `aggregation/execution.py`: total-deadline scope vs. backoff/retry; `_FatalSignal` unwrapping; that no
   path swallows `CancelledError` from the caller.
2. `models/source_result.py` `ALLOWED_ERROR_KINDS` relation and the `REDIRECT_ERROR` placement decision.
3. That `retry.py`/`execution.py` decide from `error_kind` alone (AST guards in `test_agg_guards.py`).
4. `AggregationResult`/`SourceExecutionTrace` invariants vs. the "what is not verified" list.
