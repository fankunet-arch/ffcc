"""``discover_media`` -- safe, read-only, deterministic recursive media
discovery (contract sections 3, 7).

Architecture (frozen): this module performs filesystem *reads* only. It
never calls ``os.mkdir``/``os.remove``/``os.rename``/``os.chmod``/``os.utime``
or opens a file for writing, and it has zero dependency on ``amane`` or any
``fc2_metadata_core`` submodule (``fc2_organizer -> fc2_metadata_core`` is
the only allowed direction; this package happens to need none of it).

The three filesystem seams below (``_list_directory_sorted``,
``_stat_entry``, ``_is_symlink``) exist so tests can inject a failure
(``PermissionError``, ``FileNotFoundError``, a vanished path) at an exact
point without depending on flaky, hard-to-construct real OS conditions
(section 13/17/18).
"""

from __future__ import annotations

import itertools
import os
import stat as stat_module
from collections.abc import Iterator
from pathlib import Path

from fc2_organizer.discovery._platform import is_reparse_point
from fc2_organizer.discovery.errors import (
    DiscoveryInputError,
    DiscoveryRootAccessError,
    DiscoveryRootNotADirectoryError,
    DiscoveryRootNotFoundError,
)
from fc2_organizer.discovery.models import (
    DiscoveredMediaItem,
    DiscoveryIssue,
    DiscoveryIssueKind,
    DiscoveryResult,
    DiscoveryStage,
)
from fc2_organizer.discovery.policy import DiscoveryPolicy

__all__ = ["discover_media"]


def _coerce_root(root: object) -> Path:
    """Coerce ``root`` to an **absolute, lexically-unmodified** ``Path``
    (P4-C1-R-01, tightened by P4-C1-R1-01).

    This must produce an *absolute OS-native path*, not a *canonicalized /
    normalized / resolved physical path* -- those are not the same thing
    when a relative segment (``.``/``..``) sits on either side of a
    symlink or a Windows junction/reparse point.

    ``os.path.abspath`` (P4-C1-R-01's original fix) is **not used**: despite
    its name, ``abspath`` first lexically normalizes the whole path
    (collapsing ``a/../b`` to ``b``) *before* any filesystem lookup ever
    happens. For an ordinary directory that lexical collapse is harmless.
    For ``link/../mydir`` where ``link`` is a symlink or junction, it is
    wrong: the real filesystem resolves ``..`` *after* traversing into
    wherever ``link`` actually points, which is not necessarily anywhere
    near ``link``'s own parent directory. Lexically collapsing first (as
    ``abspath``/``normpath`` do) silently substitutes a different physical
    directory for the one the caller's path string actually names --
    exactly the P4-C1-R1-01 regression the independent reviewer reproduced.
    ``Path.resolve()``/``os.path.realpath`` are equally wrong here for the
    same reason, plus they additionally resolve the root itself through any
    symlink, which P4-C1-R-01's original fix already correctly rejected.

    The fix: absolute-ize only by prefixing the current working directory
    onto a *relative* root -- never rewriting the segments that were
    already there. ``pathlib``'s ``/`` join (unlike ``os.path.normpath``/
    ``abspath``) never collapses ``..`` and only drops a redundant ``.``
    segment, which is always lexically safe (a bare ``.`` never changes
    which directory a path names, with or without symlinks in the way).
    An already-absolute root is returned completely untouched, including
    any ``..``/symlink-sensitive segments it contains.

    Every path built during the walk (``DiscoveryResult.root``, every
    ``DiscoveredMediaItem.source_path``) is derived from this ``Path`` via
    plain ``os.scandir``/``os.DirEntry.path`` string concatenation (never
    re-normalized), so any ``..``/symlink segment present here is carried
    through unresolved into every result path. Every real filesystem call
    made along the way (``os.stat``, ``os.scandir``) still receives that
    same literal string and resolves it exactly the way the OS resolves any
    path -- component by component, following a symlink/junction/reparse
    point exactly where the caller's original path said to -- so scan
    *behavior* (what gets discovered) is governed by the OS's own path
    resolution, never by an early, symlink-blind, in-process string
    rewrite.
    """
    if isinstance(root, Path):
        candidate = root
    elif isinstance(root, str):
        if not root:
            raise DiscoveryInputError("discover_media root must not be an empty string")
        candidate = Path(root)
    elif isinstance(root, os.PathLike):
        candidate = Path(os.fspath(root))
    else:
        raise DiscoveryInputError(f"discover_media root must be a str or os.PathLike, got {type(root).__name__}")

    if not candidate.is_absolute():
        candidate = Path(os.getcwd()) / candidate
    return candidate


def _check_root(root_path: Path) -> None:
    try:
        st = os.stat(root_path)
    except FileNotFoundError as exc:
        raise DiscoveryRootNotFoundError(f"discovery root does not exist: {root_path}") from exc
    except NotADirectoryError as exc:
        raise DiscoveryRootNotADirectoryError(
            f"discovery root is not usable as a directory: {root_path}"
        ) from exc
    except PermissionError as exc:
        raise DiscoveryRootAccessError(f"discovery root is not accessible: {root_path}") from exc
    except OSError as exc:
        raise DiscoveryRootAccessError(f"discovery root could not be inspected: {root_path}") from exc

    if not stat_module.S_ISDIR(st.st_mode):
        raise DiscoveryRootNotADirectoryError(f"discovery root is not a directory: {root_path}")


def _list_directory_sorted(path: Path) -> list[os.DirEntry]:
    """List one directory's immediate entries, sorted deterministically by
    entry name (ordinal codepoint order -- never the raw OS enumeration
    order; contract section 3.3)."""
    with os.scandir(path) as it:
        entries = list(it)
    entries.sort(key=lambda entry: entry.name)
    return entries


