"""FC2 Metadata Core 定位器（P5-C2 合同第 8.3 节；Risk C 信任边界的准入规则）。

纯标准库；不联网、不写文件、不起子进程；不 import amane / pydantic / fc2_metadata_core。
唯一被接受的 Core 执行形态 = exact pinned wheel（文件名 == pin、整个 wheel 的 sha256 == pin、普通文件、
非符号链接、大小有界、由 ``zipimport.zipimporter`` 精确类型加载且来源同根）。其它一切来源一律 fail closed。

唯一成功规则（I-C2-18）：任何成功返回之前，都必须有对**实际当前 import 解析**的最终证明；
预解析不是准入；不存在“wheel 已在 sys.path 中 -> 立即成功”的路径。

完整性保证 = 准入时刻的完整性（admission-time integrity），**不是**运行期不可变性（威胁模型 N-03 / L-C2-13）。
"""

import hashlib
import importlib.machinery
import importlib.util
import os
import stat
import sys
import zipimport

__all__ = ["ensure_core"]

_CORE = "fc2_metadata_core"
_MAX_WHEEL_BYTES = 16 * 1024 * 1024
_CHUNK = 1024 * 1024

_RESTART_TEMPLATE = (
    "FC2 Metadata Core 已加载的版本与插件不配对（或无法验证）：请先卸载旧版插件并重启 Amane，"
    "再安装与之配对的新版（需要 Core <CORE_VERSION>）"
)
_UNVERIFIABLE_TEMPLATE = (
    "FC2 Metadata Core 的来源不受支持或无法验证（已拒绝加载）：请把官方发布包中的 <CORE_WHEEL_NAME> 放入 "
    "<Amane 数据目录>/plugins/_ffcc_core/，不要使用 pip / 源码 / editable 形态的 Core"
)
_WHEEL_VERSION_MISMATCH_TEMPLATE = (
    "FC2 Metadata Core 随附包版本与插件不配对：请在 <Amane 数据目录>/plugins/_ffcc_core/ 中放入 <CORE_WHEEL_NAME>"
)
_WHEEL_HASH_MISMATCH_TEMPLATE = (
    "FC2 Metadata Core 随附包校验失败（sha256 与插件配对记录不一致）：请重新获取官方发布包中的 <CORE_WHEEL_NAME>"
)


def _error(template, pin):
    message = template.replace("<CORE_VERSION>", pin.CORE_VERSION).replace("<CORE_WHEEL_NAME>", pin.CORE_WHEEL_NAME)
    return ImportError(message)


def _norm(path):
    """规范化路径（``normcase(realpath(.))``）；非字符串返回 ``None``。"""
    if isinstance(path, bytes) or not isinstance(path, (str, os.PathLike)):
        return None
    try:
        return os.path.normcase(os.path.realpath(os.fspath(path)))
    except (OSError, ValueError):
        return None


def _wheel_proof(pin, wheel):
    """wheel 证明：``lstat`` 普通文件（非目录 / 非符号链接 / 非特殊文件）、文件名 == pin、大小有界、整个文件 sha256 == pin。"""
    try:
        if os.path.basename(wheel) != pin.CORE_WHEEL_NAME:
            return False
        info = os.lstat(wheel)
        if not stat.S_ISREG(info.st_mode) or info.st_size > _MAX_WHEEL_BYTES:
            return False
        digest = hashlib.sha256()
        remaining = info.st_size
        with open(wheel, "rb") as handle:
            while remaining > 0:
                block = handle.read(min(_CHUNK, remaining))
                if not block:
                    return False
                digest.update(block)
                remaining -= len(block)
            if handle.read(1):
                return False
        return digest.hexdigest() == pin.CORE_WHEEL_SHA256
    except (OSError, ValueError):
        return False


def _in_archive(spec, wheel_key, *, top_level):
    """spec 的 loader 是 ``zipimport.zipimporter`` **精确类型**（I-C2-19），archive == verified wheel，origin 在该归档内。

    顶层 ``fc2_metadata_core`` 经 wheel 根解析，其 loader 的 ``prefix == ""``；子模块的 loader 是包内路径条目的
    importer（``prefix`` 以 ``fc2_metadata_core/`` 开头），所以 ``prefix`` 只对顶层要求为空。
    """
    if spec is None:
        return False
    loader = spec.loader
    if type(loader) is not zipimport.zipimporter:
        return False
    archive = getattr(loader, "archive", None)
    if not isinstance(archive, str) or _norm(archive) != wheel_key:
        return False
    if top_level and getattr(loader, "prefix", None) != "":
        return False
    prefix = archive + os.sep
    origin = spec.origin
    return isinstance(origin, str) and origin.startswith(prefix)


def _is_verified_resolution(spec, wheel_key):
    """2E / 2C 的判据：在 ``_in_archive`` 之上，包的 ``submodule_search_locations`` 必须是归档内路径 ``<archive>/fc2_metadata_core``。"""
    if not _in_archive(spec, wheel_key, top_level=True):
        return False
    locations = spec.submodule_search_locations
    if locations is None:
        return False
    expected = spec.loader.archive + os.sep + _CORE
    entries = list(locations)
    return bool(entries) and all(item == expected for item in entries)


def _loaded_core_is_proven(pin):
    """已加载 Core 的证明 = current-origin + current-artifact proof（不是历史已执行字节证明）。"""
    items = [(name, module) for name, module in list(sys.modules.items()) if name == _CORE or name.startswith(_CORE + ".")]
    top = sys.modules.get(_CORE)
    top_spec = getattr(top, "__spec__", None)
    top_loader = getattr(top_spec, "loader", None)
    if type(top_loader) is not zipimport.zipimporter or not isinstance(getattr(top_loader, "archive", None), str):
        return False
    wheel = top_loader.archive
    wheel_key = _norm(wheel)
    if wheel_key is None or not _wheel_proof(pin, wheel):
        return False
    for name, module in items:
        spec = getattr(module, "__spec__", None)
        if not _in_archive(spec, wheel_key, top_level=(name == _CORE)):
            return False
    return True


