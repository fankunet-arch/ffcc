"""``preflight_execution`` -- read-only execution preflight (P4-C7, contract sections 5, 10-17).

Order (frozen):

1. exact input types (``ExecutionInputError``) -- no attribute of a rejected object is
   touched, no filesystem access;
2. plan graph / layout hardening, then manifest hardening (typed contract errors);
3. fingerprints;
4. with a checkpoint: the contract layer of section 14.3, in order -- seal, consumption,
   plan fingerprint, manifest fingerprint, strict prefix of E(plan, manifest), not already
   complete -- raised as ``CheckpointError`` with ZERO filesystem access;
5. READ-ONLY filesystem layer. FRESH: ``lstat`` snapshots of the library root, the source
   and the (absent) target directory. RESUME: identity of the library root and of the owned
   directories, their exact inventories, the identity (and, for artifacts, the full
   SHA-256) of every completed file effect, and the source according to progress.
   Filesystem-state problems become ``PreflightBlocker`` values (every detectable blocker,
   in a fixed order); they are never raised.

This module never creates, writes, renames, links or unlinks anything and never consumes a
preflight or a checkpoint. Its only filesystem calls are the private seam's ``snapshot``,
``list_names`` and the read-only ``read_bounded`` (RESUME artifact re-hash only).
"""

from __future__ import annotations

from fc2_organizer.execution import _fs
from fc2_organizer.execution.directories import child_name, compare_inventory, revalidate_directory
from fc2_organizer.execution.errors import (
    CheckpointError,
    CheckpointRejectionReason,
    ExecutionInputError,
)
from fc2_organizer.execution.models import (
    CompletedEffect,
    EffectKind,
    EntryIdentity,
    EntryType,
    ExecutionCheckpoint,
    ExecutionPreflight,
    ExecutionStep,
    ExpectedEffect,
    PathRole,
    PreflightBlocker,
    PreflightBlockReason,
    PreflightMode,
    TransferMode,
    same_identity,
)
from fc2_organizer.execution.seal import (
    content_sha256,
    is_consumed,
    manifest_fingerprint,
    plan_fingerprint,
    sealed,
    verify_seal,
)
from fc2_organizer.execution.validation import (
    expected_effects,
    expected_units,
    skipped_steps,
    validate_manifest,
    validate_plan,
)
from fc2_organizer.materialization import ArtifactWriteRequest
from fc2_organizer.planning import OrganizePlan

__all__ = ["preflight_execution"]

_MISSING = (FileNotFoundError, NotADirectoryError)
_FILE_EFFECTS = (EffectKind.MEDIA_PUBLISHED, EffectKind.ARTIFACT_PUBLISHED)


def preflight_execution(
    plan: OrganizePlan,
    artifacts: tuple[ArtifactWriteRequest, ...],
    checkpoint: ExecutionCheckpoint | None = None,
) -> ExecutionPreflight:
    """Validate one film's plan + manifest (+ checkpoint) and snapshot the real filesystem, read-only."""
    if type(plan) is not OrganizePlan:
        raise ExecutionInputError("plan must be an exact OrganizePlan")
    if type(artifacts) is not tuple:
        raise ExecutionInputError("artifacts must be an exact tuple")
    if checkpoint is not None and type(checkpoint) is not ExecutionCheckpoint:
        raise ExecutionInputError("checkpoint must be None or an exact ExecutionCheckpoint")

    validate_plan(plan)
    validate_manifest(plan, artifacts)
    plan_fp = plan_fingerprint(plan)
    manifest_fp = manifest_fingerprint(artifacts)

    if checkpoint is not None:
        expected = _check_checkpoint_contract(checkpoint, plan, artifacts, plan_fp, manifest_fp)
        return _resume_preflight(plan, artifacts, checkpoint, plan_fp, manifest_fp, expected)

    blockers: list[PreflightBlocker] = []
    library_identity = _snapshot_library_root(plan.library_root, blockers)
    source_identity = _snapshot_source(plan.source_path, plan.source_size, blockers)
    if library_identity is not None:
        _require_target_directory_absent(plan.target_directory.absolute_path, blockers)

    transfer_mode = None
    if library_identity is not None and source_identity is not None:
        same = source_identity.device == library_identity.device
        transfer_mode = TransferMode.SAME_VOLUME if same else TransferMode.CROSS_VOLUME

    return sealed(
        ExecutionPreflight,
        preflight_id=_fs.new_token(),
        mode=PreflightMode.FRESH,
        plan=plan,
        artifacts=artifacts,
        checkpoint=None,
        plan_fingerprint=plan_fp,
        manifest_fingerprint=manifest_fp,
        ready=not blockers,
        blockers=tuple(blockers),
        library_root_identity=library_identity,
        source_identity=source_identity,
        transfer_mode=transfer_mode,
        completed_units=(),
        pending_units=expected_units(plan, artifacts),
        skipped_steps=skipped_steps(artifacts),
    )


