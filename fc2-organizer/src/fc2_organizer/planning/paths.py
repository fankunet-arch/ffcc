"""Centralized, pure path-component safety and containment helpers.

Everything here is a pure function: no filesystem access (no ``exists``,
``stat``, ``mkdir``, ``open``, ...), no network, no randomness, no wall
clock. This is the single, centralized place path-component sanitization
and containment reasoning live (contract section 13: "不要把 sanitization
逻辑散落在多个函数中") -- ``planner.py`` and ``models.py`` both call into this
module rather than duplicating any of this logic.
"""

from __future__ import annotations

import os

from fc2_organizer.planning.errors import UnsafeTargetComponentError

__all__ = [
    "validate_path_component",
    "basenames_collide",
    "is_contained_within",
]

# Windows-illegal characters in a single path component (contract section
# 13). Forward and backward slash are included deliberately: a caller-
# controlled component (an ``OutputPolicy`` artifact filename, in
# particular) must never be able to inject an extra path segment.
_ILLEGAL_CHARS = frozenset('<>:"/\\|?*')

_RESERVED_BASENAMES = frozenset(
    {"CON", "PRN", "AUX", "NUL"}
    | {f"COM{d}" for d in range(1, 10)}
    | {f"LPT{d}" for d in range(1, 10)}
)


def validate_path_component(value: str, *, label: str) -> str:
    """Validate that ``value`` is safe to use as a single Windows path
    component (a directory name or a filename -- never a multi-segment
    path). Returns ``value`` unchanged on success; raises
    ``UnsafeTargetComponentError`` otherwise. Never touches the filesystem.

    Checks (contract section 13):

    - non-empty ``str``
    - not exactly ``"."`` or ``".."``
    - contains no separator (``/`` or ``\\``) -- a component must never
      smuggle in an extra path segment
    - contains no other Windows-illegal character (``< > : " | ? *``) and no
      ASCII control character
    - does not end with a trailing dot or trailing space
    - is not a Windows reserved device name (``CON``, ``PRN``, ``AUX``,
      ``NUL``, ``COM1``..``COM9``, ``LPT1``..``LPT9``), case-insensitively,
      checked against the portion of the name before the *first* dot (so
      ``CON.txt`` is rejected but ``CONFIG.txt`` is not)
    """
    if type(value) is not str or not value:
        raise UnsafeTargetComponentError(f"{label} must be a non-empty str, got {value!r}")

    if value in (".", ".."):
        raise UnsafeTargetComponentError(f"{label} must not be '.' or '..', got {value!r}")

    for ch in value:
        if ch in _ILLEGAL_CHARS or ord(ch) < 0x20:
            raise UnsafeTargetComponentError(
                f"{label} contains a Windows-illegal character {ch!r} in {value!r}"
            )

    if value[-1] in (" ", "."):
        raise UnsafeTargetComponentError(
            f"{label} must not end with a trailing space or dot (Windows-illegal): {value!r}"
        )

    stem = value.split(".", 1)[0]
    if stem.upper() in _RESERVED_BASENAMES:
        raise UnsafeTargetComponentError(
            f"{label} is a Windows reserved device name: {value!r}"
        )

    return value


def basenames_collide(a: str, b: str) -> bool:
    """Would ``a`` and ``b`` collide as sibling filenames on Windows?

    Windows filename comparison is case-insensitive; this uses ``casefold``
    (stronger than ``lower`` for non-ASCII text) rather than assuming the
    two names are pure ASCII.
    """
    return a.casefold() == b.casefold()


def is_contained_within(candidate: str, root: str) -> bool:
    """Is ``candidate`` strictly nested under ``root``, purely lexically?

    This never touches the filesystem (no ``resolve()``/``realpath()``/
    ``exists()``): it compares normalized path segments only, treating
    segment equality case-insensitively (Windows semantics -- the safe
    default regardless of host platform, since a planned library may later
    be read back on Windows). ``candidate == root`` is *not* considered
    contained (a target must be strictly inside the root, never the root
    itself).
    """
    candidate_parts = os.path.normpath(candidate).split(os.sep)
    root_parts = os.path.normpath(root).split(os.sep)

    if len(candidate_parts) <= len(root_parts):
        return False

    prefix = candidate_parts[: len(root_parts)]
    return [p.casefold() for p in prefix] == [p.casefold() for p in root_parts]
