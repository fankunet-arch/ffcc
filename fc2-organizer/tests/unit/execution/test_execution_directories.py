"""P4-C7 S2: exclusive target / extrafanart directory ownership (contract sections 21-22; plan S2)."""

from __future__ import annotations

import errno
import os
import stat
import threading

import pytest

from fc2_organizer.execution import (
    EntryIdentity,
    EntryType,
    ExecutionFailure,
    ExecutionFailureKind,
    ExecutionInputError,
    ExecutionStep,
    TransferStage,
)
from fc2_organizer.execution import _fs
from fc2_organizer.execution.directories import (
    child_name,
    compare_inventory,
    create_extrafanart_directory,
    create_target_directory,
    revalidate_directory,
)

from ._builders import NUMBER, scene
from ._helpers import (
    fingerprint_tree,
    inject,
    lstat_rewriting,
    trap_mutations,
    try_junction,
    try_symlink,
    with_stat_fields,
)

F = ExecutionFailureKind


def _identity(path) -> EntryIdentity:
    st = os.lstat(path)
    return EntryIdentity(st.st_dev, st.st_ino, EntryType.DIRECTORY, None, None)


class MkdirCounter:
    def __init__(self, monkeypatch, before=None, after=None):
        self.calls: list[str] = []
        real = _fs._FS.mkdir

        def counting(path, mode):
            self.calls.append(path)
            if before:
                before(path)
            real(path, mode)
            if after:
                after(path)

        inject(monkeypatch, mkdir=counting)


def _assert_failure(result, step, kind, *, errno_=None, stage=None):
    identity, failure = result
    assert identity is None and type(failure) is ExecutionFailure
    assert (failure.step, failure.kind, failure.errno, failure.stage) == (step, kind, errno_, stage)
    # A value, never an exception: no raw OSError object / text is carried anywhere.
    assert not any(isinstance(getattr(failure, name), BaseException) for name in failure.__slots__)
    return failure


@pytest.fixture
def s(tmp_path):
    return scene(tmp_path)


def _lib(s) -> EntryIdentity:
    return _identity(s.library_root)


# --------------------------------------------------------------------------- target directory


def test_exclusive_create_success_and_snapshot(s, monkeypatch):
    counter = MkdirCounter(monkeypatch)
    identity, failure = create_target_directory(s.plan, _lib(s))
    target = s.plan.target_directory.absolute_path
    assert failure is None and identity == _identity(target)
    assert os.path.isdir(target) and os.listdir(target) == []
    assert counter.calls == [target]


def _occupy_target_blocks(s, monkeypatch):
    target = s.plan.target_directory.absolute_path
    before = fingerprint_tree(s.root)
    counter = MkdirCounter(monkeypatch)
    _assert_failure(create_target_directory(s.plan, _lib(s)), ExecutionStep.CREATE_DIRECTORY, F.TARGET_CONFLICT)
    assert counter.calls == []  # never reached mkdir, never adopted
    assert fingerprint_tree(s.root) == before
    return target


def test_existing_file_is_a_conflict(s, monkeypatch):
    with open(s.plan.target_directory.absolute_path, "wb") as handle:
        handle.write(b"occupant")
    _occupy_target_blocks(s, monkeypatch)


def test_existing_empty_directory_is_a_conflict(s, monkeypatch):
    os.mkdir(s.plan.target_directory.absolute_path)
    _occupy_target_blocks(s, monkeypatch)


def test_existing_symlink_is_a_conflict(s, monkeypatch):
    (s.root / "elsewhere").mkdir()
    try_symlink(s.root / "library" / NUMBER, s.root / "elsewhere", target_is_directory=True)
    _occupy_target_blocks(s, monkeypatch)


def test_existing_dangling_symlink_is_a_conflict(s, monkeypatch):
    try_symlink(s.root / "library" / NUMBER, s.root / "missing", target_is_directory=True)
    _occupy_target_blocks(s, monkeypatch)


def test_existing_junction_is_a_conflict(s, monkeypatch):
    (s.root / "elsewhere").mkdir()
    try_junction(s.root / "library" / NUMBER, s.root / "elsewhere")
    _occupy_target_blocks(s, monkeypatch)
    assert os.listdir(s.root / "elsewhere") == []


def test_reparse_and_special_entries_are_conflicts(s, monkeypatch):
    target = s.plan.target_directory.absolute_path
    os.mkdir(target)
    for overrides in ({"st_file_attributes": stat.FILE_ATTRIBUTE_REPARSE_POINT}, {"st_mode": stat.S_IFIFO | 0o644},
                      {"st_ino": 0}):
        inject(monkeypatch, lstat=lstat_rewriting(target, **overrides))
        _assert_failure(create_target_directory(s.plan, _lib(s)), ExecutionStep.CREATE_DIRECTORY, F.TARGET_CONFLICT)
        monkeypatch.undo()


