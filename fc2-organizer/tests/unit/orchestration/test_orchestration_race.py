"""P4-C8 S5: same-process race regressions (contract sections 14, 18.1, 19.4, 25.4, 26, 30; E0-R2 hardening).

Every concurrent step is released by a ``threading.Barrier`` (timeouts are hang watchdogs only, never ordering).
The one-time registries decide every race; filesystem safety stays P4-C7's (exclusive ``mkdir``, source ownership,
one-time preflight consumption) -- P4-C8 holds no lock of its own. Every real-filesystem case asserts
``assert_source_not_lost`` and that bystanders are unchanged.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import threading

import pytest

from fc2_organizer.discovery import discover_media
from fc2_organizer.execution import ExecutionStatus, execute_filesystem
from fc2_organizer.images import ImageAcquisitionPolicy
from fc2_organizer.orchestration import (
    BatchExecutionResult,
    ExecutionDisposition as D,
    IssueReason as R,
    OrchestrationConfig,
    OrchestrationConsumedError,
    OrchestrationIntegrityError,
    OrchestrationRetryError,
    PreviewState as S,
    RetryKind as K,
    merge_retry,
)
from fc2_organizer.orchestration import _consumption
from fc2_organizer.orchestration import execute as execute_module

from ._fakes import build_metadata
from ._helpers import Corpus, Film, assert_source_not_lost, run, tree_snapshot

WAIT = 30.0


def _sha(path) -> str:
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def _race(*callables):
    """Run each callable in its own thread behind one barrier; returns (results, errors) in call order."""
    barrier = threading.Barrier(len(callables))
    results: list[object] = [None] * len(callables)
    errors: list[BaseException | None] = [None] * len(callables)

    def worker(position, function):
        barrier.wait(WAIT)
        try:
            results[position] = function()
        except BaseException as error:  # noqa: BLE001 - classified by the test
            errors[position] = error

    threads = [threading.Thread(target=worker, args=(i, f)) for i, f in enumerate(callables)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(WAIT)
    assert not any(thread.is_alive() for thread in threads), "a racing call hung"
    return results, errors


class _Calls:
    """Counts ``execute_filesystem`` calls per preflight id (thread-safe), then runs the real executor."""

    def __init__(self, monkeypatch, barrier: threading.Barrier | None = None) -> None:
        self.lock = threading.Lock()
        self.per_preflight: dict[str, int] = {}
        self.barrier = barrier
        monkeypatch.setattr(execute_module, "execute_filesystem", self)

    def __call__(self, preflight):
        with self.lock:
            self.per_preflight[preflight.preflight_id] = self.per_preflight.get(preflight.preflight_id, 0) + 1
        if self.barrier is not None:
            self.barrier.wait(WAIT)  # both executions are inside P4-C7 together
        return execute_filesystem(preflight)


def _hashes(corpus) -> dict[str, str]:
    return {item.source_path: _sha(item.source_path) for item in corpus.items}


# --------------------------------------------------------------------------- same preview, two threads


def test_the_same_preview_executed_concurrently_runs_exactly_once(tmp_path, monkeypatch):
    corpus = Corpus(tmp_path, [Film(f"FC2-PPV-{1000001 + i}.mp4") for i in range(3)])
    hashes = _hashes(corpus)
    first, second = corpus.orchestrator(), corpus.orchestrator()  # busy guards are per orchestrator
    preview = run(first.preview(corpus.items))
    calls = _Calls(monkeypatch)
    results, errors = _race(lambda: first.execute(preview), lambda: second.execute(preview))
    winners = [r for r in results if r is not None]
    assert len(winners) == 1 and sum(type(e) is OrchestrationConsumedError for e in errors) == 1
    assert sorted(calls.per_preflight.values()) == [1, 1, 1]  # no preflight reached P4-C7 twice
    result = winners[0]
    assert all(i.execution_status is ExecutionStatus.SUCCESS for i in result.items)
    assert result.retained_retry_payload_bytes <= result.retention_budget_bytes
    for item in preview.items:
        assert_source_not_lost(item.source_path, item.final_media_path, hashes[item.source_path])


# --------------------------------------------------------------------------- overlapping sources, two orchestrators


def test_two_orchestrators_racing_on_the_same_source_succeed_at_most_once(tmp_path, monkeypatch):
    corpus = Corpus(tmp_path, [Film("FC2-PPV-1000001.mp4")])
    bystander = tmp_path / "bystander.bin"
    bystander.write_bytes(b"untouched")
    hashes = _hashes(corpus)
    first, second = corpus.orchestrator(), corpus.orchestrator()
    preview_a = run(first.preview(corpus.items))
    preview_b = run(second.preview(corpus.items))  # each its own preview of the same source
    _Calls(monkeypatch, threading.Barrier(2))
    results, errors = _race(lambda: first.execute(preview_a), lambda: second.execute(preview_b))
    assert errors == [None, None]
    statuses = [r.items[0].execution_status for r in results]
    assert statuses.count(ExecutionStatus.SUCCESS) <= 1 and ExecutionStatus.SUCCESS in statuses
    loser = next(r.items[0] for r in results if r.items[0].execution_status is not ExecutionStatus.SUCCESS)
    assert loser.disposition is D.EXECUTED and loser.execution_status in (ExecutionStatus.FAILED,
                                                                          ExecutionStatus.PARTIAL)
    assert loser.issue.detail is loser.execution.failure.kind  # a typed P4-C7 failure
    item = preview_a.items[0]
    assert_source_not_lost(item.source_path, item.final_media_path, hashes[item.source_path])
    assert sorted(os.listdir(corpus.library)) == [os.path.basename(item.target_directory)]
    assert bystander.read_bytes() == b"untouched"
    for result in results:
        assert result.retained_retry_payload_bytes <= result.retention_budget_bytes


# --------------------------------------------------------------------------- in-batch conflicts


def _never_dispatched(corpus, items, monkeypatch, expected_reason):
    orchestrator = corpus.orchestrator()
    preview = run(orchestrator.preview(items))
    calls = _Calls(monkeypatch)
    snapshot = tree_snapshot(corpus.root)
    result = orchestrator.execute(preview)
    conflicted = [i for i in result.items if i.issue is not None and i.issue.reason is expected_reason]
    assert len(conflicted) >= 2 and all(i.preview_state is S.BLOCKED and i.conflict_with for i in conflicted)
    assert all(i.disposition is D.NOT_READY and i.retry_kind is K.NONE for i in conflicted)
    assert calls.per_preflight == {} and tree_snapshot(corpus.root) == snapshot  # never dispatched
    return result


def test_a_hardlinked_source_under_two_names_is_a_batch_conflict(tmp_path, monkeypatch):
    corpus = Corpus(tmp_path, [Film("FC2-PPV-1000001.mp4"), Film("FC2-PPV-1000002.mp4")])
    first, second = (str(corpus.downloads / n) for n in ("FC2-PPV-1000001.mp4", "FC2-PPV-1000002.mp4"))
    os.remove(second)
    os.link(first, second)
    items = discover_media(str(corpus.downloads)).items
    _never_dispatched(corpus, items, monkeypatch, R.DUPLICATE_SOURCE_IN_BATCH)


def test_the_same_file_twice_is_a_batch_conflict(tmp_path, monkeypatch):
    corpus = Corpus(tmp_path, [Film("FC2-PPV-1000001.mp4")])
    _never_dispatched(corpus, (corpus.items[0], corpus.items[0]), monkeypatch, R.DUPLICATE_SOURCE_IN_BATCH)


def test_a_file_found_through_two_overlapping_roots_is_a_batch_conflict(tmp_path, monkeypatch):
    corpus = Corpus(tmp_path, [Film("FC2-PPV-1000001.mp4", directory="sub")])
    items = discover_media(str(corpus.downloads)).items + discover_media(str(corpus.downloads / "sub")).items
    assert len(items) == 2 and items[0] is not items[1]
    _never_dispatched(corpus, items, monkeypatch, R.DUPLICATE_SOURCE_IN_BATCH)


# --------------------------------------------------------------------------- drift between preview and execute


def _rewrite(corpus, item, tmp_path):
    with open(item.source_path, "wb") as handle:
        handle.write(b"rewritten by the user after preview")
    return {item.source_path: b"rewritten by the user after preview"}


def _delete(corpus, item, tmp_path):
    os.remove(item.source_path)
    return {}


def _plant(corpus, item, tmp_path):
    os.makedirs(item.target_directory)
    planted = os.path.join(item.target_directory, "user.txt")
    with open(planted, "wb") as handle:
        handle.write(b"planted")
    return {planted: b"planted"}


def _junction(corpus, item, tmp_path):
    if os.name != "nt":
        pytest.skip("junctions are Windows-only (frozen platform skip)")
    import _winapi

    real = tmp_path / "lib-real"
    shutil.move(str(corpus.library), str(real))
    _winapi.CreateJunction(str(real), str(corpus.library))
    return {}


@pytest.mark.parametrize("drift", [_rewrite, _delete, _plant, _junction],
                         ids=["rewrite", "delete", "plant", "junction"])
def test_drift_after_preview_fails_typed_and_never_executes_something_else(tmp_path, monkeypatch, drift):
    corpus = Corpus(tmp_path, [Film("FC2-PPV-1000001.mp4"), Film("FC2-PPV-1000002.mp4")])
    hashes = _hashes(corpus)
    orchestrator = corpus.orchestrator()
    preview = run(orchestrator.preview(corpus.items))
    target, bystander = preview.items
    kept = drift(corpus, target, tmp_path)
    result = orchestrator.execute(preview)
    drifted = result.items[0]
    assert drifted.execution_status is not ExecutionStatus.SUCCESS
    if drifted.disposition is D.EXECUTED:
        assert drifted.execution_status in (ExecutionStatus.FAILED, ExecutionStatus.PARTIAL)
        assert drifted.issue.detail is drifted.execution.failure.kind  # a typed P4-C7 failure
    else:
        assert drifted.disposition is D.REJECTED and drifted.issue.reason is R.EXECUTION_REJECTED
    for path, content in kept.items():  # the user's bytes are never overwritten
        with open(path, "rb") as handle:
            assert handle.read() == content
    if drift is _delete:
        assert not os.path.exists(target.final_media_path)
    elif drift is _rewrite:
        assert not os.path.exists(target.final_media_path)  # the other bytes were never moved
    if drift is _junction:
        assert all(i.execution_status is not ExecutionStatus.SUCCESS for i in result.items)
        assert os.listdir(tmp_path / "lib-real") == []  # nothing was written through the swapped root
    else:
        assert result.items[1].execution_status is ExecutionStatus.SUCCESS
        assert_source_not_lost(bystander.source_path, bystander.final_media_path, hashes[bystander.source_path])
    if drift is _plant:
        assert_source_not_lost(target.source_path, target.final_media_path, hashes[target.source_path])


# --------------------------------------------------------------------------- one-time retry / merge registries


def test_two_orchestrators_racing_preview_retry_on_one_result_succeed_once(tmp_path):
    corpus = Corpus(tmp_path, [Film("FC2-PPV-1000001.mp4"), Film("FC2-PPV-1000002.mp4", kind="failed")])
    first, second = corpus.orchestrator(), corpus.orchestrator()
    result = first.execute(run(first.preview(corpus.items)))
    inside = threading.Barrier(2)  # both are past step 6 (query) and inside the metadata retry

    async def recovering(number, _seq):
        inside.wait(WAIT)
        return build_metadata(number, "success", **corpus.engine.fields.get(number, {}))

    corpus.engine.script["FC2-1000002"] = recovering
    results, errors = _race(lambda: run(first.preview_retry(result)), lambda: run(second.preview_retry(result)))
    assert sum(r is not None for r in results) == 1
    assert sum(type(e) is OrchestrationConsumedError for e in errors) == 1  # the step-11 registration decided
    assert _consumption.RESULT_RETRIES.is_registered(result.result_id)


SMALL_BUDGET = 64 * 1024


def _retry_round(tmp_path, small: bool = False):
    corpus = Corpus(tmp_path, [Film(f"FC2-PPV-{1000001 + i}.mp4") for i in range(3)])
    kwargs = {}
    if small:  # a tight lineage budget B (small images, small per-item reservation)
        kwargs = dict(image_policy=ImageAcquisitionPolicy(max_image_bytes=4096, max_total_bytes=4096),
                      config=OrchestrationConfig(max_retained_artifact_bytes=SMALL_BUDGET))
    orchestrator = corpus.orchestrator(**kwargs)
    result = orchestrator.execute(run(orchestrator.preview(corpus.items)), selection=(0,))
    round_result = orchestrator.execute(run(orchestrator.preview_retry(result)), selection=(1,))
    return corpus, orchestrator, result, round_result


def test_two_threads_merging_the_same_retry_result_succeed_once(tmp_path):
    corpus, orchestrator, result, round_result = _retry_round(tmp_path)
    results, errors = _race(lambda: merge_retry(result, round_result), lambda: merge_retry(result, round_result))
    merged = [r for r in results if r is not None]
    assert len(merged) == 1 and sum(type(e) is OrchestrationConsumedError for e in errors) == 1
    assert type(merged[0]) is BatchExecutionResult and merged[0].is_complete
    assert merged[0].retained_retry_payload_bytes <= merged[0].retention_budget_bytes
    assert [i.retry_kind for i in merged[0].items] == [K.NONE, K.NONE, K.DEFERRED]


# --------------------------------------------------------------------------- E0-R2 hardening on generated batches


def _set(obj, **fields):
    saved = {name: getattr(obj, name) for name in fields}
    for name, value in fields.items():
        object.__setattr__(obj, name, value)
    return lambda: [object.__setattr__(obj, name, value) for name, value in saved.items()]


def test_every_current_complete_result_of_a_generated_chain_stays_within_its_budget(tmp_path):
    corpus, orchestrator, result, round_result = _retry_round(tmp_path)
    merged = merge_retry(result, round_result)
    final = merge_retry(merged, orchestrator.execute(run(orchestrator.preview_retry(merged))))
    for complete in (result, merged, final):
        assert complete.is_complete
        assert complete.retained_retry_payload_bytes <= complete.retention_budget_bytes
    assert final.retained_retry_payload_bytes == 0 and final.summary.success == 3


@pytest.mark.parametrize("tamper", ["retry_budget", "retention_budget", "bigger_material"])
def test_a_tampered_real_retry_round_fails_closed_and_the_restored_one_merges(tmp_path, tamper):
    corpus, orchestrator, result, round_result = _retry_round(tmp_path, small=True)
    assert round_result.retention_budget_bytes == SMALL_BUDGET
    if tamper == "retry_budget":  # self-consistent, but not B - base_retained (section 26 step 9a)
        restore, error = _set(round_result, retry_budget_bytes=round_result.retry_budget_bytes - 1), \
            OrchestrationRetryError
    elif tamper == "retention_budget":  # another lineage budget (step 9a)
        restore, error = _set(round_result, retention_budget_bytes=round_result.retention_budget_bytes + 1), \
            OrchestrationRetryError
    else:  # the deferred item's retained material swapped for one larger than the whole lineage budget B
        deferred = round_result.items[1]
        material = deferred.retry_material
        payload = sum(len(request.content) for request in material.artifacts)
        larger = type(material)(material.plan, material.artifacts * (SMALL_BUDGET // payload + 2), None)
        assert sum(len(request.content) for request in larger.artifacts) > SMALL_BUDGET
        restore, error = _set(deferred, retry_material=larger), OrchestrationIntegrityError
    with pytest.raises(error):
        merge_retry(result, round_result)
    assert not _consumption.RETRY_MERGES.is_registered(round_result.result_id)
    restore()
    merged = merge_retry(result, round_result)
    assert merged.retained_retry_payload_bytes <= merged.retention_budget_bytes
