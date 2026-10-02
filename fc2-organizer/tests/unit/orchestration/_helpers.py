"""Shared helpers for the P4-C8 orchestration tests (construction plan section 0.5).

Generic helpers (all batches): ``make_media_tree``, ``tree_snapshot``, ``mutation_traps``,
``projection``, ``assert_source_not_lost``, ``fs_fault``. Model builders (S1 onward) construct
real lower-layer values (plans through the public ``build_organize_plan``; preflights / results /
checkpoints as plain, model-valid, *unsealed* P4-C7 values) so the P4-C8 model invariants can be
exercised without any filesystem access. Builders never decide a P4-C8 verdict (retry kind,
outcome, warnings, ...): tests state the frozen expectations themselves.

Production code never imports this module. Every production name is bound at import (collection) time:
several contract guards purge ``fc2_*`` from ``sys.modules`` while running, and a later function-level import
would build a second copy of a package whose exact-type checks then reject the first copy's objects.
"""

from __future__ import annotations

import builtins
import dataclasses
import hashlib
import os
import secrets
import shutil
import stat
import sys
import threading
from pathlib import Path

from fc2_metadata_core.batch import BatchItemErrorKind, BatchItemResult, BatchItemStatus, BatchLineage, BatchResult
from fc2_metadata_core.models import NormalizedMetadata
from fc2_metadata_core.normalize import normalize_fc2_number
from fc2_organizer import execution as execution_package
from fc2_organizer import materialization as materialization_package
from fc2_organizer.discovery import DiscoveredMediaItem, discover_media
from fc2_organizer.execution import _fs as execution_fs
from fc2_organizer.execution import executor as execution_executor
from fc2_organizer.execution import (
    CompletedEffect,
    EffectKind,
    EntryIdentity,
    EntryType,
    ExecutionCheckpoint,
    ExecutionFailure,
    ExecutionFailureKind,
    ExecutionPreflight,
    ExecutionResult,
    ExecutionStatus,
    ExecutionStep,
    LeftoverTemporary,
    PathRole,
    PreflightBlocker,
    PreflightBlockReason,
    PreflightMode,
    TransferMode,
)
from fc2_organizer.images import ImageAcquisitionPolicy, ImageCandidateFailure, ImageFailureKind, ImageRole
from fc2_organizer.materialization import ArtifactKind, ArtifactWriteRequest
from fc2_organizer.materialization import artifacts as materialization_artifacts
from fc2_organizer.materialization import atomic as materialization_atomic
from fc2_organizer.orchestration import (
    DEFAULT_MAX_RETAINED_ARTIFACT_BYTES,
    BatchExecutionResult,
    BatchOrchestrator,
    BatchPreview,
    ExecutionDisposition,
    IssueReason,
    ItemExecution,
    ItemIssue,
    ItemPreview,
    OrchestrationStage,
    PreviewState,
    RetryMaterial,
)
from fc2_organizer.planning import OrganizePlan, OutputPolicy, build_organize_plan

from ._fakes import (
    ScriptedEngine,
    ScriptedImageClient,
    build_metadata,
    jpeg_response,
    minimal_jpeg,
    status_response,
)

NUMBER = "FC2-1234567"
LIBRARY = r"C:\fc2-p4c8-library" if os.name == "nt" else "/fc2-p4c8-library"
DOWNLOADS = r"C:\fc2-p4c8-downloads" if os.name == "nt" else "/fc2-p4c8-downloads"
NFO_BYTES = b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<movie><title>t</title></movie>\n'


def new_id() -> str:
    return secrets.token_hex(16)


# =========================================================================== generic helpers


def make_media_tree(root: Path, files: dict[str, bytes]) -> tuple[DiscoveredMediaItem, ...]:
    """Create ``files`` (relative path -> bytes) below ``root`` and return ``discover_media(root).items``."""
    for relative, content in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    return discover_media(str(root)).items


