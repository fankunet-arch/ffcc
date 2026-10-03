"""P4-C10 S2: non-vacuity / mutation gate M-01..M-14 (contract section 11; EC-07).

Every mutant lives in the test process only (``pytest.MonkeyPatch.context``): it wraps or replaces a binding on the
surfaces allowed by contract section 11.3 and never writes a production source file. For each mutant:

1. the positive control -- the same scenario without the mutant -- passes;
2. with the mutant installed the scenario raises ``AcceptanceGateViolation`` (the named gate caught it);
3. after the test the replaced binding is the very original object again (``is``).

The scenarios use only the shared gates / independent oracles, so a kill is the gate's own verdict.
"""

from __future__ import annotations

import dataclasses
import json
import os
import secrets

import pytest

from . import _corpus as corpus
from . import _harness as harness
from ._corpus import expectation, fail_outcome, success_film, with_outcomes
from ._harness import CONFIG_2, CONFIG_4, Chain, MixedBatch, diagnostics_bytes, transfer_operation
from ._oracles import (
    AcceptanceGateViolation,
    gate_default_output_clean,
    gate_deterministic_equal,
    gate_diagnostics_canaries,
    gate_entries_unchanged,
    gate_library_exact,
    gate_peak,
    gate_phase_a_conflicts,
    snapshot_tree,
)
from fc2_metadata_core.aggregation import AggregationPolicy, MultiSourceEngine, merge_source_results
from fc2_metadata_core.models.source_result import SourceStatus
from fc2_organizer.diagnostics import PathPolicy
from fc2_organizer.execution import _fs as execution_fs
from fc2_organizer.orchestration import ItemExecution, RetryKind
from fc2_organizer.orchestration import execute as orchestration_execute
from fc2_organizer.orchestration import preview as preview_module
from fc2_organizer.orchestration import stages as stages_module
from support.scripted_adapters import failed as scripted_failed


def organized(films, call=0):
    return [(film, *expectation(film, call)) for film in films]


def drive(root, films, body, apply=None, **chain_kwargs):
    """Build a chain; apply the mutant (if any) inside a monkeypatch context that ends before the chain is closed."""
    with Chain(root, films, **chain_kwargs) as chain:
        with pytest.MonkeyPatch.context() as patch:
            if apply is not None:
                apply(patch, chain)
            return body(chain)


def kill(tmp_path, films, body, apply, bindings, gate, setup=None, **chain_kwargs):
    """Positive control, then the mutant (must raise ``AcceptanceGateViolation`` *from the named gate*), then the
    restoration proof."""
    before = [getattr(owner, name) for owner, name in bindings]

    def with_setup(patch, chain):
        if setup is not None:
            setup(patch, chain)

    drive(tmp_path / "control", films, body, with_setup, **chain_kwargs)  # 1. the clean scenario passes

    def mutant(patch, chain):
        with_setup(patch, chain)
        apply(patch, chain)

    with pytest.raises(AcceptanceGateViolation) as caught:  # 2. the mutant is caught by a gate ...
        drive(tmp_path / "mutant", films, body, mutant, **chain_kwargs)
    assert gate in str(caught.value), f"killed by another gate than {gate}: {caught.value}"  # ... the named one
    after = [getattr(owner, name) for owner, name in bindings]  # 3. every replaced binding is the original again
    assert all(a is b for a, b in zip(after, before))


EXECUTE = (orchestration_execute, "execute_filesystem")
FILMS3 = list(corpus.FX1_FILMS[:3])


def success_body(films):
    def body(chain):
        preview = chain.preview()
        result = chain.execute(preview)
        assert result.outcome.value == "success"
        gate_library_exact(chain.library, organized(films))  # layout, NFO, image / media bytes
    return body


# =========================================================================== M-01 .. M-04


