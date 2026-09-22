"""Phase 4 / P4-C2: immutable, pure Organize Plan.

::

    DiscoveredMediaItem (P4-C1)
    + canonical FC2 number
    + NormalizedMetadata (fc2_metadata_core)
    + library_root
    + OutputPolicy (optional)
            |
    build_organize_plan(...)
            |   pure, deterministic, side-effect-free, ZERO FILESYSTEM MUTATION
            v
    OrganizePlan(source identity, canonical number, target paths, planned operations)

Scope (frozen for this package, see
``docs/specifications/PHASE4_ORGANIZE_PLAN_CONTRACT.md``): answers "if
organizing were executed, what target paths and operations would result?"
It never executes anything: no ``mkdir``/rename/move/copy/delete, no NFO
write, no image download, no network request, no persistence.

Nothing in this package imports ``amane``. This package may depend on
``fc2_metadata_core`` and on ``fc2_organizer.discovery``'s public API
(never the reverse, never discovery's internals).
"""

from fc2_organizer.planning.errors import (
    InternalTargetCollisionError,
    InvalidCanonicalNumberError,
    InvalidLibraryRootError,
    InvalidMetadataForPlanningError,
    InvalidOutputPolicyError,
    OrganizePlanContractError,
    OrganizePlanError,
    OrganizePlanInputError,
    TargetEscapesLibraryRootError,
    UnsafeTargetComponentError,
)
from fc2_organizer.planning.models import (
    OrganizePlan,
    PlannedOperation,
    PlannedOperationKind,
    PlannedPath,
)
from fc2_organizer.planning.planner import build_organize_plan
from fc2_organizer.planning.policy import OutputPolicy

__all__ = [
    "OrganizePlan",
    "OrganizePlanContractError",
    "OrganizePlanError",
    "OrganizePlanInputError",
    "OutputPolicy",
    "PlannedOperation",
    "PlannedOperationKind",
    "PlannedPath",
    "InternalTargetCollisionError",
    "InvalidCanonicalNumberError",
    "InvalidLibraryRootError",
    "InvalidMetadataForPlanningError",
    "InvalidOutputPolicyError",
    "TargetEscapesLibraryRootError",
    "UnsafeTargetComponentError",
    "build_organize_plan",
]
