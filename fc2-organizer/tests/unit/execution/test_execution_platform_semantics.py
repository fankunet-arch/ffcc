"""P4-C7 S6: platform semantics final gate (contract section 26, item by item; construction plan S6).

Every test runs the integrated executor (``preflight_execution`` + ``execute_filesystem``) below ``tmp_path``.

Evidence classes (named in each test):

* **native Windows** -- executed only on a Windows host (``os.rename`` = ``MoveFileExW`` without replace, NTFS
  reparse points / case-insensitive names, read-only attribute, sharing violations, no directory ``fsync``);
* **native POSIX** -- executed only on a POSIX host (``link`` + real ``O_DIRECTORY`` ``fsync``, ``O_NOFOLLOW``,
  case-sensitive names); on a Windows host these SKIP and are an evidence gap, never counted as passed;
* **seam** -- the frozen private seams (``transfer._SAME_VOLUME_STRATEGY``, ``transfer._DIRECTORY_FSYNC``,
  ``_fs._FS``) select or observe the other platform's strategy on any host. Seam evidence is strategy-level
  evidence; it is never presented as native evidence of the other platform.
* **native cross-volume** -- only with ``FC2_EXECUTION_CROSS_VOLUME_ROOT`` (a directory on another volume; the
  test creates and removes only its own random subdirectory there); otherwise SKIP (evidence gap).
"""

from __future__ import annotations

import errno
import hashlib
import os
import secrets
import shutil
import stat
import types
from pathlib import Path

import pytest

from fc2_organizer.execution import (
    EffectKind,
    ExecutionFailureKind,
    ExecutionStatus,
    PreflightBlockReason,
    PreflightMode,
    PreflightNotReadyError,
    TransferMode,
    TransferStage,
    execute_filesystem,
    preflight_execution,
)
from fc2_organizer.execution import _fs, executor, paths, transfer
from fc2_organizer.materialization import ArtifactKind, ArtifactWriteError, ArtifactWriteStage

from ._builders import make_manifest, make_plan, scene
from ._helpers import (
    FakeDirectoryFsync,
    SeamLog,
    assert_source_not_lost,
    force_cross_volume_devices,
    inject,
    isolated_source_claims,  # noqa: F401 -- autouse fixture: per-test claim registry isolation
    try_junction,
    try_symlink,
    use_strategy,
    write_generated_media,
)

F = ExecutionFailureKind
WINDOWS = os.name == "nt"
MIB = 1 << 20
MEDIA = b"platform-semantics-media \x00\x01\xfe" * 97
SHA = hashlib.sha256(MEDIA).hexdigest()

native_windows = pytest.mark.skipif(
    not WINDOWS, reason="Windows native evidence: NOT EXECUTED on a non-Windows host (seam evidence only)")
native_posix = pytest.mark.skipif(
    WINDOWS, reason="POSIX native evidence: NOT EXECUTED on a Windows host (seam evidence only)")


def _scene(tmp_path: Path, **options):
    return scene(tmp_path, content=MEDIA, **options)


def _paths(s):
    plan = s.plan
    return (plan.target_directory.absolute_path, plan.target_media_path.absolute_path,
            plan.extrafanart_directory.absolute_path)


def _run(s):
    preflight = preflight_execution(s.plan, s.artifacts)
    assert preflight.ready and preflight.mode is PreflightMode.FRESH
    return preflight, execute_filesystem(preflight)


def _resume(s, result):
    preflight = preflight_execution(s.plan, s.artifacts, result.checkpoint)
    assert preflight.ready and preflight.mode is PreflightMode.RESUME
    final = execute_filesystem(preflight)
    assert final.status is ExecutionStatus.SUCCESS
    assert final.completed_effects[:len(result.completed_effects)] == result.completed_effects
    return final


def _entry_state(path) -> tuple:
    st = os.lstat(path)
    with open(path, "rb") as handle:
        return handle.read(), st.st_ino, st.st_mtime_ns


def _assert_success_layout(s, result) -> None:
    target, final, efd = _paths(s)
    assert result.status is ExecutionStatus.SUCCESS
    assert Path(final).read_bytes() == MEDIA and not os.path.lexists(s.source_path)
    assert os.path.isdir(efd)
    for request in s.artifacts:
        assert Path(request.target_path).read_bytes() == request.content


