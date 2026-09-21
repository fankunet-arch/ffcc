"""Phase 3 C4-R1 closure tests (findings C4-R1-01 .. C4-R1-05). Contract: PHASE3_BATCH_CONTRACT.md §2/§4/§6/§7/§8.

Shared idea: *caller-controlled metadata must never run, and therefore can never steer control flow.* Every hostile
object below records into ``HOSTILE`` when any of its code runs; the tests assert that list stays empty.

* C4-R1-01  ordinary ``Exception`` whose class metadata is hostile stays an isolated FAILED item.
* C4-R1-02  a fatal ``BaseException`` whose class metadata is hostile is still propagated as the original object.
* C4-R1-03  ``apply_retry`` rejects a retry from another batch even when its shape is identical (lineage).
* C4-R1-04  busy-first: an active scheduler answers ``BatchBusyError`` before looking at the argument; the
            regression tests fail fast (never hang) when the guard is broken.
* C4-R1-05  batch elements must be exact ``str``; a ``str`` subclass is rejected without running its methods.
"""

from __future__ import annotations

import asyncio
import copy
import gc
import weakref

import pytest

from fc2_metadata_core.batch import (
    BatchBusyError,
    BatchConfig,
    BatchInputError,
    BatchItemErrorKind,
    BatchItemStatus,
    BatchLineage,
    BatchResult,
    BatchRetryError,
    BatchScheduler,
    RetryBatchResult,
    apply_retry,
)
from fc2_metadata_core.batch.scheduler import _FatalSignal, _type_name
from support.batch_fakes import Gate, ScriptedEngine, agg, numbers, until

HOSTILE: list[str] = []  # anything appended here means hostile caller-controlled code RAN


@pytest.fixture(autouse=True)
def _clean_hostile_log():
    HOSTILE.clear()
    yield
    assert HOSTILE == [], f"hostile metadata code was executed: {HOSTILE}"


class CustomFatal(BaseException):
    pass


RAISERS = [RuntimeError, KeyboardInterrupt, SystemExit, GeneratorExit, CustomFatal]
BASE_EXCEPTION_RAISERS = [KeyboardInterrupt, SystemExit, GeneratorExit, CustomFatal]


def make_hostile(base, raiser, label="Hostile"):
    """A ``base`` subclass whose METACLASS ``__name__`` raises ``raiser()`` (and records that it ran)."""

    class Meta(type):
        @property
        def __name__(cls):
            HOSTILE.append(f"metaclass __name__ of {label}")
            raise raiser()

    return Meta(label, (base,), {})


def run(coro):
    return asyncio.run(coro)


def others():
    return [t for t in asyncio.all_tasks() if t is not asyncio.current_task() and not t.done()]


# ==================================================================================================================
# C4-R1-01  _type_name is total; an ordinary Exception can never be upgraded to a batch fatal
# ==================================================================================================================


@pytest.mark.parametrize("raiser", RAISERS, ids=lambda r: r.__name__)
def test_r1_01_ordinary_exception_with_a_hostile_metaclass_name_is_an_isolated_failed_item(raiser):
    Hostile = make_hostile(Exception, raiser)
    refs: list[weakref.ref] = []

    async def behavior(number, seq):
        await asyncio.sleep(0)
        if seq == 1:
            exc = Hostile("SECRET-token=abc123")
            refs.append(weakref.ref(exc))
            raise exc
        return agg(number)

    engine = ScriptedEngine(behavior)
    result = run(BatchScheduler(engine, BatchConfig(max_in_flight_items=2)).run(numbers(8)))

    assert result.total == 8 and len(engine.calls) == 8, "the batch returned normally and continued"
    bad = result.items[1]
    assert bad.status is BatchItemStatus.FAILED
    assert bad.error_kind is BatchItemErrorKind.ENGINE_EXCEPTION
    assert bad.error_type == "UnknownType", "an untrusted metaclass collapses to the safe fallback"
    assert bad.aggregation_result is None
    assert [i.status for i in result.items if i.index != 1] == [BatchItemStatus.SUCCESS] * 7, "siblings continue"
    assert "SECRET" not in repr(result)
    gc.collect()
    assert refs and all(r() is None for r in refs), "no exception object retained"


