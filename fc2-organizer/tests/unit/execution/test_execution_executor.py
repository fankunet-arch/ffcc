"""P4-C7 S5: integrated single-item executor (contract sections 4, 8, 9, 14.5, 15.4, 15.5, 17, 27-30; plan S5)."""

from __future__ import annotations

import dataclasses
import errno
import hashlib
import os
import stat
from pathlib import Path

import pytest

from fc2_organizer.execution import (
    CheckpointError,
    CheckpointRejectionReason,
    EffectKind,
    ExecutionFailure,
    ExecutionFailureKind,
    ExecutionInputError,
    ExecutionPreflight,
    ExecutionStatus,
    ExecutionStep,
    PlanGraphError,
    PreflightBlockReason,
    PreflightIntegrityError,
    PreflightIntegrityReason,
    PreflightMode,
    PreflightNotReadyError,
    TransferMode,
    execute_filesystem,
    preflight_execution,
)
from fc2_organizer.execution import _fs, executor, transfer
from fc2_organizer.execution import seal as seal_module
from fc2_organizer.execution.seal import ClaimIntegrityError, is_consumed, sealed
from fc2_organizer.execution.validation import expected_effects
from fc2_organizer.materialization import ArtifactKind, ArtifactWriteError, ArtifactWriteStage, MaterializationError

from ._builders import MAIN_COMBOS, make_manifest, scene, tampered
from ._helpers import (
    TRANSFERS,
    MaterializeSpy,
    UnitInterrupter,
    assert_source_not_lost,
    expected_library_layout,
    failing,
    inject,
    inject_p4c6,
    isolated_source_claims,  # noqa: F401 -- autouse fixture: per-test claim registry isolation
    lstat_rewriting,
    sha256_of_file,
    trap_every_filesystem_access,
    tree_layout,
    try_junction,
    use_transfer,
)

F = ExecutionFailureKind
MEDIA = b"media-bytes \x00\xff" * 41


def _scene(tmp_path, monkeypatch=None, transfer_kind="native", *, content=MEDIA, **options):
    if monkeypatch is not None:
        use_transfer(monkeypatch, transfer_kind)
    return scene(tmp_path, content=content, **options)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _assert_success(s, result, *, mode, preflight):
    E = expected_effects(s.plan, s.artifacts)
    assert result.status is ExecutionStatus.SUCCESS and result.failure is None and result.checkpoint is None
    assert [(e.kind, e.role, e.path, e.artifact_kind, e.ordinal) for e in result.completed_effects] == [
        (e.kind, e.role, e.path, e.artifact_kind, e.ordinal) for e in E]
    assert result.new_effect_count == len(E) and result.preflight_id == preflight.preflight_id
    assert result.mode is PreflightMode.FRESH and result.transfer_mode is mode
    assert result.media_sha256 == (_sha(s.content) if mode is TransferMode.CROSS_VOLUME else None)
    assert result.leftover_temporaries == () and result.skipped_steps == preflight.skipped_steps
    assert tree_layout(s.library_root) == expected_library_layout(s.plan, s.artifacts, s.content)
    assert not os.path.lexists(s.source_path)
    assert os.path.isdir(s.plan.extrafanart_directory.absolute_path)
    assert_source_not_lost(s.source_path, s.plan.target_media_path.absolute_path, _sha(s.content))


# --------------------------------------------------------------------------- SUCCESS matrix


@pytest.mark.parametrize("transfer_kind", TRANSFERS)
@pytest.mark.parametrize("extra", [0, 1, 13])
@pytest.mark.parametrize("combo", MAIN_COMBOS, ids=lambda c: "p%d-f%d-t%d" % c)
def test_success_matrix(tmp_path, monkeypatch, transfer_kind, extra, combo):
    poster, fanart, thumb = combo
    s = _scene(tmp_path, monkeypatch, transfer_kind, poster=poster, fanart=fanart, thumb=thumb, extra=extra)
    preflight = preflight_execution(s.plan, s.artifacts)
    assert preflight.ready
    result = execute_filesystem(preflight)
    mode = TransferMode.CROSS_VOLUME if transfer_kind == "cross_volume" else TransferMode.SAME_VOLUME
    _assert_success(s, result, mode=mode, preflight=preflight)
    skipped = [step for present, step in zip(combo, (ExecutionStep.MATERIALIZE_POSTER,
                                                     ExecutionStep.MATERIALIZE_FANART,
                                                     ExecutionStep.MATERIALIZE_THUMB)) if not present]
    assert list(result.skipped_steps) == skipped


