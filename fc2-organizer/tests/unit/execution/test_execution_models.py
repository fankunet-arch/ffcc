"""P4-C7 S1: execution value models, enums and error hierarchy (contract sections 8-9, 12, 14, 16, 27)."""

from __future__ import annotations

import dataclasses

import pytest

from fc2_organizer.execution import (
    ArtifactManifestError,
    CheckpointError,
    CheckpointRejectionReason,
    CompletedEffect,
    EffectKind,
    EntryIdentity,
    EntryType,
    ExecutionCheckpoint,
    ExecutionContractError,
    ExecutionError,
    ExecutionFailure,
    ExecutionFailureKind,
    ExecutionInputError,
    ExecutionModelError,
    ExecutionPreflight,
    ExecutionResult,
    ExecutionStatus,
    ExecutionStep,
    ExecutionUnit,
    LeftoverTemporary,
    ManifestRejectionReason,
    PathRole,
    PlanGraphError,
    PlanGraphRejectionReason,
    PreflightBlocker,
    PreflightBlockReason,
    PreflightIntegrityError,
    PreflightIntegrityReason,
    PreflightMode,
    PreflightNotReadyError,
    TransferMode,
    TransferStage,
)
from fc2_organizer.execution.models import ExpectedEffect, same_identity
from fc2_organizer.execution.seal import sealed
from fc2_organizer.materialization import ArtifactKind

from ._builders import make_manifest, make_plan

HEX32 = "a" * 32
HEX64 = "b" * 64
DIR = EntryIdentity(1, 2, EntryType.DIRECTORY, None, None)
FILE = EntryIdentity(1, 3, EntryType.FILE, 10, 1_000)


def _values(enum_type) -> set[str]:
    return {member.value for member in enum_type}


# --------------------------------------------------------------------------- enums (frozen member sets)


def test_enum_member_sets_are_exactly_the_contract_sets():
    assert _values(ExecutionStatus) == {"success", "partial", "failed"}
    assert [s.value for s in ExecutionStep] == [
        "create_directory", "move_media", "materialize_nfo", "materialize_poster", "materialize_fanart",
        "materialize_thumb", "ensure_extrafanart_directory", "materialize_extrafanart"]
    assert _values(EffectKind) == {"target_directory_created", "media_published", "source_removed",
                                   "artifact_published", "extrafanart_directory_created"}
    assert _values(EntryType) == {"file", "directory"}
    assert _values(PathRole) == {"library_root", "source", "target_directory", "target_media", "nfo", "poster",
                                 "fanart", "thumb", "extrafanart_directory", "extrafanart_file"}
    assert _values(PreflightMode) == {"fresh", "resume"}
    assert _values(TransferMode) == {"same_volume", "cross_volume"}
    assert len(TransferStage) == 15
    assert len(PreflightBlockReason) == 18
    assert len(ExecutionFailureKind) == 27
    assert len(PlanGraphRejectionReason) == 20
    assert len(ManifestRejectionReason) == 11
    assert _values(CheckpointRejectionReason) == {"seal_invalid", "consumed", "plan_mismatch",
                                                  "manifest_mismatch", "effects_not_prefix", "already_complete"}
    assert _values(PreflightIntegrityReason) == {"seal_invalid", "consumed", "fingerprint_mismatch"}


# --------------------------------------------------------------------------- errors


def test_error_hierarchy():
    assert issubclass(ExecutionInputError, ExecutionError) and issubclass(ExecutionInputError, TypeError)
    assert issubclass(ExecutionModelError, ExecutionError) and issubclass(ExecutionModelError, ValueError)
    for cls in (PlanGraphError, ArtifactManifestError, CheckpointError, PreflightIntegrityError):
        assert issubclass(cls, ExecutionContractError) and issubclass(cls, ValueError)
    assert issubclass(PreflightNotReadyError, ExecutionError)
    assert not issubclass(PreflightNotReadyError, ExecutionContractError)


def test_error_messages_are_fixed_wording_with_reason():
    err = PlanGraphError(PlanGraphRejectionReason.OPERATION_COUNT)
    assert err.reason is PlanGraphRejectionReason.OPERATION_COUNT
    assert str(err) == "organize plan rejected at execution boundary: operation_count"
    assert str(ArtifactManifestError(ManifestRejectionReason.ORDER)) == "artifact manifest rejected: order"
    assert CheckpointError(CheckpointRejectionReason.CONSUMED).reason is CheckpointRejectionReason.CONSUMED
    assert PreflightIntegrityError(PreflightIntegrityReason.SEAL_INVALID).reason.value == "seal_invalid"
    assert "not ready" in str(PreflightNotReadyError())


