"""P4-C8 S4: ``merge_retry(previous, retry)`` (contract section 26, steps 1-11; sections 10.7, 12.3).

Model-level results are hand-built through the ``Lineage`` builders (model-valid, no filesystem); one test
merges a real retry round. Every rejection returns nothing, registers nothing, and the correct retry result
still merges afterwards.

Error families (S4-R1, finding P4-C8-S4-R-01): an intact result that is not a retry round, or an intact retry
round whose relation to ``previous`` is wrong, is an ``OrchestrationRetryError``; a retry graph rewritten with
``object.__setattr__`` so that it violates its own model invariants is an ``OrchestrationIntegrityError``
(``revalidate(retry)`` runs before anything of it is trusted).
"""

from __future__ import annotations

import pytest

from fc2_metadata_core.batch import BatchLineage, BatchResult
from fc2_organizer.execution import ExecutionStatus
from fc2_organizer.images import ImageAcquisitionPolicy
from fc2_organizer.orchestration import (
    BatchExecutionResult,
    BatchOutcome,
    ExecutionDisposition as D,
    ItemWarning,
    OrchestrationConsumedError,
    OrchestrationIntegrityError,
    OrchestrationRetryError,
    RetryKind as K,
    merge_retry,
)
from fc2_organizer.orchestration import _consumption
from fc2_organizer.orchestration.models import revalidate
from fc2_organizer.planning import OutputPolicy

from ._helpers import Corpus, Film, Lineage, fake_checkpoint, media_item, mutation_traps, run, tampered

SCOPE = frozenset({K.DEFERRED, K.FRESH_REEXECUTE})


def _previous(lin: Lineage) -> BatchExecutionResult:
    """index 0 SUCCESS, 1 NOT_SELECTED (DEFERRED), 2 FAILED (FRESH_REEXECUTE), 3 NOT_SELECTED (DEFERRED)."""
    return lin.result([
        lin.execution_item(0, D.EXECUTED, status=ExecutionStatus.SUCCESS),
        lin.execution_item(1, D.NOT_SELECTED, material=True),
        lin.execution_item(2, D.EXECUTED, status=ExecutionStatus.FAILED, material=True),
        lin.execution_item(3, D.NOT_SELECTED, material=True),
    ])


def _retry(lin: Lineage, previous: BatchExecutionResult, indices=(1, 2, 3), *, scope=SCOPE, generation=1,
           statuses=None) -> BatchExecutionResult:
    statuses = statuses or {}
    retained = (ExecutionStatus.FAILED, ExecutionStatus.PARTIAL)
    items = [lin.execution_item(i, D.EXECUTED, status=statuses.get(i, ExecutionStatus.SUCCESS), generation=generation,
                                material=True if statuses.get(i) in retained else ...)
             for i in indices]
    kept = sum(_pay(previous.items[i]) for i in range(previous.batch_size)
               if i not in indices and previous.items[i].retry_material is not None)
    return lin.result(items, generation=generation, base_result_id=previous.result_id, retry_scope=scope,
                      budget=previous.retention_budget_bytes, retry_budget=previous.retention_budget_bytes - kept)


def _pay(item) -> int:
    return sum(len(r.content) for r in item.retry_material.artifacts)


def test_a_legal_merge_replaces_retried_indices_and_keeps_every_other_object():
    lin = Lineage(4)
    previous = _previous(lin)
    retry = _retry(lin, previous, statuses={2: ExecutionStatus.FAILED})
    merged = merge_retry(previous, retry)
    assert type(merged) is BatchExecutionResult and merged.is_complete
    assert merged.items[0] is previous.items[0]  # unretried: the very same object
    assert [merged.items[i] for i in (1, 2, 3)] == list(retry.items)
    assert all(merged.items[i] is retry.items[j] for j, i in enumerate((1, 2, 3)))
    assert merged.generation == 1 and merged.result_id not in (previous.result_id, retry.result_id)
    assert (merged.preview_id, merged.base_result_id, merged.retry_scope, merged.retry_budget_bytes) == (None,) * 4
    assert merged.metadata_batch is retry.metadata_batch and merged.lineage is previous.lineage
    assert merged.retention_budget_bytes == previous.retention_budget_bytes
    assert merged.items[2].retry_material.artifacts is retry.items[1].retry_material.artifacts
    assert merged.outcome is BatchOutcome.PARTIAL and retry.outcome is BatchOutcome.PARTIAL
    assert [i.retry_kind for i in merged.items] == [K.NONE, K.NONE, K.FRESH_REEXECUTE, K.NONE]


