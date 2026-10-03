"""P4-C10 S2: single-item chain scenarios S-01..S-09 and S-12 (contract section 7.2) with the real-chain evidence of
links L-01..L-11 (contract section 5.2).

Real ``discover_media`` -> real ``MultiSourceEngine`` (scripted ``SourceAdapter``s) -> real ``BatchOrchestrator`` -> real
``HttpxImageClient`` over ``httpx.MockTransport`` -> real P4-C7 / P4-C6 execution on a disposable ``tmp_path`` tree.
Every expected value comes from the ``_corpus`` definitions; the shared gates (SI-01, SI-14, SI-15, SI-20, SI-21, SI-22)
run inside ``Chain.preview`` / ``Chain.execute`` for every round.
"""

from __future__ import annotations

import hashlib
import os

import pytest

from . import _corpus as corpus
from ._corpus import expectation, fail_outcome, image_url, success_film, with_outcomes
from ._harness import CONFIG_4, Chain, diagnostics_bytes, diagnostics_model, relative_cwd
from ._oracles import (
    gate_diagnostics_canaries,
    gate_diagnostics_structure,
    gate_library_exact,
    gate_snapshots_equal,
    parse_nfo,
    sha256_file,
)
from fc2_organizer.diagnostics import (
    DIAGNOSTICS_SCHEMA,
    DIAGNOSTICS_SCHEMA_VERSION,
    DiagnosticsIntegrityError,
    PathPolicy,
)
from fc2_organizer.orchestration import BatchOrchestrator


def organized(films, call=0):
    return [(film, *expectation(film, call)) for film in films]


def by_number(films):
    return {film.number: film for film in films}


def diag_ok(model, kind, count):
    """The rendered diagnostics (default NONE and explicit BASENAME) pass the structure and class A canary gates."""
    for policy in (PathPolicy.NONE, PathPolicy.BASENAME):
        rendered = diagnostics_bytes(model, policy)
        gate_diagnostics_structure(rendered, schema=DIAGNOSTICS_SCHEMA, schema_version=DIAGNOSTICS_SCHEMA_VERSION,
                                   kind=kind, items_expected=count)
        gate_diagnostics_canaries(rendered, forbidden=corpus.FX5_ALWAYS_FORBIDDEN)


def source_states(diagnostics_item):
    return {s.source_id: (s.status.value, s.operational_failure, s.contributed)
            for s in diagnostics_item.metadata.sources}


def assert_sources_in_place(chain, films):
    for film in films:
        path = chain.source_path(film)
        assert sha256_file(path) == chain.original[path], f"source of {film.key} changed"


def assert_no_target_directory(chain, films):
    for film in films:
        assert not os.path.exists(os.path.join(chain.library, film.number))


# =========================================================================== S-01


