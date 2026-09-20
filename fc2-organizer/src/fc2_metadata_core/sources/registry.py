"""Source registry: enumerate, look up, and instantiate registered adapters.

Deliberately not an ``if source_id == "a": ... elif source_id == "b": ...``
chain -- adding a new adapter is one :meth:`SourceRegistry.register` call,
never an edit to a growing conditional (Phase 2 requirement).

Create boundary (Phase 3 C1, closes Phase 2 review finding P2-R-11)
-------------------------------------------------------------------
The Phase 3 dispatcher depends on ``registry.create(source_id)`` handing back
*the adapter for that id*. Phase 2's ``create`` returned whatever the factory
returned, so ``register("alias_x", Fc2dbNetAdapter)`` produced an adapter
whose own ``source_id`` was ``"fc2db_net"`` (its results would then be
attributed to the wrong source), and ``register("junk", lambda **k: 42)``
handed the dispatcher an ``int`` that would only blow up later as a bare
``AttributeError``. ``create`` now guarantees, or raises a
:class:`SourceRegistryError` subclass (never a bare ``TypeError`` /
``AttributeError``, never a foreign object):

- the factory ran without raising (otherwise :class:`SourceFactoryError`,
  original exception chained -- only ``Exception``; ``KeyboardInterrupt`` /
  ``SystemExit`` / cancellation are never swallowed);
- the result is a :class:`SourceAdapter` (otherwise
  :class:`InvalidSourceAdapterError`);
- its ``source_id`` equals the id it was requested / registered under
  (otherwise :class:`SourceIdMismatchError`).

Factories (not only classes) remain supported; the check is on the *result*.
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
    "SourceFactoryError",
    "InvalidSourceAdapterError",
    "SourceIdMismatchError",
]


class SourceRegistryError(FC2MetadataCoreError):
    """Base class for source-registry misuse."""


class DuplicateSourceIdError(SourceRegistryError):
    """Raised when registering a ``source_id`` that is already registered."""


class UnknownSourceIdError(SourceRegistryError, KeyError):
    """Raised when looking up a ``source_id`` that was never registered."""


class SourceFactoryError(SourceRegistryError):
    """The registered factory itself raised while building the adapter."""


class InvalidSourceAdapterError(SourceRegistryError):
    """The registered factory returned something that is not a ``SourceAdapter``."""


class SourceIdMismatchError(SourceRegistryError):
    """The adapter's own ``source_id`` differs from the id it was created under."""


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
        if not callable(factory):
            raise SourceRegistryError(
                f"factory for source_id {source_id!r} must be callable, got {type(factory).__name__}"
            )
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
        factory unchanged. Raises :class:`UnknownSourceIdError` for an
        unregistered id and the errors listed in the module docstring if the
        factory misbehaves; on success the returned object is a
        :class:`SourceAdapter` whose ``source_id`` is exactly ``source_id``.
        """
        try:
            factory = self._factories[source_id]
        except (KeyError, TypeError):  # TypeError: unhashable id
            raise UnknownSourceIdError(source_id) from None

        try:
            adapter = factory(**kwargs)
        except Exception as exc:
            raise SourceFactoryError(
                f"factory for source_id {source_id!r} raised {type(exc).__name__}"
            ) from exc

        if not isinstance(adapter, SourceAdapter):
            raise InvalidSourceAdapterError(
                f"factory for source_id {source_id!r} returned {type(adapter).__name__}, "
                "not a SourceAdapter"
            )
        if adapter.source_id != source_id:
            raise SourceIdMismatchError(
                f"factory registered as {source_id!r} produced an adapter whose "
                f"source_id is {adapter.source_id!r}"
            )
        return adapter

    def __contains__(self, source_id: object) -> bool:
        return source_id in self._factories

    def __len__(self) -> int:
        return len(self._factories)
