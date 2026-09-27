"""P4-C8 S2: end-to-end read-only preview (contract sections 11.3, 12-17, 21, 22).

Real ``discover_media`` over ``tmp_path``, real P4-C2..P4-C7 stages and preflight; only the metadata
engine and the image HTTP client are scripted in-memory doubles.
"""

from __future__ import annotations

import os

import pytest

from fc2_metadata_core.batch import BatchItemErrorKind, BatchScheduler
from fc2_organizer.execution import PlanGraphRejectionReason, PreflightBlockReason, PreflightMode
from fc2_organizer.images import ImageInputError
from fc2_organizer.materialization import ArtifactKind, ArtifactMappingError, MappingRejectionReason
from fc2_organizer.nfo import render_movie_nfo
from fc2_organizer.orchestration import (
    DEFAULT_MAX_RETAINED_ARTIFACT_BYTES,
    IssueReason as R,
    ItemWarning as W,
    OrchestrationConfig,
    OrchestrationStage as St,
    PreviewState as S,
)
from fc2_organizer.orchestration import preview as preview_module
from fc2_organizer.orchestration import stages
from fc2_organizer.publication import prepare_publication

from ._fakes import build_metadata
from ._helpers import Corpus, Film, by_name, image_url, make_media_tree, run


def _reason(item):
    return None if item.issue is None else item.issue.reason


# =========================================================================== READY item (15.4)


def test_ready_item_exposes_every_confirmable_fact(tmp_path):
    corpus = Corpus(tmp_path, [Film("FC2-PPV-1000001.mp4", extra=2, release="2024-02-03")])
    preview = corpus.preview()
    (item,) = preview.items
    plan = item.plan
    assert item.state is S.READY and item.executable is True and item.issue is None
    assert item.canonical_number == "FC2-1000001" and item.index == 0 and item.generation == 0
    assert item.source_path == corpus.items[0].source_path and item.source_size == corpus.items[0].size
    assert item.target_directory == str(corpus.library / "FC2-1000001")
    assert item.final_media_path == plan.target_media_path.absolute_path
    assert item.nfo_target == plan.nfo_path.absolute_path
    assert (item.poster_target, item.fanart_target, item.thumb_target) == (
        plan.poster_path.absolute_path, plan.fanart_path.absolute_path, plan.thumb_path.absolute_path)
    assert item.extrafanart_directory == plan.extrafanart_directory.absolute_path and item.extrafanart_count == 2
    assert item.artifact_kinds == (ArtifactKind.NFO, ArtifactKind.POSTER, ArtifactKind.FANART, ArtifactKind.THUMB,
                                   ArtifactKind.EXTRAFANART, ArtifactKind.EXTRAFANART)
    assert item.preflight.ready is True and item.preflight.plan is plan and item.preflight_mode is PreflightMode.FRESH
    assert item.planned_units == item.preflight.pending_units and item.planned_units
    assert item.completed_units == () and item.skipped_steps == () and item.blockers == ()
    assert item.predicted_transfer_mode is not None and item.warnings == () and item.conflict_with == ()
    # the manifest carries the real P4-C4 NFO and the scripted image bytes
    nfo_request = item.preflight.artifacts[0]
    expected_nfo = render_movie_nfo(prepare_publication(plan, item.metadata.aggregation_result))
    assert nfo_request.content == expected_nfo.encode("utf-8")
    poster = item.preflight.artifacts[1]
    assert poster.content == corpus.client.script[image_url("FC2-1000001", "poster")].content
    assert item.metadata is preview.metadata_batch.items[item.metadata_position]


def test_preview_fields_and_budget(tmp_path):
    corpus = Corpus(tmp_path, [Film("FC2-PPV-1000001.mp4")])
    preview = corpus.preview()
    assert preview.generation == 0 and preview.base_result_id is None and preview.retry_scope is None
    assert preview.retention_budget_bytes == DEFAULT_MAX_RETAINED_ARTIFACT_BYTES
    assert preview.retry_budget_bytes is None and preview.library_root == str(corpus.library)
    assert preview.lineage == preview.metadata_batch.lineage and preview.batch_size == 1
    assert 0 < preview.retained_artifact_bytes <= preview.retention_budget_bytes
    custom = corpus.orchestrator(config=OrchestrationConfig(max_retained_artifact_bytes=10 ** 9))
    assert run(custom.preview(corpus.items)).retention_budget_bytes == 10 ** 9