@pytest.mark.parametrize("transfer_kind", TRANSFERS)
def test_zero_byte_media(tmp_path, monkeypatch, transfer_kind):
    s = _scene(tmp_path, monkeypatch, transfer_kind, content=b"", extra=1)
    preflight = preflight_execution(s.plan, s.artifacts)
    result = execute_filesystem(preflight)
    mode = TransferMode.CROSS_VOLUME if transfer_kind == "cross_volume" else TransferMode.SAME_VOLUME
    _assert_success(s, result, mode=mode, preflight=preflight)
    assert os.path.getsize(s.plan.target_media_path.absolute_path) == 0


@pytest.mark.parametrize("source_name,library_name", [
    ("下载-かな-😀.MP4", "库-ライブラリ"),
    ("été-nfd.mkv", "bibliothèque"),
    ("été-nfc.Mp4", "bibliothèque"),
])
def test_unicode_paths(tmp_path, source_name, library_name):
    s = _scene(tmp_path, source_name=source_name, library_name=library_name, extra=2)
    preflight = preflight_execution(s.plan, s.artifacts)
    _assert_success(s, execute_filesystem(preflight), mode=TransferMode.SAME_VOLUME, preflight=preflight)


def _unc_path(path: Path) -> str | None:
    if os.name != "nt":
        return None
    drive, rest = os.path.splitdrive(str(path))
    if len(drive) != 2:
        return None
    unc = "\\\\localhost\\" + drive[0] + "$" + rest
    try:
        return unc if os.path.isdir(unc) else None
    except OSError:
        return None


def test_unc_library_root(tmp_path):
    unc_root = _unc_path(tmp_path)
    if unc_root is None:
        pytest.skip("UNC library root: NOT EXECUTED (no Windows administrative share \\\\localhost\\<drive>$ here)")
    s = scene(Path(unc_root), content=MEDIA, extra=1)
    preflight = preflight_execution(s.plan, s.artifacts)
    if not preflight.ready:
        pytest.skip("UNC library root: NOT EXECUTED (the administrative share is not usable on this host)")
    _assert_success(s, execute_filesystem(preflight), mode=preflight.transfer_mode, preflight=preflight)


# --------------------------------------------------------------------------- actual transfer mode (section 17)


def _device_seam(monkeypatch, predicate):
    real = _fs._FS.device_of
    inject(monkeypatch, device_of=lambda st: real(st) + 7 if predicate(st) else real(st))


def test_actual_mode_is_decided_against_the_new_target_directory(tmp_path, monkeypatch):
    s = _scene(tmp_path, extra=1)
    preflight = preflight_execution(s.plan, s.artifacts)
    assert preflight.transfer_mode is TransferMode.SAME_VOLUME
    library_inode = os.lstat(s.library_root).st_ino
    # After preflight: every directory except the library root reports another device (a mount point).
    _device_seam(monkeypatch, lambda st: stat.S_ISDIR(st.st_mode) and st.st_ino != library_inode)
    result = execute_filesystem(preflight)
    assert result.status is ExecutionStatus.SUCCESS and result.transfer_mode is TransferMode.CROSS_VOLUME
    assert result.media_sha256 == _sha(MEDIA)
    assert result.completed_effects[1].sha256 == _sha(MEDIA)


def test_predicted_cross_volume_but_same_device_target_moves(tmp_path, monkeypatch):
    s = _scene(tmp_path, extra=1)
    library_inode = os.lstat(s.library_root).st_ino
    _device_seam(monkeypatch, lambda st: st.st_ino == library_inode)
    preflight = preflight_execution(s.plan, s.artifacts)
    assert preflight.transfer_mode is TransferMode.CROSS_VOLUME
    result = execute_filesystem(preflight)
    assert result.status is ExecutionStatus.SUCCESS and result.transfer_mode is TransferMode.SAME_VOLUME
    assert result.media_sha256 is None


