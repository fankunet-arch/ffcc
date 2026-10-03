"""P4-C10 S2: execution partial / failure / deferral and the retry chain: S-13, S-14, S-16, S-17 with links L-12 and L-13
(contract sections 5.2, 7.2) over the real engine, real image transport, real P4-C7 execution and real P4-C8 retry / merge.
"""

from __future__ import annotations

import errno
import os

import pytest

from . import _corpus as corpus
from ._corpus import expectation, success_film
from ._harness import CONFIG_1, CONFIG_4, Chain, MixedBatch, diagnostics_bytes, diagnostics_model
from ._oracles import (
    gate_diagnostics_canaries,
    gate_diagnostics_structure,
    gate_entries_unchanged,
    gate_library_exact,
    sha256_file,
)
from fc2_organizer.diagnostics import DIAGNOSTICS_SCHEMA, DIAGNOSTICS_SCHEMA_VERSION, PathPolicy
from fc2_organizer.orchestration import CancellationToken, OrchestrationConsumedError, RetryKind, merge_retry


def organized(films, call=0):
    return [(film, *expectation(film, call)) for film in films]


def item_of(model, film):
    return next(i for i in model.items if i.canonical_number == film.number)


def assert_sources_in_place(chain, films):
    for film in films:
        path = chain.source_path(film)
        assert sha256_file(path) == chain.original[path], f"source of {film.key} changed"


def files_under(snapshot, prefix):
    return [name for name, state in snapshot.items() if name.startswith(prefix + "/") and state[0] == "file"]


def diag_all(model, kind, count=None):
    """Both path policies: structure (the model's own item indices: a retry round covers only its scope) + canaries."""
    for policy in (PathPolicy.NONE, PathPolicy.BASENAME):
        rendered = diagnostics_bytes(model, policy)
        gate_diagnostics_structure(rendered, schema=DIAGNOSTICS_SCHEMA, schema_version=DIAGNOSTICS_SCHEMA_VERSION,
                                   kind=kind, indices=[i.index for i in model.items])
        if count is not None:
            assert len(model.items) == count
        gate_diagnostics_canaries(rendered, forbidden=corpus.FX5_ALWAYS_FORBIDDEN)


# =========================================================================== S-13


def test_s13_execution_partial_resumes_to_the_one_success_layout(tmp_path):
    """S-13 (L-12, L-13, SI-11, SI-13, SI-08): a cross-volume source removal fails (SOURCE_UNLINK_FAILED) and an NFO
    publish fails -> PARTIAL with a checkpoint -> RESUME; completed effects are not rewritten."""
    unlink_film = success_film("s13-u", "FC2-PPV-3400001.mp4", "FC2-3400001", size=5000)
    nfo_film = success_film("s13-n", "FC2-PPV-3400002.mp4", "FC2-3400002")
    control = success_film("s13-c", "FC2-PPV-3400003.mp4", "FC2-3400003")
    films = [unlink_film, nfo_film, control]
    with Chain(tmp_path, films) as chain:
        chain.force_cross_volume([unlink_film])  # Windows same-volume is one atomic rename: no separate source removal
        preview = chain.preview()
        nfo_item = item_of(preview, nfo_film)
        chain.faults.fail("execution", "unlink", chain.source_path(unlink_film), OSError(errno.EACCES, "locked"))
        chain.faults.fail("materialization", "publish", nfo_item.nfo_target, OSError(errno.EIO, "injected"))
        result = chain.execute(preview)
        chain.faults.assert_all_fired()
        for film in (unlink_film, nfo_film):
            got = item_of(result, film)
            assert got.disposition.value == "executed" and got.execution.status.value == "partial"
            assert got.execution.checkpoint is not None and got.retry_kind.value == "resume"
            assert got.retry_material is not None and got.retry_material.checkpoint is got.execution.checkpoint
        assert result.outcome.value == "partial" and result.summary.partial == 2 and result.summary.success == 1
        unlink_item = item_of(result, unlink_film)
        assert unlink_item.execution.failure.kind.value == "source_unlink_failed"
        assert os.path.exists(chain.source_path(unlink_film)) and os.path.exists(unlink_item.final_media_path)  # both: SI-01
        assert not os.path.exists(nfo_item.nfo_target)  # SI-08: no partial NFO
        assert os.path.exists(item_of(result, nfo_film).final_media_path)
        model = diagnostics_model(result)
        for film in (unlink_film, nfo_film):
            diagnostic = model.items[item_of(result, film).index]
            assert diagnostic.execution.checkpoint_present is True and diagnostic.retry_kind.value == "resume"
            assert diagnostic.execution.status.value == "partial"
        diag_all(result, "execution", 3)
        completed = chain.snapshot()  # inode / mtime of what P4-C7 already completed
        done_files = [name for film in (unlink_film, nfo_film)
                      for name in files_under(completed, f"library/{film.number}")]
        assert done_files
        # RESUME: the preflight carries the very checkpoint the result holds (L-13)
        retry_preview = chain.preview_retry(result, frozenset({RetryKind.RESUME}))
        assert [i.index for i in retry_preview.items] == sorted(item_of(result, f).index for f in (unlink_film, nfo_film))
        for retry_item in retry_preview.items:
            previous = result.items[retry_item.index]
            assert retry_item.state.value == "ready" and retry_item.retry_origin.value == "resume"
            assert retry_item.preflight.mode.value == "resume"
            assert retry_item.preflight.checkpoint is previous.execution.checkpoint
            assert retry_item.media_item is previous.media_item  # identity of the input is preserved
        retry_result = chain.execute(retry_preview)
        assert {i.execution.status.value for i in retry_result.items} == {"success"}
        assert {i.execution.mode.value for i in retry_result.items} == {"resume"}
        after = chain.snapshot()
        gate_entries_unchanged(completed, after, done_files, "SI-13 already completed effects")  # not rewritten
        merged = chain.merge(result, retry_result)
        assert merged.outcome.value == "success" and merged.summary.success == 3 and merged.summary.retryable == 0
        gate_library_exact(chain.library, organized(films))  # == the layout of one successful run
        assert not os.path.exists(chain.source_path(unlink_film))
        diag_all(retry_preview, "preview", 2)
        diag_all(merged, "execution", 3)


