# PHASE1_R2_HANDOFF.md

```text
Phase: Phase 1 R2 — Incremental Closure Fix (R2-01 / R2-02)

Previous Reviewed-Failed R1 Code Head:
051d6c9a6d6279cf94c3d7323ee1ec2630ca04f8

Previous R1 Docs Head:
83158027bc5dbc11e35cbecfaf2ba98ee809dffd

R2 Fix Base:
83158027bc5dbc11e35cbecfaf2ba98ee809dffd

R2 Code Review Candidate:
090e9b7f19a6268c5cb8a95f9a2b2cdbb2b853c9

Current Docs Head:
reported externally after this docs commit
```

## Closure claims

### R2-01 (R1 incremental review finding F1 — PARTIAL: `Iterable` accepted where `Sequence[str]` was the intended contract)

**Root cause fixed, not patched around.** `_coerce_str_tuple` in
`fc2_metadata_core/models/metadata.py` previously accepted any
`collections.abc.Iterable` after excluding `str`/`bytes`. That let a
`dict` through (Python iterates a `dict` over its keys, so
`actors={"Alice": 1, "Bob": 2}` silently became `("Alice", "Bob")` with no
error, discarding the values entirely) and let a `set`/`frozenset` through
(iterable but unordered, so the resulting tuple's element order depended
on hash seed / insertion history rather than caller intent).

The accepted input contract for the seven sequence fields
(`actors`/`tags`/`poster_urls`/`thumb_urls`/`fanart_urls`/`extrafanart`/
`source_urls`) and for each `field_sources` value is now frozen as
`collections.abc.Sequence[str]` specifically:

- `list[str]` / `tuple[str, ...]` / any genuine `Sequence`: **accepted**,
  snapshotted to `tuple[str, ...]`, order preserved exactly.
- `str` / `bytes`: **rejected** (unchanged from R1).
- `Mapping` (`dict` and friends): **rejected explicitly** with its own
  check, even though a `dict` already fails the `Sequence` check on its
  own — kept as an explicit, clearly-worded rejection reason and as
  defense in depth against a hypothetical type registered as both.
- `set` / `frozenset`: **rejected**. Deliberately *not* sorted-and-accepted
  — this project's decision is that the Core must not invent an ordering
  on the caller's behalf, since field order may carry source/display
  meaning.
- generator / iterator / any other merely-`Iterable`, non-`Sequence`
  object: **rejected before being consumed at all** — a one-shot iterable
  is never touched by this check, so there is no risk of partial
  consumption or a mid-stream exception from something that was never a
  legal input in the first place.

`field_sources` values go through the exact same `_coerce_str_tuple`
helper (no separate/divergent logic), so the same rules apply uniformly —
this was a single shared root cause, fixed in one place.

### R2-01 regression tests

`tests/unit/core/test_metadata.py::TestSequenceContractRejectsNonSequenceIterables`:
- `test_original_r1_reviewer_reproduction_dict_as_actors_is_rejected` — the
  exact `actors={"Alice": 1, "Bob": 2}` reproduction.
- `test_original_r1_reviewer_reproduction_set_as_actors_is_rejected` /
  `..._frozenset_as_actors_is_rejected` — the exact set/frozenset
  reproductions.
- `test_original_r1_reviewer_reproduction_generator_as_actors_is_rejected`
  — uses a generator that records whether its body ever ran; asserts the
  body was never executed (rejected before consumption).
- `test_list_and_tuple_are_still_accepted_with_stable_order` — positive
  control, order preserved exactly.
- `test_dict_set_frozenset_generator_rejected_for_every_sequence_field` —
  parametrized across all seven sequence fields.
- `test_field_sources_value_rejects_mapping_as_sequence` /
  `..._rejects_set` / `..._rejects_frozenset` / `..._rejects_generator` —
  the same four illegal shapes as a `field_sources` value.
- `test_field_sources_value_accepts_list_with_stable_order` — positive
  control for `field_sources`.

### R2-02 (a misbehaving *accepted* Sequence must not leak its exception)

