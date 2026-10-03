"""Shared builders for the P4-C9 diagnostics tests (construction plan section 4).

S1: factories for *valid* diagnostics models (``make_*``); every factory accepts keyword overrides so a test can
change exactly one field. Later stages extend this module with builders for the (real, public-constructor) P4-C8 /
Phase 3 / P4-C7 inputs of the builders under test. Production code never imports this module. Every production
name is bound at import (collection) time (several contract guards purge ``fc2_*`` from ``sys.modules``).
"""

from __future__ import annotations

from fc2_metadata_core.aggregation import AggregateStatus
from fc2_metadata_core.batch import BatchItemErrorKind, BatchItemStatus
from fc2_metadata_core.models import SourceErrorKind, SourceStatus
from fc2_organizer.diagnostics import (
    BatchDiagnostics,
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
    EffectKind,
    ExecutionFailure,
    ExecutionFailureKind,
    ExecutionStatus,
    ExecutionStep,
    PathRole,
    PreflightBlocker,
    PreflightBlockReason,
    PreflightMode,
    TransferMode,
)
from fc2_organizer.images import ImageFailureKind, ImageRole
from fc2_organizer.materialization import ArtifactKind
from fc2_organizer.orchestration import (
    BatchOutcome,
    ExecutionDisposition,
    ExecutionSummary,
    IssueReason,
    ItemWarning,
    OrchestrationStage,
    PreviewState,
    PreviewSummary,
    RetryKind,
)

NUMBER = "FC2-1234567"


def zero_stage_counts() -> tuple[tuple[OrchestrationStage, int], ...]:
    return tuple((stage, 0) for stage in OrchestrationStage)


def stage_counts_for(*stages: OrchestrationStage) -> tuple[tuple[OrchestrationStage, int], ...]:
    return tuple((stage, sum(1 for s in stages if s is stage)) for stage in OrchestrationStage)


def make_preview_summary(total: int = 0, ready: int | None = None, blocked: int = 0, unprepared: int = 0,
                         warned: int = 0, stages: tuple[OrchestrationStage, ...] = ()) -> PreviewSummary:
    ready = total - blocked - unprepared if ready is None else ready
    return PreviewSummary(total=total, ready=ready, blocked=blocked, unprepared=unprepared, warned=warned,
                          stage_counts=stage_counts_for(*stages))


def make_execution_summary(total: int = 0, success: int | None = None) -> ExecutionSummary:
    """``total`` items that all executed successfully (the simplest valid execution summary)."""
    success = total if success is None else success
    return ExecutionSummary(
        total=total, ready=total, blocked=0, unprepared=0, executed=success, success=success, partial=0, failed=0,
        not_selected=total - success, cancelled=0, rejected=0, aborted=0, retryable=0, deferred=total - success,
        non_retryable=0, stage_counts=zero_stage_counts())


def make_metadata_batch_counts(**overrides) -> MetadataBatchCounts:
    values = dict(generation=0, total=3, success=2, partial=1, failed=0)
    values.update(overrides)
    return MetadataBatchCounts(**values)


def make_issue(**overrides) -> IssueDiagnostics:
    values = dict(stage=OrchestrationStage.METADATA, reason=IssueReason.METADATA_UNAVAILABLE, error_type=None,
                  detail=None)
    values.update(overrides)
    return IssueDiagnostics(**values)


def make_attempt(**overrides) -> SourceAttemptDiagnostics:
    values = dict(sequence=1, status=SourceStatus.SUCCESS, error_kind=None, completed=True, elapsed_ms=None,
                  backoff_before_ms=None)
    values.update(overrides)
    return SourceAttemptDiagnostics(**values)


def make_source(**overrides) -> SourceDiagnostics:
    values = dict(source_id="fc2db_net", status=SourceStatus.SUCCESS, error_kind=None, contributed=True,
                  operational_failure=False, provided_fields=("title",), trace_available=True, attempt_count=1,
                  max_attempts=2, deadline_exceeded=False, deadline_during=None, attempts=(make_attempt(),))
    values.update(overrides)
    return SourceDiagnostics(**values)


def make_metadata(**overrides) -> MetadataDiagnostics:
    values = dict(
        status=BatchItemStatus.SUCCESS, generation=0, error_kind=None, aggregate_status=AggregateStatus.SUCCESS,
        traces_available=True, sources=(make_source(),), disabled_source_ids=("av123",),
        field_provenance=(FieldProvenance(field="title", source_ids=("fc2db_net",)),),
        conflicts=(), elapsed_ms=None)
    values.update(overrides)
    return MetadataDiagnostics(**values)


