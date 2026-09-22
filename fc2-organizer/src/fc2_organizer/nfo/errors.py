"""Error hierarchy for ``fc2_organizer.nfo`` (P4-C4).

This module has no dependency on anything outside the standard library and
must never import ``amane``, ``fc2_metadata_core`` or ``fc2_organizer.publication``.

Every distinct rendering-failure reason (contract section 12) gets its own
named exception, so a caller can tell "the input is not a
``PublicationRecord``" from "a field has an unrenderable shape" from "the
release date is not a real ``YYYY-MM-DD`` date" from "a value contains a
character XML 1.0 cannot carry" without parsing a message string.

Messages are built only from field names, Python type names and code points
(``U+0000``). They never contain a title, plot, actor, tag, studio or release
value, and no NFO error is chained to another exception.
"""

from __future__ import annotations

__all__ = [
    "NfoError",
    "NfoInputError",
    "NfoMetadataError",
    "NfoReleaseDateError",
    "NfoXmlCharacterError",
]


class NfoError(Exception):
    """Base class for every ``fc2_organizer.nfo`` failure."""


class NfoInputError(NfoError, TypeError):
    """``render_movie_nfo`` was not given an exact ``PublicationRecord``."""


class NfoMetadataError(NfoError, ValueError):
    """A field the renderer uses has a shape it cannot render: wrong type
    (including any ``str``/``int`` subclass), negative runtime, missing
    attribute on a forged record, or a blank mandatory title / number."""


class NfoReleaseDateError(NfoMetadataError):
    """``metadata.release`` is non-blank but not an exact ASCII ``YYYY-MM-DD``
    real Gregorian calendar date."""


class NfoXmlCharacterError(NfoMetadataError):
    """A value that would be rendered contains a character that is not a legal
    XML 1.0 ``Char`` (e.g. ``U+0000``, ``U+000B``, a surrogate, ``U+FFFE``)."""
