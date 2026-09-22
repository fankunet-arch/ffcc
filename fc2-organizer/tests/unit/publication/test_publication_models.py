"""P4-C3: ``PublicationRecord`` model invariants and deep immutability
(contract section 6, test matrix 8-11, 17).

The invariants hold at the model layer, so a hand-built record cannot bypass
``prepare_publication``'s gates.
"""

from __future__ import annotations

import dataclasses

import pytest

from fc2_metadata_core.aggregation import AggregateStatus
from fc2_metadata_core.models import NormalizedMetadata
from fc2_organizer.planning import PlannedPath
from fc2_organizer.publication import (
    PUBLISHABLE_STATUSES,
    PublicationContractError,
    PublicationError,
    PublicationRecord,
    prepare_publication,
)

from ._builders import make_aggregate, make_plan

N = "FC2-1234567"
OTHER = "FC2-7654321"


def md(number=N, title="A title", **fields):
    return NormalizedMetadata(number=number, title=title, **fields)


# ---- hand-built invariants ----------------------------------------------------------------------------------------------


@pytest.mark.parametrize("status", [AggregateStatus.SUCCESS, AggregateStatus.PARTIAL])
def test_a_consistent_hand_built_record_is_accepted(status):
    record = PublicationRecord(plan=make_plan(N), metadata=md(), aggregate_status=status)
    assert record.number == N


def test_publishable_statuses_are_exactly_success_and_partial():
    assert PUBLISHABLE_STATUSES == frozenset({AggregateStatus.SUCCESS, AggregateStatus.PARTIAL})


@pytest.mark.parametrize(
    "kwargs",
    [
        {"plan": None},
        {"plan": "FC2-1234567"},
        {"metadata": None},
        {"metadata": {"number": N, "title": "t"}},
        {"aggregate_status": AggregateStatus.FAILED},
        {"aggregate_status": "success"},
        {"aggregate_status": None},
        {"metadata": md(title=None)},
        {"metadata": md(title=" ")},
        {"metadata": md(number="1234567")},
        {"metadata": md(number=OTHER)},
    ],
    ids=lambda k: f"{next(iter(k))}={next(iter(k.values()))!r}"[:60],
)
def test_an_inconsistent_hand_built_record_is_rejected(kwargs):
    base = {"plan": make_plan(N), "metadata": md(), "aggregate_status": AggregateStatus.SUCCESS}
    base.update(kwargs)
    with pytest.raises(PublicationContractError):
        PublicationRecord(**base)


def test_contract_error_is_a_publication_error():
    assert issubclass(PublicationContractError, PublicationError)


def test_a_str_subclass_metadata_number_is_rejected_by_the_model():
    class Sneaky(str):
        pass

    with pytest.raises(PublicationContractError):
        PublicationRecord(plan=make_plan(N), metadata=md(number=Sneaky(N)), aggregate_status=AggregateStatus.SUCCESS)


# ---- 8-10: immutability ------------------------------------------------------------------------------------------------------


def record(**metadata_fields):
    return prepare_publication(make_plan(N), make_aggregate(N, **metadata_fields))


@pytest.mark.parametrize("name", ["plan", "metadata", "aggregate_status", "extra"])
def test_record_fields_cannot_be_reassigned_or_added(name):
    rec = record()
    with pytest.raises((dataclasses.FrozenInstanceError, AttributeError, TypeError)):
        setattr(rec, name, None)
    with pytest.raises((dataclasses.FrozenInstanceError, AttributeError, TypeError)):
        delattr(rec, name)


def test_record_has_slots_and_no_instance_dict():
    rec = record()
    assert not hasattr(rec, "__dict__")
    assert PublicationRecord.__slots__ == ("plan", "metadata", "aggregate_status")


def test_nested_plan_is_immutable():
    rec = record()
    with pytest.raises(dataclasses.FrozenInstanceError):
        rec.plan.canonical_number = OTHER  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        rec.plan.nfo_path.absolute_path = r"C:\elsewhere\x.nfo"  # type: ignore[misc]
    assert isinstance(rec.plan.operations, tuple)
    with pytest.raises(AttributeError):
        rec.plan.operations.append(None)  # type: ignore[attr-defined]
    assert isinstance(rec.plan.nfo_path, PlannedPath)


def test_nested_metadata_is_immutable():
    rec = record()
    with pytest.raises(dataclasses.FrozenInstanceError):
        rec.metadata.title = "changed"  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        rec.metadata.number = OTHER  # type: ignore[misc]


# ---- 17: collections inside metadata --------------------------------------------------------------------------------------


def test_tuple_and_mapping_metadata_stays_immutable_and_detached_from_caller_containers():
    actors = ["Alice", "Bob"]
    external_ids = {"fc2": "1234567"}
    rec = record(actors=actors, tags=["t1"], poster_urls=["https://x.invalid/p.jpg"], external_ids=external_ids)
    actors.append("Mallory")
    external_ids["fc2"] = "tampered"
    assert rec.metadata.actors == ("Alice", "Bob")
    assert rec.metadata.external_ids["fc2"] == "1234567"
    assert isinstance(rec.metadata.actors, tuple) and isinstance(rec.metadata.tags, tuple)
    with pytest.raises(TypeError):
        rec.metadata.external_ids["fc2"] = "x"  # type: ignore[index]
    with pytest.raises(TypeError):
        rec.metadata.field_sources["title"] = ("evil",)  # type: ignore[index]
    with pytest.raises(AttributeError):
        rec.metadata.actors.append("x")  # type: ignore[attr-defined]


# ---- 11: determinism / equality --------------------------------------------------------------------------------------------


def test_identical_inputs_give_equal_records():
    plan = make_plan(N)
    aggregate = make_aggregate(N, kind="partial_retry", actors=["A"], external_ids={"k": "v"})
    first = prepare_publication(plan, aggregate)
    second = prepare_publication(plan, aggregate)
    assert first == second and first is not second
    rebuilt = prepare_publication(make_plan(N), make_aggregate(N, kind="partial_retry", actors=["A"], external_ids={"k": "v"}))
    assert rebuilt == first
    assert repr(rebuilt) == repr(first)


def test_records_for_different_statuses_or_titles_are_not_equal():
    base = record()
    assert base != prepare_publication(make_plan(N), make_aggregate(N, kind="partial"))
    assert base != prepare_publication(make_plan(N), make_aggregate(N, title="Other title"))


def test_hash_follows_the_existing_semantics_of_the_nested_objects():
    """``OrganizePlan`` is hashable; ``NormalizedMetadata`` is not (its mappings are
    ``MappingProxyType``), so neither is a record -- consistently, never randomly."""
    rec = record()
    hash(rec.plan)
    with pytest.raises(TypeError):
        hash(rec.metadata)
    with pytest.raises(TypeError):
        hash(rec)


# ---- no serializer / renderer surface ---------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name", ["to_json", "to_dict", "to_xml", "render_nfo", "render", "write", "save", "serialize", "dump"]
)
def test_record_is_not_a_serializer(name):
    assert not hasattr(PublicationRecord, name)


def test_record_exposes_only_its_three_fields():
    assert tuple(f.name for f in dataclasses.fields(PublicationRecord)) == ("plan", "metadata", "aggregate_status")
