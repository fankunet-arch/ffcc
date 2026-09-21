# PHASE3_C4_R1_HANDOFF.md

```text
Phase: Phase 3 / C4-R1 — Incremental Closure Round

Original C4 Base:
03d62702b59a6736a858081bc1e7774d6edb29af

Reviewed-Failed C4 Code Head:
e633b403c0a420d033a6bf9289bdd0d249048368

C4 Docs Head / C4-R1 Base:
adbf56408db2d89b0db7e111f4bdf27e6b500d41

PHASE3_C4_R1_CODE_HEAD (code is FROZEN):
d28e500db57149f03e43746d9f5685fb0b9fac2e

PHASE3_C4_R1_DOCS_HEAD:
the commit "docs(review): add Phase 3 C4 R1 handoff" whose parent is the R1 Code Head above and whose only
change is this file (diff R1_CODE_HEAD..R1_DOCS_HEAD). A commit cannot contain its own hash, so it is identified
by that rule and reported in the hand-back message.

Branch:
claude/phase-0-amane-integration-fnvhpq   (normal fast-forward pushes; no reset / rebase / amend / squash / force;
                                           the original C4 history is intact)

Python: 3.12.10
```

**Not a PASS / CLOSED declaration.** This is a candidate for the C4-R1 independent closure review. C5 is **NOT
STARTED** and is not unlocked by this document.

Review range: `git diff adbf564 d28e500` — 9 files: `batch/{__init__,models,retry,scheduler}.py`, the batch contract
spec, one new test file (`test_batch_r1_closure.py`) and three existing batch test files adapted to the new API.
`aggregation/**`, `sources/**`, `http/**`, `tools/**`, `docs/acceptance/**` and the frozen C3 evidence are **unchanged**
(diff empty). The scheduling architecture the reviewer already accepted — `min(M,N)` workers, bounded admission, stable
ordering, original-index duplicate identity, caller cancellation, same-loop fatal stop, the caller-cancel admission guard,
retry-only-FAILED, the generation model, the 100-item gate structure, the large-N architecture — was **not rewritten**.

## Tests

| | count |
|---|---|
| R1 base (`adbf564`) collected / passed | 1850 / 1850 |
| R1 Code Head (`d28e500`) collected | **1927** |
| passed / failed / skipped | **1927 / 0 / 0** (`-v` and `-q`, both) |
| new tests | 77 = 73 in `tests/unit/batch/test_batch_r1_closure.py` + 4 in `test_batch_models.py` |

Commands on the frozen tree: `python --version`, `python -m pytest --collect-only -q`, `python -m pytest -v`,
`python -m pytest -q`. No timing failure occurred in any full run this round (the pre-existing C2 wall-clock test
`test_17_total_deadline…` passed every time). Order-independence was re-checked (batch tests before and after
`tests/contract`, which purges `sys.modules`).

## C4-R1-01 — ordinary-`Exception` metadata extraction must not become a batch fatal (MEDIUM)

