"""P4-C8 S2: preview resource limits (contract sections 19.6.1-19.6.6; section 35 "resource limits").

Small configurations only (no large allocation). Budgets are derived from the case definition: every
film has exactly one poster of ``a`` bytes; NFO charges are the real rendered lengths observed on a
baseline run; ``R = image_policy.max_total_bytes``; item ``j`` is admitted iff
``A_nfo + sum(a for i < j) + R <= B``.
"""

from __future__ import annotations

import asyncio
import hashlib

import pytest

from fc2_metadata_core.batch import BatchConfig
from fc2_organizer.discovery import DiscoveredMediaItem
from fc2_organizer.images import AcquiredImage, ImageAcquisitionPolicy, ImageAcquisitionResult, ImageRole
from fc2_organizer.orchestration import (
    MAX_BATCH_ITEMS,
    MAX_ITEM_IMAGE_BYTES,
    BatchOrchestrator,
    IssueReason as R_,
    OrchestrationConfig,
    OrchestrationConfigError,
    OrchestrationResourceLimitError,
    PreviewState as S,
    ResourceLimitReason,
)
from fc2_organizer.orchestration import preview as preview_module
from fc2_organizer.orchestration import stages

from support.batch_fakes import until

from ._fakes import ScriptedEngine, ScriptedImageClient, minimal_jpeg
from ._helpers import DOWNLOADS, LIBRARY, Corpus, Film, image_url, mutation_traps, run, tree_snapshot

A = len(minimal_jpeg())  # every scripted poster has exactly this many bytes


def _films(count: int) -> list[Film]:
    return [Film(f"FC2-PPV-{1000001 + i}.mp4", fanart=False, thumb=False) for i in range(count)]


def _numbers(count: int) -> list[str]:
    return [f"FC2-{1000001 + i}" for i in range(count)]


def _policy(r: int) -> ImageAcquisitionPolicy:
    return ImageAcquisitionPolicy(max_image_bytes=r, max_total_bytes=r)


def _config(budget: int, k: int = 1) -> OrchestrationConfig:
    return OrchestrationConfig(metadata=BatchConfig(max_in_flight_items=4), image_in_flight_items=k,
                               max_retained_artifact_bytes=budget)


def _nfo_charges(corpus: Corpus, monkeypatch) -> list[int]:
    """The real ``4 * len(nfo_text)`` charges, in index order, from a baseline run with the default budget."""
    lengths: list[int] = []
    real = stages.render_movie_nfo

    def recording(record):
        text = real(record)
        lengths.append(4 * len(text))
        return text

    monkeypatch.setattr(stages, "render_movie_nfo", recording)
    corpus.preview(corpus.orchestrator(image_policy=_policy(A)))
    monkeypatch.setattr(stages, "render_movie_nfo", real)
    corpus.client.calls.clear()
    corpus.client.peak = 0
    return lengths


def _expect_limit(orchestrator, items, reason=ResourceLimitReason.RETAINED_BYTES_LIMIT):
    with pytest.raises(OrchestrationResourceLimitError) as info:
        run(orchestrator.preview(items), timeout=20)
    error = info.value
    assert error.reason is reason and error.__cause__ is None and error.__context__ is None
    assert "http" not in str(error) and "\\" not in str(error) and "/" not in str(error)
    assert orchestrator._busy is False
    return error


# =========================================================================== construction / item count


def test_image_policy_cap_at_construction():
    at = ImageAcquisitionPolicy(max_total_bytes=MAX_ITEM_IMAGE_BYTES)
    assert BatchOrchestrator(ScriptedEngine(), ScriptedImageClient(), LIBRARY, image_policy=at).image_policy is at
    with pytest.raises(OrchestrationConfigError):
        BatchOrchestrator(ScriptedEngine(), ScriptedImageClient(), LIBRARY,
                          image_policy=ImageAcquisitionPolicy(max_total_bytes=MAX_ITEM_IMAGE_BYTES + 1))


def _tiny_items(count: int) -> list[DiscoveredMediaItem]:
    import os

    return [DiscoveredMediaItem(index=i, source_path=os.path.join(DOWNLOADS, f"clip{i}.mp4"),
                                relative_path=f"clip{i}.mp4", extension=".mp4", size=1) for i in range(count)]


