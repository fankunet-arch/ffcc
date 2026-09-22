"""P4-C4: field mapping, exact output, optional fields, ordering, non-mapping,
status isolation and determinism of ``render_movie_nfo`` (contract sections 3-9,
test matrix 1-42).

Each behaviour is checked twice where it matters: once on the exact text
(golden, formatting frozen) and once through the stdlib XML parser (semantics).
"""

from __future__ import annotations

import pytest

from fc2_metadata_core.aggregation import AggregateStatus
from fc2_organizer.nfo import NfoReleaseDateError, render_movie_nfo

from ._builders import (
    ALL_SENTINELS,
    N,
    NON_RENDERED_FIELDS,
    SECRET_ERROR_DETAIL,
    SECRET_FIELD_SOURCE,
    SECRET_PUBLISHER,
    XML_DECLARATION,
    actors_of,
    child_texts,
    make_plan,
    make_record,
    parse,
    published,
)

FULL = dict(
    title="A & B",
    plot="Example <plot>",
    runtime=61,
    release="2026-09-19",
    studio="Example Studio",
    actors=("Alice", "Bob"),
    tags=("Tag A", "Tag B"),
)

GOLDEN_FULL = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<movie>
  <title>A &amp; B</title>
  <uniqueid type="fc2" default="true">FC2-1234567</uniqueid>
  <plot>Example &lt;plot&gt;</plot>
  <runtime>61</runtime>
  <premiered>2026-09-19</premiered>
  <studio>Example Studio</studio>
  <actor>
    <name>Alice</name>
    <order>0</order>
  </actor>
  <actor>
    <name>Bob</name>
    <order>1</order>
  </actor>
  <tag>Tag A</tag>
  <tag>Tag B</tag>
</movie>
"""

GOLDEN_MINIMAL = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<movie>
  <title>Example</title>
  <uniqueid type="fc2" default="true">FC2-1234567</uniqueid>
</movie>
"""


def _render(**fields) -> str:
    return render_movie_nfo(make_record(**fields))


def _element_order(xml_text: str) -> list[str]:
    return [child.tag for child in parse(xml_text)]


# ---- 1-10: basic mapping -----------------------------------------------------------------------------------------------


def test_01_minimum_record_renders_title_and_fc2_uniqueid_only_exactly():
    xml = _render()
    assert xml == GOLDEN_MINIMAL
    root = parse(xml)
    assert [c.tag for c in root] == ["title", "uniqueid"]
    assert root.findtext("title") == "Example"
    uid = root.find("uniqueid")
    assert uid.text == N and uid.attrib == {"type": "fc2", "default": "true"}


def test_02_full_supported_metadata_renders_the_frozen_golden_text():
    assert _render(**FULL) == GOLDEN_FULL


def test_02_full_supported_metadata_parses_back_to_the_input_semantics():
    root = parse(_render(**FULL))
    assert root.tag == "movie" and root.attrib == {}
    assert _element_order(_render(**FULL)) == [
        "title", "uniqueid", "plot", "runtime", "premiered", "studio", "actor", "actor", "tag", "tag",
    ]
    assert root.findtext("title") == "A & B"
    assert root.find("uniqueid").text == N
    assert root.find("uniqueid").attrib == {"type": "fc2", "default": "true"}
    assert root.findtext("plot") == "Example <plot>"
    assert root.findtext("runtime") == "61"
    assert root.findtext("premiered") == "2026-09-19"
    assert root.findtext("studio") == "Example Studio"
    assert actors_of(root) == [("Alice", "0"), ("Bob", "1")]
    assert child_texts(root, "tag") == ["Tag A", "Tag B"]


@pytest.mark.parametrize(
    "title",
    ["日本語タイトル 素人", "Ｆｕｌｌｗｉｄｔｈ", "é (combining, not NFC-normalised)", "  padded title  ", "MiXeD CaSe"],
)
def test_03_title_unicode_whitespace_and_case_are_preserved_exactly(title):
    xml = _render(title=title)
    assert parse(xml).findtext("title") == title
    assert f"<title>{title}</title>" in xml  # no normalisation, strip or case-fold in the text either


def test_04_ampersand_is_escaped_and_round_trips():
    xml = _render(title="A & B")
    assert "<title>A &amp; B</title>" in xml
    assert parse(xml).findtext("title") == "A & B"