class U2Scope:
    """``active`` while the executor's U2 (``transfer_media``) runs."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.active = False
        real = executor.transfer_media

        def wrapped(*args, **kwargs):
            self.active = True
            try:
                return real(*args, **kwargs)
            finally:
                self.active = False

        monkeypatch.setattr(executor, "transfer_media", wrapped)


def plant_after_probe(monkeypatch, scope: U2Scope, probed: str, planted: str, content: bytes) -> dict:
    """A REAL entry appears at ``planted`` right after U2's early absence probe of ``probed`` (the final media):
    only the no-replace primitive itself can refuse it (contract sections 18.1, 23)."""
    state: dict = {}
    real = _fs._FS.lstat

    def lstat(path):
        if scope.active and path == probed and not state:
            try:
                return real(path)
            except FileNotFoundError:
                with open(planted, "wb") as handle:
                    handle.write(content)
                state["entry"] = _entry_state(planted)
                raise
        return real(path)

    inject(monkeypatch, lstat=lstat)
    return state


def no_replace_rename(src: str, dst: str) -> None:
    """Seam model of ``MoveFileExW`` without ``MOVEFILE_REPLACE_EXISTING`` for a non-Windows host (where
    ``os.rename`` would replace): an existing destination is refused, never replaced."""
    if os.path.lexists(dst):
        raise FileExistsError(errno.EEXIST, "destination exists")
    os.rename(src, dst)


def _record(monkeypatch, *ops):
    calls = []
    for op in ops:
        real = getattr(_fs._FS, op)
        inject(monkeypatch, **{op: (lambda r, name: lambda *a: calls.append((name, a)) or r(*a))(real, op)})
    return calls


def _trap(monkeypatch, *ops):
    hits = []

    def trapped(name):
        def op(*args):
            hits.append((name, args))
            raise AssertionError("forbidden call: " + name)
        return op

    inject(monkeypatch, **{op: trapped(op) for op in ops})
    return hits


def _trap_chmod(monkeypatch):
    hits = []
    for name in ("chmod", "lchmod", "fchmod"):
        if hasattr(os, name):
            monkeypatch.setattr(os, name, lambda *a, _n=name: hits.append(_n) or (_ for _ in ()).throw(
                AssertionError("P4-C7 never changes permissions")))
    return hits


# =========================================================================== 26.1 Windows


@native_windows
def test_windows_same_volume_publish_is_one_rename_without_replacement(tmp_path, monkeypatch):
    """26.1 / 18.2 native: one ``os.rename`` (MoveFileExW, no replace flag) moves the media; no link, no source
    unlink, no directory fsync; the file id is preserved."""
    s = _scene(tmp_path, extra=1)
    log = SeamLog(monkeypatch)
    preflight, result = _run(s)
    target, final, _ = _paths(s)
    assert transfer._SAME_VOLUME_STRATEGY == "rename" and transfer._DIRECTORY_FSYNC is False
    _assert_success_layout(s, result)
    assert log.ops("rename", "link") == [("rename", s.source_path)]
    assert all(arg != s.source_path for op, arg in log.ops("unlink"))
    assert all(arg != target for op, arg in log.ops("open"))
    media = next(e for e in result.completed_effects if e.kind is EffectKind.MEDIA_PUBLISHED)
    assert media.identity.inode == preflight.source_identity.inode == os.lstat(final).st_ino


@native_windows
@pytest.mark.parametrize("variant", ["exact", "case_variant"])
@pytest.mark.parametrize("route", ["same_volume", "cross_volume"])
def test_windows_existing_target_is_never_replaced(tmp_path, monkeypatch, variant, route):
    """26.1 / 18.2 / 19 step 7 / 23 native: an entry that appears after the early probe -- the exact final name
    or (NTFS casefold) a case variant -- is refused by the no-replace rename itself; never replaced."""
    if route == "cross_volume":
        force_cross_volume_devices(monkeypatch)
    s = _scene(tmp_path, extra=0)
    target, final, _ = _paths(s)
    planted = final if variant == "exact" else os.path.join(target, os.path.basename(final).upper())
    assert planted == final or planted != final and planted.casefold() == final.casefold()
    state = plant_after_probe(monkeypatch, U2Scope(monkeypatch), final, planted, b"another writer's file")
    source_before = _entry_state(s.source_path)
    _, result = _run(s)
    stage = TransferStage.SAME_VOLUME_PRIMITIVE if route == "same_volume" else TransferStage.PUBLISH
    assert result.status is ExecutionStatus.PARTIAL and result.failure.kind is F.TARGET_CONFLICT
    assert result.failure.stage is stage
    assert [e.kind for e in result.completed_effects] == [EffectKind.TARGET_DIRECTORY_CREATED]
    assert _entry_state(planted) == state["entry"]                 # bytes, inode, mtime untouched
    assert _entry_state(s.source_path) == source_before
    assert sorted(os.listdir(target)) == [os.path.basename(planted)]  # no temporary residue either


def test_rename_strategy_seam_never_replaces_on_any_host(tmp_path, monkeypatch):
    """26.1 seam (any host): the Windows rename strategy selected through the frozen strategy seam; on a
    non-Windows host ``_FS.rename`` is the no-replace model (MoveFileExW semantics), on Windows it is native."""
    use_strategy(monkeypatch, "rename")
    if not WINDOWS:
        inject(monkeypatch, rename=no_replace_rename)
    s = _scene(tmp_path)
    _, final, _ = _paths(s)
    state = plant_after_probe(monkeypatch, U2Scope(monkeypatch), final, final, b"occupant")
    _, result = _run(s)
    assert result.failure.kind is F.TARGET_CONFLICT and _entry_state(final) == state["entry"]
    assert_source_not_lost(s.source_path, final, SHA)


@native_windows
def test_windows_junction_library_root_is_refused(tmp_path):
    """26.1 reparse point (junction) native: a junction as library root is a link -> blocked, never followed."""
    real = tmp_path / "real-library"
    real.mkdir()
    s = scene(tmp_path, content=MEDIA, make_library=False)
    try_junction(Path(s.library_root), real)
    preflight = preflight_execution(s.plan, s.artifacts)
    assert not preflight.ready
    assert PreflightBlockReason.LIBRARY_ROOT_IS_LINK in {b.reason for b in preflight.blockers}
    with pytest.raises(PreflightNotReadyError):
        execute_filesystem(preflight)
    assert os.listdir(real) == [] and Path(s.source_path).read_bytes() == MEDIA


def test_symlink_library_root_is_refused(tmp_path):
    """26.1 / 26.2 symlink native (needs symlink privilege on Windows; SKIP with reason otherwise)."""
    real = tmp_path / "real-library"
    real.mkdir()
    s = scene(tmp_path, content=MEDIA, make_library=False)
    try_symlink(Path(s.library_root), real, target_is_directory=True)
    preflight = preflight_execution(s.plan, s.artifacts)
    assert PreflightBlockReason.LIBRARY_ROOT_IS_LINK in {b.reason for b in preflight.blockers}
    assert os.listdir(real) == []


@native_windows
def test_windows_target_directory_replaced_by_junction_between_units(tmp_path, monkeypatch):
    """26.1 / 21 native: after U1, the owned target directory is swapped for a junction to a look-alike
    directory; U2's revalidation sees a reparse point -> TARGET_DIRECTORY_CHANGED, nothing moved or deleted."""
    s = _scene(tmp_path, extra=0)
    target, final, _ = _paths(s)
    moved = target + "-moved-away"
    real_transfer = executor.transfer_media

    def swap_then_transfer(*args, **kwargs):
        os.rename(target, moved)
        try_junction(Path(target), Path(moved))
        return real_transfer(*args, **kwargs)

    monkeypatch.setattr(executor, "transfer_media", swap_then_transfer)
    try:
        _, result = _run(s)
        assert result.status is ExecutionStatus.PARTIAL and result.failure.kind is F.TARGET_DIRECTORY_CHANGED
        assert [e.kind for e in result.completed_effects] == [EffectKind.TARGET_DIRECTORY_CREATED]
        assert os.listdir(moved) == [] and Path(s.source_path).read_bytes() == MEDIA
        assert _fs.is_link(os.lstat(target))
        blocked = preflight_execution(s.plan, s.artifacts, result.checkpoint)
        assert PreflightBlockReason.TARGET_DIRECTORY_CHANGED in {b.reason for b in blocked.blockers}
    finally:
        if os.path.lexists(target):
            os.rmdir(target)  # removes only this test's own junction (never its target)