def test_entry_planted_between_probe_and_mkdir_is_never_replaced(s, monkeypatch):
    target = s.plan.target_directory.absolute_path

    def plant(path):
        os.mkdir(path)
        with open(os.path.join(path, "theirs.txt"), "wb") as handle:
            handle.write(b"theirs")

    MkdirCounter(monkeypatch, before=plant)
    _assert_failure(create_target_directory(s.plan, _lib(s)), ExecutionStep.CREATE_DIRECTORY, F.TARGET_CONFLICT)
    assert os.listdir(target) == ["theirs.txt"]


def test_library_root_deleted_after_preflight(s, monkeypatch):
    identity = _lib(s)
    os.rmdir(s.library_root)
    counter = MkdirCounter(monkeypatch)
    _assert_failure(create_target_directory(s.plan, identity), ExecutionStep.CREATE_DIRECTORY,
                    F.LIBRARY_ROOT_CHANGED)
    assert counter.calls == [] and not os.path.exists(s.library_root)  # never (re)created


def test_library_root_replaced_by_another_directory_or_a_junction(s, monkeypatch):
    identity = _lib(s)
    os.rename(s.library_root, str(s.root / "old-library"))
    os.mkdir(s.library_root)
    _assert_failure(create_target_directory(s.plan, identity), ExecutionStep.CREATE_DIRECTORY,
                    F.LIBRARY_ROOT_CHANGED)
    os.rmdir(s.library_root)
    try_junction(s.root / "library", s.root / "old-library")
    counter = MkdirCounter(monkeypatch)
    _assert_failure(create_target_directory(s.plan, identity), ExecutionStep.CREATE_DIRECTORY,
                    F.LIBRARY_ROOT_CHANGED)
    assert counter.calls == [] and os.listdir(s.root / "old-library") == []


def test_library_root_missing_never_reaches_mkdir(tmp_path, monkeypatch):
    s = scene(tmp_path, make_library=False)
    fake = EntryIdentity(1, 2, EntryType.DIRECTORY, None, None)
    counter = MkdirCounter(monkeypatch)
    _assert_failure(create_target_directory(s.plan, fake), ExecutionStep.CREATE_DIRECTORY, F.LIBRARY_ROOT_CHANGED)
    assert counter.calls == [] and not os.path.exists(s.library_root)


def _replace_with_file(path):
    os.rmdir(path)
    with open(path, "wb") as handle:
        handle.write(b"swapped")


def test_target_replaced_between_mkdir_and_snapshot(s, monkeypatch):
    MkdirCounter(monkeypatch, after=_replace_with_file)
    _assert_failure(create_target_directory(s.plan, _lib(s)), ExecutionStep.CREATE_DIRECTORY,
                    F.TARGET_DIRECTORY_CHANGED, stage=TransferStage.PUBLISH_VERIFY)
    with open(s.plan.target_directory.absolute_path, "rb") as handle:
        assert handle.read() == b"swapped"  # nothing deleted / no rollback


def test_target_replaced_by_junction_between_mkdir_and_snapshot(s, monkeypatch):
    (s.root / "elsewhere").mkdir()

    def swap(path):
        os.rmdir(path)
        try_junction(s.root / "library" / NUMBER, s.root / "elsewhere")

    MkdirCounter(monkeypatch, after=swap)
    _assert_failure(create_target_directory(s.plan, _lib(s)), ExecutionStep.CREATE_DIRECTORY,
                    F.TARGET_DIRECTORY_CHANGED, stage=TransferStage.PUBLISH_VERIFY)


def test_post_mkdir_identity_unavailable_is_target_directory_changed(s, monkeypatch):
    target = s.plan.target_directory.absolute_path
    calls = []
    real_lstat = _fs._FS.lstat

    def lstat(path):
        st = real_lstat(path)
        if path == target:
            calls.append(path)
        return with_stat_fields(st, st_ino=0) if path == target and os.path.isdir(target) else st

    inject(monkeypatch, lstat=lstat)
    _assert_failure(create_target_directory(s.plan, _lib(s)), ExecutionStep.CREATE_DIRECTORY,
                    F.TARGET_DIRECTORY_CHANGED, stage=TransferStage.PUBLISH_VERIFY)


