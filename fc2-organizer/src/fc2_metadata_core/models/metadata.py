"""NormalizedMetadata: the FC2 Metadata Core's own metadata model.

This is a deliberately independent contract, not a copy of Amane's
``MediaMetadata`` (``src/amane/crawlers/models.py``). Phase 0 found that
Amane's model uses singular ``external_id`` / ``source_url``, while this
project's spec calls for plural, multi-source ``external_ids`` /
``source_urls`` so that Phase 3's field-level aggregation can track more
than one contributing source per film. Narrowing that shape down to
Amane's singular fields is explicitly deferred to the Phase 5 adapter; this
module must not be shaped around Amane's current fields.

R1 (Phase 1 review round 1) hardening
--------------------------------------
The independent Phase 1 review found two related holes, closed here:

- **F1 / R1-01**: construction previously accepted any value for scalar and
  collection fields (e.g. ``title=123``, ``actors=[123]``) without runtime
  type checking. That garbage data would silently sit in the object until
  something like ``meets_minimum_success()`` blew up on it with a bare
  ``AttributeError``/``TypeError`` -- an unrelated, undocumented exception
  leaking through what is supposed to be a domain contract boundary.
  ``NormalizedMetadata`` is a domain object: illegal data must be rejected
  at construction, as ``MetadataContractError``, never later.

- **F2 / R1-02**: ``NormalizedMetadata`` was a mutable dataclass holding
  mutable ``list``/``dict`` fields. A ``SourceResult`` built from a valid,
  minimum-success-satisfying instance could have that guarantee silently
  invalidated after construction by mutating the (still-referenced)
  ``NormalizedMetadata`` -- breaking ``SourceResult``'s own invariant
  outside of its ``__post_init__``. ``NormalizedMetadata`` is now a
  **deeply immutable value object**: the dataclass itself is frozen, every
  collection field is converted to an immutable snapshot (``tuple`` for
  sequences, ``types.MappingProxyType`` over a private copy for mappings,
  including nested list-valued mapping entries), and caller-owned input
  containers are copied at construction time so later mutation of the
  caller's own list/dict cannot reach back into the constructed object.

  This is a frozen architectural decision going forward: Phase 3's
  field-level aggregation must build merged metadata *functionally*
  (read immutable inputs, produce a new ``NormalizedMetadata``), never by
  mutating an already-published instance in place.
"""

from __future__ import annotations

from collections.abc import Iterable
from collections.abc import Mapping as MappingABC
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping

from fc2_metadata_core.errors import MetadataContractError
from fc2_metadata_core.normalize.fc2_number import is_valid_fc2_number

__all__ = ["NormalizedMetadata"]

_SCALAR_STR_FIELDS = ("number", "title", "studio", "publisher", "release", "plot")

_STR_SEQUENCE_FIELDS = (
    "actors",
    "tags",
    "poster_urls",
    "thumb_urls",
    "fanart_urls",
    "extrafanart",
    "source_urls",
)


def _coerce_str_tuple(field_name: str, value: object) -> tuple[str, ...]:
    """Validate that ``value`` is a sequence of ``str`` and snapshot it.

    Explicitly rejects a bare ``str``/``bytes`` (both are technically
    iterable-of-characters, which would otherwise silently accept e.g.
    ``actors="John Doe"`` as if it were a one-character-per-actor list).
    """
    if isinstance(value, (str, bytes)):
        raise MetadataContractError(
            f"{field_name} must be a sequence of str, not a bare str/bytes"
        )
    if not isinstance(value, Iterable):
        raise MetadataContractError(f"{field_name} must be a sequence of str")

    items: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise MetadataContractError(
                f"{field_name} elements must all be str, found {type(item)!r}"
            )
        items.append(item)
    return tuple(items)


def _coerce_str_str_mapping(field_name: str, value: object) -> Mapping[str, str]:
    """Validate a mapping of str -> str and snapshot it as an immutable copy."""
    if not isinstance(value, MappingABC):
        raise MetadataContractError(f"{field_name} must be a mapping of str to str")

    result: dict[str, str] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            raise MetadataContractError(
                f"{field_name} keys must all be str, found {type(key)!r}"
            )
        if not isinstance(item, str):
            raise MetadataContractError(
                f"{field_name} values must all be str, found {type(item)!r}"
            )
        result[key] = item
    return MappingProxyType(result)


