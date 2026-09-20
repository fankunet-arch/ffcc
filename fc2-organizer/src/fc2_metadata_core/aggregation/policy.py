"""Aggregation policy: which source wins which field. Provider-agnostic.

The policy knows source *ids* only as opaque strings handed to it by
configuration. There is no provider-specific ``if source == ...`` anywhere in
the aggregation package (a test scans the source for that): the default order
is data (``aggregation.defaults``), and per-field overrides are data too.

Priority semantics (frozen in ``PHASE3_AGGREGATION_CONTRACT.md``):

- ``source_order`` (the enabled sources in configuration order) is the
  default priority for every field.
- ``field_priority`` may override the order for individual fields. An
  override lists *some* sources; the remaining enabled sources follow in
  their default order, so every field always has a total order over all
  enabled sources -- deterministic, never dependent on ``set`` / hash order
  or on async completion order.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

from fc2_metadata_core.errors import FC2MetadataCoreError

__all__ = [
    "AggregationPolicy",
    "AggregationConfigError",
    "SCALAR_MERGE_FIELDS",
    "COLLECTION_MERGE_FIELDS",
    "MAPPING_MERGE_FIELDS",
    "PRIORITY_OVERRIDABLE_FIELDS",
    "FIELD_ORDER",
]


class AggregationConfigError(FC2MetadataCoreError, ValueError):
    """Invalid aggregation configuration; raised *before* any network request."""


# Scalars merged "first non-empty value by field priority". ``number`` is
# deliberately absent: the final number is always the requested canonical
# number, never chosen from a source.
SCALAR_MERGE_FIELDS = ("title", "studio", "publisher", "release", "runtime", "plot")
# Collections merged as an ordered, exact-string-equality unique union.
COLLECTION_MERGE_FIELDS = (
    "actors",
    "tags",
    "poster_urls",
    "thumb_urls",
    "fanart_urls",
    "extrafanart",
    "source_urls",
)
# Mappings merged key by key, first (highest priority) value wins.
MAPPING_MERGE_FIELDS = ("external_ids",)

PRIORITY_OVERRIDABLE_FIELDS = SCALAR_MERGE_FIELDS + COLLECTION_MERGE_FIELDS + MAPPING_MERGE_FIELDS
# Canonical field order used for ``field_sources`` / conflicts, so output never
# depends on dict insertion accidents.
FIELD_ORDER = ("number",) + PRIORITY_OVERRIDABLE_FIELDS


def _validate_id_tuple(label: str, ids: object) -> tuple[str, ...]:
    if not isinstance(ids, tuple):
        raise AggregationConfigError(f"{label} must be a tuple of source ids, got {type(ids).__name__}")
    seen: set[str] = set()
    for source_id in ids:
        if not isinstance(source_id, str) or not source_id.strip() or source_id != source_id.strip():
            raise AggregationConfigError(f"{label}: invalid source id {source_id!r}")
        if source_id in seen:
            raise AggregationConfigError(f"{label}: duplicate source id {source_id!r}")
        seen.add(source_id)
    return ids


@dataclass(frozen=True, slots=True)
class AggregationPolicy:
    """Immutable priority table.

    ``source_order``: enabled source ids, default priority (highest first).
    ``field_priority``: ``((field, full_order), ...)`` -- built by :meth:`build`,
    which expands each partial override to a full order over ``source_order``.
    Construct with :meth:`build`; direct construction validates the same
    invariants but requires already-expanded, immutable arguments.
    """

    source_order: tuple[str, ...]
    field_priority: tuple[tuple[str, tuple[str, ...]], ...] = ()

    def __post_init__(self) -> None:
        order = _validate_id_tuple("source_order", self.source_order)
        if not order:
            raise AggregationConfigError("source_order must not be empty")
        if not isinstance(self.field_priority, tuple):
            raise AggregationConfigError("field_priority must be a tuple of (field, order) pairs")
        seen_fields: set[str] = set()
        for entry in self.field_priority:
            if not (isinstance(entry, tuple) and len(entry) == 2):
                raise AggregationConfigError("field_priority entries must be (field, order) pairs")
            field_name, full_order = entry
            if field_name not in PRIORITY_OVERRIDABLE_FIELDS:
                raise AggregationConfigError(f"field_priority: {field_name!r} is not an overridable field")
            if field_name in seen_fields:
                raise AggregationConfigError(f"field_priority: duplicate field {field_name!r}")
            seen_fields.add(field_name)
            _validate_id_tuple(f"field_priority[{field_name!r}]", full_order)
            if set(full_order) != set(order) or len(full_order) != len(order):
                raise AggregationConfigError(
                    f"field_priority[{field_name!r}] must be a full ordering of source_order"
                )

    @classmethod
    def build(
        cls,
        source_order: Iterable[str],
        overrides: Mapping[str, Iterable[str]] | None = None,
    ) -> "AggregationPolicy":
        """Validate ``overrides`` and expand each to a full order.

        Errors (:class:`AggregationConfigError`): unknown/non-overridable field
        name (including ``number``), a source id not in ``source_order``, a
        duplicate id inside one override, an empty override.
        """
        order = tuple(source_order)
        _validate_id_tuple("source_order", order)
        expanded: list[tuple[str, tuple[str, ...]]] = []
        for field_name in sorted((overrides or {}).keys(), key=_field_sort_key):
            if field_name not in PRIORITY_OVERRIDABLE_FIELDS:
                raise AggregationConfigError(
                    f"field_priority: {field_name!r} is not an overridable field "
                    f"(allowed: {', '.join(PRIORITY_OVERRIDABLE_FIELDS)})"
                )
            listed = overrides[field_name]  # type: ignore[index]
            if isinstance(listed, (str, bytes)):
                raise AggregationConfigError(f"field_priority[{field_name!r}] must be a list of source ids")
            listed_ids = tuple(listed)
            if not listed_ids:
                raise AggregationConfigError(f"field_priority[{field_name!r}] must not be empty")
            _validate_id_tuple(f"field_priority[{field_name!r}]", listed_ids)
            unknown = [sid for sid in listed_ids if sid not in order]
            if unknown:
                raise AggregationConfigError(
                    f"field_priority[{field_name!r}] names source(s) that are not configured: {unknown!r}"
                )
            rest = tuple(sid for sid in order if sid not in listed_ids)
            expanded.append((field_name, listed_ids + rest))
        return cls(source_order=order, field_priority=tuple(expanded))

    def priority_for(self, field_name: str) -> tuple[str, ...]:
        """Total order over the enabled sources for ``field_name`` (highest first)."""
        for name, full_order in self.field_priority:
            if name == field_name:
                return full_order
        return self.source_order


def _field_sort_key(field_name: object) -> tuple[int, str]:
    text = str(field_name)
    try:
        return (FIELD_ORDER.index(text), text)
    except ValueError:
        return (len(FIELD_ORDER), text)