def test_reparse_point_attribute_is_a_link_on_any_host():
    """26.1 reparse judgement (lexical on the stat result, any host): any FILE_ATTRIBUTE_REPARSE_POINT entry is a
    link, whatever its type bits say; the judgement never depends on ``os.path.isjunction``."""
    reparse = stat.FILE_ATTRIBUTE_REPARSE_POINT
    for mode in (stat.S_IFDIR | 0o755, stat.S_IFREG | 0o644):
        assert _fs.is_link(types.SimpleNamespace(st_mode=mode, st_file_attributes=reparse))
        assert not _fs.is_link(types.SimpleNamespace(st_mode=mode, st_file_attributes=0))
        assert not _fs.is_link(types.SimpleNamespace(st_mode=mode))
    assert _fs.is_link(types.SimpleNamespace(st_mode=stat.S_IFLNK | 0o777))


def test_name_comparison_rules_casefold_on_windows_exact_on_posix():
    """26.1 / 26.2 lexical rules (both platforms' rules on any host)."""
    assert paths.same_entry_name("Poster.JPG", "poster.jpg", windows=True)
    assert not paths.same_entry_name("Poster.JPG", "poster.jpg", windows=False)
    assert paths.same_entry_name("ΣΊΣΥΦΟΣ.nfo", "σίσυφος.nfo", windows=True)


