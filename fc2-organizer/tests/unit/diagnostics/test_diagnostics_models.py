"""P4-C9 contract section 11: every diagnostics model -- valid values, wrong types, ``bool`` posing as ``int``,
subclasses posing as exact types, range violations and cross-field invariants. Every violation is a
``DiagnosticsContractError`` with fixed wording."""

from __future__ import annotations

import dataclasses

import pytest
from fc2_metadata_core.aggregation import AggregateStatus
from fc2_metadata_core.batch import BatchItemErrorKind, BatchItemStatus
from fc2_metadata_core.models import SourceErrorKind, SourceStatus
from fc2_organizer.diagnostics import (
    BatchDiagnostics,
    DiagnosticsContractError,
    DiagnosticsKind,
    ExecutionDiagnostics,
    FieldConflictDiagnostics,
    FieldProvenance,
    ImageFailureGroup,
    IssueDiagnostics,
    ItemDiagnostics,
    LeftoverTemporaryDiagnostics,
    MetadataBatchCounts,
    MetadataDiagnostics,
    PathPolicy,
    PreflightDiagnostics,
    ResultShape,
    SourceAttemptDiagnostics,
    SourceDiagnostics,
    TimingPolicy,
)
from fc2_organizer.execution import (
    CheckpointRejectionReason,
    EffectKind,
    ExecutionFailureKind,
    ExecutionStatus,
    ExecutionStep,
    PathRole,
    PreflightMode,
    TransferMode,
)
from fc2_organizer.images import ImageFailureKind, ImageRole
from fc2_organizer.materialization import ArtifactKind, MappingRejectionReason
from fc2_organizer.orchestration import (
    BatchOutcome,
    ExecutionDisposition,
    IssueReason,
    ItemWarning,
    OrchestrationStage,
    PreviewState,
    RetryKind,
)

from . import _builders as b


class IntSub(int):
    pass


class StrSub(str):
    pass


class TupleSub(tuple):
    pass


def _subclass_instance(subclass, base):
    """An instance of ``subclass`` carrying ``base``'s field values (built without running ``__post_init__``)."""
    clone = object.__new__(subclass)
    for field in dataclasses.fields(base):
        object.__setattr__(clone, field.name, getattr(base, field.name))
    return clone


def rejects(factory, **overrides):
    with pytest.raises(DiagnosticsContractError):
        factory(**overrides)


ALL_MODELS = [
    MetadataBatchCounts, IssueDiagnostics, FieldProvenance, FieldConflictDiagnostics, SourceAttemptDiagnostics,
    SourceDiagnostics, MetadataDiagnostics, ImageFailureGroup, PreflightDiagnostics, LeftoverTemporaryDiagnostics,
    ExecutionDiagnostics, ItemDiagnostics, BatchDiagnostics,
]


@pytest.mark.parametrize("model", ALL_MODELS)
def test_models_are_frozen_slotted_dataclasses_without_custom_hooks(model):
    assert dataclasses.is_dataclass(model)
    params = model.__dataclass_params__
    assert params.frozen is True
    assert "__slots__" in vars(model)
    for forbidden in ("to_dict", "to_json", "dump", "save", "__getattr__", "__getattribute__"):
        assert forbidden not in vars(model), (model, forbidden)


@pytest.mark.parametrize("factory", [
    b.make_metadata_batch_counts, b.make_issue, b.make_attempt, b.make_source, b.make_metadata, b.make_preflight,
    b.make_execution, b.make_leftover, b.make_image_group, b.make_item, b.make_execution_item,
    b.make_preview_diagnostics, b.make_execution_diagnostics,
])
def test_valid_models_are_constructed_immutable_and_equal_by_value(factory):
    first, second = factory(), factory()
    assert first == second
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(first, dataclasses.fields(first)[0].name, None)


# --------------------------------------------------------------------------- MetadataBatchCounts


def test_metadata_batch_counts_total_is_the_sum():
    rejects(b.make_metadata_batch_counts, total=4)
    rejects(b.make_metadata_batch_counts, success=0)
    assert b.make_metadata_batch_counts(generation=2, total=0, success=0, partial=0, failed=0).total == 0


@pytest.mark.parametrize("name", ["generation", "total", "success", "partial", "failed"])
@pytest.mark.parametrize("bad", [True, False, IntSub(1), -1, 1.0, "1", None])
def test_metadata_batch_counts_fields_are_exact_non_negative_ints(name, bad):
    rejects(b.make_metadata_batch_counts, **{name: bad})


# --------------------------------------------------------------------------- IssueDiagnostics (T-1)


def test_issue_follows_the_t1_table_for_every_reason():
    from fc2_organizer.diagnostics.models import ISSUE_TABLE

    for reason, (stage, needs_error_type, detail_types, needs_detail) in ISSUE_TABLE:
        error_type = "SomeError" if needs_error_type else None
        detail = next(iter(detail_types[0])) if needs_detail else None
        assert IssueDiagnostics(stage=stage, reason=reason, error_type=error_type, detail=detail).reason is reason
        wrong_stage = next(s for s in OrchestrationStage if s is not stage)
        rejects(IssueDiagnostics, stage=wrong_stage, reason=reason, error_type=error_type, detail=detail)
        rejects(IssueDiagnostics, stage=stage, reason=reason, error_type="X" if error_type is None else None,
                detail=detail)
        if needs_detail:
            rejects(IssueDiagnostics, stage=stage, reason=reason, error_type=error_type, detail=None)
        if detail_types == ():
            rejects(IssueDiagnostics, stage=stage, reason=reason, error_type=error_type,
                    detail=ExecutionFailureKind.SOURCE_CHANGED)
        else:
            foreign = next(iter(PathRole))  # an enum member of a type no T-1 row allows
            rejects(IssueDiagnostics, stage=stage, reason=reason, error_type=error_type, detail=foreign)