def test_04_already_entity_looking_text_is_escaped_again_never_html_unescaped():
    xml = _render(title="A &amp; B &lt;x&gt; &#38; &nbsp;")
    assert "<title>A &amp;amp; B &amp;lt;x&amp;gt; &amp;#38; &amp;nbsp;</title>" in xml
    assert parse(xml).findtext("title") == "A &amp; B &lt;x&gt; &#38; &nbsp;"


def test_05_angle_brackets_are_escaped():
    xml = _render(title="A < C > D <Special>")
    assert "<title>A &lt; C &gt; D &lt;Special&gt;</title>" in xml
    assert parse(xml).findtext("title") == "A < C > D <Special>"


def test_06_quotes_and_apostrophes_in_text_are_preserved():
    title = """He said "hi" & it's 'fine'"""
    xml = _render(title=title)
    assert parse(xml).findtext("title") == title
    assert """<title>He said "hi" &amp; it's 'fine'</title>""" in xml


def test_07_emoji_and_non_bmp_text_encode_as_strict_utf8_and_round_trip():
    title = "🎬 𠮷野家 \U0010fffd"
    xml = _render(title=title, tags=("🏷️",))
    data = xml.encode("utf-8", errors="strict")
    assert data.decode("utf-8") == xml
    root = parse(xml)
    assert root.findtext("title") == title and root.findtext("tag") == "🏷️"


def test_08_exactly_one_final_newline():
    for xml in (_render(), _render(**FULL)):
        assert xml.endswith("</movie>\n") and not xml.endswith("\n\n")


def test_09_no_crlf_or_bare_cr_is_ever_emitted_even_for_multiline_plot():
    xml = _render(plot="line1\r\nline2\rline3\nline4")
    assert "\r" not in xml
    assert "<plot>line1&#13;\nline2&#13;line3\nline4</plot>" in xml
    assert parse(xml).findtext("plot") == "line1\r\nline2\rline3\nline4"


def test_10_root_is_exactly_movie_and_envelope_is_frozen():
    xml = _render(**FULL)
    lines = xml.split("\n")
    assert lines[0] == XML_DECLARATION
    assert lines[1] == "<movie>" and lines[-2] == "</movie>" and lines[-1] == ""
    assert parse(xml).tag == "movie"
    for line in lines[2:-2]:  # two-space indentation, nothing else
        stripped = line.lstrip(" ")
        assert (len(line) - len(stripped)) in (2, 4) and not stripped.startswith("\t")
    assert isinstance(xml, str) and type(xml) is str


# ---- 11-24: optional fields ----------------------------------------------------------------------------------------------


@pytest.mark.parametrize("plot", [None, "", "   ", "\n\t "])
def test_11_12_missing_or_blank_plot_is_omitted(plot):
    xml = _render(plot=plot)
    assert "<plot" not in xml and parse(xml).find("plot") is None


def test_plot_is_rendered_unchanged_no_truncation_no_rewrapping():
    plot = ("Long paragraph.  " * 500) + "\n\n  indented\ttab  "
    root = parse(_render(plot=plot))
    assert root.findtext("plot") == plot


def test_13_missing_runtime_is_omitted():
    assert "<runtime" not in _render(runtime=None)


def test_14_runtime_zero_is_rendered():
    xml = _render(runtime=0)
    assert "  <runtime>0</runtime>\n" in xml and parse(xml).findtext("runtime") == "0"


@pytest.mark.parametrize("runtime", [1, 61, 123, 600])
def test_15_positive_runtime_is_rendered_as_whole_minutes(runtime):
    assert parse(_render(runtime=runtime)).findtext("runtime") == str(runtime)


@pytest.mark.parametrize("release", [None, "", "   "])
def test_16_17_missing_or_blank_release_is_omitted(release):
    xml = _render(release=release)
    assert "<premiered" not in xml


@pytest.mark.parametrize("release", ["2026-09-19", "2026-02-28", "2000-02-29", "0001-01-01", "9999-12-31"])
def test_18_valid_release_is_rendered_as_premiered(release):
    assert parse(_render(release=release)).findtext("premiered") == release


def test_19_leap_day_is_valid():
    assert parse(_render(release="2024-02-29")).findtext("premiered") == "2024-02-29"


@pytest.mark.parametrize("release", ["2026-02-30", "2026-13-01", "2026-00-10", "2026-04-31", "2023-02-29", "0000-01-01"])
def test_20_impossible_calendar_date_is_rejected(release):
    with pytest.raises(NfoReleaseDateError):
        _render(release=release)


