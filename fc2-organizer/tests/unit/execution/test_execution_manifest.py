"""P4-C7 S1: artifact manifest hardening (contract section 7; construction plan S1).

Covers the contract section 31 "manifest forgery" list, the 8 optional main-image combinations x
extrafanart {0, 1, 13}, the 1000-extrafanart manifest and the extrafanart formatter equivalence with
P4-C6's ``mapping.extrafanart_filename`` for 1..10000.
"""

from __future__ import annotations

import os

import pytest

from fc2_organizer.execution import ArtifactManifestError, ExecutionInputError
from fc2_organizer.execution import ManifestRejectionReason as M
from fc2_organizer.execution.models import EffectKind, ExecutionStep, PathRole
from fc2_organizer.execution.validation import (
    _EXTRAFANART_FORMAT,
    expected_effects,
    expected_units,
    extrafanart_target,
    skipped_steps,
    validate_manifest,
)
from fc2_organizer.materialization import ArtifactKind, ArtifactWriteRequest
from fc2_organizer.materialization.mapping import extrafanart_filename
from fc2_organizer.planning import PlannedPath

from ._builders import MAIN_COMBOS, make_manifest, make_plan, request, tampered

A = ArtifactKind


@pytest.fixture
def plan(tmp_path):
    return make_plan(str(tmp_path / "library"))


def _reject(plan, artifacts, reason):
    with pytest.raises(ArtifactManifestError) as info:
        validate_manifest(plan, artifacts)
    assert info.value.reason is reason, info.value.reason
    assert info.value.__cause__ is None and info.value.__context__ is None


def _nfo(plan, content=b"<movie/>"):
    return request(A.NFO, plan.nfo_path.absolute_path, content)


def _extra(plan, ordinal, name_ordinal=None):
    return request(A.EXTRAFANART, extrafanart_target(plan, name_ordinal or ordinal), b"x", ordinal)


# --------------------------------------------------------------------------- accepted shapes


@pytest.mark.parametrize("combo", MAIN_COMBOS)
@pytest.mark.parametrize("extra", [0, 1, 13])
def test_all_optional_image_combinations_are_accepted(plan, combo, extra):
    poster, fanart, thumb = combo
    manifest = make_manifest(plan, poster, fanart, thumb, extra)
    validate_manifest(plan, manifest)
    units = expected_units(plan, manifest)
    steps = [u.step for u in units]
    assert steps[:3] == [ExecutionStep.CREATE_DIRECTORY, ExecutionStep.MOVE_MEDIA, ExecutionStep.MATERIALIZE_NFO]
    assert ExecutionStep.ENSURE_EXTRAFANART_DIRECTORY in steps  # always, even with zero extrafanart
    assert steps.count(ExecutionStep.MATERIALIZE_EXTRAFANART) == extra
    expected_skipped = [step for present, step in zip(combo, (
        ExecutionStep.MATERIALIZE_POSTER, ExecutionStep.MATERIALIZE_FANART, ExecutionStep.MATERIALIZE_THUMB))
        if not present]
    assert list(skipped_steps(manifest)) == expected_skipped
    assert not set(expected_skipped) & set(steps)
    effects = expected_effects(plan, manifest)
    assert [e.kind for e in effects[:3]] == [EffectKind.TARGET_DIRECTORY_CREATED, EffectKind.MEDIA_PUBLISHED,
                                             EffectKind.SOURCE_REMOVED]
    assert len(effects) == len(units) + 1  # MOVE_MEDIA yields MEDIA_PUBLISHED and SOURCE_REMOVED
    assert effects[2].role is PathRole.SOURCE and effects[2].path == plan.source_path


def test_1000_extrafanart_manifest_is_accepted_in_memory(plan):
    manifest = make_manifest(plan, extra=1000)
    validate_manifest(plan, manifest)
    assert len(manifest) == 1004
    assert manifest[-1].target_path.endswith(os.sep + "extrafanart-1000.jpg")
    units = expected_units(plan, manifest)
    assert units[-1].ordinal == 1000 and len(units) == 3 + 3 + 1 + 1000


def test_private_extrafanart_format_matches_p4c6_formatter_for_1_to_10000():
    for ordinal in range(1, 10001):
        assert _EXTRAFANART_FORMAT.format(ordinal) == extrafanart_filename(ordinal)


# --------------------------------------------------------------------------- container / request types


def test_non_tuple_manifests_are_input_errors(plan):
    manifest = make_manifest(plan)
    with pytest.raises(ExecutionInputError):
        validate_manifest(plan, list(manifest))

    class Manifest(tuple):
        pass

    with pytest.raises(ExecutionInputError):
        validate_manifest(plan, Manifest(manifest))


class _Calls:
    names: list[str] = []


class HookRequest(ArtifactWriteRequest):
    def __getattribute__(self, name):
        _Calls.names.append(name)
        return object.__getattribute__(self, name)


def test_request_subclass_is_rejected_without_hooks(plan):
    hostile = HookRequest(A.NFO, plan.nfo_path.absolute_path, b"x")
    _Calls.names.clear()
    _reject(plan, (hostile,), M.REQUEST_TYPE)
    assert _Calls.names == []
    _reject(plan, (_nfo(plan), "poster"), M.REQUEST_TYPE)


class _Bytes(bytes):
    pass


