"""P4-C8 S4: lineage retention (contract sections 10.7, 19.6.7, 19.6.10, 26 steps 9a / 9b, 35 "result retention"
rows C-I, 35.1.1 multi-generation scenario g0-g4).

The g0-g4 scenario runs on the real stack (``M = K = W = 1``, ``R = I``) with exact byte values derived from a
calibration preview of the same films: ``L`` is the (ASCII) NFO length, ``I`` the image bytes of every item,
``pay = L + I``, ``need = 4 * L + I`` and ``B = 4 * pay + need``. Model-level rows use hand-built, model-valid
results (``Lineage`` builders) so exact boundaries such as "merged retention == B" are reachable.
"""

from __future__ import annotations

import os

import pytest

from fc2_metadata_core.batch import BatchConfig
from fc2_organizer.execution import ExecutionStatus
from fc2_organizer.images import ImageAcquisitionPolicy
from fc2_organizer.materialization import ArtifactKind
from fc2_organizer.orchestration import (
    ExecutionDisposition as D,
    OrchestrationConfig,
    OrchestrationConsumedError,
    OrchestrationInputError,
    OrchestrationIntegrityError,
    OrchestrationResourceLimitError,
    OrchestrationRetryError,
    ResourceLimitReason,
    RetryKind as K,
    merge_retry,
)
from fc2_organizer.orchestration import _consumption

from ._fakes import jpeg_response, minimal_jpeg
from ._helpers import Corpus, Film, Lineage, image_url, manifest_for, payload, run, tampered

D_NAMES = [f"FC2-PPV-{1000001 + i}.mp4" for i in range(4)]
M_NAMES = [f"FC2-PPV-{2000001 + i}.mp4" for i in range(4)]
M_NUMBERS = [f"FC2-{2000001 + i}" for i in range(4)]
PAD = 40_000


def _films(metadata_kind: str) -> list[Film]:
    films = [Film(name, poster=True, fanart=False, thumb=False) for name in D_NAMES]
    films += [Film(name, kind=metadata_kind, poster=True, fanart=False, thumb=False) for name in M_NAMES]
    return films


def _padded(corpus: Corpus) -> int:
    """Every poster becomes a JPEG of the same length (seeds differ); returns that length."""
    sizes = set()
    for seed, name in enumerate(D_NAMES + M_NAMES, start=1):
        number = "FC2-" + name.split("-")[2].split(".")[0]
        content = minimal_jpeg(seed=seed, pad=PAD)
        sizes.add(len(content))
        corpus.client.script[image_url(number, "poster")] = jpeg_response(content)
    assert len(sizes) == 1
    return sizes.pop()


def _calibrate(tmp_path) -> tuple[int, int]:
    corpus = Corpus(tmp_path / "calibration", _films("success"))
    image = _padded(corpus)
    preview = run(corpus.orchestrator().preview(corpus.items))
    nfo_lengths, image_lengths = set(), set()
    for item in preview.items:
        for request in item.preflight.artifacts:
            if request.kind is ArtifactKind.NFO:
                request.content.decode("ascii")  # pure ASCII: 4 * len(text) == 4 * len(bytes)
                nfo_lengths.add(len(request.content))
            else:
                image_lengths.add(len(request.content))
    assert len(nfo_lengths) == 1 and image_lengths == {image}
    nfo = nfo_lengths.pop()
    assert image > 2 * nfo and image >= 8 * nfo  # detectable (I > 2L); the main preview admits all four D
    return nfo, image


class _Scenario:
    def __init__(self, tmp_path, *, budget_delta: int = 0) -> None:
        self.L, self.I = _calibrate(tmp_path)
        self.pay = self.L + self.I
        self.need = 4 * self.L + self.I
        self.payD = 4 * self.pay
        self.B = self.payD + self.need + budget_delta
        self.corpus = Corpus(tmp_path / "lineage", _films("failed"))
        _padded(self.corpus)
        policy = ImageAcquisitionPolicy(max_image_bytes=self.I, max_total_bytes=self.I)
        config = OrchestrationConfig(metadata=BatchConfig(max_in_flight_items=1), image_in_flight_items=1,
                                     filesystem_workers=1, max_retained_artifact_bytes=self.B)
        self.orchestrator = self.corpus.orchestrator(image_policy=policy, config=config)
        self.preview = run(self.orchestrator.preview(self.corpus.items))
        self.index = {os.path.basename(i.source_path): i.index for i in self.preview.items}

    def succeed(self, number: str) -> None:
        self.corpus.engine.script[number] = "success"

    def retry(self, previous, *kinds):
        return run(self.orchestrator.preview_retry(previous, scope=frozenset(kinds)))

    def m(self, k: int) -> int:
        return self.index[M_NAMES[k]]


