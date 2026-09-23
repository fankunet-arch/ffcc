# FC2 Organizer -- Phase 4 / P4-C6 Atomic Artifact Materialization Contract

Status: **substep 1 frozen candidate** (atomic single-artifact primitive). Later
substeps are marked **PENDING IN LATER P4-C6 SUBSTEP**. Independent review REQUIRED.
Package: `fc2_organizer.materialization` (`__init__.py`, `errors.py`, `models.py`, `atomic.py`).
Frozen Base: `e44790f57004825957f2212921171667e7c576cf`
Branch: `claude/phase4-c6-atomic-materialization`

## 1. Scope

P4-C6 as a whole: land artifact *contents* (NFO text, acquired images) on disk
safely -- complete or not at all, never overwriting anything.

**Substep 1 delivers only** one primitive: atomic creation of **one** file with
exact `bytes`, inside a directory that **already exists**:

```text
bytes payload
  -> exclusive temporary sibling file
  -> write all bytes, fsync, close
  -> atomic no-overwrite publish to the final path
  -> failure cleanup of exactly the owned temporary path
```

Substep 1 does **not**: execute or read an `OrganizePlan`, move media, create
any directory (target directory or `extrafanart/`), map NFO / image roles to
paths, materialize in batch, move across volumes, preflight writability, or
orchestrate operations.

## 2. Separation from P4-C7 (frozen)

| P4-C6 (this package) | P4-C7 (future, not here) |
|---|---|
| safe on-disk landing of one artifact's bytes | whole-plan preflight |
| | `mkdir` of target / `extrafanart` directories |
| | `MOVE_MEDIA`, cross-volume handling |
| | operation-graph execution, filesystem orchestration |

The writer's precondition is that the target's parent directory already
exists. A missing parent fails closed; nothing is created.

## 3. Public API

```python
from fc2_organizer.materialization import materialize_atomic_bytes, MaterializedArtifact

materialize_atomic_bytes(target_path: str, content: bytes) -> MaterializedArtifact
```

Synchronous. Exactly two positional parameters; there is **no** `overwrite`,
`exist_ok`, suffix, mode, `mkdir`, fsync-toggle or filesystem-ops parameter.
The failure-injection seam (`atomic._FS`) is private and not exported.

The layer accepts only exact bytes. It does not accept `PublicationRecord`,
`OrganizePlan`, `AcquiredImage` or NFO `str`; mapping those to bytes/paths is
**PENDING IN LATER P4-C6 SUBSTEP**.

## 4. Input boundary (frozen)

Checked in this order, before any filesystem access and without invoking any
method of the argument:

1. `type(target_path) is str` -- else `MaterializationInputError`. `pathlib.Path`,
   any `os.PathLike`, `bytes` paths and `str` subclasses are rejected;
   `__fspath__` / `__str__` hooks never run.
2. `type(content) is bytes` -- else `MaterializationInputError`. `bytearray`,
   `memoryview`, `bytes` subclasses (hooks never run), `str` are rejected.
3. Lexical path validation (`InvalidTargetPathError`, `.reason`), by the
   runtime OS:
   * `EMPTY`, `NUL_CHARACTER`;
   * `NOT_ABSOLUTE`: Windows requires a drive letter with root (`C:\x`, `C:/x`)
     or a UNC share (`\\server\share\x`); rooted-but-driveless (`\x`), drive-
     relative (`C:x`) and relative forms are rejected. POSIX requires
     `os.path.isabs`. `~`, `$VAR`, `%VAR%` are never expanded (so they are
     simply non-absolute); no cwd is consulted.
   * Windows only: `DEVICE_NAMESPACE` (`\\?\`, `\\.\`), `ILLEGAL_CHARACTER`
     (`<>:"|?*`, control chars -- a `:` would address an NTFS alternate data
     stream), `TRAILING_DOT_OR_SPACE`, `RESERVED_NAME` (`CON`, `NUL`, `COM1`...).
   * `NO_BASENAME` (trailing separator), `DOT_SEGMENT` (`.` / `..` anywhere).

The path is never normalized, resolved or made absolute. This does not
re-implement the P4-C2 planner; it only refuses ambiguous input.

## 5. Parent / target preconditions (frozen)

* Parent (`dirname(target_path)`) is `stat`-ed: absent (or a path through a
  file) -> `ParentDirectoryMissingError`; exists but not a directory ->
  `ParentNotDirectoryError`; any other OS error -> `ParentDirectoryError`
  (`reason=INACCESSIBLE`). **Never created.**
* Target is `lstat`-ed (never followed): if *anything* exists -- file,
  directory, symlink, dangling symlink, junction -> `TargetExistsError`. An
  `lstat` OS error other than "not found" -> `TargetInaccessibleError`.

This pre-check is an early exit only; section 7 carries the guarantee.

## 6. Overwrite = NEVER (frozen, inherited from P4-C2)

