"""Shared builders for the P4-C3 publication tests (fully offline).

Plans are built by the real ``build_organize_plan``; aggregates by the real
``merge_source_results`` together with engine-shaped ``SourceExecutionTrace``s,
so every input a test publishes is one the production pipeline could produce.
Failure results deliberately carry "sensitive-looking" ``error_detail`` text
(``SECRET_MARKER``) so the no-leak tests have something real to not leak.
"""

from __future__ import annotations

from fc2_metadata_core.aggregation import (
    AggregationPolicy,
    AggregationResult,
    SourceAttempt,
    SourceExecutionTrace,
    merge_source_results,
)
from fc2_metadata_core.models import NormalizedMetadata, SourceErrorKind, SourceResult, SourceStatus
from fc2_organizer.discovery import DiscoveredMediaItem
from fc2_organizer.planning import OrganizePlan, build_organize_plan

LIBRARY_ROOT = r"C:\library"
SECRET_MARKER = "cookie=SESSION-SECRET-7f3a; Authorization: Bearer tok-XYZ; <html>body</html>"


def make_plan(number: str, *, index: int = 0) -> OrganizePlan:
    item = DiscoveredMediaItem(
        index=index,
        source_path=rf"C:\downloads\movie{index}.mp4",
        relative_path=f"movie{index}.mp4",
        extension=".mp4",
        size=1000 + index,
    )
    # Planning only validates metadata (minimum success); the title is irrelevant to paths.
    return build_organize_plan(item, number, NormalizedMetadata(number=number, title="planning"), LIBRARY_ROOT)


def success_result(source_id: str, number: str, title: str, **fields) -> SourceResult:
    metadata = NormalizedMetadata(
        number=number, title=title, field_sources={"number": (source_id,), "title": (source_id,)}, **fields
    )
    return SourceResult(source_id=source_id, status=SourceStatus.SUCCESS, metadata=metadata, elapsed_ms=12.5)


def failure_result(source_id: str, status: SourceStatus, kind: SourceErrorKind) -> SourceResult:
    return SourceResult(
        source_id=source_id,
        status=status,
        metadata=None,
        elapsed_ms=0.0,
        error_kind=kind,
        error_detail=f"{source_id}: {SECRET_MARKER}",
    )


def single_attempt_trace(result: SourceResult) -> SourceExecutionTrace:
    attempt = SourceAttempt(1, result.status, result.error_kind, 7.0)
    return SourceExecutionTrace(result.source_id, (attempt,), result, max_attempts=2)


def retried_trace(result: SourceResult) -> SourceExecutionTrace:
    """attempt 1 = TIMEOUT (retry-eligible), attempt 2 = ``result`` (engine shape)."""
    first = SourceAttempt(1, SourceStatus.NETWORK_ERROR, SourceErrorKind.TIMEOUT, 30.0)
    second = SourceAttempt(2, result.status, result.error_kind, 9.0, backoff_before_seconds=1.0)
    return SourceExecutionTrace(result.source_id, (first, second), result, max_attempts=2)


def make_aggregate(
    number: str, *, title: str = "A title", kind: str = "success", **fields
) -> AggregationResult:
    """A real merged aggregate with traces.

    * ``success``: a SUCCESS + a NOT_FOUND source (coverage gap only).
    * ``partial``: a SUCCESS + a BLOCKED source (operational failure).
    * ``partial_retry``: a SUCCESS that needed a retry + a NETWORK_ERROR source that
      retried and failed again + a PARSE_ERROR source.
    * ``failed``: only failures.
    """
    if kind == "success":
        results = (
            success_result("a", number, title, **fields),
            failure_result("b", SourceStatus.NOT_FOUND, SourceErrorKind.NOT_FOUND),
        )
        traces = tuple(single_attempt_trace(r) for r in results)
    elif kind == "partial":
        results = (
            success_result("a", number, title, **fields),
            failure_result("b", SourceStatus.BLOCKED, SourceErrorKind.BLOCKED),
        )
        traces = tuple(single_attempt_trace(r) for r in results)
    elif kind == "partial_retry":
        ok = success_result("a", number, title, **fields)
        net = failure_result("b", SourceStatus.NETWORK_ERROR, SourceErrorKind.CONNECTION_ERROR)
        parse = failure_result("c", SourceStatus.PARSE_ERROR, SourceErrorKind.PARSE_ERROR)
        results = (ok, net, parse)
        traces = (retried_trace(ok), retried_trace(net), single_attempt_trace(parse))
    elif kind == "failed":
        results = (
            failure_result("a", SourceStatus.NETWORK_ERROR, SourceErrorKind.TIMEOUT),
            failure_result("b", SourceStatus.NOT_FOUND, SourceErrorKind.NOT_FOUND),
        )
        traces = tuple(single_attempt_trace(r) for r in results)
    else:  # pragma: no cover - a test bug
        raise AssertionError(kind)
    policy = AggregationPolicy(source_order=tuple(r.source_id for r in results))
    return merge_source_results(number, results, policy, elapsed_ms=42.0, execution_traces=traces)
