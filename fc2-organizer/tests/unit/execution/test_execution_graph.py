"""P4-C7 S1: OrganizePlan execution-boundary hardening (contract section 6; construction plan S1).

Covers the contract section 31 "graph forgery" list: missing / extra / reordered operations, kind /
target / source replacement, subclass operations and paths, non-tuple operations, post-construction
``object.__setattr__`` tampering, layout violations, collisions, extended reserved names, source placement
and the bare ``\\\\server`` root.
"""

from __future__ import annotations

import dataclasses
import os

import pytest

from fc2_organizer.execution import ExecutionInputError, PlanGraphError
from fc2_organizer.execution import PlanGraphRejectionReason as G
from fc2_organizer.execution.models import ExecutionStep
from fc2_organizer.execution.validation import expected_units, validate_manifest, validate_plan
from fc2_organizer.planning import (
    OrganizePlan,
    OrganizePlanError,
    OutputPolicy,
    PlannedOperation,
    PlannedOperationKind,
    PlannedPath,
)

from ._builders import NUMBER, make_manifest, make_plan, op, replace_op, tampered

K = PlannedOperationKind
_FIELD_OP_INDEX = {"target_directory": 0, "target_media_path": 1, "nfo_path": 2, "poster_path": 3,
                   "fanart_path": 4, "thumb_path": 5, "extrafanart_directory": 6}


@pytest.fixture
def root(tmp_path) -> str:
    return str(tmp_path / "library")


@pytest.fixture
def plan(root) -> OrganizePlan:
    return make_plan(root)


def _reject(plan, reason):
    with pytest.raises(PlanGraphError) as info:
        validate_plan(plan)
    assert info.value.reason is reason, info.value.reason
    assert info.value.__cause__ is None and info.value.__context__ is None


def retarget(plan, field_name, new_path):
    """Move one target field *and* its operation consistently (so only the layout rule can fail)."""
    changed = tampered(plan, **{field_name: PlannedPath(new_path)})
    index = _FIELD_OP_INDEX[field_name]
    old = plan.operations[index]
    source = None if old.source is None else old.source.absolute_path
    return replace_op(changed, index, op(old.kind, new_path, source))


def resource(plan, new_source):
    changed = tampered(plan, source_path=new_source)
    return replace_op(changed, 1, op(K.MOVE_MEDIA, plan.target_media_path.absolute_path, new_source))


# --------------------------------------------------------------------------- accepted real plans


def test_real_default_plan_is_accepted_and_units_derive_from_fields(plan):
    validate_plan(plan)
    units = expected_units(plan, make_manifest(plan, extra=2))
    assert [u.step for u in units] == [
        ExecutionStep.CREATE_DIRECTORY, ExecutionStep.MOVE_MEDIA, ExecutionStep.MATERIALIZE_NFO,
        ExecutionStep.MATERIALIZE_POSTER, ExecutionStep.MATERIALIZE_FANART, ExecutionStep.MATERIALIZE_THUMB,
        ExecutionStep.ENSURE_EXTRAFANART_DIRECTORY, ExecutionStep.MATERIALIZE_EXTRAFANART,
        ExecutionStep.MATERIALIZE_EXTRAFANART]
    assert [u.ordinal for u in units[-2:]] == [1, 2]


@pytest.mark.parametrize("policy", [
    OutputPolicy(), OutputPolicy(nfo_extension=".xml", poster_filename="folder.jpg", fanart_filename="bg.jpg",
                                 thumb_filename="landscape.jpg", extrafanart_dirname="extras"),
    OutputPolicy(poster_filename="ポスター.jpg"),
])
def test_real_custom_policy_plans_are_accepted(root, policy):
    plan = make_plan(root, policy=policy)
    validate_plan(plan)
    validate_manifest(plan, make_manifest(plan, extra=3))


_EXTENSIONS = [".mp4", ".MKV", ".Avi", ".mov", ".WMV", ".m4v", ".ts"]
_POLICIES = [OutputPolicy(), OutputPolicy(nfo_extension=".xml"), OutputPolicy(extrafanart_dirname="extras")]
_DIRS = ["dl", "ダウンロード", "下载 目录", "émoji😀", "a.b"]


def test_400_synthetic_real_plans_are_accepted_with_zero_false_positives(tmp_path):
    root = str(tmp_path / "lib")
    for i in range(400):
        number = f"FC2-{100000 + i * 7919}"
        extension = _EXTENSIONS[i % len(_EXTENSIONS)]
        source = os.path.join(str(tmp_path), _DIRS[i % len(_DIRS)], f"raw-{i}{extension}")
        plan = make_plan(root, source, number=number, extension=extension, size=i,
                         policy=_POLICIES[i % len(_POLICIES)])
        validate_plan(plan)
        manifest = make_manifest(plan, poster=bool(i & 1), fanart=bool(i & 2), thumb=bool(i & 4), extra=i % 5)
        validate_manifest(plan, manifest)
        assert len(expected_units(plan, manifest)) == 4 + bool(i & 1) + bool(i & 2) + bool(i & 4) + i % 5