# =========================================================================== one failure per stage


def test_every_stage_failure_in_one_batch(tmp_path, monkeypatch):
    films = [
        Film("junk-video.mp4"),                                      # number
        Film("FC2-PPV-1000002.mp4"), Film("FC2PPV1000002.mkv", directory="other"),  # Phase A target
        Film("FC2-PPV-1000003.mp4", kind="failed"),                  # metadata unavailable
        Film("FC2-PPV-1000004.mp4", kind="engine"),                  # engine exception
        Film("FC2-PPV-1000005.mp4", kind="mismatch"),                # result contract mismatch
        Film("FC2-PPV-1000006.mp4", release="2024-13-45"),           # NFO
        Film("FC2-PPV-1000007.mp4"),                                 # image error (injected)
        Film("FC2-PPV-1000008.mp4"),                                 # manifest (injected)
        Film("FC2-PPV-1000009.mp4"),                                 # preflight blocked: target exists
        Film("FC2-PPV-1000010.mp4"),                                 # preflight blocked: source removed
        Film("FC2-PPV-1000011.mp4"),                                 # publication (injected identity mismatch)
        Film("FC2-PPV-1000012.mp4"),                                 # READY
    ]
    corpus = Corpus(tmp_path, films)
    (corpus.library / "FC2-1000009").mkdir()
    real_acquire = preview_module.acquire_images
    real_mapping = stages.build_artifact_requests
    real_publication = stages.prepare_publication

    async def acquire(record, client, *, policy=None):
        if record.plan.canonical_number == "FC2-1000007":
            raise ImageInputError("forged candidate collection")
        return await real_acquire(record, client, policy=policy)

    def mapping(plan, nfo_text, images):
        if plan.canonical_number == "FC2-1000008":
            raise ArtifactMappingError(MappingRejectionReason.DUPLICATE_TARGET)
        return real_mapping(plan, nfo_text, images)

    def publication(plan, aggregation):
        if plan.canonical_number == "FC2-1000011":
            return real_publication(plan, build_metadata("FC2-7777777"))
        return real_publication(plan, aggregation)

    monkeypatch.setattr(preview_module, "acquire_images", acquire)
    monkeypatch.setattr(stages, "build_artifact_requests", mapping)
    monkeypatch.setattr(stages, "prepare_publication", publication)
    removed = next(i for i in corpus.items if os.path.basename(i.source_path) == "FC2-PPV-1000010.mp4")
    os.remove(removed.source_path)
    preview = corpus.preview()
    items = by_name(preview)

    expect = {
        "junk-video.mp4": (S.UNPREPARED, St.NUMBER_RECOGNITION, R.NUMBER_NOT_RECOGNIZED, None, None),
        "FC2-PPV-1000002.mp4": (S.BLOCKED, St.BATCH_CONFLICT, R.DUPLICATE_TARGET_IN_BATCH, None, None),
        "FC2PPV1000002.mkv": (S.BLOCKED, St.BATCH_CONFLICT, R.DUPLICATE_TARGET_IN_BATCH, None, None),
        "FC2-PPV-1000003.mp4": (S.UNPREPARED, St.METADATA, R.METADATA_UNAVAILABLE, None, None),
        "FC2-PPV-1000004.mp4": (S.UNPREPARED, St.METADATA, R.METADATA_ENGINE_FAILURE, "RuntimeError",
                                BatchItemErrorKind.ENGINE_EXCEPTION),
        "FC2-PPV-1000005.mp4": (S.UNPREPARED, St.METADATA, R.METADATA_ENGINE_FAILURE, "object",
                                BatchItemErrorKind.RESULT_CONTRACT_MISMATCH),
        "FC2-PPV-1000006.mp4": (S.UNPREPARED, St.NFO_RENDER, R.NFO_RENDER_FAILED, "NfoReleaseDateError", None),
        "FC2-PPV-1000007.mp4": (S.UNPREPARED, St.IMAGE_ACQUISITION, R.IMAGE_ACQUISITION_ERROR, "ImageInputError",
                                None),
        "FC2-PPV-1000008.mp4": (S.UNPREPARED, St.MANIFEST, R.MANIFEST_REJECTED, "ArtifactMappingError",
                                MappingRejectionReason.DUPLICATE_TARGET),
        "FC2-PPV-1000009.mp4": (S.BLOCKED, St.PREFLIGHT, R.PREFLIGHT_BLOCKED, None, None),
        "FC2-PPV-1000010.mp4": (S.BLOCKED, St.PREFLIGHT, R.PREFLIGHT_BLOCKED, None, None),
        "FC2-PPV-1000011.mp4": (S.UNPREPARED, St.PUBLICATION, R.PUBLICATION_REJECTED,
                                "PublicationIdentityMismatchError", None),
        "FC2-PPV-1000012.mp4": (S.READY, None, None, None, None),
    }
    for name, (state, stage, reason, error_type, detail) in expect.items():
        item = items[name]
        assert item.state is state, name
        if reason is None:
            assert item.issue is None, name
        else:
            assert (item.issue.stage, item.issue.reason, item.issue.error_type, item.issue.detail) == (
                stage, reason, error_type, detail), name
    assert items["FC2-PPV-1000009.mp4"].blockers[0].reason is PreflightBlockReason.TARGET_DIRECTORY_EXISTS
    # stage short-circuit: Phase A conflicts never reach the engine, failed NFO never reaches the images
    assert "FC2-1000002" not in corpus.engine.calls
    assert not [url for url in corpus.client.calls if "FC2-1000006" in url]
    assert not [url for url in corpus.client.calls if "FC2-1000003" in url or "FC2-1000011" in url]
    assert items["FC2-PPV-1000003.mp4"].plan is None and items["FC2-PPV-1000011.mp4"].plan is not None
    assert items["FC2-PPV-1000002.mp4"].metadata is None and items["FC2-PPV-1000002.mp4"].preflight is None


