"""Unit tests for NormalizedMetadata: minimum success + mutable-default safety."""

from __future__ import annotations

import pytest

from fc2_metadata_core.errors import MetadataContractError
from fc2_metadata_core.models import NormalizedMetadata


class TestMinimumSuccess:
    """Frozen contract: minimum success = canonical FC2 number + non-empty title."""

    def test_number_and_title_satisfies_minimum_success(self):
        md = NormalizedMetadata(number="FC2-4825061", title="Some Title")
        assert md.meets_minimum_success() is True
        assert md.has_valid_canonical_number() is True
        assert md.has_non_empty_title() is True

    def test_number_with_empty_title_fails_minimum_success(self):
        md = NormalizedMetadata(number="FC2-4825061", title="")
        assert md.meets_minimum_success() is False

    def test_number_with_whitespace_only_title_fails_minimum_success(self):
        md = NormalizedMetadata(number="FC2-4825061", title="   ")
        assert md.meets_minimum_success() is False

    def test_number_with_missing_title_fails_minimum_success(self):
        md = NormalizedMetadata(number="FC2-4825061", title=None)
        assert md.meets_minimum_success() is False

    def test_title_without_number_fails_minimum_success(self):
        md = NormalizedMetadata(number=None, title="Some Title")
        assert md.meets_minimum_success() is False
        assert md.has_valid_canonical_number() is False

    def test_title_with_non_canonical_number_fails_minimum_success(self):
        assert (
            NormalizedMetadata(number="SSNI-999", title="Some Title")
            .meets_minimum_success()
            is False
        )
        assert (
            NormalizedMetadata(number="FC2-12", title="Some Title")
            .meets_minimum_success()
            is False
        )
        assert (
            NormalizedMetadata(number="FC21234567", title="Some Title")
            .meets_minimum_success()
            is False
        )

    def test_fully_empty_instance_is_valid_partial_and_fails_minimum_success(self):
        md = NormalizedMetadata()
        assert md.meets_minimum_success() is False

    def test_partial_metadata_with_only_secondary_fields_is_allowed(self):
        md = NormalizedMetadata(studio="Some Studio", tags=["a", "b"])
        assert md.meets_minimum_success() is False
        assert md.studio == "Some Studio"
        assert md.tags == ["a", "b"]


class TestMutableDefaultIsolation:
    def test_list_fields_are_not_shared_between_instances(self):
        a = NormalizedMetadata(number="FC2-1111111", title="A")
        b = NormalizedMetadata(number="FC2-2222222", title="B")

        a.actors.append("Actor A")
        a.tags.append("tag-a")
        a.poster_urls.append("https://example.invalid/a-poster.jpg")
        a.thumb_urls.append("https://example.invalid/a-thumb.jpg")
        a.fanart_urls.append("https://example.invalid/a-fanart.jpg")
        a.extrafanart.append("https://example.invalid/a-extra.jpg")
        a.source_urls.append("https://example.invalid/a-source")

        assert b.actors == []
        assert b.tags == []
        assert b.poster_urls == []
        assert b.thumb_urls == []
        assert b.fanart_urls == []
        assert b.extrafanart == []
        assert b.source_urls == []

    def test_dict_fields_are_not_shared_between_instances(self):
        a = NormalizedMetadata(number="FC2-1111111", title="A")
        b = NormalizedMetadata(number="FC2-2222222", title="B")

        a.external_ids["source-a"] = "ext-a-id"
        a.field_sources["title"] = ["source-a"]

        assert b.external_ids == {}
        assert b.field_sources == {}

    def test_default_factory_produces_fresh_containers_each_call(self):
        a = NormalizedMetadata()
        b = NormalizedMetadata()
        assert a.actors is not b.actors
        assert a.external_ids is not b.external_ids
        assert a.field_sources is not b.field_sources


class TestRuntimeValidation:
    def test_negative_runtime_is_rejected(self):
        with pytest.raises(MetadataContractError):
            NormalizedMetadata(number="FC2-1234567", title="T", runtime=-1)

    def test_non_int_runtime_is_rejected(self):
        with pytest.raises(MetadataContractError):
            NormalizedMetadata(number="FC2-1234567", title="T", runtime="118")  # type: ignore[arg-type]

    def test_none_or_non_negative_int_runtime_is_accepted(self):
        NormalizedMetadata(number="FC2-1234567", title="T", runtime=None)
        NormalizedMetadata(number="FC2-1234567", title="T", runtime=0)
        NormalizedMetadata(number="FC2-1234567", title="T", runtime=118)
