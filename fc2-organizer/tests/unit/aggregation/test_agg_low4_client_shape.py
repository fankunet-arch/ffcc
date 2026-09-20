"""C1 review LOW-4: a synchronous ``get`` is rejected when the engine is BUILT.

Previously ``callable(client.get)`` let ``def get(...)`` through; every source then failed
at ``await`` time as INVALID_RESPONSE. The check is made without any request.
"""

from __future__ import annotations

import asyncio
import functools
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from fc2_metadata_core.aggregation import (
    AggregationConfig,
    AggregationConfigError,
    MultiSourceEngine,
    SourceConfig,
    is_async_get,
)
from fc2_metadata_core.http.client import HttpResponse
from fc2_metadata_core.http.httpx_client import HttpxTransport
from fc2_metadata_core.sources import SourceRegistry

from support.fake_http_client import FakeHttpClient
from support.scripted_adapters import ok, scripted_adapter_class

N = "FC2-4979299"


def engine_with(client):
    async def script(number, c):
        return ok("a", number, "T")

    registry = SourceRegistry()
    registry.register("a", scripted_adapter_class("a", script))
    return MultiSourceEngine(AggregationConfig.create([SourceConfig("a")]), registry, client)


def response():
    return HttpResponse(status_code=200, url="https://x.invalid/", headers={}, text="", elapsed_ms=1.0)


# ---- rejected ----------------------------------------------------------------------------------------------


class SyncGetClient:
    """The reviewer's BadClient: a synchronous get returning a ready HttpResponse."""

    def __init__(self):
        self.calls = 0

    def get(self, url, *, headers=None, timeout=None):
        self.calls += 1
        return response()


class SyncGetReturningCoroutine:
    def get(self, url, *, headers=None, timeout=None):
        async def inner():
            return response()

        return inner()


class NoGet:
    pass


class GetIsNotCallable:
    get = "https://example.invalid"


class GetIsNone:
    get = None


@pytest.mark.parametrize(
    "client",
    [SyncGetClient(), SyncGetReturningCoroutine(), NoGet(), GetIsNotCallable(), GetIsNone(), object(), None, 5, "client",
     MagicMock(), lambda: None],
    ids=lambda c: type(c).__name__,
)
def test_a_non_async_get_is_rejected_at_engine_construction(client):
    with pytest.raises(AggregationConfigError) as info:
        engine_with(client)
    assert "async" in str(info.value)


def test_the_reviewers_bad_client_is_rejected_before_any_request_is_made():
    bad = SyncGetClient()
    with pytest.raises(AggregationConfigError):
        engine_with(bad)
    assert bad.calls == 0, "shape must be judged without calling get"


# ---- accepted -------------------------------------------------------------------------------------------------


class AsyncMethodClient:
    async def get(self, url, *, headers=None, timeout=None):
        return response()


class CallableAsyncGet:
    async def __call__(self, url, *, headers=None, timeout=None):
        return response()


class ClientWithCallableGet:
    get = CallableAsyncGet()


async def module_level_async_get(base, url, *, headers=None, timeout=None):
    return response()


class ClientWithPartialGet:
    get = staticmethod(functools.partial(module_level_async_get, "base"))


def async_mock_client():
    client = MagicMock()
    client.get = AsyncMock(return_value=response())
    return client


def make_httpx_transport():
    return HttpxTransport(transport=httpx.MockTransport(lambda request: httpx.Response(200, text="x")))


@pytest.mark.parametrize(
    "factory",
    [FakeHttpClient, AsyncMethodClient, ClientWithCallableGet, ClientWithPartialGet, async_mock_client, make_httpx_transport],
    ids=["FakeHttpClient", "async-method", "callable-object-with-async-__call__", "partial-of-async", "AsyncMock", "HttpxTransport"],
)
def test_async_get_implementations_are_accepted(factory):
    client = factory()
    assert is_async_get(client) is True
    engine_with(client)
    if isinstance(client, HttpxTransport):
        asyncio.run(client.aclose())


def test_an_accepted_async_client_actually_works_end_to_end():
    async def scenario():
        result = await engine_with(AsyncMethodClient()).aggregate(N)
        return result.metadata.title

    assert asyncio.run(scenario()) == "T"


def test_is_async_get_is_a_pure_shape_check():
    assert is_async_get(AsyncMethodClient()) and not is_async_get(SyncGetClient())
    assert not is_async_get(object()) and not is_async_get(None)