def test_exdev_fallback_is_the_reported_mode(tmp_path, monkeypatch):
    s = _scene(tmp_path, extra=1)
    for op in ("rename", "link"):  # whichever same-volume primitive this host uses
        real = getattr(_fs._FS, op)
        inject(monkeypatch, **{op: (lambda real_op: lambda a, b: (_ for _ in ()).throw(OSError(errno.EXDEV, "x"))
                                    if a == s.source_path else real_op(a, b))(real)})
    result = execute_filesystem(preflight_execution(s.plan, s.artifacts))
    assert result.status is ExecutionStatus.SUCCESS and result.transfer_mode is TransferMode.CROSS_VOLUME
    assert result.media_sha256 == _sha(MEDIA)


# --------------------------------------------------------------------------- pre-filesystem gate


def _ready(tmp_path, **options):
    s = _scene(tmp_path, **options)
    preflight = preflight_execution(s.plan, s.artifacts)
    assert preflight.ready
    return s, preflight


def _untouched(s):
    assert os.path.isfile(s.source_path) and not os.path.lexists(s.plan.target_directory.absolute_path)


def _reject(monkeypatch, preflight, error_type):
    with monkeypatch.context() as m:
        trap = trap_every_filesystem_access(m)
        with pytest.raises(error_type) as info:
            execute_filesystem(preflight)
    assert trap.calls == []  # zero filesystem access
    return info.value


def test_strict_type(tmp_path, monkeypatch):
    s, preflight = _ready(tmp_path)
    for bad in (None, object(), "preflight", (preflight,), dataclasses.replace):
        _reject(monkeypatch, bad, ExecutionInputError)
    _untouched(s)
    assert not is_consumed(preflight.preflight_id)


def test_not_ready_is_refused_without_access_or_consumption_and_a_new_preflight_works(tmp_path, monkeypatch):
    s = _scene(tmp_path, extra=1)
    os.rename(s.source_path, s.source_path + ".away")
    blocked = preflight_execution(s.plan, s.artifacts)
    assert not blocked.ready
    _reject(monkeypatch, blocked, PreflightNotReadyError)
    assert not is_consumed(blocked.preflight_id)
    os.rename(s.source_path + ".away", s.source_path)  # the filesystem is repaired
    fresh = preflight_execution(s.plan, s.artifacts)
    assert fresh.ready and execute_filesystem(fresh).status is ExecutionStatus.SUCCESS
    assert not is_consumed(blocked.preflight_id)


@pytest.mark.parametrize("field,value", [
    ("seal", "0" * 64),
    ("ready", False),
    ("preflight_id", "f" * 32),
    ("plan_fingerprint", "0" * 64),
    ("transfer_mode", TransferMode.CROSS_VOLUME),
])
def test_rewritten_preflight_field_is_seal_invalid(tmp_path, monkeypatch, field, value):
    s, preflight = _ready(tmp_path)
    forged = tampered(preflight, **{field: value})
    error = _reject(monkeypatch, forged, PreflightIntegrityError)
    assert error.reason is PreflightIntegrityReason.SEAL_INVALID
    assert not is_consumed(forged.preflight_id) and not is_consumed(preflight.preflight_id)
    _untouched(s)


def test_plan_or_manifest_rewritten_after_preflight_is_refused(tmp_path, monkeypatch):
    s, preflight = _ready(tmp_path, extra=1)
    object.__setattr__(s.plan, "canonical_number", "FC2-7654321")
    error = _reject(monkeypatch, preflight, PreflightIntegrityError)
    assert error.reason is PreflightIntegrityReason.SEAL_INVALID
    (tmp_path / "second").mkdir()
    s2, preflight2 = _ready(tmp_path / "second", extra=1)
    object.__setattr__(s2.artifacts[0], "content", s2.artifacts[0].content + b" ")
    error = _reject(monkeypatch, preflight2, PreflightIntegrityError)
    assert error.reason is PreflightIntegrityReason.SEAL_INVALID
    assert not is_consumed(preflight.preflight_id) and not is_consumed(preflight2.preflight_id)


def _resealed(preflight, **changes):
    fields = {f.name: getattr(preflight, f.name) for f in dataclasses.fields(preflight) if f.name != "seal"}
    fields.update(changes)
    return sealed(ExecutionPreflight, **fields)


def test_validly_sealed_preflight_with_other_fingerprints_is_fingerprint_mismatch(tmp_path, monkeypatch):
    s, preflight = _ready(tmp_path, extra=1)
    for field in ("plan_fingerprint", "manifest_fingerprint"):
        forged = _resealed(preflight, **{field: "0" * 64})
        error = _reject(monkeypatch, forged, PreflightIntegrityError)
        assert error.reason is PreflightIntegrityReason.FINGERPRINT_MISMATCH
        assert not is_consumed(forged.preflight_id)
    _untouched(s)


