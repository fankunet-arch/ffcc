"""P4-C6 substep 2: pure artifact mapping (plan + rendered NFO + acquired images -> requests)."""

from __future__ import annotations

import builtins
import dataclasses
import io
import os

import pytest

from fc2_organizer.images import ImageAcquisitionResult, ImageRole
from fc2_organizer.materialization import (
    ArtifactKind,
    ArtifactMappingError,
    ArtifactWriteRequest,
    MappingRejectionReason as R,
    MaterializationInputError,
    MaterializationModelError,
)
from fc2_organizer.materialization.mapping import build_artifact_requests, extrafanart_filename
from fc2_organizer.planning import OrganizePlan

from ._builders import NFO_TEXT, full_images, image, jpeg, make_plan


@pytest.fixture
def plan(tmp_path):
    return make_plan(str(tmp_path / "library"))


def _kinds(requests):
    return [r.kind for r in requests]


# --------------------------------------------------------------------------- manifest shape / order


def test_nfo_only_manifest(plan):
    requests = build_artifact_requests(plan, NFO_TEXT, ImageAcquisitionResult())
    assert type(requests) is tuple and len(requests) == 1
    (nfo,) = requests
    assert type(nfo) is ArtifactWriteRequest
    assert nfo.kind is ArtifactKind.NFO and nfo.target_path == plan.nfo_path.absolute_path
    assert nfo.content == NFO_TEXT.encode("utf-8") and nfo.ordinal is None


def test_full_manifest_fixed_order_and_exact_targets(plan):
    images = full_images(extra_count=3)
    requests = build_artifact_requests(plan, NFO_TEXT, images)
    assert _kinds(requests) == [ArtifactKind.NFO, ArtifactKind.POSTER, ArtifactKind.FANART, ArtifactKind.THUMB,
                                ArtifactKind.EXTRAFANART, ArtifactKind.EXTRAFANART, ArtifactKind.EXTRAFANART]
    extra_dir = plan.extrafanart_directory.absolute_path
    assert [r.target_path for r in requests] == [
        plan.nfo_path.absolute_path,
        plan.poster_path.absolute_path,
        plan.fanart_path.absolute_path,
        plan.thumb_path.absolute_path,
        os.path.join(extra_dir, "extrafanart-001.jpg"),
        os.path.join(extra_dir, "extrafanart-002.jpg"),
        os.path.join(extra_dir, "extrafanart-003.jpg"),
    ]
    assert [r.ordinal for r in requests] == [None, None, None, None, 1, 2, 3]


@pytest.mark.parametrize("present", [
    (), ("poster",), ("fanart",), ("thumb",), ("poster", "thumb"), ("fanart", "thumb"), ("poster", "fanart"),
])
def test_missing_optional_images_produce_no_request_and_no_cross_role_fallback(plan, present):
    full = full_images(extra_count=0)
    images = ImageAcquisitionResult(**{name: getattr(full, name) for name in present})
    requests = build_artifact_requests(plan, NFO_TEXT, images)
    expected = [ArtifactKind.NFO] + [k for k in (ArtifactKind.POSTER, ArtifactKind.FANART, ArtifactKind.THUMB)
                                     if k.value in present]
    assert _kinds(requests) == expected
    for r in requests[1:]:
        # each role's bytes go only to that role's own path
        assert r.content == getattr(full, r.kind.value).content
        assert r.target_path == getattr(plan, f"{r.kind.value}_path").absolute_path


def test_extrafanart_only_manifest_follows_acquisition_order(plan):
    extras = tuple(image(ImageRole.EXTRAFANART, jpeg(b"e%02d" % i), candidate_index=10 - i) for i in range(5))
    requests = build_artifact_requests(plan, NFO_TEXT, ImageAcquisitionResult(extrafanart=extras))
    assert [r.content for r in requests[1:]] == [e.content for e in extras]  # tuple order, not candidate_index
    assert [r.ordinal for r in requests[1:]] == [1, 2, 3, 4, 5]


def test_extrafanart_names_are_deterministic_and_frozen(plan):
    images = full_images(extra_count=12)
    names = [os.path.basename(r.target_path) for r in build_artifact_requests(plan, NFO_TEXT, images)[4:]]
    assert names == [f"extrafanart-{i:03d}.jpg" for i in range(1, 13)]
    assert names[0] == "extrafanart-001.jpg" and names[-1] == "extrafanart-012.jpg"
    for r in build_artifact_requests(plan, NFO_TEXT, images)[4:]:
        assert os.path.dirname(r.target_path) == plan.extrafanart_directory.absolute_path


