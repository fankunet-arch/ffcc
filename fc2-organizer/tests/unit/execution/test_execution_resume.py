"""P4-C7 S5: in-process checkpoint retry through execute_filesystem (contract sections 8, 14, 15.4, 18-20; plan S5).

"Resume after each partial point": for two manifest shapes and EVERY prefix length p (0 < p < |E|), a typed
failure is injected at the (p+1)-th expected effect; the PARTIAL result's checkpoint is resumed to SUCCESS and the
final library equals an uninterrupted run byte for byte, with zero rewrites of completed artifacts.
"""

from __future__ import annotations

import errno
import hashlib
import os
from pathlib import Path

import pytest

from fc2_organizer.execution import (
    CheckpointError,
    CheckpointRejectionReason,
    EffectKind,
    ExecutionFailureKind,
    ExecutionStatus,
    PreflightBlockReason,
    PreflightMode,
    PreflightNotReadyError,
    TransferMode,
    execute_filesystem,
    preflight_execution,
)
from fc2_organizer.execution import _fs, executor
from fc2_organizer.execution.seal import is_consumed
from fc2_organizer.execution.transfer import ResumePhase
from fc2_organizer.execution.validation import expected_effects
from fc2_organizer.materialization import ArtifactKind, ArtifactWriteError, ArtifactWriteStage

from ._builders import NFO_TEXT, make_manifest, make_plan, scene
from ._helpers import (
    FakeDirectoryFsync,
    MaterializeSpy,
    assert_source_not_lost,
    expected_library_layout,
    failing,
    file_state,
    inject,
    inject_p4c6,
    trap_mutations_allowing_reads,
    tree_layout,
    use_strategy,
)

F = ExecutionFailureKind
MEDIA = b"resume-media \x01\x02" * 53
SHAPES = {"nfo_only": dict(poster=False, fanart=False, thumb=False, extra=0),
          "full_3_extra": dict(poster=True, fanart=True, thumb=True, extra=3)}
_PROBE_ROOT = "C:\\probe-library" if os.name == "nt" else "/probe-library"


def _effect_count(shape: str) -> int:
    plan = make_plan(_PROBE_ROOT)  # lexical only: the length of E depends on the manifest shape alone
    return len(expected_effects(plan, make_manifest(plan, **SHAPES[shape])))


POINTS = [(shape, p) for shape in SHAPES for p in range(1, _effect_count(shape))]


def test_every_partial_point_is_parameterized():
    for shape in SHAPES:
        assert sum(1 for s, _ in POINTS if s == shape) == _effect_count(shape) - 1
    assert _effect_count("nfo_only") == 5 and _effect_count("full_3_extra") == 11
    assert ("full_3_extra", 2) in POINTS  # MEDIA_PUBLISHED done, SOURCE_REMOVED not: its own point


def _scene(root: Path, shape: str):
    root.mkdir(parents=True, exist_ok=True)
    return scene(root, content=MEDIA, **SHAPES[shape])


class _FailAt:
    """Injects ONE typed failure that prevents the effect at index ``p`` of E (0-based) and nothing else."""

    def __init__(self, monkeypatch, s, p: int):
        self.active = True
        slot = expected_effects(s.plan, s.artifacts)[p]
        kind = slot.kind
        if kind is EffectKind.MEDIA_PUBLISHED:
            for op in ("rename", "link"):
                self._wrap_seam(monkeypatch, op, lambda a, *_: a == s.source_path, PermissionError(errno.EPERM, "x"))
        elif kind is EffectKind.SOURCE_REMOVED:
            use_strategy(monkeypatch, "link")  # link publishes first; the verified source unlink then fails
            self._wrap_seam(monkeypatch, "unlink", lambda a, *_: a == s.source_path,
                            PermissionError(errno.EACCES, "busy"))
        elif kind is EffectKind.EXTRAFANART_DIRECTORY_CREATED:
            self._wrap_seam(monkeypatch, "mkdir", lambda a, *_: a == slot.path, PermissionError(errno.EACCES, "x"))
        else:
            target = next(r for r in s.artifacts if r.target_path == slot.path)
            real = executor.materialize_artifact

            def materialize(request):
                if self.active and request is target:
                    raise ArtifactWriteError(ArtifactWriteStage.WRITE, errno.ENOSPC)
                return real(request)

            monkeypatch.setattr(executor, "materialize_artifact", materialize)

    def _wrap_seam(self, monkeypatch, op, when, error):
        real = getattr(_fs._FS, op)

        def injected(*args):
            if self.active and when(*args):
                raise error
            return real(*args)

        inject(monkeypatch, **{op: injected})


