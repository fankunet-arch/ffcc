"""P4-C9 contract sections 9.12.2 / 12.4 / 18: ``TimingPolicy`` semantics (OMIT / INCLUDE, truncation, ranges,
what is and is not published). Value-by-value boundaries are the frozen table of ``test_diagnostics_numeric_totality``."""

from __future__ import annotations

import pytest
from fc2_metadata_core.models import SourceErrorKind as E, SourceStatus as T
from fc2_organizer.diagnostics import (
    MAX_TIMING_MS,
    DiagnosticsInputError,
    TimingPolicy,
    build_execution_diagnostics,
    build_preview_diagnostics,
)

from . import _builders as b


def preview(elapsed=7.0, attempt_elapsed=20.0, backoff=0.5):
    good = b.make_source_result("src_a", T.SUCCESS, elapsed_ms=987.0)
    bad = b.make_source_result("src_b", T.NETWORK_ERROR)
    attempts = (b.make_attempt_in(1, T.NETWORK_ERROR, kind=E.TIMEOUT, elapsed=attempt_elapsed),
                b.make_attempt_in(2, T.NETWORK_ERROR, kind=E.TIMEOUT, elapsed=attempt_elapsed + 5, backoff=backoff))
    aggregation = b.make_aggregation([good, bad], traces=(b.make_trace(good), b.make_trace(bad, attempts)),
                                     elapsed=555.0)
    return b.preview_of_metadata(b.batch_item_for(aggregation, elapsed_ms=elapsed))


def timings(diag):
    metadata = diag.items[0].metadata
    attempts = [a for s in metadata.sources for a in s.attempts]
    return metadata.elapsed_ms, [(a.elapsed_ms, a.backoff_before_ms) for a in attempts]


def test_the_default_policy_is_omit_and_publishes_no_timing_at_all():
    diag = build_preview_diagnostics(preview())
    assert diag.timing_policy is TimingPolicy.OMIT
    assert timings(diag) == (None, [(None, None)] * 3)


def test_include_publishes_integer_milliseconds_for_item_and_attempts():
    diag = build_preview_diagnostics(preview(), timing_policy=TimingPolicy.INCLUDE)
    assert diag.timing_policy is TimingPolicy.INCLUDE
    elapsed, attempts = timings(diag)
    assert elapsed == 7 and attempts == [(5, 0), (20, 0), (25, 500)]
    assert all(type(v) is int for pair in attempts for v in pair) and type(elapsed) is int


@pytest.mark.parametrize(("value", "published"), [(0.0, 0), (0.9, 0), (1.0, 1), (7.99, 7), (1500.7, 1500)])
def test_float_milliseconds_are_truncated_toward_zero(value, published):
    diag = build_preview_diagnostics(preview(elapsed=value), timing_policy=TimingPolicy.INCLUDE)
    assert timings(diag)[0] == published


@pytest.mark.parametrize(("seconds", "published"), [(0.0, 0), (0.0004, 0), (0.001, 1), (0.25, 250), (2, 2000)])
def test_backoff_seconds_become_truncated_milliseconds(seconds, published):
    diag = build_preview_diagnostics(preview(backoff=seconds), timing_policy=TimingPolicy.INCLUDE)
    assert timings(diag)[1][2][1] == published


def test_published_values_stay_within_the_documented_range():
    diag = build_preview_diagnostics(preview(elapsed=float(MAX_TIMING_MS), attempt_elapsed=0.0, backoff=604800),
                                     timing_policy=TimingPolicy.INCLUDE)
    elapsed, attempts = timings(diag)
    assert elapsed == MAX_TIMING_MS and all(0 <= v <= MAX_TIMING_MS for pair in attempts for v in pair)


def test_adapter_self_reported_and_aggregation_durations_are_never_published():
    diag = build_preview_diagnostics(preview(), timing_policy=TimingPolicy.INCLUDE)
    assert "987" not in repr(diag) and "555" not in repr(diag)


@pytest.mark.parametrize("bad", [None, "include", 1, True, object()])
def test_the_timing_policy_must_be_an_exact_enum(bad):
    with pytest.raises(DiagnosticsInputError):
        build_preview_diagnostics(preview(), timing_policy=bad)
    lineage = b.Lineage(1)
    from fc2_organizer.orchestration import ExecutionDisposition as D
    from fc2_organizer.execution import ExecutionStatus
    result = lineage.result([lineage.execution_item(0, D.EXECUTED, status=ExecutionStatus.SUCCESS)])
    with pytest.raises(DiagnosticsInputError):
        build_execution_diagnostics(result, timing_policy=bad)


def test_include_over_an_input_without_traces_publishes_only_the_item_elapsed():
    lineage = b.Lineage(1)
    diag = build_preview_diagnostics(lineage.preview([lineage.preview_item(0)]), timing_policy=TimingPolicy.INCLUDE)
    metadata = diag.items[0].metadata
    assert type(metadata.elapsed_ms) is int
    assert all(s.attempts == () for s in metadata.sources)
