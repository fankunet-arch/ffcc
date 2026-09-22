"""FC2 Organizer -- upper-layer, host-facing capabilities built on top of the
independent ``fc2_metadata_core`` contract.

Dependency direction (frozen, see ``docs/specifications/PHASE4_DISCOVERY_CONTRACT.md``)::

    fc2_organizer
        |
        v
    fc2_metadata_core

``fc2_metadata_core`` never imports ``fc2_organizer``. Nothing under this
package may import ``amane``.

Phase 4 / P4-C1 adds the first capability: read-only recursive media
discovery (``fc2_organizer.discovery``).
"""

from fc2_organizer import discovery

__all__ = ["discovery"]
