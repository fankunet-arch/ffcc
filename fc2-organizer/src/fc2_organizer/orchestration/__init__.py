"""FC2 Organizer -- batch orchestration / preview / retry (Phase 4 / P4-C8).

::

    DiscoveredMediaItem x N  ->  number recognition + in-batch conflicts
        ->  Phase 3 metadata batch  ->  plan / publication / NFO / images / manifest / preflight
        ->  BatchPreview (read-only)  ->  execute  ->  BatchExecutionResult
        ->  preview_retry  ->  execute  ->  merge_retry  ->  next generation

Contract: ``docs/specifications/PHASE4_BATCH_ORCHESTRATION_CONTRACT.md``; construction plan:
``docs/P4_C8_CONSTRUCTION_PLAN.md``.

S1 (foundation) exports the models, configuration, cancellation token, resource / concurrency
constants and the error hierarchy; S2 adds ``BatchOrchestrator`` (construction + ``preview``);
S3 adds ``execute``; S4 adds ``preview_retry`` and the module-level ``merge_retry``. The summary models
(S5) are added by a later batch.

Dependencies: standard library plus the bare public packages listed in contract section 6; never a
lower-layer private module. ``fc2_organizer/__init__.py`` does not import this package; import it
explicitly: ``from fc2_organizer.orchestration import OrchestrationConfig``.
"""

from fc2_organizer.orchestration.cancellation import CancellationToken
from fc2_organizer.orchestration.errors import (
    OrchestrationBusyError,
    OrchestrationConfigError,
    OrchestrationConsumedError,
    OrchestrationContractError,
    OrchestrationError,
    OrchestrationInputError,
    OrchestrationIntegrityError,
    OrchestrationResourceLimitError,
    OrchestrationRetryError,
)
from fc2_organizer.orchestration.models import (
    DEFAULT_FILESYSTEM_WORKERS,
    DEFAULT_IMAGE_IN_FLIGHT_ITEMS,
    DEFAULT_MAX_RETAINED_ARTIFACT_BYTES,
    MAX_BATCH_ITEMS,
    MAX_FILESYSTEM_WORKERS,
    MAX_IMAGE_IN_FLIGHT_ITEMS,
    MAX_ITEM_IMAGE_BYTES,
    MAX_RETAINED_ARTIFACT_BYTES_LIMIT,
    BatchExecutionResult,
    BatchOutcome,
    BatchPreview,
    ExecutionDisposition,
    IssueReason,
    ItemExecution,
    ItemIssue,
    ItemPreview,
    ItemWarning,
    OrchestrationConfig,
    OrchestrationStage,
    PreviewState,
    ResourceLimitReason,
    RetryKind,
    RetryMaterial,
)
from fc2_organizer.orchestration.orchestrator import BatchOrchestrator
from fc2_organizer.orchestration.retry import merge_retry

__all__ = [
    "BatchOrchestrator",
    "OrchestrationConfig",
    "CancellationToken",
    "merge_retry",
    "BatchPreview",
    "ItemPreview",
    "PreviewState",
    "BatchExecutionResult",
    "ItemExecution",
    "ExecutionDisposition",
    "BatchOutcome",
    "RetryMaterial",
    "RetryKind",
    "OrchestrationStage",
    "IssueReason",
    "ItemIssue",
    "ItemWarning",
    "ResourceLimitReason",
    "DEFAULT_IMAGE_IN_FLIGHT_ITEMS",
    "MAX_IMAGE_IN_FLIGHT_ITEMS",
    "DEFAULT_FILESYSTEM_WORKERS",
    "MAX_FILESYSTEM_WORKERS",
    "MAX_BATCH_ITEMS",
    "MAX_ITEM_IMAGE_BYTES",
    "DEFAULT_MAX_RETAINED_ARTIFACT_BYTES",
    "MAX_RETAINED_ARTIFACT_BYTES_LIMIT",
    "OrchestrationError",
    "OrchestrationConfigError",
    "OrchestrationInputError",
    "OrchestrationBusyError",
    "OrchestrationContractError",
    "OrchestrationIntegrityError",
    "OrchestrationConsumedError",
    "OrchestrationRetryError",
    "OrchestrationResourceLimitError",
]
