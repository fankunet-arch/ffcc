"""P4-C10 S2: G-500, the Phase 4 cross-package 500-item global gate (contract section 7.4; EC-05; XD-A01, XD-A07).

One batch of 500 inputs is carried through the *real* chain end to end: 500 physical files found by the real
``discover_media`` -> real ``MultiSourceEngine`` (scripted ``SourceAdapter``s) -> real orchestrator -> real
``HttpxImageClient`` (``httpx.MockTransport``) -> real P4-C7 / P4-C6 execution on a disposable tree -> real P4-C8 retry /
merge -> real P4-C9 diagnostics, over generations g0 .. g4 with injected faults. Every frozen count of the contract is
asserted exactly, twice: against the literal table of the contract and against its derivation from the group sizes
(``_corpus.mixed_expectations``). The whole batch then runs a second time in a fresh tree; the 14 default-policy
diagnostics JSON documents must be byte-identical.
"""

from __future__ import annotations

import json
import os
from collections import Counter

from . import _corpus as corpus
from ._corpus import G500_FROZEN, G500_PLAN, MixedCorpus, mixed_expectations
from ._harness import CONFIG_4, GENERATION_SCOPES, Chain, MixedBatch, diagnostics_bytes
from ._oracles import (
    gate_default_output_clean,
    gate_deterministic_equal,
    gate_diagnostics_canaries,
    gate_diagnostics_structure,
    gate_entries_unchanged,
    gate_library_exact,
    gate_no_network,
    gate_peak,
    gate_phase_a_conflicts,
    sha256_file,
)
from fc2_organizer.diagnostics import DIAGNOSTICS_SCHEMA, DIAGNOSTICS_SCHEMA_VERSION, PathPolicy
from fc2_organizer.orchestration import ItemWarning

EXPECTED = mixed_expectations(G500_PLAN)


def _check_literal(section, derived, names):
    for name in names:
        assert G500_FROZEN[section][name] == derived[name], (section, name)


def _counts(preview):
    s = preview.summary
    return dict(total=s.total, ready=s.ready, blocked=s.blocked, unprepared=s.unprepared)


def _result_counts(result):
    s = result.summary
    return dict(success=s.success, partial=s.partial, failed=s.failed, aborted=s.aborted, not_selected=s.not_selected,
                not_ready=result.summary.blocked + result.summary.unprepared, retryable=s.retryable,
                deferred=s.deferred, non_retryable=s.non_retryable)


def _diagnose(models):
    """The 14 models of contract section 7.4 item 6: NONE for all, BASENAME for the main preview and the final merge."""
    rendered = []
    for index, (model, kind) in enumerate(models):
        none = diagnostics_bytes(model)
        gate_diagnostics_structure(none, schema=DIAGNOSTICS_SCHEMA, schema_version=DIAGNOSTICS_SCHEMA_VERSION, kind=kind,
                                   indices=[i.index for i in model.items])
        gate_diagnostics_canaries(none, forbidden=corpus.FX5_ALWAYS_FORBIDDEN)
        gate_default_output_clean(none)  # the scripted failure details carry class A text: none of it is rendered
        assert json.loads(none)["batch_size"] == 500
        if index in (0, len(models) - 1):
            named = diagnostics_bytes(model, PathPolicy.BASENAME)
            gate_diagnostics_canaries(named, forbidden=corpus.FX5_ALWAYS_FORBIDDEN)
            gate_diagnostics_structure(named, schema=DIAGNOSTICS_SCHEMA, schema_version=DIAGNOSTICS_SCHEMA_VERSION,
                                       kind=kind, indices=[i.index for i in model.items])
        rendered.append(none)
    return rendered