@pytest.mark.parametrize("raiser", RAISERS, ids=lambda r: r.__name__)
def test_r1_01_an_engine_result_with_a_hostile___class___is_a_contract_mismatch_not_a_fatal(raiser):
    """``isinstance`` would consult the object's ``__class__`` property -- code the engine controls."""

    class Sneaky:
        @property
        def __class__(self):  # noqa: D401
            HOSTILE.append("__class__ property")
            raise raiser()

    async def behavior(number, seq):
        return Sneaky()

    result = run(BatchScheduler(ScriptedEngine(behavior)).run(numbers(3)))
    assert [i.error_kind for i in result.items] == [BatchItemErrorKind.RESULT_CONTRACT_MISMATCH] * 3
    assert [i.error_type for i in result.items] == ["Sneaky"] * 3


@pytest.mark.parametrize("raiser", RAISERS, ids=lambda r: r.__name__)
def test_r1_01_type_name_is_total_over_hostile_metaclasses(raiser):
    Hostile = make_hostile(Exception, raiser)
    assert _type_name(Hostile("x")) == "UnknownType"
    assert _type_name(Hostile) == "Meta", "the class object's own type is the (plain, safe) metaclass Meta"


def test_r1_01_type_name_of_ordinary_things_is_the_class_name():
    assert _type_name(RuntimeError("SECRET")) == "RuntimeError"
    assert _type_name(None) == "NoneType"
    assert _type_name(ExceptionGroup("g", [ValueError("x")])) == "ExceptionGroup"

    class Plain(Exception):
        pass

    assert _type_name(Plain("SECRET")) == "Plain"


def test_r1_01_type_name_rejects_names_that_are_not_short_exact_identifier_strs():
    assert _type_name(type("not an identifier!", (Exception,), {})()) == "UnknownType"
    assert _type_name(type("L" * 500, (Exception,), {})()) == "UnknownType"
    assert _type_name(type("L" * 128, (Exception,), {})()) == "L" * 128

    class EvilStr(str):
        def isidentifier(self):
            HOSTILE.append("EvilStr.isidentifier")
            return True

        def __str__(self):
            HOSTILE.append("EvilStr.__str__")
            raise KeyboardInterrupt

        def __len__(self):
            HOSTILE.append("EvilStr.__len__")
            raise SystemExit

    class Renamed(Exception):
        pass

    try:
        Renamed.__name__ = EvilStr("Evil")  # a str *subclass* as the class name
    except TypeError:  # pragma: no cover - interpreter refuses it outright: nothing to defend against
        return
    assert _type_name(Renamed()) == "UnknownType", "a non-exact str name is untrusted and none of its methods run"


def test_r1_01_an_abc_style_metaclass_is_not_trusted_either():
    import abc

    class WithAbc(Exception, metaclass=type(abc.ABC)):
        pass

    assert _type_name(WithAbc()) == "UnknownType"


# ==================================================================================================================
# C4-R1-02  the fatal carrier holds the original and reads nothing from it
# ==================================================================================================================


@pytest.mark.parametrize("raiser", RAISERS, ids=lambda r: r.__name__)
def test_r1_02_the_fatal_carrier_does_not_touch_the_originals_metadata(raiser):
    Fatal = make_hostile(BaseException, raiser)
    original = Fatal("SECRET")
    carrier = _FatalSignal(original)
    assert carrier.original is original
    assert carrier.args == (), "no name, text or repr of the original was copied into the carrier"


@pytest.mark.parametrize("raiser", RAISERS, ids=lambda r: r.__name__)
@pytest.mark.parametrize("via", ["serial", "with-siblings"])
def test_r1_02_a_fatal_with_hostile_metadata_still_reaches_the_caller_as_the_original(raiser, via):
    Fatal = make_hostile(BaseException, raiser)
    boom = Fatal("fatal-secret")
    batch = numbers(40)
    limit = 1 if via == "serial" else 4
    gate = {}

    async def behavior(number, seq):
        if seq == 2:
            await asyncio.sleep(0)
            raise boom
        if via == "with-siblings":
            await gate["g"].wait()  # siblings are blocked when the fatal happens
        else:
            await asyncio.sleep(0)
        return agg(number)

    engine = ScriptedEngine(behavior)
    sched = BatchScheduler(engine, BatchConfig(max_in_flight_items=limit))

    async def observe():
        try:
            return None, await sched.run(batch)
        except BaseException as exc:  # noqa: BLE001
            return exc, None

    async def scenario():
        gate["g"] = Gate()
        caught, value = await observe()
        await asyncio.sleep(0)
        leftover = others()
        # scheduler reusable afterwards (a healed engine, a fresh batch)
        engine._behavior = ScriptedEngine._default
        again = await sched.run(numbers(3, start=7_000_001))
        return caught, value, leftover, again

    caught, value, leftover, again = run(scenario())
    assert caught is boom, "the ORIGINAL object, whatever its class metadata does"
    assert not isinstance(caught, BaseExceptionGroup)
    assert value is None, "no partial BatchResult"
    assert leftover == [] and engine.active == 0
    admitted = 3 if via == "serial" else 4
    assert engine.calls[:admitted] == batch[:admitted]
    assert not any(n in engine.calls for n in batch[admitted:]), "nothing admitted after the fatal"
    if via == "with-siblings":
        assert sorted(engine.cancelled) == sorted(n for i, n in enumerate(batch[:4]) if i != 2), "siblings were cancelled"
    assert again.success_count == 3


