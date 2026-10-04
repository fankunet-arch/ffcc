"""P5-C1 §25.3 集合 B 的冻结冒烟：真实 ``AdapterRuntime`` 构造路径 + 一次 fake-bridge aggregate。

在 Python 3.12 与 3.14 上都必须通过（宿主解释器是 3.14+；Core 正式证据环境是 3.12）：
registry / ``AggregationConfig``（``no_retry``）/ ``SourceResourceGovernor`` / ``AmaneHttpBridge`` /
``MultiSourceEngine`` 全部是真实对象；web client 是 duck-typed 替身（脚本化返回既有 fixture 页面与 404）。
"""

from __future__ import annotations

import asyncio

from _amane_scenarios import client_4825061
from fc2_amane_adapter._bridge import AmaneHttpBridge
from fc2_amane_adapter._outcome import AdapterFound
from fc2_amane_adapter._runtime import AdapterRuntime
from fc2_amane_adapter._settings import parse_settings
from fc2_metadata_core.aggregation import AggregateStatus, MultiSourceEngine, RetryPolicy
from fc2_metadata_core.resource_control import SourceResourceGovernor


def test_core_runtime_objects_and_one_fake_bridge_aggregate():
    client = client_4825061()
    runtime = AdapterRuntime(parse_settings({}), client)
    assert isinstance(runtime._engine, MultiSourceEngine)
    assert isinstance(runtime._bridge, AmaneHttpBridge)
    assert isinstance(runtime.governor, SourceResourceGovernor)
    assert runtime._config.retry_policy == RetryPolicy.no_retry()

    result = asyncio.run(runtime._engine.aggregate("FC2-4825061"))
    assert result.status is AggregateStatus.SUCCESS
    assert len(client.calls) == 3  # L1：桥 get 调用数 = S = 3
    for _method, _url, kwargs in client.calls:
        assert kwargs["ok_statuses"] >= frozenset(range(300, 600))

    outcome = asyncio.run(AdapterRuntime(parse_settings({}), client_4825061()).lookup("FC2-PPV-4825061", "fc2"))
    assert isinstance(outcome, AdapterFound) and outcome.record.number == "FC2-4825061"
