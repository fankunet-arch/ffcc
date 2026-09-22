"""Reparse-point (Windows junction / symlink / other) detection helper.

Isolated in its own module so the scanner's safety decision ("never recurse
into a reparse point") can be unit-tested independently of any real
filesystem symlink/junction, which may not be creatable on every host (real
directory symlinks on Windows require a privilege that is often unavailable
without Developer Mode or elevation; junctions do not need it, see
``docs/specifications/PHASE4_DISCOVERY_CONTRACT.md`` section 6).

``os.DirEntry.is_symlink()`` / ``os.path.islink()`` reliably detect a real
NTFS symlink, but **not** a Windows junction (``IO_REPARSE_TAG_MOUNT_POINT``
carries a different reparse tag than a symlink's
``IO_REPARSE_TAG_SYMLINK``): a junction reports ``is_symlink() == False``
while still being a reparse point that must not be recursed into. This
module closes that gap without depending on ``os.path.isjunction`` (added in
Python 3.12; this project targets 3.11+).
"""

from __future__ import annotations

import os
import stat as stat_module

__all__ = ["is_reparse_point"]


def is_reparse_point(path: str) -> bool:
    """Return ``True`` if ``path`` is a Windows reparse point (junction,
    symlink, or any other reparse tag), determined via ``st_file_attributes``
    rather than the reparse *tag*, so every reparse kind is treated
    conservatively as unsafe to recurse into.

    Always ``False`` on a non-Windows platform (reparse points are an NTFS /
    Windows-specific concept; POSIX symlinks are already caught by
    ``os.DirEntry.is_symlink()`` before this function is consulted).

    Never raises: a path that has vanished or become unreadable between
    enumeration and this check is reported as "not a reparse point" here --
    the caller's own stat step is what surfaces that failure as a
    ``DiscoveryIssue``.
    """
    if os.name != "nt":
        return False
    try:
        st = os.lstat(path)
    except OSError:
        return False
    attributes = getattr(st, "st_file_attributes", None)
    if attributes is None:
        return False
    return bool(attributes & stat_module.FILE_ATTRIBUTE_REPARSE_POINT)
