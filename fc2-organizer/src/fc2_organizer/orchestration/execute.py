"""Bounded synchronous batch execution (P4-C8 contract sections 17-20, 23, 24, 27, 31).

``execute_preview`` runs steps 2-9 of contract section 18.1 (step 1, busy-first, is the orchestrator's):

::

    2 type(preview) is BatchPreview                    3 object-graph integrity re-check (revalidate)
    4 library root / policies / lineage budget equal   5 cancel: None or an exact CancellationToken
    6 selection: None / exact tuple of strictly increasing READY indices
    7 atomic one-time registration of preview_id        8 bounded execution         9 BatchExecutionResult

Every admitted READY item gets exactly one ``execute_filesystem(item.preflight)`` call with the very
``ExecutionPreflight`` the preview holds (option A, section 17.1): no re-preflight, no metadata / image /
NFO / manifest rebuild. This module is the only one that names ``execute_filesystem`` and the only one that
creates threads; it performs no filesystem access of its own -- all of it is P4-C7's (section 31).

Workers (section 19.3): ``W_eff = min(W, selected READY items)``; ``W_eff <= 1`` runs inline in the calling
thread, otherwise exactly ``W_eff`` non-daemon threads take the next item in index order from a cursor
guarded by one lock, checking ``stopping`` and ``cancel.cancelled`` under that lock before every admission.
Results land in per-index slots, so the output never depends on completion order.

Cancellation (section 27) only stops admission; an item inside ``execute_filesystem`` always runs to its
end. A non-``Exception`` ``BaseException`` (section 20.3) from a worker, or one delivered to the calling
thread while it waits, is recorded once (the first object wins, none of its metadata is read), stops
admission, every thread is joined, and the same object is re-raised -- never an item result, never a
partial ``BatchExecutionResult``. No exception is raised from inside an ``except`` block.
"""

from __future__ import annotations

import secrets
import threading

from fc2_organizer.execution import (
    ArtifactManifestError,
    CheckpointError,
    CheckpointRejectionReason,
    ExecutionInputError,
    ExecutionPreflight,
    ExecutionResult,
    ExecutionStatus,
    ManifestRejectionReason,
    PlanGraphError,
    PlanGraphRejectionReason,
    PreflightIntegrityError,
    PreflightIntegrityReason,
    PreflightNotReadyError,
    execute_filesystem,
)
from fc2_organizer.orchestration._consumption import PREVIEW_EXECUTIONS
from fc2_organizer.orchestration.cancellation import CancellationToken
from fc2_organizer.orchestration.errors import (
    OrchestrationConsumedError,
    OrchestrationInputError,
    OrchestrationIntegrityError,
)
from fc2_organizer.orchestration.models import (
    BatchExecutionResult,
    BatchPreview,
    ExecutionDisposition,
    IssueReason,
    ItemExecution,
    ItemIssue,
    ItemPreview,
    ItemWarning,
    OrchestrationStage,
    PreviewState,
    RetryMaterial,
    reason_detail,
    revalidate,
    type_name,
)

__all__ = ["execute_preview"]

# The six exact types P4-C7 raises before any filesystem access (section 18.2): REJECTED. Exact type only.
_REJECTED_TYPES = (ExecutionInputError, PreflightIntegrityError, PreflightNotReadyError, CheckpointError,
                   PlanGraphError, ArtifactManifestError)
_REJECTED_DETAILS = (PreflightIntegrityReason, CheckpointRejectionReason, PlanGraphRejectionReason,
                     ManifestRejectionReason)
_RETRY_BEARING_STATUS = {ExecutionStatus.FAILED: IssueReason.EXECUTION_FAILED,
                         ExecutionStatus.PARTIAL: IssueReason.EXECUTION_PARTIAL}


class _Outcome:
    """What one admitted item's single ``execute_filesystem`` call produced (never published)."""

    __slots__ = ("disposition", "execution", "issue")

    def __init__(self, disposition: ExecutionDisposition, execution: ExecutionResult | None,
                 issue: ItemIssue | None) -> None:
        self.disposition = disposition
        self.execution = execution
        self.issue = issue


def _raised_outcome(exc: Exception) -> _Outcome:
    """Section 18.2: the six exact pre-filesystem types are REJECTED (``detail`` = their frozen ``.reason``
    when allowed); every other ordinary exception is ABORTED. Only the class name is kept."""
    if any(type(exc) is rejected for rejected in _REJECTED_TYPES):
        detail = reason_detail(exc)
        issue = ItemIssue(OrchestrationStage.EXECUTION, IssueReason.EXECUTION_REJECTED, type_name(exc),
                          detail if type(detail) in _REJECTED_DETAILS else None)
        return _Outcome(ExecutionDisposition.REJECTED, None, issue)
    issue = ItemIssue(OrchestrationStage.EXECUTION, IssueReason.EXECUTION_ABORTED, type_name(exc))
    return _Outcome(ExecutionDisposition.ABORTED, None, issue)


