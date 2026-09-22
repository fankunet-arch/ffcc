"""Circuit-breaker state machine (contract §6), driven through the governor with an injected fake clock.

Deterministic: breaker time is ``FakeClock`` (no ``sleep``, no wall clock); concurrency comes from explicit
interleaving points (``await asyncio.sleep(0)``), never from timing.
"""

from __future__ import annotations

import asyncio

import pytest

from fc2_metadata_core.models.source_result import SourceErrorKind, SourceResult, SourceStatus
from fc2_metadata_core.resource_control import (
    BreakerState,
    CircuitBreakerPolicy,
    HostKey,
    Observation,
    SourceResourceGovernor,
    circuit_open_result,
    observation_for,
)

from support.resource_fakes import failed, FakeClock, ok, run

N = "FC2-1234567"
SRC = "src"
HOST = HostKey("h.example", 443)
K = SourceErrorKind
S = SourceStatus

FAILURE_STATUSES = [S.BLOCKED, S.RATE_LIMITED, S.NETWORK_ERROR, S.PARSE_ERROR, S.INVALID_RESPONSE]
HEALTHY = [ok(SRC, N), failed(SRC, S.NOT_FOUND)]


def good() -> SourceResult:
    return ok(SRC, N)


def bad(status: SourceStatus = S.NETWORK_ERROR) -> SourceResult:
    return failed(SRC, status)


def make(threshold=3, duration=30.0, probes=1):
    clock = FakeClock()
    governor = SourceResourceGovernor(
        breaker=CircuitBreakerPolicy(failure_threshold=threshold, open_duration_seconds=duration, half_open_max_calls=probes),
        clock=clock,
    )
    return governor, clock


def snap(governor, source_id=SRC):
    return next(b for b in governor.snapshot().breakers if b.source_id == source_id)


def take(governor):
    admission = governor.admit(SRC, HOST)
    assert admission is not None, "expected admission"
    return admission


def observe(governor, result):
    """One whole source execution: admit, then record the final result."""
    admission = take(governor)
    governor.record_result(admission, result)
    return admission


def trip(governor, threshold=3):
    for _ in range(threshold):
        observe(governor, bad())
    assert snap(governor).state is BreakerState.OPEN


# ---- observation table (§6.1) -----------------------------------------------------------------------------------


def test_the_observation_table_is_exhaustive_over_every_status():
    for status in S:
        result = ok(SRC, N) if status is S.SUCCESS else failed(SRC, status)
        assert observation_for(result) in (Observation.HEALTHY, Observation.FAILURE)


@pytest.mark.parametrize("result", HEALTHY, ids=["success", "not_found"])
def test_success_and_not_found_are_healthy(result):
    assert observation_for(result) is Observation.HEALTHY


@pytest.mark.parametrize("status", FAILURE_STATUSES, ids=lambda s: s.value)
def test_every_operational_failure_status_is_a_failure(status):
    assert observation_for(bad(status)) is Observation.FAILURE


@pytest.mark.parametrize(
    "kind",
    [K.NETWORK_ERROR, K.TIMEOUT, K.CONNECTION_ERROR, K.DECODE_ERROR, K.REDIRECT_ERROR, K.SOURCE_DEADLINE],
    ids=lambda k: k.value,
)
def test_every_network_error_refinement_including_the_deadline_is_a_failure(kind):
    assert observation_for(failed(SRC, S.NETWORK_ERROR, error_kind=kind)) is Observation.FAILURE


@pytest.mark.parametrize(
    "kind",
    [K.INVALID_RESPONSE, K.HTTP_SERVER_ERROR, K.RESPONSE_TOO_LARGE, K.ADAPTER_EXCEPTION, K.RESULT_CONTRACT_MISMATCH],
    ids=lambda k: k.value,
)
def test_every_invalid_response_refinement_is_a_failure(kind):
    assert observation_for(failed(SRC, S.INVALID_RESPONSE, error_kind=kind)) is Observation.FAILURE


def test_circuit_open_is_the_breakers_own_answer_and_not_an_observation():
    assert observation_for(circuit_open_result(SRC)) is Observation.NONE


def test_the_decision_ignores_error_detail_text():
    """Same status/kind, wildly different text: the same observation (structured fields only)."""
    texts = ["", "blocked by cloudflare", "HTTP 503 Service Unavailable", "success", "NOT_FOUND", "circuit_open"]
    for text in texts:
        assert observation_for(failed(SRC, S.PARSE_ERROR, detail=text or "x")) is Observation.FAILURE
        assert observation_for(failed(SRC, S.NOT_FOUND, detail=text or "x")) is Observation.HEALTHY


