"""Input snapshot, FC2 number recognition and Phase A in-batch conflicts (P4-C8 contract 8, 14, 19.6.1).

Pure functions: zero network, zero filesystem access, no engine / image client. The only use of
``os`` is ``os.path.basename`` (number recognition) and ``os.name`` (conflict key); numbers come
from the frozen Phase 1 ``normalize_fc2_number`` -- there is no second parser.

``bounded_snapshot`` is the **only** place that reads the caller's ``items`` container. It never
calls ``len(items)`` / ``tuple(items)`` / ``list(items)``: it iterates once, collects at most
``MAX_BATCH_ITEMS`` references and probes exactly once more for overflow, so resource correctness
never depends on the caller's ``__len__``.
"""

from __future__ import annotations

import os
from collections.abc import Iterator, Mapping, Sequence, Set
from dataclasses import dataclass

from fc2_metadata_core.normalize import FC2RecognitionStatus, normalize_fc2_number
from fc2_organizer.discovery import DiscoveredMediaItem
from fc2_organizer.orchestration.errors import OrchestrationInputError, OrchestrationResourceLimitError
from fc2_organizer.orchestration.models import MAX_BATCH_ITEMS, IssueReason, ResourceLimitReason, type_name

__all__ = ["Recognition", "bounded_snapshot", "validate_media_items", "recognize"]

_MAX_REPORTED_INVALID = 10
_TEXT_TYPES = (str, bytes, bytearray, memoryview)


def _container_failure(items: object) -> str | None:
    """Contract section 8 container kinds, judged on ``type(items)`` (``__class__`` is never consulted)."""
    cls = type(items)
    if issubclass(cls, _TEXT_TYPES):
        return "items must be a Sequence of DiscoveredMediaItem, not a single text / bytes value"
    if issubclass(cls, (Set, Mapping, Iterator)) or not issubclass(cls, Sequence):
        return f"items must be an ordered Sequence (list / tuple) of DiscoveredMediaItem, not {type_name(items)}"
    return None


def bounded_snapshot(items: object) -> tuple[object, ...]:
    """Contract section 19.6.1: container check, then a bounded single pass.

    ``iter(items)`` once; at most ``MAX_BATCH_ITEMS`` elements collected; exactly one overflow
    ``next()``. A ``MAX_BATCH_ITEMS + 1``-th element raises
    ``OrchestrationResourceLimitError(BATCH_ITEM_LIMIT)`` immediately (its reference is not kept and
    nothing more is read). An ordinary ``Exception`` from ``iter()`` / ``next()`` (``StopIteration``
    ending the pass aside) becomes ``OrchestrationInputError`` naming only its class; any other
    ``BaseException`` propagates unchanged. Element types are *not* checked here.
    """
    failure = _container_failure(items)
    if failure is not None:
        raise OrchestrationInputError(failure)
    iteration_error: str | None = None
    overflow = False
    collected: list[object] = []
    try:
        iterator = iter(items)
    except Exception as exc:  # noqa: BLE001 - mapped to a typed input error below, never chained
        iteration_error = type_name(exc)
    if iteration_error is None:
        exhausted = False
        while len(collected) < MAX_BATCH_ITEMS:
            try:
                collected.append(next(iterator))
            except StopIteration:
                exhausted = True
                break
            except Exception as exc:  # noqa: BLE001
                iteration_error = type_name(exc)
                break
        if iteration_error is None and not exhausted:
            try:
                next(iterator)  # the single overflow probe; its element is never bound
            except StopIteration:
                pass
            except Exception as exc:  # noqa: BLE001
                iteration_error = type_name(exc)
            else:
                overflow = True
    if overflow:
        collected.clear()
        raise OrchestrationResourceLimitError(ResourceLimitReason.BATCH_ITEM_LIMIT)
    if iteration_error is not None:
        collected.clear()
        raise OrchestrationInputError(f"iterating items raised {iteration_error}")
    snapshot = tuple(collected)
    collected.clear()
    return snapshot


def validate_media_items(snapshot: tuple[object, ...]) -> tuple[DiscoveredMediaItem, ...]:
    """All-or-nothing strict element check (contract section 8): every element must be an exact
    ``DiscoveredMediaItem``; the message lists at most 10 offending indices with class names and
    always the total count. No hook of a rejected element is run."""
    invalid: list[str] = []
    invalid_count = 0
    for index, element in enumerate(snapshot):
        if type(element) is DiscoveredMediaItem:
            continue
        invalid_count += 1
        if len(invalid) < _MAX_REPORTED_INVALID:
            invalid.append(f"[{index}] {type_name(element)}")
    if invalid_count:
        more = f" (+{invalid_count - len(invalid)} more)" if invalid_count > len(invalid) else ""
        raise OrchestrationInputError(
            f"{invalid_count} element(s) are not DiscoveredMediaItem: {', '.join(invalid)}{more}")
    return snapshot  # type: ignore[return-value]


@dataclass(frozen=True, slots=True)
class Recognition:
    """Number recognition + Phase A verdict for one snapshot position (internal).

    ``reason`` is ``None`` (recognized, no conflict), ``NUMBER_NOT_RECOGNIZED`` or a
    ``DUPLICATE_*_IN_BATCH`` reason; ``conflict_with`` is the ascending union of peer indices.
    """

    index: int
    media_item: DiscoveredMediaItem
    canonical_number: str | None
    reason: IssueReason | None
    conflict_with: tuple[int, ...]


def _canonical_number(item: DiscoveredMediaItem) -> str | None:
    result = normalize_fc2_number(os.path.basename(item.source_path))
    return result.canonical if result.status is FC2RecognitionStatus.RECOGNIZED else None


def _source_key(source_path: str) -> str:
    return source_path.casefold() if os.name == "nt" else source_path


def _peers(groups: dict[str, list[int]], size: int) -> list[set[int]]:
    peers: list[set[int]] = [set() for _ in range(size)]
    for members in groups.values():
        if len(members) >= 2:
            for member in members:
                peers[member].update(other for other in members if other != member)
    return peers


def recognize(snapshot: tuple[DiscoveredMediaItem, ...]) -> tuple[Recognition, ...]:
    """Contract section 14.1-14.2 over a validated snapshot, output in index order.

    Recognized items are grouped by source key (Windows ``casefold``, POSIX exact) and by canonical
    number (== target directory). Every member of a group of size >= 2 is a conflict; the same-source
    reason wins over the same-target reason. Group keys only group; they never decide order.
    """
    numbers = [_canonical_number(item) for item in snapshot]
    by_source: dict[str, list[int]] = {}
    by_target: dict[str, list[int]] = {}
    for index, (item, number) in enumerate(zip(snapshot, numbers)):
        if number is None:
            continue
        by_source.setdefault(_source_key(item.source_path), []).append(index)
        by_target.setdefault(number, []).append(index)
    source_peers = _peers(by_source, len(numbers))
    target_peers = _peers(by_target, len(numbers))
    recognitions = []
    for index, (item, number) in enumerate(zip(snapshot, numbers)):
        if number is None:
            reason = IssueReason.NUMBER_NOT_RECOGNIZED
        elif source_peers[index]:
            reason = IssueReason.DUPLICATE_SOURCE_IN_BATCH
        elif target_peers[index]:
            reason = IssueReason.DUPLICATE_TARGET_IN_BATCH
        else:
            reason = None
        conflict_with = tuple(sorted(source_peers[index] | target_peers[index]))
        recognitions.append(Recognition(index, item, number, reason, conflict_with))
    return tuple(recognitions)