@pytest.mark.parametrize(("exc", "kind", "code"), [
    (PermissionError(errno.EACCES, "denied"), F.DIRECTORY_CREATE_FAILED, errno.EACCES),
    (OSError(errno.ENOSPC, "full"), F.DIRECTORY_CREATE_FAILED, errno.ENOSPC),
    (FileExistsError(errno.EEXIST, "exists"), F.TARGET_CONFLICT, None),
    (FileNotFoundError(errno.ENOENT, "gone"), F.LIBRARY_ROOT_CHANGED, None),
    (NotADirectoryError(errno.ENOTDIR, "not dir"), F.LIBRARY_ROOT_CHANGED, None),
])
def test_mkdir_error_mapping(s, monkeypatch, exc, kind, code):
    def failing(path, mode):
        raise exc

    inject(monkeypatch, mkdir=failing)
    failure = _assert_failure(create_target_directory(s.plan, _lib(s)), ExecutionStep.CREATE_DIRECTORY, kind,
                              errno_=code)
    assert str(s.root) not in repr(failure) and "denied" not in repr(failure)
    assert not os.path.exists(s.plan.target_directory.absolute_path)


def test_target_probe_failure_is_directory_create_failed(s, monkeypatch):
    target = s.plan.target_directory.absolute_path
    real = _fs._FS.lstat

    def lstat(path):
        if path == target:
            raise PermissionError(errno.EACCES, "denied")
        return real(path)

    inject(monkeypatch, lstat=lstat)
    counter = MkdirCounter(monkeypatch)
    _assert_failure(create_target_directory(s.plan, _lib(s)), ExecutionStep.CREATE_DIRECTORY,
                    F.DIRECTORY_CREATE_FAILED, errno_=errno.EACCES)
    assert counter.calls == []


