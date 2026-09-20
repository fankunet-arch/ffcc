"""Source adapter contract: canonical FC2 number in, ``SourceResult`` out.

::

    canonical FC2 number
            |
            v
    build request
            |
            v
    perform request through injected SourceHttpClient
            |
            v
    parse provider response
            |
            v
    NormalizedMetadata
            |
            v
    SourceResult

A :class:`SourceAdapter` describes *only* what one source returns for one
number. It must never call another source, never merge another source's
data, and never decide to retry/fan out on its own -- cross-source
scheduling and field-level aggregation are Phase 3 concerns, deliberately
not implemented here.
"""

from __future__ import annotations

import abc
from typing import ClassVar

from fc2_metadata_core.errors import InvalidCanonicalNumberInputError
from fc2_metadata_core.http.client import (
    HttpConnectionError,
    HttpRedirectLimitError,
    HttpResponseTooLargeError,
    HttpTimeoutError,
    HttpTransportError,
    SourceHttpClient,
)
from fc2_metadata_core.models.source_result import SourceErrorKind, SourceResult, SourceStatus
from fc2_metadata_core.normalize.fc2_number import is_valid_fc2_number

__all__ = [
    "SourceAdapter",
    "require_canonical_number",
    "classify_http_status",
    "classify_transport_error",
    "transport_error_result",
]


def require_canonical_number(number: str) -> str:
    """Enforce the canonical-number boundary at the start of every ``fetch``.

    Normalization (dirty filename/free text -> canonical ``FC2-1234567``)
    is Phase 1's job (``fc2_metadata_core.normalize``), not a source
    adapter's. An adapter must not re-implement filename parsing, and must
    not fabricate a fallback for garbage input -- it fails loudly and
    explicitly here instead.
    """
    if not is_valid_fc2_number(number):
        raise InvalidCanonicalNumberInputError(
            "source adapter fetch() requires an already-canonical FC2 "
            f"number (e.g. 'FC2-1234567'), got {number!r}. Normalize it "
            "with fc2_metadata_core.normalize.normalize_fc2_number first."
        )
    return number


_STATUS_CODE_HINTS: dict[int, SourceStatus] = {
    403: SourceStatus.BLOCKED,
    404: SourceStatus.NOT_FOUND,
    429: SourceStatus.RATE_LIMITED,
}


def classify_http_status(status_code: int) -> SourceStatus | None:
    """A conservative, provider-agnostic starting point for status mapping.

    Returns the unambiguous ``SourceStatus`` for a small set of HTTP status
    codes (403/404/429), or ``None`` for everything else -- notably
    including ``200``, which never by itself means ``SUCCESS``: the body
    must still be parsed and shown to satisfy
    ``NormalizedMetadata.meets_minimum_success()``. A provider that serves
    a "not found" page as plain ``200`` needs its own body-based check;
    this helper only covers what the HTTP status code alone can say.
    """
    return _STATUS_CODE_HINTS.get(status_code)


_TRANSPORT_ERROR_KIND: tuple[tuple[type[HttpTransportError], SourceErrorKind], ...] = (
    (HttpTimeoutError, SourceErrorKind.NETWORK_ERROR),
    (HttpConnectionError, SourceErrorKind.NETWORK_ERROR),
    (HttpRedirectLimitError, SourceErrorKind.NETWORK_ERROR),
    (HttpResponseTooLargeError, SourceErrorKind.INVALID_RESPONSE),
)


def classify_transport_error(exc: HttpTransportError) -> SourceErrorKind:
    """Map a ``SourceHttpClient`` transport exception to a ``SourceErrorKind``.

    DNS/connect/TLS/timeout/redirect-loop failures are all
    ``NETWORK_ERROR`` (nothing was received to judge); a response that
    exceeded the configured size limit is the provider's fault, not the
    connection's, so it is ``INVALID_RESPONSE``. Centralized here so every
    adapter classifies transport failures identically instead of
    reimplementing this mapping.
    """
    for exc_type, kind in _TRANSPORT_ERROR_KIND:
        if isinstance(exc, exc_type):
            return kind
    return SourceErrorKind.NETWORK_ERROR


def transport_error_result(
    source_id: str, exc: HttpTransportError, *, elapsed_ms: float = 0.0
) -> SourceResult:
    """Build the failure ``SourceResult`` for a caught transport exception.

    ``SourceErrorKind`` and ``SourceStatus`` share the same string values
    for every failure kind, so the matching status is derived from the
    classified error kind rather than needing its own parallel mapping.
    """
    error_kind = classify_transport_error(exc)
    return SourceResult(
        source_id=source_id,
        status=SourceStatus(error_kind.value),
        metadata=None,
        elapsed_ms=elapsed_ms,
        error_kind=error_kind,
        error_detail=f"{source_id}: transport error: {exc}",
    )


class SourceAdapter(abc.ABC):
    """Base class for a single pluggable FC2 metadata source.

    Subclasses set three non-empty class-level identity attributes and
    implement :meth:`fetch`:

    - ``source_id``: a stable provider identity. It must **not** change
      when the provider's domain changes (see ``base_url`` below, which
      *is* meant to be reconfigured) -- e.g. ``"fc2_official"``, never
      ``"fc2-official-current-domain-com"``.
    - ``display_name``: human-readable provider name for status
      reporting/UI.
    - ``default_base_url``: the verified default base URL for this
      provider. Callers may override it per instance via ``base_url=`` at
      construction (site migrations to a new domain are a configuration
      change, not a code change).
    """

    source_id: ClassVar[str] = ""
    display_name: ClassVar[str] = ""
    default_base_url: ClassVar[str] = ""

    def __init__(self, *, base_url: str | None = None) -> None:
        for attr_name in ("source_id", "display_name", "default_base_url"):
            value = getattr(type(self), attr_name, "")
            if not isinstance(value, str) or not value.strip():
                raise TypeError(
                    f"{type(self).__name__} must define a non-empty class "
                    f"attribute {attr_name!r}"
                )
        self.base_url: str = base_url if base_url is not None else self.default_base_url

    @abc.abstractmethod
    async def fetch(self, number: str, client: SourceHttpClient) -> SourceResult:
        """Look up one canonical FC2 number on this source.

        ``number`` must already be canonical -- implementations should
        call :func:`require_canonical_number` as their first line.
        ``client`` is an injected :class:`SourceHttpClient`; implementations
        must perform every request through it and must never construct
        their own transport/session.

        Must return a :class:`SourceResult` for every reachable outcome
        (never raise for a lookup that simply didn't succeed) except for
        :class:`~fc2_metadata_core.errors.InvalidCanonicalNumberInputError`
        from a non-canonical ``number``, which is a caller bug and is
        allowed to propagate.
        """
        raise NotImplementedError
