"""Phase 3 C2, PRODUCTION path: real adapters + real ``HttpxTransport`` over ``httpx.MockTransport``.

Closes P2-R-12 end to end: every failure below is produced by an actual httpx-level event
(HTTP status, timeout, connect error, undecodable body, redirect loop, oversized body) and travels
httpx -> transport exception -> adapter ``SourceResult`` (fine ``error_kind``) -> ``RetryPolicy``.
Nothing is decided from ``error_detail`` text, and no real website is contacted.
"""

from __future__ import annotations

import asyncio

import httpx
import pytest

from fc2_metadata_core.aggregation import (
    AggregateStatus,
    AggregationConfig,
    MultiSourceEngine,
    RetryPolicy,
    SourceConfig,
    default_aggregation_config,
)
from fc2_metadata_core.http.client import HttpConnectionError
from fc2_metadata_core.http.httpx_client import HttpxTransport
from fc2_metadata_core.models.source_result import SourceErrorKind, SourceStatus
from fc2_metadata_core.sources import SourceRegistry
from fc2_metadata_core.sources.adapters import build_default_registry
from fc2_metadata_core.sources.adapters.av123 import Av123Adapter
from fc2_metadata_core.sources.adapters.fc2db_net import Fc2dbNetAdapter
from fc2_metadata_core.sources.adapters.javdb import JavdbAdapter

from support.fake_http_client import FakeHttpClient, make_response
from support.fake_source_adapter import FakeSourceAdapter
from support.source_fixtures import load_fixture

N = "FC2-4979299"
K = SourceErrorKind
S = SourceStatus
FAST = RetryPolicy(max_attempts=2, initial_backoff_seconds=0.01)
BASE = "https://mock.invalid"

# source id -> (adapter class, valid 200 fixture for N)
SOURCES = {
    "fc2db_net": (Fc2dbNetAdapter, "fc2db_net/work_4979299.html"),
    "javdb": (JavdbAdapter, "javdb/search_hit_4979299.html"),
    "av123": (Av123Adapter, "av123/detail_4979299.html"),
}
SOURCE_IDS = list(SOURCES)


class Recorder:
    """A MockTransport handler that records every request and replays scripted outcomes."""

    def __init__(self, *outcomes):
        assert outcomes
        self.outcomes = list(outcomes)
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        outcome = self.outcomes.pop(0) if len(self.outcomes) > 1 else self.outcomes[0]
        if isinstance(outcome, BaseException):
            if isinstance(outcome, (httpx.TransportError,)):
                outcome.request = request  # httpx wants the request attached
            raise outcome
        if callable(outcome):
            return outcome(request)
        return outcome

    @property
    def count(self) -> int:
        return len(self.requests)


def lookup(handler, source_id="fc2db_net", *, retry=FAST, deadline=5.0, number=N, **transport_kw):
    config = AggregationConfig.create(
        [SourceConfig(source_id, base_url=BASE, deadline_seconds=deadline)], retry_policy=retry
    )

    async def scenario():
        async with HttpxTransport(transport=httpx.MockTransport(handler), **transport_kw) as transport:
            return await MultiSourceEngine(config, build_default_registry(), transport).aggregate(number)

    return asyncio.run(scenario())


def final_of(result, source_id="fc2db_net"):
    return result.result_for(source_id)


def valid_page(source_id):
    return httpx.Response(200, text=load_fixture(SOURCES[source_id][1]))


# ---- HTTP 5xx: structured, retryable (P2-R-12) --------------------------------------------------------------------------------------


@pytest.mark.parametrize("source_id", SOURCE_IDS)
@pytest.mark.parametrize("status", [500, 502, 503, 504])
def test_5xx_is_invalid_response_http_server_error_and_is_retried_once(source_id, status):
    handler = Recorder(httpx.Response(status, text="upstream error"))
    result = lookup(handler, source_id)
    final = final_of(result, source_id)
    assert (final.status, final.error_kind) == (S.INVALID_RESPONSE, K.HTTP_SERVER_ERROR)
    assert handler.count == 2, "a 5xx is transient: exactly one retry, never a third request"
    trace = result.trace_for(source_id)
    assert [(a.status, a.error_kind) for a in trace.attempts] == [(S.INVALID_RESPONSE, K.HTTP_SERVER_ERROR)] * 2
    assert result.status is AggregateStatus.FAILED  # a single source that stayed down


