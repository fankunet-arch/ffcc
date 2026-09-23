"""P4-C6 substep 1: pure target-path validation (both OS flavors) and the result model."""

from __future__ import annotations

import dataclasses
import hashlib

import pytest

from fc2_organizer.materialization import (
    InvalidTargetPathError,
    MaterializationModelError,
    MaterializedArtifact,
    TargetPathRejectionReason as R,
)
from fc2_organizer.materialization.atomic import _validate_target_path


@pytest.mark.parametrize(
    ("path", "parent"),
    [
        ("C:\\lib\\FC2-1\\poster.jpg", "C:\\lib\\FC2-1"),
        ("C:/lib/FC2-1/poster.jpg", "C:/lib/FC2-1"),
        ("D:\\poster.jpg", "D:\\"),
        ("\\\\server\\share\\FC2-1\\FC2-1.nfo", "\\\\server\\share\\FC2-1"),
        ("C:\\lib\\CONFIG.txt", "C:\\lib"),
        ("C:\\lib\\.hidden", "C:\\lib"),
    ],
)
def test_windows_accepts_fully_qualified_paths(path, parent):
    assert _validate_target_path(path, windows=True) == parent


@pytest.mark.parametrize(
    ("path", "reason"),
    [
        ("", R.EMPTY),
        ("C:\\lib\\a\x00.jpg", R.NUL_CHARACTER),
        ("poster.jpg", R.NOT_ABSOLUTE),
        ("lib\\poster.jpg", R.NOT_ABSOLUTE),
        (".\\poster.jpg", R.NOT_ABSOLUTE),
        ("\\lib\\poster.jpg", R.NOT_ABSOLUTE),  # rooted but driveless: ambiguous
        ("/lib/poster.jpg", R.NOT_ABSOLUTE),
        ("C:poster.jpg", R.NOT_ABSOLUTE),  # drive-relative
        ("~\\poster.jpg", R.NOT_ABSOLUTE),
        ("%USERPROFILE%\\poster.jpg", R.NOT_ABSOLUTE),
        ("\\\\?\\C:\\lib\\poster.jpg", R.DEVICE_NAMESPACE),
        ("\\\\.\\NUL", R.DEVICE_NAMESPACE),
        ("C:\\lib\\", R.NO_BASENAME),
        ("C:\\lib\\..\\poster.jpg", R.DOT_SEGMENT),
        ("C:\\lib\\.\\poster.jpg", R.DOT_SEGMENT),
        ("C:\\lib\\..", R.DOT_SEGMENT),
        ("C:\\lib\\poster.jpg:stream", R.ILLEGAL_CHARACTER),  # NTFS alternate data stream
        ("C:\\lib\\po?ter.jpg", R.ILLEGAL_CHARACTER),
        ("C:\\lib\\a\tb.jpg", R.ILLEGAL_CHARACTER),
        ("C:\\lib\\poster.jpg.", R.TRAILING_DOT_OR_SPACE),
        ("C:\\lib\\poster.jpg ", R.TRAILING_DOT_OR_SPACE),
        ("C:\\lib\\CON", R.RESERVED_NAME),
        ("C:\\lib\\nul.jpg", R.RESERVED_NAME),
        ("C:\\COM1\\poster.jpg", R.RESERVED_NAME),
    ],
)
def test_windows_rejections(path, reason):
    with pytest.raises(InvalidTargetPathError) as info:
        _validate_target_path(path, windows=True)
    assert info.value.reason is reason
    if path:
        assert path not in str(info.value)


@pytest.mark.parametrize(
    ("path", "parent"),
    [("/lib/FC2-1/poster.jpg", "/lib/FC2-1"), ("/poster.jpg", "/"), ("/lib/a:b?.jpg", "/lib"),
     ("/lib/poster.jpg.", "/lib"), ("/lib/CON", "/lib")],
)
def test_posix_accepts_absolute_paths(path, parent):
    assert _validate_target_path(path, windows=False) == parent


@pytest.mark.parametrize(
    ("path", "reason"),
    [
        ("", R.EMPTY),
        ("/lib/a\x00", R.NUL_CHARACTER),
        ("poster.jpg", R.NOT_ABSOLUTE),
        ("~/poster.jpg", R.NOT_ABSOLUTE),
        ("$HOME/poster.jpg", R.NOT_ABSOLUTE),
        ("C:\\lib\\poster.jpg", R.NOT_ABSOLUTE),
        ("/lib/", R.NO_BASENAME),
        ("/lib/../poster.jpg", R.DOT_SEGMENT),
        ("/lib/.", R.DOT_SEGMENT),
    ],
)
def test_posix_rejections(path, reason):
    with pytest.raises(InvalidTargetPathError) as info:
        _validate_target_path(path, windows=False)
    assert info.value.reason is reason


# --------------------------------------------------------------------------- MaterializedArtifact


def _artifact(**overrides):
    fields = {"target_path": "C:\\lib\\a.jpg", "size_bytes": 1, "sha256": hashlib.sha256(b"x").hexdigest()}
    fields.update(overrides)
    return MaterializedArtifact(**fields)


def test_artifact_is_frozen_slotted_and_minimal():
    a = _artifact()
    assert [f.name for f in dataclasses.fields(MaterializedArtifact)] == ["target_path", "size_bytes", "sha256"]
    assert not hasattr(a, "__dict__")
    with pytest.raises(dataclasses.FrozenInstanceError):
        a.size_bytes = 2  # type: ignore[misc]


@pytest.mark.parametrize(
    "overrides",
    [
        {"target_path": ""},
        {"target_path": b"x"},
        {"target_path": type("S", (str,), {})("x")},
        {"size_bytes": -1},
        {"size_bytes": True},
        {"size_bytes": 1.0},
        {"sha256": "A" * 64},
        {"sha256": "a" * 63},
        {"sha256": b"a" * 64},
        {"sha256": "g" * 64},
    ],
)
def test_artifact_rejects_invalid_fields(overrides):
    with pytest.raises(MaterializationModelError):
        _artifact(**overrides)
