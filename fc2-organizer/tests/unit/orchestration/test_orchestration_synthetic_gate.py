"""P4-C8 S6: the 500-item batch orchestration gate (contract section 35.1) and its resource sub-gates (sections
19.6, 35.1, 35.1.1).

Only orchestration is verified here; P4-C7's own low-level gates (1000 extrafanart, platform syscalls, atomic
publication) are not repeated. 500 deterministic synthetic media files (a few bytes each) live in a dirty
``tmp_path`` download tree and are found by the real ``discover_media``; the engine and image client are scripted;
execution runs the real P4-C7 executor. Faults use the private ``_FS`` seams (tests only, contract section 34.2);
P4-C7's same-volume strategy seam is set to ``link`` for the whole gate so ``SOURCE_UNLINK_FAILED`` exists on every
host. Every concurrency control is an event / condition with a bounded wait (hang protection only).
"""

from __future__ import annotations

import asyncio
import collections.abc
import errno
import hashlib
import os
import shutil
import threading

import pytest

from fc2_metadata_core.batch import BatchConfig
from fc2_organizer.discovery import DiscoveredMediaItem, discover_media
from fc2_organizer.execution import EffectKind, ExecutionFailureKind as F, ExecutionStatus, execute_filesystem
from fc2_organizer.execution import transfer as execution_transfer
from fc2_organizer.images import ImageAcquisitionPolicy
from fc2_organizer.materialization import ArtifactKind
from fc2_organizer.nfo import render_movie_nfo
from fc2_organizer.orchestration import (
    MAX_BATCH_ITEMS,
    BatchOrchestrator,
    BatchOutcome,
    ExecutionDisposition as D,
    IssueReason as R,
    OrchestrationConfig,
    OrchestrationConsumedError,
    OrchestrationResourceLimitError,
    PreviewState as S,
    ResourceLimitReason,
    RetryKind as K,
    merge_retry,
)
from fc2_organizer.orchestration import _consumption
from fc2_organizer.orchestration import execute as execute_module
from fc2_organizer.orchestration import preview as preview_module
from fc2_organizer.publication import prepare_publication

from ._fakes import ScriptedEngine, ScriptedImageClient, build_metadata, jpeg_response, minimal_jpeg
from ._helpers import (
    Corpus,
    Film,
    assert_source_not_lost,
    fs_fault,
    image_url,
    media_item,
    mutation_traps,
    projection,
    run,
    tree_snapshot,
)

WAIT = 60.0

# --------------------------------------------------------------------------- the frozen group table (section 35.1)

GROUPS = {"A": 310, "B": 40, "C": 30, "D": 40, "E": 10, "F": 20, "G": 30, "H": 10, "I": 10}
assert sum(GROUPS.values()) == 500
C_SAME_NUMBER_PAIRS, C_REPEATED_ENTRIES, C_HARDLINK_PAIRS = 10, 3, 2
assert 2 * C_SAME_NUMBER_PAIRS + 2 * C_REPEATED_ENTRIES + 2 * C_HARDLINK_PAIRS == GROUPS["C"]
D_FAILED, D_ENGINE, D_MISMATCH = 25, 10, 5
assert D_FAILED + D_ENGINE + D_MISMATCH == GROUPS["D"]
D_RECOVER = {"failed": 20, "engine": 7, "mismatch": 3}  # 30 recover at g2, 10 stay failed
assert sum(D_RECOVER.values()) == 30
F_REMOVED = 15
G_FAILED, G_UNLINK, G_PUBLISH, G_WRITE = 15, 5, 5, 5
assert G_FAILED + G_UNLINK + G_PUBLISH + G_WRITE == GROUPS["G"]

# expected counts, derived statically from the table
MAIN_PREVIEW = dict(total=500, ready=GROUPS["A"] + GROUPS["G"] + GROUPS["H"] + GROUPS["I"],
                    blocked=GROUPS["C"] + GROUPS["F"], unprepared=GROUPS["B"] + GROUPS["D"] + GROUPS["E"])
assert MAIN_PREVIEW == dict(total=500, ready=360, blocked=50, unprepared=90)
MAIN_RESULT = dict(success=310, partial=15, failed=15, aborted=10, not_selected=10, blocked=50, unprepared=90,
                   retryable=90, deferred=10, non_retryable=90)
G1_SCOPE = frozenset({K.RESUME})
G2_SCOPE = frozenset({K.METADATA_REFETCH, K.FRESH_REEXECUTE, K.PREFLIGHT_RECHECK})
G3_SCOPE = frozenset({K.DEFERRED})
FINAL = dict(success=395, blocked=35, unprepared=60, aborted=10, retryable=15, deferred=0, non_retryable=90)


def _number(group_base: int, k: int) -> str:
    return f"FC2-{group_base + k}"


def _name(group_base: int, k: int, ext: str = ".mp4") -> str:
    return f"FC2-PPV-{group_base + k}{ext}"


