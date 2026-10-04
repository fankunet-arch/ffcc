"""配置校验与 Core 配置构造（纯模块；合同第 9 节与第 11 节）。

Pydantic（``plugin.py``）只声明形状；全部规则由 :func:`parse_settings` 全权负责，并在 Pydantic 层与
``build()`` 各执行一次，**都在任何网络活动之前**。所有违规以**确定性、不回显配置值**的消息拒绝
（只含字段名、下标与允许集合）。配置**没有任何密钥字段**。
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from fc2_metadata_core.aggregation import (
    DEFAULT_MAX_CONCURRENCY,
    DEFAULT_SOURCE_DEADLINE_SECONDS,
    DEFAULT_SOURCE_ORDER,
    AggregationConfig,
    AggregationConfigError,
    RetryPolicy,
    SourceConfig,
    validate_base_url,
)
from fc2_metadata_core.sources.adapters import ALL_ADAPTER_CLASSES, build_default_registry

__all__ = [
    "PLUGIN_ID",
    "PLUGIN_NAME",
    "PLUGIN_VERSION",
    "DEFAULT_DEADLINE_SECONDS",
    "CONTENT_TYPES",
    "METADATA_FIELDS",
    "AdapterConfigError",
    "SourceSetting",
    "AdapterSettings",
    "descriptor_urls",
    "parse_settings",
    "build_aggregation_config",
]

#: 插件身份（合同第 9 节；``id`` 一经真实安装即成为持久化键，不可再改）。
PLUGIN_ID = "ffcc.fc2-metadata"
PLUGIN_NAME = "FC2 Metadata (ffcc)"
PLUGIN_VERSION = "0.1.0"

#: 单来源总墙钟预算的缺省值（= Core ``DEFAULT_SOURCE_DEADLINE_SECONDS``）。
DEFAULT_DEADLINE_SECONDS = DEFAULT_SOURCE_DEADLINE_SECONDS

#: ``ContentType.FC2.value``；路由校验使该来源只能被挂到 FC2 路由。
CONTENT_TYPES = frozenset({"fc2"})

#: 与合同表 H 一致；不声称 directors / series / trailer_urls / score。
METADATA_FIELDS = frozenset(
    {
        "title",
        "plot",
        "actors",
        "tags",
        "release",
        "runtime",
        "publisher",
        "studio",
        "poster_urls",
        "thumb_urls",
        "extrafanart",
    }
)

_TOP_LEVEL_FIELDS = ("sources", "source_deadline_seconds")
_ENTRY_FIELDS = ("id", "enabled", "base_url")


class AdapterConfigError(ValueError):
    """配置违规；消息固定、不回显配置值。"""


@dataclass(frozen=True, slots=True)
class SourceSetting:
    source_id: str
    enabled: bool = True
    base_url: str | None = None


@dataclass(frozen=True, slots=True)
class AdapterSettings:
    sources: tuple[SourceSetting, ...]
    source_deadline_seconds: float


def descriptor_urls() -> tuple[str, ...]:
    """由 Core ``ALL_ADAPTER_CLASSES`` 的 ``default_base_url`` 按 ``DEFAULT_SOURCE_ORDER`` 派生（单一事实来源）。"""
    by_id = {adapter.source_id: adapter.default_base_url for adapter in ALL_ADAPTER_CLASSES}
    return tuple(by_id[source_id] for source_id in DEFAULT_SOURCE_ORDER)


def _registered_ids() -> tuple[str, ...]:
    return tuple(sorted(build_default_registry().source_ids()))


def _parse_entry(index: int, entry: object, registered: tuple[str, ...]) -> SourceSetting:
    where = f"sources[{index}]"
    if not isinstance(entry, Mapping):
        raise AdapterConfigError(f"{where} must be an object with fields: {', '.join(_ENTRY_FIELDS)}")
    if any(key not in _ENTRY_FIELDS for key in entry):
        raise AdapterConfigError(f"{where} has an unknown field; allowed fields: {', '.join(_ENTRY_FIELDS)}")
    if "id" not in entry:
        raise AdapterConfigError(f"{where}.id is required")
    source_id = entry["id"]
    if not isinstance(source_id, str) or source_id not in registered:
        raise AdapterConfigError(f"{where}.id must be a registered source id: {', '.join(registered)}")
    enabled = entry.get("enabled", True)
    if not isinstance(enabled, bool):
        raise AdapterConfigError(f"{where}.enabled must be a boolean")
    base_url = entry.get("base_url")
    if base_url is not None:
        try:
            validate_base_url(base_url)
        except AggregationConfigError:
            raise AdapterConfigError(f"{where}.base_url must be a safe absolute http(s) base URL") from None
    return SourceSetting(source_id=source_id, enabled=enabled, base_url=base_url)


def _parse_sources(raw: object) -> tuple[SourceSetting, ...]:
    if raw is None:
        return tuple(SourceSetting(source_id=source_id) for source_id in DEFAULT_SOURCE_ORDER)
    if isinstance(raw, (str, bytes)) or not isinstance(raw, Sequence):
        raise AdapterConfigError("sources must be a list of source entries or null")
    if len(raw) == 0:
        raise AdapterConfigError("sources must not be empty (use null for the default source set)")
    registered = _registered_ids()
    entries = tuple(_parse_entry(index, entry, registered) for index, entry in enumerate(raw))
    seen: set[str] = set()
    for entry in entries:
        if entry.source_id in seen:
            raise AdapterConfigError("sources must not repeat a source id")
        seen.add(entry.source_id)
    if not any(entry.enabled for entry in entries):
        raise AdapterConfigError("at least one source must be enabled")
    return entries


def _parse_deadline(raw: object, first_source_id: str) -> float:
    message = "source_deadline_seconds must be a finite number greater than 0 and within the Core maximum"
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        raise AdapterConfigError(message)
    if not math.isfinite(raw) or raw <= 0:
        raise AdapterConfigError(message)
    try:
        # 上界由 Core 的 SourceConfig 校验强制；adapter 不复制上界常量。
        SourceConfig(source_id=first_source_id, deadline_seconds=raw)
    except AggregationConfigError:
        raise AdapterConfigError(message) from None
    return float(raw)


def parse_settings(raw: object) -> AdapterSettings:
    """校验配置（``Mapping``）并返回不可变的 :class:`AdapterSettings`。"""
    if not isinstance(raw, Mapping):
        raise AdapterConfigError("configuration must be an object")
    if any(key not in _TOP_LEVEL_FIELDS for key in raw):
        raise AdapterConfigError(f"unknown configuration field; allowed fields: {', '.join(_TOP_LEVEL_FIELDS)}")
    sources = _parse_sources(raw.get("sources"))
    deadline = _parse_deadline(
        raw.get("source_deadline_seconds", DEFAULT_SOURCE_DEADLINE_SECONDS), sources[0].source_id
    )
    return AdapterSettings(sources=sources, source_deadline_seconds=deadline)


def build_aggregation_config(settings: AdapterSettings) -> AggregationConfig:
    """合同第 12 节：每来源与聚合级 ``RetryPolicy.no_retry()``；``max_concurrency`` 取 Core 默认。"""
    no_retry = RetryPolicy.no_retry()
    return AggregationConfig.create(
        sources=[
            SourceConfig(
                source_id=entry.source_id,
                enabled=entry.enabled,
                base_url=entry.base_url,
                deadline_seconds=settings.source_deadline_seconds,
                retry_policy=no_retry,
            )
            for entry in settings.sources
        ],
        max_concurrency=DEFAULT_MAX_CONCURRENCY,
        retry_policy=no_retry,
    )
