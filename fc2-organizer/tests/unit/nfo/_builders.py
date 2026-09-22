"""Shared builders for the P4-C4 NFO tests (fully offline).

Records are real ``PublicationRecord``s: plans come from the real
``build_organize_plan``, aggregates (where a test needs the real publication
path) from the real ``merge_source_results`` + ``prepare_publication``.
``forge`` bypasses ``NormalizedMetadata`` validation with
``object.__setattr__`` on a freshly built record, to reach shapes the normal
constructors can never produce (hostile ``str`` subclasses, lists, bools, ...).
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

from fc2_metadata_core.aggregation import (
    AggregateStatus,
    AggregationPolicy,
    AggregationResult,
    SourceAttempt,
    SourceExecutionTrace,
    merge_source_results,
)
from fc2_metadata_core.models import NormalizedMetadata, SourceErrorKind, SourceResult, SourceStatus
from fc2_organizer.discovery import DiscoveredMediaItem
from fc2_organizer.planning import OrganizePlan, build_organize_plan
from fc2_organizer.publication import PublicationRecord, prepare_publication

N = "FC2-1234567"
LIBRARY_ROOT = r"C:\library"
XML_DECLARATION = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'

SECRET_PUBLISHER = "SECRET-PUBLISHER"
SECRET_SOURCE_URL = "https://SECRET-SOURCE-URL.example/detail/1"
SECRET_FIELD_SOURCE = "SECRET-FIELD-SOURCE"
SECRET_EXTERNAL_ID = "SECRET-EXTERNAL-ID"
SECRET_POSTER = "https://SECRET-POSTER-URL.example/p.jpg"
SECRET_THUMB = "https://SECRET-THUMB-URL.example/t.jpg"
SECRET_FANART = "https://SECRET-FANART-URL.example/f.jpg"
SECRET_EXTRAFANART = "https://SECRET-EXTRAFANART-URL.example/e.jpg"
SECRET_ERROR_DETAIL = "cookie=SESSION-SECRET-7f3a; Authorization: Bearer tok-XYZ"

ALL_SENTINELS = (
    SECRET_PUBLISHER, "SECRET-SOURCE-URL", SECRET_FIELD_SOURCE, SECRET_EXTERNAL_ID, "SECRET-POSTER-URL",
    "SECRET-THUMB-URL", "SECRET-FANART-URL", "SECRET-EXTRAFANART-URL", "SESSION-SECRET", "tok-XYZ",
)

# Every non-rendered metadata field, each carrying a unique sentinel.
NON_RENDERED_FIELDS = dict(
    publisher=SECRET_PUBLISHER,
    poster_urls=(SECRET_POSTER,),
    thumb_urls=(SECRET_THUMB,),
    fanart_urls=(SECRET_FANART,),
    extrafanart=(SECRET_EXTRAFANART,),
    source_urls=(SECRET_SOURCE_URL,),
    external_ids={"javdb": SECRET_EXTERNAL_ID, SECRET_EXTERNAL_ID: "x"},
    field_sources={"title": (SECRET_FIELD_SOURCE,), SECRET_FIELD_SOURCE: ("a",)},
)


def make_plan(number: str = N, *, index: int = 0) -> OrganizePlan:
    item = DiscoveredMediaItem(
        index=index,
        source_path=rf"C:\downloads\movie{index}.mp4",
        relative_path=f"movie{index}.mp4",
        extension=".mp4",
        size=1000 + index,
    )
    return build_organize_plan(item, number, NormalizedMetadata(number=number, title="planning"), LIBRARY_ROOT)


def make_record(
    number: str = N,
    *,
    title: str = "Example",
    status: AggregateStatus = AggregateStatus.SUCCESS,
    plan: OrganizePlan | None = None,
    **fields,
) -> PublicationRecord:
    metadata = NormalizedMetadata(number=number, title=title, **fields)
    return PublicationRecord(plan=plan or make_plan(number), metadata=metadata, aggregate_status=status)


def forge(record: PublicationRecord | None = None, **overrides) -> PublicationRecord:
    """A fresh record whose metadata attributes are overwritten *after* validation."""
    record = record if record is not None else make_record()
    for name, value in overrides.items():
        object.__setattr__(record.metadata, name, value)
    return record


def make_aggregate(number: str, *, partial: bool, **fields) -> AggregationResult:
    """Real merged aggregate: SUCCESS (+ NOT_FOUND) or PARTIAL (+ BLOCKED), with traces and error_detail."""
    ok = SourceResult(
        source_id="a",
        status=SourceStatus.SUCCESS,
        metadata=NormalizedMetadata(number=number, **fields),
        elapsed_ms=12.5,
    )
    status, kind = (SourceStatus.BLOCKED, SourceErrorKind.BLOCKED) if partial else (
        SourceStatus.NOT_FOUND, SourceErrorKind.NOT_FOUND
    )
    bad = SourceResult(
        source_id="b", status=status, metadata=None, elapsed_ms=0.0, error_kind=kind,
        error_detail=f"b: {SECRET_ERROR_DETAIL}",
    )
    traces = tuple(
        SourceExecutionTrace(r.source_id, (SourceAttempt(1, r.status, r.error_kind, 7.0),), r, max_attempts=2)
        for r in (ok, bad)
    )
    return merge_source_results(
        number, (ok, bad), AggregationPolicy(source_order=("a", "b")), elapsed_ms=42.0, execution_traces=traces
    )


def published(number: str = N, *, partial: bool, index: int = 0, **fields) -> PublicationRecord:
    return prepare_publication(make_plan(number, index=index), make_aggregate(number, partial=partial, **fields))


def parse(xml_text: str) -> ET.Element:
    """Parse through the declared encoding (UTF-8), as a file reader would."""
    return ET.fromstring(xml_text.encode("utf-8", errors="strict"))


def child_texts(root: ET.Element, tag: str) -> list[str | None]:
    return [el.text for el in root.findall(tag)]


def actors_of(root: ET.Element) -> list[tuple[str | None, str | None]]:
    return [(a.findtext("name"), a.findtext("order")) for a in root.findall("actor")]
