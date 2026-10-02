"""Immutable value models of ``fc2_organizer.orchestration`` (P4-C8 contract sections 8-11, 19.6, 25.1).

Every model is a ``@dataclass(frozen=True, slots=True)`` validated by exact type in
``__post_init__``; every violation is ``OrchestrationContractError`` (fixed wording, no path or
title text). Composite models re-run the checks of the P4-C8 models they hold, so a graph that
was rewritten with ``object.__setattr__`` before (or after, through :func:`revalidate`) being
composed is always detected.

Derived values (display properties, ``warnings`` of a preview, ``retry_kind``, ``outcome``,
retained payload byte counts, the batch ``summary`` models) are read-only properties, never stored
fields, so they cannot contradict the data they are derived from.

Besides the standard library this module imports only the bare public packages authorised by
contract section 6 (the lower-layer types the invariants are expressed in). It never imports a
lower-layer submodule, never touches the filesystem or the network and holds no module state.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from fc2_metadata_core.batch import (
    BatchConfig,
    BatchItemErrorKind,
    BatchItemResult,
    BatchItemStatus,
    BatchLineage,
    BatchResult,
)
from fc2_metadata_core.normalize import is_valid_fc2_number
from fc2_organizer.discovery import DiscoveredMediaItem
from fc2_organizer.execution import (
    ArtifactManifestError,
    CheckpointError,
    CheckpointRejectionReason,
    ExecutionCheckpoint,
    ExecutionFailure,
    ExecutionFailureKind,
    ExecutionPreflight,
    ExecutionResult,
    ExecutionStatus,
    ManifestRejectionReason,
    PlanGraphError,
    PlanGraphRejectionReason,
    PreflightIntegrityError,
    PreflightIntegrityReason,
)
from fc2_organizer.images import ImageAcquisitionPolicy, ImageCandidateFailure
from fc2_organizer.materialization import (
    ArtifactKind,
    ArtifactMappingError,
    ArtifactWriteRequest,
    MappingRejectionReason,
)
from fc2_organizer.orchestration.errors import (
    OrchestrationConfigError,
    OrchestrationContractError,
    OrchestrationIntegrityError,
)
from fc2_organizer.planning import OrganizePlan, OutputPolicy

__all__ = [
    "DEFAULT_IMAGE_IN_FLIGHT_ITEMS",
    "MAX_IMAGE_IN_FLIGHT_ITEMS",
    "DEFAULT_FILESYSTEM_WORKERS",
    "MAX_FILESYSTEM_WORKERS",
    "MAX_BATCH_ITEMS",
    "MAX_ITEM_IMAGE_BYTES",
    "DEFAULT_MAX_RETAINED_ARTIFACT_BYTES",
    "MAX_RETAINED_ARTIFACT_BYTES_LIMIT",
    "PreviewState",
    "ExecutionDisposition",
    "OrchestrationStage",
    "IssueReason",
    "ItemWarning",
    "RetryKind",
    "BatchOutcome",
    "ResourceLimitReason",
    "OrchestrationConfig",
    "ItemIssue",
    "ItemPreview",
    "PreviewSummary",
    "BatchPreview",
    "RetryMaterial",
    "ItemExecution",
    "ExecutionSummary",
    "BatchExecutionResult",
]

# --------------------------------------------------------------------------- constants (contract section 9)

DEFAULT_IMAGE_IN_FLIGHT_ITEMS = 4
MAX_IMAGE_IN_FLIGHT_ITEMS = 16
DEFAULT_FILESYSTEM_WORKERS = 1
MAX_FILESYSTEM_WORKERS = 8
MAX_BATCH_ITEMS = 2000
MAX_ITEM_IMAGE_BYTES = 64 * 1024 * 1024
DEFAULT_MAX_RETAINED_ARTIFACT_BYTES = 2 * 1024 ** 3
MAX_RETAINED_ARTIFACT_BYTES_LIMIT = 16 * 1024 ** 3


# --------------------------------------------------------------------------- enums (contract section 10.1)


class PreviewState(Enum):
    READY = "ready"
    BLOCKED = "blocked"
    UNPREPARED = "unprepared"


class ExecutionDisposition(Enum):
    EXECUTED = "executed"
    NOT_READY = "not_ready"
    NOT_SELECTED = "not_selected"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    ABORTED = "aborted"


class OrchestrationStage(Enum):
    NUMBER_RECOGNITION = "number_recognition"
    BATCH_CONFLICT = "batch_conflict"
    METADATA = "metadata"
    PLANNING = "planning"
    PUBLICATION = "publication"
    NFO_RENDER = "nfo_render"
    IMAGE_ACQUISITION = "image_acquisition"
    MANIFEST = "manifest"
    PREFLIGHT = "preflight"
    EXECUTION = "execution"


class IssueReason(Enum):
    NUMBER_NOT_RECOGNIZED = "number_not_recognized"
    DUPLICATE_SOURCE_IN_BATCH = "duplicate_source_in_batch"
    DUPLICATE_TARGET_IN_BATCH = "duplicate_target_in_batch"
    METADATA_UNAVAILABLE = "metadata_unavailable"
    METADATA_ENGINE_FAILURE = "metadata_engine_failure"
    PLANNING_REJECTED = "planning_rejected"
    PUBLICATION_REJECTED = "publication_rejected"
    NFO_RENDER_FAILED = "nfo_render_failed"
    IMAGE_ACQUISITION_ERROR = "image_acquisition_error"
    MANIFEST_REJECTED = "manifest_rejected"
    PREFLIGHT_BLOCKED = "preflight_blocked"
    PREFLIGHT_REJECTED = "preflight_rejected"
    CHECKPOINT_REJECTED = "checkpoint_rejected"
    EXECUTION_FAILED = "execution_failed"
    EXECUTION_PARTIAL = "execution_partial"
    EXECUTION_REJECTED = "execution_rejected"
    EXECUTION_ABORTED = "execution_aborted"


class ItemWarning(Enum):
    METADATA_PARTIAL = "metadata_partial"
    POSTER_ABSENT = "poster_absent"
    FANART_ABSENT = "fanart_absent"
    THUMB_ABSENT = "thumb_absent"
    NO_EXTRAFANART = "no_extrafanart"
    IMAGE_CANDIDATE_FAILURES = "image_candidate_failures"
    LEFTOVER_TEMPORARIES = "leftover_temporaries"


class RetryKind(Enum):
    METADATA_REFETCH = "metadata_refetch"
    PREFLIGHT_RECHECK = "preflight_recheck"
    FRESH_REEXECUTE = "fresh_reexecute"
    RESUME = "resume"
    DEFERRED = "deferred"
    NONE = "none"


class BatchOutcome(Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"


class ResourceLimitReason(Enum):
    BATCH_ITEM_LIMIT = "batch_item_limit"
    RETAINED_BYTES_LIMIT = "retained_bytes_limit"


# --------------------------------------------------------------------------- strict helpers (contract section 8)

_HEX_DIGITS = frozenset("0123456789abcdef")
_UNKNOWN_TYPE = "UnknownType"
_MAX_TYPE_NAME_CHARS = 128
_TYPE_NAME_DESCRIPTOR = type.__dict__["__name__"]  # the C-level getter of ``type.__name__``


def type_name(obj: object) -> str:
    """The class name of ``obj`` (contract section 8, ``error_type``). **Total**: runs no caller code.

    ``type(obj)`` never consults ``obj.__class__``; the name is read through ``type.__name__``'s own
    descriptor, bypassing any ``__name__`` a hostile metaclass defines. A class whose metaclass is
    not exactly ``type``, or whose name is not an exact identifier ``str`` of at most 128
    characters, collapses to ``"UnknownType"``.
    """
    cls = type(obj)
    if type(cls) is not type:
        return _UNKNOWN_TYPE
    name = _TYPE_NAME_DESCRIPTOR.__get__(cls, type)
    if type(name) is str and len(name) <= _MAX_TYPE_NAME_CHARS and name.isidentifier():
        return name
    return _UNKNOWN_TYPE


# exact lower-layer exception type -> the frozen reason enum its ``.reason`` must be a member of
_REASON_ENUMS: dict[type, type[Enum]] = {
    PlanGraphError: PlanGraphRejectionReason,
    ArtifactManifestError: ManifestRejectionReason,
    CheckpointError: CheckpointRejectionReason,
    PreflightIntegrityError: PreflightIntegrityReason,
    ArtifactMappingError: MappingRejectionReason,
}


def reason_detail(exc: object) -> Enum | None:
    """``exc.reason`` when ``type(exc)`` is **exactly** one of the five typed lower-layer errors of
    contract section 8 and the value is a member of its frozen reason enum; otherwise ``None``.
    Never reads ``args``, ``str()``, ``repr()`` or a traceback; runs no subclass hook."""
    enum_type = _REASON_ENUMS.get(type(exc))
    if enum_type is None:
        return None
    value = getattr(exc, "reason", None)
    return value if type(value) is enum_type else None


def _fail(message: str) -> None:
    raise OrchestrationContractError(message)


def _is_int(value: object, minimum: int = 0) -> bool:
    return type(value) is int and value >= minimum


def _is_hex32(value: object) -> bool:
    return type(value) is str and len(value) == 32 and _HEX_DIGITS.issuperset(value)


def _same_str(a: object, b: object) -> bool:
    return type(a) is str and type(b) is str and a == b


def _same_lineage(a: object, b: object) -> bool:
    return (type(a) is BatchLineage and type(b) is BatchLineage and type(a.token) is str
            and type(b.token) is str and a.token == b.token)


def _non_empty_tuple(value: object) -> bool:
    return type(value) is tuple and len(value) > 0


def _check_tuple_of(value: object, item_type: type, what: str) -> None:
    if type(value) is not tuple or any(type(item) is not item_type for item in value):
        _fail(f"{what} must be a tuple of exact {item_type.__name__}")


def _check_error_type(value: object) -> bool:
    return (type(value) is str and 1 <= len(value) <= _MAX_TYPE_NAME_CHARS and value.isidentifier())


def _check_strictly_increasing_indices(indices: list[object], what: str) -> None:
    for index in indices:
        if not _is_int(index):
            _fail(f"{what} must be exact ints >= 0")
    if any(later <= earlier for earlier, later in zip(indices, indices[1:])):
        _fail(f"{what} must strictly increase")


def _check_scope(scope: object, what: str) -> None:
    if type(scope) is not frozenset or any(type(kind) is not RetryKind for kind in scope):
        _fail(f"{what} must be a frozenset of RetryKind")
    if RetryKind.NONE in scope:
        _fail(f"{what} never contains RetryKind.NONE")


def _check_budget(value: object, what: str) -> None:
    if not _is_int(value, 1) or value > MAX_RETAINED_ARTIFACT_BYTES_LIMIT:
        _fail(f"{what} must be an exact int in 1..MAX_RETAINED_ARTIFACT_BYTES_LIMIT")


def _manifest_bytes(artifacts: object) -> int:
    """Sum of ``len(request.content)``; every request counted per reference (shared bytes repeat)."""
    if type(artifacts) is not tuple:
        _fail("an artifact manifest must be a tuple of exact ArtifactWriteRequest")
    total = 0
    for request in artifacts:
        if type(request) is not ArtifactWriteRequest or type(request.content) is not bytes:
            _fail("an artifact manifest must be a tuple of exact ArtifactWriteRequest with exact bytes content")
        total += len(request.content)
    return total


# --------------------------------------------------------------------------- config (contract section 9)


@dataclass(frozen=True, slots=True)
class OrchestrationConfig:
    """Cross-item budgets of one orchestrator: metadata M (Phase 3 ``BatchConfig``), image K,
    filesystem W and the lineage retention budget B."""

    metadata: BatchConfig = field(default_factory=BatchConfig)
    image_in_flight_items: int = DEFAULT_IMAGE_IN_FLIGHT_ITEMS
    filesystem_workers: int = DEFAULT_FILESYSTEM_WORKERS
    max_retained_artifact_bytes: int = DEFAULT_MAX_RETAINED_ARTIFACT_BYTES

    def __post_init__(self) -> None:
        failure = None
        if type(self.metadata) is not BatchConfig:
            failure = "OrchestrationConfig.metadata must be an exact BatchConfig"
        elif not _is_int(self.image_in_flight_items, 1) or self.image_in_flight_items > MAX_IMAGE_IN_FLIGHT_ITEMS:
            failure = "OrchestrationConfig.image_in_flight_items must be an exact int in 1..16"
        elif not _is_int(self.filesystem_workers, 1) or self.filesystem_workers > MAX_FILESYSTEM_WORKERS:
            failure = "OrchestrationConfig.filesystem_workers must be an exact int in 1..8"
        elif (not _is_int(self.max_retained_artifact_bytes, 1)
              or self.max_retained_artifact_bytes > MAX_RETAINED_ARTIFACT_BYTES_LIMIT):
            failure = ("OrchestrationConfig.max_retained_artifact_bytes must be an exact int in "
                       "1..MAX_RETAINED_ARTIFACT_BYTES_LIMIT")
        if failure is not None:
            raise OrchestrationConfigError(failure)


# --------------------------------------------------------------------------- ItemIssue (contract section 10.2)

_NO_DETAIL: tuple[type, ...] = ()
# reason -> (stage, error_type required?, allowed exact detail types, detail required?)
_ISSUE_TABLE: dict[IssueReason, tuple[OrchestrationStage, bool, tuple[type, ...], bool]] = {
    IssueReason.NUMBER_NOT_RECOGNIZED: (OrchestrationStage.NUMBER_RECOGNITION, False, _NO_DETAIL, False),
    IssueReason.DUPLICATE_SOURCE_IN_BATCH: (OrchestrationStage.BATCH_CONFLICT, False, _NO_DETAIL, False),
    IssueReason.DUPLICATE_TARGET_IN_BATCH: (OrchestrationStage.BATCH_CONFLICT, False, _NO_DETAIL, False),
    IssueReason.METADATA_UNAVAILABLE: (OrchestrationStage.METADATA, False, _NO_DETAIL, False),
    IssueReason.METADATA_ENGINE_FAILURE: (OrchestrationStage.METADATA, True, (BatchItemErrorKind,), True),
    IssueReason.PLANNING_REJECTED: (OrchestrationStage.PLANNING, True, _NO_DETAIL, False),
    IssueReason.PUBLICATION_REJECTED: (OrchestrationStage.PUBLICATION, True, _NO_DETAIL, False),
    IssueReason.NFO_RENDER_FAILED: (OrchestrationStage.NFO_RENDER, True, _NO_DETAIL, False),
    IssueReason.IMAGE_ACQUISITION_ERROR: (OrchestrationStage.IMAGE_ACQUISITION, True, _NO_DETAIL, False),
    IssueReason.MANIFEST_REJECTED: (OrchestrationStage.MANIFEST, True, (MappingRejectionReason,), False),
    IssueReason.PREFLIGHT_BLOCKED: (OrchestrationStage.PREFLIGHT, False, _NO_DETAIL, False),
    IssueReason.PREFLIGHT_REJECTED: (OrchestrationStage.PREFLIGHT, True,
                                     (PlanGraphRejectionReason, ManifestRejectionReason), False),
    IssueReason.CHECKPOINT_REJECTED: (OrchestrationStage.PREFLIGHT, True, (CheckpointRejectionReason,), True),
    IssueReason.EXECUTION_FAILED: (OrchestrationStage.EXECUTION, False, (ExecutionFailureKind,), True),
    IssueReason.EXECUTION_PARTIAL: (OrchestrationStage.EXECUTION, False, (ExecutionFailureKind,), True),
    IssueReason.EXECUTION_REJECTED: (OrchestrationStage.EXECUTION, True,
                                     (PreflightIntegrityReason, CheckpointRejectionReason,
                                      PlanGraphRejectionReason, ManifestRejectionReason), False),
    IssueReason.EXECUTION_ABORTED: (OrchestrationStage.EXECUTION, True, _NO_DETAIL, False),
}

_BLOCKED_REASONS = frozenset({IssueReason.PREFLIGHT_BLOCKED, IssueReason.DUPLICATE_SOURCE_IN_BATCH,
                              IssueReason.DUPLICATE_TARGET_IN_BATCH})
_DUPLICATE_REASONS = frozenset({IssueReason.DUPLICATE_SOURCE_IN_BATCH, IssueReason.DUPLICATE_TARGET_IN_BATCH})


@dataclass(frozen=True, slots=True)
class ItemIssue:
    """Why one item is not READY / not organized: stage + reason (+ class name, + frozen lower-layer
    reason member). Only enums and class names -- never an exception object or message."""

    stage: OrchestrationStage
    reason: IssueReason
    error_type: str | None = None
    detail: Enum | None = None

    def __post_init__(self) -> None:
        if type(self.stage) is not OrchestrationStage or type(self.reason) is not IssueReason:
            _fail("ItemIssue.stage / reason must be OrchestrationStage / IssueReason members")
        stage, needs_error_type, detail_types, needs_detail = _ISSUE_TABLE[self.reason]
        if self.stage is not stage:
            _fail("ItemIssue.stage does not match its reason")
        if needs_error_type:
            if not _check_error_type(self.error_type):
                _fail("ItemIssue.error_type must be an identifier str of 1..128 characters for this reason")
        elif self.error_type is not None:
            _fail("ItemIssue.error_type must be None for this reason")
        if self.detail is None:
            if needs_detail:
                _fail("ItemIssue.detail is required for this reason")
        elif type(self.detail) not in detail_types:
            _fail("ItemIssue.detail is not a member of an enum allowed for this reason")


def _check_issue(issue: object, what: str) -> None:
    if type(issue) is not ItemIssue:
        _fail(f"{what} must be an exact ItemIssue")
    ItemIssue.__post_init__(issue)


# --------------------------------------------------------------------------- shared item checks


def _check_item_core(item: ItemPreview | ItemExecution, what: str) -> None:
    """Fields and invariants common to ``ItemPreview`` and ``ItemExecution`` (contract 10.3 / 10.6)."""
    if not _is_int(item.index) or not _is_int(item.generation):
        _fail(f"{what}.index / generation must be exact ints >= 0")
    if type(item.media_item) is not DiscoveredMediaItem:
        _fail(f"{what}.media_item must be an exact DiscoveredMediaItem")
    number = item.canonical_number
    if number is not None and (type(number) is not str or not is_valid_fc2_number(number)):
        _fail(f"{what}.canonical_number must be None or a canonical FC2 number (exact str)")
    unrecognized = item.issue is not None and item.issue.reason is IssueReason.NUMBER_NOT_RECOGNIZED
    if (number is None) != unrecognized:
        _fail(f"{what}.canonical_number is None iff the issue reason is NUMBER_NOT_RECOGNIZED")
    position, metadata = item.metadata_position, item.metadata
    if position is not None and not _is_int(position):
        _fail(f"{what}.metadata_position must be None or an exact int >= 0")
    if (position is None) != (metadata is None):
        _fail(f"{what}.metadata_position is None iff metadata is None")
    if metadata is not None:
        if type(metadata) is not BatchItemResult:
            _fail(f"{what}.metadata must be an exact BatchItemResult")
        if not _same_str(metadata.number, number):
            _fail(f"{what}.metadata.number must equal canonical_number")
        if not _is_int(metadata.index) or metadata.index != position:
            _fail(f"{what}.metadata.index must equal metadata_position")
    plan = item.plan
    if plan is not None:
        if type(plan) is not OrganizePlan:
            _fail(f"{what}.plan must be an exact OrganizePlan")
        if not _same_str(plan.canonical_number, number):
            _fail(f"{what}.plan.canonical_number must equal canonical_number")
        if not _same_str(plan.source_path, item.media_item.source_path):
            _fail(f"{what}.plan.source_path must equal media_item.source_path")
    _check_tuple_of(item.image_failures, ImageCandidateFailure, f"{what}.image_failures")
    conflicts = item.conflict_with
    if type(conflicts) is not tuple:
        _fail(f"{what}.conflict_with must be a tuple of ints")
    _check_strictly_increasing_indices(list(conflicts), f"{what}.conflict_with")
    if item.index in conflicts:
        _fail(f"{what}.conflict_with never contains the item's own index")


def _plan_path(plan: object, name: str) -> str | None:
    return None if plan is None else getattr(plan, name).absolute_path


def _check_conflict_graph(items: tuple, what: str) -> None:
    """``conflict_with`` names peers present in the same collection, symmetrically (contract 14)."""
    by_index = {item.index: item for item in items}
    for item in items:
        for peer_index in item.conflict_with:
            peer = by_index.get(peer_index)
            if peer is None or item.index not in peer.conflict_with:
                _fail(f"{what}: conflict_with must name peers of the same collection, symmetrically")


# --------------------------------------------------------------------------- ItemPreview (contract section 10.3)


@dataclass(frozen=True, slots=True)
class ItemPreview:
    """One item of a ``BatchPreview``: identity, pipeline products and its preview state."""

    index: int
    generation: int
    media_item: DiscoveredMediaItem
    canonical_number: str | None
    metadata_position: int | None
    metadata: BatchItemResult | None
    plan: OrganizePlan | None
    image_failures: tuple[ImageCandidateFailure, ...]
    preflight: ExecutionPreflight | None
    state: PreviewState
    issue: ItemIssue | None
    conflict_with: tuple[int, ...]
    retry_origin: RetryKind | None

    def __post_init__(self) -> None:
        if type(self.state) is not PreviewState:
            _fail("ItemPreview.state must be a PreviewState")
        if self.issue is not None:
            _check_issue(self.issue, "ItemPreview.issue")
            if self.issue.stage is OrchestrationStage.EXECUTION:
                _fail("an ItemPreview issue is never an EXECUTION-stage issue")
        _check_item_core(self, "ItemPreview")
        preflight = self.preflight
        if preflight is not None:
            if type(preflight) is not ExecutionPreflight:
                _fail("ItemPreview.preflight must be an exact ExecutionPreflight")
            if self.plan is None or preflight.plan is not self.plan:
                _fail("ItemPreview.preflight.plan must be ItemPreview.plan (same object)")
            if type(preflight.ready) is not bool or type(preflight.blockers) is not tuple:
                _fail("ItemPreview.preflight.ready / blockers are malformed")
        executable = (preflight is not None and preflight.ready is True and self.conflict_with == ())
        if (self.state is PreviewState.READY) != (self.issue is None) or (self.issue is None) != executable:
            _fail("ItemPreview: READY iff no issue iff a ready preflight without batch conflicts")
        if self.issue is not None:
            reason = self.issue.reason
            if (self.state is PreviewState.BLOCKED) != (reason in _BLOCKED_REASONS):
                _fail("ItemPreview: BLOCKED iff the issue is PREFLIGHT_BLOCKED or a batch duplicate")
            if reason is IssueReason.PREFLIGHT_BLOCKED:
                if (preflight is None or preflight.ready is not False or not preflight.blockers
                        or self.conflict_with != ()):
                    _fail("ItemPreview: PREFLIGHT_BLOCKED needs a not-ready preflight with blockers, no conflicts")
            elif reason in _DUPLICATE_REASONS:
                if not self.conflict_with:
                    _fail("ItemPreview: a batch duplicate names its conflicting peers")
            elif preflight is not None or self.conflict_with != ():
                _fail("ItemPreview: an UNPREPARED item has no preflight and no conflicts")
        if self.retry_origin is None:
            if self.generation != 0:
                _fail("ItemPreview.retry_origin is None iff generation == 0")
        elif type(self.retry_origin) is not RetryKind or self.retry_origin is RetryKind.NONE:
            _fail("ItemPreview.retry_origin must be a RetryKind other than NONE")
        elif self.generation == 0:
            _fail("ItemPreview.retry_origin is None iff generation == 0")

    # ---- derived display properties (contract section 10.3 table)

    def _manifest_kinds(self) -> tuple[ArtifactKind, ...] | None:
        if self.preflight is None:
            return None
        _manifest_bytes(self.preflight.artifacts)
        return tuple(request.kind for request in self.preflight.artifacts)

    def _manifest_path(self, kind: ArtifactKind, name: str) -> str | None:
        kinds = self._manifest_kinds()
        return None if kinds is None or kind not in kinds else _plan_path(self.plan, name)

    @property
    def source_path(self) -> str:
        return self.media_item.source_path

    @property
    def source_size(self) -> int:
        return self.media_item.size

    @property
    def target_directory(self) -> str | None:
        return _plan_path(self.plan, "target_directory")

    @property
    def final_media_path(self) -> str | None:
        return _plan_path(self.plan, "target_media_path")

    @property
    def nfo_target(self) -> str | None:
        return _plan_path(self.plan, "nfo_path")

    @property
    def extrafanart_directory(self) -> str | None:
        return _plan_path(self.plan, "extrafanart_directory")

    @property
    def poster_target(self) -> str | None:
        return self._manifest_path(ArtifactKind.POSTER, "poster_path")

    @property
    def fanart_target(self) -> str | None:
        return self._manifest_path(ArtifactKind.FANART, "fanart_path")

    @property
    def thumb_target(self) -> str | None:
        return self._manifest_path(ArtifactKind.THUMB, "thumb_path")

    @property
    def artifact_kinds(self) -> tuple[ArtifactKind, ...] | None:
        return self._manifest_kinds()

    @property
    def extrafanart_count(self) -> int | None:
        kinds = self._manifest_kinds()
        return None if kinds is None else sum(1 for kind in kinds if kind is ArtifactKind.EXTRAFANART)

    @property
    def preflight_mode(self):
        return None if self.preflight is None else self.preflight.mode

    @property
    def planned_units(self):
        return None if self.preflight is None else self.preflight.pending_units

    @property
    def completed_units(self):
        return None if self.preflight is None else self.preflight.completed_units

    @property
    def skipped_steps(self):
        return None if self.preflight is None else self.preflight.skipped_steps

    @property
    def predicted_transfer_mode(self):
        return None if self.preflight is None else self.preflight.transfer_mode

    @property
    def blockers(self):
        return None if self.preflight is None else self.preflight.blockers

    @property
    def warnings(self) -> tuple[ItemWarning, ...]:
        """Contract section 22.3, in ``ItemWarning`` declaration order."""
        found: set[ItemWarning] = set()
        if self.metadata is not None and self.metadata.status is BatchItemStatus.PARTIAL:
            found.add(ItemWarning.METADATA_PARTIAL)
        kinds = self._manifest_kinds()
        if kinds is not None:
            for kind, warning in _ABSENT_WARNINGS:
                if kind not in kinds:
                    found.add(warning)
        if self.image_failures:
            found.add(ItemWarning.IMAGE_CANDIDATE_FAILURES)
        return tuple(warning for warning in ItemWarning if warning in found)

    @property
    def executable(self) -> bool:
        return self.state is PreviewState.READY


_ABSENT_WARNINGS = (
    (ArtifactKind.POSTER, ItemWarning.POSTER_ABSENT),
    (ArtifactKind.FANART, ItemWarning.FANART_ABSENT),
    (ArtifactKind.THUMB, ItemWarning.THUMB_ABSENT),
    (ArtifactKind.EXTRAFANART, ItemWarning.NO_EXTRAFANART),
)
_ABSENT_WARNING_SET = frozenset(warning for _, warning in _ABSENT_WARNINGS)


# --------------------------------------------------------------------------- summaries (contract section 28)


def _check_counts(model: object, names: tuple[str, ...], what: str) -> None:
    for name in names:
        if not _is_int(getattr(model, name)):
            _fail(f"{what}.{name} must be an exact int >= 0")
    counts = model.stage_counts
    if (type(counts) is not tuple or len(counts) != len(OrchestrationStage)
            or any(type(pair) is not tuple or len(pair) != 2 for pair in counts)
            or [pair[0] for pair in counts] != list(OrchestrationStage)
            or any(not _is_int(pair[1]) for pair in counts)):
        _fail(f"{what}.stage_counts must list every OrchestrationStage in declaration order with an exact int")


def _stage_counts(items: tuple) -> tuple[tuple[OrchestrationStage, int], ...]:
    """Contract section 28.1: every ``OrchestrationStage`` in declaration order (zeros included), counting
    ``issue.stage`` of the items that have an issue."""
    counts = {stage: 0 for stage in OrchestrationStage}
    for item in items:
        if item.issue is not None:
            counts[item.issue.stage] += 1
    return tuple((stage, counts[stage]) for stage in OrchestrationStage)


@dataclass(frozen=True, slots=True)
class PreviewSummary:
    """Counts of a ``BatchPreview`` (contract section 28.1); built only by ``BatchPreview.summary``."""

    total: int
    ready: int
    blocked: int
    unprepared: int
    warned: int
    stage_counts: tuple[tuple[OrchestrationStage, int], ...]

    def __post_init__(self) -> None:
        _check_counts(self, ("total", "ready", "blocked", "unprepared", "warned"), "PreviewSummary")
        if self.total != self.ready + self.blocked + self.unprepared or self.warned > self.total:
            _fail("PreviewSummary: total == ready + blocked + unprepared and warned <= total")
        if sum(count for _, count in self.stage_counts) != self.blocked + self.unprepared:
            _fail("PreviewSummary: stage_counts sum to blocked + unprepared")


_RETRYABLE_KINDS = frozenset({RetryKind.METADATA_REFETCH, RetryKind.PREFLIGHT_RECHECK, RetryKind.FRESH_REEXECUTE,
                              RetryKind.RESUME})
_EXECUTION_COUNTS = ("total", "ready", "blocked", "unprepared", "executed", "success", "partial", "failed",
                     "not_selected", "cancelled", "rejected", "aborted", "retryable", "deferred", "non_retryable")


@dataclass(frozen=True, slots=True)
class ExecutionSummary:
    """Counts of a ``BatchExecutionResult`` (contract section 28.2); built only by
    ``BatchExecutionResult.summary``. No ``outcome`` field: ``outcome`` is the result's own property."""

    total: int
    ready: int
    blocked: int
    unprepared: int
    executed: int
    success: int
    partial: int
    failed: int
    not_selected: int
    cancelled: int
    rejected: int
    aborted: int
    retryable: int
    deferred: int
    non_retryable: int
    stage_counts: tuple[tuple[OrchestrationStage, int], ...]

    def __post_init__(self) -> None:
        _check_counts(self, _EXECUTION_COUNTS, "ExecutionSummary")
        unexecuted = self.not_selected + self.cancelled + self.rejected + self.aborted
        if self.executed != self.success + self.partial + self.failed:
            _fail("ExecutionSummary: executed == success + partial + failed")
        if self.ready != self.executed + unexecuted:
            _fail("ExecutionSummary: ready == executed + not_selected + cancelled + rejected + aborted")
        if self.total != self.executed + self.blocked + self.unprepared + unexecuted:
            _fail("ExecutionSummary: total == every disposition count")
        if self.total != self.success + self.retryable + self.deferred + self.non_retryable:
            _fail("ExecutionSummary: total == success + retryable + deferred + non_retryable")
        issued = self.blocked + self.unprepared + self.partial + self.failed + self.rejected + self.aborted
        if sum(count for _, count in self.stage_counts) != issued:
            _fail("ExecutionSummary: stage_counts sum to the items that carry an issue")


