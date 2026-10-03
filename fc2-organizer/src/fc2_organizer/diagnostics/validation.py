"""Local read-only validation of the consumed input graph (P4-C9 contract section 9).

This module is P4-C9's own validation: it never calls an upstream ``__post_init__``, a private / dunder name,
an upstream instance method (``meets_minimum_success`` ...), ``revalidate`` or any reflection / introspection
primitive, and it never captures an upstream exception. Rules (contract sections 9.0.1, 9.2, 9.10, 9.12):

* every object is confirmed ``type(x) is ExactClass`` before any of its fields is read (V-1);
* every caller-originated container passes **Phase V** (exact container type, structural limit, every
  element / key exact-type checked) before any **Phase R** operation (membership, equality, uniqueness, lookup)
  touches it (V-2);
* ``field_sources`` is scanned in one bounded pass (count + ``type(key) is str``) before any fixed known-key
  lookup (contract 9.2 item 9);
* exact ``int`` values are only ever compared with ``int`` constants; ``math.isfinite`` is applied to exact
  ``float`` only; timing conversions (``* 1000``, ``int(float)``) happen only after a total safe-bound gate
  (contract 9.12);
* no ``sorted`` / ``min`` / ``max`` / truthiness / text conversion of a caller-originated value is used.

``build_preview_snapshot`` / ``build_execution_snapshot`` run the contract section 24.2 steps 3-7 and return the
immutable validation snapshot that ``projection`` consumes. Every failure is a fixed-wording ``Diagnostics*``
error raised outside any ``except`` block.
"""

from __future__ import annotations

import math
import os
import re
import types

from fc2_metadata_core.aggregation import (
    CONFLICT_FIELDS,
    OPERATIONAL_FAILURE_STATUSES,
    RETRY_ELIGIBLE_KINDS,
    AggregateStatus,
    AggregationResult,
    FieldConflict,
    SourceAttempt,
    SourceExecutionTrace,
)
from fc2_metadata_core.batch import (
    BatchItemErrorKind,
    BatchItemResult,
    BatchItemStatus,
    BatchLineage,
    BatchResult,
)
from fc2_metadata_core.models import NormalizedMetadata, SourceErrorKind, SourceResult, SourceStatus
from fc2_metadata_core.normalize import is_valid_fc2_number
from fc2_organizer.diagnostics.errors import (
    DiagnosticsIntegrityError,
    DiagnosticsResourceLimitError,
    DiagnosticsUnsafeValueError,
)
from fc2_organizer.diagnostics.models import (
    BLOCKED_REASONS,
    DUPLICATE_REASONS,
    LEFTOVER_NAME_PATTERN,
    MAX_ATTEMPTS_PER_SOURCE,
    MAX_BLOCKERS_PER_ITEM,
    MAX_CONFLICTS_PER_ITEM,
    MAX_DIAGNOSTIC_ITEMS,
    MAX_LEFTOVER_TEMPORARIES_PER_ITEM,
    MAX_PROVENANCE_KEYS,
    MAX_SOURCES_PER_ITEM,
    MAX_TIMING_MS,
    MAX_TIMING_SECONDS,
    PROVENANCE_FIELD_ORDER,
    BatchSnapshot,
    DiagnosticsKind,
    ExecutionSnapshot,
    FieldConflictDiagnostics,
    IssueDiagnostics,
    ItemSnapshot,
    MetadataBatchCounts,
    MetadataSnapshot,
    PathPolicy,
    PreflightSnapshot,
    ResultShape,
    SourceAttemptDiagnostics,
    SourceSnapshot,
    TimingPolicy,
    TraceSnapshot,
    allowed_error_kinds,
    artifact_role,
    blocker_problem,
    execution_summary_problem,
    failure_problem,
    is_error_type,
    is_safe_basename,
    is_safe_id,
    issue_rule,
    preview_summary_problem,
)
from fc2_organizer.discovery import DiscoveredMediaItem
from fc2_organizer.execution import (
    CompletedEffect,
    EffectKind,
    ExecutionCheckpoint,
    ExecutionPreflight,
    ExecutionResult,
    ExecutionStatus,
    ExecutionStep,
    ExecutionUnit,
    LeftoverTemporary,
    PathRole,
    PreflightMode,
    TransferMode,
)
from fc2_organizer.images import ImageAcquisitionPolicy, ImageCandidateFailure, ImageFailureKind, ImageRole
from fc2_organizer.materialization import ArtifactKind, ArtifactWriteRequest
from fc2_organizer.orchestration import (
    MAX_RETAINED_ARTIFACT_BYTES_LIMIT,
    BatchOutcome,
    ExecutionDisposition,
    IssueReason,
    ItemExecution,
    ItemIssue,
    ItemPreview,
    ItemWarning,
    OrchestrationStage,
    PreviewState,
    RetryKind,
    RetryMaterial,
)
from fc2_organizer.planning import OrganizePlan, OutputPolicy, PlannedOperation, PlannedOperationKind, PlannedPath

HEX32 = re.compile(r"[0-9a-f]{32}")
HEX64 = re.compile(r"[0-9a-f]{64}")

# Contract section 9.12: exact-representable float gates, derived once from small int constants.
TIMING_MS_GATE = float(MAX_TIMING_MS + 1)
BACKOFF_SECONDS_GATE = float(MAX_TIMING_SECONDS)

_OPTIONAL_STEPS = (ExecutionStep.MATERIALIZE_POSTER, ExecutionStep.MATERIALIZE_FANART,
                   ExecutionStep.MATERIALIZE_THUMB)
_PLAN_OPERATION_KINDS = (
    PlannedOperationKind.CREATE_DIRECTORY, PlannedOperationKind.MOVE_MEDIA, PlannedOperationKind.MATERIALIZE_NFO,
    PlannedOperationKind.MATERIALIZE_POSTER, PlannedOperationKind.MATERIALIZE_FANART,
    PlannedOperationKind.MATERIALIZE_THUMB, PlannedOperationKind.ENSURE_EXTRAFANART_DIRECTORY,
)
_MATERIAL_KINDS = (RetryKind.PREFLIGHT_RECHECK, RetryKind.FRESH_REEXECUTE, RetryKind.RESUME, RetryKind.DEFERRED)


# --------------------------------------------------------------------------- failure helpers


def fail(message: str) -> None:
    raise DiagnosticsIntegrityError(message)


def over_limit(message: str) -> None:
    raise DiagnosticsResourceLimitError(message)


def unsafe(message: str) -> None:
    raise DiagnosticsUnsafeValueError(message)


# --------------------------------------------------------------------------- exact scalar helpers (contract 9.2)


def is_hex(value: object, pattern: re.Pattern[str]) -> bool:
    return type(value) is str and pattern.fullmatch(value) is not None


def is_int(value: object, minimum: int = 0) -> bool:
    return type(value) is int and value >= minimum


def is_non_empty_str(value: object) -> bool:
    return type(value) is str and len(value) >= 1


def same_str(left: object, right: object) -> bool:
    return type(left) is str and type(right) is str and left == right


def require_int(value: object, minimum: int, message: str) -> None:
    if type(value) is not int or value < minimum:
        fail(message)


def require_bool(value: object, message: str) -> None:
    if type(value) is not bool:
        fail(message)


def require_enum(value: object, enum_type: type, message: str) -> None:
    if type(value) is not enum_type:
        fail(message)


def require_opt_enum(value: object, enum_type: type, message: str) -> None:
    if value is not None and type(value) is not enum_type:
        fail(message)


def require_bounded_tuple(value: object, maximum: int, message: str, limit_message: str) -> None:
    """Phase V container gate: an exact ``tuple`` whose ``len`` is checked *before* any iteration."""
    if type(value) is not tuple:
        fail(message)
    if len(value) > maximum:
        over_limit(limit_message)


def require_tuple_of(value: object, item_type: type, message: str) -> None:
    if type(value) is not tuple:
        fail(message)
    for item in value:
        if type(item) is not item_type:
            fail(message)


def check_number(value: object, message: str) -> None:
    """Validation-only numeric field (contract 9.12 N-01 / N-02 / N-04 / N-05): exact ``int`` or exact ``float``,
    non-negative, ``float`` finite; no upper bound, no conversion. ``math.isfinite`` only sees a ``float``."""
    kind = type(value)
    if kind is int:
        if value < 0:
            fail(message)
    elif kind is float:
        if not math.isfinite(value):
            fail(message)
        if value < 0.0:
            fail(message)
    else:
        fail(message)


def is_zero(value: object) -> bool:
    """``value == 0`` for a validated number, with same-type comparison only (contract 9.12 TN-3)."""
    if type(value) is int:
        return value == 0
    return value == 0.0


def publish_elapsed_ms(value: object) -> int:
    """N-06: gate the (already validated) elapsed value *before* any conversion."""
    if type(value) is int:
        if value > MAX_TIMING_MS:
            unsafe("a timing value exceeds MAX_TIMING_MS")
        return value
    if value >= TIMING_MS_GATE:
        unsafe("a timing value exceeds MAX_TIMING_MS")
    return int(value)


def publish_backoff_ms(value: object) -> int:
    """N-07: SAFE BOUND BEFORE MULTIPLY / INT CONVERSION -- gate the seconds value, then convert."""
    if type(value) is int:
        if value > MAX_TIMING_SECONDS:
            unsafe("a timing value exceeds MAX_TIMING_MS")
        return value * 1000
    if value > BACKOFF_SECONDS_GATE:
        unsafe("a timing value exceeds MAX_TIMING_MS")
    return int(value * 1000)


