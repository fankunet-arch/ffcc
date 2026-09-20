#!/usr/bin/env python3
"""Phase 3 C3: the pre-batch 50-ID live coverage gate.

    python tools/run_50id_coverage_gate.py --run-kind primary \\
        --set docs/acceptance/PHASE3_50_ID_SET.json \\
        --out-dir docs/acceptance/evidence

Runs the real ``MultiSourceEngine`` (default source order ``fc2db_net, javdb, av123``; the **C2 frozen
default** ``RetryPolicy`` -- there is deliberately no flag to change attempts, deadlines or order) on the IDs
of the *frozen* set file, **sequentially**, ``--delay-seconds`` (>= 3, default 4) between IDs, through one
shared ``HttpxTransport``. Inside one ID the three sources run with the engine's normal bounded concurrency.

Metric (frozen): an ID is **COVERED** iff the aggregate result is not ``FAILED``, has metadata, and
``metadata.meets_minimum_success()`` (canonical number + non-empty title). ``SUCCESS`` *and* ``PARTIAL`` can
be covered -- this gate measures metadata coverage, not source health, so every ``PARTIAL`` and every
source-level failure is reported separately. Gate: ``covered >= 45`` of 50.

Anti-cherry-picking guards (all enforced here, all visible to a reviewer):

* the ID list comes **only** from the set file; there is no CLI way to add, drop or replace an ID, and the
  set must be exactly 50 distinct canonical IDs;
* ``--run-kind primary`` refuses to run when the working tree is dirty, when the set file is not committed
  unchanged, or when *any* primary evidence file already exists in ``--out-dir`` -- one primary run only;
* a ``diagnostic`` run is labelled as such in its file name and content and never replaces the primary;
* evidence is never overwritten.

Evidence contains only IDs, aggregate/source statuses, structured error kinds, attempt counts, engine
timings and the coverage verdict -- never a response body, header, cookie, credential, title or URL.
No Cloudflare / CAPTCHA bypass exists anywhere: a challenge is that source's ``BLOCKED``, one attempt.
"""

from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import hashlib
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fc2_metadata_core.aggregation import (  # noqa: E402
    AggregateStatus,
    MultiSourceEngine,
    RetryPolicy,
    default_aggregation_config,
)
from fc2_metadata_core.http.httpx_client import HttpxTransport  # noqa: E402
from fc2_metadata_core.models.source_result import SourceErrorKind, SourceStatus  # noqa: E402
from fc2_metadata_core.normalize.fc2_number import normalize_fc2_number  # noqa: E402
from fc2_metadata_core.sources.adapters import build_default_registry  # noqa: E402

SCHEMA_VERSION = 1
SET_SIZE = 50
REQUIRED_COVERED = 45
THRESHOLD_PERCENT = 90.0
MIN_DELAY_SECONDS = 3.0
DEFAULT_DELAY_SECONDS = 4.0
PRIMARY_PREFIX = "PHASE3_50_ID_GATE_PRIMARY_"
DIAGNOSTIC_PREFIX = "PHASE3_50_ID_GATE_DIAGNOSTIC_"
SOURCE_STATUSES = tuple(s.value for s in SourceStatus)

REPO_ROOT = Path(__file__).resolve().parents[2]  # <repo>/fc2-organizer/tools/x.py -> <repo>


# ---- pure evidence logic (unit-tested offline) ---------------------------------------------------------------------------------


def is_covered(result) -> bool:
    """The frozen coverage predicate: not FAILED, has metadata, and metadata meets minimum success."""
    return (
        result.status is not AggregateStatus.FAILED
        and result.metadata is not None
        and result.metadata.meets_minimum_success()
    )


def _attempt_entry(attempt) -> dict:
    return {
        "sequence": attempt.sequence,
        "status": attempt.status.value,
        "error_kind": None if attempt.error_kind is None else attempt.error_kind.value,
        "elapsed_ms": round(attempt.elapsed_ms),
        "backoff_before_seconds": attempt.backoff_before_seconds,
        "completed": attempt.completed,
    }


