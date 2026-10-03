"""P4-C10 S2: filesystem-safety scenarios S-10, S-11, S-15, S-21 and the central assertions of the Phase 4 Safety Invariant
Matrix SI-01..SI-22 (contract sections 6, 7.2).

Everything runs on disposable ``tmp_path`` trees (FX-3). The user's pre-existing entries are compared by bytes, size,
mtime and inode before / after; faults are injected only through the authorized ``_FS`` seams, one-shot and per entry,
and every injection is proven to have fired.
"""

from __future__ import annotations

import ast
import errno
import os
import pathlib
import re

import pytest

try:  # Windows only: creates a directory junction without a subprocess or an elevated privilege
    import _winapi
except ImportError:  # pragma: no cover - POSIX
    _winapi = None

from . import _corpus as corpus
from ._corpus import expectation, success_film
from ._harness import CONFIG_4, Chain, MixedBatch, diagnostics_bytes, diagnostics_model, transfer_operation
from ._oracles import (
    AcceptanceGateViolation,
    gate_diagnostics_canaries,
    gate_entries_unchanged,
    gate_library_exact,
    gate_no_network,
    gate_phase_a_conflicts,
    gate_repository_unmodified,
    gate_snapshots_equal,
    repository_digest,
    sha256_file,
)
from fc2_organizer.diagnostics import PathPolicy
from fc2_organizer.orchestration import BatchOrchestrator

UNRELATED_TEMP = ".fc2tmp-" + "0" * 31 + "1.part"


def organized(films, call=0):
    return [(film, *expectation(film, call)) for film in films]


def item_of(model, film):
    return next(i for i in model.items if i.canonical_number == film.number)


def assert_sources_in_place(chain, films):
    for film in films:
        path = chain.source_path(film)
        assert sha256_file(path) == chain.original[path], f"source of {film.key} changed"


def install_fx3(chain):
    """FX-3 user entries inside the disposable library: a user movie directory and unrelated look-alike temporaries.
    Returns the relative paths (relative to the acceptance root) of every user entry for before / after comparison."""
    files = {
        "FC2-0000001-user/keep.mp4": b"the user's own movie",
        "_user/user-file.txt": b"user text",
        "_user/unrelated.part": b"not ours .part",
        "_user/unrelated.tmp": b"not ours .tmp",
        f"_user/{UNRELATED_TEMP}": b"looks like a P4-C6 temporary but is the user's",
    }
    for relative, data in files.items():
        chain.user_write(os.path.join(chain.library, *relative.split("/")), data)
    chain.preexisting_temporaries.add(f"library/_user/{UNRELATED_TEMP}")
    paths = ["library/" + relative for relative in files] + ["library/FC2-0000001-user", "library/_user"]
    return files, paths


# =========================================================================== S-10


