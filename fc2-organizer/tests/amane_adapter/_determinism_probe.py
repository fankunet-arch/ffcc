"""P5-C1 E20：确定性探针（子进程运行；不 import amane；非测试模块）。

在给定 ``PYTHONHASHSEED`` 下执行一组固定场景，把中立结果序列化为 JSON 打印到 stdout。
``test_amane_determinism.py`` 以 0 / 1 / 2 三个种子运行本脚本并要求输出逐字节相同。
"""

from __future__ import annotations

import asyncio
import dataclasses
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for entry in (ROOT / "src", ROOT / "tests", ROOT / "adapters" / "amane", ROOT / "tests" / "amane_adapter"):
    sys.path.insert(0, str(entry))

from _amane_scenarios import (  # noqa: E402
    client_4825061,
    client_4824605_not_found_everywhere,
    client_4979299,
    runtime_for,
    url_for,
)
from support.amane_host_fakes import FakeRequestError, FakeSourceError  # noqa: E402

HOST_ERRORS = {"request_error_types": (FakeRequestError,), "source_error_types": (FakeSourceError,)}
ORDERS = (
    ("fc2db_net", "javdb", "av123"),
    ("av123", "javdb", "fc2db_net"),
    ("javdb", "fc2db_net", "av123"),
)


def _encode(outcome) -> dict:
    return {"type": type(outcome).__name__, "value": dataclasses.asdict(outcome)}


def _run(runtime, number, content_type="fc2"):
    return _encode(asyncio.run(runtime.lookup(number, content_type)))


def main() -> None:
    results: dict[str, object] = {}
    for order in ORDERS:
        settings = {"sources": [{"id": source_id} for source_id in order]}
        results["allhit:" + ",".join(order)] = _run(runtime_for(client_4979299(), settings), "FC2-PPV-4979299")
    results["success"] = _run(runtime_for(client_4825061()), "FC2-PPV-4825061")
    partial = client_4825061()
    partial.replace(url_for("fc2db_net", "4825061"), FakeRequestError("timeout"))
    partial.replace(url_for("av123", "4825061"), FakeRequestError("network"))
    results["partial"] = _run(runtime_for(partial, **HOST_ERRORS), "FC2-4825061")
    mixed = client_4824605_not_found_everywhere()
    mixed.replace(url_for("javdb", "4824605"), FakeRequestError("timeout"))
    mixed.replace(url_for("av123", "4824605"), FakeRequestError("unexpected"))
    results["mixed_failure"] = _run(runtime_for(mixed, **HOST_ERRORS), "FC2-4824605")
    results["all_not_found"] = _run(runtime_for(client_4824605_not_found_everywhere()), "FC2-4824605")
    results["non_fc2"] = _run(runtime_for(client_4825061()), "ABC-123")
    results["content_type"] = _run(runtime_for(client_4825061()), "FC2-4825061", "censored")
    results["foreign"] = _run(runtime_for(client_4825061()), 12345)
    sys.stdout.write(json.dumps(results, sort_keys=True, ensure_ascii=True, indent=1) + "\n")


if __name__ == "__main__":
    main()