@pytest.mark.parametrize("changes", [
    dict(content=bytearray(b"x")), dict(content=_Bytes(b"x")), dict(ordinal=1), dict(kind="nfo"),
    dict(target_path=PlannedPath("/x")), dict(target_path=""), dict(ordinal=True),
])
def test_tampered_requests_are_rejected(plan, changes):
    _reject(plan, (tampered(_nfo(plan), **changes),), M.REQUEST_INVALID)


def test_tampered_extrafanart_ordinal_zero_is_rejected(plan):
    forged = tampered(_extra(plan, 1), ordinal=0)
    _reject(plan, (_nfo(plan), forged), M.REQUEST_INVALID)


def test_empty_content_is_rejected(plan):
    _reject(plan, (_nfo(plan, b""),), M.EMPTY_CONTENT)
    _reject(plan, (_nfo(plan), request(A.POSTER, plan.poster_path.absolute_path, b"")), M.EMPTY_CONTENT)


# --------------------------------------------------------------------------- counts / order


def test_nfo_presence_and_position(plan):
    poster = request(A.POSTER, plan.poster_path.absolute_path)
    _reject(plan, (), M.NFO_MISSING)
    _reject(plan, (poster,), M.NFO_MISSING)
    _reject(plan, (poster, _nfo(plan)), M.NFO_NOT_FIRST)
    _reject(plan, (_nfo(plan), _nfo(plan)), M.DUPLICATE_KIND)


def test_duplicate_single_kinds(plan):
    for kind, field_name in ((A.POSTER, "poster_path"), (A.FANART, "fanart_path"), (A.THUMB, "thumb_path")):
        item = request(kind, getattr(plan, field_name).absolute_path)
        _reject(plan, (_nfo(plan), item, item), M.DUPLICATE_KIND)


def test_order_violations(plan):
    poster = request(A.POSTER, plan.poster_path.absolute_path)
    fanart = request(A.FANART, plan.fanart_path.absolute_path)
    thumb = request(A.THUMB, plan.thumb_path.absolute_path)
    _reject(plan, (_nfo(plan), fanart, poster), M.ORDER)
    _reject(plan, (_nfo(plan), thumb, fanart), M.ORDER)
    _reject(plan, (_nfo(plan), _extra(plan, 1), poster), M.ORDER)


# --------------------------------------------------------------------------- targets / ordinals


def test_target_mismatches(plan):
    _reject(plan, (request(A.NFO, plan.poster_path.absolute_path),), M.TARGET_MISMATCH)
    _reject(plan, (_nfo(plan), request(A.POSTER, plan.fanart_path.absolute_path)), M.TARGET_MISMATCH)
    other = os.path.join(plan.target_directory.absolute_path, "folder.jpg")
    _reject(plan, (_nfo(plan), request(A.THUMB, other)), M.TARGET_MISMATCH)


@pytest.mark.parametrize("ordinals", [(2,), (1, 3), (1, 1), (2, 1), (1, 2, 4)])
def test_extrafanart_ordinal_sequence(plan, ordinals):
    items = tuple(request(A.EXTRAFANART, extrafanart_target(plan, o), b"x", o) for o in ordinals)
    _reject(plan, (_nfo(plan),) + items, M.EXTRAFANART_ORDINAL_SEQUENCE)


def test_extrafanart_name_mismatch(plan):
    directory = plan.extrafanart_directory.absolute_path
    wrong_width = request(A.EXTRAFANART, os.path.join(directory, "extrafanart-01.jpg"), b"x", 1)
    _reject(plan, (_nfo(plan), wrong_width), M.EXTRAFANART_NAME_MISMATCH)
    wrong_number = request(A.EXTRAFANART, extrafanart_target(plan, 2), b"x", 1)
    _reject(plan, (_nfo(plan), wrong_number), M.EXTRAFANART_NAME_MISMATCH)
    outside = request(A.EXTRAFANART, os.path.join(plan.target_directory.absolute_path, "extrafanart-001.jpg"),
                      b"x", 1)
    _reject(plan, (_nfo(plan), outside), M.EXTRAFANART_NAME_MISMATCH)


def test_duplicate_targets_on_forged_plans(plan):
    # Unreachable with a validated plan; validate_manifest still refuses it on its own.
    same = tampered(plan, poster_path=plan.nfo_path)
    _reject(same, (_nfo(same), request(A.POSTER, same.poster_path.absolute_path)), M.DUPLICATE_TARGET)
    onto_media = tampered(plan, thumb_path=plan.target_media_path)
    _reject(onto_media, (_nfo(onto_media), request(A.THUMB, onto_media.thumb_path.absolute_path)),
            M.DUPLICATE_TARGET)
    onto_dir = tampered(plan, fanart_path=plan.extrafanart_directory)
    _reject(onto_dir, (_nfo(onto_dir), request(A.FANART, onto_dir.fanart_path.absolute_path)), M.DUPLICATE_TARGET)


def test_case_folded_duplicate_targets(plan):
    upper = PlannedPath(plan.nfo_path.absolute_path.upper())
    forged = tampered(plan, poster_path=upper)
    manifest = (_nfo(forged), request(A.POSTER, forged.poster_path.absolute_path))
    if os.name == "nt":
        _reject(forged, manifest, M.DUPLICATE_TARGET)
    else:
        validate_manifest(forged, manifest)  # distinct names on a case-sensitive POSIX filesystem