def test_s01_legal_success_chain_over_fx1_with_links_l01_to_l11(tmp_path):
    """S-01 (+ L-01..L-11): every FX-1 entry, three sources SUCCESS, poster / fanart / thumb + 2 extrafanart."""
    films = corpus.FX1_FILMS
    index = by_number(films)
    with Chain(tmp_path, films, config=CONFIG_4) as chain:
        # L-01: the input comes from the real discover_media over the dirty download tree
        items = chain.discover()
        assert [i.index for i in items] == list(range(12))
        assert sorted(os.path.basename(i.source_path) for i in items) == sorted(f.filename for f in films)
        assert all(os.path.isabs(i.source_path) for i in items)
        preview = chain.preview(items)
        assert preview.summary.total == 12 and preview.summary.ready == 12 and preview.summary.warned == 0
        for position, item in enumerate(preview.items):
            film = index[item.canonical_number]  # L-03: the number is recognized from the basename
            merged, images = expectation(film)
            assert item.media_item is items[position]  # L-02: the discovered objects are the preview's inputs
            assert os.path.basename(item.source_path) == film.filename
            assert item.state.value == "ready" and item.issue is None and item.warnings == ()
            assert item.metadata.status.value == "success"  # L-04 / L-05: real Phase 3 aggregation
            aggregation = item.metadata.aggregation_result
            assert type(aggregation).__name__ == "AggregationResult" and aggregation.status.value == "success"
            assert aggregation.metadata.title == merged["title"] and aggregation.metadata.tags == merged["tags"]
            assert item.target_directory == os.path.join(chain.library, film.number)  # L-06 layout
            assert item.final_media_path == os.path.join(item.target_directory, f"{film.number}{film.extension}")
            assert item.preflight.ready is True and not item.preflight.blockers  # L-11
            assert item.image_failures == ()
        for film in films:  # one fetch per source per number, in the configured priority order of the sources
            assert [chain.sources.fetch_counts[(sid, film.number)] for sid in corpus.SOURCE_IDS] == [1, 1, 1]
        wanted = [url for film in films for url in corpus.expected_request_urls(expectation(film)[0])]
        assert sorted(chain.routes.requests) == sorted(wanted) and len(wanted) == 60  # L-09: 5 requests per film
        assert not any("10.1.2.3" in url for url in chain.routes.requests)
        result = chain.execute(preview)  # shared gates run inside
        assert result.outcome.value == "success" and result.summary.success == 12 and result.summary.retryable == 0
        assert {i.retry_kind.value for i in result.items} == {"none"}
        # L-06 / L-07 / L-08 / L-10: layout, NFO, image bytes identity, media bytes == source bytes
        gate_library_exact(chain.library, organized(films))
        for film in films:
            assert not os.path.exists(chain.source_path(film))
            assert sha256_file(os.path.join(chain.library, film.number, f"{film.number}{film.extension}")) == \
                hashlib.sha256(film.content).hexdigest()
        # L-12 evidence in passing: every item executed once through the real executor
        assert chain.exec_probe.calls == 12
        # diagnostics (PREVIEW and EXECUTION) are buildable and render under both path policies
        diag_ok(preview, "preview", 12)
        diag_ok(result, "execution", 12)
        model = diagnostics_model(result)
        assert model.outcome.value == "success" and model.execution_summary.success == 12


# =========================================================================== S-02 / S-03 / S-04


def test_s02_metadata_partial_is_not_a_filesystem_partial(tmp_path):
    """S-02: one source SUCCESS, two operational failures -> metadata PARTIAL, execution SUCCESS."""
    films = [with_outcomes(success_film(f"s02-{n}", f"FC2-PPV-200000{n}.mp4", f"FC2-200000{n}"),
                           {"fc2db_net": (fail_outcome("BLOCKED"),), "javdb": (fail_outcome("PARSE_ERROR"),)})
             for n in range(3)]
    with Chain(tmp_path, films) as chain:
        preview = chain.preview()
        for item in preview.items:
            film = by_number(films)[item.canonical_number]
            merged, images = expectation(film)
            assert merged["status"] == "partial"
            assert item.state.value == "ready" and item.metadata.status.value == "partial"
            assert item.metadata.aggregation_result.status.value == "partial"  # L-07 partial aggregate -> record
            assert [w.value for w in item.warnings] == list(corpus.expected_warnings(merged, images))
            assert item.warnings[0].value == "metadata_partial"
        result = chain.execute(preview)
        assert result.summary.partial == 0 and result.summary.success == 3  # never a filesystem partial
        assert result.outcome.value == "success" and {i.retry_kind.value for i in result.items} == {"none"}
        gate_library_exact(chain.library, organized(films))
        item = diagnostics_model(preview).items[0]
        assert item.metadata.status.value == "partial" and item.metadata.aggregate_status.value == "partial"
        assert source_states(item) == {"fc2db_net": ("blocked", True, False), "javdb": ("parse_error", True, False),
                                       "av123": ("success", False, True)}
        diag_ok(preview, "preview", 3)
        diag_ok(result, "execution", 3)


def test_s03_one_source_failing_does_not_fail_the_film(tmp_path):
    """S-03 (SI-04): A = BLOCKED, B = SUCCESS, C = NOT_FOUND -> aggregate PARTIAL, the film is organized."""
    film = with_outcomes(success_film("s03", "FC2-PPV-2100001.mp4", "FC2-2100001"),
                         {"fc2db_net": (fail_outcome("BLOCKED"),), "av123": (fail_outcome("NOT_FOUND"),)})
    with Chain(tmp_path, [film]) as chain:
        preview = chain.preview()
        item = preview.items[0]
        assert item.state.value == "ready" and item.metadata.aggregation_result.status.value == "partial"
        result = chain.execute(preview)
        assert result.items[0].execution.status.value == "success" and result.outcome.value == "success"
        gate_library_exact(chain.library, organized([film]))
        states = source_states(diagnostics_model(preview).items[0])
        assert states == {"fc2db_net": ("blocked", True, False),  # the operational failure is reported as such
                          "javdb": ("success", False, True),
                          "av123": ("not_found", False, False)}  # NOT_FOUND is not an operational failure
        diag_ok(result, "execution", 1)