# --------------------------------------------------------------------------- exact input type


class _Hooks:
    calls: list[str] = []


class HookPlan(OrganizePlan):
    def __getattribute__(self, name):
        _Hooks.calls.append(name)
        return object.__getattribute__(self, name)


def test_plan_subclass_is_rejected_without_running_any_hook(plan):
    fields = {f.name: getattr(plan, f.name) for f in dataclasses.fields(OrganizePlan)}
    hostile = HookPlan(**fields)
    _Hooks.calls.clear()
    with pytest.raises(ExecutionInputError):
        validate_plan(hostile)
    assert _Hooks.calls == []
    with pytest.raises(ExecutionInputError):
        validate_plan("not a plan")


# --------------------------------------------------------------------------- field types / tampering


class HookStr(str):
    calls: list[str] = []

    def __eq__(self, other):
        HookStr.calls.append("eq")
        return str.__eq__(self, other)

    def __hash__(self):
        HookStr.calls.append("hash")
        return str.__hash__(self)

    def __len__(self):
        HookStr.calls.append("len")
        return str.__len__(self)

    def lower(self):
        HookStr.calls.append("lower")
        return str.lower(self)


class _Int(int):
    pass


@pytest.mark.parametrize(("field_name", "make_value"), [
    ("source_path", lambda p: HookStr(p.source_path)),
    ("canonical_number", lambda p: HookStr(p.canonical_number)),
    ("library_root", lambda p: HookStr(p.library_root)),
    ("source_extension", lambda p: HookStr(p.source_extension)),
    ("source_relative_path", lambda p: ""),
    ("library_root", lambda p: None),
    ("source_size", lambda p: True),
    ("source_size", lambda p: -1),
    ("source_size", lambda p: _Int(5)),
    ("source_index", lambda p: 1.0),
])
def test_field_type_violations_are_rejected_without_hooks(plan, field_name, make_value):
    forged = tampered(plan, **{field_name: make_value(plan)})
    HookStr.calls.clear()
    _reject(forged, G.FIELD_TYPE)
    assert HookStr.calls == []


class HookPath(PlannedPath):
    def __getattribute__(self, name):
        _Hooks.calls.append(name)
        return object.__getattribute__(self, name)


def test_path_type_violations(plan):
    hostile = HookPath(plan.poster_path.absolute_path)
    _Hooks.calls.clear()
    _reject(tampered(plan, poster_path=hostile), G.PATH_TYPE)
    assert _Hooks.calls == []
    _reject(tampered(plan, nfo_path=tampered(plan.nfo_path, absolute_path=b"/x")), G.PATH_TYPE)
    _reject(tampered(plan, thumb_path=plan.thumb_path.absolute_path), G.PATH_TYPE)


def test_every_field_tampered_after_construction_is_rejected(plan, root):
    outside = PlannedPath(os.path.join(os.path.dirname(root), "elsewhere", "x"))
    bad_values = {
        "source_path": "relative.mp4", "source_relative_path": 7, "source_extension": ".mkv",
        "source_index": -1, "source_size": "5", "canonical_number": "FC2-7654321",
        "library_root": "lib", "target_directory": outside, "target_media_path": outside, "nfo_path": outside,
        "poster_path": outside, "fanart_path": outside, "thumb_path": outside, "extrafanart_directory": outside,
        "operations": (),
    }
    assert set(bad_values) == {f.name for f in dataclasses.fields(OrganizePlan)}
    for name, value in bad_values.items():
        with pytest.raises(PlanGraphError):
            validate_plan(tampered(plan, **{name: value}))


def test_reconstruction_reruns_p4c2_model_checks(plan, root):
    _reject(tampered(plan, library_root="relative-lib"), G.PLAN_RECONSTRUCTION_FAILED)
    escaped = retarget(plan, "poster_path", os.path.join(os.path.dirname(root), "poster.jpg"))
    _reject(escaped, G.PLAN_RECONSTRUCTION_FAILED)
    relative_path = tampered(plan, fanart_path=tampered(plan.fanart_path, absolute_path="fanart.jpg"))
    _reject(relative_path, G.PLAN_RECONSTRUCTION_FAILED)


# --------------------------------------------------------------------------- operation graph


def test_operations_container_violations(plan):
    _reject(tampered(plan, operations=list(plan.operations)), G.OPERATIONS_NOT_TUPLE)

    class Ops(tuple):
        pass

    _reject(tampered(plan, operations=Ops(plan.operations)), G.OPERATIONS_NOT_TUPLE)


