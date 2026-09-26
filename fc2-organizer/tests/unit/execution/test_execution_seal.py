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
    ExecutionPreflight,
    ExecutionStep,
    ExecutionUnit,
    LeftoverTemporary,
    PathRole,
    PreflightBlocker,
    PreflightBlockReason,
    PreflightMode,
    TransferMode,
    preflight_execution,
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

from ._builders import make_manifest, make_plan, request, scene, tampered

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


class _SubPath(PlannedPath):
    pass


def test_encoding_refuses_unknown_types():
    for value in (1.5, ["a"], {"a": 1}, object(), bytearray(b"x"), _SubPath("/x")):
        with pytest.raises(ExecutionModelError):
            encode(value)


def test_plan_and_request_value_types_are_encoded_structurally():
    # Closed SEALED_VALUE_TYPES set (P4-C7-S1-R-01): exact types only, field by field.
    assert encode(PlannedPath("/a")) != encode(PlannedPath("/b"))
    assert encode(PlannedPath("/a")) != encode("/a") and encode(PlannedPath("/a")) != encode(("/a",))
    assert encode(request(ArtifactKind.NFO, "/a", b"x")) != encode(request(ArtifactKind.NFO, "/a", b"y"))


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


# --------------------------------------------------------------------------- P4-C7-S1-R-01: preflight seal coverage


def _ready_preflight(tmp_path):
    s = scene(tmp_path, extra=2)
    preflight = preflight_execution(s.plan, s.artifacts)
    assert preflight.ready and verify_seal(preflight)
    return s, preflight


def _other_valid_plan(s):
    # A different, fully valid OrganizePlan (same source, another canonical number).
    other = make_plan(s.library_root, s.source_path, number="FC2-7654321", extension=".mp4", size=len(s.content))
    assert other != s.plan
    return other


def test_r01_legitimate_preflight_seal_verifies(tmp_path):
    _, preflight = _ready_preflight(tmp_path)
    assert verify_seal(preflight)
    assert seal_of(preflight) == preflight.seal


def test_r01_plan_swap_without_touching_plan_fingerprint_breaks_the_seal(tmp_path):
    s, preflight = _ready_preflight(tmp_path)
    forged = tampered(preflight, plan=_other_valid_plan(s))
    assert forged.plan_fingerprint == preflight.plan_fingerprint and forged.seal == preflight.seal
    assert not verify_seal(forged)
    # Second, independent layer (contract section 15.5): the stored fingerprint no longer matches either.
    assert plan_fingerprint(forged.plan) != forged.plan_fingerprint


def test_r01_artifacts_swap_without_touching_manifest_fingerprint_breaks_the_seal(tmp_path):
    s, preflight = _ready_preflight(tmp_path)
    for other in (make_manifest(s.plan, extra=3), make_manifest(s.plan, poster=False, extra=2),
                  make_manifest(s.plan, extra=2, nfo_text="<movie>other</movie>")):
        forged = tampered(preflight, artifacts=other)
        assert forged.manifest_fingerprint == preflight.manifest_fingerprint and forged.seal == preflight.seal
        assert not verify_seal(forged)
        assert manifest_fingerprint(forged.artifacts) != forged.manifest_fingerprint


def test_r01_nested_plan_and_request_content_tamper_breaks_the_seal(tmp_path):
    s, preflight = _ready_preflight(tmp_path)
    nested_path = tampered(s.plan, poster_path=PlannedPath(s.plan.fanart_path.absolute_path))
    assert not verify_seal(tampered(preflight, plan=nested_path))
    first = s.artifacts[0]
    flipped = tampered(first, content=bytes([first.content[0] ^ 1]) + first.content[1:])
    assert not verify_seal(tampered(preflight, artifacts=(flipped,) + s.artifacts[1:]))
    assert not verify_seal(tampered(preflight, artifacts=s.artifacts[:-1]))


def test_r01_tamper_to_an_unencodable_value_fails_closed_without_raising(tmp_path):
    s, preflight = _ready_preflight(tmp_path)
    assert not verify_seal(tampered(preflight, plan=tampered(s.plan, operations=list(s.plan.operations))))
    assert not verify_seal(tampered(preflight, artifacts=list(s.artifacts)))
    assert not verify_seal(tampered(preflight, plan="plan"))