@pytest.mark.parametrize("bad", ["", "1bad", "a b", "x" * 129, StrSub("ok"), 1, b"ok"])
def test_issue_error_type_must_be_an_identifier_of_1_to_128_exact_chars(bad):
    rejects(b.make_issue, stage=OrchestrationStage.PLANNING, reason=IssueReason.PLANNING_REJECTED, error_type=bad)


def test_issue_error_type_boundary_128_is_accepted():
    ok = b.make_issue(stage=OrchestrationStage.PLANNING, reason=IssueReason.PLANNING_REJECTED, error_type="E" * 128)
    assert len(ok.error_type) == 128


def test_issue_detail_must_belong_to_the_enum_types_allowed_for_the_reason():
    rejects(b.make_issue, stage=OrchestrationStage.EXECUTION, reason=IssueReason.EXECUTION_FAILED,
            detail=CheckpointRejectionReason.__members__[next(iter(CheckpointRejectionReason.__members__))])
    rejects(b.make_issue, stage=OrchestrationStage.EXECUTION, reason=IssueReason.EXECUTION_FAILED, detail="x")
    ok = b.make_issue(stage=OrchestrationStage.EXECUTION, reason=IssueReason.EXECUTION_FAILED,
                      detail=ExecutionFailureKind.MEDIA_WRITE_FAILED)
    assert ok.detail is ExecutionFailureKind.MEDIA_WRITE_FAILED
    ok = b.make_issue(stage=OrchestrationStage.MANIFEST, reason=IssueReason.MANIFEST_REJECTED, error_type="E",
                      detail=next(iter(MappingRejectionReason)))
    assert ok.detail is not None


@pytest.mark.parametrize("field", ["stage", "reason"])
def test_issue_enum_fields_are_exact_enum_members(field):
    rejects(b.make_issue, **{field: "metadata"})
    rejects(b.make_issue, **{field: None})


# --------------------------------------------------------------------------- provenance / conflict


@pytest.mark.parametrize("bad", ["unknown", "", StrSub("title"), None, 1])
def test_provenance_field_must_be_a_known_field(bad):
    rejects(FieldProvenance, field=bad, source_ids=("a",))


@pytest.mark.parametrize("bad", [(), ("a", "a"), ["a"], ("a/b",), ("",), (StrSub("a"),), ("a" * 65,), (1,),
                                 TupleSub(("a",)), tuple("s%d" % i for i in range(65))])
def test_provenance_source_ids_are_a_non_empty_unique_tuple_of_safe_ids(bad):
    rejects(FieldProvenance, field="title", source_ids=bad)


def test_provenance_accepts_the_boundary_64_ids_and_a_64_char_id():
    assert len(FieldProvenance(field="title", source_ids=tuple("s%d" % i for i in range(64))).source_ids) == 64
    assert FieldProvenance(field="title", source_ids=("a" * 64,)).source_ids == ("a" * 64,)


def test_conflict_rules():
    ok = FieldConflictDiagnostics(field="title", selected_source_id="a", alternative_source_ids=("b", "c"))
    assert ok.alternative_source_ids == ("b", "c")
    rejects(FieldConflictDiagnostics, field="actors", selected_source_id="a", alternative_source_ids=("b",))
    rejects(FieldConflictDiagnostics, field="title", selected_source_id="a", alternative_source_ids=())
    rejects(FieldConflictDiagnostics, field="title", selected_source_id="a", alternative_source_ids=("a",))
    rejects(FieldConflictDiagnostics, field="title", selected_source_id="a", alternative_source_ids=("b", "b"))
    rejects(FieldConflictDiagnostics, field="title", selected_source_id="bad id", alternative_source_ids=("b",))
    rejects(FieldConflictDiagnostics, field="title", selected_source_id=StrSub("a"), alternative_source_ids=("b",))
    assert FieldConflictDiagnostics(field="external_ids", selected_source_id="a",
                                    alternative_source_ids=("b",)).field == "external_ids"


# --------------------------------------------------------------------------- attempts / sources


def test_attempt_status_and_error_kind_pairing():
    rejects(b.make_attempt, error_kind=SourceErrorKind.TIMEOUT)
    rejects(b.make_attempt, status=SourceStatus.NETWORK_ERROR, error_kind=None)
    rejects(b.make_attempt, status=SourceStatus.NETWORK_ERROR, error_kind=SourceErrorKind.NOT_FOUND)
    ok = b.make_attempt(status=SourceStatus.NETWORK_ERROR, error_kind=SourceErrorKind.TIMEOUT, completed=False)
    assert ok.completed is False


@pytest.mark.parametrize("bad", [True, 0, -1, IntSub(1), 1.0, None])
def test_attempt_sequence_is_an_exact_int_at_least_one(bad):
    rejects(b.make_attempt, sequence=bad)


@pytest.mark.parametrize("bad", [1, "x", None, 0])
def test_attempt_completed_is_an_exact_bool(bad):
    rejects(b.make_attempt, completed=bad)


@pytest.mark.parametrize("bad", [-1, True, 604800001, 1.5, IntSub(1), "1"])
def test_attempt_timings_are_none_or_exact_ints_in_range(bad):
    rejects(b.make_attempt, elapsed_ms=bad, backoff_before_ms=0)
    rejects(b.make_attempt, elapsed_ms=0, backoff_before_ms=bad)


