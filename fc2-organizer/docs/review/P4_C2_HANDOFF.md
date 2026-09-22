# Phase 4 / P4-C2 Handoff -- Immutable Organize Plan

```text
Phase        = 4
Package      = P4-C2
Role         = Developer
Branch       = claude/phase4-c2-organize-plan
```

## 1. Coordinates

```text
Frozen Base                = 51933a81382d7922a61b5fcdddc54b17b5293e6f
P4-C2 Code Review Candidate = 1a4ca88bf9d10ca94f2a8a640b734c96c558a8a8
P4-C2 Docs Head             = <this commit; see git log after commit>
Remote Head                 = <set after push; see "Push" section below>

Code Review Range: 51933a81382d7922a61b5fcdddc54b17b5293e6f..1a4ca88bf9d10ca94f2a8a640b734c96c558a8a8
Docs Review Range: 1a4ca88bf9d10ca94f2a8a640b734c96c558a8a8..<Docs Head>
```

Verified before any change: `git fetch --all --tags`,
`origin/claude/phase4-c1-recursive-discovery` == `51933a81382d7922a61b5fcdddc54b17b5293e6f`,
working tree clean (only untracked `.claude/`), new branch
`claude/phase4-c2-organize-plan` created from that exact commit, developed
in an isolated worktree.

## 2. Type

**NEW PACKAGE** (`fc2_organizer.planning`), plus two minimal touches to
existing files -- see section 4.

## 3. Changed files

**Code Review Candidate (`1a4ca88`), 16 files:**

New (14):
```text
fc2-organizer/src/fc2_organizer/planning/__init__.py
fc2-organizer/src/fc2_organizer/planning/errors.py
fc2-organizer/src/fc2_organizer/planning/models.py
fc2-organizer/src/fc2_organizer/planning/paths.py
fc2-organizer/src/fc2_organizer/planning/planner.py
fc2-organizer/src/fc2_organizer/planning/policy.py
fc2-organizer/tests/contract/test_planning_architecture.py
fc2-organizer/tests/unit/planning/__init__.py
fc2-organizer/tests/unit/planning/test_planning_models.py
fc2-organizer/tests/unit/planning/test_planning_no_mutation.py
fc2-organizer/tests/unit/planning/test_planning_paths.py
fc2-organizer/tests/unit/planning/test_planning_planner.py
fc2-organizer/tests/unit/planning/test_planning_policy.py
fc2-organizer/tests/unit/planning/test_planning_synthetic_gate.py
```

Modified (2):
```text
fc2-organizer/src/fc2_organizer/__init__.py             (M -- see section 8)
fc2-organizer/tests/contract/test_discovery_architecture.py  (M -- see section 4)
```

**Docs Head (this commit), 2 files, both new:**
```text
fc2-organizer/docs/specifications/PHASE4_ORGANIZE_PLAN_CONTRACT.md
fc2-organizer/docs/review/P4_C2_HANDOFF.md
```

No `pyproject.toml` change was needed: `fc2_organizer.planning` is picked
up the same way `fc2_organizer.discovery` already is (`[tool.setuptools.packages.find]
where = ["src"]`, `[tool.pytest.ini_options] pythonpath = ["src", "tests"]`).

## 4. The one touch to a P4-C1 file, and why

`fc2-organizer/tests/contract/test_discovery_architecture.py`'s
`test_organizer_package_has_no_other_stray_top_level_modules_yet` asserted
`top_level_dirs == {"discovery"}`. Its own docstring already read *"the
only subpackage under fc2_organizer is discovery **yet**"* -- an explicit
scope guard anticipating a next package, not a claim about discovery's own
internals. Adding `fc2_organizer.planning` as a sibling package (never
modifying `discovery/**`) necessarily makes that specific assertion false;
leaving it unchanged would have turned a previously-passing P4-C1 test into
a false failure. The assertion was updated to
`top_level_dirs == {"discovery", "planning"}`, with an expanded docstring
explaining the change and pointing at this handoff. **No other line in that
file, and no file under `src/fc2_organizer/discovery/**` or
`src/fc2_metadata_core/**`, was touched.** No `discover_media` behavior,
model, or error semantic changed.

This was flagged in the pre-code-write report (per the task brief's
Context Handshake step) before it was made, not discovered after the fact.

