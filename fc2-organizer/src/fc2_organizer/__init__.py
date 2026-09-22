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
discovery (``fc2_organizer.discovery``). Phase 4 / P4-C2 adds the second:
a pure, immutable organize plan (``fc2_organizer.planning``).

``fc2_organizer.planning`` is deliberately **not** eagerly imported here
(unlike ``discovery``): it depends on ``fc2_metadata_core.models`` /
``fc2_metadata_core.normalize``, and ``fc2_metadata_core``'s own
``__init__.py`` eagerly imports every one of its submodules (including
``aggregation``/``batch``/``http``/``sources``) as a side effect of
importing *any* of them. Eagerly importing ``planning`` here would make
that transitive load happen merely by importing ``fc2_organizer`` or
``fc2_organizer.discovery`` -- breaking discovery's own frozen
architecture-boundary test, which proves ``discover_media`` runs with
those exact modules blocked at the meta-path level (P4-C1,
``tests/contract/test_discovery_architecture.py``). Import
``fc2_organizer.planning`` explicitly instead: ``from fc2_organizer import
planning`` or ``from fc2_organizer.planning import build_organize_plan``.
"""

from fc2_organizer import discovery

__all__ = ["discovery"]
