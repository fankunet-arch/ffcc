"""P4-C7 S5: concurrency at the single-film boundary (contract sections 15.4, 15.6, 21, 25, 30; plan S5).

Production S5 schedules nothing: the concurrency lives in these tests only. Correctness never depends on sleeps:
threads are released together by a ``threading.Barrier`` or ordered by ``threading.Event`` hand-shakes inside
controlled seams; outcomes are checked, not timings. The process-local source ownership claim (section 15.6) is
tested both directly on the private registry and through execute_filesystem.
"""

from __future__ import annotations

import errno
import hashlib
import multiprocessing
import os
import threading
from pathlib import Path

import pytest

from fc2_organizer.execution import (
    CheckpointError,
    CheckpointRejectionReason,
    EffectKind,
    EntryIdentity,
    EntryType,
    ExecutionFailureKind,
    ExecutionStatus,
    ExecutionStep,
    PreflightIntegrityError,
    PreflightIntegrityReason,
    execute_filesystem,
    preflight_execution,
)
from fc2_organizer import execution as execution_package
from fc2_organizer.execution import _fs, executor
from fc2_organizer.execution import seal as seal_module
from fc2_organizer.execution.seal import (
    claim_acquire,
    claim_poison_active,
    claim_release,
    claim_reserve,
    claim_take_over,
    is_consumed,
)
from fc2_organizer.execution.transfer import ResumePhase

from ._builders import make_manifest, make_plan
from ._helpers import (
    TransferSpy,
    assert_source_not_lost,
    claim_state,
    expected_library_layout,
    force_cross_volume_devices,
    inject,
    isolated_source_claims,  # noqa: F401 -- autouse fixture: per-test claim registry isolation
    spawn_worker,
    tree_layout,
    use_strategy,
)

F = ExecutionFailureKind


def _media(tag: int) -> bytes:
    return (b"race-media-%03d " % tag) * 31


def _film(root: Path, library: Path, tag: int, number: str = "FC2-1234567", extra: int = 2):
    downloads = root / "downloads"
    downloads.mkdir(parents=True, exist_ok=True)
    source = downloads / f"source-{tag}.mp4"
    source.write_bytes(_media(tag))
    plan = make_plan(str(library), str(source), number=number, size=len(_media(tag)))
    return plan, make_manifest(plan, extra=extra), str(source)


