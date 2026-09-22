"""``OutputPolicy``: the only caller-configurable knobs for the v1.0 default
organize layout (contract section 6-8).

Directory naming (always the bare canonical FC2 number) and the media/NFO
basenames (always ``<canonical>.<ext>`` / ``<canonical><nfo_extension>``)
are never configurable here -- title never participates in path generation
(contract section 8), and there is no ``follow-title`` / naming-strategy
knob to accidentally enable it. ``OutputPolicy`` only lets a caller rename
the generated *artifact* files (poster/fanart/thumb/NFO extension/
extrafanart directory name). Collision policy (fail closed) and overwrite
policy (never) are frozen constants, not knobs, and are not represented as
fields here (contract section 14-15).
"""

from __future__ import annotations

from dataclasses import dataclass

from fc2_organizer.planning.errors import InvalidOutputPolicyError

__all__ = [
    "OutputPolicy",
    "DEFAULT_NFO_EXTENSION",
    "DEFAULT_POSTER_FILENAME",
    "DEFAULT_FANART_FILENAME",
    "DEFAULT_THUMB_FILENAME",
    "DEFAULT_EXTRAFANART_DIRNAME",
]

DEFAULT_NFO_EXTENSION = ".nfo"
DEFAULT_POSTER_FILENAME = "poster.jpg"
DEFAULT_FANART_FILENAME = "fanart.jpg"
DEFAULT_THUMB_FILENAME = "thumb.jpg"
DEFAULT_EXTRAFANART_DIRNAME = "extrafanart"

_STR_FIELDS = (
    "nfo_extension",
    "poster_filename",
    "fanart_filename",
    "thumb_filename",
    "extrafanart_dirname",
)


@dataclass(frozen=True, slots=True)
class OutputPolicy:
    """Immutable artifact-naming policy. ``OutputPolicy()`` (all defaults)
    reproduces the frozen v1.0 default layout (contract section 7) exactly.

    Field-level shape is validated here (non-empty ``str``, ``nfo_extension``
    dot-prefixed); Windows path-component safety (illegal characters,
    reserved names, trailing dot/space) is validated once, centrally, when
    these values are turned into actual path components by
    ``fc2_organizer.planning.planner.build_organize_plan`` -- not duplicated
    here (contract section 13).
    """

    nfo_extension: str = DEFAULT_NFO_EXTENSION
    poster_filename: str = DEFAULT_POSTER_FILENAME
    fanart_filename: str = DEFAULT_FANART_FILENAME
    thumb_filename: str = DEFAULT_THUMB_FILENAME
    extrafanart_dirname: str = DEFAULT_EXTRAFANART_DIRNAME

    def __post_init__(self) -> None:
        for name in _STR_FIELDS:
            value = getattr(self, name)
            if type(value) is not str or not value:
                raise InvalidOutputPolicyError(
                    f"OutputPolicy.{name} must be a non-empty str, got {value!r}"
                )

        if not self.nfo_extension.startswith("."):
            raise InvalidOutputPolicyError(
                f"OutputPolicy.nfo_extension must start with '.', got {self.nfo_extension!r}"
            )
