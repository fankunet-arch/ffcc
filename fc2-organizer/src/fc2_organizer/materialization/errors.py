"""Error hierarchy for ``fc2_organizer.materialization`` (P4-C6).

This module is standard-library-only and never imports ``amane``,
``fc2_metadata_core``, any network module or any other ``fc2_organizer``
package.

Every distinct failure family has its own named exception; nothing is folded
into a bare ``OSError`` / ``ValueError``. An OS-level failure is classified
internally and only its ``errno`` number (or ``None``) is carried.

Messages are fixed wording only: they never contain the target path, the
temporary path (in particular never its random token), the payload bytes, or
an ``OSError`` string (whose ``filename`` would carry the temporary path). No
materialization error is chained to an ``OSError``; the only chaining is an
:class:`ArtifactCleanupError` raised ``from`` the already-typed primary
materialization error it reports.
"""

from __future__ import annotations

from enum import Enum

__all__ = [
    "MaterializationError",
    "MaterializationInputError",
    "InvalidTargetPathError",
    "TargetPathRejectionReason",
    "MaterializationModelError",
    "ParentDirectoryError",
    "ParentDirectoryMissingError",
    "ParentNotDirectoryError",
    "ParentRejectionReason",
    "TargetExistsError",
    "TargetInaccessibleError",
    "TemporaryCreateError",
    "ArtifactWriteError",
    "ArtifactWriteStage",
    "ArtifactPublishError",
    "ArtifactCleanupError",
    "ArtifactMappingError",
    "MappingRejectionReason",
]


class TargetPathRejectionReason(Enum):
    """Why an exact-``str`` target path was rejected before any filesystem access."""

    EMPTY = "empty"
    NUL_CHARACTER = "nul_character"
    NOT_ABSOLUTE = "not_absolute"
    DEVICE_NAMESPACE = "device_namespace"
    DOT_SEGMENT = "dot_segment"
    NO_BASENAME = "no_basename"
    ILLEGAL_CHARACTER = "illegal_character"
    TRAILING_DOT_OR_SPACE = "trailing_dot_or_space"
    RESERVED_NAME = "reserved_name"


class ParentRejectionReason(Enum):
    MISSING = "missing"
    NOT_A_DIRECTORY = "not_a_directory"
    INACCESSIBLE = "inaccessible"


class MappingRejectionReason(Enum):
    """Why ``build_artifact_requests`` refused a plan / NFO / image combination (substep 2)."""

    NFO_EMPTY = "nfo_empty"
    NFO_NOT_UTF8_ENCODABLE = "nfo_not_utf8_encodable"
    PLAN_PATH_INVALID = "plan_path_invalid"
    IMAGE_INVALID = "image_invalid"
    INVALID_EXTRAFANART_ORDINAL = "invalid_extrafanart_ordinal"
    DUPLICATE_TARGET = "duplicate_target"


class ArtifactWriteStage(Enum):
    """Which step of filling the owned temporary file failed."""

    WRITE = "write"
    FLUSH = "flush"
    CLOSE = "close"


def _errno_or_none(value: object) -> int | None:
    return value if type(value) is int else None


class MaterializationError(Exception):
    """Base class of every materialization failure."""


class MaterializationInputError(MaterializationError, TypeError):
    """``target_path`` is not an exact ``str`` or ``content`` is not exact ``bytes``."""


class InvalidTargetPathError(MaterializationError, ValueError):
    """The exact-``str`` target path is not an explicit, fully-qualified file path."""

    def __init__(self, reason: TargetPathRejectionReason) -> None:
        self.reason = reason
        super().__init__(f"target path rejected: {reason.value}")


class MaterializationModelError(MaterializationError, ValueError):
    """A hand-built :class:`MaterializedArtifact` violates its own contract."""


class ParentDirectoryError(MaterializationError):
    """The target's parent is not an existing, accessible directory. Never auto-created."""

    def __init__(self, reason: ParentRejectionReason = ParentRejectionReason.INACCESSIBLE,
                 errno: int | None = None) -> None:
        self.reason = reason
        self.errno = _errno_or_none(errno)
        super().__init__(f"target parent directory unusable: {reason.value}")


class ParentDirectoryMissingError(ParentDirectoryError):
    def __init__(self, errno: int | None = None) -> None:
        super().__init__(ParentRejectionReason.MISSING, errno)


class ParentNotDirectoryError(ParentDirectoryError):
    def __init__(self, errno: int | None = None) -> None:
        super().__init__(ParentRejectionReason.NOT_A_DIRECTORY, errno)


class TargetExistsError(MaterializationError):
    """Something (file, directory, symlink, junction, ...) already occupies the target.

    Raised by the pre-check *and* by the atomic no-overwrite publish itself when a
    concurrent writer wins the race. The existing entry is never modified.
    """

    def __init__(self) -> None:
        super().__init__("target already exists; overwrite is never performed")


class TargetInaccessibleError(MaterializationError):
    """The target entry could not be probed (e.g. permission denied on lstat)."""

    def __init__(self, errno: int | None = None) -> None:
        self.errno = _errno_or_none(errno)
        super().__init__("target path could not be probed")


class TemporaryCreateError(MaterializationError):
    """No exclusive temporary sibling file could be created."""

    def __init__(self, errno: int | None = None) -> None:
        self.errno = _errno_or_none(errno)
        super().__init__("temporary sibling file could not be created")


class ArtifactWriteError(MaterializationError):
    """Writing, flushing or closing the owned temporary file failed."""

    def __init__(self, stage: ArtifactWriteStage, errno: int | None = None) -> None:
        self.stage = stage
        self.errno = _errno_or_none(errno)
        super().__init__(f"temporary artifact {stage.value} failed")


class ArtifactPublishError(MaterializationError):
    """The atomic no-overwrite publish failed for a reason other than an existing target."""

    def __init__(self, errno: int | None = None) -> None:
        self.errno = _errno_or_none(errno)
        super().__init__("atomic publish failed")


class ArtifactCleanupError(MaterializationError):
    """The owned temporary file could not be removed.

    ``target_published`` tells the caller whether the final target now holds the
    complete payload (POSIX hard-link publish succeeded, only the temp unlink
    failed) or not (a failure path whose cleanup also failed; ``primary`` is the
    typed error that started the failure path).
    """

    def __init__(self, *, target_published: bool, primary: MaterializationError | None,
                 errno: int | None = None) -> None:
        self.target_published = target_published
        self.primary = primary
        self.errno = _errno_or_none(errno)
        state = "published" if target_published else "not published"
        super().__init__(f"owned temporary file could not be removed (target {state})")


class ArtifactMappingError(MaterializationError, ValueError):
    """The already-typed inputs cannot be mapped to artifact write requests (substep 2).

    Carries only a :class:`MappingRejectionReason`; never a path, NFO text or image bytes.
    """

    def __init__(self, reason: MappingRejectionReason) -> None:
        self.reason = reason
        super().__init__(f"artifact mapping rejected: {reason.value}")
