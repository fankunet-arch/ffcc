"""Artifact unit execution for ``fc2_organizer.execution`` (P4-C7 S4; contract sections 14.4, 20, 23-25, 27-29).

S4 scope only: :func:`_execute_artifact_unit` runs ONE artifact unit (U3-U6 / U8..) and maps P4-C6
``MaterializationError`` types to typed failures. ``execute_filesystem`` (integrated orchestration,
consumption, checkpoint issuance) is added in S5.

Per unit (contract section 24):

1. revalidate the parent directory identity (target directory, or ``extrafanart/`` for extrafanart);
2. the target must be absent (an early exit only -- the no-overwrite guarantee is P4-C6's);
3. ``materialize_artifact(request)`` with the manifest's ORIGINAL request object (never copied, rebuilt or
   re-encoded) -- the only artifact write path of the package;
4. verify the receipt (path, size, SHA-256 of ``request.content``) and the published entry (``lstat``: regular
   file, not a link, size), then record ``ARTIFACT_PUBLISHED``;
5. map ``MaterializationError`` by exception TYPE (never by message); on ``ArtifactCleanupError`` record the new
   P4-C6 temporaries of the (revalidated) parent as leftovers -- never deleted -- and, when
   ``target_published`` is true, re-read the final read-only and re-hash it before recording the effect;
6. any failure stops the unit; earlier artifacts are kept (no rollback).

Only the ``MaterializationError`` types of the frozen table are translated; an undefined
``MaterializationError`` subtype, ``BaseException`` and foreign exceptions propagate unchanged (P4-C6 owns its
temporary cleanup), as does the ``OSError`` of a failed post-cleanup listing (leftovers unknown, never "none"). Failures carry enums, errno, ``write_stage``, kind and ordinal only.

This package and the bare public ``fc2_organizer.materialization`` package only.
"""

from __future__ import annotations

from fc2_organizer.execution import _fs
from fc2_organizer.execution.directories import revalidate_directory
from fc2_organizer.execution.errors import ExecutionInputError
from fc2_organizer.execution.models import (
    CompletedEffect,
    EffectKind,
    EntryIdentity,
    EntryType,
    ExecutionFailure,
    ExecutionFailureKind,
    LeftoverTemporary,
    PathRole,
    same_identity,
)
from fc2_organizer.execution.paths import same_entry_name
from fc2_organizer.execution.seal import content_sha256
from fc2_organizer.execution.validation import artifact_unit_roles
from fc2_organizer.materialization import (
    ArtifactCleanupError,
    ArtifactPublishError,
    ArtifactWriteError,
    ArtifactWriteRequest,
    InvalidTargetPathError,
    MaterializationError,
    MaterializationInputError,
    MaterializationModelError,
    MaterializedArtifact,
    ParentDirectoryError,
    TargetExistsError,
    TargetInaccessibleError,
    TemporaryCreateError,
    materialize_artifact,
)

__all__: list[str] = []  # S4: nothing public yet; execute_filesystem arrives in S5

_K = ExecutionFailureKind
_TEMP_PREFIX = ".fc2tmp-"
_TEMP_SUFFIX = ".part"
_HEX = frozenset("0123456789abcdef")

# Exception TYPE -> failure kind (contract section 24 table). Checked in this order with isinstance; the
# P4-C6 hierarchy has no overlap between these rows (ArtifactCleanupError is handled before the table).
_MAPPING: tuple[tuple[type[MaterializationError], ExecutionFailureKind], ...] = (
    (TargetExistsError, _K.TARGET_CONFLICT),
    (ParentDirectoryError, _K.TARGET_DIRECTORY_CHANGED),
    (TargetInaccessibleError, _K.ARTIFACT_TARGET_INACCESSIBLE),
    (TemporaryCreateError, _K.ARTIFACT_TEMP_CREATE_FAILED),
    (ArtifactWriteError, _K.ARTIFACT_WRITE_FAILED),
    (ArtifactPublishError, _K.ARTIFACT_PUBLISH_FAILED),
    (InvalidTargetPathError, _K.ARTIFACT_PATH_REJECTED),
    (MaterializationInputError, _K.ARTIFACT_PATH_REJECTED),
    (MaterializationModelError, _K.ARTIFACT_PATH_REJECTED),
)

_UnitResult = tuple[CompletedEffect | None, ExecutionFailure | None, tuple[LeftoverTemporary, ...]]