def test_m01_source_loss_after_a_reported_success_is_caught_by_si01(tmp_path):
    """M-01: ``execute_filesystem`` deletes the final media of one entry after the real call reported SUCCESS."""
    victim = FILMS3[1]

    def apply(patch, chain):
        real = orchestration_execute.execute_filesystem

        def mutant(preflight):
            result = real(preflight)
            if result.status.value == "success" and preflight.plan.source_path == chain.source_path(victim):
                media = [e.path for e in result.completed_effects if e.kind.value == "media_published"][0]
                os.remove(media)
            return result

        patch.setattr(orchestration_execute, "execute_filesystem", mutant)

    kill(tmp_path, FILMS3, success_body(FILMS3), apply, [EXECUTE], "SI-01")


def test_m02_overwrite_by_a_replacing_transfer_primitive_is_caught_by_si02(tmp_path):
    """M-02: the media transfer primitive (``_FS.rename`` on Windows, the link primitive elsewhere) is replaced by a
    replacing ``os.replace``; a user file appears at the final media path after U1 (a concurrent creator)."""
    films = FILMS3[:2]
    holder = {}

    def setup(patch, chain):
        """A user file appears at the final media path *after* the executor's own "final path is absent" check passed (a
        concurrent creator): the early exit cannot see it, only the no-replace primitive stands between it and the media."""
        real_fs = execution_fs._FS
        victim = films[0]
        directory = os.path.join(chain.library, victim.number)
        occupant = os.path.join(directory, f"{victim.number}{victim.extension}")

        def lstat(path, *args, **kwargs):
            try:
                return real_fs.lstat(path, *args, **kwargs)
            except FileNotFoundError:
                if (chain.faults.armed and not holder and os.path.normcase(path) == os.path.normcase(occupant)
                        and os.path.isdir(directory)):
                    with chain.observer.paused():
                        with open(occupant, "wb") as handle:
                            handle.write(b"the user's file at the final path")
                        holder["snapshot"] = snapshot_tree(chain.root)
                        holder["relative"] = os.path.relpath(occupant, chain.root).replace(os.sep, "/")
                raise

        patch.setattr(execution_fs, "_FS", dataclasses.replace(real_fs, lstat=lstat))

    def apply(patch, chain):
        replacing = lambda source, target, *a, **k: os.replace(source, target)  # noqa: E731
        patch.setattr(execution_fs, "_FS", dataclasses.replace(execution_fs._FS, **{transfer_operation(): replacing}))

    def body(chain):
        preview = chain.preview()
        chain.execute(preview)
        assert holder, "the occupant was never created (vacuous scenario)"
        gate_entries_unchanged(holder["snapshot"], chain.snapshot(), [holder["relative"]], "SI-02 overwrite = NEVER")

    kill(tmp_path, films, body, apply, [(execution_fs, "_FS")], "SI-02", setup=setup)


def test_m03_a_disabled_phase_a_conflict_check_is_caught_by_si10(tmp_path):
    """M-03: the recognition binding bound in ``preview`` loses its conflict marks."""
    control = success_film("m3-ok", "FC2-PPV-4300000.mp4", "FC2-4300000")
    dup_a = success_film("m3-a", "FC2-PPV-4300001.mp4", "FC2-4300001", directory="a")
    dup_b = success_film("m3-b", "FC2PPV4300001.mkv", "FC2-4300001", directory="b")
    films = [control, dup_a, dup_b]

    def apply(patch, chain):
        real = preview_module.recognize

        def mutant(snapshot):
            return [dataclasses.replace(r, reason=None, conflict_with=())
                    if r.reason is not None and r.reason.value.startswith("duplicate") else r for r in real(snapshot)]

        patch.setattr(preview_module, "recognize", mutant)

    def body(chain):
        preview = chain.preview()
        pair = [i.index for i in preview.items if i.canonical_number == "FC2-4300001"]
        assert len(pair) == 2
        gate_phase_a_conflicts(preview, chain.sources.numbers_called, [pair])

    kill(tmp_path, films, body, apply, [(preview_module, "recognize")], "SI-10")


