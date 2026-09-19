"""Unit tests for SourceResult's status/error/metadata invariants.

These pin down the "legal state combinations" the spec requires an explicit,
tested answer for:
- success must have metadata that meets minimum success, and no error info.
- every failure status must carry a matching error_kind and a non-empty
  error_detail.
- NOT_FOUND/BLOCKED/RATE_LIMITED/NETWORK_ERROR must not carry metadata.
- PARSE_ERROR/INVALID_RESPONSE may optionally carry partial (not
  minimum-success) metadata.
- elapsed_ms must not be negative.
- source_id must not be empty/whitespace-only.
"""

from __future__ import annotations

import pytest

from fc2_metadata_core.errors import SourceResultContractError
from fc2_metadata_core.models import (
    NormalizedMetadata,
    SourceErrorKind,
    SourceResult,
    SourceStatus,
)

NO_METADATA_STATUSES = [
    (SourceStatus.NOT_FOUND, SourceErrorKind.NOT_FOUND),
    (SourceStatus.BLOCKED, SourceErrorKind.BLOCKED),
    (SourceStatus.RATE_LIMITED, SourceErrorKind.RATE_LIMITED),
    (SourceStatus.NETWORK_ERROR, SourceErrorKind.NETWORK_ERROR),
]

PARTIAL_ALLOWED_STATUSES = [
    (SourceStatus.PARSE_ERROR, SourceErrorKind.PARSE_ERROR),
    (SourceStatus.INVALID_RESPONSE, SourceErrorKind.INVALID_RESPONSE),
]


def _minimum_metadata() -> NormalizedMetadata:
    return NormalizedMetadata(number="FC2-4825061", title="Example Title")


def _partial_metadata() -> NormalizedMetadata:
    return NormalizedMetadata(title="Only a title, no valid number")


class TestSuccessInvariants:
    def test_success_requires_metadata_meeting_minimum_success(self):
        result = SourceResult(
            source_id="source-a",
            status=SourceStatus.SUCCESS,
            metadata=_minimum_metadata(),
            elapsed_ms=120.0,
        )
        assert result.metadata is not None
        assert result.metadata.meets_minimum_success()
        assert result.error_kind is None
        assert result.error_detail is None

    def test_success_without_metadata_is_rejected(self):
        with pytest.raises(SourceResultContractError):
            SourceResult(
                source_id="source-a",
                status=SourceStatus.SUCCESS,
                metadata=None,
                elapsed_ms=100.0,
            )

    def test_success_with_only_partial_metadata_is_rejected(self):
        with pytest.raises(SourceResultContractError):
            SourceResult(
                source_id="source-a",
                status=SourceStatus.SUCCESS,
                metadata=_partial_metadata(),
                elapsed_ms=100.0,
            )

    def test_success_with_error_kind_is_rejected(self):
        with pytest.raises(SourceResultContractError):
            SourceResult(
                source_id="source-a",
                status=SourceStatus.SUCCESS,
                metadata=_minimum_metadata(),
                elapsed_ms=100.0,
                error_kind=SourceErrorKind.NOT_FOUND,
            )

    def test_success_with_error_detail_is_rejected(self):
        with pytest.raises(SourceResultContractError):
            SourceResult(
                source_id="source-a",
                status=SourceStatus.SUCCESS,
                metadata=_minimum_metadata(),
                elapsed_ms=100.0,
                error_detail="should not be here",
            )


class TestNoMetadataFailureStatuses:
    @pytest.mark.parametrize("status, error_kind", NO_METADATA_STATUSES)
    def test_valid_construction_without_metadata(self, status, error_kind):
        result = SourceResult(
            source_id="source-a",
            status=status,
            metadata=None,
            elapsed_ms=50.0,
            error_kind=error_kind,
            error_detail="deterministic failure detail",
        )
        assert result.metadata is None
        assert result.error_kind is error_kind

    @pytest.mark.parametrize("status, error_kind", NO_METADATA_STATUSES)
    def test_metadata_is_rejected_even_if_partial(self, status, error_kind):
        with pytest.raises(SourceResultContractError):
            SourceResult(
                source_id="source-a",
                status=status,
                metadata=_partial_metadata(),
                elapsed_ms=50.0,
                error_kind=error_kind,
                error_detail="deterministic failure detail",
            )

    @pytest.mark.parametrize("status, error_kind", NO_METADATA_STATUSES)
    def test_metadata_is_rejected_even_if_it_meets_minimum_success(
        self, status, error_kind
    ):
        with pytest.raises(SourceResultContractError):
            SourceResult(
                source_id="source-a",
                status=status,
                metadata=_minimum_metadata(),
                elapsed_ms=50.0,
                error_kind=error_kind,
                error_detail="deterministic failure detail",
            )


