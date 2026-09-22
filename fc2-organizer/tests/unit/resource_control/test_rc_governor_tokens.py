"""Governor tickets, host permits and diagnostics (contract §6.2, §11)."""

from __future__ import annotations

import asyncio
import dataclasses

import pytest

from fc2_metadata_core.models.source_result import SourceStatus
from fc2_metadata_core.resource_control import (
    BreakerState,
    CircuitBreakerPolicy,
    HostKey,
    HostLimitPolicy,
    ResourceControlConfigError,
    ResourceControlError,
    SourceAdmission,
    SourceResourceGovernor,
)

from support.resource_fakes import failed, FakeClock, ok, run, until

N = "FC2-1234567"
A = HostKey("a.example", 443)
B = HostKey("b.example", 443)


def gov(**kw):
    return SourceResourceGovernor(clock=FakeClock(), **kw)




# ---- construction ------------------------------------------------------------------------------------------------


def test_constructor_validates_its_arguments():
    for kw in ({"host_limits": 4}, {"host_limits": None}, {"breaker": {"failure_threshold": 3}}, {"breaker": 3}, {"clock": 5}):
        with pytest.raises(ResourceControlConfigError):
            SourceResourceGovernor(**kw)  # type: ignore[arg-type]
    assert SourceResourceGovernor().host_limits == HostLimitPolicy()
    assert SourceResourceGovernor().breaker_policy == CircuitBreakerPolicy()


def test_two_governors_never_share_state():
    g1, g2 = gov(breaker=CircuitBreakerPolicy(failure_threshold=1)), gov(breaker=CircuitBreakerPolicy(failure_threshold=1))
    g1.record_result(g1.admit("s", A), failed("s", SourceStatus.BLOCKED))
    assert g1.admit("s", A) is None
    assert g2.admit("s", A) is not None  # the other domain is untouched


# ---- tickets ------------------------------------------------------------------------------------------------------


def test_callers_cannot_construct_a_ticket():
    governor = gov()
    with pytest.raises(TypeError):
        SourceAdmission(object(), governor, "s", A, 0, False)
    with pytest.raises(TypeError):
        SourceAdmission(None, governor, "s", A, 0, False)  # type: ignore[arg-type]


def test_ticket_carries_source_host_and_kind_read_only():
    governor = gov()
    ticket = governor.admit("s", A)
    assert (ticket.source_id, ticket.host, ticket.is_probe, ticket.settled) == ("s", A, False, False)
    for name in ("source_id", "host", "is_probe", "settled"):
        with pytest.raises(AttributeError):
            setattr(ticket, name, 1)
    assert not hasattr(ticket, "__dict__")  # slots only: no side channel


def test_a_ticket_of_another_governor_is_refused_everywhere():
    g1, g2 = gov(), gov()
    foreign = g1.admit("s", A)
    result = ok("s", N)
    with pytest.raises(ResourceControlError):
        g2.record_result(foreign, result)
    with pytest.raises(ResourceControlError):
        g2.release(foreign)
    with pytest.raises(ResourceControlError):
        g2.is_current(foreign)
    with pytest.raises(ResourceControlError):
        run(g2.acquire_host_permit(foreign))
    assert g1.snapshot().breakers[0].in_flight == 1 and not g2.snapshot().breakers  # neither side was touched
    g1.record_result(foreign, result)


@pytest.mark.parametrize("junk", [None, 0, "ticket", object(), (), {}])
def test_junk_instead_of_a_ticket_is_refused(junk):
    governor = gov()
    for call in (
        lambda: governor.record_result(junk, ok("s", N)),
        lambda: governor.release(junk),
        lambda: governor.is_current(junk),
        lambda: run(governor.acquire_host_permit(junk)),
    ):
        with pytest.raises(ResourceControlError):
            call()


def test_recording_twice_is_an_error_but_release_after_settling_is_a_safe_no_op():
    governor = gov(breaker=CircuitBreakerPolicy(failure_threshold=2))
    ticket = governor.admit("s", A)
    governor.record_result(ticket, failed("s", SourceStatus.BLOCKED))
    with pytest.raises(ResourceControlError):
        governor.record_result(ticket, failed("s", SourceStatus.BLOCKED))  # must not double-count
    governor.release(ticket)
    governor.release(ticket)
    shot = governor.snapshot().breakers[0]
    assert (shot.consecutive_failures, shot.in_flight) == (1, 0)
    with pytest.raises(ResourceControlError):
        governor.is_current(ticket)
    with pytest.raises(ResourceControlError):
        run(governor.acquire_host_permit(ticket))


def test_release_twice_never_makes_in_flight_negative():
    governor = gov()
    ticket = governor.admit("s", A)
    for _ in range(5):
        governor.release(ticket)
    assert governor.snapshot().breakers[0].in_flight == 0


