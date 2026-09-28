"""P4-C8 S2: ``BatchOrchestrator`` construction and the busy-first guard (contract sections 7.2, 7.3)."""

from __future__ import annotations

import asyncio
import dataclasses
import functools as _functools
import inspect as _inspect
import threading

import pytest

from fc2_metadata_core.batch import BatchConfig
from fc2_metadata_core.batch.scheduler import _is_async_callable as _phase3_is_async_callable  # parity oracle
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


def test_shapes_that_are_not_provably_callable_are_rejected():
    class NotCallable:
        pass

    class ObjectGet:
        get = NotCallable()  # an object without __call__

    class SyncAggregate:
        def aggregate(self, number):  # pragma: no cover
            return None

    class SyncCallable:
        def __call__(self, number):  # pragma: no cover
            return None

    class SyncCallableAggregate:
        def __init__(self) -> None:
            self.aggregate = SyncCallable()

    class UnboundClassmethod:
        def __init__(self) -> None:
            self.get = classmethod(_async_get)  # a classmethod object in the instance dict is not callable

    for client in (ObjectGet(), UnboundClassmethod(), type("IntGet", (), {"get": 3})()):
        with pytest.raises(OrchestrationConfigError):
            BatchOrchestrator(ScriptedEngine(), client, LIBRARY)
    for engine in (SyncAggregate(), SyncCallableAggregate()):
        with pytest.raises(OrchestrationConfigError):
            BatchOrchestrator(engine, ScriptedImageClient(), LIBRARY)


def test_call_behind_a_custom_descriptor_is_rejected_unrun():
    hooks = _Hooks()

    class CallAsDescriptor:
        __call__ = _CountingDescriptor("__call__", hooks)

    client = type("C", (), {})()
    client.get = CallAsDescriptor()
    engine = type("E", (), {})()
    engine.aggregate = CallAsDescriptor()
    with pytest.raises(OrchestrationConfigError):
        BatchOrchestrator(ScriptedEngine(), client, LIBRARY)
    with pytest.raises(OrchestrationConfigError):
        BatchOrchestrator(engine, ScriptedImageClient(), LIBRARY)
    assert hooks.calls == []


# ---- S2-R2 (P4-C8-S2-R1-01): every contract-legal callable shape is accepted, and first runs in preview


def _delegating_engines(inner):
    """Engines whose ``aggregate`` is each legal shape, all delegating to ``inner.aggregate``."""
    calls: list[str] = []

    async def record(number):
        calls.append(number)
        return await inner.aggregate(number)

    class MethodEngine:
        async def aggregate(self, number):
            return await record(number)

    class StaticEngine:
        @staticmethod
        async def aggregate(number):
            return await record(number)

    class ClassEngine:
        @classmethod
        async def aggregate(cls, number):
            return await record(number)

    class AsyncCallable:
        async def __call__(self, number):
            return await record(number)

    class CallableEngine:
        def __init__(self) -> None:
            self.aggregate = AsyncCallable()

    class InstanceFunctionEngine:
        def __init__(self) -> None:
            self.aggregate = record

    return calls, {"method": MethodEngine(), "staticmethod": StaticEngine(), "classmethod": ClassEngine(),
                   "async callable object": CallableEngine(), "instance function": InstanceFunctionEngine()}


def _delegating_clients(inner):
    calls: list[str] = []

    def record(url, **kwargs):
        calls.append(url)
        return inner.get(url, **kwargs)  # a coroutine: acquire_images awaits it

    class MethodClient:
        async def get(self, url, **kwargs):
            return await record(url, **kwargs)

    class StaticClient:
        @staticmethod
        def get(url, **kwargs):
            return record(url, **kwargs)

    class ClassClient:
        @classmethod
        def get(cls, url, **kwargs):
            return record(url, **kwargs)

    class SyncCallable:
        def __call__(self, url, **kwargs):
            return record(url, **kwargs)

    class CallableClient:
        def __init__(self) -> None:
            self.get = SyncCallable()

    return calls, {"method": MethodClient(), "staticmethod": StaticClient(), "classmethod": ClassClient(),
                   "callable object": CallableClient()}


