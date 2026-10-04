"""adapter 内部的中立结果类型（纯模块；冻结的形状，合同第 16 节）。

``AdapterFound`` / ``AdapterNoMatch`` / ``AdapterFailure`` 在 S1 随号码边界一同建立；
``AggregationResult`` -> 中立结果的映射（表 F / 表 G / 表 H）在 S2 补入本模块。
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = [
    "AdapterRecord",
    "AdapterFound",
    "AdapterNoMatch",
    "AdapterFailure",
    "NO_MATCH_REASONS",
    "FAILURE_REASONS",
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
