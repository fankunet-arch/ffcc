"""P4-C9 contract section 28.3: real P4-C8 orchestration (scripted engine / image client, ``tmp_path`` file system) ->
diagnostics. Every scenario asserts the model *and* the JSON, proves that the producer's real output passes the local
validation (the builder accepts it), renders once under the default ``NONE`` and once under ``BASENAME``, and proves
that the diagnostic consumed nothing: the preview can still be executed, the result can still be previewed for retry
and the retry result can still be merged."""

from __future__ import annotations

import errno
import json
import os

import pytest
from fc2_organizer.diagnostics import (
    DiagnosticsKind,
    PathPolicy,
    ResultShape,
    TimingPolicy,
    build_execution_diagnostics,
    build_preview_diagnostics,
    render_diagnostics_json,
)
from fc2_organizer.execution import ExecutionStatus as X
from fc2_organizer.orchestration import (
    BatchExecutionResult,
    BatchOutcome,
    BatchPreview,
    CancellationToken,
    ExecutionDisposition as D,
    IssueReason as R,
    ItemWarning as W,
    PreviewState as S,
    RetryKind as K,
    merge_retry,
)
from orchestration._helpers import Corpus, Film, fs_fault, run, tree_snapshot

BUILD = {BatchPreview: build_preview_diagnostics, BatchExecutionResult: build_execution_diagnostics}


def diagnose(container):
    """Build under both policies, render both, and check the JSON mirrors the model. Returns the NONE model."""
    build = BUILD[type(container)]
    none = build(container)
    named = build(container, path_policy=PathPolicy.BASENAME, timing_policy=TimingPolicy.INCLUDE)
    assert none.path_policy is PathPolicy.NONE and named.path_policy is PathPolicy.BASENAME
    for model in (none, named):
        tree = json.loads(render_diagnostics_json(model))
        assert tree["kind"] == model.kind.value and tree["shape"] == model.shape.value
        assert [i["index"] for i in tree["items"]] == [i.index for i in model.items]
        assert [i["retry_kind"] for i in tree["items"]] == [None if i.retry_kind is None else i.retry_kind.value
                                                             for i in model.items]
        assert [i["preview_state"] for i in tree["items"]] == [i.preview_state.value for i in model.items]
        assert [i["canonical_number"] for i in tree["items"]] == [i.canonical_number for i in model.items]
    assert all(i.source_name is None for i in none.items)
    for item, container_item in zip(named.items, container.items):
        assert item.source_name == os.path.basename(container_item.source_path)
    return none


def chain(tmp_path, films, **kwargs):
    corpus = Corpus(tmp_path, films)
    orchestrator = corpus.orchestrator(**kwargs)
    return corpus, orchestrator, run(orchestrator.preview(corpus.items))


def by_state(model, state):
    return [i for i in model.items if i.preview_state is state]


# ---- previews


def test_success_batch(tmp_path):
    corpus, orchestrator, preview = chain(tmp_path, [Film("FC2-PPV-1000001.mp4"), Film("FC2-PPV-1000002.mp4")])
    model = diagnose(preview)
    assert model.kind is DiagnosticsKind.PREVIEW and model.shape is ResultShape.MAIN
    assert model.preview_summary == preview.summary and model.preview_summary.ready == 2
    assert all(i.metadata.status.value == "success" and W.METADATA_PARTIAL not in i.warnings for i in model.items)
    result = orchestrator.execute(preview)  # the diagnosed preview was not consumed
    model = diagnose(result)
    assert model.outcome is BatchOutcome.SUCCESS and model.execution_summary == result.summary
    assert {i.retry_kind for i in model.items} == {K.NONE}


def test_partial_metadata_and_image_warnings(tmp_path):
    films = [Film("FC2-PPV-1000001.mp4", kind="partial", poster=False, thumb=False),
             Film("FC2-PPV-1000002.mp4", extra=1, extra_fail=2), Film("FC2-PPV-1000003.mp4")]
    corpus, orchestrator, preview = chain(tmp_path, films)
    model = diagnose(preview)
    first, second, third = model.items
    assert first.metadata.status.value == "partial" and W.METADATA_PARTIAL in first.warnings
    assert W.POSTER_ABSENT in first.warnings and W.THUMB_ABSENT in first.warnings
    assert any(source.operational_failure for source in first.metadata.sources)
    assert W.IMAGE_CANDIDATE_FAILURES in second.warnings and second.image_failures
    assert all(group.count >= 1 and group.http_statuses == (404,) for group in second.image_failures)
    assert third.warnings == (W.NO_EXTRAFANART,)
    tree = json.loads(render_diagnostics_json(model))
    assert tree["items"][1]["image_failures"][0]["http_statuses"] == [404]


