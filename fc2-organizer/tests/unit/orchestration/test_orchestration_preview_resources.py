"""P4-C8 S2: preview resource limits (contract sections 19.6.1-19.6.6; section 35 "resource limits").

Small configurations only (no large allocation). Budgets are derived from the case definition: every
film has exactly one poster of ``a`` bytes; NFO charges are the real rendered lengths observed on a
baseline run; ``R = image_policy.max_total_bytes``; item ``j`` is admitted iff
``A_nfo + sum(a for i < j) + R <= B``.
"""

from __future__ import annotations

import asyncio
import hashlib

import pytest

from fc2_metadata_core.batch import BatchConfig
from fc2_organizer.discovery import DiscoveredMediaItem
from fc2_organizer.images import AcquiredImage, ImageAcquisitionPolicy, ImageAcquisitionResult, ImageRole
from fc2_organizer.orchestration import (
    MAX_BATCH_ITEMS,
    MAX_ITEM_IMAGE_BYTES,
    BatchOrchestrator,
    IssueReason as R_,
    OrchestrationConfig,
    OrchestrationConfigError,
    OrchestrationIntegrityError,
    OrchestrationResourceLimitError,
    PreviewState as S,
    ResourceLimitReason,
)
from fc2_organizer.orchestration import preview as preview_module
from fc2_organizer.orchestration import stages

from support.batch_fakes import until

from ._fakes import ScriptedEngine, ScriptedImageClient, minimal_jpeg
from ._helpers import DOWNLOADS, LIBRARY, Corpus, Film, image_url, mutation_traps, run, tree_snapshot

A = len(minimal_jpeg())  # every scripted poster has exactly this many bytes


def _films(count: int) -> list[Film]:
    return [Film(f"FC2-PPV-{1000001 + i}.mp4", fanart=False, thumb=False) for i in range(count)]


def _numbers(count: int) -> list[str]:
    return [f"FC2-{1000001 + i}" for i in range(count)]


def _policy(r: int) -> ImageAcquisitionPolicy:
    return ImageAcquisitionPolicy(max_image_bytes=r, max_total_bytes=r)


def _config(budget: int, k: int = 1) -> OrchestrationConfig:
    return OrchestrationConfig(metadata=BatchConfig(max_in_flight_items=4), image_in_flight_items=k,
                               max_retained_artifact_bytes=budget)


def _nfo_charges(corpus: Corpus, monkeypatch) -> list[int]:
    """The real ``4 * len(nfo_text)`` charges, in index order, from a baseline run with the default budget."""
    lengths: list[int] = []
    real = stages.render_movie_nfo

    def recording(record):
        text = real(record)
        lengths.append(4 * len(text))
        return text

    monkeypatch.setattr(stages, "render_movie_nfo", recording)
    corpus.preview(corpus.orchestrator(image_policy=_policy(A)))
    monkeypatch.setattr(stages, "render_movie_nfo", real)
    corpus.client.calls.clear()
    corpus.client.peak = 0
    return lengths


def _expect_limit(orchestrator, items, reason=ResourceLimitReason.RETAINED_BYTES_LIMIT):
    with pytest.raises(OrchestrationResourceLimitError) as info:
        run(orchestrator.preview(items), timeout=20)
    error = info.value
    assert error.reason is reason and error.__cause__ is None and error.__context__ is None
    assert "http" not in str(error) and "\\" not in str(error) and "/" not in str(error)
    assert orchestrator._busy is False
    return error


# =========================================================================== construction / item count


def test_image_policy_cap_at_construction():
    at = ImageAcquisitionPolicy(max_total_bytes=MAX_ITEM_IMAGE_BYTES)
    assert BatchOrchestrator(ScriptedEngine(), ScriptedImageClient(), LIBRARY, image_policy=at).image_policy is at
    with pytest.raises(OrchestrationConfigError):
        BatchOrchestrator(ScriptedEngine(), ScriptedImageClient(), LIBRARY,
                          image_policy=ImageAcquisitionPolicy(max_total_bytes=MAX_ITEM_IMAGE_BYTES + 1))


def _tiny_items(count: int) -> list[DiscoveredMediaItem]:
    import os

    return [DiscoveredMediaItem(index=i, source_path=os.path.join(DOWNLOADS, f"clip{i}.mp4"),
                                relative_path=f"clip{i}.mp4", extension=".mp4", size=1) for i in range(count)]


