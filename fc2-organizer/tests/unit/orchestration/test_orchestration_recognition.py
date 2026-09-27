"""P4-C8 S1: input container rules, bounded snapshot, number recognition and Phase A conflicts
(contract sections 8, 14.1, 14.2, 19.6.1; contract section 35 "bounded snapshot" rows A-H).

Everything here is pure: the ``no_io`` fixture traps every filesystem entry point (reads included),
and the scripted engine / image client used as witnesses must record zero calls.
"""

from __future__ import annotations

import builtins
import os
from collections.abc import Iterator, Sequence

import pytest

from fc2_organizer.discovery import DiscoveredMediaItem
from fc2_organizer.orchestration import (
    MAX_BATCH_ITEMS,
    IssueReason,
    OrchestrationInputError,
    OrchestrationResourceLimitError,
    ResourceLimitReason,
)
from fc2_organizer.orchestration.recognition import (
    Recognition,
    bounded_snapshot,
    recognize,
    validate_media_items,
)

from ._fakes import ScriptedEngine, ScriptedImageClient
from ._helpers import DOWNLOADS, media_item

LIMIT = MAX_BATCH_ITEMS

_FS_ENTRY_POINTS = ("lstat", "stat", "scandir", "listdir", "open", "walk", "mkdir", "rename", "replace", "remove",
                    "unlink", "rmdir", "link", "symlink", "readlink")


@pytest.fixture
def no_io(monkeypatch):
    """Traps every filesystem entry point (reads included); proves zero filesystem access."""
    hits: list[str] = []

    def trap(name):
        def trapped(*_args, **_kwargs):
            hits.append(name)
            raise AssertionError(f"filesystem access: {name}")
        return trapped

    for name in _FS_ENTRY_POINTS:
        if hasattr(os, name):
            monkeypatch.setattr(os, name, trap(f"os.{name}"))
    for name in ("exists", "isdir", "isfile", "islink", "realpath", "abspath"):
        monkeypatch.setattr(os.path, name, trap(f"os.path.{name}"))
    monkeypatch.setattr(builtins, "open", trap("open"))
    engine, client = ScriptedEngine(), ScriptedImageClient()
    yield hits
    assert hits == []
    assert engine.calls == [] and client.calls == []


def _items(count: int, name: str = "clip-{i}.mp4") -> list[DiscoveredMediaItem]:
    return [media_item(i, name.format(i=i), size=1) for i in range(count)]


def _run(items):
    return recognize(validate_media_items(bounded_snapshot(items)))


# =========================================================================== counting sequences


class CountingIterator(Iterator):
    def __init__(self, owner: "CountingSequence") -> None:
        self.owner = owner
        self.position = 0

    def __next__(self):
        owner = self.owner
        owner.next_calls += 1
        if owner.fail_at is not None and self.position == owner.fail_at:
            raise owner.fail_exc
        if self.position >= owner.actual:
            owner.stop_iterations += 1
            raise StopIteration
        element = owner.factory(self.position)
        self.position += 1
        owner.elements_read += 1
        return element


class CountingSequence(Sequence):
    """A lazy custom ``Sequence`` that records ``__iter__`` / ``__getitem__`` / ``__len__`` calls, ``next``
    calls and elements produced; ``claimed`` is what ``__len__`` says, ``actual`` what iteration yields."""

    def __init__(self, actual: int, *, claimed: int | None = None, factory=None, fail_at: int | None = None,
                 fail_exc: BaseException | None = None) -> None:
        self.actual = actual
        self.claimed = actual if claimed is None else claimed
        self.factory = factory or _shared_factory
        self.fail_at = fail_at
        self.fail_exc = fail_exc
        self.iter_calls = self.getitem_calls = self.len_calls = 0
        self.next_calls = self.elements_read = self.stop_iterations = 0

    def __len__(self) -> int:
        self.len_calls += 1
        return self.claimed

    def __getitem__(self, index):
        self.getitem_calls += 1
        if not 0 <= index < self.actual:
            raise IndexError(index)
        return self.factory(index)

    def __iter__(self):
        self.iter_calls += 1
        return CountingIterator(self)