def test_failed_unprepared_and_engine_failure_items(tmp_path):
    films = [Film("FC2-PPV-1000001.mp4"), Film("FC2-PPV-1000002.mp4", kind="failed"),
             Film("FC2-PPV-1000003.mp4", kind="engine"), Film("no-number-here.mp4")]
    corpus, orchestrator, preview = chain(tmp_path, films)
    model = diagnose(preview)
    states = [i.preview_state for i in model.items]
    assert states == [S.READY, S.UNPREPARED, S.UNPREPARED, S.UNPREPARED]
    reasons = [i.issue.reason if i.issue else None for i in model.items]
    assert reasons[2] is R.METADATA_ENGINE_FAILURE and reasons[3] is R.NUMBER_NOT_RECOGNIZED
    assert model.items[2].issue.error_type == "RuntimeError" and model.items[3].canonical_number is None
    assert model.preview_summary.unprepared == 3 and model.preview_summary == preview.summary
    result = orchestrator.execute(preview)
    out = diagnose(result)
    assert out.outcome is result.outcome and out.items[1].retry_kind is K.METADATA_REFETCH


def test_a_blocked_item(tmp_path):
    films = [Film("FC2-PPV-1000001.mp4"), Film("FC2-PPV-1000002.mp4")]
    probe = Corpus(tmp_path / "probe", films)
    probe_preview = probe.preview()
    target = os.path.join(str(tmp_path / "blocked" / "lib"), os.path.basename(probe_preview.items[0].target_directory))
    os.makedirs(target)
    with open(os.path.join(target, "keep.txt"), "wb") as handle:
        handle.write(b"user bytes")
    corpus, orchestrator, preview = chain(tmp_path / "blocked", films)
    model = diagnose(preview)
    blocked = by_state(model, S.BLOCKED)
    assert len(blocked) == 1 and blocked[0].issue.reason is R.PREFLIGHT_BLOCKED
    assert blocked[0].preflight.ready is False and blocked[0].preflight.blockers
    tree = json.loads(render_diagnostics_json(model))
    assert tree["items"][0]["preflight"]["blockers"][0]["reason"] == "target_directory_exists"
    result = orchestrator.execute(preview)
    assert diagnose(result).items[0].retry_kind is K.PREFLIGHT_RECHECK


def test_a_batch_conflict_is_reported_symmetrically(tmp_path):
    films = [Film("FC2-PPV-1000001.mp4", directory="a"), Film("FC2-PPV-1000001.mp4", directory="b")]
    corpus, orchestrator, preview = chain(tmp_path, films)
    model = diagnose(preview)
    assert model.items[0].conflict_with == (1,) and model.items[1].conflict_with == (0,)
    assert {i.issue.reason for i in model.items} <= {R.DUPLICATE_SOURCE_IN_BATCH, R.DUPLICATE_TARGET_IN_BATCH}


# ---- execution results


def test_execution_partial_resume_and_the_retry_chain(tmp_path, monkeypatch):
    corpus, orchestrator, preview = chain(tmp_path, [Film("FC2-PPV-1000001.mp4", extra=1),
                                                     Film("FC2-PPV-1000002.mp4")])
    thumb = preview.items[0].thumb_target
    with monkeypatch.context() as patch:
        fault = fs_fault(patch)
        fault.fail("materialization", "publish", thumb, OSError(errno.EIO, "io"))
        result = orchestrator.execute(preview)
    model = diagnose(result)
    partial = model.items[0]
    assert partial.execution.status is X.PARTIAL and partial.retry_kind is K.RESUME
    assert partial.execution.checkpoint_present and partial.execution.failure is not None
    assert partial.retry_material_retained is True and model.items[1].retry_kind is K.NONE
    assert model.outcome is result.outcome is BatchOutcome.PARTIAL
    snapshot = tree_snapshot(tmp_path)
    retry = run(orchestrator.preview_retry(result, scope=frozenset({K.RESUME})))  # not consumed by the diagnostic
    retry_model = diagnose(retry)
    assert retry_model.shape is ResultShape.RETRY and retry_model.retry_scope == (K.RESUME,)
    assert retry_model.items[0].retry_origin is K.RESUME and retry_model.generation == 1
    assert tree_snapshot(tmp_path) == snapshot  # diagnosing changed no file
    round_result = orchestrator.execute(retry)
    round_model = diagnose(round_result)
    assert round_model.shape is ResultShape.RETRY and round_model.items[0].execution.status is X.SUCCESS
    merged = merge_retry(result, round_result)  # still mergeable
    merged_model = diagnose(merged)
    assert merged_model.shape is ResultShape.MERGED and merged_model.outcome is BatchOutcome.SUCCESS
    assert [i.generation for i in merged_model.items] == [1, 0]


def test_execution_failed_fresh_reexecute(tmp_path, monkeypatch):
    corpus, orchestrator, preview = chain(tmp_path, [Film("FC2-PPV-1000001.mp4"), Film("FC2-PPV-1000002.mp4")])
    with monkeypatch.context() as patch:
        fault = fs_fault(patch)
        fault.fail("execution", "mkdir", preview.items[0].target_directory, OSError(errno.EACCES, "denied"))
        result = orchestrator.execute(preview)
    model = diagnose(result)
    failed = model.items[0]
    assert failed.execution.status is X.FAILED and failed.retry_kind is K.FRESH_REEXECUTE
    assert failed.execution.failure.errno == errno.EACCES and not failed.execution.checkpoint_present
    assert model.execution_summary.failed == 1 and model.outcome is BatchOutcome.PARTIAL
    retry = run(orchestrator.preview_retry(result))
    assert diagnose(retry).items[0].retry_origin is K.FRESH_REEXECUTE