def _stat_entry(entry: os.DirEntry) -> os.stat_result:
    return entry.stat(follow_symlinks=False)


def _is_symlink(entry: os.DirEntry) -> bool:
    return entry.is_symlink()


def _walk(
    directory: Path,
    root: Path,
    policy: DiscoveryPolicy,
    items: list[DiscoveredMediaItem],
    issues: list[DiscoveryIssue],
    counter: Iterator[int],
) -> None:
    try:
        entries = _list_directory_sorted(directory)
    except PermissionError:
        issues.append(
            DiscoveryIssue.build(path=str(directory), kind=DiscoveryIssueKind.PERMISSION_DENIED, stage=DiscoveryStage.LIST_DIRECTORY)
        )
        return
    except FileNotFoundError:
        issues.append(
            DiscoveryIssue.build(path=str(directory), kind=DiscoveryIssueKind.PATH_VANISHED, stage=DiscoveryStage.LIST_DIRECTORY)
        )
        return
    except OSError:
        issues.append(
            DiscoveryIssue.build(path=str(directory), kind=DiscoveryIssueKind.STAT_FAILED, stage=DiscoveryStage.LIST_DIRECTORY)
        )
        return

    for entry in entries:
        _process_entry(entry, root, policy, items, issues, counter)


def _process_entry(
    entry: os.DirEntry,
    root: Path,
    policy: DiscoveryPolicy,
    items: list[DiscoveredMediaItem],
    issues: list[DiscoveryIssue],
    counter: Iterator[int],
) -> None:
    entry_path = entry.path

    try:
        symlink = _is_symlink(entry)
    except OSError:
        issues.append(
            DiscoveryIssue.build(path=entry_path, kind=DiscoveryIssueKind.STAT_FAILED, stage=DiscoveryStage.CLASSIFY_ENTRY)
        )
        return

    if symlink:
        # Conservative, mandatory policy (section 11): a symlink is never
        # recursed into (directory) and never treated as a normal media
        # source (file) -- regardless of what it points to.
        issues.append(
            DiscoveryIssue.build(path=entry_path, kind=DiscoveryIssueKind.SYMLINK_SKIPPED, stage=DiscoveryStage.CLASSIFY_ENTRY)
        )
        return

    if is_reparse_point(entry_path):
        # Catches Windows junctions and any other reparse tag that
        # is_symlink() does not recognize as a symlink (section 11).
        issues.append(
            DiscoveryIssue.build(
                path=entry_path, kind=DiscoveryIssueKind.REPARSE_POINT_SKIPPED, stage=DiscoveryStage.CLASSIFY_ENTRY
            )
        )
        return

    try:
        is_dir = entry.is_dir(follow_symlinks=False)
        is_file = entry.is_file(follow_symlinks=False)
    except OSError:
        issues.append(
            DiscoveryIssue.build(path=entry_path, kind=DiscoveryIssueKind.STAT_FAILED, stage=DiscoveryStage.CLASSIFY_ENTRY)
        )
        return

    if is_dir:
        _walk(Path(entry_path), root, policy, items, issues, counter)
        return

    if not is_file:
        # Device files, FIFOs, sockets, ... : not an error, safely ignored.
        return

    extension = Path(entry.name).suffix.lower()
    if not policy.is_supported_extension(extension):
        return

    try:
        st = _stat_entry(entry)
    except FileNotFoundError:
        issues.append(
            DiscoveryIssue.build(path=entry_path, kind=DiscoveryIssueKind.PATH_VANISHED, stage=DiscoveryStage.STAT_ENTRY)
        )
        return
    except PermissionError:
        issues.append(
            DiscoveryIssue.build(path=entry_path, kind=DiscoveryIssueKind.PERMISSION_DENIED, stage=DiscoveryStage.STAT_ENTRY)
        )
        return
    except OSError:
        issues.append(
            DiscoveryIssue.build(path=entry_path, kind=DiscoveryIssueKind.STAT_FAILED, stage=DiscoveryStage.STAT_ENTRY)
        )
        return

    source_path = Path(entry_path)
    relative_path = source_path.relative_to(root)
    items.append(
        DiscoveredMediaItem(
            index=next(counter),
            source_path=str(source_path),
            relative_path=relative_path.as_posix(),
            extension=extension,
            size=st.st_size,
        )
    )


def discover_media(root: str | os.PathLike, policy: DiscoveryPolicy | None = None) -> DiscoveryResult:
    """Recursively, read-only discover supported media files under ``root``.

    Raises a ``DiscoveryRootError`` subclass (never an "empty success") if
    ``root`` does not exist, is not a directory, or cannot be accessed.
    Every other, non-root problem encountered while walking the tree
    (permission denied on a subdirectory, a file that vanished mid-scan,
    a symlink/junction that is deliberately not followed, ...) is isolated
    into a ``DiscoveryIssue`` and the scan continues.

    ``policy`` defaults to ``DiscoveryPolicy()`` (the built-in supported
    extension set) when omitted.
    """
    if policy is None:
        policy = DiscoveryPolicy()
    elif not isinstance(policy, DiscoveryPolicy):
        raise DiscoveryInputError(f"discover_media policy must be a DiscoveryPolicy, got {type(policy).__name__}")

    root_path = _coerce_root(root)
    _check_root(root_path)

    items: list[DiscoveredMediaItem] = []
    issues: list[DiscoveryIssue] = []
    counter = itertools.count()

    _walk(root_path, root_path, policy, items, issues, counter)

    return DiscoveryResult(root=str(root_path), items=tuple(items), issues=tuple(issues))
