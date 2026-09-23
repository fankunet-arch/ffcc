"""Pure artifact mapping (P4-C6 substep 2).

``build_artifact_requests(plan, nfo_text, images)`` turns an already-built
``OrganizePlan``, an already-rendered NFO ``str`` and an already-acquired
``ImageAcquisitionResult`` into an ordered tuple of :class:`ArtifactWriteRequest`:

    NFO -> POSTER? -> FANART? -> THUMB? -> EXTRAFANART (acquisition order)

Pure and deterministic: ZERO filesystem access (``os.path.join`` is lexical only),
no clock, no randomness, no network. It never reads ``OrganizePlan.operations``,
never re-parses the canonical number, never renders NFO and never re-encodes,
resizes or de-duplicates an image.

Depends on the ``fc2_organizer.planning`` and ``fc2_organizer.images`` public
packages (models only). ``fc2_organizer.planning`` loads ``fc2_metadata_core``
transitively, so this module is **not** imported by
``fc2_organizer.materialization``'s ``__init__``; import it explicitly:
``from fc2_organizer.materialization.mapping import build_artifact_requests``.
"""

from __future__ import annotations

import os

from fc2_organizer.images import AcquiredImage, ImageAcquisitionResult, ImageRole
from fc2_organizer.materialization.errors import (
    ArtifactMappingError,
    MappingRejectionReason,
    MaterializationInputError,
)
from fc2_organizer.materialization.models import ArtifactKind, ArtifactWriteRequest
from fc2_organizer.planning import OrganizePlan, PlannedPath

__all__ = ["build_artifact_requests", "extrafanart_filename"]

_EXTRAFANART_FORMAT = "extrafanart-{:03d}.jpg"

_MAIN_IMAGES = (
    # (ImageAcquisitionResult field, expected role, artifact kind, OrganizePlan path field)
    ("poster", ImageRole.POSTER, ArtifactKind.POSTER, "poster_path"),
    ("fanart", ImageRole.FANART, ArtifactKind.FANART, "fanart_path"),
    ("thumb", ImageRole.THUMB, ArtifactKind.THUMB, "thumb_path"),
)


def extrafanart_filename(ordinal: int) -> str:
    """``extrafanart-{ordinal:03d}.jpg`` for any exact ``int >= 1`` (frozen).

    ``03d`` is a *minimum* width: 1 -> ``extrafanart-001.jpg``, 1000 ->
    ``extrafanart-1000.jpg``. There is no maximum (P4-C5 ``max_extrafanart`` is
    unbounded); nothing is truncated, wrapped or dropped.
    """
    if type(ordinal) is not int or ordinal < 1:
        raise ArtifactMappingError(MappingRejectionReason.INVALID_EXTRAFANART_ORDINAL)
    return _EXTRAFANART_FORMAT.format(ordinal)


def build_artifact_requests(
    plan: OrganizePlan,
    nfo_text: str,
    images: ImageAcquisitionResult,
) -> tuple[ArtifactWriteRequest, ...]:
    """Map one film's plan + rendered NFO + acquired images to ordered write requests."""
    # Exact-type checks first; no attribute or method of a rejected object is touched.
    if type(plan) is not OrganizePlan:
        raise MaterializationInputError("plan must be an exact OrganizePlan")
    if type(nfo_text) is not str:
        raise MaterializationInputError("nfo_text must be an exact str")
    if type(images) is not ImageAcquisitionResult:
        raise MaterializationInputError("images must be an exact ImageAcquisitionResult")

    requests = [ArtifactWriteRequest(ArtifactKind.NFO, _plan_path(plan.nfo_path), _encode_nfo(nfo_text))]

    for field_name, role, kind, path_field in _MAIN_IMAGES:
        image = getattr(images, field_name)
        if image is None:
            continue  # absent image: no request, not a failure; never a cross-role fallback
        requests.append(ArtifactWriteRequest(kind, _plan_path(getattr(plan, path_field)), _image_bytes(image, role)))

    extrafanart = images.extrafanart
    if type(extrafanart) is not tuple:
        raise ArtifactMappingError(MappingRejectionReason.IMAGE_INVALID)
    directory = _plan_path(plan.extrafanart_directory)
    for ordinal, image in enumerate(extrafanart, start=1):
        requests.append(ArtifactWriteRequest(
            ArtifactKind.EXTRAFANART,
            os.path.join(directory, extrafanart_filename(ordinal)),
            _image_bytes(image, ImageRole.EXTRAFANART),
            ordinal,
        ))

    _require_distinct_targets(requests)
    return tuple(requests)


def _encode_nfo(nfo_text: str) -> bytes:
    if not nfo_text:
        raise ArtifactMappingError(MappingRejectionReason.NFO_EMPTY)
    try:
        # exact UTF-8: no BOM, no newline change, no strip / normalization
        return nfo_text.encode("utf-8", errors="strict")
    except UnicodeEncodeError:
        pass
    raise ArtifactMappingError(MappingRejectionReason.NFO_NOT_UTF8_ENCODABLE)


def _plan_path(value: object) -> str:
    if type(value) is not PlannedPath:
        raise ArtifactMappingError(MappingRejectionReason.PLAN_PATH_INVALID)
    path = value.absolute_path
    if type(path) is not str or not path:
        raise ArtifactMappingError(MappingRejectionReason.PLAN_PATH_INVALID)
    return path


def _image_bytes(image: object, role: ImageRole) -> bytes:
    if type(image) is not AcquiredImage or image.role is not role or type(image.content) is not bytes:
        raise ArtifactMappingError(MappingRejectionReason.IMAGE_INVALID)
    return image.content  # the acquired bytes themselves: no re-encode / resize / transcode


def _require_distinct_targets(requests: list[ArtifactWriteRequest]) -> None:
    fold = str.casefold if os.name == "nt" else (lambda s: s)
    keys = [fold(r.target_path) for r in requests]
    if len(set(keys)) != len(keys):
        raise ArtifactMappingError(MappingRejectionReason.DUPLICATE_TARGET)