@pytest.mark.parametrize("source_id", SOURCE_IDS)
@pytest.mark.parametrize("status", [500, 502, 503, 504])
def test_a_transient_5xx_followed_by_a_valid_page_is_a_success_after_two_attempts(source_id, status):
    handler = Recorder(httpx.Response(status), valid_page(source_id))
    result = lookup(handler, source_id)
    assert result.status is AggregateStatus.SUCCESS
    assert final_of(result, source_id).status is S.SUCCESS and handler.count == 2
    trace = result.trace_for(source_id)
    assert trace.attempt_count == 2 and trace.attempts[0].error_kind is K.HTTP_SERVER_ERROR
    assert trace.attempts[0].status is S.INVALID_RESPONSE and trace.attempts[1].status is S.SUCCESS


# ---- never retried ------------------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("source_id", SOURCE_IDS)
@pytest.mark.parametrize(
    "response, status, kind",
    [
        (httpx.Response(403, text="forbidden"), S.BLOCKED, K.BLOCKED),
        (httpx.Response(404, text="nope"), S.NOT_FOUND, K.NOT_FOUND),
        (httpx.Response(429, text="slow down", headers={"Retry-After": "30"}), S.RATE_LIMITED, K.RATE_LIMITED),
        (httpx.Response(418, text="teapot"), S.INVALID_RESPONSE, K.INVALID_RESPONSE),
        (httpx.Response(403, headers={"cf-mitigated": "challenge"}, text="challenge"), S.BLOCKED, K.BLOCKED),
    ],
    ids=["403", "404", "429(+Retry-After ignored)", "418(other 4xx)", "403+cf-mitigated"],
)
def test_blocked_not_found_rate_limited_and_other_client_errors_get_exactly_one_request(source_id, response, status, kind):
    handler = Recorder(response)
    result = lookup(handler, source_id)
    final = final_of(result, source_id)
    assert (final.status, final.error_kind) == (status, kind)
    assert handler.count == 1, "this outcome must never be retried"
    assert result.trace_for(source_id).attempt_count == 1


@pytest.mark.parametrize("source_id", SOURCE_IDS)
def test_a_cloudflare_challenge_page_served_with_200_is_blocked_and_not_retried(source_id):
    handler = Recorder(httpx.Response(200, text=load_fixture("common/cloudflare_challenge.html")))
    result = lookup(handler, source_id)
    assert (final_of(result, source_id).status, final_of(result, source_id).error_kind) == (S.BLOCKED, K.BLOCKED)
    assert handler.count == 1


@pytest.mark.parametrize(
    "source_id, expected_status",
    [("fc2db_net", S.PARSE_ERROR), ("av123", S.PARSE_ERROR), ("javdb", S.INVALID_RESPONSE)],
)
def test_a_200_page_that_does_not_parse_is_a_semantic_failure_and_is_not_retried(source_id, expected_status):
    handler = Recorder(httpx.Response(200, text="<html><body><p>a completely different page</p></body></html>"))
    result = lookup(handler, source_id)
    final = final_of(result, source_id)
    assert final.status is expected_status
    assert final.error_kind is (K.PARSE_ERROR if expected_status is S.PARSE_ERROR else K.INVALID_RESPONSE)
    assert final.error_kind is not K.HTTP_SERVER_ERROR
    assert handler.count == 1


def test_javdb_login_redirect_is_blocked_after_a_single_attempt():
    handler = Recorder(
        lambda request: httpx.Response(302, headers={"Location": BASE + "/login"})
        if request.url.path != "/login"
        else httpx.Response(200, text="<html>login</html>")
    )
    result = lookup(handler, "javdb")
    assert final_of(result, "javdb").status is S.BLOCKED
    assert result.trace_for("javdb").attempt_count == 1


def test_javdb_fuzzy_miss_for_fc2_4824605_is_not_found_with_exactly_one_request():
    number = "FC2-4824605"
    handler = Recorder(httpx.Response(200, text=load_fixture("javdb/search_no_exact_4824605.html")))
    result = lookup(handler, "javdb", number=number)
    final = final_of(result, "javdb")
    assert (final.status, final.error_kind) == (S.NOT_FOUND, K.NOT_FOUND)
    assert handler.count == 1 and result.trace_for("javdb").attempt_count == 1


