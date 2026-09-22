"""Tests for the centralized safety/containment helpers in
``fc2_organizer.planning.paths`` (contract section 13, 16; test matrix
items 19-23).
"""

from __future__ import annotations

import os

import pytest

from fc2_organizer.planning.errors import UnsafeTargetComponentError
from fc2_organizer.planning.paths import (
    basenames_collide,
    is_contained_within,
    is_fully_qualified_absolute_root,
    validate_path_component,
)


class TestValidatePathComponentAccepts:
    @pytest.mark.parametrize(
        "value",
        ["FC2-1234567", "poster.jpg", "fanart.jpg", "thumb.jpg", "extrafanart", "FC2-1234567.nfo"],
    )
    def test_normal_components_accepted(self, value):
        assert validate_path_component(value, label="x") == value

    def test_unicode_component_accepted(self):
        # No title-derived component reaches this in v1.0, but the
        # sanitization boundary itself must not choke on ordinary Unicode.
        assert validate_path_component("poster_\u6d77\u62a5.jpg", label="x") == "poster_\u6d77\u62a5.jpg"


class TestValidatePathComponentRejectsIllegalChars:
    @pytest.mark.parametrize("bad_char", list('<>:"/\\|?*'))
    def test_windows_illegal_character_rejected(self, bad_char):
        with pytest.raises(UnsafeTargetComponentError):
            validate_path_component(f"name{bad_char}part", label="x")

    def test_ascii_control_char_rejected(self):
        with pytest.raises(UnsafeTargetComponentError):
            validate_path_component("name\x01part", label="x")

    def test_null_byte_rejected(self):
        with pytest.raises(UnsafeTargetComponentError):
            validate_path_component("name\x00part", label="x")


class TestValidatePathComponentRejectsTrailing:
    def test_trailing_dot_rejected(self):
        with pytest.raises(UnsafeTargetComponentError):
            validate_path_component("poster.", label="x")

    def test_trailing_space_rejected(self):
        with pytest.raises(UnsafeTargetComponentError):
            validate_path_component("poster ", label="x")


class TestValidatePathComponentRejectsReservedNames:
    @pytest.mark.parametrize(
        "name",
        [
            "CON", "con", "Con",
            "PRN", "AUX", "NUL",
            "COM1", "com1", "COM9",
            "LPT1", "lpt1", "LPT9",
        ],
    )
    def test_bare_reserved_name_rejected(self, name):
        with pytest.raises(UnsafeTargetComponentError):
            validate_path_component(name, label="x")

    @pytest.mark.parametrize("name", ["CON.txt", "con.jpg", "COM1.nfo", "LPT9.mp4"])
    def test_reserved_name_with_extension_rejected(self, name):
        with pytest.raises(UnsafeTargetComponentError):
            validate_path_component(name, label="x")

    @pytest.mark.parametrize("name", ["CONFIG.txt", "CONSOLE", "COM10", "LPT10", "AUXILIARY"])
    def test_name_merely_starting_with_reserved_prefix_accepted(self, name):
        assert validate_path_component(name, label="x") == name


class TestValidatePathComponentRejectsStructural:
    def test_empty_rejected(self):
        with pytest.raises(UnsafeTargetComponentError):
            validate_path_component("", label="x")

    def test_non_str_rejected(self):
        with pytest.raises(UnsafeTargetComponentError):
            validate_path_component(123, label="x")  # type: ignore[arg-type]

    @pytest.mark.parametrize("value", [".", ".."])
    def test_dot_and_dotdot_rejected(self, value):
        with pytest.raises(UnsafeTargetComponentError):
            validate_path_component(value, label="x")

    def test_traversal_like_component_rejected(self):
        with pytest.raises(UnsafeTargetComponentError):
            validate_path_component("..\\escape", label="x")

    def test_embedded_separator_rejected(self):
        with pytest.raises(UnsafeTargetComponentError):
            validate_path_component("sub/dir", label="x")


class TestBasenamesCollide:
    def test_identical_names_collide(self):
        assert basenames_collide("poster.jpg", "poster.jpg")

    def test_case_variants_collide_windows_semantics(self):
        assert basenames_collide("Poster.jpg", "poster.jpg")
        assert basenames_collide("POSTER.JPG", "poster.jpg")

    def test_different_names_do_not_collide(self):
        assert not basenames_collide("poster.jpg", "fanart.jpg")


