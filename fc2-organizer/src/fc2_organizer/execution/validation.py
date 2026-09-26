"""Execution-boundary hardening of ``OrganizePlan`` and the artifact manifest (P4-C7).

Pure and deterministic: ZERO filesystem access (``os.path.join`` / ``basename`` /
``splitext`` are lexical only). Contract sections 6, 7 and 9.

* :func:`validate_plan` never trusts that the plan once passed ``__post_init__``
  (frozen dataclasses can be rewritten with ``object.__setattr__``): it checks every
  field by exact type *before* touching any value, reconstructs the plan through the
  public constructor to rerun P4-C2's model checks on the *current* values, and then
  checks the frozen 7-step graph and the exact planner layout.
* :func:`validate_manifest` does the same for ``tuple[ArtifactWriteRequest, ...]``.
* The execution units / expected effects are derived from the validated *fields*;
  ``plan.operations`` is only checked as a declaration that must match them.

Only the bare public packages ``fc2_organizer.planning`` and
``fc2_organizer.materialization`` are imported. The canonical number is never
re-parsed. ``materialization.mapping`` is never imported (it loads
``fc2_organizer.images``): the frozen extrafanart name format is held privately
here, and a test proves it equals ``mapping.extrafanart_filename`` for 1..10000.
"""

from __future__ import annotations

import os
from fc2_organizer.execution.errors import (
    ArtifactManifestError,
    ExecutionInputError,
    ManifestRejectionReason,
    PlanGraphError,
    PlanGraphRejectionReason,
)
from fc2_organizer.execution.models import (
    EffectKind,
    ExecutionStep,
    ExecutionUnit,
    ExpectedEffect,
    PathRole,
)
from fc2_organizer.execution.paths import (
    check_absolute_path,
    check_created_component,
    is_under,
    same_entry_name,
)
from fc2_organizer.materialization import ArtifactKind, ArtifactWriteRequest, MaterializationError
from fc2_organizer.planning import (
    OrganizePlan,
    OrganizePlanError,
    PlannedOperation,
    PlannedOperationKind,
    PlannedPath,
)

__all__ = [
    "validate_plan",
    "validate_manifest",
    "expected_units",
    "expected_effects",
    "skipped_steps",
    "extrafanart_target",
]

# Frozen P4-C6 extrafanart naming (materialization contract section 21); private copy.
_EXTRAFANART_FORMAT = "extrafanart-{:03d}.jpg"

_PLAN_FIELDS = (
    "source_path", "source_relative_path", "source_extension", "source_index", "source_size",
    "canonical_number", "library_root",
    "target_directory", "target_media_path", "nfo_path", "poster_path", "fanart_path", "thumb_path",
    "extrafanart_directory", "operations",
)
_STR_FIELDS = ("source_path", "source_relative_path", "source_extension", "canonical_number", "library_root")
_INT_FIELDS = ("source_index", "source_size")
_PATH_FIELDS = ("target_directory", "target_media_path", "nfo_path", "poster_path", "fanart_path",
                "thumb_path", "extrafanart_directory")

# Frozen 7-step graph (contract section 6.3): (kind, plan field of its target).
_GRAPH = (
    (PlannedOperationKind.CREATE_DIRECTORY, "target_directory"),
    (PlannedOperationKind.MOVE_MEDIA, "target_media_path"),
    (PlannedOperationKind.MATERIALIZE_NFO, "nfo_path"),
    (PlannedOperationKind.MATERIALIZE_POSTER, "poster_path"),
    (PlannedOperationKind.MATERIALIZE_FANART, "fanart_path"),
    (PlannedOperationKind.MATERIALIZE_THUMB, "thumb_path"),
    (PlannedOperationKind.ENSURE_EXTRAFANART_DIRECTORY, "extrafanart_directory"),
)

_KIND_RANK = {
    ArtifactKind.NFO: 0, ArtifactKind.POSTER: 1, ArtifactKind.FANART: 2, ArtifactKind.THUMB: 3,
    ArtifactKind.EXTRAFANART: 4,
}
_SINGLE_KINDS = (ArtifactKind.NFO, ArtifactKind.POSTER, ArtifactKind.FANART, ArtifactKind.THUMB)
_MAIN_ARTIFACTS = (
    # (artifact kind, plan path field, step, role)
    (ArtifactKind.POSTER, "poster_path", ExecutionStep.MATERIALIZE_POSTER, PathRole.POSTER),
    (ArtifactKind.FANART, "fanart_path", ExecutionStep.MATERIALIZE_FANART, PathRole.FANART),
    (ArtifactKind.THUMB, "thumb_path", ExecutionStep.MATERIALIZE_THUMB, PathRole.THUMB),
)
_ARTIFACT_TARGET_FIELD = {
    ArtifactKind.NFO: "nfo_path", ArtifactKind.POSTER: "poster_path",
    ArtifactKind.FANART: "fanart_path", ArtifactKind.THUMB: "thumb_path",
}


