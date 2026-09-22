# Phase 4 / P4-C1 Handoff — Recursive Media Discovery

```text
Phase        = 4
Package      = P4-C1
Role         = Developer
Branch       = claude/phase4-c1-recursive-discovery
Frozen Base  = 3edab6eb4ab363c1fedabd847c61b7061be8343d
```

**Type:** NEW PACKAGE (`fc2_organizer.discovery`). No existing file is
modified; `fc2_metadata_core`, `docs/specifications/PHASE3_*.md`, and every
prior `docs/review/*` file are untouched.

## 1. Exact review range

```text
Code Review Candidate: ffe49927760f57d3ea0179cde22f2c19c8dd10a9
Docs Head:              <this commit, see git log after commit>
Review Range:           3edab6eb4ab363c1fedabd847c61b7061be8343d..ffe49927760f57d3ea0179cde22f2c19c8dd10a9  (code)
                        ffe49927760f57d3ea0179cde22f2c19c8dd10a9..<Docs Head>  (docs)
```

The **Code Review Candidate** (`ffe4992`) is the commit an independent
reviewer should audit for correctness/safety. The **Docs Head** commit
(this file + the contract spec) adds no source or test changes.

## 2. Changed files

Code Review Candidate (`ffe4992`), 19 files, all new:

```text
fc2-organizer/src/fc2_organizer/__init__.py
fc2-organizer/src/fc2_organizer/discovery/__init__.py
fc2-organizer/src/fc2_organizer/discovery/_platform.py
fc2-organizer/src/fc2_organizer/discovery/errors.py
fc2-organizer/src/fc2_organizer/discovery/models.py
fc2-organizer/src/fc2_organizer/discovery/policy.py
fc2-organizer/src/fc2_organizer/discovery/scanner.py
fc2-organizer/tests/contract/test_discovery_architecture.py
fc2-organizer/tests/unit/discovery/__init__.py
fc2-organizer/tests/unit/discovery/test_discovery_basic.py
fc2-organizer/tests/unit/discovery/test_discovery_duplicates_and_ordering.py
fc2-organizer/tests/unit/discovery/test_discovery_failure_isolation.py
fc2-organizer/tests/unit/discovery/test_discovery_models.py
fc2-organizer/tests/unit/discovery/test_discovery_no_mutation.py
fc2-organizer/tests/unit/discovery/test_discovery_platform_helper.py
fc2-organizer/tests/unit/discovery/test_discovery_policy.py
fc2-organizer/tests/unit/discovery/test_discovery_root_failures.py
fc2-organizer/tests/unit/discovery/test_discovery_stage_gate.py
fc2-organizer/tests/unit/discovery/test_discovery_symlinks_and_junctions.py
```

Docs Head (this commit), 2 files, both new:

```text
fc2-organizer/docs/specifications/PHASE4_DISCOVERY_CONTRACT.md
fc2-organizer/docs/review/P4_C1_HANDOFF.md
```

No `pyproject.toml` change was needed: `[tool.setuptools.packages.find]`
already has `where = ["src"]` with no `include`/`exclude` filter, so
`fc2_organizer` is auto-discovered as a distribution package exactly like
`fc2_metadata_core`; and `[tool.pytest.ini_options] pythonpath = ["src", "tests"]`
already makes `fc2_organizer` importable for tests without installation.

## 3. Architecture summary

```text
dirty media root (a directory path)
        |
discover_media(root, policy=DiscoveryPolicy())
        |   recursive, read-only, deterministic, duplicate-safe,
        |   unsupported-file-safe, symlink/junction-safe
        v
DiscoveryResult(root, items: tuple[DiscoveredMediaItem, ...], issues: tuple[DiscoveryIssue, ...])
```

`fc2_organizer -> fc2_metadata_core` is the only allowed dependency
direction (frozen). `fc2_organizer.discovery` currently depends on **zero**
`fc2_metadata_core` modules: media identity here is the filesystem path, not
a parsed FC2 number (see contract §4, "FC2 Number Boundary"), so there was
nothing to import. Full detail: `docs/specifications/PHASE4_DISCOVERY_CONTRACT.md`.

