"""Phase 4 / P4-C4: pure Kodi Movie NFO rendering.

::

    PublicationRecord (P4-C3)
            |
    render_movie_nfo(record)   pure, deterministic, fail closed,
            |                  ZERO filesystem / network / clock / randomness
            v
    str   Kodi-compatible Movie NFO XML text

Scope (frozen, see ``docs/specifications/PHASE4_NFO_RENDERING_CONTRACT.md``):
produces an XML text *value* only. It writes no file, chooses no path, creates
no directory, downloads or selects no image, and never reads diagnostics.

Dependency direction: ``fc2_organizer.nfo -> fc2_organizer.publication``
(public package only) plus the standard library. Nothing in this package
imports ``amane`` or ``fc2_metadata_core``, and nothing below it imports ``nfo``.

Not eagerly imported by ``fc2_organizer/__init__.py`` (that would transitively
load ``fc2_metadata_core`` on a bare ``import fc2_organizer``); import it
explicitly: ``from fc2_organizer.nfo import render_movie_nfo``.
"""

from fc2_organizer.nfo.errors import (
    NfoError,
    NfoInputError,
    NfoMetadataError,
    NfoReleaseDateError,
    NfoXmlCharacterError,
)
from fc2_organizer.nfo.renderer import render_movie_nfo

__all__ = [
    "NfoError",
    "NfoInputError",
    "NfoMetadataError",
    "NfoReleaseDateError",
    "NfoXmlCharacterError",
    "render_movie_nfo",
]
