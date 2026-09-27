"""P4-C8 S2: preview fatal boundary and caller cancellation (contract sections 20.2, 27.2)."""

from __future__ import annotations

import asyncio

import pytest

from fc2_metadata_core.batch import BatchConfig
from fc2_organizer.orchestration import BatchPreview, OrchestrationConfig
from fc2_organizer.orchestration import stages

from support.batch_fakes import until

from ._helpers import Corpus, Film, image_url, mutation_traps, run, tree_snapshot


class _HostileMeta(type):
    @property
    def __name__(cls):  # pragma: no cover - must never run
        raise AssertionError("fatal metadata read")


class _HostileFatal(BaseException, metaclass=_HostileMeta):
    def __str__(self):  # pragma: no cover
        raise AssertionError("fatal str read")

    def __repr__(self):  # pragma: no cover
        raise AssertionError("fatal repr read")

    @property
    def args(self):  # pragma: no cover
        raise AssertionError("fatal args read")


class _Custom(BaseException):
    pass


def _fatals():
    return [KeyboardInterrupt(), SystemExit(3), GeneratorExit(), _Custom(), _HostileFatal(),
            asyncio.CancelledError()]


FATAL_IDS = ["KeyboardInterrupt", "SystemExit", "GeneratorExit", "custom", "hostile", "self-cancelled"]


def _films(count: int = 3) -> list[Film]:
    return [Film(f"FC2-PPV-{1000001 + i}.mp4") for i in range(count)]


def _config(m: int = 4, k: int = 1) -> OrchestrationConfig:
    return OrchestrationConfig(metadata=BatchConfig(max_in_flight_items=m), image_in_flight_items=k)


def _stray_workers() -> list[asyncio.Task]:
    names = {"_image_worker", "_worker"}
    return [t for t in asyncio.all_tasks() if not t.done() and getattr(t.get_coro(), "__name__", "") in names]


async def _expect_fatal(orchestrator, items, fatal):
    with pytest.raises(BaseException) as info:
        await orchestrator.preview(items)
    assert info.value is fatal  # the ORIGINAL object, never a group, never an item result
    assert _stray_workers() == []
    assert orchestrator._busy is False


def _assert_idle_and_reusable(corpus, orchestrator) -> None:
    from ._fakes import jpeg_response

    corpus.engine.script.update({n: "success" for n in list(corpus.engine.script)})
    for url, answer in list(corpus.client.script.items()):
        if isinstance(answer, BaseException):
            corpus.client.script[url] = jpeg_response()
    corpus.engine.gates.clear()
    corpus.client.gates.clear()
    assert type(run(orchestrator.preview(corpus.items))) is BatchPreview


# =========================================================================== caller cancellation


def test_caller_cancellation_during_metadata(tmp_path, monkeypatch):
    corpus = Corpus(tmp_path, _films())
    orchestrator = corpus.orchestrator(config=_config(m=2))
    before = tree_snapshot(tmp_path)

    async def scenario():
        for number in corpus.engine.script:
            corpus.engine.gate(number)
        task = asyncio.ensure_future(orchestrator.preview(corpus.items))
        await until(lambda: corpus.engine.active == 2)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert _stray_workers() == [] and orchestrator._busy is False

    trap = mutation_traps(monkeypatch)
    run(scenario())
    assert trap.calls == []
    monkeypatch.undo()
    assert sorted(corpus.engine.cancelled) == ["FC2-1000001", "FC2-1000002"]
    assert "FC2-1000003" not in corpus.engine.calls and corpus.client.calls == []
    assert tree_snapshot(tmp_path) == before
    _assert_idle_and_reusable(corpus, orchestrator)


def test_caller_cancellation_during_images(tmp_path):
    corpus = Corpus(tmp_path, _films(4))
    orchestrator = corpus.orchestrator(config=_config(k=2))

    async def scenario():
        for number in ("FC2-1000001", "FC2-1000002"):
            corpus.client.gate(image_url(number, "poster"))
        task = asyncio.ensure_future(orchestrator.preview(corpus.items))
        await until(lambda: corpus.client.active == 2)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert _stray_workers() == [] and orchestrator._busy is False

    run(scenario())
    assert sorted(corpus.client.cancelled) == [image_url("FC2-1000001", "poster"), image_url("FC2-1000002", "poster")]
    assert not [u for u in corpus.client.calls if "FC2-1000003" in u or "FC2-1000004" in u]
    _assert_idle_and_reusable(corpus, orchestrator)