def test_s10_in_batch_conflicts_block_every_member_and_select_no_winner(tmp_path):
    """S-10 (SI-10): two directories with one number; one discovered item twice; a hard-link pair (different numbers)."""
    control = success_film("s10-ok", "FC2-PPV-3000000.mp4", "FC2-3000000")
    dup_a = success_film("s10-da", "FC2-PPV-3000001.mp4", "FC2-3000001", directory="dup-a")
    dup_b = success_film("s10-db", "FC2PPV3000001.mkv", "FC2-3000001", directory="dup-b")
    twice = success_film("s10-tw", "FC2-PPV-3000002.mp4", "FC2-3000002")
    link_a = success_film("s10-la", "FC2-PPV-3000003.mp4", "FC2-3000003", directory="link")
    link_b = success_film("s10-lb", "FC2-PPV-3000004.mp4", "FC2-3000004", directory="link")
    films = [control, dup_a, dup_b, twice, link_a, link_b]
    with Chain(tmp_path, films) as chain:
        chain.user_hardlink(chain.source_path(link_a), chain.source_path(link_b))
        assert os.path.samefile(chain.source_path(link_a), chain.source_path(link_b))
        discovered = chain.discover()
        again = next(i for i in discovered if os.path.basename(i.source_path) == twice.filename)
        items = tuple(discovered) + (again,)
        assert len(items) == 7
        preview = chain.preview(items)
        reasons = {}
        for item in preview.items:
            if item.canonical_number is not None:
                reasons.setdefault(item.canonical_number, []).append(item)
        phase_a = reasons["FC2-3000001"] + reasons["FC2-3000002"]
        assert len(phase_a) == 4
        assert {i.issue.reason.value for i in reasons["FC2-3000001"]} == {"duplicate_target_in_batch"}
        assert {i.issue.reason.value for i in reasons["FC2-3000002"]} == {"duplicate_source_in_batch"}
        assert all(i.state.value == "blocked" and i.metadata is None and i.preflight is None for i in phase_a)
        gate_phase_a_conflicts(preview, chain.sources.numbers_called,  # Phase A: no metadata, no preflight, engine not asked
                               [[i.index for i in reasons["FC2-3000001"]], [i.index for i in reasons["FC2-3000002"]]])
        assert not {"FC2-3000001", "FC2-3000002"} & set(chain.sources.numbers_called)  # Phase A: the engine is never asked
        for member in phase_a:  # symmetric conflict graph
            for peer in member.conflict_with:
                assert member.index in preview.items[peer].conflict_with
        phase_b = reasons["FC2-3000003"] + reasons["FC2-3000004"]  # the hard-link pair: found by (device, inode) in Phase B
        assert {i.issue.reason.value for i in phase_b} == {"duplicate_source_in_batch"}
        assert all(i.preflight is not None and i.metadata is not None for i in phase_b)
        assert {"FC2-3000003", "FC2-3000004"} <= set(chain.sources.numbers_called)
        assert item_of(preview, control).state.value == "ready"
        result = chain.execute(preview)
        for item in result.items:
            if item.canonical_number == control.number:
                assert item.execution.status.value == "success"
            else:
                assert item.disposition.value == "not_ready" and item.retry_kind.value == "none"
        for number in ("FC2-3000001", "FC2-3000002", "FC2-3000003", "FC2-3000004"):  # nobody won: nothing was created
            assert not os.path.exists(os.path.join(chain.library, number))
        assert_sources_in_place(chain, [dup_a, dup_b, twice, link_a, link_b])
        gate_library_exact(chain.library, organized([control]))
        model = diagnostics_model(preview)
        assert all(model.items[i.index].conflict_with == i.conflict_with for i in preview.items)
        assert gate_diag(preview) and gate_diag(result)


def gate_diag(model):
    """The diagnostics of ``model`` render under both path policies without any class A canary."""
    for policy in (PathPolicy.NONE, PathPolicy.BASENAME):
        gate_diagnostics_canaries(diagnostics_bytes(model, policy), forbidden=corpus.FX5_ALWAYS_FORBIDDEN)
    return True


# =========================================================================== S-11


def test_s11_preflight_blocker_leaves_user_entries_untouched_and_rechecks_after_removal(tmp_path):
    """S-11 (SI-02, SI-21): the target directory already exists (with ``user-note.txt``) -> BLOCKED PREFLIGHT_BLOCKED ->
    PREFLIGHT_RECHECK; the test removes it as the user, the recheck succeeds."""
    control = success_film("s11-ok", "FC2-PPV-3100001.mp4", "FC2-3100001")
    blocked = success_film("s11-bl", "FC2-PPV-3100002.mp4", "FC2-3100002")
    with Chain(tmp_path, [control, blocked], config=CONFIG_4) as chain:
        user_files, user_paths = install_fx3(chain)
        chain.user_write(os.path.join(chain.library, blocked.number, "user-note.txt"), b"mine")
        entries = user_paths + [f"library/{blocked.number}", f"library/{blocked.number}/user-note.txt"]
        before = chain.snapshot()
        preview = chain.preview()
        item = item_of(preview, blocked)
        assert item.state.value == "blocked" and (item.issue.stage.value, item.issue.reason.value) == \
            ("preflight", "preflight_blocked")
        assert item.preflight.ready is False and "target_directory_exists" in {b.reason.value for b in item.preflight.blockers}
        assert item_of(preview, control).state.value == "ready"
        diagnostic = diagnostics_model(preview).items[item.index]
        assert diagnostic.preflight.ready is False and diagnostic.preflight.blockers
        result = chain.execute(preview)
        blocked_result = item_of(result, blocked)
        assert blocked_result.disposition.value == "not_ready" and blocked_result.retry_kind.value == "preflight_recheck"
        assert blocked_result.retry_material is not None  # the retained plan / artifacts for the recheck
        assert item_of(result, control).execution.status.value == "success"
        after = chain.snapshot()
        gate_entries_unchanged(before, after, entries, "SI-02 / S-11 user entries")  # bytes, size, mtime, inode
        assert_sources_in_place(chain, [blocked])
        # the user removes the blocking directory; the recheck now succeeds
        chain.user_remove_tree(os.path.join(chain.library, blocked.number))
        retry_preview = chain.preview_retry(result)
        retry_item = retry_preview.items[0]
        assert retry_item.state.value == "ready" and retry_item.retry_origin.value == "preflight_recheck"
        retry_result = chain.execute(retry_preview)
        assert retry_result.items[0].execution.status.value == "success"
        merged = chain.merge(result, retry_result)
        assert merged.outcome.value == "success" and merged.summary.success == 2
        gate_library_exact(chain.library, organized([control, blocked]),
                           user_files={k: v for k, v in user_files.items() if k != f"_user/{UNRELATED_TEMP}"} | {
                               f"_user/{UNRELATED_TEMP}": user_files[f"_user/{UNRELATED_TEMP}"]})


