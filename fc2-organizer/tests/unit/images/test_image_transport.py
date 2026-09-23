"""P4-C5 substep 2: binary image HTTP transport (contract section 12).

Fully offline: every test drives ``HttpxImageClient`` through ``httpx.MockTransport``
(or a recording ``AsyncByteStream``). No DNS, socket, listener or public network.
"""

from __future__ import annotations

import asyncio
import dataclasses
import gc

import httpx
import pytest

from fc2_organizer.images import (
    ImageClientClosedError,
    ImageConnectionError,
    ImageError,
    ImageFailureKind,
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
from fc2_organizer.images import transport as transport_module
from fc2_organizer.images.transport import (
    IMAGE_REQUEST_HEADERS,
    HttpxImageClient,
    ImageHttpClient,
    ImageHttpResponse,
)

SECRET = "SECRETTOKEN-9d2e"
URL = f"https://img.example.test/poster.jpg?token={SECRET}"
JPEG = b"\xff\xd8\xff\xe0" + bytes(range(256)) * 4 + b"\xff\xd9"
DEFAULTS = dict(deadline_seconds=5.0, max_redirects=5, max_bytes=16 * 1024 * 1024)


class RecordingStream(httpx.AsyncByteStream):
    """Yields ``chunks`` one by one and records how many were actually pulled."""

    def __init__(self, chunks: list[bytes], *, delay: float = 0.0, fail_after: int | None = None) -> None:
        self.chunks = chunks
        self.delay = delay
        self.fail_after = fail_after
        self.pulled = 0
        self.closed = False

    async def __aiter__(self):
        for chunk in self.chunks:
            if self.fail_after is not None and self.pulled >= self.fail_after:
                raise httpx.ReadError(f"connection reset while reading {URL}")
            if self.delay:
                await asyncio.sleep(self.delay)
            self.pulled += 1
            yield chunk

    async def aclose(self) -> None:
        self.closed = True


class Recorder:
    """A MockTransport handler routing by path; records every request actually sent."""

    def __init__(self, routes):
        self.routes = routes
        self.requests: list[httpx.Request] = []

    @property
    def urls(self) -> list[str]:
        return [str(r.url) for r in self.requests]

    async def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        route = self.routes(request) if callable(self.routes) else self.routes[request.url.path]
        if asyncio.iscoroutine(route):
            route = await route
        return route


def run(coro):
    return asyncio.run(coro)


async def fetch(recorder, url=URL, **overrides):
    kwargs = {**DEFAULTS, **overrides}
    async with HttpxImageClient(transport=httpx.MockTransport(recorder)) as client:
        return await client.get(url, **kwargs)


def fetch_error(recorder, url=URL, **overrides) -> ImageError:
    with pytest.raises(ImageError) as info:
        run(fetch(recorder, url, **overrides))
    return info.value


def redirect(location: str | None, status: int = 302, stream: RecordingStream | None = None) -> httpx.Response:
    headers = {} if location is None else {"Location": location}
    return httpx.Response(status, headers=headers, stream=stream or RecordingStream([b"<html>moved</html>"]))


def assert_clean_error(error: BaseException) -> None:
    """No URL / query / body / library object is reachable from a raised error."""
    rendered = " ".join([str(error), repr(error), repr(error.args)])
    for leaked in (SECRET, "img.example.test", "token", "127.0.0.1", "<html", "reset", "httpx"):
        assert leaked not in rendered, leaked
    assert error.__cause__ is None
    assert error.__context__ is None
    assert all(type(arg) is str for arg in error.args)
    attributes = list(getattr(error, "__dict__", {}).values()) + [getattr(error, "reason", None)]
    for value in attributes:
        assert value is None or type(value) is UrlRejectionReason, type(value)


# --- 1-7: status handling -------------------------------------------------------------------------


def test_200_binary_body_exact_bytes_preserved():
    stream = RecordingStream([JPEG[:100], JPEG[100:700], JPEG[700:]])
    recorder = Recorder({"/poster.jpg": httpx.Response(200, headers={"Content-Type": "image/jpeg"}, stream=stream)})
    response = run(fetch(recorder))
    assert type(response) is ImageHttpResponse
    assert response == ImageHttpResponse(status_code=200, content_type="image/jpeg", content=JPEG)
    assert type(response.content) is bytes and response.content == JPEG
    assert stream.pulled == 3 and stream.closed


def test_non_utf8_binary_is_never_text_round_tripped():
    body = bytes(range(256)) * 3  # invalid UTF-8 everywhere; any decode/encode would change it
    recorder = Recorder({"/poster.jpg": httpx.Response(200, content=body)})
    assert run(fetch(recorder)).content == body


@pytest.mark.parametrize("status", [404, 403, 429, 500, 204, 206, 304, 503])
def test_non_200_status_returned_without_reading_body(status):
    stream = RecordingStream([b"<html>" + SECRET.encode() + b"</html>"] * 50)
    recorder = Recorder(
        {"/poster.jpg": httpx.Response(status, headers={"Content-Type": "text/html; charset=utf-8"}, stream=stream)}
    )
    response = run(fetch(recorder))
    assert response == ImageHttpResponse(status_code=status, content_type="text/html", content=b"")
    assert stream.pulled == 0  # body never consumed
    assert stream.closed


def test_status_outside_http_range_is_transport_error():
    recorder = Recorder({"/poster.jpg": httpx.Response(999, content=b"x")})
    assert type(fetch_error(recorder)) is ImageTransportError


# --- 8-17: redirects --------------------------------------------------------------------------------


def test_one_redirect_followed():
    recorder = Recorder({"/poster.jpg": redirect("https://cdn.example.test/p.jpg"), "/p.jpg": httpx.Response(200, content=JPEG)})
    assert run(fetch(recorder)).content == JPEG
    assert recorder.urls == [URL, "https://cdn.example.test/p.jpg"]


def test_relative_redirect_resolved_against_current_url():
    recorder = Recorder({"/a/poster.jpg": redirect("../img/x.jpg?v=2"), "/img/x.jpg": httpx.Response(200, content=JPEG)})
    assert run(fetch(recorder, url="https://img.example.test/a/poster.jpg")).content == JPEG
    assert recorder.urls == ["https://img.example.test/a/poster.jpg", "https://img.example.test/img/x.jpg?v=2"]


@pytest.mark.parametrize("status", [301, 302, 303, 307, 308])
def test_every_redirect_status_is_followed_manually(status):
    recorder = Recorder({"/poster.jpg": redirect("/final.jpg", status), "/final.jpg": httpx.Response(200, content=JPEG)})
    assert run(fetch(recorder)).content == JPEG
    assert len(recorder.requests) == 2


def _chain(length: int) -> Recorder:
    """/r/<n> redirects to /r/<n-1>; /r/0 is the image. Starting at /r/<length> = <length> redirects."""

    def route(request: httpx.Request) -> httpx.Response:
        n = int(request.url.path.rsplit("/", 1)[1])
        if n == 0:
            return httpx.Response(200, content=JPEG)
        return redirect(f"/r/{n - 1}", 301 if n % 2 else 307)

    return Recorder(route)


@pytest.mark.parametrize(("max_redirects", "chain"), [(0, 0), (1, 1), (5, 5), (6, 6), (5, 0), (6, 5)])
def test_redirect_count_within_limit_succeeds(max_redirects, chain):
    recorder = _chain(chain)
    response = run(fetch(recorder, url=f"https://img.example.test/r/{chain}", max_redirects=max_redirects))
    assert response.content == JPEG
    assert len(recorder.requests) == chain + 1


@pytest.mark.parametrize(("max_redirects", "chain"), [(0, 1), (1, 2), (5, 6), (6, 7)])
def test_redirect_limit_exceeded_does_not_follow_the_extra_hop(max_redirects, chain):
    recorder = _chain(chain)
    error = fetch_error(recorder, url=f"https://img.example.test/r/{chain}", max_redirects=max_redirects)
    assert type(error) is ImageRedirectLimitError
    assert error.failure_kind is ImageFailureKind.REDIRECT_LIMIT
    assert len(recorder.requests) == max_redirects + 1  # the (max+1)-th redirect target was never requested
    assert_clean_error(error)


@pytest.mark.parametrize("location", [None, "", "   "])
def test_redirect_without_usable_location(location):
    stream = RecordingStream([b"<html>body</html>"] * 10)
    recorder = Recorder({"/poster.jpg": redirect(location, 302, stream)})
    error = fetch_error(recorder)
    assert type(error) is ImageRedirectError and error.reason is None
    assert error.failure_kind is ImageFailureKind.TRANSPORT_ERROR
    assert stream.pulled == 0  # redirect body is never treated as (or read as) an image
    assert len(recorder.requests) == 1


@pytest.mark.parametrize(
    ("location", "reason"),
    [
        ("http://127.0.0.1/x", UrlRejectionReason.NON_GLOBAL_IP),
        ("http://localhost/x.jpg", UrlRejectionReason.LOCALHOST),
        ("http://cdn.localhost/x.jpg", UrlRejectionReason.LOCALHOST),
        ("http://10.0.0.7/x.jpg", UrlRejectionReason.NON_GLOBAL_IP),
        ("http://192.168.1.1/x.jpg", UrlRejectionReason.NON_GLOBAL_IP),
        ("http://169.254.169.254/latest/meta-data/", UrlRejectionReason.NON_GLOBAL_IP),
        ("http://[::1]/x.jpg", UrlRejectionReason.NON_GLOBAL_IP),
        ("//127.0.0.1/x.jpg", UrlRejectionReason.NON_GLOBAL_IP),
        ("http://2130706433/x.jpg", UrlRejectionReason.NUMERIC_HOST),
        ("file:///etc/passwd", UrlRejectionReason.UNSUPPORTED_SCHEME),
        ("data:image/jpeg;base64,/9j/", UrlRejectionReason.UNSUPPORTED_SCHEME),
        ("ftp://cdn.example.test/x.jpg", UrlRejectionReason.UNSUPPORTED_SCHEME),
        ("https://user:pass@cdn.example.test/x.jpg", UrlRejectionReason.USERINFO),
        ("https://exa mple.test/x.jpg", UrlRejectionReason.WHITESPACE_OR_CONTROL),
    ],
)
def test_unsafe_redirect_target_is_never_requested(location, reason):
    recorder = Recorder(lambda request: redirect(location) if request.url.path == "/poster.jpg" else httpx.Response(200))
    error = fetch_error(recorder)
    assert type(error) is ImageRedirectError
    assert error.reason is reason
    assert error.failure_kind is ImageUrlError(reason).failure_kind
    assert recorder.urls == [URL]  # the unsafe second hop was never sent
    assert_clean_error(error)


def test_unsafe_redirect_later_in_chain_stops_before_request():
    recorder = Recorder(
        {
            "/poster.jpg": redirect("https://cdn.example.test/hop1.jpg"),
            "/hop1.jpg": redirect("http://192.168.0.1/internal.jpg"),
        }
    )
    error = fetch_error(recorder)
    assert type(error) is ImageRedirectError and error.reason is UrlRejectionReason.NON_GLOBAL_IP
    assert recorder.urls == [URL, "https://cdn.example.test/hop1.jpg"]


def test_malformed_location_is_typed_redirect_error():
    recorder = Recorder({"/poster.jpg": redirect("http://[::1")})
    error = fetch_error(recorder)
    assert type(error) is ImageRedirectError
    assert error.reason in (None, UrlRejectionReason.MALFORMED)
    assert len(recorder.requests) == 1


def test_initial_unsafe_url_fails_before_any_request():
    recorder = Recorder(lambda request: httpx.Response(200, content=JPEG))
    for url in ("http://127.0.0.1/a.jpg", "file:///etc/passwd", "https://u:p@example.test/a.jpg", "/rel.jpg"):
        with pytest.raises(ImageUrlError):
            run(fetch(recorder, url=url))
    assert recorder.requests == []


def test_no_automatic_redirect_follow_by_httpx():
    client = HttpxImageClient(transport=httpx.MockTransport(lambda r: httpx.Response(200)))
    try:
        assert client._client.follow_redirects is False
        assert client._client.trust_env is False
    finally:
        run(client.aclose())


# --- 18-23: size bound ------------------------------------------------------------------------------


def test_exactly_max_bytes_accepted():
    stream = RecordingStream([b"a" * 400, b"b" * 400, b"c" * 200])
    recorder = Recorder({"/poster.jpg": httpx.Response(200, stream=stream)})
    assert len(run(fetch(recorder, max_bytes=1000)).content) == 1000


def test_max_bytes_plus_one_rejected():
    stream = RecordingStream([b"a" * 400, b"b" * 400, b"c" * 201])
    recorder = Recorder({"/poster.jpg": httpx.Response(200, stream=stream)})
    error = fetch_error(recorder, max_bytes=1000)
    assert type(error) is ImageResponseTooLargeError
    assert error.failure_kind is ImageFailureKind.TOO_LARGE
    assert_clean_error(error)


def test_stream_stops_at_cap_and_remaining_chunks_are_never_pulled():
    stream = RecordingStream([b"x" * 100] * 1000)  # 100 KB body, cap 1 KB
    recorder = Recorder({"/poster.jpg": httpx.Response(200, stream=stream)})
    assert type(fetch_error(recorder, max_bytes=1000)) is ImageResponseTooLargeError
    assert stream.pulled == 11  # 10 chunks fit exactly, the 11th crosses the cap, nothing after
    assert stream.closed


def test_large_content_length_rejected_before_reading_body():
    stream = RecordingStream([b"x" * 10])
    recorder = Recorder({"/poster.jpg": httpx.Response(200, headers={"Content-Length": "5000"}, stream=stream)})
    assert type(fetch_error(recorder, max_bytes=1000)) is ImageResponseTooLargeError
    assert stream.pulled == 0


def test_huge_content_length_digit_string_is_rejected_without_int_parse():
    stream = RecordingStream([b"x"])
    recorder = Recorder({"/poster.jpg": httpx.Response(200, headers={"Content-Length": "9" * 6000}, stream=stream)})
    assert type(fetch_error(recorder, max_bytes=1000)) is ImageResponseTooLargeError
    assert stream.pulled == 0


def test_content_length_equal_to_cap_is_not_early_rejected():
    recorder = Recorder({"/poster.jpg": httpx.Response(200, headers={"Content-Length": "0001000"},
                                                       stream=RecordingStream([b"y" * 1000]))})
    assert len(run(fetch(recorder, max_bytes=1000)).content) == 1000


def test_lying_small_content_length_still_bounded_by_actual_stream():
    stream = RecordingStream([b"x" * 100] * 100)
    recorder = Recorder({"/poster.jpg": httpx.Response(200, headers={"Content-Length": "10"}, stream=stream)})
    assert type(fetch_error(recorder, max_bytes=1000)) is ImageResponseTooLargeError
    assert stream.pulled == 11


def test_missing_content_length_uses_stream_counter():
    ok = Recorder({"/poster.jpg": httpx.Response(200, stream=RecordingStream([b"x" * 500, b"y" * 500]))})
    assert len(run(fetch(ok, max_bytes=1000)).content) == 1000
    big = RecordingStream([b"x" * 500] * 10)
    over = Recorder({"/poster.jpg": httpx.Response(200, stream=big)})
    assert type(fetch_error(over, max_bytes=1000)) is ImageResponseTooLargeError
    assert big.pulled == 3


@pytest.mark.parametrize("value", ["abc", "-5", "+5", "1e3", "10, 20", "0x10", "", " 12 34 "])
def test_malformed_content_length_is_ignored_not_crashing(value):
    ok = Recorder({"/poster.jpg": httpx.Response(200, headers={"Content-Length": value},
                                                 stream=RecordingStream([b"z" * 50]))})
    assert run(fetch(ok, max_bytes=1000)).content == b"z" * 50
    big = RecordingStream([b"z" * 600] * 5)
    over = Recorder({"/poster.jpg": httpx.Response(200, headers={"Content-Length": value}, stream=big)})
    assert type(fetch_error(over, max_bytes=1000)) is ImageResponseTooLargeError
    assert big.pulled == 2


def test_compressed_content_encoding_is_refused_not_decoded():
    stream = RecordingStream([b"\x1f\x8b" + b"x" * 100])
    recorder = Recorder({"/poster.jpg": httpx.Response(200, headers={"Content-Encoding": "gzip"}, stream=stream)})
    assert type(fetch_error(recorder)) is ImageTransportError
    assert stream.pulled == 0


# --- 24-29: deadline, error mapping, cancellation -----------------------------------------------------


def test_total_deadline_covers_redirect_chain_not_reset_per_hop():
    async def route(request: httpx.Request) -> httpx.Response:
        await asyncio.sleep(0.12)
        n = int(request.url.path.rsplit("/", 1)[1])
        return httpx.Response(200, content=JPEG) if n == 0 else redirect(f"/r/{n - 1}")

    recorder = Recorder(route)
    # every single hop (0.12 s) is far below the deadline; six hops (0.72 s) are not
    error = fetch_error(recorder, url="https://img.example.test/r/5", deadline_seconds=0.4, max_redirects=5)
    assert type(error) is ImageTimeoutError
    assert error.failure_kind is ImageFailureKind.TIMEOUT
    assert len(recorder.requests) <= 4
    assert_clean_error(error)


def test_total_deadline_covers_body_streaming():
    stream = RecordingStream([b"x" * 10] * 100, delay=0.02)  # 2 s of body, each chunk quick
    recorder = Recorder({"/poster.jpg": httpx.Response(200, stream=stream)})
    error = fetch_error(recorder, deadline_seconds=0.25)
    assert type(error) is ImageTimeoutError
    assert stream.pulled < 100


def test_generous_deadline_allows_slow_but_finite_chain():
    async def route(request: httpx.Request) -> httpx.Response:
        await asyncio.sleep(0.01)
        n = int(request.url.path.rsplit("/", 1)[1])
        return httpx.Response(200, content=JPEG) if n == 0 else redirect(f"/r/{n - 1}")

    assert run(fetch(Recorder(route), url="https://img.example.test/r/3", deadline_seconds=5)).content == JPEG


def _raising(exc_factory):
    def handler(request: httpx.Request):
        raise exc_factory(request)

    return handler


@pytest.mark.parametrize(
    ("factory", "expected"),
    [
        (lambda r: httpx.ReadTimeout(f"read timed out {URL}", request=r), ImageTimeoutError),
        (lambda r: httpx.ConnectTimeout(f"connect timed out {URL}", request=r), ImageTimeoutError),
        (lambda r: httpx.PoolTimeout(f"pool {URL}", request=r), ImageTimeoutError),
        (lambda r: httpx.WriteTimeout(f"write {URL}", request=r), ImageTimeoutError),
        (lambda r: httpx.ConnectError(f"[Errno 11001] getaddrinfo failed {URL}", request=r), ImageConnectionError),
        (lambda r: httpx.ReadError(f"reset {URL}", request=r), ImageConnectionError),
        (lambda r: httpx.RemoteProtocolError(f"protocol {URL}", request=r), ImageConnectionError),
        (lambda r: httpx.ProxyError(f"proxy {URL}", request=r), ImageConnectionError),
        (lambda r: httpx.UnsupportedProtocol(f"proto {URL}", request=r), ImageTransportError),
        (lambda r: RuntimeError(f"surprise {URL}"), ImageTransportError),
        (lambda r: ValueError(f"surprise {URL}"), ImageTransportError),
    ],
)
def test_library_and_unexpected_exceptions_are_mapped_and_not_leaked(factory, expected):
    error = fetch_error(_raising(factory))
    assert type(error) is expected
    assert_clean_error(error)


def test_mid_stream_read_error_maps_to_connection_error():
    stream = RecordingStream([b"x" * 10] * 10, fail_after=3)
    recorder = Recorder({"/poster.jpg": httpx.Response(200, stream=stream)})
    error = fetch_error(recorder)
    assert type(error) is ImageConnectionError
    assert stream.pulled == 3
    assert_clean_error(error)


def test_connection_failure_is_not_retried():
    def down(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down", request=request)

    recorder = Recorder(down)
    assert type(fetch_error(recorder)) is ImageConnectionError
    assert len(recorder.requests) == 1


def test_caller_cancellation_propagates_unchanged():
    started = asyncio.Event()

    async def route(request: httpx.Request) -> httpx.Response:
        started.set()
        await asyncio.sleep(3600)
        return httpx.Response(200)

    async def scenario():
        task = asyncio.create_task(fetch(Recorder(route), deadline_seconds=3600))
        await started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    run(scenario())


class _Fatal(BaseException):
    pass


@pytest.mark.parametrize("fatal", [_Fatal, KeyboardInterrupt])
def test_fatal_base_exceptions_are_not_mapped(fatal):
    def handler(request):
        raise fatal()

    with pytest.raises(fatal):
        run(fetch(handler))


# --- 30-32: lifecycle ------------------------------------------------------------------------------


def test_closed_client_fails_typed_and_sends_nothing():
    recorder = Recorder(lambda request: httpx.Response(200, content=JPEG))

    async def scenario():
        client = HttpxImageClient(transport=httpx.MockTransport(recorder))
        await client.aclose()
        await client.aclose()  # idempotent
        assert client.closed
        with pytest.raises(ImageClientClosedError) as info:
            await client.get(URL, **DEFAULTS)
        assert_clean_error(info.value)
        with pytest.raises(ImageClientClosedError):
            async with client:
                pass

    run(scenario())
    assert recorder.requests == []


def test_context_manager_closes_client():
    async def scenario():
        async with HttpxImageClient(transport=httpx.MockTransport(lambda r: httpx.Response(200))) as client:
            assert not client.closed
        assert client.closed
        with pytest.raises(ImageClientClosedError):
            await client.get(URL, **DEFAULTS)

    run(scenario())


def test_one_async_client_reused_across_many_gets(monkeypatch):
    created: list[object] = []
    real = httpx.AsyncClient

    class CountingAsyncClient(real):
        def __init__(self, *args, **kwargs):
            created.append(self)
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(transport_module.httpx, "AsyncClient", CountingAsyncClient)
    recorder = Recorder(lambda request: httpx.Response(200, content=JPEG))

    async def scenario():
        async with HttpxImageClient(transport=httpx.MockTransport(recorder)) as client:
            inner = client._client
            for i in range(5):
                assert (await client.get(f"https://img.example.test/{i}.jpg", **DEFAULTS)).content == JPEG
            assert client._client is inner

    assert created == []  # importing / monkeypatching created nothing
    run(scenario())
    assert len(created) == 1
    assert len(recorder.requests) == 5


def test_construction_sends_no_request():
    recorder = Recorder(lambda request: httpx.Response(200))
    client = HttpxImageClient(transport=httpx.MockTransport(recorder))
    run(client.aclose())
    assert recorder.requests == []


def test_constructor_rejects_non_transport():
    with pytest.raises(ImageInputError):
        HttpxImageClient(transport=object())  # type: ignore[arg-type]


def test_client_satisfies_protocol():
    client: ImageHttpClient = HttpxImageClient(transport=httpx.MockTransport(lambda r: httpx.Response(200)))
    run(client.aclose())


@pytest.mark.parametrize(
    "overrides",
    [
        {"deadline_seconds": True}, {"deadline_seconds": 0}, {"deadline_seconds": -1.0},
        {"deadline_seconds": float("nan")}, {"deadline_seconds": float("inf")}, {"deadline_seconds": "5"},
        {"max_redirects": True}, {"max_redirects": -1}, {"max_redirects": 1.0},
        {"max_bytes": 0}, {"max_bytes": False}, {"max_bytes": 10.0},
    ],
)
def test_get_arguments_are_validated_before_any_request(overrides):
    recorder = Recorder(lambda request: httpx.Response(200, content=JPEG))
    with pytest.raises(ImageInputError):
        run(fetch(recorder, **overrides))
    assert recorder.requests == []


# --- request hygiene ----------------------------------------------------------------------------


def test_only_fixed_headers_are_sent_and_cookies_never_replayed(monkeypatch):
    monkeypatch.setenv("HTTP_PROXY", "http://proxy.invalid:1")
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy.invalid:1")
    recorder = Recorder(
        lambda request: httpx.Response(200, headers={"Set-Cookie": f"sid={SECRET}; Path=/"}, content=JPEG)
    )

    async def scenario():
        async with HttpxImageClient(transport=httpx.MockTransport(recorder)) as client:
            await client.get(URL, **DEFAULTS)
            await client.get(URL, **DEFAULTS)

    run(scenario())
    assert len(recorder.requests) == 2  # env proxies ignored: both reached the mock transport
    expected = {name.lower(): value for name, value in IMAGE_REQUEST_HEADERS}
    for request in recorder.requests:
        sent = {k.lower(): v for k, v in request.headers.items()}
        assert "cookie" not in sent and "authorization" not in sent
        assert {k: v for k, v in sent.items() if k != "host"} == expected


def test_get_accepts_no_caller_headers_or_credentials():
    client = HttpxImageClient(transport=httpx.MockTransport(lambda r: httpx.Response(200)))
    try:
        for extra in ({"headers": {"Cookie": "a=b"}}, {"auth": ("u", "p")}, {"cookies": {"a": "b"}}):
            with pytest.raises(TypeError):
                run(client.get(URL, **DEFAULTS, **extra))
    finally:
        run(client.aclose())


# --- content type -------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        (None, None),
        ("image/jpeg", "image/jpeg"),
        ("  IMAGE/JPEG ; charset=binary", "IMAGE/JPEG"),
        ("text/html; charset=utf-8", "text/html"),  # extracted, not judged
        ("application/octet-stream", "application/octet-stream"),
        ("", None),
        (";", None),
        ("image/" + "x" * 200, None),
        ("image/jp eg", None),
    ],
)
def test_content_type_is_extracted_without_policy(header, expected):
    headers = {} if header is None else {"Content-Type": header}
    recorder = Recorder({"/poster.jpg": httpx.Response(200, headers=headers, content=b"\x00\x01")})
    assert run(fetch(recorder)).content_type == expected


