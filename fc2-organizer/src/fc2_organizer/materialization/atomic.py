"""Atomic, never-overwriting creation of one artifact file (P4-C6 substep 1).

``materialize_atomic_bytes(target_path, content)`` writes exact ``bytes`` to a
new file at ``target_path`` inside an **already existing** directory:

1. validate inputs (exact types, explicit fully-qualified path) -- no I/O yet;
2. require the parent to be an existing directory (never created here);
3. fail fast if anything already occupies the target (``lstat``: file,
   directory, symlink, dangling symlink, junction);
4. exclusively create (``O_CREAT | O_EXCL``) a randomly named temporary sibling
   in the same directory -- this call owns exactly that path;
5. write every byte, ``fsync``, close;
6. publish with a primitive that **cannot replace** an existing entry:
   Windows ``os.rename`` (``MoveFileExW`` without ``MOVEFILE_REPLACE_EXISTING``),
   POSIX ``os.link`` (``EEXIST`` if the name exists; never follows it) followed
   by unlinking the temporary name;
7. on any failure, close the handle and remove only the owned temporary path.

Step 3 is only an early exit; the no-overwrite guarantee comes from step 6
itself, so a target created between 3 and 6 is never replaced. ``os.replace``
is never used. No directory is created, nothing is globbed or listed, and no
path other than the owned temporary path is ever removed.
"""

from __future__ import annotations

import errno as _errno
import hashlib
import ntpath
import os
import posixpath
import secrets
import stat as _stat
from dataclasses import dataclass
from typing import Callable

from fc2_organizer.materialization.errors import (
    ArtifactCleanupError,
    ArtifactPublishError,
    ArtifactWriteError,
    ArtifactWriteStage,
    InvalidTargetPathError,
    MaterializationError,
    MaterializationInputError,
    ParentDirectoryError,
    ParentDirectoryMissingError,
    ParentNotDirectoryError,
    ParentRejectionReason,
    TargetExistsError,
    TargetInaccessibleError,
    TargetPathRejectionReason,
    TemporaryCreateError,
)
from fc2_organizer.materialization.models import MaterializedArtifact

__all__ = ["materialize_atomic_bytes"]

_IS_WINDOWS = os.name == "nt"

# Temporary sibling name: fixed prefix/suffix + secure random token. Never derived
# from the target name, metadata, title or URL.
_TEMP_PREFIX = ".fc2tmp-"
_TEMP_SUFFIX = ".part"
_TEMP_TOKEN_BYTES = 16
_MAX_TEMP_ATTEMPTS = 8
_TEMP_FLAGS = (
    os.O_WRONLY | os.O_CREAT | os.O_EXCL
    | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOINHERIT", 0) | getattr(os, "O_CLOEXEC", 0)
)
_TEMP_MODE = 0o666  # the process umask applies; the published file keeps these bits
_WRITE_CHUNK = 1 << 20

_WINDOWS_ILLEGAL = frozenset('<>:"|?*')
_WINDOWS_RESERVED = frozenset(
    {"CON", "PRN", "AUX", "NUL"} | {f"COM{i}" for i in range(1, 10)} | {f"LPT{i}" for i in range(1, 10)}
)


def _publish_no_replace(temp_path: str, target_path: str) -> None:
    if _IS_WINDOWS:
        # MoveFileExW without MOVEFILE_REPLACE_EXISTING: FileExistsError if any entry
        # (file, directory, symlink, junction) exists at target_path; atomic on one volume.
        os.rename(temp_path, target_path)
    else:
        # link(2) never replaces and never follows an existing target_path (EEXIST).
        os.link(temp_path, target_path)


# True when a successful publish leaves the temporary name behind (POSIX hard link).
_PUBLISH_LEAVES_TEMP = not _IS_WINDOWS


@dataclass(frozen=True, slots=True)
class _FsOps:
    """Private seam for failure injection in tests. Never part of the public API."""

    lstat: Callable[[str], os.stat_result]
    stat: Callable[[str], os.stat_result]
    open: Callable[[str, int, int], int]
    write: Callable[[int, memoryview], int]
    fsync: Callable[[int], None]
    close: Callable[[int], None]
    publish: Callable[[str, str], None]
    unlink: Callable[[str], None]
    token: Callable[[int], str]


_FS = _FsOps(
    lstat=os.lstat,
    stat=os.stat,
    open=os.open,
    write=os.write,
    fsync=os.fsync,
    close=os.close,
    publish=_publish_no_replace,
    unlink=os.unlink,
    token=secrets.token_hex,
)


