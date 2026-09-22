"""Immutable, deterministic, side-effect-free result models for
``build_organize_plan`` (contract section 6, 20-21).

All types here are frozen dataclasses with ``slots=True``: no attribute can
be added or reassigned after construction, and no model here performs any
filesystem access or mutation -- a ``PlannedOperation`` is purely
descriptive of what a future execution phase *would* do, never an action
that runs itself (contract section 17, 22).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum

from fc2_organizer.planning.errors import OrganizePlanContractError, TargetEscapesLibraryRootError
from fc2_organizer.planning.paths import is_contained_within, is_fully_qualified_absolute_root

__all__ = [
    "PlannedOperationKind",
    "PlannedPath",
    "PlannedOperation",
    "OrganizePlan",
]


class PlannedOperationKind(Enum):
    """What kind of step a ``PlannedOperation`` describes. Purely a label --
    no member here executes anything (contract section 17)."""

    CREATE_DIRECTORY = "create_directory"
    MOVE_MEDIA = "move_media"
    MATERIALIZE_NFO = "materialize_nfo"
    MATERIALIZE_POSTER = "materialize_poster"
    MATERIALIZE_FANART = "materialize_fanart"
    MATERIALIZE_THUMB = "materialize_thumb"
    ENSURE_EXTRAFANART_DIRECTORY = "ensure_extrafanart_directory"


def _require_nonempty_str(value: object, field_name: str) -> None:
    if type(value) is not str or not value:
        raise OrganizePlanContractError(f"{field_name} must be a non-empty str, got {value!r}")


def _require_non_negative_int(value: object, field_name: str) -> None:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise OrganizePlanContractError(f"{field_name} must be a non-negative int, got {value!r}")


@dataclass(frozen=True, slots=True)
class PlannedPath:
    """An immutable, absolute planned filesystem path.

    Purely descriptive: constructing one performs no filesystem access
    (no ``exists``/``stat``) and no filesystem mutation. The absolute-path
    invariant is enforced here at the model layer, independent of whether
    the planner that built it is correct -- mirroring the discovery
    package's own dual-layer (scanner + model) invariant for
    ``DiscoveredMediaItem.source_path`` (P4-C1-R-01).
    """

    absolute_path: str

    def __post_init__(self) -> None:
        _require_nonempty_str(self.absolute_path, "PlannedPath.absolute_path")
        if not os.path.isabs(self.absolute_path):
            raise OrganizePlanContractError(
                f"PlannedPath.absolute_path must be an absolute path, got {self.absolute_path!r}"
            )

    def __str__(self) -> str:  # convenience only; equality/hash stay dataclass-default
        return self.absolute_path


@dataclass(frozen=True, slots=True)
class PlannedOperation:
    """One purely descriptive planned step: ``kind`` + the ``PlannedPath``
    it targets, plus an optional ``source`` (only meaningful for
    ``MOVE_MEDIA``, which is the only operation with two paths).

    Never executes anything -- there is no ``run()``/``apply()`` method
    here, deliberately (contract section 17, 28).
    """

    kind: PlannedOperationKind
    target: PlannedPath
    source: PlannedPath | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.kind, PlannedOperationKind):
            raise OrganizePlanContractError(
                f"PlannedOperation.kind must be a PlannedOperationKind, got {self.kind!r}"
            )
        if not isinstance(self.target, PlannedPath):
            raise OrganizePlanContractError(
                f"PlannedOperation.target must be a PlannedPath, got {self.target!r}"
            )
        if self.source is not None and not isinstance(self.source, PlannedPath):
            raise OrganizePlanContractError(
                f"PlannedOperation.source must be a PlannedPath or None, got {self.source!r}"
            )

        needs_source = self.kind is PlannedOperationKind.MOVE_MEDIA
        has_source = self.source is not None
        if has_source != needs_source:
            raise OrganizePlanContractError(
                "PlannedOperation.source must be set if and only if kind is "
                f"MOVE_MEDIA (kind={self.kind!r}, source={self.source!r})"
            )


_PATH_FIELDS = (
    "target_directory",
    "target_media_path",
    "nfo_path",
    "poster_path",
    "fanart_path",
    "thumb_path",
    "extrafanart_directory",
)


@dataclass(frozen=True, slots=True)
class OrganizePlan:
    """An immutable, deterministic, side-effect-free plan for how one
    discovered media item *would* be organized, if a future execution phase
    chose to carry it out. Building one never touches the filesystem
    (contract section 22-23).

    Source media identity (``source_path``/``source_relative_path``/
    ``source_extension``/``source_index``/``source_size``) is carried
    through unchanged from the already-closed P4-C1 ``DiscoveredMediaItem``
    that produced this plan, so a future execution layer can re-verify it
    against the real filesystem before acting (contract section 10).
    """

    source_path: str
    source_relative_path: str
    source_extension: str
    source_index: int
    source_size: int

    canonical_number: str

    library_root: str

    target_directory: PlannedPath
    target_media_path: PlannedPath
    nfo_path: PlannedPath
    poster_path: PlannedPath
    fanart_path: PlannedPath
    thumb_path: PlannedPath
    extrafanart_directory: PlannedPath

    operations: tuple[PlannedOperation, ...]

    def __post_init__(self) -> None:
        _require_nonempty_str(self.source_path, "OrganizePlan.source_path")
        if not os.path.isabs(self.source_path):
            raise OrganizePlanContractError(
                f"OrganizePlan.source_path must be an absolute path, got {self.source_path!r}"
            )
        _require_nonempty_str(self.source_relative_path, "OrganizePlan.source_relative_path")
        _require_nonempty_str(self.source_extension, "OrganizePlan.source_extension")
        _require_non_negative_int(self.source_index, "OrganizePlan.source_index")
        _require_non_negative_int(self.source_size, "OrganizePlan.source_size")

        _require_nonempty_str(self.canonical_number, "OrganizePlan.canonical_number")

        _require_nonempty_str(self.library_root, "OrganizePlan.library_root")
        if not is_fully_qualified_absolute_root(self.library_root):
            raise OrganizePlanContractError(
                "OrganizePlan.library_root must be a fully-qualified absolute "
                f"path (P4-C2-GOV-03), got {self.library_root!r}"
            )

        for name in _PATH_FIELDS:
            value = getattr(self, name)
            if not isinstance(value, PlannedPath):
                raise OrganizePlanContractError(
                    f"OrganizePlan.{name} must be a PlannedPath, got {value!r}"
                )
            if not is_contained_within(value.absolute_path, self.library_root):
                raise TargetEscapesLibraryRootError(
                    f"OrganizePlan.{name} ({value.absolute_path!r}) is not contained "
                    f"under library_root ({self.library_root!r})"
                )

        if not isinstance(self.operations, tuple) or not all(
            isinstance(op, PlannedOperation) for op in self.operations
        ):
            raise OrganizePlanContractError(
                "OrganizePlan.operations must be a tuple[PlannedOperation, ...]"
            )
