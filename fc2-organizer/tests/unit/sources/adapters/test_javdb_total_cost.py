"""C0-R1-01: the JavDB parser's TOTAL cost is bounded, not just each helper's.

The independent C0 closure review found that although every ``_scan``
primitive was capped, a crafted page under the 5 MiB transport cap could still
hold ``parse_javdb_search_page`` for seconds: ~200 items x several marker
lookups per item x re-scanning/re-parsing the same (up to 1.5 KB) opening tag
per marker occurrence. Reviewer measurements against C0 code head
``8b16bdbc236fac422074994622670905c8d9b2ec``:

    ~732 KiB -> 1.2 s     ~1.5 MiB -> 3.8-4.5 s     ~1.8 MiB -> ~5.5 s
    (the real fixture: ~2.8 ms)

The shapes live in ``support/adversarial_javdb.py`` and run in a **child
process** with a hard timeout (``re`` holds the GIL, so a regression must be
killed from outside). Budgets: 0.5 s per hostile case (the fixed parser's
worst is ~0.05 s, the C0 parser was over 1.2 s from 750 KiB), always below the
C0 suite's 1.0 s budget.
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from fc2_metadata_core.models.source_result import SourceStatus
from fc2_metadata_core.sources.adapters.javdb import JavdbAdapter, parse_javdb_search_page

from support.fake_http_client import FakeHttpClient, make_response
from support.source_fixtures import load_fixture

ROOT = Path(__file__).resolve().parents[4]
CHILD_TIMEOUT_SECONDS = 120
C0_BUDGET_SECONDS = 1.0
KIB = 1024

EXPECTED_SIZES = {"750 KiB": 750 * KIB, "1.5 MiB": 1536 * KIB, "3 MiB": 3 * 1024 * KIB, "5 MiB": 5 * 1024 * KIB}


@pytest.fixture(scope="module")
def rows() -> list[dict]:
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join([str(ROOT / "src"), str(ROOT / "tests")])
    try:
        completed = subprocess.run(
            [sys.executable, "-m", "support.adversarial_javdb"],
            capture_output=True,
            text=True,
            timeout=CHILD_TIMEOUT_SECONDS,
            env=env,
            cwd=str(ROOT),
        )
    except subprocess.TimeoutExpired as exc:
        partial = exc.stdout or ""
        if isinstance(partial, bytes):
            partial = partial.decode("utf-8", "replace")
        last = partial.strip().splitlines()[-1] if partial.strip() else "(no case finished)"
        pytest.fail(
            f"JavDB total-cost run exceeded {CHILD_TIMEOUT_SECONDS}s: the parser's total work is "
            f"not bounded. Last finished case: {last}"
        )
    assert completed.returncode == 0, completed.stderr[-2000:]
    parsed = [json.loads(line) for line in completed.stdout.splitlines() if line.startswith("{")]
    assert parsed, "no cases ran"
    return parsed


def test_every_case_is_within_its_budget_and_the_c0_budget(rows):
    over = [r for r in rows if r["seconds"] > r["budget"] or r["seconds"] > C0_BUDGET_SECONDS]
    assert not over, over


def test_reviewer_shape_is_covered_at_750kib_1_5mib_and_larger_via_parse_and_fetch(rows):
    headline = [r for r in rows if r["case"].startswith("reviewer-shaped")]
    assert {(r["path"], r["size"]) for r in headline} == {
        (path, size) for path in ("parse", "fetch") for size in EXPECTED_SIZES
    }
    for r in headline:
        expected = EXPECTED_SIZES[r["size"]]
        assert abs(r["chars"] - expected) <= expected * 0.02, r  # the page really is that big


def test_the_hostile_pages_really_are_hostile_shaped(rows):
    """Guards the generator itself: if these numbers drop the test would pass
    vacuously. 200 items (the parser's cap) and thousands of marker occurrences."""
    for r in rows:
        if r["path"] == "parse" and r["case"].startswith("reviewer-shaped"):
            assert r["items"] >= 200, r
            assert r["markers"] >= 9000, r
        if r["path"] == "parse" and r["case"].startswith("window-filling"):
            assert r["items"] >= 200 and r["status"] == "not_found", r  # all 200 items fully parsed


def test_hostile_pages_never_yield_a_success_and_never_crash(rows):
    for r in rows:
        if r["expect"] == "any_failure":
            assert r["status"] in ("invalid_response", "not_found", "parse_error"), r
        else:
            assert r["expect"] == "success"
            assert r["status"] == "success", r


def test_real_data_survives_a_hostile_tail(rows):
    tail = [r for r in rows if r["case"].startswith("valid exact hit")]
    assert len(tail) == len(EXPECTED_SIZES)
    assert all(r["status"] == "success" for r in tail)


# ---- correctness at the scan budget (in-process, cheap) --------------------------------------


def _item(code, title="t"):
    return (
        f'<div class="item"><a href="/v/AAA111" class="box" title="{title}">'
        f'<div class="video-title"><strong>{code}</strong> {title}</div></a></div>'
    )


def _page(*items, tail=""):
    return '<div class="movie-list">' + "".join(items) + "</div>" + tail


def _parse(html, number="FC2-4825061"):
    return parse_javdb_search_page(html, number, "https://javdb.com")


def test_near_misses_on_a_normal_page_are_still_not_found():
    metadata, error = _parse(_page(_item("FC2-1825061"), _item("FC2-4725061")))
    assert metadata is None and error[0] is SourceStatus.NOT_FOUND
    assert "listed 2 other number(s)" in error[1]


def test_a_large_page_with_no_more_class_attributes_is_not_treated_as_truncated():
    # 600 KB of plain text after the list: past the scan window, but nothing
    # left to miss, so a genuine miss is still NOT_FOUND.
    html = _page(_item("FC2-1825061"), tail="x " * 300_000)
    metadata, error = _parse(html)
    assert metadata is None and error[0] is SourceStatus.NOT_FOUND


def test_class_attributes_beyond_the_scan_window_make_a_miss_inconclusive_not_not_found():
    html = _page(_item("FC2-1825061"), tail="x " * 300_000 + '<div class="item">')
    metadata, error = _parse(html)
    assert metadata is None and error[0] is SourceStatus.INVALID_RESPONSE
    assert "cannot conclude not found" in error[1]


def test_more_items_than_the_item_cap_make_a_miss_inconclusive():
    items = [_item(f"FC2-{1000000 + n}") for n in range(230)]
    metadata, error = _parse(_page(*items))
    assert metadata is None and error[0] is SourceStatus.INVALID_RESPONSE
    assert "cannot conclude not found" in error[1]


def test_probe_budget_exhaustion_makes_a_miss_inconclusive():
    filler = '<i class="x"></i>' * 9000  # > the class-probe budget
    metadata, error = _parse(_page(_item("FC2-1825061"), tail=filler))
    assert metadata is None and error[0] is SourceStatus.INVALID_RESPONSE


def test_an_exact_hit_seen_before_the_budget_ran_out_is_still_a_success():
    items = [_item("FC2-4825061", "the right one")] + [_item(f"FC2-{1000000 + n}") for n in range(230)]
    metadata, error = _parse(_page(*items))
    assert error is None and metadata.title == "the right one"


def test_truncation_never_hides_an_empty_result_page():
    metadata, error = _parse('<div class="empty-message">none</div>' + "x " * 300_000)
    assert metadata is None and error[0] is SourceStatus.NOT_FOUND


def test_real_fixtures_are_far_below_every_cap_and_unchanged():
    hit, err = _parse(load_fixture("javdb/search_hit_4825061.html"))
    assert err is None and hit.number == "FC2-4825061" and hit.release == "2026-01-02"
    metadata, error = _parse(load_fixture("javdb/search_no_exact_4824605.html"), "FC2-4824605")
    assert metadata is None and error[0] is SourceStatus.NOT_FOUND
    assert "listed 2 other number(s)" in error[1]  # FC2-1824605 and FC2-4724605


def test_fetch_path_reports_truncation_as_invalid_response():
    adapter = JavdbAdapter()
    client = FakeHttpClient()
    url = adapter._lookup_url("FC2-4825061")
    html = _page(_item("FC2-1825061"), tail="x " * 300_000 + '<div class="item">')
    client.add_response(url, make_response(url=url, text=html))
    result = asyncio.run(adapter.fetch("FC2-4825061", client))
    assert result.status is SourceStatus.INVALID_RESPONSE and result.metadata is None
