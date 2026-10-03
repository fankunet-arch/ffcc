"""P4-C10 harness self-check (construction plan section 3, S1 item 6; contract sections 11.2 last paragraph, 12.2, 12.5).

Shows that the acceptance infrastructure is not vacuous: every shared gate passes on clean input and fails on a planted
violation, the sandbox guard refuses paths outside ``tmp_path``, the socket trap and the write observer fire and are
transparent, injected faults really fire, the concurrency gates reach the budgets, and the corpus expectations are
internally consistent (G-500 groups sum to 500, every generation count follows from the definition).
"""

from __future__ import annotations

import builtins
import errno
import io
import json
import os
from types import SimpleNamespace

import pytest
from fc2_metadata_core.aggregation import MultiSourceEngine
from fc2_metadata_core.batch import BatchConfig
from fc2_organizer.diagnostics import DIAGNOSTICS_SCHEMA, DIAGNOSTICS_SCHEMA_VERSION, PathPolicy
from fc2_organizer.execution import _fs as execution_fs
from fc2_organizer.images.transport import HttpxImageClient
from fc2_organizer.materialization import atomic as materialization_atomic
from fc2_organizer.orchestration import BatchOrchestrator, OrchestrationConfig
from fc2_organizer.orchestration import execute as orchestration_execute
from fc2_organizer.orchestration import preview as preview_module

from . import _corpus as corpus
from ._harness import Chain, Sandbox, diagnostics_bytes, result_projection, trapped_primitives
from ._oracles import (
    AcceptanceGateViolation,
    expected_retry_kind,
    gate_deterministic_equal,
    gate_diagnostics_canaries,
    gate_diagnostics_structure,
    gate_entries_unchanged,
    gate_file_bytes,
    gate_indices_exactly_once,
    gate_layout_exact,
    gate_nfo_matches,
    gate_no_network,
    gate_no_unreported_temporaries,
    gate_path_within,
    gate_peak,
    gate_result_accounting,
    gate_retry_kinds,
    gate_snapshots_equal,
    gate_source_not_lost,
    gate_write_paths_contained,
    parse_nfo,
    sha256_file,
    snapshot_tree,
)

CONFIG_4 = OrchestrationConfig(metadata=BatchConfig(max_in_flight_items=4), image_in_flight_items=4,
                               filesystem_workers=4)
CONFIG_2 = OrchestrationConfig(metadata=BatchConfig(max_in_flight_items=2), image_in_flight_items=2,
                               filesystem_workers=2)


# =========================================================================== corpus consistency


def test_g500_groups_sum_to_500_and_frozen_counts_follow_from_the_definition():
    plan = corpus.G500_PLAN
    assert plan.total == 500
    assert len(corpus.MixedCorpus(plan).films) == 500
    derived = corpus.mixed_expectations(plan)
    for section, frozen in corpus.G500_FROZEN.items():
        for name, value in frozen.items():
            assert derived[section][name] == value, (section, name)  # literal contract table == derivation
    assert derived["final"]["sources_in_place"] == 65


def test_fx2_covers_every_group_and_has_24_entries():
    plan = corpus.FX2_PLAN
    assert plan.total == 24
    assert min(plan.a, plan.b, plan.c, plan.c_recover, plan.d, plan.e, plan.f_pairs, plan.g, plan.g_removed, plan.h,
               plan.i, plan.j, plan.k) >= 1
    assert plan.c - plan.c_recover >= 1 and plan.g - plan.g_removed >= 1  # still failing / still blocked remain
    expected = corpus.mixed_expectations(plan)
    kinds = expected["g0_result"]["kinds"]
    assert set(kinds) == {"resume", "fresh_reexecute", "metadata_refetch", "preflight_recheck"} and min(kinds.values()) >= 1
    assert expected["g0_result"]["deferred"] >= 1 and expected["g0_result"]["aborted"] >= 1


def test_fx1_has_the_twelve_frozen_properties():
    films = corpus.FX1_FILMS
    assert len(films) == 12
    assert any(f.size == 0 for f in films) and any(f.size == (1 << 20) + 1 for f in films)
    assert any(f.filename.endswith((".MP4", ".MKV")) for f in films)
    names = [f.filename for f in films]
    assert any("é" in n for n in names) and any("é" in n for n in names)  # NFC and NFD
    assert any("日本語" in n for n in names) and any("\U0001F3AC" in n for n in names)
    assert len({f.number for f in films}) == 12 and len({f.key for f in films}) == 12
    assert sum(1 for f in films if f.directory) == 3