def make_preflight(**overrides) -> PreflightDiagnostics:
    values = dict(mode=PreflightMode.FRESH, ready=True, transfer_mode=TransferMode.SAME_VOLUME, blockers=(),
                  pending_unit_count=7, completed_unit_count=0, skipped_steps=(),
                  artifact_counts=tuple((kind, 1 if kind is ArtifactKind.NFO else 0) for kind in ArtifactKind))
    values.update(overrides)
    return PreflightDiagnostics(**values)


def make_execution(**overrides) -> ExecutionDiagnostics:
    values = dict(
        status=ExecutionStatus.SUCCESS, mode=PreflightMode.FRESH, transfer_mode=TransferMode.SAME_VOLUME,
        new_effect_count=2,
        effect_counts=tuple((kind, 1 if kind in (EffectKind.MEDIA_PUBLISHED, EffectKind.SOURCE_REMOVED) else 0)
                            for kind in EffectKind),
        artifact_counts=tuple((kind, 0) for kind in ArtifactKind), failure=None, checkpoint_present=False,
        skipped_steps=(), leftover_temporary_count=0, leftover_temporaries=())
    values.update(overrides)
    return ExecutionDiagnostics(**values)


def make_failure(**overrides) -> ExecutionFailure:
    values = dict(step=ExecutionStep.MOVE_MEDIA, kind=ExecutionFailureKind.MEDIA_TRANSFER_FAILED)
    values.update(overrides)
    return ExecutionFailure(**values)


def make_blocker(**overrides) -> PreflightBlocker:
    values = dict(reason=PreflightBlockReason.SOURCE_MISSING, role=PathRole.SOURCE)
    values.update(overrides)
    return PreflightBlocker(**values)


def make_leftover(**overrides) -> LeftoverTemporaryDiagnostics:
    values = dict(directory_role=PathRole.TARGET_DIRECTORY, name=None)
    values.update(overrides)
    return LeftoverTemporaryDiagnostics(**values)


def make_image_group(**overrides) -> ImageFailureGroup:
    values = dict(role=ImageRole.POSTER, kind=ImageFailureKind.TIMEOUT, count=1, http_statuses=())
    values.update(overrides)
    return ImageFailureGroup(**values)


def make_item(**overrides) -> ItemDiagnostics:
    """A valid PREVIEW-kind item (index 0, generation 0, no policy-dependent text)."""
    values = dict(
        index=0, generation=0, canonical_number=NUMBER, source_name=None, source_size=1024,
        target_directory_name=None, target_media_name=None, preview_state=PreviewState.READY, issue=None,
        warnings=(), conflict_with=(), retry_origin=None, disposition=None, retry_kind=None,
        retry_material_retained=None, metadata=make_metadata(), image_failures=(), preflight=make_preflight(),
        execution=None)
    values.update(overrides)
    return ItemDiagnostics(**values)


def make_execution_item(**overrides) -> ItemDiagnostics:
    """A valid EXECUTION-kind item (EXECUTED / SUCCESS)."""
    values = dict(preflight=None, disposition=ExecutionDisposition.EXECUTED, retry_kind=RetryKind.NONE,
                  retry_material_retained=False, execution=make_execution())
    values.update(overrides)
    return make_item(**values)


def _count_of(count: int, overrides: dict) -> int:
    items = overrides.get("items")
    return len(items) if items is not None else count


def make_preview_diagnostics(count: int = 1, **overrides) -> BatchDiagnostics:
    """``count`` default PREVIEW items; ``items`` / ``batch_size`` / the summary total follow an ``items`` override."""
    size = _count_of(count, overrides)
    values = dict(
        kind=DiagnosticsKind.PREVIEW, shape=ResultShape.MAIN, generation=0, batch_size=size, retry_scope=None,
        path_policy=PathPolicy.NONE, timing_policy=TimingPolicy.OMIT, metadata_batch=make_metadata_batch_counts(),
        preview_summary=make_preview_summary(total=size), execution_summary=None, outcome=None,
        items=tuple(make_item(index=i) for i in range(size)))
    values.update(overrides)
    return BatchDiagnostics(**values)


