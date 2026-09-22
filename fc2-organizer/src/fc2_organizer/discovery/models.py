"""Immutable, deterministic, serialization-friendly result models for
``discover_media`` (contract section 5-7, 13).

All four public types are frozen dataclasses with ``slots=True``: no
attribute can be added or reassigned after construction, and every field is
a plain ``str`` / ``int`` / ``Enum`` / ``tuple`` -- nothing here holds an
exception object, a traceback, an open file handle, or any other
non-serializable value.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum

from fc2_organizer.discovery.errors import DiscoveryContractError

__all__ = [
    "DiscoveryIssueKind",
    "DiscoveryStage",
    "DiscoveredMediaItem",
    "DiscoveryIssue",
    "DiscoveryResult",
    "MAX_ISSUE_DETAIL_LENGTH",
]

MAX_ISSUE_DETAIL_LENGTH = 200


class DiscoveryIssueKind(Enum):
    """What kind of local, non-root problem was observed for one path."""

    PERMISSION_DENIED = "permission_denied"
    PATH_VANISHED = "path_vanished"
    STAT_FAILED = "stat_failed"
    SYMLINK_SKIPPED = "symlink_skipped"
    REPARSE_POINT_SKIPPED = "reparse_point_skipped"


class DiscoveryStage(Enum):
    """Which operation was being attempted when the issue was observed."""

    LIST_DIRECTORY = "list_directory"
    CLASSIFY_ENTRY = "classify_entry"
    STAT_ENTRY = "stat_entry"


def _require_str(value: object, field_name: str) -> None:
    if not isinstance(value, str) or not value:
        raise DiscoveryContractError(f"{field_name} must be a non-empty str, got {value!r}")


def _require_non_negative_int(value: object, field_name: str) -> None:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise DiscoveryContractError(f"{field_name} must be a non-negative int, got {value!r}")


@dataclass(frozen=True, slots=True)
class DiscoveredMediaItem:
    """One successfully discovered media file.

    Identity within a ``DiscoveryResult`` is ``(source_path, index)`` --
    never a parsed FC2 number (section 7.4): the same number appearing under
    two different directories is two independent items.

    ``source_path`` must be an absolute path (P4-C1-R-01): a relative
    ``source_path`` cannot be safely reopened by a caller that has since
    changed its working directory, and silently accepting one here would
    let a scanner regression (or a hand-built instance) reintroduce exactly
    the bug this invariant closes.
    """

    index: int
    source_path: str
    relative_path: str
    extension: str
    size: int

    def __post_init__(self) -> None:
        _require_non_negative_int(self.index, "DiscoveredMediaItem.index")
        _require_str(self.source_path, "DiscoveredMediaItem.source_path")
        if not os.path.isabs(self.source_path):
            raise DiscoveryContractError(
                f"DiscoveredMediaItem.source_path must be an absolute path, got {self.source_path!r}"
            )
        _require_str(self.relative_path, "DiscoveredMediaItem.relative_path")
        _require_str(self.extension, "DiscoveredMediaItem.extension")
        if not self.extension.startswith("."):
            raise DiscoveryContractError(
                f"DiscoveredMediaItem.extension must start with '.', got {self.extension!r}"
            )
        _require_non_negative_int(self.size, "DiscoveredMediaItem.size")


_ISSUE_MESSAGES: dict[DiscoveryIssueKind, str] = {
    DiscoveryIssueKind.PERMISSION_DENIED: "permission denied",
    DiscoveryIssueKind.PATH_VANISHED: "path no longer exists (removed during scan)",
    DiscoveryIssueKind.STAT_FAILED: "could not read filesystem metadata for this path",
    DiscoveryIssueKind.SYMLINK_SKIPPED: "symlink not followed (safety policy)",
    DiscoveryIssueKind.REPARSE_POINT_SKIPPED: "reparse point (e.g. junction) not followed (safety policy)",
}


@dataclass(frozen=True, slots=True)
class DiscoveryIssue:
    """A structured, bounded, sanitized record of one local scan problem.

    ``detail`` is always one of a small fixed set of canned, human-readable
    messages (never ``str(exc)``/``repr(exc)``, never a traceback, never the
    exception object itself -- section 13) and is truncated defensively to
    ``MAX_ISSUE_DETAIL_LENGTH`` even though the canned messages never
    approach that length.
    """

    path: str
    kind: DiscoveryIssueKind
    stage: DiscoveryStage
    detail: str

    def __post_init__(self) -> None:
        _require_str(self.path, "DiscoveryIssue.path")
        if not isinstance(self.kind, DiscoveryIssueKind):
            raise DiscoveryContractError(f"DiscoveryIssue.kind must be a DiscoveryIssueKind, got {self.kind!r}")
        if not isinstance(self.stage, DiscoveryStage):
            raise DiscoveryContractError(f"DiscoveryIssue.stage must be a DiscoveryStage, got {self.stage!r}")
        _require_str(self.detail, "DiscoveryIssue.detail")
        if len(self.detail) > MAX_ISSUE_DETAIL_LENGTH:
            object.__setattr__(self, "detail", self.detail[:MAX_ISSUE_DETAIL_LENGTH])

    @classmethod
    def build(cls, *, path: str, kind: DiscoveryIssueKind, stage: DiscoveryStage) -> "DiscoveryIssue":
        """The only constructor the scanner uses: ``detail`` is always the
        canned message for ``kind``, never caller-supplied free text."""
        return cls(path=path, kind=kind, stage=stage, detail=_ISSUE_MESSAGES[kind])


@dataclass(frozen=True, slots=True)
class DiscoveryResult:
    """The complete, immutable outcome of one ``discover_media`` call.

    A root-level failure is never represented here (see
    ``DiscoveryRootError`` and its subclasses) -- every ``DiscoveryResult``
    that is successfully constructed means "the root existed, was a
    directory, and was accessible"; ``items``/``issues`` may still both be
    empty (a genuinely empty, fully-readable tree).
    """

    root: str
    items: tuple[DiscoveredMediaItem, ...]
    issues: tuple[DiscoveryIssue, ...]

    def __post_init__(self) -> None:
        _require_str(self.root, "DiscoveryResult.root")
        if not isinstance(self.items, tuple) or not all(isinstance(i, DiscoveredMediaItem) for i in self.items):
            raise DiscoveryContractError("DiscoveryResult.items must be a tuple[DiscoveredMediaItem, ...]")
        if not isinstance(self.issues, tuple) or not all(isinstance(i, DiscoveryIssue) for i in self.issues):
            raise DiscoveryContractError("DiscoveryResult.issues must be a tuple[DiscoveryIssue, ...]")

        for position, item in enumerate(self.items):
            if item.index != position:
                raise DiscoveryContractError(
                    f"DiscoveredMediaItem.index must equal its position in DiscoveryResult.items; "
                    f"got index={item.index} at position={position}"
                )

        seen_paths: set[str] = set()
        for item in self.items:
            if item.source_path in seen_paths:
                raise DiscoveryContractError(
                    f"DiscoveryResult.items contains a duplicate source_path: {item.source_path!r}"
                )
            seen_paths.add(item.source_path)

    @property
    def total_items(self) -> int:
        return len(self.items)

    @property
    def total_issues(self) -> int:
        return len(self.issues)
