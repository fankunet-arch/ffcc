"""Phase 3 C3-E02 (closes C2 review L1): no body-decoding failure may cross the transport boundary as a bare stdlib exception.

A server picks the ``charset`` of its own ``Content-Type``. ``bytes.decode`` on some registered codecs raises
``LookupError`` ("is not a text encoding": rot13, base64, hex, zlib, bz2, uu, quopri), ``UnicodeError``
(idna, undefined, punycode) or, for a malformed name, ``ValueError``. Before C3 that final ``decode`` sat outside
every ``try``, so the exception escaped as itself, bypassed the ``DECODE_ERROR`` retry policy and was only caught much
later by the engine's last-resort isolation as ``ADAPTER_EXCEPTION``.

PRODUCTION path: real ``HttpxTransport`` over ``httpx.MockTransport`` (and, for the end-to-end block, the real adapters
and engine). Where Python/httpx behave differently from expectation the *observed* behaviour is what is asserted; the
single invariant is that the transport boundary is uniform.
"""

from __future__ import annotations

import asyncio

import httpx
import pytest

from fc2_metadata_core.aggregation import AggregateStatus, AggregationConfig, MultiSourceEngine, RetryPolicy, SourceConfig
from fc2_metadata_core.http.client import HttpDecodingError, HttpResponseTooLargeError, HttpTransportError
from fc2_metadata_core.http.httpx_client import HttpxTransport
from fc2_metadata_core.models.source_result import SourceErrorKind, SourceStatus
from fc2_metadata_core.sources.adapters import build_default_registry

from support.source_fixtures import load_fixture

JAPANESE = "こんにちは、FC2 作品タイトル"
K = SourceErrorKind
S = SourceStatus

# reviewer-listed + the same family (every non-text or unusable codec the registry offers)
NON_TEXT_OR_UNUSABLE = [
    "rot13", "base64", "hex", "zlib", "bz2", "idna", "undefined",  # named in the C2 review
    "uu", "quopri", "punycode", "base64_codec", "zlib_codec", "bz2_codec", "hex_codec", "rot_13",
    "utf-8\x00x",  # embedded NUL: malformed charset name
]


def transport_get(handler, content_type: str | None, *, body: bytes | None = None):
    def wrapped(request: httpx.Request) -> httpx.Response:
        headers = {"Content-Type": content_type} if content_type is not None else {}
        return httpx.Response(200, content=JAPANESE.encode("shift_jis") if body is None else body, headers=headers)

    async def scenario():
        async with HttpxTransport(transport=httpx.MockTransport(handler or wrapped)) as client:
            return await client.get("https://mock.invalid/x")

    return asyncio.run(scenario())


# ---- transport boundary ---------------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("charset", NON_TEXT_OR_UNUSABLE)
def test_a_non_text_or_unusable_charset_raises_http_decoding_error_and_nothing_else(charset):
    try:
        transport_get(None, f"text/html; charset={charset}")
    except HttpDecodingError as exc:
        assert isinstance(exc, HttpTransportError)
        assert isinstance(exc.__cause__, (LookupError, ValueError)), "the stdlib cause is chained, not leaked"
    else:  # pragma: no cover - would mean the codec turned out to be decodable on this interpreter
        pytest.fail(f"charset={charset!r} produced a response instead of HttpDecodingError")


@pytest.mark.parametrize("charset", NON_TEXT_OR_UNUSABLE)
def test_no_bare_stdlib_exception_type_ever_crosses_the_transport_boundary(charset):
    try:
        transport_get(None, f"text/html; charset={charset}")
    except BaseException as exc:  # noqa: BLE001 - the whole point: classify whatever comes out
        assert isinstance(exc, HttpTransportError), f"bare {type(exc).__name__} leaked for charset={charset!r}"
        assert not isinstance(exc, (LookupError, UnicodeError, ValueError))


def test_the_decoding_error_message_is_bounded_and_names_the_charset_not_the_body():
    with pytest.raises(HttpDecodingError) as info:
        transport_get(None, "text/html; charset=rot13", body=b"SECRET-BODY-CONTENT")
    message = str(info.value)
    assert "rot13" in message and "SECRET-BODY-CONTENT" not in message and len(message) < 300


