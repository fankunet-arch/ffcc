#!/usr/bin/env python3
"""Phase 3 C3: build the known-valid FC2 ID *candidate pool* for the 50-ID coverage gate (builder v2).

    python tools/build_candidate_pool.py --out docs/acceptance/PHASE3_CANDIDATE_POOL.json

**Independence rule (the whole point of this tool).** An ID enters the pool because *public
references that are not the aggregation engine's sources* show that it exists. It never imports
``fc2_metadata_core.aggregation`` or any adapter, never asks fc2db.net / javdb / av123 anything, and
so the pool cannot be shaped by whether the engine happens to cover an ID (no cherry-picking).

Procedure (all constants below are frozen data, not tuned to results):

1. **Enumerate** -- reference 1 (``sukebei``), ``sukebei.nyaa.si`` torrent listing. For every prefix in
   ``PREFIXES`` run the public search ``FC2-PPV-<prefix>*`` (first result page). A 7-digit number that
   starts with the prefix and appears in a torrent *name* as ``FC2-PPV-<number>`` (any of the usual
   spellings) is a candidate. Per prefix, ``PER_PREFIX`` candidates are kept at a fixed even stride over
   the ascending list of that prefix's candidates (:func:`pick_per_prefix`).
2. **Corroborate** -- reference 2 (``netflav``), ``netflav.com`` search. A candidate is confirmed iff the
   search's embedded result list contains a document whose ``code`` is *exactly* that number (the site's
   fuzzy neighbours, e.g. 1825061 for a 4825061 query, never count).
3. **Frozen Phase 2 IDs** -- the 7 IDs frozen at Phase 2 are looked up on both references the same way and
   recorded with whatever they say, plus their Phase 2 provenance (which is *not* an external reference).
   They are never dropped because a reference misses them.

Every reference lookup ends in exactly one of three states (v2; v1 conflated the last two):

* ``confirmed``   -- a valid response was received and it contains exact validity evidence;
* ``negative``    -- a valid response was received and it contains no exact evidence;
* ``unavailable`` -- no response good enough to decide (timeout / connection error / HTTP 403, 429, 5xx or any
  other non-200 / an unrecognisable body such as a challenge page).

``unavailable`` is never turned into ``negative``. A first ``unavailable`` is retried **once** (after the same
>= 3 s politeness delay; no proxy, no bypass); ``confirmed`` / ``negative`` are never retried. If a *prefix
enumeration* query is still ``unavailable`` after its retry the whole build fails (non-zero exit, no output
file): an incomplete enumeration would silently change the candidate population and must not look complete.

Records only: number, per-reference state / attempts / bounded non-sensitive detail (HTTP status, exception
*type*, "exact_match" / "no_exact_match" ...), which references confirmed it, a note, the UTC date. **No
response body, header, cookie, credential or query string is ever written.**
"""

from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import json
import re
import sys
from pathlib import Path
from typing import NamedTuple

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import httpx  # noqa: E402

from fc2_metadata_core.normalize.fc2_number import normalize_fc2_number  # noqa: E402

SCHEMA_VERSION = 2
PROCEDURE_ID = "PHASE3-CANDIDATE-POOL-v2"

CONFIRMED = "confirmed"
NEGATIVE = "negative"
UNAVAILABLE = "unavailable"
MAX_ATTEMPTS = 2  # first try + exactly one polite retry, only after ``unavailable``

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
PHASE2_SOURCE_LABEL = "Phase 2 frozen probe set (docs/PHASE2_PROBE_SET.md)"
SUKEBEI_LABEL = "sukebei.nyaa.si torrent listing"
NETFLAV_LABEL = "netflav.com search (exact code match)"

_ROW_TITLE_RE = re.compile(r'<a href="/view/[0-9]+"[^>]*title="([^"]*)"')
_NAME_ID_RE = re.compile(r"FC2[-_ ]?PPV[-_ ]?([0-9]{5,8})(?![0-9])", re.IGNORECASE)
_NEXT_DATA_RE = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.DOTALL)
_NETFLAV_CODE_RE = re.compile(r"fc2[-_ ]?ppv[-_ ]?([0-9]{5,8})(?![0-9])", re.IGNORECASE)
_SUKEBEI_NO_RESULTS = "<h3>No results found</h3>"


