"""Media transfer for ``fc2_organizer.execution`` (P4-C7 S3; contract sections 17-20, 23, 25, 26, 29).

:func:`transfer_media` executes unit U2 ``MOVE_MEDIA`` for one validated plan:

* ``SAME_VOLUME`` (contract section 18) -- one no-replace primitive chosen by the private strategy seam
  :data:`_SAME_VOLUME_STRATEGY`: ``"rename"`` (Windows ``os.rename`` = ``MoveFileExW`` without
  ``MOVEFILE_REPLACE_EXISTING``; one atomic step yields ``MEDIA_PUBLISHED`` + ``SOURCE_REMOVED``) or ``"link"``
  (POSIX ``link`` -> verify target -> directory ``fsync`` -> verify source -> ``unlink`` source). POSIX
  ``rename(2)`` (which replaces) is never used. ``EXDEV`` falls back to the cross-volume flow exactly once.
* ``CROSS_VOLUME`` (contract section 19) -- the frozen 10 steps: read-only source fd validated by ``fstat``,
  exclusive sibling temporary ``.fc2tmp-<32 hex>.part`` (``O_CREAT | O_EXCL``, never ``O_TRUNC``, at most 8
  names), streamed copy in blocks of at most 1 MiB with SHA-256 over the very bytes written, exact size,
  ``fsync`` + ``fstat`` + ``close`` of the temporary, source fd revalidation, no-replace publish, publish
  verification, POSIX directory ``fsync``, source path revalidation, and only then ``unlink`` of the source.
* ``SOURCE_REMOVAL_ONLY`` resume phase (contract section 14.4) -- only the frozen tail after a published
  final media: (POSIX directory ``fsync``) -> source path revalidation -> ``unlink`` source.

Mutation sites are frozen (architecture test): ``unlink`` only in :func:`_remove_owned_temp` and
:func:`_unlink_verified_source`; ``rename`` / ``link`` only in :func:`_same_volume_primitive` and
:func:`_publish_no_replace`. Every syscall goes through the private seam ``_fs._FS``.

Only ``OSError`` is translated into an ``ExecutionFailure`` (enum + errno + stage; never a path, token,
message or exception object). ``BaseException`` and foreign exceptions close the descriptors still open,
unlink the exact owned temporary once, and propagate as the same object. Nothing here ever deletes a final
target, a directory, a source that was not re-verified after a complete publish, or any temporary it did not
create itself; there is no rollback.

Standard library ``errno`` / ``hashlib`` / ``os`` / ``stat`` (``os.name``, lexical ``os.path`` and ``O_*``
flags only) and this package.
"""

from __future__ import annotations

import errno as _errno
import hashlib
import os

from fc2_organizer.execution import _fs
from fc2_organizer.execution.directories import revalidate_directory
from fc2_organizer.execution.errors import ExecutionInputError, ExecutionModelError
from fc2_organizer.execution.models import (
    CompletedEffect,
    EffectKind,
    EntryIdentity,
    EntryType,
    ExecutionFailure,
    ExecutionFailureKind,
    ExecutionStep,
    LeftoverTemporary,
    PathRole,
    TransferMode,
    TransferStage,
    same_identity,
)

__all__ = ["transfer_media", "TransferOutcome", "ResumePhase"]

# Private strategy seam (construction plan S3 item 2): the platform's no-replace primitive. It selects the
# same-volume primitive and the cross-volume publish primitive (contract sections 18, 19 step 7). Tests set
# it to "link" to execute the POSIX strategy on NTFS. Read at call time.
_SAME_VOLUME_STRATEGY = "rename" if os.name == "nt" else "link"
# Private seam: directory fsync exists on POSIX only (contract section 26: Windows cannot open a directory).
_DIRECTORY_FSYNC = os.name != "nt"

_STRATEGIES = ("rename", "link")
_CHUNK = 1 << 20                 # at most 1 MiB per read and per write
_MAX_TEMP_ATTEMPTS = 8
_TEMP_PREFIX = ".fc2tmp-"
_TEMP_SUFFIX = ".part"
_HEX_DIGITS = frozenset("0123456789abcdef")
_TEMP_MODE = 0o666               # the process umask applies
_ERROR_NOT_SAME_DEVICE = 17      # Windows ERROR_NOT_SAME_DEVICE
_TEMP_FLAGS = (
    os.O_WRONLY | os.O_CREAT | os.O_EXCL
    | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOINHERIT", 0) | getattr(os, "O_CLOEXEC", 0)
)
_DIRECTORY_FLAGS = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_CLOEXEC", 0)
_STEP = ExecutionStep.MOVE_MEDIA
_MISSING = (FileNotFoundError, NotADirectoryError)


