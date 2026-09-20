"""C0-04: ``NormalizedMetadata.runtime`` is WHOLE MINUTES, seconds truncated.

Unit frozen at Phase 3 Entry C0 (contract section 2.1b). Kodi's ``<runtime>``
is minutes only, so the Core normalizes to minutes once, at the source
boundary, and Phase 3 can merge values across sources without a conversion.
"""

from __future__ import annotations

import asyncio

import pytest

from fc2_metadata_core.models.metadata import NormalizedMetadata
from fc2_metadata_core.models.source_result import SourceStatus
from fc2_metadata_core.sources.adapters._common import duration_to_minutes
from fc2_metadata_core.sources.adapters.av123 import Av123Adapter, parse_av123_detail_page
from fc2_metadata_core.sources.adapters.fc2db_net import Fc2dbNetAdapter, parse_fc2db_work_page

from support.fake_http_client import FakeHttpClient, make_response


@pytest.mark.parametrize(
    "text, expected",
    [
        ("55:23", 55),  # the frozen examples
        ("1:02:03", 62),
        ("55:59", 55),  # truncated, NOT rounded up to 56
        ("0:00", 0),
        ("0:59", 0),
        ("59:59", 59),
        ("60:00", 60),
        ("120:05", 120),  # minutes > 59 in mm:ss form is legitimate
        ("1:00:00", 60),
        ("1:59:59", 119),
        ("2:59:59", 179),
        ("10:00:00", 600),
        (" 55:23 ", 55),  # surrounding whitespace is tolerated
    ],
)
def test_clock_durations_convert_to_whole_minutes_truncating_seconds(text, expected):
    assert duration_to_minutes(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        None,
        "",
        "   ",
        "abc",
        "55",
        "55:",
        ":55",
        "55:2",  # seconds must be two digits
        "55:23:",
        "1:2:03",  # minutes must be two digits in h:mm:ss
        "-5:00",
        "55:60",  # seconds out of range -> malformed, not "56 minutes"
        "55:75",
        "1:60:00",  # minutes out of range in h:mm:ss
        "1:75:00",
        "55m23s",
        "PT55M23S",  # ISO-8601 is not a clock duration
        "55.5",
        "٥٥:٢٣",  # Arabic-Indic digits: not ASCII
        "５５:２３",  # fullwidth digits
        "5" * 5000 + ":00",  # absurdly long -> refused without scanning
        " " * 100_000 + "55:23",
    ],
    ids=lambda v: repr(v)[:30],
)
def test_anything_that_is_not_an_ascii_clock_duration_is_none(text):
    assert duration_to_minutes(text) is None


def test_result_is_a_plain_int_accepted_by_the_frozen_metadata_type():
    minutes = duration_to_minutes("55:23")
    assert type(minutes) is int
    assert NormalizedMetadata(number="FC2-1234567", title="t", runtime=minutes).runtime == 55


# ---- the adapters emit minutes end to end -------------------------------------------------


def _fc2db_page(duration: str) -> str:
    return (
        "<h1>[FC2-PPV-4824605] T</h1>"
        '<script type="application/ld+json">'
        '{"@type": "VideoObject", "duration": "%s"}</script>' % duration
    )


@pytest.mark.parametrize("duration, expected", [("55:23", 55), ("55:59", 55), ("1:02:03", 62), ("bad", None)])
def test_fc2db_net_emits_whole_minutes(duration, expected):
    metadata, error = parse_fc2db_work_page(_fc2db_page(duration), "FC2-4824605", "u")
    assert error is None
    assert metadata.runtime == expected


def _av123_page(duration: str) -> str:
    return (
        '<h1 class="watch__title">FC2-PPV-4825061 — T</h1>'
        '<div class="watch__info-row"> <dt>Duration</dt> <dd>%s</dd> </div>' % duration
    )


@pytest.mark.parametrize("duration, expected", [("39:05", 39), ("55:59", 55), ("1:02:03", 62), ("n/a", None)])
def test_av123_emits_whole_minutes(duration, expected):
    metadata, error = parse_av123_detail_page(_av123_page(duration), "FC2-4825061", "u")
    assert error is None
    assert metadata.runtime == expected


def test_a_missing_or_malformed_runtime_never_fails_the_lookup():
    for adapter, number, page in (
        (Fc2dbNetAdapter(), "FC2-4824605", _fc2db_page("garbage")),
        (Av123Adapter(), "FC2-4825061", _av123_page("garbage")),
    ):
        client = FakeHttpClient()
        url = adapter._lookup_url(number)
        client.add_response(url, make_response(url=url, text=page))
        result = asyncio.run(adapter.fetch(number, client))
        assert result.status is SourceStatus.SUCCESS
        assert result.metadata.runtime is None
