"""Retry subsets, ``preview_retry`` composition and ``merge_retry`` (P4-C8 contract sections 12, 19.6.7, 19.6.10,
24-26).

``build_retry_preview`` runs steps 2-12 of contract section 25.4 (step 1, busy-first, is the orchestrator's):

::

    2  exact complete previous result             3  object-graph integrity re-check (revalidate)
    4  library root / policies / lineage budget    5  scope: None -> every kind but NONE, else exact frozenset
    6  previous not retried yet (query only)       7  R = previous items whose retry_kind is in scope, by index
    7a base_retained / available = B - base_retained; retained material charged first (exact bytes)
    8  METADATA_REFETCH: retry_failed + apply_retry; recovered items re-run the stages from PLANNING
    9  retained material: preflight_execution(plan, artifacts, checkpoint) per the section 25.1 table
    10 Phase B conflicts inside R                   11 atomic one-time registration of previous.result_id
    12 the retry BatchPreview (generation + 1, base_result_id, scope, B, available)

Registration is the very last step: the retry preview is fully built first, so an ordinary error, a
resource limit, an integrity failure, a fatal ``BaseException`` or a cancellation leaves ``previous``
retryable (``preview_retry`` is read-only and never consumes a checkpoint, P4-C7 section 15.4). The retention
ledger and the image admission gate are ``preview.py``'s own (a call-local ledger whose limit is
``available_retry_budget``); nothing here imports ``acquire_images`` or touches the filesystem. A checkpoint
is carried opaquely: it is handed back to ``preflight_execution`` as the very object the result holds.

``merge_retry`` is pure composition plus one registration (contract section 26): every check, including the
lineage budget (9a) and the merged retained payload (9b) defence in depth, and the construction of the merged
model happen before ``retry.result_id`` is registered, so a failure never consumes the retry result.
Unretried items are the very objects of ``previous`` and no payload is copied. No exception is raised from
inside an ``except`` block.
"""

from __future__ import annotations

import secrets

from fc2_metadata_core.batch import BatchLineage, BatchResult, BatchRetryError, apply_retry
from fc2_organizer.images import ImageAcquisitionPolicy
from fc2_organizer.orchestration._consumption import RESULT_RETRIES, RETRY_MERGES
from fc2_organizer.orchestration.errors import (
    OrchestrationConsumedError,
    OrchestrationContractError,
    OrchestrationInputError,
    OrchestrationIntegrityError,
    OrchestrationResourceLimitError,
    OrchestrationRetryError,
)
from fc2_organizer.orchestration.models import (
    BatchExecutionResult,
    BatchPreview,
    IssueReason,
    ItemExecution,
    ItemIssue,
    ItemPreview,
    OrchestrationStage,
    ResourceLimitReason,
    RetryKind,
    retry_payload_bytes,
    revalidate,
)
from fc2_organizer.orchestration.preview import _image_stage, _Ledger, _Slot, _state
from fc2_organizer.orchestration.stages import (
    manifest_stage,
    metadata_outcome,
    nfo_stage,
    phase_b_conflicts,
    plan_stage,
    preflight_stage,
    publication_stage,
)
from fc2_organizer.planning import OutputPolicy

__all__ = ["build_retry_preview", "merge_retry"]

_EVERY_KIND = frozenset(kind for kind in RetryKind if kind is not RetryKind.NONE)
_MATERIAL_KINDS = frozenset({RetryKind.PREFLIGHT_RECHECK, RetryKind.FRESH_REEXECUTE, RetryKind.RESUME,
                             RetryKind.DEFERRED})
def _same_lineage(a: object, b: object) -> bool:
    return (type(a) is BatchLineage and type(b) is BatchLineage and type(a.token) is str
            and type(b.token) is str and a.token == b.token)


def _resolve_scope(scope: object) -> frozenset[RetryKind] | None:
    """Contract section 25.4 step 5: ``None`` -> every kind but ``NONE``; otherwise an exact ``frozenset`` of
    exact ``RetryKind`` members without ``NONE`` (possibly empty). ``None`` for anything else."""
    if scope is None:
        return _EVERY_KIND
    if type(scope) is not frozenset:
        return None
    for member in scope:
        if type(member) is not RetryKind or member is RetryKind.NONE:
            return None
    return scope


