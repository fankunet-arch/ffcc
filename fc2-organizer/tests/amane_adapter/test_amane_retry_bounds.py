"""P5-C1 §15（E9 纯逻辑部分）：三层请求计数口径 L1 / L2 / L3 与所有权。

* L1 = Core ``adapter.fetch`` / 桥 ``get`` 调用数 = S（Core ``A = 1``；熔断打开的来源 = 0）；
* L2 = 宿主 ``WebClient`` host attempts ≤ S × H；
* L3 = 含被跟随重定向的 network hops ≤ S × H × 21（真实 curl_cffi 的 21 跳由 H-09 见证；这里做算术核对）。

宿主语义用 ``HostModelWebClient`` 建模（不睡眠、不联网）；真实 v0.15.0 ``WebClient`` 由 H-09 见证。
"""

from __future__ import annotations

import asyncio
import itertools

import pytest

from _amane_scenarios import url_for
from fc2_amane_adapter._outcome import AdapterFailure, AdapterFound, AdapterNoMatch
from fc2_amane_adapter._runtime import AdapterRuntime
from fc2_amane_adapter._settings import parse_settings
from fc2_metadata_core.aggregation import DEFAULT_SOURCE_ORDER, RetryPolicy
from fc2_metadata_core.sources.adapters import build_default_registry
from support.amane_host_fakes import (
    FakeCurlError,
    FakeHostBridge,
    FakeRequestError,
    FakeResponse,
    HostModelWebClient,
)

N = "FC2-4825061"
ALL = ("fc2db_net", "javdb", "av123")
HOST_ERRORS = {"bridge_type": FakeHostBridge}
REDIRECT_HOPS_PER_ATTEMPT = 21  # R + 1，R = 20（宿主 max_redirects；W-08 实测）


def _runtime(client, sources: int = 3, deadline: float = 20.0) -> AdapterRuntime:
    entries = [{"id": source_id} for source_id in ALL[:sources]]
    return AdapterRuntime(parse_settings({"sources": entries, "source_deadline_seconds": deadline}), client, **HOST_ERRORS)


def _constant(item):
    return lambda url: itertools.repeat(item)


def _lookup(runtime: AdapterRuntime, number: str = N):
    return asyncio.run(runtime.lookup(number, "fc2"))


def test_registry_size_and_frozen_core_attempts_define_s_and_a():
    assert len(build_default_registry().source_ids()) == 3 == len(DEFAULT_SOURCE_ORDER)
    runtime = _runtime(HostModelWebClient(_constant(FakeCurlError())))
    assert runtime._config.retry_policy == RetryPolicy.no_retry()
    assert runtime._config.retry_policy.max_attempts == 1
    assert all(source.retry_policy.max_attempts == 1 for source in runtime._config.sources)


def test_three_layer_arithmetic_for_the_documented_configurations():
    def bounds(s, h):
        return s, s * h, s * h * REDIRECT_HOPS_PER_ATTEMPT

    assert bounds(3, 3) == (3, 9, 189)
    assert bounds(3, 10) == (3, 30, 630)
    assert bounds(1, 1) == (1, 1, 21)


@pytest.mark.parametrize("status", [200, 403, 404, 429, 500, 503, 599])
@pytest.mark.parametrize("h", [1, 3, 10])
@pytest.mark.parametrize("s", [1, 2, 3])
def test_status_paths_cost_exactly_one_host_attempt_per_source(status, h, s):
    """含 429 / 503 / 5xx：``ok_statuses`` 使状态码路径恒为 1 个 host attempt（M-01）；A = 1 使桥只被调用 S 次（M-02）。"""
    client = HostModelWebClient(_constant(FakeResponse.html("<html></html>", status=status)), max_retries=h)
    _lookup(_runtime(client, s))
    assert client.requests == s  # L1
    assert client.host_attempts == s  # L2：状态码路径与 H 无关
    assert all(count == 1 for count in client.attempts_by_url.values())
    assert all(call[2]["ok_statuses"] == frozenset(range(300, 600)) for call in client.calls)


