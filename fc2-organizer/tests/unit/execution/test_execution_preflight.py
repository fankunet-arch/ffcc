"""P4-C7 S1: READ-ONLY FRESH preflight on the real filesystem (contract sections 5, 10-17)."""

from __future__ import annotations

import dataclasses
import errno
import os
import secrets

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
    ExecutionInputError,
    ExecutionPreflight,
    PathRole,
    PlanGraphError,
    PreflightBlocker,
    PreflightMode,
    TransferMode,
    preflight_execution,
)
from fc2_organizer.execution import PreflightBlockReason as B
from fc2_organizer.execution.seal import register_consumption, sealed, verify_seal
from fc2_organizer.execution.validation import expected_units, skipped_steps
from fc2_organizer.planning import OrganizePlan

from ._builders import NUMBER, make_manifest, scene, tampered
from ._helpers import (
    CallCounter,
    fingerprint_tree,
    inject,
    lstat_failing_for,
    lstat_rewriting,
    trap_mutations,
    try_junction,
    try_symlink,
)


def _reasons(preflight: ExecutionPreflight) -> list[tuple[B, PathRole]]:
    return [(b.reason, b.role) for b in preflight.blockers]


# --------------------------------------------------------------------------- happy path


def test_ready_fresh_preflight_snapshots_and_units(tmp_path):
    s = scene(tmp_path, extra=2)
    preflight = preflight_execution(s.plan, s.artifacts)
    assert type(preflight) is ExecutionPreflight and verify_seal(preflight)
    assert preflight.ready and preflight.blockers == ()
    assert preflight.mode is PreflightMode.FRESH and preflight.checkpoint is None
    assert preflight.plan is s.plan and preflight.artifacts is s.artifacts
    lib_st, src_st = os.lstat(s.library_root), os.lstat(s.source_path)
    assert preflight.library_root_identity == EntryIdentity(lib_st.st_dev, lib_st.st_ino, EntryType.DIRECTORY,
                                                            None, None)
    assert preflight.source_identity == EntryIdentity(src_st.st_dev, src_st.st_ino, EntryType.FILE,
                                                      len(s.content), src_st.st_mtime_ns)
    assert preflight.transfer_mode is TransferMode.SAME_VOLUME
    assert preflight.completed_units == ()
    assert preflight.pending_units == expected_units(s.plan, s.artifacts)
    assert preflight.skipped_steps == skipped_steps(s.artifacts) == ()


def test_preflight_is_deterministic_apart_from_id_and_seal(tmp_path):
    s = scene(tmp_path)
    a, b = preflight_execution(s.plan, s.artifacts), preflight_execution(s.plan, s.artifacts)
    assert a.preflight_id != b.preflight_id and a.seal != b.seal
    strip = {"preflight_id": "0" * 32, "seal": "0" * 64}
    assert dataclasses.replace(a, **strip) == dataclasses.replace(b, **strip)


def test_unicode_paths_and_zero_byte_media(tmp_path):
    s = scene(tmp_path, content=b"", source_name="ダウンロード 😀.MKV", library_name="ライブラリ",
              poster=False, fanart=False, thumb=False)
    preflight = preflight_execution(s.plan, s.artifacts)
    assert preflight.ready and preflight.source_identity.size == 0
    assert len(preflight.skipped_steps) == 3


# --------------------------------------------------------------------------- zero mutation


def test_preflight_performs_zero_mutation_and_never_opens_content(tmp_path, monkeypatch):
    s = scene(tmp_path, extra=3)
    before = fingerprint_tree(tmp_path)
    trap = trap_mutations(monkeypatch)
    preflight = preflight_execution(s.plan, s.artifacts)
    monkeypatch.undo()
    assert trap.calls == []
    assert preflight.ready
    assert fingerprint_tree(tmp_path) == before
    assert not os.path.lexists(s.plan.target_directory.absolute_path)


