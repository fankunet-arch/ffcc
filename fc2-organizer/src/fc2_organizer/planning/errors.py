"""Error hierarchy for ``fc2_organizer.planning`` (P4-C2).

This module has no dependency on anything outside the standard library and
must never import ``amane`` or ``fc2_metadata_core``.

Every distinct planning-failure reason (contract section 24) gets its own
named exception rather than being collapsed into a bare ``ValueError``, so a
caller (or a test) can distinguish "the canonical number is malformed" from
"the metadata is not plannable" from "the output root is invalid" etc.
without parsing a message string.
"""

from __future__ import annotations

__all__ = [
    "OrganizePlanError",
    "OrganizePlanInputError",
    "InvalidCanonicalNumberError",
    "InvalidLibraryRootError",
    "InvalidMetadataForPlanningError",
    "InvalidOutputPolicyError",
    "UnsafeTargetComponentError",
    "InternalTargetCollisionError",
    "OrganizePlanContractError",
    "TargetEscapesLibraryRootError",
]


class OrganizePlanError(Exception):
    """Base class for every ``fc2_organizer.planning`` failure."""


class OrganizePlanInputError(OrganizePlanError, TypeError):
    """A ``build_organize_plan`` argument has a fundamentally wrong Python
    type: ``media_item`` is not a ``DiscoveredMediaItem``, ``canonical_number``
    is not an exact ``str``, ``metadata`` is not a ``NormalizedMetadata``,
    ``library_root`` is not a ``str``/``os.PathLike``, or ``policy`` is
    neither ``None`` nor an ``OutputPolicy``. Raised before any path
    computation."""


class InvalidCanonicalNumberError(OrganizePlanError, ValueError):
    """``canonical_number`` is a ``str`` but does not satisfy the frozen
    canonical FC2 number boundary (``fc2_metadata_core.normalize.is_valid_fc2_number``).
    Planning never guesses or repairs a dirty number; it fails closed."""


class InvalidLibraryRootError(OrganizePlanError, ValueError):
    """``library_root`` is empty, whitespace-only, or not an absolute path."""


class InvalidMetadataForPlanningError(OrganizePlanError, ValueError):
    """``metadata`` is a ``NormalizedMetadata`` instance but does not satisfy
    ``meets_minimum_success()``. Planning never produces a plan from
    partial/failed metadata (contract section 19)."""


class InvalidOutputPolicyError(OrganizePlanError, ValueError):
    """An ``OutputPolicy`` field is structurally invalid."""


class UnsafeTargetComponentError(OrganizePlanError, ValueError):
    """A generated path component (directory name, media/NFO/artifact
    filename) is unsafe under the frozen Windows path-component boundary
    (illegal character, control character, trailing dot/space, or reserved
    device name) -- see ``fc2_organizer.planning.paths``."""


class InternalTargetCollisionError(OrganizePlanError, ValueError):
    """Two of this plan's own target paths would resolve to the same
    location under Windows case-insensitive filename semantics. Planning
    never silently renames or suffixes to resolve this -- it fails closed
    (contract section 14)."""


class OrganizePlanContractError(OrganizePlanError, ValueError):
    """A hand-constructed planning model (``PlannedPath`` / ``PlannedOperation``
    / ``OrganizePlan``) violates its own structural contract, independent of
    whether ``build_organize_plan`` produced it."""


class TargetEscapesLibraryRootError(OrganizePlanContractError):
    """One of ``OrganizePlan``'s own target paths is not lexically contained
    under its own ``library_root``. This is a redundant, defense-in-depth
    check at the model layer: ``build_organize_plan`` cannot produce such a
    plan by construction (every caller-controlled path component is
    validated to contain no separator/``..`` before being joined), mirroring
    the discovery package's own dual-layer (scanner + model) invariant
    pattern (P4-C1-R-01)."""