def summarize_id(result) -> dict:
    """One ID's evidence record. Only ids / statuses / structured kinds / counts / engine timings."""
    traces = {t.source_id: t for t in result.source_execution_traces}
    sources = []
    for final in result.source_results:
        trace = traces.get(final.source_id)
        sources.append(
            {
                "source_id": final.source_id,
                "final_status": final.status.value,
                "error_kind": None if final.error_kind is None else final.error_kind.value,
                "attempt_count": None if trace is None else trace.attempt_count,
                "retried": None if trace is None else trace.retried,
                "deadline_exceeded": None if trace is None else trace.deadline_exceeded,
                "engine_elapsed_ms": None if trace is None else round(sum(a.elapsed_ms for a in trace.attempts)),
                "attempts": [] if trace is None else [_attempt_entry(a) for a in trace.attempts],
            }
        )
    metadata = result.metadata
    return {
        "number": result.number,
        "aggregate_status": result.status.value,
        "covered": is_covered(result),
        "title_present": bool(metadata is not None and metadata.has_non_empty_title()),
        "canonical_number_present": bool(metadata is not None and metadata.has_valid_canonical_number()),
        "number_matches_request": bool(metadata is not None and metadata.number == result.number),
        "elapsed_ms": round(result.elapsed_ms),
        "sources": sources,
    }


def failure_record(number: str, exc: BaseException) -> dict:
    """An ID whose aggregate call raised: never silently dropped, never covered."""
    return {
        "number": number,
        "aggregate_status": "engine_exception",
        "covered": False,
        "title_present": False,
        "canonical_number_present": False,
        "number_matches_request": False,
        "elapsed_ms": 0,
        "engine_exception_type": type(exc).__name__,
        "sources": [],
    }


def compute_summary(records: list[dict]) -> dict:
    total = len(records)
    covered = sum(1 for r in records if r["covered"])
    return {
        "total": total,
        "covered": covered,
        "not_covered": total - covered,
        "coverage_percent": round(100.0 * covered / total, 2) if total else 0.0,
        "threshold_percent": THRESHOLD_PERCENT,
        "required_covered_of_50": REQUIRED_COVERED,
        "numeric_threshold_met": total == SET_SIZE and covered >= REQUIRED_COVERED,
        "aggregate_status_counts": dict(sorted(Counter(r["aggregate_status"] for r in records).items())),
        "covered_but_partial": sorted(r["number"] for r in records if r["covered"] and r["aggregate_status"] == "partial"),
    }


def compute_source_statistics(records: list[dict]) -> dict:
    stats: dict[str, dict] = {}
    for record in records:
        for src in record["sources"]:
            s = stats.setdefault(
                src["source_id"],
                {
                    "ids": 0,
                    "final_status_counts": {v: 0 for v in SOURCE_STATUSES},
                    "final_error_kind_counts": {},
                    "attempts_total": 0,
                    "ids_retried": 0,
                    "engine_elapsed_ms_total": 0,
                    "deadline_exceeded": 0,
                },
            )
            s["ids"] += 1
            s["final_status_counts"][src["final_status"]] += 1
            if src["error_kind"]:
                s["final_error_kind_counts"][src["error_kind"]] = s["final_error_kind_counts"].get(src["error_kind"], 0) + 1
            s["attempts_total"] += src["attempt_count"] or 0
            s["ids_retried"] += 1 if src["retried"] else 0
            s["engine_elapsed_ms_total"] += src["engine_elapsed_ms"] or 0
            s["deadline_exceeded"] += 1 if src["deadline_exceeded"] else 0
    for s in stats.values():
        s["operational_failures"] = sum(
            n for status, n in s["final_status_counts"].items() if status not in ("success", "not_found")
        )
        s["engine_elapsed_ms_mean"] = round(s["engine_elapsed_ms_total"] / s["ids"]) if s["ids"] else 0
    return dict(sorted(stats.items()))