def make_execution_diagnostics(count: int = 1, **overrides) -> BatchDiagnostics:
    size = _count_of(count, overrides)
    values = dict(
        kind=DiagnosticsKind.EXECUTION, shape=ResultShape.MAIN, generation=0, batch_size=size, retry_scope=None,
        path_policy=PathPolicy.NONE, timing_policy=TimingPolicy.OMIT, metadata_batch=make_metadata_batch_counts(),
        preview_summary=None, execution_summary=make_execution_summary(total=size), outcome=BatchOutcome.SUCCESS,
        items=tuple(make_execution_item(index=i) for i in range(size)))
    values.update(overrides)
    return BatchDiagnostics(**values)


# =========================================================================== S2: real (public-constructor) inputs
#
# The P4-C8 model builders of ``tests/unit/orchestration/_helpers.py`` are read-only reused (contract section 27.2:
# tests may use existing test helpers; they are never modified). Everything here is built through public
# constructors / the public planner -- never forged.

import dataclasses  # noqa: E402

from fc2_metadata_core.aggregation import (  # noqa: E402
    AggregationResult,
    FieldConflict,
    SourceAttempt,
    SourceExecutionTrace,
)
from fc2_metadata_core.batch import BatchItemResult, BatchResult  # noqa: E402
from fc2_metadata_core.models import NormalizedMetadata, SourceResult  # noqa: E402
from orchestration._fakes import build_metadata  # noqa: E402
from orchestration._helpers import (  # noqa: E402,F401
    LIBRARY,
    Corpus,
    Film,
    Lineage,
    fake_checkpoint,
    fake_execution,
    fake_preflight,
    image_failure,
    manifest_for,
    media_item,
    metadata_batch,
    metadata_item,
    new_id,
    plan_for,
    run,
)

SRC_A = "src_a"
SRC_B = "src_b"


def poke(obj, **changes):
    """Rewrite fields of a frozen dataclass *in place* behind its constructor's back (the tamper device of the
    P4-C8 tests: ``object.__setattr__``). Returns ``obj``."""
    for name, value in changes.items():
        object.__setattr__(obj, name, value)
    return obj


def make_metadata_core(number: str = NUMBER, title: str = "Example Title", **fields) -> NormalizedMetadata:
    return NormalizedMetadata(number=number, title=title, **fields)


def make_source_result(source_id: str = SRC_A, status: SourceStatus = SourceStatus.SUCCESS, *, number: str = NUMBER,
                       title: str = "Example Title", error_kind: SourceErrorKind | None = None,
                       elapsed_ms: float = 3.0, with_metadata: bool | None = None) -> SourceResult:
    if status is SourceStatus.SUCCESS:
        return SourceResult(source_id=source_id, status=status, metadata=make_metadata_core(number, title),
                            elapsed_ms=elapsed_ms)
    kind = error_kind or {
        SourceStatus.NOT_FOUND: SourceErrorKind.NOT_FOUND, SourceStatus.BLOCKED: SourceErrorKind.BLOCKED,
        SourceStatus.RATE_LIMITED: SourceErrorKind.RATE_LIMITED,
        SourceStatus.NETWORK_ERROR: SourceErrorKind.TIMEOUT, SourceStatus.PARSE_ERROR: SourceErrorKind.PARSE_ERROR,
        SourceStatus.INVALID_RESPONSE: SourceErrorKind.INVALID_RESPONSE}[status]
    return SourceResult(source_id=source_id, status=status, metadata=None, elapsed_ms=elapsed_ms,
                        error_kind=kind, error_detail="C9CANARY-detail")


def make_attempt_in(sequence: int = 1, status: SourceStatus = SourceStatus.SUCCESS, *, kind=None, elapsed: float = 5.0,
                    backoff: float = 0.0, completed: bool = True) -> SourceAttempt:
    return SourceAttempt(sequence=sequence, status=status, error_kind=kind, elapsed_ms=elapsed, completed=completed,
                         backoff_before_seconds=backoff)


def make_trace(result: SourceResult, attempts: tuple[SourceAttempt, ...] | None = None, *, max_attempts: int = 2,
               deadline_exceeded: bool = False, deadline_during: str | None = None) -> SourceExecutionTrace:
    if attempts is None:
        attempts = (make_attempt_in(1, result.status, kind=result.error_kind),)
    return SourceExecutionTrace(source_id=result.source_id, attempts=attempts, final_result=result,
                                max_attempts=max_attempts, deadline_exceeded=deadline_exceeded,
                                deadline_during=deadline_during)


