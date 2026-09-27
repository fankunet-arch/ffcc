"""Cooperative cancellation for ``execute`` (P4-C8 contract sections 10.8 and 27).

Imports only ``__future__`` and ``threading``. This is **not** asyncio cancellation and it never
interrupts a running syscall: ``execute`` checks the token before admitting each item.
"""

from __future__ import annotations

import threading

__all__ = ["CancellationToken"]


class CancellationToken:
    """A one-way, idempotent, thread-safe stop request.

    ``cancel()`` may be called any number of times from any thread; once set, ``cancelled`` is
    ``True`` forever (there is no reset). Internally it holds exactly one ``threading.Event``.
    """

    __slots__ = ("_event",)

    def __init__(self) -> None:
        self._event = threading.Event()

    def cancel(self) -> None:
        self._event.set()

    @property
    def cancelled(self) -> bool:
        return self._event.is_set()
