#!/usr/bin/env python3
"""Phase 2 live source probe tool.

Two subcommands:

``raw`` -- pre-adapter candidate research. Performs a single real HTTP GET
per URL with no parsing/adapter involved at all, and prints/records the raw
evidence (status code, final URL after redirects, a few non-sensitive
headers, and a crude Cloudflare/anti-bot heuristic). This is what backs
``docs/sources/SOURCE_VIABILITY_*.md`` -- Phase 2 requires *this* kind of
real request before any adapter is written for a candidate, never a search
engine snippet or a memory-based guess.

``adapter`` -- post-ADOPT verification. Runs an actually-registered
``SourceAdapter`` end to end (through the real HTTP transport) against one
or more canonical FC2 numbers, and records both the adapter's own
``SourceResult`` outcome and the raw HTTP status/final URL of the request
that produced it. This is the evidence a source needs to count as
Phase 2 VERIFIED (see spec section 11: real HTTP request + real adapter
execution + >=2 known-valid IDs returning SUCCESS with number+title).

Usage
-----
    python3 tools/probe_sources.py raw https://example.com/FC2-1234567 ...
    python3 tools/probe_sources.py adapter --source SOURCE_ID FC2-4825061 FC2-4824605

Both subcommands:

- run **sequentially** (never concurrently) at a configurable, low default
  rate (``--delay-seconds``, default 2.0s between requests) -- this tool
  proves viability, it does not load-test anyone's site;
- print one JSON object per probe to stdout;
- append the same JSON objects to
  ``docs/source-probes/PHASE2_PROBE_<YYYYMMDD>.json`` unless ``--no-record``
  is passed;
- never print or record a cookie/authorization header value, an API
  secret, a full response body, or any other credential -- only
  ``cookie_configured: true/false`` (this tool does not currently support
  configuring cookies at all, so it is always ``false``) and a short
  excerpt of the parsed *title*, if any, for human sanity-checking.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fc2_metadata_core.http.client import HttpResponse, HttpTransportError, SourceHttpClient  # noqa: E402
from fc2_metadata_core.http.httpx_client import HttpxTransport  # noqa: E402
from fc2_metadata_core.normalize.fc2_number import normalize_fc2_number  # noqa: E402
from fc2_metadata_core.sources.adapters import ALL_ADAPTER_CLASSES  # noqa: E402
from fc2_metadata_core.sources.registry import SourceRegistry, UnknownSourceIdError  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
PROBE_EVIDENCE_DIR = REPO_ROOT / "docs" / "source-probes"

# A handful of header/status hints that commonly indicate a Cloudflare (or
# similar) bot-challenge page rather than the real content. Deliberately
# crude and over-inclusive -- it only ever *flags for human review*, never
# used to decide ADOPT/REJECT by itself.
_ANTI_BOT_HEADER_HINTS = ("cf-mitigated", "cf-ray", "cf-chl-bookmark")
_ANTI_BOT_BODY_HINTS = (
    "just a moment",
    "checking your browser",
    "attention required",
    "verify you are human",
)


def _build_registry() -> SourceRegistry:
    registry = SourceRegistry()
    for adapter_cls in ALL_ADAPTER_CLASSES:
        registry.register(adapter_cls.source_id, adapter_cls)
    return registry


def _looks_like_anti_bot_challenge(response: HttpResponse) -> bool:
    headers_lower = {k.lower(): v for k, v in response.headers.items()}
    if any(h in headers_lower for h in _ANTI_BOT_HEADER_HINTS):
        return True
    if headers_lower.get("server", "").lower() == "cloudflare" and response.status_code in (403, 503):
        return True
    body_start = response.text[:2000].lower()
    return any(hint in body_start for hint in _ANTI_BOT_BODY_HINTS)


class _RecordingHttpClient:
    """Wraps a real SourceHttpClient and remembers the last raw response.

    Lets ``adapter`` probes capture raw HTTP status/final-URL evidence from
    the exact same request the adapter itself made, instead of doubling the
    number of real requests sent to the target site.
    """

    def __init__(self, inner: SourceHttpClient) -> None:
        self._inner = inner
        self.last_status_code: int | None = None
        self.last_final_url: str | None = None
        self.last_headers: Mapping[str, str] = {}
        self.last_anti_bot_hint = False

    async def get(
        self,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        timeout: float | None = None,
    ) -> HttpResponse:
        response = await self._inner.get(url, headers=headers, timeout=timeout)
        self.last_status_code = response.status_code
        self.last_final_url = response.url
        self.last_headers = response.headers
        self.last_anti_bot_hint = _looks_like_anti_bot_challenge(response)
        return response


@dataclass
class ProbeRecord:
    probe_kind: str
    probed_at_utc: str
    source_id: str | None
    number: str | None
    requested_url: str
    http_status: int | None
    final_url: str | None
    elapsed_ms: float | None
    anti_bot_hint: bool
    cookie_configured: bool
    source_status: str | None = None
    error_kind: str | None = None
    error_detail: str | None = None
    fields_present: list[str] = field(default_factory=list)
    title_excerpt: str | None = None
    transport_error: str | None = None


_METADATA_FIELD_NAMES = (
    "number",
    "title",
    "studio",
    "publisher",
    "release",
    "runtime",
    "actors",
    "tags",
    "plot",
    "poster_urls",
    "thumb_urls",
    "fanart_urls",
    "extrafanart",
    "source_urls",
    "external_ids",
)


def _fields_present(metadata) -> list[str]:
    if metadata is None:
        return []
    present = []
    for name in _METADATA_FIELD_NAMES:
        value = getattr(metadata, name)
        if value:  # non-None scalar, non-empty tuple/mapping
            present.append(name)
    return present


def _record_evidence(records: list[ProbeRecord]) -> Path:
    PROBE_EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    out_path = PROBE_EVIDENCE_DIR / f"PHASE2_PROBE_{stamp}.json"

    existing: list[dict] = []
    if out_path.exists():
        existing = json.loads(out_path.read_text(encoding="utf-8"))
    existing.extend(asdict(r) for r in records)
    out_path.write_text(json.dumps(existing, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return out_path


async def _run_raw(urls: list[str], delay_seconds: float) -> list[ProbeRecord]:
    records: list[ProbeRecord] = []
    async with HttpxTransport() as client:
        for i, url in enumerate(urls):
            if i > 0:
                await asyncio.sleep(delay_seconds)
            try:
                response = await client.get(url)
                records.append(
                    ProbeRecord(
                        probe_kind="raw",
                        probed_at_utc=datetime.now(timezone.utc).isoformat(),
                        source_id=None,
                        number=None,
                        requested_url=url,
                        http_status=response.status_code,
                        final_url=response.url,
                        elapsed_ms=response.elapsed_ms,
                        anti_bot_hint=_looks_like_anti_bot_challenge(response),
                        cookie_configured=False,
                    )
                )
            except HttpTransportError as exc:
                records.append(
                    ProbeRecord(
                        probe_kind="raw",
                        probed_at_utc=datetime.now(timezone.utc).isoformat(),
                        source_id=None,
                        number=None,
                        requested_url=url,
                        http_status=None,
                        final_url=None,
                        elapsed_ms=None,
                        anti_bot_hint=False,
                        cookie_configured=False,
                        transport_error=f"{type(exc).__name__}: {exc}",
                    )
                )
    return records


async def _run_adapter(
    source_id: str, numbers: list[str], base_url: str | None, delay_seconds: float
) -> list[ProbeRecord]:
    registry = _build_registry()
    try:
        adapter = registry.create(source_id, base_url=base_url) if base_url else registry.create(source_id)
    except UnknownSourceIdError:
        available = ", ".join(registry.source_ids()) or "(none registered yet)"
        raise SystemExit(
            f"Unknown --source {source_id!r}. Registered adapters: {available}. "
            "An adapter only appears here after it has cleared Phase 2 "
            "viability research and been ADOPTed."
        )

    records: list[ProbeRecord] = []
    async with HttpxTransport() as real_client:
        for i, raw_number in enumerate(numbers):
            if i > 0:
                await asyncio.sleep(delay_seconds)

            normalized = normalize_fc2_number(raw_number)
            if not normalized.recognized:
                records.append(
                    ProbeRecord(
                        probe_kind="adapter",
                        probed_at_utc=datetime.now(timezone.utc).isoformat(),
                        source_id=source_id,
                        number=raw_number,
                        requested_url="",
                        http_status=None,
                        final_url=None,
                        elapsed_ms=None,
                        anti_bot_hint=False,
                        cookie_configured=False,
                        transport_error=f"not a recognizable FC2 number: {raw_number!r}",
                    )
                )
                continue

            canonical = normalized.canonical
            recorder = _RecordingHttpClient(real_client)
            try:
                result = await adapter.fetch(canonical, recorder)
                title = result.metadata.title if result.metadata else None
                records.append(
                    ProbeRecord(
                        probe_kind="adapter",
                        probed_at_utc=datetime.now(timezone.utc).isoformat(),
                        source_id=source_id,
                        number=canonical,
                        requested_url=recorder.last_final_url or "",
                        http_status=recorder.last_status_code,
                        final_url=recorder.last_final_url,
                        elapsed_ms=result.elapsed_ms,
                        anti_bot_hint=recorder.last_anti_bot_hint,
                        cookie_configured=False,
                        source_status=result.status.value,
                        error_kind=result.error_kind.value if result.error_kind else None,
                        error_detail=result.error_detail,
                        fields_present=_fields_present(result.metadata),
                        title_excerpt=(title[:80] if title else None),
                    )
                )
            except HttpTransportError as exc:
                records.append(
                    ProbeRecord(
                        probe_kind="adapter",
                        probed_at_utc=datetime.now(timezone.utc).isoformat(),
                        source_id=source_id,
                        number=canonical,
                        requested_url=recorder.last_final_url or "",
                        http_status=recorder.last_status_code,
                        final_url=recorder.last_final_url,
                        elapsed_ms=None,
                        anti_bot_hint=recorder.last_anti_bot_hint,
                        cookie_configured=False,
                        transport_error=f"{type(exc).__name__}: {exc}",
                    )
                )
    return records


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--delay-seconds", type=float, default=2.0, help="Delay between sequential requests (default: 2.0s)")
    parser.add_argument("--no-record", action="store_true", help="Do not append to docs/source-probes/PHASE2_PROBE_<date>.json")

    subparsers = parser.add_subparsers(dest="mode", required=True)

    raw_parser = subparsers.add_parser("raw", help="Raw HTTP GET probe, no adapter involved")
    raw_parser.add_argument("urls", nargs="+", help="One or more URLs to probe")

    adapter_parser = subparsers.add_parser("adapter", help="Run a registered adapter's fetch() against real numbers")
    adapter_parser.add_argument("--source", required=True, help="Registered source_id")
    adapter_parser.add_argument("--base-url", default=None, help="Override the adapter's default_base_url")
    adapter_parser.add_argument("numbers", nargs="+", help="One or more FC2 numbers (canonical or recognizable)")

    args = parser.parse_args(argv)

    if args.mode == "raw":
        records = asyncio.run(_run_raw(args.urls, args.delay_seconds))
    else:
        records = asyncio.run(_run_adapter(args.source, args.numbers, args.base_url, args.delay_seconds))

    for record in records:
        print(json.dumps(asdict(record), indent=2, ensure_ascii=False))

    if not args.no_record and records:
        out_path = _record_evidence(records)
        print(f"# appended {len(records)} record(s) to {out_path.relative_to(REPO_ROOT)}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
