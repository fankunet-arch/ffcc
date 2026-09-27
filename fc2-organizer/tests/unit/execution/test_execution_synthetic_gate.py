"""P4-C7 S6: 500-item integrated filesystem gate (contract section 31.1; construction plan S6).

The gate executes a FROZEN table of 500 deterministic synthetic films against the real executor
(``preflight_execution`` + ``execute_filesystem``) below pytest's temporary directory:

* 200 same-volume cases with the host's native strategy (Windows ``rename`` / POSIX ``link``);
* 100 cases with the POSIX hard-link strategies (media + artifacts) selected through the frozen strategy seams;
* 150 cases forced to ``CROSS_VOLUME`` through the frozen ``_FS.device_of`` seam (mocked, never native
  cross-volume evidence);
* 50 fault / resume cases: every ``ExecutionFailureKind`` is injected at least once through the frozen seams
  (``execution._fs._FS``, ``materialization.atomic._FS``, the executor's ``materialize_artifact`` binding and the
  directory-fsync seam) and every resume point ``0 < p < |E|`` of both fault manifests is hit; each failure checks
  the core invariant, then the RETURNED checkpoint is resumed (never a new fresh plan) until ``SUCCESS``.

Every expected value comes from the case definition and static rules below (default v1.0 layout names, the
frozen extrafanart name format, media bytes generated from the case index) -- never from a production result.
Conflict pairs (duplicate number = same target) run in the same corpus; unrelated user / temp-looking files are
planted in every source directory and library root (and, for 1 in 5 success cases, inside the owned target and
extrafanart directories while they execute) and must be byte / inode / mtime identical after every case. The
whole corpus runs twice in two separate roots; everything but ids, seals, tokens and leftover-name tokens must be
equal (determinism). A separate film really materializes 1000 extrafanart images.

No sleeps, no probabilistic scheduling: the only threaded pair asserts an order-independent outcome.
"""

from __future__ import annotations

import ast
import dataclasses
import errno
import hashlib
import os
import re
import stat
import threading
import unicodedata
from pathlib import Path

import pytest

from fc2_organizer.execution import (
    EffectKind,
    ExecutionFailureKind,
    ExecutionStatus,
    ExecutionStep,
    PathRole,
    PreflightMode,
    TransferMode,
    execute_filesystem,
    preflight_execution,
)
from fc2_organizer.execution import _fs, executor, transfer
from fc2_organizer.execution import seal as seal_module
from fc2_organizer.execution.seal import is_consumed
from fc2_organizer.images import ImageAcquisitionResult, ImageRole
from fc2_organizer.materialization import (
    ArtifactKind,
    InvalidTargetPathError,
    MaterializedArtifact,
    ParentDirectoryMissingError,
    TargetExistsError,
)
from fc2_organizer.materialization import atomic as p4c6_atomic
from fc2_organizer.materialization.errors import TargetPathRejectionReason
from fc2_organizer.materialization.mapping import build_artifact_requests

from ._builders import MAIN_COMBOS, image, jpeg, make_plan
from ._helpers import (
    FakeDirectoryFsync,
    assert_source_not_lost,
    inject,
    inject_p4c6,
    use_strategy,
    use_transfer,
    with_stat_fields,
)

F = ExecutionFailureKind
MIB = 1 << 20

# =========================================================================== frozen case definition

TOTAL_CASES = 500
GROUP_SIZES = {"native": 200, "hardlink": 100, "cross_volume": 150, "fault": 50}
BOUNDARY_SIZES = (0, 1, MIB - 1, MIB, MIB + 1, 3 * MIB + 17)
LIBRARIES = ("library", "库-ライブラリ-😀", "bibliothèque-nfd")
SOURCE_DIRS = ("downloads", "下载-かな", "émoji-😀-nfc", "nfd-été")
STEMS = ("random-name", "動画-かな", "vidéo-nfc", "vidéo-nfd", "clip-😀", "combining-ä")
EXTENSIONS = (".mp4", ".MP4", ".Mp4", ".mkv", ".MKV", ".avi", ".wmv", ".mOv")

# Static v1.0 layout rules (P4-C2 default OutputPolicy names; contract section 7.3 extrafanart format). They are
# written out here on purpose -- the expected layout never comes from the plan or from an execution result.
POSTER_NAME, FANART_NAME, THUMB_NAME, EXTRAFANART_DIRNAME = "poster.jpg", "fanart.jpg", "thumb.jpg", "extrafanart"


def extrafanart_name(k: int) -> str:
    return "extrafanart-%03d.jpg" % k


# Unrelated files planted before the corpus runs (every source directory and library root) and, for success
# cases with ``plant_in_target``, inside the owned directories right after their creation.
GLOBAL_PLANTS = (".fc2tmp-" + "c" * 32 + ".part", "unrelated.part", "unrelated.tmp", "user-file.txt")
TARGET_PLANTS = (".fc2tmp-" + "d" * 32 + ".part", "user-extra.part", "user-extra.tmp")
USER_MOVIE_DIR, USER_MOVIE_FILE = "FC2-0000001-user", "keep.mp4"
TEMP_NAME = re.compile(r"^\.fc2tmp-[0-9a-f]{32}\.part$")


def _temp_like(name: str) -> bool:
    return name.startswith(".fc2tmp-") or name.endswith(".part") or name.endswith(".tmp")


@dataclasses.dataclass(frozen=True)
class Fault:
    """One fault / resume case: the injector ``name`` blocks effect index ``at`` of E; the first result is
    ``PARTIAL(kind)`` with exactly ``p`` completed effects; ``then`` injects further faults into RESUME executions
    (each ``PARTIAL`` with zero new effects) before the final clean resume."""

    name: str
    kind: ExecutionFailureKind
    at: int
    p: int
    leftovers: tuple[str, ...] = ()
    then: tuple[tuple[str, ExecutionFailureKind], ...] = ()
    resolve_planted: bool = False
    size: int | None = None


@dataclasses.dataclass(frozen=True)
class Case:
    index: int
    group: str
    transfer: str
    number: str
    library: str
    source_dir: str
    source_name: str
    ext: str
    size: int
    poster: bool
    fanart: bool
    thumb: bool
    extra: int
    plant_in_target: bool
    shape: str | None = None
    fault: Fault | None = None

    @property
    def cid(self) -> str:
        return "%03d-%s" % (self.index, self.group)


FAULT_SHAPES = {"full_13": dict(poster=True, fanart=True, thumb=True, extra=13),
                "nfo_only": dict(poster=False, fanart=False, thumb=False, extra=0)}
# |E| = TD + MEDIA + SOURCE_REMOVED + NFO + (#main images) + EXTRAFANART_DIR + #extrafanart
FAULT_E_LENGTH = {"full_13": 21, "nfo_only": 5}
_NT = os.name == "nt"

