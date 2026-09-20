"""Phase 3 C3 (review C2-L5, documentation + behaviour pin): simultaneous fatal signals.

If several adapters raise *different* fatal ``BaseException``s at (nearly) the same time, exactly ONE fatal
is propagated, as the original object, never a ``BaseExceptionGroup``; the others are not preserved. This is
documented in ``PHASE3_RESILIENCE_CONTRACT.md`` §4 and pinned here so the behaviour stays deterministic.
"""

from __future__ import annotations

import asyncio

from fc2_metadata_core.aggregation import RetryPolicy, SourceConfig, SourceTarget, execute_sources_traced

from support.scripted_adapters import scripted_adapter_class

N = "FC2-4979299"
FAST = RetryPolicy(max_attempts=2, initial_backoff_seconds=0.01)


class FatalA(BaseException):
    pass


class FatalB(BaseException):
    pass


class FatalC(BaseException):
    pass


def target(source_id, script):
    return SourceTarget(SourceConfig(source_id, deadline_seconds=20.0), scripted_adapter_class(source_id, script)(), FAST)


def raising(instance):
    async def script(number, client):
        raise instance

    return script


def run_once():
    a, b, c = FatalA("a"), FatalB("b"), FatalC("c")
    targets = [target("a", raising(a)), target("b", raising(b)), target("c", raising(c))]
    try:
        asyncio.run(execute_sources_traced(N, targets, object()))
    except BaseException as exc:  # noqa: BLE001 - classify exactly what escapes
        return exc, (a, b, c)
    raise AssertionError("a fatal exception must propagate")


def test_simultaneous_distinct_fatals_propagate_exactly_one_original_object_never_a_group():
    raised, originals = run_once()
    assert not isinstance(raised, BaseExceptionGroup)
    assert any(raised is original for original in originals), "the propagated exception is one of the originals, unwrapped"
    assert raised.__cause__ is None or not isinstance(raised.__cause__, BaseExceptionGroup)


def test_which_fatal_wins_is_deterministic_for_the_same_scheduling_order():
    winners = [type(run_once()[0]) for _ in range(10)]
    assert len(set(winners)) == 1, f"fatal arbitration must not vary between identical runs: {winners}"


def test_the_other_fatals_are_not_preserved_documented_limitation():
    raised, originals = run_once()
    losers = [o for o in originals if o is not raised]
    assert len(losers) == 2
    # nothing of the losers is reachable from the propagated exception (no group, no notes, no chain)
    reachable = {id(raised.__cause__), id(raised.__context__)}
    assert not any(id(loser) in reachable for loser in losers)
    assert not getattr(raised, "__notes__", None)