# =========================================================================== S-15


def test_s15_a_foreign_exception_aborts_one_item_and_not_the_batch(tmp_path):
    """S-15 (SI-05, SI-11): U2 raises ``RuntimeError('C10CANARY-EXC')`` for one entry; the other entries are organized."""
    films = [success_film(f"s15-{n}", f"FC2-PPV-315000{n}.mp4", f"FC2-315000{n}") for n in range(3)]
    victim = films[1]
    with Chain(tmp_path, films) as chain:
        preview = chain.preview()
        chain.faults.fail("execution", transfer_operation(), chain.source_path(victim),
                          RuntimeError(corpus.FX5_CANARIES["exc"]))
        result = chain.execute(preview)
        chain.faults.assert_all_fired()
        aborted = item_of(result, victim)
        assert aborted.disposition.value == "aborted" and aborted.execution is None
        assert (aborted.issue.stage.value, aborted.issue.reason.value, aborted.issue.error_type) == \
            ("execution", "execution_aborted", "RuntimeError")
        assert aborted.retry_kind.value == "none" and aborted.retry_material is None
        assert {item_of(result, f).execution.status.value for f in films if f is not victim} == {"success"}
        summary = result.summary
        assert (summary.aborted, summary.success) == (1, 2) and result.outcome.value == "partial"  # ABORTED never success
        target = os.path.join(chain.library, victim.number)
        assert os.path.isdir(target) and os.listdir(target) == []  # the empty target directory is there, truthfully
        assert_sources_in_place(chain, [victim])  # SI-01 for the aborted entry, explicitly
        assert corpus.FX5_CANARIES["exc"] not in repr(aborted)
        assert gate_diag(result)
        assert diagnostics_model(result).items[victim_index(result, victim)].issue.error_type == "RuntimeError"
        gate_library_exact(chain.library, organized([f for f in films if f is not victim]),
                           empty_directories=[victim.number])


def victim_index(result, film):
    return item_of(result, film).index


# =========================================================================== S-21