@pytest.mark.parametrize(
    "release",
    [
        "26-01-01", "20260101", "2026/09/19", "2026-9-19", "2026-09-19T00:00:00", "2026-09-19 ", " 2026-09-19",
        "2026-09-19\n", "１２３４-０１-０１", "٢٠٢٦-٠٩-١٩", "2026-W38-6", "2026-262", "+2026-09-19", "Sep 19, 2026",
    ],
)
def test_21_malformed_release_is_rejected_never_guessed_or_omitted(release):
    with pytest.raises(NfoReleaseDateError) as info:
        _render(release=release)
    assert release not in str(info.value)


@pytest.mark.parametrize("studio", [None, "", "  \t"])
def test_22_23_missing_or_blank_studio_is_omitted(studio):
    assert "<studio" not in _render(studio=studio)


def test_24_studio_is_rendered():
    assert parse(_render(studio="S1 & Co")).findtext("studio") == "S1 & Co"


def test_optional_elements_keep_frozen_relative_order_when_some_are_missing():
    xml = _render(runtime=0, studio="S", tags=("t",))
    assert _element_order(xml) == ["title", "uniqueid", "runtime", "studio", "tag"]
    xml = _render(plot="p", release="2026-01-01", actors=("a",))
    assert _element_order(xml) == ["title", "uniqueid", "plot", "premiered", "actor"]


# ---- 25-33: actors / tags ------------------------------------------------------------------------------------------------


def test_25_26_actors_keep_tuple_order_and_order_starts_at_zero():
    root = parse(_render(actors=("Zed", "Alice", "Mike")))
    assert actors_of(root) == [("Zed", "0"), ("Alice", "1"), ("Mike", "2")]


def test_27_actor_order_is_contiguous_after_blank_items_are_omitted():
    root = parse(_render(actors=("Alice", "   ", "", "Bob", "\t")))
    assert actors_of(root) == [("Alice", "0"), ("Bob", "1")]


def test_28_duplicate_actors_are_retained_in_order():
    root = parse(_render(actors=("Alice", "Bob", "Alice")))
    assert actors_of(root) == [("Alice", "0"), ("Bob", "1"), ("Alice", "2")]


def test_29_xml_special_actor_is_safely_escaped():
    name = '</name><order>99</order></actor><evil/><actor><name>x & "y"'
    xml = _render(actors=(name,))
    root = parse(xml)
    assert actors_of(root) == [(name, "0")]
    assert root.find(".//evil") is None and len(root.findall("actor")) == 1


def test_actor_element_exact_shape():
    xml = _render(actors=("A",))
    assert "  <actor>\n    <name>A</name>\n    <order>0</order>\n  </actor>\n" in xml
    assert [c.tag for c in parse(xml).find("actor")] == ["name", "order"]


def test_30_tags_keep_tuple_order():
    assert child_texts(parse(_render(tags=("z", "a", "m"))), "tag") == ["z", "a", "m"]


def test_31_blank_tags_are_omitted():
    assert child_texts(parse(_render(tags=("a", " ", "", "b"))), "tag") == ["a", "b"]


def test_32_duplicate_tags_are_retained():
    assert child_texts(parse(_render(tags=("a", "b", "a", "a"))), "tag") == ["a", "b", "a", "a"]


def test_33_tags_are_tag_elements_never_genre():
    xml = _render(tags=("Amateur",))
    assert "<genre" not in xml and parse(xml).find("genre") is None
    assert child_texts(parse(xml), "tag") == ["Amateur"]


def test_empty_actor_and_tag_tuples_emit_nothing():
    xml = _render(actors=(), tags=())
    assert "<actor" not in xml and "<tag" not in xml


# ---- 34-38: explicit non-mapping ------------------------------------------------------------------------------------------


@pytest.fixture
def xml_with_every_non_rendered_field():
    xml = _render(**FULL, **NON_RENDERED_FIELDS)
    return xml


def test_non_rendered_fields_do_not_change_the_output_at_all(xml_with_every_non_rendered_field):
    assert xml_with_every_non_rendered_field == GOLDEN_FULL


def test_34_publisher_is_absent(xml_with_every_non_rendered_field):
    xml = xml_with_every_non_rendered_field
    assert SECRET_PUBLISHER not in xml and "<publisher" not in xml and "<studio>Example Studio</studio>" in xml


