"""P4-C7 S2: checkpoint issuance and RESUME preflight (contract sections 14-15; construction plan S2).

Partial states are built for real by the TESTS-ONLY orchestration ``_builders.advance`` (production directory
helpers + P4-C6 ``materialize_artifact`` + ``issue_checkpoint``); there is no executor in S2.
"""

from __future__ import annotations

import os
import stat

import pytest

from fc2_organizer import execution
from fc2_organizer.execution import (
    CheckpointError,
    CompletedEffect,
    EffectKind,
    EntryIdentity,
    EntryType,
    ExecutionCheckpoint,
    ExecutionStep,
    LeftoverTemporary,
    PathRole,
    PreflightBlocker,
    PreflightMode,
    TransferMode,
    preflight_execution,
)
from fc2_organizer.execution import CheckpointRejectionReason as C
from fc2_organizer.execution import PreflightBlockReason as B
from fc2_organizer.execution import seal as seal_module
from fc2_organizer.execution.seal import is_consumed, issue_checkpoint, register_consumption, verify_seal
from fc2_organizer.execution.validation import expected_effects, expected_units, skipped_steps
from fc2_organizer.materialization import ArtifactKind

from ._builders import NUMBER, TEMP_NAME, advance, checkpoint_fields, make_manifest, make_plan, scene, tampered
from ._helpers import (
    CallCounter,
    fingerprint_tree,
    inject,
    lstat_rewriting,
    trap_all_io,
    trap_mutations_allowing_reads,
    try_junction,
    try_symlink,
)


def _reasons(preflight) -> list[tuple[B, PathRole]]:
    return [(b.reason, b.role) for b in preflight.blockers]


def _reissue(checkpoint: ExecutionCheckpoint, **changes) -> ExecutionCheckpoint:
    fields = checkpoint_fields(checkpoint)
    fields.update(changes)
    return issue_checkpoint(**{k: v for k, v in fields.items() if k != "checkpoint_id"})


def _index(s, kind, artifact_kind=None, ordinal=None) -> int:
    for i, slot in enumerate(expected_effects(s.plan, s.artifacts)):
        if slot.kind is kind and slot.artifact_kind is artifact_kind and slot.ordinal == ordinal:
            return i
    raise AssertionError("no such effect")


def _after(s, kind, artifact_kind=None, ordinal=None) -> int:
    """Prefix length that includes the given effect."""
    return _index(s, kind, artifact_kind, ordinal) + 1


# --------------------------------------------------------------------------- issuance


def test_issue_checkpoint_round_trip(tmp_path):
    s = scene(tmp_path)
    cp = advance(s, 1)
    assert type(cp) is ExecutionCheckpoint and verify_seal(cp)
    assert len(cp.checkpoint_id) == 32 and cp.checkpoint_id == cp.checkpoint_id.lower()
    other = _reissue(cp)
    assert other.checkpoint_id != cp.checkpoint_id and verify_seal(other)
    assert other.completed_effects == cp.completed_effects
    assert "issue_checkpoint" not in execution.__all__ and not hasattr(execution, "issue_checkpoint")
    assert "issue_checkpoint" not in seal_module.__all__


# --------------------------------------------------------------------------- contract layer (zero I/O)


def _refused(s, checkpoint, reason, monkeypatch, plan=None, artifacts=None):
    trap = trap_all_io(monkeypatch)
    with pytest.raises(CheckpointError) as info:
        preflight_execution(plan or s.plan, artifacts or s.artifacts, checkpoint)
    monkeypatch.undo()
    assert info.value.reason is reason, info.value.reason
    assert trap.calls == []  # ZERO filesystem access
    assert info.value.__cause__ is None and info.value.__context__ is None


