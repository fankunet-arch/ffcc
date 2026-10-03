"""P4-C9 contract sections 8.1 / 8.3 / 23 / 28.1: the S1 public API, constants and enum snapshots."""

from __future__ import annotations

import enum
import inspect

import fc2_organizer.diagnostics as diagnostics
import fc2_organizer.diagnostics.models as models
from fc2_metadata_core.aggregation import AggregateStatus
from fc2_metadata_core.aggregation import policy as aggregation_policy
from fc2_organizer.orchestration import MAX_BATCH_ITEMS

_S1_ALL = [
    "DiagnosticsKind", "ResultShape", "PathPolicy", "TimingPolicy",
    "BatchDiagnostics", "MetadataBatchCounts", "ItemDiagnostics", "IssueDiagnostics", "MetadataDiagnostics",
    "SourceDiagnostics", "SourceAttemptDiagnostics", "FieldProvenance", "FieldConflictDiagnostics",
    "ImageFailureGroup", "PreflightDiagnostics", "ExecutionDiagnostics", "LeftoverTemporaryDiagnostics",
    "DIAGNOSTICS_SCHEMA", "DIAGNOSTICS_SCHEMA_VERSION", "PROVENANCE_FIELD_ORDER", "MAX_DIAGNOSTIC_ITEMS",
    "MAX_SOURCES_PER_ITEM", "MAX_ATTEMPTS_PER_SOURCE", "MAX_BLOCKERS_PER_ITEM", "MAX_CONFLICTS_PER_ITEM",
    "MAX_LEFTOVER_TEMPORARIES_PER_ITEM", "MAX_PATH_TEXT_CHARS", "MAX_TIMING_MS", "MAX_DIAGNOSTIC_OUTPUT_BYTES",
    "DiagnosticsError", "DiagnosticsInputError", "DiagnosticsIntegrityError", "DiagnosticsContractError",
    "DiagnosticsResourceLimitError", "DiagnosticsUnsafeValueError", "DiagnosticsSerializationError",
]


def test_s1_all_is_exactly_the_contract_section_8_1_s1_set_in_order():
    assert diagnostics.__all__ == _S1_ALL
    assert len(set(diagnostics.__all__)) == len(diagnostics.__all__)


def test_every_exported_name_resolves():
    for name in diagnostics.__all__:
        assert hasattr(diagnostics, name), name


def test_builder_and_renderer_names_do_not_exist_in_s1():
    for name in ("build_preview_diagnostics", "build_execution_diagnostics", "render_diagnostics_json"):
        assert name not in diagnostics.__all__
        assert not hasattr(diagnostics, name), name


def test_public_constants_have_the_frozen_values():
    assert diagnostics.DIAGNOSTICS_SCHEMA == "fc2_organizer.diagnostics"
    assert diagnostics.DIAGNOSTICS_SCHEMA_VERSION == "1.0"
    assert diagnostics.MAX_SOURCES_PER_ITEM == 64
    assert diagnostics.MAX_ATTEMPTS_PER_SOURCE == 8
    assert diagnostics.MAX_BLOCKERS_PER_ITEM == 256
    assert diagnostics.MAX_CONFLICTS_PER_ITEM == 256
    assert diagnostics.MAX_LEFTOVER_TEMPORARIES_PER_ITEM == 256
    assert diagnostics.MAX_PATH_TEXT_CHARS == 255
    assert diagnostics.MAX_TIMING_MS == 604800000
    assert diagnostics.MAX_DIAGNOSTIC_OUTPUT_BYTES == 67108864


def test_max_diagnostic_items_is_inherited_not_restated():
    assert diagnostics.MAX_DIAGNOSTIC_ITEMS == MAX_BATCH_ITEMS == 2000


def test_provenance_field_order_equals_the_phase_3_field_order():
    assert diagnostics.PROVENANCE_FIELD_ORDER == aggregation_policy.FIELD_ORDER
    assert diagnostics.PROVENANCE_FIELD_ORDER == (
        "number", "title", "studio", "publisher", "release", "runtime", "plot", "actors", "tags", "poster_urls",
        "thumb_urls", "fanart_urls", "extrafanart", "source_urls", "external_ids")
    assert type(diagnostics.PROVENANCE_FIELD_ORDER) is tuple


# ----- internal constants (Design-R3 / Design-R4)


def test_max_provenance_keys_is_64_and_covers_every_known_field():
    assert models.MAX_PROVENANCE_KEYS == 64
    assert models.MAX_PROVENANCE_KEYS >= len(diagnostics.PROVENANCE_FIELD_ORDER)
    assert type(models.MAX_PROVENANCE_KEYS) is int