def compute_retry_statistics(records: list[dict]) -> dict:
    events = []
    for record in records:
        for src in record["sources"]:
            if src["attempt_count"] and src["attempt_count"] > 1:
                events.append(
                    {
                        "number": record["number"],
                        "source_id": src["source_id"],
                        "attempt_kinds": [a["error_kind"] or a["status"] for a in src["attempts"]],
                        "final_status": src["final_status"],
                        "id_covered": record["covered"],
                    }
                )
    return {"live_retries_observed": len(events), "events": events}


def find_m1_violations(records: list[dict]) -> list[dict]:
    """Any source that ended BLOCKED after more than one attempt: an implementation failure (C2 M1)."""
    return [
        {"number": r["number"], "source_id": s["source_id"], "attempt_count": s["attempt_count"]}
        for r in records
        for s in r["sources"]
        if s["final_status"] == SourceStatus.BLOCKED.value and (s["attempt_count"] or 0) > 1
    ]


def build_evidence(records: list[dict], *, run_kind: str, meta: dict) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "run_kind": run_kind,
        **meta,
        "summary": compute_summary(records),
        "source_statistics": compute_source_statistics(records),
        "retry_statistics": compute_retry_statistics(records),
        "m1_violations": find_m1_violations(records),
        "uncovered": [
            {"number": r["number"], "aggregate_status": r["aggregate_status"],
             "source_final": {s["source_id"]: [s["final_status"], s["error_kind"], s["attempt_count"]] for s in r["sources"]}}
            for r in records
            if not r["covered"]
        ],
        "results": records,
    }


