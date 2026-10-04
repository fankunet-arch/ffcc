"""P5-C1 §18（E15 纯逻辑部分）：取消不被吞掉、不被转换；governor 不泄漏；无遗留任务。
真实 ``invoke_source`` 的见证见 H-11。"""

from __future__ import annotations

import asyncio

import pytest

from _amane_scenarios import url_for
from fc2_amane_adapter._outcome import AdapterFailure
from fc2_amane_adapter._runtime import AdapterRuntime
from fc2_amane_adapter._settings import parse_settings
from support.amane_host_fakes import HANG, FakeRequestError, FakeSourceError, FakeWebClient

N = "FC2-4825061"
ALL = ("fc2db_net", "javdb", "av123")


def _hanging_client() -> FakeWebClient:
    client = FakeWebClient()
    for source_id in ALL:
        client.add(url_for(source_id, "4825061"), HANG)
    return client


def _assert_governor_idle(runtime: AdapterRuntime) -> None:
    snapshot = runtime.governor.snapshot()
    assert all(host.in_flight == 0 and host.waiting == 0 for host in snapshot.hosts), snapshot
    assert all(breaker.in_flight == 0 and breaker.half_open_probes_in_flight == 0 for breaker in snapshot.breakers), snapshot


def test_cancel_while_all_sources_hang_propagates_cancelled_error_and_leaks_nothing():
    async def scenario():
        client = _hanging_client()
        runtime = AdapterRuntime(parse_settings({}), client)
        task = asyncio.create_task(runtime.lookup(N, "fc2"))
        for _ in range(50):
            await asyncio.sleep(0)
            if client.in_flight == 3:
                break
        assert client.in_flight == 3
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert task.cancelled()
        await asyncio.sleep(0)
        assert client.in_flight == 0
        _assert_governor_idle(runtime)
        assert not [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]

    asyncio.run(scenario())


def test_caller_timeout_cancellation_is_a_timeout_not_a_source_failure():
    async def scenario():
        client = _hanging_client()
        runtime = AdapterRuntime(parse_settings({}), client)
        with pytest.raises(TimeoutError):
            async with asyncio.timeout(0.1):
                await runtime.lookup(N, "fc2")
        _assert_governor_idle(runtime)

    asyncio.run(scenario())


def test_cancellation_is_never_converted_into_an_adapter_failure():
    async def scenario():
        runtime = AdapterRuntime(parse_settings({}), _hanging_client())
        task = asyncio.create_task(runtime.lookup(N, "fc2"))
        await asyncio.sleep(0.05)
        task.cancel()
        results = await asyncio.gather(task, return_exceptions=True)
        assert len(results) == 1 and isinstance(results[0], asyncio.CancelledError)
        assert not isinstance(results[0], AdapterFailure)

    asyncio.run(scenario())


def test_source_deadline_is_a_timeout_failure_with_all_sources_released():
    async def scenario():
        client = _hanging_client()
        runtime = AdapterRuntime(parse_settings({"source_deadline_seconds": 0.05}), client)
        outcome = await runtime.lookup(N, "fc2")
        assert outcome == AdapterFailure(
            "timeout", "FC2 lookup failed: fc2db_net=source_deadline; javdb=source_deadline; av123=source_deadline"
        )
        assert client.in_flight == 0
        _assert_governor_idle(runtime)

    asyncio.run(scenario())


@pytest.mark.parametrize("fatal", [KeyboardInterrupt, SystemExit])
def test_fatal_exceptions_from_the_host_client_are_not_converted(fatal):
    client = FakeWebClient()
    client.add(url_for("javdb", "4825061"), fatal())
    runtime = AdapterRuntime(parse_settings({"sources": [{"id": "javdb"}]}), client)
    with pytest.raises(fatal):
        asyncio.run(runtime.lookup(N, "fc2"))
    _assert_governor_idle(runtime)


def test_a_spontaneous_host_cancelled_error_is_isolated_by_core_to_one_source():
    """宿主在没有请求取消时自发抛 CancelledError：Core 把该来源记为 ADAPTER_EXCEPTION，其它来源继续（继承）。"""

    async def scenario():
        client = FakeWebClient()
        client.add(url_for("fc2db_net", "4825061"), asyncio.CancelledError())
        client.add(url_for("javdb", "4825061"), FakeRequestError("network"))
        client.add(url_for("av123", "4825061"), FakeRequestError("network"))
        runtime = AdapterRuntime(
            parse_settings({}), client, request_error_types=(FakeRequestError,), source_error_types=(FakeSourceError,)
        )
        outcome = await runtime.lookup(N, "fc2")
        assert isinstance(outcome, AdapterFailure)
        assert "fc2db_net=adapter_exception" in outcome.detail and outcome.reason == "network"

    asyncio.run(scenario())
