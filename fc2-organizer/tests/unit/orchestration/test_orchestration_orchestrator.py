"""P4-C8 S2: ``BatchOrchestrator`` construction and the busy-first guard (contract sections 7.2, 7.3)."""

from __future__ import annotations

import asyncio
import dataclasses
import threading

import pytest

from fc2_metadata_core.batch import BatchConfig
from fc2_organizer.images import ImageAcquisitionPolicy
from fc2_organizer.orchestration import (
    MAX_ITEM_IMAGE_BYTES,
    BatchOrchestrator,
    BatchPreview,
    OrchestrationBusyError,
    OrchestrationConfig,
    OrchestrationConfigError,
    OrchestrationInputError,
)
from fc2_organizer.planning import OutputPolicy

from ._fakes import ScriptedEngine, ScriptedImageClient
from ._helpers import LIBRARY, Corpus, Film, mutation_traps, run


def _valid_policy(max_total: int) -> ImageAcquisitionPolicy:
    return ImageAcquisitionPolicy(max_image_bytes=min(max_total, ImageAcquisitionPolicy().max_image_bytes),
                                  max_total_bytes=max_total)


# =========================================================================== construction (7.2)


def test_defaults_and_read_only_properties():
    orchestrator = BatchOrchestrator(ScriptedEngine(), ScriptedImageClient(), LIBRARY)
    assert orchestrator.config == OrchestrationConfig() and type(orchestrator.config) is OrchestrationConfig
    assert orchestrator.library_root == LIBRARY
    assert orchestrator.output_policy == OutputPolicy() and orchestrator.image_policy == ImageAcquisitionPolicy()
    for name in ("config", "library_root", "output_policy", "image_policy"):
        with pytest.raises(AttributeError):
            setattr(orchestrator, name, None)


def test_explicit_arguments_are_kept():
    config = OrchestrationConfig(metadata=BatchConfig(max_in_flight_items=2), image_in_flight_items=3)
    output_policy, image_policy = OutputPolicy(), _valid_policy(1000)
    orchestrator = BatchOrchestrator(ScriptedEngine(), ScriptedImageClient(), LIBRARY, output_policy=output_policy,
                                     image_policy=image_policy, config=config)
    assert orchestrator.config is config and orchestrator.output_policy is output_policy
    assert orchestrator.image_policy is image_policy


class _SyncEngine:
    def aggregate(self, number):  # not async
        return None


class _NoGetClient:
    pass


class _NotCallableGet:
    get = 3


@pytest.mark.parametrize("engine", [_SyncEngine(), object(), None])
def test_engine_without_async_aggregate_is_rejected_unchained(engine):
    with pytest.raises(OrchestrationConfigError) as info:
        BatchOrchestrator(engine, ScriptedImageClient(), LIBRARY)
    assert info.value.__cause__ is None and info.value.__context__ is None


@pytest.mark.parametrize("client", [_NoGetClient(), _NotCallableGet(), None])
def test_image_client_without_callable_get_is_rejected(client):
    with pytest.raises(OrchestrationConfigError):
        BatchOrchestrator(ScriptedEngine(), client, LIBRARY)


class _StrSub(str):
    pass


@pytest.mark.parametrize("root", ["", None, 3, b"C:\\lib", _StrSub(LIBRARY)])
def test_library_root_must_be_a_non_empty_exact_str(root):
    with pytest.raises(OrchestrationConfigError):
        BatchOrchestrator(ScriptedEngine(), ScriptedImageClient(), root)


def test_relative_library_root_is_accepted_at_construction():
    # Semantic library_root validation is P4-C2's, per item (contract section 15.3).
    assert BatchOrchestrator(ScriptedEngine(), ScriptedImageClient(), "relative/lib").library_root == "relative/lib"


def test_policy_and_config_must_be_exact_types():
    class Out(OutputPolicy):
        pass

    class Img(ImageAcquisitionPolicy):
        pass

    for kwargs in (dict(output_policy=Out()), dict(output_policy={}), dict(image_policy=Img()),
                   dict(image_policy=object()), dict(config=BatchConfig()), dict(config={"filesystem_workers": 1}),
                   dict(config=dataclasses.replace(OrchestrationConfig()).metadata)):
        with pytest.raises(OrchestrationConfigError):
            BatchOrchestrator(ScriptedEngine(), ScriptedImageClient(), LIBRARY, **kwargs)


def test_image_policy_total_is_capped_at_max_item_image_bytes():
    at_limit = _valid_policy(MAX_ITEM_IMAGE_BYTES)
    assert BatchOrchestrator(ScriptedEngine(), ScriptedImageClient(), LIBRARY,
                             image_policy=at_limit).image_policy is at_limit
    with pytest.raises(OrchestrationConfigError) as info:
        BatchOrchestrator(ScriptedEngine(), ScriptedImageClient(), LIBRARY,
                          image_policy=_valid_policy(MAX_ITEM_IMAGE_BYTES + 1))
    assert info.value.__context__ is None


def test_construction_touches_no_network_and_no_filesystem(monkeypatch):
    engine, client = ScriptedEngine(), ScriptedImageClient()
    trap = mutation_traps(monkeypatch)
    import os

    reads: list[str] = []
    for name in ("lstat", "stat", "scandir", "listdir"):
        real = getattr(os, name)
        monkeypatch.setattr(os, name, lambda *a, _n=name, _r=real, **k: (reads.append(_n), _r(*a, **k))[1])
    BatchOrchestrator(engine, client, LIBRARY)
    assert engine.calls == [] and client.calls == [] and trap.calls == [] and reads == []


