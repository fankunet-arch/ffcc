"""P4-C8 S4: ``BatchOrchestrator.preview_retry(previous, *, scope=None)`` (contract sections 12, 16, 19.6.7, 24,
25.1-25.4).

Real ``tmp_path`` trees, the real P4-C7 preflight / executor and scripted engine / image client. Registration of
``previous.result_id`` is the last step: every failure below leaves ``previous`` retryable.
"""

from __future__ import annotations

import asyncio
import errno
import os

import pytest

from fc2_metadata_core.batch import BatchConfig, BatchItemResult, BatchItemStatus, BatchResult
from fc2_organizer.discovery import discover_media
from fc2_organizer.execution import (
    CheckpointRejectionReason,
    ExecutionStatus,
    PreflightMode,
    execute_filesystem,
    preflight_execution,
)
from fc2_organizer.images import ImageAcquisitionPolicy
from fc2_organizer.materialization import ArtifactKind
from fc2_organizer.orchestration import (
    BatchOutcome,
    BatchPreview,
    ExecutionDisposition as D,
    IssueReason as R,
    OrchestrationBusyError,
    OrchestrationConfig,
    OrchestrationConsumedError,
    OrchestrationInputError,
    OrchestrationIntegrityError,
    OrchestrationResourceLimitError,
    OrchestrationStage,
    PreviewState as S,
    ResourceLimitReason,
    RetryKind as K,
    merge_retry,
)
from fc2_organizer.orchestration import _consumption
from fc2_organizer.planning import OutputPolicy

from ._fakes import build_metadata
from ._helpers import Corpus, Film, fs_fault, mutation_traps, run, tampered, tree_snapshot

EVERY_KIND = frozenset(kind for kind in K if kind is not K.NONE)
NAMES = [f"FC2-PPV-{1000001 + i}.mp4" for i in range(6)]


async def _in_flight(engine, number: str, baseline: int) -> None:
    """Yield until the retry's own metadata call for ``number`` has started (bounded; hang protection)."""
    for _ in range(10_000):
        if engine.calls.count(number) > baseline:
            return
        await asyncio.sleep(0)
    raise AssertionError("the metadata retry call never started")


def _registered(result) -> bool:
    return _consumption.RESULT_RETRIES.is_registered(result.result_id)


class _AllKinds:
    """g0 with every retry kind: 0 FAILED, 1 PARTIAL, 2 metadata FAILED, 3 PREFLIGHT_BLOCKED, 4 NOT_SELECTED,
    5 SUCCESS."""

    def __init__(self, tmp_path, monkeypatch) -> None:
        films = [Film(NAMES[0]), Film(NAMES[1]), Film(NAMES[2], kind="failed"), Film(NAMES[3]), Film(NAMES[4]),
                 Film(NAMES[5])]
        probe = Corpus(tmp_path / "probe", films)
        blocked = os.path.basename(run(probe.orchestrator().preview(probe.items)).items[3].target_directory)
        self.corpus = Corpus(tmp_path / "g", films)
        os.makedirs(self.corpus.library / blocked)
        self.orchestrator = self.corpus.orchestrator()
        self.preview = run(self.orchestrator.preview(self.corpus.items))
        items = self.preview.items
        with monkeypatch.context() as m:
            fault = fs_fault(m)
            fault.fail("execution", "mkdir", items[0].target_directory, OSError(errno.EACCES, "denied"))
            fault.fail("materialization", "publish", os.path.basename(items[1].nfo_target), OSError(errno.EIO, "io"))
            self.result = self.orchestrator.execute(self.preview, selection=(0, 1, 5))
        assert [i.retry_kind for i in self.result.items] == [K.FRESH_REEXECUTE, K.RESUME, K.METADATA_REFETCH,
                                                             K.PREFLIGHT_RECHECK, K.DEFERRED, K.NONE]

    def calls(self) -> tuple[int, int]:
        return len(self.corpus.engine.calls), len(self.corpus.client.calls)


