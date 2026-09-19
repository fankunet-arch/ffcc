"""Public data contracts for the FC2 Metadata Core."""

from fc2_metadata_core.models.metadata import NormalizedMetadata
from fc2_metadata_core.models.source_result import (
    SourceErrorKind,
    SourceResult,
    SourceStatus,
)

__all__ = [
    "NormalizedMetadata",
    "SourceResult",
    "SourceStatus",
    "SourceErrorKind",
]
