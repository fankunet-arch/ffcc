"""P4-C9 contract sections 11.5 - 11.7 / 12.2 / 12.4 (source-level log): every source status and refined error
kind, retried sources, CIRCUIT_OPEN, deadlines during an attempt / a backoff, runs without traces, disabled
sources, conflicts and the safe-id / structural-limit rules."""

from __future__ import annotations

import pytest
from fc2_metadata_core.aggregation import AggregateStatus, FieldConflict
from fc2_metadata_core.batch import BatchItemStatus
from fc2_metadata_core.models import SourceErrorKind as E, SourceStatus as T
from fc2_organizer.diagnostics import (
    DiagnosticsResourceLimitError,
    DiagnosticsUnsafeValueError,
    TimingPolicy,
    build_preview_diagnostics,
)

from . import _builders as b


def sources_of(*results, traces=(), **kwargs):
    preview = b.preview_of_metadata(b.batch_item_for(b.make_aggregation(results, traces=traces, **kwargs)))
    return build_preview_diagnostics(preview).items[0].metadata


def ok(source_id="src_a", **kwargs):
    return b.make_source_result(source_id, T.SUCCESS, **kwargs)


def failing(source_id, status, kind=None):
    return b.make_source_result(source_id, status, error_kind=kind)


_FAILURES = [
    (T.NOT_FOUND, E.NOT_FOUND, False), (T.BLOCKED, E.BLOCKED, True), (T.RATE_LIMITED, E.RATE_LIMITED, True),
    (T.NETWORK_ERROR, E.NETWORK_ERROR, True), (T.PARSE_ERROR, E.PARSE_ERROR, True),
    (T.INVALID_RESPONSE, E.INVALID_RESPONSE, True),
]


@pytest.mark.parametrize(("status", "kind", "operational"), _FAILURES)
def test_every_source_status_is_projected_with_its_operational_flag(status, kind, operational):
    metadata = sources_of(ok(), failing("src_b", status, kind))
    good, bad = metadata.sources
    assert good.status is T.SUCCESS and good.error_kind is None and good.contributed is True
    assert good.operational_failure is False
    assert bad.status is status and bad.error_kind is kind and bad.contributed is False
    assert bad.operational_failure is operational and bad.provided_fields == ()
    assert metadata.aggregate_status is (AggregateStatus.PARTIAL if operational else AggregateStatus.SUCCESS)
    assert metadata.status is (BatchItemStatus.PARTIAL if operational else BatchItemStatus.SUCCESS)


_REFINED = [
    (T.NETWORK_ERROR, E.TIMEOUT), (T.NETWORK_ERROR, E.CONNECTION_ERROR), (T.NETWORK_ERROR, E.DECODE_ERROR),
    (T.NETWORK_ERROR, E.REDIRECT_ERROR), (T.NETWORK_ERROR, E.SOURCE_DEADLINE), (T.NETWORK_ERROR, E.CIRCUIT_OPEN),
    (T.INVALID_RESPONSE, E.HTTP_SERVER_ERROR), (T.INVALID_RESPONSE, E.RESPONSE_TOO_LARGE),
    (T.INVALID_RESPONSE, E.ADAPTER_EXCEPTION), (T.INVALID_RESPONSE, E.RESULT_CONTRACT_MISMATCH),
]


@pytest.mark.parametrize(("status", "kind"), _REFINED)
def test_refined_source_error_kinds_are_carried_unchanged(status, kind):
    metadata = sources_of(ok(), failing("src_b", status, kind))
    assert metadata.sources[1].status is status and metadata.sources[1].error_kind is kind


def test_all_sources_failing_gives_a_failed_aggregate_without_provenance():
    metadata = sources_of(failing("src_a", T.NOT_FOUND, E.NOT_FOUND), failing("src_b", T.NETWORK_ERROR))
    assert metadata.aggregate_status is AggregateStatus.FAILED and metadata.status is BatchItemStatus.FAILED
    assert metadata.field_provenance == () and metadata.traces_available is False
    assert [s.contributed for s in metadata.sources] == [False, False]
    assert metadata.error_kind is None


def test_a_run_without_traces_reports_traces_unavailable():
    metadata = sources_of(ok("src_a"), ok("src_b"))
    assert metadata.traces_available is False
    for source in metadata.sources:
        assert (source.trace_available, source.attempt_count, source.max_attempts, source.deadline_exceeded,
                source.deadline_during, source.attempts) == (False, None, None, None, None, ())


