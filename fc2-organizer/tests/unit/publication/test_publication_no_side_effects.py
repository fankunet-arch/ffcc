"""P4-C3: no diagnostics leak into a ``PublicationRecord``; ``prepare_publication``
touches neither the filesystem nor the network (contract section 7, 11-12;
test matrix 12-15, 18-19).

The leak test walks the record's **actual object graph** (dataclass/slot
attributes, instance ``__dict__``, tuples, mappings) -- not field names -- and
asserts that none of the forbidden object types is reachable, and that no
string anywhere in it contains the ``error_detail`` text the input carried.
"""

from __future__ import annotations

import os
import socket

import pytest

from fc2_metadata_core.aggregation import AggregationResult, SourceAttempt, SourceExecutionTrace
from fc2_metadata_core.models import SourceResult
from fc2_organizer.publication import PublicationError, PublicationRecord, prepare_publication

from ._builders import SECRET_MARKER, make_aggregate, make_plan
from ._guards import FORBIDDEN_ATTRIBUTE_NAMES, FORBIDDEN_TYPES, SideEffectAttempted, trap, install_traps, walk

N = "FC2-1234567"


@pytest.fixture(params=["success", "partial", "partial_retry"])
def published(request):
    aggregate = make_aggregate(N, kind=request.param)
    # the input really does carry diagnostics -- otherwise the checks below would be vacuous
    assert aggregate.source_execution_traces and any(r.error_detail for r in aggregate.source_results)
    return aggregate, prepare_publication(make_plan(N), aggregate)


def test_walker_is_not_vacuous_it_finds_diagnostics_in_the_raw_aggregate():
    graph = walk(make_aggregate(N, kind="partial_retry"))
    kinds = {type(obj) for _, obj in graph}
    assert {AggregationResult, SourceResult, SourceExecutionTrace, SourceAttempt} <= kinds
    assert any(isinstance(obj, str) and SECRET_MARKER in obj for _, obj in graph)


def test_record_graph_holds_no_aggregation_result_source_result_trace_attempt_or_exception(published):
    _, rec = published
    for path, obj in walk(rec):
        assert not isinstance(obj, FORBIDDEN_TYPES), f"{path} is a forbidden {type(obj).__name__}"


def test_record_graph_holds_no_error_detail_text_or_diagnostic_attribute(published):
    aggregate, rec = published
    details = [r.error_detail for r in aggregate.source_results if r.error_detail]
    for path, obj in walk(rec):
        leaf = path.rsplit(".", 1)[-1]
        assert leaf not in FORBIDDEN_ATTRIBUTE_NAMES, f"diagnostic attribute reachable at {path}"
        if isinstance(obj, str):
            assert SECRET_MARKER not in obj and not any(d in obj for d in details), f"error_detail text at {path}"


def test_record_does_not_reference_the_input_aggregate_object(published):
    aggregate, rec = published
    ids = {id(obj) for _, obj in walk(rec)}
    assert id(aggregate) not in ids
    assert not any(id(r) in ids for r in aggregate.source_results)
    assert not any(id(t) in ids for t in aggregate.source_execution_traces)


# ---- 18, 19: zero filesystem, zero network -------------------------------------------------------------------------------


def testtraps_are_effective(monkeypatch, tmp_path):
    target = tmp_path / "x"
    install_traps(monkeypatch)
    with pytest.raises(SideEffectAttempted):
        os.stat(str(target))
    with pytest.raises(SideEffectAttempted):
        target.exists()
    with pytest.raises(SideEffectAttempted):
        open(str(target), "rb")
    with pytest.raises(SideEffectAttempted):
        socket.create_connection(("127.0.0.1", 9))


@pytest.mark.parametrize("kind", ["success", "partial", "partial_retry"])
def test_prepare_publication_runs_with_every_filesystem_and_network_apitrapped(monkeypatch, kind):
    plan, aggregate = make_plan(N), make_aggregate(N, kind=kind)
    install_traps(monkeypatch)
    rec = prepare_publication(plan, aggregate)
    assert isinstance(rec, PublicationRecord)


def test_rejections_also_run_with_every_filesystem_and_network_apitrapped(monkeypatch):
    plan, bad = make_plan(N), make_aggregate("FC2-7654321")
    failed = make_aggregate(N, kind="failed")
    install_traps(monkeypatch)
    for aggregate in (bad, failed):
        with pytest.raises(PublicationError):
            prepare_publication(plan, aggregate)


def test_prepare_publication_leaves_the_filesystem_unchanged(tmp_path):
    watched = tmp_path / "watched"
    watched.mkdir()
    (watched / "a.txt").write_text("unchanged", encoding="utf-8")
    before = sorted((str(p), p.read_bytes() if p.is_file() else b"") for p in watched.rglob("*"))
    library = tmp_path / "library"
    for i in range(5):
        prepare_publication(make_plan(f"FC2-{1000000 + i}", index=i), make_aggregate(f"FC2-{1000000 + i}"))
    after = sorted((str(p), p.read_bytes() if p.is_file() else b"") for p in watched.rglob("*"))
    assert before == after
    assert not library.exists()


# ---- determinism (no clock / random / uuid) ------------------------------------------------------------------------------


def test_prepare_publication_uses_no_clock_random_or_uuid(monkeypatch):
    import random
    import time
    import uuid

    plan, aggregate = make_plan(N), make_aggregate(N, kind="partial")
    for module, names in (
        (time, ["time", "monotonic", "perf_counter", "time_ns", "monotonic_ns"]),
        (random, ["random", "randint", "choice", "shuffle", "getrandbits"]),
        (uuid, ["uuid1", "uuid4"]),
        (os, ["urandom"]),
    ):
        for name in names:
            monkeypatch.setattr(module, name, trap(f"{module.__name__}.{name}"))
    assert prepare_publication(plan, aggregate) == prepare_publication(plan, aggregate)
