"""fc2db.net adapter: parser against real captured markup + full ``fetch`` contract."""

from __future__ import annotations

import asyncio

import pytest

from fc2_metadata_core.errors import InvalidCanonicalNumberInputError
from fc2_metadata_core.http.client import HttpConnectionError, HttpTimeoutError
from fc2_metadata_core.models.source_result import SourceStatus
from fc2_metadata_core.sources.adapters.fc2db_net import Fc2dbNetAdapter, parse_fc2db_work_page

from support.fake_http_client import FakeHttpClient, make_response
from support.source_fixtures import load_fixture

SID = "fc2db_net"


def run(coro):
    return asyncio.run(coro)


def _fetch(number, response=None, *, error=None):
    adapter = Fc2dbNetAdapter()
    client = FakeHttpClient()
    url = adapter._lookup_url(number)
    if error is not None:
        client.add_error(url, error)
    else:
        client.add_response(url, response if response is not None else make_response(url=url))
    return run(adapter.fetch(number, client)), client, url


def test_lookup_url_is_work_page_and_base_url_is_overridable():
    assert Fc2dbNetAdapter()._lookup_url("FC2-4824605") == "https://fc2db.net/work/4824605/"
    assert Fc2dbNetAdapter(base_url="https://mirror.invalid/")._lookup_url("FC2-4824605") == (
        "https://mirror.invalid/work/4824605/"
    )


def test_parse_4824605_extracts_all_fields():
    md, err = parse_fc2db_work_page(
        load_fixture("fc2db_net/work_4824605.html"), "FC2-4824605", "https://fc2db.net/work/4824605/", SID
    )
    assert err is None and md is not None
    assert md.number == "FC2-4824605"
    assert md.title == "※1/11まで初回限定90％OFF※【ハメ撮り】スレンダー美人の人妻に種付け中出し調教"
    assert md.release == "2026-01-04"
    assert md.runtime == 55
    assert md.actors == ("花谷かれん",)
    assert md.publisher == "素人0930"
    assert md.tags[:3] == ("0930", "スレンダー", "パイパン")
    assert md.thumb_urls == ("https://img.fc2db.net/wp-content/uploads/2026/01/06134641/1767165768.52.webp",)
    assert md.source_urls == ("https://fc2db.net/work/4824605/",)
    assert md.meets_minimum_success()
    for name in ("number", "title", "release", "runtime", "actors", "publisher", "tags", "thumb_urls"):
        assert md.field_sources[name] == (SID,), name


def test_parse_second_real_page_4979299():
    md, err = parse_fc2db_work_page(
        load_fixture("fc2db_net/work_4979299.html"), "FC2-4979299", "https://fc2db.net/work/4979299/", SID
    )
    assert err is None and md is not None
    assert md.title.startswith("夢は小学校の先生。")
    assert md.number == "FC2-4979299"
    assert md.meets_minimum_success()


def test_fetch_success_end_to_end_with_single_request():
    number = "FC2-4824605"
    url = Fc2dbNetAdapter()._lookup_url(number)
    result, client, _ = _fetch(
        number, make_response(url=url, text=load_fixture("fc2db_net/work_4824605.html"), elapsed_ms=12.5)
    )
    assert result.status is SourceStatus.SUCCESS
    assert result.error_kind is None and result.error_detail is None
    assert result.elapsed_ms == 12.5
    assert result.metadata.number == number and result.metadata.title
    assert client.requested_urls == [url]


def test_real_404_page_is_not_found():
    number = "FC2-4825061"
    url = Fc2dbNetAdapter()._lookup_url(number)
    result, _, _ = _fetch(
        number,
        make_response(status_code=404, url=url, text=load_fixture("fc2db_net/work_404_4825061.html")),
    )
    assert result.status is SourceStatus.NOT_FOUND and result.metadata is None


@pytest.mark.parametrize(
    "kwargs, expected",
    [
        ({"status_code": 403}, SourceStatus.BLOCKED),
        ({"status_code": 200, "headers": {"cf-mitigated": "challenge"}}, SourceStatus.BLOCKED),
        ({"status_code": 429}, SourceStatus.RATE_LIMITED),
        ({"status_code": 502}, SourceStatus.INVALID_RESPONSE),
    ],
)
def test_failure_statuses(kwargs, expected):
    number = "FC2-4824605"
    result, _, _ = _fetch(number, make_response(url=Fc2dbNetAdapter()._lookup_url(number), **kwargs))
    assert result.status is expected and result.metadata is None


@pytest.mark.parametrize("exc", [HttpTimeoutError("t"), HttpConnectionError("c")])
def test_transport_errors_are_network_error(exc):
    result, _, _ = _fetch("FC2-4824605", error=exc)
    assert result.status is SourceStatus.NETWORK_ERROR


def test_200_without_work_heading_is_parse_error():
    result, _, _ = _fetch("FC2-4824605", make_response(text="<html><title>whatever</title></html>"))
    assert result.status is SourceStatus.PARSE_ERROR and result.metadata is None


def test_empty_title_is_parse_error():
    page = '<html><body><h1 class="x">[FC2-PPV-4824605]   </h1></body></html>'
    result, _, _ = _fetch("FC2-4824605", make_response(text=page))
    assert result.status is SourceStatus.PARSE_ERROR


def test_page_for_a_different_number_is_invalid_response_not_success():
    other = load_fixture("fc2db_net/work_4979299.html")
    result, _, _ = _fetch("FC2-4824605", make_response(text=other))
    assert result.status is SourceStatus.INVALID_RESPONSE and result.metadata is None


def test_missing_optional_json_ld_still_minimum_success():
    page = "<html><body><h1>[FC2-PPV-4824605] Just A Title</h1></body></html>"
    result, _, _ = _fetch("FC2-4824605", make_response(text=page))
    assert result.status is SourceStatus.SUCCESS
    assert result.metadata.title == "Just A Title"
    assert result.metadata.actors == () and result.metadata.runtime is None


def test_malformed_json_ld_is_ignored_not_fatal():
    page = (
        "<html><body><h1>[FC2-PPV-4824605] T</h1>"
        '<script type="application/ld+json">{not json</script></body></html>'
    )
    result, _, _ = _fetch("FC2-4824605", make_response(text=page))
    assert result.status is SourceStatus.SUCCESS and result.metadata.release is None


def test_non_canonical_number_is_rejected_before_any_request():
    client = FakeHttpClient()
    with pytest.raises(InvalidCanonicalNumberInputError):
        run(Fc2dbNetAdapter().fetch("4824605", client))
    assert client.requested_urls == []
