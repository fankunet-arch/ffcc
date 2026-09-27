"""P4-C8 S2: per-item stages and Phase B conflicts (contract sections 11.3, 14.3, 15.2, 21).

Lower layers are the real public APIs; foreign failures are injected by replacing the name inside
``stages`` (the module under test), never by re-implementing a stage.
"""

from __future__ import annotations

import hashlib
import os

import pytest

from fc2_metadata_core.batch import BatchItemErrorKind, BatchItemResult, BatchItemStatus
from fc2_organizer.execution import (
    CheckpointRejectionReason,
    EntryIdentity,
    EntryType,
    ExecutionPreflight,
    ManifestRejectionReason,
    PlanGraphError,
    PlanGraphRejectionReason,
)
from fc2_organizer.images import AcquiredImage, ImageAcquisitionResult, ImageRole
from fc2_organizer.materialization import ArtifactMappingError, MappingRejectionReason
from fc2_organizer.orchestration import IssueReason as R, ItemIssue, OrchestrationStage as St
from fc2_organizer.orchestration import stages
from fc2_organizer.planning import OrganizePlan, OutputPolicy
from fc2_organizer.publication import PublicationRecord

from ._fakes import build_metadata, minimal_jpeg
from ._helpers import LIBRARY, NUMBER, fake_checkpoint, fake_preflight, manifest_for, media_item, plan_for

ITEM = media_item(0, "FC2-PPV-1234567.mp4")


def _aggregation(kind: str = "success", **fields):
    return build_metadata(NUMBER, kind, **fields)


def _raising(exc):
    def raiser(*_args, **_kwargs):
        raise exc
    return raiser


class _HostileMeta(type):
    @property
    def __name__(cls):  # pragma: no cover - must never run
        raise AssertionError("hostile metaclass ran")


class _HostileError(Exception, metaclass=_HostileMeta):
    def __str__(self):  # pragma: no cover - must never run
        raise AssertionError("str ran")

    def __repr__(self):  # pragma: no cover - must never run
        raise AssertionError("repr ran")

    @property
    def args(self):  # pragma: no cover - must never run
        raise AssertionError("args read")


class _PlanSub(PlanGraphError):
    @property
    def reason(self):  # pragma: no cover - must never run
        raise AssertionError("subclass reason read")

    @reason.setter
    def reason(self, value):
        pass


def _assert_issue(issue, stage, reason, error_type, detail=None):
    assert type(issue) is ItemIssue
    assert (issue.stage, issue.reason, issue.error_type, issue.detail) == (stage, reason, error_type, detail)


# =========================================================================== metadata (11.3)


@pytest.mark.parametrize("kind, status", [("success", BatchItemStatus.SUCCESS), ("partial", BatchItemStatus.PARTIAL)])
def test_metadata_success_and_partial_go_on_to_planning(kind, status):
    aggregation = _aggregation(kind)
    item = BatchItemResult(index=0, number=NUMBER, status=status, aggregation_result=aggregation)
    assert stages.metadata_outcome(item) is aggregation


def test_metadata_failed_aggregate_is_unavailable():
    item = BatchItemResult(index=0, number=NUMBER, status=BatchItemStatus.FAILED,
                           aggregation_result=_aggregation("failed"))
    _assert_issue(stages.metadata_outcome(item), St.METADATA, R.METADATA_UNAVAILABLE, None)


@pytest.mark.parametrize("kind", list(BatchItemErrorKind))
def test_metadata_engine_failure_keeps_kind_and_class_name(kind):
    item = BatchItemResult(index=0, number=NUMBER, status=BatchItemStatus.FAILED, error_kind=kind,
                           error_type="TimeoutError")
    _assert_issue(stages.metadata_outcome(item), St.METADATA, R.METADATA_ENGINE_FAILURE, "TimeoutError", kind)


