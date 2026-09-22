"""Contract test: ``fc2_organizer.images`` substep-1 foundation boundary (P4-C5 contract section 10).

Allowed dependencies (and nothing else) for the foundation modules
(``__init__``, ``errors``, ``models``, ``policy``, ``urls``):

* standard library: ``__future__``, ``dataclasses``, ``enum``, ``hashlib``, ``math``, ``re``,
  ``ipaddress``, ``urllib.parse`` (pure parser only);
* its own modules.

Never: ``fc2_metadata_core`` (any module), ``amane``, ``httpx`` / ``requests`` / ``socket`` /
``urllib.request`` / ``http``, any other ``fc2_organizer`` package, any filesystem / clock /
randomness / environment module. Never the reverse either: ``fc2_metadata_core``, ``discovery``,
``planning``, ``publication`` and ``nfo`` never import ``images``; ``fc2_organizer/__init__.py``
does not eagerly import it.
"""

from __future__ import annotations

import ast
import importlib
import sys
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[2] / "src"
IMAGES_SRC_ROOT = SRC_ROOT / "fc2_organizer" / "images"
ORGANIZER_SRC_ROOT = SRC_ROOT / "fc2_organizer"
CORE_SRC_ROOT = SRC_ROOT / "fc2_metadata_core"

_FOUNDATION_MODULES = {"__init__.py", "errors.py", "models.py", "policy.py", "urls.py"}
_ALLOWED_STDLIB = {"__future__", "dataclasses", "enum", "hashlib", "math", "re", "ipaddress", "urllib.parse"}
_FORBIDDEN_PREFIXES = (
    "fc2_metadata_core", "amane", "httpx", "requests", "aiohttp", "socket", "ssl", "http", "urllib.request",
    "asyncio", "os", "pathlib", "io", "shutil", "tempfile", "time", "random", "uuid", "subprocess",
    "fc2_organizer.discovery", "fc2_organizer.planning", "fc2_organizer.publication", "fc2_organizer.nfo",
    "fc2_organizer.batch", "fc2_organizer.resource_control",
)
_FORBIDDEN_CALL_NAMES = {
    "open", "mkdir", "makedirs", "rename", "remove", "unlink", "write", "write_bytes", "write_text", "read_bytes",
    "urlopen", "socket", "create_connection", "getaddrinfo", "gethostbyname", "get", "post", "request", "send",
    "stream", "AsyncClient", "Client", "print", "now", "monotonic", "time", "getenv", "random", "uuid4",
}


def _source_files(root: Path) -> list[Path]:
    return sorted(root.rglob("*.py"))


def _tree(path: Path) -> ast.AST:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _imported_modules(tree: ast.AST) -> set[str]:
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            modules.add(node.module or "")
    return modules


def test_images_package_has_exactly_the_substep_1_foundation_modules():
    """No transport.py / jpeg.py / acquisition.py was started in substep 1."""
    assert IMAGES_SRC_ROOT.is_dir()
    assert {p.name for p in _source_files(IMAGES_SRC_ROOT)} == _FOUNDATION_MODULES


def test_images_foundation_imports_only_allowed_stdlib_and_itself():
    for path in _source_files(IMAGES_SRC_ROOT):
        for module in _imported_modules(_tree(path)):
            if module.startswith("fc2_organizer.images"):
                continue
            assert module in _ALLOWED_STDLIB, f"{path.name}: import of {module!r} is outside the images boundary"
            assert not module.startswith(_FORBIDDEN_PREFIXES) or module == "urllib.parse", (path.name, module)


def test_images_foundation_has_no_network_filesystem_or_amane_text():
    for path in _source_files(IMAGES_SRC_ROOT):
        text = path.read_text(encoding="utf-8")
        for needle in ("import amane", "from amane", "import httpx", "from httpx", "urllib.request",
                       "import socket", "getaddrinfo", "os.environ"):
            assert needle not in text, f"{path.name}: {needle!r}"