# --- 33-35: response / error graph --------------------------------------------------------------


def test_response_graph_contains_only_builtin_values():
    recorder = Recorder(
        {"/poster.jpg": redirect("/b.jpg"),
         "/b.jpg": httpx.Response(200, headers={"Content-Type": "image/jpeg", "X-Secret": SECRET}, content=JPEG)}
    )
    response = run(fetch(recorder))
    assert {f.name for f in dataclasses.fields(ImageHttpResponse)} == {"status_code", "content_type", "content"}
    assert not hasattr(response, "__dict__")
    for referent in gc.get_referents(response):
        assert type(referent) in (int, str, bytes, type(None), type), type(referent)
    assert SECRET not in repr(response)
    with pytest.raises(dataclasses.FrozenInstanceError):
        response.content = b""  # type: ignore[misc]


@pytest.mark.parametrize(
    "kwargs",
    [
        dict(status_code=True, content_type=None, content=b""),
        dict(status_code=200.0, content_type=None, content=b""),
        dict(status_code=99, content_type=None, content=b""),
        dict(status_code=200, content_type=b"image/jpeg", content=b""),
        dict(status_code=200, content_type=None, content=bytearray(b"x")),
        dict(status_code=200, content_type=None, content=memoryview(b"x")),
        dict(status_code=200, content_type=None, content="x"),
        dict(status_code=404, content_type=None, content=b"<html>"),
    ],
)
def test_response_model_invariants(kwargs):
    with pytest.raises(ImageModelError):
        ImageHttpResponse(**kwargs)


