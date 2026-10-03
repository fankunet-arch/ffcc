"""P4-C9 contract sections 17 / 18 / 28.5 (redaction canaries): channel-A secrets never appear under any policy, the
secret-like basenames of channel B appear only under the explicit ``BASENAME`` opt-in, control-character names are an
unsafe value under ``BASENAME`` and invisible under ``NONE``. Every scan is shown to be non-vacuous by a mutation that
makes the canary appear (or the pipeline fail)."""

from __future__ import annotations

import os

import pytest
from fc2_metadata_core.normalize import normalize_fc2_number
from fc2_organizer.diagnostics import (
    DiagnosticsUnsafeValueError,
    PathPolicy,
    TimingPolicy,
    build_execution_diagnostics,
    build_preview_diagnostics,
    render,
    render_diagnostics_json,
    validation,
)
from orchestration._helpers import Corpus, Film

from fc2_metadata_core.aggregation import FieldConflict
from fc2_organizer.diagnostics import models
from . import _builders as b

CANARY = b"C9CANARY"
POLICIES = [(PathPolicy.NONE, TimingPolicy.OMIT), (PathPolicy.NONE, TimingPolicy.INCLUDE),
            (PathPolicy.BASENAME, TimingPolicy.OMIT), (PathPolicy.BASENAME, TimingPolicy.INCLUDE)]

A_CHANNEL = [b"C9CANARY-AUTH", b"C9CANARY-COOKIE", b"C9CANARY-TEXT", b"C9CANARY-URL", b"C9CANARY-KEY",
             b"C9CANARY-VAL", b"C9CANARY-EXC", b"C9CANARY-PLOT", b"C9CANARY-DETAIL", b"C9CANARYDIR",
             b"C9CANARYROOT", b"Bearer", b"session=", b"token="]
SECRET_NAMES = ["Authorization-C9CANARY FC2-PPV-1000001.mp4", "FC2-PPV-1000002-Cookie-C9CANARY.mp4",
                "token-C9CANARY-FC2-PPV-1000003.mp4"]


def canary_corpus(tmp_path):
    root = tmp_path / "C9CANARYROOT"
    root.mkdir()
    films = [Film(SECRET_NAMES[0], directory="C9CANARYDIR"), Film(SECRET_NAMES[1], directory="C9CANARYDIR",
                                                                   kind="partial"),
             Film(SECRET_NAMES[2], directory="C9CANARYDIR", kind="engine"), Film("FC2-PPV-1000004.mp4", kind="failed")]
    corpus = Corpus(root, films)
    for number in ("FC2-1000001", "FC2-1000002"):
        corpus.engine.fields.setdefault(number, {}).update(
            title="C9CANARY-TEXT", plot="C9CANARY-PLOT", source_urls=("https://x.invalid/a?token=C9CANARY-URL",),
            external_ids={"C9CANARY-KEY": "C9CANARY-VAL"})
    corpus.engine.script[normalize_fc2_number(SECRET_NAMES[2]).canonical] = RuntimeError("C9CANARY-EXC")
    return corpus


def outputs(corpus, path_policy, timing_policy):
    orchestrator = corpus.orchestrator()
    preview = corpus.preview(orchestrator)
    result = orchestrator.execute(preview)
    return [render_diagnostics_json(build_preview_diagnostics(preview, path_policy=path_policy,
                                                              timing_policy=timing_policy)),
            render_diagnostics_json(build_execution_diagnostics(result, path_policy=path_policy,
                                                                timing_policy=timing_policy))]


@pytest.fixture
def corpus(tmp_path):
    return canary_corpus(tmp_path)


@pytest.mark.parametrize(("path_policy", "timing_policy"), POLICIES)
def test_channel_a_canaries_never_appear_under_any_policy(corpus, path_policy, timing_policy):
    for data in outputs(corpus, path_policy, timing_policy):
        for canary in A_CHANNEL:
            assert canary not in data, canary
        assert str(corpus.root).encode() not in data and b"C9CANARYDIR" not in data