def _partial_at_poster(s, monkeypatch):
    poster = next(r for r in s.artifacts if r.kind is ArtifactKind.POSTER)
    real = executor.materialize_artifact
    with monkeypatch.context() as m:
        m.setattr(executor, "materialize_artifact", lambda r: (_ for _ in ()).throw(
            ArtifactWriteError(ArtifactWriteStage.WRITE, errno.ENOSPC)) if r is poster else real(r))
        _, result = _run(s)
    assert result.status is ExecutionStatus.PARTIAL and len(result.completed_effects) == 4
    return result


def test_resume_inventory_uses_the_host_name_rule(tmp_path, monkeypatch):
    """26.1 casefold enumeration (native rule of this host): the directory listing reports the completed names in
    another case. Windows (casefold) accepts it and resumes; POSIX (exact) sees unexpected + missing entries."""
    s = _scene(tmp_path, extra=1)
    result = _partial_at_poster(s, monkeypatch)
    target, _, _ = _paths(s)
    real_listdir = _fs._FS.listdir
    inject(monkeypatch, listdir=lambda p: [n.upper() for n in real_listdir(p)] if p == target else real_listdir(p))
    preflight = preflight_execution(s.plan, s.artifacts, result.checkpoint)
    if WINDOWS:
        assert preflight.ready
        assert execute_filesystem(preflight).status is ExecutionStatus.SUCCESS
    else:
        reasons = {b.reason for b in preflight.blockers}
        assert {PreflightBlockReason.UNEXPECTED_ENTRY, PreflightBlockReason.COMPLETED_EFFECT_MISSING} <= reasons


@native_windows
@pytest.mark.parametrize("strategy", ["rename", "link"])
def test_windows_read_only_source_is_never_chmodded(tmp_path, monkeypatch, strategy):
    """26.1 native: a read-only source. The rename strategy moves it (the attribute travels with the file);
    the link strategy's source unlink fails -> SOURCE_UNLINK_FAILED, never chmod / forced delete. After the
    user clears the attribute, the returned checkpoint resumes to SUCCESS (source removal only)."""
    use_strategy(monkeypatch, strategy)
    s = _scene(tmp_path, extra=0)
    _, final, _ = _paths(s)
    os.chmod(s.source_path, stat.S_IREAD)
    try:
        with monkeypatch.context() as m:
            chmods = _trap_chmod(m)
            _, result = _run(s)
        assert chmods == []
        if strategy == "rename":
            _assert_success_layout(s, result)
            assert os.stat(final).st_mode & stat.S_IWRITE == 0
            return
        assert result.status is ExecutionStatus.PARTIAL and result.failure.kind is F.SOURCE_UNLINK_FAILED
        assert result.failure.errno == errno.EACCES
        assert os.stat(s.source_path).st_mode & stat.S_IWRITE == 0
        assert os.lstat(s.source_path).st_ino == os.lstat(final).st_ino  # two names of one file
        os.chmod(s.source_path, stat.S_IREAD | stat.S_IWRITE)  # the user's own action
        _assert_success_layout(s, _resume(s, result))
    finally:
        for path in (s.source_path, final):
            if os.path.lexists(path):
                os.chmod(path, stat.S_IREAD | stat.S_IWRITE)