def test_response_model_rejects_str_and_bytes_subclasses():
    class S(str):
        pass

    class B(bytes):
        pass

    with pytest.raises(ImageModelError):
        ImageHttpResponse(status_code=200, content_type=S("image/jpeg"), content=b"")
    with pytest.raises(ImageModelError):
        ImageHttpResponse(status_code=200, content_type=None, content=B(b"x"))


def test_error_hierarchy_and_failure_kinds():
    assert issubclass(ImageTransportError, ImageError)
    for cls, kind in [
        (ImageTransportError, ImageFailureKind.TRANSPORT_ERROR),
        (ImageTimeoutError, ImageFailureKind.TIMEOUT),
        (ImageConnectionError, ImageFailureKind.CONNECTION_ERROR),
        (ImageRedirectLimitError, ImageFailureKind.REDIRECT_LIMIT),
        (ImageResponseTooLargeError, ImageFailureKind.TOO_LARGE),
        (ImageClientClosedError, ImageFailureKind.TRANSPORT_ERROR),
    ]:
        assert issubclass(cls, ImageTransportError)
        assert cls().failure_kind is kind
        with pytest.raises(TypeError):
            cls(f"message with {URL}")  # no caller-supplied message can be injected
    assert ImageRedirectError(UrlRejectionReason.LOCALHOST).failure_kind is ImageFailureKind.UNSAFE_URL
    assert ImageRedirectError(UrlRejectionReason.MALFORMED).failure_kind is ImageFailureKind.INVALID_URL