# --------------------------------------------------------------------------- internal models


class ResumePhase:
    """Which part of U2 to run (internal): ``FULL`` or ``SOURCE_REMOVAL_ONLY`` (the frozen tail after a
    published final media, contract section 14.4). Only the two class singletons are accepted."""

    __slots__ = ("name",)

    FULL: ResumePhase
    SOURCE_REMOVAL_ONLY: ResumePhase

    def __init__(self, name: str) -> None:
        object.__setattr__(self, "name", name)

    def __setattr__(self, name: str, value: object) -> None:
        raise ExecutionModelError("ResumePhase is immutable")

    def __repr__(self) -> str:
        return f"ResumePhase.{self.name}"


ResumePhase.FULL = ResumePhase("FULL")
ResumePhase.SOURCE_REMOVAL_ONLY = ResumePhase("SOURCE_REMOVAL_ONLY")

_OUTCOME_FIELDS = ("effects", "failure", "transfer_mode", "media_sha256", "media_size", "leftover_temporaries")
_MEDIA_KINDS = (EffectKind.MEDIA_PUBLISHED, EffectKind.SOURCE_REMOVED)


def _is_sha256_hex(value: object) -> bool:
    return type(value) is str and len(value) == 64 and set(value) <= _HEX_DIGITS


class TransferOutcome:
    """Immutable result of :func:`transfer_media` (internal value model; strict exact types).

    * ``effects`` -- the NEW final effects of this call, in order (``MEDIA_PUBLISHED`` then ``SOURCE_REMOVED``);
    * ``failure`` -- the typed failure that stopped the unit, or ``None`` iff the source was removed;
    * ``transfer_mode`` -- the mode actually used (``CROSS_VOLUME`` after an ``EXDEV`` fallback);
    * ``media_sha256`` -- SHA-256 of the copied bytes, only for a published cross-volume copy;
    * ``media_size`` -- size of the published final media, only when ``MEDIA_PUBLISHED`` happened here;
    * ``leftover_temporaries`` -- owned temporaries whose single cleanup attempt failed (never deleted later).
    """

    __slots__ = _OUTCOME_FIELDS

    def __init__(self, effects: tuple[CompletedEffect, ...], failure: ExecutionFailure | None,
                 transfer_mode: TransferMode, media_sha256: str | None, media_size: int | None,
                 leftover_temporaries: tuple[LeftoverTemporary, ...]) -> None:
        if type(effects) is not tuple or any(type(e) is not CompletedEffect or e.kind not in _MEDIA_KINDS
                                             for e in effects):
            raise ExecutionModelError("TransferOutcome.effects must be a tuple of media CompletedEffects")
        kinds = tuple(e.kind for e in effects)
        if kinds not in ((), (EffectKind.MEDIA_PUBLISHED,), (EffectKind.SOURCE_REMOVED,), _MEDIA_KINDS):
            raise ExecutionModelError("TransferOutcome.effects must follow MEDIA_PUBLISHED -> SOURCE_REMOVED")
        if failure is not None and (type(failure) is not ExecutionFailure or failure.step is not _STEP):
            raise ExecutionModelError("TransferOutcome.failure must be a MOVE_MEDIA ExecutionFailure or None")
        if (failure is None) != (kinds[-1:] == (EffectKind.SOURCE_REMOVED,)):
            raise ExecutionModelError("TransferOutcome.failure is None iff the source was removed")
        if type(transfer_mode) is not TransferMode:
            raise ExecutionModelError("TransferOutcome.transfer_mode must be a TransferMode")
        published = EffectKind.MEDIA_PUBLISHED in kinds
        if media_sha256 is not None and not (_is_sha256_hex(media_sha256) and published
                                             and transfer_mode is TransferMode.CROSS_VOLUME):
            raise ExecutionModelError("TransferOutcome.media_sha256 is set only for a published cross-volume copy")
        if media_size is not None and not (type(media_size) is int and media_size >= 0 and published):
            raise ExecutionModelError("TransferOutcome.media_size is an exact int >= 0 set only when published")
        if published and media_size is None:
            raise ExecutionModelError("a published TransferOutcome records media_size")
        if type(leftover_temporaries) is not tuple or any(type(item) is not LeftoverTemporary
                                                          for item in leftover_temporaries):
            raise ExecutionModelError("TransferOutcome.leftover_temporaries must be a tuple[LeftoverTemporary]")
        for name, value in zip(_OUTCOME_FIELDS, (effects, failure, transfer_mode, media_sha256, media_size,
                                                 leftover_temporaries)):
            object.__setattr__(self, name, value)

    def __setattr__(self, name: str, value: object) -> None:
        raise ExecutionModelError("TransferOutcome is immutable")

    def __delattr__(self, name: str) -> None:
        raise ExecutionModelError("TransferOutcome is immutable")

    def _values(self) -> tuple:
        return tuple(getattr(self, name) for name in _OUTCOME_FIELDS)

    def __eq__(self, other: object) -> bool:
        if type(other) is not TransferOutcome:
            return NotImplemented
        return self._values() == other._values()

    def __hash__(self) -> int:
        return hash(self._values())

    def __repr__(self) -> str:
        body = ", ".join(f"{name}={getattr(self, name)!r}" for name in _OUTCOME_FIELDS)
        return f"TransferOutcome({body})"


