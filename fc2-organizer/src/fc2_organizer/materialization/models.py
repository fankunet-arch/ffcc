"""Result model for ``fc2_organizer.materialization`` (P4-C6)."""

from __future__ import annotations

import re
from dataclasses import dataclass

from fc2_organizer.materialization.errors import MaterializationModelError

__all__ = ["MaterializedArtifact"]

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
