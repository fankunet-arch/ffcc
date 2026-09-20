#!/usr/bin/env python3
"""Phase 3 C1 live aggregate smoke: run the real MultiSourceEngine on real numbers.

    python tools/probe_aggregate.py FC2-4825061 FC2-4824605 FC2-4979299

Runs the default configuration (the three Phase 2 VERIFIED sources, in the
configured priority order) through **one shared** ``HttpxTransport``, one
canonical number at a time, and prints one JSON object per number: the
aggregate status, the chosen title and which source it came from, every
source's outcome, the merged collections' sizes, ``field_sources`` and the
resolved conflicts.

Safety / politeness (same rules as ``probe_sources.py``):

- **records nothing by default** (no evidence file is written, and the Phase 2
  evidence JSON is never touched). ``--out FILE`` optionally saves the same
  summary JSON you see on stdout;
- never prints or stores a response body, cookie, or authorization value --
  only the summary fields below (titles are short human-readable excerpts);
- sequential across numbers, ``--delay-seconds`` (default 3.0) between them;
  each number issues exactly one request per enabled source;
- no Cloudflare / CAPTCHA bypass: a challenge is just that source's ``BLOCKED``.

This tool does **not** run the 50-ID acceptance gate; it is a smoke check.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fc2_metadata_core.aggregation import (  # noqa: E402
    AggregationConfig,
    AggregationConfigError,
    MultiSourceEngine,
    SourceConfig,
    default_aggregation_config,
)
from fc2_metadata_core.http.httpx_client import HttpxTransport  # noqa: E402
from fc2_metadata_core.normalize.fc2_number import normalize_fc2_number  # noqa: E402
from fc2_metadata_core.sources.adapters import build_default_registry  # noqa: E402


def _excerpt(text: str | None, limit: int = 70) -> str | None:
    return None if text is None else (text if len(text) <= limit else text[:limit] + "...")


def summarize(result) -> dict:
    metadata = result.metadata
    summary: dict = {
        "number": result.number,
        "aggregate_status": result.status.value,
        "elapsed_ms": round(result.elapsed_ms),
        "source_order": list(result.source_order),
        "contributing_source_ids": list(result.contributing_source_ids),
        "sources": [
            {
                "source_id": r.source_id,
                "status": r.status.value,
                "elapsed_ms": round(r.elapsed_ms),
                "error_detail": _excerpt(r.error_detail, 100),
            }
            for r in result.source_results
        ],
    }
    if metadata is not None:
        summary.update(
            {
                "title": _excerpt(metadata.title),
                "title_from": list(metadata.field_sources.get("title", ())),
                "release": metadata.release,
                "runtime": metadata.runtime,
                "publisher": metadata.publisher,
                "counts": {
                    name: len(getattr(metadata, name))
                    for name in ("actors", "tags", "thumb_urls", "source_urls", "external_ids")
                },
                "field_sources": {k: list(v) for k, v in metadata.field_sources.items()},
            }
        )
    summary["conflicts"] = [
        {
            "field": c.field,
            "key": c.key,
            "selected_from": c.selected_source_id,
            "alternatives_from": [sid for sid, _ in c.alternatives],
        }
        for c in result.conflicts
    ]
    return summary


async def _run(numbers: list[str], config: AggregationConfig, delay_seconds: float) -> list[dict]:
    summaries: list[dict] = []
    async with HttpxTransport() as client:
        engine = MultiSourceEngine(config, build_default_registry(), client)
        for index, number in enumerate(numbers):
            if index:
                await asyncio.sleep(delay_seconds)
            summaries.append(summarize(await engine.aggregate(number)))
    return summaries


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("numbers", nargs="+", help="FC2 numbers (canonical or recognizable)")
    parser.add_argument("--delay-seconds", type=float, default=3.0, help="Delay between numbers (default 3.0s)")
    parser.add_argument("--order", default=None, help="Comma-separated source ids: configuration order = default field priority")
    parser.add_argument("--max-concurrency", type=int, default=3)
    parser.add_argument("--deadline-seconds", type=float, default=20.0, help="Per-source wall-clock deadline")
    parser.add_argument("--out", default=None, help="Also write the summary JSON to this file (nothing is recorded otherwise)")
    args = parser.parse_args(argv)

    numbers: list[str] = []
    for raw in args.numbers:
        normalized = normalize_fc2_number(raw)
        if not normalized.recognized:
            raise SystemExit(f"not a recognizable FC2 number: {raw!r}")
        numbers.append(normalized.canonical)

    try:
        if args.order:
            config = AggregationConfig.create(
                [SourceConfig(sid.strip(), deadline_seconds=args.deadline_seconds) for sid in args.order.split(",")],
                max_concurrency=args.max_concurrency,
            )
        else:
            base = default_aggregation_config(max_concurrency=args.max_concurrency)
            config = AggregationConfig.create(
                [SourceConfig(s.source_id, deadline_seconds=args.deadline_seconds) for s in base.sources],
                max_concurrency=args.max_concurrency,
            )
    except AggregationConfigError as exc:
        raise SystemExit(f"invalid configuration: {exc}")

    summaries = asyncio.run(_run(numbers, config, args.delay_seconds))
    for summary in summaries:
        print(json.dumps(summary, indent=2, ensure_ascii=False))
    if args.out:
        Path(args.out).write_text(json.dumps(summaries, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"# wrote {len(summaries)} summary object(s) to {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