@pytest.mark.parametrize(
    "content_type, expected",
    [
        ("text/html; charset=utf-8", None),  # None -> compare below against a UTF-8 payload
        ("text/html; charset=shift_jis", JAPANESE),
        ("text/html; charset=SHIFT_JIS", JAPANESE),
        ('text/html; charset="shift_jis"', JAPANESE),
        ("text/html; charset=cp932", JAPANESE),
        ("text/html; charset=euc-jp", None),
    ],
)
def test_legitimate_charsets_still_decode_exactly_as_before(content_type, expected):
    if expected is None:
        codec = content_type.split("=")[1].strip('"')
        body = JAPANESE.encode(codec)
        assert transport_get(None, content_type, body=body).text == JAPANESE
    else:
        assert transport_get(None, content_type).text == expected


@pytest.mark.parametrize("content_type", [None, "text/html", "text/html; charset=", "text/html; charset=nonsense", "text/html; charset=" + "a" * 5000])
def test_a_missing_empty_or_merely_unknown_charset_is_not_an_error_httpx_falls_back_to_utf8(content_type):
    response = transport_get(None, content_type, body=JAPANESE.encode("utf-8"))
    assert response.status_code == 200 and response.text == JAPANESE


def test_undecodable_bytes_under_a_real_text_charset_are_replaced_not_raised():
    response = transport_get(None, "text/html; charset=utf-8", body=b"ok \xff\xfe broken")
    assert response.text.startswith("ok ") and "�" in response.text


def test_a_decoding_failure_never_hides_a_size_limit_or_other_transport_error():
    async def scenario():
        async with HttpxTransport(max_response_bytes=10, transport=httpx.MockTransport(
            lambda r: httpx.Response(200, content=b"x" * 100, headers={"Content-Type": "text/html; charset=rot13"})
        )) as client:
            await client.get("https://mock.invalid/x")

    with pytest.raises(HttpResponseTooLargeError):
        asyncio.run(scenario())


# ---- end to end: DECODE_ERROR, retried per the C2 contract, never ADAPTER_EXCEPTION ---------------------------------------------------------------


BASE = "https://mock.invalid"
FAST = RetryPolicy(max_attempts=2, initial_backoff_seconds=0.01)
SOURCES = {"fc2db_net": "fc2db_net/work_4979299.html", "javdb": "javdb/search_hit_4979299.html", "av123": "av123/detail_4979299.html"}


class Recorder:
    def __init__(self, *outcomes):
        self.outcomes, self.count = list(outcomes), 0

    def __call__(self, request):
        self.count += 1
        return self.outcomes.pop(0) if len(self.outcomes) > 1 else self.outcomes[0]


def lookup(handler, source_id):
    config = AggregationConfig.create([SourceConfig(source_id, base_url=BASE, deadline_seconds=5.0)], retry_policy=FAST)

    async def scenario():
        async with HttpxTransport(transport=httpx.MockTransport(handler)) as transport:
            return await MultiSourceEngine(config, build_default_registry(), transport).aggregate("FC2-4979299")

    return asyncio.run(scenario())


def bad_charset(charset):
    return httpx.Response(200, content=b"<html>x</html>", headers={"Content-Type": f"text/html; charset={charset}"})


@pytest.mark.parametrize("source_id", SOURCES)
@pytest.mark.parametrize("charset", ["rot13", "base64", "hex", "zlib", "bz2", "idna", "undefined", "utf-8\x00x"])
def test_a_bad_charset_is_network_error_decode_error_and_retried_once_never_adapter_exception(source_id, charset):
    handler = Recorder(bad_charset(charset))
    result = lookup(handler, source_id)
    final = result.result_for(source_id)
    assert (final.status, final.error_kind) == (S.NETWORK_ERROR, K.DECODE_ERROR)
    assert final.error_kind is not K.ADAPTER_EXCEPTION
    assert handler.count == 2, "DECODE_ERROR is retryable under the C2 default policy: exactly one retry"
    assert [(a.status, a.error_kind) for a in result.trace_for(source_id).attempts] == [(S.NETWORK_ERROR, K.DECODE_ERROR)] * 2


@pytest.mark.parametrize("source_id", SOURCES)
def test_a_bad_charset_followed_by_a_clean_page_recovers_as_success(source_id):
    handler = Recorder(bad_charset("rot13"), httpx.Response(200, text=load_fixture(SOURCES[source_id])))
    result = lookup(handler, source_id)
    assert result.status is AggregateStatus.SUCCESS and handler.count == 2
    assert result.trace_for(source_id).attempts[0].error_kind is K.DECODE_ERROR