def test_m04_a_write_outside_the_target_directory_is_caught_by_si15(tmp_path):
    """M-04: ``execute_filesystem`` creates a file next to the library (inside the tmp tree, outside the target)."""

    def apply(patch, chain):
        real = orchestration_execute.execute_filesystem

        def mutant(preflight):
            result = real(preflight)
            with open(os.path.join(chain.root, "escaped.bin"), "wb") as handle:
                handle.write(b"outside the library")
            return result

        patch.setattr(orchestration_execute, "execute_filesystem", mutant)

    kill(tmp_path, FILMS3, success_body(FILMS3), apply, [EXECUTE], "SI-15")


# =========================================================================== M-05 .. M-07


def test_m05_swapped_retry_kinds_are_caught_by_si12(tmp_path):
    """M-05: ``ItemExecution.retry_kind`` reports FRESH_REEXECUTE for RESUME and the other way round (active once the
    results exist, i.e. what every consumer -- and the shared gate -- reads afterwards)."""
    mixed = corpus.MixedCorpus(corpus.FX2_PLAN)
    original = ItemExecution.retry_kind
    state = {}

    def apply(patch, chain):
        swap = {RetryKind.RESUME: RetryKind.FRESH_REEXECUTE, RetryKind.FRESH_REEXECUTE: RetryKind.RESUME}

        def getter(self):
            kind = original.fget(self)
            return swap.get(kind, kind)

        state["activate"] = lambda: patch.setattr(ItemExecution, "retry_kind", property(getter))

    def body(chain):
        batch = MixedBatch(chain, mixed)
        batch.prepare()
        _preview, result = batch.g0()
        if "activate" in state:
            state["activate"]()
        chain.round_gates(result)  # SI-12: the retry kinds are recomputed from the frozen table and compared

    kill(tmp_path, mixed.films, body, apply, [(ItemExecution, "retry_kind")], "SI-12", config=CONFIG_4)


def _partial_films():
    return [success_film(f"m6-{n}", f"FC2-PPV-460000{n}.mp4", f"FC2-460000{n}") for n in range(3)]


def _resume_body(films):
    def body(chain):
        preview = chain.preview()
        for film in films[:2]:  # two entries end PARTIAL: an NFO publish fails
            item = next(i for i in preview.items if i.canonical_number == film.number)
            chain.faults.fail("materialization", "publish", item.nfo_target, OSError(5, "injected"))
        result = chain.execute(preview)
        chain.faults.assert_all_fired()
        retry_preview = chain.preview_retry(result, frozenset({RetryKind.RESUME}))  # the SI-13 gate runs inside
        retry_result = chain.execute(retry_preview)
        chain.merge(result, retry_result)
        gate_library_exact(chain.library, organized(films))  # == one successful run
    return body


def test_m06_a_foreign_checkpoint_is_caught_by_si13(tmp_path):
    """M-06: for the second PARTIAL result the checkpoint is replaced by the first entry's checkpoint."""
    films = _partial_films()

    def apply(patch, chain):
        real = orchestration_execute.execute_filesystem
        seen = []

        def mutant(preflight):
            result = real(preflight)
            if result.status.value == "partial":
                if seen:
                    object.__setattr__(result, "checkpoint", seen[0])
                else:
                    seen.append(result.checkpoint)
            return result

        patch.setattr(orchestration_execute, "execute_filesystem", mutant)

    kill(tmp_path, films, _resume_body(films), apply, [EXECUTE], "SI-13")


def test_m07_a_corrupted_merge_is_caught_by_si22(tmp_path):
    """M-07: the merge binding used by the scenario substitutes a stale (previous generation) item for a retried one."""
    films = _partial_films()

    def apply(patch, chain):
        real = harness.merge_retry

        def mutant(previous, retry):
            merged = real(previous, retry)
            items = list(merged.items)
            index = retry.items[0].index
            items[index] = previous.items[index]
            return dataclasses.replace(merged, items=tuple(items))

        patch.setattr(harness, "merge_retry", mutant)

    kill(tmp_path, films, _resume_body(films), apply, [(harness, "merge_retry")], "SI-22")


# =========================================================================== M-08 .. M-10


def _fx5_body(chain):
    preview = chain.preview()
    result = chain.execute(preview)
    for model in (preview, result):
        none = diagnostics_bytes(model)
        gate_diagnostics_canaries(none, forbidden=corpus.FX5_ALWAYS_FORBIDDEN)
        gate_default_output_clean(none)
        gate_diagnostics_canaries(diagnostics_bytes(model, PathPolicy.BASENAME), forbidden=corpus.FX5_ALWAYS_FORBIDDEN)