def test_seal_invalid(tmp_path, monkeypatch):
    s = scene(tmp_path)
    cp = advance(s, 1)
    _refused(s, tampered(cp, transfer_mode=TransferMode.CROSS_VOLUME), C.SEAL_INVALID, monkeypatch)
    _refused(s, ExecutionCheckpoint(**checkpoint_fields(cp), seal="f" * 64), C.SEAL_INVALID, monkeypatch)


def test_consumed(tmp_path, monkeypatch):
    s = scene(tmp_path)
    cp = advance(s, 1)
    assert register_consumption((cp.checkpoint_id,))
    _refused(s, cp, C.CONSUMED, monkeypatch)


def test_plan_mismatch(tmp_path, monkeypatch):
    s = scene(tmp_path)
    cp = advance(s, 1)
    other = make_plan(s.library_root, s.source_path, number="FC2-7654321", extension=".mp4", size=len(s.content))
    _refused(s, cp, C.PLAN_MISMATCH, monkeypatch, plan=other, artifacts=make_manifest(other))


def test_manifest_mismatch_on_a_single_byte(tmp_path, monkeypatch):
    s = scene(tmp_path)
    cp = advance(s, 1)
    changed = make_manifest(s.plan, nfo_text="<movie>x</movie>")
    _refused(s, cp, C.MANIFEST_MISMATCH, monkeypatch, artifacts=changed)
    first = s.artifacts[1]
    flipped = (s.artifacts[0], tampered(first, content=bytes([first.content[0] ^ 1]) + first.content[1:])) \
        + s.artifacts[2:]
    _refused(s, cp, C.MANIFEST_MISMATCH, monkeypatch, artifacts=flipped)


def test_check_order_seal_then_consumed_then_plan(tmp_path, monkeypatch):
    s = scene(tmp_path)
    cp = advance(s, 1)
    other = make_plan(s.library_root, s.source_path, number="FC2-7654321", extension=".mp4", size=len(s.content))
    register_consumption((cp.checkpoint_id,))
    _refused(s, tampered(cp, plan_fingerprint="0" * 64), C.SEAL_INVALID, monkeypatch)
    _refused(s, cp, C.CONSUMED, monkeypatch, plan=other, artifacts=make_manifest(other))


def _non_prefix_variants(s, cp):
    effects = cp.completed_effects
    directory = effects[0]
    media = effects[1]
    nfo = effects[3]
    other_dir = EntryIdentity(7, 7, EntryType.DIRECTORY, None, None)
    wrong_path = CompletedEffect(nfo.kind, nfo.role, nfo.path + "x", nfo.identity, nfo.size, nfo.sha256,
                                 nfo.artifact_kind, nfo.ordinal)
    wrong_kind = CompletedEffect(nfo.kind, PathRole.POSTER, s.plan.poster_path.absolute_path, nfo.identity,
                                 nfo.size, nfo.sha256, ArtifactKind.POSTER, None)
    return {
        "reordered": dict(completed_effects=(directory, effects[2], media) + effects[3:]),
        "skipped_effect": dict(completed_effects=(directory,) + effects[2:]),
        "wrong_path": dict(completed_effects=effects[:3] + (wrong_path,)),
        "wrong_artifact_kind_and_role": dict(completed_effects=effects[:3] + (wrong_kind,)),
        "not_starting_with_directory": dict(completed_effects=effects[1:]),
        "directory_identity_unbound": dict(target_directory_identity=other_dir),
        "extrafanart_identity_without_effect": dict(extrafanart_directory_identity=other_dir),
        "extrafanart_leftover_without_directory": dict(leftover_temporaries=(
            LeftoverTemporary(PathRole.EXTRAFANART_DIRECTORY, TEMP_NAME),)),
    }


def test_effects_not_prefix_constructions(tmp_path, monkeypatch):
    s = scene(tmp_path, extra=2)
    cp = advance(s, 4)
    variants = _non_prefix_variants(s, cp)
    assert len(variants) >= 6
    for name, changes in variants.items():
        _refused(s, _reissue(cp, **changes), C.EFFECTS_NOT_PREFIX, monkeypatch)


