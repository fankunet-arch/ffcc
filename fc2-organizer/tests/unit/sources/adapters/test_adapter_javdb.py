"""javdb.com adapter (public search listing only): parser + ``fetch`` contract."""

from __future__ import annotations

import asyncio

import pytest

from fc2_metadata_core.errors import InvalidCanonicalNumberInputError
from fc2_metadata_core.http.client import HttpConnectionError, HttpTimeoutError
from fc2_metadata_core.models.source_result import SourceStatus
from fc2_metadata_core.sources.adapters.javdb import JavdbAdapter, parse_javdb_search_page

from support.fake_http_client import FakeHttpClient, make_response
from support.source_fixtures import load_fixture

SID = "javdb"
BASE = "https://javdb.com"


def run(coro):
    return asyncio.run(coro)


def _fetch(number, response=None, *, error=None):
    adapter = JavdbAdapter()
    client = FakeHttpClient()
    url = adapter._lookup_url(number)
    if error is not None:
        client.add_error(url, error)
    else:
        client.add_response(url, response if response is not None else make_response(url=url))
    return run(adapter.fetch(number, client)), client, url


def test_lookup_url_is_search_and_base_url_overridable():
    assert JavdbAdapter()._lookup_url("FC2-4825061") == "https://javdb.com/search?q=FC2-PPV-4825061"
    assert JavdbAdapter(base_url="https://mirror.invalid/")._lookup_url("FC2-4825061") == (
        "https://mirror.invalid/search?q=FC2-PPV-4825061"
    )


def test_parse_exact_hit_real_page():
    md, err = parse_javdb_search_page(load_fixture("javdb/search_hit_4979299.html"), "FC2-4979299", BASE, SID)
    assert err is None and md is not None
    assert md.number == "FC2-4979299"
    assert md.title == "夢は小学校の先生。天使のような笑顔と色白美巨乳♡ほのぼの系美女のおじさま２人への体当たり性指導映像。"
    assert md.release == "2026-09-19"
    assert md.thumb_urls == ("https://c0.jdbstatic.com/covers/qn/QNkPbM.jpg",)
    assert md.source_urls == ("https://javdb.com/v/QNkPbM",)
    assert md.external_ids == {"javdb": "QNkPbM"}
    assert md.meets_minimum_success()
    # detail pages need a login, so nothing detail-only may be claimed
    assert md.actors == () and md.tags == () and md.runtime is None


def test_fuzzy_search_picks_only_the_exact_number():
    # The real 4825061 search also listed the unrelated FC2-1825061 as a fuzzy hit.
    html = load_fixture("javdb/search_hit_4825061.html")
    exact, _ = parse_javdb_search_page(html, "FC2-4825061", BASE, SID)
    fuzzy, _ = parse_javdb_search_page(html, "FC2-1825061", BASE, SID)
    assert exact.title.startswith("【顔出し】ハーフ美人妻")
    assert fuzzy.number == "FC2-1825061" and fuzzy.title.startswith("【無】【顔出し】撮影経験無し")
    assert exact.external_ids != fuzzy.external_ids


def test_only_fuzzy_hits_is_not_found_never_a_near_match():
    md, err = parse_javdb_search_page(
        load_fixture("javdb/search_no_exact_4824605.html"), "FC2-4824605", BASE, SID
    )
    assert md is None and err[0] is SourceStatus.NOT_FOUND


def test_empty_result_page_is_not_found():
    md, err = parse_javdb_search_page(
        load_fixture("javdb/search_empty_99999999.html"), "FC2-9999999", BASE, SID
    )
    assert md is None and err[0] is SourceStatus.NOT_FOUND


def test_unrecognized_200_page_is_invalid_response_not_not_found():
    md, err = parse_javdb_search_page("<html><title>Something else</title></html>", "FC2-4825061", BASE, SID)
    assert md is None and err[0] is SourceStatus.INVALID_RESPONSE


def test_fetch_success_single_request():
    number = "FC2-4979299"
    url = JavdbAdapter()._lookup_url(number)
    result, client, _ = _fetch(number, make_response(url=url, text=load_fixture("javdb/search_hit_4979299.html")))
    assert result.status is SourceStatus.SUCCESS and result.metadata.number == number
    assert client.requested_urls == [url]


def test_fetch_no_exact_hit_is_not_found():
    number = "FC2-4824605"
    url = JavdbAdapter()._lookup_url(number)
    result, _, _ = _fetch(number, make_response(url=url, text=load_fixture("javdb/search_no_exact_4824605.html")))
    assert result.status is SourceStatus.NOT_FOUND and result.metadata is None


def test_redirect_to_login_is_blocked():
    result, _, _ = _fetch(
        "FC2-4825061", make_response(status_code=200, url="https://javdb.com/login", text="<html>login</html>")
    )
    assert result.status is SourceStatus.BLOCKED and result.metadata is None


@pytest.mark.parametrize(
    "kwargs, expected",
    [
        ({"status_code": 403}, SourceStatus.BLOCKED),
        ({"status_code": 200, "text": load_fixture("common/cloudflare_challenge.html")}, SourceStatus.BLOCKED),
        ({"status_code": 429}, SourceStatus.RATE_LIMITED),
        ({"status_code": 503}, SourceStatus.INVALID_RESPONSE),
    ],
)
def test_failure_statuses(kwargs, expected):
    result, _, _ = _fetch("FC2-4825061", make_response(**kwargs))
    assert result.status is expected and result.metadata is None


@pytest.mark.parametrize("exc", [HttpTimeoutError("t"), HttpConnectionError("c")])
def test_transport_errors(exc):
    result, _, _ = _fetch("FC2-4825061", error=exc)
    assert result.status is SourceStatus.NETWORK_ERROR


def test_exact_hit_with_blank_title_is_parse_error():
    page = (
        '<div class="movie-list"><div class="item"><a href="/v/AAA" class="box" title="">'
        '<div class="video-title"><strong>FC2-4825061</strong>  </div></a></div></div>'
    )
    result, _, _ = _fetch("FC2-4825061", make_response(text=page))
    assert result.status is SourceStatus.PARSE_ERROR


def test_non_canonical_number_rejected_before_request():
    client = FakeHttpClient()
    with pytest.raises(InvalidCanonicalNumberInputError):
        run(JavdbAdapter().fetch("FC2-PPV-4825061", client))
    assert client.requested_urls == []