def _returned_outcome(returned: object, preflight: ExecutionPreflight) -> _Outcome:
    if type(returned) is not ExecutionResult:
        issue = ItemIssue(OrchestrationStage.EXECUTION, IssueReason.EXECUTION_ABORTED, type_name(returned))
        return _Outcome(ExecutionDisposition.ABORTED, None, issue)
    if type(returned.preflight_id) is not str or returned.preflight_id != preflight.preflight_id:
        issue = ItemIssue(OrchestrationStage.EXECUTION, IssueReason.EXECUTION_ABORTED, "ExecutionResult")
        return _Outcome(ExecutionDisposition.ABORTED, None, issue)
    reason = _RETRY_BEARING_STATUS.get(returned.status)
    issue = None if reason is None else ItemIssue(OrchestrationStage.EXECUTION, reason, None,
                                                  returned.failure.kind)
    return _Outcome(ExecutionDisposition.EXECUTED, returned, issue)


def _execute_one(item: ItemPreview) -> _Outcome:
    """The single ``execute_filesystem`` call for one admitted item. A non-``Exception`` ``BaseException``
    is not caught here: it is fatal control flow (section 20.3)."""
    try:
        returned = execute_filesystem(item.preflight)
    except Exception as exc:  # noqa: BLE001 - classified by exact type; only the class name is kept
        return _raised_outcome(exc)
    return _returned_outcome(returned, item.preflight)


# --------------------------------------------------------------------------- validation (section 18.1)


def _check_ready_items(preview: BatchPreview) -> bool:
    for item in preview.items:
        if item.state is not PreviewState.READY:
            continue
        preflight, plan = item.preflight, item.plan
        if (type(preflight) is not ExecutionPreflight or preflight.ready is not True or preflight.plan is not plan
                or plan is None or plan.source_path != item.media_item.source_path
                or plan.canonical_number != item.canonical_number):
            return False
    return True


def _selected_items(preview: BatchPreview, selection: object) -> tuple[ItemPreview, ...] | None:
    """Step 6: the admitted-in-principle READY items in index order, or ``None`` for an invalid selection."""
    ready = [item for item in preview.items if item.state is PreviewState.READY]
    if selection is None:
        return tuple(ready)
    if type(selection) is not tuple:
        return None
    by_index = {item.index: item for item in ready}
    chosen: list[ItemPreview] = []
    previous = -1
    for index in selection:
        if type(index) is not int or index <= previous or index not in by_index:
            return None
        chosen.append(by_index[index])
        previous = index
    return tuple(chosen)


# --------------------------------------------------------------------------- bounded execution (section 19.3)


class _Run:
    """Shared state of one threaded execution: the admission cursor, the stop flag, the first fatal object
    and the per-index result slots. Guarded by ``lock`` (never published)."""

    __slots__ = ("lock", "items", "cancel", "cursor", "stopping", "fatal", "outcomes")

    def __init__(self, items: tuple[ItemPreview, ...], cancel: CancellationToken | None) -> None:
        self.lock = threading.Lock()
        self.items = items
        self.cancel = cancel
        self.cursor = 0
        self.stopping = False
        self.fatal: list[BaseException] = []  # at most one element: the first fatal object
        self.outcomes: dict[int, _Outcome] = {}

    def record_fatal(self, fatal: BaseException) -> None:
        """Keep the first fatal object only (identity; no metadata read) and stop admission."""
        with self.lock:
            if not self.fatal:
                self.fatal.append(fatal)
            self.stopping = True

    def admit(self) -> ItemPreview | None:
        with self.lock:
            if self.stopping or (self.cancel is not None and self.cancel.cancelled):
                return None
            if self.cursor >= len(self.items):
                return None
            item = self.items[self.cursor]
            self.cursor += 1
            return item


def _worker(run: _Run) -> None:
    try:
        while True:
            item = run.admit()
            if item is None:
                return
            run.outcomes[item.index] = _execute_one(item)
    except BaseException as fatal:  # fatal control flow (or a defect): recorded, re-raised by the caller
        run.record_fatal(fatal)


def _execute_threaded(items: tuple[ItemPreview, ...], cancel: CancellationToken | None,
                      workers: int) -> dict[int, _Outcome]:
    run = _Run(items, cancel)
    threads = [threading.Thread(target=_worker, args=(run,), daemon=False) for _ in range(workers)]
    started: list[threading.Thread] = []
    try:
        for thread in threads:
            thread.start()
            started.append(thread)
    except BaseException as failure:  # cannot start (or interrupted while starting): stop, drain, re-raise
        run.record_fatal(failure)
    for thread in started:  # every thread is joined before anything propagates (section 20.3)
        joined = False
        while not joined:
            try:
                thread.join()
                joined = True
            except BaseException as fatal:  # KeyboardInterrupt / SystemExit delivered to the caller
                run.record_fatal(fatal)
    if run.fatal:
        raise run.fatal[0]  # the original object
    return run.outcomes