def test_max_batch_items_is_accepted_end_to_end(monkeypatch):
    engine, client = ScriptedEngine(), ScriptedImageClient()
    orchestrator = BatchOrchestrator(engine, client, LIBRARY)
    trap = mutation_traps(monkeypatch)
    preview = run(orchestrator.preview(_tiny_items(MAX_BATCH_ITEMS)))
    assert trap.calls == [] and preview.batch_size == MAX_BATCH_ITEMS
    assert all(i.issue.reason is R_.NUMBER_NOT_RECOGNIZED for i in preview.items)
    assert engine.calls == [] and client.calls == []


def test_one_over_max_batch_items_fails_before_any_access(monkeypatch):
    engine, client = ScriptedEngine(), ScriptedImageClient()
    orchestrator = BatchOrchestrator(engine, client, LIBRARY)
    trap = mutation_traps(monkeypatch)
    items = _tiny_items(MAX_BATCH_ITEMS + 1)
    items[-1] = "not even an item"  # the limit wins over element validation
    _expect_limit(orchestrator, items, ResourceLimitReason.BATCH_ITEM_LIMIT)
    assert trap.calls == [] and engine.calls == [] and client.calls == []


# =========================================================================== byte budget


def test_b_exact_is_accepted_and_b_exact_minus_one_fails(tmp_path, monkeypatch):
    corpus = Corpus(tmp_path, _films(3))
    nfo = _nfo_charges(corpus, monkeypatch)
    r = 2 * A
    b_exact = sum(nfo) + 2 * A + r  # tightest admission is the last item (j = 2)
    before = tree_snapshot(tmp_path)
    for k in (1, 2, 4):
        preview = run(corpus.orchestrator(image_policy=_policy(r), config=_config(b_exact, k)).preview(corpus.items))
        assert all(i.state is S.READY for i in preview.items)
        assert preview.retention_budget_bytes == b_exact and preview.retained_artifact_bytes <= b_exact
        corpus.client.calls.clear()
        _expect_limit(corpus.orchestrator(image_policy=_policy(r), config=_config(b_exact - 1, k)), corpus.items)
        assert sorted(corpus.client.calls) == [image_url(n, "poster") for n in _numbers(2)]  # j = 2 never admitted
        corpus.client.calls.clear()
    assert tree_snapshot(tmp_path) == before


def test_nfo_over_budget_fails_before_any_image_request(tmp_path, monkeypatch):
    corpus = Corpus(tmp_path, _films(3))
    nfo = _nfo_charges(corpus, monkeypatch)
    for budget in (nfo[0] - 1, sum(nfo) - 1):
        _expect_limit(corpus.orchestrator(image_policy=_policy(A), config=_config(budget)), corpus.items)
        assert corpus.client.calls == []


def test_no_call_in_flight_fails_immediately_without_hanging(tmp_path, monkeypatch):
    corpus = Corpus(tmp_path, _films(2))
    nfo = _nfo_charges(corpus, monkeypatch)
    budget = sum(nfo) + A - 1  # R = A never fits, and nothing is in flight
    for k in (1, 4):
        _expect_limit(corpus.orchestrator(image_policy=_policy(A), config=_config(budget, k)), corpus.items)
        assert corpus.client.calls == []


class _RecordingLedger(preview_module._Ledger):
    instances: list["_RecordingLedger"] = []

    def __init__(self, limit: int) -> None:
        super().__init__(limit)
        _RecordingLedger.instances.append(self)


def test_k4_with_room_for_two_reservations_keeps_peak_two_and_ledger_within_b(tmp_path, monkeypatch):
    corpus = Corpus(tmp_path, _films(4))
    nfo = _nfo_charges(corpus, monkeypatch)
    r = 3 * A
    budget = sum(nfo) + 2 * r  # two reservations fit; every item is eventually admitted
    _RecordingLedger.instances.clear()
    monkeypatch.setattr(preview_module, "_Ledger", _RecordingLedger)
    observed: list[tuple[int, int]] = []
    for url, answer in list(corpus.client.script.items()):
        async def watched(_url, _answer=answer):
            ledger = _RecordingLedger.instances[-1]
            observed.append((ledger.charged + ledger.reserved, ledger.limit))
            await asyncio.sleep(0)
            return _answer
        corpus.client.script[url] = watched
    preview = run(corpus.orchestrator(image_policy=_policy(r), config=_config(budget, k=4)).preview(corpus.items))
    assert all(i.state is S.READY for i in preview.items)
    assert corpus.client.peak == 2
    assert observed and all(total <= limit for total, limit in observed)
    ledger = _RecordingLedger.instances[-1]
    assert ledger.reserved == 0 and ledger.charged == sum(nfo) + 4 * A <= budget