def test_m08_diagnostics_that_leak_a_canary_are_caught_by_si18(tmp_path):
    """M-08 (a): the rendering binding appends class A text to every document."""
    films = list(corpus.fx5_films())

    def apply(patch, chain):
        real = harness.render_diagnostics_json

        def mutant(diagnostics):
            tree = json.loads(real(diagnostics))
            tree["note"] = f"leaked {corpus.FX5_CANARIES['auth']}"
            return json.dumps(tree, sort_keys=True, separators=(",", ":")).encode("ascii")

        patch.setattr(harness, "render_diagnostics_json", mutant)

    kill(tmp_path, films, _fx5_body, apply, [(harness, "render_diagnostics_json")], "SI-18",
         library_name=corpus.FX5_CANARIES["root"])


def test_m08_a_default_path_policy_of_basename_is_caught_by_si18(tmp_path):
    """M-08 (b): the preview builder binding is forced to ``PathPolicy.BASENAME`` (secret-like names would be emitted)."""
    films = list(corpus.fx5_films())

    def apply(patch, chain):
        real = harness.build_preview_diagnostics
        patch.setattr(harness, "build_preview_diagnostics",
                      lambda preview, **kw: real(preview, **{**kw, "path_policy": PathPolicy.BASENAME}))

    kill(tmp_path, films, _fx5_body, apply, [(harness, "build_preview_diagnostics")], "SI-18",
         library_name=corpus.FX5_CANARIES["root"])


def test_m09_swapped_poster_and_fanart_are_caught_by_the_image_bytes_oracle(tmp_path):
    """M-09 (a): the manifest builder binding exchanges the poster and fanart contents (L-10)."""

    def apply(patch, chain):
        real = stages_module.build_artifact_requests

        def mutant(plan, nfo_text, images):
            requests = real(plan, nfo_text, images)
            kinds = {r.kind.value: n for n, r in enumerate(requests)}
            if "poster" not in kinds or "fanart" not in kinds:
                return requests
            out = list(requests)
            p, f = kinds["poster"], kinds["fanart"]
            out[p] = dataclasses.replace(requests[p], content=requests[f].content)
            out[f] = dataclasses.replace(requests[f], content=requests[p].content)
            return tuple(out)

        patch.setattr(stages_module, "build_artifact_requests", mutant)

    kill(tmp_path, FILMS3, success_body(FILMS3), apply, [(stages_module, "build_artifact_requests")], "layout")


def test_m09_an_nfo_rendered_for_another_entry_is_caught_by_the_nfo_oracle(tmp_path):
    """M-09 (b): the NFO renderer binding renders the first entry's record for every entry (L-08)."""

    def apply(patch, chain):
        real = stages_module.render_movie_nfo
        first = []

        def mutant(record):
            first.append(record) if not first else None
            return real(first[0])

        patch.setattr(stages_module, "render_movie_nfo", mutant)

    kill(tmp_path, FILMS3, success_body(FILMS3), apply, [(stages_module, "render_movie_nfo")], "layout")


def test_m10_output_that_follows_the_completion_order_is_caught_by_si07(tmp_path):
    """M-10: the diagnostics rendering binding orders items by the completion order of the engine stage."""
    films = list(corpus.FX1_FILMS)
    runs = []

    def run(root, reverse, mutate):
        with Chain(root, films, config=CONFIG_4, reverse=reverse) as chain:
            with pytest.MonkeyPatch.context() as patch:
                if mutate:
                    real = harness.render_diagnostics_json

                    def mutant(diagnostics):
                        tree = json.loads(real(diagnostics))
                        order = chain.sources.completion_order
                        tree["items"].sort(key=lambda item: order.index(item["canonical_number"])
                                           if item["canonical_number"] in order else len(order))
                        return json.dumps(tree, sort_keys=True, separators=(",", ":")).encode("ascii")

                    patch.setattr(harness, "render_diagnostics_json", mutant)
                preview = chain.preview()
                result = chain.execute(preview)
                return diagnostics_bytes(preview), diagnostics_bytes(result)

    before = harness.render_diagnostics_json
    gate_deterministic_equal(run(tmp_path / "c1", False, False), run(tmp_path / "c2", True, False))  # control passes
    with pytest.raises(AcceptanceGateViolation) as caught:
        gate_deterministic_equal(run(tmp_path / "m1", False, True), run(tmp_path / "m2", True, True))
    assert "SI-07" in str(caught.value)
    assert harness.render_diagnostics_json is before
    assert runs == []


