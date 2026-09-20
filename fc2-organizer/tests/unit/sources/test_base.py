"""Offline tests for the SourceAdapter contract itself (canonical-number
boundary, base_url override, identity-attribute enforcement, status/error
classification helpers)."""

from __future__ import annotations

import asyncio

import pytest

from fc2_metadata_core.errors import InvalidCanonicalNumberInputError
from fc2_metadata_core.http.client import (
    HttpConnectionError,
    HttpResponseTooLargeError,
    HttpTimeoutError,
)
from fc2_metadata_core.models.source_result import SourceErrorKind, SourceStatus
from fc2_metadata_core.sources.base import (
    SourceAdapter,
    classify_http_status,
    classify_transport_error,
    require_canonical_number,
    transport_error_result,
)

from support.fake_http_client import FakeHttpClient
from support.fake_source_adapter import FakeSourceAdapter


def run(coro):
    return asyncio.run(coro)


# --- require_canonical_number ------------------------------------------------


def test_require_canonical_number_accepts_canonical_form():
    assert require_canonical_number("FC2-1234567") == "FC2-1234567"


@pytest.mark.parametrize(
    "garbage",
    ["FC2PPV-1234567", "fc2-1234567.mp4", "SSNI-123", "", "1234567", "FC2-12"],
)
def test_require_canonical_number_rejects_non_canonical_input(garbage):
    with pytest.raises(InvalidCanonicalNumberInputError):
        require_canonical_number(garbage)


# --- classify_http_status -----------------------------------------------------


@pytest.mark.parametrize(
    "status_code,expected",
    [
        (404, SourceStatus.NOT_FOUND),
        (403, SourceStatus.BLOCKED),
        (429, SourceStatus.RATE_LIMITED),
    ],
)
def test_classify_http_status_unambiguous_codes(status_code, expected):
    assert classify_http_status(status_code) is expected


@pytest.mark.parametrize("status_code", [200, 500, 301, 401])
def test_classify_http_status_returns_none_for_ambiguous_codes(status_code):
    # 200 must never be pre-judged as success here -- the body still has to
    # be parsed and shown to meet minimum success.
    assert classify_http_status(status_code) is None


# --- classify_transport_error / transport_error_result ------------------------


def test_classify_transport_error_maps_timeout_and_connection_to_network_error():
    assert classify_transport_error(HttpTimeoutError("x")) is SourceErrorKind.NETWORK_ERROR
    assert classify_transport_error(HttpConnectionError("x")) is SourceErrorKind.NETWORK_ERROR


def test_classify_transport_error_maps_oversized_response_to_invalid_response():
    assert (
        classify_transport_error(HttpResponseTooLargeError("x"))
        is SourceErrorKind.INVALID_RESPONSE
    )


def test_transport_error_result_produces_contract_valid_failure_result():
    result = transport_error_result("some_source", HttpConnectionError("boom"))
    assert result.status is SourceStatus.NETWORK_ERROR
    assert result.error_kind is SourceErrorKind.NETWORK_ERROR
    assert result.metadata is None
    assert "boom" in result.error_detail
    assert "HttpConnectionError" in result.error_detail


def test_transport_error_detail_names_the_exception_even_when_its_message_is_empty():
    # httpx timeouts stringify to "", which used to leave only "transport error: ".
    result = transport_error_result("some_source", HttpTimeoutError(""))
    assert result.status is SourceStatus.NETWORK_ERROR
    assert result.error_detail == "some_source: transport error: HttpTimeoutError"


# --- SourceAdapter identity enforcement --------------------------------------


def test_adapter_missing_source_id_raises_type_error_at_construction():
    class BrokenAdapter(SourceAdapter):
        source_id = ""
        display_name = "Broken"
        default_base_url = "https://example.invalid"

        async def fetch(self, number, client):
            raise NotImplementedError

    with pytest.raises(TypeError):
        BrokenAdapter()


def test_adapter_missing_display_name_raises_type_error_at_construction():
    class BrokenAdapter(SourceAdapter):
        source_id = "broken"
        display_name = ""
        default_base_url = "https://example.invalid"

        async def fetch(self, number, client):
            raise NotImplementedError

    with pytest.raises(TypeError):
        BrokenAdapter()


def test_adapter_cannot_be_instantiated_without_implementing_fetch():
    class NoFetchAdapter(SourceAdapter):
        source_id = "no_fetch"
        display_name = "No Fetch"
        default_base_url = "https://example.invalid"

    with pytest.raises(TypeError):
        NoFetchAdapter()


def test_adapter_uses_default_base_url_when_not_overridden():
    adapter = FakeSourceAdapter()
    assert adapter.base_url == FakeSourceAdapter.default_base_url


def test_adapter_base_url_override_does_not_change_source_id():
    adapter = FakeSourceAdapter(base_url="https://mirror.invalid")
    assert adapter.base_url == "https://mirror.invalid"
    assert adapter.source_id == "fake_source"


def test_fetch_rejects_non_canonical_number_before_any_http_call():
    adapter = FakeSourceAdapter()
    client = FakeHttpClient()

    with pytest.raises(InvalidCanonicalNumberInputError):
        run(adapter.fetch("garbage-not-a-number", client))

    assert client.requested_urls == []