def _plan_error(reason: PlanGraphRejectionReason) -> PlanGraphError:
    return PlanGraphError(reason)


# --------------------------------------------------------------------------- plan


def validate_plan(plan: OrganizePlan) -> None:
    """Contract section 6. Raises :class:`PlanGraphError`; returns ``None`` when intact."""
    if type(plan) is not OrganizePlan:
        raise ExecutionInputError("plan must be an exact OrganizePlan")
    _check_field_types(plan)
    _check_reconstruction(plan)
    _check_graph(plan)
    _check_target_paths(plan)
    _check_layout(plan)
    _check_source(plan)


def _check_field_types(plan: OrganizePlan) -> None:
    # Exact types first: no method of any (possibly hostile) field value runs before this passes.
    for name in _STR_FIELDS:
        value = getattr(plan, name)
        if type(value) is not str or not value:
            raise _plan_error(PlanGraphRejectionReason.FIELD_TYPE)
    for name in _INT_FIELDS:
        value = getattr(plan, name)
        if type(value) is not int or value < 0:
            raise _plan_error(PlanGraphRejectionReason.FIELD_TYPE)
    for name in _PATH_FIELDS:
        if not _is_planned_path(getattr(plan, name)):
            raise _plan_error(PlanGraphRejectionReason.PATH_TYPE)
    operations = plan.operations
    if type(operations) is not tuple:
        raise _plan_error(PlanGraphRejectionReason.OPERATIONS_NOT_TUPLE)
    for op in operations:
        if type(op) is not PlannedOperation or type(op.kind) is not PlannedOperationKind:
            raise _plan_error(PlanGraphRejectionReason.OPERATION_TYPE)
        if not _is_planned_path(op.target) or not (op.source is None or _is_planned_path(op.source)):
            raise _plan_error(PlanGraphRejectionReason.OPERATION_TYPE)


def _is_planned_path(value: object) -> bool:
    if type(value) is not PlannedPath:
        return False
    path = value.absolute_path
    return type(path) is str and bool(path)


def _check_reconstruction(plan: OrganizePlan) -> None:
    values = {name: getattr(plan, name) for name in _PLAN_FIELDS}
    rebuilt: OrganizePlan | None = None
    try:
        rebuilt = OrganizePlan(**values)
    except OrganizePlanError:
        pass  # raised below, outside the except block: the planning error is never chained
    if rebuilt is None or rebuilt != plan:
        raise _plan_error(PlanGraphRejectionReason.PLAN_RECONSTRUCTION_FAILED)


def _check_graph(plan: OrganizePlan) -> None:
    operations = plan.operations
    if len(operations) != len(_GRAPH):
        raise _plan_error(PlanGraphRejectionReason.OPERATION_COUNT)
    source = plan.source_path
    for op, (kind, field_name) in zip(operations, _GRAPH):
        if op.kind is not kind:
            raise _plan_error(PlanGraphRejectionReason.OPERATION_KIND_ORDER)
        if op.target.absolute_path != getattr(plan, field_name).absolute_path:
            raise _plan_error(PlanGraphRejectionReason.OPERATION_TARGET_MISMATCH)
        if kind is PlannedOperationKind.MOVE_MEDIA:
            if op.source is None or op.source.absolute_path != source:
                raise _plan_error(PlanGraphRejectionReason.OPERATION_SOURCE_MISMATCH)
        elif op.source is not None:
            raise _plan_error(PlanGraphRejectionReason.OPERATION_SOURCE_MISMATCH)


def _check_target_paths(plan: OrganizePlan) -> None:
    if check_absolute_path(plan.library_root, directory_root=True) is not None:
        raise _plan_error(PlanGraphRejectionReason.LIBRARY_ROOT_REJECTED)
    for name in _PATH_FIELDS:
        if check_absolute_path(getattr(plan, name).absolute_path) is not None:
            raise _plan_error(PlanGraphRejectionReason.TARGET_PATH_REJECTED)


def _child_name(directory: str, path: str) -> str | None:
    """The single component ``b`` with ``os.path.join(directory, b) == path``, else None."""
    name = os.path.basename(path)
    if not name or os.path.join(directory, name) != path:
        return None
    return name