@pytest.mark.parametrize("raiser", RAISERS, ids=lambda r: r.__name__)
def test_r1_02_a_sibling_resuming_in_the_same_iteration_admits_nothing_after_a_hostile_fatal(raiser):
    Fatal = make_hostile(BaseException, raiser)
    boom = Fatal()

    async def scenario():
        go = asyncio.Event()

        async def behavior(number, seq):
            if seq in (0, 1):
                await go.wait()
            if seq == 0:
                raise boom
            return agg(number)

        engine = ScriptedEngine(behavior)

        async def observe():
            try:
                return None, await BatchScheduler(engine, BatchConfig(max_in_flight_items=2)).run(numbers(20))
            except BaseException as exc:  # noqa: BLE001
                return exc, None

        task = asyncio.create_task(observe())
        await until(lambda: engine.active == 2)
        go.set()
        caught, value = await task
        await asyncio.sleep(0)
        return engine, caught, value, others()

    engine, caught, value, leftover = run(scenario())
    assert caught is boom and value is None and leftover == []
    assert engine.calls == numbers(2)


# ==================================================================================================================
# C4-R1-03  lineage: a retry only merges into the batch it came from
# ==================================================================================================================


def two_identical_batches(*, duplicates=True):
    """Two independent runs of the SAME input with the SAME failures: identical in every observable shape."""
    n = numbers(5)
    batch = n + [n[1]] if duplicates else n  # a duplicate number, failing in both places

    def build():
        phase = {"n": 0}

        async def behavior(number, seq):
            await asyncio.sleep(0)
            if number in (n[1], n[3]) and phase["n"] == 0:
                raise RuntimeError("primary failure")
            if number == n[3] and phase["n"] == 1:
                raise RuntimeError("still failing in round 1")
            return agg(number)

        engine = ScriptedEngine(behavior)
        return phase, engine, BatchScheduler(engine, BatchConfig(max_in_flight_items=2))

    return batch, build


def test_r1_03_a_retry_from_batch_a_is_rejected_by_an_identically_shaped_batch_b():
    batch, build = two_identical_batches()
    phase_a, _, sched_a = build()
    phase_b, _, sched_b = build()
    primary_a, primary_b = run(sched_a.run(batch)), run(sched_b.run(batch))
    phase_a["n"] = 1
    retry_a = run(sched_a.retry_failed(primary_a))

    # Everything the OLD shape check could look at is identical ...
    assert primary_a.failed_indices == primary_b.failed_indices == retry_a.indices
    assert primary_a.failed_numbers == primary_b.failed_numbers
    assert primary_a.generation == primary_b.generation and retry_a.generation == primary_b.generation + 1
    assert [i.number for i in primary_a.items] == [i.number for i in primary_b.items]
    # ... and yet only the batch it came from accepts it.
    with pytest.raises(BatchRetryError, match="lineage"):
        apply_retry(primary_b, retry_a)
    assert apply_retry(primary_a, retry_a).generation == 1


def test_r1_03_a_second_run_of_the_same_input_on_the_same_scheduler_is_a_different_lineage():
    batch, build = two_identical_batches()
    phase, _, sched = build()
    first, second = run(sched.run(batch)), run(sched.run(batch))
    assert first.lineage != second.lineage
    phase["n"] = 1
    retry_first = run(sched.retry_failed(first))
    with pytest.raises(BatchRetryError):
        apply_retry(second, retry_first)


