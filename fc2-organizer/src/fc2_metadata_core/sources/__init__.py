"""Pluggable FC2 metadata source adapters: contract + registry.

Phase 2 scope only: this package defines what a source adapter *is* (see
``base.SourceAdapter``) and how adapters are registered/discovered (see
``registry.SourceRegistry``). It contains no cross-source scheduling,
aggregation, retry, backoff, or concurrency policy -- those are Phase 3.
"""

from fc2_metadata_core.sources.base import (
    SourceAdapter,
    classify_http_status,
    classify_transport_error,
    require_canonical_number,
    transport_error_result,
)
from fc2_metadata_core.sources.registry import (
    DuplicateSourceIdError,
    SourceRegistry,
    SourceRegistryError,
    UnknownSourceIdError,
)

__all__ = [
    "SourceAdapter",
    "require_canonical_number",
    "classify_http_status",
    "classify_transport_error",
    "transport_error_result",
    "SourceRegistry",
    "SourceRegistryError",
    "DuplicateSourceIdError",
    "UnknownSourceIdError",
]