# --------------------------------------------------------------------------- RESUME: contract layer


def _check_checkpoint_contract(checkpoint: ExecutionCheckpoint, plan: OrganizePlan,
                               artifacts: tuple[ArtifactWriteRequest, ...], plan_fp: str,
                               manifest_fp: str) -> tuple[ExpectedEffect, ...]:
    """Contract section 14.3 checks 1-7 in order; ZERO filesystem access."""
    if not verify_seal(checkpoint):
        raise CheckpointError(CheckpointRejectionReason.SEAL_INVALID)
    if is_consumed(checkpoint.checkpoint_id):
        raise CheckpointError(CheckpointRejectionReason.CONSUMED)
    if checkpoint.plan_fingerprint != plan_fp:
        raise CheckpointError(CheckpointRejectionReason.PLAN_MISMATCH)
    if checkpoint.manifest_fingerprint != manifest_fp:
        raise CheckpointError(CheckpointRejectionReason.MANIFEST_MISMATCH)
    expected = expected_effects(plan, artifacts)
    if not _is_bound_prefix(checkpoint, expected):
        raise CheckpointError(CheckpointRejectionReason.EFFECTS_NOT_PREFIX)
    if len(checkpoint.completed_effects) == len(expected):
        raise CheckpointError(CheckpointRejectionReason.ALREADY_COMPLETE)
    return expected


def _slot_matches(effect: CompletedEffect, slot: ExpectedEffect) -> bool:
    return (effect.kind is slot.kind and effect.role is slot.role and effect.path == slot.path
            and effect.artifact_kind is slot.artifact_kind and effect.ordinal == slot.ordinal)


def _is_bound_prefix(checkpoint: ExecutionCheckpoint, expected: tuple[ExpectedEffect, ...]) -> bool:
    done = checkpoint.completed_effects
    if len(done) > len(expected):
        return False
    if not all(_slot_matches(effect, slot) for effect, slot in zip(done, expected)):
        return False
    # The recorded directory snapshots must be the ones the directory effects recorded.
    if not same_identity(done[0].identity, checkpoint.target_directory_identity):
        return False
    extrafanart = [e for e in done if e.kind is EffectKind.EXTRAFANART_DIRECTORY_CREATED]
    efd_identity = checkpoint.extrafanart_directory_identity
    if extrafanart:
        if efd_identity is None or not same_identity(extrafanart[0].identity, efd_identity):
            return False
    elif efd_identity is not None or any(
            t.directory_role is PathRole.EXTRAFANART_DIRECTORY for t in checkpoint.leftover_temporaries):
        return False
    return True


# --------------------------------------------------------------------------- RESUME: filesystem layer


def _resume_preflight(plan: OrganizePlan, artifacts: tuple[ArtifactWriteRequest, ...],
                      checkpoint: ExecutionCheckpoint, plan_fp: str, manifest_fp: str,
                      expected: tuple[ExpectedEffect, ...]) -> ExecutionPreflight:
    blockers: list[PreflightBlocker] = []
    done = checkpoint.completed_effects
    kinds = {effect.kind for effect in done}

    library = _fs.snapshot(plan.library_root)
    library_identity = None
    if (isinstance(library, OSError) or library.entry_type is not EntryType.DIRECTORY
            or not same_identity(library, checkpoint.library_root_identity)):
        blockers.append(_blocker(PreflightBlockReason.LIBRARY_ROOT_CHANGED, PathRole.LIBRARY_ROOT))
    else:
        library_identity = library

    present: list[CompletedEffect] = []
    target_directory = plan.target_directory.absolute_path
    if not revalidate_directory(target_directory, checkpoint.target_directory_identity):
        blockers.append(_blocker(PreflightBlockReason.TARGET_DIRECTORY_CHANGED, PathRole.TARGET_DIRECTORY))
    else:
        in_target = [e for e in done[1:] if e.kind is not EffectKind.SOURCE_REMOVED
                     and e.role is not PathRole.EXTRAFANART_FILE]
        present += _check_inventory(target_directory, in_target, checkpoint, PathRole.TARGET_DIRECTORY, blockers)
        efd_effect = next((e for e in present if e.kind is EffectKind.EXTRAFANART_DIRECTORY_CREATED), None)
        if efd_effect is not None:
            extrafanart_directory = plan.extrafanart_directory.absolute_path
            if not revalidate_directory(extrafanart_directory, checkpoint.extrafanart_directory_identity):
                blockers.append(_blocker(PreflightBlockReason.TARGET_DIRECTORY_CHANGED,
                                         PathRole.EXTRAFANART_DIRECTORY))
            else:
                in_extrafanart = [e for e in done if e.role is PathRole.EXTRAFANART_FILE]
                present += _check_inventory(extrafanart_directory, in_extrafanart, checkpoint,
                                            PathRole.EXTRAFANART_DIRECTORY, blockers)

    requests = {(r.kind, r.ordinal): r for r in artifacts}
    for effect in done:  # E order
        if effect.kind in _FILE_EFFECTS and any(effect is p for p in present):
            _check_file_effect(effect, requests, blockers)

    if EffectKind.SOURCE_REMOVED not in kinds:
        _check_resume_source(plan.source_path, checkpoint.source_identity, blockers)

    completed_units, pending_units = _split_units(plan, artifacts, len(done))
    return sealed(
        ExecutionPreflight,
        preflight_id=_fs.new_token(),
        mode=PreflightMode.RESUME,
        plan=plan,
        artifacts=artifacts,
        checkpoint=checkpoint,
        plan_fingerprint=plan_fp,
        manifest_fingerprint=manifest_fp,
        ready=not blockers,
        blockers=tuple(blockers),
        library_root_identity=library_identity,
        source_identity=checkpoint.source_identity,
        transfer_mode=checkpoint.transfer_mode,
        completed_units=completed_units,
        pending_units=pending_units,
        skipped_steps=skipped_steps(artifacts),
    )


