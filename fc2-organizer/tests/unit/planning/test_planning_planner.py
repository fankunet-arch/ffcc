"""Tests for ``fc2_organizer.planning.planner.build_organize_plan`` --
the P4-C2 test matrix (contract section 29, items 1-27).
"""

from __future__ import annotations

import dataclasses
import os

import pytest

from fc2_metadata_core.models import NormalizedMetadata
from fc2_organizer.discovery import DiscoveredMediaItem
from fc2_organizer.planning.errors import (
    InternalTargetCollisionError,
    InvalidCanonicalNumberError,
    InvalidLibraryRootError,
    InvalidMetadataForPlanningError,
    InvalidOutputPolicyError,
    OrganizePlanInputError,
    UnsafeTargetComponentError,
)
from fc2_organizer.planning.models import PlannedOperationKind
from fc2_organizer.planning.planner import build_organize_plan
from fc2_organizer.planning.policy import OutputPolicy

LIBRARY_ROOT = r"C:\library"


def _item(*, index=0, source_path=r"C:\downloads\random-name.MP4", relative_path="random-name.MP4",
          extension=".mp4", size=123) -> DiscoveredMediaItem:
    return DiscoveredMediaItem(
        index=index, source_path=source_path, relative_path=relative_path,
        extension=extension, size=size,
    )


def _metadata(**overrides) -> NormalizedMetadata:
    defaults = dict(number="FC2-1234567", title="Example Title")
    defaults.update(overrides)
    return NormalizedMetadata(**defaults)


# --- 1-10: standard layout / extension handling / deterministic fields ----


def test_standard_mp4_plan_matches_frozen_v1_layout():
    plan = build_organize_plan(_item(), "FC2-1234567", _metadata(), LIBRARY_ROOT)
    assert plan.target_directory.absolute_path == LIBRARY_ROOT + r"\FC2-1234567"
    assert plan.target_media_path.absolute_path == LIBRARY_ROOT + r"\FC2-1234567\FC2-1234567.mp4"
    assert plan.nfo_path.absolute_path == LIBRARY_ROOT + r"\FC2-1234567\FC2-1234567.nfo"
    assert plan.poster_path.absolute_path == LIBRARY_ROOT + r"\FC2-1234567\poster.jpg"
    assert plan.fanart_path.absolute_path == LIBRARY_ROOT + r"\FC2-1234567\fanart.jpg"
    assert plan.thumb_path.absolute_path == LIBRARY_ROOT + r"\FC2-1234567\thumb.jpg"
    assert plan.extrafanart_directory.absolute_path == LIBRARY_ROOT + r"\FC2-1234567\extrafanart"


@pytest.mark.parametrize("extension", [".mkv", ".avi", ".mov", ".wmv", ".m4v", ".ts"])
def test_original_extension_preserved_never_changes_container(extension):
    plan = build_organize_plan(_item(extension=extension), "FC2-1234567", _metadata(), LIBRARY_ROOT)
    assert plan.target_media_path.absolute_path.endswith(extension)
    assert not plan.target_media_path.absolute_path.endswith(".mp4") or extension == ".mp4"


def test_uppercase_source_extension_is_normalized_to_lowercase_in_target():
    # DiscoveredMediaItem's own model contract does not itself enforce
    # lowercase (only requires a leading '.'), so a hand-built item can
    # carry an uppercase extension; the planner must still normalize it.
    item = _item(extension=".MP4")
    plan = build_organize_plan(item, "FC2-1234567", _metadata(), LIBRARY_ROOT)
    assert plan.target_media_path.absolute_path.endswith("FC2-1234567.mp4")
    # Source identity itself is preserved unmodified for later verification.
    assert plan.source_extension == ".MP4"


def test_deterministic_target_directory():
    plan = build_organize_plan(_item(), "FC2-1234567", _metadata(), LIBRARY_ROOT)
    assert plan.target_directory.absolute_path == LIBRARY_ROOT + r"\FC2-1234567"


