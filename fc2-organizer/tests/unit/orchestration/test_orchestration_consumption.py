"""P4-C8 S1: process-local one-time consumption registries (``_consumption.py``)."""

from __future__ import annotations

import ast
import threading
from pathlib import Path

import pytest

import fc2_organizer.orchestration as orchestration
from fc2_organizer.orchestration import _consumption
from fc2_organizer.orchestration._consumption import (
    PREVIEW_EXECUTIONS,
    RESULT_RETRIES,
    RETRY_MERGES,
    ConsumptionRegistry,
)

from ._helpers import new_id

REGISTRIES = {"preview_executions": PREVIEW_EXECUTIONS, "result_retries": RESULT_RETRIES,
              "retry_merges": RETRY_MERGES}


def test_three_distinct_registries_each_with_its_own_lock_and_set():
    registries = list(REGISTRIES.values())
    assert len({id(r) for r in registries}) == 3
    assert all(type(r) is ConsumptionRegistry for r in registries)
    assert len({id(r._lock) for r in registries}) == 3 and len({id(r._ids) for r in registries}) == 3
    assert all(type(r._ids) is set for r in registries)
    assert ConsumptionRegistry.__slots__ == ("_lock", "_ids")


@pytest.mark.parametrize("name", list(REGISTRIES))
def test_first_registration_succeeds_and_repeat_fails(name):
    registry = REGISTRIES[name]
    token = new_id()
    assert registry.is_registered(token) is False
    assert registry.register(token) is True
    assert registry.is_registered(token) is True
    assert registry.register(token) is False
    assert registry.is_registered(token) is True


@pytest.mark.parametrize("name", list(REGISTRIES))
def test_query_never_registers(name):
    registry = REGISTRIES[name]
    token = new_id()
    for _ in range(3):
        assert registry.is_registered(token) is False
    assert token not in registry._ids
    assert registry.register(token) is True


def test_registries_are_independent():
    token = new_id()
    assert PREVIEW_EXECUTIONS.register(token) is True
    assert RESULT_RETRIES.is_registered(token) is False and RETRY_MERGES.is_registered(token) is False
    assert RESULT_RETRIES.register(token) is True and RETRY_MERGES.register(token) is True


@pytest.mark.parametrize("name", list(REGISTRIES))
def test_concurrent_registration_has_exactly_one_winner(name):
    registry = REGISTRIES[name]
    token = new_id()
    contenders = 32
    barrier = threading.Barrier(contenders)
    outcomes: list[bool] = []
    lock = threading.Lock()

    def contend():
        barrier.wait()
        won = registry.register(token)
        with lock:
            outcomes.append(won)

    threads = [threading.Thread(target=contend) for _ in range(contenders)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert sorted(outcomes) == [False] * (contenders - 1) + [True]


def test_concurrent_distinct_ids_all_win():
    registry = ConsumptionRegistry()
    tokens = [new_id() for _ in range(64)]
    barrier = threading.Barrier(len(tokens))
    outcomes: list[bool] = []
    lock = threading.Lock()

    def contend(token):
        barrier.wait()
        won = registry.register(token)
        with lock:
            outcomes.append(won)

    threads = [threading.Thread(target=contend, args=(t,)) for t in tokens]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert outcomes == [True] * len(tokens) and registry._ids == set(tokens)


@pytest.mark.parametrize("bad", ["", "0" * 31, "0" * 33, "G" * 32, "A" * 32, 123, None, b"0" * 32,
                                 type("S", (str,), {})("0" * 32)])
def test_only_32_lowercase_hex_ids_are_accepted(bad):
    registry = ConsumptionRegistry()
    with pytest.raises(ValueError):
        registry.register(bad)
    with pytest.raises(ValueError):
        registry.is_registered(bad)
    assert registry._ids == set()


def test_registries_store_only_id_strings_and_nothing_else():
    for registry in REGISTRIES.values():
        assert all(type(value) is str and len(value) == 32 for value in registry._ids)
    public = {n for n in vars(_consumption) if not n.startswith("_")}
    assert public - {"annotations", "threading"} == {"ConsumptionRegistry", "PREVIEW_EXECUTIONS",
                                                     "RESULT_RETRIES", "RETRY_MERGES"}


def test_module_imports_only_future_and_threading_and_is_not_exported():
    source = (Path(orchestration.__file__).parent / "_consumption.py").read_text(encoding="utf-8")
    imported = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add(node.module)
    assert imported == {"__future__", "threading"}
    for name in ("ConsumptionRegistry", "PREVIEW_EXECUTIONS", "RESULT_RETRIES", "RETRY_MERGES", "_consumption"):
        assert name not in orchestration.__all__
    for persistence in ("open(", "json", "pickle", "shelve", "sqlite3"):
        assert persistence not in source
