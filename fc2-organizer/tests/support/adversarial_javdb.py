"""Reviewer-shaped adversarial JavDB pages (Phase 3 entry C0 R1, C0-R1-01).

The C0 adversarial suite (``adversarial_html.py``) only had *flat* hostile
inputs (one unclosed tag + filler, marker spam). The independent closure
review found a **combinatorial** shape it did not cover: a JavDB result list
near the item cap where every item's opening tags carry ~1.4 KB of attribute
text that repeatedly spells the class-token markers the parser searches for
(``video-title``, ``meta``, ``item``). The C0 parser located each marker
occurrence separately and re-found / re-parsed the same opening tag every
time, so cost multiplied (items x lookups x marker occurrences x attribute
tokens): reviewer-measured 732 KiB = 1.2 s, 1.5 MiB = 3.8-4.5 s, 1.8 MiB =
~5.5 s, against ~2.8 ms for the real fixture. "Each primitive is capped" is
not "the parser is bounded".

Every case here goes through the real ``parse_javdb_search_page`` (and, for the
headline shape, the real ``JavdbAdapter.fetch`` with a fake HTTP client), never
a single helper. Run in a **child process** by
``tests/unit/sources/adapters/test_javdb_total_cost.py``: ``re`` holds the GIL,
so a complexity regression must be killed from outside, not waited on.

``python -m support.adversarial_javdb`` prints one JSON object per case.
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
from typing import Callable

from fc2_metadata_core.sources.adapters.javdb import JavdbAdapter, parse_javdb_search_page

from support.fake_http_client import FakeHttpClient, make_response
from support.source_fixtures import load_fixture

KIB = 1024
MIB = 1024 * KIB
NUMBER = "FC2-4825061"

# Sizes: the reviewer's ~750 KiB and ~1.5 MiB, then larger representative
# inputs up to the transport's 5 MiB response cap (DEFAULT_MAX_RESPONSE_BYTES).
SIZES = (("750 KiB", 750 * KIB), ("1.5 MiB", 1536 * KIB), ("3 MiB", 3 * MIB), ("5 MiB", 5 * MIB))

# A short run of separate attribute *tokens* that spells the markers the
# parser looks for, padded with 1-character tokens (the densest thing
# ``parse_attrs`` can be fed: ~one Python-level iteration per two characters).
_SOUP_UNIT = "a " * 20 + "meta " + "video-title " + "item "
_TAG_ATTR_CHARS = 1400  # just under the parser's 1500-char opening-tag window


def soup(chars: int = _TAG_ATTR_CHARS, unit: str = _SOUP_UNIT) -> str:
    return (unit * (chars // len(unit) + 1))[:chars]


def _page(items_html: list[str], region: int, tail: str = "") -> str:
    parts = ['<html><body><div class="toolbar"></div><div class="movie-list h cols-4 vcols-8">']
    for one in items_html:
        parts.append(one + " " * max(0, region - len(one)))
    parts.append("</div>" + tail + "</body></html>")
    return "".join(parts)


def _real_title(code: str = "FC2-1111111") -> str:
    return '<div class="video-title"><strong>' + code + "</strong> some title</div>"


def _size_region(total: int, items: int, min_len: int) -> int:
    return max(min_len, (total - 400) // items)


# ---- shapes ------------------------------------------------------------------------------


def reviewer_shaped(total: int, items: int = 200) -> str:
    """The reviewer's shape: 200 items, real ``video-title`` first, ``meta``
    element *absent*, and each item's ``<a>`` opening tag stuffed with marker
    tokens + filler, so the ``meta`` lookup finds ~20 occurrences per item."""
    one = (
        '<div class="item">' + _real_title()
        + '<a href="/v/AAA111" class="box" ' + soup() + ' title="t"></a></div>'
    )
    return _page([one] * items, _size_region(total, items, len(one)))


def stuffed_tags_per_item(total: int, items: int = 200) -> str:
    """Same idea, but the item region is filled with as many dense opening tags
    (non-detail anchors + images) as fit in the parser's per-item window."""
    head = '<div class="item">' + _real_title()
    region = _size_region(total, items, len(head) + 20)
    fits = max(1, min(5, (region - len(head)) // (_TAG_ATTR_CHARS + 40)))
    tags = "".join(
        ('<a href="/x/%d" %s>' % (k, soup())) if k % 2 == 0 else ('<img alt="x" %s>' % soup())
        for k in range(fits)
    )
    return _page([head + tags + "</div>"] * items, region)


def item_marker_tokens(total: int, items: int = 200) -> str:
    """``item`` spelled inside every opening tag (the item-list scan's own marker)."""
    one = (
        '<div class="item"><a href="/v/AAA111" ' + soup(unit="item " + "a " * 30)
        + ">" + _real_title() + "</a></div>"
    )
    return _page([one] * items, _size_region(total, items, len(one)))


def quoted_marker_values(total: int, items: int = 200) -> str:
    """Markers inside one long *quoted* attribute value per item."""
    blob = ("video-title meta item " * 70)[:_TAG_ATTR_CHARS]
    one = (
        '<div class="item">' + _real_title()
        + '<a href="/v/AAA111" class="box" data-x="' + blob + '" title="t"></a></div>'
    )
    return _page([one] * items, _size_region(total, items, len(one)))


def window_filling_max_work(_total: int, items: int = 200) -> str:
    """200 items packed into the parser's whole scan window, each using every
    fixed lookup to the full (3 anchors, 3 images, big title element, meta)."""
    filler = "".join('<i class="c%d"></i>' % k for k in range(14))
    title_inner = "<strong>FC2-1111111</strong> " + "<b>x</b> " * 40
    one = (
        '<div class="item x y">'
        '<div class="video-title">' + title_inner + "</div>"
        + "".join('<a href="/nope/%d" %s>' % (k, soup(320)) for k in range(3))
        + "".join('<img src="data:x" %s>' % soup(200) for _ in range(3))
        + '<div class="meta">not a date</div>' + filler + "</div>"
    )
    return _page([one] * items, len(one))


def class_attribute_spam(total: int, items: int = 0) -> str:
    return '<div class="movie-list">' + ('<i class="x"></i>' * (total // 17))


def valid_exact_hit_then_hostile_tail(total: int, items: int = 0) -> str:
    """A genuine page with the exact hit, followed by hostile filler: the real
    result must still be returned (bounded work must not lose real data)."""
    real = load_fixture("javdb/search_hit_4825061.html")
    return real + reviewer_shaped(total)


# (name, builder, run the real adapter.fetch() path too?, per-case budget seconds, expected status)
_HEADLINE_BUDGET = 0.5    # >= 10x over the fixed parser's worst (~46 ms); the C0 parser needed >= 1.2 s
_C0_BUDGET = 1.0          # the C0 suite's existing per-case budget
Case = tuple[str, Callable[[int], str], bool, float, str]
CASES: list[Case] = [
    ("reviewer-shaped (dense marker tokens, meta absent)", reviewer_shaped, True, _HEADLINE_BUDGET, "any_failure"),
    ("dense tags per item (anchors/imgs)", stuffed_tags_per_item, False, _HEADLINE_BUDGET, "any_failure"),
    ("item marker in every opening tag", item_marker_tokens, False, _HEADLINE_BUDGET, "any_failure"),
    ("markers inside quoted attribute values", quoted_marker_values, False, _C0_BUDGET, "any_failure"),
    ("valid exact hit + hostile tail", valid_exact_hit_then_hostile_tail, False, _C0_BUDGET, "success"),
]
FIXED_SIZE_CASES: list[Case] = [
    ("window-filling max work (200 items)", window_filling_max_work, False, _HEADLINE_BUDGET, "any_failure"),
    ("class-attribute spam (probe exhaustion)", class_attribute_spam, False, _C0_BUDGET, "any_failure"),
]


def _fetch_status(html: str) -> str:
    adapter = JavdbAdapter()
    client = FakeHttpClient()
    url = adapter._lookup_url(NUMBER)
    client.add_response(url, make_response(url=url, text=html))
    result = asyncio.run(adapter.fetch(NUMBER, client))
    return result.status.value


def _emit(**row) -> None:
    print(json.dumps(row), flush=True)


def main() -> None:
    plan: list[tuple[str, str, int, Callable[[int], str], bool, float, str]] = []
    for name, builder, with_fetch, budget, expect in CASES:
        for size_label, total in SIZES:
            plan.append((name, size_label, total, builder, with_fetch, budget, expect))
    for name, builder, with_fetch, budget, expect in FIXED_SIZE_CASES:
        plan.append((name, "fixed", 512 * KIB, builder, with_fetch, budget, expect))

    for name, size_label, total, builder, with_fetch, budget, expect in plan:
        html = builder(total)
        started = time.perf_counter()
        metadata, error = parse_javdb_search_page(html, NUMBER, "https://javdb.com")
        seconds = time.perf_counter() - started
        status = "success" if metadata is not None else error[0].value
        _emit(
            path="parse", case=name, size=size_label, chars=len(html), seconds=round(seconds, 4),
            status=status, budget=budget, expect=expect,
            items=html.count('class="item'), markers=html.count("video-title") + html.count("meta"),
        )
        if with_fetch:
            started = time.perf_counter()
            fetch_status = _fetch_status(html)
            seconds = time.perf_counter() - started
            _emit(
                path="fetch", case=name, size=size_label, chars=len(html), seconds=round(seconds, 4),
                status=fetch_status, budget=budget, expect=expect, items=0, markers=0,
            )
    sys.stdout.flush()


if __name__ == "__main__":
    main()