async def _run_reversed(corpus, orchestrator, gated: list[str]):
    """Hold the given poster requests and release them in reverse order."""
    for url in gated:
        corpus.client.gate(url)

    async def controller():
        await until(lambda: corpus.client.active == len(gated))
        for url in reversed(gated):
            done = len(corpus.client.completed)
            corpus.client.gates[url].set()
            await until(lambda: len(corpus.client.completed) > done)

    control = asyncio.ensure_future(controller())
    try:
        return await orchestrator.preview(corpus.items)
    finally:
        await asyncio.gather(control, return_exceptions=True)


def test_failure_index_is_the_same_for_every_k_and_completion_order(tmp_path, monkeypatch):
    corpus = Corpus(tmp_path, _films(5))
    nfo = _nfo_charges(corpus, monkeypatch)
    budget = sum(nfo) + 2 * A  # R = A: exactly two items fit, index 2 is the deterministic failure point
    admitted = [image_url(n, "poster") for n in _numbers(2)]
    outcomes = []
    for k in (1, 2, 4):
        corpus.client.calls.clear()
        _expect_limit(corpus.orchestrator(image_policy=_policy(A), config=_config(budget, k)), corpus.items)
        outcomes.append(sorted(corpus.client.calls))
    for k in (2, 4):
        corpus.client.calls.clear()
        corpus.client.completed.clear()
        with pytest.raises(OrchestrationResourceLimitError):
            run(_run_reversed(corpus, corpus.orchestrator(image_policy=_policy(A), config=_config(budget, k)),
                              admitted), timeout=20)
        assert corpus.client.completed == list(reversed(admitted))
        outcomes.append(sorted(corpus.client.calls))
        corpus.client.gates.clear()
    assert all(outcome == admitted for outcome in outcomes)


def test_image_result_above_the_reservation_is_an_item_error(tmp_path, monkeypatch):
    corpus = Corpus(tmp_path, _films(2))
    real_acquire = preview_module.acquire_images
    oversized = minimal_jpeg(pad=500)

    async def lying(record, client, *, policy=None):
        if record.plan.canonical_number == "FC2-1000001":
            image = AcquiredImage(role=ImageRole.POSTER, candidate_index=0, content=oversized, width=16, height=16,
                                  size_bytes=len(oversized), sha256=hashlib.sha256(oversized).hexdigest())
            return ImageAcquisitionResult(poster=image)
        return await real_acquire(record, client, policy=policy)

    monkeypatch.setattr(preview_module, "acquire_images", lying)
    preview = run(corpus.orchestrator(image_policy=_policy(A)).preview(corpus.items))
    bad, good = preview.items
    assert bad.state is S.UNPREPARED and bad.issue.reason is R_.IMAGE_ACQUISITION_ERROR
    assert bad.issue.error_type == "ImageAcquisitionResult" and bad.preflight is None
    assert good.state is S.READY
    assert preview.retained_artifact_bytes == sum(len(r.content) for r in good.preflight.artifacts)


def test_resource_failure_is_read_only_and_leaves_the_orchestrator_idle(tmp_path, monkeypatch):
    corpus = Corpus(tmp_path, _films(2))
    nfo = _nfo_charges(corpus, monkeypatch)
    orchestrator = corpus.orchestrator(image_policy=_policy(A), config=_config(sum(nfo) + A - 1))
    before = tree_snapshot(tmp_path)
    trap = mutation_traps(monkeypatch)
    _expect_limit(orchestrator, corpus.items)
    assert trap.calls == []
    monkeypatch.undo()
    assert tree_snapshot(tmp_path) == before
    roomy = corpus.orchestrator(image_policy=_policy(A))
    assert run(roomy.preview(corpus.items)).retention_budget_bytes == roomy.config.max_retained_artifact_bytes


# =========================================================================== S2-R1: payload lifetime vs. ledger transitions


def _held_by_a_coroutine(obj: object) -> bool:
    """``True`` while a suspended or running coroutine (e.g. the image worker) still references ``obj``."""
    import gc

    return any(type(referrer).__name__ == "coroutine" for referrer in gc.get_referrers(obj))


