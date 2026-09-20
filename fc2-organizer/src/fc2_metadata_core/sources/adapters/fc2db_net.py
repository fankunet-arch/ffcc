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
from fc2_metadata_core.sources.adapters._scan import (
    inner_until,
    iter_open_tags,
    open_tag_containing,
)
from fc2_metadata_core.sources.base import (
    SourceAdapter,
    require_canonical_number,
    transport_failure_result,
)

__all__ = ["Fc2dbNetAdapter", "parse_fc2db_work_page"]

# The heading text is "[FC2-PPV-N] Title" (ASCII digits only -- C0-01).
_HEADING_RE = re.compile(r"\[FC2-PPV-([0-9]{1,12})\]")
_MAX_HEADING_CHARS = 2000
_MAX_JSON_LD_CHARS = 200_000
_MAX_TAG_LINK_HITS = 400
_MAX_TAG_TEXT_CHARS = 500


def _heading(html_text: str) -> tuple[str, str] | None:
    """``(digits, title)`` from the first *closed* ``<h1>[FC2-PPV-N] ...</h1>``.

    An ``<h1>`` that is never closed within ``_MAX_HEADING_CHARS`` is ignored
    (it is "not found"), so a broken page can neither be read as a giant
    title nor make the scan super-linear.
    """
    for tag in iter_open_tags(html_text, "h1", limit=20):
        inner = inner_until(html_text, tag.end, "</h1>", _MAX_HEADING_CHARS)
        if inner is None:
            continue
        text = clean_text(inner)
        match = _HEADING_RE.match(text)
        if match is not None:
            return match.group(1), text[match.end() :].strip()
    return None


def _video_object(html_text: str) -> dict[str, Any]:
    """The page's schema.org ``VideoObject`` block, or ``{}``.

    Malformed (or absurdly nested) JSON-LD is ignored rather than fatal: it
    only carries optional fields, and number/title come from the visible
    ``<h1>``.
    """
    pos = 0
    for _ in range(10):
        hit = html_text.find("application/ld+json", pos)
        if hit < 0:
            break
        pos = hit + 1
        tag = open_tag_containing(html_text, hit)
        if tag is None or tag.name != "script":
            continue
        body = inner_until(html_text, tag.end, "</script>", _MAX_JSON_LD_CHARS)
        if body is None:
            continue
        try:
            data = json.loads(body)
        except (ValueError, RecursionError):
            continue
        if isinstance(data, dict) and data.get("@type") == "VideoObject":
            return data
    return {}


def _tags(html_text: str) -> tuple[str, ...]:
    """Texts of ``<a href=".../work-tags/...">`` links (bounded number of hits)."""
    found: list[str] = []
    pos = 0
    for _ in range(_MAX_TAG_LINK_HITS):
        hit = html_text.find("/work-tags/", pos)
        if hit < 0:
            break
        pos = hit + 1
        tag = open_tag_containing(html_text, hit)
        if tag is None or tag.name != "a":
            continue
        inner = inner_until(html_text, tag.end, "</a>", _MAX_TAG_TEXT_CHARS)
        if inner is not None:
            found.append(clean_text(inner))
    return unique_in_order(found)


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
    heading = _heading(html_text)
    if heading is None:
        return None, (SourceStatus.PARSE_ERROR, f"{source_id}: no closed '[FC2-PPV-N] title' heading found")
    page_digits, title = heading
    if page_digits != digits_of(number):
        return None, (
            SourceStatus.INVALID_RESPONSE,
            f"{source_id}: page is for FC2-{page_digits}, requested {number}",
        )
    if not title:
        return None, (SourceStatus.PARSE_ERROR, f"{source_id}: heading for {number} has an empty title")

    video = _video_object(html_text)
    actors = unique_in_order(_named(video.get("actor")))
    publisher_names = _named(video.get("publisher"))
    release = video.get("uploadDate") if isinstance(video.get("uploadDate"), str) else None
    thumb = video.get("thumbnailUrl") if isinstance(video.get("thumbnailUrl"), str) else None
    duration = video.get("duration") if isinstance(video.get("duration"), str) else None
    tags = _tags(html_text)

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
            return transport_failure_result(self.source_id, exc)

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