# --------------------------------------------------------------------------- small shared upstream objects


def check_lineage(lineage: object) -> None:
    """M-03."""
    if type(lineage) is not BatchLineage:
        fail("lineage must be an exact BatchLineage")
    if not is_hex(lineage.token, HEX32):
        fail("lineage token must be 32 lowercase hex characters")


def check_media_item(media: object) -> None:
    """M-10."""
    if type(media) is not DiscoveredMediaItem:
        fail("media_item must be an exact DiscoveredMediaItem")
    require_int(media.index, 0, "DiscoveredMediaItem.index must be an exact int >= 0")
    if not is_non_empty_str(media.source_path) or not os.path.isabs(media.source_path):
        fail("DiscoveredMediaItem.source_path must be an absolute non-empty exact str")
    if not is_non_empty_str(media.relative_path):
        fail("DiscoveredMediaItem.relative_path must be a non-empty exact str")
    if not is_non_empty_str(media.extension) or not media.extension.startswith("."):
        fail("DiscoveredMediaItem.extension must be an exact str starting with a dot")
    require_int(media.size, 0, "DiscoveredMediaItem.size must be an exact int >= 0")


def check_planned_path(path: object) -> None:
    """M-12."""
    if type(path) is not PlannedPath:
        fail("a plan path must be an exact PlannedPath")
    if not is_non_empty_str(path.absolute_path) or not os.path.isabs(path.absolute_path):
        fail("PlannedPath.absolute_path must be an absolute non-empty exact str")


def check_plan(plan: object) -> None:
    """M-11 / M-13 and the contract 9.6.5 structural layout."""
    if type(plan) is not OrganizePlan:
        fail("plan must be an exact OrganizePlan")
    for text in (plan.source_path, plan.library_root):
        if not is_non_empty_str(text) or not os.path.isabs(text):
            fail("OrganizePlan.source_path / library_root must be absolute non-empty exact strs")
    if not is_non_empty_str(plan.source_relative_path) or not is_non_empty_str(plan.source_extension):
        fail("OrganizePlan source text fields must be non-empty exact strs")
    if not is_non_empty_str(plan.canonical_number):
        fail("OrganizePlan.canonical_number must be a non-empty exact str")
    require_int(plan.source_index, 0, "OrganizePlan.source_index must be an exact int >= 0")
    require_int(plan.source_size, 0, "OrganizePlan.source_size must be an exact int >= 0")
    target_directory = plan.target_directory
    target_media = plan.target_media_path
    children = (plan.nfo_path, plan.poster_path, plan.fanart_path, plan.thumb_path, plan.extrafanart_directory)
    check_planned_path(target_directory)
    check_planned_path(target_media)
    for child in children:
        check_planned_path(child)
    operations = plan.operations
    if type(operations) is not tuple or len(operations) != 7:
        fail("OrganizePlan.operations must be a tuple of exactly 7 PlannedOperation")
    for operation in operations:
        if type(operation) is not PlannedOperation:
            fail("OrganizePlan.operations must hold exact PlannedOperation values")
        require_enum(operation.kind, PlannedOperationKind, "PlannedOperation.kind must be a PlannedOperationKind")
        check_planned_path(operation.target)
        if operation.kind is PlannedOperationKind.MOVE_MEDIA:
            check_planned_path(operation.source)
        elif operation.source is not None:
            fail("only MOVE_MEDIA carries a source path")
    # contract 9.6.5: the frozen layout, character for character
    td = target_directory.absolute_path
    if td != os.path.join(plan.library_root, plan.canonical_number):
        fail("OrganizePlan.target_directory does not match the frozen layout")
    if target_media.absolute_path != os.path.join(td, plan.canonical_number + plan.source_extension.lower()):
        fail("OrganizePlan.target_media_path does not match the frozen layout")
    for child in children:
        name = os.path.basename(child.absolute_path)
        if len(name) < 1 or os.path.join(td, name) != child.absolute_path:
            fail("an OrganizePlan child path does not match the frozen layout")
    texts = (td, target_media.absolute_path, children[0].absolute_path, children[1].absolute_path,
             children[2].absolute_path, children[3].absolute_path, children[4].absolute_path)
    if len(set(texts)) != 7:
        fail("OrganizePlan paths must be pairwise distinct")
    expected_targets = texts
    for position in range(7):
        operation = operations[position]
        if operation.kind is not _PLAN_OPERATION_KINDS[position]:
            fail("OrganizePlan.operations are not in the frozen order")
        if operation.target.absolute_path != expected_targets[position]:
            fail("OrganizePlan.operations targets do not match the plan paths")
    if operations[1].source.absolute_path != plan.source_path:
        fail("the MOVE_MEDIA source must be the plan source path")


def check_image_failure(failure: object) -> None:
    """M-22."""
    if type(failure) is not ImageCandidateFailure:
        fail("image_failures must hold exact ImageCandidateFailure values")
    require_enum(failure.role, ImageRole, "ImageCandidateFailure.role must be an ImageRole")
    require_int(failure.candidate_index, 0, "ImageCandidateFailure.candidate_index must be an exact int >= 0")
    require_enum(failure.kind, ImageFailureKind, "ImageCandidateFailure.kind must be an ImageFailureKind")
    if failure.kind is ImageFailureKind.HTTP_STATUS:
        if type(failure.http_status) is not int or failure.http_status < 100 or failure.http_status > 599:
            fail("ImageCandidateFailure.http_status must be an exact int in 100..599")
    elif failure.http_status is not None:
        fail("ImageCandidateFailure.http_status must be None unless kind is HTTP_STATUS")


def check_issue(issue: object) -> None:
    """M-07 (table T-1)."""
    if type(issue) is not ItemIssue:
        fail("issue must be an exact ItemIssue")
    require_enum(issue.stage, OrchestrationStage, "ItemIssue.stage must be an OrchestrationStage")
    require_enum(issue.reason, IssueReason, "ItemIssue.reason must be an IssueReason")
    stage, needs_error_type, detail_types, needs_detail = issue_rule(issue.reason)
    if issue.stage is not stage:
        fail("ItemIssue.stage does not match its reason")
    if needs_error_type:
        if not is_error_type(issue.error_type):
            fail("ItemIssue.error_type must be an identifier of 1..128 characters for this reason")
    elif issue.error_type is not None:
        fail("ItemIssue.error_type must be None for this reason")
    if issue.detail is None:
        if needs_detail:
            fail("ItemIssue.detail is required for this reason")
    elif type(issue.detail) not in detail_types:
        fail("ItemIssue.detail is not a member of an enum allowed for this reason")


def check_warnings_field(warnings: object) -> None:
    require_tuple_of(warnings, ItemWarning, "warnings must be a tuple of exact ItemWarning")
    if tuple(member for member in ItemWarning if member in warnings) != warnings:
        fail("warnings must be unique and in ItemWarning declaration order")


def check_conflict_with(value: object, own_index: int) -> None:
    if type(value) is not tuple:
        fail("conflict_with must be a tuple of exact ints")
    previous = -1
    for peer in value:
        if type(peer) is not int or peer <= previous:
            fail("conflict_with must be strictly increasing exact ints >= 0")
        previous = peer
    if own_index in value:
        fail("conflict_with never contains the item's own index")


# --------------------------------------------------------------------------- artifacts / preflight / execution


def check_artifact_request(request: object) -> None:
    """M-24 (``content`` is only type-confirmed)."""
    if type(request) is not ArtifactWriteRequest:
        fail("artifacts must hold exact ArtifactWriteRequest values")
    require_enum(request.kind, ArtifactKind, "ArtifactWriteRequest.kind must be an ArtifactKind")
    if not is_non_empty_str(request.target_path):
        fail("ArtifactWriteRequest.target_path must be a non-empty exact str")
    if type(request.content) is not bytes:
        fail("ArtifactWriteRequest.content must be exact bytes")
    if request.kind is ArtifactKind.EXTRAFANART:
        if type(request.ordinal) is not int or request.ordinal < 1:
            fail("an extrafanart ordinal must be an exact int >= 1")
    elif request.ordinal is not None:
        fail("only extrafanart carries an ordinal")


def check_artifacts(artifacts: object) -> None:
    """Phase V of a manifest tuple (no per-tuple count limit, contract M-23 / M-30)."""
    if type(artifacts) is not tuple:
        fail("an artifact manifest must be an exact tuple")
    for request in artifacts:
        check_artifact_request(request)


def payload_bytes(artifacts: tuple) -> int:
    """Sum of ``len(request.content)`` -- every request counted per reference (contract 9.6.1 / 9.6.2)."""
    total = 0
    for request in artifacts:
        total += len(request.content)
    return total


def check_manifest_layout(artifacts: tuple, plan: OrganizePlan) -> None:
    """Contract 9.6.5: NFO, then at most one each of POSTER / FANART / THUMB in order, then EXTRAFANART 1..k."""
    count = len(artifacts)
    if count < 1:
        fail("a manifest starts with the NFO")
    first = artifacts[0]
    if first.kind is not ArtifactKind.NFO or first.target_path != plan.nfo_path.absolute_path:
        fail("the first manifest entry must be the plan NFO")
    position = 1
    for kind, planned in ((ArtifactKind.POSTER, plan.poster_path), (ArtifactKind.FANART, plan.fanart_path),
                          (ArtifactKind.THUMB, plan.thumb_path)):
        if position < count and artifacts[position].kind is kind:
            if artifacts[position].target_path != planned.absolute_path:
                fail("a manifest image entry does not match its plan path")
            position += 1
    ordinal = 1
    directory = plan.extrafanart_directory.absolute_path
    while position < count:
        request = artifacts[position]
        if request.kind is not ArtifactKind.EXTRAFANART or request.ordinal != ordinal:
            fail("manifest extrafanart entries must follow with ordinals 1..k")
        if os.path.join(directory, os.path.basename(request.target_path)) != request.target_path:
            fail("a manifest extrafanart path does not match the plan directory")
        position += 1
        ordinal += 1


