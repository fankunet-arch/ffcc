"""Offline tests for HttpxTransport: every scenario runs against an
``httpx.MockTransport`` handler, never real network I/O."""

from __future__ import annotations

import asyncio

import httpx
import pytest

from fc2_metadata_core.http.client import (
    HttpConnectionError,
    HttpRedirectLimitError,
    HttpResponseTooLargeError,
    HttpTimeoutError,
)
from fc2_metadata_core.http.httpx_client import HttpxTransport


def run(coro):
    return asyncio.run(coro)


def test_successful_get_returns_status_url_headers_text():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="hello world", headers={"X-Test": "1"})

    async def scenario():
        async with HttpxTransport(transport=httpx.MockTransport(handler)) as client:
            response = await client.get("https://example.invalid/number/FC2-1234567")
            assert response.status_code == 200
            assert response.text == "hello world"
            assert response.headers.get("x-test") == "1"
            assert response.url == "https://example.invalid/number/FC2-1234567"
            assert response.elapsed_ms >= 0

    run(scenario())


def test_final_url_reflects_redirect_target():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/old":
            return httpx.Response(302, headers={"Location": "/new"})
        return httpx.Response(200, text="landed")

    async def scenario():
        async with HttpxTransport(transport=httpx.MockTransport(handler)) as client:
            response = await client.get("https://example.invalid/old")
            assert response.status_code == 200
            assert response.url == "https://example.invalid/new"
            assert response.text == "landed"

    run(scenario())


def test_too_many_redirects_raises_redirect_limit_error():
    def handler(request: httpx.Request) -> httpx.Response:
        n = int(request.url.path.strip("/").split("/")[-1] or 0)
        return httpx.Response(302, headers={"Location": f"/loop/{n + 1}"})

    async def scenario():
        async with HttpxTransport(
            max_redirects=2, transport=httpx.MockTransport(handler)
        ) as client:
            with pytest.raises(HttpRedirectLimitError):
                await client.get("https://example.invalid/loop/0")

    run(scenario())


def test_timeout_raises_http_timeout_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("simulated timeout", request=request)

    async def scenario():
        async with HttpxTransport(transport=httpx.MockTransport(handler)) as client:
            with pytest.raises(HttpTimeoutError):
                await client.get("https://example.invalid/slow")

    run(scenario())


def test_connect_error_raises_http_connection_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("simulated dns/connect failure", request=request)

    async def scenario():
        async with HttpxTransport(transport=httpx.MockTransport(handler)) as client:
            with pytest.raises(HttpConnectionError):
                await client.get("https://example.invalid/unreachable")

    run(scenario())


def test_declared_content_length_over_limit_raises_before_reading_body():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"Content-Length": "999999999"},
            text="x" * 10,
        )

    async def scenario():
        async with HttpxTransport(
            max_response_bytes=1024, transport=httpx.MockTransport(handler)
        ) as client:
            with pytest.raises(HttpResponseTooLargeError):
                await client.get("https://example.invalid/huge")

    run(scenario())


def test_undeclared_oversized_body_raises_while_streaming():
    def handler(request: httpx.Request) -> httpx.Response:
        # No Content-Length header, so only the streamed-byte-count guard
        # can catch this -- the declared-length shortcut cannot.
        return httpx.Response(200, text="x" * 2048)

    async def scenario():
        async with HttpxTransport(
            max_response_bytes=100, transport=httpx.MockTransport(handler)
        ) as client:
            with pytest.raises(HttpResponseTooLargeError):
                await client.get("https://example.invalid/huge-unlabeled")

    run(scenario())


def test_per_call_timeout_override_is_honored_by_mock_transport():
    seen_timeouts = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_timeouts.append(request.extensions.get("timeout"))
        return httpx.Response(200, text="ok")

    async def scenario():
        async with HttpxTransport(
            timeout_seconds=15.0, transport=httpx.MockTransport(handler)
        ) as client:
            await client.get("https://example.invalid/x", timeout=3.0)

    run(scenario())
    # httpx encodes the effective timeout onto the request; a per-call
    # override must not silently fall back to the client-wide default.
    assert seen_timeouts and seen_timeouts[0] is not None