# --------------------------------------------------------------------------- seam helpers


def _attempt(op, *args):
    """Call one seam op; an ``OSError`` is returned as the second item, never raised or chained."""
    try:
        return op(*args), None
    except OSError as exc:
        return None, exc


def _close_quietly(fd: int) -> None:
    """Fatal-path close: nothing raised here may replace the exception that is propagating."""
    try:
        _fs._FS.close(fd)
    except BaseException:  # the original exception is re-raised by the caller
        pass


def _is_exdev(failure: OSError) -> bool:
    return failure.errno == _errno.EXDEV or getattr(failure, "winerror", None) == _ERROR_NOT_SAME_DEVICE


def _entry_exists(path: str) -> bool:
    """True iff ``lstat`` shows an entry (of any kind) at ``path``; an ``lstat`` error proves nothing."""
    probe = _fs.snapshot(path)
    return not isinstance(probe, OSError) or isinstance(probe, _fs.SnapshotRefused)


def _file_identity(st) -> EntryIdentity | None:
    """Identity of a regular, non-link file from a stat result (``fstat`` / ``lstat``), else ``None``."""
    if _fs.is_link(st) or not _fs.is_regular_file(st):
        return None
    return _fs._identity_of(st, EntryType.FILE)


def _remove_owned_temp(path: str) -> OSError | None:
    """The single unlink of the exact temporary THIS call created with ``O_EXCL`` (contract section 20)."""
    try:
        _fs._FS.unlink(path)
    except OSError as exc:
        return exc
    return None


def _left_behind(cleanup_failure: OSError | None) -> bool:
    """Whether the single cleanup attempt left the owned temporary behind. ``ENOENT`` means the exact path
    names nothing any more, so no leftover is recorded (a phantom leftover would block RESUME)."""
    return cleanup_failure is not None and not isinstance(cleanup_failure, FileNotFoundError)


def _same_volume_primitive(strategy: str, source: str, final: str) -> OSError | None:
    """Same-volume no-replace primitive: Windows ``rename`` (no replace flag) or POSIX ``link``."""
    try:
        if strategy == "rename":
            _fs._FS.rename(source, final)
        else:
            _fs._FS.link(source, final)
    except OSError as exc:
        return exc
    return None


def _publish_no_replace(strategy: str, temp: str, final: str) -> OSError | None:
    """Cross-volume publish of the owned temporary: Windows ``rename`` / POSIX ``link`` (never replaces)."""
    try:
        if strategy == "rename":
            _fs._FS.rename(temp, final)
        else:
            _fs._FS.link(temp, final)
    except OSError as exc:
        return exc
    return None