def make_full_aggregation(number: str = NUMBER, *, field_sources: dict | None = None, elapsed: float = 11.5,
                          with_conflict: bool = True) -> AggregationResult:
    """PARTIAL aggregate: src_a SUCCESS (one attempt), src_b NETWORK_ERROR / TIMEOUT (two attempts, one retry),
    one disabled source ``av123``, one title conflict. ``field_sources`` is the *published* provenance mapping."""
    good = make_source_result(SRC_A, SourceStatus.SUCCESS, number=number)
    bad = make_source_result(SRC_B, SourceStatus.NETWORK_ERROR)
    retried = (make_attempt_in(1, SourceStatus.NETWORK_ERROR, kind=SourceErrorKind.TIMEOUT, elapsed=20.0),
               make_attempt_in(2, SourceStatus.NETWORK_ERROR, kind=SourceErrorKind.TIMEOUT, elapsed=25.0,
                               backoff=0.5))
    traces = (make_trace(good), make_trace(bad, retried))
    if field_sources is None:
        field_sources = {"number": (SRC_A,), "title": (SRC_A,)}
    metadata = NormalizedMetadata(number=number, title="Example Title", field_sources=field_sources)
    conflicts = ()
    if with_conflict:
        conflicts = (FieldConflict(field="title", selected_source_id=SRC_A, selected_value="Example Title",
                                   alternatives=(("src_c", "Other Title"),)),)
    # a conflict may only name contributing sources: add the third source (SUCCESS, other title)
    results = (good, bad)
    contributing = (SRC_A,)
    if with_conflict:
        third = make_source_result("src_c", SourceStatus.SUCCESS, number=number, title="Other Title")
        results = (good, bad, third)
        traces = traces + (make_trace(third),)
        contributing = (SRC_A, "src_c")
    return AggregationResult(number=number, status=AggregateStatus.PARTIAL, metadata=metadata,
                             source_results=results, contributing_source_ids=contributing, conflicts=conflicts,
                             disabled_source_ids=("av123",), elapsed_ms=elapsed, source_execution_traces=traces)


def make_full_batch_item(index: int, number: str = NUMBER, **kwargs) -> BatchItemResult:
    aggregation = make_full_aggregation(number, **kwargs)
    return BatchItemResult(index=index, number=number, status=BatchItemStatus.PARTIAL,
                           aggregation_result=aggregation, generation=0, elapsed_ms=42.0)


def full_lineage(size: int = 2) -> Lineage:
    """A ``Lineage`` whose metadata items are the rich ``make_full_batch_item`` ones (traces, conflict, disabled)."""
    lineage = Lineage(size)
    items = tuple(make_full_batch_item(i, lineage.numbers[i]) for i in range(size))
    lineage.metadata = metadata_batch(items)
    return lineage


# --------------------------------------------------------------------------- generic test devices


def fingerprint(obj, _seen=None):
    """A deep, comparable structural fingerprint of an input graph (types, field values, container shapes); used
    to prove an operation left the input object graph field-by-field unchanged. Identity of nested objects is
    covered by ``identities``."""
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return (type(obj).__name__, tuple((f.name, fingerprint(getattr(obj, f.name))) for f in dataclasses.fields(obj)))
    if isinstance(obj, (tuple, list)):
        return (type(obj).__name__, tuple(fingerprint(item) for item in obj))
    if isinstance(obj, (frozenset, set)):
        return (type(obj).__name__, frozenset(fingerprint(item) for item in obj))
    if type(obj).__name__ == "mappingproxy":
        return ("mappingproxy", tuple((fingerprint(k), fingerprint(v)) for k, v in obj.items()))
    return (type(obj).__name__, obj if isinstance(obj, (str, int, float, bool, bytes, type(None))) else repr(obj))


def identities(obj, found=None):
    """The ``id`` of every dataclass node reachable from ``obj`` (nested objects must keep their identity)."""
    found = [] if found is None else found
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        found.append(id(obj))
        for f in dataclasses.fields(obj):
            identities(getattr(obj, f.name), found)
    elif isinstance(obj, (tuple, list)):
        for item in obj:
            identities(item, found)
    return found


HITS: dict[str, int] = {}


def reset_hits() -> None:
    HITS.clear()
    for name in ("hash", "eq", "ne", "lt", "bool", "len", "repr", "str", "format", "iter", "getattribute", "call"):
        HITS[name] = 0


def total_hits() -> int:
    return sum(HITS.values())


reset_hits()