def render_markdown(evidence: dict) -> str:
    s, m = evidence["summary"], evidence
    lines = [
        f"# Phase 3 C3 - 50-ID coverage gate ({m['run_kind'].upper()} run)",
        "",
        f"- Run kind: **{m['run_kind']}**" + (" (the formal acceptance result)" if m["run_kind"] == "primary" else " (diagnostic only - does NOT replace the primary result)"),
        f"- Started / finished (UTC): {m['started_at_utc']} / {m['finished_at_utc']}",
        f"- Code head: `{m['code_head']}` (working tree clean: {m['worktree_clean']})",
        f"- Set file: `{m['set_file']}` sha256 `{m['set_file_sha256']}`; last commit touching it `{m['set_last_commit']}`",
        f"- Config: order {m['config']['source_order']}, max_concurrency {m['config']['max_concurrency']}, "
        f"deadline {m['config']['deadline_seconds']}s/source, RetryPolicy {m['config']['retry_policy']}, "
        f"{m['config']['delay_between_ids_seconds']}s between IDs (sequential)",
        "",
        "## Result",
        "",
        f"**covered {s['covered']} / {s['total']} = {s['coverage_percent']}%** "
        f"(threshold >= {s['required_covered_of_50']}/50 = {s['threshold_percent']}%) -> "
        f"**{'NUMERIC THRESHOLD MET' if s['numeric_threshold_met'] else 'BELOW THRESHOLD'}**",
        "",
        f"Aggregate statuses: {s['aggregate_status_counts']}",
        f"Covered but only PARTIAL (a source failed operationally): {s['covered_but_partial'] or 'none'}",
        f"Live retries observed: **{m['retry_statistics']['live_retries_observed']}**; "
        f"M1 violations (BLOCKED after >1 attempt): **{len(m['m1_violations'])}**",
        "",
        "## Source-level statistics (final results)",
        "",
        "| source | ids | success | not_found | blocked | rate_limited | network_error | parse_error | invalid_response | attempts | ids retried | mean engine ms |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for source_id, st in m["source_statistics"].items():
        c = st["final_status_counts"]
        lines.append(
            f"| {source_id} | {st['ids']} | {c['success']} | {c['not_found']} | {c['blocked']} | {c['rate_limited']} | "
            f"{c['network_error']} | {c['parse_error']} | {c['invalid_response']} | {st['attempts_total']} | "
            f"{st['ids_retried']} | {st['engine_elapsed_ms_mean']} |"
        )
    lines += ["", "## Uncovered IDs", ""]
    if m["uncovered"]:
        lines += ["| number | aggregate | per-source [status, error_kind, attempts] |", "|---|---|---|"]
        lines += [f"| {u['number']} | {u['aggregate_status']} | {u['source_final']} |" for u in m["uncovered"]]
    else:
        lines.append("none")
    lines += ["", "## Retry events", ""]
    events = m["retry_statistics"]["events"]
    lines += [f"- {e['number']} / {e['source_id']}: attempts {e['attempt_kinds']} -> final {e['final_status']}" for e in events] or [
        "0 live retries observed."
    ]
    lines += ["", "## Per-ID results", "", "| number | aggregate | covered | title | fc2db_net | javdb | av123 | ms |", "|---|---|---|---|---|---|---|---|"]
    for r in m["results"]:
        cells = {s_["source_id"]: f"{s_['final_status']}x{s_['attempt_count']}" for s_ in r["sources"]}
        lines.append(
            f"| {r['number']} | {r['aggregate_status']} | {'yes' if r['covered'] else '**NO**'} | "
            f"{'yes' if r['title_present'] else 'no'} | {cells.get('fc2db_net', '-')} | {cells.get('javdb', '-')} | "
            f"{cells.get('av123', '-')} | {r['elapsed_ms']} |"
        )
    return "\n".join(lines) + "\n"


# ---- set file + git guards ---------------------------------------------------------------------------------------------------------------


def load_frozen_ids(set_path: Path) -> tuple[list[str], str]:
    raw = set_path.read_bytes()
    document = json.loads(raw.decode("utf-8"))
    numbers = [item["number"] for item in document["ids"]]
    canonical = []
    for number in numbers:
        verdict = normalize_fc2_number(number)
        if not verdict.recognized or verdict.canonical != number:
            raise SystemExit(f"set file has a non-canonical ID: {number!r}")
        canonical.append(verdict.canonical)
    if len(canonical) != SET_SIZE or len(set(canonical)) != SET_SIZE:
        raise SystemExit(f"set file must hold exactly {SET_SIZE} distinct IDs, found {len(canonical)} ({len(set(canonical))} distinct)")
    return canonical, hashlib.sha256(raw).hexdigest()


def _git(*args: str) -> str:
    completed = subprocess.run(["git", "-C", str(REPO_ROOT), *args], capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        raise SystemExit(f"git {' '.join(args)} failed: {completed.stderr.strip()}")
    return completed.stdout.strip()


def git_state(set_path: Path) -> dict:
    try:
        rel = str(set_path.resolve().relative_to(REPO_ROOT)).replace("\\", "/")
    except ValueError:
        raise SystemExit(f"the set file must live inside the repository ({REPO_ROOT}), got {set_path}") from None
    return {
        "code_head": _git("rev-parse", "HEAD"),
        "worktree_clean": _git("status", "--porcelain") == "",
        "set_committed_unchanged": _git("status", "--porcelain", "--", rel) == "" and _git("ls-files", "--", rel) != "",
        "set_last_commit": _git("log", "-1", "--format=%H", "--", rel),
    }


# ---- the live run --------------------------------------------------------------------------------------------------------------------------------


async def run_gate(numbers: list[str], engine, delay_seconds: float, *, sleep=asyncio.sleep, progress=None) -> list[dict]:
    """Sequential over IDs; never drops, replaces or reorders one. ``engine`` needs ``aggregate(number)``."""
    records: list[dict] = []
    for index, number in enumerate(numbers):
        if index:
            await sleep(delay_seconds)
        try:
            record = summarize_id(await engine.aggregate(number))
        except Exception as exc:  # noqa: BLE001 - an engine bug must surface as a NOT COVERED record, not vanish
            record = failure_record(number, exc)
        records.append(record)
        if progress is not None:
            progress(index + 1, len(numbers), record)
    return records


def _progress(done: int, total: int, record: dict) -> None:
    parts = " ".join(f"{s['source_id']}={s['final_status']}x{s['attempt_count']}" for s in record["sources"])
    print(f"[{done:02d}/{total}] {record['number']} {record['aggregate_status']} covered={record['covered']} {parts}", file=sys.stderr, flush=True)


async def _live(numbers: list[str], delay_seconds: float, *, http_transport=None) -> tuple[list[dict], dict]:
    """``http_transport`` (an ``httpx.AsyncBaseTransport``) exists only so tests can run this exact path offline."""
    config = default_aggregation_config()  # C2 frozen defaults: order, concurrency, deadlines, RetryPolicy()
    retry = config.retry_policy
    assert retry == RetryPolicy(), "the gate must run the C2 default retry policy"
    async with HttpxTransport(transport=http_transport) as client:
        engine = MultiSourceEngine(config, build_default_registry(), client)
        records = await run_gate(numbers, engine, delay_seconds, progress=_progress)
    return records, {
        "source_order": [s.source_id for s in config.sources],
        "max_concurrency": config.max_concurrency,
        "deadline_seconds": config.sources[0].deadline_seconds,
        "retry_policy": {
            "max_attempts": retry.max_attempts,
            "initial_backoff_seconds": retry.initial_backoff_seconds,
            "backoff_multiplier": retry.backoff_multiplier,
            "max_backoff_seconds": retry.max_backoff_seconds,
            "retryable_error_kinds": sorted(k.value for k in retry.retryable_error_kinds),
        },
        "delay_between_ids_seconds": delay_seconds,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--run-kind", choices=("primary", "diagnostic"), required=True)
    parser.add_argument("--set", required=True, dest="set_path")
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--delay-seconds", type=float, default=DEFAULT_DELAY_SECONDS)
    args = parser.parse_args(argv)

    if args.delay_seconds < MIN_DELAY_SECONDS:
        raise SystemExit(f"--delay-seconds must be >= {MIN_DELAY_SECONDS:g} (politeness floor)")
    set_path, out_dir = Path(args.set_path), Path(args.out_dir)
    numbers, set_sha = load_frozen_ids(set_path)
    state = git_state(set_path)
    if args.run_kind == "primary":
        if not state["worktree_clean"]:
            raise SystemExit("primary run refused: the working tree is not clean")
        if not state["set_committed_unchanged"]:
            raise SystemExit("primary run refused: the set file is not committed unchanged")
        if list(out_dir.glob(PRIMARY_PREFIX + "*")):
            raise SystemExit("primary run refused: primary evidence already exists (one primary run only)")
    out_dir.mkdir(parents=True, exist_ok=True)

    started = dt.datetime.now(dt.timezone.utc)
    records, config = asyncio.run(_live(numbers, args.delay_seconds))
    finished = dt.datetime.now(dt.timezone.utc)

    prefix = PRIMARY_PREFIX if args.run_kind == "primary" else DIAGNOSTIC_PREFIX
    stem = f"{prefix}{started.strftime('%Y%m%dT%H%M%SZ')}"
    meta = {
        "started_at_utc": started.isoformat(timespec="seconds"),
        "finished_at_utc": finished.isoformat(timespec="seconds"),
        "code_head": state["code_head"],
        "worktree_clean": state["worktree_clean"],
        "set_file": str(set_path).replace("\\", "/"),
        "set_file_sha256": set_sha,
        "set_last_commit": state["set_last_commit"],
        "config": config,
    }
    evidence = build_evidence(records, run_kind=args.run_kind, meta=meta)
    json_path, md_path = out_dir / f"{stem}.json", out_dir / f"{stem}.md"
    for path in (json_path, md_path):
        if path.exists():
            raise SystemExit(f"refusing to overwrite {path}")
    json_path.write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(evidence), encoding="utf-8")
    s = evidence["summary"]
    print(f"# {args.run_kind}: covered {s['covered']}/{s['total']} = {s['coverage_percent']}% -> "
          f"{'NUMERIC THRESHOLD MET' if s['numeric_threshold_met'] else 'BELOW THRESHOLD'}; wrote {json_path} and {md_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