def check_skipped_steps(steps: object) -> None:
    require_tuple_of(steps, ExecutionStep, "skipped_steps must be a tuple of ExecutionStep")
    for step in steps:
        if step not in _OPTIONAL_STEPS:
            fail("skipped_steps may only name optional image steps")


def check_preflight(preflight: object, plan: object) -> None:
    """M-23 + M-24 + the contract 9.6.5 manifest relation (``plan`` is already validated)."""
    if type(preflight) is not ExecutionPreflight:
        fail("preflight must be an exact ExecutionPreflight")
    if not is_hex(preflight.preflight_id, HEX32):
        fail("ExecutionPreflight.preflight_id must be 32 lowercase hex characters")
    require_enum(preflight.mode, PreflightMode, "ExecutionPreflight.mode must be a PreflightMode")
    if type(preflight.plan) is not OrganizePlan or preflight.plan is not plan:
        fail("ExecutionPreflight.plan must be the item's plan (same object)")
    check_artifacts(preflight.artifacts)
    if preflight.checkpoint is not None and type(preflight.checkpoint) is not ExecutionCheckpoint:
        fail("ExecutionPreflight.checkpoint must be None or an exact ExecutionCheckpoint")
    if (preflight.mode is PreflightMode.RESUME) != (preflight.checkpoint is not None):
        fail("ExecutionPreflight.mode is RESUME iff a checkpoint is present")
    if (not is_hex(preflight.plan_fingerprint, HEX64) or not is_hex(preflight.manifest_fingerprint, HEX64)
            or not is_hex(preflight.seal, HEX64)):
        fail("ExecutionPreflight fingerprints / seal must be 64 lowercase hex characters")
    require_bool(preflight.ready, "ExecutionPreflight.ready must be an exact bool")
    require_bounded_tuple(preflight.blockers, MAX_BLOCKERS_PER_ITEM, "ExecutionPreflight.blockers must be a tuple",
                          "ExecutionPreflight.blockers exceed MAX_BLOCKERS_PER_ITEM")
    for blocker in preflight.blockers:
        if blocker_problem(blocker) is not None:
            fail("ExecutionPreflight.blockers must hold valid PreflightBlocker values")
    if preflight.ready != (len(preflight.blockers) == 0):
        fail("ExecutionPreflight.ready is true iff there are no blockers")
    if preflight.transfer_mode is not None and type(preflight.transfer_mode) is not TransferMode:
        fail("ExecutionPreflight.transfer_mode must be a TransferMode or None")
    require_tuple_of(preflight.completed_units, ExecutionUnit, "ExecutionPreflight units must be ExecutionUnit tuples")
    require_tuple_of(preflight.pending_units, ExecutionUnit, "ExecutionPreflight units must be ExecutionUnit tuples")
    check_skipped_steps(preflight.skipped_steps)
    check_manifest_layout(preflight.artifacts, plan)


def check_effect(effect: object) -> None:
    """M-27 (table T-3); ``path`` / ``identity`` / ``size`` / ``sha256`` are never read."""
    if type(effect) is not CompletedEffect:
        fail("completed_effects must hold exact CompletedEffect values")
    require_enum(effect.kind, EffectKind, "CompletedEffect.kind must be an EffectKind")
    require_enum(effect.role, PathRole, "CompletedEffect.role must be a PathRole")
    require_opt_enum(effect.artifact_kind, ArtifactKind, "CompletedEffect.artifact_kind must be an ArtifactKind or None")
    if effect.ordinal is not None and type(effect.ordinal) is not int:
        fail("CompletedEffect.ordinal must be an exact int or None")
    if (effect.kind is EffectKind.ARTIFACT_PUBLISHED) != (effect.artifact_kind is not None):
        fail("an effect has an artifact_kind iff it is ARTIFACT_PUBLISHED")
    if effect.kind is EffectKind.ARTIFACT_PUBLISHED:
        if effect.role is not artifact_role(effect.artifact_kind):
            fail("an ARTIFACT_PUBLISHED effect needs the role of its artifact kind")
        if effect.artifact_kind is ArtifactKind.EXTRAFANART:
            if effect.ordinal is None or effect.ordinal < 1:
                fail("an extrafanart effect needs an ordinal >= 1")
        elif effect.ordinal is not None:
            fail("only extrafanart effects carry an ordinal")
        return
    if effect.ordinal is not None:
        fail("only ARTIFACT_PUBLISHED effects carry an ordinal")
    if effect.kind is EffectKind.SOURCE_REMOVED:
        expected = PathRole.SOURCE
    elif effect.kind is EffectKind.MEDIA_PUBLISHED:
        expected = PathRole.TARGET_MEDIA
    elif effect.kind is EffectKind.TARGET_DIRECTORY_CREATED:
        expected = PathRole.TARGET_DIRECTORY
    else:
        expected = PathRole.EXTRAFANART_DIRECTORY
    if effect.role is not expected:
        fail("a CompletedEffect has the frozen role of its kind")


def check_leftover(leftover: object) -> None:
    """M-29."""
    if type(leftover) is not LeftoverTemporary:
        fail("leftover_temporaries must hold exact LeftoverTemporary values")
    if type(leftover.directory_role) is not PathRole or (
            leftover.directory_role is not PathRole.TARGET_DIRECTORY
            and leftover.directory_role is not PathRole.EXTRAFANART_DIRECTORY):
        fail("LeftoverTemporary.directory_role must be TARGET_DIRECTORY or EXTRAFANART_DIRECTORY")
    if type(leftover.name) is not str or LEFTOVER_NAME_PATTERN.fullmatch(leftover.name) is None:
        fail("LeftoverTemporary.name must match the frozen temporary file format")


def check_execution_result(result: object) -> None:
    """M-26 (+ M-27 / M-28 / M-29)."""
    if type(result) is not ExecutionResult:
        fail("execution must be an exact ExecutionResult")
    require_enum(result.status, ExecutionStatus, "ExecutionResult.status must be an ExecutionStatus")
    require_enum(result.mode, PreflightMode, "ExecutionResult.mode must be a PreflightMode")
    if not is_hex(result.preflight_id, HEX32):
        fail("ExecutionResult.preflight_id must be 32 lowercase hex characters")
    require_opt_enum(result.transfer_mode, TransferMode, "ExecutionResult.transfer_mode must be a TransferMode or None")
    if type(result.completed_effects) is not tuple:
        fail("ExecutionResult.completed_effects must be an exact tuple")
    for effect in result.completed_effects:
        check_effect(effect)
    if type(result.new_effect_count) is not int or result.new_effect_count < 0 or (
            result.new_effect_count > len(result.completed_effects)):
        fail("ExecutionResult.new_effect_count must be an exact int in [0, len(completed_effects)]")
    if result.failure is not None and failure_problem(result.failure) is not None:
        fail("ExecutionResult.failure must be a valid ExecutionFailure or None")
    if result.checkpoint is not None and type(result.checkpoint) is not ExecutionCheckpoint:
        fail("ExecutionResult.checkpoint must be None or an exact ExecutionCheckpoint")
    require_bounded_tuple(result.leftover_temporaries, MAX_LEFTOVER_TEMPORARIES_PER_ITEM,
                          "ExecutionResult.leftover_temporaries must be an exact tuple",
                          "ExecutionResult.leftover_temporaries exceed MAX_LEFTOVER_TEMPORARIES_PER_ITEM")
    for leftover in result.leftover_temporaries:
        check_leftover(leftover)
    if result.media_sha256 is not None and not is_hex(result.media_sha256, HEX64):
        fail("ExecutionResult.media_sha256 must be 64 lowercase hex characters or None")
    check_skipped_steps(result.skipped_steps)
    if (result.status is ExecutionStatus.SUCCESS) != (result.failure is None):
        fail("ExecutionResult.failure is present iff the status is not SUCCESS")
    if (result.status is ExecutionStatus.PARTIAL) != (result.checkpoint is not None):
        fail("ExecutionResult.checkpoint is present iff the status is PARTIAL")
    if result.status is ExecutionStatus.FAILED:
        if len(result.completed_effects) != 0:
            fail("a FAILED result has no completed effects")
    elif len(result.completed_effects) == 0:
        fail("a SUCCESS / PARTIAL result has at least one completed effect")


def check_retry_material(material: object) -> None:
    """M-30 (the relations to the item are checked by the caller)."""
    if type(material) is not RetryMaterial:
        fail("retry_material must be an exact RetryMaterial")
    if type(material.plan) is not OrganizePlan:
        fail("RetryMaterial.plan must be an exact OrganizePlan")
    check_artifacts(material.artifacts)
    if material.checkpoint is not None and type(material.checkpoint) is not ExecutionCheckpoint:
        fail("RetryMaterial.checkpoint must be None or an exact ExecutionCheckpoint")


# --------------------------------------------------------------------------- Phase 3 metadata graph (M-14 .. M-21)


def metadata_meets_minimum(metadata: object) -> bool:
    """M-18 minimum success, from ``number`` / ``title`` only (``metadata`` is an exact NormalizedMetadata)."""
    number = metadata.number
    title = metadata.title
    if number is not None and type(number) is not str:
        fail("NormalizedMetadata.number must be None or an exact str")
    if title is not None and type(title) is not str:
        fail("NormalizedMetadata.title must be None or an exact str")
    if number is None or title is None:
        return False
    return is_valid_fc2_number(number) and len(title.strip()) >= 1


