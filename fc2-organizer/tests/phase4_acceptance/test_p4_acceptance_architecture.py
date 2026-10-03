"""P4-C10 test-layer architecture guard (construction plan section 3, S1 item 7; contract sections 9 PC-01, 11.3, 12.4,
12.7, 3.4.2).

AST checks over every module of ``tests/phase4_acceptance``: which packages may be imported (public APIs of the packages
under acceptance, the authorized seams, ``tests/support``, the standard library, ``httpx`` and ``pytest``), where the
seams / ``socket`` / ``httpx`` / mutation surfaces may appear, no 3.12+ names, no drive-letter roots, no home-directory
access, no function-local ``fc2_*`` import. Positive / negative controls run the same checks over planted sources, so the
guard is shown to catch what it claims to catch.
"""

from __future__ import annotations

import ast
import pathlib
import re
import sys

import pytest

HERE = pathlib.Path(__file__).resolve().parent
MODULES = sorted(path for path in HERE.glob("*.py"))
ALLOWED_FILES = {
    "__init__.py", "_harness.py", "_corpus.py", "_oracles.py", "test_p4_acceptance_harness.py",
    "test_p4_acceptance_architecture.py", "test_p4_acceptance_chain.py", "test_p4_acceptance_real_adapters.py",
    "test_p4_acceptance_safety.py", "test_p4_acceptance_retry.py", "test_p4_acceptance_diagnostics.py",
    "test_p4_acceptance_determinism.py", "test_p4_acceptance_global_gate.py", "test_p4_acceptance_mutations.py",
}

PUBLIC_PACKAGES = {"discovery", "planning", "publication", "nfo", "images", "materialization", "execution",
                   "orchestration", "diagnostics"}
# authorized seams (contract 12.6) and mutation surfaces (contract 11.3): module -> files that may import it
SEAM_FILES = {
    "fc2_organizer.execution._fs": {"_harness.py", "test_p4_acceptance_harness.py", "test_p4_acceptance_mutations.py"},
    "fc2_organizer.materialization.atomic": {"_harness.py", "test_p4_acceptance_harness.py",
                                              "test_p4_acceptance_mutations.py"},
    "fc2_organizer.orchestration.execute": {"_harness.py", "test_p4_acceptance_harness.py",
                                             "test_p4_acceptance_mutations.py"},
    "fc2_organizer.orchestration.preview": {"test_p4_acceptance_harness.py", "test_p4_acceptance_mutations.py"},
    "fc2_organizer.orchestration.stages": {"test_p4_acceptance_harness.py", "test_p4_acceptance_mutations.py"},
    "fc2_organizer.orchestration.retry": {"test_p4_acceptance_harness.py", "test_p4_acceptance_mutations.py"},
    "fc2_organizer.orchestration.recognition": {"test_p4_acceptance_harness.py", "test_p4_acceptance_mutations.py"},
    "fc2_organizer.images.transport": {"_harness.py", "test_p4_acceptance_harness.py"},
}
FORBIDDEN_NETWORK = {"requests", "urllib3", "aiohttp", "http.client", "http.server", "http.cookiejar", "urllib.request",
                     "ftplib", "smtplib", "telnetlib", "ssl", "xmlrpc", "socketserver", "asyncio.streams"}
MONKEYPATCH_FILES = {"test_p4_acceptance_harness.py", "test_p4_acceptance_mutations.py"}
HTTPX_FILES = {"_harness.py", "test_p4_acceptance_harness.py"}
SOCKET_FILES = {"_harness.py"}
BANNED_ATTRIBUTES = {"isjunction", "batched", "override", "is_junction", "expanduser"}
DRIVE_ROOT = re.compile(r"(?<![A-Za-z0-9_])[A-Za-z]:[\\/]")
STDLIB = set(sys.stdlib_module_names)
THIRD_PARTY = {"httpx", "pytest"}
PROJECT = {"fc2_organizer", "fc2_metadata_core", "support"}