def test_every_retry_kind_is_re_prepared_as_the_frozen_table_says(tmp_path, monkeypatch):
    g = _AllKinds(tmp_path, monkeypatch)
    result = g.result
    retry = run(g.orchestrator.preview_retry(result))
    assert type(retry) is BatchPreview and retry.retry_scope == EVERY_KIND  # None resolved and stored
    assert [i.index for i in retry.items] == [0, 1, 2, 3, 4]  # index order; SUCCESS (NONE) excluded
    assert [i.retry_origin for i in retry.items] == [K.FRESH_REEXECUTE, K.RESUME, K.METADATA_REFETCH,
                                                     K.PREFLIGHT_RECHECK, K.DEFERRED]
    fresh, resume, metadata, recheck, deferred = retry.items
    assert fresh.preflight_mode is PreflightMode.FRESH and fresh.preflight.checkpoint is None
    assert resume.preflight_mode is PreflightMode.RESUME
    assert resume.preflight.checkpoint is result.items[1].execution.checkpoint
    assert metadata.state is S.UNPREPARED and metadata.issue.stage is OrchestrationStage.METADATA
    assert recheck.state is S.BLOCKED and recheck.issue.reason is R.PREFLIGHT_BLOCKED
    assert recheck.preflight.checkpoint is result.items[3].retry_material.checkpoint
    assert deferred.state is S.READY and deferred.preflight.checkpoint is result.items[4].retry_material.checkpoint
    for item in (fresh, resume, recheck, deferred):  # the retained plan / manifest, never rebuilt
        material = result.items[item.index].retry_material
        assert item.plan is material.plan and item.preflight.artifacts is material.artifacts
        assert item.media_item is result.items[item.index].media_item
    assert retry.generation == 1 and retry.base_result_id == result.result_id and retry.lineage == result.lineage
    assert all(i.generation == 1 for i in retry.items) and retry.batch_size == result.batch_size
    assert retry.retention_budget_bytes == result.retention_budget_bytes
    assert retry.retry_budget_bytes == result.retention_budget_bytes  # nothing outside R retains material
    assert retry.metadata_batch.generation == 1 and _registered(result)


def test_retained_material_kinds_make_no_network_call_and_no_filesystem_change(tmp_path, monkeypatch):
    g = _AllKinds(tmp_path, monkeypatch)
    calls = g.calls()
    before = tree_snapshot(tmp_path)
    with monkeypatch.context() as m:
        trap = mutation_traps(m)
        retry = run(g.orchestrator.preview_retry(g.result, scope=EVERY_KIND - {K.METADATA_REFETCH}))
    assert trap.calls == [] and tree_snapshot(tmp_path) == before
    assert g.calls() == calls  # engine 0 / image client 0 for PREFLIGHT_RECHECK / FRESH / RESUME / DEFERRED
    assert retry.metadata_batch is g.result.metadata_batch  # the ledger passes through unchanged


def test_metadata_refetch_is_read_only_too(tmp_path, monkeypatch):
    g = _AllKinds(tmp_path, monkeypatch)
    g.corpus.engine.script["FC2-1000003"] = "success"
    before = tree_snapshot(tmp_path)
    with monkeypatch.context() as m:
        trap = mutation_traps(m)
        retry = run(g.orchestrator.preview_retry(g.result, scope=frozenset({K.METADATA_REFETCH})))
    assert trap.calls == [] and tree_snapshot(tmp_path) == before
    assert retry.items[0].state is S.READY and g.corpus.engine.calls[-1] == "FC2-1000003"