def test_max_batch_items_is_accepted_end_to_end(monkeypatch):
    engine, client = ScriptedEngine(), ScriptedImageClient()
    orchestrator = BatchOrchestrator(engine, client, LIBRARY)
    trap = mutation_traps(monkeypatch)
    preview = run(orchestrator.preview(_tiny_items(MAX_BATCH_ITEMS)))
    assert trap.calls == [] and preview.batch_size == MAX_BATCH_ITEMS
    assert all(i.issue.reason is R_.NUMBER_NOT_RECOGNIZED for i in preview.items)
    assert engine.calls == [] and client.calls == []


def test_one_over_max_batch_items_fails_before_any_access(monkeypatch):
    engine, client = ScriptedEngine(), ScriptedImageClient()
    orchestrator = BatchOrchestrator(engine, client, LIBRARY)
    trap = mutation_traps(monkeypatch)
    items = _tiny_items(MAX_BATCH_ITEMS + 1)
    items[-1] = "not even an item"  # the limit wins over element validation
    _expect_limit(orchestrator, items, ResourceLimitReason.BATCH_ITEM_LIMIT)
    assert trap.calls == [] and engine.calls == [] and client.calls == []


# =========================================================================== byte budget


def test_b_exact_is_accepted_and_b_exact_minus_one_fails(tmp_path, monkeypatch):
    corpus = Corpus(tmp_path, _films(3))
    nfo = _nfo_charges(corpus, monkeypatch)
    r = 2 * A
    b_exact = sum(nfo) + 2 * A + r  # tightest admission is the last item (j = 2)
    before = tree_snapshot(tmp_path)
    for k in (1, 2, 4):
        preview = run(corpus.orchestrator(image_policy=_policy(r), config=_config(b_exact, k)).preview(corpus.items))
        assert all(i.state is S.READY for i in preview.items)
        assert preview.retention_budget_bytes == b_exact and preview.retained_artifact_bytes <= b_exact
        corpus.client.calls.clear()
        _expect_limit(corpus.orchestrator(image_policy=_policy(r), config=_config(b_exact - 1, k)), corpus.items)
        assert sorted(corpus.client.calls) == [image_url(n, "poster") for n in _numbers(2)]  # j = 2 never admitted
        corpus.client.calls.clear()
    assert tree_snapshot(tmp_path) == before


def test_nfo_over_budget_fails_before_any_image_request(tmp_path, monkeypatch):
    corpus = Corpus(tmp_path, _films(3))
    nfo = _nfo_charges(corpus, monkeypatch)
    for budget in (nfo[0] - 1, sum(nfo) - 1):
        _expect_limit(corpus.orchestrator(image_policy=_policy(A), config=_config(budget)), corpus.items)
        assert corpus.client.calls == []


def test_no_call_in_flight_fails_immediately_without_hanging(tmp_path, monkeypatch):
    corpus = Corpus(tmp_path, _films(2))
    nfo = _nfo_charges(corpus, monkeypatch)
    budget = sum(nfo) + A - 1  # R = A never fits, and nothing is in flight
    for k in (1, 4):
        _expect_limit(corpus.orchestrator(image_policy=_policy(A), config=_config(budget, k)), corpus.items)
        assert corpus.client.calls == []


class _RecordingLedger(preview_module._Ledger):
    instances: list["_RecordingLedger"] = []

    def __init__(self, limit: int) -> None:
        super().__init__(limit)
        _RecordingLedger.instances.append(self)


def test_k4_with_room_for_two_reservations_keeps_peak_two_and_ledger_within_b(tmp_path, monkeypatch):
    corpus = Corpus(tmp_path, _films(4))
    nfo = _nfo_charges(corpus, monkeypatch)
    r = 3 * A
    budget = sum(nfo) + 2 * r  # two reservations fit; every item is eventually admitted
    _RecordingLedger.instances.clear()
    monkeypatch.setattr(preview_module, "_Ledger", _RecordingLedger)
    observed: list[tuple[int, int]] = []
    for url, answer in list(corpus.client.script.items()):
        async def watched(_url, _answer=answer):
            ledger = _RecordingLedger.instances[-1]
            observed.append((ledger.charged + ledger.reserved, ledger.limit))
            await asyncio.sleep(0)
            return _answer
        corpus.client.script[url] = watched
    preview = run(corpus.orchestrator(image_policy=_policy(r), config=_config(budget, k=4)).preview(corpus.items))
    assert all(i.state is S.READY for i in preview.items)
    assert corpus.client.peak == 2
    assert observed and all(total <= limit for total, limit in observed)
    ledger = _RecordingLedger.instances[-1]
    assert ledger.reserved == 0 and ledger.charged == sum(nfo) + 4 * A <= budget