def test_attempt_timings_boundaries_and_pairing():
    assert b.make_attempt(elapsed_ms=0, backoff_before_ms=0).elapsed_ms == 0
    assert b.make_attempt(elapsed_ms=604800000, backoff_before_ms=604800000).backoff_before_ms == 604800000
    rejects(b.make_attempt, elapsed_ms=5, backoff_before_ms=None)
    rejects(b.make_attempt, elapsed_ms=None, backoff_before_ms=5)


def test_source_rules():
    rejects(b.make_source, source_id="")
    rejects(b.make_source, source_id="-bad")
    rejects(b.make_source, source_id="x" * 65)
    rejects(b.make_source, source_id=StrSub("fc2db_net"))
    rejects(b.make_source, status=SourceStatus.NETWORK_ERROR, error_kind=None)
    rejects(b.make_source, error_kind=SourceErrorKind.TIMEOUT)
    rejects(b.make_source, operational_failure=True)
    rejects(b.make_source, status=SourceStatus.BLOCKED, error_kind=SourceErrorKind.BLOCKED, operational_failure=False)
    ok = b.make_source(status=SourceStatus.BLOCKED, error_kind=SourceErrorKind.BLOCKED, operational_failure=True,
                       contributed=False, provided_fields=())
    assert ok.operational_failure is True
    rejects(b.make_source, contributed=False)  # provides a field while not contributing
    rejects(b.make_source, provided_fields=("title", "title"))
    rejects(b.make_source, provided_fields=("studio", "title"))
    rejects(b.make_source, provided_fields=("nope",))
    rejects(b.make_source, provided_fields=["title"])


def test_source_trace_fields_are_consistent():
    no_trace = b.make_source(trace_available=False, attempt_count=None, max_attempts=None, deadline_exceeded=None,
                             deadline_during=None, attempts=())
    assert no_trace.trace_available is False
    rejects(b.make_source, trace_available=False)  # trace fields present without a trace
    rejects(b.make_source, attempt_count=2)
    rejects(b.make_source, attempt_count=True)
    rejects(b.make_source, max_attempts=0)
    rejects(b.make_source, deadline_exceeded=None)
    rejects(b.make_source, deadline_exceeded=True)  # deadline_during is None
    rejects(b.make_source, deadline_during="attempt")  # not exceeded
    rejects(b.make_source, deadline_exceeded=True, deadline_during="soon")
    for during in ("attempt", "backoff"):
        assert b.make_source(deadline_exceeded=True, deadline_during=during).deadline_during == during
    rejects(b.make_source, attempts=(b.make_attempt(sequence=2),))
    rejects(b.make_source, attempts=(b.make_attempt(), b.make_attempt(sequence=1)), attempt_count=2)
    circuit = b.make_source(status=SourceStatus.NETWORK_ERROR, error_kind=SourceErrorKind.CIRCUIT_OPEN,
                            operational_failure=True, contributed=False, provided_fields=(), attempt_count=0,
                            attempts=())
    assert circuit.attempts == ()


def test_source_attempts_boundary_8_and_9():
    attempts = tuple(b.make_attempt(sequence=i + 1, status=SourceStatus.NETWORK_ERROR,
                                    error_kind=SourceErrorKind.TIMEOUT) for i in range(8))
    ok = b.make_source(status=SourceStatus.NETWORK_ERROR, error_kind=SourceErrorKind.TIMEOUT,
                       operational_failure=True, contributed=False, provided_fields=(), attempt_count=8,
                       max_attempts=8, attempts=attempts)
    assert len(ok.attempts) == 8
    nine = attempts + (b.make_attempt(sequence=9, status=SourceStatus.NETWORK_ERROR,
                                      error_kind=SourceErrorKind.TIMEOUT),)
    rejects(b.make_source, status=SourceStatus.NETWORK_ERROR, error_kind=SourceErrorKind.TIMEOUT,
            operational_failure=True, contributed=False, provided_fields=(), attempt_count=9, max_attempts=9,
            attempts=nine)


# --------------------------------------------------------------------------- MetadataDiagnostics


def test_metadata_aggregate_vs_engine_failure_exclusivity():
    failed = b.make_metadata(status=BatchItemStatus.FAILED, error_kind=BatchItemErrorKind.ENGINE_EXCEPTION,
                             aggregate_status=None, traces_available=False, sources=(), disabled_source_ids=(),
                             field_provenance=())
    assert failed.aggregate_status is None
    rejects(b.make_metadata, error_kind=BatchItemErrorKind.ENGINE_EXCEPTION)  # both set
    rejects(b.make_metadata, aggregate_status=None, error_kind=None)  # neither set
    rejects(b.make_metadata, status=BatchItemStatus.SUCCESS, error_kind=BatchItemErrorKind.ENGINE_EXCEPTION,
            aggregate_status=None, traces_available=False, sources=(), field_provenance=())
    rejects(b.make_metadata, status=BatchItemStatus.FAILED, error_kind=BatchItemErrorKind.ENGINE_EXCEPTION,
            aggregate_status=None, traces_available=True, sources=(), field_provenance=())
    rejects(b.make_metadata, status=BatchItemStatus.FAILED, error_kind=BatchItemErrorKind.ENGINE_EXCEPTION,
            aggregate_status=None, traces_available=False, sources=(b.make_source(),), field_provenance=())


