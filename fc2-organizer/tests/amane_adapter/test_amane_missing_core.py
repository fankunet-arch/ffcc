"""P5-C1 §22（E16 纯逻辑部分）：缺失 Core 的失败翻译。真实 discover / install 见证见 H-05。"""

from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from fc2_amane_adapter._core_gate import MISSING_CORE_MESSAGE_TEMPLATE, translate_core_import_error

ADAPTERS_ROOT = Path(__file__).resolve().parents[2] / "adapters" / "amane"

EXPECTED = (
    "FC2 Metadata Core 未安装或版本不兼容：请在 Amane 所在的 Python 环境中安装 fc2-metadata-core（缺失模块：{name}）"
)


def test_template_is_the_frozen_text():
    assert MISSING_CORE_MESSAGE_TEMPLATE == EXPECTED


@pytest.mark.parametrize(
    "name", ["fc2_metadata_core", "fc2_metadata_core.aggregation", "fc2_metadata_core.sources.adapters", "fc2_metadata_core.http.client"]
)
def test_core_import_errors_become_the_fixed_message(name):
    translated = translate_core_import_error(ModuleNotFoundError(f"No module named {name!r}", name=name))
    assert type(translated) is ImportError
    assert str(translated) == EXPECTED.format(name=name)


def test_cannot_import_a_public_name_is_translated_too():
    exc = ImportError("cannot import name 'X' from 'fc2_metadata_core.aggregation'", name="fc2_metadata_core.aggregation")
    assert str(translate_core_import_error(exc)) == EXPECTED.format(name="fc2_metadata_core.aggregation")


@pytest.mark.parametrize(
    "exc",
    [
        ModuleNotFoundError("No module named 'amane'", name="amane"),
        ModuleNotFoundError("No module named 'fc2_amane_adapter._bridge'", name="fc2_amane_adapter._bridge"),
        ModuleNotFoundError("No module named 'fc2_metadata_core_other'", name="fc2_metadata_core_other"),
        ModuleNotFoundError("x", name="fc2_metadata_corex.y"),
        ImportError("no name"),
        ImportError("x", name=None),
        ImportError("x", name=""),
        ImportError("x", name="fc2_metadata_core." + "a" * 200),
        ImportError("x", name="fc2_metadata_core.bad\nname"),
        ImportError("x", name="fc2_metadata_core.bad name"),
        ImportError("x", name=123),
        ValueError("not an import error"),
    ],
)
def test_non_core_import_errors_are_not_misreported(exc):
    assert translate_core_import_error(exc) is None


def test_translated_message_is_bounded_and_secret_free():
    text = str(translate_core_import_error(ImportError("x", name="fc2_metadata_core.sub")))
    assert len(text) < 200 and "\n" not in text


def _run(script: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-c", textwrap.dedent(script)],
        capture_output=True,
        text=True,
        cwd=str(ADAPTERS_ROOT),
        timeout=60,
    )


BLOCKER = """
import sys, importlib.abc
class Block(importlib.abc.MetaPathFinder):
    def find_spec(self, name, path=None, target=None):
        if name == "fc2_metadata_core" or name.startswith("fc2_metadata_core."):
            raise ModuleNotFoundError("blocked " + name, name=name)
sys.meta_path.insert(0, Block())
sys.path.insert(0, ".")
"""


def test_core_gate_loads_without_core_and_translates_the_real_failure_of_a_pure_module():
    result = _run(
        BLOCKER
        + """
from fc2_amane_adapter._core_gate import translate_core_import_error
try:
    import fc2_amane_adapter._settings
except ImportError as exc:
    translated = translate_core_import_error(exc)
    print(type(translated).__name__, translated)
else:
    print("IMPORTED")
"""
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "ImportError " + EXPECTED.format(name="fc2_metadata_core")


def test_non_core_failure_inside_the_chain_is_returned_untranslated():
    result = _run(
        """
import sys
sys.path.insert(0, ".")
from fc2_amane_adapter._core_gate import translate_core_import_error
try:
    import some_missing_support_module_xyz
except ImportError as exc:
    print(translate_core_import_error(exc))
"""
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "None"


def test_core_gate_module_itself_never_imports_core():
    source = (ADAPTERS_ROOT / "fc2_amane_adapter" / "_core_gate.py").read_text(encoding="utf-8")
    import ast

    tree = ast.parse(source)
    imported = {alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names}
    imported |= {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module}
    assert imported == {"__future__"}
