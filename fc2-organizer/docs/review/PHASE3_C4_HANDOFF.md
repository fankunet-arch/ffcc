# PHASE3_C4_HANDOFF.md

```text
Phase: Phase 3 / C4 — Batch Scheduler Core

C4 Base (Phase 3 C3 Docs Head):
03d62702b59a6736a858081bc1e7774d6edb29af

PHASE3_C4_CODE_HEAD (final code review candidate; code is FROZEN):
e633b403c0a420d033a6bf9289bdd0d249048368

PHASE3_C4_DOCS_HEAD:
the commit "docs(review): add Phase 3 C4 batch scheduler handoff" whose parent is the Code Head above and
whose only change is this file (diff CODE_HEAD..DOCS_HEAD). A commit cannot contain its own hash, so it is
identified by that rule and reported in the hand-back message.

Branch:
claude/phase-0-amane-integration-fnvhpq   (fast-forward only; C3 history untouched)

Python: 3.12.10
```

**Not a PASS declaration.** This is a candidate for independent Phase 3 C4 review. Circuit breaker, per-host
limiter, persistence, NFO writer, image downloader, filesystem operations, Amane adapter, GUI and the final
500-item acceptance are **NOT STARTED / NOT RUN**.

Review range: `git diff 03d6270 e633b40` (21 files: 5 new source files + a one-line re-export in the top-level
`__init__.py`, 1 spec, 13 new test/support files, 1 edit to the F4 contract test).
`src/fc2_metadata_core/aggregation/**`, `sources/**`, `http/**`, `tools/**` and every frozen C3 evidence file are
**unchanged** (`git diff --stat 03d6270 e633b40 -- src/fc2_metadata_core/aggregation src/fc2_metadata_core/sources
src/fc2_metadata_core/http tools docs/acceptance` is empty). The only edit to existing source is one line in
`src/fc2_metadata_core/__init__.py` (re-export `batch`).

## Tests

| | count |
|---|---|
| C4 Base (`03d6270`) collected / passed | 1595 / 1595 |
| Code Head (`e633b40`) collected | **1850** |
| passed / failed / skipped | **1850 / 0 / 0** |
| new tests | 255 = 247 in `tests/unit/batch/` + 8 in `tests/contract/` (3 explicit F4/Amane tests + 5 new parametrised static-scan cases, one per new `batch/*.py`) |

Commands run on the frozen tree: `python --version`, `python -m pytest --collect-only -q`, `python -m pytest -v`,
`python -m pytest -q` — all green. **Honest note:** one earlier full run of the same tree reported a single failure in
the *pre-existing* C2 wall-clock test `test_agg_retry_execution.py::test_17_total_deadline_covers_attempt_backoff_and_retry_not_deadline_times_attempts`
(that run took 74 s instead of ~30 s). Two unrelated `atk_fuzz.py` python processes (started the previous day, not
part of this job) were running on the machine. The test passed alone (56/56 in its file) and in the next three full
runs. None of the C4 tests contains a wall-clock assertion; the C4 files were repeated 6× (291 passed each time) and
also run in both orders relative to `tests/contract` (which purges `sys.modules`).

## What C4 adds (`src/fc2_metadata_core/batch/`)

| File | Role |
|---|---|
| `config.py` | `BatchConfig(max_in_flight_items)` — frozen, 1..64, default 4, `bool` rejected |
| `models.py` | `BatchItemResult`, `BatchResult`, `RetryBatchResult`, `BatchItemStatus`, `BatchItemErrorKind`, error types |
| `scheduler.py` | `BatchScheduler.run` / `.retry_failed`, `validate_batch`, `AggregationEngine` Protocol |
| `retry.py` | `failed_work`, `apply_retry` (pure, fail-closed) |
| `__init__.py` | public surface |

