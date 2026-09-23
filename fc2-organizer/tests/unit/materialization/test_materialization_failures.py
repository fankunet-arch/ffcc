"""P4-C6 substep 1: failure injection, exact temp ownership, cleanup, fatal propagation."""

from __future__ import annotations

import errno
import os

import pytest

from fc2_organizer.materialization import (
    ArtifactCleanupError,
    ArtifactPublishError,
    ArtifactWriteError,
    ArtifactWriteStage,
    TargetExistsError,
    TemporaryCreateError,
    materialize_atomic_bytes,
)
from fc2_organizer.materialization import atomic

from ._helpers import (
    STRATEGIES,
    TEMP_PREFIX,
    TEMP_SUFFIX,
    TempRecorder,
    apply_strategy,
    entries,
    failing,
    inject,
    temp_entries,
    use_hardlink_strategy,
)

KNOWN_TOKEN = "0123456789abcdef" * 2
PAYLOAD = b"PAYLOAD-" * 64


@pytest.fixture(params=STRATEGIES)
def strategy(request, monkeypatch):
    apply_strategy(monkeypatch, request.param)
    return request.param


def _plant_unrelated(directory):
    planted = {
        f"{TEMP_PREFIX}{'f' * 32}{TEMP_SUFFIX}": b"someone else's temp",
        "download.tmp": b"other tmp",
        "poster.jpg.part": b"other part",
    }
    for name, data in planted.items():
        (directory / name).write_bytes(data)
    return planted


def _assert_planted_intact(directory, planted):
    for name, data in planted.items():
        assert (directory / name).read_bytes() == data, name


def _close_then(exc):
    """A close op that really closes the fd (so Windows can delete the temp) and then fails."""

    def op(fd):
        os.close(fd)
        raise exc

    return op


def _write_n_times_then(n, exc):
    state = {"calls": 0}

    def op(fd, data):
        state["calls"] += 1
        if state["calls"] > n:
            raise exc
        return os.write(fd, data)

    return op


# --------------------------------------------------------------------------- write / flush / close


def test_write_failure_midway_leaves_no_target_and_removes_owned_temp(tmp_path, monkeypatch, strategy):
    planted = _plant_unrelated(tmp_path)
    recorder = TempRecorder(monkeypatch)
    monkeypatch.setattr(atomic, "_WRITE_CHUNK", 16)
    inject(monkeypatch, write=_write_n_times_then(3, OSError(errno.ENOSPC, "No space left", "x")))
    target = tmp_path / "poster.jpg"

    with pytest.raises(ArtifactWriteError) as info:
        materialize_atomic_bytes(str(target), PAYLOAD)

    assert info.value.stage is ArtifactWriteStage.WRITE and info.value.errno == errno.ENOSPC
    assert not target.exists()
    assert len(recorder.created) == 1 and not os.path.exists(recorder.created[0])
    assert entries(tmp_path) == set(planted)
    _assert_planted_intact(tmp_path, planted)


def test_short_writes_are_completed(tmp_path, monkeypatch):
    inject(monkeypatch, write=lambda fd, data: os.write(fd, data[:3]))
    target = tmp_path / "a.bin"
    materialize_atomic_bytes(str(target), PAYLOAD)
    assert target.read_bytes() == PAYLOAD


def test_zero_length_write_is_a_typed_write_failure(tmp_path, monkeypatch):
    inject(monkeypatch, write=lambda fd, data: 0)
    with pytest.raises(ArtifactWriteError) as info:
        materialize_atomic_bytes(str(tmp_path / "a.bin"), b"abc")
    assert info.value.stage is ArtifactWriteStage.WRITE and info.value.errno == errno.EIO
    assert entries(tmp_path) == set()


def test_flush_failure_leaves_no_target_and_removes_owned_temp(tmp_path, monkeypatch, strategy):
    planted = _plant_unrelated(tmp_path)
    inject(monkeypatch, fsync=failing(OSError(errno.EIO, "I/O error")))
    target = tmp_path / "fanart.jpg"
    with pytest.raises(ArtifactWriteError) as info:
        materialize_atomic_bytes(str(target), PAYLOAD)
    assert info.value.stage is ArtifactWriteStage.FLUSH and info.value.errno == errno.EIO
    assert not target.exists()
    assert entries(tmp_path) == set(planted)


def test_close_failure_leaves_no_target_and_removes_owned_temp(tmp_path, monkeypatch, strategy):
    planted = _plant_unrelated(tmp_path)
    inject(monkeypatch, close=_close_then(OSError(errno.EIO, "close failed")))
    target = tmp_path / "thumb.jpg"
    with pytest.raises(ArtifactWriteError) as info:
        materialize_atomic_bytes(str(target), PAYLOAD)
    assert info.value.stage is ArtifactWriteStage.CLOSE
    assert not target.exists()
    assert entries(tmp_path) == set(planted)


