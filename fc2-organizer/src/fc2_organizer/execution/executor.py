"""The single-film filesystem executor of ``fc2_organizer.execution`` (P4-C7 S4 + S5).

* :func:`execute_filesystem` (S5; contract sections 4, 8, 9, 14.5, 15.4, 15.5, 27-30) -- the only entry that
  produces final effects: frozen pre-filesystem checks (type -> seal -> ready -> structure + fingerprints ->
  consumption), a read-only whole-state revalidation, then the pending units U1..U8.. in order, stopping at the
  first typed failure; status from the cumulative effects; a new sealed checkpoint for every PARTIAL.
* :func:`_execute_artifact_unit` (S4; contract sections 20, 24) -- ONE artifact unit (U3-U6 / U8..) and the
  ``MaterializationError`` type mapping.

Per artifact unit (contract section 24):

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

Synchronous, single film, forward-only: no batch, thread / process pool, persistence, rollback, undo or
transaction. This package and the bare public ``fc2_organizer.materialization`` / ``fc2_organizer.planning``
packages only.
"""

from __future__ import annotations

from fc2_organizer.execution import _fs
from fc2_organizer.execution import preflight as _preflight
from fc2_organizer.execution.directories import (
    create_extrafanart_directory,
    create_target_directory,
    revalidate_directory,
)
from fc2_organizer.execution.errors import (
    CheckpointError,
    CheckpointRejectionReason,
    ExecutionInputError,
    PreflightIntegrityError,
    PreflightIntegrityReason,
    PreflightNotReadyError,
)
from fc2_organizer.execution.models import (
    CompletedEffect,
    EffectKind,
    EntryIdentity,
    EntryType,
    ExecutionCheckpoint,
    ExecutionFailure,
    ExecutionFailureKind,
    ExecutionPreflight,
    ExecutionResult,
    ExecutionStatus,
    ExecutionStep,
    ExecutionUnit,
    LeftoverTemporary,
    PathRole,
    PreflightBlocker,
    PreflightBlockReason,
    PreflightMode,
    TransferMode,
    same_identity,
)
from fc2_organizer.execution.paths import same_entry_name
from fc2_organizer.execution.seal import (
    ClaimIntegrityError,
    claim_acquire,
    claim_hand_over,
    claim_poison_active,
    claim_poison_reserved,
    claim_release,
    claim_reserve,
    claim_take_over,
    content_sha256,
    is_consumed,
    issue_checkpoint,
    manifest_fingerprint,
    plan_fingerprint,
    register_consumption,
    verify_seal,
)
from fc2_organizer.execution.transfer import ResumePhase, transfer_media
from fc2_organizer.execution.validation import (
    artifact_unit_roles,
    validate_manifest,
    validate_plan,
)
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

__all__ = ["execute_filesystem"]

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


# =========================================================================== S5: execute_filesystem

