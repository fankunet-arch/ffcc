"""Source registry: enumerate, look up, and instantiate registered adapters.

Deliberately not an ``if source_id == "a": ... elif source_id == "b": ...``
chain -- adding a new adapter is one :meth:`SourceRegistry.register` call,
never an edit to a growing conditional (Phase 2 requirement).
"""

from __future__ import annotations

from typing import Callable

from fc2_metadata_core.errors import FC2MetadataCoreError
from fc2_metadata_core.sources.base import SourceAdapter

__all__ = [
    "SourceRegistry",
    "SourceRegistryError",
    "DuplicateSourceIdError",
    "UnknownSourceIdError",
]


class SourceRegistryError(FC2MetadataCoreError):
    """Base class for source-registry misuse."""


class DuplicateSourceIdError(SourceRegistryError):
    """Raised when registering a ``source_id`` that is already registered."""


class UnknownSourceIdError(SourceRegistryError, KeyError):
    """Raised when looking up a ``source_id`` that was never registered."""


SourceFactory = Callable[..., SourceAdapter]


class SourceRegistry:
    """Enumerable, lookup-by-id registry of source adapter factories.

    A "factory" is usually just the adapter class itself (since
    ``SourceAdapter.__init__`` already accepts an optional ``base_url``
    override), stored rather than a single shared instance, so callers can
    construct a fresh adapter -- or one with a non-default ``base_url`` --
    per lookup without the registry needing to know adapter-specific
    construction concerns.
    """

    def __init__(self) -> None:
        self._factories: dict[str, SourceFactory] = {}

    def register(self, source_id: str, factory: SourceFactory) -> None:
        if not isinstance(source_id, str) or not source_id.strip():
            raise SourceRegistryError("source_id must be a non-empty string")
        if source_id in self._factories:
            raise DuplicateSourceIdError(f"source_id {source_id!r} is already registered")
        self._factories[source_id] = factory

    def unregister(self, source_id: str) -> None:
        try:
            del self._factories[source_id]
        except KeyError:
            raise UnknownSourceIdError(source_id) from None

    def source_ids(self) -> tuple[str, ...]:
        """All registered ``source_id``s, in registration order."""
        return tuple(self._factories)

    def create(self, source_id: str, **kwargs: object) -> SourceAdapter:
        """Instantiate the adapter registered under ``source_id``.

        Extra keyword arguments (e.g. ``base_url=``) are forwarded to the
        factory unchanged.
        """
        try:
            factory = self._factories[source_id]
        except KeyError:
            raise UnknownSourceIdError(source_id) from None
        return factory(**kwargs)

    def __contains__(self, source_id: object) -> bool:
        return source_id in self._factories

    def __len__(self) -> int:
        return len(self._factories)
