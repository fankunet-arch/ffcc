"""Fingerprints, process-local seals and one-shot consumption (contract section 15).

* :func:`encode` -- injective canonical encoding: one tag byte + 8-byte big-endian
  length + payload per value; tuples carry an item count and self-delimiting items.
  ``str`` is encoded ``utf-8`` with ``surrogatepass``; nothing relies on ``repr`` or
  ``hash()``.
* :func:`plan_fingerprint` / :func:`manifest_fingerprint` -- SHA-256 over a
  domain-separated encoding of an *already validated* plan / manifest.
* A 32-byte key is generated once per process at import (``secrets.token_bytes``);
  it is never exported, logged or stored in any model or message. :func:`seal_of`
  is an HMAC-SHA256 over the canonical encoding of *every* field except ``seal`` --
  including the *current* content of ``ExecutionPreflight.plan`` / ``.artifacts``,
  encoded structurally through the closed ``models.SEALED_VALUE_TYPES`` set (the
  stored fingerprints are a second, independent layer, contract section 15.5).
  :func:`verify_seal` compares with ``hmac.compare_digest``. A forged model, a field
  rewritten with ``object.__setattr__`` (also to an unencodable value) or a model
  from another process never verifies.
* :func:`register_consumption` -- process-local, lock-protected one-shot registry.
* Source ownership claims (contract section 15.6, S5-A2 / S5-A2-R1 / S5-A2-R2) -- a private, process-local,
  lock-protected registry keyed by a frozen source identity ``(device, inode)`` with the states ACTIVE(token),
  RESERVED(checkpoint_id) and POISONED. Every read-verify-transition happens in ONE critical section of one
  lock; every ownership change of ACTIVE requires the exact current token, and a RESERVED hand-over the exact
  current checkpoint id (wrong / stale / duplicate credentials are no-ops that return ``False``). Tokens and
  states never leave this module's registry and the executing call; nothing is exported or persisted.

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
    SEALED_VALUE_TYPES,
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
# Every value type the encoder frames as a dataclass, field by field: the execution models plus the
# closed set of caller-held plan / manifest value types (``models.SEALED_VALUE_TYPES``).
_STRUCTURED = _NESTED_MODELS + _SEALED_MODELS + SEALED_VALUE_TYPES
# The only field a seal does not cover is the seal itself (contract section 15.3): the preflight's
# ``plan`` and ``artifacts`` are encoded with their *current* content, not only via fingerprints.
_UNSEALED_FIELDS = frozenset({"seal"})

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
    if kind in _STRUCTURED:
        return _frame(b"M", kind.__qualname__.encode("ascii")) + encode(_model_values(value))
    raise ExecutionModelError("value cannot be canonically encoded")


def _model_values(model: object) -> tuple[object, ...]:
    # Exact-type dataclasses only (checked by the caller): field order is the declaration order.
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
    expected = _seal_or_none(model)
    if expected is None:
        return False  # a field was rewritten to a value outside the closed encodable set
    return hmac.compare_digest(expected, claimed)


def _seal_or_none(model: object) -> str | None:
    try:
        return seal_of(model)
    except ExecutionModelError:
        return None


def sealed(model_type: type, **fields: object) -> object:
    """Construct ``model_type(**fields, seal=<its seal>)`` (checkpoint / preflight only)."""
    if model_type not in _SEALED_MODELS:
        raise ExecutionModelError("only checkpoints and preflights are sealed")
    draft = model_type(**fields, seal=_ZERO_SEAL)
    return model_type(**fields, seal=seal_of(draft))


def issue_checkpoint(*, plan_fingerprint: str, manifest_fingerprint: str, library_root_identity: EntryIdentity,
                     source_identity: EntryIdentity, transfer_mode: object,
                     target_directory_identity: EntryIdentity,
                     extrafanart_directory_identity: EntryIdentity | None,
                     completed_effects: tuple[CompletedEffect, ...],
                     leftover_temporaries: tuple[LeftoverTemporary, ...]) -> ExecutionCheckpoint:
    """Issue a new sealed, immutable in-process checkpoint (contract sections 14.2, 14.5).

    Private construction helper (not public API): a fresh ``checkpoint_id`` from ``secrets.token_hex(16)``
    and the full-field seal. Only the S5 executor issues checkpoints in production; S2 tests use it to build
    real partial states.
    """
    return sealed(
        ExecutionCheckpoint,
        checkpoint_id=secrets.token_hex(16),
        plan_fingerprint=plan_fingerprint,
        manifest_fingerprint=manifest_fingerprint,
        library_root_identity=library_root_identity,
        source_identity=source_identity,
        transfer_mode=transfer_mode,
        target_directory_identity=target_directory_identity,
        extrafanart_directory_identity=extrafanart_directory_identity,
        completed_effects=completed_effects,
        leftover_temporaries=leftover_temporaries,
    )


def content_sha256(content: bytes) -> str:
    """SHA-256 hex digest of exact bytes (RESUME re-hash of published artifacts, contract section 14.3).

    Lives here because ``seal.py`` is the only module whose frozen import allow-list includes ``hashlib``.
    """
    if type(content) is not bytes:
        raise ExecutionModelError("content must be exact bytes")
    return hashlib.sha256(content).hexdigest()


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


# --------------------------------------------------------------------------- source ownership claims (15.6)

_CLAIM_ACTIVE = "active"
_CLAIM_RESERVED = "reserved"
_CLAIM_POISONED = "poisoned"
# (device, inode) -> (state, credential): credential is the ACTIVE token or the RESERVED checkpoint id.
_CLAIMS: dict[tuple[int, int], tuple[str, str | None]] = {}
_CLAIMS_LOCK = threading.Lock()


class ClaimIntegrityError(Exception):
    """Private: an ownership transition the executing call owed did not take effect (contract section 15.6,
    owner authorization item 5). Fixed wording only -- never a token, key, path or seal."""

    def __init__(self) -> None:
        super().__init__("source ownership claim transition did not take effect; execution stopped (fail closed)")


def _claim_key(identity: EntryIdentity) -> tuple[int, int]:
    if type(identity) is not EntryIdentity:
        raise ExecutionModelError("a source ownership claim is keyed by an EntryIdentity")
    return identity.device, identity.inode


def claim_acquire(identity: EntryIdentity) -> str | None:
    """No entry -> ACTIVE(fresh token); returns the token, or ``None`` (conflict: any existing state)."""
    key = _claim_key(identity)
    with _CLAIMS_LOCK:
        if key in _CLAIMS:
            return None
        token = secrets.token_hex(16)
        _CLAIMS[key] = (_CLAIM_ACTIVE, token)
        return token


def claim_take_over(identity: EntryIdentity, checkpoint_id: str) -> str | None:
    """RESERVED(checkpoint_id) -> ACTIVE(fresh token) for the lineage whose input checkpoint is the current
    reservation owner; ``None`` for any other state or owner."""
    key = _claim_key(identity)
    with _CLAIMS_LOCK:
        if _CLAIMS.get(key) != (_CLAIM_RESERVED, checkpoint_id):
            return None
        token = secrets.token_hex(16)
        _CLAIMS[key] = (_CLAIM_ACTIVE, token)
        return token


def claim_release(identity: EntryIdentity, token: str) -> bool:
    """ACTIVE(token) -> no entry; any other state or token is a no-op (``False``)."""
    key = _claim_key(identity)
    with _CLAIMS_LOCK:
        if _CLAIMS.get(key) != (_CLAIM_ACTIVE, token):
            return False
        del _CLAIMS[key]
        return True


def claim_reserve(identity: EntryIdentity, token: str, checkpoint_id: str) -> bool:
    """ACTIVE(token) -> RESERVED(checkpoint_id); any other state or token is a no-op (``False``)."""
    key = _claim_key(identity)
    with _CLAIMS_LOCK:
        if _CLAIMS.get(key) != (_CLAIM_ACTIVE, token):
            return False
        _CLAIMS[key] = (_CLAIM_RESERVED, checkpoint_id)
        return True


def claim_hand_over(identity: EntryIdentity, old_checkpoint_id: str, new_checkpoint_id: str) -> str:
    """RESERVED(old) -> RESERVED(new). Returns ``"handed_over"``, ``"poisoned"`` (the lineage no longer owns
    the key: nothing to hand over) or ``"mismatch"`` (any other state: registry unchanged)."""
    key = _claim_key(identity)
    with _CLAIMS_LOCK:
        current = _CLAIMS.get(key)
        if current == (_CLAIM_RESERVED, old_checkpoint_id):
            _CLAIMS[key] = (_CLAIM_RESERVED, new_checkpoint_id)
            return "handed_over"
        if current is not None and current[0] == _CLAIM_POISONED:
            return "poisoned"
        return "mismatch"


def claim_poison_active(identity: EntryIdentity, token: str) -> bool:
    """ACTIVE(token) -> POISONED; any other state or token is a no-op (``False``)."""
    key = _claim_key(identity)
    with _CLAIMS_LOCK:
        if _CLAIMS.get(key) != (_CLAIM_ACTIVE, token):
            return False
        _CLAIMS[key] = (_CLAIM_POISONED, None)
        return True


def claim_poison_reserved(identity: EntryIdentity, checkpoint_id: str) -> bool:
    """RESERVED(checkpoint_id) -> POISONED; any other state or owner is a no-op (``False``)."""
    key = _claim_key(identity)
    with _CLAIMS_LOCK:
        if _CLAIMS.get(key) != (_CLAIM_RESERVED, checkpoint_id):
            return False
        _CLAIMS[key] = (_CLAIM_POISONED, None)
        return True


def _claim_state_for_tests(identity: EntryIdentity) -> tuple[str, str | None] | None:
    """TESTS ONLY: the private state of one key (never used by production code)."""
    with _CLAIMS_LOCK:
        return _CLAIMS.get(_claim_key(identity))


def _claim_keys_for_tests() -> frozenset[tuple[int, int]]:
    """TESTS ONLY: the keys currently present (to discard exactly what one test created)."""
    with _CLAIMS_LOCK:
        return frozenset(_CLAIMS)


def _claim_discard_for_tests(keys: frozenset[tuple[int, int]]) -> None:
    """TESTS ONLY: forget exactly these keys (test isolation; production never clears the registry)."""
    with _CLAIMS_LOCK:
        for key in keys:
            _CLAIMS.pop(key, None)
