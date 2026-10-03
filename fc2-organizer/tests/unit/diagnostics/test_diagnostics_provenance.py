"""P4-C9 contract sections 9.2 item 9 / 9.0 / 28.1 (three rows) -- field provenance:
(a) upstream trust boundary; (b) R2-01 ``field_sources`` key-subclass gate (EvilStr public-constructor gate with
Normal-Key Positive Control); (c) key-scan mutations. Opaque ``mappingproxy`` referent forging (layer C) is out of
the test model and is not tested."""

from __future__ import annotations

import types

import pytest
from fc2_metadata_core.models import NormalizedMetadata, SourceStatus as T
from fc2_organizer.diagnostics import (
    DiagnosticsIntegrityError,
    DiagnosticsResourceLimitError,
    build_preview_diagnostics,
    validation,
)
from fc2_organizer.diagnostics.models import MAX_PROVENANCE_KEYS, PROVENANCE_FIELD_ORDER

from . import _builders as b

EVIL = b.EvilStr
SRC = ("src_a",)
FULL = dict(studio="S", publisher="P", release="2020-01-01", runtime=90, plot="pl", actors=("a",), tags=("t",),
            poster_urls=("https://x.invalid/p",), thumb_urls=("https://x.invalid/t",),
            fanart_urls=("https://x.invalid/f",), extrafanart=("https://x.invalid/e",),
            source_urls=("https://x.invalid/s",), external_ids={"k": "v"})


def metadata_with(field_sources, **fields):
    return NormalizedMetadata(number=b.NUMBER, title="T", field_sources=field_sources, **fields)


def preview_for(field_sources, results=None, **fields):
    results = results or [b.make_source_result("src_a", T.SUCCESS)]
    aggregation = b.make_aggregation(results, metadata=metadata_with(field_sources, **fields))
    return b.preview_of_metadata(b.batch_item_for(aggregation))


def provenance(diag):
    return diag.items[0].metadata.field_provenance


def attempt(preview):
    """Build; return (exception type or None, hits since the reset point). The sentinels are reset *after* the
    whole upstream graph was constructed (contract 28.1 sentinel-reset rule) and before the builder runs."""
    b.reset_hits()
    try:
        build_preview_diagnostics(preview)
    except DiagnosticsIntegrityError as exc:
        return type(exc), dict(b.HITS), exc
    except DiagnosticsResourceLimitError as exc:
        return type(exc), dict(b.HITS), exc
    return None, dict(b.HITS), None


# ---- (a) upstream trust boundary


def test_normal_public_construction_completes_with_the_published_provenance():
    diag = build_preview_diagnostics(preview_for({"number": SRC, "title": SRC}))
    assert [(p.field, p.source_ids) for p in provenance(diag)] == [("number", SRC), ("title", SRC)]


def test_a_failed_aggregate_has_no_provenance_and_runs_no_key_scan(monkeypatch):
    results = [b.make_source_result("src_a", T.NOT_FOUND)]
    aggregation = b.make_aggregation(results)
    preview = b.preview_of_metadata(b.batch_item_for(aggregation))

    def boom(*args, **kwargs):
        raise AssertionError("key scan ran for a FAILED aggregate")

    monkeypatch.setattr(validation, "scan_field_sources", boom)
    assert provenance(build_preview_diagnostics(preview)) == ()


def test_a_non_exact_mappingproxy_field_sources_fails_closed():
    preview = preview_for({"number": SRC})
    metadata = preview.metadata_batch.items[0].aggregation_result.metadata
    for fake in ({"number": SRC}, types.MappingProxyType, None, [("number", SRC)]):
        b.poke(metadata, field_sources=fake)
        with pytest.raises(DiagnosticsIntegrityError):
            build_preview_diagnostics(preview)


@pytest.mark.parametrize("bad", [["src_a"], "src_a", ("src_a", 1), (b"src_a",), (), ("src_a", "src_a"),
                                 ("unknown_source",), (EVIL("src_a"),), None, {"src_a"}])
def test_a_known_key_value_must_be_an_exact_tuple_of_unique_contributing_str_ids(bad):
    preview = preview_for({"number": SRC})
    metadata = preview.metadata_batch.items[0].aggregation_result.metadata
    b.poke(metadata, field_sources=types.MappingProxyType({"number": bad}))
    b.reset_hits()
    with pytest.raises(DiagnosticsIntegrityError):
        build_preview_diagnostics(preview)
    assert b.total_hits() == 0


def test_a_value_longer_than_the_source_limit_fails_closed():
    many = tuple("s%d" % i for i in range(65))
    preview = preview_for({"number": SRC})
    metadata = preview.metadata_batch.items[0].aggregation_result.metadata
    b.poke(metadata, field_sources=types.MappingProxyType({"number": many}))
    with pytest.raises(DiagnosticsIntegrityError):
        build_preview_diagnostics(preview)


