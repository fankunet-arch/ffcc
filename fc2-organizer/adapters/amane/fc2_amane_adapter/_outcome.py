"""adapter 内部的中立结果类型与 ``AggregationResult`` -> 中立结果的映射（纯模块；合同第 16-20 节）。

* 表 F：``AggregateStatus`` -> 中立结果；表 G：``SourceErrorKind`` -> ``FailureReason`` 字符串与 7 级优先级；
  表 H：``NormalizedMetadata`` -> ``AdapterRecord``（含 N-1 / N-2 窄化、URL 卫生过滤）。
* 全部是**纯函数**：不读取时钟、随机数、环境、文件；所有“选择”基于配置顺序或固定优先级表（不迭代 set / dict 视图）。
* 分类只读结构化的 ``SourceStatus`` / ``SourceErrorKind``，绝不读取 ``SourceResult.error_detail`` 或异常文本（I8）；
  ``detail`` 只含封闭词汇：Core 的 ``source_id`` 与 ``SourceErrorKind.value``（I12 / I23）。
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlsplit

from fc2_metadata_core.aggregation import AggregateStatus, AggregationResult
from fc2_metadata_core.models import NormalizedMetadata, SourceErrorKind, SourceResult, SourceStatus

__all__ = [
    "AdapterRecord",
    "AdapterFound",
    "AdapterNoMatch",
    "AdapterFailure",
    "NO_MATCH_REASONS",
    "FAILURE_REASONS",
    "KIND_TO_REASON",
    "CORE_FIELD_DISPOSITION",
    "TARGET_FIELD_DISPOSITION",
    "DETAIL_PREFIX",
    "internal_error_detail",
    "reason_for_kind",
    "pick_reason",
    "build_detail",
    "is_clean_http_url",
    "filter_urls",
    "narrow_source_url",
    "narrow_external_id",
    "map_record",
    "map_aggregation",
]

#: ``AdapterNoMatch.why`` 的封闭词汇（合同第 16 节）。
NO_MATCH_REASONS = ("content_type", "number_too_long", "not_fc2", "all_not_found")

#: ``AdapterFailure.reason`` 的封闭词汇：``FailureReason`` 的 7 个字符串值（合同第 17 节，按优先级排序）。
FAILURE_REASONS = (
    "http_error",
    "rate_limited",
    "parse_error",
    "server_error",
    "timeout",
    "network",
    "unexpected",
)


@dataclass(frozen=True, slots=True)
class AdapterRecord:
    """映射到 Amane ``MediaMetadata`` 之前的中立字段集（合同表 H；无 Amane 类型）。"""

    number: str
    title: str | None
    studio: str | None
    publisher: str | None
    release: str | None
    runtime: int | None
    actors: tuple[str, ...]
    tags: tuple[str, ...]
    plot: str | None
    poster_urls: tuple[str, ...]
    thumb_urls: tuple[str, ...]
    extrafanart: tuple[str, ...]
    source_url: str | None
    external_id: str | None


@dataclass(frozen=True, slots=True)
class AdapterFound:
    """SUCCESS / PARTIAL：可用的记录；``degraded`` = 运行性失败的 (source_id, error_kind_value)，按配置顺序。"""

    record: AdapterRecord
    degraded: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True, slots=True)
class AdapterNoMatch:
    """“没有找到”：宿主侧返回 ``None``。"""

    why: str

    def __post_init__(self) -> None:
        if self.why not in NO_MATCH_REASONS:
            raise ValueError("unknown no-match reason")


@dataclass(frozen=True, slots=True)
class AdapterFailure:
    """运行性失败：宿主侧抛 ``SourceError(FailureReason(reason), detail=detail)``。"""

    reason: str
    detail: str

    def __post_init__(self) -> None:
        if self.reason not in FAILURE_REASONS:
            raise ValueError("unknown failure reason")


# ------------------------------------------------------------------------------------------ 表 G：错误映射

#: ``SourceErrorKind`` -> ``FailureReason`` 字符串（合同 17.1）。穷尽 ``NOT_FOUND`` 之外的全部成员（由测试枚举验证）；
#: 未在表中的将来新 kind -> ``unexpected``。不使用 cloudflare_* / ip_banned / geo_restricted / age_verification。
KIND_TO_REASON: dict[SourceErrorKind, str] = {
    SourceErrorKind.BLOCKED: "http_error",
    SourceErrorKind.RATE_LIMITED: "rate_limited",
    SourceErrorKind.TIMEOUT: "timeout",
    SourceErrorKind.SOURCE_DEADLINE: "timeout",
    SourceErrorKind.CONNECTION_ERROR: "network",
    SourceErrorKind.NETWORK_ERROR: "network",
    SourceErrorKind.DECODE_ERROR: "network",
    SourceErrorKind.REDIRECT_ERROR: "network",
    SourceErrorKind.CIRCUIT_OPEN: "network",
    SourceErrorKind.PARSE_ERROR: "parse_error",
    SourceErrorKind.INVALID_RESPONSE: "parse_error",
    SourceErrorKind.RESPONSE_TOO_LARGE: "parse_error",
    SourceErrorKind.HTTP_SERVER_ERROR: "server_error",
    SourceErrorKind.ADAPTER_EXCEPTION: "unexpected",
    SourceErrorKind.RESULT_CONTRACT_MISMATCH: "unexpected",
}

#: 运行性失败：来源“没有真正回答”（与 NOT_FOUND 的“回答了：没有这部影片”相对）。
_OPERATIONAL_STATUSES = (
    SourceStatus.BLOCKED,
    SourceStatus.RATE_LIMITED,
    SourceStatus.NETWORK_ERROR,
    SourceStatus.PARSE_ERROR,
    SourceStatus.INVALID_RESPONSE,
)

DETAIL_PREFIX = "FC2 lookup failed: "


def internal_error_detail(type_name: str) -> str:
    """合同 §16：``internal adapter error: <ExceptionTypeName>``（detail 仅含类型名）。"""
    return f"internal adapter error: {type_name}"


def reason_for_kind(kind: object) -> str:
    """kind -> reason 字符串；未知 / 非 ``SourceErrorKind`` -> ``unexpected``。"""
    return KIND_TO_REASON.get(kind, "unexpected")  # type: ignore[arg-type]


def pick_reason(reasons: tuple[str, ...]) -> str:
    """7 级确定性优先级（合同 17.2）：按 ``FAILURE_REASONS`` 自上而下第一个出现的 reason。

    与来源顺序、完成顺序、集合 / 字典迭代顺序无关。
    """
    for candidate in FAILURE_REASONS:
        if candidate in reasons:
            return candidate
    return "unexpected"


def _kind_value(result: SourceResult) -> str:
    kind = result.error_kind
    return kind.value if isinstance(kind, SourceErrorKind) else result.status.value


def build_detail(results: tuple[SourceResult, ...]) -> str:
    """``FC2 lookup failed: <source_id>=<kind>; ...``（配置顺序；含 NOT_FOUND 的来源；封闭词汇）。"""
    return DETAIL_PREFIX + "; ".join(f"{result.source_id}={_kind_value(result)}" for result in results)


# ------------------------------------------------------------------------------------------ 表 H：字段映射

#: Core ``NormalizedMetadata`` 的**每个**字段的处置（合同 19.1；守护测试穷举字段集合）。
CORE_FIELD_DISPOSITION: dict[str, str] = {
    "number": "mapped:number",
    "title": "mapped:title",
    "studio": "mapped:studio",
    "publisher": "mapped:publisher",
    "release": "mapped:release",
    "runtime": "mapped:runtime",
    "actors": "mapped:actors",
    "tags": "mapped:tags",
    "plot": "mapped:plot",
    "poster_urls": "mapped:poster_urls",
    "thumb_urls": "mapped:thumb_urls",
    "fanart_urls": "not_representable",
    "extrafanart": "mapped:extrafanart",
    "source_urls": "narrowed:source_url",
    "external_ids": "not_exported",
    "field_sources": "not_exported",
}

#: Amane ``MediaMetadata`` 的**每个**字段的来源（合同 19.2；守护测试与 API manifest 对账）。
TARGET_FIELD_DISPOSITION: dict[str, str] = {
    "number": "core:number",
    "title": "core:title",
    "actors": "core:actors",
    "studio": "core:studio",
    "publisher": "core:publisher",
    "release": "core:release",
    "runtime": "core:runtime",
    "tags": "core:tags",
    "series": "absent:None",
    "plot": "core:plot",
    "poster_urls": "core:poster_urls",
    "thumb_urls": "core:thumb_urls",
    "trailer_urls": "absent:[]",
    "score": "absent:None",
    "external_id": "narrowed:canonical_digits",
    "source_url": "narrowed:source_urls[0]",
    "directors": "absent:[]",
    "extrafanart": "core:extrafanart",
}


def is_clean_http_url(value: object) -> bool:
    """I22：带 host 的绝对 http(s) URL；无控制字符、无首尾空白。只判定，不改写。"""
    if not isinstance(value, str) or not value or value != value.strip():
        return False
    if any(ord(char) < 0x20 or ord(char) == 0x7F for char in value):
        return False
    try:
        parts = urlsplit(value)
        host = parts.hostname
    except ValueError:
        return False
    return parts.scheme.lower() in ("http", "https") and bool(host)


def filter_urls(urls: tuple[str, ...]) -> tuple[str, ...]:
    """只**删除**不合规项；不重排、不改写、不规范化大小写。"""
    return tuple(url for url in urls if is_clean_http_url(url))


def narrow_source_url(source_urls: tuple[str, ...]) -> str | None:
    """N-1：``source_urls`` 中第一个满足 I22 的 URL；没有则 ``None``。"""
    for url in source_urls:
        if is_clean_http_url(url):
            return url
    return None


def narrow_external_id(canonical: str) -> str | None:
    """N-2：canonical 号的数字部分（``FC2-4825061`` -> ``4825061``）；**不**使用 Core 的 ``external_ids``。"""
    _prefix, separator, digits = canonical.partition("-")
    return digits if separator and digits else None


def map_record(metadata: NormalizedMetadata, canonical: str) -> AdapterRecord:
    """表 H：``NormalizedMetadata`` -> ``AdapterRecord``（纯函数；确定性）。"""
    return AdapterRecord(
        number=canonical,
        title=metadata.title,
        studio=metadata.studio,
        publisher=metadata.publisher,
        release=metadata.release,
        runtime=metadata.runtime,
        actors=tuple(name for name in metadata.actors if name.strip()),
        tags=tuple(metadata.tags),
        plot=metadata.plot,
        poster_urls=filter_urls(metadata.poster_urls),
        thumb_urls=filter_urls(metadata.thumb_urls),
        extrafanart=filter_urls(metadata.extrafanart),
        source_url=narrow_source_url(metadata.source_urls),
        external_id=narrow_external_id(canonical),
    )


# ------------------------------------------------------------------------------------------ 表 F：状态映射


def map_aggregation(result: AggregationResult, canonical: str) -> AdapterFound | AdapterNoMatch | AdapterFailure:
    """``AggregationResult`` -> 中立结果（合同 16；PARTIAL 是可用结果，不是错误）。"""
    if result.status is AggregateStatus.SUCCESS or result.status is AggregateStatus.PARTIAL:
        metadata = result.metadata
        if metadata is None:
            return AdapterFailure("unexpected", internal_error_detail("MissingMetadata"))
        degraded: tuple[tuple[str, str], ...] = ()
        if result.status is AggregateStatus.PARTIAL:
            degraded = tuple(
                (item.source_id, _kind_value(item)) for item in result.source_results if item.status in _OPERATIONAL_STATUSES
            )
        return AdapterFound(map_record(metadata, canonical), degraded)
    if result.status is not AggregateStatus.FAILED:
        return AdapterFailure("unexpected", internal_error_detail("UnknownAggregateStatus"))
    operational = tuple(item for item in result.source_results if item.status in _OPERATIONAL_STATUSES)
    if not operational:
        return AdapterNoMatch("all_not_found")
    reason = pick_reason(tuple(reason_for_kind(item.error_kind) for item in operational))
    return AdapterFailure(reason, build_detail(result.source_results))