@pytest.mark.parametrize("scope, indices", [
    (frozenset({K.RESUME}), [1]),
    (frozenset({K.DEFERRED, K.FRESH_REEXECUTE}), [0, 4]),
    (frozenset({K.PREFLIGHT_RECHECK, K.METADATA_REFETCH}), [2, 3]),
    (frozenset(), []),
])
def test_scope_selects_the_retry_subset(tmp_path, monkeypatch, scope, indices):
    g = _AllKinds(tmp_path, monkeypatch)
    retry = run(g.orchestrator.preview_retry(g.result, scope=scope))
    assert [i.index for i in retry.items] == indices and retry.retry_scope is scope
    assert retry.generation == 1 and _registered(g.result)  # an empty retry is still one round
    round_result = g.orchestrator.execute(retry)
    assert round_result.generation == 1 and round_result.base_result_id == g.result.result_id
    assert round_result.retry_scope is scope and not round_result.is_complete
    merged = merge_retry(g.result, round_result)
    assert merged.generation == 1 and merged.is_complete
    if not indices:
        assert round_result.items == () and round_result.outcome is BatchOutcome.SUCCESS
        assert all(a is b for a, b in zip(merged.items, g.result.items))


class _FrozenSetSubclass(frozenset):
    pass


@pytest.mark.parametrize("scope", [
    {K.RESUME}, (K.RESUME,), [K.RESUME], _FrozenSetSubclass({K.RESUME}), frozenset({"resume"}),
    frozenset({K.RESUME, K.NONE}), frozenset({K.NONE}), "resume", K.RESUME,
])
def test_an_invalid_scope_is_an_input_error_and_consumes_nothing(tmp_path, monkeypatch, scope):
    g = _AllKinds(tmp_path, monkeypatch)
    calls = g.calls()
    with pytest.raises(OrchestrationInputError):
        run(g.orchestrator.preview_retry(g.result, scope=scope))
    assert g.calls() == calls and not _registered(g.result)
    assert run(g.orchestrator.preview_retry(g.result, scope=frozenset({K.RESUME}))).items[0].index == 1


def test_previous_must_be_an_exact_complete_result(tmp_path, monkeypatch):
    g = _AllKinds(tmp_path, monkeypatch)
    for bad in (None, "result", g.preview, object()):
        with pytest.raises(OrchestrationInputError):
            run(g.orchestrator.preview_retry(bad))
    retry = run(g.orchestrator.preview_retry(g.result, scope=frozenset({K.DEFERRED})))
    round_result = g.orchestrator.execute(retry)
    with pytest.raises(OrchestrationInputError):  # a retry round is not complete
        run(g.orchestrator.preview_retry(round_result))
    assert not _registered(round_result)
    other = _AllKinds(tmp_path / "other", monkeypatch)
    with pytest.raises(OrchestrationIntegrityError):  # step 3: a rewritten graph (same result_id)
        run(other.orchestrator.preview_retry(tampered(other.result, batch_size=other.result.batch_size + 1)))
    assert not _registered(other.result)
    assert run(other.orchestrator.preview_retry(other.result)).base_result_id == other.result.result_id


@pytest.mark.parametrize("change", ["library_root", "output_policy", "image_policy", "budget"])
def test_a_configuration_mismatch_is_an_input_error(tmp_path, monkeypatch, change):
    g = _AllKinds(tmp_path, monkeypatch)
    kwargs = {"library_root": dict(library_root=str(tmp_path / "elsewhere")),
              "output_policy": dict(output_policy=OutputPolicy(poster_filename="cover.jpg")),
              "image_policy": dict(image_policy=ImageAcquisitionPolicy(max_redirects=1)),
              "budget": dict(config=OrchestrationConfig(max_retained_artifact_bytes=10 ** 9))}[change]
    calls = g.calls()
    with pytest.raises(OrchestrationInputError):
        run(g.corpus.orchestrator(**kwargs).preview_retry(g.result))
    assert g.calls() == calls and not _registered(g.result)


