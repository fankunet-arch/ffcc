"""P5-C1 表 D（E7）：Amane HTTP 响应 -> Core ``HttpResponse``（头小写化、charset 矩阵、5 MiB、外来响应）。"""

from __future__ import annotations

import asyncio
import inspect

import pytest

from fc2_amane_adapter._bridge import MAX_RESPONSE_BYTES, OK_STATUSES, AmaneHttpBridge
from fc2_metadata_core.http import (
    HttpResponse,
    HttpResponseTooLargeError,
    HttpTransportError,
)
from fc2_metadata_core.http.client import HttpDecodingError
from support.amane_host_fakes import FakeHeaders, FakeResponse, FakeWebClient

URL = "https://site.example/work/1234567"


def _get(response, *, clock=None, **kwargs):
    client = FakeWebClient({URL: response})
    bridge = AmaneHttpBridge(client, **({"clock": clock} if clock else {}))
    return asyncio.run(bridge.get(URL, **kwargs)), client


def test_request_uses_only_the_frozen_keywords():
    _, client = _get(FakeResponse.html("<html></html>"), headers={"Accept": "text/html"}, timeout=7.5)
    (method, url, kwargs), = client.calls
    assert (method, url) == ("GET", URL)
    assert set(kwargs) == {"headers", "timeout", "ok_statuses"}
    assert kwargs["headers"] == {"Accept": "text/html"}
    assert kwargs["timeout"] == 7.5
    assert kwargs["ok_statuses"] == frozenset(range(300, 600)) == OK_STATUSES
    for forbidden in ("cookies", "data", "json", "use_proxy", "allow_redirects", "max_attempts"):
        assert forbidden not in kwargs


def test_no_headers_and_no_timeout_pass_none():
    _, client = _get(FakeResponse.html("x"))
    assert client.calls[0][2]["headers"] is None and client.calls[0][2]["timeout"] is None


def test_ok_statuses_covers_300_to_599_exactly():
    assert 299 not in OK_STATUSES and 300 in OK_STATUSES and 429 in OK_STATUSES and 599 in OK_STATUSES
    assert 600 not in OK_STATUSES and 200 not in OK_STATUSES


def test_bridge_satisfies_the_source_http_client_shape():
    assert inspect.iscoroutinefunction(AmaneHttpBridge.get)
    parameters = inspect.signature(AmaneHttpBridge.get).parameters
    assert parameters["headers"].kind is inspect.Parameter.KEYWORD_ONLY
    assert parameters["timeout"].kind is inspect.Parameter.KEYWORD_ONLY


@pytest.mark.parametrize("status", [200, 301, 403, 404, 429, 500, 503, 599])
def test_every_status_is_an_ordinary_response(status):
    result, _ = _get(FakeResponse.html("body", status=status, url=URL))
    assert isinstance(result, HttpResponse) and result.status_code == status and result.text == "body"


def test_final_url_and_fallback():
    final = "https://site.example/final"
    assert _get(FakeResponse.html("x", url=final))[0].url == final
    assert _get(FakeResponse.html("x", url=""))[0].url == URL
    assert _get(FakeResponse(200, b"x", None, FakeHeaders([("Content-Type", "text/html")])))[0].url == URL

    class UrlObject:
        def __str__(self):
            return "https://site.example/object"

    assert _get(FakeResponse(200, b"x", UrlObject(), FakeHeaders()))[0].url == "https://site.example/object"


def test_headers_are_lowercased_and_multi_values_joined_in_host_order():
    headers = FakeHeaders([("CF-Mitigated", "challenge"), ("Set-Cookie", "a=1"), ("set-cookie", "b=2"), ("X-A", "1")])
    result, _ = _get(FakeResponse(200, b"x", URL, headers))
    assert dict(result.headers) == {"cf-mitigated": "challenge", "set-cookie": "a=1, b=2", "x-a": "1"}


