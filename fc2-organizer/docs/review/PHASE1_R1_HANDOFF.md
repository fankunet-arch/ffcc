# PHASE1_R1_HANDOFF.md

```text
Phase: Phase 1 R1 — Incremental Closure Fix (R1-01 / R1-02)

Previous Reviewed-Failed Code Head:
1e2f4d753aad9050a79589776abda74f2e063e7b

Previous Docs Head:
30396dfefdd62aa4dbe3e9044c8ff056ac25c369

R1 Fix Base:
30396dfefdd62aa4dbe3e9044c8ff056ac25c369

R1 Code Review Candidate:
051d6c9a6d6279cf94c3d7323ee1ec2630ca04f8

Current Docs Head:
reported externally after this docs commit
```

## Closure claims

### R1-01 (reviewer F1 — NormalizedMetadata runtime contract / total predicate hole)

**Root cause fixed, not patched around.** `NormalizedMetadata.__post_init__`
now validates the runtime type of every field before the instance is
considered constructed:

- `number`/`title`/`studio`/`publisher`/`release`/`plot`: must be `str` or
  `None`.
- `runtime`: must be `int` or `None`, with `bool` explicitly excluded (a
  `bool` is an `int` subclass in Python but is not a legal runtime value
  here), and non-negative.
- `actors`/`tags`/`poster_urls`/`thumb_urls`/`fanart_urls`/`extrafanart`/
  `source_urls`: must be a sequence whose every element is `str`; a bare
  `str`/`bytes` value is explicitly rejected (not silently iterated
  character-by-character) and a non-iterable value is rejected.
- `external_ids`: must be a mapping of `str` key to `str` value.
- `field_sources`: must be a mapping of `str` key to a sequence of `str`.

Any violation raises `MetadataContractError` **at construction**, in
`fc2_metadata_core/models/metadata.py`. As a direct consequence,
`has_valid_canonical_number()`, `has_non_empty_title()`, and
`meets_minimum_success()` are now **total predicates**: for any instance
that was successfully constructed, they are guaranteed to return `bool` and
never raise `AttributeError`/`TypeError`/`KeyError`.

`SourceResult.__post_init__` now also validates that `metadata` is `None`
or an actual `NormalizedMetadata` instance, before touching
`metadata.meets_minimum_success()`. A caller passing e.g. `metadata=123` or
`metadata={"number": ..., "title": ...}` is rejected immediately with
`SourceResultContractError`, for every status (not only `SUCCESS`).

### R1-01 regression tests

`tests/unit/core/test_metadata.py`:
- `TestScalarTypeValidation` (incl. `test_original_f1_reproduction_title_int_is_rejected_at_construction`
  — the exact reviewer reproduction — and a parametrized check across all
  six scalar `str` fields).
- `TestCollectionTypeValidation` (parametrized across all seven sequence
  fields for non-`str` elements, plus bare-str-as-sequence, non-iterable,
  `external_ids` bad key/value/non-mapping, `field_sources` bad
  key/value-element/non-sequence-value).
- `test_meets_minimum_success_never_raises_for_any_constructed_instance`
  (totality check across a spread of constructed instances).

`tests/unit/core/test_source_result.py`:
- `TestMetadataTypeGuard` (incl.
  `test_original_f1_reproduction_int_metadata_is_rejected` — the exact
  reviewer reproduction on the `SourceResult` side — plus dict-metadata,
  wrong-type-metadata-on-a-failure-status, and none-metadata-still-ok
  cases).

### R1-02 (reviewer F2 — SourceResult lifetime invariant breakable through mutable metadata)

**Root cause fixed, not patched around; the rejected "document it as a
caveat" approach was not used.** `NormalizedMetadata` is now a **deeply
immutable value object**, not just a shallow `frozen=True` dataclass over
mutable containers:

- The dataclass is `frozen=True` — scalar (re)assignment raises
  `dataclasses.FrozenInstanceError` (a subclass of `AttributeError`).
- Every sequence field is snapshotted to a `tuple` in `__post_init__` —
  there is no `.append`/`.remove`/item-assignment available on the stored
  value at all (`AttributeError`/`TypeError` on attempt, not a documented
  "don't do this").
- `external_ids` and `field_sources` are snapshotted to
  `types.MappingProxyType` over a freshly built private `dict` copy — item
  assignment/deletion raises `TypeError`.
- `field_sources` values are themselves snapshotted to `tuple`, closing the
  nested-mutation path the reviewer specifically flagged
  (`field_sources["title"].append(...)`).
- Caller-owned input containers (`list`s, `dict`s passed to the
  constructor) are copied element-by-element at construction time, so
  mutating the caller's original object after construction cannot reach
  the already-built `NormalizedMetadata` (no aliasing).

