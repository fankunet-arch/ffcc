"""P4-C5 substep 1: immutable image value models (contract section 3-6)."""

from __future__ import annotations

import dataclasses
import hashlib

import pytest

from fc2_organizer.images import (
    AcquiredImage,
    ImageAcquisitionResult,
    ImageCandidateFailure,
    ImageError,
    ImageFailureKind,
    ImageModelError,
    ImageRole,
)

CONTENT = b"\xff\xd8\xff\xe0 fake jpeg bytes \xff\xd9"


def _image(role: ImageRole = ImageRole.POSTER, content: bytes = CONTENT, **overrides: object) -> AcquiredImage:
    fields: dict[str, object] = dict(
        role=role,
        candidate_index=0,
        content=content,
        width=800,
        height=538,
        size_bytes=len(content),
        sha256=hashlib.sha256(content).hexdigest(),
    )
    fields.update(overrides)
    return AcquiredImage(**fields)  # type: ignore[arg-type]


# --- roles / vocabulary --------------------------------------------------------------------------


def test_image_roles_are_exactly_the_four_layout_roles():
    assert [r.name for r in ImageRole] == ["POSTER", "FANART", "THUMB", "EXTRAFANART"]


def test_failure_kind_vocabulary_is_frozen():
    assert {k.name for k in ImageFailureKind} == {
        "INVALID_URL", "UNSAFE_URL", "CANDIDATE_LIMIT",
        "TIMEOUT", "CONNECTION_ERROR", "REDIRECT_LIMIT", "TRANSPORT_ERROR",
        "HTTP_STATUS", "TOO_LARGE", "TOTAL_BYTES_LIMIT",
        "CONTENT_TYPE_MISMATCH", "INVALID_JPEG", "INVALID_DIMENSIONS",
    }


# --- AcquiredImage -------------------------------------------------------------------------------


def test_acquired_image_is_frozen_and_slotted():
    image = _image()
    with pytest.raises(dataclasses.FrozenInstanceError):
        image.width = 1  # type: ignore[misc]
    assert not hasattr(image, "__dict__")


def test_acquired_image_repr_never_contains_content_bytes():
    assert "fake jpeg" not in repr(_image())


class _BytesSub(bytes):
    pass


@pytest.mark.parametrize("content", [bytearray(CONTENT), memoryview(CONTENT), _BytesSub(CONTENT), "text"])
def test_acquired_image_content_must_be_exact_bytes(content):
    with pytest.raises(ImageModelError):
        AcquiredImage(ImageRole.POSTER, 0, content, 1, 1, len(CONTENT), hashlib.sha256(CONTENT).hexdigest())


@pytest.mark.parametrize("bad", [True, False, -1, 1.0, "0", None])
def test_acquired_image_candidate_index_exact_non_negative_int(bad):
    with pytest.raises(ImageModelError):
        _image(candidate_index=bad)


@pytest.mark.parametrize("name", ["width", "height"])
@pytest.mark.parametrize("bad", [True, 0, -1, 1.5, "1", None])
def test_acquired_image_dimensions_exact_positive_int(name, bad):
    with pytest.raises(ImageModelError):
        _image(**{name: bad})


@pytest.mark.parametrize("bad", [len(CONTENT) + 1, len(CONTENT) - 1, True, float(len(CONTENT))])
def test_acquired_image_size_bytes_must_equal_len_content(bad):
    with pytest.raises(ImageModelError):
        _image(size_bytes=bad)


def test_acquired_image_checks_shape_only_not_jpeg_validity():
    # Substep 1 checks model invariants only; "is this a real JPEG" is a later substep.
    image = _image(content=b"")
    assert image.size_bytes == 0


@pytest.mark.parametrize(
    "bad",
    [
        hashlib.sha256(CONTENT).hexdigest().upper(),
        hashlib.sha256(CONTENT).hexdigest()[:-1],
        hashlib.sha256(CONTENT).hexdigest() + "0",
        "g" * 64,
        hashlib.sha256(CONTENT).digest(),
        None,
    ],
)
def test_acquired_image_sha256_shape(bad):
    with pytest.raises(ImageModelError):
        _image(sha256=bad)


def test_acquired_image_sha256_must_match_content():
    with pytest.raises(ImageModelError):
        _image(sha256=hashlib.sha256(b"other").hexdigest())


def test_acquired_image_role_must_be_image_role():
    with pytest.raises(ImageModelError):
        _image(role="poster")


def test_model_errors_are_typed_image_errors():
    with pytest.raises(ImageError) as info:
        _image(width=0)
    assert type(info.value) is ImageModelError


# --- ImageCandidateFailure -----------------------------------------------------------------------


