#!/usr/bin/env python3
"""Phase 3 C3: deterministically select the frozen 50-ID acceptance set from the frozen candidate pool (v2).

    python tools/select_50id_set.py --pool docs/acceptance/PHASE3_CANDIDATE_POOL.json \\
                                    --out  docs/acceptance/PHASE3_50_ID_SET.json

Method ``PHASE3-50ID-SELECTION-v2`` (prose contract: ``docs/acceptance/PHASE3_50_ID_SELECTION_METHOD.md``;
this file is its executable form). v2 is a *pre-selection amendment* of v1 (which required every sampled ID to
have >= 2 external references); it changes nothing about the mandatory IDs, bands or quotas. The same pool file
*always* yields the same 50 IDs -- offline, no randomness, no seed, no clock, no network, no engine:

1. the 7 IDs frozen at Phase 2 are always included (they must be in the pool), tier ``phase2_mandatory``;
2. sampling candidates = every other pool candidate that is **confirmed by at least one external reference**
   (``reference_checks`` with state ``confirmed`` on sukebei / netflav). Zero-reference, negative-only and
   unavailable-only candidates are never eligible. Tier 1 ("dual_reference") = 2 confirmed external
   references; tier 2 ("single_reference_fallback") = exactly 1;
3. fixed numeric bands -- older ``< 2,000,000``, middle ``2,000,000 .. 3,999,999``, recent ``>= 4,000,000`` --
   with fixed quotas 14 / 15 / 14 (= 43);
4. inside a band with quota ``q``: let ``T1`` be its tier-1 candidates ascending. If ``len(T1) >= q`` take ``q``
   of them at indices ``((2*j + 1) * m) // (2*q)`` (``m = len(T1)``), and use **no** tier 2. Otherwise take
   **all** of ``T1`` plus ``deficit = q - len(T1)`` tier-2 candidates chosen from the tier-2 list (ascending)
   by the same even stride with ``m = len(T2)``, ``q = deficit``;
5. the result is sorted ascending and must be exactly 50 distinct IDs.

A band that cannot reach its quota from tier 1 + tier 2 is an error (the pool must be widened *before*
selection); the algorithm never silently shifts a quota or swaps an ID. The selector refuses a pool whose
prefix enumeration is not complete or whose stored reference counts disagree with its own reference checks.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fc2_metadata_core.normalize.fc2_number import normalize_fc2_number  # noqa: E402

SCHEMA_VERSION = 2
POOL_SCHEMA_VERSION = 2
METHOD_ID = "PHASE3-50ID-SELECTION-v2"
MANDATORY: tuple[str, ...] = (
    "FC2-4825061",
    "FC2-4824605",
    "FC2-4979299",
    "FC2-4976588",
    "FC2-1042815",
    "FC2-4978035",
    "FC2-4972767",
)
# (name, inclusive lower bound, exclusive upper bound, quota)
BANDS: tuple[tuple[str, int, int, int], ...] = (
    ("older", 0, 2_000_000, 14),
    ("middle", 2_000_000, 4_000_000, 15),
    ("recent", 4_000_000, 10**9, 14),
)
TOTAL = 50
TIER_MANDATORY = "phase2_mandatory"
TIER_DUAL = "dual_reference"
TIER_SINGLE = "single_reference_fallback"
EXTERNAL_REFERENCES = ("sukebei", "netflav")


class SelectionError(ValueError):
    """The pool cannot satisfy the frozen method (widen the pool; never bend the method)."""


def band_name(n: int) -> str:
    for name, lo, hi, _ in BANDS:
        if lo <= n < hi:
            return name
    raise SelectionError(f"number {n} is outside every band")


def _canonical(entry: dict) -> tuple[str, int]:
    verdict = normalize_fc2_number(entry.get("number", ""))
    if not verdict.recognized:
        raise SelectionError(f"pool candidate has a non-canonical number: {entry.get('number')!r}")
    return verdict.canonical, int(verdict.canonical.split("-", 1)[1])


def confirmed_external_references(entry: dict) -> int:
    """Number of external references whose recorded check state is ``confirmed`` (validated against the stored count)."""
    checks = entry.get("reference_checks")
    if not isinstance(checks, dict):
        raise SelectionError(f"{entry.get('number')!r}: missing reference_checks")
    confirmed = sum(1 for name in EXTERNAL_REFERENCES if isinstance(checks.get(name), dict) and checks[name].get("state") == "confirmed")
    if entry.get("external_reference_count") != confirmed:
        raise SelectionError(
            f"{entry.get('number')!r}: external_reference_count={entry.get('external_reference_count')!r} "
            f"disagrees with its reference_checks ({confirmed} confirmed)"
        )
    return confirmed


def _stride(members: list[str], quota: int) -> list[str]:
    """``quota`` members at an even stride over an ascending list (requires ``len(members) >= quota``)."""
    return [members[((2 * j + 1) * len(members)) // (2 * quota)] for j in range(quota)]


def select(candidates: list[dict]) -> list[dict]:
    """Pure function: pool candidates -> the 50 selected entries (ascending), tagged with origin / validation tier."""
    by_number: dict[str, dict] = {}
    for entry in candidates:
        canonical, _ = _canonical(entry)
        by_number.setdefault(canonical, entry)  # de-duplicate: first occurrence wins
    missing = [m for m in MANDATORY if m not in by_number]
    if missing:
        raise SelectionError(f"the pool lacks Phase 2 frozen IDs: {missing}")

    selected: dict[str, dict] = {}
    for number in MANDATORY:
        confirmed_external_references(by_number[number])  # consistency only; mandatory regardless of the count
        selected[number] = {**by_number[number], "selection_origin": "phase2_frozen", "validation_tier": TIER_MANDATORY}

    tier1: dict[str, list[str]] = {name: [] for name, *_ in BANDS}
    tier2: dict[str, list[str]] = {name: [] for name, *_ in BANDS}
    for n, number in sorted((int(number.split("-", 1)[1]), number) for number in by_number if number not in MANDATORY):
        confirmed = confirmed_external_references(by_number[number])
        if confirmed >= 2:
            tier1[band_name(n)].append(number)
        elif confirmed == 1:
            tier2[band_name(n)].append(number)
        # 0 confirmed (zero-reference / negative-only / unavailable-only) is never eligible

    for name, _lo, _hi, quota in BANDS:
        first, second = tier1[name], tier2[name]
        if len(first) >= quota:
            chosen = [(number, TIER_DUAL) for number in _stride(first, quota)]
        else:
            deficit = quota - len(first)
            if len(second) < deficit:
                raise SelectionError(
                    f"band {name!r} has {len(first)} dual + {len(second)} single-reference candidates, needs {quota}"
                )
            chosen = [(number, TIER_DUAL) for number in first] + [(number, TIER_SINGLE) for number in _stride(second, deficit)]
        for number, tier in chosen:
            selected[number] = {**by_number[number], "selection_origin": f"sampled:{name}", "validation_tier": tier}

    if len(selected) != TOTAL:
        raise SelectionError(f"selected {len(selected)} IDs, expected {TOTAL}")
    return [selected[n] for n in sorted(selected, key=lambda x: int(x.split("-", 1)[1]))]


def _check_pool_document(pool_doc: dict) -> None:
    if pool_doc.get("schema_version") != POOL_SCHEMA_VERSION:
        raise SelectionError(f"pool schema_version must be {POOL_SCHEMA_VERSION}, got {pool_doc.get('schema_version')!r}")
    if pool_doc.get("prefix_enumeration_complete") is not True:
        raise SelectionError("the pool's prefix enumeration is not complete")
    if not isinstance(pool_doc.get("candidates"), list):
        raise SelectionError("the pool has no candidates list")


def build_set_document(pool_doc: dict, pool_sha256: str, *, created_at: str) -> dict:
    _check_pool_document(pool_doc)
    chosen = select(pool_doc["candidates"])
    ids = []
    for entry in chosen:
        digits = int(entry["number"].split("-", 1)[1])
        ids.append(
            {
                "number": entry["number"],
                "band": band_name(digits),
                "selection_origin": entry["selection_origin"],
                "validation_tier": entry["validation_tier"],
                "external_reference_count": entry["external_reference_count"],
                "validity_sources": entry["validity_sources"],
                "reference_checks": entry["reference_checks"],
                "validity_note": entry["validity_note"],
                "validation_date": entry["validation_date"],
            }
        )
    tiers: dict[str, int] = {}
    for item in ids:
        tiers[item["validation_tier"]] = tiers.get(item["validation_tier"], 0) + 1
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": created_at,
        "selection_method": {
            "id": METHOD_ID,
            "doc": "docs/acceptance/PHASE3_50_ID_SELECTION_METHOD.md",
            "tool": "tools/select_50id_set.py",
            "bands": [{"name": n, "min": lo, "max_exclusive": hi, "quota": q} for n, lo, hi, q in BANDS],
            "mandatory": list(MANDATORY),
            "eligibility": "tier1 (>=2 confirmed external references) first; tier2 (exactly 1) only to fill a band's deficit",
        },
        "candidate_pool": {
            "file": "docs/acceptance/PHASE3_CANDIDATE_POOL.json",
            "sha256": pool_sha256,
            "candidates": len(pool_doc["candidates"]),
        },
        "evidence_tier_counts": dict(sorted(tiers.items())),
        "ids": ids,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--pool", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    pool_path, out = Path(args.pool), Path(args.out)
    if out.exists():
        raise SystemExit(f"refusing to overwrite {out}")
    raw = pool_path.read_bytes()
    try:
        document = build_set_document(
            json.loads(raw.decode("utf-8")),
            hashlib.sha256(raw).hexdigest(),
            created_at=dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        )
    except SelectionError as exc:
        raise SystemExit(f"selection failed, nothing written: {exc}") from None
    out.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"# wrote {len(document['ids'])} IDs to {out} (tiers: {document['evidence_tier_counts']})", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