@pytest.mark.parametrize("shape", ["method", "staticmethod", "classmethod", "async callable object",
                                   "instance function"])
def test_every_legal_aggregate_shape_is_accepted_and_runs_only_in_preview(tmp_path, shape):
    corpus = Corpus(tmp_path, [Film("FC2-PPV-1000001.mp4")])
    calls, engines = _delegating_engines(corpus.engine)
    orchestrator = BatchOrchestrator(engines[shape], corpus.client, str(corpus.library))
    assert calls == [] and corpus.engine.calls == []  # construction ran no engine code
    preview = run(orchestrator.preview(corpus.items))
    assert calls == ["FC2-1000001"] and preview.items[0].issue is None


@pytest.mark.parametrize("shape", ["method", "staticmethod", "classmethod", "callable object"])
def test_every_legal_get_shape_is_accepted_and_runs_only_in_preview(tmp_path, shape):
    corpus = Corpus(tmp_path, [Film("FC2-PPV-1000001.mp4")])
    calls, clients = _delegating_clients(corpus.client)
    orchestrator = BatchOrchestrator(corpus.engine, clients[shape], str(corpus.library))
    assert calls == [] and corpus.client.calls == []  # construction ran no client code
    preview = run(orchestrator.preview(corpus.items))
    assert calls and calls == corpus.client.calls and preview.items[0].issue is None


def test_builtin_callable_get_is_accepted():
    class BuiltinGet:
        get = len  # a builtin function: callable, never bound

    assert BatchOrchestrator(ScriptedEngine(), BuiltinGet(), LIBRARY).library_root == LIBRARY


def test_callable_object_with_hostile_getattribute_runs_no_hook():
    hooks = _Hooks()

    class Hostile:
        async def __call__(self, number):  # pragma: no cover
            return None

        def __getattribute__(self, attribute):
            hooks.calls.append(attribute)
            return object.__getattribute__(self, attribute)

    engine = type("E", (), {})()
    engine.aggregate = Hostile()
    hooks.calls.clear()
    BatchOrchestrator(engine, ScriptedImageClient(), LIBRARY)
    assert hooks.calls == []


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


# =========================================================================== S2-R3: async shapes follow Phase 3 (inspect)

async def _async_impl(number):  # pragma: no cover - only classified here
    return None


def _sync_impl(number):  # pragma: no cover - only classified here
    return None


def _fake_marked(value):
    def sync_fn(number):  # pragma: no cover - never awaited
        return None

    sync_fn._is_coroutine_marker = value
    return sync_fn


class _AsyncCall:
    async def __call__(self, number):  # pragma: no cover
        return None


class _SyncCall:
    def __call__(self, number):  # pragma: no cover
        return None


class _Methods:
    async def async_method(self, number):  # pragma: no cover
        return None

    def sync_method(self, number):  # pragma: no cover
        return None


def _parity_candidates() -> dict[str, object]:
    candidates = {
        "async function": _async_impl,
        "sync function": _sync_impl,
        "partial(async)": _functools.partial(_async_impl),
        "partial(async, bound argument)": _functools.partial(_async_impl, "FC2-1000001"),
        "partial(partial(async))": _functools.partial(_functools.partial(_async_impl)),
        "partial(sync)": _functools.partial(_sync_impl),
        "fake marker False": _fake_marked(False),
        "fake marker True": _fake_marked(True),
        "fake marker object": _fake_marked(object()),
        "fake marker string": _fake_marked("fake"),
        "bound async method": _Methods().async_method,
        "bound sync method": _Methods().sync_method,
        "async callable object": _AsyncCall(),
        "sync callable object": _SyncCall(),
    }
    if hasattr(_inspect, "markcoroutinefunction"):
        candidates["official marker"] = _inspect.markcoroutinefunction(_fake_marked(None))
    return candidates


def _engine_with(aggregate):
    engine = type("Engine", (), {})()
    engine.aggregate = aggregate
    return engine


def _accepted(engine) -> bool:
    try:
        BatchOrchestrator(engine, ScriptedImageClient(), LIBRARY)
    except OrchestrationConfigError:
        return False
    return True