# (shape, transfer group, Fault). ``at`` / ``p`` index the static E of the shape:
#   full_13 : 0 TD, 1 MEDIA, 2 SOURCE_REMOVED, 3 NFO, 4 POSTER, 5 FANART, 6 THUMB, 7 EXTRAFANART_DIR, 8..20 X1..X13
#   nfo_only: 0 TD, 1 MEDIA, 2 SOURCE_REMOVED, 3 NFO, 4 EXTRAFANART_DIR
FAULT_TABLE: tuple[tuple[str, str, Fault], ...] = (
    ("full_13", "native", Fault("same_volume_primitive_eperm", F.MEDIA_TRANSFER_FAILED, 1, 1)),
    ("full_13", "native", Fault("planted_final", F.TARGET_CONFLICT, 1, 1, resolve_planted=True)),
    ("full_13", "native", Fault("source_changed_u2", F.SOURCE_CHANGED, 1, 1)),
    ("full_13", "hardlink", Fault("source_missing_u2", F.SOURCE_MISSING, 1, 1)),
    ("full_13", "cross_volume", Fault("target_dir_changed_u2", F.TARGET_DIRECTORY_CHANGED, 1, 1)),
    ("full_13", "cross_volume", Fault("source_open_fail", F.MEDIA_SOURCE_OPEN_FAILED, 1, 1)),
    ("full_13", "cross_volume", Fault("read_fail_second_block", F.MEDIA_READ_FAILED, 1, 1, size=MIB + 1)),
    ("full_13", "cross_volume", Fault("temp_create_fail", F.MEDIA_TEMP_CREATE_FAILED, 1, 1)),
    ("full_13", "cross_volume", Fault("write_fail", F.MEDIA_WRITE_FAILED, 1, 1)),
    ("full_13", "cross_volume", Fault("fsync_fail", F.MEDIA_FSYNC_FAILED, 1, 1)),
    ("full_13", "cross_volume", Fault("close_fail", F.MEDIA_CLOSE_FAILED, 1, 1)),
    ("full_13", "cross_volume", Fault("source_fd_changed", F.SOURCE_CHANGED_DURING_COPY, 1, 1)),
    ("full_13", "cross_volume", Fault("publish_fail", F.MEDIA_PUBLISH_FAILED, 1, 1)),
    ("full_13", "hardlink", Fault("source_unlink_fail", F.SOURCE_UNLINK_FAILED, 2, 2)),
    ("full_13", "hardlink", Fault("dir_fsync_fail", F.TARGET_DIRECTORY_FSYNC_FAILED, 2, 2)),
    ("full_13", "cross_volume", Fault("temp_cleanup_fail", F.MEDIA_TEMP_CLEANUP_FAILED, 2, 2,
                                      leftovers=("target_directory",))),
    ("full_13", "hardlink", Fault("published_media_mismatch", F.PUBLISHED_MEDIA_MISMATCH, 2, 2)),
    ("full_13", "cross_volume", Fault("source_changed_before_unlink", F.SOURCE_CHANGED, 2, 2)),
    ("full_13", "native", Fault("p4c6_write_fail", F.ARTIFACT_WRITE_FAILED, 3, 3)),
    ("full_13", "native", Fault("p4c6_temp_create_fail", F.ARTIFACT_TEMP_CREATE_FAILED, 4, 4)),
    ("full_13", "native", Fault("p4c6_publish_fail", F.ARTIFACT_PUBLISH_FAILED, 5, 5)),
    ("full_13", "hardlink", Fault("artifact_target_inaccessible", F.ARTIFACT_TARGET_INACCESSIBLE, 6, 6)),
    ("full_13", "native", Fault("u7_mkdir_eacces", F.DIRECTORY_CREATE_FAILED, 7, 7)),
    ("full_13", "native", Fault("p4c6_cleanup_unpublished", F.ARTIFACT_CLEANUP_FAILED, 8, 8,
                                leftovers=("extrafanart_directory",))),
    ("full_13", "cross_volume", Fault("forged_receipt", F.PUBLISHED_ARTIFACT_MISMATCH, 9, 9)),
    ("full_13", "native", Fault("path_rejected", F.ARTIFACT_PATH_REJECTED, 10, 10)),
    ("full_13", "cross_volume", Fault("artifact_parent_changed", F.TARGET_DIRECTORY_CHANGED, 11, 11)),
    ("full_13", "hardlink", Fault("p4c6_cleanup_published", F.ARTIFACT_CLEANUP_FAILED, 11, 12,
                                  leftovers=("extrafanart_directory",))),
    ("full_13", "native", Fault("target_exists_error", F.TARGET_CONFLICT, 13, 13)),
    ("full_13", "hardlink", Fault("p4c6_fsync_fail", F.ARTIFACT_WRITE_FAILED, 14, 14)),
    ("full_13", "cross_volume", Fault("p4c6_close_fail", F.ARTIFACT_WRITE_FAILED, 15, 15)),
    ("full_13", "cross_volume", Fault("p4c6_temp_create_fail", F.ARTIFACT_TEMP_CREATE_FAILED, 16, 16)),
    ("full_13", "hardlink", Fault("p4c6_publish_fail", F.ARTIFACT_PUBLISH_FAILED, 17, 17)),
    ("full_13", "native", Fault("artifact_target_inaccessible", F.ARTIFACT_TARGET_INACCESSIBLE, 18, 18)),
    ("full_13", "native", Fault("parent_directory_error", F.TARGET_DIRECTORY_CHANGED, 19, 19)),
    ("full_13", "native", Fault("p4c6_write_fail", F.ARTIFACT_WRITE_FAILED, 20, 20)),
    ("nfo_only", "hardlink", Fault("hardlink_unsupported", F.MEDIA_TRANSFER_FAILED, 1, 1)),
    ("nfo_only", "cross_volume", Fault("source_unlink_fail", F.SOURCE_UNLINK_FAILED, 2, 2)),
    ("nfo_only", "native", Fault("p4c6_write_fail", F.ARTIFACT_WRITE_FAILED, 3, 3)),
    ("nfo_only", "native", Fault("u7_mkdir_exists", F.TARGET_CONFLICT, 4, 4)),
    ("full_13", "native", Fault("p4c6_write_fail", F.ARTIFACT_WRITE_FAILED, 3, 3,
                                then=(("resume_library_root_changed", F.LIBRARY_ROOT_CHANGED),))),
    ("nfo_only", "hardlink", Fault("p4c6_write_fail", F.ARTIFACT_WRITE_FAILED, 3, 3,
                                   then=(("resume_unexpected_entry", F.UNEXPECTED_ENTRY),))),
    ("full_13", "native", Fault("same_volume_primitive_eperm", F.MEDIA_TRANSFER_FAILED, 1, 1,
                                then=(("resume_source_missing", F.SOURCE_MISSING),))),
    ("full_13", "cross_volume", Fault("p4c6_write_fail", F.ARTIFACT_WRITE_FAILED, 8, 8,
                                      then=(("resume_target_changed", F.TARGET_DIRECTORY_CHANGED),))),
    ("full_13", "hardlink", Fault("source_missing_before_unlink", F.SOURCE_MISSING, 2, 2)),
    # Host-native strategy: the atomic Windows rename records MEDIA_PUBLISHED + SOURCE_REMOVED before its
    # post-publish verification fails (p = 3); the POSIX link keeps the source (p = 2). Contract 18.2 / 18.3.
    ("nfo_only", "native", Fault("published_media_mismatch", F.PUBLISHED_MEDIA_MISMATCH, 1, 3 if _NT else 2)),
    ("nfo_only", "cross_volume", Fault("dir_fsync_fail", F.TARGET_DIRECTORY_FSYNC_FAILED, 2, 2)),
    ("nfo_only", "cross_volume", Fault("planted_final", F.TARGET_CONFLICT, 1, 1, resolve_planted=True)),
    ("nfo_only", "cross_volume", Fault("source_grows_during_copy", F.SOURCE_CHANGED_DURING_COPY, 1, 1)),
    ("nfo_only", "hardlink", Fault("u7_mkdir_eacces", F.DIRECTORY_CREATE_FAILED, 4, 4)),
)

# Contract section 27 kinds that cannot be injected through a frozen test seam. Empty: every kind is produced
# below -- ARTIFACT_PATH_REJECTED ("impossible, manifest validated", contract section 24) only through the
# executor's materialize_artifact binding, the same seam S4 used for its mapping-table rows.
NON_INJECTABLE: dict[ExecutionFailureKind, str] = {}


def _small_size(index: int) -> int:
    return 2 + (index * 7919) % 5000


