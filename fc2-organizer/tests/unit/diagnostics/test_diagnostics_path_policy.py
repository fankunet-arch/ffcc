"""P4-C9 contract section 18 (``PathPolicy``): the default is ``NONE`` (no path-derived field, no basename computed),
``BASENAME`` is an explicit opt-in that discloses basenames only, and every disclosed basename must satisfy the
lexical grammar of 18.2 (violation -> ``DiagnosticsUnsafeValueError``, never repaired)."""

from __future__ import annotations

import dataclasses
import os

import pytest
from fc2_organizer.diagnostics import (
    MAX_PATH_TEXT_CHARS,
    DiagnosticsInputError,
    DiagnosticsUnsafeValueError,
    PathPolicy,
    build_execution_diagnostics,
    build_preview_diagnostics,
    models,
    validation,
)
from fc2_organizer.execution import ExecutionStatus as X
from fc2_organizer.orchestration import ExecutionDisposition as D, ItemWarning as W
from fc2_organizer.planning import PlannedPath

from . import _builders as b
from . import _builders as h


def planned_paths(node, found=None):
    found = [] if found is None else found
    if isinstance(node, PlannedPath):
        found.append(node)
    elif dataclasses.is_dataclass(node) and not isinstance(node, type):
        for field in dataclasses.fields(node):
            planned_paths(getattr(node, field.name), found)
    elif isinstance(node, tuple):
        for member in node:
            planned_paths(member, found)
    return found


def rename_source(item, new_path):
    """Give ``item`` a new source path *consistently* (media item, plan, every ``PlannedPath`` of the plan)."""
    old = item.media_item.source_path
    b.poke(item.media_item, source_path=new_path)
    b.poke(item.plan, source_path=new_path)
    for path in planned_paths(item.plan):
        if path.absolute_path == old:
            b.poke(path, absolute_path=new_path)


def rename_target_media(item, new_path):
    old = item.plan.target_media_path.absolute_path
    for path in planned_paths(item.plan):
        if path.absolute_path == old:
            b.poke(path, absolute_path=new_path)


def graph_with_source(name):
    graph = h.preview_graph()
    rename_source(graph.items[0], os.path.dirname(graph.items[0].media_item.source_path) + "/" + name)
    return graph


# ---- the default and the explicit policies


def test_the_default_policy_is_none_and_every_path_derived_field_is_none():
    for kind in ("preview", "execution"):
        diag = h.BUILD[kind](h.FACTORY[kind]())
        assert diag.path_policy is PathPolicy.NONE
        for item in diag.items:
            assert item.source_name is None and item.target_directory_name is None
            assert item.target_media_name is None


def test_none_never_computes_a_disclosed_basename(monkeypatch):
    """Validation-only structural checks may take a basename internally (contract 9.6.5); the *disclosure*
    computation (``basename_of``) runs only under ``BASENAME``."""
    calls = []
    real = validation.basename_of
    monkeypatch.setattr(validation, "basename_of", lambda text: calls.append(text) or real(text))
    h.BUILD["preview"](h.preview_graph())
    assert calls == []
    h.BUILD["preview"](h.preview_graph(), path_policy=PathPolicy.BASENAME)
    assert len(calls) == 6  # source + directory + media for each of the two items (the spy is not vacuous)


def test_basename_discloses_exactly_the_basenames_of_the_source_and_the_target():
    graph = h.preview_graph()
    diag = build_preview_diagnostics(graph, path_policy=PathPolicy.BASENAME)
    assert diag.path_policy is PathPolicy.BASENAME
    for item, shown in zip(graph.items, diag.items):
        assert shown.source_name == os.path.basename(item.media_item.source_path)
        assert shown.target_directory_name == os.path.basename(item.plan.target_directory.absolute_path)
        assert shown.target_media_name == os.path.basename(item.plan.target_media_path.absolute_path)
        assert os.sep not in shown.source_name and shown.source_name != item.media_item.source_path


def test_no_directory_or_library_root_or_absolute_path_is_ever_disclosed():
    graph = h.preview_graph()
    text = repr(build_preview_diagnostics(graph, path_policy=PathPolicy.BASENAME))
    for item in graph.items:
        for path in planned_paths(item.plan):
            assert path.absolute_path not in text
    assert graph.library_root not in text and os.path.dirname(graph.items[0].media_item.source_path) not in text