def test_deferred_not_selected_and_cancelled(tmp_path):
    corpus, orchestrator, preview = chain(tmp_path, [Film("FC2-PPV-%d.mp4" % (1000001 + i)) for i in range(4)])
    ready = [i.index for i in preview.items]
    result = orchestrator.execute(preview, selection=(ready[1],))
    model = diagnose(result)
    assert [i.disposition for i in model.items] == [D.NOT_SELECTED, D.EXECUTED, D.NOT_SELECTED, D.NOT_SELECTED]
    assert [i.retry_kind for i in model.items] == [K.DEFERRED, K.NONE, K.DEFERRED, K.DEFERRED]
    assert model.execution_summary == result.summary and model.execution_summary.deferred == 3
    corpus2, orchestrator2, preview2 = chain(tmp_path / "second", [Film("FC2-PPV-%d.mp4" % (1000001 + i))
                                                                     for i in range(3)])
    token = CancellationToken()
    token.cancel()
    cancelled = diagnose(orchestrator2.execute(preview2, cancel=token))
    assert [i.disposition for i in cancelled.items] == [D.CANCELLED] * 3
    assert {i.retry_kind for i in cancelled.items} == {K.DEFERRED}


def test_aborted_item(tmp_path, monkeypatch):
    corpus, orchestrator, preview = chain(tmp_path, [Film("FC2-PPV-1000001.mp4")])
    (item,) = preview.items
    fault = fs_fault(monkeypatch)
    for op in ("rename", "link", "open"):
        fault.fail("execution", op, os.path.basename(item.source_path), RuntimeError("injected C9CANARY-EXC"))
    result = orchestrator.execute(preview)
    model = diagnose(result)
    assert model.items[0].disposition is D.ABORTED and model.items[0].issue.reason is R.EXECUTION_ABORTED
    assert model.items[0].issue.error_type == "RuntimeError" and model.items[0].retry_kind is K.NONE
    for policy in PathPolicy:
        assert b"C9CANARY" not in render_diagnostics_json(build_execution_diagnostics(result, path_policy=policy))


def test_every_retry_kind_is_reached_by_real_producers(tmp_path, monkeypatch):
    seen = set()
    corpus, orchestrator, preview = chain(tmp_path / "a", [Film("FC2-PPV-1000001.mp4", extra=1),
                                                           Film("FC2-PPV-1000002.mp4"),
                                                           Film("FC2-PPV-1000003.mp4", kind="failed"),
                                                           Film("FC2-PPV-1000004.mp4")])
    thumb = preview.items[0].thumb_target
    with monkeypatch.context() as patch:
        fault = fs_fault(patch)
        fault.fail("materialization", "publish", thumb, OSError(errno.EIO, "io"))
        fault.fail("execution", "mkdir", preview.items[1].target_directory, OSError(errno.EACCES, "denied"))
        result = orchestrator.execute(preview, selection=(0, 1))
    seen |= {i.retry_kind for i in diagnose(result).items}
    corpus, orchestrator, preview = chain(tmp_path / "b", [Film("FC2-PPV-1000001.mp4"), Film("FC2-PPV-1000002.mp4")])
    token = CancellationToken()
    token.cancel()
    seen |= {i.retry_kind for i in diagnose(orchestrator.execute(preview, cancel=token)).items}
    assert {K.RESUME, K.FRESH_REEXECUTE, K.METADATA_REFETCH, K.DEFERRED} <= seen


def test_diagnosing_calls_no_engine_client_or_file_system_seam(tmp_path, monkeypatch):
    corpus, orchestrator, preview = chain(tmp_path, [Film("FC2-PPV-1000001.mp4", extra=1), Film("FC2-PPV-1000002.mp4")])
    result = orchestrator.execute(preview)
    engine_calls, client_calls = len(corpus.engine.calls), len(corpus.client.calls)
    snapshot = tree_snapshot(tmp_path)
    with monkeypatch.context() as patch:
        fault = fs_fault(patch)  # records every file-system seam call as a hit (none is configured to fail)
        fault.fail("execution", "stat", "", OSError(errno.EIO, "any file-system access"))
        fault.fail("execution", "lstat", "", OSError(errno.EIO, "any file-system access"))
        fault.fail("execution", "open", "", OSError(errno.EIO, "any file-system access"))
        fault.fail("materialization", "publish", "", OSError(errno.EIO, "any file-system access"))
        diagnose(preview)
        diagnose(result)
        assert fault.hits == []
    assert (len(corpus.engine.calls), len(corpus.client.calls)) == (engine_calls, client_calls)
    assert tree_snapshot(tmp_path) == snapshot
