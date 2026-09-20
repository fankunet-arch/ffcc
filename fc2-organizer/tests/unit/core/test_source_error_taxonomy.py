"""C2 failure taxonomy: SourceStatus stays coarse, SourceErrorKind gets finer.

Closes the classification half of Phase 2 review finding P2-R-12: retry policy needs
to tell a transient server-side failure from a stable semantic one *structurally*.
"""

from __future__ import annotations

import pytest

from fc2_metadata_core.errors import SourceResultContractError
from fc2_metadata_core.models.metadata import NormalizedMetadata
from fc2_metadata_core.models.source_result import (
    ALLOWED_ERROR_KINDS,
    SourceErrorKind,
    SourceResult,
    SourceStatus,
    status_for_error_kind,
)

FAILURE_STATUSES = [s for s in SourceStatus if s is not SourceStatus.SUCCESS]


def build(status, kind, detail="boom"):
    return SourceResult(source_id="s", status=status, metadata=None, elapsed_ms=1.0, error_kind=kind, error_detail=detail)


def test_source_status_vocabulary_is_unchanged_and_coarse():
    assert {s.value for s in SourceStatus} == {
        "success", "not_found", "blocked", "rate_limited", "network_error", "parse_error", "invalid_response",
    }


def test_every_kind_belongs_to_exactly_one_status():
    seen = {}
    for status, kinds in ALLOWED_ERROR_KINDS.items():
        for kind in kinds:
            assert kind not in seen, (kind, status, seen.get(kind))
            seen[kind] = status
    assert set(seen) == set(SourceErrorKind), "a SourceErrorKind is missing from ALLOWED_ERROR_KINDS"
    for kind, status in seen.items():
        assert status_for_error_kind(kind) is status


def test_the_frozen_relation_matches_the_contract_table():
    K = SourceErrorKind
    assert dict(ALLOWED_ERROR_KINDS) == {
        SourceStatus.NOT_FOUND: {K.NOT_FOUND},
        SourceStatus.BLOCKED: {K.BLOCKED},
        SourceStatus.RATE_LIMITED: {K.RATE_LIMITED},
        SourceStatus.NETWORK_ERROR: {K.NETWORK_ERROR, K.TIMEOUT, K.CONNECTION_ERROR, K.DECODE_ERROR, K.REDIRECT_ERROR, K.SOURCE_DEADLINE},
        SourceStatus.PARSE_ERROR: {K.PARSE_ERROR},
        SourceStatus.INVALID_RESPONSE: {K.INVALID_RESPONSE, K.HTTP_SERVER_ERROR, K.RESPONSE_TOO_LARGE, K.ADAPTER_EXCEPTION, K.RESULT_CONTRACT_MISMATCH},
    }


def test_the_required_fine_kinds_exist():
    names = {k.name for k in SourceErrorKind}
    assert {
        "NETWORK_ERROR", "TIMEOUT", "CONNECTION_ERROR", "DECODE_ERROR", "REDIRECT_ERROR", "SOURCE_DEADLINE",
        "INVALID_RESPONSE", "HTTP_SERVER_ERROR", "RESPONSE_TOO_LARGE", "ADAPTER_EXCEPTION", "RESULT_CONTRACT_MISMATCH",
    } <= names


@pytest.mark.parametrize("status", FAILURE_STATUSES, ids=lambda s: s.value)
def test_backward_compatibility_the_generic_kind_is_always_accepted(status):
    result = build(status, SourceErrorKind(status.value))
    assert result.error_kind is SourceErrorKind(status.value)


@pytest.mark.parametrize(
    "status, kind",
    [(status, kind) for status, kinds in ALLOWED_ERROR_KINDS.items() for kind in kinds],
    ids=lambda v: v.value if hasattr(v, "value") else str(v),
)
def test_every_allowed_pairing_constructs(status, kind):
    assert build(status, kind).error_kind is kind


@pytest.mark.parametrize(
    "status, kind",
    [
        (status, kind)
        for status in FAILURE_STATUSES
        for kind in SourceErrorKind
        if kind not in ALLOWED_ERROR_KINDS[status]
    ],
    ids=lambda v: v.value if hasattr(v, "value") else str(v),
)
def test_every_other_pairing_is_rejected(status, kind):
    with pytest.raises(SourceResultContractError):
        build(status, kind)


@pytest.mark.parametrize("kind", [SourceErrorKind.HTTP_SERVER_ERROR, SourceErrorKind.TIMEOUT, SourceErrorKind.SOURCE_DEADLINE])
def test_success_still_rejects_any_error_kind(kind):
    with pytest.raises(SourceResultContractError):
        SourceResult(
            source_id="s", status=SourceStatus.SUCCESS, elapsed_ms=1.0,
            metadata=NormalizedMetadata(number="FC2-1234567", title="t"), error_kind=kind,
        )


@pytest.mark.parametrize("kind", list(SourceErrorKind))
@pytest.mark.parametrize("detail", [None, "", "   ", 5])
def test_the_phase_1_invariant_a_failure_needs_a_non_empty_error_detail_still_holds(kind, detail):
    with pytest.raises(SourceResultContractError):
        build(status_for_error_kind(kind), kind, detail)  # type: ignore[arg-type]


@pytest.mark.parametrize("status", FAILURE_STATUSES, ids=lambda s: s.value)
def test_a_failure_without_an_error_kind_or_with_a_non_enum_kind_is_rejected(status):
    for bad in (None, status.value, 3):
        with pytest.raises(SourceResultContractError):
            build(status, bad)  # type: ignore[arg-type]
