# FC2 Metadata Core — Phase 3 / C4 Batch Scheduler Contract

Status: **frozen at Phase 3 C4** (candidate; independent review pending).
Builds on `PHASE3_AGGREGATION_CONTRACT.md` (C1) and `PHASE3_RESILIENCE_CONTRACT.md` (C2/C3).
Package: `fc2_metadata_core.batch` (`config.py`, `models.py`, `scheduler.py`, `retry.py`).

**Out of scope, not implemented (C4):** circuit breaker, per-host limiter / host rate limits, persistence
of any kind (JSON / DB), NFO writer, image downloader, filesystem rename/move, Amane adapter, GUI,
the final 500-item acceptance run. `BatchResult` lives in memory only; the library has no side effects.

Each rule names the test file that enforces it (all offline and deterministic, `tests/unit/batch/`
unless stated; no wall-clock assertion anywhere).

## 1. Architecture and dependency direction

```text
caller (future CLI / scan layer: dirty filename -> canonical number)
        |  Sequence[str]  (canonical FC2 numbers, order = batch order)
        v
BatchScheduler(engine, BatchConfig)        <- this package
        |  await engine.aggregate(number)   (narrow Protocol; MultiSourceEngine satisfies it)
        v
MultiSourceEngine.aggregate  -> execute_sources_traced -> adapters      (C1/C2, unchanged)
```

* `batch` depends on the aggregation **public** contract (`AggregationResult`, `AggregateStatus`), the
  canonical-number boundary (`sources.base.require_canonical_number`) and `errors`. It **never** imports
  `sources.adapters`, `aggregation.execution` or `aggregation.engine`, never reimplements fan-out or
  merging, and never constructs a transport or registry.
* `aggregation` (and every other package) **never** imports `batch`. No cyclic import.
* Nothing imports `amane`.
* The scheduler **reuses the injected engine**. It creates no HTTP client / registry / adapter; lifecycle of
  those belongs to the caller (future CLI / upper layer).

Enforced by: `test_batch_architecture.py`, and `tests/contract/test_core_independent_of_amane.py` (F4:
the module discovery is `rglob`-derived, so every `batch/*.py` is in both the static AST scan and the
blocked-import dynamic scan; C4 adds explicit assertions that they are).

## 2. Two concurrency budgets (frozen semantics)

| Knob | Where | Bounds |
|---|---|---|
| `AggregationConfig.max_concurrency = S` | C1/C2, per `aggregate(number)` call | concurrent **source** executions **inside one item** |
| `BatchConfig.max_in_flight_items = M` | C4, per `BatchScheduler` | concurrent `aggregate(number)` calls **across items** (the *global* item budget) |

Theoretical maximum simultaneous source operations = **M × S**, further limited by the number of enabled
sources, per-source deadlines and cancellation. C4 does **not** implement a per-host limiter: two sources
served from one host, or many items hitting one source, are not throttled per host (Phase 3 / C5).

`max_in_flight_items` is enforced **at the scheduler boundary by bounded admission**, not by a semaphore
that inner code contends on: at any instant at most `M` `aggregate()` calls exist for the scheduler.

**One active run per scheduler instance.** `run()` / `retry_failed()` on a scheduler that already has an
active run raises `BatchBusyError` (fail closed) — otherwise two concurrent runs would silently double the
budget. The flag is released on success, on ordinary completion, on fatal exceptions and on cancellation.
Independent budgets require independent scheduler instances (their budgets add up).

`test_batch_concurrency.py`, `test_batch_bounded_admission.py`, `test_batch_config.py`.

## 3. `BatchConfig` (`config.py`)

Frozen dataclass, validated in `__post_init__`, immutable.

* `max_in_flight_items: int`, default **4**, valid range **1..64** (`MAX_IN_FLIGHT_ITEMS_LIMIT`); a `bool`
  is not an `int`; anything else raises `BatchConfigError` (before any engine call).
* There is **no** `continue_on_item_failure` switch. **Frozen semantics: an ordinary failure of one item is
  always isolated and the batch always continues.** A knob that could turn isolation off would contradict the
  project rule "one failed film must not block the others". A fatal `BaseException` (§7) is not an item
  failure and is unaffected.

## 4. Input contract (`BatchScheduler.run`)

* The batch is a `collections.abc.Sequence` of `str`: order is meaningful, so output is deterministic.
  **Rejected** with `BatchInputError` (zero engine calls): a bare `str` / `bytes` / `bytearray` /
  `memoryview`, any `Set` / `frozenset`, any `Mapping`, any generator / iterator / other non-`Sequence`.
* The scheduler takes a **snapshot** (`tuple(numbers)`) once; later mutation of the caller's list has no effect.
* Every element must pass the existing canonical boundary (`require_canonical_number`, exactly
  `FC2-` + 5..8 digits, e.g. `FC2-1234567`). **The scheduler contains no second FC2 parser and does no
  normalisation.** Dirty input (`abc FC2PPV-1234567.mp4`, `fc2ppv 1234567`) must be normalised by the
  upper scan/normalize layer first; it is **rejected here**, not repaired.
