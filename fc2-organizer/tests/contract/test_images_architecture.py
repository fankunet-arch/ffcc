"""Contract test: ``fc2_organizer.images`` architecture boundary (P4-C5 contract section 10).

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

Substep-2 exception (frozen): ``transport.py`` is the **only** images module that may import
``httpx``. Its allow-list is exactly ``_TRANSPORT_ALLOWED`` below; it still never imports
``fc2_metadata_core`` (in particular not ``SourceHttpClient`` / ``HttpResponse``), ``amane``, any
filesystem module, or any other ``fc2_organizer`` package, and it makes no filesystem call.
``fc2_organizer/images/__init__.py`` does not import ``transport``, so ``import fc2_organizer.images``
never loads ``httpx``.
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

# Foundation = stdlib-only modules. Substep 3 added jpeg.py (JPEG-only content policy) to this set.
_FOUNDATION_MODULES = {"__init__.py", "errors.py", "models.py", "policy.py", "urls.py", "jpeg.py"}
_JPEG_ALLOWED = {"__future__", "dataclasses", "enum", "fc2_organizer.images.errors"}
_TRANSPORT_MODULE = "transport.py"
_TRANSPORT_ALLOWED = {
    "__future__", "asyncio", "dataclasses", "math", "re", "types", "typing", "urllib.parse", "httpx",
}
_TRANSPORT_FORBIDDEN_CALL_NAMES = {
    "open", "stat", "lstat", "exists", "is_file", "is_dir", "resolve", "realpath", "mkdir", "makedirs",
    "rename", "remove", "unlink", "read_bytes", "read_text", "write_bytes", "write_text", "getcwd", "chdir",
    "getenv", "print", "AsyncHTTPTransport", "HTTPTransport", "Client", "sleep", "retry",
}
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


def _foundation_files() -> list[Path]:
    return [p for p in _source_files(IMAGES_SRC_ROOT) if p.name in _FOUNDATION_MODULES]


def test_images_package_has_exactly_the_foundation_plus_transport_modules():
    """Substep 2 added transport.py, substep 3 jpeg.py; no acquisition.py was started."""
    assert IMAGES_SRC_ROOT.is_dir()
    assert {p.name for p in _source_files(IMAGES_SRC_ROOT)} == _FOUNDATION_MODULES | {_TRANSPORT_MODULE}


def test_images_foundation_imports_only_allowed_stdlib_and_itself():
    for path in _foundation_files():
        for module in _imported_modules(_tree(path)):
            if module.startswith("fc2_organizer.images"):
                continue
            assert module in _ALLOWED_STDLIB, f"{path.name}: import of {module!r} is outside the images boundary"
            assert not module.startswith(_FORBIDDEN_PREFIXES) or module == "urllib.parse", (path.name, module)


def test_images_foundation_has_no_network_filesystem_or_amane_text():
    for path in _foundation_files():
        text = path.read_text(encoding="utf-8")
        for needle in ("import amane", "from amane", "import httpx", "from httpx", "urllib.request",
                       "import socket", "getaddrinfo", "os.environ"):
            assert needle not in text, f"{path.name}: {needle!r}"


def test_images_foundation_makes_no_io_network_or_clock_call():
    for path in _foundation_files():
        for node in ast.walk(_tree(path)):
            if isinstance(node, ast.Call):
                func = node.func
                name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
                assert name not in _FORBIDDEN_CALL_NAMES, f"{path.name}:{node.lineno}: call to {name!r}"


def test_only_transport_imports_httpx():
    for path in _source_files(IMAGES_SRC_ROOT):
        uses_httpx = any(m == "httpx" or m.startswith("httpx.") for m in _imported_modules(_tree(path)))
        assert uses_httpx is (path.name == _TRANSPORT_MODULE), path.name


def test_transport_imports_only_its_frozen_allow_list():
    for module in _imported_modules(_tree(IMAGES_SRC_ROOT / _TRANSPORT_MODULE)):
        if module in {"fc2_organizer.images.errors", "fc2_organizer.images.urls"}:
            continue
        assert module in _TRANSPORT_ALLOWED, f"transport.py: import of {module!r} is outside its allow-list"


def test_transport_never_reuses_core_text_http_client_or_touches_filesystem():
    path = IMAGES_SRC_ROOT / _TRANSPORT_MODULE
    for module in _imported_modules(_tree(path)):
        assert not module.startswith(("fc2_metadata_core", "amane", "os", "pathlib", "io", "shutil")), module
    for node in ast.walk(_tree(path)):
        if isinstance(node, ast.Call):
            func = node.func
            name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
            assert name not in _TRANSPORT_FORBIDDEN_CALL_NAMES, f"transport.py:{node.lineno}: call to {name!r}"
    tree = _tree(path)
    for node in ast.walk(tree):
        # bytes end to end: no text decoding, no whole-body read before the size check
        if isinstance(node, ast.Attribute):
            assert node.attr not in {"aread", "read", "text", "json", "aiter_text", "iter_text", "decode",
                                     "encode", "environ"}, f"transport.py:{node.lineno}: .{node.attr}"
            if node.attr == "content":
                assert isinstance(node.value, ast.Name) and node.value.id == "self", (
                    f"transport.py:{node.lineno}: .content on a non-self object (whole-body read)"
                )
        if isinstance(node, ast.Call) and getattr(node.func, "attr", None) == "AsyncClient":
            keywords = {k.arg: k.value for k in node.keywords}
            for flag in ("follow_redirects", "trust_env"):
                assert isinstance(keywords.get(flag), ast.Constant) and keywords[flag].value is False, flag
            assert not ({"auth", "cookies", "headers", "proxy", "proxies", "mounts"} & set(keywords))


def test_transport_creates_exactly_one_async_client_in_the_constructor_and_none_at_import():
    tree = _tree(IMAGES_SRC_ROOT / _TRANSPORT_MODULE)
    sites = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            for inner in ast.walk(node):
                if isinstance(inner, ast.Call) and getattr(inner.func, "attr", None) == "AsyncClient":
                    sites.append(node.name)
    assert sites == ["__init__"]
    module_level_calls = [
        n for n in tree.body if isinstance(n, ast.Assign | ast.AnnAssign) and any(
            isinstance(c, ast.Call) and getattr(c.func, "attr", None) == "AsyncClient" for c in ast.walk(n)
        )
    ]
    assert module_level_calls == []


def test_jpeg_module_is_pure_and_independent_of_transport():
    """jpeg.py: stdlib + images errors only -- no httpx, transport, image library, struct,
    filesystem, clock or randomness; and it makes no I/O call."""
    path = IMAGES_SRC_ROOT / "jpeg.py"
    assert _imported_modules(_tree(path)) <= _JPEG_ALLOWED
    for node in ast.walk(_tree(path)):
        if isinstance(node, ast.Call):
            func = node.func
            name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
            assert name not in _TRANSPORT_FORBIDDEN_CALL_NAMES | {"urlopen", "random", "now", "monotonic"}, name
    text = path.read_text(encoding="utf-8")
    for needle in ("import PIL", "from PIL", "import httpx", "images.transport", "import struct", "import os"):
        assert needle not in text, needle


def test_nothing_but_transport_imports_transport():
    for path in _source_files(IMAGES_SRC_ROOT):
        if path.name == _TRANSPORT_MODULE:
            continue
        for module in _imported_modules(_tree(path)):
            assert module != "fc2_organizer.images.transport", path.name


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


def test_images_public_api_is_the_foundation_plus_pure_transport_errors_and_jpeg_policy():
    _purge()
    try:
        images = importlib.import_module("fc2_organizer.images")
        assert set(images.__all__) == {
            "AcquiredImage", "ImageAcquisitionPolicy", "ImageAcquisitionResult", "ImageCandidateFailure",
            "ImageError", "ImageFailureKind", "ImageInputError", "ImageModelError", "ImagePolicyError",
            "ImageRole", "ImageUrlError", "MAX_IMAGE_URL_LENGTH", "UrlRejectionReason", "validate_image_url",
            "ImageTransportError", "ImageTimeoutError", "ImageConnectionError", "ImageRedirectLimitError",
            "ImageRedirectError", "ImageResponseTooLargeError", "ImageClientClosedError",
            "ContentTypeVerdict", "DimensionRejectionReason", "ImageContentTypeError", "ImageDimensionError",
            "ImageJpegError", "JpegInfo", "JpegRejectionReason", "MAX_IMAGE_HEIGHT", "MAX_IMAGE_PIXELS",
            "MAX_IMAGE_WIDTH", "inspect_jpeg", "validate_acquired_image", "validate_image_content_type",
        }
        assert "fc2_organizer.images.transport" not in sys.modules
        assert not any(name == "httpx" or name.startswith("httpx.") for name in images.__all__)
        for deferred in ("acquire_images", "HttpxImageClient", "download", "parse_jpeg", "write", "save"):
            assert not hasattr(images, deferred)
    finally:
        _purge()