def test_deterministic_target_media_path():
    plan = build_organize_plan(_item(), "FC2-1234567", _metadata(), LIBRARY_ROOT)
    assert plan.target_media_path.absolute_path == LIBRARY_ROOT + r"\FC2-1234567\FC2-1234567.mp4"


def test_deterministic_nfo_path():
    plan = build_organize_plan(_item(), "FC2-1234567", _metadata(), LIBRARY_ROOT)
    assert plan.nfo_path.absolute_path == LIBRARY_ROOT + r"\FC2-1234567\FC2-1234567.nfo"


def test_deterministic_poster_path():
    plan = build_organize_plan(_item(), "FC2-1234567", _metadata(), LIBRARY_ROOT)
    assert plan.poster_path.absolute_path == LIBRARY_ROOT + r"\FC2-1234567\poster.jpg"


def test_deterministic_fanart_path():
    plan = build_organize_plan(_item(), "FC2-1234567", _metadata(), LIBRARY_ROOT)
    assert plan.fanart_path.absolute_path == LIBRARY_ROOT + r"\FC2-1234567\fanart.jpg"


def test_deterministic_thumb_path():
    plan = build_organize_plan(_item(), "FC2-1234567", _metadata(), LIBRARY_ROOT)
    assert plan.thumb_path.absolute_path == LIBRARY_ROOT + r"\FC2-1234567\thumb.jpg"


def test_deterministic_extrafanart_directory():
    plan = build_organize_plan(_item(), "FC2-1234567", _metadata(), LIBRARY_ROOT)
    assert plan.extrafanart_directory.absolute_path == LIBRARY_ROOT + r"\FC2-1234567\extrafanart"


# --- 11-12: identical/distinct inputs ---------------------------------


def test_identical_input_produces_identical_plan():
    item = _item()
    metadata = _metadata()
    plan_a = build_organize_plan(item, "FC2-1234567", metadata, LIBRARY_ROOT)
    plan_b = build_organize_plan(item, "FC2-1234567", metadata, LIBRARY_ROOT)
    assert plan_a == plan_b


def test_different_source_items_same_fc2_number_remain_distinguishable():
    item_a = _item(index=0, source_path=r"C:\downloads\a\movie.mp4", relative_path="a/movie.mp4")
    item_b = _item(index=0, source_path=r"C:\downloads\b\movie.mp4", relative_path="b/movie.mp4")
    plan_a = build_organize_plan(item_a, "FC2-1234567", _metadata(), LIBRARY_ROOT)
    plan_b = build_organize_plan(item_b, "FC2-1234567", _metadata(), LIBRARY_ROOT)
    assert plan_a.source_path != plan_b.source_path
    assert plan_a != plan_b
    # But they still plan to the same target -- that is exactly why
    # InternalTargetCollisionError / real filesystem preflight matters at
    # execution time; P4-C2 does not resolve this, it only surfaces it.
    assert plan_a.target_media_path == plan_b.target_media_path


# --- 13-14: canonical number validation --------------------------------


def test_valid_canonical_number_accepted():
    plan = build_organize_plan(_item(), "FC2-1234567", _metadata(), LIBRARY_ROOT)
    assert plan.canonical_number == "FC2-1234567"


@pytest.mark.parametrize(
    "dirty",
    ["fc2-1234567", "FC2PPV-1234567", "abc FC2-1234567.mp4", "FC2-123", "not-a-number", ""],
)
def test_dirty_or_noncanonical_number_rejected(dirty):
    with pytest.raises(InvalidCanonicalNumberError):
        build_organize_plan(_item(), dirty, _metadata(), LIBRARY_ROOT)


def test_non_str_canonical_number_rejected():
    with pytest.raises(OrganizePlanInputError):
        build_organize_plan(_item(), 1234567, _metadata(), LIBRARY_ROOT)  # type: ignore[arg-type]


