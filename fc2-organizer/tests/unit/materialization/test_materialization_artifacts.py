"""P4-C6 substep 2: single-artifact materializer on the real filesystem."""

from __future__ import annotations

import hashlib
import os

import pytest

from fc2_organizer.images import ImageAcquisitionResult, ImageRole
from fc2_organizer.materialization import (
    ArtifactKind,
    ArtifactWriteRequest,
    MaterializationInputError,
    MaterializedArtifact,
    ParentDirectoryMissingError,
    TargetExistsError,
    materialize_artifact,
)
from fc2_organizer.materialization import artifacts
from fc2_organizer.materialization.mapping import build_artifact_requests

from ._builders import NFO_TEXT, full_images, image, jpeg, make_plan


@pytest.fixture
def plan(tmp_path):
    return make_plan(str(tmp_path / "library"))


@pytest.fixture
def ready(plan):
    """The test (never the code under test) creates the directories C7 would create."""
    os.makedirs(plan.extrafanart_directory.absolute_path)
    return plan


def _read(path):
    with open(path, "rb") as fh:
        return fh.read()


def _by_kind(requests, kind):
    return [r for r in requests if r.kind is kind]


def _assert_written(result, request):
    assert type(result) is MaterializedArtifact
    assert result.target_path == request.target_path
    with open(request.target_path, "rb") as fh:
        data = fh.read()
    assert data == request.content
    assert result.size_bytes == len(request.content)
    assert result.sha256 == hashlib.sha256(request.content).hexdigest()


def test_nfo_is_written_with_exact_utf8_bytes(ready):
    text = NFO_TEXT.replace("Example Title", "日本語 🎬").replace("\n", "\r\n")
    (req,) = build_artifact_requests(ready, text, ImageAcquisitionResult())
    result = materialize_artifact(req)
    _assert_written(result, req)
    with open(req.target_path, "rb") as fh:
        assert fh.read() == text.encode("utf-8")  # no BOM, no newline translation


def test_poster_is_written_with_identical_bytes(ready):
    images = full_images(extra_count=0)
    (req,) = _by_kind(build_artifact_requests(ready, NFO_TEXT, images), ArtifactKind.POSTER)
    _assert_written(materialize_artifact(req), req)
    assert _read(req.target_path) == images.poster.content


def test_every_artifact_of_a_full_manifest_is_written_one_call_each(ready):
    images = full_images(extra_count=3)
    requests = build_artifact_requests(ready, NFO_TEXT, images)
    for req in requests:
        _assert_written(materialize_artifact(req), req)
    target_dir = ready.target_directory.absolute_path
    assert sorted(os.listdir(target_dir)) == sorted(["FC2-1234567.nfo", "poster.jpg", "fanart.jpg", "thumb.jpg",
                                                     "extrafanart"])
    assert sorted(os.listdir(ready.extrafanart_directory.absolute_path)) == [
        "extrafanart-001.jpg", "extrafanart-002.jpg", "extrafanart-003.jpg"]


def test_extrafanart_is_written_into_existing_directory(ready):
    images = ImageAcquisitionResult(extrafanart=(image(ImageRole.EXTRAFANART, jpeg(b"a")),
                                                 image(ImageRole.EXTRAFANART, jpeg(b"b"))))
    extras = _by_kind(build_artifact_requests(ready, NFO_TEXT, images), ArtifactKind.EXTRAFANART)
    for req in extras:
        _assert_written(materialize_artifact(req), req)
    assert os.path.basename(extras[1].target_path) == "extrafanart-002.jpg"


@pytest.mark.parametrize("kind", list(ArtifactKind))
def test_existing_target_of_every_kind_fails_closed_untouched(ready, kind):
    req = _by_kind(build_artifact_requests(ready, NFO_TEXT, full_images(extra_count=1)), kind)[0]
    with open(req.target_path, "wb") as fh:
        fh.write(b"PRE-EXISTING")
    with pytest.raises(TargetExistsError):
        materialize_artifact(req)
    assert _read(req.target_path) == b"PRE-EXISTING"
    parent = os.path.dirname(req.target_path)
    assert not any(n.startswith(".fc2tmp-") for n in os.listdir(parent))  # no suffix, no leftover temp


def test_missing_target_directory_fails_and_is_never_created(plan, monkeypatch):
    for name in ("mkdir", "makedirs"):
        monkeypatch.setattr(os, name, lambda *a, **k: pytest.fail("directory creation attempted"))
    (req,) = build_artifact_requests(plan, NFO_TEXT, ImageAcquisitionResult())
    with pytest.raises(ParentDirectoryMissingError):
        materialize_artifact(req)
    assert not os.path.exists(plan.target_directory.absolute_path)


def test_missing_extrafanart_directory_fails_and_is_never_created(plan, monkeypatch):
    os.makedirs(plan.target_directory.absolute_path)
    for name in ("mkdir", "makedirs"):
        monkeypatch.setattr(os, name, lambda *a, **k: pytest.fail("directory creation attempted"))
    images = ImageAcquisitionResult(extrafanart=(image(ImageRole.EXTRAFANART, jpeg(b"a")),))
    (req,) = _by_kind(build_artifact_requests(plan, NFO_TEXT, images), ArtifactKind.EXTRAFANART)
    with pytest.raises(ParentDirectoryMissingError):
        materialize_artifact(req)
    assert os.listdir(plan.target_directory.absolute_path) == []


def test_earlier_success_is_not_rolled_back_by_a_later_failure(ready):
    requests = build_artifact_requests(ready, NFO_TEXT, full_images(extra_count=0))
    nfo, poster = requests[0], requests[1]
    with open(poster.target_path, "wb") as fh:
        fh.write(b"OLD POSTER")
    materialize_artifact(nfo)
    with pytest.raises(TargetExistsError):
        materialize_artifact(poster)
    assert _read(nfo.target_path) == nfo.content  # independent calls: nothing to roll back


def test_wrapper_only_delegates_to_the_atomic_primitive(monkeypatch):
    calls = []
    sentinel = object()
    monkeypatch.setattr(artifacts, "materialize_atomic_bytes", lambda p, c: (calls.append((p, c)), sentinel)[1])
    req = ArtifactWriteRequest(ArtifactKind.THUMB, "C:\\lib\\thumb.jpg", b"t")
    assert materialize_artifact(req) is sentinel
    assert calls == [("C:\\lib\\thumb.jpg", b"t")]
    assert calls[0][1] is req.content


@pytest.mark.parametrize("bad", [None, b"x", ("C:\\x", b"x"), object()])
def test_wrapper_rejects_non_request(bad, monkeypatch):
    monkeypatch.setattr(artifacts, "materialize_atomic_bytes", lambda *a: pytest.fail("primitive reached"))
    with pytest.raises(MaterializationInputError):
        materialize_artifact(bad)


def test_wrapper_rejects_request_subclass_without_hooks(monkeypatch):
    monkeypatch.setattr(artifacts, "materialize_atomic_bytes", lambda *a: pytest.fail("primitive reached"))
    counter = {"n": 0}

    class Spy(ArtifactWriteRequest):
        __slots__ = ()

        def __getattribute__(self, name):
            counter["n"] += 1
            return object.__getattribute__(self, name)

    with pytest.raises(MaterializationInputError):
        materialize_artifact(Spy.__new__(Spy))
    assert counter["n"] == 0