# --- R1 / P4-C5-R-01: cleanup exceptions stay inside the transport error boundary -------------------

SECRET_EXCEPTION_TEXT = "SECRET_EXCEPTION_TEXT"
TOKEN_URL = "https://example.com/x.jpg?token=SUPERSECRET"
R1_LEAKS = (SECRET_EXCEPTION_TEXT, "SUPERSECRET", "token=", "example.com", "x.jpg", "httpx", "CloseError",
            "ReadError", "<Request", "<Response")  # httpx object reprs (the types are checked in the graph walk)


def _close_error() -> Exception:
    return httpx.CloseError(f"{SECRET_EXCEPTION_TEXT} {TOKEN_URL}", request=httpx.Request("GET", TOKEN_URL))


class CleanupFailingStream(httpx.AsyncByteStream):
    """A response body whose ``aclose`` raises ``close_exc``. ``primary`` (if given) is raised
    by the iterator after ``fail_after`` chunks; ``hang`` makes the body block after its chunks."""

    def __init__(self, chunks, close_exc, *, primary=None, fail_after=0, hang=False):
        self.chunks = list(chunks)
        self.close_exc = close_exc
        self.primary = primary
        self.fail_after = fail_after
        self.hang = hang
        self.pulled = 0
        self.close_calls = 0

    def __aiter__(self):
        return self

    async def __anext__(self) -> bytes:
        if self.primary is not None and self.pulled >= self.fail_after:
            raise self.primary
        if self.pulled < len(self.chunks):
            self.pulled += 1
            return self.chunks[self.pulled - 1]
        if self.hang:
            await asyncio.sleep(3600)
        raise StopAsyncIteration

    async def aclose(self) -> None:
        self.close_calls += 1
        raise self.close_exc