def test_str_subclass_canonical_number_rejected():
    class HostileStr(str):
        pass

    with pytest.raises(OrganizePlanInputError):
        build_organize_plan(_item(), HostileStr("FC2-1234567"), _metadata(), LIBRARY_ROOT)


# --- 15: invalid metadata rejected --------------------------------------


def test_metadata_without_number_rejected():
    with pytest.raises(InvalidMetadataForPlanningError):
        build_organize_plan(_item(), "FC2-1234567", NormalizedMetadata(title="Example"), LIBRARY_ROOT)


def test_metadata_without_title_rejected():
    with pytest.raises(InvalidMetadataForPlanningError):
        build_organize_plan(_item(), "FC2-1234567", NormalizedMetadata(number="FC2-1234567"), LIBRARY_ROOT)


def test_empty_metadata_rejected():
    with pytest.raises(InvalidMetadataForPlanningError):
        build_organize_plan(_item(), "FC2-1234567", NormalizedMetadata(), LIBRARY_ROOT)


def test_non_normalized_metadata_type_rejected():
    with pytest.raises(OrganizePlanInputError):
        build_organize_plan(_item(), "FC2-1234567", {"number": "FC2-1234567", "title": "x"}, LIBRARY_ROOT)  # type: ignore[arg-type]


# --- 16: empty/invalid library root rejected ----------------------------


def test_empty_library_root_rejected():
    with pytest.raises(InvalidLibraryRootError):
        build_organize_plan(_item(), "FC2-1234567", _metadata(), "")


def test_whitespace_only_library_root_rejected():
    with pytest.raises(InvalidLibraryRootError):
        build_organize_plan(_item(), "FC2-1234567", _metadata(), "   ")


def test_relative_library_root_rejected():
    with pytest.raises(InvalidLibraryRootError):
        build_organize_plan(_item(), "FC2-1234567", _metadata(), "library")


def test_non_str_non_pathlike_library_root_rejected():
    with pytest.raises(OrganizePlanInputError):
        build_organize_plan(_item(), "FC2-1234567", _metadata(), 12345)  # type: ignore[arg-type]


def test_pathlike_library_root_accepted():
    import pathlib

    plan = build_organize_plan(_item(), "FC2-1234567", _metadata(), pathlib.Path(LIBRARY_ROOT))
    assert plan.library_root == LIBRARY_ROOT


# --- P4-C2-GOV-03: library_root must be fully-qualified -----------------
#
# Windows-specific forms are only meaningful on a Windows host (a bare
# backslash is an ordinary filename character on POSIX, not a separator);
# gated accordingly (contract section 10).


@pytest.mark.skipif(os.name != "nt", reason="Windows rooted-but-driveless path")
def test_windows_rooted_but_driveless_backslash_root_rejected():
    with pytest.raises(InvalidLibraryRootError):
        build_organize_plan(_item(), "FC2-1234567", _metadata(), r"\library")


@pytest.mark.skipif(os.name != "nt", reason="Windows rooted-but-driveless path")
def test_windows_rooted_but_driveless_forward_slash_root_rejected():
    with pytest.raises(InvalidLibraryRootError):
        build_organize_plan(_item(), "FC2-1234567", _metadata(), "/library")


@pytest.mark.skipif(os.name != "nt", reason="Windows drive-relative path")
def test_windows_drive_relative_root_rejected():
    with pytest.raises(InvalidLibraryRootError):
        build_organize_plan(_item(), "FC2-1234567", _metadata(), "C:library")


@pytest.mark.skipif(os.name != "nt", reason="Windows dot-relative path")
def test_windows_dot_relative_root_rejected():
    with pytest.raises(InvalidLibraryRootError):
        build_organize_plan(_item(), "FC2-1234567", _metadata(), r".\library")