def test_fd_is_closed_exactly_once_on_the_failure_path(tmp_path, monkeypatch):
    closed = []
    inject(monkeypatch, fsync=failing(OSError(errno.EIO, "x")),
           close=lambda fd: (closed.append(fd), os.close(fd))[1])
    with pytest.raises(ArtifactWriteError):
        materialize_atomic_bytes(str(tmp_path / "a.bin"), b"x")
    assert len(closed) == 1


# --------------------------------------------------------------------------- publish


def test_publish_failure_leaves_no_target_and_removes_owned_temp(tmp_path, monkeypatch, strategy):
    planted = _plant_unrelated(tmp_path)
    recorder = TempRecorder(monkeypatch)
    inject(monkeypatch, publish=failing(PermissionError(errno.EACCES, "denied", "tmp", None, "dst")))
    target = tmp_path / "poster.jpg"
    with pytest.raises(ArtifactPublishError) as info:
        materialize_atomic_bytes(str(target), PAYLOAD)
    assert info.value.errno == errno.EACCES
    assert not target.exists()
    assert not os.path.exists(recorder.created[0])
    assert entries(tmp_path) == set(planted)


def test_target_planted_between_precheck_and_publish_is_never_replaced(tmp_path, monkeypatch, strategy):
    """TOCTOU: the pre-check passes, then a competitor creates the target. The publish
    primitive itself must refuse -- no check-then-replace window exists."""
    target = tmp_path / "poster.jpg"
    real_publish = atomic._FS.publish

    def plant_then_publish(src, dst):
        with open(dst, "xb") as fh:
            fh.write(b"COMPETITOR")
        real_publish(src, dst)

    inject(monkeypatch, publish=plant_then_publish)
    with pytest.raises(TargetExistsError):
        materialize_atomic_bytes(str(target), b"MINE")
    assert target.read_bytes() == b"COMPETITOR"
    assert entries(tmp_path) == {"poster.jpg"}


def test_directory_planted_between_precheck_and_publish_is_never_replaced(tmp_path, monkeypatch, strategy):
    target = tmp_path / "poster.jpg"
    real_publish = atomic._FS.publish

    def plant_then_publish(src, dst):
        os.mkdir(dst)
        real_publish(src, dst)

    inject(monkeypatch, publish=plant_then_publish)
    with pytest.raises(TargetExistsError):
        materialize_atomic_bytes(str(target), b"MINE")
    assert target.is_dir() and os.listdir(target) == []
    assert entries(tmp_path) == {"poster.jpg"}


def test_symlink_planted_between_precheck_and_publish_is_never_followed(tmp_path, monkeypatch, strategy):
    victim = tmp_path / "victim.bin"
    victim.write_bytes(b"VICTIM")
    lib = tmp_path / "lib"
    lib.mkdir()
    target = lib / "poster.jpg"
    real_publish = atomic._FS.publish

    def plant_then_publish(src, dst):
        try:
            os.symlink(victim, dst)
        except OSError:
            pytest.skip("symlink creation not permitted on this host")
        real_publish(src, dst)

    inject(monkeypatch, publish=plant_then_publish)
    with pytest.raises(TargetExistsError):
        materialize_atomic_bytes(str(target), b"ATTACK")
    assert os.path.islink(target) and victim.read_bytes() == b"VICTIM"
    assert entries(lib) == {"poster.jpg"}


# --------------------------------------------------------------------------- cleanup failures


def test_cleanup_failure_after_write_failure_is_typed_and_keeps_primary(tmp_path, monkeypatch):
    inject(monkeypatch, token=lambda n: KNOWN_TOKEN, fsync=failing(OSError(errno.EIO, "x")),
           unlink=failing(PermissionError(errno.EACCES, "denied")))
    target = tmp_path / "a.jpg"
    with pytest.raises(ArtifactCleanupError) as info:
        materialize_atomic_bytes(str(target), b"x")
    err = info.value
    assert err.target_published is False and err.errno == errno.EACCES
    assert type(err.primary) is ArtifactWriteError and err.primary.stage is ArtifactWriteStage.FLUSH
    assert err.__cause__ is err.primary
    assert not target.exists()
    # the leaked temp is exactly our own -- nothing else was created or deleted
    assert entries(tmp_path) == {f"{TEMP_PREFIX}{KNOWN_TOKEN}{TEMP_SUFFIX}"}


