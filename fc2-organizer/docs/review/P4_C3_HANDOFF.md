# Phase 4 / P4-C3 Handoff -- Metadata Publication Boundary Hardening

```text
Phase        = 4
Package      = P4-C3
Role         = Developer
Branch       = claude/phase4-c3-publication-boundary
```

## 1. Coordinates

```text
Frozen Base                  = b44ca7a1a3ca70dddf8686d9d14a98d52b481b82
P4-C3 Code Review Candidate  = 1e66ab40dc66c5ea6edb6f623b15d1f6e4fe817f
P4-C3 Docs Head              = <this commit; see `git log -1 -- fc2-organizer/docs/review/P4_C3_HANDOFF.md`>
Remote Head                  = <= Docs Head after push of this commit>

Code Review Range: b44ca7a1a3ca70dddf8686d9d14a98d52b481b82..1e66ab40dc66c5ea6edb6f623b15d1f6e4fe817f
Docs Review Range: 1e66ab40dc66c5ea6edb6f623b15d1f6e4fe817f..<Docs Head>
```

Verified before any change: `git fetch --all --tags`;
`origin/claude/phase4-c2-organize-plan` == `b44ca7a1a3ca70dddf8686d9d14a98d52b481b82`;
working tree clean (only untracked `.claude/`); new branch
`claude/phase4-c3-publication-boundary` created from that exact commit, developed in an
isolated worktree. No rebase / amend / squash / force push.

The Code Review Candidate contains code, tests and the frozen contract
(`PHASE4_PUBLICATION_BOUNDARY_CONTRACT.md`). The Docs Head commit contains only this file.

## 2. Type

**NEW PACKAGE** (`fc2_organizer.publication`) + two authorised minimal fixes in
`fc2_metadata_core` (C2-L2 trace validators, P2-R-10 JavDB decode) + two one-line
package-set scope-guard updates.

## 3. Changed files (Code Review Candidate `1e66ab4`, 19 files, +2166 / -7)

New (15):
```text
fc2-organizer/docs/specifications/PHASE4_PUBLICATION_BOUNDARY_CONTRACT.md
fc2-organizer/src/fc2_organizer/publication/__init__.py
fc2-organizer/src/fc2_organizer/publication/boundary.py
fc2-organizer/src/fc2_organizer/publication/errors.py
fc2-organizer/src/fc2_organizer/publication/models.py
fc2-organizer/tests/contract/test_publication_architecture.py
fc2-organizer/tests/unit/aggregation/test_agg_c2_l2_trace_hardening.py
fc2-organizer/tests/unit/publication/__init__.py
fc2-organizer/tests/unit/publication/_builders.py
fc2-organizer/tests/unit/publication/_guards.py
fc2-organizer/tests/unit/publication/test_publication_boundary.py
fc2-organizer/tests/unit/publication/test_publication_models.py
fc2-organizer/tests/unit/publication/test_publication_no_side_effects.py
fc2-organizer/tests/unit/publication/test_publication_synthetic_gate.py
fc2-organizer/tests/unit/sources/adapters/test_javdb_p2_r10_single_unescape.py
```

Modified (4):
```text
fc2-organizer/src/fc2_metadata_core/aggregation/models.py      +42 -1  (C2-L2, section 9)
fc2-organizer/src/fc2_metadata_core/sources/adapters/javdb.py  +3 -4   (P2-R-10, section 10)
fc2-organizer/tests/contract/test_discovery_architecture.py    +1 -1   (package set, section 12)
fc2-organizer/tests/contract/test_planning_architecture.py      +1 -1   (package set, section 12)
```

Not touched: aggregation engine / execution / retry / merge, resource_control, batch,
HTTP transport, other adapters, discovery and planning production code,
`fc2_organizer/__init__.py`, Amane.

## 4. Publication API

```python
from fc2_organizer.publication import prepare_publication
prepare_publication(plan: OrganizePlan, aggregation_result: AggregationResult) -> PublicationRecord
```

Checks in deterministic order: input types -> status -> metadata minimum success ->
identity. First failure raises; nothing is repaired or chosen.

## 5. PublicationRecord