Since `SourceResult` was already frozen and cannot have its `metadata`
field reassigned, and `NormalizedMetadata` can now not be mutated at any
depth through any public API, a constructed `SourceResult`'s invariants
(established once in `__post_init__`) now hold for the object graph's
**entire lifetime**, closing the gap the reviewer identified between
"true at construction" and "true forever."

`FC2_METADATA_CORE_CONTRACT.md` §2.3 formally withdraws the earlier Phase 1
HANDOFF's stated rationale for leaving `NormalizedMetadata` mutable
("Phase 3 might need incremental in-place merge") and freezes the
direction: Phase 3 aggregation must be functional/copy-on-write (read
immutable inputs, produce a new instance), never in-place mutation of a
published `NormalizedMetadata`.

### R1-02 regression tests

`tests/unit/core/test_metadata.py`:
- `TestImmutability` (scalar reassignment rejected; sequence fields stored
  as `tuple` and unmutable in place; `external_ids`/`field_sources` stored
  as `MappingProxyType` and unmutable; nested `field_sources` tuple values
  unmutable).
- `TestCallerOwnedInputAliasSafety` (mutating the original `list`/`dict`
  passed into the constructor, including a nested list inside
  `field_sources`, after construction does not affect the built instance).

`tests/unit/core/test_source_result.py`:
- `TestSuccessLifetimeInvariant` — builds a `SUCCESS` `SourceResult`, then
  attacks scalar, sequence, mapping, and nested `field_sources` mutation
  paths plus `metadata` field reassignment; asserts
  `result.metadata.meets_minimum_success()` is still `True` after every
  attempt, and that every attempt itself raised.
- `TestPartialFailureLifetimeInvariant` — parametrized over
  `PARSE_ERROR`/`INVALID_RESPONSE`; builds a result with partial metadata,
  attempts to mutate it into minimum-success, confirms the attempt fails
  and `meets_minimum_success()` remains `False`.
- `TestCallerOwnedAliasSafetyThroughSourceResult` — mutating the original
  `NormalizedMetadata` reference or its original input `list` after it was
  used to build a `SourceResult` cannot affect the result.

## Files changed

Diff range `30396df` → `051d6c9` (5 files modified, 0 added/removed):

```text
fc2-organizer/docs/specifications/FC2_METADATA_CORE_CONTRACT.md   (modified: +§2.1/§2.2/§2.3, updated §3 table)
fc2-organizer/src/fc2_metadata_core/models/metadata.py            (modified: runtime validation + deep immutability)
fc2-organizer/src/fc2_metadata_core/models/source_result.py       (modified: metadata isinstance guard + docstring)
fc2-organizer/tests/unit/core/test_metadata.py                    (modified: +4 new test classes, updated collection-equality assertions to tuple)
fc2-organizer/tests/unit/core/test_source_result.py               (modified: +4 new test classes)
```

`normalize/fc2_number.py`, `errors/__init__.py`,
`tests/unit/core/test_normalize_fc2_number.py`, and
`tests/contract/test_core_independent_of_amane.py` are **untouched** — R1
only closes R1-01/R1-02, not F3/F4/F5, and does not re-open FC2 number
normalization.

## Tests added/changed

Test count went from 100 (original Phase 1 submission) to 146 in this R1:
- `test_metadata.py`: 8 pre-existing tests kept (with two collection
  equality assertions updated from `list` literals to `tuple` literals to
  match the now-immutable stored representation, e.g.
  `md.tags == ("a", "b")` instead of `md.tags == ["a", "b"]`), 1 new
  `bool`-runtime test, plus 4 new test classes (`TestScalarTypeValidation`,
  `TestCollectionTypeValidation`, `TestImmutability`,
  `TestCallerOwnedInputAliasSafety`) replacing the old
  `TestMutableDefaultIsolation` (which asserted the old mutable-list
  sharing behavior that no longer applies once fields are tuples).
- `test_source_result.py`: all 32 pre-existing tests kept unchanged, plus 4
  new test classes (`TestMetadataTypeGuard`, `TestSuccessLifetimeInvariant`,
  `TestPartialFailureLifetimeInvariant`,
  `TestCallerOwnedAliasSafetyThroughSourceResult`).
- `test_normalize_fc2_number.py` (43 tests) and
  `test_core_independent_of_amane.py` (9 tests): unchanged, all still pass.

## Exact commands

```bash
cd fc2-organizer
python3 --version
# Python 3.11.15

python3 -m pytest -v
# ... 146 passed in 0.14s

python3 -m pytest -q
# 146 passed in 0.12s

python3 -m pytest --collect-only -q
# 146 tests collected in 0.04s
```

## Pass/fail counts

```text
Python version: 3.11.15
Collected:      146
Passed:         146
Failed:         0
Skipped:        0
```

## Original reproduction verification

Both reviewer reproductions were re-run directly (not only via pytest), per
requirement:

**Original F1 reproduction:**

