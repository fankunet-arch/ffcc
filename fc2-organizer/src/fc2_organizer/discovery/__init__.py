"""Phase 4 / P4-C1: safe, read-only, deterministic recursive media discovery.

::

    dirty media root (a directory path)
            |
    discover_media(root, policy=DiscoveryPolicy())
            |   recursive, read-only, deterministic, duplicate-safe,
            |   unsupported-file-safe, symlink/junction-safe
            v
    DiscoveryResult(root, items: tuple[DiscoveredMediaItem, ...], issues: tuple[DiscoveryIssue, ...])

Scope (frozen for this package, see
``docs/specifications/PHASE4_DISCOVERY_CONTRACT.md``): media *discovery*
only. No FC2 number parsing (identity is source path / index, never a
parsed number -- that job belongs to ``fc2_metadata_core.normalize`` and is
out of scope here), no metadata scraping, no NFO/image handling, no
filesystem mutation of any kind, no Amane dependency, no persistence.

Nothing in this package imports ``amane``. This package may depend on
``fc2_metadata_core`` (never the reverse) but currently depends on none of
it -- media identity here is the filesystem path, not a parsed FC2 number.
"""

from fc2_organizer.discovery.errors import (
    DiscoveryConfigError,
    DiscoveryContractError,
    DiscoveryError,
    DiscoveryInputError,
    DiscoveryRootAccessError,
    DiscoveryRootError,
    DiscoveryRootNotADirectoryError,
    DiscoveryRootNotFoundError,
)
from fc2_organizer.discovery.models import (
    DiscoveredMediaItem,
    DiscoveryIssue,
    DiscoveryIssueKind,
    DiscoveryResult,
    DiscoveryStage,
)
from fc2_organizer.discovery.policy import DEFAULT_SUPPORTED_EXTENSIONS, DiscoveryPolicy
from fc2_organizer.discovery.scanner import discover_media

__all__ = [
    "DEFAULT_SUPPORTED_EXTENSIONS",
    "DiscoveredMediaItem",
    "DiscoveryConfigError",
    "DiscoveryContractError",
    "DiscoveryError",
    "DiscoveryInputError",
    "DiscoveryIssue",
    "DiscoveryIssueKind",
    "DiscoveryPolicy",
    "DiscoveryResult",
    "DiscoveryRootAccessError",
    "DiscoveryRootError",
    "DiscoveryRootNotADirectoryError",
    "DiscoveryRootNotFoundError",
    "DiscoveryStage",
    "discover_media",
]