def test_s21_user_entries_and_case_variants_are_never_overwritten_or_renamed(tmp_path):
    """S-21 (SI-02, SI-14, SI-16): user movie directory, look-alike temporaries and a case-variant target directory.
    NTFS is case-insensitive, so the variant blocks the entry there; on POSIX it is a different directory."""
    plain = success_film("s21-ok", "FC2-PPV-3210001.mp4", "FC2-3210001")
    variant = success_film("s21-cv", "FC2-PPV-3210002.mp4", "FC2-3210002")
    with Chain(tmp_path, [plain, variant]) as chain:
        user_files, user_paths = install_fx3(chain)
        variant_directory = os.path.join(chain.library, variant.number.lower())  # fc2-3210002
        chain.user_write(os.path.join(variant_directory, "user-note.txt"), b"variant")
        entries = user_paths + [f"library/{variant.number.lower()}", f"library/{variant.number.lower()}/user-note.txt"]
        before = chain.snapshot()
        preview = chain.preview()
        result = chain.execute(preview)
        after = chain.snapshot()
        gate_entries_unchanged(before, after, entries, "S-21 user entries")
        blocks = os.name == "nt"  # an existing case variant is "the target directory already exists" on NTFS only
        item = item_of(result, variant)
        if blocks:
            assert item.disposition.value == "not_ready" and item.retry_kind.value == "preflight_recheck"
            assert item_of(preview, variant).issue.reason.value == "preflight_blocked"
            assert_sources_in_place(chain, [variant])
        else:
            assert item.execution.status.value == "success"
        assert item_of(result, plain).execution.status.value == "success"
        # no link was followed, nothing was renamed or suffixed: the only entries are the expected ones
        names = sorted(os.listdir(chain.library))
        expected = sorted(["FC2-0000001-user", "_user", plain.number, variant.number.lower()]
                          + ([] if blocks else [variant.number]))
        assert names == expected
        assert chain.observer.take() == []  # nothing happened after the round's gates (and no write was missed)


@pytest.mark.skipif(os.name != "nt" or _winapi is None, reason="Windows-only: directory junction library root (contract 8.1)")
def test_s21_junction_library_root_is_refused_and_nothing_is_followed(tmp_path):
    """S-21 (SI-16, Windows native): a junction as library root blocks every entry; zero modification."""
    films = [success_film(f"s21j-{n}", f"FC2-PPV-322000{n}.mp4", f"FC2-322000{n}") for n in range(2)]
    with Chain(tmp_path, films) as chain:
        real_target = os.path.join(chain.root, "junction-target")
        junction = os.path.join(chain.root, "library-junction")
        chain.user_mkdir(real_target)
        with chain.user_action():
            _winapi.CreateJunction(real_target, junction)
        chain.sandbox.require(junction, "junction library root")
        orchestrator = BatchOrchestrator(chain.engine, chain.client, junction, config=chain.config)
        before = chain.snapshot()
        preview = chain.preview(orchestrator=orchestrator)
        assert {i.state.value for i in preview.items} == {"blocked"}
        assert {i.issue.reason.value for i in preview.items} == {"preflight_blocked"}
        result = chain.execute(preview, orchestrator=orchestrator)
        assert {i.retry_kind.value for i in result.items} == {"preflight_recheck"}
        assert os.listdir(real_target) == []  # nothing was written through the junction
        assert_sources_in_place(chain, films)
        gate_snapshots_equal(before, chain.snapshot(), "S-21 junction root: zero modification")


# =========================================================================== SI-01 .. SI-22: central assertions

# one compact scenario per failure shape: (injection, expected status, checkpoint present, retry kind)
SHAPES = {
    "u1_mkdir_denied": ("failed", False, "fresh_reexecute"),
    "u1_source_revalidation": ("failed", False, "fresh_reexecute"),
    "artifact_publish": ("partial", True, "resume"),
    "source_unlink": ("partial", True, "resume"),
    "foreign_exception": (None, False, "none"),
}


def _inject(chain, shape, film, item):
    if shape == "u1_mkdir_denied":
        chain.faults.fail("execution", "mkdir", item.target_directory, OSError(errno.EACCES, "denied"))
    elif shape == "u1_source_revalidation":
        chain.faults.fail("execution", "lstat", chain.source_path(film), OSError(errno.EIO, "io"))
    elif shape == "artifact_publish":
        chain.faults.fail("materialization", "publish", item.nfo_target, OSError(errno.EIO, "io"))
    elif shape == "source_unlink":
        chain.faults.fail("execution", "unlink", chain.source_path(film), OSError(errno.EACCES, "locked"))
    else:
        chain.faults.fail("execution", transfer_operation(), chain.source_path(film), RuntimeError("boom"))


