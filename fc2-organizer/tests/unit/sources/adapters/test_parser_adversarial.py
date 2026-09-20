"""C0-02: no parser may take unbounded time on a corrupt or hostile page.

The parsers run synchronously inside ``async fetch`` and Phase 3 will run
several sources concurrently, so one bad response must not hold the event
loop. The cases live in ``support/adversarial_html.py`` and run in a **child
process**: Python's ``re`` holds the GIL, so a catastrophic pattern cannot be
interrupted from inside the test process -- but the child can be killed. A
regression therefore surfaces here as a clean, bounded failure (timeout or a
case over budget) instead of a hung test run.

Old behaviour this pins against (measured at Phase 2 review, unclosed relevant
tag + whitespace): fc2db_net 2000 spaces 2.9 s / 4000 spaces 63 s, av123
2000 spaces 7.5 s, javdb 2000 spaces 3.7 s. The new parsers take single-digit
milliseconds on 5 MiB, so the per-case budget below leaves ~100x CI headroom
while still failing the old seconds-scale behaviour by a wide margin.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[4]
PER_CASE_BUDGET_SECONDS = 1.0
CHILD_TIMEOUT_SECONDS = 90


@pytest.fixture(scope="module")
def results() -> list[dict]:
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join([str(ROOT / "src"), str(ROOT / "tests")])
    try:
        completed = subprocess.run(
            [sys.executable, "-m", "support.adversarial_html"],
            capture_output=True,
            text=True,
            timeout=CHILD_TIMEOUT_SECONDS,
            env=env,
            cwd=str(ROOT),
        )
    except subprocess.TimeoutExpired as exc:
        partial = (exc.stdout or b"")
        if isinstance(partial, bytes):
            partial = partial.decode("utf-8", "replace")
        last = partial.strip().splitlines()[-1] if partial.strip() else "(no case finished)"
        pytest.fail(
            f"adversarial parser run exceeded {CHILD_TIMEOUT_SECONDS}s -- a parser has "
            f"super-linear behaviour. Last finished case: {last}"
        )
    assert completed.returncode == 0, completed.stderr[-2000:]
    rows = [json.loads(line) for line in completed.stdout.splitlines() if line.startswith("{")]
    assert rows, "no adversarial cases ran"
    return rows


def test_every_adversarial_case_finishes_within_budget(results):
    slow = [r for r in results if r["seconds"] > PER_CASE_BUDGET_SECONDS]
    assert not slow, slow


def test_hostile_pages_are_failures_never_successes_or_crashes(results):
    wrong = [r for r in results if r["expectation"] == "fail" and r["status"] not in (
        "parse_error", "invalid_response", "not_found")]
    assert not wrong, wrong


def test_reviewer_reproductions_are_parse_or_invalid_response(results):
    repro = [r for r in results if r["case"].startswith("unclosed relevant tag")]
    assert {r["parser"] for r in repro} == {"fc2db_net", "av123", "javdb"}
    for r in repro:
        assert r["status"] in ("parse_error", "invalid_response"), r


def test_the_suite_actually_exercises_5_mib_inputs_on_every_parser(results):
    for parser in ("fc2db_net", "av123", "javdb"):
        biggest = max(r["chars"] for r in results if r["parser"] == parser)
        assert biggest >= 5 * 1024 * 1024, (parser, biggest)


def test_valid_heading_survives_hostile_tail_for_the_heading_parsers(results):
    # A genuine page with junk appended must still parse (bounded, not bricked).
    for r in results:
        if r["case"].startswith("valid page + ") and r["parser"] in ("fc2db_net", "av123"):
            assert r["status"] == "success", r
