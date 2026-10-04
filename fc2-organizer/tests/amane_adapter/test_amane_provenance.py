"""P5-C1 表 I（E13 纯逻辑部分）：来源归属——Amane 可见输出不含任何内部 provenance；词汇封闭。
真实 ``amane.aggregate`` 的见证见 H-12。"""

from __future__ import annotations

import dataclasses
import re

from _amane_scenarios import client_4825061, client_4979299, client_4824605_not_found_everywhere, lookup, runtime_for, url_for
from fc2_amane_adapter._outcome import AdapterFailure, AdapterFound, AdapterRecord
from fc2_amane_adapter._runtime import PARTIAL_LOG_FORMAT
from fc2_metadata_core.aggregation import DEFAULT_SOURCE_ORDER
from support.amane_host_fakes import FakeHostBridge, FakeRequestError

REQUEST_ERRORS = {"bridge_type": FakeHostBridge}
DETAIL_RE = re.compile(r"^FC2 lookup failed: [a-z0-9_]+=[a-z_]+(; [a-z0-9_]+=[a-z_]+)*$")
INTERNAL_NAMES = {"field_sources", "external_ids", "source_urls", "conflicts", "contributing_source_ids", "source_results",
                  "source_execution_traces", "fanart_urls", "provenance"}


def test_record_has_no_internal_provenance_fields():
    assert not {f.name for f in dataclasses.fields(AdapterRecord)} & INTERNAL_NAMES


def test_single_source_identity_is_left_to_the_host():
    outcome = lookup(runtime_for(client_4979299()), "FC2-PPV-4979299")
    assert isinstance(outcome, AdapterFound)
    values = [value for value in dataclasses.astuple(outcome.record)]
    flat = [item for value in values for item in (value if isinstance(value, tuple) else (value,))]
    for source_id in DEFAULT_SOURCE_ORDER:
        assert not any(isinstance(item, str) and item == source_id for item in flat)
    assert outcome.record.external_id.isdigit()


def test_failure_detail_is_a_closed_vocabulary_over_many_scenarios():
    seen = []
    for builder, number in ((client_4824605_not_found_everywhere, "FC2-4824605"), (client_4825061, "FC2-4825061")):
        for kind in ("timeout", "network", "unexpected"):
            client = builder()
            client.replace(url_for("javdb", number[4:]), FakeRequestError(kind, detail="SECRET https://leak.example/?k=1"))
            outcome = lookup(runtime_for(client, **REQUEST_ERRORS), number)
            if isinstance(outcome, AdapterFailure):
                seen.append(outcome)
                assert DETAIL_RE.fullmatch(outcome.detail), outcome.detail
                assert "SECRET" not in outcome.detail and "leak" not in outcome.detail
                for token in re.findall(r"([a-z0-9_]+)=", outcome.detail):
                    assert token in DEFAULT_SOURCE_ORDER
    assert seen


def test_partial_log_line_is_closed_vocabulary_only(caplog):
    client = client_4825061()
    client.replace(url_for("fc2db_net", "4825061"), FakeRequestError("network", detail="SECRET https://leak.example"))
    caplog.set_level("DEBUG")
    outcome = lookup(runtime_for(client, **REQUEST_ERRORS), "FC2-4825061")
    assert isinstance(outcome, AdapterFound) and outcome.degraded
    messages = [record.getMessage() for record in caplog.records if record.name == "ffcc.fc2_metadata"]
    assert messages == [PARTIAL_LOG_FORMAT % ("FC2-4825061", "fc2db_net=connection_error")]
    assert "SECRET" not in caplog.text and "leak" not in caplog.text
