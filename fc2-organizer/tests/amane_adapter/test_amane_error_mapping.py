"""P5-C1 表 G（E14）：Core 失败 -> Amane ``FailureReason`` 字符串、7 级优先级、``detail`` 封闭词汇。"""

from __future__ import annotations

import ast
import dataclasses
import itertools
from pathlib import Path

import pytest

from fc2_amane_adapter import _outcome
from fc2_amane_adapter._outcome import (
    DETAIL_PREFIX,
    FAILURE_REASONS,
    KIND_TO_REASON,
    AdapterFailure,
    AdapterNoMatch,
    build_detail,
    map_aggregation,
    pick_reason,
    reason_for_kind,
)
from fc2_metadata_core.aggregation import AggregateStatus, AggregationResult
from fc2_metadata_core.models import SourceErrorKind, SourceResult, SourceStatus
from fc2_metadata_core.models.source_result import status_for_error_kind

N = "FC2-4979299"
OUTCOME_SOURCE = Path(_outcome.__file__)

#: 作者写下的合同 17.1 表（不从实现读取）。
EXPECTED = {
    SourceErrorKind.BLOCKED: "http_error",
    SourceErrorKind.RATE_LIMITED: "rate_limited",
    SourceErrorKind.TIMEOUT: "timeout",
    SourceErrorKind.SOURCE_DEADLINE: "timeout",
    SourceErrorKind.CONNECTION_ERROR: "network",
    SourceErrorKind.NETWORK_ERROR: "network",
    SourceErrorKind.DECODE_ERROR: "network",
    SourceErrorKind.REDIRECT_ERROR: "network",
    SourceErrorKind.CIRCUIT_OPEN: "network",
    SourceErrorKind.PARSE_ERROR: "parse_error",
    SourceErrorKind.INVALID_RESPONSE: "parse_error",
    SourceErrorKind.RESPONSE_TOO_LARGE: "parse_error",
    SourceErrorKind.HTTP_SERVER_ERROR: "server_error",
    SourceErrorKind.ADAPTER_EXCEPTION: "unexpected",
    SourceErrorKind.RESULT_CONTRACT_MISMATCH: "unexpected",
}


def _failed(source_id: str, kind: SourceErrorKind, detail: str = "d") -> SourceResult:
    return SourceResult(source_id, status_for_error_kind(kind), None, 1.0, kind, detail)


def _aggregate(*results: SourceResult) -> AggregationResult:
    return AggregationResult(
        number=N, status=AggregateStatus.FAILED, metadata=None, source_results=tuple(results)
    )


def test_every_source_error_kind_has_an_explicit_disposition():
    """枚举完备（M-15）：除 NOT_FOUND 外的每个 kind 都在表里；表里没有多余项。"""
    assert set(KIND_TO_REASON) | {SourceErrorKind.NOT_FOUND} == set(SourceErrorKind)
    assert SourceErrorKind.NOT_FOUND not in KIND_TO_REASON
    assert dict(KIND_TO_REASON) == EXPECTED


@pytest.mark.parametrize("kind", [k for k in SourceErrorKind if k is not SourceErrorKind.NOT_FOUND], ids=lambda k: k.name)
def test_each_kind_maps_through_the_whole_aggregation_boundary(kind):
    outcome = map_aggregation(_aggregate(_failed("javdb", kind)), N)
    assert outcome == AdapterFailure(EXPECTED[kind], f"{DETAIL_PREFIX}javdb={kind.value}")
    assert reason_for_kind(kind) == EXPECTED[kind]


@pytest.mark.parametrize("unknown", [object(), "network_error", None, 7, SourceStatus.BLOCKED])
def test_unknown_kinds_default_to_unexpected(unknown):
    assert reason_for_kind(unknown) == "unexpected"


def test_reasons_used_are_the_seven_frozen_values_all_present_in_both_hosts():
    assert FAILURE_REASONS == ("http_error", "rate_limited", "parse_error", "server_error", "timeout", "network", "unexpected")
    assert set(EXPECTED.values()) <= set(FAILURE_REASONS)
    assert not set(FAILURE_REASONS) & {"cloudflare_challenge", "cloudflare_blocked", "ip_banned", "geo_restricted", "age_verification"}