```python
@dataclass(frozen=True, slots=True)
class PublicationRecord:
    plan: OrganizePlan
    metadata: NormalizedMetadata
    aggregate_status: AggregateStatus   # SUCCESS | PARTIAL
    # read-only property: number -> plan.canonical_number
```

Model-level invariants (hand-built records included, `PublicationContractError`):
types; status in `{SUCCESS, PARTIAL}`; `metadata.meets_minimum_success()`;
`metadata.number` exact `str` == `plan.canonical_number`. No serializer / renderer
methods.

## 6. Identity correlation (P4-C2 metadata identity gap)

`plan.canonical_number == aggregation_result.number == aggregation_result.metadata.number`,
all exact `str`, else `PublicationIdentityMismatchError`. No "winner" is picked. Re-checked
even though `AggregationResult` enforces `metadata.number == number` itself (tests use
`object.__new__`-bypassed aggregates to prove the boundary does not rely on it). A `str`
subclass with a lying `__eq__` is rejected.

```text
P4-C2 metadata identity gap = CLOSED AT P4-C3 BOUNDARY
```

## 7. SUCCESS / PARTIAL / FAILED

SUCCESS -> record (status SUCCESS). PARTIAL -> record (status stays PARTIAL).
FAILED -> `AggregationNotPublishableError` (also for a bypassed FAILED result that
carries metadata, and for any non-`AggregateStatus` value).
Minimum success only via `NormalizedMetadata.meets_minimum_success()`
(`InvalidPublicationMetadataError` otherwise).

## 8. Diagnostic exclusion

The record's actual object graph (slots, `__dict__`, tuples, mappings; walked, not
name-checked) contains no `AggregationResult`, `SourceResult`, `SourceExecutionTrace`,
`SourceAttempt` or exception object, no `error_detail` / `error_kind` / `args` /
traceback / response / headers / cookie attribute, no string containing the input's
`error_detail` text, and does not reference the input aggregate, its results or traces.
Inputs deliberately carry traces and a sensitive-looking `error_detail`
(`cookie=... Authorization: Bearer ... <html>`), and a companion test proves the walker
finds all of them in the raw aggregate (non-vacuous). Error messages carry only
canonical numbers / enum values / type names; foreign objects are rendered as
`<TypeName>` without calling `repr`; no error is chained.

## 9. C2-L2 closure details

Closure method: **tighten validators** (`aggregation/models.py`); engine not modified.
Derived from `execution.py`: `completed=False` is only written by `_run_source`'s deadline
path as `NETWORK_ERROR/SOURCE_DEADLINE`; another attempt / backoff only happens when
`RetryPolicy.should_retry` is true, i.e. `error_kind in retryable_error_kinds ⊆
RETRY_ELIGIBLE_KINDS`.

| historical engine-impossible state | now |
|---|---|
| incomplete SUCCESS attempt | rejected by `SourceAttempt` (`_check_incomplete_attempt`) |
| incomplete non-`SOURCE_DEADLINE` attempt (`PARSE_ERROR`, `NOT_FOUND`, `CONNECTION_ERROR`, every other allowed pair) | rejected by `SourceAttempt` |
| retry after `NOT_FOUND` (and after any non-retry-eligible kind incl. `SUCCESS`, `BLOCKED`, `RATE_LIMITED`, `PARSE_ERROR`, `SOURCE_DEADLINE`, `CIRCUIT_OPEN`) | rejected by `SourceExecutionTrace` (`_check_retry_shape`) |
| deadline during backoff after a terminal `SUCCESS` (or any non-retry-eligible outcome) | rejected by `SourceExecutionTrace` |

Still accepted, pinned against the **real** `execute_sources_traced`: single SUCCESS /
NOT_FOUND / BLOCKED / PARSE_ERROR; retryable -> SUCCESS; retryable -> NOT_FOUND;
retryable -> final failure; 3-attempt chain; narrowed-policy stop; deadline during
attempt 1; deadline during a retry attempt; deadline during retry backoff; real
`CIRCUIT_OPEN` zero-attempt trace via a `SourceResourceGovernor`. The full pre-existing
Phase 3 aggregation / resource-control / batch suites (which construct every engine
trace through the hardened `__post_init__`) are green.