class PrefixEnumerationIncomplete(RuntimeError):
    """A prefix query stayed ``unavailable`` after its retry: the candidate population would be incomplete."""


class Check(NamedTuple):
    """One reference lookup's final outcome. ``detail`` is bounded and never carries response data."""

    state: str
    attempts: int
    detail: str

    def as_dict(self, **extra: object) -> dict:
        return {"state": self.state, "attempts": self.attempts, "detail": self.detail, **extra}


# ---- pure parsing (offline-tested) ---------------------------------------------------------------------------------------------------------------


def sukebei_page_is_valid(html_text: str) -> bool:
    """A usable sukebei search page: it lists result rows, or it explicitly says "No results found"."""
    return _ROW_TITLE_RE.search(html_text) is not None or _SUKEBEI_NO_RESULTS in html_text


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


def netflav_result_codes(html_text: str) -> list[str] | None:
    """Digits of every result whose ``code`` is an FC2-PPV code; ``None`` if the page is not a valid result page.

    ``None`` (missing / malformed embedded JSON) is the *unavailable* case -- never "no hit".
    """
    match = _NEXT_DATA_RE.search(html_text)
    if match is None:
        return None
    try:
        data = json.loads(match.group(1))
        docs = data["props"]["initialState"]["search"]["docs"]
    except (ValueError, KeyError, TypeError):
        return None
    if not isinstance(docs, list):
        return None
    codes: list[str] = []
    for doc in docs:
        code = doc.get("code") if isinstance(doc, dict) else None
        if isinstance(code, str):
            found = _NETFLAV_CODE_RE.fullmatch(code.strip())
            if found:
                codes.append(found.group(1))
    return codes


def netflav_exact_hit(html_text: str, digits: str) -> bool:
    """Does netflav's embedded result list contain a document whose code is exactly ``digits``?"""
    return digits in (netflav_result_codes(html_text) or [])


def band_of(number_digits: str) -> str:
    n = int(number_digits)
    return "older" if n < 2_000_000 else "middle" if n < 4_000_000 else "recent"


# ---- the two public references -----------------------------------------------------------------------------------------------------------------


class References:
    """The two public references, one polite sequential client with tri-state outcomes and one retry."""

    def __init__(self, client: httpx.AsyncClient, delay_seconds: float) -> None:
        self._client = client
        self._delay = delay_seconds
        self._first = True
        self.requests_made = 0
        self.retry_requests = 0

    async def _get(self, url: str, params: dict[str, str]) -> tuple[str | None, str]:
        """One polite request -> ``(body or None, bounded detail)``. Never raises for a network problem."""
        if not self._first:
            await asyncio.sleep(self._delay)
        self._first = False
        self.requests_made += 1
        try:
            response = await self._client.get(url, params=params)
        except httpx.TimeoutException:
            return None, "timeout"
        except httpx.HTTPError as exc:
            return None, f"exception:{type(exc).__name__}"
        except (ValueError, LookupError) as exc:  # e.g. an undecodable body surfaced by httpx
            return None, f"exception:{type(exc).__name__}"
        if response.status_code != 200:
            return None, f"http_{response.status_code}"
        return response.text, "http_200"

    async def _lookup(self, url: str, params: dict[str, str], decide) -> tuple[str, int, str, object]:
        """``decide(text) -> (state, detail, payload)`` or ``None`` for an unusable body.

        Returns ``(state, attempts, detail, payload)``. Only ``unavailable`` is retried, once.
        """
        detail = "no_attempt"
        for attempt in range(1, MAX_ATTEMPTS + 1):
            if attempt > 1:
                self.retry_requests += 1
            text, detail = await self._get(url, params)
            if text is not None:
                decided = decide(text)
                if decided is None:
                    detail = "invalid_response"
                else:
                    state, why, payload = decided
                    return state, attempt, why, payload
        return UNAVAILABLE, MAX_ATTEMPTS, detail, None

    async def sukebei_prefix(self, prefix: str) -> tuple[Check, dict[str, int]]:
        """Enumeration query. ``confirmed`` = a valid page (possibly with zero rows); never ``negative``."""

        def decide(text: str):
            if not sukebei_page_is_valid(text):
                return None
            return CONFIRMED, "valid_results_page", sukebei_torrent_ids(text)

        state, attempts, detail, counts = await self._lookup(
            SUKEBEI_URL, {"f": "0", "c": "0_0", "q": f"FC2-PPV-{prefix}*"}, decide
        )
        return Check(state, attempts, detail), (counts or {})

    async def sukebei_number(self, digits: str) -> tuple[Check, int]:
        """Direct lookup of one number. Returns the check and how many torrent rows named it."""

        def decide(text: str):
            if not sukebei_page_is_valid(text):
                return None
            rows = sukebei_torrent_ids(text).get(digits, 0)
            return (CONFIRMED, f"exact_match_in_{rows}_torrent_rows", rows) if rows else (NEGATIVE, "no_exact_match", 0)

        state, attempts, detail, rows = await self._lookup(
            SUKEBEI_URL, {"f": "0", "c": "0_0", "q": f"FC2-PPV-{digits}"}, decide
        )
        return Check(state, attempts, detail), int(rows or 0)

    async def netflav(self, digits: str) -> Check:
        def decide(text: str):
            codes = netflav_result_codes(text)
            if codes is None:
                return None
            return (CONFIRMED, "exact_match", None) if digits in codes else (NEGATIVE, "no_exact_match", None)

        state, attempts, detail, _ = await self._lookup(NETFLAV_URL, {"keyword": digits}, decide)
        return Check(state, attempts, detail)