def check_source_result(result: object) -> bool:
    """M-17. Returns whether ``result.metadata`` (if any) meets minimum success."""
    if type(result) is not SourceResult:
        fail("source_results must hold exact SourceResult values")
    if type(result.source_id) is not str or len(result.source_id.strip()) < 1:
        fail("SourceResult.source_id must be a non-blank exact str")
    require_enum(result.status, SourceStatus, "SourceResult.status must be a SourceStatus")
    check_number(result.elapsed_ms, "SourceResult.elapsed_ms must be a finite number >= 0")
    meets = False
    if result.metadata is not None:
        if type(result.metadata) is not NormalizedMetadata:
            fail("SourceResult.metadata must be None or an exact NormalizedMetadata")
        meets = metadata_meets_minimum(result.metadata)
    require_opt_enum(result.error_kind, SourceErrorKind, "SourceResult.error_kind must be a SourceErrorKind or None")
    if result.error_detail is not None and type(result.error_detail) is not str:
        fail("SourceResult.error_detail must be None or an exact str")
    status = result.status
    if status is SourceStatus.SUCCESS:
        if result.metadata is None or not meets or result.error_kind is not None or result.error_detail is not None:
            fail("a SUCCESS SourceResult carries minimum-success metadata and no error")
        return meets
    if result.error_kind is None or result.error_kind not in allowed_error_kinds(status):
        fail("a failed SourceResult needs an error_kind allowed for its status")
    if result.error_detail is None or len(result.error_detail.strip()) < 1:
        fail("a failed SourceResult needs a non-blank error_detail")
    if status is SourceStatus.PARSE_ERROR or status is SourceStatus.INVALID_RESPONSE:
        if result.metadata is not None and meets:
            fail("a PARSE_ERROR / INVALID_RESPONSE SourceResult has no minimum-success metadata")
    elif result.metadata is not None:
        fail("this SourceResult status carries no metadata")
    return meets


def check_attempt(attempt: object) -> None:
    """M-20 (the timing values are only validated here; conversion happens in the safe-output step)."""
    if type(attempt) is not SourceAttempt:
        fail("attempts must hold exact SourceAttempt values")
    require_int(attempt.sequence, 1, "SourceAttempt.sequence must be an exact int >= 1")
    require_enum(attempt.status, SourceStatus, "SourceAttempt.status must be a SourceStatus")
    require_opt_enum(attempt.error_kind, SourceErrorKind, "SourceAttempt.error_kind must be a SourceErrorKind or None")
    check_number(attempt.elapsed_ms, "SourceAttempt.elapsed_ms must be a finite number >= 0")
    check_number(attempt.backoff_before_seconds, "SourceAttempt.backoff_before_seconds must be a finite number >= 0")
    require_bool(attempt.completed, "SourceAttempt.completed must be an exact bool")
    if attempt.status is SourceStatus.SUCCESS:
        if attempt.error_kind is not None:
            fail("a successful attempt has no error_kind")
    elif attempt.error_kind is None or attempt.error_kind not in allowed_error_kinds(attempt.status):
        fail("a failed attempt needs an error_kind allowed for its status")
    if not attempt.completed:
        if attempt.status is not SourceStatus.NETWORK_ERROR or attempt.error_kind is not SourceErrorKind.SOURCE_DEADLINE:
            fail("an incomplete attempt is NETWORK_ERROR / SOURCE_DEADLINE")
    if attempt.sequence == 1 and not is_zero(attempt.backoff_before_seconds):
        fail("the first attempt has no backoff before it")


def check_trace(trace: object, result: object) -> None:
    """M-19 (``result`` is the aligned, already validated ``SourceResult``)."""
    if type(trace) is not SourceExecutionTrace:
        fail("source_execution_traces must hold exact SourceExecutionTrace values")
    if not is_non_empty_str(trace.source_id):
        fail("SourceExecutionTrace.source_id must be a non-empty exact str")
    final = trace.final_result
    if type(final) is not SourceResult:
        fail("SourceExecutionTrace.final_result must be an exact SourceResult")
    if final is not result:
        check_source_result(final)
    require_int(trace.max_attempts, 1, "SourceExecutionTrace.max_attempts must be an exact int >= 1")
    require_bool(trace.deadline_exceeded, "SourceExecutionTrace.deadline_exceeded must be an exact bool")
    during = trace.deadline_during
    if during is not None and (type(during) is not str or (during != "attempt" and during != "backoff")):
        fail("SourceExecutionTrace.deadline_during must be None, 'attempt' or 'backoff'")
    require_bounded_tuple(trace.attempts, MAX_ATTEMPTS_PER_SOURCE, "SourceExecutionTrace.attempts must be a tuple",
                          "SourceExecutionTrace.attempts exceed MAX_ATTEMPTS_PER_SOURCE")
    for attempt in trace.attempts:
        check_attempt(attempt)
    if not same_str(final.source_id, trace.source_id):
        fail("a trace's final_result must be its own source's result")
    attempts = trace.attempts
    count = len(attempts)
    circuit_open = final.error_kind is SourceErrorKind.CIRCUIT_OPEN
    if circuit_open != (count == 0):
        fail("a trace has no attempts iff its final result is CIRCUIT_OPEN")
    if circuit_open:
        if trace.deadline_exceeded or during is not None:
            fail("an open-breaker trace cannot have exceeded a deadline")
        return
    expected = 1
    for attempt in attempts:
        if attempt.sequence != expected:
            fail("attempt sequences must be 1..n in order")
        expected += 1
    if count > trace.max_attempts:
        fail("a trace has more attempts than max_attempts")
    for attempt in attempts[:-1]:
        if not attempt.completed or attempt.status is SourceStatus.SUCCESS:
            fail("only the last attempt may be incomplete, and none before it may succeed")
        if attempt.error_kind not in RETRY_ELIGIBLE_KINDS:
            fail("an attempt may be followed by another only after a retry-eligible failure")
    last = attempts[-1]
    if trace.deadline_exceeded:
        if during is None:
            fail("an exceeded deadline names where it ran out")
        if final.status is not SourceStatus.NETWORK_ERROR or final.error_kind is not SourceErrorKind.SOURCE_DEADLINE:
            fail("an expired deadline ends in NETWORK_ERROR / SOURCE_DEADLINE")
        if during == "attempt":
            if last.completed:
                fail("a deadline during an attempt leaves the last attempt incomplete")
        else:
            if not last.completed or last.error_kind not in RETRY_ELIGIBLE_KINDS or count >= trace.max_attempts:
                fail("a deadline during backoff follows a completed retry-eligible attempt below max_attempts")
    else:
        if during is not None:
            fail("deadline_during requires an exceeded deadline")
        if not last.completed:
            fail("an attempt is incomplete only when the deadline was exceeded")
        if final.status is not last.status or final.error_kind is not last.error_kind:
            fail("a trace's final_result must match its last attempt")


def check_conflict(conflict: object) -> None:
    """M-21."""
    if type(conflict) is not FieldConflict:
        fail("conflicts must hold exact FieldConflict values")
    if type(conflict.field) is not str or conflict.field not in CONFLICT_FIELDS:
        fail("FieldConflict.field must be a member of CONFLICT_FIELDS")
    if conflict.field == "external_ids":
        if type(conflict.key) is not str or len(conflict.key.strip()) < 1:
            fail("an external_ids conflict needs a non-blank key")
    elif conflict.key is not None:
        fail("a scalar conflict has no key")
    if not is_non_empty_str(conflict.selected_source_id):
        fail("FieldConflict.selected_source_id must be a non-empty exact str")
    selected = conflict.selected_value
    if type(selected) is not str and type(selected) is not int:
        fail("FieldConflict.selected_value must be an exact str or int")
    require_bounded_tuple(conflict.alternatives, MAX_SOURCES_PER_ITEM, "FieldConflict.alternatives must be a tuple",
                          "FieldConflict.alternatives exceed MAX_SOURCES_PER_ITEM")
    if len(conflict.alternatives) < 1:
        fail("FieldConflict.alternatives must not be empty")
    for entry in conflict.alternatives:
        if type(entry) is not tuple or len(entry) != 2:
            fail("FieldConflict.alternatives must be (source_id, value) pairs")
        if not is_non_empty_str(entry[0]) or (type(entry[1]) is not str and type(entry[1]) is not int):
            fail("FieldConflict.alternatives must be (source_id, value) pairs of exact str / int")
    seen: set[str] = set()
    for entry in conflict.alternatives:
        identifier = entry[0]
        if identifier == conflict.selected_source_id or identifier in seen:
            fail("FieldConflict alternatives are unique and never the selected source")
        seen.add(identifier)
        if type(entry[1]) is type(selected) and entry[1] == selected:
            fail("an alternative equal to the selected value is not a conflict")