def test_a_result_is_retried_once_and_the_second_attempt_does_no_work(tmp_path, monkeypatch):
    g = _AllKinds(tmp_path, monkeypatch)
    run(g.orchestrator.preview_retry(g.result))
    calls = g.calls()
    with pytest.raises(OrchestrationConsumedError):
        run(g.orchestrator.preview_retry(g.result))
    assert g.calls() == calls  # rejected at step 6, before any metadata / image / preflight work


def test_busy_first_before_looking_at_the_arguments(tmp_path, monkeypatch):
    g = _AllKinds(tmp_path, monkeypatch)
    gate_holder = {}

    async def scenario():
        baseline = g.corpus.engine.calls.count("FC2-1000003")
        gate_holder["gate"] = g.corpus.engine.gate("FC2-1000003")
        first = asyncio.create_task(g.orchestrator.preview_retry(g.result))
        await _in_flight(g.corpus.engine, "FC2-1000003", baseline)
        for bad in (g.result, None, "junk"):
            with pytest.raises(OrchestrationBusyError):
                await g.orchestrator.preview_retry(bad, scope=object())
        gate_holder["gate"].set()
        return await first

    retry = run(scenario())
    assert [i.index for i in retry.items] == [0, 1, 2, 3, 4] and g.orchestrator._busy is False


@pytest.mark.parametrize("fatal", [KeyboardInterrupt(), SystemExit(2)], ids=["KeyboardInterrupt", "SystemExit"])
def test_a_fatal_during_preview_retry_registers_nothing(tmp_path, monkeypatch, fatal):
    g = _AllKinds(tmp_path, monkeypatch)
    g.corpus.engine.script["FC2-1000003"] = fatal
    with pytest.raises(BaseException) as info:
        run(g.orchestrator.preview_retry(g.result))
    assert info.value is fatal and not _registered(g.result) and g.orchestrator._busy is False
    g.corpus.engine.script["FC2-1000003"] = "success"
    retry = run(g.orchestrator.preview_retry(g.result))
    assert retry.items[2].state is S.READY and _registered(g.result)


def test_an_async_cancellation_during_preview_retry_registers_nothing(tmp_path, monkeypatch):
    g = _AllKinds(tmp_path, monkeypatch)

    async def scenario():
        baseline = g.corpus.engine.calls.count("FC2-1000003")
        g.corpus.engine.gate("FC2-1000003")  # held forever: the call is in flight when we cancel
        task = asyncio.create_task(g.orchestrator.preview_retry(g.result))
        await _in_flight(g.corpus.engine, "FC2-1000003", baseline)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    run(scenario())
    g.corpus.engine.gates.clear()
    assert not _registered(g.result) and g.orchestrator._busy is False and "FC2-1000003" in g.corpus.engine.cancelled
    retry = run(g.orchestrator.preview_retry(g.result))
    assert [i.index for i in retry.items] == [0, 1, 2, 3, 4]


def test_a_forged_metadata_ledger_breaks_the_index_consistency_check(tmp_path, monkeypatch):
    g = _AllKinds(tmp_path, monkeypatch)
    ledger = g.result.metadata_batch
    first = ledger.items[0]  # a SUCCESS item presented as FAILED: retry_failed would re-run it too
    fake = BatchItemResult(index=first.index, number=first.number, status=BatchItemStatus.FAILED,
                           aggregation_result=build_metadata(first.number, "failed"), generation=0)
    forged = tampered(g.result, metadata_batch=BatchResult(items=(fake, *ledger.items[1:]),
                                                           generation=ledger.generation, lineage=ledger.lineage))
    with pytest.raises(OrchestrationIntegrityError):
        run(g.orchestrator.preview_retry(forged))
    assert not _registered(g.result)
    assert run(g.orchestrator.preview_retry(g.result)).items[2].retry_origin is K.METADATA_REFETCH


