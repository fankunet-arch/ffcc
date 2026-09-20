"""Core error/status semantics.

Phase 1 freezes the failure vocabulary used across the FC2 Metadata Core so
that later phases never have to collapse a real failure into a bare
``except Exception: return None``. ``SourceResult`` (see
``fc2_metadata_core.models.source_result``) carries one of these as
``error_kind`` together with a mandatory ``error_detail`` string whenever a
source did not reach the minimum-success bar.

This module intentionally has no dependency on anything outside the standard
library and must never import ``amane``.
"""

from __future__ import annotations

__all__ = [
    "FC2MetadataCoreError",
    "MetadataContractError",
    "SourceResultContractError",
    "InvalidCanonicalNumberInputError",
]


class FC2MetadataCoreError(Exception):
    """Base class for all fc2_metadata_core contract violations."""


class MetadataContractError(FC2MetadataCoreError, ValueError):
    """Raised when a ``NormalizedMetadata`` instance violates its contract."""


class SourceResultContractError(FC2MetadataCoreError, ValueError):
    """Raised when a ``SourceResult`` instance violates its status/error contract."""


class InvalidCanonicalNumberInputError(FC2MetadataCoreError, ValueError):
    """Raised when a source adapter is asked to look up a non-canonical number.

    Phase 1 owns turning dirty input (filenames, free text) into a canonical
    ``FC2-1234567`` string (see ``fc2_metadata_core.normalize``). A source
    adapter's ``fetch`` is a Phase 2 boundary that only ever accepts an
    already-canonical number: it must not re-implement filename parsing or
    invent a fallback for garbage input. Passing anything else is a caller
    (dispatcher) bug, reported explicitly here rather than silently
    producing a fabricated or nonsensical lookup.
    """