def test_effects_not_prefix_wrong_extrafanart_ordinal_and_too_long(tmp_path, monkeypatch):
    s = scene(tmp_path, poster=False, fanart=False, thumb=False, extra=2)
    total = len(expected_effects(s.plan, s.artifacts))
    cp = advance(s, total - 1)  # everything except extrafanart #2
    last = cp.completed_effects[-1]
    assert last.ordinal == 1
    wrong = CompletedEffect(last.kind, last.role, last.path, last.identity, last.size, last.sha256,
                            last.artifact_kind, 2)
    _refused(s, _reissue(cp, completed_effects=cp.completed_effects[:-1] + (wrong,)), C.EFFECTS_NOT_PREFIX,
             monkeypatch)
    too_long = cp.completed_effects + (last, last)
    _refused(s, _reissue(cp, completed_effects=too_long), C.EFFECTS_NOT_PREFIX, monkeypatch)


def test_already_complete(tmp_path, monkeypatch):
    s = scene(tmp_path, extra=1)
    cp = advance(s, len(expected_effects(s.plan, s.artifacts)))
    _refused(s, cp, C.ALREADY_COMPLETE, monkeypatch)


# --------------------------------------------------------------------------- resume at every partial point


def _expected_split(s, done):
    units = list(expected_units(s.plan, s.artifacts))
    completed, pending, remaining = [], [], done
    for unit in units:
        need = 2 if unit.step is ExecutionStep.MOVE_MEDIA else 1
        if not pending and remaining >= need:
            completed.append(unit)
            remaining -= need
        else:
            pending.append(unit)
    return tuple(completed), tuple(pending)


@pytest.mark.parametrize("options", [dict(poster=False, fanart=False, thumb=False),
                                     dict(extra=3), dict(poster=True, fanart=False, thumb=True, extra=1)])
def test_resume_is_ready_and_exact_at_every_partial_point(tmp_path, monkeypatch, options):
    total = len(expected_effects(*_shape(tmp_path, options)))
    checked = 0
    for done in range(1, total):
        root = tmp_path / f"p{done}"
        root.mkdir()
        s = scene(root, **options)
        cp = advance(s, done)
        before = fingerprint_tree(root)
        trap, opened = trap_mutations_allowing_reads(monkeypatch)
        preflight = preflight_execution(s.plan, s.artifacts, cp)
        monkeypatch.undo()
        assert trap.calls == [] and fingerprint_tree(root) == before  # ZERO mutation
        assert preflight.ready, (done, preflight.blockers)
        assert preflight.mode is PreflightMode.RESUME and preflight.checkpoint is cp
        assert (preflight.completed_units, preflight.pending_units) == _expected_split(s, done)
        assert preflight.skipped_steps == skipped_steps(s.artifacts)
        assert preflight.source_identity == cp.source_identity and preflight.transfer_mode is cp.transfer_mode
        assert verify_seal(preflight) and not is_consumed(cp.checkpoint_id)  # preflight never consumes
        artifacts_done = [e.path for e in cp.completed_effects if e.kind is EffectKind.ARTIFACT_PUBLISHED]
        assert sorted(opened) == sorted(artifacts_done)  # only artifacts are re-read, never the media
        checked += 1
    assert checked == total - 1


def _shape(tmp_path, options):
    root = tmp_path / "shape"
    root.mkdir()
    s = scene(root, **options)
    return s.plan, s.artifacts


def test_move_media_half_done_keeps_move_media_pending(tmp_path):
    s = scene(tmp_path)
    cp = advance(s, _after(s, EffectKind.MEDIA_PUBLISHED))
    preflight = preflight_execution(s.plan, s.artifacts, cp)
    assert preflight.ready
    assert [u.step for u in preflight.completed_units] == [ExecutionStep.CREATE_DIRECTORY]
    assert preflight.pending_units[0].step is ExecutionStep.MOVE_MEDIA


