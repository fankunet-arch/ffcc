"""P4-C6 substep 3: integrated synthetic / stress gate (contract section 26).

Test-layer orchestration only: this file creates its own temporary directories (the job
P4-C7 will own), builds requests with ``build_artifact_requests`` and writes them one at a
time with ``materialize_artifact``. The production package gains nothing.

Every expectation (order, kinds, target paths, ordinals, bytes, SHA-256) is derived from the
synthetic *case definition* -- never read back from the production result. No network, no
user files: every path lives under pytest's ``tmp_path``.
"""

from __future__ import annotations

import ast
import errno
import hashlib
import os
import threading
from dataclasses import dataclass
from pathlib import Path

import pytest

from fc2_metadata_core.models import NormalizedMetadata
from fc2_organizer.discovery import DiscoveredMediaItem
from fc2_organizer.images import AcquiredImage, ImageAcquisitionResult, ImageRole
from fc2_organizer.materialization import (
    ArtifactCleanupError,
    ArtifactKind,
    ArtifactPublishError,
    ArtifactWriteError,
    ArtifactWriteRequest,
    ArtifactWriteStage,
    MaterializedArtifact,
    ParentDirectoryMissingError,
    TargetExistsError,
    materialize_artifact,
)
from fc2_organizer import materialization as materialization_pkg
from fc2_organizer.materialization import atomic
from fc2_organizer.materialization.mapping import build_artifact_requests, extrafanart_filename
from fc2_organizer.planning import build_organize_plan

from ._helpers import STRATEGIES, TEMP_PREFIX, TEMP_SUFFIX, apply_strategy, failing, inject

GATE_SIZE = 300
MAT_SRC = Path(__file__).resolve().parents[3] / "src" / "fc2_organizer" / "materialization"

_TITLES = [
    "Example Title", "日本語タイトル", "Ünïcödé & <XML> \"quoted\"", "🎬 emoji title 🎞️",
    "ﾊﾝｶｸｶﾀｶﾅ", "é decomposed", "Tab\tand spaces  ", "中文标题 第二部",
]
_MAIN = ("poster", "fanart", "thumb")
_KIND = {"poster": ArtifactKind.POSTER, "fanart": ArtifactKind.FANART, "thumb": ArtifactKind.THUMB}
_ROLE = {"poster": ImageRole.POSTER, "fanart": ImageRole.FANART, "thumb": ImageRole.THUMB}
_FILE = {"poster": "poster.jpg", "fanart": "fanart.jpg", "thumb": "thumb.jpg"}


# --------------------------------------------------------------------------- case definition


@dataclass(frozen=True)
class Case:
    index: int
    number: str
    nfo_text: str
    main: dict            # role name -> bytes, only for present roles
    extras: tuple         # tuple[bytes, ...] in acquisition order


def _jpeg(tag: str) -> bytes:
    body = hashlib.sha256(tag.encode()).digest() * (1 + len(tag) % 5)
    return b"\xff\xd8\xff\xe0" + body + b"\x00\xff\x00" + b"\xff\xd9"


def _case(i: int) -> Case:
    number = f"FC2-{1_000_000 + i * 7919}"
    title = _TITLES[i % len(_TITLES)]
    nfo = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<movie>\n'
        f"  <title>{title} #{i}</title>\n  <num>{number}</num>\n</movie>\n"
    )
    if i % 11 == 0:
        nfo = nfo.replace("\n", "\r\n")  # CRLF must survive untouched
    group = i // 100
    main: dict = {}
    extras: tuple = ()
    if group == 1:
        mask = 1 + i % 7                      # the 7 non-empty subsets of poster/fanart/thumb
    elif group == 2:
        mask = i % 8                          # all 8 subsets, including none
    else:
        mask = 0
    for bit, role in enumerate(_MAIN):
        if mask & (1 << bit):
            main[role] = _jpeg(f"{number}-{role}")
    if i % 5 == 0 and "poster" in main and "fanart" in main:
        main["fanart"] = main["poster"]       # duplicate bytes across roles: never de-duplicated
    if group == 2:
        count = 1 + i % 13
        extras = tuple(_jpeg(f"{number}-extra-{k % 4}") for k in range(count))  # repeats when count > 4
    return Case(i, number, nfo, main, extras)