def _check_layout(plan: OrganizePlan) -> None:
    number = plan.canonical_number
    target_directory = plan.target_directory.absolute_path
    if target_directory != os.path.join(plan.library_root, number):
        raise _plan_error(PlanGraphRejectionReason.TARGET_DIRECTORY_LAYOUT)
    media_name = number + plan.source_extension.lower()
    if plan.target_media_path.absolute_path != os.path.join(target_directory, media_name):
        raise _plan_error(PlanGraphRejectionReason.MEDIA_NAME_MISMATCH)
    nfo_name = _child_name(target_directory, plan.nfo_path.absolute_path)
    if nfo_name is None or not nfo_name.startswith(number):
        raise _plan_error(PlanGraphRejectionReason.NFO_NAME_INVALID)
    nfo_extension = nfo_name[len(number):]
    if not nfo_extension.startswith(".") or len(nfo_extension) < 2:
        raise _plan_error(PlanGraphRejectionReason.NFO_NAME_INVALID)
    names = [media_name, nfo_name]
    for name in ("poster_path", "fanart_path", "thumb_path", "extrafanart_directory"):
        child = _child_name(target_directory, getattr(plan, name).absolute_path)
        if child is None:
            raise _plan_error(PlanGraphRejectionReason.ARTIFACT_LAYOUT)
        names.append(child)
    for component in (number, *names):
        if check_created_component(component) is not None:
            raise _plan_error(PlanGraphRejectionReason.UNSAFE_COMPONENT)
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            if same_entry_name(names[i], names[j]):
                raise _plan_error(PlanGraphRejectionReason.BASENAME_COLLISION)


def _check_source(plan: OrganizePlan) -> None:
    source = plan.source_path
    if check_absolute_path(source) is not None:
        raise _plan_error(PlanGraphRejectionReason.SOURCE_PATH_REJECTED)
    if os.path.splitext(source)[1].lower() != plan.source_extension.lower():
        raise _plan_error(PlanGraphRejectionReason.SOURCE_EXTENSION_MISMATCH)
    target_directory = plan.target_directory.absolute_path
    for name in _PATH_FIELDS:
        if same_entry_name(source, getattr(plan, name).absolute_path):
            raise _plan_error(PlanGraphRejectionReason.SOURCE_INSIDE_TARGET)
    if is_under(source, target_directory):
        raise _plan_error(PlanGraphRejectionReason.SOURCE_INSIDE_TARGET)


# --------------------------------------------------------------------------- manifest


def _manifest_error(reason: ManifestRejectionReason) -> ArtifactManifestError:
    return ArtifactManifestError(reason)


def extrafanart_target(plan: OrganizePlan, ordinal: int) -> str:
    return os.path.join(plan.extrafanart_directory.absolute_path, _EXTRAFANART_FORMAT.format(ordinal))


def validate_manifest(plan: OrganizePlan, artifacts: tuple[ArtifactWriteRequest, ...]) -> None:
    """Contract section 7. ``plan`` must already be validated. Raises :class:`ArtifactManifestError`."""
    if type(plan) is not OrganizePlan:
        raise ExecutionInputError("plan must be an exact OrganizePlan")
    if type(artifacts) is not tuple:
        raise ExecutionInputError("artifacts must be an exact tuple")
    for request in artifacts:
        if type(request) is not ArtifactWriteRequest:
            raise _manifest_error(ManifestRejectionReason.REQUEST_TYPE)
    for request in artifacts:
        _check_request(request)
    for request in artifacts:
        if not request.content:
            raise _manifest_error(ManifestRejectionReason.EMPTY_CONTENT)
    _check_shape([request.kind for request in artifacts])
    _check_targets(plan, artifacts)


def _check_request(request: ArtifactWriteRequest) -> None:
    kind, target, content, ordinal = request.kind, request.target_path, request.content, request.ordinal
    if (type(kind) is not ArtifactKind or type(target) is not str or type(content) is not bytes
            or not (ordinal is None or type(ordinal) is int)):
        raise _manifest_error(ManifestRejectionReason.REQUEST_INVALID)
    rebuilt: ArtifactWriteRequest | None = None
    try:
        rebuilt = ArtifactWriteRequest(kind, target, content, ordinal)
    except MaterializationError:
        pass  # raised below, never chained
    if rebuilt is None or rebuilt != request:
        raise _manifest_error(ManifestRejectionReason.REQUEST_INVALID)


def _check_shape(kinds: list[ArtifactKind]) -> None:
    if ArtifactKind.NFO not in kinds:
        raise _manifest_error(ManifestRejectionReason.NFO_MISSING)
    if kinds[0] is not ArtifactKind.NFO:
        raise _manifest_error(ManifestRejectionReason.NFO_NOT_FIRST)
    for single in _SINGLE_KINDS:
        if kinds.count(single) > 1:
            raise _manifest_error(ManifestRejectionReason.DUPLICATE_KIND)
    ranks = [_KIND_RANK[kind] for kind in kinds]
    if ranks != sorted(ranks):
        raise _manifest_error(ManifestRejectionReason.ORDER)