def test_the_default_policy_outputs_no_secret_like_basename(corpus):
    orchestrator = corpus.orchestrator()
    preview = corpus.preview(orchestrator)
    result = orchestrator.execute(preview)
    for data in (render_diagnostics_json(build_preview_diagnostics(preview)),
                 render_diagnostics_json(build_execution_diagnostics(result))):
        assert CANARY not in data and b"Authorization" not in data and b"Cookie" not in data
        assert b"token" not in data and b".mp4" not in data


def test_the_explicit_basename_policy_discloses_the_basenames_but_not_the_parents(corpus):
    data = outputs(corpus, PathPolicy.BASENAME, TimingPolicy.OMIT)
    for rendered in data:
        for name in SECRET_NAMES:
            assert name.encode() in rendered
        assert b"C9CANARYDIR" not in rendered and b"C9CANARYROOT" not in rendered and b"/" not in rendered


def test_the_source_error_detail_never_appears():
    preview = b.preview_graph()
    source = preview.metadata_batch.items[0].aggregation_result.source_results[1]
    b.poke(source, error_detail="Authorization: Bearer C9CANARY-AUTH Cookie: session=C9CANARY-COOKIE")
    for path_policy, timing_policy in POLICIES:
        data = render_diagnostics_json(build_preview_diagnostics(preview, path_policy=path_policy,
                                                                 timing_policy=timing_policy))
        assert b"C9CANARY" not in data and b"Bearer" not in data


def test_conflict_values_and_metadata_texts_never_appear():
    result = b.make_source_result("src_a")
    third = b.make_source_result("src_c", title="C9CANARY-OTHER-TITLE")
    metadata = b.NormalizedMetadata(number=b.NUMBER, title="C9CANARY-TITLE", plot="C9CANARY-PLOT",
                                    source_urls=("https://x.invalid/?token=C9CANARY-URL",),
                                    external_ids={"C9CANARY-KEY": "C9CANARY-VAL"},
                                    field_sources={"number": ("src_a", "src_c"), "title": ("src_a",)})

    conflict = FieldConflict(field="title", selected_source_id="src_a", selected_value="C9CANARY-TITLE",
                             alternatives=(("src_c", "C9CANARY-OTHER-TITLE"),))
    aggregation = b.make_aggregation([result, third], metadata=metadata, conflicts=(conflict,))
    preview = b.preview_of_metadata(b.batch_item_for(aggregation))
    data = render_diagnostics_json(build_preview_diagnostics(preview, path_policy=PathPolicy.BASENAME,
                                                             timing_policy=TimingPolicy.INCLUDE))
    assert b"C9CANARY" not in data and b'"field":"title"' in data and b"src_c" in data


# ---- control-character names


FORBIDDEN_CHARS = ["\x01", "\x1b", "\x7f", "\x85", " ", "‮", "﻿", "\ud800"]


def source_with(char):
    graph = b.preview_graph()
    item = graph.items[0]
    old = item.media_item.source_path
    new = old.rsplit("/", 1)[0] + "/a" + char + "b.mp4"
    b.poke(item.media_item, source_path=new)
    b.poke(item.plan, source_path=new)
    for path in (item.plan.operations[1].source,):
        b.poke(path, absolute_path=new)
    return graph


@pytest.mark.parametrize("char", FORBIDDEN_CHARS)
def test_a_control_character_name_is_unsafe_under_basename_and_invisible_under_none(char):
    graph = source_with(char)
    with pytest.raises(DiagnosticsUnsafeValueError):
        build_preview_diagnostics(graph, path_policy=PathPolicy.BASENAME)
    data = render_diagnostics_json(build_preview_diagnostics(graph))
    assert char.encode("utf-8", "surrogatepass") not in data
    assert data.isascii() and b"\\u202e" not in data and b"\\ufeff" not in data and b"\\ud800" not in data


