"""``ImageAcquisitionPolicy``: the immutable caps for image acquisition
(P4-C5 contract section 7).

Substep 1 only freezes and validates the values. Nothing here enforces them at
runtime yet -- the deadline, redirect, per-image byte, total byte, candidate and
extrafanart caps are applied by the later transport / orchestration substeps.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from fc2_organizer.images.errors import ImagePolicyError

__all__ = [
    "ImageAcquisitionPolicy",
    "DEFAULT_REQUEST_DEADLINE_SECONDS",
    "DEFAULT_MAX_REDIRECTS",
    "DEFAULT_MAX_IMAGE_BYTES",
    "DEFAULT_MAX_TOTAL_BYTES",
    "DEFAULT_MAX_CANDIDATES_PER_ROLE",
    "DEFAULT_MAX_EXTRAFANART",
]

DEFAULT_REQUEST_DEADLINE_SECONDS = 15.0
DEFAULT_MAX_REDIRECTS = 5
DEFAULT_MAX_IMAGE_BYTES = 16 * 1024 * 1024
DEFAULT_MAX_TOTAL_BYTES = 64 * 1024 * 1024
DEFAULT_MAX_CANDIDATES_PER_ROLE = 16
DEFAULT_MAX_EXTRAFANART = 12

_INT_FIELDS = (
    "max_redirects",
    "max_image_bytes",
    "max_total_bytes",
    "max_candidates_per_role",
    "max_extrafanart",
)


@dataclass(frozen=True, slots=True)
class ImageAcquisitionPolicy:
    """Immutable acquisition caps. ``ImageAcquisitionPolicy()`` is the frozen default.

    * ``request_deadline_seconds``: exact ``int`` or ``float`` (never ``bool``),
      finite, ``> 0``. Total wall-clock budget for one candidate request,
      redirects included.
    * every other field: exact ``int`` (never ``bool``), ``> 0``.
    * ``max_image_bytes <= max_total_bytes`` (a single image may never be
      allowed to exceed the whole-film budget).
    """

    request_deadline_seconds: float = DEFAULT_REQUEST_DEADLINE_SECONDS
    max_redirects: int = DEFAULT_MAX_REDIRECTS
    max_image_bytes: int = DEFAULT_MAX_IMAGE_BYTES
    max_total_bytes: int = DEFAULT_MAX_TOTAL_BYTES
    max_candidates_per_role: int = DEFAULT_MAX_CANDIDATES_PER_ROLE
    max_extrafanart: int = DEFAULT_MAX_EXTRAFANART

    def __post_init__(self) -> None:
        deadline = self.request_deadline_seconds
        if type(deadline) is not float and type(deadline) is not int:
            raise ImagePolicyError(
                "ImageAcquisitionPolicy.request_deadline_seconds must be an exact int or float, "
                f"got {type(deadline).__name__}"
            )
        # An int is always finite; math.isfinite() on a huge int would raise OverflowError.
        if (type(deadline) is float and not math.isfinite(deadline)) or deadline <= 0:
            raise ImagePolicyError("ImageAcquisitionPolicy.request_deadline_seconds must be finite and > 0")
        for name in _INT_FIELDS:
            value = getattr(self, name)
            if type(value) is not int:
                raise ImagePolicyError(
                    f"ImageAcquisitionPolicy.{name} must be an exact int, got {type(value).__name__}"
                )
            if value <= 0:
                raise ImagePolicyError(f"ImageAcquisitionPolicy.{name} must be > 0")
        if self.max_image_bytes > self.max_total_bytes:
            raise ImagePolicyError("ImageAcquisitionPolicy.max_image_bytes must be <= max_total_bytes")
