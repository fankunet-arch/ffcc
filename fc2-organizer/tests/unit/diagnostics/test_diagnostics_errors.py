"""P4-C9 contract section 8.4 / 24: the error hierarchy, fixed wording, no chaining."""

from __future__ import annotations

import dataclasses

import pytest
from fc2_organizer.diagnostics import (
    DiagnosticsContractError,
    DiagnosticsError,
    DiagnosticsInputError,
    DiagnosticsIntegrityError,
    DiagnosticsResourceLimitError,
    DiagnosticsSerializationError,
    DiagnosticsUnsafeValueError,
)

from . import _builders as b

_HIERARCHY = [
    (DiagnosticsInputError, TypeError),
    (DiagnosticsIntegrityError, ValueError),
    (DiagnosticsContractError, ValueError),
    (DiagnosticsResourceLimitError, RuntimeError),
    (DiagnosticsUnsafeValueError, ValueError),
    (DiagnosticsSerializationError, RuntimeError),
]


def test_base_class_is_an_exception_and_not_a_builtin_subclass():
    assert issubclass(DiagnosticsError, Exception)
    assert DiagnosticsError.__bases__ == (Exception,)


@pytest.mark.parametrize(("error", "builtin"), _HIERARCHY)
def test_every_error_derives_from_the_base_and_its_builtin(error, builtin):
    assert error.__bases__ == (DiagnosticsError, builtin)
    assert issubclass(error, DiagnosticsError)


def test_there_are_exactly_seven_error_classes():
    import fc2_organizer.diagnostics.errors as errors

    assert errors.__all__ == [
        "DiagnosticsError", "DiagnosticsInputError", "DiagnosticsIntegrityError", "DiagnosticsContractError",
        "DiagnosticsResourceLimitError", "DiagnosticsUnsafeValueError", "DiagnosticsSerializationError",
    ]


def test_errors_module_imports_nothing_but_future():
    import ast
    from pathlib import Path

    import fc2_organizer.diagnostics.errors as errors

    tree = ast.parse(Path(errors.__file__).read_text(encoding="utf-8"))
    imports = [n for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom))]
    assert [n.module for n in imports] == ["__future__"]


def test_model_violation_message_is_fixed_wording_without_the_offending_value():
    secret = "C9CANARY-SECRET-VALUE"
    with pytest.raises(DiagnosticsContractError) as caught:
        b.make_source(source_id=secret + "/../x")
    assert secret not in str(caught.value) and secret not in repr(caught.value.args)


def test_model_violation_is_raised_outside_any_except_block_and_is_not_chained():
    with pytest.raises(DiagnosticsContractError) as caught:
        dataclasses.replace(b.make_item(), index=-1)
    assert caught.value.__cause__ is None and caught.value.__context__ is None
    assert caught.value.__suppress_context__ is False


def test_messages_are_non_empty_strings_without_path_separators_of_inputs():
    with pytest.raises(DiagnosticsContractError) as caught:
        b.make_item(source_name="a/b")
    assert isinstance(str(caught.value), str) and str(caught.value)
    assert "a/b" not in str(caught.value)
