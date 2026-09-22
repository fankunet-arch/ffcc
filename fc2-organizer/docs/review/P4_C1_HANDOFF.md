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

## R1.12 Independent R1 Closure Review (original round)

```text
REQUIRED
```

## R1.13 P4-C1 (original round)

```text
NOT CLOSED
```

---

# R2 Closure — P4-C1-R1-01 (HIGH / BLOCKING)

The two sections above (original P4-C1 and R1) are left unmodified for
history. This section records the R2 incremental-closure round.

## R2.1 Coordinates

```text
R1 Reviewed-Failed Code Head = 77f928df9e8233ec42f3aa3d5b14291a24c1036a
Previous Docs Head           = 25013d1fffee717603389511c3ca7b272e62518d
R2 Code Review Candidate     = 2db3a44d48eb6e9ae36d627c3fd1bb5ed661e34c
R2 Docs Head                 = <this commit; see git log after commit>
R2 Code Review Range         = 25013d1fffee717603389511c3ca7b272e62518d..2db3a44d48eb6e9ae36d627c3fd1bb5ed661e34c
R2 Docs Review Range         = 2db3a44d48eb6e9ae36d627c3fd1bb5ed661e34c..<R2 Docs Head>
```

```text
P4-C1-R-01: REMAINS CLOSED (reverified by direct reproduction, R2.7 Repro A)
```

## R2.2 Finding addressed

```text
P4-C1-R1-01
Severity: HIGH / BLOCKING
```

**Defect:** R1's fix for P4-C1-R-01 absolutized a relative root via
`os.path.abspath`, which performs a purely lexical normalization
(collapsing `a/../b` to `b`) *before any filesystem access happens*. For an
ordinary directory this lexical shortcut is harmless. For
`link/../mydir` where `link` is a symlink (or, on Windows, a junction),
it is wrong in general: a filesystem that resolves paths component-by-component
resolves `..` in the context of wherever `link` actually points, not
lexically relative to `link`'s own location. The independent reviewer
reproduced this with a real POSIX symlink:

```text
base/
  mydir/
    BASE.mp4
  link -> other/subdir

other/
  subdir/
  mydir/
    OTHER.mp4

chdir(base); discover_media("link/../mydir")
```

R1's `abspath`-based fix scanned `base/mydir` (`BASE.mp4`) even though the
caller's path, resolved the way a real filesystem resolves it, names
`other/mydir` (`OTHER.mp4`) -- a silent substitution of *which physical
directory* gets scanned, i.e. a correctness regression, not merely a
cosmetic one.

## R2.3 Exact changed files

```text
fc2-organizer/src/fc2_organizer/discovery/scanner.py                            (M)
fc2-organizer/tests/unit/discovery/test_discovery_root_absolutization.py        (M)
fc2-organizer/tests/unit/discovery/test_discovery_symlink_dotdot_identity.py    (new)
fc2-organizer/docs/review/P4_C1_HANDOFF.md                                       (this section)
```

`models.py` was **not** touched: the "`source_path` must be absolute"
invariant added in R1 is correct and unchanged. `PHASE4_DISCOVERY_CONTRACT.md`
was **not** touched: it already specified "absolute" and never claimed
"canonicalized/normalized/resolved"; only the implementation had drifted
from that by using `abspath` internally, an implementation detail the
contract never mandated.

## R2.4 Absolute-without-identity-change strategy

`scanner._coerce_root` no longer calls `os.path.abspath`, `os.path.normpath`,
`Path.resolve()`, or `os.path.realpath` on the whole path -- none of those
are used anywhere in this fix. Instead:

```python
if not candidate.is_absolute():
    candidate = Path(os.getcwd()) / candidate
return candidate
```

