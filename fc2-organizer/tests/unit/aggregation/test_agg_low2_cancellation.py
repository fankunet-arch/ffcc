"""C1 review LOW-2: BaseException / cancellation semantics (frozen at C2).

* Caller cancellation -> ``CancelledError`` propagates unchanged, siblings are cancelled,
  no background task is left behind.
* An adapter *itself* raising ``CancelledError`` (nobody cancelled the aggregate) is a
  misbehaving adapter: that source -> INVALID_RESPONSE / ADAPTER_EXCEPTION, the rest continue.
* ``KeyboardInterrupt`` / ``SystemExit`` / ``GeneratorExit`` / any custom ``BaseException``
  are fatal control flow: the ORIGINAL exception object reaches the caller (identity check),
  never a ``BaseExceptionGroup``, never a source result.
* Known limitation (documented, not "solved"): an adapter that swallows ``CancelledError``
  cannot be interrupted by ``asyncio.timeout``; the three adopted adapters do not swallow it.
"""

from __future__ import annotations

import ast
import asyncio
import time
from pathlib import Path

import pytest

from fc2_metadata_core.aggregation import (
    AggregateStatus,
    AggregationConfig,
    MultiSourceEngine,
    RetryPolicy,
    SourceConfig,
    SourceTarget,
    execute_sources,
    execute_sources_traced,
)
from fc2_metadata_core.models.source_result import SourceErrorKind, SourceStatus
from fc2_metadata_core.sources import SourceRegistry
from fc2_metadata_core.sources.adapters.av123 import Av123Adapter
from fc2_metadata_core.sources.adapters.fc2db_net import Fc2dbNetAdapter
from fc2_metadata_core.sources.adapters.javdb import JavdbAdapter

from support.fake_http_client import FakeHttpClient
from support.scripted_adapters import failed, ok, scripted_adapter_class

N = "FC2-4979299"
CLIENT = object()
FAST = RetryPolicy(max_attempts=2, initial_backoff_seconds=0.01)


def target(source_id, script, *, deadline=20.0, retry=FAST):
    return SourceTarget(SourceConfig(source_id, deadline_seconds=deadline), scripted_adapter_class(source_id, script)(), retry)


async def good(number, client):
    return ok("good", number, "Good")


async def hang(number, client):
    await asyncio.Event().wait()


def run(coro):
    return asyncio.run(coro)


# ---- adapter-originated CancelledError ------------------------------------------------------------------------------


def test_an_adapter_raising_cancelled_error_on_its_own_is_isolated_and_the_others_continue():
    async def self_cancel(number, client):
        raise asyncio.CancelledError("secret-token=abc123")

    traces = run(execute_sources_traced(N, [target("bad", self_cancel), target("good", good)], CLIENT))
    bad, fine = traces
    assert bad.final_result.status is SourceStatus.INVALID_RESPONSE
    assert bad.final_result.error_kind is SourceErrorKind.ADAPTER_EXCEPTION
    assert "bad" in bad.final_result.error_detail and "CancelledError" in bad.final_result.error_detail
    assert "secret-token" not in bad.final_result.error_detail and "abc123" not in bad.final_result.error_detail
    assert bad.attempt_count == 1, "a misbehaving adapter is never retried"
    assert fine.final_result.status is SourceStatus.SUCCESS


def test_the_aggregate_survives_an_adapter_that_cancels_itself():
    async def self_cancel(number, client):
        raise asyncio.CancelledError()

    registry = SourceRegistry()
    registry.register("bad", scripted_adapter_class("bad", self_cancel))
    registry.register("good", scripted_adapter_class("good", good))
    config = AggregationConfig.create([SourceConfig("bad"), SourceConfig("good")])

    async def scenario():
        engine = MultiSourceEngine(config, registry, FakeHttpClient())
        return await engine.aggregate(N)

    result = run(scenario())  # must return normally: nobody cancelled the aggregate
    assert result.status is AggregateStatus.PARTIAL and result.metadata.title == "Good"
    assert result.result_for("bad").error_kind is SourceErrorKind.ADAPTER_EXCEPTION


def test_cancelled_error_raised_after_partial_work_is_still_isolated():
    async def late_self_cancel(number, client):
        await asyncio.sleep(0.02)
        raise asyncio.CancelledError()

    bad, fine = run(execute_sources(N, [target("bad", late_self_cancel), target("good", good)], CLIENT))
    assert bad.status is SourceStatus.INVALID_RESPONSE and fine.status is SourceStatus.SUCCESS


