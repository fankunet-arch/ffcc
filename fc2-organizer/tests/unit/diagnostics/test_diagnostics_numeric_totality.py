"""P4-C9 contract section 9.12 (Design-R4 Numeric Totality), matrix N-01..N-15 and the frozen boundary table.

Five numeric fields are exercised under OMIT and INCLUDE: ``BatchItemResult.elapsed_ms``,
``AggregationResult.elapsed_ms``, ``SourceResult.elapsed_ms``, ``SourceAttempt.elapsed_ms`` and
``SourceAttempt.backoff_before_seconds``. The hostile values are injected *behind the upstream constructors*
(``object.__setattr__``): the upstream constructors themselves would reject several of them. A failure must be a
``Diagnostics*`` error of the *exact* documented class -- never a bare ``OverflowError`` / ``ValueError`` /
``TypeError`` (the ``Diagnostics*`` classes inherit those builtins, so ``isinstance`` is not the criterion)."""

from __future__ import annotations

import math
import sys

import pytest
from fc2_metadata_core.models import SourceErrorKind as E, SourceStatus as T
from fc2_organizer.diagnostics import (
    DiagnosticsError,
    DiagnosticsIntegrityError as Int,
    DiagnosticsUnsafeValueError as Unsafe,
    TimingPolicy,
    build_preview_diagnostics,
    validation,
)

from . import _builders as b

OMIT, INCLUDE = TimingPolicy.OMIT, TimingPolicy.INCLUDE
FIELDS = ["item", "aggregation", "result", "attempt_elapsed", "attempt_backoff"]
PUBLISHED = {"item", "attempt_elapsed", "attempt_backoff"}
BARE = (OverflowError, ValueError, TypeError)


def graph():
    good = b.make_source_result("src_a", T.SUCCESS)
    bad = b.make_source_result("src_b", T.NETWORK_ERROR)
    attempts = (b.make_attempt_in(1, T.NETWORK_ERROR, kind=E.TIMEOUT, elapsed=20.0),
                b.make_attempt_in(2, T.NETWORK_ERROR, kind=E.TIMEOUT, elapsed=25.0, backoff=0.5))
    aggregation = b.make_aggregation([good, bad], traces=(b.make_trace(good), b.make_trace(bad, attempts)))
    item = b.batch_item_for(aggregation, elapsed_ms=7.0)
    preview = b.preview_of_metadata(item)
    targets = {"item": (item, "elapsed_ms"), "aggregation": (aggregation, "elapsed_ms"),
               "result": (good, "elapsed_ms"), "attempt_elapsed": (attempts[1], "elapsed_ms"),
               "attempt_backoff": (attempts[1], "backoff_before_seconds")}
    return preview, targets


def run(field, value, policy):
    preview, targets = graph()
    obj, name = targets[field]
    b.poke(obj, **{name: value})
    return build_preview_diagnostics(preview, timing_policy=policy)


def outcome(field, value, policy):
    """The exact exception class raised (or ``None`` on success); asserts the failure is never a bare builtin."""
    try:
        run(field, value, policy)
    except Exception as exc:  # noqa: BLE001 -- the point of the test is to classify *any* escape
        assert isinstance(exc, DiagnosticsError), "bare %s escaped" % type(exc).__name__
        assert type(exc) not in BARE
        return type(exc)
    return None


HUGE_INTS = [10**400, 10**4000]
HUGE_FLOATS = [1e306, sys.float_info.max]
NON_FINITE = [math.nan, math.inf, -math.inf]
NEGATIVE = [-1, -0.5, -(10**400), -sys.float_info.max]
WRONG_TYPES = [True, False, "1", None, b"1", (1,), [1], {}, object()]


class IntSub(int):
    pass


class FloatSub(float):
    pass


# ---- (1)(2) huge exact int: OMIT accepts (validation-only), INCLUDE rejects as Unsafe where published


@pytest.mark.parametrize("field", FIELDS)
@pytest.mark.parametrize("value", HUGE_INTS, ids=["1e400", "1e4000"])
def test_huge_exact_int_is_accepted_under_omit(field, value):
    assert outcome(field, value, OMIT) is None


@pytest.mark.parametrize("field", FIELDS)
@pytest.mark.parametrize("value", HUGE_INTS, ids=["1e400", "1e4000"])
def test_huge_exact_int_under_include_is_unsafe_where_published_else_accepted(field, value):
    assert outcome(field, value, INCLUDE) is (Unsafe if field in PUBLISHED else None)


