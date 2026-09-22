"""P4-C3 Publication Synthetic Gate (contract section 13).

Several hundred synthetic plan + aggregate pairs -- SUCCESS / PARTIAL mixed,
Unicode titles, several source-result combinations (single-attempt, retried,
NOT_FOUND gaps, BLOCKED / NETWORK / PARSE failures) -- all offline. Asserts:

* every matching identity is accepted;
* every mismatch (each item's plan against a neighbour's aggregate, plus a
  forged metadata-number mismatch) is rejected, and every FAILED aggregate too;
* the output is deterministic (a second full pass is equal item by item);
* every record is deeply immutable and holds no raw diagnostics;
* the whole gate runs with every filesystem and network API trapped.
"""

from __future__ import annotations

import dataclasses

import pytest

from fc2_metadata_core.aggregation import AggregateStatus, AggregationResult
from fc2_metadata_core.models import NormalizedMetadata
from fc2_organizer.publication import (
    AggregationNotPublishableError,
    PublicationIdentityMismatchError,
    PublicationRecord,
    prepare_publication,
)

from ._builders import SECRET_MARKER, make_aggregate, make_plan
from ._guards import FORBIDDEN_TYPES, install_traps, walk

GATE_SIZE = 400
KINDS = ("success", "partial", "partial_retry")
TITLE_STEMS = (
    "Plain title",
    "素人・初撮り【個人撮影】",
    "Ｆｕｌｌｗｉｄｔｈ ＆ half",
    "Emoji 🎬 é",
    "A &amp; B",
    "Ünïcödé — dash «quotes»",
)


def number_for(i: int) -> str:
    # 6- and 7-digit canonical numbers, spread over the range
    return f"FC2-{100000 + i * 7919}" if i % 5 == 0 else f"FC2-{1000000 + i * 104729 % 8999999}"


def build_inputs():
    items = []
    for i in range(GATE_SIZE):
        number = number_for(i)
        kind = KINDS[i % len(KINDS)]
        title = f"{TITLE_STEMS[i % len(TITLE_STEMS)]} #{i}"
        extra = {"actors": [f"Actor {i}", "共演者"], "external_ids": {"gate": str(i)}} if i % 2 else {}
        items.append((make_plan(number, index=i), make_aggregate(number, title=title, kind=kind, **extra), title))
    return items


def forge_metadata_number(aggregate: AggregationResult, number: str) -> AggregationResult:
    clone = object.__new__(AggregationResult)
    for field in dataclasses.fields(AggregationResult):
        object.__setattr__(clone, field.name, getattr(aggregate, field.name))
    object.__setattr__(clone, "metadata", NormalizedMetadata(number=number, title="forged"))
    return clone


def test_publication_synthetic_gate(monkeypatch):
    items = build_inputs()
    numbers = [plan.canonical_number for plan, _, _ in items]
    assert len(set(numbers)) == GATE_SIZE, "gate numbers must be distinct for the mismatch pass to mean anything"
    failed = [make_aggregate(n, kind="failed") for n in numbers[:50]]

    install_traps(monkeypatch)  # zero filesystem / network for the whole gate

    first_pass = [prepare_publication(plan, aggregate) for plan, aggregate, _ in items]
    second_pass = [prepare_publication(plan, aggregate) for plan, aggregate, _ in items]

    statuses = {AggregateStatus.SUCCESS: 0, AggregateStatus.PARTIAL: 0}
    for (plan, aggregate, title), rec, again in zip(items, first_pass, second_pass):
        assert isinstance(rec, PublicationRecord)
        assert rec == again  # deterministic
        assert rec.plan is plan and rec.metadata is aggregate.metadata
        assert rec.number == plan.canonical_number == aggregate.number == rec.metadata.number
        assert rec.metadata.title == title
        statuses[rec.aggregate_status] += 1
        with pytest.raises(dataclasses.FrozenInstanceError):
            rec.metadata = None  # type: ignore[misc]
        for path, obj in walk(rec):
            assert not isinstance(obj, FORBIDDEN_TYPES), path
            assert not (isinstance(obj, str) and SECRET_MARKER in obj), path
    assert statuses[AggregateStatus.SUCCESS] > 100 and statuses[AggregateStatus.PARTIAL] > 200

    mismatches = 0
    for i, (plan, _, _) in enumerate(items):
        _, neighbour, _ = items[(i + 1) % GATE_SIZE]
        with pytest.raises(PublicationIdentityMismatchError):
            prepare_publication(plan, neighbour)
        mismatches += 1
        _, own, _ = items[i]
        with pytest.raises(PublicationIdentityMismatchError):
            prepare_publication(plan, forge_metadata_number(own, numbers[(i + 7) % GATE_SIZE]))
        mismatches += 1
    assert mismatches == 2 * GATE_SIZE

    for plan_index, aggregate in enumerate(failed):
        with pytest.raises(AggregationNotPublishableError):
            prepare_publication(items[plan_index][0], aggregate)