def test_metadata_sources_rules():
    rejects(b.make_metadata, sources=(b.make_source(), b.make_source()))
    rejects(b.make_metadata, traces_available=False)  # the source has a trace
    rejects(b.make_metadata, disabled_source_ids=("fc2db_net",))  # overlaps a source
    rejects(b.make_metadata, disabled_source_ids=("av123", "av123"))
    rejects(b.make_metadata, disabled_source_ids=("bad id",))
    many = tuple(b.make_source(source_id="s%d" % i, provided_fields=()) for i in range(65))
    rejects(b.make_metadata, sources=many, field_provenance=())
    sixty_four = tuple(b.make_source(source_id="s%d" % i, provided_fields=()) for i in range(64))
    assert len(b.make_metadata(sources=sixty_four, field_provenance=(), disabled_source_ids=()).sources) == 64


def test_metadata_provenance_rules():
    rejects(b.make_metadata, field_provenance=(FieldProvenance(field="studio", source_ids=("fc2db_net",)),
                                              FieldProvenance(field="title", source_ids=("fc2db_net",))))
    rejects(b.make_metadata, field_provenance=(FieldProvenance(field="title", source_ids=("fc2db_net",)),
                                              FieldProvenance(field="title", source_ids=("fc2db_net",))))
    rejects(b.make_metadata, field_provenance=())  # source claims 'title' but provenance is empty
    rejects(b.make_metadata, field_provenance=[FieldProvenance(field="title", source_ids=("fc2db_net",))])
    rejects(b.make_metadata, field_provenance=("x",))
    conflicts = tuple(FieldConflictDiagnostics(field="title", selected_source_id="a", alternative_source_ids=("b",))
                      for _ in range(256))
    assert len(b.make_metadata(conflicts=conflicts).conflicts) == 256
    rejects(b.make_metadata, conflicts=conflicts + conflicts[:1])
    rejects(b.make_metadata, conflicts=("x",))


@pytest.mark.parametrize("bad", [-1, True, 604800001, 1.0, IntSub(1)])
def test_metadata_elapsed_is_none_or_a_bounded_exact_int(bad):
    rejects(b.make_metadata, elapsed_ms=bad)


def test_metadata_elapsed_boundaries():
    assert b.make_metadata(elapsed_ms=604800000).elapsed_ms == 604800000
    assert b.make_metadata(elapsed_ms=0).elapsed_ms == 0


@pytest.mark.parametrize("field", ["status", "aggregate_status"])
def test_metadata_enum_fields_are_exact_members(field):
    rejects(b.make_metadata, **{field: "success"})


# --------------------------------------------------------------------------- image failure groups


def test_image_failure_group_rules():
    ok = b.make_image_group(kind=ImageFailureKind.HTTP_STATUS, count=3, http_statuses=(404, 500))
    assert ok.http_statuses == (404, 500)
    rejects(b.make_image_group, kind=ImageFailureKind.HTTP_STATUS, http_statuses=())
    rejects(b.make_image_group, http_statuses=(404,))
    rejects(b.make_image_group, kind=ImageFailureKind.HTTP_STATUS, http_statuses=(500, 404))
    rejects(b.make_image_group, kind=ImageFailureKind.HTTP_STATUS, http_statuses=(404, 404))
    rejects(b.make_image_group, kind=ImageFailureKind.HTTP_STATUS, http_statuses=(99,))
    rejects(b.make_image_group, kind=ImageFailureKind.HTTP_STATUS, http_statuses=(600,))
    rejects(b.make_image_group, kind=ImageFailureKind.HTTP_STATUS, http_statuses=(True,))
    assert b.make_image_group(kind=ImageFailureKind.HTTP_STATUS, http_statuses=(100, 599)).http_statuses == (100, 599)
    rejects(b.make_image_group, count=0)
    rejects(b.make_image_group, count=True)
    rejects(b.make_image_group, role="poster")
    rejects(b.make_image_group, kind="timeout")


# --------------------------------------------------------------------------- preflight / execution / leftovers


def test_preflight_rules():
    assert b.make_preflight(ready=False, blockers=(b.make_blocker(),)).ready is False
    rejects(b.make_preflight, ready=False)  # no blockers but not ready
    rejects(b.make_preflight, ready=True, blockers=(b.make_blocker(),))
    rejects(b.make_preflight, blockers=("x",))
    rejects(b.make_preflight, blockers=[])
    rejects(b.make_preflight, ready=1)
    rejects(b.make_preflight, pending_unit_count=-1)
    rejects(b.make_preflight, completed_unit_count=True)
    rejects(b.make_preflight, skipped_steps=("x",))
    rejects(b.make_preflight, artifact_counts=((ArtifactKind.NFO, 1),))
    rejects(b.make_preflight, artifact_counts=tuple(reversed(b.make_preflight().artifact_counts)))
    rejects(b.make_preflight, artifact_counts=tuple((k, -1) for k in ArtifactKind))
    rejects(b.make_preflight, transfer_mode="same_volume")
    rejects(b.make_preflight, mode="fresh")
    many = tuple(b.make_blocker() for _ in range(256))
    assert len(b.make_preflight(ready=False, blockers=many).blockers) == 256
    rejects(b.make_preflight, ready=False, blockers=many + many[:1])


def test_carried_blockers_and_failures_are_validated_values():
    from fc2_organizer.execution import PreflightBlocker

    rejects(b.make_preflight, ready=False, blockers=(object(),))

    class BlockerSub(PreflightBlocker):
        pass

    sub = BlockerSub(reason=b.make_blocker().reason, role=PathRole.SOURCE)
    rejects(b.make_preflight, ready=False, blockers=(sub,))


