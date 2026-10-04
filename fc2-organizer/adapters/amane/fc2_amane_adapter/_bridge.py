"""Amane ``PluginContext.web_client`` -> Core ``SourceHttpClient`` 传输桥（纯模块；合同第 13、14 节）。

* 只调用宿主的 ``web_client.request``；不创建任何 HTTP 客户端（I3 / I4）。
* ``ok_statuses = 300..599``：显式集合内的 HTTP 状态码作为**普通响应**返回，只产生 1 个 host attempt；
  集合之外（如 ``600``）宿主仍可能抛 ``RequestError(http_error)``，由 ``HttpTransportError`` 兜底承接（W-09）。
* 异常分类**只**读取结构化属性 ``reason``（``FailureReason`` 的值），绝不解析异常消息（I8）。
* 本模块不 import ``amane``：宿主的异常类型由 ``plugin.py`` 中的私有子类以**类属性**
  ``host_request_error_types`` / ``host_source_error_types`` 提供；基类的默认空元组 ``()`` 表示“不映射任何宿主异常”
  （``except ()`` 什么也不捕获）。构造器保持合同 §13.2 冻结的签名 ``(web_client, *, clock)``，
  **不**接受任何异常类型参数。这样 §18 的“不得出现 ``except Exception`` / ``except BaseException``”在本模块中也成立，
  编程错误与 ``CancelledError`` 原样传播（表 E 末两行）。
* 桥抛出的异常消息都是固定短文本，不含 URL / 响应体 / 头 / 宿主异常消息（I12）。
"""

from __future__ import annotations

import codecs
import time
from collections.abc import Callable, Mapping
from typing import ClassVar

from fc2_metadata_core.http import (
    HttpConnectionError,
    HttpResponse,
    HttpResponseTooLargeError,
    HttpTimeoutError,
    HttpTransportError,
)
from fc2_metadata_core.http.client import HttpDecodingError

__all__ = ["MAX_RESPONSE_BYTES", "OK_STATUSES", "AmaneHttpBridge"]

#: 响应体上限（与 Core ``HttpxTransport`` 默认一致）；只能事后检查（L-02）。
MAX_RESPONSE_BYTES = 5 * 1024 * 1024

#: ``ok_statuses``：让 3xx-5xx 作为普通响应进入 Core adapter，而不是被宿主重试 / 抛 ``RequestError``。
OK_STATUSES = frozenset(range(300, 600))

_INVALID_RESPONSE = "invalid host response"
_DEFAULT_CHARSET = "utf-8"


def _charset_from_content_type(content_type: str) -> str:
    for part in content_type.split(";")[1:]:
        key, separator, value = part.partition("=")
        if separator and key.strip().lower() == "charset":
            return value.strip().strip("\"'").strip() or _DEFAULT_CHARSET
    return _DEFAULT_CHARSET


def _decode(content: bytes, content_type: str) -> str:
    name = _charset_from_content_type(content_type)
    try:
        codecs.lookup(name)
    except LookupError:
        name = _DEFAULT_CHARSET  # 未知 charset 名：回退 utf-8（与 Core HttpxTransport 一致）
    except ValueError:
        raise HttpDecodingError("response charset is malformed") from None
    try:
        return content.decode(name, "replace")
    except (LookupError, UnicodeError, ValueError):
        # 非文本 codec（rot13 / base64 / zlib ...）、不可用 codec（idna / undefined ...）
        raise HttpDecodingError("response charset cannot decode text") from None


def _joined_headers(raw_headers: object) -> dict[str, str]:
    try:
        items = raw_headers.multi_items() if hasattr(raw_headers, "multi_items") else raw_headers.items()  # type: ignore[attr-defined]
        headers: dict[str, str] = {}
        for key, value in items:
            if not isinstance(key, str) or not isinstance(value, str):
                raise HttpTransportError(_INVALID_RESPONSE)
            lowered = key.lower()
            headers[lowered] = f"{headers[lowered]}, {value}" if lowered in headers else value
    except (AttributeError, TypeError, ValueError):
        raise HttpTransportError(_INVALID_RESPONSE) from None
    return headers


class AmaneHttpBridge:
    """满足 ``SourceHttpClient`` Protocol：``async get(url, *, headers=None, timeout=None)``。

    宿主异常的精确分类由子类通过类属性声明（``plugin.py`` 的 ``_HostAmaneHttpBridge``）：
    ``host_request_error_types`` 对应 Amane ``RequestError``（按结构化 ``reason`` 映射），
    ``host_source_error_types`` 对应其它 ``SourceError``（-> ``HttpTransportError``）。
    基类的默认空元组不捕获任何宿主异常。
    """

    host_request_error_types: ClassVar[tuple[type[BaseException], ...]] = ()
    host_source_error_types: ClassVar[tuple[type[BaseException], ...]] = ()

    def __init__(
        self,
        web_client: object,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._web_client = web_client
        self._clock = clock

    async def get(
        self,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        timeout: float | None = None,
    ) -> HttpResponse:
        started = self._clock()
        try:
            response = await self._web_client.request(  # type: ignore[attr-defined]
                "GET",
                url,
                headers=dict(headers) if headers else None,
                timeout=timeout,
                ok_statuses=OK_STATUSES,
            )
        except self.host_request_error_types as exc:
            raise self._map_request_error(exc) from None
        except self.host_source_error_types:
            raise HttpTransportError("host source error") from None
        elapsed_ms = max(0.0, (self._clock() - started) * 1000.0)
        return self._to_http_response(url, response, elapsed_ms)

    @staticmethod
    def _map_request_error(exc: BaseException) -> HttpTransportError:
        reason = getattr(exc, "reason", None)
        reason_value = getattr(reason, "value", reason)
        if reason_value == "timeout":
            return HttpTimeoutError("host request timed out")
        if reason_value == "network":
            return HttpConnectionError("host request failed to connect")
        return HttpTransportError("host request failed")

    @staticmethod
    def _to_http_response(url: str, response: object, elapsed_ms: float) -> HttpResponse:
        status_code = getattr(response, "status_code", None)
        if not isinstance(status_code, int) or isinstance(status_code, bool):
            raise HttpTransportError(_INVALID_RESPONSE)
        content = getattr(response, "content", None)
        if not isinstance(content, bytes):
            raise HttpTransportError(_INVALID_RESPONSE)
        raw_headers = getattr(response, "headers", None)
        if raw_headers is None:
            raise HttpTransportError(_INVALID_RESPONSE)
        headers = _joined_headers(raw_headers)
        if len(content) > MAX_RESPONSE_BYTES:
            raise HttpResponseTooLargeError(f"response body exceeded {MAX_RESPONSE_BYTES} byte limit")
        final_url = getattr(response, "url", None)
        final_url_text = str(final_url) if final_url is not None else ""
        text = _decode(content, headers.get("content-type", ""))
        return HttpResponse(
            status_code=status_code,
            url=final_url_text or url,
            headers=headers,
            text=text,
            elapsed_ms=elapsed_ms,
        )