## 4. Public API

```python
from fc2_organizer.discovery import (
    DiscoveryPolicy, DiscoveredMediaItem, DiscoveryIssue,
    DiscoveryIssueKind, DiscoveryStage, DiscoveryResult, discover_media,
)

result = discover_media(root, policy=DiscoveryPolicy())
```

`DiscoveredMediaItem`: `index`, `source_path`, `relative_path`, `extension`,
`size` — exactly the five fields required by the task brief, nothing more
(no scraped metadata, no target path, no Amane/DB state).

## 5. Error semantics

* Root-level (never disguised as empty success):
  `DiscoveryRootNotFoundError` / `DiscoveryRootNotADirectoryError` /
  `DiscoveryRootAccessError` (all subclass `DiscoveryRootError`), raised
  directly by `discover_media`.
* Argument-contract: `DiscoveryInputError` (bad `root`/`policy` type),
  `DiscoveryConfigError` (bad `DiscoveryPolicy.supported_extensions`).
* Model-contract: `DiscoveryContractError` (any of the four frozen models
  constructed with an invalid value).
* Non-root, local failures during the walk are never raised — isolated as
  `DiscoveryIssue(path, kind, stage, detail)` with a fixed, canned, bounded
  `detail` string (never `str(exc)`/`repr(exc)`/traceback/exception object).

## 6. Symlink / junction policy

Fixed, mandatory, non-configurable in v1.0 (no `DiscoveryPolicy.follow_symlinks`
field): a symlinked directory is never recursed into, a symlinked file is
never treated as a normal media source, and a Windows reparse point
(junction or otherwise) is detected independently of `is_symlink()` via
`fc2_organizer.discovery._platform.is_reparse_point`
(`st_file_attributes & FILE_ATTRIBUTE_REPARSE_POINT`, Python 3.11-compatible,
not `os.path.isjunction` which needs 3.12+). Full rationale: contract §10.

## 7. Deterministic ordering rule

Per directory, entries (files + subdirectories together) are sorted by
`entry.name` using plain Python ordinal string comparison, then walked
depth-first pre-order (a subdirectory is fully recursed into the instant it
is reached, before its later siblings). `index` is assigned in exact
traversal-append order. Full detail: contract §7.

## 8. Supported extension policy

`DiscoveryPolicy.supported_extensions`, default `.mp4 .mkv .avi .mov .wmv
.m4v .ts`, case-insensitive (normalized to lowercase at construction),
overridable, centralized (no extension list duplicated elsewhere).
Rationale for the default set: contract §5.

## 9. Test commands

```bash
# Targeted (from fc2-organizer/):
python -m pytest tests/unit/discovery tests/contract/test_discovery_architecture.py -q

# Full suite:
python -m pytest -q
```

(`--basetemp=<dir>` was used in this environment only to avoid an unrelated
pytest-internal teardown race against a shared `%TEMP%\pytest-of-<user>`
directory when another process touches it concurrently on this multi-job
host — see §12. It has no effect on and is not required for the tests
themselves.)

## 10. Targeted tests

```text
99 passed, 3 skipped
```

The 3 skips are the real-directory-symlink tests in
`test_discovery_symlinks_and_junctions.py` (see §12 — privilege unavailable
on this host, `pytest.skip` with the concrete `WinError 1314` reason, never
faked as passing). All junction tests (which need no elevation) ran for
real and passed.

## 11. Full suite

```text
2460 passed, 3 skipped
```

Matches the prior closed-phase baseline exactly: C5-R1 recorded
`2361/2361` passed for the pre-existing suite (see
`docs/review/PHASE3_C5_R1_HANDOFF.md` §5); `2361 + 99 (new P4-C1 tests) = 2460`.
No pre-existing test was modified, skipped, or newly failing. `0` warnings
/ `0` xfail beyond the 3 documented platform skips.

## 12. Platform-specific tests not run

