# FC2 Metadata Core — Phase 1 Contract

**Revision note (Phase 1 R1):** §2.1/§2.2/§2.3 were added/updated in R1 to
close independent-review findings F1 (runtime type contract hole) and F2
(`SourceResult` lifetime invariant breakable through mutable metadata). See
`docs/review/PHASE1_R1_HANDOFF.md` for the review-round record. Everything
else in this document is unchanged from the original Phase 1 submission.

**Scope:** this document freezes the Phase 1 public contract of
`fc2_metadata_core` (`fc2-organizer/src/fc2_metadata_core/`). It is a
companion to the code and its tests, not a replacement for either — every
rule stated here is enforced by an automated test under
`fc2-organizer/tests/`.

Phase 1 does not access any real website, does not implement any scraper,
does not talk to Amane, and does not touch the filesystem beyond normal
Python module imports. Everything in this document and in the code it
describes is 100% offline.

## 1. Independence from Amane

`fc2_metadata_core` must never import `amane` or any `amane.*` module,
directly or indirectly, and must be importable and fully usable in an
environment where Amane is not installed at all.

Enforced by `tests/contract/test_core_independent_of_amane.py`:
- a static AST scan of every source file rejects any `import amane` /
  `from amane import ...` statement;
- a dynamic test installs a `sys.meta_path` finder that raises on any
  attempt to import `amane`/`amane.*`, then imports every core module and
  exercises the public API (`normalize_fc2_number`, `NormalizedMetadata`,
  `SourceResult`) under that finder.

This closes Phase 0 reviewer background note 1/3: the Core's model shapes
(`external_ids`, `source_urls`, plural) are deliberately **not** narrowed to
match Amane's current singular `MediaMetadata.external_id` /
`MediaMetadata.source_url`. That narrowing is Phase 5's job (the thin
adapter), not Phase 1's.

## 2. `NormalizedMetadata`

`fc2_metadata_core.models.NormalizedMetadata` — a **deeply immutable value
object** (frozen dataclass; revised in R1, see §2.3). Every field defaults
to `None` (scalars) or an empty immutable collection, so
`NormalizedMetadata()` with no arguments is valid.

Fields: `number`, `title`, `studio`, `publisher`, `release`, `runtime`,
`actors`, `tags`, `plot`, `poster_urls`, `thumb_urls`, `fanart_urls`,
`extrafanart`, `source_urls`, `external_ids`, `field_sources`.

### Minimum success (frozen)

```text
minimum success = a valid canonical FC2 number (see §4) + a non-empty title
```

All other fields may be partial/absent without affecting this. Implemented
as `NormalizedMetadata.meets_minimum_success()`, backed by
`has_valid_canonical_number()` and `has_non_empty_title()`. Covered by
`tests/unit/core/test_metadata.py::TestMinimumSuccess` (number+title passes;
number+empty/whitespace/missing title fails; title+missing/malformed number
fails). All three methods are **total predicates**: for any instance that
was successfully constructed, they always return `bool` and never raise
(`TestScalarTypeValidation::test_meets_minimum_success_never_raises_for_any_constructed_instance`).

### 2.1 Runtime type contract (R1-01 / reviewer finding F1)

R1 closed a hole where construction accepted any value for any field (e.g.
`title=123`, `actors=[123]`) and the illegal value only surfaced later as a
bare `AttributeError`/`TypeError` from `meets_minimum_success()` or similar
— an undocumented exception leaking through what is supposed to be a domain
contract boundary.

`NormalizedMetadata` is a domain object: every field's runtime type is
validated in `__post_init__` and any violation is rejected immediately as
`MetadataContractError`, never later.

| Field group | Required runtime shape | Rejected examples |
|---|---|---|
| `number`, `title`, `studio`, `publisher`, `release`, `plot` | `str \| None` | `title=123` |
| `runtime` | `int \| None`, `bool` excluded, `>= 0` | `runtime=True`, `runtime=-1`, `runtime="1"` |
| `actors`, `tags`, `poster_urls`, `thumb_urls`, `fanart_urls`, `extrafanart`, `source_urls` | a non-`str` sequence whose every element is `str` | `actors=[123]`, `actors="John"` (bare str rejected, not iterated char-by-char), `tags=123` (not iterable) |
| `external_ids` | mapping of `str` key to `str` value | `{123: "x"}`, `{"x": 123}`, a `list` instead of a mapping |
| `field_sources` | mapping of `str` key to a sequence of `str` | `{123: [...]}`, `{"title": [123]}`, `{"title": 123}` |

Enforced by `tests/unit/core/test_metadata.py::TestScalarTypeValidation` and
`::TestCollectionTypeValidation`, including the exact reviewer reproduction
(`test_original_f1_reproduction_title_int_is_rejected_at_construction`).

