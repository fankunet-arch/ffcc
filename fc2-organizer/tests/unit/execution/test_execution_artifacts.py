"""P4-C7 S4: artifact unit execution + retry verification (contract sections 14.4, 20, 23-25, 27-29; plan S4).

Every P4-C6 failure is produced inside the REAL ``materialize_artifact`` through ``materialization.atomic._FS``
(both publish strategies: this host's native one and the POSIX hard-link one); only the three rows that a
validated manifest cannot reach (path / input / model errors) use a stub raising the real P4-C6 error object.
"""

from __future__ import annotations

import errno
import hashlib
import os
from pathlib import Path

import pytest

from fc2_organizer.execution import (
    CompletedEffect,
    EffectKind,
    EntryIdentity,
    EntryType,
    ExecutionFailure,
    ExecutionFailureKind,
    ExecutionInputError,
    ExecutionStep,
    LeftoverTemporary,
    PathRole,
    preflight_execution,
)
from fc2_organizer.execution import _fs, executor
from fc2_organizer.execution.directories import create_extrafanart_directory
from fc2_organizer.execution.executor import _execute_artifact_unit
from fc2_organizer.execution.validation import artifact_unit_roles
from fc2_organizer.materialization import (
    ArtifactKind,
    ArtifactMappingError,
    InvalidTargetPathError,
    MappingRejectionReason,
    MaterializationError,
    MaterializationInputError,
    MaterializationModelError,
    MaterializedArtifact,
    TargetPathRejectionReason,
)
from fc2_organizer.materialization import atomic

from ._builders import advance, scene
from ._helpers import (
    ARTIFACT_PLANTED,
    ARTIFACT_STRATEGIES,
    MaterializeSpy,
    artifact_scene,
    artifact_temp_names,
    assert_artifact_planted_unchanged,
    failing,
    file_state,
    inject,
    inject_p4c6,
    lstat_rewriting,
    parent_identity_for,
    try_junction,
    try_symlink,
    use_p4c6_strategy,
)

F = ExecutionFailureKind
STEP = {
    ArtifactKind.NFO: ExecutionStep.MATERIALIZE_NFO, ArtifactKind.POSTER: ExecutionStep.MATERIALIZE_POSTER,
    ArtifactKind.FANART: ExecutionStep.MATERIALIZE_FANART, ArtifactKind.THUMB: ExecutionStep.MATERIALIZE_THUMB,
    ArtifactKind.EXTRAFANART: ExecutionStep.MATERIALIZE_EXTRAFANART,
}
ROLE = {
    ArtifactKind.NFO: PathRole.NFO, ArtifactKind.POSTER: PathRole.POSTER, ArtifactKind.FANART: PathRole.FANART,
    ArtifactKind.THUMB: PathRole.THUMB, ArtifactKind.EXTRAFANART: PathRole.EXTRAFANART_FILE,
}
KINDS = [ArtifactKind.NFO, ArtifactKind.POSTER, ArtifactKind.FANART, ArtifactKind.THUMB, ArtifactKind.EXTRAFANART]


def _request(a, kind=ArtifactKind.NFO, ordinal=None):
    return next(r for r in a.artifacts if r.kind is kind and (ordinal is None or r.ordinal == ordinal))


def _run(a, request, parent_identity=None):
    identity = parent_identity if parent_identity is not None else parent_identity_for(a, request)
    return _execute_artifact_unit(request, identity, a.plan)


def _failure(request, kind, **fields):
    return ExecutionFailure(step=STEP[request.kind], kind=kind, artifact_kind=request.kind,
                            ordinal=request.ordinal, **fields)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read(path) -> bytes:
    with open(path, "rb") as handle:
        return handle.read()


def _parent(a, request) -> str:
    return (a.plan.extrafanart_directory if request.kind is ArtifactKind.EXTRAFANART
            else a.plan.target_directory).absolute_path


def _assert_nothing_published(a, request, outcome, failure, leftovers=()):
    effect, got_failure, got_leftovers = outcome
    assert effect is None and got_failure == failure and got_leftovers == leftovers
    assert not os.path.lexists(request.target_path)
    assert artifact_temp_names(_parent(a, request)) == sorted(item.name for item in leftovers)
    assert_artifact_planted_unchanged(a)


# --------------------------------------------------------------------------- mapping helpers


