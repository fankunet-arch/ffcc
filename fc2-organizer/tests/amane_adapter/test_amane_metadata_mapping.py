"""P5-C1 表 H（E11）：``NormalizedMetadata`` -> 中立记录 -> ``MediaMetadata`` 字段的逐字段处置与 URL 卫生过滤。"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import pytest

from _amane_scenarios import TITLE_4979299, client_4979299, lookup, runtime_for
from fc2_amane_adapter._outcome import (
    CORE_FIELD_DISPOSITION,
    TARGET_FIELD_DISPOSITION,
    AdapterFound,
    AdapterRecord,
    filter_urls,
    is_clean_http_url,
    map_record,
)
from fc2_metadata_core.models import NormalizedMetadata
from support.source_fixtures import load_fixture

MANIFEST = json.loads(
    (Path(__file__).resolve().parents[2] / "adapters" / "amane" / "api_manifest" / "amane_v0.15.0_api_manifest.json").read_text(encoding="utf-8")
)
CANONICAL = "FC2-4979299"


def _metadata(**overrides) -> NormalizedMetadata:
    fields = dict(
        number=CANONICAL,
        title="T",
        studio="S",
        publisher="P",
        release="2026-09-19",
        runtime=78,
        actors=("A1", "A2"),
        tags=("t1", "t2"),
        plot="plot",
        poster_urls=("https://h.example/p.jpg",),
        thumb_urls=("https://h.example/t.jpg",),
        fanart_urls=("https://h.example/fanart.jpg",),
        extrafanart=("https://h.example/e1.jpg", "https://h.example/e2.jpg"),
        source_urls=("https://src.example/1", "https://src.example/2"),
        external_ids={"javdb": "QNkPbM"},
        field_sources={"title": ("javdb",)},
    )
    fields.update(overrides)
    return NormalizedMetadata(**fields)


def test_every_core_field_has_an_explicit_disposition():
    """Core 将来新增字段而表里没有处置 -> 本测试失败。"""
    assert set(CORE_FIELD_DISPOSITION) == {f.name for f in dataclasses.fields(NormalizedMetadata)}
    assert len(CORE_FIELD_DISPOSITION) == 16
    assert CORE_FIELD_DISPOSITION["fanart_urls"] == "not_representable"
    assert CORE_FIELD_DISPOSITION["external_ids"] == "not_exported"
    assert CORE_FIELD_DISPOSITION["field_sources"] == "not_exported"
    assert CORE_FIELD_DISPOSITION["source_urls"] == "narrowed:source_url"


def test_every_amane_target_field_has_an_explicit_source():
    """manifest 里 ``MediaMetadata`` 出现本表未处置的字段 -> 本测试失败。"""
    assert set(TARGET_FIELD_DISPOSITION) == set(MANIFEST["classes"]["MediaMetadata"]["fields"])
    assert len(TARGET_FIELD_DISPOSITION) == 18
    assert TARGET_FIELD_DISPOSITION["series"].startswith("absent")
    assert TARGET_FIELD_DISPOSITION["directors"].startswith("absent")
    assert TARGET_FIELD_DISPOSITION["trailer_urls"].startswith("absent")
    assert TARGET_FIELD_DISPOSITION["score"].startswith("absent")


def test_record_fields_are_exactly_the_mapped_and_narrowed_targets():
    mapped = {name for name, value in TARGET_FIELD_DISPOSITION.items() if not value.startswith("absent")}
    assert {f.name for f in dataclasses.fields(AdapterRecord)} == mapped


def test_scalar_and_list_fields_map_one_to_one_in_core_order():
    record = map_record(_metadata(), CANONICAL)
    assert (record.number, record.title, record.studio, record.publisher, record.release, record.runtime, record.plot) == (
        CANONICAL, "T", "S", "P", "2026-09-19", 78, "plot",
    )
    assert record.actors == ("A1", "A2") and record.tags == ("t1", "t2")
    assert record.poster_urls == ("https://h.example/p.jpg",) and record.thumb_urls == ("https://h.example/t.jpg",)
    assert record.extrafanart == ("https://h.example/e1.jpg", "https://h.example/e2.jpg")
    assert all(isinstance(getattr(record, name), tuple) for name in ("actors", "tags", "poster_urls", "thumb_urls", "extrafanart"))


def test_missing_values_stay_none_or_empty_and_runtime_zero_is_preserved():
    record = map_record(NormalizedMetadata(number=CANONICAL, title="T"), CANONICAL)
    assert (record.studio, record.publisher, record.release, record.runtime, record.plot) == (None, None, None, None, None)
    assert record.actors == record.tags == record.poster_urls == record.thumb_urls == record.extrafanart == ()
    assert record.source_url is None and record.external_id == "4979299"
    assert map_record(_metadata(runtime=0), CANONICAL).runtime == 0


def test_blank_actor_names_are_dropped_and_others_kept_verbatim():
    record = map_record(_metadata(actors=("A1", "", "  ", "\u3000", " A2 ")), CANONICAL)
    assert record.actors == ("A1", " A2 ")


def test_fanart_is_dropped_and_never_stuffed_into_another_field():
    """M-09：显式 ``fanart_urls`` 不并入 thumb_urls / extrafanart / poster_urls。"""
    fanart = "https://h.example/fanart.jpg"
    record = map_record(_metadata(), CANONICAL)
    for value in dataclasses.astuple(record):
        flat = value if isinstance(value, tuple) else (value,)
        assert fanart not in flat
    assert record.thumb_urls == ("https://h.example/t.jpg",)
    only_fanart = map_record(_metadata(thumb_urls=(), extrafanart=(), poster_urls=()), CANONICAL)
    assert only_fanart.thumb_urls == only_fanart.extrafanart == only_fanart.poster_urls == ()


@pytest.mark.parametrize(
    "url",
    [
        "https://h.example/a.jpg",
        "http://h.example/a.jpg",
        "https://h.example:8443/a?x=1&y=2#f",
        "HTTPS://H.EXAMPLE/A.JPG",
        "http://127.0.0.1/a.jpg",
        "https://[::1]/a.jpg",
        "https://h.example/a b.jpg",
    ],
)
def test_clean_http_urls_are_kept_verbatim(url):
    assert is_clean_http_url(url) and filter_urls((url,)) == (url,)


@pytest.mark.parametrize(
    "url",
    [
        "",
        "/relative/a.jpg",
        "a.jpg",
        "//h.example/a.jpg",
        "javascript:alert(1)",
        "data:image/png;base64,AAAA",
        "ftp://h.example/a.jpg",
        "file:///C:/x.jpg",
        "http://",
        "https:///a.jpg",
        "https://",
        " https://h.example/a.jpg",
        "https://h.example/a.jpg ",
        "https://h.example/a\n.jpg",
        "https://h.example/\x00a.jpg",
        "https://[::1/a.jpg",
        None,
        5,
    ],
)
def test_non_http_relative_or_malformed_urls_are_dropped(url):
    assert not is_clean_http_url(url)


def test_filtering_only_deletes_never_reorders_or_rewrites():
    urls = ("https://b.example/2", "/x", "HTTP://A.example/1", "javascript:x", "https://c.example/3")
    assert filter_urls(urls) == ("https://b.example/2", "HTTP://A.example/1", "https://c.example/3")


def test_all_url_fields_are_filtered_and_source_url_is_the_first_valid_one():
    record = map_record(
        _metadata(
            poster_urls=("/p", "https://h.example/p.jpg"),
            thumb_urls=("javascript:x",),
            extrafanart=("ftp://x/e", "https://h.example/e.jpg"),
            source_urls=("/relative", "https://src.example/ok", "https://src.example/later"),
        ),
        CANONICAL,
    )
    assert record.poster_urls == ("https://h.example/p.jpg",)
    assert record.thumb_urls == ()
    assert record.extrafanart == ("https://h.example/e.jpg",)
    assert record.source_url == "https://src.example/ok"


def test_mapping_is_a_deterministic_pure_function():
    metadata = _metadata()
    assert map_record(metadata, CANONICAL) == map_record(metadata, CANONICAL)
    assert map_record(_metadata(), CANONICAL) == map_record(_metadata(), CANONICAL)


def test_real_fixture_chain_matches_the_values_in_the_fixture_html():
    """端到端（真实 Core + 真实 fixture HTML）：预期值由 fixture 文本独立佐证。"""
    outcome = lookup(runtime_for(client_4979299()), "FC2-PPV-4979299")
    assert isinstance(outcome, AdapterFound)
    record = outcome.record
    assert record.number == CANONICAL and record.title == TITLE_4979299
    assert record.release == "2026-09-19" and "春野くるみ" in record.actors
    assert record.external_id == "4979299"
    assert record.source_url == "https://fc2db.net/work/4979299/"  # 默认配置顺序里最靠前且提供了 URL 的来源
    assert record.thumb_urls and all(url.startswith("https://") for url in record.thumb_urls)
    corpus = load_fixture("fc2db_net/work_4979299.html") + load_fixture("javdb/search_hit_4979299.html")
    assert "春野くるみ" in corpus and "2026-09-19" in corpus or "2026/09/19" in corpus
    for url in record.thumb_urls:
        assert url.split("?")[0] in corpus
    assert not hasattr(record, "fanart_urls")
