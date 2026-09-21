"""Architecture guards for the batch package (contract §1): dependency direction, no side effects, no Amane."""

from __future__ import annotations

import ast
import os
import subprocess
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[3] / "src"
CORE = SRC / "fc2_metadata_core"
BATCH = CORE / "batch"

EXPECTED_FILES = {"__init__.py", "config.py", "models.py", "retry.py", "scheduler.py"}

# Everything the batch layer must NOT reach: concrete adapters, the execution/engine internals, the transport,
# Amane, and anything that could persist or touch the outside world.
FORBIDDEN_PREFIXES = (
    "amane",
    "httpx",
    "fc2_metadata_core.sources.adapters",
    "fc2_metadata_core.aggregation.execution",
    "fc2_metadata_core.aggregation.engine",
    "fc2_metadata_core.aggregation.merge",
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
    "urllib",
    "requests",
)


def module_files(root: Path):
    return sorted(p for p in root.rglob("*.py"))


def imported_modules(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found += [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0, f"{path}: relative imports are not used in this codebase"
            found.append(node.module or "")
    return found


def test_the_batch_package_has_the_expected_modules():
    assert EXPECTED_FILES <= {p.name for p in BATCH.iterdir() if p.suffix == ".py"}


@pytest.mark.parametrize("path", module_files(BATCH), ids=lambda p: p.name)
def test_batch_modules_import_nothing_forbidden(path):
    for module in imported_modules(path):
        for prefix in FORBIDDEN_PREFIXES:
            assert not (module == prefix or module.startswith(prefix + ".")), f"{path.name} imports {module}"


@pytest.mark.parametrize("path", module_files(BATCH), ids=lambda p: p.name)
def test_batch_modules_only_depend_on_the_aggregation_public_package(path):
    for module in imported_modules(path):
        if module.startswith("fc2_metadata_core.aggregation"):
            assert module == "fc2_metadata_core.aggregation", f"{path.name}: use the public package, not {module}"


@pytest.mark.parametrize("path", module_files(BATCH), ids=lambda p: p.name)
def test_batch_modules_do_no_file_io(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    calls = {n.func.id for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert not (calls & {"open", "print", "input", "exec", "eval", "__import__"})


def test_no_other_package_imports_batch_so_there_is_no_cycle_and_aggregation_never_depends_on_it():
    offenders = []
    for path in module_files(CORE):
        if BATCH in path.parents:
            continue
        for module in imported_modules(path):
            if module == "fc2_metadata_core.batch" or module.startswith("fc2_metadata_core.batch."):
                offenders.append((path.relative_to(CORE).as_posix(), module))
    # (the top-level package facade uses `from fc2_metadata_core import ..., batch`, which is not a
    # `fc2_metadata_core.batch` import statement and is the only place batch is re-exported)
    assert offenders == [], offenders
    for path in module_files(CORE / "aggregation"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "fc2_metadata_core":
                assert "batch" not in [a.name for a in node.names], path.name


@pytest.mark.parametrize(
    "module",
    [
        "fc2_metadata_core.batch",
        "fc2_metadata_core.batch.models",
        "fc2_metadata_core.batch.config",
        "fc2_metadata_core.batch.retry",
        "fc2_metadata_core.batch.scheduler",
    ],
)
def test_each_batch_module_is_importable_first_in_a_fresh_interpreter(module):
    env = dict(os.environ, PYTHONPATH=str(SRC))
    done = subprocess.run(
        [sys.executable, "-c", f"import {module}"], env=env, capture_output=True, text=True, timeout=60
    )
    assert done.returncode == 0, done.stderr


def test_batch_source_never_names_a_concrete_adapter_or_creates_a_transport():
    for path in module_files(BATCH):
        text = path.read_text(encoding="utf-8")
        for token in ("Av123Adapter", "JavdbAdapter", "Fc2dbNetAdapter", "HttpxTransport", "SourceRegistry(", "build_default_registry"):
            assert token not in text, f"{path.name} mentions {token}"
