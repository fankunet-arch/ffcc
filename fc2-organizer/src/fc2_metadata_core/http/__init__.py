"""Injectable HTTP transport abstraction for FC2 Metadata Core source adapters.

Adapters depend on :class:`SourceHttpClient` (a narrow Protocol) and
:class:`HttpResponse` only. Two implementations satisfy that Protocol:

- :class:`fc2_metadata_core.http.httpx_client.HttpxTransport` -- the
  production transport, backed by ``httpx``, shared across every adapter
  call rather than constructed per-fetch.
- a fully offline fake transport (``tests/support/fake_http_client.py``) --
  used by every adapter's offline unit tests, with zero network access and
  zero monkeypatching.

This top-level package intentionally does not import ``httpx_client`` (and
therefore does not require ``httpx`` to be installed) merely to use the
Protocol/value-types/exceptions here; only code that actually needs the
production transport imports ``fc2_metadata_core.http.httpx_client``
directly.
"""

from fc2_metadata_core.http.client import (
    HttpConnectionError,
    HttpRedirectLimitError,
    HttpResponse,
    HttpResponseTooLargeError,
    HttpTimeoutError,
    HttpTransportError,
    SourceHttpClient,
)

__all__ = [
    "HttpResponse",
    "SourceHttpClient",
    "HttpTransportError",
    "HttpTimeoutError",
    "HttpConnectionError",
    "HttpRedirectLimitError",
    "HttpResponseTooLargeError",
]