# --------------------------------------------------------------------------- BatchPreview (contract section 10.4)


def _check_batch_common(model: BatchPreview | BatchExecutionResult, what: str) -> None:
    if not _is_int(model.generation):
        _fail(f"{what}.generation must be an exact int >= 0")
    if type(model.lineage) is not BatchLineage or type(model.lineage.token) is not str:
        _fail(f"{what}.lineage must be an exact BatchLineage")
    if model.base_result_id is not None and not _is_hex32(model.base_result_id):
        _fail(f"{what}.base_result_id must be None or 32 lowercase hex characters")
    if model.retry_scope is not None:
        _check_scope(model.retry_scope, f"{what}.retry_scope")
    if type(model.library_root) is not str or not model.library_root:
        _fail(f"{what}.library_root must be a non-empty exact str")
    if type(model.output_policy) is not OutputPolicy or type(model.image_policy) is not ImageAcquisitionPolicy:
        _fail(f"{what}.output_policy / image_policy must be exact OutputPolicy / ImageAcquisitionPolicy")
    if not _is_int(model.batch_size) or model.batch_size > MAX_BATCH_ITEMS:
        _fail(f"{what}.batch_size must be an exact int in 0..MAX_BATCH_ITEMS")
    if type(model.metadata_batch) is not BatchResult or type(model.metadata_batch.items) is not tuple:
        _fail(f"{what}.metadata_batch must be an exact BatchResult")
    if not _same_lineage(model.metadata_batch.lineage, model.lineage):
        _fail(f"{what}.metadata_batch.lineage must equal lineage")
    _check_budget(model.retention_budget_bytes, f"{what}.retention_budget_bytes")
    budget = model.retry_budget_bytes
    if budget is not None and (not _is_int(budget) or budget > model.retention_budget_bytes):
        _fail(f"{what}.retry_budget_bytes must be None or an exact int in 0..retention_budget_bytes")


