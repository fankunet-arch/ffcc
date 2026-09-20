"""Pure, deterministic field-level merge of ``SourceResult``s (Phase 3 C1).

No network, no clock, no asyncio, no adapter import: ``merge_source_results``
is a pure function of ``(number, results, policy)``. Later phases (batch,
retry) can therefore test merge correctness offline.

Trust model -- fail closed
--------------------------
Provenance authority is the **slot** a result occupies (the configured source
id it was executed for) plus the **actual values** in its metadata. Nothing an
adapter *claims* is believed:

- a result whose ``source_id`` differs from its slot's, a non-``SourceResult``,
  or a ``SUCCESS`` whose ``metadata.number`` is not the requested number is
  replaced by an ``INVALID_RESPONSE`` result for that slot and contributes
  nothing (a buggy adapter returning another film must not contaminate the
  aggregate);
- only ``SUCCESS`` results contribute; partial metadata attached to
  ``PARSE_ERROR`` / ``INVALID_RESPONSE`` is never used;
- the metadata's own ``field_sources`` are ignored entirely; the aggregate's
  ``field_sources`` are recomputed from who supplied which value, so a forged
  ``field_sources["title"] = ("other_source",)`` cannot leak into provenance.

Merge rules (frozen in ``docs/specifications/PHASE3_AGGREGATION_CONTRACT.md``)
------------------------------------------------------------------------------
- ``number``: always the requested canonical number; provenance = every
  contributing source, in default source order.
- scalars (``title studio publisher release runtime plot``): the first
  non-empty value in that field's priority order. Non-empty = not ``None`` and
  (for ``str``) not blank; an ``int`` runtime of 0 is a value. Provenance =
  every contributing source whose value is *exactly equal* to the selected one
  (priority order); different values are recorded as a :class:`FieldConflict`.
- collections (``actors tags poster_urls thumb_urls fanart_urls extrafanart
  source_urls``): ordered unique union following the field's priority order;
  exact string equality only (no case-folding, translation or fuzzy matching);
  blank items are skipped. Provenance = every source that supplied at least one
  non-blank item.
- ``external_ids``: key by key, first (highest priority) value wins, never
  last-write-wins; a different value for an existing key is a conflict.
"""

from __future__ import annotations

from typing import Mapping, Sequence

from fc2_metadata_core.aggregation.models import (
    OPERATIONAL_FAILURE_STATUSES,
    AggregateStatus,
    AggregationInputError,
    AggregationResult,
    FieldConflict,
    SourceExecutionTrace,
)
from fc2_metadata_core.aggregation.policy import (
    COLLECTION_MERGE_FIELDS,
    FIELD_ORDER,
    SCALAR_MERGE_FIELDS,
    AggregationPolicy,
)
from fc2_metadata_core.models.metadata import NormalizedMetadata
from fc2_metadata_core.models.source_result import SourceErrorKind, SourceResult, SourceStatus
from fc2_metadata_core.sources.base import require_canonical_number

__all__ = ["merge_source_results", "validate_source_result", "invalid_response_result"]


def invalid_response_result(
    source_id: str,
    detail: str,
    *,
    elapsed_ms: float = 0.0,
    error_kind: SourceErrorKind = SourceErrorKind.RESULT_CONTRACT_MISMATCH,
) -> SourceResult:
    """The fail-closed replacement for a result that cannot be trusted.

    ``error_kind`` defaults to ``RESULT_CONTRACT_MISMATCH`` (wrong ``source_id`` /
    number / type); the execution boundary passes ``ADAPTER_EXCEPTION`` for an
    adapter that raised. Neither is ever retried.
    """
    return SourceResult(
        source_id=source_id,
        status=SourceStatus.INVALID_RESPONSE,
        metadata=None,
        elapsed_ms=elapsed_ms,
        error_kind=error_kind,
        error_detail=detail,
    )