def test_missing_and_extra_operations(plan):
    _reject(tampered(plan, operations=plan.operations[:-1]), G.OPERATION_COUNT)
    _reject(tampered(plan, operations=plan.operations + plan.operations[-1:]), G.OPERATION_COUNT)
    _reject(tampered(plan, operations=()), G.OPERATION_COUNT)


def test_reordered_and_replaced_kinds(plan):
    ops = list(plan.operations)
    ops[3], ops[4] = ops[4], ops[3]
    _reject(tampered(plan, operations=tuple(ops)), G.OPERATION_KIND_ORDER)
    _reject(replace_op(plan, 3, op(K.MATERIALIZE_FANART, plan.poster_path.absolute_path)), G.OPERATION_KIND_ORDER)
    _reject(replace_op(plan, 6, op(K.CREATE_DIRECTORY, plan.extrafanart_directory.absolute_path)),
            G.OPERATION_KIND_ORDER)


def test_wrong_targets(plan):
    _reject(replace_op(plan, 0, op(K.CREATE_DIRECTORY, plan.nfo_path.absolute_path)), G.OPERATION_TARGET_MISMATCH)
    _reject(replace_op(plan, 5, op(K.MATERIALIZE_THUMB, plan.poster_path.absolute_path)),
            G.OPERATION_TARGET_MISMATCH)
    _reject(replace_op(plan, 1, op(K.MOVE_MEDIA, plan.nfo_path.absolute_path, plan.source_path)),
            G.OPERATION_TARGET_MISMATCH)


def test_wrong_sources(plan, root):
    other = os.path.join(os.path.dirname(root), "other", "x.mp4")
    _reject(replace_op(plan, 1, op(K.MOVE_MEDIA, plan.target_media_path.absolute_path, other)),
            G.OPERATION_SOURCE_MISMATCH)
    _reject(replace_op(plan, 1, op(K.MOVE_MEDIA, plan.target_media_path.absolute_path)),
            G.OPERATION_SOURCE_MISMATCH)
    _reject(replace_op(plan, 2, op(K.MATERIALIZE_NFO, plan.nfo_path.absolute_path, plan.source_path)),
            G.OPERATION_SOURCE_MISMATCH)


class HookOp(PlannedOperation):
    def __getattribute__(self, name):
        _Hooks.calls.append(name)
        return object.__getattribute__(self, name)


def test_forged_operation_objects(plan):
    hostile = HookOp(kind=K.MATERIALIZE_NFO, target=plan.nfo_path)
    _Hooks.calls.clear()
    _reject(replace_op(plan, 2, hostile), G.OPERATION_TYPE)
    assert _Hooks.calls == []
    string_kind = op(K.MATERIALIZE_NFO, plan.nfo_path.absolute_path)
    object.__setattr__(string_kind, "kind", "materialize_nfo")
    _reject(replace_op(plan, 2, string_kind), G.OPERATION_TYPE)
    string_target = op(K.MATERIALIZE_NFO, plan.nfo_path.absolute_path)
    object.__setattr__(string_target, "target", plan.nfo_path.absolute_path)
    _reject(replace_op(plan, 2, string_target), G.OPERATION_TYPE)
    _reject(replace_op(plan, 2, "MATERIALIZE_NFO"), G.OPERATION_TYPE)


# --------------------------------------------------------------------------- layout


def test_target_directory_must_be_the_direct_canonical_child(plan, root):
    _reject(retarget(plan, "target_directory", os.path.join(root, "sub", NUMBER)), G.TARGET_DIRECTORY_LAYOUT)
    _reject(retarget(plan, "target_directory", os.path.join(root, "FC2-7654321")), G.TARGET_DIRECTORY_LAYOUT)


def test_media_name_must_be_number_plus_lowercased_source_extension(plan):
    td = plan.target_directory.absolute_path
    _reject(retarget(plan, "target_media_path", os.path.join(td, "other.mp4")), G.MEDIA_NAME_MISMATCH)
    _reject(retarget(plan, "target_media_path", os.path.join(td, NUMBER + ".mkv")), G.MEDIA_NAME_MISMATCH)
    _reject(retarget(plan, "target_media_path", os.path.join(td, NUMBER + ".MP4")), G.MEDIA_NAME_MISMATCH)


@pytest.mark.parametrize("name_parts", [("other.nfo",), (NUMBER + "x.nfo",), (NUMBER,), (NUMBER + ".",),
                                        ("sub", NUMBER + ".nfo")])
def test_nfo_name_rules(plan, name_parts):
    forged = retarget(plan, "nfo_path", os.path.join(plan.target_directory.absolute_path, *name_parts))
    with pytest.raises(PlanGraphError) as info:
        validate_plan(forged)
    assert info.value.reason in (G.NFO_NAME_INVALID, G.TARGET_PATH_REJECTED)


