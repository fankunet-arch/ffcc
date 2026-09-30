"""P4-C8 S3: bounded execution workers (contract sections 13, 19.3, 19.4, 29).

A spy wraps the real ``execute_filesystem`` inside the execute module and synchronises with
``threading.Event`` / ``Barrier`` (bounded waits only; no sleep is a correctness mechanism).
"""

from __future__ import annotations

import os
import threading

import pytest

from fc2_organizer.execution import ExecutionStatus, execute_filesystem
from fc2_organizer.orchestration import ExecutionDisposition as D, OrchestrationConfig
from fc2_organizer.orchestration import execute as execute_module

from ._helpers import Corpus, Film, run

WAIT = 30.0


def _films(count: int) -> list[Film]:
    return [Film(f"FC2-PPV-{1000001 + i}.mp4") for i in range(count)]


def _prepared(tmp_path, count: int, workers: int):
    corpus = Corpus(tmp_path, _films(count))
    orchestrator = corpus.orchestrator(config=OrchestrationConfig(filesystem_workers=workers))
    return corpus, orchestrator, run(orchestrator.preview(corpus.items))


class _PeakSpy:
    """Counts concurrent calls; the first ``expected`` calls wait until all of them are inside, which proves
    the peak is reached, then every call proceeds into the real P4-C7 executor."""

    def __init__(self, monkeypatch, expected: int) -> None:
        self.lock = threading.Lock()
        self.active = 0
        self.peak = 0
        self.calls = 0
        self.threads: set[int] = set()
        self.all_in = threading.Event()
        self.expected = expected
        monkeypatch.setattr(execute_module, "execute_filesystem", self)

    def __call__(self, preflight):
        with self.lock:
            self.active += 1
            self.calls += 1
            self.peak = max(self.peak, self.active)
            self.threads.add(threading.get_ident())
            if self.active >= self.expected:
                self.all_in.set()
        try:
            assert self.all_in.wait(WAIT), "the expected number of concurrent calls never ran together"
            return execute_filesystem(preflight)
        finally:
            with self.lock:
                self.active -= 1


@pytest.mark.parametrize("workers", [1, 2, 4, 8])
def test_peak_concurrency_is_exactly_the_worker_bound(tmp_path, monkeypatch, workers):
    count = 10
    corpus, orchestrator, preview = _prepared(tmp_path, count, workers)
    baseline = threading.active_count()
    spy = _PeakSpy(monkeypatch, min(workers, count))
    result = orchestrator.execute(preview)
    assert spy.calls == count and spy.peak == min(workers, count)
    assert all(i.execution_status is ExecutionStatus.SUCCESS for i in result.items)
    assert threading.active_count() == baseline  # every worker was joined
    if workers == 1:
        assert spy.threads == {threading.get_ident()}  # inline: no worker thread at all
    else:
        assert len(spy.threads) == min(workers, count) and threading.get_ident() not in spy.threads


@pytest.mark.parametrize("workers, count", [(4, 1), (8, 3), (2, 2)])
def test_worker_count_is_min_of_the_bound_and_the_selected_items(tmp_path, monkeypatch, workers, count):
    corpus, orchestrator, preview = _prepared(tmp_path, count, workers)
    created: list[threading.Thread] = []
    real_thread = threading.Thread

    class CountingThread(real_thread):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            created.append(self)

    monkeypatch.setattr(execute_module.threading, "Thread", CountingThread)
    spy = _PeakSpy(monkeypatch, min(workers, count))
    orchestrator.execute(preview)
    effective = min(workers, count)
    assert len(created) == (0 if effective <= 1 else effective)
    assert all(thread.daemon is False and not thread.is_alive() for thread in created)
    assert spy.calls == count


def test_selection_bounds_the_worker_count(tmp_path, monkeypatch):
    corpus, orchestrator, preview = _prepared(tmp_path, 6, 8)
    ready = [i.index for i in preview.items]
    spy = _PeakSpy(monkeypatch, 3)
    orchestrator.execute(preview, selection=tuple(ready[:3]))
    assert spy.calls == 3 and spy.peak == 3 and len(spy.threads) == 3


def test_the_thread_probe_detects_a_naive_thread_per_item_runner(tmp_path, monkeypatch):
    """Control: the same probe sees one thread per item (well above any bound W < n) for a naive runner."""
    corpus, orchestrator, preview = _prepared(tmp_path, 10, 2)
    spy = _PeakSpy(monkeypatch, 10)
    threads = [threading.Thread(target=spy, args=(item.preflight,)) for item in preview.items]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert len(spy.threads) == 10 and spy.peak == 10  # vs. == 2 for the bounded implementation


def _projection(result):
    """Deterministic per-item view (no random ids, no absolute paths)."""
    return tuple((i.index, i.disposition, i.execution_status, i.retry_kind,
                  None if i.execution is None else tuple(e.kind for e in i.execution.completed_effects),
                  None if i.issue is None else (i.issue.reason, i.issue.detail))
                 for i in result.items)


def test_reversed_completion_order_gives_the_same_projection(tmp_path, monkeypatch):
    count = 4
    corpus_a, orchestrator_a, preview_a = _prepared(tmp_path / "a", count, 1)
    baseline = _projection(orchestrator_a.execute(preview_a))

    corpus_b, orchestrator_b, preview_b = _prepared(tmp_path / "b", count, count)
    by_id = {item.preflight.preflight_id: item.index for item in preview_b.items}
    gates = {index: threading.Event() for index in range(count)}
    arrived = threading.Barrier(count + 1)
    finished: list[int] = []
    finished_lock = threading.Lock()

    def gated(preflight):
        index = by_id[preflight.preflight_id]
        arrived.wait(WAIT)
        assert gates[index].wait(WAIT)
        result = execute_filesystem(preflight)
        with finished_lock:
            finished.append(index)
        done[index].set()
        return result

    done = {index: threading.Event() for index in range(count)}
    monkeypatch.setattr(execute_module, "execute_filesystem", gated)

    def controller():
        arrived.wait(WAIT)  # all four calls are in flight
        for index in reversed(range(count)):
            gates[index].set()
            assert done[index].wait(WAIT)

    control = threading.Thread(target=controller)
    control.start()
    reversed_result = orchestrator_b.execute(preview_b)
    control.join()
    assert finished == list(reversed(range(count)))  # completions really happened in reverse
    assert _projection(reversed_result) == baseline
    assert [i.index for i in reversed_result.items] == list(range(count))


def test_concurrent_items_reach_their_own_targets(tmp_path, monkeypatch):
    corpus, orchestrator, preview = _prepared(tmp_path, 8, 8)
    _PeakSpy(monkeypatch, 8)
    result = orchestrator.execute(preview)
    for executed, source in zip(result.items, preview.items):
        assert executed.disposition is D.EXECUTED and executed.execution_status is ExecutionStatus.SUCCESS
        assert os.path.isfile(source.final_media_path) and not os.path.exists(source.source_path)
    assert len(os.listdir(corpus.library)) == 8