def _rejects(previous, bad, error, retry=None):
    outcome = []
    with pytest.raises(error):
        outcome.append(merge_retry(previous, bad))
    assert outcome == []
    if retry is not None:
        assert not _consumption.RETRY_MERGES.is_registered(retry.result_id)


def test_type_and_shape_rejections():
    lin = Lineage(4)
    previous = _previous(lin)
    retry = _retry(lin, previous)
    for bad in (None, "result", object(), previous):  # previous itself is not a retry round
        _rejects(previous, bad, OrchestrationRetryError)
    for bad in (None, retry):  # a retry round is not a complete previous
        with pytest.raises(OrchestrationRetryError):
            merge_retry(bad, retry)
    assert not _consumption.RETRY_MERGES.is_registered(retry.result_id)
    assert merge_retry(previous, retry).is_complete


def test_a_retry_of_another_result_is_rejected_even_with_an_identical_shape():
    lin = Lineage(4)
    previous, twin = _previous(lin), _previous(lin)  # same shape, same lineage, different result_id
    retry_of_twin = _retry(lin, twin)
    _rejects(previous, retry_of_twin, OrchestrationRetryError, retry_of_twin)
    assert merge_retry(twin, retry_of_twin).is_complete


def _sibling(lin: Lineage) -> Lineage:
    """Another lineage (own metadata ledger / token) over the very same media items and plans."""
    other = Lineage(lin.size)
    other.media, other.plans, other.numbers = lin.media, lin.plans, lin.numbers
    return other


def test_lineage_generation_index_and_configuration_mismatches_are_retry_errors():
    """Intact retry rounds whose relation to ``previous`` is wrong (each one passes ``revalidate``)."""
    lin = Lineage(4)
    previous = _previous(lin)
    retry = _retry(lin, previous)
    foreign = _retry(_sibling(lin), previous)  # same media / indices / base id, another lineage
    revalidate(foreign)
    _rejects(previous, foreign, OrchestrationRetryError, foreign)
    for generation in (2, 5):  # replayed / skipped generations, built as intact retry rounds
        later = _retry(lin, previous, generation=generation)
        revalidate(later)
        _rejects(previous, later, OrchestrationRetryError, later)
    for indices in ((1, 2), (2, 3), (0, 1, 2, 3)):  # fewer / other / more
        other = _retry(lin, previous, indices)
        _rejects(previous, other, OrchestrationRetryError, other)
    narrower = _retry(lin, previous, (1, 3), scope=frozenset({K.DEFERRED, K.FRESH_REEXECUTE}))
    _rejects(previous, narrower, OrchestrationRetryError, narrower)  # scope says 1, 2, 3
    for change in (dict(library_root=previous.library_root + "x"),
                   dict(output_policy=OutputPolicy(poster_filename="cover.jpg")),
                   dict(image_policy=ImageAcquisitionPolicy(max_redirects=1))):
        _rejects(previous, tampered(retry, **change), OrchestrationRetryError, retry)
    assert merge_retry(previous, retry).is_complete


def test_metadata_ledger_mismatches_are_retry_errors():
    lin = Lineage(4)
    previous = _previous(lin)
    retry = _retry(lin, previous)
    older = tampered(previous, metadata_batch=BatchResult(items=previous.metadata_batch.items, generation=3,
                                                          lineage=previous.lineage))
    _rejects(older, retry, OrchestrationRetryError, retry)  # retry ledger generation 0 < 3
    assert merge_retry(previous, retry).is_complete


