"""P4-C7 S1: canonical encoding, fingerprints, process seals and consumption (contract section 15)."""

from __future__ import annotations

import ast
import dataclasses
import secrets
import threading
from pathlib import Path

import pytest

from fc2_organizer.execution import (
    CompletedEffect,
    EffectKind,
    EntryIdentity,
    EntryType,
    ExecutionCheckpoint,
    ExecutionModelError,
    PathRole,
    TransferMode,
)
from fc2_organizer.execution import seal as seal_module
from fc2_organizer.execution.seal import (
    encode,
    is_consumed,
    manifest_fingerprint,
    plan_fingerprint,
    register_consumption,
    seal_of,
    sealed,
    verify_seal,
)
from fc2_organizer.materialization import ArtifactKind
from fc2_organizer.planning import PlannedPath

from ._builders import make_manifest, make_plan, request, tampered

SEAL_SRC = Path(__file__).resolve().parents[3] / "src" / "fc2_organizer" / "execution" / "seal.py"
DIR = EntryIdentity(1, 2, EntryType.DIRECTORY, None, None)
FILE = EntryIdentity(1, 3, EntryType.FILE, 10, 1_000)


def _checkpoint_fields(**overrides):
    fields = dict(
        checkpoint_id=secrets.token_hex(16), plan_fingerprint="a" * 64, manifest_fingerprint="b" * 64,
        library_root_identity=DIR, source_identity=FILE, transfer_mode=TransferMode.SAME_VOLUME,
        target_directory_identity=DIR, extrafanart_directory_identity=None,
        completed_effects=(CompletedEffect(EffectKind.TARGET_DIRECTORY_CREATED, PathRole.TARGET_DIRECTORY,
                                           "/lib/FC2-1", DIR, None, None, None, None),),
        leftover_temporaries=(),
    )
    fields.update(overrides)
    return fields


# --------------------------------------------------------------------------- encoding


def test_encoding_is_injective_on_prefix_and_type_ambiguities():
    samples = [
        ("ab", "c"), ("a", "bc"), ("abc",), "abc", b"abc", 1, "1", True, 0, False, None, "", b"", (), ((),),
        (None,), ("",), (1, 2), ((1, 2),), (1, (2,)), ArtifactKind.NFO, "nfo", EffectKind.SOURCE_REMOVED,
        -5, "-5", ("a\x00", "b"), ("a", "\x00b"),
    ]
    encodings = [encode(value) for value in samples]
    assert len(set(encodings)) == len(encodings)


def test_encoding_is_deterministic_and_handles_lone_surrogates():
    assert encode(("\udcff", 7)) == encode(("\udcff", 7))
    assert encode("\udcff") != encode("\udcfe")


def test_encoding_refuses_unknown_types():
    for value in (1.5, ["a"], {"a": 1}, object(), bytearray(b"x"), PlannedPath("/x")):
        with pytest.raises(ExecutionModelError):
            encode(value)


# --------------------------------------------------------------------------- fingerprints


def test_plan_fingerprint_is_deterministic_and_sensitive_to_every_field(tmp_path):
    plan = make_plan(str(tmp_path / "lib"))
    base = plan_fingerprint(plan)
    assert base == plan_fingerprint(make_plan(str(tmp_path / "lib")))
    changes = {
        "source_path": plan.source_path + "x", "source_relative_path": "other", "source_extension": ".mkv",
        "source_index": 1, "source_size": 124, "canonical_number": "FC2-1234568", "library_root": "/elsewhere",
        "target_directory": PlannedPath("/a/b"), "target_media_path": PlannedPath("/a/c"),
        "nfo_path": PlannedPath("/a/d"), "poster_path": PlannedPath("/a/e"), "fanart_path": PlannedPath("/a/f"),
        "thumb_path": PlannedPath("/a/g"), "extrafanart_directory": PlannedPath("/a/h"),
        "operations": plan.operations[:-1],
    }
    assert set(changes) == {f.name for f in dataclasses.fields(plan)}
    seen = {base}
    for name, value in changes.items():
        fingerprint = plan_fingerprint(tampered(plan, **{name: value}))
        assert fingerprint not in seen, name
        seen.add(fingerprint)


