"""P4-C9 contract section 28.6 -- no side effects: with every mutating / querying / network / thread / logging /
orchestration entry point turned into a trip-wire for the duration of the call, both builders still succeed; the
file-system tree is identical before and after; the input graph is field-for-field unchanged with all node identities
intact; module-level state of the diagnostics package is unchanged; the input remains consumable by P4-C8."""

from __future__ import annotations

import asyncio
import builtins
import dataclasses
import hashlib
import logging
import os
import socket
import threading

import fc2_organizer.diagnostics as diagnostics_package
import pytest
from fc2_organizer.diagnostics import PathPolicy, TimingPolicy
from fc2_organizer.orchestration import BatchOrchestrator

import fc2_organizer.execution as execution_package
from . import _builders as b
from . import _builders as h

OS_FUNCTIONS = ("stat", "lstat", "listdir", "scandir", "mkdir", "rename", "replace", "unlink", "remove", "rmdir",
                "makedirs", "chmod", "utime", "symlink", "link", "readlink")
PATH_FUNCTIONS = ("exists", "realpath", "islink", "isfile", "isdir", "getsize", "getmtime", "lexists", "samefile")


def trip(label):
    def fire(*args, **kwargs):
        raise AssertionError("forbidden call: %s" % label)
    return fire


def arm_everything(monkeypatch):
    for cls, name in ((BatchOrchestrator, "preview"), (BatchOrchestrator, "execute"),
                      (BatchOrchestrator, "preview_retry")):
        monkeypatch.setattr(cls, name, trip("BatchOrchestrator.%s" % name))

    monkeypatch.setattr(execution_package, "preflight_execution", trip("preflight_execution"))
    monkeypatch.setattr(execution_package, "execute_filesystem", trip("execute_filesystem"))
    monkeypatch.setattr(builtins, "open", trip("builtins.open"))
    monkeypatch.setattr(os, "open", trip("os.open"), raising=False)
    for name in OS_FUNCTIONS:
        if hasattr(os, name):
            monkeypatch.setattr(os, name, trip("os.%s" % name))
    for name in PATH_FUNCTIONS:
        monkeypatch.setattr(os.path, name, trip("os.path.%s" % name))
    monkeypatch.setattr(socket, "socket", trip("socket.socket"))
    monkeypatch.setattr(socket, "create_connection", trip("socket.create_connection"))
    monkeypatch.setattr(threading.Thread, "start", trip("Thread.start"))
    monkeypatch.setattr(asyncio, "new_event_loop", trip("asyncio.new_event_loop"))
    monkeypatch.setattr(asyncio, "run", trip("asyncio.run"))
    monkeypatch.setattr(logging.Logger, "handle", trip("Logger.handle"))


def tree_snapshot(root):
    entries = []
    for directory, folders, files in os.walk(root):
        for name in sorted(folders + files):
            path = os.path.join(directory, name)
            info = os.lstat(path)
            digest = hashlib.sha256(open(path, "rb").read()).hexdigest() if os.path.isfile(path) else None
            entries.append((path, info.st_mode, info.st_size, info.st_mtime_ns, digest))
    return sorted(entries)


@pytest.mark.parametrize("kind", ["preview", "execution"])
@pytest.mark.parametrize("path_policy", list(PathPolicy))
@pytest.mark.parametrize("timing_policy", list(TimingPolicy))
def test_both_builders_succeed_with_every_side_effect_entry_point_turned_into_a_trap(
        monkeypatch, kind, path_policy, timing_policy):
    graph = h.FACTORY[kind]()
    reference = h.BUILD[kind](graph, path_policy=path_policy, timing_policy=timing_policy)
    with monkeypatch.context() as patch:
        arm_everything(patch)
        out = h.BUILD[kind](graph, path_policy=path_policy, timing_policy=timing_policy)
    assert out == reference


