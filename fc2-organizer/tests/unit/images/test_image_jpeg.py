"""P4-C5 substep 3: JPEG-only content policy, bounded structural validation, dimension caps
(contract section 13). Fixtures are built segment by segment -- never ``FFD8 + random + FFD9``."""

from __future__ import annotations

import dataclasses
import random

import pytest

from fc2_organizer.images import (
    MAX_IMAGE_HEIGHT,
    MAX_IMAGE_PIXELS,
    MAX_IMAGE_WIDTH,
    ContentTypeVerdict,
    DimensionRejectionReason,
    ImageContentTypeError,
    ImageDimensionError,
    ImageError,
    ImageFailureKind,
    ImageInputError,
    ImageJpegError,
    JpegInfo,
    JpegRejectionReason,
    inspect_jpeg,
    validate_acquired_image,
    validate_image_content_type,
)
from fc2_organizer.images.jpeg import SOF_MARKERS

J = JpegRejectionReason
D = DimensionRejectionReason

# --- fixture builder -------------------------------------------------------------------------------

SOI = b"\xff\xd8"
EOI = b"\xff\xd9"


def segment(marker: int, payload: bytes) -> bytes:
    return bytes([0xFF, marker]) + (len(payload) + 2).to_bytes(2, "big") + payload


def app0() -> bytes:
    return segment(0xE0, b"JFIF\x00\x01\x01\x00\x00\x48\x00\x48\x00\x00")


def dqt() -> bytes:
    return segment(0xDB, b"\x00" + bytes(range(1, 65)))


def dht() -> bytes:
    counts = bytes([0, 1, 5, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0])
    return segment(0xC4, b"\x00" + counts + bytes(range(12)))


def sof(width: int = 640, height: int = 480, marker: int = 0xC0, precision: int = 8, components: int = 3,
        declared_components: int | None = None) -> bytes:
    count = components if declared_components is None else declared_components
    body = bytes([precision]) + height.to_bytes(2, "big") + width.to_bytes(2, "big") + bytes([count])
    body += b"".join(bytes([i + 1, 0x11 if i == 0 else 0x11, 0 if i == 0 else 1]) for i in range(components))
    return segment(marker, body)


def sos(components: int = 3) -> bytes:
    body = bytes([components]) + b"".join(bytes([i + 1, 0x00 if i == 0 else 0x11]) for i in range(components))
    return segment(0xDA, body + b"\x00\x3f\x00")


ENTROPY = b"\xf8\x3f\x12\xff\x00\x9a\xcd\xff\xd0\x44\x11"  # contains stuffed FF00 and an RST0


def jpeg(*, width: int = 640, height: int = 480, marker: int = 0xC0, head: bytes | None = None,
         entropy: bytes = ENTROPY, tail: bytes = EOI) -> bytes:
    head = app0() + dqt() if head is None else head
    return SOI + head + sof(width, height, marker) + dht() + sos() + entropy + tail


# --- valid structures ---------------------------------------------------------------------------------


def test_baseline_sof0_valid_and_dimensions_extracted():
    info = inspect_jpeg(jpeg(width=1280, height=720, marker=0xC0))
    assert info == JpegInfo(width=1280, height=720, sof_marker=0xC0)


def test_progressive_sof2_valid():
    info = inspect_jpeg(jpeg(width=800, height=538, marker=0xC2))
    assert (info.width, info.height, info.sof_marker) == (800, 538, 0xC2)


@pytest.mark.parametrize("marker", sorted(SOF_MARKERS))
def test_every_standard_sof_marker_is_accepted(marker):
    precision = 8 if marker not in (0xC3, 0xC7, 0xCB, 0xCF) else 16
    data = SOI + dqt() + sof(10, 20, marker, precision) + sos() + ENTROPY + EOI
    assert inspect_jpeg(data).sof_marker == marker


def test_app_segments_dqt_dht_com_dri_before_sof():
    head = app0() + segment(0xE1, b"Exif\x00\x00" + b"\x00" * 30) + segment(0xFE, b"comment \xff\xd9 inside") \
        + dqt() + dht() + segment(0xDD, b"\x00\x10")
    assert inspect_jpeg(jpeg(width=3, height=4, head=head)) == JpegInfo(3, 4, 0xC0)


def test_fill_bytes_before_markers_are_not_segment_data():
    data = SOI + b"\xff\xff\xff" + app0() + b"\xff\xff" + sof(7, 9) + sos() + ENTROPY + EOI
    assert inspect_jpeg(data) == JpegInfo(7, 9, 0xC0)


