"""123AV (``123av.com``) source adapter.

Evidence: ``docs/sources/SOURCE_VIABILITY_av123.md``.

Lookup is one plain GET of ``{base_url}/en/v/fc2-ppv-{digits}`` -- a
server-rendered detail page, no login/cookie/JS needed. A work the site does
not carry is a genuine HTTP 404. This site is complementary to FC2DB rather
than a copy of it: in live probing each carried works the other did not.

Extraction: ``<h1 class="watch__title">FC2-PPV-N — Title</h1>`` gives number
+ title; the "Details" ``<dl>`` gives release date, duration and genres. The
title is the site's English rendering, not the Japanese original; that is a
property of this source, recorded in its viability document, for Phase 3 to
weigh. The "Maker" row is always the generic bucket ``FC2`` (not the real
seller), so it is intentionally not mapped to ``studio``/``publisher``.
"""

from __future__ import annotations

import re

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
    class_tokens,
    inner_until,
    iter_class_tags,
    iter_open_tags,
    open_tag_at,
    parse_attrs,
)
from fc2_metadata_core.sources.base import (
    SourceAdapter,
    require_canonical_number,
    transport_failure_result,
)

__all__ = ["Av123Adapter", "parse_av123_detail_page"]

# "FC2-PPV-N — Title" (ASCII digits only -- C0-01); em dash, en dash or hyphen.
_HEADING_RE = re.compile(r"FC2-PPV-([0-9]{1,12})\s*+[—–-]\s*+")
_DATE_RE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
_MAX_HEADING_CHARS = 2000
_MAX_INFO_ROWS = 40
_MAX_ROW_CHARS = 3000
_MAX_CHIPS = 60
_MAX_CHIP_TEXT_CHARS = 300


def _heading(html_text: str) -> tuple[str, str] | None:
    """``(digits, title)`` from the closed ``<h1 class="watch__title">``."""
    for tag in iter_class_tags(html_text, "watch__title", limit=20):
        if tag.name != "h1":
            continue
        inner = inner_until(html_text, tag.end, "</h1>", _MAX_HEADING_CHARS)
        if inner is None:
            continue
        text = clean_text(inner)
        match = _HEADING_RE.match(text)
        if match is not None:
            return match.group(1), text[match.end() :].strip()
    return None


def _info_rows(html_text: str) -> dict[str, str]:
    """``{lower-cased label: raw <dd> inner html}`` from the Details ``<dl>``."""
    rows: dict[str, str] = {}
    for row in iter_class_tags(html_text, "watch__info-row", limit=_MAX_INFO_ROWS):
        window = html_text[row.end : row.end + _MAX_ROW_CHARS]
        label_end = window.find("</dt>")
        if label_end < 0:
            continue
        dd_start = window.find("<dd", label_end)
        if dd_start < 0:
            continue
        dd = open_tag_at(window, dd_start)
        if dd is None:
            continue
        value_end = window.find("</dd>", dd.end)
        if value_end < 0:
            continue
        label = clean_text(window[:label_end]).lower()
        rows.setdefault(label, window[dd.end : value_end])
    return rows


def _chips(value_html: str) -> tuple[str, ...]:
    found: list[str] = []
    for tag in iter_open_tags(value_html, "a", limit=_MAX_CHIPS):
        if "chip" not in class_tokens(parse_attrs(tag.attrs)):
            continue
        inner = inner_until(value_html, tag.end, "</a>", _MAX_CHIP_TEXT_CHARS)
        if inner is not None:
            found.append(clean_text(inner))
    return unique_in_order(found)


def parse_av123_detail_page(html_text: str, number: str, page_url: str, source_id: str = "av123"):
    """Parse a 123av ``/en/v/fc2-ppv-N`` page.

    Returns ``(metadata, None)`` or ``(None, (status, detail))``.
    """
    heading = _heading(html_text)
    if heading is None:
        return None, (SourceStatus.PARSE_ERROR, f"{source_id}: no closed 'FC2-PPV-N — title' heading found")
    page_digits, title = heading
    if page_digits != digits_of(number):
        return None, (
            SourceStatus.INVALID_RESPONSE,
            f"{source_id}: page is for FC2-{page_digits}, requested {number}",
        )
    if not title:
        return None, (SourceStatus.PARSE_ERROR, f"{source_id}: heading for {number} has an empty title")

    rows = _info_rows(html_text)
    release = clean_text(rows.get("release date", ""))
    tags = _chips(rows.get("genres", ""))

    metadata = with_field_sources(
        source_id,
        number=number,
        title=title,
        release=release if _DATE_RE.fullmatch(release) else None,
        runtime=duration_to_minutes(clean_text(rows.get("duration", ""))),
        tags=tags,
        source_urls=(page_url,),
    )
    return metadata, None


class Av123Adapter(SourceAdapter):
    source_id = "av123"
    display_name = "123AV (123av.com)"
    default_base_url = "https://123av.com"

    def _lookup_url(self, number: str) -> str:
        return f"{self.base_url.rstrip('/')}/en/v/fc2-ppv-{digits_of(number)}"

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

        metadata, error = parse_av123_detail_page(response.text, number, url, self.source_id)
        if metadata is None:
            status, detail = error
            return failure_result(self.source_id, status, detail, elapsed_ms=response.elapsed_ms)
        return SourceResult(
            source_id=self.source_id,
            status=SourceStatus.SUCCESS,
            metadata=metadata,
            elapsed_ms=response.elapsed_ms,
        )
