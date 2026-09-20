"""Aggregation configuration boundary: everything is rejected BEFORE any network request.

Closes Phase 2 review finding P2-R-08 (a malformed ``base_url`` used to surface
as a raw ``httpx`` exception at request time) on the Phase 3 config path.
"""

from __future__ import annotations

import pytest

from fc2_metadata_core.aggregation import (
    DEFAULT_SOURCE_ORDER,
    AggregationConfig,
    AggregationConfigError,
    AggregationPolicy,
    SourceConfig,
    default_aggregation_config,
    validate_base_url,
)

GOOD_URLS = [
    "https://fc2db.net",
    "https://fc2db.net/",
    "http://fc2db.net",
    "https://mirror.example.com/prefix",
    "http://127.0.0.1:8080",
    "http://127.0.0.1:8080/x/y",
    "https://[::1]:8443/",
    "https://a-b.c-d.example",
    "https://xn--wgv71a.example",  # punycode is ASCII
]

BAD_URLS = [
    "",
    "fc2db.net",  # no scheme
    "//fc2db.net",
    "http://",
    "https://",
    "https:///path",
    "ftp://fc2db.net",
    "file:///etc/passwd",
    "javascript:alert(1)",
    "https://fc2db.net\n",
    "https://fc2db.net\r\nHost: evil.example",
    "https://fc2db.net/\x00",
    "https://fc2db.net/\ta",
    "https://fc2db.net/ a",
    " https://fc2db.net",
    "https://fc2db.net ",
    "https://user:pw@fc2db.net",
    "https://user@fc2db.net",
    "https://fc2db.net?x=1",
    "https://fc2db.net/#frag",
    "https://fc2db.net:0",
    "https://fc2db.net:99999",
    "https://fc2db.net:abc",
    "https://-bad-.example",
    "https://bad_host.example",
    "https://exa mple.com",
    "https://fc2db..net",
    "https://fc2db.net。",  # ideographic full stop (non-ASCII)
    "https://ᴅb.example",  # non-ASCII host
    "https://fc2db.net/é",
    "https://fc2db.net\\evil",
    "https://" + "a" * 64 + ".example",  # label too long
    "https://fc2db.net/" + "a" * 2100,
]


@pytest.mark.parametrize("url", GOOD_URLS)
def test_valid_base_urls_are_accepted_unchanged(url):
    assert validate_base_url(url) == url


@pytest.mark.parametrize("url", BAD_URLS, ids=[ascii(u)[:60] for u in BAD_URLS])
def test_malformed_base_urls_are_rejected_with_a_domain_error(url):
    with pytest.raises(AggregationConfigError):
        validate_base_url(url)
    with pytest.raises(AggregationConfigError):
        SourceConfig("fc2db_net", base_url=url)


@pytest.mark.parametrize("value", [None, 1, b"https://x.example", ["https://x.example"]])
def test_non_string_base_url_is_rejected(value):
    if value is None:
        assert SourceConfig("x").base_url is None  # None means "adapter default"
    else:
        with pytest.raises(AggregationConfigError):
            validate_base_url(value)


def test_source_config_defaults_and_immutability():
    config = SourceConfig("fc2db_net")
    assert config.enabled is True and config.base_url is None and config.deadline_seconds == 20.0
    with pytest.raises(Exception):
        config.enabled = False  # type: ignore[misc]


@pytest.mark.parametrize("source_id", ["", "  ", " x", "x ", 5, None])
def test_bad_source_ids_are_rejected(source_id):
    with pytest.raises(AggregationConfigError):
        SourceConfig(source_id)  # type: ignore[arg-type]


@pytest.mark.parametrize("deadline", [0, -1, -0.5, float("nan"), float("inf"), 601, True, "20", None])
def test_bad_deadlines_are_rejected(deadline):
    with pytest.raises(AggregationConfigError):
        SourceConfig("x", deadline_seconds=deadline)  # type: ignore[arg-type]


@pytest.mark.parametrize("deadline", [0.001, 1, 20, 20.5, 600])
def test_good_deadlines_are_accepted(deadline):
    assert SourceConfig("x", deadline_seconds=deadline).deadline_seconds == deadline


def test_enabled_must_be_a_real_bool():
    with pytest.raises(AggregationConfigError):
        SourceConfig("x", enabled=1)  # type: ignore[arg-type]


# ---- AggregationConfig --------------------------------------------------------------------


def test_empty_source_set_is_rejected():
    with pytest.raises(AggregationConfigError):
        AggregationConfig(sources=())
    with pytest.raises(AggregationConfigError):
        AggregationConfig.create([])