# =========================================================================== S-14


def test_s14_execution_failure_without_effect_re_executes_fresh(tmp_path):
    """S-14 (SI-11): a failure before U1 (source revalidation) and an unwritable target directory (EACCES at the seam)
    are FAILED with zero effects and no checkpoint -> FRESH_REEXECUTE -> SUCCESS."""
    before_u1 = success_film("s14-a", "FC2-PPV-3500001.mp4", "FC2-3500001")
    unwritable = success_film("s14-b", "FC2-PPV-3500002.mp4", "FC2-3500002")
    control = success_film("s14-c", "FC2-PPV-3500003.mp4", "FC2-3500003")
    films = [before_u1, unwritable, control]
    with Chain(tmp_path, films) as chain:
        preview = chain.preview()
        chain.faults.fail("execution", "lstat", chain.source_path(before_u1), OSError(errno.EIO, "injected"))
        chain.faults.fail("execution", "mkdir", item_of(preview, unwritable).target_directory,
                          OSError(errno.EACCES, "target not writable"))
        result = chain.execute(preview)
        chain.faults.assert_all_fired()
        for film in (before_u1, unwritable):
            got = item_of(result, film)
            assert got.execution.status.value == "failed" and got.execution.completed_effects == ()
            assert got.execution.checkpoint is None and got.retry_kind.value == "fresh_reexecute"
            assert got.execution.failure.step.value and got.execution.failure.kind.value  # failure step / kind reported
            assert not os.path.exists(os.path.join(chain.library, film.number))  # no target directory
            assert got.retry_material is not None and got.retry_material.checkpoint is None
        assert_sources_in_place(chain, [before_u1, unwritable])
        assert result.outcome.value == "partial" and result.summary.failed == 2
        # P4-C7 section 14: a source that cannot be revalidated before U1 is SOURCE_CHANGED / SOURCE_MISSING; a target directory
        # that cannot be created is DIRECTORY_CREATE_FAILED; both fail at the first step (CREATE_DIRECTORY)
        assert item_of(result, before_u1).execution.failure.kind.value in ("source_changed", "source_missing")
        assert item_of(result, unwritable).execution.failure.kind.value == "directory_create_failed"
        model = diagnostics_model(result)
        for film in (before_u1, unwritable):
            reported = model.items[item_of(result, film).index].execution
            assert reported.failure.kind is item_of(result, film).execution.failure.kind
            assert reported.checkpoint_present is False and reported.new_effect_count == 0
        retry_preview = chain.preview_retry(result, frozenset({RetryKind.FRESH_REEXECUTE}))
        assert {i.preflight.mode.value for i in retry_preview.items} == {"fresh"}
        retry_result = chain.execute(retry_preview)
        assert {i.execution.status.value for i in retry_result.items} == {"success"}
        merged = chain.merge(result, retry_result)
        assert merged.outcome.value == "success"
        gate_library_exact(chain.library, organized(films))
        diag_all(merged, "execution", 3)


