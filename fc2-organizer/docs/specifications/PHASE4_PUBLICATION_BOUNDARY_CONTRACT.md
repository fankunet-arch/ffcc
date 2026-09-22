# FC2 Organizer -- Phase 4 / P4-C3 Metadata Publication Boundary Contract

Status: **frozen at P4-C3** (candidate; independent review pending).
Package: `fc2_organizer.publication` (`errors.py`, `models.py`, `boundary.py`).
Also closes, in `fc2_metadata_core`: **C2-L2** (trace model hardening, section 14)
and **P2-R-10** (JavDB title double-unescape, section 16).

**Scope (frozen for this package):** answers "may this aggregated metadata be
safely bound to this `OrganizePlan` and handed to a later content-rendering
layer?". It renders nothing. No NFO/XML/JSON, no image, no filesystem access of
any kind, no network, no diagnostics export, no Amane. See section 17.

## 1. Architecture and dependency direction

```text
fc2_organizer.publication
    |-- fc2_organizer.planning          (public package only: OrganizePlan)
    |-- fc2_metadata_core.aggregation   (public package only: AggregationResult, AggregateStatus)
    '-- fc2_metadata_core.models        (public package only: NormalizedMetadata)
```

* `fc2_organizer.publication` imports nothing else outside the standard library
  (in practice only `__future__` and `dataclasses`). `errors.py` is stdlib-only.
* Forbidden: `amane`, `fc2_metadata_core.sources` (adapters), `.http`,
  `.resource_control`, `.batch`, aggregation internals (`engine`, `execution`,
  `retry`, `merge` modules), `fc2_organizer.discovery`, and any
  filesystem / network / clock / randomness module.
* No reverse dependency: nothing in `fc2_metadata_core`, `fc2_organizer.planning`
  or `fc2_organizer.discovery` imports `fc2_organizer.publication`.
* `fc2_organizer/__init__.py` does **not** eagerly import `publication` (same
  reason as `planning`, P4-C2: that would transitively load `fc2_metadata_core`
  on a bare `import fc2_organizer` and break P4-C1's frozen discovery boundary
  test). Import it explicitly: `from fc2_organizer.publication import prepare_publication`.
* Top-level `fc2_organizer` subpackages are now exactly
  `{"discovery", "planning", "publication"}`. The P4-C1 / P4-C2 scope-guard
  assertions were updated by one line each; none of their forbidden-import
  guards was changed.

Enforced by `tests/contract/test_publication_architecture.py`.

## 2. Public API

```python
from fc2_organizer.publication import prepare_publication, PublicationRecord

prepare_publication(plan: OrganizePlan, aggregation_result: AggregationResult) -> PublicationRecord
```

Also exported: `PUBLISHABLE_STATUSES` and the error classes of section 9.

## 3. `PublicationRecord` shape (frozen)

```python
@dataclass(frozen=True, slots=True)
class PublicationRecord:
    plan: OrganizePlan
    metadata: NormalizedMetadata
    aggregate_status: AggregateStatus   # SUCCESS or PARTIAL only

    number -> str   # read-only property: plan.canonical_number
```

Exactly these three fields. No `to_json` / `to_dict` / `to_xml` / `render*` /
`write` / `save` / `serialize` / `dump`: the record is a value, not a serializer.

## 4. Aggregate status gate (frozen)

| `AggregationResult.status` | publication |
|---|---|
| `SUCCESS` | accepted |
| `PARTIAL` | accepted -- the frozen Phase 3 aggregation contract guarantees minimum-success metadata; the operational failure of some source does not make the metadata unpublishable. The record keeps `PARTIAL` (never upgraded). |
| `FAILED` | **rejected** (`AggregationNotPublishableError`) |
| anything that is not an `AggregateStatus` (bypassed construction) | **rejected** (`AggregationNotPublishableError`) |

Aggregate statuses are not redefined here; `PUBLISHABLE_STATUSES = {SUCCESS, PARTIAL}`.

## 5. Metadata minimum-success gate (frozen)

The aggregate's `metadata` must be a `NormalizedMetadata` for which
`meets_minimum_success()` is true (valid canonical FC2 number + non-empty title).
That method is the only success rule; no second rule exists here. Otherwise:
`InvalidPublicationMetadataError`.

