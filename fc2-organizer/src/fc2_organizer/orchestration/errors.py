"""Error hierarchy of ``fc2_organizer.orchestration`` (P4-C8 contract section 7.4).

Imports nothing but ``__future__``: in particular it never imports ``models`` (the
``ResourceLimitReason`` enum lives there); ``OrchestrationResourceLimitError`` only keeps the
reason object its (internal) raiser hands over.

Contract rules:

* messages are fixed wording plus enum values, indices and class names only -- never a path, a
  title, a URL, a secret or the text of a lower-layer exception;
* every P4-C8 error is raised outside any ``except`` block, so ``__cause__`` / ``__context__``
  stay ``None`` (no lower-layer exception is ever chained);
* these errors mean *caller error or tampering*; an individual item's outcome is always data.
"""

from __future__ import annotations

__all__ = [
    "OrchestrationError",
    "OrchestrationConfigError",
    "OrchestrationInputError",
    "OrchestrationBusyError",
    "OrchestrationContractError",
    "OrchestrationIntegrityError",
    "OrchestrationConsumedError",
    "OrchestrationRetryError",
    "OrchestrationResourceLimitError",
]


class OrchestrationError(Exception):
    """Base class of every ``fc2_organizer.orchestration`` error."""


class OrchestrationConfigError(OrchestrationError, ValueError):
    """Constructor arguments / ``OrchestrationConfig`` are invalid."""


class OrchestrationInputError(OrchestrationError, ValueError):
    """items / selection / cancel / scope / previous have a wrong type or value, or a preview / result
    does not match this orchestrator's configuration."""


class OrchestrationBusyError(OrchestrationError, RuntimeError):
    """The orchestrator already has an active operation (busy-first)."""


class OrchestrationContractError(OrchestrationError, ValueError):
    """A model invariant is violated at construction time."""


class OrchestrationIntegrityError(OrchestrationError, ValueError):
    """A preview / result object graph was altered after construction or is internally inconsistent."""


class OrchestrationConsumedError(OrchestrationError, RuntimeError):
    """The preview was already executed / the result already retried / the retry result already merged."""


class OrchestrationRetryError(OrchestrationError, ValueError):
    """``merge_retry`` / ``preview_retry`` fail-closed mismatch."""


# Fixed messages keyed by ``ResourceLimitReason.value`` (contract section 7.4). The numeric limit in the
# first message is the frozen ``models.MAX_BATCH_ITEMS``; the constant itself is defined only in
# ``models.py`` (contract section 34.1) and test_orchestration_errors pins this text to it.
_RESOURCE_LIMIT_MESSAGES = {
    "batch_item_limit": "batch resource limit reached: batch_item_limit (MAX_BATCH_ITEMS=2000)",
    "retained_bytes_limit": "batch resource limit reached: retained_bytes_limit",
}
_RESOURCE_LIMIT_FALLBACK = "batch resource limit reached"


class OrchestrationResourceLimitError(OrchestrationError, RuntimeError):
    """A batch-level hard resource limit was reached (contract section 19.6).

    ``reason`` is the ``ResourceLimitReason`` member handed over by the raiser, kept as is.
    """

    def __init__(self, reason: object) -> None:
        self.reason = reason
        value = getattr(reason, "value", None)
        message = _RESOURCE_LIMIT_MESSAGES.get(value) if type(value) is str else None
        super().__init__(message if message is not None else _RESOURCE_LIMIT_FALLBACK)