def test_record_result_rejects_a_non_result_and_a_result_of_another_source():
    governor = gov()
    ticket = governor.admit("s", A)
    for junk in (None, "success", 1, object()):
        with pytest.raises(ResourceControlError):
            governor.record_result(ticket, junk)  # type: ignore[arg-type]
    with pytest.raises(ResourceControlError):
        governor.record_result(ticket, ok("other", N))
    assert not ticket.settled and governor.snapshot().breakers[0].in_flight == 1
    governor.release(ticket)


@pytest.mark.parametrize("source_id", ["", None, 5, b"s"])
def test_admit_validates_its_arguments(source_id):
    with pytest.raises(ResourceControlError):
        gov().admit(source_id, A)  # type: ignore[arg-type]
    with pytest.raises(ResourceControlError):
        gov().admit("s", "a.example:443")  # type: ignore[arg-type]


def test_is_current_reflects_a_breaker_that_changed_epoch():
    governor = gov(breaker=CircuitBreakerPolicy(failure_threshold=2))
    early = governor.admit("s", A)
    for _ in range(2):
        governor.record_result(governor.admit("s", A), failed("s", SourceStatus.PARSE_ERROR))
    assert governor.is_current(early) is False
    governor.release(early)
    fresh_governor = gov()
    assert fresh_governor.is_current(fresh_governor.admit("s", A)) is True


# ---- host permits through the governor --------------------------------------------------------------------------------


def test_per_host_limits_and_overrides_apply_and_hosts_are_independent():
    async def main():
        governor = gov(host_limits=HostLimitPolicy.create(1, {"a.example:443": 2, "b.example:443": 3}))
        held = []
        for host, count in ((A, 2), (B, 3)):
            for _ in range(count):
                ticket = governor.admit(f"s-{host.host}", host)
                held.append(await governor.acquire_host_permit(ticket))
        shots = {s.host: s for s in governor.snapshot().hosts}
        assert (shots[A].in_flight, shots[B].in_flight) == (2, 3)
        # the next request on either host must queue, without blocking the other host
        extra_a = asyncio.create_task(governor.acquire_host_permit(governor.admit("s-a.example", A)))
        await until(lambda: {s.host: s.waiting for s in governor.snapshot().hosts}[A] == 1)
        extra_c = await governor.acquire_host_permit(governor.admit("s-c", HostKey("c.example", 443)))  # default limit 1
        assert not extra_a.done()
        held[0].release()
        held.append(await extra_a)
        for permit in held + [extra_c]:
            permit.release()
        assert all(s.in_flight == 0 and s.waiting == 0 for s in governor.snapshot().hosts)

    run(main())


def test_the_permit_can_be_taken_after_the_breaker_admission_and_is_independent_of_the_epoch():
    async def main():
        governor = gov(breaker=CircuitBreakerPolicy(failure_threshold=1))
        ticket = governor.admit("s", A)
        governor.record_result(governor.admit("s", A), failed("s", SourceStatus.BLOCKED))  # opens
        permit = await governor.acquire_host_permit(ticket)  # the queue wait itself is not fenced ...
        assert governor.is_current(ticket) is False  # ... the caller must re-check (contract §7 step 3)
        permit.release()
        governor.release(ticket)

    run(main())


def test_snapshot_is_immutable_deterministic_and_bounded_to_hosts_and_sources():
    async def main():
        governor = gov()
        for i in range(500):  # 500 lookups over 2 hosts and 2 sources ...
            source_id, host = ("s1", A) if i % 2 else ("s2", B)
            ticket = governor.admit(source_id, host)
            (await governor.acquire_host_permit(ticket)).release()
            governor.record_result(ticket, ok(source_id, N))
        shot = governor.snapshot()
        assert [h.host for h in shot.hosts] == [A, B] and [b.source_id for b in shot.breakers] == ["s1", "s2"]
        assert len(shot.hosts) == 2 and len(shot.breakers) == 2  # ... leave O(hosts + sources) state
        assert governor.snapshot() == shot
        with pytest.raises(dataclasses.FrozenInstanceError):
            shot.hosts = ()  # type: ignore[misc]
        assert isinstance(shot.hosts, tuple) and isinstance(shot.breakers, tuple)
        host_fields = {f.name for f in dataclasses.fields(shot.hosts[0])}
        assert host_fields == {"host", "limit", "in_flight", "waiting", "peak_in_flight"}
        assert shot.hosts[0].peak_in_flight == 1

    run(main())


def test_breaker_state_enum_is_the_documented_three_states():
    assert {s.name for s in BreakerState} == {"CLOSED", "OPEN", "HALF_OPEN"}