def test_blocked_preflights_also_perform_zero_mutation(tmp_path, monkeypatch):
    s = scene(tmp_path, make_library=False, make_source=False)
    before = fingerprint_tree(tmp_path)
    trap = trap_mutations(monkeypatch)
    preflight = preflight_execution(s.plan, s.artifacts)
    monkeypatch.undo()
    assert trap.calls == [] and not preflight.ready
    assert fingerprint_tree(tmp_path) == before
    assert not os.path.exists(s.library_root)  # the library root is never created


def test_only_lstat_probes_are_made(tmp_path, monkeypatch):
    s = scene(tmp_path)
    counter = CallCounter(monkeypatch)
    preflight_execution(s.plan, s.artifacts)
    assert counter.paths == [s.library_root, s.source_path, s.plan.target_directory.absolute_path]


# --------------------------------------------------------------------------- library root


def test_library_root_missing_blocks_and_skips_target_probe(tmp_path, monkeypatch):
    s = scene(tmp_path, make_library=False)
    counter = CallCounter(monkeypatch)
    preflight = preflight_execution(s.plan, s.artifacts)
    assert _reasons(preflight) == [(B.LIBRARY_ROOT_MISSING, PathRole.LIBRARY_ROOT)]
    assert s.plan.target_directory.absolute_path not in counter.paths
    assert preflight.library_root_identity is None and preflight.transfer_mode is None


def test_library_root_below_a_file_is_missing(tmp_path):
    (tmp_path / "blocker").write_bytes(b"f")
    s = scene(tmp_path, library_name=os.path.join("blocker", "library"), make_library=False)
    assert _reasons(preflight_execution(s.plan, s.artifacts)) == [(B.LIBRARY_ROOT_MISSING, PathRole.LIBRARY_ROOT)]


def test_library_root_that_is_a_file(tmp_path):
    s = scene(tmp_path, make_library=False)
    open(s.library_root, "wb").close()
    assert _reasons(preflight_execution(s.plan, s.artifacts)) == [
        (B.LIBRARY_ROOT_NOT_DIRECTORY, PathRole.LIBRARY_ROOT)]


def test_library_root_junction_is_a_link(tmp_path):
    real = tmp_path / "real-library"
    real.mkdir()
    s = scene(tmp_path, make_library=False)
    try_junction(tmp_path / "library", real)
    assert _reasons(preflight_execution(s.plan, s.artifacts)) == [(B.LIBRARY_ROOT_IS_LINK, PathRole.LIBRARY_ROOT)]


def test_library_root_symlink_is_a_link(tmp_path):
    real = tmp_path / "real-library"
    real.mkdir()
    s = scene(tmp_path, make_library=False)
    try_symlink(tmp_path / "library", real, target_is_directory=True)
    assert _reasons(preflight_execution(s.plan, s.artifacts)) == [(B.LIBRARY_ROOT_IS_LINK, PathRole.LIBRARY_ROOT)]


def test_library_root_inaccessible_carries_errno_only(tmp_path, monkeypatch):
    s = scene(tmp_path)
    inject(monkeypatch, lstat=lstat_failing_for(s.library_root, PermissionError(errno.EACCES, "denied",
                                                                                 s.library_root)))
    preflight = preflight_execution(s.plan, s.artifacts)
    assert preflight.blockers == (PreflightBlocker(B.LIBRARY_ROOT_INACCESSIBLE, PathRole.LIBRARY_ROOT,
                                                   errno.EACCES),)
    assert s.library_root not in repr(preflight.blockers)


def test_library_root_with_inode_zero_is_identity_unavailable(tmp_path, monkeypatch):
    s = scene(tmp_path)
    inject(monkeypatch, lstat=lstat_rewriting(s.library_root, st_ino=0))
    preflight = preflight_execution(s.plan, s.artifacts)
    assert _reasons(preflight) == [(B.IDENTITY_UNAVAILABLE, PathRole.LIBRARY_ROOT)]


# --------------------------------------------------------------------------- source


