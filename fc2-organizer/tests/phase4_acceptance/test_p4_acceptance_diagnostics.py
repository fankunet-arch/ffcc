"""P4-C10 S2: S-18, the diagnostics scenario (contract section 7.2, FX-5; link L-14; SI-18).

Diagnostics of real-chain products: class A canaries are planted in every source-controlled text channel (failure
``error_detail`` text with an ``Authorization`` header and a ``Cookie``, titles / plots, an image URL query, an exception
message, the source parent directory and the library root, secret-like file names) and must never appear in the
rendered JSON, under the default ``PathPolicy.NONE`` nor under an explicit ``BASENAME``; the default output contains
no ``C10CANARY`` at all. A diagnosed model is consumed by nothing: the preview still executes, the result still previews
its retry and the retry result still merges.
"""

from __future__ import annotations

import json

from . import _corpus as corpus
from ._corpus import FX5_ALWAYS_FORBIDDEN, FX5_CANARIES
from ._harness import CONFIG_4, Chain, MixedBatch, diagnostics_bytes, diagnostics_model, transfer_operation
from ._oracles import gate_default_output_clean, gate_diagnostics_canaries, gate_diagnostics_structure
from fc2_organizer.diagnostics import (
    DIAGNOSTICS_SCHEMA,
    DIAGNOSTICS_SCHEMA_VERSION,
    PathPolicy,
    TimingPolicy,
    build_execution_diagnostics,
    build_preview_diagnostics,
    render_diagnostics_json,
)
from fc2_organizer.orchestration import RetryKind


def structure(rendered, kind, model):
    return gate_diagnostics_structure(rendered, schema=DIAGNOSTICS_SCHEMA, schema_version=DIAGNOSTICS_SCHEMA_VERSION,
                                      kind=kind, indices=[i.index for i in model.items])


def both_policies(model, kind):
    """Render under ``NONE`` (the default) and an explicit ``BASENAME``; returns ``(none_bytes, basename_bytes)`` after the
    structure and class A canary gates."""
    none, named = diagnostics_bytes(model), diagnostics_bytes(model, PathPolicy.BASENAME)
    for rendered in (none, named):
        structure(rendered, kind, model)
        gate_diagnostics_canaries(rendered, forbidden=FX5_ALWAYS_FORBIDDEN)
    return none, named


def test_s18_canaries_never_leak_and_the_default_output_has_no_canary_at_all(tmp_path):
    """S-18 (L-14, SI-18): FX-5 canaries in every channel; PREVIEW and EXECUTION diagnostics, both path policies."""
    films = list(corpus.fx5_films())
    victim = films[2]
    with Chain(tmp_path, films, library_name=FX5_CANARIES["root"], config=CONFIG_4) as chain:
        assert FX5_CANARIES["dir"] in chain.source_path(films[0]) and FX5_CANARIES["root"] in chain.library
        preview = chain.preview()
        assert preview.summary.ready == 3
        # the planted channels really reached the pipeline (non-vacuity): the failure detail sits in the aggregate,
        # the title in the metadata, the token in a requested URL
        failing = preview.items[0].metadata.aggregation_result
        details = " ".join(r.error_detail or "" for r in failing.source_results)
        assert FX5_CANARIES["auth"] in details and FX5_CANARIES["cookie"] in details
        assert FX5_CANARIES["text"] in failing.metadata.title
        assert any(FX5_CANARIES["url"] in url for url in chain.routes.requests)
        none, named = both_policies(preview, "preview")
        gate_default_output_clean(none)  # the default NONE: not even a file / directory name
        assert b"Authorization-C10CANARY.mp4" in named  # BASENAME emits the (secret-like) base names, only those
        assert FX5_CANARIES["dir"].encode() not in named and FX5_CANARIES["root"].encode() not in named
        chain.faults.fail("execution", transfer_operation(), chain.source_path(victim),
                          RuntimeError(FX5_CANARIES["exc"]))
        result = chain.execute(preview)  # the preview was not consumed by the diagnostics above
        chain.faults.assert_all_fired()
        assert result.summary.aborted == 1 and result.summary.success == 2
        none, named = both_policies(result, "execution")
        gate_default_output_clean(none)
        assert FX5_CANARIES["exc"] not in repr(result) and FX5_CANARIES["exc"].encode() not in named
        # a timing policy and the path policy change nothing about the class A guarantee
        full = render_diagnostics_json(build_execution_diagnostics(result, path_policy=PathPolicy.BASENAME,
                                                                   timing_policy=TimingPolicy.INCLUDE))
        gate_diagnostics_canaries(full, forbidden=FX5_ALWAYS_FORBIDDEN)
        tree = json.loads(none)
        assert tree["kind"] == "execution" and tree["shape"] == "main" and tree["batch_size"] == 3
        assert [item["retry_kind"] for item in tree["items"]].count("none") == 3  # SUCCESS, SUCCESS, ABORTED