# ---- (3) huge finite float (1e306 * 1000 would overflow to inf)


@pytest.mark.parametrize("field", FIELDS)
@pytest.mark.parametrize("value", HUGE_FLOATS)
def test_huge_finite_float(field, value):
    assert outcome(field, value, OMIT) is None
    assert outcome(field, value, INCLUDE) is (Unsafe if field in PUBLISHED else None)


# ---- (4)(5)(6) NaN / +inf / -inf are Integrity under any policy


@pytest.mark.parametrize("field", FIELDS)
@pytest.mark.parametrize("value", NON_FINITE)
@pytest.mark.parametrize("policy", [OMIT, INCLUDE])
def test_non_finite_floats_are_integrity_errors(field, value, policy):
    assert outcome(field, value, policy) is Int


# ---- (7) negatives; -0.0 is accepted and published as 0


@pytest.mark.parametrize("field", FIELDS)
@pytest.mark.parametrize("value", NEGATIVE, ids=["-1", "-0.5", "-huge-int", "-maxfloat"])
@pytest.mark.parametrize("policy", [OMIT, INCLUDE])
def test_negative_numbers_are_integrity_errors(field, value, policy):
    assert outcome(field, value, policy) is Int


def test_negative_zero_is_accepted_and_published_as_zero():
    out = run("item", -0.0, INCLUDE).items[0].metadata
    assert out.elapsed_ms == 0 and type(out.elapsed_ms) is int
    attempt = run("attempt_backoff", -0.0, INCLUDE).items[0].metadata.sources[1].attempts[1]
    assert attempt.backoff_before_ms == 0 and type(attempt.backoff_before_ms) is int
    attempt = run("attempt_elapsed", -0.0, INCLUDE).items[0].metadata.sources[1].attempts[1]
    assert attempt.elapsed_ms == 0


# ---- wrong types: bool, subclasses, str, None, containers


@pytest.mark.parametrize("field", FIELDS)
@pytest.mark.parametrize("value", WRONG_TYPES + [IntSub(3), FloatSub(3.0)], ids=lambda v: type(v).__name__ + repr(v)[:6])
@pytest.mark.parametrize("policy", [OMIT, INCLUDE])
def test_wrong_numeric_types_are_integrity_errors(field, value, policy):
    assert outcome(field, value, policy) is Int


# ---- (8)(9) the frozen boundary table


ELAPSED_BOUNDARY = [  # (value, OMIT result, INCLUDE result, published value)
    (604800000, None, None, 604800000), (604800001, None, Unsafe, None),
    (604800000.0, None, None, 604800000), (604800000.999, None, None, 604800000),
    (604800001.0, None, Unsafe, None), (0, None, None, 0), (0.0, None, None, 0),
    (1500, None, None, 1500), (1500.7, None, None, 1500), (0.999, None, None, 0),
]
BACKOFF_BOUNDARY = [
    (604800, None, None, 604800000), (604801, None, Unsafe, None),
    (604800.0, None, None, 604800000), (math.nextafter(604800.0, math.inf), None, Unsafe, None),
    (2, None, None, 2000), (0.25, None, None, 250), (0, None, None, 0), (0.0, None, None, 0),
    (604799.9999, None, None, 604799999),
]


@pytest.mark.parametrize(("value", "omit", "include", "published"), ELAPSED_BOUNDARY)
@pytest.mark.parametrize("field", ["item", "attempt_elapsed"])
def test_elapsed_boundary_table(field, value, omit, include, published):
    assert outcome(field, value, OMIT) is omit
    assert outcome(field, value, INCLUDE) is include
    if include is None:
        metadata = run(field, value, INCLUDE).items[0].metadata
        got = metadata.elapsed_ms if field == "item" else metadata.sources[1].attempts[1].elapsed_ms
        assert got == published and type(got) is int


@pytest.mark.parametrize(("value", "omit", "include", "published"), BACKOFF_BOUNDARY)
def test_backoff_boundary_table(value, omit, include, published):
    assert outcome("attempt_backoff", value, OMIT) is omit
    assert outcome("attempt_backoff", value, INCLUDE) is include
    if include is None:
        got = run("attempt_backoff", value, INCLUDE).items[0].metadata.sources[1].attempts[1].backoff_before_ms
        assert got == published and type(got) is int and 0 <= got <= 604800000


