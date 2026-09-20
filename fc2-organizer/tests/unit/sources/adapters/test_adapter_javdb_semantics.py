"""C0-03: JavDB layout drift must never masquerade as ``NOT_FOUND``.

Phase 3 treats ``NOT_FOUND`` as a normal coverage gap, so the parser has to
tell apart:

A. a readable result list with candidate numbers, none exact  -> NOT_FOUND
B. a result list from which *no* candidate number can be read  -> INVALID_RESPONSE
C. the requested number identified, but no usable title        -> PARSE_ERROR

and the ``N`` in the NOT_FOUND detail must be the number of candidate numbers
actually parsed, not a count of HTML chunks.
"""

from __future__ import annotations

import asyncio

import pytest

from fc2_metadata_core.models.source_result import SourceStatus
from fc2_metadata_core.sources.adapters.javdb import JavdbAdapter, parse_javdb_search_page

from support.fake_http_client import FakeHttpClient, make_response
from support.source_fixtures import load_fixture

BASE = "https://javdb.com"
SID = "javdb"


def item(
    code="FC2-4825061",
    title="A Title",
    *,
    item_cls="item",
    vt_cls="video-title",
    number_markup="<strong>{code}</strong>",
    href="/v/AAA111",
    title_attr=None,
    date="2026-01-02",
    quote='"',
):
    attr = title if title_attr is None else title_attr
    strong = number_markup.format(code=code)
    return (
        f"<div class={quote}{item_cls}{quote}>"
        f'<a href="{href}" class="box" title="{attr}">'
        f'<div class="cover "><img loading="lazy" src="https://c0.jdbstatic.com/covers/aa/AAA111.jpg" /></div>'
        f"<div class={quote}{vt_cls}{quote}>{strong} {title}</div>"
        f'<div class="meta">\n      {date}\n    </div>'
        f"</a></div>"
    )


def page(*items, list_cls="movie-list h cols-4 vcols-8"):
    return f'<html><body><div class="toolbar"></div><div class="{list_cls}">' + "".join(items) + "</div></body></html>"


def parse(html, number="FC2-4825061"):
    return parse_javdb_search_page(html, number, BASE, SID)


def status_of(html, number="FC2-4825061"):
    metadata, error = parse(html, number)
    return ("success", metadata) if metadata is not None else (error[0], error[1])


# ---- tolerated cosmetic drift (must still SUCCEED) ---------------------------------


@pytest.mark.parametrize(
    "kwargs",
    [
        {"item_cls": "item "},  # trailing space -- the reviewer's example
        {"item_cls": " item"},
        {"item_cls": "item is-featured"},  # extra CSS class after
        {"item_cls": "is-featured item"},  # extra CSS class before
        {"vt_cls": "video-title is-clamped"},  # extra class on the title element
        {"vt_cls": " video-title "},
        {"quote": "'"},  # single-quoted attributes
    ],
    ids=lambda k: str(k),
)
def test_cosmetic_class_drift_still_parses_the_exact_hit(kwargs):
    status, metadata = status_of(page(item(**kwargs)))
    assert status == "success"
    assert metadata.number == "FC2-4825061" and metadata.title == "A Title"
    assert metadata.release == "2026-01-02"


def test_extra_class_on_the_list_container_is_fine():
    status, metadata = status_of(page(item(), list_cls="movie-list is-x other"))
    assert status == "success"


# ---- A: readable candidates, none exact -> NOT_FOUND --------------------------------


def test_fuzzy_near_misses_only_is_not_found_and_counts_parsed_numbers():
    html = page(item("FC2-1825061"), item("FC2-4725061"))
    status, detail = status_of(html)
    assert status is SourceStatus.NOT_FOUND
    assert "listed 2 other number(s)" in detail


def test_real_fuzzy_page_for_4824605_is_not_found_with_two_parsed_candidates():
    html = load_fixture("javdb/search_no_exact_4824605.html")
    status, detail = status_of(html, "FC2-4824605")
    assert status is SourceStatus.NOT_FOUND
    assert "listed 2 other number(s)" in detail  # FC2-1824605 and FC2-4724605


def test_not_found_count_is_parsed_candidates_not_html_chunks():
    unreadable = '<div class="item"><a href="/v/ZZZ" class="box" title="x">no video-title here</a></div>'
    html = page(item("FC2-1111111"), unreadable, item("FC2-2222222"), unreadable)
    status, detail = status_of(html)
    assert status is SourceStatus.NOT_FOUND
    assert "listed 2 other number(s)" in detail  # 4 item elements, 2 readable


