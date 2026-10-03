"""Read-only projection of the validation snapshot into diagnostics models (P4-C9 contract section 12).

Input is only the immutable snapshot produced by ``validation`` (policy-applied: converted timings, basenames
only under ``PathPolicy.BASENAME``). Nothing here touches an input model, an upstream property or the filesystem;
every ordering comes from the declaration order of a frozen enum / constant (never from a set / mapping order).
"""

from __future__ import annotations

from fc2_organizer.diagnostics.models import (
    PROVENANCE_FIELD_ORDER,
    BatchDiagnostics,
    BatchSnapshot,
    ExecutionDiagnostics,
    FieldProvenance,
    ImageFailureGroup,
    ItemDiagnostics,
    ItemSnapshot,
    LeftoverTemporaryDiagnostics,
    MetadataDiagnostics,
    MetadataSnapshot,
    PathPolicy,
    PreflightDiagnostics,
    PreflightSnapshot,
    SourceDiagnostics,
    SourceSnapshot,
    TimingPolicy,
)
from fc2_metadata_core.aggregation import OPERATIONAL_FAILURE_STATUSES
from fc2_organizer.execution import EffectKind
from fc2_organizer.images import ImageFailureKind, ImageRole
from fc2_organizer.materialization import ArtifactKind


def project_image_failures(raw: tuple) -> tuple:
    """Contract 12.5: group by ``(role, kind)`` in declaration order; ``HTTP_STATUS`` groups list their distinct
    status codes ascending (taken by walking ``100..599``, never by sorting)."""
    groups = []
    for role in ImageRole:
        for kind in ImageFailureKind:
            count = 0
            statuses = set()
            for failure_role, failure_kind, http_status in raw:
                if failure_role is role and failure_kind is kind:
                    count += 1
                    if http_status is not None:
                        statuses.add(http_status)
            if count != 0:
                codes = tuple(code for code in range(100, 600) if code in statuses)
                groups.append(ImageFailureGroup(role=role, kind=kind, count=count, http_statuses=codes))
    return tuple(groups)


def project_source(source: SourceSnapshot, provenance: tuple) -> SourceDiagnostics:
    """Contract 11.6 / 12.2."""
    provided = ()
    if source.contributed:
        provided = tuple(name for name, ids in provenance if source.source_id in ids)
    trace = source.trace
    operational = source.status in OPERATIONAL_FAILURE_STATUSES
    if trace is None:
        return SourceDiagnostics(
            source_id=source.source_id, status=source.status, error_kind=source.error_kind,
            contributed=source.contributed, operational_failure=operational, provided_fields=provided,
            trace_available=False, attempt_count=None, max_attempts=None, deadline_exceeded=None,
            deadline_during=None, attempts=())
    return SourceDiagnostics(
        source_id=source.source_id, status=source.status, error_kind=source.error_kind,
        contributed=source.contributed, operational_failure=operational, provided_fields=provided,
        trace_available=True, attempt_count=len(trace.attempts), max_attempts=trace.max_attempts,
        deadline_exceeded=trace.deadline_exceeded, deadline_during=trace.deadline_during, attempts=trace.attempts)


def project_metadata(metadata: MetadataSnapshot) -> MetadataDiagnostics:
    """Contract 11.5 / 12.2 / 12.3: ``field_provenance`` in ``PROVENANCE_FIELD_ORDER`` (the snapshot already holds
    the known fields in that order; unknown keys never reach the snapshot)."""
    provenance = tuple(FieldProvenance(field=name, source_ids=ids) for name, ids in metadata.provenance
                       if name in PROVENANCE_FIELD_ORDER)
    return MetadataDiagnostics(
        status=metadata.status, generation=metadata.generation, error_kind=metadata.error_kind,
        aggregate_status=metadata.aggregate_status, traces_available=metadata.traces_available,
        sources=tuple(project_source(source, metadata.provenance) for source in metadata.sources),
        disabled_source_ids=metadata.disabled_source_ids, field_provenance=provenance,
        conflicts=metadata.conflicts, elapsed_ms=metadata.elapsed_ms)


def project_preflight(preflight: PreflightSnapshot) -> PreflightDiagnostics:
    """Contract 11.11 / 12.6: ``artifact_counts`` lists every ``ArtifactKind`` (zeros included)."""
    counts = tuple((kind, sum(1 for present in preflight.artifact_kinds if present is kind))
                   for kind in ArtifactKind)
    return PreflightDiagnostics(
        mode=preflight.mode, ready=preflight.ready, transfer_mode=preflight.transfer_mode,
        blockers=preflight.blockers, pending_unit_count=preflight.pending_unit_count,
        completed_unit_count=preflight.completed_unit_count, skipped_steps=preflight.skipped_steps,
        artifact_counts=counts)


def project_execution(execution) -> ExecutionDiagnostics:
    """Contract 11.12 / 12.6: ``effect_counts`` / ``artifact_counts`` list every member (zeros included)."""
    effect_counts = tuple((kind, sum(1 for effect, _ in execution.effect_kinds if effect is kind))
                          for kind in EffectKind)
    artifact_counts = tuple(
        (kind, sum(1 for effect, artifact in execution.effect_kinds
                   if effect is EffectKind.ARTIFACT_PUBLISHED and artifact is kind))
        for kind in ArtifactKind)
    leftovers = tuple(LeftoverTemporaryDiagnostics(directory_role=role, name=name)
                      for role, name in execution.leftovers)
    return ExecutionDiagnostics(
        status=execution.status, mode=execution.mode, transfer_mode=execution.transfer_mode,
        new_effect_count=execution.new_effect_count, effect_counts=effect_counts, artifact_counts=artifact_counts,
        failure=execution.failure, checkpoint_present=execution.checkpoint_present,
        skipped_steps=execution.skipped_steps, leftover_temporary_count=len(leftovers),
        leftover_temporaries=leftovers)


def project_item(item: ItemSnapshot) -> ItemDiagnostics:
    """Contract 12.1."""
    return ItemDiagnostics(
        index=item.index, generation=item.generation, canonical_number=item.canonical_number,
        source_name=item.source_name, source_size=item.source_size,
        target_directory_name=item.target_directory_name, target_media_name=item.target_media_name,
        preview_state=item.preview_state, issue=item.issue, warnings=item.warnings,
        conflict_with=item.conflict_with, retry_origin=item.retry_origin, disposition=item.disposition,
        retry_kind=item.retry_kind, retry_material_retained=item.retry_material_retained,
        metadata=None if item.metadata is None else project_metadata(item.metadata),
        image_failures=project_image_failures(item.image_failures),
        preflight=None if item.preflight is None else project_preflight(item.preflight),
        execution=None if item.execution is None else project_execution(item.execution))


def project_batch(snapshot: BatchSnapshot, path_policy: PathPolicy, timing_policy: TimingPolicy) -> BatchDiagnostics:
    """Contract 12.8: summary / outcome are carried as-is (never recomputed)."""
    return BatchDiagnostics(
        kind=snapshot.kind, shape=snapshot.shape, generation=snapshot.generation, batch_size=snapshot.batch_size,
        retry_scope=snapshot.retry_scope, path_policy=path_policy, timing_policy=timing_policy,
        metadata_batch=snapshot.metadata_counts, preview_summary=snapshot.preview_summary,
        execution_summary=snapshot.execution_summary, outcome=snapshot.outcome,
        items=tuple(project_item(item) for item in snapshot.items))