def test_a_retried_source_lists_every_attempt_in_sequence_order():
    bad = failing("src_b", T.NETWORK_ERROR, E.TIMEOUT)
    attempts = (b.make_attempt_in(1, T.NETWORK_ERROR, kind=E.TIMEOUT),
                b.make_attempt_in(2, T.NETWORK_ERROR, kind=E.TIMEOUT, backoff=0.25),
                b.make_attempt_in(3, T.NETWORK_ERROR, kind=E.TIMEOUT, backoff=0.5))
    good = ok("src_a")
    metadata = sources_of(good, bad, traces=(b.make_trace(good), b.make_trace(bad, attempts, max_attempts=3)))
    source = metadata.sources[1]
    assert metadata.traces_available is True and source.trace_available is True
    assert (source.attempt_count, source.max_attempts, source.deadline_exceeded) == (3, 3, False)
    assert [a.sequence for a in source.attempts] == [1, 2, 3]
    assert all(a.status is T.NETWORK_ERROR and a.error_kind is E.TIMEOUT and a.completed for a in source.attempts)
    assert [(a.elapsed_ms, a.backoff_before_ms) for a in source.attempts] == [(None, None)] * 3  # OMIT


def test_circuit_open_has_a_trace_without_attempts():
    bad = failing("src_b", T.NETWORK_ERROR, E.CIRCUIT_OPEN)
    good = ok("src_a")
    metadata = sources_of(good, bad, traces=(b.make_trace(good), b.make_trace(bad, ())))
    source = metadata.sources[1]
    assert source.trace_available is True and source.attempt_count == 0 and source.attempts == ()
    assert source.error_kind is E.CIRCUIT_OPEN and source.deadline_exceeded is False and source.deadline_during is None


def test_a_deadline_during_an_attempt_is_reported():
    bad = failing("src_b", T.NETWORK_ERROR, E.SOURCE_DEADLINE)
    good = ok("src_a")
    trace = b.make_trace(bad, (b.make_attempt_in(1, T.NETWORK_ERROR, kind=E.SOURCE_DEADLINE, completed=False),),
                         deadline_exceeded=True, deadline_during="attempt")
    source = sources_of(good, bad, traces=(b.make_trace(good), trace)).sources[1]
    assert (source.deadline_exceeded, source.deadline_during) == (True, "attempt")
    assert source.attempts[0].completed is False and source.attempts[0].error_kind is E.SOURCE_DEADLINE


def test_a_deadline_during_a_backoff_is_reported():
    bad = failing("src_b", T.NETWORK_ERROR, E.SOURCE_DEADLINE)
    good = ok("src_a")
    trace = b.make_trace(bad, (b.make_attempt_in(1, T.NETWORK_ERROR, kind=E.TIMEOUT),), max_attempts=3,
                         deadline_exceeded=True, deadline_during="backoff")
    source = sources_of(good, bad, traces=(b.make_trace(good), trace)).sources[1]
    assert (source.deadline_exceeded, source.deadline_during, source.attempt_count) == (True, "backoff", 1)


def test_disabled_sources_keep_their_input_order():
    metadata = sources_of(ok("src_a"), disabled=("zeta", "alpha", "mid"))
    assert metadata.disabled_source_ids == ("zeta", "alpha", "mid")


def test_sources_keep_the_source_results_order_not_an_alphabetical_one():
    metadata = sources_of(ok("zzz"), ok("aaa"), ok("mmm"))
    assert [s.source_id for s in metadata.sources] == ["zzz", "aaa", "mmm"]


def test_conflicts_carry_only_source_ids_never_values_or_keys():
    first, second = ok("src_a", title="C9CANARY-SELECTED"), ok("src_b", title="C9CANARY-OTHER")
    conflicts = (FieldConflict(field="title", selected_source_id="src_a", selected_value="C9CANARY-SELECTED",
                               alternatives=(("src_b", "C9CANARY-OTHER"),)),
                 FieldConflict(field="external_ids", selected_source_id="src_a", selected_value="C9CANARY-ID1",
                               alternatives=(("src_b", "C9CANARY-ID2"),), key="C9CANARY-KEY"),
                 FieldConflict(field="runtime", selected_source_id="src_a", selected_value=90,
                               alternatives=(("src_b", 95),)))
    metadata = sources_of(first, second, conflicts=conflicts)
    assert [(c.field, c.selected_source_id, c.alternative_source_ids) for c in metadata.conflicts] == [
        ("title", "src_a", ("src_b",)), ("external_ids", "src_a", ("src_b",)), ("runtime", "src_a", ("src_b",))]
    assert "C9CANARY" not in repr(metadata)