# =========================================================================== S-16


def test_s16_unselected_items_are_deferred_and_retry_to_success(tmp_path):
    """S-16: the selection excludes three entries (NOT_SELECTED -> DEFERRED); a deferred round later succeeds."""
    films = [success_film(f"s16-{n}", f"FC2-PPV-360000{n}.mp4", f"FC2-360000{n}") for n in range(6)]
    with Chain(tmp_path, films) as chain:
        preview = chain.preview()
        ready = [i.index for i in preview.items]
        chosen = tuple(ready[0::2])  # entries 0, 2, 4
        result = chain.execute(preview, selection=chosen)
        deferred = [i for i in result.items if i.index not in chosen]
        assert {i.disposition.value for i in deferred} == {"not_selected"} and len(deferred) == 3
        assert {i.retry_kind.value for i in deferred} == {"deferred"} and all(i.execution is None for i in deferred)
        assert all(i.retry_material is not None for i in deferred)
        assert result.summary.not_selected == 3 and result.summary.deferred == 3 and result.summary.success == 3
        assert result.outcome.value == "partial"  # three of six succeeded
        for item in deferred:
            assert sha256_file(item.source_path) == chain.original[item.source_path]
            assert not os.path.exists(item.target_directory)
        assert {diagnostics_model(result).items[i.index].disposition.value for i in deferred} == {"not_selected"}
        retry_preview = chain.preview_retry(result, frozenset({RetryKind.DEFERRED}))
        assert [i.index for i in retry_preview.items] == [i.index for i in deferred]
        retry_result = chain.execute(retry_preview)
        assert retry_result.outcome.value == "success" and retry_result.summary.success == 3
        merged = chain.merge(result, retry_result)
        assert merged.outcome.value == "success" and merged.summary.success == 6 and merged.summary.deferred == 0
        gate_library_exact(chain.library, organized(films))
        diag_all(merged, "execution", 6)


def test_s16_cancellation_stops_admission_only_and_the_cancelled_items_retry(tmp_path):
    """S-16 (cancel): W = 1 and a ``CancellationToken`` set after the second item -> that item completes, the rest are
    CANCELLED (a suffix) and DEFERRED; a retry round finishes them."""
    films = [success_film(f"s16c-{n}", f"FC2-PPV-361000{n}.mp4", f"FC2-361000{n}") for n in range(5)]
    with Chain(tmp_path, films, config=CONFIG_1) as chain:
        preview = chain.preview()
        token = CancellationToken()
        chain.exec_probe.after[2] = token.cancel  # set once the second item has been processed
        result = chain.execute(preview, cancel=token)
        assert token.cancelled
        assert [i.disposition.value for i in result.items] == ["executed", "executed", "cancelled", "cancelled", "cancelled"]
        assert [i.retry_kind.value for i in result.items] == ["none", "none", "deferred", "deferred", "deferred"]
        assert chain.exec_probe.calls == 2  # cancellation only stopped admission; started items ran to their end
        for item in result.items[2:]:
            assert sha256_file(item.source_path) == chain.original[item.source_path] and item.execution is None
        assert result.summary.cancelled == 3 and result.summary.success == 2
        retry_preview = chain.preview_retry(result, frozenset({RetryKind.DEFERRED}))
        retry_result = chain.execute(retry_preview)
        merged = chain.merge(result, retry_result)
        assert merged.outcome.value == "success" and merged.summary.success == 5
        gate_library_exact(chain.library, organized(films))


# =========================================================================== S-17


def _scope_names(scope):
    return None if scope is None else tuple(sorted(kind.value for kind in scope))