## 6. Identity correlation gate (frozen) -- closes the P4-C2 carried identity gap

A record is formed only if

```text
plan.canonical_number == aggregation_result.number == aggregation_result.metadata.number
```

all three being exact `str` (a `str` subclass could override `__eq__`). Any
disagreement raises `PublicationIdentityMismatchError`. The boundary never
chooses a "winner" between the plan's number and the metadata's number.
`AggregationResult` already enforces `metadata.number == number`; the boundary
re-checks every identity it relies on anyway, so an `AggregationResult` whose own
`__post_init__` was bypassed still cannot be bound to the wrong plan.

Check order (deterministic; the first failure raises): input types (section 9)
-> status (4) -> metadata (5) -> identity (6).

## 7. Model-level invariants (frozen)

`PublicationRecord.__post_init__` enforces, independent of `prepare_publication`
(a hand-built record gets the same guarantees), raising `PublicationContractError`:

* `plan` is an `OrganizePlan`; `metadata` is a `NormalizedMetadata`;
* `aggregate_status` is `AggregateStatus.SUCCESS` or `PARTIAL`;
* `metadata.meets_minimum_success()`;
* `metadata.number` is an exact `str` equal to `plan.canonical_number`.

## 8. No diagnostics in the publication object graph (frozen)

The record holds only the plan, the metadata and the status. Its full object graph
never reaches an `AggregationResult`, `SourceResult`, `SourceExecutionTrace`,
`SourceAttempt`, any exception object (hence no exception `args` / traceback), any
`error_detail` / `error_kind`, HTTP response, body, headers, cookie or credential.
Verified by walking the actual object graph (slots, `__dict__`, tuples, mappings) of
records built from aggregates that *do* carry traces and sensitive-looking
`error_detail` text (`tests/unit/publication/test_publication_no_side_effects.py`).

NFO/content publication and diagnostics publication stay separate layers: the C2-L2
hardening (section 14) does **not** make traces part of the record.

## 9. Error taxonomy (`errors.py`)

| error | base | raised when |
|---|---|---|
| `PublicationError` | `Exception` | base of all below |
| `PublicationInputError` | `PublicationError`, `TypeError` | `plan` not an `OrganizePlan` / `aggregation_result` not an `AggregationResult` |
| `AggregationNotPublishableError` | `PublicationError`, `ValueError` | status not `SUCCESS`/`PARTIAL` |
| `InvalidPublicationMetadataError` | `PublicationError`, `ValueError` | metadata missing / wrong type / not minimum success |
| `PublicationIdentityMismatchError` | `PublicationError`, `ValueError` | section 6 |
| `PublicationContractError` | `PublicationError`, `ValueError` | a `PublicationRecord` violates section 7 |

Messages are built only from canonical numbers, enum values and type names. They
never contain `SourceResult.error_detail`, an exception object / args / traceback or
any HTTP payload; a foreign (non-`str`, non-enum) value is rendered only as
`<TypeName>` -- its `repr` is never called. No publication error is chained to
another exception.

## 10. Deep immutability (frozen)

`PublicationRecord` is `frozen=True, slots=True` (no instance `__dict__`, no field
reassignment or deletion). `OrganizePlan` (frozen, tuples, frozen `PlannedPath`s)
and `NormalizedMetadata` (frozen; tuples; `MappingProxyType` snapshots detached from
caller containers) are already deeply immutable, so the whole record is.

## 11. Determinism, equality, hash (frozen)

Equal inputs give equal records (`==`, same `repr`). No clock, randomness, UUID,
filesystem or network is consulted. Hashing follows the existing semantics of the
nested objects: `OrganizePlan` is hashable but `NormalizedMetadata` is not (its
mappings are `MappingProxyType`), so `hash(record)` raises `TypeError` --
consistently, never randomly.

## 12. Zero filesystem, zero network (frozen)

`prepare_publication` and `PublicationRecord` perform no `exists` / `stat` /
`resolve` / `realpath` / `open` / `mkdir` / write / rename / move / copy / delete,
no socket, no `httpx` / `requests` / `urllib` request. Proven by running the boundary
(accepting and rejecting paths, and the whole synthetic gate) with all of these
APIs trapped, plus a before/after filesystem snapshot.

## 13. Synthetic gate

