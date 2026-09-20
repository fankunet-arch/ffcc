"""Phase 3 C3-E01 (closes C2 review M1): an anti-bot challenge is BLOCKED and never retried, under ANY HTTP status.

Before C3 the "Just a moment..." body check ran only for HTTP 200. A ``503`` + challenge body *without* a
``cf-mitigated`` header was therefore classified ``INVALID_RESPONSE / HTTP_SERVER_ERROR`` and the C2 retry
policy hit the site a second time -- violating the frozen "challenge -> BLOCKED -> never retry" rule.

Everything below runs the PRODUCTION path: the real adopted adapter -> the real ``HttpxTransport`` over
``httpx.MockTransport``. No real website is contacted, nothing is bypassed.
"""

from __future__ import annotations

import asyncio

import httpx
import pytest

from fc2_metadata_core.aggregation import AggregateStatus, AggregationConfig, MultiSourceEngine, RetryPolicy, SourceConfig
from fc2_metadata_core.http.client import HttpResponse
from fc2_metadata_core.http.httpx_client import HttpxTransport
from fc2_metadata_core.models.source_result import SourceErrorKind, SourceStatus
from fc2_metadata_core.sources.adapters import build_default_registry
from fc2_metadata_core.sources.adapters._common import classify_page_response
from fc2_metadata_core.sources.adapters.av123 import Av123Adapter
from fc2_metadata_core.sources.adapters.fc2db_net import Fc2dbNetAdapter
from fc2_metadata_core.sources.adapters.javdb import JavdbAdapter

from support.source_fixtures import load_fixture

N = "FC2-4979299"
K = SourceErrorKind
S = SourceStatus
FAST = RetryPolicy(max_attempts=2, initial_backoff_seconds=0.01)
BASE = "https://mock.invalid"
SOURCES = {
    "fc2db_net": (Fc2dbNetAdapter, "fc2db_net/work_4979299.html"),
    "javdb": (JavdbAdapter, "javdb/search_hit_4979299.html"),
    "av123": (Av123Adapter, "av123/detail_4979299.html"),
}
SOURCE_IDS = list(SOURCES)

CHALLENGE = load_fixture("common/cloudflare_challenge.html")  # verbatim real interstitial; title "Just a moment..."
ATTENTION = '<!DOCTYPE html><html><head><title>Attention Required! | Cloudflare</title></head><body>Sorry, you have been blocked</body></html>'
ORDINARY_ERROR_PAGE = "<html><head><title>Service Temporarily Unavailable</title></head><body><h1>503</h1></body></html>"


class Recorder:
    def __init__(self, *outcomes):
        self.outcomes = list(outcomes)
        self.count = 0

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.count += 1
        return self.outcomes.pop(0) if len(self.outcomes) > 1 else self.outcomes[0]


def lookup(handler, source_id):
    config = AggregationConfig.create([SourceConfig(source_id, base_url=BASE, deadline_seconds=5.0)], retry_policy=FAST)

    async def scenario():
        async with HttpxTransport(transport=httpx.MockTransport(handler)) as transport:
            return await MultiSourceEngine(config, build_default_registry(), transport).aggregate(N)

    return asyncio.run(scenario())


def valid_page(source_id):
    return httpx.Response(200, text=load_fixture(SOURCES[source_id][1]))


# ---- the M1 regression, through the production path ---------------------------------------------------------------------------------------


@pytest.mark.parametrize("source_id", SOURCE_IDS)
@pytest.mark.parametrize("status", [200, 403, 429, 500, 502, 503, 504, 404, 418])
@pytest.mark.parametrize("body", [CHALLENGE, ATTENTION], ids=["just-a-moment", "attention-required"])
def test_challenge_body_under_any_status_without_cf_mitigated_is_blocked_with_one_attempt(source_id, status, body):
    handler = Recorder(httpx.Response(status, text=body))  # note: NO cf-mitigated header
    result = lookup(handler, source_id)
    final = result.result_for(source_id)
    assert (final.status, final.error_kind) == (S.BLOCKED, K.BLOCKED)
    assert handler.count == 1, "a challenge must never be re-requested"
    trace = result.trace_for(source_id)
    assert trace.attempt_count == 1 and [(a.status, a.error_kind) for a in trace.attempts] == [(S.BLOCKED, K.BLOCKED)]
    assert result.status is AggregateStatus.FAILED and result.metadata is None


