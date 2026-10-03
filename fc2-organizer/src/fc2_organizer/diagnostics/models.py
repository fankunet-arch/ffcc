"""Constants, diagnostic enums and immutable diagnostics models of ``fc2_organizer.diagnostics``
(P4-C9 contract sections 8.3, 9.8, 11, 17.2, 18.2).

Every model is a ``@dataclass(frozen=True, slots=True)`` whose invariants are implemented by a
module-level *local validation function* (``*_problem``) returning ``None`` when the value is valid and a
fixed wording ``str`` otherwise. ``__post_init__`` only calls that function and raises
``DiagnosticsContractError``; the renderer (S3) calls the same functions on a whole diagnostics graph and
maps a problem to ``DiagnosticsIntegrityError`` without needing a ``try`` block. No code here reads a
``__post_init__`` (or any private / dunder name) of another object, uses reflection or ``isinstance``, and
every check is an exact-type check (``type(x) is T``; ``bool`` is never an ``int``).

Besides ``dataclasses`` / ``enum`` / ``re`` this module imports only the bare public upstream names
authorised by contract section 8.5 (the types the invariants are expressed in) and its sibling ``errors``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from fc2_metadata_core.aggregation import CONFLICT_FIELDS, OPERATIONAL_FAILURE_STATUSES, AggregateStatus
from fc2_metadata_core.batch import BatchItemErrorKind, BatchItemStatus
from fc2_metadata_core.models import SourceErrorKind, SourceStatus
from fc2_metadata_core.normalize import is_valid_fc2_number
from fc2_organizer.diagnostics.errors import DiagnosticsContractError
from fc2_organizer.execution import (
    CheckpointRejectionReason,
    EffectKind,
    ExecutionFailure,
    ExecutionFailureKind,
    ExecutionStatus,
    ExecutionStep,
    ManifestRejectionReason,
    PathRole,
    PlanGraphRejectionReason,
    PreflightBlocker,
    PreflightBlockReason,
    PreflightIntegrityReason,
    PreflightMode,
    TransferMode,
    TransferStage,
)
from fc2_organizer.images import ImageFailureKind, ImageRole
from fc2_organizer.materialization import ArtifactKind, MappingRejectionReason
from fc2_organizer.orchestration import (
    MAX_BATCH_ITEMS,
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

__all__ = [
    "DiagnosticsKind",
    "ResultShape",
    "PathPolicy",
    "TimingPolicy",
    "BatchDiagnostics",
    "MetadataBatchCounts",
    "ItemDiagnostics",
    "IssueDiagnostics",
    "MetadataDiagnostics",
    "SourceDiagnostics",
    "SourceAttemptDiagnostics",
    "FieldProvenance",
    "FieldConflictDiagnostics",
    "ImageFailureGroup",
    "PreflightDiagnostics",
    "ExecutionDiagnostics",
    "LeftoverTemporaryDiagnostics",
    "DIAGNOSTICS_SCHEMA",
    "DIAGNOSTICS_SCHEMA_VERSION",
    "PROVENANCE_FIELD_ORDER",
    "MAX_DIAGNOSTIC_ITEMS",
    "MAX_SOURCES_PER_ITEM",
    "MAX_ATTEMPTS_PER_SOURCE",
    "MAX_BLOCKERS_PER_ITEM",
    "MAX_CONFLICTS_PER_ITEM",
    "MAX_LEFTOVER_TEMPORARIES_PER_ITEM",
    "MAX_PATH_TEXT_CHARS",
    "MAX_TIMING_MS",
    "MAX_DIAGNOSTIC_OUTPUT_BYTES",
]

# --------------------------------------------------------------------------- constants (contract section 8.3)

DIAGNOSTICS_SCHEMA = "fc2_organizer.diagnostics"
DIAGNOSTICS_SCHEMA_VERSION = "1.0"
PROVENANCE_FIELD_ORDER = (
    "number", "title", "studio", "publisher", "release", "runtime", "plot", "actors", "tags",
    "poster_urls", "thumb_urls", "fanart_urls", "extrafanart", "source_urls", "external_ids",
)
MAX_DIAGNOSTIC_ITEMS = MAX_BATCH_ITEMS
MAX_SOURCES_PER_ITEM = 64
MAX_ATTEMPTS_PER_SOURCE = 8
MAX_BLOCKERS_PER_ITEM = 256
MAX_CONFLICTS_PER_ITEM = 256
MAX_LEFTOVER_TEMPORARIES_PER_ITEM = 256
MAX_PATH_TEXT_CHARS = 255
MAX_TIMING_MS = 604800000
MAX_DIAGNOSTIC_OUTPUT_BYTES = 67108864

# Internal constants (not part of any stage ``__all__``, never output): contract sections 8.3 / 9.12.
MAX_PROVENANCE_KEYS = 64
MAX_TIMING_SECONDS = MAX_TIMING_MS // 1000
# Largest HTTP status groups / retained HTTP status codes per image failure group (contract section 21.2).
MAX_HTTP_STATUSES_PER_GROUP = 500

# --------------------------------------------------------------------------- safe text rules (17.2 / 18.2)

# Source id (contract section 17.2): exact str, ``[A-Za-z0-9][A-Za-z0-9_.\-]{0,63}``.
SAFE_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.\-]{0,63}")
# P4-C7 leftover temporary file name.
LEFTOVER_NAME_PATTERN = re.compile(r"\.fc2tmp-[0-9a-f]{32}\.part")
# Lexical basename grammar (contract section 18.2, rule 4 + 5): the *allowed* characters. Anything else is
# refused: "/" and "\" (every platform), C0 / DEL / C1 controls, surrogates, U+2028 / U+2029, the bidi
# controls U+061C U+200E U+200F U+202A..U+202E U+2066..U+2069 and U+FEFF.
BASENAME_ALLOWED_CHARS = re.compile(
    "[^\\x00-\\x1f\\x7f-\\x9f\\ud800-\\udfff\\u2028\\u2029\\u061c\\u200e\\u200f\\u202a-\\u202e"
    "\\u2066-\\u2069\\ufeff/\\\\]+"
)
# error_type (contract section 17.2): identifier of 1..128 characters.
MAX_ERROR_TYPE_CHARS = 128

# --------------------------------------------------------------------------- local frozen tables (9.8 / 17.2)

_NO_DETAIL: tuple[type, ...] = ()
# T-1: reason -> (stage, error_type required?, allowed exact detail types, detail required?) -- copied from
# P4-C8 contract section 10.2 (the upstream table is private and is only compared with in tests).
ISSUE_TABLE: tuple[tuple[IssueReason, tuple[OrchestrationStage, bool, tuple[type, ...], bool]], ...] = (
    (IssueReason.NUMBER_NOT_RECOGNIZED, (OrchestrationStage.NUMBER_RECOGNITION, False, _NO_DETAIL, False)),
    (IssueReason.DUPLICATE_SOURCE_IN_BATCH, (OrchestrationStage.BATCH_CONFLICT, False, _NO_DETAIL, False)),
    (IssueReason.DUPLICATE_TARGET_IN_BATCH, (OrchestrationStage.BATCH_CONFLICT, False, _NO_DETAIL, False)),
    (IssueReason.METADATA_UNAVAILABLE, (OrchestrationStage.METADATA, False, _NO_DETAIL, False)),
    (IssueReason.METADATA_ENGINE_FAILURE, (OrchestrationStage.METADATA, True, (BatchItemErrorKind,), True)),
    (IssueReason.PLANNING_REJECTED, (OrchestrationStage.PLANNING, True, _NO_DETAIL, False)),
    (IssueReason.PUBLICATION_REJECTED, (OrchestrationStage.PUBLICATION, True, _NO_DETAIL, False)),
    (IssueReason.NFO_RENDER_FAILED, (OrchestrationStage.NFO_RENDER, True, _NO_DETAIL, False)),
    (IssueReason.IMAGE_ACQUISITION_ERROR, (OrchestrationStage.IMAGE_ACQUISITION, True, _NO_DETAIL, False)),
    (IssueReason.MANIFEST_REJECTED, (OrchestrationStage.MANIFEST, True, (MappingRejectionReason,), False)),
    (IssueReason.PREFLIGHT_BLOCKED, (OrchestrationStage.PREFLIGHT, False, _NO_DETAIL, False)),
    (IssueReason.PREFLIGHT_REJECTED, (OrchestrationStage.PREFLIGHT, True,
                                      (PlanGraphRejectionReason, ManifestRejectionReason), False)),
    (IssueReason.CHECKPOINT_REJECTED, (OrchestrationStage.PREFLIGHT, True, (CheckpointRejectionReason,), True)),
    (IssueReason.EXECUTION_FAILED, (OrchestrationStage.EXECUTION, False, (ExecutionFailureKind,), True)),
    (IssueReason.EXECUTION_PARTIAL, (OrchestrationStage.EXECUTION, False, (ExecutionFailureKind,), True)),
    (IssueReason.EXECUTION_REJECTED, (OrchestrationStage.EXECUTION, True,
                                      (PreflightIntegrityReason, CheckpointRejectionReason,
                                       PlanGraphRejectionReason, ManifestRejectionReason), False)),
    (IssueReason.EXECUTION_ABORTED, (OrchestrationStage.EXECUTION, True, _NO_DETAIL, False)),
)

# T-2: SourceStatus -> allowed SourceErrorKind set (Phase 3 resilience contract ``ALLOWED_ERROR_KINDS``).
ALLOWED_ERROR_KINDS: tuple[tuple[SourceStatus, frozenset[SourceErrorKind]], ...] = (
    (SourceStatus.NOT_FOUND, frozenset({SourceErrorKind.NOT_FOUND})),
    (SourceStatus.BLOCKED, frozenset({SourceErrorKind.BLOCKED})),
    (SourceStatus.RATE_LIMITED, frozenset({SourceErrorKind.RATE_LIMITED})),
    (SourceStatus.NETWORK_ERROR, frozenset({
        SourceErrorKind.NETWORK_ERROR, SourceErrorKind.TIMEOUT, SourceErrorKind.CONNECTION_ERROR,
        SourceErrorKind.DECODE_ERROR, SourceErrorKind.REDIRECT_ERROR, SourceErrorKind.SOURCE_DEADLINE,
        SourceErrorKind.CIRCUIT_OPEN,
    })),
    (SourceStatus.PARSE_ERROR, frozenset({SourceErrorKind.PARSE_ERROR})),
    (SourceStatus.INVALID_RESPONSE, frozenset({
        SourceErrorKind.INVALID_RESPONSE, SourceErrorKind.HTTP_SERVER_ERROR, SourceErrorKind.RESPONSE_TOO_LARGE,
        SourceErrorKind.ADAPTER_EXCEPTION, SourceErrorKind.RESULT_CONTRACT_MISMATCH,
    })),
)

# T-3: ArtifactKind -> PathRole (P4-C7 contract section 14.2).
ARTIFACT_ROLE: tuple[tuple[ArtifactKind, PathRole], ...] = (
    (ArtifactKind.NFO, PathRole.NFO),
    (ArtifactKind.POSTER, PathRole.POSTER),
    (ArtifactKind.FANART, PathRole.FANART),
    (ArtifactKind.THUMB, PathRole.THUMB),
    (ArtifactKind.EXTRAFANART, PathRole.EXTRAFANART_FILE),
)

# T-4 (P4-C8 contract section 10.3).
BLOCKED_REASONS = frozenset({IssueReason.PREFLIGHT_BLOCKED, IssueReason.DUPLICATE_SOURCE_IN_BATCH,
                             IssueReason.DUPLICATE_TARGET_IN_BATCH})
DUPLICATE_REASONS = frozenset({IssueReason.DUPLICATE_SOURCE_IN_BATCH, IssueReason.DUPLICATE_TARGET_IN_BATCH})

# Contract section 11.4: the frozen detail enum types and the class name each is output under (the name is
# taken from this table, never from ``type(x).__name__``).
DETAIL_TYPE_NAMES: tuple[tuple[type, str], ...] = (
    (BatchItemErrorKind, "BatchItemErrorKind"),
    (MappingRejectionReason, "MappingRejectionReason"),
    (PlanGraphRejectionReason, "PlanGraphRejectionReason"),
    (ManifestRejectionReason, "ManifestRejectionReason"),
    (CheckpointRejectionReason, "CheckpointRejectionReason"),
    (ExecutionFailureKind, "ExecutionFailureKind"),
    (PreflightIntegrityReason, "PreflightIntegrityReason"),
)


def issue_rule(reason: IssueReason) -> tuple[OrchestrationStage, bool, tuple[type, ...], bool]:
    """T-1 row of ``reason`` (``reason`` is an exact ``IssueReason``: callers confirm it first)."""
    for key, rule in ISSUE_TABLE:
        if key is reason:
            return rule
    raise DiagnosticsContractError("IssueDiagnostics.reason has no T-1 row")


def allowed_error_kinds(status: SourceStatus) -> frozenset[SourceErrorKind]:
    """T-2 row of ``status`` (an empty set for ``SUCCESS``)."""
    for key, kinds in ALLOWED_ERROR_KINDS:
        if key is status:
            return kinds
    return frozenset()


def artifact_role(kind: ArtifactKind) -> PathRole:
    """T-3: the ``PathRole`` of an artifact kind."""
    for key, role in ARTIFACT_ROLE:
        if key is kind:
            return role
    raise DiagnosticsContractError("ArtifactKind has no T-3 row")


def detail_type_name(detail_type: type) -> str | None:
    """The output class name of a frozen detail enum type; ``None`` for any other type (never ``__name__``)."""
    for key, name in DETAIL_TYPE_NAMES:
        if key is detail_type:
            return name
    return None


# --------------------------------------------------------------------------- new diagnostics enums (section 11)


class DiagnosticsKind(Enum):
    PREVIEW = "preview"
    EXECUTION = "execution"


class ResultShape(Enum):
    MAIN = "main"
    RETRY = "retry"
    MERGED = "merged"


class PathPolicy(Enum):
    NONE = "none"
    BASENAME = "basename"


class TimingPolicy(Enum):
    OMIT = "omit"
    INCLUDE = "include"


# --------------------------------------------------------------------------- strict helpers (all exact-type)


def is_int(value: object, minimum: int = 0) -> bool:
    return type(value) is int and value >= minimum


def is_opt_int(value: object, minimum: int = 0) -> bool:
    return value is None or (type(value) is int and value >= minimum)


def is_bool(value: object) -> bool:
    return type(value) is bool


def is_safe_id(value: object) -> bool:
    return type(value) is str and SAFE_ID_PATTERN.fullmatch(value) is not None


def is_safe_basename(value: object) -> bool:
    """Contract section 18.2 (``os.sep`` / ``os.altsep`` are subsumed: both are ``/`` or ``\\``)."""
    return (type(value) is str and 1 <= len(value) <= MAX_PATH_TEXT_CHARS and value != "." and value != ".."
            and BASENAME_ALLOWED_CHARS.fullmatch(value) is not None)


def is_opt_safe_basename(value: object) -> bool:
    return value is None or is_safe_basename(value)


def is_error_type(value: object) -> bool:
    return type(value) is str and 1 <= len(value) <= MAX_ERROR_TYPE_CHARS and value.isidentifier()


def is_tuple_of(value: object, item_type: type) -> bool:
    if type(value) is not tuple:
        return False
    for item in value:
        if type(item) is not item_type:
            return False
    return True


def is_unique_ordered_enum_tuple(value: object, enum_type: type[Enum]) -> bool:
    """An exact tuple of exact ``enum_type`` members, unique and in declaration order."""
    if not is_tuple_of(value, enum_type):
        return False
    return tuple(member for member in enum_type if member in value) == value


def is_enum_count_pairs(value: object, enum_type: type[Enum]) -> bool:
    """Exactly one ``(member, int >= 0)`` pair per member of ``enum_type``, in declaration order."""
    if type(value) is not tuple or len(value) != len(enum_type):
        return False
    for pair in value:
        if type(pair) is not tuple or len(pair) != 2:
            return False
        if type(pair[0]) is not enum_type or not is_int(pair[1]):
            return False
    return tuple(pair[0] for pair in value) == tuple(enum_type)


def strictly_increasing_ints(values: tuple) -> bool:
    previous = -1
    for value in values:
        if type(value) is not int or value <= previous:
            return False
        previous = value
    return True


def _timing_ok(value: object) -> bool:
    """A published timing value: ``None`` or an exact ``int`` in ``0..MAX_TIMING_MS``."""
    return value is None or (type(value) is int and 0 <= value <= MAX_TIMING_MS)


def _raise(problem: str | None) -> None:
    if problem is not None:
        raise DiagnosticsContractError(problem)


# --------------------------------------------------------------------------- upstream value objects carried as-is


def stage_counts_problem(counts: object) -> str | None:
    """``stage_counts`` of the P4-C8 summaries (M-08 / M-09): every ``OrchestrationStage`` once, in order."""
    if not is_enum_count_pairs(counts, OrchestrationStage):
        return "summary.stage_counts must list every OrchestrationStage in declaration order with an exact int"
    return None


def preview_summary_problem(summary: object) -> str | None:
    """M-08: an exact ``PreviewSummary`` whose counts satisfy the P4-C8 identities."""
    if type(summary) is not PreviewSummary:
        return "preview_summary must be an exact PreviewSummary"
    counts = (summary.total, summary.ready, summary.blocked, summary.unprepared, summary.warned)
    for count in counts:
        if not is_int(count):
            return "PreviewSummary counts must be exact ints >= 0"
    counts_problem = stage_counts_problem(summary.stage_counts)
    if counts_problem is not None:
        return counts_problem
    if summary.total != summary.ready + summary.blocked + summary.unprepared or summary.warned > summary.total:
        return "PreviewSummary: total == ready + blocked + unprepared and warned <= total"
    staged = 0
    for pair in summary.stage_counts:
        staged += pair[1]
    if staged != summary.blocked + summary.unprepared:
        return "PreviewSummary: stage_counts sum to blocked + unprepared"
    return None


def execution_summary_problem(summary: object) -> str | None:
    """M-09: an exact ``ExecutionSummary`` whose counts satisfy the five P4-C8 identities."""
    if type(summary) is not ExecutionSummary:
        return "execution_summary must be an exact ExecutionSummary"
    counts = (summary.total, summary.ready, summary.blocked, summary.unprepared, summary.executed,
              summary.success, summary.partial, summary.failed, summary.not_selected, summary.cancelled,
              summary.rejected, summary.aborted, summary.retryable, summary.deferred, summary.non_retryable)
    for count in counts:
        if not is_int(count):
            return "ExecutionSummary counts must be exact ints >= 0"
    counts_problem = stage_counts_problem(summary.stage_counts)
    if counts_problem is not None:
        return counts_problem
    unexecuted = summary.not_selected + summary.cancelled + summary.rejected + summary.aborted
    if summary.executed != summary.success + summary.partial + summary.failed:
        return "ExecutionSummary: executed == success + partial + failed"
    if summary.ready != summary.executed + unexecuted:
        return "ExecutionSummary: ready == executed + not_selected + cancelled + rejected + aborted"
    if summary.total != summary.executed + summary.blocked + summary.unprepared + unexecuted:
        return "ExecutionSummary: total == every disposition count"
    if summary.total != summary.success + summary.retryable + summary.deferred + summary.non_retryable:
        return "ExecutionSummary: total == success + retryable + deferred + non_retryable"
    issued = (summary.blocked + summary.unprepared + summary.partial + summary.failed + summary.rejected
              + summary.aborted)
    staged = 0
    for pair in summary.stage_counts:
        staged += pair[1]
    if staged != issued:
        return "ExecutionSummary: stage_counts sum to the items that carry an issue"
    return None


def blocker_problem(blocker: object) -> str | None:
    """M-25: an exact ``PreflightBlocker``."""
    if type(blocker) is not PreflightBlocker:
        return "blockers must be exact PreflightBlocker values"
    if type(blocker.reason) is not PreflightBlockReason or type(blocker.role) is not PathRole:
        return "PreflightBlocker.reason / role must be enum members"
    if not is_opt_int(blocker.errno) or not is_opt_int(blocker.ordinal, 1):
        return "PreflightBlocker.errno / ordinal must be exact ints or None"
    return None


def failure_problem(failure: object) -> str | None:
    """M-28: an exact ``ExecutionFailure``."""
    if type(failure) is not ExecutionFailure:
        return "failure must be an exact ExecutionFailure"
    if type(failure.step) is not ExecutionStep or type(failure.kind) is not ExecutionFailureKind:
        return "ExecutionFailure.step / kind must be enum members"
    if failure.stage is not None and type(failure.stage) is not TransferStage:
        return "ExecutionFailure.stage must be a TransferStage or None"
    if failure.artifact_kind is not None and type(failure.artifact_kind) is not ArtifactKind:
        return "ExecutionFailure.artifact_kind must be an ArtifactKind or None"
    write_stage = failure.write_stage
    if write_stage is not None:
        if type(write_stage) is not str or (write_stage != "write" and write_stage != "flush"
                                            and write_stage != "close"):
            return "ExecutionFailure.write_stage must be write / flush / close"
        if failure.kind is not ExecutionFailureKind.ARTIFACT_WRITE_FAILED:
            return "ExecutionFailure.write_stage is only for ARTIFACT_WRITE_FAILED"
    if not is_opt_int(failure.errno):
        return "ExecutionFailure.errno must be an exact int or None"
    if not is_opt_int(failure.ordinal, 1):
        return "ExecutionFailure.ordinal must be an exact int >= 1 or None"
    if failure.ordinal is not None and failure.artifact_kind is not ArtifactKind.EXTRAFANART:
        return "ExecutionFailure.ordinal is only for extrafanart"
    if failure.target_published is not None:
        if type(failure.target_published) is not bool:
            return "ExecutionFailure.target_published must be a bool or None"
        if (failure.kind is not ExecutionFailureKind.ARTIFACT_CLEANUP_FAILED
                and failure.kind is not ExecutionFailureKind.MEDIA_TEMP_CLEANUP_FAILED):
            return "ExecutionFailure.target_published is only for cleanup failures"
    return None


# --------------------------------------------------------------------------- MetadataBatchCounts (11.2)


@dataclass(frozen=True, slots=True)
class MetadataBatchCounts:
    generation: int
    total: int
    success: int
    partial: int
    failed: int

    def __post_init__(self) -> None:
        _raise(metadata_batch_counts_problem(self))


def metadata_batch_counts_problem(value: object) -> str | None:
    if type(value) is not MetadataBatchCounts:
        return "MetadataBatchCounts must be an exact MetadataBatchCounts"
    for number in (value.generation, value.total, value.success, value.partial, value.failed):
        if not is_int(number):
            return "MetadataBatchCounts fields must be exact ints >= 0"
    if value.total != value.success + value.partial + value.failed:
        return "MetadataBatchCounts.total must equal success + partial + failed"
    return None


# --------------------------------------------------------------------------- IssueDiagnostics (11.4)


@dataclass(frozen=True, slots=True)
class IssueDiagnostics:
    stage: OrchestrationStage
    reason: IssueReason
    error_type: str | None
    detail: Enum | None

    def __post_init__(self) -> None:
        _raise(issue_problem(self))


def issue_problem(value: object) -> str | None:
    if type(value) is not IssueDiagnostics:
        return "issue must be an exact IssueDiagnostics"
    if type(value.stage) is not OrchestrationStage or type(value.reason) is not IssueReason:
        return "IssueDiagnostics.stage / reason must be OrchestrationStage / IssueReason members"
    stage, needs_error_type, detail_types, needs_detail = issue_rule(value.reason)
    if value.stage is not stage:
        return "IssueDiagnostics.stage does not match its reason"
    if needs_error_type:
        if not is_error_type(value.error_type):
            return "IssueDiagnostics.error_type must be an identifier of 1..128 characters for this reason"
    elif value.error_type is not None:
        return "IssueDiagnostics.error_type must be None for this reason"
    if value.detail is None:
        if needs_detail:
            return "IssueDiagnostics.detail is required for this reason"
    elif type(value.detail) not in detail_types:
        return "IssueDiagnostics.detail is not a member of an enum allowed for this reason"
    return None


# --------------------------------------------------------------------------- FieldProvenance / FieldConflict (11.8 / 11.9)


@dataclass(frozen=True, slots=True)
class FieldProvenance:
    field: str
    source_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _raise(field_provenance_problem(self))


def _unique_safe_ids(values: object, maximum: int) -> bool:
    if type(values) is not tuple or len(values) > maximum:
        return False
    for value in values:
        if not is_safe_id(value):
            return False
    return len(set(values)) == len(values)


def field_provenance_problem(value: object) -> str | None:
    if type(value) is not FieldProvenance:
        return "field_provenance entries must be exact FieldProvenance values"
    if type(value.field) is not str or value.field not in PROVENANCE_FIELD_ORDER:
        return "FieldProvenance.field must be a member of PROVENANCE_FIELD_ORDER"
    if not _unique_safe_ids(value.source_ids, MAX_SOURCES_PER_ITEM) or len(value.source_ids) == 0:
        return "FieldProvenance.source_ids must be a non-empty tuple of unique safe source ids"
    return None


@dataclass(frozen=True, slots=True)
class FieldConflictDiagnostics:
    field: str
    selected_source_id: str
    alternative_source_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _raise(field_conflict_problem(self))


def field_conflict_problem(value: object) -> str | None:
    if type(value) is not FieldConflictDiagnostics:
        return "conflicts entries must be exact FieldConflictDiagnostics values"
    if type(value.field) is not str or value.field not in CONFLICT_FIELDS:
        return "FieldConflictDiagnostics.field must be a member of CONFLICT_FIELDS"
    if not is_safe_id(value.selected_source_id):
        return "FieldConflictDiagnostics.selected_source_id must be a safe source id"
    alternatives = value.alternative_source_ids
    if not _unique_safe_ids(alternatives, MAX_SOURCES_PER_ITEM) or len(alternatives) == 0:
        return "FieldConflictDiagnostics.alternative_source_ids must be a non-empty tuple of unique safe ids"
    if value.selected_source_id in alternatives:
        return "FieldConflictDiagnostics.alternative_source_ids must not contain the selected source"
    return None


# --------------------------------------------------------------------------- SourceAttemptDiagnostics (11.7)


@dataclass(frozen=True, slots=True)
class SourceAttemptDiagnostics:
    sequence: int
    status: SourceStatus
    error_kind: SourceErrorKind | None
    completed: bool
    elapsed_ms: int | None
    backoff_before_ms: int | None

    def __post_init__(self) -> None:
        _raise(source_attempt_problem(self))


def source_attempt_problem(value: object) -> str | None:
    if type(value) is not SourceAttemptDiagnostics:
        return "attempts must be exact SourceAttemptDiagnostics values"
    if not is_int(value.sequence, 1):
        return "SourceAttemptDiagnostics.sequence must be an exact int >= 1"
    if type(value.status) is not SourceStatus:
        return "SourceAttemptDiagnostics.status must be a SourceStatus"
    if value.status is SourceStatus.SUCCESS:
        if value.error_kind is not None:
            return "a successful attempt has no error_kind"
    elif type(value.error_kind) is not SourceErrorKind or value.error_kind not in allowed_error_kinds(value.status):
        return "a failed attempt needs an error_kind allowed for its status"
    if not is_bool(value.completed):
        return "SourceAttemptDiagnostics.completed must be a bool"
    if not _timing_ok(value.elapsed_ms) or not _timing_ok(value.backoff_before_ms):
        return "SourceAttemptDiagnostics timings must be None or an exact int in 0..MAX_TIMING_MS"
    if (value.elapsed_ms is None) != (value.backoff_before_ms is None):
        return "SourceAttemptDiagnostics timings are either both published or both None"
    return None


# --------------------------------------------------------------------------- SourceDiagnostics (11.6)


@dataclass(frozen=True, slots=True)
class SourceDiagnostics:
    source_id: str
    status: SourceStatus
    error_kind: SourceErrorKind | None
    contributed: bool
    operational_failure: bool
    provided_fields: tuple[str, ...]
    trace_available: bool
    attempt_count: int | None
    max_attempts: int | None
    deadline_exceeded: bool | None
    deadline_during: str | None
    attempts: tuple[SourceAttemptDiagnostics, ...]

    def __post_init__(self) -> None:
        _raise(source_problem(self))


def source_problem(value: object) -> str | None:
    if type(value) is not SourceDiagnostics:
        return "sources must be exact SourceDiagnostics values"
    if not is_safe_id(value.source_id):
        return "SourceDiagnostics.source_id must be a safe source id"
    if type(value.status) is not SourceStatus:
        return "SourceDiagnostics.status must be a SourceStatus"
    if value.status is SourceStatus.SUCCESS:
        if value.error_kind is not None:
            return "SourceDiagnostics.error_kind is None iff status is SUCCESS"
    elif type(value.error_kind) is not SourceErrorKind or value.error_kind not in allowed_error_kinds(value.status):
        return "SourceDiagnostics.error_kind is None iff status is SUCCESS"
    if not is_bool(value.contributed) or not is_bool(value.operational_failure) or not is_bool(value.trace_available):
        return "SourceDiagnostics flags must be exact bools"
    if value.operational_failure != (value.status in OPERATIONAL_FAILURE_STATUSES):
        return "SourceDiagnostics.operational_failure must follow OPERATIONAL_FAILURE_STATUSES"
    fields = value.provided_fields
    if type(fields) is not tuple:
        return "SourceDiagnostics.provided_fields must be a tuple"
    for name in fields:
        if type(name) is not str or name not in PROVENANCE_FIELD_ORDER:
            return "SourceDiagnostics.provided_fields must name PROVENANCE_FIELD_ORDER members"
    if tuple(name for name in PROVENANCE_FIELD_ORDER if name in fields) != fields:
        return "SourceDiagnostics.provided_fields must be unique and in PROVENANCE_FIELD_ORDER"
    if not value.contributed and len(fields) != 0:
        return "a source that did not contribute provides no fields"
    attempts = value.attempts
    if type(attempts) is not tuple or len(attempts) > MAX_ATTEMPTS_PER_SOURCE:
        return "SourceDiagnostics.attempts must be a tuple of at most MAX_ATTEMPTS_PER_SOURCE items"
    for attempt in attempts:
        problem = source_attempt_problem(attempt)
        if problem is not None:
            return problem
    expected = 1
    for attempt in attempts:
        if attempt.sequence != expected:
            return "SourceDiagnostics.attempts must be in sequence order 1..n"
        expected += 1
    if not value.trace_available:
        if (value.attempt_count is not None or value.max_attempts is not None or value.deadline_exceeded is not None
                or value.deadline_during is not None or len(attempts) != 0):
            return "a source without a trace has no trace fields"
        return None
    if not is_int(value.attempt_count) or value.attempt_count != len(attempts):
        return "SourceDiagnostics.attempt_count must equal len(attempts)"
    if not is_int(value.max_attempts, 1):
        return "SourceDiagnostics.max_attempts must be an exact int >= 1"
    if not is_bool(value.deadline_exceeded):
        return "SourceDiagnostics.deadline_exceeded must be a bool when a trace is available"
    during = value.deadline_during
    if during is not None and (type(during) is not str or (during != "attempt" and during != "backoff")):
        return "SourceDiagnostics.deadline_during must be None, 'attempt' or 'backoff'"
    if value.deadline_exceeded != (during is not None):
        return "SourceDiagnostics.deadline_exceeded is true iff deadline_during is not None"
    return None


# --------------------------------------------------------------------------- MetadataDiagnostics (11.5)


@dataclass(frozen=True, slots=True)
class MetadataDiagnostics:
    status: BatchItemStatus
    generation: int
    error_kind: BatchItemErrorKind | None
    aggregate_status: AggregateStatus | None
    traces_available: bool
    sources: tuple[SourceDiagnostics, ...]
    disabled_source_ids: tuple[str, ...]
    field_provenance: tuple[FieldProvenance, ...]
    conflicts: tuple[FieldConflictDiagnostics, ...]
    elapsed_ms: int | None

    def __post_init__(self) -> None:
        _raise(metadata_problem(self))


def metadata_problem(value: object) -> str | None:
    if type(value) is not MetadataDiagnostics:
        return "metadata must be an exact MetadataDiagnostics"
    if type(value.status) is not BatchItemStatus:
        return "MetadataDiagnostics.status must be a BatchItemStatus"
    if not is_int(value.generation):
        return "MetadataDiagnostics.generation must be an exact int >= 0"
    has_aggregate = value.aggregate_status is not None
    if has_aggregate:
        if type(value.aggregate_status) is not AggregateStatus:
            return "MetadataDiagnostics.aggregate_status must be an AggregateStatus or None"
        if value.error_kind is not None:
            return "MetadataDiagnostics.error_kind is set iff there is no AggregationResult"
    else:
        if type(value.error_kind) is not BatchItemErrorKind:
            return "MetadataDiagnostics.error_kind is set iff there is no AggregationResult"
        if value.status is not BatchItemStatus.FAILED:
            return "an item without an AggregationResult is FAILED"
    if not is_bool(value.traces_available):
        return "MetadataDiagnostics.traces_available must be a bool"
    if not has_aggregate and value.traces_available:
        return "MetadataDiagnostics.traces_available is false without an AggregationResult"
    sources = value.sources
    if type(sources) is not tuple or len(sources) > MAX_SOURCES_PER_ITEM:
        return "MetadataDiagnostics.sources must be a tuple of at most MAX_SOURCES_PER_ITEM items"
    for source in sources:
        problem = source_problem(source)
        if problem is not None:
            return problem
    if not has_aggregate and len(sources) != 0:
        return "MetadataDiagnostics.sources is empty without an AggregationResult"
    source_ids = tuple(source.source_id for source in sources)
    if len(set(source_ids)) != len(source_ids):
        return "MetadataDiagnostics.sources must have unique source ids"
    for source in sources:
        if source.trace_available != value.traces_available:
            return "MetadataDiagnostics.traces_available must match every source's trace_available"
    if not _unique_safe_ids(value.disabled_source_ids, MAX_SOURCES_PER_ITEM):
        return "MetadataDiagnostics.disabled_source_ids must be a tuple of unique safe source ids"
    for disabled in value.disabled_source_ids:
        if disabled in source_ids:
            return "MetadataDiagnostics.disabled_source_ids must not overlap sources"
    provenance = value.field_provenance
    if type(provenance) is not tuple or len(provenance) > len(PROVENANCE_FIELD_ORDER):
        return "MetadataDiagnostics.field_provenance must be a tuple of at most one entry per known field"
    for entry in provenance:
        problem = field_provenance_problem(entry)
        if problem is not None:
            return problem
    seen_fields = tuple(entry.field for entry in provenance)
    if tuple(name for name in PROVENANCE_FIELD_ORDER if name in seen_fields) != seen_fields:
        return "MetadataDiagnostics.field_provenance must be unique and in PROVENANCE_FIELD_ORDER"
    for source in sources:
        provided = tuple(entry.field for entry in provenance if source.source_id in entry.source_ids)
        if provided != source.provided_fields:
            return "SourceDiagnostics.provided_fields must match MetadataDiagnostics.field_provenance"
    conflicts = value.conflicts
    if type(conflicts) is not tuple or len(conflicts) > MAX_CONFLICTS_PER_ITEM:
        return "MetadataDiagnostics.conflicts must be a tuple of at most MAX_CONFLICTS_PER_ITEM items"
    for conflict in conflicts:
        problem = field_conflict_problem(conflict)
        if problem is not None:
            return problem
    if not _timing_ok(value.elapsed_ms):
        return "MetadataDiagnostics.elapsed_ms must be None or an exact int in 0..MAX_TIMING_MS"
    return None


# --------------------------------------------------------------------------- ImageFailureGroup (11.10)


@dataclass(frozen=True, slots=True)
class ImageFailureGroup:
    role: ImageRole
    kind: ImageFailureKind
    count: int
    http_statuses: tuple[int, ...]

    def __post_init__(self) -> None:
        _raise(image_failure_group_problem(self))


def image_failure_group_problem(value: object) -> str | None:
    if type(value) is not ImageFailureGroup:
        return "image_failures entries must be exact ImageFailureGroup values"
    if type(value.role) is not ImageRole or type(value.kind) is not ImageFailureKind:
        return "ImageFailureGroup.role / kind must be enum members"
    if not is_int(value.count, 1):
        return "ImageFailureGroup.count must be an exact int >= 1"
    statuses = value.http_statuses
    if type(statuses) is not tuple or len(statuses) > MAX_HTTP_STATUSES_PER_GROUP:
        return "ImageFailureGroup.http_statuses must be a short tuple"
    previous = 99
    for status in statuses:
        if type(status) is not int or status <= previous or status > 599:
            return "ImageFailureGroup.http_statuses must be ascending, unique and in 100..599"
        previous = status
    if (value.kind is ImageFailureKind.HTTP_STATUS) != (len(statuses) != 0):
        return "ImageFailureGroup.http_statuses is non-empty iff kind is HTTP_STATUS"
    return None


# --------------------------------------------------------------------------- PreflightDiagnostics (11.11)


@dataclass(frozen=True, slots=True)
class PreflightDiagnostics:
    mode: PreflightMode
    ready: bool
    transfer_mode: TransferMode | None
    blockers: tuple[PreflightBlocker, ...]
    pending_unit_count: int
    completed_unit_count: int
    skipped_steps: tuple[ExecutionStep, ...]
    artifact_counts: tuple[tuple[ArtifactKind, int], ...]

    def __post_init__(self) -> None:
        _raise(preflight_problem(self))


def preflight_problem(value: object) -> str | None:
    if type(value) is not PreflightDiagnostics:
        return "preflight must be an exact PreflightDiagnostics"
    if type(value.mode) is not PreflightMode:
        return "PreflightDiagnostics.mode must be a PreflightMode"
    if not is_bool(value.ready):
        return "PreflightDiagnostics.ready must be a bool"
    if value.transfer_mode is not None and type(value.transfer_mode) is not TransferMode:
        return "PreflightDiagnostics.transfer_mode must be a TransferMode or None"
    blockers = value.blockers
    if type(blockers) is not tuple or len(blockers) > MAX_BLOCKERS_PER_ITEM:
        return "PreflightDiagnostics.blockers must be a tuple of at most MAX_BLOCKERS_PER_ITEM items"
    for blocker in blockers:
        problem = blocker_problem(blocker)
        if problem is not None:
            return problem
    if value.ready != (len(blockers) == 0):
        return "PreflightDiagnostics.ready is true iff there are no blockers"
    if not is_int(value.pending_unit_count) or not is_int(value.completed_unit_count):
        return "PreflightDiagnostics unit counts must be exact ints >= 0"
    if not is_tuple_of(value.skipped_steps, ExecutionStep):
        return "PreflightDiagnostics.skipped_steps must be a tuple of ExecutionStep"
    if not is_enum_count_pairs(value.artifact_counts, ArtifactKind):
        return "PreflightDiagnostics.artifact_counts must list every ArtifactKind in declaration order"
    return None


# --------------------------------------------------------------------------- Leftover / Execution (11.12 / 11.13)


@dataclass(frozen=True, slots=True)
class LeftoverTemporaryDiagnostics:
    directory_role: PathRole
    name: str | None

    def __post_init__(self) -> None:
        _raise(leftover_problem(self))


def leftover_problem(value: object) -> str | None:
    if type(value) is not LeftoverTemporaryDiagnostics:
        return "leftover_temporaries must be exact LeftoverTemporaryDiagnostics values"
    if type(value.directory_role) is not PathRole or (value.directory_role is not PathRole.TARGET_DIRECTORY
                                                      and value.directory_role is not PathRole.EXTRAFANART_DIRECTORY):
        return "LeftoverTemporaryDiagnostics.directory_role must be TARGET_DIRECTORY or EXTRAFANART_DIRECTORY"
    if value.name is not None and (type(value.name) is not str or LEFTOVER_NAME_PATTERN.fullmatch(value.name) is None):
        return "LeftoverTemporaryDiagnostics.name must be None or match .fc2tmp-<32 hex>.part"
    return None


@dataclass(frozen=True, slots=True)
class ExecutionDiagnostics:
    status: ExecutionStatus
    mode: PreflightMode
    transfer_mode: TransferMode | None
    new_effect_count: int
    effect_counts: tuple[tuple[EffectKind, int], ...]
    artifact_counts: tuple[tuple[ArtifactKind, int], ...]
    failure: ExecutionFailure | None
    checkpoint_present: bool
    skipped_steps: tuple[ExecutionStep, ...]
    leftover_temporary_count: int
    leftover_temporaries: tuple[LeftoverTemporaryDiagnostics, ...]

    def __post_init__(self) -> None:
        _raise(execution_problem(self))


def execution_problem(value: object) -> str | None:
    if type(value) is not ExecutionDiagnostics:
        return "execution must be an exact ExecutionDiagnostics"
    if type(value.status) is not ExecutionStatus or type(value.mode) is not PreflightMode:
        return "ExecutionDiagnostics.status / mode must be enum members"
    if value.transfer_mode is not None and type(value.transfer_mode) is not TransferMode:
        return "ExecutionDiagnostics.transfer_mode must be a TransferMode or None"
    if not is_enum_count_pairs(value.effect_counts, EffectKind):
        return "ExecutionDiagnostics.effect_counts must list every EffectKind in declaration order"
    if not is_enum_count_pairs(value.artifact_counts, ArtifactKind):
        return "ExecutionDiagnostics.artifact_counts must list every ArtifactKind in declaration order"
    effects = 0
    for pair in value.effect_counts:
        effects += pair[1]
    if not is_int(value.new_effect_count) or value.new_effect_count > effects:
        return "ExecutionDiagnostics.new_effect_count must be an exact int <= sum(effect_counts)"
    if value.failure is not None:
        problem = failure_problem(value.failure)
        if problem is not None:
            return problem
    if (value.status is ExecutionStatus.SUCCESS) != (value.failure is None):
        return "ExecutionDiagnostics.failure is None iff status is SUCCESS"
    if not is_bool(value.checkpoint_present):
        return "ExecutionDiagnostics.checkpoint_present must be a bool"
    if (value.status is ExecutionStatus.PARTIAL) != value.checkpoint_present:
        return "ExecutionDiagnostics.checkpoint_present is true iff status is PARTIAL"
    if not is_tuple_of(value.skipped_steps, ExecutionStep):
        return "ExecutionDiagnostics.skipped_steps must be a tuple of ExecutionStep"
    leftovers = value.leftover_temporaries
    if type(leftovers) is not tuple or len(leftovers) > MAX_LEFTOVER_TEMPORARIES_PER_ITEM:
        return "ExecutionDiagnostics.leftover_temporaries must be a tuple of at most MAX_LEFTOVER_TEMPORARIES_PER_ITEM items"
    for leftover in leftovers:
        problem = leftover_problem(leftover)
        if problem is not None:
            return problem
    if not is_int(value.leftover_temporary_count) or value.leftover_temporary_count != len(leftovers):
        return "ExecutionDiagnostics.leftover_temporary_count must equal len(leftover_temporaries)"
    return None


# --------------------------------------------------------------------------- ItemDiagnostics (11.3)


@dataclass(frozen=True, slots=True)
class ItemDiagnostics:
    index: int
    generation: int
    canonical_number: str | None
    source_name: str | None
    source_size: int
    target_directory_name: str | None
    target_media_name: str | None
    preview_state: PreviewState
    issue: IssueDiagnostics | None
    warnings: tuple[ItemWarning, ...]
    conflict_with: tuple[int, ...]
    retry_origin: RetryKind | None
    disposition: ExecutionDisposition | None
    retry_kind: RetryKind | None
    retry_material_retained: bool | None
    metadata: MetadataDiagnostics | None
    image_failures: tuple[ImageFailureGroup, ...]
    preflight: PreflightDiagnostics | None
    execution: ExecutionDiagnostics | None

    def __post_init__(self) -> None:
        _raise(item_problem(self))


def item_problem(value: object) -> str | None:
    if type(value) is not ItemDiagnostics:
        return "items must be exact ItemDiagnostics values"
    if not is_int(value.index) or not is_int(value.generation):
        return "ItemDiagnostics.index / generation must be exact ints >= 0"
    if not is_int(value.source_size):
        return "ItemDiagnostics.source_size must be an exact int >= 0"
    if type(value.preview_state) is not PreviewState:
        return "ItemDiagnostics.preview_state must be a PreviewState"
    issue = value.issue
    if issue is not None:
        problem = issue_problem(issue)
        if problem is not None:
            return problem
    unrecognized = issue is not None and issue.reason is IssueReason.NUMBER_NOT_RECOGNIZED
    number = value.canonical_number
    if (number is None) != unrecognized:
        return "ItemDiagnostics.canonical_number is None iff the issue is NUMBER_NOT_RECOGNIZED"
    if number is not None and (type(number) is not str or not is_valid_fc2_number(number)):
        return "ItemDiagnostics.canonical_number must be a canonical FC2 number"
    if (not is_opt_safe_basename(value.source_name) or not is_opt_safe_basename(value.target_directory_name)
            or not is_opt_safe_basename(value.target_media_name)):
        return "ItemDiagnostics path-derived names must be None or a safe basename"
    if not is_unique_ordered_enum_tuple(value.warnings, ItemWarning):
        return "ItemDiagnostics.warnings must be unique and in ItemWarning declaration order"
    conflicts = value.conflict_with
    if type(conflicts) is not tuple or not strictly_increasing_ints(conflicts):
        return "ItemDiagnostics.conflict_with must be strictly increasing exact ints >= 0"
    if value.index in conflicts:
        return "ItemDiagnostics.conflict_with never contains the item's own index"
    origin = value.retry_origin
    if origin is not None and (type(origin) is not RetryKind or origin is RetryKind.NONE):
        return "ItemDiagnostics.retry_origin must be a RetryKind other than NONE"
    if value.disposition is None:
        if value.retry_kind is not None or value.retry_material_retained is not None or value.execution is not None:
            return "ItemDiagnostics.disposition / retry_kind / retry_material_retained are set together"
    else:
        if type(value.disposition) is not ExecutionDisposition:
            return "ItemDiagnostics.disposition must be an ExecutionDisposition"
        if type(value.retry_kind) is not RetryKind or not is_bool(value.retry_material_retained):
            return "ItemDiagnostics.disposition / retry_kind / retry_material_retained are set together"
        if (value.execution is not None) != (value.disposition is ExecutionDisposition.EXECUTED):
            return "ItemDiagnostics.execution is present iff the disposition is EXECUTED"
    if value.metadata is not None:
        problem = metadata_problem(value.metadata)
        if problem is not None:
            return problem
    groups = value.image_failures
    if type(groups) is not tuple:
        return "ItemDiagnostics.image_failures must be a tuple"
    seen_roles_kinds: list[tuple[ImageRole, ImageFailureKind]] = []
    for group in groups:
        problem = image_failure_group_problem(group)
        if problem is not None:
            return problem
        seen_roles_kinds.append((group.role, group.kind))
    expected_order = [(role, kind) for role in ImageRole for kind in ImageFailureKind if (role, kind) in seen_roles_kinds]
    if expected_order != seen_roles_kinds:
        return "ItemDiagnostics.image_failures must be unique per (role, kind) in declaration order"
    if value.preflight is not None:
        problem = preflight_problem(value.preflight)
        if problem is not None:
            return problem
    if value.execution is not None:
        problem = execution_problem(value.execution)
        if problem is not None:
            return problem
    return None


# --------------------------------------------------------------------------- BatchDiagnostics (11.1)


@dataclass(frozen=True, slots=True)
class BatchDiagnostics:
    kind: DiagnosticsKind
    shape: ResultShape
    generation: int
    batch_size: int
    retry_scope: tuple[RetryKind, ...] | None
    path_policy: PathPolicy
    timing_policy: TimingPolicy
    metadata_batch: MetadataBatchCounts
    preview_summary: PreviewSummary | None
    execution_summary: ExecutionSummary | None
    outcome: BatchOutcome | None
    items: tuple[ItemDiagnostics, ...]

    def __post_init__(self) -> None:
        _raise(batch_problem(self))


def _item_kind_problem(item: ItemDiagnostics, kind: DiagnosticsKind) -> str | None:
    """Contract section 10 applicability table for one item."""
    if kind is DiagnosticsKind.PREVIEW:
        if (item.disposition is not None or item.retry_kind is not None or item.retry_material_retained is not None
                or item.execution is not None):
            return "a PREVIEW item has no disposition / retry_kind / retry_material_retained / execution"
        return None
    if (item.retry_origin is not None or item.preflight is not None or item.disposition is None):
        return "an EXECUTION item has no retry_origin / preflight and always has its disposition"
    return None


def _policy_problem(item: ItemDiagnostics, path_policy: PathPolicy, timing_policy: TimingPolicy) -> str | None:
    leftovers = () if item.execution is None else item.execution.leftover_temporaries
    if path_policy is PathPolicy.NONE:
        if (item.source_name is not None or item.target_directory_name is not None
                or item.target_media_name is not None):
            return "with PathPolicy.NONE every path-derived text is None"
        for leftover in leftovers:
            if leftover.name is not None:
                return "with PathPolicy.NONE every path-derived text is None"
    else:
        if item.source_name is None:
            return "with PathPolicy.BASENAME the source name is present"
        for leftover in leftovers:
            if leftover.name is None:
                return "with PathPolicy.BASENAME every leftover temporary name is present"
    metadata = item.metadata
    if metadata is not None:
        published = timing_policy is TimingPolicy.INCLUDE
        if (metadata.elapsed_ms is not None) != published:
            return "MetadataDiagnostics.elapsed_ms is None iff TimingPolicy.OMIT"
        for source in metadata.sources:
            for attempt in source.attempts:
                if (attempt.elapsed_ms is not None) != published:
                    return "attempt timings are None iff TimingPolicy.OMIT"
    return None


def batch_problem(value: object) -> str | None:
    if type(value) is not BatchDiagnostics:
        return "diagnostics must be an exact BatchDiagnostics"
    if type(value.kind) is not DiagnosticsKind or type(value.shape) is not ResultShape:
        return "BatchDiagnostics.kind / shape must be enum members"
    if value.kind is DiagnosticsKind.PREVIEW and value.shape is ResultShape.MERGED:
        return "a PREVIEW is never MERGED"
    if not is_int(value.generation) or (value.generation == 0) != (value.shape is ResultShape.MAIN):
        return "BatchDiagnostics.generation is 0 iff the shape is MAIN"
    if not is_int(value.batch_size) or value.batch_size > MAX_DIAGNOSTIC_ITEMS:
        return "BatchDiagnostics.batch_size must be an exact int in 0..MAX_DIAGNOSTIC_ITEMS"
    scope = value.retry_scope
    if value.shape is ResultShape.RETRY:
        if scope is None or not is_unique_ordered_enum_tuple(scope, RetryKind) or RetryKind.NONE in scope:
            return "a RETRY BatchDiagnostics has a unique, ordered retry_scope without NONE"
    elif scope is not None:
        return "only a RETRY BatchDiagnostics has a retry_scope"
    if type(value.path_policy) is not PathPolicy or type(value.timing_policy) is not TimingPolicy:
        return "BatchDiagnostics.path_policy / timing_policy must be enum members"
    problem = metadata_batch_counts_problem(value.metadata_batch)
    if problem is not None:
        return problem
    if value.kind is DiagnosticsKind.PREVIEW:
        if value.execution_summary is not None or value.outcome is not None:
            return "a PREVIEW has no execution_summary / outcome"
        problem = preview_summary_problem(value.preview_summary)
        if problem is not None:
            return problem
        total = value.preview_summary.total
    else:
        if value.preview_summary is not None:
            return "an EXECUTION has no preview_summary"
        if type(value.outcome) is not BatchOutcome:
            return "an EXECUTION has an outcome"
        problem = execution_summary_problem(value.execution_summary)
        if problem is not None:
            return problem
        total = value.execution_summary.total
    items = value.items
    if type(items) is not tuple or len(items) > value.batch_size:
        return "BatchDiagnostics.items must be a tuple of at most batch_size items"
    for item in items:
        problem = item_problem(item)
        if problem is not None:
            return problem
    if total != len(items):
        return "the summary total must equal len(items)"
    indices = tuple(item.index for item in items)
    if not strictly_increasing_ints(indices) or (len(indices) != 0 and indices[-1] >= value.batch_size):
        return "BatchDiagnostics.items indices must strictly increase and stay below batch_size"
    if value.shape is not ResultShape.RETRY and indices != tuple(range(value.batch_size)):
        return "a MAIN / MERGED BatchDiagnostics covers indices 0..batch_size-1"
    for item in items:
        problem = _item_kind_problem(item, value.kind)
        if problem is not None:
            return problem
        if value.kind is DiagnosticsKind.EXECUTION and value.shape is ResultShape.MERGED:
            if item.generation > value.generation:
                return "a MERGED item generation is at most the result generation"
        elif item.generation != value.generation:
            return "every item carries the diagnostics generation"
        problem = _policy_problem(item, value.path_policy, value.timing_policy)
        if problem is not None:
            return problem
    return None
