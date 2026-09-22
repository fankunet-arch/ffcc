# FC2 Organizer -- Phase 4 / P4-C2 Immutable Organize Plan Contract

Status: **frozen at P4-C2** (candidate; independent closure review pending).
Package: `fc2_organizer.planning` (`errors.py`, `models.py`, `policy.py`, `paths.py`, `planner.py`).

**Scope (frozen for this package):** answers "if organizing were executed,
what target paths and operations would result?" for one already-discovered
media item. No filesystem mutation of any kind, no NFO/image writing, no
Amane dependency, no persistence, no CLI/UI, no execution of any planned
operation. See section 13 for the full out-of-scope list.

## 1. Architecture and dependency direction

```text
fc2_organizer
    |
    v
fc2_metadata_core
```

`fc2_metadata_core` never imports `fc2_organizer`. Nothing under
`fc2_organizer` may import `amane`. `fc2_organizer.planning` consumes only:

* `fc2_organizer.discovery`'s **public** package (`DiscoveredMediaItem`) --
  never its internal modules (`scanner`, `models`, `policy`, `errors`,
  `_platform`) directly, and it re-scans/re-discovers nothing.
* `fc2_metadata_core.models` (`NormalizedMetadata`) and
  `fc2_metadata_core.normalize` (`is_valid_fc2_number`) -- the closed Phase
  1/3 public boundary. It never imports `fc2_metadata_core.sources`,
  `.aggregation`, `.resource_control`, `.http`, or `.batch`.

Enforced by `tests/contract/test_planning_architecture.py`: a static AST
scan of every `planning/*.py` file (catches an import buried in a function
body or `try`/`except`), a check that only `fc2_metadata_core.models` /
`fc2_metadata_core.normalize` are ever imported, a check that only the bare
`fc2_organizer.discovery` package (never its submodules) is ever imported,
and a dynamic meta-path-finder block proving `amane` cannot be imported
even lazily while actually exercising `build_organize_plan` end to end
under the block.

**Note on the dynamic block's scope:** the block only guards against
`amane` loading at runtime (not against `fc2_metadata_core.aggregation` /
`.sources` / `.http` / `.batch` loading). This is deliberate, not a gap:
`fc2_metadata_core`'s own (frozen, out-of-scope-to-modify) `__init__.py`
unconditionally imports *all* of its submodules as soon as *any* of them --
including the allowed `models`/`normalize` -- is imported. Blocking those
specific submodules at the meta-path level would make
`fc2_metadata_core.models` itself unimportable through its own supported
interface, which is not a meaningful test of `fc2_organizer.planning`'s own
architecture. The static AST scan is what proves this package's own source
never *references* those submodules -- and it is exercised at full
strictness (see `_FORBIDDEN_PREFIXES` in the test file).

`fc2_organizer/__init__.py` deliberately does **not** eagerly import
`planning` (unlike `discovery`), for exactly the reason above: eagerly
importing `planning` from `fc2_organizer/__init__.py` would make the
`fc2_metadata_core` transitive load happen merely by importing
`fc2_organizer` or `fc2_organizer.discovery` -- which would have broken
P4-C1's own already-frozen `test_discover_media_runs_end_to_end_with_forbidden_modules_blocked_at_runtime`
(this was caught and fixed during P4-C2 development; see the P4-C2 handoff
"Known limitations" section). Callers reach this package via
`from fc2_organizer import planning` or
`from fc2_organizer.planning import build_organize_plan`.

## 2. Public API

```python
from fc2_organizer.planning import (
    OutputPolicy,
    OrganizePlan,
    PlannedPath,
    PlannedOperation,
    PlannedOperationKind,
    build_organize_plan,
)

plan: OrganizePlan = build_organize_plan(
    media_item,       # fc2_organizer.discovery.DiscoveredMediaItem
    canonical_number,  # exact str, already FC2-<digits>
    metadata,          # fc2_metadata_core.models.NormalizedMetadata
    library_root,      # str | os.PathLike, fully-qualified absolute (section 11a)
    policy=None,       # OutputPolicy | None
)
```