def test_mixed_corpus_identities_and_script_invariants():
    mixed = corpus.MixedCorpus(corpus.G500_PLAN)
    numbers = [f.number for f in mixed.films if f.number is not None]
    assert len(set(numbers)) == 500 - 20 - 10  # GE has no number; GF pairs share one
    assert len({f.key for f in mixed.films}) == 500
    for film in mixed.films:
        for _source, outcomes in film.scripts:
            if len(outcomes) > 1:
                assert not any(o.status in corpus.RETRYABLE_SOURCE_STATUSES for o in outcomes)
    assert all(film.number is None for film in mixed.by_group("E"))
    f_numbers = [film.number for film in mixed.by_group("F")]
    assert all(f_numbers.count(n) == 2 for n in f_numbers)
    recovering = mixed.c_recovering
    assert len(recovering) == 20 and all(len(dict(f.scripts)[sid]) == 2 for f in recovering for sid in corpus.SOURCE_IDS)
    b_statuses = {s for f in mixed.by_group("B") for _sid, o in f.scripts for s in [o[0].status] if s != "SUCCESS"}
    assert b_statuses == {"BLOCKED", "NETWORK_ERROR", "PARSE_ERROR"}


def test_merge_expectation_follows_the_s04_field_level_definition():
    film = corpus.FX1_FILMS[0]
    merged = corpus.merge_expected(film.outcomes_at(0))
    assert merged["status"] == "success"
    assert merged["title"] == "Title A fx1-01" and merged["provenance"]["title"] == ("fc2db_net",)  # only A
    assert merged["release"] == "2024-05-06" and merged["provenance"]["release"] == ("javdb",)  # only B
    assert merged["tags"] == ("alpha", "beta", "delta") and merged["provenance"]["tags"] == ("fc2db_net", "av123")
    assert merged["extrafanart"] == tuple(corpus.image_url("fx1-01", "extra", i) for i in range(2))
    # a source failing operationally makes the aggregate partial and removes its fields; NOT_FOUND does not
    failing = {"fc2db_net": corpus.fail_outcome("BLOCKED"), "javdb": corpus.fail_outcome("NOT_FOUND"),
               "av123": corpus.ok_outcome(title="only C", tags=("x",))}
    merged = corpus.merge_expected(failing)
    assert merged["status"] == "partial" and merged["title"] == "only C" and merged["tags"] == ("x",)
    assert corpus.merge_expected({s: corpus.fail_outcome("NOT_FOUND") for s in corpus.SOURCE_IDS}) is None
    quiet = {"fc2db_net": corpus.ok_outcome(title="t"), "javdb": corpus.fail_outcome("NOT_FOUND"),
             "av123": corpus.fail_outcome("NOT_FOUND")}
    assert corpus.merge_expected(quiet)["status"] == "success"


def test_expected_images_classify_every_candidate_behavior():
    key = "img"
    merged = {"poster_urls": tuple(corpus.image_url(key, "poster", i, b) for i, b in enumerate(("404", "ok"))),
              "fanart_urls": (corpus.image_url(key, "fanart", 0, "redir"),),
              "thumb_urls": (corpus.image_url(key, "thumb", 0, "png"), corpus.image_url(key, "thumb", 1, "bad")),
              "extrafanart": tuple(corpus.image_url(key, "extra", i, b) for i, b in enumerate(("bad", "ok", "ok")))}
    images = corpus.expected_images(merged)
    assert images["poster"][0] == 1 and images["fanart"] is None and images["thumb"] is None
    assert [e[0] for e in images["extrafanart"]] == [1, 2]
    assert images["failures"] == [("POSTER", 0, "http_status", 404), ("FANART", 0, "unsafe_url", None),
                                  ("THUMB", 0, "content_type_mismatch", None), ("THUMB", 1, "invalid_jpeg", None),
                                  ("EXTRAFANART", 0, "invalid_jpeg", None)]
    assert corpus.expected_warnings({"status": "partial"}, images) == (
        "metadata_partial", "fanart_absent", "thumb_absent", "image_candidate_failures")