@pytest.mark.skipif(os.name != "nt", reason="Windows dot-dot-relative path")
def test_windows_dotdot_relative_root_rejected():
    with pytest.raises(InvalidLibraryRootError):
        build_organize_plan(_item(), "FC2-1234567", _metadata(), r"..\library")


@pytest.mark.skipif(os.name != "nt", reason="Windows UNC share root")
def test_windows_unc_share_root_accepted():
    plan = build_organize_plan(_item(), "FC2-1234567", _metadata(), r"\\server\share\library")
    assert plan.target_directory.absolute_path == r"\\server\share\library\FC2-1234567"
    assert plan.target_media_path.absolute_path == r"\\server\share\library\FC2-1234567\FC2-1234567.mp4"


@pytest.mark.skipif(os.name != "nt", reason="Windows bare drive root")
def test_windows_bare_drive_root_accepted_as_library_root():
    # P4-C2-GOV-02's exact scenario, exercised end-to-end through the
    # public API: a bare drive root must not wrongly reject its own child.
    plan = build_organize_plan(_item(), "FC2-1234567", _metadata(), "C:\\")
    assert plan.target_directory.absolute_path == "C:\\FC2-1234567"
    assert plan.target_media_path.absolute_path == "C:\\FC2-1234567\\FC2-1234567.mp4"


@pytest.mark.skipif(os.name == "nt", reason="POSIX absolute path")
def test_posix_absolute_root_still_accepted():
    # A POSIX-style absolute source_path here, deliberately not the
    # module's Windows-hardcoded ``_item()`` default -- this test only runs
    # on a POSIX host, where DiscoveredMediaItem's own absolute-path
    # invariant requires a real POSIX absolute path.
    posix_item = _item(source_path="/downloads/random-name.MP4", relative_path="random-name.MP4")
    plan = build_organize_plan(posix_item, "FC2-1234567", _metadata(), "/library")
    assert plan.target_directory.absolute_path == "/library/FC2-1234567"


# --- 17-18: target containment / traversal ------------------------------


def test_all_target_paths_contained_in_library_root():
    plan = build_organize_plan(_item(), "FC2-1234567", _metadata(), LIBRARY_ROOT)
    for planned in (
        plan.target_directory, plan.target_media_path, plan.nfo_path,
        plan.poster_path, plan.fanart_path, plan.thumb_path, plan.extrafanart_directory,
    ):
        assert planned.absolute_path.startswith(LIBRARY_ROOT + "\\")


def test_traversal_via_artifact_filename_cannot_escape_root():
    policy = OutputPolicy(poster_filename=r"..\..\evil.jpg")
    with pytest.raises(UnsafeTargetComponentError):
        build_organize_plan(_item(), "FC2-1234567", _metadata(), LIBRARY_ROOT, policy=policy)


def test_traversal_via_extrafanart_dirname_cannot_escape_root():
    policy = OutputPolicy(extrafanart_dirname="..")
    with pytest.raises(UnsafeTargetComponentError):
        build_organize_plan(_item(), "FC2-1234567", _metadata(), LIBRARY_ROOT, policy=policy)


def test_absolute_child_override_via_artifact_filename_cannot_escape_root():
    policy = OutputPolicy(poster_filename=r"C:\somewhere\else\evil.jpg")
    with pytest.raises(UnsafeTargetComponentError):
        build_organize_plan(_item(), "FC2-1234567", _metadata(), LIBRARY_ROOT, policy=policy)


def test_drive_replacement_via_artifact_filename_cannot_escape_root():
    policy = OutputPolicy(poster_filename=r"D:evil.jpg")
    with pytest.raises(UnsafeTargetComponentError):
        build_organize_plan(_item(), "FC2-1234567", _metadata(), LIBRARY_ROOT, policy=policy)


# --- 19-21: Windows naming safety ---------------------------------------


def test_windows_illegal_character_in_artifact_filename_rejected():
    policy = OutputPolicy(poster_filename="post|er.jpg")
    with pytest.raises(UnsafeTargetComponentError):
        build_organize_plan(_item(), "FC2-1234567", _metadata(), LIBRARY_ROOT, policy=policy)