def test_extrafanart_name_never_uses_url_title_hash_or_randomness(plan):
    images = full_images(extra_count=2)
    a = build_artifact_requests(plan, NFO_TEXT, images)
    b = build_artifact_requests(plan, NFO_TEXT, images)
    assert a == b
    for r in a[4:]:
        name = os.path.basename(r.target_path)
        assert "Example" not in name and "Title" not in name and "http" not in name
        assert all(img.sha256[:8] not in name for img in images.extrafanart)


@pytest.mark.parametrize(("ordinal", "name"), [
    (1, "extrafanart-001.jpg"),
    (12, "extrafanart-012.jpg"),
    (99, "extrafanart-099.jpg"),
    (999, "extrafanart-999.jpg"),
    (1000, "extrafanart-1000.jpg"),
    (10000, "extrafanart-10000.jpg"),
    (123456789, "extrafanart-123456789.jpg"),
])
def test_extrafanart_filename_03d_is_minimum_width_with_no_maximum(ordinal, name):
    assert extrafanart_filename(ordinal) == name


class _Int(int):
    pass


@pytest.mark.parametrize("bad", [0, -1, -1000, True, False, 1.0, "1", None, _Int(1)],
                         ids=["zero", "neg", "neg-large", "True", "False", "float", "str", "None", "int-subclass"])
def test_extrafanart_filename_rejects_non_positive_or_non_exact_int(bad):
    with pytest.raises(ArtifactMappingError) as info:
        extrafanart_filename(bad)
    assert info.value.reason is R.INVALID_EXTRAFANART_ORDINAL


def test_1000_extrafanart_map_completely_in_memory(plan):
    extras = tuple(image(ImageRole.EXTRAFANART, jpeg(b"%d" % (i % 7)), candidate_index=i) for i in range(1000))
    images = ImageAcquisitionResult(extrafanart=extras)
    requests = build_artifact_requests(plan, NFO_TEXT, images)
    extra_reqs = requests[1:]
    assert len(requests) == 1001 and len(extra_reqs) == 1000
    assert all(r.kind is ArtifactKind.EXTRAFANART for r in extra_reqs)
    assert [r.ordinal for r in extra_reqs] == list(range(1, 1001))
    names = [os.path.basename(r.target_path) for r in extra_reqs]
    assert names[0] == "extrafanart-001.jpg" and names[998] == "extrafanart-999.jpg"
    assert names[-1] == "extrafanart-1000.jpg"
    assert len(set(names)) == 1000  # no truncation / modulo collision
    assert all(r.content is e.content for r, e in zip(extra_reqs, extras, strict=True))  # order kept, no dedupe
    assert build_artifact_requests(plan, NFO_TEXT, images) == requests  # deterministic replay


def test_mapping_is_deterministic(plan):
    images = full_images()
    assert build_artifact_requests(plan, NFO_TEXT, images) == build_artifact_requests(plan, NFO_TEXT, images)


# --------------------------------------------------------------------------- NFO encoding


def test_nfo_bytes_are_exact_utf8_encoding(plan):
    (nfo,) = build_artifact_requests(plan, NFO_TEXT, ImageAcquisitionResult())
    assert nfo.content == NFO_TEXT.encode("utf-8", errors="strict")
    assert nfo.content.decode("utf-8") == NFO_TEXT


def test_unicode_nfo_is_encoded_exactly(plan):
    text = NFO_TEXT.replace("Example Title", "日本語タイトル 🎬 Ünïcödé &amp; ﾊﾝｶｸ")
    (nfo,) = build_artifact_requests(plan, text, ImageAcquisitionResult())
    assert nfo.content == text.encode("utf-8")
    assert "🎬".encode("utf-8") in nfo.content


@pytest.mark.parametrize("text", [
    NFO_TEXT,
    NFO_TEXT.replace("\n", "\r\n"),          # CRLF kept, never rewritten to LF
    "  " + NFO_TEXT + "  \n\n",              # surrounding whitespace kept, never stripped
    "\ufeff" + NFO_TEXT,                     # a caller-supplied U+FEFF is encoded, not added or removed
    "e\u0301" + NFO_TEXT,                    # decomposed form kept, never NFC-normalized
])
def test_nfo_text_is_never_mutated(plan, text):
    (nfo,) = build_artifact_requests(plan, text, ImageAcquisitionResult())
    assert nfo.content == text.encode("utf-8")


