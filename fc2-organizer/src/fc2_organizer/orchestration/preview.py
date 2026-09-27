"""Read-only batch preview composition (P4-C8 contract sections 15-17, 19.2, 19.6, 20.2).

::

    1 busy-first (orchestrator)          2 bounded snapshot + strict element check (recognition)
    3 number recognition + Phase A       4 metadata: await scheduler.run(numbers)   (always called)
    5 per item, index order: plan -> publication -> NFO   (each NFO charged 4 * len at once)
    6 images: min(K, n) workers, index-ordered reservation admission gate
    7 per item, index order: manifest -> preflight_execution (read only)
    8 Phase B conflicts                  9 assemble the BatchPreview

The retention ledger is **call-local** (no module state); its limit is a parameter, so the main preview
passes the lineage budget ``B`` and a later retry preview can pass another limit. An item stops at its
first failing stage. Only ``preview.py`` imports ``acquire_images``; nothing here mutates the filesystem.

Fatal boundary (contract section 20.2): a caller cancellation propagates after every worker is cancelled
and awaited; ``KeyboardInterrupt`` / ``SystemExit`` / ``GeneratorExit`` / any other non-``Exception``
``BaseException`` and a ``CancelledError`` nobody requested stop admission, cancel and await the siblings
and re-raise the **original object**. Workers carry such an object out of the task group in a private,
metadata-free carrier; no exception is ever raised from inside an ``except`` block.
"""

from __future__ import annotations

import asyncio
import secrets
from dataclasses import dataclass, field

from fc2_organizer.images.acquisition import acquire_images
from fc2_organizer.orchestration.errors import OrchestrationResourceLimitError
from fc2_organizer.orchestration.models import (
    BatchPreview,
    IssueReason,
    ItemIssue,
    ItemPreview,
    OrchestrationStage,
    PreviewState,
    ResourceLimitReason,
    type_name,
)
from fc2_organizer.orchestration.recognition import bounded_snapshot, recognize, validate_media_items
from fc2_organizer.orchestration.stages import (
    image_outcome,
    manifest_stage,
    metadata_outcome,
    nfo_stage,
    phase_b_conflicts,
    plan_stage,
    preflight_stage,
    publication_stage,
)

__all__ = ["build_preview"]

_BLOCKING_PHASE_A = frozenset({IssueReason.DUPLICATE_SOURCE_IN_BATCH, IssueReason.DUPLICATE_TARGET_IN_BATCH})


class _Ledger:
    """Call-local retention ledger ``L = charged + reserved`` (contract section 19.6.2); ``L <= limit`` always.
    Private: tests may observe it (read only) by substituting this class."""

    __slots__ = ("limit", "charged", "reserved")

    def __init__(self, limit: int) -> None:
        self.limit = limit
        self.charged = 0
        self.reserved = 0

    def charge(self, amount: int) -> bool:
        """Add ``amount`` to ``charged``; ``False`` if the ledger now exceeds its limit."""
        self.charged += amount
        return self.charged + self.reserved <= self.limit


class _FatalCarrier(Exception):
    """Carries a fatal ``BaseException`` out of an image worker without ``BaseExceptionGroup`` wrapping.
    Metadata-free: it only holds the object, never reads its class name, text or attributes."""

    __slots__ = ("original",)

    def __init__(self, original: BaseException) -> None:
        super().__init__()
        self.original = original


@dataclass
class _Slot:
    """Scratch state of one item while the preview is being composed (never published)."""

    index: int
    media_item: object
    canonical_number: str | None
    metadata_position: int | None = None
    metadata: object = None
    aggregation: object = None
    plan: object = None
    record: object = None
    nfo_text: str | None = None
    images: object = None
    image_failures: tuple = ()
    preflight: object = None
    issue: ItemIssue | None = None
    conflict_with: tuple[int, ...] = ()


@dataclass
class _ImageRun:
    """Run-local state of the image stage: the admission cursor, the gate and the stop flags."""

    targets: list[_Slot]
    reservation: int
    ledger: _Ledger
    gate: asyncio.Condition
    driver: asyncio.Task | None
    cancel_baseline: int
    cursor: int = 0
    stopping: bool = False
    exhausted: bool = False
    results: dict[int, object] = field(default_factory=dict)

    def admission_open(self) -> bool:
        if self.stopping:
            return False
        return self.driver is None or self.driver.cancelling() <= self.cancel_baseline