def test_s18_diagnostics_of_every_generation_consume_nothing_and_are_deterministic(tmp_path):
    """S-18 (L-14): representative forms of S-01..S-17 -- the FX-2 mixture and its whole retry chain -- are diagnosed after
    every step; the chain proceeds afterwards (nothing was consumed) and rendering twice gives identical bytes."""
    plan = corpus.FX2_PLAN
    mixed = corpus.MixedCorpus(plan)
    with Chain(tmp_path, mixed.films, config=CONFIG_4) as chain:
        batch = MixedBatch(chain, mixed)
        batch.prepare()
        preview = chain.preview(chain.discover())
        none, _named = both_policies(preview, "preview")
        assert diagnostics_bytes(preview) == none  # rendering is a pure function of the model
        gate_default_output_clean(none)  # the failure details of the scripted sources carry class A text
        batch._arm_g0_faults(preview)
        selection = tuple(sorted(i.index for i in preview.items if i.state.value == "ready" and batch.group_of(i) != "J"))
        result = chain.execute(preview, selection=selection)
        chain.faults.assert_all_fired()
        for model, kind in ((preview, "preview"), (result, "execution")):
            both_policies(model, kind)
        assert diagnostics_model(result).execution_summary == result.summary
        # PREVIEW of the retry, then its result, then the merged result: each diagnosed, then used
        retry_preview = chain.preview_retry(result, None)
        both_policies(retry_preview, "preview")
        retry_result = chain.execute(retry_preview)
        both_policies(retry_result, "execution")
        merged = chain.merge(result, retry_result)
        none, _named = both_policies(merged, "execution")
        gate_default_output_clean(none)
        shapes = {json.loads(diagnostics_bytes(m))["shape"] for m in (result, retry_result, merged)}
        assert shapes == {"main", "retry", "merged"}


def test_l14_diagnostics_models_agree_with_the_models_they_describe(tmp_path):
    """L-14: PREVIEW / EXECUTION diagnostics of a real batch repeat exactly the summary, outcome and per-item retry kind of
    the P4-C8 result (cross-package consistency; the numbers come from the P4-C8 models, the rendering from P4-C9)."""
    mixed = corpus.MixedCorpus(corpus.FX2_PLAN)
    with Chain(tmp_path, mixed.films, config=CONFIG_4) as chain:
        batch = MixedBatch(chain, mixed)
        batch.prepare()
        preview, result = batch.g0()
        diag_preview, diag_result = diagnostics_model(preview), diagnostics_model(result)
        assert diag_preview.preview_summary == preview.summary and diag_preview.batch_size == preview.batch_size
        assert diag_result.execution_summary == result.summary and diag_result.outcome is result.outcome
        for item, diagnostic in zip(result.items, diag_result.items):
            assert diagnostic.index == item.index and diagnostic.retry_kind is item.retry_kind
            assert diagnostic.disposition is item.disposition and diagnostic.canonical_number == item.canonical_number
        tree = json.loads(diagnostics_bytes(result))
        assert tree["execution_summary"]["total"] == result.summary.total
        assert tree["outcome"] == result.outcome.value
        assert {i["retry_kind"] for i in tree["items"]} == {k.value for k in
                                                          {i.retry_kind for i in result.items}}
        assert RetryKind.RESUME.value in {i["retry_kind"] for i in tree["items"]}
        assert build_preview_diagnostics(preview).items[0].index == 0
