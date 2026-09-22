"""Retry policy (Phase 3 C2). Immutable, deterministic, provider-agnostic.

What is retried, and only that
------------------------------
A retry is a **source-local** repeat of ``adapter.fetch`` inside the *same*
execution slot: it never re-runs another source, and only the source's *final*
``SourceResult`` reaches the merge. Whether to retry is decided from the
result's **structured** ``error_kind`` -- never from ``error_detail`` text and
never from a provider name (closes Phase 2 review finding P2-R-12).

Default matrix (frozen in ``docs/specifications/PHASE3_RESILIENCE_CONTRACT.md``)::

    RETRY      TIMEOUT  CONNECTION_ERROR  DECODE_ERROR  HTTP_SERVER_ERROR
               and the generic NETWORK_ERROR (older / unrefined adapters)
    NO RETRY   SUCCESS  NOT_FOUND  BLOCKED  RATE_LIMITED  PARSE_ERROR
               INVALID_RESPONSE (generic)  RESPONSE_TOO_LARGE  REDIRECT_ERROR
               ADAPTER_EXCEPTION  RESULT_CONTRACT_MISMATCH  SOURCE_DEADLINE
               CIRCUIT_OPEN (C5: an open breaker answered; no request was made)

Why the non-retryable ones are not retried: ``NOT_FOUND`` is a coverage gap, not a
failure; ``BLOCKED`` (403 / anti-bot challenge) must never be hit again
automatically; ``RATE_LIMITED`` (429) carries no Retry-After information yet, so an
immediate repeat could make throttling worse; parse/layout and contract failures
are stable (the same page parses the same way); too-large responses and redirect
loops are provider/configuration problems; ``SOURCE_DEADLINE`` means the time
budget is already spent.

A policy may only *narrow* the retryable set (``retryable_error_kinds`` must be a
subset of :data:`RETRY_ELIGIBLE_KINDS`): ``BLOCKED`` and ``RATE_LIMITED`` cannot be
made retryable by configuration in C2.

Backoff
-------
Deterministic, no jitter. The pause before attempt ``n >= 2`` is
``min(max_backoff_seconds, initial_backoff_seconds * backoff_multiplier ** (n - 2))``.
With the default ``max_attempts = 2`` there is at most one pause (1.0 s). The pause
counts against the source's total wall-clock deadline (see ``execution.py``).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from fc2_metadata_core.aggregation.policy import AggregationConfigError
from fc2_metadata_core.models.source_result import SourceErrorKind, SourceResult, SourceStatus

__all__ = [
    "RetryPolicy",
    "RETRY_ELIGIBLE_KINDS",
    "DEFAULT_RETRYABLE_ERROR_KINDS",
    "DEFAULT_MAX_ATTEMPTS",
    "MAX_ATTEMPTS_LIMIT",
]

DEFAULT_MAX_ATTEMPTS = 2
MAX_ATTEMPTS_LIMIT = 5
_MAX_BACKOFF_LIMIT_SECONDS = 600.0

# The only kinds a policy may ever treat as retryable.
RETRY_ELIGIBLE_KINDS: frozenset[SourceErrorKind] = frozenset(
    {
        SourceErrorKind.NETWORK_ERROR,
        SourceErrorKind.TIMEOUT,
        SourceErrorKind.CONNECTION_ERROR,
        SourceErrorKind.DECODE_ERROR,
        SourceErrorKind.HTTP_SERVER_ERROR,
    }
)
DEFAULT_RETRYABLE_ERROR_KINDS: frozenset[SourceErrorKind] = RETRY_ELIGIBLE_KINDS


def _number(label: str, value: object, *, minimum: float, maximum: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise AggregationConfigError(f"RetryPolicy.{label} must be a number, got {type(value).__name__}")
    if not math.isfinite(value) or value < minimum or value > maximum:
        raise AggregationConfigError(
            f"RetryPolicy.{label} must be finite and in [{minimum:g}, {maximum:g}], got {value!r}"
        )
    return float(value)


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    """Immutable retry configuration.

    ``max_attempts`` counts **all** attempts: ``2`` = the first try plus at most one
    retry (default). ``1`` disables retrying. Validation (``AggregationConfigError``):
    ``max_attempts`` an ``int`` (not ``bool``) in ``1..5``; ``initial_backoff_seconds``
    and ``max_backoff_seconds`` finite and ``>= 0`` (``<= 600``);
    ``backoff_multiplier`` finite and ``>= 1``; ``retryable_error_kinds`` a
    ``frozenset`` of :class:`SourceErrorKind` within :data:`RETRY_ELIGIBLE_KINDS`.
    """

    max_attempts: int = DEFAULT_MAX_ATTEMPTS
    initial_backoff_seconds: float = 1.0
    backoff_multiplier: float = 2.0
    max_backoff_seconds: float = 5.0
    retryable_error_kinds: frozenset[SourceErrorKind] = DEFAULT_RETRYABLE_ERROR_KINDS

    def __post_init__(self) -> None:
        if (
            isinstance(self.max_attempts, bool)
            or not isinstance(self.max_attempts, int)
            or not 1 <= self.max_attempts <= MAX_ATTEMPTS_LIMIT
        ):
            raise AggregationConfigError(f"RetryPolicy.max_attempts must be an int in 1..{MAX_ATTEMPTS_LIMIT}")
        _number("initial_backoff_seconds", self.initial_backoff_seconds, minimum=0.0, maximum=_MAX_BACKOFF_LIMIT_SECONDS)
        _number("backoff_multiplier", self.backoff_multiplier, minimum=1.0, maximum=100.0)
        _number("max_backoff_seconds", self.max_backoff_seconds, minimum=0.0, maximum=_MAX_BACKOFF_LIMIT_SECONDS)
        kinds = self.retryable_error_kinds
        if not isinstance(kinds, frozenset) or not all(isinstance(k, SourceErrorKind) for k in kinds):
            raise AggregationConfigError("RetryPolicy.retryable_error_kinds must be a frozenset of SourceErrorKind")
        forbidden = sorted(k.value for k in kinds - RETRY_ELIGIBLE_KINDS)
        if forbidden:
            raise AggregationConfigError(
                f"RetryPolicy.retryable_error_kinds may not include {forbidden!r} "
                f"(allowed: {sorted(k.value for k in RETRY_ELIGIBLE_KINDS)})"
            )

    @classmethod
    def no_retry(cls) -> "RetryPolicy":
        """A policy that makes exactly one attempt."""
        return cls(max_attempts=1)

    def is_retryable(self, result: SourceResult) -> bool:
        """Is this failure of a kind the policy retries? (Ignores the attempt budget.)

        Structured decision only: ``SUCCESS`` is never retried; anything else is
        retried iff its ``error_kind`` is in ``retryable_error_kinds``.
        """
        if result.status is SourceStatus.SUCCESS or result.error_kind is None:
            return False
        return result.error_kind in self.retryable_error_kinds

    def should_retry(self, result: SourceResult, attempts_made: int) -> bool:
        """After ``attempts_made`` attempts ended in ``result``: try again?"""
        return attempts_made < self.max_attempts and self.is_retryable(result)

    def backoff_before_attempt(self, attempt_number: int) -> float:
        """Seconds to pause before ``attempt_number`` (``>= 2``); ``0.0`` for the first."""
        if attempt_number <= 1:
            return 0.0
        delay = self.initial_backoff_seconds * (self.backoff_multiplier ** (attempt_number - 2))
        return min(self.max_backoff_seconds, delay)
