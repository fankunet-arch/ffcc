#!/usr/bin/env python3
"""Phase 3 C3: build the known-valid FC2 ID *candidate pool* for the 50-ID coverage gate.

    python tools/build_candidate_pool.py --out docs/acceptance/PHASE3_CANDIDATE_POOL.json

**Independence rule (the whole point of this tool).** An ID enters the pool because *public
references that are not the aggregation engine's sources* show that it exists. It never imports
``fc2_metadata_core.aggregation`` or any adapter, never asks fc2db.net / javdb / av123 anything, and
so the pool cannot be shaped by whether the engine happens to cover an ID (no cherry-picking).

Procedure (all constants below are frozen data, not tuned to results):

1. **Enumerate** -- reference 1, ``sukebei.nyaa.si`` torrent listing. For every prefix in
   ``PREFIXES`` run the public search ``FC2-PPV-<prefix>*`` (first result page). A 7-digit number that
   starts with the prefix and appears in a torrent *name* as ``FC2-PPV-<number>`` (any of the usual
   spellings) is a candidate. Per prefix, ``PER_PREFIX`` candidates are kept at a fixed even stride over
   the ascending list of that prefix's candidates (:func:`pick_per_prefix`).
2. **Corroborate** -- reference 2, ``netflav.com`` search. A candidate is corroborated iff the search's
   embedded result list contains a document whose ``code`` is *exactly* that number (the site's fuzzy
   neighbours, e.g. 1825061 for a 4825061 query, never count).
3. **Frozen Phase 2 IDs** -- the 7 IDs frozen at Phase 2 are looked up the same way and recorded with
   whatever the two references say, plus their Phase 2 provenance. They are *not* dropped if a
   reference misses them.

Records only: number, which references confirmed it, a note, the UTC date. **No response body, header,
cookie or credential is ever written.** Sequential, ``--delay-seconds`` (default 3) between requests,
no bypass of any kind; a blocked / failing request just means "not confirmed by that reference".
"""

from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import httpx  # noqa: E402

from fc2_metadata_core.normalize.fc2_number import normalize_fc2_number  # noqa: E402

SCHEMA_VERSION = 1
PROCEDURE_ID = "PHASE3-CANDIDATE-POOL-v1"

# 7-digit ID space 1.0M .. 4.99M in 40 fixed two-digit prefixes (10..49).
PREFIXES: tuple[str, ...] = tuple(str(n) for n in range(10, 50))
PER_PREFIX = 4

PHASE2_FROZEN_IDS: tuple[str, ...] = (
    "FC2-4825061",
    "FC2-4824605",
    "FC2-4979299",
    "FC2-4976588",
    "FC2-1042815",
    "FC2-4978035",
    "FC2-4972767",
)

SUKEBEI_URL = "https://sukebei.nyaa.si/"
NETFLAV_URL = "https://netflav.com/search"
USER_AGENT = "fc2-organizer-source-probe/0.1 (+https://github.com/fankunet-arch/ffcc)"

_ROW_TITLE_RE = re.compile(r'<a href="/view/[0-9]+"[^>]*title="([^"]*)"')
_NAME_ID_RE = re.compile(r"FC2[-_ ]?PPV[-_ ]?([0-9]{5,8})(?![0-9])", re.IGNORECASE)
_NEXT_DATA_RE = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.DOTALL)
_NETFLAV_CODE_RE = re.compile(r"fc2[-_ ]?ppv[-_ ]?([0-9]{5,8})(?![0-9])", re.IGNORECASE)


def sukebei_torrent_ids(html_text: str) -> dict[str, int]:
    """``{digits: number of torrent rows naming it}`` from one sukebei result page (names only)."""
    counts: dict[str, int] = {}
    for name in _ROW_TITLE_RE.findall(html_text):
        for digits in set(_NAME_ID_RE.findall(name)):
            counts[digits] = counts.get(digits, 0) + 1
    return counts


def prefix_candidates(counts: dict[str, int], prefix: str) -> list[str]:
    """Ascending 7-digit ids from ``counts`` that start with ``prefix``."""
    return sorted(d for d in counts if len(d) == 7 and d.startswith(prefix))