def test_manifest_fingerprint_is_sensitive_to_one_byte_and_every_field(tmp_path):
    plan = make_plan(str(tmp_path / "lib"))
    manifest = make_manifest(plan, extra=2)
    base = manifest_fingerprint(manifest)
    assert base == manifest_fingerprint(make_manifest(plan, extra=2))
    first = manifest[0]
    flipped = bytes([first.content[0] ^ 1]) + first.content[1:]
    variants = [
        (request(first.kind, first.target_path, flipped),) + manifest[1:],
        (request(first.kind, first.target_path, first.content + b" "),) + manifest[1:],
        (tampered(first, target_path=first.target_path + "x"),) + manifest[1:],
        (tampered(first, kind=ArtifactKind.POSTER),) + manifest[1:],
        manifest[:-1] + (tampered(manifest[-1], ordinal=9),),
        manifest[:-1],
        (manifest[0], manifest[2], manifest[1]) + manifest[3:],
    ]
    fingerprints = {manifest_fingerprint(v) for v in variants}
    assert base not in fingerprints and len(fingerprints) == len(variants)


# --------------------------------------------------------------------------- seals


def test_sealed_checkpoint_verifies_and_detects_tampering():
    cp = sealed(ExecutionCheckpoint, **_checkpoint_fields())
    assert verify_seal(cp)
    for name, value in [("checkpoint_id", secrets.token_hex(16)), ("plan_fingerprint", "c" * 64),
                        ("transfer_mode", TransferMode.CROSS_VOLUME),
                        ("completed_effects", cp.completed_effects * 2), ("seal", "0" * 64)]:
        assert not verify_seal(tampered(cp, **{name: value})), name
    assert verify_seal(tampered(cp, leftover_temporaries=()))  # an equal value keeps the seal valid


def test_hand_built_checkpoint_with_arbitrary_seal_never_verifies():
    assert not verify_seal(ExecutionCheckpoint(**_checkpoint_fields(), seal="e" * 64))


def test_non_str_seal_and_foreign_objects_never_verify():
    cp = sealed(ExecutionCheckpoint, **_checkpoint_fields())
    assert not verify_seal(tampered(cp, seal=b"x"))
    assert not verify_seal("checkpoint")
    with pytest.raises(ExecutionModelError):
        seal_of(DIR)
    with pytest.raises(ExecutionModelError):
        sealed(EntryIdentity, device=1)


def test_a_different_process_key_invalidates_every_seal(monkeypatch):
    cp = sealed(ExecutionCheckpoint, **_checkpoint_fields())
    monkeypatch.setattr(seal_module, "_PROCESS_KEY", secrets.token_bytes(32))
    assert not verify_seal(cp)  # e.g. a checkpoint carried over from another process


def test_seal_verification_uses_compare_digest_and_key_is_never_exposed():
    tree = ast.parse(SEAL_SRC.read_text(encoding="utf-8"))
    calls = {node.func.attr for node in ast.walk(tree)
             if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)}
    assert "compare_digest" in calls
    assert "_PROCESS_KEY" not in seal_module.__all__
    cp = sealed(ExecutionCheckpoint, **_checkpoint_fields())
    assert seal_module._PROCESS_KEY.hex() not in repr(cp) and cp.seal not in repr(cp)


# --------------------------------------------------------------------------- consumption


def test_register_consumption_is_one_shot_and_atomic():
    a, b = secrets.token_hex(16), secrets.token_hex(16)
    assert not is_consumed(a)
    assert register_consumption((a,))
    assert is_consumed(a)
    assert not register_consumption((a,))
    assert not register_consumption((b, a))  # all-or-nothing: b must not have been registered
    assert not is_consumed(b)
    assert register_consumption((b,))


def test_16_threads_racing_for_one_id_have_exactly_one_winner():
    for _ in range(20):
        target = secrets.token_hex(16)
        barrier = threading.Barrier(16)
        wins: list[bool] = []
        lock = threading.Lock()

        def worker():
            barrier.wait()
            won = register_consumption((target,))
            with lock:
                wins.append(won)

        threads = [threading.Thread(target=worker) for _ in range(16)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        assert wins.count(True) == 1 and len(wins) == 16