def test_publisher_is_never_used_as_studio_fallback():
    xml = _render(publisher=SECRET_PUBLISHER)
    assert "<studio" not in xml and SECRET_PUBLISHER not in xml


def test_35_image_urls_are_absent(xml_with_every_non_rendered_field):
    xml = xml_with_every_non_rendered_field
    for sentinel in ("SECRET-POSTER-URL", "SECRET-THUMB-URL", "SECRET-FANART-URL", "SECRET-EXTRAFANART-URL"):
        assert sentinel not in xml
    assert "<thumb" not in xml and "<fanart" not in xml and "http" not in xml


def test_36_source_urls_are_absent(xml_with_every_non_rendered_field):
    assert "SECRET-SOURCE-URL" not in xml_with_every_non_rendered_field


def test_37_external_ids_are_absent_and_only_one_uniqueid_exists(xml_with_every_non_rendered_field):
    xml = xml_with_every_non_rendered_field
    assert "SECRET-EXTERNAL-ID" not in xml and "javdb" not in xml
    assert len(parse(xml).findall("uniqueid")) == 1


def test_38_field_sources_are_absent_including_as_comments_or_attributes(xml_with_every_non_rendered_field):
    xml = xml_with_every_non_rendered_field
    assert SECRET_FIELD_SOURCE not in xml and "<!--" not in xml
    for element in parse(xml).iter():
        if element.tag != "uniqueid":
            assert element.attrib == {}


def test_no_sentinel_of_any_kind_leaks(xml_with_every_non_rendered_field):
    for sentinel in ALL_SENTINELS:
        assert sentinel not in xml_with_every_non_rendered_field


# ---- 39-42: status isolation ----------------------------------------------------------------------------------------------


@pytest.mark.parametrize("status", [AggregateStatus.SUCCESS, AggregateStatus.PARTIAL])
def test_39_40_success_and_partial_records_render(status):
    assert _render(status=status, **FULL) == GOLDEN_FULL


def test_41_same_plan_same_metadata_success_vs_partial_is_byte_identical():
    plan = make_plan()
    a = make_record(plan=plan, status=AggregateStatus.SUCCESS, **FULL, **NON_RENDERED_FIELDS)
    b = make_record(plan=plan, status=AggregateStatus.PARTIAL, **FULL, **NON_RENDERED_FIELDS)
    assert a.plan == b.plan and a.metadata == b.metadata and a.aggregate_status != b.aggregate_status
    assert render_movie_nfo(a).encode("utf-8") == render_movie_nfo(b).encode("utf-8")


def test_41_real_published_success_and_partial_aggregates_render_identically():
    fields = dict(title="A & B", plot="p", runtime=5, actors=("x",), tags=("y",))
    a, b = published(partial=False, **fields), published(partial=True, **fields)
    assert a.aggregate_status is AggregateStatus.SUCCESS and b.aggregate_status is AggregateStatus.PARTIAL
    assert a.metadata == b.metadata
    xa, xb = render_movie_nfo(a), render_movie_nfo(b)
    assert xa == xb
    assert SECRET_ERROR_DETAIL not in xa and "SESSION-SECRET" not in xa


@pytest.mark.parametrize("status", [AggregateStatus.SUCCESS, AggregateStatus.PARTIAL])
def test_42_aggregate_status_literals_never_appear(status):
    xml = _render(status=status, **FULL).lower()
    for literal in ("success", "partial", "failed", "status", "aggregate", "<!--"):
        assert literal not in xml


# ---- determinism / purity ---------------------------------------------------------------------------------------------------


def test_same_record_rendered_100_times_gives_identical_text():
    record = make_record(**FULL, **NON_RENDERED_FIELDS)
    outputs = {render_movie_nfo(record) for _ in range(100)}
    assert outputs == {GOLDEN_FULL}


def test_equal_records_built_separately_render_identically():
    assert render_movie_nfo(make_record(**FULL)) == render_movie_nfo(make_record(**FULL))


def test_rendering_does_not_modify_the_record():
    plan = make_plan()
    record = make_record(plan=plan, **FULL, **NON_RENDERED_FIELDS)
    twin = make_record(plan=plan, **FULL, **NON_RENDERED_FIELDS)
    snapshot = repr(record)
    render_movie_nfo(record)
    assert record == twin and repr(record) == snapshot