def test_artifact_unit_roles_are_the_frozen_mapping():
    assert artifact_unit_roles(ArtifactKind.NFO) == (ExecutionStep.MATERIALIZE_NFO, PathRole.NFO,
                                                     PathRole.TARGET_DIRECTORY)
    for kind in (ArtifactKind.POSTER, ArtifactKind.FANART, ArtifactKind.THUMB):
        assert artifact_unit_roles(kind) == (STEP[kind], ROLE[kind], PathRole.TARGET_DIRECTORY)
    assert artifact_unit_roles(ArtifactKind.EXTRAFANART) == (
        ExecutionStep.MATERIALIZE_EXTRAFANART, PathRole.EXTRAFANART_FILE, PathRole.EXTRAFANART_DIRECTORY)
    with pytest.raises(ExecutionInputError):
        artifact_unit_roles("nfo")


def test_strict_inputs(tmp_path):
    a = artifact_scene(tmp_path, plant=False)
    request = _request(a)
    with pytest.raises(ExecutionInputError):
        _execute_artifact_unit(object(), a.target_identity, a.plan)
    file_identity = EntryIdentity(1, 2, EntryType.FILE, 3, 4)
    with pytest.raises(ExecutionInputError):
        _execute_artifact_unit(request, file_identity, a.plan)
    assert not os.path.lexists(request.target_path)


# --------------------------------------------------------------------------- success


@pytest.mark.parametrize("strategy", ARTIFACT_STRATEGIES)
@pytest.mark.parametrize("kind", KINDS)
def test_each_kind_publishes_exact_bytes_with_the_original_request(tmp_path, monkeypatch, strategy, kind):
    use_p4c6_strategy(monkeypatch, strategy)
    a = artifact_scene(tmp_path)
    request = _request(a, kind, 2 if kind is ArtifactKind.EXTRAFANART else None)
    spy = MaterializeSpy(monkeypatch)
    effect, failure, leftovers = _run(a, request)
    assert failure is None and leftovers == ()
    assert len(spy.requests) == 1 and spy.requests[0] is request and spy.contents[0] is request.content
    assert _read(request.target_path) == request.content
    assert effect == CompletedEffect(EffectKind.ARTIFACT_PUBLISHED, ROLE[kind], request.target_path,
                                     _fs.snapshot(request.target_path), len(request.content),
                                     _sha(request.content), kind, request.ordinal)
    assert effect.ordinal == (2 if kind is ArtifactKind.EXTRAFANART else None)
    assert artifact_temp_names(_parent(a, request)) == []
    assert_artifact_planted_unchanged(a)


# --------------------------------------------------------------------------- step 1: parent revalidation


@pytest.mark.parametrize("kind", [ArtifactKind.POSTER, ArtifactKind.EXTRAFANART])
@pytest.mark.parametrize("replacement", ["junction", "other_directory", "missing"])
def test_parent_replaced_after_a_previous_artifact(tmp_path, monkeypatch, kind, replacement):
    a = artifact_scene(tmp_path, plant=False)
    first = _request(a, ArtifactKind.NFO) if kind is ArtifactKind.POSTER else _request(a, kind, 1)
    assert _run(a, first)[1] is None
    parent = _parent(a, first)
    moved = parent + "-moved"
    os.rename(parent, moved)
    if replacement == "junction":
        try_junction(Path(parent), Path(moved))
    elif replacement == "other_directory":
        os.mkdir(parent)
    spy = MaterializeSpy(monkeypatch)
    request = _request(a, kind, 2 if kind is ArtifactKind.EXTRAFANART else None)
    effect, failure, leftovers = _run(a, request)
    assert effect is None and leftovers == () and failure == _failure(request, F.TARGET_DIRECTORY_CHANGED)
    assert spy.requests == []  # materialize_artifact is never called
    moved_first = os.path.join(moved, os.path.basename(first.target_path))
    assert _read(moved_first) == first.content  # the earlier artifact is kept (no rollback)


def test_parent_symlink_is_a_changed_directory(tmp_path, monkeypatch):
    a = artifact_scene(tmp_path, plant=False)
    parent = a.plan.target_directory.absolute_path
    os.rename(parent, parent + "-moved")
    try_symlink(Path(parent), Path(parent + "-moved"), target_is_directory=True)
    spy = MaterializeSpy(monkeypatch)
    request = _request(a)
    assert _run(a, request) == (None, _failure(request, F.TARGET_DIRECTORY_CHANGED), ())
    assert spy.requests == []