def test_max_provenance_keys_is_not_in_any_stage_all():
    assert "MAX_PROVENANCE_KEYS" not in diagnostics.__all__
    assert "MAX_PROVENANCE_KEYS" not in models.__all__
    assert not hasattr(diagnostics, "MAX_PROVENANCE_KEYS")


def test_max_timing_seconds_is_derived_from_max_timing_ms():
    assert models.MAX_TIMING_SECONDS == 604800
    assert models.MAX_TIMING_SECONDS == models.MAX_TIMING_MS // 1000
    assert models.MAX_TIMING_MS % 1000 == 0
    assert type(models.MAX_TIMING_SECONDS) is int


def test_max_timing_seconds_is_not_in_any_stage_all():
    assert "MAX_TIMING_SECONDS" not in diagnostics.__all__
    assert "MAX_TIMING_SECONDS" not in models.__all__
    assert not hasattr(diagnostics, "MAX_TIMING_SECONDS")


def test_timing_gate_float_constants_are_exactly_representable():
    # contract section 9.12: float(MAX_TIMING_MS + 1) and float(MAX_TIMING_SECONDS) are exact binary64 values
    assert float(models.MAX_TIMING_MS + 1) == 604800001.0
    assert float(models.MAX_TIMING_SECONDS) == 604800.0
    assert int(float(models.MAX_TIMING_MS + 1)) == models.MAX_TIMING_MS + 1
    assert float(models.MAX_TIMING_SECONDS) * 1000 == float(models.MAX_TIMING_MS)


# ----- the four new enums


def _members(enum_type: type[enum.Enum]) -> list[tuple[str, str]]:
    return [(m.name, m.value) for m in enum_type]


def test_the_four_new_enums_have_the_frozen_members_and_order():
    assert _members(diagnostics.DiagnosticsKind) == [("PREVIEW", "preview"), ("EXECUTION", "execution")]
    assert _members(diagnostics.ResultShape) == [("MAIN", "main"), ("RETRY", "retry"), ("MERGED", "merged")]
    assert _members(diagnostics.PathPolicy) == [("NONE", "none"), ("BASENAME", "basename")]
    assert _members(diagnostics.TimingPolicy) == [("OMIT", "omit"), ("INCLUDE", "include")]


# ----- reused upstream enum value snapshots (contract section 23: an upstream change forces a schema review)

_SNAPSHOTS = {
    "OrchestrationStage": ["number_recognition", "batch_conflict", "metadata", "planning", "publication", "nfo_render",
                           "image_acquisition", "manifest", "preflight", "execution"],
    "IssueReason": ["number_not_recognized", "duplicate_source_in_batch", "duplicate_target_in_batch",
                    "metadata_unavailable", "metadata_engine_failure", "planning_rejected", "publication_rejected",
                    "nfo_render_failed", "image_acquisition_error", "manifest_rejected", "preflight_blocked",
                    "preflight_rejected", "checkpoint_rejected", "execution_failed", "execution_partial",
                    "execution_rejected", "execution_aborted"],
    "ItemWarning": ["metadata_partial", "poster_absent", "fanart_absent", "thumb_absent", "no_extrafanart",
                    "image_candidate_failures", "leftover_temporaries"],
    "PreviewState": ["ready", "blocked", "unprepared"],
    "ExecutionDisposition": ["executed", "not_ready", "not_selected", "cancelled", "rejected", "aborted"],
    "RetryKind": ["metadata_refetch", "preflight_recheck", "fresh_reexecute", "resume", "deferred", "none"],
    "BatchOutcome": ["success", "partial", "failed"],
    "BatchItemStatus": ["success", "partial", "failed"],
    "BatchItemErrorKind": ["engine_exception", "result_contract_mismatch"],
    "AggregateStatus": ["success", "partial", "failed"],
    "SourceStatus": ["success", "not_found", "blocked", "rate_limited", "network_error", "parse_error",
                     "invalid_response"],
    "SourceErrorKind": ["not_found", "blocked", "rate_limited", "network_error", "parse_error", "invalid_response",
                        "timeout", "connection_error", "decode_error", "redirect_error", "source_deadline",
                        "circuit_open", "http_server_error", "response_too_large", "adapter_exception",
                        "result_contract_mismatch"],
    "ImageRole": ["poster", "fanart", "thumb", "extrafanart"],
    "ImageFailureKind": ["invalid_url", "unsafe_url", "candidate_limit", "timeout", "connection_error",
                         "redirect_limit", "transport_error", "http_status", "too_large", "total_bytes_limit",
                         "content_type_mismatch", "invalid_jpeg", "invalid_dimensions"],
    "PreflightMode": ["fresh", "resume"],
    "TransferMode": ["same_volume", "cross_volume"],
    "ExecutionStatus": ["success", "partial", "failed"],
    "ExecutionStep": ["create_directory", "move_media", "materialize_nfo", "materialize_poster",
                      "materialize_fanart", "materialize_thumb", "ensure_extrafanart_directory",
                      "materialize_extrafanart"],
    "EffectKind": ["target_directory_created", "media_published", "source_removed", "artifact_published",
                   "extrafanart_directory_created"],
    "ArtifactKind": ["nfo", "poster", "fanart", "thumb", "extrafanart"],
    "PathRole": ["library_root", "source", "target_directory", "target_media", "nfo", "poster", "fanart", "thumb",
                 "extrafanart_directory", "extrafanart_file"],
}