def test_standalone_tem_and_rst_markers_are_skipped():
    data = SOI + b"\xff\x01" + app0() + b"\xff\xd3" + sof(5, 6) + sos() + ENTROPY + EOI
    assert inspect_jpeg(data) == JpegInfo(5, 6, 0xC0)


def test_entropy_data_is_not_scanned_for_markers():
    # SOI / SOF-looking bytes inside the scan must not matter; only the final EOI does.
    entropy = b"\xff\xd8\xff\xc0\x00\x11" + b"\x00" * 50 + b"\xff\xda\xff\xd9\x00\x01"
    assert inspect_jpeg(jpeg(entropy=entropy)) == JpegInfo(640, 480, 0xC0)


def test_empty_entropy_segment_still_needs_eoi_after_sos():
    assert inspect_jpeg(jpeg(entropy=b"")).width == 640


# --- non-SOF markers are not frames ----------------------------------------------------------------------


@pytest.mark.parametrize("marker", [0xC4, 0xC8, 0xCC])  # DHT, JPG, DAC
def test_dht_jpg_dac_are_never_taken_as_sof(marker):
    fake_frame = bytes([8]) + (100).to_bytes(2, "big") + (100).to_bytes(2, "big") + b"\x01\x01\x11\x00"
    data = SOI + segment(marker, fake_frame) + sos() + ENTROPY + EOI
    with pytest.raises(ImageJpegError) as info:
        inspect_jpeg(data)
    assert info.value.reason is J.MISSING_SOF


# --- invalid structures (spec items 7-13) ------------------------------------------------------------------


def _jpeg_reason(data: bytes) -> JpegRejectionReason:
    with pytest.raises(ImageJpegError) as info:
        inspect_jpeg(data)
    assert info.value.__cause__ is None and info.value.__context__ is None
    assert info.value.failure_kind is ImageFailureKind.INVALID_JPEG
    return info.value.reason


def test_missing_soi():
    assert _jpeg_reason(jpeg()[2:]) is J.NOT_JPEG
    assert _jpeg_reason(b"") is J.NOT_JPEG
    assert _jpeg_reason(b"\xff") is J.NOT_JPEG


def test_missing_sof():
    assert _jpeg_reason(SOI + app0() + dqt() + dht() + sos() + ENTROPY + EOI) is J.MISSING_SOF


def test_missing_sos():
    assert _jpeg_reason(SOI + app0() + sof() + dht() + EOI) is J.MISSING_SOS
    assert _jpeg_reason(SOI + app0() + sof() + dht()) is J.TRUNCATED  # data ends before any scan


def test_missing_eoi():
    assert _jpeg_reason(jpeg(tail=b"")) is J.MISSING_EOI
    assert _jpeg_reason(jpeg(tail=EOI + b"trailing")) is J.MISSING_EOI
    assert _jpeg_reason(jpeg(tail=b"\xff")) is J.MISSING_EOI


def test_start_and_end_markers_alone_are_not_a_jpeg():
    # the naive startswith(FFD8) and endswith(FFD9) check would accept all of these
    for data in (SOI + EOI, SOI + b"random bytes that are no segment" + EOI, SOI + bytes(range(256)) + EOI):
        with pytest.raises(ImageJpegError):
            inspect_jpeg(data)


def test_truncated_segment():
    full = SOI + app0() + sof()
    assert _jpeg_reason(full[:-3]) is J.SEGMENT_OUT_OF_BOUNDS
    assert _jpeg_reason(SOI + b"\xff\xe0\x00") is J.TRUNCATED  # length field cut
    assert _jpeg_reason(SOI + b"\xff") is J.TRUNCATED  # marker code cut
    assert _jpeg_reason(SOI + b"\xff\xff\xff") is J.TRUNCATED


@pytest.mark.parametrize("length", [0, 1])
def test_segment_length_below_two(length):
    assert _jpeg_reason(SOI + b"\xff\xe0" + length.to_bytes(2, "big") + b"\x00" * 10) is J.INVALID_SEGMENT_LENGTH


def test_segment_length_beyond_body():
    assert _jpeg_reason(SOI + b"\xff\xe0\xff\xff" + b"\x00" * 100) is J.SEGMENT_OUT_OF_BOUNDS
    assert _jpeg_reason(SOI + app0() + b"\xff\xc0\x00\x40" + b"\x08\x00\x10") is J.SEGMENT_OUT_OF_BOUNDS


def test_marker_expected_but_data_found():
    assert _jpeg_reason(SOI + b"\x00\x00" + app0()) is J.INVALID_MARKER
    assert _jpeg_reason(SOI + app0() + b"garbage" + sof() + sos() + EOI) is J.INVALID_MARKER


