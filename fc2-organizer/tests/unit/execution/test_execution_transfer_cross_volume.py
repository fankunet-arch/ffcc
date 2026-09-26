"""P4-C7 S3: cross-volume media copy (contract sections 17, 19, 20; construction plan S3).

CROSS_VOLUME is forced through the ``_FS.device_of`` seam (files report another device than directories, so
the read-only preflight predicts CROSS_VOLUME on one disk) -- this is mocked, never native evidence. A real
second volume is exercised only when ``FC2_EXECUTION_CROSS_VOLUME_ROOT`` names a directory on another volume;
otherwise that test is SKIPPED (recorded as NOT EXECUTED).
"""

from __future__ import annotations

import hashlib
import os
import secrets
import shutil
import tracemalloc

import pytest

from fc2_organizer.execution import EffectKind, PathRole, TransferMode, preflight_execution
from fc2_organizer.execution import _fs
from fc2_organizer.execution.directories import create_target_directory
from fc2_organizer.execution.transfer import ResumePhase, transfer_media

from ._builders import make_manifest, make_plan, scene
from ._helpers import (
    MIB,
    SeamLog,
    FakeDirectoryFsync,
    assert_planted_unchanged,
    assert_source_not_lost,
    force_cross_volume_devices,
    inject,
    sha256_of_file,
    temp_names,
    transfer_scene,
    use_strategy,
    write_generated_media,
)

CROSS = TransferMode.CROSS_VOLUME
FULL = ResumePhase.FULL
SIZES = [0, 1, MIB - 1, MIB, MIB + 1, 3 * MIB + 17]


