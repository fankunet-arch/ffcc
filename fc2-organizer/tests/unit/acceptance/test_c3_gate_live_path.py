"""Phase 3 C3: the gate runner's exact live code path, run OFFLINE.

Real ``MultiSourceEngine`` + real adapters + real ``HttpxTransport`` over ``httpx.MockTransport``, driven through
``run_50id_coverage_gate._live`` -- the very function the one-shot primary run uses -- so a latent bug in it
cannot first appear during the formal run. Also pins the primary-run refusal guards (they fire before any network use).
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import tempfile
from pathlib import Path

import httpx
import pytest

from support.source_fixtures import load_fixture

TOOL = Path(__file__).resolve().parents[3] / "tools" / "run_50id_coverage_gate.py"
_spec = importlib.util.spec_from_file_location("run_50id_coverage_gate_live_under_test", TOOL)
gate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gate)

N = "FC2-4979299"


def site_handler(request: httpx.Request) -> httpx.Response:
    host = request.url.host
    if "fc2db" in host:
        return httpx.Response(200, text=load_fixture("fc2db_net/work_4979299.html"))
    if "javdb" in host:
        return httpx.Response(200, text=load_fixture("javdb/search_hit_4979299.html"))
    return httpx.Response(404, text="not here")  # av123


def test_the_live_code_path_runs_end_to_end_offline_with_the_frozen_default_config():
    records, config = asyncio.run(gate._live([N, N], 0.0, http_transport=httpx.MockTransport(site_handler)))
    assert [r["number"] for r in records] == [N, N]
    for record in records:
        assert record["covered"] is True and record["aggregate_status"] == "success", record
        finals = {s["source_id"]: (s["final_status"], s["attempt_count"]) for s in record["sources"]}
        assert finals == {"fc2db_net": ("success", 1), "javdb": ("success", 1), "av123": ("not_found", 1)}
    assert config["source_order"] == ["fc2db_net", "javdb", "av123"] and config["max_concurrency"] == 3
    assert config["retry_policy"]["max_attempts"] == 2 and config["deadline_seconds"] == 20.0
    json.dumps(records)


def test_a_challenge_under_503_on_the_live_path_is_blocked_with_one_attempt_and_no_m1_violation():
    def handler(request):
        if "javdb" in request.url.host:
            return httpx.Response(503, text="<html><head><title>Just a moment...</title></head></html>")  # no cf-mitigated header
        return site_handler(request)

    records, _ = asyncio.run(gate._live([N], 0.0, http_transport=httpx.MockTransport(handler)))
    javdb = next(s for s in records[0]["sources"] if s["source_id"] == "javdb")
    assert (javdb["final_status"], javdb["error_kind"], javdb["attempt_count"]) == ("blocked", "blocked", 1)
    assert records[0]["aggregate_status"] == "partial" and records[0]["covered"] is True
    assert gate.find_m1_violations(records) == []


def test_a_transient_503_that_recovers_is_covered_and_recorded_as_a_live_retry():
    calls = {"n": 0}

    def handler(request):
        if "av123" in request.url.host or "123av" in request.url.host:
            calls["n"] += 1
            return httpx.Response(503, text="upstream") if calls["n"] == 1 else httpx.Response(404, text="nope")
        return site_handler(request)

    records, _ = asyncio.run(gate._live([N], 0.0, http_transport=httpx.MockTransport(handler)))
    av123 = next(s for s in records[0]["sources"] if s["source_id"] == "av123")
    assert av123["attempt_count"] == 2 and av123["retried"] is True and [a["error_kind"] for a in av123["attempts"]] == ["http_server_error", "not_found"]
    retry = gate.compute_retry_statistics(records)
    assert retry["live_retries_observed"] == 1 and retry["events"][0]["source_id"] == "av123"


def test_primary_run_refusals_happen_before_any_network_access(monkeypatch):
    def boom(*args, **kwargs):
        raise AssertionError("must refuse before running the engine")

    monkeypatch.setattr(gate, "_live", boom)
    with tempfile.TemporaryDirectory() as directory:
        set_path = Path(directory) / "set.json"
        set_path.write_text(json.dumps({"ids": [{"number": f"FC2-{1000000 + i}"} for i in range(50)]}), encoding="utf-8")
        out_dir = Path(directory) / "evidence"
        argv = ["--run-kind", "primary", "--set", str(set_path), "--out-dir", str(out_dir)]

        with pytest.raises(SystemExit, match="inside the repository"):
            gate.main(argv)

        clean = {"code_head": "h", "worktree_clean": True, "set_committed_unchanged": True, "set_last_commit": "c"}
        monkeypatch.setattr(gate, "git_state", lambda p: {**clean, "worktree_clean": False})
        with pytest.raises(SystemExit, match="not clean"):
            gate.main(argv)
        monkeypatch.setattr(gate, "git_state", lambda p: {**clean, "set_committed_unchanged": False})
        with pytest.raises(SystemExit, match="not committed unchanged"):
            gate.main(argv)
        monkeypatch.setattr(gate, "git_state", lambda p: clean)
        out_dir.mkdir()
        (out_dir / "PHASE3_50_ID_GATE_PRIMARY_20260101T000000Z.json").write_text("{}", encoding="utf-8")
        with pytest.raises(SystemExit, match="one primary run only"):
            gate.main(argv)
