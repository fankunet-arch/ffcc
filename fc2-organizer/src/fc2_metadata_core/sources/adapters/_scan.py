"""Bounded-cost HTML scanning primitives for the concrete adapters.

Why this module exists (Phase 3 entry C0-02, Phase 2 review P2-R-02)
--------------------------------------------------------------------
Phase 2's parsers were built from lazy ``.*?`` regexes with adjacent ``\\s*``
and ``[^>]*`` runs. On a broken page (an unclosed ``<h1>`` followed by
whitespace) those go super-linear: 2000 spaces cost 3-7 s and 4000 cost
~63 s in one adapter. A parser is synchronous CPU work inside an async
``fetch``; Phase 3 will run several sources concurrently, so one corrupt or
hostile response (up to the transport's 5 MiB cap) must never be able to
monopolise the event loop.

The stdlib ``html.parser.HTMLParser`` is *not* the answer: on this project's
Python (3.12.10) it is itself quadratic on trivially small inputs (measured:
``"<!--" * 20_000`` = 3.2 s, ``"<a " * 100_000`` did not finish in 8 s).

Design rules every function here follows, so the *worst case* is bounded by
construction rather than by hoping a page is well-formed:

1. Locate candidates with ``str.find`` on a short, distinctive marker (C
   speed, linear, no backtracking).
2. Cap how many candidates are ever examined (``MAX_ATTEMPTS``).
3. Only ever run a regex on a *window* of at most ``MAX_TAG_CHARS`` /
   caller-supplied ``max_len`` characters, anchored with ``match(text, pos,
   endpos)``, never an unanchored ``search`` over the whole page.
4. Regexes are written without ambiguity (alternatives that start with
   different characters, possessive quantifiers ``*+``), so they cannot
   backtrack super-linearly even inside a window.

Nothing here tries to be a general HTML parser. It reads the handful of
fixed, server-rendered constructs the adopted sources emit, and answers
"not found" for anything else -- which callers turn into ``PARSE_ERROR`` /
``INVALID_RESPONSE``, never into a guessed value. Tag names and the closing
tags searched for are matched **case-sensitively in lowercase**, as the
adopted sources emit them; fixtures pin that.
"""

from __future__ import annotations

import re
from typing import Iterator, NamedTuple

__all__ = [
    "MAX_TAG_CHARS",
    "MAX_ATTEMPTS",
    "OpenTag",
    "parse_attrs",
    "class_tokens",
    "open_tag_at",
    "open_tag_containing",
    "iter_open_tags",
    "iter_class_tags",
    "inner_until",
]

# Longest opening tag (name + attributes) that will be considered. Real tags on
# the adopted sources are a few hundred characters; anything longer is treated
# as "not a tag we understand".
MAX_TAG_CHARS = 1500
# Upper bound on how many marker hits any single scan will examine.
MAX_ATTEMPTS = 2000

_TAG_NAME_RE = re.compile(r"<([A-Za-z][A-Za-z0-9-]*)")
# Attribute text up to the first '>' that is not inside a quoted value. The
# three alternatives start with different characters and the quantifiers are
# possessive (Python >= 3.11, the project minimum), so there is no backtracking.
_OPEN_TAIL_RE = re.compile(r"((?:[^>\"']|\"[^\"]*+\"|'[^']*+')*+)>")
_ATTR_RE = re.compile(
    r"([^\s\"'<>/=]+)(?:\s*+=\s*+(?:\"([^\"]*+)\"|'([^']*+)'|([^\s\"'>]++)))?"
)


class OpenTag(NamedTuple):
    name: str  # lower-cased tag name
    attrs: str  # raw attribute text between the name and '>'
    start: int  # index of '<'
    end: int  # index just after '>'


def parse_attrs(attr_text: str) -> dict[str, str]:
    """Raw (still entity-encoded) attribute values by lower-cased name.

    ``attr_text`` must already be bounded (it comes from :func:`open_tag_at`).
    A duplicate attribute keeps its first value, as browsers do.
    """
    result: dict[str, str] = {}
    for match in _ATTR_RE.finditer(attr_text):
        name = match.group(1).lower()
        if name in result:
            continue
        value = match.group(2)
        if value is None:
            value = match.group(3)
        if value is None:
            value = match.group(4)
        result[name] = value if value is not None else ""
    return result


def class_tokens(attrs: dict[str, str]) -> tuple[str, ...]:
    return tuple(attrs.get("class", "").split())


def open_tag_at(html: str, lt: int) -> OpenTag | None:
    """The opening tag whose ``<`` is at ``lt``, or ``None`` if it is not a
    well-formed opening tag that ends within ``MAX_TAG_CHARS``."""
    name = _TAG_NAME_RE.match(html, lt, min(len(html), lt + 64))
    if name is None:
        return None
    limit = min(len(html), name.end() + MAX_TAG_CHARS)
    tail = _OPEN_TAIL_RE.match(html, name.end(), limit)
    if tail is None:
        return None
    return OpenTag(name.group(1).lower(), tail.group(1), lt, tail.end())


def open_tag_containing(html: str, pos: int) -> OpenTag | None:
    """The opening tag whose attribute text contains index ``pos``, if any."""
    lt = html.rfind("<", max(0, pos - MAX_TAG_CHARS), pos)
    if lt < 0:
        return None
    tag = open_tag_at(html, lt)
    if tag is not None and tag.end > pos:
        return tag
    return None


def iter_open_tags(html: str, name: str, *, start: int = 0, limit: int = 200) -> Iterator[OpenTag]:
    """Opening ``<name ...>`` tags in document order (at most ``limit`` tried)."""
    needle = "<" + name
    pos = start
    attempts = 0
    while attempts < limit:
        i = html.find(needle, pos)
        if i < 0:
            return
        attempts += 1
        pos = i + len(needle)
        follower = html[pos : pos + 1]
        if follower not in (">", "/", " ", "\t", "\n", "\r", "\f"):
            continue  # "<h10", "<header" for name="h1"/"h"...
        tag = open_tag_at(html, i)
        if tag is not None:
            pos = max(pos, tag.end)
            yield tag


def iter_class_tags(
    html: str, token: str, *, start: int = 0, limit: int = MAX_ATTEMPTS
) -> Iterator[OpenTag]:
    """Opening tags whose ``class`` attribute has ``token`` as a whole token.

    Whole-token, so ``class="item is-x"`` and ``class=" item "`` match while
    ``class="navbar-item"`` does not. Candidates are found by locating
    ``token`` itself with ``str.find``; at most ``limit`` occurrences are
    examined.
    """
    pos = start
    attempts = 0
    last_start = -1
    while attempts < limit:
        i = html.find(token, pos)
        if i < 0:
            return
        attempts += 1
        pos = i + len(token)
        tag = open_tag_containing(html, i)
        if tag is None or tag.start == last_start:
            continue
        if token in class_tokens(parse_attrs(tag.attrs)):
            last_start = tag.start
            yield tag


def inner_until(html: str, start: int, closing: str, max_len: int) -> str | None:
    """Text from ``start`` up to the first ``closing`` within ``max_len`` chars.

    ``None`` if the closing marker does not appear inside that window -- an
    unclosed element is "not found", never "everything to end of page".
    """
    end = html.find(closing, start, start + max_len + len(closing))
    if end < 0:
        return None
    return html[start:end]