# --------------------------------------------------------------------------- filesystem blockers


@pytest.fixture
def mid(tmp_path):
    """NFO + poster + extrafanart directory + extrafanart #1 done; #2 pending."""
    s = scene(tmp_path, fanart=False, thumb=False, extra=2)
    return s, advance(s, _after(s, EffectKind.ARTIFACT_PUBLISHED, ArtifactKind.EXTRAFANART, 1))


def test_library_root_changed(mid, monkeypatch):
    s, cp = mid
    inject(monkeypatch, lstat=lstat_rewriting(s.library_root, st_ino=os.lstat(s.library_root).st_ino + 1))
    assert _reasons(preflight_execution(s.plan, s.artifacts, cp)) == [(B.LIBRARY_ROOT_CHANGED,
                                                                       PathRole.LIBRARY_ROOT)]


def test_library_root_replaced_on_disk(mid):
    s, cp = mid
    os.rename(s.library_root, str(s.root / "old-library"))
    os.mkdir(s.library_root)
    reasons = _reasons(preflight_execution(s.plan, s.artifacts, cp))
    assert reasons[0] == (B.LIBRARY_ROOT_CHANGED, PathRole.LIBRARY_ROOT)
    assert (B.TARGET_DIRECTORY_CHANGED, PathRole.TARGET_DIRECTORY) in reasons
    assert not os.path.exists(s.plan.target_directory.absolute_path)  # nothing recreated


def test_target_directory_replaced_or_missing(mid):
    s, cp = mid
    target = s.plan.target_directory.absolute_path
    os.rename(target, str(s.root / "moved"))
    assert _reasons(preflight_execution(s.plan, s.artifacts, cp)) == [(B.TARGET_DIRECTORY_CHANGED,
                                                                       PathRole.TARGET_DIRECTORY)]
    os.mkdir(target)
    assert _reasons(preflight_execution(s.plan, s.artifacts, cp)) == [(B.TARGET_DIRECTORY_CHANGED,
                                                                       PathRole.TARGET_DIRECTORY)]


def test_target_directory_replaced_by_junction(mid):
    s, cp = mid
    target = s.plan.target_directory.absolute_path
    os.rename(target, str(s.root / "moved"))
    try_junction(s.root / "library" / NUMBER, s.root / "moved")
    assert _reasons(preflight_execution(s.plan, s.artifacts, cp)) == [(B.TARGET_DIRECTORY_CHANGED,
                                                                       PathRole.TARGET_DIRECTORY)]


def test_extrafanart_directory_replaced(mid):
    s, cp = mid
    efd = s.plan.extrafanart_directory.absolute_path
    os.rename(efd, str(s.root / "moved-extra"))
    reasons = _reasons(preflight_execution(s.plan, s.artifacts, cp))
    assert (B.COMPLETED_EFFECT_MISSING, PathRole.EXTRAFANART_DIRECTORY) in reasons
    os.mkdir(efd)
    reasons = _reasons(preflight_execution(s.plan, s.artifacts, cp))
    assert reasons == [(B.TARGET_DIRECTORY_CHANGED, PathRole.EXTRAFANART_DIRECTORY)]


def _plant_and_check(s, cp, path, role, make):
    make(path)
    before = fingerprint_tree(s.root)
    reasons = _reasons(preflight_execution(s.plan, s.artifacts, cp))
    assert reasons == [(B.UNEXPECTED_ENTRY, role)], reasons
    assert fingerprint_tree(s.root) == before  # never touched / adopted


def _file(path):
    with open(path, "wb") as handle:
        handle.write(b"planted")


@pytest.mark.parametrize("name", ["planted.txt", TEMP_NAME, ".fc2tmp-" + "0" * 32 + ".part", "notes"])
def test_unexpected_files_in_target_directory(mid, name):
    s, cp = mid
    _plant_and_check(s, cp, os.path.join(s.plan.target_directory.absolute_path, name), PathRole.TARGET_DIRECTORY,
                     _file)