This host (win32, Python 3.12.10) can create a real NTFS junction without
elevation (`_winapi.CreateJunction`, verified directly during development),
so **junction safety was tested for real**, not simulated:
`test_junction_directory_is_not_recursed_into`,
`test_junction_loop_does_not_hang`,
`test_junction_pointing_outside_root_is_not_followed` all pass against an
actual junction on disk.

Creating a real **directory symlink** on this host fails with
`OSError: [WinError 1314] 客户端没有所需的特权` (`os.symlink` requires
`SeCreateSymbolicLinkPrivilege` / Developer Mode, neither available here).
The following 3 tests detect this at runtime and `pytest.skip` with that
exact reason rather than being faked as passing:

```text
test_discovery_symlinks_and_junctions.py::test_symlink_directory_is_not_recursed_into
test_discovery_symlinks_and_junctions.py::test_symlink_file_is_not_treated_as_a_normal_media_source
test_discovery_symlinks_and_junctions.py::test_symlink_loop_does_not_hang
```

**Windows-specific runtime test NOT RUN: real directory-symlink recursion
safety** (only the junction/reparse-point path was exercised against a real
filesystem object; the symlink code path itself — `entry.is_symlink() ==
True` — is instead covered indirectly by `is_reparse_point`'s own unit
tests in `test_discovery_platform_helper.py`, which do not require a real
symlink, plus the fact that `scanner._process_entry`'s symlink branch is
identical code regardless of whether the underlying object is a symlink or
a junction). If this is later run with `SeCreateSymbolicLinkPrivilege`
available (elevated shell, or Developer Mode enabled), these 3 tests will
execute for real with no code change required.

## 13. Synthetic stage gate

```text
PASS
```

`test_discovery_stage_gate.py::test_large_synthetic_stage_gate` builds
~360 supported + ~360 unsupported files across 50 nested directories (10
studios × 5 sub-batches × 6 files, mixed extensions cycled per file), plus
3 duplicate-FC2-number files in 3 separate directories, Unicode
directory/file names, and empty directories scattered through the tree.
Verifies, fully offline, on a fixed code-driven (non-random) layout so the
run is exactly reproducible: every supported file discovered exactly once,
zero unsupported files ever became items, zero issues on the clean tree,
zero duplicate `source_path`, identical ordering/indices across two
back-to-back runs, and zero filesystem mutation (before/after `os.walk`
snapshot equality).

## 14. Known limitations

* Traversal recursion depth is bounded by the Python call stack
  (`sys.getrecursionlimit()`, default ~1000); an extremely deep directory
  nesting could raise `RecursionError`. No real media library is expected
  to approach this; contract §7 documents it as an accepted v1.0 limit.
* A symlinked **file** (not directory) is excluded entirely rather than
  resolved-and-stat'd through — a deliberate conservative choice (task
  brief §11), not yet exercised against a real symlink on this host (§12).