class _TransitionLedger(preview_module._Ledger):
    """Records every reservation release / conversion with the ledger state and the liveness of the payload
    the image worker is settling (the last object ``acquire_images`` returned)."""

    instances: list["_TransitionLedger"] = []
    produced: list[object] = []

    def __init__(self, limit: int) -> None:
        super().__init__(limit)
        self.events: list[tuple] = []
        _TransitionLedger.instances.append(self)

    def _settling_alive(self) -> bool:
        return bool(self.produced) and _held_by_a_coroutine(self.produced[-1])

    def release(self, reservation: int) -> None:
        self.events.append(("release", self.reserved, self.charged, self._settling_alive()))
        super().release(reservation)

    def convert(self, reservation: int, actual: int) -> None:
        before = (self.reserved, self.charged)
        super().convert(reservation, actual)
        self.events.append(("convert", before, (self.reserved, self.charged), actual))


def _instrument(monkeypatch, overrides: dict[str, object] | None = None):
    """Spy ledger + an ``acquire_images`` substitute that records every returned payload (and can replace or
    fail it per number) + a classification probe recording the reservation held at that moment."""
    _TransitionLedger.instances.clear()
    _TransitionLedger.produced.clear()
    monkeypatch.setattr(preview_module, "_Ledger", _TransitionLedger)
    overrides = overrides or {}
    real_acquire = preview_module.acquire_images
    admissions: list[bool] = []

    async def acquire(record, client, *, policy=None):
        # entering a new admission: no earlier rejected payload may still be held by a worker
        admissions.append(any(_held_by_a_coroutine(p) for p in _TransitionLedger.produced
                              if type(p) is not ImageAcquisitionResult or p.total_bytes > policy.max_total_bytes))
        override = overrides.get(record.plan.canonical_number)
        if isinstance(override, BaseException):
            raise override
        result = override if override is not None else await real_acquire(record, client, policy=policy)
        _TransitionLedger.produced.append(result)
        return result

    real_outcome = preview_module.image_outcome
    classified: list[int] = []

    def outcome(result, failure_type, reservation):
        classified.append(_TransitionLedger.instances[-1].reserved)
        return real_outcome(result, failure_type, reservation)

    monkeypatch.setattr(preview_module, "acquire_images", acquire)
    monkeypatch.setattr(preview_module, "image_outcome", outcome)
    return admissions, classified


def _oversized(size: int) -> ImageAcquisitionResult:
    content = minimal_jpeg(pad=size)
    image = AcquiredImage(role=ImageRole.POSTER, candidate_index=0, content=content, width=16, height=16,
                          size_bytes=len(content), sha256=hashlib.sha256(content).hexdigest())
    return ImageAcquisitionResult(poster=image)


def test_success_payload_stays_reserved_until_converted_in_one_step(tmp_path, monkeypatch):
    corpus = Corpus(tmp_path, _films(3))
    r = 2 * A
    admissions, classified = _instrument(monkeypatch)
    preview = run(corpus.orchestrator(image_policy=_policy(r), config=_config(10 ** 9, k=1)).preview(corpus.items))
    assert all(i.state is S.READY for i in preview.items)
    assert classified == [r, r, r]  # classification happens while the reservation is still held
    ledger = _TransitionLedger.instances[-1]
    assert [e[0] for e in ledger.events] == ["convert"] * 3  # never "released but not yet charged"
    for _, (reserved_before, charged_before), (reserved_after, charged_after), actual in ledger.events:
        assert actual == A and reserved_before == r and reserved_after == 0
        assert charged_after == charged_before + actual
    assert admissions == [False, False, False]
    assert ledger.reserved == 0


@pytest.mark.parametrize("invalid", ["oversized", "wrong-type"])
def test_rejected_payload_is_dropped_before_its_reservation_is_released(tmp_path, monkeypatch, invalid):
    corpus = Corpus(tmp_path, _films(3))
    r = 2 * A
    bad = _oversized(3 * A) if invalid == "oversized" else {"poster": b"x" * (3 * A)}
    assert invalid != "oversized" or bad.total_bytes > r
    admissions, classified = _instrument(monkeypatch, {"FC2-1000001": bad})
    preview = run(corpus.orchestrator(image_policy=_policy(r), config=_config(10 ** 9, k=1)).preview(corpus.items))
    first = preview.items[0]
    assert first.state is S.UNPREPARED and first.issue.reason is R_.IMAGE_ACQUISITION_ERROR
    assert first.preflight is None
    ledger = _TransitionLedger.instances[-1]
    kind, reserved_before, _charged_before, alive = ledger.events[0]
    assert kind == "release" and reserved_before == r and alive is False  # dropped first, then released
    assert [e[0] for e in ledger.events[1:]] == ["convert", "convert"]
    assert classified[0] == r
    assert admissions == [False, False, False]  # never alive across the next admission
    assert not _held_by_a_coroutine(bad)
    assert preview.retained_artifact_bytes == sum(len(a.content) for i in preview.items[1:]
                                                  for a in i.preflight.artifacts)


