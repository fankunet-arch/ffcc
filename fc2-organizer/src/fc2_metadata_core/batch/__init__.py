"""Phase 3 (C4): the batch scheduler core -- many FC2 numbers through one single-item engine.

::

    Sequence[str] of canonical FC2 numbers (order = batch order, duplicates kept as separate items)
            |
    BatchScheduler(engine, BatchConfig(max_in_flight_items=M))
            |   bounded admission: min(M, N) workers, never one task per item; global item budget
            |   ordinary item failure isolated; fatal BaseException / cancellation propagate
            v
    BatchResult  (items in input order: SUCCESS | PARTIAL | FAILED per item, immutable)
            |
    retry_failed(result) -> RetryBatchResult   (only FAILED items, by original index, next generation)
    apply_retry(result, retry) -> BatchResult  (pure, fail-closed merge)

The scheduler drives the C1/C2 engine (``MultiSourceEngine.aggregate``) through a narrow protocol; it neither
re-implements aggregation nor touches adapters. Theoretical maximum simultaneous source operations is
``max_in_flight_items * AggregationConfig.max_concurrency``.

Contract: ``docs/specifications/PHASE3_BATCH_CONTRACT.md``. Not implemented here (later phases): circuit breaker,
per-host limiter, persistence, NFO, filesystem, Amane adapter. Nothing in this package imports ``amane``, and no
other package imports this one.
"""

from fc2_metadata_core.batch.config import DEFAULT_MAX_IN_FLIGHT_ITEMS, MAX_IN_FLIGHT_ITEMS_LIMIT, BatchConfig
from fc2_metadata_core.batch.models import (
    BatchBusyError,
    BatchConfigError,
    BatchContractError,
    BatchError,
    BatchInputError,
    BatchItemErrorKind,
    BatchItemResult,
    BatchItemStatus,
    BatchLineage,
    BatchResult,
    BatchRetryError,
    RetryBatchResult,
)
from fc2_metadata_core.batch.retry import apply_retry, failed_work
from fc2_metadata_core.batch.scheduler import AggregationEngine, BatchScheduler, validate_batch

__all__ = [
    "AggregationEngine",
    "BatchBusyError",
    "BatchConfig",
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
    "BatchScheduler",
    "DEFAULT_MAX_IN_FLIGHT_ITEMS",
    "MAX_IN_FLIGHT_ITEMS_LIMIT",
    "RetryBatchResult",
    "apply_retry",
    "failed_work",
    "validate_batch",
]
