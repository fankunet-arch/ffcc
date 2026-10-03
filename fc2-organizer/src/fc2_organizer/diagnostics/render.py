"""``render_diagnostics_json`` (P4-C9 contract sections 22 / 24.4 / 21.3 / 17): the one place where an immutable
``BatchDiagnostics`` becomes bytes.

Order (contract 24.4): (1) exact top-level type, (2) a local re-check of the whole diagnostics graph through the
module-level validators of ``models`` (the graph is frozen but can be rewritten behind its constructors), (3) an
*explicit* conversion to a tree of ``dict`` / ``list`` / ``str`` / ``int`` / ``bool`` / ``None`` in which every
``str`` passes the section 17.2 whitelist for its position, (4) bounded streaming encoding with the fixed
parameters of section 22.1. The function only returns ``bytes``: nothing is opened, written, renamed or logged.

Failure mapping: graph / type problems -> ``DiagnosticsIntegrityError``; a text outside the whitelist ->
``DiagnosticsUnsafeValueError``; more than ``MAX_DIAGNOSTIC_OUTPUT_BYTES`` -> ``DiagnosticsResourceLimitError``;
an encoding-stage ``ValueError`` / ``TypeError`` / ``RecursionError`` / ``OverflowError`` (including the int-to-text
digit limit of Python >= 3.11, contract 9.12 N-15) -> ``DiagnosticsSerializationError``, raised *outside* the
``except`` block so that nothing is chained.
"""

from __future__ import annotations

import json

from fc2_metadata_core.aggregation import CONFLICT_FIELDS
from fc2_metadata_core.normalize import is_valid_fc2_number
from fc2_organizer.diagnostics.errors import (
    DiagnosticsInputError,
    DiagnosticsIntegrityError,
    DiagnosticsResourceLimitError,
    DiagnosticsSerializationError,
    DiagnosticsUnsafeValueError,
)
from fc2_organizer.diagnostics.models import (
    DIAGNOSTICS_SCHEMA,
    DIAGNOSTICS_SCHEMA_VERSION,
    LEFTOVER_NAME_PATTERN,
    MAX_DIAGNOSTIC_OUTPUT_BYTES,
    PROVENANCE_FIELD_ORDER,
    BatchDiagnostics,
    batch_problem,
    detail_type_name,
    is_error_type,
    is_safe_basename,
    is_safe_id,
)

# --------------------------------------------------------------------------- whitelisted text (contract 17.2)


def unsafe() -> None:
    raise DiagnosticsUnsafeValueError("a text value is outside the allowed output whitelist")


def enum_text(member: object) -> object:
    """An enum member -> its ``.value``; ``None`` stays ``None``. The value must be an exact ``str``."""
    if member is None:
        return None
    value = member.value
    if type(value) is not str:
        unsafe()
    return value


def safe_id(value: object) -> str:
    if not is_safe_id(value):
        unsafe()
    return value


def error_type_text(value: object) -> object:
    if value is None:
        return None
    if not is_error_type(value):
        unsafe()
    return value


def field_name(value: object) -> str:
    if type(value) is not str or (value not in PROVENANCE_FIELD_ORDER and value not in CONFLICT_FIELDS):
        unsafe()
    return value


def number_text(value: object) -> object:
    if value is None:
        return None
    if type(value) is not str or not is_valid_fc2_number(value):
        unsafe()
    return value


def during_text(value: object) -> object:
    if value is None:
        return None
    if type(value) is not str or (value != "attempt" and value != "backoff"):
        unsafe()
    return value


def basename_text(value: object) -> object:
    if value is None:
        return None
    if not is_safe_basename(value):
        unsafe()
    return value


def write_stage_text(value: object) -> object:
    if value is None:
        return None
    if type(value) is not str or (value != "write" and value != "flush" and value != "close"):
        unsafe()
    return value


def leftover_text(value: object) -> object:
    if value is None:
        return None
    if type(value) is not str or LEFTOVER_NAME_PATTERN.fullmatch(value) is None:
        unsafe()
    return value


# --------------------------------------------------------------------------- explicit tree conversion (22.2)


def counts_tree(pairs: tuple, name: str) -> list:
    """``((enum, n), ...)`` -> ``[{"<name>": value, "count": n}, ...]``."""
    out = []
    for pair in pairs:
        out.append({name: enum_text(pair[0]), "count": pair[1]})
    return out


def enums_tree(members: tuple) -> list:
    out = []
    for member in members:
        out.append(enum_text(member))
    return out


def ids_tree(values: tuple) -> list:
    out = []
    for value in values:
        out.append(safe_id(value))
    return out


