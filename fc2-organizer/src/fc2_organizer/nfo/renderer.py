"""``render_movie_nfo``: the P4-C4 pure Kodi Movie NFO renderer (contract section 2-13).

::

    PublicationRecord (P4-C3)
            |
    render_movie_nfo(record)   pure, deterministic, fail closed,
            |                  ZERO filesystem / network / clock / randomness
            v
    str   (XML 1.0 text, "\\n" line endings, exactly one trailing "\\n")

Only ``title``, the canonical number, ``plot``, ``runtime``, ``release``,
``studio``, ``actors`` and ``tags`` are read. Everything else on the metadata
(``publisher``, image URLs, ``source_urls``, ``external_ids``,
``field_sources``) and the record's ``aggregate_status`` are never read, so
they cannot reach the XML.

Every value is validated before any method is called on it: textual values
must be exact ``str`` (``type(v) is str``), so a ``str`` subclass's hooks
(``__str__``, ``strip``, ``translate``, ...) never run. Every text node goes
through the single :func:`_text_element` -> :func:`_escape_text` boundary;
tag names and attributes are module constants, never caller data.
"""

from __future__ import annotations

import re
from datetime import date

from fc2_organizer.nfo.errors import (
    NfoInputError,
    NfoMetadataError,
    NfoReleaseDateError,
    NfoXmlCharacterError,
)
from fc2_organizer.publication import PublicationRecord

__all__ = ["render_movie_nfo"]

XML_DECLARATION = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
_INDENT = "  "

# Anything that is not an XML 1.0 ``Char``:
# #x9 | #xA | #xD | [#x20-#xD7FF] | [#xE000-#xFFFD] | [#x10000-#x10FFFF].
_ILLEGAL_XML_CHAR = re.compile("[^\t\n\r -퟿-�\U00010000-\U0010ffff]")

# ``\r`` is emitted as a character reference: a literal CR would be normalised
# to LF by every conforming parser (XML 1.0 section 2.11) and would also put a
# platform-looking line ending into the output.
_TEXT_ESCAPES = str.maketrans({"&": "&amp;", "<": "&lt;", ">": "&gt;", "\r": "&#13;"})

_RELEASE_SHAPE = re.compile("[0-9]{4}-[0-9]{2}-[0-9]{2}")


def _escape_text(value: str) -> str:
    """The one XML text-node escaping boundary. ``value`` is an exact ``str``
    already checked by :func:`_check_xml_chars`."""
    return value.translate(_TEXT_ESCAPES)


def _text_element(depth: int, tag: str, value: str) -> str:
    """``<tag>escaped value</tag>`` at ``depth``; ``tag`` is always a module constant."""
    return f"{_INDENT * depth}<{tag}>{_escape_text(value)}</{tag}>"


def _check_xml_chars(field: str, value: str) -> str:
    match = _ILLEGAL_XML_CHAR.search(value)
    if match is not None:
        raise NfoXmlCharacterError(
            f"{field} contains U+{ord(match.group()):04X}, which is not a legal XML 1.0 character"
        )
    return value


def _type_name(value: object) -> str:
    return type(value).__name__


def _read(obj: object, name: str, field: str) -> object:
    try:
        return getattr(obj, name)
    except Exception:
        raise NfoMetadataError(f"{field} could not be read from the record") from None


def _exact_str(field: str, value: object) -> str:
    if type(value) is not str:
        raise NfoMetadataError(f"{field} must be an exact str, got {_type_name(value)}")
    return value


def _optional_str(field: str, value: object) -> str | None:
    """``None`` / whitespace-only -> ``None`` (omitted); otherwise an XML-safe exact ``str``."""
    if value is None:
        return None
    text = _exact_str(field, value)
    if text.strip() == "":
        return None
    return _check_xml_chars(field, text)