def test_cleanup_failure_after_publish_conflict_keeps_target_exists_as_primary(tmp_path, monkeypatch):
    target = tmp_path / "a.jpg"
    real_publish = atomic._FS.publish

    def plant_then_publish(src, dst):
        with open(dst, "xb") as fh:
            fh.write(b"WINNER")
        real_publish(src, dst)

    inject(monkeypatch, publish=plant_then_publish, unlink=failing(PermissionError(errno.EACCES, "denied")))
    with pytest.raises(ArtifactCleanupError) as info:
        materialize_atomic_bytes(str(target), b"LOSER")
    assert type(info.value.primary) is TargetExistsError and info.value.target_published is False
    assert target.read_bytes() == b"WINNER"


def test_hardlink_strategy_temp_unlink_failure_after_publish_reports_published(tmp_path, monkeypatch):
    use_hardlink_strategy(monkeypatch)
    inject(monkeypatch, token=lambda n: KNOWN_TOKEN, unlink=failing(PermissionError(errno.EACCES, "denied")))
    target = tmp_path / "a.jpg"
    with pytest.raises(ArtifactCleanupError) as info:
        materialize_atomic_bytes(str(target), PAYLOAD)
    assert info.value.target_published is True and info.value.primary is None
    assert target.read_bytes() == PAYLOAD  # the complete artifact is published and not removed


def test_hardlink_strategy_removes_temp_after_successful_publish(tmp_path, monkeypatch):
    use_hardlink_strategy(monkeypatch)
    recorder = TempRecorder(monkeypatch)
    materialize_atomic_bytes(str(tmp_path / "a.jpg"), b"x")
    assert not os.path.exists(recorder.created[0])
    assert entries(tmp_path) == {"a.jpg"}


def test_temp_already_gone_during_cleanup_is_not_a_cleanup_failure(tmp_path, monkeypatch):
    def fsync_then_vanish(fd):
        raise OSError(errno.EIO, "x")

    real_unlink = atomic._FS.unlink

    def unlink_twice(path):
        real_unlink(path)
        real_unlink(path)  # raises FileNotFoundError

    inject(monkeypatch, fsync=fsync_then_vanish, unlink=unlink_twice)
    with pytest.raises(ArtifactWriteError):
        materialize_atomic_bytes(str(tmp_path / "a.jpg"), b"x")


def test_windows_rename_strategy_never_cleans_after_publish(tmp_path, monkeypatch):
    """After a consuming publish the temp name is no longer ours: never unlinked again."""
    monkeypatch.setattr(atomic, "_PUBLISH_LEAVES_TEMP", False)
    unlinked = []
    inject(monkeypatch, publish=os.rename, unlink=lambda p: unlinked.append(p))
    materialize_atomic_bytes(str(tmp_path / "a.jpg"), b"x")
    assert unlinked == []


# --------------------------------------------------------------------------- exact temp ownership


def test_planted_unrelated_temp_files_survive_every_failure_kind(tmp_path, monkeypatch):
    planted = _plant_unrelated(tmp_path)
    for i, op in enumerate([
        {"write": failing(OSError(errno.EIO, "x"))},
        {"fsync": failing(OSError(errno.EIO, "x"))},
        {"close": _close_then(OSError(errno.EIO, "x"))},
        {"publish": failing(OSError(errno.EIO, "x"))},
    ]):
        with monkeypatch.context() as m:
            inject(m, **op)
            with pytest.raises((ArtifactWriteError, ArtifactPublishError)):
                materialize_atomic_bytes(str(tmp_path / f"t{i}.jpg"), PAYLOAD)
    assert entries(tmp_path) == set(planted)
    _assert_planted_intact(tmp_path, planted)


def test_temp_name_clash_with_foreign_file_retries_and_never_touches_it(tmp_path, monkeypatch):
    foreign = tmp_path / f"{TEMP_PREFIX}{KNOWN_TOKEN}{TEMP_SUFFIX}"
    foreign.write_bytes(b"FOREIGN")
    tokens = iter([KNOWN_TOKEN, "a" * 32])
    inject(monkeypatch, token=lambda n: next(tokens))
    materialize_atomic_bytes(str(tmp_path / "a.jpg"), b"x")
    assert foreign.read_bytes() == b"FOREIGN"
    assert entries(tmp_path) == {"a.jpg", foreign.name}


def test_temp_name_exhaustion_is_typed_and_foreign_file_survives(tmp_path, monkeypatch):
    foreign = tmp_path / f"{TEMP_PREFIX}{KNOWN_TOKEN}{TEMP_SUFFIX}"
    foreign.write_bytes(b"FOREIGN")
    inject(monkeypatch, token=lambda n: KNOWN_TOKEN)
    with pytest.raises(TemporaryCreateError) as info:
        materialize_atomic_bytes(str(tmp_path / "a.jpg"), b"x")
    assert info.value.errno == errno.EEXIST
    assert foreign.read_bytes() == b"FOREIGN" and entries(tmp_path) == {foreign.name}


