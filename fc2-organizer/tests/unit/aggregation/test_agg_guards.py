"""Structural guards for the aggregation package + AggregationResult invariants."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from fc2_metadata_core.aggregation import (
    AggregateStatus,
    AggregationContractError,
    AggregationResult,
    FieldConflict,
)
from fc2_metadata_core.models.metadata import NormalizedMetadata
from fc2_metadata_core.models.source_result import SourceStatus

from support.scripted_adapters import failed, ok

PACKAGE = Path(__file__).resolve().parents[3] / "src" / "fc2_metadata_core" / "aggregation"
PROVIDER_IDS = ("fc2db_net", "javdb", "av123", "fc2db", "123av")
N = "FC2-4979299"


def _source(name):
    return (PACKAGE / name).read_text(encoding="utf-8")


@pytest.mark.parametrize("module", ["merge.py", "policy.py", "execution.py", "engine.py", "models.py", "config.py", "retry.py"])
def test_core_aggregation_modules_never_name_a_provider(module):
    text = _source(module)
    for provider in PROVIDER_IDS:
        assert provider not in text, f"{module} mentions provider {provider!r}: provider-specific logic belongs in configuration"


def test_only_the_defaults_module_names_providers_and_only_as_data():
    text = _source("defaults.py")
    assert "fc2db_net" in text and "DEFAULT_SOURCE_ORDER" in text
    tree = ast.parse(text)
    assert not [n for n in ast.walk(tree) if isinstance(n, (ast.If, ast.Match))], "defaults.py must be data, not branching"


def test_aggregation_never_imports_a_concrete_adapter_or_amane():
    for path in PACKAGE.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            for name in names:
                assert not name.startswith("amane"), (path.name, name)
                assert not name.startswith("fc2_metadata_core.sources.adapters"), (path.name, name)


def test_no_object_setattr_and_no_mutation_of_metadata_in_the_aggregation_package():
    for path in PACKAGE.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "object.__setattr__" not in text, path.name
        assert "__dict__" not in text, path.name


def _identifiers(tree):
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, ast.arg):
            names.add(node.arg)
        elif isinstance(node, ast.keyword) and node.arg:
            names.add(node.arg)
    return names


def test_no_circuit_breaker_in_c2():
    # Identifiers only (docstrings may say what is deliberately NOT implemented yet).
    for path in PACKAGE.glob("*.py"):
        for name in _identifiers(ast.parse(path.read_text(encoding="utf-8"))):
            lowered = name.lower()
            for forbidden in ("circuit", "breaker"):
                assert forbidden not in lowered, (path.name, name)


@pytest.mark.parametrize("module", ["retry.py", "execution.py", "merge.py", "engine.py"])
def test_retry_and_execution_decisions_never_read_error_detail(module):
    """P2-R-12: retryability comes from the structured error_kind, never from text.
    ``error_detail=`` as a *keyword when building a result* is fine; reading
    ``something.error_detail`` (an ast.Attribute) is not."""
    tree = ast.parse((PACKAGE / module).read_text(encoding="utf-8"))
    reads = [n.lineno for n in ast.walk(tree) if isinstance(n, ast.Attribute) and n.attr == "error_detail"]
    assert not reads, f"{module} reads .error_detail at line(s) {reads}"


def test_retry_and_execution_code_contains_no_text_matching_literals():
    """P2-R-12: no string literal (docstrings excluded) in the retry decision code could be
    used to sniff error text such as '500', 'timeout' or 'connection'."""
    banned = ("500", "5xx", "timeout", "time out", "connection", "server error", "reset", "refused", "dns", "http")
    for module in ("retry.py", "execution.py"):
        tree = ast.parse((PACKAGE / module).read_text(encoding="utf-8"))
        docstring_nodes = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and (
                node.body and isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Constant)
            ):
                docstring_nodes.add(id(node.body[0].value))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docstring_nodes:
                lowered = node.value.lower()
                # f-string fragments that build a human message are fine; membership tests are not:
                assert not any(b == lowered.strip() for b in banned), (module, node.lineno, node.value)


def test_no_string_membership_tests_on_results_in_retry_or_execution():
    """No ``"..." in something`` / ``something.startswith/find/lower`` on result text."""
    for module in ("retry.py", "execution.py"):
        tree = ast.parse((PACKAGE / module).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Compare) and any(isinstance(op, (ast.In, ast.NotIn)) for op in node.ops):
                if isinstance(node.left, ast.Constant) and isinstance(node.left.value, str):
                    raise AssertionError(f"{module}:{node.lineno} tests a string literal for membership")
            if isinstance(node, ast.Attribute) and node.attr in ("startswith", "endswith", "find", "lower", "casefold"):
                raise AssertionError(f"{module}:{node.lineno} calls a string-sniffing method .{node.attr}")


def test_retry_module_does_not_import_the_http_library_or_adapters():
    tree = ast.parse((PACKAGE / "retry.py").read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        names = [a.name for a in node.names] if isinstance(node, ast.Import) else (
            [node.module] if isinstance(node, ast.ImportFrom) and node.module else []
        )
        for name in names:
            assert not name.startswith(("httpx", "fc2_metadata_core.sources.adapters", "fc2_metadata_core.http")), name


# ---- AggregationResult invariants ----------------------------------------------------------------------


def _md(title="T"):
    return NormalizedMetadata(number=N, title=title)


def test_success_requires_minimum_success_metadata_a_contributor_and_no_operational_failure():
    good = ok("a", N)
    AggregationResult(N, AggregateStatus.SUCCESS, _md(), (good, failed("b", SourceStatus.NOT_FOUND)), ("a",))
    with pytest.raises(AggregationContractError):
        AggregationResult(N, AggregateStatus.SUCCESS, _md(), (good, failed("b", SourceStatus.NETWORK_ERROR)), ("a",))
    with pytest.raises(AggregationContractError):
        AggregationResult(N, AggregateStatus.SUCCESS, NormalizedMetadata(number=N), (good,), ("a",))
    with pytest.raises(AggregationContractError):
        AggregationResult(N, AggregateStatus.SUCCESS, _md(), (good,), ())
    with pytest.raises(AggregationContractError):
        AggregationResult(N, AggregateStatus.SUCCESS, NormalizedMetadata(number="FC2-1111111", title="x"), (good,), ("a",))


def test_partial_requires_an_operational_failure():
    good = ok("a", N)
    AggregationResult(N, AggregateStatus.PARTIAL, _md(), (good, failed("b", SourceStatus.BLOCKED)), ("a",))
    with pytest.raises(AggregationContractError):
        AggregationResult(N, AggregateStatus.PARTIAL, _md(), (good, failed("b", SourceStatus.NOT_FOUND)), ("a",))


def test_failed_carries_no_metadata_and_no_contributors():
    nf = failed("a", SourceStatus.NOT_FOUND)
    AggregationResult(N, AggregateStatus.FAILED, None, (nf,))
    with pytest.raises(AggregationContractError):
        AggregationResult(N, AggregateStatus.FAILED, _md(), (nf,))
    with pytest.raises(AggregationContractError):
        AggregationResult(N, AggregateStatus.FAILED, None, (ok("a", N),), ("a",))


@pytest.mark.parametrize(
    "kwargs",
    [
        {"number": "FC2-1234567\n"},
        {"number": "1234567"},
        {"status": "success"},
        {"source_results": ()},
        {"source_results": [ok("a", N)]},
        {"elapsed_ms": -1},
        {"contributing_source_ids": ("ghost",)},
    ],
)
def test_malformed_results_cannot_be_constructed(kwargs):
    base = dict(number=N, status=AggregateStatus.SUCCESS, metadata=_md(), source_results=(ok("a", N),), contributing_source_ids=("a",))
    base.update(kwargs)
    with pytest.raises(AggregationContractError):
        AggregationResult(**base)


def test_duplicate_source_ids_and_non_contributing_contributors_are_rejected():
    with pytest.raises(AggregationContractError):
        AggregationResult(N, AggregateStatus.FAILED, None, (failed("a", SourceStatus.NOT_FOUND), failed("a", SourceStatus.NOT_FOUND)))
    with pytest.raises(AggregationContractError):
        AggregationResult(N, AggregateStatus.SUCCESS, _md(), (failed("a", SourceStatus.NOT_FOUND), ok("b", N)), ("a",))


def test_field_conflict_rejects_a_non_conflict():
    FieldConflict("title", "a", "X", (("b", "Y"),))
    with pytest.raises(AggregationContractError):
        FieldConflict("title", "a", "X", (("b", "X"),))
    with pytest.raises(AggregationContractError):
        FieldConflict("title", "a", "X", ())