Contract: `docs/specifications/PHASE3_BATCH_CONTRACT.md` (rule → test-file matrix in §9).
Dependency direction: `batch → aggregation (public package) + sources.base.require_canonical_number + errors + normalize`.
Nothing imports `batch` except the top-level package facade; `batch` imports no adapter, no `execution`/`engine`/`merge`
internals, no transport, no `os`/`pathlib`/`json`/`sqlite3`/… (`test_batch_architecture.py`).

## Global concurrency semantics

* `BatchConfig.max_in_flight_items = M` bounds concurrent `aggregate(number)` calls **across items**; the existing
  `AggregationConfig.max_concurrency = S` bounds source executions **inside one item**. Theoretical maximum
  simultaneous source operations = **M × S** (also limited by source count / deadlines / cancellation).
  **No per-host limiter** — deferred to C5.
* `M = 1` is strictly serial (calls start and finish in input order); `M > N` peaks at `N`; peak never exceeds `M`.
* **One active run per scheduler**: a concurrent `run()`/`retry_failed()` raises `BatchBusyError` (otherwise two runs
  would silently double the budget). Released on success, fatal exception and cancellation. Independent budgets need
  independent scheduler instances (their budgets add).
* Design choice, stated: there is **no** `continue_on_item_failure` switch — ordinary item failure is always isolated.

## Bounded admission proof (not "N tasks + semaphore")

`min(M, N)` worker tasks pull the next position from a shared cursor and `await engine.aggregate(number)` directly.
The batch layer never creates a task or a coroutine per item. Proof, all count-based and machine-speed independent
(`test_batch_bounded_admission.py`): `M` calls are held open at a barrier (an `Event`), then

| measure at the barrier | N = 10,000, M = 4 |
|---|---|
| live asyncio tasks | **6** = asyncio.run main task + `run()` task + 4 workers |
| live `ScriptedEngine.aggregate` coroutine objects (via `gc`) | **4** |
| items admitted (engine calls started) | **4** |

Parametrised over `M ∈ {1, 4, 16, 64}` at `N = 3000`, and `N < M` (5 items, M = 64 ⇒ 5 workers). Two **control** tests
run a deliberately naive design through the *same* measurement and show it is distinguishable: `create_task × N +
Semaphore` reports ≥ 2000 live tasks (N = 2000, M = 4); pre-building N `aggregate` coroutines reports ≥ 2000 live
coroutines. `test_admission_is_completion_driven_one_new_item_per_freed_slot` shows that finishing one item admits
exactly one new item.

## Input, duplicates, ordering

* Input is an ordered `Sequence[str]`. Rejected with `BatchInputError` (zero engine calls): bare `str`/`bytes`/
  `bytearray`/`memoryview`, `set`/`frozenset`, `Mapping` and its views, generators/iterators, `None`, other objects.
  The scheduler snapshots the input (`tuple(...)`).
* Every element goes through the existing `require_canonical_number` (`FC2-` + 5..8 digits). **No second parser, no
  normalisation.** Dirty input (`abc FC2PPV-1234567.mp4`) is rejected, not repaired — that is the upstream scan layer's job.
  Validation is **all-or-nothing** before any call; the message lists offending indices (first 10) with a truncated
  `repr` and never calls a hostile element's `repr`/`str`.
* Empty input is legal: `BatchResult(items=(), generation=0)`, `total == 0`, engine never called.
* **Duplicates are separate work items**, identified by their original `index` (never `dict[number]`); two equal
  numbers ⇒ two `aggregate()` calls and two results with indices 0 and 1.
* **Stable ordering:** completion may be arbitrary (test forces `E C A D B`); `BatchResult.items` is always input
  order; `failed_indices` / `failed_numbers` follow batch order.

## Status mapping, failure isolation, no leaks

`AggregateStatus` maps 1:1 to `BatchItemStatus` (SUCCESS/PARTIAL/FAILED); a FAILED aggregate keeps every `SourceResult`.

