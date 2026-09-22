"""Phase 4 / P4-C3: the metadata publication boundary.

::

    OrganizePlan (P4-C2)  +  AggregationResult (fc2_metadata_core, Phase 3)
            |
    prepare_publication(plan, aggregation_result)
            |   identity-correlated, fail closed, deterministic,
            |   ZERO filesystem access, ZERO network
            v
    PublicationRecord(plan, metadata, aggregate_status)   deeply immutable

Scope (frozen, see ``docs/specifications/PHASE4_PUBLICATION_BOUNDARY_CONTRACT.md``):
answers "may this aggregated metadata be bound to this plan and handed to a
later content-rendering layer?". It renders nothing: no NFO, no XML/JSON, no
image, no filesystem materialization, no diagnostics export.

Nothing in this package imports ``amane``. It may depend on
``fc2_organizer.planning``'s public API and on ``fc2_metadata_core``'s public
``aggregation`` / ``models`` packages -- never on source adapters, the HTTP
transport, resource control or batch internals (never the reverse either).

Like ``planning``, this package is **not** eagerly imported by
``fc2_organizer/__init__.py`` (that would transitively load
``fc2_metadata_core`` on a bare ``import fc2_organizer``); import it explicitly:
``from fc2_organizer.publication import prepare_publication``.
"""

from fc2_organizer.publication.boundary import prepare_publication
from fc2_organizer.publication.errors import (
    AggregationNotPublishableError,
    InvalidPublicationMetadataError,
    PublicationContractError,
    PublicationError,
    PublicationIdentityMismatchError,
    PublicationInputError,
)
from fc2_organizer.publication.models import PUBLISHABLE_STATUSES, PublicationRecord

__all__ = [
    "PUBLISHABLE_STATUSES",
    "AggregationNotPublishableError",
    "InvalidPublicationMetadataError",
    "PublicationContractError",
    "PublicationError",
    "PublicationIdentityMismatchError",
    "PublicationInputError",
    "PublicationRecord",
    "prepare_publication",
]
