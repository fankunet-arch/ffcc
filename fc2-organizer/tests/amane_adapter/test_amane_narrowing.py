"""P5-C1 §19.3（E12）：复数 -> 单数的确定性窄化 N-1 ``source_url`` / N-2 ``external_id``。"""

from __future__ import annotations

import pytest

from _amane_scenarios import client_4979299, lookup, runtime_for
from fc2_amane_adapter._outcome import AdapterFound, map_record, narrow_external_id, narrow_source_url
from fc2_metadata_core.models import NormalizedMetadata
from support.source_fixtures import load_fixture

CANONICAL = "FC2-4979299"
FC2DB_URL = "https://fc2db.net/work/4979299/"
AV123_URL = "https://123av.com/en/v/fc2-ppv-4979299"
JAVDB_URL = "https://javdb.com/v/QNkPbM"
ALL = ("fc2db_net", "javdb", "av123")


def _record(order):
    outcome = lookup(runtime_for(client_4979299(), {"sources": [{"id": i} for i in order]}), "FC2-PPV-4979299")
    assert isinstance(outcome, AdapterFound)
    return outcome.record


def test_author_constants_are_present_in_the_fixture_html():
    assert "QNkPbM" in load_fixture("javdb/search_hit_4979299.html")


@pytest.mark.parametrize(
    ("order", "expected"),
    [
        (("fc2db_net", "javdb", "av123"), FC2DB_URL),
        (("av123", "javdb", "fc2db_net"), AV123_URL),
        (("javdb", "fc2db_net", "av123"), JAVDB_URL),
        (("javdb", "av123", "fc2db_net"), JAVDB_URL),
    ],
)
def test_n1_source_url_follows_configuration_order_only(order, expected):
    """多个来源提供不同 URL：结果只随配置顺序以规定方式变化（M-04：不得取最后一个）。"""
    assert _record(order).source_url == expected


def test_n1_is_stable_across_repeated_runs():
    assert {_record(ALL).source_url for _ in range(5)} == {FC2DB_URL}


def test_n1_skips_invalid_urls_then_none_when_none_valid_or_empty():
    assert narrow_source_url(("", "/rel", "javascript:x", "https://ok.example/1", "https://ok.example/2")) == "https://ok.example/1"
    assert narrow_source_url(("", "/rel", "ftp://x/y")) is None
    assert narrow_source_url(()) is None


def test_n2_external_id_is_the_canonical_digits_whatever_the_order():
    for order in (ALL, tuple(reversed(ALL)), ("javdb", "av123", "fc2db_net")):
        assert _record(order).external_id == "4979299"


@pytest.mark.parametrize(("canonical", "digits"), [("FC2-4825061", "4825061"), ("FC2-12345", "12345"), ("FC2-12345678", "12345678")])
def test_n2_unit(canonical, digits):
    assert narrow_external_id(canonical) == digits


def test_n2_never_uses_core_external_ids_even_when_they_conflict():
    """M-05：Core 的 ``external_ids``（各内部站点的私有 id）永不成为本插件的 external_id。"""
    for ids in ({"javdb": "QNkPbM"}, {"javdb": "QNkPbM", "av123": "999", "fc2db_net": "123"}, {"a": "1"}, {}):
        metadata = NormalizedMetadata(number=CANONICAL, title="T", external_ids=ids)
        assert map_record(metadata, CANONICAL).external_id == "4979299"


def test_real_core_ids_differ_from_the_narrowed_external_id():
    runtime = runtime_for(client_4979299())
    import asyncio

    result = asyncio.run(runtime._engine.aggregate(CANONICAL))
    core_ids = dict(result.metadata.external_ids)
    assert core_ids, "the fixture chain should provide at least one Core-internal id"
    outcome = lookup(runtime_for(client_4979299()), "FC2-PPV-4979299")
    assert outcome.record.external_id not in core_ids.values()
    assert outcome.record.external_id == "4979299"


def test_conflicting_source_urls_and_ids_change_only_with_documented_inputs():
    base = dict(number=CANONICAL, title="T", external_ids={"javdb": "A"})
    first = map_record(NormalizedMetadata(**base, source_urls=("https://a.example/1", "https://b.example/2")), CANONICAL)
    swapped = map_record(NormalizedMetadata(**base, source_urls=("https://b.example/2", "https://a.example/1")), CANONICAL)
    other_ids = map_record(
        NormalizedMetadata(number=CANONICAL, title="T", external_ids={"javdb": "Z"}, source_urls=("https://a.example/1", "https://b.example/2")),
        CANONICAL,
    )
    assert first.source_url == "https://a.example/1" and swapped.source_url == "https://b.example/2"
    assert other_ids == first  # external_ids 的变化不影响任何输出字段