def test_multi_generation_retention_g0_to_g4_matches_the_frozen_scenario(tmp_path):
    s = _Scenario(tmp_path)
    B = s.B
    # g0: D1-D4 DEFERRED, M1-M4 metadata FAILED
    g0 = s.orchestrator.execute(s.preview, selection=())
    assert g0.retained_retry_payload_bytes == s.payD <= B
    assert [g0.items[s.index[n]].retry_kind for n in D_NAMES] == [K.DEFERRED] * 4
    assert [g0.items[s.m(k)].retry_kind for k in range(4)] == [K.METADATA_REFETCH] * 4
    # g1: only M1 recovers; available == need(M): exactly admitted (boundary D)
    s.succeed(M_NUMBERS[0])
    retry1 = s.retry(g0, K.METADATA_REFETCH)
    assert retry1.retry_budget_bytes == B - s.payD == s.need
    assert retry1.retained_artifact_bytes == s.pay
    g1 = merge_retry(g0, s.orchestrator.execute(retry1, selection=()))
    assert g1.generation == 1 and g1.retained_retry_payload_bytes == s.payD + s.pay <= B
    # g2 (failed attempt): M2 would recover, but available == need - pay < need
    s.succeed(M_NUMBERS[1])
    with pytest.raises(OrchestrationResourceLimitError) as info:
        s.retry(g1, K.METADATA_REFETCH)
    assert info.value.reason is ResourceLimitReason.RETAINED_BYTES_LIMIT
    assert not _consumption.RESULT_RETRIES.is_registered(g1.result_id)  # g1 stays retryable
    # g2: change the scope -- settle M1, D1-D4 stay NOT_SELECTED
    retry2 = s.retry(g1, K.DEFERRED)
    assert retry2.retry_budget_bytes == B and retry2.generation == 2
    round2 = s.orchestrator.execute(retry2, selection=(s.m(0),))
    assert round2.items[[i.index for i in round2.items].index(s.m(0))].execution_status is ExecutionStatus.SUCCESS
    g2 = merge_retry(g1, round2)
    assert g2.retained_retry_payload_bytes == s.payD
    # g3: M2 recovers; available == need(M) again: exactly admitted
    retry3 = s.retry(g2, K.METADATA_REFETCH)
    assert retry3.retry_budget_bytes == s.need and retry3.generation == 3
    g3 = merge_retry(g2, s.orchestrator.execute(retry3, selection=()))
    assert g3.retained_retry_payload_bytes == s.payD + s.pay <= B
    # g4: everything READY executes; nothing is retained any more
    retry4 = s.retry(g3, K.DEFERRED)
    assert sorted(i.index for i in retry4.items) == sorted([s.index[n] for n in D_NAMES] + [s.m(1)])
    g4 = merge_retry(g3, s.orchestrator.execute(retry4))
    assert g4.generation == 4 and g4.retained_retry_payload_bytes == 0
    succeeded = [i.index for i in g4.items if i.execution_status is ExecutionStatus.SUCCESS]
    assert sorted(succeeded) == sorted([s.index[n] for n in D_NAMES] + [s.m(0), s.m(1)])
    assert [g4.items[s.m(k)].retry_kind for k in (2, 3)] == [K.METADATA_REFETCH] * 2
    for result in (g0, g1, g2, g3, g4):  # every current complete result stays <= B, same lineage and B
        assert result.retention_budget_bytes == B and result.lineage == g0.lineage
        assert result.retained_retry_payload_bytes <= B


def test_available_plus_one_fails_without_registration_and_a_narrower_scope_proceeds(tmp_path):
    """Rows E / F: the first retry needs exactly one byte more than is available."""
    s = _Scenario(tmp_path, budget_delta=-1)
    g0 = s.orchestrator.execute(s.preview, selection=())
    s.succeed(M_NUMBERS[0])
    with pytest.raises(OrchestrationResourceLimitError) as info:
        s.retry(g0, K.METADATA_REFETCH)
    assert info.value.reason is ResourceLimitReason.RETAINED_BYTES_LIMIT
    assert not _consumption.RESULT_RETRIES.is_registered(g0.result_id)
    retry = s.retry(g0, K.DEFERRED)  # a narrower scope proceeds (base_retained 0, available B)
    assert retry.retry_budget_bytes == s.B and retry.retained_artifact_bytes == s.payD


def test_a_larger_budget_orchestrator_cannot_bypass_the_lineage_budget(tmp_path):
    """Row I: the lineage B is fixed; execute / preview_retry on another budget are input errors."""
    s = _Scenario(tmp_path)
    g0 = s.orchestrator.execute(s.preview, selection=())
    bigger = s.corpus.orchestrator(
        image_policy=s.orchestrator.image_policy,
        config=OrchestrationConfig(metadata=BatchConfig(max_in_flight_items=1), image_in_flight_items=1,
                                   filesystem_workers=1, max_retained_artifact_bytes=s.B * 2))
    s.succeed(M_NUMBERS[0])
    calls = len(s.corpus.engine.calls)
    with pytest.raises(OrchestrationInputError):
        run(bigger.preview_retry(g0))
    assert len(s.corpus.engine.calls) == calls and not _consumption.RESULT_RETRIES.is_registered(g0.result_id)
    retry = s.retry(g0, K.DEFERRED)
    with pytest.raises(OrchestrationInputError):
        bigger.execute(retry)