def test_s04_field_level_aggregation_agrees_with_the_nfo_and_the_diagnostics(tmp_path):
    """S-04: three sources SUCCESS with different fields -> aggregate == NFO == diagnostics (three-way)."""
    films = corpus.FX1_FILMS[:3]
    with Chain(tmp_path, films) as chain:
        preview = chain.preview()
        result = chain.execute(preview)
        gate_library_exact(chain.library, organized(films))  # NFO title / premiered / tags == the definition
        for item, execution_item in zip(preview.items, result.items):
            film = by_number(films)[item.canonical_number]
            merged, _images = expectation(film)
            expected = merged["provenance"]
            aggregate = dict(item.metadata.aggregation_result.metadata.field_sources)
            for name in ("title", "release", "tags", "studio", "plot", "poster_urls", "fanart_urls", "thumb_urls"):
                assert tuple(aggregate[name]) == expected[name], name  # aggregate provenance == the merge definition
            assert expected["title"] == ("fc2db_net",) and expected["release"] == ("javdb",)
            assert expected["tags"] == ("fc2db_net", "av123")
            diagnostic = diagnostics_model(preview).items[item.index]
            provenance = {p.field: p.source_ids for p in diagnostic.metadata.field_provenance}
            for name in ("title", "release", "tags", "studio", "plot"):
                assert provenance[name] == expected[name], name  # diagnostics provenance == the same definition
            # the diagnostics report the title conflict (B and C offered other titles; A wins)
            conflicts = {c.field: c for c in diagnostic.metadata.conflicts}
            assert conflicts["title"].selected_source_id == "fc2db_net"
            assert set(conflicts["title"].alternative_source_ids) == {"javdb", "av123"}
            assert "release" not in conflicts
            nfo = parse_nfo(open(os.path.join(chain.library, film.number, f"{film.number}.nfo"), "rb").read())
            assert [c[2] for c in nfo if c[0] == "premiered"] == [merged["release"]]
            assert [c[2] for c in nfo if c[0] == "tag"] == ["alpha", "beta", "delta"]
        diag_ok(preview, "preview", 3)


# =========================================================================== S-05 / S-06


def _recovering(film):
    """All three sources fail on the first aggregation and answer normally on the second."""
    scripts = {sid: (fail_outcome("BLOCKED"),) + outcomes for sid, outcomes in film.scripts}
    return with_outcomes(film, scripts)


def test_s05_all_sources_fail_then_recover_through_the_phase3_retry(tmp_path):
    """S-05 (L-04): UNPREPARED METADATA_UNAVAILABLE -> METADATA_REFETCH -> real Phase 3 retry -> READY -> SUCCESS."""
    films = [_recovering(success_film(f"s05-{n}", f"FC2-PPV-220000{n}.mp4", f"FC2-220000{n}")) for n in range(3)]
    with Chain(tmp_path, films) as chain:
        preview = chain.preview()
        assert preview.summary.unprepared == 3 and preview.summary.ready == 0
        for item in preview.items:
            assert item.state.value == "unprepared" and item.plan is None and item.preflight is None
            assert (item.issue.stage.value, item.issue.reason.value) == ("metadata", "metadata_unavailable")
            assert item.metadata.status.value == "failed"
        result = chain.execute(preview)
        assert {i.disposition.value for i in result.items} == {"not_ready"}
        assert {i.retry_kind.value for i in result.items} == {"metadata_refetch"}
        assert result.outcome.value == "failed" and result.summary.retryable == 3
        assert_sources_in_place(chain, films)
        assert_no_target_directory(chain, films)
        generation0 = diagnostics_model(result)
        assert {i.retry_kind.value for i in generation0.items} == {"metadata_refetch"}
        retry_preview = chain.preview_retry(result)
        assert retry_preview.generation == 1 and retry_preview.summary.ready == 3
        retry_result = chain.execute(retry_preview)
        assert retry_result.outcome.value == "success" and retry_result.summary.success == 3
        merged = chain.merge(result, retry_result)
        assert merged.outcome.value == "success" and merged.summary.success == 3 and merged.summary.retryable == 0
        for film in films:  # the real engine asked every source twice: once per aggregation round
            assert [chain.sources.fetch_counts[(sid, film.number)] for sid in corpus.SOURCE_IDS] == [2, 2, 2]
        gate_library_exact(chain.library, organized(films, call=1))
        assert diagnostics_model(merged).generation == 1
        diag_ok(retry_preview, "preview", 3)
        diag_ok(merged, "execution", 3)