def base_retained(previous: BatchExecutionResult, retried: frozenset[int]) -> int:
    """Contract section 19.6.7: the retained payload of the previous items that stay in the merged result
    (index not in ``R``, holding ``RetryMaterial``). ``R``'s old material is replaced and never counted."""
    return sum(retry_payload_bytes(item.retry_material) for item in previous.items
               if item.index not in retried and item.retry_material is not None)


# --------------------------------------------------------------------------- preview_retry (section 25.4)


def _retained_preflight(item: ItemExecution, kind: RetryKind):
    """Contract section 25.1: the retained plan / artifacts are re-preflighted; the checkpoint is the very
    object the material carries (original preflight checkpoint, or ``execution.checkpoint`` for RESUME), and
    FRESH_REEXECUTE runs without one."""
    material = item.retry_material
    checkpoint = None if kind is RetryKind.FRESH_REEXECUTE else material.checkpoint
    return preflight_stage(material.plan, material.artifacts, checkpoint)


async def _refetch_metadata(slots: list[_Slot], metadata_items: list[ItemExecution], previous, scheduler,
                            image_client, library_root, output_policy, image_policy, image_workers: int,
                            ledger: _Ledger):
    """Contract sections 25.3 / 19.6.3 / 19.6.4 for the METADATA_REFETCH subset: one Phase 3 retry round;
    recovered items re-run PLANNING .. NFO (NFO charged at once) and the image stage of ``preview.py``."""
    retry = await scheduler.retry_failed(previous.metadata_batch)
    expected = tuple(sorted(item.metadata_position for item in metadata_items))
    if retry.indices != expected:
        raise OrchestrationIntegrityError("the metadata retry does not cover exactly the METADATA_REFETCH items")
    merged = None
    try:
        merged = apply_retry(previous.metadata_batch, retry)
    except BatchRetryError:
        pass  # translated below, outside the handler (never chained)
    if merged is None:
        raise OrchestrationIntegrityError("the metadata retry does not belong to the previous metadata batch")
    for slot in slots:
        slot.metadata = merged.items[slot.metadata_position]
        outcome = metadata_outcome(slot.metadata)
        if type(outcome) is ItemIssue:
            slot.issue = outcome  # still FAILED: METADATA / UNPREPARED, retryable again
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
        if not ledger.charge(4 * len(nfo_text)):  # section 19.6.3, before any image request
            raise OrchestrationResourceLimitError(ResourceLimitReason.RETAINED_BYTES_LIMIT)
    targets = [slot for slot in slots if slot.issue is None and slot.nfo_text is not None]
    await _image_stage(targets, image_client, image_policy, image_workers, ledger)
    for slot in targets:
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
    return merged


