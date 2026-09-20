"""Small helpers shared by the concrete, real-site adapters.

Everything here is provider-agnostic. Parsing of a specific provider's page
layout stays in that provider's own module -- this file only holds the parts
that would otherwise be copy-pasted three times (HTTP-status/anti-bot
classification, HTML text clean-up, duration parsing, ``field_sources``
bookkeeping), so every adapter reports the same failure with the same
``SourceStatus``.
"""

from __future__ import annotations

import html
import re
from typing import Iterable

from fc2_metadata_core.http.client import HttpResponse
from fc2_metadata_core.models.metadata import NormalizedMetadata
from fc2_metadata_core.models.source_result import SourceErrorKind, SourceResult, SourceStatus
from fc2_metadata_core.sources.base import classify_http_status

__all__ = [
    "failure_result",
    "classify_page_response",
    "clean_text",
    "duration_to_minutes",
    "digits_of",
    "with_field_sources",
    "unique_in_order",
]

# ``[^<>]*`` (not ``[^>]+``): a tag body can never contain another '<', so each
# attempt stops at the next '<' or '>' and a string full of stray '<' stays
# linear instead of rescanning to the end once per '<'.
_TAG_RE = re.compile(r"<[^<>]*+>")
_WS_RE = re.compile(r"\s+")
# "55:23" -> mm:ss, "1:02:03" -> h:mm:ss. Providers never show days. ASCII
# digits only ([0-9], not \d): int() would happily accept Arabic-Indic digits.
_DURATION_RE = re.compile(r"(?:([0-9]{1,2}):)?([0-9]{1,3}):([0-9]{2})")
_MAX_DURATION_TEXT_CHARS = 64

# Only ever reads the first couple of KB: a Cloudflare interstitial is a tiny
# page whose <title> is this literal, whereas a real metadata page that merely
# *mentions* the phrase deep in its body must not be misread as blocked.
_CHALLENGE_TITLE_RE = re.compile(
    r"<title[^>]*+>\s*+(just a moment|attention required)", re.IGNORECASE
)


def failure_result(
    source_id: str,
    status: SourceStatus,
    detail: str,
    *,
    elapsed_ms: float,
    error_kind: SourceErrorKind | None = None,
) -> SourceResult:
    """A non-success ``SourceResult``.

    ``error_kind`` refines ``status`` (Phase 3 C2, e.g. ``HTTP_SERVER_ERROR`` for
    an ``INVALID_RESPONSE``); omitted, it is the generic kind matching ``status``.
    ``SourceResult`` itself rejects a kind that does not belong to ``status``.
    """
    return SourceResult(
        source_id=source_id,
        status=status,
        metadata=None,
        elapsed_ms=elapsed_ms,
        error_kind=error_kind if error_kind is not None else SourceErrorKind(status.value),
        error_detail=detail,
    )