# --------------------------------------------------------------------------- step 2: target precheck


@pytest.mark.parametrize("occupant", ["file", "directory", "junction", "symlink", "dangling_symlink"])
def test_existing_target_is_a_conflict_and_untouched(tmp_path, monkeypatch, occupant):
    a = artifact_scene(tmp_path)
    request = _request(a, ArtifactKind.POSTER)
    target = Path(request.target_path)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    if occupant == "file":
        target.write_bytes(b"someone else's poster")
    elif occupant == "directory":
        target.mkdir()
    elif occupant == "junction":
        try_junction(target, elsewhere)
    elif occupant == "symlink":
        (elsewhere / "f").write_bytes(b"x")
        try_symlink(target, elsewhere / "f")
    else:
        try_symlink(target, elsewhere / "missing")
    before = os.lstat(target)
    spy = MaterializeSpy(monkeypatch)
    assert _run(a, request) == (None, _failure(request, F.TARGET_CONFLICT), ())
    assert spy.requests == []
    after = os.lstat(target)
    assert (after.st_ino, after.st_mtime_ns, after.st_mode) == (before.st_ino, before.st_mtime_ns, before.st_mode)
    if occupant == "file":
        assert _read(target) == b"someone else's poster"
    assert_artifact_planted_unchanged(a)


def test_target_probe_error_is_inaccessible(tmp_path, monkeypatch):
    a = artifact_scene(tmp_path)
    request = _request(a)
    real = _fs._FS.lstat
    inject(monkeypatch, lstat=lambda p: (_ for _ in ()).throw(PermissionError(errno.EACCES, "x"))
           if p == request.target_path else real(p))
    spy = MaterializeSpy(monkeypatch)
    assert _run(a, request) == (None, _failure(request, F.ARTIFACT_TARGET_INACCESSIBLE, errno=errno.EACCES), ())
    assert spy.requests == []


# --------------------------------------------------------------------------- MaterializationError mapping


@pytest.mark.parametrize("strategy", ARTIFACT_STRATEGIES)
@pytest.mark.parametrize("thief", ["file", "directory"])
def test_target_race_is_refused_by_the_p4c6_primitive(tmp_path, monkeypatch, strategy, thief):
    use_p4c6_strategy(monkeypatch, strategy)
    a = artifact_scene(tmp_path)
    request = _request(a, ArtifactKind.FANART)
    real_publish = atomic._FS.publish

    def racing_publish(temp, final):
        if thief == "file":
            with open(final, "wb") as handle:
                handle.write(b"thief")
        else:
            os.mkdir(final)
        return real_publish(temp, final)

    inject_p4c6(monkeypatch, publish=racing_publish)
    effect, failure, leftovers = _run(a, request)
    assert effect is None and leftovers == () and failure == _failure(request, F.TARGET_CONFLICT)
    if thief == "file":
        assert _read(request.target_path) == b"thief"
    else:
        assert os.listdir(request.target_path) == []
    assert artifact_temp_names(_parent(a, request)) == []
    assert_artifact_planted_unchanged(a)


@pytest.mark.parametrize("error,expected", [
    (FileNotFoundError(errno.ENOENT, "gone"), errno.ENOENT),
    (PermissionError(errno.EACCES, "denied"), errno.EACCES),
])
def test_parent_directory_errors_map_to_target_directory_changed(tmp_path, monkeypatch, error, expected):
    a = artifact_scene(tmp_path)
    request = _request(a)
    inject_p4c6(monkeypatch, stat=failing(error))
    assert _run(a, request) == (None, _failure(request, F.TARGET_DIRECTORY_CHANGED, errno=expected), ())
    assert not os.path.lexists(request.target_path)


def test_parent_not_a_directory_maps_to_target_directory_changed(tmp_path, monkeypatch):
    a = artifact_scene(tmp_path)
    request = _request(a)
    a_file = tmp_path / "a-file"
    a_file.write_bytes(b"x")
    inject_p4c6(monkeypatch, stat=lambda _p: os.stat(a_file))
    assert _run(a, request) == (None, _failure(request, F.TARGET_DIRECTORY_CHANGED), ())