_SHARED = media_item(0, "clip.mp4", size=1)


def _shared_factory(_index: int) -> DiscoveredMediaItem:
    return _SHARED


# =========================================================================== container rules


@pytest.mark.parametrize("container", [list, tuple])
def test_list_and_tuple_are_accepted(no_io, container):
    items = _items(3)
    assert bounded_snapshot(container(items)) == tuple(items)


def _generator():
    yield from _items(2)


class _SequenceIterator(Sequence, Iterator):
    def __len__(self):
        return 0

    def __getitem__(self, index):
        raise IndexError(index)

    def __next__(self):
        raise StopIteration


class _SpoofedClass:
    @property
    def __class__(self):  # noqa: D401 - hostile spoof
        return list


@pytest.mark.parametrize("bad", [
    "FC2-PPV-1234567.mp4", b"bytes", bytearray(b"x"), memoryview(b"x"), {_SHARED}, frozenset({_SHARED}),
    {"a": _SHARED}, _generator(), iter([_SHARED]), None, 42, _SequenceIterator(), _SpoofedClass(),
])
def test_non_sequence_containers_are_rejected(no_io, bad):
    with pytest.raises(OrchestrationInputError) as info:
        bounded_snapshot(bad)
    assert info.value.__cause__ is None and info.value.__context__ is None


def test_rejected_container_is_never_iterated(no_io):
    class Mapping_(dict):
        def __iter__(self):  # pragma: no cover - must never run
            raise AssertionError("iterated")

    with pytest.raises(OrchestrationInputError):
        bounded_snapshot(Mapping_())


def test_empty_input(no_io):
    assert bounded_snapshot([]) == () and _run(()) == ()


def test_snapshot_is_independent_of_later_caller_mutation(no_io):
    items = _items(3)
    snapshot = bounded_snapshot(items)
    items.append(media_item(9, "late.mp4"))
    items[0] = None
    assert type(snapshot) is tuple and len(snapshot) == 3 and type(snapshot[0]) is DiscoveredMediaItem


# =========================================================================== element strictness


class _HookedItem(DiscoveredMediaItem):
    hooks: list[str] = []

    def __eq__(self, other):  # pragma: no cover - must never run
        _HookedItem.hooks.append("__eq__")
        return False

    __hash__ = None

    def __repr__(self):  # pragma: no cover
        _HookedItem.hooks.append("__repr__")
        return "hooked"

    def __getattribute__(self, name):  # pragma: no cover - must never run
        _HookedItem.hooks.append(name)
        return object.__getattribute__(self, name)


def test_element_subclass_is_rejected_without_running_any_hook(no_io):
    hooked = _HookedItem(index=0, source_path=os.path.join(DOWNLOADS, "FC2-PPV-1234567.mp4"),
                         relative_path="a.mp4", extension=".mp4", size=1)
    _HookedItem.hooks.clear()
    with pytest.raises(OrchestrationInputError) as info:
        validate_media_items(bounded_snapshot([hooked]))
    assert _HookedItem.hooks == []
    assert "_HookedItem" in str(info.value) and "[0]" in str(info.value)


def test_element_errors_list_at_most_ten_indices_and_the_total(no_io):
    items = [object() if i % 2 else _SHARED for i in range(40)]
    with pytest.raises(OrchestrationInputError) as info:
        validate_media_items(bounded_snapshot(items))
    text = str(info.value)
    assert text.startswith("20 element(s)")
    assert text.count("[") == 10 and "(+10 more)" in text and "[39]" not in text
    assert info.value.__cause__ is None and info.value.__context__ is None


def test_element_check_is_all_or_nothing(no_io):
    with pytest.raises(OrchestrationInputError):
        validate_media_items(bounded_snapshot(_items(5) + ["FC2-PPV-1234567.mp4"]))


# =========================================================================== bounded snapshot (contract 35, A-H)


def test_a_exactly_max_items_accepted_with_one_stop_probe(no_io):
    seq = CountingSequence(LIMIT)
    snapshot = bounded_snapshot(seq)
    assert len(snapshot) == LIMIT
    assert seq.elements_read == LIMIT and seq.next_calls == LIMIT + 1 and seq.stop_iterations == 1
    assert seq.iter_calls == 1 and seq.len_calls == 0 and seq.getitem_calls == 0


