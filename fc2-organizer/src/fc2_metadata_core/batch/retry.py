"""Failed-subset retry helpers (Phase 3 C4). Pure functions; see contract §8.

* :func:`failed_work` selects what a retry round must re-run: the ``FAILED`` items of a :class:`BatchResult`,
  identified by their **original index** (never by number -- numbers may repeat).
  ``SUCCESS`` and ``PARTIAL`` items are never selected.
* :func:`apply_retry` merges a :class:`RetryBatchResult` into the result it was made from and returns a **new**
  :class:`BatchResult` (the inputs are never mutated). It fails closed with :class:`BatchRetryError`, producing
  nothing, unless the retry demonstrably belongs to that result: **the same lineage** (the opaque identity of the
  execution chain, created once per ``run()`` and carried by every derived result -- shape comparison alone cannot
  tell two identical-looking batches apart), right generation, exactly the failed indices, same numbers.
"""

from __future__ import annotations

from fc2_metadata_core.batch.models import (
    BatchItemResult,
    BatchResult,
    BatchRetryError,
    RetryBatchResult,
)

__all__ = ["apply_retry", "failed_work"]


def failed_work(previous: BatchResult) -> tuple[tuple[int, str], ...]:
    """``(original_index, number)`` of every FAILED item of ``previous``, in batch order."""
    if not isinstance(previous, BatchResult):
        raise BatchRetryError("retry_failed needs a BatchResult (apply_retry the RetryBatchResult first)")
    return tuple((item.index, item.number) for item in previous.failed_items)


def apply_retry(previous: BatchResult, retry: RetryBatchResult) -> BatchResult:
    """Replace the retried items of ``previous`` with ``retry``'s, keeping the original order.

    Unretried items are the *same objects* as in ``previous``. The new result's ``generation`` is
    ``retry.generation``.
    """
    if not isinstance(previous, BatchResult):
        raise BatchRetryError("apply_retry: previous must be a BatchResult")
    if not isinstance(retry, RetryBatchResult):
        raise BatchRetryError("apply_retry: retry must be a RetryBatchResult")
    if retry.lineage != previous.lineage:
        raise BatchRetryError(
            "apply_retry: the retry was not made from this batch (different lineage); a retry can only be applied "
            "to the batch execution chain it came from"
        )
    if retry.generation != previous.generation + 1:
        raise BatchRetryError(
            f"apply_retry: retry generation {retry.generation} does not follow the previous result's "
            f"generation {previous.generation} (a stale, replayed or foreign retry)"
        )
    if retry.indices != previous.failed_indices:
        raise BatchRetryError(
            "apply_retry: the retry must cover exactly the previous result's failed indices "
            f"(expected {previous.failed_indices!r}, got {retry.indices!r})"
        )
    replacements: dict[int, BatchItemResult] = {}
    for item in retry.items:
        original = previous.items[item.index]
        if item.number != original.number:
            raise BatchRetryError(
                f"apply_retry: item {item.index} is {item.number!r} in the retry but {original.number!r} in the batch"
            )
        replacements[item.index] = item
    merged = tuple(replacements.get(item.index, item) for item in previous.items)
    return BatchResult(merged, generation=retry.generation, lineage=previous.lineage)