def test_output_follows_the_fixed_field_order_not_the_insertion_order():
    forward = {name: SRC for name in PROVENANCE_FIELD_ORDER}
    reverse = dict(reversed(list(forward.items())))
    shuffled = {name: SRC for name in sorted(PROVENANCE_FIELD_ORDER, key=lambda n: hash(n) % 7)}
    outputs = [provenance(build_preview_diagnostics(preview_for(source, **FULL)))
               for source in (forward, reverse, shuffled)]
    assert outputs[0] == outputs[1] == outputs[2] and repr(outputs[0]) == repr(outputs[1])
    assert [p.field for p in outputs[0]] == list(PROVENANCE_FIELD_ORDER)


def test_unknown_exact_str_keys_are_scanned_and_counted_but_never_projected():
    mapping = {"number": SRC, "unknown_field_1": SRC, "zzz": ("whatever",), "title": SRC}
    diag = build_preview_diagnostics(preview_for(mapping))
    assert [p.field for p in provenance(diag)] == ["number", "title"]
    assert "unknown_field" not in repr(diag) and "whatever" not in repr(diag)


def test_unknown_key_values_are_not_validated_or_read():
    preview = preview_for({"number": SRC})
    metadata = preview.metadata_batch.items[0].aggregation_result.metadata

    class Trip:
        def __getattribute__(self, name):
            raise AssertionError("an unknown key's value was touched")

    b.poke(metadata, field_sources=types.MappingProxyType({"number": SRC, "zzz": Trip()}))
    assert [p.field for p in provenance(build_preview_diagnostics(preview))] == ["number"]


# ---- (b) R2-01: EvilStr public-constructor gate


EVIL_VARIANTS = {
    "known_same_name": lambda: {EVIL("title"): SRC},
    "unknown_name": lambda: {EVIL("zzz"): SRC},
    "first": lambda: {EVIL("zzz"): SRC, "number": SRC, "title": SRC},
    "middle": lambda: {"number": SRC, EVIL("zzz"): SRC, "title": SRC},
    "last": lambda: {"number": SRC, "title": SRC, EVIL("zzz"): SRC},
    "with_legal_keys": lambda: {"number": SRC, "title": SRC, "plot": SRC, EVIL("studio"): SRC},
}


@pytest.mark.parametrize("variant", sorted(EVIL_VARIANTS))
def test_an_evil_str_key_fails_closed_with_no_hook_executed_by_the_builder(variant):
    preview = preview_for(EVIL_VARIANTS[variant](), studio="S", plot="pl")
    (key,) = [k for k in preview.metadata_batch.items[0].aggregation_result.metadata.field_sources
              if type(k) is EVIL]
    assert type(key) is EVIL  # the upstream public constructor really kept the subclass (UC-1)
    exc_type, hits, exc = attempt(preview)
    assert exc_type is DiagnosticsIntegrityError
    assert hits["hash"] == 0 and hits["eq"] == 0 and sum(hits.values()) == 0
    assert "title" not in str(exc) and "zzz" not in str(exc)


def test_hash_collision_variant_never_reaches_a_membership_test():
    class Colliding(b.CollidingStr):
        target = "title"

    preview = preview_for({"title": SRC, Colliding("title"): SRC, "number": SRC})
    keys = list(preview.metadata_batch.items[0].aggregation_result.metadata.field_sources)
    assert len(keys) == 3  # both keys coexist (same hash, never equal)
    exc_type, hits, _ = attempt(preview)
    assert exc_type is DiagnosticsIntegrityError and sum(hits.values()) == 0


def test_the_evil_key_with_a_valid_value_is_not_a_value_validation_false_positive():
    preview = preview_for({EVIL("title"): SRC})
    value = preview.metadata_batch.items[0].aggregation_result.metadata.field_sources
    assert list(value.values()) == [SRC]  # the value alone is perfectly legal
    assert attempt(preview)[0] is DiagnosticsIntegrityError


def test_v4_an_evil_key_ahead_of_an_oversized_scan_decides_the_error_class():
    keys = {EVIL("first"): SRC}
    keys.update({"k%d" % i: SRC for i in range(MAX_PROVENANCE_KEYS + 1)})
    preview = preview_for(keys)
    exc_type, hits, _ = attempt(preview)
    assert exc_type is DiagnosticsIntegrityError and sum(hits.values()) == 0


def test_v4_the_oversized_scan_ahead_of_an_evil_key_is_a_resource_limit_error():
    keys = {"k%d" % i: SRC for i in range(MAX_PROVENANCE_KEYS + 1)}
    keys[EVIL("late")] = SRC
    exc_type, hits, _ = attempt(preview_for(keys))
    assert exc_type is DiagnosticsResourceLimitError and sum(hits.values()) == 0


