"""P4-C7 S1: lexical path rules (contract section 26.3), simulated for Windows and POSIX on any host."""

from __future__ import annotations

import pytest

from fc2_organizer.execution.errors import PathRejectionReason as R
from fc2_organizer.execution.paths import (
    check_absolute_path,
    check_created_component,
    is_under,
    path_components,
    same_entry_name,
)
from fc2_organizer.materialization import InvalidTargetPathError
from fc2_organizer.materialization.atomic import _validate_target_path

# --------------------------------------------------------------------------- Windows rules


@pytest.mark.parametrize("path", [
    r"C:\lib\FC2-1234567\poster.jpg", "C:/lib/x.mp4", r"\\server\share\lib\x.nfo", "//server/share/x",
    r"D:\ライブラリ\FC2-1\FC2-1.mp4", r"C:\a b\c.d\e",
])
def test_windows_accepts_fully_qualified_files(path):
    assert check_absolute_path(path, windows=True) is None


@pytest.mark.parametrize(("path", "reason"), [
    ("", R.EMPTY),
    ("C:\\a\x00b", R.NUL_CHARACTER),
    (r"lib\x.mp4", R.NOT_ABSOLUTE),
    (r"\lib\x.mp4", R.NOT_ABSOLUTE),
    ("/lib/x.mp4", R.NOT_ABSOLUTE),
    (r"C:lib\x.mp4", R.NOT_ABSOLUTE),
    (r"1:\lib\x.mp4", R.NOT_ABSOLUTE),
    (r"\\server", R.NOT_ABSOLUTE),
    (r"\\server\share", R.NOT_ABSOLUTE),
    (r"\\?\C:\lib\x", R.DEVICE_NAMESPACE),
    (r"\\.\C:\lib\x", R.DEVICE_NAMESPACE),
    ("//?/C:/x", R.DEVICE_NAMESPACE),
    ("C:\\lib\\", R.NO_BASENAME),
    (r"C:\lib\..\x.mp4", R.DOT_SEGMENT),
    (r"C:\lib\.\x.mp4", R.DOT_SEGMENT),
    (r"C:\lib\a:b", R.ILLEGAL_CHARACTER),
    (r"C:\lib\a*b", R.ILLEGAL_CHARACTER),
    ("C:\\lib\\a\tb", R.ILLEGAL_CHARACTER),
    (r"C:\lib\name.", R.TRAILING_DOT_OR_SPACE),
    ("C:\\lib\\name ", R.TRAILING_DOT_OR_SPACE),
    (r"C:\lib\CON", R.RESERVED_NAME),
    (r"C:\lib\nul.txt", R.RESERVED_NAME),
    (r"C:\COM1\x", R.RESERVED_NAME),
])
def test_windows_rejections(path, reason):
    assert check_absolute_path(path, windows=True) is reason


@pytest.mark.parametrize(("root", "ok"), [
    ("C:\\", True), (r"C:\lib", True), ("C:\\lib\\", True), (r"\\server\share", True),
    ("\\\\server\\share\\", True), (r"\\server", False), ("\\\\server\\", False), (r"\lib", False),
    ("C:", False), (r"C:lib", False),
])
def test_windows_library_root_forms(root, ok):
    assert (check_absolute_path(root, directory_root=True, windows=True) is None) is ok


def test_bare_server_without_share_is_always_rejected():
    # P4-C2-R1-02 neutralised at the execution boundary.
    assert check_absolute_path(r"\\server", directory_root=True, windows=True) is R.NOT_ABSOLUTE
    assert check_absolute_path("//server", directory_root=True, windows=True) is R.NOT_ABSOLUTE


# --------------------------------------------------------------------------- POSIX rules


@pytest.mark.parametrize(("path", "reason"), [
    ("/lib/x.mp4", None),
    ("/lib/名前/x:y*z.mp4", None),  # Windows-illegal characters are legal POSIX path characters
    ("lib/x.mp4", R.NOT_ABSOLUTE),
    (r"C:\lib\x.mp4", R.NOT_ABSOLUTE),
    ("/lib/", R.NO_BASENAME),
    ("/", R.NO_BASENAME),
    ("/lib/../x", R.DOT_SEGMENT),
    ("/lib/./x", R.DOT_SEGMENT),
    ("/lib/a\x00", R.NUL_CHARACTER),
])
def test_posix_rules(path, reason):
    assert check_absolute_path(path, windows=False) is reason


def test_posix_library_root_forms():
    assert check_absolute_path("/", directory_root=True, windows=False) is None
    assert check_absolute_path("/lib/", directory_root=True, windows=False) is None
    assert check_absolute_path("lib", directory_root=True, windows=False) is R.NOT_ABSOLUTE


