"""Error hierarchy for ``fc2_organizer.images`` (P4-C5).

This module has no dependency on anything outside the standard library and
must never import ``amane``, ``fc2_metadata_core``, ``httpx`` or any
filesystem / network module.

Every distinct failure family gets its own named exception rather than a bare
``ValueError``, so a caller can tell "a policy value is illegal" from "a model
invariant is violated" from "a candidate URL is unsafe" without parsing a
message string.

Messages never contain an image URL (full or partial), its query string, a
token, a header, a cookie, response bytes or an exception payload. A URL
rejection reports only its :class:`UrlRejectionReason`; model / policy errors
report only field names, Python type names and fixed wording. No images error
is chained to another exception.
"""

from __future__ import annotations

from enum import Enum

__all__ = [
    "ImageError",
    "ImageInputError",
    "ImagePolicyError",
    "ImageModelError",
    "ImageUrlError",
    "ImageFailureKind",
    "UrlRejectionReason",
]


class ImageFailureKind(Enum):
    """Frozen per-candidate failure vocabulary (contract section 5).

    P4-C5 substep 1 only freezes the words. Only ``INVALID_URL`` /
    ``UNSAFE_URL`` are produced by code in this substep (via
    :attr:`ImageUrlError.failure_kind`); every other kind is reserved for the
    later transport / validation / orchestration substeps.
    """

    # candidate selection / URL gate
    INVALID_URL = "invalid_url"
    UNSAFE_URL = "unsafe_url"
    CANDIDATE_LIMIT = "candidate_limit"
    # transport
    TIMEOUT = "timeout"
    CONNECTION_ERROR = "connection_error"
    REDIRECT_LIMIT = "redirect_limit"
    TRANSPORT_ERROR = "transport_error"
    # response
    HTTP_STATUS = "http_status"
    TOO_LARGE = "too_large"
    TOTAL_BYTES_LIMIT = "total_bytes_limit"
    # content
    CONTENT_TYPE_MISMATCH = "content_type_mismatch"
    INVALID_JPEG = "invalid_jpeg"
    INVALID_DIMENSIONS = "invalid_dimensions"


class UrlRejectionReason(Enum):
    """Why :func:`fc2_organizer.images.urls.validate_image_url` rejected a
    candidate (contract section 8). Each reason maps to exactly one
    :class:`ImageFailureKind` through :attr:`ImageUrlError.failure_kind`."""

    # -> ImageFailureKind.INVALID_URL (not a usable absolute http(s) URL)
    NOT_EXACT_STR = "not_exact_str"
    EMPTY = "empty"
    TOO_LONG = "too_long"
    WHITESPACE_OR_CONTROL = "whitespace_or_control"
    MALFORMED = "malformed"
    RELATIVE = "relative"
    MISSING_HOST = "missing_host"
    INVALID_PORT = "invalid_port"
    INVALID_HOST = "invalid_host"
    # -> ImageFailureKind.UNSAFE_URL (well-formed enough, but refused)
    UNSUPPORTED_SCHEME = "unsupported_scheme"
    BACKSLASH = "backslash"
    USERINFO = "userinfo"
    LOCALHOST = "localhost"
    NUMERIC_HOST = "numeric_host"
    NON_GLOBAL_IP = "non_global_ip"


_UNSAFE_REASONS = frozenset(
    {
        UrlRejectionReason.UNSUPPORTED_SCHEME,
        UrlRejectionReason.BACKSLASH,
        UrlRejectionReason.USERINFO,
        UrlRejectionReason.LOCALHOST,
        UrlRejectionReason.NUMERIC_HOST,
        UrlRejectionReason.NON_GLOBAL_IP,
    }
)


class ImageError(Exception):
    """Base class for every ``fc2_organizer.images`` failure."""


class ImageInputError(ImageError, TypeError):
    """A public images entry point was given an argument of the wrong Python
    type. Reserved for the later acquisition entry point; no substep-1 function
    raises it."""


class ImagePolicyError(ImageError, ValueError):
    """An :class:`~fc2_organizer.images.policy.ImageAcquisitionPolicy` field has
    the wrong exact type (``bool`` never passes as ``int`` / ``float``), is not
    finite, or is not strictly positive."""


class ImageModelError(ImageError, ValueError):
    """An images value object (``AcquiredImage``, ``ImageCandidateFailure``,
    ``ImageAcquisitionResult``) violates its own model-level invariants."""


class ImageUrlError(ImageError, ValueError):
    """A candidate image URL was rejected. Carries only :attr:`reason`; the URL
    itself is never stored on the exception and never appears in its message."""

    __slots__ = ("reason",)

    def __init__(self, reason: UrlRejectionReason) -> None:
        if type(reason) is not UrlRejectionReason:
            raise TypeError("ImageUrlError.reason must be a UrlRejectionReason")
        self.reason = reason
        super().__init__(f"image URL rejected: {reason.value}")

    @property
    def failure_kind(self) -> ImageFailureKind:
        """``UNSAFE_URL`` for a refused-by-policy URL, ``INVALID_URL`` otherwise."""
        if self.reason in _UNSAFE_REASONS:
            return ImageFailureKind.UNSAFE_URL
        return ImageFailureKind.INVALID_URL
