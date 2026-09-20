"""Phase 3 C3 (pre-selection amendment 1): deterministic selector v2 (dual-first, transparent single-reference fallback).

v1 demanded >= 2 external references for every sampled ID; the first pool could not satisfy that (older 9 < 14,
recent 2 < 14). v2 keeps the mandatory 7, the bands and the 14/15/14 quotas, and only relaxes eligibility: tier 1
(>= 2 confirmed external references) first; tier 2 (exactly 1) *only* to fill a band's deficit; a candidate with
0 confirmed external references (zero / negative-only / unavailable-only / Phase-2-provenance-only) is never sampled.
Pure, offline, no randomness, no clock, no engine.
"""

from __future__ import annotations

import ast
import importlib.util
import json
import random
import tempfile
from pathlib import Path

import pytest

TOOL = Path(__file__).resolve().parents[3] / "tools" / "select_50id_set.py"
_spec = importlib.util.spec_from_file_location("select_50id_set_v2_under_test", TOOL)
sel = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sel)

PHASE2_SEVEN = ("FC2-4825061", "FC2-4824605", "FC2-4979299", "FC2-4976588", "FC2-1042815", "FC2-4978035", "FC2-4972767")
OLDER, MIDDLE, RECENT = 1_000_000, 2_000_001, 4_000_003


def cand(n: int, sukebei: str = "confirmed", netflav: str = "confirmed", origin: str = "enumerated") -> dict:
    external = (sukebei == "confirmed") + (netflav == "confirmed")
    return {
        "number": f"FC2-{n}",
        "band": sel.band_name(n),
        "origin": origin,
        "validation_date": "2026-09-20",
        "validity_sources": ["s"] * external,
        "external_reference_count": external,
        "validity_note": "n",
        "reference_checks": {
            "sukebei": {"state": sukebei, "attempts": 1, "detail": "d"},
            "netflav": {"state": netflav, "attempts": 1, "detail": "d"},
        },
    }


def pool_doc(candidates, *, complete=True, schema=2):
    return {"schema_version": schema, "prefix_enumeration_complete": complete, "candidates": candidates}


def frozen_seven(**states):
    return [cand(int(n.split("-")[1]), sukebei=states.get("sukebei", "negative"), netflav=states.get("netflav", "negative"), origin="phase2_frozen") for n in PHASE2_SEVEN]


def band_pool(*, dual, single, base, step=10_000, other=()):
    """``dual`` tier-1 + ``single`` tier-2 candidates interleaved through one band, plus ``other`` junk (0-confirmed) ones."""
    out = []
    n = base
    kinds = ["dual"] * dual + ["single"] * single
    random.Random(7).shuffle(kinds)
    for kind in kinds:
        out.append(cand(n, "confirmed", "confirmed" if kind == "dual" else "negative"))
        n += step
    for i, (s, f) in enumerate(other):
        out.append(cand(n + i * step, s, f))
    return out


def full_pool(older=(20, 40), middle=(40, 40), recent=(20, 40), junk=True):
    junk_states = [("negative", "negative"), ("unavailable", "unavailable"), ("negative", "unavailable"), ("unavailable", "negative")]
    other = junk_states if junk else []
    return (
        band_pool(dual=older[0], single=older[1], base=OLDER, other=other)
        + band_pool(dual=middle[0], single=middle[1], base=MIDDLE, other=other)
        + band_pool(dual=recent[0], single=recent[1], base=RECENT, other=other)
        + frozen_seven()
    )


def counts(chosen):
    out = {}
    for c in chosen:
        key = (c["selection_origin"], c["validation_tier"])
        out[key] = out.get(key, 0) + 1
    return out


# ---- quotas, mandatory ids, tiers -----------------------------------------------------------------------------------------------------------------


def test_exactly_50_with_the_frozen_quotas_and_all_mandatory_ids():
    chosen = sel.select(full_pool())
    numbers = [c["number"] for c in chosen]
    assert len(numbers) == 50 == len(set(numbers)) and set(sel.MANDATORY) <= set(numbers)
    by_band = {b: sum(1 for c in chosen if c["selection_origin"] == f"sampled:{b}") for b in ("older", "middle", "recent")}
    assert by_band == {"older": 14, "middle": 15, "recent": 14}
    assert numbers == sorted(numbers, key=lambda n: int(n.split("-")[1]))


def test_when_a_band_has_enough_dual_candidates_only_dual_is_used_and_single_is_ignored():
    chosen = sel.select(full_pool(older=(20, 40), middle=(40, 40), recent=(20, 40)))
    assert counts(chosen) == {
        ("phase2_frozen", "phase2_mandatory"): 7,
        ("sampled:older", "dual_reference"): 14,
        ("sampled:middle", "dual_reference"): 15,
        ("sampled:recent", "dual_reference"): 14,
    }


