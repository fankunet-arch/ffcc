"""Production :class:`SourceHttpClient` backed by ``httpx``.

Why ``httpx`` (Phase 2 dependency justification, see ``pyproject.toml``):
Phase 2 requires real outbound requests to FC2 metadata sources, and every
adapter must share one governed client lifecycle instead of each
constructing its own per-fetch session. ``httpx`` was chosen over
``requests`` because it has first-class ``async`` support -- required for
Phase 3's later multi-source concurrency, which this transport must not
need to be rewritten for -- while keeping a ``requests``-like API so the
transport implementation itself stays small.

Scope: this transport only ever provides a *single request's* governance --
a bounded timeout, a bounded redirect chain, and a bounded response size,
enforced by actually stopping a streamed read partway through rather than
downloading an oversized body and discarding it afterwards. Everything
about *scheduling many requests* (per-source/per-host concurrency, retry,
backoff, circuit breaking, fanout) is explicitly out of scope for Phase 2
and belongs to Phase 3.
"""

from __future__ import annotations

import time
from types import TracebackType
from typing import Mapping

import httpx

from fc2_metadata_core.http.client import (
    HttpConnectionError,
    HttpDecodingError,
    HttpRedirectLimitError,
    HttpResponse,
    HttpResponseTooLargeError,
    HttpTimeoutError,
)

__all__ = [
    "HttpxTransport",
    "DEFAULT_TIMEOUT_SECONDS",
    "DEFAULT_MAX_REDIRECTS",
    "DEFAULT_MAX_RESPONSE_BYTES",
]

DEFAULT_TIMEOUT_SECONDS = 15.0
DEFAULT_MAX_REDIRECTS = 5
# A metadata page, not a video file or an image; generous enough for even a
# heavy HTML page while still refusing to hold an unbounded body in memory.
DEFAULT_MAX_RESPONSE_BYTES = 5 * 1024 * 1024
_CHARSET_NAME_IN_MESSAGE_CHARS = 48


def _decode_body(body: bytes, encoding: str, url: str) -> str:
    """Bytes -> text, or :class:`HttpDecodingError` (Phase 3 C3-E02, closes C2 review L1).

    A server chooses the ``charset`` of its own ``Content-Type``, so anything Python's
    codec registry can be made to do is reachable from the network: a *non-text* codec
    (``rot13``, ``base64``, ``hex``, ``zlib``, ``bz2``, ``uu`` ... -> ``LookupError``),
    ``idna`` / ``undefined`` / ``punycode`` (-> ``UnicodeError``), a name with an
    embedded NUL (-> ``ValueError``). All of them are the *same* transport-domain
    failure -- "the body cannot be turned into text" -- and must not cross the adapter
    boundary as a bare stdlib exception. ``LookupError`` and ``ValueError`` (the base of
    ``UnicodeError``) cover every one of them.

    A charset name Python simply does not know (``charset=nonsense``) is *not* an error:
    ``httpx`` already substitutes UTF-8 for it before we get here, and a page that then
    decodes with replacement characters is still an ordinary response.
    """
    try:
        return body.decode(encoding, errors="replace")
    except (LookupError, ValueError) as exc:
        raise HttpDecodingError(_decode_failure_message(url, encoding, exc)) from exc


def _decode_failure_message(url: str, encoding: str, exc: Exception) -> str:
    shown = encoding if len(encoding) <= _CHARSET_NAME_IN_MESSAGE_CHARS else encoding[:_CHARSET_NAME_IN_MESSAGE_CHARS] + "..."
    return f"cannot decode response body of {url} as charset {shown!r}: {type(exc).__name__}"


class HttpxTransport:
    """Shared-lifecycle ``SourceHttpClient`` implementation using ``httpx``.

    One instance owns one ``httpx.AsyncClient`` for its whole lifetime.
    Adapters must be handed a shared instance (construct once, reuse across
    every ``fetch`` call -- e.g. via the async context manager) rather than
    each creating their own, so connection pooling and the governance
    below live in exactly one place.
    """

    def __init__(
        self,
        *,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        max_redirects: int = DEFAULT_MAX_REDIRECTS,
        max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
        user_agent: str = "fc2-organizer-source-probe/0.1 (+https://github.com/fankunet-arch/ffcc)",
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        """``transport`` is exposed only so tests can inject
        ``httpx.MockTransport`` and exercise this class's own redirect/size/
        error-mapping logic fully offline; production callers leave it
        unset and get real network I/O."""
        self._timeout_seconds = timeout_seconds
        self._max_response_bytes = max_response_bytes
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout_seconds),
            follow_redirects=True,
            max_redirects=max_redirects,
            headers={"User-Agent": user_agent},
            transport=transport,
        )

    async def get(
        self,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        timeout: float | None = None,
    ) -> HttpResponse:
        start = time.monotonic()
        request_timeout = timeout if timeout is not None else self._timeout_seconds
        try:
            async with self._client.stream(
                "GET",
                url,
                headers=dict(headers) if headers else None,
                timeout=request_timeout,
            ) as response:
                content_length = response.headers.get("content-length")
                if content_length is not None:
                    try:
                        declared = int(content_length)
                    except ValueError:
                        declared = None
                    if declared is not None and declared > self._max_response_bytes:
                        raise HttpResponseTooLargeError(
                            f"declared content-length {declared} exceeds "
                            f"{self._max_response_bytes} byte limit for {url}"
                        )

                body = bytearray()
                async for chunk in response.aiter_bytes():
                    body.extend(chunk)
                    if len(body) > self._max_response_bytes:
                        raise HttpResponseTooLargeError(
                            f"response body exceeded {self._max_response_bytes} "
                            f"byte limit while streaming {url}"
                        )

                status_code = response.status_code
                final_url = str(response.url)
                response_headers = dict(response.headers)
                try:
                    encoding = response.encoding or "utf-8"
                except (LookupError, ValueError) as exc:  # httpx probing a malformed charset (NUL ...)
                    raise HttpDecodingError(_decode_failure_message(url, "<malformed>", exc)) from exc
        except httpx.TooManyRedirects as exc:
            raise HttpRedirectLimitError(str(exc)) from exc
        except httpx.TimeoutException as exc:
            raise HttpTimeoutError(str(exc)) from exc
        except httpx.DecodingError as exc:
            raise HttpDecodingError(str(exc)) from exc
        except httpx.HTTPError as exc:
            raise HttpConnectionError(str(exc)) from exc

        elapsed_ms = (time.monotonic() - start) * 1000
        text = _decode_body(bytes(body), encoding, final_url)
        return HttpResponse(
            status_code=status_code,
            url=final_url,
            headers=response_headers,
            text=text,
            elapsed_ms=elapsed_ms,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> "HttpxTransport":
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.aclose()