**Root cause fixed, not patched around.** Restricting the input type to
`Sequence` does not guarantee a well-behaved implementation — a custom
`Sequence` subclass could still raise mid-iteration (e.g. a broken
`__getitem__`). `_coerce_str_tuple` now wraps the element-reading loop in
`try/except`: our own element-type `MetadataContractError` is re-raised
unchanged (`except MetadataContractError: raise`, checked first so it is
never caught by the broader handler below it), while any other exception
raised while reading an accepted `Sequence` is caught and re-raised as
`MetadataContractError` with the original chained via
`raise MetadataContractError(...) from exc`.

### R2-02 regression tests

`tests/unit/core/test_metadata.py::TestBrokenAcceptedSequenceIsWrapped`,
using a `_BrokenSequence(collections.abc.Sequence)` test double whose
`__getitem__(0)` returns `"Alice"` and `__getitem__(1)` raises
`RuntimeError("boom")`:
- `test_broken_sequence_raises_metadata_contract_error_with_chained_cause`
  — asserts `MetadataContractError` is raised and its `__cause__` is the
  original `RuntimeError` with the original message.
- `test_broken_sequence_is_not_a_bare_runtime_error` — asserts the raw
  `RuntimeError` never propagates as-is.
- `test_broken_sequence_in_field_sources_value_is_also_wrapped` — same
  double used as a `field_sources` value.
- `test_own_element_type_error_is_not_double_wrapped` — asserts that our
  own `MetadataContractError` (from `actors=[123]`) has `__cause__ is
  None`, i.e. it was re-raised unchanged, not wrapped a second time by the
  broken-sequence handler.

## R1-02 preservation evidence