def test_s06_unrecognized_number_never_reaches_the_engine_or_the_client(tmp_path):
    """S-06 (L-03): no FC2 number in the file name -> UNPREPARED NUMBER_NOT_RECOGNIZED, zero engine / client calls."""
    clip = corpus.Film("s06-clip", "holiday-clip-000.mp4", None, "x", 33)
    good = success_film("s06-good", "FC2-PPV-2300001.mp4", "FC2-2300001")
    with Chain(tmp_path / "only", [clip]) as chain:
        preview = chain.preview()
        item = preview.items[0]
        assert item.canonical_number is None and item.metadata_position is None and item.metadata is None
        assert (item.issue.stage.value, item.issue.reason.value) == ("number_recognition", "number_not_recognized")
        assert chain.sources.log == [] and chain.sources.numbers_called == {} and chain.routes.requests == []
        result = chain.execute(preview)
        assert result.items[0].disposition.value == "not_ready" and result.items[0].retry_kind.value == "none"
        assert_sources_in_place(chain, [clip])
        assert diagnostics_model(result).items[0].issue.reason.value == "number_not_recognized"
        diag_ok(result, "execution", 1)
    with Chain(tmp_path / "mixed", [clip, good]) as chain:
        preview = chain.preview()
        assert sorted(chain.sources.numbers_called) == ["FC2-2300001"]  # only the recognized film was asked
        assert all("s06-good" in url for url in chain.routes.requests) and chain.routes.requests
        chain.execute(preview)
        gate_library_exact(chain.library, organized([good]))
        assert_sources_in_place(chain, [clip])


# =========================================================================== S-07 / S-08 / S-09


def test_s07_image_partial_and_failure_are_reported_and_only_good_roles_are_written(tmp_path):
    """S-07 (L-09, L-10): 404 then a valid poster; a redirect to a private address; a Content-Type mismatch; an invalid
    extrafanart next to a valid one."""
    key = "s07"
    images = dict(poster=(image_url(key, "poster", 0, "404"), image_url(key, "poster", 1)),
                  fanart=(image_url(key, "fanart", 0, "redir"),), thumb=(image_url(key, "thumb", 0, "png"),),
                  extra=(image_url(key, "extra", 0, "bad"), image_url(key, "extra", 1)))
    film = success_film(key, "FC2-PPV-2400001.mp4", "FC2-2400001", images=images)
    merged, expected = expectation(film)
    assert expected["poster"][0] == 1 and expected["fanart"] is None and expected["thumb"] is None
    with Chain(tmp_path, [film]) as chain:
        preview = chain.preview()
        item = preview.items[0]
        assert item.state.value == "ready"
        assert [(f.role.name, f.candidate_index, f.kind.value, f.http_status) for f in item.image_failures] == \
            expected["failures"]
        assert [w.value for w in item.warnings] == ["fanart_absent", "thumb_absent", "image_candidate_failures"]
        assert chain.routes.requests == corpus.expected_request_urls(merged)  # sequential candidates, nothing else
        assert not any("10.1.2.3" in url for url in chain.routes.requests)  # the private redirect target: never requested
        result = chain.execute(preview)
        assert result.items[0].execution.status.value == "success"
        gate_library_exact(chain.library, organized([film]))  # poster == second candidate; one extrafanart; no fanart / thumb
        directory = os.path.join(chain.library, film.number)
        assert not os.path.exists(os.path.join(directory, "fanart.jpg"))
        assert not os.path.exists(os.path.join(directory, "thumb.jpg"))
        assert sorted(os.listdir(os.path.join(directory, "extrafanart"))) == ["extrafanart-001.jpg"]
        groups = {(g.role.name, g.kind.value, g.count, g.http_statuses)
                  for g in diagnostics_model(preview).items[0].image_failures}
        assert groups == {("POSTER", "http_status", 1, (404,)), ("FANART", "unsafe_url", 1, ()),
                          ("THUMB", "content_type_mismatch", 1, ()), ("EXTRAFANART", "invalid_jpeg", 1, ())}
        diag_ok(result, "execution", 1)