## 5. Architecture summary

```text
DiscoveredMediaItem (P4-C1, closed)
+ canonical FC2 number
+ NormalizedMetadata (fc2_metadata_core, closed)
+ library_root
+ OutputPolicy (optional)
        |
build_organize_plan(...)
        |   pure, deterministic, side-effect-free, ZERO FILESYSTEM MUTATION
        v
OrganizePlan(source identity, canonical number, target paths, planned operations)
```

`fc2_organizer -> fc2_metadata_core` is the only allowed dependency
direction (unchanged, frozen). `fc2_organizer.planning` depends on
`fc2_organizer.discovery`'s public package (`DiscoveredMediaItem` only) and
on `fc2_metadata_core.models` / `fc2_metadata_core.normalize` (never
`.sources`/`.aggregation`/`.resource_control`/`.http`/`.batch`, never
discovery's internal modules). Full detail:
`docs/specifications/PHASE4_ORGANIZE_PLAN_CONTRACT.md`.

## 6. Public API

```python
from fc2_organizer.planning import (
    OutputPolicy, OrganizePlan, PlannedPath, PlannedOperation,
    PlannedOperationKind, build_organize_plan,
)

plan = build_organize_plan(media_item, canonical_number, metadata, library_root, policy=None)
```

## 7. Default directory layout

```text
<library_root>/
  FC2-1234567/
    FC2-1234567.<original-extension, lowercased>
    FC2-1234567.nfo
    poster.jpg
    fanart.jpg
    thumb.jpg
    extrafanart/
```

Title never participates; verified directly by
`test_title_does_not_alter_default_target_path` and
`test_unicode_metadata_does_not_alter_default_target_path`, plus the
400-item synthetic gate's `test_synthetic_gate_unicode_titles_never_leak_into_target_paths`.

## 8. Target containment strategy

**Structural, not filesystem-probed.** Every caller-controlled path
component (directory name, media/NFO basename, artifact filenames) is
validated to contain no path separator and no `..` *before* being joined
onto `library_root`/`target_directory` via `os.path.join` -- so the result
is nested under the root by construction, regardless of what
`library_root`'s own string content is. `OrganizePlan.__post_init__`
independently re-checks every target field via a purely lexical,
Windows-case-insensitive containment check
(`fc2_organizer.planning.paths.is_contained_within`) and raises
`TargetEscapesLibraryRootError` if that ever fails -- a redundant,
defense-in-depth invariant at the model layer, mirroring P4-C1-R-01's
dual-layer (scanner + model) pattern for `DiscoveredMediaItem.source_path`.
No `exists()`/`resolve()`/`realpath()` call appears anywhere in this
package.

## 9. Windows filename safety strategy

Centralized in one function, `fc2_organizer.planning.paths.validate_path_component`
(section 10 of the contract spec): illegal characters (`< > : " / \ | ? *`),
ASCII control characters, trailing dot/space, and Windows reserved device
names (`CON`/`PRN`/`AUX`/`NUL`/`COM1`-`9`/`LPT1`-`9`, case-insensitive,
checked against the portion before the first dot) are all rejected with
`UnsafeTargetComponentError`. Both `planner.py` and `models.py` call into
this single function -- no sanitization logic is duplicated. The frozen
v1.0 default values never trigger it.

## 10. Collision policy

**Fail closed, frozen, not a knob.** `InternalTargetCollisionError` if any
two of a plan's own generated basenames would collide under Windows
case-insensitive semantics. No automatic suffixing (`(1)`/`_2`/`-copy`), no
silent rename. `OutputPolicy` has no collision-strategy field;
`build_organize_plan` has no `on_collision=` parameter.

## 11. Overwrite policy

**Never, for source media, target media, and every generated artifact.**
Frozen constant, not represented as a field/parameter anywhere in this
package (verified directly: `test_overwrite_policy_is_frozen_never_and_not_a_caller_knob`
checks `OutputPolicy` has no `overwrite`/`overwrite_policy` attribute and
`build_organize_plan`'s signature has no `overwrite` parameter). No real
filesystem preflight (existing-file detection) is performed -- P4-C2
performs zero filesystem access of any kind; a real preflight against what
actually exists on disk is explicitly deferred to a future execution
package.

## 12. Immutability strategy

Every public model (`OutputPolicy`, `PlannedPath`, `PlannedOperation`,
`OrganizePlan`) is `@dataclass(frozen=True, slots=True)`.
`OrganizePlan.operations` is a real `tuple[PlannedOperation, ...]` (not a
list); there is no caller-owned mutable container anywhere in the object
graph. `test_planning_models.py::TestOrganizePlanImmutability` proves scalar
reassignment raises `dataclasses.FrozenInstanceError`, `operations[i] = x`
raises `TypeError` (tuple item assignment), `operations` is a real `tuple`
(not `isinstance(..., list)`), and no mutator method (`append`/`extend`/...)
exists on the public surface.

## 13. Determinism strategy

`build_organize_plan` reads no randomness, no wall clock, no filesystem
enumeration order, and generates no UUID -- every target path is a pure
string computation from its five inputs. `test_identical_input_produces_identical_plan`
and the synthetic gate's `test_synthetic_gate_all_plans_deterministic_on_replay`
(400 items, replayed twice) both assert full `OrganizePlan.__eq__` equality
(dataclass field-by-field, including `operations` tuple ordering) across
repeated calls with identical inputs.

## 14. No-mutation evidence

Two independent proofs (`test_planning_no_mutation.py`), per the brief's
explicit requirement that "looks like it doesn't write" is not sufficient
evidence:

1. **Before/after directory snapshot.** A real directory with existing
   files is snapshotted (path -> content) before and after building five
   plans against a library root that itself does not exist on disk; the
   snapshots are asserted byte-identical, and the (never-created) library
   root is asserted to still not exist.
2. **Mutation-API trap.** Every common mutation API is monkeypatched to
   raise if called: `os.mkdir`/`makedirs`/`rename`/`replace`/`remove`/
   `unlink`/`rmdir`/`removedirs`/`chmod`/`utime`/`symlink`/`link`,
   `shutil.move`/`copy`/`copy2`/`copyfile`/`copytree`/`rmtree`,
   `pathlib.Path.mkdir`/`write_text`/`write_bytes`/`touch`/`rename`/
   `replace`/`unlink`/`rmdir`/`symlink_to`, and builtin `open()` in any
   write-capable mode. `build_organize_plan` is called repeatedly under all
   of these traps and must run to completion without tripping any of them.
   A self-test (`test_blocked_mutation_trap_is_itself_effective`) proves the
   trap mechanism itself actually catches a real mutation call (mirrors
   P4-C1's `UnguardedScheduler`-style self-test pattern from C4).

## 15. Architecture-boundary evidence

`test_planning_architecture.py`: static AST scan of every `planning/*.py`
file forbidding `amane` and the `fc2_metadata_core`/discovery internal
prefixes listed in the contract spec section 1; an explicit allow-list
check that only `fc2_metadata_core.models`/`.normalize` and the bare
`fc2_organizer.discovery` package are ever imported; a dynamic meta-path
block proving `amane` cannot be imported even lazily while
`build_organize_plan` is exercised end to end under the block (see the
contract spec section 1 for why the dynamic block covers only `amane`, not
`fc2_metadata_core` internals -- that boundary is covered statically
instead, for a structural reason specific to `fc2_metadata_core`'s own
`__init__.py`); confirmation `amane` is not actually installed in this
environment (sanity check the block is meaningful); and a scope guard that
`fc2_organizer` now has exactly `{discovery, planning}` as subpackages.

## 16. Targeted tests

```bash
# From fc2-organizer/:
python -m pytest tests/unit/planning tests/contract/test_planning_architecture.py -q
```

```text
179 passed
```

(Also reran `tests/contract/test_discovery_architecture.py` alongside --
all pre-existing P4-C1 architecture tests still pass with the one updated
assertion, see section 4.)

## 17. Full suite

```bash
python -m pytest -q
```

```text
2659 passed, 4 skipped
```

`2480 (P4-C1 final-closure baseline) + 179 (new P4-C2 tests) = 2659`. No
pre-existing test was modified beyond the single assertion in section 4, no
pre-existing test newly failed, and the 4 skips are the same pre-existing
Windows symlink-privilege skips from P4-C1 (unaffected, unchanged reasons).

(`--basetemp=<dir>` was used in this environment only to avoid the same
pytest-internal teardown race against a shared `%TEMP%\pytest-of-<user>`
directory that P4-C1's handoff documented (section 9 there) -- irrelevant
to the tests themselves.)

## 18. Synthetic planning gate

```text
PASS
```

`test_planning_synthetic_gate.py` builds 400 synthetic
`DiscoveredMediaItem`s across 7 extensions, 400 distinct canonical FC2
numbers, and 5 Unicode/emoji titles, fully offline, on a fixed
(non-random) layout. Verifies: full replay determinism (built twice,
asserted `==`), full target containment for every generated path, zero
internal collisions across all 400 unique-number plans' media targets, zero
Unicode-title leakage into any target path, correctness under a custom
`OutputPolicy` (containment + determinism still hold), zero filesystem
mutation (library root never created), and (via a dedicated AST scan of the
`planning/` source tree) zero reachable import of `socket`/`httpx`/
`urllib`/`requests`/`asyncio`.

## 19. Known limitations

* **`fc2_organizer/__init__.py` does not eagerly import `planning`.** This
  was discovered as a real regression during development (not merely a
  design choice made up front): the first version of this file did
  `from fc2_organizer import discovery, planning`, which broke P4-C1's own
  frozen `test_discover_media_runs_end_to_end_with_forbidden_modules_blocked_at_runtime`
  test, because `fc2_metadata_core`'s own `__init__.py` eagerly imports
  `aggregation`/`batch`/`http`/`sources` as soon as *any* of its submodules
  (including the allowed `models`) is imported -- so eagerly importing
  `planning` from `fc2_organizer/__init__.py` made that transitive load
  happen merely by importing `fc2_organizer.discovery`. Fixed by not
  eagerly importing `planning`; it is reached via
  `from fc2_organizer import planning` (an ordinary, explicit subpackage
  import). Documented in the contract spec section 1 and in this file so a
  future package does not reintroduce the same regression.
* No cross-check that `metadata.number == canonical_number`. The default
  v1.0 path derivation does not read `metadata.number` at all (only
  `meets_minimum_success()` is checked), so a caller could in principle
  pass metadata for a different number than `canonical_number`; P4-C2 does
  not treat this as a planning error, since nothing in the brief requires
  it and the resulting plan is still internally consistent (it plans
  correctly for `canonical_number`, which is the authoritative identity
  here). Left for a future round to decide if it should become an error.
* `OrganizePlan` does not carry the `OutputPolicy` used to build it. Not
  required by the brief's "at least include" field list (section 6 of the
  task); omitted deliberately to avoid expanding the plan's responsibility
  beyond what was asked.
* No real-filesystem preflight of any kind (existing-file detection,
  writability probing) -- by design, this is P4-C2's central constraint
  (ZERO FILESYSTEM MUTATION), not an oversight; deferred to a future
  execution package per the brief.

## 20. Carried debts (not triggered / not addressed by P4-C2)

```text
P4-C1-R-02, P4-C1-R-03, P4-C1-R-04, P4-C1-R-05,
C2-L2, P2-R-05, P2-R-06, P2-R-07, P2-R-10,
C3-N1, C3-N2, C3-N3, C3-N4,
C4-N1, C4-R1-N1, C4-R1-N2, C4-R1-N3,
F3, F5, C5-R1-L1
```

None of these are read, touched, or relevant: `fc2_organizer.planning`
has zero runtime dependency on any module any of them concern (its only
`fc2_metadata_core` dependency is the read-only `models`/`normalize`
boundary; it has zero dependency on `batch`, `aggregation`,
`resource_control`, `sources`, or `http`). None was triggered during
development; none was fixed, upgraded, or reopened.

## 21. `git diff --check`

```text
clean (no output)
```

## 22. `git status --porcelain`

Clean after the code commit; clean again after this docs commit (verify
with `git status --porcelain` -- expected empty once this file is
committed).

## 23. Push

To be pushed to `origin/claude/phase4-c2-organize-plan` after the docs
commit; Remote Head recorded above once pushed.

## 24. Independent Review

```text
REQUIRED
```

## 25. P4-C2

```text
NOT CLOSED
```

## 26. Phase 4

```text
NOT CLOSED
```
