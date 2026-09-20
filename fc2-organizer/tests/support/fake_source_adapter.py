"""A minimal, fully offline ``SourceAdapter`` test double.

Not a real production source -- it exists only to exercise the
``SourceAdapter``/``SourceRegistry`` framework itself (canonical-number
boundary, ``base_url`` override, HTTP-status-to-``SourceStatus`` mapping,
``field_sources`` attribution) without depending on any adopted adapter's
real parsing logic. Its "page format" is a trivial ``TITLE: ...`` text line
invented for this test double only.
"""

from __future__ import annotations

from fc2_metadata_core.http.client import HttpTransportError, SourceHttpClient
from fc2_metadata_core.models.metadata import NormalizedMetadata
from fc2_metadata_core.models.source_result import SourceErrorKind, SourceResult, SourceStatus
from fc2_metadata_core.sources.base import (
    SourceAdapter,
    classify_http_status,
    require_canonical_number,
    transport_error_result,
)

__all__ = ["FakeSourceAdapter"]


class FakeSourceAdapter(SourceAdapter):
    source_id = "fake_source"
    display_name = "Fake Source (test double)"
    default_base_url = "https://fake-source.invalid"

    def _lookup_url(self, number: str) -> str:
        return f"{self.base_url}/lookup/{number}"

    async def fetch(self, number: str, client: SourceHttpClient) -> SourceResult:
        require_canonical_number(number)
        url = self._lookup_url(number)
        try:
            response = await client.get(url)
        except HttpTransportError as exc:
            return transport_error_result(self.source_id, exc)

        hinted_status = classify_http_status(response.status_code)
        if hinted_status is SourceStatus.NOT_FOUND:
            return SourceResult(
                source_id=self.source_id,
                status=SourceStatus.NOT_FOUND,
                metadata=None,
                elapsed_ms=response.elapsed_ms,
                error_kind=SourceErrorKind.NOT_FOUND,
                error_detail=f"{number} not found on {self.source_id} (HTTP 404)",
            )
        if hinted_status is SourceStatus.BLOCKED:
            return SourceResult(
                source_id=self.source_id,
                status=SourceStatus.BLOCKED,
                metadata=None,
                elapsed_ms=response.elapsed_ms,
                error_kind=SourceErrorKind.BLOCKED,
                error_detail=f"{self.source_id} returned HTTP 403 (blocked)",
            )
        if hinted_status is SourceStatus.RATE_LIMITED:
            return SourceResult(
                source_id=self.source_id,
                status=SourceStatus.RATE_LIMITED,
                metadata=None,
                elapsed_ms=response.elapsed_ms,
                error_kind=SourceErrorKind.RATE_LIMITED,
                error_detail=f"{self.source_id} returned HTTP 429 (rate limited)",
            )
        if response.status_code != 200:
            return SourceResult(
                source_id=self.source_id,
                status=SourceStatus.INVALID_RESPONSE,
                metadata=None,
                elapsed_ms=response.elapsed_ms,
                error_kind=SourceErrorKind.INVALID_RESPONSE,
                error_detail=f"{self.source_id} returned unexpected HTTP {response.status_code}",
            )

        title: str | None = None
        for line in response.text.splitlines():
            if line.startswith("TITLE:"):
                title = line[len("TITLE:") :].strip()
                break

        if not title:
            return SourceResult(
                source_id=self.source_id,
                status=SourceStatus.PARSE_ERROR,
                metadata=None,
                elapsed_ms=response.elapsed_ms,
                error_kind=SourceErrorKind.PARSE_ERROR,
                error_detail=f"{self.source_id}: no TITLE line found in response body",
            )

        metadata = NormalizedMetadata(
            number=number,
            title=title,
            field_sources={
                "number": (self.source_id,),
                "title": (self.source_id,),
            },
        )
        return SourceResult(
            source_id=self.source_id,
            status=SourceStatus.SUCCESS,
            metadata=metadata,
            elapsed_ms=response.elapsed_ms,
        )