def _content(size: int) -> bytes:
    block = hashlib.sha256(b"cross-volume").digest()
    return (block * (size // len(block) + 1))[:size]


def _run(ts):
    return transfer_media(ts.plan, ts.source_identity, ts.target_identity, CROSS, resume_phase=FULL)


def _assert_copied(ts, outcome, expected_sha256):
    assert outcome.failure is None and outcome.transfer_mode is CROSS
    assert [e.kind for e in outcome.effects] == [EffectKind.MEDIA_PUBLISHED, EffectKind.SOURCE_REMOVED]
    media = outcome.effects[0]
    assert media.role is PathRole.TARGET_MEDIA and media.path == ts.final and media.size == ts.size
    assert media.sha256 == expected_sha256 == outcome.media_sha256 and outcome.media_size == ts.size
    assert media.identity == _fs.snapshot(ts.final)
    assert media.identity.inode != ts.source_identity.inode  # a new file, not a move
    assert outcome.leftover_temporaries == ()
    assert not os.path.lexists(ts.source)
    assert temp_names(ts.target_directory) == []
    assert sha256_of_file(ts.final) == expected_sha256
    assert_planted_unchanged(ts)
    assert_source_not_lost(ts.source, ts.final, expected_sha256)


def test_device_seam_makes_preflight_predict_cross_volume(tmp_path, monkeypatch):
    force_cross_volume_devices(monkeypatch)
    s = scene(tmp_path)
    assert preflight_execution(s.plan, s.artifacts).transfer_mode is CROSS


@pytest.mark.parametrize("strategy", ["rename", "link"])
@pytest.mark.parametrize("size", SIZES)
def test_exact_bytes_and_sha256_for_boundary_sizes(tmp_path, monkeypatch, size, strategy):
    use_strategy(monkeypatch, strategy)
    force_cross_volume_devices(monkeypatch)
    content = _content(size)
    ts = transfer_scene(tmp_path, content=content)
    library = _fs.snapshot(ts.plan.library_root)
    assert ts.source_identity.device != library.device  # the seam-predicted mode is CROSS_VOLUME
    log = SeamLog(monkeypatch)
    outcome = _run(ts)
    calls = list(log.calls)
    _assert_copied(ts, outcome, hashlib.sha256(content).hexdigest())
    with open(ts.final, "rb") as handle:
        assert handle.read() == content
    # Never a rename / link of the source itself; the source is unlinked last, after publish + verification.
    mutations = [c for c in calls if c[0] in ("rename", "link", "unlink")]
    temp = mutations[0][1]
    assert os.path.dirname(temp) == ts.target_directory and os.path.basename(temp).startswith(".fc2tmp-")
    if strategy == "rename":
        assert mutations == [("rename", temp), ("unlink", ts.source)]
    else:
        assert mutations == [("link", temp), ("unlink", temp), ("unlink", ts.source)]
    assert calls[-1] == ("unlink", ts.source)
    published = max(i for i, c in enumerate(calls) if c[0] in ("rename", "link"))
    verified = next(i for i in range(published, len(calls)) if calls[i] == ("lstat", ts.final))
    revalidated = next(i for i in range(verified, len(calls)) if calls[i] == ("lstat", ts.source))
    assert published < verified < revalidated < len(calls) - 1


def test_exact_ten_step_order_with_posix_publish_and_directory_fsync(tmp_path, monkeypatch):
    use_strategy(monkeypatch, "link")
    ts = transfer_scene(tmp_path, content=_content(2 * MIB + 5))
    FakeDirectoryFsync(monkeypatch, ts.target_directory)
    log = SeamLog(monkeypatch)
    outcome = _run(ts)
    calls = list(log.calls)
    assert outcome.failure is None
    src_open = log.index("open", ts.source)
    temp_open = next(i for i in range(src_open + 1, len(calls)) if calls[i][0] == "open")
    temp = calls[temp_open][1]
    order = [
        log.index("open", ts.source),                      # 1 open source (read-only)
        log.index("fstat", None, src_open),                #   fstat(source fd)
        temp_open,                                         # 2 exclusive temp
        log.index("read", None, temp_open),                # 3-4 streamed copy
        log.index("write", None, temp_open),
        log.index("fsync", None, temp_open),               # 5 fsync / fstat / close temp
    ]
    fsync_temp = order[-1]
    order += [
        log.index("fstat", None, fsync_temp),
        log.index("close", None, fsync_temp),
    ]
    source_revalidate = log.index("fstat", None, order[-1])  # 6 source fd revalidated, then closed
    order += [source_revalidate, log.index("close", None, source_revalidate),
              log.index("link", temp),                     # 7 publish (no replace) + temp unlink + verify
              log.index("unlink", temp),
              log.index("lstat", ts.final, log.index("unlink", temp)),
              log.index("open", ts.target_directory),      # 8 directory fsync
              log.index("fsync", FakeDirectoryFsync.FD),
              log.index("lstat", ts.source, log.index("fsync", FakeDirectoryFsync.FD)),  # 9 source path
              log.index("unlink", ts.source)]              # 10 unlink source
    assert order == sorted(order), order
    assert order[-1] == len(calls) - 1


def test_64_mib_generated_media_is_streamed_in_blocks_of_at_most_one_mib(tmp_path, monkeypatch):
    size = 64 * MIB + 3
    ts = transfer_scene(tmp_path, size=size)
    read_sizes, write_sizes = [], []
    real_read, real_write = _fs._FS.read, _fs._FS.write

    def read(fd, n):
        read_sizes.append(n)
        return real_read(fd, n)

    def write(fd, data):
        write_sizes.append(len(data))
        return real_write(fd, data)

    inject(monkeypatch, read=read, write=write)
    tracemalloc.start()
    try:
        outcome = _run(ts)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert max(read_sizes) <= MIB and max(write_sizes) <= MIB
    assert len(read_sizes) >= 65 and sum(write_sizes) == size
    assert peak < 8 * MIB, peak  # memory does not grow with the media size
    _assert_copied(ts, outcome, ts.sha256)


@pytest.mark.parametrize("strategy", ["rename", "link"])
def test_unicode_and_zero_byte_cross_volume(tmp_path, monkeypatch, strategy):
    use_strategy(monkeypatch, strategy)
    ts = transfer_scene(tmp_path, content=b"", source_name="下载-かな-😀-é.MKV", library_name="库-ライブラリ")
    outcome = _run(ts)
    _assert_copied(ts, outcome, hashlib.sha256(b"").hexdigest())


def test_temporary_mode_and_flags_never_truncate(tmp_path, monkeypatch):
    ts = transfer_scene(tmp_path, content=_content(10))
    seen = []
    real = _fs._FS.open

    def open_(path, flags, *rest):
        seen.append((path, flags, rest))
        return real(path, flags, *rest)

    inject(monkeypatch, open=open_)
    _assert_copied(ts, _run(ts), hashlib.sha256(_content(10)).hexdigest())
    (source_path, source_flags, source_rest), (temp_path, temp_flags, temp_rest) = seen
    assert source_path == ts.source and source_rest == ()
    assert not source_flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND)
    assert temp_flags & os.O_CREAT and temp_flags & os.O_EXCL and temp_flags & os.O_WRONLY
    assert not temp_flags & os.O_TRUNC and temp_rest == (0o666,)
    name = os.path.basename(temp_path)
    assert len(name) == len(".fc2tmp-") + 32 + len(".part") and name[8:40] == name[8:40].lower()


# --------------------------------------------------------------------------- native cross-volume

_NATIVE_ROOT = os.environ.get("FC2_EXECUTION_CROSS_VOLUME_ROOT")


@pytest.mark.skipif(not _NATIVE_ROOT, reason="native cross-volume: NOT EXECUTED "
                                             "(FC2_EXECUTION_CROSS_VOLUME_ROOT is not set)")
def test_native_cross_volume_copy(tmp_path):
    own = os.path.join(_NATIVE_ROOT, "fc2-p4c7-s3-" + secrets.token_hex(8))
    os.mkdir(own)
    try:
        source = os.path.join(own, "native-source.mp4")
        digest = write_generated_media(source, 3 * MIB + 17)
        library = tmp_path / "library"
        library.mkdir()
        plan = make_plan(str(library), source, size=3 * MIB + 17)
        preflight = preflight_execution(plan, make_manifest(plan))
        if preflight.transfer_mode is not CROSS:
            pytest.skip("FC2_EXECUTION_CROSS_VOLUME_ROOT is on the same volume as tmp_path: NOT EXECUTED")
        target_identity, failure = create_target_directory(plan, preflight.library_root_identity)
        assert failure is None
        outcome = transfer_media(plan, preflight.source_identity, target_identity, preflight.transfer_mode,
                                 resume_phase=FULL)
        assert outcome.failure is None and outcome.media_sha256 == digest
        assert not os.path.lexists(source)
        assert sha256_of_file(plan.target_media_path.absolute_path) == digest
        assert_source_not_lost(source, plan.target_media_path.absolute_path, digest)
    finally:
        shutil.rmtree(own, ignore_errors=True)