class TestIsContainedWithin:
    def test_direct_child_is_contained(self):
        assert is_contained_within(r"C:\library\FC2-1234567", r"C:\library")

    def test_nested_grandchild_is_contained(self):
        assert is_contained_within(r"C:\library\FC2-1234567\extrafanart\1.jpg", r"C:\library")

    def test_root_itself_is_not_contained(self):
        assert not is_contained_within(r"C:\library", r"C:\library")

    def test_sibling_directory_is_not_contained(self):
        assert not is_contained_within(r"C:\other\FC2-1234567", r"C:\library")

    def test_prefix_collision_without_separator_boundary_is_not_contained(self):
        # "C:\library2" is not "under" "C:\library" even though it shares a
        # string prefix -- containment must be segment-based, not substring.
        assert not is_contained_within(r"C:\library2\FC2-1234567", r"C:\library")

    def test_case_insensitive_containment(self):
        assert is_contained_within(r"C:\LIBRARY\FC2-1234567", r"c:\library")

    # -- P4-C2-GOV-02 regression coverage ---------------------------------
    #
    # A bare drive root ("C:\") or UNC share root ("\\server\share\")
    # normalizes to a string *ending* in the separator; the old
    # ``os.path.normpath(...).split(os.sep)`` implementation produced a
    # spurious trailing empty segment for that case, inflating the root's
    # part count so that an actual child compared as "not contained." These
    # are Windows-native path forms (drive letters, UNC), so they are only
    # meaningful -- and only run -- on a Windows host; on POSIX, ``Path``
    # would not parse a backslash as a separator at all, so this would not
    # be testing what it claims to (contract section 10: "不得拿 foreign-OS
    # path string冒充当前 OS-native runtime path").

    @pytest.mark.skipif(os.name != "nt", reason="drive-root path forms are Windows-native")
    def test_drive_root_contains_its_direct_child(self):
        assert is_contained_within(r"C:\FC2-1234567", r"C:\\")

    @pytest.mark.skipif(os.name != "nt", reason="drive-root path forms are Windows-native")
    def test_drive_root_contains_its_grandchild(self):
        assert is_contained_within(r"C:\FC2-1234567\poster.jpg", r"C:\\")

    @pytest.mark.skipif(os.name != "nt", reason="drive-root path forms are Windows-native")
    def test_drive_root_without_trailing_separator_contains_its_child(self):
        # "C:" alone is drive-relative, not a root; "C:\" (with the
        # separator) is the actual bare drive root, spelled either with or
        # without the trailing backslash in common usage.
        assert is_contained_within(r"C:\FC2-1234567", "C:\\")

    @pytest.mark.skipif(os.name != "nt", reason="drive-root path forms are Windows-native")
    def test_library_child_not_wrongly_excluded_from_its_own_drive_root(self):
        # The exact P4-C2-GOV-02 reproduction: a real child of "C:\" must
        # not be judged "not contained" merely because the root string ends
        # in a separator.
        assert is_contained_within(r"C:\library-child", r"C:\\")

    @pytest.mark.skipif(os.name != "nt", reason="drive-root path forms are Windows-native")
    def test_different_drive_is_not_contained(self):
        assert not is_contained_within(r"D:\FC2-1234567", r"C:\\")

    @pytest.mark.skipif(os.name != "nt", reason="UNC path forms are Windows-native")
    def test_unc_share_root_with_trailing_separator_contains_its_child(self):
        assert is_contained_within(r"\\server\share\FC2-1234567", r"\\server\share\\")

    @pytest.mark.skipif(os.name != "nt", reason="UNC path forms are Windows-native")
    def test_unc_share_root_without_trailing_separator_contains_its_child(self):
        assert is_contained_within(r"\\server\share\FC2-1234567", r"\\server\share")

    @pytest.mark.skipif(os.name != "nt", reason="UNC path forms are Windows-native")
    def test_different_unc_share_is_not_contained(self):
        assert not is_contained_within(r"\\server\other\FC2-1234567", r"\\server\share\\")

    @pytest.mark.skipif(os.name != "nt", reason="UNC path forms are Windows-native")
    def test_unc_and_local_drive_do_not_cross_contain(self):
        assert not is_contained_within(r"\\server\share\FC2-1234567", r"C:\\")
        assert not is_contained_within(r"C:\FC2-1234567", r"\\server\share\\")

    def test_no_string_startswith_false_positive_on_drive_root(self):
        # Regression guard for the "dangerous string.startswith(root)"
        # anti-pattern the brief explicitly forbids: naive prefix matching
        # would treat "C:\library2" as contained under "C:\library" purely
        # because one string starts with the other.
        assert not is_contained_within(r"C:\library2\FC2-1234567", r"C:\library\\")