def test_source_error_detail_text_is_never_carried():
    bad = failing("src_b", T.NETWORK_ERROR)
    assert bad.error_detail == "C9CANARY-detail"
    assert "C9CANARY" not in repr(sources_of(ok("src_a"), bad))


def test_adapter_self_reported_elapsed_time_is_never_published():
    metadata = sources_of(ok("src_a", elapsed_ms=987654.0))
    preview = b.preview_of_metadata(b.batch_item_for(b.make_aggregation([ok("src_a", elapsed_ms=987654.0)]),
                                                       elapsed_ms=2.0))
    out = build_preview_diagnostics(preview, timing_policy=TimingPolicy.INCLUDE).items[0].metadata
    assert out.elapsed_ms == 2 and "987654" not in repr(out) and metadata is not None


# ---- safe source ids (contract 17.2)


@pytest.mark.parametrize("bad", ["has space", "-leading", "_leading", "a/b", "a\\b", "x" * 65, "日本語", "a\x00b"])
def test_an_unsafe_source_id_fails_closed_with_an_unsafe_value_error(bad):
    with pytest.raises(DiagnosticsUnsafeValueError) as caught:
        sources_of(ok(bad))
    assert bad not in str(caught.value)


@pytest.mark.parametrize("good", ["fc2db_net", "javdb", "av123", "A", "a.b-c_d", "x" * 64, "0leading"])
def test_safe_source_ids_are_accepted(good):
    assert sources_of(ok(good)).sources[0].source_id == good


def test_an_unsafe_disabled_source_id_fails_closed():
    with pytest.raises(DiagnosticsUnsafeValueError):
        sources_of(ok("src_a"), disabled=("bad id",))


# ---- structural limits (contract 21.2): at the limit succeeds, one above fails before any iteration


def test_64_sources_succeed_and_65_fail_with_a_resource_limit_error():
    many = [ok("s%d" % i) for i in range(64)]
    assert len(sources_of(*many, field_sources={"number": ("s0",)}).sources) == 64
    with pytest.raises(DiagnosticsResourceLimitError):
        sources_of(*[ok("s%d" % i) for i in range(65)], field_sources={"number": ("s0",)})


def test_64_disabled_sources_succeed_and_65_fail():
    assert len(sources_of(ok(), disabled=tuple("d%d" % i for i in range(64))).disabled_source_ids) == 64
    with pytest.raises(DiagnosticsResourceLimitError):
        sources_of(ok(), disabled=tuple("d%d" % i for i in range(65)))


def test_8_attempts_succeed_and_9_fail_with_a_resource_limit_error():
    bad = failing("src_b", T.NETWORK_ERROR, E.TIMEOUT)
    good = ok("src_a")

    def with_attempts(count):
        attempts = tuple(b.make_attempt_in(i + 1, T.NETWORK_ERROR, kind=E.TIMEOUT, backoff=0.0 if i == 0 else 0.1)
                         for i in range(count))
        return sources_of(good, bad, traces=(b.make_trace(good), b.make_trace(bad, attempts, max_attempts=count)))

    assert with_attempts(8).sources[1].attempt_count == 8
    with pytest.raises(DiagnosticsResourceLimitError):
        with_attempts(9)


def test_256_conflicts_succeed_and_257_fail():
    first, second = ok("src_a"), ok("src_b")

    def conflicts(count):
        return tuple(FieldConflict(field="title", selected_source_id="src_a", selected_value="v%d" % i,
                                   alternatives=(("src_b", "w%d" % i),)) for i in range(count))

    assert len(sources_of(first, second, conflicts=conflicts(256)).conflicts) == 256
    with pytest.raises(DiagnosticsResourceLimitError):
        sources_of(first, second, conflicts=conflicts(257))


def test_64_alternatives_succeed_and_65_fail():
    selected = ok("src_a")
    others = [ok("o%d" % i) for i in range(63)]

    def conflict(count):
        return (FieldConflict(field="title", selected_source_id="src_a", selected_value="v",
                              alternatives=tuple(("o%d" % i if i < 63 else "o62", "w%d" % i) for i in range(count))),)

    # 63 alternatives is the largest number the 64-source cap lets a real conflict reach
    assert len(sources_of(selected, *others, conflicts=conflict(63)).conflicts[0].alternative_source_ids) == 63