def test_validly_sealed_preflight_with_a_broken_plan_fails_structural_revalidation(tmp_path, monkeypatch):
    s, preflight = _ready(tmp_path)
    broken = tampered(s.plan, operations=s.plan.operations[:-1])
    forged = _resealed(preflight, plan=broken)
    _reject(monkeypatch, forged, PlanGraphError)
    assert not is_consumed(forged.preflight_id)


def test_second_execution_is_consumed_without_filesystem_access(tmp_path, monkeypatch):
    s, preflight = _ready(tmp_path, extra=1)
    assert execute_filesystem(preflight).status is ExecutionStatus.SUCCESS
    before = tree_layout(s.library_root)
    error = _reject(monkeypatch, preflight, PreflightIntegrityError)
    assert error.reason is PreflightIntegrityReason.CONSUMED
    assert tree_layout(s.library_root) == before


def test_consumed_checkpoint_is_checkpoint_error_not_preflight_error(tmp_path, monkeypatch):
    s = _scene(tmp_path, extra=1)
    inject_p4c6(monkeypatch, write=failing(OSError(errno.ENOSPC, "full")))
    first = execute_filesystem(preflight_execution(s.plan, s.artifacts))
    assert first.status is ExecutionStatus.PARTIAL
    monkeypatch.undo()
    a = preflight_execution(s.plan, s.artifacts, first.checkpoint)
    b = preflight_execution(s.plan, s.artifacts, first.checkpoint)  # a second preflight of the same checkpoint
    assert execute_filesystem(a).status is ExecutionStatus.SUCCESS
    with pytest.raises(CheckpointError) as info:
        execute_filesystem(b)
    assert info.value.reason is CheckpointRejectionReason.CONSUMED
    assert not is_consumed(b.preflight_id)


# --------------------------------------------------------------------------- FAILED (nothing happened)


def _assert_failed(s, result, kind, step=ExecutionStep.CREATE_DIRECTORY):
    assert result.status is ExecutionStatus.FAILED and result.checkpoint is None
    assert result.completed_effects == () and result.new_effect_count == 0
    assert result.failure.kind is kind and result.failure.step is step
    assert result.transfer_mode is None and result.media_sha256 is None


def _stale(s, how):
    library, source, target = s.library_root, s.source_path, s.plan.target_directory.absolute_path
    if how == "library_removed":
        os.rename(library, library + "-away")
    elif how == "library_replaced_by_junction":
        os.rename(library, library + "-away")
        try_junction(Path(library), Path(library + "-away"))
    elif how == "library_replaced_by_directory":
        os.rename(library, library + "-away")
        os.mkdir(library)
    elif how == "source_appended":
        with open(source, "ab") as handle:
            handle.write(b"more")
    elif how == "source_missing":
        os.rename(source, source + ".away")
    elif how == "source_replaced":
        os.rename(source, source + ".away")
        with open(source, "wb") as handle:
            handle.write(MEDIA)
    elif how == "target_created":
        os.mkdir(target)


STALE = {
    "library_removed": F.LIBRARY_ROOT_CHANGED, "library_replaced_by_junction": F.LIBRARY_ROOT_CHANGED,
    "library_replaced_by_directory": F.LIBRARY_ROOT_CHANGED, "source_appended": F.SOURCE_CHANGED,
    "source_missing": F.SOURCE_MISSING, "source_replaced": F.SOURCE_CHANGED, "target_created": F.TARGET_CONFLICT,
}


@pytest.mark.parametrize("how", sorted(STALE))
def test_stale_state_after_preflight_fails_before_any_mutation(tmp_path, monkeypatch, how):
    s, preflight = _ready(tmp_path, extra=1)
    _stale(s, how)
    units = UnitInterrupter(monkeypatch)
    result = execute_filesystem(preflight)
    _assert_failed(s, result, STALE[how])
    assert units.calls == []  # no unit ran: the read-only revalidation stopped first
    assert is_consumed(preflight.preflight_id)
    original = s.source_path + ".away" if how in ("source_missing", "source_replaced") else s.source_path
    expected = _sha(MEDIA + b"more") if how == "source_appended" else _sha(MEDIA)
    assert_source_not_lost(original, s.plan.target_media_path.absolute_path, expected)
    if how == "target_created":
        assert os.listdir(s.plan.target_directory.absolute_path) == []  # never adopted, never touched