def _find_data_dir(module_file):
    """由 shim 的 ``__file__`` 向上找第一个满足 ``name == sources and parent.name == plugins`` 的目录；返回数据目录或 ``None``。"""
    try:
        current = os.path.dirname(os.path.abspath(os.fspath(module_file)))
    except (TypeError, ValueError):
        return None
    while True:
        parent = os.path.dirname(current)
        if os.path.basename(current) == "sources" and os.path.basename(parent) == "plugins":
            return os.path.dirname(parent)
        if parent == current:
            return None
        current = parent


def _cache_snapshot(wheel_key):
    return {key: value for key, value in list(sys.path_importer_cache.items()) if _norm(key) == wheel_key}


def _rollback(entry_path_object, entry_path, entry_cache, wheel_key):
    """失败回滚：``sys.path`` 逐元素还原（同一 list 对象）；verified-wheel 的 importer-cache 条目回到入口状态。"""
    if sys.path is not entry_path_object:
        sys.path = entry_path_object
    if entry_path_object != entry_path:
        entry_path_object[:] = entry_path
    if wheel_key is None:
        return
    for key in [key for key in list(sys.path_importer_cache) if _norm(key) == wheel_key]:
        if key not in entry_cache:
            del sys.path_importer_cache[key]
    for key, value in entry_cache.items():
        if key not in sys.path_importer_cache or sys.path_importer_cache[key] is not value:
            sys.path_importer_cache[key] = value


def _pre_resolve(wheel):
    """2C 防御性预解析：不修改 ``sys.path``；按 ``sys.meta_path`` 顺序取第一个非 ``None`` 的 spec。"""
    for finder in list(sys.meta_path):
        find_spec = getattr(finder, "find_spec", None)
        if find_spec is None:
            continue
        if finder is importlib.machinery.PathFinder:
            spec = find_spec(_CORE, [wheel] + list(sys.path))
        else:
            spec = find_spec(_CORE, None)
        if spec is not None:
            return spec
    return None


def _admit_sidecar_wheel(pin, wheel, entry_path_object, entry_path):
    """2A..2E。任何失败都回滚后抛出 ``ImportError``；只有 2E 通过才返回。"""
    wheel_key = _norm(wheel)
    entry_cache = _cache_snapshot(wheel_key) if wheel_key is not None else {}
    try:
        # 2B wheel 证明
        if wheel_key is None or not _wheel_proof(pin, wheel):
            raise _error(_WHEEL_HASH_MISMATCH_TEMPLATE, pin)
        # 2C 预解析（防御性；不是准入）
        if not _is_verified_resolution(_pre_resolve(wheel), wheel_key):
            raise _error(_UNVERIFIABLE_TEMPLATE, pin)
        # 2D 建立优先级：只在 wheel 不在 sys.path 时单次插入；绝不重排 / 移动 / 删除已有条目；已在则不得直接返回成功
        if wheel_key not in [_norm(item) for item in list(sys.path)]:
            sys.path.insert(0, wheel)
        # 2E 最终真实解析（两个分支都必须执行）
        if not _is_verified_resolution(importlib.util.find_spec(_CORE), wheel_key):
            raise _error(_UNVERIFIABLE_TEMPLATE, pin)
    except ImportError:
        _rollback(entry_path_object, entry_path, entry_cache, wheel_key)
        raise
    except Exception:
        _rollback(entry_path_object, entry_path, entry_cache, wheel_key)
        raise _error(_UNVERIFIABLE_TEMPLATE, pin) from None
    except BaseException:
        _rollback(entry_path_object, entry_path, entry_cache, wheel_key)
        raise


def ensure_core(pin, module_file):
    """让 exact pinned Core wheel 成为 ``fc2_metadata_core`` 的唯一可执行来源，或 fail closed（``ImportError``）。"""
    # 0. 入口快照：先于一切 probe
    entry_path_object = sys.path
    entry_path = list(entry_path_object)

    # 1. 已加载：必须证明来自同一个 exact pinned wheel 且所有 fc2_metadata_core* 同根；不修改任何状态
    if _CORE in sys.modules:
        if not _loaded_core_is_proven(pin):
            raise _error(_RESTART_TEMPLATE, pin)
        return

    # 2. sidecar
    data_dir = _find_data_dir(module_file)
    sidecar = None if data_dir is None else os.path.join(data_dir, "plugins", pin.SIDECAR_DIRNAME)
    if sidecar is not None and os.path.isdir(sidecar):
        wheel = os.path.join(sidecar, pin.CORE_WHEEL_NAME)
        try:
            present = os.path.lexists(wheel)
            names = [] if present else os.listdir(sidecar)
        except OSError:
            present, names = False, []
        if present:
            _admit_sidecar_wheel(pin, wheel, entry_path_object, entry_path)
            return
        if any(name.startswith(_CORE + "-") and name.endswith(".whl") for name in names):
            raise _error(_WHEEL_VERSION_MISMATCH_TEMPLATE, pin)

    # 3. 无有效 sidecar 且 Core 未加载：找不到 -> 什么也不做；找到任何来源 -> 在任何 import 之前拒绝
    try:
        spec = importlib.util.find_spec(_CORE)
    except Exception:
        raise _error(_UNVERIFIABLE_TEMPLATE, pin) from None
    if spec is not None:
        raise _error(_UNVERIFIABLE_TEMPLATE, pin)
