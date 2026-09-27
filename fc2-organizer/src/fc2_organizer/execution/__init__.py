"""FC2 Organizer -- safe filesystem execution (Phase 4 / P4-C7).

Executes one film's already-built ``OrganizePlan`` (P4-C2) plus its artifact
manifest (``tuple[ArtifactWriteRequest, ...]``, P4-C6) against the real filesystem,
forward-only and never overwriting anything. See
``docs/specifications/PHASE4_SAFE_FILESYSTEM_EXECUTION_CONTRACT.md`` and
``docs/P4_C7_CONSTRUCTION_PLAN.md``.

Public API (frozen by contract section 4): the READ-ONLY ``preflight_execution`` and
``execute_filesystem``, the only entry that produces final effects, plus their value
models and errors.

Dependencies: standard library plus the bare public packages
``fc2_organizer.planning`` (which loads ``fc2_metadata_core`` transitively) and
``fc2_organizer.materialization``. ``fc2_organizer/__init__.py`` does not import
this package; import it explicitly: ``from fc2_organizer.execution import
preflight_execution``.
"""

from fc2_organizer.execution.errors import (
    ArtifactManifestError,
    CheckpointError,
    CheckpointRejectionReason,
    ExecutionContractError,
    ExecutionError,
    ExecutionInputError,
    ExecutionModelError,
    ManifestRejectionReason,
    PlanGraphError,
    PlanGraphRejectionReason,
    PreflightIntegrityError,
    PreflightIntegrityReason,
    PreflightNotReadyError,
)
from fc2_organizer.execution.models import (
    CompletedEffect,
    EffectKind,
    EntryIdentity,
    EntryType,
    ExecutionCheckpoint,
    ExecutionFailure,
    ExecutionFailureKind,
    ExecutionPreflight,
    ExecutionResult,
    ExecutionStatus,
    ExecutionStep,
    ExecutionUnit,
    LeftoverTemporary,
    PathRole,
    PreflightBlocker,
    PreflightBlockReason,
    PreflightMode,
    TransferMode,
    TransferStage,
)
from fc2_organizer.execution.executor import execute_filesystem
from fc2_organizer.execution.preflight import preflight_execution

__all__ = [
    "preflight_execution",
    "execute_filesystem",
    "ExecutionPreflight",
    "ExecutionResult",
    "ExecutionCheckpoint",
    "ExecutionStatus",
    "ExecutionStep",
    "ExecutionUnit",
    "PreflightMode",
    "TransferMode",
    "EntryIdentity",
    "EntryType",
    "PathRole",
    "EffectKind",
    "CompletedEffect",
    "LeftoverTemporary",
    "PreflightBlocker",
    "PreflightBlockReason",
    "ExecutionFailure",
    "ExecutionFailureKind",
    "TransferStage",
    "ExecutionError",
    "ExecutionInputError",
    "ExecutionContractError",
    "PlanGraphError",
    "PlanGraphRejectionReason",
    "ArtifactManifestError",
    "ManifestRejectionReason",
    "CheckpointError",
    "CheckpointRejectionReason",
    "PreflightIntegrityError",
    "PreflightIntegrityReason",
    "PreflightNotReadyError",
    "ExecutionModelError",
]