@pytest.mark.parametrize("field", ["aggregation", "result"])
@pytest.mark.parametrize("value", [604800001, 604800001.0, 10**400, 1e306], ids=["i", "f", "huge-i", "huge-f"])
def test_unpublished_timing_fields_ignore_the_publication_bound_under_every_policy(field, value):
    assert outcome(field, value, OMIT) is None and outcome(field, value, INCLUDE) is None


def test_the_strict_backoff_gate_rejects_the_value_the_r3_truncation_would_have_let_through():
    just_over = 604800.0005
    assert int(just_over * 1000) == 604800000  # R3: truncate first -> looks like the bound -> let through
    assert outcome("attempt_backoff", just_over, INCLUDE) is Unsafe  # R4: gate first -> reject


# ---- normal values (10)(11)(12)


def test_normal_values_convert_as_documented():
    out = run("attempt_backoff", 2, INCLUDE).items[0].metadata.sources[1].attempts[1]
    assert (out.backoff_before_ms, out.elapsed_ms) == (2000, 25)
    assert run("attempt_backoff", 0.25, INCLUDE).items[0].metadata.sources[1].attempts[1].backoff_before_ms == 250
    for seconds in (604800, 604800.0):
        got = run("attempt_backoff", seconds, INCLUDE).items[0].metadata.sources[1].attempts[1].backoff_before_ms
        assert got == 604800000


# ---- N-11: sequence == 1 and a non-zero backoff -> Integrity (huge ints included, no bare exception)


@pytest.mark.parametrize("value", [1, 0.5, 10**400, 1e306, sys.float_info.max], ids=["1", "0.5", "i400", "f306", "fmax"])
@pytest.mark.parametrize("policy", [OMIT, INCLUDE])
def test_first_attempt_with_a_non_zero_backoff_is_an_integrity_error(value, policy):
    preview, targets = graph()
    aggregation = targets["item"][0].aggregation_result
    first = aggregation.source_execution_traces[1].attempts[0]
    b.poke(first, backoff_before_seconds=value)
    with pytest.raises(Int) as caught:
        build_preview_diagnostics(preview, timing_policy=policy)
    assert type(caught.value) is Int


def test_first_attempt_with_a_zero_backoff_in_either_exact_type_is_accepted():
    for zero in (0, 0.0, -0.0):
        preview, targets = graph()
        first = targets["item"][0].aggregation_result.source_execution_traces[1].attempts[0]
        b.poke(first, backoff_before_seconds=zero)
        build_preview_diagnostics(preview, timing_policy=INCLUDE)


# ---- N-12 / N-13 / N-14: huge int counters, budgets and ranges -> typed errors only


HUGE = 10**4000
HUGE_IDS = ["huge", "-huge"]


@pytest.mark.parametrize("value", [HUGE, -HUGE], ids=HUGE_IDS)
@pytest.mark.parametrize("name", ["batch_size", "retention_budget_bytes", "retry_budget_bytes"])
def test_huge_int_batch_counters_and_budgets_fail_with_typed_errors_only(name, value):
    lineage = b.Lineage(1)
    preview = lineage.preview([lineage.preview_item(0)])
    b.poke(preview, **{name: value})
    with pytest.raises(DiagnosticsError) as caught:
        build_preview_diagnostics(preview)
    assert type(caught.value) not in BARE


@pytest.mark.parametrize("value", [HUGE, -HUGE], ids=HUGE_IDS)
def test_huge_int_item_index_fails_with_a_typed_error_only(value):
    lineage = b.Lineage(1)
    preview = lineage.preview([lineage.preview_item(0)])
    b.poke(preview.items[0], index=value)
    with pytest.raises(DiagnosticsError) as caught:
        build_preview_diagnostics(preview)
    assert type(caught.value) not in BARE


def test_an_unbounded_int_field_accepts_any_magnitude_and_is_never_converted_to_text():
    old = sys.get_int_max_str_digits()
    sys.set_int_max_str_digits(640)
    try:
        preview, targets = graph()
        item = targets["item"][0]
        b.poke(item, generation=HUGE)
        b.poke(preview.metadata_batch, generation=HUGE)
        out = build_preview_diagnostics(preview)
        assert out.items[0].metadata.generation == HUGE
    finally:
        sys.set_int_max_str_digits(old)


# ---- math.isfinite tripwire (N-01 / TN-1): only ever applied to an exact float


