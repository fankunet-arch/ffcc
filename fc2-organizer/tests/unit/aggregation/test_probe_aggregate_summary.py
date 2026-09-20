"""tools/probe_aggregate.py (C2): the live-smoke summary reports each source's FINAL status AND its
attempt diagnostics, and stays free of bodies / headers / cookies / error text of attempts.

Fully offline: the real tool's ``summarize`` runs on a real ``AggregationResult`` produced by the real
engine over scripted adapters.
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
from pathlib import Path

from fc2_metadata_core.aggregation import AggregationConfig, MultiSourceEngine, RetryPolicy, SourceConfig
from fc2_metadata_core.models.source_result import SourceErrorKind, SourceStatus
from fc2_metadata_core.sources import SourceRegistry

from support.fake_http_client import FakeHttpClient
from support.scripted_adapters import failed, ok, scripted_adapter_class

TOOL = Path(__file__).resolve().parents[3] / "tools" / "probe_aggregate.py"
_spec = importlib.util.spec_from_file_location("probe_aggregate_under_test", TOOL)
probe = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(probe)

N = "FC2-4979299"
SECRET = "SECRET-COOKIE-abc123"


def scripted(outcomes):
    calls = []

    async def script(number, client):
        calls.append(number)
        return outcomes.pop(0) if len(outcomes) > 1 else outcomes[0]

    return script


def aggregate(scripts, retry):
    registry = SourceRegistry()
    for sid, script in scripts.items():
        registry.register(sid, scripted_adapter_class(sid, script))
    config = AggregationConfig.create([SourceConfig(sid) for sid in scripts], retry_policy=retry)
    return asyncio.run(MultiSourceEngine(config, registry, FakeHttpClient()).aggregate(N))


def test_summary_reports_final_status_attempt_count_and_the_first_attempt_failure():
    transient = failed(
        "flaky", SourceStatus.INVALID_RESPONSE, error_kind=SourceErrorKind.HTTP_SERVER_ERROR, detail=f"flaky: HTTP 500 {SECRET}"
    )
    result = aggregate(
        {
            "flaky": scripted([transient, ok("flaky", N, "T")]),
            "steady": scripted([ok("steady", N, "T")]),
            "gone": scripted([failed("gone", SourceStatus.NOT_FOUND)]),
        },
        RetryPolicy(max_attempts=2, initial_backoff_seconds=0.01),
    )
    summary = probe.summarize(result)
    by_id = {entry["source_id"]: entry for entry in summary["sources"]}

    assert by_id["flaky"]["status"] == "success" and by_id["flaky"]["attempt_count"] == 2 and by_id["flaky"]["retried"] is True
    first, second = by_id["flaky"]["attempts"]
    assert (first["sequence"], first["status"], first["error_kind"]) == (1, "invalid_response", "http_server_error")
    assert (second["sequence"], second["status"], second["error_kind"]) == (2, "success", None)
    assert second["backoff_before_seconds"] == 0.01

    assert by_id["steady"]["attempt_count"] == 1 and by_id["steady"]["retried"] is False
    assert by_id["gone"]["status"] == "not_found" and by_id["gone"]["attempt_count"] == 1, "NOT_FOUND is never retried"
    assert summary["aggregate_status"] == "success"


def test_summary_is_json_serialisable_and_carries_no_attempt_error_text():
    transient = failed("a", SourceStatus.NETWORK_ERROR, error_kind=SourceErrorKind.TIMEOUT, detail=f"a: timeout {SECRET}")
    result = aggregate({"a": scripted([transient, transient]), "b": scripted([ok("b", N, "T")])}, RetryPolicy(max_attempts=2, initial_backoff_seconds=0.01))
    summary = probe.summarize(result)
    entry = next(e for e in summary["sources"] if e["source_id"] == "a")
    assert entry["status"] == "network_error" and entry["error_kind"] == "timeout" and entry["attempt_count"] == 2
    assert all(set(a) == {"sequence", "status", "error_kind", "elapsed_ms", "backoff_before_seconds", "completed"} for a in entry["attempts"])
    json.dumps(summary)  # must be serialisable as-is
    assert summary["aggregate_status"] == "partial"


def test_tool_default_is_to_write_no_file():
    text = TOOL.read_text(encoding="utf-8")
    assert "--out" in text and "nothing is recorded otherwise" in text
    assert text.count("write_text(") == 1 and "if args.out:" in text
