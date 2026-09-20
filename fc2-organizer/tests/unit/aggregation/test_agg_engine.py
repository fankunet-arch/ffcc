"""MultiSourceEngine: config + registry + shared client -> AggregationResult.

Two flavours, both offline: scripted adapters (behaviour) and the three REAL
adapters served from verbatim real-response fixtures through ``FakeHttpClient``
(so the default configuration is exercised end to end without a network).
"""

from __future__ import annotations

import asyncio

import pytest

from fc2_metadata_core.aggregation import (
    AggregateStatus,
    AggregationConfig,
    AggregationConfigError,
    MultiSourceEngine,
    SourceConfig,
    default_aggregation_config,
)
from fc2_metadata_core.errors import InvalidCanonicalNumberInputError
from fc2_metadata_core.models.source_result import SourceStatus
from fc2_metadata_core.sources import SourceRegistry
from fc2_metadata_core.sources.adapters import build_default_registry
from fc2_metadata_core.sources.adapters.av123 import Av123Adapter
from fc2_metadata_core.sources.adapters.fc2db_net import Fc2dbNetAdapter
from fc2_metadata_core.sources.adapters.javdb import JavdbAdapter
from fc2_metadata_core.sources.registry import (
    InvalidSourceAdapterError,
    SourceIdMismatchError,
    SourceRegistryError,
)

from support.fake_http_client import FakeHttpClient, make_response
from support.scripted_adapters import failed, ok, scripted_adapter_class
from support.source_fixtures import load_fixture

N = "FC2-4979299"


def registry_of(**scripts):
    registry = SourceRegistry()
    classes = {}
    for source_id, script in scripts.items():
        classes[source_id] = scripted_adapter_class(source_id, script)
        registry.register(source_id, classes[source_id])
    return registry, classes


def run(coro):
    return asyncio.run(coro)


async def _ok(number, client, source_id="x"):
    return ok(source_id, number, "T")


def script_ok(source_id, title="T", **fields):
    async def script(number, client):
        return ok(source_id, number, title, **fields)

    return script


def script_fail(source_id, status):
    async def script(number, client):
        return failed(source_id, status)

    return script


# ---- construction-time validation (nothing touches the network) ---------------------------------------


def test_unknown_source_ids_are_rejected_at_construction_listing_all_of_them():
    registry, _ = registry_of(a=script_ok("a"))
    config = AggregationConfig.create([SourceConfig("a"), SourceConfig("ghost1"), SourceConfig("ghost2")])
    with pytest.raises(AggregationConfigError) as info:
        MultiSourceEngine(config, registry, FakeHttpClient())
    assert "ghost1" in str(info.value) and "ghost2" in str(info.value)


def test_a_disabled_unknown_source_is_not_an_error_and_is_never_built():
    registry, _ = registry_of(a=script_ok("a"))
    config = AggregationConfig.create([SourceConfig("a"), SourceConfig("ghost", enabled=False)])
    result = run(MultiSourceEngine(config, registry, FakeHttpClient()).aggregate(N))
    assert result.disabled_source_ids == ("ghost",) and result.source_order == ("a",)


def test_engine_rejects_wrong_argument_types():
    registry, _ = registry_of(a=script_ok("a"))
    config = AggregationConfig.create([SourceConfig("a")])
    with pytest.raises(AggregationConfigError):
        MultiSourceEngine("config", registry, FakeHttpClient())  # type: ignore[arg-type]
    with pytest.raises(AggregationConfigError):
        MultiSourceEngine(config, {}, FakeHttpClient())  # type: ignore[arg-type]
    with pytest.raises(AggregationConfigError):
        MultiSourceEngine(config, registry, object())  # type: ignore[arg-type]


def test_21_malformed_base_url_is_rejected_before_any_engine_or_network_work():
    calls = []

    async def script(number, client):
        calls.append(number)
        return ok("a", number, "T")

    registry, _ = registry_of(a=script)
    for bad in ("fc2db.net", "http://", "https://", "https://x.example\n"):
        with pytest.raises(AggregationConfigError):
            AggregationConfig.create([SourceConfig("a", base_url=bad)])
    assert calls == []
    assert isinstance(registry, SourceRegistry)  # nothing was ever asked of it


def test_base_url_override_reaches_the_adapter_and_defaults_are_untouched():
    registry, classes = registry_of(a=script_ok("a"), b=script_ok("b"))
    config = AggregationConfig.create([SourceConfig("a", base_url="https://mirror.example/x"), SourceConfig("b")])
    engine = MultiSourceEngine(config, registry, FakeHttpClient())
    adapters = {t.config.source_id: t.adapter for t in engine._targets}
    assert adapters["a"].base_url == "https://mirror.example/x"
    assert adapters["b"].base_url == classes["b"].default_base_url


