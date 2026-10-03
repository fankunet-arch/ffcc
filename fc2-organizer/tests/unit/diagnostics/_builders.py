"""Shared builders for the P4-C9 diagnostics tests (construction plan section 4).

S1: factories for *valid* diagnostics models (``make_*``); every factory accepts keyword overrides so a test can
change exactly one field. Later stages extend this module with builders for the (real, public-constructor) P4-C8 /
Phase 3 / P4-C7 inputs of the builders under test. Production code never imports this module. Every production
name is bound at import (collection) time (several contract guards purge ``fc2_*`` from ``sys.modules``).
"""

from __future__ import annotations

from fc2_metadata_core.aggregation import AggregateStatus
from fc2_metadata_core.batch import BatchItemErrorKind, BatchItemStatus
from fc2_metadata_core.models import SourceErrorKind, SourceStatus
from fc2_organizer.diagnostics import (
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
from fc2_organizer.execution import (
    EffectKind,
    ExecutionFailure,
    ExecutionFailureKind,
    ExecutionStatus,
    ExecutionStep,
    PathRole,
    PreflightBlocker,
    PreflightBlockReason,
    PreflightMode,
    TransferMode,
)
from fc2_organizer.images import ImageFailureKind, ImageRole
from fc2_organizer.materialization import ArtifactKind
from fc2_organizer.orchestration import (
    BatchOutcome,
    ExecutionDisposition,
    ExecutionSummary,
    IssueReason,
    ItemWarning,
    OrchestrationStage,
    PreviewState,
    PreviewSummary,
    RetryKind,
)

NUMBER = "FC2-1234567"


def zero_stage_counts() -> tuple[tuple[OrchestrationStage, int], ...]:
    return tuple((stage, 0) for stage in OrchestrationStage)


def stage_counts_for(*stages: OrchestrationStage) -> tuple[tuple[OrchestrationStage, int], ...]:
    return tuple((stage, sum(1 for s in stages if s is stage)) for stage in OrchestrationStage)


def make_preview_summary(total: int = 0, ready: int | None = None, blocked: int = 0, unprepared: int = 0,
                         warned: int = 0, stages: tuple[OrchestrationStage, ...] = ()) -> PreviewSummary:
    ready = total - blocked - unprepared if ready is None else ready
    return PreviewSummary(total=total, ready=ready, blocked=blocked, unprepared=unprepared, warned=warned,
                          stage_counts=stage_counts_for(*stages))


def make_execution_summary(total: int = 0, success: int | None = None) -> ExecutionSummary:
    """``total`` items that all executed successfully (the simplest valid execution summary)."""
    success = total if success is None else success
    return ExecutionSummary(
        total=total, ready=total, blocked=0, unprepared=0, executed=success, success=success, partial=0, failed=0,
        not_selected=total - success, cancelled=0, rejected=0, aborted=0, retryable=0, deferred=total - success,
        non_retryable=0, stage_counts=zero_stage_counts())


def make_metadata_batch_counts(**overrides) -> MetadataBatchCounts:
    values = dict(generation=0, total=3, success=2, partial=1, failed=0)
    values.update(overrides)
    return MetadataBatchCounts(**values)


def make_issue(**overrides) -> IssueDiagnostics:
    values = dict(stage=OrchestrationStage.METADATA, reason=IssueReason.METADATA_UNAVAILABLE, error_type=None,
                  detail=None)
    values.update(overrides)
    return IssueDiagnostics(**values)


def make_attempt(**overrides) -> SourceAttemptDiagnostics:
    values = dict(sequence=1, status=SourceStatus.SUCCESS, error_kind=None, completed=True, elapsed_ms=None,
                  backoff_before_ms=None)
    values.update(overrides)
    return SourceAttemptDiagnostics(**values)


def make_source(**overrides) -> SourceDiagnostics:
    values = dict(source_id="fc2db_net", status=SourceStatus.SUCCESS, error_kind=None, contributed=True,
                  operational_failure=False, provided_fields=("title",), trace_available=True, attempt_count=1,
                  max_attempts=2, deadline_exceeded=False, deadline_during=None, attempts=(make_attempt(),))
    values.update(overrides)
    return SourceDiagnostics(**values)


def make_metadata(**overrides) -> MetadataDiagnostics:
    values = dict(
        status=BatchItemStatus.SUCCESS, generation=0, error_kind=None, aggregate_status=AggregateStatus.SUCCESS,
        traces_available=True, sources=(make_source(),), disabled_source_ids=("av123",),
        field_provenance=(FieldProvenance(field="title", source_ids=("fc2db_net",)),),
        conflicts=(), elapsed_ms=None)
    values.update(overrides)
    return MetadataDiagnostics(**values)


def make_preflight(**overrides) -> PreflightDiagnostics:
    values = dict(mode=PreflightMode.FRESH, ready=True, transfer_mode=TransferMode.SAME_VOLUME, blockers=(),
                  pending_unit_count=7, completed_unit_count=0, skipped_steps=(),
                  artifact_counts=tuple((kind, 1 if kind is ArtifactKind.NFO else 0) for kind in ArtifactKind))
    values.update(overrides)
    return PreflightDiagnostics(**values)


def make_execution(**overrides) -> ExecutionDiagnostics:
    values = dict(
        status=ExecutionStatus.SUCCESS, mode=PreflightMode.FRESH, transfer_mode=TransferMode.SAME_VOLUME,
        new_effect_count=2,
        effect_counts=tuple((kind, 1 if kind in (EffectKind.MEDIA_PUBLISHED, EffectKind.SOURCE_REMOVED) else 0)
                            for kind in EffectKind),
        artifact_counts=tuple((kind, 0) for kind in ArtifactKind), failure=None, checkpoint_present=False,
        skipped_steps=(), leftover_temporary_count=0, leftover_temporaries=())
    values.update(overrides)
    return ExecutionDiagnostics(**values)


def make_failure(**overrides) -> ExecutionFailure:
    values = dict(step=ExecutionStep.MOVE_MEDIA, kind=ExecutionFailureKind.MEDIA_TRANSFER_FAILED)
    values.update(overrides)
    return ExecutionFailure(**values)


def make_blocker(**overrides) -> PreflightBlocker:
    values = dict(reason=PreflightBlockReason.SOURCE_MISSING, role=PathRole.SOURCE)
    values.update(overrides)
    return PreflightBlocker(**values)


def make_leftover(**overrides) -> LeftoverTemporaryDiagnostics:
    values = dict(directory_role=PathRole.TARGET_DIRECTORY, name=None)
    values.update(overrides)
    return LeftoverTemporaryDiagnostics(**values)


def make_image_group(**overrides) -> ImageFailureGroup:
    values = dict(role=ImageRole.POSTER, kind=ImageFailureKind.TIMEOUT, count=1, http_statuses=())
    values.update(overrides)
    return ImageFailureGroup(**values)


def make_item(**overrides) -> ItemDiagnostics:
    """A valid PREVIEW-kind item (index 0, generation 0, no policy-dependent text)."""
    values = dict(
        index=0, generation=0, canonical_number=NUMBER, source_name=None, source_size=1024,
        target_directory_name=None, target_media_name=None, preview_state=PreviewState.READY, issue=None,
        warnings=(), conflict_with=(), retry_origin=None, disposition=None, retry_kind=None,
        retry_material_retained=None, metadata=make_metadata(), image_failures=(), preflight=make_preflight(),
        execution=None)
    values.update(overrides)
    return ItemDiagnostics(**values)


def make_execution_item(**overrides) -> ItemDiagnostics:
    """A valid EXECUTION-kind item (EXECUTED / SUCCESS)."""
    values = dict(preflight=None, disposition=ExecutionDisposition.EXECUTED, retry_kind=RetryKind.NONE,
                  retry_material_retained=False, execution=make_execution())
    values.update(overrides)
    return make_item(**values)


def _count_of(count: int, overrides: dict) -> int:
    items = overrides.get("items")
    return len(items) if items is not None else count


def make_preview_diagnostics(count: int = 1, **overrides) -> BatchDiagnostics:
    """``count`` default PREVIEW items; ``items`` / ``batch_size`` / the summary total follow an ``items`` override."""
    size = _count_of(count, overrides)
    values = dict(
        kind=DiagnosticsKind.PREVIEW, shape=ResultShape.MAIN, generation=0, batch_size=size, retry_scope=None,
        path_policy=PathPolicy.NONE, timing_policy=TimingPolicy.OMIT, metadata_batch=make_metadata_batch_counts(),
        preview_summary=make_preview_summary(total=size), execution_summary=None, outcome=None,
        items=tuple(make_item(index=i) for i in range(size)))
    values.update(overrides)
    return BatchDiagnostics(**values)


def make_execution_diagnostics(count: int = 1, **overrides) -> BatchDiagnostics:
    size = _count_of(count, overrides)
    values = dict(
        kind=DiagnosticsKind.EXECUTION, shape=ResultShape.MAIN, generation=0, batch_size=size, retry_scope=None,
        path_policy=PathPolicy.NONE, timing_policy=TimingPolicy.OMIT, metadata_batch=make_metadata_batch_counts(),
        preview_summary=None, execution_summary=make_execution_summary(total=size), outcome=BatchOutcome.SUCCESS,
        items=tuple(make_execution_item(index=i) for i in range(size)))
    values.update(overrides)
    return BatchDiagnostics(**values)
