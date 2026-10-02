"""P4-C8 S5: determinism (contract section 29).

One mixed batch -- every stage succeeding and failing, warnings, a Phase A conflict pair, execution faults, a
not-selected item -- runs ``preview -> execute -> preview_retry -> execute -> merge_retry`` several times: twice
identically, once with the engine / image / execution completion order reversed (gates released last-started
first; a barrier holds every execution in flight), and with other ``M`` / ``K`` / ``W``. The deterministic
projections (``_helpers.projection``: everything except ids, lineage token, preflight / checkpoint ids and seals)
and the summaries are equal item by item. Each run lives in its own root; the only normalisation is replacing
that root path by a placeholder.
"""

from __future__ import annotations

import asyncio
import errno
import os
import threading

from fc2_metadata_core.batch import BatchConfig
from fc2_organizer.execution import execute_filesystem
from fc2_organizer.images import ImageInputError
from fc2_organizer.materialization import ArtifactMappingError, MappingRejectionReason
from fc2_organizer.orchestration import (
    OrchestrationConfig,
    PreviewState as S,
    RetryKind as K,
    merge_retry,
)
from fc2_organizer.orchestration import execute as execute_module
from fc2_organizer.orchestration import preview as preview_module
from fc2_organizer.orchestration import stages

from ._helpers import Corpus, Film, assert_source_not_lost, by_name, fs_fault, projection, run

WAIT = 30.0
FILMS = [
    Film("FC2-PPV-1000001.mp4", extra=2),                         # READY, executes
    Film("FC2-PPV-1000002.mp4", kind="partial", extra_fail=1),     # READY, metadata PARTIAL + candidate failure
    Film("FC2-PPV-1000003.mp4", fanart=False),                    # READY, image absence warning
    Film("junk-video.mp4"),                                        # number not recognised
    Film("FC2-PPV-1000004.mp4"), Film("FC2PPV1000004.mkv", directory="other"),  # Phase A conflict pair
    Film("FC2-PPV-1000005.mp4", kind="failed"),                   # metadata unavailable (recovers on retry)
    Film("FC2-PPV-1000006.mp4", kind="engine"),                   # engine exception
    Film("FC2-PPV-1000007.mp4", kind="mismatch"),                 # result contract mismatch
    Film("FC2-PPV-1000008.mp4", release="2024-13-45"),            # NFO render failure
    Film("FC2-PPV-1000009.mp4"),                                  # image stage error (injected)
    Film("FC2-PPV-1000010.mp4"),                                  # manifest rejected (injected)
    Film("FC2-PPV-1000011.mp4"),                                  # preflight blocked (target exists)
    Film("FC2-PPV-1000012.mp4"),                                  # execution FAILED (U1 fault)
    Film("FC2-PPV-1000013.mp4"),                                  # execution PARTIAL (NFO publish fault)
    Film("FC2-PPV-1000014.mp4"),                                  # READY, not selected
]


def _inject_stage_failures(monkeypatch) -> None:
    real_acquire = preview_module.acquire_images
    real_mapping = stages.build_artifact_requests

    async def acquire(record, client, *, policy=None):
        if record.plan.canonical_number == "FC2-1000009":
            raise ImageInputError("forged candidate collection")
        return await real_acquire(record, client, policy=policy)

    def mapping(plan, nfo_text, images):
        if plan.canonical_number == "FC2-1000010":
            raise ArtifactMappingError(MappingRejectionReason.DUPLICATE_TARGET)
        return real_mapping(plan, nfo_text, images)

    monkeypatch.setattr(preview_module, "acquire_images", acquire)
    monkeypatch.setattr(stages, "build_artifact_requests", mapping)


async def _reverse_release(recorder, task) -> None:
    """Release gated calls last-started first while ``task`` runs (yield only; never a timed wait)."""
    released: set[str] = set()
    for _ in range(1_000_000):
        if task.done():
            return
        started = [key for key in recorder.calls if key in recorder.gates and key not in released]
        if started:
            key = started[-1]
            recorder.gates[key].set()
            released.add(key)
        await asyncio.sleep(0)
    raise AssertionError("the reverse release controller did not finish")


async def _preview(corpus, orchestrator, reverse: bool):
    if not reverse:
        return await orchestrator.preview(corpus.items)
    for number in corpus.engine.script:
        corpus.engine.gate(number)
    for url in corpus.client.script:
        corpus.client.gate(url)
    task = asyncio.ensure_future(orchestrator.preview(corpus.items))
    await asyncio.gather(_reverse_release(corpus.engine, task), _reverse_release(corpus.client, task))
    return await task