def build_cases() -> tuple[Case, ...]:
    cases: list[Case] = []
    index = 0
    for group in ("native", "hardlink", "cross_volume"):
        for j in range(GROUP_SIZES[group]):
            poster, fanart, thumb = MAIN_COMBOS[j % 8]
            size = BOUNDARY_SIZES[j] if j < len(BOUNDARY_SIZES) else _small_size(index)
            cases.append(_case(index, group, group, size, poster, fanart, thumb, (j // 8) % 14, j % 5 == 0))
            index += 1
    for shape, transfer_group, fault in FAULT_TABLE:
        options = FAULT_SHAPES[shape]
        size = fault.size if fault.size is not None else 257 + index % 97
        cases.append(dataclasses.replace(
            _case(index, "fault", transfer_group, size, options["poster"], options["fanart"], options["thumb"],
                  options["extra"], False), shape=shape, fault=fault))
        index += 1
    return tuple(cases)


def _case(index, group, transfer_group, size, poster, fanart, thumb, extra, plant) -> Case:
    ext = EXTENSIONS[index % len(EXTENSIONS)]
    return Case(index=index, group=group, transfer=transfer_group, number="FC2-%d" % (4000000 + index),
                library=LIBRARIES[index % len(LIBRARIES)], source_dir=SOURCE_DIRS[index % len(SOURCE_DIRS)],
                source_name="%s-%03d%s" % (STEMS[index % len(STEMS)], index, ext), ext=ext, size=size,
                poster=poster, fanart=fanart, thumb=thumb, extra=extra, plant_in_target=plant)


CASES = build_cases()

# --------------------------------------------------------------------------- content from the definition


def media_bytes(tag: str, size: int) -> bytes:
    """Deterministic media content of ``size`` bytes: distinct per case and per 32-byte block."""
    seed = hashlib.sha256(("p4-c7-s6-media/" + tag).encode()).digest()
    blocks = (size + 31) // 32
    return b"".join(hashlib.sha256(seed + i.to_bytes(8, "big")).digest() for i in range(blocks))[:size]


def nfo_text(tag: str, number: str) -> str:
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            "<movie>\n  <title>S6 %s 合成 %s</title>\n</movie>\n" % (number, tag))


def main_image_bytes(tag: str, role: str) -> bytes:
    return jpeg(("%s-%s" % (role, tag)).encode())


def extra_image_bytes(tag: str, k: int) -> bytes:
    return jpeg(("extra-%s-%d" % (tag, k)).encode())


def build_manifest(plan, tag: str, number: str, poster: bool, fanart: bool, thumb: bool, extra: int) -> tuple:
    images = ImageAcquisitionResult(
        poster=image(ImageRole.POSTER, main_image_bytes(tag, "poster")) if poster else None,
        fanart=image(ImageRole.FANART, main_image_bytes(tag, "fanart")) if fanart else None,
        thumb=image(ImageRole.THUMB, main_image_bytes(tag, "thumb")) if thumb else None,
        extrafanart=tuple(image(ImageRole.EXTRAFANART, extra_image_bytes(tag, k), k - 1)
                          for k in range(1, extra + 1)),
    )
    return build_artifact_requests(plan, nfo_text(tag, number), images)


@dataclasses.dataclass(frozen=True)
class Film:
    """Static expectation of one film, derived only from its definition (never from production output)."""

    tag: str
    number: str
    library_root: str
    source: str
    ext: str
    media: bytes
    poster: bool
    fanart: bool
    thumb: bool
    extra: int

    @property
    def target_dir(self) -> str:
        return os.path.join(self.library_root, self.number)

    @property
    def final(self) -> str:
        return os.path.join(self.target_dir, self.number + self.ext.lower())

    @property
    def efd(self) -> str:
        return os.path.join(self.target_dir, EXTRAFANART_DIRNAME)

    def artifact_files(self) -> list[tuple[str, str, int | None, bytes]]:
        """(artifact kind value, absolute path, ordinal, bytes) in E order."""
        files = [("nfo", os.path.join(self.target_dir, self.number + ".nfo"), None,
                  nfo_text(self.tag, self.number).encode("utf-8"))]
        for present, kind, name in ((self.poster, "poster", POSTER_NAME), (self.fanart, "fanart", FANART_NAME),
                                    (self.thumb, "thumb", THUMB_NAME)):
            if present:
                files.append((kind, os.path.join(self.target_dir, name), None, main_image_bytes(self.tag, kind)))
        for k in range(1, self.extra + 1):
            files.append(("extrafanart", os.path.join(self.efd, extrafanart_name(k)), k,
                          extra_image_bytes(self.tag, k)))
        return files

    def effects(self) -> list[tuple]:
        """Static E(plan, manifest): (effect kind value, path, artifact kind value, ordinal)."""
        files = self.artifact_files()
        main = [f for f in files if f[0] != "extrafanart"]
        extra = [f for f in files if f[0] == "extrafanart"]
        return ([("target_directory_created", self.target_dir, None, None),
                 ("media_published", self.final, None, None),
                 ("source_removed", self.source, None, None)]
                + [("artifact_published", path, kind, ordinal) for kind, path, ordinal, _ in main]
                + [("extrafanart_directory_created", self.efd, None, None)]
                + [("artifact_published", path, kind, ordinal) for kind, path, ordinal, _ in extra])

    def tree(self) -> dict[str, bytes | None]:
        """Exact final entries below the target directory (relative path -> bytes, ``None`` for a directory)."""
        tree: dict[str, bytes | None] = {self.number + self.ext.lower(): self.media, EXTRAFANART_DIRNAME: None}
        for _, path, _, content in self.artifact_files():
            tree[os.path.relpath(path, self.target_dir)] = content
        return tree


def film_of(case: Case, root: Path) -> Film:
    return Film(tag=case.cid, number=case.number, library_root=str(root / case.library),
                source=str(root / case.source_dir / case.source_name), ext=case.ext,
                media=media_bytes(case.cid, case.size), poster=case.poster, fanart=case.fanart, thumb=case.thumb,
                extra=case.extra)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def entry_state(path: str) -> tuple:
    """(bytes, inode, mtime_ns) of a planted file (or ``None`` when it is missing / not a regular file)."""
    try:
        st = os.lstat(path)
    except FileNotFoundError:
        return (None,)
    if not stat.S_ISREG(st.st_mode):
        return ("<not a regular file>",)
    with open(path, "rb") as handle:
        return handle.read(), st.st_ino, st.st_mtime_ns


def read_tree(directory: str) -> dict[str, bytes | None]:
    tree: dict[str, bytes | None] = {}
    for dirpath, dirnames, filenames in os.walk(directory):
        for name in dirnames:
            tree[os.path.relpath(os.path.join(dirpath, name), directory)] = None
        for name in filenames:
            with open(os.path.join(dirpath, name), "rb") as handle:
                tree[os.path.relpath(os.path.join(dirpath, name), directory)] = handle.read()
    return tree


def claim_state(identity):
    return seal_module._claim_state_for_tests(identity)


# =========================================================================== scoped one-shot fault injection


class Injector:
    """Tracks which executor unit is running (U1 / U2 / U7 / one artifact) and lets a fault fire exactly once,
    only inside its unit, through the frozen seams. ``fired`` proves the injection really happened."""

    def __init__(self, mp: pytest.MonkeyPatch, film: Film, artifacts: tuple) -> None:
        self.mp, self.film, self.artifacts = mp, film, artifacts
        self.scope: object = None
        self.done: set[str] = set()
        self.counts: dict[str, int] = {}
        self.planted: tuple | None = None
        self.log: list[tuple[str, object]] = []
        self.fake: FakeDirectoryFsync | None = None
        for name, tag in (("create_target_directory", "u1"), ("transfer_media", "u2"),
                          ("create_extrafanart_directory", "u7")):
            self._scoped(name, lambda *_a, _tag=tag, **_k: _tag)
        self._scoped("_execute_artifact_unit", lambda request, *_a, **_k: ("artifact", request.kind, request.ordinal))

    def _scoped(self, name: str, tagger) -> None:
        real = getattr(executor, name)

        def wrapped(*args, **kwargs):
            previous = self.scope
            self.scope = tagger(*args, **kwargs)
            try:
                return real(*args, **kwargs)
            finally:
                self.scope = previous

        self.mp.setattr(executor, name, wrapped)

    def fired(self) -> bool:
        return bool(self.done) or (self.fake is not None and "fsync" in self.fake.events)

    def once(self, key: str) -> bool:
        if key in self.done:
            return False
        self.done.add(key)
        return True

    def count(self, key: str) -> int:
        self.counts[key] = self.counts.get(key, 0) + 1
        return self.counts[key]

    def seam(self, op: str, handler) -> None:
        real = getattr(_fs._FS, op)
        inject(self.mp, **{op: lambda *args: handler(real, *args)})

    def p4c6(self, op: str, handler) -> None:
        real = getattr(p4c6_atomic._FS, op)
        inject_p4c6(self.mp, **{op: lambda *args: handler(real, *args)})

    def materialize(self, handler) -> None:
        real = executor.materialize_artifact
        self.mp.setattr(executor, "materialize_artifact", lambda request: handler(real, request))

    def artifact_scope(self, at: int) -> tuple:
        kind, path, ordinal = self.film.effects()[at][2], self.film.effects()[at][1], self.film.effects()[at][3]
        assert kind is not None, "fault index does not name an artifact effect"
        return ("artifact", ArtifactKind(kind), ordinal)

    def artifact_path(self, at: int) -> str:
        return self.film.effects()[at][1]


def _raise_once(inj: Injector, op: str, where, error: OSError, key: str | None = None) -> None:
    def handler(real, *args):
        if where(*args) and inj.once(key or op):
            raise error
        return real(*args)
    inj.seam(op, handler)


def _stat_once(inj: Injector, where, **overrides) -> None:
    """The first ``lstat`` matching ``where`` that SUCCEEDS returns a rewritten identity (transient observation)."""
    def handler(real, path):
        st = real(path)
        if where(path) and inj.once("lstat-rewrite"):
            return with_stat_fields(st, **overrides)
        return st
    inj.seam("lstat", handler)


def _u2(inj: Injector) -> bool:
    return inj.scope == "u2"


def _is_temp(path) -> bool:
    return type(path) is str and os.path.basename(path).startswith(".fc2tmp-")


def _eperm() -> OSError:
    return PermissionError(errno.EPERM, "injected")


def _eacces() -> OSError:
    return PermissionError(errno.EACCES, "injected")


def _plant_final(inj: Injector, fault: Fault) -> None:
    """A REAL entry appears at the final media path right after U2's early absence probe; only the
    no-replace primitive can refuse it (contract section 18.1 / 23)."""
    final = inj.film.final

    def handler(real, path):
        if _u2(inj) and path == final and inj.planted is None:
            try:
                return real(path)
            except FileNotFoundError:
                if inj.once("plant"):
                    with open(final, "wb") as handle:
                        handle.write(b"planted by another writer " + inj.film.tag.encode())
                    inj.planted = entry_state(final)
                raise
        return real(path)
    inj.seam("lstat", handler)


def _fd_of_source(inj: Injector) -> None:
    real_open = _fs._FS.open

    def open_(path, flags, *rest):
        fd = real_open(path, flags, *rest)
        if _u2(inj) and path == inj.film.source:
            inj.source_fd = fd
        return fd
    inj.source_fd = None
    inject(inj.mp, open=open_)


def _install_first(inj: Injector, fault: Fault) -> None:  # noqa: C901 -- one frozen table, one dispatcher
    film, name = inj.film, fault.name
    source, final, target_dir, efd = film.source, film.final, film.target_dir, film.efd
    if name == "same_volume_primitive_eperm":
        for op in ("rename", "link"):
            _raise_once(inj, op, lambda a, *_: _u2(inj) and a == source, _eperm(), "primitive")
    elif name == "planted_final":
        _plant_final(inj, fault)
    elif name == "source_changed_u2":
        _stat_once(inj, lambda p: _u2(inj) and p == source, st_mtime_ns=1)
    elif name == "source_missing_u2":
        _raise_once(inj, "lstat", lambda p: _u2(inj) and p == source, FileNotFoundError(errno.ENOENT, "x"))
    elif name == "target_dir_changed_u2":
        _stat_once(inj, lambda p: _u2(inj) and p == target_dir, st_ino=987654321)
    elif name == "source_open_fail":
        _raise_once(inj, "open", lambda p, *_: _u2(inj) and p == source, _eacces())
    elif name == "read_fail_second_block":
        def read(real, fd, n):
            if _u2(inj) and inj.count("read") == 2 and inj.once("read"):
                raise OSError(errno.EIO, "injected")
            return real(fd, n)
        inj.seam("read", read)
    elif name == "temp_create_fail":
        _raise_once(inj, "open", lambda p, flags, *_: _u2(inj) and bool(flags & os.O_CREAT), _eacces())
    elif name == "write_fail":
        _raise_once(inj, "write", lambda *_: _u2(inj), OSError(errno.ENOSPC, "injected"))
    elif name == "fsync_fail":
        _raise_once(inj, "fsync", lambda *_: _u2(inj), OSError(errno.EIO, "injected"))
    elif name == "close_fail":
        def close(real, fd):
            real(fd)  # the descriptor IS released; only the report fails (POSIX close semantics)
            if _u2(inj) and inj.once("close"):
                raise OSError(errno.EIO, "injected")
        inj.seam("close", close)
    elif name == "source_fd_changed":
        _fd_of_source(inj)

        def fstat(real, fd):
            st = real(fd)
            if _u2(inj) and fd == inj.source_fd and inj.count("fstat-source") == 2 and inj.once("fstat"):
                return with_stat_fields(st, st_mtime_ns=st.st_mtime_ns + 1)
            return st
        inj.seam("fstat", fstat)
    elif name == "source_grows_during_copy":
        def read(real, fd, n):
            chunk = real(fd, n)
            if _u2(inj) and chunk and inj.once("grow"):
                return chunk + b"appended during copy"
            return chunk
        inj.seam("read", read)
    elif name == "publish_fail":
        for op in ("rename", "link"):
            _raise_once(inj, op, lambda a, *_: _u2(inj) and _is_temp(a), _eacces(), "publish")
    elif name == "source_unlink_fail":
        _raise_once(inj, "unlink", lambda p: _u2(inj) and p == source, _eacces())
    elif name == "dir_fsync_fail":  # POSIX directory-fsync path through the frozen seam, failing
        inj.fake = FakeDirectoryFsync(inj.mp, target_dir, fsync_error=OSError(errno.EIO, "injected"))
    elif name == "temp_cleanup_fail":
        use_strategy(inj.mp, "link")  # POSIX publish: link(temp, final) then unlink(temp)
        _raise_once(inj, "unlink", lambda p: _u2(inj) and _is_temp(p), _eacces())
    elif name == "published_media_mismatch":
        _stat_once(inj, lambda p: _u2(inj) and p == final, st_ino=987654321)
    elif name == "source_changed_before_unlink":
        def lstat(real, path):
            st = real(path)
            if _u2(inj) and path == source and inj.count("lstat-source") == 2 and inj.once("lstat"):
                return with_stat_fields(st, st_mtime_ns=st.st_mtime_ns + 1)
            return st
        inj.seam("lstat", lstat)
    elif name == "source_missing_before_unlink":
        def lstat(real, path):
            if _u2(inj) and path == source and inj.count("lstat-source") == 2 and inj.once("lstat"):
                raise FileNotFoundError(errno.ENOENT, "injected")
            return real(path)
        inj.seam("lstat", lstat)
    elif name == "hardlink_unsupported":
        _raise_once(inj, "link", lambda a, *_: _u2(inj) and a == source, OSError(errno.EMLINK, "injected"))
        _record_rename(inj)
    elif name in ("u7_mkdir_eacces", "u7_mkdir_exists"):
        error = _eacces() if name == "u7_mkdir_eacces" else FileExistsError(errno.EEXIST, "injected")
        _raise_once(inj, "mkdir", lambda p, *_: inj.scope == "u7" and p == efd, error)
    else:
        _install_artifact_fault(inj, fault)


def _record_rename(inj: Injector) -> None:
    def rename(real, a, b):
        inj.log.append(("rename", a))
        return real(a, b)
    inj.seam("rename", rename)


def _install_artifact_fault(inj: Injector, fault: Fault) -> None:
    name, scope, path = fault.name, inj.artifact_scope(fault.at), inj.artifact_path(fault.at)
    here = lambda *_: inj.scope == scope  # noqa: E731
    if name == "p4c6_write_fail":
        _p4c6_raise(inj, "write", here, OSError(errno.ENOSPC, "injected"))
    elif name == "p4c6_fsync_fail":
        _p4c6_raise(inj, "fsync", here, OSError(errno.EIO, "injected"))
    elif name == "p4c6_close_fail":
        def close(real, fd):
            real(fd)
            if here() and inj.once("p4c6-close"):
                raise OSError(errno.EIO, "injected")
        inj.p4c6("close", close)
    elif name == "p4c6_temp_create_fail":
        _p4c6_raise(inj, "open", here, _eacces())
    elif name == "p4c6_publish_fail":
        _p4c6_raise(inj, "publish", here, _eacces())
    elif name == "p4c6_cleanup_unpublished":
        _p4c6_raise(inj, "write", here, OSError(errno.ENOSPC, "injected"))
        _p4c6_raise(inj, "unlink", here, _eacces(), key="p4c6-unlink")
    elif name == "p4c6_cleanup_published":  # the group installs the hard-link publish that leaves the temp
        _p4c6_raise(inj, "unlink", here, _eacces())
    elif name == "artifact_target_inaccessible":
        _raise_once(inj, "lstat", lambda p: here() and p == path, _eacces())
    elif name == "artifact_parent_changed":
        parent = inj.film.efd if scope[1] is ArtifactKind.EXTRAFANART else inj.film.target_dir
        _stat_once(inj, lambda p: here() and p == parent, st_ino=987654321)
    elif name in ("forged_receipt", "path_rejected", "target_exists_error", "parent_directory_error"):
        def materialize(real, request):
            if here() and inj.once("materialize"):
                if name == "forged_receipt":  # an inconsistent receipt, nothing written
                    return MaterializedArtifact(request.target_path, len(request.content) + 1, "0" * 64)
                if name == "path_rejected":
                    raise InvalidTargetPathError(TargetPathRejectionReason.NOT_ABSOLUTE)
                if name == "target_exists_error":
                    raise TargetExistsError()
                raise ParentDirectoryMissingError(errno.ENOENT)
            return real(request)
        inj.materialize(materialize)
    else:
        raise AssertionError("unknown fault " + name)


def _p4c6_raise(inj: Injector, op: str, here, error: OSError, key: str | None = None) -> None:
    def handler(real, *args):
        if here() and inj.once(key or "p4c6-" + op):
            raise error
        return real(*args)
    inj.p4c6(op, handler)


def _install_resume(inj: Injector, name: str) -> None:
    film = inj.film
    if name == "resume_library_root_changed":
        _stat_once(inj, lambda p: p == film.library_root, st_ino=987654321)
    elif name == "resume_unexpected_entry":
        def listdir(real, path):
            names = real(path)
            if path == film.target_dir and inj.once("listdir"):
                return list(names) + ["phantom-entry-planted-after-preflight"]
            return names
        inj.seam("listdir", listdir)
    elif name == "resume_source_missing":
        _raise_once(inj, "lstat", lambda p: p == film.source, FileNotFoundError(errno.ENOENT, "injected"))
    elif name == "resume_target_changed":
        _stat_once(inj, lambda p: p == film.target_dir, st_ino=987654321)
    else:
        raise AssertionError("unknown resume fault " + name)


# =========================================================================== corpus run


CONFLICT_PAIRS = (("mkdir_race", "native"), ("mkdir_race", "hardlink"), ("mkdir_race", "cross_volume"),
                  ("revalidate", "native"), ("revalidate", "hardlink"), ("revalidate", "cross_volume"),
                  ("threaded", "native"))


class CorpusRun:
    """One complete execution of the frozen corpus below ``root``; collects observations and violations."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.errors: list[str] = []
        self.obs: dict[str, object] = {}
        self.successes = 0
        self.kinds: set[ExecutionFailureKind] = set()
        self.points: set[tuple[str, int]] = set()
        self.conflicts: dict[str, dict] = {}
        self.planted: dict[str, tuple] = {}
        self.target_planted_checks = 0

    # ------------------------------------------------------------------ setup / global invariants

    def setup(self) -> None:
        for directory in LIBRARIES + SOURCE_DIRS:
            (self.root / directory).mkdir(parents=True)
            for name in GLOBAL_PLANTS:
                path = self.root / directory / name
                path.write_bytes(b"unrelated %s in %s" % (name.encode(), directory.encode()))
        for library in LIBRARIES:
            user = self.root / library / USER_MOVIE_DIR
            user.mkdir()
            (user / USER_MOVIE_FILE).write_bytes(b"a user's own movie, never ours")
        self.planted = self._planted_now()

    def _planted_paths(self) -> list[str]:
        paths = [str(self.root / d / n) for d in LIBRARIES + SOURCE_DIRS for n in GLOBAL_PLANTS]
        return paths + [str(self.root / lib / USER_MOVIE_DIR / USER_MOVIE_FILE) for lib in LIBRARIES]

    def _planted_now(self) -> dict[str, tuple]:
        return {path: entry_state(path) for path in self._planted_paths()}

    def assert_planted_unchanged(self) -> None:
        assert self._planted_now() == self.planted, "a pre-existing unrelated entry was modified"

    def rel(self, path: str) -> str:
        return os.path.relpath(path, self.root)

    # ------------------------------------------------------------------ one film

    def prepare(self, tag: str, number: str, library: str, source_dir: str, source_name: str, ext: str,
                media: bytes, poster: bool, fanart: bool, thumb: bool, extra: int):
        film = Film(tag=tag, number=number, library_root=str(self.root / library),
                    source=str(self.root / source_dir / source_name), ext=ext, media=media, poster=poster,
                    fanart=fanart, thumb=thumb, extra=extra)
        with open(film.source, "wb") as handle:
            handle.write(media)
        plan = make_plan(film.library_root, film.source, number=number, extension=ext, size=len(media))
        artifacts = build_manifest(plan, tag, number, poster, fanart, thumb, extra)
        # The manifest is test INPUT: it must carry exactly the definition's bytes and targets.
        assert [(r.kind.value, r.target_path, r.ordinal, r.content) for r in artifacts] == [
            (kind, path, ordinal, content) for kind, path, ordinal, content in film.artifact_files()]
        return film, plan, artifacts

    def run(self) -> None:
        self.setup()
        before_claims = seal_module._claim_keys_for_tests()
        try:
            for case in CASES:
                self._guarded(case.cid, self._run_case, case)
            for k, (kind, transfer_group) in enumerate(CONFLICT_PAIRS):
                self._guarded("pair-%d-%s-%s" % (k, kind, transfer_group), self._run_pair, k, kind,
                              transfer_group)
            self._guarded("final-planted", self.assert_planted_unchanged)
        finally:
            leaked = seal_module._claim_keys_for_tests() - before_claims
            if leaked:
                self.errors.append("claims left behind: %d" % len(leaked))
            seal_module._claim_discard_for_tests(leaked)

    def _guarded(self, label: str, fn, *args) -> None:
        try:
            fn(*args)
        except Exception as exc:  # noqa: BLE001 -- recorded per case; the gate test asserts none
            self.errors.append("%s: %s: %s" % (label, type(exc).__name__, exc))

    def _run_case(self, case: Case) -> None:
        film, plan, artifacts = self.prepare(case.cid, case.number, case.library, case.source_dir,
                                             case.source_name, case.ext, media_bytes(case.cid, case.size),
                                             case.poster, case.fanart, case.thumb, case.extra)
        assert film == film_of(case, self.root)
        with pytest.MonkeyPatch.context() as outer:
            use_transfer(outer, case.transfer)
            if case.fault is None:
                self._run_success(case, film, plan, artifacts)
            else:
                self._run_fault(case, film, plan, artifacts, outer)
        self.assert_planted_unchanged()

    def _run_success(self, case: Case, film: Film, plan, artifacts) -> None:
        preflight = preflight_execution(plan, artifacts)
        assert preflight.ready and preflight.mode is PreflightMode.FRESH
        planted: dict[str, tuple] = {}
        with pytest.MonkeyPatch.context() as mp:
            if case.plant_in_target:
                self._plant_into_owned_directories(mp, film, planted)
            result = execute_filesystem(preflight)
        assert result.new_effect_count == len(film.effects())
        statuses = [self._status(result)]
        self._verify_final(case, film, preflight, result, planted=planted, statuses=statuses)

    def _plant_into_owned_directories(self, mp, film: Film, planted: dict) -> None:
        for name, directory in (("create_target_directory", film.target_dir),
                                ("create_extrafanart_directory", film.efd)):
            real = getattr(executor, name)

            def created(*args, _real=real, _directory=directory):
                identity, failure = _real(*args)
                if failure is None:
                    for plant in TARGET_PLANTS:
                        path = os.path.join(_directory, plant)
                        with open(path, "wb") as handle:
                            handle.write(b"unrelated, planted mid-run: " + plant.encode())
                        planted[path] = entry_state(path)
                return identity, failure
            mp.setattr(executor, name, created)

    def _run_fault(self, case: Case, film: Film, plan, artifacts, outer) -> None:
        fault = case.fault
        preflight = preflight_execution(plan, artifacts)
        assert preflight.ready and preflight.mode is PreflightMode.FRESH
        source_sha = sha(film.media)
        E = film.effects()
        with pytest.MonkeyPatch.context() as mp:
            inj = Injector(mp, film, artifacts)
            _install_first(inj, fault)
            first = execute_filesystem(preflight)
        assert inj.fired(), "the fault was never injected (vacuous case)"
        if fault.name == "hardlink_unsupported":
            assert inj.log == []  # fail closed: never a rename fallback (contract section 18.3)
        statuses = [self._status(first)]
        self._assert_partial(film, preflight, first, fault.kind, fault.p, E, source_sha)
        self.points.add((case.shape, len(first.completed_effects)))
        if fault.resolve_planted:  # the other writer's entry is intact; the user then resolves the conflict
            assert inj.planted is not None and entry_state(film.final) == inj.planted
            os.unlink(film.final)
        previous = first
        for then_name, then_kind in fault.then:
            resumed = preflight_execution(plan, artifacts, previous.checkpoint)
            assert resumed.ready and resumed.mode is PreflightMode.RESUME
            with pytest.MonkeyPatch.context() as mp:
                inj = Injector(mp, film, artifacts)
                _install_resume(inj, then_name)
                result = execute_filesystem(resumed)
            assert inj.fired(), "the resume fault was never injected"
            statuses.append(self._status(result))
            self._assert_partial(film, preflight, result, then_kind, len(previous.completed_effects), E,
                                 source_sha)
            assert result.new_effect_count == 0 and result.completed_effects == previous.completed_effects
            assert result.checkpoint.checkpoint_id != previous.checkpoint.checkpoint_id
            assert is_consumed(previous.checkpoint.checkpoint_id)
            previous = result
        resumed = preflight_execution(plan, artifacts, previous.checkpoint)
        assert resumed.ready and resumed.mode is PreflightMode.RESUME
        final = execute_filesystem(resumed)
        statuses.append(self._status(final))
        assert final.mode is PreflightMode.RESUME
        assert final.completed_effects[:len(previous.completed_effects)] == previous.completed_effects
        assert final.new_effect_count == len(E) - len(previous.completed_effects)
        assert is_consumed(previous.checkpoint.checkpoint_id)
        self._verify_final(case, film, preflight, final, planted={}, statuses=statuses,
                           leftover_roles=fault.leftovers)

    def _assert_partial(self, film: Film, preflight, result, kind, p, E, source_sha) -> None:
        """Core invariant (contract section 31) after every injected failure."""
        assert result.status is ExecutionStatus.PARTIAL, (result.status, result.failure)
        assert result.failure is not None and result.failure.kind is kind, result.failure
        assert result.checkpoint is not None
        assert len(result.completed_effects) == p
        assert [(e.kind.value, e.path, e.artifact_kind.value if e.artifact_kind else None, e.ordinal)
                for e in result.completed_effects] == E[:p]
        assert result.checkpoint.completed_effects == result.completed_effects
        assert_source_not_lost(film.source, film.final, source_sha)
        self.assert_planted_unchanged()
        kinds = {e.kind for e in result.completed_effects}
        retained = EffectKind.MEDIA_PUBLISHED in kinds and EffectKind.SOURCE_REMOVED not in kinds
        expected_claim = ("reserved", result.checkpoint.checkpoint_id) if retained else None
        assert claim_state(preflight.source_identity) == expected_claim
        for leftover in result.leftover_temporaries:
            directory = film.target_dir if leftover.directory_role is PathRole.TARGET_DIRECTORY else film.efd
            assert TEMP_NAME.fullmatch(leftover.name) and os.path.isfile(os.path.join(directory, leftover.name))
        self.kinds.add(kind)

    def _status(self, result) -> tuple:
        failure = result.failure
        return (result.status.value, result.mode.value,
                None if failure is None else (failure.step.value, failure.kind.value,
                                              failure.stage.value if failure.stage else None,
                                              failure.write_stage, failure.target_published),
                len(result.completed_effects), result.new_effect_count,
                tuple(sorted(item.directory_role.value for item in result.leftover_temporaries)))

    def _verify_final(self, case: Case, film: Film, preflight, result, *, planted: dict, statuses: list,
                      leftover_roles: tuple[str, ...] = ()) -> None:
        E = film.effects()
        assert result.status is ExecutionStatus.SUCCESS and result.failure is None and result.checkpoint is None
        assert [(e.kind.value, e.path, e.artifact_kind.value if e.artifact_kind else None, e.ordinal)
                for e in result.completed_effects] == E
        expected_files = {path: content for _, path, _, content in film.artifact_files()}
        for effect in result.completed_effects:
            if effect.kind is EffectKind.ARTIFACT_PUBLISHED:
                assert effect.sha256 == sha(expected_files[effect.path])
                assert effect.size == len(expected_files[effect.path])
            elif effect.kind is EffectKind.MEDIA_PUBLISHED:
                assert effect.size == len(film.media)
        cross = case.transfer == "cross_volume"
        assert result.transfer_mode is (TransferMode.CROSS_VOLUME if cross else TransferMode.SAME_VOLUME)
        assert result.media_sha256 == (sha(film.media) if cross else None)
        media = next(e for e in result.completed_effects if e.kind is EffectKind.MEDIA_PUBLISHED)
        if not cross:  # rename keeps the file id, link adds a name to the same inode
            assert media.identity.inode == preflight.source_identity.inode
        # leftovers: exact count, directory role and name pattern (contract sections 14.2, 20)
        assert sorted(item.directory_role.value for item in result.leftover_temporaries) == sorted(leftover_roles)
        expected_tree = film.tree()
        leftover_keys = []
        for leftover in result.leftover_temporaries:
            assert TEMP_NAME.fullmatch(leftover.name)
            prefix = "" if leftover.directory_role is PathRole.TARGET_DIRECTORY else EXTRAFANART_DIRNAME
            leftover_keys.append(os.path.join(prefix, leftover.name))
        for path, state in planted.items():
            expected_tree[os.path.relpath(path, film.target_dir)] = state[0]
        actual = read_tree(film.target_dir)
        assert sorted(actual) == sorted(list(expected_tree) + leftover_keys), "final directory entries differ"
        for key, content in expected_tree.items():
            assert actual[key] == content, key
        # no temporary residue beyond the planted and the exactly-reported leftovers
        residue = sorted(k for k in actual if _temp_like(os.path.basename(k)))
        allowed = sorted([os.path.relpath(p, film.target_dir) for p in planted] + leftover_keys)
        assert residue == allowed
        for path, state in planted.items():
            assert entry_state(path) == state, "an unrelated entry planted in an owned directory changed"
        self.target_planted_checks += len(planted)
        # the source is gone, nothing temp-like was left next to it, and the claim was released
        assert not os.path.lexists(film.source)
        source_dir = os.path.dirname(film.source)
        assert sorted(n for n in os.listdir(source_dir) if _temp_like(n)) == sorted(
            n for n in GLOBAL_PLANTS if _temp_like(n))
        assert claim_state(preflight.source_identity) is None
        self.successes += 1
        layout = {}
        for key in actual:
            shown = key if key not in leftover_keys else os.path.join(os.path.dirname(key), "<leftover>")
            layout[shown] = "<dir>" if actual[key] is None else sha(actual[key])
        self.obs[case.cid] = {
            "statuses": statuses,
            "effects": [(e.kind.value, self.rel(e.path), e.artifact_kind.value if e.artifact_kind else None,
                         e.ordinal, e.size, e.sha256) for e in result.completed_effects],
            "layout": sorted(layout.items()),
            "transfer_mode": result.transfer_mode.value,
            "media_sha256": result.media_sha256,
        }

    # ------------------------------------------------------------------ conflict pairs (same target)

    def _run_pair(self, k: int, kind: str, transfer_group: str) -> None:
        number = "FC2-%d" % (4900000 + k)
        library, source_dir = LIBRARIES[k % len(LIBRARIES)], SOURCE_DIRS[k % len(SOURCE_DIRS)]
        films = []
        with pytest.MonkeyPatch.context() as outer:
            use_transfer(outer, transfer_group)
            for side, ext in (("a", ".mp4"), ("b", ".MP4")):
                tag = "pair-%d-%s" % (k, side)
                films.append(self.prepare(tag, number, library, source_dir, "dup-%d-%s%s" % (k, side, ext), ext,
                                          media_bytes(tag, 300 + k), True, True, True, 2))
            (film_a, plan_a, art_a), (film_b, plan_b, art_b) = films
            pf_a, pf_b = preflight_execution(plan_a, art_a), preflight_execution(plan_b, art_b)
            assert pf_a.ready and pf_b.ready  # both plans passed preflight before either executes
            b_source = entry_state(film_b.source)
            results = {}
            if kind == "mkdir_race":
                # B has passed its read-only revalidation and U1's absence probe; A completes entirely inside
                # the window just before B's exclusive mkdir (deterministic interleaving, no threads).
                real_mkdir = _fs._FS.mkdir
                armed = [True]

                def mkdir(path, *rest):
                    if armed[0] and path == film_b.target_dir:
                        armed[0] = False
                        results["a"] = execute_filesystem(pf_a)
                    return real_mkdir(path, *rest)

                with pytest.MonkeyPatch.context() as mp:
                    inject(mp, mkdir=mkdir)
                    results["b"] = execute_filesystem(pf_b)
                assert not armed[0]
            elif kind == "revalidate":
                results["a"] = execute_filesystem(pf_a)
                results["b"] = execute_filesystem(pf_b)
            else:
                barrier = threading.Barrier(2)

                def worker(side, pf):
                    barrier.wait()
                    results[side] = execute_filesystem(pf)

                threads = [threading.Thread(target=worker, args=("a", pf_a)),
                           threading.Thread(target=worker, args=("b", pf_b))]
                for thread in threads:
                    thread.start()
                for thread in threads:
                    thread.join()
        statuses = sorted(r.status.value for r in results.values())
        assert statuses == ["failed", "success"], statuses  # never two SUCCESS, never two finals
        winner = "a" if results["a"].status is ExecutionStatus.SUCCESS else "b"
        if kind != "threaded":
            assert winner == "a"
        loser = "b" if winner == "a" else "a"
        win_film, lose_film = (film_a, film_b) if winner == "a" else (film_b, film_a)
        win_pf, lose_pf = (pf_a, pf_b) if winner == "a" else (pf_b, pf_a)
        lost = results[loser]
        assert lost.failure.kind is F.TARGET_CONFLICT and lost.failure.step is ExecutionStep.CREATE_DIRECTORY
        assert lost.completed_effects == () and lost.checkpoint is None and lost.new_effect_count == 0
        # exactly one final media, holding the winner's bytes (no overwrite); the loser's source is untouched
        assert read_tree(win_film.target_dir) == win_film.tree()
        assert not os.path.lexists(win_film.source)
        if kind == "threaded":
            assert os.path.isfile(lose_film.source) and Path(lose_film.source).read_bytes() == lose_film.media
        else:
            assert entry_state(film_b.source) == b_source
        assert_source_not_lost(lose_film.source, lose_film.final, sha(lose_film.media))
        assert claim_state(win_pf.source_identity) is None and claim_state(lose_pf.source_identity) is None
        self.assert_planted_unchanged()
        self.conflicts["%d-%s-%s" % (k, kind, transfer_group)] = {
            "statuses": statuses, "loser": (lost.status.value, lost.failure.kind.value, lost.failure.step.value,
                                            len(lost.completed_effects)),
            "winner_layout": sorted((key, "<dir>" if v is None else sha(v))
                                    for key, v in read_tree(win_film.target_dir).items()
                                    if kind != "threaded"),
        }


@pytest.fixture(scope="module")
def corpus(tmp_path_factory):
    """The frozen corpus executed twice, in two separate roots below pytest's temporary directory."""
    runs = []
    for label in ("run1", "run2"):
        run = CorpusRun(tmp_path_factory.mktemp("s6-gate-" + label))
        run.run()
        runs.append(run)
    return runs


# =========================================================================== static definition gates


def _expected_points() -> set[tuple[str, int]]:
    return {(shape, p) for shape, length in FAULT_E_LENGTH.items() for p in range(1, length)}


def test_case_set_is_exactly_500_with_the_frozen_composition():
    assert len(CASES) == TOTAL_CASES == 500
    assert {group: sum(1 for c in CASES if c.group == group) for group in GROUP_SIZES} == GROUP_SIZES
    assert [c.index for c in CASES] == list(range(500))
    # 500 distinct films: distinct numbers (targets) and distinct sources -- never one case repeated
    assert len({c.number for c in CASES}) == 500
    assert len({(c.source_dir, c.source_name) for c in CASES}) == 500
    assert sum(1 for c in CASES if c.fault is not None) == len(FAULT_TABLE) == 50
    faults = [c for c in CASES if c.group == "fault"]
    assert {c.transfer for c in faults} == {"native", "hardlink", "cross_volume"}


def test_media_size_coverage_from_the_definition():
    for group in ("native", "hardlink", "cross_volume"):
        sizes = {c.size for c in CASES if c.group == group}
        assert set(BOUNDARY_SIZES) <= sizes, group
    assert BOUNDARY_SIZES == (0, 1, MIB - 1, MIB, MIB + 1, 3 * MIB + 17)
    assert any(c.fault is not None and c.size > MIB for c in CASES)  # a fault in the middle of a multi-block copy
    for size in BOUNDARY_SIZES:
        assert len(media_bytes("probe", size)) == size


def test_manifest_combination_coverage():
    success = [c for c in CASES if c.fault is None]
    combos = {((c.poster, c.fanart, c.thumb), c.extra) for c in success}
    assert combos == {(combo, extra) for combo in MAIN_COMBOS for extra in range(14)}  # 8 x 14 = 112
    for group in ("native", "cross_volume"):
        assert {((c.poster, c.fanart, c.thumb), c.extra) for c in success if c.group == group} == combos
    assert {(c.poster, c.fanart, c.thumb) for c in CASES if c.group == "hardlink"} == set(MAIN_COMBOS)
    assert sum(1 for c in success if c.plant_in_target) == 90


def test_unicode_and_extension_case_coverage():
    names = [c.source_name for c in CASES] + list(SOURCE_DIRS) + list(LIBRARIES)
    text = "".join(names)
    assert any("一" <= ch <= "鿿" for ch in text)                          # CJK
    assert any("぀" <= ch <= "ヿ" for ch in text)                          # kana
    assert any(ord(ch) > 0xFFFF for ch in text)                                    # emoji (astral plane)
    assert any(unicodedata.combining(ch) for ch in text)                           # combining characters
    assert any(unicodedata.normalize("NFC", n) != n for n in names)                # NFD forms
    assert any(unicodedata.normalize("NFD", n) != n for n in names)                # NFC forms
    assert {c.ext for c in CASES} == set(EXTENSIONS)
    assert {c.ext.lower() for c in CASES} == {".mp4", ".mkv", ".avi", ".wmv", ".mov"}
    for group in ("native", "hardlink", "cross_volume", "fault"):
        assert len({c.ext for c in CASES if c.group == group}) >= 4, group
        assert len({c.library for c in CASES if c.group == group}) == len(LIBRARIES), group


def test_fault_table_design_covers_every_injectable_kind_and_every_resume_point():
    designed = {fault.kind for _, _, fault in FAULT_TABLE} | {
        kind for _, _, fault in FAULT_TABLE for _, kind in fault.then}
    assert designed == set(ExecutionFailureKind) - set(NON_INJECTABLE)
    assert {(shape, fault.p) for shape, _, fault in FAULT_TABLE} == _expected_points()
    for shape, _, fault in FAULT_TABLE:
        assert 0 < fault.p < FAULT_E_LENGTH[shape] and fault.at < FAULT_E_LENGTH[shape]


def test_non_injectable_set_is_empty_and_every_kind_is_accounted_for():
    assert NON_INJECTABLE == {}
    assert len(ExecutionFailureKind) == 27


# =========================================================================== the integrated gate (two runs)


@pytest.mark.parametrize("run_index", [0, 1], ids=["run1", "run2"])
def test_gate_run_every_case_passes(corpus, run_index):
    run = corpus[run_index]
    assert run.errors == []
    assert run.successes == 500  # 450 direct + 50 fault cases resumed to SUCCESS
    assert set(run.obs) == {c.cid for c in CASES}
    assert len(run.conflicts) == len(CONFLICT_PAIRS)
    assert run.target_planted_checks == 90 * 2 * len(TARGET_PLANTS)


@pytest.mark.parametrize("run_index", [0, 1], ids=["run1", "run2"])
def test_gate_run_covers_every_injectable_failure_kind(corpus, run_index):
    run = corpus[run_index]
    assert run.errors == []
    required = set(ExecutionFailureKind) - set(NON_INJECTABLE)
    assert run.kinds == required, sorted(k.value for k in required - run.kinds)


@pytest.mark.parametrize("run_index", [0, 1], ids=["run1", "run2"])
def test_gate_run_covers_every_resume_point(corpus, run_index):
    run = corpus[run_index]
    assert run.errors == []
    assert run.points == _expected_points(), sorted(_expected_points() - run.points)
    assert len(run.points) == 20 + 4


def test_gate_is_deterministic_across_two_runs(corpus):
    first, second = corpus
    assert first.errors == [] and second.errors == []
    for case in CASES:
        assert first.obs[case.cid] == second.obs[case.cid], case.cid
    assert first.conflicts == second.conflicts


def test_conflict_pairs_have_exactly_one_success_and_a_zero_effect_failure(corpus):
    for run in corpus:
        assert run.errors == []
        for label, outcome in run.conflicts.items():
            assert outcome["statuses"] == ["failed", "success"], label
            assert outcome["loser"] == ("failed", "target_conflict", "create_directory", 0), label


# =========================================================================== 1000 extrafanart, really executed


def test_one_film_really_materializes_1000_extrafanart(tmp_path):
    run = CorpusRun(tmp_path)
    run.setup()
    film, plan, artifacts = run.prepare("x1000", "FC2-4999999", LIBRARIES[0], SOURCE_DIRS[0], "x1000.MP4", ".MP4",
                                        media_bytes("x1000", 4099), True, True, True, 1000)
    assert sum(1 for r in artifacts if r.kind is ArtifactKind.EXTRAFANART) == 1000
    preflight = preflight_execution(plan, artifacts)
    assert preflight.ready
    result = execute_filesystem(preflight)
    assert result.status is ExecutionStatus.SUCCESS
    extras = [e for e in result.completed_effects if e.artifact_kind is ArtifactKind.EXTRAFANART]
    assert [e.ordinal for e in extras] == list(range(1, 1001))
    assert [os.path.basename(e.path) for e in extras] == [extrafanart_name(k) for k in range(1, 1001)]
    assert os.path.basename(extras[-1].path) == "extrafanart-1000.jpg"
    names = sorted(os.listdir(film.efd))
    assert names == sorted(extrafanart_name(k) for k in range(1, 1001))  # nothing missing, duplicated or extra
    contents = []
    for k in range(1, 1001):
        with open(os.path.join(film.efd, extrafanart_name(k)), "rb") as handle:
            data = handle.read()
        assert data == extra_image_bytes("x1000", k), k
        contents.append(data)
    assert len(set(contents)) == 1000
    assert read_tree(film.target_dir) == film.tree()
    assert not os.path.lexists(film.source)
    run.assert_planted_unchanged()


# =========================================================================== architecture regression scan


_EXECUTION_DIR = Path(executor.__file__).parent
_FROZEN_SITES = {"mkdir": {"_mkdir_exclusive"}, "rename": {"_same_volume_primitive", "_publish_no_replace"},
                 "link": {"_same_volume_primitive", "_publish_no_replace"},
                 "unlink": {"_remove_owned_temp", "_unlink_verified_source"}}
_FORBIDDEN_CALLS = {"replace", "makedirs", "rmtree", "rmdir", "remove", "removedirs", "chmod", "truncate",
                    "ftruncate", "utime", "renames"}


def _functions_calling(tree: ast.AST, attr: str) -> set[str]:
    found = set()
    for fn in ast.walk(tree):
        if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for node in ast.walk(fn):
                if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                        and node.func.attr == attr and isinstance(node.func.value, ast.Attribute)
                        and node.func.value.attr == "_FS"):
                    found.add(fn.name)
    return found


def test_architecture_regression_scan_of_the_mutation_sites():
    modules = sorted(_EXECUTION_DIR.glob("*.py"))
    assert {m.name for m in modules} == {"__init__.py", "errors.py", "models.py", "paths.py", "validation.py",
                                         "seal.py", "_fs.py", "directories.py", "transfer.py", "preflight.py",
                                         "executor.py"}
    sites = {op: set() for op in _FROZEN_SITES}
    for module in modules:
        tree = ast.parse(module.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                name = getattr(node.func, "attr", getattr(node.func, "id", None))
                assert name not in _FORBIDDEN_CALLS, (module.name, name)
                assert all(kw.arg != "exist_ok" for kw in node.keywords), module.name
            if isinstance(node, (ast.Name, ast.Attribute)):
                assert getattr(node, "id", getattr(node, "attr", None)) != "O_TRUNC", module.name
            if isinstance(node, ast.ExceptHandler) and module.name == "directories.py":
                caught = ast.unparse(node.type) if node.type is not None else "BaseException"
                assert "FileExistsError" not in caught, "an existing directory must never be tolerated"
        for op in sites:
            sites[op] |= _functions_calling(tree, op)
    assert sites == _FROZEN_SITES
    # The seam's defaults are the non-replacing primitives (never os.replace / an exist_ok mkdir).
    assert _fs._FS.rename is os.rename and _fs._FS.link is os.link and _fs._FS.mkdir is os.mkdir
    assert _fs._FS.unlink is os.unlink
    assert transfer._SAME_VOLUME_STRATEGY == ("rename" if _NT else "link")
    assert transfer._DIRECTORY_FSYNC is (not _NT)