def test_revalidation_is_read_only(tmp_path, monkeypatch):
    s, preflight = _ready(tmp_path)
    _stale(s, "source_appended")
    trap = _MutationTrap(monkeypatch)
    result = execute_filesystem(preflight)
    assert result.failure.kind is F.SOURCE_CHANGED and trap.calls == []


class _MutationTrap:
    def __init__(self, monkeypatch):
        self.calls = []
        ops = {}
        for name in ("mkdir", "rename", "link", "unlink", "write", "fsync"):
            ops[name] = self._trap(name)
        inject(monkeypatch, **ops)
        MaterializeSpy(monkeypatch, replacement=self._trap("materialize_artifact"))

    def _trap(self, name):
        def op(*_args, **_kwargs):
            self.calls.append(name)
            raise AssertionError(name)
        return op


def test_source_identity_unavailable_at_execution_is_failed_source_changed(tmp_path, monkeypatch):
    # S5-R-01: the ready preflight snapshotted the source; at execution time the source is still a regular file
    # but reports no usable identity (st_ino == 0 -> SnapshotRefused(REFUSED_IDENTITY_UNAVAILABLE)).
    s, preflight = _ready(tmp_path, extra=1)
    inject(monkeypatch, lstat=lstat_rewriting(s.source_path, st_ino=0))
    assert isinstance(_fs.snapshot(s.source_path), _fs.SnapshotRefused)
    trap = _MutationTrap(monkeypatch)
    units = UnitInterrupter(monkeypatch)
    result = execute_filesystem(preflight)  # a typed result, never a KeyError
    assert result.status is ExecutionStatus.FAILED and result.failure is not None
    assert result.failure.kind is F.SOURCE_CHANGED and result.failure.step is ExecutionStep.CREATE_DIRECTORY
    assert result.completed_effects == () and result.new_effect_count == 0 and result.checkpoint is None
    assert units.calls == [] and trap.calls == []  # no unit, no mkdir / rename / link / unlink / materialize
    _untouched(s)
    assert is_consumed(preflight.preflight_id)  # consumption happened before the revalidation; never undone
    with pytest.raises(PreflightIntegrityError) as info:
        execute_filesystem(preflight)
    assert info.value.reason is PreflightIntegrityReason.CONSUMED
    assert_source_not_lost(s.source_path, s.plan.target_media_path.absolute_path, _sha(MEDIA))


def test_identity_unavailable_blocker_maps_to_source_changed_only():
    mapping = executor._BLOCKER_FAILURE
    assert mapping[PreflightBlockReason.IDENTITY_UNAVAILABLE] is F.SOURCE_CHANGED
    assert set(mapping) == set(PreflightBlockReason)  # every blocker the revalidation can report is typed
    assert mapping[PreflightBlockReason.SOURCE_MISSING] is F.SOURCE_MISSING
    assert mapping[PreflightBlockReason.TARGET_DIRECTORY_EXISTS] is F.TARGET_CONFLICT
    assert mapping[PreflightBlockReason.LIBRARY_ROOT_MISSING] is F.LIBRARY_ROOT_CHANGED


def test_directory_create_failure_is_failed(tmp_path, monkeypatch):
    s, preflight = _ready(tmp_path)
    inject(monkeypatch, mkdir=failing(PermissionError(errno.EACCES, "denied")))
    units = UnitInterrupter(monkeypatch)
    result = execute_filesystem(preflight)
    _assert_failed(s, result, F.DIRECTORY_CREATE_FAILED)
    assert result.failure.errno == errno.EACCES and units.calls == ["create_target_directory"]
    assert_source_not_lost(s.source_path, s.plan.target_media_path.absolute_path, _sha(MEDIA))


def test_mkdir_race_is_target_conflict(tmp_path, monkeypatch):
    s, preflight = _ready(tmp_path)
    real = _fs._FS.mkdir

    def racing(path, mode):
        os.mkdir(path)  # another actor wins between the revalidation and the exclusive mkdir
        return real(path, mode)

    inject(monkeypatch, mkdir=racing)
    result = execute_filesystem(preflight)
    _assert_failed(s, result, F.TARGET_CONFLICT)
    assert os.listdir(s.plan.target_directory.absolute_path) == []


