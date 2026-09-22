"""``PublicationRecord``: the immutable, publication-safe binding of one
``OrganizePlan`` to one aggregate's ``NormalizedMetadata`` (contract section 5-6).

It carries exactly three things -- the validated plan, the validated metadata
and the (publishable) aggregate status -- and nothing else. In particular it
never holds the ``AggregationResult`` itself, any ``SourceResult``,
``SourceExecutionTrace`` or ``SourceAttempt``, any ``error_detail``, exception
or HTTP payload: a later content layer that receives a record must not thereby
gain access to transport / retry diagnostics (contract section 7).

The invariants are enforced here at the model layer, so even a hand-built
record cannot bind metadata to a plan for another film, carry a ``FAILED``
status, or carry metadata that misses the minimum-success rule. ``OrganizePlan``
and ``NormalizedMetadata`` are already deeply immutable contract objects, and
this dataclass is frozen with ``slots``, so the whole record is deeply
immutable. There is deliberately no ``to_dict``/``to_json``/``to_xml``/
``render``/``write``/``save``: this is a value, not a serializer.
"""

from __future__ import annotations

from dataclasses import dataclass

from fc2_metadata_core.aggregation import AggregateStatus
from fc2_metadata_core.models import NormalizedMetadata
from fc2_organizer.planning import OrganizePlan
from fc2_organizer.publication.errors import PublicationContractError

__all__ = ["PUBLISHABLE_STATUSES", "PublicationRecord"]

# SUCCESS: full coverage without operational failure. PARTIAL: minimum-success
# metadata with at least one source operational failure (frozen Phase 3
# aggregation contract). FAILED carries no metadata and is never publishable.
PUBLISHABLE_STATUSES: frozenset[AggregateStatus] = frozenset({AggregateStatus.SUCCESS, AggregateStatus.PARTIAL})


def describe_identity_value(value: object) -> str:
    """Render a value for an error message without running foreign code: an exact
    ``str`` or an ``AggregateStatus`` is shown, anything else only by type name."""
    if type(value) is str:
        return repr(value)
    if type(value) is AggregateStatus:
        return repr(value.value)
    return f"<{type(value).__name__}>"


@dataclass(frozen=True, slots=True)
class PublicationRecord:
    """A validated plan + validated metadata + a publishable aggregate status."""

    plan: OrganizePlan
    metadata: NormalizedMetadata
    aggregate_status: AggregateStatus

    def __post_init__(self) -> None:
        if not isinstance(self.plan, OrganizePlan):
            raise PublicationContractError(
                f"PublicationRecord.plan must be an OrganizePlan, got {type(self.plan).__name__}"
            )
        if not isinstance(self.metadata, NormalizedMetadata):
            raise PublicationContractError(
                f"PublicationRecord.metadata must be a NormalizedMetadata, got {type(self.metadata).__name__}"
            )
        if not isinstance(self.aggregate_status, AggregateStatus) or self.aggregate_status not in PUBLISHABLE_STATUSES:
            raise PublicationContractError(
                "PublicationRecord.aggregate_status must be AggregateStatus.SUCCESS or PARTIAL, "
                f"got {describe_identity_value(self.aggregate_status)}"
            )
        if not self.metadata.meets_minimum_success():
            raise PublicationContractError(
                "PublicationRecord.metadata must meet minimum success (canonical FC2 number + non-empty title)"
            )
        if type(self.metadata.number) is not str or self.plan.canonical_number != self.metadata.number:
            raise PublicationContractError(
                "PublicationRecord.plan.canonical_number must equal metadata.number "
                f"({describe_identity_value(self.plan.canonical_number)} != "
                f"{describe_identity_value(self.metadata.number)})"
            )

    @property
    def number(self) -> str:
        """The one canonical FC2 number this record is bound to."""
        return self.plan.canonical_number