def test_all_disabled_is_rejected():
    with pytest.raises(AggregationConfigError):
        AggregationConfig.create([SourceConfig("a", enabled=False), SourceConfig("b", enabled=False)])


def test_duplicate_source_id_is_rejected():
    with pytest.raises(AggregationConfigError):
        AggregationConfig.create([SourceConfig("a"), SourceConfig("b"), SourceConfig("a", enabled=False)])


def test_sources_must_be_source_configs():
    with pytest.raises(AggregationConfigError):
        AggregationConfig(sources=("fc2db_net",))  # type: ignore[arg-type]
    with pytest.raises(AggregationConfigError):
        AggregationConfig(sources=[SourceConfig("a")])  # type: ignore[arg-type]  # list, not tuple


@pytest.mark.parametrize("value", [0, -1, 65, 3.0, True, "3", None])
def test_bad_max_concurrency_is_rejected(value):
    with pytest.raises(AggregationConfigError):
        AggregationConfig(sources=(SourceConfig("a"),), max_concurrency=value)  # type: ignore[arg-type]


def test_default_max_concurrency_is_three_and_configurable():
    assert AggregationConfig.create([SourceConfig("a")]).max_concurrency == 3
    assert AggregationConfig.create([SourceConfig("a")], max_concurrency=1).max_concurrency == 1
    assert AggregationConfig.create([SourceConfig("a")], max_concurrency=64).max_concurrency == 64


def test_source_order_is_the_default_priority_and_disabled_sources_are_excluded():
    config = AggregationConfig.create([SourceConfig("c"), SourceConfig("a", enabled=False), SourceConfig("b")])
    assert config.policy().source_order == ("c", "b")
    assert config.disabled_source_ids == ("a",)
    assert [s.source_id for s in config.enabled_sources] == ["c", "b"]


def test_default_config_is_the_three_verified_sources_in_configured_order():
    config = default_aggregation_config()
    assert DEFAULT_SOURCE_ORDER == ("fc2db_net", "javdb", "av123")
    assert [s.source_id for s in config.sources] == ["fc2db_net", "javdb", "av123"]
    assert config.max_concurrency == 3
    assert all(s.deadline_seconds == 20.0 and s.enabled and s.base_url is None for s in config.sources)


# ---- per-field priority overrides ------------------------------------------------------------


def _three(**kwargs):
    return AggregationConfig.create([SourceConfig("a"), SourceConfig("b"), SourceConfig("c")], **kwargs)


def test_field_override_is_expanded_to_a_full_deterministic_order():
    policy = _three(field_priority={"title": ["c"], "actors": ["b", "c"]}).policy()
    assert policy.priority_for("title") == ("c", "a", "b")
    assert policy.priority_for("actors") == ("b", "c", "a")
    assert policy.priority_for("release") == ("a", "b", "c")  # no override: default order


@pytest.mark.parametrize(
    "overrides",
    [
        {"number": ["a"]},  # number is never chosen from a source
        {"field_sources": ["a"]},
        {"nonsense": ["a"]},
        {"title": ["zzz"]},  # not configured
        {"title": ["a", "a"]},  # duplicate
        {"title": []},  # empty
        {"title": "a"},  # bare str
        {1: ["a"]},
    ],
)
def test_invalid_field_priority_is_rejected(overrides):
    with pytest.raises(AggregationConfigError):
        _three(field_priority=overrides)


def test_override_naming_a_disabled_but_configured_source_is_tolerated():
    config = AggregationConfig.create(
        [SourceConfig("a"), SourceConfig("b", enabled=False), SourceConfig("c")],
        field_priority={"title": ["b", "c"]},
    )
    assert config.policy().priority_for("title") == ("c", "a")


def test_policy_build_rejects_the_same_things_directly():
    with pytest.raises(AggregationConfigError):
        AggregationPolicy.build(["a", "b"], {"title": ["c"]})
    with pytest.raises(AggregationConfigError):
        AggregationPolicy.build(["a", "a"])
    with pytest.raises(AggregationConfigError):
        AggregationPolicy.build([])
    assert AggregationPolicy.build(["a", "b"], {"title": ["b"]}).priority_for("title") == ("b", "a")


def test_config_is_immutable_and_hashable_values_only():
    config = _three(field_priority={"title": ["c"]})
    assert isinstance(config.sources, tuple) and isinstance(config.field_priority, tuple)
    with pytest.raises(Exception):
        config.max_concurrency = 9  # type: ignore[misc]
