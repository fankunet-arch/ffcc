"""123av.com adapter: parser against real captured markup + full ``fetch`` contract."""

from __future__ import annotations

import asyncio

import pytest

from fc2_metadata_core.errors import InvalidCanonicalNumberInputError
from fc2_metadata_core.http.client import HttpConnectionError, HttpTimeoutError
from fc2_metadata_core.models.source_result import SourceStatus
from fc2_metadata_core.sources.adapters.av123 import Av123Adapter, parse_av123_detail_page

from support.fake_http_client import FakeHttpClient, make_response
from support.source_fixtures import load_fixture

SID = "av123"


def run(coro):
    return asyncio.run(coro)


def _fetch(number, response=None, *, error=None):
    adapter = Av123Adapter()
    client = FakeHttpClient()
    url = adapter._lookup_url(number)
    if error is not None:
        client.add_error(url, error)
    else:
        client.add_response(url, response if response is not None else make_response(url=url))
    return run(adapter.fetch(number, client)), client, url


def test_lookup_url_and_base_url_override():
    assert Av123Adapter()._lookup_url("FC2-4825061") == "https://123av.com/en/v/fc2-ppv-4825061"
    assert Av123Adapter(base_url="https://mirror.invalid")._lookup_url("FC2-4825061") == (
        "https://mirror.invalid/en/v/fc2-ppv-4825061"
    )


def test_parse_4825061_real_page():
    md, err = parse_av123_detail_page(
        load_fixture("av123/detail_4825061.html"), "FC2-4825061", "https://123av.com/en/v/fc2-ppv-4825061", SID
    )
    assert err is None and md is not None
    assert md.number == "FC2-4825061"
    # the entity in the real markup (&#039;) must come out as a plain apostrophe
    assert md.title == (
        "[Face Revealed] Half-Japanese Beautiful Wife's First And Last Face Revealed "
        "Unreleased Video X 2 *Only For Sns Authenticated Users"
    )
    assert md.release == "2026-01-02"
    assert md.runtime == 39
    assert md.tags == ("Amateur",)
    assert md.source_urls == ("https://123av.com/en/v/fc2-ppv-4825061",)
    # the generic "Maker: FC2" bucket is deliberately not mapped
    assert md.studio is None and md.publisher is None
    assert md.meets_minimum_success()
    assert md.field_sources["title"] == (SID,)


def test_parse_second_real_page_4979299():
    md, err = parse_av123_detail_page(load_fixture("av123/detail_4979299.html"), "FC2-4979299", "u", SID)
    assert err is None and md is not None
    assert md.number == "FC2-4979299"
    assert md.title.startswith("Her dream is to be an elementary school teacher")
    assert md.meets_minimum_success()


def test_fetch_success_single_request():
    number = "FC2-4825061"
    url = Av123Adapter()._lookup_url(number)
    result, client, _ = _fetch(number, make_response(url=url, text=load_fixture("av123/detail_4825061.html")))
    assert result.status is SourceStatus.SUCCESS and result.metadata.number == number
    assert client.requested_urls == [url]


def test_real_404_is_not_found():
    number = "FC2-4824605"
    url = Av123Adapter()._lookup_url(number)
    result, _, _ = _fetch(
        number,
        make_response(status_code=404, url=url, text=load_fixture("av123/detail_404_4824605.html")),
    )
    assert result.status is SourceStatus.NOT_FOUND and result.metadata is None


@pytest.mark.parametrize(
    "kwargs, expected",
    [
        ({"status_code": 403}, SourceStatus.BLOCKED),
        ({"status_code": 200, "text": load_fixture("common/cloudflare_challenge.html")}, SourceStatus.BLOCKED),
        ({"status_code": 429}, SourceStatus.RATE_LIMITED),
        ({"status_code": 500}, SourceStatus.INVALID_RESPONSE),
    ],
)
def test_failure_statuses(kwargs, expected):
    result, _, _ = _fetch("FC2-4825061", make_response(**kwargs))
    assert result.status is expected and result.metadata is None


@pytest.mark.parametrize("exc", [HttpTimeoutError("t"), HttpConnectionError("c")])
def test_transport_errors(exc):
    result, _, _ = _fetch("FC2-4825061", error=exc)
    assert result.status is SourceStatus.NETWORK_ERROR


def test_200_without_heading_is_parse_error():
    result, _, _ = _fetch("FC2-4825061", make_response(text="<html><title>x</title></html>"))
    assert result.status is SourceStatus.PARSE_ERROR


def test_page_for_different_number_is_invalid_response():
    result, _, _ = _fetch("FC2-4825061", make_response(text=load_fixture("av123/detail_4979299.html")))
    assert result.status is SourceStatus.INVALID_RESPONSE


def test_release_not_a_date_is_dropped_not_guessed():
    page = (
        '<h1 class="watch__title">FC2-PPV-4825061 — T</h1>'
        '<div class="watch__info-row"> <dt>Release date</dt> <dd>soon</dd> </div>'
    )
    result, _, _ = _fetch("FC2-4825061", make_response(text=page))
    assert result.status is SourceStatus.SUCCESS and result.metadata.release is None


def test_non_canonical_number_rejected_before_request():
    client = FakeHttpClient()
    with pytest.raises(InvalidCanonicalNumberInputError):
        run(Av123Adapter().fetch("fc2 4825061", client))
    assert client.requested_urls == []
