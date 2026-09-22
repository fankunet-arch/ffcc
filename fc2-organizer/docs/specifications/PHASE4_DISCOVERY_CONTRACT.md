# FC2 Organizer — Phase 4 / P4-C1 Recursive Media Discovery Contract

Status: **frozen at P4-C1** (candidate; independent closure review pending).
Package: `fc2_organizer.discovery` (`errors.py`, `policy.py`, `models.py`, `_platform.py`, `scanner.py`).

**Scope (frozen for this package):** media *discovery* only --
`dirty media root -> recursive read-only discovery -> deterministic
discovered media items`. No FC2 number parsing, no metadata scraping, no
NFO/image handling, no organize plan, no filesystem mutation of any kind,
no Amane dependency, no persistence, no CLI/UI. See section 9 for the full
out-of-scope list carried from the task brief.

## 1. Architecture and dependency direction

```text
fc2_organizer
    |
    v
fc2_metadata_core
```

`fc2_metadata_core` never imports `fc2_organizer`. Nothing under
`fc2_organizer` may import `amane`.

`fc2_organizer.discovery` currently depends on **zero** `fc2_metadata_core`
modules -- not even `normalize`. Media identity in this package is the
filesystem path (`source_path` + `index`), never a parsed FC2 number
(section 4), so there is nothing here for `normalize` to do. This is
enforced (not just observed) by `tests/contract/test_discovery_architecture.py`,
which additionally forbids, by both a static AST scan and a dynamic
import-blocking meta path finder exercised against a real end-to-end
`discover_media` call:

* `amane` (any submodule),
* `fc2_metadata_core.sources` (adapters, HTTP source framework),
* `fc2_metadata_core.aggregation` (multi-source execution internals),
* `fc2_metadata_core.resource_control` (governor / circuit breaker / host limiter internals),
* `fc2_metadata_core.http` (the HTTP transport).

## 2. Public API

```python
from fc2_organizer.discovery import (
    DiscoveryPolicy,
    DiscoveredMediaItem,
    DiscoveryIssue,
    DiscoveryIssueKind,
    DiscoveryStage,
    DiscoveryResult,
    discover_media,
)

result: DiscoveryResult = discover_media(root, policy=DiscoveryPolicy())
```

* `root: str | os.PathLike` -- a directory path. A bad type (not `str`/`os.PathLike`,
  or an empty string) raises `DiscoveryInputError` (`TypeError` subclass) before
  any filesystem access.
* `policy: DiscoveryPolicy | None` -- defaults to `DiscoveryPolicy()` (the built-in
  extension set, section 5) when omitted. A non-`DiscoveryPolicy` value raises
  `DiscoveryInputError`.
* Returns a `DiscoveryResult` on success. Raises a `DiscoveryRootError` subclass
  (section 8) if the root itself cannot be scanned -- never an empty-looking
  success for a root-level problem.

All four result models (`DiscoveryPolicy`, `DiscoveredMediaItem`, `DiscoveryIssue`,
`DiscoveryResult`) are frozen dataclasses with `slots=True`: immutable, no
attribute can be added or reassigned post-construction, every field is a plain
`str`/`int`/`Enum`/`tuple` (serialization-friendly; no exception object, no
traceback, no open handle, no caller-owned mutable container ever stored).

## 3. `DiscoveredMediaItem`

Fields (frozen, all validated in `__post_init__`, `DiscoveryContractError` on
violation): `index: int` (>= 0), `source_path: str` (absolute, OS-native
separators, non-empty), `relative_path: str` (relative to the scanned root,
**POSIX-style forward slashes via `Path.as_posix()`** regardless of host OS --
chosen for a stable, serializable representation independent of platform),
`extension: str` (lowercase, dot-prefixed, e.g. `.mp4`), `size: int` (bytes,
>= 0, from `os.stat(..., follow_symlinks=False)`).

No scraped title, actors, studio, NFO/image status, target path, move status,
Amane state, or database state is present, by design (task brief section 6) --
those belong to later phases.

