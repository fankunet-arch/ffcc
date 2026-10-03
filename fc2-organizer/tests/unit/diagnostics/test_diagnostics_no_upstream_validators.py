"""P4-C9 contract sections 9.1 / 9.5 and 28.1 "no upstream validator": the builders never call an upstream
``__post_init__``, a public instance method / property outside the five approved properties, or ``gc.get_referents``.
Every such callable of every consumed upstream class is replaced by a trip-wire *after* the input graph was built;
a legal input must still build, with the trip-wire counter at zero."""

from __future__ import annotations

import gc

import pytest
from fc2_metadata_core.aggregation import AggregationResult, FieldConflict, SourceAttempt, SourceExecutionTrace
from fc2_metadata_core.batch import BatchItemResult, BatchLineage, BatchResult
from fc2_metadata_core.models import NormalizedMetadata, SourceResult
from fc2_organizer.discovery import DiscoveredMediaItem
from fc2_organizer.execution import (
    CompletedEffect,
    ExecutionFailure,
    ExecutionPreflight,
    ExecutionResult,
    LeftoverTemporary,
    PreflightBlocker,
)
from fc2_organizer.images import ImageCandidateFailure
from fc2_organizer.materialization import ArtifactWriteRequest
from fc2_organizer.orchestration import (
    BatchExecutionResult,
    BatchPreview,
    ItemExecution,
    ItemIssue,
    ItemPreview,
    RetryMaterial,
)
from fc2_organizer.planning import OrganizePlan, PlannedOperation, PlannedPath

from . import _builders as b
from . import _builders as h

CLASSES = [
    BatchPreview, BatchExecutionResult, ItemPreview, ItemExecution, ItemIssue, DiscoveredMediaItem, OrganizePlan,
    PlannedPath, PlannedOperation, BatchResult, BatchItemResult, BatchLineage, AggregationResult, SourceResult,
    SourceExecutionTrace, SourceAttempt, NormalizedMetadata, FieldConflict, ImageCandidateFailure,
    ExecutionPreflight, ArtifactWriteRequest, PreflightBlocker, ExecutionResult, CompletedEffect, ExecutionFailure,
    LeftoverTemporary, RetryMaterial,
]
APPROVED = {(BatchPreview, "summary"), (BatchExecutionResult, "summary"), (BatchExecutionResult, "outcome"),
            (ItemPreview, "warnings"), (ItemExecution, "retry_kind")}


def patchable(cls):
    """(name, attribute) of every ``__post_init__`` / public method / public property declared on ``cls``."""
    for name, attr in sorted(vars(cls).items()):
        if (cls, name) in APPROVED:
            continue
        if name == "__post_init__" or (not name.startswith("_") and (callable(attr) or isinstance(attr, property))):
            yield name, attr


def arm(monkeypatch):
    """Replace every patchable upstream callable by a trip-wire; returns the call log and the patched labels."""
    calls = []

    def boom(label):
        def fire(*args, **kwargs):
            calls.append(label)
            raise AssertionError("upstream callable ran: %s" % label)
        return fire

    patched = []
    for cls in CLASSES:
        for name, attr in patchable(cls):
            label = "%s.%s" % (cls.__name__, name)
            monkeypatch.setattr(cls, name, property(boom(label)) if isinstance(attr, property) else boom(label))
            patched.append(label)
    monkeypatch.setattr(gc, "get_referents", boom("gc.get_referents"))
    return calls, patched


@pytest.mark.parametrize("kind", ["preview", "execution"])
def test_a_legal_input_builds_with_every_upstream_validator_and_method_tripwired(kind, monkeypatch):
    graph = h.FACTORY[kind]()  # constructed first: the upstream constructors run their own validators
    reference = h.BUILD[kind](graph)
    calls, patched = arm(monkeypatch)
    assert len(patched) > 60
    out = h.BUILD[kind](graph)
    assert calls == []
    assert out == reference


def test_the_tripwire_is_not_vacuous_it_fires_when_an_upstream_validator_is_called(monkeypatch):
    graph = h.preview_graph()
    calls, _ = arm(monkeypatch)
    with pytest.raises(AssertionError):
        graph.items[0].plan.__post_init__()
    with pytest.raises(AssertionError):
        graph.metadata_batch.items[0].aggregation_result.metadata.meets_minimum_success()
    with pytest.raises(AssertionError):
        gc.get_referents(graph)
    assert calls == ["OrganizePlan.__post_init__", "NormalizedMetadata.meets_minimum_success", "gc.get_referents"]


def test_the_tripwire_covers_the_expected_surface():
    names = {"%s.%s" % (cls.__name__, name) for cls in CLASSES for name, _ in patchable(cls)}
    for expected in ("NormalizedMetadata.meets_minimum_success", "AggregationResult.result_for",
                     "AggregationResult.trace_for", "OrganizePlan.__post_init__", "BatchPreview.__post_init__",
                     "BatchExecutionResult.retained_retry_payload_bytes", "BatchPreview.retained_artifact_bytes"):
        assert expected in names, expected