# ---- pool assembly -----------------------------------------------------------------------------------------------------------------------------------------


def _entry(
    digits: str,
    *,
    sukebei: Check,
    sukebei_rows: int,
    netflav: Check,
    origin: str,
    today: str,
    shared_with_prefix_query: str | None = None,
) -> dict:
    sources: list[str] = []
    notes: list[str] = []
    if sukebei.state == CONFIRMED:
        sources.append(SUKEBEI_LABEL)
        notes.append(f"named FC2-PPV-{digits} in {sukebei_rows} torrent row(s)" if sukebei_rows else f"named FC2-PPV-{digits} in a torrent name")
    if netflav.state == CONFIRMED:
        sources.append(NETFLAV_LABEL)
        notes.append("exact 'fc2-ppv' code hit on netflav")
    external = len(sources)
    if origin == "phase2_frozen":
        sources.append(PHASE2_SOURCE_LABEL)
        notes.append("frozen at Phase 2 as a known-valid probe ID (provenance only, not an external reference)")
    for name, check in (("sukebei", sukebei), ("netflav", netflav)):
        if check.state == UNAVAILABLE:
            notes.append(f"{name} UNAVAILABLE after {check.attempts} attempt(s) ({check.detail}); not a negative")
        elif check.state == NEGATIVE:
            notes.append(f"{name} negative (no exact match)")
    if external == 1:
        notes.append("single external reference (single-source validation)")
    elif external == 0:
        notes.append("no external reference confirmed")
    sukebei_check = sukebei.as_dict()
    if shared_with_prefix_query is not None:
        sukebei_check["shared_with_prefix_query"] = shared_with_prefix_query
    return {
        "number": f"FC2-{digits}",
        "band": band_of(digits),
        "origin": origin,
        "validation_date": today,
        "validity_sources": sources,
        "external_reference_count": external,
        "validity_note": "; ".join(notes),
        "reference_checks": {"sukebei": sukebei_check, "netflav": netflav.as_dict()},
    }


def summarize_pool(candidates: list[dict], prefix_rows: list[dict], refs_requests: int, retry_requests: int) -> dict:
    counts = {CONFIRMED: 0, NEGATIVE: 0, UNAVAILABLE: 0}
    for candidate in candidates:
        for name, check in candidate["reference_checks"].items():
            if name == "sukebei" and "shared_with_prefix_query" in check:
                continue  # counted with its prefix query, not as a separate lookup
            counts[check["state"]] += 1
    prefix_complete = all(row["state"] == CONFIRMED for row in prefix_rows)
    return {
        "requests_made": refs_requests,
        "retry_requests": retry_requests,
        "initial_requests": refs_requests - retry_requests,
        "confirmed_checks": counts[CONFIRMED],
        "negative_checks": counts[NEGATIVE],
        "unavailable_checks": counts[UNAVAILABLE],
        "prefix_enumeration_complete": prefix_complete,
    }