def _reference_layout(root: Path, shape: str) -> dict:
    s = _scene(root, shape)
    assert execute_filesystem(preflight_execution(s.plan, s.artifacts)).status is ExecutionStatus.SUCCESS
    return tree_layout(s.library_root)


@pytest.mark.parametrize("shape,p", POINTS, ids=[f"{shape}-p{p}" for shape, p in POINTS])
def test_resume_after_each_partial_point(tmp_path, monkeypatch, shape, p):
    reference = _reference_layout(tmp_path / "reference", shape)
    s = _scene(tmp_path / "run", shape)
    E = expected_effects(s.plan, s.artifacts)
    fail = _FailAt(monkeypatch, s, p)
    first = execute_filesystem(preflight_execution(s.plan, s.artifacts))
    assert first.status is ExecutionStatus.PARTIAL and first.checkpoint is not None
    assert len(first.completed_effects) == p == first.new_effect_count
    assert [(e.kind, e.path) for e in first.completed_effects] == [(e.kind, e.path) for e in E[:p]]
    assert first.checkpoint.completed_effects == first.completed_effects
    assert_source_not_lost(s.source_path, s.plan.target_media_path.absolute_path, hashlib.sha256(MEDIA).hexdigest())

    fail.active = False
    done_artifacts = {e.path: file_state(e.path) for e in first.completed_effects
                      if e.kind is EffectKind.ARTIFACT_PUBLISHED}
    spy = MaterializeSpy(monkeypatch)
    preflight = preflight_execution(s.plan, s.artifacts, first.checkpoint)
    assert preflight.ready and preflight.mode is PreflightMode.RESUME
    second = execute_filesystem(preflight)
    assert second.status is ExecutionStatus.SUCCESS and second.mode is PreflightMode.RESUME
    assert second.completed_effects[:p] == first.completed_effects  # append-only
    assert second.new_effect_count == len(E) - p
    assert tree_layout(s.library_root) == reference == expected_library_layout(s.plan, s.artifacts, MEDIA)
    assert all(r.target_path not in done_artifacts for r in spy.requests)  # zero rematerialization
    assert {path: file_state(path) for path in done_artifacts} == done_artifacts  # bytes / inode / mtime
    assert is_consumed(first.checkpoint.checkpoint_id)
    assert not os.path.lexists(s.source_path)


def test_checkpoint_chain(tmp_path, monkeypatch):
    s = _scene(tmp_path, "full_3_extra")
    fail_poster = _FailAt(monkeypatch, s, 4)
    r1 = execute_filesystem(preflight_execution(s.plan, s.artifacts))
    cp1 = r1.checkpoint
    fail_poster.active = False
    fail_fanart = _FailAt(monkeypatch, s, 5)
    r2 = execute_filesystem(preflight_execution(s.plan, s.artifacts, cp1))
    cp2 = r2.checkpoint
    assert r2.status is ExecutionStatus.PARTIAL and r2.new_effect_count == 1
    assert cp2.checkpoint_id != cp1.checkpoint_id and cp2.seal != cp1.seal
    assert cp2.completed_effects[:len(cp1.completed_effects)] == cp1.completed_effects
    assert len(cp2.completed_effects) == len(cp1.completed_effects) + 1
    with pytest.raises(CheckpointError) as info:
        preflight_execution(s.plan, s.artifacts, cp1)
    assert info.value.reason is CheckpointRejectionReason.CONSUMED
    fail_fanart.active = False
    r3 = execute_filesystem(preflight_execution(s.plan, s.artifacts, cp2))
    assert r3.status is ExecutionStatus.SUCCESS and r3.checkpoint is None
    assert r3.completed_effects[:len(cp2.completed_effects)] == cp2.completed_effects
    with pytest.raises(CheckpointError):
        preflight_execution(s.plan, s.artifacts, cp2)


def _partial_at_poster(tmp_path, monkeypatch):
    s = _scene(tmp_path, "full_3_extra")
    fail = _FailAt(monkeypatch, s, 4)
    result = execute_filesystem(preflight_execution(s.plan, s.artifacts))
    fail.active = False
    assert result.status is ExecutionStatus.PARTIAL
    return s, result


def test_manifest_changed_by_one_byte_is_refused_without_mutation(tmp_path, monkeypatch):
    s, result = _partial_at_poster(tmp_path, monkeypatch)
    changed = make_manifest(s.plan, **SHAPES["full_3_extra"],
                            nfo_text=NFO_TEXT.replace("Example Title", "Example Titlf"))  # one byte
    before = tree_layout(s.root)
    with monkeypatch.context() as m:
        trap, _ = trap_mutations_allowing_reads(m)
        with pytest.raises(CheckpointError) as info:
            preflight_execution(s.plan, changed, result.checkpoint)
    assert info.value.reason is CheckpointRejectionReason.MANIFEST_MISMATCH and trap.calls == []
    assert tree_layout(s.root) == before