def test_target_inaccessible_inside_p4c6(tmp_path, monkeypatch):
    a = artifact_scene(tmp_path)
    request = _request(a, ArtifactKind.THUMB)
    real = atomic._FS.lstat
    inject_p4c6(monkeypatch, lstat=lambda p: (_ for _ in ()).throw(PermissionError(errno.EACCES, "x"))
                if p == request.target_path else real(p))
    outcome = _run(a, request)
    _assert_nothing_published(a, request, outcome,
                              _failure(request, F.ARTIFACT_TARGET_INACCESSIBLE, errno=errno.EACCES))


def test_temporary_create_failure(tmp_path, monkeypatch):
    a = artifact_scene(tmp_path)
    request = _request(a, ArtifactKind.EXTRAFANART, 1)
    inject_p4c6(monkeypatch, open=failing(PermissionError(errno.EACCES, "x")))
    outcome = _run(a, request)
    _assert_nothing_published(a, request, outcome,
                              _failure(request, F.ARTIFACT_TEMP_CREATE_FAILED, errno=errno.EACCES))


@pytest.mark.parametrize("strategy", ARTIFACT_STRATEGIES)
@pytest.mark.parametrize("op,stage", [("write", "write"), ("fsync", "flush"), ("close", "close")])
def test_write_stages(tmp_path, monkeypatch, strategy, op, stage):
    use_p4c6_strategy(monkeypatch, strategy)
    a = artifact_scene(tmp_path)
    request = _request(a, ArtifactKind.POSTER)
    real = getattr(atomic._FS, op)

    def injected(*args):
        if op == "close":
            real(*args)  # released, but reported as failed
        raise OSError(errno.EIO, "io")

    inject_p4c6(monkeypatch, **{op: injected})
    outcome = _run(a, request)
    _assert_nothing_published(a, request, outcome,
                              _failure(request, F.ARTIFACT_WRITE_FAILED, write_stage=stage, errno=errno.EIO))


@pytest.mark.parametrize("strategy", ARTIFACT_STRATEGIES)
def test_publish_failure(tmp_path, monkeypatch, strategy):
    use_p4c6_strategy(monkeypatch, strategy)
    a = artifact_scene(tmp_path)
    request = _request(a, ArtifactKind.FANART)
    inject_p4c6(monkeypatch, publish=failing(PermissionError(errno.EACCES, "x")))
    outcome = _run(a, request)
    _assert_nothing_published(a, request, outcome, _failure(request, F.ARTIFACT_PUBLISH_FAILED, errno=errno.EACCES))


@pytest.mark.parametrize("error", [
    InvalidTargetPathError(TargetPathRejectionReason.RESERVED_NAME),
    MaterializationInputError("x"),
    MaterializationModelError("x"),
])
def test_unreachable_rows_map_to_path_rejected(tmp_path, monkeypatch, error):
    a = artifact_scene(tmp_path)
    request = _request(a)
    spy = MaterializeSpy(monkeypatch, replacement=failing(error))
    outcome = _run(a, request)
    _assert_nothing_published(a, request, outcome, _failure(request, F.ARTIFACT_PATH_REJECTED))
    assert spy.requests == [request]


class FutureMaterializationError(MaterializationError):
    """A MaterializationError subtype the frozen section 24 table does not define."""


@pytest.mark.parametrize("make", [
    lambda: ArtifactMappingError(MappingRejectionReason.PLAN_PATH_INVALID),  # mapping layer, not a writer error
    lambda: FutureMaterializationError("future"),
], ids=["ArtifactMappingError", "FutureMaterializationError"])
def test_undefined_materialization_error_propagates_as_the_same_object(tmp_path, monkeypatch, make):
    # R-02: no catch-all row; an undefined subtype is never silently classified (e.g. ARTIFACT_PATH_REJECTED).
    a = artifact_scene(tmp_path)
    request = _request(a, ArtifactKind.EXTRAFANART, 1)
    exc = make()
    spy = MaterializeSpy(monkeypatch, replacement=failing(exc))
    with pytest.raises(MaterializationError) as info:
        _run(a, request)
    assert info.value is exc and exc.__cause__ is None and exc.__context__ is None
    assert spy.requests == [request]
    assert not os.path.lexists(request.target_path)
    assert_artifact_planted_unchanged(a)