* Extreme Windows long-path edge cases (`MAX_PATH` = 260 without the
  `\\?\` long-path opt-in) were not specifically stress-tested; the deep
  recursive tree test in `test_discovery_basic.py` uses 25 nesting levels
  with short names, comfortably under any such limit, and is not a claim
  about arbitrarily long absolute paths.
* No dedicated concurrency/thread-safety claim: `discover_media` is a
  single-threaded, synchronous, one-shot call, matching the task brief's
  scope (no batch/async integration in P4-C1).

## 15. Carried debts (not triggered / not addressed by P4-C1)

```text
C2-L2, P2-R-05, P2-R-06, P2-R-07, P2-R-10,
C3-N1, C3-N2, C3-N3, C3-N4,
C4-N1, C4-R1-N1, C4-R1-N2, C4-R1-N3,
F3, F5, C5-R1-L1
```

None of these are read, touched, or relevant: `fc2_organizer.discovery` has
zero dependency on the modules any of them concern (see contract §14).

## 16. `git diff --check`

```text
clean (no output)
```

## 17. `git status --porcelain`

Clean after the Docs Head commit (verify with `git status --porcelain` —
expected empty once this file is committed).

## 18. Independent Review (original round)

```text
REQUIRED
```

## 19. P4-C1 (original round)

```text
NOT CLOSED
```

---

# R1 Closure — P4-C1-R-01 (HIGH / BLOCKING)

The section above is the original, as-reviewed P4-C1 submission and is left
unmodified for history. This section records the R1 incremental-closure
round.

## R1.1 Coordinates

```text
Reviewed-Failed Code Head = ffe49927760f57d3ea0179cde22f2c19c8dd10a9
Previous Docs Head        = 00dc40d0338b75427766c6b768ed572ee16b9ca0
R1 Code Review Candidate  = 77f928df9e8233ec42f3aa3d5b14291a24c1036a
R1 Docs Head              = <this commit; see git log after commit>
R1 Code Review Range      = 00dc40d0338b75427766c6b768ed572ee16b9ca0..77f928df9e8233ec42f3aa3d5b14291a24c1036a
R1 Docs Review Range      = 77f928df9e8233ec42f3aa3d5b14291a24c1036a..<R1 Docs Head>
```

Two reviewer outputs existed for the original round. The first was
`BLOCKED` because its own instructions required reading a
`fc2-organizer/docs/HANDOFF.md` path that does not exist in this repository
-- a review-instruction defect, not a P4-C1 implementation defect. Per this
round's brief, that file was **not** created and the repository structure
was **not** changed to satisfy it; its same-named `P4-C1-R-01` label is
**not** what this section closes. The finding closed here is the one from
the second reviewer output, which performed an actual code read, test
re-run, and reproduction.

## R1.2 Finding addressed

```text
P4-C1-R-01
Severity: HIGH / BLOCKING
```

**Defect:** `discover_media("mydir")` with a relative root produced a
`DiscoveredMediaItem.source_path` that was itself still relative
(`os.path.isabs(...) == False`), violating the frozen contract
(`source_path` must be absolute -- contract §3). Reproduced directly by the
reviewer via `chdir` + relative root. The original test suite passed only
`tmp_path` (already absolute) everywhere, so this path was structurally
untested.

## R1.3 Exact changed files

```text
fc2-organizer/src/fc2_organizer/discovery/scanner.py      (M)
fc2-organizer/src/fc2_organizer/discovery/models.py       (M)
fc2-organizer/tests/unit/discovery/test_discovery_root_absolutization.py  (new)
fc2-organizer/docs/review/P4_C1_HANDOFF.md                 (this section)
```

No other file touched. `docs/specifications/PHASE4_DISCOVERY_CONTRACT.md`
was **not** modified: it already stated `source_path: str` is "(absolute,
OS-native separators...)" in §3 -- the contract was already correct; only
the implementation had not satisfied it.

## R1.4 Repair description

**A. Root absolutization** (`scanner._coerce_root`): after coercing `root`
to a `Path` (unchanged type-dispatch logic for `str`/`Path`/`os.PathLike`),
the result is now passed through `Path(os.path.abspath(candidate))` before
being used anywhere else. `os.path.abspath` was chosen deliberately over
`Path.resolve()`: `abspath` only joins onto the current working directory
and normalizes `.`/`..` segments -- it never resolves a symlink. `resolve()`
would additionally follow a symlinked root or a symlinked intermediate
path component, silently changing *what* gets scanned; that would be a
real semantic change to the caller-supplied root and to the (untouched,
frozen) root-symlink handling, not a pure absolutization, and was
explicitly out of scope for this fix.

Because every path produced during the walk
(`DiscoveryResult.root`, every `DiscoveredMediaItem.source_path`) is built
by `os.scandir`/`os.DirEntry.path` off the directory passed into `_walk`,
and `_walk`'s very first call in `discover_media` now receives this
absolutized `root_path`, absolutizing once at the top is sufficient for
the entire recursive traversal -- no other call site needed a change.

**B. Model invariant** (`DiscoveredMediaItem.__post_init__`): added
`if not os.path.isabs(self.source_path): raise DiscoveryContractError(...)`
immediately after the existing non-empty-`str` check. A hand-built
`DiscoveredMediaItem` with a relative `source_path` is now rejected at
construction, independent of whether the scanner itself is correct --
closing the "model trusts the scanner" gap the reviewer's reproduction
exposed conceptually.

Nothing else in either file changed. Symlink/junction detection
(`_is_symlink`, `is_reparse_point`), the deterministic sort/traversal
order, extension-policy matching, failure-isolation seams
(`_list_directory_sorted`, `_stat_entry`), and root-typed-error semantics
(`_check_root`) are byte-for-byte unchanged.

## R1.5 New regression tests

`tests/unit/discovery/test_discovery_root_absolutization.py` (10 tests),
all using a genuinely relative root (via `monkeypatch.chdir` + a bare
relative directory name, not `tmp_path` directly):

* relative root -> absolute `source_path`
* relative root -> correct `relative_path`
* relative root -> `source_path` identifies the real underlying file (stat
  + read back its content)
* relative root -> `DiscoveryResult.root` is also absolute
* `.`-prefixed relative root (`./mydir`) -> absolute `source_path`
* relative root containing a `..` segment (`sibling/../mydir`) -> absolute
  `source_path`
* a plain relative-root scan with no symlinks present still yields zero
  `DiscoveryIssue`s (proves R1 did not perturb symlink/junction behavior)
* direct `DiscoveredMediaItem(source_path="relative/a.mp4", ...)` ->
  `DiscoveryContractError`
* direct `DiscoveredMediaItem` with an absolute `source_path` -> accepted
* direct `DiscoveredMediaItem(source_path="mydir\\a.mp4", ...)` (Windows-style
  relative) -> `DiscoveryContractError`

## R1.6 Targeted test result

```text
109 passed, 3 skipped
```

(99 pre-existing P4-C1 tests + 10 new, all green; the 3 skips are the
same pre-existing real-directory-symlink-privilege skips from the original
round, unaffected by this fix.)

## R1.7 Full-suite result

```text
2470 passed, 3 skipped
```

`2460 (original P4-C1 full-suite baseline) + 10 (new) = 2470`. No
pre-existing test was modified, newly failing, or newly skipped.

## R1.8 Reviewer reproduction — re-verified directly

Ran the equivalent of the reviewer's reproduction by hand, outside pytest,
against the fixed code:

```text
mkdir mydir; create mydir/a.mp4; chdir to the parent; discover_media("mydir")

source_path: C:\Users\Ctg\AppData\Local\Temp\tmp90nqlzuu\mydir\a.mp4
os.path.isabs(source_path) == True
relative_path == "a.mp4"
result.root == C:\Users\Ctg\AppData\Local\Temp\tmp90nqlzuu\mydir  (absolute)
os.path.isfile(source_path) == True
```

Also directly verified `.\mydir` and `foo\..\mydir` relative forms both
resolve to the same absolute, correct target, and that hand-constructing
`DiscoveredMediaItem(source_path="relative\a.mp4", ...)` now raises
`DiscoveryContractError`.

## R1.9 `git diff --check`

```text
clean (no output)
```

## R1.10 `git status --porcelain`

Clean after the R1 code commit; clean again after this R1 docs commit
(verify with `git status --porcelain`).

## R1.11 Carried non-blocking findings (unchanged, not addressed by R1)

```text
P4-C1-R-02  MEDIUM
P4-C1-R-03  LOW
P4-C1-R-04  LOW
P4-C1-R-05  LOW
```

All four were explicitly judged `non-blocking / carried` by the second
reviewer output. Per this round's brief, none is addressed here: no
anti-TOCTOU rewrite of the scanner, no symlink/junction architecture
expansion, no extension-policy redesign, and no scope expansion to close a
LOW finding. They remain open for a future round.

## R1.12 Independent R1 Closure Review

```text
REQUIRED
```

## R1.13 P4-C1

```text
NOT CLOSED
```