def test_source_unlink_permission_error_seam_never_chmods(tmp_path, monkeypatch):
    """26.1 seam (any host): an unlink PermissionError on the source is SOURCE_UNLINK_FAILED, both names kept."""
    use_strategy(monkeypatch, "link")
    s = _scene(tmp_path)
    _, final, _ = _paths(s)
    real = _fs._FS.unlink
    with monkeypatch.context() as m:
        inject(m, unlink=lambda p: (_ for _ in ()).throw(PermissionError(errno.EACCES, "denied"))
               if p == s.source_path else real(p))
        chmods = _trap_chmod(m)
        _, result = _run(s)
    assert chmods == [] and result.failure.kind is F.SOURCE_UNLINK_FAILED
    assert os.path.isfile(s.source_path) and Path(final).read_bytes() == MEDIA
    _assert_success_layout(s, _resume(s, result))


@native_windows
@pytest.mark.parametrize("route", ["same_volume", "cross_volume"])
def test_windows_never_fsyncs_a_directory(tmp_path, monkeypatch, route):
    """26.1 native: no directory fsync on Windows (a directory cannot be opened); fsync only on file fds."""
    if route == "cross_volume":
        force_cross_volume_devices(monkeypatch)
    s = _scene(tmp_path, extra=2)
    opened = []
    real_open = _fs._FS.open
    inject(monkeypatch, open=lambda path, *rest: opened.append(path) or real_open(path, *rest))
    _, result = _run(s)
    _assert_success_layout(s, result)
    assert transfer._DIRECTORY_FSYNC is False
    assert not any(os.path.isdir(path) for path in opened)
    # same volume: the rename opens nothing; cross volume: exactly the source and the owned temporary
    assert len(opened) == (0 if route == "same_volume" else 2)


def test_windows_directory_fsync_rule_through_the_seam(tmp_path, monkeypatch):
    """26.1 seam (any host): with the Windows rule (``_DIRECTORY_FSYNC`` false) even the link strategy never opens
    the target directory."""
    use_strategy(monkeypatch, "link")
    monkeypatch.setattr(transfer, "_DIRECTORY_FSYNC", False)
    s = _scene(tmp_path)
    target, _, _ = _paths(s)
    calls = _record(monkeypatch, "open")
    _, result = _run(s)
    _assert_success_layout(s, result)
    assert all(args[0] != target for _, args in calls)


@native_windows
@pytest.mark.parametrize("route,kind", [("same_volume", F.MEDIA_TRANSFER_FAILED),
                                        ("cross_volume", F.SOURCE_UNLINK_FAILED)])
def test_windows_sharing_violation_fails_closed_then_resumes(tmp_path, monkeypatch, route, kind):
    """26.1 native: another handle holds the source open (no FILE_SHARE_DELETE). Same volume: the rename is a
    sharing violation -> MEDIA_TRANSFER_FAILED, nothing moved. Cross volume: the copy is published, the source
    unlink fails -> SOURCE_UNLINK_FAILED, both complete. Never a forced close; resume after the handle closes."""
    if route == "cross_volume":
        force_cross_volume_devices(monkeypatch)
    s = _scene(tmp_path, extra=1)
    _, final, _ = _paths(s)
    with open(s.source_path, "rb"):
        _, result = _run(s)
        assert result.status is ExecutionStatus.PARTIAL and result.failure.kind is kind
        assert result.failure.errno is not None
        assert_source_not_lost(s.source_path, final, SHA)
        assert Path(s.source_path).read_bytes() == MEDIA
        if route == "same_volume":
            assert not os.path.lexists(final)
        else:
            assert Path(final).read_bytes() == MEDIA
    _assert_success_layout(s, _resume(s, result))


def test_sharing_violation_seam_on_any_host(tmp_path, monkeypatch):
    """26.1 seam (any host): a rename refused with a permission / sharing error is MEDIA_TRANSFER_FAILED with no
    media effect and no fallback."""
    use_strategy(monkeypatch, "rename")
    if not WINDOWS:
        inject(monkeypatch, rename=no_replace_rename)
    s = _scene(tmp_path)
    real = _fs._FS.rename
    with monkeypatch.context() as m:
        inject(m, rename=lambda a, b: (_ for _ in ()).throw(PermissionError(errno.EACCES, "sharing violation"))
               if a == s.source_path else real(a, b))
        links = _trap(m, "link")
        _, result = _run(s)
    assert result.failure.kind is F.MEDIA_TRANSFER_FAILED and links == []
    assert [e.kind for e in result.completed_effects] == [EffectKind.TARGET_DIRECTORY_CREATED]
    _assert_success_layout(s, _resume(s, result))


