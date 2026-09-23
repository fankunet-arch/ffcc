"""Value models for ``fc2_organizer.materialization`` (P4-C6).

Substep 1: :class:`MaterializedArtifact` (result of one atomic write).
Substep 2: :class:`ArtifactKind` and :class:`ArtifactWriteRequest` (one artifact's
exact target path + exact bytes). Standard library only.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum

from fc2_organizer.materialization.errors import MaterializationModelError

__all__ = ["ArtifactKind", "ArtifactWriteRequest", "MaterializedArtifact"]

_SHA256_HEX = re.compile(r"[0-9a-f]{64}")


@dataclass(frozen=True, slots=True)
class MaterializedArtifact:
    """What one successful :func:`materialize_atomic_bytes` call published.

    Carries no temporary path, file handle, exception or filesystem object.
    ``sha256`` / ``size_bytes`` describe exactly the bytes written to ``target_path``.
    """

    target_path: str
    size_bytes: int
    sha256: str

    def __post_init__(self) -> None:
        if type(self.target_path) is not str or not self.target_path:
            raise MaterializationModelError("target_path must be a non-empty exact str")
        if type(self.size_bytes) is not int or self.size_bytes < 0:
            raise MaterializationModelError("size_bytes must be an exact int >= 0")
        if type(self.sha256) is not str or _SHA256_HEX.fullmatch(self.sha256) is None:
            raise MaterializationModelError("sha256 must be 64 lowercase hex characters")


class ArtifactKind(Enum):
    """The five artifact kinds of the frozen v1.0 layout (substep 2)."""

    NFO = "nfo"
    POSTER = "poster"
    FANART = "fanart"
    THUMB = "thumb"
    EXTRAFANART = "extrafanart"


@dataclass(frozen=True, slots=True)
class ArtifactWriteRequest:
    """One artifact to materialize: exact target path + exact bytes.

    Holds no ``PublicationRecord``, ``AcquiredImage``, URL, HTTP data or exception.
    ``ordinal`` is an exact ``int >= 1`` iff ``kind is EXTRAFANART``, else ``None``.
    ``content`` is excluded from ``repr``.
    """

    kind: ArtifactKind
    target_path: str
    content: bytes = field(repr=False)
    ordinal: int | None = None

    def __post_init__(self) -> None:
        if type(self.kind) is not ArtifactKind:
            raise MaterializationModelError("kind must be an ArtifactKind")
        if type(self.target_path) is not str or not self.target_path:
            raise MaterializationModelError("target_path must be a non-empty exact str")
        if type(self.content) is not bytes:
            raise MaterializationModelError("content must be exact bytes")
        if self.kind is ArtifactKind.EXTRAFANART:
            if type(self.ordinal) is not int or self.ordinal < 1:
                raise MaterializationModelError("extrafanart ordinal must be an exact int >= 1")
        elif self.ordinal is not None:
            raise MaterializationModelError("ordinal is only allowed for EXTRAFANART")