def test_unexpected_directory_in_target_directory(mid):
    s, cp = mid
    _plant_and_check(s, cp, os.path.join(s.plan.target_directory.absolute_path, "subdir"),
                     PathRole.TARGET_DIRECTORY, os.mkdir)


def test_unexpected_entry_in_extrafanart_directory(mid):
    s, cp = mid
    _plant_and_check(s, cp, os.path.join(s.plan.extrafanart_directory.absolute_path, "extrafanart-002.jpg"),
                     PathRole.EXTRAFANART_DIRECTORY, _file)


def test_case_variant_of_a_pending_artifact_is_unexpected(mid):
    s, cp = mid
    # fanart / thumb are absent from this manifest; a case variant of the NFO name of another film, too.
    name = (NUMBER + ".NFO").lower() if os.name != "nt" else "FANART.JPG"
    _plant_and_check(s, cp, os.path.join(s.plan.target_directory.absolute_path, name), PathRole.TARGET_DIRECTORY,
                     _file)


def test_case_variant_of_a_completed_name_on_windows(tmp_path):
    s = scene(tmp_path)
    cp = advance(s, _after(s, EffectKind.ARTIFACT_PUBLISHED, ArtifactKind.NFO))
    nfo = s.plan.nfo_path.absolute_path
    renamed = os.path.join(os.path.dirname(nfo), os.path.basename(nfo).upper())
    os.rename(nfo, renamed)
    reasons = _reasons(preflight_execution(s.plan, s.artifacts, cp))
    if os.name == "nt":
        assert reasons == []  # case-insensitive: the same entry
    else:
        assert (B.UNEXPECTED_ENTRY, PathRole.TARGET_DIRECTORY) in reasons
        assert (B.COMPLETED_EFFECT_MISSING, PathRole.NFO) in reasons


def test_completed_effect_missing(mid):
    s, cp = mid
    os.remove(s.plan.poster_path.absolute_path)
    os.remove(os.path.join(s.plan.extrafanart_directory.absolute_path, "extrafanart-001.jpg"))
    blockers = preflight_execution(s.plan, s.artifacts, cp).blockers
    assert PreflightBlocker(B.COMPLETED_EFFECT_MISSING, PathRole.POSTER) in blockers
    assert PreflightBlocker(B.COMPLETED_EFFECT_MISSING, PathRole.EXTRAFANART_FILE, None, 1) in blockers
    assert all(b.reason is B.COMPLETED_EFFECT_MISSING for b in blockers)


def test_completed_media_missing(tmp_path):
    s = scene(tmp_path)
    cp = advance(s, _after(s, EffectKind.SOURCE_REMOVED))
    os.rename(s.plan.target_media_path.absolute_path, str(tmp_path / "stolen.mp4"))
    assert _reasons(preflight_execution(s.plan, s.artifacts, cp)) == [(B.COMPLETED_EFFECT_MISSING,
                                                                       PathRole.TARGET_MEDIA)]


def _rewrite_same_size(path, keep_mtime):
    st = os.stat(path)
    with open(path, "r+b") as handle:
        first = handle.read(1)
        handle.seek(0)
        handle.write(bytes([first[0] ^ 0xFF]))
    if keep_mtime:
        os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns))


@pytest.mark.parametrize("keep_mtime", [False, True])
def test_artifact_same_size_rewrite_is_changed(mid, keep_mtime):
    s, cp = mid
    _rewrite_same_size(s.plan.nfo_path.absolute_path, keep_mtime)
    if keep_mtime:
        st = os.lstat(s.plan.nfo_path.absolute_path)
        recorded = next(e for e in cp.completed_effects if e.role is PathRole.NFO).identity
        assert (st.st_ino, st.st_size, st.st_mtime_ns) == (recorded.inode, recorded.size, recorded.mtime_ns)
    assert _reasons(preflight_execution(s.plan, s.artifacts, cp)) == [(B.COMPLETED_EFFECT_CHANGED, PathRole.NFO)]


