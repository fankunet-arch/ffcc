"""JavDB (``javdb.com``) source adapter -- public search listing only.

Evidence: ``docs/sources/SOURCE_VIABILITY_javdb.md``.

Lookup is one plain GET of ``{base_url}/search?q=FC2-PPV-{digits}``. The
*search listing* is public: it needs no login, cookie, or JS, and each hit
carries number + title + release date + cover thumbnail. JavDB's **detail**
pages (``/v/<id>``), by contrast, redirect to ``/login`` -- so this adapter
deliberately never requests them, and actors/tags/etc. are therefore not
available from this source (partial-safe metadata).

The search is *fuzzy*: searching ``4824605`` also returns ``FC2-1824605`` and
``FC2-4724605``. So only the hit whose number equals the requested one
exactly is accepted, never a "close enough" hit.

Failure semantics (frozen at Phase 3 Entry C0-03; Phase 3 treats ``NOT_FOUND``
as a *normal coverage gap*, so a layout change must never masquerade as one):

=====================================================  =====================
Page                                                   Result
=====================================================  =====================
result list, >=1 candidate number parsed, one is the   ``SUCCESS``
requested number and has a title
result list, >=1 candidate number parsed, none is the  ``NOT_FOUND``
requested number (fuzzy near-misses only)
the requested number is identified but its title is    ``PARSE_ERROR``
missing/blank
zero-result page (explicit ``empty-message`` block)    ``NOT_FOUND``
result list present but **no** candidate number can    ``INVALID_RESPONSE``
be parsed out of it, or neither a result list nor an
``empty-message`` block is found (layout drift)
=====================================================  =====================

A *candidate number* is a ``<strong>CODE</strong>`` inside the item's
``video-title`` element (any studio code, not only FC2: a search for an FC2
number legitimately also lists other studios' items). The ``N`` reported in
``NOT_FOUND`` details is the number of candidate numbers actually parsed, not
a count of HTML chunks.

Matching is by whole CSS class token, so extra classes (``class="item x"``,
``class="video-title is-x"``) do not break it; a *renamed* class does, and is
reported as ``INVALID_RESPONSE`` rather than guessed around. All scanning goes
through :mod:`._scan` (bounded cost, C0-02).
"""

from __future__ import annotations

import html
import re
from typing import NamedTuple

from fc2_metadata_core.http.client import HttpTransportError, SourceHttpClient
from fc2_metadata_core.models.source_result import SourceResult, SourceStatus
from fc2_metadata_core.sources.adapters._common import (
    classify_page_response,
    clean_text,
    digits_of,
    failure_result,
    with_field_sources,
)
from fc2_metadata_core.sources.adapters._scan import (
    inner_until,
    iter_class_tags,
    iter_open_tags,
    parse_attrs,
)
from fc2_metadata_core.sources.base import (
    SourceAdapter,
    require_canonical_number,
    transport_error_result,
)

__all__ = ["JavdbAdapter", "parse_javdb_search_page"]

_MAX_ITEMS = 200
_MAX_ITEM_CHARS = 8000
_MAX_TITLE_REGION_CHARS = 3000
_MAX_META_CHARS = 500

# <strong>CODE</strong>: the item's number. Bounded code length; lazy body and
# the trailing \s*+ cannot overlap because the body excludes '<' and is capped.
_STRONG_RE = re.compile(r"<strong[^>]*+>\s*+([^<]{1,40}?)\s*+</strong>")
_DATE_RE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
_DETAIL_PATH_RE = re.compile(r"/v/[A-Za-z0-9]{1,32}")


class _Item(NamedTuple):
    code: str
    title: str
    release: str | None
    cover: str | None
    detail_path: str | None


def _parse_item(region: str) -> _Item | None:
    """One result item, or ``None`` if no candidate number can be read from it."""
    title_tag = next(iter_class_tags(region, "video-title", limit=20), None)
    if title_tag is None:
        return None
    inner = inner_until(region, title_tag.end, "</div>", _MAX_TITLE_REGION_CHARS)
    if inner is None:
        return None
    strong = _STRONG_RE.search(inner)
    if strong is None:
        return None
    code = clean_text(strong.group(1))
    if not code:
        return None
    text_title = clean_text(inner[strong.end() :])

    href: str | None = None
    attr_title = ""
    for anchor in iter_open_tags(region, "a", limit=10):
        attrs = parse_attrs(anchor.attrs)
        if _DETAIL_PATH_RE.fullmatch(attrs.get("href", "")):
            href = attrs["href"]
            # Historical behaviour kept as-is (double unescape is a tracked
            # LOW backlog item, P2-R-10, not part of C0).
            attr_title = clean_text(html.unescape(attrs.get("title", "")))
            break

    cover: str | None = None
    for img in iter_open_tags(region, "img", limit=5):
        src = parse_attrs(img.attrs).get("src", "")
        if src.startswith(("http://", "https://")):
            cover = src
            break

    release: str | None = None
    meta_tag = next(iter_class_tags(region, "meta", limit=20), None)
    if meta_tag is not None:
        meta_inner = inner_until(region, meta_tag.end, "</div>", _MAX_META_CHARS)
        if meta_inner is not None:
            candidate = clean_text(meta_inner)
            release = candidate if _DATE_RE.fullmatch(candidate) else None

    return _Item(code, attr_title or text_title, release, cover, href)


def parse_javdb_search_page(
    html_text: str, number: str, base_url: str, source_id: str = "javdb"
):
    """Parse a JavDB search page for the exact ``number`` (see module docstring).

    Returns ``(metadata, None)`` on an exact hit, else ``(None, (status, detail))``.
    """
    list_tag = next(iter_class_tags(html_text, "movie-list", limit=50), None)
    if list_tag is None:
        if next(iter_class_tags(html_text, "empty-message", limit=50), None) is not None:
            return None, (SourceStatus.NOT_FOUND, f"{source_id}: search for {number} returned no results")
        return None, (
            SourceStatus.INVALID_RESPONSE,
            f"{source_id}: page has neither a result list nor an empty-result marker",
        )

    item_tags = []
    for tag in iter_class_tags(html_text, "item", start=list_tag.end):
        item_tags.append(tag)
        if len(item_tags) >= _MAX_ITEMS:
            break

    candidates: list[_Item] = []
    for index, tag in enumerate(item_tags):
        end = item_tags[index + 1].start if index + 1 < len(item_tags) else len(html_text)
        region = html_text[tag.end : min(end, tag.end + _MAX_ITEM_CHARS)]
        item = _parse_item(region)
        if item is not None:
            candidates.append(item)

    if not candidates:
        return None, (
            SourceStatus.INVALID_RESPONSE,
            f"{source_id}: result list present but no candidate number could be parsed "
            f"from {len(item_tags)} item element(s) (layout drift?)",
        )

    exact = next((c for c in candidates if c.code == number), None)
    if exact is None:
        return None, (
            SourceStatus.NOT_FOUND,
            f"{source_id}: search for {number} listed {len(candidates)} other number(s), none exact",
        )
    if not exact.title:
        return None, (SourceStatus.PARSE_ERROR, f"{source_id}: hit for {number} has an empty title")

    metadata = with_field_sources(
        source_id,
        number=number,
        title=exact.title,
        release=exact.release,
        thumb_urls=(exact.cover,) if exact.cover else (),
        source_urls=(f"{base_url.rstrip('/')}{exact.detail_path}",) if exact.detail_path else (),
        external_ids={source_id: exact.detail_path.rsplit("/", 1)[1]} if exact.detail_path else {},
    )
    return metadata, None


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
