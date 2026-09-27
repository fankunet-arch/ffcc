"""P4-C8 S2: bounded preview concurrency and determinism (contract sections 13, 19.1, 19.2, 29).

Completion order is controlled with ``asyncio.Event`` gates released by a controller task; loops wait by
loop iterations (``support.batch_fakes.until``), never by wall-clock sleeps.
"""

from __future__ import annotations

import asyncio

import pytest

from fc2_metadata_core.batch import BatchConfig
from fc2_organizer.orchestration import OrchestrationConfig, PreviewState as S
from fc2_organizer.orchestration import preview as preview_module

from support.batch_fakes import until

from ._helpers import Corpus, Film, image_url, projection, run

N = 6


def _films(count: int = N) -> list[Film]:
    return [Film(f"FC2-PPV-{1000001 + i}.mp4", extra=1) for i in range(count)]


def _numbers(count: int = N) -> list[str]:
    return [f"FC2-{1000001 + i}" for i in range(count)]


def _config(m: int = 4, k: int = 4) -> OrchestrationConfig:
    return OrchestrationConfig(metadata=BatchConfig(max_in_flight_items=m), image_in_flight_items=k)


@pytest.mark.parametrize("m", [1, 2, 4, 8])
def test_metadata_peak_is_bounded_by_m_and_reached(tmp_path, m):
    corpus = Corpus(tmp_path, _films())
    preview = corpus.preview(corpus.orchestrator(config=_config(m=m)))
    assert corpus.engine.peak == min(m, N)
    assert sorted(corpus.engine.calls) == _numbers() and len(corpus.engine.calls) == N
    assert all(i.state is S.READY for i in preview.items)


@pytest.mark.parametrize("k", [1, 2, 4, 16])
def test_image_peak_is_bounded_by_k_and_reached(tmp_path, k):
    corpus = Corpus(tmp_path, _films())
    corpus.preview(corpus.orchestrator(config=_config(k=k)))
    assert corpus.client.peak == min(k, N)
    assert len(corpus.client.calls) == N * 4  # poster, fanart, thumb, one extrafanart each


def test_k_equal_one_is_strictly_serial_in_index_order(tmp_path):
    corpus = Corpus(tmp_path, _films())
    corpus.preview(corpus.orchestrator(config=_config(k=1)))
    assert corpus.client.peak == 1
    per_item = [call.split("/")[3] for call in corpus.client.calls]
    assert per_item == [n for n in _numbers() for _ in range(4)]


def _live_task_probe(corpus, observed: list[int]) -> None:
    for url, response in list(corpus.client.script.items()):
        async def answer(_url, _response=response):
            observed.append(len(asyncio.all_tasks()))
            return _response
        corpus.client.script[url] = answer


@pytest.mark.parametrize("k", [1, 2, 3])
def test_live_image_tasks_are_o_of_k(tmp_path, k):
    corpus = Corpus(tmp_path, _films(12))
    observed: list[int] = []
    _live_task_probe(corpus, observed)
    corpus.preview(corpus.orchestrator(config=_config(k=k)))
    # the driving task + at most k workers (the watchdog wrapper task adds one)
    assert observed and max(observed) <= k + 2


def test_live_task_probe_detects_a_naive_task_per_item_stage(tmp_path):
    """Control: a naive 'one task per item' image stage is visible to the same probe."""
    corpus = Corpus(tmp_path, _films(12))
    observed: list[int] = []
    _live_task_probe(corpus, observed)

    async def naive():
        urls = [image_url(n, "poster") for n in _numbers(12)]

        async def one(url):
            return await corpus.client.get(url, deadline_seconds=1, max_redirects=1, max_bytes=10 ** 6)

        tasks = [asyncio.ensure_future(one(url)) for url in urls]
        await asyncio.wait(tasks)

    run(naive())
    assert max(observed) >= 12  # far above k + 2 for any k < 10: the bound above is not vacuous


def test_image_stage_creates_exactly_min_k_n_workers(tmp_path, monkeypatch):
    created: list[int] = []
    real_worker = preview_module._image_worker

    async def counting(*args, **kwargs):
        created.append(1)
        return await real_worker(*args, **kwargs)

    monkeypatch.setattr(preview_module, "_image_worker", counting)
    for k, films in ((4, 2), (2, 7), (1, 5)):
        created.clear()
        corpus = Corpus(tmp_path / f"k{k}", _films(films))
        corpus.preview(corpus.orchestrator(config=_config(k=k)))
        assert len(created) == min(k, films)


async def _reversed(corpus, orchestrator, numbers, image_numbers):
    """Run a preview while forcing metadata and image completions into reverse index order."""
    engine, client = corpus.engine, corpus.client
    for number in numbers:
        engine.gate(number)
    first_urls = [image_url(n, "poster") for n in image_numbers]
    for url in first_urls:
        client.gate(url)

    async def controller():
        await until(lambda: engine.active == len(numbers))
        for number in reversed(numbers):
            done = len(engine.completed)
            engine.gates[number].set()
            await until(lambda: len(engine.completed) > done)
        await until(lambda: client.active == len(image_numbers))
        for url in reversed(first_urls):
            done = len(client.completed)
            client.gates[url].set()
            await until(lambda: len(client.completed) > done)

    control = asyncio.ensure_future(controller())
    work = asyncio.ensure_future(orchestrator.preview(corpus.items))
    await asyncio.wait({control, work}, return_when=asyncio.FIRST_EXCEPTION)
    if control.done() and control.exception() is not None:
        work.cancel()
        await asyncio.gather(work, return_exceptions=True)
        raise control.exception()
    await control
    return await work


def test_reversed_completion_order_gives_the_same_projection(tmp_path):
    corpus = Corpus(tmp_path, _films() + [Film("unrecognized.mp4"), Film("FC2-PPV-1000009.mp4", kind="failed")])
    numbers = _numbers() + ["FC2-1000009"]
    wide = _config(m=16, k=16)
    baseline = corpus.preview(corpus.orchestrator(config=wide))
    corpus.engine.completed.clear()
    corpus.client.completed.clear()
    reversed_preview = run(_reversed(corpus, corpus.orchestrator(config=wide), numbers, _numbers()))
    assert corpus.engine.completed == list(reversed(numbers))
    posters = [url for url in corpus.client.completed if url.endswith("/poster.jpg")]
    assert posters == [image_url(n, "poster") for n in reversed(_numbers())]
    assert projection(reversed_preview) == projection(baseline)
    assert [i.index for i in reversed_preview.items] == list(range(len(corpus.items)))
    for configured in (_config(m=1, k=1), _config(m=2, k=3)):
        assert projection(corpus.preview(corpus.orchestrator(config=configured))) == projection(baseline)