def test_s17_retry_chain_over_fx2_with_exact_counts_and_one_time_consumption(tmp_path):
    """S-17 (L-12, L-13, SI-12, SI-22): FX-2, g0 -> g1 {RESUME} -> g2 {METADATA_REFETCH, FRESH_REEXECUTE, PREFLIGHT_RECHECK}
    -> g3 {DEFERRED} -> g4 (scope None); exact per-generation counts, the final layout, consumption errors, diagnostics."""
    plan = corpus.FX2_PLAN
    expected = corpus.mixed_expectations(plan)
    mixed = corpus.MixedCorpus(plan)
    with Chain(tmp_path, mixed.films, config=CONFIG_4) as chain:
        batch = MixedBatch(chain, mixed)
        batch.prepare()
        preview, result = batch.g0()
        g0 = expected["g0_preview"]
        assert (preview.summary.total, preview.summary.ready, preview.summary.blocked, preview.summary.unprepared) == \
            (g0["total"], g0["ready"], g0["blocked"], g0["unprepared"])
        r0 = expected["g0_result"]
        summary = result.summary
        assert (summary.success, summary.partial, summary.failed, summary.aborted, summary.not_selected) == \
            (r0["success"], r0["partial"], r0["failed"], r0["aborted"], r0["not_selected"])
        assert (summary.retryable, summary.deferred, summary.non_retryable) == \
            (r0["retryable"], r0["deferred"], r0["non_retryable"]) and result.outcome.value == r0["outcome"]
        kinds = {}
        for item in result.items:
            kinds[item.retry_kind.value] = kinds.get(item.retry_kind.value, 0) + 1
        assert {k: v for k, v in kinds.items() if k in r0["kinds"]} == r0["kinds"]
        models = [(preview, "preview"), (result, "execution")]
        previous, rounds = result, []
        for name in ("g1", "g2", "g3", "g4"):
            if name == "g2":
                removed = batch.user_removes_blockers()
                assert len(removed) == plan.g_removed
            want = expected[name]
            scope = {"g1": frozenset({RetryKind.RESUME}),
                     "g2": frozenset({RetryKind.METADATA_REFETCH, RetryKind.FRESH_REEXECUTE, RetryKind.PREFLIGHT_RECHECK}),
                     "g3": frozenset({RetryKind.DEFERRED}), "g4": None}[name]
            assert _scope_names(scope) == (None if want["scope"] is None else tuple(sorted(want["scope"])))
            retry_preview = chain.preview_retry(previous, scope)
            assert retry_preview.generation == int(name[1]) and retry_preview.base_result_id == previous.result_id
            assert len(retry_preview.items) == want["items"]
            rs = retry_preview.summary
            assert (rs.ready, rs.blocked, rs.unprepared) == (want["ready"], want["blocked"], want["unprepared"])
            retry_result = chain.execute(retry_preview)
            assert retry_result.summary.success == want["success"] and retry_result.outcome.value == want["outcome"]
            assert retry_result.retry_scope == (scope if scope is not None else retry_result.retry_scope)
            for retried in retry_result.items:  # identity of every retried input is the previous item's
                assert retried.media_item is previous.items[retried.index].media_item
            merged = chain.merge(previous, retry_result)
            assert merged.summary.success == want["merged_success"] and merged.generation == int(name[1])
            with pytest.raises(OrchestrationConsumedError):  # SI-12: a result is retried once, a retry result merged once
                chain.run(chain.orchestrator.preview_retry(previous, scope=scope))
            with pytest.raises(OrchestrationConsumedError):
                merge_retry(previous, retry_result)
            models += [(retry_preview, "preview"), (retry_result, "execution"), (merged, "execution")]
            previous = merged
            rounds.append((retry_preview, retry_result, merged))
        final = expected["final"]
        assert (previous.summary.success, previous.summary.blocked, previous.summary.unprepared,
                previous.summary.aborted) == (final["success"], final["blocked"], final["unprepared"], final["aborted"])
        assert previous.outcome.value == final["outcome"] and previous.summary.retryable == final["retryable"]
        organized_films, user_files, empty = batch.final_library_expectation()
        gate_library_exact(chain.library, organized_films, user_files=user_files, empty_directories=empty)
        in_place = sum(1 for film in mixed.films if os.path.exists(chain.source_path(film)))
        assert in_place == final["sources_in_place"]
        assert len(models) == 14
        for model, kind in models:  # diagnostics of every generation: 14 models, both policies
            diag_all(model, kind)
        assert chain.gate_runs["SI-01"] == 5 and chain.gate_runs["SI-21"] == 5  # g0 + four retry rounds, each gated