class EvilStr(str):
    """A ``str`` subclass whose every dispatch-sensitive hook counts a hit (the R2-01 hostile key / id). The
    upstream public constructors accept it (``isinstance(x, str)``) and may themselves run these hooks -- tests
    call ``reset_hits()`` after the upstream construction and before calling P4-C9."""

    def __hash__(self):
        HITS["hash"] += 1
        return str.__hash__(self)

    def __eq__(self, other):
        HITS["eq"] += 1
        return str.__eq__(self, other)

    def __ne__(self, other):
        HITS["ne"] += 1
        return str.__ne__(self, other)

    def __lt__(self, other):
        HITS["lt"] += 1
        return str.__lt__(self, other)

    def __bool__(self):
        HITS["bool"] += 1
        return True

    def __len__(self):
        HITS["len"] += 1
        return str.__len__(self)

    def __repr__(self):
        HITS["repr"] += 1
        return str.__repr__(self)

    def __str__(self):
        HITS["str"] += 1
        return str.__str__(self)

    def __format__(self, spec):
        HITS["format"] += 1
        return str.__format__(self, spec)

    def __iter__(self):
        HITS["iter"] += 1
        return str.__iter__(self)

    def __getattribute__(self, name):
        HITS["getattribute"] += 1
        return str.__getattribute__(self, name)


class CollidingStr(EvilStr):
    """Hash-collides with a given exact ``str`` but never compares equal to it (both keys then coexist)."""

    target = "title"

    def __hash__(self):
        HITS["hash"] += 1
        return hash(type(self).target)

    def __eq__(self, other):
        HITS["eq"] += 1
        return False


def poke_subclass(subclass, base):
    """An instance of ``subclass`` carrying ``base``'s field values (built without running any ``__post_init__``)."""
    clone = object.__new__(subclass)
    for field in dataclasses.fields(base):
        object.__setattr__(clone, field.name, getattr(base, field.name))
    return clone


def first_item(model):
    return model.items[0]


def placeholder_items(count: int):
    """``count`` plain ``object()`` placeholders (never touched when the limit check fires first)."""
    return [object() for _ in range(count)]


# --------------------------------------------------------------------------- P4-C7 effects (execution results)

from fc2_organizer.execution import (  # noqa: E402
    CompletedEffect,
    EntryIdentity,
    EntryType,
    ExecutionResult,
    LeftoverTemporary,
)

_DIR_IDENTITY = EntryIdentity(device=1, inode=10, entry_type=EntryType.DIRECTORY, size=None, mtime_ns=None)
_FILE_IDENTITY = EntryIdentity(device=1, inode=11, entry_type=EntryType.FILE, size=100, mtime_ns=5)
_SHA = "0" * 64


def make_effect(kind: EffectKind, artifact_kind: ArtifactKind | None = None, ordinal: int | None = None,
                path: str = "C9CANARYDIR/x") -> CompletedEffect:
    """A model-valid ``CompletedEffect`` of ``kind`` (``path`` carries a canary: it must never be output)."""
    roles = {EffectKind.SOURCE_REMOVED: PathRole.SOURCE, EffectKind.MEDIA_PUBLISHED: PathRole.TARGET_MEDIA,
             EffectKind.TARGET_DIRECTORY_CREATED: PathRole.TARGET_DIRECTORY,
             EffectKind.EXTRAFANART_DIRECTORY_CREATED: PathRole.EXTRAFANART_DIRECTORY}
    if kind is EffectKind.ARTIFACT_PUBLISHED:
        role = {ArtifactKind.NFO: PathRole.NFO, ArtifactKind.POSTER: PathRole.POSTER,
                ArtifactKind.FANART: PathRole.FANART, ArtifactKind.THUMB: PathRole.THUMB,
                ArtifactKind.EXTRAFANART: PathRole.EXTRAFANART_FILE}[artifact_kind]
        return CompletedEffect(kind=kind, role=role, path=path, identity=_FILE_IDENTITY, size=10, sha256=_SHA,
                               artifact_kind=artifact_kind, ordinal=ordinal)
    if kind is EffectKind.SOURCE_REMOVED:
        return CompletedEffect(kind=kind, role=roles[kind], path=path, identity=None, size=None, sha256=None,
                               artifact_kind=None, ordinal=None)
    if kind is EffectKind.MEDIA_PUBLISHED:
        return CompletedEffect(kind=kind, role=roles[kind], path=path, identity=_FILE_IDENTITY, size=100,
                               sha256=_SHA, artifact_kind=None, ordinal=None)
    return CompletedEffect(kind=kind, role=roles[kind], path=path, identity=_DIR_IDENTITY, size=None, sha256=None,
                           artifact_kind=None, ordinal=None)


