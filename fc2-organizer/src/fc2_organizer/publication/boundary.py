"""``prepare_publication``: the P4-C3 publication boundary (contract section 4-10).

::

    OrganizePlan + AggregationResult
            |
    prepare_publication(...)   pure, deterministic, fail closed,
            |                  ZERO filesystem access, ZERO network
            v
    PublicationRecord(plan, metadata, aggregate_status)

Checks, in order (the first failing one raises; nothing is repaired, guessed or
chosen on the caller's behalf):

1. input types (``PublicationInputError``);
2. aggregate status is ``SUCCESS`` or ``PARTIAL`` (``AggregationNotPublishableError``);
3. metadata is a ``NormalizedMetadata`` meeting minimum success
   (``InvalidPublicationMetadataError``) -- via ``meets_minimum_success()``, never a
   second success rule;
4. identity: ``plan.canonical_number == aggregation_result.number ==
   aggregation_result.metadata.number`` (``PublicationIdentityMismatchError``).

``AggregationResult`` already enforces ``metadata.number == number`` itself; this
boundary re-checks every identity it relies on anyway, so an ``AggregationResult``
whose own invariants were bypassed still cannot be published against the wrong plan.
Only the plan, the metadata and the status cross into the record: the
``AggregationResult``, its ``SourceResult``s and its traces stay behind.
"""

from __future__ import annotations

from fc2_metadata_core.aggregation import AggregateStatus, AggregationResult
from fc2_metadata_core.models import NormalizedMetadata
from fc2_organizer.planning import OrganizePlan
from fc2_organizer.publication.errors import (
    AggregationNotPublishableError,
    InvalidPublicationMetadataError,
    PublicationIdentityMismatchError,
    PublicationInputError,
)
from fc2_organizer.publication.models import PUBLISHABLE_STATUSES, PublicationRecord, describe_identity_value

__all__ = ["prepare_publication"]


def prepare_publication(plan: OrganizePlan, aggregation_result: AggregationResult) -> PublicationRecord:
    """Bind ``aggregation_result``'s metadata to ``plan``, or fail closed.

    :raises PublicationInputError: ``plan`` is not an ``OrganizePlan`` or
        ``aggregation_result`` is not an ``AggregationResult``.
    :raises AggregationNotPublishableError: the aggregate status is not
        ``SUCCESS``/``PARTIAL`` (``FAILED`` is never publishable).
    :raises InvalidPublicationMetadataError: the aggregate's metadata is missing
        or does not meet minimum success.
    :raises PublicationIdentityMismatchError: the plan's, the aggregate's and the
        metadata's canonical numbers are not all equal.
    """
    if not isinstance(plan, OrganizePlan):
        raise PublicationInputError(f"plan must be an OrganizePlan, got {type(plan).__name__}")
    if not isinstance(aggregation_result, AggregationResult):
        raise PublicationInputError(
            f"aggregation_result must be an AggregationResult, got {type(aggregation_result).__name__}"
        )

    status = aggregation_result.status
    if not isinstance(status, AggregateStatus) or status not in PUBLISHABLE_STATUSES:
        raise AggregationNotPublishableError(
            f"aggregate status {describe_identity_value(status)} is not publishable "
            "(only success / partial)"
        )

    metadata = aggregation_result.metadata
    if not isinstance(metadata, NormalizedMetadata):
        raise InvalidPublicationMetadataError(
            f"aggregate metadata must be a NormalizedMetadata, got {type(metadata).__name__}"
        )
    if not metadata.meets_minimum_success():
        raise InvalidPublicationMetadataError(
            "aggregate metadata does not meet minimum success (canonical FC2 number + non-empty title)"
        )

    plan_number = plan.canonical_number
    identities = (plan_number, aggregation_result.number, metadata.number)
    # Exact ``str`` only: a ``str`` subclass could override ``__eq__`` and fake agreement.
    if not all(type(value) is str for value in identities) or len(set(identities)) != 1:
        raise PublicationIdentityMismatchError(
            "publication identity mismatch: "
            f"plan.canonical_number={describe_identity_value(plan_number)}, "
            f"aggregation_result.number={describe_identity_value(aggregation_result.number)}, "
            f"metadata.number={describe_identity_value(metadata.number)}"
        )

    return PublicationRecord(plan=plan, metadata=metadata, aggregate_status=status)
