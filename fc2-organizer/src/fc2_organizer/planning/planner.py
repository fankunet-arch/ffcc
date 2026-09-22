"""``build_organize_plan``: the P4-C2 planning entry point.

::

    DiscoveredMediaItem (P4-C1, closed)
    + canonical FC2 number
    + NormalizedMetadata (fc2_metadata_core, closed)
    + library_root
    + OutputPolicy (optional)
            |
    build_organize_plan(...)
            |   pure, deterministic, side-effect-free, ZERO FILESYSTEM MUTATION
            v
    OrganizePlan (immutable)

This module never re-implements FC2 number parsing (it uses the frozen
``fc2_metadata_core.normalize.is_valid_fc2_number`` boundary), never
re-scans or re-discovers media (it only consumes an already-built
``DiscoveredMediaItem``), and never touches the filesystem: no
``mkdir``/``open``/``rename``/``move``/``copy``/``unlink`` appears anywhere
in this package (contract section 22).
"""

from __future__ import annotations

import os

from fc2_metadata_core.models import NormalizedMetadata
from fc2_metadata_core.normalize import is_valid_fc2_number

from fc2_organizer.discovery import DiscoveredMediaItem
from fc2_organizer.planning.errors import (
    InternalTargetCollisionError,
    InvalidCanonicalNumberError,
    InvalidLibraryRootError,
    InvalidMetadataForPlanningError,
    InvalidOutputPolicyError,
    OrganizePlanInputError,
)
from fc2_organizer.planning.models import (
    OrganizePlan,
    PlannedOperation,
    PlannedOperationKind,
    PlannedPath,
)
from fc2_organizer.planning.paths import (
    basenames_collide,
    is_fully_qualified_absolute_root,
    validate_path_component,
)
from fc2_organizer.planning.policy import OutputPolicy

__all__ = ["build_organize_plan"]