def test_ordinary_image_failure_releases_its_reservation(tmp_path, monkeypatch):
    corpus = Corpus(tmp_path, _films(2))
    r = 2 * A
    _instrument(monkeypatch, {"FC2-1000001": RuntimeError("scripted")})
    preview = run(corpus.orchestrator(image_policy=_policy(r), config=_config(10 ** 9, k=1)).preview(corpus.items))
    assert preview.items[0].issue.reason is R_.IMAGE_ACQUISITION_ERROR
    assert preview.items[0].issue.error_type == "RuntimeError" and preview.items[1].state is S.READY
    ledger = _TransitionLedger.instances[-1]
    assert [e[0] for e in ledger.events] == ["release", "convert"]
    assert ledger.events[0][1] == r and ledger.reserved == 0


@pytest.mark.parametrize("fatal", [KeyboardInterrupt(), SystemExit(1), asyncio.CancelledError()],
                         ids=["KeyboardInterrupt", "SystemExit", "self-cancelled"])
def test_fatal_releases_every_reservation(tmp_path, monkeypatch, fatal):
    corpus = Corpus(tmp_path, _films(3))
    r = 2 * A
    _instrument(monkeypatch)
    orchestrator = corpus.orchestrator(image_policy=_policy(r), config=_config(10 ** 9, k=2))
    failing, sibling = image_url("FC2-1000001", "poster"), image_url("FC2-1000002", "poster")
    corpus.client.script[failing] = fatal

    observed: list[int] = []

    async def scenario():
        release = corpus.client.gate(failing)
        corpus.client.gate(sibling)

        async def controller():
            await until(lambda: corpus.client.active == 2)
            observed.append(_TransitionLedger.instances[-1].reserved)
            release.set()

        control = asyncio.ensure_future(controller())
        # awaited in this task (never a separate one): the fatal object must reach pytest.raises here
        with pytest.raises(BaseException) as info:
            await orchestrator.preview(corpus.items)
        await control
        assert info.value is fatal

    run(scenario())
    assert observed == [2 * r]  # both reservations held while both calls were in flight
    ledger = _TransitionLedger.instances[-1]
    assert ledger.reserved == 0 and [e[0] for e in ledger.events] == ["release", "release"]


def test_caller_cancellation_releases_every_reservation(tmp_path, monkeypatch):
    corpus = Corpus(tmp_path, _films(3))
    r = 2 * A
    _instrument(monkeypatch)
    orchestrator = corpus.orchestrator(image_policy=_policy(r), config=_config(10 ** 9, k=2))

    async def scenario():
        for number in _numbers(2):
            corpus.client.gate(image_url(number, "poster"))
        task = asyncio.ensure_future(orchestrator.preview(corpus.items))
        await until(lambda: corpus.client.active == 2)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    run(scenario())
    ledger = _TransitionLedger.instances[-1]
    assert ledger.reserved == 0 and [e[0] for e in ledger.events] == ["release", "release"]
    assert orchestrator._busy is False


# =========================================================================== S2-R2: ledger "always" invariant


class _LedgerTracer:
    """Test-only ``sys.settrace`` observer: inside every ``_Ledger`` method it records the ledger state after
    each executed line (and at return), i.e. every state the object ever holds mid-transition."""

    def __init__(self) -> None:
        self.states: list[tuple[int, int, int]] = []  # (charged, reserved, limit)
        functions = [v for v in vars(preview_module._Ledger).values() if callable(v)]
        functions += [v.fget for v in vars(preview_module._Ledger).values() if isinstance(v, property)]
        self.codes = {f.__code__ for f in functions if hasattr(f, "__code__")}

    def _record(self, frame) -> None:
        ledger = frame.f_locals.get("self")
        if isinstance(ledger, preview_module._Ledger):
            try:
                state = object.__getattribute__(ledger, "_state")
            except AttributeError:
                return  # inside __init__, before the first state exists
            charged, reserved = state
            self.states.append((charged, reserved, ledger.limit))

    def _local(self, frame, event, arg):
        if event in ("line", "return"):
            self._record(frame)
        return self._local

    def _global(self, frame, event, arg):
        if event == "call" and frame.f_code in self.codes:
            return self._local
        return None

    def __enter__(self):
        import sys

        self._previous = sys.gettrace()
        sys.settrace(self._global)
        return self

    def __exit__(self, *exc):
        import sys

        sys.settrace(self._previous)
        return False

    def assert_always_within_limit(self) -> None:
        assert self.states, "the tracer observed nothing"
        for charged, reserved, limit in self.states:
            assert charged >= 0 and reserved >= 0 and charged + reserved <= limit, (charged, reserved, limit)