@pytest.mark.parametrize("tamper,reason", [
    ("rewrite_same_size", PreflightBlockReason.COMPLETED_EFFECT_CHANGED),
    ("delete", PreflightBlockReason.COMPLETED_EFFECT_MISSING),
    ("replace_same_bytes", PreflightBlockReason.COMPLETED_EFFECT_CHANGED),
])
def test_completed_artifact_tampered_before_resume_blocks(tmp_path, monkeypatch, tamper, reason):
    s, result = _partial_at_poster(tmp_path, monkeypatch)
    nfo = s.plan.nfo_path.absolute_path
    data = Path(nfo).read_bytes()
    if tamper == "rewrite_same_size":
        with open(nfo, "r+b") as handle:
            handle.write(bytes([data[0] ^ 0x20]))
    elif tamper == "delete":
        os.unlink(nfo)
    else:
        os.unlink(nfo)
        Path(nfo).write_bytes(data)
    preflight = preflight_execution(s.plan, s.artifacts, result.checkpoint)
    assert not preflight.ready and reason in {b.reason for b in preflight.blockers}
    with pytest.raises(PreflightNotReadyError):
        execute_filesystem(preflight)
    assert not is_consumed(result.checkpoint.checkpoint_id)


@pytest.mark.parametrize("where", ["target", "extrafanart"])
def test_unexpected_entry_blocks_and_is_never_touched(tmp_path, monkeypatch, where):
    s = _scene(tmp_path, "full_3_extra")
    fail = _FailAt(monkeypatch, s, 9)  # after U7 and the first extrafanart
    result = execute_filesystem(preflight_execution(s.plan, s.artifacts))
    fail.active = False
    directory = (s.plan.target_directory if where == "target" else s.plan.extrafanart_directory).absolute_path
    planted = os.path.join(directory, "planted-by-someone.txt")
    Path(planted).write_bytes(b"not ours")
    preflight = preflight_execution(s.plan, s.artifacts, result.checkpoint)
    assert PreflightBlockReason.UNEXPECTED_ENTRY in {b.reason for b in preflight.blockers}
    assert Path(planted).read_bytes() == b"not ours"


def test_source_unlink_failed_resume_only_removes_the_source(tmp_path, monkeypatch):
    s = _scene(tmp_path, "nfo_only")
    fail = _FailAt(monkeypatch, s, 2)  # link publishes, the verified source unlink fails
    first = execute_filesystem(preflight_execution(s.plan, s.artifacts))
    assert first.failure.kind is F.SOURCE_UNLINK_FAILED
    assert [e.kind for e in first.completed_effects] == [EffectKind.TARGET_DIRECTORY_CREATED,
                                                          EffectKind.MEDIA_PUBLISHED]
    fail.active = False
    phases, publishes = [], []
    real_transfer = executor.transfer_media
    monkeypatch.setattr(executor, "transfer_media",
                        lambda *a, resume_phase: phases.append(resume_phase) or real_transfer(*a, resume_phase=resume_phase))
    for op in ("rename", "link"):
        real = getattr(_fs._FS, op)
        inject(monkeypatch, **{op: (lambda r, name: lambda a, b: publishes.append(name) or r(a, b))(real, op)})
    second = execute_filesystem(preflight_execution(s.plan, s.artifacts, first.checkpoint))
    assert second.status is ExecutionStatus.SUCCESS
    assert phases == [ResumePhase.SOURCE_REMOVAL_ONLY] and publishes == []  # never re-published
    assert second.completed_effects[2].kind is EffectKind.SOURCE_REMOVED and second.new_effect_count == 3


def test_directory_fsync_failed_resume_fsyncs_then_unlinks_without_republishing(tmp_path, monkeypatch):
    s = _scene(tmp_path, "nfo_only")
    use_strategy(monkeypatch, "link")
    with monkeypatch.context() as m:
        FakeDirectoryFsync(m, s.plan.target_directory.absolute_path, fsync_error=OSError(errno.EIO, "fsync"))
        first = execute_filesystem(preflight_execution(s.plan, s.artifacts))
    assert first.failure.kind is F.TARGET_DIRECTORY_FSYNC_FAILED and os.path.exists(s.source_path)
    order = []
    fake = FakeDirectoryFsync(monkeypatch, s.plan.target_directory.absolute_path)
    for op in ("link", "rename", "unlink"):
        real = getattr(_fs._FS, op)
        inject(monkeypatch, **{op: (lambda r, name: lambda *a: order.append((name, a[0])) or r(*a))(real, op)})
    real_fsync = _fs._FS.fsync
    inject(monkeypatch, fsync=lambda fd: order.append(("fsync", fd)) or real_fsync(fd))
    second = execute_filesystem(preflight_execution(s.plan, s.artifacts, first.checkpoint))
    assert second.status is ExecutionStatus.SUCCESS and "fsync" in fake.events
    assert order[:2] == [("fsync", FakeDirectoryFsync.FD), ("unlink", s.source_path)]
    assert not any(name in ("link", "rename") for name, _ in order)


