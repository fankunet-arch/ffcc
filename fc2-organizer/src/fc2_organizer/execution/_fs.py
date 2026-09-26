"""Private filesystem seam of ``fc2_organizer.execution`` (P4-C7). Never public API.

Every syscall the execution package makes goes through the module-level ``_FS``
(a frozen ``_FsOps``) so tests can inject failures at exact points; no other module
of the package calls ``os.<syscall>`` directly (architecture test). Callers must
reference ``_fs._FS`` at call time (never capture it), so a patched seam is honoured.

S1 uses only the read-only part (``lstat``, ``device_of``, ``token``). The mutating
entries (``mkdir``, ``rename``, ``link``, ``unlink``, ``write``, ...) are defined
for S2-S5 and are not reached by any S1 code path (zero-mutation tests trap them).

OS failures are *returned* as ``OSError`` values rather than raised, so the caller
raises its typed error outside any ``except`` block (no ``OSError`` is ever chained).
"""

from __future__ import annotations

import os
import secrets
import stat as _stat
from dataclasses import dataclass
from typing import Callable

from fc2_organizer.execution.models import EntryIdentity, EntryType

__all__ = [
    "lstat_entry", "is_link", "is_directory", "is_regular_file", "identity_of", "list_names", "new_token",
    "os_errno",
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


def lstat_entry(path: str) -> os.stat_result | OSError:
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


def identity_of(st: os.stat_result, entry_type: EntryType) -> EntryIdentity | None:
    """The ``EntryIdentity`` of a non-link entry, or ``None`` if the OS reports no usable
    identity (``st_ino == 0``: contract sections 10-11, ``IDENTITY_UNAVAILABLE``)."""
    inode = st.st_ino
    device = _FS.device_of(st)
    if type(inode) is not int or inode <= 0 or type(device) is not int or device < 0:
        return None
    if entry_type is EntryType.FILE:
        return EntryIdentity(device, inode, EntryType.FILE, st.st_size, st.st_mtime_ns)
    return EntryIdentity(device, inode, EntryType.DIRECTORY, None, None)


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