def test_execution_rules():
    assert b.make_execution().status is ExecutionStatus.SUCCESS
    failed = b.make_execution(status=ExecutionStatus.FAILED, failure=b.make_failure(), new_effect_count=0,
                              effect_counts=tuple((k, 0) for k in EffectKind))
    assert failed.failure is not None
    partial = b.make_execution(status=ExecutionStatus.PARTIAL, failure=b.make_failure(), checkpoint_present=True)
    assert partial.checkpoint_present is True
    rejects(b.make_execution, failure=b.make_failure())  # SUCCESS with a failure
    rejects(b.make_execution, status=ExecutionStatus.FAILED, failure=None)
    rejects(b.make_execution, checkpoint_present=True)  # SUCCESS with a checkpoint
    rejects(b.make_execution, status=ExecutionStatus.PARTIAL, failure=b.make_failure(), checkpoint_present=False)
    rejects(b.make_execution, new_effect_count=3)  # more than the effects
    rejects(b.make_execution, new_effect_count=True)
    rejects(b.make_execution, effect_counts=((EffectKind.MEDIA_PUBLISHED, 1),))
    rejects(b.make_execution, artifact_counts=((ArtifactKind.NFO, 1),))
    rejects(b.make_execution, skipped_steps=["x"])
    rejects(b.make_execution, leftover_temporary_count=1)
    rejects(b.make_execution, failure=object(), status=ExecutionStatus.FAILED)
    name = ".fc2tmp-" + "0" * 32 + ".part"
    ok = b.make_execution(leftover_temporary_count=1, leftover_temporaries=(b.make_leftover(name=name),))
    assert ok.leftover_temporaries[0].name == name
    many = tuple(b.make_leftover() for _ in range(256))
    assert b.make_execution(leftover_temporary_count=256, leftover_temporaries=many).leftover_temporary_count == 256
    rejects(b.make_execution, leftover_temporary_count=257, leftover_temporaries=many + many[:1])


def _tampered(value, **fields):
    """A copy of a (valid) upstream value with fields rewritten behind its constructor's back."""
    clone = dataclasses.replace(value)
    for name, replacement in fields.items():
        object.__setattr__(clone, name, replacement)
    return clone


def test_failure_validation_covers_the_p4_c7_cross_field_rules():
    from fc2_organizer.diagnostics.models import failure_problem
    from fc2_organizer.execution import ExecutionFailure

    assert failure_problem(b.make_failure()) is None
    assert failure_problem(b.make_failure(kind=ExecutionFailureKind.ARTIFACT_WRITE_FAILED, write_stage="flush")) is None
    assert failure_problem(_tampered(b.make_failure(), write_stage="flush")) is not None
    assert failure_problem(b.make_failure(artifact_kind=ArtifactKind.EXTRAFANART, ordinal=2)) is None
    assert failure_problem(_tampered(b.make_failure(), ordinal=2)) is not None
    assert failure_problem(b.make_failure(kind=ExecutionFailureKind.ARTIFACT_CLEANUP_FAILED,
                                          target_published=True)) is None
    assert failure_problem(_tampered(b.make_failure(), target_published=True)) is not None
    assert failure_problem(_tampered(b.make_failure(), errno=True)) is not None
    assert failure_problem(_tampered(b.make_failure(), step="move_media")) is not None
    assert failure_problem("x") is not None

    class FailureSub(ExecutionFailure):
        pass

    sub = object.__new__(FailureSub)
    for field in dataclasses.fields(ExecutionFailure):
        object.__setattr__(sub, field.name, getattr(b.make_failure(), field.name))
    assert failure_problem(sub) is not None


@pytest.mark.parametrize("bad", ["x", ".fc2tmp-" + "0" * 31 + ".part", ".fc2tmp-" + "G" * 32 + ".part",
                                 ".fc2tmp-" + "0" * 32 + ".part\n", StrSub(".fc2tmp-" + "0" * 32 + ".part"), 1])
def test_leftover_name_is_none_or_the_frozen_format(bad):
    rejects(b.make_leftover, name=bad)


@pytest.mark.parametrize("role", [PathRole.SOURCE, PathRole.NFO, "target_directory", None])
def test_leftover_directory_role_is_target_or_extrafanart_directory(role):
    rejects(b.make_leftover, directory_role=role)
    assert b.make_leftover(directory_role=PathRole.EXTRAFANART_DIRECTORY).directory_role is \
        PathRole.EXTRAFANART_DIRECTORY


# --------------------------------------------------------------------------- ItemDiagnostics


def test_item_number_follows_the_issue():
    unrecognized = b.make_issue(stage=OrchestrationStage.NUMBER_RECOGNITION,
                                reason=IssueReason.NUMBER_NOT_RECOGNIZED)
    ok = b.make_item(canonical_number=None, issue=unrecognized, preview_state=PreviewState.UNPREPARED,
                     metadata=None, preflight=None)
    assert ok.canonical_number is None
    rejects(b.make_item, canonical_number=None)
    rejects(b.make_item, canonical_number="FC2-1")
    rejects(b.make_item, canonical_number=StrSub(b.NUMBER))
    rejects(b.make_item, issue=unrecognized)  # a number alongside NUMBER_NOT_RECOGNIZED
    rejects(b.make_item, canonical_number=123)


@pytest.mark.parametrize("name", ["index", "generation", "source_size"])
@pytest.mark.parametrize("bad", [True, -1, IntSub(1), 1.0, None, "1"])
def test_item_ints_are_exact_non_negative(name, bad):
    rejects(b.make_item, **{name: bad})