def test_reserved_device_name_artifact_filename_rejected():
    policy = OutputPolicy(poster_filename="CON.jpg")
    with pytest.raises(UnsafeTargetComponentError):
        build_organize_plan(_item(), "FC2-1234567", _metadata(), LIBRARY_ROOT, policy=policy)


def test_trailing_dot_artifact_filename_rejected():
    policy = OutputPolicy(poster_filename="poster.jpg.")
    with pytest.raises(UnsafeTargetComponentError):
        build_organize_plan(_item(), "FC2-1234567", _metadata(), LIBRARY_ROOT, policy=policy)


def test_trailing_space_artifact_filename_rejected():
    policy = OutputPolicy(poster_filename="poster.jpg ")
    with pytest.raises(UnsafeTargetComponentError):
        build_organize_plan(_item(), "FC2-1234567", _metadata(), LIBRARY_ROOT, policy=policy)


# --- 22-23: case-insensitive / internal collision -----------------------


def test_case_insensitive_collision_between_poster_and_fanart_fails_closed():
    policy = OutputPolicy(poster_filename="Poster.JPG", fanart_filename="poster.jpg")
    with pytest.raises(InternalTargetCollisionError):
        build_organize_plan(_item(), "FC2-1234567", _metadata(), LIBRARY_ROOT, policy=policy)


def test_collision_between_nfo_and_media_when_nfo_extension_matches_source_fails_closed():
    policy = OutputPolicy(nfo_extension=".mp4")
    with pytest.raises(InternalTargetCollisionError):
        build_organize_plan(_item(extension=".mp4"), "FC2-1234567", _metadata(), LIBRARY_ROOT, policy=policy)


def test_default_layout_has_no_internal_collision():
    # Sanity: the frozen v1.0 default layout must never itself collide.
    build_organize_plan(_item(), "FC2-1234567", _metadata(), LIBRARY_ROOT)


# --- 24-25: overwrite policy frozen / no automatic suffixing ------------


def test_overwrite_policy_is_frozen_never_and_not_a_caller_knob():
    assert not hasattr(OutputPolicy(), "overwrite")
    assert not hasattr(OutputPolicy(), "overwrite_policy")
    import inspect

    sig = inspect.signature(build_organize_plan)
    assert "overwrite" not in sig.parameters


def test_no_automatic_suffixing_on_repeated_calls_same_target():
    item_a = _item(index=0, source_path=r"C:\downloads\a\movie.mp4", relative_path="a/movie.mp4")
    item_b = _item(index=1, source_path=r"C:\downloads\b\movie.mp4", relative_path="b/movie.mp4")
    plan_a = build_organize_plan(item_a, "FC2-1234567", _metadata(), LIBRARY_ROOT)
    plan_b = build_organize_plan(item_b, "FC2-1234567", _metadata(), LIBRARY_ROOT)
    # No "(1)"/"_2"/"-copy" suffix invented -- both plans name the exact
    # same target; resolving that collision is explicitly out of scope here.
    assert plan_a.target_media_path == plan_b.target_media_path
    assert "(1)" not in plan_b.target_media_path.absolute_path
    assert "_2" not in plan_b.target_media_path.absolute_path
    assert "copy" not in plan_b.target_media_path.absolute_path.lower()


# --- 26-27: title / Unicode metadata never alter default target path ----


def test_title_does_not_alter_default_target_path():
    plan_a = build_organize_plan(_item(), "FC2-1234567", _metadata(title="Alpha Title"), LIBRARY_ROOT)
    plan_b = build_organize_plan(_item(), "FC2-1234567", _metadata(title="A Totally Different Title"), LIBRARY_ROOT)
    assert plan_a.target_directory == plan_b.target_directory
    assert plan_a.target_media_path == plan_b.target_media_path
    assert "Alpha" not in plan_a.target_media_path.absolute_path
    assert "Title" not in plan_a.target_media_path.absolute_path


