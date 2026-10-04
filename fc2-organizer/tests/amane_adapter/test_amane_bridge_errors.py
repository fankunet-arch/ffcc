"""P5-C1 表 E（E8）：传输异常映射——只看结构化 ``reason``，不解析消息；取消与编程错误原样传播。"""

from __future__ import annotations

import ast
import asyncio
from pathlib import Path

import pytest

from fc2_amane_adapter import _bridge
from fc2_amane_adapter._bridge import AmaneHttpBridge
from fc2_metadata_core.http import (
    HttpConnectionError,
    HttpTimeoutError,
    HttpTransportError,
)
from fc2_metadata_core.models import SourceErrorKind
from fc2_metadata_core.sources.base import classify_transport_failure
from support.amane_host_fakes import HANG, FakeRequestError, FakeSourceError, FakeWebClient

URL = "https://site.example/secret-path/1234567?token=SECRET"
BRIDGE_SOURCE = Path(_bridge.__file__)


def _bridge_for(item):
    client = FakeWebClient({URL: item})
    return AmaneHttpBridge(
        client, request_error_types=(FakeRequestError,), source_error_types=(FakeSourceError,)
    )


def _raises(item):
    bridge = _bridge_for(item)
    with pytest.raises(BaseException) as excinfo:
        asyncio.run(bridge.get(URL))
    return excinfo.value


@pytest.mark.parametrize(
    ("reason", "expected_type", "expected_kind"),
    [
        ("timeout", HttpTimeoutError, SourceErrorKind.TIMEOUT),
        ("network", HttpConnectionError, SourceErrorKind.CONNECTION_ERROR),
        ("unexpected", HttpTransportError, SourceErrorKind.NETWORK_ERROR),
        ("http_error", HttpTransportError, SourceErrorKind.NETWORK_ERROR),  # 状态码 600
        ("server_error", HttpTransportError, SourceErrorKind.NETWORK_ERROR),
        ("rate_limited", HttpTransportError, SourceErrorKind.NETWORK_ERROR),
        ("not_found", HttpTransportError, SourceErrorKind.NETWORK_ERROR),
        ("cloudflare_challenge", HttpTransportError, SourceErrorKind.NETWORK_ERROR),
    ],
)
def test_request_error_reason_maps_to_core_exception_and_kind(reason, expected_type, expected_kind):
    error = _raises(FakeRequestError(reason, http_status=None, detail="host detail", url=URL))
    assert type(error) is expected_type
    assert classify_transport_failure(error) is expected_kind


@pytest.mark.parametrize(
    ("reason", "detail"),
    [
        ("unexpected", "timeout while connecting to the network; dns failure; connection refused"),
        ("timeout", "connection reset; TLS handshake failed; network is unreachable"),
        ("network", "operation timed out after 30s"),
    ],
)
def test_mapping_never_reads_the_exception_message(reason, detail):
    """消息被“篡改”成相反语义：分类仍只取决于 ``reason``。"""
    error = _raises(FakeRequestError(reason, detail=detail, url=URL))
    expected = {"timeout": HttpTimeoutError, "network": HttpConnectionError, "unexpected": HttpTransportError}[reason]
    assert type(error) is expected


def test_non_request_source_error_is_generic_even_if_its_reason_says_timeout():
    error = _raises(FakeSourceError("timeout", detail="timeout"))
    assert type(error) is HttpTransportError
    assert classify_transport_failure(error) is SourceErrorKind.NETWORK_ERROR


def test_raised_messages_are_fixed_short_texts_without_url_or_host_message():
    for item in (
        FakeRequestError("timeout", detail="HOSTMSG", url=URL),
        FakeRequestError("network", detail="HOSTMSG", url=URL),
        FakeRequestError("unexpected", detail="HOSTMSG", url=URL),
        FakeSourceError("unexpected", detail="HOSTMSG", url=URL),
    ):
        error = _raises(item)
        text = str(error)
        assert "HOSTMSG" not in text and "secret-path" not in text and "SECRET" not in text and URL not in text
        assert len(text) < 80
        assert error.__cause__ is None and error.__suppress_context__


def test_cancellation_propagates_unchanged():
    error = _raises(asyncio.CancelledError())
    assert type(error) is asyncio.CancelledError


def test_task_cancel_while_the_host_request_hangs_is_not_converted():
    async def scenario():
        bridge = _bridge_for(HANG)
        task = asyncio.create_task(bridge.get(URL))
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(scenario())


@pytest.mark.parametrize("error", [ValueError("boom"), AttributeError("x"), KeyError("k"), RuntimeError("r")])
def test_programming_errors_are_not_caught(error):
    assert _raises(error) is error


def test_fatal_exceptions_propagate():
    assert type(_raises(KeyboardInterrupt())) is KeyboardInterrupt


def test_without_injected_host_types_nothing_is_mapped():
    """``except ()`` 什么也不捕获：默认桥不会吞宿主异常（宿主类型只由 plugin.py 注入）。"""
    client = FakeWebClient({URL: FakeRequestError("timeout")})
    bridge = AmaneHttpBridge(client)
    with pytest.raises(FakeRequestError):
        asyncio.run(bridge.get(URL))


def test_bridge_ast_has_no_broad_except_and_never_reads_exception_text():
    tree = ast.parse(BRIDGE_SOURCE.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler):
            assert node.type is not None, "bare except"
            names = {n.id for n in ast.walk(node.type) if isinstance(n, ast.Name)}
            assert not names & {"Exception", "BaseException", "CancelledError"}
    attributes = {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
    assert not attributes & {"message", "detail", "args", "failure"}
    strings = [node.value for node in ast.walk(tree) if isinstance(node, ast.Constant) and isinstance(node.value, str)]
    assert not any(" in " in s and "detail" in s for s in strings)
