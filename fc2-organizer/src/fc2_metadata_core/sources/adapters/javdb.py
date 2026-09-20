"""JavDB (``javdb.com``) source adapter -- public search listing only.

Evidence: ``docs/sources/SOURCE_VIABILITY_javdb.md``.

Lookup is one plain GET of ``{base_url}/search?q=FC2-PPV-{digits}``. The
*search listing* is public: it needs no login, cookie, or JS, and each hit
carries number + title + release date + cover thumbnail. JavDB's **detail**
pages (``/v/<id>``), by contrast, redirect to ``/login`` -- so this adapter
deliberately never requests them, and actors/tags/etc. are therefore not
available from this source (partial-safe metadata).

The search is *fuzzy*: searching ``4824605`` also returns ``FC2-1824605`` and
``FC2-4724605``. So the hit whose number equals the requested one exactly is
picked; if none does, that is ``NOT_FOUND`` (the listing itself was
readable), never a "close enough" hit. A zero-result page carries an explicit
``empty-message`` block; a page with *neither* a result list nor that block is
not a JavDB search page and is reported as ``INVALID_RESPONSE`` rather than
guessed at.
"""

from __future__ import annotations

import html
import re

from fc2_metadata_core.http.client import HttpTransportError, SourceHttpClient
from fc2_metadata_core.models.source_result import SourceResult, SourceStatus
from fc2_metadata_core.sources.adapters._common import (
    classify_page_response,
    clean_text,
    digits_of,
    failure_result,
    with_field_sources,
)
from fc2_metadata_core.sources.base import (
    SourceAdapter,
    require_canonical_number,
    transport_error_result,
)

__all__ = ["JavdbAdapter", "parse_javdb_search_page"]

_ITEM_SPLIT_RE = re.compile(r'<div class="item">')
_HREF_RE = re.compile(r'<a href="(/v/[A-Za-z0-9]+)"')
_TITLE_ATTR_RE = re.compile(r'<a href="/v/[A-Za-z0-9]+"[^>]*\stitle="([^"]*)"')
_VIDEO_TITLE_RE = re.compile(
    r'<div class="video-title"><strong>(FC2-\d+)</strong>\s*(.*?)</div>', re.DOTALL
)
_COVER_RE = re.compile(r'<img[^>]+src="(https?://[^"]+)"')
_META_RE = re.compile(r'<div class="meta">\s*(.*?)\s*</div>', re.DOTALL)
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def parse_javdb_search_page(
    html_text: str, number: str, base_url: str, source_id: str = "javdb"
):
    """Parse a JavDB search page for the exact ``number``.

    Returns ``(metadata, None)`` on an exact hit, else
    ``(None, (status, detail))``.
    """
    has_list = 'class="movie-list' in html_text
    if not has_list:
        if 'class="empty-message"' in html_text:
            return None, (SourceStatus.NOT_FOUND, f"{source_id}: search for {number} returned no results")
        return None, (
            SourceStatus.INVALID_RESPONSE,
            f"{source_id}: page has neither a result list nor an empty-result marker",
        )

    chunks = _ITEM_SPLIT_RE.split(html_text)[1:]
    for chunk in chunks:
        video_title = _VIDEO_TITLE_RE.search(chunk)
        if video_title is None or video_title.group(1) != number:
            continue

        title_attr = _TITLE_ATTR_RE.search(chunk)
        title = clean_text(html.unescape(title_attr.group(1))) if title_attr else ""
        if not title:
            title = clean_text(video_title.group(2))
        if not title:
            return None, (SourceStatus.PARSE_ERROR, f"{source_id}: hit for {number} has an empty title")

        href = _HREF_RE.search(chunk)
        cover = _COVER_RE.search(chunk)
        meta = _META_RE.search(chunk)
        release = clean_text(meta.group(1)) if meta else ""
        detail_path = href.group(1) if href else None

        metadata = with_field_sources(
            source_id,
            number=number,
            title=title,
            release=release if _DATE_RE.match(release) else None,
            thumb_urls=(cover.group(1),) if cover else (),
            source_urls=(f"{base_url.rstrip('/')}{detail_path}",) if detail_path else (),
            external_ids={source_id: detail_path.rsplit("/", 1)[1]} if detail_path else {},
        )
        return metadata, None

    return None, (
        SourceStatus.NOT_FOUND,
        f"{source_id}: search for {number} listed {len(chunks)} other number(s), none exact",
    )


class JavdbAdapter(SourceAdapter):
    source_id = "javdb"
    display_name = "JavDB (javdb.com, public search listing)"
    default_base_url = "https://javdb.com"

    def _lookup_url(self, number: str) -> str:
        return f"{self.base_url.rstrip('/')}/search?q=FC2-PPV-{digits_of(number)}"

    async def fetch(self, number: str, client: SourceHttpClient) -> SourceResult:
        require_canonical_number(number)
        url = self._lookup_url(number)
        try:
            response = await client.get(url)
        except HttpTransportError as exc:
            return transport_error_result(self.source_id, exc)

        failure = classify_page_response(
            self.source_id, number, response, blocked_url_markers=("/login",)
        )
        if failure is not None:
            return failure

        metadata, error = parse_javdb_search_page(
            response.text, number, self.base_url, self.source_id
        )
        if metadata is None:
            status, detail = error
            return failure_result(self.source_id, status, detail, elapsed_ms=response.elapsed_ms)
        return SourceResult(
            source_id=self.source_id,
            status=SourceStatus.SUCCESS,
            metadata=metadata,
            elapsed_ms=response.elapsed_ms,
        )