def _coerce_field_sources_mapping(value: object) -> Mapping[str, tuple[str, ...]]:
    """Validate ``field_sources``: str -> sequence-of-str, snapshotted immutably."""
    if not isinstance(value, MappingABC):
        raise MetadataContractError(
            "field_sources must be a mapping of str to a sequence of str"
        )

    result: dict[str, tuple[str, ...]] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            raise MetadataContractError(
                f"field_sources keys must all be str, found {type(key)!r}"
            )
        result[key] = _coerce_str_tuple(f"field_sources[{key!r}]", item)
    return MappingProxyType(result)


@dataclass(frozen=True, slots=True)
class NormalizedMetadata:
    """Partial-safe, source-agnostic, deeply immutable FC2 film metadata.

    Every field except ``number``/``title`` may be absent (``None`` for
    scalars, empty for collections) -- ``NormalizedMetadata()`` with no
    arguments at all is a valid, fully partial instance. The only frozen
    success rule (see :meth:`meets_minimum_success`) is:

        minimum success = a valid canonical FC2 number + a non-empty title

    Construction validates every field's runtime type and rejects anything
    that does not match the public contract with :class:`MetadataContractError`
    -- there is no path from a successfully-constructed instance to a bare
    ``AttributeError``/``TypeError`` later. Sequence fields are stored as
    ``tuple``; ``external_ids``/``field_sources`` are stored as
    ``types.MappingProxyType`` snapshots (with ``field_sources`` values
    themselves snapshotted to ``tuple``). Caller-owned input containers are
    copied at construction time, so mutating them afterwards never reaches
    the constructed instance, and the instance itself exposes no mutable
    attribute, list, or dict to the outside once built.
    """

    number: str | None = None
    title: str | None = None
    studio: str | None = None
    publisher: str | None = None
    release: str | None = None
    runtime: int | None = None
    actors: tuple[str, ...] = field(default_factory=tuple)
    tags: tuple[str, ...] = field(default_factory=tuple)
    plot: str | None = None

    poster_urls: tuple[str, ...] = field(default_factory=tuple)
    thumb_urls: tuple[str, ...] = field(default_factory=tuple)
    fanart_urls: tuple[str, ...] = field(default_factory=tuple)
    extrafanart: tuple[str, ...] = field(default_factory=tuple)

    source_urls: tuple[str, ...] = field(default_factory=tuple)
    external_ids: Mapping[str, str] = field(default_factory=dict)
    field_sources: Mapping[str, tuple[str, ...]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self._validate_scalars()
        self._freeze_collections()

    def _validate_scalars(self) -> None:
        for name in _SCALAR_STR_FIELDS:
            value = getattr(self, name)
            if value is not None and not isinstance(value, str):
                raise MetadataContractError(
                    f"{name} must be a str or None, got {type(value)!r}"
                )

        if self.runtime is not None:
            if not isinstance(self.runtime, int) or isinstance(self.runtime, bool):
                raise MetadataContractError("runtime must be an int or None")
            if self.runtime < 0:
                raise MetadataContractError("runtime must not be negative")

    def _freeze_collections(self) -> None:
        for name in _STR_SEQUENCE_FIELDS:
            coerced = _coerce_str_tuple(name, getattr(self, name))
            object.__setattr__(self, name, coerced)

        object.__setattr__(
            self,
            "external_ids",
            _coerce_str_str_mapping("external_ids", self.external_ids),
        )
        object.__setattr__(
            self,
            "field_sources",
            _coerce_field_sources_mapping(self.field_sources),
        )

    def has_valid_canonical_number(self) -> bool:
        """True iff ``number`` is a well-formed canonical FC2 number.

        Total: never raises for any successfully-constructed instance.
        """
        return self.number is not None and is_valid_fc2_number(self.number)

    def has_non_empty_title(self) -> bool:
        """True iff ``title`` is set and not just whitespace.

        Total: never raises for any successfully-constructed instance --
        ``title`` is guaranteed to be ``str | None`` by construction.
        """
        return self.title is not None and self.title.strip() != ""

    def meets_minimum_success(self) -> bool:
        """The one frozen success condition for this Phase.

        ``minimum success = canonical FC2 number + non-empty title``.
        Every other field may be missing/partial without affecting this.
        Total predicate: always returns ``bool`` for any instance that was
        successfully constructed, never raises.
        """
        return self.has_valid_canonical_number() and self.has_non_empty_title()
