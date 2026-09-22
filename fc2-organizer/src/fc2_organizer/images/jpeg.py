"""JPEG-only content policy and bounded structural validation (P4-C5 substep 3, contract section 13).

::

    validate_acquired_image(content, content_type) -> JpegInfo
        1. validate_image_content_type(content_type)   explicit non-JPEG media type -> CONTENT_TYPE_MISMATCH
        2. inspect_jpeg(content)                        structure: SOI, segments, SOF, SOS, EOI -> INVALID_JPEG
        3. JpegInfo(width, height, ...)                 caps -> INVALID_DIMENSIONS

Pure: standard library only, no filesystem / network / clock / randomness, no image
library, no pixel decoding, no transcoding. The output format of P4-C5 is frozen as
**JPEG only**; PNG / WEBP / GIF / AVIF / HTML / anything without a JPEG structure is refused.

Scope of the promise (frozen): *bounded structural validation*. The walk parses every
marker and segment header up to and including the first SOS, reads the frame header
(precision, height, width, components) from the SOF segment, checks the SOS header, and
then only checks that the payload ends with EOI (``FF D9``). Entropy-coded scan data is
never scanned. Passing this check does **not** guarantee that every JPEG decoder can
decode the image.

Exact-type boundary: ``content`` must be ``type(content) is bytes`` and ``content_type``
must be ``None`` or ``type(content_type) is str`` -- checked first, before any method or
dunder of the value can run, so a hostile subclass executes no hook.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from fc2_organizer.images.errors import (
    DimensionRejectionReason,
    ImageContentTypeError,
    ImageDimensionError,
    ImageInputError,
    ImageJpegError,
    JpegRejectionReason,
)

__all__ = [
    "ContentTypeVerdict",
    "JpegInfo",
    "JPEG_MEDIA_TYPES",
    "UNDECLARED_MEDIA_TYPES",
    "MAX_IMAGE_WIDTH",
    "MAX_IMAGE_HEIGHT",
    "MAX_IMAGE_PIXELS",
    "SOF_MARKERS",
    "validate_image_content_type",
    "inspect_jpeg",
    "validate_acquired_image",
]

MAX_IMAGE_WIDTH = 20_000
MAX_IMAGE_HEIGHT = 20_000
MAX_IMAGE_PIXELS = 100_000_000

JPEG_MEDIA_TYPES = frozenset({"image/jpeg", "image/jpg", "image/pjpeg"})
# No usable declaration: the bytes alone decide.
UNDECLARED_MEDIA_TYPES = frozenset({"", "application/octet-stream"})

# Start-Of-Frame markers (ITU T.81 table B.1). Deliberately excluded from the C0..CF range:
# C4 DHT (Huffman tables), C8 JPG (reserved extension), CC DAC (arithmetic conditioning).
SOF_MARKERS = frozenset({0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF})
_LOSSLESS_SOF = frozenset({0xC3, 0xC7, 0xCB, 0xCF})
_SOI = 0xD8
_EOI = 0xD9
_SOS = 0xDA
_TEM = 0x01
_RST = frozenset(range(0xD0, 0xD8))


class ContentTypeVerdict(Enum):
    """Outcome of the Content-Type policy when it does not reject."""

    JPEG_DECLARED = "jpeg_declared"  # image/jpeg | image/jpg | image/pjpeg
    UNDECLARED = "undeclared"  # None | "" | application/octet-stream: bytes decide


def _check_dimensions(width: object, height: object) -> None:
    if type(width) is not int or type(height) is not int:
        raise ImageDimensionError(DimensionRejectionReason.NOT_EXACT_INT)
    if width <= 0:
        raise ImageDimensionError(DimensionRejectionReason.ZERO_WIDTH)
    if height <= 0:
        raise ImageDimensionError(DimensionRejectionReason.ZERO_HEIGHT)
    if width > MAX_IMAGE_WIDTH:
        raise ImageDimensionError(DimensionRejectionReason.WIDTH_TOO_LARGE)
    if height > MAX_IMAGE_HEIGHT:
        raise ImageDimensionError(DimensionRejectionReason.HEIGHT_TOO_LARGE)
    if width * height > MAX_IMAGE_PIXELS:
        raise ImageDimensionError(DimensionRejectionReason.TOO_MANY_PIXELS)


@dataclass(frozen=True, slots=True)
class JpegInfo:
    """What the structural walk established. Construction enforces the dimension caps:
    ``0 < width <= 20000``, ``0 < height <= 20000``, ``width * height <= 100_000_000``."""

    width: int
    height: int
    sof_marker: int

    def __post_init__(self) -> None:
        _check_dimensions(self.width, self.height)
        if type(self.sof_marker) is not int or self.sof_marker not in SOF_MARKERS:
            raise ImageJpegError(JpegRejectionReason.INVALID_SOF)


def validate_image_content_type(content_type: str | None) -> ContentTypeVerdict:
    """JPEG-only Content-Type policy. Case-insensitive; parameters after ``;`` are ignored.

    * ``image/jpeg`` / ``image/jpg`` / ``image/pjpeg`` -> ``JPEG_DECLARED``
    * ``None`` / empty / ``application/octet-stream`` -> ``UNDECLARED`` (the bytes decide)
    * anything else (``image/png``, ``image/webp``, ``text/html``, ``application/json`` ...)
      -> :class:`ImageContentTypeError` (``CONTENT_TYPE_MISMATCH``), even if the body is a
      valid JPEG.
    """
    if content_type is None:
        return ContentTypeVerdict.UNDECLARED
    if type(content_type) is not str:
        raise ImageInputError("content_type must be None or an exact str")
    media_type = content_type.split(";", 1)[0].strip().lower()
    if media_type in JPEG_MEDIA_TYPES:
        return ContentTypeVerdict.JPEG_DECLARED
    if media_type in UNDECLARED_MEDIA_TYPES:
        return ContentTypeVerdict.UNDECLARED
    raise ImageContentTypeError()


def _read_sof(data: bytes, start: int, end: int, marker: int) -> tuple[int, int]:
    """Frame header: P(1) Y(2) X(2) Nf(1) then Nf * (C, H/V, Tq). Returns (width, height)."""
    length = end - start
    if length < 6:
        raise ImageJpegError(JpegRejectionReason.INVALID_SOF)
    precision = data[start]
    height = (data[start + 1] << 8) | data[start + 2]
    width = (data[start + 3] << 8) | data[start + 4]
    components = data[start + 5]
    if components < 1 or length != 6 + 3 * components:
        raise ImageJpegError(JpegRejectionReason.INVALID_SOF)
    if marker in _LOSSLESS_SOF:
        if not 2 <= precision <= 16:
            raise ImageJpegError(JpegRejectionReason.INVALID_SOF)
    elif precision not in (8, 12):
        raise ImageJpegError(JpegRejectionReason.INVALID_SOF)
    return width, height


def _check_sos(data: bytes, start: int, end: int) -> None:
    """Scan header: Ns(1) then Ns * (Cs, Td/Ta) then Ss, Se, Ah/Al."""
    length = end - start
    if length < 1:
        raise ImageJpegError(JpegRejectionReason.INVALID_SOS)
    count = data[start]
    if not 1 <= count <= 4 or length != 1 + 2 * count + 3:
        raise ImageJpegError(JpegRejectionReason.INVALID_SOS)


def inspect_jpeg(content: bytes) -> JpegInfo:
    """Bounded structural validation of an in-memory JPEG; returns its frame dimensions.

    Single forward pass, O(len(content)), every index bounds-checked before use (no
    ``IndexError`` / ``struct.error`` can escape). Raises :class:`ImageJpegError` for a
    structural defect and :class:`ImageDimensionError` for out-of-range dimensions
    (dimensions are judged only after the structure is accepted).
    """
    if type(content) is not bytes:
        raise ImageInputError("content must be exact bytes")
    data = content
    size = len(data)
    if size < 2 or data[0] != 0xFF or data[1] != _SOI:
        raise ImageJpegError(JpegRejectionReason.NOT_JPEG)

    position = 2
    frame: tuple[int, int, int] | None = None  # (width, height, sof marker)
    while True:
        # Marker: 0xFF, optionally repeated as fill bytes (T.81 B.1.1.2), then a marker code.
        if position >= size:
            raise ImageJpegError(JpegRejectionReason.TRUNCATED)
        if data[position] != 0xFF:
            raise ImageJpegError(JpegRejectionReason.INVALID_MARKER)
        while position < size and data[position] == 0xFF:
            position += 1
        if position >= size:
            raise ImageJpegError(JpegRejectionReason.TRUNCATED)
        marker = data[position]
        position += 1

        if marker == _TEM or marker in _RST:
            continue  # standalone markers: no length, no payload
        if marker == 0x00 or marker == _SOI or 0x02 <= marker <= 0xBF:
            raise ImageJpegError(JpegRejectionReason.INVALID_MARKER)  # stuffed zero / repeated SOI / reserved
        if marker == _EOI:
            # EOI before any scan: there is no image data.
            raise ImageJpegError(
                JpegRejectionReason.MISSING_SOF if frame is None else JpegRejectionReason.MISSING_SOS
            )

        if position + 2 > size:
            raise ImageJpegError(JpegRejectionReason.TRUNCATED)
        length = (data[position] << 8) | data[position + 1]
        if length < 2:
            raise ImageJpegError(JpegRejectionReason.INVALID_SEGMENT_LENGTH)
        segment_start = position + 2
        segment_end = position + length
        if segment_end > size:
            raise ImageJpegError(JpegRejectionReason.SEGMENT_OUT_OF_BOUNDS)

        if marker in SOF_MARKERS:
            if frame is not None:
                raise ImageJpegError(JpegRejectionReason.MULTIPLE_SOF)
            width, height = _read_sof(data, segment_start, segment_end, marker)
            frame = (width, height, marker)
        elif marker == _SOS:
            if frame is None:
                raise ImageJpegError(JpegRejectionReason.MISSING_SOF)
            _check_sos(data, segment_start, segment_end)
            # Entropy-coded data follows; it is not scanned. The payload must end with EOI,
            # and the EOI must lie after the SOS header.
            if size - 2 < segment_end or data[size - 2] != 0xFF or data[size - 1] != _EOI:
                raise ImageJpegError(JpegRejectionReason.MISSING_EOI)
            break
        # Any other marker with a length (APPn, DQT, DHT, DAC, DRI, COM, JPG, JPGn, DNL,
        # DHP, EXP ...) is skipped by its declared length -- never scanned byte by byte.
        position = segment_end

    width, height, sof_marker = frame
    return JpegInfo(width=width, height=height, sof_marker=sof_marker)


def validate_acquired_image(content: bytes, content_type: str | None) -> JpegInfo:
    """Frozen order: exact types -> Content-Type policy -> JPEG structure -> dimensions.

    No HTTP, role, candidate or I/O involvement."""
    if type(content) is not bytes:
        raise ImageInputError("content must be exact bytes")
    if content_type is not None and type(content_type) is not str:
        raise ImageInputError("content_type must be None or an exact str")
    validate_image_content_type(content_type)
    return inspect_jpeg(content)
