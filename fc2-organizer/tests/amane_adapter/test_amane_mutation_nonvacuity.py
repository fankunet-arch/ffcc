"""P5-C1 E21 / 计划第 9 节：mutation / non-vacuity。M-01..M-17 每个至少被一个指定测试杀死。

方法：把插件树复制到临时目录，对副本施加**恰好一处**文本补丁，在子进程里以 ``-o pythonpath=<副本根> src tests``
把副本置于最前运行指定测试，并附带哨兵测试（``test_amane_architecture_guards.py::test_the_adapter_under_test_is_the_expected_tree``，
环境变量 ``P5_C1_MUTANT_ROOT``）证明被测的确是被篡改的副本。仓库内的原树从不被修改。

直接运行 ``python tests/amane_adapter/test_amane_mutation_nonvacuity.py`` 可打印每个 mutant 的失败用例与失败数（HANDOFF 使用）。
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TREE = ROOT / "adapters" / "amane" / "fc2_amane_adapter"
SENTINEL = "tests/amane_adapter/test_amane_architecture_guards.py::test_the_adapter_under_test_is_the_expected_tree"


@dataclass(frozen=True)
class Mutant:
    mutant_id: str
    description: str
    file: str
    old: str
    new: str
    killers: tuple[str, ...]


MUTANTS = (
    Mutant("M-01", "bridge does not pass ok_statuses", "_bridge.py", "                ok_statuses=OK_STATUSES,\n", "",
           ("test_amane_bridge_response", "test_amane_retry_bounds")),
    Mutant("M-02", "Core retry becomes max_attempts = 2", "_settings.py", "no_retry = RetryPolicy.no_retry()", "no_retry = RetryPolicy(max_attempts=2)",
           ("test_amane_retry_bounds", "test_amane_runtime_lifetime")),
    Mutant("M-03", "BLOCKED is no longer an operational failure (-> None / not_found)", "_outcome.py",
           "    SourceStatus.BLOCKED,\n    SourceStatus.RATE_LIMITED,\n", "    SourceStatus.RATE_LIMITED,\n",
           ("test_amane_error_mapping", "test_amane_outcome_status")),
    Mutant("M-04", "source_url takes the last valid URL", "_outcome.py", "    for url in source_urls:\n", "    for url in reversed(source_urls):\n",
           ("test_amane_narrowing",)),
    Mutant("M-05", "external_id takes a Core external_ids value", "_outcome.py", "        external_id=narrow_external_id(canonical),",
           "        external_id=next(iter(metadata.external_ids.values()), narrow_external_id(canonical)),", ("test_amane_narrowing",)),
    Mutant("M-06", "runtime swallows cancellation (except BaseException)", "_runtime.py", "        except Exception as exc:", "        except BaseException as exc:",
           ("test_amane_cancellation", "test_amane_architecture_guards")),
    Mutant("M-07", "failure detail appends SourceResult.error_detail", "_outcome.py",
           '    return DETAIL_PREFIX + "; ".join(f"{result.source_id}={_kind_value(result)}" for result in results)',
           '    return DETAIL_PREFIX + "; ".join(f"{result.source_id}={_kind_value(result)}:{result.error_detail}" for result in results)',
           ("test_amane_error_mapping", "test_amane_logging_redaction")),
    Mutant("M-08", "no normalisation: the raw query.number is used", "_number.py", "    return result.canonical\n", "    return number\n",
           ("test_amane_number_boundary",)),
    Mutant("M-09", "fanart_urls are merged into thumb_urls", "_outcome.py", "        thumb_urls=filter_urls(metadata.thumb_urls),",
           "        thumb_urls=filter_urls(metadata.thumb_urls + metadata.fanart_urls),", ("test_amane_metadata_mapping",)),
    Mutant("M-10", "a new engine is built for every fetch", "_runtime.py", "            result = await self._engine.aggregate(resolved)",
           "            result = await MultiSourceEngine(self._config, self._registry, self._bridge, governor=self._governor).aggregate(resolved)",
           ("test_amane_runtime_lifetime",)),
    Mutant("M-11", "bridge imports httpx", "_bridge.py", "import codecs\n", "import codecs\nimport httpx\n", ("test_amane_architecture_guards",)),
    Mutant("M-12", "PARTIAL becomes an error", "_outcome.py", "        degraded: tuple[tuple[str, str], ...] = ()\n",
           '        if result.status is AggregateStatus.PARTIAL:\n            return AdapterFailure("unexpected", "x")\n        degraded: tuple[tuple[str, str], ...] = ()\n',
           ("test_amane_outcome_status",)),
    Mutant("M-13", "all NOT_FOUND becomes an error", "_outcome.py", '        return AdapterNoMatch("all_not_found")', '        return AdapterFailure("unexpected", "x")',
           ("test_amane_outcome_status",)),
    Mutant("M-14", "precedence takes the lowest priority", "_outcome.py", "    for candidate in FAILURE_REASONS:\n", "    for candidate in reversed(FAILURE_REASONS):\n",
           ("test_amane_error_mapping", "test_amane_determinism")),
    Mutant("M-15", "one kind -> reason entry is deleted", "_outcome.py", '    SourceErrorKind.RESULT_CONTRACT_MISMATCH: "unexpected",\n', "",
           ("test_amane_error_mapping",)),
    Mutant("M-16", "plugin.py imports a non-public Amane module", "plugin.py", "from pydantic import BaseModel,",
           "from amane.db import Repository  # noqa: F401\nfrom pydantic import BaseModel,", ("test_amane_api_manifest", "test_amane_architecture_guards")),
    Mutant("M-17", "a pure module writes a file", "_settings.py", 'PLUGIN_ID = "ffcc.fc2-metadata"\n',
           'PLUGIN_ID = "ffcc.fc2-metadata"\n\n\ndef _mutant_write():\n    open("p5c1_mutant.txt", "w").write("x")\n\n',
           ("test_amane_architecture_guards", "test_amane_no_side_effects")),
)

FAILED_LINE = re.compile(r"^FAILED (tests/amane_adapter/[^\s:]+)::(\S+)", re.MULTILINE)
SUMMARY = re.compile(r"(\d+) failed")


@dataclass
class MutantResult:
    mutant_id: str
    failed_tests: list[str]
    failed_count: int
    killed_by_designated: bool
    sentinel_ok: bool
    applied_once: bool


def run_mutant(mutant: Mutant) -> MutantResult:
    with tempfile.TemporaryDirectory(prefix=f"p5c1_{mutant.mutant_id}_") as work:
        copy = Path(work) / "fc2_amane_adapter"
        shutil.copytree(TREE, copy, ignore=shutil.ignore_patterns("__pycache__"))
        target = copy / mutant.file
        text = target.read_text(encoding="utf-8").replace("\r\n", "\n")
        applied_once = text.count(mutant.old) == 1
        if applied_once:
            target.write_text(text.replace(mutant.old, mutant.new, 1), encoding="utf-8", newline="\n")
        files = [f"tests/amane_adapter/{name}.py" for name in mutant.killers]
        env = {**os.environ, "P5_C1_MUTANT_ROOT": str(Path(work))}
        completed = subprocess.run(
            [sys.executable, "-m", "pytest", *files, SENTINEL, "-q", "-p", "no:cacheprovider", "--no-header", "--color=no", "-rf",
             "-o", f"pythonpath={Path(work).as_posix()} src tests"],  # 正斜杠：pytest 用 shlex 切分，反斜杠会被吃掉
            cwd=str(ROOT), env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900,
        )
    output = completed.stdout
    failed = [f"{path}::{name}" for path, name in FAILED_LINE.findall(output)]
    count = int(SUMMARY.search(output).group(1)) if SUMMARY.search(output) else 0
    sentinel_ok = not any(item.endswith("test_the_adapter_under_test_is_the_expected_tree") for item in failed) and "error" not in output.splitlines()[-1].lower()
    killed = any(any(path.endswith(f"{name}.py") or f"/{name}.py::" in item for name in mutant.killers)
                 for item in failed for path in [item.split("::")[0]])
    return MutantResult(mutant.mutant_id, failed, count, killed, sentinel_ok, applied_once)


@pytest.mark.parametrize("mutant", MUTANTS, ids=lambda m: m.mutant_id)
def test_every_mutant_is_killed_by_a_designated_test(mutant):
    result = run_mutant(mutant)
    assert result.applied_once, f"{mutant.mutant_id}: the patch must apply exactly once (the mutant would be vacuous)"
    assert result.sentinel_ok, f"{mutant.mutant_id}: the sentinel shows the tests did not run against the mutated copy"
    assert result.killed_by_designated, f"{mutant.mutant_id} survived: failed={result.failed_tests}"
    assert result.failed_count >= 1


def test_the_mutant_table_covers_m01_to_m17_exactly():
    assert [m.mutant_id for m in MUTANTS] == [f"M-{index:02d}" for index in range(1, 18)]
    for mutant in MUTANTS:
        assert (ROOT / "tests" / "amane_adapter" / f"{mutant.killers[0]}.py").is_file()
        assert (TREE / mutant.file).is_file()


def test_the_original_tree_is_untouched_by_the_harness():
    for mutant in MUTANTS:
        text = (TREE / mutant.file).read_text(encoding="utf-8").replace("\r\n", "\n")
        assert text.count(mutant.old) == 1 and mutant.new != mutant.old
    assert not (TREE / "p5c1_mutant.txt").exists() and not (ROOT / "p5c1_mutant.txt").exists()


if __name__ == "__main__":  # pragma: no cover - 供 HANDOFF 打印 mutation 记录
    for item in MUTANTS:
        outcome = run_mutant(item)
        print(f"{outcome.mutant_id} {item.description}: applied_once={outcome.applied_once} sentinel_ok={outcome.sentinel_ok} "
              f"killed={outcome.killed_by_designated} failed_count={outcome.failed_count}")
        for name in outcome.failed_tests:
            print(f"    {name}")
