"""Model-level contract tests for ``fc2_organizer.planning.models``:
``PlannedPath``, ``PlannedOperation``, ``OrganizePlan`` invariants and deep
immutability (contract section 20, tests #28).
"""

from __future__ import annotations

import dataclasses

import pytest

from fc2_organizer.planning.errors import OrganizePlanContractError, TargetEscapesLibraryRootError
from fc2_organizer.planning.models import (
    OrganizePlan,
    PlannedOperation,
    PlannedOperationKind,
    PlannedPath,
)


def _valid_plan(**overrides) -> OrganizePlan:
    library_root = r"C:\library"
    target_directory = PlannedPath(library_root + r"\FC2-1234567")
    defaults = dict(
        source_path=r"C:\downloads\a.mp4",
        source_relative_path="a.mp4",
        source_extension=".mp4",
        source_index=0,
        source_size=123,
        canonical_number="FC2-1234567",
        library_root=library_root,
        target_directory=target_directory,
        target_media_path=PlannedPath(target_directory.absolute_path + r"\FC2-1234567.mp4"),
        nfo_path=PlannedPath(target_directory.absolute_path + r"\FC2-1234567.nfo"),
        poster_path=PlannedPath(target_directory.absolute_path + r"\poster.jpg"),
        fanart_path=PlannedPath(target_directory.absolute_path + r"\fanart.jpg"),
        thumb_path=PlannedPath(target_directory.absolute_path + r"\thumb.jpg"),
        extrafanart_directory=PlannedPath(target_directory.absolute_path + r"\extrafanart"),
        operations=(
            PlannedOperation(kind=PlannedOperationKind.CREATE_DIRECTORY, target=target_directory),
        ),
    )
    defaults.update(overrides)
    return OrganizePlan(**defaults)


class TestPlannedPath:
    def test_valid_absolute_path_accepted(self):
        p = PlannedPath(r"C:\library\FC2-1234567")
        assert p.absolute_path == r"C:\library\FC2-1234567"

    def test_relative_path_rejected(self):
        with pytest.raises(OrganizePlanContractError):
            PlannedPath(r"relative\path")

    def test_empty_string_rejected(self):
        with pytest.raises(OrganizePlanContractError):
            PlannedPath("")

    def test_non_str_rejected(self):
        with pytest.raises(OrganizePlanContractError):
            PlannedPath(123)  # type: ignore[arg-type]

    def test_frozen_scalar_reassignment_raises(self):
        p = PlannedPath(r"C:\library\FC2-1234567")
        with pytest.raises(dataclasses.FrozenInstanceError):
            p.absolute_path = r"C:\other"  # type: ignore[misc]

    def test_str_dunder_returns_absolute_path(self):
        p = PlannedPath(r"C:\library\FC2-1234567")
        assert str(p) == r"C:\library\FC2-1234567"


class TestPlannedOperation:
    def test_non_move_operation_with_source_rejected(self):
        target = PlannedPath(r"C:\library\FC2-1234567")
        with pytest.raises(OrganizePlanContractError):
            PlannedOperation(
                kind=PlannedOperationKind.CREATE_DIRECTORY,
                target=target,
                source=PlannedPath(r"C:\downloads\a.mp4"),
            )

    def test_move_media_without_source_rejected(self):
        target = PlannedPath(r"C:\library\FC2-1234567\FC2-1234567.mp4")
        with pytest.raises(OrganizePlanContractError):
            PlannedOperation(kind=PlannedOperationKind.MOVE_MEDIA, target=target)

    def test_move_media_with_source_accepted(self):
        target = PlannedPath(r"C:\library\FC2-1234567\FC2-1234567.mp4")
        source = PlannedPath(r"C:\downloads\a.mp4")
        op = PlannedOperation(kind=PlannedOperationKind.MOVE_MEDIA, target=target, source=source)
        assert op.source == source

    def test_bad_kind_type_rejected(self):
        target = PlannedPath(r"C:\library\FC2-1234567")
        with pytest.raises(OrganizePlanContractError):
            PlannedOperation(kind="CREATE_DIRECTORY", target=target)  # type: ignore[arg-type]

    def test_bad_target_type_rejected(self):
        with pytest.raises(OrganizePlanContractError):
            PlannedOperation(kind=PlannedOperationKind.CREATE_DIRECTORY, target=r"C:\library")  # type: ignore[arg-type]

    def test_frozen_reassignment_raises(self):
        target = PlannedPath(r"C:\library\FC2-1234567")
        op = PlannedOperation(kind=PlannedOperationKind.CREATE_DIRECTORY, target=target)
        with pytest.raises(dataclasses.FrozenInstanceError):
            op.target = PlannedPath(r"C:\other")  # type: ignore[misc]


class TestOrganizePlanImmutability:
    def test_scalar_reassignment_raises(self):
        plan = _valid_plan()
        with pytest.raises(dataclasses.FrozenInstanceError):
            plan.canonical_number = "FC2-7654321"  # type: ignore[misc]

    def test_operations_tuple_cannot_be_mutated_in_place(self):
        plan = _valid_plan()
        with pytest.raises(TypeError):
            plan.operations[0] = plan.operations[0]  # type: ignore[index]

    def test_operations_is_a_real_tuple_not_a_list(self):
        plan = _valid_plan()
        assert isinstance(plan.operations, tuple)
        assert not isinstance(plan.operations, list)

    def test_no_public_mutator_methods_exist(self):
        plan = _valid_plan()
        forbidden_names = {"append", "extend", "insert", "remove", "pop", "clear", "update"}
        public_attrs = {name for name in dir(plan) if not name.startswith("_")}
        assert not (public_attrs & forbidden_names)


class TestOrganizePlanContract:
    def test_relative_source_path_rejected(self):
        with pytest.raises(OrganizePlanContractError):
            _valid_plan(source_path="a.mp4")

    def test_relative_library_root_rejected(self):
        with pytest.raises(OrganizePlanContractError):
            _valid_plan(library_root="library")

    def test_negative_source_index_rejected(self):
        with pytest.raises(OrganizePlanContractError):
            _valid_plan(source_index=-1)

    def test_negative_source_size_rejected(self):
        with pytest.raises(OrganizePlanContractError):
            _valid_plan(source_size=-1)

    def test_bool_source_index_rejected(self):
        with pytest.raises(OrganizePlanContractError):
            _valid_plan(source_index=True)

    def test_non_planned_path_target_field_rejected(self):
        with pytest.raises(OrganizePlanContractError):
            _valid_plan(target_media_path=r"C:\library\FC2-1234567\FC2-1234567.mp4")

    def test_operations_must_be_tuple_of_planned_operation(self):
        with pytest.raises(OrganizePlanContractError):
            _valid_plan(operations=["not", "planned", "operations"])

    def test_target_path_outside_library_root_raises_target_escapes_error(self):
        with pytest.raises(TargetEscapesLibraryRootError):
            _valid_plan(target_media_path=PlannedPath(r"C:\somewhere\else\FC2-1234567.mp4"))

    def test_target_escapes_error_is_organize_plan_contract_error(self):
        assert issubclass(TargetEscapesLibraryRootError, OrganizePlanContractError)

    def test_target_path_equal_to_library_root_is_not_contained(self):
        library_root = r"C:\library"
        with pytest.raises(TargetEscapesLibraryRootError):
            _valid_plan(library_root=library_root, target_directory=PlannedPath(library_root))