@pytest.mark.parametrize("shape", sorted(SHAPES))
def test_si01_si03_si08_si11_every_failure_shape_is_typed_atomic_and_loses_no_source(tmp_path, shape):
    """SI-01 (no silent source loss), SI-03 (fail closed: typed outcome), SI-08 (no partial final file),
    SI-11 (PARTIAL iff verified effect + checkpoint; FAILED iff none), SI-05 (the control entry is unaffected)."""
    expected_status, checkpoint, retry_kind = SHAPES[shape]
    victim = success_film("si-v", "FC2-PPV-3300001.mp4", "FC2-3300001")
    control = success_film("si-c", "FC2-PPV-3300002.mp4", "FC2-3300002")
    with Chain(tmp_path, [victim, control]) as chain:
        if shape == "source_unlink":
            chain.force_cross_volume([victim])  # the same-volume Windows rename has no separate source removal
        preview = chain.preview()
        item = item_of(preview, victim)
        _inject(chain, shape, victim, item)
        result = chain.execute(preview)
        chain.faults.assert_all_fired()
        got = item_of(result, victim)
        assert got.retry_kind.value == retry_kind
        if expected_status is None:
            assert got.disposition.value == "aborted" and got.execution is None
        else:
            assert got.disposition.value == "executed" and got.execution.status.value == expected_status
            assert (got.execution.checkpoint is not None) == checkpoint
            assert (len(got.execution.completed_effects) == 0) == (expected_status == "failed")  # FAILED iff no effect
            assert got.execution.failure is not None and got.execution.failure.kind.value
        if shape == "artifact_publish":  # SI-08: the NFO was not published, so no NFO file exists at all
            assert not os.path.exists(item.nfo_target)
            assert os.path.exists(item.final_media_path)
        if shape in ("u1_mkdir_denied", "u1_source_revalidation"):
            assert not os.path.exists(item.target_directory)  # nothing created
        assert item_of(result, control).execution.status.value == "success"
        assert chain.gate_runs["SI-01"] >= 1 and chain.gate_runs["SI-14"] >= 1


def test_si02_overwrite_never_final_media_path_is_never_replaced(tmp_path):
    """SI-02 (overwrite = NEVER): a user file already sits at the final media path inside an otherwise empty target
    directory; the entry is blocked and the user's bytes, inode and mtime survive."""
    film = success_film("si02", "FC2-PPV-3301001.mp4", "FC2-3301001")
    with Chain(tmp_path, [film]) as chain:
        occupant = os.path.join(chain.library, film.number, f"{film.number}{film.extension}")
        chain.user_write(occupant, b"the user's file at the final path")
        entries = [f"library/{film.number}", f"library/{film.number}/{film.number}{film.extension}"]
        before = chain.snapshot()
        preview = chain.preview()
        assert preview.items[0].state.value == "blocked"
        result = chain.execute(preview)
        assert result.items[0].disposition.value == "not_ready"
        gate_entries_unchanged(before, chain.snapshot(), entries, "SI-02")
        assert_sources_in_place(chain, [film])


@pytest.mark.parametrize("failing", corpus.SOURCE_IDS)
def test_si04_a_single_failing_source_never_fails_the_film(tmp_path, failing):
    """SI-04 (source isolation): whichever single source fails, the film is organized from the others."""
    base = success_film("si04", "FC2-PPV-3302001.mp4", "FC2-3302001")
    film = corpus.with_outcomes(base, {failing: (corpus.fail_outcome("NETWORK_ERROR"),)})
    with Chain(tmp_path, [film]) as chain:
        preview = chain.preview()
        assert preview.items[0].state.value == "ready" and preview.items[0].metadata.status.value == "partial"
        result = chain.execute(preview)
        assert result.outcome.value == "success"
        gate_library_exact(chain.library, organized([film]))
        # the engine's own source-local retry repeated the failing source and nobody else
        assert chain.sources.fetch_counts[(failing, film.number)] == 2
        assert all(chain.sources.fetch_counts[(sid, film.number)] == 1 for sid in corpus.SOURCE_IDS if sid != failing)