# --------------------------------------------------------------------------- EntryIdentity


def test_entry_identity_valid_and_same_identity():
    assert same_identity(FILE, EntryIdentity(1, 3, EntryType.FILE, 10, 1_000))
    assert not same_identity(FILE, EntryIdentity(1, 3, EntryType.FILE, 11, 1_000))
    assert not same_identity(FILE, EntryIdentity(1, 3, EntryType.FILE, 10, 1_001))
    assert not same_identity(FILE, EntryIdentity(2, 3, EntryType.FILE, 10, 1_000))
    assert same_identity(DIR, EntryIdentity(1, 2, EntryType.DIRECTORY, None, None))
    assert not same_identity(DIR, EntryIdentity(1, 9, EntryType.DIRECTORY, None, None))
    assert not same_identity(DIR, "not-an-identity")


class _Int(int):
    pass


@pytest.mark.parametrize("fields", [
    (True, 2, EntryType.DIRECTORY, None, None),
    (-1, 2, EntryType.DIRECTORY, None, None),
    (1, 0, EntryType.DIRECTORY, None, None),
    (1, _Int(2), EntryType.DIRECTORY, None, None),
    (1, 2, "directory", None, None),
    (1, 2, EntryType.DIRECTORY, 0, None),
    (1, 2, EntryType.FILE, None, 5),
    (1, 2, EntryType.FILE, -1, 5),
    (1, 2, EntryType.FILE, 5, 1.5),
])
def test_entry_identity_rejects_invalid(fields):
    with pytest.raises(ExecutionModelError):
        EntryIdentity(*fields)


# --------------------------------------------------------------------------- units / effects


def test_execution_unit_shapes():
    ExecutionUnit(ExecutionStep.MATERIALIZE_EXTRAFANART, PathRole.EXTRAFANART_FILE, ArtifactKind.EXTRAFANART, 3)
    ExecutionUnit(ExecutionStep.CREATE_DIRECTORY, PathRole.TARGET_DIRECTORY, None, None)
    for bad in [
        (ExecutionStep.CREATE_DIRECTORY, PathRole.NFO, None, None),
        (ExecutionStep.MATERIALIZE_NFO, PathRole.NFO, None, None),
        (ExecutionStep.MATERIALIZE_NFO, PathRole.NFO, ArtifactKind.NFO, 1),
        (ExecutionStep.MATERIALIZE_EXTRAFANART, PathRole.EXTRAFANART_FILE, ArtifactKind.EXTRAFANART, 0),
        (ExecutionStep.MATERIALIZE_EXTRAFANART, PathRole.EXTRAFANART_FILE, ArtifactKind.EXTRAFANART, None),
        ("create_directory", PathRole.TARGET_DIRECTORY, None, None),
    ]:
        with pytest.raises(ExecutionModelError):
            ExecutionUnit(*bad)


def _effect(**overrides):
    fields = dict(kind=EffectKind.ARTIFACT_PUBLISHED, role=PathRole.NFO, path="/x/a.nfo", identity=FILE, size=10,
                  sha256=HEX64, artifact_kind=ArtifactKind.NFO, ordinal=None)
    fields.update(overrides)
    return CompletedEffect(**fields)


def test_completed_effect_valid_shapes():
    _effect()
    _effect(role=PathRole.EXTRAFANART_FILE, artifact_kind=ArtifactKind.EXTRAFANART, ordinal=4)
    _effect(kind=EffectKind.TARGET_DIRECTORY_CREATED, role=PathRole.TARGET_DIRECTORY, identity=DIR, size=None,
            sha256=None, artifact_kind=None)
    _effect(kind=EffectKind.EXTRAFANART_DIRECTORY_CREATED, role=PathRole.EXTRAFANART_DIRECTORY, identity=DIR,
            size=None, sha256=None, artifact_kind=None)
    _effect(kind=EffectKind.MEDIA_PUBLISHED, role=PathRole.TARGET_MEDIA, sha256=None, artifact_kind=None)
    _effect(kind=EffectKind.SOURCE_REMOVED, role=PathRole.SOURCE, identity=None, size=None, sha256=None,
            artifact_kind=None)