def pick_per_prefix(sorted_digits: list[str], k: int) -> list[str]:
    """``k`` items at an even stride over an ascending list (all of it when it has <= k items)."""
    n = len(sorted_digits)
    if n <= k:
        return list(sorted_digits)
    return [sorted_digits[((2 * j + 1) * n) // (2 * k)] for j in range(k)]


def netflav_exact_hit(html_text: str, digits: str) -> bool:
    """Does netflav's embedded result list contain a document whose code is exactly ``digits``?"""
    match = _NEXT_DATA_RE.search(html_text)
    if match is None:
        return False
    try:
        data = json.loads(match.group(1))
        docs = data["props"]["initialState"]["search"]["docs"]
    except (ValueError, KeyError, TypeError):
        return False
    if not isinstance(docs, list):
        return False
    for doc in docs:
        code = doc.get("code") if isinstance(doc, dict) else None
        if isinstance(code, str):
            found = _NETFLAV_CODE_RE.fullmatch(code.strip())
            if found and found.group(1) == digits:
                return True
    return False


def band_of(number_digits: str) -> str:
    n = int(number_digits)
    return "older" if n < 2_000_000 else "middle" if n < 4_000_000 else "recent"


class References:
    """The two public references, one polite sequential client."""

    def __init__(self, client: httpx.AsyncClient, delay_seconds: float) -> None:
        self._client = client
        self._delay = delay_seconds
        self._first = True
        self.request_count = 0
        self.failures = 0

    async def _get(self, url: str, params: dict[str, str]) -> str | None:
        if not self._first:
            await asyncio.sleep(self._delay)
        self._first = False
        self.request_count += 1
        try:
            response = await self._client.get(url, params=params)
        except (httpx.HTTPError, ValueError, LookupError):
            self.failures += 1
            return None
        if response.status_code != 200:
            self.failures += 1
            return None
        return response.text

    async def sukebei(self, query: str) -> dict[str, int]:
        text = await self._get(SUKEBEI_URL, {"f": "0", "c": "0_0", "q": query})
        return {} if text is None else sukebei_torrent_ids(text)

    async def netflav(self, digits: str) -> bool:
        text = await self._get(NETFLAV_URL, {"keyword": digits})
        return False if text is None else netflav_exact_hit(text, digits)


def _entry(digits: str, *, torrents: int, netflav: bool, origin: str, phase2_note: str | None, today: str) -> dict:
    sources: list[str] = []
    notes: list[str] = []
    if torrents:
        sources.append("sukebei.nyaa.si torrent listing")
        notes.append(f"named FC2-PPV-{digits} in {torrents} torrent row(s)")
    if netflav:
        sources.append("netflav.com search (exact code match)")
        notes.append("exact 'fc2-ppv' code hit on netflav")
    if phase2_note:
        sources.append("Phase 2 frozen probe set (docs/PHASE2_PROBE_SET.md)")
        notes.append(phase2_note)
    if len([s for s in sources if not s.startswith("Phase 2")]) == 1:
        notes.append("single external reference (single-source validation)")
    return {
        "number": f"FC2-{digits}",
        "band": band_of(digits),
        "origin": origin,
        "validity_sources": sources,
        "external_reference_count": len([s for s in sources if not s.startswith("Phase 2")]),
        "validity_note": "; ".join(notes) if notes else "no external reference confirmed",
        "validation_date": today,
    }


async def build_pool(delay_seconds: float, *, prefixes=PREFIXES, per_prefix=PER_PREFIX, frozen=PHASE2_FROZEN_IDS) -> dict:
    today = dt.datetime.now(dt.timezone.utc).date().isoformat()
    entries: dict[str, dict] = {}
    async with httpx.AsyncClient(
        headers={"User-Agent": USER_AGENT}, follow_redirects=True, timeout=httpx.Timeout(20.0)
    ) as client:
        refs = References(client, delay_seconds)
        candidates: dict[str, int] = {}
        for prefix in prefixes:
            counts = await refs.sukebei(f"FC2-PPV-{prefix}*")
            for digits in pick_per_prefix(prefix_candidates(counts, prefix), per_prefix):
                candidates[digits] = counts[digits]
        for digits, torrents in sorted(candidates.items()):
            hit = await refs.netflav(digits)
            entries[digits] = _entry(digits, torrents=torrents, netflav=hit, origin="enumerated", phase2_note=None, today=today)
        for number in frozen:
            digits = number.split("-", 1)[1]
            counts = await refs.sukebei(f"FC2-PPV-{digits}")
            hit = await refs.netflav(digits)
            entries[digits] = _entry(
                digits,
                torrents=counts.get(digits, 0),
                netflav=hit,
                origin="phase2_frozen",
                phase2_note="frozen at Phase 2 as a known-valid probe ID (resolved by >= 1 adopted source there)",
                today=today,
            )
        request_count, failures = refs.request_count, refs.failures
    ordered = [entries[d] for d in sorted(entries, key=int)]
    return {
        "schema_version": SCHEMA_VERSION,
        "procedure": PROCEDURE_ID,
        "created_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "prefixes": list(prefixes),
        "per_prefix": per_prefix,
        "requests_made": request_count,
        "request_failures": failures,
        "engine_independent": True,
        "entries": ordered,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", required=True)
    parser.add_argument("--delay-seconds", type=float, default=3.0)
    args = parser.parse_args(argv)
    if args.delay_seconds < 3.0:
        raise SystemExit("--delay-seconds must be >= 3 (politeness floor)")
    out = Path(args.out)
    if out.exists():
        raise SystemExit(f"refusing to overwrite {out}")
    pool = asyncio.run(build_pool(args.delay_seconds))
    for entry in pool["entries"]:
        if not normalize_fc2_number(entry["number"]).recognized:
            raise SystemExit(f"internal error: {entry['number']!r} is not canonical")
    out.write_text(json.dumps(pool, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    dual = sum(1 for e in pool["entries"] if e["external_reference_count"] >= 2)
    print(f"# wrote {len(pool['entries'])} entries ({dual} with >=2 external references) to {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