`build_organize_plan` is a pure function: same inputs always produce an
equal `OrganizePlan` (section 9), and it performs **zero filesystem
access** -- not even a read (section 10-11).

## 3. `OutputPolicy`

Frozen dataclass (`policy.py`), the *only* caller-configurable knobs:

```text
nfo_extension: str = ".nfo"
poster_filename: str = "poster.jpg"
fanart_filename: str = "fanart.jpg"
thumb_filename: str = "thumb.jpg"
extrafanart_dirname: str = "extrafanart"
```

Directory naming (always the bare canonical FC2 number) and the
media/NFO basenames (always `<canonical><ext>` / `<canonical><nfo_extension>`)
are **never** configurable -- there is no naming-strategy field, and title
never participates (section 5). Collision policy (fail closed) and
overwrite policy (never) are frozen constants, not fields on this policy
(section 7-8) -- `OutputPolicy` has no `overwrite`/`collision` knob and
`build_organize_plan` has no `overwrite=`/`on_collision=` parameter.

`__post_init__` validates field *shape* only (non-empty `str`,
`nfo_extension` dot-prefixed); Windows path-component *safety* is validated
once, centrally, by `paths.validate_path_component` when these values are
turned into actual path components inside `build_organize_plan` -- never
duplicated (section 6).

## 4. Default v1.0 layout (frozen)

```text
<library_root>/
  FC2-1234567/
    FC2-1234567.<original-extension>
    FC2-1234567.nfo
    poster.jpg
    fanart.jpg
    thumb.jpg
    extrafanart/
```

`downloads/random-name.MP4` + canonical `FC2-1234567` -> target media
`<library_root>/FC2-1234567/FC2-1234567.mp4`. The extension is normalized
to lowercase (`.MP4` -> `.mp4`) but the **container is never changed**
(`.mp4` never becomes `.mkv`): `build_organize_plan` only lower-cases
`media_item.extension`, it never substitutes a different extension.
`OrganizePlan.source_extension` (source identity, section 8) preserves the
*original*, unmodified extension for later verification against the real
file; only the *target* basename is normalized.

## 5. Title never participates in path generation (frozen)

Even when `metadata.title` is `"Example Title"`, the target directory is
always `FC2-1234567` and the target media is always `FC2-1234567.mp4` --
never `FC2-1234567 Example Title`. No `NormalizedMetadata` field (`title`,
`actors`, `studio`, `genre`, ...) is read by the default path-generation
logic. This is a deliberate v1.0 freeze (not an oversight) to avoid title
drift, Unicode/special-character path risk, and source-priority rename
drift; there is no `OutputPolicy` naming-strategy knob to opt into
title-based naming.

## 6. Canonical number boundary (no second parser)

`canonical_number` must be an exact `str` (a `str` subclass is rejected --
`OrganizePlanInputError` -- mirroring the batch package's own C4-R1-05
precedent: no method of a hostile subclass is ever called on the rejection
path) that satisfies `fc2_metadata_core.normalize.is_valid_fc2_number`
(`InvalidCanonicalNumberError` otherwise). This package implements no
second FC2 recognizer and never guesses/repairs dirty input -- it fails
closed, exactly like `BatchScheduler` (`PHASE3_BATCH_CONTRACT.md` section
4) does at its own canonical-number boundary.

## 7. Source media identity (no re-discovery)

`media_item` must be an actual `fc2_organizer.discovery.DiscoveredMediaItem`
instance (`OrganizePlanInputError` otherwise). This package never
re-scans a directory, never re-derives media identity, and never touches
the filesystem to verify `media_item`'s fields -- it only reads the five
already-validated P4-C1 fields: `source_path`, `relative_path`,
`extension`, `index`, `size`. All five are carried unchanged into
`OrganizePlan.source_*` so a future execution layer can re-verify them
against the real filesystem before acting (that re-verification is
explicitly out of scope here -- P4-C2 produces no side effects at all).

## 8. `OrganizePlan` fields (frozen shape)