@pytest.mark.parametrize("field", ["source_name", "target_directory_name", "target_media_name"])
@pytest.mark.parametrize("bad", ["", ".", "..", "a/b", "a\\b", "a\x01", "a\x7f", "a\x85", "a ", "a‮",
                                 "a﻿", "a\ud800", "x" * 256, StrSub("ok"), 1])
def test_item_path_derived_names_are_none_or_a_safe_basename(field, bad):
    rejects(b.make_item, **{field: bad})


@pytest.mark.parametrize("field", ["source_name", "target_directory_name", "target_media_name"])
def test_item_path_derived_names_accept_printable_and_boundary_text(field):
    for good in ("movie.mp4", "全角　空白 日本語.mkv", "x" * 255, "a b", "Authorization-C9CANARY.mp4"):
        assert getattr(b.make_item(**{field: good}), field) == good


def test_item_warnings_are_unique_and_in_declaration_order():
    ok = b.make_item(warnings=(ItemWarning.METADATA_PARTIAL, ItemWarning.POSTER_ABSENT))
    assert len(ok.warnings) == 2
    rejects(b.make_item, warnings=(ItemWarning.POSTER_ABSENT, ItemWarning.METADATA_PARTIAL))
    rejects(b.make_item, warnings=(ItemWarning.POSTER_ABSENT, ItemWarning.POSTER_ABSENT))
    rejects(b.make_item, warnings=[ItemWarning.POSTER_ABSENT])
    rejects(b.make_item, warnings=("poster_absent",))


def test_item_conflict_with_is_strictly_increasing_and_never_self():
    assert b.make_item(index=3, conflict_with=(1, 2, 4)).conflict_with == (1, 2, 4)
    rejects(b.make_item, index=3, conflict_with=(4, 2))
    rejects(b.make_item, index=3, conflict_with=(2, 2))
    rejects(b.make_item, index=3, conflict_with=(3,))
    rejects(b.make_item, conflict_with=(True,))
    rejects(b.make_item, conflict_with=[1])
    rejects(b.make_item, conflict_with=(-1,))


def test_item_retry_origin_is_none_or_a_retry_kind_other_than_none():
    rejects(b.make_item, retry_origin=RetryKind.NONE)
    rejects(b.make_item, retry_origin="resume")
    assert b.make_item(retry_origin=RetryKind.RESUME).retry_origin is RetryKind.RESUME


def test_item_execution_triplet_is_set_together():
    rejects(b.make_item, disposition=ExecutionDisposition.EXECUTED)
    rejects(b.make_item, retry_kind=RetryKind.NONE)
    rejects(b.make_item, retry_material_retained=False)
    rejects(b.make_execution_item, retry_kind=None)
    rejects(b.make_execution_item, retry_material_retained=None)
    rejects(b.make_execution_item, retry_material_retained=0)
    rejects(b.make_execution_item, disposition="executed")


def test_item_execution_present_iff_executed():
    rejects(b.make_execution_item, disposition=ExecutionDisposition.NOT_SELECTED)  # execution present
    rejects(b.make_execution_item, execution=None)  # EXECUTED without execution
    ok = b.make_execution_item(disposition=ExecutionDisposition.NOT_SELECTED, execution=None,
                               retry_kind=RetryKind.DEFERRED, retry_material_retained=True)
    assert ok.execution is None
    rejects(b.make_item, execution=b.make_execution())  # execution without a disposition


def test_item_image_failures_are_unique_and_ordered_by_role_then_kind():
    first = b.make_image_group(role=ImageRole.POSTER, kind=ImageFailureKind.TIMEOUT)
    second = b.make_image_group(role=ImageRole.POSTER, kind=ImageFailureKind.TRANSPORT_ERROR)
    third = b.make_image_group(role=ImageRole.FANART, kind=ImageFailureKind.INVALID_URL)
    assert b.make_item(image_failures=(first, second, third)).image_failures == (first, second, third)
    rejects(b.make_item, image_failures=(third, first))
    rejects(b.make_item, image_failures=(second, first))
    rejects(b.make_item, image_failures=(first, first))
    rejects(b.make_item, image_failures=[first])
    rejects(b.make_item, image_failures=("x",))


def test_item_nested_models_are_exact_and_validated():
    rejects(b.make_item, metadata="x")
    rejects(b.make_item, preflight="x")
    rejects(b.make_item, issue="x")
    rejects(b.make_item, preview_state="ready")
    rejects(b.make_execution_item, execution="x")


def test_item_nested_subclass_is_rejected():
    class MetadataSub(MetadataDiagnostics):
        pass

    rejects(b.make_item, metadata=_subclass_instance(MetadataSub, b.make_metadata()))


# --------------------------------------------------------------------------- BatchDiagnostics


def test_batch_kind_and_shape_basics():
    assert b.make_preview_diagnostics().kind is DiagnosticsKind.PREVIEW
    assert b.make_execution_diagnostics().kind is DiagnosticsKind.EXECUTION
    rejects(b.make_preview_diagnostics, kind="preview")
    rejects(b.make_preview_diagnostics, shape="main")
    rejects(b.make_preview_diagnostics, path_policy="none")
    rejects(b.make_preview_diagnostics, timing_policy="omit")
    rejects(b.make_preview_diagnostics, metadata_batch="x")


def test_batch_preview_is_never_merged():
    rejects(b.make_preview_diagnostics, shape=ResultShape.MERGED, generation=1,
            items=(b.make_item(generation=1),))