def test_elapsed_ms_is_measured_with_the_injected_clock_around_the_whole_request():
    ticks = iter([100.0, 100.25])
    result, _ = _get(FakeResponse.html("x"), clock=lambda: next(ticks))
    assert result.elapsed_ms == pytest.approx(250.0)


def test_dict_like_headers_are_supported():
    class DictHeaders(dict):
        pass

    result, _ = _get(FakeResponse(200, b"x", URL, DictHeaders({"Content-Type": "text/html", "X-Y": "z"})))
    assert dict(result.headers) == {"content-type": "text/html", "x-y": "z"}


@pytest.mark.parametrize(
    ("charset", "text"),
    [("utf-8", "日本語タイトル"), ("shift_jis", "日本語タイトル"), ("euc-jp", "日本語タイトル"), ("UTF-8", "ascii"), ('"utf-8"', "quoted")],
)
def test_charset_matrix_decodes_declared_text(charset, text):
    encoding = charset.strip('"')
    response = FakeResponse(200, text.encode(encoding), URL, FakeHeaders([("Content-Type", f"text/html; charset={charset}")]))
    assert _get(response)[0].text == text


def test_missing_charset_defaults_to_utf8_and_replaces_invalid_bytes():
    response = FakeResponse(200, b"ok \xff end", URL, FakeHeaders([("Content-Type", "text/html")]))
    assert _get(response)[0].text == "ok � end"
    assert _get(FakeResponse(200, "あ".encode(), URL, FakeHeaders()))[0].text == "あ"


def test_unknown_charset_name_falls_back_to_utf8_like_core_transport():
    response = FakeResponse(200, "あ".encode(), URL, FakeHeaders([("Content-Type", "text/html; charset=nonsense")]))
    assert _get(response)[0].text == "あ"


@pytest.mark.parametrize("charset", ["rot13", "base64", "zlib", "hex", "bz2", "idna", "undefined", "utf-8\x00x"])
def test_non_text_or_unusable_charset_is_a_decoding_error(charset):
    response = FakeResponse(200, b"hello", URL, FakeHeaders([("Content-Type", f"text/html; charset={charset}")]))
    with pytest.raises(HttpDecodingError) as excinfo:
        _get(response)
    assert charset not in str(excinfo.value) and URL not in str(excinfo.value)


def test_five_mebibyte_boundary():
    limit = MAX_RESPONSE_BYTES
    assert limit == 5 * 1024 * 1024
    at_limit = FakeResponse(200, b"a" * limit, URL, FakeHeaders())
    assert len(_get(at_limit)[0].text) == limit
    with pytest.raises(HttpResponseTooLargeError) as excinfo:
        _get(FakeResponse(200, b"a" * (limit + 1), URL, FakeHeaders()))
    assert str(excinfo.value) == f"response body exceeded {limit} byte limit"
    assert URL not in str(excinfo.value)


@pytest.mark.parametrize(
    "response",
    [
        object(),
        FakeResponse(True, b"x", URL, FakeHeaders()),
        FakeResponse("200", b"x", URL, FakeHeaders()),
        FakeResponse(None, b"x", URL, FakeHeaders()),
        FakeResponse(200, "text", URL, FakeHeaders()),
        FakeResponse(200, None, URL, FakeHeaders()),
        FakeResponse(200, b"x", URL, None),
        FakeResponse(200, b"x", URL, FakeHeaders([("a", 1)])),
        FakeResponse(200, b"x", URL, FakeHeaders([(1, "a")])),
        FakeResponse(200, b"x", URL, 5),
        FakeResponse(200, b"x", URL, object()),
    ],
)
def test_foreign_responses_become_generic_transport_errors_never_attribute_errors(response):
    with pytest.raises(HttpTransportError) as excinfo:
        _get(response)
    assert type(excinfo.value) is HttpTransportError
    assert str(excinfo.value) == "invalid host response"