Mutation-style proof: `test_mutation_reverting_the_c2_l2_checks_makes_each_invalid_state_constructible_again`
monkeypatches the two new module-level checks back to no-ops; each of the four
historical invalid states then constructs, i.e. the rejections are due to the new logic.

```text
C2-L2 = CLOSED (implemented; pending independent review)
```

P2-R-07 remains carried; the contract (section 14) records that any future diagnostics
publication must use the engine-measured `SourceAttempt.elapsed_ms`, never an adapter
failure's `elapsed_ms == 0`. Traces are **not** added to `PublicationRecord`.

## 10. P2-R-10 closure details

`javdb.py`: `clean_text(html.unescape(attrs.get("title", "")))` ->
`clean_text(attrs.get("title", ""))` (unused `import html` removed). Results:
`A &amp; B` -> `A & B`; `A &amp;amp; B` -> `A &amp; B`; `&#38;amp;` -> `&amp;`;
`&amp;lt;tag&amp;gt;` -> `&lt;tag&gt;`. Pinned unchanged: text-title fallback (single
decode), whitespace collapse/trim, text-title tag stripping, exact-number matching with
near misses, near-miss-only `NOT_FOUND`, empty-title `PARSE_ERROR`; all existing JavDB
suites (incl. adversarial / total-cost) green. A test also shows the old formula yields
`A & B` for the nested case. P2-R-05 / 06 / 07 untouched.

```text
P2-R-10 = CLOSED (implemented; pending independent review)
```

## 11. No-filesystem / no-network evidence

* `test_prepare_publication_runs_with_every_filesystem_and_network_api_trapped` (x3 kinds)
  and `test_rejections_also_run_...`: `os.stat/lstat/listdir/scandir/open/mkdir/makedirs/
  rename/replace/remove/unlink/rmdir/removedirs/chmod/utime/symlink/link/access/readlink/walk`,
  `os.path.exists/lexists/isfile/isdir/islink/realpath/getsize/getmtime/samefile`,
  `pathlib.Path.exists/stat/lstat/resolve/is_file/is_dir/open/read_*/write_*/mkdir/touch/
  rename/replace/unlink/rmdir/iterdir/glob/rglob/samefile/symlink_to`, `shutil.*`,
  `builtins.open`, `io.open`, `socket.socket/create_connection/getaddrinfo`,
  `urllib.request.urlopen`, `httpx.Client/AsyncClient.send/request` all trapped; the
  traps are shown effective by `test_traps_are_effective`.
* The whole 400-item synthetic gate runs under the same traps.
* Before/after filesystem snapshot unchanged; the plan's library root never created.
* Clock / `random` / `uuid` / `os.urandom` trapped: output still equal
  (`test_prepare_publication_uses_no_clock_random_or_uuid`).
* Static: the publication source makes no I/O-style call and imports only
  `__future__`, `dataclasses` and the three allowed project packages.

## 12. Architecture boundary

`tests/contract/test_publication_architecture.py`: allowed imports only
(`fc2_organizer.planning`, `fc2_metadata_core.aggregation`, `fc2_metadata_core.models`
packages, own modules, `__future__`, `dataclasses`); `errors.py` stdlib-only; no reverse
dependency from `fc2_metadata_core` / planning / discovery; `fc2_organizer/__init__.py`
does not import publication and `import fc2_organizer` does not load it; end-to-end run
with `amane` blocked on the meta path; Amane not installed; exactly
`{"discovery", "planning", "publication"}` subpackages.

Scope-guard edits: `test_discovery_architecture.py` and `test_planning_architecture.py`
each changed exactly one line, `{"discovery", "planning"}` ->
`{"discovery", "planning", "publication"}`. **Deviation note:** the brief named only the
discovery file for this update; the planning file carries the identical frozen
package-set assertion and would otherwise fail, so the same one-line update was applied
there. No forbidden-import guard in either file was changed.

## 13. Synthetic publication gate

`test_publication_synthetic_gate.py`: 400 distinct pairs (6-/7-digit numbers;
SUCCESS 134 / PARTIAL 266 via single-attempt, retried, NOT_FOUND, BLOCKED,
NETWORK_ERROR, PARSE_ERROR combinations; Unicode titles; collection/mapping metadata)
under filesystem/network traps: 400/400 accepted, second pass equal item by item, every
record frozen and diagnostic-free; 800/800 mismatches rejected (neighbour aggregate +
forged metadata number per item); 50/50 FAILED rejected. PASS.