def test_artifacts_must_be_direct_children_of_the_target_directory(plan, root):
    td = plan.target_directory.absolute_path
    _reject(retarget(plan, "poster_path", os.path.join(root, "poster.jpg")), G.ARTIFACT_LAYOUT)
    _reject(retarget(plan, "fanart_path", os.path.join(td, "sub", "fanart.jpg")), G.ARTIFACT_LAYOUT)
    _reject(retarget(plan, "extrafanart_directory", os.path.join(root, "extrafanart")), G.ARTIFACT_LAYOUT)


def test_basename_collisions(plan):
    td = plan.target_directory.absolute_path
    _reject(retarget(plan, "fanart_path", plan.poster_path.absolute_path), G.BASENAME_COLLISION)
    _reject(retarget(plan, "nfo_path", os.path.join(td, NUMBER + ".mp4")), G.BASENAME_COLLISION)
    _reject(retarget(plan, "extrafanart_directory", os.path.join(td, "thumb.jpg")), G.BASENAME_COLLISION)


@pytest.mark.skipif(os.name != "nt", reason="case-insensitive collision is a Windows rule")
def test_case_insensitive_basename_collision_on_windows(plan):
    forged = retarget(plan, "fanart_path", os.path.join(plan.target_directory.absolute_path, "POSTER.JPG"))
    _reject(forged, G.BASENAME_COLLISION)


@pytest.mark.parametrize("policy", [
    OutputPolicy(poster_filename="COM\u00b9.jpg"), OutputPolicy(fanart_filename="CONIN$.jpg"),
    OutputPolicy(extrafanart_dirname="CONOUT$"), OutputPolicy(thumb_filename="lpt\u00b3.jpg"),
])
def test_extended_reserved_names_from_a_real_policy_fail_closed(root, policy):
    plan = make_plan(root, policy=policy)  # the planner itself accepts these
    _reject(plan, G.UNSAFE_COMPONENT)


# --------------------------------------------------------------------------- source placement


def test_source_path_lexical_rejection(plan, root):
    dotted = os.path.join(os.path.dirname(root), "dl", "..", "dl", "x.mp4")
    _reject(resource(plan, dotted), G.SOURCE_PATH_REJECTED)


@pytest.mark.skipif(os.name != "nt", reason="Windows-illegal source component")
def test_source_path_windows_illegal_component(plan, root):
    _reject(resource(plan, os.path.join(os.path.dirname(root), "dl", "a*b.mp4")), G.SOURCE_PATH_REJECTED)


def test_source_extension_must_match(plan, root):
    _reject(resource(plan, os.path.join(os.path.dirname(root), "dl", "x.mkv")), G.SOURCE_EXTENSION_MISMATCH)
    _reject(resource(plan, os.path.join(os.path.dirname(root), "dl", "x")), G.SOURCE_EXTENSION_MISMATCH)


def test_source_extension_case_differences_are_accepted(plan, root):
    validate_plan(resource(plan, os.path.join(os.path.dirname(root), "dl", "X.Mp4")))


def test_source_inside_or_equal_to_a_target(plan):
    td = plan.target_directory.absolute_path
    _reject(resource(plan, os.path.join(td, "x.mp4")), G.SOURCE_INSIDE_TARGET)
    _reject(resource(plan, os.path.join(td, "extrafanart", "deep", "x.mp4")), G.SOURCE_INSIDE_TARGET)
    _reject(resource(plan, plan.target_media_path.absolute_path), G.SOURCE_INSIDE_TARGET)


def test_source_elsewhere_inside_library_root_is_allowed(plan, root):
    validate_plan(resource(plan, os.path.join(root, "downloads", "x.mp4")))


# --------------------------------------------------------------------------- library root


@pytest.mark.skipif(os.name != "nt", reason="UNC library roots are a Windows form")
@pytest.mark.parametrize("bare_root", ["\\\\server", "\\\\server\\"])
def test_bare_server_library_root_never_reaches_execution(bare_root):
    # P4-C2-R1-02: is_fully_qualified_absolute_root accepts a bare \\server. A plan built on it either
    # fails P4-C2's own containment check, or -- if it is constructed -- is refused by the executor.
    try:
        plan = make_plan(bare_root, "C:\\dl\\x.mp4")
    except OrganizePlanError:
        return
    _reject(plan, G.LIBRARY_ROOT_REJECTED)


@pytest.mark.skipif(os.name != "nt", reason="UNC library roots are a Windows form")
def test_unc_share_library_root_is_accepted():
    validate_plan(make_plan("\\\\server\\share", "C:\\dl\\x.mp4"))


def test_library_root_with_dot_segment_is_rejected(plan, root):
    dotted_root = os.path.join(root, "..", "library")
    forged = make_plan(dotted_root, os.path.join(os.path.dirname(root), "dl", "x.mp4"))
    _reject(forged, G.LIBRARY_ROOT_REJECTED)