# ---- transport-level failures ---------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("source_id", SOURCE_IDS)
@pytest.mark.parametrize(
    "exc_factory, kind",
    [
        (lambda: httpx.ReadTimeout("slow"), K.TIMEOUT),
        (lambda: httpx.ConnectTimeout("slow"), K.TIMEOUT),
        (lambda: httpx.PoolTimeout("slow"), K.TIMEOUT),
        (lambda: httpx.ConnectError("dns failure"), K.CONNECTION_ERROR),
        (lambda: httpx.RemoteProtocolError("bad framing"), K.CONNECTION_ERROR),
        (lambda: httpx.ReadError("connection reset"), K.CONNECTION_ERROR),
    ],
    ids=["ReadTimeout", "ConnectTimeout", "PoolTimeout", "ConnectError", "RemoteProtocolError", "ReadError"],
)
def test_timeouts_and_connection_failures_are_network_errors_with_a_structured_kind_and_are_retried(source_id, exc_factory, kind):
    handler = Recorder(exc_factory())
    result = lookup(handler, source_id)
    final = final_of(result, source_id)
    assert (final.status, final.error_kind) == (S.NETWORK_ERROR, kind)
    assert handler.count == 2
    assert [a.error_kind for a in result.trace_for(source_id).attempts] == [kind, kind]


def test_a_transient_timeout_then_a_valid_page_recovers():
    handler = Recorder(httpx.ReadTimeout("slow"), valid_page("fc2db_net"))
    result = lookup(handler, "fc2db_net")
    assert result.status is AggregateStatus.SUCCESS and handler.count == 2
    assert result.trace_for("fc2db_net").attempts[0].error_kind is K.TIMEOUT


def test_a_transient_connection_error_then_a_valid_page_recovers():
    handler = Recorder(httpx.ConnectError("dns"), valid_page("av123"))
    result = lookup(handler, "av123")
    assert result.status is AggregateStatus.SUCCESS and result.trace_for("av123").attempts[0].error_kind is K.CONNECTION_ERROR


# ---- decode / decompression: the production path is REAL (httpx -> HttpDecodingError -> DECODE_ERROR) ------------------------------------------


@pytest.mark.parametrize("encoding, body", [("gzip", b"this is definitely not gzip data"), ("deflate", b"garbage garbage garbage")])
@pytest.mark.parametrize("source_id", SOURCE_IDS)
def test_an_undecodable_body_is_network_error_decode_error_and_is_retried(source_id, encoding, body):
    # built inside the handler: httpx decodes eagerly in Response(...), which must happen on the transport path
    handler = Recorder(lambda request: httpx.Response(200, headers={"content-encoding": encoding}, content=body))
    result = lookup(handler, source_id)
    final = final_of(result, source_id)
    assert (final.status, final.error_kind) == (S.NETWORK_ERROR, K.DECODE_ERROR)
    assert handler.count == 2, "DECODE_ERROR is retryable"
    assert [a.error_kind for a in result.trace_for(source_id).attempts] == [K.DECODE_ERROR, K.DECODE_ERROR]


def test_a_decode_failure_followed_by_a_clean_response_recovers():
    handler = Recorder(lambda request: httpx.Response(200, headers={"content-encoding": "gzip"}, content=b"not gzip"), valid_page("fc2db_net"))
    result = lookup(handler, "fc2db_net")
    assert result.status is AggregateStatus.SUCCESS
    assert result.trace_for("fc2db_net").attempts[0].error_kind is K.DECODE_ERROR and handler.count == 2


# ---- redirect loop / oversized: default no retry ----------------------------------------------------------------------------------------------


@pytest.mark.parametrize("source_id", SOURCE_IDS)
def test_a_redirect_loop_is_network_error_redirect_error_and_is_not_retried(source_id):
    handler = Recorder(httpx.Response(302, headers={"Location": BASE + "/again"}))
    result = lookup(handler, source_id)
    final = final_of(result, source_id)
    assert (final.status, final.error_kind) == (S.NETWORK_ERROR, K.REDIRECT_ERROR)
    assert result.trace_for(source_id).attempt_count == 1
    assert handler.count == 6, "one lookup follows exactly max_redirects(5)+1 hops; a retry would double it"


@pytest.mark.parametrize("source_id", SOURCE_IDS)
def test_an_oversized_response_is_invalid_response_response_too_large_and_is_not_retried(source_id):
    handler = Recorder(httpx.Response(200, content=b"x" * 500))
    result = lookup(handler, source_id, max_response_bytes=100)
    final = final_of(result, source_id)
    assert (final.status, final.error_kind) == (S.INVALID_RESPONSE, K.RESPONSE_TOO_LARGE)
    assert handler.count == 1 and result.trace_for(source_id).attempt_count == 1


# ---- the real-world case that motivated C2: a transient av123 HTTP 500 ---------------------------------------------------------------------------------------