def _reused_enums() -> dict[str, type[enum.Enum]]:
    found = {}
    for name in _SNAPSHOTS:
        for module in (models,):
            candidate = getattr(module, name, None)
            if inspect.isclass(candidate) and issubclass(candidate, enum.Enum):
                found[name] = candidate
    return found


def test_reused_upstream_enums_have_the_frozen_value_sets():
    reused = _reused_enums()
    assert set(reused) == set(_SNAPSHOTS)
    for name, values in _SNAPSHOTS.items():
        assert [m.value for m in reused[name]] == values, name


def test_the_aggregate_status_used_by_the_models_is_the_phase_3_enum():
    assert models.AggregateStatus is AggregateStatus


# ----- local frozen tables (contract 9.8): equality with the upstream (private) tables


def test_t1_issue_table_equals_the_p4_c8_table():
    from fc2_organizer.orchestration import models as orchestration_models

    assert dict(models.ISSUE_TABLE) == orchestration_models._ISSUE_TABLE
    assert len(models.ISSUE_TABLE) == len(orchestration_models._ISSUE_TABLE)
    assert type(models.ISSUE_TABLE) is tuple


def test_t2_allowed_error_kinds_equal_the_phase_3_table():
    from fc2_metadata_core.models import source_result

    assert dict(models.ALLOWED_ERROR_KINDS) == dict(source_result.ALLOWED_ERROR_KINDS)
    assert type(models.ALLOWED_ERROR_KINDS) is tuple


def test_t3_artifact_role_equals_the_p4_c7_table():
    from fc2_organizer.execution import models as execution_models

    assert dict(models.ARTIFACT_ROLE) == execution_models._ARTIFACT_ROLE
    assert type(models.ARTIFACT_ROLE) is tuple


def test_t4_blocked_and_duplicate_reasons_equal_the_p4_c8_sets():
    from fc2_organizer.orchestration import models as orchestration_models

    assert models.BLOCKED_REASONS == orchestration_models._BLOCKED_REASONS
    assert models.DUPLICATE_REASONS == orchestration_models._DUPLICATE_REASONS


def test_detail_type_name_table_is_the_frozen_section_11_4_set():
    assert {cls.__name__: name for cls, name in models.DETAIL_TYPE_NAMES} == {
        "BatchItemErrorKind": "BatchItemErrorKind", "MappingRejectionReason": "MappingRejectionReason",
        "PlanGraphRejectionReason": "PlanGraphRejectionReason", "ManifestRejectionReason": "ManifestRejectionReason",
        "CheckpointRejectionReason": "CheckpointRejectionReason", "ExecutionFailureKind": "ExecutionFailureKind",
        "PreflightIntegrityReason": "PreflightIntegrityReason"}
    assert len(models.DETAIL_TYPE_NAMES) == 7


def test_detail_types_allowed_by_t1_are_all_in_the_name_table():
    for _reason, (_stage, _needs_error_type, detail_types, _needs_detail) in models.ISSUE_TABLE:
        for detail_type in detail_types:
            assert models.detail_type_name(detail_type) is not None


def test_safe_text_patterns_are_compiled_module_constants():
    import re

    for name in ("SAFE_ID_PATTERN", "LEFTOVER_NAME_PATTERN", "BASENAME_ALLOWED_CHARS"):
        assert isinstance(getattr(models, name), re.Pattern), name


def test_table_lookup_helpers_agree_with_the_tables_and_are_total_on_their_domain():
    for reason, rule in models.ISSUE_TABLE:
        assert models.issue_rule(reason) == rule
    for status in models.SourceStatus:
        expected = dict(models.ALLOWED_ERROR_KINDS).get(status, frozenset())
        assert models.allowed_error_kinds(status) == expected
    assert models.allowed_error_kinds(models.SourceStatus.SUCCESS) == frozenset()
    for kind, role in models.ARTIFACT_ROLE:
        assert models.artifact_role(kind) is role
    assert models.detail_type_name(int) is None


def test_no_module_level_mutable_container_is_defined_by_models():
    """contract section 21.1: module state holds only immutable constants (no dict / list / set)."""
    for name, value in vars(models).items():
        if name.startswith("__"):
            continue
        assert type(value) not in (dict, list, set, bytearray), name
