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

---

# R1 Closure -- P4-C2-GOV-01, P4-C2-GOV-02, P4-C2-GOV-03

The section above is the original, as-reviewed P4-C2 submission and is
left unmodified for history. This section records the R1 incremental-
closure round.

## R1.1 Coordinates

```text
Reviewed-Failed Code Head = 1a4ca88bf9d10ca94f2a8a640b734c96c558a8a8
Previous Docs Head        = e8ebd153b2160f3dfc812668c34cc8e382614ee4
R1 Code Review Candidate  = d43608645a960401c0cf0cc03d56418bdfa760be
R1 Docs Head              = <this commit; see git log after commit>
R1 Code Review Range      = e8ebd153b2160f3dfc812668c34cc8e382614ee4..d43608645a960401c0cf0cc03d56418bdfa760be
R1 Docs Review Range      = d43608645a960401c0cf0cc03d56418bdfa760be..<R1 Docs Head>
```

## R1.2 Governance context

Two independent Level 1 reviews conflicted on finding severity. Per the
issuing instruction, this round does not build against either reviewer's
own finding numbering; it builds solely against the three GOV findings the
instruction itself specified as the arbitrated, authoritative closure
scope:

```text
P4-C2-GOV-01   HIGH / BLOCKING            -- vacuous synthetic-gate network-isolation test
P4-C2-GOV-02   MEDIUM / CLOSURE-REQUIRED  -- legitimate absolute roots wrongly judged "escaped"
P4-C2-GOV-03   MEDIUM / CLOSURE-REQUIRED  -- ambiguous Windows rooted-but-driveless library_root
```

## R1.3 Findings addressed

### P4-C2-GOV-01 -- CLOSED

**Defect:** `test_planning_synthetic_gate.py::test_synthetic_gate_no_network_import_reachable`
computed its production-source directory as
`Path(__file__).resolve().parents[2] / "src" / "fc2_organizer" / "planning"`.
This file lives at `tests/unit/planning/test_planning_synthetic_gate.py`;
`parents[2]` from there is `tests/` (one directory too shallow -- the value
`2` was copied from `tests/contract/test_planning_architecture.py`, which
*is* one directory shallower, where `parents[2]` correctly resolves to the
repo root). The computed path was therefore the nonexistent
`tests/src/fc2_organizer/planning`; `rglob("*.py")` silently returned an
empty list, and the `for path in ...: assert ...` loop body never executed
-- a vacuous test that always passed regardless of what the production code
actually imported.

**Repair:** fixed the index to `parents[3]` (verified directly, R1.5 Repro
A). Added `test_synthetic_gate_planning_src_root_resolves_and_has_production_files`,
which asserts the resolved directory exists, `rglob("*.py")` returns a
non-empty file list, and that list contains every known production module
by name (`__init__.py`, `errors.py`, `models.py`, `paths.py`, `planner.py`,
`policy.py`) -- so a future accidental re-introduction of the same
off-by-one is caught by an explicit assertion, not merely by the guard
"happening" to scan the right files. Extracted the AST-walking scan itself
into a small, reusable, pure function (`_scan_forbidden_imports`), then
added two planted-import proof tests
(`test_network_guard_fails_on_planted_import_statement`,
`test_network_guard_fails_on_planted_import_from_form`) that write `import
socket` / `from urllib import request` into an isolated `tmp_path` file
(never a production file) and assert the scanner detects it -- proving the
guard can actually FAIL, not just proving it PASSes on whatever happens to
be clean today. Added a fourth test
(`test_network_guard_does_not_false_positive_on_ordinary_stdlib_imports`)
proving the same scanner does not flag ordinary allowed imports this very
package uses (`os`, `pathlib`, `dataclasses`, `enum`).

**No production code was changed to make this pass** -- both original
independent reviewers already confirmed `fc2_organizer.planning` has no
real network dependency; this was purely a test-evidence defect, exactly
as the issuing instruction characterized it.

### P4-C2-GOV-02 -- CLOSED

