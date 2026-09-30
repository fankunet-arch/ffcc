"""P4-C8 S3: the execute fatal boundary (contract sections 20.3, 27.2).

A non-``Exception`` ``BaseException`` from a worker, or one delivered to the calling thread while it joins,
stops admission, lets in-flight items finish, joins every thread and re-raises the very same object; no
``BatchExecutionResult`` is returned and the preview stays consumed. Ordering is made deterministic by
observing ``_Run.record_fatal`` (events with bounded waits, no sleep).
"""

from __future__ import annotations

import hashlib
import threading

import pytest

from fc2_organizer.execution import execute_filesystem
from fc2_organizer.orchestration import BatchExecutionResult, OrchestrationConfig, OrchestrationConsumedError
from fc2_organizer.orchestration import execute as execute_module

from ._helpers import Corpus, Film, assert_source_not_lost, run

WAIT = 30.0


class _HostileMeta(type):
    @property
    def __name__(cls):  # pragma: no cover - must never run
        _HOOKS.append("metaclass __name__")
        return "Hostile"


_HOOKS: list[str] = []


class _HostileFatal(BaseException, metaclass=_HostileMeta):
    def __str__(self):  # pragma: no cover
        _HOOKS.append("__str__")
        return "hostile"

    def __repr__(self):  # pragma: no cover
        _HOOKS.append("__repr__")
        return "hostile"

    @property
    def args(self):  # pragma: no cover
        _HOOKS.append("args")
        return ()


class _Custom(BaseException):
    pass


def _fatals():
    return [KeyboardInterrupt(), SystemExit(3), GeneratorExit(), _Custom(), _HostileFatal()]


IDS = ["KeyboardInterrupt", "SystemExit", "GeneratorExit", "custom", "hostile"]


def _prepared(tmp_path, count: int, workers: int):
    corpus = Corpus(tmp_path, [Film(f"FC2-PPV-{1000001 + i}.mp4") for i in range(count)])
    orchestrator = corpus.orchestrator(config=OrchestrationConfig(filesystem_workers=workers))
    preview = run(orchestrator.preview(corpus.items))
    hashes = {}
    for item in preview.items:
        with open(item.source_path, "rb") as handle:
            hashes[item.index] = hashlib.sha256(handle.read()).hexdigest()
    return corpus, orchestrator, preview, hashes


def _observe_fatal_record(monkeypatch) -> threading.Event:
    recorded = threading.Event()
    real = execute_module._Run.record_fatal

    def observing(self, fatal):
        real(self, fatal)
        recorded.set()

    monkeypatch.setattr(execute_module._Run, "record_fatal", observing)
    return recorded


def _worker_threads() -> list[threading.Thread]:
    return [t for t in threading.enumerate() if getattr(t, "_target", None) is execute_module._worker]


def _after_fatal(corpus, orchestrator, preview, hashes) -> None:
    assert _worker_threads() == []  # every worker was joined
    assert orchestrator._busy is False
    with pytest.raises(OrchestrationConsumedError):  # consumed at step 7, kept after the fatal
        orchestrator.execute(preview)
    for item in preview.items:
        assert_source_not_lost(item.source_path, item.final_media_path, hashes[item.index])


@pytest.mark.parametrize("index", range(5), ids=IDS)
def test_worker_fatal_drains_in_flight_items_and_reraises_the_same_object(tmp_path, monkeypatch, index):
    fatal = _fatals()[index]
    corpus, orchestrator, preview, hashes = _prepared(tmp_path, 5, 2)
    recorded = _observe_fatal_record(monkeypatch)
    sibling_in = threading.Event()
    calls: list[int] = []
    completed: list[int] = []
    lock = threading.Lock()
    by_id = {i.preflight.preflight_id: i.index for i in preview.items}

    def scripted(preflight):
        position = by_id[preflight.preflight_id]
        with lock:
            calls.append(position)
        if position == 0:
            assert sibling_in.wait(WAIT)  # the sibling is inside the executor
            raise fatal
        sibling_in.set()
        assert recorded.wait(WAIT)  # the fatal is recorded while this item is still in flight
        result = execute_filesystem(preflight)
        with lock:
            completed.append(position)
        return result

    monkeypatch.setattr(execute_module, "execute_filesystem", scripted)
    _HOOKS.clear()
    outcome: list[object] = []
    with pytest.raises(BaseException) as info:
        outcome.append(orchestrator.execute(preview))
    assert info.value is fatal and outcome == []  # the original object; no partial result
    assert sorted(calls) == [0, 1] and completed == [1]  # the in-flight sibling finished; nothing more admitted
    assert _HOOKS == []  # no metadata of the fatal object was read
    _after_fatal(corpus, orchestrator, preview, hashes)