Identity within one `DiscoveryResult` is `(source_path, index)`, **never** a
parsed FC2 number: `A/FC2-1234567.mp4` and `B/FC2-1234567.mp4` are two
independent items (section 6 below).

## 4. FC2 number boundary

This package implements no second FC2 recognizer. It does not call
`fc2_metadata_core.normalize.normalize_fc2_number` and does not need to: its
only job is "is this a supported media file at this path", decided purely by
extension (section 5). Whether a filename happens to look like an FC2 number
is irrelevant to discovery and is entirely the concern of a later phase.

## 5. `DiscoveryPolicy` and supported extensions

`supported_extensions: frozenset[str]`, default:

```text
.mp4  .mkv  .avi  .mov  .wmv  .m4v  .ts
```

Chosen for breadth over precision -- common video containers a user's FC2
library is realistically stored in; a rare container false-negative is worse
than a stray non-video false-positive with this extension (there is no
content sniffing in v1.0). Overridable via `DiscoveryPolicy(supported_extensions=...)`.

* Normalized at construction: entries are lower-cased and required to be
  `.`-prefixed, non-empty after the dot; a bare `str`/`bytes` argument (an
  iterable of *characters*, not extensions) is explicitly rejected rather
  than silently misinterpreted.
* Matching is **case-insensitive** by construction-time normalization:
  `VIDEO.MP4` and `video.mp4` match the same policy entry.
* Extension is the **only** signal used to decide "is this media" -- no
  filename convention (`~prefix`, `.part`, timestamps, ...) is special-cased.
  A `.part`/`.tmp` sidecar is excluded because that is not a supported
  extension, not because of any "looks like a partial download" heuristic.
* This is the single, centralized place extensions are declared; nothing
  else in the package hard-codes an extension list.

## 6. Duplicate-safety (frozen)

The same FC2 number (or the same plain filename) appearing under two
different directories always produces two independent `DiscoveredMediaItem`s.
There is no dedupe by number and no `dict[number, ...]` anywhere in the
scanner. `DiscoveryResult.__post_init__` enforces the complementary
invariant: no two items may share the same `source_path` (an actual,
physical duplicate discovery would be a scanner bug, not a legitimate
result).

## 7. Deterministic ordering (frozen)

Traversal never relies on raw OS directory-enumeration order
(`os.scandir()`/`Path.iterdir()` order is unspecified across platforms and
even across repeated calls on some filesystems). Instead:

1. Within one directory, all immediate entries (files and subdirectories
   together) are sorted by `entry.name` using plain Python string (Unicode
   code-point / ordinal) comparison -- locale-independent, not "natural"
   sort, just stable and reproducible. A directory's entries have unique
   names by filesystem construction, so this ordering has no ties to break.
2. The tree is walked **depth-first, pre-order**: at each directory, entries
   are visited in that sorted order; when a subdirectory entry is reached, it
   is recursed into immediately (its entire subtree is fully visited) before
   the parent directory's next sorted sibling is visited.
3. Each `DiscoveredMediaItem.index` is assigned in the exact order media
   files are appended during that traversal (a single, per-call counter
   starting at 0).

Consequence: for the same, unchanged directory tree, repeated calls to
`discover_media` produce byte-identical `relative_path` ordering and
`index` assignment. Adding, removing, or renaming any file/directory can
change subsequent indices (indices are positional, not stable identifiers
across tree mutation -- this is expected: v1.0 discovery is a one-shot
snapshot, not a diff engine).

Known limitation: traversal recurses using the Python call stack (one frame
per directory depth). An extremely deep tree (approaching
`sys.getrecursionlimit()`, ~1000 by default) could raise `RecursionError`.
No real FC2 media library is expected to nest anywhere near that deep;
out of scope for v1.0 (see "Known Limitations" in the P4-C1 handoff).

## 8. Root failure semantics (frozen)

`discover_media` raises, and never silently downgrades to an empty
`DiscoveryResult`:

| Condition | Exception |
|---|---|
| root does not exist | `DiscoveryRootNotFoundError` |
| root exists but is not a directory (including a path with a non-directory parent component) | `DiscoveryRootNotADirectoryError` |
| root exists but cannot be accessed (`PermissionError` or other `OSError` while stat-ing it) | `DiscoveryRootAccessError` |
| `root` argument has the wrong type, or is an empty string | `DiscoveryInputError` |
| `policy` argument is not a `DiscoveryPolicy` | `DiscoveryInputError` |

All of the above (except the two `DiscoveryInputError` cases, which are
argument-contract violations) subclass `DiscoveryRootError`, itself a
`DiscoveryError`. A successfully returned `DiscoveryResult` therefore always
means "root existed, was a directory, was accessible" -- `items`/`issues`
may still both be empty for a genuinely empty, fully-readable tree, and that
case is indistinguishable from itself only, never from a root failure.

## 9. Subtree / item failure isolation (frozen)

A non-root problem encountered while walking (permission denied on a
subdirectory, a directory or file that vanishes mid-scan, a stat failure)
is never silently swallowed and never aborts the whole scan. It is recorded
as one `DiscoveryIssue` and traversal continues with the next sibling /
directory.

`DiscoveryIssue` fields: `path: str`, `kind: DiscoveryIssueKind`,
`stage: DiscoveryStage`, `detail: str`.

`DiscoveryIssueKind`: `PERMISSION_DENIED`, `PATH_VANISHED`, `STAT_FAILED`,
`SYMLINK_SKIPPED`, `REPARSE_POINT_SKIPPED`.

`DiscoveryStage`: `LIST_DIRECTORY`, `CLASSIFY_ENTRY`, `STAT_ENTRY`.

`detail` is **never** `str(exc)`/`repr(exc)`, never a traceback, never the
exception object -- `DiscoveryIssue.build(path, kind, stage)` is the only
constructor the scanner uses, and it always attaches one of five fixed,
short, canned messages keyed by `kind` (e.g. `"permission denied"`). This is
bounded and sanitized by construction, not by post-hoc truncation (though
`DiscoveryIssue.__post_init__` additionally hard-truncates any `detail`
longer than `MAX_ISSUE_DETAIL_LENGTH` = 200 chars as a defense-in-depth
backstop for direct construction).

Filesystem seams (`scanner._list_directory_sorted`, `scanner._stat_entry`,
`scanner._is_symlink`) are isolated as small module-level functions
specifically so tests can inject `PermissionError` / `FileNotFoundError` /
`OSError` at an exact point via `monkeypatch`, rather than depending on
flaky, hard-to-construct real OS race conditions or real permission denial
against the invoking user's own files (unreliable on Windows in particular).

## 10. Symlink / junction / reparse-point policy (frozen, mandatory, non-configurable)

* A directory entry that is a symlink (`os.DirEntry.is_symlink()`) is
  **never** recursed into if it is a directory, and **never** treated as a
  normal media source if it is a file -- regardless of what it points to.
  Recorded as `DiscoveryIssueKind.SYMLINK_SKIPPED` at `CLASSIFY_ENTRY`.
* A directory entry that is a Windows **reparse point** (junctions and any
  other NTFS reparse tag) is likewise never recursed into, even though
  `os.DirEntry.is_symlink()` reports `False` for a junction (junctions carry
  `IO_REPARSE_TAG_MOUNT_POINT`, not `IO_REPARSE_TAG_SYMLINK`). Detected via
  `fc2_organizer.discovery._platform.is_reparse_point`, which reads
  `os.lstat(path).st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT` --
  deliberately *not* `os.path.isjunction` (Python 3.12+ only; this project
  targets 3.11+) and deliberately keyed on the attribute bit rather than the
  specific reparse tag, so *any* reparse kind is treated conservatively as
  unsafe. Always returns `False` on non-Windows (`os.name != "nt"`).
  Recorded as `DiscoveryIssueKind.REPARSE_POINT_SKIPPED`.