class SpyMath:
    def __init__(self):
        self.args = []

    def isfinite(self, value):
        self.args.append(type(value))
        if type(value) is not float:
            raise AssertionError("math.isfinite saw a %s" % type(value).__name__)
        return math.isfinite(value)

    def __getattr__(self, name):
        return getattr(math, name)


@pytest.mark.parametrize("field", FIELDS)
@pytest.mark.parametrize("value", [10**400, 10**4000, 1500, 0, 1e306, 2.5, 0.0], ids=["i400", "i4000", "i1500", "i0", "f306", "f2.5", "f0"])
@pytest.mark.parametrize("policy", [OMIT, INCLUDE])
def test_isfinite_never_sees_an_int(monkeypatch, field, value, policy):
    spy = SpyMath()
    monkeypatch.setattr(validation, "math", spy)
    try:
        run(field, value, policy)
    except DiagnosticsError:
        pass
    assert all(kind is float for kind in spy.args)


def test_isfinite_tripwire_is_not_vacuous(monkeypatch):
    spy = SpyMath()
    monkeypatch.setattr(validation, "math", spy)
    run("item", 1.5, INCLUDE)
    assert spy.args and set(spy.args) == {float}


def test_a_mutation_that_calls_isfinite_on_a_huge_int_is_detected(monkeypatch):
    """Mutation (R3-01): ``math.isfinite`` on an exact int. The real ``isfinite`` raises OverflowError on 10**400."""
    with pytest.raises(OverflowError):
        math.isfinite(10**400)
    spy = SpyMath()
    with pytest.raises(AssertionError):
        spy.isfinite(10**400)


# ---- numeric mutations (contract 28.5 R3-01 row): each deviant implementation is rejected by this file


def _mutated(monkeypatch, name, replacement):
    monkeypatch.setattr(validation, name, replacement)


def test_mutation_convert_then_check_backoff_is_detected(monkeypatch):
    def convert_first(value):  # R3: multiply / int() before any bound
        if type(value) is int:
            return value * 1000
        return int(value * 1000)

    _mutated(monkeypatch, "publish_backoff_ms", convert_first)
    with pytest.raises(OverflowError):  # the mutant lets the bare exception escape for 1e306 ...
        run("attempt_backoff", 1e306, INCLUDE)
    monkeypatch.undo()
    assert outcome("attempt_backoff", 1e306, INCLUDE) is Unsafe  # ... the real code does not


def test_mutation_truncating_before_the_bound_is_detected(monkeypatch):
    def truncating(value):
        milliseconds = value * 1000 if type(value) is int else int(value * 1000)
        if milliseconds > 604800000:
            validation.unsafe("a timing value exceeds MAX_TIMING_MS")
        return milliseconds

    _mutated(monkeypatch, "publish_backoff_ms", truncating)
    assert outcome("attempt_backoff", 604800.0005, INCLUDE) is None  # mutant lets the R3 value through
    monkeypatch.undo()
    assert outcome("attempt_backoff", 604800.0005, INCLUDE) is Unsafe


def test_mutation_float_conversion_of_a_huge_elapsed_int_is_detected(monkeypatch):
    def via_float(value):
        if float(value) >= 604800001.0:
            validation.unsafe("a timing value exceeds MAX_TIMING_MS")
        return int(value)

    _mutated(monkeypatch, "publish_elapsed_ms", via_float)
    with pytest.raises(OverflowError):
        run("item", 10**400, INCLUDE)
    monkeypatch.undo()
    assert outcome("item", 10**400, INCLUDE) is Unsafe


def test_mutation_omit_imposing_the_publication_bound_is_detected(monkeypatch):
    def bounded(value, message):
        if type(value) is int and value > 604800000:
            validation.fail(message)
        if type(value) is float and value >= 604800001.0:
            validation.fail(message)

    _mutated(monkeypatch, "check_number", bounded)
    assert outcome("item", 10**400, OMIT) is Int  # the mutant rejects what OMIT must accept
    monkeypatch.undo()
    assert outcome("item", 10**400, OMIT) is None
    assert outcome("item", 1e306, OMIT) is None


def test_mutation_isfinite_on_every_number_is_detected(monkeypatch):
    def isfinite_everything(value, message):
        if not math.isfinite(value):
            validation.fail(message)

    _mutated(monkeypatch, "check_number", isfinite_everything)
    with pytest.raises(OverflowError):
        run("item", 10**400, OMIT)
    monkeypatch.undo()
    assert outcome("item", 10**400, OMIT) is None