def test_r01_every_preflight_field_except_seal_is_covered(tmp_path):
    s, preflight = _ready_preflight(tmp_path)
    checkpoint = sealed(ExecutionCheckpoint, **_checkpoint_fields())
    other_dir = EntryIdentity(9, 9, EntryType.DIRECTORY, None, None)
    other_file = EntryIdentity(9, 8, EntryType.FILE, 1, 2)
    unit = ExecutionUnit(ExecutionStep.CREATE_DIRECTORY, PathRole.TARGET_DIRECTORY, None, None)
    replacements = {  # same-type, individually valid values
        "preflight_id": secrets.token_hex(16),
        "mode": PreflightMode.RESUME,
        "plan": _other_valid_plan(s),
        "artifacts": make_manifest(s.plan, extra=5),
        "checkpoint": checkpoint,
        "plan_fingerprint": "c" * 64,
        "manifest_fingerprint": "d" * 64,
        "ready": False,
        "blockers": (PreflightBlocker(PreflightBlockReason.SOURCE_MISSING, PathRole.SOURCE),),
        "library_root_identity": other_dir,
        "source_identity": other_file,
        "transfer_mode": TransferMode.CROSS_VOLUME,
        "completed_units": (unit,),
        "pending_units": preflight.pending_units[:-1],
        "skipped_steps": (ExecutionStep.MATERIALIZE_THUMB,),
    }
    assert set(replacements) == {f.name for f in dataclasses.fields(ExecutionPreflight)} - {"seal"}
    for name, value in replacements.items():
        assert getattr(preflight, name) != value, name
        assert not verify_seal(tampered(preflight, **{name: value})), name
    assert verify_seal(preflight)  # the original is untouched


def test_r01_every_checkpoint_field_except_seal_is_still_covered():
    cp = sealed(ExecutionCheckpoint, **_checkpoint_fields())
    other_dir = EntryIdentity(9, 9, EntryType.DIRECTORY, None, None)
    extra_effect = CompletedEffect(EffectKind.EXTRAFANART_DIRECTORY_CREATED, PathRole.EXTRAFANART_DIRECTORY,
                                   "/lib/FC2-1/extrafanart", other_dir, None, None, None, None)
    replacements = {
        "checkpoint_id": secrets.token_hex(16), "plan_fingerprint": "c" * 64, "manifest_fingerprint": "d" * 64,
        "library_root_identity": other_dir, "source_identity": EntryIdentity(9, 8, EntryType.FILE, 1, 2),
        "transfer_mode": TransferMode.CROSS_VOLUME, "target_directory_identity": other_dir,
        "extrafanart_directory_identity": other_dir,
        "completed_effects": cp.completed_effects + (extra_effect,),
        "leftover_temporaries": (LeftoverTemporary(PathRole.TARGET_DIRECTORY, ".fc2tmp-" + "0" * 32 + ".part"),),
    }
    assert set(replacements) == {f.name for f in dataclasses.fields(ExecutionCheckpoint)} - {"seal"}
    for name, value in replacements.items():
        assert not verify_seal(tampered(cp, **{name: value})), name
    assert verify_seal(cp)


def test_r01_seal_of_and_verify_seal_do_not_modify_their_input(tmp_path):
    s, preflight = _ready_preflight(tmp_path)
    before = {f.name: getattr(preflight, f.name) for f in dataclasses.fields(ExecutionPreflight)}
    plan_before = {f.name: getattr(s.plan, f.name) for f in dataclasses.fields(s.plan)}
    contents = [item.content for item in s.artifacts]
    for _ in range(3):
        seal_of(preflight)
        verify_seal(preflight)
        verify_seal(tampered(preflight, plan="plan"))
    for name, value in before.items():
        assert getattr(preflight, name) is value, name
    for name, value in plan_before.items():
        assert getattr(s.plan, name) is value, name
    assert all(item.content is content for item, content in zip(s.artifacts, contents))
    assert verify_seal(preflight)


def test_r01_fingerprint_layer_is_unchanged_and_independent(tmp_path):
    s, preflight = _ready_preflight(tmp_path)
    assert preflight.plan_fingerprint == plan_fingerprint(s.plan)
    assert preflight.manifest_fingerprint == manifest_fingerprint(s.artifacts)
    # A seal-valid preflight carrying a wrong stored fingerprint is still caught by the fingerprint layer;
    # a fingerprint-consistent preflight carrying a wrong seal is still caught by the seal layer.
    fields = {f.name: getattr(preflight, f.name) for f in dataclasses.fields(ExecutionPreflight)
              if f.name != "seal"}
    fields["plan_fingerprint"] = "e" * 64
    resealed = sealed(ExecutionPreflight, **fields)
    assert verify_seal(resealed) and plan_fingerprint(resealed.plan) != resealed.plan_fingerprint
    assert not verify_seal(tampered(preflight, seal="0" * 64))
