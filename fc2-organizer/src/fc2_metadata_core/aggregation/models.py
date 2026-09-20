"""Aggregation result model (Phase 3 C1). Immutable; validated at construction.

``AggregationResult`` is what one aggregate lookup returns: the requested
number, an aggregate status, the merged metadata (or ``None``), **every**
per-source ``SourceResult`` (also on failure -- later retry / UI logic needs
them), which sources actually contributed data, and the field conflicts that
were resolved. Its ``__post_init__`` enforces the status semantics so an
inconsistent result cannot be constructed:

``SUCCESS``
    merged metadata meets minimum success (canonical number + non-empty title)
    **and** no enabled source had an *operational* failure. ``NOT_FOUND`` is a
    normal coverage gap and never counts as one.
``PARTIAL``
    merged metadata meets minimum success, but at least one enabled source
    ended ``BLOCKED`` / ``RATE_LIMITED`` / ``NETWORK_ERROR`` / ``PARSE_ERROR`` /
    ``INVALID_RESPONSE``.
``FAILED``
    no source produced usable data; ``metadata`` is ``None``. Every
    ``SourceResult`` is still kept.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from fc2_metadata_core.errors import FC2MetadataCoreError
from fc2_metadata_core.models.metadata import NormalizedMetadata
from fc2_metadata_core.models.source_result import SourceResult, SourceStatus
from fc2_metadata_core.normalize.fc2_number import is_valid_fc2_number

__all__ = [
    "AggregateStatus",
    "AggregationResult",
    "FieldConflict",
    "AggregationContractError",
    "AggregationInputError",
    "OPERATIONAL_FAILURE_STATUSES",
]


class AggregationContractError(FC2MetadataCoreError, ValueError):
    """An ``AggregationResult`` / ``FieldConflict`` violates its invariants."""


class AggregationInputError(FC2MetadataCoreError, ValueError):
    """The caller handed the merge function inconsistent input (a caller bug)."""


class AggregateStatus(Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"


# Source outcomes that mean "the source did not answer properly" -- as opposed
# to NOT_FOUND ("the source answered: it does not have this film").
OPERATIONAL_FAILURE_STATUSES = frozenset(
    {
        SourceStatus.BLOCKED,
        SourceStatus.RATE_LIMITED,
        SourceStatus.NETWORK_ERROR,
        SourceStatus.PARSE_ERROR,
        SourceStatus.INVALID_RESPONSE,
    }
)


@dataclass(frozen=True, slots=True)
class FieldConflict:
    """A resolved disagreement between sources, for inspection only.

    ``selected_*`` is what the aggregate kept (highest priority for the field);
    ``alternatives`` lists ``(source_id, value)`` for every lower-priority source
    that offered a *different* value, in priority order. ``key`` is the mapping
    key for ``external_ids`` conflicts and ``None`` for scalar fields.
    """

    field: str
    selected_source_id: str
    selected_value: str | int
    alternatives: tuple[tuple[str, str | int], ...]
    key: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.field, str) or not self.field:
            raise AggregationContractError("FieldConflict.field must be a non-empty str")
        if not isinstance(self.selected_source_id, str) or not self.selected_source_id:
            raise AggregationContractError("FieldConflict.selected_source_id must be a non-empty str")
        if not isinstance(self.alternatives, tuple) or not self.alternatives:
            raise AggregationContractError("FieldConflict.alternatives must be a non-empty tuple")
        for entry in self.alternatives:
            if not (isinstance(entry, tuple) and len(entry) == 2 and isinstance(entry[0], str)):
                raise AggregationContractError("FieldConflict.alternatives must be (source_id, value) pairs")
            if entry[1] == self.selected_value and type(entry[1]) is type(self.selected_value):
                raise AggregationContractError("an alternative equal to the selected value is not a conflict")


@dataclass(frozen=True, slots=True)
class AggregationResult:
    number: str
    status: AggregateStatus
    metadata: NormalizedMetadata | None
    source_results: tuple[SourceResult, ...]
    contributing_source_ids: tuple[str, ...] = ()
    conflicts: tuple[FieldConflict, ...] = ()
    disabled_source_ids: tuple[str, ...] = ()
    elapsed_ms: float = 0.0

    def __post_init__(self) -> None:
        if not is_valid_fc2_number(self.number):
            raise AggregationContractError(f"number must be a canonical FC2 number, got {self.number!r}")
        if not isinstance(self.status, AggregateStatus):
            raise AggregationContractError("status must be an AggregateStatus")
        if not isinstance(self.source_results, tuple) or not self.source_results:
            raise AggregationContractError("source_results must be a non-empty tuple")
        if not all(isinstance(result, SourceResult) for result in self.source_results):
            raise AggregationContractError("source_results must contain only SourceResult")
        ids = [result.source_id for result in self.source_results]
        if len(set(ids)) != len(ids):
            raise AggregationContractError("source_results contain a duplicate source_id")
        if not isinstance(self.contributing_source_ids, tuple) or not all(
            sid in ids for sid in self.contributing_source_ids
        ):
            raise AggregationContractError("contributing_source_ids must be a tuple of result source ids")
        if not isinstance(self.conflicts, tuple) or not all(isinstance(c, FieldConflict) for c in self.conflicts):
            raise AggregationContractError("conflicts must be a tuple of FieldConflict")
        if not isinstance(self.disabled_source_ids, tuple):
            raise AggregationContractError("disabled_source_ids must be a tuple")
        if isinstance(self.elapsed_ms, bool) or not isinstance(self.elapsed_ms, (int, float)) or self.elapsed_ms < 0:
            raise AggregationContractError("elapsed_ms must be a non-negative number")

        by_id = {result.source_id: result for result in self.source_results}
        for sid in self.contributing_source_ids:
            if by_id[sid].status is not SourceStatus.SUCCESS:
                raise AggregationContractError(f"contributing source {sid!r} did not succeed")

        has_operational_failure = any(
            result.status in OPERATIONAL_FAILURE_STATUSES for result in self.source_results
        )
        if self.status is AggregateStatus.FAILED:
            if self.metadata is not None:
                raise AggregationContractError("status=failed must not carry metadata")
            if self.contributing_source_ids:
                raise AggregationContractError("status=failed cannot have contributing sources")
            return
        if not isinstance(self.metadata, NormalizedMetadata) or not self.metadata.meets_minimum_success():
            raise AggregationContractError(
                f"status={self.status.value} requires metadata that meets minimum success"
            )
        if self.metadata.number != self.number:
            raise AggregationContractError("aggregated metadata.number must equal the requested number")
        if not self.contributing_source_ids:
            raise AggregationContractError(f"status={self.status.value} requires at least one contributing source")
        if self.status is AggregateStatus.SUCCESS and has_operational_failure:
            raise AggregationContractError("status=success requires no operational source failure")
        if self.status is AggregateStatus.PARTIAL and not has_operational_failure:
            raise AggregationContractError("status=partial requires at least one operational source failure")

    # -- inspection helpers (pure) ------------------------------------------------

    @property
    def source_order(self) -> tuple[str, ...]:
        return tuple(result.source_id for result in self.source_results)

    def result_for(self, source_id: str) -> SourceResult | None:
        for result in self.source_results:
            if result.source_id == source_id:
                return result
        return None

    @property
    def operational_failure_source_ids(self) -> tuple[str, ...]:
        return tuple(r.source_id for r in self.source_results if r.status in OPERATIONAL_FAILURE_STATUSES)

    @property
    def not_found_source_ids(self) -> tuple[str, ...]:
        return tuple(r.source_id for r in self.source_results if r.status is SourceStatus.NOT_FOUND)
