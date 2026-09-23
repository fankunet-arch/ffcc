"""Binary image HTTP transport (P4-C5 substep 2, contract section 12).

::

    HttpxImageClient.get(url, deadline_seconds=, max_redirects=, max_bytes=)
        validate_image_url(url)                 before any request (substep-1 gate, not a copy)
        one asyncio.timeout(deadline_seconds)   covers every hop + headers + body
        hop:  send once (no retry), follow_redirects=False
              301/302/303/307/308 -> resolve Location against the current URL,
                                     validate_image_url(target) BEFORE the next hop is sent
              200                 -> stream raw bytes, stop at max_bytes + 1
              anything else       -> ImageHttpResponse(status, content_type, b"") -- body never read
        -> ImageHttpResponse(status_code, content_type, content)   builtin values only

This is the only ``fc2_organizer.images`` module allowed to import ``httpx``. It
works on ``bytes`` end to end: it never decodes a body as text and never reuses
``fc2_metadata_core``'s text-oriented ``SourceHttpClient`` / ``HttpResponse``.

Nothing is decided here about whether a 200 body *is* an acceptable image
(Content-Type policy, JPEG validity, dimensions): that belongs to the later
acquisition substep.

Error hygiene: every failure is one of the fixed-message, argument-less
``ImageTransportError`` subclasses (or the substep-1 ``ImageUrlError`` for the
initial URL). Library exceptions are translated into an error *value* inside the
worker coroutine and raised only afterwards from :meth:`HttpxImageClient.get`,
outside any ``except`` block, so ``__cause__`` / ``__context__`` are ``None`` and no
``httpx`` exception, request, response, header mapping or redirect URL is
reachable from the raised error. ``asyncio.CancelledError`` and every other
non-``Exception`` ``BaseException`` propagate untouched.

Cleanup (R1, contract section 12.9a): closing a response or its byte iterator runs
through :func:`_cleanup`, which turns an ordinary cleanup ``Exception`` into a fresh
error *value* (same type-based mapping) and never lets it replace a primary outcome:
an already-decided error value is kept, and a propagating cancellation / fatal
``BaseException`` is re-raised as the original object after cleanup.
"""

from __future__ import annotations

import asyncio
import math
import re
from dataclasses import dataclass
from types import TracebackType
from typing import Awaitable, Callable, Protocol
from urllib.parse import urljoin, urlsplit

import httpx

from fc2_organizer.images.errors import (
    ImageClientClosedError,
    ImageConnectionError,
    ImageError,
    ImageInputError,
    ImageModelError,
    ImageRedirectError,
    ImageRedirectLimitError,
    ImageResponseTooLargeError,
    ImageTimeoutError,
    ImageTransportError,
    ImageUrlError,
    UrlRejectionReason,
)
from fc2_organizer.images.urls import validate_image_url

__all__ = [
    "ImageHttpClient",
    "ImageHttpResponse",
    "HttpxImageClient",
    "REDIRECT_STATUSES",
    "IMAGE_REQUEST_HEADERS",
]

REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})

# Fixed request headers. Callers can add nothing (no Cookie / Authorization / custom header).
# ``identity`` keeps the byte counter equal to the bytes held in memory: no decompression
# (and so no decompression bomb) ever happens in this layer.
IMAGE_REQUEST_HEADERS: tuple[tuple[str, str], ...] = (
    ("Accept", "image/jpeg, image/*;q=0.8"),
    ("Accept-Encoding", "identity"),
    ("User-Agent", "fc2-organizer-image-fetch/0.1 (+https://github.com/fankunet-arch/ffcc)"),
)

_DECIMAL = re.compile(r"[0-9]+", re.ASCII)
_MEDIA_TYPE_MAX_CHARS = 127


@dataclass(frozen=True, slots=True)
class ImageHttpResponse:
    """The final response of one candidate request, reduced to builtin values.

    * ``status_code``: exact ``int`` in ``100..599`` (never a redirect status -- those are
      followed or fail).
    * ``content_type``: ``None`` or an exact ``str`` media type (section 12.8).
    * ``content``: exact ``bytes``; always ``b""`` unless ``status_code == 200``.

    No URL, redirect history, header mapping, cookie or library object is kept.
    """

    status_code: int
    content_type: str | None
    content: bytes

    def __post_init__(self) -> None:
        if type(self.status_code) is not int or not 100 <= self.status_code <= 599:
            raise ImageModelError("ImageHttpResponse.status_code must be an exact int in 100..599")
        if self.content_type is not None and type(self.content_type) is not str:
            raise ImageModelError("ImageHttpResponse.content_type must be None or an exact str")
        if type(self.content) is not bytes:
            raise ImageModelError("ImageHttpResponse.content must be exact bytes")
        if self.status_code != 200 and self.content:
            raise ImageModelError("ImageHttpResponse.content must be empty unless status_code is 200")