# =========================================================================== 26.2 POSIX


def _assert_in_order(log: SeamLog, *steps) -> list[int]:
    positions, start = [], 0
    for op, arg in steps:
        start = log.index(op, arg, start)
        positions.append(start)
        start += 1
    return positions


@pytest.mark.parametrize("route", ["same_volume", "cross_volume"])
def test_posix_strategy_order_through_the_seam(tmp_path, monkeypatch, route):
    """26.2 / 18.3 / 19 seam (any host): link -> publish verification -> directory fsync -> source path
    revalidation -> source unlink; the directory fsync happens strictly before the source unlink; never rename."""
    use_strategy(monkeypatch, "link")
    if route == "cross_volume":
        force_cross_volume_devices(monkeypatch)
    s = _scene(tmp_path)
    target, final, _ = _paths(s)
    fake = FakeDirectoryFsync(monkeypatch, target)
    log = SeamLog(monkeypatch)
    _, result = _run(s)
    _assert_success_layout(s, result)
    first = s.source_path if route == "same_volume" else None
    link_at = log.index("link", first)
    if route == "cross_volume":
        assert os.path.basename(log.calls[link_at][1]).startswith(".fc2tmp-")
        assert log.calls[link_at + 1][0] == "unlink"  # the owned temporary right after the publish link
    _assert_in_order(log, ("link", first), ("lstat", final), ("open", target), ("fsync", fake.FD),
                     ("close", fake.FD), ("lstat", s.source_path), ("unlink", s.source_path))
    assert fake.events == ["open", "fsync", "close"]
    assert log.ops("rename") == []


@native_posix
def test_posix_native_link_order_with_a_real_directory_fsync(tmp_path, monkeypatch):
    """26.2 native POSIX: the host strategy is link; a real O_DIRECTORY fd of the target directory is fsynced
    after the link and before the source unlink."""
    assert transfer._SAME_VOLUME_STRATEGY == "link" and transfer._DIRECTORY_FSYNC is True
    s = _scene(tmp_path)
    target, final, _ = _paths(s)
    log = SeamLog(monkeypatch)
    _, result = _run(s)
    _assert_success_layout(s, result)
    link_at, open_at = _assert_in_order(log, ("link", s.source_path), ("open", target))
    fsync_at = next(i for i in range(open_at + 1, len(log.calls)) if log.calls[i][0] == "fsync")
    unlink_at = log.index("unlink", s.source_path, fsync_at)
    assert link_at < open_at < fsync_at < unlink_at and log.ops("rename") == []


@pytest.mark.parametrize("route", ["same_volume", "cross_volume"])
def test_link_publish_never_replaces_an_existing_final(tmp_path, monkeypatch, route):
    """26.2 / 18.3 / 23: the POSIX link strategy (seam-selected; ``os.link`` is native on this host) refuses an
    entry that appeared after the early probe (EEXIST); the occupant is never replaced."""
    use_strategy(monkeypatch, "link")
    if route == "cross_volume":
        force_cross_volume_devices(monkeypatch)
    s = _scene(tmp_path)
    target, final, _ = _paths(s)
    state = plant_after_probe(monkeypatch, U2Scope(monkeypatch), final, final, b"occupant bytes")
    _, result = _run(s)
    assert result.status is ExecutionStatus.PARTIAL and result.failure.kind is F.TARGET_CONFLICT
    assert _entry_state(final) == state["entry"] and Path(s.source_path).read_bytes() == MEDIA
    assert sorted(os.listdir(target)) == [os.path.basename(final)]


def test_cross_volume_source_open_flags(tmp_path, monkeypatch):
    """26.2 O_NOFOLLOW: the cross-volume source open carries O_NOFOLLOW wherever the platform defines it (POSIX),
    plus read-only / binary / no-inherit flags; it never carries a write, create or truncate flag."""
    force_cross_volume_devices(monkeypatch)
    s = _scene(tmp_path)
    calls = _record(monkeypatch, "open")
    _, result = _run(s)
    _assert_success_layout(s, result)
    flags = [args[1] for _, args in calls if args[0] == s.source_path]
    assert len(flags) == 1
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    assert flags[0] & nofollow == nofollow
    assert WINDOWS or nofollow != 0  # on POSIX the flag really exists; on Windows it is an evidence gap
    assert flags[0] & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND) == 0


