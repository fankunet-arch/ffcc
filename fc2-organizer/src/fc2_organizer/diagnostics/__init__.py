"""FC2 Organizer -- structured diagnostics (Phase 4 / P4-C9).

::

    BatchPreview / BatchExecutionResult (already produced, in memory)
        ->  local read-only validation  ->  read-only deterministic projection
        ->  immutable ``BatchDiagnostics``  ->  redaction + path policy (default NONE)
        ->  deterministic JSON ``bytes``

Contract: ``docs/specifications/PHASE4_DIAGNOSTICS_CONTRACT.md``; construction plan:
``docs/P4_C9_CONSTRUCTION_PLAN.md``.

Public API (contract section 8.1): the diagnostics enums, immutable models, constants and the error hierarchy, the
two builders (``build_preview_diagnostics`` / ``build_execution_diagnostics``) and the renderer
``render_diagnostics_json`` (bytes only; nothing is written anywhere). ``fc2_organizer/__init__.py`` does not
import this package; import it explicitly: ``from fc2_organizer.diagnostics import PathPolicy``.
"""

from fc2_organizer.diagnostics.build import build_execution_diagnostics, build_preview_diagnostics
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
from fc2_organizer.diagnostics.render import render_diagnostics_json

__all__ = [
    "build_preview_diagnostics", "build_execution_diagnostics", "render_diagnostics_json",
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