def test_expected_nfo_text_escapes_and_orders():
    merged = corpus.merge_expected({"fc2db_net": corpus.ok_outcome(title='Tom & "Jerry" <b>\'x\'</b>\r'),
                                    "javdb": corpus.fail_outcome("NOT_FOUND"), "av123": corpus.fail_outcome("NOT_FOUND")})
    text = corpus.expected_nfo_text("FC2-1", merged)
    assert "<title>Tom &amp; \"Jerry\" &lt;b&gt;'x'&lt;/b&gt;&#13;</title>" in text
    assert text.startswith('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<movie>\n') and text.endswith("</movie>\n")
    assert parse_nfo(text.encode("utf-8"))[0][2] == 'Tom & "Jerry" <b>\'x\'</b>\r'


def test_jpeg_payloads_are_valid_and_unique_per_url():
    first, second = corpus.image_payload("https://a.example/1-ok.jpg"), corpus.image_payload("https://a.example/2-ok.jpg")
    assert first != second and first.startswith(b"\xff\xd8") and first.endswith(b"\xff\xd9")
    assert corpus.media_bytes("k", 0) == b"" and len(corpus.media_bytes("k", (1 << 20) + 1)) == (1 << 20) + 1


# =========================================================================== oracle positive / negative controls


def _tree(root):
    os.makedirs(os.path.join(root, "d"))
    for name, data in (("a.bin", b"alpha"), ("d/b.bin", b"beta")):
        with open(os.path.join(root, name), "wb") as handle:
            handle.write(data)
    return str(root)


def test_snapshot_gates_pass_on_equal_and_fail_on_every_kind_of_change(tmp_path):
    root = _tree(tmp_path)
    before = snapshot_tree(root)
    gate_snapshots_equal(before, snapshot_tree(root), "control")
    gate_entries_unchanged(before, snapshot_tree(root), ["a.bin", "d/b.bin"], "control")
    for mutate in (
        lambda: open(os.path.join(root, "new.bin"), "wb").close(),  # added
        lambda: os.remove(os.path.join(root, "a.bin")),  # removed
    ):
        mutate()
        with pytest.raises(AcceptanceGateViolation):
            gate_snapshots_equal(before, snapshot_tree(root), "control")
    with open(os.path.join(root, "d/b.bin"), "wb") as handle:  # changed bytes, same size
        handle.write(b"BETA")
    with pytest.raises(AcceptanceGateViolation):
        gate_snapshots_equal(before, snapshot_tree(root), "control")
    with pytest.raises(AcceptanceGateViolation):
        gate_entries_unchanged(before, snapshot_tree(root), ["d/b.bin"], "control")
    with pytest.raises(AcceptanceGateViolation):
        gate_entries_unchanged(before, snapshot_tree(root), ["a.bin"], "control")  # disappeared


def test_source_not_lost_gate_controls(tmp_path):
    source, final = str(tmp_path / "s.bin"), str(tmp_path / "f.bin")
    with open(source, "wb") as handle:
        handle.write(b"media")
    original = sha256_file(source)
    gate_source_not_lost(source, final, original)  # source present, final absent
    os.rename(source, final)
    gate_source_not_lost(source, final, original)  # moved
    with open(source, "wb") as handle:
        handle.write(b"media")  # both present
    gate_source_not_lost(source, final, original)
    os.remove(source)
    with open(final, "wb") as handle:
        handle.write(b"other bytes")  # the final holds other bytes
    with pytest.raises(AcceptanceGateViolation):
        gate_source_not_lost(source, final, original)
    os.remove(final)
    with pytest.raises(AcceptanceGateViolation):
        gate_source_not_lost(source, final, original)
    with pytest.raises(AcceptanceGateViolation):
        gate_source_not_lost(source, None, original)


def test_write_containment_gate_controls(tmp_path):
    root = str(tmp_path)
    target, source = os.path.join(root, "lib", "FC2-1"), os.path.join(root, "dl", "a.mp4")
    clean = [("execution.mkdir", (target,)), ("execution.rename", (source, os.path.join(target, "FC2-1.mp4"))),
             ("open(write)", (os.path.join(target, ".fc2tmp-" + "0" * 32 + ".part"),))]
    gate_write_paths_contained(clean, sandbox_root=root, allowed_directories=[target], allowed_files=[source])
    for bad in (("open(write)", (os.path.join(root, "outside.bin"),)),  # inside the sandbox, outside the target
                ("os.mkdir", (os.path.join(os.path.dirname(root), "elsewhere"),)),  # outside the sandbox
                ("os.remove", (os.path.join(root, "dl", "other.mp4"),))):  # a file that is not a source of the batch
        with pytest.raises(AcceptanceGateViolation):
            gate_write_paths_contained(clean + [bad], sandbox_root=root, allowed_directories=[target],
                                       allowed_files=[source])
    with pytest.raises(AcceptanceGateViolation):
        gate_path_within(os.path.join(root, "..", "x"), root, "control")