# ---- P2-R-11 through the engine (22, 23) ------------------------------------------------------------------


def test_22_a_registry_factory_returning_junk_is_a_domain_error_at_engine_construction():
    registry = SourceRegistry()
    registry.register("junk", lambda **k: 42)
    with pytest.raises(InvalidSourceAdapterError):
        MultiSourceEngine(AggregationConfig.create([SourceConfig("junk")]), registry, FakeHttpClient())


def test_23_a_registry_id_mismatch_is_a_domain_error_at_engine_construction():
    registry = SourceRegistry()
    registry.register("alias_x", Fc2dbNetAdapter)
    with pytest.raises(SourceIdMismatchError):
        MultiSourceEngine(AggregationConfig.create([SourceConfig("alias_x")]), registry, FakeHttpClient())
    assert issubclass(SourceIdMismatchError, SourceRegistryError)


# ---- behaviour ---------------------------------------------------------------------------------------------------


def test_non_canonical_number_is_a_caller_error_and_no_source_is_called():
    registry, classes = registry_of(a=script_ok("a"))
    engine = MultiSourceEngine(AggregationConfig.create([SourceConfig("a")]), registry, FakeHttpClient())
    for bad in ("4979299", "FC2-4979299\n", "FC2-４９７９２９９"):
        with pytest.raises(InvalidCanonicalNumberInputError):
            run(engine.aggregate(bad))
    assert all(t.adapter.calls == [] for t in engine._targets)


def test_engine_end_to_end_with_scripted_sources_and_priority_and_provenance():
    registry, _ = registry_of(
        a=script_ok("a", "Title A", actors=("Alice", "Bob"), tags=("t1",)),
        b=script_ok("b", "Title B", actors=("Bob", "Carol"), studio="Studio B"),
        c=script_fail("c", SourceStatus.NOT_FOUND),
    )
    config = AggregationConfig.create([SourceConfig("a"), SourceConfig("b"), SourceConfig("c")], field_priority={"studio": ["b"]})
    result = run(MultiSourceEngine(config, registry, FakeHttpClient()).aggregate(N))
    assert result.status is AggregateStatus.SUCCESS
    assert result.metadata.title == "Title A" and result.metadata.actors == ("Alice", "Bob", "Carol")
    assert result.metadata.field_sources["actors"] == ("a", "b")
    assert result.source_order == ("a", "b", "c") and result.contributing_source_ids == ("a", "b")
    assert result.elapsed_ms >= 0


def test_15_engine_result_is_identical_when_source_completion_order_is_reversed_by_sleeps():
    def delayed(source_id, delay, **fields):
        async def script(number, client):
            await asyncio.sleep(delay)
            return ok(source_id, number, f"T-{source_id}", **fields)

        return script

    def build(delays):
        registry, _ = registry_of(
            a=delayed("a", delays[0], tags=("a1", "shared")),
            b=delayed("b", delays[1], tags=("b1", "shared")),
            c=delayed("c", delays[2], tags=("c1",)),
        )
        config = AggregationConfig.create([SourceConfig("a"), SourceConfig("b"), SourceConfig("c")])
        return run(MultiSourceEngine(config, registry, FakeHttpClient()).aggregate(N))

    forward, reverse = build((0.0, 0.05, 0.1)), build((0.1, 0.05, 0.0))
    assert forward.metadata == reverse.metadata
    assert forward.source_order == reverse.source_order == ("a", "b", "c")
    assert forward.metadata.tags == ("a1", "shared", "b1", "c1")


def test_deadline_expiry_gives_partial_when_another_source_succeeds_and_failed_when_none_does():
    async def hang(number, client):
        await asyncio.Event().wait()

    registry, _ = registry_of(stuck=hang, good=script_ok("good", "Good"))
    config = AggregationConfig.create([SourceConfig("stuck", deadline_seconds=0.1), SourceConfig("good")])
    partial = run(MultiSourceEngine(config, registry, FakeHttpClient()).aggregate(N))
    assert partial.status is AggregateStatus.PARTIAL and partial.metadata.title == "Good"
    assert partial.result_for("stuck").status is SourceStatus.NETWORK_ERROR
    assert "deadline exceeded" in partial.result_for("stuck").error_detail

    only_stuck = AggregationConfig.create([SourceConfig("stuck", deadline_seconds=0.1)])
    assert run(MultiSourceEngine(only_stuck, registry, FakeHttpClient()).aggregate(N)).status is AggregateStatus.FAILED


