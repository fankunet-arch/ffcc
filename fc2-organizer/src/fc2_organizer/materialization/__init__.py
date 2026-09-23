"""FC2 Organizer -- atomic artifact materialization (Phase 4 / P4-C6).

Substep 1 provides one low-level primitive: :func:`materialize_atomic_bytes`,
which atomically creates a single file with exact ``bytes`` in an **existing**
directory and never overwrites anything. It knows nothing about organize plans,
NFO text or images, creates no directory and moves no media (those belong to
later P4-C6 substeps and to P4-C7). See
``docs/specifications/PHASE4_ATOMIC_MATERIALIZATION_CONTRACT.md``.

Standard library only. ``fc2_organizer/__init__.py`` does not import this
package; import it explicitly.
"""

from fc2_organizer.materialization.atomic import materialize_atomic_bytes
from fc2_organizer.materialization.errors import (
    ArtifactCleanupError,
    ArtifactPublishError,
    ArtifactWriteError,
    ArtifactWriteStage,
    InvalidTargetPathError,
    MaterializationError,
    MaterializationInputError,
    MaterializationModelError,
    ParentDirectoryError,
    ParentDirectoryMissingError,
    ParentNotDirectoryError,
    ParentRejectionReason,
    TargetExistsError,
    TargetInaccessibleError,
    TargetPathRejectionReason,
    TemporaryCreateError,
)
from fc2_organizer.materialization.models import MaterializedArtifact

__all__ = [
    "materialize_atomic_bytes",
    "MaterializedArtifact",
    "MaterializationError",
    "MaterializationInputError",
    "InvalidTargetPathError",
    "TargetPathRejectionReason",
    "MaterializationModelError",
    "ParentDirectoryError",
    "ParentDirectoryMissingError",
    "ParentNotDirectoryError",
    "ParentRejectionReason",
    "TargetExistsError",
    "TargetInaccessibleError",
    "TemporaryCreateError",
    "ArtifactWriteError",
    "ArtifactWriteStage",
    "ArtifactPublishError",
    "ArtifactCleanupError",
]