def _walk_error(error: BaseException) -> list[object]:
    """Everything reachable from a raised error except its own ``__traceback__``."""
    found, stack, seen = [], [error], set()
    while stack:
        obj = stack.pop()
        if id(obj) in seen:
            continue
        seen.add(id(obj))
        found.append(obj)
        if isinstance(obj, BaseException):
            stack.extend(obj.args)
            stack.extend(v for v in (obj.__cause__, obj.__context__) if v is not None)
            stack.extend(getattr(obj, "__dict__", {}).values())
            stack.extend(getattr(obj, "__notes__", []))
            if hasattr(obj, "reason"):
                stack.append(obj.reason)
        elif isinstance(obj, (tuple, list)):
            stack.extend(obj)
    return found


def assert_r1_clean(error: BaseException) -> None:
    assert_clean_error(error)
    assert error.__cause__ is None and error.__context__ is None
    rendered = " ".join([str(error), repr(error), repr(error.args)])
    for leaked in R1_LEAKS:
        assert leaked not in rendered, leaked
    for obj in _walk_error(error):
        assert not isinstance(obj, (httpx.Request, httpx.Response, httpx.HTTPError)), type(obj)
        assert obj is error or not isinstance(obj, BaseException), type(obj)
        if isinstance(obj, str):
            assert SECRET_EXCEPTION_TEXT not in obj and "SUPERSECRET" not in obj
    # the raise point is get() itself: no frame of the worker / cleanup path, and no frame local
    # anywhere in the traceback holds an httpx exception, request or response
    tb = error.__traceback__
    while tb is not None:
        assert tb.tb_frame.f_code.co_name not in ("_follow", "_read_body", "_cleanup", "_response_outcome")
        for value in tb.tb_frame.f_locals.values():
            assert not isinstance(value, (httpx.Request, httpx.Response, httpx.HTTPError)), type(value)
        tb = tb.tb_next