def _is_p4c6_temp_name(name: str) -> bool:
    """``^\\.fc2tmp-[0-9a-f]{32}\\.part$`` (exact, lowercase) -- the frozen temporary name pattern."""
    if not (name.startswith(_TEMP_PREFIX) and name.endswith(_TEMP_SUFFIX)):
        return False
    token = name[len(_TEMP_PREFIX):len(name) - len(_TEMP_SUFFIX)]
    return len(token) == 32 and set(token) <= _HEX


def _parent_path(plan: object, parent_role: PathRole) -> str:
    if parent_role is PathRole.TARGET_DIRECTORY:
        return plan.target_directory.absolute_path
    return plan.extrafanart_directory.absolute_path


class _Unit:
    """The frozen facts of one artifact unit (all derived from the validated request and plan)."""

    __slots__ = ("request", "step", "role", "parent", "parent_role", "parent_identity")

    def __init__(self, request: ArtifactWriteRequest, parent_identity: EntryIdentity, plan: object) -> None:
        self.request = request
        self.step, self.role, self.parent_role = artifact_unit_roles(request.kind)
        self.parent = _parent_path(plan, self.parent_role)
        self.parent_identity = parent_identity

    def failure(self, kind: ExecutionFailureKind, *, errno: int | None = None, write_stage: str | None = None,
                target_published: bool | None = None) -> ExecutionFailure:
        return ExecutionFailure(step=self.step, kind=kind, stage=None, write_stage=write_stage, errno=errno,
                                artifact_kind=self.request.kind, ordinal=self.request.ordinal,
                                target_published=target_published)

    def effect(self, identity: EntryIdentity, sha256: str) -> CompletedEffect:
        request = self.request
        return CompletedEffect(EffectKind.ARTIFACT_PUBLISHED, self.role, request.target_path, identity,
                               len(request.content), sha256, request.kind, request.ordinal)


def _execute_artifact_unit(request: ArtifactWriteRequest, parent_identity: EntryIdentity,
                           plan: object) -> _UnitResult:
    """Execute one artifact unit. ``plan`` / ``request`` must already be validated (plan + manifest).

    Returns ``(effect, failure, leftovers)``: ``effect`` only for a verified publish; ``failure`` is ``None``
    iff the unit completed. Propagates (same object, never wrapped) only: a ``MaterializationError`` type the
    frozen table does not define, and the ``OSError`` of a failed after-listing on the cleanup path.
    """
    if type(request) is not ArtifactWriteRequest:
        raise ExecutionInputError("request must be an exact ArtifactWriteRequest")
    if type(parent_identity) is not EntryIdentity or parent_identity.entry_type is not EntryType.DIRECTORY:
        raise ExecutionInputError("parent_identity must be a DIRECTORY EntryIdentity")
    unit = _Unit(request, parent_identity, plan)

    # 1. parent directory identity (missing / replaced / link / junction / unidentifiable -> changed).
    if not revalidate_directory(unit.parent, parent_identity):
        return None, unit.failure(_K.TARGET_DIRECTORY_CHANGED), ()
    # 2. the target must be absent (early exit; P4-C6's publish primitive is the no-overwrite guarantee).
    probe = _fs.snapshot(request.target_path)
    if isinstance(probe, NotADirectoryError):
        return None, unit.failure(_K.TARGET_DIRECTORY_CHANGED), ()
    if not isinstance(probe, FileNotFoundError):
        if isinstance(probe, OSError) and not isinstance(probe, _fs.SnapshotRefused):
            return None, unit.failure(_K.ARTIFACT_TARGET_INACCESSIBLE, errno=_fs.os_errno(probe)), ()
        return None, unit.failure(_K.TARGET_CONFLICT), ()  # any existing entry; never touched
    before = _fs.list_names(unit.parent)  # for exact leftover attribution (contract section 20)
    if isinstance(before, OSError):
        return None, unit.failure(_K.TARGET_DIRECTORY_CHANGED, errno=_fs.os_errno(before)), ()

    # 3. the ONLY artifact write path: P4-C6 materialize_artifact with the original request object.
    outcome: list[object] = []
    try:
        outcome.append(materialize_artifact(request))
    except MaterializationError as exc:
        outcome.append(exc)
    result = outcome[0]
    if isinstance(result, ArtifactCleanupError):
        return _cleanup_failed(unit, result, before)
    if isinstance(result, MaterializationError):
        failure = _mapped_failure(unit, result)
        if failure is None:
            # A MaterializationError type the frozen table does not define: never silently classified as an
            # existing kind; the same object propagates (raised outside any except block: nothing chained).
            raise result
        return None, failure, ()

    # 4. verify the receipt and the published entry.
    sha256 = content_sha256(request.content)
    if (type(result) is not MaterializedArtifact or result.target_path != request.target_path
            or result.size_bytes != len(request.content) or result.sha256 != sha256):
        return None, unit.failure(_K.PUBLISHED_ARTIFACT_MISMATCH), ()
    identity = _published_identity(request)
    if identity is None:
        return None, unit.failure(_K.PUBLISHED_ARTIFACT_MISMATCH), ()
    return unit.effect(identity, sha256), None, ()