def test_19_caller_cancellation_propagates_out_of_aggregate():
    async def hang(number, client):
        await asyncio.Event().wait()

    registry, _ = registry_of(a=hang)
    engine = MultiSourceEngine(AggregationConfig.create([SourceConfig("a")]), registry, FakeHttpClient())

    async def scenario():
        task = asyncio.create_task(engine.aggregate(N))
        await asyncio.sleep(0.1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    run(scenario())


def test_the_engine_can_be_reused_for_many_lookups():
    registry, _ = registry_of(a=script_ok("a", "T"))
    engine = MultiSourceEngine(AggregationConfig.create([SourceConfig("a")]), registry, FakeHttpClient())
    numbers = ["FC2-1000001", "FC2-1000002", "FC2-1000003"]
    results = [run(engine.aggregate(n)) for n in numbers]
    assert [r.number for r in results] == numbers
    assert engine._targets[0].adapter.calls == numbers


# ---- the three REAL adapters through the default config, offline ---------------------------------------------------


def _serve(client, adapter_cls, number, *, status=200, fixture=None):
    url = adapter_cls()._lookup_url(number)
    text = load_fixture(fixture) if fixture else ""
    client.add_response(url, make_response(status_code=status, url=url, text=text))
    return url


def _default_engine(client):
    return MultiSourceEngine(default_aggregation_config(), build_default_registry(), client)


def test_default_config_fc2_4825061_fc2db_gap_is_normal_and_title_comes_from_javdb():
    client = FakeHttpClient()
    _serve(client, Fc2dbNetAdapter, "FC2-4825061", status=404, fixture="fc2db_net/work_404_4825061.html")
    _serve(client, JavdbAdapter, "FC2-4825061", fixture="javdb/search_hit_4825061.html")
    _serve(client, Av123Adapter, "FC2-4825061", fixture="av123/detail_4825061.html")
    result = run(_default_engine(client).aggregate("FC2-4825061"))

    assert result.status is AggregateStatus.SUCCESS  # fc2db_net NOT_FOUND is a coverage gap, not a failure
    assert result.source_order == ("fc2db_net", "javdb", "av123")
    assert [r.status for r in result.source_results] == [SourceStatus.NOT_FOUND, SourceStatus.SUCCESS, SourceStatus.SUCCESS]
    md = result.metadata
    assert md.number == "FC2-4825061" and md.title.startswith("【顔出し】ハーフ美人妻")  # javdb (Japanese), not av123 (English)
    assert md.field_sources["title"] == ("javdb",)
    assert md.release == "2026-01-02" and md.field_sources["release"] == ("javdb", "av123")  # both agree
    assert md.runtime == 39 and md.field_sources["runtime"] == ("av123",)  # only av123 has it
    assert md.tags == ("Amateur",) and md.field_sources["tags"] == ("av123",)
    assert dict(md.external_ids) == {"javdb": "82ZNYd"} and md.field_sources["external_ids"] == ("javdb",)
    assert result.contributing_source_ids == ("javdb", "av123")
    assert len(client.requested_urls) == 3 and len(set(client.requested_urls)) == 3  # one request per source


def test_default_config_fc2_4824605_only_fc2db_has_it():
    client = FakeHttpClient()
    _serve(client, Fc2dbNetAdapter, "FC2-4824605", fixture="fc2db_net/work_4824605.html")
    _serve(client, JavdbAdapter, "FC2-4824605", fixture="javdb/search_no_exact_4824605.html")
    _serve(client, Av123Adapter, "FC2-4824605", status=404, fixture="av123/detail_404_4824605.html")
    result = run(_default_engine(client).aggregate("FC2-4824605"))

    assert result.status is AggregateStatus.SUCCESS
    assert [r.status for r in result.source_results] == [SourceStatus.SUCCESS, SourceStatus.NOT_FOUND, SourceStatus.NOT_FOUND]
    assert result.metadata.title.startswith("※1/11まで初回限定90％OFF※")
    assert result.metadata.actors == ("花谷かれん",) and result.metadata.publisher == "素人0930"
    assert result.contributing_source_ids == ("fc2db_net",)
    assert set(result.metadata.field_sources["title"]) == {"fc2db_net"}


def test_default_config_fc2_4979299_all_three_sources_merge():
    client = FakeHttpClient()
    _serve(client, Fc2dbNetAdapter, "FC2-4979299", fixture="fc2db_net/work_4979299.html")
    _serve(client, JavdbAdapter, "FC2-4979299", fixture="javdb/search_hit_4979299.html")
    _serve(client, Av123Adapter, "FC2-4979299", fixture="av123/detail_4979299.html")
    result = run(_default_engine(client).aggregate("FC2-4979299"))

    assert result.status is AggregateStatus.SUCCESS
    assert result.contributing_source_ids == ("fc2db_net", "javdb", "av123")
    md = result.metadata
    assert md.number == "FC2-4979299"
    assert md.title.startswith("夢は小学校の先生。") and md.field_sources["title"][0] == "fc2db_net"
    assert md.field_sources["number"] == ("fc2db_net", "javdb", "av123")
    # fc2db_net and javdb share the same Japanese title; av123's English one is a conflict, not the value.
    assert "javdb" in md.field_sources["title"] and "av123" not in md.field_sources["title"]
    assert any(c.field == "title" and c.alternatives[0][0] == "av123" for c in result.conflicts)
    assert len(md.source_urls) == len(set(md.source_urls)) >= 3
    assert set(md.field_sources["source_urls"]) == {"fc2db_net", "javdb", "av123"}
    assert md.thumb_urls and set(md.field_sources["thumb_urls"]) <= {"fc2db_net", "javdb"}


def test_default_config_one_source_blocked_gives_partial_not_failed():
    client = FakeHttpClient()
    _serve(client, Fc2dbNetAdapter, "FC2-4979299", fixture="fc2db_net/work_4979299.html")
    _serve(client, JavdbAdapter, "FC2-4979299", status=403, fixture="common/cloudflare_challenge.html")
    _serve(client, Av123Adapter, "FC2-4979299", status=404)
    result = run(_default_engine(client).aggregate("FC2-4979299"))
    assert result.status is AggregateStatus.PARTIAL
    assert [r.status for r in result.source_results] == [SourceStatus.SUCCESS, SourceStatus.BLOCKED, SourceStatus.NOT_FOUND]


def test_default_config_every_source_missing_is_failed_with_all_results_kept():
    client = FakeHttpClient()
    _serve(client, Fc2dbNetAdapter, "FC2-1234567", status=404)
    _serve(client, JavdbAdapter, "FC2-1234567", fixture="javdb/search_empty_99999999.html")
    _serve(client, Av123Adapter, "FC2-1234567", status=404)
    result = run(_default_engine(client).aggregate("FC2-1234567"))
    assert result.status is AggregateStatus.FAILED and result.metadata is None
    assert [r.status for r in result.source_results] == [SourceStatus.NOT_FOUND] * 3


def test_reordering_the_configuration_changes_the_winner_without_code_changes():
    def aggregate(order):
        client = FakeHttpClient()
        _serve(client, Fc2dbNetAdapter, "FC2-4979299", fixture="fc2db_net/work_4979299.html")
        _serve(client, JavdbAdapter, "FC2-4979299", fixture="javdb/search_hit_4979299.html")
        _serve(client, Av123Adapter, "FC2-4979299", fixture="av123/detail_4979299.html")
        config = AggregationConfig.create([SourceConfig(s) for s in order])
        return run(MultiSourceEngine(config, build_default_registry(), client).aggregate("FC2-4979299"))

    english_first = aggregate(("av123", "fc2db_net", "javdb"))
    assert english_first.metadata.title.startswith("Her dream is to be an elementary school teacher")
    assert english_first.metadata.field_sources["title"] == ("av123",)
    japanese_first = aggregate(("javdb", "av123", "fc2db_net"))
    assert japanese_first.metadata.title.startswith("夢は小学校の先生。")
    assert japanese_first.metadata.field_sources["title"] == ("javdb", "fc2db_net")


def test_per_field_override_via_configuration_only():
    client = FakeHttpClient()
    _serve(client, Fc2dbNetAdapter, "FC2-4979299", fixture="fc2db_net/work_4979299.html")
    _serve(client, JavdbAdapter, "FC2-4979299", fixture="javdb/search_hit_4979299.html")
    _serve(client, Av123Adapter, "FC2-4979299", fixture="av123/detail_4979299.html")
    config = AggregationConfig.create(
        [SourceConfig(s) for s in ("fc2db_net", "javdb", "av123")], field_priority={"title": ["av123"]}
    )
    result = run(MultiSourceEngine(config, build_default_registry(), client).aggregate("FC2-4979299"))
    assert result.metadata.title.startswith("Her dream")
    assert result.metadata.release == "2026-09-19"  # other fields still follow the default order