def _single(stream: CleanupFailingStream, status: int = 200, headers=None) -> Recorder:
    return Recorder({"/poster.jpg": httpx.Response(status, headers=headers or {}, stream=stream)})


@pytest.mark.parametrize("status", [404, 500, 204])
def test_r1_non_200_cleanup_httpx_close_error_is_connection_error(status):
    stream = CleanupFailingStream([b"<html>error page</html>"], _close_error())
    error = fetch_error(_single(stream, status))
    assert type(error) is ImageConnectionError
    assert stream.pulled == 0 and stream.close_calls >= 1
    assert_r1_clean(error)


def test_r1_non_200_cleanup_ordinary_exception_is_transport_error():
    stream = CleanupFailingStream([b"x"], RuntimeError(f"{SECRET_EXCEPTION_TEXT} {TOKEN_URL}"))
    error = fetch_error(_single(stream, 404))
    assert type(error) is ImageTransportError
    assert_r1_clean(error)


@pytest.mark.parametrize(
    ("close_exc", "expected"),
    [(_close_error, ImageConnectionError), (lambda: ValueError(f"{SECRET_EXCEPTION_TEXT} {TOKEN_URL}"),
                                             ImageTransportError)],
    ids=["httpx-CloseError", "ValueError"],
)
def test_r1_200_success_cleanup_error_fails_closed_typed(close_exc, expected):
    stream = CleanupFailingStream([JPEG[:100], JPEG[100:]], close_exc())
    error = fetch_error(_single(stream, 200, {"Content-Type": "image/jpeg"}))
    assert type(error) is expected
    assert stream.pulled == 2 and stream.close_calls >= 1
    assert_r1_clean(error)


