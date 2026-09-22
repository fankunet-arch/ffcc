"""Architecture / AST guards for ``resource_control`` (contract §1, §9, §10, §12)."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[3] / "src"
CORE = SRC / "fc2_metadata_core"
RC = CORE / "resource_control"
EXECUTION = CORE / "aggregation" / "execution.py"

EXPECTED_FILES = {"__init__.py", "errors.py", "host_key.py", "config.py", "host_limiter.py", "circuit_breaker.py", "governor.py"}
DECISION_MODULES = ["host_limiter.py", "circuit_breaker.py", "governor.py"]  # limiter / breaker / governor decisions

FORBIDDEN_IMPORT_PREFIXES = (
    "amane",
    "httpx",
    "requests",
    "urllib3",
    "urllib.request",
    "fc2_metadata_core.batch",
    "fc2_metadata_core.aggregation",
    "fc2_metadata_core.sources",
    "fc2_metadata_core.http",
    "os",
    "pathlib",
    "shutil",
    "sqlite3",
    "json",
    "pickle",
    "shelve",
    "socket",
    "subprocess",
    "tempfile",
    "datetime",
    "random",
    "threading",
    "logging",
)

# Anything a trace / diagnostic / text could offer that a resource decision must never read.
FORBIDDEN_NAMES = {
    "source_execution_traces",
    "SourceExecutionTrace",
    "SourceAttempt",
    "attempts",
    "attempt_count",
    "deadline_during",
    "deadline_exceeded",
    "retried",
    "error_detail",
    "metadata",
    "elapsed_ms",
    "BatchLineage",
    "AggregationResult",
}
STRING_SNIFFING = {
    "startswith", "endswith", "find", "rfind", "index", "count", "lower", "upper", "casefold", "strip", "lstrip",
    "rstrip", "split", "rsplit", "partition", "rpartition", "replace", "format", "translate", "encode", "decode",
}
PROVIDERS = ("fc2db", "javdb", "av123", "javbus", "123av", "fc2_official", "sukebei")


def files(names=None):
    return sorted(p for p in RC.glob("*.py") if names is None or p.name in names)


def tree_of(path: Path) -> ast.AST:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def imported(path: Path) -> list[str]:
    found = []
    for node in ast.walk(tree_of(path)):
        if isinstance(node, ast.Import):
            found += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0, f"{path.name}: relative import"
            found.append(node.module or "")
    return found


def test_the_package_has_exactly_the_documented_modules():
    assert {p.name for p in RC.glob("*.py")} == EXPECTED_FILES


@pytest.mark.parametrize("path", files(), ids=lambda p: p.name)
def test_resource_control_imports_nothing_forbidden(path):
    for module in imported(path):
        for prefix in FORBIDDEN_IMPORT_PREFIXES:
            assert not (module == prefix or module.startswith(prefix + ".")), f"{path.name} imports {module}"


@pytest.mark.parametrize("path", files(), ids=lambda p: p.name)
def test_resource_control_depends_only_on_the_source_result_contract_errors_and_itself(path):
    for module in imported(path):
        if module.startswith("fc2_metadata_core"):
            allowed = (
                module.startswith("fc2_metadata_core.resource_control")
                or module == "fc2_metadata_core.errors"
                or module == "fc2_metadata_core.models.source_result"
            )
            assert allowed, f"{path.name} imports {module}"


@pytest.mark.parametrize("path", files(), ids=lambda p: p.name)
def test_no_file_network_process_or_wall_clock_io(path):
    tree = tree_of(path)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert node.func.id not in {"open", "print", "input", "eval", "exec", "__import__"}, (path.name, node.func.id)
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "time":
            assert node.attr == "monotonic", f"{path.name}: only time.monotonic may be used, got time.{node.attr}"
        if isinstance(node, ast.Attribute) and node.attr in {"sleep", "now", "utcnow", "today", "time_ns"}:
            raise AssertionError(f"{path.name}: {node.attr!r} (wall clock / sleep) is not allowed in resource control")


@pytest.mark.parametrize("path", files(), ids=lambda p: p.name)
def test_no_provider_specific_logic(path):
    text = path.read_text(encoding="utf-8").lower()
    for provider in PROVIDERS:
        assert provider not in text, f"{path.name} mentions {provider!r}"


# ---- no trace / text dependency (C2-L2 non-dependency) --------------------------------------------------------------------------


@pytest.mark.parametrize("path", files(), ids=lambda p: p.name)
def test_resource_control_never_reads_traces_diagnostics_or_metadata(path):
    for node in ast.walk(tree_of(path)):
        if isinstance(node, ast.Attribute):
            assert node.attr not in FORBIDDEN_NAMES, f"{path.name}:{node.lineno} reads .{node.attr}"
        elif isinstance(node, ast.Name):
            assert node.id not in FORBIDDEN_NAMES, f"{path.name}:{node.lineno} uses {node.id}"
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            assert node.name not in FORBIDDEN_NAMES, (path.name, node.name)
        elif isinstance(node, ast.arg):
            assert node.arg not in FORBIDDEN_NAMES, (path.name, node.arg)
        elif isinstance(node, (ast.ImportFrom, ast.Import)):
            names = [a.name for a in node.names]
            assert not set(names) & FORBIDDEN_NAMES, (path.name, names)


def test_the_breaker_reads_only_status_error_kind_and_source_id_of_a_result():
    """The only attributes ever read off a result-like object in the decision modules."""
    allowed_result_attrs = {"status", "error_kind", "source_id"}
    seen = set()
    for path in files({"circuit_breaker.py", "governor.py"}):
        for node in ast.walk(tree_of(path)):
            if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "result":
                seen.add(node.attr)
    assert seen and seen <= allowed_result_attrs, seen


@pytest.mark.parametrize("path", files(set(DECISION_MODULES)), ids=lambda p: p.name)
def test_decision_modules_never_sniff_or_format_text(path):
    tree = tree_of(path)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute):
                assert func.attr not in STRING_SNIFFING, f"{path.name}:{node.lineno} .{func.attr}()"
            if isinstance(func, ast.Name):
                assert func.id not in {"str", "repr", "ascii", "format", "getattr", "hasattr", "vars", "dir", "type"}, (
                    f"{path.name}:{node.lineno} {func.id}()"
                )
        if isinstance(node, ast.Compare):
            for operand in [node.left, *node.comparators]:
                assert not (isinstance(operand, ast.Constant) and isinstance(operand.value, str)), (
                    f"{path.name}:{node.lineno}: comparison against a string literal"
                )
        assert not isinstance(node, ast.Import) or all(a.name != "re" for a in node.names), path.name


def test_the_breaker_decides_from_enums_never_from_strings():
    tree = tree_of(RC / "circuit_breaker.py")
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr in {"value", "name"}:
            raise AssertionError(f"circuit_breaker.py:{node.lineno} reads enum .{node.attr}: decide by member identity")


# ---- no global singleton -------------------------------------------------------------------------------------------------------------


MUTABLE_CALLS = {"dict", "list", "set", "deque", "Counter", "defaultdict", "OrderedDict", "bytearray"}


@pytest.mark.parametrize("path", files(), ids=lambda p: p.name)
def test_no_module_level_mutable_state_and_no_global_statement(path):
    tree = tree_of(path)
    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if [t.id for t in targets if isinstance(t, ast.Name)] == ["__all__"]:
                continue  # the export list is never mutated
            value = node.value
            assert not isinstance(value, (ast.Dict, ast.List, ast.Set, ast.ListComp, ast.DictComp, ast.SetComp)), (
                f"{path.name}:{node.lineno}: module-level mutable literal"
            )
            if isinstance(value, ast.Call):
                name = value.func.id if isinstance(value.func, ast.Name) else getattr(value.func, "attr", "")
                assert name not in MUTABLE_CALLS, f"{path.name}:{node.lineno}: module-level {name}()"
    for node in ast.walk(tree):
        assert not isinstance(node, (ast.Global, ast.Nonlocal)), f"{path.name}:{node.lineno}: global/nonlocal"


def test_the_only_module_level_object_instances_are_the_issue_key_and_frozen_defaults():
    instances = []
    for path in files():
        for node in tree_of(path).body:
            if isinstance(node, (ast.Assign, ast.AnnAssign)) and isinstance(node.value, ast.Call):
                func = node.value.func
                name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", "")
                instances.append((path.name, name))
    assert sorted(instances) == [
        ("circuit_breaker.py", "MappingProxyType"),  # the exhaustive status -> observation table (read-only)
        ("governor.py", "object"),  # the private ticket-issue key
        ("host_key.py", "MappingProxyType"),  # default ports (read-only)
        ("host_key.py", "compile"),  # a compiled regex
    ]


# ---- C5 integration points in execution.py ----------------------------------------------------------------------------------------------


def _function(tree, name):
    return next(n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name)


def test_the_fatal_carrier_is_metadata_free():
    tree = tree_of(EXECUTION)
    carrier = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "_FatalSignal")
    assert any(
        isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "__slots__" for t in n.targets) for n in carrier.body
    )
    forbidden = {"__name__", "__qualname__", "__class__", "type", "str", "repr", "args", "format", "getattr", "__str__"}
    used = {n.id for n in ast.walk(carrier) if isinstance(n, ast.Name)} | {n.attr for n in ast.walk(carrier) if isinstance(n, ast.Attribute)}
    assert not used & forbidden, used & forbidden
    init = _function(carrier, "__init__")
    assert [a.arg for a in init.args.args] == ["self", "original"]


def test_nothing_awaits_between_the_final_result_and_the_breaker_update():
    """`trace = await _run_source(...)` is immediately followed by the synchronous `record_result`: a cancellation can
    never land between "the fetch finished" and "the breaker was told"."""
    execute_one = _function(tree_of(EXECUTION), "_execute_one")
    body_holder = next(n for n in ast.walk(execute_one) if isinstance(n, ast.Try))
    statements = body_holder.body
    index = next(
        i
        for i, s in enumerate(statements)
        if isinstance(s, ast.Assign) and isinstance(s.value, ast.Await) and "_run_source" in ast.dump(s.value)
    )
    following = statements[index + 1]
    assert isinstance(following, ast.Expr) and isinstance(following.value, ast.Call)
    assert isinstance(following.value.func, ast.Attribute) and following.value.func.attr == "record_result"
    assert not any(isinstance(n, ast.Await) for n in ast.walk(following))
    # ... and the release is in a `finally`, so cancellation / fatal exceptions always free the ticket
    assert any(
        isinstance(s, ast.Expr) and isinstance(s.value, ast.Call) and getattr(s.value.func, "attr", "") == "release"
        or isinstance(s, ast.If) and "release" in ast.dump(s)
        for s in body_holder.finalbody
    )


def test_the_execution_boundary_hands_the_governor_only_the_final_result():
    execute_one = _function(tree_of(EXECUTION), "_execute_one")
    trace_reads = {n.attr for n in ast.walk(execute_one) if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and n.value.id == "trace"}
    assert trace_reads == {"final_result"}, trace_reads


def test_the_governor_is_never_reached_through_module_state_in_aggregation():
    for path in (CORE / "aggregation").glob("*.py"):
        for node in tree_of(path).body:
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                assert "governor" not in ast.dump(node).lower() or path.name in {"execution.py", "engine.py"}, (path.name, node.lineno)
    engine = tree_of(CORE / "aggregation" / "engine.py")
    assert not [n for n in engine.body if isinstance(n, ast.Assign) and "Governor(" in ast.dump(n)], "no default global governor"


def test_circuit_open_is_not_in_the_retry_eligible_set_and_retry_py_never_names_it():
    text = (CORE / "aggregation" / "retry.py").read_text(encoding="utf-8")
    tree = ast.parse(text)
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            assert node.attr != "CIRCUIT_OPEN", "retry.py must not treat CIRCUIT_OPEN specially (it is simply not eligible)"
    from fc2_metadata_core.aggregation.retry import RETRY_ELIGIBLE_KINDS
    from fc2_metadata_core.models.source_result import SourceErrorKind

    assert SourceErrorKind.CIRCUIT_OPEN not in RETRY_ELIGIBLE_KINDS


def test_batch_and_the_scheduler_do_not_know_about_resource_control():
    for path in (CORE / "batch").glob("*.py"):
        assert "resource_control" not in path.read_text(encoding="utf-8"), path.name
    for path in (CORE / "resource_control").glob("*.py"):
        assert "BatchLineage" not in path.read_text(encoding="utf-8"), f"{path.name}: BatchLineage must not be reused"
