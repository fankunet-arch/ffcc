"""Error hierarchy and rejection-reason vocabularies for ``fc2_organizer.execution`` (P4-C7).

Standard library only (``enum``). Never imports ``fc2_metadata_core``, ``amane``,
any network module or any other ``fc2_organizer`` package.

Contract (``PHASE4_SAFE_FILESYSTEM_EXECUTION_CONTRACT.md`` section 27):

* every failure family has its own named exception carrying a typed ``reason``;
* messages are fixed wording plus enum values only -- never a path, a temporary
  token, payload bytes, an ``OSError`` string, the process key or a seal;
* typed errors are raised outside any ``except`` block, so no ``OSError`` or
  foreign exception is ever attached as ``__cause__`` / ``__context__``.
"""

from __future__ import annotations

from enum import Enum

__all__ = [
    "ExecutionError",
    "ExecutionInputError",
    "ExecutionModelError",
    "ExecutionContractError",
    "PlanGraphError",
    "PlanGraphRejectionReason",
    "ArtifactManifestError",
    "ManifestRejectionReason",
    "CheckpointError",
    "CheckpointRejectionReason",
    "PreflightIntegrityError",
    "PreflightIntegrityReason",
    "PreflightNotReadyError",
    "PathRejectionReason",
]


class PlanGraphRejectionReason(Enum):
    """Why an ``OrganizePlan`` was refused at the execution boundary (contract section 6)."""

    PLAN_RECONSTRUCTION_FAILED = "plan_reconstruction_failed"
    FIELD_TYPE = "field_type"
    PATH_TYPE = "path_type"
    OPERATIONS_NOT_TUPLE = "operations_not_tuple"
    OPERATION_COUNT = "operation_count"
    OPERATION_TYPE = "operation_type"
    OPERATION_KIND_ORDER = "operation_kind_order"
    OPERATION_TARGET_MISMATCH = "operation_target_mismatch"
    OPERATION_SOURCE_MISMATCH = "operation_source_mismatch"
    TARGET_DIRECTORY_LAYOUT = "target_directory_layout"
    MEDIA_NAME_MISMATCH = "media_name_mismatch"
    NFO_NAME_INVALID = "nfo_name_invalid"
    ARTIFACT_LAYOUT = "artifact_layout"
    BASENAME_COLLISION = "basename_collision"
    UNSAFE_COMPONENT = "unsafe_component"
    SOURCE_PATH_REJECTED = "source_path_rejected"
    SOURCE_EXTENSION_MISMATCH = "source_extension_mismatch"
    SOURCE_INSIDE_TARGET = "source_inside_target"
    TARGET_PATH_REJECTED = "target_path_rejected"
    LIBRARY_ROOT_REJECTED = "library_root_rejected"


class ManifestRejectionReason(Enum):
    """Why a ``tuple[ArtifactWriteRequest, ...]`` was refused (contract section 7)."""

    REQUEST_TYPE = "request_type"
    REQUEST_INVALID = "request_invalid"
    EMPTY_CONTENT = "empty_content"
    NFO_MISSING = "nfo_missing"
    NFO_NOT_FIRST = "nfo_not_first"
    DUPLICATE_KIND = "duplicate_kind"
    ORDER = "order"
    TARGET_MISMATCH = "target_mismatch"
    EXTRAFANART_NAME_MISMATCH = "extrafanart_name_mismatch"
    EXTRAFANART_ORDINAL_SEQUENCE = "extrafanart_ordinal_sequence"
    DUPLICATE_TARGET = "duplicate_target"


class CheckpointRejectionReason(Enum):
    """Why an ``ExecutionCheckpoint`` was refused (contract section 14.3)."""

    SEAL_INVALID = "seal_invalid"
    CONSUMED = "consumed"
    PLAN_MISMATCH = "plan_mismatch"
    MANIFEST_MISMATCH = "manifest_mismatch"
    EFFECTS_NOT_PREFIX = "effects_not_prefix"
    ALREADY_COMPLETE = "already_complete"


class PreflightIntegrityReason(Enum):
    """Why an ``ExecutionPreflight`` was refused by the executor (contract section 15.5)."""

    SEAL_INVALID = "seal_invalid"
    CONSUMED = "consumed"
    FINGERPRINT_MISMATCH = "fingerprint_mismatch"


class PathRejectionReason(Enum):
    """Lexical path / component rejection (contract section 26.3). Internal detail:
    the public errors report the path *role* through ``PlanGraphRejectionReason``."""

    EMPTY = "empty"
    NUL_CHARACTER = "nul_character"
    NOT_ABSOLUTE = "not_absolute"
    DEVICE_NAMESPACE = "device_namespace"
    DOT_SEGMENT = "dot_segment"
    NO_BASENAME = "no_basename"
    ILLEGAL_CHARACTER = "illegal_character"
    TRAILING_DOT_OR_SPACE = "trailing_dot_or_space"
    RESERVED_NAME = "reserved_name"


class ExecutionError(Exception):
    """Base class of every ``fc2_organizer.execution`` failure."""


class ExecutionInputError(ExecutionError, TypeError):
    """An argument has the wrong exact Python type (contract section 5). Raised before
    any attribute of the rejected object is touched and before any filesystem access."""


class ExecutionModelError(ExecutionError, ValueError):
    """A hand-built execution model violates its own structural contract."""


class ExecutionContractError(ExecutionError, ValueError):
    """Base class of the typed structural / integrity refusals below."""


class PlanGraphError(ExecutionContractError):
    """The ``OrganizePlan`` is not an intact, frozen-layout, frozen-graph plan."""

    def __init__(self, reason: PlanGraphRejectionReason) -> None:
        self.reason = reason
        super().__init__(f"organize plan rejected at execution boundary: {reason.value}")


class ArtifactManifestError(ExecutionContractError):
    """The artifact manifest does not match the frozen manifest shape for this plan."""

    def __init__(self, reason: ManifestRejectionReason) -> None:
        self.reason = reason
        super().__init__(f"artifact manifest rejected: {reason.value}")


class CheckpointError(ExecutionContractError):
    """The checkpoint is forged, altered, foreign, consumed or does not bind this input."""

    def __init__(self, reason: CheckpointRejectionReason) -> None:
        self.reason = reason
        super().__init__(f"execution checkpoint rejected: {reason.value}")


class PreflightIntegrityError(ExecutionContractError):
    """The preflight is forged, altered, already consumed or its inputs changed."""

    def __init__(self, reason: PreflightIntegrityReason) -> None:
        self.reason = reason
        super().__init__(f"execution preflight rejected: {reason.value}")


class PreflightNotReadyError(ExecutionError):
    """``execute_filesystem`` was given a preflight whose ``ready`` is ``False``."""

    def __init__(self) -> None:
        super().__init__("execution preflight is not ready; nothing was executed")