@pytest.mark.parametrize("source_id", SOURCE_IDS)
def test_a_503_challenge_followed_by_a_valid_page_is_never_given_the_chance_to_recover(source_id):
    handler = Recorder(httpx.Response(503, text=CHALLENGE), valid_page(source_id))
    result = lookup(handler, source_id)
    assert handler.count == 1, "the second (valid) response is never requested: BLOCKED is final"
    assert result.result_for(source_id).status is S.BLOCKED and result.status is AggregateStatus.FAILED


@pytest.mark.parametrize("source_id", SOURCE_IDS)
def test_503_with_the_cf_mitigated_header_is_still_blocked_with_one_attempt(source_id):
    handler = Recorder(httpx.Response(503, headers={"cf-mitigated": "challenge"}, text="x"))
    result = lookup(handler, source_id)
    assert result.result_for(source_id).error_kind is K.BLOCKED and handler.count == 1


# ---- the fix must not turn every 5xx into BLOCKED -----------------------------------------------------------------------------------------


@pytest.mark.parametrize("source_id", SOURCE_IDS)
@pytest.mark.parametrize("status", [500, 502, 503, 504])
@pytest.mark.parametrize(
    "body",
    [
        ORDINARY_ERROR_PAGE,
        "upstream error",
        "",
        # the phrase appears, but not as the page <title> near the top: an ordinary error page that merely mentions it
        "<html><head><title>Bad gateway</title></head><body><p>Just a moment, we are restarting.</p></body></html>",
        # a title of the phrase, but buried far below the scanned prefix
        "<html><head><title>Oops</title></head><body>" + "x" * 5000 + "<title>Just a moment</title></body></html>",
    ],
    ids=["html-error-page", "plain-text", "empty", "phrase-in-body-not-title", "title-beyond-scan-window"],
)
def test_an_ordinary_5xx_is_still_http_server_error_and_retried_once(source_id, status, body):
    handler = Recorder(httpx.Response(status, text=body))
    result = lookup(handler, source_id)
    final = result.result_for(source_id)
    assert (final.status, final.error_kind) == (S.INVALID_RESPONSE, K.HTTP_SERVER_ERROR)
    assert handler.count == 2
    assert [(a.status, a.error_kind) for a in result.trace_for(source_id).attempts] == [(S.INVALID_RESPONSE, K.HTTP_SERVER_ERROR)] * 2


@pytest.mark.parametrize("source_id", SOURCE_IDS)
def test_an_ordinary_503_followed_by_a_valid_page_still_recovers(source_id):
    handler = Recorder(httpx.Response(503, text=ORDINARY_ERROR_PAGE), valid_page(source_id))
    result = lookup(handler, source_id)
    assert result.status is AggregateStatus.SUCCESS and handler.count == 2


# ---- the shared classifier, directly ---------------------------------------------------------------------------------------------------------


def response(status, text, *, headers=None, url=BASE + "/x"):
    return HttpResponse(status_code=status, url=url, headers=headers or {}, text=text, elapsed_ms=1.0)


@pytest.mark.parametrize("status", [200, 202, 302, 400, 401, 403, 404, 410, 429, 451, 500, 503, 599])
def test_classify_page_response_challenge_is_blocked_under_every_status(status):
    result = classify_page_response("s", N, response(status, CHALLENGE))
    assert result is not None and (result.status, result.error_kind) == (S.BLOCKED, K.BLOCKED)
    assert str(status) in result.error_detail, "the diagnostic names the status the challenge arrived with"


@pytest.mark.parametrize(
    "status, expected",
    [(404, (S.NOT_FOUND, K.NOT_FOUND)), (429, (S.RATE_LIMITED, K.RATE_LIMITED)), (403, (S.BLOCKED, K.BLOCKED)),
     (503, (S.INVALID_RESPONSE, K.HTTP_SERVER_ERROR)), (418, (S.INVALID_RESPONSE, K.INVALID_RESPONSE))],
)
def test_classify_page_response_non_challenge_statuses_keep_their_existing_classification(status, expected):
    result = classify_page_response("s", N, response(status, "<html><title>Nothing special</title></html>"))
    assert (result.status, result.error_kind) == expected


def test_classify_page_response_a_clean_200_is_still_usable_and_never_a_success():
    assert classify_page_response("s", N, response(200, "<html><title>Some Work</title></html>")) is None


def test_a_challenge_is_recognised_case_insensitively_and_with_leading_whitespace():
    for title in ("just a moment...", "JUST A MOMENT", "\n  Just a moment"):
        result = classify_page_response("s", N, response(503, f"<html><head><title>{title}</title></head></html>"))
        assert result.status is S.BLOCKED, title