# ---- CLOSED ------------------------------------------------------------------------------------------------------


def test_a_fresh_breaker_is_closed_at_epoch_zero():
    governor, _ = make()
    take(governor)
    shot = snap(governor)
    assert (shot.state, shot.epoch, shot.consecutive_failures, shot.times_opened) == (BreakerState.CLOSED, 0, 0, 0)
    assert shot.opened_at is None and shot.remaining_cooldown_seconds is None


@pytest.mark.parametrize("threshold", [1, 2, 3, 5])
def test_the_breaker_opens_exactly_at_the_threshold(threshold):
    governor, _ = make(threshold=threshold)
    for i in range(threshold - 1):
        observe(governor, bad())
        assert snap(governor).state is BreakerState.CLOSED
        assert snap(governor).consecutive_failures == i + 1
    observe(governor, bad())
    shot = snap(governor)
    assert (shot.state, shot.epoch, shot.times_opened) == (BreakerState.OPEN, 1, 1)


def test_a_healthy_observation_resets_the_consecutive_failure_count():
    governor, _ = make(threshold=3)
    for _ in range(5):
        observe(governor, bad())
        observe(governor, bad())
        observe(governor, good())  # never three in a row
    assert snap(governor).state is BreakerState.CLOSED and snap(governor).consecutive_failures == 0


def test_not_found_is_healthy_and_100_of_them_never_touch_the_breaker():
    governor, _ = make(threshold=3)
    observe(governor, bad())
    observe(governor, bad())
    for _ in range(100):
        observe(governor, failed(SRC, S.NOT_FOUND))
    shot = snap(governor)
    assert (shot.state, shot.consecutive_failures, shot.epoch, shot.times_opened) == (BreakerState.CLOSED, 0, 0, 0)


def test_100_consecutive_not_found_on_a_fresh_breaker_stay_closed_with_zero_failures():
    governor, _ = make(threshold=3)
    for _ in range(100):
        observe(governor, failed(SRC, S.NOT_FOUND))
    shot = snap(governor)
    assert (shot.state, shot.consecutive_failures, shot.in_flight) == (BreakerState.CLOSED, 0, 0)


@pytest.mark.parametrize("status", [S.BLOCKED, S.RATE_LIMITED, S.PARSE_ERROR, S.INVALID_RESPONSE, S.NETWORK_ERROR], ids=lambda s: s.value)
def test_threshold_consecutive_failures_of_each_status_open_the_breaker(status):
    governor, _ = make(threshold=3)
    for _ in range(3):
        observe(governor, bad(status))
    assert snap(governor).state is BreakerState.OPEN


def test_a_mix_of_failure_statuses_counts_together():
    governor, _ = make(threshold=3)
    for status in (S.BLOCKED, S.PARSE_ERROR, S.RATE_LIMITED):
        observe(governor, bad(status))
    assert snap(governor).state is BreakerState.OPEN


def test_unobserved_tickets_never_move_the_failure_count():
    governor, _ = make(threshold=2)
    observe(governor, bad())
    for _ in range(10):
        governor.release(take(governor))  # cancelled / fatal / not attempted: no observation
    observe(governor, circuit_open_result(SRC))  # not an observation either
    assert snap(governor).consecutive_failures == 1 and snap(governor).state is BreakerState.CLOSED
    observe(governor, bad())
    assert snap(governor).state is BreakerState.OPEN


# ---- OPEN --------------------------------------------------------------------------------------------------------


def test_an_open_breaker_rejects_until_the_cooldown_elapses():
    governor, clock = make(duration=30.0)
    trip(governor)
    for _ in range(3):
        assert governor.admit(SRC, HOST) is None
    clock.advance(29.999)
    assert governor.admit(SRC, HOST) is None
    assert snap(governor).state is BreakerState.OPEN
    assert snap(governor).remaining_cooldown_seconds == pytest.approx(0.001)
    clock.advance(0.001)  # exactly `open_duration` after opening -> the next admission probes
    probe = governor.admit(SRC, HOST)
    assert probe is not None and probe.is_probe
    assert snap(governor).state is BreakerState.HALF_OPEN


def test_rejections_take_no_state_and_no_ticket():
    governor, _ = make()
    trip(governor)
    before = snap(governor)
    for _ in range(50):
        assert governor.admit(SRC, HOST) is None
    assert snap(governor) == before
    assert before.in_flight == 0


def test_a_snapshot_never_mutates_state_an_expired_cooldown_reads_open_with_zero_remaining():
    governor, clock = make(duration=10.0)
    trip(governor)
    clock.advance(500)
    for _ in range(3):
        shot = snap(governor)
        assert (shot.state, shot.remaining_cooldown_seconds, shot.epoch) == (BreakerState.OPEN, 0.0, 1)


