"""Registry ``create`` boundary (Phase 3 C1, closes Phase 2 review finding P2-R-11).

Phase 2 let ``register("alias_x", Fc2dbNetAdapter)`` produce an adapter whose
own ``source_id`` was ``"fc2db_net"`` (results attributed to the wrong source)
and ``register("junk", lambda **k: 42)`` hand the dispatcher an ``int``.
"""

from __future__ import annotations

import pytest

from fc2_metadata_core.sources import (
    InvalidSourceAdapterError,
    SourceFactoryError,
    SourceIdMismatchError,
    SourceRegistry,
    SourceRegistryError,
    UnknownSourceIdError,
)
from fc2_metadata_core.sources.adapters.fc2db_net import Fc2dbNetAdapter

from support.fake_source_adapter import FakeSourceAdapter


def test_22_factory_returning_a_non_adapter_is_a_domain_error():
    registry = SourceRegistry()
    registry.register("junk", lambda **kwargs: 42)
    with pytest.raises(InvalidSourceAdapterError) as info:
        registry.create("junk")
    assert "int" in str(info.value)


@pytest.mark.parametrize("junk", [None, "adapter", object(), FakeSourceAdapter, {"source_id": "x"}, 3.5])
def test_any_foreign_return_value_is_rejected_never_leaked(junk):
    registry = SourceRegistry()
    registry.register("x", lambda **kwargs: junk)
    with pytest.raises(InvalidSourceAdapterError):
        registry.create("x")


def test_23_source_id_mismatch_is_a_domain_error():
    registry = SourceRegistry()
    registry.register("alias_x", Fc2dbNetAdapter)
    with pytest.raises(SourceIdMismatchError) as info:
        registry.create("alias_x")
    assert "alias_x" in str(info.value) and "fc2db_net" in str(info.value)


def test_a_matching_class_and_a_matching_factory_both_work():
    registry = SourceRegistry()
    registry.register("fake_source", FakeSourceAdapter)
    registry.register("fc2db_net", lambda **kwargs: Fc2dbNetAdapter(**kwargs))
    assert isinstance(registry.create("fake_source"), FakeSourceAdapter)
    adapter = registry.create("fc2db_net", base_url="https://mirror.example")
    assert adapter.source_id == "fc2db_net" and adapter.base_url == "https://mirror.example"


@pytest.mark.parametrize("exc", [TypeError("bad kwargs"), AttributeError("x"), ValueError("v"), RuntimeError("r")])
def test_a_factory_that_raises_is_wrapped_with_the_original_chained(exc):
    def factory(**kwargs):
        raise exc

    registry = SourceRegistry()
    registry.register("boom", factory)
    with pytest.raises(SourceFactoryError) as info:
        registry.create("boom")
    assert info.value.__cause__ is exc
    assert type(exc).__name__ in str(info.value)


def test_an_unexpected_keyword_for_the_factory_is_a_domain_error_not_a_bare_type_error():
    registry = SourceRegistry()
    registry.register("fake_source", FakeSourceAdapter)
    with pytest.raises(SourceFactoryError):
        registry.create("fake_source", not_a_real_option=1)


def test_keyboard_interrupt_and_system_exit_from_a_factory_are_not_swallowed():
    for exc_type in (KeyboardInterrupt, SystemExit):
        def factory(**kwargs):
            raise exc_type()

        registry = SourceRegistry()
        registry.register("x", factory)
        with pytest.raises(exc_type):
            registry.create("x")


def test_every_new_error_is_a_source_registry_error():
    for cls in (InvalidSourceAdapterError, SourceIdMismatchError, SourceFactoryError):
        assert issubclass(cls, SourceRegistryError)


def test_a_non_callable_factory_is_rejected_at_registration():
    registry = SourceRegistry()
    for bad in (None, 42, "FakeSourceAdapter"):
        with pytest.raises(SourceRegistryError):
            registry.register("x", bad)  # type: ignore[arg-type]
    assert "x" not in registry


def test_an_unknown_or_unhashable_id_is_still_unknown_source_id():
    registry = SourceRegistry()
    for bad in ("nope", ["list"], {"d": 1}):
        with pytest.raises(UnknownSourceIdError):
            registry.create(bad)  # type: ignore[arg-type]
