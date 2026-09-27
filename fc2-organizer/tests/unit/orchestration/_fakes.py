"""Scripted in-memory fakes for the P4-C8 orchestration tests (construction plan section 0.5).

* ``ScriptedEngine``      -- Phase 3 ``AggregationEngine`` protocol (``async aggregate(number)``);
* ``ScriptedImageClient`` -- P4-C5 ``ImageHttpClient`` protocol (``async get(url, *, ...)``);
* ``build_metadata``      -- a **real** ``AggregationResult`` built through the public
  ``NormalizedMetadata`` / ``SourceResult`` / ``merge_source_results`` API (never hand-forged);
* ``minimal_jpeg``        -- bytes that pass the P4-C5 JPEG validation.

Both fakes record call order and the concurrency peak; completion order is controlled with
``asyncio.Event`` gates, never with ``sleep`` as a correctness mechanism. Nothing here touches the
network or the filesystem, and production code never imports this module.
"""

from __future__ import annotations

import asyncio
from typing import Awaitable, Callable

from fc2_metadata_core.aggregation import AggregationPolicy, AggregationResult, merge_source_results
from fc2_metadata_core.models.source_result import SourceStatus
from fc2_organizer.images.transport import ImageHttpResponse

from support.scripted_adapters import failed, ok

SOURCES = ("src_a", "src_b")


def build_metadata(number: str, kind: str = "success", **fields) -> AggregationResult:
    """A real merged ``AggregationResult`` for ``number``.

    ``success`` both sources answer; ``partial`` one answers, the other fails (network error);
    ``failed`` nobody produced data. ``fields`` (``release``, ``poster_urls``, ...) go into the
    answering sources' ``NormalizedMetadata``.
    """
    policy = AggregationPolicy.build(SOURCES)
    a, b = SOURCES
    title = fields.pop("title", "Example Title")
    if kind == "success":
        results = [ok(a, number, title, **fields), ok(b, number, title, **fields)]
    elif kind == "partial":
        results = [ok(a, number, title, **fields), failed(b, SourceStatus.NETWORK_ERROR)]
    elif kind == "failed":
        results = [failed(a, SourceStatus.NOT_FOUND), failed(b, SourceStatus.NETWORK_ERROR)]
    else:  # pragma: no cover - test bug
        raise AssertionError(f"unknown metadata kind {kind!r}")
    return merge_source_results(number, results, policy)


def _segment(marker: int, payload: bytes) -> bytes:
    return bytes([0xFF, marker]) + (len(payload) + 2).to_bytes(2, "big") + payload


def minimal_jpeg(width: int = 16, height: int = 16, *, seed: int = 0, pad: int = 0) -> bytes:
    """A structurally valid baseline JPEG (``seed`` varies the bytes, ``pad`` grows a COM segment)."""
    frame = bytes([8]) + height.to_bytes(2, "big") + width.to_bytes(2, "big") + b"\x01\x01\x11\x00"
    scan = b"\x01\x01\x00\x00\x3f\x00"
    comments = b""
    remaining = pad
    while remaining > 0:
        chunk = min(remaining, 60_000)
        comments += _segment(0xFE, bytes([seed % 256]) * chunk)
        remaining -= chunk
    return (b"\xff\xd8" + _segment(0xE0, b"JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00") + comments
            + _segment(0xDB, b"\x00" + bytes(range(1, 65))) + _segment(0xC0, frame)
            + _segment(0xDA, scan) + bytes([seed % 256, 0x12, 0xFF, 0x00, 0x34]) + b"\xff\xd9")


class _Recorder:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.completed: list[str] = []
        self.cancelled: list[str] = []
        self.active = 0
        self.peak = 0
        self.gates: dict[str, asyncio.Event] = {}

    def gate(self, key: str) -> asyncio.Event:
        """Hold every call for ``key`` until the returned event is set (create inside the loop)."""
        event = asyncio.Event()
        self.gates[key] = event
        return event

    async def _run(self, key: str, produce: Callable[[], Awaitable[object]]):
        self.calls.append(key)
        self.active += 1
        self.peak = max(self.peak, self.active)
        try:
            await asyncio.sleep(0)
            gate = self.gates.get(key)
            if gate is not None:
                await gate.wait()
            result = await produce()
            self.completed.append(key)
            return result
        except asyncio.CancelledError:
            self.cancelled.append(key)
            raise
        finally:
            self.active -= 1


async def _outcome(value: object, *args: object) -> object:
    if isinstance(value, type) and issubclass(value, BaseException):
        raise value()
    if isinstance(value, BaseException):
        raise value
    if callable(value):
        return await value(*args)
    return value


class ScriptedEngine(_Recorder):
    """``async aggregate(number)``. ``script[number]`` is ``"success"`` / ``"partial"`` / ``"failed"``
    (a real result), an exception (class or instance) to raise, an ``async`` callable
    ``(number, seq)``, or any other object returned as is (a result-contract mismatch).
    Unscripted numbers answer ``default``; a list value is consumed one entry per call."""

    def __init__(self, script: dict[str, object] | None = None, *, default: object = "success",
                 fields: dict[str, dict] | None = None) -> None:
        super().__init__()
        self.script = dict(script or {})
        self.default = default
        self.fields = dict(fields or {})

    async def aggregate(self, number: str) -> AggregationResult:
        seq = len(self.calls)
        value = self.script.get(number, self.default)
        if isinstance(value, list):
            value = value.pop(0) if len(value) > 1 else value[0]

        async def produce():
            if isinstance(value, str) and value in ("success", "partial", "failed"):
                return build_metadata(number, value, **self.fields.get(number, {}))
            return await _outcome(value, number, seq)

        return await self._run(number, produce)


class ScriptedImageClient(_Recorder):
    """``async get(url, *, deadline_seconds, max_redirects, max_bytes)``. ``script[url]`` is an
    ``ImageHttpResponse``, an exception (class or instance) to raise, or an ``async`` callable
    ``(url,)``. An unscripted URL fails the test."""

    def __init__(self, script: dict[str, object] | None = None) -> None:
        super().__init__()
        self.script = dict(script or {})
        self.kwargs: list[dict[str, object]] = []

    async def get(self, url: str, *, deadline_seconds: float, max_redirects: int, max_bytes: int):
        self.kwargs.append(dict(deadline_seconds=deadline_seconds, max_redirects=max_redirects, max_bytes=max_bytes))

        async def produce():
            assert url in self.script, "unscripted image request"
            return await _outcome(self.script[url], url)

        return await self._run(url, produce)

    async def aclose(self) -> None:
        return None


def jpeg_response(content: bytes | None = None) -> ImageHttpResponse:
    return ImageHttpResponse(status_code=200, content_type="image/jpeg",
                             content=minimal_jpeg() if content is None else content)


def status_response(code: int) -> ImageHttpResponse:
    return ImageHttpResponse(status_code=code, content_type="text/html", content=b"")