# =========================================================================== M-11 .. M-14


def test_m11_a_thread_per_entry_is_caught_by_si06(tmp_path):
    """M-11: the concurrency entry of the execution stage is wrapped to start one worker per entry."""
    films = list(corpus.FX1_FILMS[:8])
    real = orchestration_execute._execute_threaded

    def body(chain):
        preview = chain.preview()
        chain.execute(preview)
        gate_peak(chain.exec_probe.peak, limit=2, expect_reached=True)

    def apply(patch, chain):
        chain.exec_probe.target = 3  # the mutant has the threads to reach three at once; the budget is two
        patch.setattr(orchestration_execute, "_execute_threaded", lambda items, cancel, workers: real(items, cancel, len(items)))

    kill(tmp_path, films, body, apply, [(orchestration_execute, "_execute_threaded")], "SI-06", config=CONFIG_2,
         hold_exec=2)


def test_m12_one_failing_source_failing_the_film_is_caught_by_si04(tmp_path):
    """M-12: the real ``MultiSourceEngine.aggregate`` returns FAILED as soon as any source did not succeed."""
    film = with_outcomes(success_film("m12", "FC2-PPV-4120001.mp4", "FC2-4120001"),
                         {"fc2db_net": (fail_outcome("BLOCKED"),)})

    def apply(patch, chain):
        real = MultiSourceEngine.aggregate

        async def mutant(self, number):
            result = await real(self, number)
            if any(r.status is not SourceStatus.SUCCESS for r in result.source_results):
                failed = [scripted_failed(sid, SourceStatus.NETWORK_ERROR) for sid in corpus.SOURCE_IDS]
                return merge_source_results(number, failed, AggregationPolicy.build(corpus.SOURCE_IDS))
            return result

        patch.setattr(MultiSourceEngine, "aggregate", mutant)

    def body(chain):
        chain.preview()  # the SI-04 gate compares the metadata status with the independent merge definition

    kill(tmp_path, [film], body, apply, [(MultiSourceEngine, "aggregate")], "SI-04")


def test_m13_an_unreported_temporary_file_is_caught_by_si14(tmp_path):
    """M-13: ``execute_filesystem`` leaves a ``.fc2tmp-<32hex>.part`` in the target directory without reporting it."""

    def apply(patch, chain):
        real = orchestration_execute.execute_filesystem

        def mutant(preflight):
            result = real(preflight)
            directory = preflight.plan.target_directory.absolute_path
            with open(os.path.join(directory, f".fc2tmp-{secrets.token_hex(16)}.part"), "wb") as handle:
                handle.write(b"left behind")
            return result

        patch.setattr(orchestration_execute, "execute_filesystem", mutant)

    kill(tmp_path, FILMS3, success_body(FILMS3), apply, [EXECUTE], "SI-14")


def test_m14_a_directory_created_by_a_preview_stage_is_caught_by_si21(tmp_path):
    """M-14: the read-only preflight stage binding of ``preview`` creates a directory."""

    def apply(patch, chain):
        real = preview_module.preflight_stage

        def mutant(*args, **kwargs):
            os.makedirs(os.path.join(chain.library, "created-by-a-preview-stage"), exist_ok=True)
            return real(*args, **kwargs)

        patch.setattr(preview_module, "preflight_stage", mutant)

    def body(chain):
        chain.preview()

    kill(tmp_path, FILMS3, body, apply, [(preview_module, "preflight_stage")], "SI-21")
