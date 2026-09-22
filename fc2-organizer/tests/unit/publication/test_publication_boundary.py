"""P4-C3: ``prepare_publication`` behaviour (contract section 4-10, test matrix 1-7, 16).

Accepted: SUCCESS / PARTIAL aggregates whose number, metadata number and plan
number are the same canonical FC2 number. Everything else fails closed with a
typed ``PublicationError`` -- never a bare ``ValueError`` and never a record.
"""

from __future__ import annotations

import dataclasses

import pytest

from fc2_metadata_core.aggregation import AggregateStatus, AggregationResult
from fc2_metadata_core.models import NormalizedMetadata
from fc2_organizer.publication import (
    AggregationNotPublishableError,
    InvalidPublicationMetadataError,
    PublicationError,
    PublicationIdentityMismatchError,
    PublicationInputError,
    PublicationRecord,
    prepare_publication,
)

from ._builders import SECRET_MARKER, make_aggregate, make_plan

N = "FC2-1234567"
OTHER = "FC2-7654321"


def bypass(result: AggregationResult, **overrides) -> AggregationResult:
    """An ``AggregationResult`` whose own ``__post_init__`` invariants were skipped
    (``object.__new__`` + ``object.__setattr__``): the boundary must not rely on them."""
    clone = object.__new__(AggregationResult)
    for field in dataclasses.fields(AggregationResult):
        object.__setattr__(clone, field.name, overrides.get(field.name, getattr(result, field.name)))
    return clone


# ---- 1, 2, 6: accepted -----------------------------------------------------------------------------------------------


@pytest.mark.parametrize("kind", ["success", "partial", "partial_retry"])
def test_matching_success_or_partial_aggregate_is_published(kind):
    plan = make_plan(N)
    aggregate = make_aggregate(N, kind=kind)
    record = prepare_publication(plan, aggregate)
    assert isinstance(record, PublicationRecord)
    assert record.plan is plan
    assert record.metadata is aggregate.metadata
    assert record.aggregate_status is aggregate.status
    assert record.number == N == record.metadata.number == record.plan.canonical_number
    expected = AggregateStatus.SUCCESS if kind == "success" else AggregateStatus.PARTIAL
    assert record.aggregate_status is expected


def test_partial_publication_keeps_the_partial_status_it_does_not_upgrade_it():
    record = prepare_publication(make_plan(N), make_aggregate(N, kind="partial"))
    assert record.aggregate_status is AggregateStatus.PARTIAL


# ---- 3: FAILED -------------------------------------------------------------------------------------------------------


def test_failed_aggregate_is_rejected():
    aggregate = make_aggregate(N, kind="failed")
    assert aggregate.status is AggregateStatus.FAILED
    with pytest.raises(AggregationNotPublishableError):
        prepare_publication(make_plan(N), aggregate)


def test_failed_status_is_rejected_even_if_bypassed_metadata_is_present():
    ok = make_aggregate(N)
    forged = bypass(ok, status=AggregateStatus.FAILED)
    with pytest.raises(AggregationNotPublishableError):
        prepare_publication(make_plan(N), forged)


@pytest.mark.parametrize("status", ["success", None, 1, object()])
def test_a_non_enum_status_on_a_bypassed_result_is_not_publishable(status):
    forged = bypass(make_aggregate(N), status=status)
    with pytest.raises(AggregationNotPublishableError):
        prepare_publication(make_plan(N), forged)


# ---- 4, 5: identity ------------------------------------------------------------------------------------------------------


def test_plan_number_differing_from_aggregate_number_is_rejected():
    with pytest.raises(PublicationIdentityMismatchError) as info:
        prepare_publication(make_plan(N), make_aggregate(OTHER))
    assert N in str(info.value) and OTHER in str(info.value)


def test_metadata_number_differing_from_aggregate_number_is_rejected():
    ok = make_aggregate(N)
    forged = bypass(ok, metadata=NormalizedMetadata(number=OTHER, title="A title"))
    with pytest.raises(PublicationIdentityMismatchError):
        prepare_publication(make_plan(N), forged)


def test_aggregate_number_alone_differing_is_rejected():
    ok = make_aggregate(N)
    forged = bypass(ok, number=OTHER)
    with pytest.raises(PublicationIdentityMismatchError):
        prepare_publication(make_plan(N), forged)


def test_no_winner_is_chosen_when_plan_and_metadata_agree_but_the_aggregate_number_does_not():
    forged = bypass(make_aggregate(OTHER), metadata=NormalizedMetadata(number=N, title="t"))
    with pytest.raises(PublicationIdentityMismatchError):
        prepare_publication(make_plan(N), forged)


