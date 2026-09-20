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
from fc2_metadata_core.sources.base import (
    SourceAdapter,
    require_canonical_number,
    transport_error_result,
)

__all__ = ["Av123Adapter", "parse_av123_detail_page"]

_H1_RE = re.compile(
    r'<h1[^>]*class="[^"]*watch__title[^"]*"[^>]*>\s*FC2-PPV-(\d+)\s*[—–-]\s*(.*?)\s*</h1>',
    re.DOTALL,
)
_INFO_ROW_RE = re.compile(
    r'<div class="watch__info-row">\s*<dt>(.*?)</dt>\s*<dd[^>]*>(.*?)</dd>\s*</div>', re.DOTALL
)
_CHIP_RE = re.compile(r'<a[^>]*class="chip"[^>]*>(.*?)</a>', re.DOTALL)
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def parse_av123_detail_page(html_text: str, number: str, page_url: str, source_id: str = "av123"):
    """Parse a 123av ``/en/v/fc2-ppv-N`` page.

    Returns ``(metadata, None)`` or ``(None, (status, detail))``.
    """
    match = _H1_RE.search(html_text)
    if match is None:
        return None, (SourceStatus.PARSE_ERROR, f"{source_id}: no 'FC2-PPV-N — title' heading found")
    page_digits, raw_title = match.group(1), match.group(2)
    if page_digits != digits_of(number):
        return None, (
            SourceStatus.INVALID_RESPONSE,
            f"{source_id}: page is for FC2-{page_digits}, requested {number}",
        )
    title = clean_text(raw_title)
    if not title:
        return None, (SourceStatus.PARSE_ERROR, f"{source_id}: heading for {number} has an empty title")

    rows = {clean_text(k).lower(): v for k, v in _INFO_ROW_RE.findall(html_text)}
    release = clean_text(rows.get("release date", ""))
    tags = unique_in_order(clean_text(t) for t in _CHIP_RE.findall(rows.get("genres", "")))

    metadata = with_field_sources(
        source_id,
        number=number,
        title=title,
        release=release if _DATE_RE.match(release) else None,
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
            return transport_error_result(self.source_id, exc)

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