def rich_execution(plan, status: ExecutionStatus = ExecutionStatus.SUCCESS, *, leftovers: int = 0,
                   failure_kind: ExecutionFailureKind = ExecutionFailureKind.MEDIA_TRANSFER_FAILED,
                   new_effects: int = 3, skipped: tuple[ExecutionStep, ...] = ()) -> ExecutionResult:
    effects = (make_effect(EffectKind.TARGET_DIRECTORY_CREATED), make_effect(EffectKind.MEDIA_PUBLISHED),
               make_effect(EffectKind.SOURCE_REMOVED), make_effect(EffectKind.ARTIFACT_PUBLISHED, ArtifactKind.NFO),
               make_effect(EffectKind.ARTIFACT_PUBLISHED, ArtifactKind.POSTER),
               make_effect(EffectKind.EXTRAFANART_DIRECTORY_CREATED),
               make_effect(EffectKind.ARTIFACT_PUBLISHED, ArtifactKind.EXTRAFANART, 1),
               make_effect(EffectKind.ARTIFACT_PUBLISHED, ArtifactKind.EXTRAFANART, 2))
    temporaries = tuple(LeftoverTemporary(PathRole.TARGET_DIRECTORY, f".fc2tmp-{new_id()}.part")
                        for _ in range(leftovers))
    failure = None if status is ExecutionStatus.SUCCESS else ExecutionFailure(
        step=ExecutionStep.MOVE_MEDIA, kind=failure_kind, errno=13)
    return ExecutionResult(
        status=status, preflight_id=new_id(), mode=PreflightMode.FRESH, transfer_mode=TransferMode.SAME_VOLUME,
        completed_effects=() if status is ExecutionStatus.FAILED else effects, new_effect_count=(
            0 if status is ExecutionStatus.FAILED else new_effects), failure=failure,
        checkpoint=fake_checkpoint(plan) if status is ExecutionStatus.PARTIAL else None,
        leftover_temporaries=temporaries, media_sha256=_SHA, skipped_steps=skipped)


# --------------------------------------------------------------------------- flexible aggregation builder

from fc2_metadata_core.aggregation import OPERATIONAL_FAILURE_STATUSES  # noqa: E402


def make_aggregation(results, *, traces=(), disabled=(), conflicts=(), field_sources=None, number: str = NUMBER,
                     elapsed: float = 1.0, status: AggregateStatus | None = None,
                     metadata: NormalizedMetadata | None = None) -> AggregationResult:
    """An ``AggregationResult`` over ``results`` built through the public constructor; the status, the
    contributing ids and the (published) provenance mapping follow the Phase 3 rules unless overridden."""
    successful = tuple(r.source_id for r in results if r.status is SourceStatus.SUCCESS)
    operational = any(r.status in OPERATIONAL_FAILURE_STATUSES for r in results)
    if status is None:
        status = (AggregateStatus.FAILED if not successful
                  else AggregateStatus.PARTIAL if operational else AggregateStatus.SUCCESS)
    if status is AggregateStatus.FAILED:
        return AggregationResult(number=number, status=status, metadata=None, source_results=tuple(results),
                                 contributing_source_ids=(), conflicts=tuple(conflicts),
                                 disabled_source_ids=tuple(disabled), elapsed_ms=elapsed,
                                 source_execution_traces=tuple(traces))
    if metadata is None:
        if field_sources is None:
            field_sources = {"number": successful, "title": successful[:1]}
        metadata = NormalizedMetadata(number=number, title="Example Title", field_sources=field_sources)
    return AggregationResult(number=number, status=status, metadata=metadata, source_results=tuple(results),
                             contributing_source_ids=successful, conflicts=tuple(conflicts),
                             disabled_source_ids=tuple(disabled), elapsed_ms=elapsed,
                             source_execution_traces=tuple(traces))


def batch_item_for(aggregation: AggregationResult, index: int = 0, **kwargs) -> BatchItemResult:
    status = {AggregateStatus.SUCCESS: BatchItemStatus.SUCCESS, AggregateStatus.PARTIAL: BatchItemStatus.PARTIAL,
              AggregateStatus.FAILED: BatchItemStatus.FAILED}[aggregation.status]
    values = dict(index=index, number=aggregation.number, status=status, aggregation_result=aggregation,
                  generation=0, elapsed_ms=7.0)
    values.update(kwargs)
    return BatchItemResult(**values)