def preview_summary_tree(summary: object) -> object:
    if summary is None:
        return None
    return {"total": summary.total, "ready": summary.ready, "blocked": summary.blocked,
            "unprepared": summary.unprepared, "warned": summary.warned,
            "stage_counts": counts_tree(summary.stage_counts, "stage")}


def execution_summary_tree(summary: object) -> object:
    if summary is None:
        return None
    return {"total": summary.total, "ready": summary.ready, "blocked": summary.blocked,
            "unprepared": summary.unprepared, "executed": summary.executed, "success": summary.success,
            "partial": summary.partial, "failed": summary.failed, "not_selected": summary.not_selected,
            "cancelled": summary.cancelled, "rejected": summary.rejected, "aborted": summary.aborted,
            "retryable": summary.retryable, "deferred": summary.deferred, "non_retryable": summary.non_retryable,
            "stage_counts": counts_tree(summary.stage_counts, "stage")}


def issue_tree(issue: object) -> object:
    if issue is None:
        return None
    detail_type = None
    detail = None
    if issue.detail is not None:
        detail_type = detail_type_name(type(issue.detail))
        if detail_type is None:
            unsafe()
        detail = enum_text(issue.detail)
    return {"stage": enum_text(issue.stage), "reason": enum_text(issue.reason),
            "error_type": error_type_text(issue.error_type), "detail_type": detail_type, "detail": detail}


def attempt_tree(attempt: object) -> dict:
    return {"sequence": attempt.sequence, "status": enum_text(attempt.status),
            "error_kind": enum_text(attempt.error_kind), "completed": attempt.completed,
            "elapsed_ms": attempt.elapsed_ms, "backoff_before_ms": attempt.backoff_before_ms}


def source_tree(source: object) -> dict:
    fields = []
    for name in source.provided_fields:
        fields.append(field_name(name))
    attempts = []
    for attempt in source.attempts:
        attempts.append(attempt_tree(attempt))
    return {"source_id": safe_id(source.source_id), "status": enum_text(source.status),
            "error_kind": enum_text(source.error_kind), "contributed": source.contributed,
            "operational_failure": source.operational_failure, "provided_fields": fields,
            "trace_available": source.trace_available, "attempt_count": source.attempt_count,
            "max_attempts": source.max_attempts, "deadline_exceeded": source.deadline_exceeded,
            "deadline_during": during_text(source.deadline_during), "attempts": attempts}


def metadata_tree(metadata: object) -> object:
    if metadata is None:
        return None
    sources = []
    for source in metadata.sources:
        sources.append(source_tree(source))
    provenance = []
    for entry in metadata.field_provenance:
        provenance.append({"field": field_name(entry.field), "source_ids": ids_tree(entry.source_ids)})
    conflicts = []
    for conflict in metadata.conflicts:
        conflicts.append({"field": field_name(conflict.field),
                          "selected_source_id": safe_id(conflict.selected_source_id),
                          "alternative_source_ids": ids_tree(conflict.alternative_source_ids)})
    return {"status": enum_text(metadata.status), "generation": metadata.generation,
            "error_kind": enum_text(metadata.error_kind), "aggregate_status": enum_text(metadata.aggregate_status),
            "traces_available": metadata.traces_available, "sources": sources,
            "disabled_source_ids": ids_tree(metadata.disabled_source_ids), "field_provenance": provenance,
            "conflicts": conflicts, "elapsed_ms": metadata.elapsed_ms}


def image_failures_tree(groups: tuple) -> list:
    out = []
    for group in groups:
        statuses = []
        for status in group.http_statuses:
            statuses.append(status)
        out.append({"role": enum_text(group.role), "kind": enum_text(group.kind), "count": group.count,
                    "http_statuses": statuses})
    return out


def blocker_tree(blocker: object) -> dict:
    return {"reason": enum_text(blocker.reason), "role": enum_text(blocker.role), "errno": blocker.errno,
            "ordinal": blocker.ordinal}


def failure_tree(failure: object) -> object:
    if failure is None:
        return None
    return {"step": enum_text(failure.step), "kind": enum_text(failure.kind), "stage": enum_text(failure.stage),
            "write_stage": write_stage_text(failure.write_stage), "errno": failure.errno,
            "artifact_kind": enum_text(failure.artifact_kind), "ordinal": failure.ordinal,
            "target_published": failure.target_published}


def preflight_tree(preflight: object) -> object:
    if preflight is None:
        return None
    blockers = []
    for blocker in preflight.blockers:
        blockers.append(blocker_tree(blocker))
    return {"mode": enum_text(preflight.mode), "ready": preflight.ready,
            "transfer_mode": enum_text(preflight.transfer_mode), "blockers": blockers,
            "pending_unit_count": preflight.pending_unit_count,
            "completed_unit_count": preflight.completed_unit_count,
            "skipped_steps": enums_tree(preflight.skipped_steps),
            "artifact_counts": counts_tree(preflight.artifact_counts, "artifact_kind")}