async def _run_reversed(corpus, orchestrator, gated: list[str]):
    """Hold the given poster requests and release them in reverse order."""
    for url in gated:
        corpus.client.gate(url)

    async def controller():
        await until(lambda: corpus.client.active == len(gated))
        for url in reversed(gated):
            done = len(corpus.client.completed)
            corpus.client.gates[url].set()
            await until(lambda: len(corpus.client.completed) > done)

    control = asyncio.ensure_future(controller())
    try:
        return await orchestrator.preview(corpus.items)
    finally:
        await asyncio.gather(control, return_exceptions=True)


def test_failure_index_is_the_same_for_every_k_and_completion_order(tmp_path, monkeypatch):
    corpus = Corpus(tmp_path, _films(5))
    nfo = _nfo_charges(corpus, monkeypatch)
    budget = sum(nfo) + 2 * A  # R = A: exactly two items fit, index 2 is the deterministic failure point
    admitted = [image_url(n, "poster") for n in _numbers(2)]
    outcomes = []
    for k in (1, 2, 4):
        corpus.client.calls.clear()
        _expect_limit(corpus.orchestrator(image_policy=_policy(A), config=_config(budget, k)), corpus.items)
        outcomes.append(sorted(corpus.client.calls))
    for k in (2, 4):
        corpus.client.calls.clear()
        corpus.client.completed.clear()
        with pytest.raises(OrchestrationResourceLimitError):
            run(_run_reversed(corpus, corpus.orchestrator(image_policy=_policy(A), config=_config(budget, k)),
                              admitted), timeout=20)
        assert corpus.client.completed == list(reversed(admitted))
        outcomes.append(sorted(corpus.client.calls))
        corpus.client.gates.clear()
    assert all(outcome == admitted for outcome in outcomes)


def test_image_result_above_the_reservation_is_an_item_error(tmp_path, monkeypatch):
    corpus = Corpus(tmp_path, _films(2))
    real_acquire = preview_module.acquire_images
    oversized = minimal_jpeg(pad=500)

    async def lying(record, client, *, policy=None):
        if record.plan.canonical_number == "FC2-1000001":
            image = AcquiredImage(role=ImageRole.POSTER, candidate_index=0, content=oversized, width=16, height=16,
                                  size_bytes=len(oversized), sha256=hashlib.sha256(oversized).hexdigest())
            return ImageAcquisitionResult(poster=image)
        return await real_acquire(record, client, policy=policy)

    monkeypatch.setattr(preview_module, "acquire_images", lying)
    preview = run(corpus.orchestrator(image_policy=_policy(A)).preview(corpus.items))
    bad, good = preview.items
    assert bad.state is S.UNPREPARED and bad.issue.reason is R_.IMAGE_ACQUISITION_ERROR
    assert bad.issue.error_type == "ImageAcquisitionResult" and bad.preflight is None
    assert good.state is S.READY
    assert preview.retained_artifact_bytes == sum(len(r.content) for r in good.preflight.artifacts)


def test_resource_failure_is_read_only_and_leaves_the_orchestrator_idle(tmp_path, monkeypatch):
    corpus = Corpus(tmp_path, _films(2))
    nfo = _nfo_charges(corpus, monkeypatch)
    orchestrator = corpus.orchestrator(image_policy=_policy(A), config=_config(sum(nfo) + A - 1))
    before = tree_snapshot(tmp_path)
    trap = mutation_traps(monkeypatch)
    _expect_limit(orchestrator, corpus.items)
    assert trap.calls == []
    monkeypatch.undo()
    assert tree_snapshot(tmp_path) == before
    roomy = corpus.orchestrator(image_policy=_policy(A))
    assert run(roomy.preview(corpus.items)).retention_budget_bytes == roomy.config.max_retained_artifact_bytes