def test_source_removed_after_discovery_is_blocked(tmp_path):
    corpus = Corpus(tmp_path, [Film("FC2-PPV-1000001.mp4")])
    os.remove(corpus.items[0].source_path)
    (item,) = corpus.preview().items
    assert item.state is S.BLOCKED and _reason(item) is R.PREFLIGHT_BLOCKED
    assert {b.reason for b in item.blockers} == {PreflightBlockReason.SOURCE_MISSING}


def test_invalid_library_root_rejects_every_planned_item(tmp_path):
    corpus = Corpus(tmp_path, [Film("FC2-PPV-1000001.mp4"), Film("FC2-PPV-1000002.mp4")])
    preview = run(corpus.orchestrator(library_root="relative-library").preview(corpus.items))
    for item in preview.items:
        assert _reason(item) is R.PLANNING_REJECTED and item.issue.error_type == "InvalidLibraryRootError"
        assert item.plan is None
    assert corpus.client.calls == []


def test_missing_library_root_is_a_preflight_blocker(tmp_path):
    corpus = Corpus(tmp_path, [Film("FC2-PPV-1000001.mp4")], library=False)
    (item,) = corpus.preview().items
    assert item.state is S.BLOCKED
    assert PreflightBlockReason.LIBRARY_ROOT_MISSING in {b.reason for b in item.blockers}


@pytest.mark.skipif(os.name != "nt", reason="junctions exist only on Windows hosts")
def test_library_root_junction_is_a_preflight_blocker(tmp_path):
    import _winapi

    real = tmp_path / "real-lib"
    real.mkdir()
    corpus = Corpus(tmp_path, [Film("FC2-PPV-1000001.mp4")], library=False)
    _winapi.CreateJunction(str(real), str(corpus.library))
    (item,) = corpus.preview().items
    assert item.state is S.BLOCKED
    assert PreflightBlockReason.LIBRARY_ROOT_IS_LINK in {b.reason for b in item.blockers}


def test_source_inside_target_is_preflight_rejected(tmp_path):
    corpus = Corpus(tmp_path, [Film("FC2-PPV-1000001.mp4")])
    inside = make_media_tree(corpus.library / "FC2-1000002", {"FC2-PPV-1000002.mp4": b"inside"})
    corpus.engine.script["FC2-1000002"] = "success"
    preview = run(corpus.orchestrator().preview(corpus.items + inside))
    rejected = preview.items[1]
    assert rejected.state is S.UNPREPARED and _reason(rejected) is R.PREFLIGHT_REJECTED
    assert rejected.issue.error_type == "PlanGraphError"
    assert rejected.issue.detail is PlanGraphRejectionReason.SOURCE_INSIDE_TARGET