def test_eight_threads_one_target_exactly_one_winner(tmp_path):
    for round_ in range(5):
        (tmp_path / f"round{round_}").mkdir()
        s = scene(tmp_path / f"round{round_}")
        library = _lib(s)
        barrier = threading.Barrier(8)
        results = []
        lock = threading.Lock()

        def worker():
            barrier.wait()
            result = create_target_directory(s.plan, library)
            with lock:
                results.append(result)

        threads = [threading.Thread(target=worker) for _ in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        winners = [r for r in results if r[1] is None]
        assert len(winners) == 1 and winners[0][0] == _identity(s.plan.target_directory.absolute_path)
        assert all(r[1].kind is F.TARGET_CONFLICT for r in results if r[1] is not None)


def test_input_identity_must_be_an_exact_directory_identity(s):
    with pytest.raises(ExecutionInputError):
        create_target_directory(s.plan, EntryIdentity(1, 2, EntryType.FILE, 1, 1))
    with pytest.raises(ExecutionInputError):
        create_extrafanart_directory(s.plan, "identity")


# --------------------------------------------------------------------------- extrafanart directory


@pytest.fixture
def owned(s):
    identity, failure = create_target_directory(s.plan, _lib(s))
    assert failure is None
    return identity


def test_extrafanart_exclusive_create_success(s, owned, monkeypatch):
    counter = MkdirCounter(monkeypatch)
    identity, failure = create_extrafanart_directory(s.plan, owned)
    path = s.plan.extrafanart_directory.absolute_path
    assert failure is None and identity == _identity(path) and counter.calls == [path]


def test_extrafanart_existing_entries_are_conflicts(s, owned, monkeypatch):
    path = s.plan.extrafanart_directory.absolute_path
    for make in (lambda: os.mkdir(path), lambda: open(path, "wb").close()):
        make()
        before = fingerprint_tree(s.root)
        counter = MkdirCounter(monkeypatch)
        _assert_failure(create_extrafanart_directory(s.plan, owned), ExecutionStep.ENSURE_EXTRAFANART_DIRECTORY,
                        F.TARGET_CONFLICT)
        assert counter.calls == [] and fingerprint_tree(s.root) == before
        monkeypatch.undo()
        if os.path.isdir(path):
            os.rmdir(path)
        else:
            os.remove(path)


def test_extrafanart_symlink_and_junction_are_conflicts(s, owned, monkeypatch):
    (s.root / "elsewhere").mkdir()
    link = s.root / "library" / NUMBER / "extrafanart"
    try_junction(link, s.root / "elsewhere")
    _assert_failure(create_extrafanart_directory(s.plan, owned), ExecutionStep.ENSURE_EXTRAFANART_DIRECTORY,
                    F.TARGET_CONFLICT)
    assert os.listdir(s.root / "elsewhere") == []


def test_extrafanart_dangling_symlink_is_a_conflict(s, owned):
    try_symlink(s.root / "library" / NUMBER / "extrafanart", s.root / "missing", target_is_directory=True)
    _assert_failure(create_extrafanart_directory(s.plan, owned), ExecutionStep.ENSURE_EXTRAFANART_DIRECTORY,
                    F.TARGET_CONFLICT)


def test_extrafanart_requires_the_owned_target_directory(s, owned, monkeypatch):
    target = s.plan.target_directory.absolute_path
    os.rename(target, str(s.root / "moved"))
    os.mkdir(target)  # same path, different directory
    counter = MkdirCounter(monkeypatch)
    _assert_failure(create_extrafanart_directory(s.plan, owned), ExecutionStep.ENSURE_EXTRAFANART_DIRECTORY,
                    F.TARGET_DIRECTORY_CHANGED)
    assert counter.calls == [] and os.listdir(target) == []


def test_extrafanart_target_directory_replaced_by_junction(s, owned):
    target = s.plan.target_directory.absolute_path
    os.rename(target, str(s.root / "moved"))
    try_junction(s.root / "library" / NUMBER, s.root / "moved")
    _assert_failure(create_extrafanart_directory(s.plan, owned), ExecutionStep.ENSURE_EXTRAFANART_DIRECTORY,
                    F.TARGET_DIRECTORY_CHANGED)
    assert os.listdir(s.root / "moved") == []


def test_extrafanart_replaced_between_mkdir_and_snapshot(s, owned, monkeypatch):
    MkdirCounter(monkeypatch, after=_replace_with_file)
    _assert_failure(create_extrafanart_directory(s.plan, owned), ExecutionStep.ENSURE_EXTRAFANART_DIRECTORY,
                    F.TARGET_DIRECTORY_CHANGED, stage=TransferStage.PUBLISH_VERIFY)


@pytest.mark.parametrize(("exc", "kind", "code"), [
    (PermissionError(errno.EACCES, "denied"), F.DIRECTORY_CREATE_FAILED, errno.EACCES),
    (FileExistsError(errno.EEXIST, "exists"), F.TARGET_CONFLICT, None),
    (FileNotFoundError(errno.ENOENT, "gone"), F.TARGET_DIRECTORY_CHANGED, None),
])
def test_extrafanart_mkdir_error_mapping(s, owned, monkeypatch, exc, kind, code):
    def failing(path, mode):
        raise exc

    inject(monkeypatch, mkdir=failing)
    _assert_failure(create_extrafanart_directory(s.plan, owned), ExecutionStep.ENSURE_EXTRAFANART_DIRECTORY, kind,
                    errno_=code)


def test_extrafanart_eight_threads_exactly_one_winner(s, owned):
    barrier = threading.Barrier(8)
    results = []
    lock = threading.Lock()

    def worker():
        barrier.wait()
        result = create_extrafanart_directory(s.plan, owned)
        with lock:
            results.append(result)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert sum(1 for r in results if r[1] is None) == 1
    assert all(r[1].kind is F.TARGET_CONFLICT for r in results if r[1] is not None)


# --------------------------------------------------------------------------- revalidate / inventory


def test_revalidate_directory(s, owned, monkeypatch):
    target = s.plan.target_directory.absolute_path
    trap = trap_mutations(monkeypatch)
    assert revalidate_directory(target, owned)
    monkeypatch.undo()
    assert trap.calls == []
    inject(monkeypatch, lstat=lstat_rewriting(target, st_ino=0))
    assert not revalidate_directory(target, owned)
    monkeypatch.undo()
    inject(monkeypatch, lstat=lstat_rewriting(target, st_file_attributes=stat.FILE_ATTRIBUTE_REPARSE_POINT))
    assert not revalidate_directory(target, owned)
    monkeypatch.undo()
    assert not revalidate_directory(str(s.root / "missing"), owned)
    assert not revalidate_directory(s.source_path, owned)  # a file
    os.rename(target, str(s.root / "moved"))
    os.mkdir(target)
    assert not revalidate_directory(target, owned)  # replacement


def test_revalidate_directory_rejects_a_junction(s, owned):
    target = s.plan.target_directory.absolute_path
    os.rename(target, str(s.root / "moved"))
    try_junction(s.root / "library" / NUMBER, s.root / "moved")
    assert not revalidate_directory(target, owned)


def test_child_name_and_inventory(tmp_path):
    directory = str(tmp_path)
    assert child_name(directory, os.path.join(directory, "a.jpg")) == "a.jpg"
    assert child_name(directory, os.path.join(directory, "sub", "a.jpg")) is None
    (tmp_path / "a.jpg").write_bytes(b"")
    (tmp_path / "b.nfo").write_bytes(b"")
    assert compare_inventory(directory, ("a.jpg", "b.nfo")) == (False, frozenset())
    assert compare_inventory(directory, ("a.jpg",)) == (True, frozenset())
    assert compare_inventory(directory, ("a.jpg", "b.nfo", "c.jpg")) == (False, frozenset({"c.jpg"}))
    assert type(compare_inventory(str(tmp_path / "missing"), ())) is FileNotFoundError
    case_variant = compare_inventory(directory, ("A.JPG", "b.nfo"))
    assert case_variant == ((False, frozenset()) if os.name == "nt" else (True, frozenset({"A.JPG"})))
