"""Pure field-level merge: no network, no asyncio, no adapters.

``merge_source_results(number, results, policy)`` is a pure function; these
tests are the bulk of the aggregation tests so merge correctness never needs a
network. Numbers in the section titles refer to the C1 required-test list.
"""

from __future__ import annotations

import copy
import random

import pytest

from fc2_metadata_core.aggregation import (
    AggregateStatus,
    AggregationInputError,
    AggregationPolicy,
    merge_source_results,
)
from fc2_metadata_core.errors import InvalidCanonicalNumberInputError
from fc2_metadata_core.models.metadata import NormalizedMetadata
from fc2_metadata_core.models.source_result import SourceErrorKind, SourceResult, SourceStatus

from support.scripted_adapters import failed, ok

N = "FC2-4979299"
ABC = ("a", "b", "c")


def policy(order=ABC, **overrides):
    return AggregationPolicy.build(order, overrides or None)


def merge(results, pol=None, number=N):
    return merge_source_results(number, results, pol or policy(tuple(r.source_id for r in results)))


NOT_FOUND = SourceStatus.NOT_FOUND
NETWORK = SourceStatus.NETWORK_ERROR


# ---- scalars: 1, 2, 3, 8, 9 -----------------------------------------------------------------


def test_01_title_conflict_is_won_by_the_higher_priority_source():
    result = merge([ok("a", N, "Title A"), ok("b", N, "Title B")])
    assert result.metadata.title == "Title A"
    assert result.metadata.field_sources["title"] == ("a",)
    (conflict,) = [c for c in result.conflicts if c.field == "title"]
    assert (conflict.selected_source_id, conflict.selected_value) == ("a", "Title A")
    assert conflict.alternatives == (("b", "Title B"),)


def test_02_per_field_override_makes_the_other_source_win():
    result = merge([ok("a", N, "Title A"), ok("b", N, "Title B")], policy(("a", "b"), title=["b"]))
    assert result.metadata.title == "Title B"
    assert result.metadata.field_sources["title"] == ("b",)


def test_02b_an_override_for_one_field_does_not_change_others():
    result = merge(
        [ok("a", N, "Title A", studio="Studio A"), ok("b", N, "Title B", studio="Studio B")],
        policy(("a", "b"), title=["b"]),
    )
    assert (result.metadata.title, result.metadata.studio) == ("Title B", "Studio A")


def test_03_identical_titles_keep_the_value_and_record_all_corroborating_sources_in_priority_order():
    result = merge([ok("a", N, "Same"), ok("b", N, "Same"), ok("c", N, "Other")])
    assert result.metadata.title == "Same"
    assert result.metadata.field_sources["title"] == ("a", "b")
    reordered = merge([ok("a", N, "Same"), ok("b", N, "Same"), ok("c", N, "Other")], policy(ABC, title=["c", "b"]))
    assert reordered.metadata.title == "Other"
    identical = merge([ok("a", N, "Same"), ok("b", N, "Same")], policy(("a", "b"), title=["b", "a"]))
    assert identical.metadata.field_sources["title"] == ("b", "a")  # priority order, not config order
    assert not [c for c in identical.conflicts if c.field == "title"]


def test_08_runtime_conflict_is_deterministic():
    results = [ok("a", N, runtime=55), ok("b", N, runtime=56), ok("c", N, runtime=55)]
    merged = merge(results)
    assert merged.metadata.runtime == 55
    assert merged.metadata.field_sources["runtime"] == ("a", "c")
    (conflict,) = [c for c in merged.conflicts if c.field == "runtime"]
    assert conflict.alternatives == (("b", 56),)
    assert merge(results, policy(ABC, runtime=["b"])).metadata.runtime == 56


def test_09_release_conflict_is_deterministic():
    results = [ok("a", N, release="2026-01-04"), ok("b", N, release="2026-01-02")]
    assert merge(results).metadata.release == "2026-01-04"
    assert merge(results, policy(("a", "b"), release=["b"])).metadata.release == "2026-01-02"


def test_scalar_skips_missing_and_blank_values_and_falls_through_to_the_next_source():
    results = [ok("a", N, "A"), ok("b", N, "B", studio="   ", publisher="Pub B"), ok("c", N, "C", studio="Studio C")]
    merged = merge(results)
    assert merged.metadata.studio == "Studio C"  # a: absent, b: blank
    assert merged.metadata.field_sources["studio"] == ("c",)
    assert merged.metadata.publisher == "Pub B"


def test_a_scalar_nobody_provides_is_absent_and_has_no_provenance():
    merged = merge([ok("a", N, "A"), ok("b", N, "B")])
    assert merged.metadata.plot is None and "plot" not in merged.metadata.field_sources