def scan_field_sources(metadata: object, contributing: tuple) -> tuple:
    """M-18 / contract 9.2 item 9: BOUNDED ONE-PASS KEY SCAN -> EXACT KEY VALIDATION -> FIXED KNOWN-KEY LOOKUP.

    Step 1-2: exact types. Step 3: one pass over the stored keys -- count, stop at ``MAX_PROVENANCE_KEYS + 1``,
    and the **only** operation on a key is ``type(key) is str`` (no ``in`` / index / equality / hash on the proxy
    until every key has passed). Step 4: fixed known-key lookup in ``PROVENANCE_FIELD_ORDER`` order. Step 5: value
    validation (Phase V before Phase R). Returns ``((field, source_ids), ...)`` in ``PROVENANCE_FIELD_ORDER``.
    """
    if type(metadata) is not NormalizedMetadata:
        fail("AggregationResult.metadata must be an exact NormalizedMetadata")
    proxy = metadata.field_sources
    if type(proxy) is not types.MappingProxyType:
        fail("NormalizedMetadata.field_sources must be an exact mappingproxy")
    seen_keys = 0
    for key in proxy:
        seen_keys += 1
        if seen_keys > MAX_PROVENANCE_KEYS:
            over_limit("NormalizedMetadata.field_sources exceeds MAX_PROVENANCE_KEYS")
        if type(key) is not str:
            fail("NormalizedMetadata.field_sources keys must be exact str")
    found = []
    for name in PROVENANCE_FIELD_ORDER:
        if name in proxy:
            value = proxy[name]
            if type(value) is not tuple:
                fail("a field_sources value must be an exact tuple")
            if len(value) < 1 or len(value) > MAX_SOURCES_PER_ITEM:
                fail("a field_sources value must hold between 1 and MAX_SOURCES_PER_ITEM source ids")
            for source_id in value:
                if type(source_id) is not str:
                    fail("a field_sources value must hold exact str source ids")
            if len(set(value)) != len(value):
                fail("a field_sources value must hold unique source ids")
            for source_id in value:
                if source_id not in contributing:
                    fail("a field_sources source id must be a contributing source")
            found.append((name, value))
    return tuple(found)


def check_aggregation(aggregation: object) -> tuple:
    """M-16 (Phase V, then Phase R, then M-18). Returns the validated provenance."""
    if type(aggregation) is not AggregationResult:
        fail("aggregation_result must be an exact AggregationResult")
    if type(aggregation.number) is not str or not is_valid_fc2_number(aggregation.number):
        fail("AggregationResult.number must be a canonical FC2 number")
    require_enum(aggregation.status, AggregateStatus, "AggregationResult.status must be an AggregateStatus")
    check_number(aggregation.elapsed_ms, "AggregationResult.elapsed_ms must be a finite number >= 0")
    results = aggregation.source_results
    require_bounded_tuple(results, MAX_SOURCES_PER_ITEM, "AggregationResult.source_results must be a tuple",
                          "AggregationResult.source_results exceed MAX_SOURCES_PER_ITEM")
    if len(results) < 1:
        fail("AggregationResult.source_results must not be empty")
    contributing = aggregation.contributing_source_ids
    require_bounded_tuple(contributing, MAX_SOURCES_PER_ITEM, "AggregationResult.contributing_source_ids must be a tuple",
                          "AggregationResult.contributing_source_ids exceed MAX_SOURCES_PER_ITEM")
    disabled = aggregation.disabled_source_ids
    require_bounded_tuple(disabled, MAX_SOURCES_PER_ITEM, "AggregationResult.disabled_source_ids must be a tuple",
                          "AggregationResult.disabled_source_ids exceed MAX_SOURCES_PER_ITEM")
    conflicts = aggregation.conflicts
    require_bounded_tuple(conflicts, MAX_CONFLICTS_PER_ITEM, "AggregationResult.conflicts must be a tuple",
                          "AggregationResult.conflicts exceed MAX_CONFLICTS_PER_ITEM")
    traces = aggregation.source_execution_traces
    require_bounded_tuple(traces, MAX_SOURCES_PER_ITEM, "AggregationResult.source_execution_traces must be a tuple",
                          "AggregationResult.source_execution_traces exceed MAX_SOURCES_PER_ITEM")
    # ----- Phase V: every element of every container is exact-type validated before any membership / equality
    for result in results:
        check_source_result(result)
    for identifier in contributing:
        if type(identifier) is not str:
            fail("AggregationResult.contributing_source_ids must hold exact str")
    for identifier in disabled:
        if type(identifier) is not str or len(identifier.strip()) < 1:
            fail("AggregationResult.disabled_source_ids must hold non-blank exact str")
    for conflict in conflicts:
        check_conflict(conflict)
    if len(traces) != 0 and len(traces) != len(results):
        fail("source_execution_traces must be empty or match source_results one-to-one")
    for position in range(len(traces)):
        check_trace(traces[position], results[position])
    # ----- Phase R: relations
    ids = tuple(result.source_id for result in results)
    if len(set(ids)) != len(ids):
        fail("source_results contain a duplicate source_id")
    if len(set(disabled)) != len(disabled):
        fail("disabled_source_ids contain a duplicate")
    for identifier in disabled:
        if identifier in ids:
            fail("a disabled source also has a result")
    successful = tuple(result.source_id for result in results if result.status is SourceStatus.SUCCESS)
    status = aggregation.status
    if status is AggregateStatus.FAILED:
        if len(contributing) != 0:
            fail("a FAILED aggregate has no contributing sources")
    elif contributing != successful:
        fail("contributing_source_ids must equal the SUCCESS source ids")
    for position in range(len(traces)):
        trace, result = traces[position], results[position]
        if trace.source_id != result.source_id:
            fail("source_execution_traces must follow source_results in order")
        if trace.final_result.status is not result.status or trace.final_result.error_kind is not result.error_kind:
            fail("a trace's final_result must match its source result")
    for conflict in conflicts:
        if conflict.selected_source_id not in contributing:
            fail("a conflict names a source that did not contribute")
        for entry in conflict.alternatives:
            if entry[0] not in contributing:
                fail("a conflict names a source that did not contribute")
    if status is AggregateStatus.FAILED:
        if aggregation.metadata is not None:
            fail("a FAILED aggregate carries no metadata")
        if len(successful) != 0:
            fail("a FAILED aggregate contradicts a SUCCESS source result")
        return ()
    if type(aggregation.metadata) is not NormalizedMetadata or not metadata_meets_minimum(aggregation.metadata):
        fail("a SUCCESS / PARTIAL aggregate needs minimum-success metadata")
    if not same_str(aggregation.metadata.number, aggregation.number):
        fail("the aggregated metadata number must equal the aggregate number")
    if len(successful) == 0:
        fail("a SUCCESS / PARTIAL aggregate needs a SUCCESS source result")
    operational = False
    for result in results:
        if result.status in OPERATIONAL_FAILURE_STATUSES:
            operational = True
    if status is AggregateStatus.SUCCESS and operational:
        fail("a SUCCESS aggregate has no operational source failure")
    if status is AggregateStatus.PARTIAL and not operational:
        fail("a PARTIAL aggregate has an operational source failure")
    return scan_field_sources(aggregation.metadata, contributing)


def check_batch_item_result(item: object) -> tuple:
    """M-15 (+ M-16 .. M-21 for a present ``AggregationResult``). Returns the validated provenance."""
    if type(item) is not BatchItemResult:
        fail("metadata must hold exact BatchItemResult values")
    require_int(item.index, 0, "BatchItemResult.index must be an exact int >= 0")
    if type(item.number) is not str or not is_valid_fc2_number(item.number):
        fail("BatchItemResult.number must be a canonical FC2 number")
    require_enum(item.status, BatchItemStatus, "BatchItemResult.status must be a BatchItemStatus")
    require_int(item.generation, 0, "BatchItemResult.generation must be an exact int >= 0")
    check_number(item.elapsed_ms, "BatchItemResult.elapsed_ms must be a finite number >= 0")
    require_opt_enum(item.error_kind, BatchItemErrorKind, "BatchItemResult.error_kind must be a BatchItemErrorKind or None")
    if item.error_type is not None and (type(item.error_type) is not str or len(item.error_type) < 1
                                        or len(item.error_type) > 256):
        fail("BatchItemResult.error_type must be None or a non-empty exact str of at most 256 characters")
    if item.aggregation_result is not None:
        provenance = check_aggregation(item.aggregation_result)
        if item.error_kind is not None or item.error_type is not None:
            fail("an item with an aggregation_result has no error_kind / error_type")
        aggregation = item.aggregation_result
        if not same_str(aggregation.number, item.number):
            fail("aggregation_result.number must equal the item number")
        if aggregation.status is AggregateStatus.SUCCESS:
            expected = BatchItemStatus.SUCCESS
        elif aggregation.status is AggregateStatus.PARTIAL:
            expected = BatchItemStatus.PARTIAL
        else:
            expected = BatchItemStatus.FAILED
        if item.status is not expected:
            fail("the item status must map the aggregation status")
        return provenance
    if item.status is not BatchItemStatus.FAILED:
        fail("an item without an aggregation_result is FAILED")
    if item.error_kind is None or item.error_type is None:
        fail("an item without an aggregation_result needs error_kind and error_type")
    return ()


def check_metadata_batch(batch: object, lineage: object) -> tuple:
    """M-14. Returns ``(MetadataBatchCounts, provenances)`` -- one validated provenance per batch item."""
    if type(batch) is not BatchResult:
        fail("metadata_batch must be an exact BatchResult")
    items = batch.items
    require_bounded_tuple(items, MAX_DIAGNOSTIC_ITEMS, "BatchResult.items must be an exact tuple",
                          "BatchResult.items exceed MAX_DIAGNOSTIC_ITEMS")
    require_int(batch.generation, 0, "BatchResult.generation must be an exact int >= 0")
    check_lineage(batch.lineage)
    if batch.lineage.token != lineage.token:
        fail("metadata_batch.lineage must equal the lineage")
    provenances = []
    success = 0
    partial = 0
    failed = 0
    position = 0
    for item in items:
        provenances.append(check_batch_item_result(item))
        if item.index != position:
            fail("BatchResult items must be in input order with index 0..n-1")
        if item.generation > batch.generation:
            fail("no BatchResult item is newer than the batch generation")
        if item.status is BatchItemStatus.SUCCESS:
            success += 1
        elif item.status is BatchItemStatus.PARTIAL:
            partial += 1
        else:
            failed += 1
        position += 1
    if success + partial + failed != len(items):
        fail("BatchResult counts must add up")
    counts = MetadataBatchCounts(generation=batch.generation, total=len(items), success=success, partial=partial,
                                 failed=failed)
    return counts, tuple(provenances)