```text
source_path: str            (absolute; from media_item, unmodified)
source_relative_path: str   (from media_item, unmodified)
source_extension: str       (from media_item, unmodified -- NOT lowercased)
source_index: int           (from media_item, unmodified)
source_size: int            (from media_item, unmodified)

canonical_number: str

library_root: str            (fully-qualified absolute, section 11a)

target_directory: PlannedPath
target_media_path: PlannedPath
nfo_path: PlannedPath
poster_path: PlannedPath
fanart_path: PlannedPath
thumb_path: PlannedPath
extrafanart_directory: PlannedPath

operations: tuple[PlannedOperation, ...]
```

No aggregation trace, `SourceExecutionTrace`, or error-diagnostic object is
ever stored here (section 12) -- `OrganizePlan` is not a trace-publication
boundary. `metadata` itself (the `NormalizedMetadata` object) is likewise
not stored on the plan; only the already-extracted `canonical_number` is
(metadata's role in P4-C2 is validation-only, see section 9).

## 9. Metadata boundary: validation-only, fail closed

`metadata` must be an actual `NormalizedMetadata` instance
(`OrganizePlanInputError` otherwise) that satisfies
`meets_minimum_success()` (`FC2_METADATA_CORE_CONTRACT.md` section 2 --
canonical number + non-empty title). Anything less raises
`InvalidMetadataForPlanningError` -- **no plan is ever produced from
partial/failed metadata**, even though the v1.0 default path derivation
does not actually read `metadata.title`/`.actors`/etc. This package does
not redefine "metadata success"; it defers entirely to the frozen
`NormalizedMetadata.meets_minimum_success()` predicate.

## 10. Windows path-component safety (centralized)

`fc2_organizer.planning.paths.validate_path_component` is the **single**
place path-component sanitization lives (`planner.py` and `models.py` both
call into it; no duplicated logic). Every generated basename/dirname
(`FC2-1234567`, `FC2-1234567.mp4`, `FC2-1234567.nfo`, `poster.jpg`,
`fanart.jpg`, `thumb.jpg`, `extrafanart`, and any `OutputPolicy` override of
the last four plus the NFO extension) is validated:

* non-empty `str`; not exactly `"."` or `".."`
* no embedded path separator (`/` or `\`) -- a single component can never
  smuggle in an extra path segment (this is also the traversal/absolute-
  override/drive-replacement defense: `../../evil.jpg`, `C:\other\evil.jpg`,
  and `D:evil.jpg` are all rejected here, since each contains a forbidden
  character or separator)
* no other Windows-illegal character (`< > : " | ? *`) and no ASCII
  control character
* no trailing dot or trailing space
* not a Windows reserved device name (`CON`, `PRN`, `AUX`, `NUL`,
  `COM1`-`COM9`, `LPT1`-`LPT9`), case-insensitively, checked against the
  portion before the *first* dot (`CON.txt` rejected, `CONFIG.txt` accepted)

Violation raises `UnsafeTargetComponentError`. The frozen v1.0 default
values never trigger this (regression-tested); it only fires for an
`OutputPolicy` override or a hand-built model.

## 11. Target containment (structural, not filesystem-probed)

Because every caller-controlled component is validated separator/`..`-free
*before* being joined with `os.path.join(target_directory, basename)`, the
result is **structurally** guaranteed to be nested under `library_root` --
this is a property of string construction, not something checked by
resolving/statting the filesystem (`build_organize_plan` never calls
`exists`/`resolve`/`realpath`). `OrganizePlan.__post_init__` additionally
**re-checks** every target field via
`fc2_organizer.planning.paths.is_contained_within` (a purely lexical,
Windows-case-insensitive segment comparison) and raises
`TargetEscapesLibraryRootError` if it ever fails -- a redundant,
defense-in-depth invariant at the model layer, independent of whether the
planner that built the plan is correct, mirroring P4-C1-R-01's dual-layer
(scanner + model) pattern for `DiscoveredMediaItem.source_path`.

**Segment comparison, not `str.split(os.sep)` (R1, P4-C2-GOV-02).** The
original implementation split each normalized path on `os.sep`. A root that
is itself a bare drive (`C:\`) or a bare UNC share (`\\server\share\`)
normalizes to a string *ending* in the separator, so `str.split(os.sep)`
produces a spurious trailing empty segment that inflates the root's part
count -- a real child (`C:\FC2-1234567`) then wrongly compared as "not
contained" (`len(candidate_parts) <= len(root_parts)` tripped even though
the candidate genuinely nests under the root). `is_contained_within` now
splits with `pathlib.Path(...).parts` instead: a drive-and-root or a
UNC-share-and-root collapses into a single anchor part (`('C:\\',)` /
`('\\\\server\\share\\',)`), which has no such artifact, still performs
zero filesystem access (`Path` construction and `.parts` are purely
lexical), and continues to reject a same-string-prefix sibling
(`C:\library2` is not "under" `C:\library`) without ever using
`str.startswith`.

## 11a. Fully-qualified library root boundary (frozen, P4-C2-GOV-03)

`library_root` must be an **unambiguous, fully-qualified absolute path**,
under the *current runtime OS*'s own semantics --
`fc2_organizer.planning.paths.is_fully_qualified_absolute_root` is the
single, centralized boundary; `planner.py` and `models.py` both call into
it rather than each guessing with a bare `os.path.isabs()`.

* **Windows** (`os.name == "nt"`): accepted only if `os.path.splitdrive`
  finds a real drive letter with a root (`C:\lib`, `C:/lib`) or a UNC share
  (`\\server\share`, `\\server\share\lib`, with or without a trailing
  separator). **Rejected:** a plain relative name (`lib`), a dot-relative
  form (`.\lib`, `..\lib`), a drive-relative form (`C:lib`), and --
  the specific finding this closes -- a **rooted-but-driveless** form
  (`\lib`, `/lib`). `os.path.isabs()`'s treatment of the rooted-but-driveless
  form has differed across Python versions; it is ambiguous ("the root of
  whichever drive is current"), and this package never guesses it.
* **POSIX** (anything else): plain `os.path.isabs(path)` -- POSIX has no
  drive/UNC ambiguity, so `/lib` is already unambiguous and remains legal.
  The branch is chosen by the *current runtime OS*, never by guessing from
  the string's own shape, so a genuine POSIX absolute path is never
  rejected by a Windows-only rule (and vice versa).

Violation raises `InvalidLibraryRootError` from `build_organize_plan`, and
(redundantly, at the model layer) `OrganizePlanContractError` from
`OrganizePlan.__post_init__` for a hand-built plan -- the same dual-layer
pattern as section 11's containment re-check.

## 12. Collision and overwrite policy (frozen, not a knob)

**Collision = fail closed.** If any two of a plan's own generated target
basenames would collide under Windows case-insensitive filename semantics
(e.g. `poster.jpg` vs. an `OutputPolicy.fanart_filename` also set to
`"poster.jpg"`, or `nfo_extension` set to match the source's own
extension), `build_organize_plan` raises `InternalTargetCollisionError`.
There is no automatic suffixing (`(1)`, `_2`, `-copy`) and no silent
directory rename.

**Overwrite = never**, for source media, target media, and every generated
artifact. This is a frozen semantic this package's plans are built to be
consistent with; P4-C2 does not check or delete anything against a real
filesystem (there is no filesystem access at all) -- a real preflight
against existing files on disk is explicitly deferred to a future execution
phase (section 13).

Two different `DiscoveredMediaItem`s that happen to canonicalize to the
same FC2 number (e.g. a real duplicate download under two different source
directories) are **not** deduplicated or resolved by P4-C2: each produces
its own valid, independently-computed `OrganizePlan`, and those two plans
will name the *same* target -- P4-C2 surfaces this (both plans are
inspectable and comparable by the caller) rather than resolving it, exactly
as `InternalTargetCollisionError`/collision-policy freeze intends.

## 13. Out of scope for P4-C2

No `mkdir`/rename/move/copy/delete of any kind, no NFO
rendering/writing, no poster/fanart/thumb/extrafanart downloading or image
validation, no filesystem executor, no preview UI, no CLI, no JSON
diagnostics, no persistent job/database/resume, no Amane adapter, no HTTP
service/REST API/GUI, no real-filesystem preflight (existing-file
detection, permission/writability probing). Real-filesystem preflight and
collision resolution against what is actually on disk are explicitly
deferred to a future execution package.

## 14. Immutability and determinism (frozen)

Every public model (`OutputPolicy`, `PlannedPath`, `PlannedOperation`,
`OrganizePlan`) is a frozen, `slots=True` dataclass. `OrganizePlan.operations`
is a `tuple[PlannedOperation, ...]`; there is no caller-owned mutable
container anywhere in the object graph. `build_organize_plan` reads no
random source, no wall clock, no filesystem enumeration order, and
generates no UUID -- identical inputs always produce an equal
(`==`-comparable) `OrganizePlan`, including identical `operations` ordering:
`CREATE_DIRECTORY`, `MOVE_MEDIA`, `MATERIALIZE_NFO`, `MATERIALIZE_POSTER`,
`MATERIALIZE_FANART`, `MATERIALIZE_THUMB`, `ENSURE_EXTRAFANART_DIRECTORY`.

## 15. Planned operations are purely descriptive

`PlannedOperationKind` has seven members (the list above). `PlannedOperation`
carries only `kind` + `target: PlannedPath` (+ `source: PlannedPath | None`,
set if and only if `kind is MOVE_MEDIA` -- the only operation with two
paths). No `PlannedOperation`/`OrganizePlan` method performs the action it
describes -- there is no `run()`/`apply()`/`execute()` anywhere in this
package.

## 16. Error taxonomy (`errors.py`)

```text
OrganizePlanError(Exception)
+-- OrganizePlanInputError(OrganizePlanError, TypeError)
|      media_item not a DiscoveredMediaItem; canonical_number not an
|      exact str; metadata not a NormalizedMetadata; library_root not a
|      str/os.PathLike; policy neither None nor an OutputPolicy
+-- InvalidCanonicalNumberError(OrganizePlanError, ValueError)
+-- InvalidLibraryRootError(OrganizePlanError, ValueError)
|      empty / whitespace-only / not a fully-qualified absolute path
|      (section 11a -- includes a Windows rooted-but-driveless form)
+-- InvalidMetadataForPlanningError(OrganizePlanError, ValueError)
+-- InvalidOutputPolicyError(OrganizePlanError, ValueError)
+-- UnsafeTargetComponentError(OrganizePlanError, ValueError)
+-- InternalTargetCollisionError(OrganizePlanError, ValueError)
+-- OrganizePlanContractError(OrganizePlanError, ValueError)
       (hand-built model violates its own structural contract)
       +-- TargetEscapesLibraryRootError(OrganizePlanContractError)
```

Each is independently catchable; no bare `ValueError` is used to collapse
distinct failure reasons (consistent with the rest of the project's
"no status-less failure path" convention, `FC2_METADATA_CORE_CONTRACT.md`
section 3).

## 17. Test matrix

| # | Requirement | Test file |
|---|---|---|
| 1-12 | standard/extension-preserving/normalized/deterministic-field plans, identical-input replay, distinct-identity-same-number | `test_planning_planner.py` |
| 13-15 | canonical number validation (valid/dirty/subclass), invalid metadata rejected | `test_planning_planner.py` |
| 16 | empty/whitespace/relative/non-str library root rejected, `os.PathLike` accepted, **fully-qualified-root boundary (section 11a): Windows drive/UNC accepted, rooted-but-driveless (`\lib`/`/lib`) rejected, POSIX `/lib` accepted** | `test_planning_planner.py`, `test_planning_paths.py`, `test_planning_models.py` |
| 17-18 | target containment (including bare drive-root and UNC-share-root children, section 11 R1 fix), traversal/absolute-override/drive-replacement cannot escape root | `test_planning_planner.py`, `test_planning_paths.py` |
| 19-21 | Windows illegal chars, reserved device names, trailing dot/space | `test_planning_paths.py`, `test_planning_planner.py` |
| 22-23 | case-insensitive collision reasoning, internal collision fail-closed | `test_planning_paths.py`, `test_planning_planner.py` |
| 24-25 | overwrite policy frozen (not a knob), no automatic suffixing | `test_planning_planner.py` |
| 26-27 | title / Unicode metadata never alter default target path | `test_planning_planner.py` |
| 28 | plan models deeply immutable | `test_planning_models.py` |
| 29 | operations ordered deterministically | `test_planning_planner.py`, `test_planning_synthetic_gate.py` |
| 30-33 | no filesystem mutation, no network (guard scans the real, non-empty production source directory and is proven to FAIL on a planted forbidden import, not just PASS on today's clean code -- section "Network Guard" below, P4-C2-GOV-01), no Amane, no reverse dependency | `test_planning_no_mutation.py`, `test_planning_architecture.py`, `test_planning_synthetic_gate.py` |
| 34 | P4-C1 discovery remains untouched (behaviorally) | full-suite regression (2692 passed / 8 skipped after R1, baseline 2480 passed / 4 skipped at P4-C1 close) |
| model/policy/paths contracts | `PlannedPath`/`PlannedOperation`/`OrganizePlan`/`OutputPolicy` invariants, sanitization/containment/qualification helpers | `test_planning_models.py`, `test_planning_policy.py`, `test_planning_paths.py` |
| architecture | dependency direction, no `amane`, no forbidden `fc2_metadata_core`/`discovery` submodule | `test_planning_architecture.py` |
| synthetic planning gate | 400 synthetic items, multiple extensions/numbers/Unicode titles, determinism, containment, zero internal collision, zero mutation, non-vacuous + planted-import-detecting network guard | `test_planning_synthetic_gate.py` |

### Network Guard (R1, P4-C2-GOV-01)

The synthetic gate's no-network-import scan computes its production
source directory as `Path(__file__).resolve().parents[N] / "src" /
"fc2_organizer" / "planning"`. The original `N=2` was copied from
`tests/contract/test_planning_architecture.py` (one directory shallower --
`tests/contract` -- where `parents[2]` is correct), but this file lives at
`tests/unit/planning/`, one level deeper, so `parents[2]` resolved to the
nonexistent `tests/src/fc2_organizer/planning`: `rglob("*.py")` silently
returned zero files, and a `for path in ...: assert ...` loop over zero
files vacuously passes without checking anything. Fixed to `parents[3]`,
and now guarded three ways: (1) a dedicated test asserts the resolved
directory exists *and* the file count is non-zero *and* contains every
known production module by name; (2) the scan function itself
(`_scan_forbidden_imports`) is a small, reusable, pure AST walker exercised
directly against a planted `import socket` / `from urllib import request`
in an isolated `tmp_path` file (never a production file) and asserted to
detect it -- proving the guard can actually FAIL, not just PASS on
whatever code happens to be clean today; (3) a fourth test proves the same
scanner does *not* false-positive on ordinary allowed imports (`os`,
`pathlib`, `dataclasses`, `enum`) it itself uses. No production code was
changed to make this pass -- both independent reviewers already confirmed
`fc2_organizer.planning` has no real network dependency; this was purely a
test-evidence defect.

## 18. Backlog carried forward (not addressed by P4-C2)

Not triggered / not addressed: `P4-C1-R-02`, `P4-C1-R-03`, `P4-C1-R-04`,
`P4-C1-R-05`, `C2-L2`, `P2-R-05`, `P2-R-06`, `P2-R-07`, `P2-R-10`, `C3-N1`,
`C3-N2`, `C3-N3`, `C3-N4`, `C4-N1`, `C4-R1-N1`, `C4-R1-N2`, `C4-R1-N3`, `F3`,
`F5`, `C5-R1-L1`. None of these debts is touched, read, or relevant:
`fc2_organizer.planning` has zero runtime dependency on any module any of
them concern (its only `fc2_metadata_core` dependency is the read-only
`models`/`normalize` boundary).