def test_s08_nfo_is_parseable_round_trips_and_an_invalid_date_fails_closed(tmp_path):
    """S-08 (L-08): markup / CJK / emoji titles survive verbatim without injecting elements; release 2026-02-30 fails closed."""
    nasty = success_film("s08-a", "FC2-PPV-2500001.mp4", "FC2-2500001", title="Tom & \"Jerry\" <b>'x'</b> 日本語 \U0001F3AC")
    inject = success_film("s08-b", "FC2-PPV-2500002.mp4", "FC2-2500002",
                          title="</title><evil>true</evil><title>", plot="]]> <![CDATA[x]]> <!-- c --> &xxe;")
    bad_date = success_film("s08-c", "FC2-PPV-2500003.mp4", "FC2-2500003", release="2026-02-30")
    films = [nasty, inject, bad_date]
    with Chain(tmp_path, films) as chain:
        preview = chain.preview()
        states = {i.canonical_number: i for i in preview.items}
        assert states["FC2-2500001"].state.value == states["FC2-2500002"].state.value == "ready"
        failing = states["FC2-2500003"]
        assert failing.state.value == "unprepared" and failing.preflight is None
        assert (failing.issue.stage.value, failing.issue.reason.value, failing.issue.error_type) == \
            ("nfo_render", "nfo_render_failed", "NfoReleaseDateError")
        result = chain.execute(preview)
        by_state = {i.canonical_number: i for i in result.items}
        assert by_state["FC2-2500003"].disposition.value == "not_ready" and by_state["FC2-2500003"].retry_kind.value == "none"
        assert by_state["FC2-2500001"].execution.status.value == "success"
        gate_library_exact(chain.library, organized([nasty, inject]))  # exact bytes + parse: no injected element / DTD / CDATA
        assert_sources_in_place(chain, [bad_date])
        assert_no_target_directory(chain, [bad_date])
        nfo = parse_nfo(open(os.path.join(chain.library, "FC2-2500002", "FC2-2500002.nfo"), "rb").read())
        assert nfo[0][2] == "</title><evil>true</evil><title>" and [c[0] for c in nfo].count("title") == 1
        diag_ok(result, "execution", 3)


def _rejected_library_chain(tmp_path, library_root):
    """A chain whose orchestrator uses ``library_root`` (rejected by planning); returns the outcome facts."""
    film = success_film("s09", "FC2-PPV-2600001.mp4", "FC2-2600001")
    with Chain(tmp_path, [film]) as chain:
        orchestrator = BatchOrchestrator(chain.engine, chain.client, library_root, config=chain.config)
        before = chain.snapshot()
        with relative_cwd(chain.root):  # a relative root could otherwise resolve inside the repository work tree
            preview = chain.preview(orchestrator=orchestrator)
            item = preview.items[0]
            assert item.metadata.status.value == "success"  # metadata was fetched normally
            assert item.state.value == "unprepared" and item.plan is None and item.preflight is None
            assert (item.issue.stage.value, item.issue.reason.value) == ("planning", "planning_rejected")
            assert item.issue.error_type  # the exception class name only
            assert chain.sources.numbers_called[film.number] == 3
            result = chain.execute(preview, orchestrator=orchestrator)
            assert result.items[0].disposition.value == "not_ready" and result.items[0].retry_kind.value == "none"
            assert_sources_in_place(chain, [film])
            gate_snapshots_equal(before, chain.snapshot(), "S-09 nothing is created")
            assert os.listdir(chain.library) == []
            assert not os.path.exists(os.path.join(chain.root, "relative-library"))
            if os.path.isabs(library_root):  # P4-C9 section 9: a diagnosable batch has an absolute library_root
                diag_ok(result, "execution", 1)
                assert diagnostics_model(result).items[0].issue.reason.value == "planning_rejected"
            else:  # fail closed with a typed error; the issue is presented by the model itself (see HANDOFF OBS-01)
                with pytest.raises(DiagnosticsIntegrityError):
                    diagnostics_model(result)
                with pytest.raises(DiagnosticsIntegrityError):
                    diagnostics_model(preview)