@pytest.mark.parametrize("code", [0x00, 0x02, 0x4F, 0xBF, 0xD8])
def test_stuffed_zero_reserved_and_repeated_soi_markers_rejected(code):
    assert _jpeg_reason(SOI + bytes([0xFF, code]) + b"\x00\x04\x00\x00" + sof() + sos() + EOI) is J.INVALID_MARKER


def test_multiple_sof_rejected():
    assert _jpeg_reason(SOI + sof(10, 10) + sof(20, 20, 0xC2) + sos() + ENTROPY + EOI) is J.MULTIPLE_SOF


@pytest.mark.parametrize(
    "frame",
    [
        segment(0xC0, b"\x08\x00\x10\x00"),  # shorter than a frame header
        sof(precision=7),
        sof(precision=16),  # 16-bit only valid for lossless
        sof(marker=0xC3, precision=1),
        sof(components=0),
        sof(components=3, declared_components=4),  # component table length mismatch
    ],
)
def test_invalid_sof_segment(frame):
    assert _jpeg_reason(SOI + frame + sos() + ENTROPY + EOI) is J.INVALID_SOF


@pytest.mark.parametrize("scan", [segment(0xDA, b""), segment(0xDA, b"\x00\x00\x3f\x00"),
                                  segment(0xDA, b"\x05" + b"\x00" * 13), segment(0xDA, b"\x01\x01\x00\x00\x3f")])
def test_invalid_sos_header(scan):
    assert _jpeg_reason(SOI + sof() + scan + ENTROPY + EOI) is J.INVALID_SOS


def test_sos_before_sof_and_eoi_before_anything():
    assert _jpeg_reason(SOI + sos() + sof() + ENTROPY + EOI) is J.MISSING_SOF
    assert _jpeg_reason(SOI + EOI) is J.MISSING_SOF


# --- dimensions (spec items 14-18) ----------------------------------------------------------------------


def _dimension_reason(width: int, height: int) -> DimensionRejectionReason:
    with pytest.raises(ImageDimensionError) as info:
        inspect_jpeg(jpeg(width=width, height=height))
    assert info.value.failure_kind is ImageFailureKind.INVALID_DIMENSIONS
    assert info.value.__cause__ is None and info.value.__context__ is None
    return info.value.reason


def test_zero_width_and_zero_height():
    assert _dimension_reason(0, 480) is D.ZERO_WIDTH
    assert _dimension_reason(640, 0) is D.ZERO_HEIGHT  # DNL-defined height is not supported


def test_width_and_height_caps():
    assert _dimension_reason(20_001, 10) is D.WIDTH_TOO_LARGE
    assert _dimension_reason(10, 20_001) is D.HEIGHT_TOO_LARGE
    assert _dimension_reason(65_535, 65_535) is D.WIDTH_TOO_LARGE


def test_pixel_count_cap():
    assert MAX_IMAGE_WIDTH == MAX_IMAGE_HEIGHT == 20_000 and MAX_IMAGE_PIXELS == 100_000_000
    assert inspect_jpeg(jpeg(width=20_000, height=5_000)) == JpegInfo(20_000, 5_000, 0xC0)  # exactly 1e8
    assert inspect_jpeg(jpeg(width=20_000, height=1)).width == 20_000
    assert inspect_jpeg(jpeg(width=1, height=20_000)).height == 20_000
    assert _dimension_reason(20_000, 5_001) is D.TOO_MANY_PIXELS
    assert _dimension_reason(10_001, 10_000) is D.TOO_MANY_PIXELS


def test_structure_is_judged_before_dimensions():
    with pytest.raises(ImageJpegError):
        inspect_jpeg(jpeg(width=0, height=0, tail=b""))


@pytest.mark.parametrize("kwargs", [dict(width=0, height=1, sof_marker=0xC0), dict(width=True, height=1, sof_marker=0xC0),
                                    dict(width=1.0, height=1, sof_marker=0xC0)])
def test_jpeg_info_enforces_caps_itself(kwargs):
    with pytest.raises(ImageDimensionError):
        JpegInfo(**kwargs)


@pytest.mark.parametrize("marker", [0xC4, 0xC8, 0xCC, 0xD8, True, 0xC0 + 0.0])
def test_jpeg_info_rejects_non_sof_marker(marker):
    with pytest.raises(ImageJpegError):
        JpegInfo(width=1, height=1, sof_marker=marker)


def test_jpeg_info_is_frozen_and_slotted():
    info = inspect_jpeg(jpeg())
    with pytest.raises(dataclasses.FrozenInstanceError):
        info.width = 1  # type: ignore[misc]
    assert not hasattr(info, "__dict__")
    assert {f.name for f in dataclasses.fields(JpegInfo)} == {"width", "height", "sof_marker"}


