"""P4-C6 substep 1: concurrent writers racing for the same final target."""

from __future__ import annotations

import os
import threading

import pytest

from fc2_organizer.materialization import TargetExistsError, materialize_atomic_bytes
from fc2_organizer.materialization import atomic

from ._helpers import STRATEGIES, apply_strategy, entries, inject


@pytest.fixture(params=STRATEGIES)
def strategy(request, monkeypatch):
    apply_strategy(monkeypatch, request.param)
    return request.param


def _run(writers):
    results: list[tuple[str, object]] = []
    lock = threading.Lock()

    def worker(target, payload):
        try:
            outcome = ("ok", materialize_atomic_bytes(target, payload))
        except BaseException as exc:  # noqa: BLE001 - recorded and asserted below
            outcome = ("err", exc)
        with lock:
            results.append((payload, outcome))

    threads = [threading.Thread(target=worker, args=w) for w in writers]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    assert not any(t.is_alive() for t in threads)
    return results


def _assert_single_winner(tmp_path, target, results):
    winners = [(p, o[1]) for p, o in results if o[0] == "ok"]
    losers = [o[1] for _, o in results if o[0] == "err"]
    assert len(winners) == 1, results
    assert all(type(e) is TargetExistsError for e in losers), losers
    payload, artifact = winners[0]
    assert target.read_bytes() == payload  # winner's content is complete and never overwritten
    assert artifact.size_bytes == len(payload)
    assert entries(tmp_path) == {target.name}  # every loser removed exactly its own temp


def test_two_writers_both_past_precheck_only_one_publishes(tmp_path, monkeypatch, strategy):
    """Force the real race: both callers pass the lstat pre-check, then publish together."""
    target = tmp_path / "poster.jpg"
    barrier = threading.Barrier(2, timeout=10)
    real_publish = atomic._FS.publish

    def synchronized_publish(src, dst):
        barrier.wait()
        real_publish(src, dst)

    inject(monkeypatch, publish=synchronized_publish)
    payloads = [b"A" * 100_000, b"B" * 120_000]
    results = _run([(str(target), p) for p in payloads])
    _assert_single_winner(tmp_path, target, results)


@pytest.mark.parametrize("round_", range(10))
def test_many_writers_unsynchronized_single_winner(tmp_path, strategy, round_):
    target = tmp_path / "FC2-1234567.nfo"
    payloads = [bytes([65 + i]) * (5000 + i) for i in range(8)]
    results = _run([(str(target), p) for p in payloads])
    _assert_single_winner(tmp_path, target, results)


def test_existing_winner_survives_a_late_writer(tmp_path, strategy):
    target = tmp_path / "thumb.jpg"
    materialize_atomic_bytes(str(target), b"FIRST")
    with pytest.raises(TargetExistsError):
        materialize_atomic_bytes(str(target), b"SECOND")
    assert target.read_bytes() == b"FIRST"
    assert os.listdir(tmp_path) == ["thumb.jpg"]
