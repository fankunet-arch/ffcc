"""Contract test: fc2_metadata_core must be importable and usable with zero
dependency on Amane.

Two independent checks, per Phase 1 requirement:
1. Static: no source file under fc2_metadata_core contains an `import amane`
   / `from amane import ...` statement (AST-based, catches it even if such
   an import is buried inside a function body or a try/except).
2. Dynamic: fc2_metadata_core (and every one of its submodules) can be
   freshly imported while a meta path finder actively raises if *anything*
   tries to import `amane` or `amane.*`. If this passes, the package does
   not merely happen to avoid importing amane in this environment -- it
   cannot, structurally, without failing this test.
"""

from __future__ import annotations

import ast
import importlib
import sys
from pathlib import Path

import pytest

CORE_SRC_ROOT = Path(__file__).resolve().parents[2] / "src" / "fc2_metadata_core"


def _iter_core_source_files() -> list[Path]:
    return sorted(CORE_SRC_ROOT.rglob("*.py"))


def _module_name_from_source_file(path: Path) -> str:
    """Map a source file under ``CORE_SRC_ROOT`` to its dotted module name.

    ``.../fc2_metadata_core/models/metadata.py`` -> ``fc2_metadata_core.models.metadata``
    ``.../fc2_metadata_core/models/__init__.py``  -> ``fc2_metadata_core.models``
    """
    relative = path.relative_to(CORE_SRC_ROOT.parent).with_suffix("")
    parts = relative.parts
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _discover_core_modules() -> list[str]:
    """F4 closure: derive the module list to test from the filesystem itself.

    Previously this was a hand-maintained list (``CORE_MODULES``) that a new
    ``fc2_metadata_core`` module could be added without updating, silently
    letting the dynamic Amane-independence check below drift out of sync
    with the actual package tree. Deriving it from
    ``_iter_core_source_files()`` -- the same file listing the static
    AST check already uses -- means every new file under
    ``fc2_metadata_core`` is automatically covered by both checks with no
    second list to remember.
    """
    return sorted({_module_name_from_source_file(p) for p in _iter_core_source_files()})


CORE_MODULES = _discover_core_modules()


def test_core_source_root_exists_and_has_files():
    assert CORE_SRC_ROOT.is_dir(), f"expected {CORE_SRC_ROOT} to exist"
    files = _iter_core_source_files()
    assert files, "fc2_metadata_core has no source files to statically check"


def test_module_name_from_source_file_maps_dunder_init_to_package_name():
    package_file = CORE_SRC_ROOT / "sources" / "__init__.py"
    assert _module_name_from_source_file(package_file) == "fc2_metadata_core.sources"


def test_module_name_from_source_file_maps_plain_module():
    module_file = CORE_SRC_ROOT / "sources" / "registry.py"
    assert _module_name_from_source_file(module_file) == "fc2_metadata_core.sources.registry"


def test_discovered_modules_have_no_duplicates_and_cover_every_file():
    """F4 closure evidence: the discovered list is derived, not maintained by
    hand, and its size tracks the file tree exactly -- one dotted module name
    per source file, no more, no less."""
    assert len(CORE_MODULES) == len(set(CORE_MODULES))
    assert len(CORE_MODULES) == len(_iter_core_source_files())
    assert "fc2_metadata_core" in CORE_MODULES


def test_discovery_found_more_than_the_original_phase1_module_count():
    """F4 regression guard: Phase 1 shipped with exactly 7 core modules under
    a hand-maintained ``CORE_MODULES`` list that a new module could silently
    bypass. Phase 2 adds ``fc2_metadata_core.http`` and
    ``fc2_metadata_core.sources`` packages; this asserts the *discovery
    mechanism itself* picked them up, with zero edits to this list, rather
    than merely asserting today's fixed total (which would reintroduce the
    exact hand-maintenance problem F4 closes)."""
    assert len(CORE_MODULES) > 7


@pytest.mark.parametrize(
    "path",
    _iter_core_source_files(),
    ids=lambda p: str(p.relative_to(CORE_SRC_ROOT)) if p.is_absolute() else str(p),
)
def test_no_static_amane_import_in_core(path: Path):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top_level = alias.name.split(".")[0]
                assert top_level != "amane", f"{path}: forbidden `import {alias.name}`"
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            top_level = module.split(".")[0]
            assert top_level != "amane", f"{path}: forbidden `from {module} import ...`"


class _BlockAmaneFinder:
    """Meta path finder that fails fast if `amane`/`amane.*` is imported."""

    def find_spec(self, fullname, path=None, target=None):
        if fullname == "amane" or fullname.startswith("amane."):
            raise ImportError(
                f"fc2_metadata_core attempted to import forbidden module: {fullname}"
            )
        return None  # defer to the normal finders for everything else


def _purge_core_modules() -> None:
    for name in list(sys.modules):
        if name == "fc2_metadata_core" or name.startswith("fc2_metadata_core."):
            del sys.modules[name]


def test_core_imports_cleanly_with_amane_import_blocked_at_runtime():
    _purge_core_modules()
    blocker = _BlockAmaneFinder()
    sys.meta_path.insert(0, blocker)
    try:
        for module_name in CORE_MODULES:
            importlib.import_module(module_name)
    finally:
        sys.meta_path.remove(blocker)
        _purge_core_modules()


def test_core_public_symbols_usable_with_amane_import_blocked_at_runtime():
    """Beyond importing, exercise the public contract end-to-end while the
    blocker is active, so a lazily-imported `amane` dependency inside a
    method body would also be caught."""
    _purge_core_modules()
    blocker = _BlockAmaneFinder()
    sys.meta_path.insert(0, blocker)
    try:
        core = importlib.import_module("fc2_metadata_core")

        result = core.normalize.normalize_fc2_number("FC2-PPV-1234567")
        assert result.canonical == "FC2-1234567"

        metadata = core.models.NormalizedMetadata(
            number=result.canonical, title="Example"
        )
        assert metadata.meets_minimum_success() is True

        source_result = core.models.SourceResult(
            source_id="example-source",
            status=core.models.SourceStatus.SUCCESS,
            metadata=metadata,
            elapsed_ms=42.0,
        )
        assert source_result.metadata is metadata
    finally:
        sys.meta_path.remove(blocker)
        _purge_core_modules()


def test_amane_is_not_actually_installed_in_this_test_environment():
    """Sanity check that the dynamic test above is meaningful: `amane` isn't
    already absent from sys.modules for some unrelated reason, and importing
    it for real does fail here (this is a Phase 1 offline environment)."""
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("amane")