def _films() -> tuple[list[Film], dict[str, str], dict[str, str]]:
    """The 497 files (500 inputs: three files appear twice). Returns films, basename -> group, number -> kind."""
    films: list[Film] = []
    group: dict[str, str] = {}
    kinds: dict[str, str] = {}
    combos = [(p, f, t) for p in (True, False) for f in (True, False) for t in (True, False)]
    for k in range(GROUPS["A"]):  # A: SUCCESS / PARTIAL metadata, 8 combos x extrafanart 0..3, candidate failures
        poster, fanart, thumb = combos[k % 8]
        kind = "partial" if k % 3 == 0 else "success"
        film = Film(_name(1_000_000, k), directory=f"a/{k % 7}", kind=kind, poster=poster, fanart=fanart,
                    thumb=thumb, extra=(k // 8) % 4, extra_fail=1 if k % 5 == 0 else 0)
        films.append(film)
        group[film.name], kinds[_number(1_000_000, k)] = "A", kind
    for k in range(GROUPS["B"]):  # B: no FC2 number
        film = Film(f"holiday-clip-{k:03d}.mp4", directory="b")
        films.append(film)
        group[film.name] = "B"
    for k in range(C_SAME_NUMBER_PAIRS):  # C: same number, two different files
        for film in (Film(_name(2_000_000, k)), Film(f"FC2PPV{2_000_000 + k}.mkv", directory="c-copy")):
            films.append(film)
            group[film.name] = "C"
    for k in range(C_REPEATED_ENTRIES):  # C: files that appear twice in the input
        film = Film(_name(2_100_000, k), directory="c-repeat")
        films.append(film)
        group[film.name] = "C"
    for k in range(2 * C_HARDLINK_PAIRS):  # C: hard-linked pairs with different numbers (linked after creation)
        film = Film(_name(2_200_000, k), directory="c-link")
        films.append(film)
        group[film.name] = "C"
    d_kinds = ["failed"] * D_FAILED + ["engine"] * D_ENGINE + ["mismatch"] * D_MISMATCH
    for k, kind in enumerate(d_kinds):  # D: metadata failures
        film = Film(_name(3_000_000, k), directory="d", kind=kind)
        films.append(film)
        group[film.name], kinds[_number(3_000_000, k)] = "D", kind
    for k in range(GROUPS["E"]):  # E: an invalid release date -> the real NFO stage fails
        film = Film(_name(4_000_000, k), directory="e", release="2024-13-45")
        films.append(film)
        group[film.name] = "E"
    for prefix, base, count in (("F", 5_000_000, GROUPS["F"]), ("G", 6_000_000, GROUPS["G"]),
                                ("H", 7_000_000, GROUPS["H"]), ("I", 8_000_000, GROUPS["I"])):
        for k in range(count):
            film = Film(_name(base, k), directory=prefix.lower(), extra=1 if prefix == "G" else 0)
            films.append(film)
            group[film.name], kinds[_number(base, k)] = prefix, "success"
    assert len(films) == 497
    return films, group, kinds


def _d_recovering() -> set[str]:
    recover, counts = set(), dict(D_RECOVER)
    kinds = ["failed"] * D_FAILED + ["engine"] * D_ENGINE + ["mismatch"] * D_MISMATCH
    for k, kind in enumerate(kinds):
        if counts[kind]:
            counts[kind] -= 1
            recover.add(_number(3_000_000, k))
    return recover


# --------------------------------------------------------------------------- run controls


class _FsPeak:
    """Wraps ``execute_filesystem``: concurrency peak; the first ``W`` calls wait until all ``W`` run together (so
    the peak is reached), then finish in start order or -- ``reverse`` -- in reverse start order."""

    def __init__(self, monkeypatch, workers: int, reverse: bool) -> None:
        self.cond = threading.Condition()
        self.active = 0
        self.peak = 0
        self.calls = 0
        self.workers = workers
        self.reverse = reverse
        self.held: list[int] = []
        self.gathered = False
        monkeypatch.setattr(execute_module, "execute_filesystem", self)

    def __call__(self, preflight):
        with self.cond:
            self.calls += 1
            number = self.calls
            self.active += 1
            self.peak = max(self.peak, self.active)
            held = number <= self.workers
            if held:
                self.held.append(number)
                if len(self.held) == self.workers:
                    self.gathered = True
                    self.cond.notify_all()
                assert self.cond.wait_for(lambda: self.gathered, WAIT), "the worker peak was never reached"
                if self.reverse:
                    assert self.cond.wait_for(lambda: self.held[-1] == number, WAIT)
        try:
            return execute_filesystem(preflight)
        finally:
            with self.cond:
                self.active -= 1
                if held:
                    self.held.remove(number)
                    self.cond.notify_all()


async def _reverse_release(recorder, task) -> None:
    released: set[str] = set()
    for _ in range(5_000_000):
        if task.done():
            return
        started = [key for key in recorder.calls if key in recorder.gates and key not in released]
        if started:
            recorder.gates[started[-1]].set()
            released.add(started[-1])
        await asyncio.sleep(0)
    raise AssertionError("the reverse release controller did not finish")


def _preview(corpus, orchestrator, items, reverse: bool):
    async def go():
        if not reverse:
            return await orchestrator.preview(items)
        for number in corpus.engine.script:
            corpus.engine.gate(number)
        for url in corpus.client.script:
            corpus.client.gate(url)
        task = asyncio.ensure_future(orchestrator.preview(items))
        await asyncio.gather(_reverse_release(corpus.engine, task), _reverse_release(corpus.client, task))
        return await task

    try:
        return run(go(), timeout=600)
    finally:
        corpus.engine.gates.clear()
        corpus.client.gates.clear()


# --------------------------------------------------------------------------- invariants


def _sha(path) -> str:
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def _summary(result) -> dict:
    summary = result.summary
    return {name: getattr(summary, name) for name in ("success", "partial", "failed", "aborted", "not_selected",
                                                      "blocked", "unprepared", "retryable", "deferred",
                                                      "non_retryable")}


def _kinds(result) -> collections.Counter:
    return collections.Counter(item.retry_kind for item in result.items)


def _all_sources_safe(items, hashes) -> None:
    """Section 35 core invariant for every one of the 500 inputs (repeated entries included): an item without a
    plan has no final path, so its source must hold the original bytes."""
    for item in items:
        if item.final_media_path is None:
            assert _sha(item.source_path) == hashes[item.source_path]
        else:
            assert_source_not_lost(item.source_path, item.final_media_path, hashes[item.source_path])


def _touched(result) -> tuple[set[str], set[str]]:
    targets, sources = set(), set()
    for item in result.items:
        if item.disposition in (D.EXECUTED, D.ABORTED):
            targets.add(os.path.normcase(item.target_directory))
            sources.add(os.path.normcase(item.source_path))
    return targets, sources


def _bystanders_unchanged(root, before, after, result) -> None:
    """Every file this execution did not own keeps its bytes, inode and mtime; every directory it did not own still
    exists (a directory's own mtime legitimately changes when an executed item's source / target entry changes)."""
    targets, sources = _touched(result)
    for relative, state in before.items():
        absolute = os.path.normcase(os.path.join(str(root), relative))
        if absolute in sources or any(absolute == t or absolute.startswith(t + os.sep) for t in targets):
            continue
        if state[0] == "dir":
            assert relative in after and after[relative][0] == "dir", relative
        else:
            assert after.get(relative) == state, relative


def _preview_read_only(corpus, call):
    before = tree_snapshot(corpus.root)
    value = call()
    assert tree_snapshot(corpus.root) == before  # zero mutation (section 16)
    return value


def _normalised(root, models) -> list[str]:
    text = str(root)
    out = []
    for model in models:
        shown = repr(projection(model)) + repr(model.summary)
        if hasattr(model, "outcome"):
            shown += repr(model.outcome)
        out.append(shown.replace(text.replace("\\", "\\\\"), "<ROOT>").replace(text, "<ROOT>"))
    return out


# --------------------------------------------------------------------------- the gate


def _gate(root, monkeypatch, *, reverse: bool):
    films, group, kinds = _films()
    corpus = Corpus(root, films)
    downloads = corpus.downloads
    links = [str(downloads / "c-link" / _name(2_200_000, k)) for k in range(2 * C_HARDLINK_PAIRS)]
    for first, second in zip(links[0::2], links[1::2]):  # C: two names, one inode, different numbers
        os.remove(second)
        os.link(first, second)
    for k in range(GROUPS["F"]):  # F: the target directory already exists (the user's)
        blocker = corpus.library / _number(5_000_000, k)
        blocker.mkdir()
        (blocker / "user-note.txt").write_bytes(b"mine")
    discovered = discover_media(str(downloads)).items
    assert len(discovered) == 497
    repeated = [i for i in discovered if os.path.basename(i.source_path) in
                {_name(2_100_000, k) for k in range(C_REPEATED_ENTRIES)}]
    items = tuple(discovered) + tuple(repeated)  # C: three entries appear twice
    assert len(items) == 500
    hashes = {item.source_path: _sha(item.source_path) for item in discovered}
    monkeypatch.setattr(execution_transfer, "_SAME_VOLUME_STRATEGY", "link")
    config = OrchestrationConfig(metadata=BatchConfig(max_in_flight_items=4), image_in_flight_items=4,
                                 filesystem_workers=4)  # default B, MAX_BATCH_ITEMS and image policy
    orchestrator = corpus.orchestrator(config=config)
    models = []

    # ---- g0: main preview + execute
    preview = _preview_read_only(corpus, lambda: _preview(corpus, orchestrator, items, reverse))
    assert corpus.engine.peak == 4 and corpus.client.peak == 4  # M and K reached and never exceeded
    summary = preview.summary
    assert dict(total=summary.total, ready=summary.ready, blocked=summary.blocked,
                unprepared=summary.unprepared) == MAIN_PREVIEW
    by_group: dict[str, list] = collections.defaultdict(list)
    for item in preview.items:
        by_group[group[os.path.basename(item.source_path)]].append(item)
    assert {g: len(v) for g, v in by_group.items()} == GROUPS
    assert {i.issue.reason for i in by_group["B"]} == {R.NUMBER_NOT_RECOGNIZED}
    assert {i.issue.reason for i in by_group["C"]} <= {R.DUPLICATE_SOURCE_IN_BATCH, R.DUPLICATE_TARGET_IN_BATCH}
    assert all(i.state is S.BLOCKED for i in by_group["C"])
    phase_a = [i for i in by_group["C"] if not os.path.basename(i.source_path).startswith("FC2-PPV-22")]
    phase_b = [i for i in by_group["C"] if os.path.basename(i.source_path).startswith("FC2-PPV-22")]
    assert len(phase_a) == 26 and len(phase_b) == 4
    # section 14.2: Phase A blocks before metadata (no metadata, no preflight, the engine never asked)
    assert all(i.metadata is None and i.preflight is None for i in phase_a)
    assert not {i.canonical_number for i in phase_a} & set(corpus.engine.calls)
    assert all(i.preflight is not None and i.issue.reason is R.DUPLICATE_SOURCE_IN_BATCH for i in phase_b)  # 14.3
    assert {i.issue.reason for i in by_group["D"]} == {R.METADATA_UNAVAILABLE, R.METADATA_ENGINE_FAILURE}
    assert {i.issue.reason for i in by_group["E"]} == {R.NFO_RENDER_FAILED}
    assert {i.issue.reason for i in by_group["F"]} == {R.PREFLIGHT_BLOCKED}
    assert all(i.state is S.READY for g in "AGHI" for i in by_group[g])
    models.append(preview)
    selection = tuple(sorted(i.index for i in preview.items if i.state is S.READY and group[
        os.path.basename(i.source_path)] != "I"))
    g_items = sorted(by_group["G"], key=lambda i: i.index)
    fails = g_items[:G_FAILED]
    unlinks = g_items[G_FAILED:G_FAILED + G_UNLINK]
    publishes = g_items[G_FAILED + G_UNLINK:G_FAILED + G_UNLINK + G_PUBLISH]
    writes = g_items[G_FAILED + G_UNLINK + G_PUBLISH:]
    before = tree_snapshot(corpus.root)
    with monkeypatch.context() as m:
        fault = fs_fault(m)
        for item in fails:  # before U1: the execution-time source revalidation fails -> FAILED
            fault.fail("execution", "lstat", os.path.basename(item.source_path), OSError(errno.EIO, "io"))
        for item in unlinks:  # U2 after the link publish: SOURCE_UNLINK_FAILED -> PARTIAL
            fault.fail("execution", "unlink", os.path.basename(item.source_path), OSError(errno.EACCES, "locked"))
        for item in publishes:  # U3: the NFO publish fails -> PARTIAL
            fault.fail("materialization", "publish", os.path.basename(item.nfo_target), OSError(errno.EIO, "io"))
        for item in writes:  # U3: the NFO write fails -> PARTIAL
            fault.fail("materialization", "write", item.target_directory, OSError(errno.ENOSPC, "full"), times=1)
        for item in by_group["H"]:  # U2: a foreign exception from the link primitive -> ABORTED
            fault.fail("execution", "link", os.path.basename(item.source_path), RuntimeError("foreign"))
        peak = _FsPeak(m, 4, reverse)
        result = orchestrator.execute(preview, selection=selection)
        assert peak.peak == 4  # W reached and never exceeded
    with pytest.raises(OrchestrationConsumedError):  # the preview executes once
        orchestrator.execute(preview)
    assert _summary(result) == MAIN_RESULT and result.outcome is BatchOutcome.PARTIAL
    assert _kinds(result) == collections.Counter({K.NONE: 90 + 310, K.RESUME: 15, K.FRESH_REEXECUTE: 15,
                                                  K.METADATA_REFETCH: 40, K.PREFLIGHT_RECHECK: 20,
                                                  K.DEFERRED: 10})
    executions = {i.index: i for i in result.items}
    assert {executions[i.index].issue.detail for i in fails} == {F.SOURCE_CHANGED}
    assert {executions[i.index].issue.detail for i in unlinks} == {F.SOURCE_UNLINK_FAILED}
    assert {executions[i.index].issue.detail for i in publishes} == {F.ARTIFACT_PUBLISH_FAILED}
    assert {executions[i.index].issue.detail for i in writes} == {F.ARTIFACT_WRITE_FAILED}
    assert {executions[i.index].disposition for i in by_group["H"]} == {D.ABORTED}
    for item in by_group["H"]:
        assert_source_not_lost(item.source_path, item.final_media_path, hashes[item.source_path])
    _all_sources_safe(result.items, hashes)
    _bystanders_unchanged(corpus.root, before, tree_snapshot(corpus.root), result)
    assert result.retained_retry_payload_bytes <= result.retention_budget_bytes
    models.append(result)

    # ---- g1: RESUME
    resumed = [executions[i.index] for i in unlinks + publishes + writes]
    published = {}
    for item in resumed:
        for effect in item.execution.completed_effects:
            if effect.kind in (EffectKind.ARTIFACT_PUBLISHED, EffectKind.MEDIA_PUBLISHED):
                st = os.stat(effect.path)
                published[effect.path] = (st.st_ino, st.st_mtime_ns)
    assert published
    engine_calls, client_calls = len(corpus.engine.calls), len(corpus.client.calls)
    retry1 = _preview_read_only(corpus, lambda: run(orchestrator.preview_retry(result, scope=G1_SCOPE)))
    assert (len(corpus.engine.calls), len(corpus.client.calls)) == (engine_calls, client_calls)
    assert len(retry1.items) == 15 and retry1.summary.ready == 15
    before = tree_snapshot(corpus.root)
    round1 = orchestrator.execute(retry1)
    assert round1.summary.success == 15 and round1.outcome is BatchOutcome.SUCCESS
    for path, identity in published.items():  # completed effects are never redone; the media never moves again
        st = os.stat(path)
        assert (st.st_ino, st.st_mtime_ns) == identity, path
    merged1 = merge_retry(result, round1)
    assert merged1.summary.success == 325 and merged1.outcome is BatchOutcome.PARTIAL
    _all_sources_safe(merged1.items, hashes)
    _bystanders_unchanged(corpus.root, before, tree_snapshot(corpus.root), round1)
    models += [retry1, round1, merged1]

    # ---- g2: the user removes 15 blockers; faults are gone; 30 metadata failures recover
    for k in range(F_REMOVED):
        shutil.rmtree(corpus.library / _number(5_000_000, k))
    for number in _d_recovering():
        corpus.engine.script[number] = "success"
    retry2 = _preview_read_only(corpus, lambda: run(orchestrator.preview_retry(merged1, scope=G2_SCOPE)))
    assert len(retry2.items) == 75
    assert (retry2.summary.ready, retry2.summary.blocked, retry2.summary.unprepared) == (60, 5, 10)
    before = tree_snapshot(corpus.root)
    round2 = orchestrator.execute(retry2)
    assert round2.summary.success == 60 and round2.outcome is BatchOutcome.PARTIAL
    merged2 = merge_retry(merged1, round2)
    assert merged2.summary.success == 385 and merged2.outcome is BatchOutcome.PARTIAL
    _all_sources_safe(merged2.items, hashes)
    _bystanders_unchanged(corpus.root, before, tree_snapshot(corpus.root), round2)
    models += [retry2, round2, merged2]

    # ---- g3: DEFERRED
    retry3 = _preview_read_only(corpus, lambda: run(orchestrator.preview_retry(merged2, scope=G3_SCOPE)))
    assert len(retry3.items) == 10 and retry3.summary.ready == 10
    round3 = orchestrator.execute(retry3)
    assert round3.summary.success == 10 and round3.outcome is BatchOutcome.SUCCESS
    merged3 = merge_retry(merged2, round3)
    assert merged3.summary.success == 395 and merged3.outcome is BatchOutcome.PARTIAL
    _all_sources_safe(merged3.items, hashes)
    models += [retry3, round3, merged3]

    # ---- g4: everything still retryable
    retry4 = _preview_read_only(corpus, lambda: run(orchestrator.preview_retry(merged3)))
    assert len(retry4.items) == 15 and retry4.summary.ready == 0
    round4 = orchestrator.execute(retry4)
    assert round4.summary.executed == 0 and round4.outcome is BatchOutcome.FAILED
    final = merge_retry(merged3, round4)
    assert final.outcome is BatchOutcome.PARTIAL
    assert {k: v for k, v in _summary(final).items() if k in FINAL} == FINAL
    for complete in (result, merged1, merged2, merged3, final):
        assert complete.retained_retry_payload_bytes <= complete.retention_budget_bytes
    _all_sources_safe(final.items, hashes)
    models += [retry4, round4, final]

    _assert_final_library(corpus, final, group, kinds)
    return corpus, models


def _assert_final_library(corpus, final, group, kinds) -> None:
    """The exact final library: every directory and every byte."""
    expected: dict[str, bytes | None] = {}
    successes = [i for i in final.items if i.execution_status is ExecutionStatus.SUCCESS]
    assert len(successes) == 395
    films = {f.name: f for f in _films()[0]}
    recovered = _d_recovering()
    for item in successes:
        name = os.path.basename(item.source_path)
        film, number = films[name], item.canonical_number
        directory = os.path.basename(item.target_directory)
        expected[directory] = None
        expected[os.path.relpath(item.final_media_path, corpus.library)] = _source_bytes(corpus, item)
        kind = "success" if number in recovered else kinds.get(number, "success")
        aggregation = build_metadata(number, kind, **corpus.engine.fields.get(number, {}))
        expected[os.path.relpath(item.nfo_target, corpus.library)] = render_movie_nfo(
            prepare_publication(item.plan, aggregation)).encode("utf-8")
        for role, present in (("poster", film.poster), ("fanart", film.fanart), ("thumb", film.thumb)):
            if present:
                expected[os.path.join(directory, f"{role}.jpg")] = corpus.client.script[image_url(number, role)].content
        expected[os.path.join(directory, "extrafanart")] = None
        for ordinal in range(film.extra):
            expected[os.path.join(directory, "extrafanart", f"extrafanart-{ordinal + 1:03d}.jpg")] = \
                corpus.client.script[image_url(number, f"extra{ordinal}")].content
    for k in range(F_REMOVED, GROUPS["F"]):  # the 5 blockers the user kept, untouched
        expected[_number(5_000_000, k)] = None
        expected[os.path.join(_number(5_000_000, k), "user-note.txt")] = b"mine"
    for item in final.items:  # ABORTED: P4-C7 created the target directory (U1) and stopped; nothing else
        if item.disposition is D.ABORTED:
            expected[os.path.basename(item.target_directory)] = None
    actual: dict[str, bytes | None] = {}
    for dirpath, dirnames, filenames in os.walk(corpus.library):
        for name in dirnames:
            actual[os.path.relpath(os.path.join(dirpath, name), corpus.library)] = None
        for name in filenames:
            path = os.path.join(dirpath, name)
            with open(path, "rb") as handle:
                actual[os.path.relpath(path, corpus.library)] = handle.read()
    assert not [p for p in actual if ".fc2tmp-" in p]  # no temporary residue (no leftover was ever recorded)
    assert set(actual) == set(expected)
    assert actual == expected


def _source_bytes(corpus, item) -> bytes:
    relative = os.path.relpath(item.source_path, corpus.downloads).replace(os.sep, "/")
    position = next(i for i, f in enumerate(_films()[0])
                    if (f"{f.directory}/{f.name}" if f.directory else f.name) == relative)
    film = _films()[0][position]
    if film.directory == "c-link":
        raise AssertionError("a hard-linked conflict item never succeeds")
    return b"media-%d-" % position + relative.encode()


def test_the_500_item_gate_with_a_deterministic_reversed_rerun(tmp_path, monkeypatch):
    first_corpus, first = _gate(tmp_path / "first", monkeypatch, reverse=False)
    first_text = _normalised(first_corpus.root, first)
    second_corpus, second = _gate(tmp_path / "second", monkeypatch, reverse=True)  # fresh tree, reversed orders
    second_text = _normalised(second_corpus.root, second)
    assert len(first_text) == len(second_text) == 14  # main preview + result, then 4 x (retry preview, round, merged)
    for position, (a, b) in enumerate(zip(first_text, second_text)):
        assert a == b, position
    outcomes = [m.outcome for m in first if type(m).__name__ == "BatchExecutionResult"]
    assert outcomes == [BatchOutcome.PARTIAL, BatchOutcome.SUCCESS, BatchOutcome.PARTIAL, BatchOutcome.PARTIAL,
                        BatchOutcome.PARTIAL, BatchOutcome.SUCCESS, BatchOutcome.PARTIAL, BatchOutcome.FAILED,
                        BatchOutcome.PARTIAL]


# --------------------------------------------------------------------------- resource sub-gates (small configurations)


def _bare_orchestrator(tmp_path, **kwargs):
    engine, client = ScriptedEngine(), ScriptedImageClient()
    (tmp_path / "lib").mkdir(exist_ok=True)
    return engine, client, BatchOrchestrator(engine, client, str(tmp_path / "lib"), **kwargs)


def _unrecognised(count: int) -> list[DiscoveredMediaItem]:
    return [media_item(i, f"holiday-{i:05d}.mp4") for i in range(count)]


def test_max_batch_items_is_accepted_and_one_more_fails_before_any_work(tmp_path, monkeypatch):
    engine, client, orchestrator = _bare_orchestrator(tmp_path)
    accepted = run(orchestrator.preview(_unrecognised(MAX_BATCH_ITEMS)))
    assert accepted.summary.total == MAX_BATCH_ITEMS == accepted.summary.unprepared
    with monkeypatch.context() as m:
        trap = mutation_traps(m)
        with pytest.raises(OrchestrationResourceLimitError) as info:
            run(orchestrator.preview(_unrecognised(MAX_BATCH_ITEMS + 1)))
    assert info.value.reason is ResourceLimitReason.BATCH_ITEM_LIMIT
    assert engine.calls == [] and client.calls == [] and trap.calls == []


class _CountingSequence(collections.abc.Sequence):
    """A custom Sequence that records ``__iter__`` / ``__getitem__`` / ``__len__`` use and elements produced."""

    def __init__(self, actual: int, claimed: int) -> None:
        self.actual, self.claimed = actual, claimed
        self.read = 0
        self.len_calls = 0
        self.getitem_calls = 0
        self.item = media_item(0, "holiday-00000.mp4")

    def __len__(self):
        self.len_calls += 1
        return self.claimed

    def __getitem__(self, index):
        self.getitem_calls += 1
        raise AssertionError("indexing is never needed")

    def __iter__(self):
        for _ in range(self.actual):
            self.read += 1
            yield self.item


@pytest.mark.parametrize("actual, claimed", [(MAX_BATCH_ITEMS + 1, MAX_BATCH_ITEMS + 1),
                                             (1_000_000, 1_000_000), (3000, 1)],
                         ids=["limit_plus_one", "lazy_huge", "lying_length"])
def test_the_bounded_snapshot_reads_at_most_limit_plus_one_through_preview(tmp_path, actual, claimed):
    engine, client, orchestrator = _bare_orchestrator(tmp_path)
    sequence = _CountingSequence(actual, claimed)
    with pytest.raises(OrchestrationResourceLimitError) as info:
        run(orchestrator.preview(sequence))
    assert info.value.reason is ResourceLimitReason.BATCH_ITEM_LIMIT
    assert sequence.read == MAX_BATCH_ITEMS + 1  # never one element more, never a full traversal / copy
    assert sequence.len_calls == 0 and sequence.getitem_calls == 0
    assert engine.calls == [] and client.calls == []


def _resource_model(preview) -> tuple[int, list[int]]:
    """``A_nfo`` (4 x NFO characters, ASCII) and the per-target image bytes ``a_i`` in index order."""
    nfo, images = 0, []
    for item in preview.items:
        if item.preflight is None:
            continue
        sizes = {ArtifactKind.NFO: 0}
        total = 0
        for request in item.preflight.artifacts:
            if request.kind is ArtifactKind.NFO:
                request.content.decode("ascii")
                sizes[ArtifactKind.NFO] = len(request.content)
            else:
                total += len(request.content)
        nfo += 4 * sizes[ArtifactKind.NFO]
        images.append(total)
    return nfo, images


def test_b_exact_admits_the_500_item_preview_and_one_byte_less_fails(tmp_path):
    films, _, _ = _films()
    reference_corpus = Corpus(tmp_path / "reference", films)
    reference = run(reference_corpus.orchestrator().preview(reference_corpus.items), timeout=600)
    a_nfo, images = _resource_model(reference)
    reservation = max(images)  # a small R that still fits every item's images
    b_exact = a_nfo + sum(images[:-1]) + reservation  # section 19.6.4 admission at the last image target
    policy = ImageAcquisitionPolicy(max_image_bytes=reservation, max_total_bytes=reservation)
    exact_corpus = Corpus(tmp_path / "exact", films)
    exact = run(exact_corpus.orchestrator(image_policy=policy, config=OrchestrationConfig(
        max_retained_artifact_bytes=b_exact)).preview(exact_corpus.items), timeout=600)
    assert _item_text(exact, exact_corpus.root) == _item_text(reference, reference_corpus.root)  # same preview
    short_corpus = Corpus(tmp_path / "short", films)
    snapshot = tree_snapshot(short_corpus.root)
    outcome = []
    with pytest.raises(OrchestrationResourceLimitError) as info:
        outcome.append(run(short_corpus.orchestrator(image_policy=policy, config=OrchestrationConfig(
            max_retained_artifact_bytes=b_exact - 1)).preview(short_corpus.items), timeout=600))
    assert info.value.reason is ResourceLimitReason.RETAINED_BYTES_LIMIT and outcome == []
    assert tree_snapshot(short_corpus.root) == snapshot


def _item_text(model, root) -> str:
    """The item part of the deterministic projection (the batch fields carry the different budget / policy)."""
    shown, root = repr(projection(model)[-1]), str(root)
    return shown.replace(root.replace("\\", "\\\\"), "<ROOT>").replace(root, "<ROOT>")


class _LedgerWatch:
    """Records every committed ledger state (``charged + reserved``) by substituting preview's ledger class."""

    def __init__(self, monkeypatch) -> None:
        self.states: list[int] = []
        watch = self

        class Watched(preview_module._Ledger):
            __slots__ = ()

            def _commit(self, charged, reserved):
                ok = super()._commit(charged, reserved)
                if ok:
                    watch.states.append(charged + reserved)
                return ok

        monkeypatch.setattr(preview_module, "_Ledger", Watched)


@pytest.mark.parametrize("reverse", [False, True], ids=["natural", "reversed"])
def test_reservation_admission_holds_two_in_flight_when_b_fits_two(tmp_path, monkeypatch, reverse):
    films = [Film(_name(9_000_000, k), poster=True, fanart=False, thumb=False) for k in range(6)]
    corpus = Corpus(tmp_path, films)
    size = None
    for k in range(6):
        content = minimal_jpeg(seed=k + 1, pad=500)
        size = len(content)
        corpus.client.script[image_url(_number(9_000_000, k), "poster")] = jpeg_response(content)
    probe_corpus = Corpus(tmp_path / "probe", films)
    a_nfo = _resource_model(run(probe_corpus.orchestrator().preview(probe_corpus.items)))[0]
    budget = a_nfo + 2 * size  # room for exactly two reservations
    watch = _LedgerWatch(monkeypatch)
    real_acquire = preview_module.acquire_images
    flight = {"active": 0, "peak": 0, "admitted": []}

    async def counting(record, client, *, policy=None):
        flight["active"] += 1
        flight["peak"] = max(flight["peak"], flight["active"])
        flight["admitted"].append(record.plan.canonical_number)
        try:
            return await real_acquire(record, client, policy=policy)
        finally:
            flight["active"] -= 1

    monkeypatch.setattr(preview_module, "acquire_images", counting)
    policy = ImageAcquisitionPolicy(max_image_bytes=size, max_total_bytes=size)
    orchestrator = corpus.orchestrator(image_policy=policy, config=OrchestrationConfig(
        image_in_flight_items=4, max_retained_artifact_bytes=budget))
    with pytest.raises(OrchestrationResourceLimitError) as info:
        _preview(corpus, orchestrator, corpus.items, reverse)
    assert info.value.reason is ResourceLimitReason.RETAINED_BYTES_LIMIT
    assert flight["peak"] <= 2 and flight["peak"] == 2
    assert sorted(flight["admitted"]) == [_number(9_000_000, 0), _number(9_000_000, 1)]  # the same, any order
    assert watch.states and max(watch.states) <= budget


# --------------------------------------------------------------------------- multi-generation retention (35.1.1)

D_NAMES = [_name(9_100_000, k) for k in range(4)]
M_NAMES = [_name(9_200_000, k) for k in range(4)]


class _Retention:
    def __init__(self, tmp_path, *, delta: int = 0) -> None:
        def films(metadata_kind):
            return ([Film(n, poster=True, fanart=False, thumb=False) for n in D_NAMES]
                    + [Film(n, kind=metadata_kind, poster=True, fanart=False, thumb=False) for n in M_NAMES])

        def pad(corpus):
            sizes = set()
            for seed, name in enumerate(D_NAMES + M_NAMES, start=1):
                content = minimal_jpeg(seed=seed, pad=40_000)
                sizes.add(len(content))
                corpus.client.script[image_url("FC2-" + name[8:-4], "poster")] = jpeg_response(content)
            return sizes.pop()

        calibration = Corpus(tmp_path / "calibration", films("success"))
        self.I = pad(calibration)
        nfo = {len(r.content) for i in run(calibration.orchestrator().preview(calibration.items)).items
               for r in i.preflight.artifacts if r.kind is ArtifactKind.NFO}
        assert len(nfo) == 1
        self.L = nfo.pop()
        assert self.I > 2 * self.L and self.I >= 8 * self.L
        self.pay, self.need = self.L + self.I, 4 * self.L + self.I
        self.payD = 4 * self.pay
        self.B = self.payD + self.need + delta
        self.corpus = Corpus(tmp_path / "lineage", films("failed"))
        pad(self.corpus)
        policy = ImageAcquisitionPolicy(max_image_bytes=self.I, max_total_bytes=self.I)
        self.orchestrator = self.corpus.orchestrator(image_policy=policy, config=OrchestrationConfig(
            metadata=BatchConfig(max_in_flight_items=1), image_in_flight_items=1, filesystem_workers=1,
            max_retained_artifact_bytes=self.B))
        self.preview = run(self.orchestrator.preview(self.corpus.items))
        self.index = {os.path.basename(i.source_path): i.index for i in self.preview.items}

    def recover(self, k: int) -> None:
        self.corpus.engine.script["FC2-" + M_NAMES[k][8:-4]] = "success"

    def retry(self, previous, kind):
        return run(self.orchestrator.preview_retry(previous, scope=frozenset({kind})))


def test_multi_generation_retention_g0_to_g4(tmp_path):
    s = _Retention(tmp_path)
    g0 = s.orchestrator.execute(s.preview, selection=())
    assert g0.retained_retry_payload_bytes == s.payD <= s.B
    s.recover(0)
    retry1 = s.retry(g0, K.METADATA_REFETCH)
    assert retry1.retry_budget_bytes == s.B - s.payD == s.need  # exactly admitted
    g1 = merge_retry(g0, s.orchestrator.execute(retry1, selection=()))
    assert g1.retained_retry_payload_bytes == s.payD + s.pay <= s.B
    s.recover(1)
    with pytest.raises(OrchestrationResourceLimitError) as info:  # available need - pay < need
        s.retry(g1, K.METADATA_REFETCH)
    assert info.value.reason is ResourceLimitReason.RETAINED_BYTES_LIMIT
    assert not _consumption.RESULT_RETRIES.is_registered(g1.result_id)
    retry2 = s.retry(g1, K.DEFERRED)
    g2 = merge_retry(g1, s.orchestrator.execute(retry2, selection=(s.index[M_NAMES[0]],)))
    assert g2.retained_retry_payload_bytes == s.payD
    retry3 = s.retry(g2, K.METADATA_REFETCH)
    assert retry3.retry_budget_bytes == s.need
    g3 = merge_retry(g2, s.orchestrator.execute(retry3, selection=()))
    assert g3.retained_retry_payload_bytes == s.payD + s.pay <= s.B
    g4 = merge_retry(g3, s.orchestrator.execute(s.retry(g3, K.DEFERRED)))
    assert g4.retained_retry_payload_bytes == 0 and g4.generation == 4
    assert [g4.items[s.index[n]].retry_kind for n in M_NAMES[2:]] == [K.METADATA_REFETCH] * 2
    for complete in (g0, g1, g2, g3, g4):
        assert complete.retained_retry_payload_bytes <= complete.retention_budget_bytes == s.B
