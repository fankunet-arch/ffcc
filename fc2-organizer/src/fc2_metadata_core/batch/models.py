"""Batch result models (Phase 3 C4). Immutable; see ``docs/specifications/PHASE3_BATCH_CONTRACT.md`` §6.

A batch is an *execution list*: every element is a separate work item identified by its original ``index``
(never by its number, which may legitimately repeat). Results are plain frozen dataclasses of tuples, so they
follow the same immutability contract as the Phase 1/3 models.

No overall "batch status" enum is introduced: ``AggregateStatus.PARTIAL`` already has a meaning at item level, and
the derived counts are unambiguous.
"""

from __future__ import annotations

import math
import re
import secrets
from dataclasses import dataclass, field
from enum import Enum

from fc2_metadata_core.aggregation import AggregateStatus, AggregationResult
from fc2_metadata_core.errors import FC2MetadataCoreError
from fc2_metadata_core.normalize.fc2_number import is_valid_fc2_number

__all__ = [
    "BatchBusyError",
    "BatchConfigError",
    "BatchContractError",
    "BatchError",
    "BatchInputError",
    "BatchItemErrorKind",
    "BatchItemResult",
    "BatchItemStatus",
    "BatchLineage",
    "BatchResult",
    "BatchRetryError",
    "RetryBatchResult",
    "MAX_ERROR_TYPE_CHARS",
]

MAX_ERROR_TYPE_CHARS = 256


class BatchError(FC2MetadataCoreError):
    """Base class for batch-layer errors (all are caller / contract bugs, never per-item outcomes)."""


class BatchConfigError(BatchError, ValueError):
    """``BatchConfig`` / scheduler construction arguments are invalid."""


class BatchInputError(BatchError, ValueError):
    """The batch handed to the scheduler is not an ordered ``Sequence`` of canonical FC2 numbers."""


class BatchContractError(BatchError, ValueError):
    """A ``BatchItemResult`` / ``BatchResult`` / ``RetryBatchResult`` violates its invariants."""


class BatchRetryError(BatchError, ValueError):
    """Failed-subset retry was asked to do something inconsistent (fail closed, nothing is produced)."""


class BatchBusyError(BatchError, RuntimeError):
    """The scheduler already has an active run; a second one would silently double the global budget."""


class BatchItemStatus(Enum):
    """1:1 with ``AggregateStatus`` -- no new source/aggregate status is invented."""

    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"


class BatchItemErrorKind(Enum):
    """Why an item is ``FAILED`` *without* an ``AggregationResult`` (the engine did not produce one)."""

    ENGINE_EXCEPTION = "engine_exception"  # aggregate() raised an ordinary Exception
    RESULT_CONTRACT_MISMATCH = "result_contract_mismatch"  # not an AggregationResult, or for another number


_STATUS_FOR_AGGREGATE = {
    AggregateStatus.SUCCESS: BatchItemStatus.SUCCESS,
    AggregateStatus.PARTIAL: BatchItemStatus.PARTIAL,
    AggregateStatus.FAILED: BatchItemStatus.FAILED,
}


def batch_status_for(status: AggregateStatus) -> BatchItemStatus:
    return _STATUS_FOR_AGGREGATE[status]


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


_LINEAGE_TOKEN_RE = re.compile(r"[0-9a-f]{32}")


@dataclass(frozen=True, slots=True)
class BatchLineage:
    """Opaque, immutable identity of ONE batch execution chain (primary run -> retries -> merged results).

    Created once per :meth:`BatchScheduler.run` (128 random bits, hex) and carried unchanged by every
    :class:`BatchResult` / :class:`RetryBatchResult` derived from that run. ``apply_retry`` accepts a retry only if
    its lineage equals the previous result's, so a retry made from batch A can never be merged into a
    different batch B -- even one with identical numbers, failed indices and generation. The identity is by value
    (so a copy of the same batch still matches); it is an in-memory provenance token, **not** a persistence format.
    """

    token: str

    def __post_init__(self) -> None:
        if type(self.token) is not str or _LINEAGE_TOKEN_RE.fullmatch(self.token) is None:
            raise BatchContractError("BatchLineage.token must be 32 lowercase hex characters")

    @classmethod
    def new(cls) -> "BatchLineage":
        return cls(secrets.token_hex(16))


