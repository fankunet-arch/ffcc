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
from pathlib import Path

from fc2_organizer.planning.errors import UnsafeTargetComponentError

__all__ = [
    "validate_path_component",
    "basenames_collide",
    "is_contained_within",
    "is_fully_qualified_absolute_root",
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
    ``exists()``): it compares path segments only, treating segment
    equality case-insensitively (Windows semantics -- the safe default
    regardless of host platform, since a planned library may later be read
    back on Windows). ``candidate == root`` is *not* considered contained (a
    target must be strictly inside the root, never the root itself).

    **Two lexical hazards, both handled (P4-C2-GOV-02, then P4-C2-R1-01):**

    1. A bare drive root (``C:\\``) or a UNC share root (``\\\\server\\share\\``)
       normalizes to a string *ending* in the separator. A naive
       ``str.split(os.sep)`` on that string produces a spurious trailing
       empty segment that inflates the root's part count, making an actual
       child (``C:\\FC2-1234567``) wrongly compare as "not contained"
       (GOV-02). Fixed by using ``pathlib.Path(...).parts``, which collapses
       a drive-and-root or a UNC-share-and-root into a single anchor part
       (``('C:\\\\',)`` / ``('\\\\\\\\server\\\\share\\\\',)``) with no such
       artifact.
    2. ``pathlib.PurePath.parts`` alone does **not** collapse ``.``/``..``
       segments -- it is a pure string-splitting operation. Left
       unaddressed, ``is_contained_within(r"C:\\library\\..\\outside\\x",
       r"C:\\library")`` would wrongly return ``True``: the raw segments
       ``('C:\\\\', 'library', '..', 'outside', 'x')`` happen to start with
       the root's segments, even though the path's actual *lexical meaning*
       (what it would resolve to) is ``C:\\outside\\x`` -- outside the root
       entirely (P4-C2-R1-01, the GOV-02 fix's own regression). Fixed by
       running ``os.path.normpath`` on both ``candidate`` and ``root``
       *before* splitting into parts: ``normpath`` collapses ``.``/``..``
       lexically (still zero filesystem access -- pure string
       manipulation, no ``stat``/``exists``/``resolve``) while correctly
       clamping a leading ``..`` at the drive/UNC-share anchor exactly the
       way real Windows path resolution does (verified: ``normpath`` on
       ``\\\\server\\share\\..\\other\\x`` yields
       ``\\\\server\\share\\other\\x`` -- clamped to stay inside the share,
       matching the drive-root precedent already established for this
       project by P4-C1-R2-01/R3's ``GetFullPathNameW`` findings -- never
       ``\\\\server\\other\\x``, which would be a different share
       entirely). Composing both fixes (``normpath`` first, then
       ``Path(...).parts`` on the *normalized* string) inherits neither
       hazard: ``normpath`` never strips a bare root's own trailing
       separator down to something ``Path.parts`` would mis-segment (a bare
       ``C:\\`` normalizes to ``C:\\``, unchanged), and ``Path.parts`` no
       longer has to deal with un-collapsed ``.``/``..`` segments because
       ``normpath`` already removed them.

    This still rejects a same-string-prefix sibling (``C:\\library2`` is not
    "under" ``C:\\library``) since comparison is segment-based, never
    ``str.startswith``.
    """
    candidate_parts = Path(os.path.normpath(candidate)).parts
    root_parts = Path(os.path.normpath(root)).parts

    if len(candidate_parts) <= len(root_parts):
        return False

    prefix = candidate_parts[: len(root_parts)]
    return [p.casefold() for p in prefix] == [p.casefold() for p in root_parts]


def is_fully_qualified_absolute_root(path: str) -> bool:
    """Is ``path`` an unambiguous, fully-qualified absolute root, under the
    **current runtime OS**'s own path semantics (P4-C2-GOV-03)?

    This is the single, centralized library-root qualification boundary --
    ``planner.py`` and ``models.py`` both call into it rather than each
    guessing with a bare ``os.path.isabs()``. It is deliberately stricter
    than ``os.path.isabs()`` on Windows: ``os.path.isabs()``'s treatment of
    a Windows *rooted-but-driveless* path (``\\lib``, ``/lib``) has differed
    across Python versions (it lacks a resolved drive, so it is ambiguous --
    it means "the root of whichever drive is current," which this package
    never guesses). ``library_root`` for P4-C2 v1.0 must be unambiguous:

    * **Windows** (``os.name == "nt"``): accepted only if
      ``os.path.splitdrive`` finds a real drive letter (``C:\\lib``,
      ``C:/lib`` -- accepted only when the tail also has a root, i.e. not
      the drive-relative ``C:lib``) or a UNC share (``\\\\server\\share``,
      ``\\\\server\\share\\lib``, accepted with or without a trailing
      separator, since a bare share is already an unambiguous root).
      Rejected: a plain relative name (``lib``), a dot-relative form
      (``.\\lib``, ``..\\lib``), a drive-relative form (``C:lib``), and a
      rooted-but-driveless form (``\\lib``, ``/lib``).
    * **POSIX** (anything else): an ordinary ``os.path.isabs(path)`` check
      -- POSIX has no drive/UNC ambiguity, so ``/lib`` is already
      unambiguous and must remain legal. This branch is chosen by the
      *current runtime OS*, never by guessing from the string's own shape,
      so a genuine POSIX absolute path is never rejected by a Windows-only
      rule (and vice versa).

    Purely lexical: ``os.path.splitdrive``/``os.path.isabs`` never touch the
    filesystem.
    """
    if os.name != "nt":
        return os.path.isabs(path)

    drive, tail = os.path.splitdrive(path)
    if not drive:
        return False

    is_unc = drive.startswith("\\\\") or drive.startswith("//")
    if tail == "":
        # A bare UNC share ("\\server\share") is itself an unambiguous
        # root; a bare drive letter ("C:") is not -- it means "current
        # directory on that drive," which this package never guesses.
        return is_unc

    return tail[0] in ("\\", "/")