def _source_state(path: str, identity: EntryIdentity) -> ExecutionFailureKind | None:
    """Read-only source path revalidation: ``None`` iff ``path`` is still exactly the snapshotted file."""
    current = _fs.snapshot(path)
    if isinstance(current, _MISSING):
        return ExecutionFailureKind.SOURCE_MISSING
    if isinstance(current, OSError) or not same_identity(current, identity):
        return ExecutionFailureKind.SOURCE_CHANGED
    return None


def _unlink_verified_source(path: str, identity: EntryIdentity) -> ExecutionFailure | None:
    """Revalidate the source path, then unlink it (contract sections 18.3 / 19 steps 9-10).

    Only reached after the final media was completely published and verified. A changed / missing source
    is never unlinked (the entry now at that path is not ours).
    """
    kind = _source_state(path, identity)
    if kind is not None:
        return _failure(kind, TransferStage.SOURCE_PATH_REVALIDATE)
    try:
        _fs._FS.unlink(path)
    except OSError as exc:
        return _failure(ExecutionFailureKind.SOURCE_UNLINK_FAILED, TransferStage.SOURCE_UNLINK, exc)
    return None


def _fsync_directory(path: str) -> OSError | None:
    """POSIX: make the new final name durable before the old name is removed (contract section 18.3)."""
    fd, failure = _attempt(_fs._FS.open, path, _DIRECTORY_FLAGS)
    if failure is not None:
        return failure
    try:
        _, failure = _attempt(_fs._FS.fsync, fd)
    except BaseException:
        _close_quietly(fd)
        raise
    _, close_failure = _attempt(_fs._FS.close, fd)
    return failure if failure is not None else close_failure


def _failure(kind: ExecutionFailureKind, stage: TransferStage | None = None,
             cause: OSError | None = None, *, target_published: bool | None = None) -> ExecutionFailure:
    errno = None if cause is None else _fs.os_errno(cause)
    return ExecutionFailure(step=_STEP, kind=kind, stage=stage, errno=errno, target_published=target_published)


# --------------------------------------------------------------------------- entry point


class _Context:
    __slots__ = ("source", "target_directory", "final", "source_identity", "target_directory_identity",
                 "strategy")

    def __init__(self, plan: object, source_identity: EntryIdentity, target_directory_identity: EntryIdentity,
                 strategy: str) -> None:
        self.source = plan.source_path
        self.target_directory = plan.target_directory.absolute_path
        self.final = plan.target_media_path.absolute_path
        self.source_identity = source_identity
        self.target_directory_identity = target_directory_identity
        self.strategy = strategy


def transfer_media(plan: object, source_identity: EntryIdentity, target_directory_identity: EntryIdentity,
                   mode: TransferMode, *, resume_phase: ResumePhase) -> TransferOutcome:
    """Execute U2 ``MOVE_MEDIA`` (or only its source-removal tail). ``plan`` must already be validated.

    Returns a :class:`TransferOutcome`; never raises for an ``OSError``. ``BaseException`` / foreign
    exceptions propagate unchanged after closing descriptors and removing the owned temporary once.
    """
    if type(source_identity) is not EntryIdentity or source_identity.entry_type is not EntryType.FILE:
        raise ExecutionInputError("source_identity must be a FILE EntryIdentity")
    if (type(target_directory_identity) is not EntryIdentity
            or target_directory_identity.entry_type is not EntryType.DIRECTORY):
        raise ExecutionInputError("target_directory_identity must be a DIRECTORY EntryIdentity")
    if type(mode) is not TransferMode:
        raise ExecutionInputError("mode must be a TransferMode")
    if resume_phase is not ResumePhase.FULL and resume_phase is not ResumePhase.SOURCE_REMOVAL_ONLY:
        raise ExecutionInputError("resume_phase must be ResumePhase.FULL or ResumePhase.SOURCE_REMOVAL_ONLY")
    strategy = _SAME_VOLUME_STRATEGY
    if type(strategy) is not str or strategy not in _STRATEGIES:
        raise ExecutionInputError("the private same-volume strategy must be 'rename' or 'link'")
    ctx = _Context(plan, source_identity, target_directory_identity, strategy)

    if resume_phase is ResumePhase.SOURCE_REMOVAL_ONLY:
        failure = _remove_source_tail(ctx)
        effects = () if failure is not None else (_source_removed(ctx),)
        return TransferOutcome(effects, failure, mode, None, None, ())

    failure = _precheck(ctx)
    if failure is not None:
        return TransferOutcome((), failure, mode, None, None, ())
    if mode is TransferMode.SAME_VOLUME:
        return _same_volume(ctx)
    return _cross_volume(ctx)