async def build_retry_preview(previous: object, *, scope: object, scheduler, image_client, library_root: str,
                              output_policy, image_policy, image_workers: int,
                              retention_budget: int) -> BatchPreview:
    """Steps 2-12 of contract section 25.4 (step 1 is the orchestrator's busy-first claim)."""
    if type(previous) is not BatchExecutionResult or not previous.is_complete:  # step 2
        raise OrchestrationInputError("previous must be a complete (main or merged) BatchExecutionResult")
    revalidate(previous)  # step 3 (OrchestrationIntegrityError)
    if (previous.library_root != library_root or previous.output_policy != output_policy  # step 4
            or previous.image_policy != image_policy or previous.retention_budget_bytes != retention_budget):
        raise OrchestrationInputError("previous does not match this orchestrator's configuration")
    resolved = _resolve_scope(scope)  # step 5
    if resolved is None:
        raise OrchestrationInputError("scope must be None or an exact frozenset of RetryKind without NONE")
    if RESULT_RETRIES.is_registered(previous.result_id):  # step 6 (query only; registration is step 11)
        raise OrchestrationConsumedError("this result was already retried")
    retried = [item for item in previous.items if item.retry_kind in resolved]  # step 7, index order
    retried_indices = frozenset(item.index for item in retried)

    budget = previous.retention_budget_bytes  # step 7a: the lineage budget B, never re-read
    available = budget - base_retained(previous, retried_indices)
    if available < 0:
        raise OrchestrationIntegrityError("previous retains more than its lineage budget")
    ledger = _Ledger(available)
    for item in retried:
        if item.retry_kind in _MATERIAL_KINDS and not ledger.charge(retry_payload_bytes(item.retry_material)):
            raise OrchestrationResourceLimitError(ResourceLimitReason.RETAINED_BYTES_LIMIT)

    generation = previous.generation + 1
    slots: dict[int, _Slot] = {}
    for item in retried:
        slot = _Slot(item.index, item.media_item, item.canonical_number, item.metadata_position)
        slots[item.index] = slot
    metadata_items = [item for item in retried if item.retry_kind is RetryKind.METADATA_REFETCH]
    metadata_batch = previous.metadata_batch
    if metadata_items:  # step 8
        metadata_batch = await _refetch_metadata(
            [slots[item.index] for item in metadata_items], metadata_items, previous, scheduler, image_client,
            library_root, output_policy, image_policy, image_workers, ledger)

    for item in retried:  # step 9: the retained-material subset, synchronously, index order
        kind = item.retry_kind
        if kind not in _MATERIAL_KINDS:
            continue
        slot = slots[item.index]
        slot.plan = item.retry_material.plan
        slot.image_failures = item.image_failures
        if slot.metadata_position is not None:
            slot.metadata = metadata_batch.items[slot.metadata_position]
        preflight = _retained_preflight(item, kind)
        if type(preflight) is ItemIssue:
            slot.issue = preflight  # CHECKPOINT_REJECTED / PREFLIGHT_REJECTED -> UNPREPARED
            continue
        slot.preflight = preflight
        if preflight.ready is not True:
            slot.issue = ItemIssue(OrchestrationStage.PREFLIGHT, IssueReason.PREFLIGHT_BLOCKED)

    ordered = [slots[item.index] for item in retried]
    conflicts = phase_b_conflicts([(slot.index, slot.preflight) for slot in ordered if slot.preflight is not None])
    for index, (reason, conflict_with) in conflicts.items():  # step 10, inside R only
        slot = slots[index]
        slot.issue = ItemIssue(OrchestrationStage.BATCH_CONFLICT, reason)
        slot.conflict_with = conflict_with

    kinds = {item.index: item.retry_kind for item in retried}
    items_out = tuple(
        ItemPreview(index=slot.index, generation=generation, media_item=slot.media_item,
                    canonical_number=slot.canonical_number, metadata_position=slot.metadata_position,
                    metadata=slot.metadata, plan=slot.plan, image_failures=slot.image_failures,
                    preflight=slot.preflight, state=_state(slot), issue=slot.issue,
                    conflict_with=slot.conflict_with, retry_origin=kinds[slot.index])
        for slot in ordered)
    retry_preview = BatchPreview(
        preview_id=secrets.token_hex(16), lineage=previous.lineage, generation=generation,
        base_result_id=previous.result_id, retry_scope=resolved, library_root=previous.library_root,
        output_policy=previous.output_policy, image_policy=previous.image_policy, batch_size=previous.batch_size,
        items=items_out, metadata_batch=metadata_batch, retention_budget_bytes=budget,
        retry_budget_bytes=available)
    if not RESULT_RETRIES.register(previous.result_id):  # step 11: last; a lost race discards the product
        raise OrchestrationConsumedError("this result was already retried")
    return retry_preview  # step 12


# --------------------------------------------------------------------------- merge_retry (section 26)


