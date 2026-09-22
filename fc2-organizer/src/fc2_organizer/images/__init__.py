"""Phase 4 / P4-C5: image acquisition -- substep 1 foundation only.

Scope of this substep (frozen, see
``docs/specifications/PHASE4_IMAGE_ACQUISITION_CONTRACT.md``): immutable value
models, the failure vocabulary, the acquisition policy and a pure candidate-URL
safety gate. There is **no** HTTP transport, redirect handling, download,
streaming, JPEG validation, dimension parsing or acquisition orchestration here
yet; those land in later P4-C5 substeps.

Dependency direction: standard library only (``fc2_organizer.images`` does not
import ``fc2_metadata_core``, ``httpx``, ``amane`` or any filesystem / network
module), and nothing below it imports ``images``.

Not eagerly imported by ``fc2_organizer/__init__.py``; import it explicitly:
``from fc2_organizer.images import validate_image_url``.
"""

from fc2_organizer.images.errors import (
    ImageError,
    ImageFailureKind,
    ImageInputError,
    ImageModelError,
    ImagePolicyError,
    ImageUrlError,
    UrlRejectionReason,
)
from fc2_organizer.images.models import (
    AcquiredImage,
    ImageAcquisitionResult,
    ImageCandidateFailure,
    ImageRole,
)
from fc2_organizer.images.policy import ImageAcquisitionPolicy
from fc2_organizer.images.urls import MAX_IMAGE_URL_LENGTH, validate_image_url

__all__ = [
    "AcquiredImage",
    "ImageAcquisitionPolicy",
    "ImageAcquisitionResult",
    "ImageCandidateFailure",
    "ImageError",
    "ImageFailureKind",
    "ImageInputError",
    "ImageModelError",
    "ImagePolicyError",
    "ImageRole",
    "ImageUrlError",
    "MAX_IMAGE_URL_LENGTH",
    "UrlRejectionReason",
    "validate_image_url",
]