R1-02 (deep immutability, `SourceResult` lifetime invariant, caller-owned
alias isolation) was **not modified** in this round:
`fc2_metadata_core/models/source_result.py` is untouched (see Files
changed below — it does not appear in this commit's diff at all). All
pre-existing R1-02 regression tests were re-run and continue to pass
unchanged:

```text
tests/unit/core/test_metadata.py::TestImmutability             (7 tests, all PASSED)
tests/unit/core/test_metadata.py::TestCallerOwnedInputAliasSafety (4 tests, all PASSED)
tests/unit/core/test_source_result.py::TestSuccessLifetimeInvariant (5 tests, all PASSED)
tests/unit/core/test_source_result.py::TestPartialFailureLifetimeInvariant (2 tests, all PASSED)
tests/unit/core/test_source_result.py::TestCallerOwnedAliasSafetyThroughSourceResult (2 tests, all PASSED)
```

`NormalizedMetadata` was not reverted to mutable at any point; the fix is
purely in what is *accepted* as valid input before the existing
tuple/`MappingProxyType` snapshotting runs.

## Files changed

Diff range `83158027` → `090e9b7` (3 files modified, 0 added/removed):

```text
fc2-organizer/docs/specifications/FC2_METADATA_CORE_CONTRACT.md   (modified: +§2.1a, updated §2.1 table, revision note)
fc2-organizer/src/fc2_metadata_core/models/metadata.py            (modified: _coerce_str_tuple tightened to Sequence + exception wrapping, module docstring)
fc2-organizer/tests/unit/core/test_metadata.py                    (modified: +2 new test classes, +Sequence import)
```

`models/source_result.py`, `normalize/fc2_number.py`, `errors/__init__.py`,
`tests/unit/core/test_source_result.py`,
`tests/unit/core/test_normalize_fc2_number.py`, and
`tests/contract/test_core_independent_of_amane.py` are **untouched** — R2
only closes R2-01/R2-02.

## Exact commands

```bash
cd fc2-organizer
python3 --version
# Python 3.11.15

python3 -m pytest --collect-only -q
# 167 tests collected in 0.03s

python3 -m pytest -v
# ... 167 passed in 0.14s

python3 -m pytest -q
# 167 passed in 0.15s
```

R2-specific new tests run in isolation:

```bash
python3 -m pytest tests/unit/core/test_metadata.py -v \
  -k "TestSequenceContractRejectsNonSequenceIterables or TestBrokenAcceptedSequenceIsWrapped"
# 21 passed in 0.04s
```

Full F-02/F-03/R1-02/contract regression re-check:

```bash
python3 -m pytest tests/unit/core/test_normalize_fc2_number.py -q
# 41 passed in 0.04s

python3 -m pytest \
  tests/unit/core/test_metadata.py::TestImmutability \
  tests/unit/core/test_metadata.py::TestCallerOwnedInputAliasSafety \
  tests/unit/core/test_source_result.py::TestSuccessLifetimeInvariant \
  tests/unit/core/test_source_result.py::TestPartialFailureLifetimeInvariant \
  tests/unit/core/test_source_result.py::TestCallerOwnedAliasSafetyThroughSourceResult \
  -v
# 20 passed in 0.03s

python3 -m pytest tests/contract/ -q
# 11 passed in 0.03s
```

## Counts

```text
Python version: 3.11.15
Collected:      167
Passed:         167
Failed:         0
Skipped:        0
```

(Test count went from 146 after R1 to 167 in R2: +21 new tests, 0 removed,
0 pre-existing tests modified in `test_source_result.py`;
`test_metadata.py` gained an import and two new test classes.)

## Original reviewer reproduction

All four reproductions plus the broken-Sequence case were re-run directly
via a standalone script (not only pytest), per requirement:

```text
NormalizedMetadata(actors={"Alice": 1, "Bob": 2})
  -> MetadataContractError: actors must be an ordered Sequence[str], not a mapping

NormalizedMetadata(actors={"Alice", "Bob"})
  -> MetadataContractError: actors must be an ordered Sequence[str] (e.g. list or
     tuple), got <class 'set'>

NormalizedMetadata(actors=frozenset({"Alice", "Bob"}))
  -> MetadataContractError: actors must be an ordered Sequence[str] (e.g. list or
     tuple), got <class 'frozenset'>

NormalizedMetadata(actors=<generator>)  # body records "STARTED" on first next()
  -> MetadataContractError: actors must be an ordered Sequence[str] (e.g. list or
     tuple), got <class 'generator'>
  -> generator body executed: [] (confirmed never run)

NormalizedMetadata(actors=<Sequence test double raising RuntimeError("boom-in-sequence")
                            at index 1>)
  -> MetadataContractError: actors raised an unexpected error while being read:
     boom-in-sequence
  -> __cause__ = RuntimeError('boom-in-sequence')   (chained, not leaked raw)

Positive control:
NormalizedMetadata(actors=["Alice", "Bob"]).actors  == ("Alice", "Bob")
NormalizedMetadata(actors=("Alice", "Bob")).actors  == ("Alice", "Bob")
```

## Regression check

- Phase 0 **F-02** / **F-03**: unaffected — `normalize/fc2_number.py` not
  touched; all 41 `test_normalize_fc2_number.py` tests pass, including the
  two dedicated F-03 regressions.
- **R1-02**: unaffected — `source_result.py` not touched; all 20 relevant
  R1-02 lifetime/immutability/alias tests re-run and pass (see above).
- `tests/contract/test_core_independent_of_amane.py`: unaffected, all 11
  tests pass — `fc2_metadata_core` still imports and runs fully with
  `amane` import blocked at runtime.
- 7-state `SourceStatus` vocabulary, minimum-success definition, and all
  other Phase 1/R1 contract surfaces: unchanged.
- No new blocking regression identified.

## Known limitations

1. The rejection error message for `set`/`frozenset`/generator/other
   non-`Sequence` values is a single shared message
   ("must be an ordered Sequence[str] ...") rather than a distinct message
   per rejected kind; the `Mapping` case does get its own distinct message.
   This is a minor diagnostics-quality trade-off, not a contract gap — the
   exception type and the fact of rejection are what matter for the domain
   boundary.
2. `_BrokenSequence`'s misbehavior is deliberately simple (raises on the
   second element read); a `Sequence` that behaves inconsistently between
   `__len__` and `__getitem__` in more exotic ways is not separately
   exercised, since the wrapping behavior (any exception during the read
   loop other than our own `MetadataContractError` gets wrapped) does not
   depend on which particular inconsistency triggers it.
3. F3/F4/F5 remain deliberately deferred (see below), unchanged from R1.

## Deferred non-blocking

```text
F3
F4
F5
```

Not part of the R2 Required Closure Set (`R2-01`, `R2-02` only). Per
instruction, must still be closed no later than before Phase 5
integration. `tests/contract/test_core_independent_of_amane.py`'s
`CORE_MODULES` discovery mechanism and the Amane-installed-environment
assertion were **not** touched in this round.

## Phase 2 NOT started