def test_u1_mkdir_succeeded_but_not_an_owned_directory_records_no_effect(tmp_path, monkeypatch):
    # Ruling: our directory is not visible at the final location and has no identity -> nothing recordable.
    s, preflight = _ready(tmp_path)
    real = _fs._FS.mkdir
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()

    def replaced(path, mode):
        real(path, mode)
        os.rmdir(path)
        try_junction(Path(path), elsewhere)

    inject(monkeypatch, mkdir=replaced)
    result = execute_filesystem(preflight)
    _assert_failed(s, result, F.TARGET_DIRECTORY_CHANGED)
    assert result.failure.stage.name == "PUBLISH_VERIFY"
    assert os.listdir(elsewhere) == [] and os.path.isfile(s.source_path)


# --------------------------------------------------------------------------- PARTIAL (first failure stops)


def _assert_partial(s, result, kind, done_kinds, step):
    assert result.status is ExecutionStatus.PARTIAL and result.failure.kind is kind and result.failure.step is step
    assert [e.kind for e in result.completed_effects] == done_kinds
    assert result.new_effect_count == len(done_kinds)
    checkpoint = result.checkpoint
    assert checkpoint is not None and checkpoint.completed_effects == result.completed_effects
    assert checkpoint.leftover_temporaries == result.leftover_temporaries
    E = expected_effects(s.plan, s.artifacts)
    assert [(e.kind, e.path) for e in result.completed_effects] == [(e.kind, e.path) for e in E[:len(done_kinds)]]


def test_u2_failure_is_partial_and_stops(tmp_path, monkeypatch):
    s, preflight = _ready(tmp_path, extra=1)
    inject(monkeypatch, rename=failing(PermissionError(errno.EPERM, "x")),
           link=failing(PermissionError(errno.EPERM, "x")))
    units = UnitInterrupter(monkeypatch)
    result = execute_filesystem(preflight)
    _assert_partial(s, result, F.MEDIA_TRANSFER_FAILED, [EffectKind.TARGET_DIRECTORY_CREATED],
                    ExecutionStep.MOVE_MEDIA)
    assert units.calls == ["create_target_directory", "transfer_media"]
    assert result.checkpoint.transfer_mode is TransferMode.SAME_VOLUME
    assert_source_not_lost(s.source_path, s.plan.target_media_path.absolute_path, _sha(MEDIA))


def test_artifact_failure_is_partial_and_stops(tmp_path, monkeypatch):
    s, preflight = _ready(tmp_path, extra=2)
    poster = next(r for r in s.artifacts if r.kind is ArtifactKind.POSTER)
    real = executor.materialize_artifact

    def failing_poster(request):
        if request is poster:
            raise ArtifactWriteError(ArtifactWriteStage.WRITE, errno.ENOSPC)
        return real(request)

    spy = MaterializeSpy(monkeypatch, replacement=failing_poster)
    units = UnitInterrupter(monkeypatch)
    result = execute_filesystem(preflight)
    _assert_partial(s, result, F.ARTIFACT_WRITE_FAILED,
                    [EffectKind.TARGET_DIRECTORY_CREATED, EffectKind.MEDIA_PUBLISHED, EffectKind.SOURCE_REMOVED,
                     EffectKind.ARTIFACT_PUBLISHED], ExecutionStep.MATERIALIZE_POSTER)
    assert [r.kind for r in spy.requests] == [ArtifactKind.NFO, ArtifactKind.POSTER]  # nothing after POSTER
    assert units.calls.count("_execute_artifact_unit") == 2 and "create_extrafanart_directory" not in units.calls
    assert result.failure.write_stage == "write" and result.failure.artifact_kind is ArtifactKind.POSTER
    assert_source_not_lost(s.source_path, s.plan.target_media_path.absolute_path, _sha(MEDIA))


def test_u7_failure_is_partial_and_stops(tmp_path, monkeypatch):
    s, preflight = _ready(tmp_path, extra=2)
    real = _fs._FS.mkdir
    extrafanart = s.plan.extrafanart_directory.absolute_path
    inject(monkeypatch, mkdir=lambda p, m: (_ for _ in ()).throw(PermissionError(errno.EACCES, "x"))
           if p == extrafanart else real(p, m))
    spy = MaterializeSpy(monkeypatch)
    result = execute_filesystem(preflight)
    assert result.status is ExecutionStatus.PARTIAL and result.failure.kind is F.DIRECTORY_CREATE_FAILED
    assert result.failure.step is ExecutionStep.ENSURE_EXTRAFANART_DIRECTORY
    assert all(r.kind is not ArtifactKind.EXTRAFANART for r in spy.requests)
    assert result.checkpoint.extrafanart_directory_identity is None


