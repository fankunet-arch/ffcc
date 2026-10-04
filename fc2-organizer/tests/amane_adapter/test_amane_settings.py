"""P5-C1 表 C（E5 配置 / E23）：配置校验、确定性、不回显配置值、无密钥字段。"""

from __future__ import annotations

import pytest

from fc2_amane_adapter import _settings
from fc2_amane_adapter._settings import (
    AdapterConfigError,
    METADATA_FIELDS,
    PLUGIN_ID,
    build_aggregation_config,
    descriptor_urls,
    parse_settings,
)
from fc2_metadata_core.aggregation import (
    DEFAULT_MAX_CONCURRENCY,
    DEFAULT_SOURCE_DEADLINE_SECONDS,
    DEFAULT_SOURCE_ORDER,
    RetryPolicy,
)

from support.amane_config_matrix import CONFIG_MATRIX, DEADLINE_MATRIX, RAW_STRING_DEADLINES

SECRET = "TOPSECRET-VALUE-9f3a"


def test_default_settings_use_core_default_order_all_enabled():
    settings = parse_settings({})
    assert [entry.source_id for entry in settings.sources] == list(DEFAULT_SOURCE_ORDER)
    assert all(entry.enabled and entry.base_url is None for entry in settings.sources)
    assert settings.source_deadline_seconds == DEFAULT_SOURCE_DEADLINE_SECONDS == 20.0
    assert parse_settings({"sources": None}) == settings


def test_explicit_sources_are_authoritative_and_ordered():
    settings = parse_settings(
        {"sources": [{"id": "javdb"}, {"id": "fc2db_net", "enabled": False}, {"id": "av123", "base_url": "https://mirror.example"}]}
    )
    assert [(e.source_id, e.enabled, e.base_url) for e in settings.sources] == [
        ("javdb", True, None),
        ("fc2db_net", False, None),
        ("av123", True, "https://mirror.example"),
    ]


def test_unlisted_registered_sources_are_not_used():
    config = build_aggregation_config(parse_settings({"sources": [{"id": "javdb"}]}))
    assert [source.source_id for source in config.sources] == ["javdb"]


def test_core_config_has_no_core_retry_and_frozen_defaults():
    config = build_aggregation_config(parse_settings({"source_deadline_seconds": 7}))
    no_retry = RetryPolicy.no_retry()
    assert config.retry_policy == no_retry
    assert config.max_concurrency == DEFAULT_MAX_CONCURRENCY
    assert config.field_priority == ()
    for source in config.sources:
        assert source.retry_policy == no_retry
        assert source.deadline_seconds == 7.0
    assert no_retry.max_attempts == 1


@pytest.mark.parametrize(
    "raw",
    [
        [],
        "sources",
        {"unknown": 1},
        {"sources": []},
        {"sources": "javdb"},
        {"sources": [{"id": "nope"}]},
        {"sources": [{"id": 5}]},
        {"sources": [{}]},
        {"sources": [{"id": "javdb"}, {"id": "javdb"}]},
        {"sources": [{"id": "javdb", "enabled": False}, {"id": "av123", "enabled": False}]},
        {"sources": [{"id": "javdb", "enabled": "yes"}]},
        {"sources": [{"id": "javdb", "enabled": 1}]},
        {"sources": [{"id": "javdb", "extra": 1}]},
        {"sources": ["javdb"]},
        {"sources": [{"id": "javdb", "base_url": "https://user:pw@mirror.example"}]},
        {"sources": [{"id": "javdb", "base_url": "ftp://mirror.example"}]},
        {"sources": [{"id": "javdb", "base_url": "https://mirror.example/?q=1"}]},
        {"sources": [{"id": "javdb", "base_url": "https://mirror.example/#frag"}]},
        {"sources": [{"id": "javdb", "base_url": "https://mirror\r\n.example"}]},
        {"sources": [{"id": "javdb", "base_url": 5}]},
        {"source_deadline_seconds": 0},
        {"source_deadline_seconds": -1},
        {"source_deadline_seconds": float("nan")},
        {"source_deadline_seconds": float("inf")},
        {"source_deadline_seconds": 100000},
        {"source_deadline_seconds": True},
        {"source_deadline_seconds": "20"},
        {"source_deadline_seconds": None},
    ],
)
def test_invalid_configuration_is_rejected_before_any_network(raw):
    with pytest.raises(AdapterConfigError):
        parse_settings(raw)