def run_g500(root):
    """One complete G-500 run in ``root``; returns the 14 default-policy diagnostics documents."""
    mixed = MixedCorpus(G500_PLAN)
    plan = G500_PLAN
    physical = len(mixed.films)
    assert physical == 500
    with Chain(root, mixed.films, config=CONFIG_4) as chain:
        batch = MixedBatch(chain, mixed)
        batch.prepare()
        # ---- g0: preview
        items = chain.discover()  # 500 physical files, all found by the real discover_media
        assert len(items) == 500 and [i.index for i in items] == list(range(500))
        preview = chain.preview(items)
        derived = EXPECTED["g0_preview"]
        assert _counts(preview) == derived
        _check_literal("g0_preview", derived, ("total", "ready", "blocked", "unprepared"))
        assert gate_peak(chain.sources.peak_items, limit=4, expect_reached=False) is None
        groups = {name: [i for i in preview.items if batch.group_of(i) == name] for name in "ABCDEFGHIJK"}
        assert {name: len(v) for name, v in groups.items()} == {
            "A": plan.a, "B": plan.b, "C": plan.c, "D": plan.d, "E": plan.e, "F": 2 * plan.f_pairs, "G": plan.g,
            "H": plan.h, "I": plan.i, "J": plan.j, "K": plan.k}
        reasons = lambda name: Counter(i.issue.reason.value if i.issue else None for i in groups[name])  # noqa: E731
        for name in "ABDHIJK":
            assert reasons(name) == {None: len(groups[name])} and {i.state.value for i in groups[name]} == {"ready"}
        assert reasons("C") == {"metadata_unavailable": plan.c} and reasons("E") == {"number_not_recognized": plan.e}
        assert reasons("F") == {"duplicate_target_in_batch": 2 * plan.f_pairs} and reasons("G") == {
            "preflight_blocked": plan.g}
        assert {i.state.value for i in groups["F"] + groups["G"]} == {"blocked"}
        assert all(i.metadata is None for i in groups["E"] + groups["F"])  # Phase A: engine never asked
        f_numbers = {film.number for film in mixed.by_group("F")}
        by_number = {}
        for item in groups["F"]:
            by_number.setdefault(item.canonical_number, []).append(item.index)
        gate_phase_a_conflicts(preview, chain.sources.numbers_called, by_number.values())  # 10 pairs, none fetched
        assert len(by_number) == plan.f_pairs
        assert not f_numbers & set(chain.sources.numbers_called) and not any(
            batch.film_of(i).number is None for i in groups["A"])
        assert all(ItemWarning.METADATA_PARTIAL in i.warnings for i in groups["B"])
        assert all(ItemWarning.IMAGE_CANDIDATE_FAILURES in i.warnings for i in groups["D"])
        assert all(i.metadata.status.value == "success" for i in groups["A"])
        # ---- g0: execute (GH / GI / GK faults, GJ not selected)
        batch.main_preview = preview
        batch._arm_g0_faults(preview)
        selection = tuple(sorted(i.index for i in preview.items if i.state.value == "ready" and batch.group_of(i) != "J"))
        result = chain.execute(preview, selection=selection)
        chain.faults.assert_all_fired()
        chain.faults.clear_fired()
        batch.main_result = result
        derived = EXPECTED["g0_result"]
        assert _result_counts(result) == {k: derived[k] for k in _result_counts(result)}
        assert result.outcome.value == derived["outcome"] == "partial"  # contract 7.4: g0 outcome PARTIAL
        _check_literal("g0_result", derived, ("success", "partial", "failed", "aborted", "not_selected", "not_ready",
                                              "retryable", "deferred"))
        kinds = Counter(i.retry_kind.value for i in result.items)
        assert {k: kinds[k] for k in derived["kinds"]} == derived["kinds"] == G500_FROZEN["g0_result"]["kinds"]
        by_group = {name: [i for i in result.items if batch.group_of(i) == name] for name in "ABCDEFGHIJK"}
        assert {i.execution.status.value for i in by_group["H"]} == {"partial"} and all(
            i.execution.checkpoint is not None for i in by_group["H"])
        assert {i.execution.status.value for i in by_group["I"]} == {"failed"} and all(
            i.execution.checkpoint is None and not i.execution.completed_effects for i in by_group["I"])
        assert {i.disposition.value for i in by_group["K"]} == {"aborted"} and {
            i.disposition.value for i in by_group["J"]} == {"not_selected"}
        h_before = chain.snapshot()  # what P4-C7 completed for the GH entries (SI-13 reference)
        h_files = [name for film in mixed.by_group("H") for name, state in h_before.items()
                   if name.startswith(f"library/{film.number}/") and state[0] == "file"]
        assert h_files
        # ---- g1 .. g4
        models = [(preview, "preview"), (result, "execution")]
        previous = result
        for name in ("g1", "g2", "g3", "g4"):
            if name == "g2":
                assert len(batch.user_removes_blockers()) == plan.g_removed  # the user deletes 15 of the 20 blockers
            want = EXPECTED[name]
            retry_preview, retry_result, merged = batch.retry(previous, GENERATION_SCOPES[name])
            assert retry_preview.generation == int(name[1]) and len(retry_preview.items) == want["items"]
            rs = retry_preview.summary
            assert (rs.ready, rs.blocked, rs.unprepared) == (want["ready"], want["blocked"], want["unprepared"])
            assert retry_result.summary.success == want["success"] and retry_result.outcome.value == want["outcome"]
            assert merged.summary.success == want["merged_success"] and merged.generation == int(name[1])
            literal = G500_FROZEN[name]
            for key in ("items", "ready", "success", "merged_success"):
                if key in literal:
                    got = {"items": len(retry_preview.items), "ready": rs.ready, "success": retry_result.summary.success,
                           "merged_success": merged.summary.success}[key]
                    assert got == literal[key], (name, key)
            if name == "g1":
                after = chain.snapshot()  # SI-13: RESUME did not rewrite what was already completed
                gate_entries_unchanged(h_before, after, h_files, "SI-13 g1 RESUME")
            models += [(retry_preview, "preview"), (retry_result, "execution"), (merged, "execution")]
            previous = merged
        final = EXPECTED["final"]
        summary = previous.summary
        assert (summary.success, summary.blocked, summary.unprepared, summary.aborted) == (
            final["success"], final["blocked"], final["unprepared"], final["aborted"])
        assert previous.outcome.value == final["outcome"] and summary.retryable == final["retryable"]
        for key, value in G500_FROZEN["final"].items():
            if key in ("success", "blocked", "unprepared", "aborted", "retryable"):
                assert {"success": summary.success, "blocked": summary.blocked, "unprepared": summary.unprepared,
                        "aborted": summary.aborted, "retryable": summary.retryable}[key] == value
        # ---- invariants over the end state
        in_place = [film for film in mixed.films if os.path.exists(chain.source_path(film))]
        assert len(in_place) == final["sources_in_place"] == G500_FROZEN["final"]["sources_in_place"] == 65  # SI-09
        assert Counter(f.group for f in in_place) == {"E": plan.e, "F": 2 * plan.f_pairs, "G": plan.g - plan.g_removed,
                                                      "C": plan.c - plan.c_recover, "K": plan.k}
        for film in in_place:
            path = chain.source_path(film)
            assert sha256_file(path) == chain.original[path]
        organized, user_files, empty = batch.final_library_expectation()
        assert len(organized) == final["success"]  # 435 organized film directories
        gate_library_exact(chain.library, organized, user_files=user_files, empty_directories=empty)
        assert len(empty) == 10 and sum(1 for k in user_files if k.endswith("user-note.txt")) == 5
        assert chain.gate_runs["SI-01"] == 5 and chain.gate_runs["SI-21"] == 5  # g0 + four generations, every one gated
        gate_peak(chain.sources.peak_items, limit=4, expect_reached=False)
        gate_peak(chain.routes.peak, limit=4, expect_reached=False)
        gate_peak(chain.exec_probe.peak, limit=4, expect_reached=False)
        assert chain.sources.peak_items >= 2 and chain.routes.peak >= 2  # the stages really ran concurrently
        gate_no_network(chain.trap.hits)
        assert len(models) == 14
        return _diagnose(models), dict(peaks=(chain.sources.peak_items, chain.routes.peak, chain.exec_probe.peak))


def test_g500_cross_package_global_gate_with_exact_frozen_counts_and_deterministic_rerun(tmp_path):
    """G-500: frozen counts, accounting, source preservation, final layout, peaks, 14 diagnostics models, determinism."""
    first, first_peaks = run_g500(tmp_path / "run-1")
    second, second_peaks = run_g500(tmp_path / "run-2")  # a second complete run in a fresh tree
    assert len(first) == len(second) == 14
    for index, (a, b) in enumerate(zip(first, second)):
        gate_deterministic_equal(a, b, f"SI-07 G-500 diagnostics model {index}")  # byte-identical
    assert max(first_peaks["peaks"]) <= 4 and max(second_peaks["peaks"]) <= 4
