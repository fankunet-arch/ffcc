"""Builders for the P4-C6 substep-2 mapping / single-artifact tests."""

from __future__ import annotations

import hashlib
import os

from fc2_metadata_core.models import NormalizedMetadata
from fc2_organizer.discovery import DiscoveredMediaItem
from fc2_organizer.images import AcquiredImage, ImageAcquisitionResult, ImageRole
from fc2_organizer.planning import OrganizePlan, build_organize_plan

NUMBER = "FC2-1234567"
NFO_TEXT = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
    "<movie>\n  <title>Example Title</title>\n</movie>\n"
)


def make_plan(library_root: str) -> OrganizePlan:
    source = os.path.join(library_root, "downloads", "random-name.MP4")
    item = DiscoveredMediaItem(index=0, source_path=source, relative_path="random-name.MP4",
                               extension=".MP4", size=123)
    metadata = NormalizedMetadata(number=NUMBER, title="Example Title")
    return build_organize_plan(item, NUMBER, metadata, library_root)


def jpeg(tag: bytes) -> bytes:
    return b"\xff\xd8\xff\xe0" + tag + b"\x00\x01\x02\xff" + b"\xff\xd9"


def image(role: ImageRole, content: bytes, candidate_index: int = 0) -> AcquiredImage:
    return AcquiredImage(role=role, candidate_index=candidate_index, content=content, width=10, height=20,
                         size_bytes=len(content), sha256=hashlib.sha256(content).hexdigest())


def full_images(extra_count: int = 3) -> ImageAcquisitionResult:
    return ImageAcquisitionResult(
        poster=image(ImageRole.POSTER, jpeg(b"poster")),
        fanart=image(ImageRole.FANART, jpeg(b"fanart")),
        thumb=image(ImageRole.THUMB, jpeg(b"thumb")),
        extrafanart=tuple(image(ImageRole.EXTRAFANART, jpeg(b"extra-%d" % i), i) for i in range(extra_count)),
    )
