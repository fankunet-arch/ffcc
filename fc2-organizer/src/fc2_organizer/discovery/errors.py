"""Error hierarchy for ``fc2_organizer.discovery`` (P4-C1).

This module has no dependency on anything outside the standard library and
must never import ``amane`` or ``fc2_metadata_core``.
"""

from __future__ import annotations

__all__ = [
    "DiscoveryError",
    "DiscoveryContractError",
    "DiscoveryConfigError",
    "DiscoveryInputError",
    "DiscoveryRootError",
    "DiscoveryRootNotFoundError",
    "DiscoveryRootNotADirectoryError",
    "DiscoveryRootAccessError",
]


class DiscoveryError(Exception):
    """Base class for every ``fc2_organizer.discovery`` failure."""


class DiscoveryContractError(DiscoveryError, ValueError):
    """A discovery model (``DiscoveryPolicy`` / ``DiscoveredMediaItem`` /
    ``DiscoveryIssue`` / ``DiscoveryResult``) violates its structural
    contract."""


class DiscoveryConfigError(DiscoveryError, ValueError):
    """``DiscoveryPolicy`` was constructed with an invalid configuration."""


class DiscoveryInputError(DiscoveryError, TypeError):
    """``discover_media`` was called with a malformed ``root`` or ``policy``
    argument (wrong type)."""


class DiscoveryRootError(DiscoveryError):
    """Base class for root-level scan failures.

    A root-level failure (missing root, root is not a directory, root not
    accessible) must never be silently downgraded to an empty
    ``DiscoveryResult`` -- that would look indistinguishable from "root
    exists and legitimately has no media", which is misleading. Every
    subclass below is raised directly by ``discover_media`` instead.
    """


class DiscoveryRootNotFoundError(DiscoveryRootError):
    """The scan root does not exist."""


class DiscoveryRootNotADirectoryError(DiscoveryRootError):
    """The scan root exists but is not a directory."""


class DiscoveryRootAccessError(DiscoveryRootError):
    """The scan root exists but could not be accessed (e.g. permission
    denied, or some other OS-level failure while stat-ing it)."""