| Engine outcome | item |
|---|---|
| returns `AggregationResult` | status = mapping; result carried through untouched |
| ordinary `Exception` (incl. `RecursionError`, `MemoryError`, `ExceptionGroup`) | `FAILED`, `ENGINE_EXCEPTION`, `error_type` = class name; **siblings and admission continue** |
| non-`AggregationResult`, or a result for another number | `FAILED`, `RESULT_CONTRACT_MISMATCH` (fail closed) |

Only `type(exc).__name__` is recorded (sanitised: non-identifier / over-long / hostile-metaclass names become
`UnknownType`) — never `str`/`repr`/`args`/traceback; a weakref test shows the scheduler retains no exception object.

## Fatal exceptions and cancellation

* Caller cancels the batch → `CancelledError` propagates unchanged; running items are cancelled **and awaited**
  (through a real `MultiSourceEngine` too, so the engine's nested task group is exercised); un-admitted items never
  start; no orphan task; scheduler reusable afterwards.
* `KeyboardInterrupt` / `SystemExit` / `GeneratorExit` / custom `BaseException` (and a `CancelledError` the *engine*
  raises on its own) → admission stops at once, siblings cancelled and awaited, the **original object** is re-raised
  (identity asserted; never a group, never a FAILED item, no partial `BatchResult`). Simultaneous fatals: one
  original propagated (same rule as C2-L5).
* Deliberate difference from C2, stated: a *source adapter's* self-raised `CancelledError` is isolated as an adapter
  failure (C2); at *batch* level an engine's self-raised `CancelledError` is propagated, as the task requires.
* Two admission races found and closed **by my own tests while writing them**: (1) a sibling already scheduled in
  the same loop iteration as a fatal would finish its item, loop and admit the next one before the TaskGroup could
  cancel it → run-local `stopping` flag set synchronously; (2) after `task.cancel()` the cancellation reaches the
  workers one loop iteration later, so a freed worker could admit one more item → workers also check the driving
  task's `Task.cancelling()` against its value at run start.

## `retry_failed` / `apply_retry`

* `retry_failed(previous: BatchResult) -> RetryBatchResult` re-runs **only `FAILED`** items, selected by **original
  index** (never by number); SUCCESS and PARTIAL are never retried; no `retry_partial` option exists. Same bounded worker
  model and fatal/cancel rules.
* **Generation:** primary = 0; retry of a generation-`g` result = `g+1`; each item carries its round; an empty retry
  round is still a round. `previous` is never mutated.
* `apply_retry(previous, retry) -> BatchResult` is pure, keeps original order, and **fails closed**
  (`BatchRetryError`) unless: types right; `retry.generation == previous.generation + 1` (rejects stale / replayed);
  retry indices are **exactly** `previous.failed_indices`; each retried number equals the previous number at that
  index. Unretried items are the same objects.
* Duplicate-number case: `[X SUCCESS, X FAILED]` → only index 1 is retried and replaced.
* Not introduced: a batch-level overall status enum (counts only; `PARTIAL` already has an item-level meaning).

## 100-item offline stage gate — PASS

`test_batch_stage_gate_100.py` (scripted engine, **not** a live scrape): 100 items (90 unique + 10 duplicates) with 10
plan categories — success, partial, deadline-like partial, permanent failed aggregation, ordinary exception recovering
on retry, slow success, failed aggregation recovering to partial, permanent ordinary exception, contract mismatch
recovering. `M = 6`. Checked: 100 items accounted for exactly once, indices `0..99`, input order, statuses equal the
plan (computed independently of the run), each number called exactly its multiplicity, peak == 6, exceptions/mismatches
recorded without secrets, `retry_failed` re-ran exactly the failed subset in batch order (engine call log), merged
result complete/ordered with per-item generations and untouched items being the same objects, a second retry round
touching only what is still failed, zero orphan tasks, `engine.active == 0`.

## Large-N stress — PASS

`test_batch_large_n_stress.py`, parametrised `(N, M) ∈ {(10,000, 4), (5,000, 1), (5,000, 64)}`; no wall-clock assertion.
The number of live tasks is sampled **inside the engine on every call**:

```text
N = 10,000   configured limit M = 4   peak admitted (engine.peak) = 4   calls = 10,000
max live tasks sampled = 5  (1 caller task + ≤ 4 workers)
```

(measured by a one-off script on the frozen tree; the test asserts `≤ M + 1` and `peak == M`). It also checks
completeness, order, exactly-once and a failed-subset retry over N items.

## Mutation check (evidence that the tests bite)

Each mutation was applied to a pristine `scheduler.py` / `retry.py` and the batch suite run; the source was restored after
each. All 11 were caught: remove the driver-cancellation check · remove `stopping` on fatal · remove `stopping` on
self-cancel · task-per-item · `workers = M+1` · swallow engine self-cancel · leak exception text · results in completion
order · dedupe by number · retry PARTIAL too (10 by a failing assertion) — and "remove busy guard", which is caught only
as a *hang* (the concurrent-run test blocks; a hang is a poor failure mode but it is a detection). The first version of
the suite let the "remove `stopping` on fatal" mutation **survive**; I added the same-loop-iteration race test
(`test_a_sibling_resuming_in_the_same_loop_iteration_admits_nothing_after_the_fatal`) to close that gap, and fixed a
harness bug in that new test (it counted its own outer task as a leftover) before the freeze. The mutation script is
job scratch and is not committed.

## Known limits (documented, not fixed)

* An engine that swallows `CancelledError` and keeps running cannot be interrupted (same as C2).
* No batch-level per-item timeout; termination of one item relies on the C2 per-source total deadlines. A user-supplied
  engine that never returns would hold its slot.
* `apply_retry` cannot tell apart a retry from a *different* batch that has identical failed indices, numbers and
  generation. It rejects every mismatch it can observe.
* `BatchItemResult.aggregation_result` carries the full `AggregationResult` **including its execution traces**.
  C3 said C2-L2 (the public trace model permits states the engine never produces) should be re-evaluated *before any
  batch API exposes traces to wider callers*; C4 keeps that finding **LOW / DEFERRED** because it neither reads nor
  relies on trace invariants, but flags that the trigger condition arguably now exists — reviewer's call.
* Results are in memory only.

## Backlog carried forward (nothing below is fixed by C4)

* **C3-N1 — OPEN / LOW.** Primary-gate anti-rerun / set-binding guard is procedural, not globally enforced.
  **Before any future reuse of `tools/run_50id_coverage_gate.py`: pin the expected set path/blob, and detect an existing
  Primary through *committed* evidence, not only the supplied `--out-dir`.** The frozen C3 runner and evidence were not touched.
* C3-N2 LOW (evidence set hash depends on working-tree line endings) · C3-N3 LOW (attempt-1 pool traceability incomplete) ·
  **C3-N4 LOW** — the 50-ID acceptance population is torrent-indexed / first-page prefix sampled; any "98%" means
  **98% aggregate union coverage on the frozen C3 50-ID acceptance population**, never FC2-catalogue coverage.
* P2-R-05 LOW · P2-R-06 LOW · P2-R-07 partially mitigated LOW · P2-R-10 LOW · C2-L2 LOW / DEFERRED (see above) ·
  F3 DEFERRED · F5 DEFERRED · F4 CLOSED.

**F4 for the new package:** module discovery in `tests/contract/test_core_independent_of_amane.py` is `rglob`-derived,
so all five `batch/*.py` files were already covered by both the static AST scan and the blocked-import scan without an
edit; C4 adds explicit assertions that they are (so the package cannot become a blind spot) and a test that runs a real
batch (scheduler + retry + merge) while any `amane` import would raise.

## Not started

Circuit breaker (C5) · per-host limiter (C5) · persistence / DB · NFO writer · image downloader · filesystem
rename/move · Amane adapter · GUI · final 500-item failure-injection acceptance · any live batch scrape.

READY FOR PHASE 3 C4 INDEPENDENT REVIEW