def test_the_forbidden_code_point_check_is_not_vacuous(monkeypatch):
    """Mutation: the validation-side grammar check is removed; the model invariant of ``ItemDiagnostics`` (a second,
    independent line of defence) still refuses the name, and with *both* removed the name would reach the output."""
    graph = source_with("\u202e")
    monkeypatch.setattr(validation, "is_safe_basename", lambda value: True)
    with pytest.raises(Exception):
        build_preview_diagnostics(graph, path_policy=PathPolicy.BASENAME)

    monkeypatch.setattr(models, "is_safe_basename", lambda value: True)
    diagnostics = build_preview_diagnostics(graph, path_policy=PathPolicy.BASENAME)
    monkeypatch.setattr(render, "batch_problem", lambda value: None)
    monkeypatch.setattr(render, "is_safe_basename", lambda value: True)
    assert b"\\u202e" in render_diagnostics_json(diagnostics)  # every check gone: the code point is output


# ---- mutations: each leak makes the scan (or the pipeline) fail


def scan_fails(data):
    return any(canary in data for canary in A_CHANNEL + [CANARY])


def run_default_pipeline(corpus):
    orchestrator = corpus.orchestrator()
    preview = corpus.preview(orchestrator)
    return render_diagnostics_json(build_preview_diagnostics(preview))


def test_mutation_default_path_policy_basename_is_killed(corpus, monkeypatch):
    real = build_preview_diagnostics

    def leaky(preview, /, *, path_policy=PathPolicy.BASENAME, timing_policy=TimingPolicy.OMIT):
        return real(preview, path_policy=path_policy, timing_policy=timing_policy)

    orchestrator = corpus.orchestrator()
    preview = corpus.preview(orchestrator)
    assert CANARY not in render_diagnostics_json(real(preview))
    assert CANARY in render_diagnostics_json(leaky(preview))  # the default-NONE assertion above would fail


def test_mutation_none_still_outputs_a_basename_is_killed(corpus, monkeypatch):
    preview = corpus.preview(corpus.orchestrator())
    real_parts = validation.output_parts

    def leaky(item, provenance, path_policy, timing_policy, preflight, execution):
        return real_parts(item, provenance, PathPolicy.BASENAME, timing_policy, preflight, execution)

    monkeypatch.setattr(validation, "output_parts", leaky)
    with pytest.raises(Exception):  # the ItemDiagnostics policy invariant refuses a name under NONE
        build_preview_diagnostics(preview)


def test_mutation_absolute_path_output_is_killed(corpus, monkeypatch):
    preview = corpus.preview(corpus.orchestrator())
    monkeypatch.setattr(validation, "basename_of", lambda path_text: path_text)  # leak the absolute path
    with pytest.raises(Exception):
        build_preview_diagnostics(preview, path_policy=PathPolicy.BASENAME)


def test_mutation_extra_error_detail_or_exception_text_in_the_tree_is_detected(corpus, monkeypatch):
    preview = corpus.preview(corpus.orchestrator())
    real = render.item_tree
    monkeypatch.setattr(render, "item_tree", lambda item: dict(real(item), leak="C9CANARY-EXC"))
    assert scan_fails(render_diagnostics_json(build_preview_diagnostics(preview)))


def test_the_explicit_basename_scan_is_not_vacuous(corpus):
    """The same scan that is clean under NONE does see the (opt-in) basename canary under BASENAME."""
    orchestrator = corpus.orchestrator()
    preview = corpus.preview(orchestrator)
    assert CANARY not in render_diagnostics_json(build_preview_diagnostics(preview))
    assert CANARY in render_diagnostics_json(build_preview_diagnostics(preview, path_policy=PathPolicy.BASENAME))
    assert os.sep.encode() not in render_diagnostics_json(build_preview_diagnostics(
        preview, path_policy=PathPolicy.BASENAME))
