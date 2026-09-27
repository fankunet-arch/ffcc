"""Per-item synchronous pipeline stages and Phase B conflicts (P4-C8 contract sections 11.3, 14.3, 15.2, 21).

Each stage function returns its success product **or** an ``ItemIssue``. An ordinary ``Exception`` of a
lower layer becomes the stage's frozen ``IssueReason`` (``error_type`` = class name through the total
``type_name`` helper; ``detail`` only through ``reason_detail`` for the exactly-typed lower errors). No
exception text, ``args``, path, URL or title is ever kept. A non-``Exception`` ``BaseException`` is never
caught: it propagates unchanged.

This module is the only one importing ``build_organize_plan``, ``prepare_publication``, ``render_movie_nfo``,
``build_artifact_requests`` and ``preflight_execution`` (contract section 34.1). ``acquire_images`` is
awaited by ``preview.py``; ``image_outcome`` here only classifies what that call produced. Every function
is synchronous; the only filesystem access is P4-C7's read-only ``preflight_execution``.
"""

from __future__ import annotations

import os

from fc2_metadata_core.batch import BatchItemResult, BatchItemStatus
from fc2_organizer.execution import (
    CheckpointError,
    CheckpointRejectionReason,
    ExecutionPreflight,
    ManifestRejectionReason,
    PlanGraphRejectionReason,
    preflight_execution,
)
from fc2_organizer.images import ImageAcquisitionResult
from fc2_organizer.materialization import MappingRejectionReason
from fc2_organizer.materialization.mapping import build_artifact_requests
from fc2_organizer.nfo import render_movie_nfo
from fc2_organizer.orchestration.models import (
    IssueReason,
    ItemIssue,
    OrchestrationStage,
    reason_detail,
    type_name,
)
from fc2_organizer.planning import build_organize_plan
from fc2_organizer.publication import prepare_publication

__all__ = [
    "metadata_outcome",
    "plan_stage",
    "publication_stage",
    "nfo_stage",
    "image_outcome",
    "manifest_stage",
    "preflight_stage",
    "phase_b_conflicts",
]

_UNKNOWN_TYPE = "UnknownType"
_MAX_ERROR_TYPE = 128


def _issue(stage: OrchestrationStage, reason: IssueReason, exc: object) -> ItemIssue:
    return ItemIssue(stage, reason, type_name(exc))


def _detailed_issue(stage: OrchestrationStage, reason: IssueReason, exc: object,
                    allowed: tuple[type, ...]) -> ItemIssue:
    """``detail`` is the frozen ``.reason`` of an exactly-typed lower error, kept only when it is a member of
    an enum this reason allows (contract section 10.2); otherwise ``None``."""
    detail = reason_detail(exc)
    return ItemIssue(stage, reason, type_name(exc), detail if type(detail) in allowed else None)


def _engine_error_type(value: object) -> str:
    """Phase 3 ``BatchItemResult.error_type`` is already a class name produced by its total helper; anything
    outside the ``ItemIssue`` shape (identifier, 1..128) collapses to ``UnknownType``."""
    if type(value) is str and 1 <= len(value) <= _MAX_ERROR_TYPE and value.isidentifier():
        return value
    return _UNKNOWN_TYPE


def metadata_outcome(metadata: BatchItemResult):
    """Contract section 11.3: the ``AggregationResult`` to plan with, or the METADATA issue."""
    if metadata.aggregation_result is None:
        return ItemIssue(OrchestrationStage.METADATA, IssueReason.METADATA_ENGINE_FAILURE,
                         _engine_error_type(metadata.error_type), metadata.error_kind)
    if metadata.status is BatchItemStatus.FAILED:
        return ItemIssue(OrchestrationStage.METADATA, IssueReason.METADATA_UNAVAILABLE)
    return metadata.aggregation_result


def plan_stage(media_item, canonical_number, aggregation_result, library_root, output_policy):
    try:
        return build_organize_plan(media_item, canonical_number, aggregation_result.metadata, library_root,
                                   policy=output_policy)
    except Exception as exc:  # noqa: BLE001 - item isolation (contract section 20.1)
        return _issue(OrchestrationStage.PLANNING, IssueReason.PLANNING_REJECTED, exc)


def publication_stage(plan, aggregation_result):
    try:
        return prepare_publication(plan, aggregation_result)
    except Exception as exc:  # noqa: BLE001
        return _issue(OrchestrationStage.PUBLICATION, IssueReason.PUBLICATION_REJECTED, exc)