def test_si09_every_unexecuted_entry_keeps_its_source_in_place(tmp_path):
    """SI-09 (source preservation for non-success entries) over the first generation of the FX-2 mixture."""
    mixed = corpus.MixedCorpus(corpus.FX2_PLAN)
    with Chain(tmp_path, mixed.films, config=CONFIG_4) as chain:
        batch = MixedBatch(chain, mixed)
        batch.prepare()
        _preview, result = batch.g0()
        untouched = 0
        for item in result.items:
            film = batch.film_of(item)
            executed_ok = item.disposition.value == "executed" and item.execution.status.value == "success"
            if executed_ok:
                assert not os.path.exists(chain.source_path(film))  # moved
                continue
            if item.disposition.value == "executed":  # partial / failed: the bytes exist at the source or the final path
                continue
            untouched += 1
            assert sha256_file(chain.source_path(film)) == chain.original[chain.source_path(film)]
        expected = corpus.mixed_expectations(corpus.FX2_PLAN)["g0_result"]
        assert untouched == expected["not_ready"] + expected["not_selected"] + expected["aborted"]


def test_si17_real_producers_pass_every_boundary(tmp_path):
    """SI-17 (every boundary validates its own input): real producer output crosses engine -> plan -> publication -> NFO ->
    images -> manifest -> preflight -> execution -> diagnostics with no boundary rejecting it."""
    films = corpus.FX1_FILMS[:4]
    with Chain(tmp_path, films) as chain:
        preview = chain.preview()
        assert preview.summary.unprepared == 0 and preview.summary.blocked == 0
        result = chain.execute(preview)
        assert result.summary.success == 4 and result.summary.rejected == 0
        diagnostics_model(preview)
        diagnostics_model(result)


def test_si19_si20_no_persistence_no_network_and_the_repository_stays_read_only(tmp_path):
    """SI-19 (no unexpected persistence) and SI-20 (no network): the observed writes are confined to the targets, the files
    the acceptance may only read are byte-identical afterwards, and no network primitive was used."""
    digest = repository_digest()
    films = corpus.FX1_FILMS[:3]
    with Chain(tmp_path, films) as chain:
        preview = chain.preview()
        result = chain.execute(preview)
        for model in (preview, result):  # diagnostics write nothing anywhere
            diagnostics_bytes(model)
        assert chain.observer.take() == []  # diagnostics performed no modification
        assert chain.gate_runs["SI-19"] >= 1 and chain.gate_runs["SI-20"] >= 1
        gate_no_network(chain.trap.hits)
        assert chain.trap.hits == []
    gate_repository_unmodified(digest, repository_digest())
    assert sorted(os.listdir(tmp_path)) == ["downloads", "library"]  # no state / cache / diagnostics file anywhere else


def test_si21_preview_zero_mutation_is_enforced_by_the_chain(tmp_path):
    """SI-21: every preview / preview_retry of every scenario is bracketed by whole-tree snapshots (see ``Chain``)."""
    film = success_film("si21", "FC2-PPV-3303001.mp4", "FC2-3303001")
    with Chain(tmp_path, [film]) as chain:
        preview = chain.preview()
        result = chain.execute(preview)
        assert chain.gate_runs["SI-21"] == 1
        assert result.outcome.value == "success"
        for before, after in chain.preview_snapshots:
            gate_snapshots_equal(before, after, "SI-21")
        with pytest.raises(AcceptanceGateViolation):  # negative control for the comparison itself
            gate_snapshots_equal(chain.preview_snapshots[0][0], chain.snapshot(), "SI-21 control")


# --------------------------------------------------------------------------- the evidence matrix of the contract is anchored