def test_metadata_engine_error_type_outside_the_issue_shape_collapses():
    item = BatchItemResult(index=0, number=NUMBER, status=BatchItemStatus.FAILED,
                           error_kind=BatchItemErrorKind.ENGINE_EXCEPTION, error_type="not a name " * 3)
    assert stages.metadata_outcome(item).error_type == "UnknownType"


# =========================================================================== planning / publication / NFO


def test_plan_stage_success():
    plan = stages.plan_stage(ITEM, NUMBER, _aggregation(), LIBRARY, OutputPolicy())
    assert type(plan) is OrganizePlan and plan.canonical_number == NUMBER


def test_plan_stage_invalid_library_root():
    _assert_issue(stages.plan_stage(ITEM, NUMBER, _aggregation(), "relative/lib", OutputPolicy()),
                  St.PLANNING, R.PLANNING_REJECTED, "InvalidLibraryRootError")


def test_plan_stage_foreign_exception(monkeypatch):
    monkeypatch.setattr(stages, "build_organize_plan", _raising(RuntimeError(r"C:\secret")))
    issue = stages.plan_stage(ITEM, NUMBER, _aggregation(), LIBRARY, OutputPolicy())
    _assert_issue(issue, St.PLANNING, R.PLANNING_REJECTED, "RuntimeError")


def test_publication_stage_success_and_identity_mismatch():
    plan = plan_for(ITEM, NUMBER)
    record = stages.publication_stage(plan, _aggregation())
    assert type(record) is PublicationRecord
    other = build_metadata("FC2-7654321")
    _assert_issue(stages.publication_stage(plan, other), St.PUBLICATION, R.PUBLICATION_REJECTED,
                  "PublicationIdentityMismatchError")


def test_nfo_stage_success_and_invalid_release():
    plan = plan_for(ITEM, NUMBER)
    good = stages.nfo_stage(stages.publication_stage(plan, _aggregation(release="2024-02-03")))
    assert type(good) is str and "<movie>" in good
    bad = stages.nfo_stage(stages.publication_stage(plan, _aggregation(release="2024-13-45")))
    _assert_issue(bad, St.NFO_RENDER, R.NFO_RENDER_FAILED, "NfoReleaseDateError")


@pytest.mark.parametrize("name, call", [
    ("build_organize_plan", lambda: stages.plan_stage(ITEM, NUMBER, _aggregation(), LIBRARY, OutputPolicy())),
    ("prepare_publication", lambda: stages.publication_stage(plan_for(ITEM), _aggregation())),
    ("render_movie_nfo", lambda: stages.nfo_stage(object())),
    ("build_artifact_requests", lambda: stages.manifest_stage(plan_for(ITEM), "<movie/>", object())),
    ("preflight_execution", lambda: stages.preflight_stage(plan_for(ITEM), ())),
])
@pytest.mark.parametrize("fatal", [KeyboardInterrupt(), SystemExit(2), GeneratorExit(), type("Custom", (BaseException,), {})()])
def test_base_exceptions_propagate_unchanged_from_every_stage(monkeypatch, name, call, fatal):
    monkeypatch.setattr(stages, name, _raising(fatal))
    with pytest.raises(BaseException) as info:
        call()
    assert info.value is fatal


def test_hostile_exception_metadata_is_never_read(monkeypatch):
    monkeypatch.setattr(stages, "render_movie_nfo", _raising(_HostileError()))
    issue = stages.nfo_stage(object())
    _assert_issue(issue, St.NFO_RENDER, R.NFO_RENDER_FAILED, "UnknownType")


# =========================================================================== images


def _images(pad: int = 0) -> ImageAcquisitionResult:
    content = minimal_jpeg(pad=pad)
    size = len(content)
    return ImageAcquisitionResult(poster=AcquiredImage(role=ImageRole.POSTER, candidate_index=0, content=content,
                                                       width=16, height=16, size_bytes=size,
                                                       sha256=hashlib.sha256(content).hexdigest()))