def test_a_max_items_through_the_whole_recognition_path(no_io):
    items = _items(LIMIT)
    recognitions = _run(items)
    assert len(recognitions) == LIMIT
    assert all(r.reason is IssueReason.NUMBER_NOT_RECOGNIZED for r in recognitions)


def test_b_one_over_the_limit_reads_exactly_limit_plus_one_and_stops(no_io):
    seq = CountingSequence(LIMIT + 1)
    with pytest.raises(OrchestrationResourceLimitError) as info:
        bounded_snapshot(seq)
    assert info.value.reason is ResourceLimitReason.BATCH_ITEM_LIMIT
    assert seq.elements_read == LIMIT + 1 and seq.next_calls == LIMIT + 1 and seq.stop_iterations == 0
    assert seq.iter_calls == 1 and seq.len_calls == 0


def test_b_plain_list_over_the_limit(no_io):
    with pytest.raises(OrchestrationResourceLimitError) as info:
        _run(_items(LIMIT + 1))
    assert info.value.reason is ResourceLimitReason.BATCH_ITEM_LIMIT


def test_c_lazy_million_item_sequence_reads_only_limit_plus_one(no_io):
    produced: list[int] = []

    def factory(index):
        produced.append(index)
        return _SHARED

    seq = CountingSequence(1_000_000, factory=factory)
    with pytest.raises(OrchestrationResourceLimitError) as info:
        bounded_snapshot(seq)
    assert info.value.reason is ResourceLimitReason.BATCH_ITEM_LIMIT
    assert seq.elements_read == LIMIT + 1 and len(produced) == LIMIT + 1
    assert produced == list(range(LIMIT + 1))
    assert seq.len_calls == 0 and seq.getitem_calls == 0


def test_d_lying_short_len_is_not_trusted(no_io):
    seq = CountingSequence(3000, claimed=1)
    with pytest.raises(OrchestrationResourceLimitError) as info:
        bounded_snapshot(seq)
    assert info.value.reason is ResourceLimitReason.BATCH_ITEM_LIMIT
    assert seq.elements_read == LIMIT + 1 and seq.len_calls == 0


def test_e_len_is_never_called_and_a_lying_huge_len_is_ignored(no_io):
    seq = CountingSequence(5, claimed=10 ** 9, factory=lambda i: media_item(i, f"FC2-PPV-{1000000 + i}.mp4"))
    recognitions = _run(seq)
    assert len(recognitions) == 5 and seq.len_calls == 0
    assert [r.canonical_number for r in recognitions] == [f"FC2-{1000000 + i}" for i in range(5)]


def test_e_len_is_never_called_even_when_it_raises(no_io):
    class NoLen(CountingSequence):
        def __len__(self):  # pragma: no cover - must never run
            raise AssertionError("__len__ called")

    assert len(bounded_snapshot(NoLen(4))) == 4


def test_f_limit_takes_precedence_over_later_invalid_elements(no_io):
    def factory(index):
        return _SHARED if index < LIMIT else "not an item"

    seq = CountingSequence(LIMIT + 50, factory=factory)
    with pytest.raises(OrchestrationResourceLimitError) as info:
        _run(seq)
    assert info.value.reason is ResourceLimitReason.BATCH_ITEM_LIMIT
    assert seq.elements_read == LIMIT + 1


def test_f_limit_takes_precedence_over_invalid_elements_inside_the_first_limit(no_io):
    items = ["not an item"] * 3 + [_SHARED] * LIMIT
    with pytest.raises(OrchestrationResourceLimitError) as info:
        _run(items)
    assert info.value.reason is ResourceLimitReason.BATCH_ITEM_LIMIT


def test_g_invalid_element_within_the_limit_is_an_input_error(no_io):
    items = [_SHARED] * (LIMIT - 1) + [object()]
    with pytest.raises(OrchestrationInputError):
        _run(items)
    with pytest.raises(OrchestrationInputError):
        _run([_SHARED] * (LIMIT - 1) + [None])