# --- other formats (spec items 19-22) ----------------------------------------------------------------------

PNG = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x02\x80\x00\x00\x01\xe0\x08\x02\x00\x00\x00" + b"\x00" * 40
WEBP = b"RIFF\x24\x00\x00\x00WEBPVP8 \x18\x00\x00\x00" + b"\x00" * 24
GIF = b"GIF89a\x80\x02\xe0\x01\x00\x00\x00" + b"\x00" * 20 + b";"
AVIF = b"\x00\x00\x00\x1cftypavif\x00\x00\x00\x00avifmif1miaf" + b"\x00" * 20
HTML = b"<!DOCTYPE html><html><body>403 Forbidden</body></html>"


@pytest.mark.parametrize("payload", [PNG, WEBP, GIF, AVIF, HTML, b"{\"error\": \"x\"}", PNG + EOI],
                         ids=["png", "webp", "gif", "avif", "html", "json", "png-with-ffd9-tail"])
def test_non_jpeg_payloads_rejected(payload):
    assert _jpeg_reason(payload) is J.NOT_JPEG
    with pytest.raises(ImageJpegError):
        validate_acquired_image(payload, None)
    with pytest.raises(ImageJpegError):
        validate_acquired_image(payload, "application/octet-stream")


# --- robustness: no internal exception can escape -----------------------------------------------------------


def test_every_prefix_of_a_valid_jpeg_fails_typed():
    data = jpeg()
    for cut in range(len(data)):
        with pytest.raises((ImageJpegError, ImageDimensionError)):
            inspect_jpeg(data[:cut])


def test_deterministic_mutation_fuzz_never_leaks_internal_exceptions():
    rng = random.Random(20260923)
    base = jpeg()
    for _ in range(3000):
        data = bytearray(base)
        for _ in range(rng.randint(1, 6)):
            data[rng.randrange(len(data))] = rng.randrange(256)
        if rng.random() < 0.3:
            del data[rng.randrange(len(data)):]
        try:
            info = inspect_jpeg(bytes(data))
        except (ImageJpegError, ImageDimensionError):
            continue
        assert type(info) is JpegInfo and info.width > 0 and info.height > 0


def test_many_fill_bytes_and_segments_stay_linear():
    many = SOI + b"\xff" * 200_000 + app0() + segment(0xFE, b"x") * 20_000 + sof() + sos() + ENTROPY + EOI
    assert inspect_jpeg(many).width == 640


# --- Content-Type policy ------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value",
    ["image/jpeg", "IMAGE/JPEG", "Image/Jpeg", "image/jpeg; charset=binary", "Image/JPEG; charset=binary",
     "  image/jpeg  ", "image/jpg", "image/pjpeg", "IMAGE/PJPEG;q=1"],
)
def test_jpeg_media_types_accepted(value):
    assert validate_image_content_type(value) is ContentTypeVerdict.JPEG_DECLARED


@pytest.mark.parametrize("value", [None, "application/octet-stream", "Application/Octet-Stream; x=y", ""])
def test_undeclared_media_types_defer_to_bytes(value):
    assert validate_image_content_type(value) is ContentTypeVerdict.UNDECLARED
    assert validate_acquired_image(jpeg(), value) == JpegInfo(640, 480, 0xC0)
    with pytest.raises(ImageJpegError):
        validate_acquired_image(PNG, value)


@pytest.mark.parametrize(
    "value",
    ["image/png", "image/webp", "image/gif", "image/avif", "text/html", "text/html; charset=utf-8",
     "application/json", "text/plain", "image/jpeg2000", "image/x-jpeg", "binary/octet-stream", "image/*", "jpeg"],
)
def test_explicit_non_jpeg_media_types_rejected(value):
    with pytest.raises(ImageContentTypeError) as info:
        validate_image_content_type(value)
    assert info.value.failure_kind is ImageFailureKind.CONTENT_TYPE_MISMATCH
    assert info.value.args == ("image content type is not JPEG",)  # the declared value is never echoed


@pytest.mark.parametrize("value", ["image/png", "image/webp", "image/gif", "text/html", "application/json"])
def test_explicit_non_jpeg_type_with_valid_jpeg_bytes_is_still_mismatch(value):
    with pytest.raises(ImageContentTypeError):
        validate_acquired_image(jpeg(), value)


