"""P5-C1 §12（E9 / M-10）：registry / 配置 / governor / 桥 / engine 一次构造、多次复用。"""

from __future__ import annotations

import asyncio

import pytest

from _amane_scenarios import client_4825061, client_4979299, lookup
from fc2_amane_adapter import _runtime
from fc2_amane_adapter._outcome import AdapterFound
from fc2_amane_adapter._settings import AdapterConfigError, parse_settings
from fc2_metadata_core.aggregation import MultiSourceEngine
from fc2_metadata_core.resource_control import SourceResourceGovernor


def _counting(monkeypatch, name):
    original = getattr(_runtime, name)
    counter = {"n": 0}

    def wrapper(*args, **kwargs):
        counter["n"] += 1
        return original(*args, **kwargs)

    if isinstance(original, type):
        # 类：保持 isinstance 兼容，用子类计数
        class Counting(original):  # type: ignore[misc, valid-type]
            def __init__(self, *args, **kwargs):
                counter["n"] += 1
                super().__init__(*args, **kwargs)

        monkeypatch.setattr(_runtime, name, Counting)
    else:
        monkeypatch.setattr(_runtime, name, wrapper)
    return counter


def test_core_runtime_objects_are_built_exactly_once_for_many_lookups(monkeypatch):
    counters = {
        name: _counting(monkeypatch, name)
        for name in ("MultiSourceEngine", "SourceResourceGovernor", "AmaneHttpBridge", "build_default_registry", "build_aggregation_config")
    }
    runtime = _runtime.AdapterRuntime(parse_settings({}), client_4979299())
    assert {name: counter["n"] for name, counter in counters.items()} == {name: 1 for name in counters}
    for _ in range(4):
        lookup(runtime, "FC2-PPV-4979299")
    assert {name: counter["n"] for name, counter in counters.items()} == {name: 1 for name in counters}, "M-10：每次 fetch 重建"


def test_non_fc2_lookups_do_not_construct_anything(monkeypatch):
    runtime = _runtime.AdapterRuntime(parse_settings({}), client_4979299())
    counter = _counting(monkeypatch, "MultiSourceEngine")
    for number in ("ABC-1", "x"):
        lookup(runtime, number)
    assert counter["n"] == 0


def test_the_same_governor_serves_every_lookup():
    runtime = _runtime.AdapterRuntime(parse_settings({}), client_4979299())
    governor = runtime.governor
    assert isinstance(governor, SourceResourceGovernor)
    lookup(runtime, "FC2-PPV-4979299")
    first_hosts = {host.host for host in governor.snapshot().hosts}
    lookup(runtime, "FC2-PPV-4979299")
    assert runtime.governor is governor
    assert {host.host for host in governor.snapshot().hosts} == first_hosts and len(first_hosts) == 3
    assert isinstance(runtime._engine, MultiSourceEngine)


def test_two_runtimes_do_not_share_governor_state():
    """provider 重建时 governor 重置（L-09）：两个 runtime 互不共享。"""
    one = _runtime.AdapterRuntime(parse_settings({}), client_4979299())
    two = _runtime.AdapterRuntime(parse_settings({}), client_4979299())
    assert one.governor is not two.governor
    lookup(one, "FC2-PPV-4979299")
    assert two.governor.snapshot().hosts == ()


def test_construction_does_not_touch_the_network_or_the_host_client():
    client = client_4825061()
    _runtime.AdapterRuntime(parse_settings({}), client)
    assert client.calls == []


def test_concurrent_lookups_on_one_runtime_are_independent_and_leave_the_governor_idle():
    async def scenario():
        runtime = _runtime.AdapterRuntime(parse_settings({}), client_4979299())
        outcomes = await asyncio.gather(*(runtime.lookup("FC2-PPV-4979299", "fc2") for _ in range(5)))
        assert all(isinstance(o, AdapterFound) for o in outcomes) and len({o.record for o in outcomes}) == 1
        snapshot = runtime.governor.snapshot()
        assert all(h.in_flight == 0 and h.waiting == 0 for h in snapshot.hosts)
        assert max(h.peak_in_flight for h in snapshot.hosts) <= 4  # HostLimitPolicy 默认 4

    asyncio.run(scenario())


def test_valid_configuration_never_makes_construction_raise():
    for raw in ({}, {"sources": [{"id": "javdb"}]}, {"source_deadline_seconds": 600}, {"sources": [{"id": "av123", "base_url": "https://mirror.example/p"}]}):
        _runtime.AdapterRuntime(parse_settings(raw), client_4825061())


@pytest.mark.parametrize("raw", [{"sources": []}, {"source_deadline_seconds": 0}])
def test_invalid_configuration_fails_before_a_runtime_exists(raw):
    with pytest.raises(AdapterConfigError):
        parse_settings(raw)
