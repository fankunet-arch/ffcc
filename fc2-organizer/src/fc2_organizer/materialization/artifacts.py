"""Single-artifact materializer (P4-C6 substep 2).

``materialize_artifact(request)`` writes exactly one :class:`ArtifactWriteRequest`
through the frozen substep-1 primitive and does nothing else: no directory
creation, no media move, no plan execution, no multi-artifact transaction or
rollback. One call = one artifact. Standard library only.
"""

from __future__ import annotations

from fc2_organizer.materialization.atomic import materialize_atomic_bytes
from fc2_organizer.materialization.errors import MaterializationInputError
from fc2_organizer.materialization.models import ArtifactWriteRequest, MaterializedArtifact

__all__ = ["materialize_artifact"]


def materialize_artifact(request: ArtifactWriteRequest) -> MaterializedArtifact:
    """Atomically create ``request.target_path`` with ``request.content``; never overwrite.

    Every failure is the substep-1 primitive's own typed error, unchanged.
    """
    if type(request) is not ArtifactWriteRequest:
        raise MaterializationInputError("request must be an exact ArtifactWriteRequest")
    return materialize_atomic_bytes(request.target_path, request.content)