def _sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def tree_snapshot(root: Path) -> dict[str, tuple]:
    """relative path -> (type, sha256 or None, st_ino, st_mtime_ns); links are never followed."""
    snapshot: dict[str, tuple] = {}
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        for name in sorted(dirnames + filenames):
            path = os.path.join(dirpath, name)
            st = os.lstat(path)
            if stat.S_ISREG(st.st_mode):
                kind, digest = "file", _sha256_file(path)
            elif stat.S_ISDIR(st.st_mode):
                kind, digest = "dir", None
            else:
                kind, digest = "other", None
            snapshot[os.path.relpath(path, root)] = (kind, digest, st.st_ino, st.st_mtime_ns)
    return snapshot


_WRITE_FLAGS = os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND | getattr(os, "O_EXCL", 0)
_MUTATING_OS = ("mkdir", "makedirs", "rename", "renames", "replace", "remove", "unlink", "rmdir", "removedirs",
                "link", "symlink", "truncate", "ftruncate", "chmod", "utime")
_MUTATING_SHUTIL = ("copy", "copy2", "copyfile", "copyfileobj", "copytree", "move", "rmtree")
_WRITER_NAMES = ("execute_filesystem", "materialize_artifact", "materialize_atomic_bytes")


class MutationTrap:
    """Contract section 16 interception: every hit is recorded and raises ``AssertionError``."""

    def __init__(self) -> None:
        self.calls: list[str] = []
        self._lock = threading.Lock()

    def hit(self, name: str) -> None:
        with self._lock:
            self.calls.append(name)
        raise AssertionError(f"forbidden filesystem mutation during a read-only operation: {name}")

    def make(self, name: str):
        def trapped(*_args, **_kwargs):
            self.hit(name)
        return trapped


