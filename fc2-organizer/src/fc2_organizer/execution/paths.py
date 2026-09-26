"""Pure lexical path rules for ``fc2_organizer.execution`` (contract section 26.3).

No filesystem access, no normalisation, no ``abspath`` / ``realpath`` / ``expanduser``,
no cwd. Every function takes an optional ``windows`` flag (default: the runtime OS)
so that both rule sets are testable on any host; production callers never pass it.

The rule set for full paths is at least as strict as P4-C6's private
``_validate_target_path`` (contract section 3: the execution package may not import
that private helper; a test proves P4-C7 rejects everything P4-C6 rejects).
"""

from __future__ import annotations

import ntpath
import os
import posixpath

from fc2_organizer.execution.errors import PathRejectionReason

__all__ = [
    "check_absolute_path",
    "check_created_component",
    "same_entry_name",
    "is_under",
    "path_components",
]

_WINDOWS_ILLEGAL = frozenset('<>:"|?*')
_COMPONENT_ILLEGAL = frozenset('<>:"/\\|?*')
_BASE_RESERVED = frozenset(
    {"CON", "PRN", "AUX", "NUL"} | {f"COM{i}" for i in range(1, 10)} | {f"LPT{i}" for i in range(1, 10)}
)
# Contract section 26.3: extended reserved names, applied to every component P4-C7 creates.
_EXTENDED_RESERVED = _BASE_RESERVED | frozenset(
    {"COM\u00b9", "COM\u00b2", "COM\u00b3", "LPT\u00b9", "LPT\u00b2", "LPT\u00b3", "CONIN$", "CONOUT$"}
)
_DEVICE_PREFIXES = ("\\\\?\\", "\\\\.\\", "//?/", "//./", "\\\\?/", "//?\\", "\\\\./", "//.\\")


def _is_windows(windows: bool | None) -> bool:
    return os.name == "nt" if windows is None else windows


def _windows_component_reason(component: str, reserved: frozenset[str]) -> PathRejectionReason | None:
    if any(ch in _WINDOWS_ILLEGAL or ord(ch) < 32 for ch in component):
        return PathRejectionReason.ILLEGAL_CHARACTER
    if component[-1] in (".", " "):
        return PathRejectionReason.TRAILING_DOT_OR_SPACE
    if component.split(".", 1)[0].upper() in reserved:
        return PathRejectionReason.RESERVED_NAME
    return None


def _backslashed(text: str) -> str:
    return "\\".join(text.split("/"))


def _split_windows(path: str) -> tuple[str, str] | None:
    """Return ``(drive, rest)`` for a drive-letter or a server+share UNC path, else None."""
    drive, rest = ntpath.splitdrive(path)
    if len(drive) == 2 and drive[1] == ":" and drive[0].isascii() and drive[0].isalpha():
        return drive, rest
    if drive[:2] in ("\\\\", "//"):
        parts = [part for chunk in drive[2:].split("/") for part in chunk.split("\\")]
        if len(parts) == 2 and parts[0] and parts[1]:
            return drive, rest
    return None


def path_components(path: str, *, windows: bool | None = None) -> tuple[str, list[str]] | None:
    """Split a lexically absolute path into ``(anchor, non-empty components)``; None if not absolute."""
    if _is_windows(windows):
        split = _split_windows(path)
        if split is None:
            return None
        drive, rest = split
        if rest and rest[0] not in ("\\", "/"):
            return None
        return drive, [c for part in rest.split("\\") for c in part.split("/") if c]
    if not posixpath.isabs(path):
        return None
    return "/", [c for c in path.split("/") if c]


def check_absolute_path(path: str, *, directory_root: bool = False,
                        windows: bool | None = None) -> PathRejectionReason | None:
    """Lexically validate an explicit, fully-qualified path; ``None`` means acceptable.

    ``directory_root=True`` (library root only) additionally accepts a bare drive root
    (``C:\\``), a bare UNC share (``\\\\server\\share``) and a trailing separator.
    A bare ``\\\\server`` without a share is always rejected (P4-C2-R1-02 neutralised).
    """
    if type(path) is not str or not path:
        return PathRejectionReason.EMPTY
    if "\x00" in path:
        return PathRejectionReason.NUL_CHARACTER
    win = _is_windows(windows)
    if win:
        if path.startswith(_DEVICE_PREFIXES):
            return PathRejectionReason.DEVICE_NAMESPACE
        split = _split_windows(path)
        if split is None:
            return PathRejectionReason.NOT_ABSOLUTE
        drive, rest = split
        if rest == "":
            is_unc = drive[:2] in ("\\\\", "//")
            return None if (directory_root and is_unc) else PathRejectionReason.NOT_ABSOLUTE
        if rest[0] not in ("\\", "/"):
            return PathRejectionReason.NOT_ABSOLUTE
        raw = [c for part in rest[1:].split("\\") for c in part.split("/")]
    else:
        if not posixpath.isabs(path):
            return PathRejectionReason.NOT_ABSOLUTE
        raw = path.split("/")[1:]
    if raw and raw[-1] == "":
        if not directory_root:
            return PathRejectionReason.NO_BASENAME
    elif not raw and not directory_root:
        return PathRejectionReason.NO_BASENAME
    for component in raw:
        if not component:
            continue
        if component in (".", ".."):
            return PathRejectionReason.DOT_SEGMENT
        if win:
            reason = _windows_component_reason(component, _BASE_RESERVED)
            if reason is not None:
                return reason
    return None


def check_created_component(name: str) -> PathRejectionReason | None:
    """Validate one component P4-C7 will create, on every platform (contract section 26.3)."""
    if type(name) is not str or not name:
        return PathRejectionReason.EMPTY
    if name in (".", ".."):
        return PathRejectionReason.DOT_SEGMENT
    if any(ch in _COMPONENT_ILLEGAL or ord(ch) < 32 for ch in name):
        return PathRejectionReason.ILLEGAL_CHARACTER
    return _windows_component_reason(name, _EXTENDED_RESERVED)


def same_entry_name(a: str, b: str, *, windows: bool | None = None) -> bool:
    """Would ``a`` and ``b`` name the same entry (Windows: case-insensitive)?"""
    return a.casefold() == b.casefold() if _is_windows(windows) else a == b


def is_under(candidate: str, directory: str, *, windows: bool | None = None) -> bool:
    """Is ``candidate`` strictly below ``directory``, by path segments (never ``startswith``)?"""
    win = _is_windows(windows)
    c = path_components(candidate, windows=win)
    d = path_components(directory, windows=win)
    if c is None or d is None:
        return False
    (c_anchor, c_parts), (d_anchor, d_parts) = c, d
    fold = str.casefold if win else (lambda s: s)
    if fold(_backslashed(c_anchor)) != fold(_backslashed(d_anchor)):
        return False
    if len(c_parts) <= len(d_parts):
        return False
    return [fold(p) for p in c_parts[:len(d_parts)]] == [fold(p) for p in d_parts]