def materialize_atomic_bytes(target_path: str, content: bytes) -> MaterializedArtifact:
    """Atomically create ``target_path`` holding exactly ``content``; never overwrite.

    ``target_path`` must be an exact ``str`` naming a file inside an existing
    directory; ``content`` must be exact ``bytes``. Raises a
    :class:`~fc2_organizer.materialization.errors.MaterializationError` subclass
    on every failure; on failure the final target is never created, modified or
    removed, and only this call's own temporary file is cleaned up.
    """
    if type(target_path) is not str:
        raise MaterializationInputError("target_path must be an exact str")
    if type(content) is not bytes:
        raise MaterializationInputError("content must be exact bytes")
    parent = _validate_target_path(target_path, windows=_IS_WINDOWS)
    size_bytes = len(content)
    sha256 = hashlib.sha256(content).hexdigest()

    fs = _FS
    _require_parent_directory(fs, parent)
    _require_target_absent(fs, target_path)
    temp_path, fd = _create_owned_temp(fs, parent, target_path)
    _fill_and_publish(fs, fd, temp_path, target_path, content)
    return MaterializedArtifact(target_path=target_path, size_bytes=size_bytes, sha256=sha256)


# --------------------------------------------------------------------------- path validation


def _validate_target_path(path: str, *, windows: bool) -> str:
    """Lexically validate an explicit target file path; return its parent. No I/O."""
    if not path:
        raise InvalidTargetPathError(TargetPathRejectionReason.EMPTY)
    if "\x00" in path:
        raise InvalidTargetPathError(TargetPathRejectionReason.NUL_CHARACTER)
    flavor = ntpath if windows else posixpath
    if windows:
        if path.startswith(("\\\\?\\", "\\\\.\\", "//?/", "//./")):
            raise InvalidTargetPathError(TargetPathRejectionReason.DEVICE_NAMESPACE)
        drive, rest = ntpath.splitdrive(path)
        is_drive_letter = len(drive) == 2 and drive[1] == ":"
        is_unc = drive[:2] in ("\\\\", "//") and len(drive) > 2
        if not (is_drive_letter or is_unc) or rest[:1] not in ("\\", "/"):
            raise InvalidTargetPathError(TargetPathRejectionReason.NOT_ABSOLUTE)
        components = [c for part in rest.split("\\") for c in part.split("/")]
    else:
        if not posixpath.isabs(path):
            raise InvalidTargetPathError(TargetPathRejectionReason.NOT_ABSOLUTE)
        components = path.split("/")
    if components[-1] == "":
        raise InvalidTargetPathError(TargetPathRejectionReason.NO_BASENAME)
    for component in components:
        if component in (".", ".."):
            raise InvalidTargetPathError(TargetPathRejectionReason.DOT_SEGMENT)
        if windows and component:
            _validate_windows_component(component)
    return flavor.dirname(path)


def _validate_windows_component(component: str) -> None:
    if any(ch in _WINDOWS_ILLEGAL or ord(ch) < 32 for ch in component):
        # ':' here would name an NTFS alternate data stream of another file.
        raise InvalidTargetPathError(TargetPathRejectionReason.ILLEGAL_CHARACTER)
    if component[-1] in (".", " "):
        raise InvalidTargetPathError(TargetPathRejectionReason.TRAILING_DOT_OR_SPACE)
    if component.split(".", 1)[0].upper() in _WINDOWS_RESERVED:
        raise InvalidTargetPathError(TargetPathRejectionReason.RESERVED_NAME)


# --------------------------------------------------------------------------- preconditions


def _os_error_of(fn: Callable[..., object], *args: object) -> OSError | None:
    """Run one filesystem op; return its ``OSError`` instead of raising it.

    Typed errors are then raised *outside* any ``except`` block, so no ``OSError``
    (whose ``filename`` names the temporary path) is ever attached as context.
    """
    try:
        fn(*args)
    except OSError as exc:
        return exc
    return None


def _require_parent_directory(fs: _FsOps, parent: str) -> None:
    result: list[os.stat_result] = []
    failure = _os_error_of(lambda: result.append(fs.stat(parent)))
    if failure is not None:
        if isinstance(failure, FileNotFoundError | NotADirectoryError):
            raise ParentDirectoryMissingError(failure.errno)
        raise ParentDirectoryError(ParentRejectionReason.INACCESSIBLE, failure.errno)
    if not _stat.S_ISDIR(result[0].st_mode):
        raise ParentNotDirectoryError()


