"""FC2DB (``fc2db.net``) source adapter.

Evidence: ``docs/sources/SOURCE_VIABILITY_fc2db_net.md``.

Lookup is one plain GET of ``{base_url}/work/{digits}/`` -- a server-rendered
WordPress page that needs no login/cookie/JS. A missing work is a genuine
HTTP 404 page ("作品が削除されたか存在しません"), so 404 -> ``NOT_FOUND`` is
trustworthy here. The sibling domain ``fc2db.com`` sits behind a Cloudflare
challenge and is deliberately *not* used.

Extraction: ``<h1>[FC2-PPV-N] Title</h1>`` gives number + title; a
schema.org ``VideoObject`` JSON-LD block gives release/runtime/actors/
publisher/thumbnail; ``/work-tags/`` links give tags. Everything except
number/title is optional -- a page that only yields those two is still a
minimum-success ``SUCCESS``.
"""

from __future__ import annotations

import json
import re
from typing import Any

from fc2_metadata_core.http.client import HttpTransportError, SourceHttpClient
from fc2_metadata_core.models.source_result import SourceResult, SourceStatus
from fc2_metadata_core.sources.adapters._common import (
    classify_page_response,
    clean_text,
    digits_of,
    duration_to_minutes,
    failure_result,
    unique_in_order,
    with_field_sources,
)
from fc2_metadata_core.sources.base import (
    SourceAdapter,
    require_canonical_number,
    transport_error_result,
)

__all__ = ["Fc2dbNetAdapter", "parse_fc2db_work_page"]

_H1_RE = re.compile(r"<h1[^>]*>\s*\[FC2-PPV-(\d+)\]\s*(.*?)\s*</h1>", re.DOTALL)
_LD_JSON_RE = re.compile(
    r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', re.DOTALL | re.IGNORECASE
)
_TAG_LINK_RE = re.compile(r'<a[^>]+href="[^"]*/work-tags/[^"]*"[^>]*>(.*?)</a>', re.DOTALL)


def _video_object(html_text: str) -> dict[str, Any]:
    """The page's schema.org ``VideoObject`` block, or ``{}``.

    Malformed JSON-LD is ignored rather than fatal: it only carries optional
    fields, and number/title come from the visible ``<h1>``.
    """
    for raw in _LD_JSON_RE.findall(html_text):
        try:
            data = json.loads(raw)
        except ValueError:
            continue
        if isinstance(data, dict) and data.get("@type") == "VideoObject":
            return data
    return {}


def _named(items: Any) -> list[str]:
    if isinstance(items, dict):
        items = [items]
    if not isinstance(items, list):
        return []
    return [clean_text(i["name"]) for i in items if isinstance(i, dict) and isinstance(i.get("name"), str)]


def parse_fc2db_work_page(html_text: str, number: str, page_url: str, source_id: str = "fc2db_net"):
    """Parse a fc2db.net ``/work/N/`` page into ``NormalizedMetadata``.

    Returns ``(metadata, None)`` on success or ``(None, (status, detail))`` when
    the page is not the requested work / has no usable title.
    """
    match = _H1_RE.search(html_text)
    if match is None:
        return None, (SourceStatus.PARSE_ERROR, f"{source_id}: no '[FC2-PPV-N] title' heading found")
    page_digits, raw_title = match.group(1), match.group(2)
    if page_digits != digits_of(number):
        return None, (
            SourceStatus.INVALID_RESPONSE,
            f"{source_id}: page is for FC2-{page_digits}, requested {number}",
        )
    title = clean_text(raw_title)
    if not title:
        return None, (SourceStatus.PARSE_ERROR, f"{source_id}: heading for {number} has an empty title")

    video = _video_object(html_text)
    actors = unique_in_order(_named(video.get("actor")))
    publisher_names = _named(video.get("publisher"))
    release = video.get("uploadDate") if isinstance(video.get("uploadDate"), str) else None
    thumb = video.get("thumbnailUrl") if isinstance(video.get("thumbnailUrl"), str) else None
    duration = video.get("duration") if isinstance(video.get("duration"), str) else None
    tags = unique_in_order(clean_text(t) for t in _TAG_LINK_RE.findall(html_text))

    metadata = with_field_sources(
        source_id,
        number=number,
        title=title,
        publisher=publisher_names[0] if publisher_names else None,
        release=release,
        runtime=duration_to_minutes(duration),
        actors=actors,
        tags=tags,
        thumb_urls=(thumb,) if thumb else (),
        source_urls=(page_url,),
    )
    return metadata, None


class Fc2dbNetAdapter(SourceAdapter):
    source_id = "fc2db_net"
    display_name = "FC2DB (fc2db.net)"
    default_base_url = "https://fc2db.net"

    def _lookup_url(self, number: str) -> str:
        return f"{self.base_url.rstrip('/')}/work/{digits_of(number)}/"

    async def fetch(self, number: str, client: SourceHttpClient) -> SourceResult:
        require_canonical_number(number)
        url = self._lookup_url(number)
        try:
            response = await client.get(url)
        except HttpTransportError as exc:
            return transport_error_result(self.source_id, exc)

        failure = classify_page_response(self.source_id, number, response)
        if failure is not None:
            return failure

        metadata, error = parse_fc2db_work_page(response.text, number, url, self.source_id)
        if metadata is None:
            status, detail = error
            return failure_result(self.source_id, status, detail, elapsed_ms=response.elapsed_ms)
        return SourceResult(
            source_id=self.source_id,
            status=SourceStatus.SUCCESS,
            metadata=metadata,
            elapsed_ms=response.elapsed_ms,
        )