def test_s09_planning_rejection_creates_no_directory(tmp_path):
    """S-09: a relative library root is rejected by planning (UNPREPARED PLANNING_REJECTED); nothing is created."""
    _rejected_library_chain(tmp_path, "relative-library")


@pytest.mark.skipif(os.name != "nt", reason="Windows-only: a rooted path without a drive letter (contract 8.1)")
def test_s09_windows_rooted_library_root_without_a_drive_is_rejected(tmp_path):
    """S-09 (Windows native group): ``\\lib`` is rooted but has no drive letter."""
    _rejected_library_chain(tmp_path, "\\lib")


# =========================================================================== S-12


@pytest.mark.parametrize("forced_cross_volume", [False, True], ids=["same-volume-native", "cross-volume-seam"])
def test_s12_execution_success_variants(tmp_path, forced_cross_volume):
    """S-12 (PC-05, PC-06): native same-volume keeps the inode; ``_FS.device_of`` forces cross-volume (streamed 1 MiB + 1);
    0-byte media; NFC / NFD names; ``.MP4`` -> ``.mp4``; the container (extension) is unchanged."""
    films = [corpus.FX1_FILMS[i] for i in (1, 2, 5, 6, 7, 8, 9)]  # .MP4, 0 byte, NFC, NFD, .MKV, 1 MiB + 1, a
    with Chain(tmp_path, films, config=CONFIG_4) as chain:
        inodes = {film.number: os.lstat(chain.source_path(film)).st_ino for film in films}
        if forced_cross_volume:
            chain.force_cross_volume()
        preview = chain.preview()
        expected_mode = "cross_volume" if forced_cross_volume else "same_volume"
        assert {i.preflight.transfer_mode.value for i in preview.items} == {expected_mode}
        result = chain.execute(preview)
        assert result.outcome.value == "success"
        index = by_number(films)
        for item in result.items:
            film = index[item.canonical_number]
            merged, images = expectation(film)
            execution = item.execution
            assert execution.transfer_mode.value == expected_mode and execution.status.value == "success"
            final = item.final_media_path
            assert os.path.basename(final) == f"{film.number}{film.extension}"
            assert film.extension in (".mp4", ".mkv") and final.endswith(film.extension)  # lower-case, container unchanged
            if forced_cross_volume:  # the streamed copy reports the verified digest (same-volume moves no bytes)
                assert execution.media_sha256 == hashlib.sha256(film.content).hexdigest()
            assert sha256_file(final) == hashlib.sha256(film.content).hexdigest()
            if not forced_cross_volume:
                assert os.lstat(final).st_ino == inodes[film.number]  # same-volume: the very same file, moved
            kinds = [e.kind.value for e in execution.completed_effects]
            artifacts = 1 + sum(images[r] is not None for r in ("poster", "fanart", "thumb")) + len(images["extrafanart"])
            assert kinds.count("artifact_published") == artifacts and kinds.count("media_published") == 1
            # Every success records exactly one SOURCE_REMOVED (P4-C7 section 18.2): on Windows same-volume one atomic
            # rename produces both MEDIA_PUBLISHED and SOURCE_REMOVED (no separate unlink); link + unlink on POSIX;
            # copy + unlink across volumes
            assert kinds.count("source_removed") == 1
            assert kinds.count("target_directory_created") == 1 and kinds.count("extrafanart_directory_created") == 1
            assert execution.new_effect_count == len(execution.completed_effects)
            assert not os.path.exists(chain.source_path(film))
        gate_library_exact(chain.library, organized(films))
        if forced_cross_volume:
            assert chain.fs.cross_volume_calls > 0
        diag_ok(result, "execution", len(films))
        transfer = {i.execution.transfer_mode.value for i in diagnostics_model(result).items}
        assert transfer == {expected_mode}