def test_pick_reason_follows_the_frozen_priority_for_every_subset_and_order():
    for size in range(1, len(FAILURE_REASONS) + 1):
        for subset in itertools.combinations(FAILURE_REASONS, size):
            expected = subset[0]  # 子集按优先级顺序给出，第一个即最高
            for permutation in itertools.permutations(subset):
                assert pick_reason(permutation) == expected
    assert pick_reason(("network", "network", "timeout")) == "timeout"
    assert pick_reason(()) == "unexpected"


@pytest.mark.parametrize(
    ("kinds", "expected"),
    [
        ((SourceErrorKind.BLOCKED, SourceErrorKind.CONNECTION_ERROR), "http_error"),
        ((SourceErrorKind.RATE_LIMITED, SourceErrorKind.PARSE_ERROR), "rate_limited"),
        ((SourceErrorKind.NOT_FOUND, SourceErrorKind.CONNECTION_ERROR), "network"),
        ((SourceErrorKind.BLOCKED, SourceErrorKind.BLOCKED, SourceErrorKind.BLOCKED), "http_error"),
        ((SourceErrorKind.TIMEOUT, SourceErrorKind.HTTP_SERVER_ERROR), "server_error"),
        ((SourceErrorKind.PARSE_ERROR, SourceErrorKind.HTTP_SERVER_ERROR, SourceErrorKind.TIMEOUT), "parse_error"),
        ((SourceErrorKind.ADAPTER_EXCEPTION, SourceErrorKind.CONNECTION_ERROR), "network"),
        ((SourceErrorKind.ADAPTER_EXCEPTION, SourceErrorKind.NOT_FOUND), "unexpected"),
    ],
)
def test_precedence_is_independent_of_source_order(kinds, expected):
    ids = ("fc2db_net", "javdb", "av123")[: len(kinds)]
    for permutation in itertools.permutations(range(len(kinds))):
        results = [_failed(ids[position], kinds[index]) for position, index in enumerate(permutation)]
        outcome = map_aggregation(_aggregate(*results), N)
        assert isinstance(outcome, AdapterFailure)
        assert outcome.reason == expected


def test_all_not_found_is_no_match_and_a_mix_is_a_failure():
    nf = [_failed(sid, SourceErrorKind.NOT_FOUND) for sid in ("fc2db_net", "javdb", "av123")]
    assert map_aggregation(_aggregate(*nf), N) == AdapterNoMatch("all_not_found")
    mixed = map_aggregation(_aggregate(nf[0], _failed("javdb", SourceErrorKind.TIMEOUT), nf[2]), N)
    assert mixed == AdapterFailure("timeout", f"{DETAIL_PREFIX}fc2db_net=not_found; javdb=timeout; av123=not_found")


def test_detail_lists_every_participating_source_in_configuration_order():
    results = (
        _failed("av123", SourceErrorKind.BLOCKED),
        _failed("fc2db_net", SourceErrorKind.NOT_FOUND),
        _failed("javdb", SourceErrorKind.PARSE_ERROR),
    )
    assert build_detail(results) == "FC2 lookup failed: av123=blocked; fc2db_net=not_found; javdb=parse_error"


def test_detail_never_contains_error_detail_urls_or_secrets_and_is_bounded():
    hostile = "SECRET-TOKEN https://evil.example/path?key=1 <html>BODY</html> C:\\Users\\me\\file"
    results = tuple(_failed(sid, SourceErrorKind.CONNECTION_ERROR, hostile) for sid in ("fc2db_net", "javdb", "av123"))
    outcome = map_aggregation(_aggregate(*results), N)
    assert isinstance(outcome, AdapterFailure)
    for needle in ("SECRET", "http", "BODY", "Users", "evil"):
        assert needle not in outcome.detail
    assert len(outcome.detail) <= len(DETAIL_PREFIX) + 3 * 40
    assert set(ch for ch in outcome.detail if not ch.isalnum()) <= set(" :;=_")


def test_amane_error_carries_neither_url_nor_http_status_by_construction():
    assert [f.name for f in dataclasses.fields(AdapterFailure)] == ["reason", "detail"]


def test_classification_reads_only_structured_fields_never_error_detail_text():
    tree = ast.parse(OUTCOME_SOURCE.read_text(encoding="utf-8"))
    attributes = {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
    assert "error_detail" not in attributes
    assert not attributes & {"message", "args", "__cause__", "__str__"}


def test_failure_reason_values_are_validated_closed_vocabulary():
    with pytest.raises(ValueError):
        AdapterFailure("cloudflare_challenge", "x")
    with pytest.raises(ValueError):
        AdapterNoMatch("whatever")