def mutation_traps(monkeypatch) -> MutationTrap:
    """Trap every mutating API listed by contract section 16 (os, write-mode ``open`` / ``os.open``,
    shutil, and every module attribute bound to ``execute_filesystem`` / ``materialize_*``).
    Read-only opens keep working. Positive control: calling any trapped API records a hit."""
    trap = MutationTrap()
    for name in _MUTATING_OS:
        if hasattr(os, name):
            monkeypatch.setattr(os, name, trap.make(f"os.{name}"))
    real_os_open = os.open

    def guarded_os_open(path, flags, *rest, **kwargs):
        if flags & _WRITE_FLAGS:
            trap.hit("os.open(write)")
        return real_os_open(path, flags, *rest, **kwargs)

    monkeypatch.setattr(os, "open", guarded_os_open)
    real_open = builtins.open

    def guarded_open(file, mode="r", *args, **kwargs):
        if any(flag in mode for flag in "wax+"):
            trap.hit("open(write)")
        return real_open(file, mode, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", guarded_open)
    for name in _MUTATING_SHUTIL:
        monkeypatch.setattr(shutil, name, trap.make(f"shutil.{name}"))
    for name, module in writer_bindings():
        monkeypatch.setattr(module, name, trap.make(name))
    return trap


_HELD_WRITER_MODULES = (execution_package, execution_executor, materialization_package, materialization_artifacts,
                        materialization_atomic)


def writer_bindings() -> list[tuple[str, object]]:
    """Every module attribute bound to one of the three writers: the collection-time module objects held here
    plus whatever is in ``sys.modules`` now (contract guards may have purged and re-imported the packages)."""
    modules = {id(m): m for m in (*_HELD_WRITER_MODULES, *list(sys.modules.values())) if m is not None}
    bindings = []
    for module in modules.values():
        for name in _WRITER_NAMES:
            value = getattr(module, name, None)
            if callable(value) and str(getattr(value, "__module__", "")).startswith("fc2_organizer."):
                bindings.append((name, module))
    return bindings


def assert_source_not_lost(source_path, final_path, original_sha256: str) -> None:
    """Contract section 35 core invariant: the source path or the final path (or both) holds a regular,
    non-link file whose bytes equal the original source bytes."""

    def holds(path) -> bool:
        try:
            st = os.lstat(path)
        except OSError:
            return False
        return stat.S_ISREG(st.st_mode) and _sha256_file(str(path)) == original_sha256

    assert holds(source_path) or holds(final_path), "source media was lost"


class FsFault:
    """Path-keyed, thread-safe fault injection through the private seams ``execution._fs._FS`` and
    ``materialization.atomic._FS`` (contract section 34.2; tests only). ``fail(seam, op, where, exc)``
    makes ``op`` raise ``exc`` whenever one of its path arguments (or, for fd operations, the path
    the fd was opened from) contains ``where``; ``times`` bounds the number of hits. Artifact bytes are written
    to a ``.fc2tmp-*.part`` temporary, so a per-artifact fault keys ``publish`` (``(temporary, target)``) on
    the target name, or the fd operations on the target directory."""

    _PATH_OPS = {"lstat", "stat", "open", "mkdir", "rename", "link", "unlink", "listdir", "publish"}
    _FD_OPS = {"fstat", "read", "write", "fsync", "close"}

    def __init__(self, monkeypatch) -> None:
        self._lock = threading.Lock()
        self._rules: list[list] = []
        self._fd_paths: dict[tuple[str, int], str] = {}
        self.hits: list[tuple[str, str]] = []
        for seam, module in (("execution", execution_fs), ("materialization", materialization_atomic)):
            ops = {}
            for spec in dataclasses.fields(module._FS):
                ops[spec.name] = self._wrap(seam, spec.name, getattr(module._FS, spec.name))
            monkeypatch.setattr(module, "_FS", dataclasses.replace(module._FS, **ops))

    def fail(self, seam: str, op: str, where: str, exc: BaseException, *, times: int | None = None) -> None:
        with self._lock:
            self._rules.append([seam, op, os.path.normcase(where), exc, times])

    def _match(self, seam: str, op: str, paths: list[str]) -> BaseException | None:
        with self._lock:
            for rule in self._rules:
                r_seam, r_op, where, exc, times = rule
                if r_seam == seam and r_op == op and times != 0 and any(where in os.path.normcase(p) for p in paths):
                    if times is not None:
                        rule[4] = times - 1
                    self.hits.append((seam, op))
                    return exc
        return None

    def _wrap(self, seam: str, op: str, real):
        if op not in self._PATH_OPS | self._FD_OPS:
            return real

        def wrapped(*args, **kwargs):
            if op in self._FD_OPS:
                with self._lock:
                    path = self._fd_paths.get((seam, args[0]))
                paths = [path] if path is not None else []
            else:
                paths = [a for a in args if isinstance(a, str)]
            exc = self._match(seam, op, paths)
            if exc is not None:
                raise exc
            result = real(*args, **kwargs)
            if op == "open" and type(result) is int and paths:
                with self._lock:
                    self._fd_paths[(seam, result)] = paths[0]
            elif op == "close":
                with self._lock:
                    self._fd_paths.pop((seam, args[0]), None)
            return result

        return wrapped


def fs_fault(monkeypatch) -> FsFault:
    return FsFault(monkeypatch)


def _issue_projection(issue) -> tuple | None:
    if issue is None:
        return None
    return (issue.stage, issue.reason, issue.error_type, issue.detail)


def _preflight_projection(preflight) -> tuple | None:
    if preflight is None:
        return None
    return (preflight.mode, preflight.ready, preflight.blockers, preflight.transfer_mode, preflight.pending_units,
            preflight.completed_units, preflight.skipped_steps,
            tuple((r.kind, r.target_path, r.ordinal, hashlib.sha256(r.content).hexdigest())
                  for r in preflight.artifacts))


def _execution_projection(execution) -> tuple | None:
    if execution is None:
        return None
    return (execution.status, execution.mode, execution.transfer_mode,
            tuple((e.kind, e.role, e.path, e.artifact_kind, e.ordinal) for e in execution.completed_effects),
            execution.new_effect_count, execution.failure, execution.skipped_steps,
            tuple((t.directory_role, t.name) for t in execution.leftover_temporaries))


def projection(obj) -> tuple:
    """Contract section 29 deterministic projection of a ``BatchPreview`` / ``BatchExecutionResult``:
    every item field except exactly the six identities / seals section 29 excludes -- ``preview_id``,
    ``result_id``, the lineage token, P4-C7 ``preflight_id`` / ``checkpoint_id`` and seals. Leftover temporaries
    are projected with their directory role and name."""
    if type(obj) is BatchPreview:
        items = tuple(
            (i.index, i.generation, i.media_item, i.canonical_number, i.metadata_position,
             None if i.metadata is None else (i.metadata.status, i.metadata.error_kind, i.metadata.error_type),
             i.plan, i.image_failures, _preflight_projection(i.preflight), i.state, _issue_projection(i.issue),
             i.conflict_with, i.retry_origin, i.warnings)
            for i in obj.items)
    elif type(obj) is BatchExecutionResult:
        items = tuple(
            (i.index, i.generation, i.media_item, i.canonical_number, i.metadata_position, i.plan,
             i.image_failures, i.conflict_with, i.preview_state, _issue_projection(i.issue), i.warnings,
             i.disposition, _execution_projection(i.execution), i.retry_kind,
             None if i.retry_material is None else (i.retry_material.plan, len(i.retry_material.artifacts),
                                                    i.retry_material.checkpoint is None))
            for i in obj.items)
    else:  # pragma: no cover - test bug
        raise AssertionError(f"cannot project {type(obj).__name__}")
    return (type(obj).__name__, obj.generation, obj.base_result_id is None, obj.retry_scope, obj.library_root,
            obj.output_policy, obj.image_policy, obj.batch_size, obj.retention_budget_bytes,
            obj.retry_budget_bytes, items)


# =========================================================================== model builders (S1)


def media_item(index: int = 0, name: str = "FC2-PPV-1234567.mp4", directory: str = DOWNLOADS,
               size: int = 100) -> DiscoveredMediaItem:
    """A hand-built, model-valid discovered item (nothing is created on disk)."""
    extension = os.path.splitext(name)[1].lower() or ".mp4"
    return DiscoveredMediaItem(index=index, source_path=os.path.join(directory, name), relative_path=name,
                               extension=extension, size=size)


def plan_for(item: DiscoveredMediaItem, number: str = NUMBER, library_root: str = LIBRARY) -> OrganizePlan:
    """A real plan from the public (pure) P4-C2 planner."""
    return build_organize_plan(item, number, NormalizedMetadata(number=number, title="Example Title"),
                               library_root)


def manifest_for(plan: OrganizePlan, *, poster: bytes | None = b"P" * 10, fanart: bytes | None = b"F" * 20,
                 thumb: bytes | None = b"T" * 30, extra: tuple[bytes, ...] = (),
                 nfo: bytes = NFO_BYTES) -> tuple[ArtifactWriteRequest, ...]:
    """A manifest with exactly the given payload bytes (the ``content`` objects are used as passed)."""
    requests = [ArtifactWriteRequest(ArtifactKind.NFO, plan.nfo_path.absolute_path, nfo)]
    for kind, path, content in ((ArtifactKind.POSTER, plan.poster_path, poster),
                                (ArtifactKind.FANART, plan.fanart_path, fanart),
                                (ArtifactKind.THUMB, plan.thumb_path, thumb)):
        if content is not None:
            requests.append(ArtifactWriteRequest(kind, path.absolute_path, content))
    for ordinal, content in enumerate(extra, start=1):
        target = os.path.join(plan.extrafanart_directory.absolute_path, f"fanart{ordinal}.jpg")
        requests.append(ArtifactWriteRequest(ArtifactKind.EXTRAFANART, target, content, ordinal))
    return tuple(requests)


def payload(artifacts: tuple[ArtifactWriteRequest, ...]) -> int:
    return sum(len(r.content) for r in artifacts)


_DIR_ID = EntryIdentity(device=1, inode=10, entry_type=EntryType.DIRECTORY, size=None, mtime_ns=None)
_FILE_ID = EntryIdentity(device=1, inode=11, entry_type=EntryType.FILE, size=100, mtime_ns=5)
_HEX64 = "0" * 64


def fake_checkpoint(plan: OrganizePlan) -> ExecutionCheckpoint:
    effect = CompletedEffect(kind=EffectKind.TARGET_DIRECTORY_CREATED, role=PathRole.TARGET_DIRECTORY,
                             path=plan.target_directory.absolute_path, identity=_DIR_ID, size=None, sha256=None,
                             artifact_kind=None, ordinal=None)
    return ExecutionCheckpoint(checkpoint_id=new_id(), plan_fingerprint=_HEX64, manifest_fingerprint=_HEX64,
                               library_root_identity=_DIR_ID, source_identity=_FILE_ID,
                               transfer_mode=TransferMode.SAME_VOLUME, target_directory_identity=_DIR_ID,
                               extrafanart_directory_identity=None, completed_effects=(effect,),
                               leftover_temporaries=(), seal=_HEX64)


def fake_preflight(plan: OrganizePlan, artifacts: tuple[ArtifactWriteRequest, ...] | None = None, *,
                   ready: bool = True, checkpoint: ExecutionCheckpoint | None = None,
                   source_identity: EntryIdentity | None = None) -> ExecutionPreflight:
    """A model-valid (unsealed) P4-C7 preflight; never executable by P4-C7 itself."""
    blockers = () if ready else (PreflightBlocker(PreflightBlockReason.TARGET_DIRECTORY_EXISTS,
                                                  PathRole.TARGET_DIRECTORY),)
    return ExecutionPreflight(
        preflight_id=new_id(), mode=PreflightMode.FRESH if checkpoint is None else PreflightMode.RESUME,
        plan=plan, artifacts=manifest_for(plan) if artifacts is None else artifacts, checkpoint=checkpoint,
        plan_fingerprint=_HEX64, manifest_fingerprint=_HEX64, ready=ready, blockers=blockers,
        library_root_identity=None, source_identity=source_identity, transfer_mode=None, completed_units=(),
        pending_units=(), skipped_steps=(), seal=_HEX64)


def fake_execution(plan: OrganizePlan, status: ExecutionStatus, *,
                   kind: ExecutionFailureKind = ExecutionFailureKind.MEDIA_TRANSFER_FAILED,
                   leftovers: bool = False) -> ExecutionResult:
    """A model-valid P4-C7 result of the given status (PARTIAL carries a fresh checkpoint)."""
    effect = CompletedEffect(kind=EffectKind.TARGET_DIRECTORY_CREATED, role=PathRole.TARGET_DIRECTORY,
                             path=plan.target_directory.absolute_path, identity=_DIR_ID, size=None, sha256=None,
                             artifact_kind=None, ordinal=None)
    temporaries = (LeftoverTemporary(PathRole.TARGET_DIRECTORY, f".fc2tmp-{new_id()}.part"),) if leftovers else ()
    failure = None if status is ExecutionStatus.SUCCESS else ExecutionFailure(step=ExecutionStep.MOVE_MEDIA,
                                                                              kind=kind)
    return ExecutionResult(
        status=status, preflight_id=new_id(), mode=PreflightMode.FRESH, transfer_mode=None,
        completed_effects=() if status is ExecutionStatus.FAILED else (effect,),
        new_effect_count=0 if status is ExecutionStatus.FAILED else 1, failure=failure,
        checkpoint=fake_checkpoint(plan) if status is ExecutionStatus.PARTIAL else None,
        leftover_temporaries=temporaries, media_sha256=None, skipped_steps=())


def metadata_item(index: int, number: str = NUMBER, kind: str = "success", generation: int = 0) -> BatchItemResult:
    """A Phase 3 item: ``success`` / ``partial`` / ``failed`` (real aggregation) or ``engine``
    (FAILED without a result, ``ENGINE_EXCEPTION``)."""
    if kind == "engine":
        return BatchItemResult(index=index, number=number, status=BatchItemStatus.FAILED,
                               error_kind=BatchItemErrorKind.ENGINE_EXCEPTION, error_type="RuntimeError",
                               generation=generation)
    status = {"success": BatchItemStatus.SUCCESS, "partial": BatchItemStatus.PARTIAL,
              "failed": BatchItemStatus.FAILED}[kind]
    return BatchItemResult(index=index, number=number, status=status,
                           aggregation_result=build_metadata(number, kind), generation=generation)


def metadata_batch(items: tuple[BatchItemResult, ...] = (), lineage: BatchLineage | None = None,
                   generation: int = 0) -> BatchResult:
    return BatchResult(items=items, generation=generation, lineage=lineage or BatchLineage.new())


def issue(reason: IssueReason, **kwargs) -> ItemIssue:
    """``ItemIssue`` with the stage of the frozen contract section 10.2 table (stated independently)."""
    stage = {
        IssueReason.NUMBER_NOT_RECOGNIZED: OrchestrationStage.NUMBER_RECOGNITION,
        IssueReason.DUPLICATE_SOURCE_IN_BATCH: OrchestrationStage.BATCH_CONFLICT,
        IssueReason.DUPLICATE_TARGET_IN_BATCH: OrchestrationStage.BATCH_CONFLICT,
        IssueReason.METADATA_UNAVAILABLE: OrchestrationStage.METADATA,
        IssueReason.METADATA_ENGINE_FAILURE: OrchestrationStage.METADATA,
        IssueReason.PLANNING_REJECTED: OrchestrationStage.PLANNING,
        IssueReason.PUBLICATION_REJECTED: OrchestrationStage.PUBLICATION,
        IssueReason.NFO_RENDER_FAILED: OrchestrationStage.NFO_RENDER,
        IssueReason.IMAGE_ACQUISITION_ERROR: OrchestrationStage.IMAGE_ACQUISITION,
        IssueReason.MANIFEST_REJECTED: OrchestrationStage.MANIFEST,
        IssueReason.PREFLIGHT_BLOCKED: OrchestrationStage.PREFLIGHT,
        IssueReason.PREFLIGHT_REJECTED: OrchestrationStage.PREFLIGHT,
        IssueReason.CHECKPOINT_REJECTED: OrchestrationStage.PREFLIGHT,
    }.get(reason, OrchestrationStage.EXECUTION)
    return ItemIssue(stage, reason, **kwargs)


def image_failure() -> ImageCandidateFailure:
    return ImageCandidateFailure(role=ImageRole.EXTRAFANART, candidate_index=0, kind=ImageFailureKind.HTTP_STATUS,
                                 http_status=404)


class Lineage:
    """One lineage under construction: a shared metadata batch, media items and plans by index."""

    def __init__(self, size: int, *, kinds: dict[int, str] | None = None) -> None:
        self.size = size
        self.media = [media_item(i, f"FC2-PPV-{1000000 + i}.mp4") for i in range(size)]
        self.numbers = [f"FC2-{1000000 + i}" for i in range(size)]
        kinds = kinds or {}
        self.metadata = metadata_batch(tuple(metadata_item(i, self.numbers[i], kinds.get(i, "success"))
                                             for i in range(size)))
        self.plans = [plan_for(self.media[i], self.numbers[i]) for i in range(size)]

    def preview_item(self, index: int, *, state: PreviewState = PreviewState.READY, reason: IssueReason | None = None,
                     preflight=..., generation: int = 0, retry_origin=None, conflict_with: tuple[int, ...] = (),
                     issue_kwargs: dict | None = None, image_failures: tuple = (), with_plan: bool = True,
                     with_metadata: bool = True) -> ItemPreview:
        plan = self.plans[index] if with_plan else None
        if preflight is ...:
            preflight = fake_preflight(plan) if (plan is not None and state is PreviewState.READY) else None
        return ItemPreview(
            index=index, generation=generation, media_item=self.media[index],
            canonical_number=None if reason is IssueReason.NUMBER_NOT_RECOGNIZED else self.numbers[index],
            metadata_position=index if with_metadata else None,
            metadata=self.metadata.items[index] if with_metadata else None,
            plan=plan, image_failures=image_failures, preflight=preflight, state=state,
            issue=None if reason is None else issue(reason, **(issue_kwargs or {})),
            conflict_with=conflict_with, retry_origin=retry_origin)

    def preview(self, items, *, generation: int = 0, base_result_id: str | None = None, retry_scope=None,
                budget: int = DEFAULT_MAX_RETAINED_ARTIFACT_BYTES, retry_budget: int | None = None) -> BatchPreview:
        return BatchPreview(preview_id=new_id(), lineage=self.metadata.lineage, generation=generation,
                            base_result_id=base_result_id, retry_scope=retry_scope, library_root=LIBRARY,
                            output_policy=OutputPolicy(), image_policy=ImageAcquisitionPolicy(),
                            batch_size=self.size, items=tuple(items), metadata_batch=self.metadata,
                            retention_budget_bytes=budget, retry_budget_bytes=retry_budget)

    def execution_item(self, index: int, disposition: ExecutionDisposition, *, status: ExecutionStatus | None = None,
                       state: PreviewState = PreviewState.READY, reason: IssueReason | None = None,
                       execution=..., material=..., artifacts=None, warnings: tuple = (), generation: int = 0,
                       conflict_with: tuple[int, ...] = (), issue_kwargs: dict | None = None,
                       with_plan: bool = True, with_metadata: bool = True, image_failures: tuple = (),
                       checkpoint=...) -> ItemExecution:
        """``material`` / ``execution`` are explicit when passed; the ``...`` defaults only build what the
        disposition row of contract section 10.6 needs (never a retry-kind decision: material is
        attached only when the test asks with ``material=True``)."""
        plan = self.plans[index] if with_plan else None
        if execution is ...:
            execution = fake_execution(plan, status) if disposition is ExecutionDisposition.EXECUTED else None
        if reason is None and execution is not None and execution.status is not ExecutionStatus.SUCCESS:
            reason = (IssueReason.EXECUTION_PARTIAL if execution.status is ExecutionStatus.PARTIAL
                      else IssueReason.EXECUTION_FAILED)
            issue_kwargs = {"detail": execution.failure.kind, **(issue_kwargs or {})}
        if material is True:
            if checkpoint is ...:
                checkpoint = execution.checkpoint if execution is not None else None
            material = RetryMaterial(plan, manifest_for(plan) if artifacts is None else artifacts, checkpoint)
        elif material is ...:
            material = None
        return ItemExecution(
            index=index, generation=generation, media_item=self.media[index],
            canonical_number=None if reason is IssueReason.NUMBER_NOT_RECOGNIZED else self.numbers[index],
            metadata_position=index if with_metadata else None,
            metadata=self.metadata.items[index] if with_metadata else None,
            plan=plan, image_failures=image_failures, conflict_with=conflict_with, preview_state=state,
            issue=None if reason is None else issue(reason, **(issue_kwargs or {})), warnings=warnings,
            disposition=disposition, execution=execution, retry_material=material)

    def result(self, items, *, generation: int = 0, preview_id: str | None = "new", base_result_id: str | None = None,
               retry_scope=None, budget: int = DEFAULT_MAX_RETAINED_ARTIFACT_BYTES,
               retry_budget: int | None = None) -> BatchExecutionResult:
        return BatchExecutionResult(
            result_id=new_id(), preview_id=new_id() if preview_id == "new" else preview_id,
            lineage=self.metadata.lineage, generation=generation, base_result_id=base_result_id,
            retry_scope=retry_scope, library_root=LIBRARY, output_policy=OutputPolicy(),
            image_policy=ImageAcquisitionPolicy(), batch_size=self.size, items=tuple(items),
            metadata_batch=self.metadata, retention_budget_bytes=budget, retry_budget_bytes=retry_budget)


def tampered(obj, **changes):
    """A shallow copy of a frozen dataclass with fields rewritten via ``object.__setattr__``."""
    import copy

    clone = copy.copy(obj)
    for name, value in changes.items():
        object.__setattr__(clone, name, value)
    return clone


# =========================================================================== S2: preview corpus / runner


WATCHDOG_SECONDS = 60


def run(coro, timeout: float = WATCHDOG_SECONDS):
    """``asyncio.run`` under a watchdog: a regression that would hang fails the test instead (never used as a
    correctness mechanism)."""
    import asyncio

    async def guarded():
        return await asyncio.wait_for(coro, timeout)

    return asyncio.run(guarded())


def image_url(number: str, role: str) -> str:
    return f"https://img.example.test/{number}/{role}.jpg"


@dataclasses.dataclass
class Film:
    """One synthetic media file of a corpus and the scripted answers about it."""

    name: str
    directory: str = ""
    kind: str = "success"  # metadata: success / partial / failed / engine (exception) / mismatch
    poster: bool = True
    fanart: bool = True
    thumb: bool = True
    extra: int = 0
    extra_fail: int = 0
    release: str | None = None
    content: bytes | None = None


class Corpus:
    """A real ``tmp_path`` download tree discovered by ``discover_media`` plus a scripted engine and image
    client that answer for its films (built only through public APIs)."""

    def __init__(self, root: Path, films: list[Film], *, library: bool = True) -> None:
        self.root = root
        self.downloads = root / "dl"
        self.library = root / "lib"
        self.downloads.mkdir(parents=True, exist_ok=True)
        if library:
            self.library.mkdir(parents=True, exist_ok=True)
        files: dict[str, bytes] = {}
        script: dict[str, object] = {}
        fields: dict[str, dict] = {}
        images: dict[str, object] = {}
        seed = 0
        for position, film in enumerate(films):
            relative = f"{film.directory}/{film.name}" if film.directory else film.name
            files[relative] = film.content if film.content is not None else b"media-%d-" % position + relative.encode()
            number = normalize_fc2_number(film.name).canonical
            if number is None or number in script:
                continue
            script[number] = {"engine": RuntimeError("scripted engine failure"), "mismatch": object()}.get(
                film.kind, film.kind)
            urls: dict[str, tuple[str, ...]] = {}
            for role, present in (("poster", film.poster), ("fanart", film.fanart), ("thumb", film.thumb)):
                if present:
                    urls[f"{role}_urls"] = (image_url(number, role),)
            extra_urls = []
            for ordinal in range(film.extra + film.extra_fail):
                extra_urls.append(image_url(number, f"extra{ordinal}"))
            if extra_urls:
                urls["extrafanart"] = tuple(extra_urls)
            for role_urls in urls.values():
                for url in role_urls:
                    seed += 1
                    failing = url.endswith(tuple(f"extra{i}.jpg" for i in range(film.extra,
                                                                                 film.extra + film.extra_fail)))
                    images[url] = status_response(404) if failing else jpeg_response(minimal_jpeg(seed=seed))
            if film.release is not None:
                urls["release"] = film.release
            fields[number] = urls
        self.items = make_media_tree(self.downloads, files)
        self.engine = ScriptedEngine(script, fields=fields)
        self.client = ScriptedImageClient(images)

    def orchestrator(self, **kwargs):
        return BatchOrchestrator(self.engine, self.client, kwargs.pop("library_root", str(self.library)), **kwargs)

    def preview(self, orchestrator=None, items=None):
        orchestrator = orchestrator or self.orchestrator()
        return run(orchestrator.preview(self.items if items is None else items))


def by_name(preview) -> dict[str, object]:
    """basename of the source -> preview item."""
    return {os.path.basename(item.source_path): item for item in preview.items}