def _precheck(ctx: _Context) -> ExecutionFailure | None:
    """Contract section 18.1 early exits: target directory identity, final absent, source identity.
    The no-overwrite guarantee comes from the primitives, not from these checks."""
    if not revalidate_directory(ctx.target_directory, ctx.target_directory_identity):
        return _failure(ExecutionFailureKind.TARGET_DIRECTORY_CHANGED)
    probe = _fs.snapshot(ctx.final)
    if isinstance(probe, NotADirectoryError):
        return _failure(ExecutionFailureKind.TARGET_DIRECTORY_CHANGED)
    if not isinstance(probe, FileNotFoundError):
        if isinstance(probe, OSError) and not isinstance(probe, _fs.SnapshotRefused):
            return _failure(ExecutionFailureKind.MEDIA_TRANSFER_FAILED, None, probe)
        return _failure(ExecutionFailureKind.TARGET_CONFLICT)  # any existing entry: never replaced
    kind = _source_state(ctx.source, ctx.source_identity)
    if kind is not None:
        return _failure(kind)
    return None


def _media_published(ctx: _Context, identity: EntryIdentity, sha256: str | None) -> CompletedEffect:
    return CompletedEffect(EffectKind.MEDIA_PUBLISHED, PathRole.TARGET_MEDIA, ctx.final, identity,
                           identity.size, sha256, None, None)


def _source_removed(ctx: _Context) -> CompletedEffect:
    return CompletedEffect(EffectKind.SOURCE_REMOVED, PathRole.SOURCE, ctx.source, None, None, None, None, None)


def _remove_source_tail(ctx: _Context) -> ExecutionFailure | None:
    """After a published final media: target directory revalidation, (POSIX) directory fsync, then the
    verified source unlink. Shared by the FULL flows and by ``SOURCE_REMOVAL_ONLY`` resume."""
    if not revalidate_directory(ctx.target_directory, ctx.target_directory_identity):
        return _failure(ExecutionFailureKind.TARGET_DIRECTORY_CHANGED)
    if _DIRECTORY_FSYNC:
        failure = _fsync_directory(ctx.target_directory)
        if failure is not None:
            return _failure(ExecutionFailureKind.TARGET_DIRECTORY_FSYNC_FAILED, TransferStage.DIRECTORY_FSYNC,
                            failure)
    return _unlink_verified_source(ctx.source, ctx.source_identity)


# --------------------------------------------------------------------------- same volume


def _same_volume(ctx: _Context) -> TransferOutcome:
    mode = TransferMode.SAME_VOLUME
    primitive_failure = _same_volume_primitive(ctx.strategy, ctx.source, ctx.final)
    if primitive_failure is not None:
        if _is_exdev(primitive_failure):
            return _cross_volume(ctx)  # the only fallback; nothing happened yet (contract section 17)
        if isinstance(primitive_failure, FileExistsError) or primitive_failure.errno == _errno.EEXIST:
            kind = ExecutionFailureKind.TARGET_CONFLICT
        elif ctx.strategy == "rename" and _entry_exists(ctx.final):
            kind = ExecutionFailureKind.TARGET_CONFLICT  # an entry now exists at the target (P4-C6 rule)
        else:
            kind = ExecutionFailureKind.MEDIA_TRANSFER_FAILED
        cause = primitive_failure if kind is ExecutionFailureKind.MEDIA_TRANSFER_FAILED else None
        return TransferOutcome((), _failure(kind, TransferStage.SAME_VOLUME_PRIMITIVE, cause), mode, None, None, ())

    published = _fs.snapshot(ctx.final)
    if isinstance(published, OSError) or not same_identity(published, ctx.source_identity):
        # Never rolled back and never recorded as an effect: the entry is not the verified source file.
        failure = _failure(ExecutionFailureKind.PUBLISHED_MEDIA_MISMATCH, TransferStage.PUBLISH_VERIFY)
        return TransferOutcome((), failure, mode, None, None, ())
    media = _media_published(ctx, published, None)

    if ctx.strategy == "rename":
        # One atomic rename moved the entry: the final is published AND the source name is gone.
        return TransferOutcome((media, _source_removed(ctx)), None, mode, None, published.size, ())

    failure = _remove_source_tail(ctx)
    if failure is not None:
        return TransferOutcome((media,), failure, mode, None, published.size, ())
    return TransferOutcome((media, _source_removed(ctx)), None, mode, None, published.size, ())