# --------------------------------------------------------------------------- ArtifactCleanupError


def _unlink_fails_for_temps(monkeypatch, error=None):
    real = atomic._FS.unlink

    def unlink(path):
        if os.path.basename(path).startswith(".fc2tmp-"):
            raise error or PermissionError(errno.EACCES, "busy")
        return real(path)

    inject_p4c6(monkeypatch, unlink=unlink)


@pytest.mark.parametrize("strategy", ARTIFACT_STRATEGIES)
@pytest.mark.parametrize("kind", [ArtifactKind.NFO, ArtifactKind.EXTRAFANART])
def test_cleanup_failure_not_published_records_exact_new_leftover(tmp_path, monkeypatch, strategy, kind):
    use_p4c6_strategy(monkeypatch, strategy)
    a = artifact_scene(tmp_path)
    request = _request(a, kind, 1 if kind is ArtifactKind.EXTRAFANART else None)
    inject_p4c6(monkeypatch, write=failing(OSError(errno.ENOSPC, "full")))
    _unlink_fails_for_temps(monkeypatch)
    effect, failure, leftovers = _run(a, request)
    [name] = artifact_temp_names(_parent(a, request))
    role = PathRole.EXTRAFANART_DIRECTORY if kind is ArtifactKind.EXTRAFANART else PathRole.TARGET_DIRECTORY
    assert effect is None
    assert failure == _failure(request, F.ARTIFACT_CLEANUP_FAILED, errno=errno.EACCES, target_published=False)
    assert leftovers == (LeftoverTemporary(role, name),)  # exact; the planted temp is not included
    assert ARTIFACT_PLANTED[0] not in {item.name for item in leftovers}
    assert os.path.exists(os.path.join(_parent(a, request), name))  # never deleted by P4-C7
    assert not os.path.lexists(request.target_path)
    assert_artifact_planted_unchanged(a)


@pytest.mark.parametrize("kind", [ArtifactKind.THUMB, ArtifactKind.EXTRAFANART])
def test_cleanup_failure_published_is_reverified_and_recorded(tmp_path, monkeypatch, kind):
    use_p4c6_strategy(monkeypatch, "hardlink")
    a = artifact_scene(tmp_path)
    request = _request(a, kind, 2 if kind is ArtifactKind.EXTRAFANART else None)
    _unlink_fails_for_temps(monkeypatch)
    reads = []
    real_read = _fs.read_bounded

    def read_bounded(path, limit):
        reads.append((path, limit))
        return real_read(path, limit)

    monkeypatch.setattr(_fs, "read_bounded", read_bounded)
    effect, failure, leftovers = _run(a, request)
    [name] = artifact_temp_names(_parent(a, request))
    assert failure == _failure(request, F.ARTIFACT_CLEANUP_FAILED, errno=errno.EACCES, target_published=True)
    assert effect == CompletedEffect(EffectKind.ARTIFACT_PUBLISHED, ROLE[kind], request.target_path,
                                     _fs.snapshot(request.target_path), len(request.content),
                                     _sha(request.content), kind, request.ordinal)
    assert reads == [(request.target_path, len(request.content))]  # full read-only re-hash of the final
    assert leftovers[0].name == name and len(leftovers) == 1
    assert _read(request.target_path) == request.content
    assert_artifact_planted_unchanged(a)


@pytest.mark.parametrize("tamper", ["same_size_other_bytes", "appended", "replaced_by_directory"])
def test_cleanup_failure_published_but_final_not_provable_records_no_effect(tmp_path, monkeypatch, tamper):
    use_p4c6_strategy(monkeypatch, "hardlink")
    a = artifact_scene(tmp_path)
    request = _request(a, ArtifactKind.POSTER)
    def publish_then_tamper(temp, final):
        os.link(temp, final)
        if tamper == "same_size_other_bytes":
            data = bytearray(_read(final))
            data[-3] ^= 0xFF
            os.unlink(final)
            with open(final, "wb") as handle:
                handle.write(bytes(data))
        elif tamper == "appended":
            with open(final, "ab") as handle:
                handle.write(b"x")
        else:
            os.unlink(final)
            os.mkdir(final)

    inject_p4c6(monkeypatch, publish=publish_then_tamper)
    _unlink_fails_for_temps(monkeypatch)
    effect, failure, leftovers = _run(a, request)
    assert effect is None and failure == _failure(request, F.PUBLISHED_ARTIFACT_MISMATCH)
    assert len(leftovers) == 1  # the leftover is still reported
    assert os.path.lexists(request.target_path)  # nothing deleted, nothing rolled back
    assert_artifact_planted_unchanged(a)