`SourceResult` mirrors this at its own boundary: `metadata` must be `None`
or an actual `NormalizedMetadata` instance, or construction is rejected
with `SourceResultContractError` — a caller passing e.g. `metadata=123`
cannot get as far as `metadata.meets_minimum_success()` raising
`AttributeError` (`tests/unit/core/test_source_result.py::TestMetadataTypeGuard`).

### 2.2 Deep immutability (R1-02 / reviewer finding F2)

R1 closed a lifetime hole: `SourceResult` was frozen, but the
`NormalizedMetadata` it referenced was mutable, so a `SUCCESS` result's
`metadata.meets_minimum_success()` guarantee (established in
`SourceResult.__post_init__`) could be invalidated *after* construction by
mutating the still-referenced `NormalizedMetadata` — outside any contract
boundary. The same applied to a `PARSE_ERROR`/`INVALID_RESPONSE` result's
partial metadata being mutated into something that meets minimum success
after the fact.

**Fix:** `NormalizedMetadata` is now deeply immutable, not just
shallow-frozen:

- The dataclass itself is `frozen=True`; scalar attribute (re)assignment
  raises `dataclasses.FrozenInstanceError`.
- Every sequence field (`actors`, `tags`, `poster_urls`, `thumb_urls`,
  `fanart_urls`, `extrafanart`, `source_urls`) is snapshotted to a `tuple`
  in `__post_init__` — `list.append`/`list[i] = ...` are simply not
  available on the stored value.
- `external_ids` and `field_sources` are snapshotted to
  `types.MappingProxyType` over a freshly-built private `dict` — item
  assignment/deletion raises `TypeError`.
- `field_sources` values are themselves snapshotted to `tuple`, so
  `field_sources["title"].append(...)` fails the same way sequence fields do.
- Caller-owned input containers are copied at construction time (element by
  element, not just re-wrapped), so mutating the original `list`/`dict`
  *after* constructing a `NormalizedMetadata` never reaches the already-built
  instance (no aliasing).

Because `SourceResult` cannot have its own `metadata` field reassigned
(frozen) and the referenced `NormalizedMetadata` cannot be mutated at any
depth, a `SourceResult`'s invariants now hold for the object graph's entire
lifetime, not just at the instant `__post_init__` ran.

Enforced by `tests/unit/core/test_metadata.py::TestImmutability` and
`::TestCallerOwnedInputAliasSafety`, and end-to-end through `SourceResult`
by `tests/unit/core/test_source_result.py::TestSuccessLifetimeInvariant`,
`::TestPartialFailureLifetimeInvariant`, and
`::TestCallerOwnedAliasSafetyThroughSourceResult`.

### 2.3 Consequence for Phase 3 (aggregation) — direction changed in R1

The Phase 1 HANDOFF originally left `NormalizedMetadata` non-frozen with
the stated rationale that "Phase 3 might need incremental in-place merge."
**That rationale is withdrawn as of R1.** `NormalizedMetadata` is frozen
architecture from here on:

```text
NormalizedMetadata = immutable value object
```

Phase 3's field-level aggregation must be **functional / copy-on-write**:
read one or more immutable `NormalizedMetadata` inputs, compute a merge,
and produce a *new* `NormalizedMetadata` instance. It must never attempt to
mutate an already-constructed/published `NormalizedMetadata` in place —
doing so is not possible through the public API (see §2.2) and must not be
worked around via private attribute access or `object.__setattr__` from
outside this module.

## 3. `SourceResult` / `SourceStatus` / `SourceErrorKind`

`fc2_metadata_core.models.SourceResult` — a frozen dataclass carrying the
outcome of one source's attempt to resolve one FC2 number:
`source_id`, `status`, `metadata`, `elapsed_ms`, `error_kind`, `error_detail`.

`SourceStatus` (7 members, per spec): `SUCCESS`, `NOT_FOUND`, `BLOCKED`,
`RATE_LIMITED`, `NETWORK_ERROR`, `PARSE_ERROR`, `INVALID_RESPONSE`.

`SourceErrorKind` mirrors the six non-success statuses one-to-one. It is a
separate type from `SourceStatus` so a later phase can add finer-grained
sub-kinds without touching the status vocabulary, and so it reads as
meaningless (and is forbidden) on a successful result.

### Invariants (all enforced in `__post_init__`, all tested)

| Rule | Enforced by |
|---|---|
| `source_id` must be non-empty / non-whitespace-only | `TestSourceIdInvariant` |
| `elapsed_ms` must not be negative (int/float, not bool) | `TestElapsedMsInvariant` |
| `metadata` must be `None` or an actual `NormalizedMetadata` instance (R1-01/F1) | `TestMetadataTypeGuard` |
| `status == SUCCESS` requires `metadata` present **and** `metadata.meets_minimum_success()` | `TestSuccessInvariants` |
| `status == SUCCESS` forbids `error_kind`/`error_detail` | `TestSuccessInvariants` |
| every non-success status requires `error_kind == <matching SourceErrorKind>` | `TestErrorKindAndDetailConsistency` |
| every non-success status requires a non-empty `error_detail` | `TestErrorKindAndDetailConsistency` |
| `NOT_FOUND` / `BLOCKED` / `RATE_LIMITED` / `NETWORK_ERROR` must **not** carry `metadata` | `TestNoMetadataFailureStatuses` |
| `PARSE_ERROR` / `INVALID_RESPONSE` **may** carry partial `metadata`, but not one that already meets minimum success (that would mean the status should have been `SUCCESS`) | `TestPartialMetadataAllowedStatuses` |