def _check_targets(plan: OrganizePlan, artifacts: tuple[ArtifactWriteRequest, ...]) -> None:
    expected_ordinal = 0
    for request in artifacts:
        if request.kind is ArtifactKind.EXTRAFANART:
            expected_ordinal += 1
            if request.ordinal != expected_ordinal:
                raise _manifest_error(ManifestRejectionReason.EXTRAFANART_ORDINAL_SEQUENCE)
            if request.target_path != extrafanart_target(plan, expected_ordinal):
                raise _manifest_error(ManifestRejectionReason.EXTRAFANART_NAME_MISMATCH)
        elif request.target_path != getattr(plan, _ARTIFACT_TARGET_FIELD[request.kind]).absolute_path:
            raise _manifest_error(ManifestRejectionReason.TARGET_MISMATCH)
    targets = [request.target_path for request in artifacts]
    targets += [plan.target_media_path.absolute_path, plan.extrafanart_directory.absolute_path]
    fold = str.casefold if os.name == "nt" else (lambda s: s)
    keys = [fold(target) for target in targets]
    if len(set(keys)) != len(keys):
        raise _manifest_error(ManifestRejectionReason.DUPLICATE_TARGET)


# --------------------------------------------------------------------------- units / effects


def _present(artifacts: tuple[ArtifactWriteRequest, ...], kind: ArtifactKind) -> bool:
    return any(request.kind is kind for request in artifacts)


def skipped_steps(artifacts: tuple[ArtifactWriteRequest, ...]) -> tuple[ExecutionStep, ...]:
    return tuple(step for kind, _, step, _ in _MAIN_ARTIFACTS if not _present(artifacts, kind))


def expected_units(plan: OrganizePlan, artifacts: tuple[ArtifactWriteRequest, ...]) -> tuple[ExecutionUnit, ...]:
    """Contract section 9: ordered units derived from the validated plan and manifest."""
    units = [
        ExecutionUnit(ExecutionStep.CREATE_DIRECTORY, PathRole.TARGET_DIRECTORY, None, None),
        ExecutionUnit(ExecutionStep.MOVE_MEDIA, PathRole.TARGET_MEDIA, None, None),
        ExecutionUnit(ExecutionStep.MATERIALIZE_NFO, PathRole.NFO, ArtifactKind.NFO, None),
    ]
    for kind, _, step, role in _MAIN_ARTIFACTS:
        if _present(artifacts, kind):
            units.append(ExecutionUnit(step, role, kind, None))
    units.append(ExecutionUnit(ExecutionStep.ENSURE_EXTRAFANART_DIRECTORY, PathRole.EXTRAFANART_DIRECTORY,
                               None, None))
    for request in artifacts:
        if request.kind is ArtifactKind.EXTRAFANART:
            units.append(ExecutionUnit(ExecutionStep.MATERIALIZE_EXTRAFANART, PathRole.EXTRAFANART_FILE,
                                       ArtifactKind.EXTRAFANART, request.ordinal))
    return tuple(units)


def expected_effects(plan: OrganizePlan, artifacts: tuple[ArtifactWriteRequest, ...]) -> tuple[ExpectedEffect, ...]:
    """Contract section 9: the full expected effect sequence E; checkpoints hold a prefix of it."""
    effects = [
        ExpectedEffect(EffectKind.TARGET_DIRECTORY_CREATED, PathRole.TARGET_DIRECTORY,
                       plan.target_directory.absolute_path, None, None),
        ExpectedEffect(EffectKind.MEDIA_PUBLISHED, PathRole.TARGET_MEDIA,
                       plan.target_media_path.absolute_path, None, None),
        ExpectedEffect(EffectKind.SOURCE_REMOVED, PathRole.SOURCE, plan.source_path, None, None),
        ExpectedEffect(EffectKind.ARTIFACT_PUBLISHED, PathRole.NFO, plan.nfo_path.absolute_path,
                       ArtifactKind.NFO, None),
    ]
    for kind, field_name, _, role in _MAIN_ARTIFACTS:
        if _present(artifacts, kind):
            effects.append(ExpectedEffect(EffectKind.ARTIFACT_PUBLISHED, role,
                                          getattr(plan, field_name).absolute_path, kind, None))
    effects.append(ExpectedEffect(EffectKind.EXTRAFANART_DIRECTORY_CREATED, PathRole.EXTRAFANART_DIRECTORY,
                                  plan.extrafanart_directory.absolute_path, None, None))
    for request in artifacts:
        if request.kind is ArtifactKind.EXTRAFANART:
            effects.append(ExpectedEffect(EffectKind.ARTIFACT_PUBLISHED, PathRole.EXTRAFANART_FILE,
                                          request.target_path, ArtifactKind.EXTRAFANART, request.ordinal))
    return tuple(effects)