An existing final target is never overwritten, truncated, replaced, deleted,
renamed or suffixed (`(1)`, `_copy`, ...). There is no knob to change this.
`os.replace` is never used; there is no "check exists -> replace" path.

## 7. Atomic no-overwrite publish (frozen platform strategy)

Python's stdlib has no single cross-platform "rename without replace". The
frozen per-OS strategy (`atomic._publish_no_replace`):

| OS | primitive | existing target | temp afterwards |
|---|---|---|---|
| Windows (`os.name == "nt"`) | `os.rename` = `MoveFileExW` **without** `MOVEFILE_REPLACE_EXISTING` | fails `FileExistsError` for any entry (file, dir, symlink, junction); atomic within one volume | consumed by the rename |
| POSIX | `os.link(temp, target)` (`link(2)`) | fails `EEXIST`; never follows an existing target symlink | this call unlinks its own temp name |

Consequences (frozen):

* A target created by anyone between the pre-check and the publish is **never
  replaced**: the publish itself fails and is reported as `TargetExistsError`.
* The target appears either complete (all bytes, fsynced) or not at all.
* If the publish fails with another OS error and the target now exists,
  `TargetExistsError` is reported; otherwise `ArtifactPublishError(errno)`.
  This probe classifies the error only; it never triggers an action.
* POSIX filesystems without hard-link support fail closed with
  `ArtifactPublishError`; there is no fallback to `rename` / `replace`.
* Temp and target share a directory, so the publish never crosses a volume.
* Durability: the file data is `fsync`ed before publish; `fsync` of the
  parent directory entry is not performed in substep 1.

## 8. Temporary file (frozen)

* Name: `.fc2tmp-<32 lowercase hex from secrets.token_hex(16)>.part`, joined to
  the target's own parent -- a sibling. It never contains the target name,
  metadata, title, URL or any secret, and never influences the final content.
* Created with `O_WRONLY | O_CREAT | O_EXCL` (+ `O_BINARY` / `O_NOINHERIT` /
  `O_CLOEXEC` where available), never `O_TRUNC`, mode `0o666` (umask applies).
  Exclusive create never opens an existing entry and never follows a planted
  symlink.
* A name equal to the target (case-insensitively on Windows) is skipped. On
  `FileExistsError` a fresh token is tried, up to 8 attempts; the clashing
  entry is **not ours** and is never touched. Exhaustion or any other OS error
  -> `TemporaryCreateError(errno)`.

## 9. Ownership and failure cleanup (frozen)

* The call owns exactly one path: the temp it successfully exclusive-created.
  Ownership ends when the Windows rename consumes it or after the one POSIX
  post-publish unlink attempt.
* On any failure (write, flush, close, publish, or a `BaseException`), the
  call closes its descriptor if still open (errors ignored) and, if still
  owned, unlinks **that exact path** once. "Already gone" counts as cleaned.
* Never: glob / wildcard / listing-based cleanup, deleting other `.tmp` /
  `.part` / `.fc2tmp-*` files, deleting or modifying the final target (even
  when this call had just published it), deleting any directory.
* Short writes are continued; a zero-length write is `ArtifactWriteError(WRITE, EIO)`.

## 10. Cleanup failure and fatal control flow (frozen)

| primary | cleanup | raised |
|---|---|---|
| none (success) | -- | returns `MaterializedArtifact` |
| POSIX: publish succeeded, temp unlink fails | failed | `ArtifactCleanupError(target_published=True, primary=None)`; target is complete and kept |
| a `MaterializationError` | ok | the primary |
| a `MaterializationError` | failed | `ArtifactCleanupError(target_published=False, primary=<primary>)`, `__cause__` = primary |
| `KeyboardInterrupt`, `SystemExit`, `GeneratorExit`, any other `BaseException`, or a foreign `Exception` | ok or failed | the **same object**, unchanged; a cleanup failure never masks it |

Only `OSError` is intercepted around filesystem calls; a `BaseException`
raised inside cleanup itself propagates.

## 11. Typed errors (`errors.py`)

```text
MaterializationError(Exception)
+-- MaterializationInputError(MaterializationError, TypeError)
+-- InvalidTargetPathError(MaterializationError, ValueError)     .reason: TargetPathRejectionReason
+-- MaterializationModelError(MaterializationError, ValueError)
+-- ParentDirectoryError                                          .reason: ParentRejectionReason, .errno
|   +-- ParentDirectoryMissingError
|   +-- ParentNotDirectoryError
+-- TargetExistsError
+-- TargetInaccessibleError                                       .errno
+-- TemporaryCreateError                                          .errno
+-- ArtifactWriteError                                            .stage: ArtifactWriteStage (WRITE|FLUSH|CLOSE), .errno
+-- ArtifactPublishError                                          .errno
+-- ArtifactCleanupError                                          .target_published, .primary, .errno
```

