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

R2 note (P4-C1-R1-01): the R1 fix above used ``os.path.abspath``, which
lexically collapses a ``..`` segment *before* any filesystem access --
wrong when a symlink/junction sits before the ``..`` (see
``test_discovery_symlink_dotdot_identity.py`` for the real-filesystem
identity proof). The three ``test_coerce_root_*`` tests below are the
platform-independent, no-filesystem-required regression guard for that
specific defect: they assert ``_coerce_root`` never folds ``..`` away
itself, regardless of whether a real symlink/junction is available on the
host running the tests.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from fc2_organizer.discovery import DiscoveredMediaItem, DiscoveryContractError, discover_media
from fc2_organizer.discovery import scanner


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


def test_relative_root_with_no_symlinks_present_yields_zero_issues(relative_root_tree):
    """Absolutization must not itself manufacture spurious DiscoveryIssues
    on an ordinary tree that contains no symlink/junction at all. This does
    **not** exercise symlink/junction traversal policy (that requires an
    actual symlink/junction on disk -- see
    ``test_discovery_symlink_dotdot_identity.py`` for that, per the R2
    review note that a same-named R1 test overclaimed what it tested)."""
    result = discover_media(relative_root_tree)

    assert result.issues == ()


def test_coerce_root_does_not_lexically_collapse_dotdot_in_relative_root(monkeypatch):
    """Core P4-C1-R1-01 regression guard, independent of any real
    filesystem object: ``_coerce_root`` must only *prefix* the current
    working directory onto a relative root -- it must never fold a ``..``
    segment away itself (that is exactly what ``os.path.abspath`` did in
    R1, and exactly what let a symlink/junction target get silently
    substituted). A ``.`` segment may still be dropped by plain ``pathlib``
    joining -- that is always lexically safe (see the next test)."""
    monkeypatch.setattr(scanner.os, "getcwd", lambda: str(Path("C:/base") if os.name == "nt" else Path("/base")))

    result = scanner._coerce_root(os.path.join("link", "..", "mydir"))

    expected = Path("C:/base" if os.name == "nt" else "/base") / "link" / ".." / "mydir"
    assert result == expected
    assert ".." in result.parts


def test_coerce_root_does_not_lexically_collapse_dotdot_in_absolute_root(monkeypatch):
    """An already-absolute root must be returned completely untouched --
    including any ``..`` segment it contains -- never run through
    ``abspath``/``normpath``/``resolve`` (all of which would silently fold
    it)."""
    base = Path("C:/base") if os.name == "nt" else Path("/base")
    absolute_with_dotdot = base / "link" / ".." / "mydir"

    result = scanner._coerce_root(str(absolute_with_dotdot))

    assert result == absolute_with_dotdot
    assert ".." in result.parts


def test_coerce_root_still_absolutizes_a_plain_relative_root(monkeypatch):
    fake_cwd = Path("C:/base") if os.name == "nt" else Path("/base")
    monkeypatch.setattr(scanner.os, "getcwd", lambda: str(fake_cwd))

    result = scanner._coerce_root("mydir")

    assert result == fake_cwd / "mydir"
    assert result.is_absolute()


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