@native_posix
def test_posix_native_symlink_swapped_in_before_open_is_refused_by_o_nofollow(tmp_path, monkeypatch):
    """26.2 native POSIX: the source path becomes a symlink right before the cross-volume open; O_NOFOLLOW makes
    the open fail (ELOOP) -> MEDIA_SOURCE_OPEN_FAILED; the link and its target are untouched."""
    force_cross_volume_devices(monkeypatch)
    s = _scene(tmp_path)
    moved = s.source_path + ".original"
    real_open = _fs._FS.open

    def swap_then_open(path, flags, *rest):
        if path == s.source_path and not os.path.islink(path):
            os.rename(path, moved)
            os.symlink(moved, path)
        return real_open(path, flags, *rest)

    inject(monkeypatch, open=swap_then_open)
    _, result = _run(s)
    assert result.failure.kind is F.MEDIA_SOURCE_OPEN_FAILED and result.failure.errno == errno.ELOOP
    assert os.path.islink(s.source_path) and Path(moved).read_bytes() == MEDIA


def test_file_swapped_in_before_open_is_refused_by_the_fd_identity_check(tmp_path, monkeypatch):
    """26.1 / 19 step 1 (any host): a different regular file is swapped in right before the cross-volume open; the
    fstat identity check refuses it (SOURCE_CHANGED); the substitute is never copied, published or deleted."""
    force_cross_volume_devices(monkeypatch)
    s = _scene(tmp_path)
    moved = s.source_path + ".original"
    real_open = _fs._FS.open
    swapped = []

    def swap_then_open(path, flags, *rest):
        if path == s.source_path and not swapped:
            os.rename(path, moved)
            Path(path).write_bytes(b"x" * len(MEDIA))
            swapped.append(_entry_state(path))
        return real_open(path, flags, *rest)

    inject(monkeypatch, open=swap_then_open)
    _, result = _run(s)
    assert result.failure.kind is F.SOURCE_CHANGED and result.failure.stage is TransferStage.SOURCE_FD_VALIDATE
    assert _entry_state(s.source_path) == swapped[0] and Path(moved).read_bytes() == MEDIA
    target, final, _ = _paths(s)
    assert os.listdir(target) == [] and not os.path.lexists(final)


@pytest.mark.parametrize("route", ["same_volume", "cross_volume"])
def test_source_replaced_after_publish_is_never_deleted(tmp_path, monkeypatch, route):
    """26.2 / 18.3 / 19 steps 9-10 / 25 (seam strategy, any host): after the complete publish, the source path is
    replaced by another file; the frozen source revalidation refuses the unlink (SOURCE_CHANGED); the substitute
    survives byte for byte and the final holds the media."""
    use_strategy(monkeypatch, "link")
    if route == "cross_volume":
        force_cross_volume_devices(monkeypatch)
    s = _scene(tmp_path)
    _, final, _ = _paths(s)
    real_link = _fs._FS.link
    substitute = []

    def link_then_replace_source(a, b):
        real_link(a, b)
        if b == final:
            if route == "same_volume":
                os.unlink(s.source_path)  # the other name of the final stays
            else:
                os.rename(s.source_path, s.source_path + ".original")
            Path(s.source_path).write_bytes(b"a different file " * 7)
            substitute.append(_entry_state(s.source_path))

    inject(monkeypatch, link=link_then_replace_source)
    _, result = _run(s)
    assert result.status is ExecutionStatus.PARTIAL and result.failure.kind is F.SOURCE_CHANGED
    assert result.failure.stage is TransferStage.SOURCE_PATH_REVALIDATE
    assert _entry_state(s.source_path) == substitute[0]
    assert Path(final).read_bytes() == MEDIA


@native_posix
def test_posix_native_case_variant_is_a_distinct_entry(tmp_path, monkeypatch):
    """26.2 native POSIX (case-sensitive filesystem): a case variant of the final media name is another entry;
    the media is published next to it and the variant is untouched."""
    probe = tmp_path / "CaseProbe"
    probe.write_bytes(b"")
    if (tmp_path / "caseprobe").exists():
        pytest.skip("POSIX native case-sensitivity: NOT EXECUTED (this filesystem is case-insensitive)")
    s = _scene(tmp_path)
    target, final, _ = _paths(s)
    variant = os.path.join(target, os.path.basename(final).upper())
    state = plant_after_probe(monkeypatch, U2Scope(monkeypatch), final, variant, b"case variant")
    _, result = _run(s)
    _assert_success_layout(s, result)
    assert _entry_state(variant) == state["entry"]


