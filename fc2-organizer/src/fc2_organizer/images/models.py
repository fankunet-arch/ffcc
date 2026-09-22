"""Immutable value objects for ``fc2_organizer.images`` (P4-C5 contract section 3-6).

Every model here is ``@dataclass(frozen=True, slots=True)`` and validates its
own invariants in ``__post_init__`` with **exact** type checks (``type(x) is T``):
a ``bool`` never passes as an ``int``, a ``bytes``/``str``/``tuple`` subclass never
passes as ``bytes``/``str``/``tuple``, and a model subclass never passes as the
model. Nothing here downloads, parses, decodes or writes an image; ``width`` /
``height`` are carried, not measured (JPEG parsing is a later P4-C5 substep).

``AcquiredImage.content`` is excluded from ``repr`` so a diagnostic print of a
result can never dump up to 16 MiB of image bytes.

There is deliberately no ``url`` / ``headers`` / ``error_detail`` / exception
field anywhere: a failure is a role + candidate index + kind (+ HTTP status),
nothing else.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import Enum

from fc2_organizer.images.errors import ImageFailureKind, ImageModelError

__all__ = [
    "ImageRole",
    "ImageFailureKind",
    "AcquiredImage",
    "ImageCandidateFailure",
    "ImageAcquisitionResult",
]

_HEX_LOWER = frozenset("0123456789abcdef")


class ImageRole(Enum):
    """The four artwork roles of the frozen v1.0 organize layout."""

    POSTER = "poster"
    FANART = "fanart"
    THUMB = "thumb"
    EXTRAFANART = "extrafanart"


def _type_name(value: object) -> str:
    return type(value).__name__


def _require_role(owner: str, value: object) -> None:
    if type(value) is not ImageRole:
        raise ImageModelError(f"{owner}.role must be an ImageRole, got {_type_name(value)}")


def _require_candidate_index(owner: str, value: object) -> None:
    if type(value) is not int:
        raise ImageModelError(f"{owner}.candidate_index must be an exact int, got {_type_name(value)}")
    if value < 0:
        raise ImageModelError(f"{owner}.candidate_index must be >= 0")


@dataclass(frozen=True, slots=True)
class AcquiredImage:
    """One successfully acquired image held in memory.

    Invariants: ``content`` is exact ``bytes``; ``size_bytes == len(content)``;
    ``sha256`` is the lowercase hex SHA-256 of ``content``; ``width`` /
    ``height`` are exact positive ``int``; ``candidate_index`` is an exact
    ``int >= 0`` (the position in the role's candidate list it came from).
    """

    role: ImageRole
    candidate_index: int
    content: bytes = field(repr=False)
    width: int
    height: int
    size_bytes: int
    sha256: str

    def __post_init__(self) -> None:
        _require_role("AcquiredImage", self.role)
        _require_candidate_index("AcquiredImage", self.candidate_index)
        if type(self.content) is not bytes:
            raise ImageModelError(f"AcquiredImage.content must be exact bytes, got {_type_name(self.content)}")
        for name in ("width", "height"):
            value = getattr(self, name)
            if type(value) is not int:
                raise ImageModelError(f"AcquiredImage.{name} must be an exact int, got {_type_name(value)}")
            if value <= 0:
                raise ImageModelError(f"AcquiredImage.{name} must be > 0")
        if type(self.size_bytes) is not int:
            raise ImageModelError(f"AcquiredImage.size_bytes must be an exact int, got {_type_name(self.size_bytes)}")
        if self.size_bytes != len(self.content):
            raise ImageModelError("AcquiredImage.size_bytes must equal len(content)")
        if type(self.sha256) is not str:
            raise ImageModelError(f"AcquiredImage.sha256 must be an exact str, got {_type_name(self.sha256)}")
        if len(self.sha256) != 64 or not _HEX_LOWER.issuperset(self.sha256):
            raise ImageModelError("AcquiredImage.sha256 must be 64 lowercase hex characters")
        if hashlib.sha256(self.content).hexdigest() != self.sha256:
            raise ImageModelError("AcquiredImage.sha256 does not match content")


@dataclass(frozen=True, slots=True)
class ImageCandidateFailure:
    """Why one candidate of one role was not acquired.

    ``http_status`` is an exact ``int`` in ``100..599`` when (and only when)
    ``kind is ImageFailureKind.HTTP_STATUS``; it is ``None`` for every other kind.
    No URL, query, header, cookie, body, exception or free-text detail is kept.
    """

    role: ImageRole
    candidate_index: int
    kind: ImageFailureKind
    http_status: int | None = None

    def __post_init__(self) -> None:
        _require_role("ImageCandidateFailure", self.role)
        _require_candidate_index("ImageCandidateFailure", self.candidate_index)
        if type(self.kind) is not ImageFailureKind:
            raise ImageModelError(
                f"ImageCandidateFailure.kind must be an ImageFailureKind, got {_type_name(self.kind)}"
            )
        if self.kind is ImageFailureKind.HTTP_STATUS:
            if type(self.http_status) is not int:
                raise ImageModelError(
                    "ImageCandidateFailure.http_status must be an exact int for kind HTTP_STATUS, "
                    f"got {_type_name(self.http_status)}"
                )
            if not 100 <= self.http_status <= 599:
                raise ImageModelError("ImageCandidateFailure.http_status must be in 100..599")
        elif self.http_status is not None:
            raise ImageModelError("ImageCandidateFailure.http_status must be None unless kind is HTTP_STATUS")


@dataclass(frozen=True, slots=True)
class ImageAcquisitionResult:
    """The images acquired for one film plus every per-candidate failure.

    ``poster`` / ``fanart`` / ``thumb`` are ``None`` or an exact ``AcquiredImage``
    of the matching role; ``extrafanart`` is an exact ``tuple`` of exact
    ``AcquiredImage`` whose role is ``EXTRAFANART``; ``failures`` is an exact
    ``tuple`` of exact ``ImageCandidateFailure``. An all-empty result is legal.
    """

    poster: AcquiredImage | None = None
    fanart: AcquiredImage | None = None
    thumb: AcquiredImage | None = None
    extrafanart: tuple[AcquiredImage, ...] = ()
    failures: tuple[ImageCandidateFailure, ...] = ()

    def __post_init__(self) -> None:
        for name, role in (("poster", ImageRole.POSTER), ("fanart", ImageRole.FANART), ("thumb", ImageRole.THUMB)):
            value = getattr(self, name)
            if value is None:
                continue
            if type(value) is not AcquiredImage:
                raise ImageModelError(
                    f"ImageAcquisitionResult.{name} must be None or an AcquiredImage, got {_type_name(value)}"
                )
            if value.role is not role:
                raise ImageModelError(f"ImageAcquisitionResult.{name} must have role {role.name}")
        if type(self.extrafanart) is not tuple:
            raise ImageModelError(
                f"ImageAcquisitionResult.extrafanart must be an exact tuple, got {_type_name(self.extrafanart)}"
            )
        for item in self.extrafanart:
            if type(item) is not AcquiredImage:
                raise ImageModelError(
                    f"ImageAcquisitionResult.extrafanart items must be AcquiredImage, got {_type_name(item)}"
                )
            if item.role is not ImageRole.EXTRAFANART:
                raise ImageModelError("ImageAcquisitionResult.extrafanart items must have role EXTRAFANART")
        if type(self.failures) is not tuple:
            raise ImageModelError(
                f"ImageAcquisitionResult.failures must be an exact tuple, got {_type_name(self.failures)}"
            )
        for item in self.failures:
            if type(item) is not ImageCandidateFailure:
                raise ImageModelError(
                    f"ImageAcquisitionResult.failures items must be ImageCandidateFailure, got {_type_name(item)}"
                )

    @property
    def total_bytes(self) -> int:
        """Sum of ``size_bytes`` over every acquired image (pure; no I/O)."""
        singles = (self.poster, self.fanart, self.thumb)
        return sum(image.size_bytes for image in singles if image is not None) + sum(
            image.size_bytes for image in self.extrafanart
        )