def test_normal_key_positive_control():
    forward = {name: SRC for name in PROVENANCE_FIELD_ORDER}
    forward.update({"unknown_field_1": SRC, "unknown_field_2": SRC})
    reverse = dict(reversed(list(forward.items())))
    first = build_preview_diagnostics(preview_for(forward, **FULL))
    second = build_preview_diagnostics(preview_for(reverse, **FULL))
    assert [p.field for p in provenance(first)] == list(PROVENANCE_FIELD_ORDER)
    assert repr(first.items[0].metadata) == repr(second.items[0].metadata)
    assert "unknown_field" not in repr(first)


# ---- the 64-key limit (contract 21.2; the S3 resource file repeats the end-to-end bound)


def test_exactly_the_limit_passes_and_one_more_is_a_resource_limit_error():
    at_limit = {name: SRC for name in PROVENANCE_FIELD_ORDER}
    at_limit.update({"u%d" % i: SRC for i in range(MAX_PROVENANCE_KEYS - len(at_limit))})
    assert len(at_limit) == MAX_PROVENANCE_KEYS
    assert len(provenance(build_preview_diagnostics(preview_for(at_limit, **FULL)))) == 15
    at_limit["one_more"] = SRC
    with pytest.raises(DiagnosticsResourceLimitError):
        build_preview_diagnostics(preview_for(at_limit, **FULL))


def test_the_scan_stops_at_the_65th_key_and_does_not_read_further():
    keys = {"k%d" % i: SRC for i in range(MAX_PROVENANCE_KEYS)}
    keys[EVIL("beyond")] = SRC  # the 65th key
    keys.update({"x%d" % i: SRC for i in range(10 * MAX_PROVENANCE_KEYS)})
    exc_type, hits, _ = attempt(preview_for(keys))
    assert exc_type is DiagnosticsResourceLimitError and sum(hits.values()) == 0


def test_ten_times_the_limit_still_fails_with_the_resource_limit_error():
    keys = {"k%d" % i: SRC for i in range(10 * MAX_PROVENANCE_KEYS)}
    assert attempt(preview_for(keys))[0] is DiagnosticsResourceLimitError


PROXY_TYPE = types.MappingProxyType
SPIED = ("list", "dict", "sorted", "set", "len")


def proxy_spy(name, real, trips):
    def spy(*args, **kwargs):
        if args and type(args[0]) is PROXY_TYPE:
            trips.append(name)
        return real(*args, **kwargs)

    return spy


def install_tripwire(monkeypatch):
    """Shadow the materialising builtins inside the ``validation`` namespace; ``trips`` records every call whose
    first argument is a ``mappingproxy`` (``tuple`` / ``frozenset`` are left alone: the module compares exact
    types with them)."""
    import builtins

    trips = []
    for name in SPIED:
        monkeypatch.setattr(validation, name, proxy_spy(name, getattr(builtins, name), trips), raising=False)
    return trips


def test_the_proxy_is_never_materialised(monkeypatch):
    trips = install_tripwire(monkeypatch)
    build_preview_diagnostics(preview_for({name: SRC for name in PROVENANCE_FIELD_ORDER}, **FULL))
    with pytest.raises(DiagnosticsResourceLimitError):
        build_preview_diagnostics(preview_for({"k%d" % i: SRC for i in range(10 * MAX_PROVENANCE_KEYS)}))
    assert trips == []


def test_the_tripwire_is_not_vacuous(monkeypatch):
    trips = install_tripwire(monkeypatch)
    proxy = types.MappingProxyType({"a": 1})
    for name in SPIED:
        getattr(validation, name)(proxy)
    assert sorted(set(trips)) == sorted(SPIED)


# ---- (c) mutations of the key scan: standalone deviant re-implementations, each killed by a gate scenario


def mutant_scan(*, interleave_lookup=False, skip_type_check=False, only_known_checked=False, materialise=None,
                limit=MAX_PROVENANCE_KEYS, count_after_check=False, skip_unknown_count=False,
                read_past_limit=False):
    """The real scan (contract 9.2 item 9) with one deliberate defect; with every flag off it is equivalent."""

    def scan(metadata, contributing):
        proxy = metadata.field_sources
        if type(proxy) is not PROXY_TYPE:
            validation.fail("field_sources must be a mappingproxy")
        if materialise is not None:
            materialise(proxy)  # defect: materialise before the bounded scan
        if interleave_lookup:  # defect: look names up while (before) the keys are verified
            for name in PROVENANCE_FIELD_ORDER:
                if name in proxy:
                    pass
        seen = 0
        for key in proxy:
            known = (type(key) is str and key in PROVENANCE_FIELD_ORDER) if only_known_checked else True
            if skip_unknown_count and only_known_checked and not known:
                continue
            if not count_after_check:
                seen += 1
            if seen > limit and not read_past_limit:
                validation.over_limit("limit")
            if not skip_type_check and (known or not only_known_checked) and type(key) is not str:
                validation.fail("keys must be exact str")
            if count_after_check:
                seen += 1
        found = []
        for name in PROVENANCE_FIELD_ORDER:
            if name in proxy:
                found.append((name, proxy[name]))
        return tuple(found)

    return scan