def _check_indices(indices: list[int], batch_size: int, complete: bool, what: str) -> None:
    if complete:
        if indices != list(range(batch_size)):
            _fail(f"{what}: items must cover indices 0..batch_size-1 in order")
    else:
        _check_strictly_increasing_indices(indices, f"{what} item indices")
        if indices and indices[-1] >= batch_size:
            _fail(f"{what}: every item index must be < batch_size")


@dataclass(frozen=True, slots=True)
class BatchPreview:
    """A read-only batch preview (main: generation 0; retry: a strictly increasing index subset)."""

    preview_id: str = field(repr=False)
    lineage: BatchLineage
    generation: int
    base_result_id: str | None
    retry_scope: frozenset[RetryKind] | None
    library_root: str
    output_policy: OutputPolicy
    image_policy: ImageAcquisitionPolicy
    batch_size: int
    items: tuple[ItemPreview, ...]
    metadata_batch: BatchResult
    retention_budget_bytes: int
    retry_budget_bytes: int | None

    def __post_init__(self) -> None:
        if not _is_hex32(self.preview_id):
            _fail("BatchPreview.preview_id must be 32 lowercase hex characters")
        _check_batch_common(self, "BatchPreview")
        _check_tuple_of(self.items, ItemPreview, "BatchPreview.items")
        for item in self.items:
            ItemPreview.__post_init__(item)
        is_main = self.base_result_id is None
        if (self.retry_scope is None) != is_main or (self.generation == 0) != is_main:
            _fail("BatchPreview: base_result_id is None iff retry_scope is None iff generation == 0")
        if (self.retry_budget_bytes is None) != is_main:
            _fail("BatchPreview.retry_budget_bytes is None iff this is the main preview")
        _check_indices([item.index for item in self.items], self.batch_size, is_main, "BatchPreview")
        metadata_items = self.metadata_batch.items
        for item in self.items:
            if item.generation != self.generation:
                _fail("BatchPreview: every item carries the preview generation")
            if not is_main and item.retry_origin not in self.retry_scope:
                _fail("BatchPreview: a retry item's retry_origin must be in retry_scope")
            if item.metadata is not None and (item.metadata_position >= len(metadata_items)
                                              or item.metadata is not metadata_items[item.metadata_position]):
                _fail("BatchPreview: item.metadata must be metadata_batch.items[item.metadata_position]")
        _check_conflict_graph(self.items, "BatchPreview")
        limit = self.retention_budget_bytes if is_main else self.retry_budget_bytes
        if self.retained_artifact_bytes > limit:
            _fail("BatchPreview: retained artifact bytes exceed the retention / retry budget")

    @property
    def retained_artifact_bytes(self) -> int:
        """Σ ``len(request.content)`` over ``preflight.artifacts`` of every item with a preflight
        (contract section 10.4; shared bytes counted once per reference)."""
        return sum(_manifest_bytes(item.preflight.artifacts) for item in self.items if item.preflight is not None)

    @property
    def summary(self) -> PreviewSummary:
        """Contract section 28.1, derived from ``items`` on every access (never stored)."""
        entries = self.items
        return PreviewSummary(
            total=len(entries),
            ready=sum(1 for item in entries if item.state is PreviewState.READY),
            blocked=sum(1 for item in entries if item.state is PreviewState.BLOCKED),
            unprepared=sum(1 for item in entries if item.state is PreviewState.UNPREPARED),
            warned=sum(1 for item in entries if item.warnings),
            stage_counts=_stage_counts(entries))