def test_runtime_zero_counts_as_a_value():
    merged = merge([ok("a", N, runtime=0), ok("b", N, runtime=55)])
    assert merged.metadata.runtime == 0


def test_number_is_always_the_requested_number_with_provenance_of_every_contributor():
    merged = merge([ok("a", N), ok("b", N), failed("c", NOT_FOUND)])
    assert merged.metadata.number == N
    assert merged.metadata.field_sources["number"] == ("a", "b")


# ---- collections: 4, 5, 6 ----------------------------------------------------------------------


def test_04_actors_are_an_ordered_unique_union_in_priority_order():
    merged = merge([ok("a", N, actors=("Alice", "Bob")), ok("b", N, actors=("Bob", "Carol"))])
    assert merged.metadata.actors == ("Alice", "Bob", "Carol")
    assert merged.metadata.field_sources["actors"] == ("a", "b")
    swapped = merge([ok("a", N, actors=("Alice", "Bob")), ok("b", N, actors=("Bob", "Carol"))], policy(("a", "b"), actors=["b"]))
    assert swapped.metadata.actors == ("Bob", "Carol", "Alice")
    assert isinstance(merged.metadata.actors, tuple)


def test_05_tags_ordered_union():
    merged = merge([ok("a", N, tags=("t1", "t2")), ok("b", N, tags=("t2", "t3")), ok("c", N, tags=("t3", "t1", "t4"))])
    assert merged.metadata.tags == ("t1", "t2", "t3", "t4")
    assert merged.metadata.field_sources["tags"] == ("a", "b", "c")


def test_06_source_urls_ordered_union():
    merged = merge(
        [ok("a", N, source_urls=("https://a.example/1",)), ok("b", N, source_urls=("https://b.example/1", "https://a.example/1"))]
    )
    assert merged.metadata.source_urls == ("https://a.example/1", "https://b.example/1")
    assert merged.metadata.field_sources["source_urls"] == ("a", "b")


def test_collections_dedupe_by_exact_string_equality_only():
    # no case folding, no whitespace normalisation, no translation
    merged = merge([ok("a", N, tags=("Tag",)), ok("b", N, tags=("tag", "Tag ", "タグ", "Tag"))])
    assert merged.metadata.tags == ("Tag", "tag", "Tag ", "タグ")


def test_blank_collection_items_are_skipped_and_a_source_with_only_blanks_is_not_provenance():
    merged = merge([ok("a", N, tags=("  ", "")), ok("b", N, tags=("x",))])
    assert merged.metadata.tags == ("x",)
    assert merged.metadata.field_sources["tags"] == ("b",)


def test_every_collection_field_merges_the_same_way():
    fields = ("actors", "tags", "poster_urls", "thumb_urls", "fanart_urls", "extrafanart", "source_urls")
    a = ok("a", N, **{f: (f"{f}-1", f"{f}-2") for f in fields})
    b = ok("b", N, **{f: (f"{f}-2", f"{f}-3") for f in fields})
    merged = merge([a, b])
    for f in fields:
        assert getattr(merged.metadata, f) == (f"{f}-1", f"{f}-2", f"{f}-3"), f
        assert merged.metadata.field_sources[f] == ("a", "b")


# ---- external_ids: 7 ----------------------------------------------------------------------------


def test_07_external_ids_collision_is_first_wins_never_last_write_wins():
    merged = merge(
        [ok("a", N, external_ids={"x": "A1", "shared": "from-a"}), ok("b", N, external_ids={"shared": "from-b", "y": "B1"})]
    )
    assert dict(merged.metadata.external_ids) == {"x": "A1", "shared": "from-a", "y": "B1"}
    (conflict,) = [c for c in merged.conflicts if c.field == "external_ids"]
    assert conflict.key == "shared" and conflict.selected_source_id == "a"
    assert conflict.selected_value == "from-a" and conflict.alternatives == (("b", "from-b"),)
    flipped = merge(
        [ok("a", N, external_ids={"shared": "from-a"}), ok("b", N, external_ids={"shared": "from-b"})],
        policy(("a", "b"), external_ids=["b"]),
    )
    assert dict(flipped.metadata.external_ids) == {"shared": "from-b"}


def test_external_ids_same_key_same_value_is_not_a_conflict():
    merged = merge([ok("a", N, external_ids={"k": "v"}), ok("b", N, external_ids={"k": "v"})])
    assert dict(merged.metadata.external_ids) == {"k": "v"}
    assert not merged.conflicts
    assert merged.metadata.field_sources["external_ids"] == ("a", "b")


# ---- aggregate status: 10-14 --------------------------------------------------------------------