def test_leftover_temporary_names_follow_the_policy():
    lineage = b.Lineage(1)
    execution = b.rich_execution(lineage.plans[0], X.PARTIAL, leftovers=2)
    item = lineage.execution_item(0, D.EXECUTED, execution=execution, warnings=(W.LEFTOVER_TEMPORARIES,),
                                  material=True)
    result = lineage.result([item])
    none = build_execution_diagnostics(result).items[0].execution.leftover_temporaries
    named = build_execution_diagnostics(result, path_policy=PathPolicy.BASENAME).items[0].execution
    assert all(t.name is None for t in none)
    assert [t.name for t in named.leftover_temporaries] == [t.name for t in execution.leftover_temporaries]
    assert all(t.directory_role is not None for t in none)


@pytest.mark.parametrize("bad", [None, "none", "basename", 0, True, object()])
def test_the_policy_must_be_an_exact_enum(bad):
    with pytest.raises(DiagnosticsInputError):
        build_preview_diagnostics(h.preview_graph(), path_policy=bad)


# ---- 18.2 grammar: forbidden basenames fail only when they would be disclosed
#
# Two different concepts are kept apart (contract 18.1 / 18.2):
#   A. the grammar of the *final, already extracted* basename ``b`` -- platform independent: "/" and "\\" are
#      forbidden in ``b`` on every platform (FORBIDDEN_NAMES below and the FINAL_BASENAME_* tests);
#   B. the *native extraction* ``os.path.basename(raw path)`` -- platform native (contract 18.1: "the running
#      platform's path semantics"): a raw "\\" is a separator on Windows (``a\\b.mp4`` -> ``b.mp4``) but an ordinary
#      character on POSIX (``a\\b.mp4`` stays, so the final basename is unsafe). The NATIVE_* tests below.
# FORBIDDEN_NAMES therefore holds only names whose unsafety does not depend on how a raw path is split.


FORBIDDEN_NAMES = {
    "nul": "a\x00b.mp4", "tab": "a\tb.mp4", "lf": "a\nb.mp4", "cr": "a\rb.mp4", "c0": "a\x1fb.mp4",
    "del": "a\x7fb.mp4", "c1_low": "a\x80b.mp4", "c1_high": "a\x9fb.mp4", "lone_surrogate": "a\ud800b.mp4",
    "surrogate_high": "a\udfffb.mp4", "ls": "a b.mp4", "ps": "a b.mp4", "alm": "a؜b.mp4",
    "lrm": "a‎b.mp4", "rlm": "a‏b.mp4", "lre": "a‪b.mp4", "rlo": "a‮b.mp4",
    "lri": "a⁦b.mp4", "pdi": "a⁩b.mp4", "bom": "a﻿b.mp4",
    "dotdot": "..", "dot": ".", "too_long": "x" * (MAX_PATH_TEXT_CHARS + 1),
}
ALLOWED_NAMES = {
    "plain": "movie.mp4", "space": "my movie.mp4", "ideographic_space": "a　b.mp4", "japanese": "映画.mp4",
    "emoji": "a\U0001f600.mp4", "at_limit": "x" * (MAX_PATH_TEXT_CHARS - 4) + ".mp4", "unicode_dash": "a–b.mp4",
    "u2027_next_to_ls": "a‧b.mp4", "u2065": "a⁥b.mp4", "u2070": "a⁰b.mp4",
}


@pytest.mark.parametrize("name", sorted(FORBIDDEN_NAMES))
def test_a_forbidden_source_basename_is_unsafe_under_basename(name):
    graph = graph_with_source(FORBIDDEN_NAMES[name])
    with pytest.raises(DiagnosticsUnsafeValueError) as caught:
        build_preview_diagnostics(graph, path_policy=PathPolicy.BASENAME)
    assert type(caught.value) is DiagnosticsUnsafeValueError
    assert FORBIDDEN_NAMES[name] not in str(caught.value)


@pytest.mark.parametrize("name", sorted(FORBIDDEN_NAMES))
def test_a_forbidden_source_basename_does_not_fail_under_none(name):
    graph = graph_with_source(FORBIDDEN_NAMES[name])
    diag = build_preview_diagnostics(graph)
    assert diag.items[0].source_name is None


@pytest.mark.parametrize("name", sorted(ALLOWED_NAMES))
def test_an_allowed_basename_is_disclosed_unchanged(name):
    graph = graph_with_source(ALLOWED_NAMES[name])
    diag = build_preview_diagnostics(graph, path_policy=PathPolicy.BASENAME)
    assert diag.items[0].source_name == ALLOWED_NAMES[name]


def test_the_length_boundary_is_inclusive():
    exact = "x" * MAX_PATH_TEXT_CHARS
    assert validation.is_safe_basename(exact) is True
    assert validation.is_safe_basename(exact + "x") is False
    assert validation.is_safe_basename("") is False