def _check_inventory(directory: str, effects: list[CompletedEffect], checkpoint: ExecutionCheckpoint,
                     role: PathRole, blockers: list[PreflightBlocker]) -> list[CompletedEffect]:
    """Exact inventory (contract section 14.3). Returns the completed effects whose entry is present."""
    named = [(effect, child_name(directory, effect.path)) for effect in effects]
    leftovers = tuple(t.name for t in checkpoint.leftover_temporaries if t.directory_role is role)
    expected_names = tuple(name for _, name in named if name is not None) + leftovers
    result = compare_inventory(directory, expected_names)
    if isinstance(result, OSError):
        blockers.append(_blocker(PreflightBlockReason.TARGET_DIRECTORY_CHANGED, role, _fs.os_errno(result)))
        return []
    has_unexpected, missing = result
    if has_unexpected:
        blockers.append(_blocker(PreflightBlockReason.UNEXPECTED_ENTRY, role))
    present = []
    for effect, name in named:
        if name is None or name in missing:
            blockers.append(PreflightBlocker(PreflightBlockReason.COMPLETED_EFFECT_MISSING, effect.role,
                                             None, effect.ordinal))
        else:
            present.append(effect)
    if any(name in missing for name in leftovers):
        blockers.append(_blocker(PreflightBlockReason.COMPLETED_EFFECT_MISSING, role))
    return present


def _check_file_effect(effect: CompletedEffect, requests: dict, blockers: list[PreflightBlocker]) -> None:
    changed = PreflightBlocker(PreflightBlockReason.COMPLETED_EFFECT_CHANGED, effect.role, None, effect.ordinal)
    current = _fs.snapshot(effect.path)
    if isinstance(current, OSError) or not same_identity(current, effect.identity):
        blockers.append(changed)
        return
    if effect.kind is not EffectKind.ARTIFACT_PUBLISHED:
        return  # media: identity only (device, inode, size, mtime_ns); never re-hashed
    request = requests[(effect.artifact_kind, effect.ordinal)]
    data = _fs.read_bounded(effect.path, effect.size)
    if isinstance(data, OSError) or len(data) != effect.size:
        blockers.append(changed)
        return
    digest = content_sha256(data)
    if digest != effect.sha256 or digest != content_sha256(request.content):
        blockers.append(changed)


def _check_resume_source(path: str, identity: EntryIdentity, blockers: list[PreflightBlocker]) -> None:
    role = PathRole.SOURCE
    current = _fs.snapshot(path)
    if isinstance(current, _fs.SnapshotRefused):  # before the generic OSError branch
        blockers.append(_blocker(PreflightBlockReason.SOURCE_CHANGED, role))
    elif isinstance(current, OSError):
        if isinstance(current, _MISSING):
            blockers.append(_blocker(PreflightBlockReason.SOURCE_MISSING, role))
        else:
            blockers.append(_blocker(PreflightBlockReason.SOURCE_INACCESSIBLE, role, _fs.os_errno(current)))
    elif not same_identity(current, identity):
        blockers.append(_blocker(PreflightBlockReason.SOURCE_CHANGED, role))