# --------------------------------------------------------------------------- batch scalars (M-01 / M-02)


def check_scope(scope: object) -> tuple:
    """``retry_scope``: an exact frozenset, *iterated first* (D-02) -- membership only afterwards (D-12)."""
    if type(scope) is not frozenset:
        fail("retry_scope must be None or an exact frozenset")
    for kind in scope:
        if type(kind) is not RetryKind or kind is RetryKind.NONE:
            fail("retry_scope must hold RetryKind members other than NONE")
    return tuple(kind for kind in RetryKind if kind in scope)


def check_batch_scalars(model: object, is_execution: bool) -> None:
    """M-01 / M-02 scalars (shape relations are checked by the callers)."""
    if is_execution:
        if not is_hex(model.result_id, HEX32):
            fail("BatchExecutionResult.result_id must be 32 lowercase hex characters")
        if model.preview_id is not None and not is_hex(model.preview_id, HEX32):
            fail("BatchExecutionResult.preview_id must be None or 32 lowercase hex characters")
    elif not is_hex(model.preview_id, HEX32):
        fail("BatchPreview.preview_id must be 32 lowercase hex characters")
    check_lineage(model.lineage)
    require_int(model.generation, 0, "generation must be an exact int >= 0")
    if model.base_result_id is not None and not is_hex(model.base_result_id, HEX32):
        fail("base_result_id must be None or 32 lowercase hex characters")
    if not is_non_empty_str(model.library_root) or not os.path.isabs(model.library_root):
        fail("library_root must be an absolute non-empty exact str")
    if type(model.output_policy) is not OutputPolicy or type(model.image_policy) is not ImageAcquisitionPolicy:
        fail("output_policy / image_policy must be exact OutputPolicy / ImageAcquisitionPolicy")
    if type(model.batch_size) is not int or model.batch_size < 0 or model.batch_size > MAX_DIAGNOSTIC_ITEMS:
        fail("batch_size must be an exact int in 0..MAX_DIAGNOSTIC_ITEMS")
    if (type(model.retention_budget_bytes) is not int or model.retention_budget_bytes < 1
            or model.retention_budget_bytes > MAX_RETAINED_ARTIFACT_BYTES_LIMIT):
        fail("retention_budget_bytes must be an exact int in 1..MAX_RETAINED_ARTIFACT_BYTES_LIMIT")
    budget = model.retry_budget_bytes
    if budget is not None and (type(budget) is not int or budget < 0 or budget > model.retention_budget_bytes):
        fail("retry_budget_bytes must be None or an exact int in 0..retention_budget_bytes")


def check_indices(indices: tuple, batch_size: int, complete: bool) -> None:
    if complete:
        if len(indices) != batch_size:
            fail("items must cover indices 0..batch_size-1")
        position = 0
        for index in indices:
            if index != position:
                fail("items must cover indices 0..batch_size-1 in order")
            position += 1
        return
    previous = -1
    for index in indices:
        if index <= previous:
            fail("item indices must strictly increase")
        previous = index
    if len(indices) != 0 and indices[-1] >= batch_size:
        fail("every item index must be < batch_size")


def check_conflict_graph(items: tuple) -> None:
    """Contract 9.6.1: ``conflict_with`` names peers of the same collection, symmetrically (Phase V done)."""
    by_index = {}
    for item in items:
        by_index[item.index] = item
    for item in items:
        for peer_index in item.conflict_with:
            if peer_index not in by_index:
                fail("conflict_with must name peers of the same collection")
            if item.index not in by_index[peer_index].conflict_with:
                fail("conflict_with must be symmetric")


# --------------------------------------------------------------------------- item cores (M-05 / M-06 shared)


def check_item_core(item: object) -> None:
    """Fields and relations common to ``ItemPreview`` / ``ItemExecution`` (contract 9.6.3 / 9.6.4)."""
    require_int(item.index, 0, "item.index must be an exact int >= 0")
    require_int(item.generation, 0, "item.generation must be an exact int >= 0")
    check_media_item(item.media_item)
    number = item.canonical_number
    if number is not None and (type(number) is not str or not is_valid_fc2_number(number)):
        fail("canonical_number must be None or a canonical FC2 number")
    if item.issue is not None:
        check_issue(item.issue)
    unrecognized = item.issue is not None and item.issue.reason is IssueReason.NUMBER_NOT_RECOGNIZED
    if (number is None) != unrecognized:
        fail("canonical_number is None iff the issue reason is NUMBER_NOT_RECOGNIZED")
    position = item.metadata_position
    if position is not None and (type(position) is not int or position < 0):
        fail("metadata_position must be None or an exact int >= 0")
    if (position is None) != (item.metadata is None):
        fail("metadata_position is None iff metadata is None")
    if item.plan is not None:
        check_plan(item.plan)
        if not same_str(item.plan.canonical_number, number):
            fail("plan.canonical_number must equal canonical_number")
        media = item.media_item
        plan = item.plan
        if (plan.source_path != media.source_path or plan.source_relative_path != media.relative_path
                or plan.source_extension != media.extension or plan.source_index != media.index
                or plan.source_size != media.size):
            fail("plan source fields must equal the media item")
    require_tuple_of(item.image_failures, ImageCandidateFailure, "image_failures must be a tuple of ImageCandidateFailure")
    for failure in item.image_failures:
        check_image_failure(failure)
    check_conflict_with(item.conflict_with, item.index)


def check_item_metadata_relation(item: object) -> None:
    """``metadata.number`` / ``metadata.index`` relations (needs the metadata already validated)."""
    if item.metadata is not None:
        if not same_str(item.metadata.number, item.canonical_number):
            fail("metadata.number must equal canonical_number")
        if item.metadata.index != item.metadata_position:
            fail("metadata.index must equal metadata_position")


def retry_origin_problem(item: ItemPreview) -> bool:
    """True iff ``retry_origin`` / ``generation`` violate contract 9.6.3."""
    origin = item.retry_origin
    if origin is None:
        return item.generation != 0
    return type(origin) is not RetryKind or origin is RetryKind.NONE or item.generation == 0


# --------------------------------------------------------------------------- the PREVIEW path


def check_preview_item(item: object, batch_items: tuple, provenances: tuple) -> tuple:
    """M-05 + 9.6.3. Returns the provenance of the item's metadata (``()`` if none)."""
    if type(item) is not ItemPreview:
        fail("BatchPreview.items must hold exact ItemPreview values")
    require_enum(item.state, PreviewState, "ItemPreview.state must be a PreviewState")
    check_item_core(item)
    if item.retry_origin is not None and type(item.retry_origin) is not RetryKind:
        fail("ItemPreview.retry_origin must be None or a RetryKind")
    provenance = ()
    if item.metadata is not None:
        position = item.metadata_position
        if position >= len(batch_items) or item.metadata is not batch_items[position]:
            fail("item.metadata must be metadata_batch.items[item.metadata_position]")
        provenance = provenances[position]
        check_item_metadata_relation(item)
    if item.preflight is not None:
        if item.plan is None:
            fail("a preflight needs the item's plan")
        check_preflight(item.preflight, item.plan)
    issue = item.issue
    if issue is not None and issue.stage is OrchestrationStage.EXECUTION:
        fail("an ItemPreview issue is never an EXECUTION-stage issue")
    executable = item.preflight is not None and item.preflight.ready is True and len(item.conflict_with) == 0
    if (item.state is PreviewState.READY) != (issue is None) or (issue is None) != executable:
        fail("ItemPreview: READY iff no issue iff a ready preflight without batch conflicts")
    if issue is not None:
        reason = issue.reason
        if (item.state is PreviewState.BLOCKED) != (reason in BLOCKED_REASONS):
            fail("ItemPreview: BLOCKED iff the issue is PREFLIGHT_BLOCKED or a batch duplicate")
        if reason is IssueReason.PREFLIGHT_BLOCKED:
            if (item.preflight is None or item.preflight.ready is not False or len(item.preflight.blockers) == 0
                    or len(item.conflict_with) != 0):
                fail("ItemPreview: PREFLIGHT_BLOCKED needs a not-ready preflight with blockers and no conflicts")
        elif reason in DUPLICATE_REASONS:
            if len(item.conflict_with) == 0:
                fail("ItemPreview: a batch duplicate names its conflicting peers")
        elif item.preflight is not None or len(item.conflict_with) != 0:
            fail("ItemPreview: an UNPREPARED item has no preflight and no conflicts")
    if retry_origin_problem(item):
        fail("ItemPreview.retry_origin is None iff generation == 0")
    return provenance


def retained_preview_bytes(items: tuple) -> int:
    total = 0
    for item in items:
        if item.preflight is not None:
            total += payload_bytes(item.preflight.artifacts)
    return total