def test_other_studio_codes_are_candidates_too():
    status, detail = status_of(page(item("heydouga-4079-299")))
    assert status is SourceStatus.NOT_FOUND
    assert "listed 1 other number(s)" in detail


def test_exact_item_among_fuzzy_items_wins():
    html = page(item("FC2-1825061", "wrong one"), item("FC2-4825061", "right one"), item("FC2-4825062", "x"))
    status, metadata = status_of(html)
    assert status == "success" and metadata.title == "right one"


# ---- B: list present, nothing parseable -> INVALID_RESPONSE ---------------------------


@pytest.mark.parametrize(
    "html",
    [
        page(item(vt_cls="video-name")),  # video-title class renamed
        page(item(item_cls="movie-item")),  # item class renamed
        page(item(number_markup="<b>{code}</b>")),  # <strong> replaced
        page(item(vt_cls="video-name"), item("FC2-1", vt_cls="video-name")),
        '<div class="movie-list"></div>',  # container but zero items
        page("<div class=\"item\"></div>", "<div class=\"item\"></div>"),
    ],
    ids=["video-title-renamed", "item-renamed", "strong-replaced", "all-items-drifted", "empty-container", "empty-items"],
)
def test_result_list_without_a_single_parseable_number_is_invalid_response(html):
    status, detail = status_of(html)
    assert status is SourceStatus.INVALID_RESPONSE
    assert "no candidate number could be parsed" in detail


def test_neither_list_nor_empty_marker_is_invalid_response():
    status, _ = status_of("<html><body><p>totally different page</p></body></html>")
    assert status is SourceStatus.INVALID_RESPONSE


def test_partial_drift_is_not_hidden_when_at_least_one_number_parses():
    # One readable non-exact candidate + one drifted item: layout is still
    # recognizable, so this is a normal miss, not INVALID_RESPONSE.
    html = page(item("FC2-1111111"), item("FC2-4825061", vt_cls="video-name"))
    status, detail = status_of(html)
    assert status is SourceStatus.NOT_FOUND and "listed 1 other number(s)" in detail


# ---- zero results: explicit marker only -------------------------------------------------


def test_real_empty_result_page_is_not_found():
    status, _ = status_of(load_fixture("javdb/search_empty_99999999.html"), "FC2-9999999")
    assert status is SourceStatus.NOT_FOUND


def test_empty_marker_tolerates_extra_classes():
    status, _ = status_of('<div class="empty-message is-x">暫無內容</div>')
    assert status is SourceStatus.NOT_FOUND


# ---- C: exact number identified but unusable -> PARSE_ERROR -----------------------------


def test_exact_number_with_no_title_anywhere_is_parse_error_not_not_found():
    html = page(item("FC2-4825061", title="", title_attr=""))
    status, _ = status_of(html)
    assert status is SourceStatus.PARSE_ERROR


def test_exact_number_with_no_title_attribute_falls_back_to_visible_title():
    html = page(item("FC2-4825061", title="Visible Title", title_attr=""))
    status, metadata = status_of(html)
    assert status == "success" and metadata.title == "Visible Title"


def test_exact_number_with_blank_title_and_other_fuzzy_items_is_still_parse_error():
    html = page(item("FC2-1825061"), item("FC2-4825061", title="", title_attr=""))
    status, _ = status_of(html)
    assert status is SourceStatus.PARSE_ERROR


# ---- through fetch(): the SourceResult carries the same semantics ------------------------


def _fetch(html, number="FC2-4825061"):
    adapter = JavdbAdapter()
    client = FakeHttpClient()
    url = adapter._lookup_url(number)
    client.add_response(url, make_response(url=url, text=html))
    return asyncio.run(adapter.fetch(number, client))


def test_fetch_layout_drift_is_invalid_response_result():
    result = _fetch(page(item(vt_cls="video-name")))
    assert result.status is SourceStatus.INVALID_RESPONSE and result.metadata is None


def test_fetch_fuzzy_only_is_not_found_result():
    result = _fetch(page(item("FC2-1825061")))
    assert result.status is SourceStatus.NOT_FOUND and result.metadata is None


def test_fetch_exact_without_title_is_parse_error_result():
    result = _fetch(page(item(title="", title_attr="")))
    assert result.status is SourceStatus.PARSE_ERROR and result.metadata is None