def test_the_cooldown_is_measured_by_the_injected_clock_from_the_moment_of_opening():
    governor, clock = make(duration=30.0)
    clock.advance(123.0)
    trip(governor)
    assert snap(governor).opened_at == clock.now
    clock.advance(10)
    assert snap(governor).remaining_cooldown_seconds == pytest.approx(20.0)


# ---- HALF_OPEN ---------------------------------------------------------------------------------------------------


def half_open(governor, clock, duration=30.0):
    trip(governor)
    clock.advance(duration)


def test_a_healthy_probe_closes_the_breaker_and_resets_the_counter():
    governor, clock = make()
    half_open(governor, clock)
    probe = governor.admit(SRC, HOST)
    assert probe.is_probe
    governor.record_result(probe, good())
    shot = snap(governor)
    assert (shot.state, shot.consecutive_failures, shot.half_open_probes_in_flight, shot.opened_at) == (
        BreakerState.CLOSED, 0, 0, None,
    )
    assert shot.epoch == 3  # CLOSED->OPEN (1) -> HALF_OPEN (2) -> CLOSED (3)
    observe(governor, bad())  # counting starts from zero again
    assert snap(governor).state is BreakerState.CLOSED and snap(governor).consecutive_failures == 1


def test_not_found_is_a_healthy_probe_and_closes_the_breaker():
    governor, clock = make()
    half_open(governor, clock)
    governor.record_result(governor.admit(SRC, HOST), failed(SRC, S.NOT_FOUND))
    assert snap(governor).state is BreakerState.CLOSED


@pytest.mark.parametrize("status", FAILURE_STATUSES, ids=lambda s: s.value)
def test_a_failed_probe_reopens_with_a_fresh_cooldown(status):
    governor, clock = make(duration=30.0)
    half_open(governor, clock)
    clock.advance(7)
    probe = governor.admit(SRC, HOST)
    governor.record_result(probe, bad(status))
    shot = snap(governor)
    assert (shot.state, shot.times_opened, shot.half_open_probes_in_flight) == (BreakerState.OPEN, 2, 0)
    assert shot.opened_at == clock.now  # the cooldown restarted *now*, not at the first opening
    assert governor.admit(SRC, HOST) is None
    clock.advance(29.9)
    assert governor.admit(SRC, HOST) is None
    clock.advance(0.1)
    assert governor.admit(SRC, HOST).is_probe


def test_only_half_open_max_calls_probes_are_admitted_the_rest_short_circuit():
    governor, clock = make(probes=2)
    half_open(governor, clock)
    probes = [governor.admit(SRC, HOST), governor.admit(SRC, HOST)]
    assert all(p is not None and p.is_probe for p in probes)
    assert snap(governor).half_open_probes_in_flight == 2
    assert governor.admit(SRC, HOST) is None
    assert governor.admit(SRC, HOST) is None
    governor.record_result(probes[0], good())  # closes
    assert snap(governor).state is BreakerState.CLOSED
    late = probes[1]
    governor.record_result(late, bad())  # a probe of the superseded HALF_OPEN epoch: discarded
    assert snap(governor).state is BreakerState.CLOSED and snap(governor).consecutive_failures == 0


def test_100_concurrent_lookups_after_the_cooldown_send_exactly_one_probe():
    governor, clock = make(probes=1)
    half_open(governor, clock)
    admissions = [governor.admit(SRC, HOST) for _ in range(100)]
    granted = [a for a in admissions if a is not None]
    assert len(granted) == 1 and granted[0].is_probe
    assert admissions.count(None) == 99
    assert snap(governor).half_open_probes_in_flight == 1 and snap(governor).in_flight == 1


@pytest.mark.parametrize("probes", [1, 2, 5, 16])
def test_the_probe_bound_holds_for_any_half_open_max_calls(probes):
    governor, clock = make(probes=probes)
    half_open(governor, clock)
    granted = [a for a in (governor.admit(SRC, HOST) for _ in range(200)) if a is not None]
    assert len(granted) == probes and all(a.is_probe for a in granted)


def test_a_cancelled_or_unobserved_probe_frees_its_slot_for_another_probe():
    governor, clock = make(probes=1)
    half_open(governor, clock)
    probe = governor.admit(SRC, HOST)
    assert governor.admit(SRC, HOST) is None  # slot taken
    governor.release(probe)  # cancelled: no observation
    assert snap(governor).state is BreakerState.HALF_OPEN
    assert snap(governor).half_open_probes_in_flight == 0 and snap(governor).in_flight == 0
    again = governor.admit(SRC, HOST)
    assert again is not None and again.is_probe
    governor.record_result(again, good())
    assert snap(governor).state is BreakerState.CLOSED