def test_candidate_failure_is_frozen_and_has_no_url_or_detail_fields():
    failure = ImageCandidateFailure(ImageRole.FANART, 3, ImageFailureKind.TIMEOUT)
    with pytest.raises(dataclasses.FrozenInstanceError):
        failure.kind = ImageFailureKind.TOO_LARGE  # type: ignore[misc]
    assert not hasattr(failure, "__dict__")
    assert {f.name for f in dataclasses.fields(ImageCandidateFailure)} == {
        "role", "candidate_index", "kind", "http_status",
    }


def test_candidate_failure_http_status_only_with_http_status_kind():
    assert ImageCandidateFailure(ImageRole.THUMB, 0, ImageFailureKind.HTTP_STATUS, 404).http_status == 404
    assert ImageCandidateFailure(ImageRole.THUMB, 0, ImageFailureKind.TIMEOUT).http_status is None
    with pytest.raises(ImageModelError):
        ImageCandidateFailure(ImageRole.THUMB, 0, ImageFailureKind.HTTP_STATUS)
    with pytest.raises(ImageModelError):
        ImageCandidateFailure(ImageRole.THUMB, 0, ImageFailureKind.TIMEOUT, 404)


@pytest.mark.parametrize("bad", [True, 99, 600, 404.0, "404"])
def test_candidate_failure_http_status_exact_int_in_range(bad):
    with pytest.raises(ImageModelError):
        ImageCandidateFailure(ImageRole.THUMB, 0, ImageFailureKind.HTTP_STATUS, bad)


@pytest.mark.parametrize(
    "args",
    [
        ("poster", 0, ImageFailureKind.TIMEOUT),
        (ImageRole.POSTER, -1, ImageFailureKind.TIMEOUT),
        (ImageRole.POSTER, True, ImageFailureKind.TIMEOUT),
        (ImageRole.POSTER, 0, "timeout"),
    ],
)
def test_candidate_failure_field_types(args):
    with pytest.raises(ImageModelError):
        ImageCandidateFailure(*args)


# --- ImageAcquisitionResult ----------------------------------------------------------------------


def test_result_allows_all_empty_and_is_frozen():
    result = ImageAcquisitionResult()
    assert (result.poster, result.fanart, result.thumb, result.extrafanart, result.failures) == (
        None, None, None, (), (),
    )
    assert result.total_bytes == 0
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.poster = None  # type: ignore[misc]
    assert not hasattr(result, "__dict__")


@pytest.mark.parametrize("slot", ["poster", "fanart", "thumb"])
def test_result_single_slots_require_matching_role(slot):
    for role in ImageRole:
        image = _image(role=role)
        if role.value == slot:
            assert getattr(ImageAcquisitionResult(**{slot: image}), slot) is image
        else:
            with pytest.raises(ImageModelError):
                ImageAcquisitionResult(**{slot: image})


def test_result_extrafanart_only_extrafanart_role_in_exact_tuple():
    extra = _image(role=ImageRole.EXTRAFANART)
    assert ImageAcquisitionResult(extrafanart=(extra,)).extrafanart == (extra,)
    with pytest.raises(ImageModelError):
        ImageAcquisitionResult(extrafanart=(_image(role=ImageRole.POSTER),))
    with pytest.raises(ImageModelError):
        ImageAcquisitionResult(extrafanart=[extra])  # type: ignore[arg-type]
    with pytest.raises(ImageModelError):
        ImageAcquisitionResult(extrafanart=("not an image",))  # type: ignore[arg-type]


def test_result_failures_only_candidate_failures_in_exact_tuple():
    failure = ImageCandidateFailure(ImageRole.POSTER, 0, ImageFailureKind.UNSAFE_URL)
    assert ImageAcquisitionResult(failures=(failure,)).failures == (failure,)
    with pytest.raises(ImageModelError):
        ImageAcquisitionResult(failures=[failure])  # type: ignore[arg-type]
    with pytest.raises(ImageModelError):
        ImageAcquisitionResult(failures=(ValueError("boom"),))  # type: ignore[arg-type]


def test_result_rejects_non_acquired_image_single_slot():
    with pytest.raises(ImageModelError):
        ImageAcquisitionResult(poster=CONTENT)  # type: ignore[arg-type]


def test_total_bytes_sums_every_acquired_image():
    poster = _image(ImageRole.POSTER, b"a" * 10)
    fanart = _image(ImageRole.FANART, b"b" * 20)
    thumb = _image(ImageRole.THUMB, b"c" * 30)
    extras = tuple(_image(ImageRole.EXTRAFANART, bytes([i]) * (i + 1), candidate_index=i) for i in range(4))
    result = ImageAcquisitionResult(
        poster=poster, fanart=fanart, thumb=thumb, extrafanart=extras,
        failures=(ImageCandidateFailure(ImageRole.POSTER, 1, ImageFailureKind.HTTP_STATUS, 500),),
    )
    assert result.total_bytes == 10 + 20 + 30 + (1 + 2 + 3 + 4)
    assert ImageAcquisitionResult(fanart=fanart).total_bytes == 20