def _run_together(calls):
    """Run the zero-argument callables in threads released by one barrier; returns results / exceptions."""
    barrier = threading.Barrier(len(calls))
    outcomes = [None] * len(calls)

    def runner(index, call):
        barrier.wait()
        try:
            outcomes[index] = call()
        except BaseException as exc:  # recorded for the assertions
            outcomes[index] = exc

    threads = [threading.Thread(target=runner, args=(i, c)) for i, c in enumerate(calls)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    return outcomes


def _assert_single_owner(films, results):
    successes = [i for i, r in enumerate(results) if r.status is ExecutionStatus.SUCCESS]
    assert len(successes) == 1, [(r.status, r.failure) for r in results]
    winner = successes[0]
    for index, result in enumerate(results):
        plan, manifest, source = films[index]
        digest = hashlib.sha256(_media(index)).hexdigest()
        if index == winner:
            assert not os.path.lexists(source)
            assert tree_layout(plan.library_root) == expected_library_layout(plan, manifest, _media(index))
        else:  # the loser: FAILED(TARGET_CONFLICT), zero effects, its source untouched
            assert result.status is ExecutionStatus.FAILED and result.failure.kind is F.TARGET_CONFLICT
            assert result.completed_effects == () and result.checkpoint is None
            assert os.path.isfile(source)
        assert_source_not_lost(source, plan.target_media_path.absolute_path if index == winner else source, digest)


def test_same_target_race_has_exactly_one_owner(tmp_path):
    library = tmp_path / "library"
    library.mkdir()
    films = [_film(tmp_path, library, tag) for tag in range(2)]
    preflights = [preflight_execution(plan, manifest) for plan, manifest, _ in films]
    assert all(p.ready for p in preflights)  # both saw an absent target
    results = _run_together([lambda p=p: execute_filesystem(p) for p in preflights])
    _assert_single_owner(films, results)


@pytest.mark.parametrize("round_", range(5))
def test_eight_threads_same_target(tmp_path, round_):
    library = tmp_path / f"library-{round_}"
    library.mkdir()
    films = [_film(tmp_path / f"r{round_}", library, tag) for tag in range(8)]
    preflights = [preflight_execution(plan, manifest) for plan, manifest, _ in films]
    assert all(p.ready for p in preflights)
    results = _run_together([lambda p=p: execute_filesystem(p) for p in preflights])
    _assert_single_owner(films, results)


def test_same_preflight_in_two_threads_executes_once(tmp_path):
    library = tmp_path / "library"
    library.mkdir()
    plan, manifest, source = _film(tmp_path, library, 0)
    preflight = preflight_execution(plan, manifest)
    outcomes = _run_together([lambda: execute_filesystem(preflight)] * 2)
    results = [o for o in outcomes if not isinstance(o, BaseException)]
    errors = [o for o in outcomes if isinstance(o, BaseException)]
    assert len(results) == 1 and results[0].status is ExecutionStatus.SUCCESS
    assert len(errors) == 1 and type(errors[0]) is PreflightIntegrityError
    assert errors[0].reason is PreflightIntegrityReason.CONSUMED
    assert tree_layout(library) == expected_library_layout(plan, manifest, _media(0))  # executed exactly once


@pytest.mark.parametrize("round_", range(6))
def test_same_source_two_libraries_moves_it_at_most_once(tmp_path, round_):
    downloads = tmp_path / "downloads"
    downloads.mkdir()
    source = downloads / "shared.mp4"
    source.write_bytes(_media(0))
    plans = []
    for name in ("library-a", "library-b"):
        (tmp_path / name).mkdir()
        plan = make_plan(str(tmp_path / name), str(source), size=len(_media(0)))
        plans.append((plan, make_manifest(plan, extra=1)))
    preflights = [preflight_execution(plan, manifest) for plan, manifest in plans]
    assert all(p.ready for p in preflights)
    results = _run_together([lambda p=p: execute_filesystem(p) for p in preflights])
    successes = [r for r in results if r.status is ExecutionStatus.SUCCESS]
    assert len(successes) == 1  # S5-A2-R2 claim: at most one (and here exactly one) SUCCESS, never two
    finals = [plan.target_media_path.absolute_path for plan, _ in plans]
    holders = [f for f in finals if os.path.isfile(f)]
    assert len(holders) == 1  # exactly one media final target holds the one source
    for (plan, manifest), result in zip(plans, results):
        if result.status is ExecutionStatus.SUCCESS:
            continue
        # Same process: the loser either conflicted on the source ownership claim (PARTIAL(SOURCE_CHANGED))
        # or entered U2 only after the winner removed the source (SOURCE_MISSING / SOURCE_CHANGED); the
        # cross-process residual outcomes (PUBLISHED_MEDIA_MISMATCH / MEDIA_TRANSFER_FAILED) cannot occur.
        assert result.failure.kind in (F.SOURCE_MISSING, F.SOURCE_CHANGED)
        assert not any(e.kind is EffectKind.MEDIA_PUBLISHED for e in result.completed_effects)
        assert not os.path.lexists(plan.target_media_path.absolute_path)
    digest = hashlib.sha256(_media(0)).hexdigest()
    assert_source_not_lost(str(source), holders[0], digest)


def test_multiprocess_spawn_distinct_films_all_succeed(tmp_path):
    jobs = []
    for index in range(3):
        library = tmp_path / f"library-{index}"
        library.mkdir()
        _, _, source = _film(tmp_path / f"p{index}", library, index)
        jobs.append((str(library), source, len(_media(index))))
    context = multiprocessing.get_context("spawn")
    with context.Pool(processes=3) as pool:
        statuses = pool.map(spawn_worker, jobs, chunksize=1)
    assert statuses == ["success"] * 3
    for library, source, _ in jobs:
        assert not os.path.lexists(source) and os.listdir(library) == ["FC2-1234567"]


# =========================================================================== S5-R1: source ownership claim


def _identity(inode: int) -> EntryIdentity:
    """A synthetic FILE identity on a device no real test file uses (registry-level tests only)."""
    return EntryIdentity(987_654_321, inode, EntryType.FILE, 1, 1)


# --------------------------------------------------------------------------- A-E: token ownership (registry)


def test_wrong_token_release_is_a_no_op():
    key = _identity(1)
    token_a = claim_acquire(key)
    assert token_a is not None and claim_state(key) == ("active", token_a)
    assert claim_release(key, "f" * 32) is False
    assert claim_state(key) == ("active", token_a)
    assert claim_acquire(key) is None  # still owned: another acquisition conflicts
    assert claim_release(key, token_a) is True and claim_state(key) is None


def test_duplicate_release_is_a_no_op():
    key = _identity(2)
    token_a = claim_acquire(key)
    assert claim_release(key, token_a) is True and claim_state(key) is None
    assert claim_release(key, token_a) is False and claim_state(key) is None


def test_aba_stale_release_never_frees_a_newer_owner():
    key = _identity(3)
    token_a = claim_acquire(key)
    assert claim_release(key, token_a) is True
    token_b = claim_acquire(key)
    assert token_b is not None and token_b != token_a  # a fresh token per acquisition
    assert claim_release(key, token_a) is False  # A's late / duplicate cleanup
    assert claim_state(key) == ("active", token_b)
    assert claim_acquire(key) is None  # C conflicts: B and C can never both hold the source


def test_stale_reserve_never_overwrites_a_newer_owner():
    key = _identity(4)
    token_a = claim_acquire(key)
    claim_release(key, token_a)
    token_b = claim_acquire(key)
    assert claim_reserve(key, token_a, "c" * 32) is False
    assert claim_state(key) == ("active", token_b)
    assert claim_reserve(key, token_b, "c" * 32) is True and claim_state(key) == ("reserved", "c" * 32)
    assert claim_take_over(key, "d" * 32) is None  # only the reservation owner may take it over
    assert claim_state(key) == ("reserved", "c" * 32)


def test_stale_poison_never_poisons_a_newer_owner():
    key = _identity(5)
    token_a = claim_acquire(key)
    claim_release(key, token_a)
    token_b = claim_acquire(key)
    assert claim_poison_active(key, token_a) is False
    assert claim_state(key) == ("active", token_b)
    assert claim_poison_active(key, token_b) is True and claim_state(key) == ("poisoned", None)
    assert claim_release(key, token_b) is False and claim_acquire(key) is None  # never cleared


def test_tokens_are_never_exposed_by_the_public_package():
    for name in ("claim_acquire", "claim_release", "ClaimIntegrityError", "_CLAIMS"):
        assert name not in execution_package.__all__ and not hasattr(execution_package, name)
    assert "claim" not in " ".join(execution_package.__all__).lower()
    assert isinstance(seal_module._CLAIMS, dict) and "_CLAIMS" not in seal_module.__all__


# --------------------------------------------------------------------------- scenes


def _shared_source(tmp_path: Path, *, extra: int = 1):
    downloads = tmp_path / "downloads"
    downloads.mkdir()
    source = downloads / "shared.mp4"
    source.write_bytes(_media(0))
    films = []
    for name in ("library-a", "library-b"):
        (tmp_path / name).mkdir()
        plan = make_plan(str(tmp_path / name), str(source), size=len(_media(0)))
        films.append((plan, make_manifest(plan, extra=extra)))
    return str(source), films


def _unlink_fails_for(monkeypatch, path):
    real = _fs._FS.unlink
    state = {"active": True}

    def unlink(candidate):
        if state["active"] and candidate == path:
            raise PermissionError(errno.EACCES, "busy")
        return real(candidate)

    inject(monkeypatch, unlink=unlink)
    return state


def _digest() -> str:
    return hashlib.sha256(_media(0)).hexdigest()


# --------------------------------------------------------------------------- deterministic acquisition overlap


def test_deterministic_acquisition_overlap(tmp_path, monkeypatch):
    source, ((plan_a, manifest_a), (plan_b, manifest_b)) = _shared_source(tmp_path)
    pre_a, pre_b = preflight_execution(plan_a, manifest_a), preflight_execution(plan_b, manifest_b)
    assert pre_a.ready and pre_b.ready
    owner_active, release_a = threading.Event(), threading.Event()
    target_a = plan_a.target_directory.absolute_path
    target_b = plan_b.target_directory.absolute_path
    real_transfer, real_mkdir_unit = executor.transfer_media, executor.create_target_directory
    transfers, attempts = [], []

    def transfer(plan, *args, **kwargs):
        transfers.append(plan.target_directory.absolute_path)
        if plan.target_directory.absolute_path == target_a:
            owner_active.set()  # A holds ACTIVE and is inside the transfer seam
            assert release_a.wait(30)
        return real_transfer(plan, *args, **kwargs)

    def create_target_directory(plan, identity):
        result = real_mkdir_unit(plan, identity)
        if plan.target_directory.absolute_path == target_b:
            assert owner_active.wait(30)  # B has finished U1; it may enter U2 only once A is ACTIVE
        return result

    real_acquire = executor.claim_acquire

    def acquire(identity):
        token = real_acquire(identity)
        attempts.append((threading.current_thread().name, token))
        return token

    monkeypatch.setattr(executor, "transfer_media", transfer)
    monkeypatch.setattr(executor, "create_target_directory", create_target_directory)
    monkeypatch.setattr(executor, "claim_acquire", acquire)
    results = {}
    thread_a = threading.Thread(target=lambda: results.__setitem__("a", execute_filesystem(pre_a)), name="A")
    thread_b = threading.Thread(target=lambda: results.__setitem__("b", execute_filesystem(pre_b)), name="B")
    thread_a.start()
    thread_b.start()
    thread_b.join(60)
    assert not thread_b.is_alive()
    b = results["b"]  # B's result is checked while A still holds ACTIVE
    assert b.status is ExecutionStatus.PARTIAL and b.failure.kind is F.SOURCE_CHANGED
    assert b.failure.step is ExecutionStep.MOVE_MEDIA and b.failure.stage is None and b.failure.errno is None
    assert [e.kind for e in b.checkpoint.completed_effects] == [EffectKind.TARGET_DIRECTORY_CREATED]
    assert transfers == [target_a]  # B never reached transfer_media
    assert ("B", None) in attempts  # B really attempted the acquisition and conflicted
    assert not os.path.lexists(plan_b.target_media_path.absolute_path)
    release_a.set()
    thread_a.join(60)
    assert results["a"].status is ExecutionStatus.SUCCESS
    assert claim_state(pre_a.source_identity) is None  # released after SOURCE_REMOVED
    assert_source_not_lost(source, plan_a.target_media_path.absolute_path, _digest())


# --------------------------------------------------------------------------- reservation


@pytest.mark.parametrize("volume", ["posix_same_volume", "cross_volume"])
def test_published_but_source_retained_reserves_and_blocks_a_second_final(tmp_path, monkeypatch, volume):
    if volume == "posix_same_volume":
        use_strategy(monkeypatch, "link")
    else:
        force_cross_volume_devices(monkeypatch)
    source, ((plan_a, manifest_a), (plan_b, manifest_b)) = _shared_source(tmp_path)
    failing = _unlink_fails_for(monkeypatch, source)
    first = execute_filesystem(preflight_execution(plan_a, manifest_a))
    assert first.status is ExecutionStatus.PARTIAL and first.failure.kind is F.SOURCE_UNLINK_FAILED
    identity = first.checkpoint.source_identity
    assert claim_state(identity) == ("reserved", first.checkpoint.checkpoint_id)
    spy = TransferSpy(monkeypatch)
    pre_b = preflight_execution(plan_b, manifest_b)
    assert pre_b.ready  # the source is still there and unchanged
    second = execute_filesystem(pre_b)
    assert second.status is ExecutionStatus.PARTIAL and second.failure.kind is F.SOURCE_CHANGED
    assert second.failure.step is ExecutionStep.MOVE_MEDIA and spy.calls == []
    assert not os.path.lexists(plan_b.target_media_path.absolute_path)  # no second final
    assert claim_state(identity) == ("reserved", first.checkpoint.checkpoint_id)
    failing["active"] = False
    done = execute_filesystem(preflight_execution(plan_a, manifest_a, first.checkpoint))
    assert done.status is ExecutionStatus.SUCCESS and claim_state(identity) is None
    holders = [p.target_media_path.absolute_path for p in (plan_a, plan_b)
               if os.path.isfile(p.target_media_path.absolute_path)]
    assert holders == [plan_a.target_media_path.absolute_path]
    assert_source_not_lost(source, holders[0], _digest())


def test_reservation_moves_along_the_checkpoint_chain(tmp_path, monkeypatch):
    use_strategy(monkeypatch, "link")
    source, ((plan_a, manifest_a), (plan_b, manifest_b)) = _shared_source(tmp_path)
    failing = _unlink_fails_for(monkeypatch, source)
    spy = TransferSpy(monkeypatch)
    r1 = execute_filesystem(preflight_execution(plan_a, manifest_a))
    cp1 = r1.checkpoint
    identity = cp1.source_identity
    assert claim_state(identity) == ("reserved", cp1.checkpoint_id)
    phases = []
    spy_inner = executor.transfer_media

    def phase_spy(plan, *args, resume_phase):
        phases.append(resume_phase)
        return spy_inner(plan, *args, resume_phase=resume_phase)

    monkeypatch.setattr(executor, "transfer_media", phase_spy)
    r2 = execute_filesystem(preflight_execution(plan_a, manifest_a, cp1))  # the unlink fails again
    cp2 = r2.checkpoint
    assert r2.failure.kind is F.SOURCE_UNLINK_FAILED and phases == [ResumePhase.SOURCE_REMOVAL_ONLY]
    assert claim_state(identity) == ("reserved", cp2.checkpoint_id)  # exactly one owner: cp2, not cp1
    assert is_consumed(cp1.checkpoint_id)
    with pytest.raises(CheckpointError) as info:
        preflight_execution(plan_a, manifest_a, cp1)
    assert info.value.reason is CheckpointRejectionReason.CONSUMED
    assert claim_take_over(identity, cp1.checkpoint_id) is None  # the consumed predecessor can never take over
    blocked = execute_filesystem(preflight_execution(plan_b, manifest_b))  # at every point of the chain
    assert blocked.failure.kind is F.SOURCE_CHANGED
    assert not os.path.lexists(plan_b.target_media_path.absolute_path)
    failing["active"] = False
    r3 = execute_filesystem(preflight_execution(plan_a, manifest_a, cp2))
    assert r3.status is ExecutionStatus.SUCCESS and claim_state(identity) is None
    assert phases == [ResumePhase.SOURCE_REMOVAL_ONLY] * 2 and len(spy.calls) == 3
    assert_source_not_lost(source, plan_a.target_media_path.absolute_path, _digest())


def test_unconsumed_not_ready_checkpoint_keeps_its_reservation(tmp_path, monkeypatch):
    use_strategy(monkeypatch, "link")
    source, ((plan_a, manifest_a), _) = _shared_source(tmp_path)
    failing = _unlink_fails_for(monkeypatch, source)
    first = execute_filesystem(preflight_execution(plan_a, manifest_a))
    cp = first.checkpoint
    planted = Path(plan_a.target_directory.absolute_path, "planted.txt")
    planted.write_bytes(b"x")
    blocked = preflight_execution(plan_a, manifest_a, cp)
    assert not blocked.ready and not is_consumed(cp.checkpoint_id)
    assert claim_state(cp.source_identity) == ("reserved", cp.checkpoint_id)  # preflight never touches claims
    planted.unlink()
    failing["active"] = False
    done = execute_filesystem(preflight_execution(plan_a, manifest_a, cp))
    assert done.status is ExecutionStatus.SUCCESS and claim_state(cp.source_identity) is None


# --------------------------------------------------------------------------- release classes


def test_pre_publish_failure_releases_the_claim(tmp_path, monkeypatch):
    source, ((plan_a, manifest_a), (plan_b, manifest_b)) = _shared_source(tmp_path)
    pre_a, pre_b = preflight_execution(plan_a, manifest_a), preflight_execution(plan_b, manifest_b)
    real = {op: getattr(_fs._FS, op) for op in ("rename", "link")}
    state = {"fail": True}

    def primitive(op):
        def run(a, b):
            if state["fail"] and a == source:
                raise PermissionError(errno.EPERM, "x")
            return real[op](a, b)
        return run

    inject(monkeypatch, rename=primitive("rename"), link=primitive("link"))
    first = execute_filesystem(pre_a)
    assert first.failure.kind is F.MEDIA_TRANSFER_FAILED
    assert not any(e.kind is EffectKind.MEDIA_PUBLISHED for e in first.completed_effects)
    assert claim_state(pre_a.source_identity) is None  # released: nothing was published
    state["fail"] = False
    second = execute_filesystem(pre_b)  # a legitimate later execution can take the source
    assert second.status is ExecutionStatus.SUCCESS
    assert_source_not_lost(source, plan_b.target_media_path.absolute_path, _digest())


def test_source_removed_releases_the_claim(tmp_path):
    source, ((plan_a, manifest_a), _) = _shared_source(tmp_path)
    pre = preflight_execution(plan_a, manifest_a)
    assert execute_filesystem(pre).status is ExecutionStatus.SUCCESS
    assert claim_state(pre.source_identity) is None
    token = claim_acquire(pre.source_identity)  # no stale claim blocks the key
    assert token is not None and claim_release(pre.source_identity, token)


# --------------------------------------------------------------------------- POISONED


class CustomFatal(BaseException):
    pass


def test_fatal_while_active_poisons_and_blocks_the_source(tmp_path, monkeypatch):
    source, ((plan_a, manifest_a), (plan_b, manifest_b)) = _shared_source(tmp_path)
    pre_a, pre_b = preflight_execution(plan_a, manifest_a), preflight_execution(plan_b, manifest_b)
    exc = RuntimeError("inside transfer_media")
    real = executor.transfer_media

    def exploding(plan, *args, **kwargs):
        if plan is plan_a:
            raise exc
        return real(plan, *args, **kwargs)

    monkeypatch.setattr(executor, "transfer_media", exploding)
    with pytest.raises(RuntimeError) as info:
        execute_filesystem(pre_a)
    assert info.value is exc
    assert claim_state(pre_a.source_identity) == ("poisoned", None)  # never auto-released
    spy = TransferSpy(monkeypatch)
    blocked = execute_filesystem(pre_b)
    assert blocked.failure.kind is F.SOURCE_CHANGED and spy.calls == []
    assert claim_state(pre_a.source_identity) == ("poisoned", None)
    assert_source_not_lost(source, plan_a.target_media_path.absolute_path, _digest())


@pytest.mark.parametrize("fatal", [RuntimeError, CustomFatal, KeyboardInterrupt])
def test_fatal_after_consuming_a_reserving_checkpoint_poisons(tmp_path, monkeypatch, fatal):
    use_strategy(monkeypatch, "link")
    source, ((plan_a, manifest_a), (plan_b, manifest_b)) = _shared_source(tmp_path)
    failing = _unlink_fails_for(monkeypatch, source)
    cp1 = execute_filesystem(preflight_execution(plan_a, manifest_a)).checkpoint
    identity = cp1.source_identity
    resume = preflight_execution(plan_a, manifest_a, cp1)
    exc = fatal("before the hand-over")
    real_check = executor._preflight._check_resume_source

    def exploding(*args):
        raise exc

    monkeypatch.setattr(executor._preflight, "_check_resume_source", exploding)
    with pytest.raises(fatal) as info:
        execute_filesystem(resume)
    assert info.value is exc and is_consumed(cp1.checkpoint_id)
    assert claim_state(identity) == ("poisoned", None)
    monkeypatch.setattr(executor._preflight, "_check_resume_source", real_check)
    failing["active"] = False
    spy = TransferSpy(monkeypatch)
    blocked = execute_filesystem(preflight_execution(plan_b, manifest_b))
    assert blocked.failure.kind is F.SOURCE_CHANGED and spy.calls == []
    assert not os.path.lexists(plan_b.target_media_path.absolute_path)
    assert_source_not_lost(source, plan_a.target_media_path.absolute_path, _digest())
