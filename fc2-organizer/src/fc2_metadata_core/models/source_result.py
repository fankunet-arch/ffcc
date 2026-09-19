"""SourceResult: the outcome contract for a single source lookup.

Phase 1 freezes this so that later phases (Phase 2 sources, Phase 3
aggregation) can never collapse every kind of failure into a bare
``except Exception: return None``. A caller must always be able to tell
"this FC2 number does not exist on this source" apart from "the network
failed", "we were blocked/rate-limited", or "the response could not be
parsed" -- even though Phase 1 itself performs no network access and only
freezes the contract.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from fc2_metadata_core.errors import SourceResultContractError
from fc2_metadata_core.models.metadata import NormalizedMetadata

__all__ = ["SourceStatus", "SourceErrorKind", "SourceResult"]


class SourceStatus(Enum):
    """Coarse outcome of a single source lookup."""

    SUCCESS = "success"
    NOT_FOUND = "not_found"
    BLOCKED = "blocked"
    RATE_LIMITED = "rate_limited"
    NETWORK_ERROR = "network_error"
    PARSE_ERROR = "parse_error"
    INVALID_RESPONSE = "invalid_response"


class SourceErrorKind(Enum):
    """Failure category. Mirrors every non-success ``SourceStatus``.

    Kept as a distinct enum (rather than reusing ``SourceStatus`` directly)
    so that ``SourceResult.error_kind`` has its own type that is meaningless
    for a successful result, and so a later phase can widen it with more
    granular sub-kinds without touching ``SourceStatus`` itself.
    """

    NOT_FOUND = "not_found"
    BLOCKED = "blocked"
    RATE_LIMITED = "rate_limited"
    NETWORK_ERROR = "network_error"
    PARSE_ERROR = "parse_error"
    INVALID_RESPONSE = "invalid_response"


_STATUS_TO_ERROR_KIND: dict[SourceStatus, SourceErrorKind] = {
    SourceStatus.NOT_FOUND: SourceErrorKind.NOT_FOUND,
    SourceStatus.BLOCKED: SourceErrorKind.BLOCKED,
    SourceStatus.RATE_LIMITED: SourceErrorKind.RATE_LIMITED,
    SourceStatus.NETWORK_ERROR: SourceErrorKind.NETWORK_ERROR,
    SourceStatus.PARSE_ERROR: SourceErrorKind.PARSE_ERROR,
    SourceStatus.INVALID_RESPONSE: SourceErrorKind.INVALID_RESPONSE,
}

# Statuses where the source could not have produced any usable extraction
# at all -- metadata must be absent.
_NO_METADATA_STATUSES = frozenset(
    {
        SourceStatus.NOT_FOUND,
        SourceStatus.BLOCKED,
        SourceStatus.RATE_LIMITED,
        SourceStatus.NETWORK_ERROR,
    }
)

# Statuses where a response was received but couldn't be fully trusted --
# a partial (non-minimum-success) metadata MAY be attached for debugging /
# future partial-credit aggregation, but a *complete* one must not be, since
# that would actually be a success.
_PARTIAL_METADATA_ALLOWED_STATUSES = frozenset(
    {
        SourceStatus.PARSE_ERROR,
        SourceStatus.INVALID_RESPONSE,
    }
)


@dataclass(frozen=True, slots=True)
class SourceResult:
    """Outcome of one source's attempt to resolve one FC2 number.

    Invariants (enforced in ``__post_init__``, all covered by
    ``tests/unit/core/test_source_result.py``):

    - ``source_id`` must be a non-empty (non-whitespace-only) string.
    - ``elapsed_ms`` must not be negative.
    - ``status == SUCCESS`` requires ``metadata`` to be present and to
      satisfy :meth:`NormalizedMetadata.meets_minimum_success`, and
      requires ``error_kind``/``error_detail`` to both be ``None``.
    - Every non-success status requires ``error_kind`` to be the matching
      :class:`SourceErrorKind` member and ``error_detail`` to be a
      non-empty string -- callers can never leave the reason blank.
    - ``NOT_FOUND``/``BLOCKED``/``RATE_LIMITED``/``NETWORK_ERROR`` must not
      carry any ``metadata`` (nothing usable was ever extracted).
    - ``PARSE_ERROR``/``INVALID_RESPONSE`` may optionally carry a partial
      ``metadata`` that does *not* meet minimum success (if it did, the
      status should have been ``SUCCESS``).
    """

    source_id: str
    status: SourceStatus
    metadata: NormalizedMetadata | None
    elapsed_ms: float
    error_kind: SourceErrorKind | None = None
    error_detail: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.source_id, str) or not self.source_id.strip():
            raise SourceResultContractError("source_id must be a non-empty string")
        if not isinstance(self.status, SourceStatus):
            raise SourceResultContractError("status must be a SourceStatus member")
        if isinstance(self.elapsed_ms, bool) or not isinstance(
            self.elapsed_ms, (int, float)
        ):
            raise SourceResultContractError("elapsed_ms must be an int or float")
        if self.elapsed_ms < 0:
            raise SourceResultContractError("elapsed_ms must not be negative")

        if self.status is SourceStatus.SUCCESS:
            self._validate_success()
        else:
            self._validate_failure()

    def _validate_success(self) -> None:
        if self.metadata is None or not self.metadata.meets_minimum_success():
            raise SourceResultContractError(
                "status=success requires metadata that meets minimum success "
                "(canonical FC2 number + non-empty title)"
            )
        if self.error_kind is not None or self.error_detail is not None:
            raise SourceResultContractError(
                "status=success must not carry error_kind/error_detail"
            )

    def _validate_failure(self) -> None:
        expected_kind = _STATUS_TO_ERROR_KIND[self.status]
        if self.error_kind is not expected_kind:
            raise SourceResultContractError(
                f"status={self.status.value} requires "
                f"error_kind={expected_kind.value}, got {self.error_kind!r}"
            )
        if not isinstance(self.error_detail, str) or not self.error_detail.strip():
            raise SourceResultContractError(
                f"status={self.status.value} requires a non-empty error_detail"
            )

        if self.status in _NO_METADATA_STATUSES:
            if self.metadata is not None:
                raise SourceResultContractError(
                    f"status={self.status.value} must not carry metadata"
                )
        elif self.status in _PARTIAL_METADATA_ALLOWED_STATUSES:
            if self.metadata is not None and self.metadata.meets_minimum_success():
                raise SourceResultContractError(
                    f"status={self.status.value} carries metadata that already "
                    "meets minimum success; use status=success instead"
                )