def test_a_consumed_checkpoint_is_checkpoint_rejected_then_not_retryable(tmp_path, monkeypatch):
    g = _AllKinds(tmp_path, monkeypatch)
    material = g.result.items[1].retry_material
    assert execute_filesystem(preflight_execution(material.plan, material.artifacts,
                                                  material.checkpoint)).status is ExecutionStatus.SUCCESS
    retry = run(g.orchestrator.preview_retry(g.result, scope=frozenset({K.RESUME})))
    item = retry.items[0]
    assert item.state is S.UNPREPARED and item.issue.reason is R.CHECKPOINT_REJECTED
    assert item.issue.detail is CheckpointRejectionReason.CONSUMED
    round_result = g.orchestrator.execute(retry)
    assert round_result.items[0].retry_kind is K.NONE and round_result.outcome is BatchOutcome.FAILED


def test_base_retained_counts_only_items_outside_the_retry_subset(tmp_path, monkeypatch):
    g = _AllKinds(tmp_path, monkeypatch)
    B = g.result.retention_budget_bytes
    pay = {i.index: sum(len(r.content) for r in i.retry_material.artifacts)
           for i in g.result.items if i.retry_material is not None}
    assert sorted(pay) == [0, 1, 3, 4]
    everything = run(g.orchestrator.preview_retry(g.result, scope=EVERY_KIND - {K.METADATA_REFETCH}))
    assert everything.retry_budget_bytes == B  # R's own old material is replaced, never counted

    other = _AllKinds(tmp_path / "other", monkeypatch)
    pay = {i.index: sum(len(r.content) for r in i.retry_material.artifacts)
           for i in other.result.items if i.retry_material is not None}
    only_resume = run(other.orchestrator.preview_retry(other.result, scope=frozenset({K.RESUME})))
    assert only_resume.retry_budget_bytes == B - pay[0] - pay[3] - pay[4]
    assert only_resume.retained_artifact_bytes == pay[1] <= only_resume.retry_budget_bytes


def test_phase_b_conflicts_are_detected_inside_the_retry_subset_only(tmp_path):
    corpus = Corpus(tmp_path, [Film("FC2-PPV-1000001.mp4"), Film("FC2-PPV-1000002.mp4", kind="failed")])
    first, second = (os.path.join(str(corpus.downloads), n) for n in ("FC2-PPV-1000001.mp4", "FC2-PPV-1000002.mp4"))
    os.remove(second)
    os.link(first, second)  # two names, one source file: a same-source conflict hidden behind metadata
    corpus.items = discover_media(str(corpus.downloads)).items
    orchestrator = corpus.orchestrator()
    preview = run(orchestrator.preview(corpus.items))
    assert [i.state for i in preview.items] == [S.READY, S.UNPREPARED]
    result = orchestrator.execute(preview, selection=())
    corpus.engine.script["FC2-1000002"] = "success"
    alone = run(orchestrator.preview_retry(result, scope=frozenset({K.METADATA_REFETCH})))
    assert alone.items[0].state is S.READY  # its peer is not in R: not considered

    other = Corpus(tmp_path / "b", [Film("FC2-PPV-1000001.mp4"), Film("FC2-PPV-1000002.mp4", kind="failed")])
    a, b = (os.path.join(str(other.downloads), n) for n in ("FC2-PPV-1000001.mp4", "FC2-PPV-1000002.mp4"))
    os.remove(b)
    os.link(a, b)
    other.items = discover_media(str(other.downloads)).items
    orchestrator = other.orchestrator()
    result = orchestrator.execute(run(orchestrator.preview(other.items)), selection=())
    other.engine.script["FC2-1000002"] = "success"
    both = run(orchestrator.preview_retry(result))
    assert [(i.index, i.state, i.issue.reason, i.conflict_with) for i in both.items] == [
        (0, S.BLOCKED, R.DUPLICATE_SOURCE_IN_BATCH, (1,)), (1, S.BLOCKED, R.DUPLICATE_SOURCE_IN_BATCH, (0,))]


# --------------------------------------------------------------------------- retained-material metering