def test_temporary_leftover_gate_controls(tmp_path):
    root = str(tmp_path)
    directory = os.path.join(root, "lib", "FC2-1")
    os.makedirs(directory)
    gate_no_unreported_temporaries(root, [])
    name = ".fc2tmp-" + "a" * 32 + ".part"
    with open(os.path.join(directory, name), "wb") as handle:
        handle.write(b"x")
    with pytest.raises(AcceptanceGateViolation):
        gate_no_unreported_temporaries(root, [])
    gate_no_unreported_temporaries(root, [(directory, name)])  # reported by P4-C7
    gate_no_unreported_temporaries(root, [], preexisting=["lib/FC2-1/" + name])  # a fixture look-alike
    with open(os.path.join(directory, "unrelated.part"), "wb") as handle:
        handle.write(b"x")
    gate_no_unreported_temporaries(root, [(directory, name)])  # ``unrelated.part`` is not an acceptance temporary


def test_layout_and_file_bytes_gate_controls(tmp_path):
    root = _tree(tmp_path)
    gate_layout_exact(root, ["a.bin", "d/b.bin"], ["d"])
    for files, dirs in ((["a.bin"], ["d"]), (["a.bin", "d/b.bin", "x"], ["d"]), (["a.bin", "d/b.bin"], ["d", "e"]),
                        (["a.bin", "d/b.bin"], [])):
        with pytest.raises(AcceptanceGateViolation):
            gate_layout_exact(root, files, dirs)
    gate_file_bytes(os.path.join(root, "a.bin"), b"alpha", "control")
    with pytest.raises(AcceptanceGateViolation):
        gate_file_bytes(os.path.join(root, "a.bin"), b"alpha!", "control")
    with pytest.raises(AcceptanceGateViolation):
        gate_file_bytes(os.path.join(root, "missing.bin"), b"", "control")


def test_nfo_gate_controls():
    merged = corpus.merge_expected(corpus.FX1_FILMS[0].outcomes_at(0))
    text = corpus.expected_nfo_text("FC2-1000001", merged)
    args = dict(number="FC2-1000001", title=merged["title"], tags=merged["tags"], premiered=merged["release"])
    gate_nfo_matches(text.encode("utf-8"), expected_text=text, **args)
    with pytest.raises(AcceptanceGateViolation):  # other bytes than the independent serialization
        gate_nfo_matches(text.replace("alpha", "ALPHA").encode("utf-8"), expected_text=text, **args)
    for tampered in (text.replace("</movie>", "<evil>true</evil></movie>"),  # injected element
                     text.replace("<movie>", "<!DOCTYPE movie [<!ENTITY x 'y'>]>\n<movie>"),  # DTD
                     text.replace("<title>", '<title lang="x">'),  # attribute
                     text.replace("</movie>", "<!-- c --></movie>"),  # comment
                     text.replace("<uniqueid", "<note>x</note>\n  <uniqueid").replace('<title>Title A fx1-01</title>\n', "")):
        with pytest.raises(AcceptanceGateViolation):
            gate_nfo_matches(tampered.encode("utf-8"), expected_text=tampered, **args)  # structure rejects it
    with pytest.raises(AcceptanceGateViolation):
        parse_nfo(b"<movie><title>unclosed</movie>")


def _item(disposition, status=None, state="ready", stage=None, reason=None, kind=None):
    value = lambda v: None if v is None else SimpleNamespace(value=v)  # noqa: E731
    issue = None if stage is None else SimpleNamespace(stage=value(stage), reason=value(reason))
    execution = None if status is None else SimpleNamespace(status=value(status))
    return SimpleNamespace(index=0, disposition=value(disposition), execution=execution, preview_state=value(state),
                           issue=issue, retry_kind=value(kind))