async def build_pool(delay_seconds: float, *, prefixes=PREFIXES, per_prefix=PER_PREFIX, frozen=PHASE2_FROZEN_IDS, client: httpx.AsyncClient | None = None) -> dict:
    """Build the pool document. Raises :class:`PrefixEnumerationIncomplete` rather than return a partial pool."""
    today = dt.datetime.now(dt.timezone.utc).date().isoformat()
    owns_client = client is None
    if client is None:
        client = httpx.AsyncClient(headers={"User-Agent": USER_AGENT}, follow_redirects=True, timeout=httpx.Timeout(20.0))
    try:
        refs = References(client, delay_seconds)
        prefix_rows: list[dict] = []
        picked: dict[str, tuple[str, int, Check]] = {}  # digits -> (prefix, rows, prefix Check)
        for prefix in prefixes:
            check, counts = await refs.sukebei_prefix(prefix)
            if check.state != CONFIRMED:
                raise PrefixEnumerationIncomplete(
                    f"prefix {prefix!r} enumeration stayed {check.state} after {check.attempts} attempt(s) ({check.detail})"
                )
            found = prefix_candidates(counts, prefix)
            kept = pick_per_prefix(found, per_prefix)
            prefix_rows.append({"prefix": prefix, "state": check.state, "attempts": check.attempts, "detail": check.detail,
                                "candidates_found": len(found), "candidates_kept": len(kept)})
            for digits in kept:
                picked[digits] = (prefix, counts[digits], check)

        candidates: dict[str, dict] = {}
        for digits, (prefix, rows, prefix_check) in sorted(picked.items()):
            netflav = await refs.netflav(digits)
            sukebei = Check(CONFIRMED, prefix_check.attempts, "torrent_name_match_via_prefix_query")
            candidates[digits] = _entry(digits, sukebei=sukebei, sukebei_rows=rows, netflav=netflav, origin="enumerated",
                                        today=today, shared_with_prefix_query=prefix)
        for number in frozen:
            digits = number.split("-", 1)[1]
            sukebei, rows = await refs.sukebei_number(digits)
            netflav = await refs.netflav(digits)
            candidates[digits] = _entry(digits, sukebei=sukebei, sukebei_rows=rows, netflav=netflav, origin="phase2_frozen", today=today)
        ordered = [candidates[d] for d in sorted(candidates, key=int)]
        summary = summarize_pool(ordered, prefix_rows, refs.requests_made, refs.retry_requests)
    finally:
        if owns_client:
            await client.aclose()
    return {
        "schema_version": SCHEMA_VERSION,
        "procedure": PROCEDURE_ID,
        "builder": "tools/build_candidate_pool.py (v2: tri-state lookups, one polite retry, prefix-completeness guard)",
        "created_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "engine_independent": True,
        "prefixes": list(prefixes),
        "per_prefix": per_prefix,
        **summary,
        "prefix_enumeration": prefix_rows,
        "candidates": ordered,
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
    try:
        pool = asyncio.run(build_pool(args.delay_seconds))
    except PrefixEnumerationIncomplete as exc:
        raise SystemExit(f"pool build FAILED, no output written: {exc}") from None
    for candidate in pool["candidates"]:
        if not normalize_fc2_number(candidate["number"]).recognized:
            raise SystemExit(f"internal error: {candidate['number']!r} is not canonical")
    out.write_text(json.dumps(pool, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    dual = sum(1 for c in pool["candidates"] if c["external_reference_count"] >= 2)
    print(
        f"# wrote {len(pool['candidates'])} candidates ({dual} with >=2 external references; "
        f"{pool['requests_made']} requests, {pool['retry_requests']} retries, {pool['unavailable_checks']} unavailable checks) to {out}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