def test_content_type_error_never_echoes_the_declared_value():
    secret = "text/html; token=SECRET-abc123"
    with pytest.raises(ImageContentTypeError) as info:
        validate_image_content_type(secret)
    rendered = " ".join([str(info.value), repr(info.value), repr(info.value.args)])
    assert "SECRET" not in rendered and "text/html" not in rendered
    assert info.value.__cause__ is None and info.value.__context__ is None


# --- frozen order: content type -> structure -> dimensions --------------------------------------------------------


def test_validation_order_is_frozen():
    with pytest.raises(ImageContentTypeError):
        validate_acquired_image(b"not even a jpeg", "image/png")  # policy first
    with pytest.raises(ImageJpegError):
        validate_acquired_image(jpeg(width=0, tail=b""), "image/jpeg")  # structure before dimensions
    with pytest.raises(ImageDimensionError):
        validate_acquired_image(jpeg(width=30_000), "image/jpeg")
    assert validate_acquired_image(jpeg(), "image/jpeg") == JpegInfo(640, 480, 0xC0)


def test_error_messages_never_contain_payload_bytes():
    marker_payload = b"PAYLOAD-SECRET-" * 10
    data = SOI + segment(0xE0, marker_payload) + b"\x00"
    with pytest.raises(ImageError) as info:
        validate_acquired_image(data, "image/jpeg")
    rendered = " ".join([str(info.value), repr(info.value), repr(info.value.args)])
    assert "PAYLOAD" not in rendered and "\\x" not in rendered


# --- hostile input boundary ---------------------------------------------------------------------------------


def _hostile(base: type, names: tuple[str, ...]):
    calls: list[str] = []

    def hook(name):
        def method(self, *args, **kwargs):
            calls.append(name)
            raise AssertionError(f"hostile hook {name} executed")

        return method

    namespace = {name: hook(name) for name in names}
    return type(f"Hostile{base.__name__}", (base,), namespace), calls


_BYTES_HOOKS = ("__bytes__", "__repr__", "__str__", "__getitem__", "__len__", "__iter__", "__eq__", "__ne__",
                "__hash__", "__bool__", "__contains__", "__buffer__", "__index__", "startswith", "endswith", "find",
                "decode", "hex", "__add__", "__mod__", "__format__")
_STR_HOOKS = ("__repr__", "__str__", "__getitem__", "__len__", "__iter__", "__eq__", "__ne__", "__hash__", "__bool__",
              "__contains__", "__format__", "strip", "lower", "casefold", "split", "partition", "startswith", "encode",
              "__add__", "__mod__")


def test_hostile_bytes_subclass_rejected_with_zero_hooks():
    cls, calls = _hostile(bytes, _BYTES_HOOKS)
    hostile = cls(jpeg())
    calls.clear()
    for call in (lambda: inspect_jpeg(hostile), lambda: validate_acquired_image(hostile, "image/jpeg"),
                 lambda: validate_acquired_image(hostile, None)):
        with pytest.raises(ImageInputError):
            call()
    assert calls == []


def test_hostile_str_content_type_rejected_with_zero_hooks():
    cls, calls = _hostile(str, _STR_HOOKS)
    hostile = cls("image/jpeg")
    calls.clear()
    with pytest.raises(ImageInputError):
        validate_image_content_type(hostile)
    with pytest.raises(ImageInputError):
        validate_acquired_image(jpeg(), hostile)
    assert calls == []


@pytest.mark.parametrize("content", [bytearray(b"\xff\xd8"), memoryview(b"\xff\xd8"), "\xff\xd8", None, 0])
def test_non_bytes_content_rejected(content):
    with pytest.raises(ImageInputError):
        inspect_jpeg(content)  # type: ignore[arg-type]
    with pytest.raises(ImageInputError):
        validate_acquired_image(content, None)  # type: ignore[arg-type]


@pytest.mark.parametrize("value", [b"image/jpeg", 1, ["image/jpeg"]])
def test_non_str_content_type_rejected(value):
    with pytest.raises(ImageInputError):
        validate_image_content_type(value)  # type: ignore[arg-type]


def test_content_error_kinds_and_hierarchy():
    assert ImageContentTypeError().failure_kind is ImageFailureKind.CONTENT_TYPE_MISMATCH
    assert ImageJpegError(J.MISSING_EOI).failure_kind is ImageFailureKind.INVALID_JPEG
    assert ImageDimensionError(D.ZERO_WIDTH).failure_kind is ImageFailureKind.INVALID_DIMENSIONS
    for cls in (ImageContentTypeError, ImageJpegError, ImageDimensionError):
        assert issubclass(cls, ImageError) and issubclass(cls, ValueError)
    with pytest.raises(TypeError):
        ImageJpegError("free text")  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        ImageDimensionError("free text")  # type: ignore[arg-type]