# --------------------------------------------------------------------------- cross volume


class _CopyState:
    """Resources this call holds: open descriptors and the exact owned temporary (``None`` once released)."""

    __slots__ = ("source_fd", "temp_fd", "temp_path", "temp_name")

    def __init__(self) -> None:
        self.source_fd: int | None = None
        self.temp_fd: int | None = None
        self.temp_path: str | None = None
        self.temp_name: str | None = None

    def take_source_fd(self) -> int | None:
        fd, self.source_fd = self.source_fd, None
        return fd

    def take_temp_fd(self) -> int | None:
        fd, self.temp_fd = self.temp_fd, None
        return fd

    def take_temp(self) -> tuple[str | None, str | None]:
        """End temp ownership: after this, the path is never touched again by this call."""
        path, name = self.temp_path, self.temp_name
        self.temp_path = self.temp_name = None
        return path, name


def _cross_volume(ctx: _Context) -> TransferOutcome:
    state = _CopyState()
    try:
        return _cross_volume_steps(ctx, state)
    except BaseException:
        _abandon(state)
        raise


def _abandon(state: _CopyState) -> None:
    """Fatal path (contract section 29): close open descriptors, unlink the owned temporary once, and let
    nothing raised here replace the propagating exception."""
    for fd in (state.take_temp_fd(), state.take_source_fd()):
        if fd is not None:
            _close_quietly(fd)
    path, _ = state.take_temp()
    if path is not None:
        try:
            _remove_owned_temp(path)
        except BaseException:  # the original exception is re-raised by the caller
            pass


def _stop_before_publish(state: _CopyState, failure: ExecutionFailure) -> TransferOutcome:
    """Typed failure in steps 1-7 before a publish: close descriptors, clean the exact owned temporary once.
    A failed cleanup keeps the primary failure and records the leftover name."""
    for fd in (state.take_temp_fd(), state.take_source_fd()):
        if fd is not None:
            _attempt(_fs._FS.close, fd)
    leftovers = ()
    path, name = state.take_temp()
    if path is not None and _left_behind(_remove_owned_temp(path)):
        leftovers = (LeftoverTemporary(PathRole.TARGET_DIRECTORY, name),)
    return TransferOutcome((), failure, TransferMode.CROSS_VOLUME, None, None, leftovers)


def _new_temp_name() -> str | None:
    token = _fs.new_token()
    if type(token) is not str or len(token) != 32 or not set(token) <= _HEX_DIGITS:
        return None
    return _TEMP_PREFIX + token + _TEMP_SUFFIX


def _create_owned_temp(ctx: _Context, state: _CopyState) -> ExecutionFailure | None:
    """Step 2: exclusive sibling temporary; a name collision draws a new token, at most 8 names."""
    for _ in range(_MAX_TEMP_ATTEMPTS):
        name = _new_temp_name()
        if name is None:
            return ExecutionFailure(step=_STEP, kind=ExecutionFailureKind.MEDIA_TEMP_CREATE_FAILED,
                                    stage=TransferStage.TEMP_CREATE, errno=_errno.EINVAL)
        path = os.path.join(ctx.target_directory, name)
        fd, failure = _attempt(_fs._FS.open, path, _TEMP_FLAGS, _TEMP_MODE)
        if failure is None:
            state.temp_fd, state.temp_path, state.temp_name = fd, path, name
            return None
        if not isinstance(failure, FileExistsError):
            return _failure(ExecutionFailureKind.MEDIA_TEMP_CREATE_FAILED, TransferStage.TEMP_CREATE, failure)
    return ExecutionFailure(step=_STEP, kind=ExecutionFailureKind.MEDIA_TEMP_CREATE_FAILED,
                            stage=TransferStage.TEMP_CREATE, errno=_errno.EEXIST)