async def _admit(run: _ImageRun) -> _Slot | None:
    """The serialized, index-ordered admission gate (contract section 19.6.4). Returns the next target once
    ``charged + reserved + R <= limit`` (reserving ``R``), ``None`` when nothing more may start. With no call
    in flight (``reserved == 0``) an unsatisfiable next target exhausts the ledger at once; the gate never
    waits for a ledger that cannot go down."""
    ledger = run.ledger
    async with run.gate:
        while True:
            if not run.admission_open() or run.cursor >= len(run.targets):
                return None
            if ledger.charged + ledger.reserved + run.reservation <= ledger.limit:
                slot = run.targets[run.cursor]
                run.cursor += 1
                ledger.reserved += run.reservation
                return slot
            if ledger.reserved == 0:
                run.exhausted = True
                run.stopping = True
                run.gate.notify_all()
                return None
            await run.gate.wait()


async def _image_worker(run: _ImageRun, image_client, image_policy) -> None:
    while True:
        slot = await _admit(run)
        if slot is None:
            return
        result: object = None
        failure_type: str | None = None
        fatal: BaseException | None = None
        cancelled: BaseException | None = None
        try:
            result = await acquire_images(slot.record, image_client, policy=image_policy)
        except Exception as exc:  # noqa: BLE001 - item isolation: class name only
            failure_type = type_name(exc)
        except asyncio.CancelledError as exc:
            task = asyncio.current_task()
            if task is not None and task.cancelling() > 0:
                cancelled = exc  # a real cancellation request (the caller's, or the group tearing down)
            else:
                fatal = exc  # the client cancelled itself: fatal control flow, never an item failure
        except BaseException as exc:  # KeyboardInterrupt, SystemExit, GeneratorExit, custom
            fatal = exc
        finally:
            run.ledger.reserved -= run.reservation  # released on every path (no await here)
        if cancelled is not None:
            run.stopping = True
            raise cancelled
        if fatal is not None:
            run.stopping = True
            raise _FatalCarrier(fatal)
        outcome = image_outcome(result, failure_type, run.reservation)
        if type(outcome) is not ItemIssue:
            run.ledger.charged += outcome.total_bytes  # reservation becomes the actual bytes (<= R)
        run.results[slot.index] = outcome
        async with run.gate:
            run.gate.notify_all()


async def _image_stage(targets: list[_Slot], image_client, image_policy, workers: int, ledger: _Ledger) -> None:
    """Contract sections 19.2 and 19.6.4: ``min(K, n)`` workers (never one task per item)."""
    if not targets:
        return
    driver = asyncio.current_task()
    run = _ImageRun(targets=targets, reservation=image_policy.max_total_bytes, ledger=ledger,
                    gate=asyncio.Condition(), driver=driver,
                    cancel_baseline=driver.cancelling() if driver is not None else 0)
    group_error: BaseExceptionGroup | None = None
    try:
        async with asyncio.TaskGroup() as group:
            for _ in range(min(workers, len(targets))):
                group.create_task(_image_worker(run, image_client, image_policy))
    except BaseExceptionGroup as error:
        group_error = error
    if group_error is not None:
        carriers = [e for e in group_error.exceptions if type(e) is _FatalCarrier]
        if carriers:
            raise carriers[0].original  # the ORIGINAL fatal object; only one propagates
        raise group_error
    if run.exhausted:
        raise OrchestrationResourceLimitError(ResourceLimitReason.RETAINED_BYTES_LIMIT)
    for slot in targets:
        outcome = run.results[slot.index]
        if type(outcome) is ItemIssue:
            slot.issue = outcome
        else:
            slot.images = outcome
            slot.image_failures = outcome.failures


def _state(slot: _Slot) -> PreviewState:
    if slot.issue is None:
        return PreviewState.READY
    if slot.issue.reason in (IssueReason.PREFLIGHT_BLOCKED, *_BLOCKING_PHASE_A):
        return PreviewState.BLOCKED
    return PreviewState.UNPREPARED