@pytest.mark.parametrize("item", [FakeCurlError(), TimeoutError()], ids=["curl_error", "timeout"])
@pytest.mark.parametrize("h", [1, 3, 10])
@pytest.mark.parametrize("s", [1, 2, 3])
def test_transport_failures_are_bounded_by_h_per_source_and_s_times_h_overall(item, h, s):
    client = HostModelWebClient(_constant(item), max_retries=h)
    outcome = _lookup(_runtime(client, s))
    assert isinstance(outcome, AdapterFailure)
    assert client.requests == s  # L1 = S：Core 不再重复宿主重试
    assert client.host_attempts == s * h  # L2 达到上界 S × H
    assert all(count == h for count in client.attempts_by_url.values())
    assert client.host_attempts * REDIRECT_HOPS_PER_ATTEMPT <= s * h * 21  # L3 算术上界


def test_mixed_path_curl_error_then_503_is_still_within_h():
    def outcomes(url):
        return iter([FakeCurlError(), FakeResponse.html("", status=503, url=url)])

    client = HostModelWebClient(outcomes, max_retries=3)
    _lookup(_runtime(client))
    assert client.requests == 3 and all(count == 2 for count in client.attempts_by_url.values())
    assert client.host_attempts <= 3 * 3


def test_default_and_maximum_host_bounds_hold_with_transport_failures():
    for h, ceiling in ((3, 9), (10, 30)):
        client = HostModelWebClient(_constant(FakeCurlError()), max_retries=h)
        _lookup(_runtime(client))
        assert client.host_attempts == ceiling  # = S × H，S = 3


def test_host_defect_zero_retries_sends_nothing_and_fails_closed():
    client = HostModelWebClient(_constant(FakeResponse.html("x")), max_retries=0)
    outcome = _lookup(_runtime(client))
    assert client.host_attempts == 0 and client.requests == 3
    assert outcome == AdapterFailure("network", "FC2 lookup failed: fc2db_net=connection_error; javdb=connection_error; av123=connection_error")


def test_disabled_sources_reduce_s():
    client = HostModelWebClient(_constant(FakeCurlError()), max_retries=3)
    runtime = AdapterRuntime(
        parse_settings({"sources": [{"id": "fc2db_net", "enabled": False}, {"id": "javdb"}, {"id": "av123", "enabled": False}]}),
        client,
        **HOST_ERRORS,
    )
    _lookup(runtime)
    assert client.requests == 1 and client.host_attempts == 3 and set(client.attempts_by_url) == {url_for("javdb", "4825061")}


def test_breaker_open_sources_send_zero_requests():
    client = HostModelWebClient(_constant(FakeCurlError()), max_retries=3)
    runtime = _runtime(client)
    for _ in range(3):  # 默认熔断：连续 3 次最终失败
        _lookup(runtime)
    assert client.requests == 9 and client.host_attempts == 27
    outcome = _lookup(runtime)
    assert client.requests == 9 and client.host_attempts == 27  # 熔断打开：0 次
    assert outcome == AdapterFailure("network", "FC2 lookup failed: fc2db_net=circuit_open; javdb=circuit_open; av123=circuit_open")


def test_breaker_state_is_per_source_and_does_not_leak_to_healthy_sources():
    def outcomes(url):
        item = FakeCurlError() if "javdb" in url else FakeResponse.html("", status=404, url=url)
        return itertools.repeat(item)

    client = HostModelWebClient(outcomes, max_retries=3)
    runtime = _runtime(client)
    for _ in range(4):
        _lookup(runtime)
    javdb_url = url_for("javdb", "4825061")
    assert client.attempts_by_url[javdb_url] == 9  # 前 3 次 × H=3，第 4 次为 0
    assert client.attempts_by_url[url_for("av123", "4825061")] == 4


def test_non_fc2_and_foreign_queries_send_no_request_at_all():
    client = HostModelWebClient(_constant(FakeCurlError()), max_retries=10)
    runtime = _runtime(client)
    for number, content_type in (("ABC-123", "fc2"), (N, "censored"), (7, None)):
        outcome = asyncio.run(runtime.lookup(number, content_type))
        assert isinstance(outcome, (AdapterNoMatch, AdapterFailure))
    assert client.requests == 0 and client.host_attempts == 0


def test_a_successful_lookup_costs_s_requests_and_s_host_attempts():
    client = HostModelWebClient(_constant(FakeResponse.html("", status=404)), max_retries=10)
    outcome = _lookup(_runtime(client))
    assert isinstance(outcome, AdapterNoMatch) or isinstance(outcome, AdapterFound)
    assert client.requests == 3 and client.host_attempts == 3
