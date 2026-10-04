"""P5-C1：纯逻辑测试用的“宿主 web client”替身（duck-typed；**不 import amane**）。

* ``FakeResponse`` / ``FakeHeaders``：形状与 curl_cffi ``Response`` 的被使用子集一致
  （``status_code`` / ``content`` / ``url`` / ``headers``）。
* ``FakeRequestError`` / ``FakeSourceError``：与 Amane ``RequestError`` / ``SourceError`` 同形状的异常
  （``reason.value`` / ``http_status`` / ``detail`` / ``url``）；``FakeRequestError`` 是 ``FakeSourceError`` 的子类。
* ``FakeWebClient``：按 URL 编排响应 / 异常 / 挂起，记录每次调用的参数。
* ``HostModelWebClient``：把 v0.15.0 ``WebClient.request`` 的“重试 H 次 + ``ok_statuses``”语义建模
  （不睡眠、不联网），用于有界性的纯逻辑测试；真实语义由 ``H-09`` 在真实宿主上见证。
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field

__all__ = [
    "HANG",
    "FakeCurlError",
    "FakeHeaders",
    "FakeReason",
    "FakeRequestError",
    "FakeResponse",
    "FakeSourceError",
    "FakeWebClient",
    "HostModelWebClient",
]

HANG = object()  # 编排项：挂起直到被取消


@dataclass(frozen=True)
class FakeReason:
    value: str


class FakeSourceError(Exception):
    def __init__(self, reason: str, *, http_status: int | None = None, detail: str | None = None, url: str | None = None):
        self.reason = FakeReason(reason)
        self.http_status = http_status
        self.detail = detail
        self.url = url
        super().__init__(detail or reason)


class FakeRequestError(FakeSourceError):
    """与 Amane ``RequestError`` 同形状；消息里故意放入会诱导“解析文本”的内容。"""


class FakeCurlError(Exception):
    """宿主模型里“可重试的传输失败”（对应 ``CurlError``）。"""


class FakeHeaders:
    def __init__(self, pairs: Iterable[tuple[str, str]] = ()) -> None:
        self._pairs = list(pairs)

    def items(self):
        return list(self._pairs)

    def multi_items(self):
        return list(self._pairs)


@dataclass
class FakeResponse:
    status_code: object = 200
    content: object = b""
    url: object = ""
    headers: object = field(default_factory=FakeHeaders)

    @classmethod
    def html(cls, text: str, *, status: int = 200, url: str = "", charset: str | None = "utf-8",
             extra_headers: Iterable[tuple[str, str]] = ()) -> FakeResponse:
        content_type = "text/html" + (f"; charset={charset}" if charset else "")
        encoding = charset if charset and _known(charset) else "utf-8"
        pairs = [("Content-Type", content_type), *extra_headers]
        return cls(status_code=status, content=text.encode(encoding), url=url, headers=FakeHeaders(pairs))


def _known(name: str) -> bool:
    import codecs

    try:
        codecs.lookup(name)
    except LookupError:
        return False
    return True


class FakeWebClient:
    """按 URL 编排：每个 URL 一个队列（用完后重复最后一项）；未编排的 URL 返回 404 响应。"""

    def __init__(self, routes: Mapping[str, object] | None = None, *, default: object | None = None) -> None:
        self._routes: dict[str, list[object]] = {}
        for url, item in (routes or {}).items():
            self.add(url, *(item if isinstance(item, list) else [item]))
        self._default = default
        self.calls: list[tuple[str, str, dict[str, object]]] = []
        self.in_flight = 0

    def add(self, url: str, *items: object) -> None:
        self._routes.setdefault(url, []).extend(items)

    async def request(self, method, url, **kwargs):
        self.calls.append((method, url, dict(kwargs)))
        queue = self._routes.get(url)
        if queue:
            item = queue.pop(0) if len(queue) > 1 else queue[0]
        elif self._default is not None:
            item = self._default
        else:
            item = FakeResponse.html("", status=404, url=url)
        self.in_flight += 1
        try:
            if item is HANG:
                await asyncio.Event().wait()
            if isinstance(item, BaseException):
                raise item
            if callable(item):
                item = item()
                if isinstance(item, BaseException):
                    raise item
            return item
        finally:
            self.in_flight -= 1

    @property
    def requested_urls(self) -> list[str]:
        return [url for _method, url, _kwargs in self.calls]


class HostModelWebClient:
    """v0.15.0 ``WebClient.request`` 语义的纯逻辑模型（``max_retries`` = H 个 host attempts；不睡眠）。

    ``outcomes(url)`` 返回该 URL 的逐 attempt 结果迭代器：``FakeResponse`` / 异常实例。
    ``FakeCurlError`` 与 ``TimeoutError`` 可重试；状态码 408/429/503/504 在不被 ``ok_statuses`` 覆盖时可重试；
    其它异常不重试；耗尽后抛 ``FakeRequestError``。
    """

    RETRYABLE_STATUSES = frozenset({408, 429, 503, 504})

    def __init__(self, outcomes: Callable[[str], Iterable[object]], *, max_retries: int = 3) -> None:
        self._outcomes = outcomes
        self._iterators: dict[str, object] = {}
        self.max_retries = max_retries
        self.host_attempts = 0
        self.requests = 0
        self.attempts_by_url: dict[str, int] = {}
        self.calls: list[tuple[str, str, dict[str, object]]] = []

    async def request(self, method, url, *, ok_statuses=None, **kwargs):
        self.calls.append((method, url, {"ok_statuses": ok_statuses, **kwargs}))
        self.requests += 1
        iterator = self._iterators.setdefault(url, iter(self._outcomes(url)))
        failure_reason = "network"
        status = None
        for _attempt in range(self.max_retries):
            self.host_attempts += 1
            self.attempts_by_url[url] = self.attempts_by_url.get(url, 0) + 1
            outcome = next(iterator)
            if isinstance(outcome, FakeResponse):
                code = outcome.status_code
                extra = ok_statuses or frozenset()
                if code < 300 or code in extra:
                    return outcome
                status = code
                failure_reason = "rate_limited" if code == 429 else "server_error" if code >= 500 else "http_error"
                if code not in self.RETRYABLE_STATUSES:
                    break
                continue
            if isinstance(outcome, (FakeCurlError,)):
                failure_reason = "network"
                continue
            if isinstance(outcome, TimeoutError):
                failure_reason = "timeout"
                continue
            failure_reason = "unexpected"
            break
        raise FakeRequestError(failure_reason, http_status=status, detail="host message that must never be parsed", url=url)