def test_cleanup_failure_with_replaced_parent_trusts_nothing(tmp_path, monkeypatch):
    use_p4c6_strategy(monkeypatch, "hardlink")
    a = artifact_scene(tmp_path, plant=False)
    request = _request(a)
    parent = a.plan.target_directory.absolute_path
    real_unlink = atomic._FS.unlink

    def unlink(path):
        if os.path.basename(path).startswith(".fc2tmp-"):
            os.rename(parent, parent + "-moved")
            os.mkdir(parent)
            raise PermissionError(errno.EACCES, "busy")
        return real_unlink(path)

    inject_p4c6(monkeypatch, unlink=unlink)
    effect, failure, leftovers = _run(a, request)
    assert effect is None and leftovers == ()
    assert failure == _failure(request, F.ARTIFACT_CLEANUP_FAILED, errno=errno.EACCES, target_published=True)
    moved = os.listdir(parent + "-moved")
    assert os.path.basename(request.target_path) in moved and any(n.startswith(".fc2tmp-") for n in moved)


def test_leftover_attribution_uses_platform_name_semantics(tmp_path, monkeypatch):
    # The "before" listing reports an upper-case-hex twin of the temp that appears "after".
    a = artifact_scene(tmp_path, plant=False)
    request = _request(a)
    token = "c" * 32
    lower = f".fc2tmp-{token}.part"
    upper = f".fc2tmp-{token.upper()}.part"
    listings = iter([[upper], [lower, "other.part"]])
    inject(monkeypatch, listdir=lambda _d: next(listings))
    inject_p4c6(monkeypatch, write=failing(OSError(errno.EIO, "x")))
    _unlink_fails_for_temps(monkeypatch)
    _, failure, leftovers = _run(a, request)
    assert failure.kind is F.ARTIFACT_CLEANUP_FAILED
    if os.name == "nt":
        assert leftovers == ()  # casefold: the same entry existed before
    else:
        assert leftovers == (LeftoverTemporary(PathRole.TARGET_DIRECTORY, lower),)  # the actual name


def test_listing_failure_before_materialization_fails_closed(tmp_path, monkeypatch):
    a = artifact_scene(tmp_path)
    request = _request(a)
    inject(monkeypatch, listdir=failing(PermissionError(errno.EACCES, "x")))
    spy = MaterializeSpy(monkeypatch)
    assert _run(a, request) == (None, _failure(request, F.TARGET_DIRECTORY_CHANGED, errno=errno.EACCES), ())
    assert spy.requests == []


# --------------------------------------------------------------------------- step 4: receipt / snapshot


@pytest.mark.parametrize("field", ["target_path", "size_bytes", "sha256"])
def test_receipt_mismatch_is_published_artifact_mismatch(tmp_path, monkeypatch, field):
    a = artifact_scene(tmp_path)
    request = _request(a)
    real = executor.materialize_artifact

    def lying(req):
        receipt = real(req)
        values = {"target_path": receipt.target_path, "size_bytes": receipt.size_bytes, "sha256": receipt.sha256}
        values[field] = {"target_path": receipt.target_path + "x", "size_bytes": receipt.size_bytes + 1,
                         "sha256": "0" * 64}[field]
        return MaterializedArtifact(**values)

    MaterializeSpy(monkeypatch, replacement=lying)
    assert _run(a, request) == (None, _failure(request, F.PUBLISHED_ARTIFACT_MISMATCH), ())
    assert _read(request.target_path) == request.content  # kept: no rollback


@pytest.mark.parametrize("override", [{"st_size": 1}, {"st_ino": 0}, {"st_mode": 0o040755}])
def test_post_publish_snapshot_mismatch(tmp_path, monkeypatch, override):
    a = artifact_scene(tmp_path)
    request = _request(a)
    real = _fs._FS.lstat
    rewriting = lstat_rewriting(request.target_path, **override)
    inject(monkeypatch, lstat=lambda p: rewriting(p) if os.path.lexists(request.target_path) else real(p))
    assert _run(a, request) == (None, _failure(request, F.PUBLISHED_ARTIFACT_MISMATCH), ())
    assert _read(request.target_path) == request.content