def _execute_inline(items: tuple[ItemPreview, ...], cancel: CancellationToken | None) -> dict[int, _Outcome]:
    outcomes: dict[int, _Outcome] = {}
    for item in items:
        if cancel is not None and cancel.cancelled:
            break
        outcomes[item.index] = _execute_one(item)  # a fatal BaseException propagates as is
    return outcomes


# --------------------------------------------------------------------------- assembly (step 9)


def _material(item: ItemPreview, checkpoint) -> RetryMaterial:
    """The original plan / artifacts of the preview preflight (same objects, no copy)."""
    return RetryMaterial(item.preflight.plan, item.preflight.artifacts, checkpoint)


def _warnings(item: ItemPreview, execution: ExecutionResult | None) -> tuple[ItemWarning, ...]:
    found = set(item.warnings)
    if execution is not None and execution.leftover_temporaries:
        found.add(ItemWarning.LEFTOVER_TEMPORARIES)
    return tuple(warning for warning in ItemWarning if warning in found)


def _item_execution(item: ItemPreview, selected: bool, outcome: _Outcome | None) -> ItemExecution:
    if item.state is not PreviewState.READY:
        disposition, execution, issue = ExecutionDisposition.NOT_READY, None, item.issue
        material = (_material(item, item.preflight.checkpoint)
                    if issue.reason is IssueReason.PREFLIGHT_BLOCKED else None)
    elif not selected:
        disposition, execution, issue = ExecutionDisposition.NOT_SELECTED, None, None
        material = _material(item, item.preflight.checkpoint)
    elif outcome is None:
        disposition, execution, issue = ExecutionDisposition.CANCELLED, None, None
        material = _material(item, item.preflight.checkpoint)
    else:
        disposition, execution, issue = outcome.disposition, outcome.execution, outcome.issue
        material = None
        if execution is not None and execution.status is ExecutionStatus.PARTIAL:
            material = _material(item, execution.checkpoint)
        elif execution is not None and execution.status is ExecutionStatus.FAILED:
            material = _material(item, None)
    return ItemExecution(index=item.index, generation=item.generation, media_item=item.media_item,
                         canonical_number=item.canonical_number, metadata_position=item.metadata_position,
                         metadata=item.metadata, plan=item.plan, image_failures=item.image_failures,
                         conflict_with=item.conflict_with, preview_state=item.state, issue=issue,
                         warnings=_warnings(item, execution), disposition=disposition, execution=execution,
                         retry_material=material)


def execute_preview(preview: object, *, selection: object, cancel: object, library_root: str, output_policy,
                    image_policy, retention_budget: int, workers: int) -> BatchExecutionResult:
    """Steps 2-9 of contract section 18.1 (step 1 is the orchestrator's busy-first claim)."""
    if type(preview) is not BatchPreview:  # step 2
        raise OrchestrationInputError("preview must be an exact BatchPreview")
    revalidate(preview)  # step 3 (OrchestrationIntegrityError)
    if not _check_ready_items(preview):
        raise OrchestrationIntegrityError("a READY preview item does not carry its own ready preflight")
    if (preview.library_root != library_root or preview.output_policy != output_policy  # step 4
            or preview.image_policy != image_policy or preview.retention_budget_bytes != retention_budget):
        raise OrchestrationInputError("preview does not match this orchestrator's configuration")
    if cancel is not None and type(cancel) is not CancellationToken:  # step 5
        raise OrchestrationInputError("cancel must be None or an exact CancellationToken")
    selected = _selected_items(preview, selection)  # step 6
    if selected is None:
        raise OrchestrationInputError("selection must be None or a tuple of strictly increasing READY indices")
    if not PREVIEW_EXECUTIONS.register(preview.preview_id):  # step 7: consumed from here on
        raise OrchestrationConsumedError("this preview was already executed")
    effective = min(workers, len(selected))  # step 8
    if effective <= 1:
        outcomes = _execute_inline(selected, cancel)
    else:
        outcomes = _execute_threaded(selected, cancel, effective)
    chosen = {item.index for item in selected}  # step 9
    items = tuple(_item_execution(item, item.index in chosen, outcomes.get(item.index)) for item in preview.items)
    return BatchExecutionResult(result_id=secrets.token_hex(16), preview_id=preview.preview_id,
                                lineage=preview.lineage, generation=preview.generation,
                                base_result_id=preview.base_result_id, retry_scope=preview.retry_scope,
                                library_root=preview.library_root, output_policy=preview.output_policy,
                                image_policy=preview.image_policy, batch_size=preview.batch_size, items=items,
                                metadata_batch=preview.metadata_batch,
                                retention_budget_bytes=preview.retention_budget_bytes,
                                retry_budget_bytes=preview.retry_budget_bytes)