@pytest.mark.parametrize("overrides", [
    dict(path=""),
    dict(sha256="B" * 64),
    dict(sha256=None),
    dict(role=PathRole.POSTER),
    dict(identity=DIR),
    dict(ordinal=1),
    dict(artifact_kind=ArtifactKind.EXTRAFANART, role=PathRole.EXTRAFANART_FILE, ordinal=None),
    dict(kind=EffectKind.SOURCE_REMOVED, role=PathRole.SOURCE, artifact_kind=None, sha256=None, size=None),
    dict(kind=EffectKind.MEDIA_PUBLISHED, role=PathRole.TARGET_MEDIA, artifact_kind=None, size=None),
    dict(kind=EffectKind.TARGET_DIRECTORY_CREATED, role=PathRole.TARGET_DIRECTORY, identity=FILE,
         artifact_kind=None, size=None, sha256=None),
    dict(kind="artifact_published"),
])
def test_completed_effect_rejects_invalid(overrides):
    with pytest.raises(ExecutionModelError):
        _effect(**overrides)


def test_expected_effect_and_leftover_and_blocker():
    ExpectedEffect(EffectKind.ARTIFACT_PUBLISHED, PathRole.EXTRAFANART_FILE, "/x", ArtifactKind.EXTRAFANART, 1)
    with pytest.raises(ExecutionModelError):
        ExpectedEffect(EffectKind.ARTIFACT_PUBLISHED, PathRole.NFO, "/x", ArtifactKind.NFO, 1)
    LeftoverTemporary(PathRole.TARGET_DIRECTORY, ".fc2tmp-" + "0" * 32 + ".part")
    for role, name in [(PathRole.SOURCE, ".fc2tmp-" + "0" * 32 + ".part"),
                       (PathRole.TARGET_DIRECTORY, ".fc2tmp-" + "A" * 32 + ".part"),
                       (PathRole.TARGET_DIRECTORY, "other.part")]:
        with pytest.raises(ExecutionModelError):
            LeftoverTemporary(role, name)
    PreflightBlocker(PreflightBlockReason.SOURCE_INACCESSIBLE, PathRole.SOURCE, 13)
    for bad in [("x", PathRole.SOURCE), (PreflightBlockReason.SOURCE_MISSING, PathRole.SOURCE, True),
                (PreflightBlockReason.SOURCE_MISSING, PathRole.SOURCE, None, 0)]:
        with pytest.raises(ExecutionModelError):
            PreflightBlocker(*bad)


def test_execution_failure_rules():
    ExecutionFailure(ExecutionStep.MOVE_MEDIA, ExecutionFailureKind.MEDIA_WRITE_FAILED, TransferStage.WRITE,
                     errno=28)
    ExecutionFailure(ExecutionStep.MATERIALIZE_EXTRAFANART, ExecutionFailureKind.ARTIFACT_WRITE_FAILED,
                     write_stage="flush", artifact_kind=ArtifactKind.EXTRAFANART, ordinal=2)
    ExecutionFailure(ExecutionStep.MATERIALIZE_NFO, ExecutionFailureKind.ARTIFACT_CLEANUP_FAILED,
                     artifact_kind=ArtifactKind.NFO, target_published=True)
    for kwargs in [
        dict(write_stage="flush"),
        dict(kind=ExecutionFailureKind.ARTIFACT_WRITE_FAILED, write_stage="sync"),
        dict(target_published=True),
        dict(kind=ExecutionFailureKind.ARTIFACT_CLEANUP_FAILED, target_published=1),
        dict(errno=True),
        dict(artifact_kind=ArtifactKind.NFO, ordinal=1),
        dict(stage="write"),
    ]:
        fields = dict(step=ExecutionStep.MOVE_MEDIA, kind=ExecutionFailureKind.MEDIA_TRANSFER_FAILED)
        fields.update(kwargs)
        with pytest.raises(ExecutionModelError):
            ExecutionFailure(**fields)


# --------------------------------------------------------------------------- checkpoint / preflight / result


def _dir_effect():
    return CompletedEffect(EffectKind.TARGET_DIRECTORY_CREATED, PathRole.TARGET_DIRECTORY, "/lib/FC2-1", DIR,
                           None, None, None, None)


def _checkpoint(**overrides):
    fields = dict(checkpoint_id=HEX32, plan_fingerprint=HEX64, manifest_fingerprint=HEX64,
                  library_root_identity=DIR, source_identity=FILE, transfer_mode=TransferMode.SAME_VOLUME,
                  target_directory_identity=DIR, extrafanart_directory_identity=None,
                  completed_effects=(_dir_effect(),), leftover_temporaries=(), seal=HEX64)
    fields.update(overrides)
    return ExecutionCheckpoint(**fields)


def test_checkpoint_model_and_repr_hides_seal():
    cp = _checkpoint(seal="c" * 64)
    assert "c" * 64 not in repr(cp)
    with pytest.raises(dataclasses.FrozenInstanceError):
        cp.checkpoint_id = "b" * 32
    assert not hasattr(cp, "__dict__")