def _write_all(fd: int, chunk: bytes) -> ExecutionFailure | None:
    """Write one block completely: short writes continue with the remainder; a zero write is ``EIO``."""
    view = memoryview(chunk)
    while view:
        written, failure = _attempt(_fs._FS.write, fd, view)
        if failure is not None:
            return _failure(ExecutionFailureKind.MEDIA_WRITE_FAILED, TransferStage.WRITE, failure)
        if type(written) is not int or written <= 0 or written > len(view):
            return ExecutionFailure(step=_STEP, kind=ExecutionFailureKind.MEDIA_WRITE_FAILED,
                                    stage=TransferStage.WRITE, errno=_errno.EIO)
        view = view[written:]
    return None


def _copy_stream(state: _CopyState, expected_size: int) -> tuple[str | None, ExecutionFailure | None]:
    """Steps 3-4: stream <= 1 MiB blocks, hashing exactly the bytes written; abort as soon as more than the
    snapshot size was read; at EOF the total must equal the snapshot size."""
    digest = hashlib.sha256()
    total = 0
    while True:
        chunk, failure = _attempt(_fs._FS.read, state.source_fd, _CHUNK)
        if failure is not None:
            return None, _failure(ExecutionFailureKind.MEDIA_READ_FAILED, TransferStage.READ, failure)
        if type(chunk) is not bytes or len(chunk) > _CHUNK:
            return None, ExecutionFailure(step=_STEP, kind=ExecutionFailureKind.MEDIA_READ_FAILED,
                                          stage=TransferStage.READ, errno=_errno.EIO)
        if not chunk:
            break
        total += len(chunk)
        if total > expected_size:
            return None, _failure(ExecutionFailureKind.SOURCE_CHANGED_DURING_COPY, TransferStage.READ)
        digest.update(chunk)
        failure = _write_all(state.temp_fd, chunk)
        if failure is not None:
            return None, failure
    if total != expected_size:
        return None, _failure(ExecutionFailureKind.SOURCE_CHANGED_DURING_COPY, TransferStage.READ)
    return digest.hexdigest(), None


def _finish_temp(state: _CopyState, expected_size: int) -> tuple[int | None, ExecutionFailure | None]:
    """Step 5: fsync, fstat (record the inode) and close the temporary."""
    _, failure = _attempt(_fs._FS.fsync, state.temp_fd)
    if failure is not None:
        return None, _failure(ExecutionFailureKind.MEDIA_FSYNC_FAILED, TransferStage.FSYNC, failure)
    st, failure = _attempt(_fs._FS.fstat, state.temp_fd)
    if failure is not None:
        return None, _failure(ExecutionFailureKind.MEDIA_FSYNC_FAILED, TransferStage.FSYNC, failure)
    identity = _file_identity(st)
    if identity is None or identity.size != expected_size:
        return None, ExecutionFailure(step=_STEP, kind=ExecutionFailureKind.MEDIA_WRITE_FAILED,
                                      stage=TransferStage.FSYNC, errno=_errno.EIO)
    _, failure = _attempt(_fs._FS.close, state.take_temp_fd())
    if failure is not None:
        return None, _failure(ExecutionFailureKind.MEDIA_CLOSE_FAILED, TransferStage.CLOSE, failure)
    return identity.inode, None


