"""Regression tests for P4-C1-R-01 (HIGH / BLOCKING, closed in R1).

Finding: ``discover_media("mydir")`` with a **relative** root produced a
``DiscoveredMediaItem.source_path`` that was itself still relative,
violating the frozen contract ("source_path must be absolute" --
``docs/specifications/PHASE4_DISCOVERY_CONTRACT.md`` section 3). The
original test suite never caught this because every test used
``tmp_path``, which is already absolute.

These tests exercise a genuinely relative root by changing the process
working directory to a temporary parent and passing a bare relative
directory name, exactly like the reviewer's reproduction
(``mkdir mydir; create mydir/a.mp4; discover_media("mydir")``).
"""

from __future__ import annotations

import os

import pytest

from fc2_organizer.discovery import DiscoveredMediaItem, DiscoveryContractError, discover_media


@pytest.fixture
def relative_root_tree(tmp_path, monkeypatch):
    """Sets cwd to a fresh temp parent and returns the *relative* dirname
    of a subdirectory containing one media file -- ``tmp_path`` itself is
    never passed to ``discover_media`` here, only the bare relative name."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "mydir").mkdir()
    (tmp_path / "mydir" / "a.mp4").write_bytes(b"hello")
    return "mydir"


def test_relative_root_yields_absolute_source_path(relative_root_tree):
    result = discover_media(relative_root_tree)

    assert len(result.items) == 1
    item = result.items[0]
    assert os.path.isabs(item.source_path) is True


def test_relative_root_yields_correct_relative_path(relative_root_tree):
    result = discover_media(relative_root_tree)

    assert result.items[0].relative_path == "a.mp4"


def test_relative_root_source_path_identifies_the_real_file(relative_root_tree):
    result = discover_media(relative_root_tree)

    item = result.items[0]
    assert os.path.isfile(item.source_path)
    assert item.size == 5  # b"hello"
    with open(item.source_path, "rb") as f:
        assert f.read() == b"hello"


def test_relative_root_result_root_is_also_absolute(relative_root_tree):
    result = discover_media(relative_root_tree)

    assert os.path.isabs(result.root) is True


def test_dot_prefixed_relative_root_yields_absolute_source_path(relative_root_tree):
    result = discover_media(os.path.join(".", relative_root_tree))

    assert os.path.isabs(result.items[0].source_path) is True
    assert result.items[0].relative_path == "a.mp4"


def test_relative_root_with_dotdot_segment_yields_absolute_source_path(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "sibling").mkdir()
    (tmp_path / "mydir").mkdir()
    (tmp_path / "mydir" / "a.mp4").write_bytes(b"x")

    result = discover_media(os.path.join("sibling", "..", "mydir"))

    item = result.items[0]
    assert os.path.isabs(item.source_path) is True
    assert item.relative_path == "a.mp4"
    assert os.path.isfile(item.source_path)


def test_relative_root_does_not_change_symlink_or_junction_semantics(relative_root_tree):
    """R1 must not touch symlink/junction policy while fixing absolutization
    -- a plain relative-root scan with no symlinks present must still yield
    zero issues, exactly as before."""
    result = discover_media(relative_root_tree)

    assert result.issues == ()


def test_discovered_media_item_rejects_relative_source_path():
    with pytest.raises(DiscoveryContractError):
        DiscoveredMediaItem(
            index=0, source_path="relative/a.mp4", relative_path="a.mp4", extension=".mp4", size=1
        )


def test_discovered_media_item_accepts_absolute_source_path(tmp_path):
    item = DiscoveredMediaItem(
        index=0, source_path=str(tmp_path / "a.mp4"), relative_path="a.mp4", extension=".mp4", size=1
    )
    assert os.path.isabs(item.source_path)


def test_discovered_media_item_rejects_windows_style_relative_source_path():
    with pytest.raises(DiscoveryContractError):
        DiscoveredMediaItem(
            index=0, source_path="mydir\\a.mp4", relative_path="a.mp4", extension=".mp4", size=1
        )