def test_10_one_success_and_two_not_found_is_success():
    result = merge([ok("a", N), failed("b", NOT_FOUND), failed("c", NOT_FOUND)])
    assert result.status is AggregateStatus.SUCCESS
    assert result.contributing_source_ids == ("a",)
    assert result.operational_failure_source_ids == () and result.not_found_source_ids == ("b", "c")


def test_11_success_plus_network_error_is_partial():
    result = merge([ok("a", N), failed("b", NETWORK)])
    assert result.status is AggregateStatus.PARTIAL and result.metadata.meets_minimum_success()
    assert result.operational_failure_source_ids == ("b",)


def test_12_success_blocked_not_found_is_partial():
    result = merge([ok("a", N), failed("b", SourceStatus.BLOCKED), failed("c", NOT_FOUND)])
    assert result.status is AggregateStatus.PARTIAL


@pytest.mark.parametrize(
    "status",
    [SourceStatus.BLOCKED, SourceStatus.RATE_LIMITED, SourceStatus.NETWORK_ERROR, SourceStatus.PARSE_ERROR, SourceStatus.INVALID_RESPONSE],
)
def test_every_operational_failure_kind_downgrades_success_to_partial(status):
    assert merge([ok("a", N), failed("b", status)]).status is AggregateStatus.PARTIAL


def test_13_all_not_found_is_failed_and_keeps_every_source_result():
    result = merge([failed("a", NOT_FOUND), failed("b", NOT_FOUND), failed("c", NOT_FOUND)])
    assert result.status is AggregateStatus.FAILED and result.metadata is None
    assert [r.status for r in result.source_results] == [NOT_FOUND] * 3
    assert result.contributing_source_ids == ()


def test_14_not_found_network_error_blocked_is_failed_and_keeps_every_source_result():
    inputs = [failed("a", NOT_FOUND), failed("b", NETWORK), failed("c", SourceStatus.BLOCKED)]
    result = merge(inputs)
    assert result.status is AggregateStatus.FAILED and result.metadata is None
    assert result.source_results == tuple(inputs)


def test_all_operational_failures_is_failed():
    assert merge([failed("a", NETWORK), failed("b", NETWORK)]).status is AggregateStatus.FAILED


def test_partial_metadata_attached_to_a_parse_error_is_never_used():
    partial = SourceResult(
        source_id="a", status=SourceStatus.PARSE_ERROR, elapsed_ms=1.0,
        metadata=NormalizedMetadata(number=N, tags=("leak",)),
        error_kind=SourceErrorKind.PARSE_ERROR, error_detail="a: partial",
    )
    result = merge([partial, ok("b", N, "B")])
    assert result.metadata.tags == () and result.metadata.title == "B"
    assert result.status is AggregateStatus.PARTIAL


# ---- fail closed: 16, 17, 24 ------------------------------------------------------------------


def test_16_wrong_metadata_number_is_invalid_response_and_cannot_contaminate():
    other = "FC2-1111111"
    result = merge([ok("a", other, "A DIFFERENT FILM", tags=("evil",), external_ids={"k": "evil"}), ok("b", N, "Right film")])
    assert result.metadata.title == "Right film"
    assert result.metadata.tags == () and dict(result.metadata.external_ids) == {}
    bad = result.result_for("a")
    assert bad.status is SourceStatus.INVALID_RESPONSE and bad.metadata is None
    assert other in bad.error_detail and N in bad.error_detail
    assert result.status is AggregateStatus.PARTIAL and result.contributing_source_ids == ("b",)


def test_16b_only_a_wrong_number_source_means_failed_not_a_fabricated_success():
    result = merge([ok("a", "FC2-1111111", "Other film")])
    assert result.status is AggregateStatus.FAILED and result.metadata is None
    assert result.source_results[0].status is SourceStatus.INVALID_RESPONSE


def test_17_wrong_source_result_source_id_fails_closed():
    stolen = ok("evil_source", N, "Title from someone else", tags=("evil",))
    result = merge([stolen, ok("b", N, "B")], policy(("a", "b")))
    slot = result.result_for("a")
    assert slot is not None and slot.status is SourceStatus.INVALID_RESPONSE and slot.metadata is None
    assert result.result_for("evil_source") is None
    assert result.metadata.title == "B" and result.metadata.tags == ()
    assert result.status is AggregateStatus.PARTIAL


def test_a_non_source_result_object_fails_closed():
    result = merge_source_results(N, ["not a result", ok("b", N, "B")], policy(("a", "b")))
    assert result.result_for("a").status is SourceStatus.INVALID_RESPONSE
    assert result.status is AggregateStatus.PARTIAL


