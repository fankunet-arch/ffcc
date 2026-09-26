"""Immutable value models for ``fc2_organizer.execution`` (P4-C7).

Every model is a frozen, ``slots=True`` dataclass validated by exact type in
``__post_init__`` (``ExecutionModelError``); ``bool`` never counts as ``int`` and no
subclass of ``str`` / ``int`` / ``tuple`` / an enum / a model ever passes.

Besides the standard library and this package's ``errors``, this module imports the
two bare public packages the execution package is authorised to consume
(``fc2_organizer.planning``, ``fc2_organizer.materialization``) -- only so that the
strict-type invariants of ``ExecutionPreflight.plan`` / ``.artifacts`` and of every
``artifact_kind`` field (contract sections 16, 27) can be enforced at the model
layer. It never imports their submodules.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum

from fc2_organizer.execution.errors import ExecutionModelError
from fc2_organizer.materialization import ArtifactKind, ArtifactWriteRequest
from fc2_organizer.planning import OrganizePlan

__all__ = [
    "ExecutionStatus",
    "ExecutionStep",
    "EffectKind",
    "EntryType",
    "PathRole",
    "PreflightMode",
    "TransferMode",
    "TransferStage",
    "PreflightBlockReason",
    "ExecutionFailureKind",
    "EntryIdentity",
    "ExecutionUnit",
    "CompletedEffect",
    "LeftoverTemporary",
    "PreflightBlocker",
    "ExecutionFailure",
    "ExecutionCheckpoint",
    "ExecutionPreflight",
    "ExecutionResult",
    "ExpectedEffect",
    "same_identity",
]

_HEX32 = re.compile(r"[0-9a-f]{32}")
_HEX64 = re.compile(r"[0-9a-f]{64}")
_TEMP_NAME = re.compile(r"\.fc2tmp-[0-9a-f]{32}\.part")


# --------------------------------------------------------------------------- enums


class ExecutionStatus(Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"


class ExecutionStep(Enum):
    CREATE_DIRECTORY = "create_directory"
    MOVE_MEDIA = "move_media"
    MATERIALIZE_NFO = "materialize_nfo"
    MATERIALIZE_POSTER = "materialize_poster"
    MATERIALIZE_FANART = "materialize_fanart"
    MATERIALIZE_THUMB = "materialize_thumb"
    ENSURE_EXTRAFANART_DIRECTORY = "ensure_extrafanart_directory"
    MATERIALIZE_EXTRAFANART = "materialize_extrafanart"


class EffectKind(Enum):
    TARGET_DIRECTORY_CREATED = "target_directory_created"
    MEDIA_PUBLISHED = "media_published"
    SOURCE_REMOVED = "source_removed"
    ARTIFACT_PUBLISHED = "artifact_published"
    EXTRAFANART_DIRECTORY_CREATED = "extrafanart_directory_created"


class EntryType(Enum):
    FILE = "file"
    DIRECTORY = "directory"


class PathRole(Enum):
    LIBRARY_ROOT = "library_root"
    SOURCE = "source"
    TARGET_DIRECTORY = "target_directory"
    TARGET_MEDIA = "target_media"
    NFO = "nfo"
    POSTER = "poster"
    FANART = "fanart"
    THUMB = "thumb"
    EXTRAFANART_DIRECTORY = "extrafanart_directory"
    EXTRAFANART_FILE = "extrafanart_file"


class PreflightMode(Enum):
    FRESH = "fresh"
    RESUME = "resume"


class TransferMode(Enum):
    SAME_VOLUME = "same_volume"
    CROSS_VOLUME = "cross_volume"


class TransferStage(Enum):
    SOURCE_OPEN = "source_open"
    SOURCE_FD_VALIDATE = "source_fd_validate"
    TEMP_CREATE = "temp_create"
    READ = "read"
    WRITE = "write"
    FSYNC = "fsync"
    CLOSE = "close"
    SOURCE_FD_REVALIDATE = "source_fd_revalidate"
    PUBLISH = "publish"
    PUBLISH_VERIFY = "publish_verify"
    TEMP_CLEANUP = "temp_cleanup"
    DIRECTORY_FSYNC = "directory_fsync"
    SOURCE_PATH_REVALIDATE = "source_path_revalidate"
    SOURCE_UNLINK = "source_unlink"
    SAME_VOLUME_PRIMITIVE = "same_volume_primitive"


class PreflightBlockReason(Enum):
    LIBRARY_ROOT_MISSING = "library_root_missing"
    LIBRARY_ROOT_NOT_DIRECTORY = "library_root_not_directory"
    LIBRARY_ROOT_IS_LINK = "library_root_is_link"
    LIBRARY_ROOT_INACCESSIBLE = "library_root_inaccessible"
    LIBRARY_ROOT_CHANGED = "library_root_changed"
    SOURCE_MISSING = "source_missing"
    SOURCE_IS_LINK = "source_is_link"
    SOURCE_NOT_REGULAR_FILE = "source_not_regular_file"
    SOURCE_SIZE_MISMATCH = "source_size_mismatch"
    SOURCE_INACCESSIBLE = "source_inaccessible"
    SOURCE_CHANGED = "source_changed"
    TARGET_DIRECTORY_EXISTS = "target_directory_exists"
    TARGET_DIRECTORY_INACCESSIBLE = "target_directory_inaccessible"
    TARGET_DIRECTORY_CHANGED = "target_directory_changed"
    UNEXPECTED_ENTRY = "unexpected_entry"
    COMPLETED_EFFECT_MISSING = "completed_effect_missing"
    COMPLETED_EFFECT_CHANGED = "completed_effect_changed"
    IDENTITY_UNAVAILABLE = "identity_unavailable"


class ExecutionFailureKind(Enum):
    LIBRARY_ROOT_CHANGED = "library_root_changed"
    SOURCE_CHANGED = "source_changed"
    SOURCE_MISSING = "source_missing"
    TARGET_DIRECTORY_CHANGED = "target_directory_changed"
    UNEXPECTED_ENTRY = "unexpected_entry"
    TARGET_CONFLICT = "target_conflict"
    DIRECTORY_CREATE_FAILED = "directory_create_failed"
    MEDIA_TRANSFER_FAILED = "media_transfer_failed"
    MEDIA_SOURCE_OPEN_FAILED = "media_source_open_failed"
    MEDIA_READ_FAILED = "media_read_failed"
    MEDIA_TEMP_CREATE_FAILED = "media_temp_create_failed"
    MEDIA_WRITE_FAILED = "media_write_failed"
    MEDIA_FSYNC_FAILED = "media_fsync_failed"
    MEDIA_CLOSE_FAILED = "media_close_failed"
    SOURCE_CHANGED_DURING_COPY = "source_changed_during_copy"
    MEDIA_PUBLISH_FAILED = "media_publish_failed"
    MEDIA_TEMP_CLEANUP_FAILED = "media_temp_cleanup_failed"
    PUBLISHED_MEDIA_MISMATCH = "published_media_mismatch"
    TARGET_DIRECTORY_FSYNC_FAILED = "target_directory_fsync_failed"
    SOURCE_UNLINK_FAILED = "source_unlink_failed"
    ARTIFACT_TARGET_INACCESSIBLE = "artifact_target_inaccessible"
    ARTIFACT_TEMP_CREATE_FAILED = "artifact_temp_create_failed"
    ARTIFACT_WRITE_FAILED = "artifact_write_failed"
    ARTIFACT_PUBLISH_FAILED = "artifact_publish_failed"
    ARTIFACT_CLEANUP_FAILED = "artifact_cleanup_failed"
    ARTIFACT_PATH_REJECTED = "artifact_path_rejected"
    PUBLISHED_ARTIFACT_MISMATCH = "published_artifact_mismatch"


# The closed set of enum types the canonical encoding (``seal.encode``) accepts.
ENCODABLE_ENUMS: tuple[type[Enum], ...] = (
    ExecutionStatus, ExecutionStep, EffectKind, EntryType, PathRole, PreflightMode, TransferMode,
    TransferStage, PreflightBlockReason, ExecutionFailureKind, ArtifactKind,
)


# --------------------------------------------------------------------------- strict helpers


def _fail(message: str) -> None:
    raise ExecutionModelError(message)


def _is_int(value: object, minimum: int | None = None) -> bool:
    return type(value) is int and (minimum is None or value >= minimum)


def _opt_int(value: object, minimum: int | None = None) -> bool:
    return value is None or _is_int(value, minimum)


def _is_str(value: object) -> bool:
    return type(value) is str and bool(value)


def _is_hex(value: object, pattern: re.Pattern[str]) -> bool:
    return type(value) is str and pattern.fullmatch(value) is not None


def _is_member(value: object, enum_type: type[Enum]) -> bool:
    return type(value) is enum_type


def _opt_member(value: object, enum_type: type[Enum]) -> bool:
    return value is None or type(value) is enum_type


def _is_tuple_of(value: object, item_type: type) -> bool:
    return type(value) is tuple and all(type(item) is item_type for item in value)


# --------------------------------------------------------------------------- identity


@dataclass(frozen=True, slots=True)
class EntryIdentity:
    """One ``lstat`` snapshot (contract section 12). ``size`` / ``mtime_ns`` iff FILE."""

    device: int
    inode: int
    entry_type: EntryType
    size: int | None
    mtime_ns: int | None

    def __post_init__(self) -> None:
        if not _is_int(self.device, 0):
            _fail("EntryIdentity.device must be an exact int >= 0")
        if not _is_int(self.inode, 1):
            _fail("EntryIdentity.inode must be an exact int >= 1")
        if not _is_member(self.entry_type, EntryType):
            _fail("EntryIdentity.entry_type must be an EntryType")
        if self.entry_type is EntryType.FILE:
            if not _is_int(self.size, 0) or not _is_int(self.mtime_ns):
                _fail("a FILE identity needs exact int size >= 0 and exact int mtime_ns")
        elif self.size is not None or self.mtime_ns is not None:
            _fail("a DIRECTORY identity carries neither size nor mtime_ns")


def same_identity(a: EntryIdentity, b: EntryIdentity) -> bool:
    """Contract section 12: files compare all five fields, directories device/inode/type."""
    if type(a) is not EntryIdentity or type(b) is not EntryIdentity:
        return False
    if (a.device, a.inode, a.entry_type) != (b.device, b.inode, b.entry_type):
        return False
    if a.entry_type is EntryType.FILE:
        return (a.size, a.mtime_ns) == (b.size, b.mtime_ns)
    return True


# --------------------------------------------------------------------------- units / effects

_UNIT_SHAPES: dict[ExecutionStep, tuple[PathRole, ArtifactKind | None]] = {
    ExecutionStep.CREATE_DIRECTORY: (PathRole.TARGET_DIRECTORY, None),
    ExecutionStep.MOVE_MEDIA: (PathRole.TARGET_MEDIA, None),
    ExecutionStep.MATERIALIZE_NFO: (PathRole.NFO, ArtifactKind.NFO),
    ExecutionStep.MATERIALIZE_POSTER: (PathRole.POSTER, ArtifactKind.POSTER),
    ExecutionStep.MATERIALIZE_FANART: (PathRole.FANART, ArtifactKind.FANART),
    ExecutionStep.MATERIALIZE_THUMB: (PathRole.THUMB, ArtifactKind.THUMB),
    ExecutionStep.ENSURE_EXTRAFANART_DIRECTORY: (PathRole.EXTRAFANART_DIRECTORY, None),
    ExecutionStep.MATERIALIZE_EXTRAFANART: (PathRole.EXTRAFANART_FILE, ArtifactKind.EXTRAFANART),
}

_ARTIFACT_ROLE: dict[ArtifactKind, PathRole] = {
    ArtifactKind.NFO: PathRole.NFO,
    ArtifactKind.POSTER: PathRole.POSTER,
    ArtifactKind.FANART: PathRole.FANART,
    ArtifactKind.THUMB: PathRole.THUMB,
    ArtifactKind.EXTRAFANART: PathRole.EXTRAFANART_FILE,
}


def _ordinal_ok(artifact_kind: object, ordinal: object) -> bool:
    if artifact_kind is ArtifactKind.EXTRAFANART:
        return _is_int(ordinal, 1)
    return ordinal is None


@dataclass(frozen=True, slots=True)
class ExecutionUnit:
    """One ordered execution unit (contract section 9), used for preview."""

    step: ExecutionStep
    role: PathRole
    artifact_kind: ArtifactKind | None
    ordinal: int | None

    def __post_init__(self) -> None:
        if not _is_member(self.step, ExecutionStep):
            _fail("ExecutionUnit.step must be an ExecutionStep")
        if not _is_member(self.role, PathRole) or not _opt_member(self.artifact_kind, ArtifactKind):
            _fail("ExecutionUnit.role / artifact_kind must be enum members")
        role, artifact_kind = _UNIT_SHAPES[self.step]
        if self.role is not role or self.artifact_kind is not artifact_kind:
            _fail("ExecutionUnit.role / artifact_kind do not match its step")
        if not _ordinal_ok(self.artifact_kind, self.ordinal):
            _fail("ExecutionUnit.ordinal must be an exact int >= 1 iff the unit is an extrafanart file")


@dataclass(frozen=True, slots=True)
class CompletedEffect:
    """One final filesystem effect (contract section 14.2)."""

    kind: EffectKind
    role: PathRole
    path: str
    identity: EntryIdentity | None
    size: int | None
    sha256: str | None
    artifact_kind: ArtifactKind | None
    ordinal: int | None

    def __post_init__(self) -> None:
        if not _is_member(self.kind, EffectKind) or not _is_member(self.role, PathRole):
            _fail("CompletedEffect.kind / role must be enum members")
        if not _is_str(self.path):
            _fail("CompletedEffect.path must be a non-empty exact str")
        if not _opt_member(self.artifact_kind, ArtifactKind):
            _fail("CompletedEffect.artifact_kind must be an ArtifactKind or None")
        if self.sha256 is not None and not _is_hex(self.sha256, _HEX64):
            _fail("CompletedEffect.sha256 must be 64 lowercase hex characters or None")
        if not _opt_int(self.size, 0):
            _fail("CompletedEffect.size must be an exact int >= 0 or None")
        kind = self.kind
        if kind is EffectKind.ARTIFACT_PUBLISHED:
            if self.artifact_kind is None or self.role is not _ARTIFACT_ROLE[self.artifact_kind]:
                _fail("an ARTIFACT_PUBLISHED effect needs an artifact_kind matching its role")
            if self.sha256 is None or self.size is None:
                _fail("an ARTIFACT_PUBLISHED effect records size and sha256")
            if not _ordinal_ok(self.artifact_kind, self.ordinal):
                _fail("CompletedEffect.ordinal must be set iff the artifact is an extrafanart file")
            self._require_identity(EntryType.FILE)
            return
        if self.artifact_kind is not None or self.ordinal is not None:
            _fail("only ARTIFACT_PUBLISHED effects carry artifact_kind / ordinal")
        if kind is EffectKind.SOURCE_REMOVED:
            if self.role is not PathRole.SOURCE or self.identity is not None:
                _fail("a SOURCE_REMOVED effect has role SOURCE and no identity")
            if self.size is not None or self.sha256 is not None:
                _fail("a SOURCE_REMOVED effect carries no size / sha256")
        elif kind is EffectKind.MEDIA_PUBLISHED:
            if self.role is not PathRole.TARGET_MEDIA or self.size is None:
                _fail("a MEDIA_PUBLISHED effect has role TARGET_MEDIA and a size")
            self._require_identity(EntryType.FILE)
        else:
            expected_role = (PathRole.TARGET_DIRECTORY if kind is EffectKind.TARGET_DIRECTORY_CREATED
                             else PathRole.EXTRAFANART_DIRECTORY)
            if self.role is not expected_role or self.size is not None or self.sha256 is not None:
                _fail("a directory effect has its directory role and no size / sha256")
            self._require_identity(EntryType.DIRECTORY)

    def _require_identity(self, entry_type: EntryType) -> None:
        if type(self.identity) is not EntryIdentity or self.identity.entry_type is not entry_type:
            _fail(f"this effect needs a {entry_type.value} EntryIdentity")


@dataclass(frozen=True, slots=True)
class ExpectedEffect:
    """One slot of the deterministic expected effect sequence E(plan, manifest) (contract
    section 9). Internal: derived by ``validation.expected_effects``; not public API."""

    kind: EffectKind
    role: PathRole
    path: str
    artifact_kind: ArtifactKind | None
    ordinal: int | None

    def __post_init__(self) -> None:
        if not _is_member(self.kind, EffectKind) or not _is_member(self.role, PathRole):
            _fail("ExpectedEffect.kind / role must be enum members")
        if not _is_str(self.path) or not _opt_member(self.artifact_kind, ArtifactKind):
            _fail("ExpectedEffect.path must be a non-empty exact str")
        if not _ordinal_ok(self.artifact_kind, self.ordinal):
            _fail("ExpectedEffect.ordinal must be set iff the artifact is an extrafanart file")


@dataclass(frozen=True, slots=True)
class LeftoverTemporary:
    """A temporary file left behind after a failed cleanup; never deleted by P4-C7."""

    directory_role: PathRole
    name: str

    def __post_init__(self) -> None:
        if type(self.directory_role) is not PathRole or self.directory_role not in (
                PathRole.TARGET_DIRECTORY, PathRole.EXTRAFANART_DIRECTORY):
            _fail("LeftoverTemporary.directory_role must be TARGET_DIRECTORY or EXTRAFANART_DIRECTORY")
        if type(self.name) is not str or _TEMP_NAME.fullmatch(self.name) is None:
            _fail("LeftoverTemporary.name must match .fc2tmp-<32 hex>.part")


@dataclass(frozen=True, slots=True)
class PreflightBlocker:
    """One filesystem-state reason a preflight is not ready. Carries no path text."""

    reason: PreflightBlockReason
    role: PathRole
    errno: int | None = None
    ordinal: int | None = None

    def __post_init__(self) -> None:
        if not _is_member(self.reason, PreflightBlockReason) or not _is_member(self.role, PathRole):
            _fail("PreflightBlocker.reason / role must be enum members")
        if not _opt_int(self.errno) or not _opt_int(self.ordinal, 1):
            _fail("PreflightBlocker.errno / ordinal must be exact ints or None")


_WRITE_STAGES = (None, "write", "flush", "close")
_CLEANUP_KINDS = (ExecutionFailureKind.ARTIFACT_CLEANUP_FAILED, ExecutionFailureKind.MEDIA_TEMP_CLEANUP_FAILED)


@dataclass(frozen=True, slots=True)
class ExecutionFailure:
    """The typed failure that stopped an execution (contract section 27)."""

    step: ExecutionStep
    kind: ExecutionFailureKind
    stage: TransferStage | None = None
    write_stage: str | None = None
    errno: int | None = None
    artifact_kind: ArtifactKind | None = None
    ordinal: int | None = None
    target_published: bool | None = None

    def __post_init__(self) -> None:
        if not _is_member(self.step, ExecutionStep) or not _is_member(self.kind, ExecutionFailureKind):
            _fail("ExecutionFailure.step / kind must be enum members")
        if not _opt_member(self.stage, TransferStage) or not _opt_member(self.artifact_kind, ArtifactKind):
            _fail("ExecutionFailure.stage / artifact_kind must be enum members or None")
        if (type(self.write_stage) not in (type(None), str) or self.write_stage not in _WRITE_STAGES
                or (self.write_stage is not None and self.kind is not ExecutionFailureKind.ARTIFACT_WRITE_FAILED)):
            _fail("ExecutionFailure.write_stage is write/flush/close and only for ARTIFACT_WRITE_FAILED")
        if not _opt_int(self.errno):
            _fail("ExecutionFailure.errno must be an exact int or None")
        ordinal_allowed = self.artifact_kind is ArtifactKind.EXTRAFANART
        if not (_opt_int(self.ordinal, 1) and (ordinal_allowed or self.ordinal is None)):
            _fail("ExecutionFailure.ordinal must be an exact int >= 1 and only for extrafanart")
        if self.target_published is not None and (
                type(self.target_published) is not bool or self.kind not in _CLEANUP_KINDS):
            _fail("ExecutionFailure.target_published is a bool and only for cleanup failures")


# --------------------------------------------------------------------------- checkpoint / preflight / result


@dataclass(frozen=True, slots=True)
class ExecutionCheckpoint:
    """Immutable, sealed, in-process checkpoint (contract section 14.2). Issued only by
    ``execute_filesystem``; S1 defines and validates the model but never issues one."""

    checkpoint_id: str
    plan_fingerprint: str
    manifest_fingerprint: str
    library_root_identity: EntryIdentity
    source_identity: EntryIdentity
    transfer_mode: TransferMode
    target_directory_identity: EntryIdentity
    extrafanart_directory_identity: EntryIdentity | None
    completed_effects: tuple[CompletedEffect, ...]
    leftover_temporaries: tuple[LeftoverTemporary, ...]
    seal: str = field(repr=False)

    def __post_init__(self) -> None:
        if not _is_hex(self.checkpoint_id, _HEX32):
            _fail("ExecutionCheckpoint.checkpoint_id must be 32 lowercase hex characters")
        if not _is_hex(self.plan_fingerprint, _HEX64) or not _is_hex(self.manifest_fingerprint, _HEX64):
            _fail("ExecutionCheckpoint fingerprints must be 64 lowercase hex characters")
        _require_identity(self.library_root_identity, EntryType.DIRECTORY, "library_root_identity")
        _require_identity(self.source_identity, EntryType.FILE, "source_identity")
        _require_identity(self.target_directory_identity, EntryType.DIRECTORY, "target_directory_identity")
        if self.extrafanart_directory_identity is not None:
            _require_identity(self.extrafanart_directory_identity, EntryType.DIRECTORY,
                              "extrafanart_directory_identity")
        if not _is_member(self.transfer_mode, TransferMode):
            _fail("ExecutionCheckpoint.transfer_mode must be a TransferMode")
        if not _is_tuple_of(self.completed_effects, CompletedEffect) or not self.completed_effects:
            _fail("ExecutionCheckpoint.completed_effects must be a non-empty tuple[CompletedEffect, ...]")
        if not _is_tuple_of(self.leftover_temporaries, LeftoverTemporary):
            _fail("ExecutionCheckpoint.leftover_temporaries must be a tuple[LeftoverTemporary, ...]")
        if not _is_hex(self.seal, _HEX64):
            _fail("ExecutionCheckpoint.seal must be 64 lowercase hex characters")


def _require_identity(value: object, entry_type: EntryType, name: str) -> None:
    if type(value) is not EntryIdentity or value.entry_type is not entry_type:
        _fail(f"{name} must be a {entry_type.value} EntryIdentity")


_OPTIONAL_STEPS = (ExecutionStep.MATERIALIZE_POSTER, ExecutionStep.MATERIALIZE_FANART,
                   ExecutionStep.MATERIALIZE_THUMB)


@dataclass(frozen=True, slots=True)
class ExecutionPreflight:
    """The sealed, immutable result of ``preflight_execution`` (contract section 16).

    ``plan`` / ``artifacts`` are the caller's own objects; the seal covers their
    fingerprints, and the executor re-validates and re-fingerprints them before any
    filesystem access (contract section 15.5).
    """

    preflight_id: str
    mode: PreflightMode
    plan: OrganizePlan
    artifacts: tuple[ArtifactWriteRequest, ...]
    checkpoint: ExecutionCheckpoint | None
    plan_fingerprint: str
    manifest_fingerprint: str
    ready: bool
    blockers: tuple[PreflightBlocker, ...]
    library_root_identity: EntryIdentity | None
    source_identity: EntryIdentity | None
    transfer_mode: TransferMode | None
    completed_units: tuple[ExecutionUnit, ...]
    pending_units: tuple[ExecutionUnit, ...]
    skipped_steps: tuple[ExecutionStep, ...]
    seal: str = field(repr=False)

    def __post_init__(self) -> None:
        if not _is_hex(self.preflight_id, _HEX32):
            _fail("ExecutionPreflight.preflight_id must be 32 lowercase hex characters")
        if not _is_member(self.mode, PreflightMode):
            _fail("ExecutionPreflight.mode must be a PreflightMode")
        if type(self.plan) is not OrganizePlan:
            _fail("ExecutionPreflight.plan must be an exact OrganizePlan")
        if not _is_tuple_of(self.artifacts, ArtifactWriteRequest):
            _fail("ExecutionPreflight.artifacts must be a tuple[ArtifactWriteRequest, ...]")
        if self.checkpoint is not None and type(self.checkpoint) is not ExecutionCheckpoint:
            _fail("ExecutionPreflight.checkpoint must be an ExecutionCheckpoint or None")
        if (self.mode is PreflightMode.RESUME) != (self.checkpoint is not None):
            _fail("ExecutionPreflight.mode is RESUME iff a checkpoint is present")
        if not _is_hex(self.plan_fingerprint, _HEX64) or not _is_hex(self.manifest_fingerprint, _HEX64):
            _fail("ExecutionPreflight fingerprints must be 64 lowercase hex characters")
        if type(self.ready) is not bool or not _is_tuple_of(self.blockers, PreflightBlocker):
            _fail("ExecutionPreflight.ready must be a bool and blockers a tuple[PreflightBlocker, ...]")
        if self.ready != (self.blockers == ()):
            _fail("ExecutionPreflight.ready must be True iff there are no blockers")
        if self.library_root_identity is not None:
            _require_identity(self.library_root_identity, EntryType.DIRECTORY, "library_root_identity")
        if self.source_identity is not None:
            _require_identity(self.source_identity, EntryType.FILE, "source_identity")
        if not _opt_member(self.transfer_mode, TransferMode):
            _fail("ExecutionPreflight.transfer_mode must be a TransferMode or None")
        if not _is_tuple_of(self.completed_units, ExecutionUnit) or not _is_tuple_of(self.pending_units,
                                                                                       ExecutionUnit):
            _fail("ExecutionPreflight units must be tuple[ExecutionUnit, ...]")
        if not _is_tuple_of(self.skipped_steps, ExecutionStep) or any(
                step not in _OPTIONAL_STEPS for step in self.skipped_steps):
            _fail("ExecutionPreflight.skipped_steps may only name optional image steps")
        if not _is_hex(self.seal, _HEX64):
            _fail("ExecutionPreflight.seal must be 64 lowercase hex characters")


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    """What one ``execute_filesystem`` call left on disk (contract section 27)."""

    status: ExecutionStatus
    preflight_id: str
    mode: PreflightMode
    transfer_mode: TransferMode | None
    completed_effects: tuple[CompletedEffect, ...]
    new_effect_count: int
    failure: ExecutionFailure | None
    checkpoint: ExecutionCheckpoint | None
    leftover_temporaries: tuple[LeftoverTemporary, ...]
    media_sha256: str | None
    skipped_steps: tuple[ExecutionStep, ...]

    def __post_init__(self) -> None:
        if not _is_member(self.status, ExecutionStatus) or not _is_member(self.mode, PreflightMode):
            _fail("ExecutionResult.status / mode must be enum members")
        if not _is_hex(self.preflight_id, _HEX32):
            _fail("ExecutionResult.preflight_id must be 32 lowercase hex characters")
        if not _opt_member(self.transfer_mode, TransferMode):
            _fail("ExecutionResult.transfer_mode must be a TransferMode or None")
        if not _is_tuple_of(self.completed_effects, CompletedEffect):
            _fail("ExecutionResult.completed_effects must be a tuple[CompletedEffect, ...]")
        if not _is_int(self.new_effect_count, 0) or self.new_effect_count > len(self.completed_effects):
            _fail("ExecutionResult.new_effect_count must be an exact int in [0, len(completed_effects)]")
        if self.failure is not None and type(self.failure) is not ExecutionFailure:
            _fail("ExecutionResult.failure must be an ExecutionFailure or None")
        if self.checkpoint is not None and type(self.checkpoint) is not ExecutionCheckpoint:
            _fail("ExecutionResult.checkpoint must be an ExecutionCheckpoint or None")
        if (self.status is ExecutionStatus.SUCCESS) != (self.failure is None):
            _fail("ExecutionResult.failure must be present iff status is not SUCCESS")
        if (self.status is ExecutionStatus.PARTIAL) != (self.checkpoint is not None):
            _fail("ExecutionResult.checkpoint must be present iff status is PARTIAL")
        if self.status is ExecutionStatus.FAILED and self.completed_effects:
            _fail("a FAILED result has no completed effects")
        if self.status is not ExecutionStatus.FAILED and not self.completed_effects:
            _fail("a SUCCESS / PARTIAL result has at least one completed effect")
        if not _is_tuple_of(self.leftover_temporaries, LeftoverTemporary):
            _fail("ExecutionResult.leftover_temporaries must be a tuple[LeftoverTemporary, ...]")
        if self.media_sha256 is not None and not _is_hex(self.media_sha256, _HEX64):
            _fail("ExecutionResult.media_sha256 must be 64 lowercase hex characters or None")
        if not _is_tuple_of(self.skipped_steps, ExecutionStep) or any(
                step not in _OPTIONAL_STEPS for step in self.skipped_steps):
            _fail("ExecutionResult.skipped_steps may only name optional image steps")
