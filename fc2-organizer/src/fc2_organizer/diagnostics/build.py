"""The two public builders of ``fc2_organizer.diagnostics`` (P4-C9 contract sections 8.2 and 24.2).

Order (contract 24.2): (1) exact top-level type, (2) exact policy enums, then ``validation`` runs steps 3-7
(items tuple + limit, recursive local validation, cross-object checks, safe output + timing conversion, approved
property reads), (8) ``projection`` maps the validation snapshot, (9) the ``BatchDiagnostics`` model is built.
Both functions are read-only: the input object is never modified and nothing is registered, written or consumed.
"""

from __future__ import annotations

from fc2_organizer.diagnostics.errors import DiagnosticsInputError
from fc2_organizer.diagnostics.models import BatchDiagnostics, PathPolicy, TimingPolicy
from fc2_organizer.diagnostics.projection import project_batch
from fc2_organizer.diagnostics.validation import build_execution_snapshot, build_preview_snapshot
from fc2_organizer.orchestration import BatchExecutionResult, BatchPreview


def build_preview_diagnostics(
    preview: BatchPreview,
    /,
    *,
    path_policy: PathPolicy = PathPolicy.NONE,
    timing_policy: TimingPolicy = TimingPolicy.OMIT,
) -> BatchDiagnostics:
    """Project an already produced ``BatchPreview`` into immutable ``BatchDiagnostics`` (read-only)."""
    if type(preview) is not BatchPreview:
        raise DiagnosticsInputError("build_preview_diagnostics needs an exact BatchPreview")
    if type(path_policy) is not PathPolicy or type(timing_policy) is not TimingPolicy:
        raise DiagnosticsInputError("path_policy / timing_policy must be exact PathPolicy / TimingPolicy members")
    snapshot = build_preview_snapshot(preview, path_policy, timing_policy)
    return project_batch(snapshot, path_policy, timing_policy)


def build_execution_diagnostics(
    result: BatchExecutionResult,
    /,
    *,
    path_policy: PathPolicy = PathPolicy.NONE,
    timing_policy: TimingPolicy = TimingPolicy.OMIT,
) -> BatchDiagnostics:
    """Project an already produced ``BatchExecutionResult`` into immutable ``BatchDiagnostics`` (read-only)."""
    if type(result) is not BatchExecutionResult:
        raise DiagnosticsInputError("build_execution_diagnostics needs an exact BatchExecutionResult")
    if type(path_policy) is not PathPolicy or type(timing_policy) is not TimingPolicy:
        raise DiagnosticsInputError("path_policy / timing_policy must be exact PathPolicy / TimingPolicy members")
    snapshot = build_execution_snapshot(result, path_policy, timing_policy)
    return project_batch(snapshot, path_policy, timing_policy)
