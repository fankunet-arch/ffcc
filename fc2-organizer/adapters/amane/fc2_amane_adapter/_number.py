"""SearchQuery -> canonical FC2 边界（纯模块；合同第 10 节表 B）。

在**任何网络活动之前**按 B1..B5 的顺序执行。番号规范化**完全委托** Core 的 ``normalize_fc2_number``：
本模块不含任何 FC2 正则 / 前缀剥离 / 数字提取（I7）。``file_path`` / ``file_hash`` / ``partial_result`` /
``raw_results`` / ``FetchOptions.language`` 一律不读取（I26；``file_path`` 是宿主本机路径，属隐私）。
"""

from __future__ import annotations

from fc2_metadata_core.normalize import FC2RecognitionStatus, normalize_fc2_number

from ._outcome import AdapterFailure, AdapterNoMatch

__all__ = ["MAX_NUMBER_CHARS", "INVALID_QUERY_DETAIL", "read_query_fields", "resolve_query"]

#: B3：有界输入。
MAX_NUMBER_CHARS = 256

#: B1 的固定 detail。
INVALID_QUERY_DETAIL = "invalid search query"

_FC2_CONTENT_TYPE = "fc2"


def _invalid_query() -> AdapterFailure:
    return AdapterFailure("unexpected", INVALID_QUERY_DETAIL)


def read_query_fields(query: object) -> tuple[object, object] | AdapterFailure:
    """只读取 ``number`` 与 ``content_type`` 两个属性（B1：外来对象 -> ``Failed(unexpected)``）。

    ``SearchQuery`` 是无运行时校验的 dataclass；缺少属性的外来对象是宿主缺陷，而不是“没有找到”。
    """
    try:
        number = query.number  # type: ignore[attr-defined]
        content_type = query.content_type  # type: ignore[attr-defined]
    except AttributeError:
        return _invalid_query()
    return number, content_type


def resolve_query(number: object, content_type: object) -> str | AdapterNoMatch | AdapterFailure:
    """表 B 的 B1-B5：返回 canonical（``FC2-<5..8 位数字>``）、``AdapterNoMatch`` 或 ``AdapterFailure``。"""
    # B1
    if not isinstance(number, str):
        return _invalid_query()
    # B2：``StrEnum`` 与 ``str`` 都按值比较；``None`` 表示宿主没有判定类型，继续。
    if content_type is not None and (content_type == _FC2_CONTENT_TYPE) is not True:
        return AdapterNoMatch("content_type")
    # B3
    if len(number) > MAX_NUMBER_CHARS:
        return AdapterNoMatch("number_too_long")
    # B4 / B5：规范化只在 Core 完成。
    result = normalize_fc2_number(number)
    if result.status is not FC2RecognitionStatus.RECOGNIZED or not isinstance(result.canonical, str):
        return AdapterNoMatch("not_fc2")
    return result.canonical
