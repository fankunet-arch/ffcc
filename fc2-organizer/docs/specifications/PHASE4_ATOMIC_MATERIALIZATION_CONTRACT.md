# FC2 Organizer -- Phase 4 / P4-C6 Atomic Artifact Materialization Contract

Status: **substeps 1-2 frozen candidate** (atomic single-artifact primitive; artifact
mapping + single-artifact materializer). Anything still open is marked **PENDING IN
LATER P4-C6 SUBSTEP** (section 25). Independent review REQUIRED.
Package: `fc2_organizer.materialization` (`__init__.py`, `errors.py`, `models.py`, `atomic.py`,
`artifacts.py`, `mapping.py`).
Frozen Base: `e44790f57004825957f2212921171667e7c576cf`
Substep 1 Head: `b088db8acb2c4ae47037d58546000c41543b73b1`
Substep 2 Head: `67fb857523c59b3cd19691caedf3316171f8e0ca` (substep 2A corrects the extrafanart naming boundary, section 21)
Branch: `claude/phase4-c6-atomic-materialization`

Sections 1-15 were frozen in substep 1 and are **unchanged in substep 2** except
for the additive notes marked *(substep 2)*. Sections 16-24 are **IMPLEMENTED IN
SUBSTEP 2**.

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

**Substep 2 delivers only** (sections 16-24): the artifact kinds and request
model, the pure `build_artifact_requests` mapping (plan + rendered NFO `str` +
acquired images -> ordered requests), the frozen NFO UTF-8 rule, image byte
identity, deterministic extrafanart naming, and the single-artifact wrapper
`materialize_artifact(request)`. It still does not create directories, move
media, read or execute `OrganizePlan.operations`, orchestrate several
artifacts, or roll anything back.

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
`OrganizePlan`, `AcquiredImage` or NFO `str`. *(substep 2)* Mapping those to
paths/bytes is the separate `mapping` module (section 17); the primitive itself
is unchanged.

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
+-- ArtifactMappingError(MaterializationError, ValueError)        .reason: MappingRejectionReason   (substep 2)
```

*(substep 2)* `MappingRejectionReason`: `NFO_EMPTY`, `NFO_NOT_UTF8_ENCODABLE`,
`PLAN_PATH_INVALID`, `IMAGE_INVALID`, `INVALID_EXTRAFANART_ORDINAL`, `DUPLICATE_TARGET`
(substep 2A replaced the former `EXTRAFANART_LIMIT`; see section 21).
`MaterializationModelError` also covers an invalid `ArtifactWriteRequest`;
`MaterializationInputError` also covers a wrong-type mapping / wrapper input.

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
* *(substep 2)* The stdlib-only rule above applies to every module **except
  `mapping.py`** (section 23). `artifacts.py` is stdlib / own-package only.
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

## 16. Artifact kinds and request model (IMPLEMENTED IN SUBSTEP 2)

```python
class ArtifactKind(Enum):
    NFO = "nfo"; POSTER = "poster"; FANART = "fanart"; THUMB = "thumb"; EXTRAFANART = "extrafanart"

@dataclass(frozen=True, slots=True)
class ArtifactWriteRequest:
    kind: ArtifactKind
    target_path: str          # non-empty exact str
    content: bytes            # exact bytes, excluded from repr
    ordinal: int | None = None  # exact int >= 1 iff kind is EXTRAFANART, else None
```

Exact-type validated (`MaterializationModelError`; `bool` is not an `int`,
subclasses never pass). It stores **no** `PublicationRecord`, `AcquiredImage`,
`OrganizePlan`, URL, HTTP data or exception -- only a path and bytes. Both are
exported from `fc2_organizer.materialization`.

## 17. Pure mapping API (IMPLEMENTED IN SUBSTEP 2)

```python
from fc2_organizer.materialization.mapping import build_artifact_requests