# --------------------------------------------------------------------------- RetryMaterial (contract section 10.5)


@dataclass(frozen=True, slots=True)
class RetryMaterial:
    """The original ``plan`` / ``artifacts`` (and checkpoint) a retry re-preflights with."""

    plan: OrganizePlan
    artifacts: tuple[ArtifactWriteRequest, ...]
    checkpoint: ExecutionCheckpoint | None

    def __post_init__(self) -> None:
        if type(self.plan) is not OrganizePlan:
            _fail("RetryMaterial.plan must be an exact OrganizePlan")
        _manifest_bytes(self.artifacts)
        if self.checkpoint is not None and type(self.checkpoint) is not ExecutionCheckpoint:
            _fail("RetryMaterial.checkpoint must be None or an exact ExecutionCheckpoint")


def retry_payload_bytes(material: RetryMaterial) -> int:
    """Contract section 10.7: Σ ``len(req.content)`` over ``material.artifacts`` (per reference)."""
    if type(material) is not RetryMaterial:
        _fail("retry_payload_bytes needs an exact RetryMaterial")
    return _manifest_bytes(material.artifacts)


# --------------------------------------------------------------------------- ItemExecution (contract section 10.6)

_MATERIAL_KINDS = frozenset({RetryKind.PREFLIGHT_RECHECK, RetryKind.FRESH_REEXECUTE, RetryKind.RESUME,
                             RetryKind.DEFERRED})