def classify_page_response(
    source_id: str,
    number: str,
    response: HttpResponse,
    *,
    blocked_url_markers: tuple[str, ...] = (),
) -> SourceResult | None:
    """Return a failure ``SourceResult`` unless ``response`` is a usable page.

    ``None`` means "a normal 200 page: go on and parse it". Never returns a
    success -- HTTP 200 alone never proves a lookup worked.

    - 404 -> ``NOT_FOUND``; 429 -> ``RATE_LIMITED``; 403 -> ``BLOCKED``
    - a Cloudflare-style interstitial (``cf-mitigated: challenge`` header, or
      the well-known "Just a moment..." page even under a 200) -> ``BLOCKED``.
      Nothing here tries to solve or bypass it.
    - a redirect that ended on one of ``blocked_url_markers`` (e.g. a login or
      age-verification page) -> ``BLOCKED``: the site wants a private
      session we deliberately do not have.
    - HTTP 500-599 -> ``INVALID_RESPONSE`` with ``error_kind=HTTP_SERVER_ERROR``:
      still an operational failure for aggregation, but structurally a *server-side*
      failure, the only ``INVALID_RESPONSE`` the retry policy treats as transient
      (closes Phase 2 review finding P2-R-12);
    - any other non-200 -> generic ``INVALID_RESPONSE`` (not retried).
    """
    elapsed = response.elapsed_ms
    lowered_headers = {k.lower(): v for k, v in response.headers.items()}

    if lowered_headers.get("cf-mitigated", "").lower() == "challenge":
        return failure_result(
            source_id,
            SourceStatus.BLOCKED,
            f"{source_id}: anti-bot challenge (cf-mitigated) for {number}; not bypassed",
            elapsed_ms=elapsed,
        )

    for marker in blocked_url_markers:
        if marker in response.url:
            return failure_result(
                source_id,
                SourceStatus.BLOCKED,
                f"{source_id}: request for {number} ended on {response.url!r} "
                "(login/verification required)",
                elapsed_ms=elapsed,
            )

    hinted = classify_http_status(response.status_code)
    if hinted is not None:
        return failure_result(
            source_id,
            hinted,
            f"{source_id}: HTTP {response.status_code} for {number}",
            elapsed_ms=elapsed,
        )

    if 500 <= response.status_code <= 599:
        return failure_result(
            source_id,
            SourceStatus.INVALID_RESPONSE,
            f"{source_id}: HTTP {response.status_code} server error for {number}",
            elapsed_ms=elapsed,
            error_kind=SourceErrorKind.HTTP_SERVER_ERROR,
        )

    if response.status_code != 200:
        return failure_result(
            source_id,
            SourceStatus.INVALID_RESPONSE,
            f"{source_id}: unexpected HTTP {response.status_code} for {number}",
            elapsed_ms=elapsed,
        )

    if _CHALLENGE_TITLE_RE.search(response.text[:4000]):
        return failure_result(
            source_id,
            SourceStatus.BLOCKED,
            f"{source_id}: anti-bot interstitial served with HTTP 200 for {number}",
            elapsed_ms=elapsed,
        )
    return None


def clean_text(fragment: str) -> str:
    """Drop tags, decode entities, collapse whitespace."""
    return _WS_RE.sub(" ", html.unescape(_TAG_RE.sub(" ", fragment))).strip()


def duration_to_minutes(text: str | None) -> int | None:
    """Clock duration -> ``NormalizedMetadata.runtime`` (whole minutes).

    ``"55:23"`` -> 55, ``"1:02:03"`` -> 62, ``"55:59"`` -> 55: the seconds are
    **truncated**, never rounded (unit frozen at Phase 3 Entry C0-04, see
    ``docs/specifications/FC2_METADATA_CORE_CONTRACT.md``; Kodi's ``<runtime>``
    is minutes only). Anything not shaped like an ASCII clock duration ->
    ``None`` (a missing runtime is a partial field, never an error).
    """
    if not text:
        return None
    if len(text) > _MAX_DURATION_TEXT_CHARS:  # checked before strip(): no copy of a huge string
        return None
    match = _DURATION_RE.fullmatch(text.strip())
    if match is None:
        return None
    hours_text, minutes_text, seconds_text = match.groups()
    if int(seconds_text) > 59:
        return None  # "55:75" is not a clock duration
    if hours_text is not None and (len(minutes_text) != 2 or int(minutes_text) > 59):
        return None  # h:mm:ss needs two-digit minutes below 60 ("1:2:03", "1:75:00")
    return int(hours_text or 0) * 60 + int(minutes_text)


def digits_of(number: str) -> str:
    """``"FC2-4825061"`` -> ``"4825061"`` (caller already canonicalized)."""
    return number.split("-", 1)[1]


def with_field_sources(source_id: str, **fields: object) -> NormalizedMetadata:
    """Build ``NormalizedMetadata`` attributing every populated field to ``source_id``.

    ``field_sources`` is only recorded for fields that actually carry a value,
    so Phase 3's aggregation can trust "this field came from source X" without
    having to re-check emptiness.
    """
    populated: list[str] = []
    for name, value in fields.items():
        if name in ("field_sources", "external_ids"):
            continue
        if value not in (None, "", (), [], {}):
            populated.append(name)
    fields["field_sources"] = {name: (source_id,) for name in populated}
    return NormalizedMetadata(**fields)  # type: ignore[arg-type]


def unique_in_order(values: Iterable[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            out.append(value)
    return tuple(out)