def test_artifact_inode_replacement_is_changed(mid):
    s, cp = mid
    path = s.plan.poster_path.absolute_path
    st = os.stat(path)
    with open(path, "rb") as handle:
        content = handle.read()
    os.rename(path, str(s.root / "old-poster"))
    with open(path, "wb") as handle:
        handle.write(content)
    os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns))
    assert _reasons(preflight_execution(s.plan, s.artifacts, cp)) == [(B.COMPLETED_EFFECT_CHANGED,
                                                                       PathRole.POSTER)]


def test_mtime_change_is_changed_for_artifacts_and_media(tmp_path):
    s = scene(tmp_path)
    cp = advance(s, _after(s, EffectKind.ARTIFACT_PUBLISHED, ArtifactKind.NFO))
    for path, role in ((s.plan.nfo_path.absolute_path, PathRole.NFO),
                       (s.plan.target_media_path.absolute_path, PathRole.TARGET_MEDIA)):
        st = os.stat(path)
        os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns + 1_000_000_000))
        assert (B.COMPLETED_EFFECT_CHANGED, role) in _reasons(preflight_execution(s.plan, s.artifacts, cp))
        os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns))
    assert preflight_execution(s.plan, s.artifacts, cp).ready


def test_recorded_artifact_hash_must_match_file_and_manifest(tmp_path):
    s = scene(tmp_path)
    cp = advance(s, _after(s, EffectKind.ARTIFACT_PUBLISHED, ArtifactKind.NFO))
    nfo = next(e for e in cp.completed_effects if e.role is PathRole.NFO)
    forged = CompletedEffect(nfo.kind, nfo.role, nfo.path, nfo.identity, nfo.size, "a" * 64, nfo.artifact_kind,
                             None)
    effects = tuple(forged if e is nfo else e for e in cp.completed_effects)
    assert _reasons(preflight_execution(s.plan, s.artifacts, _reissue(cp, completed_effects=effects))) == [
        (B.COMPLETED_EFFECT_CHANGED, PathRole.NFO)]


def test_media_is_never_rehashed(tmp_path, monkeypatch):
    s = scene(tmp_path)
    cp = advance(s, _after(s, EffectKind.ARTIFACT_PUBLISHED, ArtifactKind.NFO))
    trap, opened = trap_mutations_allowing_reads(monkeypatch)
    assert preflight_execution(s.plan, s.artifacts, cp).ready
    assert opened == [s.plan.nfo_path.absolute_path] and trap.calls == []


# --------------------------------------------------------------------------- source by progress


def test_source_changed_or_missing_before_media_published(tmp_path):
    s = scene(tmp_path)
    cp = advance(s, 1)
    with open(s.source_path, "ab") as handle:
        handle.write(b"+")
    assert _reasons(preflight_execution(s.plan, s.artifacts, cp)) == [(B.SOURCE_CHANGED, PathRole.SOURCE)]
    os.remove(s.source_path)
    assert _reasons(preflight_execution(s.plan, s.artifacts, cp)) == [(B.SOURCE_MISSING, PathRole.SOURCE)]


def test_source_after_media_published_but_before_removal(tmp_path):
    s = scene(tmp_path)
    cp = advance(s, _after(s, EffectKind.MEDIA_PUBLISHED))
    assert preflight_execution(s.plan, s.artifacts, cp).ready
    os.remove(s.source_path)  # the published media (a second name of the same file) stays
    reasons = _reasons(preflight_execution(s.plan, s.artifacts, cp))
    assert reasons == [(B.SOURCE_MISSING, PathRole.SOURCE)]  # never pretended to be removed by us
    with open(s.source_path, "wb") as handle:
        handle.write(s.content)  # a different file at the same path
    assert _reasons(preflight_execution(s.plan, s.artifacts, cp)) == [(B.SOURCE_CHANGED, PathRole.SOURCE)]