_UNEXECUTED_READY = {
    ExecutionDisposition.NOT_SELECTED: None,
    ExecutionDisposition.CANCELLED: None,
    ExecutionDisposition.REJECTED: IssueReason.EXECUTION_REJECTED,
    ExecutionDisposition.ABORTED: IssueReason.EXECUTION_ABORTED,
}
_EXECUTED_ISSUE = {
    ExecutionStatus.SUCCESS: None,
    ExecutionStatus.FAILED: IssueReason.EXECUTION_FAILED,
    ExecutionStatus.PARTIAL: IssueReason.EXECUTION_PARTIAL,
}


@dataclass(frozen=True, slots=True)
class ItemExecution:
    """One item of a ``BatchExecutionResult``: the preview data it was (not) executed with, its
    disposition, the P4-C7 result when executed and the material a retry needs."""

    index: int
    generation: int
    media_item: DiscoveredMediaItem
    canonical_number: str | None
    metadata_position: int | None
    metadata: BatchItemResult | None
    plan: OrganizePlan | None
    image_failures: tuple[ImageCandidateFailure, ...]
    conflict_with: tuple[int, ...]
    preview_state: PreviewState
    issue: ItemIssue | None
    warnings: tuple[ItemWarning, ...]
    disposition: ExecutionDisposition
    execution: ExecutionResult | None
    retry_material: RetryMaterial | None

    def __post_init__(self) -> None:
        if type(self.preview_state) is not PreviewState or type(self.disposition) is not ExecutionDisposition:
            _fail("ItemExecution.preview_state / disposition must be enum members")
        if self.issue is not None:
            _check_issue(self.issue, "ItemExecution.issue")
        _check_item_core(self, "ItemExecution")
        self._check_disposition()
        self._check_conflicts_and_plan()
        self._check_warnings()
        self._check_retry_material()

    def _check_disposition(self) -> None:
        disposition, state, execution, issue = self.disposition, self.preview_state, self.execution, self.issue
        if (execution is None) == (disposition is ExecutionDisposition.EXECUTED):
            _fail("ItemExecution.execution is present iff disposition is EXECUTED")
        if disposition is ExecutionDisposition.NOT_READY:
            if state is PreviewState.READY or issue is None or issue.stage is OrchestrationStage.EXECUTION:
                _fail("ItemExecution: NOT_READY carries a BLOCKED / UNPREPARED preview issue")
            if (state is PreviewState.BLOCKED) != (issue.reason in _BLOCKED_REASONS):
                _fail("ItemExecution: preview_state BLOCKED iff the issue is a blocking reason")
            return
        if state is not PreviewState.READY:
            _fail("ItemExecution: only READY items are executed / selected / cancelled / rejected / aborted")
        if disposition is ExecutionDisposition.EXECUTED:
            if type(execution) is not ExecutionResult or type(execution.status) is not ExecutionStatus:
                _fail("ItemExecution.execution must be an exact ExecutionResult")
            expected = _EXECUTED_ISSUE[execution.status]
            if expected is None:
                if issue is not None:
                    _fail("ItemExecution: an EXECUTED SUCCESS item has no issue")
                return
            if issue is None or issue.reason is not expected:
                _fail("ItemExecution: an EXECUTED FAILED / PARTIAL item has the matching EXECUTION issue")
            failure = execution.failure
            if (type(failure) is not ExecutionFailure or type(failure.kind) is not ExecutionFailureKind
                    or issue.detail is not failure.kind):
                _fail("ItemExecution: issue.detail must equal execution.failure.kind")
            return
        expected = _UNEXECUTED_READY[disposition]
        if (issue is None) != (expected is None) or (issue is not None and issue.reason is not expected):
            _fail("ItemExecution: the issue does not match the disposition")

    def _check_conflicts_and_plan(self) -> None:
        duplicate = self.issue is not None and self.issue.reason in _DUPLICATE_REASONS
        if duplicate != bool(self.conflict_with):
            _fail("ItemExecution.conflict_with is non-empty iff the issue is a batch duplicate")
        if self.preview_state is PreviewState.READY and self.plan is None:
            _fail("ItemExecution: a READY item always has its plan")

    def _check_warnings(self) -> None:
        warnings = self.warnings
        _check_tuple_of(warnings, ItemWarning, "ItemExecution.warnings")
        if list(warnings) != [warning for warning in ItemWarning if warning in warnings]:
            _fail("ItemExecution.warnings must be unique and in ItemWarning declaration order")
        metadata_partial = self.metadata is not None and self.metadata.status is BatchItemStatus.PARTIAL
        leftovers = self.execution is not None and _non_empty_tuple(self.execution.leftover_temporaries)
        for warning, expected in ((ItemWarning.METADATA_PARTIAL, metadata_partial),
                                  (ItemWarning.IMAGE_CANDIDATE_FAILURES, bool(self.image_failures)),
                                  (ItemWarning.LEFTOVER_TEMPORARIES, leftovers)):
            if (warning in warnings) != expected:
                _fail("ItemExecution.warnings contradict the item data (contract section 22.3)")
        no_preflight = self.preview_state is PreviewState.UNPREPARED or self.plan is None
        if no_preflight and _ABSENT_WARNING_SET.intersection(warnings):
            _fail("ItemExecution: an item previewed without a preflight has no image-absence warning")

    def _check_retry_material(self) -> None:
        material, kind = self.retry_material, self.retry_kind
        if (material is not None) != (kind in _MATERIAL_KINDS):
            _fail("ItemExecution.retry_material is present iff retry_kind needs retained material")
        if material is None:
            return
        if type(material) is not RetryMaterial:
            _fail("ItemExecution.retry_material must be an exact RetryMaterial")
        RetryMaterial.__post_init__(material)
        if material.plan is not self.plan:
            _fail("ItemExecution.retry_material.plan must be ItemExecution.plan (same object)")
        if kind is RetryKind.RESUME:
            if material.checkpoint is None or material.checkpoint is not self.execution.checkpoint:
                _fail("ItemExecution: RESUME material carries execution.checkpoint (same object)")
        elif kind is RetryKind.FRESH_REEXECUTE and material.checkpoint is not None:
            _fail("ItemExecution: FRESH_REEXECUTE material carries no checkpoint")

    # ---- derived

    @property
    def execution_status(self) -> ExecutionStatus | None:
        return None if self.execution is None else self.execution.status

    @property
    def retry_kind(self) -> RetryKind:
        """Contract section 25.1, a pure function of disposition / execution status / issue."""
        disposition = self.disposition
        if disposition is ExecutionDisposition.EXECUTED:
            status = self.execution.status
            if status is ExecutionStatus.PARTIAL:
                return RetryKind.RESUME
            if status is ExecutionStatus.FAILED:
                return RetryKind.FRESH_REEXECUTE
            return RetryKind.NONE
        if disposition is ExecutionDisposition.NOT_READY:
            if self.issue.stage is OrchestrationStage.METADATA:
                return RetryKind.METADATA_REFETCH
            if self.issue.reason is IssueReason.PREFLIGHT_BLOCKED:
                return RetryKind.PREFLIGHT_RECHECK
            return RetryKind.NONE
        if disposition in (ExecutionDisposition.NOT_SELECTED, ExecutionDisposition.CANCELLED):
            return RetryKind.DEFERRED
        return RetryKind.NONE

    @property
    def source_path(self) -> str:
        return self.media_item.source_path

    @property
    def source_size(self) -> int:
        return self.media_item.size

    @property
    def target_directory(self) -> str | None:
        return _plan_path(self.plan, "target_directory")

    @property
    def final_media_path(self) -> str | None:
        return _plan_path(self.plan, "target_media_path")

    @property
    def nfo_target(self) -> str | None:
        return _plan_path(self.plan, "nfo_path")

    @property
    def extrafanart_directory(self) -> str | None:
        return _plan_path(self.plan, "extrafanart_directory")


