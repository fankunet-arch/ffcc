"""P4-C4 synthetic NFO gate (contract section 14): 400+ varied ``PublicationRecord``s,
each rendered twice under the filesystem / network / clock / random / environment
traps, then verified through the stdlib XML parser.
"""

from __future__ import annotations

import pytest

from fc2_metadata_core.aggregation import AggregateStatus
from fc2_organizer.nfo import render_movie_nfo

from ._builders import (
    ALL_SENTINELS,
    SECRET_ERROR_DETAIL,
    NON_RENDERED_FIELDS,
    actors_of,
    child_texts,
    make_plan,
    make_record,
    parse,
    published,
)
from ._guards import traps

GATE_SIZE = 400

TITLES = [
    "Plain title", "日本語タイトル", "A & B <Special>", "</title><evil>true</evil><title>", 'Quote "q" \'s\'',
    "🎬 emoji 𠮷", "&amp; already-escaped", "  padded  ", "Tab\tand\nnewline", "CR\rtitle", "]]> cdata end",
    "<!DOCTYPE x [<!ENTITY e 'v'>]>&e;",
]
PLOTS = [None, "", "   ", "Short plot.", "Multi\nline\r\nplot & <b>html</b>", "長いあらすじ " * 40]
RELEASES = [None, "", "2026-09-19", "2024-02-29", "2000-01-01", "1999-12-31"]
STUDIOS = [None, " ", "Studio", "S & <S>", "スタジオ"]
ACTOR_SETS = [(), ("Alice",), ("Alice", "  ", "Bob"), ("Dup", "Dup"), ("<x>&", "女優", "🎭"), ("a", "b", "c", "d")]
TAG_SETS = [(), ("t",), ("b", "a", "b"), (" ", "tag"), ("<genre>", "&", "タグ")]


def _case(i: int) -> dict:
    number = f"FC2-{(100000 + i * 7919) if i % 2 else (1000000 + i * 9973)}"
    fields = dict(
        title=f"{TITLES[i % len(TITLES)]} #{i}",
        plot=PLOTS[i % len(PLOTS)],
        runtime=None if i % 4 == 0 else (0 if i % 4 == 1 else i),
        release=RELEASES[i % len(RELEASES)],
        studio=STUDIOS[i % len(STUDIOS)],
        actors=ACTOR_SETS[i % len(ACTOR_SETS)],
        tags=TAG_SETS[(i // 3) % len(TAG_SETS)],
    )
    if i % 3 == 0:
        fields.update(NON_RENDERED_FIELDS)
    status = AggregateStatus.PARTIAL if i % 2 else AggregateStatus.SUCCESS
    return dict(number=number, status=status, fields=fields)


@pytest.fixture(scope="module")
def gate():
    cases = [_case(i) for i in range(GATE_SIZE)]
    records = [
        make_record(c["number"], plan=make_plan(c["number"], index=i), status=c["status"], **c["fields"])
        for i, c in enumerate(cases)
    ]
    # plus real prepare_publication() records (real aggregates with traces + error_detail)
    for i in range(20):
        c = _case(1000 + i)
        records.append(published(c["number"], partial=bool(i % 2), index=1000 + i, **c["fields"]))
        cases.append(c)
    return cases, records


def test_gate_is_large_and_covers_the_required_variation(gate):
    cases, records = gate
    assert len(records) >= GATE_SIZE
    statuses = {r.aggregate_status for r in records}
    assert statuses == {AggregateStatus.SUCCESS, AggregateStatus.PARTIAL}
    fields = [c["fields"] for c in cases]
    assert any(f["plot"] and f["plot"].strip() for f in fields) and any(not (f["plot"] or "").strip() for f in fields)
    assert {f["runtime"] is None for f in fields} == {True, False} and any(f["runtime"] == 0 for f in fields)
    assert {bool((f["release"] or "").strip()) for f in fields} == {True, False}
    assert {bool((f["studio"] or "").strip()) for f in fields} == {True, False}
    assert {len(f["actors"]) for f in fields} >= {0, 1, 3, 4}
    assert {len(f["tags"]) for f in fields} >= {0, 1, 2, 3}
    assert sum("source_urls" in f for f in fields) > 100
    assert len({r.number for r in records}) == len(records)


def test_synthetic_gate(gate):
    cases, records = gate
    with traps():
        first = [render_movie_nfo(r) for r in records]
        second = [render_movie_nfo(r) for r in records]
    assert first == second

    for case, record, xml in zip(cases, records, first):
        xml.encode("utf-8", errors="strict")
        assert xml.endswith("</movie>\n") and not xml.endswith("\n\n") and "\r" not in xml
        root = parse(xml)
        assert root.tag == "movie"
        # expectations come from the record's own metadata (a real merge may e.g. dedupe actors upstream)
        f = {name: getattr(record.metadata, name) for name in ("title", "plot", "runtime", "release", "studio",
                                                                "actors", "tags")}
        assert root.findtext("title") == f["title"] == case["fields"]["title"]
        uid = root.find("uniqueid")
        assert uid.text == record.number == case["number"]
        assert uid.attrib == {"type": "fc2", "default": "true"} and len(root.findall("uniqueid")) == 1
        assert root.findtext("plot") == (f["plot"] if (f["plot"] or "").strip() else None)
        assert root.findtext("runtime") == (None if f["runtime"] is None else str(f["runtime"]))
        assert root.findtext("premiered") == (f["release"] if (f["release"] or "").strip() else None)
        assert root.findtext("studio") == (f["studio"] if (f["studio"] or "").strip() else None)
        kept_actors = [a for a in f["actors"] if a.strip()]
        assert actors_of(root) == [(a, str(i)) for i, a in enumerate(kept_actors)]
        assert child_texts(root, "tag") == [t for t in f["tags"] if t.strip()]
        assert root.find(".//evil") is None and root.find("genre") is None
        for sentinel in ALL_SENTINELS + (SECRET_ERROR_DETAIL,):
            assert sentinel not in xml
        lowered = xml.lower()
        assert "success" not in lowered and "partial" not in lowered and "<!--" not in xml


def test_gate_status_flip_never_changes_output(gate):
    """Every gate record re-rendered with the opposite publishable status: byte-identical."""
    cases, records = gate
    flip = {AggregateStatus.SUCCESS: AggregateStatus.PARTIAL, AggregateStatus.PARTIAL: AggregateStatus.SUCCESS}
    for record in records[:GATE_SIZE]:
        twin = type(record)(plan=record.plan, metadata=record.metadata, aggregate_status=flip[record.aggregate_status])
        assert render_movie_nfo(twin) == render_movie_nfo(record)