def test_extrafanart_failure_in_the_middle_keeps_order_and_stops(tmp_path, monkeypatch):
    s, preflight = _ready(tmp_path, extra=4)
    second = next(r for r in s.artifacts if r.kind is ArtifactKind.EXTRAFANART and r.ordinal == 2)
    real = executor.materialize_artifact
    spy = MaterializeSpy(monkeypatch, replacement=lambda r: (_ for _ in ()).throw(
        ArtifactWriteError(ArtifactWriteStage.CLOSE, errno.EIO)) if r is second else real(r))
    result = execute_filesystem(preflight)
    assert result.failure.kind is F.ARTIFACT_WRITE_FAILED and result.failure.ordinal == 2
    assert [r.ordinal for r in spy.requests if r.kind is ArtifactKind.EXTRAFANART] == [1, 2]
    assert result.checkpoint.extrafanart_directory_identity is not None
    assert [e.ordinal for e in result.completed_effects if e.kind is EffectKind.ARTIFACT_PUBLISHED][-1] == 1


# --------------------------------------------------------------------------- fatal / raw propagation


@pytest.mark.parametrize("at", range(11))  # U1, U2, NFO, POSTER, FANART, THUMB, U7, extras 1..3, and past the end
def test_keyboard_interrupt_at_every_unit_boundary(tmp_path, monkeypatch, at):
    s, preflight = _ready(tmp_path, extra=3)
    total = len(preflight.pending_units)
    assert total == 10
    exc = KeyboardInterrupt("boundary %d" % at)
    units = UnitInterrupter(monkeypatch, at=at, exc=exc)
    if at >= total:
        assert execute_filesystem(preflight).status is ExecutionStatus.SUCCESS
        return
    with pytest.raises(KeyboardInterrupt) as info:
        execute_filesystem(preflight)
    assert info.value is exc and is_consumed(preflight.preflight_id)
    assert len(units.calls) == at + 1 and units.calls[-1].endswith("!")
    target = s.plan.target_directory.absolute_path
    assert os.path.isdir(target) == (at >= 1)  # effects that happened are kept, none are invented
    assert os.path.exists(s.plan.target_media_path.absolute_path) == (at >= 2)
    assert os.path.exists(s.plan.nfo_path.absolute_path) == (at >= 3)
    assert os.path.isdir(s.plan.extrafanart_directory.absolute_path) == (at >= 7)
    assert_source_not_lost(s.source_path, s.plan.target_media_path.absolute_path, _sha(MEDIA))


class CustomFatal(BaseException):
    pass


class FutureMaterializationError(MaterializationError):
    pass


@pytest.mark.parametrize("make", [RuntimeError, MemoryError, SystemExit, GeneratorExit, CustomFatal,
                                  FutureMaterializationError], ids=lambda t: t.__name__)
def test_foreign_and_unmapped_exceptions_propagate_without_a_result(tmp_path, monkeypatch, make):
    s, preflight = _ready(tmp_path, extra=1)
    exc = make("inside a unit")
    MaterializeSpy(monkeypatch, replacement=failing(exc))
    with pytest.raises(BaseException) as info:
        execute_filesystem(preflight)
    assert info.value is exc and exc.__cause__ is None
    assert is_consumed(preflight.preflight_id)
    assert sha256_of_file(s.plan.target_media_path.absolute_path) == _sha(MEDIA)  # no rollback
    assert_source_not_lost(s.source_path, s.plan.target_media_path.absolute_path, _sha(MEDIA))


def test_s4r1_unknown_leftovers_oserror_propagates_without_a_result(tmp_path, monkeypatch):
    s, preflight = _ready(tmp_path, extra=1)
    inject_p4c6(monkeypatch, write=failing(OSError(errno.ENOSPC, "full")),
                unlink=failing(PermissionError(errno.EACCES, "busy")))
    real = _fs._FS.listdir
    listings = []
    exc = PermissionError(errno.EACCES, "after listing")

    def listdir(path):
        listings.append(path)
        if len(listings) == 2:
            raise exc
        return real(path)

    inject(monkeypatch, listdir=listdir)
    with pytest.raises(OSError) as info:
        execute_filesystem(preflight)
    assert info.value is exc
    assert is_consumed(preflight.preflight_id)
    assert_source_not_lost(s.source_path, s.plan.target_media_path.absolute_path, _sha(MEDIA))


