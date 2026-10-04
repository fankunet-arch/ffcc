"""P5-C1 §21 / I12 / I23：诊断与敏感信息——唯一的日志、封闭词汇、不泄漏。"""

from __future__ import annotations

import ast
import logging
from pathlib import Path

import pytest

from _amane_scenarios import client_4825061, client_4824605_not_found_everywhere, lookup, runtime_for, url_for
from fc2_amane_adapter import _bridge, _core_gate, _number, _outcome, _runtime, _settings
from fc2_amane_adapter._outcome import AdapterFailure
from fc2_amane_adapter._settings import AdapterConfigError, parse_settings
from support.amane_host_fakes import FakeHostBridge, FakeRequestError, FakeResponse, FakeSourceError

HOST_ERRORS = {"bridge_type": FakeHostBridge}
HOSTILE = "SENTINEL-SECRET-7731 https://leak.example/p?token=abc cookie=session C:\\Users\\me\\x"
TREE = [Path(m.__file__) for m in (_bridge, _core_gate, _number, _outcome, _runtime, _settings)]


def test_exactly_one_logger_and_one_warning_call_exist_in_the_adapter_tree():
    loggers, calls = [], []
    for path in TREE + [path.parent / "plugin.py" for path in TREE[:1]]:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr == "getLogger":
                    loggers.append((path.name, [ast.unparse(a) for a in node.args]))
                if node.func.attr in {"debug", "info", "warning", "error", "exception", "critical", "log"}:
                    calls.append((path.name, node.func.attr))
            if isinstance(node, ast.Name):
                assert node.id not in {"print", "structlog"}, path.name
    assert loggers == [("_runtime.py", ["LOGGER_NAME"])]
    assert _runtime.LOGGER_NAME == "ffcc.fc2_metadata"
    assert calls == [("_runtime.py", "warning")]


def test_hostile_host_details_never_reach_logs_or_errors(caplog):
    caplog.set_level(logging.DEBUG)
    client = client_4825061()
    client.replace(url_for("fc2db_net", "4825061"), FakeRequestError("network", detail=HOSTILE, url=HOSTILE))
    client.replace(url_for("javdb", "4825061"), FakeSourceError("unexpected", detail=HOSTILE, url=HOSTILE))
    outcome = lookup(runtime_for(client, **HOST_ERRORS), "FC2-4825061")
    assert "SENTINEL" not in repr(outcome) and "leak" not in repr(outcome)
    assert "SENTINEL" not in caplog.text and "token=abc" not in caplog.text and "Users" not in caplog.text


def test_failure_outputs_never_contain_hostile_text_even_when_every_source_fails(caplog):
    caplog.set_level(logging.DEBUG)
    client = client_4824605_not_found_everywhere()
    for source_id in ("fc2db_net", "javdb", "av123"):
        client.replace(url_for(source_id, "4824605"), FakeRequestError("unexpected", detail=HOSTILE, url=HOSTILE))
    outcome = lookup(runtime_for(client, **HOST_ERRORS), "FC2-4824605")
    assert isinstance(outcome, AdapterFailure)
    assert "SENTINEL" not in outcome.detail and "http" not in outcome.detail
    assert not [r for r in caplog.records if "SENTINEL" in r.getMessage()]


def test_host_response_bodies_and_headers_never_appear_in_failures(caplog):
    caplog.set_level(logging.DEBUG)
    client = client_4825061()
    body = f"<html><title>Just a moment...</title>{HOSTILE}</html>"
    client.replace(url_for("fc2db_net", "4825061"), FakeResponse.html(body, status=403, extra_headers=[("Set-Cookie", HOSTILE)]))
    outcome = lookup(runtime_for(client, **HOST_ERRORS), "FC2-4825061")
    text = repr(outcome) + caplog.text
    assert "SENTINEL" not in text and "Set-Cookie" not in text and "Just a moment" not in text


def test_settings_error_messages_do_not_echo_values():
    with pytest.raises(AdapterConfigError) as excinfo:
        parse_settings({"sources": [{"id": "javdb", "base_url": f"https://u:{HOSTILE.split()[0]}@mirror.example"}]})
    assert "SENTINEL" not in str(excinfo.value)