def test_the_first_fatal_wins_when_two_workers_fail(tmp_path, monkeypatch):
    corpus, orchestrator, preview, hashes = _prepared(tmp_path, 4, 2)
    first, second = KeyboardInterrupt(), SystemExit(1)
    recorded = _observe_fatal_record(monkeypatch)
    both_in = threading.Barrier(2)
    by_id = {i.preflight.preflight_id: i.index for i in preview.items}

    def scripted(preflight):
        position = by_id[preflight.preflight_id]
        both_in.wait(WAIT)
        if position == 0:
            raise first
        assert recorded.wait(WAIT)  # strictly after the first one was recorded
        raise second

    monkeypatch.setattr(execute_module, "execute_filesystem", scripted)
    with pytest.raises(BaseException) as info:
        orchestrator.execute(preview)
    assert info.value is first and not isinstance(info.value, BaseExceptionGroup)
    _after_fatal(corpus, orchestrator, preview, hashes)


def test_caller_thread_interrupt_while_joining_is_drained_then_reraised(tmp_path, monkeypatch):
    corpus, orchestrator, preview, hashes = _prepared(tmp_path, 6, 2)
    interrupt = KeyboardInterrupt()
    recorded = _observe_fatal_record(monkeypatch)
    arrived = threading.Barrier(2 + 1)
    calls: list[str] = []
    lock = threading.Lock()

    def blocking(preflight):
        with lock:
            calls.append(preflight.preflight_id)
        arrived.wait(WAIT)
        assert recorded.wait(WAIT)  # in flight while the caller is interrupted
        return execute_filesystem(preflight)

    monkeypatch.setattr(execute_module, "execute_filesystem", blocking)
    real_thread = threading.Thread
    created: list[threading.Thread] = []
    interrupted: list[bool] = []

    class InterruptedWhileJoining(real_thread):
        """Deterministic stand-in for a signal delivered to the waiting caller thread."""

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            created.append(self)

        def join(self, timeout=None):
            if not interrupted:
                interrupted.append(True)
                arrived.wait(WAIT)  # both workers are inside the executor
                raise interrupt
            return super().join(timeout)

    monkeypatch.setattr(execute_module.threading, "Thread", InterruptedWhileJoining)
    with pytest.raises(BaseException) as info:
        orchestrator.execute(preview)
    assert info.value is interrupt
    assert len(calls) == 2  # the two in-flight items finished; nothing more was admitted
    assert len(created) == 2 and not any(thread.is_alive() for thread in created)
    monkeypatch.undo()
    _after_fatal(corpus, orchestrator, preview, hashes)


@pytest.mark.parametrize("index", range(5), ids=IDS)
def test_inline_fatal_propagates_directly(tmp_path, monkeypatch, index):
    fatal = _fatals()[index]
    corpus, orchestrator, preview, hashes = _prepared(tmp_path, 4, 1)
    calls: list[str] = []
    real = execute_filesystem

    def scripted(preflight):
        calls.append(preflight.preflight_id)
        if len(calls) == 2:
            raise fatal
        return real(preflight)

    monkeypatch.setattr(execute_module, "execute_filesystem", scripted)
    baseline = threading.active_count()
    _HOOKS.clear()
    with pytest.raises(BaseException) as info:
        orchestrator.execute(preview)
    assert info.value is fatal and len(calls) == 2 and _HOOKS == []
    assert threading.active_count() == baseline  # inline: no thread was ever created
    _after_fatal(corpus, orchestrator, preview, hashes)


def test_the_orchestrator_is_usable_again_after_a_fatal(tmp_path, monkeypatch):
    corpus, orchestrator, preview, hashes = _prepared(tmp_path, 2, 2)
    fatal = _Custom()

    def raising(preflight):
        raise fatal

    monkeypatch.setattr(execute_module, "execute_filesystem", raising)
    with pytest.raises(BaseException) as info:
        orchestrator.execute(preview)
    assert info.value is fatal
    monkeypatch.undo()
    fresh = run(orchestrator.preview(corpus.items))  # a fresh preview of the untouched sources
    assert type(orchestrator.execute(fresh)) is BatchExecutionResult