# --------------------------------------------------------------------------- BatchExecutionResult (contract 10.7)


def _is_s(item: ItemExecution) -> bool:
    return item.disposition is ExecutionDisposition.EXECUTED and item.execution.status is ExecutionStatus.SUCCESS


def _is_p(item: ItemExecution) -> bool:
    return item.disposition is ExecutionDisposition.EXECUTED and item.execution.status is ExecutionStatus.PARTIAL


@dataclass(frozen=True, slots=True)
class BatchExecutionResult:
    """The result of one ``execute`` (main / retry round) or ``merge_retry`` (merged)."""

    result_id: str = field(repr=False)
    preview_id: str | None
    lineage: BatchLineage
    generation: int
    base_result_id: str | None
    retry_scope: frozenset[RetryKind] | None
    library_root: str
    output_policy: OutputPolicy
    image_policy: ImageAcquisitionPolicy
    batch_size: int
    items: tuple[ItemExecution, ...]
    metadata_batch: BatchResult
    retention_budget_bytes: int
    retry_budget_bytes: int | None

    def __post_init__(self) -> None:
        if not _is_hex32(self.result_id):
            _fail("BatchExecutionResult.result_id must be 32 lowercase hex characters")
        if self.preview_id is not None and not _is_hex32(self.preview_id):
            _fail("BatchExecutionResult.preview_id must be None or 32 lowercase hex characters")
        _check_batch_common(self, "BatchExecutionResult")
        _check_tuple_of(self.items, ItemExecution, "BatchExecutionResult.items")
        for item in self.items:
            ItemExecution.__post_init__(item)
        shape = self._shape()
        if shape is None:
            _fail("BatchExecutionResult is neither a main, a retry-round nor a merged result")
        complete = shape != "retry"
        _check_indices([item.index for item in self.items], self.batch_size, complete, "BatchExecutionResult")
        for item in self.items:
            if item.generation > self.generation or (shape != "merged" and item.generation != self.generation):
                _fail("BatchExecutionResult: item generations do not match the result shape")
        _check_conflict_graph(self.items, "BatchExecutionResult")
        if complete:
            if self.retained_retry_payload_bytes > self.retention_budget_bytes:
                _fail("BatchExecutionResult: retained retry payload exceeds retention_budget_bytes")
        elif self.retained_retry_payload_bytes > self.retry_budget_bytes:
            _fail("BatchExecutionResult: retained retry payload exceeds retry_budget_bytes")

    def _shape(self) -> str | None:
        """"main" / "retry" / "merged" (contract section 10.7, mutually exclusive) or ``None``."""
        no_retry_fields = self.base_result_id is None and self.retry_scope is None and self.retry_budget_bytes is None
        if self.generation == 0 and no_retry_fields and self.preview_id is not None:
            return "main"
        if (self.generation >= 1 and self.base_result_id is not None and self.retry_scope is not None
                and self.preview_id is not None and self.retry_budget_bytes is not None):
            return "retry"
        if self.generation >= 1 and no_retry_fields and self.preview_id is None:
            return "merged"
        return None

    @property
    def is_complete(self) -> bool:
        """Main or merged result (covers the whole lineage)."""
        return self._shape() in ("main", "merged")

    @property
    def retained_retry_payload_bytes(self) -> int:
        """Σ ``retry_payload_bytes`` over items holding ``RetryMaterial`` (contract section 10.7)."""
        return sum(retry_payload_bytes(item.retry_material) for item in self.items
                   if item.retry_material is not None)

    @property
    def summary(self) -> ExecutionSummary:
        """Contract section 28.2, derived from ``items`` on every access (never stored). ``success`` only from a
        P4-C7 ``SUCCESS``; ``PARTIAL`` never counts as success; ``ABORTED`` is counted on its own only."""
        entries = self.items
        executed = [item for item in entries if item.disposition is ExecutionDisposition.EXECUTED]
        not_ready = [item for item in entries if item.disposition is ExecutionDisposition.NOT_READY]

        def disposition(value: ExecutionDisposition) -> int:
            return sum(1 for item in entries if item.disposition is value)

        def status(value: ExecutionStatus) -> int:
            return sum(1 for item in executed if item.execution.status is value)

        kinds = [item.retry_kind for item in entries]
        return ExecutionSummary(
            total=len(entries),
            ready=sum(1 for item in entries if item.preview_state is PreviewState.READY),
            blocked=sum(1 for item in not_ready if item.preview_state is PreviewState.BLOCKED),
            unprepared=sum(1 for item in not_ready if item.preview_state is PreviewState.UNPREPARED),
            executed=len(executed),
            success=status(ExecutionStatus.SUCCESS),
            partial=status(ExecutionStatus.PARTIAL),
            failed=status(ExecutionStatus.FAILED),
            not_selected=disposition(ExecutionDisposition.NOT_SELECTED),
            cancelled=disposition(ExecutionDisposition.CANCELLED),
            rejected=disposition(ExecutionDisposition.REJECTED),
            aborted=disposition(ExecutionDisposition.ABORTED),
            retryable=sum(1 for kind in kinds if kind in _RETRYABLE_KINDS),
            deferred=sum(1 for kind in kinds if kind is RetryKind.DEFERRED),
            non_retryable=sum(1 for item, kind in zip(entries, kinds) if kind is RetryKind.NONE and not _is_s(item)),
            stage_counts=_stage_counts(entries))

    @property
    def outcome(self) -> BatchOutcome:
        """Contract section 11.5: SUCCESS iff s == total (empty included); else PARTIAL iff s + p >= 1;
        else FAILED. A pure function of ``items``."""
        s = sum(1 for item in self.items if _is_s(item))
        p = sum(1 for item in self.items if _is_p(item))
        if s == len(self.items):
            return BatchOutcome.SUCCESS
        if s + p >= 1:
            return BatchOutcome.PARTIAL
        return BatchOutcome.FAILED


# --------------------------------------------------------------------------- revalidation (contract 18.1 / 25.4 / 26)


def revalidate(model: object) -> None:
    """Internal (not exported): re-run every P4-C8 invariant of a ``BatchPreview`` /
    ``BatchExecutionResult`` object graph, e.g. after ``object.__setattr__`` tampering.

    Any violation becomes ``OrchestrationIntegrityError`` raised outside the ``except`` block (never
    chained). A non-exact model type is an integrity failure as well; no hook of it is run.
    """
    altered = False
    if type(model) is BatchPreview:
        try:
            BatchPreview.__post_init__(model)
        except OrchestrationContractError:
            altered = True
    elif type(model) is BatchExecutionResult:
        try:
            BatchExecutionResult.__post_init__(model)
        except OrchestrationContractError:
            altered = True
    else:
        altered = True
    if altered:
        raise OrchestrationIntegrityError("orchestration object graph is altered or internally inconsistent")