@dataclass(frozen=True, slots=True)
class BatchItemResult:
    """The outcome of one work item.

    Exactly one of ``aggregation_result`` / ``error_kind`` is set. With an ``aggregation_result`` the ``status``
    is the 1:1 mapping of its ``AggregateStatus`` (a ``FAILED`` aggregate keeps every ``SourceResult``); without
    one the item is ``FAILED`` and ``error_kind`` says why. ``error_type`` is a **class name only** -- never an
    exception message, repr or argument, which could carry a URL, cookie or token.

    ``generation``: which batch execution round produced this result (``0`` = the primary run, ``1`` = the first
    ``retry_failed`` round, ...). ``elapsed_ms``: measured by the scheduler around the engine call.
    """

    index: int
    number: str
    status: BatchItemStatus
    aggregation_result: AggregationResult | None = None
    error_kind: BatchItemErrorKind | None = None
    error_type: str | None = None
    generation: int = 0
    elapsed_ms: float = 0.0

    def __post_init__(self) -> None:
        if not _is_int(self.index) or self.index < 0:
            raise BatchContractError("BatchItemResult.index must be an int >= 0")
        if type(self.number) is not str or not is_valid_fc2_number(self.number):
            raise BatchContractError("BatchItemResult.number must be a canonical FC2 number (exact str)")
        if not isinstance(self.status, BatchItemStatus):
            raise BatchContractError("BatchItemResult.status must be a BatchItemStatus")
        if not _is_int(self.generation) or self.generation < 0:
            raise BatchContractError("BatchItemResult.generation must be an int >= 0")
        elapsed = self.elapsed_ms
        if isinstance(elapsed, bool) or not isinstance(elapsed, (int, float)) or not math.isfinite(elapsed) or elapsed < 0:
            raise BatchContractError("BatchItemResult.elapsed_ms must be a finite number >= 0")

        if self.aggregation_result is not None:
            result = self.aggregation_result
            if not isinstance(result, AggregationResult):
                raise BatchContractError("BatchItemResult.aggregation_result must be an AggregationResult")
            if self.error_kind is not None or self.error_type is not None:
                raise BatchContractError("an item with an aggregation_result has no error_kind / error_type")
            if result.number != self.number:
                raise BatchContractError("aggregation_result.number must equal the item number")
            if self.status is not _STATUS_FOR_AGGREGATE[result.status]:
                raise BatchContractError("item status must be the mapping of the aggregation status")
            return
        if self.status is not BatchItemStatus.FAILED:
            raise BatchContractError("an item without an aggregation_result is FAILED")
        if not isinstance(self.error_kind, BatchItemErrorKind):
            raise BatchContractError("an item without an aggregation_result needs a BatchItemErrorKind")
        if type(self.error_type) is not str or not self.error_type or len(self.error_type) > MAX_ERROR_TYPE_CHARS:
            raise BatchContractError("error_type must be a non-empty class name (<= 256 chars)")


def _count(items: tuple[BatchItemResult, ...], status: BatchItemStatus) -> int:
    return sum(1 for item in items if item.status is status)


def _validate_items_tuple(items: object, what: str) -> tuple[BatchItemResult, ...]:
    if not isinstance(items, tuple) or not all(isinstance(item, BatchItemResult) for item in items):
        raise BatchContractError(f"{what}.items must be a tuple of BatchItemResult")
    return items