@pytest.mark.parametrize("overrides", [
    dict(checkpoint_id="A" * 32), dict(plan_fingerprint="x"), dict(library_root_identity=FILE),
    dict(source_identity=DIR), dict(target_directory_identity=FILE), dict(extrafanart_directory_identity=FILE),
    dict(transfer_mode="same_volume"), dict(completed_effects=()), dict(completed_effects=[_dir_effect()]),
    dict(leftover_temporaries=("x",)), dict(seal="z" * 64),
])
def test_checkpoint_rejects_invalid(overrides):
    with pytest.raises(ExecutionModelError):
        _checkpoint(**overrides)


def _preflight_fields(tmp_path, **overrides):
    plan = make_plan(str(tmp_path / "lib"))
    fields = dict(preflight_id=HEX32, mode=PreflightMode.FRESH, plan=plan, artifacts=make_manifest(plan),
                  checkpoint=None, plan_fingerprint=HEX64, manifest_fingerprint=HEX64, ready=True, blockers=(),
                  library_root_identity=DIR, source_identity=FILE, transfer_mode=TransferMode.SAME_VOLUME,
                  completed_units=(), pending_units=(), skipped_steps=(), seal=HEX64)
    fields.update(overrides)
    return fields


def test_preflight_model_rules(tmp_path):
    preflight = ExecutionPreflight(**_preflight_fields(tmp_path, seal="d" * 64))
    assert "d" * 64 not in repr(preflight)
    assert r"\xff" not in repr(preflight) and "poster" in repr(preflight)  # content excluded from repr
    blocker = PreflightBlocker(PreflightBlockReason.SOURCE_MISSING, PathRole.SOURCE)
    ExecutionPreflight(**_preflight_fields(tmp_path, ready=False, blockers=(blocker,)))
    ExecutionPreflight(**_preflight_fields(tmp_path, skipped_steps=(ExecutionStep.MATERIALIZE_THUMB,)))
    for overrides in [
        dict(ready=False), dict(blockers=(blocker,)), dict(ready=1), dict(plan="plan"),
        dict(artifacts=list(make_manifest(make_plan(str(tmp_path / "lib"))))), dict(mode=PreflightMode.RESUME),
        dict(checkpoint=_checkpoint()), dict(library_root_identity=FILE), dict(source_identity=DIR),
        dict(skipped_steps=(ExecutionStep.MOVE_MEDIA,)), dict(pending_units=["x"]), dict(preflight_id="short"),
    ]:
        with pytest.raises(ExecutionModelError):
            ExecutionPreflight(**_preflight_fields(tmp_path, **overrides))


def test_preflight_mode_resume_requires_checkpoint(tmp_path):
    ExecutionPreflight(**_preflight_fields(tmp_path, mode=PreflightMode.RESUME, checkpoint=_checkpoint()))


def _result(**overrides):
    fields = dict(status=ExecutionStatus.SUCCESS, preflight_id=HEX32, mode=PreflightMode.FRESH,
                  transfer_mode=TransferMode.SAME_VOLUME, completed_effects=(_dir_effect(),), new_effect_count=1,
                  failure=None, checkpoint=None, leftover_temporaries=(), media_sha256=None, skipped_steps=())
    fields.update(overrides)
    return ExecutionResult(**fields)


def test_result_status_invariants():
    failure = ExecutionFailure(ExecutionStep.CREATE_DIRECTORY, ExecutionFailureKind.DIRECTORY_CREATE_FAILED)
    _result()
    _result(status=ExecutionStatus.PARTIAL, failure=failure, checkpoint=_checkpoint())
    _result(status=ExecutionStatus.FAILED, failure=failure, completed_effects=(), new_effect_count=0)
    for overrides in [
        dict(failure=failure),
        dict(status=ExecutionStatus.PARTIAL, failure=failure),
        dict(status=ExecutionStatus.FAILED, failure=failure),
        dict(status=ExecutionStatus.FAILED, failure=failure, completed_effects=(), new_effect_count=0,
             checkpoint=_checkpoint()),
        dict(completed_effects=(), new_effect_count=0),
        dict(new_effect_count=2),
        dict(new_effect_count=True),
        dict(media_sha256="xyz"),
    ]:
        with pytest.raises(ExecutionModelError):
            _result(**overrides)


def test_sealed_helper_builds_a_valid_sealed_checkpoint():
    fields = {f.name: getattr(_checkpoint(), f.name) for f in dataclasses.fields(ExecutionCheckpoint)
              if f.name != "seal"}
    cp = sealed(ExecutionCheckpoint, **fields)
    assert cp.seal != HEX64 and len(cp.seal) == 64