def test_r1_03_the_correct_retry_is_accepted_and_the_previous_result_is_untouched():
    batch, build = two_identical_batches()
    phase, engine, sched = build()
    primary = run(sched.run(batch))
    before = (primary.items, primary.generation, primary.lineage)
    phase["n"] = 1
    retry = run(sched.retry_failed(primary))
    merged = apply_retry(primary, retry)
    assert merged.total == primary.total and merged.generation == 1
    assert (primary.items, primary.generation, primary.lineage) == before


def test_r1_03_the_lineage_survives_primary_to_retry_to_merged_to_the_next_rounds():
    batch, build = two_identical_batches()
    phase_a, _, sched_a = build()
    phase_b, _, sched_b = build()
    primary_a, primary_b = run(sched_a.run(batch)), run(sched_b.run(batch))

    phase_a["n"] = phase_b["n"] = 1
    retry1_a, retry1_b = run(sched_a.retry_failed(primary_a)), run(sched_b.retry_failed(primary_b))
    merged1_a, merged1_b = apply_retry(primary_a, retry1_a), apply_retry(primary_b, retry1_b)
    assert primary_a.lineage == retry1_a.lineage == merged1_a.lineage
    assert primary_b.lineage == retry1_b.lineage == merged1_b.lineage != primary_a.lineage

    phase_a["n"] = phase_b["n"] = 2
    retry2_a, retry2_b = run(sched_a.retry_failed(merged1_a)), run(sched_b.retry_failed(merged1_b))
    merged2_a = apply_retry(merged1_a, retry2_a)
    assert retry2_a.lineage == merged2_a.lineage == primary_a.lineage, "still the same chain at generation 2"
    assert retry2_a.generation == 2 and merged2_a.generation == 2
    # identical shape at generation 1 -> 2 in both chains; only the lineage tells them apart
    assert merged1_a.failed_indices == merged1_b.failed_indices == retry2_a.indices
    with pytest.raises(BatchRetryError):
        apply_retry(merged1_b, retry2_a)
    with pytest.raises(BatchRetryError):
        apply_retry(merged1_a, retry2_b)
    assert apply_retry(merged1_b, retry2_b).generation == 2


def test_r1_03_duplicate_number_identity_is_untouched_by_lineage():
    batch, build = two_identical_batches(duplicates=True)
    phase, engine, sched = build()
    primary = run(sched.run(batch))
    assert primary.failed_indices == (1, 3, 5) and primary.failed_numbers[0] == primary.failed_numbers[2]
    phase["n"] = 1
    retry = run(sched.retry_failed(primary))
    assert retry.indices == (1, 3, 5)
    merged = apply_retry(primary, retry)
    assert [(i.index, i.number) for i in merged.items] == [(i.index, i.number) for i in primary.items]


def test_r1_03_lineage_is_identity_by_value_so_a_reconstructed_copy_of_the_same_batch_still_matches():
    batch, build = two_identical_batches()
    phase, _, sched = build()
    primary = run(sched.run(batch))
    phase["n"] = 1
    retry = run(sched.retry_failed(primary))
    assert copy.deepcopy(primary.lineage) == primary.lineage
    rebuilt = BatchResult(primary.items, generation=primary.generation, lineage=BatchLineage(primary.lineage.token))
    assert apply_retry(rebuilt, retry).generation == 1
    assert isinstance(retry, RetryBatchResult)
    # a result built by hand for the same items is a DIFFERENT batch as far as provenance goes
    with pytest.raises(BatchRetryError):
        apply_retry(BatchResult(primary.items, generation=primary.generation), retry)


# ==================================================================================================================
# C4-R1-04  busy-first, and a regression test that cannot hang
# ==================================================================================================================

FIRST = numbers(2, start=1_000_001)  # the run that is held open
PRE = numbers(3, start=9_000_001)  # failed in a finished run so that a valid retry_failed(previous) exists