# =========================================================================== Phase A / Phase B


def test_same_object_twice_is_a_source_conflict_with_no_metadata_call(tmp_path):
    corpus = Corpus(tmp_path, [Film("FC2-PPV-1000001.mp4"), Film("FC2-PPV-1000002.mp4")])
    doubled = [corpus.items[0], corpus.items[1], corpus.items[0]]
    preview = run(corpus.orchestrator().preview(doubled))
    assert [(_reason(i), i.conflict_with) for i in preview.items] == [
        (R.DUPLICATE_SOURCE_IN_BATCH, (2,)), (None, ()), (R.DUPLICATE_SOURCE_IN_BATCH, (0,))]
    assert corpus.engine.calls == ["FC2-1000002"]


def test_hardlinked_sources_are_phase_b_conflicts_keeping_their_preflights(tmp_path):
    corpus = Corpus(tmp_path, [Film("FC2-PPV-1000001.mp4"), Film("FC2-PPV-1000003.mp4")])
    original = corpus.items[0].source_path
    alias_dir = corpus.downloads / "alias"
    alias_dir.mkdir()
    os.link(original, alias_dir / "FC2-PPV-1000002.mp4")
    corpus.engine.script["FC2-1000002"] = "success"
    items = make_media_tree(corpus.downloads, {})
    preview = run(corpus.orchestrator().preview(items))
    named = by_name(preview)
    first, alias = named["FC2-PPV-1000001.mp4"], named["FC2-PPV-1000002.mp4"]
    assert _reason(first) is _reason(alias) is R.DUPLICATE_SOURCE_IN_BATCH
    assert first.state is alias.state is S.BLOCKED and not first.executable
    assert first.preflight is not None and first.preflight.ready is True  # kept, but not executable
    assert first.conflict_with == (alias.index,) and alias.conflict_with == (first.index,)
    assert named["FC2-PPV-1000003.mp4"].state is S.READY


def test_phase_b_overrides_a_preflight_blocked_item(tmp_path):
    corpus = Corpus(tmp_path, [Film("FC2-PPV-1000001.mp4")])
    alias_dir = corpus.downloads / "alias"
    alias_dir.mkdir()
    os.link(corpus.items[0].source_path, alias_dir / "FC2-PPV-1000002.mp4")
    corpus.engine.script["FC2-1000002"] = "success"
    (corpus.library / "FC2-1000001").mkdir()  # item 1000001 is also PREFLIGHT_BLOCKED
    preview = run(corpus.orchestrator().preview(make_media_tree(corpus.downloads, {})))
    blocked = by_name(preview)["FC2-PPV-1000001.mp4"]
    assert _reason(blocked) is R.DUPLICATE_SOURCE_IN_BATCH and blocked.state is S.BLOCKED
    assert PreflightBlockReason.TARGET_DIRECTORY_EXISTS in {b.reason for b in blocked.blockers}


# =========================================================================== images (22.2) and warnings (22.3)


@pytest.mark.parametrize("film, warnings", [
    (Film("FC2-PPV-1000001.mp4", poster=False), (W.POSTER_ABSENT, W.NO_EXTRAFANART)),
    (Film("FC2-PPV-1000001.mp4", fanart=False), (W.FANART_ABSENT, W.NO_EXTRAFANART)),
    (Film("FC2-PPV-1000001.mp4", thumb=False), (W.THUMB_ABSENT, W.NO_EXTRAFANART)),
    (Film("FC2-PPV-1000001.mp4", extra=1), ()),
    (Film("FC2-PPV-1000001.mp4", extra=2, extra_fail=2), (W.IMAGE_CANDIDATE_FAILURES,)),
    (Film("FC2-PPV-1000001.mp4", poster=False, fanart=False, thumb=False),
     (W.POSTER_ABSENT, W.FANART_ABSENT, W.THUMB_ABSENT, W.NO_EXTRAFANART)),
    (Film("FC2-PPV-1000001.mp4", kind="partial", poster=False, extra=1, extra_fail=1),
     (W.METADATA_PARTIAL, W.POSTER_ABSENT, W.IMAGE_CANDIDATE_FAILURES)),
])
def test_partial_images_are_warnings_never_blockers(tmp_path, film, warnings):
    corpus = Corpus(tmp_path, [film])
    (item,) = corpus.preview().items
    assert item.state is S.READY and item.warnings == warnings
    kinds = item.artifact_kinds
    assert kinds[0] is ArtifactKind.NFO
    assert (ArtifactKind.POSTER in kinds) is film.poster and (ArtifactKind.THUMB in kinds) is film.thumb
    assert item.extrafanart_count == film.extra
    assert len(item.image_failures) == film.extra_fail


