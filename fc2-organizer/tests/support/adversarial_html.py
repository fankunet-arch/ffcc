"""Adversarial HTML for the three adapter parsers (Phase 3 entry C0-02).

Phase 2 review P2-R-02: the original regex parsers went super-linear on a
broken page -- an unclosed ``<h1>`` followed by whitespace cost 2.9 s
(fc2db_net, 2000 spaces), 63 s (4000 spaces), 7.5 s (av123), 3.7 s (javdb).
A parser is synchronous CPU work inside an async ``fetch``, so a single
corrupt or hostile 5 MiB response must not be able to hold the event loop.

This module is imported by a **child process** (see
``tests/unit/sources/adapters/test_parser_adversarial.py``) so that a
regression shows up as a clean timeout failure instead of hanging the test
run: ``re`` holds the GIL, so an in-process watchdog cannot interrupt it.

Run directly (``python -m adversarial_html``) it prints one JSON line per case.
"""

from __future__ import annotations

import json
import sys
import time

from fc2_metadata_core.sources.adapters.av123 import parse_av123_detail_page
from fc2_metadata_core.sources.adapters.fc2db_net import parse_fc2db_work_page
from fc2_metadata_core.sources.adapters.javdb import parse_javdb_search_page

from support.source_fixtures import load_fixture

# The transport's default response cap (DEFAULT_MAX_RESPONSE_BYTES): the
# largest body a parser can ever be handed in production.
BIG = 5 * 1024 * 1024

PARSERS = {
    "fc2db_net": lambda html: parse_fc2db_work_page(html, "FC2-4824605", "u"),
    "av123": lambda html: parse_av123_detail_page(html, "FC2-4825061", "u"),
    "javdb": lambda html: parse_javdb_search_page(html, "FC2-4825061", "https://javdb.com"),
}

_OPEN_H1 = {
    "fc2db_net": "<h1 class=\"t\">[FC2-PPV-4824605] ",
    "av123": "<h1 class=\"watch__title\">FC2-PPV-4825061 — ",
    "javdb": "<div class=\"movie-list\"><div class=\"item\"><div class=\"video-title\"><strong>FC2-4825061</strong> ",
}
_VALID = {
    "fc2db_net": load_fixture("fc2db_net/work_4824605.html"),
    "av123": load_fixture("av123/detail_4825061.html"),
    "javdb": load_fixture("javdb/search_hit_4825061.html"),
}


def _fill(unit: str, size: int = BIG) -> str:
    return unit * (size // len(unit))


def build_cases() -> list[tuple[str, str, str, str]]:
    """``(parser, case name, html, expectation)``; expectation is ``"fail"``
    (must return a failure status) or ``"any"`` (only the time is judged)."""
    cases: list[tuple[str, str, str, str]] = []
    for parser, opener in _OPEN_H1.items():
        # The exact reviewer reproductions, small enough that the old code took
        # seconds/minutes (not hours) -- these are what catches a regression.
        cases.append((parser, "unclosed relevant tag + 2000 spaces", opener + " " * 2000, "fail"))
        cases.append((parser, "unclosed relevant tag + 4000 spaces", opener + " " * 4000, "fail"))
        # Same shape at the transport's full size cap.
        cases.append((parser, "unclosed relevant tag + 5 MiB spaces", opener + " " * BIG, "fail"))
        cases.append((parser, "unclosed relevant tag + 5 MiB text", opener + _fill("word "), "fail"))
        for junk_name, junk in (
            ("'<h1 ' x N", "<h1 "),
            ("'<a ' x N", "<a "),
            ("'<!--' x N", "<!--"),
            ("'<' x N", "<"),
            ("'class=\"' x N", "class=\""),
            ("'<div class=\"item\">' x N", "<div class=\"item\">"),
            ("'<strong>' x N", "<strong>"),
            ("unbalanced quotes x N", "<a x=\""),
        ):
            cases.append((parser, junk_name, _fill(junk), "fail"))

    # A *valid* page followed by adversarial tails: every later extraction stage
    # (JSON-LD, tag links, info rows, item list) runs on hostile input while the
    # heading is genuine, so the time cost of those stages is exercised too.
    # C0-R1-01 lesson: "each primitive is capped" is not "the parser is bounded".
    # These are the *combinatorial* analogues for the other two parsers -- many
    # opening tags each carrying ~1.4 KB of one-character attribute tokens that
    # spell the markers the parser searches for (measured ~13 ms worst; kept as
    # a guard so a future refactor cannot introduce a marker x tag multiplication).
    soup = ("a " * 30 + "watch__title watch__info-row chip ") * 30
    soup = soup[:1400]
    dense_h1_openers = "".join("<h1 %s>" % soup for _ in range(25))
    dense_rows = "".join("<div %s>" % soup for _ in range(60))
    dense_chips = "".join("<a %s>x</a>" % soup for _ in range(80))
    dense_tag_links = "".join("<a href=\"/work-tags/x\" %s>t</a>" % soup[:300] for _ in range(450))
    tails = {
        "fc2db_net": [
            ("ld+json unclosed + spaces", "<script type=\"application/ld+json\">" + " " * BIG),
            ("ld+json marker spam", _fill("application/ld+json ")),
            ("'/work-tags/' spam", _fill("<a href=\"/work-tags/x\">")),
            ("deeply nested json", "<script type=\"application/ld+json\">" + "[" * 100_000 + "</script>"),
            ("dense-attribute /work-tags/ links x450", dense_tag_links),
            ("dense-attribute <h1> openers x25", dense_h1_openers),
        ],
        "av123": [
            ("'watch__info-row' spam", _fill("<div class=\"watch__info-row\"><dt>")),
            ("unclosed dd + spaces", "<div class=\"watch__info-row\"><dt>Genres</dt><dd>" + " " * BIG),
            ("'chip' spam", "<div class=\"watch__info-row\"><dt>Genres</dt><dd>" + _fill("<a class=\"chip\">")),
            ("dense-attribute row markers x60", dense_rows),
            ("dense-attribute chips x80 in Genres", "<div class=\"watch__info-row\"><dt>Genres</dt><dd>" + dense_chips + "</dd></div>"),
            ("dense-attribute title markers x25", dense_h1_openers.replace("<h1", "<p")),
        ],
        "javdb": [
            ("'video-title' spam", _fill("<div class=\"video-title\"><strong>")),
            ("'item' spam", _fill("<div class=\"item\"><a href=\"/v/a\" title=\"")),
            ("'movie-list' spam", _fill("<div class=\"movie-list\">")),
        ],
    }
    for parser, entries in tails.items():
        for name, tail in entries:
            cases.append((parser, "valid page + " + name, _VALID[parser] + tail, "any"))
    return cases


def main() -> None:
    for parser, name, html, expectation in build_cases():
        started = time.perf_counter()
        metadata, error = PARSERS[parser](html)
        seconds = time.perf_counter() - started
        status = "success" if metadata is not None else error[0].value
        print(
            json.dumps(
                {
                    "parser": parser,
                    "case": name,
                    "expectation": expectation,
                    "chars": len(html),
                    "seconds": round(seconds, 4),
                    "status": status,
                }
            ),
            flush=True,
        )
    sys.stdout.flush()


if __name__ == "__main__":
    main()
