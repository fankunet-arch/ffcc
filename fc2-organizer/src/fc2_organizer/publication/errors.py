"""Error hierarchy for ``fc2_organizer.publication`` (P4-C3).

This module has no dependency on anything outside the standard library and
must never import ``amane`` or ``fc2_metadata_core``.

Every distinct publication-failure reason (contract section 9) gets its own
named exception rather than a bare ``ValueError``, so a caller can tell "the
aggregate failed" from "the identities disagree" from "the input is not an
``AggregationResult`` at all" without parsing a message string.

No message raised from this package ever contains ``SourceResult.error_detail``,
an exception object/``args``/traceback, or any HTTP payload: messages are built
only from canonical numbers, enum values and Python type names.
"""

from __future__ import annotations

__all__ = [
    "PublicationError",
    "PublicationInputError",
    "AggregationNotPublishableError",
    "InvalidPublicationMetadataError",
    "PublicationIdentityMismatchError",
    "PublicationContractError",
]


class PublicationError(Exception):
    """Base class for every ``fc2_organizer.publication`` failure."""


class PublicationInputError(PublicationError, TypeError):
    """A ``prepare_publication`` argument has the wrong Python type: ``plan``
    is not an ``OrganizePlan`` or ``aggregation_result`` is not an
    ``AggregationResult``."""


class AggregationNotPublishableError(PublicationError, ValueError):
    """The aggregate status is not publishable. Only ``SUCCESS`` and
    ``PARTIAL`` may be published; ``FAILED`` (or anything that is not an
    ``AggregateStatus`` at all) never forms a publication record."""


class InvalidPublicationMetadataError(PublicationError, ValueError):
    """The aggregate's metadata is missing, not a ``NormalizedMetadata``, or
    does not satisfy ``meets_minimum_success()``."""


class PublicationIdentityMismatchError(PublicationError, ValueError):
    """``plan.canonical_number``, ``aggregation_result.number`` and
    ``aggregation_result.metadata.number`` are not all the same canonical FC2
    number. The boundary never picks a "winner" among them; it fails closed."""


class PublicationContractError(PublicationError, ValueError):
    """A ``PublicationRecord`` (typically hand-constructed) violates its own
    model-level invariants, independent of whether ``prepare_publication``
    produced it."""