# --------------------------------------------------------------------------- S5-R1: ownership integrity (15.6 item 5)


def _foreign_owner(key_identity, name):
    """Wraps an executor claim transition so that, just before it runs, another owner holds the key: the
    owner-matched primitive then really fails (a genuine token / lineage mismatch, not a stubbed False)."""
    real = getattr(executor, name)
    other = "f" * 32

    def transition(identity, *args):
        with seal_module._CLAIMS_LOCK:
            seal_module._CLAIMS[(identity.device, identity.inode)] = ("active", other)
        return real(identity, *args)

    return transition, other


def _link_unlink_failing(monkeypatch, source):
    monkeypatch.setattr(transfer, "_SAME_VOLUME_STRATEGY", "link")
    real = _fs._FS.unlink
    inject(monkeypatch, unlink=lambda p: (_ for _ in ()).throw(PermissionError(errno.EACCES, "busy"))
           if p == source else real(p))


def test_reserve_that_does_not_take_effect_fails_closed(tmp_path, monkeypatch):
    s, preflight = _ready(tmp_path)
    _link_unlink_failing(monkeypatch, s.source_path)
    transition, other = _foreign_owner(preflight.source_identity, "claim_reserve")
    monkeypatch.setattr(executor, "claim_reserve", transition)
    with pytest.raises(ClaimIntegrityError):
        execute_filesystem(preflight)  # never a PARTIAL whose reservation silently failed
    key = (preflight.source_identity.device, preflight.source_identity.inode)
    assert seal_module._CLAIMS[key] == ("active", other)  # registry unchanged by our (stale) poison attempt
    assert_source_not_lost(s.source_path, s.plan.target_media_path.absolute_path, _sha(MEDIA))


def test_release_that_does_not_take_effect_fails_closed(tmp_path, monkeypatch):
    s, preflight = _ready(tmp_path)
    transition, other = _foreign_owner(preflight.source_identity, "claim_release")
    monkeypatch.setattr(executor, "claim_release", transition)
    with pytest.raises(ClaimIntegrityError) as info:
        execute_filesystem(preflight)  # never claims SUCCESS when its release did not happen
    assert "f" * 32 not in str(info.value) and s.source_path not in str(info.value)
    key = (preflight.source_identity.device, preflight.source_identity.inode)
    assert seal_module._CLAIMS[key] == ("active", other)


def test_owned_reservation_hand_over_that_does_not_take_effect_fails_closed(tmp_path, monkeypatch):
    # Integrity failure, NOT a claim conflict: the lineage genuinely owns RESERVED(cp1) when the resume starts
    # (asserted below); the resume fails its revalidation before U2 (so no take-over is attempted) and owes the
    # RESERVED(cp1) -> RESERVED(new) hand-over, which a foreign owner appearing at that moment defeats.
    s, preflight = _ready(tmp_path)
    _link_unlink_failing(monkeypatch, s.source_path)
    first = execute_filesystem(preflight)
    cp1 = first.checkpoint
    Path(s.plan.target_directory.absolute_path, "late").write_bytes(b"x")
    resume = preflight_execution(s.plan, s.artifacts, cp1)
    assert not resume.ready
    Path(s.plan.target_directory.absolute_path, "late").unlink()
    resume = preflight_execution(s.plan, s.artifacts, cp1)
    Path(s.plan.target_directory.absolute_path, "late").write_bytes(b"x")  # revalidation will fail (PARTIAL)
    key = (cp1.source_identity.device, cp1.source_identity.inode)
    assert seal_module._CLAIMS[key] == ("reserved", cp1.checkpoint_id)  # owned at the start of the resume
    transition, other = _foreign_owner(cp1.source_identity, "claim_hand_over")
    monkeypatch.setattr(executor, "claim_hand_over", transition)
    transfers = []
    monkeypatch.setattr(executor, "transfer_media", lambda *a, **k: transfers.append(a) or None)
    with pytest.raises(ClaimIntegrityError):
        execute_filesystem(resume)
    assert transfers == []  # U2 never ran: this is the owed hand-over path, not the take-over conflict
    assert seal_module._CLAIMS[key] == ("active", other)
    assert is_consumed(cp1.checkpoint_id)
