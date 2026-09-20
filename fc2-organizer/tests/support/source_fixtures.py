"""Loader for the real-response HTML excerpts under ``tests/fixtures/sources``.

Each fixture is a verbatim excerpt of a response captured from the real site
during Phase 2 live probing (see the provenance comment at the top of every
file), so adapter parser tests exercise real markup -- not markup invented to
make the parser pass.
"""

from __future__ import annotations

from pathlib import Path

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "sources"


def load_fixture(relative_path: str) -> str:
    return (FIXTURE_ROOT / relative_path).read_text(encoding="utf-8")
