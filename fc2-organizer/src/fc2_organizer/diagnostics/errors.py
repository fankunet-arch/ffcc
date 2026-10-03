"""Error hierarchy of ``fc2_organizer.diagnostics`` (P4-C9 contract section 8.4).

Imports nothing but ``__future__``.

Contract rules:

* messages are fixed wording only (a constant name or an item position at most) -- never a path, a
  title, a URL, a source text, a secret, a Validation-Only value or the text of a lower-layer
  exception;
* every diagnostics error is raised outside any ``except`` block, so ``__cause__`` /
  ``__context__`` stay ``None`` (no lower-layer exception is ever chained);
* these errors mean *caller error, tampering or a resource limit*; they never change the original
  batch result, retry eligibility or any file.
"""

from __future__ import annotations

__all__ = [
    "DiagnosticsError",
    "DiagnosticsInputError",
    "DiagnosticsIntegrityError",
    "DiagnosticsContractError",
    "DiagnosticsResourceLimitError",
    "DiagnosticsUnsafeValueError",
    "DiagnosticsSerializationError",
]


class DiagnosticsError(Exception):
    """Base class of every ``fc2_organizer.diagnostics`` error."""


class DiagnosticsInputError(DiagnosticsError, TypeError):
    """An argument is not the exact public input type / policy enum."""


class DiagnosticsIntegrityError(DiagnosticsError, ValueError):
    """The input object graph failed local validation, or a diagnostics graph was altered."""


class DiagnosticsContractError(DiagnosticsError, ValueError):
    """A diagnostics model was constructed in violation of its own invariants."""


class DiagnosticsResourceLimitError(DiagnosticsError, RuntimeError):
    """An item count / structural limit / output byte limit was exceeded."""


class DiagnosticsUnsafeValueError(DiagnosticsError, ValueError):
    """A value that would be output violates the safe text / numeric rules."""


class DiagnosticsSerializationError(DiagnosticsError, RuntimeError):
    """Another failure of the JSON encoding stage."""