def _ledger(limit: int, charged: int = 0, reserved: int = 0):
    ledger = preview_module._Ledger(limit)
    if charged:
        assert ledger.charge(charged)
    if reserved:
        assert ledger.try_reserve(reserved)
    return ledger


def test_ledger_state_is_one_indivisible_pair_with_read_only_views():
    ledger = _ledger(100, 10, 20)
    assert preview_module._Ledger.__slots__ == ("limit", "_state")
    assert type(ledger._state) is tuple and ledger._state == (10, 20)
    assert (ledger.charged, ledger.reserved) == (10, 20)
    for name in ("charged", "reserved"):
        descriptor = vars(preview_module._Ledger)[name]
        assert isinstance(descriptor, property) and descriptor.fset is None
        with pytest.raises(AttributeError):
            setattr(ledger, name, 0)
    assert ledger._state == (10, 20)


def test_reserve_success_and_failure_leave_valid_states():
    ledger = _ledger(100, 30)
    with _LedgerTracer() as tracer:
        assert ledger.try_reserve(70) is True  # exactly at the limit
        assert ledger.try_reserve(1) is False  # does not fit: unchanged
        assert ledger.try_reserve(0) is False and ledger.try_reserve(True) is False
    assert ledger._state == (30, 70)
    tracer.assert_always_within_limit()


def test_nfo_charge_success_and_over_limit_leave_the_state_unchanged():
    ledger = _ledger(100)
    with _LedgerTracer() as tracer:
        assert ledger.charge(60) is True
        assert ledger.charge(41) is False  # would exceed: refused, nothing written
        assert ledger.charge(-1) is False
    assert ledger._state == (60, 0)
    tracer.assert_always_within_limit()


def test_release_transition():
    ledger = _ledger(100, 10, 50)
    with _LedgerTracer() as tracer:
        ledger.release(50)
    assert ledger._state == (10, 0)
    tracer.assert_always_within_limit()


def test_convert_at_a_full_ledger_is_one_step_without_over_limit_or_uncovered_states():
    r, actual, charged = 40, 25, 60
    ledger = _ledger(charged + r, charged, r)  # L == limit before the conversion
    before = ledger._state
    with _LedgerTracer() as tracer:
        ledger.convert(r, actual)
    after = ledger._state
    assert before == (charged, r) and after == (charged + actual, 0)
    tracer.assert_always_within_limit()
    # every state the object held during the transition is the complete old one or the complete new one
    assert {(c, res) for c, res, _ in tracer.states} <= {before, after}


def test_double_release_fails_closed():
    ledger = _ledger(100, 0, 30)
    ledger.release(30)
    with pytest.raises(OrchestrationIntegrityError) as info:
        ledger.release(30)
    assert info.value.__context__ is None and ledger._state == (0, 0)


def test_actual_above_the_reservation_fails_closed():
    ledger = _ledger(100, 0, 30)
    with pytest.raises(OrchestrationIntegrityError):
        ledger.convert(30, 31)
    assert ledger._state == (0, 30)


def test_converting_more_than_is_reserved_fails_closed():
    ledger = _ledger(100, 0, 20)
    with pytest.raises(OrchestrationIntegrityError):
        ledger.convert(30, 10)
    with pytest.raises(OrchestrationIntegrityError):
        ledger.release(30)
    assert ledger._state == (0, 20)


def test_every_ledger_state_of_a_tight_preview_stays_within_the_budget(tmp_path, monkeypatch):
    corpus = Corpus(tmp_path, _films(4))
    nfo = _nfo_charges(corpus, monkeypatch)
    r = 3 * A
    budget = sum(nfo) + 2 * r  # two reservations fit at a time
    with _LedgerTracer() as tracer:
        preview = run(corpus.orchestrator(image_policy=_policy(r), config=_config(budget, k=4)).preview(corpus.items))
    assert all(i.state is S.READY for i in preview.items)
    tracer.assert_always_within_limit()
    assert max(c + res for c, res, _ in tracer.states) <= budget