def _reverse_execution(monkeypatch, count: int) -> list[str]:
    """Every selected execution waits at a barrier, then they finish in reverse start order."""
    arrived = threading.Barrier(count)
    lock = threading.Lock()
    order: list[str] = []
    started: list[str] = []
    finished: list[str] = []
    turn = threading.Condition(lock)

    def gated(preflight):
        with lock:
            order.append(preflight.preflight_id)
            started.append(preflight.preflight_id)
        arrived.wait(WAIT)
        with turn:
            assert turn.wait_for(lambda: order[-1] == preflight.preflight_id, WAIT)
        try:
            return execute_filesystem(preflight)
        finally:
            with turn:
                order.remove(preflight.preflight_id)
                finished.append(preflight.preflight_id)
                turn.notify_all()

    monkeypatch.setattr(execute_module, "execute_filesystem", gated)
    return started, finished


def _scenario(root, monkeypatch, *, m: int, k: int, w: int, reverse: bool):
    corpus = Corpus(root, list(FILMS))
    (corpus.library / "FC2-1000011").mkdir()
    hashes = {}
    for item in corpus.items:
        with open(item.source_path, "rb") as handle:
            hashes[item.source_path] = handle.read()
    config = OrchestrationConfig(metadata=BatchConfig(max_in_flight_items=m), image_in_flight_items=k,
                                 filesystem_workers=w)
    orchestrator = corpus.orchestrator(config=config)
    with monkeypatch.context() as patched:
        _inject_stage_failures(patched)
        preview = run(_preview(corpus, orchestrator, reverse))
    corpus.engine.gates.clear()
    corpus.client.gates.clear()
    items = by_name(preview)
    selection = tuple(sorted(i.index for name, i in items.items()
                             if i.state is S.READY and name != "FC2-PPV-1000014.mp4"))
    with monkeypatch.context() as patched:
        fault = fs_fault(patched)
        fault.fail("execution", "mkdir", items["FC2-PPV-1000012.mp4"].target_directory, OSError(errno.EACCES, "no"))
        fault.fail("materialization", "publish", os.path.basename(items["FC2-PPV-1000013.mp4"].nfo_target),
                   OSError(errno.EIO, "io"))
        orders = _reverse_execution(patched, len(selection)) if reverse else None
        result = orchestrator.execute(preview, selection=selection)
    corpus.engine.script["FC2-1000005"] = "success"
    retry = run(orchestrator.preview_retry(result))
    round_result = orchestrator.execute(retry)
    merged = merge_retry(result, round_result)
    for item in merged.items:  # the core invariant after every run
        assert_source_not_lost(item.source_path, item.final_media_path, _digest(hashes[item.source_path]))
    if reverse:  # evidence that the completion orders really were reversed
        assert corpus.engine.completed != corpus.engine.calls[:len(corpus.engine.completed)]
        assert corpus.client.completed != corpus.client.calls[:len(corpus.client.completed)]
        started, finished = orders
        assert len(started) == len(selection) and finished == list(reversed(started))
    return root, (preview, result, retry, round_result, merged)


def _digest(content: bytes) -> str:
    import hashlib

    return hashlib.sha256(content).hexdigest()


def _normalised(root, models) -> list[str]:
    text = str(root)
    out = []
    for model in models:
        shown = repr(projection(model)) + repr(model.summary)
        out.append(shown.replace(text.replace("\\", "\\\\"), "<ROOT>").replace(text, "<ROOT>"))
    return out


def test_the_mixed_batch_is_deterministic_across_runs_orders_and_budgets(tmp_path, monkeypatch):
    runs = {
        "baseline": dict(m=1, k=1, w=1, reverse=False),
        "repeat": dict(m=1, k=1, w=1, reverse=False),
        "reversed": dict(m=4, k=4, w=5, reverse=True),
        "other_budgets": dict(m=2, k=3, w=2, reverse=False),
    }
    observed = {}
    for name, options in runs.items():
        root, models = _scenario(tmp_path / name, monkeypatch, **options)
        observed[name] = (_normalised(root, models), models)
    baseline_text, baseline_models = observed["baseline"]
    for name in ("repeat", "reversed", "other_budgets"):
        text, models = observed[name]
        for position, (expected, actual) in enumerate(zip(baseline_text, text)):
            assert actual == expected, (name, position)
    preview, result, retry, round_result, merged = baseline_models
    # the batch really exercises what the comparison claims
    assert {i.state for i in preview.items} == {S.READY, S.BLOCKED, S.UNPREPARED}
    assert any(i.warnings for i in preview.items) and any(i.conflict_with for i in preview.items)
    assert {i.retry_kind for i in result.items} >= {K.NONE, K.RESUME, K.FRESH_REEXECUTE, K.METADATA_REFETCH,
                                                    K.PREFLIGHT_RECHECK, K.DEFERRED}
    assert [i.index for i in retry.items] == sorted(i.index for i in retry.items)  # retry subset in index order
    assert result.summary.executed == 5 and merged.summary.success >= 6
