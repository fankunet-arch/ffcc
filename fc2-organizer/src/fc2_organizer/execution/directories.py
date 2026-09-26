"""Exclusive directory ownership for ``fc2_organizer.execution`` (P4-C7 S2; contract sections 21-22).

* :func:`create_target_directory` -- revalidate the library root, require the target directory to be
  absent, create it with ONE exclusive ``mkdir`` (never ``makedirs`` / ``parents`` / ``exist_ok``), then
  snapshot it.
* :func:`create_extrafanart_directory` -- the same for ``extrafanart/`` below a revalidated target directory.
* :func:`revalidate_directory` -- snapshot-based directory identity check (device, inode, type).
* :func:`child_name` / :func:`compare_inventory` -- lexical child names and the exact directory inventory
  used by RESUME preflight (contract section 14.3).

Returned values, never raised: ``(EntryIdentity, None)`` on success, ``(None, ExecutionFailure)`` otherwise.
A failure with ``stage is TransferStage.PUBLISH_VERIFY`` means the exclusive ``mkdir`` itself SUCCEEDED
(the directory now exists: a final effect happened) but its post-``mkdir`` snapshot is not a real, owned
directory; every other failure means nothing was created. Nothing here ever deletes, renames or adopts an
existing entry: ownership grants no removal right (contract section 21).

``mkdir`` is reached only through :func:`_mkdir_exclusive` (architecture test). Standard library ``os``
(lexical ``os.path`` / ``os.name`` only) and this package.
"""

from __future__ import annotations

import os

from fc2_organizer.execution import _fs
from fc2_organizer.execution.errors import ExecutionInputError
from fc2_organizer.execution.models import (
    EntryIdentity,
    EntryType,
    ExecutionFailure,
    ExecutionFailureKind,
    ExecutionStep,
    TransferStage,
    same_identity,
)

__all__ = [
    "create_target_directory",
    "create_extrafanart_directory",
    "revalidate_directory",
    "child_name",
    "compare_inventory",
]

_DIRECTORY_MODE = 0o777  # the process umask applies

_MISSING = (FileNotFoundError, NotADirectoryError)


def _mkdir_exclusive(path: str) -> OSError | None:
    """The single exclusive ``mkdir`` of the package; the ``OSError`` is returned, not raised."""
    try:
        _fs._FS.mkdir(path, _DIRECTORY_MODE)
    except OSError as exc:
        return exc
    return None


def _require_directory_identity(value: object, name: str) -> None:
    if type(value) is not EntryIdentity or value.entry_type is not EntryType.DIRECTORY:
        raise ExecutionInputError(f"{name} must be a DIRECTORY EntryIdentity")


def _failure(step: ExecutionStep, kind: ExecutionFailureKind, *, errno: int | None = None,
             stage: TransferStage | None = None) -> tuple[None, ExecutionFailure]:
    return None, ExecutionFailure(step=step, kind=kind, stage=stage, errno=errno)


def revalidate_directory(path: str, identity: EntryIdentity) -> bool:
    """True iff ``path`` is still the same real directory (device, inode, type). Read-only.

    Missing, inaccessible, a link / reparse point, a special entry, an entry without a usable identity
    or a replacement all yield ``False``.
    """
    current = _fs.snapshot(path)
    if isinstance(current, OSError):  # SnapshotRefused is an OSError value too
        return False
    return current.entry_type is EntryType.DIRECTORY and same_identity(current, identity)


def _create_exclusive(path: str, step: ExecutionStep,
                      parent_changed: ExecutionFailureKind) -> tuple[EntryIdentity | None, ExecutionFailure | None]:
    """Absent-check, exclusive mkdir, post-mkdir snapshot. The parent was revalidated by the caller."""
    probe = _fs.snapshot(path)
    if isinstance(probe, _fs.SnapshotRefused) or not isinstance(probe, OSError):
        return _failure(step, ExecutionFailureKind.TARGET_CONFLICT)  # any existing entry: never adopted
    if isinstance(probe, NotADirectoryError):
        return _failure(step, parent_changed)
    if not isinstance(probe, FileNotFoundError):
        return _failure(step, ExecutionFailureKind.DIRECTORY_CREATE_FAILED, errno=_fs.os_errno(probe))

    failure = _mkdir_exclusive(path)
    if failure is not None:
        if isinstance(failure, FileExistsError):
            return _failure(step, ExecutionFailureKind.TARGET_CONFLICT)
        if isinstance(failure, _MISSING):
            return _failure(step, parent_changed)
        return _failure(step, ExecutionFailureKind.DIRECTORY_CREATE_FAILED, errno=_fs.os_errno(failure))

    created = _fs.snapshot(path)
    if isinstance(created, OSError) or created.entry_type is not EntryType.DIRECTORY:
        # mkdir succeeded (effect happened) but the entry is no longer an owned real directory.
        return _failure(step, ExecutionFailureKind.TARGET_DIRECTORY_CHANGED, stage=TransferStage.PUBLISH_VERIFY)
    return created, None


def create_target_directory(plan: object, library_root_identity: EntryIdentity,
                            ) -> tuple[EntryIdentity | None, ExecutionFailure | None]:
    """Contract section 21 (U1 ``CREATE_DIRECTORY``). ``plan`` must already be validated."""
    _require_directory_identity(library_root_identity, "library_root_identity")
    step = ExecutionStep.CREATE_DIRECTORY
    if not revalidate_directory(plan.library_root, library_root_identity):
        return _failure(step, ExecutionFailureKind.LIBRARY_ROOT_CHANGED)
    return _create_exclusive(plan.target_directory.absolute_path, step, ExecutionFailureKind.LIBRARY_ROOT_CHANGED)


def create_extrafanart_directory(plan: object, target_directory_identity: EntryIdentity,
                                 ) -> tuple[EntryIdentity | None, ExecutionFailure | None]:
    """Contract section 22 (U7 ``ENSURE_EXTRAFANART_DIRECTORY``), even with zero extrafanart images."""
    _require_directory_identity(target_directory_identity, "target_directory_identity")
    step = ExecutionStep.ENSURE_EXTRAFANART_DIRECTORY
    if not revalidate_directory(plan.target_directory.absolute_path, target_directory_identity):
        return _failure(step, ExecutionFailureKind.TARGET_DIRECTORY_CHANGED)
    return _create_exclusive(plan.extrafanart_directory.absolute_path, step,
                             ExecutionFailureKind.TARGET_DIRECTORY_CHANGED)


def child_name(directory: str, path: str) -> str | None:
    """The single component ``b`` with ``os.path.join(directory, b) == path``, else ``None`` (lexical)."""
    name = os.path.basename(path)
    if not name or os.path.join(directory, name) != path:
        return None
    return name


def _fold(name: str) -> str:
    return name.casefold() if os.name == "nt" else name


def compare_inventory(directory: str, expected_names: tuple[str, ...],
                      ) -> tuple[bool, frozenset[str]] | OSError:
    """Compare the entries directly inside ``directory`` with ``expected_names`` (Windows: casefold).

    Returns ``(has_unexpected_entry, missing_expected_names)`` (the missing names as given) or the listing
    ``OSError``. Read-only; an unexpected entry is only reported -- never touched, trusted or adopted,
    whatever its name looks like.
    """
    names = _fs.list_names(directory)
    if isinstance(names, OSError):
        return names
    present = {_fold(name) for name in names}
    expected = {_fold(name) for name in expected_names}
    missing = frozenset(name for name in expected_names if _fold(name) not in present)
    return bool(present - expected), missing