```python
NormalizedMetadata(number="FC2-4825061", title=123)
```

Result: raises `MetadataContractError: title must be a str or None, got
<class 'int'>` immediately at construction. Does **not** construct
successfully; does **not** defer to a later `AttributeError`.

**Original F2 reproduction:**

```python
md = NormalizedMetadata(number="FC2-4825061", title="valid")
r = SourceResult(source_id="x", status=SourceStatus.SUCCESS, metadata=md, elapsed_ms=1)
```

Verified by direct script execution (not only pytest) that every available
public mutation path fails and the invariant survives:
- `md.title = ""` → `FrozenInstanceError: cannot assign to field 'title'`
- `r.metadata.title = ""` → same
- `r.metadata.actors.append("x")` → `AttributeError: 'tuple' object has no
  attribute 'append'`
- `r.metadata = NormalizedMetadata(title="other")` →
  `FrozenInstanceError: cannot assign to field 'metadata'`
- After all four attempts: `r.status == SourceStatus.SUCCESS` and
  `r.metadata.meets_minimum_success() == True`, unchanged.

Additionally verified `SourceResult(source_id="x", status=SUCCESS,
metadata=123, elapsed_ms=1)` raises `SourceResultContractError` at
construction rather than deferring to `AttributeError`.

## Regression check

- Phase 0 reviewer note **F-02** (independent `NOT_FC2`/`UNRECOGNIZED`
  semantics, no reliance on Amane fallback): unaffected by this R1 —
  `normalize/fc2_number.py` was not touched. All 43
  `test_normalize_fc2_number.py` tests still pass, including
  `test_negative_misidentification_regression` and the
  `TestIsValidFc2Number` class.
- Phase 0 reviewer note **F-03** (`[广告]FC2PPV-1234567` /
  `xxx@FC2PPV-1234567` automated regressions): unaffected. Verified
  individually:
  `python3 -m pytest tests/unit/core/test_normalize_fc2_number.py -v -k "f03"`
  → `test_f03_regression_ad_prefix_noise_closed` and
  `test_f03_regression_xxx_at_prefix_noise_closed` both `PASSED`.
- `tests/contract/test_core_independent_of_amane.py` (9 tests, unchanged):
  all still pass — `fc2_metadata_core` still does not import `amane`
  anywhere, statically or dynamically, and the public API (including the
  now-immutable `NormalizedMetadata`) is still fully usable with `amane`
  import blocked at runtime.
- 7-state `SourceStatus` vocabulary unchanged (`SUCCESS`, `NOT_FOUND`,
  `BLOCKED`, `RATE_LIMITED`, `NETWORK_ERROR`, `PARSE_ERROR`,
  `INVALID_RESPONSE`).
- Minimum-success definition unchanged (`canonical FC2 number + non-empty
  title`); only its *enforcement totality* and the *immutability of the
  object it is checked against* changed.

## Known limitations

1. Mutation-attempt exceptions are the natural ones raised by the
   underlying immutable Python types (`dataclasses.FrozenInstanceError` for
   attribute reassignment, `AttributeError` for calling a mutating method
   that doesn't exist on `tuple`, `TypeError` for item assignment on
   `MappingProxyType`), not a single unified custom exception type. This is
   intentional and idiomatic for "attempting an illegal mutation on an
   already-valid immutable object" (as opposed to R1-01's concern, which is
   about *construction-time* domain validation) but a reviewer may want a
   single `NormalizedMetadataImmutableError` wrapper instead; not done here
   to keep the R1 diff minimal and because the underlying exceptions are
   already reliably raised (never silently swallowed) and are documented in
   the contract doc and docstrings.
2. `field_sources` value coercion accepts any non-`str`/`bytes` iterable of
   `str` (e.g. a generator) and snapshots it to a `tuple`; this was already
   true for the plain sequence fields before R1 and is unchanged.
3. F3/F4/F5 (Phase 0/R1-independent-review non-blocking findings) are
   deliberately not touched in this round; see "Deferred non-blocking"
   below.

## Non-blocking findings deliberately deferred

```text
F3
F4
F5
```

Not part of the R1 Required Closure Set (`R1-01`, `R1-02` only). Must be
closed no later than before Phase 5 integration, per instruction.

## Security considerations

No new network access, file I/O, or credential handling introduced. All
changes are pure in-memory dataclass/validation logic. No secrets, tokens,
or cookies touched.

## Windows run

Windows NOT run (same as Phase 1 original submission; this R1's changes
are pure standard-library Python with no platform-specific behavior).

## Amane integration run

Not run / not applicable to Phase 1 R1 (unchanged from Phase 1 original:
`fc2_metadata_core` remains fully decoupled from `amane`, reverified by the
unchanged and still-passing `tests/contract/test_core_independent_of_amane.py`).

## Phase 2 NOT started
