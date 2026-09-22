"""Model contracts for DiscoveredMediaItem / DiscoveryIssue / DiscoveryResult
(contract sections 5-7, 13)."""

from __future__ import annotations

import pytest

from fc2_organizer.discovery import (
    DiscoveredMediaItem,
    DiscoveryContractError,
    DiscoveryIssue,
    DiscoveryIssueKind,
    DiscoveryResult,
    DiscoveryStage,
)
from fc2_organizer.discovery.models import MAX_ISSUE_DETAIL_LENGTH


def make_item(index=0, source_path="/root/a.mp4", relative_path="a.mp4", extension=".mp4", size=10):
    return DiscoveredMediaItem(
        index=index, source_path=source_path, relative_path=relative_path, extension=extension, size=size
    )


class TestDiscoveredMediaItem:
    def test_valid_construction(self):
        item = make_item()
        assert item.index == 0
        assert item.extension == ".mp4"

    def test_frozen(self):
        item = make_item()
        with pytest.raises(Exception):
            item.size = 5  # type: ignore[misc]

    @pytest.mark.parametrize("bad_index", [-1, "0", 1.5, True, False])
    def test_rejects_bad_index(self, bad_index):
        with pytest.raises(DiscoveryContractError):
            make_item(index=bad_index)

    @pytest.mark.parametrize("field_name", ["source_path", "relative_path"])
    def test_rejects_empty_path_fields(self, field_name):
        with pytest.raises(DiscoveryContractError):
            make_item(**{field_name: ""})

    def test_rejects_extension_without_leading_dot(self):
        with pytest.raises(DiscoveryContractError):
            make_item(extension="mp4")

    @pytest.mark.parametrize("bad_size", [-1, "10", 1.5, True])
    def test_rejects_bad_size(self, bad_size):
        with pytest.raises(DiscoveryContractError):
            make_item(size=bad_size)

    def test_zero_size_file_is_legal(self):
        item = make_item(size=0)
        assert item.size == 0


class TestDiscoveryIssue:
    def test_build_uses_canned_message(self):
        issue = DiscoveryIssue.build(
            path="/root/secret", kind=DiscoveryIssueKind.PERMISSION_DENIED, stage=DiscoveryStage.LIST_DIRECTORY
        )
        assert issue.detail == "permission denied"
        assert issue.path == "/root/secret"

    def test_detail_is_truncated_to_bound(self):
        issue = DiscoveryIssue(
            path="/x", kind=DiscoveryIssueKind.STAT_FAILED, stage=DiscoveryStage.STAT_ENTRY, detail="x" * 10_000
        )
        assert len(issue.detail) == MAX_ISSUE_DETAIL_LENGTH

    def test_rejects_wrong_kind_type(self):
        with pytest.raises(DiscoveryContractError):
            DiscoveryIssue(path="/x", kind="permission_denied", stage=DiscoveryStage.STAT_ENTRY, detail="d")  # type: ignore[arg-type]

    def test_rejects_wrong_stage_type(self):
        with pytest.raises(DiscoveryContractError):
            DiscoveryIssue(path="/x", kind=DiscoveryIssueKind.STAT_FAILED, stage="stat", detail="d")  # type: ignore[arg-type]

    def test_frozen(self):
        issue = DiscoveryIssue.build(
            path="/x", kind=DiscoveryIssueKind.STAT_FAILED, stage=DiscoveryStage.STAT_ENTRY
        )
        with pytest.raises(Exception):
            issue.path = "/y"  # type: ignore[misc]


class TestDiscoveryResult:
    def test_empty_result_is_legal(self):
        result = DiscoveryResult(root="/root", items=(), issues=())
        assert result.total_items == 0
        assert result.total_issues == 0

    def test_index_must_equal_position(self):
        bad_item = DiscoveredMediaItem(index=5, source_path="/a", relative_path="a", extension=".mp4", size=1)
        with pytest.raises(DiscoveryContractError):
            DiscoveryResult(root="/root", items=(bad_item,), issues=())

    def test_rejects_duplicate_source_path(self):
        item0 = DiscoveredMediaItem(index=0, source_path="/a", relative_path="a", extension=".mp4", size=1)
        item1 = DiscoveredMediaItem(index=1, source_path="/a", relative_path="a", extension=".mp4", size=1)
        with pytest.raises(DiscoveryContractError):
            DiscoveryResult(root="/root", items=(item0, item1), issues=())

    def test_accepts_two_items_with_same_relative_name_different_dirs(self):
        item0 = DiscoveredMediaItem(index=0, source_path="/root/A/a.mp4", relative_path="A/a.mp4", extension=".mp4", size=1)
        item1 = DiscoveredMediaItem(index=1, source_path="/root/B/a.mp4", relative_path="B/a.mp4", extension=".mp4", size=1)
        result = DiscoveryResult(root="/root", items=(item0, item1), issues=())
        assert result.total_items == 2

    def test_rejects_non_tuple_items(self):
        with pytest.raises(DiscoveryContractError):
            DiscoveryResult(root="/root", items=[], issues=())  # type: ignore[arg-type]

    def test_frozen(self):
        result = DiscoveryResult(root="/root", items=(), issues=())
        with pytest.raises(Exception):
            result.root = "/other"  # type: ignore[misc]