def test_a_circuit_open_result_recorded_for_a_probe_frees_the_slot_without_deciding():
    governor, clock = make(probes=1)
    half_open(governor, clock)
    probe = governor.admit(SRC, HOST)
    governor.record_result(probe, circuit_open_result(SRC))
    assert snap(governor).state is BreakerState.HALF_OPEN and snap(governor).half_open_probes_in_flight == 0


# ---- stale completion (§6.2) -------------------------------------------------------------------------------------


def test_a_late_success_from_before_the_breaker_opened_cannot_close_it():
    """The contract's example: A, B, C admitted; B and C fail and trip the breaker; A returns SUCCESS late."""
    governor, _ = make(threshold=2)
    a, b, c = take(governor), take(governor), take(governor)
    governor.record_result(b, bad())
    governor.record_result(c, bad())
    assert snap(governor).state is BreakerState.OPEN and snap(governor).epoch == 1
    governor.record_result(a, good())  # observation of epoch 0: stale
    shot = snap(governor)
    assert (shot.state, shot.epoch, shot.consecutive_failures, shot.times_opened) == (BreakerState.OPEN, 1, 2, 1)
    assert shot.in_flight == 0  # ... but its accounting was released
    assert governor.admit(SRC, HOST) is None  # still short-circuiting


def test_a_late_failure_from_before_the_opening_neither_extends_nor_double_counts():
    governor, clock = make(threshold=2, duration=30.0)
    a, b, c = take(governor), take(governor), take(governor)
    governor.record_result(b, bad())
    governor.record_result(c, bad())
    opened_at = snap(governor).opened_at
    clock.advance(20)
    governor.record_result(a, bad())  # stale failure
    shot = snap(governor)
    assert (shot.epoch, shot.times_opened, shot.opened_at, shot.consecutive_failures) == (1, 1, opened_at, 2)
    assert shot.remaining_cooldown_seconds == pytest.approx(10.0)  # the cooldown was not restarted


def test_a_late_success_cannot_close_a_half_open_breaker_or_steal_the_probe_verdict():
    governor, clock = make(threshold=2, duration=30.0)
    old = take(governor)  # admitted while CLOSED
    observe(governor, bad())
    observe(governor, bad())
    clock.advance(30)
    probe = governor.admit(SRC, HOST)
    assert snap(governor).state is BreakerState.HALF_OPEN
    governor.record_result(old, good())  # epoch 0 vs the HALF_OPEN epoch: stale
    assert snap(governor).state is BreakerState.HALF_OPEN and snap(governor).half_open_probes_in_flight == 1
    governor.record_result(probe, bad())  # the probe alone decides
    assert snap(governor).state is BreakerState.OPEN


def test_a_stale_failure_cannot_reopen_a_closed_breaker():
    governor, clock = make(threshold=2, duration=30.0)
    old = take(governor)
    observe(governor, bad())
    observe(governor, bad())  # OPEN
    clock.advance(30)
    governor.record_result(governor.admit(SRC, HOST), good())  # probe closes it
    assert snap(governor).state is BreakerState.CLOSED
    governor.record_result(old, bad())  # a failure that belongs to two epochs ago
    assert snap(governor).state is BreakerState.CLOSED and snap(governor).consecutive_failures == 0


def test_in_flight_calls_are_not_cancelled_when_the_breaker_opens_they_finish_and_only_new_admissions_short_circuit():
    governor, _ = make(threshold=3)
    tickets = [take(governor) for _ in range(5)]
    for ticket in tickets[:3]:
        governor.record_result(ticket, bad())
    assert snap(governor).state is BreakerState.OPEN
    assert snap(governor).in_flight == 2  # the two in-flight calls are still legitimately running
    assert governor.admit(SRC, HOST) is None  # a NEW admission short-circuits
    for ticket in tickets[3:]:
        governor.record_result(ticket, good())  # they finish normally ...
    assert snap(governor).state is BreakerState.OPEN and snap(governor).in_flight == 0  # ... without closing it


def test_epochs_are_monotone_across_a_full_cycle():
    governor, clock = make(threshold=1, duration=5.0)
    seen = [snap(governor).epoch] if governor.snapshot().breakers else [0]
    for _ in range(3):
        observe(governor, bad())
        seen.append(snap(governor).epoch)
        clock.advance(5)
        probe = governor.admit(SRC, HOST)
        seen.append(snap(governor).epoch)
        governor.record_result(probe, bad())
        seen.append(snap(governor).epoch)
        clock.advance(5)
        governor.record_result(governor.admit(SRC, HOST), good())
        seen.append(snap(governor).epoch)
    assert seen == sorted(seen) and len(set(seen)) == len(seen)


