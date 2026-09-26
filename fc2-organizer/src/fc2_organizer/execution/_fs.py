"""Private filesystem seam of ``fc2_organizer.execution`` (P4-C7). Never public API.

Every syscall the execution package makes goes through the module-level ``_FS``
(a frozen ``_FsOps``) so tests can inject failures at exact points; no other module
of the package calls ``os.<syscall>`` directly (architecture test). Callers must
reference ``_fs._FS`` at call time (never capture it), so a patched seam is honoured.

S1 uses only the read-only part (``lstat``, ``device_of``, ``token``) through the
frozen ``snapshot(path)`` interface. The mutating
entries (``mkdir``, ``rename``, ``link``, ``unlink``, ``write``, ...) are defined
for S2-S5 and are not reached by any S1 code path (zero-mutation tests trap them).

OS failures are *returned* as ``OSError`` values rather than raised, so the caller
raises its typed error outside any ``except`` block (no ``OSError`` is ever chained).
"""

from __future__ import annotations

import errno as _errno
import os
import secrets
import stat as _stat
from dataclasses import dataclass
from typing import Callable

from fc2_organizer.execution.models import EntryIdentity, EntryType

__all__ = [
    "snapshot", "SnapshotRefused", "REFUSED_LINK", "REFUSED_SPECIAL", "REFUSED_IDENTITY_UNAVAILABLE",
    "is_link", "is_directory", "is_regular_file", "list_names", "new_token", "os_errno",
]


def _device_of(st: os.stat_result) -> int:
    return st.st_dev


@dataclass(frozen=True, slots=True)
class _FsOps:
    """Private seam for failure injection in tests."""

    lstat: Callable[[str], os.stat_result]
    fstat: Callable[[int], os.stat_result]
    open: Callable[..., int]
    read: Callable[[int, int], bytes]
    write: Callable[[int, memoryview], int]
    fsync: Callable[[int], None]
    close: Callable[[int], None]
    mkdir: Callable[..., None]
    rename: Callable[[str, str], None]
    link: Callable[[str, str], None]
    unlink: Callable[[str], None]
    listdir: Callable[[str], list[str]]
    token: Callable[[int], str]
    device_of: Callable[[os.stat_result], int]


_FS = _FsOps(
    lstat=os.lstat,
    fstat=os.fstat,
    open=os.open,
    read=os.read,
    write=os.write,
    fsync=os.fsync,
    close=os.close,
    mkdir=os.mkdir,
    rename=os.rename,
    link=os.link,
    unlink=os.unlink,
    listdir=os.listdir,
    token=secrets.token_hex,
    device_of=_device_of,
)


def _lstat_entry(path: str) -> os.stat_result | OSError:
    """``lstat`` (never follows a link); the ``OSError`` is returned, not raised."""
    box: list[os.stat_result] = []
    try:
        box.append(_FS.lstat(path))
    except OSError as exc:
        return exc
    return box[0]


def is_link(st: os.stat_result) -> bool:
    """A POSIX symlink, or any Windows reparse point (junction, symlink, other tags)."""
    if _stat.S_ISLNK(st.st_mode):
        return True
    attributes = getattr(st, "st_file_attributes", None)
    return type(attributes) is int and bool(attributes & _stat.FILE_ATTRIBUTE_REPARSE_POINT)


def is_directory(st: os.stat_result) -> bool:
    return _stat.S_ISDIR(st.st_mode)


def is_regular_file(st: os.stat_result) -> bool:
    return _stat.S_ISREG(st.st_mode)


def _identity_of(st: os.stat_result, entry_type: EntryType) -> EntryIdentity | None:
    """The ``EntryIdentity`` of a non-link entry, or ``None`` if the OS reports no usable
    identity (``st_ino == 0``: contract sections 10-11, ``IDENTITY_UNAVAILABLE``)."""
    inode = st.st_ino
    device = _FS.device_of(st)
    if type(inode) is not int or inode <= 0 or type(device) is not int or device < 0:
        return None
    if entry_type is EntryType.FILE:
        return EntryIdentity(device, inode, EntryType.FILE, st.st_size, st.st_mtime_ns)
    return EntryIdentity(device, inode, EntryType.DIRECTORY, None, None)


# Why ``snapshot`` refused an *existing* entry (SnapshotRefused.reason).
REFUSED_LINK = "link"                                   # symlink / junction / any reparse point
REFUSED_SPECIAL = "special"                             # neither a regular file nor a directory
REFUSED_IDENTITY_UNAVAILABLE = "identity_unavailable"   # st_ino == 0 (contract sections 10-11)

_REFUSAL_ERRNO = {REFUSED_LINK: _errno.ELOOP, REFUSED_SPECIAL: _errno.EINVAL,
                  REFUSED_IDENTITY_UNAVAILABLE: _errno.EINVAL}


class SnapshotRefused(OSError):
    """``snapshot`` found an entry that yields no ownable identity. Returned, never raised.

    A link (like ``O_NOFOLLOW``: ``ELOOP``) is never snapshotted as a file or directory.
    ``entry_type`` / ``size`` are only set for ``REFUSED_IDENTITY_UNAVAILABLE`` (a regular file or a
    directory whose identity the OS cannot report), so callers keep their classification order.
    """

    def __init__(self, reason: str, *, entry_type: EntryType | None = None, size: int | None = None) -> None:
        super().__init__(_REFUSAL_ERRNO[reason], "entry yields no usable identity")
        self.reason = reason
        self.entry_type = entry_type
        self.size = size


def snapshot(path: str) -> EntryIdentity | OSError:
    """Frozen S1 interface (construction plan S1 item 6): one ``lstat`` snapshot, never following links.

    * regular file / directory with a usable identity -> its ``EntryIdentity``;
    * missing / inaccessible -> the ``OSError`` itself (returned, not raised);
    * link / reparse point, special file, or ``st_ino == 0`` -> a :class:`SnapshotRefused` value.
    """
    st = _lstat_entry(path)
    if isinstance(st, OSError):
        return st
    if is_link(st):
        return SnapshotRefused(REFUSED_LINK)
    if is_regular_file(st):
        entry_type = EntryType.FILE
    elif is_directory(st):
        entry_type = EntryType.DIRECTORY
    else:
        return SnapshotRefused(REFUSED_SPECIAL)
    identity = _identity_of(st, entry_type)
    if identity is None:
        size = st.st_size if entry_type is EntryType.FILE else None
        return SnapshotRefused(REFUSED_IDENTITY_UNAVAILABLE, entry_type=entry_type, size=size)
    return identity


def list_names(directory: str) -> list[str] | OSError:
    """Names of the entries directly inside ``directory`` (sorted); the ``OSError`` is returned."""
    box: list[list[str]] = []
    try:
        box.append(sorted(_FS.listdir(directory)))
    except OSError as exc:
        return exc
    return box[0]


def new_token() -> str:
    """32 lowercase hex characters from the seam's secure token source."""
    return _FS.token(16)


def os_errno(failure: OSError) -> int | None:
    value = failure.errno
    return value if type(value) is int else None