* This is a **fixed v1.0 safety invariant, not a policy knob** --
  `DiscoveryPolicy` has no `follow_symlinks` field. Rationale: prevents
  infinite recursion (a symlink/junction loop), prevents scanning outside
  `root` (a link pointing elsewhere), and prevents double-counting the same
  physical files through two different paths.
* Conservative choice for a symlinked **file** specifically (task brief
  section 11): rather than resolve and stat through it, it is excluded from
  results entirely, exactly like a symlinked directory is excluded from
  recursion. A future phase may revisit this with an explicit opt-in policy
  if a real use case needs it; v1.0 does not guess.

## 11. Test matrix (`tests/unit/discovery/`, `tests/contract/test_discovery_architecture.py`)

| # | Requirement | Test file |
|---|---|---|
| 1-7, 9-10, 12-15 | empty root, single/nested/deep/mixed files, unsupported ignored, case-insensitive, Unicode names, unusual valid chars | `test_discovery_basic.py` |
| 8, 9, 23 | duplicate FC2 number across dirs, duplicate filename across dirs, exact-once discovery | `test_discovery_duplicates_and_ordering.py` |
| 11 | deterministic ordering across repeated scans | `test_discovery_duplicates_and_ordering.py` |
| 16-18 | permission-denied subtree, file vanishes before stat, directory vanishes during scan (injected via monkeypatch) | `test_discovery_failure_isolation.py` |
| 19-21 | symlink dir/file not followed, symlink loop does not hang, junction not followed, junction loop does not hang, junction escaping root not followed | `test_discovery_symlinks_and_junctions.py` |
| 21 (platform abstraction) | `is_reparse_point` unit-tested independent of a real junction | `test_discovery_platform_helper.py` |
| 22, 24 | large synthetic tree stage gate, sidecar files never become items | `test_discovery_stage_gate.py` |
| 25-27 | no filesystem mutation, no network dependency, no Amane dependency | `test_discovery_no_mutation.py`, `tests/contract/test_discovery_architecture.py` |
| model contracts | `DiscoveredMediaItem`/`DiscoveryIssue`/`DiscoveryResult` invariants | `test_discovery_models.py` |
| policy contract | extension normalization / validation | `test_discovery_policy.py` |
| root failure semantics | `test_discovery_root_failures.py` |
| architecture / dependency direction | `tests/contract/test_discovery_architecture.py` |

## 12. Performance boundary (frozen)

Discovery reads filesystem metadata only (`os.scandir`, `entry.stat()`);
it never reads file content, never hashes a file, and never re-lists an
already-visited directory. Memory grows linearly with
`len(items) + len(issues)`; live recursion depth grows with directory
nesting depth, not with the total number of files (siblings in one
directory are processed and discarded from the call stack one at a time,
not held open simultaneously).

## 13. Out of scope (task brief section 16, carried here verbatim in spirit)

No metadata scraping, no `SourceAdapter`/`MultiSourceEngine`/retry/resource
governor/`BatchScheduler` changes, no `OrganizePlan`, no output naming or
target directory generation, no NFO rendering/writing, no
poster/fanart/thumb/extrafanart downloading or image validation, no
artifact writer, no `mkdir`/rename/move/copy/delete of organizer source
media, no filesystem executor, no preview UI, no CLI report system, no JSON
diagnostics, no persistent job/database/resume, no Amane adapter, no HTTP
service/REST API/GUI.

## 14. Backlog carried forward (not addressed by P4-C1)

Not triggered / not addressed: `C2-L2`, `P2-R-05`, `P2-R-06`, `P2-R-07`,
`P2-R-10`, `C3-N1`, `C3-N2`, `C3-N3`, `C3-N4`, `C4-N1`, `C4-R1-N1`,
`C4-R1-N2`, `C4-R1-N3`, `F3`, `F5`, `C5-R1-L1`. None of these debts is
touched, read, or relevant to this package; `fc2_organizer.discovery` has
zero dependency on the modules any of them concern.