# --------------------------------------------------------------------------- no rollback / resume / 1000


def test_a_later_failure_keeps_the_earlier_artifact(tmp_path, monkeypatch):
    a = artifact_scene(tmp_path)
    nfo, poster = _request(a), _request(a, ArtifactKind.POSTER)
    assert _run(a, nfo)[1] is None
    before = file_state(nfo.target_path)
    inject_p4c6(monkeypatch, write=failing(OSError(errno.ENOSPC, "full")))
    assert _run(a, poster)[1].kind is F.ARTIFACT_WRITE_FAILED
    assert file_state(nfo.target_path) == before


def test_resume_never_rematerializes_a_completed_artifact(tmp_path, monkeypatch):
    s = scene(tmp_path, extra=2)
    checkpoint = advance(s, 5)  # U1, media, source removal, NFO, POSTER completed
    preflight = preflight_execution(s.plan, s.artifacts, checkpoint)
    assert preflight.ready
    pending_kinds = [(u.artifact_kind, u.ordinal) for u in preflight.pending_units if u.artifact_kind]
    assert (ArtifactKind.NFO, None) not in pending_kinds and (ArtifactKind.POSTER, None) not in pending_kinds
    nfo_before = file_state(s.plan.nfo_path.absolute_path)
    poster_before = file_state(s.plan.poster_path.absolute_path)
    spy = MaterializeSpy(monkeypatch)
    requests = {(r.kind, r.ordinal): r for r in s.artifacts}
    extrafanart_identity = None
    for unit in preflight.pending_units:  # tests-only unit loop (S5 owns orchestration)
        if unit.step is ExecutionStep.ENSURE_EXTRAFANART_DIRECTORY:
            extrafanart_identity, failure = create_extrafanart_directory(s.plan, checkpoint.target_directory_identity)
            assert failure is None
            continue
        request = requests[(unit.artifact_kind, unit.ordinal)]
        parent = (extrafanart_identity if unit.artifact_kind is ArtifactKind.EXTRAFANART
                  else checkpoint.target_directory_identity)
        effect, failure, _ = _execute_artifact_unit(request, parent, s.plan)
        assert failure is None and effect.path == request.target_path
    called = [(r.kind, r.ordinal) for r in spy.requests]
    assert called == pending_kinds and (ArtifactKind.NFO, None) not in called
    assert all(r is requests[(r.kind, r.ordinal)] for r in spy.requests)
    assert file_state(s.plan.nfo_path.absolute_path) == nfo_before  # zero rewrites
    assert file_state(s.plan.poster_path.absolute_path) == poster_before


def test_one_thousand_extrafanart_units_in_manifest_order(tmp_path, monkeypatch):
    a = artifact_scene(tmp_path, extra=1000, plant=False)
    extras = [r for r in a.artifacts if r.kind is ArtifactKind.EXTRAFANART]
    assert [r.ordinal for r in extras] == list(range(1, 1001))
    spy = MaterializeSpy(monkeypatch)
    effects = []
    for request in extras:
        effect, failure, leftovers = _run(a, request)
        assert failure is None and leftovers == ()
        effects.append(effect)
    assert len(spy.requests) == 1000 and all(got is want for got, want in zip(spy.requests, extras))
    assert [e.ordinal for e in effects] == list(range(1, 1001))
    names = sorted(os.listdir(a.plan.extrafanart_directory.absolute_path))
    assert names == sorted(f"extrafanart-{k:03d}.jpg" for k in range(1, 1001))
    assert os.path.basename(effects[-1].path) == "extrafanart-1000.jpg"
    assert all(e.role is PathRole.EXTRAFANART_FILE and e.artifact_kind is ArtifactKind.EXTRAFANART for e in effects)


# --------------------------------------------------------------------------- fatal / foreign exceptions


class CustomFatal(BaseException):
    pass


@pytest.mark.parametrize("fatal", [KeyboardInterrupt, SystemExit, GeneratorExit, MemoryError, RuntimeError,
                                   CustomFatal])
