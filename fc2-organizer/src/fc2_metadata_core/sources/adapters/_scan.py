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

Per-primitive caps are **not** a total bound (C0-R1-01)
-------------------------------------------------------
Rules 1-4 bound each *call*. They do not bound a parser that makes many calls:
the first C0 JavDB parser located each of ``item`` / ``video-title`` / ``meta``
by marker occurrence and, for every occurrence, re-found and re-parsed the
same (up to 1.5 KB) opening tag. Attribute tokens x marker occurrences x items
multiplied into seconds on a page well under the 5 MiB transport cap. So a
fifth rule applies to any parser built from these primitives:

5. Work must be **shared, not repeated**: collect what you need in one pass
   (:func:`collect_class_hits`), then give each *structural element* a fixed
   number of bounded lookups (:func:`first_open_tag`,
   :func:`open_tag_containing`, :func:`inner_until`) -- never a per-marker-
   occurrence re-scan of the same tag -- and cap the attributes parsed per tag
   (``parse_attrs(max_attrs=...)``). The total is then
   ``passes x cap + elements x constant``, with every factor a named constant.

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
    "first_open_tag",
    "ClassHit",
    "collect_class_hits",
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
_TAG_FOLLOWERS = (">", "/", " ", "\t", "\n", "\r", "\f")


class OpenTag(NamedTuple):
    name: str  # lower-cased tag name
    attrs: str  # raw attribute text between the name and '>'
    start: int  # index of '<'
    end: int  # index just after '>'


def parse_attrs(attr_text: str, *, max_attrs: int | None = None) -> dict[str, str]:
    """Raw (still entity-encoded) attribute values by lower-cased name.

    ``attr_text`` must already be bounded (it comes from :func:`open_tag_at`).
    A duplicate attribute keeps its first value, as browsers do. ``max_attrs``
    stops after that many attribute tokens: real tags carry a handful, while a
    hostile tag can spell hundreds of one-character "attributes", and this
    loop is the Python-level (slow) part of a scan -- callers that parse many
    tags pass a small cap so the per-tag cost has a hard ceiling.
    """
    result: dict[str, str] = {}
    for seen, match in enumerate(_ATTR_RE.finditer(attr_text)):
        if max_attrs is not None and seen >= max_attrs:
            break
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
        if html[pos : pos + 1] not in _TAG_FOLLOWERS:
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

    Each examined occurrence re-locates and re-parses its enclosing tag, so a
    caller that uses this **repeatedly** (per item of a long list) multiplies
    its cost -- use it only for a small, fixed number of lookups per page, and
    use :func:`collect_class_hits` for list-shaped pages (C0-R1-01).
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


def first_open_tag(
    html: str, name: str, *, start: int, end: int, attempts: int = 3
) -> OpenTag | None:
    """The first ``<name ...>`` opening tag in ``html[start:end]``.

    At most ``attempts`` candidates are examined (each is one bounded window),
    so the cost is a small constant however many look-alikes the page holds.
    """
    needle = "<" + name
    pos = start
    for _ in range(attempts):
        i = html.find(needle, pos, end)
        if i < 0:
            return None
        pos = i + len(needle)
        if html[pos : pos + 1] not in _TAG_FOLLOWERS:
            continue
        tag = open_tag_at(html, i)
        if tag is not None:
            return tag
    return None


class ClassHit(NamedTuple):
    pos: int  # index of the word "class" in the attribute
    tokens: frozenset[str]  # the *wanted* class tokens that attribute carries


_CLASS_VALUE_RE = re.compile(r"\s*+=\s*+(?:\"([^\"]{0,400})\"|'([^']{0,400})')")
_CLASS_PRECEDERS = frozenset(" \t\r\n\f\"'")
_CLASS_VALUE_WINDOW = 460


def collect_class_hits(
    html: str, wanted: frozenset[str], *, max_chars: int, max_probes: int
) -> tuple[list[ClassHit], bool]:
    """Every quoted ``class="..."`` attribute that carries a ``wanted`` token,
    found in **one** pass over ``html[:max_chars]``.

    Returns ``(hits, truncated)``. ``hits`` are in document order. ``truncated``
    is true if the pass stopped early (more than ``max_probes`` occurrences of
    the word ``class``) or the page continues past ``max_chars`` with more
    ``class`` occurrences -- i.e. the caller has not seen the whole page and
    must not conclude "absent" from these hits alone.

    Why one pass: the first C0 scans re-located a marker inside the same
    (possibly 1.5 KB) opening tag once per marker occurrence and re-parsed the
    tag every time (C0-R1-01), so cost multiplied. Here each occurrence costs
    one anchored, bounded regex match and nothing is re-scanned; total work is
    at most ``max_probes`` small matches plus one ``str.find`` sweep. Matching
    is by whole token, so ``class="navbar-item"`` never satisfies ``item``.
    Unquoted ``class=item`` and an upper-case ``CLASS`` attribute name are not
    recognised (the adopted sources emit lower-case, always-quoted ``class``).
    """
    end = min(len(html), max_chars)
    hits: list[ClassHit] = []
    pos = 0
    probes = 0
    exhausted = False
    while True:
        i = html.find("class", pos, end)
        if i < 0:
            break
        if probes >= max_probes:
            exhausted = True
            break
        probes += 1
        pos = i + 5
        if i and html[i - 1] not in _CLASS_PRECEDERS:
            continue  # "data-class", "subclass", ...
        match = _CLASS_VALUE_RE.match(html, pos, min(len(html), pos + _CLASS_VALUE_WINDOW))
        if match is None:
            continue
        value = match.group(1) if match.group(1) is not None else match.group(2)
        found = wanted.intersection(value.split())
        if found:
            hits.append(ClassHit(i, frozenset(found)))
    truncated = exhausted or (len(html) > end and html.find("class", end) >= 0)
    return hits, truncated