def test_source_replaced_by_a_link_is_changed(tmp_path, monkeypatch):
    s = scene(tmp_path)
    cp = advance(s, 1)
    inject(monkeypatch, lstat=lstat_rewriting(s.source_path, st_file_attributes=stat.FILE_ATTRIBUTE_REPARSE_POINT))
    assert _reasons(preflight_execution(s.plan, s.artifacts, cp)) == [(B.SOURCE_CHANGED, PathRole.SOURCE)]


def test_source_path_is_never_checked_after_source_removed(tmp_path, monkeypatch):
    s = scene(tmp_path)
    cp = advance(s, _after(s, EffectKind.SOURCE_REMOVED))
    with open(s.source_path, "wb") as handle:
        handle.write(b"someone else's new file")
    before = fingerprint_tree(tmp_path)
    counter = CallCounter(monkeypatch)
    assert preflight_execution(s.plan, s.artifacts, cp).ready
    assert s.source_path not in counter.paths
    assert fingerprint_tree(tmp_path) == before


# --------------------------------------------------------------------------- leftovers


def test_recorded_leftovers_are_tolerated_and_never_deleted(tmp_path, monkeypatch):
    s = scene(tmp_path, extra=1)
    cp = advance(s, _after(s, EffectKind.EXTRAFANART_DIRECTORY_CREATED),
                 leftovers=[(PathRole.TARGET_DIRECTORY, TEMP_NAME),
                            (PathRole.EXTRAFANART_DIRECTORY, ".fc2tmp-" + "cd" * 16 + ".part")])
    before = fingerprint_tree(tmp_path)
    trap, _ = trap_mutations_allowing_reads(monkeypatch)
    preflight = preflight_execution(s.plan, s.artifacts, cp)
    monkeypatch.undo()
    assert preflight.ready and trap.calls == [] and fingerprint_tree(tmp_path) == before


def test_an_unrecorded_temp_next_to_a_recorded_one_is_unexpected(tmp_path):
    s = scene(tmp_path)
    cp = advance(s, 1, leftovers=[(PathRole.TARGET_DIRECTORY, TEMP_NAME)])
    _file(os.path.join(s.plan.target_directory.absolute_path, ".fc2tmp-" + "ef" * 16 + ".part"))
    assert _reasons(preflight_execution(s.plan, s.artifacts, cp)) == [(B.UNEXPECTED_ENTRY,
                                                                       PathRole.TARGET_DIRECTORY)]


def test_a_vanished_recorded_leftover_is_reported_missing(tmp_path):
    s = scene(tmp_path)
    cp = advance(s, 1, leftovers=[(PathRole.TARGET_DIRECTORY, TEMP_NAME)])
    os.remove(os.path.join(s.plan.target_directory.absolute_path, TEMP_NAME))
    assert _reasons(preflight_execution(s.plan, s.artifacts, cp)) == [(B.COMPLETED_EFFECT_MISSING,
                                                                       PathRole.TARGET_DIRECTORY)]


def test_resume_blockers_carry_no_path_text(mid):
    s, cp = mid
    _file(os.path.join(s.plan.target_directory.absolute_path, "planted"))
    os.remove(s.plan.poster_path.absolute_path)
    rendered = repr(preflight_execution(s.plan, s.artifacts, cp).blockers)
    assert str(s.root) not in rendered and "planted" not in rendered


def test_symlink_planted_in_target_directory_is_unexpected(mid):
    s, cp = mid
    try_symlink(s.root / "library" / NUMBER / "link", s.root / "downloads")
    assert _reasons(preflight_execution(s.plan, s.artifacts, cp)) == [(B.UNEXPECTED_ENTRY,
                                                                       PathRole.TARGET_DIRECTORY)]
