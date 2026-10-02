"""P4-C8 S5: real end-to-end integration (contract sections 15, 18, 31, 35 "integration").

A dirty download tree (nested directories, a Unicode directory, upper / mixed case video extensions, companion
files) is scanned by the real ``discover_media``; its ``DiscoveryResult.items`` go through preview -> execute on the
real stack. The final library is listed exactly: every relative path, every byte (media unchanged, the NFO equal to
the real P4-C4 renderer's output, images equal to what the P4-C5 acquisition fetched, extrafanart names and order).
The production package itself never calls ``discover_media``.
"""

from __future__ import annotations

import hashlib
import importlib
import os
import sys

import pytest

from fc2_organizer.discovery import discover_media
from fc2_organizer.execution import ExecutionStatus, PreflightBlockReason
from fc2_organizer.nfo import render_movie_nfo
from fc2_organizer.orchestration import (
    BatchOutcome,
    ExecutionDisposition as D,
    IssueReason as R,
    PreviewState as S,
    merge_retry,
)
from fc2_organizer.planning import build_organize_plan
from fc2_organizer.publication import prepare_publication

from ._fakes import build_metadata
from ._helpers import Corpus, Film, assert_source_not_lost, image_url, mutation_traps, run, tree_snapshot

FILMS = [
    Film("FC2-PPV-1000001.MP4", directory="incoming/batch-a", extra=3),
    Film("FC2-PPV-1000002.Mkv", directory="映画/新しい"),
    Film("fc2ppv1000003.mp4", thumb=False, extra=1),
]
COMPANIONS = {"incoming/batch-a/FC2-PPV-1000001.nfo": b"<old/>", "incoming/batch-a/cover.jpg": b"jpeg",
              "映画/新しい/readme.txt": b"notes", "notes.txt": b"x"}


def _listing(root) -> dict[str, bytes | None]:
    found = {}
    for dirpath, dirnames, filenames in os.walk(root):
        for name in dirnames:
            found[os.path.relpath(os.path.join(dirpath, name), root)] = None
        for name in filenames:
            path = os.path.join(dirpath, name)
            with open(path, "rb") as handle:
                found[os.path.relpath(path, root)] = handle.read()
    return found


def _dirty_corpus(tmp_path):
    corpus = Corpus(tmp_path, list(FILMS))
    for relative, content in COMPANIONS.items():
        path = corpus.downloads / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    return corpus


def test_a_dirty_download_tree_becomes_exactly_the_expected_library(tmp_path):
    corpus = _dirty_corpus(tmp_path)
    discovered = discover_media(str(corpus.downloads))  # the caller discovers; P4-C8 never does
    names = sorted(os.path.basename(i.source_path) for i in discovered.items)
    assert names == sorted(f.name for f in FILMS)  # companions are not media
    originals = {}
    for item in discovered.items:
        with open(item.source_path, "rb") as handle:
            originals[item.source_path] = handle.read()
    orchestrator = corpus.orchestrator()
    preview = run(orchestrator.preview(discovered.items))
    assert [i.state for i in preview.items] == [S.READY] * 3
    result = orchestrator.execute(preview)
    assert result.outcome is BatchOutcome.SUCCESS and result.summary.success == 3
    assert all(i.execution_status is ExecutionStatus.SUCCESS for i in result.items)

    expected: dict[str, bytes | None] = {}
    for item in preview.items:
        number = item.canonical_number
        film = next(f for f in FILMS if os.path.basename(item.source_path) == f.name)
        fields = corpus.engine.fields[number]
        directory = os.path.basename(item.target_directory)
        assert directory == number  # the P4-C2 directory naming
        expected[directory] = None
        extension = os.path.splitext(item.source_path)[1].lower()  # the source extension, lower-cased
        expected[os.path.join(directory, f"{number}{extension}")] = originals[item.source_path]
        aggregation = build_metadata(number, "success", **fields)
        plan = build_organize_plan(item.media_item, number, aggregation.metadata, str(corpus.library))
        nfo = render_movie_nfo(prepare_publication(plan, aggregation)).encode("utf-8")
        expected[os.path.join(directory, f"{number}.nfo")] = nfo  # the real P4-C4 renderer
        for role, present in (("poster", film.poster), ("fanart", film.fanart), ("thumb", film.thumb)):
            if present:
                expected[os.path.join(directory, f"{role}.jpg")] = corpus.client.script[image_url(number, role)].content
        expected[os.path.join(directory, "extrafanart")] = None
        for ordinal in range(film.extra):
            content = corpus.client.script[image_url(number, f"extra{ordinal}")].content
            expected[os.path.join(directory, "extrafanart", f"extrafanart-{ordinal + 1:03d}.jpg")] = content
    assert _listing(corpus.library) == expected  # every path and every byte, nothing more
    for item in preview.items:
        assert not os.path.exists(item.source_path)
        assert_source_not_lost(item.source_path, item.final_media_path,
                               hashlib.sha256(originals[item.source_path]).hexdigest())
    for relative, content in COMPANIONS.items():  # companions are untouched
        assert (corpus.downloads / relative).read_bytes() == content


