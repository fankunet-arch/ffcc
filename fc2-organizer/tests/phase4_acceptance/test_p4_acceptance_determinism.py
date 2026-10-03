"""P4-C10 S2: S-19 (determinism) and S-22 (bounded concurrency) (contract section 7.2; SI-06, SI-07).

S-19: FX-1 runs in two fresh trees; in the second run gate events reverse the completion order of the engine stage, the
image stage and the execution stage. The result projections (paths relative to the tree), the library trees and the
default-policy diagnostics bytes must be identical. S-22: eight entries with M = K = W = N; gate events hold calls in flight
until the budget is reached, so the observed peak must equal the budget and never exceed it.
"""

from __future__ import annotations

import pytest

from . import _corpus as corpus
from ._harness import CONFIG_1, CONFIG_4, Chain, diagnostics_bytes, result_projection
from ._oracles import gate_deterministic_equal, gate_peak, snapshot_tree
from fc2_metadata_core.batch import BatchConfig
from fc2_organizer.diagnostics import PathPolicy
from fc2_organizer.orchestration import OrchestrationConfig


def library_digest(chain):
    """Relative path -> (kind, size, sha256) of the library: the tree itself, independent of inodes / mtimes."""
    return {name: (state[0], state[1], state[3]) for name, state in snapshot_tree(chain.library).items()}


def run_once(root, *, reverse):
    films = corpus.FX1_FILMS
    with Chain(root, films, config=CONFIG_4, reverse=reverse) as chain:
        preview = chain.preview()
        result = chain.execute(preview)
        evidence = dict(
            preview=result_projection(chain.root, preview), result=result_projection(chain.root, result),
            library=library_digest(chain), diagnostics_none=(diagnostics_bytes(preview), diagnostics_bytes(result)),
            diagnostics_basename=(diagnostics_bytes(preview, PathPolicy.BASENAME),
                                  diagnostics_bytes(result, PathPolicy.BASENAME)))
        if reverse:
            for name, gate in (("engine", chain.sources.reverse), ("images", chain.routes.reverse),
                               ("execution", chain.exec_probe.reverse)):
                assert len(gate.arrival) == 4 and gate.release == gate.arrival[::-1], name  # the reversal really happened
            evidence["gated"] = (list(chain.sources.reverse.release), list(chain.sources.reverse.arrival))
        assert [i.index for i in result.items] == list(range(len(films)))  # index order, whatever finished first
        return evidence


def test_s19_two_fresh_trees_with_reversed_completion_order_give_identical_results(tmp_path):
    """S-19 (SI-07): identical projections, library trees and default-policy diagnostics bytes."""
    first = run_once(tmp_path / "first", reverse=False)
    second = run_once(tmp_path / "second", reverse=True)
    for name in ("preview", "result", "library", "diagnostics_none", "diagnostics_basename"):
        gate_deterministic_equal(first[name], second[name], f"SI-07 {name}")
    released, arrived = second["gated"]
    assert released != arrived  # the completion order of the second run really differed from the arrival order
    assert first["result"][3][0][0] == 0 and len(first["result"][3]) == 12


def test_s19_a_third_ordinary_run_is_also_identical(tmp_path):
    """S-19: a repeat of the ordinary run is byte-identical as well (no dependence on time, ids or the tree location)."""
    first = run_once(tmp_path / "one", reverse=False)
    again = run_once(tmp_path / "another-location" / "deeper", reverse=False)
    for name in ("preview", "result", "library", "diagnostics_none"):
        gate_deterministic_equal(first[name], again[name], f"SI-07 {name}")


@pytest.mark.parametrize("budget", [2, 3])
def test_s22_peaks_equal_the_budget_and_never_exceed_it(tmp_path, budget):
    """S-22 (SI-06): eight entries, M = K = W = budget, calls held in flight: each stage peaks exactly at its budget."""
    config = OrchestrationConfig(metadata=BatchConfig(max_in_flight_items=budget), image_in_flight_items=budget,
                                 filesystem_workers=budget)
    films = corpus.FX1_FILMS[:8]
    with Chain(tmp_path, films, config=config, hold_items=budget, hold_images=budget, hold_exec=budget) as chain:
        preview = chain.preview()  # zero mutation: checked by the chain around the call
        assert preview.summary.ready == 8
        result = chain.execute(preview)
        assert result.summary.success == 8 and chain.gate_runs["SI-21"] == 1
        gate_peak(chain.sources.peak_items, limit=budget, expect_reached=True)  # metadata items in flight
        gate_peak(chain.routes.peak, limit=budget, expect_reached=True)  # image items in flight (one request each)
        gate_peak(chain.exec_probe.peak, limit=budget, expect_reached=True)  # filesystem workers
        # no thread per entry: far fewer worker calls overlapped than there are entries
        assert chain.exec_probe.calls == 8 and chain.exec_probe.peak < 8


def test_s22_a_budget_of_one_serializes_every_stage(tmp_path):
    """S-22: M = K = W = 1 -> never more than one item in flight in any stage."""
    films = corpus.FX1_FILMS[:6]
    with Chain(tmp_path, films, config=CONFIG_1) as chain:
        result = chain.execute(chain.preview())
        assert result.summary.success == 6
        gate_peak(chain.sources.peak_items, limit=1, expect_reached=True)
        gate_peak(chain.routes.peak, limit=1, expect_reached=True)
        gate_peak(chain.exec_probe.peak, limit=1, expect_reached=True)