def _str_items(field: str, value: object) -> list[str]:
    """Non-blank items of an exact ``tuple`` of exact ``str``, in tuple order (no dedupe, no sort)."""
    if type(value) is not tuple:
        raise NfoMetadataError(f"{field} must be an exact tuple, got {_type_name(value)}")
    items: list[str] = []
    for index, item in enumerate(value):
        item_field = f"{field}[{index}]"
        text = _exact_str(item_field, item)  # an item is never None: only blank items are omitted
        if text.strip() != "":
            items.append(_check_xml_chars(item_field, text))
    return items


def _runtime(value: object) -> str | None:
    if value is None:
        return None
    if type(value) is not int:  # excludes bool and every int subclass
        raise NfoMetadataError(f"metadata.runtime must be an exact int or None, got {_type_name(value)}")
    if value < 0:
        raise NfoMetadataError("metadata.runtime must not be negative")
    try:
        return str(value)
    except ValueError:  # beyond the interpreter's int -> str digit limit
        raise NfoMetadataError("metadata.runtime is too large to render") from None


def _release(value: object) -> str | None:
    text = _optional_str("metadata.release", value)
    if text is None:
        return None
    if _RELEASE_SHAPE.fullmatch(text) is None:
        raise NfoReleaseDateError("metadata.release must be an exact YYYY-MM-DD date")
    try:
        date.fromisoformat(text)
    except ValueError:
        raise NfoReleaseDateError("metadata.release is not a real Gregorian calendar date") from None
    return text


def _mandatory_str(field: str, value: object) -> str:
    text = _exact_str(field, value)
    if text.strip() == "":
        raise NfoMetadataError(f"{field} must not be blank")
    return _check_xml_chars(field, text)


def render_movie_nfo(record: PublicationRecord) -> str:
    """Render ``record`` as a Kodi-compatible Movie NFO XML document (a ``str``).

    :raises NfoInputError: ``record`` is not an exact ``PublicationRecord``.
    :raises NfoMetadataError: a used field has an unrenderable shape.
    :raises NfoReleaseDateError: ``release`` is non-blank and not a real ``YYYY-MM-DD`` date.
    :raises NfoXmlCharacterError: a rendered value contains a non-XML-1.0 character.
    """
    # Exact type: a subclass could override ``number`` / ``metadata`` and run code here.
    if type(record) is not PublicationRecord:
        raise NfoInputError(f"record must be a PublicationRecord, got {_type_name(record)}")

    number = _mandatory_str("record.number", _read(record, "number", "record.number"))
    metadata = _read(record, "metadata", "record.metadata")

    title = _mandatory_str("metadata.title", _read(metadata, "title", "metadata.title"))
    plot = _optional_str("metadata.plot", _read(metadata, "plot", "metadata.plot"))
    runtime = _runtime(_read(metadata, "runtime", "metadata.runtime"))
    premiered = _release(_read(metadata, "release", "metadata.release"))
    studio = _optional_str("metadata.studio", _read(metadata, "studio", "metadata.studio"))
    actors = _str_items("metadata.actors", _read(metadata, "actors", "metadata.actors"))
    tags = _str_items("metadata.tags", _read(metadata, "tags", "metadata.tags"))

    lines = [XML_DECLARATION, "<movie>"]
    lines.append(_text_element(1, "title", title))
    lines.append(f'{_INDENT}<uniqueid type="fc2" default="true">{_escape_text(number)}</uniqueid>')
    if plot is not None:
        lines.append(_text_element(1, "plot", plot))
    if runtime is not None:
        lines.append(_text_element(1, "runtime", runtime))
    if premiered is not None:
        lines.append(_text_element(1, "premiered", premiered))
    if studio is not None:
        lines.append(_text_element(1, "studio", studio))
    for order, name in enumerate(actors):
        lines.append(f"{_INDENT}<actor>")
        lines.append(_text_element(2, "name", name))
        lines.append(_text_element(2, "order", str(order)))
        lines.append(f"{_INDENT}</actor>")
    for tag in tags:
        lines.append(_text_element(1, "tag", tag))
    lines.append("</movie>")
    return "\n".join(lines) + "\n"