class _Boom(Exception):
    pass


@pytest.mark.parametrize("fail_at", [0, 7, LIMIT])
def test_h_ordinary_iteration_exception_becomes_an_unchained_input_error(no_io, fail_at):
    seq = CountingSequence(LIMIT + 10, fail_at=fail_at, fail_exc=_Boom(r"C:\secret\path"))
    with pytest.raises(OrchestrationInputError) as info:
        bounded_snapshot(seq)
    assert info.value.__cause__ is None and info.value.__context__ is None
    assert "_Boom" in str(info.value) and "secret" not in str(info.value)
    assert seq.next_calls == fail_at + 1


def test_h_exception_from_iter_itself_is_an_input_error(no_io):
    class BadIter(CountingSequence):
        def __iter__(self):
            raise ValueError("nope")

    with pytest.raises(OrchestrationInputError) as info:
        bounded_snapshot(BadIter(3))
    assert "ValueError" in str(info.value) and info.value.__context__ is None


@pytest.mark.parametrize("fatal", [KeyboardInterrupt(), SystemExit(3), GeneratorExit()])
@pytest.mark.parametrize("fail_at", [0, 5, LIMIT])
def test_h_non_exception_base_exception_propagates_as_the_same_object(no_io, fatal, fail_at):
    seq = CountingSequence(LIMIT + 10, fail_at=fail_at, fail_exc=fatal)
    with pytest.raises(BaseException) as info:
        bounded_snapshot(seq)
    assert info.value is fatal


def test_no_len_tuple_or_list_is_applied_to_the_input_container(no_io):
    class Guarded(CountingSequence):
        def __len__(self):  # pragma: no cover - must never run
            raise AssertionError("len(items)")

        def __getitem__(self, index):  # pragma: no cover - tuple()/list() of a Sequence could use it
            raise AssertionError("indexing")

    seq = Guarded(10)
    assert len(bounded_snapshot(seq)) == 10
    assert seq.iter_calls == 1


# =========================================================================== number recognition (14.1)


@pytest.mark.parametrize("name, expected", [
    ("FC2-PPV-1234567.mp4", "FC2-1234567"),
    ("FC2PPV1234567.mp4", "FC2-1234567"),
    ("[广告]FC2PPV-1234567.mp4", "FC2-1234567"),
    ("xxx@FC2PPV-1234567.mkv", "FC2-1234567"),
    ("fc2_ppv_7654321.MP4", "FC2-7654321"),
    ("FC2-PPV-1111111 FC2-PPV-2222222.mp4", "FC2-1111111"),
    ("random-name.mp4", None),
    ("abcFC2-1234567.mp4", None),
])
def test_number_comes_from_the_basename_through_phase1(no_io, name, expected):
    (recognition,) = _run([media_item(0, name)])
    assert recognition.canonical_number == expected
    if expected is None:
        assert recognition.reason is IssueReason.NUMBER_NOT_RECOGNIZED and recognition.conflict_with == ()
    else:
        assert recognition.reason is None


def test_parent_directory_number_is_never_used(no_io):
    item = media_item(0, "random.mp4", directory=os.path.join(DOWNLOADS, "FC2-PPV-1234567"))
    (recognition,) = _run([item])
    assert recognition.canonical_number is None
    assert recognition.reason is IssueReason.NUMBER_NOT_RECOGNIZED


def test_recognition_objects_keep_identity_and_index_order(no_io):
    items = _items(3, "FC2-PPV-{i}000001.mp4")
    recognitions = _run(items)
    assert [r.index for r in recognitions] == [0, 1, 2]
    assert all(r.media_item is item for r, item in zip(recognitions, items))
    assert all(type(r) is Recognition for r in recognitions)


# =========================================================================== Phase A conflicts (14.2)


def _by_index(recognitions):
    return {r.index: (r.reason, r.conflict_with) for r in recognitions}