def _require_target_absent(fs: _FsOps, target_path: str) -> None:
    # lstat: an existing symlink / junction counts as existing and is never followed.
    failure = _os_error_of(fs.lstat, target_path)
    if failure is None:
        raise TargetExistsError()
    if not isinstance(failure, FileNotFoundError):
        raise TargetInaccessibleError(failure.errno)


def _same_entry_name(a: str, b: str) -> bool:
    return a.casefold() == b.casefold() if _IS_WINDOWS else a == b


def _create_owned_temp(fs: _FsOps, parent: str, target_path: str) -> tuple[str, int]:
    """Exclusively create a fresh temporary sibling. Returns (owned path, fd)."""
    last_errno: int | None = None
    flavor = ntpath if _IS_WINDOWS else posixpath
    for _ in range(_MAX_TEMP_ATTEMPTS):
        temp_path = flavor.join(parent, f"{_TEMP_PREFIX}{fs.token(_TEMP_TOKEN_BYTES)}{_TEMP_SUFFIX}")
        if _same_entry_name(temp_path, target_path):
            continue
        fd_box: list[int] = []
        failure = _os_error_of(lambda: fd_box.append(fs.open(temp_path, _TEMP_FLAGS, _TEMP_MODE)))
        if failure is None:
            return temp_path, fd_box[0]
        last_errno = failure.errno
        if not isinstance(failure, FileExistsError):
            break  # not a name clash: retrying with another name cannot help
    raise TemporaryCreateError(last_errno)


# --------------------------------------------------------------------------- write + publish


def _write_all(fs: _FsOps, fd: int, content: bytes) -> OSError | None:
    view = memoryview(content)
    offset = 0
    total = len(view)
    while offset < total:
        written: list[int] = []
        failure = _os_error_of(lambda: written.append(fs.write(fd, view[offset:offset + _WRITE_CHUNK])))
        if failure is not None:
            return failure
        if type(written[0]) is not int or written[0] <= 0:
            return OSError(_errno.EIO, "short write")
        offset += written[0]
    return None


def _remove_owned_temp(fs: _FsOps, temp_path: str) -> OSError | None:
    failure = _os_error_of(fs.unlink, temp_path)
    return None if isinstance(failure, FileNotFoundError) else failure


def _publish_failure(fs: _FsOps, failure: OSError, target_path: str) -> MaterializationError:
    if isinstance(failure, FileExistsError) or failure.errno == _errno.EEXIST:
        return TargetExistsError()
    # e.g. Windows reports "access denied" when the occupant is a directory: classify
    # by what is there now. This probe decides only the error type, never an action.
    if _os_error_of(fs.lstat, target_path) is None:
        return TargetExistsError()
    return ArtifactPublishError(failure.errno)


def _fill_and_publish(fs: _FsOps, fd: int, temp_path: str, target_path: str, content: bytes) -> None:
    fd_open = True
    temp_owned = True  # this call created temp_path and it has not been consumed / removed
    published = False
    try:
        failure = _write_all(fs, fd, content)
        if failure is not None:
            raise ArtifactWriteError(ArtifactWriteStage.WRITE, failure.errno)
        failure = _os_error_of(fs.fsync, fd)
        if failure is not None:
            raise ArtifactWriteError(ArtifactWriteStage.FLUSH, failure.errno)
        fd_open = False  # a failed close still invalidates the descriptor
        failure = _os_error_of(fs.close, fd)
        if failure is not None:
            raise ArtifactWriteError(ArtifactWriteStage.CLOSE, failure.errno)
        failure = _os_error_of(fs.publish, temp_path, target_path)
        if failure is not None:
            raise _publish_failure(fs, failure, target_path)
        published = True
        if _PUBLISH_LEAVES_TEMP:
            failure = _remove_owned_temp(fs, temp_path)
            temp_owned = False  # attempted exactly once; never retried against a reused name
            if failure is not None:
                raise ArtifactCleanupError(target_published=True, primary=None, errno=failure.errno)
        else:
            temp_owned = False  # the rename consumed the temporary name
    except BaseException as primary:
        if fd_open:
            _os_error_of(fs.close, fd)
        if temp_owned:
            cleanup_failure = _remove_owned_temp(fs, temp_path)
            if cleanup_failure is not None and isinstance(primary, MaterializationError):
                raise ArtifactCleanupError(
                    target_published=published, primary=primary, errno=cleanup_failure.errno
                ) from primary
            # Any other primary (KeyboardInterrupt, SystemExit, GeneratorExit, cancellation,
            # a foreign exception) propagates unchanged; a cleanup failure never masks it.
        raise
