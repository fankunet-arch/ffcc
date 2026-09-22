"""Core traversal behavior: empty root, single file, nested recursion, mixed
supported/unsupported content, case-insensitivity, Unicode, unusual valid
filename characters (contract test matrix items 1-15)."""

from __future__ import annotations

import os

from fc2_organizer.discovery import DiscoveryPolicy, discover_media


def rels(result):
    return sorted(item.relative_path for item in result.items)


def test_empty_root_returns_zero_items(tmp_path):
    result = discover_media(tmp_path)
    assert result.items == ()
    assert result.issues == ()
    assert result.total_items == 0


def test_single_media_file(tmp_path):
    (tmp_path / "movie.mp4").write_bytes(b"0123456789")
    result = discover_media(tmp_path)
    assert result.total_items == 1
    item = result.items[0]
    assert item.index == 0
    assert item.relative_path == "movie.mp4"
    assert item.extension == ".mp4"
    assert item.size == 10
    assert os.path.isabs(item.source_path)


def test_nested_recursive_directories(tmp_path):
    (tmp_path / "A" / "B").mkdir(parents=True)
    (tmp_path / "A" / "one.mp4").write_text("x")
    (tmp_path / "A" / "B" / "two.mkv").write_text("xx")
    result = discover_media(tmp_path)
    assert rels(result) == ["A/B/two.mkv", "A/one.mp4"]


def test_deep_recursive_tree(tmp_path):
    depth = 25
    current = tmp_path
    for level in range(depth):
        current = current / f"level{level}"
        current.mkdir()
    (current / "deep.mp4").write_text("x")
    result = discover_media(tmp_path)
    assert result.total_items == 1
    assert result.items[0].relative_path.endswith("deep.mp4")
    assert result.items[0].relative_path.count("/") == depth


def test_mixed_media_and_non_media_files(tmp_path):
    (tmp_path / "movie.mp4").write_text("x")
    (tmp_path / "poster.jpg").write_text("x")
    (tmp_path / "movie.nfo").write_text("x")
    (tmp_path / "subs.srt").write_text("x")
    result = discover_media(tmp_path)
    assert rels(result) == ["movie.mp4"]


def test_unsupported_extensions_are_ignored_without_failing_scan(tmp_path):
    for name in ("a.jpg", "a.jpeg", "a.png", "a.webp", "a.nfo", "a.srt", "a.ass", "a.txt", "a.url"):
        (tmp_path / name).write_text("x")
    result = discover_media(tmp_path)
    assert result.items == ()
    assert result.issues == ()


def test_partial_and_temp_files_are_ignored_by_their_own_unsupported_extension(tmp_path):
    # ".part"/".tmp" are not supported extensions, so these are ignored like
    # any other unsupported file -- policy matches by extension only, with
    # no special-cased filename convention (contract section 9).
    (tmp_path / "video.mp4.part").write_text("x")
    (tmp_path / "video.mp4.tmp").write_text("x")
    result = discover_media(tmp_path)
    assert result.items == ()


def test_tilde_prefixed_file_with_supported_extension_is_still_discovered(tmp_path):
    # A leading "~" has no special meaning to this package: only the
    # extension decides. This is deliberate, not an oversight.
    (tmp_path / "~video.mp4").write_text("x")
    result = discover_media(tmp_path)
    assert [item.relative_path for item in result.items] == ["~video.mp4"]


def test_uppercase_and_lowercase_extensions_are_equivalent(tmp_path):
    (tmp_path / "VIDEO.MP4").write_text("x")
    (tmp_path / "video2.mp4").write_text("x")
    result = discover_media(tmp_path)
    extensions = sorted(item.extension for item in result.items)
    assert extensions == [".mp4", ".mp4"]
    assert rels(result) == ["VIDEO.MP4", "video2.mp4"]


def test_unicode_filenames(tmp_path):
    name = "日本語ファイル名.mp4"
    (tmp_path / name).write_text("x", encoding="utf-8")
    result = discover_media(tmp_path)
    assert rels(result) == [name]


def test_unicode_directory_names(tmp_path):
    directory = tmp_path / "動画フォルダ"
    directory.mkdir()
    (directory / "movie.mp4").write_text("x")
    result = discover_media(tmp_path)
    assert rels(result) == ["動画フォルダ/movie.mp4"]


def test_spaces_and_unusual_valid_filename_characters(tmp_path):
    names = [
        "my movie (2024) [1080p].mp4",
        "movie - part 1 & 2.mkv",
        "movie's file.avi",
        "movie_v1.0.mov",
    ]
    for name in names:
        (tmp_path / name).write_text("x")
    result = discover_media(tmp_path)
    assert rels(result) == sorted(names)


def test_custom_policy_narrows_supported_extensions(tmp_path):
    (tmp_path / "a.mp4").write_text("x")
    (tmp_path / "b.mkv").write_text("x")
    result = discover_media(tmp_path, policy=DiscoveryPolicy(supported_extensions=frozenset({".mp4"})))
    assert rels(result) == ["a.mp4"]


def test_empty_subdirectories_do_not_produce_items_or_issues(tmp_path):
    (tmp_path / "empty1").mkdir()
    (tmp_path / "empty2" / "nested_empty").mkdir(parents=True)
    result = discover_media(tmp_path)
    assert result.items == ()
    assert result.issues == ()