CASES = [_case(i) for i in range(GATE_SIZE)]


def _acquired(role: ImageRole, content: bytes, idx: int) -> AcquiredImage:
    return AcquiredImage(role=role, candidate_index=idx, content=content, width=640, height=480,
                         size_bytes=len(content), sha256=hashlib.sha256(content).hexdigest())


def _images(case: Case) -> ImageAcquisitionResult:
    return ImageAcquisitionResult(
        **{role: _acquired(_ROLE[role], data, 0) for role, data in case.main.items()},
        extrafanart=tuple(_acquired(ImageRole.EXTRAFANART, d, k) for k, d in enumerate(case.extras)),
    )


def _plan(case: Case, library_root: str):
    source = os.path.join(library_root, "incoming", f"dirty name {case.index}.MP4")
    item = DiscoveredMediaItem(index=case.index, source_path=source, relative_path=f"dirty name {case.index}.MP4",
                               extension=".MP4", size=1000 + case.index)
    return build_organize_plan(item, case.number, NormalizedMetadata(number=case.number, title="t"), library_root)


def _expected(case: Case, library_root: str) -> list[tuple[ArtifactKind, str, int | None, bytes]]:
    """Independent expectation from the frozen v1.0 layout + section 18-21 rules."""
    film = os.path.join(library_root, case.number)
    out = [(ArtifactKind.NFO, os.path.join(film, f"{case.number}.nfo"), None, case.nfo_text.encode("utf-8"))]
    for role in _MAIN:
        if role in case.main:
            out.append((_KIND[role], os.path.join(film, _FILE[role]), None, case.main[role]))
    for k, data in enumerate(case.extras, start=1):
        out.append((ArtifactKind.EXTRAFANART, os.path.join(film, "extrafanart", f"extrafanart-{k:03d}.jpg"), k, data))
    return out


def _read(path: str) -> bytes:
    with open(path, "rb") as fh:
        return fh.read()


def _prepare_dirs(plan) -> None:
    # Test-owned setup standing in for P4-C7: the package itself never creates directories.
    os.makedirs(plan.extrafanart_directory.absolute_path)


def _no_temp_residue(directory: str) -> bool:
    return not any(name.startswith(TEMP_PREFIX) for name in os.listdir(directory))


# --------------------------------------------------------------------------- 300-case gate