def build_organize_plan(
    media_item: DiscoveredMediaItem,
    canonical_number: str,
    metadata: NormalizedMetadata,
    library_root: str | os.PathLike,
    policy: OutputPolicy | None = None,
) -> OrganizePlan:
    """Compute the immutable, deterministic :class:`OrganizePlan` for one
    already-discovered media item, without touching the filesystem.

    :param media_item: a :class:`~fc2_organizer.discovery.DiscoveredMediaItem`
        produced by the closed P4-C1 ``discover_media``. Not re-validated
        against the real filesystem here -- only its already-validated
        fields (``source_path``, ``relative_path``, ``extension``,
        ``index``, ``size``) are consumed.
    :param canonical_number: an exact ``str`` already in canonical
        ``FC2-<digits>`` form (see
        ``fc2_metadata_core.normalize.is_valid_fc2_number``). Dirty input is
        rejected, never repaired -- this package contains no second FC2
        parser (contract section 9).
    :param metadata: a :class:`~fc2_metadata_core.models.NormalizedMetadata`
        that satisfies ``meets_minimum_success()``. Partial/failed metadata
        is rejected fail-closed (contract section 19).
    :param library_root: a *fully-qualified* absolute directory path (``str``
        or ``os.PathLike``) that is the target library root -- on Windows, a
        drive-qualified path (``C:\\lib``) or a UNC share (``\\\\server\\share``);
        on POSIX, an ordinary absolute path (``/lib``). A Windows
        rooted-but-driveless form (``\\lib``, ``/lib``) is rejected, not
        guessed onto the current drive (contract section 11, P4-C2-GOV-03).
        Never confused with ``media_item.source_path``'s own root (contract
        section 11).
    :param policy: an :class:`~fc2_organizer.planning.policy.OutputPolicy`,
        or ``None`` for the frozen v1.0 default layout.
    :raises OrganizePlanInputError: an argument has the wrong fundamental
        Python type.
    :raises InvalidCanonicalNumberError: ``canonical_number`` is not
        canonical.
    :raises InvalidMetadataForPlanningError: ``metadata`` does not meet
        minimum success.
    :raises InvalidOutputPolicyError: ``policy`` is neither ``None`` nor an
        ``OutputPolicy``.
    :raises InvalidLibraryRootError: ``library_root`` is empty, whitespace,
        or not absolute.
    :raises UnsafeTargetComponentError: a generated path component is
        Windows-unsafe.
    :raises InternalTargetCollisionError: two of this plan's own targets
        would collide under Windows case-insensitive semantics.
    """
    if not isinstance(media_item, DiscoveredMediaItem):
        raise OrganizePlanInputError(
            f"media_item must be a DiscoveredMediaItem, got {type(media_item)!r}"
        )

    if type(canonical_number) is not str:
        raise OrganizePlanInputError(
            f"canonical_number must be an exact str, got {type(canonical_number)!r}"
        )
    if not is_valid_fc2_number(canonical_number):
        raise InvalidCanonicalNumberError(
            f"canonical_number is not a valid canonical FC2 number: {canonical_number!r}"
        )

    if not isinstance(metadata, NormalizedMetadata):
        raise OrganizePlanInputError(
            f"metadata must be a NormalizedMetadata, got {type(metadata)!r}"
        )
    if not metadata.meets_minimum_success():
        raise InvalidMetadataForPlanningError(
            "metadata does not satisfy NormalizedMetadata.meets_minimum_success(); "
            "refusing to plan from partial/failed metadata"
        )

    if policy is None:
        policy = OutputPolicy()
    elif not isinstance(policy, OutputPolicy):
        raise InvalidOutputPolicyError(
            f"policy must be an OutputPolicy or None, got {type(policy)!r}"
        )

    if not isinstance(library_root, (str, os.PathLike)):
        raise OrganizePlanInputError(
            f"library_root must be a str or os.PathLike, got {type(library_root)!r}"
        )
    try:
        library_root_str = os.fspath(library_root)
    except TypeError as exc:
        raise OrganizePlanInputError(
            f"library_root could not be converted via os.fspath: {exc}"
        ) from exc
    if not isinstance(library_root_str, str):
        raise OrganizePlanInputError(
            f"library_root must resolve to a str path, got {type(library_root_str)!r}"
        )
    if not library_root_str.strip():
        raise InvalidLibraryRootError(
            f"library_root must be a non-empty, non-whitespace path, got {library_root_str!r}"
        )
    if not is_fully_qualified_absolute_root(library_root_str):
        raise InvalidLibraryRootError(
            "library_root must be a fully-qualified absolute path (a "
            "Windows drive-qualified path or UNC share, or a POSIX "
            f"absolute path); got {library_root_str!r} (P4-C2-GOV-03: a "
            "Windows rooted-but-driveless form such as '\\lib' or '/lib' "
            "is not accepted -- this package never guesses the current "
            "drive)"
        )

    directory_name = validate_path_component(canonical_number, label="target directory name")
    # Extension normalization (contract section 7): the container itself is
    # never changed, only its casing -- defensive even though the P4-C1
    # scanner already lowercases every discovered extension, because
    # DiscoveredMediaItem's own model contract does not itself enforce
    # lowercase (only "starts with '.'"), so a hand-built item must not be
    # able to bypass normalization here.
    normalized_extension = media_item.extension.lower()
    media_basename = validate_path_component(
        f"{canonical_number}{normalized_extension}", label="target media filename"
    )
    nfo_basename = validate_path_component(
        f"{canonical_number}{policy.nfo_extension}", label="NFO filename"
    )
    poster_basename = validate_path_component(policy.poster_filename, label="poster filename")
    fanart_basename = validate_path_component(policy.fanart_filename, label="fanart filename")
    thumb_basename = validate_path_component(policy.thumb_filename, label="thumb filename")
    extrafanart_dirname = validate_path_component(
        policy.extrafanart_dirname, label="extrafanart directory name"
    )

    _assert_no_internal_collisions(
        (
            ("target media", media_basename),
            ("NFO", nfo_basename),
            ("poster", poster_basename),
            ("fanart", fanart_basename),
            ("thumb", thumb_basename),
            ("extrafanart directory", extrafanart_dirname),
        )
    )

    target_directory = os.path.join(library_root_str, directory_name)

    def _child(basename: str) -> PlannedPath:
        return PlannedPath(os.path.join(target_directory, basename))

    target_directory_path = PlannedPath(target_directory)
    target_media_path = _child(media_basename)
    nfo_path = _child(nfo_basename)
    poster_path = _child(poster_basename)
    fanart_path = _child(fanart_basename)
    thumb_path = _child(thumb_basename)
    extrafanart_directory = _child(extrafanart_dirname)

    operations = (
        PlannedOperation(kind=PlannedOperationKind.CREATE_DIRECTORY, target=target_directory_path),
        PlannedOperation(
            kind=PlannedOperationKind.MOVE_MEDIA,
            target=target_media_path,
            source=PlannedPath(media_item.source_path),
        ),
        PlannedOperation(kind=PlannedOperationKind.MATERIALIZE_NFO, target=nfo_path),
        PlannedOperation(kind=PlannedOperationKind.MATERIALIZE_POSTER, target=poster_path),
        PlannedOperation(kind=PlannedOperationKind.MATERIALIZE_FANART, target=fanart_path),
        PlannedOperation(kind=PlannedOperationKind.MATERIALIZE_THUMB, target=thumb_path),
        PlannedOperation(
            kind=PlannedOperationKind.ENSURE_EXTRAFANART_DIRECTORY, target=extrafanart_directory
        ),
    )

    return OrganizePlan(
        source_path=media_item.source_path,
        source_relative_path=media_item.relative_path,
        source_extension=media_item.extension,
        source_index=media_item.index,
        source_size=media_item.size,
        canonical_number=canonical_number,
        library_root=library_root_str,
        target_directory=target_directory_path,
        target_media_path=target_media_path,
        nfo_path=nfo_path,
        poster_path=poster_path,
        fanart_path=fanart_path,
        thumb_path=thumb_path,
        extrafanart_directory=extrafanart_directory,
        operations=operations,
    )


def _assert_no_internal_collisions(labeled_basenames: tuple[tuple[str, str], ...]) -> None:
    """Fail closed if any two of this plan's own generated basenames would
    collide as Windows sibling filenames (contract section 14: no automatic
    suffixing, no silent rename -- ``InternalTargetCollisionError``)."""
    for i in range(len(labeled_basenames)):
        label_a, name_a = labeled_basenames[i]
        for j in range(i + 1, len(labeled_basenames)):
            label_b, name_b = labeled_basenames[j]
            if basenames_collide(name_a, name_b):
                raise InternalTargetCollisionError(
                    f"{label_a} target ({name_a!r}) collides with {label_b} target "
                    f"({name_b!r}) under Windows case-insensitive filename semantics"
                )