# Read-only whole-state revalidation (contract sections 10-14.3 re-run at execution time): the first blocker,
# in the frozen library -> source -> target order, becomes the typed failure that stops before any mutation.
_BLOCKER_FAILURE = {
    PreflightBlockReason.LIBRARY_ROOT_MISSING: _K.LIBRARY_ROOT_CHANGED,
    PreflightBlockReason.LIBRARY_ROOT_NOT_DIRECTORY: _K.LIBRARY_ROOT_CHANGED,
    PreflightBlockReason.LIBRARY_ROOT_IS_LINK: _K.LIBRARY_ROOT_CHANGED,
    PreflightBlockReason.LIBRARY_ROOT_INACCESSIBLE: _K.LIBRARY_ROOT_CHANGED,
    PreflightBlockReason.LIBRARY_ROOT_CHANGED: _K.LIBRARY_ROOT_CHANGED,
    PreflightBlockReason.SOURCE_MISSING: _K.SOURCE_MISSING,
    PreflightBlockReason.SOURCE_IS_LINK: _K.SOURCE_CHANGED,
    PreflightBlockReason.SOURCE_NOT_REGULAR_FILE: _K.SOURCE_CHANGED,
    PreflightBlockReason.SOURCE_SIZE_MISMATCH: _K.SOURCE_CHANGED,
    PreflightBlockReason.SOURCE_INACCESSIBLE: _K.SOURCE_CHANGED,
    PreflightBlockReason.SOURCE_CHANGED: _K.SOURCE_CHANGED,
    # Only the source snapshot reaches _first() with this reason (an unusable library root returns
    # LIBRARY_ROOT_CHANGED before): the source can no longer be proven to be the frozen one (fail closed).
    PreflightBlockReason.IDENTITY_UNAVAILABLE: _K.SOURCE_CHANGED,
    PreflightBlockReason.TARGET_DIRECTORY_EXISTS: _K.TARGET_CONFLICT,
    PreflightBlockReason.TARGET_DIRECTORY_INACCESSIBLE: _K.TARGET_DIRECTORY_CHANGED,
    PreflightBlockReason.TARGET_DIRECTORY_CHANGED: _K.TARGET_DIRECTORY_CHANGED,
    PreflightBlockReason.UNEXPECTED_ENTRY: _K.UNEXPECTED_ENTRY,
    PreflightBlockReason.COMPLETED_EFFECT_MISSING: _K.TARGET_DIRECTORY_CHANGED,
    PreflightBlockReason.COMPLETED_EFFECT_CHANGED: _K.TARGET_DIRECTORY_CHANGED,
}


def execute_filesystem(preflight: ExecutionPreflight) -> ExecutionResult:
    """Execute one film's sealed, ready preflight against the real filesystem (contract section 4).

    Frozen order (section 15.5): exact type -> seal -> ``ready`` -> plan / manifest re-validation and
    fingerprints -> consumption registration -> filesystem. Rejections before consumption touch nothing and
    consume nothing. Typed failures become a result; ``BaseException``, foreign exceptions and the raw
    propagations of the lower layers pass through unchanged (no result, no checkpoint, no rollback).
    """
    if type(preflight) is not ExecutionPreflight:
        raise ExecutionInputError("preflight must be an exact ExecutionPreflight")
    if not verify_seal(preflight):
        raise PreflightIntegrityError(PreflightIntegrityReason.SEAL_INVALID)
    if preflight.ready is not True:
        raise PreflightNotReadyError()
    plan, artifacts = preflight.plan, preflight.artifacts
    validate_plan(plan)
    validate_manifest(plan, artifacts)
    if (plan_fingerprint(plan) != preflight.plan_fingerprint
            or manifest_fingerprint(artifacts) != preflight.manifest_fingerprint):
        raise PreflightIntegrityError(PreflightIntegrityReason.FINGERPRINT_MISMATCH)
    _consume(preflight)
    return _Run(preflight).execute()


def _consume(preflight: ExecutionPreflight) -> None:
    """Atomic check-and-register of the preflight id (and the checkpoint id on RESUME), before any filesystem
    access (section 15.4). The two CONSUMED families stay distinct."""
    checkpoint = preflight.checkpoint
    ids = (preflight.preflight_id,) if checkpoint is None else (preflight.preflight_id, checkpoint.checkpoint_id)
    if register_consumption(ids):
        return
    if is_consumed(preflight.preflight_id):
        raise PreflightIntegrityError(PreflightIntegrityReason.CONSUMED)
    raise CheckpointError(CheckpointRejectionReason.CONSUMED)