build_artifact_requests(
    plan: OrganizePlan,               # exact type
    nfo_text: str,                    # exact type; already rendered (P4-C4)
    images: ImageAcquisitionResult,   # exact type; already acquired (P4-C5)
) -> tuple[ArtifactWriteRequest, ...]
```

* Input identity first, in this order: `type(plan) is OrganizePlan`,
  `type(nfo_text) is str`, `type(images) is ImageAcquisitionResult`, else
  `MaterializationInputError` -- **before any attribute or method** of a
  rejected object is touched (a subclass's hooks never run).
* Pure and deterministic: **zero filesystem access** (only the lexical
  `os.path.join`), no clock, randomness, network, NFO rendering or image
  acquisition. Identical inputs give an equal tuple.
* Never reads `OrganizePlan.operations` (behaviourally and AST-enforced),
  never re-parses / re-validates `plan.canonical_number`.
* Each plan path read must be an exact `PlannedPath` whose `absolute_path` is a
  non-empty exact `str` (`PLAN_PATH_INVALID` otherwise, e.g. a forged plan).
* All request target paths must be distinct (case-insensitively on Windows);
  otherwise `DUPLICATE_TARGET` (defends against a forged plan; a real P4-C2
  plan never collides).

## 18. Mapping order (frozen)

```text
NFO                                   always, exactly one
POSTER                                iff images.poster is not None
FANART                                iff images.fanart is not None
THUMB                                 iff images.thumb  is not None
EXTRAFANART x N                       images.extrafanart, in tuple order
```

The extrafanart order is the `ImageAcquisitionResult.extrafanart` tuple order
(itself the P4-C5 candidate order), never re-sorted by `candidate_index`, size or hash.

## 19. NFO -> bytes (frozen)

`nfo_text.encode("utf-8", errors="strict")` -- exactly that, nothing else:
no BOM is added, newlines are not changed (`\r\n` stays `\r\n`), nothing is
stripped, Unicode is not normalized, the XML is not re-parsed or rewritten, and
a caller-supplied leading U+FEFF is encoded as-is (not removed). Target:
`plan.nfo_path`. An empty `str` -> `ArtifactMappingError(NFO_EMPTY)` (an empty
`.nfo` is never a valid P4-C4 render); a lone surrogate ->
`NFO_NOT_UTF8_ENCODABLE`, raised with no chained `UnicodeEncodeError`.

## 20. Image mapping (frozen)

| `ImageAcquisitionResult` field | required role | kind | target |
|---|---|---|---|
| `poster` | `ImageRole.POSTER` | `POSTER` | `plan.poster_path` |
| `fanart` | `ImageRole.FANART` | `FANART` | `plan.fanart_path` |
| `thumb` | `ImageRole.THUMB` | `THUMB` | `plan.thumb_path` |
| each of `extrafanart` | `ImageRole.EXTRAFANART` | `EXTRAFANART` | section 21 |

* A missing (`None`) image produces **no request and no failure**. There is
  **no cross-role fallback** (e.g. fanart never fills an absent poster).
* `request.content` **is** `AcquiredImage.content` (same object): no
  re-encode, resize, crop, transcode, copy or re-validation.
* Identical bytes in several roles or repeated in extrafanart are **not**
  de-duplicated; each yields its own request and file.
* An image that is not an exact `AcquiredImage` of the expected role with exact
  `bytes` content (only possible with a forged result) -> `IMAGE_INVALID`.

## 21. Extrafanart naming (frozen)

No earlier frozen document names extrafanart files (the v1.0 spec, P4-C2 and
P4-C5 fix only the `extrafanart/` directory), so substep 2 freezes:

```text
<plan.extrafanart_directory>/extrafanart-001.jpg
<plan.extrafanart_directory>/extrafanart-002.jpg
...
```

* `ordinal` = 1-based position in `images.extrafanart`; name =
  `f"extrafanart-{ordinal:03d}.jpg"` (`extrafanart_filename(ordinal)`).
* Never derived from a URL basename, title, hash, `candidate_index` or randomness.
* *(substep 2A)* `ordinal` is **any exact positive `int`** -- there is **no
  maximum**. `03d` is a *minimum* width only: `1 -> extrafanart-001.jpg`,
  `12 -> extrafanart-012.jpg`, `999 -> extrafanart-999.jpg`,
  `1000 -> extrafanart-1000.jpg`, `10000 -> extrafanart-10000.jpg`. Every
  entry of `images.extrafanart` yields a request; nothing is truncated, wrapped
  (modulo) or dropped, and names stay unique. The P4-C5
  `ImageAcquisitionPolicy.max_extrafanart` default of 12 is only a default of
  that policy (which is itself unbounded above), **not** a P4-C6 limit.
* `extrafanart_filename` rejects `0`, negatives, `bool`, `float`, `str` and
  `int` subclasses with `ArtifactMappingError(INVALID_EXTRAFANART_ORDINAL)`.
  (Substep 2's `MAX_EXTRAFANART_ORDINAL = 999` cap and its `EXTRAFANART_LIMIT`
  reason were removed in substep 2A: P4-C6 must not add a limit P4-C5 does not have.)
* The directory is **not created** here; if it does not exist, the write of
  each extrafanart request fails with the primitive's `ParentDirectoryMissingError`.

## 22. Single-artifact materializer (frozen)

```python
from fc2_organizer.materialization import materialize_artifact

