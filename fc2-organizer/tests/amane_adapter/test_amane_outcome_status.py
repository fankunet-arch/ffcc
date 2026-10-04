"""P5-C1 表 F（E10）：SUCCESS / PARTIAL / FAILED -> 中立结果；PARTIAL 是可用结果且恰好一条 WARNING。"""

from __future__ import annotations

import logging

import pytest

from _amane_scenarios import (
    TITLE_4825061,
    client_4825061,
    client_4824605_not_found_everywhere,
    lookup,
    runtime_for,
    url_for,
)
from fc2_amane_adapter._outcome import AdapterFailure, AdapterFound, AdapterNoMatch
from fc2_amane_adapter._runtime import LOGGER_NAME
from support.amane_host_fakes import FakeHostBridge, FakeRequestError

REQUEST_ERRORS = {"bridge_type": FakeHostBridge}


def test_success_returns_a_usable_record_with_nothing_degraded(caplog):
    caplog.set_level(logging.DEBUG)
    outcome = lookup(runtime_for(client_4825061(), **REQUEST_ERRORS))
    assert isinstance(outcome, AdapterFound)
    assert outcome.degraded == ()
    assert outcome.record.number == "FC2-4825061" and outcome.record.title == TITLE_4825061
    assert not [r for r in caplog.records if r.name == LOGGER_NAME]


def test_partial_returns_the_usable_record_and_exactly_one_warning(caplog):
    client = client_4825061()
    client.replace(url_for("fc2db_net", "4825061"), FakeRequestError("network", detail="HOST SECRET https://x"))
    caplog.set_level(logging.DEBUG)
    outcome = lookup(runtime_for(client, **REQUEST_ERRORS))
    assert isinstance(outcome, AdapterFound), outcome
    assert outcome.record.title == TITLE_4825061
    assert outcome.degraded == (("fc2db_net", "connection_error"),)
    records = [r for r in caplog.records if r.name == LOGGER_NAME]
    assert len(records) == 1 and records[0].levelno == logging.WARNING
    assert records[0].getMessage() == "partial FC2 result for FC2-4825061: fc2db_net=connection_error"
    assert "SECRET" not in caplog.text and "http" not in records[0].getMessage()


def test_partial_degraded_list_follows_configuration_order():
    client = client_4825061()
    client.replace(url_for("fc2db_net", "4825061"), FakeRequestError("timeout"))
    client.replace(url_for("av123", "4825061"), FakeRequestError("network"))
    for order, expected in (
        (["fc2db_net", "javdb", "av123"], (("fc2db_net", "timeout"), ("av123", "connection_error"))),
        (["av123", "javdb", "fc2db_net"], (("av123", "connection_error"), ("fc2db_net", "timeout"))),
    ):
        outcome = lookup(runtime_for(client, {"sources": [{"id": i} for i in order]}, **REQUEST_ERRORS))
        assert isinstance(outcome, AdapterFound) and outcome.degraded == expected


def test_all_not_found_is_no_match_not_an_error():
    assert lookup(runtime_for(client_4824605_not_found_everywhere()), "FC2-4824605") == AdapterNoMatch("all_not_found")


def test_a_not_found_plus_an_operational_failure_is_an_error_never_none():
    client = client_4824605_not_found_everywhere()
    client.replace(url_for("javdb", "4824605"), FakeRequestError("timeout"))
    outcome = lookup(runtime_for(client, **REQUEST_ERRORS), "FC2-4824605")
    assert outcome == AdapterFailure("timeout", "FC2 lookup failed: fc2db_net=not_found; javdb=timeout; av123=not_found")


def test_every_source_failing_reports_the_highest_priority_reason():
    client = client_4825061()
    client.replace(url_for("fc2db_net", "4825061"), FakeRequestError("timeout"))
    client.replace(url_for("javdb", "4825061"), FakeRequestError("network"))
    client.replace(url_for("av123", "4825061"), FakeRequestError("network"))
    outcome = lookup(runtime_for(client, **REQUEST_ERRORS))
    assert outcome == AdapterFailure("timeout", "FC2 lookup failed: fc2db_net=timeout; javdb=connection_error; av123=connection_error")


def test_non_fc2_inputs_return_no_match_without_any_request():
    client = client_4825061()
    runtime = runtime_for(client)
    for number, content_type in (("ABC-123", "fc2"), ("FC2-PPV-4825061", "censored"), ("", None), ("FC2-123456789", None)):
        assert isinstance(lookup(runtime, number, content_type), AdapterNoMatch)
    assert client.calls == []


def test_foreign_number_is_an_unexpected_failure_without_any_request():
    client = client_4825061()
    outcome = lookup(runtime_for(client), 12345)  # type: ignore[arg-type]
    assert outcome == AdapterFailure("unexpected", "invalid search query")
    assert client.calls == []


def test_an_engine_exception_becomes_a_bounded_unexpected_failure_naming_only_the_type():
    runtime = runtime_for(client_4825061())

    class Boom:
        async def aggregate(self, number):
            raise RuntimeError("SECRET https://example.invalid/x")

    runtime._engine = Boom()
    outcome = lookup(runtime)
    assert outcome == AdapterFailure("unexpected", "internal adapter error: RuntimeError")


@pytest.mark.parametrize("fatal", [KeyboardInterrupt, SystemExit])
def test_fatal_exceptions_from_the_engine_are_not_converted(fatal):
    runtime = runtime_for(client_4825061())

    class Fatal:
        async def aggregate(self, number):
            raise fatal()

    runtime._engine = Fatal()
    with pytest.raises(fatal):
        lookup(runtime)