def test_a_missing_library_root_blocks_and_changes_nothing(tmp_path):
    corpus = Corpus(tmp_path, [Film("FC2-PPV-1000001.mp4")], library=False)
    orchestrator = corpus.orchestrator()
    snapshot = tree_snapshot(tmp_path)
    preview = run(orchestrator.preview(discover_media(str(corpus.downloads)).items))
    item = preview.items[0]
    assert item.state is S.BLOCKED and item.issue.reason is R.PREFLIGHT_BLOCKED
    assert [b.reason for b in item.blockers] == [PreflightBlockReason.LIBRARY_ROOT_MISSING]
    result = orchestrator.execute(preview)
    assert result.items[0].disposition is D.NOT_READY and result.outcome is BatchOutcome.FAILED
    assert tree_snapshot(tmp_path) == snapshot and not corpus.library.exists()


def test_a_junction_library_root_blocks_and_writes_nothing_through_it(tmp_path):
    if os.name != "nt":
        pytest.skip("junctions are Windows-only (frozen platform skip)")
    import _winapi

    corpus = Corpus(tmp_path, [Film("FC2-PPV-1000001.mp4")], library=False)
    real = tmp_path / "real-library"
    real.mkdir()
    _winapi.CreateJunction(str(real), str(corpus.library))
    orchestrator = corpus.orchestrator()
    preview = run(orchestrator.preview(discover_media(str(corpus.downloads)).items))
    item = preview.items[0]
    assert item.state is S.BLOCKED and item.issue.reason is R.PREFLIGHT_BLOCKED
    assert [b.reason for b in item.blockers] == [PreflightBlockReason.LIBRARY_ROOT_IS_LINK]
    snapshot = tree_snapshot(real)
    orchestrator.execute(preview)
    assert tree_snapshot(real) == snapshot == {} and os.path.exists(item.source_path)


_BLOCKED = ("amane", "requests", "sqlite3", "shelve", "dbm", "pickle")


class _Blocker:
    def __init__(self) -> None:
        self.attempts: list[str] = []

    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".")[0] in _BLOCKED:
            self.attempts.append(fullname)
            raise ImportError(f"forbidden module during orchestration: {fullname}")
        return None


def test_the_real_lifecycle_runs_with_forbidden_modules_blocked(tmp_path):
    corpus = _dirty_corpus(tmp_path)
    saved = {name: sys.modules.pop(name) for name in list(sys.modules) if name.split(".")[0] in _BLOCKED}
    blocker = _Blocker()
    sys.meta_path.insert(0, blocker)
    try:
        for root in _BLOCKED:  # positive control: an import of any of them is caught and recorded
            with pytest.raises(ImportError):
                importlib.import_module(root)
        assert sorted(blocker.attempts) == sorted(_BLOCKED)
        blocker.attempts.clear()
        orchestrator = corpus.orchestrator()
        preview = run(orchestrator.preview(discover_media(str(corpus.downloads)).items))
        result = orchestrator.execute(preview, selection=(0,))
        retry = run(orchestrator.preview_retry(result))
        merged = merge_retry(result, orchestrator.execute(retry))
        assert merged.summary.success == 3 and merged.outcome is BatchOutcome.SUCCESS
        assert blocker.attempts == []  # nothing in the lifecycle tried to import a forbidden module
        assert not any(name.split(".")[0] in _BLOCKED for name in sys.modules)
    finally:
        sys.meta_path.remove(blocker)
        sys.modules.update(saved)


def test_the_filesystem_guards_are_not_vacuous(tmp_path, monkeypatch):
    """Positive controls: the tree snapshot sees a byte change, a new entry and a removal; the mutation trap
    records (and refuses) a real write attempt."""
    (tmp_path / "a.bin").write_bytes(b"one")
    before = tree_snapshot(tmp_path)
    (tmp_path / "a.bin").write_bytes(b"two")
    assert tree_snapshot(tmp_path) != before
    (tmp_path / "b").mkdir()
    changed = tree_snapshot(tmp_path)
    os.rmdir(tmp_path / "b")
    assert tree_snapshot(tmp_path) != changed
    with monkeypatch.context() as m:
        trap = mutation_traps(m)
        with pytest.raises(AssertionError):
            open(tmp_path / "c.bin", "wb")
        with pytest.raises(AssertionError):
            os.mkdir(tmp_path / "d")
    assert trap.calls == ["open(write)", "os.mkdir"] and not (tmp_path / "c.bin").exists()