HERE = pathlib.Path(__file__).resolve().parent
SI_EVIDENCE = {
    1: ("test_p4_acceptance_safety.py", "test_si01_si03_si08_si11_every_failure_shape_is_typed_atomic_and_loses_no_source"),
    2: ("test_p4_acceptance_safety.py", "test_si02_overwrite_never_final_media_path_is_never_replaced"),
    3: ("test_p4_acceptance_safety.py", "test_si01_si03_si08_si11_every_failure_shape_is_typed_atomic_and_loses_no_source"),
    4: ("test_p4_acceptance_safety.py", "test_si04_a_single_failing_source_never_fails_the_film"),
    5: ("test_p4_acceptance_safety.py", "test_s15_a_foreign_exception_aborts_one_item_and_not_the_batch"),
    6: ("test_p4_acceptance_determinism.py", "test_s22_peaks_equal_the_budget_and_never_exceed_it"),
    7: ("test_p4_acceptance_determinism.py", "test_s19_two_fresh_trees_with_reversed_completion_order_give_identical_results"),
    8: ("test_p4_acceptance_retry.py", "test_s13_execution_partial_resumes_to_the_one_success_layout"),
    9: ("test_p4_acceptance_safety.py", "test_si09_every_unexecuted_entry_keeps_its_source_in_place"),
    10: ("test_p4_acceptance_safety.py", "test_s10_in_batch_conflicts_block_every_member_and_select_no_winner"),
    11: ("test_p4_acceptance_retry.py", "test_s14_execution_failure_without_effect_re_executes_fresh"),
    12: ("test_p4_acceptance_retry.py", "test_s17_retry_chain_over_fx2_with_exact_counts_and_one_time_consumption"),
    13: ("test_p4_acceptance_retry.py", "test_s13_execution_partial_resumes_to_the_one_success_layout"),
    14: ("test_p4_acceptance_safety.py", "test_s21_user_entries_and_case_variants_are_never_overwritten_or_renamed"),
    15: ("test_p4_acceptance_safety.py", "test_si19_si20_no_persistence_no_network_and_the_repository_stays_read_only"),
    16: ("test_p4_acceptance_safety.py", "test_s21_junction_library_root_is_refused_and_nothing_is_followed"),
    17: ("test_p4_acceptance_safety.py", "test_si17_real_producers_pass_every_boundary"),
    18: ("test_p4_acceptance_diagnostics.py", "test_s18_canaries_never_leak_and_the_default_output_has_no_canary_at_all"),
    19: ("test_p4_acceptance_safety.py", "test_si19_si20_no_persistence_no_network_and_the_repository_stays_read_only"),
    20: ("test_p4_acceptance_harness.py", "test_socket_trap_fires_on_every_primitive_and_the_gate_reports_it"),
    21: ("test_p4_acceptance_safety.py", "test_si21_preview_zero_mutation_is_enforced_by_the_chain"),
    22: ("test_p4_acceptance_global_gate.py", "test_g500_cross_package_global_gate_with_exact_frozen_counts_and_deterministic_rerun"),
}


def _functions(filename):
    tree = ast.parse((HERE / filename).read_text(encoding="utf-8"))
    return {node.name for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}


def test_every_safety_invariant_has_a_named_evidence_test_that_exists():
    """SI-01 .. SI-22: each invariant is anchored to a real test (the table above is checked, not trusted)."""
    assert sorted(SI_EVIDENCE) == list(range(1, 23))
    for number, (filename, name) in SI_EVIDENCE.items():
        assert name in _functions(filename), f"SI-{number:02d}: {filename}::{name} does not exist"


def test_every_contract_id_appears_in_the_acceptance_tests():
    """The scenario, link, mutation and global-gate identifiers of contract sections 5.2, 7, 11 are all referenced by name
    in at least one acceptance test (IDs are generated here, not listed, so this module cannot satisfy itself)."""
    text = {path.name: path.read_text(encoding="utf-8") for path in HERE.glob("test_p4_acceptance_*.py")
            if path.name not in ("test_p4_acceptance_safety.py", "test_p4_acceptance_architecture.py")}
    own = (HERE / "test_p4_acceptance_safety.py").read_text(encoding="utf-8")
    safety_scenarios = {"S-10", "S-11", "S-15", "S-21"}  # their tests live in this very module (docstrings above)
    corpus_text = "\n".join(text.values())
    wanted = ([f"S-{n:02d}" for n in range(1, 23)] + [f"L-{n:02d}" for n in range(1, 15)]
              + [f"SI-{n:02d}" for n in range(1, 23)] + [f"M-{n:02d}" for n in range(1, 15)] + ["G-500"])
    missing = [identifier for identifier in wanted
               if not re.search(rf"(?<![A-Za-z0-9-]){re.escape(identifier)}(?![0-9])", corpus_text)
               and not (identifier in safety_scenarios or identifier.startswith("SI-")) ]
    assert missing == [], f"identifiers without a referencing test: {missing}"
    assert all(re.search(rf"\b{re.escape(identifier)}\b", own) for identifier in safety_scenarios)