materialize_artifact(request: ArtifactWriteRequest) -> MaterializedArtifact
```

* `type(request) is ArtifactWriteRequest`, else `MaterializationInputError`
  (no hook of a subclass runs, the primitive is not reached).
* Its only action: `materialize_atomic_bytes(request.target_path, request.content)`.
  It returns that result and lets every typed error through unchanged.
* **One call = one artifact.** It therefore inherits sections 4-13 verbatim:
  overwrite = NEVER for the NFO, poster, fanart, thumb and every extrafanart
  file (`TargetExistsError`, no suffix); missing parent -> `ParentDirectoryError`
  family, never `mkdir`.

## 23. No multi-artifact orchestration, no mkdir, no MOVE_MEDIA (frozen)

* There is no `materialize_all`, `execute_plan`, `apply_operations`,
  `transaction` or `rollback_all`. Writing several artifacts, their order,
  partial-failure policy and any directory creation belong to the P4-C7
  executor.
* Because every call handles exactly one request, there is **no concept of
  rollback** here: if the NFO was written and a later poster write fails, the
  NFO stays (tested).
* No `mkdir` / `makedirs` anywhere in the package (AST-enforced); the target
  directory and `extrafanart/` must already exist.
* `MOVE_MEDIA`, `CREATE_DIRECTORY`, `ENSURE_EXTRAFANART_DIRECTORY` and all
  other `PlannedOperation`s are never read or executed.

**Architecture of `mapping.py` (frozen).** The only module that imports
another `fc2_organizer` package: exactly the `fc2_organizer.planning` and
`fc2_organizer.images` **public packages** (models only: `OrganizePlan`,
`PlannedPath`, `AcquiredImage`, `ImageAcquisitionResult`, `ImageRole`) plus
`os`. Never `fc2_metadata_core`, `amane`, `httpx`, `images.transport`,
`images.acquisition`, `nfo` (the renderer is not called; only its output `str`
is consumed), `publication`, `discovery`, or `atomic` / `artifacts`. Its only
`os` call is `os.path.join`. Because `fc2_organizer.planning` loads
`fc2_metadata_core` transitively, `mapping` is **not** imported by
`materialization/__init__.py` (a bare `import fc2_organizer.materialization`
still loads no planning / images / core module); import it explicitly. A
runtime test proves `mapping` imports and works with `amane`, `httpx`,
`images.transport`, `images.acquisition`, `nfo` and `publication` blocked.

## 24. Test matrix (substep 2)

| requirement | test file |
|---|---|
| NFO-only / full manifest, missing optional images (7 combinations), no cross-role fallback, fixed order, exact targets, determinism | `tests/unit/materialization/test_materialization_mapping.py` |
| extrafanart order (tuple, not `candidate_index`), `extrafanart-001..012.jpg`, no URL/title/hash; *(2A)* `03d` minimum width (1/12/999/1000/10000), no maximum, 1000 extrafanart mapped in memory (last `extrafanart-1000.jpg`, replay identical), 0 / negative / bool / float / int-subclass rejected | `test_materialization_mapping.py` |
| exact UTF-8, Unicode / emoji, CRLF / whitespace / U+FEFF / decomposed form preserved, no BOM, empty NFO, unencodable NFO (unchained) | `test_materialization_mapping.py` |
| image bytes identity (`is`), duplicate bytes not de-duplicated, request holds no foreign object | `test_materialization_mapping.py` |
| hostile `str` NFO subclass, plan / images subclass (zero attribute access), wrong types, forged path / colliding paths / wrong-role image | `test_materialization_mapping.py` |
| canonical number not re-parsed, `operations` not consulted, zero filesystem calls (os / os.path / open / primitive trapped) | `test_materialization_mapping.py` |
| request model rules, exactly five kinds | `test_materialization_mapping.py` |
| NFO / poster / extrafanart / full manifest written, exact bytes, sha256 / size | `tests/unit/materialization/test_materialization_artifacts.py` |
| existing target of every kind -> `TargetExistsError`, untouched, no leftover temp | `test_materialization_artifacts.py` |
| missing target directory / `extrafanart/` -> `ParentDirectoryMissingError`, never created (`mkdir` trapped) | `test_materialization_artifacts.py` |
| no rollback of an earlier success; wrapper only delegates; non-request / subclass rejected | `test_materialization_artifacts.py` |
| mapping / wrapper architecture, `__init__` never loads mapping | `tests/contract/test_materialization_architecture.py` |

## 25. PENDING IN LATER P4-C6 SUBSTEP

* final P4-C6 handoff.