def test_image_outcome_classification():
    images = _images(50)
    size = images.total_bytes
    assert stages.image_outcome(images, None, size) is images  # total == R accepted
    _assert_issue(stages.image_outcome(images, None, size - 1), St.IMAGE_ACQUISITION, R.IMAGE_ACQUISITION_ERROR,
                  "ImageAcquisitionResult")
    _assert_issue(stages.image_outcome(None, "ImageInputError", size), St.IMAGE_ACQUISITION,
                  R.IMAGE_ACQUISITION_ERROR, "ImageInputError")
    _assert_issue(stages.image_outcome({"poster": b""}, None, size), St.IMAGE_ACQUISITION,
                  R.IMAGE_ACQUISITION_ERROR, "dict")


# =========================================================================== manifest


def test_manifest_stage_success():
    plan = plan_for(ITEM)
    artifacts = stages.manifest_stage(plan, "<movie/>", _images())
    assert [a.kind.value for a in artifacts] == ["nfo", "poster"]


def test_manifest_stage_reads_the_mapping_reason():
    plan = plan_for(ITEM)
    _assert_issue(stages.manifest_stage(plan, "", ImageAcquisitionResult()), St.MANIFEST, R.MANIFEST_REJECTED,
                  "ArtifactMappingError", MappingRejectionReason.NFO_EMPTY)


def test_manifest_stage_foreign_and_subclass_errors_have_no_detail(monkeypatch):
    plan = plan_for(ITEM)
    monkeypatch.setattr(stages, "build_artifact_requests", _raising(ValueError("x")))
    _assert_issue(stages.manifest_stage(plan, "<movie/>", ImageAcquisitionResult()), St.MANIFEST,
                  R.MANIFEST_REJECTED, "ValueError")

    class SubMapping(ArtifactMappingError):
        pass

    monkeypatch.setattr(stages, "build_artifact_requests",
                        _raising(SubMapping(MappingRejectionReason.DUPLICATE_TARGET)))
    _assert_issue(stages.manifest_stage(plan, "<movie/>", ImageAcquisitionResult()), St.MANIFEST,
                  R.MANIFEST_REJECTED, "SubMapping")


# =========================================================================== preflight


def test_preflight_stage_ready_on_a_real_tree(tmp_path):
    (tmp_path / "lib").mkdir()
    source = tmp_path / "dl" / "FC2-PPV-1234567.mp4"
    source.parent.mkdir()
    source.write_bytes(b"media")
    item = media_item(0, "FC2-PPV-1234567.mp4", directory=str(source.parent), size=5)
    plan = plan_for(item, NUMBER, str(tmp_path / "lib"))
    preflight = stages.preflight_stage(plan, manifest_for(plan))
    assert type(preflight) is ExecutionPreflight and preflight.ready is True


def test_preflight_stage_plan_graph_rejection_detail():
    inside = media_item(0, "FC2-PPV-1234567.mp4", directory=os.path.join(LIBRARY, NUMBER))
    plan = plan_for(inside, NUMBER)
    _assert_issue(stages.preflight_stage(plan, manifest_for(plan)), St.PREFLIGHT, R.PREFLIGHT_REJECTED,
                  "PlanGraphError", PlanGraphRejectionReason.SOURCE_INSIDE_TARGET)


def test_preflight_stage_manifest_rejection_detail():
    plan = plan_for(ITEM)
    _assert_issue(stages.preflight_stage(plan, manifest_for(plan)[1:]), St.PREFLIGHT, R.PREFLIGHT_REJECTED,
                  "ArtifactManifestError", ManifestRejectionReason.NFO_MISSING)


def test_preflight_stage_checkpoint_rejection():
    plan = plan_for(ITEM)
    issue = stages.preflight_stage(plan, manifest_for(plan), fake_checkpoint(plan))
    _assert_issue(issue, St.PREFLIGHT, R.CHECKPOINT_REJECTED, "CheckpointError", CheckpointRejectionReason.SEAL_INVALID)


