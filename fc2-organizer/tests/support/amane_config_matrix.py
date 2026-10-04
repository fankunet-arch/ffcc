"""P5-C1 R1（P5-C1-L1-01）：配置校验矩阵——``parse_settings``（权威）与宿主 Pydantic 模型 ``Fc2MetadataConfig`` 共用。

同一张矩阵被两处使用，保证“宿主入口语义 == parse_settings 语义”：

* 主进程纯逻辑测试（``test_amane_settings.py``）：断言 ``parse_settings`` 对每一行的 accept / reject 等于期望；
* 真实 Amane v0.15.0 宿主见证 H-04（``host_scripts/h_scenarios.py``）：对每一行同时调用宿主模型与 ``parse_settings``，
  断言二者结果**一致**且等于期望。

本模块**不 import amane / pydantic**。每行：``(label, 原始配置对象, 是否应被接受)``。
"""

from __future__ import annotations

from decimal import Decimal

__all__ = ["CONFIG_MATRIX", "DEADLINE_MATRIX", "RAW_STRING_DEADLINES"]

_NAN = float("nan")
_INF = float("inf")

#: ``source_deadline_seconds`` 的原始值矩阵（合同 §11：有限数值、int / float 语义、bool 不是数值、范围 (0, 600]）。
DEADLINE_MATRIX: tuple[tuple[str, object, bool], ...] = (
    ("int 20", 20, True),
    ("float 20.0", 20.0, True),
    ("float 0.5", 0.5, True),
    ("int 600", 600, True),
    ("float 600.0", 600.0, True),
    ("str '20'", "20", False),
    ("str '20.0'", "20.0", False),
    ("str ' 20 '", " 20 ", False),
    ("str '1e1'", "1e1", False),
    ("str 'x'", "x", False),
    ("str ''", "", False),
    ("bool True", True, False),
    ("bool False", False, False),
    ("nan", _NAN, False),
    ("inf", _INF, False),
    ("-inf", -_INF, False),
    ("int 0", 0, False),
    ("float 0.0", 0.0, False),
    ("int -1", -1, False),
    ("float -0.5", -0.5, False),
    ("int 601", 601, False),
    ("float 600.0001", 600.0001, False),
    ("None", None, False),
    ("bytes b'20'", b"20", False),
    ("list [20]", [20], False),
    ("dict", {"value": 20}, False),
    ("Decimal 20", Decimal("20"), False),  # Pydantic 的 float 字段会宽松接受 Decimal；parse_settings 不接受
)

#: 其中会被 Pydantic 宽松模式“先转换成数值”的原始字符串（回归焦点）。
RAW_STRING_DEADLINES: tuple[str, ...] = ("20", "20.0", " 20 ", "1e1")

#: 完整配置矩阵：H-04 与主进程共用（宿主模型与 ``parse_settings`` 必须对每一行给出同一裁决）。
CONFIG_MATRIX: tuple[tuple[str, object, bool], ...] = (
    ("empty", {}, True),
    ("sources null", {"sources": None}, True),
    ("one source", {"sources": [{"id": "javdb"}]}, True),
    ("sources as tuple", {"sources": ({"id": "javdb"},)}, True),
    (
        "mirror + disabled",
        {"sources": [{"id": "av123", "enabled": False}, {"id": "javdb", "base_url": "https://mirror.example/prefix"}]},
        True,
    ),
    ("unknown source id", {"sources": [{"id": "nope"}]}, False),
    ("duplicate source id", {"sources": [{"id": "javdb"}, {"id": "javdb"}]}, False),
    ("empty sources list", {"sources": []}, False),
    ("all disabled", {"sources": [{"id": "javdb", "enabled": False}]}, False),
    ("base_url userinfo", {"sources": [{"id": "javdb", "base_url": "https://user:pw@mirror.example"}]}, False),
    ("base_url ftp", {"sources": [{"id": "javdb", "base_url": "ftp://mirror.example"}]}, False),
    ("base_url query", {"sources": [{"id": "javdb", "base_url": "https://mirror.example/?q=1"}]}, False),
    ("base_url int", {"sources": [{"id": "javdb", "base_url": 5}]}, False),
    ("enabled 'yes'", {"sources": [{"id": "javdb", "enabled": "yes"}]}, False),
    ("enabled 1", {"sources": [{"id": "javdb", "enabled": 1}]}, False),
    ("entry extra field", {"sources": [{"id": "javdb", "extra": 1}]}, False),
    ("id int", {"sources": [{"id": 5}]}, False),
    ("sources str", {"sources": "javdb"}, False),
    ("unknown top-level field", {"unknown_field": 1}, False),
    *[(f"deadline {label}", {"source_deadline_seconds": value}, accepted) for label, value, accepted in DEADLINE_MATRIX],
)
