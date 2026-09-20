"""Concrete, real-site source adapters.

Empty until a candidate provider clears the Phase 2 research process:

    candidate search -> live probe -> recorded evidence -> ADOPT/REJECT

Only an ``ADOPT``ed candidate (see ``docs/sources/SOURCE_VIABILITY_*.md``
and ``docs/SOURCE_STATUS_MATRIX.md``) gets a module in this package. Writing
an adapter here for a site that has not been probed and adopted is exactly
what the Phase 2 process forbids -- see spec section five ("先做 Source
Viability Research，再决定写哪个 Adapter").

``ALL_ADAPTER_CLASSES`` is the single list ``tools/probe_sources.py`` (and,
later, Phase 3's dispatcher) registers into a
``fc2_metadata_core.sources.SourceRegistry``. Adding an adopted adapter is
one import + one append here, never a growing if/elif chain elsewhere.
"""

from __future__ import annotations

from fc2_metadata_core.sources.base import SourceAdapter

ALL_ADAPTER_CLASSES: list[type[SourceAdapter]] = []

__all__ = ["ALL_ADAPTER_CLASSES"]
