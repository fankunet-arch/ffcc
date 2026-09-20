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
reported as ``INVALID_RESPONSE`` rather than guessed around.

Total parse cost is bounded by construction (C0-02, C0-R1-01)
--------------------------------------------------------------
The parse makes **one** pass over the class attributes
(:func:`._scan.collect_class_hits`) and then gives each item a *fixed* number
of bounded lookups. Nothing is located per marker *occurrence* and no opening
tag is parsed twice, so the total is

    <= _MAX_CLASS_PROBES small anchored matches            (one pass)
     + _MAX_ITEMS x (a constant number of windows, each <= _MAX_ITEM_CHARS /
                     _MAX_TITLE_REGION_CHARS / MAX_TAG_CHARS)

whatever the page contains. The caps were sized from a real result page (8
items: 31 KB, ~780 chars and ~25 ``class`` attributes per item) with >= 5x
headroom for ``_MAX_ITEMS`` items, so they do not affect normal coverage.
If the scan stops at a cap (page longer than ``_MAX_SCAN_CHARS`` still holding
``class`` attributes, more than ``_MAX_CLASS_PROBES`` of them, or more than
``_MAX_ITEMS`` items) the parser has not seen the whole page, so "no exact
hit" is reported as ``INVALID_RESPONSE`` -- never as ``NOT_FOUND``.
"""

from __future__ import annotations

import html
from bisect import bisect_left
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
    collect_class_hits,
    first_open_tag,
    inner_until,
    open_tag_containing,
    parse_attrs,
)
from fc2_metadata_core.sources.base import (
    SourceAdapter,
    require_canonical_number,
    transport_error_result,
)

__all__ = ["JavdbAdapter", "parse_javdb_search_page"]

_WANTED_CLASS_TOKENS = frozenset({"movie-list", "empty-message", "item", "video-title", "meta"})
# Scan window and probe budget for the one class-attribute pass. A real result
# page is ~30 KB with ~1000 ``class`` words; these are >= 15x / >= 5x that.
_MAX_SCAN_CHARS = 512 * 1024
_MAX_CLASS_PROBES = 8000
_MAX_ITEMS = 200
_MAX_ITEM_CHARS = 8000
_MAX_TITLE_REGION_CHARS = 3000
_MAX_META_CHARS = 500
_MAX_CODE_CHARS = 40
# Tags examined per item for the anchor / cover lookups, and attributes parsed per tag.
_MAX_ANCHOR_TAGS = 3
_MAX_IMG_TAGS = 3
_MAX_ATTRS_PER_TAG = 16
_STRONG_CLOSE = "</strong>"


class _Item(NamedTuple):
    code: str
    title: str
    release: str | None
    cover: str | None
    detail_path: str | None


def _is_detail_path(value: str) -> bool:
    if not value.startswith("/v/") or not 4 <= len(value) <= 35:
        return False
    return value[3:].isascii() and value[3:].isalnum()


def _is_date(value: str) -> bool:
    return (
        len(value) == 10
        and value[4] == "-"
        and value[7] == "-"
        and value[:4].isascii()
        and (value[:4] + value[5:7] + value[8:]).isdigit()
        and (value[:4] + value[5:7] + value[8:]).isascii()
    )


def _first_between(sorted_positions: list[int], low: int, high: int) -> int | None:
    """First position ``p`` with ``low < p < high`` (positions are sorted)."""
    index = bisect_left(sorted_positions, low + 1)
    if index < len(sorted_positions) and sorted_positions[index] < high:
        return sorted_positions[index]
    return None


def _code_and_rest(inner: str) -> tuple[str, str] | None:
    """``(CODE, text after </strong>)`` from ``<strong>CODE</strong> ...``."""
    strong = first_open_tag(inner, "strong", start=0, end=len(inner))
    if strong is None:
        return None
    close = inner.find(_STRONG_CLOSE, strong.end, strong.end + _MAX_CODE_CHARS * 2)
    if close < 0:
        return None
    raw_code = inner[strong.end : close]
    if "<" in raw_code:
        return None
    code = clean_text(raw_code)
    if not code or len(code) > _MAX_CODE_CHARS:
        return None
    return code, inner[close + len(_STRONG_CLOSE) :]


def _parse_item(
    page: str,
    item_pos: int,
    region_end: int,
    title_positions: list[int],
    meta_positions: list[int],
) -> _Item | None:
    """One result item, or ``None`` if no candidate number can be read from it.

    A fixed number of bounded lookups; each opening tag is parsed at most once.
    """
    title_pos = _first_between(title_positions, item_pos, region_end)
    if title_pos is None:
        return None
    title_tag = open_tag_containing(page, title_pos)
    if title_tag is None:
        return None
    inner = inner_until(page, title_tag.end, "</div>", _MAX_TITLE_REGION_CHARS)
    if inner is None:
        return None
    parsed = _code_and_rest(inner)
    if parsed is None:
        return None
    code, rest = parsed
    text_title = clean_text(rest)

    href: str | None = None
    attr_title = ""
    scan_from = item_pos
    for _ in range(_MAX_ANCHOR_TAGS):
        anchor = first_open_tag(page, "a", start=scan_from, end=region_end)
        if anchor is None:
            break
        attrs = parse_attrs(anchor.attrs, max_attrs=_MAX_ATTRS_PER_TAG)
        if _is_detail_path(attrs.get("href", "")):
            href = attrs["href"]
            # Historical behaviour kept as-is (double unescape is a tracked
            # LOW backlog item, P2-R-10, not part of C0 / C0-R1).
            attr_title = clean_text(html.unescape(attrs.get("title", "")))
            break
        scan_from = anchor.end

    cover: str | None = None
    scan_from = item_pos
    for _ in range(_MAX_IMG_TAGS):
        img = first_open_tag(page, "img", start=scan_from, end=region_end)
        if img is None:
            break
        src = parse_attrs(img.attrs, max_attrs=_MAX_ATTRS_PER_TAG).get("src", "")
        if src.startswith(("http://", "https://")):
            cover = src
            break
        scan_from = img.end

    release: str | None = None
    meta_pos = _first_between(meta_positions, item_pos, region_end)
    if meta_pos is not None:
        meta_tag = open_tag_containing(page, meta_pos)
        if meta_tag is not None:
            meta_inner = inner_until(page, meta_tag.end, "</div>", _MAX_META_CHARS)
            if meta_inner is not None:
                candidate = clean_text(meta_inner)
                release = candidate if _is_date(candidate) else None

    return _Item(code, attr_title or text_title, release, cover, href)


def parse_javdb_search_page(
    html_text: str, number: str, base_url: str, source_id: str = "javdb"
):
    """Parse a JavDB search page for the exact ``number`` (see module docstring).

    Returns ``(metadata, None)`` on an exact hit, else ``(None, (status, detail))``.
    """
    hits, truncated = collect_class_hits(
        html_text,
        _WANTED_CLASS_TOKENS,
        max_chars=_MAX_SCAN_CHARS,
        max_probes=_MAX_CLASS_PROBES,
    )
    positions: dict[str, list[int]] = {token: [] for token in _WANTED_CLASS_TOKENS}
    for hit in hits:
        for token in hit.tokens:
            positions[token].append(hit.pos)

    if not positions["movie-list"]:
        if positions["empty-message"]:
            return None, (SourceStatus.NOT_FOUND, f"{source_id}: search for {number} returned no results")
        suffix = " (scan budget reached before the whole page was seen)" if truncated else ""
        return None, (
            SourceStatus.INVALID_RESPONSE,
            f"{source_id}: page has neither a result list nor an empty-result marker{suffix}",
        )

    list_pos = positions["movie-list"][0]
    item_positions = [pos for pos in positions["item"] if pos > list_pos]
    over_item_cap = len(item_positions) > _MAX_ITEMS
    item_positions = item_positions[:_MAX_ITEMS]

    candidates: list[_Item] = []
    for index, item_pos in enumerate(item_positions):
        next_pos = item_positions[index + 1] if index + 1 < len(item_positions) else len(html_text)
        region_end = min(next_pos, item_pos + _MAX_ITEM_CHARS)
        item = _parse_item(
            html_text, item_pos, region_end, positions["video-title"], positions["meta"]
        )
        if item is not None:
            candidates.append(item)

    if not candidates:
        return None, (
            SourceStatus.INVALID_RESPONSE,
            f"{source_id}: result list present but no candidate number could be parsed "
            f"from {len(item_positions)} item element(s) (layout drift?)",
        )

    exact = next((c for c in candidates if c.code == number), None)
    if exact is None:
        if truncated or over_item_cap:
            return None, (
                SourceStatus.INVALID_RESPONSE,
                f"{source_id}: {len(candidates)} candidate number(s) parsed, none exact, but the "
                "scan budget was reached before the whole page was seen; cannot conclude not found",
            )
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