# --------------------------------------------------------------------------- model-level rows (C, G, H, I)


def _retention_lineage(extra: int = 0):
    """previous (main): index 0 FAILED (FRESH_REEXECUTE, material a), 1 NOT_SELECTED (DEFERRED, material b),
    2 SUCCESS; B == a + b exactly. The retry round (scope DEFERRED) re-defers index 1 with ``b + extra``."""
    lin = Lineage(3)
    small = manifest_for(lin.plans[0], poster=b"p" * 5, fanart=None, thumb=None)
    large = manifest_for(lin.plans[1], poster=b"q" * 50, fanart=b"r" * 60, thumb=None)
    budget = payload(small) + payload(large)
    items = [lin.execution_item(0, D.EXECUTED, status=ExecutionStatus.FAILED, material=True, artifacts=small),
             lin.execution_item(1, D.NOT_SELECTED, material=True, artifacts=large),
             lin.execution_item(2, D.EXECUTED, status=ExecutionStatus.SUCCESS)]
    previous = lin.result(items, budget=budget)
    again = large if extra == 0 else manifest_for(lin.plans[1], poster=b"q" * (50 + extra), fanart=b"r" * 60,
                                                  thumb=None)
    retry_item = lin.execution_item(1, D.NOT_SELECTED, material=True, artifacts=again, generation=1)
    return lin, previous, retry_item, budget, payload(small)


def test_merged_retention_exactly_b_is_accepted_and_copies_no_payload():
    """Rows A / G: retained == B is legal for a complete result; the merge composes references only."""
    lin, previous, retry_item, budget, base = _retention_lineage()
    assert previous.retained_retry_payload_bytes == budget
    retry = lin.result([retry_item], generation=1, base_result_id=previous.result_id,
                       retry_scope=frozenset({K.DEFERRED}), budget=budget, retry_budget=budget - base)
    merged = merge_retry(previous, retry)
    assert merged.retained_retry_payload_bytes == budget == merged.retention_budget_bytes
    assert merged.retry_budget_bytes is None and merged.items[1] is retry_item
    assert merged.items[0] is previous.items[0] and merged.items[2] is previous.items[2]
    assert merged.items[0].retry_material is previous.items[0].retry_material
    assert merged.items[0].retry_material.artifacts is previous.items[0].retry_material.artifacts
    assert merged.items[1].retry_material.artifacts is retry_item.retry_material.artifacts


def test_tampered_retry_budget_or_payload_fails_closed_before_registration():
    """Row H: 9a (budget) / 9b (merged payload > B) reject without registering; the correct result merges."""
    lin, previous, retry_item, budget, base = _retention_lineage()
    retry = lin.result([retry_item], generation=1, base_result_id=previous.result_id,
                       retry_scope=frozenset({K.DEFERRED}), budget=budget, retry_budget=budget - base)
    with pytest.raises(OrchestrationRetryError):  # 9a: retry_budget_bytes rewritten
        merge_retry(previous, tampered(retry, retry_budget_bytes=budget - base - 1))
    with pytest.raises(OrchestrationRetryError):  # 9a: another lineage budget
        merge_retry(previous, tampered(retry, retention_budget_bytes=budget + 1))
    bigger = lin.execution_item(1, D.NOT_SELECTED, material=True, generation=1,
                                artifacts=manifest_for(lin.plans[1], poster=b"q" * 51, fanart=b"r" * 60, thumb=None))
    with pytest.raises(OrchestrationIntegrityError):  # 9b: merged retention would be B + 1
        merge_retry(previous, tampered(retry, items=(bigger,)))
    assert not _consumption.RETRY_MERGES.is_registered(retry.result_id)
    merged = merge_retry(previous, retry)  # the corrected (original) result still merges
    assert merged.retained_retry_payload_bytes == budget
    with pytest.raises(OrchestrationConsumedError):
        merge_retry(previous, retry)


def test_available_below_zero_is_an_integrity_error(tmp_path):
    """Row I (E0-R2): a previous retaining more than its B can only be tampered."""
    s = _Scenario(tmp_path)
    g0 = s.orchestrator.execute(s.preview, selection=())
    forged = tampered(g0, retention_budget_bytes=s.payD - 1)
    with pytest.raises(OrchestrationIntegrityError):
        run(s.orchestrator.preview_retry(forged))
    assert not _consumption.RESULT_RETRIES.is_registered(g0.result_id)


def test_the_registries_hold_only_id_strings(tmp_path):
    lin, previous, retry_item, budget, base = _retention_lineage()
    retry = lin.result([retry_item], generation=1, base_result_id=previous.result_id,
                       retry_scope=frozenset({K.DEFERRED}), budget=budget, retry_budget=budget - base)
    merge_retry(previous, retry)
    for registry in (_consumption.PREVIEW_EXECUTIONS, _consumption.RESULT_RETRIES, _consumption.RETRY_MERGES):
        assert all(type(value) is str and len(value) == 32 for value in registry._ids)
