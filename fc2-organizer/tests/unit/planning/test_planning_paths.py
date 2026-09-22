"""Tests for the centralized safety/containment helpers in
``fc2_organizer.planning.paths`` (contract section 13, 16; test matrix
items 19-23).
"""

from __future__ import annotations

import pytest

from fc2_organizer.planning.errors import UnsafeTargetComponentError
from fc2_organizer.planning.paths import basenames_collide, is_contained_within, validate_path_component


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