def test_same_number_different_files_is_a_target_conflict(no_io):
    a = media_item(0, "FC2-PPV-1234567.mp4")
    b = media_item(1, "FC2PPV1234567.mkv", directory=os.path.join(DOWNLOADS, "other"))
    c = media_item(2, "FC2-PPV-7654321.mp4")
    assert _by_index(_run([a, b, c])) == {
        0: (IssueReason.DUPLICATE_TARGET_IN_BATCH, (1,)),
        1: (IssueReason.DUPLICATE_TARGET_IN_BATCH, (0,)),
        2: (None, ()),
    }


def test_same_object_twice_is_a_source_conflict(no_io):
    a = media_item(0, "FC2-PPV-1234567.mp4")
    assert _by_index(_run([a, a])) == {
        0: (IssueReason.DUPLICATE_SOURCE_IN_BATCH, (1,)),
        1: (IssueReason.DUPLICATE_SOURCE_IN_BATCH, (0,)),
    }


@pytest.mark.skipif(os.name != "nt", reason="case-insensitive source keys are Windows-only (contract 14.2)")
def test_windows_case_variants_of_one_path_are_a_source_conflict(no_io):
    a = media_item(0, "FC2-PPV-1234567.mp4")
    b = DiscoveredMediaItem(index=1, source_path=a.source_path.upper(), relative_path="x.mp4", extension=".mp4",
                            size=1)
    assert _by_index(_run([a, b]))[1] == (IssueReason.DUPLICATE_SOURCE_IN_BATCH, (0,))


def test_source_key_is_exact_on_posix(no_io, monkeypatch):
    import fc2_organizer.orchestration.recognition as recognition_module

    monkeypatch.setattr(recognition_module.os, "name", "posix")
    a = media_item(0, "FC2-PPV-1234567.mp4")
    b = DiscoveredMediaItem(index=1, source_path=a.source_path.upper(), relative_path="x.mp4", extension=".mp4",
                            size=1)
    # different exact strings: only the same canonical number (target) conflicts
    assert _by_index(_run([a, b]))[1] == (IssueReason.DUPLICATE_TARGET_IN_BATCH, (0,))


def test_three_way_group_blocks_every_member(no_io):
    items = [media_item(i, "FC2-PPV-1234567.mp4", directory=os.path.join(DOWNLOADS, f"d{i}")) for i in range(3)]
    assert _by_index(_run(items)) == {
        0: (IssueReason.DUPLICATE_TARGET_IN_BATCH, (1, 2)),
        1: (IssueReason.DUPLICATE_TARGET_IN_BATCH, (0, 2)),
        2: (IssueReason.DUPLICATE_TARGET_IN_BATCH, (0, 1)),
    }


def test_member_of_both_groups_gets_source_priority_and_the_ascending_union(no_io):
    same_path = media_item(0, "FC2-PPV-1234567.mp4")
    same_number = media_item(3, "FC2-PPV-1234567.mkv", directory=os.path.join(DOWNLOADS, "other"))
    unrelated = media_item(1, "FC2-PPV-7654321.mp4")
    items = [same_number, unrelated, same_path, same_path]
    assert _by_index(_run(items)) == {
        0: (IssueReason.DUPLICATE_TARGET_IN_BATCH, (2, 3)),
        1: (None, ()),
        2: (IssueReason.DUPLICATE_SOURCE_IN_BATCH, (0, 3)),
        3: (IssueReason.DUPLICATE_SOURCE_IN_BATCH, (0, 2)),
    }


def test_unrecognized_items_never_join_a_conflict_group(no_io):
    a = media_item(0, "random.mp4")
    assert _by_index(_run([a, a])) == {
        0: (IssueReason.NUMBER_NOT_RECOGNIZED, ()),
        1: (IssueReason.NUMBER_NOT_RECOGNIZED, ()),
    }


def test_conflict_verdicts_do_not_depend_on_input_rotation(no_io):
    base = [media_item(i, f"FC2-PPV-{1000000 + i % 3}.mp4", directory=os.path.join(DOWNLOADS, f"d{i}"))
            for i in range(9)]
    first = _run(base)
    again = _run(list(base))
    assert first == again
    for r in first:
        assert list(r.conflict_with) == sorted(r.conflict_with)
        peers = {i for i in range(9) if i != r.index and i % 3 == r.index % 3}
        assert set(r.conflict_with) == peers