@pytest.mark.parametrize("where", ["p4c6_write", "p4c6_publish", "materialize_stub", "execution_seam"])
def test_fatal_and_foreign_exceptions_propagate_unchanged(tmp_path, monkeypatch, fatal, where):
    a = artifact_scene(tmp_path)
    request = _request(a, ArtifactKind.POSTER)
    exc = fatal("stop")
    if where == "p4c6_write":
        inject_p4c6(monkeypatch, write=failing(exc))
    elif where == "p4c6_publish":
        inject_p4c6(monkeypatch, publish=failing(exc))
    elif where == "materialize_stub":
        MaterializeSpy(monkeypatch, replacement=failing(exc))
    else:
        inject(monkeypatch, listdir=failing(exc))
    with pytest.raises(fatal) as info:
        _run(a, request)
    assert info.value is exc and exc.__cause__ is None
    assert not os.path.lexists(request.target_path)
    assert artifact_temp_names(_parent(a, request)) == []  # P4-C6 cleaned its own temporary
    assert_artifact_planted_unchanged(a)


def test_failure_carries_no_path_text_or_exception(tmp_path, monkeypatch):
    a = artifact_scene(tmp_path)
    request = _request(a, ArtifactKind.EXTRAFANART, 2)
    inject_p4c6(monkeypatch, write=failing(OSError(errno.EIO, "SECRET-TEXT", request.target_path)))
    _, failure, _ = _run(a, request)
    text = repr(failure) + str(failure)
    assert "SECRET-TEXT" not in text and request.target_path not in text and ".fc2tmp-" not in text
    assert failure.artifact_kind is ArtifactKind.EXTRAFANART and failure.ordinal == 2
    assert failure.step is ExecutionStep.MATERIALIZE_EXTRAFANART
    for name in failure.__slots__:
        assert not isinstance(getattr(failure, name), BaseException)


# --------------------------------------------------------------------------- R-01: unknown leftovers are never "none"


def _after_listing_fails(monkeypatch, exc):
    """The execution seam's listdir works for the "before" listing and raises ``exc`` for the next one."""
    real = _fs._FS.listdir
    calls = []

    def listdir(directory):
        calls.append(directory)
        if len(calls) == 2:
            raise exc
        return real(directory)

    inject(monkeypatch, listdir=listdir)
    return calls


@pytest.mark.parametrize("strategy", ARTIFACT_STRATEGIES)
def test_cleanup_unpublished_with_failed_after_listing_propagates_the_same_oserror(tmp_path, monkeypatch,
                                                                                   strategy):
    use_p4c6_strategy(monkeypatch, strategy)
    a = artifact_scene(tmp_path)
    request = _request(a, ArtifactKind.POSTER)
    inject_p4c6(monkeypatch, write=failing(OSError(errno.ENOSPC, "full")))
    _unlink_fails_for_temps(monkeypatch)
    exc = PermissionError(errno.EACCES, "listing denied")
    calls = _after_listing_fails(monkeypatch, exc)
    with pytest.raises(OSError) as info:
        _run(a, request)  # never (None, ARTIFACT_CLEANUP_FAILED, ()): unknown leftovers are not "none"
    assert info.value is exc and exc.__cause__ is None and len(calls) == 2
    assert len(artifact_temp_names(_parent(a, request))) == 1  # the real P4-C6 temp stays; never deleted
    assert not os.path.lexists(request.target_path)
    assert_artifact_planted_unchanged(a)


@pytest.mark.parametrize("kind", [ArtifactKind.NFO, ArtifactKind.EXTRAFANART])
def test_cleanup_published_with_failed_after_listing_propagates_and_keeps_the_final(tmp_path, monkeypatch, kind):
    use_p4c6_strategy(monkeypatch, "hardlink")
    a = artifact_scene(tmp_path)
    request = _request(a, kind, 1 if kind is ArtifactKind.EXTRAFANART else None)
    _unlink_fails_for_temps(monkeypatch)
    exc = OSError(errno.EIO, "listing failed")
    calls = _after_listing_fails(monkeypatch, exc)
    with pytest.raises(OSError) as info:
        _run(a, request)  # no effect / failure / leftovers=() result is formed
    assert info.value is exc and exc.__cause__ is None and len(calls) == 2
    assert _read(request.target_path) == request.content  # the published final is kept
    assert len(artifact_temp_names(_parent(a, request))) == 1  # the leftover stays; never deleted
    assert_artifact_planted_unchanged(a)
