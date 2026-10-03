"""FC2 Organizer -- structured diagnostics (Phase 4 / P4-C9).

::

    BatchPreview / BatchExecutionResult (already produced, in memory)
        ->  local read-only validation  ->  read-only deterministic projection
        ->  immutable ``BatchDiagnostics``  ->  redaction + path policy (default NONE)
        ->  deterministic JSON ``bytes``

Contract: ``docs/specifications/PHASE4_DIAGNOSTICS_CONTRACT.md``; construction plan:
``docs/P4_C9_CONSTRUCTION_PLAN.md``.

S1 (this stage) exports the diagnostics enums, immutable models, constants and the error hierarchy.
S2 adds the two builders (``build_preview_diagnostics`` / ``build_execution_diagnostics``); S3 adds
``render_diagnostics_json`` and fixes the final public API (contract section 8.1). ``fc2_organizer/__init__.py``
does not import this package; import it explicitly: ``from fc2_organizer.diagnostics import PathPolicy``.
"""

from fc2_organizer.diagnostics.errors import (
    DiagnosticsContractError,
    DiagnosticsError,
    DiagnosticsInputError,
    DiagnosticsIntegrityError,
    DiagnosticsResourceLimitError,
    DiagnosticsSerializationError,
    DiagnosticsUnsafeValueError,
)
from fc2_organizer.diagnostics.models import (
    DIAGNOSTICS_SCHEMA,
    DIAGNOSTICS_SCHEMA_VERSION,
    MAX_ATTEMPTS_PER_SOURCE,
    MAX_BLOCKERS_PER_ITEM,
    MAX_CONFLICTS_PER_ITEM,
    MAX_DIAGNOSTIC_ITEMS,
    MAX_DIAGNOSTIC_OUTPUT_BYTES,
    MAX_LEFTOVER_TEMPORARIES_PER_ITEM,
    MAX_PATH_TEXT_CHARS,
    MAX_SOURCES_PER_ITEM,
    MAX_TIMING_MS,
    PROVENANCE_FIELD_ORDER,
    BatchDiagnostics,
    DiagnosticsKind,
    ExecutionDiagnostics,
    FieldConflictDiagnostics,
    FieldProvenance,
    ImageFailureGroup,
    IssueDiagnostics,
    ItemDiagnostics,
    LeftoverTemporaryDiagnostics,
    MetadataBatchCounts,
    MetadataDiagnostics,
    PathPolicy,
    PreflightDiagnostics,
    ResultShape,
    SourceAttemptDiagnostics,
    SourceDiagnostics,
    TimingPolicy,
)

__all__ = [
    "DiagnosticsKind", "ResultShape", "PathPolicy", "TimingPolicy",
    "BatchDiagnostics", "MetadataBatchCounts", "ItemDiagnostics", "IssueDiagnostics", "MetadataDiagnostics",
    "SourceDiagnostics", "SourceAttemptDiagnostics", "FieldProvenance", "FieldConflictDiagnostics",
    "ImageFailureGroup", "PreflightDiagnostics", "ExecutionDiagnostics", "LeftoverTemporaryDiagnostics",
    "DIAGNOSTICS_SCHEMA", "DIAGNOSTICS_SCHEMA_VERSION", "PROVENANCE_FIELD_ORDER", "MAX_DIAGNOSTIC_ITEMS",
    "MAX_SOURCES_PER_ITEM", "MAX_ATTEMPTS_PER_SOURCE", "MAX_BLOCKERS_PER_ITEM", "MAX_CONFLICTS_PER_ITEM",
    "MAX_LEFTOVER_TEMPORARIES_PER_ITEM", "MAX_PATH_TEXT_CHARS", "MAX_TIMING_MS", "MAX_DIAGNOSTIC_OUTPUT_BYTES",
    "DiagnosticsError", "DiagnosticsInputError", "DiagnosticsIntegrityError", "DiagnosticsContractError",
    "DiagnosticsResourceLimitError", "DiagnosticsUnsafeValueError", "DiagnosticsSerializationError",
]