class _Run:
    """The mutable bookkeeping of ONE execute_filesystem call (never shared, never persisted)."""

    def __init__(self, preflight: ExecutionPreflight) -> None:
        self.preflight = preflight
        self.plan = preflight.plan
        checkpoint = preflight.checkpoint
        self.resume = checkpoint is not None
        if checkpoint is None:
            self.library_identity = preflight.library_root_identity
            self.source_identity = preflight.source_identity
            self.target_identity: EntryIdentity | None = None
            self.extrafanart_identity: EntryIdentity | None = None
            self.mode: TransferMode | None = preflight.transfer_mode
            self.effects: list[CompletedEffect] = []
            self.leftovers: list[LeftoverTemporary] = []
        else:
            self.library_identity = checkpoint.library_root_identity
            self.source_identity = checkpoint.source_identity
            self.target_identity = checkpoint.target_directory_identity
            self.extrafanart_identity = checkpoint.extrafanart_directory_identity
            self.mode = checkpoint.transfer_mode
            self.effects = list(checkpoint.completed_effects)
            self.leftovers = list(checkpoint.leftover_temporaries)
        self.initial_count = len(self.effects)
        self.u2_mode: TransferMode | None = self.mode if self._has(EffectKind.MEDIA_PUBLISHED) else None
        self.requests = {(r.kind, r.ordinal): r for r in preflight.artifacts}  # the manifest's own objects
        # Source ownership claim (contract section 15.6): the ACTIVE token this call holds, and -- for a
        # RESUME of a lineage that published the media but has not removed the source -- the reservation
        # owner the consumed input checkpoint may hold until this call hands it over or takes it over.
        self.claim_token: str | None = None
        self.reserving_checkpoint_id: str | None = (
            checkpoint.checkpoint_id if checkpoint is not None and self._source_retained() else None)

    def _source_retained(self) -> bool:
        """MEDIA_PUBLISHED is recorded but SOURCE_REMOVED is not (a published, source-retaining lineage)."""
        return self._has(EffectKind.MEDIA_PUBLISHED) and not self._has(EffectKind.SOURCE_REMOVED)

    def _has(self, kind: EffectKind) -> bool:
        return any(effect.kind is kind for effect in self.effects)

    # ------------------------------------------------------------------ driver

    def execute(self) -> ExecutionResult:
        try:
            units = self.preflight.pending_units
            failure = self._revalidate(units[0].step)
            if failure is None:
                for unit in units:
                    failure = self._run_unit(unit)
                    if failure is not None:
                        break  # first failure: nothing after it runs (forward-only, no rollback)
            return self._result(failure)
        except BaseException:
            # Section 15.6: whether the media was published can no longer be proven -> POISONED (owner-matched;
            # a no-op when this call does not own the key), then the same exception object propagates.
            self._poison()
            raise

    def _poison(self) -> None:
        if self.claim_token is not None:
            claim_poison_active(self.source_identity, self.claim_token)
        elif self.reserving_checkpoint_id is not None:
            claim_poison_reserved(self.source_identity, self.reserving_checkpoint_id)

    def _run_unit(self, unit: ExecutionUnit) -> ExecutionFailure | None:
        step = unit.step
        if step is ExecutionStep.CREATE_DIRECTORY:
            return self._u1()
        if step is ExecutionStep.MOVE_MEDIA:
            return self._u2()
        if step is ExecutionStep.ENSURE_EXTRAFANART_DIRECTORY:
            return self._u7()
        return self._artifact(unit)

    # ------------------------------------------------------------------ units

    def _u1(self) -> ExecutionFailure | None:
        identity, failure = create_target_directory(self.plan, self.library_identity)
        if failure is not None:
            return failure  # PUBLISH_VERIFY: see _result -- no identity, so no recordable effect
        self.target_identity = identity
        self.effects.append(CompletedEffect(EffectKind.TARGET_DIRECTORY_CREATED, PathRole.TARGET_DIRECTORY,
                                            self.plan.target_directory.absolute_path, identity,
                                            None, None, None, None))
        # Section 17: the actual mode is decided against the NEW target directory's device.
        same = self.source_identity.device == identity.device
        self.mode = TransferMode.SAME_VOLUME if same else TransferMode.CROSS_VOLUME
        return None

    def _u2(self) -> ExecutionFailure | None:
        tail = self._has(EffectKind.MEDIA_PUBLISHED)
        phase = ResumePhase.SOURCE_REMOVAL_ONLY if tail else ResumePhase.FULL
        # Section 15.6 acquisition, only now (after U1, immediately before U2): no entry -> ACTIVE, or the
        # source-removal tail takes over RESERVED(input checkpoint) -> ACTIVE. Anything else is a conflict.
        if tail:
            token = (None if self.reserving_checkpoint_id is None
                     else claim_take_over(self.source_identity, self.reserving_checkpoint_id))
        else:
            token = claim_acquire(self.source_identity)
        if token is None:
            return ExecutionFailure(step=ExecutionStep.MOVE_MEDIA, kind=_K.SOURCE_CHANGED)
        self.claim_token = token
        self.reserving_checkpoint_id = None  # taken over: ACTIVE(token) now protects the source
        outcome = transfer_media(self.plan, self.source_identity, self.target_identity, self.mode,
                                 resume_phase=phase)
        self.effects.extend(outcome.effects)  # every effect that really happened, even with a failure
        self.leftovers.extend(outcome.leftover_temporaries)
        self.mode = outcome.transfer_mode  # CROSS_VOLUME after an EXDEV fallback
        self.u2_mode = outcome.transfer_mode
        return outcome.failure

    def _u7(self) -> ExecutionFailure | None:
        identity, failure = create_extrafanart_directory(self.plan, self.target_identity)
        if failure is not None:
            return failure
        self.extrafanart_identity = identity
        self.effects.append(CompletedEffect(EffectKind.EXTRAFANART_DIRECTORY_CREATED,
                                            PathRole.EXTRAFANART_DIRECTORY,
                                            self.plan.extrafanart_directory.absolute_path, identity,
                                            None, None, None, None))
        return None

    def _artifact(self, unit: ExecutionUnit) -> ExecutionFailure | None:
        request = self.requests[(unit.artifact_kind, unit.ordinal)]
        parent = (self.extrafanart_identity if unit.step is ExecutionStep.MATERIALIZE_EXTRAFANART
                  else self.target_identity)
        effect, failure, leftovers = _execute_artifact_unit(request, parent, self.plan)
        if effect is not None:
            self.effects.append(effect)
        self.leftovers.extend(leftovers)
        return failure

    # ------------------------------------------------------------------ read-only whole-state revalidation

    def _revalidate(self, step: ExecutionStep) -> ExecutionFailure | None:
        kind, errno = self._revalidate_resume() if self.resume else self._revalidate_fresh()
        if kind is None:
            return None
        return ExecutionFailure(step=step, kind=kind, errno=errno)

    def _revalidate_fresh(self) -> tuple[ExecutionFailureKind | None, int | None]:
        plan, preflight = self.plan, self.preflight
        blockers: list[PreflightBlocker] = []
        library = _preflight._snapshot_library_root(plan.library_root, blockers)
        if library is None or not same_identity(library, preflight.library_root_identity):
            return _K.LIBRARY_ROOT_CHANGED, None
        source = _preflight._snapshot_source(plan.source_path, plan.source_size, blockers)
        if source is None:
            return _first(blockers)
        if not same_identity(source, preflight.source_identity):
            return _K.SOURCE_CHANGED, None
        _preflight._require_target_directory_absent(plan.target_directory.absolute_path, blockers)
        return _first(blockers)

    def _revalidate_resume(self) -> tuple[ExecutionFailureKind | None, int | None]:
        plan, checkpoint = self.plan, self.preflight.checkpoint
        library = _fs.snapshot(plan.library_root)
        if (isinstance(library, OSError) or library.entry_type is not EntryType.DIRECTORY
                or not same_identity(library, checkpoint.library_root_identity)):
            return _K.LIBRARY_ROOT_CHANGED, None
        blockers: list[PreflightBlocker] = []
        if not self._has(EffectKind.SOURCE_REMOVED):
            _preflight._check_resume_source(plan.source_path, checkpoint.source_identity, blockers)
            if blockers:
                return _first(blockers)
        _preflight._check_owned_state(plan, self.preflight.artifacts, checkpoint, blockers)
        return _first(blockers)

    # ------------------------------------------------------------------ result

    def _result(self, failure: ExecutionFailure | None) -> ExecutionResult:
        preflight = self.preflight
        effects = tuple(self.effects)
        leftovers = tuple(self.leftovers)
        media = next((e for e in effects if e.kind is EffectKind.MEDIA_PUBLISHED), None)
        media_sha256 = None if media is None else media.sha256  # cross-volume only; never re-read
        if failure is None:
            status, checkpoint = ExecutionStatus.SUCCESS, None  # every pending unit completed: E is complete
        elif effects:
            status, checkpoint = ExecutionStatus.PARTIAL, self._checkpoint(effects, leftovers)
        else:
            # Includes U1's exclusive mkdir succeeding while its snapshot shows no owned directory
            # (stage PUBLISH_VERIFY): our directory is not visible at the final location, no identity can be
            # recorded, and no checkpoint may claim it; a later fresh preflight fails closed
            # (TARGET_DIRECTORY_EXISTS).
            status, checkpoint = ExecutionStatus.FAILED, None
        result = ExecutionResult(
            status=status,
            preflight_id=preflight.preflight_id,
            mode=preflight.mode,
            transfer_mode=self.u2_mode,
            completed_effects=effects,
            new_effect_count=len(effects) - self.initial_count,
            failure=failure,
            checkpoint=checkpoint,
            leftover_temporaries=leftovers,
            media_sha256=media_sha256,
            skipped_steps=preflight.skipped_steps,
        )
        self._settle_claim(checkpoint)  # the result is delivered only after the claim transition took effect
        return result

    def _settle_claim(self, checkpoint: ExecutionCheckpoint | None) -> None:
        """Section 15.6 after the units: a published, source-retaining state is never released -- it is handed to
        the NEW checkpoint (ACTIVE(token) -> RESERVED, or RESERVED(input) -> RESERVED); otherwise an ACTIVE claim
        is released. Every owed transition must take effect (owner-matched) or the call fails closed."""
        identity = self.source_identity
        if self._source_retained():
            if self.claim_token is not None:
                if checkpoint is None or not claim_reserve(identity, self.claim_token, checkpoint.checkpoint_id):
                    raise ClaimIntegrityError()
            elif self.reserving_checkpoint_id is not None:
                if checkpoint is None:
                    raise ClaimIntegrityError()
                outcome = claim_hand_over(identity, self.reserving_checkpoint_id, checkpoint.checkpoint_id)
                if outcome == "mismatch":
                    raise ClaimIntegrityError()
                # "poisoned": this lineage no longer owns the key; nothing to hand over (fail closed stays).
            else:
                raise ClaimIntegrityError()  # a published, retained source must be protected by this lineage
        elif self.claim_token is not None and not claim_release(identity, self.claim_token):
            raise ClaimIntegrityError()
        self.claim_token = None
        self.reserving_checkpoint_id = None

    def _checkpoint(self, effects: tuple[CompletedEffect, ...],
                    leftovers: tuple[LeftoverTemporary, ...]) -> ExecutionCheckpoint:
        """A NEW sealed checkpoint (new id, new seal) over the cumulative prefix and leftovers (section 14.5)."""
        preflight = self.preflight
        return issue_checkpoint(
            plan_fingerprint=preflight.plan_fingerprint,
            manifest_fingerprint=preflight.manifest_fingerprint,
            library_root_identity=self.library_identity,
            source_identity=self.source_identity,
            transfer_mode=self.mode,
            target_directory_identity=self.target_identity,
            extrafanart_directory_identity=(self.extrafanart_identity
                                            if any(e.kind is EffectKind.EXTRAFANART_DIRECTORY_CREATED
                                                   for e in effects) else None),
            completed_effects=effects,
            leftover_temporaries=leftovers,
        )


def _first(blockers: list[PreflightBlocker]) -> tuple[ExecutionFailureKind | None, int | None]:
    if not blockers:
        return None, None
    blocker = blockers[0]
    return _BLOCKER_FAILURE[blocker.reason], blocker.errno