async def build_preview(items: object, *, scheduler, image_client, library_root: str, output_policy,
                        image_policy, image_workers: int, ledger_limit: int) -> BatchPreview:
    """Steps 2-9 of contract section 15.1 (step 1, busy-first, is the orchestrator's). ``ledger_limit`` is
    the retention ledger's limit; the main preview passes the lineage budget ``B`` and records it."""
    snapshot = validate_media_items(bounded_snapshot(items))  # step 2
    slots: list[_Slot] = []
    numbers: list[str] = []
    for recognition in recognize(snapshot):  # step 3
        slot = _Slot(recognition.index, recognition.media_item, recognition.canonical_number)
        if recognition.reason is IssueReason.NUMBER_NOT_RECOGNIZED:
            slot.issue = ItemIssue(OrchestrationStage.NUMBER_RECOGNITION, IssueReason.NUMBER_NOT_RECOGNIZED)
        elif recognition.reason in _BLOCKING_PHASE_A:
            slot.issue = ItemIssue(OrchestrationStage.BATCH_CONFLICT, recognition.reason)
            slot.conflict_with = recognition.conflict_with
        else:
            slot.metadata_position = len(numbers)
            numbers.append(recognition.canonical_number)
        slots.append(slot)

    metadata_batch = await scheduler.run(tuple(numbers))  # step 4 (called even when empty: lineage)
    ledger = _Ledger(ledger_limit)
    for slot in slots:  # step 5
        if slot.metadata_position is None:
            continue
        slot.metadata = metadata_batch.items[slot.metadata_position]
        outcome = metadata_outcome(slot.metadata)
        if type(outcome) is ItemIssue:
            slot.issue = outcome
            continue
        slot.aggregation = outcome
        plan = plan_stage(slot.media_item, slot.canonical_number, outcome, library_root, output_policy)
        if type(plan) is ItemIssue:
            slot.issue = plan
            continue
        slot.plan = plan
        record = publication_stage(plan, outcome)
        if type(record) is ItemIssue:
            slot.issue = record
            continue
        slot.record = record
        nfo_text = nfo_stage(record)
        if type(nfo_text) is ItemIssue:
            slot.issue = nfo_text
            continue
        slot.nfo_text = nfo_text
        if not ledger.charge(4 * len(nfo_text)):  # contract section 19.6.3: before any image request
            raise OrchestrationResourceLimitError(ResourceLimitReason.RETAINED_BYTES_LIMIT)

    targets = [slot for slot in slots if slot.issue is None and slot.nfo_text is not None]
    await _image_stage(targets, image_client, image_policy, image_workers, ledger)  # step 6

    for slot in targets:  # step 7
        if slot.issue is not None:
            continue
        artifacts = manifest_stage(slot.plan, slot.nfo_text, slot.images)
        if type(artifacts) is ItemIssue:
            slot.issue = artifacts
            continue
        preflight = preflight_stage(slot.plan, artifacts)
        if type(preflight) is ItemIssue:
            slot.issue = preflight
            continue
        slot.preflight = preflight
        if preflight.ready is not True:
            slot.issue = ItemIssue(OrchestrationStage.PREFLIGHT, IssueReason.PREFLIGHT_BLOCKED)

    conflicts = phase_b_conflicts([(slot.index, slot.preflight) for slot in slots if slot.preflight is not None])
    for index, (reason, conflict_with) in conflicts.items():  # step 8 (overrides READY / PREFLIGHT_BLOCKED)
        slot = slots[index]
        slot.issue = ItemIssue(OrchestrationStage.BATCH_CONFLICT, reason)
        slot.conflict_with = conflict_with

    items_out = tuple(  # step 9
        ItemPreview(index=slot.index, generation=0, media_item=slot.media_item,
                    canonical_number=slot.canonical_number, metadata_position=slot.metadata_position,
                    metadata=slot.metadata, plan=slot.plan, image_failures=slot.image_failures,
                    preflight=slot.preflight, state=_state(slot), issue=slot.issue,
                    conflict_with=slot.conflict_with, retry_origin=None)
        for slot in slots)
    return BatchPreview(preview_id=secrets.token_hex(16), lineage=metadata_batch.lineage, generation=0,
                        base_result_id=None, retry_scope=None, library_root=library_root,
                        output_policy=output_policy, image_policy=image_policy, batch_size=len(slots),
                        items=items_out, metadata_batch=metadata_batch, retention_budget_bytes=ledger_limit,
                        retry_budget_bytes=None)