@pytest.mark.parametrize("declared", [False, True])
def test_r1_too_large_cleanup_error_keeps_primary_too_large(declared):
    stream = CleanupFailingStream([b"x" * 10] * 5, _close_error())
    headers = {"Content-Length": "50"} if declared else {}
    error = fetch_error(_single(stream, 200, headers), max_bytes=25)
    assert type(error) is ImageResponseTooLargeError
    assert stream.pulled <= 3 and stream.close_calls >= 1
    assert_r1_clean(error)


def test_r1_mid_stream_read_error_plus_cleanup_error_keeps_primary_connection_error():
    read = httpx.ReadError(f"{SECRET_EXCEPTION_TEXT} {TOKEN_URL}", request=httpx.Request("GET", TOKEN_URL))
    stream = CleanupFailingStream([b"x"] * 5, RuntimeError(SECRET_EXCEPTION_TEXT), primary=read, fail_after=2)
    error = fetch_error(_single(stream))
    assert type(error) is ImageConnectionError
    assert_r1_clean(error)


def test_r1_timeout_during_body_with_cleanup_error_is_timeout():
    stream = CleanupFailingStream([b"x"], _close_error(), hang=True)
    error = fetch_error(_single(stream), deadline_seconds=0.2)
    assert type(error) is ImageTimeoutError
    assert stream.close_calls >= 1
    assert_r1_clean(error)


def test_r1_timeout_during_body_with_cleanup_ordinary_exception_is_timeout():
    stream = CleanupFailingStream([b"x"], RuntimeError(SECRET_EXCEPTION_TEXT), hang=True)
    error = fetch_error(_single(stream, 200), deadline_seconds=0.2)
    assert type(error) is ImageTimeoutError
    assert_r1_clean(error)


def test_r1_caller_cancellation_with_cleanup_error_propagates_cancellation():
    stream = CleanupFailingStream([b"x"], _close_error(), hang=True)

    async def scenario():
        task = asyncio.create_task(fetch(_single(stream), deadline_seconds=3600))
        while stream.pulled < 1:
            await asyncio.sleep(0.01)
        await asyncio.sleep(0.02)
        task.cancel()
        with pytest.raises(asyncio.CancelledError) as info:
            await task
        return info.value

    cancelled = run(scenario())
    assert type(cancelled) is asyncio.CancelledError
    assert stream.close_calls >= 1


class _R1Fatal(BaseException):
    pass