def test_no_bom_is_added(plan):
    (nfo,) = build_artifact_requests(plan, NFO_TEXT, ImageAcquisitionResult())
    assert not nfo.content.startswith(b"\xef\xbb\xbf") and nfo.content.startswith(b"<?xml")


def test_empty_nfo_is_rejected(plan):
    with pytest.raises(ArtifactMappingError) as info:
        build_artifact_requests(plan, "", ImageAcquisitionResult())
    assert info.value.reason is R.NFO_EMPTY


def test_unencodable_nfo_is_typed_and_unchained(plan):
    with pytest.raises(ArtifactMappingError) as info:
        build_artifact_requests(plan, NFO_TEXT + "\ud800", ImageAcquisitionResult())
    assert info.value.reason is R.NFO_NOT_UTF8_ENCODABLE
    assert info.value.__context__ is None and info.value.__cause__ is None


# --------------------------------------------------------------------------- image bytes


def test_image_bytes_are_the_acquired_objects_themselves(plan):
    images = full_images(extra_count=2)
    requests = build_artifact_requests(plan, NFO_TEXT, images)
    sources = [images.poster, images.fanart, images.thumb, *images.extrafanart]
    for r, src in zip(requests[1:], sources, strict=True):
        assert r.content is src.content  # identity: no re-encode, resize, transcode or copy


def test_duplicate_image_bytes_are_not_deduplicated(plan):
    same = jpeg(b"same")
    images = ImageAcquisitionResult(
        poster=image(ImageRole.POSTER, same), fanart=image(ImageRole.FANART, same),
        thumb=image(ImageRole.THUMB, same),
        extrafanart=(image(ImageRole.EXTRAFANART, same),) * 3,
    )
    requests = build_artifact_requests(plan, NFO_TEXT, images)
    assert len(requests) == 7
    assert all(r.content == same for r in requests[1:])
    assert len({r.target_path for r in requests}) == 7


def test_requests_hold_no_foreign_objects(plan):
    for r in build_artifact_requests(plan, NFO_TEXT, full_images()):
        assert [f.name for f in dataclasses.fields(r)] == ["kind", "target_path", "content", "ordinal"]
        assert type(r.content) is bytes and type(r.target_path) is str
        assert "xff" not in repr(r)  # content excluded from repr


# --------------------------------------------------------------------------- input identity


class _HostileStr(str):
    calls = 0

    def encode(self, *a, **k):
        type(self).calls += 1
        return b"EVIL"

    def __len__(self):
        type(self).calls += 1
        return 1

    def __bool__(self):
        type(self).calls += 1
        return True


def test_hostile_str_subclass_nfo_is_rejected_without_hooks(plan):
    _HostileStr.calls = 0
    with pytest.raises(MaterializationInputError):
        build_artifact_requests(plan, _HostileStr(NFO_TEXT), ImageAcquisitionResult())
    assert _HostileStr.calls == 0


@pytest.mark.parametrize("nfo", [NFO_TEXT.encode(), None, 1, bytearray(b"x")])
def test_non_str_nfo_is_rejected(plan, nfo):
    with pytest.raises(MaterializationInputError):
        build_artifact_requests(plan, nfo, ImageAcquisitionResult())


def _spy_subclass(base):
    """A subclass instance whose every attribute access is counted (never initialised)."""
    counter = {"n": 0}

    class Spy(base):
        __slots__ = ()

        def __getattribute__(self, name):
            counter["n"] += 1
            return object.__getattribute__(self, name)

    return Spy.__new__(Spy), counter


def test_plan_subclass_is_rejected_without_attribute_access(plan):
    spy, counter = _spy_subclass(OrganizePlan)
    with pytest.raises(MaterializationInputError):
        build_artifact_requests(spy, NFO_TEXT, ImageAcquisitionResult())
    assert counter["n"] == 0


def test_images_subclass_is_rejected_without_attribute_access(plan):
    spy, counter = _spy_subclass(ImageAcquisitionResult)
    with pytest.raises(MaterializationInputError):
        build_artifact_requests(plan, NFO_TEXT, spy)
    assert counter["n"] == 0


