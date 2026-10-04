"""P5-C1 表 B（E5 / E6）：SearchQuery -> canonical FC2 边界；规范化完全委托 Core。"""

from __future__ import annotations

import ast
import enum
from pathlib import Path

import pytest

from fc2_amane_adapter import _number
from fc2_amane_adapter._number import MAX_NUMBER_CHARS, read_query_fields, resolve_query
from fc2_amane_adapter._outcome import AdapterFailure, AdapterNoMatch

NUMBER_SOURCE = Path(_number.__file__)


class _ContentType(str, enum.Enum):
    FC2 = "fc2"
    CENSORED = "censored"


class _Query:
    def __init__(self, number, content_type=None):
        self.number = number
        self.content_type = content_type

    @property
    def file_path(self):  # 绝不应被读取
        raise AssertionError("file_path must never be read")

    file_hash = raw_results = partial_result = file_path


@pytest.mark.parametrize(
    "dirty",
    [
        "FC2-1234567",
        "FC2PPV-1234567",
        "FC2-PPV-1234567",
        "[广告]FC2PPV-1234567",
        "xxx@FC2PPV-1234567",
        "fc2-ppv-1234567",
        " FC2-PPV-1234567 ",
    ],
)
def test_dirty_forms_are_canonicalised_by_core(dirty):
    assert resolve_query(dirty, None) == "FC2-1234567"


@pytest.mark.parametrize(
    ("raw", "canonical"),
    [("FC2-12345", "FC2-12345"), ("FC2-PPV-4825061", "FC2-4825061"), ("FC2PPV-12345678", "FC2-12345678")],
)
def test_five_to_eight_digit_canonical_forms(raw, canonical):
    assert resolve_query(raw, "fc2") == canonical


@pytest.mark.parametrize(
    "garbage",
    [
        "",
        "   ",
        "abc",
        "FC2-",
        "FC2-1234",  # 4 位
        "FC2-123456789",  # 9 位：Amane 的 FC2-\d{5,} 会接受，Core 以 [0-9]{5,8} 为准
        "FC2-１２３４５６７",  # 全角数字
        "FC2-PPV-",
        "ABC-123",
    ],
)
def test_not_fc2_is_no_match_never_a_request(garbage):
    assert resolve_query(garbage, None) == AdapterNoMatch("not_fc2")


@pytest.mark.parametrize("content_type", ["censored", "uncensored", "western", "amateur", "", _ContentType.CENSORED, 7])
def test_b2_other_content_type_is_no_match_even_for_a_valid_number(content_type):
    assert resolve_query("FC2-PPV-1234567", content_type) == AdapterNoMatch("content_type")


@pytest.mark.parametrize("content_type", [None, "fc2", _ContentType.FC2])
def test_b2_none_and_fc2_content_types_continue(content_type):
    assert resolve_query("FC2-PPV-1234567", content_type) == "FC2-1234567"


def test_b2_precedes_b3_and_b4():
    assert resolve_query("x" * 1000, "censored") == AdapterNoMatch("content_type")


def test_b3_length_boundary_is_256():
    padded = "x" * (MAX_NUMBER_CHARS - len("@FC2PPV-1234567")) + "@FC2PPV-1234567"
    assert len(padded) == MAX_NUMBER_CHARS
    assert resolve_query(padded + "x", None) == AdapterNoMatch("number_too_long")
    assert not isinstance(resolve_query(padded, None), AdapterFailure)


@pytest.mark.parametrize("number", [None, 1234567, b"FC2-1234567", ["FC2-1234567"], object()])
def test_b1_non_string_number_is_unexpected_failure(number):
    result = resolve_query(number, None)
    assert result == AdapterFailure("unexpected", "invalid search query")


def test_b1_foreign_object_without_attributes_is_failure_not_attribute_error():
    assert read_query_fields(object()) == AdapterFailure("unexpected", "invalid search query")

    class OnlyNumber:
        number = "FC2-1234567"

    assert read_query_fields(OnlyNumber()) == AdapterFailure("unexpected", "invalid search query")


def test_only_number_and_content_type_are_ever_read():
    query = _Query("FC2-PPV-1234567", _ContentType.FC2)
    assert read_query_fields(query) == ("FC2-PPV-1234567", _ContentType.FC2)  # file_path 等属性会抛 AssertionError
    assert resolve_query(*read_query_fields(query)) == "FC2-1234567"


def test_unread_query_attributes_do_not_appear_in_the_module_ast():
    tree = ast.parse(NUMBER_SOURCE.read_text(encoding="utf-8"))
    names = {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
    names |= {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    assert not names & {"file_path", "file_hash", "partial_result", "raw_results", "language"}


def test_number_module_has_no_fc2_parser_of_its_own():
    """I7：规范化只在 Core；本模块不含正则 / 字符串解析。"""
    tree = ast.parse(NUMBER_SOURCE.read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported |= {alias.name for alias in node.names}
        elif isinstance(node, ast.ImportFrom):
            imported.add(("." * node.level) + (node.module or ""))
    assert imported == {"__future__", "fc2_metadata_core.normalize", "._outcome"}
    parsing_methods = {"replace", "split", "strip", "startswith", "isdigit", "lstrip", "rstrip", "removeprefix", "upper", "lower"}
    called = {
        node.func.attr for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert not called & parsing_methods
