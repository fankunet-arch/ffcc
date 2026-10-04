"""P5-C1：确定性的 Amane 插件 zip 构建骨架（不是最终可分发包；最终分发与 Core 供给属 P5-C2）。

zip 的**唯一顶层文件夹**名为插件 id（``ffcc.fc2-metadata/``），其下是 ``fc2_amane_adapter/`` 的全部 ``*.py``
（``plugin.py`` 在该文件夹根）；不含 ``__pycache__`` / 测试 / 文档 / Core 源码。确定性：条目按名字排序、
固定时间戳 ``1980-01-01 00:00:00``、固定权限 ``0644``、固定压缩级别、``.py`` 文本统一为 LF 换行
（使 ``autocrlf`` 不同的检出得到字节相同的产物）。

用法::

    python tools/build_amane_plugin_zip.py --tree adapters/amane/fc2_amane_adapter --out <file.zip>
"""

from __future__ import annotations

import argparse
import hashlib
import io
import sys
import zipfile
from pathlib import Path

#: 与 ``fc2_amane_adapter._settings.PLUGIN_ID`` 相同（测试核对相等；构建器自身不 import adapter，因此不需要 Core）。
PLUGIN_ID = "ffcc.fc2-metadata"

FIXED_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
FIXED_ATTRIBUTES = 0o100644 << 16
MAX_ZIP_BYTES = 20 * 1024 * 1024  # Amane 的 MAX_ZIP_BYTES


class PluginTreeError(ValueError):
    """插件树不满足冻结布局。"""


def collect_files(tree: Path) -> list[tuple[str, bytes]]:
    """返回按名字排序的 (条目名, LF 规范化的字节)；严格校验布局。"""
    if not tree.is_dir():
        raise PluginTreeError("plugin tree is not a directory")
    entries: list[tuple[str, bytes]] = []
    for path in sorted(tree.iterdir(), key=lambda item: item.name):
        if path.name == "__pycache__":
            continue
        if not path.is_file():
            raise PluginTreeError(f"unexpected non-file entry: {path.name}")
        if path.suffix != ".py":
            raise PluginTreeError(f"only .py files may be packaged: {path.name}")
        if path.name == "__init__.py":
            raise PluginTreeError("the plugin tree must not contain __init__.py")
        if "fc2_metadata_core" in path.name:
            raise PluginTreeError("Core sources must never be bundled (supply is a P5-C2 decision)")
        entries.append((f"{PLUGIN_ID}/{path.name}", path.read_bytes().replace(b"\r\n", b"\n")))
    if not any(name == f"{PLUGIN_ID}/plugin.py" for name, _ in entries):
        raise PluginTreeError("plugin.py is required at the tree root")
    return entries


def build_zip_bytes(tree: Path) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in collect_files(tree):
            info = zipfile.ZipInfo(name, date_time=FIXED_TIMESTAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = FIXED_ATTRIBUTES
            info.create_system = 3  # 固定为 Unix，使产物与构建平台无关
            archive.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    payload = buffer.getvalue()
    if len(payload) > MAX_ZIP_BYTES:
        raise PluginTreeError("zip exceeds the Amane size limit")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tree", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    options = parser.parse_args(argv)
    payload = build_zip_bytes(options.tree)
    options.out.parent.mkdir(parents=True, exist_ok=True)
    options.out.write_bytes(payload)
    print(f"{options.out} sha256={hashlib.sha256(payload).hexdigest()} bytes={len(payload)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
