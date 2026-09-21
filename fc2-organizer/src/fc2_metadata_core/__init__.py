"""Independent FC2 metadata contracts and number normalization.

This package is the "FC2 Metadata Core" mandated by the frozen architecture
(``Amane host -> thin adapter -> FC2 metadata core -> pluggable sources``).

Hard rule (Phase 1 scope freeze): nothing under ``fc2_metadata_core`` may
import ``amane`` or any ``amane.*`` module, directly or indirectly. The
contract must be importable and testable in an environment where Amane is
not installed at all. This is enforced by
``tests/contract/test_core_independent_of_amane.py``.

Phase 1 defined contracts only (models, normalization, error semantics),
with no network access and no site-specific scraper. Phase 2 adds the
pluggable source adapter framework (``sources``) and its injectable HTTP
transport (``http``). Phase 3 C1 adds multi-source execution and deterministic
field-level aggregation (``aggregation``). Zero dependency on ``amane``.
"""

from fc2_metadata_core import aggregation, batch, errors, http, models, normalize, sources

__all__ = ["aggregation", "batch", "errors", "http", "models", "normalize", "sources"]
