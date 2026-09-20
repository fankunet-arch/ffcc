"""Concrete, real-site source adapters.

Populated only by candidates that cleared the Phase 2 research process:

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

from fc2_metadata_core.sources.adapters.av123 import Av123Adapter
from fc2_metadata_core.sources.adapters.fc2db_net import Fc2dbNetAdapter
from fc2_metadata_core.sources.adapters.javdb import JavdbAdapter
from fc2_metadata_core.sources.base import SourceAdapter

ALL_ADAPTER_CLASSES: list[type[SourceAdapter]] = [
    Fc2dbNetAdapter,
    Av123Adapter,
    JavdbAdapter,
]

__all__ = ["ALL_ADAPTER_CLASSES"]