@pytest.mark.parametrize("bad", [None, {}, "plan", object()])
def test_wrong_plan_or_images_type_is_rejected(plan, bad):
    with pytest.raises(MaterializationInputError):
        build_artifact_requests(bad, NFO_TEXT, ImageAcquisitionResult())
    with pytest.raises(MaterializationInputError):
        build_artifact_requests(plan, NFO_TEXT, bad)


def test_forged_plan_path_is_rejected(plan):
    object.__setattr__(plan, "poster_path", plan.poster_path.absolute_path)  # a bare str, not PlannedPath
    with pytest.raises(ArtifactMappingError) as info:
        build_artifact_requests(plan, NFO_TEXT, full_images())
    assert info.value.reason is R.PLAN_PATH_INVALID


def test_forged_colliding_plan_paths_are_rejected(plan):
    object.__setattr__(plan, "poster_path", plan.nfo_path)
    with pytest.raises(ArtifactMappingError) as info:
        build_artifact_requests(plan, NFO_TEXT, full_images())
    assert info.value.reason is R.DUPLICATE_TARGET


def test_forged_wrong_role_image_is_rejected(plan):
    images = ImageAcquisitionResult()
    object.__setattr__(images, "poster", image(ImageRole.FANART, jpeg(b"f")))
    with pytest.raises(ArtifactMappingError) as info:
        build_artifact_requests(plan, NFO_TEXT, images)
    assert info.value.reason is R.IMAGE_INVALID


def test_canonical_number_is_never_reparsed(plan):
    object.__setattr__(plan, "canonical_number", "not-an-fc2-number")
    assert len(build_artifact_requests(plan, NFO_TEXT, ImageAcquisitionResult())) == 1


def test_plan_operations_are_never_consulted(plan):
    images = full_images()
    before = build_artifact_requests(plan, NFO_TEXT, images)
    object.__setattr__(plan, "operations", ())
    assert build_artifact_requests(plan, NFO_TEXT, images) == before


# --------------------------------------------------------------------------- request model


def test_request_model_rules():
    ok = ArtifactWriteRequest(ArtifactKind.POSTER, "C:\\x\\poster.jpg", b"x")
    with pytest.raises(dataclasses.FrozenInstanceError):
        ok.content = b"y"  # type: ignore[misc]
    bad = [
        dict(kind="poster", target_path="p", content=b"x"),
        dict(kind=ArtifactKind.POSTER, target_path="", content=b"x"),
        dict(kind=ArtifactKind.POSTER, target_path=type("S", (str,), {})("p"), content=b"x"),
        dict(kind=ArtifactKind.POSTER, target_path="p", content=bytearray(b"x")),
        dict(kind=ArtifactKind.POSTER, target_path="p", content=b"x", ordinal=1),
        dict(kind=ArtifactKind.EXTRAFANART, target_path="p", content=b"x"),
        dict(kind=ArtifactKind.EXTRAFANART, target_path="p", content=b"x", ordinal=0),
        dict(kind=ArtifactKind.EXTRAFANART, target_path="p", content=b"x", ordinal=True),
    ]
    for fields in bad:
        with pytest.raises(MaterializationModelError):
            ArtifactWriteRequest(**fields)


def test_artifact_kinds_are_exactly_the_five_frozen_kinds():
    assert [k.name for k in ArtifactKind] == ["NFO", "POSTER", "FANART", "THUMB", "EXTRAFANART"]


# --------------------------------------------------------------------------- purity


def test_mapping_performs_zero_filesystem_calls(plan, monkeypatch):
    images = full_images(extra_count=4)
    calls = []

    def boom(name):
        def op(*a, **k):
            calls.append(name)
            raise AssertionError(f"filesystem call {name} during pure mapping")
        return op

    for name in ("stat", "lstat", "open", "mkdir", "makedirs", "listdir", "scandir", "rename", "replace",
                 "link", "unlink", "remove", "rmdir", "getcwd", "walk"):
        monkeypatch.setattr(os, name, boom(f"os.{name}"))
    for name in ("exists", "isdir", "isfile", "lexists", "realpath", "abspath", "expanduser"):
        monkeypatch.setattr(os.path, name, boom(f"os.path.{name}"))
    monkeypatch.setattr(builtins, "open", boom("open"))
    monkeypatch.setattr(io, "open", boom("io.open"))
    from fc2_organizer.materialization import atomic
    monkeypatch.setattr(atomic, "materialize_atomic_bytes", boom("materialize_atomic_bytes"))

    requests = build_artifact_requests(plan, NFO_TEXT, images)
    assert len(requests) == 8 and calls == []