## 14. Tests

Environment note: this host's shared pytest temp root (`pytest-of-Ctg/pytest-current`)
is permission-denied, so every run used `--basetemp` under the job's temp directory and
`-p no:cacheprovider`. Plain `python` resolves the packages to the main checkout via an
installed `.pth`; pytest's `pythonpath = ["src", "tests"]` makes it use this worktree's
`src` (the direct reproductions below used `PYTHONPATH=src`).

Baseline at Frozen Base `b44ca7a` (clean export): **2703 passed, 14 skipped, 0 failed**.

Targeted (on `1e66ab4`):
```text
python -m pytest tests/unit/publication tests/contract/test_publication_architecture.py \
  tests/unit/aggregation/test_agg_c2_l2_trace_hardening.py \
  tests/unit/aggregation/test_agg_low1_result_invariants.py \
  tests/unit/aggregation/test_agg_retry_execution.py \
  tests/unit/resource_control/test_rc_breaker_execution.py \
  tests/unit/sources/adapters/test_javdb_p2_r10_single_unescape.py \
  tests/unit/sources/adapters/test_adapter_javdb.py \
  tests/unit/sources/adapters/test_adapter_javdb_semantics.py \
  tests/unit/sources/adapters/test_javdb_total_cost.py -q
-> 411 passed, 0 failed, 0 skipped
```

Full suite (on `1e66ab4`): `python -m pytest -q` -> **2924 passed, 14 skipped, 0 failed**
(+221 new tests; P4-C1, P4-C2, Phase 3 aggregation / resilience / batch / resource
control and all source-adapter suites green). The 14 skips are the pre-existing
platform skips (POSIX-only path forms in planning tests; directory-symlink privilege in
one discovery test), identical to baseline.

Direct reproductions (`PYTHONPATH=src`):
```text
A  plan FC2-1234567 vs aggregate FC2-7654321 -> PublicationIdentityMismatchError (fail closed)
B  PARTIAL + valid metadata + matching plan  -> PublicationRecord(number=FC2-1234567, status=partial)
C  NOT_FOUND attempt then attempt 2           -> AggregationContractError
D  completed=False with PARSE_ERROR / NOT_FOUND / CONNECTION_ERROR / SUCCESS -> AggregationContractError (each)
E  JavDB title="A &amp;amp; B"                -> 'A &amp; B' (not 'A & B')
```

## 15. Known limitations

* `hash(PublicationRecord)` raises `TypeError` because `NormalizedMetadata` is
  unhashable (its mappings are `MappingProxyType`) -- the existing semantics, documented
  in contract section 11; equality is fully deterministic.
* The trace validators pin the engine's *shape* rules; they do not re-derive whether a
  final retryable failure with attempts remaining was stopped by a narrowed policy or a
  stale C5 admission (both legal and indistinguishable from the trace alone), nor
  `backoff_before_seconds` values against a policy (the trace does not carry the policy).
* `OrganizePlan.canonical_number` is still only non-empty-`str`-checked at the planning
  model layer; canonical validity at publication is guaranteed transitively (it must
  equal the minimum-success metadata number).

## 16. Carried findings

Closed by this package (pending independent review):
```text
P4-C2 metadata.number != canonical_number identity gap -- CLOSED AT P4-C3 BOUNDARY
C2-L2 -- CLOSED
P2-R-10 -- CLOSED
```

Still carried, unchanged:
```text
P4-C2-R1-02 -- LOW (bare "\\server" root)
OrganizePlan operation-graph model-level hardening
overwrite executor semantics -- frozen NEVER
extended Windows reserved-name edge cases
P4-C1-R-02, P4-C1-R-03, P4-C1-R-04, P4-C1-R-05
P2-R-05, P2-R-06, P2-R-07 (timing note recorded, contract section 14)
C3-N1, C3-N2, C3-N3, C3-N4, C4-N1, C4-R1-N1, C4-R1-N2, C4-R1-N3, F3, F5, C5-R1-L1
```