def test_gate_case_mix_is_as_specified():
    groups = [sum(1 for c in CASES if c.index // 100 == g) for g in range(3)]
    assert groups == [100, 100, 100]
    assert all(not c.main and not c.extras for c in CASES[:100])
    assert all(c.main and not c.extras for c in CASES[100:200])
    assert all(c.extras for c in CASES[200:300])
    assert {frozenset(c.main) for c in CASES[100:200]} == {
        frozenset(s) for s in (("poster",), ("fanart",), ("thumb",), ("poster", "fanart"), ("poster", "thumb"),
                               ("fanart", "thumb"), ("poster", "fanart", "thumb"))}
    assert any(c.main.get("poster") is not None and c.main.get("poster") == c.main.get("fanart") for c in CASES)
    assert any(len(set(c.extras)) < len(c.extras) for c in CASES)
    assert max(len(c.extras) for c in CASES) == 13


def test_synthetic_gate_300_films_materialize_exactly(tmp_path):
    totals = {"films": 0, "files": 0, "extrafanart": 0, "bytes": 0}
    for case in CASES:
        root = str(tmp_path / f"lib{case.index:03d}")
        plan = _plan(case, root)
        images = _images(case)
        requests = build_artifact_requests(plan, case.nfo_text, images)
        expected = _expected(case, root)

        # request order / kind / target / ordinal / exact bytes, before any write
        assert [(r.kind, r.target_path, r.ordinal, r.content) for r in requests] == expected, case.index
        # image bytes are the acquired objects themselves (identity), in acquisition order
        sources = [getattr(images, role) for role in _MAIN if role in case.main] + list(images.extrafanart)
        assert all(r.content is s.content for r, s in zip(requests[1:], sources, strict=True)), case.index
        # replay is identical
        assert build_artifact_requests(plan, case.nfo_text, images) == requests

        _prepare_dirs(plan)
        for req, (kind, path, _ordinal, data) in zip(requests, expected, strict=True):
            result = materialize_artifact(req)
            assert type(result) is MaterializedArtifact
            assert result.target_path == path
            assert result.size_bytes == len(data)
            assert result.sha256 == hashlib.sha256(data).hexdigest()
            on_disk = _read(path)
            assert on_disk == data, (case.index, kind)
            if kind is ArtifactKind.NFO:
                assert not on_disk.startswith(b"\xef\xbb\xbf")
                assert on_disk.decode("utf-8") == case.nfo_text
            totals["files"] += 1
            totals["bytes"] += len(data)

        film = plan.target_directory.absolute_path
        expected_top = {os.path.basename(p) for k, p, _, _ in expected if k is not ArtifactKind.EXTRAFANART}
        assert set(os.listdir(film)) == expected_top | {"extrafanart"}, case.index
        assert sorted(os.listdir(plan.extrafanart_directory.absolute_path)) == [
            f"extrafanart-{k:03d}.jpg" for k in range(1, len(case.extras) + 1)]
        assert _no_temp_residue(film) and _no_temp_residue(plan.extrafanart_directory.absolute_path)
        totals["films"] += 1
        totals["extrafanart"] += len(case.extras)

    assert totals["films"] == GATE_SIZE
    assert totals["files"] == GATE_SIZE + sum(len(c.main) for c in CASES) + sum(len(c.extras) for c in CASES)
    assert totals["extrafanart"] == sum(len(c.extras) for c in CASES) > 0


# --------------------------------------------------------------------------- extrafanart boundary


@pytest.mark.parametrize(("ordinal", "name"), [
    (1, "extrafanart-001.jpg"), (12, "extrafanart-012.jpg"),
    (999, "extrafanart-999.jpg"), (1000, "extrafanart-1000.jpg"),
])
def test_gate_extrafanart_boundary_names(ordinal, name):
    assert extrafanart_filename(ordinal) == name


def test_gate_1000_extrafanart_mapping_in_memory_no_maximum(tmp_path):
    root = str(tmp_path / "lib")
    case = Case(0, "FC2-1234567", CASES[0].nfo_text, {}, tuple(_jpeg(f"x{k % 3}") for k in range(1000)))
    plan = _plan(case, root)
    requests = build_artifact_requests(plan, case.nfo_text, _images(case))
    assert [(r.kind, r.target_path, r.ordinal, r.content) for r in requests] == _expected(case, root)
    assert os.path.basename(requests[-1].target_path) == "extrafanart-1000.jpg"
    assert not os.path.exists(root)  # mapping only: nothing written


# --------------------------------------------------------------------------- overwrite NEVER


@pytest.mark.parametrize("kind", list(ArtifactKind), ids=lambda k: k.name)
def test_gate_overwrite_never_for_every_kind(tmp_path, kind):
    case = CASES[207]  # has poster/fanart/thumb + extrafanart
    assert set(case.main) == set(_MAIN) and case.extras
    root = str(tmp_path / "lib")
    plan = _plan(case, root)
    _prepare_dirs(plan)
    req = next(r for r in build_artifact_requests(plan, case.nfo_text, _images(case)) if r.kind is kind)
    original = b"ORIGINAL-" + kind.name.encode() + bytes(range(256))
    with open(req.target_path, "wb") as fh:
        fh.write(original)
    parent = os.path.dirname(req.target_path)
    before_listing = sorted(os.listdir(parent))
    before_stat = os.stat(req.target_path)

    with pytest.raises(TargetExistsError):
        materialize_artifact(req)

    assert _read(req.target_path) == original                       # bytes unchanged
    after_stat = os.stat(req.target_path)
    assert (after_stat.st_ino, after_stat.st_mtime_ns) == (before_stat.st_ino, before_stat.st_mtime_ns)
    assert sorted(os.listdir(parent)) == before_listing              # no suffix, no temp residue


# --------------------------------------------------------------------------- partial success


def test_gate_partial_success_is_never_rolled_back(tmp_path):
    case = next(c for c in CASES[100:200] if "poster" in c.main)
    plan = _plan(case, str(tmp_path / "lib"))
    _prepare_dirs(plan)
    requests = build_artifact_requests(plan, case.nfo_text, _images(case))
    nfo, poster = requests[0], next(r for r in requests if r.kind is ArtifactKind.POSTER)
    with open(poster.target_path, "wb") as fh:
        fh.write(b"PRE-EXISTING POSTER")
    materialize_artifact(nfo)
    with pytest.raises(TargetExistsError):
        materialize_artifact(poster)
    assert _read(nfo.target_path) == case.nfo_text.encode("utf-8")
    assert _read(poster.target_path) == b"PRE-EXISTING POSTER"


# --------------------------------------------------------------------------- failure injection regression


def _plant(directory: str) -> dict:
    planted = {f"{TEMP_PREFIX}{'e' * 32}{TEMP_SUFFIX}": b"foreign temp", "other.tmp": b"other", "x.part": b"part"}
    for name, data in planted.items():
        with open(os.path.join(directory, name), "wb") as fh:
            fh.write(data)
    return planted


def _close_then_fail(fd):
    os.close(fd)
    raise OSError(errno.EIO, "close failed")


_INJECTIONS = {
    "write": ({"write": failing(OSError(errno.ENOSPC, "full"))}, ArtifactWriteError, ArtifactWriteStage.WRITE),
    "flush": ({"fsync": failing(OSError(errno.EIO, "io"))}, ArtifactWriteError, ArtifactWriteStage.FLUSH),
    "close": ({"close": _close_then_fail}, ArtifactWriteError, ArtifactWriteStage.CLOSE),
    "publish": ({"publish": failing(PermissionError(errno.EACCES, "denied"))}, ArtifactPublishError, None),
}


@pytest.mark.parametrize("strategy", STRATEGIES)
@pytest.mark.parametrize("stage", list(_INJECTIONS))
def test_gate_failure_injection_through_materialize_artifact(tmp_path, monkeypatch, strategy, stage):
    apply_strategy(monkeypatch, strategy)
    ops, error_type, write_stage = _INJECTIONS[stage]
    case = CASES[260]
    plan = _plan(case, str(tmp_path / "lib"))
    _prepare_dirs(plan)
    film = plan.target_directory.absolute_path
    planted = _plant(film)
    created = []
    real_open = atomic._FS.open
    inject(monkeypatch, open=lambda p, f, m: (created.append(p), real_open(p, f, m))[1], **ops)

    nfo = build_artifact_requests(plan, case.nfo_text, _images(case))[0]
    with pytest.raises(error_type) as info:
        materialize_artifact(nfo)
    if write_stage is not None:
        assert info.value.stage is write_stage
    assert not os.path.exists(nfo.target_path)                     # no partial final
    assert len(created) == 1 and not os.path.exists(created[0])    # exact owned temp removed
    assert set(os.listdir(film)) == set(planted) | {"extrafanart"}  # unrelated temps survive
    for name, data in planted.items():
        assert _read(os.path.join(film, name)) == data


def test_gate_cleanup_failure_is_typed_and_only_own_temp_leaks(tmp_path, monkeypatch):
    case = CASES[260]
    plan = _plan(case, str(tmp_path / "lib"))
    _prepare_dirs(plan)
    film = plan.target_directory.absolute_path
    planted = _plant(film)
    token = "c" * 32
    inject(monkeypatch, token=lambda n: token, fsync=failing(OSError(errno.EIO, "io")),
           unlink=failing(PermissionError(errno.EACCES, "denied")))
    nfo = build_artifact_requests(plan, case.nfo_text, _images(case))[0]
    with pytest.raises(ArtifactCleanupError) as info:
        materialize_artifact(nfo)
    assert info.value.target_published is False and type(info.value.primary) is ArtifactWriteError
    assert not os.path.exists(nfo.target_path)
    assert set(os.listdir(film)) == set(planted) | {"extrafanart", f"{TEMP_PREFIX}{token}{TEMP_SUFFIX}"}


# --------------------------------------------------------------------------- concurrent same target


def _race(requests_by_writer, barrier_publish, monkeypatch):
    if barrier_publish:
        barrier = threading.Barrier(len(requests_by_writer), timeout=10)
        real = atomic._FS.publish
        inject(monkeypatch, publish=lambda s, d: (barrier.wait(), real(s, d))[1])
    outcomes = []
    lock = threading.Lock()

    def run(req):
        try:
            res = ("ok", materialize_artifact(req))
        except BaseException as exc:  # noqa: BLE001 -- recorded and asserted
            res = ("err", exc)
        with lock:
            outcomes.append((req, res))

    threads = [threading.Thread(target=run, args=(r,)) for r in requests_by_writer]
    for t in threads:
        t.start()
    for t in threads:
        t.join(30)
    assert not any(t.is_alive() for t in threads)
    return outcomes


@pytest.mark.parametrize("strategy", STRATEGIES)
@pytest.mark.parametrize("barrier_publish", [True, False], ids=["barrier-forced", "unsynchronised"])
def test_gate_same_target_race_single_winner(tmp_path, monkeypatch, strategy, barrier_publish):
    apply_strategy(monkeypatch, strategy)
    directory = tmp_path / "film"
    directory.mkdir()
    target = str(directory / "poster.jpg")
    writers = 2 if barrier_publish else 8
    reqs = [ArtifactWriteRequest(ArtifactKind.POSTER, target, _jpeg(f"writer-{w}") * (50 + w)) for w in range(writers)]
    for _round in range(1 if barrier_publish else 5):
        for name in os.listdir(directory):
            os.unlink(directory / name)
        outcomes = _race(reqs, barrier_publish, monkeypatch)
        winners = [(req, res[1]) for req, res in outcomes if res[0] == "ok"]
        losers = [res[1] for _, res in outcomes if res[0] == "err"]
        assert len(winners) == 1
        assert all(type(e) is TargetExistsError for e in losers)
        win_req, win_res = winners[0]
        assert _read(target) == win_req.content and win_res.sha256 == hashlib.sha256(win_req.content).hexdigest()
        assert os.listdir(directory) == ["poster.jpg"]


# --------------------------------------------------------------------------- architecture regression


def _calls(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            f = node.func
            yield node.lineno, (f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", None))


def test_gate_architecture_regression():
    files = sorted(MAT_SRC.glob("*.py"))
    names = {p.name for p in files}
    assert names == {"__init__.py", "errors.py", "models.py", "atomic.py", "artifacts.py", "mapping.py"}
    assert not names & {"executor.py", "move.py", "orchestrator.py", "planner.py"}
    for path in files:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import | ast.ImportFrom):
                mods = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""]
                for m in mods:
                    assert not m.startswith(("httpx", "amane", "fc2_metadata_core", "fc2_organizer.images.transport",
                                             "fc2_organizer.images.acquisition", "fc2_organizer.nfo")), (path.name, m)
                    if m.startswith(("fc2_organizer.planning", "fc2_organizer.images")):
                        assert path.name == "mapping.py" and m in {"fc2_organizer.planning", "fc2_organizer.images"}
        for lineno, name in _calls(tree):
            assert name not in {"mkdir", "makedirs", "replace", "materialize_all", "execute_plan",
                                "apply_operations", "transaction", "rollback_all"}, (path.name, lineno, name)
            if name in {"rename", "link"}:  # the frozen no-replace publish only
                assert path.name == "atomic.py", (path.name, lineno)
    for absent in ("materialize_all", "execute_plan", "apply_operations", "transaction", "rollback_all"):
        assert not hasattr(materialization_pkg, absent)


# --------------------------------------------------------------------------- direct reproductions A-H


def test_repro_A_new_nfo_exact_utf8_bytes(tmp_path):
    case = CASES[2]  # Unicode title
    plan = _plan(case, str(tmp_path / "lib"))
    _prepare_dirs(plan)
    (req,) = build_artifact_requests(plan, case.nfo_text, _images(case))
    materialize_artifact(req)
    assert _read(req.target_path) == case.nfo_text.encode("utf-8")


def test_repro_B_existing_target_unchanged(tmp_path):
    case = CASES[0]
    plan = _plan(case, str(tmp_path / "lib"))
    _prepare_dirs(plan)
    (req,) = build_artifact_requests(plan, case.nfo_text, _images(case))
    with open(req.target_path, "wb") as fh:
        fh.write(b"USER NFO")
    with pytest.raises(TargetExistsError):
        materialize_artifact(req)
    assert _read(req.target_path) == b"USER NFO"


def test_repro_C_two_writers_exactly_one_success(tmp_path, monkeypatch):
    target = str(tmp_path / "thumb.jpg")
    reqs = [ArtifactWriteRequest(ArtifactKind.THUMB, target, b"A" * 70_000),
            ArtifactWriteRequest(ArtifactKind.THUMB, target, b"B" * 90_000)]
    outcomes = _race(reqs, True, monkeypatch)
    ok = [req for req, res in outcomes if res[0] == "ok"]
    assert len(ok) == 1 and _read(target) == ok[0].content
    assert [type(res[1]) for _, res in outcomes if res[0] == "err"] == [TargetExistsError]


def test_repro_D_write_failure_no_final_owned_temp_removed(tmp_path, monkeypatch):
    created = []
    real_open = atomic._FS.open
    inject(monkeypatch, open=lambda p, f, m: (created.append(p), real_open(p, f, m))[1],
           write=failing(OSError(errno.ENOSPC, "full")))
    req = ArtifactWriteRequest(ArtifactKind.NFO, str(tmp_path / "FC2-1.nfo"), b"<movie/>")
    with pytest.raises(ArtifactWriteError):
        materialize_artifact(req)
    assert not os.path.exists(req.target_path) and len(created) == 1 and not os.path.exists(created[0])


def test_repro_E_planted_unrelated_temp_remains(tmp_path, monkeypatch):
    planted = _plant(str(tmp_path))
    inject(monkeypatch, publish=failing(OSError(errno.EIO, "io")))
    with pytest.raises(ArtifactPublishError):
        materialize_artifact(ArtifactWriteRequest(ArtifactKind.FANART, str(tmp_path / "fanart.jpg"), b"f"))
    assert set(os.listdir(tmp_path)) == set(planted)


def test_repro_F_nfo_success_then_poster_failure_nfo_remains(tmp_path):
    test_gate_partial_success_is_never_rolled_back(tmp_path)


def test_repro_G_1000_extrafanart_last_name(tmp_path):
    case = Case(0, "FC2-7654321", CASES[0].nfo_text, {}, (_jpeg("same"),) * 1000)
    requests = build_artifact_requests(_plan(case, str(tmp_path / "lib")), case.nfo_text, _images(case))
    assert len(requests) == 1001 and os.path.basename(requests[-1].target_path) == "extrafanart-1000.jpg"


def test_repro_H_missing_extrafanart_directory_not_created(tmp_path, monkeypatch):
    case = CASES[200]
    plan = _plan(case, str(tmp_path / "lib"))
    os.makedirs(plan.target_directory.absolute_path)  # film dir exists, extrafanart/ does not
    for name in ("mkdir", "makedirs"):
        monkeypatch.setattr(os, name, lambda *a, **k: pytest.fail("directory creation attempted"))
    req = next(r for r in build_artifact_requests(plan, case.nfo_text, _images(case))
               if r.kind is ArtifactKind.EXTRAFANART)
    with pytest.raises(ParentDirectoryMissingError):
        materialize_artifact(req)
    assert not os.path.exists(plan.extrafanart_directory.absolute_path)
    assert os.listdir(plan.target_directory.absolute_path) == []