def preview_of_metadata(*items: BatchItemResult):
    """A real ``BatchPreview`` whose item ``i`` carries ``items[i]`` as its Phase 3 metadata."""
    lineage = Lineage(len(items))
    lineage.metadata = metadata_batch(tuple(items))
    for position, item in enumerate(items):
        lineage.numbers[position] = item.number
    lineage.plans = [plan_for(lineage.media[i], lineage.numbers[i]) for i in range(len(items))]
    return lineage.preview([lineage.preview_item(i) for i in range(len(items))])


# --------------------------------------------------------------------------- hostile-input devices
# (contract sections 9.0, 9.10, 9.11, 28.1): every hook of every hostile object counts a hit in ``HITS``; a P4-C9
# builder is correct only if it rejects the hostile graph *without* running any of them. The sentinel counters are
# reset after the whole input graph -- including every upstream public construction -- exists, and read after the
# call. Used by the tamper / malicious-subclass / dispatch-safety / retry-material tests.

from fc2_organizer.diagnostics import (  # noqa: E402
    DiagnosticsIntegrityError,
    build_execution_diagnostics,
    build_preview_diagnostics,
)
from fc2_organizer.execution import ExecutionStatus as X  # noqa: E402
from fc2_organizer.orchestration import ExecutionDisposition as D, ItemWarning as W  # noqa: E402


def count(name):
    HITS[name] += 1


class Hostile:
    """A plain object whose every dispatch hook counts a hit (stands in for an enum / model / scalar element)."""

    def __hash__(self):
        count("hash")
        return 1

    def __eq__(self, other):
        count("eq")
        return True

    def __ne__(self, other):
        count("ne")
        return False

    def __lt__(self, other):
        count("lt")
        return True

    def __bool__(self):
        count("bool")
        return True

    def __len__(self):
        count("len")
        return 1

    def __repr__(self):
        count("repr")
        return "Hostile"

    def __str__(self):
        count("str")
        return "Hostile"

    def __format__(self, spec):
        count("format")
        return "Hostile"

    def __iter__(self):
        count("iter")
        return iter(())

    def __getattribute__(self, name):
        count("getattribute")
        return object.__getattribute__(self, name)


def hook_namespace():
    """Class-body namespace overriding every dispatch hook of a *model* subclass with a counting one."""
    def make(name, result):
        def hook(self, *args, **kwargs):
            count(name)
            return result
        return hook

    return {
        "__hash__": make("hash", 1), "__eq__": make("eq", True), "__ne__": make("ne", False),
        "__lt__": make("lt", True), "__bool__": make("bool", True), "__len__": make("len", 1),
        "__repr__": make("repr", "Hostile"), "__str__": make("str", "Hostile"),
        "__format__": make("format", "Hostile"),
        "__getattribute__": lambda self, name: (count("getattribute"), object.__getattribute__(self, name))[1],
    }


_SUBCLASSES: dict[type, type] = {}


def hostile_subclass(base: type) -> type:
    if base not in _SUBCLASSES:
        _SUBCLASSES[base] = type("Hostile" + base.__name__, (base,), hook_namespace())
    return _SUBCLASSES[base]


def hostile_instance(original):
    """An instance of a hostile subclass of ``type(original)`` carrying ``original``'s field values."""
    subclass = hostile_subclass(type(original))
    clone = object.__new__(subclass)
    for field in dataclasses.fields(type(original)):
        object.__setattr__(clone, field.name, object.__getattribute__(original, field.name))
    return clone


class HostileInt(int):
    def __hash__(self):
        count("hash")
        return int.__hash__(self)

    def __eq__(self, other):
        count("eq")
        return int.__eq__(self, other)

    def __lt__(self, other):
        count("lt")
        return int.__lt__(self, other)

    def __bool__(self):
        count("bool")
        return True

    def __repr__(self):
        count("repr")
        return int.__repr__(self)


class HostileTuple(tuple):
    """An exact-type violation for every tuple-typed field; its hooks count."""

    def __iter__(self):
        count("iter")
        return tuple.__iter__(self)

    def __len__(self):
        count("len")
        return tuple.__len__(self)

    def __eq__(self, other):
        count("eq")
        return tuple.__eq__(self, other)

    def __hash__(self):
        count("hash")
        return tuple.__hash__(self)

    def __bool__(self):
        count("bool")
        return True

    def __getitem__(self, index):
        count("getattribute")
        return tuple.__getitem__(self, index)

    def __contains__(self, value):
        count("eq")
        return tuple.__contains__(self, value)


