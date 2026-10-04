"""P5-C1 §25.1（E22）：主 pytest 进程隔离——任何 import amane 的测试都在子进程里；主进程从不 import amane，
也不操作 ``sys.modules``，因此不会使已 CLOSED 的架构守卫变得依赖顺序（P5-ENTRY-CLOSURE-OBS-01 不被加重）。
三种收集顺序的完整套件证据见 HANDOFF（E22）。"""

from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_the_main_process_never_imported_amane():
    assert "amane" not in sys.modules
    assert not [name for name in sys.modules if name.split(".")[0] == "amane" or name.startswith("amane_ext_")]


def test_host_scripts_were_never_imported_by_pytest():
    assert not [name for name in sys.modules if name in {"h_common", "h_scenarios"}]
    assert not [name for name in sys.modules if name.startswith("witness_tool_")]


def _run(script: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-c", textwrap.dedent(script), *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=str(ROOT), timeout=600,
    )


def test_collecting_the_adapter_and_contract_test_trees_never_imports_amane():
    """收集（不只是运行）本身也不得 import amane。范围刻意限定为 adapter 与 contract 两棵树：它们在 3.12 / 3.14 上都能收集；
    整个 ``tests`` 在 3.14 / Windows 上有一个与 P5-C1 无关的收集期失败（合同 L-07 / 集合 D），完整收集由 3.12 的全量套件覆盖。"""
    completed = _run(
        """
        import sys, pytest
        code = pytest.main(["--collect-only", "-q", "-p", "no:cacheprovider", "tests/amane_adapter", "tests/contract"])
        leaked = sorted(name for name in sys.modules if name.split(".")[0] == "amane")
        print("RESULT", code, leaked)
        """
    )
    assert "RESULT 0 []" in completed.stdout, completed.stdout[-600:] + completed.stderr[-600:]


def test_pure_adapter_tests_pass_even_when_amane_cannot_be_imported_at_all():
    """子进程里用 meta_path 把 ``amane`` 整体屏蔽；纯逻辑测试仍全部通过（没有隐含的 amane 依赖）。"""
    completed = _run(
        """
        import importlib.abc, sys, pytest
        class Block(importlib.abc.MetaPathFinder):
            def find_spec(self, name, path=None, target=None):
                if name == "amane" or name.startswith("amane."):
                    raise ImportError("amane is blocked in this process: " + name)
        sys.meta_path.insert(0, Block())
        code = pytest.main(["-q", "-p", "no:cacheprovider", "--no-header", "--color=no",
                            "tests/amane_adapter/test_amane_settings.py",
                            "tests/amane_adapter/test_amane_number_boundary.py",
                            "tests/amane_adapter/test_amane_bridge_response.py",
                            "tests/amane_adapter/test_amane_bridge_errors.py",
                            "tests/amane_adapter/test_amane_outcome_status.py",
                            "tests/amane_adapter/test_amane_error_mapping.py",
                            "tests/amane_adapter/test_amane_narrowing.py",
                            "tests/amane_adapter/test_amane_retry_bounds.py"])
        print("RESULT", code)
        """
    )
    assert "RESULT 0" in completed.stdout, completed.stdout[-1500:] + completed.stderr[-600:]


def test_existing_architecture_guards_still_pass_after_adapter_modules_were_imported_in_a_fresh_process():
    """既有的 Core 独立性守卫在“adapter 纯模块已被导入”的进程里仍然通过（顺序无关）。"""
    completed = _run(
        """
        import sys, pytest
        sys.path[:0] = ["src", "adapters/amane"]
        import fc2_amane_adapter._runtime, fc2_amane_adapter._bridge  # 先导入 adapter（它们 import Core）
        code = pytest.main(["-q", "-p", "no:cacheprovider", "--no-header", "--color=no",
                            "tests/contract/test_core_independent_of_amane.py"])
        print("RESULT", code)
        """
    )
    assert "RESULT 0" in completed.stdout, completed.stdout[-1500:] + completed.stderr[-600:]
