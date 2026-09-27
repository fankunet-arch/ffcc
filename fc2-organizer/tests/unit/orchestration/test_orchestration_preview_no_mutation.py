"""P4-C8 S2: preview never mutates the filesystem (contract section 16).

Every mutating API of contract section 16 is trapped (``os`` mutators, write-mode ``os.open`` / ``open``,
``shutil`` copy / move / rmtree, ``execute_filesystem``, ``materialize_artifact``,
``materialize_atomic_bytes``); the preview must hit none of them, a positive control proves each trap is
live, and the tree before / after is identical (relative path, type, SHA-256, ``st_ino``, ``st_mtime_ns``).
"""

from __future__ import annotations

import builtins
import os
import shutil

import pytest

import fc2_organizer.execution as execution_package
import fc2_organizer.materialization as materialization_package
from fc2_organizer.orchestration import IssueReason as R, PreviewState as S

from ._helpers import Corpus, Film, by_name, make_media_tree, mutation_traps, run, tree_snapshot, writer_bindings


def _mixed_corpus(tmp_path) -> Corpus:
    corpus = Corpus(tmp_path, [
        Film("FC2-PPV-1000001.mp4", extra=2, extra_fail=1),       # READY
        Film("FC2-PPV-1000002.mp4", poster=False),                  # READY with warnings
        Film("FC2-PPV-1000003.mp4"), Film("FC2PPV1000003.mkv", directory="dup"),  # Phase A
        Film("FC2-PPV-1000004.mp4"),                                # preflight blocked
        Film("FC2-PPV-1000005.mp4", kind="failed"),                 # metadata
        Film("FC2-PPV-1000006.mp4", release="bad-date"),            # NFO
        Film("unrecognized.mp4"),                                   # number
    ])
    (corpus.library / "FC2-1000004").mkdir()
    (corpus.library / "FC2-1000004" / "planted.txt").write_bytes(b"do not touch")
    return corpus


def _positive_control(trap) -> None:
    probes = [
        lambda: os.mkdir("never-created"),
        lambda: os.makedirs("never/created"),
        lambda: os.rename("a", "b"),
        lambda: os.replace("a", "b"),
        lambda: os.remove("a"),
        lambda: os.unlink("a"),
        lambda: os.rmdir("a"),
        lambda: os.link("a", "b"),
        lambda: os.symlink("a", "b"),
        lambda: os.truncate("a", 0),
        lambda: os.chmod("a", 0o600),
        lambda: os.utime("a"),
        lambda: os.open("a", os.O_WRONLY | os.O_CREAT),
        lambda: builtins.open("a", "wb"),
        lambda: shutil.copy("a", "b"),
        lambda: shutil.copy2("a", "b"),
        lambda: shutil.copyfile("a", "b"),
        lambda: shutil.move("a", "b"),
        lambda: shutil.rmtree("a"),
        lambda: execution_package.execute_filesystem(None),
        lambda: materialization_package.materialize_artifact(None),
        lambda: materialization_package.materialize_atomic_bytes(None, b""),
    ]
    for probe in probes:
        with pytest.raises(AssertionError):
            probe()
    assert len(trap.calls) == len(probes)
    for expected in ("os.mkdir", "os.rename", "os.replace", "os.unlink", "os.rmdir", "shutil.move",
                     "shutil.rmtree", "execute_filesystem", "materialize_artifact", "materialize_atomic_bytes",
                     "os.open(write)", "open(write)"):
        assert expected in trap.calls, expected


def test_mixed_preview_hits_no_mutating_api_and_leaves_the_tree_identical(tmp_path, monkeypatch):
    corpus = _mixed_corpus(tmp_path)
    orchestrator = corpus.orchestrator()
    before = tree_snapshot(tmp_path)
    trap = mutation_traps(monkeypatch)
    preview = run(orchestrator.preview(corpus.items))
    assert trap.calls == []
    after_preview = list(trap.calls)
    _positive_control(trap)  # the traps were live the whole time
    monkeypatch.undo()
    assert after_preview == [] and tree_snapshot(tmp_path) == before
    named = by_name(preview)
    assert named["FC2-PPV-1000001.mp4"].state is S.READY
    assert named["FC2-PPV-1000004.mp4"].issue.reason is R.PREFLIGHT_BLOCKED
    assert named["FC2PPV1000003.mkv"].issue.reason is R.DUPLICATE_TARGET_IN_BATCH
    assert named["unrecognized.mp4"].issue.reason is R.NUMBER_NOT_RECOGNIZED
    assert {i.state for i in preview.items} == {S.READY, S.BLOCKED, S.UNPREPARED}


def test_traps_reach_every_module_binding_of_the_writers(monkeypatch):
    bound = writer_bindings()
    held = {(name, id(module)) for name, module in bound}
    assert ("execute_filesystem", id(execution_package)) in held  # the package attributes at least
    assert ("materialize_artifact", id(materialization_package)) in held
    trap = mutation_traps(monkeypatch)
    for name, module in bound:
        with pytest.raises(AssertionError):
            getattr(module, name)(None)
    assert len(trap.calls) == len(bound)


def test_hardlink_phase_b_and_missing_library_are_also_read_only(tmp_path, monkeypatch):
    corpus = Corpus(tmp_path, [Film("FC2-PPV-1000001.mp4")], library=False)
    (corpus.downloads / "alias").mkdir()
    os.link(corpus.items[0].source_path, corpus.downloads / "alias" / "FC2-PPV-1000002.mp4")
    corpus.engine.script["FC2-1000002"] = "success"
    items = make_media_tree(corpus.downloads, {})
    before = tree_snapshot(tmp_path)
    trap = mutation_traps(monkeypatch)
    preview = run(corpus.orchestrator().preview(items))
    assert trap.calls == []
    monkeypatch.undo()
    assert tree_snapshot(tmp_path) == before
    assert not corpus.library.exists()
    assert all(i.state is S.BLOCKED for i in preview.items)