def _result(items, **summary):
    base = dict(total=6, ready=4, blocked=1, unprepared=1, executed=3, success=1, partial=1, failed=1, not_selected=1,
                cancelled=0, rejected=0, aborted=0, retryable=4, deferred=1, non_retryable=0)
    base.update(summary)
    for index, item in enumerate(items):
        item.index = index
    return SimpleNamespace(items=tuple(items), summary=SimpleNamespace(**base), outcome=SimpleNamespace(value="partial"))


def _clean_items():
    return [_item("executed", "success", kind="none"), _item("executed", "partial", kind="resume"),
            _item("executed", "failed", kind="fresh_reexecute"),
            _item("not_ready", None, "unprepared", "metadata", "metadata_unavailable", "metadata_refetch"),
            _item("not_ready", None, "blocked", "preflight", "preflight_blocked", "preflight_recheck"),
            _item("not_selected", None, "ready", None, None, "deferred")]


def test_accounting_and_retry_gates_pass_on_a_hand_computed_result():
    result = _result(_clean_items())
    counts = gate_result_accounting(result)
    assert counts["total"] == 6 and counts["retryable"] == 4 and counts["deferred"] == 1
    assert counts.get("non_retryable", 0) == 0
    gate_retry_kinds(result)
    gate_indices_exactly_once(result, 6)


@pytest.mark.parametrize("break_it", [
    lambda items, summary: summary.update(success=2),  # a summary count that disagrees
    lambda items, summary: summary.update(retryable=3),
    lambda items, summary: summary.update(non_retryable=1),
    lambda items, summary: setattr(items[1], "retry_kind", SimpleNamespace(value="fresh_reexecute")),  # RESUME <-> FRESH
    lambda items, summary: setattr(items[3], "retry_kind", SimpleNamespace(value="none")),
    lambda items, summary: setattr(items[5], "retry_kind", SimpleNamespace(value="none")),
    lambda items, summary: summary.update(outcome="success"),  # a wrong outcome (truth table)
])
def test_accounting_gate_fails_on_planted_corruption(break_it):
    items = _clean_items()
    summary = {}
    break_it(items, summary)
    result = _result(items, **{k: v for k, v in summary.items() if k != "outcome"})
    if "outcome" in summary:
        result.outcome = SimpleNamespace(value=summary["outcome"])
    with pytest.raises(AcceptanceGateViolation):
        gate_result_accounting(result)


def test_index_gate_fails_on_a_dropped_or_duplicated_item():
    result = _result(_clean_items())
    gate_indices_exactly_once(result, 6)
    with pytest.raises(AcceptanceGateViolation):
        gate_indices_exactly_once(SimpleNamespace(items=result.items[:-1]), 6)
    duplicated = list(result.items)
    duplicated[2] = duplicated[1]
    with pytest.raises(AcceptanceGateViolation):
        gate_indices_exactly_once(SimpleNamespace(items=tuple(duplicated)), 6)


def test_expected_retry_kind_table_is_the_frozen_one():
    table = {("executed", "partial"): "resume", ("executed", "failed"): "fresh_reexecute", ("executed", "success"): "none"}
    for (disposition, status), kind in table.items():
        assert expected_retry_kind(_item(disposition, status)) == kind
    assert expected_retry_kind(_item("not_ready", None, "unprepared", "metadata", "metadata_engine_failure")) == "metadata_refetch"
    assert expected_retry_kind(_item("not_ready", None, "blocked", "preflight", "preflight_blocked")) == "preflight_recheck"
    assert expected_retry_kind(_item("not_ready", None, "unprepared", "planning", "planning_rejected")) == "none"
    assert expected_retry_kind(_item("not_ready", None, "blocked", "batch_conflict", "duplicate_source_in_batch")) == "none"
    for disposition, kind in (("not_selected", "deferred"), ("cancelled", "deferred"), ("rejected", "none"),
                              ("aborted", "none")):
        assert expected_retry_kind(_item(disposition)) == kind


