"""P4-C8 S1: error hierarchy (contract section 7.4)."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

import fc2_organizer.orchestration as orchestration
from fc2_organizer.orchestration import (
    MAX_BATCH_ITEMS,
    OrchestrationBusyError,
    OrchestrationConfigError,
    OrchestrationConsumedError,
    OrchestrationContractError,
    OrchestrationError,
    OrchestrationInputError,
    OrchestrationIntegrityError,
    OrchestrationResourceLimitError,
    OrchestrationRetryError,
    ResourceLimitReason,
)
from fc2_organizer.orchestration import errors as errors_module
from fc2_organizer.orchestration import recognition

PKG_ROOT = Path(orchestration.__file__).resolve().parent

_HIERARCHY = {
    OrchestrationConfigError: ValueError,
    OrchestrationInputError: ValueError,
    OrchestrationBusyError: RuntimeError,
    OrchestrationContractError: ValueError,
    OrchestrationIntegrityError: ValueError,
    OrchestrationConsumedError: RuntimeError,
    OrchestrationRetryError: ValueError,
    OrchestrationResourceLimitError: RuntimeError,
}


def test_base_is_a_plain_exception():
    assert OrchestrationError.__bases__ == (Exception,)
    assert not issubclass(OrchestrationError, (ValueError, RuntimeError))


@pytest.mark.parametrize("error, builtin", list(_HIERARCHY.items()))
def test_each_error_has_exactly_the_frozen_bases(error, builtin):
    assert error.__bases__ == (OrchestrationError, builtin)
    assert issubclass(error, OrchestrationError) and issubclass(error, builtin)


def test_there_are_exactly_nine_error_classes():
    classes = {name for name, value in vars(errors_module).items()
               if isinstance(value, type) and issubclass(value, BaseException)}
    assert classes == {e.__name__ for e in _HIERARCHY} | {"OrchestrationError"}
    assert set(errors_module.__all__) == classes


def test_resource_limit_error_keeps_the_reason_object_and_fixed_messages():
    item_limit = OrchestrationResourceLimitError(ResourceLimitReason.BATCH_ITEM_LIMIT)
    assert item_limit.reason is ResourceLimitReason.BATCH_ITEM_LIMIT
    assert str(item_limit) == f"batch resource limit reached: batch_item_limit (MAX_BATCH_ITEMS={MAX_BATCH_ITEMS})"
    retained = OrchestrationResourceLimitError(ResourceLimitReason.RETAINED_BYTES_LIMIT)
    assert retained.reason is ResourceLimitReason.RETAINED_BYTES_LIMIT
    assert str(retained) == "batch resource limit reached: retained_bytes_limit"
    assert item_limit.__cause__ is None and item_limit.__context__ is None


def test_resource_limit_message_never_contains_caller_text():
    class Hostile:
        value = r"C:\secret\path https://example.test/?token=abc"

    error = OrchestrationResourceLimitError(Hostile())
    assert str(error) == "batch resource limit reached"
    assert "secret" not in str(error) and "token" not in str(error)


def test_errors_module_imports_only_future():
    tree = ast.parse((PKG_ROOT / "errors.py").read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add(node.module)
    assert imported == {"__future__"}


def test_no_production_raise_is_chained_or_inside_an_except_block():
    # Contract section 7.4: every P4-C8 error is raised outside any `except` block (no __context__)
    # and never with `raise ... from ...` (no __cause__).
    for path in PKG_ROOT.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Raise):
                assert node.cause is None, (path.name, node.lineno)
            if isinstance(node, ast.ExceptHandler):
                for inner in ast.walk(node):
                    assert not isinstance(inner, ast.Raise), (path.name, inner.lineno)


def test_iteration_error_is_mapped_without_chaining_or_message_text():
    class Exploding(list):
        def __iter__(self):
            raise RuntimeError(r"C:\private\file.mp4 https://example.test/secret")

    with pytest.raises(OrchestrationInputError) as info:
        recognition.bounded_snapshot(Exploding())
    assert info.value.__cause__ is None and info.value.__context__ is None
    assert "RuntimeError" in str(info.value)
    assert "private" not in str(info.value) and "secret" not in str(info.value)


def test_resource_limit_from_bounded_snapshot_is_not_chained():
    with pytest.raises(OrchestrationResourceLimitError) as info:
        recognition.bounded_snapshot([object()] * (MAX_BATCH_ITEMS + 1))
    assert info.value.reason is ResourceLimitReason.BATCH_ITEM_LIMIT
    assert info.value.__cause__ is None and info.value.__context__ is None


def test_contract_error_messages_hold_no_path_or_title():
    from ._helpers import LIBRARY, Lineage, tampered

    lineage = Lineage(1)
    item = lineage.preview_item(0)
    with pytest.raises(OrchestrationContractError) as info:
        tampered(item, index=-1).__post_init__()
    text = str(info.value)
    assert LIBRARY not in text and "Example Title" not in text and "FC2-PPV" not in text
    assert info.value.__context__ is None and info.value.__cause__ is None
