"""P4-C8 S3: cooperative cancellation of ``execute`` (contract sections 18.3, 25.1, 27).

A ``CancellationToken`` only stops admission; an item already inside ``execute_filesystem`` always runs to
its end. Synchronisation uses events with bounded waits (no sleep).
"""

from __future__ import annotations

import errno
import os
import threading

import pytest

from fc2_organizer.execution import ExecutionStatus, execute_filesystem
from fc2_organizer.orchestration import (
    BatchExecutionResult,
    CancellationToken,
    ExecutionDisposition as D,
    OrchestrationConfig,
    OrchestrationConsumedError,
    RetryKind as K,
)
from fc2_organizer.orchestration import execute as execute_module

from ._helpers import Corpus, Film, fs_fault, run

WAIT = 30.0


def _prepared(tmp_path, count: int, workers: int):
    corpus = Corpus(tmp_path, [Film(f"FC2-PPV-{1000001 + i}.mp4") for i in range(count)])
    orchestrator = corpus.orchestrator(config=OrchestrationConfig(filesystem_workers=workers))
    return corpus, orchestrator, run(orchestrator.preview(corpus.items))


def _assert_cancelled_items_keep_their_material(result, preview) -> None:
    sources = {i.index: i for i in preview.items}
    for item in result.items:
        if item.disposition is D.CANCELLED:
            assert item.retry_kind is K.DEFERRED and item.issue is None and item.execution is None
            source = sources[item.index]
            assert item.retry_material.artifacts is source.preflight.artifacts
            assert item.retry_material.plan is source.plan
            assert item.retry_material.checkpoint is source.preflight.checkpoint


@pytest.mark.parametrize("workers", [1, 4])
def test_cancel_before_execute_admits_nothing_but_consumes_the_preview(tmp_path, monkeypatch, workers):
    corpus, orchestrator, preview = _prepared(tmp_path, 5, workers)
    calls: list[object] = []
    monkeypatch.setattr(execute_module, "execute_filesystem", lambda preflight: calls.append(preflight))
    token = CancellationToken()
    token.cancel()
    result = orchestrator.execute(preview, cancel=token)
    assert calls == []
    assert [i.disposition for i in result.items] == [D.CANCELLED] * 5
    _assert_cancelled_items_keep_their_material(result, preview)
    with pytest.raises(OrchestrationConsumedError):
        orchestrator.execute(preview)


@pytest.mark.parametrize("k", [1, 2, 4])
def test_w1_cancellation_executes_exactly_a_prefix(tmp_path, monkeypatch, k):
    corpus, orchestrator, preview = _prepared(tmp_path, 6, 1)
    token = CancellationToken()
    calls: list[str] = []

    def cancelling(preflight):
        calls.append(preflight.preflight_id)
        if len(calls) == k:
            token.cancel()  # while the k-th item is inside the executor: it still finishes
        return execute_filesystem(preflight)

    monkeypatch.setattr(execute_module, "execute_filesystem", cancelling)
    result = orchestrator.execute(preview, cancel=token)
    assert len(calls) == k
    dispositions = [i.disposition for i in result.items]
    assert dispositions == [D.EXECUTED] * k + [D.CANCELLED] * (6 - k)  # a strict prefix of the selection
    assert all(i.execution_status is ExecutionStatus.SUCCESS for i in result.items[:k])
    _assert_cancelled_items_keep_their_material(result, preview)


def test_w1_cancellation_follows_the_selection_order(tmp_path, monkeypatch):
    corpus, orchestrator, preview = _prepared(tmp_path, 6, 1)
    token = CancellationToken()
    selection = (1, 3, 4, 5)
    executed: list[int] = []
    by_id = {i.preflight.preflight_id: i.index for i in preview.items}

    def cancelling(preflight):
        executed.append(by_id[preflight.preflight_id])
        if len(executed) == 2:
            token.cancel()
        return execute_filesystem(preflight)

    monkeypatch.setattr(execute_module, "execute_filesystem", cancelling)
    result = orchestrator.execute(preview, selection=selection, cancel=token)
    assert executed == [1, 3]
    by_index = {i.index: i.disposition for i in result.items}
    assert by_index == {0: D.NOT_SELECTED, 1: D.EXECUTED, 2: D.NOT_SELECTED, 3: D.EXECUTED, 4: D.CANCELLED,
                        5: D.CANCELLED}


def test_w_gt_1_cancellation_lets_in_flight_items_finish_and_admits_nothing_more(tmp_path, monkeypatch):
    corpus, orchestrator, preview = _prepared(tmp_path, 8, 3)
    token = CancellationToken()
    arrived = threading.Barrier(3 + 1)
    release = threading.Event()
    calls: list[str] = []
    lock = threading.Lock()

    def blocking(preflight):
        with lock:
            calls.append(preflight.preflight_id)
        arrived.wait(WAIT)
        assert release.wait(WAIT)  # blocked *inside* the executor call while cancellation happens
        return execute_filesystem(preflight)

    monkeypatch.setattr(execute_module, "execute_filesystem", blocking)

    def controller():
        arrived.wait(WAIT)  # three items admitted and in flight
        token.cancel()
        release.set()

    control = threading.Thread(target=controller)
    control.start()
    result = orchestrator.execute(preview, cancel=token)
    control.join()
    assert type(result) is BatchExecutionResult  # a complete, normal result
    assert len(calls) == 3  # zero admissions after the cancellation
    executed = [i for i in result.items if i.disposition is D.EXECUTED]
    assert len(executed) == 3 and all(i.execution_status is ExecutionStatus.SUCCESS for i in executed)
    assert [i.index for i in executed] == [0, 1, 2]  # admission is in index order
    assert sum(i.disposition is D.CANCELLED for i in result.items) == 5
    _assert_cancelled_items_keep_their_material(result, preview)


def test_an_admitted_item_is_never_interrupted_and_keeps_its_partial_checkpoint(tmp_path, monkeypatch):
    corpus, orchestrator, preview = _prepared(tmp_path, 3, 1)
    token = CancellationToken()
    first = preview.items[0]
    fault = fs_fault(monkeypatch)
    fault.fail("materialization", "publish", os.path.basename(first.nfo_target), OSError(errno.EIO, "io"))
    real = execute_module.execute_filesystem

    def cancelling(preflight):
        token.cancel()
        return real(preflight)

    monkeypatch.setattr(execute_module, "execute_filesystem", cancelling)
    result = orchestrator.execute(preview, cancel=token)
    head = result.items[0]
    assert head.disposition is D.EXECUTED and head.execution_status is ExecutionStatus.PARTIAL
    assert head.retry_kind is K.RESUME and head.retry_material.checkpoint is head.execution.checkpoint
    assert [i.disposition for i in result.items[1:]] == [D.CANCELLED, D.CANCELLED]


def test_cancelling_after_execute_changes_nothing(tmp_path):
    corpus, orchestrator, preview = _prepared(tmp_path, 2, 2)
    token = CancellationToken()
    result = orchestrator.execute(preview, cancel=token)
    token.cancel()
    assert all(i.execution_status is ExecutionStatus.SUCCESS for i in result.items)
    assert token.cancelled is True