UNSUPPORTED_LINK_ERRNOS = sorted({errno.EPERM, errno.EMLINK, getattr(errno, "ENOTSUP", errno.EPERM),
                                  getattr(errno, "EOPNOTSUPP", errno.EPERM)})


@pytest.mark.parametrize("code", UNSUPPORTED_LINK_ERRNOS)
def test_unsupported_hardlink_fails_closed_without_rename_or_copy_fallback(tmp_path, monkeypatch, code):
    """26.2 / 18.3 (seam, any host): a filesystem without hard links -> MEDIA_TRANSFER_FAILED(errno), no media
    effect, never a rename and never a cross-volume copy; resume succeeds once linking works."""
    use_strategy(monkeypatch, "link")
    s = _scene(tmp_path)
    real_link = _fs._FS.link
    with monkeypatch.context() as m:
        inject(m, link=lambda a, b: (_ for _ in ()).throw(OSError(code, "no hard links"))
               if a == s.source_path else real_link(a, b))
        renames = _trap(m, "rename")
        creates = _record(m, "open")
        _, result = _run(s)
    assert renames == [] and not any(args[1] & os.O_CREAT for _, args in creates)
    assert result.failure.kind is F.MEDIA_TRANSFER_FAILED and result.failure.errno == code
    assert result.failure.stage is TransferStage.SAME_VOLUME_PRIMITIVE
    assert [e.kind for e in result.completed_effects] == [EffectKind.TARGET_DIRECTORY_CREATED]
    _assert_success_layout(s, _resume(s, result))


@pytest.mark.parametrize("route", ["same_volume", "cross_volume"])
def test_link_strategy_never_calls_an_overwrite_capable_rename(tmp_path, monkeypatch, route):
    """26.2 (seam, any host): with the POSIX strategies (media + P4-C6 artifacts) not a single execution-seam
    rename happens during a complete execution."""
    use_strategy(monkeypatch, "link")
    if route == "cross_volume":
        force_cross_volume_devices(monkeypatch)
    s = _scene(tmp_path, extra=2)
    renames = _trap(monkeypatch, "rename")
    _, result = _run(s)
    _assert_success_layout(s, result)
    assert renames == []


@native_posix
def test_posix_native_host_strategy_is_link():
    """26.2 native POSIX: the host's same-volume strategy is link (never rename(2)); directory fsync is on."""
    assert transfer._SAME_VOLUME_STRATEGY == "link" and transfer._DIRECTORY_FSYNC is True


# =========================================================================== native cross-volume (26.1 st_dev)

_NATIVE_ROOT = os.environ.get("FC2_EXECUTION_CROSS_VOLUME_ROOT")


@pytest.mark.skipif(not _NATIVE_ROOT, reason="Native cross-volume evidence: NOT EXECUTED "
                                             "(FC2_EXECUTION_CROSS_VOLUME_ROOT not configured)")
def test_native_cross_volume_integrated_execution(tmp_path):
    """17 / 19 / 26.1 native: the source lives on another volume (st_dev differs) -> the executor copies with the
    verified 10-step flow and removes the source last. Only this test's own random directory is created and
    removed below the configured root."""
    own = os.path.join(_NATIVE_ROOT, "fc2-p4c7-s6-" + secrets.token_hex(8))
    os.mkdir(own)
    try:
        source = os.path.join(own, "native-source.mp4")
        size = 3 * MIB + 17
        digest = write_generated_media(source, size)
        library = tmp_path / "library"
        library.mkdir()
        plan = make_plan(str(library), source, size=size)
        artifacts = make_manifest(plan, extra=2)
        preflight = preflight_execution(plan, artifacts)
        if preflight.transfer_mode is not TransferMode.CROSS_VOLUME:
            pytest.skip("Native cross-volume evidence: NOT EXECUTED (the configured root is on the tmp_path volume)")
        result = execute_filesystem(preflight)
        assert result.status is ExecutionStatus.SUCCESS and result.transfer_mode is TransferMode.CROSS_VOLUME
        assert result.media_sha256 == digest and not os.path.lexists(source)
        final = plan.target_media_path.absolute_path
        assert_source_not_lost(source, final, digest)
    finally:
        shutil.rmtree(own, ignore_errors=True)
