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


class TestMetadataTypeGuard:
    """R1-01 / F1 (SourceResult side): a caller passing a non-NormalizedMetadata
    value for `metadata` must be rejected at the SourceResult contract
    boundary, never allowed through to fail later with a bare AttributeError
    from `metadata.meets_minimum_success()`."""

    def test_original_f1_reproduction_int_metadata_is_rejected(self):
        """The exact reviewer reproduction for the SourceResult side."""
        with pytest.raises(SourceResultContractError):
            SourceResult(
                source_id="x",
                status=SourceStatus.SUCCESS,
                metadata=123,  # type: ignore[arg-type]
                elapsed_ms=1,
            )

    def test_dict_metadata_is_rejected(self):
        with pytest.raises(SourceResultContractError):
            SourceResult(
                source_id="x",
                status=SourceStatus.SUCCESS,
                metadata={"number": "FC2-1234567", "title": "T"},  # type: ignore[arg-type]
                elapsed_ms=1,
            )

    def test_wrong_type_metadata_is_rejected_even_for_failure_statuses(self):
        with pytest.raises(SourceResultContractError):
            SourceResult(
                source_id="x",
                status=SourceStatus.PARSE_ERROR,
                metadata="not a NormalizedMetadata",  # type: ignore[arg-type]
                elapsed_ms=1,
                error_kind=SourceErrorKind.PARSE_ERROR,
                error_detail="could not parse",
            )

    def test_none_metadata_is_still_accepted_where_status_allows_it(self):
        result = SourceResult(
            source_id="x",
            status=SourceStatus.NOT_FOUND,
            metadata=None,
            elapsed_ms=1,
            error_kind=SourceErrorKind.NOT_FOUND,
            error_detail="no such number on this source",
        )
        assert result.metadata is None


class TestSuccessLifetimeInvariant:
    """R1-02 / F2: once a SUCCESS SourceResult is constructed, no public API
    can make `result.metadata.meets_minimum_success()` become False later.

    NormalizedMetadata is now a deeply immutable value object, so every
    mutation attempt below must itself fail (not silently succeed) --
    which is exactly what keeps the SourceResult invariant intact for the
    object's entire lifetime, not just at __post_init__ time."""

    def _success_result(self) -> SourceResult:
        md = _minimum_metadata()
        return SourceResult(
            source_id="source-a",
            status=SourceStatus.SUCCESS,
            metadata=md,
            elapsed_ms=10.0,
        )

    def test_scalar_mutation_attempt_fails_and_invariant_survives(self):
        result = self._success_result()
        with pytest.raises(Exception):
            result.metadata.title = ""  # type: ignore[misc]
        assert result.metadata.meets_minimum_success() is True

    def test_sequence_mutation_attempt_fails_and_invariant_survives(self):
        md = NormalizedMetadata(
            number="FC2-4825061", title="Example Title", actors=["A"]
        )
        result = SourceResult(
            source_id="source-a",
            status=SourceStatus.SUCCESS,
            metadata=md,
            elapsed_ms=10.0,
        )
        with pytest.raises(AttributeError):
            result.metadata.actors.append("B")  # type: ignore[attr-defined]
        assert result.metadata.meets_minimum_success() is True
        assert result.metadata.actors == ("A",)

    def test_mapping_mutation_attempt_fails_and_invariant_survives(self):
        md = NormalizedMetadata(
            number="FC2-4825061",
            title="Example Title",
            external_ids={"source-a": "ext-1"},
        )
        result = SourceResult(
            source_id="source-a",
            status=SourceStatus.SUCCESS,
            metadata=md,
            elapsed_ms=10.0,
        )
        with pytest.raises(TypeError):
            result.metadata.external_ids["source-b"] = "ext-2"  # type: ignore[index]
        assert result.metadata.meets_minimum_success() is True
        assert dict(result.metadata.external_ids) == {"source-a": "ext-1"}

    def test_nested_field_sources_mutation_attempt_fails_and_invariant_survives(self):
        md = NormalizedMetadata(
            number="FC2-4825061",
            title="Example Title",
            field_sources={"title": ["source-a"]},
        )
        result = SourceResult(
            source_id="source-a",
            status=SourceStatus.SUCCESS,
            metadata=md,
            elapsed_ms=10.0,
        )
        with pytest.raises(AttributeError):
            result.metadata.field_sources["title"].append("source-z")  # type: ignore[attr-defined]
        assert result.metadata.meets_minimum_success() is True
        assert result.metadata.field_sources["title"] == ("source-a",)

    def test_result_metadata_attribute_itself_cannot_be_reassigned(self):
        result = self._success_result()
        other = NormalizedMetadata(title="not minimum success on its own")
        with pytest.raises(Exception):
            result.metadata = other  # type: ignore[misc]
        assert result.metadata.meets_minimum_success() is True


class TestPartialFailureLifetimeInvariant:
    """R1-02 / F2: a PARSE_ERROR/INVALID_RESPONSE SourceResult carrying
    partial (non-minimum-success) metadata must never be mutable into a
    metadata that meets minimum success after the fact."""

    @pytest.mark.parametrize("status, error_kind", PARTIAL_ALLOWED_STATUSES)
    def test_partial_metadata_cannot_be_mutated_into_minimum_success(
        self, status, error_kind
    ):
        md = NormalizedMetadata(title="Only a title, no valid number")
        result = SourceResult(
            source_id="source-a",
            status=status,
            metadata=md,
            elapsed_ms=10.0,
            error_kind=error_kind,
            error_detail="could not fully parse response",
        )
        assert result.metadata.meets_minimum_success() is False

        with pytest.raises(Exception):
            result.metadata.number = "FC2-4825061"  # type: ignore[misc]

        assert result.metadata.meets_minimum_success() is False


class TestCallerOwnedAliasSafetyThroughSourceResult:
    """R1-02 / F2: mutating the caller's own input containers, or the
    NormalizedMetadata instance directly, after it has already been used
    to build a SourceResult, must never reach the constructed result."""

    def test_mutating_original_metadata_instance_reference_cannot_succeed(self):
        md = _minimum_metadata()
        result = SourceResult(
            source_id="source-a",
            status=SourceStatus.SUCCESS,
            metadata=md,
            elapsed_ms=10.0,
        )
        assert result.metadata is md

        with pytest.raises(Exception):
            md.title = ""  # type: ignore[misc]

        assert result.metadata.meets_minimum_success() is True

    def test_caller_owned_list_mutation_after_source_result_construction_is_isolated(
        self,
    ):
        actors = ["A"]
        md = NormalizedMetadata(
            number="FC2-4825061", title="Example Title", actors=actors
        )
        result = SourceResult(
            source_id="source-a",
            status=SourceStatus.SUCCESS,
            metadata=md,
            elapsed_ms=10.0,
        )
        actors.append("B")
        assert result.metadata.actors == ("A",)