@pytest.mark.parametrize("name", sorted(FORBIDDEN_NAMES))
def test_the_disclosure_helper_applies_the_same_grammar_to_every_path_derived_text(name):
    """The target directory / media names are bound to the canonical number by the planning layout (contract
    9.6.5), so the grammar is exercised on them through the shared helper."""
    with pytest.raises(DiagnosticsUnsafeValueError):
        validation.basename_of("/lib/FC2-1/" + FORBIDDEN_NAMES[name])


# ---- A. final basename grammar (platform independent): "/" and "\\" are forbidden in the *extracted* basename

FINAL_BASENAME_SEPARATORS = {"slash": "a/b.mp4", "backslash": "a\\b.mp4", "leading_slash": "/b.mp4",
                             "trailing_backslash": "b.mp4\\"}


@pytest.mark.parametrize("name", sorted(FINAL_BASENAME_SEPARATORS))
def test_a_separator_in_the_final_basename_is_never_safe_on_any_platform(name):
    text = FINAL_BASENAME_SEPARATORS[name]
    assert validation.is_safe_basename(text) is False
    assert models.is_safe_basename(text) is False  # the same grammar as the diagnostics-model invariant
    assert models.is_opt_safe_basename(text) is False


def test_the_separator_free_counterpart_of_each_final_basename_is_safe():
    for text in ("b.mp4", "ab.mp4", "a b.mp4"):
        assert validation.is_safe_basename(text) is True and models.is_safe_basename(text) is True


# ---- B. native extraction: the platform's own ``os.path.basename`` decides what is disclosed

RAW_WITH_BACKSLASH = "/lib/FC2-1/a\\b.mp4"
WINDOWS_NATIVE = "C:\\lib\\FC2-1\\a\\b.mp4"
POSIX_NATIVE = "/lib/FC2-1/b.mp4"


def test_native_extraction_of_a_raw_backslash_follows_the_running_platform():
    extracted = os.path.basename(RAW_WITH_BACKSLASH)
    if os.name == "nt":
        assert extracted == "b.mp4"  # ntpath: "\\" is a separator, the final basename is legal
        assert validation.basename_of(RAW_WITH_BACKSLASH) == "b.mp4"
    else:
        assert extracted == "a\\b.mp4"  # posixpath: "\\" is an ordinary character ...
        with pytest.raises(DiagnosticsUnsafeValueError) as caught:  # ... so the final basename is unsafe
            validation.basename_of(RAW_WITH_BACKSLASH)
        assert type(caught.value) is DiagnosticsUnsafeValueError and "a\\b" not in str(caught.value)


def test_native_extraction_positive_controls():
    if os.name == "nt":
        assert validation.basename_of(WINDOWS_NATIVE) == "b.mp4"
    assert validation.basename_of(POSIX_NATIVE) == "b.mp4"  # a forward-slash path works on both platforms


def test_end_to_end_a_raw_backslash_in_the_source_path_follows_native_extraction():
    graph = graph_with_source("a\\b.mp4")
    if os.name == "nt":
        assert build_preview_diagnostics(graph, path_policy=PathPolicy.BASENAME).items[0].source_name == "b.mp4"
    else:
        with pytest.raises(DiagnosticsUnsafeValueError):
            build_preview_diagnostics(graph, path_policy=PathPolicy.BASENAME)


def test_none_neither_extracts_nor_judges_a_raw_backslash(monkeypatch):
    calls = []
    real = validation.basename_of
    monkeypatch.setattr(validation, "basename_of", lambda text: calls.append(text) or real(text))
    diag = build_preview_diagnostics(graph_with_source("a\\b.mp4"))  # default PathPolicy.NONE
    item = diag.items[0]
    assert (item.source_name, item.target_directory_name, item.target_media_name) == (None, None, None)
    assert calls == []


def test_a_basename_is_never_repaired_or_truncated():
    graph = graph_with_source("a\x00b.mp4")
    with pytest.raises(DiagnosticsUnsafeValueError):
        build_preview_diagnostics(graph, path_policy=PathPolicy.BASENAME)


def test_no_filesystem_access_is_made_to_compute_a_basename(monkeypatch):
    for name in ("stat", "lstat", "listdir", "scandir", "readlink", "realpath", "open"):
        monkeypatch.setattr(os, name, lambda *a, **k: (_ for _ in ()).throw(AssertionError("fs access")),
                            raising=False)
    monkeypatch.setattr(os.path, "exists", lambda *a, **k: (_ for _ in ()).throw(AssertionError("fs access")))
    monkeypatch.setattr(os.path, "realpath", lambda *a, **k: (_ for _ in ()).throw(AssertionError("fs access")))
    build_preview_diagnostics(h.preview_graph(), path_policy=PathPolicy.BASENAME)