No new frozen gate was triggered by P4-C3.

## 17. git diff --check / status

```text
git diff --check b44ca7a1a3ca70dddf8686d9d14a98d52b481b82..1e66ab40dc66c5ea6edb6f623b15d1f6e4fe817f  -> clean
git status --porcelain (after the Docs Head commit)                                              -> empty
```

## 18. Status

```text
Independent Review: REQUIRED
P4-C3:   NOT CLOSED
Phase 4: NOT CLOSED
```

No later package (NFO renderer, image download, executor, CLI, persistence, Amane
adapter) was started.

---

# Final Closure -- P4-C3

```text
Phase:
4

Package:
P4-C3 Metadata Publication Boundary Hardening

Status:
CLOSED

Final Level:
Level 1 PASS

Final Reviewed Code Head:
1e66ab40dc66c5ea6edb6f623b15d1f6e4fe817f

Previous Docs Head:
3b16908a167259117140308f72e6310b216aea20
```

This section is appended by a docs-only final closure commit. Everything above it
is the unchanged developer handoff history. No code, test or contract file is
touched by this closure.

## Independent review evidence

```text
Independent Level 1 = PASS

Context Handshake = PASS
Scope = PASS

Publication boundary = PASS
Identity correlation = PASS
Diagnostic exclusion = PASS

P4-C2 metadata identity gap = CLOSED
C2-L2 = CLOSED
P2-R-10 = CLOSED

Targeted (reviewer's explicit review set):
246 passed / 0 failed / 0 skipped

Developer-equivalent targeted set:
411 passed / 0 failed / 0 skipped

Full Suite:
2924 passed / 14 skipped / 0 failed

Direct independent probes:
56 / 56 PASS

git diff --check:
clean
```

All blocking P4-C3 findings are closed.

P4-C3-R-01 and P4-C3-R-02 are explicitly carried as LOW / non-blocking.

## Closure targets

```text
P4-C2 metadata identity gap = CLOSED
C2-L2 = CLOSED
P2-R-10 = CLOSED
```

## New reviewer findings (carried)

```text
P4-C3-R-01
Severity: LOW
Status: CARRIED / non-blocking
```

Some test names cited in the contract / this handoff have drifted from the
actual pytest test names. The actual tests are still collected and run
normally by pytest, so correctness is not affected. This is a traceability /
documentation-quality issue. Not changed in this closure (no test or contract
edits).

```text
P4-C3-R-02
Severity: LOW
Status: CARRIED / non-blocking
```

The built-in positive controls of the publication no-side-effect tests do not
individually cover every trap category or every rejection path. The
independent reviewer additionally verified that all 11 trap categories are
genuinely effective and that all 6 rejection paths perform no I/O. Current
runtime behaviour is therefore correct; this is a test-strength /
future-regression-resistance issue. Not changed in this closure (no test edits).

## Carried debts

```text
P4-C3-R-01 = LOW / CARRIED / non-blocking
P4-C3-R-02 = LOW / CARRIED / non-blocking

P2-R-07 = CARRIED

P4-C2-R1-02 -- LOW
OrganizePlan operation-graph hardening
overwrite executor semantics = frozen NEVER
extended Windows reserved names

P4-C1-R-02..R-05

P2-R-05
P2-R-06
P2-R-07

C3-N1..N4
C4-N1
C4-R1-N1..N3

F3
F5
C5-R1-L1
```

C2-L2, P2-R-10 and the P4-C2 metadata identity gap are CLOSED and are no longer
carried.

## Future entry notes (not addressed by this closure)

```text
P2-R-07 remains LOW / CARRIED.
  Future diagnostics publication must use engine-measured
  SourceAttempt.elapsed_ms rather than assuming adapter failure
  SourceResult.elapsed_ms is a trustworthy elapsed duration.

OrganizePlan operation-graph hardening
  remains an executor-entry gate.

overwrite = NEVER
  remains a frozen global executor semantic.
```

## Scope of this closure

This closes **P4-C3** only. It does not close Phase 4 and does not start any
later package; each later package needs its own frozen contract and review cycle.

## Final status

```text
P4-C3: CLOSED
Phase 4: NOT CLOSED
Next Package: NOT STARTED
```