class TestIsFullyQualifiedAbsoluteRoot:
    """P4-C2-GOV-03: ``library_root`` must be an unambiguous, fully-qualified
    absolute path. Each test is gated to the platform whose path semantics
    it actually exercises (contract section 10) -- a Windows drive/UNC form
    is not meaningful on POSIX (backslash is just an ordinary filename
    character there), and vice versa."""

    # -- Windows: accepted -------------------------------------------------

    @pytest.mark.skipif(os.name != "nt", reason="Windows drive-qualified path")
    def test_windows_drive_qualified_backslash_accepted(self):
        assert is_fully_qualified_absolute_root(r"C:\library")

    @pytest.mark.skipif(os.name != "nt", reason="Windows drive-qualified path")
    def test_windows_drive_qualified_forward_slash_accepted(self):
        assert is_fully_qualified_absolute_root("C:/library")

    @pytest.mark.skipif(os.name != "nt", reason="Windows bare drive root")
    def test_windows_bare_drive_root_accepted(self):
        assert is_fully_qualified_absolute_root("C:\\")

    @pytest.mark.skipif(os.name != "nt", reason="Windows UNC share")
    def test_windows_unc_share_with_trailing_slash_accepted(self):
        assert is_fully_qualified_absolute_root(r"\\server\share\library")

    @pytest.mark.skipif(os.name != "nt", reason="Windows UNC share")
    def test_windows_bare_unc_share_root_accepted(self):
        assert is_fully_qualified_absolute_root(r"\\server\share")

    # -- Windows: rejected ---------------------------------------------------

    @pytest.mark.skipif(os.name != "nt", reason="Windows relative path")
    def test_windows_plain_relative_name_rejected(self):
        assert not is_fully_qualified_absolute_root("library")

    @pytest.mark.skipif(os.name != "nt", reason="Windows dot-relative path")
    def test_windows_dot_relative_rejected(self):
        assert not is_fully_qualified_absolute_root(r".\library")

    @pytest.mark.skipif(os.name != "nt", reason="Windows dot-dot-relative path")
    def test_windows_dotdot_relative_rejected(self):
        assert not is_fully_qualified_absolute_root(r"..\library")

    @pytest.mark.skipif(os.name != "nt", reason="Windows drive-relative path")
    def test_windows_drive_relative_rejected(self):
        assert not is_fully_qualified_absolute_root("C:library")

    @pytest.mark.skipif(os.name != "nt", reason="Windows rooted-but-driveless path")
    def test_windows_rooted_but_driveless_backslash_rejected(self):
        assert not is_fully_qualified_absolute_root(r"\library")

    @pytest.mark.skipif(os.name != "nt", reason="Windows rooted-but-driveless path")
    def test_windows_rooted_but_driveless_forward_slash_rejected(self):
        assert not is_fully_qualified_absolute_root("/library")

    # -- POSIX ---------------------------------------------------------------

    @pytest.mark.skipif(os.name == "nt", reason="POSIX absolute path")
    def test_posix_absolute_path_accepted(self):
        assert is_fully_qualified_absolute_root("/library")

    @pytest.mark.skipif(os.name == "nt", reason="POSIX relative path")
    def test_posix_relative_path_rejected(self):
        assert not is_fully_qualified_absolute_root("library")

    @pytest.mark.skipif(os.name == "nt", reason="POSIX dot-relative path")
    def test_posix_dot_relative_rejected(self):
        assert not is_fully_qualified_absolute_root("./library")