def build_preview_snapshot(preview: object, path_policy: object, timing_policy: object) -> BatchSnapshot:
    """Contract section 24.2 steps 3-7 for a ``BatchPreview``."""
    # step 3
    items = preview.items
    require_bounded_tuple(items, MAX_DIAGNOSTIC_ITEMS, "BatchPreview.items must be an exact tuple",
                          "BatchPreview.items exceed MAX_DIAGNOSTIC_ITEMS")
    # step 4 (Phase V of every object)
    check_batch_scalars(preview, False)
    scope = None
    if preview.retry_scope is not None:
        scope = check_scope(preview.retry_scope)
    counts, provenances = check_metadata_batch(preview.metadata_batch, preview.lineage)
    batch_items = preview.metadata_batch.items
    item_provenances = []
    for item in items:
        item_provenances.append(check_preview_item(item, batch_items, provenances))
    # step 5 (Phase R)
    is_main = preview.base_result_id is None
    if (preview.retry_scope is None) != is_main or (preview.generation == 0) != is_main:
        fail("base_result_id is None iff retry_scope is None iff generation == 0")
    if (preview.retry_budget_bytes is None) != is_main:
        fail("retry_budget_bytes is None iff this is the main preview")
    check_indices(tuple(item.index for item in items), preview.batch_size, is_main)
    for item in items:
        if item.generation != preview.generation:
            fail("every item carries the preview generation")
        if not is_main and item.retry_origin not in preview.retry_scope:
            fail("a retry item's retry_origin must be in retry_scope")
        if item.plan is not None and item.plan.library_root != preview.library_root:
            fail("plan.library_root must equal the batch library_root")
    check_conflict_graph(items)
    limit = preview.retention_budget_bytes if is_main else preview.retry_budget_bytes
    if retained_preview_bytes(items) > limit:
        fail("retained artifact bytes exceed the retention / retry budget")
    # step 6 (safe output + conversion)
    parts = []
    for position in range(len(items)):
        parts.append(output_parts(items[position], item_provenances[position], path_policy, timing_policy,
                                  items[position].preflight, None))
    # step 7 (approved properties, only now)
    snapshots = []
    for position in range(len(items)):
        item = items[position]
        warnings = item.warnings
        check_warnings_field(warnings)
        snapshots.append(assemble_item(item, parts[position], warnings, None, None, None))
    summary = preview.summary
    problem = preview_summary_problem(summary)
    if problem is not None or summary.total != len(items):
        fail("BatchPreview.summary must be a valid PreviewSummary with total == len(items)")
    return BatchSnapshot(
        kind=DiagnosticsKind.PREVIEW, shape=ResultShape.MAIN if is_main else ResultShape.RETRY,
        generation=preview.generation, batch_size=preview.batch_size, retry_scope=scope, metadata_counts=counts,
        preview_summary=summary, execution_summary=None, outcome=None, items=tuple(snapshots))


# --------------------------------------------------------------------------- the EXECUTION path


def local_shape(result: object) -> ResultShape:
    """Contract 9.6.2: exactly one of MAIN / RETRY / MERGED holds, else ``DiagnosticsIntegrityError``."""
    no_retry = result.base_result_id is None and result.retry_scope is None and result.retry_budget_bytes is None
    if result.generation == 0 and no_retry and result.preview_id is not None:
        return ResultShape.MAIN
    if (result.generation >= 1 and result.base_result_id is not None and result.retry_scope is not None
            and result.preview_id is not None and result.retry_budget_bytes is not None):
        return ResultShape.RETRY
    if result.generation >= 1 and no_retry and result.preview_id is None:
        return ResultShape.MERGED
    fail("BatchExecutionResult is neither a main, a retry-round nor a merged result")
    return ResultShape.MAIN


def expected_retry_kind(item: ItemExecution) -> RetryKind:
    """Contract 9.6.4: the P4-C8 section 25.1 pure function, derived from already validated public fields."""
    disposition = item.disposition
    if disposition is ExecutionDisposition.EXECUTED:
        status = item.execution.status
        if status is ExecutionStatus.SUCCESS:
            return RetryKind.NONE
        if status is ExecutionStatus.PARTIAL:
            return RetryKind.RESUME
        return RetryKind.FRESH_REEXECUTE
    if disposition is ExecutionDisposition.NOT_READY:
        if item.issue.stage is OrchestrationStage.METADATA:
            return RetryKind.METADATA_REFETCH
        if item.issue.reason is IssueReason.PREFLIGHT_BLOCKED:
            return RetryKind.PREFLIGHT_RECHECK
        return RetryKind.NONE
    if disposition is ExecutionDisposition.NOT_SELECTED or disposition is ExecutionDisposition.CANCELLED:
        return RetryKind.DEFERRED
    return RetryKind.NONE


def check_execution_item(item: object, batch_items: tuple, provenances: tuple) -> tuple:
    """M-06 + 9.6.4 (everything before ``retry_kind`` is read). Returns ``(provenance, expected_kind)``."""
    if type(item) is not ItemExecution:
        fail("BatchExecutionResult.items must hold exact ItemExecution values")
    require_enum(item.preview_state, PreviewState, "ItemExecution.preview_state must be a PreviewState")
    require_enum(item.disposition, ExecutionDisposition, "ItemExecution.disposition must be an ExecutionDisposition")
    check_item_core(item)
    check_warnings_field(item.warnings)
    provenance = ()
    if item.metadata is not None:
        position = item.metadata_position
        if position < len(batch_items) and item.metadata is batch_items[position]:
            provenance = provenances[position]
        else:
            provenance = check_batch_item_result(item.metadata)
        check_item_metadata_relation(item)
    if item.execution is not None:
        check_execution_result(item.execution)
    if (item.execution is None) == (item.disposition is ExecutionDisposition.EXECUTED):
        fail("ItemExecution.execution is present iff the disposition is EXECUTED")
    disposition, state, execution, issue = item.disposition, item.preview_state, item.execution, item.issue
    if disposition is ExecutionDisposition.NOT_READY:
        if state is PreviewState.READY or issue is None or issue.stage is OrchestrationStage.EXECUTION:
            fail("ItemExecution: NOT_READY carries a BLOCKED / UNPREPARED preview issue")
        if (state is PreviewState.BLOCKED) != (issue.reason in BLOCKED_REASONS):
            fail("ItemExecution: preview_state BLOCKED iff the issue is a blocking reason")
    else:
        if state is not PreviewState.READY:
            fail("ItemExecution: only READY items are executed / selected / cancelled / rejected / aborted")
        if disposition is ExecutionDisposition.EXECUTED:
            if execution.status is ExecutionStatus.SUCCESS:
                if issue is not None:
                    fail("ItemExecution: an EXECUTED SUCCESS item has no issue")
            else:
                wanted = (IssueReason.EXECUTION_PARTIAL if execution.status is ExecutionStatus.PARTIAL
                          else IssueReason.EXECUTION_FAILED)
                if issue is None or issue.reason is not wanted:
                    fail("ItemExecution: an EXECUTED FAILED / PARTIAL item has the matching EXECUTION issue")
                if execution.failure is None or issue.detail is not execution.failure.kind:
                    fail("ItemExecution: issue.detail must equal execution.failure.kind")
        elif disposition is ExecutionDisposition.NOT_SELECTED or disposition is ExecutionDisposition.CANCELLED:
            if issue is not None:
                fail("ItemExecution: a NOT_SELECTED / CANCELLED item has no issue")
        else:
            wanted = (IssueReason.EXECUTION_REJECTED if disposition is ExecutionDisposition.REJECTED
                      else IssueReason.EXECUTION_ABORTED)
            if issue is None or issue.reason is not wanted:
                fail("ItemExecution: the issue does not match the disposition")
    duplicate = issue is not None and issue.reason in DUPLICATE_REASONS
    if duplicate != (len(item.conflict_with) != 0):
        fail("ItemExecution.conflict_with is non-empty iff the issue is a batch duplicate")
    if state is PreviewState.READY and item.plan is None:
        fail("ItemExecution: a READY item always has its plan")
    check_item_warning_relations(item)
    expected = expected_retry_kind(item)
    material = item.retry_material
    if (material is not None) != (expected in _MATERIAL_KINDS):
        fail("ItemExecution.retry_material is present iff retry_kind needs retained material")
    if material is not None:
        check_retry_material(material)
        if material.plan is not item.plan:
            fail("ItemExecution.retry_material.plan must be the item's plan (same object)")
        if expected is RetryKind.RESUME:
            if (execution is None or execution.checkpoint is None or material.checkpoint is None
                    or material.checkpoint is not execution.checkpoint):
                fail("ItemExecution: RESUME material carries execution.checkpoint (same object)")
        elif expected is RetryKind.FRESH_REEXECUTE and material.checkpoint is not None:
            fail("ItemExecution: FRESH_REEXECUTE material carries no checkpoint")
    return provenance, expected


def check_item_warning_relations(item: ItemExecution) -> None:
    """Contract 9.6.4 warnings relations."""
    warnings = item.warnings
    partial = item.metadata is not None and item.metadata.status is BatchItemStatus.PARTIAL
    leftovers = item.execution is not None and len(item.execution.leftover_temporaries) != 0
    if (ItemWarning.METADATA_PARTIAL in warnings) != partial:
        fail("ItemExecution.warnings contradict the metadata status")
    if (ItemWarning.IMAGE_CANDIDATE_FAILURES in warnings) != (len(item.image_failures) != 0):
        fail("ItemExecution.warnings contradict the image failures")
    if (ItemWarning.LEFTOVER_TEMPORARIES in warnings) != leftovers:
        fail("ItemExecution.warnings contradict the leftover temporaries")
    if item.preview_state is PreviewState.UNPREPARED or item.plan is None:
        for absent in (ItemWarning.POSTER_ABSENT, ItemWarning.FANART_ABSENT, ItemWarning.THUMB_ABSENT,
                       ItemWarning.NO_EXTRAFANART):
            if absent in warnings:
                fail("an item previewed without a preflight has no image-absence warning")