def run_with(monkeypatch, mutant, preview):
    """(error class or None, hits) of one build with the given ``scan_field_sources`` implementation."""
    monkeypatch.setattr(validation, "scan_field_sources", mutant)
    try:
        return attempt(preview)[:2]
    finally:
        monkeypatch.undo()


def exact_limit_keys():
    keys = {name: SRC for name in PROVENANCE_FIELD_ORDER}
    keys.update({"u%d" % i: SRC for i in range(MAX_PROVENANCE_KEYS - len(keys))})
    return keys


GATES = {  # scenario -> (preview factory, expected error class, hooks allowed)
    "evil_known": (lambda: preview_for({EVIL("title"): SRC}), DiagnosticsIntegrityError),
    "evil_unknown": (lambda: preview_for({EVIL("zzz"): SRC, "number": SRC}), DiagnosticsIntegrityError),
    "over_limit": (lambda: preview_for(dict(exact_limit_keys(), one_more=SRC), **FULL),
                   DiagnosticsResourceLimitError),
    "exact_limit": (lambda: preview_for(exact_limit_keys(), **FULL), None),
    "unknown_only_over": (lambda: preview_for({"u%d" % i: SRC for i in range(MAX_PROVENANCE_KEYS + 1)}),
                          DiagnosticsResourceLimitError),
    "early_stop": (lambda: preview_for({**{"k%d" % i: SRC for i in range(MAX_PROVENANCE_KEYS)},
                                        EVIL("beyond"): SRC, **{"x%d" % i: SRC for i in range(20)}}),
                   DiagnosticsResourceLimitError),
}


def gate_passes(monkeypatch, mutant, name):
    factory, expected = GATES[name]
    exc_type, hits = run_with(monkeypatch, mutant, factory())
    return exc_type is expected and sum(hits.values()) == 0


@pytest.mark.parametrize("name", sorted(GATES))
def test_the_unmutated_harness_scan_passes_every_gate_scenario(monkeypatch, name):
    """Non-vacuity of the harness: with every defect off, the reference re-implementation and the real code both
    satisfy every scenario, so a failure below is attributable to the single defect."""
    assert gate_passes(monkeypatch, mutant_scan(), name)
    assert gate_passes(monkeypatch, validation.scan_field_sources, name)


KILLS = [
    ("lookup_before_verification", dict(interleave_lookup=True), "evil_known"),
    ("type_check_skipped", dict(skip_type_check=True), "evil_known"),
    ("type_check_skipped_unknown", dict(skip_type_check=True), "evil_unknown"),
    ("only_known_keys_checked", dict(only_known_checked=True), "evil_unknown"),
    ("limit_off_by_one_exact", dict(limit=MAX_PROVENANCE_KEYS - 1), "exact_limit"),
    ("limit_removed", dict(limit=10**9), "over_limit"),
    ("limit_relaxed_by_one", dict(limit=MAX_PROVENANCE_KEYS + 1), "over_limit"),
    ("count_after_check", dict(count_after_check=True), "over_limit"),
    ("unknown_not_counted", dict(only_known_checked=True, skip_unknown_count=True), "unknown_only_over"),
    ("read_past_the_limit", dict(read_past_limit=True), "early_stop"),
]


@pytest.mark.parametrize(("label", "defect", "scenario"), KILLS, ids=[k[0] for k in KILLS])
def test_each_key_scan_mutation_is_killed(monkeypatch, label, defect, scenario):
    assert not gate_passes(monkeypatch, mutant_scan(**defect), scenario), label


@pytest.mark.parametrize("name", SPIED)
def test_a_materialising_scan_is_killed_by_the_tripwire(monkeypatch, name):
    import builtins

    trips = install_tripwire(monkeypatch)
    real = getattr(builtins, name)

    def materialise(proxy):
        validation.__dict__[name](proxy)  # the spy installed in the validation namespace

    assert real is not None
    monkeypatch.setattr(validation, "scan_field_sources", mutant_scan(materialise=materialise))
    build_preview_diagnostics(preview_for({"number": SRC}))
    assert trips == [name]