def execution_tree(execution: object) -> object:
    if execution is None:
        return None
    leftovers = []
    for leftover in execution.leftover_temporaries:
        leftovers.append({"directory_role": enum_text(leftover.directory_role),
                          "name": leftover_text(leftover.name)})
    return {"status": enum_text(execution.status), "mode": enum_text(execution.mode),
            "transfer_mode": enum_text(execution.transfer_mode), "new_effect_count": execution.new_effect_count,
            "effect_counts": counts_tree(execution.effect_counts, "effect_kind"),
            "artifact_counts": counts_tree(execution.artifact_counts, "artifact_kind"),
            "failure": failure_tree(execution.failure), "checkpoint_present": execution.checkpoint_present,
            "skipped_steps": enums_tree(execution.skipped_steps),
            "leftover_temporary_count": execution.leftover_temporary_count, "leftover_temporaries": leftovers}


def item_tree(item: object) -> dict:
    conflict_with = []
    for index in item.conflict_with:
        conflict_with.append(index)
    return {"index": item.index, "generation": item.generation,
            "canonical_number": number_text(item.canonical_number),
            "source_name": basename_text(item.source_name), "source_size": item.source_size,
            "target_directory_name": basename_text(item.target_directory_name),
            "target_media_name": basename_text(item.target_media_name),
            "preview_state": enum_text(item.preview_state), "issue": issue_tree(item.issue),
            "warnings": enums_tree(item.warnings), "conflict_with": conflict_with,
            "retry_origin": enum_text(item.retry_origin), "disposition": enum_text(item.disposition),
            "retry_kind": enum_text(item.retry_kind), "retry_material_retained": item.retry_material_retained,
            "metadata": metadata_tree(item.metadata), "image_failures": image_failures_tree(item.image_failures),
            "preflight": preflight_tree(item.preflight), "execution": execution_tree(item.execution)}


def batch_tree(diagnostics: BatchDiagnostics) -> dict:
    scope = None
    if diagnostics.retry_scope is not None:
        scope = enums_tree(diagnostics.retry_scope)
    counts = diagnostics.metadata_batch
    items = []
    for item in diagnostics.items:
        items.append(item_tree(item))
    return {
        "schema": DIAGNOSTICS_SCHEMA, "schema_version": DIAGNOSTICS_SCHEMA_VERSION,
        "kind": enum_text(diagnostics.kind), "shape": enum_text(diagnostics.shape),
        "generation": diagnostics.generation, "batch_size": diagnostics.batch_size, "retry_scope": scope,
        "path_policy": enum_text(diagnostics.path_policy), "timing_policy": enum_text(diagnostics.timing_policy),
        "metadata_batch": {"generation": counts.generation, "total": counts.total, "success": counts.success,
                           "partial": counts.partial, "failed": counts.failed},
        "preview_summary": preview_summary_tree(diagnostics.preview_summary),
        "execution_summary": execution_summary_tree(diagnostics.execution_summary),
        "outcome": enum_text(diagnostics.outcome), "items": items}


# --------------------------------------------------------------------------- the public renderer


def render_diagnostics_json(diagnostics: BatchDiagnostics, /) -> bytes:
    """Serialise ``diagnostics`` as compact, key-sorted, ASCII-only JSON (contract 22). Returns bytes only."""
    if type(diagnostics) is not BatchDiagnostics:
        raise DiagnosticsInputError("render_diagnostics_json needs an exact BatchDiagnostics")
    if batch_problem(diagnostics) is not None:
        raise DiagnosticsIntegrityError("the diagnostics graph failed the local re-check")
    tree = batch_tree(diagnostics)
    encoder = json.JSONEncoder(skipkeys=False, ensure_ascii=True, check_circular=True, allow_nan=False, sort_keys=True,
                          indent=None, separators=(",", ":"))
    chunks = []
    total = 0
    too_large = False
    encoding_failed = False
    try:
        for chunk in encoder.iterencode(tree):
            total += len(chunk)
            if total > MAX_DIAGNOSTIC_OUTPUT_BYTES:
                too_large = True
                break
            chunks.append(chunk)
        data = "".join(chunks).encode("ascii")
    except (ValueError, TypeError, RecursionError, OverflowError):
        encoding_failed = True
    if encoding_failed:
        raise DiagnosticsSerializationError("the diagnostics could not be encoded")
    if too_large:
        raise DiagnosticsResourceLimitError("the encoded diagnostics exceed MAX_DIAGNOSTIC_OUTPUT_BYTES")
    return data
