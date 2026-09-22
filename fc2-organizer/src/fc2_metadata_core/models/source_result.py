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
from types import MappingProxyType
from typing import Mapping

from fc2_metadata_core.errors import SourceResultContractError
from fc2_metadata_core.models.metadata import NormalizedMetadata

__all__ = [
    "SourceStatus",
    "SourceErrorKind",
    "SourceResult",
    "ALLOWED_ERROR_KINDS",
    "status_for_error_kind",
]


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
    """Failure category, finer than ``SourceStatus`` (widened at Phase 3 C2).

    Kept as a distinct enum (rather than reusing ``SourceStatus`` directly)
    so that ``SourceResult.error_kind`` has its own type that is meaningless
    for a successful result, and so the failure taxonomy can be refined
    without touching the coarse, aggregate-visible ``SourceStatus``
    vocabulary. **Retry decisions are made from this structured kind, never
    from ``error_detail`` text** (closes Phase 2 review finding P2-R-12).

    The six *generic* members (one per non-success status) are kept unchanged
    for backward compatibility: every ``SourceResult`` built before C2, and any
    adapter that does not refine its failures, still validates; a generic
    ``NETWORK_ERROR`` is treated as a retryable transport failure, the other
    generics are not. The refined members and the ``SourceStatus`` each may
    accompany are frozen in :data:`ALLOWED_ERROR_KINDS`.
    """

    # generic (one per non-success status)
    NOT_FOUND = "not_found"
    BLOCKED = "blocked"
    RATE_LIMITED = "rate_limited"
    NETWORK_ERROR = "network_error"
    PARSE_ERROR = "parse_error"
    INVALID_RESPONSE = "invalid_response"

    # refinements of NETWORK_ERROR (nothing usable was received)
    TIMEOUT = "timeout"
    CONNECTION_ERROR = "connection_error"  # DNS / connect / TLS
    DECODE_ERROR = "decode_error"  # body decode / decompress failure
    REDIRECT_ERROR = "redirect_error"  # redirect chain limit exceeded
    SOURCE_DEADLINE = "source_deadline"  # the per-source wall-clock deadline (aggregation layer)
    CIRCUIT_OPEN = "circuit_open"  # governor rejected lookup without a request

    # refinements of INVALID_RESPONSE (a response arrived but is unusable)
    HTTP_SERVER_ERROR = "http_server_error"  # HTTP 500-599
    RESPONSE_TOO_LARGE = "response_too_large"
    ADAPTER_EXCEPTION = "adapter_exception"  # the adapter itself raised
    RESULT_CONTRACT_MISMATCH = "result_contract_mismatch"  # wrong source_id / number / type


# Which fine-grained kinds may accompany each failure status. Frozen contract
# (docs/specifications/PHASE3_RESILIENCE_CONTRACT.md); a status/kind pairing
# outside this table is rejected by ``SourceResult`` at construction.
ALLOWED_ERROR_KINDS: Mapping[SourceStatus, frozenset[SourceErrorKind]] = MappingProxyType(
    {
        SourceStatus.NOT_FOUND: frozenset({SourceErrorKind.NOT_FOUND}),
        SourceStatus.BLOCKED: frozenset({SourceErrorKind.BLOCKED}),
        SourceStatus.RATE_LIMITED: frozenset({SourceErrorKind.RATE_LIMITED}),
        SourceStatus.NETWORK_ERROR: frozenset(
            {
                SourceErrorKind.NETWORK_ERROR,
                SourceErrorKind.TIMEOUT,
                SourceErrorKind.CONNECTION_ERROR,
                SourceErrorKind.DECODE_ERROR,
                SourceErrorKind.REDIRECT_ERROR,
                SourceErrorKind.SOURCE_DEADLINE,
                SourceErrorKind.CIRCUIT_OPEN,
            }
        ),
        SourceStatus.PARSE_ERROR: frozenset({SourceErrorKind.PARSE_ERROR}),
        SourceStatus.INVALID_RESPONSE: frozenset(
            {
                SourceErrorKind.INVALID_RESPONSE,
                SourceErrorKind.HTTP_SERVER_ERROR,
                SourceErrorKind.RESPONSE_TOO_LARGE,
                SourceErrorKind.ADAPTER_EXCEPTION,
                SourceErrorKind.RESULT_CONTRACT_MISMATCH,
            }
        ),
    }
)

_KIND_TO_STATUS: Mapping[SourceErrorKind, SourceStatus] = MappingProxyType(
    {kind: status for status, kinds in ALLOWED_ERROR_KINDS.items() for kind in kinds}
)


def status_for_error_kind(kind: SourceErrorKind) -> SourceStatus:
    """The one ``SourceStatus`` a given ``SourceErrorKind`` belongs to."""
    return _KIND_TO_STATUS[kind]

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
    - ``metadata`` must be ``None`` or an actual :class:`NormalizedMetadata`
      instance (R1-01/F1: a caller passing e.g. a plain ``int`` or ``dict``
      is rejected here with :class:`SourceResultContractError`, never
      allowed to construct and only fail later with a bare
      ``AttributeError`` from ``metadata.meets_minimum_success()``).
    - ``status == SUCCESS`` requires ``metadata`` to be present and to
      satisfy :meth:`NormalizedMetadata.meets_minimum_success`, and
      requires ``error_kind``/``error_detail`` to both be ``None``.
    - Every non-success status requires ``error_kind`` to be a :class:`SourceErrorKind` member allowed for
      that status (``ALLOWED_ERROR_KINDS``; the generic one always is) and ``error_detail`` to be a
      non-empty string -- callers can never leave the reason blank.
    - ``NOT_FOUND``/``BLOCKED``/``RATE_LIMITED``/``NETWORK_ERROR`` must not
      carry any ``metadata`` (nothing usable was ever extracted).
    - ``PARSE_ERROR``/``INVALID_RESPONSE`` may optionally carry a partial
      ``metadata`` that does *not* meet minimum success (if it did, the
      status should have been ``SUCCESS``).

    Lifetime (R1-02/F2): ``NormalizedMetadata`` is itself a deeply immutable
    value object (see its docstring), and this dataclass is frozen, so once
    a ``SourceResult`` is constructed there is no public API through which
    any of the above invariants can be invalidated later -- not by
    reassigning ``metadata``, not by mutating the referenced metadata's
    scalars, and not by mutating its collection/mapping fields.
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
        if self.metadata is not None and not isinstance(self.metadata, NormalizedMetadata):
            raise SourceResultContractError(
                f"metadata must be a NormalizedMetadata or None, got "
                f"{type(self.metadata)!r}"
            )

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
        allowed = ALLOWED_ERROR_KINDS[self.status]
        if not isinstance(self.error_kind, SourceErrorKind) or self.error_kind not in allowed:
            raise SourceResultContractError(
                f"status={self.status.value} requires error_kind in "
                f"{sorted(kind.value for kind in allowed)}, got {self.error_kind!r}"
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