def validate_source_result(
    expected_source_id: str, number: str, candidate: object, *, elapsed_ms: float = 0.0
) -> SourceResult:
    """Return ``candidate`` if it is trustworthy for ``(expected_source_id, number)``,
    otherwise an ``INVALID_RESPONSE`` result for that source. Idempotent.
    """
    if not isinstance(candidate, SourceResult):
        return invalid_response_result(
            expected_source_id,
            f"{expected_source_id}: adapter returned {type(candidate).__name__}, not a SourceResult",
            elapsed_ms=elapsed_ms,
        )
    if candidate.source_id != expected_source_id:
        return invalid_response_result(
            expected_source_id,
            f"{expected_source_id}: adapter returned a result labelled source_id "
            f"{candidate.source_id!r}; discarded",
            elapsed_ms=candidate.elapsed_ms,
        )
    if candidate.status is SourceStatus.SUCCESS:
        metadata = candidate.metadata
        if metadata is None or metadata.number != number:
            got = None if metadata is None else metadata.number
            return invalid_response_result(
                expected_source_id,
                f"{expected_source_id}: SUCCESS result is for {got!r}, requested {number}; discarded",
                elapsed_ms=candidate.elapsed_ms,
            )
    return candidate


def _has_value(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip() != ""
    return True


def _merge_scalar(
    order: tuple[str, ...], by_id: Mapping[str, NormalizedMetadata], field_name: str
) -> tuple[str | int | None, tuple[str, ...], FieldConflict | None]:
    offered = [
        (sid, getattr(by_id[sid], field_name))
        for sid in order
        if sid in by_id and _has_value(getattr(by_id[sid], field_name))
    ]
    if not offered:
        return None, (), None
    selected_source, selected_value = offered[0]
    agreeing = tuple(sid for sid, value in offered if value == selected_value and type(value) is type(selected_value))
    losers = tuple(
        (sid, value)
        for sid, value in offered
        if not (value == selected_value and type(value) is type(selected_value))
    )
    conflict = (
        FieldConflict(field_name, selected_source, selected_value, losers) if losers else None
    )
    return selected_value, agreeing, conflict


def _merge_collection(
    order: tuple[str, ...], by_id: Mapping[str, NormalizedMetadata], field_name: str
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    seen: set[str] = set()
    items: list[str] = []
    contributors: list[str] = []
    for sid in order:
        metadata = by_id.get(sid)
        if metadata is None:
            continue
        provided = False
        for item in getattr(metadata, field_name):
            if not _has_value(item):
                continue
            provided = True
            if item not in seen:
                seen.add(item)
                items.append(item)
        if provided:
            contributors.append(sid)
    return tuple(items), tuple(contributors)


def _merge_external_ids(
    order: tuple[str, ...], by_id: Mapping[str, NormalizedMetadata]
) -> tuple[dict[str, str], tuple[str, ...], list[FieldConflict]]:
    selected: dict[str, tuple[str, str]] = {}  # key -> (source_id, value)
    losers: dict[str, list[tuple[str, str]]] = {}
    contributors: list[str] = []
    for sid in order:
        metadata = by_id.get(sid)
        if metadata is None:
            continue
        provided = False
        for key, value in metadata.external_ids.items():
            if not (_has_value(key) and _has_value(value)):
                continue
            provided = True
            if key not in selected:
                selected[key] = (sid, value)
            elif selected[key][1] != value:
                losers.setdefault(key, []).append((sid, value))
        if provided:
            contributors.append(sid)
    conflicts = [
        FieldConflict("external_ids", selected[key][0], selected[key][1], tuple(losers[key]), key=key)
        for key in selected
        if key in losers
    ]
    return {key: pair[1] for key, pair in selected.items()}, tuple(contributors), conflicts


def merge_source_results(
    number: str,
    source_results: Sequence[object],
    policy: AggregationPolicy,
    *,
    disabled_source_ids: Sequence[str] = (),
    elapsed_ms: float = 0.0,
    execution_traces: Sequence[SourceExecutionTrace] | None = None,
) -> AggregationResult:
    """Merge one result per enabled source into an :class:`AggregationResult`.

    ``source_results`` is matched **by position** to ``policy.source_order``
    (that is how a result is tied to the configured source it was executed
    for); a different length is a caller bug (:class:`AggregationInputError`),
    a non-canonical ``number`` raises ``InvalidCanonicalNumberInputError``.
    ``execution_traces`` (C2, optional) must be one trace per result, same order,
    each ``final_result`` equal to the (validated) result -- else
    :class:`AggregationInputError`. Only the **final** results are merged; retry
    history never contributes data. Everything else -- including hostile or buggy results -- yields a normal
    ``AggregationResult``.
    """
    require_canonical_number(number)
    if len(source_results) != len(policy.source_order):
        raise AggregationInputError(
            f"expected {len(policy.source_order)} source result(s) (one per enabled source), "
            f"got {len(source_results)}"
        )

    sanitized = tuple(
        validate_source_result(slot_id, number, candidate)
        for slot_id, candidate in zip(policy.source_order, source_results)
    )
    traces: tuple[SourceExecutionTrace, ...] = ()
    if execution_traces is not None:
        traces = tuple(execution_traces)
        if len(traces) != len(sanitized) or any(
            t.source_id != r.source_id or t.final_result != r for t, r in zip(traces, sanitized)
        ):
            raise AggregationInputError(
                "execution_traces must match the (validated) source results one-to-one, in order"
            )
    by_id: dict[str, NormalizedMetadata] = {
        result.source_id: result.metadata
        for result in sanitized
        if result.status is SourceStatus.SUCCESS and result.metadata is not None
    }
    contributing = tuple(sid for sid in policy.source_order if sid in by_id)
    has_operational_failure = any(r.status in OPERATIONAL_FAILURE_STATUSES for r in sanitized)

    if not contributing:
        return AggregationResult(
            number=number,
            status=AggregateStatus.FAILED,
            metadata=None,
            source_results=sanitized,
            disabled_source_ids=tuple(disabled_source_ids),
            elapsed_ms=elapsed_ms,
            source_execution_traces=traces,
        )

    values: dict[str, object] = {"number": number}
    provenance: dict[str, tuple[str, ...]] = {"number": contributing}
    conflicts: list[FieldConflict] = []

    for field_name in SCALAR_MERGE_FIELDS:
        value, agreeing, conflict = _merge_scalar(policy.priority_for(field_name), by_id, field_name)
        if value is not None:
            values[field_name] = value
            provenance[field_name] = agreeing
        if conflict is not None:
            conflicts.append(conflict)

    for field_name in COLLECTION_MERGE_FIELDS:
        items, contributors = _merge_collection(policy.priority_for(field_name), by_id, field_name)
        if items:
            values[field_name] = items
            provenance[field_name] = contributors

    external_ids, id_contributors, id_conflicts = _merge_external_ids(
        policy.priority_for("external_ids"), by_id
    )
    if external_ids:
        values["external_ids"] = external_ids
        provenance["external_ids"] = id_contributors
    conflicts.extend(id_conflicts)

    ordered_conflicts = sorted(
        conflicts, key=lambda c: (FIELD_ORDER.index(c.field), c.key or "")
    )
    metadata = NormalizedMetadata(
        **values,  # type: ignore[arg-type]
        field_sources={name: provenance[name] for name in FIELD_ORDER if name in provenance},
    )
    return AggregationResult(
        number=number,
        status=AggregateStatus.PARTIAL if has_operational_failure else AggregateStatus.SUCCESS,
        metadata=metadata,
        source_results=sanitized,
        contributing_source_ids=contributing,
        conflicts=tuple(ordered_conflicts),
        disabled_source_ids=tuple(disabled_source_ids),
        elapsed_ms=elapsed_ms,
        source_execution_traces=traces,
    )