def test_a_retried_item_must_be_the_same_media_item():
    lin = Lineage(4)
    previous = _previous(lin)
    retry = _retry(lin, previous)
    impostor = tampered(retry.items[0], media_item=media_item(1, "FC2-PPV-1000001.mp4"))
    original = previous.items[1].media_item
    assert impostor.media_item == original and impostor.media_item is not original
    _rejects(previous, tampered(retry, items=(impostor, *retry.items[1:])), OrchestrationIntegrityError, retry)
    renamed = tampered(retry.items[0], canonical_number="FC2-7654321")
    _rejects(previous, tampered(retry, items=(renamed, *retry.items[1:])), OrchestrationIntegrityError, retry)
    assert merge_retry(previous, retry).is_complete


def test_a_retry_result_merges_once():
    lin = Lineage(4)
    previous = _previous(lin)
    retry = _retry(lin, previous)
    merge_retry(previous, retry)
    with pytest.raises(OrchestrationConsumedError):
        merge_retry(previous, retry)


def test_a_real_retry_round_merges_and_the_chain_continues(tmp_path):
    corpus = Corpus(tmp_path, [Film(f"FC2-PPV-{1000001 + i}.mp4") for i in range(3)])
    orchestrator = corpus.orchestrator()
    preview = run(orchestrator.preview(corpus.items))
    result = orchestrator.execute(preview, selection=(1,))
    retry = run(orchestrator.preview_retry(result))
    round_result = orchestrator.execute(retry, selection=(0,))
    assert not round_result.is_complete and round_result.generation == 1
    merged = merge_retry(result, round_result)
    assert [i.retry_kind for i in merged.items] == [K.NONE, K.NONE, K.DEFERRED]
    assert merged.items[1] is result.items[1] and merged.items[2] is round_result.items[1]
    final = merge_retry(merged, orchestrator.execute(run(orchestrator.preview_retry(merged))))
    assert final.generation == 2 and final.outcome is BatchOutcome.SUCCESS


# --------------------------------------------------------------------------- S4-R1: hostile retry graphs


def _set(obj, **fields):
    """Rewrite frozen fields in place; returns the restorer."""
    saved = {name: getattr(obj, name) for name in fields}
    for name, value in fields.items():
        object.__setattr__(obj, name, value)
    return lambda: [object.__setattr__(obj, name, value) for name, value in saved.items()]


def _item_generation_substitution(lin, previous, retry):
    original = previous.items[1]  # same index, same media_item object, same number, generation 0
    assert original.index == retry.items[0].index and original.media_item is retry.items[0].media_item
    assert original.canonical_number == retry.items[0].canonical_number
    assert original.generation == retry.generation - 1
    return _set(retry, items=(original, *retry.items[1:]))


def _item_warnings(lin, previous, retry):
    return _set(retry.items[0], warnings=(ItemWarning.METADATA_PARTIAL,))  # contradicts the item data


def _item_issue(lin, previous, retry):
    return _set(retry.items[0], disposition=D.NOT_SELECTED)  # EXECUTED data, wrong disposition


def _material_plan(lin, previous, retry):
    return _set(retry.items[1].retry_material, plan=lin.plans[0])  # no longer ItemExecution.plan


def _material_checkpoint(lin, previous, retry):
    return _set(retry.items[1].retry_material, checkpoint=fake_checkpoint(lin.plans[2]))  # not execution's


def _scope_with_none(lin, previous, retry):
    return _set(retry, retry_scope=SCOPE | {K.NONE})


def _metadata_lineage(lin, previous, retry):
    foreign = BatchResult(items=previous.metadata_batch.items, generation=0, lineage=BatchLineage.new())
    return _set(retry, metadata_batch=foreign)


def _lineage(lin, previous, retry):
    return _set(retry, lineage=BatchLineage.new())  # metadata ledger now belongs to another lineage


def _generation(lin, previous, retry):
    return _set(retry, generation=2)  # items still carry generation 1