def test_diagnostics_gates_controls():
    clean = json.dumps({"schema": DIAGNOSTICS_SCHEMA, "schema_version": DIAGNOSTICS_SCHEMA_VERSION, "kind": "preview",
                        "items": [{"index": 0}, {"index": 1}]}, sort_keys=True, separators=(",", ":")).encode("ascii")
    gate_diagnostics_structure(clean, schema=DIAGNOSTICS_SCHEMA, schema_version=DIAGNOSTICS_SCHEMA_VERSION, kind="preview",
                               items_expected=2)
    gate_diagnostics_canaries(clean, forbidden=corpus.FX5_ALWAYS_FORBIDDEN)
    leaked = clean.replace(b'"preview"', b'"preview","note":"C10CANARY-AUTH"')
    with pytest.raises(AcceptanceGateViolation):
        gate_diagnostics_canaries(leaked, forbidden=corpus.FX5_ALWAYS_FORBIDDEN)
    escaped = json.dumps({"x": "C10CANARY‑TEXT C10CANARYDIR"}, ensure_ascii=True).encode("ascii")
    with pytest.raises(AcceptanceGateViolation):  # the JSON-escaped form is scanned as well
        gate_diagnostics_canaries(escaped, forbidden=["C10CANARYDIR"])
    for kwargs in (dict(schema="other"), dict(schema_version="9.9"), dict(kind="execution"), dict(items_expected=3)):
        args = dict(schema=DIAGNOSTICS_SCHEMA, schema_version=DIAGNOSTICS_SCHEMA_VERSION, kind="preview", items_expected=2)
        args.update(kwargs)
        with pytest.raises(AcceptanceGateViolation):
            gate_diagnostics_structure(clean, **args)
    with pytest.raises(AcceptanceGateViolation):  # not the compact key-sorted form
        gate_diagnostics_structure(json.dumps({"schema": DIAGNOSTICS_SCHEMA, "items": []}, indent=2).encode("ascii"),
                                   schema=DIAGNOSTICS_SCHEMA, schema_version=DIAGNOSTICS_SCHEMA_VERSION, kind="preview",
                                   items_expected=0)


def test_determinism_peak_and_network_gate_controls():
    gate_deterministic_equal((1, 2), (1, 2))
    with pytest.raises(AcceptanceGateViolation):
        gate_deterministic_equal((1, 2), (2, 1))
    gate_peak(2, limit=2, expect_reached=True)
    gate_peak(1, limit=2, expect_reached=False)
    with pytest.raises(AcceptanceGateViolation):
        gate_peak(3, limit=2, expect_reached=False)
    with pytest.raises(AcceptanceGateViolation):
        gate_peak(1, limit=2, expect_reached=True)
    gate_no_network([])
    with pytest.raises(AcceptanceGateViolation):
        gate_no_network(["socket.getaddrinfo"])


# =========================================================================== sandbox guard


def test_sandbox_guard_accepts_inside_and_refuses_outside_and_the_repository(tmp_path):
    sandbox = Sandbox(tmp_path)
    inside = str(tmp_path / "downloads" / "x.mp4")
    assert sandbox.require(inside) == inside
    for outside in (os.path.dirname(str(tmp_path)), os.path.join(os.path.dirname(str(tmp_path)), "sibling"),
                    os.path.abspath(os.sep), str(tmp_path / ".." / "up")):
        with pytest.raises(AcceptanceGateViolation):
            sandbox.require(outside)
    repository = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    for unsafe_root in (repository, os.path.join(repository, "fc2-organizer"), os.path.dirname(repository),
                        os.path.abspath(os.sep)):
        with pytest.raises(AcceptanceGateViolation):
            Sandbox(unsafe_root)


def test_a_chain_refuses_a_library_root_outside_the_disposable_tree(tmp_path):
    with pytest.raises(AcceptanceGateViolation):
        Chain(tmp_path, corpus.FX1_FILMS[:1], library_name=".." + os.sep + "escaped-library")
    assert not os.path.exists(os.path.join(os.path.dirname(str(tmp_path)), "escaped-library"))


# =========================================================================== real components, no shortcuts


def test_the_chain_uses_the_real_components(tmp_path):
    with Chain(tmp_path, corpus.FX1_FILMS[:2]) as chain:
        assert type(chain.engine) is MultiSourceEngine and type(chain.client) is HttpxImageClient
        assert type(chain.orchestrator) is BatchOrchestrator
        preview = chain.preview()
        assert preview.summary.ready == 2
        assert chain.sources.numbers_called and chain.routes.requests  # the scripted sources / MockTransport were used
        assert not any(url.startswith("http://10.") for url in chain.routes.requests)
        result = chain.execute(preview)
        assert result.summary.success == 2


# =========================================================================== write observer / socket trap / restore