def test_batch_generation_matches_the_shape():
    rejects(b.make_preview_diagnostics, generation=1)  # MAIN with generation 1
    rejects(b.make_preview_diagnostics, shape=ResultShape.RETRY, generation=0, retry_scope=())
    ok = b.make_preview_diagnostics(shape=ResultShape.RETRY, generation=1, retry_scope=(RetryKind.RESUME,),
                                    batch_size=1, items=(b.make_item(generation=1, retry_origin=RetryKind.RESUME),))
    assert ok.shape is ResultShape.RETRY
    rejects(b.make_preview_diagnostics, generation=True)


def test_batch_retry_scope_rules():
    rejects(b.make_preview_diagnostics, retry_scope=(RetryKind.RESUME,))  # MAIN with a scope
    retry_items = dict(shape=ResultShape.RETRY, generation=1, batch_size=1,
                       items=(b.make_item(generation=1, retry_origin=RetryKind.RESUME),))
    rejects(b.make_preview_diagnostics, retry_scope=None, **retry_items)
    rejects(b.make_preview_diagnostics, retry_scope=(RetryKind.NONE,), **retry_items)
    rejects(b.make_preview_diagnostics, retry_scope=(RetryKind.DEFERRED, RetryKind.RESUME), **retry_items)
    rejects(b.make_preview_diagnostics, retry_scope=(RetryKind.RESUME, RetryKind.RESUME), **retry_items)
    rejects(b.make_preview_diagnostics, retry_scope=[RetryKind.RESUME], **retry_items)
    rejects(b.make_preview_diagnostics, retry_scope=frozenset({RetryKind.RESUME}), **retry_items)
    empty = b.make_preview_diagnostics(retry_scope=(), **retry_items)  # an empty RETRY scope is LEGAL
    assert empty.retry_scope == ()
    merged = b.make_execution_diagnostics(shape=ResultShape.MERGED, generation=2,
                                          items=(b.make_execution_item(generation=1),))
    assert merged.retry_scope is None
    rejects(b.make_execution_diagnostics, shape=ResultShape.MERGED, generation=2, retry_scope=(),
            items=(b.make_execution_item(generation=1),))


def test_batch_applicability_table_preview():
    rejects(b.make_preview_diagnostics, preview_summary=None)
    rejects(b.make_preview_diagnostics, execution_summary=b.make_execution_summary(total=1))
    rejects(b.make_preview_diagnostics, outcome=BatchOutcome.SUCCESS)
    rejects(b.make_preview_diagnostics, items=(b.make_execution_item(),))  # execution fields on a preview item


def test_batch_applicability_table_execution():
    rejects(b.make_execution_diagnostics, execution_summary=None)
    rejects(b.make_execution_diagnostics, outcome=None)
    rejects(b.make_execution_diagnostics, preview_summary=b.make_preview_summary(total=1))
    rejects(b.make_execution_diagnostics, items=(b.make_item(),))  # no disposition
    rejects(b.make_execution_diagnostics, items=(b.make_execution_item(retry_origin=RetryKind.RESUME),))
    rejects(b.make_execution_diagnostics, items=(b.make_execution_item(preflight=b.make_preflight()),))


def test_batch_summary_total_equals_len_items():
    rejects(b.make_preview_diagnostics, preview_summary=b.make_preview_summary(total=2))
    rejects(b.make_execution_diagnostics, execution_summary=b.make_execution_summary(total=2))
    rejects(b.make_preview_diagnostics, preview_summary="x")


def test_batch_summaries_are_validated_p4_c8_values():
    from fc2_organizer.orchestration import PreviewSummary

    bad_counts = dataclasses.replace  # noqa: F841 (documentation of intent)
    summary = b.make_preview_summary(total=1)
    object.__setattr__(summary, "ready", 5)  # tampered upstream value carried as-is
    rejects(b.make_preview_diagnostics, preview_summary=summary)

    class SummarySub(PreviewSummary):
        pass

    clean = b.make_preview_summary(total=1)
    rejects(b.make_preview_diagnostics, preview_summary=SummarySub(
        total=clean.total, ready=clean.ready, blocked=clean.blocked, unprepared=clean.unprepared,
        warned=clean.warned, stage_counts=clean.stage_counts))


def test_batch_execution_summary_identities_are_enforced():
    summary = b.make_execution_summary(total=1)
    object.__setattr__(summary, "success", 0)
    rejects(b.make_execution_diagnostics, execution_summary=summary)
    broken = b.make_execution_summary(total=1)
    object.__setattr__(broken, "stage_counts", tuple(reversed(broken.stage_counts)))
    rejects(b.make_execution_diagnostics, execution_summary=broken)


def test_batch_items_index_rules():
    rejects(b.make_preview_diagnostics, items=(b.make_item(index=1),))  # MAIN must start at 0
    rejects(b.make_preview_diagnostics, batch_size=2, preview_summary=b.make_preview_summary(total=1))
    rejects(b.make_preview_diagnostics, batch_size=2, items=(b.make_item(index=1), b.make_item(index=0)),
            preview_summary=b.make_preview_summary(total=2))
    retry = dict(shape=ResultShape.RETRY, generation=1, retry_scope=(RetryKind.RESUME,))

    def retry_item(index):
        return b.make_item(index=index, generation=1, retry_origin=RetryKind.RESUME)

    ok = b.make_preview_diagnostics(batch_size=5, items=(retry_item(1), retry_item(4)),
                                    preview_summary=b.make_preview_summary(total=2), **retry)
    assert [i.index for i in ok.items] == [1, 4]
    rejects(b.make_preview_diagnostics, batch_size=4, items=(retry_item(1), retry_item(4)),
            preview_summary=b.make_preview_summary(total=2), **retry)
    rejects(b.make_preview_diagnostics, batch_size=5, items=(retry_item(4), retry_item(1)),
            preview_summary=b.make_preview_summary(total=2), **retry)
    rejects(b.make_preview_diagnostics, batch_size=5, items=[retry_item(1)],
            preview_summary=b.make_preview_summary(total=1), **retry)
    rejects(b.make_preview_diagnostics, batch_size=3, items=(retry_item(0), retry_item(1), retry_item(2),
                                                              retry_item(3)),
            preview_summary=b.make_preview_summary(total=4), **retry)


