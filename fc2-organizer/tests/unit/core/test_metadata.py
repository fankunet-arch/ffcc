"""Unit tests for NormalizedMetadata: minimum success, runtime type contract
(R1-01/F1), and deep immutability (R1-02/F2).
"""

from __future__ import annotations

from types import MappingProxyType

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
        assert md.tags == ("a", "b")


class TestRuntimeValidation:
    def test_negative_runtime_is_rejected(self):
        with pytest.raises(MetadataContractError):
            NormalizedMetadata(number="FC2-1234567", title="T", runtime=-1)

    def test_non_int_runtime_is_rejected(self):
        with pytest.raises(MetadataContractError):
            NormalizedMetadata(number="FC2-1234567", title="T", runtime="118")  # type: ignore[arg-type]

    def test_bool_runtime_is_rejected(self):
        with pytest.raises(MetadataContractError):
            NormalizedMetadata(number="FC2-1234567", title="T", runtime=True)  # type: ignore[arg-type]

    def test_none_or_non_negative_int_runtime_is_accepted(self):
        NormalizedMetadata(number="FC2-1234567", title="T", runtime=None)
        NormalizedMetadata(number="FC2-1234567", title="T", runtime=0)
        NormalizedMetadata(number="FC2-1234567", title="T", runtime=118)


class TestScalarTypeValidation:
    """R1-01 / F1: illegal scalar types must be rejected at construction,
    as MetadataContractError, never surface later as a bare AttributeError
    from meets_minimum_success() or its helpers."""

    def test_original_f1_reproduction_title_int_is_rejected_at_construction(self):
        """The exact reviewer reproduction: title=123 must raise
        MetadataContractError immediately, not construct successfully and
        blow up later with AttributeError on `.strip()`."""
        with pytest.raises(MetadataContractError):
            NormalizedMetadata(number="FC2-4825061", title=123)  # type: ignore[arg-type]

    def test_number_wrong_type_is_rejected(self):
        with pytest.raises(MetadataContractError):
            NormalizedMetadata(number=4825061, title="T")  # type: ignore[arg-type]

    @pytest.mark.parametrize(
        "field_name", ["number", "title", "studio", "publisher", "release", "plot"]
    )
    def test_each_scalar_str_field_rejects_non_str_non_none(self, field_name):
        with pytest.raises(MetadataContractError):
            NormalizedMetadata(**{field_name: 123})

    def test_meets_minimum_success_never_raises_for_any_constructed_instance(self):
        """Total predicate: if construction succeeds, meets_minimum_success()
        (and its helpers) must always return a plain bool."""
        candidates = [
            NormalizedMetadata(),
            NormalizedMetadata(number="FC2-1234567"),
            NormalizedMetadata(title="only a title"),
            NormalizedMetadata(number="FC2-1234567", title="a title"),
            NormalizedMetadata(number="FC2-1234567", title=""),
            NormalizedMetadata(number="not-fc2-shaped", title="a title"),
        ]
        for md in candidates:
            assert isinstance(md.has_valid_canonical_number(), bool)
            assert isinstance(md.has_non_empty_title(), bool)
            assert isinstance(md.meets_minimum_success(), bool)


class TestCollectionTypeValidation:
    """R1-01 / F1: illegal collection contents must be rejected at
    construction, never allowed to enter the domain object."""

    @pytest.mark.parametrize(
        "field_name",
        [
            "actors",
            "tags",
            "poster_urls",
            "thumb_urls",
            "fanart_urls",
            "extrafanart",
            "source_urls",
        ],
    )
    def test_each_str_sequence_field_rejects_non_str_element(self, field_name):
        with pytest.raises(MetadataContractError):
            NormalizedMetadata(**{field_name: [123]})
        with pytest.raises(MetadataContractError):
            NormalizedMetadata(**{field_name: [None]})
        with pytest.raises(MetadataContractError):
            NormalizedMetadata(**{field_name: [object()]})

    def test_bare_str_is_rejected_for_a_sequence_field(self):
        """A common bug: passing a single str where a list of str was meant.
        Must be rejected, not silently iterated character-by-character."""
        with pytest.raises(MetadataContractError):
            NormalizedMetadata(actors="John Doe")  # type: ignore[arg-type]

    def test_non_iterable_is_rejected_for_a_sequence_field(self):
        with pytest.raises(MetadataContractError):
            NormalizedMetadata(tags=123)  # type: ignore[arg-type]

    def test_external_ids_rejects_non_str_key(self):
        with pytest.raises(MetadataContractError):
            NormalizedMetadata(external_ids={123: "abc"})  # type: ignore[dict-item]

    def test_external_ids_rejects_non_str_value(self):
        with pytest.raises(MetadataContractError):
            NormalizedMetadata(external_ids={"x": 123})  # type: ignore[dict-item]

    def test_external_ids_rejects_non_mapping(self):
        with pytest.raises(MetadataContractError):
            NormalizedMetadata(external_ids=["x", "y"])  # type: ignore[arg-type]

    def test_field_sources_rejects_non_str_key(self):
        with pytest.raises(MetadataContractError):
            NormalizedMetadata(field_sources={123: ["source-a"]})  # type: ignore[dict-item]

    def test_field_sources_rejects_non_str_value_element(self):
        with pytest.raises(MetadataContractError):
            NormalizedMetadata(field_sources={"title": [123]})

    def test_field_sources_rejects_non_sequence_value(self):
        with pytest.raises(MetadataContractError):
            NormalizedMetadata(field_sources={"title": 123})  # type: ignore[dict-item]


