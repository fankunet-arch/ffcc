"""P4-C8 S1: ``CancellationToken`` (contract sections 10.8 and 27)."""

from __future__ import annotations

import ast
import asyncio
import threading
from pathlib import Path

import pytest

import fc2_organizer.orchestration as orchestration
from fc2_organizer.orchestration import CancellationToken


def test_new_token_is_not_cancelled():
    assert CancellationToken().cancelled is False


def test_cancel_is_one_way_and_idempotent():
    token = CancellationToken()
    token.cancel()
    assert token.cancelled is True
    for _ in range(3):
        token.cancel()
        assert token.cancelled is True
    assert type(token.cancelled) is bool


def test_there_is_no_reset_and_no_extra_api():
    public = {name for name in dir(CancellationToken) if not name.startswith("_")}
    assert public == {"cancel", "cancelled"}
    token = CancellationToken()
    token.cancel()
    with pytest.raises(AttributeError):
        token.cancelled = False  # type: ignore[misc]
    with pytest.raises(AttributeError):
        token.anything = 1  # type: ignore[attr-defined]
    assert token.cancelled is True


def test_internal_state_is_exactly_one_threading_event():
    token = CancellationToken()
    assert CancellationToken.__slots__ == ("_event",)
    assert type(token._event) is threading.Event


def test_concurrent_cancel_and_read_from_many_threads():
    token = CancellationToken()
    threads_count = 16
    barrier = threading.Barrier(threads_count * 2)
    observed: list[bool] = []
    lock = threading.Lock()

    def canceller():
        barrier.wait()
        token.cancel()

    def reader():
        barrier.wait()
        value = token.cancelled
        with lock:
            observed.append(value)

    threads = [threading.Thread(target=canceller) for _ in range(threads_count)]
    threads += [threading.Thread(target=reader) for _ in range(threads_count)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert token.cancelled is True
    assert len(observed) == threads_count and all(type(v) is bool for v in observed)


def test_a_reader_thread_observes_the_cancellation_monotonically():
    token = CancellationToken()
    seen_true = threading.Event()
    regressions: list[int] = []
    started = threading.Event()

    def watcher():
        started.set()
        was = False
        while not seen_true.is_set():
            now = token.cancelled
            if was and not now:
                regressions.append(1)
            if now:
                seen_true.set()
            was = was or now

    thread = threading.Thread(target=watcher)
    thread.start()
    started.wait()
    token.cancel()
    thread.join()
    assert regressions == [] and token.cancelled is True


def test_it_is_not_asyncio_cancellation():
    token = CancellationToken()

    async def scenario():
        async def worker():
            await asyncio.sleep(0)
            return "finished"

        task = asyncio.ensure_future(worker())
        token.cancel()
        return await task

    assert asyncio.run(scenario()) == "finished"  # a set token cancels no task
    assert not isinstance(token, asyncio.Event)
    source = (Path(orchestration.__file__).parent / "cancellation.py").read_text(encoding="utf-8")
    imported = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add(node.module)
    assert imported == {"__future__", "threading"}