def test_batch_size_bounds():
    rejects(b.make_preview_diagnostics, batch_size=2001, items=())
    rejects(b.make_preview_diagnostics, batch_size=-1)
    rejects(b.make_preview_diagnostics, batch_size=True)
    empty = b.make_preview_diagnostics(count=0)
    assert empty.items == () and empty.batch_size == 0
    assert b.make_execution_diagnostics(count=0).items == ()


def test_batch_item_generation_rules():
    rejects(b.make_preview_diagnostics, items=(b.make_item(generation=1),))
    rejects(b.make_execution_diagnostics, items=(b.make_execution_item(generation=1),))
    merged_kwargs = dict(shape=ResultShape.MERGED, generation=2)
    ok = b.make_execution_diagnostics(items=(b.make_execution_item(generation=2),), **merged_kwargs)
    assert ok.items[0].generation == 2
    rejects(b.make_execution_diagnostics, items=(b.make_execution_item(generation=3),), **merged_kwargs)
    rejects(b.make_execution_diagnostics, items=(b.make_execution_item(generation=1), ), shape=ResultShape.RETRY,
            generation=2, retry_scope=(RetryKind.RESUME,), batch_size=1)


def test_path_policy_none_requires_every_path_derived_text_to_be_none():
    rejects(b.make_preview_diagnostics, items=(b.make_item(source_name="movie.mp4"),))
    rejects(b.make_preview_diagnostics, items=(b.make_item(target_directory_name="d"),))
    rejects(b.make_preview_diagnostics, items=(b.make_item(target_media_name="m.mp4"),))
    name = ".fc2tmp-" + "0" * 32 + ".part"
    leftover = b.make_execution(leftover_temporary_count=1, leftover_temporaries=(b.make_leftover(name=name),))
    rejects(b.make_execution_diagnostics, items=(b.make_execution_item(execution=leftover),))


def test_path_policy_basename_requires_the_source_and_leftover_names():
    ok = b.make_preview_diagnostics(path_policy=PathPolicy.BASENAME,
                                    items=(b.make_item(source_name="movie.mp4", target_directory_name="FC2-1",
                                                       target_media_name="FC2-1.mp4"),))
    assert ok.items[0].source_name == "movie.mp4"
    rejects(b.make_preview_diagnostics, path_policy=PathPolicy.BASENAME)  # source_name None
    leftover = b.make_execution(leftover_temporary_count=1, leftover_temporaries=(b.make_leftover(name=None),))
    rejects(b.make_execution_diagnostics, path_policy=PathPolicy.BASENAME,
            items=(b.make_execution_item(source_name="movie.mp4", execution=leftover),))
    name = ".fc2tmp-" + "0" * 32 + ".part"
    named = b.make_execution(leftover_temporary_count=1, leftover_temporaries=(b.make_leftover(name=name),))
    assert b.make_execution_diagnostics(path_policy=PathPolicy.BASENAME,
                                        items=(b.make_execution_item(source_name="movie.mp4", execution=named),))


def test_timing_policy_controls_whether_timings_are_present():
    timed_metadata = b.make_metadata(
        elapsed_ms=10, sources=(b.make_source(attempts=(b.make_attempt(elapsed_ms=5, backoff_before_ms=0),)),))
    ok = b.make_preview_diagnostics(timing_policy=TimingPolicy.INCLUDE, items=(b.make_item(metadata=timed_metadata),))
    assert ok.timing_policy is TimingPolicy.INCLUDE
    rejects(b.make_preview_diagnostics, items=(b.make_item(metadata=timed_metadata),))  # OMIT with timings
    rejects(b.make_preview_diagnostics, timing_policy=TimingPolicy.INCLUDE)  # INCLUDE without timings
    only_attempts = b.make_metadata(
        elapsed_ms=10, sources=(b.make_source(attempts=(b.make_attempt(),)),))
    rejects(b.make_preview_diagnostics, timing_policy=TimingPolicy.INCLUDE, items=(b.make_item(metadata=only_attempts),))
    no_metadata = b.make_item(metadata=None)
    assert b.make_preview_diagnostics(timing_policy=TimingPolicy.INCLUDE, items=(no_metadata,)).items == (no_metadata,)


def test_batch_items_must_be_exact_item_diagnostics():
    rejects(b.make_preview_diagnostics, items=("x",))
    rejects(b.make_preview_diagnostics, items=[b.make_item()])

    class ItemSub(ItemDiagnostics):
        pass

    rejects(b.make_preview_diagnostics, items=(_subclass_instance(ItemSub, b.make_item()),))


def test_models_do_not_hold_bytes_or_unsafe_upstream_objects():
    diag = b.make_execution_diagnostics(count=1)
    for item in diag.items:
        assert not any(type(getattr(item, f.name)) in (bytes, bytearray) for f in dataclasses.fields(item))
