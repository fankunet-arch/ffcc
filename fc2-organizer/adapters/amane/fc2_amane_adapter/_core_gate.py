"""Core 缺失 / 不兼容时的 ImportError 翻译（纯模块；自身不 import Core）。

``plugin.py`` 在模块顶层导入其它纯模块；这些模块在顶层导入 ``fc2_metadata_core``。导入链失败时，
``plugin.py`` 把 ``ImportError`` 交给本模块：当且仅当 ``exc.name`` 属于 ``fc2_metadata_core`` 时返回新的、
消息固定的 ``ImportError``；其它 ``ImportError`` 返回 ``None``（调用方原样重抛，不误报为 Core 缺失）。

合同第 22 节冻结：消息模板固定、有界、无密钥、确定性。
"""

from __future__ import annotations

__all__ = ["CORE_PACKAGE", "MISSING_CORE_MESSAGE_TEMPLATE", "translate_core_import_error"]

CORE_PACKAGE = "fc2_metadata_core"

MISSING_CORE_MESSAGE_TEMPLATE = (
    "FC2 Metadata Core 未安装或版本不兼容：请在 Amane 所在的 Python 环境中安装 "
    "fc2-metadata-core（缺失模块：{name}）"
)

_MAX_NAME_CHARS = 128
_ALLOWED_CHARS = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.")


def _is_core_module_name(name: object) -> bool:
    if not isinstance(name, str) or not name or len(name) > _MAX_NAME_CHARS:
        return False
    if not (name == CORE_PACKAGE or name.startswith(CORE_PACKAGE + ".")):
        return False
    return all(char in _ALLOWED_CHARS for char in name)


def translate_core_import_error(exc: BaseException) -> ImportError | None:
    """Core 相关的 ImportError -> 固定消息的新 ImportError；其它 -> ``None``。"""
    name = getattr(exc, "name", None)
    if not _is_core_module_name(name):
        return None
    return ImportError(MISSING_CORE_MESSAGE_TEMPLATE.format(name=name))
