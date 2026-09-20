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

R2 (Phase 1 review round 2) hardening
--------------------------------------
The independent R1 review found the R1-01 fix incomplete (**F1 / R2-01**):
sequence-field coercion accepted *any* ``Iterable``, not just an ordered
``Sequence``. That silently accepted e.g. ``actors={"Alice": 1, "Bob": 2}``
(a ``dict`` is iterable -- iterating it yields only its keys, discarding
the values without warning) and ``actors={"Alice", "Bob"}`` (a ``set`` is
iterable but unordered, so the resulting tuple's element order would
depend on hash seed / insertion history rather than caller intent).

The accepted input contract for every sequence-shaped field (the seven
``_STR_SEQUENCE_FIELDS`` below, and each value of ``field_sources``) is now
frozen as ``collections.abc.Sequence[str]`` specifically -- not
``Iterable[str]``:

- ``list``/``tuple`` (or any other genuine ``Sequence``): accepted,
  snapshotted to ``tuple`` (unchanged from R1).
- ``str``/``bytes``: rejected (unchanged from R1).
- ``Mapping`` (``dict`` and friends): rejected explicitly, even though a
  ``dict`` already fails the ``Sequence`` check on its own -- this keeps
  the rejection reason explicit and defends against a hypothetical custom
  type registered as both.
- ``set``/``frozenset``: rejected. The Core deliberately does **not** sort
  and accept them: field order may carry source/display meaning that the
  Core must not invent on the caller's behalf.
- generator/iterator/arbitrary ``Iterable`` that is not a ``Sequence``:
  rejected *before* being consumed at all -- a one-shot iterable is never
  touched, so there is no risk of partial consumption or a mid-stream
  exception from something that was never a legal input.

**F2 / R2-02**: even restricted to ``Sequence``, a custom ``Sequence``
implementation could still raise mid-iteration (e.g. a broken
``__getitem__``). Such an exception is now caught while reading an
*accepted* Sequence and re-raised as ``MetadataContractError`` with the
original exception chained via ``raise ... from exc`` -- never leaked
as-is. Our own element-type ``MetadataContractError`` is re-raised
unchanged (never double-wrapped).
"""

from __future__ import annotations

from collections.abc import Mapping as MappingABC
from collections.abc import Sequence
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
    """Validate that ``value`` is an ordered ``Sequence[str]`` and snapshot it.

    R2/F1: the accepted input contract is ``collections.abc.Sequence``
    (e.g. ``list``/``tuple``), not merely ``Iterable``. Explicitly rejected:

    - a bare ``str``/``bytes`` (iterable-of-characters; would otherwise
      silently accept e.g. ``actors="John Doe"`` as a one-character list);
    - any ``Mapping`` (iterating it would silently yield only its keys,
      discarding the values -- checked explicitly even though a ``dict``
      already fails the ``Sequence`` check below, as defense in depth);
    - ``set``/``frozenset`` (unordered -- the Core must not invent an
      ordering, e.g. by sorting, on the caller's behalf);
    - a generator/iterator or any other merely-``Iterable``,
      non-``Sequence`` object (rejected before being consumed at all, so a
      one-shot iterable is never partially/fully drained by this check).

    R2/F2: if reading an *accepted* ``Sequence`` itself raises (a custom
    ``Sequence`` implementation misbehaving mid-iteration), that exception
    is not leaked as-is -- it is wrapped as ``MetadataContractError`` with
    the original exception chained via ``from``. Our own element-type
    ``MetadataContractError`` is re-raised unchanged, never double-wrapped.
    """
    if isinstance(value, (str, bytes)):
        raise MetadataContractError(
            f"{field_name} must be an ordered Sequence[str], not a bare str/bytes"
        )
    if isinstance(value, MappingABC):
        raise MetadataContractError(
            f"{field_name} must be an ordered Sequence[str], not a mapping"
        )
    if not isinstance(value, Sequence):
        raise MetadataContractError(
            f"{field_name} must be an ordered Sequence[str] (e.g. list or "
            f"tuple), got {type(value)!r}"
        )

    items: list[str] = []
    try:
        for item in value:
            if not isinstance(item, str):
                raise MetadataContractError(
                    f"{field_name} elements must all be str, found {type(item)!r}"
                )
            items.append(item)
    except MetadataContractError:
        raise
    except Exception as exc:
        raise MetadataContractError(
            f"{field_name} raised an unexpected error while being read: {exc}"
        ) from exc

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

    ``runtime`` is a non-negative ``int`` number of **whole minutes** (unit
    frozen at Phase 3 Entry C0-04; see the contract, section 2.1b). Sources
    that report a clock duration are converted by truncating the seconds
    (``55:59`` -> 55), never rounding. Before C0 only the *type* was frozen.
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