def _published_identity(request: ArtifactWriteRequest) -> EntryIdentity | None:
    """``lstat`` of the final: a regular, non-link file with a usable identity and the exact size."""
    current = _fs.snapshot(request.target_path)
    if isinstance(current, OSError) or current.entry_type is not EntryType.FILE:
        return None
    return current if current.size == len(request.content) else None


def _mapped_failure(unit: _Unit, error: MaterializationError) -> ExecutionFailure | None:
    """Contract section 24 table, by exception type only (never the message); ``None`` for a type the
    frozen table does not define (no catch-all row)."""
    errno = getattr(error, "errno", None)
    errno = errno if type(errno) is int else None
    for error_type, kind in _MAPPING:
        if isinstance(error, error_type):
            if kind is _K.ARTIFACT_WRITE_FAILED:
                return unit.failure(kind, errno=errno, write_stage=error.stage.value)
            return unit.failure(kind, errno=errno)
    return None


def _cleanup_failed(unit: _Unit, error: ArtifactCleanupError, before: list[str]) -> _UnitResult:
    """``ArtifactCleanupError``: record the new P4-C6 temporaries (never deleted); if P4-C6 reports the
    target published, re-verify the final (identity, size, full read-only re-hash) before recording it."""
    published = error.target_published
    errno = error.errno if type(error.errno) is int else None
    published_flag = published if type(published) is bool else False
    if not revalidate_directory(unit.parent, unit.parent_identity):
        # The directory is no longer the one we own: its contents are not trusted, nothing is recorded.
        return None, unit.failure(_K.ARTIFACT_CLEANUP_FAILED, errno=errno, target_published=published_flag), ()
    leftovers = _new_temporaries(unit, before)
    if published is not True:
        return None, unit.failure(_K.ARTIFACT_CLEANUP_FAILED, errno=errno, target_published=False), leftovers
    effect = _reverified_effect(unit)
    if effect is None:
        return None, unit.failure(_K.PUBLISHED_ARTIFACT_MISMATCH), leftovers
    return effect, unit.failure(_K.ARTIFACT_CLEANUP_FAILED, errno=errno, target_published=True), leftovers


def _new_temporaries(unit: _Unit, before: list[str]) -> tuple[LeftoverTemporary, ...]:
    """Names present now but not before this unit (Windows: casefold comparison), matching the exact
    lowercase temporary pattern; the actual on-disk names are recorded. Nothing is deleted.

    If the after-listing fails, the leftovers are UNKNOWN, which must never become "none": the listing's
    own ``OSError`` object propagates, so no checkpointable unit result claims a known inventory."""
    after = _fs.list_names(unit.parent)
    if isinstance(after, OSError):
        raise after
    directory_role = (PathRole.EXTRAFANART_DIRECTORY if unit.parent_role is PathRole.EXTRAFANART_DIRECTORY
                      else PathRole.TARGET_DIRECTORY)
    return tuple(LeftoverTemporary(directory_role, name) for name in after
                 if _is_p4c6_temp_name(name) and not any(same_entry_name(name, old) for old in before))


def _reverified_effect(unit: _Unit) -> CompletedEffect | None:
    """P4-C6 says the target was published but its temp cleanup failed: prove it ourselves -- identity,
    size and a full read-only re-read whose SHA-256 equals the request content's, with the identity
    unchanged across the read. Artifacts are small (P4-C5 / P4-C6 limits); media is never re-read."""
    request = unit.request
    identity = _published_identity(request)
    if identity is None:
        return None
    data = _fs.read_bounded(request.target_path, len(request.content))
    if isinstance(data, OSError) or len(data) != len(request.content):
        return None
    sha256 = content_sha256(request.content)
    if content_sha256(data) != sha256:
        return None
    after = _fs.snapshot(request.target_path)
    if isinstance(after, OSError) or not same_identity(after, identity):
        return None
    return unit.effect(identity, sha256)