* **Root cause.** `_type_name(obj)` read `type(obj).__name__` and caught only `Exception`. A hostile *metaclass*
  `__name__` property on an ordinary exception class could raise `KeyboardInterrupt` / `SystemExit` / `GeneratorExit` /
  a custom `BaseException` from inside `_run_item`'s `except Exception` block; that escaped as a `BaseException`, the
  worker treated it as fatal, and one ordinary item failure aborted the whole batch. (The same shape also existed for
  `isinstance(candidate, AggregationResult)`, which consults an engine-returned object's `__class__`.)
* **Change.** `_type_name` now runs **no caller-controlled code** and cannot raise: `type(obj)` (never consults
  `obj.__class__`) → a class whose metaclass is not plain `type` is untrusted → `UnknownType`; otherwise the name is read
  through `type.__dict__["__name__"].__get__(cls, type)` (the C-level getter, bypassing any metaclass property) and is
  used only if it is an **exact** `str`, an identifier, ≤ 128 chars. The engine result is checked with
  `type(candidate) is AggregationResult`. Nothing calls `str(exc)`, `repr(exc)`, `exc.args` or touches the traceback.
  `BatchItemResult.error_type` additionally requires an exact `str`.
* **Tests** (`test_batch_r1_closure.py`): ordinary `Exception` whose metaclass `__name__` raises
  `RuntimeError` / `KeyboardInterrupt` / `SystemExit` / `GeneratorExit` / custom `BaseException` → `FAILED`,
  `ENGINE_EXCEPTION`, `error_type == "UnknownType"`, siblings continue, the batch returns normally, the hostile code never
  ran (a shared `HOSTILE` log asserted empty by an autouse fixture), no secret text, weakref-proved no exception object
  retained; engine result with a hostile `__class__` property → `RESULT_CONTRACT_MISMATCH` (×5 raisers); `_type_name`
  totality over the same five raisers, ordinary names, over-long / non-identifier names, a `str`-subclass `__name__` whose
  `isidentifier`/`__str__`/`__len__` would run, and an `ABCMeta` class.
* **Closure claim.** No class metadata or return-value metadata can execute caller code on the item-failure path, so
  an ordinary item failure can no longer be escalated to a batch fatal.
* **Design trade-off, stated.** A class whose metaclass is not plain `type` (hostile, but also `ABCMeta`) is reported as
  `UnknownType` rather than by its real name — deliberately conservative; the descriptor read would already be safe, but
  the task text asks for a *safe fallback* for hostile metadata, and no diagnostic value is lost that matters here.

## C4-R1-02 — the fatal carrier must be metadata-free (MEDIUM)

* **Root cause.** `_FatalSignal.__init__` called `super().__init__(type(original).__name__)`. A fatal `BaseException`
  with a hostile metaclass `__name__` therefore raised *from the carrier*, replacing the real fatal with a different
  exception.
* **Change.** `_FatalSignal` is `__slots__ = ("original",)` and `__init__` is `super().__init__(); self.original =
  original` — it reads nothing from the object.
* **Tests.** carrier direct: `.original is` the object and `.args == ()` (×5 raisers); end to end for a fatal whose
  hostile metadata raises `RuntimeError`/`KeyboardInterrupt`/`SystemExit`/`GeneratorExit`/custom, both serially and with
  four blocked siblings: `caught is original`, no `ExceptionGroup`/`BaseExceptionGroup`, no partial `BatchResult`, siblings
  cancelled **and awaited**, nothing admitted after the fatal, no orphan task, scheduler reusable (a healed engine runs a
  fresh batch); plus the same-loop-iteration race (one event wakes two workers, the first raises the hostile fatal, the
  second must not admit item 2) ×5 raisers.
* **Closure claim.** Whatever a fatal exception's class metadata does, the caller receives that very object.

## C4-R1-03 — retry lineage (LOW)

* **Root cause.** `apply_retry` could only compare *shape* (generation, failed indices, numbers). A retry from batch A
  was accepted by any same-shaped batch B.
* **Change (not "more shape comparison").** `BatchLineage(token)`: an opaque, immutable, **value-compared** identity
  (128 random bits as 32 hex chars, validated), created **once per `run()`**. `BatchResult.lineage` (default: a fresh one,
  so a hand-built result is its own batch) and `RetryBatchResult.lineage` (**required**, no default). `retry_failed` copies
  `previous.lineage`; `apply_retry` requires `retry.lineage == previous.lineage` (first check after the type checks) and
  gives the merged result `previous.lineage`, so the identity survives 0 → 1 → 2 → …. `lineage` is excluded from
  equality and `repr`. Duplicate identity is untouched (still the original index). **Contract statement:** it is an
  in-memory provenance token, not a persistence format; persisting/resuming needs a real batch id (recorded as C4-N1).
* **Tests.** two independent runs of the *same* input with the *same* failures (duplicates included): everything the old
  check could see is asserted identical (failed indices, numbers, generation, retry indices) and `apply_retry(B, retry_A)`
  → `BatchRetryError("… lineage …")` while `apply_retry(A, retry_A)` is accepted; a second run of the same input on the
  same scheduler is a different lineage; lineage equality through primary → retry → merged → retry₂ → merged₂ and
  cross-chain rejection at generation 2; correct retry accepted and `previous` untouched; duplicate-number identity
  unchanged; a value-equal reconstructed lineage still matches while a hand-built same-item batch does not; model tests
  for `BatchLineage` validation / immutability / distinctness and the required `RetryBatchResult.lineage`.
* **Closure claim.** A retry can only be merged into the execution chain it was produced from, independent of how
  similar another batch looks. **Known limit:** a caller can forge a matching lineage by constructing
  `BatchLineage(token)` from a copied token; this guards accidents, not an adversary, by design (in-memory).

## C4-R1-04 — busy-first semantics and a non-hanging busy regression (LOW)

* **Root cause.** The busy check ran after argument preprocessing, so a busy `run(invalid)` answered
  `BatchInputError` and a busy `retry_failed(invalid)` answered `BatchRetryError`. The busy regression test also blocked
  forever on its gate if the guard was removed.
* **Change.** `run()` and `retry_failed()` start with `self._claim()` (raises `BatchBusyError` or sets the flag),
  and everything else — validation included — runs inside `try … finally: self._busy = False`. A rejected call never
  touches the active run's flag. Idle-scheduler validation errors are unchanged and leave the scheduler idle.
* **Tests.** `busy_probe`: hold one run open, fire eleven kinds of second call (valid run, empty run, dirty element, bare
  `str`, set, `None`, `str` subclass, valid retry, `None` retry, `object()` retry, `RetryBatchResult` retry) → each must be
  `BatchBusyError` with **zero** extra engine calls, the claim must still be held afterwards, the held run completes
  (no orphan). The probe cannot hang: only the held run's numbers are gated (a missing guard shows up as "returned"),
  the second call sits under `asyncio.timeout`, and release/await happen in `finally`. The original busy test in
  `test_batch_concurrency.py` got the same treatment. A self-test with `UnguardedScheduler` proves both broken-guard
  failure modes are **reported** (second call returns / second call would block → watchdog 0.2 s) with `leftover == []`.
* **Closure claim.** Busy-first is frozen in the contract (§2) and pinned; removing the guard now fails in ~5.6 s
  instead of hanging.

## C4-R1-05 — exact string elements (LOW)

* **Root cause.** `isinstance(element, str)` admitted `str` subclasses: error reporting could call a hostile
  `__repr__`, and a canonical-valued subclass instance flowed un-coerced into the engine and `BatchItemResult.number`.
* **Change (contract: reject, fail closed).** A batch element must satisfy `type(element) is str` (then the existing
  `require_canonical_number`). A subclass — canonical or not — is rejected with `BatchInputError`; none of its methods
  runs; it is reported by class name only (`<HostileStr>`); `_short` only ever `repr`s an exact `str`.
  `BatchItemResult.number` also requires an exact `str`. The documented upstream remedy is `str.__str__(x)` (exact `str`
  copy, calls no override).
* **Tests.** hostile subclass (every method records and raises `RuntimeError` / `KeyboardInterrupt` / `SystemExit` /
  `GeneratorExit` / custom) × canonical and invalid values → `BatchInputError`, message names `<HostileStr>`, no
  `SECRET` text, zero engine calls, hostile log empty; benign subclass rejected even when canonical; only exact `str`
  objects reach the engine and results; the `str.__str__` remedy works; 200 hostile invalid elements keep the message
  bounded (`200 element(s)`, < 2 KB); model-level exact-`str` checks.
* **Closure claim.** No caller-controlled string subclass can carry `__repr__` / `__str__` / slicing / type metadata into the
  batch core.

## Mutation check

Applied one at a time to pristine sources (timeouts 120 s, durations measured); all **killed**:
restore the `except Exception`-only `_type_name` · drop the untrusted-metaclass check · `isinstance` on the engine result ·
reintroduce `type(original).__name__` in the carrier · remove the lineage check · `retry_failed` mints a fresh lineage ·
the merged result mints a fresh lineage · busy check moved after validation in `run()` · … in `retry_failed()` · **remove
the busy guard entirely → fails in 5.6 s, no hang** · `isinstance(element, str)` in `validate_batch` (also caught by the
model's exact-`str` check behind it) · `_short` reprs `str` subclasses. The 11 original C4 mutants (driver-cancel check,
`stopping` flags, task-per-item, `M+1` workers, swallowed self-cancel, leaked exception text, completion-order results,
dedupe, retry-PARTIAL, busy guard) were re-run and are still all killed. Hostile raisers are parametrised with
`RuntimeError` first so a regression fails as a clean assertion instead of aborting the test runner. The mutation
scripts are job scratch and are not committed.

## Offline gates re-run before the freeze (unchanged results)

* **100-item stage gate** (`test_batch_stage_gate_100.py`, untouched): PASS — 100 accounted once, input order, peak ==
  limit, isolation, exact failed-subset retry, two retry rounds, zero orphan tasks.
* **Large-N**, measured by a one-off script on the frozen tree: `N = 10,000`, `M = 4` → 10,000 accounted, 10,000 unique
  indices, stable order, **peak 4**, max live tasks sampled inside the engine **5** (1 caller + 4 workers), 0 orphans.
  Barrier measurement (4 calls held open): live tasks **6** (= `asyncio.run` main task + `run()` task + 4 workers), live
  `aggregate` coroutine objects **4**, items admitted **4**; the two control tests (task-per-item, N pre-built
  coroutines) still show ≥ 2000 live tasks / coroutines through the same measurement.

## Carried forward — not fixed by R1

* **C2-L2 — LOW / OPEN.** **The trigger has occurred**: `BatchItemResult.aggregation_result` transparently exposes the
  `AggregationResult` including its `source_execution_traces` (the batch layer never reads or relies on them; R1 does not
  touch `SourceExecutionTrace`). It must be **closed** — tighten the `SourceExecutionTrace` validators, or freeze an
  explicit "trusted-producer diagnostics" statement — **before any of**: (1) persistence / report / UI / NFO / CLI
  serialises or displays traces; (2) C5's circuit breaker / per-host limiter reads trace fields; (3) production accepts a
  non-`MultiSourceEngine` producer whose traces are not trusted. If C5 never reads traces it may keep carrying it.
* **C3-N1 OPEN LOW** — before any future reuse of `tools/run_50id_coverage_gate.py`: pin the expected set path/blob **and**
  detect an existing Primary through *committed* evidence, not only the supplied `--out-dir`. · **C3-N2 LOW** (evidence set
  hash depends on working-tree line endings) · **C3-N3 LOW** (attempt-1 pool traceability incomplete) · **C3-N4 LOW**
  (the 50-ID acceptance population is torrent-indexed / first-page prefix sampled; any "98%" means **98% aggregate union
  coverage on the frozen C3 50-ID acceptance population**, never FC2-catalogue coverage).
* P2-R-05 LOW · P2-R-06 LOW · P2-R-07 partially mitigated LOW · P2-R-10 LOW · F3 DEFERRED · F5 DEFERRED · F4 CLOSED ·
  **C4-N1** (the lineage token is in-memory only; design a real batch id before results are persisted or resumed).
* Residual observation, out of R1 scope: `validate_batch`'s *container* checks (`isinstance(numbers, …)`, `tuple(numbers)`)
  still consult the caller's own container object; a hostile container raises from `run()` before any engine call, which
  is a caller-argument error, not an item failure being escalated.

## Not started

Circuit breaker (**C5 NOT STARTED**) · per-host limiter · persistence / DB · NFO writer · image downloader · filesystem
rename/move · Amane adapter · GUI · final 500-item failure-injection acceptance · any live batch scrape.

READY FOR C4-R1 INDEPENDENT CLOSURE REVIEW
