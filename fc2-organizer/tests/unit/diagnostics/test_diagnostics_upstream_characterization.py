"""P4-C9 contract section 9.0 U-1..U-5 / section 28.1 "upstream characterization" (UC-1..UC-9).

These tests pin the *upstream* facts the dispatch-safety design relies on (public-constructor behaviour of
``NormalizedMetadata`` / ``AggregationResult`` / Phase 3 merge, and a language-level fact about mapping lookup).
If an upstream change makes one of them fail, the contract must be revised; a failure here is never a licence
to change the upstream."""

from __future__ import annotations

import types

import pytest
from fc2_metadata_core.aggregation import AggregationPolicy, merge_source_results
from fc2_metadata_core.aggregation.policy import FIELD_ORDER
from fc2_metadata_core.errors import MetadataContractError
from fc2_metadata_core.models import NormalizedMetadata, SourceResult, SourceStatus
from fc2_organizer.diagnostics.models import MAX_PROVENANCE_KEYS, PROVENANCE_FIELD_ORDER
from support.scripted_adapters import ok

from . import _builders as b

FULL_FIELDS = dict(studio="S", publisher="P", release="2020-01-01", runtime=90, plot="pl", actors=("a",),
                   tags=("t",), poster_urls=("https://x.invalid/p",), thumb_urls=("https://x.invalid/t",),
                   fanart_urls=("https://x.invalid/f",), extrafanart=("https://x.invalid/e",),
                   source_urls=("https://x.invalid/s",), external_ids={"k": "v"})


@pytest.fixture(autouse=True)
def fresh_hits():
    b.reset_hits()
    yield
    b.reset_hits()


def metadata_with(field_sources):
    return NormalizedMetadata(number=b.NUMBER, title="T", field_sources=field_sources)


def test_uc1_a_str_subclass_key_is_accepted_and_stored_unnormalised():
    metadata = metadata_with({b.EvilStr("title"): ("a",)})
    (key,) = list(metadata.field_sources)
    assert type(key) is b.EvilStr and type(key) is not str


def test_uc2_the_upstream_construction_itself_runs_the_subclass_hooks():
    metadata_with({b.EvilStr("title"): ("a",)})
    assert b.HITS["hash"] > 0  # hence tests must reset the sentinels after the upstream construction


@pytest.mark.parametrize("bad_key", [1, b"title", None, ("title",), 1.5])
def test_uc3_a_non_str_key_is_rejected_by_the_upstream(bad_key):
    with pytest.raises(MetadataContractError):
        metadata_with({bad_key: ("a",)})


def test_uc4_field_sources_is_an_immutable_exact_mappingproxy_with_tuple_values():
    metadata = metadata_with({"title": ["a", "b"]})
    assert type(metadata.field_sources) is types.MappingProxyType
    assert type(metadata.field_sources["title"]) is tuple and metadata.field_sources["title"] == ("a", "b")
    with pytest.raises(TypeError):
        metadata.field_sources["x"] = ("a",)
    with pytest.raises(TypeError):
        del metadata.field_sources["title"]


def test_uc5_the_input_mapping_is_snapshotted_and_not_aliased():
    caller = {"title": ["a"]}
    metadata = metadata_with(caller)
    caller["number"] = ["z"]
    caller["title"].append("late")
    del caller["title"]
    assert dict(metadata.field_sources) == {"title": ("a",)}

    from collections.abc import Mapping

    class Live(Mapping):
        data = {"title": ("a",)}

        def __getitem__(self, key):
            return self.data[key]

        def __iter__(self):
            return iter(self.data)

        def __len__(self):
            return len(self.data)

    live = Live()
    metadata = metadata_with(live)
    live.data["number"] = ("z",)
    assert dict(metadata.field_sources) == {"title": ("a",)}


def test_uc6_a_str_subclass_source_id_in_a_value_tuple_is_accepted_and_kept():
    metadata = metadata_with({"title": (b.EvilStr("src_a"),)})
    assert type(metadata.field_sources["title"][0]) is b.EvilStr


def test_uc7_public_constructors_accept_str_subclass_keys_and_source_ids():
    metadata = metadata_with({b.EvilStr("title"): ("src_a",)})
    result = b.make_source_result("src_a")
    aggregation = b.make_aggregation([result], metadata=metadata)
    assert type(next(iter(aggregation.metadata.field_sources))) is b.EvilStr
    evil_id = SourceResult(source_id=b.EvilStr("src_e"), status=SourceStatus.SUCCESS,
                           metadata=b.make_metadata_core(), elapsed_ms=1.0)
    assert type(evil_id.source_id) is b.EvilStr
    aggregation = b.make_aggregation([evil_id], field_sources={"number": (b.EvilStr("src_e"),)})
    assert type(aggregation.contributing_source_ids[0]) is b.EvilStr


def test_uc8_the_real_phase_3_producer_never_exceeds_the_published_field_set():
    number = b.NUMBER
    order = ("src_a", "src_b", "src_c")
    results = [ok(source, number, "T" + source, **FULL_FIELDS) for source in order]
    aggregation = merge_source_results(number, results, AggregationPolicy.build(order))
    keys = list(aggregation.metadata.field_sources)
    assert set(keys) <= set(FIELD_ORDER) and keys == list(FIELD_ORDER)  # fully populated: exactly all 15
    assert len(keys) == 15 <= MAX_PROVENANCE_KEYS
    assert PROVENANCE_FIELD_ORDER == tuple(FIELD_ORDER)


def test_uc9_scanning_keys_runs_no_hook_but_a_membership_test_runs_the_subclass_eq():
    proxy = metadata_with({b.EvilStr("title"): ("a",)}).field_sources
    b.reset_hits()
    for key in proxy:
        assert type(key) is not str
    assert b.total_hits() == 0
    assert "title" in proxy
    assert b.HITS["eq"] > 0