def test_a_str_subclass_that_claims_equality_cannot_fake_an_identity_match():
    class Liar(str):
        def __eq__(self, other):  # pragma: no cover - must never be consulted for acceptance
            return True

        __hash__ = str.__hash__

    forged = bypass(make_aggregate(N), number=Liar(OTHER))
    with pytest.raises(PublicationIdentityMismatchError) as info:
        prepare_publication(make_plan(N), forged)
    assert "<Liar>" in str(info.value)


def test_near_miss_numbers_are_not_equal():
    for near in ("FC2-12345670", "FC2-123456", "FC2-1234568"):
        with pytest.raises(PublicationIdentityMismatchError):
            prepare_publication(make_plan(N), make_aggregate(near))


# ---- 7: minimum success ----------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "metadata",
    [
        None,
        NormalizedMetadata(number=N, title=None),
        NormalizedMetadata(number=N, title="   "),
        NormalizedMetadata(number=None, title="t"),
        NormalizedMetadata(number="fc2-1234567", title="t"),
        "not metadata",
    ],
    ids=["none", "no-title", "blank-title", "no-number", "non-canonical", "wrong-type"],
)
def test_metadata_that_misses_minimum_success_is_rejected(metadata):
    forged = bypass(make_aggregate(N), metadata=metadata)
    with pytest.raises(InvalidPublicationMetadataError):
        prepare_publication(make_plan(N), forged)


# ---- input types ---------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("plan", [None, "FC2-1234567", object(), {"canonical_number": N}])
def test_a_non_plan_is_rejected_as_input_error(plan):
    with pytest.raises(PublicationInputError):
        prepare_publication(plan, make_aggregate(N))  # type: ignore[arg-type]


@pytest.mark.parametrize("aggregate", [None, object(), NormalizedMetadata(number=N, title="t")])
def test_a_non_aggregation_result_is_rejected_as_input_error(aggregate):
    with pytest.raises(PublicationInputError):
        prepare_publication(make_plan(N), aggregate)  # type: ignore[arg-type]


def test_arguments_are_type_checked_before_anything_else():
    # wrong plan type + FAILED aggregate: the input error wins (deterministic order)
    with pytest.raises(PublicationInputError):
        prepare_publication(None, make_aggregate(N, kind="failed"))  # type: ignore[arg-type]


def test_every_publication_error_is_typed_and_shares_one_base():
    for cls in (
        PublicationInputError,
        AggregationNotPublishableError,
        InvalidPublicationMetadataError,
        PublicationIdentityMismatchError,
    ):
        assert issubclass(cls, PublicationError) and cls is not ValueError
    assert issubclass(PublicationInputError, TypeError)


# ---- error messages never carry diagnostics -------------------------------------------------------------------------


def test_error_messages_never_include_source_error_detail():
    failures = []
    for call in (
        lambda: prepare_publication(make_plan(N), make_aggregate(N, kind="failed")),
        lambda: prepare_publication(make_plan(N), make_aggregate(OTHER, kind="partial_retry")),
        lambda: prepare_publication(make_plan(N), bypass(make_aggregate(N, kind="partial"), metadata=None)),
    ):
        with pytest.raises(PublicationError) as info:
            call()
        failures.append(info.value)
    for error in failures:
        text = str(error) + repr(error) + repr(error.args)
        assert SECRET_MARKER not in text
        assert "cookie" not in text.lower() and "bearer" not in text.lower()
        assert error.__cause__ is None and error.__context__ is None


def test_a_hostile_object_in_an_identity_field_is_never_repr_d():
    class Hostile:
        def __repr__(self):  # pragma: no cover - must never run
            raise AssertionError("repr of a foreign object was called")

        __str__ = __repr__

    forged = bypass(make_aggregate(N), number=Hostile())
    with pytest.raises(PublicationIdentityMismatchError) as info:
        prepare_publication(make_plan(N), forged)
    assert "<Hostile>" in str(info.value)


# ---- 16: Unicode ---------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "title",
    [
        "素人・初撮り 【個人撮影】 ちゃん",
        "Ｆｕｌｌｗｉｄｔｈ ＆ half-width & mixed",
        "Emoji 🎬✨ and combining é and ZWJ 👩‍💻",
        "A &amp; B",  # a literal entity survives publication untouched (no decoding here)
        "  leading and trailing spaces kept  ",
    ],
)
def test_unicode_titles_are_preserved_exactly(title):
    record = prepare_publication(make_plan(N), make_aggregate(N, title=title))
    assert record.metadata.title == title
    assert record.metadata.title.encode("utf-8") == title.encode("utf-8")