def test_source_missing(tmp_path):
    s = scene(tmp_path, make_source=False)
    preflight = preflight_execution(s.plan, s.artifacts)
    assert _reasons(preflight) == [(B.SOURCE_MISSING, PathRole.SOURCE)]
    assert preflight.source_identity is None and preflight.transfer_mode is None


def test_source_is_a_directory(tmp_path):
    s = scene(tmp_path, make_source=False)
    os.mkdir(s.source_path)
    assert _reasons(preflight_execution(s.plan, s.artifacts)) == [(B.SOURCE_NOT_REGULAR_FILE, PathRole.SOURCE)]


def test_source_symlink_is_a_link(tmp_path):
    s = scene(tmp_path, make_source=False)
    real = tmp_path / "real.mp4"
    real.write_bytes(s.content)
    try_symlink(tmp_path / "downloads" / "random-name.MP4", real)
    assert _reasons(preflight_execution(s.plan, s.artifacts)) == [(B.SOURCE_IS_LINK, PathRole.SOURCE)]


def test_source_junction_is_a_link(tmp_path):
    s = scene(tmp_path, make_source=False)
    real = tmp_path / "real-dir"
    real.mkdir()
    try_junction(tmp_path / "downloads" / "random-name.MP4", real)
    assert _reasons(preflight_execution(s.plan, s.artifacts)) == [(B.SOURCE_IS_LINK, PathRole.SOURCE)]


def test_source_size_changed_since_discovery(tmp_path):
    s = scene(tmp_path)
    with open(s.source_path, "ab") as handle:
        handle.write(b"+")
    assert _reasons(preflight_execution(s.plan, s.artifacts)) == [(B.SOURCE_SIZE_MISMATCH, PathRole.SOURCE)]


def test_source_inaccessible_and_inode_zero(tmp_path, monkeypatch):
    s = scene(tmp_path)
    inject(monkeypatch, lstat=lstat_failing_for(s.source_path, OSError(errno.EIO, "io")))
    assert preflight_execution(s.plan, s.artifacts).blockers == (
        PreflightBlocker(B.SOURCE_INACCESSIBLE, PathRole.SOURCE, errno.EIO),)
    monkeypatch.undo()
    inject(monkeypatch, lstat=lstat_rewriting(s.source_path, st_ino=0))
    assert _reasons(preflight_execution(s.plan, s.artifacts)) == [(B.IDENTITY_UNAVAILABLE, PathRole.SOURCE)]


# --------------------------------------------------------------------------- target directory (fresh)


def _assert_target_exists_blocks(s):
    target = s.plan.target_directory.absolute_path
    before = os.lstat(target)
    preflight = preflight_execution(s.plan, s.artifacts)
    assert _reasons(preflight) == [(B.TARGET_DIRECTORY_EXISTS, PathRole.TARGET_DIRECTORY)]
    after = os.lstat(target)
    assert (after.st_ino, after.st_mtime_ns) == (before.st_ino, before.st_mtime_ns)
    return preflight


def test_existing_file_at_target_directory(tmp_path):
    s = scene(tmp_path)
    with open(s.plan.target_directory.absolute_path, "wb") as handle:
        handle.write(b"occupant")
    _assert_target_exists_blocks(s)
    with open(s.plan.target_directory.absolute_path, "rb") as handle:
        assert handle.read() == b"occupant"


def test_existing_empty_directory_is_never_adopted(tmp_path):
    s = scene(tmp_path)
    os.mkdir(s.plan.target_directory.absolute_path)
    _assert_target_exists_blocks(s)
    assert os.listdir(s.plan.target_directory.absolute_path) == []


def test_existing_symlink_and_dangling_symlink_at_target(tmp_path):
    s = scene(tmp_path)
    target = s.plan.target_directory.absolute_path
    try_symlink(tmp_path / "library" / NUMBER, tmp_path / "does-not-exist", target_is_directory=True)
    assert os.path.lexists(target) and not os.path.exists(target)
    _assert_target_exists_blocks(s)