def test_transient_av123_500_then_200_is_success_not_partial_in_the_default_three_source_config():
    client = FakeHttpClient()
    number = N
    client.add_response(Fc2dbNetAdapter()._lookup_url(number), make_response(url="u", text=load_fixture("fc2db_net/work_4979299.html")))
    client.add_response(JavdbAdapter()._lookup_url(number), make_response(url="u", text=load_fixture("javdb/search_hit_4979299.html")))
    av_url = Av123Adapter()._lookup_url(number)
    client.add_sequence(
        av_url,
        [make_response(status_code=500, url=av_url, text="Internal Server Error"), make_response(url=av_url, text=load_fixture("av123/detail_4979299.html"))],
    )
    base = default_aggregation_config()
    config = AggregationConfig.create(list(base.sources), retry_policy=FAST)
    result = asyncio.run(MultiSourceEngine(config, build_default_registry(), client).aggregate(number))

    assert result.status is AggregateStatus.SUCCESS, "with retry the transient 500 no longer makes the aggregate PARTIAL"
    av = result.result_for("av123")
    assert av.status is S.SUCCESS
    trace = result.trace_for("av123")
    assert trace.attempt_count == 2 and (trace.attempts[0].status, trace.attempts[0].error_kind) == (S.INVALID_RESPONSE, K.HTTP_SERVER_ERROR)
    assert client.request_count(av_url) == 2
    assert result.contributing_source_ids == ("fc2db_net", "javdb", "av123")
    assert [result.trace_for(s).attempt_count for s in ("fc2db_net", "javdb")] == [1, 1]


def test_the_same_transient_500_without_retry_is_the_c1_partial_outcome():
    client = FakeHttpClient()
    client.add_response(Fc2dbNetAdapter()._lookup_url(N), make_response(url="u", text=load_fixture("fc2db_net/work_4979299.html")))
    client.add_response(JavdbAdapter()._lookup_url(N), make_response(url="u", text=load_fixture("javdb/search_hit_4979299.html")))
    av_url = Av123Adapter()._lookup_url(N)
    client.add_sequence(av_url, [make_response(status_code=500, url=av_url), make_response(url=av_url, text=load_fixture("av123/detail_4979299.html"))])
    config = AggregationConfig.create(list(default_aggregation_config().sources), retry_policy=RetryPolicy.no_retry())
    result = asyncio.run(MultiSourceEngine(config, build_default_registry(), client).aggregate(N))
    assert result.status is AggregateStatus.PARTIAL and client.request_count(av_url) == 1
    assert result.result_for("av123").error_kind is K.HTTP_SERVER_ERROR


def test_default_config_javdb_fuzzy_miss_is_asked_once_while_fc2db_answers():
    number = "FC2-4824605"
    client = FakeHttpClient()
    fc2db_url, javdb_url, av_url = (c()._lookup_url(number) for c in (Fc2dbNetAdapter, JavdbAdapter, Av123Adapter))
    client.add_response(fc2db_url, make_response(url="u", text=load_fixture("fc2db_net/work_4824605.html")))
    client.add_response(javdb_url, make_response(url="u", text=load_fixture("javdb/search_no_exact_4824605.html")))
    client.add_response(av_url, make_response(status_code=404, url=av_url, text=load_fixture("av123/detail_404_4824605.html")))
    config = AggregationConfig.create(list(default_aggregation_config().sources), retry_policy=FAST)
    result = asyncio.run(MultiSourceEngine(config, build_default_registry(), client).aggregate(number))
    assert result.status is AggregateStatus.SUCCESS
    assert [client.request_count(u) for u in (fc2db_url, javdb_url, av_url)] == [1, 1, 1]
    assert [t.attempt_count for t in result.source_execution_traces] == [1, 1, 1]
    assert result.not_found_source_ids == ("javdb", "av123")


# ---- backward compatibility: an adapter using the LEGACY (coarse) transport helper -----------------------------------------------------------------


def test_an_unrefined_adapter_reporting_a_generic_network_error_is_still_retried():
    """FakeSourceAdapter uses the pre-C2 ``transport_error_result`` (generic NETWORK_ERROR kind)."""
    adapter_url = FakeSourceAdapter()._lookup_url(N)
    client = FakeHttpClient()
    client.add_sequence(adapter_url, [HttpConnectionError("legacy"), make_response(url=adapter_url, text="TITLE: Legacy Title\n")])
    registry = SourceRegistry()
    registry.register("fake_source", FakeSourceAdapter)
    config = AggregationConfig.create([SourceConfig("fake_source")], retry_policy=FAST)
    result = asyncio.run(MultiSourceEngine(config, registry, client).aggregate(N))
    trace = result.trace_for("fake_source")
    assert trace.attempt_count == 2 and result.status is AggregateStatus.SUCCESS
    assert (trace.attempts[0].status, trace.attempts[0].error_kind) == (S.NETWORK_ERROR, K.NETWORK_ERROR)  # generic kind
