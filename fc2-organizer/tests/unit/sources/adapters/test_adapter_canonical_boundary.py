"""C0-01: every formal adapter refuses a non-canonical number *before any request*.

A ``"FC2-1234567\\n"`` used to pass the boundary check and blow up inside
httpx (``InvalidURL``) instead of being rejected as a caller bug. These tests
hand each real adapter a recording fake client and prove it is never called.
"""

from __future__ import annotations

import asyncio

import pytest

from fc2_metadata_core.errors import InvalidCanonicalNumberInputError
from fc2_metadata_core.models.source_result import SourceStatus
from fc2_metadata_core.sources.adapters import ALL_ADAPTER_CLASSES
from fc2_metadata_core.sources.adapters.av123 import Av123Adapter
from fc2_metadata_core.sources.adapters.fc2db_net import Fc2dbNetAdapter
from fc2_metadata_core.sources.adapters.javdb import JavdbAdapter

from support.fake_http_client import FakeHttpClient, make_response

FULLWIDTH = "１２３４５６７"
ARABIC_INDIC = "٤٨٢٤٦٠٥"

BAD_NUMBERS = [
    "FC2-1234567\n",
    "FC2-1234567\r\n",
    "FC2-" + FULLWIDTH,
    "FC2-" + ARABIC_INDIC,
    "FC2-1234567XYZ",
    "XFC2-1234567",
    "FC2-1234567/../x",
    "FC2-1234567?a=b",
    "",
    "4825061",
]

ADAPTERS = [Fc2dbNetAdapter, JavdbAdapter, Av123Adapter]


def test_the_three_formal_adapters_are_exactly_the_ones_covered_here():
    assert {cls for cls in ADAPTERS} == set(ALL_ADAPTER_CLASSES)


@pytest.mark.parametrize("adapter_cls", ADAPTERS, ids=lambda c: c.source_id)
@pytest.mark.parametrize("number", BAD_NUMBERS, ids=[ascii(n) for n in BAD_NUMBERS])
def test_non_canonical_number_is_rejected_without_any_http_call(adapter_cls, number):
    client = FakeHttpClient()
    with pytest.raises(InvalidCanonicalNumberInputError):
        asyncio.run(adapter_cls().fetch(number, client))
    assert client.requested_urls == []


@pytest.mark.parametrize("adapter_cls", ADAPTERS, ids=lambda c: c.source_id)
def test_a_valid_canonical_number_still_makes_exactly_one_request(adapter_cls):
    adapter = adapter_cls()
    client = FakeHttpClient()
    url = adapter._lookup_url("FC2-4825061")
    client.add_response(url, make_response(status_code=404, url=url))
    result = asyncio.run(adapter.fetch("FC2-4825061", client))
    assert result.status is SourceStatus.NOT_FOUND
    assert client.requested_urls == [url]
    assert "\n" not in url and url.isascii()
