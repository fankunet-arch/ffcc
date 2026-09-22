"""Resource-control error vocabulary (Phase 3 C5)."""

from __future__ import annotations

from fc2_metadata_core.errors import FC2MetadataCoreError

__all__ = ["ResourceControlError", "ResourceControlConfigError"]


class ResourceControlError(FC2MetadataCoreError):
    """The resource-control API was misused (foreign / forged / already-settled ticket, ...)."""


class ResourceControlConfigError(ResourceControlError, ValueError):
    """A host key, limit policy or breaker policy is invalid. Always raised before any network use."""