@pytest.mark.parametrize(
    "primary_factory",
    [asyncio.CancelledError, _R1Fatal, KeyboardInterrupt, SystemExit, GeneratorExit],
    ids=["CancelledError", "custom-BaseException", "KeyboardInterrupt", "SystemExit", "GeneratorExit"],
)
@pytest.mark.parametrize("cleanup_factory", [_close_error, lambda: RuntimeError(SECRET_EXCEPTION_TEXT)],
                         ids=["httpx-CloseError", "RuntimeError"])
def test_r1_primary_cancellation_or_fatal_is_the_same_object_after_failing_cleanup(primary_factory, cleanup_factory):
    primary = primary_factory()
    stream = CleanupFailingStream([b"x"] * 3, cleanup_factory(), primary=primary, fail_after=1)

    async def scenario():
        try:
            await fetch(_single(stream), deadline_seconds=3600)
        except BaseException as exc:  # capture in the same task: identity is preserved
            return exc
        return None

    raised = run(scenario())
    assert raised is primary
    assert stream.close_calls >= 1
    assert not isinstance(raised.__context__, (httpx.HTTPError, RuntimeError))


@pytest.mark.parametrize("fatal_factory", [_R1Fatal, KeyboardInterrupt, asyncio.CancelledError])
def test_r1_cancellation_or_fatal_raised_by_cleanup_itself_is_not_swallowed_or_mapped(fatal_factory):
    fatal = fatal_factory()
    stream = CleanupFailingStream([b"<html>x</html>"], fatal)

    async def scenario():
        try:
            await fetch(_single(stream, 404), deadline_seconds=3600)
        except BaseException as exc:
            return exc
        return None

    assert run(scenario()) is fatal


def test_r1_cleanup_helper_maps_by_type_never_by_message():
    async def boom(exc):
        raise exc

    async def scenario():
        mapped = [
            await transport_module._cleanup(lambda: boom(httpx.CloseError("timed out"))),
            await transport_module._cleanup(lambda: boom(RuntimeError("connection reset / CloseError"))),
            await transport_module._cleanup(lambda: boom(httpx.ReadTimeout("x"))),
        ]
        ok = await transport_module._cleanup(lambda: asyncio.sleep(0))
        return mapped, ok

    (close, other, timeout), ok = run(scenario())
    assert type(close) is ImageConnectionError  # message says "timed out": the type decides
    assert type(other) is ImageTransportError  # message says "connection reset": the type decides
    assert type(timeout) is ImageTimeoutError
    assert ok is None
    for error in (close, other, timeout):
        assert error.__cause__ is None and error.__context__ is None and error.__traceback__ is None


def test_r1_successful_cleanup_still_returns_response_unchanged():
    class OkStream(CleanupFailingStream):
        async def aclose(self) -> None:
            self.close_calls += 1

    stream = OkStream([JPEG], None)
    response = run(fetch(_single(stream, 200, {"Content-Type": "image/jpeg"})))
    assert response.content == JPEG and response.status_code == 200 and stream.close_calls >= 1


# --- R1 / P4-C5-R-02: huge but policy-valid deadlines never leak OverflowError -------------------------


@pytest.mark.parametrize("deadline", [10**400, 10**309, 2**1024], ids=["10**400", "10**309", "2**1024"])
def test_r2_unrepresentable_int_deadline_is_typed_transport_error_and_sends_nothing(deadline):
    recorder = Recorder({"/poster.jpg": httpx.Response(200, content=JPEG)})
    with pytest.raises(ImageError) as info:
        run(fetch(recorder, deadline_seconds=deadline))
    error = info.value
    assert type(error) is ImageTransportError
    assert error.failure_kind is ImageFailureKind.TRANSPORT_ERROR
    assert not isinstance(error, (OverflowError, ValueError))
    assert recorder.requests == []
    assert_clean_error(error)
    assert error.__cause__ is None and error.__context__ is None


def test_r2_policy_domain_unchanged_huge_int_deadline_still_accepted():
    from fc2_organizer.images import ImageAcquisitionPolicy

    assert ImageAcquisitionPolicy(request_deadline_seconds=10**400).request_deadline_seconds == 10**400


def test_r2_huge_deadline_never_raises_overflow_error_at_all():
    recorder = Recorder({"/poster.jpg": httpx.Response(200, content=JPEG)})
    try:
        run(fetch(recorder, deadline_seconds=10**400))
    except OverflowError:  # pragma: no cover - the regression this guards against
        pytest.fail("OverflowError leaked from HttpxImageClient.get")
    except ImageTransportError:
        pass


@pytest.mark.parametrize("deadline", [15.0, 1, 5, 3600, 10**300, 10**308, 1e300, 1.7976931348623157e308])
def test_r2_normal_and_large_representable_deadlines_do_not_regress(deadline):
    recorder = Recorder({"/poster.jpg": httpx.Response(200, headers={"Content-Type": "image/jpeg"}, content=JPEG)})
    response = run(fetch(recorder, deadline_seconds=deadline))
    assert response.status_code == 200 and response.content == JPEG
    assert len(recorder.requests) == 1


def test_r2_deadline_delay_conversion_is_type_based():
    assert transport_module._deadline_delay(15.0) == 15.0
    assert transport_module._deadline_delay(1) == 1.0 and type(transport_module._deadline_delay(1)) is float
    assert transport_module._deadline_delay(10**308) == 1e308
    assert transport_module._deadline_delay(10**400) is None