def test_write_observer_records_modifications_and_ignores_reads_and_user_actions(tmp_path):
    with Chain(tmp_path, corpus.FX1_FILMS[:1]) as chain:
        chain.observer.take()
        probe = os.path.join(chain.library, "probe.bin")
        with open(probe, "wb") as handle:
            handle.write(b"x")
        assert [op for op, _ in chain.observer.take()] == ["open(write)"]
        with open(probe, "rb") as handle:
            handle.read()
        assert chain.observer.take() == []  # a read-only open is not a modification
        with io.open(probe, "ab") as handle:
            handle.write(b"y")
        fd = os.open(probe, os.O_WRONLY)
        os.close(fd)
        os.mkdir(os.path.join(chain.library, "d"))
        os.rename(probe, os.path.join(chain.library, "d", "moved.bin"))
        os.remove(os.path.join(chain.library, "d", "moved.bin"))
        execution_fs._FS.mkdir(os.path.join(chain.library, "seam"))
        operations = {op for op, _ in chain.observer.take()}
        assert {"open(write)", "os.open(write)", "os.mkdir", "os.rename", "os.remove", "execution.mkdir"} <= operations
        with chain.user_action():
            with open(os.path.join(chain.library, "by-the-user.bin"), "wb") as handle:
                handle.write(b"u")
        assert chain.observer.take() == []
        # the gate fails on a planted write outside every allowed directory (negative control for SI-15)
        with open(os.path.join(chain.root, "stray.bin"), "wb") as handle:
            handle.write(b"s")
        with pytest.raises(AcceptanceGateViolation):
            gate_write_paths_contained(chain.observer.take(), sandbox_root=chain.root,
                                       allowed_directories=[os.path.join(chain.library, "FC2-1000001")],
                                       allowed_files=[])


def test_socket_trap_fires_on_every_primitive_and_the_gate_reports_it(tmp_path):
    with Chain(tmp_path, corpus.FX1_FILMS[:1]) as chain:
        gate_no_network(chain.trap.hits)
        hits = chain.trap.exercise()
        assert {"socket.create_connection", "socket.getaddrinfo", "socket.gethostbyname", "socket.connect"} <= set(hits)
        with pytest.raises(AcceptanceGateViolation):
            gate_no_network(chain.trap.hits)
        chain.trap.hits.clear()
        gate_no_network(chain.trap.hits)


def test_the_chain_restores_every_binding_it_replaced(tmp_path):
    originals = [(builtins, "open"), (io, "open"), (os, "open"), (os, "mkdir"), (os, "rename"), (os, "remove"),
                 *trapped_primitives(),
                 (execution_fs, "_FS"), (materialization_atomic, "_FS"), (orchestration_execute, "execute_filesystem")]
    before = [getattr(target, name) for target, name in originals]
    with Chain(tmp_path, corpus.FX1_FILMS[:1]) as chain:
        during = [getattr(target, name) for target, name in originals]
        assert all(a is not b for a, b in zip(before, during)), "every seam is wrapped while the chain is installed"
        chain.preview()
    assert [getattr(target, name) for target, name in originals] == before
    assert all(getattr(target, name) is original for (target, name), original in zip(originals, before))


def test_wrapping_is_transparent_the_result_projection_is_unchanged(tmp_path):
    def run(root, instrument):
        with Chain(root, corpus.FX1_FILMS[:4], instrument=instrument) as chain:
            if not instrument:
                assert builtins.open is chain_free_open
            preview = chain.preview()
            result = chain.execute(preview, gates=instrument)
            return (result_projection(chain.root, preview), result_projection(chain.root, result),
                    sorted(snapshot_tree(chain.library)))

    chain_free_open = builtins.open
    assert run(tmp_path / "wrapped", True) == run(tmp_path / "bare", False)


# =========================================================================== fault injection / forced cross volume


def test_injected_faults_fire_exactly_once_and_vacuous_injection_is_detected(tmp_path):
    with Chain(tmp_path, corpus.FX1_FILMS[:3]) as chain:
        preview = chain.preview()
        victim = preview.items[0]
        source_of_second = preview.items[1].source_path
        chain.faults.fail("execution", "mkdir", victim.target_directory, OSError(errno.EACCES, "injected"))
        chain.faults.fail("execution", "lstat", source_of_second, OSError(errno.EIO, "injected"))
        assert chain.faults.fired == []  # armed only while executing (the preview already ran un-armed)
        result = chain.execute(preview)
        assert len(chain.faults.fired) == 2
        chain.faults.assert_all_fired()
        assert [i.execution.status.value for i in result.items] == ["failed", "failed", "success"]
        # negative control: a rule that matches nothing is reported
        chain.faults.fail("execution", "unlink", os.path.join(chain.library, "never"), OSError(errno.EIO, "x"))
        with pytest.raises(AcceptanceGateViolation):
            chain.faults.assert_all_fired()