`tests/unit/publication/test_publication_synthetic_gate.py`: 400 distinct plan +
aggregate pairs (6- and 7-digit numbers; SUCCESS / PARTIAL mixed; single-attempt,
retried, NOT_FOUND, BLOCKED, NETWORK_ERROR, PARSE_ERROR source combinations; Unicode
titles; collection/mapping metadata), all under the filesystem/network traps. Every
matching pair is accepted; 800 mismatches (each plan against its neighbour's
aggregate + a forged metadata-number mismatch per item) and 50 FAILED aggregates are
rejected; a second pass is equal item by item; every record is frozen and its object
graph holds no diagnostics.

## 14. C2-L2 closure: `SourceExecutionTrace` / `SourceAttempt` reject engine-impossible states

Chosen closure: **validator hardening** in `fc2_metadata_core/aggregation/models.py`
(not a "trusted producer" statement). The engine (`execution.py`) was not modified.
Derived from the actual engine behaviour:

* an attempt is recorded with `completed=False` only by `_run_source`'s deadline
  path, always as `NETWORK_ERROR` / `SOURCE_DEADLINE`;
* the engine starts another attempt -- or a backoff before one -- only when
  `RetryPolicy.should_retry` is true, i.e. the attempt's `error_kind` is in the
  policy's `retryable_error_kinds`, which is always a subset of
  `retry.RETRY_ELIGIBLE_KINDS` (`NETWORK_ERROR`, `TIMEOUT`, `CONNECTION_ERROR`,
  `DECODE_ERROR`, `HTTP_SERVER_ERROR`).

New invariants (raise `AggregationContractError`):

| # | invariant | historical state it closes |
|---|---|---|
| 1 | `SourceAttempt(completed=False)` must be `NETWORK_ERROR` / `SOURCE_DEADLINE` | incomplete `SUCCESS` attempt |
| 2 | (same rule) | incomplete attempt of another kind (`PARSE_ERROR`, `NOT_FOUND`, `CONNECTION_ERROR`, ...) |
| 3 | every attempt except the last has a retry-eligible `error_kind` | retry after `NOT_FOUND` (and after `SUCCESS`, `BLOCKED`, `RATE_LIMITED`, `PARSE_ERROR`, `SOURCE_DEADLINE`, `CIRCUIT_OPEN`, ...) |
| 4 | with `deadline_during == "backoff"`, the last (completed) attempt has a retry-eligible `error_kind` | deadline during backoff after a terminal `SUCCESS` (or any non-retryable outcome) |

Still accepted (every shape the real engine produces, pinned by running the real
`execute_sources_traced`): single `SUCCESS` / `NOT_FOUND` / failure; retryable
failure -> `SUCCESS`; retryable failure -> final failure of any kind; 3-attempt
chains; a narrowed policy that stops on an eligible kind; deadline during attempt 1
or a retry attempt; deadline during retry backoff; `CIRCUIT_OPEN` with zero attempts
(C5); the C5 stale-admission case (a retry not made, the earlier retryable failure
stands). Completed attempts keep the pre-existing rule (any status / kind pair
allowed by `ALLOWED_ERROR_KINDS`) -- deliberately not tightened further.

The two checks are module-level functions (`_check_incomplete_attempt`,
`_check_retry_shape`); a mutation-style test reverts exactly them and shows each of
the four historical invalid states becomes constructible again.

**P2-R-07 note (still carried, not fixed here):** adapter-returned
`SourceResult.elapsed_ms` may be `0` on some failure paths. Any future diagnostics
publication that needs attempt timing **must** use the engine-measured
`SourceAttempt.elapsed_ms`, never treat an adapter failure's `elapsed_ms == 0` as a
real duration.

## 15. Relationship of C2-L2 to publication

Traces are never part of a `PublicationRecord` (section 8). The hardening exists so a
future, separately-contracted diagnostics/report layer that explicitly reads traces
receives a public model that cannot express engine-impossible states.

## 16. P2-R-10 closure: JavDB title decoded exactly once

`sources/adapters/javdb.py` read the detail-anchor title as
`clean_text(html.unescape(attrs.get("title", "")))`. `parse_attrs` returns the raw,
still entity-encoded value and `clean_text` itself calls `html.unescape`, so entities
were decoded twice. Now: `clean_text(attrs.get("title", ""))` (the unused `html`
import removed). Frozen behaviour:

| raw attribute | title |
|---|---|
| `A &amp; B` | `A & B` |
| `A &amp;amp; B` | `A &amp; B` (not `A & B`) |
| `&#38;amp; x` | `&amp; x` |
| `&amp;lt;tag&amp;gt;` | `&lt;tag&gt;` |
| `  A \n\t  B  ` | `A B` |

Unchanged: the text-title fallback when the attribute is empty (already a single
decode), whitespace collapsing, tag stripping of the text title, exact-number
matching / near-miss `NOT_FOUND`, and empty-title `PARSE_ERROR`. P2-R-05, P2-R-06 and
P2-R-07 are not touched.

## 17. Out of scope for P4-C3

NFO rendering / XML / writing; poster / fanart / thumb download or validation;
filesystem materialization (`mkdir`, move, rename); preview UI; CLI; JSON report;
diagnostics export; persistence / resume; Amane integration. No placeholder for any
of them exists.

## 18. Test matrix

| # | requirement | test |
|---|---|---|
| 1, 2, 6 | SUCCESS / PARTIAL matching -> record | `test_publication_boundary.py::test_matching_success_or_partial_aggregate_is_published` |
| 3 | FAILED rejected | `test_failed_aggregate_is_rejected`, `test_failed_status_is_rejected_even_if_bypassed_metadata_is_present` |
| 4 | plan != aggregate number | `test_plan_number_differing_from_aggregate_number_is_rejected` |
| 5 | plan != metadata number | `test_metadata_number_differing_from_aggregate_number_is_rejected`, `test_no_winner_is_chosen_...` |
| 7 | minimum success | `test_metadata_that_misses_minimum_success_is_rejected` |
| 8-10 | scalar / nested immutability | `test_publication_models.py::test_record_fields_cannot_be_reassigned_or_added`, `test_nested_plan_is_immutable`, `test_nested_metadata_is_immutable` |
| 11 | identical input -> identical record | `test_identical_inputs_give_equal_records` |
| 12-15 | no AggregationResult / SourceResult / trace / attempt / error_detail / exception | `test_publication_no_side_effects.py::test_record_graph_*`, `test_record_does_not_reference_the_input_aggregate_object` |
| 16 | Unicode preserved | `test_unicode_titles_are_preserved_exactly` |
| 17 | tuple / mapping immutable | `test_tuple_and_mapping_metadata_stays_immutable_and_detached_from_caller_containers` |
| 18, 19 | zero filesystem / network | `test_prepare_publication_runs_with_every_filesystem_and_network_api_trapped`, `test_rejections_also_run_...`, `test_prepare_publication_leaves_the_filesystem_unchanged` |
| 20 | no Amane | `tests/contract/test_publication_architecture.py` |
| 21-24 | C2-L2 invalid states rejected | `tests/unit/aggregation/test_agg_c2_l2_trace_hardening.py::test_21_* .. test_24_*` (+ all-kinds parametrizations) |
| 25-28 | legal shapes accepted | `test_25_* .. test_28_*` |
| 29 | real engine traces still valid | `test_29_every_real_engine_trace_shape_is_valid_under_the_hardened_model`, `test_29_real_engine_circuit_open_zero_attempt_trace_is_valid`, plus the unchanged Phase 3 aggregation / resource-control suites |
| -- | mutation proof | `test_mutation_reverting_the_c2_l2_checks_makes_each_invalid_state_constructible_again` |
| 30-34 | P2-R-10 | `tests/unit/sources/adapters/test_javdb_p2_r10_single_unescape.py` |
| gate | synthetic gate | `test_publication_synthetic_gate.py` |

## 19. Carried debts

Closed by P4-C3: **P4-C2 `metadata.number != canonical_number` identity gap**
(closed at this boundary, section 6), **C2-L2** (section 14), **P2-R-10** (section 16).

Still carried, unchanged: P4-C2-R1-02 (LOW), OrganizePlan operation-graph
model-level hardening, overwrite executor semantics (frozen `NEVER`), extended
Windows reserved-name edge cases; P4-C1-R-02..R-05; P2-R-05, P2-R-06, P2-R-07 (see
section 14 note); C3-N1..N4; C4-N1; C4-R1-N1..N3; F3; F5; C5-R1-L1.