# ---- caller cancellation -----------------------------------------------------------------------------------------------


def test_caller_cancellation_propagates_original_cancelled_error_cancels_siblings_and_leaves_no_task():
    cancelled: list[str] = []

    def hanging(source_id):
        async def script(number, client):
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                cancelled.append(source_id)
                raise

        return script

    async def scenario():
        before = asyncio.all_tasks()
        task = asyncio.create_task(
            execute_sources_traced(N, [target("a", hanging("a")), target("b", hanging("b")), target("c", good)], CLIENT)
        )
        await asyncio.sleep(0.1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert task.cancelled()
        await asyncio.sleep(0)
        assert asyncio.all_tasks() <= before | {asyncio.current_task()}, "a background task outlived the cancelled call"

    run(scenario())
    assert sorted(cancelled) == ["a", "b"]


def test_cancellation_during_an_attempt_is_not_retried():
    calls = []

    async def slow_transient(number, client):
        calls.append(1)
        await asyncio.sleep(5)

    async def scenario():
        task = asyncio.create_task(execute_sources(N, [target("a", slow_transient)], CLIENT))
        await asyncio.sleep(0.1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    run(scenario())
    assert calls == [1], "cancellation must not start attempt 2"


def test_cancellation_during_backoff_does_not_start_the_next_attempt():
    calls = []

    async def transient_then_fine(number, client):
        calls.append(1)
        return failed("a", SourceStatus.NETWORK_ERROR, error_kind=SourceErrorKind.TIMEOUT)

    slow_backoff = RetryPolicy(max_attempts=3, initial_backoff_seconds=30.0, max_backoff_seconds=30.0)

    async def scenario():
        task = asyncio.create_task(
            execute_sources_traced(N, [target("a", transient_then_fine, retry=slow_backoff), target("b", good)], CLIENT)
        )
        await asyncio.sleep(0.15)  # attempt 1 done, now sleeping in the 30 s backoff
        assert len(calls) == 1
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    started = time.monotonic()
    run(scenario())
    assert time.monotonic() - started < 3, "cancellation must interrupt the backoff sleep"
    assert calls == [1], "cancellation during backoff must not run attempt 2"


def test_cancellation_is_never_converted_into_a_retryable_failure_or_source_result():
    async def scenario():
        engine_task = asyncio.create_task(execute_sources_traced(N, [target("h", hang, retry=RetryPolicy(max_attempts=5, initial_backoff_seconds=0))], CLIENT))
        await asyncio.sleep(0.05)
        engine_task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await engine_task

    run(scenario())


def test_engine_aggregate_cancellation_propagates_and_no_partial_result_is_returned():
    registry = SourceRegistry()
    registry.register("h", scripted_adapter_class("h", hang))
    config = AggregationConfig.create([SourceConfig("h")])

    async def scenario():
        engine = MultiSourceEngine(config, registry, FakeHttpClient())
        task = asyncio.create_task(engine.aggregate(N))
        await asyncio.sleep(0.05)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    run(scenario())


# ---- fatal BaseException: the ORIGINAL object, unwrapped ------------------------------------------------------------------


class CustomFatal(BaseException):
    """A project-unknown non-Exception BaseException."""


@pytest.mark.parametrize("exc_factory", [KeyboardInterrupt, SystemExit, GeneratorExit, CustomFatal], ids=lambda f: f.__name__)
def test_fatal_base_exceptions_reach_the_caller_as_the_original_object(exc_factory):
    instance = exc_factory("boom")

    async def raises(number, client):
        raise instance

    with pytest.raises(BaseException) as info:
        run(execute_sources_traced(N, [target("x", raises), target("good", good)], CLIENT))
    assert info.value is instance, f"expected the original {exc_factory.__name__} object, got {info.value!r}"
    assert not isinstance(info.value, BaseExceptionGroup)


@pytest.mark.parametrize("exc_factory", [KeyboardInterrupt, SystemExit, GeneratorExit, CustomFatal], ids=lambda f: f.__name__)
def test_a_fatal_exception_is_never_turned_into_a_source_result_and_siblings_are_cancelled(exc_factory):
    cancelled = []

    async def raises(number, client):
        await asyncio.sleep(0.05)
        raise exc_factory()

    async def sibling(number, client):
        try:
            await asyncio.sleep(5)
        except asyncio.CancelledError:
            cancelled.append(True)
            raise

    with pytest.raises(BaseException) as info:
        run(execute_sources_traced(N, [target("x", raises), target("sib", sibling)], CLIENT))
    assert type(info.value) is exc_factory
    assert cancelled == [True], "the sibling must be cancelled before the fatal exception is re-raised"


def test_a_fatal_exception_in_the_engine_propagates_unwrapped_too():
    instance = CustomFatal("engine")

    async def raises(number, client):
        raise instance

    registry = SourceRegistry()
    registry.register("x", scripted_adapter_class("x", raises))
    config = AggregationConfig.create([SourceConfig("x")])

    async def scenario():
        return await MultiSourceEngine(config, registry, FakeHttpClient()).aggregate(N)

    with pytest.raises(CustomFatal) as info:
        run(scenario())
    assert info.value is instance


def test_ordinary_exceptions_are_still_isolated_not_fatal():
    async def raises(number, client):
        raise RuntimeError("secret")

    bad, fine = run(execute_sources(N, [target("bad", raises), target("good", good)], CLIENT))
    assert bad.error_kind is SourceErrorKind.ADAPTER_EXCEPTION and fine.status is SourceStatus.SUCCESS


# ---- documented limitation: an adapter that SWALLOWS cancellation ----------------------------------------------------------


def test_documented_limitation_an_adapter_that_swallows_cancellation_cannot_be_interrupted():
    """NOT solved in C2 (no thread/process isolation). If a plugin adapter catches and swallows
    CancelledError and keeps going, ``asyncio.timeout`` cannot stop it; its own result is used
    when it eventually returns. This test pins the *current* behaviour so a change is deliberate."""

    async def swallower(number, client):
        try:
            await asyncio.sleep(5)
        except asyncio.CancelledError:
            pass  # the misbehaviour
        await asyncio.sleep(0.2)
        return ok("swallow", number, "late result")

    started = time.monotonic()
    (result,) = run(execute_sources(N, [target("swallow", swallower, deadline=0.1)], CLIENT))
    assert time.monotonic() - started >= 0.25, "the deadline could not interrupt the swallowing adapter"
    assert result.status is SourceStatus.SUCCESS and result.metadata.title == "late result"


# ---- the adopted adapters do not swallow cancellation ---------------------------------------------------------------------------


class HangingClient:
    """A SourceHttpClient whose get never returns (until cancelled)."""

    def __init__(self):
        self.calls = 0

    async def get(self, url, *, headers=None, timeout=None):
        self.calls += 1
        await asyncio.Event().wait()


@pytest.mark.parametrize("adapter_cls", [Fc2dbNetAdapter, JavdbAdapter, Av123Adapter], ids=lambda c: c.source_id)
def test_adopted_adapters_propagate_cancellation_promptly(adapter_cls):
    client = HangingClient()

    async def scenario():
        task = asyncio.create_task(adapter_cls().fetch("FC2-4979299", client))
        await asyncio.sleep(0.05)
        assert client.calls == 1 and not task.done()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, timeout=2)
        assert task.cancelled()

    run(scenario())


@pytest.mark.parametrize("adapter_cls", [Fc2dbNetAdapter, JavdbAdapter, Av123Adapter], ids=lambda c: c.source_id)
def test_the_engine_deadline_stops_each_adopted_adapter_on_a_hung_client(adapter_cls):
    client = HangingClient()
    adapter = adapter_cls()
    tgt = SourceTarget(SourceConfig(adapter.source_id, deadline_seconds=0.15), adapter, RetryPolicy.no_retry())
    started = time.monotonic()
    (trace,) = run(execute_sources_traced("FC2-4979299", [tgt], client))
    assert time.monotonic() - started < 1.5
    assert trace.final_result.error_kind is SourceErrorKind.SOURCE_DEADLINE


ADAPTER_DIR = Path(__file__).resolve().parents[3] / "src" / "fc2_metadata_core" / "sources" / "adapters"


@pytest.mark.parametrize("module", ["fc2db_net.py", "javdb.py", "av123.py", "_common.py", "_scan.py"])
def test_no_adopted_adapter_source_can_swallow_cancelled_error(module):
    """Static guard: no bare ``except:``, no ``except BaseException``, no handler naming
    CancelledError anywhere in the adapter code (``except Exception`` does not catch it)."""
    tree = ast.parse((ADAPTER_DIR / module).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler):
            assert node.type is not None, f"{module}:{node.lineno}: bare except would swallow CancelledError"
            names = [n.id for n in ast.walk(node.type) if isinstance(n, ast.Name)] + [
                n.attr for n in ast.walk(node.type) if isinstance(n, ast.Attribute)
            ]
            assert "BaseException" not in names and "CancelledError" not in names, f"{module}:{node.lineno}"