class ImageHttpClient(Protocol):
    """The binary transport boundary the acquisition layer depends on."""

    async def get(
        self,
        url: str,
        *,
        deadline_seconds: float,
        max_redirects: int,
        max_bytes: int,
    ) -> ImageHttpResponse: ...

    async def aclose(self) -> None: ...


def _check_arguments(deadline_seconds: object, max_redirects: object, max_bytes: object) -> None:
    if type(deadline_seconds) is not float and type(deadline_seconds) is not int:
        raise ImageInputError("deadline_seconds must be an exact int or float")
    if (type(deadline_seconds) is float and not math.isfinite(deadline_seconds)) or deadline_seconds <= 0:
        raise ImageInputError("deadline_seconds must be finite and > 0")
    if type(max_redirects) is not int or max_redirects < 0:
        raise ImageInputError("max_redirects must be an exact int >= 0")
    if type(max_bytes) is not int or max_bytes <= 0:
        raise ImageInputError("max_bytes must be an exact int > 0")


def _media_type(headers: httpx.Headers) -> str | None:
    """The ``Content-Type`` media type (before any ``;``), whitespace-trimmed, case kept.

    ``None`` when absent, empty, longer than 127 chars, or containing anything but
    printable ASCII. No accept / reject decision is made here."""
    raw = headers.get("content-type")
    if raw is None:
        return None
    value = str(raw).split(";", 1)[0].strip()
    if not value or len(value) > _MEDIA_TYPE_MAX_CHARS:
        return None
    if any(not 0x21 <= ord(char) <= 0x7E for char in value):
        return None
    return value


def _declared_length_exceeds(headers: httpx.Headers, max_bytes: int) -> bool:
    """True only for a well-formed decimal ``Content-Length`` larger than ``max_bytes``.

    Malformed / duplicated / signed values are ignored (the streamed byte counter still
    applies). Very long digit strings are compared by length, never passed to ``int()``."""
    raw = headers.get("content-length")
    if raw is None:
        return False
    value = str(raw).strip()
    if _DECIMAL.fullmatch(value) is None:
        return False
    digits = value.lstrip("0") or "0"
    limit = str(max_bytes)
    if len(digits) != len(limit):
        return len(digits) > len(limit)
    return digits > limit


class _RedirectSignal(Exception):
    """Private control-flow signal: a redirect status was received.

    httpx 0.27 ``AsyncClient.send`` parses the ``Location`` header itself (to build
    ``response.next_request``) even with ``follow_redirects=False``, raising its own
    exceptions for a malformed / non-http target. The response event hook runs after the
    headers arrive and *before* that step, so raising this signal there hands the raw
    ``Location`` string to our own resolver + ``validate_image_url`` instead. httpx closes
    the response (unread) on the way out. Holds only the status and the header string;
    never escapes this module."""

    def __init__(self, location: str | None) -> None:
        super().__init__()
        self.location = location


async def _stop_at_redirect(response: httpx.Response) -> None:
    if response.status_code in REDIRECT_STATUSES:
        location = response.headers.get("location")
        raise _RedirectSignal(None if location is None else str(location))


def _redirect_target(current: str, location: str | None) -> str | ImageError:
    """Resolve ``location`` against ``current`` and re-validate with the substep-1 gate.
    Returns the absolute target, or a fresh ``ImageRedirectError`` (never raised here)."""
    if location is None or not location.strip():
        return ImageRedirectError()
    try:
        target = urljoin(current, location)
    except Exception:
        return ImageRedirectError(UrlRejectionReason.MALFORMED)
    try:
        validate_image_url(target)
    except ImageUrlError as error:
        return ImageRedirectError(error.reason)
    return target


def _map_exception(exc: Exception) -> ImageTransportError:
    if isinstance(exc, (httpx.TimeoutException, TimeoutError)):
        return ImageTimeoutError()
    if isinstance(exc, (httpx.NetworkError, httpx.ProtocolError, httpx.ProxyError)):
        return ImageConnectionError()
    return ImageTransportError()