class TestImmutability:
    """R1-02 / F2: NormalizedMetadata is a deeply immutable value object."""

    def test_scalar_attribute_assignment_is_rejected(self):
        md = NormalizedMetadata(number="FC2-1234567", title="valid")
        with pytest.raises(Exception):
            md.title = "changed"  # type: ignore[misc]
        assert md.title == "valid"

    def test_sequence_fields_are_stored_as_tuples(self):
        md = NormalizedMetadata(
            number="FC2-1234567",
            title="valid",
            actors=["A", "B"],
            tags=["x"],
            poster_urls=["https://example.invalid/p.jpg"],
        )
        assert isinstance(md.actors, tuple)
        assert isinstance(md.tags, tuple)
        assert isinstance(md.poster_urls, tuple)
        assert md.actors == ("A", "B")

    def test_sequence_fields_cannot_be_mutated_in_place(self):
        md = NormalizedMetadata(number="FC2-1234567", title="valid", actors=["A"])
        with pytest.raises(AttributeError):
            md.actors.append("B")  # type: ignore[attr-defined]
        assert md.actors == ("A",)

    def test_mapping_fields_are_stored_as_mapping_proxy(self):
        md = NormalizedMetadata(
            number="FC2-1234567",
            title="valid",
            external_ids={"source-a": "ext-1"},
            field_sources={"title": ["source-a"]},
        )
        assert isinstance(md.external_ids, MappingProxyType)
        assert isinstance(md.field_sources, MappingProxyType)
        assert md.field_sources["title"] == ("source-a",)

    def test_external_ids_cannot_be_mutated_in_place(self):
        md = NormalizedMetadata(
            number="FC2-1234567", title="valid", external_ids={"a": "1"}
        )
        with pytest.raises(TypeError):
            md.external_ids["b"] = "2"  # type: ignore[index]
        with pytest.raises(TypeError):
            del md.external_ids["a"]  # type: ignore[attr-defined]
        assert dict(md.external_ids) == {"a": "1"}

    def test_field_sources_nested_tuple_cannot_be_mutated_in_place(self):
        md = NormalizedMetadata(
            number="FC2-1234567",
            title="valid",
            field_sources={"title": ["source-a"]},
        )
        with pytest.raises(AttributeError):
            md.field_sources["title"].append("source-z")  # type: ignore[attr-defined]
        assert md.field_sources["title"] == ("source-a",)

    def test_field_sources_mapping_cannot_be_mutated_in_place(self):
        md = NormalizedMetadata(
            number="FC2-1234567",
            title="valid",
            field_sources={"title": ["source-a"]},
        )
        with pytest.raises(TypeError):
            md.field_sources["tags"] = ("source-b",)  # type: ignore[index]
        assert dict(md.field_sources) == {"title": ("source-a",)}


class TestCallerOwnedInputAliasSafety:
    """R1-02 / F2: mutating the caller's own input container after
    construction must never affect the already-constructed instance."""

    def test_mutating_original_list_after_construction_does_not_affect_instance(self):
        actors = ["A"]
        md = NormalizedMetadata(number="FC2-1234567", title="valid", actors=actors)
        actors.append("B")
        assert md.actors == ("A",)

    def test_mutating_original_external_ids_dict_does_not_affect_instance(self):
        external_ids = {"a": "1"}
        md = NormalizedMetadata(
            number="FC2-1234567", title="valid", external_ids=external_ids
        )
        external_ids["b"] = "2"
        external_ids["a"] = "changed"
        assert dict(md.external_ids) == {"a": "1"}

    def test_mutating_original_field_sources_dict_does_not_affect_instance(self):
        field_sources = {"title": ["a"]}
        md = NormalizedMetadata(
            number="FC2-1234567", title="valid", field_sources=field_sources
        )
        field_sources["title"].append("b")  # mutate the nested list too
        field_sources["tags"] = ["c"]  # and add a whole new key
        assert dict(md.field_sources) == {"title": ("a",)}

    def test_default_factory_produces_fresh_containers_each_call(self):
        a = NormalizedMetadata()
        b = NormalizedMetadata()
        assert a.actors == () and b.actors == ()
        assert dict(a.external_ids) == {} and dict(b.external_ids) == {}
        assert dict(a.field_sources) == {} and dict(b.field_sources) == {}
