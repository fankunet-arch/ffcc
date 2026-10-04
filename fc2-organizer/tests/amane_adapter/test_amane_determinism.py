"""P5-C1 §24（E20）：确定性——同输入重复结果逐字节相同；``PYTHONHASHSEED`` 无影响；映射模块无非确定性来源。"""

from __future__ import annotations

import ast
import dataclasses
import json
import os
import subprocess
import sys
from pathlib import Path

from _amane_scenarios import client_4979299, lookup, runtime_for
from fc2_amane_adapter import _number, _outcome, _runtime, _settings

ROOT = Path(__file__).resolve().parents[2]
PROBE = Path(__file__).resolve().parent / "_determinism_probe.py"
NON_DETERMINISTIC_IMPORTS = {"random", "time", "datetime", "os", "secrets", "uuid", "sys", "platform", "locale"}


def _probe(seed: str) -> bytes:
    env = {**os.environ, "PYTHONHASHSEED": seed}
    completed = subprocess.run([sys.executable, str(PROBE)], capture_output=True, env=env, cwd=str(ROOT), timeout=120)
    assert completed.returncode == 0, completed.stderr.decode("utf-8", "replace")
    return completed.stdout


def test_repeated_lookups_are_identical():
    first = lookup(runtime_for(client_4979299()), "FC2-PPV-4979299")
    for _ in range(4):
        again = lookup(runtime_for(client_4979299()), "FC2-PPV-4979299")
        assert dataclasses.asdict(again) == dataclasses.asdict(first)


def test_probe_output_is_byte_identical_under_three_hash_seeds():
    outputs = {seed: _probe(seed) for seed in ("0", "1", "2")}
    assert outputs["0"] == outputs["1"] == outputs["2"]
    data = json.loads(outputs["0"])
    assert set(data) == {
        "allhit:fc2db_net,javdb,av123", "allhit:av123,javdb,fc2db_net", "allhit:javdb,fc2db_net,av123",
        "success", "partial", "mixed_failure", "all_not_found", "non_fc2", "content_type", "foreign",
    }
    assert data["all_not_found"]["type"] == "AdapterNoMatch"
    assert data["mixed_failure"]["type"] == "AdapterFailure"
    urls = {key: value["value"]["record"]["source_url"] for key, value in data.items() if key.startswith("allhit")}
    assert urls == {
        "allhit:fc2db_net,javdb,av123": "https://fc2db.net/work/4979299/",
        "allhit:av123,javdb,fc2db_net": "https://123av.com/en/v/fc2-ppv-4979299",
        "allhit:javdb,fc2db_net,av123": "https://javdb.com/v/QNkPbM",
    }


def test_probe_is_not_vacuous_it_really_depends_on_configuration_order():
    data = json.loads(_probe("0"))
    records = {key: json.dumps(value["value"]["record"], sort_keys=True) for key, value in data.items() if key.startswith("allhit")}
    assert len(set(records.values())) > 1


def test_mapping_modules_import_no_clock_random_or_environment_module():
    for module in (_number, _outcome, _runtime, _settings):
        tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
        roots = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                roots |= {alias.name.split(".")[0] for alias in node.names}
            elif isinstance(node, ast.ImportFrom) and not node.level:
                roots.add((node.module or "").split(".")[0])
        assert not roots & NON_DETERMINISTIC_IMPORTS, (module.__name__, roots & NON_DETERMINISTIC_IMPORTS)
