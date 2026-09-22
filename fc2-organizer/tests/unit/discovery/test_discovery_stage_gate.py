"""Large synthetic stage gate (contract section 19).

Builds a synthetic tree with hundreds of files across many nested
directories, mixed supported/unsupported extensions, duplicate FC2 numbers
across directories, Unicode names, and empty directories, then proves:

* every supported media file is discovered exactly once,
* no unsupported file ever becomes an item,
* output order is stable across repeated runs,
* there is no duplicate ``source_path``,
* no recursion loop occurs (the run terminates at all),
* no filesystem mutation occurs.

Fully offline and deterministic; no network, no Amane. Reproducible: uses a
fixed, code-driven layout (no randomness), so re-running this test builds
the identical tree and must produce the identical result every time.
"""

from __future__ import annotations

import os

from fc2_organizer.discovery import discover_media

_SUPPORTED = (".mp4", ".mkv", ".avi", ".mov", ".wmv", ".m4v", ".ts")
_UNSUPPORTED = (".jpg", ".jpeg", ".png", ".webp", ".nfo", ".srt", ".ass", ".txt", ".url")

_DUPLICATE_NUMBERS = ("FC2-1000001", "FC2-1000002", "FC2-1000003")


def _build_synthetic_tree(root) -> tuple[int, int]:
    """Returns (expected_supported_count, expected_unsupported_count)."""
    supported_count = 0
    unsupported_count = 0

    for studio in range(10):
        studio_dir = root / f"studio_{studio:02d}"
        for sub in range(5):
            leaf = studio_dir / f"batch_{sub:02d}"
            leaf.mkdir(parents=True)
            for i in range(6):
                ext = _SUPPORTED[(studio + sub + i) % len(_SUPPORTED)]
                (leaf / f"video_{studio:02d}_{sub:02d}_{i:02d}{ext}").write_bytes(b"x" * (i + 1))
                supported_count += 1
                unsupported_ext = _UNSUPPORTED[(studio + sub + i) % len(_UNSUPPORTED)]
                (leaf / f"video_{studio:02d}_{sub:02d}_{i:02d}{unsupported_ext}").write_bytes(b"y")
                unsupported_count += 1

    # Duplicate FC2 numbers across distinct directories (must never collapse).
    for i, number in enumerate(_DUPLICATE_NUMBERS):
        dup_dir = root / "duplicates" / f"copy_{i}"
        dup_dir.mkdir(parents=True)
        (dup_dir / f"{number}.mp4").write_bytes(b"dup")
        supported_count += 1

    # Unicode names.
    unicode_dir = root / "動画" / "日本語サブフォルダ"
    unicode_dir.mkdir(parents=True)
    (unicode_dir / "動画ファイル.mp4").write_bytes(b"u")
    supported_count += 1
    (unicode_dir / "字幕.srt").write_bytes(b"u")
    unsupported_count += 1

    # Empty directories scattered through the tree.
    (root / "empty_top").mkdir()
    (root / "studio_00" / "empty_leaf").mkdir()

    return supported_count, unsupported_count


def test_large_synthetic_stage_gate(tmp_path):
    expected_supported, expected_unsupported = _build_synthetic_tree(tmp_path)
    assert expected_supported >= 300  # sanity: this is genuinely a "hundreds of files" gate
    assert expected_unsupported >= 300

    def snapshot_fs():
        seen = set()
        for dirpath, dirnames, filenames in os.walk(tmp_path):
            for name in dirnames + filenames:
                seen.add(os.path.join(dirpath, name))
        return seen

    before = snapshot_fs()
    first = discover_media(tmp_path)
    second = discover_media(tmp_path)
    after = snapshot_fs()

    # No mutation across either run.
    assert before == after

    # Every supported file exactly once; no unsupported file ever an item.
    assert first.total_items == expected_supported
    for item in first.items:
        assert item.extension in _SUPPORTED
        assert item.extension not in _UNSUPPORTED

    # No duplicate source_path (DiscoveryResult's own invariant already
    # enforces this at construction, but assert explicitly here too).
    source_paths = [item.source_path for item in first.items]
    assert len(source_paths) == len(set(source_paths))

    # No issues expected on a clean, fully-readable synthetic tree.
    assert first.issues == ()

    # Stable ordering across repeated runs of the same unchanged tree.
    assert [item.relative_path for item in first.items] == [item.relative_path for item in second.items]
    assert [item.index for item in first.items] == [item.index for item in second.items]

    # Duplicate FC2 numbers across directories remain distinct items.
    dup_items = [item for item in first.items if "duplicates/" in item.relative_path.replace(os.sep, "/")]
    assert len(dup_items) == len(_DUPLICATE_NUMBERS)
    assert len({item.source_path for item in dup_items}) == len(_DUPLICATE_NUMBERS)