No failure escapes as a bare `OSError` / `ValueError`. Messages are fixed
wording: no target path, no temp path / token, no payload, no `OSError`
text. Typed errors are raised outside any `except` block, so no `OSError`
(whose `filename` is the temp path) is ever attached as `__cause__` or
`__context__`; the only chaining is `ArtifactCleanupError` from its typed primary.

## 12. Result model

```python
@dataclass(frozen=True, slots=True)
class MaterializedArtifact:
    target_path: str   # the exact input string
    size_bytes: int    # len(content)
    sha256: str        # hashlib.sha256(content).hexdigest(), i.e. of the bytes written
```

Exact-type validated (`MaterializationModelError`). No temp path, handle,
exception or filesystem object is stored.

## 13. Concurrency guarantee (frozen)

N writers racing for one final target (threads or processes, same host
filesystem): at most one returns a `MaterializedArtifact`; every other gets
`TargetExistsError` (or an `ArtifactCleanupError` whose `primary` is one);
the winner's bytes are complete and never overwritten; every loser removes
only its own temp. This holds even when all racers pass the pre-check,
because the guarantee is the publish primitive's (section 7).

## 14. Architecture (frozen for substep 1)

* stdlib only: `__future__`, `dataclasses`, `enum`, `errno`, `hashlib`,
  `ntpath`, `os`, `posixpath`, `re`, `secrets`, `stat`, `typing`.
* Never imports `fc2_metadata_core`, `amane`, `httpx` or any network module,
  `shutil` / `tempfile` / `glob` / `fnmatch` / `pathlib`, or any other
  `fc2_organizer` package (`planning`, `nfo`, `images`, `publication`,
  `discovery`).
* No call to `replace`, `mkdir` / `makedirs`, `rmdir` / `rmtree` / `remove`,
  `listdir` / `scandir` / `walk` / `glob`, `expanduser` / `expandvars`,
  `getcwd`, `abspath` / `realpath` / `resolve` / `normpath`, `truncate`.
  `os.rename` / `os.link` appear only in `_publish_no_replace`; `unlink` is
  reached only through `_remove_owned_temp`.
* No reverse dependency: nothing else under `src` imports it;
  `fc2_organizer/__init__.py` does not eagerly import it.
* No `executor.py`, `planner.py`, `move.py`, `orchestrator.py`.
* Top-level `fc2_organizer` subpackages are now
  `{"discovery", "planning", "publication", "nfo", "images", "materialization"}`;
  the four existing package-set scope guards were updated by one line each.

Enforced by `tests/contract/test_materialization_architecture.py`.

## 15. Test matrix (substep 1)

| requirement | test file |
|---|---|
| exact bytes, zero-byte, binary, multi-chunk; size / sha256; no temp left; sibling random temp | `tests/unit/materialization/test_materialization_atomic.py` |
| existing file / directory / symlink / dangling symlink / junction -> `TargetExistsError`, untouched; pre-check uses `lstat` (host-independent); no overwrite knob / suffix | `test_materialization_atomic.py` |
| parent missing / is a file / through a file / inaccessible; target un-probeable | `test_materialization_atomic.py` |
| `bytearray` / `memoryview` / hostile `bytes` subclass / `PathLike` / hostile `str` subclass rejected, zero hooks, zero I/O | `test_materialization_atomic.py` |
| write (mid-way), short write, zero write, flush, close, publish failures -> no target, owned temp removed | `test_materialization_failures.py` |
| target / directory / symlink planted between pre-check and publish -> never replaced | `test_materialization_failures.py` |
| cleanup failure typed (`target_published` False / True), planted unrelated temps survive, temp-name clash & exhaustion, secret-free unchained errors | `test_materialization_failures.py` |
| `KeyboardInterrupt` / `SystemExit` / `GeneratorExit` / custom `BaseException` propagate as the same object; cleanup failure never masks them | `test_materialization_failures.py` |
| same-target race: barrier-forced (both past pre-check) and unsynchronized 8-writer rounds | `test_materialization_race.py` |
| Windows + POSIX path rules (pure), result model | `test_materialization_paths_and_models.py` |
| architecture boundary | `tests/contract/test_materialization_architecture.py` |

Publish-dependent tests run under both strategies on the development host:
`native` and `hardlink` (the POSIX `link` + unlink strategy, exercised via the
private seam on NTFS, which supports hard links). Tests that create real
symlinks skip on hosts without symlink privilege (Windows without Developer
Mode); junctions and the `lstat` simulation cover that host.

## 16. PENDING IN LATER P4-C6 SUBSTEP

* artifact mapping (plan role -> path -> bytes);
* NFO materialization (`render_movie_nfo` text -> UTF-8 bytes -> `nfo_path`);
* image materialization (`AcquiredImage` -> `poster` / `fanart` / `thumb`);
* extrafanart materialization (into an existing `extrafanart/`; directory
  creation remains P4-C7);
* final P4-C6 handoff.