def _split_units(plan: OrganizePlan, artifacts: tuple[ArtifactWriteRequest, ...], done_count: int):
    """Units whose every effect is in the completed prefix are completed; the rest are pending, in order.
    ``MOVE_MEDIA`` owns two effects (``MEDIA_PUBLISHED``, ``SOURCE_REMOVED``); every other unit owns one."""
    completed, pending = [], []
    remaining = done_count
    for unit in expected_units(plan, artifacts):
        size = 2 if unit.step is ExecutionStep.MOVE_MEDIA else 1
        if not pending and remaining >= size:
            completed.append(unit)
            remaining -= size
        else:
            pending.append(unit)
    return tuple(completed), tuple(pending)


# --------------------------------------------------------------------------- FRESH


def _blocker(reason: PreflightBlockReason, role: PathRole, errno: int | None = None) -> PreflightBlocker:
    return PreflightBlocker(reason=reason, role=role, errno=errno)


def _snapshot_library_root(path: str, blockers: list[PreflightBlocker]) -> EntryIdentity | None:
    # Classification order is unchanged: link -> not a directory -> identity unavailable.
    role = PathRole.LIBRARY_ROOT
    result = _fs.snapshot(path)
    if isinstance(result, _fs.SnapshotRefused):
        if result.reason == _fs.REFUSED_LINK:
            blockers.append(_blocker(PreflightBlockReason.LIBRARY_ROOT_IS_LINK, role))
        elif result.reason == _fs.REFUSED_SPECIAL or result.entry_type is not EntryType.DIRECTORY:
            blockers.append(_blocker(PreflightBlockReason.LIBRARY_ROOT_NOT_DIRECTORY, role))
        else:
            blockers.append(_blocker(PreflightBlockReason.IDENTITY_UNAVAILABLE, role))
        return None
    if isinstance(result, OSError):
        if isinstance(result, _MISSING):
            blockers.append(_blocker(PreflightBlockReason.LIBRARY_ROOT_MISSING, role))
        else:
            blockers.append(_blocker(PreflightBlockReason.LIBRARY_ROOT_INACCESSIBLE, role, _fs.os_errno(result)))
        return None
    if result.entry_type is not EntryType.DIRECTORY:
        blockers.append(_blocker(PreflightBlockReason.LIBRARY_ROOT_NOT_DIRECTORY, role))
        return None
    return result


def _snapshot_source(path: str, expected_size: int, blockers: list[PreflightBlocker]) -> EntryIdentity | None:
    # Classification order is unchanged: link -> not a regular file -> size mismatch -> identity unavailable.
    role = PathRole.SOURCE
    result = _fs.snapshot(path)
    if isinstance(result, _fs.SnapshotRefused):
        if result.reason == _fs.REFUSED_LINK:
            blockers.append(_blocker(PreflightBlockReason.SOURCE_IS_LINK, role))
        elif result.reason == _fs.REFUSED_SPECIAL or result.entry_type is not EntryType.FILE:
            blockers.append(_blocker(PreflightBlockReason.SOURCE_NOT_REGULAR_FILE, role))
        elif result.size != expected_size:
            blockers.append(_blocker(PreflightBlockReason.SOURCE_SIZE_MISMATCH, role))
        else:
            blockers.append(_blocker(PreflightBlockReason.IDENTITY_UNAVAILABLE, role))
        return None
    if isinstance(result, OSError):
        if isinstance(result, _MISSING):
            blockers.append(_blocker(PreflightBlockReason.SOURCE_MISSING, role))
        else:
            blockers.append(_blocker(PreflightBlockReason.SOURCE_INACCESSIBLE, role, _fs.os_errno(result)))
        return None
    if result.entry_type is not EntryType.FILE:
        blockers.append(_blocker(PreflightBlockReason.SOURCE_NOT_REGULAR_FILE, role))
        return None
    if result.size != expected_size:
        blockers.append(_blocker(PreflightBlockReason.SOURCE_SIZE_MISMATCH, role))
        return None
    return result


def _require_target_directory_absent(path: str, blockers: list[PreflightBlocker]) -> None:
    # Contract section 13: any existing entry (even an empty directory, a link, a special file or one
    # without a usable identity) blocks; nothing is adopted.
    role = PathRole.TARGET_DIRECTORY
    result = _fs.snapshot(path)
    if isinstance(result, _fs.SnapshotRefused) or not isinstance(result, OSError):
        blockers.append(_blocker(PreflightBlockReason.TARGET_DIRECTORY_EXISTS, role))
    elif isinstance(result, FileNotFoundError):
        return
    elif isinstance(result, NotADirectoryError):
        blockers.append(_blocker(PreflightBlockReason.LIBRARY_ROOT_NOT_DIRECTORY, PathRole.LIBRARY_ROOT))
    else:
        blockers.append(_blocker(PreflightBlockReason.TARGET_DIRECTORY_INACCESSIBLE, role, _fs.os_errno(result)))
