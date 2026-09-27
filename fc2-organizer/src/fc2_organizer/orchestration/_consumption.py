"""Process-local one-time consumption registries (P4-C8 contract sections 12.2, 18.1, 25.4, 26).

Private (never exported). Three registries, each a ``threading.Lock``-protected ``set[str]``:

* ``PREVIEW_EXECUTIONS`` -- ``BatchPreview.preview_id`` values already handed to ``execute``;
* ``RESULT_RETRIES``     -- ``BatchExecutionResult.result_id`` values already retried;
* ``RETRY_MERGES``       -- retry-round ``result_id`` values already merged.

Only 32-character lowercase hex id strings are stored -- never a preview, a result, a
``RetryMaterial`` or artifact bytes -- and nothing is persisted: the registries live and die with
the process (contract section 33). Imports only ``__future__`` and ``threading``.
"""

from __future__ import annotations

import threading

__all__ = ["ConsumptionRegistry", "PREVIEW_EXECUTIONS", "RESULT_RETRIES", "RETRY_MERGES"]

_HEX_DIGITS = frozenset("0123456789abcdef")


def _is_id(value: object) -> bool:
    return type(value) is str and len(value) == 32 and _HEX_DIGITS.issuperset(value)


class ConsumptionRegistry:
    """One process-local registry of consumed ids with an atomic check-and-register."""

    __slots__ = ("_lock", "_ids")

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._ids: set[str] = set()

    def register(self, consumed_id: str) -> bool:
        """Atomically register ``consumed_id``. ``True`` if it was not registered before (this caller
        consumed it), ``False`` if it already was (nothing changes)."""
        if not _is_id(consumed_id):
            raise ValueError("a consumption id is 32 lowercase hex characters")
        with self._lock:
            if consumed_id in self._ids:
                return False
            self._ids.add(consumed_id)
            return True

    def is_registered(self, consumed_id: str) -> bool:
        """Read-only query; never registers anything."""
        if not _is_id(consumed_id):
            raise ValueError("a consumption id is 32 lowercase hex characters")
        with self._lock:
            return consumed_id in self._ids


PREVIEW_EXECUTIONS = ConsumptionRegistry()
RESULT_RETRIES = ConsumptionRegistry()
RETRY_MERGES = ConsumptionRegistry()