def test_images_foundation_makes_no_io_network_or_clock_call():
    for path in _source_files(IMAGES_SRC_ROOT):
        for node in ast.walk(_tree(path)):
            if isinstance(node, ast.Call):
                func = node.func
                name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
                assert name not in _FORBIDDEN_CALL_NAMES, f"{path.name}:{node.lineno}: call to {name!r}"


def test_errors_module_is_stdlib_only():
    assert _imported_modules(_tree(IMAGES_SRC_ROOT / "errors.py")) <= {"__future__", "enum"}


def test_no_reverse_dependency_on_images():
    for root in (
        CORE_SRC_ROOT,
        ORGANIZER_SRC_ROOT / "discovery",
        ORGANIZER_SRC_ROOT / "planning",
        ORGANIZER_SRC_ROOT / "publication",
        ORGANIZER_SRC_ROOT / "nfo",
    ):
        for path in _source_files(root):
            for module in _imported_modules(_tree(path)):
                assert not module.startswith("fc2_organizer.images"), f"{path}: imports {module!r}"
            assert "fc2_organizer.images" not in path.read_text(encoding="utf-8"), path


def test_top_level_organizer_init_does_not_eagerly_import_images():
    tree = _tree(ORGANIZER_SRC_ROOT / "__init__.py")
    for module in _imported_modules(tree):
        assert "images" not in module
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            assert all(alias.name != "images" for alias in node.names)


_BLOCKED_ROOTS = {"amane", "httpx", "requests", "socket", "ssl", "fc2_metadata_core"}
_BLOCKED_EXACT = {"urllib.request", "http.client"}


class _BlockNetworkAndCoreFinder:
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".")[0] in _BLOCKED_ROOTS or fullname in _BLOCKED_EXACT:
            raise ImportError(f"fc2_organizer.images attempted to import forbidden module: {fullname}")
        return None


def _purge() -> None:
    for name in list(sys.modules):
        if name.split(".")[0] in {"fc2_organizer", "fc2_metadata_core"}:
            del sys.modules[name]


def test_images_imports_and_works_with_network_core_and_amane_blocked():
    _purge()
    saved = {name: sys.modules.pop(name) for name in list(sys.modules) if name.split(".")[0] in _BLOCKED_ROOTS
             or name in _BLOCKED_EXACT}
    blocker = _BlockNetworkAndCoreFinder()
    sys.meta_path.insert(0, blocker)
    try:
        images = importlib.import_module("fc2_organizer.images")
        assert images.validate_image_url("https://example.com/a.jpg") == "https://example.com/a.jpg"
        assert images.ImageAcquisitionPolicy().max_redirects == 5
        assert images.ImageAcquisitionResult().total_bytes == 0
        loaded = set(sys.modules)
        assert not any(name.split(".")[0] in _BLOCKED_ROOTS or name in _BLOCKED_EXACT for name in loaded)
        assert not any(
            name.startswith(("fc2_organizer.publication", "fc2_organizer.planning", "fc2_organizer.nfo"))
            for name in loaded
        )
    finally:
        sys.meta_path.remove(blocker)
        _purge()
        sys.modules.update(saved)


def test_bare_import_of_fc2_organizer_does_not_load_images():
    _purge()
    try:
        importlib.import_module("fc2_organizer")
        assert "fc2_organizer.images" not in sys.modules
    finally:
        _purge()


def test_images_public_api_is_exactly_the_substep_1_foundation():
    _purge()
    try:
        images = importlib.import_module("fc2_organizer.images")
        assert set(images.__all__) == {
            "AcquiredImage", "ImageAcquisitionPolicy", "ImageAcquisitionResult", "ImageCandidateFailure",
            "ImageError", "ImageFailureKind", "ImageInputError", "ImageModelError", "ImagePolicyError",
            "ImageRole", "ImageUrlError", "MAX_IMAGE_URL_LENGTH", "UrlRejectionReason", "validate_image_url",
        }
        for deferred in ("acquire_images", "ImageHttpClient", "HttpxImageClient", "download", "parse_jpeg",
                         "write", "save"):
            assert not hasattr(images, deferred)
    finally:
        _purge()
