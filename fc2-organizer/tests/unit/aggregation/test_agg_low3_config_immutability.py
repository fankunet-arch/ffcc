"""C1 review LOW-3: AggregationConfig is immutable through the DIRECT constructor too.

The reviewer showed ``AggregationConfig(...)`` accepted a mutable list for
``field_priority``; mutating it afterwards changed ``policy()``. The frozen shape is
``tuple[tuple[str, tuple[str, ...]], ...]`` and anything else is an
``AggregationConfigError`` -- never a TypeError / KeyError / AttributeError.
"""

from __future__ import annotations

import dataclasses

import pytest

from fc2_metadata_core.aggregation import AggregationConfig, AggregationConfigError, SourceConfig

SOURCES = (SourceConfig("a"), SourceConfig("b"), SourceConfig("c"))


def direct(field_priority):
    return AggregationConfig(sources=SOURCES, field_priority=field_priority)


# ---- the reviewer's reproduction ----------------------------------------------------------------------------


def test_the_reviewers_mutable_list_is_rejected_at_construction():
    with pytest.raises(AggregationConfigError):
        direct([("title", ("c",))])  # type: ignore[arg-type]  # outer list


def test_a_mutable_nested_list_is_rejected():
    with pytest.raises(AggregationConfigError):
        direct((("title", ["c"]),))  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "bad",
    [
        [("title", ("c",))],
        {"title": ("c",)},
        {"title": ["c"]},
        (["title", ("c",)],),  # entry is a list
        (("title", ["c"]),),  # ids are a list
        (("title", {"c"}),),  # ids are a set
        (("title", "c"),),  # a bare str for ids
        (("title", ("c",), "extra"),),  # 3-tuple
        (("title",),),  # 1-tuple
        ((),),
        ("title",),  # entry is a str
        (("title", ("c", 5)),),  # non-str id
        (("title", (None,)),),
        "title",
        5,
        None,
        b"title",
        frozenset({("title", ("c",))}),
    ],
    ids=lambda v: repr(v)[:50],
)
def test_every_non_frozen_shape_is_a_domain_error(bad):
    with pytest.raises(AggregationConfigError):
        direct(bad)


@pytest.mark.parametrize("field_name", [None, 5, 1.5, ("t",), ["t"], {"t"}, b"title", object(), "", True])
def test_bad_field_names_including_unhashable_ones_are_domain_errors_not_type_errors(field_name):
    try:
        direct(((field_name, ("a",)),))
    except AggregationConfigError:
        return
    except Exception as exc:  # pragma: no cover - the failure this test exists to catch
        pytest.fail(f"leaked {type(exc).__name__}: {exc}")
    pytest.fail("accepted a malformed field name")


def test_unknown_field_or_unconfigured_source_or_duplicates_are_still_domain_errors_when_shaped_correctly():
    for bad in ((("nonsense", ("a",)),), (("title", ("zzz",)),), (("title", ("a", "a")),), (("title", ("a",)), ("title", ("b",))), (("number", ("a",)),)):
        with pytest.raises(AggregationConfigError):
            direct(bad)


def test_the_strict_shape_is_accepted():
    config = direct((("title", ("c", "a")), ("actors", ("b",))))
    assert config.policy().priority_for("title") == ("c", "a", "b")
    assert config.policy().priority_for("actors") == ("b", "a", "c")


def test_other_direct_constructor_containers_are_strict_too():
    with pytest.raises(AggregationConfigError):
        AggregationConfig(sources=list(SOURCES))  # type: ignore[arg-type]
    with pytest.raises(AggregationConfigError):
        AggregationConfig(sources=set(SOURCES))  # type: ignore[arg-type]
    with pytest.raises(AggregationConfigError):
        AggregationConfig(sources=SOURCES, retry_policy={"max_attempts": 2})  # type: ignore[arg-type]


# ---- later mutation of caller-owned objects cannot reach the config ----------------------------------------------


def test_create_copies_everything_so_caller_mutation_changes_nothing():
    priority = {"title": ["c"], "actors": ["b", "c"]}
    sources = [SourceConfig("a"), SourceConfig("b"), SourceConfig("c")]
    config = AggregationConfig.create(sources, field_priority=priority)
    before = (config, hash(config), config.policy(), config.policy().priority_for("title"))

    priority["title"].append("a")
    priority["title"][0] = "a"
    priority["actors"].clear()
    priority["release"] = ["c"]
    priority.clear()
    sources.append(SourceConfig("d"))
    sources.clear()

    after = (config, hash(config), config.policy(), config.policy().priority_for("title"))
    assert after == before
    assert config.policy().priority_for("title") == ("c", "a", "b")
    assert [s.source_id for s in config.sources] == ["a", "b", "c"]


def test_a_direct_config_holds_only_tuples_so_nothing_can_be_mutated_in_place():
    config = direct((("title", ("c",)),))
    assert isinstance(config.sources, tuple) and isinstance(config.field_priority, tuple)
    assert all(isinstance(entry, tuple) and isinstance(entry[1], tuple) for entry in config.field_priority)
    with pytest.raises(TypeError):
        config.field_priority[0][1][0] = "a"  # type: ignore[index]
    with pytest.raises(dataclasses.FrozenInstanceError):
        config.field_priority = ()  # type: ignore[misc]


def test_equality_hash_and_policy_are_value_based_and_stable():
    one = direct((("title", ("c",)),))
    two = direct((("title", ("c",)),))
    assert one == two and hash(one) == hash(two)
    assert one != direct((("title", ("b",)),))
    assert len({one, two}) == 1
    assert one.policy() == two.policy() == one.policy()


def test_policy_is_recomputed_from_frozen_state_each_time():
    config = direct((("title", ("c",)),))
    assert config.policy() == config.policy()
    assert config.policy().priority_for("title") == ("c", "a", "b")