def _imports(tree: ast.AST):
    """(module, names, is_relative, is_nested) for every import statement."""
    found = []

    def visit(node, nested):
        for child in ast.iter_child_nodes(node):
            inner = nested or isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
            if isinstance(child, ast.Import):
                for alias in child.names:
                    found.append((alias.name, (), False, inner))
            elif isinstance(child, ast.ImportFrom):
                found.append((child.module or "", tuple(a.name for a in child.names), child.level > 0, inner))
            visit(child, inner)

    visit(tree, False)
    return found


def check_source(name: str, source: str) -> list[str]:
    """All architecture violations of one module, as messages."""
    problems = []
    tree = ast.parse(source)
    for module, names, relative, nested in _imports(tree):
        top = module.split(".")[0]
        if relative:
            continue
        if nested and (top in PROJECT):
            problems.append(f"{name}: function-local import of {module} (contract 12.7)")
        if top in {"tests", "unit"} or module.startswith("tests."):
            problems.append(f"{name}: imports {module} (tests/unit is not an oracle source)")
        elif top in PROJECT:
            parts = module.split(".")
            if top == "fc2_organizer":
                if len(parts) > 1 and parts[1] not in PUBLIC_PACKAGES:
                    problems.append(f"{name}: imports unknown fc2_organizer module {module}")
                if len(parts) > 2 and module not in SEAM_FILES:
                    problems.append(f"{name}: imports internal module {module} (only public package APIs and "
                                    f"authorized seams are allowed)")
                for dotted in [module] + [f"{module}.{n}" for n in names]:
                    if dotted in SEAM_FILES and name not in SEAM_FILES[dotted]:
                        problems.append(f"{name}: imports seam {dotted}, not allowed in this file")
                for imported in names:
                    if imported.startswith("_") and f"{module}.{imported}" not in SEAM_FILES:
                        problems.append(f"{name}: imports private name {module}.{imported}")
            elif top == "fc2_metadata_core" and any(part.startswith("_") for part in parts[1:]):
                problems.append(f"{name}: imports private module {module}")
        elif top in THIRD_PARTY:
            if top == "httpx" and name not in HTTPX_FILES:
                problems.append(f"{name}: httpx is only for MockTransport in the harness")
        elif top in STDLIB:
            if top == "socket" and name not in SOCKET_FILES:
                problems.append(f"{name}: socket may only appear in the harness trap")
            for dotted in [module] + [f"{module}.{n}" for n in names]:
                if any(dotted == banned or dotted.startswith(banned + ".") for banned in FORBIDDEN_NETWORK):
                    problems.append(f"{name}: network library {dotted}")
        else:
            problems.append(f"{name}: import of {module} is not on the allowed list")
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            if node.attr in BANNED_ATTRIBUTES:
                problems.append(f"{name}: banned attribute .{node.attr} (3.12+ name or home access)")
            if node.attr == "walk" and not (isinstance(node.value, ast.Name) and node.value.id in {"os", "ast"}):
                problems.append(f"{name}: .walk is only allowed as os.walk (Path.walk is 3.12+)")
            if node.attr == "home" and isinstance(node.value, ast.Name) and node.value.id == "Path":
                problems.append(f"{name}: Path.home() is forbidden")
            if node.attr in {"MonkeyPatch"} and name not in MONKEYPATCH_FILES:
                problems.append(f"{name}: monkeypatching is a mutation surface (contract 11.3)")
        if ((isinstance(node, ast.Name) and node.id == "monkeypatch")
                or (isinstance(node, ast.arg) and node.arg == "monkeypatch")) and name not in MONKEYPATCH_FILES:
            problems.append(f"{name}: the monkeypatch fixture is a mutation surface (contract 11.3)")
        if type(node).__name__ == "TypeAlias" or getattr(node, "type_params", None):
            problems.append(f"{name}: PEP 695 syntax (3.12+)")
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and DRIVE_ROOT.search(node.value) \
                and name != "test_p4_acceptance_architecture.py":
            problems.append(f"{name}: drive-letter literal {node.value[:20]!r}")
    return problems


