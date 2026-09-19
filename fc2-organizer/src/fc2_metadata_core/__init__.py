"""Independent FC2 metadata contracts and number normalization.

This package is the "FC2 Metadata Core" mandated by the frozen architecture
(``Amane host -> thin adapter -> FC2 metadata core -> pluggable sources``).

Hard rule (Phase 1 scope freeze): nothing under ``fc2_metadata_core`` may
import ``amane`` or any ``amane.*`` module, directly or indirectly. The
contract must be importable and testable in an environment where Amane is
not installed at all. This is enforced by
``tests/contract/test_core_independent_of_amane.py``.

Phase 1 only defines contracts (models, normalization, error semantics).
It does not perform any network access, does not implement any site-specific
scraper, and does not talk to Amane.
"""

from fc2_metadata_core import errors, models, normalize

__all__ = ["errors", "models", "normalize"]
