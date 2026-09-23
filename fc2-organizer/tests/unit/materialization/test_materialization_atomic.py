"""P4-C6 substep 1: happy path, overwrite NEVER, parent/target preconditions, input boundary."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest

from fc2_organizer.materialization import (
    InvalidTargetPathError,
    MaterializationInputError,
    MaterializedArtifact,
    ParentDirectoryError,
    ParentDirectoryMissingError,
    ParentNotDirectoryError,
    ParentRejectionReason,
    TargetExistsError,
    TargetInaccessibleError,
    materialize_atomic_bytes,
)
from fc2_organizer.materialization import atomic

from ._helpers import STRATEGIES, TempRecorder, apply_strategy, entries, failing, inject, try_junction, try_symlink


@pytest.fixture(params=STRATEGIES)
def strategy(request, monkeypatch):
    apply_strategy(monkeypatch, request.param)
    return request.param


# --------------------------------------------------------------------------- happy path


@pytest.mark.parametrize(
    "payload",
    [
        b"<movie/>\n",
        b"",
        bytes(range(256)) * 3,
        b"\x00\xff\xd8\xff\xe0" + os.urandom(4096) + b"\xff\xd9",
        os.urandom(3 * (1 << 20) + 17),  # larger than one write chunk
    ],
    ids=["text", "zero-byte", "all-byte-values", "binary-jpeg-like", "multi-chunk"],
)
def test_writes_exact_bytes_and_reports_size_and_sha256(tmp_path, strategy, payload):
    target = tmp_path / "poster.jpg"
    result = materialize_atomic_bytes(str(target), payload)

    assert type(result) is MaterializedArtifact
    assert result.target_path == str(target)
    assert result.size_bytes == len(payload)
    assert result.sha256 == hashlib.sha256(payload).hexdigest()
    assert target.read_bytes() == payload
    assert hashlib.sha256(target.read_bytes()).hexdigest() == result.sha256
    assert entries(tmp_path) == {"poster.jpg"}  # success leaves no temporary file


def test_result_target_path_is_the_exact_input_object_value(tmp_path):
    target = str(tmp_path / "FC2-1234567.nfo")
    assert materialize_atomic_bytes(target, b"x").target_path == target


def test_temp_is_a_sibling_with_random_name_never_derived_from_target(tmp_path, monkeypatch):
    recorder = TempRecorder(monkeypatch)
    target = tmp_path / "FC2-1234567 Secret Title.nfo"
    materialize_atomic_bytes(str(target), b"x")

    assert len(recorder.created) == 1
    temp = Path(recorder.created[0])
    assert temp.parent == tmp_path  # same directory -> same filesystem, no cross-volume rename
    assert temp.name != target.name
    assert temp.name.startswith(atomic._TEMP_PREFIX) and temp.name.endswith(atomic._TEMP_SUFFIX)
    token = temp.name[len(atomic._TEMP_PREFIX):-len(atomic._TEMP_SUFFIX)]
    assert len(token) == 32 and all(c in "0123456789abcdef" for c in token)
    for word in ("FC2", "1234567", "Secret", "Title", "nfo"):
        assert word not in temp.name
    assert not temp.exists()


def test_temp_names_differ_between_calls(tmp_path, monkeypatch):
    recorder = TempRecorder(monkeypatch)
    for i in range(5):
        materialize_atomic_bytes(str(tmp_path / f"a{i}.jpg"), b"x")
    assert len(set(recorder.created)) == 5


def test_writes_into_an_existing_root_level_style_parent(tmp_path):
    nested = tmp_path / "lib" / "FC2-1"
    nested.mkdir(parents=True)
    materialize_atomic_bytes(str(nested / "thumb.jpg"), b"t")
    assert (nested / "thumb.jpg").read_bytes() == b"t"


# --------------------------------------------------------------------------- overwrite NEVER


def test_existing_file_is_never_overwritten_or_touched(tmp_path, strategy, monkeypatch):
    target = tmp_path / "poster.jpg"
    target.write_bytes(b"ORIGINAL")
    before = os.stat(target)
    recorder = TempRecorder(monkeypatch)

    with pytest.raises(TargetExistsError):
        materialize_atomic_bytes(str(target), b"NEW")

    assert target.read_bytes() == b"ORIGINAL"
    after = os.stat(target)
    assert (after.st_size, after.st_mtime_ns) == (before.st_size, before.st_mtime_ns)
    assert recorder.created == []  # pre-check fails before any temp is created
    assert entries(tmp_path) == {"poster.jpg"}


def test_existing_zero_byte_file_is_not_replaced(tmp_path):
    target = tmp_path / "fanart.jpg"
    target.write_bytes(b"")
    with pytest.raises(TargetExistsError):
        materialize_atomic_bytes(str(target), b"payload")
    assert target.read_bytes() == b""


def test_existing_directory_fails_and_is_untouched(tmp_path, strategy):
    target = tmp_path / "poster.jpg"
    target.mkdir()
    (target / "inner").write_bytes(b"keep")
    with pytest.raises(TargetExistsError):
        materialize_atomic_bytes(str(target), b"x")
    assert target.is_dir() and (target / "inner").read_bytes() == b"keep"
    assert entries(tmp_path) == {"poster.jpg"}


def test_existing_symlink_to_file_elsewhere_is_not_followed_or_modified(tmp_path, strategy):
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    victim = elsewhere / "victim.bin"
    victim.write_bytes(b"VICTIM")
    lib = tmp_path / "lib"
    lib.mkdir()
    link = lib / "poster.jpg"
    try_symlink(link, victim)
    link_target_before = os.readlink(link)

    with pytest.raises(TargetExistsError):
        materialize_atomic_bytes(str(link), b"ATTACK")

    assert os.path.islink(link) and os.readlink(link) == link_target_before
    assert victim.read_bytes() == b"VICTIM"
    assert entries(lib) == {"poster.jpg"}


def test_existing_dangling_symlink_fails_and_its_target_is_not_created(tmp_path):
    lib = tmp_path / "lib"
    lib.mkdir()
    missing = tmp_path / "would-be-created.bin"
    link = lib / "poster.jpg"
    try_symlink(link, missing)
    with pytest.raises(TargetExistsError):
        materialize_atomic_bytes(str(link), b"x")
    assert not missing.exists() and os.path.islink(link)


def test_precheck_uses_lstat_so_a_link_is_never_followed(tmp_path, monkeypatch):
    """Host-independent (no symlink privilege needed): simulate a dangling link -- following
    stat() says "absent", non-following lstat() says "present". The pre-check must trust lstat."""
    target = str(tmp_path / "poster.jpg")
    real_stat = atomic._FS.stat
    fake_link_stat = os.lstat(tmp_path)

    def following_stat(path):
        if path == target:
            raise FileNotFoundError(2, "dangling")
        return real_stat(path)

    recorder = TempRecorder(monkeypatch)
    inject(monkeypatch, stat=following_stat,
           lstat=lambda p: fake_link_stat if p == target else os.lstat(p))
    with pytest.raises(TargetExistsError):
        materialize_atomic_bytes(target, b"x")
    assert recorder.created == [] and entries(tmp_path) == set()


def test_existing_junction_fails_and_its_target_is_untouched(tmp_path):
    real_dir = tmp_path / "real"
    real_dir.mkdir()
    lib = tmp_path / "lib"
    lib.mkdir()
    junction = lib / "extrafanart"
    try_junction(junction, real_dir)
    with pytest.raises(TargetExistsError):
        materialize_atomic_bytes(str(junction), b"x")
    assert os.listdir(real_dir) == []
    assert entries(lib) == {"extrafanart"}


def test_api_has_no_overwrite_or_suffix_knob():
    import inspect

    params = inspect.signature(materialize_atomic_bytes).parameters
    assert list(params) == ["target_path", "content"]
    with pytest.raises(TypeError):
        materialize_atomic_bytes("x", b"x", overwrite=True)  # type: ignore[call-arg]


def test_no_automatic_suffix_is_ever_created(tmp_path):
    target = tmp_path / "poster.jpg"
    target.write_bytes(b"A")
    with pytest.raises(TargetExistsError):
        materialize_atomic_bytes(str(target), b"B")
    assert entries(tmp_path) == {"poster.jpg"}  # no "poster (1).jpg", "poster_copy.jpg", ...


# --------------------------------------------------------------------------- parent precondition


def test_missing_parent_fails_and_is_never_created(tmp_path, monkeypatch):
    recorder = TempRecorder(monkeypatch)
    target = tmp_path / "missing" / "deeper" / "poster.jpg"
    with pytest.raises(ParentDirectoryMissingError) as info:
        materialize_atomic_bytes(str(target), b"x")
    assert info.value.reason is ParentRejectionReason.MISSING
    assert isinstance(info.value, ParentDirectoryError)
    assert entries(tmp_path) == set()
    assert recorder.created == []


def test_parent_that_is_a_file_fails(tmp_path, monkeypatch):
    recorder = TempRecorder(monkeypatch)
    parent = tmp_path / "FC2-1"
    parent.write_bytes(b"i am a file")
    with pytest.raises(ParentNotDirectoryError) as info:
        materialize_atomic_bytes(str(parent / "poster.jpg"), b"x")
    assert info.value.reason is ParentRejectionReason.NOT_A_DIRECTORY
    assert parent.read_bytes() == b"i am a file"
    assert recorder.created == []


def test_path_through_a_file_is_reported_as_missing_parent(tmp_path):
    f = tmp_path / "file"
    f.write_bytes(b"f")
    with pytest.raises(ParentDirectoryMissingError):
        materialize_atomic_bytes(str(f / "sub" / "poster.jpg"), b"x")


def test_inaccessible_parent_is_typed(tmp_path, monkeypatch):
    inject(monkeypatch, stat=failing(PermissionError(13, "denied", "secret-parent")))
    with pytest.raises(ParentDirectoryError) as info:
        materialize_atomic_bytes(str(tmp_path / "a.jpg"), b"x")
    assert type(info.value) is ParentDirectoryError
    assert info.value.reason is ParentRejectionReason.INACCESSIBLE and info.value.errno == 13


def test_unprobeable_target_is_typed_and_nothing_is_written(tmp_path, monkeypatch):
    recorder = TempRecorder(monkeypatch)
    inject(monkeypatch, lstat=failing(PermissionError(13, "denied")))
    with pytest.raises(TargetInaccessibleError) as info:
        materialize_atomic_bytes(str(tmp_path / "a.jpg"), b"x")
    assert info.value.errno == 13
    assert recorder.created == [] and entries(tmp_path) == set()


# --------------------------------------------------------------------------- input boundary


class _HostileBytes(bytes):
    calls = 0

    def __len__(self):
        type(self).calls += 1
        return 0

    def __buffer__(self, flags):
        type(self).calls += 1
        return super().__buffer__(flags)


class _HostileStr(str):
    calls = 0

    def __fspath__(self):
        type(self).calls += 1
        return "/evil"

    def __str__(self):
        type(self).calls += 1
        return "/evil"


class _PathLike:
    calls = 0

    def __fspath__(self):
        type(self).calls += 1
        return "/evil"


def _no_fs(monkeypatch):
    """Any filesystem op at all fails the test."""
    boom = failing(AssertionError("filesystem touched on the rejection path"))
    inject(monkeypatch, lstat=boom, stat=boom, open=boom, write=boom, fsync=boom, close=boom,
           publish=boom, unlink=boom, token=boom)


@pytest.mark.parametrize(
    "content",
    [bytearray(b"x"), memoryview(b"x"), "x", None, 0, [120]],
    ids=["bytearray", "memoryview", "str", "None", "int", "list"],
)
def test_non_exact_bytes_content_is_rejected_before_any_io(tmp_path, monkeypatch, content):
    _no_fs(monkeypatch)
    with pytest.raises(MaterializationInputError):
        materialize_atomic_bytes(str(tmp_path / "a.jpg"), content)


def test_hostile_bytes_subclass_is_rejected_without_running_hooks(tmp_path, monkeypatch):
    _no_fs(monkeypatch)
    hostile = _HostileBytes(b"payload")
    _HostileBytes.calls = 0
    with pytest.raises(MaterializationInputError):
        materialize_atomic_bytes(str(tmp_path / "a.jpg"), hostile)
    assert _HostileBytes.calls == 0


@pytest.mark.parametrize("make_target", [
    lambda p: p,  # pathlib.Path (os.PathLike)
    lambda p: str(p).encode(),
    lambda p: _PathLike(),
    lambda p: None,
], ids=["pathlib", "bytes-path", "pathlike", "None"])
def test_target_must_be_exact_str(tmp_path, monkeypatch, make_target):
    _no_fs(monkeypatch)
    _PathLike.calls = 0
    with pytest.raises(MaterializationInputError):
        materialize_atomic_bytes(make_target(tmp_path / "a.jpg"), b"x")
    assert _PathLike.calls == 0


def test_hostile_str_subclass_target_is_rejected_without_running_hooks(tmp_path, monkeypatch):
    _no_fs(monkeypatch)
    hostile = _HostileStr(str(tmp_path / "a.jpg"))
    _HostileStr.calls = 0
    with pytest.raises(MaterializationInputError):
        materialize_atomic_bytes(hostile, b"x")
    assert _HostileStr.calls == 0


def test_target_type_is_checked_before_content_type(monkeypatch):
    _no_fs(monkeypatch)
    with pytest.raises(MaterializationInputError, match="target_path"):
        materialize_atomic_bytes(None, None)  # type: ignore[arg-type]


@pytest.mark.parametrize("raw", ["", "relative.jpg", "~/poster.jpg", "$HOME/poster.jpg",
                                 "%USERPROFILE%\\poster.jpg", "./poster.jpg"])
def test_non_explicit_targets_are_rejected_before_any_io(monkeypatch, raw):
    _no_fs(monkeypatch)
    with pytest.raises(InvalidTargetPathError):
        materialize_atomic_bytes(raw, b"x")


def test_every_error_is_a_materialization_error():
    from fc2_organizer import materialization as m

    for name in m.__all__:
        obj = getattr(m, name)
        if isinstance(obj, type) and issubclass(obj, BaseException):
            # compare within one module generation (architecture tests purge and re-import)
            assert issubclass(obj, m.MaterializationError), name