# ---- concurrency at await boundaries ------------------------------------------------------------------------------


def test_many_concurrent_failures_at_await_boundaries_open_the_breaker_exactly_once():
    async def main():
        governor, _ = make(threshold=3)
        gate = asyncio.Event()

        async def call():
            admission = governor.admit(SRC, HOST)
            assert admission is not None
            await gate.wait()  # all 50 are admitted before any completes
            await asyncio.sleep(0)
            governor.record_result(admission, bad())

        tasks = [asyncio.create_task(call()) for _ in range(50)]
        await asyncio.sleep(0)
        assert snap(governor).in_flight == 50
        gate.set()
        await asyncio.gather(*tasks)
        shot = snap(governor)
        # first three completions tripped it; the other 47 belong to the old epoch and were fenced off:
        assert (shot.state, shot.epoch, shot.times_opened, shot.consecutive_failures) == (BreakerState.OPEN, 1, 1, 3)
        assert shot.in_flight == 0

    run(main())


def test_interleaved_successes_and_failures_never_corrupt_the_counters():
    async def main():
        governor, _ = make(threshold=1000 // 10)
        gate = asyncio.Event()

        async def call(i):
            admission = governor.admit(SRC, HOST)
            await gate.wait()
            for _ in range(i % 3):
                await asyncio.sleep(0)
            governor.record_result(admission, good() if i % 2 else bad())

        tasks = [asyncio.create_task(call(i)) for i in range(60)]
        await asyncio.sleep(0)
        gate.set()
        await asyncio.gather(*tasks)
        shot = snap(governor)
        assert shot.in_flight == 0 and shot.consecutive_failures >= 0 and shot.half_open_probes_in_flight == 0
        assert shot.state is BreakerState.CLOSED  # 100-failure threshold never reached with alternating outcomes

    run(main())


def test_the_half_open_race_with_100_asyncio_callers_lets_exactly_one_through():
    async def main():
        governor, clock = make(probes=1)
        half_open(governor, clock)
        fetched = 0
        gate = asyncio.Event()

        async def lookup():
            nonlocal fetched
            admission = governor.admit(SRC, HOST)
            if admission is None:
                return "short-circuit"
            fetched += 1
            await gate.wait()
            governor.record_result(admission, good())
            return "probe"

        tasks = [asyncio.create_task(lookup()) for _ in range(100)]
        await asyncio.sleep(0)
        gate.set()
        outcomes = await asyncio.gather(*tasks)
        assert fetched == 1 and outcomes.count("probe") == 1 and outcomes.count("short-circuit") == 99
        assert snap(governor).state is BreakerState.CLOSED

    run(main())


# ---- domain isolation & diagnostics --------------------------------------------------------------------------------


def test_breakers_are_independent_per_source_id_even_on_the_same_host():
    governor, _ = make(threshold=2)
    for _ in range(2):
        governor.record_result(governor.admit("source_a", HOST), failed("source_a", S.PARSE_ERROR))
    assert governor.admit("source_a", HOST) is None
    healthy = governor.admit("source_b", HOST)  # same host, other source: unaffected
    assert healthy is not None
    governor.record_result(healthy, ok("source_b", N))
    states = {b.source_id: b.state for b in governor.snapshot().breakers}
    assert states == {"source_a": BreakerState.OPEN, "source_b": BreakerState.CLOSED}


def test_snapshots_are_sorted_immutable_values_and_hold_only_scalars():
    import dataclasses

    governor, _ = make()
    for source_id in ("zeta", "alpha", "mid"):
        governor.release(governor.admit(source_id, HOST))
    shots = governor.snapshot().breakers
    assert [b.source_id for b in shots] == ["alpha", "mid", "zeta"]
    with pytest.raises(dataclasses.FrozenInstanceError):
        shots[0].state = BreakerState.OPEN  # type: ignore[misc]
    for field in dataclasses.fields(shots[0]):
        value = getattr(shots[0], field.name)
        assert value is None or isinstance(value, (str, int, float, BreakerState)), field.name
    assert {f.name for f in dataclasses.fields(shots[0])} == {
        "source_id", "state", "consecutive_failures", "epoch", "in_flight", "half_open_probes_in_flight",
        "opened_at", "remaining_cooldown_seconds", "times_opened",
    }