def test_unicode_metadata_does_not_alter_default_target_path():
    plan = build_organize_plan(
        _item(), "FC2-1234567", _metadata(title="\u65e5\u672c\u8a9e\u30bf\u30a4\u30c8\u30eb \ud83d\ude00"), LIBRARY_ROOT
    )
    assert plan.target_directory.absolute_path == LIBRARY_ROOT + r"\FC2-1234567"
    assert plan.target_media_path.absolute_path == LIBRARY_ROOT + r"\FC2-1234567\FC2-1234567.mp4"


# --- operations model / ordering ----------------------------------------


def test_operations_are_ordered_deterministically():
    plan = build_organize_plan(_item(), "FC2-1234567", _metadata(), LIBRARY_ROOT)
    kinds = [op.kind for op in plan.operations]
    assert kinds == [
        PlannedOperationKind.CREATE_DIRECTORY,
        PlannedOperationKind.MOVE_MEDIA,
        PlannedOperationKind.MATERIALIZE_NFO,
        PlannedOperationKind.MATERIALIZE_POSTER,
        PlannedOperationKind.MATERIALIZE_FANART,
        PlannedOperationKind.MATERIALIZE_THUMB,
        PlannedOperationKind.ENSURE_EXTRAFANART_DIRECTORY,
    ]


def test_move_media_operation_carries_source_identity():
    item = _item()
    plan = build_organize_plan(item, "FC2-1234567", _metadata(), LIBRARY_ROOT)
    move_ops = [op for op in plan.operations if op.kind is PlannedOperationKind.MOVE_MEDIA]
    assert len(move_ops) == 1
    assert move_ops[0].source.absolute_path == item.source_path
    assert move_ops[0].target == plan.target_media_path


def test_repeated_calls_produce_identical_operations_ordering():
    item = _item()
    metadata = _metadata()
    plan_a = build_organize_plan(item, "FC2-1234567", metadata, LIBRARY_ROOT)
    plan_b = build_organize_plan(item, "FC2-1234567", metadata, LIBRARY_ROOT)
    assert plan_a.operations == plan_b.operations


# --- source identity carried through --------------------------------------


def test_source_identity_fields_carried_through_unchanged():
    item = _item(index=7, source_path=r"C:\downloads\random-name.MP4", relative_path="random-name.MP4",
                 extension=".mp4", size=999)
    plan = build_organize_plan(item, "FC2-1234567", _metadata(), LIBRARY_ROOT)
    assert plan.source_path == item.source_path
    assert plan.source_relative_path == item.relative_path
    assert plan.source_extension == item.extension
    assert plan.source_index == item.index
    assert plan.source_size == item.size


# --- invalid media item / policy ----------------------------------------


def test_non_discovered_media_item_rejected():
    with pytest.raises(OrganizePlanInputError):
        build_organize_plan("not-an-item", "FC2-1234567", _metadata(), LIBRARY_ROOT)  # type: ignore[arg-type]


def test_invalid_policy_type_rejected():
    with pytest.raises(InvalidOutputPolicyError):
        build_organize_plan(_item(), "FC2-1234567", _metadata(), LIBRARY_ROOT, policy="not-a-policy")  # type: ignore[arg-type]


def test_none_policy_uses_default_layout():
    plan = build_organize_plan(_item(), "FC2-1234567", _metadata(), LIBRARY_ROOT, policy=None)
    assert plan.poster_path.absolute_path.endswith("poster.jpg")


# --- return type is immutable -------------------------------------------


def test_returned_plan_is_frozen():
    plan = build_organize_plan(_item(), "FC2-1234567", _metadata(), LIBRARY_ROOT)
    with pytest.raises(dataclasses.FrozenInstanceError):
        plan.canonical_number = "FC2-7654321"  # type: ignore[misc]
