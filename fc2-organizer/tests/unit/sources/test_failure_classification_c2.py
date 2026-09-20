"""C2 failure classification below the aggregation layer (P2-R-12): transport exceptions,
HTTP status mapping, and the unchanged legacy coarse helpers."""

from __future__ import annotations

import asyncio
import gzip

import httpx
import pytest

from fc2_metadata_core.errors import SourceResultContractError
from fc2_metadata_core.http.client import (
    HttpConnectionError,
    HttpDecodingError,
    HttpRedirectLimitError,
    HttpResponseTooLargeError,
    HttpTimeoutError,
    HttpTransportError,
)
from fc2_metadata_core.http.httpx_client import HttpxTransport
from fc2_metadata_core.models.source_result import SourceErrorKind, SourceStatus
from fc2_metadata_core.sources import (
    classify_transport_error,
    classify_transport_failure,
    transport_error_result,
    transport_failure_result,
)
from fc2_metadata_core.sources.adapters._common import classify_page_response, failure_result

from support.fake_http_client import make_response

K = SourceErrorKind
S = SourceStatus


class UnknownTransportError(HttpTransportError):
    pass


FINE = [
    (HttpTimeoutError("t"), K.TIMEOUT, S.NETWORK_ERROR),
    (HttpConnectionError("c"), K.CONNECTION_ERROR, S.NETWORK_ERROR),
    (HttpDecodingError("d"), K.DECODE_ERROR, S.NETWORK_ERROR),
    (HttpRedirectLimitError("r"), K.REDIRECT_ERROR, S.NETWORK_ERROR),
    (HttpResponseTooLargeError("l"), K.RESPONSE_TOO_LARGE, S.INVALID_RESPONSE),
    (UnknownTransportError("u"), K.NETWORK_ERROR, S.NETWORK_ERROR),
    (HttpTransportError("base"), K.NETWORK_ERROR, S.NETWORK_ERROR),
]


@pytest.mark.parametrize("exc, kind, status", FINE, ids=lambda v: type(v).__name__ if isinstance(v, Exception) else str(getattr(v, "value", v)))
def test_fine_transport_classification_table(exc, kind, status):
    assert classify_transport_failure(exc) is kind
    result = transport_failure_result("src", exc, elapsed_ms=12.5)
    assert (result.status, result.error_kind) == (status, kind)
    assert result.metadata is None and result.elapsed_ms == 12.5
    assert "src" in result.error_detail and type(exc).__name__ in result.error_detail


COARSE = [
    (HttpTimeoutError("t"), K.NETWORK_ERROR),
    (HttpConnectionError("c"), K.NETWORK_ERROR),
    (HttpDecodingError("d"), K.NETWORK_ERROR),
    (HttpRedirectLimitError("r"), K.NETWORK_ERROR),
    (HttpResponseTooLargeError("l"), K.INVALID_RESPONSE),
]


@pytest.mark.parametrize("exc, kind", COARSE, ids=lambda v: type(v).__name__ if isinstance(v, Exception) else "")
def test_the_legacy_coarse_helpers_are_unchanged_for_older_adapters(exc, kind):
    assert classify_transport_error(exc) is kind
    assert transport_error_result("src", exc).error_kind is kind


# ---- HTTP status -> (status, kind) --------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "http_status, expected",
    [
        (403, (S.BLOCKED, K.BLOCKED)),
        (404, (S.NOT_FOUND, K.NOT_FOUND)),
        (429, (S.RATE_LIMITED, K.RATE_LIMITED)),
        (499, (S.INVALID_RESPONSE, K.INVALID_RESPONSE)),
        (500, (S.INVALID_RESPONSE, K.HTTP_SERVER_ERROR)),
        (501, (S.INVALID_RESPONSE, K.HTTP_SERVER_ERROR)),
        (502, (S.INVALID_RESPONSE, K.HTTP_SERVER_ERROR)),
        (503, (S.INVALID_RESPONSE, K.HTTP_SERVER_ERROR)),
        (504, (S.INVALID_RESPONSE, K.HTTP_SERVER_ERROR)),
        (599, (S.INVALID_RESPONSE, K.HTTP_SERVER_ERROR)),
        (600, (S.INVALID_RESPONSE, K.INVALID_RESPONSE)),
        (301, (S.INVALID_RESPONSE, K.INVALID_RESPONSE)),
        (204, (S.INVALID_RESPONSE, K.INVALID_RESPONSE)),
        (400, (S.INVALID_RESPONSE, K.INVALID_RESPONSE)),
    ],
)
def test_http_status_maps_to_a_structured_kind(http_status, expected):
    result = classify_page_response("src", "FC2-1234567", make_response(status_code=http_status))
    assert result is not None and (result.status, result.error_kind) == expected


