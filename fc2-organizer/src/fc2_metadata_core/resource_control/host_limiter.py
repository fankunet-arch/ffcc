"""Per-host concurrency limiter (Phase 3 C5): a FIFO, hand-off, cancellation-safe permit pool.

One :class:`HostLimiter` bounds the network attempts in flight to **one host key**. It is deliberately *not*
``asyncio.Semaphore``: it needs (a) strict FIFO with direct hand-off so a newcomer can never overtake or steal a
released permit, (b) an explicit answer to "granted in the same loop iteration in which the waiter's task was
cancelled" (the permit goes back, never leaks), and (c) observable ``in_flight`` / ``waiting`` / peak counters for
diagnostics -- on every supported Python (>= 3.11).

State transitions are synchronous (no ``await`` inside them), hence atomic on one event loop. The limiter is
bound to whichever loop first makes a caller wait; it is not thread-safe.

It reads nothing but its own counters: no result, no exception message, no trace.
"""

from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass

from fc2_metadata_core.resource_control.errors import ResourceControlConfigError
from fc2_metadata_core.resource_control.host_key import HostKey

__all__ = ["HostLimiter", "HostPermit", "HostSnapshot"]


@dataclass(frozen=True, slots=True)
class HostSnapshot:
    """Immutable diagnostics of one host limiter (scalars and the host key only)."""

    host: HostKey
    limit: int
    in_flight: int
    waiting: int
    peak_in_flight: int


class HostPermit:
    """One held permit. ``release()`` is idempotent; ``with permit:`` releases on exit (also on cancellation)."""

    __slots__ = ("_limiter", "_released")

    def __init__(self, limiter: "HostLimiter") -> None:
        self._limiter: HostLimiter | None = limiter
        self._released = False

    @property
    def released(self) -> bool:
        return self._released

    def release(self) -> None:
        if self._released:
            return
        self._released = True
        limiter, self._limiter = self._limiter, None
        if limiter is not None:
            limiter._release_slot()

    def __enter__(self) -> "HostPermit":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.release()


class HostLimiter:
    """At most ``limit`` live permits for ``host``; waiters are served strictly first-come first-served."""

    __slots__ = ("_host", "_limit", "_in_flight", "_waiters", "_peak")

    def __init__(self, host: HostKey, limit: int) -> None:
        if not isinstance(host, HostKey):
            raise ResourceControlConfigError("host must be a HostKey")
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
            raise ResourceControlConfigError("limit must be an int >= 1")
        self._host = host
        self._limit = limit
        self._in_flight = 0
        self._waiters: deque[asyncio.Future[None]] = deque()
        self._peak = 0

    @property
    def host(self) -> HostKey:
        return self._host

    @property
    def limit(self) -> int:
        return self._limit

    @property
    def in_flight(self) -> int:
        return self._in_flight

    @property
    def waiting(self) -> int:
        return len(self._waiters)

    def snapshot(self) -> HostSnapshot:
        return HostSnapshot(self._host, self._limit, self._in_flight, len(self._waiters), self._peak)

    async def acquire(self) -> HostPermit:
        """Wait for (and return) a permit. A cancellation while waiting propagates at once, leaving no waiter and
        no permit behind."""
        if not self._waiters and self._in_flight < self._limit:
            self._take()
            return HostPermit(self)
        waiter: asyncio.Future[None] = asyncio.get_running_loop().create_future()
        self._waiters.append(waiter)
        try:
            await waiter
        except BaseException:
            # Nothing about the exception is inspected: whatever interrupted the wait, undo our claim.
            if waiter.done() and not waiter.cancelled():
                # The permit was handed to us in the very iteration we were cancelled: give it back.
                self._release_slot()
            else:
                try:
                    self._waiters.remove(waiter)
                except ValueError:
                    pass
            raise
        return HostPermit(self)  # the releaser already counted this permit as in flight (hand-off)

    def _take(self) -> None:
        self._in_flight += 1
        if self._in_flight > self._peak:
            self._peak = self._in_flight

    def _release_slot(self) -> None:
        while self._waiters:
            waiter = self._waiters.popleft()
            if not waiter.done():
                waiter.set_result(None)  # hand-off: in_flight is unchanged, the permit changes hands
                return
        self._in_flight -= 1
