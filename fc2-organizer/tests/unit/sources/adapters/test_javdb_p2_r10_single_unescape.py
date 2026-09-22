"""P2-R-10 closure (P4-C3): the JavDB detail-anchor ``title`` attribute is entity-decoded exactly once.

``parse_attrs`` returns the raw, still entity-encoded attribute value and ``clean_text`` decodes entities itself,
so the historical ``clean_text(html.unescape(...))`` decoded twice: ``title="A &amp;amp; B"`` (whose real text is
``A &amp; B``) came out as ``A & B``. Only this path changed; the text-title fallback, whitespace cleaning, tag
stripping and exact-number matching are pinned unchanged below.
"""

from __future__ import annotations

import html

import pytest

from fc2_metadata_core.models.source_result import SourceStatus
from fc2_metadata_core.sources.adapters._common import clean_text
from fc2_metadata_core.sources.adapters.javdb import parse_javdb_search_page

BASE = "https://javdb.com"
SID = "javdb"
N = "FC2-4825061"


def item(code=N, text_title="Text Title", *, title_attr="Attr Title", href="/v/AAA111"):
    return (
        '<div class="item">'
        f'<a href="{href}" class="box" title="{title_attr}">'
        '<div class="cover "><img loading="lazy" src="https://c0.jdbstatic.com/covers/aa/AAA111.jpg" /></div>'
        f'<div class="video-title"><strong>{code}</strong> {text_title}</div>'
        '<div class="meta">\n      2026-01-02\n    </div>'
        "</a></div>"
    )


def page(*items):
    return '<html><body><div class="movie-list h cols-4">' + "".join(items) + "</div></body></html>"


def title_of(html_text, number=N):
    metadata, failure = parse_javdb_search_page(html_text, number, BASE, SID)
    assert failure is None, failure
    return metadata.title


# ---- 30, 31: exactly one decode -------------------------------------------------------------------------------------------


def test_30_a_plain_entity_is_decoded_once():
    assert title_of(page(item(title_attr="A &amp; B"))) == "A & B"


def test_31_a_nested_entity_keeps_its_literal_after_one_decode():
    assert title_of(page(item(title_attr="A &amp;amp; B"))) == "A &amp; B"


def test_31_the_old_double_decode_really_produced_the_wrong_value():
    """Guards the fix itself: the historical formula would not have passed test 31."""
    raw = "A &amp;amp; B"
    assert clean_text(html.unescape(raw)) == "A & B"  # the P2-R-10 defect
    assert clean_text(raw) == "A &amp; B"  # the fixed single decode


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("&#38;amp; numeric", "&amp; numeric"),
        ("&quot;quoted&quot;", '"quoted"'),
        ("caf&eacute;", "café"),
        ("&amp;lt;tag&amp;gt;", "&lt;tag&gt;"),
        ("素人 &amp; 初撮り", "素人 & 初撮り"),
    ],
)
def test_other_entities_are_decoded_exactly_once(raw, expected):
    assert title_of(page(item(title_attr=raw))) == expected


# ---- 32: text-title fallback unchanged --------------------------------------------------------------------------------------


def test_32_empty_attribute_falls_back_to_the_text_title():
    assert title_of(page(item(text_title="Visible Title", title_attr=""))) == "Visible Title"


def test_32_text_title_fallback_decoding_is_unchanged_single_decode():
    assert title_of(page(item(text_title="Visible &amp;amp; Title", title_attr=""))) == "Visible &amp; Title"


def test_32_no_title_anywhere_is_still_a_parse_error():
    metadata, failure = parse_javdb_search_page(page(item(text_title="", title_attr="")), N, BASE, SID)
    assert metadata is None and failure[0] is SourceStatus.PARSE_ERROR


# ---- 33: whitespace normalisation and tag stripping unchanged ----------------------------------------------------------------


def test_33_whitespace_is_collapsed_and_trimmed():
    assert title_of(page(item(title_attr="  A \n\t  B   "))) == "A B"


def test_33_an_entity_encoded_space_is_normalised_like_a_literal_one():
    assert title_of(page(item(title_attr="A&#32;&#32;B"))) == "A B"


def test_33_the_text_title_still_has_its_tags_stripped():
    assert title_of(page(item(text_title="<span>Tagged</span>  Title", title_attr=""))) == "Tagged Title"


# ---- 34: exact-number matching unchanged ----------------------------------------------------------------------------------


def test_34_only_the_exact_number_is_accepted_and_its_own_title_is_used():
    html_text = page(
        item("FC2-1825061", title_attr="Near miss &amp;amp; wrong", href="/v/NEAR1"),
        item(N, title_attr="Exact &amp;amp; right", href="/v/EXACT"),
        item("FC2-4724605", title_attr="Another near miss", href="/v/NEAR2"),
    )
    metadata, failure = parse_javdb_search_page(html_text, N, BASE, SID)
    assert failure is None
    assert metadata.number == N and metadata.title == "Exact &amp; right"
    assert metadata.source_urls == (f"{BASE}/v/EXACT",)


def test_34_near_misses_only_is_still_not_found():
    html_text = page(item("FC2-1825061", title_attr="A &amp; B"), item("FC2-4724605", title_attr="C"))
    metadata, failure = parse_javdb_search_page(html_text, N, BASE, SID)
    assert metadata is None and failure[0] is SourceStatus.NOT_FOUND