async def _cleanup(close: Callable[[], Awaitable[object]]) -> ImageTransportError | None:
    """Run one cleanup step (``response.aclose`` / byte-iterator ``aclose``).

    An ordinary ``Exception`` becomes a fresh, argument-less error value via the same
    type-based :func:`_map_exception` (httpx close / network -> ``ImageConnectionError``,
    anything else -> ``ImageTransportError``). The value is created, never raised, so it
    has no ``__cause__`` / ``__context__`` / traceback. A cancellation / fatal
    ``BaseException`` raised by the cleanup itself propagates unchanged."""
    try:
        await close()
    except Exception as exc:
        return _map_exception(exc)
    return None


def _deadline_delay(deadline_seconds: int | float) -> float | None:
    """``deadline_seconds`` as the float ``asyncio.timeout`` needs, or ``None`` when an
    (already validated, positive) ``int`` is too large to be represented as a float.
    Decided by exception type (``OverflowError`` of the conversion), never by message."""
    if type(deadline_seconds) is float:
        return deadline_seconds
    try:
        return float(deadline_seconds)
    except OverflowError:
        return None


class HttpxImageClient:
    """Production :class:`ImageHttpClient`: one shared ``httpx.AsyncClient`` per instance.

    Construction performs no I/O and sends no request. The ``AsyncClient`` is created
    once here (never per request, never at import time) with ``follow_redirects=False``,
    ``trust_env=False`` (no proxy environment variables, no ``.netrc``), no auth, no
    cookies and no caller headers. ``transport`` exists so tests can inject
    ``httpx.MockTransport``; production callers leave it ``None``.

    Lifecycle: ``async with HttpxImageClient() as client: ...`` or an explicit
    ``await client.aclose()`` (idempotent). Any ``get`` after close raises
    :class:`ImageClientClosedError`.
    """

    def __init__(self, *, transport: httpx.AsyncBaseTransport | None = None) -> None:
        if transport is not None and not isinstance(transport, httpx.AsyncBaseTransport):
            raise ImageInputError("transport must be None or an httpx.AsyncBaseTransport")
        self._closed = False
        self._client = httpx.AsyncClient(
            follow_redirects=False,
            trust_env=False,
            transport=transport,
            event_hooks={"response": [_stop_at_redirect]},
        )

    @property
    def closed(self) -> bool:
        return self._closed

    async def aclose(self) -> None:
        if self._closed:
            return
        self._closed = True
        await self._client.aclose()

    async def __aenter__(self) -> HttpxImageClient:
        if self._closed:
            raise ImageClientClosedError()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.aclose()

    async def get(
        self,
        url: str,
        *,
        deadline_seconds: float,
        max_redirects: int,
        max_bytes: int,
    ) -> ImageHttpResponse:
        _check_arguments(deadline_seconds, max_redirects, max_bytes)
        if self._closed:
            raise ImageClientClosedError()
        validate_image_url(url)  # raises ImageUrlError before any request is built
        outcome = await self._get_within_deadline(url, deadline_seconds, max_redirects, max_bytes)
        if isinstance(outcome, ImageError):
            raise outcome  # raised here, outside every except block: no __cause__ / __context__
        return outcome

    async def _get_within_deadline(
        self, url: str, deadline_seconds: float, max_redirects: int, max_bytes: int
    ) -> ImageHttpResponse | ImageError:
        delay = _deadline_delay(deadline_seconds)
        if delay is None:
            # R1 / P4-C5-R-02: accepted by policy, not representable by the event loop's
            # float clock. Nothing is sent; a fresh fixed-message error is returned.
            return ImageTransportError()
        try:
            async with asyncio.timeout(delay) as scope:
                return await self._follow(url, scope, max_redirects, max_bytes)
        except TimeoutError:
            # Only asyncio.timeout's own expiry reaches here: _follow turns every ordinary
            # Exception into a returned value. A caller's CancelledError is not converted.
            return ImageTimeoutError()

    async def _follow(
        self, url: str, scope: asyncio.Timeout, max_redirects: int, max_bytes: int
    ) -> ImageHttpResponse | ImageError:
        current = url
        redirects_followed = 0
        loop = asyncio.get_running_loop()
        # Every error returned below is a *fresh* instance created here (never one that was
        # raised), so it carries no traceback frames holding requests / responses / URLs.
        while True:
            when = scope.when()
            remaining = when - loop.time() if when is not None else None
            if remaining is not None and remaining <= 0:
                return ImageTimeoutError()
            try:
                request = self._build_request(current, remaining)
            except Exception as exc:
                return _map_exception(exc)
            if request is None:
                return ImageTransportError()
            try:
                response = await self._client.send(request, stream=True)
            except _RedirectSignal as signal:
                # Redirect response: httpx already closed it unread (body never consumed).
                if redirects_followed >= max_redirects:
                    return ImageRedirectLimitError()
                target_or_error = _redirect_target(current, signal.location)
                if isinstance(target_or_error, ImageError):
                    return target_or_error
                current = target_or_error
                redirects_followed += 1
                continue
            except Exception as exc:
                return self._closed_or(_map_exception(exc))
            finally:
                self._client.cookies.clear()  # never carry a server cookie to any later hop
            # Closes without draining: a redirect / non-200 / over-cap body is never read on.
            try:
                outcome = await self._response_outcome(response, max_bytes)
            except BaseException:
                # Only cancellation / fatal reaches here (_response_outcome returns ordinary
                # failures as values). Cleanup's ordinary error is discarded; the original
                # object is re-raised.
                await _cleanup(response.aclose)
                raise
            cleanup_error = await _cleanup(response.aclose)
            if cleanup_error is not None and not isinstance(outcome, ImageError):
                return self._closed_or(cleanup_error)  # the primary error, if any, wins
            return outcome

    async def _response_outcome(
        self, response: httpx.Response, max_bytes: int
    ) -> ImageHttpResponse | ImageError:
        try:
            status = response.status_code
            if type(status) is not int or not 100 <= status <= 599 or status in REDIRECT_STATUSES:
                return ImageTransportError()
            content_type = _media_type(response.headers)
            if status != 200:
                return ImageHttpResponse(status_code=status, content_type=content_type, content=b"")
            return await self._read_body(response, content_type, max_bytes)
        except Exception as exc:
            return self._closed_or(_map_exception(exc))

    def _build_request(self, url: str, timeout_seconds: float | None) -> httpx.Request | None:
        """A request carrying only the fixed headers, built directly (not via the client's
        cookie / header / auth merging). Its parsed scheme and host must equal what the
        substep-1 validator judged, so no httpx / urllib parse differential slips through;
        on a mismatch ``None`` is returned and nothing is sent."""
        request = httpx.Request("GET", url, headers=list(IMAGE_REQUEST_HEADERS))
        judged = urlsplit(url)
        if request.url.scheme != judged.scheme or request.url.host != judged.hostname:
            return None
        if timeout_seconds is not None:
            request.extensions["timeout"] = httpx.Timeout(timeout_seconds).as_dict()
        return request

    async def _read_body(
        self, response: httpx.Response, content_type: str | None, max_bytes: int
    ) -> ImageHttpResponse | ImageError:
        encoding = response.headers.get("content-encoding")
        if encoding is not None and str(encoding).strip().lower() not in ("", "identity"):
            return ImageTransportError()
        if _declared_length_exceeds(response.headers, max_bytes):
            return ImageResponseTooLargeError()
        buffer = bytearray()
        # Content-Encoding is identity (checked above), so aiter_bytes() yields the raw bytes
        # unchanged; unlike aiter_raw() it also serves an already-buffered response.
        chunks = response.aiter_bytes()
        too_large = False
        try:
            async for chunk in chunks:
                if len(buffer) + len(chunk) > max_bytes:
                    too_large = True  # stop: no further chunk is pulled
                    break
                buffer += chunk
        except BaseException:
            # The primary failure (ordinary, cancellation or fatal) keeps precedence:
            # cleanup's ordinary error is discarded and the original object re-raised.
            await _cleanup(chunks.aclose)
            raise
        cleanup_error = await _cleanup(chunks.aclose)
        if too_large:
            return ImageResponseTooLargeError()
        if cleanup_error is not None:
            return self._closed_or(cleanup_error)
        return ImageHttpResponse(status_code=200, content_type=content_type, content=bytes(buffer))

    def _closed_or(self, error: ImageTransportError) -> ImageTransportError:
        return ImageClientClosedError() if self._closed else error
