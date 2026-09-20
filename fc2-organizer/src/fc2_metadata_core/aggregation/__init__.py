"""Phase 3 / C1: multi-source execution and deterministic field-level aggregation.

::

    canonical FC2 number
            |
    ordered SourceConfig  (order = default field priority)
            |
    execute_sources        bounded fan-out, per-source wall-clock deadline,
            |              isolation, fail-closed result validation
    SourceResult[]         one per enabled source, in configuration order
            |
    merge_source_results   PURE: scalars first-non-empty by priority,
            |              collections ordered-unique union, external_ids
            |              first-wins, provenance recomputed
    AggregationResult      SUCCESS | PARTIAL | FAILED + every SourceResult

The contract lives in ``docs/specifications/PHASE3_AGGREGATION_CONTRACT.md``.
Out of scope here (later Phase 3 subphases): retry/backoff, circuit breaking,
batch jobs. Nothing in this package imports ``amane``.
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