* A **relative** root is absolutized by prefixing the current working
  directory via a plain `pathlib` join. This join never folds a `..`
  segment away (verified: `Path("/base") / "link/../mydir"` stays
  `PurePath("/base/link/../mydir")`, `.." literally present in `.parts`).
  It does drop a redundant `.` segment (`Path("/base") / "./mydir"` ->
  `/base/mydir`) -- always lexically safe, since a bare `.` never changes
  which directory a path names, symlinks or not.
* An **already-absolute** root -- even one containing `..`, even one
  R1's `abspath` call would have collapsed -- is returned completely
  untouched, byte-for-byte.
* Every path built during the walk (`DiscoveryResult.root`, every
  `DiscoveredMediaItem.source_path`) is still derived from this `Path` via
  plain `os.scandir`/`os.DirEntry.path` string concatenation, exactly as
  in R1 -- so the unresolved `..`/symlink-sensitive segment is carried
  through into every result path unchanged.
* Every *real* filesystem call made along the way (`os.stat` in
  `_check_root`, `os.scandir` in `_list_directory_sorted`) still receives
  that same literal, unresolved string, so **the OS's own path resolution**
  -- not any in-process string rewrite -- decides which physical directory
  gets scanned. On a filesystem where the kernel resolves `..` component-by-
  component honoring symlinks (POSIX), this correctly reproduces the
  caller's actual intended target. This is the concrete meaning of the R2
  brief's Requirement B ("filesystem 自己按正常路径解析语义处理").

## R2.5 Windows: verified platform limit, not a residual defect

Independently of this package's code, `ctypes`-calling `GetFullPathNameW`
(the Win32 API kernel32 uses internally to convert a DOS path to an NT path
before `CreateFileW`/`FindFirstFileW` -- which every `os.stat`/`os.scandir`
call on Windows ultimately goes through) on a **nonexistent** path
(`C:\some\base\link\..\mydir`) returns `C:\some\base\mydir` -- proving the
`..` collapse happens as a pure string operation, with zero filesystem I/O
and zero reparse-point awareness, *before* the filesystem/junction layer is
ever consulted. This is identical to how `cmd.exe`, PowerShell, and Windows
Explorer resolve such a path (`cd link\..\mydir` behaves the same way) --
a native Windows path-resolution characteristic that predates and is
external to `fc2_organizer.discovery`, not something introduced by, or
fixable from within, this package (short of hand-rolling raw NT-native
path calls, explicitly out of scope per the R2 brief).

Consequently, for a Windows junction specifically, the *correct*,
native-Windows interpretation of `link\..\mydir` **is** the
lexically-collapsed `base\mydir` -- R1's `abspath` and R2's cwd-prefix-only
`_coerce_root` produce the **identical, correct** result for this specific
case. There is no Windows-side regression to fix: P4-C1-R1-01 is
specifically about the POSIX symlink case, where the kernel's real
per-component resolution genuinely differs from a naive lexical collapse,
and R2's fix addresses exactly that.

## R2.6 Relative root / ordinary `..` (must not regress)

Reverified unchanged from R1: `discover_media("mydir")`,
`discover_media("./mydir")`, and an ordinary (no-symlink) `discover_media("foo/../mydir")`
all still yield an absolute `DiscoveryResult.root`, an absolute
`DiscoveredMediaItem.source_path`, the correct `relative_path`, and
correct file identity (content read back matches). Covered by the
pre-existing `test_discovery_root_absolutization.py` tests plus the new
`test_ordinary_dotdot_root_identity_is_unaffected` (adds an explicit
content check, per the R2 brief's note that the plain-directory `..` case
and the symlink/junction `..` case are not the same semantic test and both
must be covered).

## R2.7 Symlink + `..` identity (POSIX)

`test_discovery_symlink_dotdot_identity.py::test_posix_symlink_dotdot_root_preserves_caller_path_identity`
builds the reviewer's exact structure (`base/link -> other/subdir`,
`base/mydir/BASE.mp4`, `other/mydir/OTHER.mp4`) and asserts
`discover_media("link/../mydir")` discovers `OTHER.mp4` with content
`"other-content"`, not `BASE.mp4`. On this host it `pytest.skip`s with the
concrete reason (`os.symlink` fails: `WinError 1314`, no
`SeCreateSymbolicLinkPrivilege` / Developer Mode) -- the same limitation
already documented for the original P4-C1 symlink tests, not faked as
passing. On a host that can create a real directory symlink (a POSIX CI
runner, or an elevated/Developer-Mode Windows host), it runs for real with
no code change required.

## R2.8 Windows junction + `..` identity

```text
PASS -- ran for real on this host (junction creation needs no elevation)
```

`test_discovery_symlink_dotdot_identity.py::test_windows_junction_dotdot_root_matches_native_win32_path_resolution`
builds the equivalent structure with a real NTFS junction
(`_winapi.CreateJunction`), first independently reconfirms the
`GetFullPathNameW` lexical-collapse behavior via `ctypes` (§R2.5), then
asserts `discover_media("link/../mydir")` discovers `BASE.mp4` with content
`"base-content"` -- the correct-for-Windows, native outcome, not the
POSIX-symlink outcome (which is not achievable on Windows through any
ordinary Win32 file API, per §R2.5). Not a "Windows junction + .. identity
test NOT RUN" case: the environment can and does create the junction, so
this ran for real and its actual (platform-correct) result is reported
honestly rather than assumed to mirror the POSIX case.

## R2.9 Model absolute invariant

Unchanged. `DiscoveredMediaItem.__post_init__`'s `os.path.isabs(source_path)`
check (added in R1) was not touched, not weakened, and not removed.
Reverified directly (R2.10 Repro A) that a relative `source_path` is still
rejected with `DiscoveryContractError`.

## R2.10 Direct reproduction — Repro A (original P4-C1-R-01 bug, must not regress)

```text
mkdir mydir; create mydir/a.mp4; chdir to parent; discover_media("mydir")

source_path: C:\Users\Ctg\AppData\Local\Temp\tmpwkjgwcnq\mydir\a.mp4
os.path.isabs(source_path) == True
result.root: C:\Users\Ctg\AppData\Local\Temp\tmpwkjgwcnq\mydir  (absolute)
relative_path == "a.mp4"
-> Repro A: PASS (P4-C1-R-01 remains CLOSED)

Direct DiscoveredMediaItem(source_path="relative/a.mp4", ...)
-> DiscoveryContractError: "DiscoveredMediaItem.source_path must be an
   absolute path, got 'relative/a.mp4'"  (model invariant still enforced)
```

## R2.11 Direct reproduction — Repro B (P4-C1-R1-01, this round's fix)

```text
base/mydir/BASE.mp4, other/mydir/OTHER.mp4, base/link -> junction -> other/subdir
chdir(base); discover_media("link/../mydir")

caller root string:      link\..\mydir
result.root (observed):  <tmp>\base\link\..\mydir   (absolute; literal ".." preserved, not pre-collapsed by our code)
observed relative_path:  BASE.mp4
observed content:        base-content

Expected physical file per POSIX-symlink-style resolution
  (NOT achievable on Windows via any ordinary Win32 API): other/mydir/OTHER.mp4
Expected physical file per native Windows GetFullPathNameW resolution
  (independently verified via ctypes, see R2.5):          base/mydir/BASE.mp4
Observed physical file this run:                           base/mydir/BASE.mp4

-> matches native Windows resolution exactly; no in-process lexical
   pre-collapse was performed by fc2_organizer.discovery's own code
   (independently confirmed by the platform-independent
   test_coerce_root_does_not_lexically_collapse_dotdot_in_* unit tests,
   which do not depend on any real symlink/junction being present).
```

## R2.12 Targeted tests

```text
114 passed, 4 skipped
```

(109 prior P4-C1(+R1) tests + 5 new, all green; 4 skips = the 3 pre-existing
real-directory-symlink-privilege skips + 1 new one for
`test_posix_symlink_dotdot_root_preserves_caller_path_identity`, same root
cause.)

## R2.13 Full suite

```text
2475 passed, 4 skipped
```

`2470 (R1 full-suite baseline) + 5 (new) = 2475`. No pre-existing test was
modified, newly failing, or newly skipped for a different reason than
before.

## R2.14 `git diff --check`

```text
clean (no output)
```

## R2.15 `git status --porcelain`

Clean after the R2 code commit; clean again after this R2 docs commit
(verify with `git status --porcelain`).

## R2.16 Carried non-blocking findings (unchanged, not addressed by R2)

```text
P4-C1-R-02  MEDIUM  -- CARRIED / non-blocking
P4-C1-R-03  LOW     -- CARRIED / non-blocking
P4-C1-R-04  LOW     -- CARRIED / non-blocking
P4-C1-R-05  LOW     -- CARRIED / non-blocking
```

None closed, upgraded, or removed by R2. Per the R2 brief: no anti-TOCTOU
scanner rewrite, no symlink/junction architecture expansion, no
extension-policy redesign, and no fd-relative scanner rewrite were
undertaken to close P4-C1-R1-01. They remain open for a future round.

## R2.17 Independent R2 Closure Review (original round)

```text
REQUIRED
```

## R2.18 P4-C1 (original round)

```text
NOT CLOSED
```

---

# R3 Closure — P4-C1-R2-01 (HIGH / BLOCKING)

The three sections above (original P4-C1, R1, R2) are left unmodified for
history. This section records the R3 incremental-closure round.

## R3.1 Coordinates

```text
R2 Reviewed-Failed Code Head = 2db3a44d48eb6e9ae36d627c3fd1bb5ed661e34c
Previous Docs Head           = a65a29f30b0c6e1352c19e6f2a85c061434f86a5
R3 Code Review Candidate     = c4f5a415d8fd8d0d56ff4ee227e7b87a01fbe79f
R3 Docs Head                 = <this commit; see git log after commit>
R3 Code Review Range         = a65a29f30b0c6e1352c19e6f2a85c061434f86a5..c4f5a415d8fd8d0d56ff4ee227e7b87a01fbe79f
R3 Docs Review Range         = c4f5a415d8fd8d0d56ff4ee227e7b87a01fbe79f..<R3 Docs Head>
```

```text
P4-C1-R-01:   REMAINS CLOSED (reverified, R3.10 Repro A)
P4-C1-R1-01:  REMAINS CLOSED (reverified, R3.10 Repro B + Repro C)
P4-C1-R2-01:  CLOSED by this round (R3.10 Repro D)
```

## R3.2 Finding addressed

```text
P4-C1-R2-01
Severity: HIGH / BLOCKING
```

**Defect:** R2's `_coerce_root` absolutized a relative root by
unconditionally prefixing the current working directory
(`Path(os.getcwd()) / candidate`). Correct on POSIX (no drive-relative
concept exists there), but wrong on Windows for relative forms a plain
string join cannot express: same-drive drive-relative (`C:foo`),
cross-drive drive-relative (`D:foo` while the process's current drive is
`C:`), and rooted-relative (`\foo`). `D:foo` in particular resolves
against drive `D:`'s **own** current directory -- OS-maintained state (the
hidden per-drive `=D:` environment variable Windows itself tracks) that
`os.getcwd()` cannot report for any drive other than the current one.
`Path(os.getcwd()) / Path("D:foo")` does not correctly resolve this and
could still fail to produce a path that is actually absolute for the
caller's intended target -- reopening the P4-C1-R-01 contract violation
for this specific input shape.

## R3.3 Exact changed files

```text
fc2-organizer/src/fc2_organizer/discovery/scanner.py                              (M)
fc2-organizer/tests/unit/discovery/test_discovery_root_absolutization.py          (M)
fc2-organizer/tests/unit/discovery/test_discovery_drive_relative_identity.py      (new)
fc2-organizer/docs/review/P4_C1_HANDOFF.md                                        (this section)
```

`models.py` was **not** touched: the "`source_path` must be absolute"
invariant is correct and unchanged. `PHASE4_DISCOVERY_CONTRACT.md` was
**not** touched: it specifies "absolute OS-native path", which is what
this fix now actually delivers on every platform.

## R3.4 Platform-specific absolutization strategy

```python
def _is_windows() -> bool:
    return os.name == "nt"

...
if _is_windows():
    return Path(os.path.abspath(candidate))

if not candidate.is_absolute():
    candidate = Path(os.getcwd()) / candidate
return candidate
```

`_is_windows()` is a new, small, isolated seam (mirroring the existing
`_list_directory_sorted`/`_stat_entry`/`_is_symlink` pattern) so a test can
force either branch without mutating the real `os.name` global --
important because `os.name` is read by other modules in the same process,
including `pathlib`'s own concrete-`Path`-subclass selection, so mutating
it directly breaks on a real Windows host (`NotImplementedError: cannot
instantiate 'PosixPath' on your system`, hit and fixed during this round).

* **Windows branch:** delegates entirely to `os.path.abspath`
  (`ntpath.abspath`, backed by the real `GetFullPathNameW` Win32 API).
  This is not a convenience choice -- it is the *only* way to correctly
  resolve same-drive/cross-drive-relative and rooted-relative paths at
  all, since Python exposes no other API for a non-current drive's own
  current directory. It also means `..` is lexically collapsed on
  Windows -- but that is *not* a P4-C1-R1-01 regression: R2 already
  independently verified (via `ctypes` `GetFullPathNameW` on a
  nonexistent path) that Windows collapses `..` this way natively, before
  any reparse point is ever consulted, identical to
  `cmd.exe`/PowerShell/Explorer -- so `abspath` on Windows produces the
  identical, correct-for-Windows result the OS would produce for any
  filesystem access to that path regardless of what this package does.
* **POSIX branch:** unchanged from R2 -- prefixes the current working
  directory onto a relative root via a plain `pathlib` join, never folding
  `..` away, so a POSIX kernel can still resolve `..` in
  `link/../mydir` relative to wherever `link` actually points
  (P4-C1-R1-01).

## R3.5 Ordinary relative root (must not regress)

`discover_media("mydir")`, `"./mydir"`, and (non-symlink) `"foo/../mydir"`
all still yield absolute `result.root`/`source_path`, correct
`relative_path`, and correct content identity on Windows -- now via the
`os.path.abspath` branch instead of the R2 cwd-join, with an identical
observable result for these ordinary forms. Covered by the pre-existing
`test_discovery_root_absolutization.py` tests, all still green.

## R3.6 Windows rooted-relative root (`\foo`)

Covered as an oracle path-resolution match (`ctypes GetFullPathNameW`),
not against a real file at a drive root: this round deliberately does not
write test fixtures directly at a drive root (`C:\` or `D:\`), matching
the task brief's own softer "at least add appropriate regression
coverage" wording for this specific case (vs. the explicit "must be a
real Windows filesystem test" wording for the cross-drive case, R3.8).
`test_discovery_drive_relative_identity.py::test_rooted_relative_root_matches_native_path_resolution`
asserts `_coerce_root("\\foo")` matches `GetFullPathNameW("\\foo")`
exactly, under a real (non-root) `monkeypatch.chdir`.

## R3.7 Windows same-drive drive-relative root (`C:foo`)

Real filesystem identity test, no special drive needed (same-drive
drive-relative resolves against the current drive's own current
directory, i.e. `tmp_path` here, an ordinary, already-sanctioned temp
location -- never a drive root).
`test_discovery_drive_relative_identity.py::test_same_drive_drive_relative_root_preserves_identity`:
creates a real file under `tmp_path`, independently resolves `"C:mydir"`
via `ctypes GetFullPathNameW`, directly reads the oracle-resolved file's
content with a plain `open()` before ever calling `discover_media`, then
asserts `discover_media("C:mydir")` matches that oracle exactly in both
path identity (`os.path.samefile`) and content.

## R3.8 Windows cross-drive drive-relative root (`D:foo`)

```text
PASS -- ran for real (a genuine second writable drive, D:, is present on this host)
```

This is the round's central regression, and the only piece requiring
write access outside the repo's own temp areas. **Explicit user
authorization was obtained before touching the real `D:\` drive** (which
contains the repo owner's actual personal files -- Documents, SQL dumps,
project folders -- not a scratch/test drive), under these constraints,
honored exactly:

* Exactly **one** uniquely, randomly-named directory created directly
  under `D:\` (`D:\ffcc_p4c1_r3_<uuid4 hex>`) -- nothing else on `D:`
  read, modified, moved, or deleted.
* Every created path tracked explicitly; deletion targets only that one
  owned root (and its own contents, created by this round), verified by
  path identity immediately before `shutil.rmtree`.
* No recursive delete of anything that existed before this round; no
  wildcard/fuzzy path used for deletion.
* Deletion success re-verified after (`owned_root.exists() == False`);
  the strategy was to report a residual path and stop, never bypass a
  protection, if deletion had failed (it did not).

**Standalone reproduction (outside pytest, Repro D)** ran first, with
every created/deleted path printed:

```text
Created: D:\ffcc_p4c1_r3_12d5923b632143d99e2c9a6fab0a0da4
         D:\ffcc_p4c1_r3_12d5923b632143d99e2c9a6fab0a0da4\droot
         D:\ffcc_p4c1_r3_12d5923b632143d99e2c9a6fab0a0da4\droot\mydir
         D:\ffcc_p4c1_r3_12d5923b632143d99e2c9a6fab0a0da4\droot\mydir\D_DRIVE_FILE.mp4
Oracle (ctypes GetFullPathNameW) resolved "D:mydir" ->
         D:\ffcc_p4c1_r3_12d5923b632143d99e2c9a6fab0a0da4\droot\mydir
discover_media("D:mydir") result.root / item.source_path: same directory, absolute
item.relative_path: D_DRIVE_FILE.mp4
Oracle direct-read content == discover_media-read content == "d-drive-content"
Deleted: D:\ffcc_p4c1_r3_12d5923b632143d99e2c9a6fab0a0da4 (the single owned root)
owned_root exists after cleanup: False
```

`Get-ChildItem D:\` was diffed before and after (22 top-level entries,
identical names, no `ffcc_*` residual) both after the standalone script
and again after the full pytest run that also exercises this path
(`test_discovery_drive_relative_identity.py::test_cross_drive_drive_relative_root_preserves_identity`,
which programmatically re-derives a second writable drive via a
`_second_writable_drive` fixture rather than hard-coding `D:` -- it
`pytest.skip`s if none is found, never fabricating a pass).

## R3.9 Windows junction + `..` (must not regress, P4-C1-R1-01 Windows side)

`test_discovery_symlink_dotdot_identity.py::test_windows_junction_dotdot_root_matches_native_win32_path_resolution`
(unmodified from R2) still passes: `discover_media("link/../mydir")`
across a real junction still resolves to `BASE.mp4` -- the same,
correct-for-Windows result as before, since `_coerce_root`'s Windows
branch (`abspath`) produces an identical result to R2's cwd-join for this
specific case (R3.4).

## R3.10 Direct reproductions (outside pytest)

```text
Repro A -- ordinary relative root ("mydir"):
  source_path/result.root absolute, relative_path == "a.mp4"
  direct DiscoveredMediaItem(source_path="relative/a.mp4", ...) -> DiscoveryContractError
  -> PASS, P4-C1-R-01 remains closed

Repro B -- POSIX symlink/../mydir:
  os.symlink(...) -> OSError(22, "客户端没有所需的特权。") (WinError 1314)
  -> NOT RUN -- platform/privilege limitation (unchanged from R1/R2), honestly reported

Repro C -- Windows junction/../mydir:
  discovered BASE.mp4 / "base-content" (native, correct-for-Windows result)
  result.root now shows the lexically-collapsed path (...\base\mydir), consistent
  with the Windows branch now using abspath unconditionally
  -> PASS, P4-C1-R1-01 Windows side remains closed

Repro D -- Windows cross-drive "D:mydir":
  independent oracle (ctypes GetFullPathNameW) and discover_media agree exactly
  on both path identity and file content; single owned directory created and
  fully deleted, D:\ diffed clean before/after
  -> PASS, P4-C1-R2-01 CLOSED
```

## R3.11 Targeted tests

```text
119 passed, 4 skipped
```

(114 prior P4-C1(+R1+R2) tests + 5 new, all green; 4 skips unchanged --
the 3 pre-existing real-directory-symlink-privilege skips plus the one
POSIX-symlink-identity skip from R2, same root cause each time: no
`SeCreateSymbolicLinkPrivilege` on this host.)

## R3.12 Full suite

```text
2480 passed, 4 skipped
```

`2475 (R2 full-suite baseline) + 5 (new) = 2480`. No pre-existing test was
modified, newly failing, or newly skipped for a different reason than
before.

## R3.13 `git diff --check`

```text
clean (no output)
```

## R3.14 `git status --porcelain`

Clean after the R3 code commit; clean again after this R3 docs commit
(verify with `git status --porcelain`). No residual state on `D:\` (see
R3.8).

## R3.15 Carried non-blocking findings (unchanged, not addressed by R3)

```text
P4-C1-R-02  MEDIUM  -- CARRIED / non-blocking
P4-C1-R-03  LOW     -- CARRIED / non-blocking
P4-C1-R-04  LOW     -- CARRIED / non-blocking
P4-C1-R-05  LOW     -- CARRIED / non-blocking
```

None closed, upgraded, or removed by R3.

## R3.16 Independent R3 Closure Review

```text
REQUIRED
```

## R3.17 P4-C1

```text
NOT CLOSED
```