def test_metadata_partial_is_not_refetched(tmp_path):
    corpus = Corpus(tmp_path, [Film("FC2-PPV-1000001.mp4", kind="partial")])
    (item,) = corpus.preview().items
    assert item.state is S.READY and W.METADATA_PARTIAL in item.warnings
    assert corpus.engine.calls == ["FC2-1000001"]


# =========================================================================== ordering / empty / nine steps


def test_items_follow_the_input_snapshot_order(tmp_path):
    corpus = Corpus(tmp_path, [Film(f"FC2-PPV-100000{i}.mp4") for i in range(1, 6)] + [Film("junk.mp4")])
    reordered = list(reversed(corpus.items))
    preview = run(corpus.orchestrator().preview(reordered))
    assert [i.index for i in preview.items] == list(range(len(reordered)))
    assert [i.media_item for i in preview.items] == reordered
    assert all(i.media_item is r for i, r in zip(preview.items, reordered))


def test_empty_batch_still_calls_the_scheduler(tmp_path, monkeypatch):
    calls = []
    real_run = BatchScheduler.run

    async def spy(self, numbers):
        calls.append(tuple(numbers))
        return await real_run(self, numbers)

    monkeypatch.setattr(BatchScheduler, "run", spy)
    corpus = Corpus(tmp_path, [])
    preview = run(corpus.orchestrator().preview(()))
    assert calls == [()] and preview.items == () and preview.batch_size == 0
    assert preview.metadata_batch.items == () and preview.lineage == preview.metadata_batch.lineage
    assert corpus.engine.calls == [] and corpus.client.calls == []


def test_the_nine_step_order(tmp_path, monkeypatch):
    events: list[tuple[str, str]] = []
    corpus = Corpus(tmp_path, [Film(f"FC2-PPV-100000{i}.mp4") for i in range(1, 5)])

    def wrap(module, name, key):
        real = getattr(module, name)

        def recorded(*args, **kwargs):
            events.append((name, key(args)))
            return real(*args, **kwargs)
        monkeypatch.setattr(module, name, recorded)

    wrap(stages, "build_organize_plan", lambda a: a[1])
    wrap(stages, "prepare_publication", lambda a: a[0].canonical_number)
    wrap(stages, "render_movie_nfo", lambda a: a[0].plan.canonical_number)
    wrap(stages, "build_artifact_requests", lambda a: a[0].canonical_number)
    wrap(stages, "preflight_execution", lambda a: a[0].canonical_number)
    real_acquire = preview_module.acquire_images

    async def acquire(record, client, *, policy=None):
        events.append(("acquire_images", record.plan.canonical_number))
        return await real_acquire(record, client, policy=policy)

    monkeypatch.setattr(preview_module, "acquire_images", acquire)
    real_aggregate = corpus.engine.aggregate

    async def aggregate(number):
        events.append(("aggregate", number))
        return await real_aggregate(number)

    corpus.engine.aggregate = aggregate
    corpus.preview()
    names = [name for name, _ in events]

    def last(name):
        return max(i for i, n in enumerate(names) if n == name)

    def first(name):
        return names.index(name)

    assert last("aggregate") < first("build_organize_plan")                     # 4 before 5
    assert max(last(n) for n in ("build_organize_plan", "prepare_publication", "render_movie_nfo")) \
        < first("acquire_images")                                               # 5 before 6
    assert last("acquire_images") < first("build_artifact_requests")            # 6 before 7
    step5 = [(n, k) for n, k in events if n in ("build_organize_plan", "prepare_publication", "render_movie_nfo")]
    numbers = [f"FC2-100000{i}" for i in range(1, 5)]
    assert step5 == [(n, k) for k in numbers for n in ("build_organize_plan", "prepare_publication",
                                                       "render_movie_nfo")]
    step7 = [(n, k) for n, k in events if n in ("build_artifact_requests", "preflight_execution")]
    assert step7 == [(n, k) for k in numbers for n in ("build_artifact_requests", "preflight_execution")]