def _cross_volume_steps(ctx: _Context, state: _CopyState) -> TransferOutcome:
    expected = ctx.source_identity

    # 1. read-only source fd, validated by fstat against the snapshot.
    fd, failure = _attempt(_fs._FS.open, ctx.source, _fs._READ_ONLY_FLAGS)
    if failure is not None:
        return _stop_before_publish(state, _failure(ExecutionFailureKind.MEDIA_SOURCE_OPEN_FAILED,
                                                    TransferStage.SOURCE_OPEN, failure))
    state.source_fd = fd
    st, failure = _attempt(_fs._FS.fstat, fd)
    if failure is not None:
        return _stop_before_publish(state, _failure(ExecutionFailureKind.MEDIA_SOURCE_OPEN_FAILED,
                                                    TransferStage.SOURCE_FD_VALIDATE, failure))
    if not same_identity(_file_identity(st), expected):
        return _stop_before_publish(state, _failure(ExecutionFailureKind.SOURCE_CHANGED,
                                                    TransferStage.SOURCE_FD_VALIDATE))

    # 2. exclusive sibling temporary inside the revalidated target directory.
    if not revalidate_directory(ctx.target_directory, ctx.target_directory_identity):
        return _stop_before_publish(state, _failure(ExecutionFailureKind.TARGET_DIRECTORY_CHANGED,
                                                    TransferStage.TEMP_CREATE))
    failure = _create_owned_temp(ctx, state)
    if failure is not None:
        return _stop_before_publish(state, failure)

    # 3-4. streamed copy + SHA-256; 5. fsync / fstat / close of the temporary.
    media_sha256, failure = _copy_stream(state, expected.size)
    if failure is not None:
        return _stop_before_publish(state, failure)
    temp_inode, failure = _finish_temp(state, expected.size)
    if failure is not None:
        return _stop_before_publish(state, failure)

    # 6. the source fd still describes the snapshotted file (append / truncate / mtime / inode).
    st, failure = _attempt(_fs._FS.fstat, state.source_fd)
    if failure is not None:
        return _stop_before_publish(state, _failure(ExecutionFailureKind.MEDIA_READ_FAILED,
                                                    TransferStage.SOURCE_FD_REVALIDATE, failure))
    if not same_identity(_file_identity(st), expected):
        return _stop_before_publish(state, _failure(ExecutionFailureKind.SOURCE_CHANGED_DURING_COPY,
                                                    TransferStage.SOURCE_FD_REVALIDATE))
    _, failure = _attempt(_fs._FS.close, state.take_source_fd())
    if failure is not None:
        return _stop_before_publish(state, _failure(ExecutionFailureKind.MEDIA_CLOSE_FAILED,
                                                    TransferStage.CLOSE, failure))

    # 7. no-replace publish of the owned temporary.
    if not revalidate_directory(ctx.target_directory, ctx.target_directory_identity):
        return _stop_before_publish(state, _failure(ExecutionFailureKind.TARGET_DIRECTORY_CHANGED,
                                                    TransferStage.PUBLISH))
    failure = _publish_no_replace(ctx.strategy, state.temp_path, ctx.final)
    if failure is not None:
        conflict = isinstance(failure, FileExistsError) or failure.errno == _errno.EEXIST or (
            ctx.strategy == "rename" and _entry_exists(ctx.final))
        if conflict:
            return _stop_before_publish(state, _failure(ExecutionFailureKind.TARGET_CONFLICT, TransferStage.PUBLISH))
        return _stop_before_publish(state, _failure(ExecutionFailureKind.MEDIA_PUBLISH_FAILED,
                                                    TransferStage.PUBLISH, failure))
    leftovers: tuple[LeftoverTemporary, ...] = ()
    temp_path, temp_name = state.take_temp()  # ownership ends: consumed by rename, or unlinked once below
    cleanup_failure = None
    if ctx.strategy == "link":
        cleanup_failure = _remove_owned_temp(temp_path)
        if not _left_behind(cleanup_failure):
            cleanup_failure = None
        else:
            leftovers = (LeftoverTemporary(PathRole.TARGET_DIRECTORY, temp_name),)

    published = _fs.snapshot(ctx.final)
    if (isinstance(published, OSError) or published.entry_type is not EntryType.FILE
            or published.size != expected.size or published.inode != temp_inode):
        failure = _failure(ExecutionFailureKind.PUBLISHED_MEDIA_MISMATCH, TransferStage.PUBLISH_VERIFY)
        return TransferOutcome((), failure, TransferMode.CROSS_VOLUME, None, None, leftovers)
    media = _media_published(ctx, published, media_sha256)
    if cleanup_failure is not None:
        failure = _failure(ExecutionFailureKind.MEDIA_TEMP_CLEANUP_FAILED, TransferStage.TEMP_CLEANUP,
                           cleanup_failure, target_published=True)
        return TransferOutcome((media,), failure, TransferMode.CROSS_VOLUME, media_sha256, published.size,
                               leftovers)

    # 8. POSIX directory fsync; 9. source path revalidation; 10. unlink of the verified source.
    failure = _remove_source_tail(ctx)
    if failure is not None:
        return TransferOutcome((media,), failure, TransferMode.CROSS_VOLUME, media_sha256, published.size, ())
    return TransferOutcome((media, _source_removed(ctx)), None, TransferMode.CROSS_VOLUME, media_sha256,
                           published.size, ())