def retained_retry_bytes(items: tuple) -> int:
    total = 0
    for item in items:
        if item.retry_material is not None:
            total += payload_bytes(item.retry_material.artifacts)
    return total


def build_execution_snapshot(result: object, path_policy: object, timing_policy: object) -> BatchSnapshot:
    """Contract section 24.2 steps 3-7 for a ``BatchExecutionResult``."""
    items = result.items
    require_bounded_tuple(items, MAX_DIAGNOSTIC_ITEMS, "BatchExecutionResult.items must be an exact tuple",
                          "BatchExecutionResult.items exceed MAX_DIAGNOSTIC_ITEMS")
    check_batch_scalars(result, True)
    scope = None
    if result.retry_scope is not None:
        scope = check_scope(result.retry_scope)
    counts, provenances = check_metadata_batch(result.metadata_batch, result.lineage)
    batch_items = result.metadata_batch.items
    checked = []
    for item in items:
        checked.append(check_execution_item(item, batch_items, provenances))
    shape = local_shape(result)
    complete = shape is not ResultShape.RETRY
    check_indices(tuple(item.index for item in items), result.batch_size, complete)
    for item in items:
        if item.generation > result.generation or (shape is not ResultShape.MERGED
                                                   and item.generation != result.generation):
            fail("item generations do not match the result shape")
        if item.plan is not None and item.plan.library_root != result.library_root:
            fail("plan.library_root must equal the batch library_root")
    check_conflict_graph(items)
    limit = result.retention_budget_bytes if complete else result.retry_budget_bytes
    if retained_retry_bytes(items) > limit:
        fail("retained retry payload exceeds the retention / retry budget")
    parts = []
    for position in range(len(items)):
        item = items[position]
        parts.append(output_parts(item, checked[position][0], path_policy, timing_policy, None, item.execution))
    # step 7: approved properties -- per item ``retry_kind`` first, then ``summary``, then ``outcome``
    snapshots = []
    for position in range(len(items)):
        item = items[position]
        kind = item.retry_kind
        if kind is not checked[position][1]:
            fail("ItemExecution.retry_kind contradicts the locally derived kind")
        snapshots.append(assemble_item(item, parts[position], item.warnings, item.disposition, kind,
                                       item.retry_material is not None))
    summary = result.summary
    problem = execution_summary_problem(summary)
    if problem is not None or summary.total != len(items):
        fail("BatchExecutionResult.summary must be a valid ExecutionSummary with total == len(items)")
    outcome = result.outcome
    if type(outcome) is not BatchOutcome:
        fail("BatchExecutionResult.outcome must be a BatchOutcome")
    return BatchSnapshot(
        kind=DiagnosticsKind.EXECUTION, shape=shape, generation=result.generation, batch_size=result.batch_size,
        retry_scope=scope, metadata_counts=counts, preview_summary=None, execution_summary=summary, outcome=outcome,
        items=tuple(snapshots))


# --------------------------------------------------------------------------- step 6: safe output + policies


def basename_of(path_text: str) -> str:
    """Contract 18.1: pure string processing of an exact ``str`` (no filesystem access)."""
    name = os.path.basename(path_text)
    if not is_safe_basename(name) or os.sep in name or (os.altsep is not None and os.altsep in name):
        unsafe("a path-derived text is not a safe basename")
    return name


def snapshot_metadata(item: BatchItemResult, provenance: tuple, timing_policy: TimingPolicy) -> MetadataSnapshot:
    """The metadata part of an item: id safety checks, timing conversion (INCLUDE only), traces."""
    include = timing_policy is TimingPolicy.INCLUDE
    elapsed = publish_elapsed_ms(item.elapsed_ms) if include else None
    aggregation = item.aggregation_result
    if aggregation is None:
        return MetadataSnapshot(status=item.status, generation=item.generation, error_kind=item.error_kind,
                                aggregate_status=None, traces_available=False, sources=(), disabled_source_ids=(),
                                provenance=(), conflicts=(), elapsed_ms=elapsed)
    for result in aggregation.source_results:
        if not is_safe_id(result.source_id):
            unsafe("a source id is not a safe source id")
    for identifier in aggregation.disabled_source_ids:
        if not is_safe_id(identifier):
            unsafe("a source id is not a safe source id")
    traces = aggregation.source_execution_traces
    sources = []
    for position in range(len(aggregation.source_results)):
        result = aggregation.source_results[position]
        trace = None
        if len(traces) != 0:
            attempts = []
            for attempt in traces[position].attempts:
                if include:
                    attempts.append(SourceAttemptDiagnostics(
                        sequence=attempt.sequence, status=attempt.status, error_kind=attempt.error_kind,
                        completed=attempt.completed, elapsed_ms=publish_elapsed_ms(attempt.elapsed_ms),
                        backoff_before_ms=publish_backoff_ms(attempt.backoff_before_seconds)))
                else:
                    attempts.append(SourceAttemptDiagnostics(
                        sequence=attempt.sequence, status=attempt.status, error_kind=attempt.error_kind,
                        completed=attempt.completed, elapsed_ms=None, backoff_before_ms=None))
            trace_source = traces[position]
            trace = TraceSnapshot(max_attempts=trace_source.max_attempts,
                                  deadline_exceeded=trace_source.deadline_exceeded,
                                  deadline_during=trace_source.deadline_during, attempts=tuple(attempts))
        sources.append(SourceSnapshot(source_id=result.source_id, status=result.status, error_kind=result.error_kind,
                                      contributed=result.source_id in aggregation.contributing_source_ids,
                                      trace=trace))
    conflicts = []
    for conflict in aggregation.conflicts:
        conflicts.append(FieldConflictDiagnostics(
            field=conflict.field, selected_source_id=conflict.selected_source_id,
            alternative_source_ids=tuple(entry[0] for entry in conflict.alternatives)))
    return MetadataSnapshot(
        status=item.status, generation=item.generation, error_kind=None, aggregate_status=aggregation.status,
        traces_available=len(traces) != 0, sources=tuple(sources),
        disabled_source_ids=aggregation.disabled_source_ids, provenance=provenance, conflicts=tuple(conflicts),
        elapsed_ms=elapsed)


def snapshot_preflight(preflight: ExecutionPreflight) -> PreflightSnapshot:
    return PreflightSnapshot(
        mode=preflight.mode, ready=preflight.ready, transfer_mode=preflight.transfer_mode,
        blockers=preflight.blockers, pending_unit_count=len(preflight.pending_units),
        completed_unit_count=len(preflight.completed_units), skipped_steps=preflight.skipped_steps,
        artifact_kinds=tuple(request.kind for request in preflight.artifacts))


def snapshot_execution(execution: ExecutionResult, path_policy: PathPolicy) -> ExecutionSnapshot:
    leftovers = []
    for leftover in execution.leftover_temporaries:
        leftovers.append((leftover.directory_role, leftover.name if path_policy is PathPolicy.BASENAME else None))
    return ExecutionSnapshot(
        status=execution.status, mode=execution.mode, transfer_mode=execution.transfer_mode,
        new_effect_count=execution.new_effect_count,
        effect_kinds=tuple((effect.kind, effect.artifact_kind) for effect in execution.completed_effects),
        failure=execution.failure, checkpoint_present=execution.checkpoint is not None,
        skipped_steps=execution.skipped_steps, leftovers=tuple(leftovers))


def output_parts(item: object, provenance: tuple, path_policy: PathPolicy, timing_policy: TimingPolicy,
                 preflight: object, execution: object) -> tuple:
    """Step 6 for one item: ``(source_name, directory_name, media_name, metadata, preflight, execution, issue)``.
    Basenames are computed only under ``PathPolicy.BASENAME``; ``NONE`` computes none."""
    source_name = directory_name = media_name = None
    if path_policy is PathPolicy.BASENAME:
        source_name = basename_of(item.media_item.source_path)
        if item.plan is not None:
            directory_name = basename_of(item.plan.target_directory.absolute_path)
            media_name = basename_of(item.plan.target_media_path.absolute_path)
    metadata = None
    if item.metadata is not None:
        metadata = snapshot_metadata(item.metadata, provenance, timing_policy)
    preflight_part = None if preflight is None else snapshot_preflight(preflight)
    execution_part = None if execution is None else snapshot_execution(execution, path_policy)
    issue = None
    if item.issue is not None:
        issue = IssueDiagnostics(stage=item.issue.stage, reason=item.issue.reason, error_type=item.issue.error_type,
                                 detail=item.issue.detail)
    return source_name, directory_name, media_name, metadata, preflight_part, execution_part, issue


def assemble_item(item: object, parts: tuple, warnings: tuple, disposition: object, retry_kind: object,
                  retained: object) -> ItemSnapshot:
    source_name, directory_name, media_name, metadata, preflight, execution, issue = parts
    return ItemSnapshot(
        index=item.index, generation=item.generation, canonical_number=item.canonical_number,
        source_name=source_name, source_size=item.media_item.size, target_directory_name=directory_name,
        target_media_name=media_name,
        preview_state=item.state if disposition is None else item.preview_state, issue=issue,
        warnings=warnings, conflict_with=item.conflict_with,
        retry_origin=item.retry_origin if disposition is None else None, disposition=disposition,
        retry_kind=retry_kind, retry_material_retained=retained, metadata=metadata,
        image_failures=tuple((failure.role, failure.kind, failure.http_status) for failure in item.image_failures),
        preflight=preflight, execution=execution)