This is the concrete answer to "no bare `except Exception: return None`":
a source implementation (Phase 2+) is structurally forced to pick one of
the seven statuses and, for every failure, supply a matching `error_kind`
and a human-readable `error_detail` — there is no status-less failure path.

## 4. FC2 number normalization (NORM-01)

`fc2_metadata_core.normalize.normalize_fc2_number(text: str) -> FC2NumberResult`.

### NORM-01 — the hard invariant this Phase closes (Phase 0 reviewer F-02)

Phase 0 found that Amane's `parse_file_info(path=...)` always has a
mandatory fallback and therefore never returns `number=None` for a real
file — an unrecognized file can still surface as e.g. `TOTALLY-998` /
`ContentType.WESTERN` instead of an explicit "not recognized" signal.

**The FC2 Metadata Core makes this decision on its own, from its own
grammar, and never delegates it to Amane's fallback.** Every call to
`normalize_fc2_number` returns one of exactly two outcomes:

- `FC2RecognitionStatus.RECOGNIZED` with a well-formed `canonical` string, or
- `FC2RecognitionStatus.NOT_FC2` with `canonical=None`.

There is no third, fabricated outcome. `FC2NumberResult.__post_init__`
itself asserts `canonical is not None` iff `status is RECOGNIZED`, so this
invariant cannot be violated by construction, not just by convention.

### Canonical grammar

```text
FC2 [-_]* (PPV [-_]*)? DIGITS{5,8}
```

- Matched case-insensitively, anywhere inside a larger noisy string.
- `FC2` and the optional `PPV` literal may be joined by zero or more
  `-`/`_` separators, or none. Covers `FC2-PPV-1234567`, `FC2PPV-1234567`,
  `FC2PPV1234567`, `FC2-1234567`, `FC2_1234567`.
- The digit run must be 5 to 8 digits long (`MIN_FC2_DIGITS` /
  `MAX_FC2_DIGITS` in `fc2_number.py`). Current real FC2 PPV numbers are
  6-7 digits; 5-8 gives headroom while still rejecting implausible digit
  blobs (dates glued together, resolutions, hashes, timestamps). This is a
  Phase 1 design decision, not an upstream fact — a later phase may revisit
  it with evidence.
- **Word-boundary rule:** the character immediately before `FC2` (if any)
  and the character immediately after the digit run (if any) must not be
  `[A-Za-z0-9]`. This is what lets arbitrary noise (`[广告]`, `xxx@`,
  brackets, whitespace, other prefixes, extensions, `-CD1` suffixes)
  surround the token, while rejecting `SUPERFC2-1234567` (glued to a
  preceding letter) or `FC2-1234567EXTRA` (glued to a following letter).
- The canonical output is always `FC2-<digits>` (uppercase, single dash).

`is_valid_fc2_number(value)` checks whether a string is *already* in that
exact canonical shape (`^FC2-\d{5,8}$`); it does not extract from noisy
text. This is what `NormalizedMetadata.has_valid_canonical_number()` uses.

### Positive regression set (`tests/unit/core/test_normalize_fc2_number.py`)

Covers every form in spec §10, including the two forms Phase 0 reviewer
note F-03 explicitly required closed with real automated tests (not just
documentation): `[广告]FC2PPV-1234567` and `xxx@FC2PPV-1234567`, plus
extension/CD-suffix noise, mixed separators, repeated dashes, and
leading/trailing whitespace.

### Negative regression set

Attacks the grammar directly rather than restating the spec's bullet list
literally: pure numeric filenames, other studios' codes, dates,
resolutions, CD markers with no FC2 token, bare `FC2` with no digits, `FC2`
followed by digits that are too short (<5) or absurdly long (glued digit
blobs, >8 or spilling past the boundary), and — the key anti-naive-parser
cases — `FC2` glued to a preceding letter (`SUPERFC2-...`,
`PERFC2PPV...`) and a digit run glued to a following letter
(`FC2-1234567EXTRA`). These specifically prove the parser is not just
"sees `FC2` + any digits = match".

## 5. Explicitly out of scope for Phase 1

No site-specific logic of any kind (no FC2CMADB/FC2DB/JavTen selectors, no
FC2 official endpoint handling, no Cloudflare bypass, no cookies/HTTP
sessions), no scraper, no multi-source aggregation, no batch engine, no
Amane plugin adapter, no NFO writing, no file moves, no Amane DB access.
Those are Phase 2 and later.