def _reordered(lin, previous, retry):
    return _set(retry, items=(retry.items[1], retry.items[0], retry.items[2]))


def _budget_below_payload(lin, previous, retry):
    return _set(retry, retry_budget_bytes=retry.retained_retry_payload_bytes - 1)  # the old 9a "-1" case


def _no_preview_id(lin, previous, retry):
    return _set(retry, preview_id=None)


def _no_base_result_id(lin, previous, retry):
    return _set(retry, base_result_id=None)


def _no_retry_budget(lin, previous, retry):
    return _set(retry, retry_budget_bytes=None)


HOSTILE = [_item_generation_substitution, _item_warnings, _item_issue, _material_plan, _material_checkpoint,
           _scope_with_none, _metadata_lineage, _lineage, _generation, _reordered, _budget_below_payload,
           _no_preview_id, _no_base_result_id, _no_retry_budget]


def _payload_refs(result):
    return [(item, item.retry_material, None if item.retry_material is None else item.retry_material.artifacts)
            for item in result.items]


@pytest.mark.parametrize("mutate", HOSTILE, ids=[f.__name__.strip("_") for f in HOSTILE])
def test_a_hostile_retry_graph_is_an_integrity_error_before_registration(monkeypatch, mutate):
    lin = Lineage(4)
    previous = _previous(lin)
    statuses = {2: ExecutionStatus.PARTIAL} if mutate is _material_checkpoint else {2: ExecutionStatus.FAILED}
    retry = _retry(lin, previous, statuses=statuses)
    before = (_payload_refs(previous), _payload_refs(retry))
    restore = mutate(lin, previous, retry)
    outcome = []
    with monkeypatch.context() as m:
        trap = mutation_traps(m)  # pure composition: no filesystem access is ever attempted
        with pytest.raises(OrchestrationIntegrityError):
            outcome.append(merge_retry(previous, retry))
    assert outcome == [] and trap.calls == []
    assert not _consumption.RETRY_MERGES.is_registered(retry.result_id)  # failed before registration
    restore()
    assert (_payload_refs(previous), _payload_refs(retry)) == before  # nothing was rewritten by the merge
    merged = merge_retry(previous, retry)  # the restored graph merges under the same result_id
    assert merged.is_complete and merged.items[0] is previous.items[0]


def test_the_lineage_batch_size_must_match_even_when_the_retry_is_self_consistent():
    lin = Lineage(4)
    previous = _previous(lin)
    retry = _retry(lin, previous)
    restore = _set(retry, batch_size=previous.batch_size + 3)  # indices 1..3 < 7: still self-valid
    revalidate(retry)
    with pytest.raises(OrchestrationRetryError):
        merge_retry(previous, retry)
    assert not _consumption.RETRY_MERGES.is_registered(retry.result_id)
    restore()
    assert merge_retry(previous, retry).batch_size == previous.batch_size


def test_a_scope_rewrite_that_changes_the_expected_index_set_fails_closed():
    lin = Lineage(4)
    previous = _previous(lin)
    retry = _retry(lin, previous)
    restore = _set(retry, retry_scope=frozenset({K.DEFERRED}))  # self-valid, but scope now selects 1 and 3
    revalidate(retry)
    with pytest.raises(OrchestrationRetryError):
        merge_retry(previous, retry)
    assert not _consumption.RETRY_MERGES.is_registered(retry.result_id)
    restore()
    assert merge_retry(previous, retry).is_complete


def test_intact_main_and_merged_results_are_not_retry_rounds():
    lin = Lineage(4)
    previous = _previous(lin)
    main = _previous(lin)  # an intact main result of the same lineage
    retry = _retry(lin, main)
    merged = merge_retry(main, retry)  # an intact merged result
    for intact in (main, merged):
        revalidate(intact)
        with pytest.raises(OrchestrationRetryError):
            merge_retry(previous, intact)
        assert not _consumption.RETRY_MERGES.is_registered(intact.result_id)