@pytest.mark.parametrize("name", list(_parity_candidates()))
def test_aggregate_acceptance_matches_phase3_inspect_semantics(name):
    candidate = _parity_candidates()[name]
    expected = _phase3_is_async_callable(candidate)  # the Phase 3 boundary's own rule
    assert _accepted(_engine_with(candidate)) is expected, name


def test_parity_expectations_are_the_standard_library_verdicts():
    candidates = _parity_candidates()
    assert _inspect.iscoroutinefunction(candidates["partial(async)"]) is True
    assert _inspect.iscoroutinefunction(candidates["partial(partial(async))"]) is True
    for fake in ("fake marker False", "fake marker True", "fake marker object", "fake marker string"):
        assert _inspect.iscoroutinefunction(candidates[fake]) is False, fake
        assert _accepted(_engine_with(candidates[fake])) is False, fake
    if "official marker" in candidates:
        assert _inspect.iscoroutinefunction(candidates["official marker"]) is True
        assert _accepted(_engine_with(candidates["official marker"])) is True


def _runtime_aggregates(inner):
    """Legal aggregate shapes (partials, nested partials, the official marker when available), each
    delegating to ``inner.aggregate`` and counting its calls."""
    calls: list[str] = []

    async def impl(number):
        calls.append(number)
        return await inner.aggregate(number)

    def sync_returning_coroutine(number):
        return impl(number)

    shapes = {"partial(async)": _functools.partial(impl),
              "partial(partial(async))": _functools.partial(_functools.partial(impl))}
    if hasattr(_inspect, "markcoroutinefunction"):
        shapes["official marker"] = _inspect.markcoroutinefunction(sync_returning_coroutine)
    return calls, shapes


@pytest.mark.parametrize("shape", ["partial(async)", "partial(partial(async))", "official marker"])
def test_partial_and_marked_aggregates_run_only_in_preview(tmp_path, shape):
    corpus = Corpus(tmp_path, [Film("FC2-PPV-1000001.mp4")])
    calls, shapes = _runtime_aggregates(corpus.engine)
    if shape not in shapes:  # the runtime has no inspect.markcoroutinefunction: nothing to accept
        assert not hasattr(_inspect, "markcoroutinefunction")
        return
    orchestrator = BatchOrchestrator(_engine_with(shapes[shape]), corpus.client, str(corpus.library))
    assert calls == [] and corpus.engine.calls == []  # construction ran no engine code
    preview = run(orchestrator.preview(corpus.items))
    assert calls == ["FC2-1000001"] and preview.items[0].issue is None


def test_partial_image_client_get_is_accepted_and_used(tmp_path):
    corpus = Corpus(tmp_path, [Film("FC2-PPV-1000001.mp4")])
    calls: list[str] = []

    def get_impl(url, **kwargs):
        calls.append(url)
        return corpus.client.get(url, **kwargs)

    client = type("Client", (), {})()
    client.get = _functools.partial(get_impl)
    orchestrator = BatchOrchestrator(corpus.engine, client, str(corpus.library))
    assert calls == []
    preview = run(orchestrator.preview(corpus.items))
    assert calls and preview.items[0].issue is None


def test_objects_that_only_look_like_partials_run_no_hook():
    hooks = _Hooks()

    class FakePartial:
        @property
        def func(self):
            hooks.calls.append("func")
            return _async_impl

    class PartialSubclass(_functools.partial):
        @property
        def func(self):
            hooks.calls.append("subclass func")
            return _async_impl

    class HostileTarget:
        async def __call__(self, number):  # pragma: no cover
            return None

        @property
        def __class__(self):
            hooks.calls.append("__class__")
            return _functools.partial

        def __getattribute__(self, attribute):
            hooks.calls.append(attribute)
            return object.__getattribute__(self, attribute)

    for candidate in (FakePartial(), PartialSubclass(_async_impl), _functools.partial(HostileTarget())):
        hooks.calls.clear()
        assert _accepted(_engine_with(candidate)) is False  # not provably async without running code
        assert hooks.calls == []
    client = type("Client", (), {})()
    client.get = _functools.partial(HostileTarget())  # a partial is callable: accepted for get, still no hook
    hooks.calls.clear()
    BatchOrchestrator(ScriptedEngine(), client, LIBRARY)
    assert hooks.calls == []