def test_the_observed_attempt1_shape_all_dual_are_taken_then_single_fills_the_deficit():
    pool = full_pool(older=(9, 31), middle=(34, 46), recent=(2, 38))
    chosen = sel.select(pool)
    assert counts(chosen) == {
        ("phase2_frozen", "phase2_mandatory"): 7,
        ("sampled:older", "dual_reference"): 9, ("sampled:older", "single_reference_fallback"): 5,
        ("sampled:middle", "dual_reference"): 15,
        ("sampled:recent", "dual_reference"): 2, ("sampled:recent", "single_reference_fallback"): 12,
    }
    # every dual candidate of a short band is in the set
    dual_older = {c["number"] for c in pool if c["band"] == "older" and c["external_reference_count"] == 2}
    assert dual_older <= {c["number"] for c in chosen}
    # the single-reference picks are the even stride over ascending single candidates
    singles = sorted((c["number"] for c in pool if c["band"] == "older" and c["external_reference_count"] == 1), key=lambda n: int(n.split("-")[1]))
    expected = [singles[((2 * j + 1) * len(singles)) // (2 * 5)] for j in range(5)]
    got = [c["number"] for c in chosen if c["validation_tier"] == "single_reference_fallback" and c["selection_origin"] == "sampled:older"]
    assert got == expected


def test_the_middle_band_stride_is_exactly_the_documented_formula_over_dual_candidates():
    pool = full_pool(middle=(34, 46))
    duals = sorted((c["number"] for c in pool if c["band"] == "middle" and c["external_reference_count"] == 2), key=lambda n: int(n.split("-")[1]))
    expected = {duals[((2 * j + 1) * 34) // (2 * 15)] for j in range(15)}
    assert {c["number"] for c in sel.select(pool) if c["selection_origin"] == "sampled:middle"} == expected


# ---- who may never be sampled ---------------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("states", [("negative", "negative"), ("unavailable", "unavailable"), ("negative", "unavailable"), ("unavailable", "negative")])
def test_zero_confirmed_candidates_are_never_sampled_even_when_they_would_complete_the_quota(states):
    valid = band_pool(dual=3, single=6, base=OLDER)  # 9 usable, quota 14
    junk = [cand(OLDER + 500_000 + i * 1000, *states) for i in range(50)]
    pool = valid + junk + band_pool(dual=40, single=0, base=MIDDLE) + band_pool(dual=40, single=0, base=RECENT) + frozen_seven()
    with pytest.raises(sel.SelectionError, match="older"):
        sel.select(pool)


def test_junk_candidates_are_ignored_when_enough_valid_ones_exist_and_mandatory_ids_need_no_external_reference():
    chosen = sel.select(full_pool(junk=True))
    for c in chosen:
        if c["selection_origin"].startswith("sampled:"):
            assert c["external_reference_count"] >= 1 and c["validation_tier"] in {"dual_reference", "single_reference_fallback"}
    mandatory = [c for c in chosen if c["selection_origin"] == "phase2_frozen"]
    assert {c["number"] for c in mandatory} == set(PHASE2_SEVEN) and all(c["external_reference_count"] == 0 for c in mandatory)
    assert all(c["validation_tier"] == "phase2_mandatory" for c in mandatory)


def test_a_mandatory_id_is_kept_even_when_its_lookups_were_unavailable():
    chosen = sel.select(full_pool()[:-7] + frozen_seven(sukebei="unavailable", netflav="unavailable"))
    assert set(sel.MANDATORY) <= {c["number"] for c in chosen}


def test_a_short_band_that_tier1_plus_tier2_cannot_fill_is_an_error_never_a_silent_shift():
    with pytest.raises(sel.SelectionError, match=r"band 'recent' has 2 dual \+ 5 single-reference candidates, needs 14"):
        sel.select(full_pool(recent=(2, 5)))
    with pytest.raises(sel.SelectionError, match="lacks Phase 2 frozen"):
        sel.select([c for c in full_pool() if c["number"] != "FC2-4825061"])
    with pytest.raises(sel.SelectionError, match="non-canonical"):
        sel.select(full_pool() + [{"number": "not-a-number"}])


def test_inconsistent_or_missing_reference_evidence_is_refused():
    pool = full_pool()
    liar = cand(OLDER + 123_456, "confirmed", "negative")
    liar["external_reference_count"] = 2
    with pytest.raises(sel.SelectionError, match="disagrees"):
        sel.select(pool + [liar])
    naked = cand(OLDER + 123_456)
    del naked["reference_checks"]
    with pytest.raises(sel.SelectionError, match="missing reference_checks"):
        sel.select(pool + [naked])


def test_the_document_level_guards_refuse_an_incomplete_or_old_schema_pool():
    for bad in (pool_doc(full_pool(), complete=False), pool_doc(full_pool(), schema=1), {"schema_version": 2, "prefix_enumeration_complete": True}):
        with pytest.raises(sel.SelectionError):
            sel.build_set_document(bad, "0" * 64, created_at="x")


# ---- determinism ---------------------------------------------------------------------------------------------------------------------------------------


def test_the_same_pool_selected_100_times_gives_the_same_numbers():
    pool = full_pool(older=(9, 31), middle=(34, 46), recent=(2, 38))
    baseline = [c["number"] for c in sel.select(pool)]
    for _ in range(100):
        assert [c["number"] for c in sel.select(pool)] == baseline


def test_input_order_duplicates_and_dict_key_order_do_not_change_the_selection():
    pool = full_pool(older=(9, 31), middle=(34, 46), recent=(2, 38))
    baseline = [(c["number"], c["validation_tier"]) for c in sel.select(pool)]
    for seed in range(20):
        shuffled = [dict(reversed(list(c.items()))) for c in pool] + [dict(c) for c in pool[:9]]
        for c in shuffled:
            c["reference_checks"] = {k: dict(reversed(list(v.items()))) for k, v in reversed(list(c["reference_checks"].items()))}
        random.Random(seed).shuffle(shuffled)
        assert [(c["number"], c["validation_tier"]) for c in sel.select(shuffled)] == baseline


def test_the_set_ids_do_not_depend_on_the_clock_only_created_at_does():
    doc = pool_doc(full_pool(older=(9, 31), middle=(34, 46), recent=(2, 38)))
    a = sel.build_set_document(doc, "a" * 64, created_at="2026-01-01T00:00:00+00:00")
    b = sel.build_set_document(doc, "a" * 64, created_at="2031-12-31T23:59:59+00:00")
    assert [i["number"] for i in a["ids"]] == [i["number"] for i in b["ids"]] and a["created_at"] != b["created_at"]
    assert {**a, "created_at": None} == {**b, "created_at": None}


def test_the_selection_function_uses_no_randomness_clock_network_or_engine():
    tree = ast.parse(TOOL.read_text(encoding="utf-8"))
    imported = {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    imported |= {n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
    assert not imported & {"random", "secrets", "time", "socket", "httpx", "requests", "urllib", "asyncio"}
    assert not any(m.startswith("fc2_metadata_core.") and m.split(".")[1] in {"aggregation", "sources", "http"} for m in (
        n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module))
    source = TOOL.read_text(encoding="utf-8")
    body = source[source.index("def select("):source.index("def _check_pool_document")]
    assert "datetime" not in body and "random" not in body and "time." not in body


# ---- output document ----------------------------------------------------------------------------------------------------------------------------------


def test_set_document_marks_every_id_with_its_evidence_tier_and_keeps_the_reference_checks():
    doc = sel.build_set_document(pool_doc(full_pool(older=(9, 31), middle=(34, 46), recent=(2, 38))), "b" * 64, created_at="2026-09-20T00:00:00+00:00")
    assert doc["selection_method"]["id"] == "PHASE3-50ID-SELECTION-v2" and doc["candidate_pool"]["sha256"] == "b" * 64
    assert doc["evidence_tier_counts"] == {"dual_reference": 26, "phase2_mandatory": 7, "single_reference_fallback": 17}
    assert len(doc["ids"]) == 50
    for item in doc["ids"]:
        assert {"number", "band", "selection_origin", "validation_tier", "external_reference_count", "validity_sources",
                "reference_checks", "validity_note", "validation_date"} <= set(item)
    dumped = json.dumps(doc).lower()
    for forbidden in ("cookie", "authorization", "token", "password", "<html", "set-cookie", "aggregate", "coverage"):
        assert forbidden not in dumped


def test_main_writes_nothing_when_selection_fails_and_never_overwrites():
    with tempfile.TemporaryDirectory() as directory:
        pool_path, out = Path(directory) / "pool.json", Path(directory) / "set.json"
        pool_path.write_text(json.dumps(pool_doc(full_pool(recent=(2, 5)))), encoding="utf-8")
        with pytest.raises(SystemExit, match="selection failed, nothing written"):
            sel.main(["--pool", str(pool_path), "--out", str(out)])
        assert not out.exists()
        pool_path.write_text(json.dumps(pool_doc(full_pool())), encoding="utf-8")
        assert sel.main(["--pool", str(pool_path), "--out", str(out)]) == 0 and out.exists()
        with pytest.raises(SystemExit, match="refusing to overwrite"):
            sel.main(["--pool", str(pool_path), "--out", str(out)])


def test_the_frozen_constants_are_unchanged_from_v1():
    assert sel.MANDATORY == PHASE2_SEVEN
    assert [(n, lo, hi, q) for n, lo, hi, q in sel.BANDS] == [("older", 0, 2_000_000, 14), ("middle", 2_000_000, 4_000_000, 15), ("recent", 4_000_000, 10**9, 14)]
    assert sum(q for *_, q in sel.BANDS) + len(sel.MANDATORY) == sel.TOTAL == 50
