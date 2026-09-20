"""Transport-agnostic HTTP contract shared by every source adapter.

Phase 2 requirement: adapters must not each construct their own
``httpx.Client()``/``requests.Session()`` per fetch. Instead they depend on
this narrow :class:`SourceHttpClient` Protocol only. A production transport
(see ``fc2_metadata_core.http.httpx_client``) and a fully offline fake
transport (used by adapter unit tests) both satisfy this same Protocol, so
adapter code never needs monkeypatching to run offline -- a fake
implementation is simply passed in instead.

This module itself has zero third-party dependency (no ``httpx`` import
here) so that importing it -- and testing everything that only needs the
Protocol/value types/exceptions -- never requires the production transport
dependency to be installed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Protocol

from fc2_metadata_core.errors import FC2MetadataCoreError

__all__ = [
    "HttpResponse",
    "SourceHttpClient",
    "HttpTransportError",
    "HttpTimeoutError",
    "HttpConnectionError",
    "HttpRedirectLimitError",
    "HttpResponseTooLargeError",
]


class HttpTransportError(FC2MetadataCoreError):
    """Base class for every transport-level failure a SourceHttpClient raises.

    Raised instead of leaking a transport-library-specific exception type
    (e.g. ``httpx.ConnectError``) across the adapter boundary, so adapter
    code -- and its offline tests -- depend only on this vocabulary.
    """


class HttpTimeoutError(HttpTransportError):
    """The request did not complete within the configured timeout."""


class HttpConnectionError(HttpTransportError):
    """DNS resolution, TCP connect, or TLS handshake failed."""


class HttpRedirectLimitError(HttpTransportError):
    """The response chain exceeded the configured redirect limit."""


class HttpResponseTooLargeError(HttpTransportError):
    """The response body exceeded the configured maximum size."""


@dataclass(frozen=True, slots=True)
class HttpResponse:
    """A transport-agnostic snapshot of a completed HTTP response.

    ``url`` is the *final* URL after any redirects were followed -- callers
    never need to separately ask where they actually ended up (useful for
    detecting a site that redirects every lookup to a generic landing/error
    page instead of returning 404).
    """

    status_code: int
    url: str
    headers: Mapping[str, str]
    text: str
    elapsed_ms: float


class SourceHttpClient(Protocol):
    """Narrow interface a source adapter needs from an HTTP transport.

    Deliberately one verb, one response shape. Adapters depend on this
    Protocol only -- never on a concrete transport class -- so a production
    transport and a fully offline fake transport are interchangeable, both
    in production and in tests.
    """

    async def get(
        self,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        timeout: float | None = None,
    ) -> HttpResponse:
        """Perform an HTTP GET.

        Raises an :class:`HttpTransportError` subclass for anything that
        prevented a response from being obtained at all. A non-2xx HTTP
        response is *not* an error here: it comes back as an ordinary
        ``HttpResponse`` carrying that ``status_code`` for the caller
        (the source adapter) to classify.
        """
        ...