def test_preflight_stage_foreign_and_subclass_errors(monkeypatch):
    plan = plan_for(ITEM)
    monkeypatch.setattr(stages, "preflight_execution", _raising(OSError(5, "denied", r"C:\x")))
    _assert_issue(stages.preflight_stage(plan, ()), St.PREFLIGHT, R.PREFLIGHT_REJECTED, "OSError")
    monkeypatch.setattr(stages, "preflight_execution", _raising(_PlanSub(PlanGraphRejectionReason.FIELD_TYPE)))
    _assert_issue(stages.preflight_stage(plan, ()), St.PREFLIGHT, R.PREFLIGHT_REJECTED, "_PlanSub")


# =========================================================================== Phase B (14.3)


def _identity(inode: int) -> EntryIdentity:
    return EntryIdentity(device=7, inode=inode, entry_type=EntryType.FILE, size=1, mtime_ns=1)


def _entry(index: int, number: str, inode: int | None, name: str | None = None):
    item = media_item(index, name or f"FC2-PPV-{number[4:]}.mp4", directory=os.path.join(LIBRARY + "-dl", str(index)))
    plan = plan_for(item, number)
    return index, fake_preflight(plan, source_identity=None if inode is None else _identity(inode))


def test_phase_b_hardlink_same_inode_different_names():
    entries = [_entry(0, "FC2-1000001", 50), _entry(1, "FC2-1000002", 50), _entry(2, "FC2-1000003", 51)]
    assert stages.phase_b_conflicts(entries) == {0: (R.DUPLICATE_SOURCE_IN_BATCH, (1,)),
                                                 1: (R.DUPLICATE_SOURCE_IN_BATCH, (0,))}


def test_phase_b_same_target_and_combination():
    entries = [_entry(0, "FC2-1000001", 1), _entry(1, "FC2-1000001", 2), _entry(3, "FC2-1000001", 1),
               _entry(4, "FC2-1000009", None)]
    assert stages.phase_b_conflicts(entries) == {
        0: (R.DUPLICATE_SOURCE_IN_BATCH, (1, 3)),
        1: (R.DUPLICATE_TARGET_IN_BATCH, (0, 3)),
        3: (R.DUPLICATE_SOURCE_IN_BATCH, (0, 1)),
    }


def test_phase_b_unknown_identity_only_groups_by_target():
    entries = [_entry(0, "FC2-1000001", None), _entry(1, "FC2-1000002", None)]
    assert stages.phase_b_conflicts(entries) == {}


@pytest.mark.skipif(os.name != "nt", reason="case-insensitive target keys are Windows-only (contract 14.3)")
def test_phase_b_target_key_is_casefolded_on_windows():
    index, first = _entry(0, "FC2-1000001", 1)
    upper_library = LIBRARY.upper()
    item = media_item(1, "FC2-PPV-1000001.mkv", directory=LIBRARY + "-other")
    plan = plan_for(item, "FC2-1000001", upper_library)
    assert plan.target_directory.absolute_path != first.plan.target_directory.absolute_path
    assert stages.phase_b_conflicts([(0, first), (1, fake_preflight(plan, source_identity=_identity(2)))]) == {
        0: (R.DUPLICATE_TARGET_IN_BATCH, (1,)), 1: (R.DUPLICATE_TARGET_IN_BATCH, (0,))}


def test_phase_b_touches_no_filesystem(monkeypatch):
    entries = [_entry(0, "FC2-1000001", 50), _entry(1, "FC2-1000002", 50)]
    hits: list[str] = []
    for name in ("lstat", "stat", "scandir", "listdir", "open"):
        monkeypatch.setattr(os, name, lambda *_a, _n=name, **_k: hits.append(_n))
    conflicts = stages.phase_b_conflicts(entries)
    monkeypatch.undo()  # assert only after the traps are gone
    assert hits == [] and len(conflicts) == 2
