"""Duplicate-safety (contract section 7.4) and deterministic ordering
(section 3.3) -- test matrix items 8-11, 23."""

from __future__ import annotations

from fc2_organizer.discovery import discover_media


def test_same_fc2_number_in_different_directories_yields_two_distinct_items(tmp_path):
    (tmp_path / "A").mkdir()
    (tmp_path / "B").mkdir()
    (tmp_path / "A" / "FC2-1234567.mp4").write_bytes(b"aaaa")
    (tmp_path / "B" / "FC2-1234567.mp4").write_bytes(b"bb")

    result = discover_media(tmp_path)

    assert result.total_items == 2
    paths = {item.source_path for item in result.items}
    assert len(paths) == 2  # never deduplicated by "number"
    by_rel = {item.relative_path: item for item in result.items}
    assert by_rel["A/FC2-1234567.mp4"].size == 4
    assert by_rel["B/FC2-1234567.mp4"].size == 2


def test_same_filename_in_different_directories_yields_two_distinct_items(tmp_path):
    (tmp_path / "X").mkdir()
    (tmp_path / "Y").mkdir()
    (tmp_path / "X" / "movie.mp4").write_text("x")
    (tmp_path / "Y" / "movie.mp4").write_text("x")

    result = discover_media(tmp_path)

    assert result.total_items == 2
    assert {item.relative_path for item in result.items} == {"X/movie.mp4", "Y/movie.mp4"}


def test_exact_once_media_discovery_no_duplicate_paths(tmp_path):
    for i in range(20):
        directory = tmp_path / f"dir{i}"
        directory.mkdir()
        (directory / "movie.mp4").write_text("x")

    result = discover_media(tmp_path)

    source_paths = [item.source_path for item in result.items]
    assert len(source_paths) == len(set(source_paths)) == 20


def test_deterministic_ordering_across_repeated_scans(tmp_path):
    (tmp_path / "b").mkdir()
    (tmp_path / "a").mkdir()
    (tmp_path / "b" / "z.mp4").write_text("x")
    (tmp_path / "b" / "a.mp4").write_text("x")
    (tmp_path / "a" / "m.mp4").write_text("x")
    (tmp_path / "root.mp4").write_text("x")

    first = discover_media(tmp_path)
    second = discover_media(tmp_path)

    assert [item.relative_path for item in first.items] == [item.relative_path for item in second.items]
    assert [item.index for item in first.items] == [item.index for item in second.items]


def test_ordering_is_alphabetical_depth_first_by_entry_name(tmp_path):
    (tmp_path / "b").mkdir()
    (tmp_path / "a").mkdir()
    (tmp_path / "b" / "child.mp4").write_text("x")
    (tmp_path / "a" / "child.mp4").write_text("x")
    (tmp_path / "root.mp4").write_text("x")

    result = discover_media(tmp_path)

    # "a" < "b" < "root.mp4" in ordinal order, and a directory's contents are
    # visited immediately when the directory entry itself is reached.
    assert [item.relative_path for item in result.items] == ["a/child.mp4", "b/child.mp4", "root.mp4"]


def test_ordering_does_not_depend_on_creation_order(tmp_path):
    (tmp_path / "z.mp4").write_text("x")
    (tmp_path / "a.mp4").write_text("x")
    (tmp_path / "m.mp4").write_text("x")

    result = discover_media(tmp_path)

    assert [item.relative_path for item in result.items] == ["a.mp4", "m.mp4", "z.mp4"]