class HostileFrozenSet(frozenset):
    def __iter__(self):
        count("iter")
        return frozenset.__iter__(self)

    def __hash__(self):
        count("hash")
        return frozenset.__hash__(self)

    def __contains__(self, value):
        count("eq")
        return frozenset.__contains__(self, value)

    def __len__(self):
        count("len")
        return frozenset.__len__(self)


class HostileBytes(bytes):
    def __len__(self):
        count("len")
        return bytes.__len__(self)

    def __hash__(self):
        count("hash")
        return bytes.__hash__(self)

    def __eq__(self, other):
        count("eq")
        return bytes.__eq__(self, other)


# --------------------------------------------------------------------------- graph factories


def preview_graph():
    lineage = full_lineage(2)
    return lineage.preview([lineage.preview_item(i) for i in range(2)])


def execution_graph():
    """Eight execution items covering EXECUTED (SUCCESS / PARTIAL with material, checkpoint, leftover / FAILED),
    NOT_SELECTED / CANCELLED with material, REJECTED / ABORTED and a blocked NOT_READY with material."""
    from fc2_organizer.orchestration import IssueReason as R, PreviewState as S

    lineage = Lineage(8)
    partial = rich_execution(lineage.plans[1], X.PARTIAL, leftovers=1)
    items = [
        lineage.execution_item(0, D.EXECUTED, execution=rich_execution(lineage.plans[0], X.SUCCESS)),
        lineage.execution_item(1, D.EXECUTED, execution=partial, warnings=(W.LEFTOVER_TEMPORARIES,), material=True),
        lineage.execution_item(2, D.EXECUTED, execution=rich_execution(lineage.plans[2], X.FAILED), material=True),
        lineage.execution_item(3, D.NOT_SELECTED, material=True),
        lineage.execution_item(4, D.CANCELLED, material=True),
        lineage.execution_item(5, D.REJECTED, reason=R.EXECUTION_REJECTED, issue_kwargs={"error_type": "E"}),
        lineage.execution_item(6, D.ABORTED, reason=R.EXECUTION_ABORTED, issue_kwargs={"error_type": "E"}),
        lineage.execution_item(7, D.NOT_READY, state=S.BLOCKED, reason=R.PREFLIGHT_BLOCKED, material=True,
                               execution=None),
    ]
    return lineage.result(items)


def baseline_ok(graph, build):
    """The unmutated graph builds: a rejection of the planted graph is attributable to the plant."""
    build(graph)


# --------------------------------------------------------------------------- planting


def resolve(root, path):
    """Walk ``path`` (attribute names / tuple indices) from ``root``; return ``(parent, field_name)`` for the last
    step so a plant can rewrite that field with ``object.__setattr__``."""
    node = root
    for step in path[:-1]:
        node = node[step] if type(step) is int else getattr(node, step)
    return node, path[-1]


def read(root, path):
    parent, name = resolve(root, path)
    return parent[name] if type(name) is int else getattr(parent, name)


def write(root, path, value):
    """Rewrite ``path`` behind the constructors. A tuple element is replaced by rebuilding its (exact) tuple and
    writing it back one level up."""
    if type(path[-1]) is int:
        container_path = path[:-1]
        container = list(read(root, container_path))
        container[path[-1]] = value
        write(root, container_path, tuple(container))
        return
    parent, name = resolve(root, path)
    object.__setattr__(parent, name, value)


def plant_element(root, path, hostile):
    """Put ``hostile`` into the tuple at ``path`` as its first element (inserting into an empty tuple)."""
    original = read(root, path)
    write(root, path, (hostile,) + tuple(original)[1:])


def plant_container(root, path, factory=HostileTuple):
    write(root, path, factory(read(root, path)))


def plant_object(root, path):
    write(root, path, hostile_instance(read(root, path)))


def run_hostile(build, graph):
    """Build ``graph`` after resetting the sentinels; return ``(exception or None, hits)``."""
    reset_hits()
    try:
        build(graph)
    except Exception as exc:  # noqa: BLE001 -- classified by the caller
        return exc, dict(HITS)
    return None, dict(HITS)


def assert_fail_closed(build, graph, label=""):
    exc, hits = run_hostile(build, graph)
    assert exc is not None, "the hostile graph was accepted: %s" % label
    assert type(exc) is DiagnosticsIntegrityError, "%s: %r" % (label, type(exc))
    assert sum(hits.values()) == 0, "%s: hooks ran: %s" % (label, {k: v for k, v in hits.items() if v})


BUILD = {"preview": build_preview_diagnostics, "execution": build_execution_diagnostics}
FACTORY = {"preview": preview_graph, "execution": execution_graph}