# --------------------------------------------------------------------------- created components


@pytest.mark.parametrize("name", ["FC2-1234567", "FC2-1234567.mp4", "poster.jpg", "extrafanart", "CONFIG.txt",
                                  "COM10.jpg", "ポスター.jpg"])
def test_created_component_accepts(name):
    assert check_created_component(name) is None


@pytest.mark.parametrize(("name", "reason"), [
    ("", R.EMPTY), (".", R.DOT_SEGMENT), ("..", R.DOT_SEGMENT), ("a/b", R.ILLEGAL_CHARACTER),
    ("a\\b", R.ILLEGAL_CHARACTER), ("a:b", R.ILLEGAL_CHARACTER), ("a\x01", R.ILLEGAL_CHARACTER),
    ("name.", R.TRAILING_DOT_OR_SPACE), ("name ", R.TRAILING_DOT_OR_SPACE),
    ("CON", R.RESERVED_NAME), ("con.jpg", R.RESERVED_NAME), ("LPT9.nfo", R.RESERVED_NAME),
    ("COM\u00b9", R.RESERVED_NAME), ("com\u00b2.jpg", R.RESERVED_NAME), ("LPT\u00b3.jpg", R.RESERVED_NAME),
    ("CONIN$", R.RESERVED_NAME), ("conout$.jpg", R.RESERVED_NAME),
])
def test_created_component_rejects_including_extended_reserved_names(name, reason):
    assert check_created_component(name) is reason


def test_extended_reserved_names_are_not_rejected_inside_full_paths_that_p4c7_does_not_create():
    # Base reserved set applies to full paths; the extended set only to created components.
    assert check_absolute_path("C:\\lib\\CONIN$\\x.mp4", windows=True) is None
    assert check_absolute_path(r"C:\lib\CON\x.mp4", windows=True) is R.RESERVED_NAME


# --------------------------------------------------------------------------- comparisons


def test_same_entry_name_and_is_under():
    assert same_entry_name("Poster.JPG", "poster.jpg", windows=True)
    assert not same_entry_name("Poster.JPG", "poster.jpg", windows=False)
    assert is_under(r"C:\Lib\FC2-1\x.mp4", r"c:\lib\fc2-1", windows=True)
    assert not is_under(r"C:\lib\FC2-1", r"C:\lib\FC2-1", windows=True)
    assert not is_under(r"C:\lib\FC2-10\x", r"C:\lib\FC2-1", windows=True)
    assert not is_under(r"D:\lib\FC2-1\x", r"C:\lib\FC2-1", windows=True)
    assert is_under("//server/share/a/b", r"\\SERVER\share\a", windows=True)
    assert is_under("/lib/FC2-1/x", "/lib/FC2-1", windows=False)
    assert not is_under("/lib/fc2-1/x", "/lib/FC2-1", windows=False)
    assert not is_under("relative/x", "/lib", windows=False)
    assert path_components("relative", windows=False) is None
    assert path_components(r"C:\a\\b", windows=True) == ("C:", ["a", "b"])


# --------------------------------------------------------------------------- consistency with P4-C6

_CORPUS = [
    "", "a", "a\x00", "/", "/x", "/x/", "/x/./y", "/x/../y", "/x/y", "x/y", "C:", "C:x", "C:\\", "C:\\x",
    "C:\\x\\", "C:/x", "C:\\x\\..\\y", "C:\\x\\.", "\\x", "/x:y", "C:\\x:y", "C:\\x*", "C:\\x?", 'C:\\x"',
    "C:\\x|y", "C:\\x<y", "C:\\x>y", "C:\\x.", "C:\\x ", "C:\\CON", "C:\\con.txt", "C:\\COM1\\y", "C:\\LPT1",
    "\\\\server", "\\\\server\\", "\\\\server\\share", "\\\\server\\share\\", "\\\\server\\share\\x",
    "//server/share/x", "\\\\?\\C:\\x", "\\\\.\\C:\\x", "//?/C:/x", "//./C:/x", "1:\\x", "C:\\a\\\\b",
    "C:\\x\ty", "C:\\CONIN$", "/x\ty", "/CON", "C:\\ok\\FC2-1234567.mp4",
]


@pytest.mark.parametrize("windows", [True, False])
@pytest.mark.parametrize("path", _CORPUS)
def test_p4c7_rejects_everything_p4c6_rejects(path, windows):
    p4c6_rejects = False
    try:
        _validate_target_path(path, windows=windows)
    except InvalidTargetPathError:
        p4c6_rejects = True
    if p4c6_rejects:
        assert check_absolute_path(path, windows=windows) is not None