async def busy_probe(scheduler_cls, second, *, watchdog=5.0):
    """Hold one run open, fire ``second(sched, previous)`` at the busy scheduler, report what happened.

    Never hangs: the second call is bounded by ``asyncio.timeout(watchdog)``, the held-open run is always released
    and awaited in ``finally``, and the leftover tasks are reported. If the guard is broken the second call either
    returns (its numbers are not gated) or times out -- both are *reported*, never waited on forever.
    """
    gate = Gate()
    state = {"healed": False}

    async def behavior(number, seq):
        if number in FIRST:
            await gate.wait()
        elif number in PRE and not state["healed"]:
            raise RuntimeError("primary failure")
        return agg(number)

    engine = ScriptedEngine(behavior)
    sched = scheduler_cls(engine, BatchConfig(max_in_flight_items=2))
    previous = await sched.run(PRE)  # a finished run with failures: a valid argument for retry_failed
    state["healed"] = True
    out = {"busy": False, "returned": False, "timed_out": False, "other": None, "extra_calls": None, "still_busy": None}
    first = asyncio.create_task(sched.run(FIRST))
    try:
        await until(lambda: engine.active == 2)
        calls_before = len(engine.calls)
        try:
            async with asyncio.timeout(watchdog):
                await second(sched, previous)
            out["returned"] = True
        except BatchBusyError:
            out["busy"] = True
        except TimeoutError:
            out["timed_out"] = True
        except BaseException as exc:  # noqa: BLE001 - e.g. BatchInputError / BatchRetryError: busy-first violated
            out["other"] = type(exc).__name__
        out["extra_calls"] = len(engine.calls) - calls_before
        try:  # the rejected call must not have released the first run's claim
            await sched.run([])
            out["still_busy"] = False
        except BatchBusyError:
            out["still_busy"] = True
    finally:
        gate.release.set()
        await asyncio.gather(first, return_exceptions=True)
    await asyncio.sleep(0)
    out["leftover"] = others()
    out["first_ok"] = first.done() and not first.cancelled() and first.exception() is None
    return out


SECOND_CALLS = {
    "valid run": lambda s, p: s.run(numbers(2, start=5_000_001)),
    "empty run": lambda s, p: s.run([]),
    "run: dirty element": lambda s, p: s.run(["FC2-1000001", "abc FC2PPV-1234567.mp4"]),
    "run: bare str": lambda s, p: s.run("FC2-1000001"),
    "run: set": lambda s, p: s.run({"FC2-1000001"}),
    "run: None": lambda s, p: s.run(None),
    "run: str subclass": lambda s, p: s.run([BenignStr("FC2-1000001")]),
    "valid retry": lambda s, p: s.retry_failed(p),
    "retry: None": lambda s, p: s.retry_failed(None),
    "retry: object": lambda s, p: s.retry_failed(object()),
    "retry: RetryBatchResult": lambda s, p: s.retry_failed(RetryBatchResult((), generation=1, lineage=p.lineage)),
}


@pytest.mark.parametrize("name", list(SECOND_CALLS))
def test_r1_04_an_active_scheduler_answers_busy_first_for_every_kind_of_second_call(name):
    out = run(busy_probe(BatchScheduler, SECOND_CALLS[name]))
    assert out["busy"] is True, f"{name}: expected BatchBusyError first, got {out}"
    assert out["other"] is None and out["returned"] is False and out["timed_out"] is False
    assert out["extra_calls"] == 0, "the rejected call made zero engine calls"
    assert out["still_busy"] is True, "a rejected call must not release the running run's claim"
    assert out["first_ok"] and out["leftover"] == []


def test_r1_04_validation_still_happens_when_the_scheduler_is_idle():
    async def scenario():
        sched = BatchScheduler(ScriptedEngine())
        with pytest.raises(BatchInputError):
            await sched.run(["nope"])
        with pytest.raises(BatchRetryError):
            await sched.retry_failed(None)  # type: ignore[arg-type]
        with pytest.raises(BatchInputError):
            await sched.run("FC2-1000001")
        return (await sched.run(numbers(2))).total  # and none of the failures left it busy

    assert run(scenario()) == 2


class UnguardedScheduler(BatchScheduler):
    """The busy guard removed -- exactly the mutation the regression test must catch, without hanging."""

    def _claim(self) -> None:
        self._busy = True


def test_r1_04_the_regression_fails_fast_and_reports_when_the_guard_is_removed_and_the_second_call_returns():
    out = run(busy_probe(UnguardedScheduler, SECOND_CALLS["valid run"]))
    assert out["busy"] is False and out["returned"] is True, "no guard: the second run simply ran"
    assert out["extra_calls"] > 0
    assert out["leftover"] == []


