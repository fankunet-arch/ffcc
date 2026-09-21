"""Offline fakes for the Phase 3 C4 batch scheduler tests.

``agg(number, kind)`` builds a **real** ``AggregationResult`` through the real
``merge_source_results`` (never hand-forged), so every batch test runs against results that satisfy the
aggregation invariants. ``ScriptedEngine`` is a fake single-item engine (``async aggregate(number)``) that
records what the scheduler did to it: start order, live calls, peak, completion order, cancellations.
"""

from __future__ import annotations

import asyncio
from functools import lru_cache
from typing import Awaitable, Callable

from fc2_metadata_core.aggregation import AggregationPolicy, AggregationResult, merge_source_results
from fc2_metadata_core.models.source_result import SourceErrorKind, SourceStatus

from support.scripted_adapters import failed, ok

Behavior = Callable[[str, int], Awaitable[AggregationResult]]

SOURCES = ("src_a", "src_b")


def numbers(count: int, start: int = 1_000_001) -> list[str]:
    """``count`` distinct canonical FC2 numbers."""
    return [f"FC2-{start + i}" for i in range(count)]


@lru_cache(maxsize=None)
def agg(number: str, kind: str = "success") -> AggregationResult:
    """A real merged AggregationResult of the requested kind.

    ``success``  both sources answer.
    ``partial``  one source answers, the other a network error (an operational failure).
    ``deadline`` one source answers, the other hit its total deadline (SOURCE_DEADLINE).
    ``failed``   nobody produced data (FAILED, every SourceResult kept).
    """
    policy = AggregationPolicy.build(SOURCES)
    a, b = SOURCES
    if kind == "success":
        results = [ok(a, number, "Title A"), ok(b, number, "Title B")]
    elif kind == "partial":
        results = [ok(a, number, "Title A"), failed(b, SourceStatus.NETWORK_ERROR)]
    elif kind == "deadline":
        results = [
            ok(a, number, "Title A"),
            failed(b, SourceStatus.NETWORK_ERROR, error_kind=SourceErrorKind.SOURCE_DEADLINE),
        ]
    elif kind == "failed":
        results = [failed(a, SourceStatus.NOT_FOUND), failed(b, SourceStatus.NETWORK_ERROR)]
    else:  # pragma: no cover - test bug
        raise AssertionError(f"unknown kind {kind!r}")
    return merge_source_results(number, results, policy)


class ScriptedEngine:
    """A fake single-item engine: ``async aggregate(number)``.

    ``behavior(number, call_seq)`` decides each call's outcome (default: an immediate SUCCESS);
    ``call_seq`` is the 0-based order in which calls *started*.
    """

    def __init__(self, behavior: Behavior | None = None) -> None:
        self._behavior = behavior or self._default
        self.calls: list[str] = []  # numbers, in start order
        self.completed: list[str] = []  # numbers, in completion order (normal return only)
        self.cancelled: list[str] = []  # numbers whose call observed a CancelledError
        self.active = 0
        self.peak = 0

    @staticmethod
    async def _default(number: str, seq: int) -> AggregationResult:
        await asyncio.sleep(0)
        return agg(number)

    async def aggregate(self, number: str) -> AggregationResult:
        seq = len(self.calls)
        self.calls.append(number)
        self.active += 1
        self.peak = max(self.peak, self.active)
        try:
            result = await self._behavior(number, seq)
            self.completed.append(number)
            return result
        except asyncio.CancelledError:
            self.cancelled.append(number)
            raise
        finally:
            self.active -= 1


class Gate:
    """Lets a test hold calls open until it releases them (no timing involved)."""

    def __init__(self) -> None:
        self.release = asyncio.Event()

    async def wait(self) -> None:
        await self.release.wait()


async def until(predicate: Callable[[], bool], *, spins: int = 10_000) -> None:
    """Yield to the loop until ``predicate()`` holds (bounded by loop iterations, not wall time)."""
    for _ in range(spins):
        if predicate():
            return
        await asyncio.sleep(0)
    raise AssertionError("condition never became true")
