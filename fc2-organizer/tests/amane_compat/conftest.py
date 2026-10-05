"""P5-C2 targeted 测试夹具（只在 ``tests/amane_compat`` 内生效）。"""

from __future__ import annotations

import pytest

from _compat_support import REPO, load_tool


@pytest.fixture(scope="session")
def core_wheel(tmp_path_factory) -> "Path":
    """真实构建的 L0 Core wheel（由 ``tools/build_core_wheel.py`` 的构建逻辑生成；不依赖 Amane）。"""
    builder = load_tool("build_core_wheel.py")
    name, payload, _tree = builder.build_wheel_bytes(REPO / "src" / "fc2_metadata_core", REPO / "pyproject.toml")
    directory = tmp_path_factory.mktemp("core_wheel")
    path = directory / name
    path.write_bytes(payload)
    return path
