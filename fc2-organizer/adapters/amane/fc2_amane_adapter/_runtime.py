"""一次构造、多次复用的 Core 调用封装（纯模块；合同第 12 节与第 18 节）。

``AdapterRuntime`` 在构造时**一次性**建立 registry / ``AggregationConfig``（``RetryPolicy.no_retry()``）/
``SourceResourceGovernor`` / 传输桥 / ``MultiSourceEngine``；之后每次 ``lookup`` 只调用 ``engine.aggregate``。
adapter 无状态；governor / breaker 是内存态，随 provider 生命周期（宿主 rebuild 时重置，L-09）。

取消：本模块唯一的宽捕获 ``except Exception`` 只包住 ``engine.aggregate``；``CancelledError`` /
``KeyboardInterrupt`` / ``SystemExit`` 是 ``BaseException``，原样传播，永不转成 source failure。
"""

from __future__ import annotations

import logging

from fc2_metadata_core.aggregation import MultiSourceEngine
from fc2_metadata_core.resource_control import SourceResourceGovernor
from fc2_metadata_core.sources.adapters import build_default_registry

from ._bridge import AmaneHttpBridge
from ._number import resolve_query
from ._outcome import (
    AdapterFailure,
    AdapterFound,
    AdapterNoMatch,
    internal_error_detail,
    map_aggregation,
)
from ._settings import AdapterSettings, build_aggregation_config

__all__ = ["LOGGER_NAME", "PARTIAL_LOG_FORMAT", "AdapterRuntime"]

#: 合同 §21：唯一的日志器与格式；仅在 PARTIAL 时发一条 WARNING。
LOGGER_NAME = "ffcc.fc2_metadata"
PARTIAL_LOG_FORMAT = "partial FC2 result for %s: %s"

_LOGGER = logging.getLogger(LOGGER_NAME)


class AdapterRuntime:
    def __init__(
        self,
        settings: AdapterSettings,
        web_client: object,
        *,
        bridge_type: type[AmaneHttpBridge] | None = None,
    ) -> None:
        # None = 基类（不映射任何宿主异常）；生产路径由 plugin.py 传入其私有子类（合同 §13.2：构造器签名不变）。
        if bridge_type is None:
            bridge_type = AmaneHttpBridge
        elif not (isinstance(bridge_type, type) and issubclass(bridge_type, AmaneHttpBridge)):
            raise TypeError("bridge_type must be AmaneHttpBridge or a subclass of it")
        self._registry = build_default_registry()
        self._config = build_aggregation_config(settings)
        self._governor = SourceResourceGovernor()
        self._bridge = bridge_type(web_client)
        self._engine = MultiSourceEngine(self._config, self._registry, self._bridge, governor=self._governor)

    @property
    def governor(self) -> SourceResourceGovernor:
        return self._governor

    async def lookup(self, number: object, content_type: object) -> AdapterFound | AdapterNoMatch | AdapterFailure:
        outcome, _cause = await self.lookup_with_cause(number, content_type)
        return outcome

    async def lookup_with_cause(
        self, number: object, content_type: object
    ) -> tuple[AdapterFound | AdapterNoMatch | AdapterFailure, Exception | None]:
        """与 ``lookup`` 相同，另返回**原始**异常对象（仅当 ``engine.aggregate`` 抛出非取消 ``Exception`` 时非 ``None``）。

        合同表 F：``AdapterFailure("unexpected", "internal adapter error: <ExceptionTypeName>")`` 的 ``detail`` 只含类型名，
        而 Amane 边界必须 ``raise SourceError(...) from <原始异常>``。``AdapterFailure`` 的冻结形状 ``(reason, detail)`` 不变；
        原始异常经由**返回值**带出（不使用任何全局可变状态，并发安全）。
        """
        resolved = resolve_query(number, content_type)
        if not isinstance(resolved, str):
            return resolved, None
        try:
            result = await self._engine.aggregate(resolved)
        except Exception as exc:
            return AdapterFailure("unexpected", internal_error_detail(type(exc).__name__)), exc
        outcome = map_aggregation(result, resolved)
        if isinstance(outcome, AdapterFound) and outcome.degraded:
            _LOGGER.warning(
                PARTIAL_LOG_FORMAT,
                resolved,
                "; ".join(f"{source_id}={kind_value}" for source_id, kind_value in outcome.degraded),
            )
        return outcome, None