def test_a_normal_200_is_not_a_failure_and_a_challenge_header_wins_over_the_status():
    assert classify_page_response("src", "FC2-1234567", make_response(status_code=200, text="<html><title>ok</title></html>")) is None
    blocked = classify_page_response("src", "FC2-1234567", make_response(status_code=503, headers={"cf-mitigated": "challenge"}))
    assert (blocked.status, blocked.error_kind) == (S.BLOCKED, K.BLOCKED)


def test_failure_result_helper_takes_an_optional_refinement_and_still_validates_it():
    assert failure_result("s", S.INVALID_RESPONSE, "d", elapsed_ms=1.0).error_kind is K.INVALID_RESPONSE
    assert failure_result("s", S.INVALID_RESPONSE, "d", elapsed_ms=1.0, error_kind=K.HTTP_SERVER_ERROR).error_kind is K.HTTP_SERVER_ERROR
    with pytest.raises(SourceResultContractError):
        failure_result("s", S.NOT_FOUND, "d", elapsed_ms=1.0, error_kind=K.HTTP_SERVER_ERROR)


# ---- the production transport really raises HttpDecodingError ------------------------------------------------------------------------


def transport_get(handler, **kw):
    async def scenario():
        async with HttpxTransport(transport=httpx.MockTransport(handler), **kw) as client:
            return await client.get("https://mock.invalid/x")

    return asyncio.run(scenario())


@pytest.mark.parametrize("encoding, body", [("gzip", b"not gzip at all"), ("deflate", b"not deflate at all")])
def test_httpx_decoding_errors_become_http_decoding_error(encoding, body):
    with pytest.raises(HttpDecodingError) as info:
        transport_get(lambda request: httpx.Response(200, headers={"content-encoding": encoding}, content=body))
    assert isinstance(info.value.__cause__, httpx.DecodingError), "the httpx exception is chained, not leaked"
    assert not isinstance(info.value, HttpConnectionError)


def test_valid_gzip_still_decodes_and_unknown_or_missing_encoding_is_not_a_decode_error():
    good = transport_get(lambda request: httpx.Response(200, headers={"content-encoding": "gzip"}, content=gzip.compress(b"hello")))
    assert good.text == "hello"
    assert transport_get(lambda request: httpx.Response(200, headers={"content-type": "text/html; charset=nonsense"}, content=b"hi")).text == "hi"


@pytest.mark.parametrize(
    "exc_factory, expected",
    [
        (lambda: httpx.ReadTimeout("x"), HttpTimeoutError),
        (lambda: httpx.ConnectTimeout("x"), HttpTimeoutError),
        (lambda: httpx.ConnectError("x"), HttpConnectionError),
        (lambda: httpx.RemoteProtocolError("x"), HttpConnectionError),
        (lambda: httpx.ReadError("x"), HttpConnectionError),
        (lambda: httpx.TooManyRedirects("x"), HttpRedirectLimitError),
    ],
)
def test_transport_exception_mapping_is_exact_and_never_leaks_httpx_types(exc_factory, expected):
    def handler(request):
        exc = exc_factory()
        exc.request = request
        raise exc

    with pytest.raises(expected) as info:
        transport_get(handler)
    assert type(info.value) is expected


def test_oversized_declared_body_is_response_too_large():
    with pytest.raises(HttpResponseTooLargeError):
        transport_get(lambda request: httpx.Response(200, content=b"x" * 300), max_response_bytes=50)
