"""Phase 4 / P4-C5: image acquisition -- substeps 1-3.

Substep 3 adds ``fc2_organizer.images.jpeg`` (stdlib only, exported here): the
JPEG-only Content-Type policy, bounded JPEG structural validation and the
dimension caps.

Scope so far (see ``docs/specifications/PHASE4_IMAGE_ACQUISITION_CONTRACT.md``):
immutable value models, the failure vocabulary, the acquisition policy, a pure
candidate-URL safety gate (substep 1) and a binary HTTP transport with manual,
re-validated redirects, a streamed size cap and one total deadline (substep 2),
JPEG-only content validation (substep 3). There is **no** acquisition
orchestration (``acquire_images``, candidate / role iteration) here yet.

Dependency direction: this package ``__init__`` and the foundation modules are
standard library only. ``fc2_organizer.images.transport`` is the single module
that imports ``httpx``; it is **not** imported here, so
``import fc2_organizer.images`` never loads ``httpx``. Import it explicitly:
``from fc2_organizer.images.transport import HttpxImageClient``. Nothing imports
``fc2_metadata_core`` or ``amane``, and nothing below this package imports ``images``.

Not eagerly imported by ``fc2_organizer/__init__.py``; import it explicitly:
``from fc2_organizer.images import validate_image_url``.
"""

from fc2_organizer.images.errors import (
    ImageClientClosedError,
    ImageConnectionError,
    ImageError,
    ImageFailureKind,
    ImageInputError,
    ImageModelError,
    ImagePolicyError,
    ImageRedirectError,
    ImageRedirectLimitError,
    ImageResponseTooLargeError,
    ImageTimeoutError,
    ImageTransportError,
    ImageUrlError,
    UrlRejectionReason,
    DimensionRejectionReason,
    ImageContentTypeError,
    ImageDimensionError,
    ImageJpegError,
    JpegRejectionReason,
)
from fc2_organizer.images.jpeg import (
    MAX_IMAGE_HEIGHT,
    MAX_IMAGE_PIXELS,
    MAX_IMAGE_WIDTH,
    ContentTypeVerdict,
    JpegInfo,
    inspect_jpeg,
    validate_acquired_image,
    validate_image_content_type,
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
    "ImageClientClosedError",
    "ImageConnectionError",
    "ImageError",
    "ImageFailureKind",
    "ImageInputError",
    "ImageModelError",
    "ImagePolicyError",
    "ImageRedirectError",
    "ImageRedirectLimitError",
    "ImageResponseTooLargeError",
    "ImageRole",
    "ImageTimeoutError",
    "ImageTransportError",
    "ImageUrlError",
    "MAX_IMAGE_URL_LENGTH",
    "UrlRejectionReason",
    "validate_image_url",
    # substep 3: JPEG-only content policy (stdlib only)
    "ContentTypeVerdict",
    "DimensionRejectionReason",
    "ImageContentTypeError",
    "ImageDimensionError",
    "ImageJpegError",
    "JpegInfo",
    "JpegRejectionReason",
    "MAX_IMAGE_HEIGHT",
    "MAX_IMAGE_PIXELS",
    "MAX_IMAGE_WIDTH",
    "inspect_jpeg",
    "validate_acquired_image",
    "validate_image_content_type",
]