def test_deadline_upper_bound_comes_from_core_not_adapter():
    assert parse_settings({"source_deadline_seconds": 600}).source_deadline_seconds == 600.0
    with pytest.raises(AdapterConfigError):
        parse_settings({"source_deadline_seconds": 600.5})
    assert not hasattr(_settings, "MAX_SOURCE_DEADLINE_SECONDS")


@pytest.mark.parametrize(
    "raw",
    [
        {"sources": [{"id": SECRET}]},
        {"sources": [{"id": "javdb", "base_url": f"https://u:{SECRET}@mirror.example"}]},
        {"sources": [{"id": "javdb", "base_url": f"ftp://{SECRET}.example"}]},
        {"source_deadline_seconds": SECRET},
        {SECRET: 1},
        {"sources": [{"id": "javdb", SECRET: 1}]},
        {"sources": SECRET},
    ],
)
def test_error_messages_never_echo_configuration_values(raw):
    with pytest.raises(AdapterConfigError) as excinfo:
        parse_settings(raw)
    assert SECRET not in str(excinfo.value)
    assert len(str(excinfo.value)) < 300


def test_error_messages_are_deterministic():
    messages = set()
    for _ in range(3):
        with pytest.raises(AdapterConfigError) as excinfo:
            parse_settings({"sources": [{"id": "nope"}]})
        messages.add(str(excinfo.value))
    assert len(messages) == 1
    assert "av123" in messages.pop()  # 允许集合被列出


def test_descriptor_constants_follow_the_contract():
    assert PLUGIN_ID == "ffcc.fc2-metadata"
    assert METADATA_FIELDS == frozenset(
        {"title", "plot", "actors", "tags", "release", "runtime", "publisher", "studio", "poster_urls", "thumb_urls", "extrafanart"}
    )
    assert not METADATA_FIELDS & {"directors", "series", "trailer_urls", "score"}
    assert descriptor_urls() == ("https://fc2db.net", "https://javdb.com", "https://123av.com")


def test_no_secret_like_configuration_field_names():
    names = {"sources", "id", "enabled", "base_url", "source_deadline_seconds"}
    for name in names:
        assert not any(word in name for word in ("token", "secret", "password", "api_key", "cookie", "credential", "dsn"))


# ------------------------------------------------------------ P5-C1-L1-01：原始类型校验（parse_settings 是权威）


@pytest.mark.parametrize(("label", "config", "accepted"), CONFIG_MATRIX, ids=[row[0] for row in CONFIG_MATRIX])
def test_parse_settings_matches_the_shared_validation_matrix(label, config, accepted):
    """同一张矩阵也由真实宿主 H-04 对 ``Fc2MetadataConfig`` 逐行裁决；二者必须一致。"""
    if accepted:
        parse_settings(config)
    else:
        with pytest.raises(AdapterConfigError):
            parse_settings(config)


@pytest.mark.parametrize("raw", RAW_STRING_DEADLINES)
def test_parse_settings_rejects_coercible_numeric_strings_before_any_conversion(raw):
    """``"20"`` 这类会被 Pydantic 宽松模式先转成 ``20.0`` 的原始字符串，``parse_settings`` 必须看到并拒绝。"""
    with pytest.raises(AdapterConfigError):
        parse_settings({"source_deadline_seconds": raw})


def test_deadline_matrix_covers_the_frozen_contract_cases():
    labels = {label for label, _value, _accepted in DEADLINE_MATRIX}
    assert {"str '20'", "str '20.0'", "bool True", "bool False", "nan", "inf", "-inf", "int 0", "int -1", "int 601", "int 600", "int 20", "float 20.0"} <= labels
    accepted = {label for label, _value, ok in DEADLINE_MATRIX if ok}
    assert {"int 20", "float 20.0", "int 600"} <= accepted and "bool True" not in accepted
