"""End-to-end offline exercise of a SourceAdapter through the injected
SourceHttpClient Protocol: every SourceStatus outcome, the canonical-number
boundary, base_url override, and field_sources attribution -- all without
any real network access."""

from __future__ import annotations

import asyncio

from fc2_metadata_core.http.client import HttpConnectionError, HttpTimeoutError
from fc2_metadata_core.models.source_result import SourceErrorKind, SourceStatus

from support.fake_http_client import FakeHttpClient, make_response
from support.fake_source_adapter import FakeSourceAdapter


def run(coro):
    return asyncio.run(coro)


def test_success_returns_minimum_success_metadata_with_field_sources():
    adapter = FakeSourceAdapter()
    client = FakeHttpClient()
    url = adapter._lookup_url("FC2-4825061")
    client.add_response(url, make_response(status_code=200, url=url, text="TITLE: Example Film\n"))

    result = run(adapter.fetch("FC2-4825061", client))

    assert result.status is SourceStatus.SUCCESS
    assert result.error_kind is None
    assert result.metadata is not None
    assert result.metadata.number == "FC2-4825061"
    assert result.metadata.title == "Example Film"
    assert result.metadata.meets_minimum_success() is True
    assert result.metadata.field_sources["number"] == ("fake_source",)
    assert result.metadata.field_sources["title"] == ("fake_source",)
    assert client.requested_urls == [url]


def test_not_found_maps_404_with_no_metadata():
    adapter = FakeSourceAdapter()
    client = FakeHttpClient()
    url = adapter._lookup_url("FC2-9999999")
    client.add_response(url, make_response(status_code=404, url=url))

    result = run(adapter.fetch("FC2-9999999", client))

    assert result.status is SourceStatus.NOT_FOUND
    assert result.error_kind is SourceErrorKind.NOT_FOUND
    assert result.metadata is None
    assert result.error_detail


def test_blocked_maps_403():
    adapter = FakeSourceAdapter()
    client = FakeHttpClient()
    url = adapter._lookup_url("FC2-1234567")
    client.add_response(url, make_response(status_code=403, url=url))

    result = run(adapter.fetch("FC2-1234567", client))

    assert result.status is SourceStatus.BLOCKED
    assert result.error_kind is SourceErrorKind.BLOCKED
    assert result.metadata is None


def test_rate_limited_maps_429():
    adapter = FakeSourceAdapter()
    client = FakeHttpClient()
    url = adapter._lookup_url("FC2-1234567")
    client.add_response(url, make_response(status_code=429, url=url))

    result = run(adapter.fetch("FC2-1234567", client))

    assert result.status is SourceStatus.RATE_LIMITED
    assert result.error_kind is SourceErrorKind.RATE_LIMITED
    assert result.metadata is None


def test_unparseable_200_body_is_parse_error_not_success():
    adapter = FakeSourceAdapter()
    client = FakeHttpClient()
    url = adapter._lookup_url("FC2-1234567")
    client.add_response(url, make_response(status_code=200, url=url, text="<no title here>"))

    result = run(adapter.fetch("FC2-1234567", client))

    assert result.status is SourceStatus.PARSE_ERROR
    assert result.error_kind is SourceErrorKind.PARSE_ERROR
    assert result.metadata is None


def test_unexpected_status_code_is_invalid_response():
    adapter = FakeSourceAdapter()
    client = FakeHttpClient()
    url = adapter._lookup_url("FC2-1234567")
    client.add_response(url, make_response(status_code=500, url=url))

    result = run(adapter.fetch("FC2-1234567", client))

    assert result.status is SourceStatus.INVALID_RESPONSE
    assert result.error_kind is SourceErrorKind.INVALID_RESPONSE
    assert result.metadata is None


def test_connection_error_maps_to_network_error():
    adapter = FakeSourceAdapter()
    client = FakeHttpClient()
    url = adapter._lookup_url("FC2-1234567")
    client.add_error(url, HttpConnectionError("simulated DNS failure"))

    result = run(adapter.fetch("FC2-1234567", client))

    assert result.status is SourceStatus.NETWORK_ERROR
    assert result.error_kind is SourceErrorKind.NETWORK_ERROR
    assert result.metadata is None


def test_timeout_maps_to_network_error():
    adapter = FakeSourceAdapter()
    client = FakeHttpClient()
    url = adapter._lookup_url("FC2-1234567")
    client.add_error(url, HttpTimeoutError("simulated timeout"))

    result = run(adapter.fetch("FC2-1234567", client))

    assert result.status is SourceStatus.NETWORK_ERROR
    assert result.error_kind is SourceErrorKind.NETWORK_ERROR


def test_base_url_override_changes_the_request_url():
    adapter = FakeSourceAdapter(base_url="https://mirror.invalid")
    client = FakeHttpClient()
    url = adapter._lookup_url("FC2-1234567")
    assert url.startswith("https://mirror.invalid/")
    client.add_response(url, make_response(status_code=200, url=url, text="TITLE: Mirrored\n"))

    result = run(adapter.fetch("FC2-1234567", client))

    assert result.status is SourceStatus.SUCCESS
    assert client.requested_urls == [url]