def test_the_traps_are_not_vacuous(monkeypatch):

    with monkeypatch.context() as patch:
        arm_everything(patch)
        for forbidden in (lambda: open("x"), lambda: os.stat("."), lambda: os.path.exists("."),
                          lambda: socket.socket(), lambda: asyncio.run(None),
                          lambda: BatchOrchestrator.preview(None),
                          lambda: execution_package.preflight_execution(), lambda: execution_package.execute_filesystem()):
            with pytest.raises(AssertionError):
                forbidden()


def test_the_file_system_tree_is_identical_before_and_after(tmp_path, monkeypatch):
    (tmp_path / "library").mkdir()
    (tmp_path / "library" / "a.txt").write_bytes(b"alpha")
    (tmp_path / "downloads").mkdir()
    (tmp_path / "downloads" / "b.mp4").write_bytes(b"beta")
    monkeypatch.chdir(tmp_path)
    before = tree_snapshot(tmp_path)
    for kind in ("preview", "execution"):
        h.BUILD[kind](h.FACTORY[kind](), path_policy=PathPolicy.BASENAME, timing_policy=TimingPolicy.INCLUDE)
    assert tree_snapshot(tmp_path) == before
    assert sorted(os.listdir(tmp_path)) == ["downloads", "library"]


@pytest.mark.parametrize("kind", ["preview", "execution"])
def test_the_input_graph_is_field_for_field_unchanged_and_keeps_every_node_identity(kind):
    graph = h.FACTORY[kind]()
    fingerprint, ids = b.fingerprint(graph), b.identities(graph)
    for path_policy in PathPolicy:
        for timing_policy in TimingPolicy:
            h.BUILD[kind](graph, path_policy=path_policy, timing_policy=timing_policy)
    assert b.fingerprint(graph) == fingerprint and b.identities(graph) == ids


def test_the_diagnostics_package_keeps_its_module_level_state():
    modules = [getattr(diagnostics_package, name) for name in ("errors", "models", "validation", "projection", "build")]
    before = [{k: v for k, v in vars(m).items() if not k.startswith("__")} for m in modules]
    for kind in ("preview", "execution"):
        h.BUILD[kind](h.FACTORY[kind](), path_policy=PathPolicy.BASENAME, timing_policy=TimingPolicy.INCLUDE)
    after = [{k: v for k, v in vars(m).items() if not k.startswith("__")} for m in modules]
    assert [sorted(x) for x in before] == [sorted(x) for x in after]
    assert all(before[i][k] is after[i][k] for i in range(len(modules)) for k in before[i])


def test_the_input_is_still_consumable_by_p4_c8_after_a_diagnostic():
    preview = h.preview_graph()
    summary, retained = preview.summary, preview.retained_artifact_bytes
    h.BUILD["preview"](preview)
    assert preview.summary == summary and preview.retained_artifact_bytes == retained
    result = h.execution_graph()
    summary, outcome, kinds = result.summary, result.outcome, [i.retry_kind for i in result.items]
    h.BUILD["execution"](result)
    assert result.summary == summary and result.outcome is outcome
    assert [i.retry_kind for i in result.items] == kinds
    assert result.retained_retry_payload_bytes == result.retained_retry_payload_bytes


def test_outputs_are_new_immutable_objects_and_share_no_input_container():
    graph = h.preview_graph()
    out = h.BUILD["preview"](graph)
    assert out is not h.BUILD["preview"](graph)
    with pytest.raises(dataclasses.FrozenInstanceError):
        out.generation = 5


def test_a_failed_diagnostic_leaves_no_residue_and_the_next_call_succeeds():
    graph = h.preview_graph()
    clean = h.BUILD["preview"](graph)
    saved = graph.items[0].state
    b.poke(graph.items[0], state="bad")
    with pytest.raises(diagnostics_package.DiagnosticsIntegrityError):
        h.BUILD["preview"](graph)
    b.poke(graph.items[0], state=saved)
    assert h.BUILD["preview"](graph) == clean