def merge_retry(previous: object, retry: object) -> BatchExecutionResult:
    """Merge a retry-round result into the complete result it was made from (contract section 26).

    Pure composition: no network, no filesystem, no preflight. Checks 1-9b fail closed before the one-time
    registration of ``retry.result_id`` (``OrchestrationRetryError`` for a wrong result / lineage /
    generation / index set / configuration / budget, ``OrchestrationIntegrityError`` for identity and graph
    integrity), so a rejected retry result stays mergeable once corrected. The retry graph is revalidated in
    full (every model invariant re-run) before any of it is trusted: a rewritten graph is an integrity error,
    an intact main / merged result passed as ``retry`` is a retry error. The merged result reuses the very
    ``ItemExecution`` objects of both inputs and copies no payload."""
    if type(previous) is not BatchExecutionResult or not previous.is_complete:  # step 1
        raise OrchestrationRetryError("previous must be a complete (main or merged) BatchExecutionResult")
    revalidate(previous)
    if type(retry) is not BatchExecutionResult:  # step 2
        raise OrchestrationRetryError("retry must be a retry-round BatchExecutionResult")
    revalidate(retry)  # a rewritten retry graph -> OrchestrationIntegrityError (never trusted below)
    if retry.is_complete:  # an intact main / merged result is not a retry round
        raise OrchestrationRetryError("retry must be a retry-round BatchExecutionResult")
    if retry.base_result_id != previous.result_id:  # step 3
        raise OrchestrationRetryError("the retry was not made from this result")
    if not _same_lineage(retry.lineage, previous.lineage):  # step 4
        raise OrchestrationRetryError("the retry belongs to another lineage")
    if retry.generation != previous.generation + 1:  # step 5
        raise OrchestrationRetryError("the retry generation does not follow the previous result (stale / replay)")
    if (type(retry.library_root) is not str or retry.library_root != previous.library_root  # step 6
            or type(retry.output_policy) is not OutputPolicy or retry.output_policy != previous.output_policy
            or type(retry.image_policy) is not ImageAcquisitionPolicy
            or retry.image_policy != previous.image_policy):
        raise OrchestrationRetryError("the retry result has another configuration")
    if retry.batch_size != previous.batch_size:  # the lineage's fixed input size N
        raise OrchestrationRetryError("the retry result has another lineage batch size")
    expected = [item.index for item in previous.items if item.retry_kind in retry.retry_scope]
    if [item.index for item in retry.items] != expected:  # step 7
        raise OrchestrationRetryError("the retry items are not exactly the previous items in its scope")
    for item in retry.items:  # step 8
        original = previous.items[item.index]
        if item.media_item is not original.media_item or item.canonical_number != original.canonical_number:
            raise OrchestrationIntegrityError("a retried item is not the same media item as in previous")
    metadata = retry.metadata_batch  # step 9
    if (type(metadata) is not BatchResult or not _same_lineage(metadata.lineage, previous.lineage)
            or type(metadata.generation) is not int
            or metadata.generation < previous.metadata_batch.generation):
        raise OrchestrationRetryError("the retry metadata batch does not continue the previous one")
    budget = previous.retention_budget_bytes
    kept = base_retained(previous, frozenset(expected))
    if retry.retention_budget_bytes != budget or retry.retry_budget_bytes != budget - kept:  # step 9a
        raise OrchestrationRetryError("the retry result does not carry this lineage's retention budget")
    retry_payload = None
    try:
        retry_payload = retry.retained_retry_payload_bytes
    except OrchestrationContractError:
        pass  # malformed material: translated below, outside the handler
    if type(retry_payload) is not int or kept + retry_payload > budget:  # step 9b (defence in depth)
        raise OrchestrationIntegrityError("the merged result would retain more than the lineage budget")
    replacements = {item.index: item for item in retry.items}
    merged = None
    try:
        merged = BatchExecutionResult(
            result_id=secrets.token_hex(16), preview_id=None, lineage=previous.lineage,
            generation=retry.generation, base_result_id=None, retry_scope=None,
            library_root=previous.library_root, output_policy=previous.output_policy,
            image_policy=previous.image_policy, batch_size=previous.batch_size,
            items=tuple(replacements.get(item.index, item) for item in previous.items),
            metadata_batch=metadata, retention_budget_bytes=budget, retry_budget_bytes=None)
    except OrchestrationContractError:
        pass  # a tampered retry graph: translated below, outside the handler (never chained)
    if merged is None:
        raise OrchestrationIntegrityError("the merged result would violate the result invariants")
    if not RETRY_MERGES.register(retry.result_id):  # step 10: last
        raise OrchestrationConsumedError("this retry result was already merged")
    return merged  # step 11