def test_no_execute_or_retry_api_in_s2():
    for name in ("execute", "preview_retry", "merge_retry", "summary"):
        assert not hasattr(BatchOrchestrator, name), name


# =========================================================================== busy-first (7.3)


async def _hold_first_preview(corpus, orchestrator):
    """Start a preview and wait (by loop iterations) until it is inside the metadata stage."""
    release = corpus.engine.gate("FC2-1000001")
    first = asyncio.ensure_future(orchestrator.preview(corpus.items))
    for _ in range(10_000):
        if corpus.engine.calls:
            break
        await asyncio.sleep(0)
    assert corpus.engine.calls == ["FC2-1000001"]
    return first, release


@pytest.mark.parametrize("second_argument", ["valid", "invalid", "empty", "missing-container"])
def test_second_preview_is_busy_first_whatever_its_argument(tmp_path, second_argument):
    corpus = Corpus(tmp_path, [Film("FC2-PPV-1000001.mp4")])
    orchestrator = corpus.orchestrator()
    argument = {"valid": corpus.items, "invalid": "not a sequence", "empty": (), "missing-container": None}[
        second_argument]

    async def scenario():
        first, release = await _hold_first_preview(corpus, orchestrator)
        with pytest.raises(OrchestrationBusyError) as info:
            await orchestrator.preview(argument)
        assert info.value.__context__ is None
        with pytest.raises(OrchestrationBusyError):  # the rejected call did not release the claim
            await orchestrator.preview(corpus.items)
        release.set()
        preview = await first
        assert type(preview) is BatchPreview
        again = await orchestrator.preview(corpus.items)  # idle again after completion
        return again

    assert type(run(scenario())) is BatchPreview
    assert corpus.engine.calls == ["FC2-1000001", "FC2-1000001"]


def test_busy_from_another_thread_and_event_loop(tmp_path):
    corpus = Corpus(tmp_path, [Film("FC2-PPV-1000001.mp4")])
    orchestrator = corpus.orchestrator()
    outcome: list[object] = []

    async def scenario():
        first, release = await _hold_first_preview(corpus, orchestrator)

        def other_thread():
            try:
                asyncio.run(orchestrator.preview(()))
                outcome.append("ran")
            except OrchestrationBusyError as error:
                outcome.append(type(error))

        thread = threading.Thread(target=other_thread)
        thread.start()
        thread.join()
        release.set()
        await first

    run(scenario())
    assert outcome == [OrchestrationBusyError]


def test_invalid_input_on_an_idle_orchestrator_is_an_input_error_and_stays_idle(tmp_path):
    corpus = Corpus(tmp_path, [Film("FC2-PPV-1000001.mp4")])
    orchestrator = corpus.orchestrator()
    for bad in ("text", None, [object()], {1: 2}):
        with pytest.raises(OrchestrationInputError):
            run(orchestrator.preview(bad))
    assert corpus.engine.calls == [] and corpus.client.calls == []
    assert type(run(orchestrator.preview(corpus.items))) is BatchPreview


def test_busy_regression_detector_does_not_hang_and_detects_a_broken_guard(tmp_path, monkeypatch):
    """Watchdog + control (Phase 3 C4-R1-04 shape): with the guard disabled, the detector reports the
    violation instead of hanging; with the real guard, it reports compliance."""

    def detects_busy(orchestrator, corpus) -> bool:
        async def scenario():
            first, release = await _hold_first_preview(corpus, orchestrator)
            try:
                second = asyncio.ensure_future(orchestrator.preview(()))
                done, _ = await asyncio.wait({second}, timeout=5)
                ok = bool(done) and isinstance(second.exception(), OrchestrationBusyError)
                if not done:
                    second.cancel()
                    await asyncio.gather(second, return_exceptions=True)
                return ok
            finally:
                release.set()
                await asyncio.gather(first, return_exceptions=True)

        return run(scenario(), timeout=30)

    corpus = Corpus(tmp_path / "a", [Film("FC2-PPV-1000001.mp4")])
    assert detects_busy(corpus.orchestrator(), corpus) is True
    broken = Corpus(tmp_path / "b", [Film("FC2-PPV-1000001.mp4")])
    orchestrator = broken.orchestrator()
    monkeypatch.setattr(BatchOrchestrator, "_claim", lambda self: None)
    assert detects_busy(orchestrator, broken) is False


def test_guard_is_released_after_every_exit_path(tmp_path, monkeypatch):
    corpus = Corpus(tmp_path, [Film("FC2-PPV-1000001.mp4")])
    orchestrator = corpus.orchestrator()
    with pytest.raises(OrchestrationInputError):  # ordinary error
        run(orchestrator.preview([object()]))

    async def cancelled():
        corpus.engine.gate("FC2-1000001")
        task = asyncio.ensure_future(orchestrator.preview(corpus.items))
        for _ in range(10_000):
            if corpus.engine.calls:
                break
            await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    run(cancelled())  # caller cancellation
    assert orchestrator._busy is False
    corpus.engine.gates.clear()
    assert type(run(orchestrator.preview(corpus.items))) is BatchPreview  # normal return
    assert orchestrator._busy is False