# =========================================================================== fatal from the engine (Phase 3 boundary)


@pytest.mark.parametrize("index", range(6), ids=FATAL_IDS)
def test_fatal_from_the_engine_propagates_the_original_object(tmp_path, index):
    fatal = _fatals()[index]
    corpus = Corpus(tmp_path, _films())
    corpus.engine.script["FC2-1000002"] = fatal
    orchestrator = corpus.orchestrator(config=_config(m=1))
    run(_expect_fatal(orchestrator, corpus.items, fatal))
    assert "FC2-1000003" not in corpus.engine.calls  # no admission after the fatal signal
    assert corpus.client.calls == []
    _assert_idle_and_reusable(corpus, orchestrator)


# =========================================================================== fatal from the image client


@pytest.mark.parametrize("index", range(6), ids=FATAL_IDS)
def test_fatal_from_the_image_client_stops_admission_k1(tmp_path, index):
    fatal = _fatals()[index]
    corpus = Corpus(tmp_path, _films())
    corpus.client.script[image_url("FC2-1000001", "fanart")] = fatal
    orchestrator = corpus.orchestrator(config=_config(k=1))
    run(_expect_fatal(orchestrator, corpus.items, fatal))
    assert corpus.client.calls == [image_url("FC2-1000001", "poster"), image_url("FC2-1000001", "fanart")]
    _assert_idle_and_reusable(corpus, orchestrator)


@pytest.mark.parametrize("index", range(6), ids=FATAL_IDS)
def test_fatal_from_the_image_client_cancels_and_awaits_siblings(tmp_path, index):
    fatal = _fatals()[index]
    corpus = Corpus(tmp_path, _films(4))
    orchestrator = corpus.orchestrator(config=_config(k=2))

    async def scenario():
        sibling = image_url("FC2-1000002", "poster")
        corpus.client.gate(sibling)
        failing = image_url("FC2-1000001", "poster")
        release = corpus.client.gate(failing)
        corpus.client.script[failing] = fatal
        task = asyncio.ensure_future(_expect_fatal(orchestrator, corpus.items, fatal))
        await until(lambda: corpus.client.active == 2)
        release.set()
        await task
        assert sibling in corpus.client.cancelled and set(corpus.client.cancelled) <= {sibling, failing}

    run(scenario())
    assert not [u for u in corpus.client.calls if "FC2-1000003" in u or "FC2-1000004" in u]
    _assert_idle_and_reusable(corpus, orchestrator)


def test_image_client_cancelled_error_is_fatal_not_an_item_failure(tmp_path):
    own = asyncio.CancelledError()
    corpus = Corpus(tmp_path, _films(2))
    corpus.client.script[image_url("FC2-1000001", "poster")] = own
    orchestrator = corpus.orchestrator(config=_config(k=1))
    run(_expect_fatal(orchestrator, corpus.items, own))


# =========================================================================== fatal from a synchronous stage


@pytest.mark.parametrize("name", ["build_organize_plan", "render_movie_nfo", "build_artifact_requests",
                                  "preflight_execution"])
@pytest.mark.parametrize("index", range(5), ids=FATAL_IDS[:5])
def test_fatal_from_a_synchronous_stage_propagates(tmp_path, monkeypatch, name, index):
    fatal = _fatals()[index]
    corpus = Corpus(tmp_path, _films())

    def raiser(*_args, **_kwargs):
        raise fatal

    monkeypatch.setattr(stages, name, raiser)
    orchestrator = corpus.orchestrator()
    run(_expect_fatal(orchestrator, corpus.items, fatal))
    if name in ("build_organize_plan", "render_movie_nfo"):
        assert corpus.client.calls == []  # stopped before the image stage
    monkeypatch.undo()
    _assert_idle_and_reusable(corpus, orchestrator)