def test_leftovers_are_carried_across_checkpoints_and_never_deleted(tmp_path, monkeypatch):
    s = _scene(tmp_path, "full_3_extra")
    poster = next(r for r in s.artifacts if r.kind is ArtifactKind.POSTER)
    with monkeypatch.context() as m:  # POSTER: P4-C6 write fails AND its temp cleanup fails -> a leftover
        real_mat = executor.materialize_artifact

        def poster_with_leftover(request):
            if request is poster:
                inject_p4c6(m, write=failing(OSError(errno.ENOSPC, "full")),
                            unlink=failing(PermissionError(errno.EACCES, "busy")))
            return real_mat(request)

        m.setattr(executor, "materialize_artifact", poster_with_leftover)
        r1 = execute_filesystem(preflight_execution(s.plan, s.artifacts))
    assert r1.failure.kind is F.ARTIFACT_CLEANUP_FAILED and len(r1.leftover_temporaries) == 1
    leftover = r1.leftover_temporaries[0]
    leftover_path = os.path.join(s.plan.target_directory.absolute_path, leftover.name)
    assert r1.checkpoint.leftover_temporaries == (leftover,)
    fail = _FailAt(monkeypatch, s, 6)  # THUMB
    r2 = execute_filesystem(preflight_execution(s.plan, s.artifacts, r1.checkpoint))
    assert r2.status is ExecutionStatus.PARTIAL and r2.checkpoint.leftover_temporaries == (leftover,)
    fail.active = False
    r3 = execute_filesystem(preflight_execution(s.plan, s.artifacts, r2.checkpoint))
    assert r3.status is ExecutionStatus.SUCCESS and r3.leftover_temporaries == (leftover,)
    assert os.path.isfile(leftover_path)  # tolerated, reported, never deleted or adopted


def test_exdev_mode_is_kept_across_resume(tmp_path, monkeypatch):
    s = _scene(tmp_path, "full_3_extra")
    for op in ("rename", "link"):
        real = getattr(_fs._FS, op)
        inject(monkeypatch, **{op: (lambda r: lambda a, b: (_ for _ in ()).throw(OSError(errno.EXDEV, "x"))
                                    if a == s.source_path else r(a, b))(real)})
    fail = _FailAt(monkeypatch, s, 3)  # NFO
    first = execute_filesystem(preflight_execution(s.plan, s.artifacts))
    assert first.transfer_mode is TransferMode.CROSS_VOLUME
    assert first.checkpoint.transfer_mode is TransferMode.CROSS_VOLUME
    digest = hashlib.sha256(MEDIA).hexdigest()
    assert first.media_sha256 == digest
    fail.active = False
    preflight = preflight_execution(s.plan, s.artifacts, first.checkpoint)
    assert preflight.transfer_mode is TransferMode.CROSS_VOLUME
    second = execute_filesystem(preflight)
    assert second.status is ExecutionStatus.SUCCESS and second.transfer_mode is TransferMode.CROSS_VOLUME
    assert second.media_sha256 == digest  # restored from the recorded effect, never re-read


def test_resume_revalidation_failure_is_partial_never_failed(tmp_path, monkeypatch):
    s, result = _partial_at_poster(tmp_path, monkeypatch)
    preflight = preflight_execution(s.plan, s.artifacts, result.checkpoint)
    assert preflight.ready
    Path(s.plan.target_directory.absolute_path, "late-entry").write_bytes(b"x")  # after the preflight
    spy = MaterializeSpy(monkeypatch)
    resumed = execute_filesystem(preflight)
    assert resumed.status is ExecutionStatus.PARTIAL and resumed.failure.kind is F.UNEXPECTED_ENTRY
    assert resumed.new_effect_count == 0 and spy.requests == []
    assert resumed.checkpoint.checkpoint_id != result.checkpoint.checkpoint_id
    assert resumed.checkpoint.completed_effects == result.completed_effects
    assert is_consumed(result.checkpoint.checkpoint_id)