def test_temp_create_os_failure_is_typed_and_not_retried(tmp_path, monkeypatch):
    calls = []

    def denied(path, flags, mode):
        calls.append(path)
        raise PermissionError(errno.EACCES, "denied", path)

    inject(monkeypatch, open=denied)
    with pytest.raises(TemporaryCreateError) as info:
        materialize_atomic_bytes(str(tmp_path / "a.jpg"), b"x")
    assert info.value.errno == errno.EACCES and len(calls) == 1
    assert entries(tmp_path) == set()


def test_temp_equal_to_target_name_is_skipped(tmp_path, monkeypatch):
    name = f"{TEMP_PREFIX}{KNOWN_TOKEN}{TEMP_SUFFIX}"
    tokens = iter([KNOWN_TOKEN, "b" * 32])
    inject(monkeypatch, token=lambda n: next(tokens))
    materialize_atomic_bytes(str(tmp_path / name), b"x")
    assert (tmp_path / name).read_bytes() == b"x"
    assert entries(tmp_path) == {name}


# --------------------------------------------------------------------------- secret-free errors


@pytest.mark.parametrize("op", ["write", "fsync", "publish", "open"])
def test_errors_never_leak_temp_token_or_os_error_text(tmp_path, monkeypatch, op):
    temp_name = f"{TEMP_PREFIX}{KNOWN_TOKEN}{TEMP_SUFFIX}"
    exc = OSError(errno.EIO, "leaky strerror", str(tmp_path / temp_name))
    inject(monkeypatch, token=lambda n: KNOWN_TOKEN, **{op: failing(exc)})
    with pytest.raises(Exception) as info:
        materialize_atomic_bytes(str(tmp_path / "secret-title.jpg"), b"x")
    err = info.value
    for text in (str(err), repr(err)):
        assert KNOWN_TOKEN not in text and "leaky" not in text and "secret-title" not in text
    assert err.__cause__ is None and err.__context__ is None  # never chained to the OSError


# --------------------------------------------------------------------------- fatal / cancellation


class _Custom(BaseException):
    pass


FATALS = [KeyboardInterrupt, SystemExit, GeneratorExit, _Custom]


@pytest.mark.parametrize("fatal_type", FATALS, ids=lambda t: t.__name__)
@pytest.mark.parametrize("op", ["write", "fsync", "publish"])
def test_fatal_propagates_unchanged_and_owned_temp_is_cleaned(tmp_path, monkeypatch, strategy, fatal_type, op):
    planted = _plant_unrelated(tmp_path)
    fatal = fatal_type()
    inject(monkeypatch, **{op: failing(fatal)})
    with pytest.raises(fatal_type) as info:
        materialize_atomic_bytes(str(tmp_path / "a.jpg"), PAYLOAD)
    assert info.value is fatal
    assert entries(tmp_path) == set(planted)


@pytest.mark.parametrize("fatal_type", FATALS, ids=lambda t: t.__name__)
def test_cleanup_failure_never_masks_a_fatal(tmp_path, monkeypatch, fatal_type):
    fatal = fatal_type()
    inject(monkeypatch, fsync=failing(fatal), unlink=failing(PermissionError(errno.EACCES, "denied")))
    with pytest.raises(fatal_type) as info:
        materialize_atomic_bytes(str(tmp_path / "a.jpg"), b"x")
    assert info.value is fatal


def test_foreign_ordinary_exception_propagates_unchanged_with_cleanup(tmp_path, monkeypatch):
    boom = RuntimeError("not ours")
    inject(monkeypatch, fsync=failing(boom))
    with pytest.raises(RuntimeError) as info:
        materialize_atomic_bytes(str(tmp_path / "a.jpg"), b"x")
    assert info.value is boom and entries(tmp_path) == set()


def test_fatal_during_cleanup_itself_propagates(tmp_path, monkeypatch):
    inject(monkeypatch, fsync=failing(OSError(errno.EIO, "x")), unlink=failing(KeyboardInterrupt()))
    with pytest.raises(KeyboardInterrupt):
        materialize_atomic_bytes(str(tmp_path / "a.jpg"), b"x")


def test_fatal_after_hardlink_publish_keeps_published_target(tmp_path, monkeypatch):
    use_hardlink_strategy(monkeypatch)
    real_link = os.link

    def link_then_interrupt(src, dst):
        real_link(src, dst)
        raise KeyboardInterrupt

    inject(monkeypatch, publish=link_then_interrupt)
    target = tmp_path / "a.jpg"
    with pytest.raises(KeyboardInterrupt):
        materialize_atomic_bytes(str(target), PAYLOAD)
    assert target.read_bytes() == PAYLOAD  # the target is never deleted by cleanup
    assert temp_entries(tmp_path) == set()