def test_existing_junction_at_target(tmp_path):
    s = scene(tmp_path)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    try_junction(tmp_path / "library" / NUMBER, elsewhere)
    _assert_target_exists_blocks(s)
    assert os.listdir(elsewhere) == []


def test_target_directory_inaccessible(tmp_path, monkeypatch):
    s = scene(tmp_path)
    target = s.plan.target_directory.absolute_path
    inject(monkeypatch, lstat=lstat_failing_for(target, PermissionError(errno.EACCES, "denied")))
    assert preflight_execution(s.plan, s.artifacts).blockers == (
        PreflightBlocker(B.TARGET_DIRECTORY_INACCESSIBLE, PathRole.TARGET_DIRECTORY, errno.EACCES),)


def test_target_directory_not_a_directory_component(tmp_path, monkeypatch):
    s = scene(tmp_path)
    target = s.plan.target_directory.absolute_path
    inject(monkeypatch, lstat=lstat_failing_for(target, NotADirectoryError(errno.ENOTDIR, "not a dir")))
    assert _reasons(preflight_execution(s.plan, s.artifacts)) == [
        (B.LIBRARY_ROOT_NOT_DIRECTORY, PathRole.LIBRARY_ROOT)]


# --------------------------------------------------------------------------- multiple blockers


def test_multiple_blockers_are_all_listed_in_the_frozen_order(tmp_path):
    s = scene(tmp_path, make_source=False)
    os.mkdir(s.plan.target_directory.absolute_path)
    preflight = preflight_execution(s.plan, s.artifacts)
    assert _reasons(preflight) == [(B.SOURCE_MISSING, PathRole.SOURCE),
                                   (B.TARGET_DIRECTORY_EXISTS, PathRole.TARGET_DIRECTORY)]
    assert not preflight.ready
    assert preflight.pending_units == expected_units(s.plan, s.artifacts)  # preview still sees the units


def test_library_root_and_source_blockers_together(tmp_path):
    s = scene(tmp_path, make_library=False, make_source=False)
    assert _reasons(preflight_execution(s.plan, s.artifacts)) == [
        (B.LIBRARY_ROOT_MISSING, PathRole.LIBRARY_ROOT), (B.SOURCE_MISSING, PathRole.SOURCE)]


def test_blockers_carry_no_path_text(tmp_path):
    s = scene(tmp_path, make_source=False)
    os.mkdir(s.plan.target_directory.absolute_path)
    rendered = repr(preflight_execution(s.plan, s.artifacts).blockers)
    assert str(tmp_path) not in rendered and "downloads" not in rendered


# --------------------------------------------------------------------------- transfer-mode prediction


def test_cross_volume_prediction_through_the_device_seam(tmp_path, monkeypatch):
    s = scene(tmp_path)
    source_inode = os.lstat(s.source_path).st_ino
    inject(monkeypatch, device_of=lambda st: st.st_dev + 1 if st.st_ino == source_inode else st.st_dev)
    preflight = preflight_execution(s.plan, s.artifacts)
    assert preflight.ready and preflight.transfer_mode is TransferMode.CROSS_VOLUME
    assert preflight.source_identity.device == os.lstat(s.source_path).st_dev + 1


# --------------------------------------------------------------------------- input errors before any I/O


class _Calls:
    names: list[str] = []


class HookPlan(OrganizePlan):
    def __getattribute__(self, name):
        _Calls.names.append(name)
        return object.__getattribute__(self, name)


def test_input_type_errors_happen_before_any_filesystem_access(tmp_path, monkeypatch):
    s = scene(tmp_path)
    counter = CallCounter(monkeypatch)
    hostile = HookPlan(**{f.name: getattr(s.plan, f.name) for f in dataclasses.fields(OrganizePlan)})
    _Calls.names.clear()

    class Manifest(tuple):
        pass

    for args in [(hostile, s.artifacts), ("plan", s.artifacts), (s.plan, list(s.artifacts)),
                 (s.plan, Manifest(s.artifacts)), (s.plan, s.artifacts, "checkpoint")]:
        with pytest.raises(ExecutionInputError):
            preflight_execution(*args)
    assert _Calls.names == [] and counter.paths == []


