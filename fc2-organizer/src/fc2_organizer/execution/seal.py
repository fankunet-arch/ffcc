"""Fingerprints, process-local seals and one-shot consumption (contract section 15).

* :func:`encode` -- injective canonical encoding: one tag byte + 8-byte big-endian
  length + payload per value; tuples carry an item count and self-delimiting items.
  ``str`` is encoded ``utf-8`` with ``surrogatepass``; nothing relies on ``repr`` or
  ``hash()``.
* :func:`plan_fingerprint` / :func:`manifest_fingerprint` -- SHA-256 over a
  domain-separated encoding of an *already validated* plan / manifest.
* A 32-byte key is generated once per process at import (``secrets.token_bytes``);
  it is never exported, logged or stored in any model or message. :func:`seal_of`
  is an HMAC-SHA256 over every sealed field; :func:`verify_seal` compares with
  ``hmac.compare_digest``. A forged model, a field rewritten with
  ``object.__setattr__`` or a model from another process never verifies.
* :func:`register_consumption` -- process-local, lock-protected one-shot registry.

Standard library (``hashlib``, ``hmac``, ``secrets``, ``threading``) and this package only.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import threading

from fc2_organizer.execution.errors import ExecutionModelError
from fc2_organizer.execution.models import (
    ENCODABLE_ENUMS,
    CompletedEffect,
    EntryIdentity,
    ExecutionCheckpoint,
    ExecutionPreflight,
    ExecutionUnit,
    LeftoverTemporary,
    PreflightBlocker,
)

__all__ = [
    "encode",
    "plan_fingerprint",
    "manifest_fingerprint",
    "seal_of",
    "verify_seal",
    "sealed",
    "register_consumption",
    "is_consumed",
]

_PROCESS_KEY: bytes = secrets.token_bytes(32)
_SEAL_DOMAIN = b"fc2-organizer/p4-c7/seal/v1"
_PLAN_DOMAIN = "fc2-organizer/p4-c7/plan/v1"
_MANIFEST_DOMAIN = "fc2-organizer/p4-c7/manifest/v1"
_ZERO_SEAL = "0" * 64

# Execution value models that may appear inside a sealed model (encoded field by field).
_NESTED_MODELS = (EntryIdentity, CompletedEffect, LeftoverTemporary, PreflightBlocker, ExecutionUnit)
_SEALED_MODELS = (ExecutionCheckpoint, ExecutionPreflight)
# Fields of a sealed model that are *not* covered directly: the seal itself, and the
# preflight's caller-held plan / artifacts, which are covered through their fingerprints.
_UNSEALED_FIELDS = frozenset({"seal", "plan", "artifacts"})

_CONSUMED: set[str] = set()
_CONSUMED_LOCK = threading.Lock()


# --------------------------------------------------------------------------- encoding


def _frame(tag: bytes, payload: bytes) -> bytes:
    return tag + len(payload).to_bytes(8, "big") + payload


def encode(value: object) -> bytes:
    """Injective canonical encoding of ``None``/``bool``/``int``/``str``/``bytes``/enum/
    ``tuple`` and the execution value models. Anything else is refused."""
    kind = type(value)
    if value is None:
        return _frame(b"N", b"")
    if kind is bool:
        return _frame(b"O", b"1" if value else b"0")
    if kind is int:
        return _frame(b"I", str(value).encode("ascii"))
    if kind is str:
        return _frame(b"S", value.encode("utf-8", "surrogatepass"))
    if kind is bytes:
        return _frame(b"B", value)
    if kind in ENCODABLE_ENUMS:
        return _frame(b"E", f"{kind.__qualname__}.{value.value}".encode("utf-8"))
    if kind is tuple:
        return b"T" + len(value).to_bytes(8, "big") + b"".join(encode(item) for item in value)
    if kind in _NESTED_MODELS or kind in _SEALED_MODELS:
        return _frame(b"M", kind.__qualname__.encode("ascii")) + encode(_model_values(value))
    raise ExecutionModelError("value cannot be canonically encoded")


def _model_values(model: object) -> tuple[object, ...]:
    names = [name for name in type(model).__dataclass_fields__ if name not in _UNSEALED_FIELDS]
    return tuple(getattr(model, name) for name in names)


# --------------------------------------------------------------------------- fingerprints


def _digest(value: tuple[object, ...]) -> str:
    return hashlib.sha256(encode(value)).hexdigest()


def plan_fingerprint(plan: object) -> str:
    """SHA-256 fingerprint of an already validated ``OrganizePlan`` (contract section 15.1)."""
    operations = tuple(
        (op.kind.value, op.target.absolute_path, None if op.source is None else op.source.absolute_path)
        for op in plan.operations
    )
    return _digest((
        _PLAN_DOMAIN,
        plan.source_path, plan.source_relative_path, plan.source_extension, plan.source_index,
        plan.source_size, plan.canonical_number, plan.library_root,
        plan.target_directory.absolute_path, plan.target_media_path.absolute_path,
        plan.nfo_path.absolute_path, plan.poster_path.absolute_path, plan.fanart_path.absolute_path,
        plan.thumb_path.absolute_path, plan.extrafanart_directory.absolute_path,
        operations,
    ))


def manifest_fingerprint(artifacts: tuple[object, ...]) -> str:
    """SHA-256 fingerprint of an already validated manifest (contract section 7.6)."""
    items = tuple(
        (request.kind.value, request.target_path, request.ordinal, len(request.content),
         hashlib.sha256(request.content).hexdigest())
        for request in artifacts
    )
    return _digest((_MANIFEST_DOMAIN, items))


# --------------------------------------------------------------------------- seals


def seal_of(model: object) -> str:
    """HMAC-SHA256 (process key) over every sealed field of a checkpoint / preflight."""
    if type(model) not in _SEALED_MODELS:
        raise ExecutionModelError("only checkpoints and preflights are sealed")
    message = _SEAL_DOMAIN + encode(_model_values(model)) + encode(type(model).__qualname__)
    return hmac.new(_PROCESS_KEY, message, hashlib.sha256).hexdigest()


def verify_seal(model: object) -> bool:
    """True iff ``model`` carries the seal this process would compute for it right now."""
    if type(model) not in _SEALED_MODELS:
        return False
    claimed = model.seal
    if type(claimed) is not str:
        return False
    return hmac.compare_digest(seal_of(model), claimed)


def sealed(model_type: type, **fields: object) -> object:
    """Construct ``model_type(**fields, seal=<its seal>)`` (checkpoint / preflight only)."""
    if model_type not in _SEALED_MODELS:
        raise ExecutionModelError("only checkpoints and preflights are sealed")
    draft = model_type(**fields, seal=_ZERO_SEAL)
    return model_type(**fields, seal=seal_of(draft))


# --------------------------------------------------------------------------- consumption


def register_consumption(ids: tuple[str, ...]) -> bool:
    """Atomically register every id; ``False`` (and nothing registered) if any was already used."""
    with _CONSUMED_LOCK:
        if any(item in _CONSUMED for item in ids):
            return False
        _CONSUMED.update(ids)
        return True


def is_consumed(item: str) -> bool:
    with _CONSUMED_LOCK:
        return item in _CONSUMED
