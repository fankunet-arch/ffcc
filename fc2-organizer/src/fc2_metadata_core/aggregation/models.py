"""Aggregation result model (Phase 3 C1, hardened and extended in C2). Immutable.

``AggregationResult`` is what one aggregate lookup returns: the requested
number, an aggregate status, the merged metadata (or ``None``), **every**
per-source ``SourceResult`` (also on failure -- later retry / UI logic needs
them), which sources actually contributed data, the field conflicts that were
resolved, and (C2) one :class:`SourceExecutionTrace` per source recording how
many attempts it took.

Statuses
--------
``SUCCESS``
    merged metadata meets minimum success (canonical number + non-empty title)
    **and** no enabled source's *final* result is an operational failure.
    ``NOT_FOUND`` is a normal coverage gap and never counts as one.
``PARTIAL``
    merged metadata meets minimum success, but at least one enabled source's
    final result is ``BLOCKED`` / ``RATE_LIMITED`` / ``NETWORK_ERROR`` /
    ``PARSE_ERROR`` / ``INVALID_RESPONSE``.
``FAILED``
    no source produced usable data; ``metadata`` is ``None``. Every
    ``SourceResult`` is still kept.

Only a source's **final** result decides the status: a source that failed once
and then succeeded on a retry is a success (its first failure stays visible in
its trace).

What ``AggregationResult.__post_init__`` enforces (and therefore what "cannot be
built inconsistently" covers -- nothing more is claimed)
-------------------------------------------------------
* ``number`` canonical; ``status`` an :class:`AggregateStatus`;
  ``source_results`` a non-empty tuple of ``SourceResult`` with unique source ids;
* ``successful_source_ids`` = the ids of ``SUCCESS`` results, in ``source_results``
  order. ``FAILED``: ``metadata is None``, ``contributing_source_ids == ()`` (and
  so there is no ``SUCCESS`` result). ``SUCCESS``/``PARTIAL``: metadata meets
  minimum success with ``number == requested`` and ``contributing_source_ids ==
  successful_source_ids`` **exactly** (same members, same order) -- a ``SUCCESS``
  source can never be silently left out of the contributors;
* ``SUCCESS`` requires no operational failure among the final results;
  ``PARTIAL`` requires at least one;
* ``disabled_source_ids``: a tuple of distinct non-empty ``str`` that do not
  overlap ``source_results`` ids;
* ``conflicts``: each one names a conflict-capable field, uses ``key`` only for
  ``external_ids``, and refers only to contributing sources (selected source not
  repeated among its alternatives; alternatives distinct);
* ``source_execution_traces`` is either empty (a pure merge with no execution) or
  aligned one-to-one and in the same order with ``source_results``, each trace's
  ``final_result`` equal to the corresponding result; disabled sources have none.

**Not** verified (would mean re-running the merge): that ``metadata``'s field
values are what the merge rules would pick from the sources, that ``field_sources``
match, and that ``conflicts`` is the complete list. ``merge_source_results`` is the
only producer of these and is tested against the rules.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum

from fc2_metadata_core.aggregation.policy import MAPPING_MERGE_FIELDS, SCALAR_MERGE_FIELDS
from fc2_metadata_core.errors import FC2MetadataCoreError
from fc2_metadata_core.models.metadata import NormalizedMetadata
from fc2_metadata_core.models.source_result import (
    ALLOWED_ERROR_KINDS,
    SourceErrorKind,
    SourceResult,
    SourceStatus,
)
from fc2_metadata_core.normalize.fc2_number import is_valid_fc2_number

__all__ = [
    "AggregateStatus",
    "AggregationResult",
    "FieldConflict",
    "SourceAttempt",
    "SourceExecutionTrace",
    "AggregationContractError",
    "AggregationInputError",
    "OPERATIONAL_FAILURE_STATUSES",
    "CONFLICT_FIELDS",
]


class AggregationContractError(FC2MetadataCoreError, ValueError):
    """An ``AggregationResult`` / ``FieldConflict`` / trace violates its invariants."""


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

# Fields a ``FieldConflict`` may name: the scalar fields and external_ids
# (collections are unions, so they never conflict).
CONFLICT_FIELDS = SCALAR_MERGE_FIELDS + MAPPING_MERGE_FIELDS


def _is_number(value: object) -> bool:
    return not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value)


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
        if self.field not in CONFLICT_FIELDS:
            raise AggregationContractError(
                f"FieldConflict.field must be one of {CONFLICT_FIELDS}, got {self.field!r}"
            )
        if self.field in MAPPING_MERGE_FIELDS:
            if not isinstance(self.key, str) or not self.key.strip():
                raise AggregationContractError("an external_ids conflict needs a non-empty str key")
        elif self.key is not None:
            raise AggregationContractError(f"a {self.field!r} (scalar) conflict must not have a key")
        if not isinstance(self.selected_source_id, str) or not self.selected_source_id:
            raise AggregationContractError("FieldConflict.selected_source_id must be a non-empty str")
        if isinstance(self.selected_value, bool) or not isinstance(self.selected_value, (str, int)):
            raise AggregationContractError("FieldConflict.selected_value must be a str or int")
        if not isinstance(self.alternatives, tuple) or not self.alternatives:
            raise AggregationContractError("FieldConflict.alternatives must be a non-empty tuple")
        seen: set[str] = set()
        for entry in self.alternatives:
            if not (isinstance(entry, tuple) and len(entry) == 2 and isinstance(entry[0], str) and entry[0]):
                raise AggregationContractError("FieldConflict.alternatives must be (source_id, value) pairs")
            source_id, value = entry
            if isinstance(value, bool) or not isinstance(value, (str, int)):
                raise AggregationContractError("FieldConflict alternative values must be str or int")
            if source_id == self.selected_source_id:
                raise AggregationContractError("the selected source cannot also be one of its own alternatives")
            if source_id in seen:
                raise AggregationContractError(f"duplicate alternative source {source_id!r}")
            seen.add(source_id)
            if value == self.selected_value and type(value) is type(self.selected_value):
                raise AggregationContractError("an alternative equal to the selected value is not a conflict")


@dataclass(frozen=True, slots=True)
class SourceAttempt:
    """One attempt to fetch from one source, as observed by the engine.

    ``elapsed_ms`` is measured by the engine around the attempt, so it is real
    even when the adapter-returned ``SourceResult.elapsed_ms`` is 0 (P2-R-07).
    ``completed`` is ``False`` only for an attempt cut off by the source's
    wall-clock deadline. ``backoff_before_seconds`` is the pause that preceded
    this attempt (``0.0`` for the first). Nothing here can hold a response body,
    cookie or credential: only status, structured kind and timings.
    """

    sequence: int
    status: SourceStatus
    error_kind: SourceErrorKind | None
    elapsed_ms: float
    completed: bool = True
    backoff_before_seconds: float = 0.0

    def __post_init__(self) -> None:
        if isinstance(self.sequence, bool) or not isinstance(self.sequence, int) or self.sequence < 1:
            raise AggregationContractError("SourceAttempt.sequence must be an int >= 1")
        if not isinstance(self.status, SourceStatus):
            raise AggregationContractError("SourceAttempt.status must be a SourceStatus")
        if self.status is SourceStatus.SUCCESS:
            if self.error_kind is not None:
                raise AggregationContractError("a successful attempt has no error_kind")
        elif not isinstance(self.error_kind, SourceErrorKind) or self.error_kind not in ALLOWED_ERROR_KINDS[self.status]:
            raise AggregationContractError("a failed attempt needs an error_kind allowed for its status")
        if not _is_number(self.elapsed_ms) or self.elapsed_ms < 0:
            raise AggregationContractError("SourceAttempt.elapsed_ms must be a finite number >= 0")
        if not isinstance(self.completed, bool):
            raise AggregationContractError("SourceAttempt.completed must be a bool")
        if not _is_number(self.backoff_before_seconds) or self.backoff_before_seconds < 0:
            raise AggregationContractError("SourceAttempt.backoff_before_seconds must be a finite number >= 0")
        if self.sequence == 1 and self.backoff_before_seconds != 0:
            raise AggregationContractError("the first attempt has no backoff before it")


@dataclass(frozen=True, slots=True)
class SourceExecutionTrace:
    """How one source's execution went: every attempt and how it ended.

    ``attempts`` is in order (sequence ``1..n``, ``n <= max_attempts``). If the
    source's total wall-clock deadline ran out, ``deadline_exceeded`` is true and
    ``deadline_during`` says where: ``"attempt"`` (the last attempt was cut off:
    ``completed=False``) or ``"backoff"`` (the pause before attempt ``n + 1``
    ran out, so **attempt ``n + 1`` never started** -- it is absent from
    ``attempts``). ``final_result`` is the one result the merge used.
    """

    source_id: str
    attempts: tuple[SourceAttempt, ...]
    final_result: SourceResult
    max_attempts: int
    deadline_exceeded: bool = False
    deadline_during: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.source_id, str) or not self.source_id:
            raise AggregationContractError("SourceExecutionTrace.source_id must be a non-empty str")
        if not isinstance(self.final_result, SourceResult) or self.final_result.source_id != self.source_id:
            raise AggregationContractError("SourceExecutionTrace.final_result must be this source's SourceResult")
        if isinstance(self.max_attempts, bool) or not isinstance(self.max_attempts, int) or self.max_attempts < 1:
            raise AggregationContractError("SourceExecutionTrace.max_attempts must be an int >= 1")
        if not isinstance(self.attempts, tuple) or not self.attempts:
            raise AggregationContractError("SourceExecutionTrace.attempts must be a non-empty tuple")
        if not all(isinstance(a, SourceAttempt) for a in self.attempts):
            raise AggregationContractError("SourceExecutionTrace.attempts must contain SourceAttempt only")
        if [a.sequence for a in self.attempts] != list(range(1, len(self.attempts) + 1)):
            raise AggregationContractError("attempt sequences must be 1..n in order")
        if len(self.attempts) > self.max_attempts:
            raise AggregationContractError("more attempts than max_attempts")
        if any(not a.completed for a in self.attempts[:-1]):
            raise AggregationContractError("only the last attempt may be incomplete")
        if any(a.status is SourceStatus.SUCCESS for a in self.attempts[:-1]):
            raise AggregationContractError("an attempt that succeeded cannot be followed by another")
        if not isinstance(self.deadline_exceeded, bool):
            raise AggregationContractError("deadline_exceeded must be a bool")
        last = self.attempts[-1]
        final = self.final_result
        if self.deadline_exceeded:
            if self.deadline_during not in ("attempt", "backoff"):
                raise AggregationContractError("deadline_during must be 'attempt' or 'backoff' when the deadline was exceeded")
            if final.status is not SourceStatus.NETWORK_ERROR or final.error_kind is not SourceErrorKind.SOURCE_DEADLINE:
                raise AggregationContractError("an expired deadline must end in NETWORK_ERROR / SOURCE_DEADLINE")
            if self.deadline_during == "attempt" and last.completed:
                raise AggregationContractError("deadline during an attempt means the last attempt is incomplete")
            if self.deadline_during == "backoff":
                if not last.completed:
                    raise AggregationContractError("deadline during backoff means the last attempt had completed")
                if len(self.attempts) >= self.max_attempts:
                    raise AggregationContractError("no backoff can follow the last permitted attempt")
        else:
            if self.deadline_during is not None:
                raise AggregationContractError("deadline_during requires deadline_exceeded")
            if not last.completed:
                raise AggregationContractError("an attempt is incomplete only when the deadline was exceeded")
            if final.status is not last.status or final.error_kind is not last.error_kind:
                raise AggregationContractError("final_result must match the last attempt")

    @property
    def attempt_count(self) -> int:
        """How many attempts were **started** (a cut-off attempt counts; a never-started one does not)."""
        return len(self.attempts)

    @property
    def retried(self) -> bool:
        return len(self.attempts) > 1


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
    source_execution_traces: tuple[SourceExecutionTrace, ...] = ()

    def __post_init__(self) -> None:
        if not is_valid_fc2_number(self.number):
            raise AggregationContractError(f"number must be a canonical FC2 number, got {self.number!r}")
        if not isinstance(self.status, AggregateStatus):
            raise AggregationContractError("status must be an AggregateStatus")
        if not isinstance(self.source_results, tuple) or not self.source_results:
            raise AggregationContractError("source_results must be a non-empty tuple")
        if not all(isinstance(result, SourceResult) for result in self.source_results):
            raise AggregationContractError("source_results must contain only SourceResult")
        ids = tuple(result.source_id for result in self.source_results)
        if len(set(ids)) != len(ids):
            raise AggregationContractError("source_results contain a duplicate source_id")
        if not isinstance(self.contributing_source_ids, tuple) or not all(
            isinstance(sid, str) for sid in self.contributing_source_ids
        ):
            raise AggregationContractError("contributing_source_ids must be a tuple of str")
        if not isinstance(self.conflicts, tuple) or not all(isinstance(c, FieldConflict) for c in self.conflicts):
            raise AggregationContractError("conflicts must be a tuple of FieldConflict")
        self._validate_disabled(ids)
        if not _is_number(self.elapsed_ms) or self.elapsed_ms < 0:
            raise AggregationContractError("elapsed_ms must be a non-negative number")
        self._validate_traces(ids)

        successful = tuple(r.source_id for r in self.source_results if r.status is SourceStatus.SUCCESS)
        if self.contributing_source_ids != (successful if self.status is not AggregateStatus.FAILED else ()):
            raise AggregationContractError(
                "contributing_source_ids must equal the SUCCESS source ids exactly "
                f"(expected {successful if self.status is not AggregateStatus.FAILED else ()!r}, "
                f"got {self.contributing_source_ids!r})"
            )
        self._validate_conflicts()

        has_operational_failure = any(
            result.status in OPERATIONAL_FAILURE_STATUSES for result in self.source_results
        )
        if self.status is AggregateStatus.FAILED:
            if self.metadata is not None:
                raise AggregationContractError("status=failed must not carry metadata")
            if successful:
                raise AggregationContractError("status=failed contradicts a SUCCESS source result")
            return
        if not isinstance(self.metadata, NormalizedMetadata) or not self.metadata.meets_minimum_success():
            raise AggregationContractError(
                f"status={self.status.value} requires metadata that meets minimum success"
            )
        if self.metadata.number != self.number:
            raise AggregationContractError("aggregated metadata.number must equal the requested number")
        if not successful:
            raise AggregationContractError(f"status={self.status.value} requires at least one SUCCESS source result")
        if self.status is AggregateStatus.SUCCESS and has_operational_failure:
            raise AggregationContractError("status=success requires no operational source failure")
        if self.status is AggregateStatus.PARTIAL and not has_operational_failure:
            raise AggregationContractError("status=partial requires at least one operational source failure")

    def _validate_disabled(self, source_ids: tuple[str, ...]) -> None:
        disabled = self.disabled_source_ids
        if not isinstance(disabled, tuple) or not all(isinstance(sid, str) and sid.strip() for sid in disabled):
            raise AggregationContractError("disabled_source_ids must be a tuple of non-empty str")
        if len(set(disabled)) != len(disabled):
            raise AggregationContractError("disabled_source_ids contain a duplicate")
        overlap = set(disabled) & set(source_ids)
        if overlap:
            raise AggregationContractError(f"disabled source(s) {sorted(overlap)!r} also have a result")

    def _validate_traces(self, source_ids: tuple[str, ...]) -> None:
        traces = self.source_execution_traces
        if not isinstance(traces, tuple) or not all(isinstance(t, SourceExecutionTrace) for t in traces):
            raise AggregationContractError("source_execution_traces must be a tuple of SourceExecutionTrace")
        if not traces:
            return
        if tuple(t.source_id for t in traces) != source_ids:
            raise AggregationContractError("source_execution_traces must match source_results one-to-one, in order")
        for trace, result in zip(traces, self.source_results):
            if trace.final_result != result:
                raise AggregationContractError(
                    f"trace for {trace.source_id!r}: final_result is not the source's result"
                )

    def _validate_conflicts(self) -> None:
        contributing = set(self.contributing_source_ids)
        for conflict in self.conflicts:
            if conflict.selected_source_id not in contributing:
                raise AggregationContractError(
                    f"conflict on {conflict.field!r} selects {conflict.selected_source_id!r}, which did not contribute"
                )
            for source_id, _ in conflict.alternatives:
                if source_id not in contributing:
                    raise AggregationContractError(
                        f"conflict on {conflict.field!r} lists {source_id!r}, which did not contribute"
                    )

    # -- inspection helpers (pure) ------------------------------------------------

    @property
    def source_order(self) -> tuple[str, ...]:
        return tuple(result.source_id for result in self.source_results)

    @property
    def successful_source_ids(self) -> tuple[str, ...]:
        return tuple(r.source_id for r in self.source_results if r.status is SourceStatus.SUCCESS)

    def result_for(self, source_id: str) -> SourceResult | None:
        for result in self.source_results:
            if result.source_id == source_id:
                return result
        return None

    def trace_for(self, source_id: str) -> SourceExecutionTrace | None:
        for trace in self.source_execution_traces:
            if trace.source_id == source_id:
                return trace
        return None

    @property
    def operational_failure_source_ids(self) -> tuple[str, ...]:
        return tuple(r.source_id for r in self.source_results if r.status in OPERATIONAL_FAILURE_STATUSES)

    @property
    def not_found_source_ids(self) -> tuple[str, ...]:
        return tuple(r.source_id for r in self.source_results if r.status is SourceStatus.NOT_FOUND)
