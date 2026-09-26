"""``preflight_execution`` -- read-only execution preflight (P4-C7, contract sections 5, 10-17).

Order (frozen):

1. exact input types (``ExecutionInputError``) -- no attribute of a rejected object is
   touched, no filesystem access;
2. plan graph / layout hardening, then manifest hardening (typed contract errors);
3. fingerprints;
4. checkpoint contract checks (S1: type, seal, consumption -- see below);
5. READ-ONLY filesystem snapshots: ``lstat`` of the library root, the source and the
   target directory. Filesystem-state problems become ``PreflightBlocker`` values
   (every detectable blocker, in a fixed order); they are never raised.

This module never creates, writes, renames, links, unlinks or opens anything: the
only filesystem call on the FRESH path is ``lstat`` through the private seam.

S1 scope (construction plan S1 item 7): the RESUME path is not implemented yet. A
non-``None`` checkpoint gets the contract-layer checks 1-3 of section 14.3 (exact
type, seal, consumption) and is then refused with ``CheckpointError(SEAL_INVALID)``,
because S1 cannot issue a legitimate checkpoint. S2 replaces this with full RESUME.
"""

from __future__ import annotations

from fc2_organizer.execution import _fs
from fc2_organizer.execution.errors import (
    CheckpointError,
    CheckpointRejectionReason,
    ExecutionInputError,
)
from fc2_organizer.execution.models import (
    EntryIdentity,
    EntryType,
    ExecutionCheckpoint,
    ExecutionPreflight,
    PathRole,
    PreflightBlocker,
    PreflightBlockReason,
    PreflightMode,
    TransferMode,
)
from fc2_organizer.execution.seal import (
    is_consumed,
    manifest_fingerprint,
    plan_fingerprint,
    sealed,
    verify_seal,
)
from fc2_organizer.execution.validation import (
    expected_units,
    skipped_steps,
    validate_manifest,
    validate_plan,
)
from fc2_organizer.materialization import ArtifactWriteRequest
from fc2_organizer.planning import OrganizePlan

__all__ = ["preflight_execution"]

_MISSING = (FileNotFoundError, NotADirectoryError)


def preflight_execution(
    plan: OrganizePlan,
    artifacts: tuple[ArtifactWriteRequest, ...],
    checkpoint: ExecutionCheckpoint | None = None,
) -> ExecutionPreflight:
    """Validate one film's plan + manifest and snapshot the real filesystem, read-only."""
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
        _refuse_checkpoint_in_s1(checkpoint)

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


def _refuse_checkpoint_in_s1(checkpoint: ExecutionCheckpoint) -> None:
    # Contract section 14.3 checks 1-3; zero filesystem access.
    if not verify_seal(checkpoint):
        raise CheckpointError(CheckpointRejectionReason.SEAL_INVALID)
    if is_consumed(checkpoint.checkpoint_id):
        raise CheckpointError(CheckpointRejectionReason.CONSUMED)
    # S1 cannot issue a checkpoint, so no checkpoint reaching here was issued by an
    # execution of this process: fail closed until S2 implements RESUME.
    raise CheckpointError(CheckpointRejectionReason.SEAL_INVALID)


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
