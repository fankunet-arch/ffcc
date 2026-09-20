"""Phase 3 C3: the acceptance tooling (candidate-pool builder, deterministic selector, 50-ID gate runner).

Fully offline. Guards what makes the gate trustworthy: the selection is deterministic and cannot see engine
results; the pool builder is engine-independent; the runner's metric counts PARTIAL-with-metadata as covered,
FAILED as not covered, flags M1 violations, and records nothing that could be a body / cookie / title.
"""

from __future__ import annotations

import ast
import asyncio
import importlib.util
import json
import random
import tempfile
from pathlib import Path

import httpx
import pytest

from fc2_metadata_core.aggregation import AggregationConfig, MultiSourceEngine, RetryPolicy, SourceConfig
from fc2_metadata_core.models.source_result import SourceErrorKind, SourceStatus
from fc2_metadata_core.sources import SourceRegistry

from support.fake_http_client import FakeHttpClient
from support.scripted_adapters import failed, ok, scripted_adapter_class

TOOLS = Path(__file__).resolve().parents[3] / "tools"


def load(name):
    spec = importlib.util.spec_from_file_location(f"{name}_under_test", TOOLS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


pool_tool = load("build_candidate_pool")
select_tool = load("select_50id_set")
gate = load("run_50id_coverage_gate")

N = "FC2-4979299"
SECRET = "SECRET-COOKIE-abc123"


# ---- independence: none of the acceptance tools may touch aggregation results ------------------------------------------------------------------


def imported_modules(path: Path) -> set[str]:
    found: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            found |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
    return found


@pytest.mark.parametrize("tool", ["build_candidate_pool", "select_50id_set"])
def test_pool_builder_and_selector_are_engine_independent(tool):
    mods = imported_modules(TOOLS / f"{tool}.py")
    banned = [m for m in mods if m.startswith(("fc2_metadata_core.aggregation", "fc2_metadata_core.sources", "fc2_metadata_core.http"))]
    assert banned == [], f"{tool} must not import the engine / adapters / transport: {banned}"


# ---- candidate pool builder ---------------------------------------------------------------------------------------------------------------------


SUKEBEI_PAGE = """
<table><tbody>
<tr class="default"><td><a href="/view/101" title="FC2-PPV-2304688 素人 title A">x</a></td></tr>
<tr class="default"><td><a href="/view/102" title="FC2PPV_2304688 mirror">x</a></td></tr>
<tr class="default"><td><a href="/view/103" title="[1080p] FC2 PPV 2305735 B">x</a></td></tr>
<tr class="default"><td><a href="/view/104" title="FC2-PPV-83654 old six digit">x</a></td></tr>
<tr class="default"><td><a href="/view/105" title="FC2-PPV-23047 too short? no five digits">x</a></td></tr>
<tr class="default"><td><a href="/view/106" title="no fc2 here 2399999">x</a></td></tr>
<tr class="default"><td><a href="/view/107" title="FC2-PPV-12345678901 too long">x</a></td></tr>
</tbody></table>
FC2-PPV-2311111 outside any row title must be ignored
"""


def test_sukebei_ids_come_from_torrent_names_only_and_are_counted():
    counts = pool_tool.sukebei_torrent_ids(SUKEBEI_PAGE)
    assert counts["2304688"] == 2 and counts["2305735"] == 1 and counts["83654"] == 1 and counts["23047"] == 1
    assert "2399999" not in counts and "2311111" not in counts and "12345678901" not in counts


def test_prefix_candidates_keep_only_seven_digit_ids_with_the_prefix_ascending():
    counts = pool_tool.sukebei_torrent_ids(SUKEBEI_PAGE)
    assert pool_tool.prefix_candidates(counts, "23") == ["2304688", "2305735"]
    assert pool_tool.prefix_candidates(counts, "99") == []


def test_pick_per_prefix_is_an_even_deterministic_stride():
    ids = [str(2_000_000 + i) for i in range(10)]
    assert pool_tool.pick_per_prefix(ids, 4) == [ids[1], ids[3], ids[6], ids[8]]
    assert pool_tool.pick_per_prefix(ids, 4) == pool_tool.pick_per_prefix(list(ids), 4)
    assert pool_tool.pick_per_prefix(ids[:3], 4) == ids[:3]
    assert pool_tool.pick_per_prefix([], 4) == []


def netflav_page(*codes):
    docs = [{"code": c, "title": "t"} for c in codes]
    payload = {"props": {"initialState": {"search": {"docs": docs}}}}
    return f'<html><script id="__NEXT_DATA__" type="application/json">{json.dumps(payload)}</script></html>'


def test_netflav_needs_an_exact_code_match_not_a_fuzzy_neighbour():
    page = netflav_page("fc2-ppv 4825061", "FC2-PPV-1825061")
    assert pool_tool.netflav_exact_hit(page, "4825061") is True
    assert pool_tool.netflav_exact_hit(page, "1825061") is True
    assert pool_tool.netflav_exact_hit(page, "4825062") is False
    assert pool_tool.netflav_exact_hit(netflav_page("FC2-PPV-1825061"), "4825061") is False, "fuzzy neighbour must not corroborate"
    assert pool_tool.netflav_exact_hit(netflav_page("abc 4825061"), "4825061") is False


@pytest.mark.parametrize("html", ["", "<html></html>", '<script id="__NEXT_DATA__">{not json</script>', '<script id="__NEXT_DATA__">{"props":{}}</script>',
                                  '<script id="__NEXT_DATA__">{"props":{"initialState":{"search":{"docs":"x"}}}}</script>'])
def test_netflav_malformed_pages_are_simply_not_a_hit(html):
    assert pool_tool.netflav_exact_hit(html, "4825061") is False


def test_references_treat_any_failure_as_not_confirmed_and_never_raise():
    calls = []

    def handler(request):
        calls.append(str(request.url))
        if "netflav" in request.url.host:
            return httpx.Response(503, text="down")
        raise httpx.ConnectError("boom", request=request)

    async def scenario():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            refs = pool_tool.References(client, 0.0)
            return await refs.sukebei("FC2-PPV-23*"), await refs.netflav("2304688"), refs.failures

    assert asyncio.run(scenario()) == ({}, False, 2)


def test_pool_entry_records_sources_and_never_a_body():
    entry = pool_tool._entry("2304688", torrents=2, netflav=True, origin="enumerated", phase2_note=None, today="2026-09-20")
    assert entry["number"] == "FC2-2304688" and entry["band"] == "middle" and entry["external_reference_count"] == 2
    assert entry["validation_date"] == "2026-09-20" and len(entry["validity_sources"]) == 2
    single = pool_tool._entry("2304688", torrents=1, netflav=False, origin="enumerated", phase2_note=None, today="d")
    assert single["external_reference_count"] == 1 and "single-source validation" in single["validity_note"]
    none = pool_tool._entry("1", torrents=0, netflav=False, origin="phase2_frozen", phase2_note="p2", today="d")
    assert none["external_reference_count"] == 0 and any("Phase 2" in s for s in none["validity_sources"])


# ---- deterministic selector ---------------------------------------------------------------------------------------------------------------------


PHASE2_SEVEN = ("FC2-4825061", "FC2-4824605", "FC2-4979299", "FC2-4976588", "FC2-1042815", "FC2-4978035", "FC2-4972767")


def test_the_phase2_frozen_ids_are_the_same_seven_everywhere():
    assert select_tool.MANDATORY == PHASE2_SEVEN == pool_tool.PHASE2_FROZEN_IDS
    assert sum(q for *_, q in select_tool.BANDS) + len(select_tool.MANDATORY) == select_tool.TOTAL == 50


def synthetic_pool(*, older=40, middle=50, recent=40, single_source_every=5):
    entries = []

    def add(n, refs):
        entries.append({"number": f"FC2-{n}", "external_reference_count": refs, "validity_sources": ["a", "b"][:refs] or ["p2"],
                        "validity_note": "n", "validation_date": "2026-09-20", "origin": "enumerated"})

    for i in range(older):
        add(1_000_000 + i * 20_000, 1 if i % single_source_every == 0 else 2)
    for i in range(middle):
        add(2_000_001 + i * 30_000, 1 if i % single_source_every == 0 else 2)
    for i in range(recent):
        add(4_000_003 + i * 20_000, 1 if i % single_source_every == 0 else 2)
    for number in select_tool.MANDATORY:
        add(int(number.split("-")[1]), 0)
    return entries


def test_selector_yields_exactly_50_with_the_frozen_quotas_and_all_mandatory_ids():
    chosen = select_tool.select(synthetic_pool())
    numbers = [c["number"] for c in chosen]
    assert len(numbers) == 50 == len(set(numbers))
    assert set(select_tool.MANDATORY) <= set(numbers)
    sampled = [c for c in chosen if c["selection_origin"].startswith("sampled:")]
    assert {b: sum(1 for c in sampled if c["selection_origin"] == f"sampled:{b}") for b in ("older", "middle", "recent")} == {"older": 14, "middle": 15, "recent": 14}
    assert numbers == sorted(numbers, key=lambda n: int(n.split("-")[1]))


def test_selection_is_deterministic_and_independent_of_input_order_and_duplicates():
    pool = synthetic_pool()
    baseline = [c["number"] for c in select_tool.select(pool)]
    for seed in range(5):
        shuffled = pool + pool[:7]  # duplicates too
        random.Random(seed).shuffle(shuffled)
        assert [c["number"] for c in select_tool.select(shuffled)] == baseline


def test_single_reference_entries_are_never_sampled_but_mandatory_ids_are_kept_regardless():
    chosen = select_tool.select(synthetic_pool())
    for c in chosen:
        if c["selection_origin"].startswith("sampled:"):
            assert c["external_reference_count"] >= 2
    assert {c["number"] for c in chosen if c["selection_origin"] == "phase2_frozen"} == set(select_tool.MANDATORY)


def test_the_selection_spans_older_middle_and_recent_ranges():
    chosen = select_tool.select(synthetic_pool())
    digits = [int(c["number"].split("-")[1]) for c in chosen]
    assert sum(d < 2_000_000 for d in digits) >= 14 and sum(2_000_000 <= d < 4_000_000 for d in digits) >= 15 and sum(d >= 4_000_000 for d in digits) >= 14
    assert max(digits) - min(digits) > 3_000_000


def test_an_insufficient_band_is_an_error_never_a_silent_shift():
    with pytest.raises(select_tool.SelectionError, match="older"):
        select_tool.select(synthetic_pool(older=10))
    with pytest.raises(select_tool.SelectionError, match="lacks Phase 2 frozen"):
        select_tool.select([e for e in synthetic_pool() if e["number"] != "FC2-4825061"])
    with pytest.raises(select_tool.SelectionError, match="non-canonical"):
        select_tool.select(synthetic_pool() + [{"number": "not-a-number", "external_reference_count": 2}])


def test_the_selector_ignores_everything_but_the_pool_no_clock_no_randomness():
    text = (TOOLS / "select_50id_set.py").read_text(encoding="utf-8")
    body = text[text.index("def select("):text.index("def build_set_document")]
    assert "random" not in body and "datetime" not in body and "time." not in body


def test_set_document_has_the_required_fields_and_no_response_data():
    pool_doc = {"entries": synthetic_pool()}
    document = select_tool.build_set_document(pool_doc, "0" * 64, created_at="2026-09-20T00:00:00+00:00")
    assert {"schema_version", "created_at", "selection_method", "ids"} <= set(document)
    assert len(document["ids"]) == 50
    for item in document["ids"]:
        assert {"number", "validity_sources", "validity_note", "validation_date"} <= set(item)
    dumped = json.dumps(document).lower()
    for forbidden in ("cookie", "authorization", "token", "password", "<html", "set-cookie"):
        assert forbidden not in dumped


# ---- the gate runner ---------------------------------------------------------------------------------------------------------------------------------


def scripted(outcomes):
    async def script(number, client):
        return outcomes.pop(0) if len(outcomes) > 1 else outcomes[0]

    return script


def aggregate(scripts, number=N, retry=RetryPolicy(max_attempts=2, initial_backoff_seconds=0.01)):
    registry = SourceRegistry()
    for sid, script in scripts.items():
        registry.register(sid, scripted_adapter_class(sid, script))
    config = AggregationConfig.create([SourceConfig(sid) for sid in scripts], retry_policy=retry)
    return asyncio.run(MultiSourceEngine(config, registry, FakeHttpClient()).aggregate(number))


def test_partial_with_metadata_is_covered_and_reported_as_partial():
    result = aggregate({"fc2db_net": scripted([ok("fc2db_net", N, "Title")]),
                        "javdb": scripted([failed("javdb", SourceStatus.NETWORK_ERROR, error_kind=SourceErrorKind.TIMEOUT)])})
    record = gate.summarize_id(result)
    assert record["aggregate_status"] == "partial" and record["covered"] is True and record["title_present"] is True
    assert gate.compute_summary([record])["covered_but_partial"] == [N]


def test_failed_aggregate_is_not_covered_even_if_a_source_returned_something_odd():
    result = aggregate({"a": scripted([failed("a", SourceStatus.NOT_FOUND)]), "b": scripted([failed("b", SourceStatus.BLOCKED)])})
    record = gate.summarize_id(result)
    assert record["aggregate_status"] == "failed" and record["covered"] is False and record["title_present"] is False


def test_success_is_covered_and_the_metric_uses_meets_minimum_success():
    result = aggregate({"a": scripted([ok("a", N, "T")])})
    assert gate.is_covered(result) is True
    assert result.metadata.meets_minimum_success() is True


def test_records_carry_only_ids_statuses_kinds_counts_and_timings_never_titles_or_error_text():
    transient = failed("flaky", SourceStatus.INVALID_RESPONSE, error_kind=SourceErrorKind.HTTP_SERVER_ERROR, detail=f"flaky: HTTP 500 {SECRET}")
    result = aggregate({"flaky": scripted([transient, ok("flaky", N, "A SECRET TITLE")]), "b": scripted([ok("b", N, "T")])})
    record = gate.summarize_id(result)
    dumped = json.dumps(record)
    assert SECRET not in dumped and "A SECRET TITLE" not in dumped and "error_detail" not in dumped
    flaky = next(s for s in record["sources"] if s["source_id"] == "flaky")
    assert flaky["attempt_count"] == 2 and flaky["retried"] is True and [a["status"] for a in flaky["attempts"]] == ["invalid_response", "success"]
    assert set(flaky) == {"source_id", "final_status", "error_kind", "attempt_count", "retried", "deadline_exceeded", "engine_elapsed_ms", "attempts"}


def make_records():
    good = gate.summarize_id(aggregate({"fc2db_net": scripted([ok("fc2db_net", N, "T")]), "javdb": scripted([failed("javdb", SourceStatus.NOT_FOUND)])}))
    retried = gate.summarize_id(aggregate({"fc2db_net": scripted([failed("fc2db_net", SourceStatus.NETWORK_ERROR, error_kind=SourceErrorKind.TIMEOUT), ok("fc2db_net", N, "T")]),
                                           "javdb": scripted([failed("javdb", SourceStatus.BLOCKED)])}))
    bad = gate.summarize_id(aggregate({"fc2db_net": scripted([failed("fc2db_net", SourceStatus.BLOCKED)]), "javdb": scripted([failed("javdb", SourceStatus.NOT_FOUND)])}))
    return [good, retried, bad]


def test_summary_source_and_retry_statistics_are_computed_from_the_records():
    records = make_records()
    summary = gate.compute_summary(records)
    assert (summary["total"], summary["covered"], summary["not_covered"]) == (3, 2, 1)
    assert summary["coverage_percent"] == 66.67 and summary["numeric_threshold_met"] is False, "total != 50 can never meet the gate"
    stats = gate.compute_source_statistics(records)
    assert stats["fc2db_net"]["final_status_counts"]["success"] == 2 and stats["fc2db_net"]["final_status_counts"]["blocked"] == 1
    assert stats["fc2db_net"]["ids_retried"] == 1 and stats["fc2db_net"]["attempts_total"] == 4
    assert stats["javdb"]["final_status_counts"]["not_found"] == 2 and stats["javdb"]["operational_failures"] == 1
    retry = gate.compute_retry_statistics(records)
    assert retry["live_retries_observed"] == 1 and retry["events"][0]["attempt_kinds"] == ["timeout", "success"]
    assert gate.find_m1_violations(records) == []


def test_a_blocked_source_with_more_than_one_attempt_is_flagged_as_an_m1_violation():
    fake = [{"number": N, "sources": [{"source_id": "javdb", "final_status": "blocked", "attempt_count": 2}]},
            {"number": N, "sources": [{"source_id": "javdb", "final_status": "blocked", "attempt_count": 1}]}]
    assert gate.find_m1_violations(fake) == [{"number": N, "source_id": "javdb", "attempt_count": 2}]


def test_threshold_is_exactly_45_of_50():
    def records(covered):
        return [{"number": f"FC2-{1000000 + i}", "aggregate_status": "success" if i < covered else "failed", "covered": i < covered, "sources": []} for i in range(50)]

    assert gate.compute_summary(records(45))["numeric_threshold_met"] is True
    assert gate.compute_summary(records(44))["numeric_threshold_met"] is False
    assert gate.compute_summary(records(50))["coverage_percent"] == 100.0


class FlakyEngine:
    """A real MultiSourceEngine over one scripted adapter, except that one number makes the call itself raise."""

    def __init__(self):
        self.calls = []
        registry = SourceRegistry()

        async def script(number, client):
            return ok("a", number, "T")

        registry.register("a", scripted_adapter_class("a", script))
        self._engine = MultiSourceEngine(AggregationConfig.create([SourceConfig("a")]), registry, FakeHttpClient())

    async def aggregate(self, number):
        self.calls.append(number)
        if number == "FC2-1000002":
            raise RuntimeError("engine bug")
        return await self._engine.aggregate(number)


def test_run_gate_is_sequential_in_frozen_order_paces_ids_and_never_drops_an_id():
    engine, sleeps, progress = FlakyEngine(), [], []
    numbers = ["FC2-1000001", "FC2-1000002", "FC2-1000003"]

    async def fake_sleep(seconds):
        sleeps.append(seconds)

    records = asyncio.run(gate.run_gate(numbers, engine, 4.0, sleep=fake_sleep, progress=lambda *a: progress.append(a[0])))
    assert engine.calls == numbers and sleeps == [4.0, 4.0] and progress == [1, 2, 3]
    assert [r["number"] for r in records] == numbers
    assert records[1]["covered"] is False and records[1]["aggregate_status"] == "engine_exception" and records[1]["engine_exception_type"] == "RuntimeError"
    assert records[0]["covered"] and records[2]["covered"]


def test_the_runner_has_no_way_to_change_ids_attempts_order_or_deadline_and_enforces_pacing():
    text = (TOOLS / "run_50id_coverage_gate.py").read_text(encoding="utf-8")
    flags = [line for line in text.splitlines() if "add_argument(" in line]
    assert len(flags) == 4 and all(any(f in line for f in ("--run-kind", "--set", "--out-dir", "--delay-seconds")) for line in flags)
    assert "assert retry == RetryPolicy()" in text and "MIN_DELAY_SECONDS = 3.0" in text
    with pytest.raises(SystemExit, match="delay-seconds"):
        gate.main(["--run-kind", "diagnostic", "--set", "x.json", "--out-dir", "y", "--delay-seconds", "1"])


def test_load_frozen_ids_requires_exactly_50_distinct_canonical_ids():
    with tempfile.TemporaryDirectory() as directory:
        def write(numbers):
            path = Path(directory) / "set.json"
            path.write_text(json.dumps({"ids": [{"number": n} for n in numbers]}), encoding="utf-8")
            return path

        good = [f"FC2-{1000000 + i}" for i in range(50)]
        numbers, sha = gate.load_frozen_ids(write(good))
        assert numbers == good and len(sha) == 64
        for bad in (good[:49], good[:49] + [good[0]], good[:49] + ["fc2-1000049"], good[:49] + ["FC2-PPV-1000049"]):
            with pytest.raises(SystemExit):
                gate.load_frozen_ids(write(bad))


def test_markdown_and_evidence_render_and_state_the_verdict():
    records = make_records()
    meta = {"started_at_utc": "s", "finished_at_utc": "f", "code_head": "h", "worktree_clean": True, "set_file": "x", "set_file_sha256": "0" * 64,
            "set_last_commit": "c", "config": {"source_order": ["fc2db_net", "javdb"], "max_concurrency": 3, "deadline_seconds": 20.0,
                                                "retry_policy": {}, "delay_between_ids_seconds": 4.0}}
    evidence = gate.build_evidence(records, run_kind="primary", meta=meta)
    json.dumps(evidence)
    markdown = gate.render_markdown(evidence)
    assert "BELOW THRESHOLD" in markdown and "PRIMARY" in markdown and "formal acceptance result" in markdown
    assert evidence["uncovered"][0]["number"] == N and evidence["m1_violations"] == []
    diagnostic = gate.render_markdown(gate.build_evidence(records, run_kind="diagnostic", meta=meta))
    assert "does NOT replace the primary" in diagnostic
