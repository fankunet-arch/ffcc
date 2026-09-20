"""Phase 3 (C1 + C2): multi-source execution, source-local retry, and deterministic
field-level aggregation for **one** FC2 number.

::

    canonical FC2 number
            |
    ordered SourceConfig  (order = default field priority; each source has its own
            |              total wall-clock deadline)  + one RetryPolicy
            |
    execute_sources_traced  bounded fan-out (per aggregate() call); per source, inside
            |               ONE concurrency slot and ONE total-deadline budget:
            |                 attempt -> [structured error_kind retryable? -> backoff
            |                 -> attempt] ... (default max_attempts = 2)
            |               isolation, fail-closed result validation, cancellation and
            |               fatal-exception handling
    SourceExecutionTrace[]  final SourceResult + every SourceAttempt, config order
            |
    merge_source_results    PURE, over the FINAL results only: scalars first-non-empty
            |               by priority, collections ordered-unique union, external_ids
            |               first-wins, provenance recomputed
    AggregationResult       SUCCESS | PARTIAL | FAILED + every SourceResult + traces

Retry (``retry.py``) is decided from the structured ``SourceErrorKind`` only, never
from ``error_detail`` text or a provider name; ``BLOCKED`` (incl. anti-bot
challenges), ``RATE_LIMITED`` and ``NOT_FOUND`` are never retried.

Contracts: ``docs/specifications/PHASE3_AGGREGATION_CONTRACT.md`` (C1) and
``docs/specifications/PHASE3_RESILIENCE_CONTRACT.md`` (C2/C3).
Out of scope here (later Phase 3 subphases): cross-item scheduling and any global
concurrency budget (``max_concurrency`` is per ``aggregate()`` call), circuit
breaking, batch jobs. Nothing in this package imports ``amane``.
"""

from fc2_metadata_core.aggregation.config import (
    DEFAULT_MAX_CONCURRENCY,
    DEFAULT_SOURCE_DEADLINE_SECONDS,
    AggregationConfig,
    SourceConfig,
    validate_base_url,
)
from fc2_metadata_core.aggregation.defaults import DEFAULT_SOURCE_ORDER, default_aggregation_config
from fc2_metadata_core.aggregation.engine import MultiSourceEngine, is_async_get
from fc2_metadata_core.aggregation.execution import SourceTarget, execute_sources, execute_sources_traced
from fc2_metadata_core.aggregation.merge import merge_source_results, validate_source_result
from fc2_metadata_core.aggregation.models import (
    CONFLICT_FIELDS,
    OPERATIONAL_FAILURE_STATUSES,
    AggregateStatus,
    AggregationContractError,
    AggregationInputError,
    AggregationResult,
    FieldConflict,
    SourceAttempt,
    SourceExecutionTrace,
)
from fc2_metadata_core.aggregation.policy import AggregationConfigError, AggregationPolicy
from fc2_metadata_core.aggregation.retry import (
    DEFAULT_MAX_ATTEMPTS,
    DEFAULT_RETRYABLE_ERROR_KINDS,
    RETRY_ELIGIBLE_KINDS,
    RetryPolicy,
)

__all__ = [
    "AggregateStatus",
    "AggregationConfig",
    "AggregationConfigError",
    "AggregationContractError",
    "AggregationInputError",
    "AggregationPolicy",
    "AggregationResult",
    "CONFLICT_FIELDS",
    "DEFAULT_MAX_ATTEMPTS",
    "DEFAULT_MAX_CONCURRENCY",
    "DEFAULT_SOURCE_DEADLINE_SECONDS",
    "DEFAULT_RETRYABLE_ERROR_KINDS",
    "DEFAULT_SOURCE_ORDER",
    "FieldConflict",
    "MultiSourceEngine",
    "OPERATIONAL_FAILURE_STATUSES",
    "RETRY_ELIGIBLE_KINDS",
    "RetryPolicy",
    "SourceAttempt",
    "SourceConfig",
    "SourceExecutionTrace",
    "SourceTarget",
    "default_aggregation_config",
    "execute_sources",
    "execute_sources_traced",
    "is_async_get",
    "merge_source_results",
    "validate_base_url",
    "validate_source_result",
]
