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


# =========================================================================== S2-R1: constructor shape checks run no caller code


class _Hooks:
    """Counts every caller-controlled attribute hook that runs."""

    def __init__(self) -> None:
        self.calls: list[str] = []


async def _async_get(*_args, **_kwargs):  # pragma: no cover - never awaited here
    return None


async def _async_aggregate(number):  # pragma: no cover - never awaited here
    return None


def _property_holder(name: str, hooks: _Hooks):
    def getter(self):
        hooks.calls.append(f"property {name}")
        return _async_get

    return type(f"Property_{name}", (), {name: property(getter)})()


class _CountingDescriptor:
    def __init__(self, name: str, hooks: _Hooks) -> None:
        self.name, self.hooks = name, hooks

    def __get__(self, instance, owner=None):
        self.hooks.calls.append(f"descriptor {self.name}")
        return _async_get


def _descriptor_holder(name: str, hooks: _Hooks):
    return type(f"Descriptor_{name}", (), {name: _CountingDescriptor(name, hooks)})()


def _getattr_holder(name: str, hooks: _Hooks):
    def __getattr__(self, attribute):
        hooks.calls.append(f"__getattr__ {attribute}")
        if attribute == name:
            return _async_get
        raise AttributeError(attribute)

    return type(f"GetAttr_{name}", (), {"__getattr__": __getattr__})()


def _getattribute_holder(name: str, hooks: _Hooks):
    async def method(self, *_args, **_kwargs):  # pragma: no cover
        return None

    def __getattribute__(self, attribute):
        hooks.calls.append(f"__getattribute__ {attribute}")
        return object.__getattribute__(self, attribute)

    return type(f"GetAttribute_{name}", (), {name: method, "__getattribute__": __getattribute__})()


_HOSTILE_BUILDERS = {"property": _property_holder, "descriptor": _descriptor_holder,
                     "__getattr__": _getattr_holder}


@pytest.mark.parametrize("kind", list(_HOSTILE_BUILDERS))
def test_hostile_image_client_get_is_rejected_without_running_its_hook(kind):
    hooks = _Hooks()
    client = _HOSTILE_BUILDERS[kind]("get", hooks)
    with pytest.raises(OrchestrationConfigError) as info:
        BatchOrchestrator(ScriptedEngine(), client, LIBRARY)
    assert hooks.calls == []
    assert info.value.__context__ is None and info.value.__cause__ is None


@pytest.mark.parametrize("kind", list(_HOSTILE_BUILDERS))
def test_hostile_engine_aggregate_is_rejected_without_running_its_hook(kind):
    hooks = _Hooks()
    engine = _HOSTILE_BUILDERS[kind]("aggregate", hooks)
    with pytest.raises(OrchestrationConfigError) as info:
        BatchOrchestrator(engine, ScriptedImageClient(), LIBRARY)
    assert hooks.calls == []
    assert info.value.__context__ is None and info.value.__cause__ is None


@pytest.mark.parametrize("name", ["get", "aggregate"])
def test_getattribute_hook_never_runs_during_construction(name):
    hooks = _Hooks()
    holder = _getattribute_holder(name, hooks)
    engine = holder if name == "aggregate" else ScriptedEngine()
    client = holder if name == "get" else ScriptedImageClient()
    BatchOrchestrator(engine, client, LIBRARY)  # a plain method: accepted...
    assert hooks.calls == []  # ...and still no hook ran


def test_data_descriptor_shadowing_an_instance_function_is_rejected_unrun():
    hooks = _Hooks()
    client = _property_holder("get", hooks)
    client.__dict__["get"] = _async_get  # the class property wins in normal lookup
    with pytest.raises(OrchestrationConfigError):
        BatchOrchestrator(ScriptedEngine(), client, LIBRARY)
    assert hooks.calls == []


def test_hostile_metaclass_never_runs():
    hooks = _Hooks()

    class Meta(type):
        def __getattribute__(cls, attribute):
            hooks.calls.append(f"meta {attribute}")
            return type.__getattribute__(cls, attribute)

        def __eq__(cls, other):  # pragma: no cover - must never run
            hooks.calls.append("meta __eq__")
            return type.__eq__(cls, other)

        __hash__ = type.__hash__

    class Engine(metaclass=Meta):
        async def aggregate(self, number):  # pragma: no cover
            return None

    class Client(metaclass=Meta):
        async def get(self, url, **kwargs):  # pragma: no cover
            return None

    hooks.calls.clear()
    BatchOrchestrator(Engine(), Client(), LIBRARY)
    assert hooks.calls == []


def test_non_function_shapes_are_rejected():
    class StaticGet:
        get = staticmethod(_async_get)

    class CallableGet:
        get = ScriptedImageClient()  # a callable object, not a function

    class SyncAggregate:
        def aggregate(self, number):  # pragma: no cover
            return None

    for client in (StaticGet(), CallableGet()):
        with pytest.raises(OrchestrationConfigError):
            BatchOrchestrator(ScriptedEngine(), client, LIBRARY)
    with pytest.raises(OrchestrationConfigError):
        BatchOrchestrator(SyncAggregate(), ScriptedImageClient(), LIBRARY)


class _CountingEngine(ScriptedEngine):
    def __getattribute__(self, attribute):
        if attribute == "aggregate":
            object.__getattribute__(self, "reads").append(attribute)
        return object.__getattribute__(self, attribute)


class _CountingClient(ScriptedImageClient):
    def __getattribute__(self, attribute):
        if attribute == "get":
            object.__getattribute__(self, "reads").append(attribute)
        return object.__getattribute__(self, attribute)


def test_normal_objects_are_accepted_and_first_called_only_by_preview(tmp_path):
    corpus = Corpus(tmp_path, [Film("FC2-PPV-1000001.mp4")])
    engine = _CountingEngine(corpus.engine.script, fields=corpus.engine.fields)
    engine.reads = []
    client = _CountingClient(corpus.client.script)
    client.reads = []
    orchestrator = BatchOrchestrator(engine, client, str(corpus.library))
    assert engine.reads == [] and client.reads == [] and engine.calls == [] and client.calls == []
    preview = run(orchestrator.preview(corpus.items))
    assert type(preview) is BatchPreview
    assert engine.reads and engine.calls == ["FC2-1000001"]  # the caller engine runs in the metadata stage
    assert client.reads and client.calls  # the caller client runs in the image stage


def test_instance_attribute_functions_and_bound_methods_are_accepted(tmp_path):
    corpus = Corpus(tmp_path, [Film("FC2-PPV-1000001.mp4")])
    engine = ScriptedEngine()
    other = ScriptedEngine({"FC2-1000001": "success"})
    engine.aggregate = other.aggregate  # a bound method in the instance dict
    orchestrator = BatchOrchestrator(engine, corpus.client, str(corpus.library))
    run(orchestrator.preview(corpus.items))
    assert other.calls == ["FC2-1000001"] and engine.calls == []