@dataclass(frozen=True, slots=True)
class BatchResult:
    """A complete batch outcome: one ``BatchItemResult`` per work item, **in input order**.

    ``items[i].index == i`` (contiguous ``0..n-1``). ``generation`` is the latest execution round reflected in
    this result (``0`` for a primary run; each :func:`apply_retry` produces the next one); no item may be newer
    than its batch. Counts and failed views are *derived* (nothing stored can contradict them) and are tuples.
    ``lineage`` identifies the execution chain this result belongs to (see :class:`BatchLineage`); a result built
    by hand gets a fresh lineage of its own.
    """

    items: tuple[BatchItemResult, ...]
    generation: int = 0
    lineage: BatchLineage = field(default_factory=BatchLineage.new, compare=False, repr=False)

    def __post_init__(self) -> None:
        items = _validate_items_tuple(self.items, "BatchResult")
        if not isinstance(self.lineage, BatchLineage):
            raise BatchContractError("BatchResult.lineage must be a BatchLineage")
        if not _is_int(self.generation) or self.generation < 0:
            raise BatchContractError("BatchResult.generation must be an int >= 0")
        if [item.index for item in items] != list(range(len(items))):
            raise BatchContractError("BatchResult items must be in input order with index 0..n-1")
        if any(item.generation > self.generation for item in items):
            raise BatchContractError("no item may be newer than the batch generation")

    @property
    def total(self) -> int:
        return len(self.items)

    @property
    def success_count(self) -> int:
        return _count(self.items, BatchItemStatus.SUCCESS)

    @property
    def partial_count(self) -> int:
        return _count(self.items, BatchItemStatus.PARTIAL)

    @property
    def failed_count(self) -> int:
        return _count(self.items, BatchItemStatus.FAILED)

    @property
    def failed_items(self) -> tuple[BatchItemResult, ...]:
        return tuple(item for item in self.items if item.status is BatchItemStatus.FAILED)

    @property
    def failed_indices(self) -> tuple[int, ...]:
        return tuple(item.index for item in self.failed_items)

    @property
    def failed_numbers(self) -> tuple[str, ...]:
        """Aligned with :attr:`failed_indices`; may contain the same number more than once."""
        return tuple(item.number for item in self.failed_items)


@dataclass(frozen=True, slots=True)
class RetryBatchResult:
    """The outcome of one ``retry_failed`` round: **only** the retried items, in batch order.

    Every item carries this round's ``generation`` (``>= 1``) and its **original** ``index``; indices strictly
    increase, and ``lineage`` is the lineage of the batch it was made from. It never replaces anything by itself --
    :func:`fc2_metadata_core.batch.apply_retry` produces the
    merged, complete :class:`BatchResult`.
    """

    items: tuple[BatchItemResult, ...]
    generation: int
    lineage: BatchLineage = field(compare=False, repr=False)

    def __post_init__(self) -> None:
        items = _validate_items_tuple(self.items, "RetryBatchResult")
        if not isinstance(self.lineage, BatchLineage):
            raise BatchContractError("RetryBatchResult.lineage must be the BatchLineage of the batch it retries")
        if not _is_int(self.generation) or self.generation < 1:
            raise BatchContractError("RetryBatchResult.generation must be an int >= 1 (0 is the primary run)")
        indices = [item.index for item in items]
        if any(later <= earlier for earlier, later in zip(indices, indices[1:])):
            raise BatchContractError("RetryBatchResult item indices must strictly increase")
        if any(item.generation != self.generation for item in items):
            raise BatchContractError("every RetryBatchResult item must carry the retry generation")

    @property
    def total(self) -> int:
        return len(self.items)

    @property
    def indices(self) -> tuple[int, ...]:
        return tuple(item.index for item in self.items)

    @property
    def success_count(self) -> int:
        return _count(self.items, BatchItemStatus.SUCCESS)

    @property
    def partial_count(self) -> int:
        return _count(self.items, BatchItemStatus.PARTIAL)

    @property
    def failed_count(self) -> int:
        return _count(self.items, BatchItemStatus.FAILED)

    @property
    def failed_indices(self) -> tuple[int, ...]:
        return tuple(item.index for item in self.items if item.status is BatchItemStatus.FAILED)