**Defect:** `fc2_organizer.planning.paths.is_contained_within` computed
segments via `os.path.normpath(candidate_or_root).split(os.sep)`. A bare
drive root (`C:\`) or a bare UNC share root (`\\server\share\`) normalizes
to a string *ending* in the separator; splitting that on `os.sep` produces
a spurious trailing empty string segment, inflating the root's part count.
The containment check's early-exit guard
(`len(candidate_parts) <= len(root_parts): return False`) then fired for a
*genuine* child (`C:\library-child` under `C:\`) purely because of that
extra phantom segment -- a false "target escapes root" verdict for a
perfectly legitimate absolute root.

**Repair:** `is_contained_within` now computes segments via
`pathlib.Path(...).parts` instead of `os.path.normpath(...).split(os.sep)`.
`pathlib` collapses a drive-and-root (`C:\` -> `('C:\\',)`) or a
UNC-share-and-root (`\\server\share\` -> `('\\\\server\\share\\',)`) into a
*single* anchor part with no trailing-empty-segment artifact, regardless of
whether the string carries a trailing separator or not. This is still
purely lexical (`Path` construction and `.parts` perform zero filesystem
access -- no `stat`/`exists`/`resolve`) and still segment-based, not
`str.startswith` (so `C:\library2` still correctly compares as *not*
contained under `C:\library` -- verified unchanged,
`test_prefix_collision_without_separator_boundary_is_not_contained` and the
new `test_no_string_startswith_false_positive_on_drive_root`).

Directly reproduced and fixed (R1.5 Repro C): `C:\` now correctly contains
`C:\FC2-1234567` and `C:\FC2-1234567\poster.jpg`; `D:\FC2-1234567` is
correctly excluded from `C:\`; `\\server\share\` correctly contains
`\\server\share\FC2-1234567`; `\\server\other\FC2-1234567` is correctly
excluded.

### P4-C2-GOV-03 -- CLOSED

**Governance decision (frozen by this round, per the issuing instruction):**
`library_root` for P4-C2 v1.0 must be an **unambiguous, fully-qualified
absolute path**. A Windows *rooted-but-driveless* form (`\lib`, `/lib`) is
rejected fail-closed, never silently bound to whichever drive happens to be
current, and never decided by relying on `os.path.isabs()`'s own
cross-Python-version treatment of that form.

**Repair:** added `fc2_organizer.planning.paths.is_fully_qualified_absolute_root`
as the single, centralized library-root qualification boundary (contract
section 11a):

* **Windows** (`os.name == "nt"`): accepted only if `os.path.splitdrive`
  finds a real drive with a root (`C:\lib`, `C:/lib`) or a UNC share
  (`\\server\share`, `\\server\share\lib`, with or without a trailing
  separator -- a bare share is already unambiguous, unlike a bare drive
  letter `C:` alone, which means "current directory on that drive" and is
  rejected). Rejected: `library`, `.\library`, `..\library`, `C:library`,
  `\library`, `/library`.
* **POSIX** (anything else, chosen by the *current runtime OS*, never by
  guessing from the string's shape): plain `os.path.isabs(path)` --
  `/library` remains legal, `library` remains rejected.

Wired into both `planner.py` (`InvalidLibraryRootError`, replacing the bare
`os.path.isabs()` call) and `models.py`'s redundant model-layer check on
`OrganizePlan.library_root` (`OrganizePlanContractError`), mirroring the
existing dual-layer pattern already used for target containment
(section 11) and for `DiscoveredMediaItem.source_path` in P4-C1-R-01.

Directly reproduced (R1.5 Repro D): `\lib` and `/lib` both rejected by
`is_fully_qualified_absolute_root` and by `build_organize_plan` itself
(raises `InvalidLibraryRootError`); `C:\lib` and `\\server\share\lib` both
accepted; `build_organize_plan(..., library_root="C:\\")` (the exact
GOV-02/GOV-03 boundary case) succeeds end-to-end and produces
`target_directory == "C:\\FC2-1234567"`.

## R1.4 Exact changed files

**R1 Code Review Candidate (`d436086`), 8 files, all modified (no new
files, no renames):**

```text
fc2-organizer/docs/specifications/PHASE4_ORGANIZE_PLAN_CONTRACT.md    (M)
fc2-organizer/src/fc2_organizer/planning/models.py                    (M)
fc2-organizer/src/fc2_organizer/planning/paths.py                     (M)
fc2-organizer/src/fc2_organizer/planning/planner.py                   (M)
fc2-organizer/tests/unit/planning/test_planning_models.py             (M)
fc2-organizer/tests/unit/planning/test_planning_paths.py              (M)
fc2-organizer/tests/unit/planning/test_planning_planner.py            (M)
fc2-organizer/tests/unit/planning/test_planning_synthetic_gate.py     (M)
```

No file under `fc2_metadata_core/**` or `fc2_organizer/discovery/**` was
touched. No new source file was added (the brief permitted a new
path/root helper "if necessary, minimized" -- `is_fully_qualified_absolute_root`
was added as a new *function* inside the already-existing, already-central
`paths.py`, not as a new module).

**R1 Docs Head (this commit), 1 file:**

```text
fc2-organizer/docs/review/P4_C2_HANDOFF.md   (M -- this section)
```

## R1.5 Direct reproductions (outside pytest)

```text
Repro A -- network guard scans real production files:
  planning src root resolved correctly (parents[3], not parents[2])
  production file count: 6 (__init__.py, errors.py, models.py, paths.py,
  planner.py, policy.py)
  -> PASS

Repro B -- planted 'import socket' causes guard FAIL:
  planted into an isolated tempfile.TemporaryDirectory() file (never a
  repo file); _scan_forbidden_imports([planted], ...) returned one
  violation naming 'socket'
  -> PASS (guard detects a real violation, not just passes on clean code)
  temp directory auto-cleaned by the context manager; git status
  confirmed clean immediately after (no leftover modification)

Repro C -- Windows drive-root / UNC containment:
  is_contained_within(r"C:\FC2-1234567", r"C:\\")                -> True
  is_contained_within(r"C:\library-child", r"C:\\")               -> True  (exact GOV-02 repro)
  is_contained_within(r"D:\FC2-1234567", r"C:\\")                  -> False
  is_contained_within(r"\\server\share\FC2-1234567", r"\\server\share\\") -> True
  is_contained_within(r"\\server\other\FC2-1234567", r"\\server\share\\") -> False
  -> PASS

Repro D -- Windows rooted-but-driveless root fails closed:
  is_fully_qualified_absolute_root(r"\lib")          -> False
  is_fully_qualified_absolute_root("/lib")            -> False
  is_fully_qualified_absolute_root(r"C:\lib")         -> True
  is_fully_qualified_absolute_root(r"\\server\share\lib") -> True
  build_organize_plan(..., library_root=r"\lib")      -> raises InvalidLibraryRootError
  build_organize_plan(..., library_root="C:\\")       -> succeeds;
    target_directory.absolute_path == "C:\\FC2-1234567"
  -> PASS
```

This host is Windows (win32, Python 3.12.10), so Repros A-D above all ran
for real. The POSIX-side unit coverage added in R1 (`is_fully_qualified_absolute_root`
POSIX-absolute-accepted / relative-rejected / dot-relative-rejected, and
`build_organize_plan`'s `test_posix_absolute_root_still_accepted`) is
present and correct but **NOT RUN** on this host (`pytest.mark.skipif(os.name
== "nt", ...)`); per the issuing instruction's explicit allowance for this
case, the coverage exists and is platform-gated correctly rather than
being executed here.

## R1.6 Targeted tests

```text
212 passed, 4 skipped
```

Command: `python -m pytest tests/unit/planning tests/contract/test_planning_architecture.py -q`
(179 prior P4-C2 tests + 33 new passing + 4 new POSIX-only skips, all
green; the 4 skips are the new POSIX-gated tests, correctly inert on this
Windows host -- not the same skips as the full suite's pre-existing
P4-C1 symlink-privilege skips, see R1.7).

## R1.7 Full suite

```text
2692 passed, 8 skipped
```

Command: `python -m pytest -q`. `2659 (original P4-C2 submission baseline)
+ 33 (new R1 tests, passing on this host) = 2692`; `4 (pre-existing P4-C1
symlink-privilege skips) + 4 (new R1 POSIX-gated skips on this Windows
host) = 8`. No pre-existing test was modified, newly failing, or newly
skipped for a different reason than before.

## R1.8 P4-C1 frozen protection

No file under `src/fc2_organizer/discovery/**` or `src/fc2_metadata_core/**`
was read for the purpose of modification, and none was touched. The full
suite's unchanged P4-C1 test count and pass status (section R1.7) is the
behavioral proof; `git status --porcelain` after the R1 commit (section
R1.11) is the file-level proof.

## R1.9 Preserved behaviors (not regressed)

Verified via the unmodified, still-100%-green pre-R1 test files (`test_planning_models.py`'s
immutability tests, `test_planning_planner.py`'s canonical-number/metadata/
source-identity/default-layout/title-isolation/policy/collision/overwrite/
determinism tests, `test_planning_no_mutation.py`, `test_planning_architecture.py`'s
dependency-boundary tests) plus the full-suite regression count: Deep
Immutability, Canonical Number Boundary, Metadata minimum-success
validation, Source Identity, Default Layout, Title Isolation, `OutputPolicy`
artifact naming, Collision = FAIL CLOSED, Overwrite = NEVER (frozen, no new
field/parameter added -- re-verified directly,
`test_overwrite_policy_is_frozen_never_and_not_a_caller_knob` still passes
unmodified), Windows component validation, no filesystem mutation,
filesystem-state independence, architecture boundary, package import
safety, determinism -- all unchanged, none weakened, none re-scoped.

## R1.10 Carried findings (explicitly not addressed this round)

```text
metadata.number != canonical_number identity gap
  -> CARRIED (frozen contract section 9 defines metadata as validation-only;
     no cross-check added; must close before OrganizePlan/metadata/NFO
     publication binding)

OrganizePlan operation-graph model-level hardening
  -> CARRIED (executor-entry hardening, deferred to when an executor
     actually consumes an arbitrary OrganizePlan)

overwrite executor semantics
  -> frozen NEVER (unchanged); a future executor must enforce it;
     not a P4-C2 plan-field defect, no field/parameter added this round

CON.txt / COM(super-1).jpg style contract-external Windows edge cases
  -> not addressed (out of the frozen contract's scope, per the issuing
     instruction; not touched)

All prior carried debts unchanged:
P4-C1-R-02, P4-C1-R-03, P4-C1-R-04, P4-C1-R-05,
C2-L2, P2-R-05, P2-R-06, P2-R-07, P2-R-10,
C3-N1, C3-N2, C3-N3, C3-N4,
C4-N1, C4-R1-N1, C4-R1-N2, C4-R1-N3,
F3, F5, C5-R1-L1
```

## R1.11 `git diff --check`

```text
clean (no output)
```

## R1.12 `git status --porcelain`

Clean after the R1 code commit; clean again after this R1 docs commit
(verify with `git status --porcelain`). No stray files (`_tmp_probe*.py`,
`_tmp_repro.py` used during development were deleted before either commit
and never staged).

## R1.13 Independent R1 Closure Review

```text
REQUIRED
```

## R1.14 P4-C2

```text
NOT CLOSED
```

## R1.15 Phase 4

```text
NOT CLOSED
```

---

# R2 Closure -- P4-C2-R1-01

The two sections above (original P4-C2, R1) are left unmodified for
history. This section records the R2 incremental-closure round.

## R2.1 Coordinates

```text
R1 Reviewed-Failed Code Head = d43608645a960401c0cf0cc03d56418bdfa760be
Previous Docs Head           = bb8b78ffabf2b4a66c342813b089675b08b29d78
R2 Code Review Candidate     = f56bfeef9fac2bd6a2e11e6e9065d3aea1b05ee7
R2 Docs Head                 = <this commit; see git log after commit>
R2 Code Review Range         = bb8b78ffabf2b4a66c342813b089675b08b29d78..f56bfeef9fac2bd6a2e11e6e9065d3aea1b05ee7
R2 Docs Review Range         = f56bfeef9fac2bd6a2e11e6e9065d3aea1b05ee7..<R2 Docs Head>
```

```text
P4-C2-GOV-01: REMAINS CLOSED (reverified, R2.5)
P4-C2-GOV-02: REMAINS CLOSED (reverified, R2.5)
P4-C2-GOV-03: REMAINS CLOSED (reverified, R2.5)
P4-C2-R1-01:  CLOSED by this round (R2.5 Repro A/C/D)
```

## R2.2 Finding addressed

```text
P4-C2-R1-01
Severity: HIGH / BLOCKING
```

**Defect:** R1's fix for P4-C2-GOV-02 switched
`fc2_organizer.planning.paths.is_contained_within` from
`os.path.normpath(...).split(os.sep)` to `pathlib.Path(...).parts` to fix a
trailing-empty-segment bug on bare drive/UNC roots. `pathlib.PurePath.parts`
is a pure string-splitting operation, though -- it does **not** collapse
`.`/`..` segments. Consequently a candidate whose *raw* segments happened
to start with the root's segments compared as "contained" even when the
path's actual lexical meaning (what it would resolve to once `..` is
accounted for) escapes the root entirely:

```text
root:      C:\library
candidate: C:\library\..\outside\FC2-1234567.mp4

R1's Path(...).parts comparison: ('C:\\', 'library', 'outside_wrongly_seen_as_child')
  -- wrong: raw segments ('C:\\', 'library', '..', 'outside', 'FC2-1234567.mp4')
     happen to start with the root's ('C:\\', 'library'), so the naive
     comparison said "contained" == True

actual lexical meaning: C:\outside\FC2-1234567.mp4 -- outside C:\library entirely
```

The same hazard applied to `C:\library\FC2-1\..\..\outside\...` and to the
POSIX equivalent `/library/../outside/file`.

## R2.3 Exact changed files

```text
fc2-organizer/src/fc2_organizer/planning/paths.py                     (M)
fc2-organizer/tests/unit/planning/test_planning_paths.py              (M)
fc2-organizer/tests/unit/planning/test_planning_models.py             (M)
fc2-organizer/docs/review/P4_C2_HANDOFF.md                            (this section)
```

`planner.py`, `models.py` (other than the test file), `policy.py`,
`errors.py` were **not** touched -- the defect and its fix are entirely
contained within `paths.is_contained_within`'s own segment-computation
logic; nothing about the public API, error taxonomy, or default layout
changed. `PHASE4_ORGANIZE_PLAN_CONTRACT.md` was **not** touched this round:
its section 11 already promised pure-lexical containment and an
independent model-layer re-check; neither promise changed, only the
implementation's correctness in fulfilling it.

## R2.4 Normalize-then-split strategy

```python
candidate_parts = Path(os.path.normpath(candidate)).parts
root_parts = Path(os.path.normpath(root)).parts
```

`os.path.normpath` is run on **both** strings *before* splitting into
parts. This composes the fix for both hazards without reintroducing either:

* **R1-01's hazard** (un-collapsed `.`/`..`) is closed because `normpath`
  lexically collapses `.`/`..` first -- still pure string manipulation, zero
  filesystem access (no `stat`/`exists`/`resolve`/`realpath`).
* **GOV-02's original hazard** (a bare anchor's trailing separator producing
  a spurious empty `str.split(os.sep)` segment) is *not* reintroduced,
  because the fix never returns to plain `str.split(os.sep)` -- `Path(...).parts`
  is still used for the actual segmentation, and `normpath` never leaves a
  bare root's trailing separator in a form that would trip `Path.parts`'s
  anchor-collapsing (`os.path.normpath("C:\\\\")` is `"C:\\"`,
  `Path("C:\\").parts` is `('C:\\',)`, unchanged from R1's behavior).

**Anchor clamping verified directly** (not assumed): `os.path.normpath`
clamps a leading `..` at a drive or UNC-share anchor exactly the way real
Windows path resolution does --
`os.path.normpath(r"\\server\share\..\other\x")` yields
`\\server\share\other\x` (stays **inside** the share), never
`\\server\other\x` (which would be a different share). This mirrors the
drive-root `..`-clamping precedent already established for this project by
the P4-C1-R2-01/R3 rounds' independent `GetFullPathNameW` verification (R3.5
of the P4-C1 handoff) -- `..` cannot cross a drive-letter or UNC-share
boundary on Windows, by the OS's own lexical rules, not merely by this
package's convention.

**Consequence for the "different share" test list item:** the brief's
section 7 UNC example (`\\server\share\..\other\FC2-1234567`) is therefore
*correctly* judged **contained** (its true lexical meaning stays inside
`share`, it never actually reaches `other`) -- this is the right answer
under genuine Windows lexical semantics, not an escape being wrongly
accepted. A candidate that names a genuinely different share **from the
start** (`\\server\other\FC2-1234567`, never reached via `..`) remains
correctly rejected, unchanged from GOV-02 (`test_different_unc_share_from_the_start_is_still_not_contained`).

## R2.5 Direct reproductions (outside pytest)

```text
Repro A -- dot-dot escape correctly rejected:
  is_contained_within(r"C:\library\..\outside\file.mp4", r"C:\library") -> False
  -> PASS (P4-C2-R1-01 closed)

Repro B -- bare drive root still correctly contains its child (GOV-02 not regressed):
  is_contained_within(r"C:\FC2-1234567", "C:\\") -> True
  -> PASS

Repro C -- UNC root child / different share:
  is_contained_within(r"\\server\share\FC2-1234567", "\\server\share\") -> True
  is_contained_within(r"\\server\other\FC2-1234567", "\\server\share\") -> False
  is_contained_within(r"\\server\share\a\..\FC2-1234567", "\\server\share\") -> True
  is_contained_within(r"\\server\share\..\other\FC2-1234567", "\\server\share\") -> True
    (clamped at the share boundary -- see R2.4; this is the lexically
    correct verdict, not a residual defect)
  -> PASS

Repro D -- hand-built OrganizePlan with dot-dot-escaping target fails closed:
  OrganizePlan(..., target_media_path=PlannedPath(r"C:\library\..\outside\FC2-1234567.mp4"), ...)
  -> raised TargetEscapesLibraryRootError:
     "OrganizePlan.target_media_path ('C:\\library\\..\\outside\\FC2-1234567.mp4')
      is not contained under library_root ('C:\\library')"
  -> PASS (contract section 11's promised model-layer re-check verified for real)

Repro E -- POSIX /library/../outside:
  Host is Windows (os.name == 'nt') -> NOT RUN as a live filesystem-path
  reproduction on this host, honestly reported. Platform-correct pure-
  semantics unit coverage exists instead
  (TestIsContainedWithinPosixDotDot, 4 tests, @pytest.mark.skipif(os.name
  == "nt", ...)) and will execute for real with no code change required on
  a POSIX host. Sanity-checked by source inspection that
  is_contained_within's implementation calls the OS-native
  os.path.normpath (which dispatches to posixpath.normpath on a real
  POSIX host), not a Windows-only helper.
```

This host is Windows (win32, Python 3.12.10), so Repros A-D ran for real;
Repro E's platform-specific runtime execution is honestly reported as
NOT RUN with equivalent coverage in place, per the issuing instruction's
explicit allowance.

## R2.6 Targeted tests

```text
223 passed, 10 skipped
```

Command: `python -m pytest tests/unit/planning tests/contract/test_planning_architecture.py -q`
(212 prior tests + 11 new passing + 6 new POSIX-gated skips, all green;
the 10 skips = 4 pre-existing POSIX-gated skips from R1 + 6 new
POSIX-gated skips from R2, all correctly inert on this Windows host).

## R2.7 Full suite

```text
2703 passed, 14 skipped
```

Command: `python -m pytest -q`. `2692 (R1 full-suite baseline) + 11 (new
R2 tests, passing on this host) = 2703`; `8 (R1 baseline skips) + 6 (new
R2 POSIX-gated skips) = 14`. No pre-existing test was modified, newly
failing, or newly skipped for a different reason than before.

## R2.8 GOV-01/02/03 reverified unchanged

* **GOV-01 (network guard):** untouched this round --
  `test_planning_synthetic_gate.py` was not in the R2 changed-files list
  (section R2.3). Full-suite pass count confirms
  `test_synthetic_gate_no_network_import_reachable` and its planted-import
  proof tests are still green.
* **GOV-02 (drive/UNC containment):** re-verified directly, R2.5 Repro B/C
  -- the exact GOV-02 reproductions (`C:\` contains `C:\FC2-1234567`;
  `\\server\share\` contains its child; a different drive/share is
  excluded) still pass, now composed with the R1-01 dot-collapsing fix
  rather than superseded by it.
* **GOV-03 (fully-qualified library_root boundary):** untouched this round
  -- `is_fully_qualified_absolute_root` was not modified; its own test
  class (`TestIsFullyQualifiedAbsoluteRoot`) and the planner-level tests
  are unchanged and still green in the full-suite run.

## R2.9 Preserved behaviors (not regressed)

Same checklist as R1.9, reverified via the full-suite regression count:
Deep Immutability, Canonical Number Boundary, Metadata minimum-success
validation, Source Identity, Default Layout, Title Isolation, `OutputPolicy`
artifact naming, Collision = FAIL CLOSED, Overwrite = NEVER (frozen, no
field/parameter added), Windows component validation, no filesystem
mutation, filesystem-state independence, architecture boundary, package
import safety, determinism -- all unchanged. `build_organize_plan` itself
was not modified this round (section R2.3); identical input continues to
produce an identical plan, and every plan's targets continue to be
contained (existing planner-level tests, unmodified, still pass) --
the R1-01 defect was only reachable through a *hand-built* `OrganizePlan`
or a direct `is_contained_within` call, never through the public
`build_organize_plan` entry point, since every caller-controlled path
component it builds from is already validated separator/`..`-free before
being joined (`validate_path_component`). No new planner-level test was
therefore needed to prove no regression there; the model-layer and
helper-level tests are where this defect could actually manifest.

## R2.10 Carried findings (explicitly not addressed this round)

```text
P4-C2-R1-02
  -> CARRIED / LOW (bare "\\server" may be accepted by
     is_fully_qualified_absolute_root; not touched -- GOV-03's
     implementation was not modified this round, so this behavior is
     unchanged from R1)

metadata.number != canonical_number identity gap
  -> CARRIED (contract section 9 defines metadata as validation-only;
     must close before OrganizePlan/metadata/NFO publication binding)

OrganizePlan operation-graph model-level hardening
  -> CARRIED (executor-entry hardening, deferred to when an executor
     actually consumes an arbitrary OrganizePlan)

overwrite executor semantics
  -> frozen NEVER (unchanged); a future executor must enforce it; not a
     P4-C2 plan-field defect, no field/parameter added this round

CON.txt / COM(super-1).jpg style contract-external Windows edge cases
  -> not addressed (out of the frozen contract's scope)

All prior carried debts unchanged:
P4-C1-R-02, P4-C1-R-03, P4-C1-R-04, P4-C1-R-05,
C2-L2, P2-R-05, P2-R-06, P2-R-07, P2-R-10,
C3-N1, C3-N2, C3-N3, C3-N4,
C4-N1, C4-R1-N1, C4-R1-N2, C4-R1-N3,
F3, F5, C5-R1-L1
```

## R2.11 `git diff --check`

```text
clean (no output)
```

## R2.12 `git status --porcelain`

Clean after the R2 code commit; clean again after this R2 docs commit
(verify with `git status --porcelain`). No stray files (`_tmp_probe_r2.py`,
`_tmp_repro_r2.py` used during development were deleted before either
commit and never staged).

## R2.13 Independent R2 Closure Review

```text
REQUIRED
```

## R2.14 P4-C2

```text
NOT CLOSED
```

## R2.15 Phase 4

```text
NOT CLOSED
```

---

# Final Closure -- P4-C2

The sections above (original P4-C2, R1, R2) are left unmodified for
history. This section is a docs-only governance record of the final
independent closure decision; it introduces no code or test change and
freezes no new technical claim beyond what R1/R2 already established.

```text
Phase:                       4
Package:                     P4-C2 Immutable Organize Plan
Status:                      CLOSED
Final Level:                 Level 1 PASS
Final Reviewed Code Head:    f56bfeef9fac2bd6a2e11e6e9065d3aea1b05ee7
Previous Docs Head:          fa2655408f6cff8e2376d90b953cb477b16c084d
```

## Final findings disposition

```text
P4-C2-GOV-01   CLOSED
P4-C2-GOV-02   CLOSED
P4-C2-GOV-03   CLOSED
P4-C2-R1-01    CLOSED

P4-C2-R1-02    CARRIED / LOW / non-blocking
```

**All blocking P4-C2 findings are closed. Remaining findings are
explicitly carried as non-blocking, or stand as entry-gates for a later
package** -- they were not fixed, not downgraded, and not reopened by this
closure; see R1.10/R1.11/R2.10 above and "Carried findings" and "Future
entry gates" below for what each concerns and why none was addressed
in-round.

## Independent closure evidence

Two independent Level 1 review outputs were obtained for this R2 round.

**Reviewer A -- PASS.** Ran the suite directly and reported real numbers:

```text
Targeted: 223 passed / 10 skipped
Full suite: 2703 passed / 14 skipped
```

and independently, substantively verified: normal-root dot/dot-dot
containment (the exact P4-C2-R1-01 defect class), drive-root containment,
UNC-root containment, the Windows lexical `normpath` anchor-clamping
semantics the fix depends on, hand-built-`OrganizePlan` escape rejection at
the model layer, and that both the network guard (GOV-01) and the
fully-qualified root boundary (GOV-03) remain closed and unregressed.

**Reviewer B -- substantive result PASS, procedural verdict BLOCKED.**
This review's own read of the code and diff reached the same substantive
conclusion as Reviewer A: P4-C2-R1-01 closed, GOV-01/02/03 remain closed,
no new blocking code finding. However, that reviewer's execution
environment had no local repository checkout available to it, so it could
not run the targeted pytest suite, could not run the full pytest suite,
and could not run a literal local `git diff --check` -- and its own report
accordingly surfaced a procedural `BLOCKED` verdict for those specific,
environment-caused gaps.

**This `BLOCKED` verdict was caused by the reviewer's execution
environment, not by a code or contract finding.** No blocking or
closure-required defect was identified by Reviewer B; the substantive
code-level conclusion from that review is the same PASS as Reviewer A's.

Closure is therefore based on **one execution-capable independent Level 1
PASS** (Reviewer A, with real targeted/full-suite numbers and direct
verification of every R1-01-relevant semantic) **plus one additional
independent substantive confirmation with no code blocker** (Reviewer B),
consistent with this project's phase-gate governance for a round whose
change is narrowly scoped (one function's containment-normalization logic
plus its regression tests) and whose only prior-round carried procedural
issue (a reviewer-instruction defect, see P4-C1's own R1.1 precedent for
this exact class of non-implementation blocker) was again environmental,
not substantive.

## Carried findings

```text
P4-C2-R1-02 -- LOW / CARRIED / non-blocking
  Bare "\\server" (no explicit share) may be accepted by
  is_fully_qualified_absolute_root. Not touched by R1 or R2 (GOV-03's
  implementation was not modified after R1). Carried forward unchanged.

metadata.number != canonical_number identity gap -- CARRIED
operation-graph model-level hardening -- CARRIED
overwrite executor semantics -- CARRIED / frozen NEVER
extended Windows reserved-name edge cases -- CARRIED
```

Plus all pre-existing project carried debts, unchanged:
`P4-C1-R-02`, `P4-C1-R-03`, `P4-C1-R-04`, `P4-C1-R-05`, `C2-L2`, `P2-R-05`,
`P2-R-06`, `P2-R-07`, `P2-R-10`, `C3-N1`, `C3-N2`, `C3-N3`, `C3-N4`,
`C4-N1`, `C4-R1-N1`, `C4-R1-N2`, `C4-R1-N3`, `F3`, `F5`, `C5-R1-L1`.

## Future entry gates (must be resolved before, not by, a later package)

```text
metadata.number != canonical_number identity gap
  Must be closed before the first package that actually binds OrganizePlan
  with NormalizedMetadata for NFO/artifact publication. Not a P4-C2
  defect: contract section 9 freezes metadata as validation-only for this
  package, and no cross-check was ever promised here.

OrganizePlan operation-graph model-level hardening
  Must be resolved before an executor accepts arbitrary or reconstructed
  OrganizePlan instances (as opposed to ones produced by
  build_organize_plan itself). Deferred as executor-entry hardening,
  out of scope for a pure planning package with no executor.

overwrite = NEVER
  Remains a frozen global execution semantic (contract section 12). It is
  not a caller-configurable field on OrganizePlan or OutputPolicy today,
  and P4-C2 performs no filesystem access to enforce it against. The
  future executor must enforce it fail-closed against the real
  filesystem; that enforcement does not exist yet anywhere in this
  codebase and is not claimed to.
```

## Scope of this closure

This closes **P4-C2** (immutable organize plan) only. It does not close
Phase 4 as a whole, and does not authorize starting P4-C3 or any other
later Phase 4 package -- each requires its own frozen contract and its own
review cycle, per the project's phase-gate governance (the same boundary
P4-C1's own final closure recorded).

```text
Phase 4: NOT CLOSED
```

## Final status

```text
P4-C2: CLOSED
```
