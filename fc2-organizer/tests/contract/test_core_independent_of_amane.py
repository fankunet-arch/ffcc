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

CORE_MODULES = [
    "fc2_metadata_core",
    "fc2_metadata_core.errors",
    "fc2_metadata_core.models",
    "fc2_metadata_core.models.metadata",
    "fc2_metadata_core.models.source_result",
    "fc2_metadata_core.normalize",
    "fc2_metadata_core.normalize.fc2_number",
]


def _iter_core_source_files() -> list[Path]:
    return sorted(CORE_SRC_ROOT.rglob("*.py"))


def test_core_source_root_exists_and_has_files():
    assert CORE_SRC_ROOT.is_dir(), f"expected {CORE_SRC_ROOT} to exist"
    files = _iter_core_source_files()
    assert files, "fc2_metadata_core has no source files to statically check"


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