def _metering(tmp_path, monkeypatch, delta: int):
    """0 PARTIAL (RESUME, checkpoint), 1 metadata FAILED; poster only; ``R = I``;
    ``B = pay(0) + need(1) + delta`` with ``pay = L + I`` and ``need = 4 * L + I``."""
    films = [Film("FC2-PPV-1000001.mp4", fanart=False, thumb=False),
             Film("FC2-PPV-1000002.mp4", kind="success", fanart=False, thumb=False)]
    probe = Corpus(tmp_path / "probe", films)
    calibration = run(probe.orchestrator().preview(probe.items))
    lengths = {r.kind: len(r.content) for r in calibration.items[1].preflight.artifacts}
    nfo, image = lengths[ArtifactKind.NFO], lengths[ArtifactKind.POSTER]
    assert {r.kind: len(r.content) for r in calibration.items[0].preflight.artifacts} == lengths
    budget = (nfo + image) + (4 * nfo + image) + delta
    films[1] = Film("FC2-PPV-1000002.mp4", kind="failed", fanart=False, thumb=False)
    corpus = Corpus(tmp_path / "lineage", films)
    policy = ImageAcquisitionPolicy(max_image_bytes=image, max_total_bytes=image)
    config = OrchestrationConfig(metadata=BatchConfig(max_in_flight_items=1), image_in_flight_items=1,
                                 max_retained_artifact_bytes=budget)
    orchestrator = corpus.orchestrator(image_policy=policy, config=config)
    preview = run(orchestrator.preview(corpus.items))
    with monkeypatch.context() as m:
        fault = fs_fault(m)
        fault.fail("materialization", "publish", os.path.basename(preview.items[0].nfo_target),
                   OSError(errno.EIO, "io"))
        result = orchestrator.execute(preview)
    assert [i.retry_kind for i in result.items] == [K.RESUME, K.METADATA_REFETCH]
    corpus.engine.script["FC2-1000002"] = "success"
    return corpus, orchestrator, result, nfo + image


def test_retained_material_plus_new_payload_exactly_at_the_budget_is_accepted(tmp_path, monkeypatch):
    corpus, orchestrator, result, pay = _metering(tmp_path, monkeypatch, 0)
    retry = run(orchestrator.preview_retry(result))
    assert retry.retry_budget_bytes == result.retention_budget_bytes
    assert retry.retained_artifact_bytes == 2 * pay  # recovered item: NFO + image bytes, as in a preview
    final = merge_retry(result, orchestrator.execute(retry))
    assert final.outcome is BatchOutcome.SUCCESS


def test_one_byte_over_the_available_budget_fails_closed_and_the_checkpoint_survives(tmp_path, monkeypatch):
    corpus, orchestrator, result, pay = _metering(tmp_path, monkeypatch, -1)
    snapshot = tree_snapshot(corpus.root)
    outcome = []
    with pytest.raises(OrchestrationResourceLimitError) as info:
        outcome.append(run(orchestrator.preview_retry(result)))
    assert info.value.reason is ResourceLimitReason.RETAINED_BYTES_LIMIT and outcome == []
    assert not _registered(result) and orchestrator._busy is False and tree_snapshot(corpus.root) == snapshot
    retry = run(orchestrator.preview_retry(result, scope=frozenset({K.RESUME})))  # narrower scope
    assert retry.items[0].preflight.checkpoint is result.items[0].execution.checkpoint
    round_result = orchestrator.execute(retry)
    assert round_result.items[0].execution_status is ExecutionStatus.SUCCESS  # the checkpoint was not consumed
    assert round_result.outcome is BatchOutcome.SUCCESS
    merged = merge_retry(result, round_result)
    assert merged.outcome is BatchOutcome.PARTIAL and merged.items[1].retry_kind is K.METADATA_REFETCH
    assert merged.items[0].disposition is D.EXECUTED
