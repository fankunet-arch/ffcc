"""P4-C7 S5: concurrency at the single-film boundary (contract sections 15.4, 21, 25, 30; plan S5).

Production S5 schedules nothing: the concurrency lives in these tests only. Correctness never depends on sleeps:
threads are released together by a ``threading.Barrier``; outcomes are checked, not timings.
"""

from __future__ import annotations

import hashlib
import multiprocessing
import os
import threading
from pathlib import Path

import pytest

from fc2_organizer.execution import (
    ExecutionFailureKind,
    ExecutionStatus,
    PreflightIntegrityError,
    PreflightIntegrityReason,
    execute_filesystem,
    preflight_execution,
)

from ._builders import make_manifest, make_plan
from ._helpers import assert_source_not_lost, expected_library_layout, spawn_worker, tree_layout

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
    assert len(successes) <= 1
    finals = [plan.target_media_path.absolute_path for plan, _ in plans]
    holders = [f for f in finals if os.path.isfile(f)]
    assert len(holders) <= 1  # never two independent targets holding the one source
    for (plan, manifest), result in zip(plans, results):
        if result.status is ExecutionStatus.SUCCESS:
            continue
        kind = result.failure.kind
        # The loser saw the source gone / changed (revalidation or the transfer's own checks), or the race
        # surfaced at the primitive itself (section 18.2: MEDIA_TRANSFER_FAILED), or -- Windows MoveFileExW
        # renames through a handle opened before the other thread's rename -- its own atomic rename moved the
        # file and the winner's then moved it on: the post-publish verification fails closed (section 25).
        assert kind in (F.SOURCE_MISSING, F.SOURCE_CHANGED, F.MEDIA_TRANSFER_FAILED, F.PUBLISHED_MEDIA_MISMATCH)
        if kind is F.PUBLISHED_MEDIA_MISMATCH:
            assert not os.path.lexists(plan.target_media_path.absolute_path)  # the bytes live at the winner
            resume = preflight_execution(plan, manifest, result.checkpoint)
            assert not resume.ready  # a recorded-but-gone final can never be resumed past (fail closed)
        else:
            assert not any(e.kind.name in ("MEDIA_PUBLISHED", "SOURCE_REMOVED") for e in result.completed_effects)
    digest = hashlib.sha256(_media(0)).hexdigest()
    assert_source_not_lost(str(source), holders[0] if holders else str(source), digest)


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
