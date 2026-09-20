#!/usr/bin/env python3
"""Phase 3 C3: deterministically select the frozen 50-ID acceptance set from the candidate pool.

    python tools/select_50id_set.py --pool docs/acceptance/PHASE3_CANDIDATE_POOL.json \\
                                    --out  docs/acceptance/PHASE3_50_ID_SET.json

Method ``PHASE3-50ID-SELECTION-v1`` (the prose contract is ``docs/acceptance/PHASE3_50_ID_SELECTION_METHOD.md``;
this file is its executable form). The same pool file *always* yields the same 50 IDs:

1. the 7 IDs frozen at Phase 2 are always included (they must be present in the pool);
2. eligible sampling candidates = pool entries with >= 2 external references (``external_reference_count``),
   minus the 7 above, canonicalised, de-duplicated, sorted ascending by number;
3. split into three fixed numeric bands -- older ``< 2,000,000``, middle ``2,000,000 .. 3,999,999``,
   recent ``>= 4,000,000`` -- with fixed quotas 14 / 15 / 14 (= 43);
4. inside a band with ``m`` members and quota ``q`` take the members at indices
   ``((2*j + 1) * m) // (2*q)`` for ``j = 0..q-1`` (an even stride over the ascending list; no randomness,
   no seed, no clock);
5. the result is sorted ascending and must be exactly 50 distinct IDs.

The selector never sees, and cannot depend on, any aggregation result. A band with fewer members than its
quota is an error (the pool must be widened *before* selection) -- the algorithm never silently shifts a
quota or swaps an ID.
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

SCHEMA_VERSION = 1
METHOD_ID = "PHASE3-50ID-SELECTION-v1"
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
MIN_EXTERNAL_REFERENCES = 2


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
        raise SelectionError(f"pool entry has a non-canonical number: {entry.get('number')!r}")
    return verdict.canonical, int(verdict.canonical.split("-", 1)[1])


def select(entries: list[dict]) -> list[dict]:
    """Pure function: pool entries -> the 50 selected entries (ascending), each tagged with stratum/origin."""
    by_number: dict[str, dict] = {}
    for entry in entries:
        canonical, _ = _canonical(entry)
        by_number.setdefault(canonical, entry)  # de-duplicate: first occurrence wins
    missing = [m for m in MANDATORY if m not in by_number]
    if missing:
        raise SelectionError(f"the pool lacks Phase 2 frozen IDs: {missing}")

    selected: dict[str, dict] = {}
    for number in MANDATORY:
        selected[number] = {**by_number[number], "selection_origin": "phase2_frozen"}

    remainder = sorted(
        (
            (int(number.split("-", 1)[1]), number)
            for number, entry in by_number.items()
            if number not in MANDATORY and int(entry.get("external_reference_count", 0)) >= MIN_EXTERNAL_REFERENCES
        )
    )
    for name, lo, hi, quota in BANDS:
        members = [number for n, number in remainder if lo <= n < hi]
        if len(members) < quota:
            raise SelectionError(f"band {name!r} has {len(members)} eligible candidates, needs {quota}")
        for j in range(quota):
            number = members[((2 * j + 1) * len(members)) // (2 * quota)]
            selected[number] = {**by_number[number], "selection_origin": f"sampled:{name}"}

    if len(selected) != TOTAL:
        raise SelectionError(f"selected {len(selected)} IDs, expected {TOTAL}")
    return [selected[n] for n in sorted(selected, key=lambda x: int(x.split("-", 1)[1]))]


def build_set_document(pool_doc: dict, pool_sha256: str, *, created_at: str) -> dict:
    chosen = select(pool_doc["entries"])
    ids = []
    for entry in chosen:
        digits = int(entry["number"].split("-", 1)[1])
        ids.append(
            {
                "number": entry["number"],
                "band": band_name(digits),
                "selection_origin": entry["selection_origin"],
                "validity_sources": entry["validity_sources"],
                "validity_note": entry["validity_note"],
                "validation_date": entry["validation_date"],
            }
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": created_at,
        "selection_method": {
            "id": METHOD_ID,
            "doc": "docs/acceptance/PHASE3_50_ID_SELECTION_METHOD.md",
            "tool": "tools/select_50id_set.py",
            "bands": [{"name": n, "min": lo, "max_exclusive": hi, "quota": q} for n, lo, hi, q in BANDS],
            "mandatory": list(MANDATORY),
            "min_external_references": MIN_EXTERNAL_REFERENCES,
        },
        "candidate_pool": {
            "file": "docs/acceptance/PHASE3_CANDIDATE_POOL.json",
            "sha256": pool_sha256,
            "entries": len(pool_doc["entries"]),
        },
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
    document = build_set_document(
        json.loads(raw.decode("utf-8")),
        hashlib.sha256(raw).hexdigest(),
        created_at=dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
    )
    out.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"# wrote {len(document['ids'])} IDs to {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