class TestPartialMetadataAllowedStatuses:
    @pytest.mark.parametrize("status, error_kind", PARTIAL_ALLOWED_STATUSES)
    def test_no_metadata_is_allowed(self, status, error_kind):
        result = SourceResult(
            source_id="source-a",
            status=status,
            metadata=None,
            elapsed_ms=50.0,
            error_kind=error_kind,
            error_detail="could not parse response body",
        )
        assert result.metadata is None

    @pytest.mark.parametrize("status, error_kind", PARTIAL_ALLOWED_STATUSES)
    def test_partial_non_minimum_success_metadata_is_allowed(self, status, error_kind):
        result = SourceResult(
            source_id="source-a",
            status=status,
            metadata=_partial_metadata(),
            elapsed_ms=50.0,
            error_kind=error_kind,
            error_detail="could not parse response body",
        )
        assert result.metadata is not None
        assert not result.metadata.meets_minimum_success()

    @pytest.mark.parametrize("status, error_kind", PARTIAL_ALLOWED_STATUSES)
    def test_metadata_meeting_minimum_success_is_rejected(self, status, error_kind):
        with pytest.raises(SourceResultContractError):
            SourceResult(
                source_id="source-a",
                status=status,
                metadata=_minimum_metadata(),
                elapsed_ms=50.0,
                error_kind=error_kind,
                error_detail="inconsistent with declared failure",
            )


class TestErrorKindAndDetailConsistency:
    def test_error_kind_must_match_status(self):
        with pytest.raises(SourceResultContractError):
            SourceResult(
                source_id="source-a",
                status=SourceStatus.NOT_FOUND,
                metadata=None,
                elapsed_ms=50.0,
                error_kind=SourceErrorKind.BLOCKED,
                error_detail="mismatched kind",
            )

    def test_missing_error_kind_on_failure_is_rejected(self):
        with pytest.raises(SourceResultContractError):
            SourceResult(
                source_id="source-a",
                status=SourceStatus.NETWORK_ERROR,
                metadata=None,
                elapsed_ms=50.0,
                error_kind=None,
                error_detail="connection reset",
            )

    def test_missing_error_detail_on_failure_is_rejected(self):
        with pytest.raises(SourceResultContractError):
            SourceResult(
                source_id="source-a",
                status=SourceStatus.NETWORK_ERROR,
                metadata=None,
                elapsed_ms=50.0,
                error_kind=SourceErrorKind.NETWORK_ERROR,
                error_detail=None,
            )

    def test_blank_error_detail_on_failure_is_rejected(self):
        with pytest.raises(SourceResultContractError):
            SourceResult(
                source_id="source-a",
                status=SourceStatus.NETWORK_ERROR,
                metadata=None,
                elapsed_ms=50.0,
                error_kind=SourceErrorKind.NETWORK_ERROR,
                error_detail="   ",
            )


class TestElapsedMsInvariant:
    def test_negative_elapsed_ms_is_rejected(self):
        with pytest.raises(SourceResultContractError):
            SourceResult(
                source_id="source-a",
                status=SourceStatus.SUCCESS,
                metadata=_minimum_metadata(),
                elapsed_ms=-1,
            )

    def test_zero_elapsed_ms_is_accepted(self):
        result = SourceResult(
            source_id="source-a",
            status=SourceStatus.SUCCESS,
            metadata=_minimum_metadata(),
            elapsed_ms=0,
        )
        assert result.elapsed_ms == 0

    def test_bool_elapsed_ms_is_rejected(self):
        with pytest.raises(SourceResultContractError):
            SourceResult(
                source_id="source-a",
                status=SourceStatus.SUCCESS,
                metadata=_minimum_metadata(),
                elapsed_ms=True,
            )


class TestSourceIdInvariant:
    def test_empty_source_id_is_rejected(self):
        with pytest.raises(SourceResultContractError):
            SourceResult(
                source_id="",
                status=SourceStatus.SUCCESS,
                metadata=_minimum_metadata(),
                elapsed_ms=10.0,
            )

    def test_whitespace_only_source_id_is_rejected(self):
        with pytest.raises(SourceResultContractError):
            SourceResult(
                source_id="   ",
                status=SourceStatus.SUCCESS,
                metadata=_minimum_metadata(),
                elapsed_ms=10.0,
            )

    def test_non_empty_source_id_is_accepted(self):
        result = SourceResult(
            source_id="fc2-source-example",
            status=SourceStatus.SUCCESS,
            metadata=_minimum_metadata(),
            elapsed_ms=10.0,
        )
        assert result.source_id == "fc2-source-example"


class TestSourceResultIsImmutable:
    def test_fields_cannot_be_reassigned(self):
        result = SourceResult(
            source_id="source-a",
            status=SourceStatus.SUCCESS,
            metadata=_minimum_metadata(),
            elapsed_ms=10.0,
        )
        with pytest.raises(Exception):
            result.status = SourceStatus.NOT_FOUND  # type: ignore[misc]
