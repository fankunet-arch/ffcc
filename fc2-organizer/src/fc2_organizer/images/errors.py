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
    "ImageTransportError",
    "ImageTimeoutError",
    "ImageConnectionError",
    "ImageRedirectLimitError",
    "ImageRedirectError",
    "ImageResponseTooLargeError",
    "ImageClientClosedError",
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
    """A public images entry point was given an illegal argument (wrong exact
    type or out-of-range value), e.g. ``HttpxImageClient.get(max_bytes=True)``."""


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
        return _url_failure_kind(self.reason)


def _url_failure_kind(reason: UrlRejectionReason) -> ImageFailureKind:
    if reason in _UNSAFE_REASONS:
        return ImageFailureKind.UNSAFE_URL
    return ImageFailureKind.INVALID_URL


# --- transport family (P4-C5 substep 2, contract section 12) ----------------------------------------
#
# Every transport error takes no constructor argument: its message is a fixed string, so no
# URL, header, body, or library exception text can ever be passed in. Transport code creates
# these outside of any ``except`` block's raise path, so ``__cause__`` / ``__context__`` stay None.


class ImageTransportError(ImageError):
    """A candidate request failed below the HTTP-status level (generic / unexpected failure)."""

    failure_kind = ImageFailureKind.TRANSPORT_ERROR
    _message = "image request failed"

    def __init__(self) -> None:
        super().__init__(self._message)


class ImageTimeoutError(ImageTransportError):
    """The per-candidate total deadline (all hops + body) expired, or the library timed out."""

    failure_kind = ImageFailureKind.TIMEOUT
    _message = "image request deadline exceeded"


class ImageConnectionError(ImageTransportError):
    """Connect / DNS / TLS / read / write / protocol-level connection failure."""

    failure_kind = ImageFailureKind.CONNECTION_ERROR
    _message = "image request connection failed"


class ImageRedirectLimitError(ImageTransportError):
    """More redirects than ``max_redirects`` were returned; the extra one was not followed."""

    failure_kind = ImageFailureKind.REDIRECT_LIMIT
    _message = "image request redirect limit exceeded"


class ImageRedirectError(ImageTransportError):
    """A redirect response had no usable ``Location``, or its target failed URL validation.

    ``reason`` is ``None`` for a missing / unusable ``Location``; otherwise it is the
    :class:`UrlRejectionReason` of the resolved target, and ``failure_kind`` follows the
    same INVALID_URL / UNSAFE_URL mapping as :class:`ImageUrlError`.
    """

    __slots__ = ("reason",)
    _message = "image request redirect rejected"

    def __init__(self, reason: UrlRejectionReason | None = None) -> None:
        if reason is not None and type(reason) is not UrlRejectionReason:
            raise TypeError("ImageRedirectError.reason must be a UrlRejectionReason or None")
        self.reason = reason
        suffix = "missing_location" if reason is None else reason.value
        Exception.__init__(self, f"{self._message}: {suffix}")

    @property
    def failure_kind(self) -> ImageFailureKind:  # type: ignore[override]
        if self.reason is None:
            return ImageFailureKind.TRANSPORT_ERROR
        return _url_failure_kind(self.reason)


class ImageResponseTooLargeError(ImageTransportError):
    """The 200 body (declared ``Content-Length`` or actually streamed bytes) exceeded ``max_bytes``."""

    failure_kind = ImageFailureKind.TOO_LARGE
    _message = "image response exceeded max_bytes"


class ImageClientClosedError(ImageTransportError):
    """The image HTTP client was used after ``aclose()`` / context-manager exit."""

    _message = "image HTTP client is closed"