def test_forced_cross_volume_reaches_the_executor_and_keeps_the_bytes(tmp_path):
    films = corpus.FX1_FILMS[:3] + (corpus.FX1_FILMS[8],)  # includes the 1 MiB + 1 and the 0 byte file
    with Chain(tmp_path / "native", films) as native:
        result = native.execute(native.preview())
        assert {i.execution.transfer_mode.value for i in result.items} == {"same_volume"}
    with Chain(tmp_path / "forced", films) as chain:
        chain.force_cross_volume()
        preview = chain.preview()
        assert {i.preflight.transfer_mode.value for i in preview.items} == {"cross_volume"}
        result = chain.execute(preview)
        assert {i.execution.transfer_mode.value for i in result.items} == {"cross_volume"}
        assert chain.fs.cross_volume_calls > 0
        by_number = {film.number: film for film in films}
        for item in result.items:
            film = by_number[item.canonical_number]
            gate_file_bytes(item.final_media_path, film.content, "cross-volume media bytes")
            assert not os.path.exists(chain.source_path(film))  # the source was removed after the verified copy
        assert len(result.items) == len(films)


# =========================================================================== concurrency gates


def test_hold_gates_reach_each_budget_exactly_and_never_exceed_it(tmp_path):
    with Chain(tmp_path, corpus.FX1_FILMS[:8], config=CONFIG_2, hold_items=2, hold_images=2, hold_exec=2) as chain:
        preview = chain.preview()
        result = chain.execute(preview)
        assert result.summary.success == 8
        gate_peak(chain.sources.peak_items, limit=2, expect_reached=True)
        gate_peak(chain.routes.peak, limit=2, expect_reached=True)
        gate_peak(chain.exec_probe.peak, limit=2, expect_reached=True)


def test_reverse_gates_invert_the_completion_order_of_each_stage(tmp_path):
    with Chain(tmp_path, corpus.FX1_FILMS[:8], config=CONFIG_4, reverse=True) as chain:
        preview = chain.preview()
        result = chain.execute(preview)
        assert result.summary.success == 8
        for gate in (chain.sources.reverse, chain.routes.reverse, chain.exec_probe.reverse):
            assert len(gate.arrival) == 4 and gate.release == gate.arrival[::-1]
        gated = chain.sources.reverse.release
        assert [n for n in chain.sources.completion_order if n in gated] == gated  # the gated items finished reversed
        assert [i.index for i in result.items] == list(range(8))  # ... yet the result stays in index order


# =========================================================================== gates wired into the chain


def test_the_chain_preview_trips_on_a_stage_that_mutates_the_filesystem(tmp_path):
    with Chain(tmp_path, corpus.FX1_FILMS[:2]) as chain:
        real = preview_module.preflight_stage
        original = preview_module.preflight_stage

        def mutating(*args, **kwargs):
            os.makedirs(os.path.join(chain.library, "created-by-a-preview-stage"), exist_ok=True)
            return real(*args, **kwargs)

        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(preview_module, "preflight_stage", mutating)
            with pytest.raises(AcceptanceGateViolation):
                chain.preview()
        assert preview_module.preflight_stage is original  # binding restored
        os.rmdir(os.path.join(chain.library, "created-by-a-preview-stage"))
        chain.preview()  # positive control: the same chain previews fine without the mutant


def test_diagnostics_of_a_real_chain_pass_the_diagnostics_gates(tmp_path):
    with Chain(tmp_path, corpus.FX1_FILMS[:3]) as chain:
        preview = chain.preview()
        result = chain.execute(preview)
        for model, kind in ((preview, "preview"), (result, "execution")):
            for policy in (PathPolicy.NONE, PathPolicy.BASENAME):
                rendered = diagnostics_bytes(model, policy)
                gate_diagnostics_structure(rendered, schema=DIAGNOSTICS_SCHEMA, schema_version=DIAGNOSTICS_SCHEMA_VERSION,
                                           kind=kind, items_expected=3)
                gate_diagnostics_canaries(rendered, forbidden=corpus.FX5_ALWAYS_FORBIDDEN)