* **All-or-nothing validation:** if any element is invalid, the whole batch is rejected with
  `BatchInputError` *before* any `aggregate()` call; the message lists the offending indices (capped) and a
  truncated `repr`, never a partial run.
* **Empty input is legal**: returns `BatchResult(items=(), generation=0)`, `total == 0`, all counts `0`;
  the engine is never called; no division anywhere.
* **Duplicates are preserved as separate work items** (a batch is an execution list; the same number may
  later come from two files). Each item is identified by its **original `index`**, never by its number;
  no dedupe, no `dict[number]` anywhere. Two equal numbers ⇒ two independent `aggregate()` calls and two
  `BatchItemResult`s with `index` 0 and 1.

`test_batch_input.py`.

## 5. Scheduling model: bounded worker admission (`scheduler.py`)

* `min(M, len(work))` **worker tasks** are created (never one task per item). Workers pull the next
  position from a shared cursor and `await engine.aggregate(number)` **directly in the worker** — no
  per-item task is ever created by the batch layer. Live batch tasks are therefore `O(M)`, independent of
  the batch size (`N = 10,000` with `M = 4` ⇒ 4 batch tasks + the caller's task at the first barrier).
  The scheduler also never materialises `N` coroutine objects.
* `M = 1` ⇒ strictly serial; `M > N` ⇒ peak = `N`; peak never exceeds `M`.
* Memory is `O(N)` only for the result slots (one pointer each); `BatchItemResult` objects are created as
  items finish.
* Admission stops the instant a fatal exception or a cancellation is seen (§7). Before **every** admission a
  worker checks (a) a run-local `stopping` flag, set synchronously by whichever worker sees a fatal signal,
  and (b) whether the driving task (the one awaiting `run()` / `retry_failed()`) has a **new** pending
  cancellation request (`Task.cancelling()` above its value when the run began). (a) closes the race where a
  sibling that was already scheduled in the same loop iteration finishes its item and loops before the
  TaskGroup can cancel it; (b) closes the one-iteration gap between `task.cancel()` and the cancellation
  reaching the workers through the TaskGroup. Both are pinned by tests that fail if the check is removed.
* **No per-item batch-level timeout in C4.** Termination of one item is guaranteed by the C2 per-source
  total deadlines inside the engine. A user-supplied engine that never returns would hold its slot forever
  (documented limit; the adopted `MultiSourceEngine` cannot).

`test_batch_bounded_admission.py` (includes a *control* test proving the measurement distinguishes a naive
`create_task × N + semaphore` scheduler: it would show `N` live tasks).

## 6. Result model (`models.py`) and status mapping

All immutable (`frozen=True, slots=True`), tuples only, invariants enforced in `__post_init__`
(`BatchContractError`).

`BatchItemResult`: `index`, `number`, `status: BatchItemStatus`, `aggregation_result | None`,
`error_kind: BatchItemErrorKind | None`, `error_type: str | None`, `generation`, `elapsed_ms`.

| Engine outcome | `status` | `aggregation_result` | `error_kind` / `error_type` |
|---|---|---|---|
| returns `AggregationResult` `SUCCESS` | `SUCCESS` | the result | `None` / `None` |
| returns `AggregationResult` `PARTIAL` | `PARTIAL` | the result | `None` / `None` |
| returns `AggregationResult` `FAILED` | `FAILED` | the result (all `SourceResult`s kept) | `None` / `None` |
| raises an ordinary `Exception` | `FAILED` | `None` | `ENGINE_EXCEPTION` / exception **class name** |
| returns a non-`AggregationResult`, or one for another number | `FAILED` | `None` | `RESULT_CONTRACT_MISMATCH` / returned object's **class name** |

Batch statuses are a 1:1 mapping of `AggregateStatus`; no new source status is invented. Invariant: exactly
one of `aggregation_result` / `error_kind` is set; `aggregation_result.number == number`; `status` is the
mapping of `aggregation_result.status`.

**No secret leak:** for an ordinary exception only `type(exc).__name__` is recorded — never `str(exc)`,
`repr(exc)`, `args`, the traceback or the exception object. The scheduler keeps no reference to the exception.

`BatchResult(items, generation)`: `items` in **input order**, `index == position` (`0..n-1`, contiguous);
derived `total`, `success_count`, `partial_count`, `failed_count`, `failed_items`, `failed_indices`,
`failed_numbers` (tuples aligned with `failed_indices`; may contain repeated numbers). No stored redundant
counts (nothing can contradict). **No batch-level overall status enum** is introduced: `AggregateStatus.PARTIAL`
already has a meaning, and counts are unambiguous.

`RetryBatchResult(items, generation)`: only the retried items, strictly increasing `index`, every
`item.generation == generation >= 1`; same derived counts.

`test_batch_models.py`, `test_batch_status_mapping.py`.

## 7. Fatal exceptions and cancellation (consistent with C1/C2 §4)

* **Caller cancels the batch** (`run()` task cancelled): `CancelledError` propagates unchanged; every
  running worker (and through it the engine's own task group) is cancelled **and awaited**; items not yet
  admitted are **never started**; no task outlives the call.
* **`KeyboardInterrupt`, `SystemExit`, `GeneratorExit`, any other non-`Exception` `BaseException`**
  raised by `engine.aggregate`, and a `CancelledError` the engine raises **on its own** (nobody cancelled):
  fatal control flow. Admission stops immediately, siblings are cancelled and awaited, and the **original
  exception object** is re-raised to the caller — never a `BaseExceptionGroup`/`ExceptionGroup`, never a
  `BatchItemResult`, never `FAILED`. (Unlike a *source* adapter, whose self-raised `CancelledError` C2 turns
  into a source failure, a batch-level `CancelledError` is always propagated: swallowing it here would lose
  cancellation semantics for the whole batch.)
* If several fatals race, one is propagated as the original object (C2-L5); the others are not preserved.
* No partial `BatchResult` is returned after a fatal exception.
* Known limit (same as C2): an engine that swallows `CancelledError` and keeps running cannot be interrupted.

`test_batch_fatal_and_cancellation.py`, `test_batch_isolation.py`.

## 8. Failed-subset retry (`retry.py`, `BatchScheduler.retry_failed`)

* `retry_failed(previous: BatchResult) -> RetryBatchResult` re-executes **only `FAILED` items**, selected by
  **original index** (never by number: with `index0 SUCCESS FC2-X` and `index1 FAILED FC2-X` only index 1 is
  retried). `SUCCESS` and `PARTIAL` items are never retried (a `retry_partial` option is deliberately not
  provided in C4). It uses the same bounded worker model and the same fatal/cancel rules.
* **Generation:** primary run = generation `0`; the retry of a generation-`g` result is generation `g + 1`.
  Each `BatchItemResult.generation` says which round produced it. A retry round with nothing to retry is
  still a round (`RetryBatchResult(items=(), generation=g+1)`). `previous` is never mutated.
* `apply_retry(previous, retry) -> BatchResult` is a **pure** function producing a **new** result in the
  original order in which only the retried items are replaced (unretried items are the same objects). It
  **fails closed** (`BatchRetryError`, nothing returned) unless: both types are right;
  `retry.generation == previous.generation + 1` (rejects stale / replayed / cross-batch retries); the retry's
  indices are **exactly** `previous.failed_indices`; and each retried item's `number` equals the previous
  item's number at that index.
* Retry results are never merged implicitly: the caller applies them.

`test_batch_retry.py`.

## 9. Test matrix

| Requirement | Test file |
|---|---|
| config validation | `test_batch_config.py` |
| Sequence contract, unordered rejected, empty, canonical boundary, dirty input, duplicates, snapshot | `test_batch_input.py` |
| immutable models / invariants / counts | `test_batch_models.py` |
| status mapping, `RESULT_CONTRACT_MISMATCH`, protocol | `test_batch_status_mapping.py` |
| stable ordering, global concurrency 1 / M / >N, busy guard | `test_batch_concurrency.py` |
| bounded admission (`O(M)` tasks), control test | `test_batch_bounded_admission.py` |
| ordinary exception isolation, no secret leak | `test_batch_isolation.py` |
| cancellation, KeyboardInterrupt / SystemExit / GeneratorExit / custom / self-raised CancelledError, sibling cleanup, no orphan, no admission after stop | `test_batch_fatal_and_cancellation.py` |
| failed-subset retry, duplicate-number selective retry, generation, mismatch fail-closed, `apply_retry` | `test_batch_retry.py` |
| 100-item offline stage gate | `test_batch_stage_gate_100.py` |
| large-N stress (10,000 items, `M = 4`) | `test_batch_large_n_stress.py` |
| no `aggregation → batch`, no adapter import, Amane independence, F4 discovery | `test_batch_architecture.py`, `tests/contract/test_core_independent_of_amane.py` |

## 10. Backlog carried forward (nothing here is fixed by C4)

* **C3-N1 — OPEN / LOW.** The 50-ID primary gate's anti-rerun / set-binding guard is procedural rather than
  globally enforced. **Before any future reuse of `tools/run_50id_coverage_gate.py`:** pin the expected
  set path/blob **and** detect an existing Primary through *committed* evidence, not only the supplied
  `--out-dir`. C4 does not touch the frozen C3 runner or evidence.
* C3-N2 LOW (evidence set hash depends on working-tree line endings) · C3-N3 LOW (attempt-1 pool
  traceability incomplete) · **C3-N4 LOW: the 50-ID acceptance population is torrent-indexed / first-page
  prefix sampled. Any "98%" in a document means "98% aggregate union coverage on the frozen C3 50-ID
  acceptance population", never FC2-catalogue coverage.**
* P2-R-05, P2-R-06, P2-R-10 LOW · P2-R-07 partially mitigated LOW · C2-L2 LOW / DEFERRED
  (`SourceExecutionTrace` permits states the engine never produces; C4 *carries* `AggregationResult`s
  including their traces in `BatchItemResult` but neither reads nor relies on trace invariants) ·
  F3 DEFERRED · F5 DEFERRED · F4 CLOSED.
* Next (not started): C5 = circuit breaker + per-host limiter (each needs its own frozen contract);
  final 500-item failure-injection acceptance; NFO / filesystem / Amane adapter.
