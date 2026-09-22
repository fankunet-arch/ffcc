"""Symlink / junction / reparse-point safety (contract section 11) --
test matrix items 19-21.

Real directory symlinks require a Windows privilege (``SeCreateSymbolicLinkPrivilege``
/ Developer Mode) that is not guaranteed to be available on the host running
these tests; a real NTFS junction, by contrast, needs no elevation
(``_winapi.CreateJunction``). Tests that cannot obtain the required privilege
``pytest.skip`` with the concrete reason instead of silently passing or being
faked -- see ``docs/review/P4_C1_HANDOFF.md`` "Platform-Specific Tests Not Run".
"""

from __future__ import annotations

import os

import pytest

from fc2_organizer.discovery import DiscoveryIssueKind, discover_media


def _try_make_symlink(target: str, link: str, *, target_is_directory: bool) -> None:
    try:
        os.symlink(target, link, target_is_directory=target_is_directory)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"directory/file symlink could not be created on this host: {exc!r}")


def _try_make_junction(target: str, link: str) -> None:
    if os.name != "nt":
        pytest.skip("junctions are a Windows-only (NTFS) concept")
    import _winapi

    _winapi.CreateJunction(target, link)


def test_symlink_directory_is_not_recursed_into(tmp_path):
    target = tmp_path / "target"
    target.mkdir()
    (target / "inside.mp4").write_text("x")
    link = tmp_path / "link"
    _try_make_symlink(str(target), str(link), target_is_directory=True)

    result = discover_media(tmp_path)

    relative_paths = {item.relative_path for item in result.items}
    assert "target/inside.mp4" in relative_paths
    assert not any(rp.startswith("link/") for rp in relative_paths)
    assert any(issue.kind is DiscoveryIssueKind.SYMLINK_SKIPPED for issue in result.issues)


def test_symlink_file_is_not_treated_as_a_normal_media_source(tmp_path):
    real = tmp_path / "real.mp4"
    real.write_text("x")
    link = tmp_path / "link.mp4"
    _try_make_symlink(str(real), str(link), target_is_directory=False)

    result = discover_media(tmp_path)

    relative_paths = {item.relative_path for item in result.items}
    assert "real.mp4" in relative_paths
    assert "link.mp4" not in relative_paths
    assert any(issue.kind is DiscoveryIssueKind.SYMLINK_SKIPPED for issue in result.issues)


def test_symlink_loop_does_not_hang(tmp_path):
    looped = tmp_path / "looped"
    looped.mkdir()
    self_link = looped / "self"
    _try_make_symlink(str(looped), str(self_link), target_is_directory=True)

    result = discover_media(tmp_path)  # must return, not hang

    assert any(issue.kind is DiscoveryIssueKind.SYMLINK_SKIPPED for issue in result.issues)


def test_junction_directory_is_not_recursed_into(tmp_path):
    target = tmp_path / "target"
    target.mkdir()
    (target / "inside.mp4").write_text("x")
    link = tmp_path / "junction_link"
    _try_make_junction(str(target), str(link))

    result = discover_media(tmp_path)

    relative_paths = {item.relative_path for item in result.items}
    assert "target/inside.mp4" in relative_paths
    assert not any(rp.startswith("junction_link") for rp in relative_paths)
    assert any(issue.kind is DiscoveryIssueKind.REPARSE_POINT_SKIPPED for issue in result.issues)


def test_junction_loop_does_not_hang(tmp_path):
    looped = tmp_path / "looped"
    looped.mkdir()
    self_link = looped / "self_junction"
    _try_make_junction(str(looped), str(self_link))

    result = discover_media(tmp_path)  # must return, not hang

    assert any(issue.kind is DiscoveryIssueKind.REPARSE_POINT_SKIPPED for issue in result.issues)


def test_junction_pointing_outside_root_is_not_followed(tmp_path):
    outside = tmp_path.parent / f"outside-{tmp_path.name}"
    outside.mkdir()
    (outside / "secret.mp4").write_text("x")
    try:
        root = tmp_path / "root"
        root.mkdir()
        link = root / "escape"
        _try_make_junction(str(outside), str(link))

        result = discover_media(root)

        assert result.items == ()
        assert any(issue.kind is DiscoveryIssueKind.REPARSE_POINT_SKIPPED for issue in result.issues)
    finally:
        import shutil

        shutil.rmtree(outside, ignore_errors=True)