def test_24_forged_field_sources_cannot_change_final_provenance():
    forged = {"number": ("b",), "title": ("b",), "tags": ("b", "zzz")}
    a = ok("a", N, "Title A", tags=("ta",), field_sources=forged)
    b = ok("b", N, "Title B", tags=("tb",))
    merged = merge([a, b])
    assert merged.metadata.title == "Title A"
    assert merged.metadata.field_sources["title"] == ("a",)  # not ("b",) as a claimed
    assert merged.metadata.field_sources["tags"] == ("a", "b")
    assert "zzz" not in {s for sources in merged.metadata.field_sources.values() for s in sources}
    assert merged.metadata.field_sources["number"] == ("a", "b")


def test_provenance_only_ever_names_contributing_configured_sources():
    merged = merge([ok("a", N, tags=("t",), field_sources={"tags": ("ghost",)}), failed("b", NOT_FOUND)])
    names = {s for sources in merged.metadata.field_sources.values() for s in sources}
    assert names == {"a"}


# ---- determinism & purity: 15 (order independence at the pure level) ------------------------------


def _fingerprint(result):
    md = result.metadata
    return (
        result.status, md.title, md.actors, md.tags, md.source_urls, tuple(sorted(md.external_ids.items())),
        tuple(sorted(md.field_sources.items())), result.contributing_source_ids,
        tuple(r.source_id for r in result.source_results), tuple((c.field, c.key, c.selected_source_id) for c in result.conflicts),
    )


def test_15_result_depends_only_on_slot_order_not_on_any_hidden_ordering():
    def build():
        return [
            ok("a", N, "A", actors=("x", "y"), tags=("t1",), external_ids={"k": "1"}, runtime=50),
            ok("b", N, "B", actors=("y", "z"), tags=("t2", "t1"), external_ids={"k": "2", "j": "3"}, runtime=51),
            ok("c", N, "C", actors=("z", "w"), tags=("t3",), runtime=50),
        ]

    reference = _fingerprint(merge(build()))
    for _ in range(25):
        assert _fingerprint(merge(build())) == reference


def test_merge_does_not_mutate_its_inputs_and_returns_new_immutable_metadata():
    results = [ok("a", N, "A", tags=("t",)), ok("b", N, "B")]
    snapshot = copy.deepcopy([(r.source_id, r.status, r.metadata.title, r.metadata.tags, dict(r.metadata.field_sources)) for r in results])
    merged = merge(results)
    after = [(r.source_id, r.status, r.metadata.title, r.metadata.tags, dict(r.metadata.field_sources)) for r in results]
    assert snapshot == after
    assert merged.metadata is not results[0].metadata and merged.metadata is not results[1].metadata
    with pytest.raises(Exception):
        merged.metadata.title = "x"  # type: ignore[misc]
    with pytest.raises(Exception):
        merged.metadata.field_sources["title"] = ("x",)  # type: ignore[index]
    with pytest.raises(Exception):
        merged.status = AggregateStatus.FAILED  # type: ignore[misc]


def test_priority_permutation_changes_only_what_it_should():
    base = [ok("a", N, "A", tags=("a1",)), ok("b", N, "B", tags=("b1",)), ok("c", N, "C", tags=("c1",))]
    rng = random.Random(7)
    for _ in range(12):
        order = list(ABC)
        rng.shuffle(order)
        pol = policy(ABC, title=order, tags=order)
        merged = merge(base, pol)
        assert merged.metadata.title == {"a": "A", "b": "B", "c": "C"}[order[0]]
        assert merged.metadata.tags == tuple(f"{sid}1" for sid in order)


# ---- input validation ---------------------------------------------------------------------------------


def test_result_count_must_match_the_policy():
    with pytest.raises(AggregationInputError):
        merge_source_results(N, [ok("a", N)], policy(("a", "b")))
    with pytest.raises(AggregationInputError):
        merge_source_results(N, [ok("a", N), ok("b", N)], policy(("a",)))


@pytest.mark.parametrize("bad", ["4979299", "FC2-1234567\n", "fc2-1234567", "", "FC2-１２３４５"])
def test_non_canonical_number_is_a_caller_error(bad):
    with pytest.raises(InvalidCanonicalNumberInputError):
        merge_source_results(bad, [ok("a", N)], policy(("a",)))


def test_result_carries_disabled_ids_and_elapsed_and_is_frozen():
    result = merge_source_results(N, [ok("a", N)], policy(("a",)), disabled_source_ids=("z",), elapsed_ms=12.5)
    assert result.disabled_source_ids == ("z",) and result.elapsed_ms == 12.5 and result.source_order == ("a",)