def test_contract_errors_happen_before_any_filesystem_access(tmp_path, monkeypatch):
    s = scene(tmp_path)
    counter = CallCounter(monkeypatch)
    with pytest.raises(PlanGraphError):
        preflight_execution(tampered(s.plan, operations=s.plan.operations[:6]), s.artifacts)
    with pytest.raises(ArtifactManifestError):
        preflight_execution(s.plan, s.artifacts[1:])
    with pytest.raises(ArtifactManifestError):
        preflight_execution(s.plan, make_manifest(s.plan, extra=1)[:1] + make_manifest(s.plan, extra=1)[:1])
    assert counter.paths == []


# --------------------------------------------------------------------------- checkpoint handling in S1


def _checkpoint(s, **overrides):
    directory = EntryIdentity(1, 2, EntryType.DIRECTORY, None, None)
    fields = dict(
        checkpoint_id=secrets.token_hex(16), plan_fingerprint="a" * 64, manifest_fingerprint="b" * 64,
        library_root_identity=directory, source_identity=EntryIdentity(1, 3, EntryType.FILE, 1, 1),
        transfer_mode=TransferMode.SAME_VOLUME, target_directory_identity=directory,
        extrafanart_directory_identity=None,
        completed_effects=(CompletedEffect(EffectKind.TARGET_DIRECTORY_CREATED, PathRole.TARGET_DIRECTORY,
                                           s.plan.target_directory.absolute_path, directory, None, None, None,
                                           None),),
        leftover_temporaries=(),
    )
    fields.update(overrides)
    return fields


def _assert_checkpoint_refused(s, checkpoint, reason, monkeypatch):
    counter = CallCounter(monkeypatch)
    with pytest.raises(CheckpointError) as info:
        preflight_execution(s.plan, s.artifacts, checkpoint)
    assert info.value.reason is reason and counter.paths == []


def test_forged_checkpoint_is_refused_as_seal_invalid(tmp_path, monkeypatch):
    s = scene(tmp_path)
    forged = ExecutionCheckpoint(**_checkpoint(s), seal="f" * 64)
    _assert_checkpoint_refused(s, forged, CheckpointRejectionReason.SEAL_INVALID, monkeypatch)


def test_tampered_sealed_checkpoint_is_refused(tmp_path, monkeypatch):
    s = scene(tmp_path)
    cp = sealed(ExecutionCheckpoint, **_checkpoint(s))
    forged = tampered(cp, transfer_mode=TransferMode.CROSS_VOLUME)
    _assert_checkpoint_refused(s, forged, CheckpointRejectionReason.SEAL_INVALID, monkeypatch)


def test_consumed_checkpoint_is_refused_as_consumed(tmp_path, monkeypatch):
    s = scene(tmp_path)
    cp = sealed(ExecutionCheckpoint, **_checkpoint(s))
    assert register_consumption((cp.checkpoint_id,))
    _assert_checkpoint_refused(s, cp, CheckpointRejectionReason.CONSUMED, monkeypatch)


def test_s1_refuses_even_a_correctly_sealed_checkpoint(tmp_path, monkeypatch):
    # S1 cannot issue checkpoints, so no checkpoint was issued by an execution: fail closed (plan S1 item 7).
    s = scene(tmp_path)
    cp = sealed(ExecutionCheckpoint, **_checkpoint(s))
    _assert_checkpoint_refused(s, cp, CheckpointRejectionReason.SEAL_INVALID, monkeypatch)


def test_preflight_never_consumes_anything(tmp_path):
    s = scene(tmp_path)
    first = preflight_execution(s.plan, s.artifacts)
    second = preflight_execution(s.plan, s.artifacts)
    assert first.ready and second.ready
    assert register_consumption((first.preflight_id,))  # not registered by preflight_execution