@pytest.mark.parametrize("path", MODULES, ids=lambda p: p.name)
def test_every_module_satisfies_the_architecture_rules(path):
    assert check_source(path.name, path.read_text(encoding="utf-8")) == []


def test_only_the_planned_files_exist():
    assert {path.name for path in HERE.iterdir() if path.is_file()} <= ALLOWED_FILES | {"__pycache__"}


def test_no_c10_module_reads_the_environment_or_the_home_directory():
    for path in MODULES:
        if path.name == "test_p4_acceptance_architecture.py":
            continue  # this module names the forbidden patterns as data; the AST rules above cover it
        text = path.read_text(encoding="utf-8")
        for pattern in ("os.environ", "getpass", "Path.home", "expanduser", "os.getenv"):
            assert pattern not in text, f"{path.name} uses {pattern}"


# ---- controls: the guard fails on planted violations and passes on clean code


@pytest.mark.parametrize("name, source, fragment", [
    ("test_x.py", "from unit.orchestration import _helpers\n", "tests/unit"),
    ("test_x.py", "from tests.unit.nfo import _builders\n", "tests/unit"),
    ("test_x.py", "import requests\n", "not on the allowed list"),
    ("test_x.py", "import urllib.request\n", "network library"),
    ("test_x.py", "import http.client\n", "network library"),
    ("test_x.py", "import socket\n", "socket may only appear"),
    ("test_x.py", "import httpx\n", "httpx is only for MockTransport"),
    ("test_x.py", "from fc2_organizer.execution import _fs\n", "seam"),
    ("test_x.py", "from fc2_organizer.orchestration import preview\n", "seam"),
    ("test_x.py", "from fc2_organizer.execution.transfer import x\n", "internal module"),
    ("test_x.py", "from fc2_organizer.amane import x\n", "unknown fc2_organizer module"),
    ("test_x.py", "def f():\n    from fc2_organizer.nfo import render_movie_nfo\n", "function-local"),
    ("test_x.py", "import os\nos.path.isjunction('x')\n", "banned attribute"),
    ("test_x.py", "import itertools\nitertools.batched([], 2)\n", "banned attribute"),
    ("test_x.py", "import pathlib\nfor _ in pathlib.Path('.').walk(): pass\n", "Path.walk"),
    ("test_x.py", "from pathlib import Path\nPath.home()\n", "Path.home"),
    ("test_x.py", "import os\nos.path.expanduser('~')\n", "banned attribute"),
    ("test_x.py", "X = 'C:\\\\Users\\\\someone'\n", "drive-letter"),
    ("test_x.py", "def test(monkeypatch):\n    pass\n", "monkeypatch fixture"),
    ("test_x.py", "import pytest\npytest.MonkeyPatch.context()\n", "monkeypatching"),
])
def test_the_guard_catches_planted_violations(name, source, fragment):
    problems = check_source(name, source)
    assert problems, f"nothing flagged for {source!r}"
    assert any(re.search(fragment, problem) for problem in problems), problems


@pytest.mark.parametrize("name, source", [
    ("test_x.py", "import os\nimport pytest\nfrom fc2_organizer.orchestration import BatchOrchestrator\n"
                  "from fc2_metadata_core.aggregation import MultiSourceEngine\nfrom support.fake_http_client import FakeHttpClient\n"
                  "from . import _corpus\nfor _ in os.walk('.'): pass\n"),
    ("_harness.py", "import httpx\nimport socket\nfrom fc2_organizer.execution import _fs\n"
                    "from fc2_organizer.materialization import atomic\n"),
    ("test_p4_acceptance_mutations.py", "import pytest\nfrom fc2_organizer.orchestration import preview, stages\n"
                                        "def test_m(monkeypatch):\n    pass\n"),
])
def test_the_guard_accepts_clean_sources(name, source):
    assert check_source(name, source) == []