def nfo_stage(record):
    try:
        return render_movie_nfo(record)
    except Exception as exc:  # noqa: BLE001
        return _issue(OrchestrationStage.NFO_RENDER, IssueReason.NFO_RENDER_FAILED, exc)


def image_outcome(result: object, failure_type: str | None, reservation: int):
    """Classify one awaited ``acquire_images`` call (contract sections 15.2, 19.6.4, 22.2).

    ``failure_type`` is the class name of the ordinary ``Exception`` it raised (``None`` if it returned).
    A returned value that is not an exact ``ImageAcquisitionResult``, or whose ``total_bytes`` exceeds the
    reservation ``R`` (a P4-C5 contract violation, only possible from a test double), is an
    ``IMAGE_ACQUISITION_ERROR`` and none of its bytes are kept.
    """
    if failure_type is not None:
        return ItemIssue(OrchestrationStage.IMAGE_ACQUISITION, IssueReason.IMAGE_ACQUISITION_ERROR, failure_type)
    if type(result) is not ImageAcquisitionResult:
        return _issue(OrchestrationStage.IMAGE_ACQUISITION, IssueReason.IMAGE_ACQUISITION_ERROR, result)
    if result.total_bytes > reservation:
        return ItemIssue(OrchestrationStage.IMAGE_ACQUISITION, IssueReason.IMAGE_ACQUISITION_ERROR,
                         "ImageAcquisitionResult")
    return result


def manifest_stage(plan, nfo_text, images):
    try:
        return build_artifact_requests(plan, nfo_text, images)
    except Exception as exc:  # noqa: BLE001
        return _detailed_issue(OrchestrationStage.MANIFEST, IssueReason.MANIFEST_REJECTED, exc,
                               (MappingRejectionReason,))


def preflight_stage(plan, artifacts, checkpoint=None):
    """``ExecutionPreflight`` (ready or not) or a PREFLIGHT issue. ``CheckpointError`` (only possible with a
    checkpoint) is ``CHECKPOINT_REJECTED``; every other ordinary exception is ``PREFLIGHT_REJECTED``."""
    try:
        return preflight_execution(plan, artifacts, checkpoint)
    except Exception as exc:  # noqa: BLE001
        if type(exc) is CheckpointError and type(reason_detail(exc)) is CheckpointRejectionReason:
            return _detailed_issue(OrchestrationStage.PREFLIGHT, IssueReason.CHECKPOINT_REJECTED, exc,
                                   (CheckpointRejectionReason,))
        return _detailed_issue(OrchestrationStage.PREFLIGHT, IssueReason.PREFLIGHT_REJECTED, exc,
                               (PlanGraphRejectionReason, ManifestRejectionReason))


def _target_key(path: str) -> str:
    return path.casefold() if os.name == "nt" else path


def _peers(groups: dict, indices: list[int]) -> dict[int, set[int]]:
    peers: dict[int, set[int]] = {index: set() for index in indices}
    for members in groups.values():
        if len(members) >= 2:
            for member in members:
                peers[member].update(other for other in members if other != member)
    return peers


def phase_b_conflicts(entries: list[tuple[int, ExecutionPreflight]]) -> dict[int, tuple[IssueReason, tuple[int, ...]]]:
    """Contract section 14.3 over ``(index, preflight)`` pairs of one preview (index ascending): group by the
    source ``(device, inode)`` (when ``source_identity`` is known) and by the target directory (Windows
    ``casefold``, POSIX exact). Returns ``index -> (reason, conflict_with)`` for every member of a group of
    size >= 2 (same source wins over same target). Pure: uses only the preflight / plan values."""
    by_source: dict[tuple[int, int], list[int]] = {}
    by_target: dict[str, list[int]] = {}
    indices = [index for index, _ in entries]
    for index, preflight in entries:
        identity = preflight.source_identity
        if identity is not None:
            by_source.setdefault((identity.device, identity.inode), []).append(index)
        by_target.setdefault(_target_key(preflight.plan.target_directory.absolute_path), []).append(index)
    source_peers = _peers(by_source, indices)
    target_peers = _peers(by_target, indices)
    conflicts: dict[int, tuple[IssueReason, tuple[int, ...]]] = {}
    for index in indices:
        if source_peers[index]:
            reason = IssueReason.DUPLICATE_SOURCE_IN_BATCH
        elif target_peers[index]:
            reason = IssueReason.DUPLICATE_TARGET_IN_BATCH
        else:
            continue
        conflicts[index] = (reason, tuple(sorted(source_peers[index] | target_peers[index])))
    return conflicts