def test_r1_04_the_regression_fails_fast_and_reports_when_the_guard_is_removed_and_the_second_call_would_hang():
    """The second run uses the gated numbers, so without the guard it would block forever on the gate (the old
    test's failure mode). The bounded watchdog turns that into a *reported* time-out, and nothing is left behind."""
    out = run(busy_probe(UnguardedScheduler, lambda s, p: s.run(FIRST), watchdog=0.2))
    assert out["timed_out"] is True and out["busy"] is False
    assert out["leftover"] == [], "the abandoned second run was cancelled and cleaned up"
    assert out["first_ok"], "the held-open run was still released and completed in `finally`"


# ==================================================================================================================
# C4-R1-05  exact str elements
# ==================================================================================================================


def hostile_str_class(raiser):
    """A str subclass whose every observable method records that it ran and then raises ``raiser()``."""

    class HostileStr(str):
        def __repr__(self):
            HOSTILE.append("HostileStr.__repr__")
            raise raiser("SECRET-repr")

        def __str__(self):
            HOSTILE.append("HostileStr.__str__")
            raise raiser("SECRET-str")

        def __getitem__(self, item):
            HOSTILE.append("HostileStr.__getitem__")
            raise raiser("SECRET-slice")

        def __len__(self):
            HOSTILE.append("HostileStr.__len__")
            raise raiser("SECRET-len")

        def __eq__(self, other):
            HOSTILE.append("HostileStr.__eq__")
            raise raiser("SECRET-eq")

        __hash__ = str.__hash__

        def isidentifier(self):
            HOSTILE.append("HostileStr.isidentifier")
            return True

    return HostileStr


class BenignStr(str):
    pass


@pytest.mark.parametrize("value", ["FC2-1000001", "not-a-number"], ids=["canonical value", "invalid value"])
@pytest.mark.parametrize("raiser", RAISERS, ids=lambda r: r.__name__)
def test_r1_05_a_hostile_str_subclass_is_rejected_without_running_any_of_its_methods(raiser, value):
    element = hostile_str_class(raiser)(value)
    engine = ScriptedEngine()
    batch = numbers(2) + [element] + numbers(2, start=2_000_001)
    with pytest.raises(BatchInputError) as caught:
        run(BatchScheduler(engine).run(batch))
    message = str(caught.value)
    assert "[2]" in message and "<HostileStr>" in message, "reported by class name only"
    assert "SECRET" not in message and value not in message.split("[2]")[1]
    assert engine.calls == [], "all-or-nothing: the valid neighbours did not run either"


@pytest.mark.parametrize("value", ["FC2-1000001", "bad"], ids=["canonical value", "invalid value"])
def test_r1_05_a_benign_str_subclass_is_rejected_too_even_when_canonical(value):
    engine = ScriptedEngine()
    with pytest.raises(BatchInputError) as caught:
        run(BatchScheduler(engine).run(numbers(2) + [BenignStr(value)] + numbers(2, start=2_000_001)))
    assert "[2]" in str(caught.value) and "<BenignStr>" in str(caught.value)
    assert engine.calls == []


def test_r1_05_only_exact_str_objects_ever_reach_the_engine_and_the_results():
    engine = ScriptedEngine()
    batch = numbers(6)
    result = run(BatchScheduler(engine, BatchConfig(max_in_flight_items=2)).run(batch))
    assert engine.calls == batch
    assert all(type(n) is str for n in engine.calls)
    assert all(type(i.number) is str for i in result.items)
    assert all(type(n) is str for n in result.failed_numbers)


def test_r1_05_a_batch_of_exact_str_still_works_when_the_values_came_from_str_subclass_processing():
    """The documented remedy for a caller holding subclass instances: build exact ``str`` values upstream."""
    engine = ScriptedEngine()
    upstream = [BenignStr(n) for n in numbers(3)]
    result = run(BatchScheduler(engine).run([str.__str__(x) for x in upstream]))  # str.__str__ -> exact str copy
    assert [i.number for i in result.items] == numbers(3)
    assert all(type(i.number) is str for i in result.items)


def test_r1_05_many_invalid_subclasses_keep_the_message_bounded():
    with pytest.raises(BatchInputError) as caught:
        run(BatchScheduler(ScriptedEngine()).run([hostile_str_class(RuntimeError)("x" * 5000)] * 200))
    assert len(str(caught.value)) < 2000 and "200 element(s)" in str(caught.value)
