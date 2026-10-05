"""P5-C2 E31：locator 单元层的隔离 harness（不是 pytest 文件；pytest 从不导入）。

每次调用在**全新的解释器进程**里执行**一个**用例（避免污染主进程 ``sys.modules`` / ``sys.path``）：
在 ``--work`` 下布置夹具 -> 取入口快照 -> 调用 ``ensure_core`` -> 打印一行 ``@@CASE@@<json>`` 观测。

只依赖标准库（因而 3.12 与 3.14 都能直接运行）。所有“不受支持来源”夹具都是**惰性**的：
目录包的 ``__init__.py`` 只含注释；只有合同明确要求的 E31-g / E31-h 目录形态使用“写 sentinel 的 canary”，
canary 只有在 locator 错误地放行时才会触发，且只写入临时目录。

用法::

    python _locator_harness.py --case <id> --work <dir> --wheel <good.whl> --repo <repo-root> [--locator <path>]
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.machinery
import importlib.util
import io
import json
import os
import shutil
import stat
import subprocess
import sys
import types
import zipfile
import zipimport
from pathlib import Path

CORE = "fc2_metadata_core"
MARK = "@@CASE@@"
TEMPLATE_MARKERS = {
    "RESTART": "已加载的版本与插件不配对",
    "UNVERIFIABLE": "来源不受支持或无法验证",
    "WHEEL_VERSION_MISMATCH": "随附包版本与插件不配对",
    "WHEEL_HASH_MISMATCH": "随附包校验失败",
}


def norm(path):
    return os.path.normcase(os.path.realpath(str(path)))


class TrackedList(list):
    """记录对 ``sys.path`` 的任何修改次数（用来证明“预解析阶段从未修改 sys.path”）。"""

    mutations = 0

    def _count(self):
        type(self).mutations += 1


def _wrap(name):
    original = getattr(list, name)

    def method(self, *args, **kwargs):
        self._count()
        return original(self, *args, **kwargs)

    method.__name__ = name
    return method


for _name in ("append", "extend", "insert", "pop", "remove", "reverse", "sort", "clear", "__setitem__", "__delitem__", "__iadd__", "__imul__"):
    setattr(TrackedList, _name, _wrap(_name))


class Ctx:
    def __init__(self, options):
        self.work = Path(options.work).resolve()
        self.wheel_src = Path(options.wheel).resolve()
        self.repo = Path(options.repo).resolve()
        self.locator_path = Path(options.locator).resolve() if options.locator else self.repo / "adapters" / "amane" / "shim" / "_ffcc_locator.py"
        self.data_dir = self.work / "data"
        self.sidecar = self.data_dir / "plugins" / "_ffcc_core"
        self.plugin_dir = self.data_dir / "plugins" / "sources" / "ffcc.fc2-metadata"
        self.staging_dir = self.data_dir / "plugins" / "sources" / ".staging" / "x"
        self.module_file = str(self.plugin_dir / "plugin.py")
        self.sentinel = self.work / "SENTINEL_PAYLOAD_EXECUTED"
        self.pin = self._load_pin()
        self.locator = self._load("ffcc_locator_under_test", self.locator_path)
        self.sidecar_wheel = str(self.sidecar / self.pin.CORE_WHEEL_NAME)
        self.extras: dict[str, object] = {}

    @staticmethod
    def _load(name, path):
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def _load_pin(self):
        tools = self.repo / "tools" / "build_amane_release.py"
        release = self._load("ffcc_release_tool_under_test", tools)
        data = self.wheel_src.read_bytes()
        _tree, _members = release.inspect_core_wheel(data, self.wheel_src.name, "0.1.0")
        pin_dir = self.work / "pin"
        pin_dir.mkdir(parents=True, exist_ok=True)
        (pin_dir / "_ffcc_pin.py").write_bytes(
            release.render_pin(core_version="0.1.0", wheel_name=self.wheel_src.name, wheel_sha256=hashlib.sha256(data).hexdigest(), core_tree_sha256=_tree)
        )
        return self._load("ffcc_pin_under_test", pin_dir / "_ffcc_pin.py")

    def ensure(self, module_file=None):
        return self.locator.ensure_core(self.pin, module_file or self.module_file)

    def place_good_sidecar(self):
        self.sidecar.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(self.wheel_src, self.sidecar_wheel)

    def good_wheel_elsewhere(self, directory, name=None):
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / (name or self.pin.CORE_WHEEL_NAME)
        shutil.copyfile(self.wheel_src, target)
        return str(target)

    def tampered_valid_zip(self, directory):
        """同名、仍是合法 zip、但内容多 1 字节的 wheel（可被 zipimport 导入）。"""
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        buffer = io.BytesIO()
        with zipfile.ZipFile(self.wheel_src) as source, zipfile.ZipFile(buffer, "w", zipfile.ZIP_STORED) as target:
            for info in source.infolist():
                data = source.read(info.filename)
                if info.filename == f"{CORE}/__init__.py":
                    data += b"#"
                clone = zipfile.ZipInfo(info.filename, date_time=info.date_time)
                clone.compress_type = zipfile.ZIP_STORED
                target.writestr(clone, data)
        path = directory / self.pin.CORE_WHEEL_NAME
        path.write_bytes(buffer.getvalue())
        return str(path)

    def real_core_dir(self, directory, *, dist_info=False):
        directory = Path(directory)
        target = directory / CORE
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(self.repo / "src" / CORE, target, ignore=shutil.ignore_patterns("__pycache__"))
        if dist_info:
            info = directory / "fc2_metadata_core-0.1.0.dist-info"
            info.mkdir(exist_ok=True)
            (info / "METADATA").write_text("Metadata-Version: 2.1\nName: fc2-metadata-core\nVersion: 0.1.0\n", encoding="utf-8")
        return str(directory)

    def inert_dir_core(self, directory):
        package = Path(directory) / CORE
        package.mkdir(parents=True, exist_ok=True)
        (package / "__init__.py").write_text("# inert fixture: never executed\n", encoding="utf-8")
        return str(directory)

    def canary_dir_core(self, directory):
        package = Path(directory) / CORE
        package.mkdir(parents=True, exist_ok=True)
        (package / "__init__.py").write_text(f"open({str(self.sentinel)!r}, 'w').write('payload executed')\n", encoding="utf-8")
        return str(directory)

    def pyc_poc_dir(self, directory):
        """Reviewer 的 .pyc PoC（W2-12）：恶意 pyc 携带源文件相同 mtime / size；``*.py`` 内容不变。"""
        package = Path(directory) / CORE
        package.mkdir(parents=True, exist_ok=True)
        source = package / "__init__.py"
        source.write_text("X = 1\n", encoding="utf-8")
        info = source.stat()
        payload = compile(f"open({str(self.sentinel)!r}, 'w').write('pyc payload executed')\nX = 1\n", str(source), "exec")
        data = importlib._bootstrap_external._code_to_timestamp_pyc(payload, int(info.st_mtime), info.st_size)
        pyc = Path(importlib.util.cache_from_source(str(source)))
        pyc.parent.mkdir(parents=True, exist_ok=True)
        pyc.write_bytes(data)
        return str(directory)


def classify(message):
    for key, marker in TEMPLATE_MARKERS.items():
        if marker in message:
            return key
    return "OTHER"


def observe(ctx, call, *, wheel=None):
    wheel_path = wheel or ctx.sidecar_wheel
    wheel_key = norm(wheel_path)
    entry_path_object = sys.path
    entry_path = list(sys.path)
    entry_cache = {key: value for key, value in sys.path_importer_cache.items() if norm(key) == wheel_key}
    entry_modules = {key: id(value) for key, value in sys.modules.items() if key == CORE or key.startswith(CORE + ".")}
    entry_all_modules = set(sys.modules)
    mutations_before = TrackedList.mutations
    outcome, message, error_type = "PASS", "", ""
    try:
        call()
    except ImportError as exc:
        outcome, message = "FAIL", str(exc)
    except BaseException as exc:  # noqa: BLE001
        outcome, error_type = "ERROR", type(exc).__name__
        message = str(exc)
    after_cache = {key: value for key, value in sys.path_importer_cache.items() if norm(key) == wheel_key}
    after_modules = {key: id(value) for key, value in sys.modules.items() if key == CORE or key.startswith(CORE + ".")}
    observation = {
        "python": ".".join(str(part) for part in sys.version_info[:3]),
        "outcome": outcome,
        "error_type": error_type,
        "message": message,
        "template": classify(message) if outcome == "FAIL" else None,
        "path_equals_entry": list(sys.path) == entry_path,
        "path_same_object": sys.path is entry_path_object,
        "path_inserted": [item for item in sys.path if item not in entry_path],
        "path_mutations": TrackedList.mutations - mutations_before,
        "wheel_count_in_path": sum(1 for item in sys.path if isinstance(item, str) and norm(item) == wheel_key),
        "wheel_index_in_path": next((index for index, item in enumerate(sys.path) if isinstance(item, str) and norm(item) == wheel_key), None),
        "cache_keys_equal_entry": set(after_cache) == set(entry_cache),
        "cache_same_objects": all(after_cache.get(key) is value for key, value in entry_cache.items()),
        "entry_cache_had_wheel": bool(entry_cache),
        "core_modules_unchanged": after_modules == entry_modules,
        "core_modules_added": sorted(set(after_modules) - set(entry_modules)),
        "locator_imported_core": any(name == CORE or name.startswith(CORE + ".") for name in set(sys.modules) - entry_all_modules),
        "sentinel_exists": ctx.sentinel.exists(),
    }
    observation.update(ctx.extras)
    return observation


def import_core_and_describe(ctx):
    """（locator 之外）执行真实 import 以确认加载来源；仅在 locator 已放行之后调用。"""
    module = __import__(CORE)
    loader = module.__spec__.loader
    ctx.extras["loaded_loader_type"] = type(loader).__name__
    ctx.extras["loaded_archive_is_wheel"] = isinstance(getattr(loader, "archive", None), str) and norm(loader.archive) == norm(ctx.sidecar_wheel)
    ctx.extras["sentinel_exists"] = ctx.sentinel.exists()


# ---------------------------------------------------------------- 用例（case id 与合同 E31 子项一一对应）

CASES = {}


def case(name):
    def register(function):
        CASES[name] = function
        return function

    return register


def _load_core_from(path):
    sys.path.insert(0, str(path))
    __import__(CORE)


@case("a_loaded_exact_wheel")
def _(ctx):
    ctx.place_good_sidecar()
    _load_core_from(ctx.sidecar_wheel)
    __import__(CORE + ".aggregation")
    return observe(ctx, ctx.ensure)


@case("b_loaded_wrong_version_wheel")
def _(ctx):
    other = ctx.good_wheel_elsewhere(ctx.work / "other", "fc2_metadata_core-9.9.9-py3-none-any.whl")
    _load_core_from(other)
    return observe(ctx, ctx.ensure)


@case("c_loaded_tampered_same_name_wheel")
def _(ctx):
    tampered = ctx.tampered_valid_zip(ctx.work / "tampered")
    _load_core_from(tampered)
    return observe(ctx, ctx.ensure)


@case("d_loaded_directory_pip_target")
def _(ctx):
    _load_core_from(ctx.real_core_dir(ctx.work / "pipdir", dist_info=True))
    return observe(ctx, ctx.ensure)


@case("e_loaded_editable_source")
def _(ctx):
    _load_core_from(ctx.repo / "src")
    return observe(ctx, ctx.ensure)


@case("f_unloaded_directory_pip_target_no_sidecar")
def _(ctx):
    sys.path.insert(0, ctx.real_core_dir(ctx.work / "pipdir", dist_info=True))
    return observe(ctx, ctx.ensure)


@case("f_unloaded_directory_editable_no_sidecar")
def _(ctx):
    sys.path.insert(0, ctx.real_core_dir(ctx.work / "editable"))
    return observe(ctx, ctx.ensure)


@case("f_unloaded_source_checkout_no_sidecar")
def _(ctx):
    sys.path.insert(0, str(ctx.repo / "src"))
    return observe(ctx, ctx.ensure)


@case("f_unloaded_pythonpath_directory_no_sidecar")
def _(ctx):
    if os.environ.get("FFCC_REEXEC") != "1":
        directory = ctx.real_core_dir(ctx.work / "pythonpath_dir")
        env = dict(os.environ, PYTHONPATH=directory, FFCC_REEXEC="1")
        completed = subprocess.run([sys.executable, *sys.orig_argv[1:]], capture_output=True, text=True, env=env, check=False)
        sys.stdout.write(completed.stdout)
        sys.stderr.write(completed.stderr)
        raise SystemExit(completed.returncode)
    assert any(norm(item) == norm(ctx.work / "pythonpath_dir") for item in sys.path if item), "PYTHONPATH directory missing from sys.path"
    return observe(ctx, ctx.ensure)


@case("g_directory_core_with_valid_sidecar_loads_wheel")
def _(ctx):
    ctx.place_good_sidecar()
    sys.path.insert(0, ctx.canary_dir_core(ctx.work / "canary"))
    result = observe(ctx, ctx.ensure)
    import_core_and_describe(ctx)
    result.update(ctx.extras)
    return result


@case("h1_pyc_poc_directory_no_sidecar")
def _(ctx):
    sys.path.insert(0, ctx.pyc_poc_dir(ctx.work / "poc"))
    return observe(ctx, ctx.ensure)


@case("h2_pyc_poc_directory_with_valid_sidecar_loads_wheel")
def _(ctx):
    ctx.place_good_sidecar()
    sys.path.insert(0, ctx.pyc_poc_dir(ctx.work / "poc"))
    result = observe(ctx, ctx.ensure)
    import_core_and_describe(ctx)
    result.update(ctx.extras)
    return result


@case("h3_loaded_directory_with_benign_pyc")
def _(ctx):
    directory = ctx.inert_dir_core(ctx.work / "benign")
    sys.path.insert(0, directory)
    __import__(CORE)
    return observe(ctx, ctx.ensure)


@case("h0_pyc_poc_control_payload_runs_without_locator")
def _(ctx):
    """非空洞对照：不经 locator 直接 import PoC 目录，payload **会**执行（证明 h1/h2 的“不存在”不是虚假的）。"""
    sys.path.insert(0, ctx.pyc_poc_dir(ctx.work / "poc"))
    __import__(CORE)
    return {"python": ".".join(str(part) for part in sys.version_info[:3]), "sentinel_exists": ctx.sentinel.exists(), "outcome": "CONTROL"}


@case("i_sidecar_tampered_one_byte")
def _(ctx):
    ctx.place_good_sidecar()
    data = bytearray(Path(ctx.sidecar_wheel).read_bytes())
    data[len(data) // 2] ^= 0x01
    Path(ctx.sidecar_wheel).write_bytes(bytes(data))
    return observe(ctx, ctx.ensure)


@case("i_sidecar_symlink")
def _(ctx):
    ctx.sidecar.mkdir(parents=True, exist_ok=True)
    target = ctx.good_wheel_elsewhere(ctx.work / "linktarget", "real.whl")
    privilege = True
    try:
        os.symlink(target, ctx.sidecar_wheel)
    except (OSError, NotImplementedError):
        privilege = False
        shutil.copyfile(target, ctx.sidecar_wheel)
        real_lstat = os.lstat
        wheel = ctx.sidecar_wheel

        def lstat_stub(path, *args, **kwargs):
            if os.fspath(path) == wheel:
                return os.stat_result((stat.S_IFLNK | 0o777, 0, 0, 1, 0, 0, 10, 0, 0, 0))
            return real_lstat(path, *args, **kwargs)

        os.lstat = lstat_stub
    ctx.extras["symlink_privilege"] = privilege
    return observe(ctx, ctx.ensure)


@case("i_sidecar_oversize")
def _(ctx):
    ctx.sidecar.mkdir(parents=True, exist_ok=True)
    with open(ctx.sidecar_wheel, "wb") as handle:
        handle.write(Path(ctx.wheel_src).read_bytes())
        handle.write(b"\0" * (16 * 1024 * 1024 + 1))
    return observe(ctx, ctx.ensure)


@case("i_sidecar_same_name_directory")
def _(ctx):
    os.makedirs(ctx.sidecar_wheel, exist_ok=True)
    return observe(ctx, ctx.ensure)


@case("i_sidecar_only_other_version_wheel")
def _(ctx):
    ctx.good_wheel_elsewhere(ctx.sidecar, "fc2_metadata_core-9.9.9-py3-none-any.whl")
    return observe(ctx, ctx.ensure)


@case("j_mixed_submodule_other_archive")
def _(ctx):
    ctx.place_good_sidecar()
    _load_core_from(ctx.sidecar_wheel)
    other = ctx.good_wheel_elsewhere(ctx.work / "other2")
    importer = zipimport.zipimporter(other)
    module = types.ModuleType(CORE + ".mixed")
    module.__spec__ = importlib.machinery.ModuleSpec(CORE + ".mixed", importer, origin=other + os.sep + CORE + os.sep + "mixed.py")
    sys.modules[CORE + ".mixed"] = module
    return observe(ctx, ctx.ensure)


@case("j_mixed_submodule_directory_origin")
def _(ctx):
    ctx.place_good_sidecar()
    _load_core_from(ctx.sidecar_wheel)
    directory = ctx.inert_dir_core(ctx.work / "dirsub")
    module = types.ModuleType(CORE + ".mixed")
    loader = importlib.machinery.SourceFileLoader(CORE + ".mixed", str(Path(directory) / CORE / "__init__.py"))
    module.__spec__ = importlib.machinery.ModuleSpec(CORE + ".mixed", loader, origin=str(Path(directory) / CORE / "__init__.py"))
    sys.modules[CORE + ".mixed"] = module
    return observe(ctx, ctx.ensure)


@case("j_mixed_submodule_no_spec")
def _(ctx):
    ctx.place_good_sidecar()
    _load_core_from(ctx.sidecar_wheel)
    module = types.ModuleType(CORE + ".mixed")
    module.__spec__ = None
    sys.modules[CORE + ".mixed"] = module
    return observe(ctx, ctx.ensure)


@case("j_mixed_submodule_namespace_package")
def _(ctx):
    ctx.place_good_sidecar()
    _load_core_from(ctx.sidecar_wheel)
    module = types.ModuleType(CORE + ".mixed")
    spec = importlib.machinery.ModuleSpec(CORE + ".mixed", None, is_package=True)
    spec.submodule_search_locations = []
    module.__spec__ = spec
    sys.modules[CORE + ".mixed"] = module
    return observe(ctx, ctx.ensure)


class ZipImporterSubclass(zipimport.zipimporter):
    """惰性 test double：``zipimporter`` 的子类（不覆盖任何方法）。"""


@case("j_mixed_submodule_subclass_loader")
def _(ctx):
    ctx.place_good_sidecar()
    _load_core_from(ctx.sidecar_wheel)
    importer = ZipImporterSubclass(ctx.sidecar_wheel)
    module = types.ModuleType(CORE + ".mixed")
    module.__spec__ = importlib.machinery.ModuleSpec(CORE + ".mixed", importer, origin=ctx.sidecar_wheel + os.sep + CORE + os.sep + "mixed.py")
    sys.modules[CORE + ".mixed"] = module
    return observe(ctx, ctx.ensure)


class ShadowFinder:
    """惰性 finder：无条件为 ``fc2_metadata_core`` 返回一个 spec（遮蔽）。"""

    @classmethod
    def find_spec(cls, name, path=None, target=None):
        if name == CORE:
            return importlib.machinery.ModuleSpec(name, None, origin="inert://shadow", is_package=True)
        return None


@case("k_shadow_meta_path_finder_with_valid_sidecar")
def _(ctx):
    ctx.place_good_sidecar()
    sys.meta_path.insert(0, ShadowFinder)
    return observe(ctx, ctx.ensure)


@case("k_shadow_meta_path_finder_no_sidecar")
def _(ctx):
    sys.meta_path.insert(0, ShadowFinder)
    return observe(ctx, ctx.ensure)


class StatefulPreemptFinder:
    """惰性 finder：只有当 verified wheel 已进入 ``sys.path`` 之后才抢占（预解析时它不抢占）。"""

    wheel_key = ""

    @classmethod
    def find_spec(cls, name, path=None, target=None):
        if name == CORE and any(isinstance(item, str) and norm(item) == cls.wheel_key for item in sys.path):
            return importlib.machinery.ModuleSpec(name, None, origin="inert://stateful", is_package=True)
        return None


class StatefulSubclassLoaderFinder:
    """惰性 finder：wheel 进入 ``sys.path`` 之后返回 loader 为 zipimporter 子类实例的 spec（archive / origin 都在 verified wheel 内）。"""

    wheel = ""

    @classmethod
    def find_spec(cls, name, path=None, target=None):
        if name == CORE and any(isinstance(item, str) and norm(item) == norm(cls.wheel) for item in sys.path):
            importer = ZipImporterSubclass(cls.wheel)
            spec = importlib.machinery.ModuleSpec(name, importer, origin=cls.wheel + os.sep + CORE + os.sep + "__init__.py", is_package=True)
            spec.submodule_search_locations = [cls.wheel + os.sep + CORE]
            return spec
        return None


@case("l1_rollback_after_insertion_cache_absent_at_entry")
def _(ctx):
    ctx.place_good_sidecar()
    StatefulPreemptFinder.wheel_key = norm(ctx.sidecar_wheel)
    sys.meta_path.insert(0, StatefulPreemptFinder)
    return observe(ctx, ctx.ensure)


@case("l2_rollback_after_insertion_cache_present_at_entry")
def _(ctx):
    ctx.place_good_sidecar()
    StatefulPreemptFinder.wheel_key = norm(ctx.sidecar_wheel)
    sys.meta_path.insert(0, StatefulPreemptFinder)
    original = zipimport.zipimporter(ctx.sidecar_wheel)
    sys.path_importer_cache[ctx.sidecar_wheel] = original
    result = observe(ctx, ctx.ensure)
    result["cache_entry_is_original_object"] = sys.path_importer_cache.get(ctx.sidecar_wheel) is original
    return result


@case("m_sidecar_same_name_directory_with_directory_core")
def _(ctx):
    os.makedirs(ctx.sidecar_wheel, exist_ok=True)
    sys.path.insert(0, ctx.canary_dir_core(ctx.work / "canary"))
    return observe(ctx, ctx.ensure)


@case("o_no_core_no_sidecar")
def _(ctx):
    return observe(ctx, ctx.ensure)


@case("o_empty_sidecar_directory")
def _(ctx):
    ctx.sidecar.mkdir(parents=True, exist_ok=True)
    return observe(ctx, ctx.ensure)


@case("o_module_file_outside_plugins_sources")
def _(ctx):
    ctx.place_good_sidecar()
    return observe(ctx, lambda: ctx.ensure(str(ctx.work / "elsewhere" / "plugin.py")))


class CountingFinder:
    calls = 0

    @classmethod
    def find_spec(cls, name, path=None, target=None):
        if name == CORE:
            cls.calls += 1
        return None


@case("p_success_single_insertion_and_idempotent_with_final_resolution")
def _(ctx):
    ctx.place_good_sidecar()
    sys.meta_path.insert(0, CountingFinder)
    first = observe(ctx, ctx.ensure)
    first_path = list(sys.path)
    calls_after_first = CountingFinder.calls
    second = observe(ctx, ctx.ensure)
    first["second_outcome"] = second["outcome"]
    first["second_path_equals_first"] = list(sys.path) == first_path
    first["second_path_mutations"] = second["path_mutations"]
    first["second_wheel_count"] = second["wheel_count_in_path"]
    first["second_final_resolution_calls"] = CountingFinder.calls - calls_after_first
    import_core_and_describe(ctx)
    first.update(ctx.extras)
    return first


@case("p_success_from_staging_module_file")
def _(ctx):
    ctx.place_good_sidecar()
    return observe(ctx, lambda: ctx.ensure(str(ctx.staging_dir / "plugin.py")))


@case("u_existing_wheel_but_resolution_disagrees")
def _(ctx):
    ctx.place_good_sidecar()
    directory = ctx.inert_dir_core(ctx.work / "inert_earlier")
    sys.path.insert(0, directory)
    sys.path.append(ctx.sidecar_wheel)
    result = observe(ctx, ctx.ensure)
    result["inert_package_never_imported"] = CORE not in sys.modules and not (Path(directory) / CORE / "__pycache__").exists()
    return result


@case("u_existing_wheel_first_and_resolution_matches")
def _(ctx):
    ctx.place_good_sidecar()
    sys.path.append(str(ctx.inert_dir_core(ctx.work / "inert_later")))
    sys.path.insert(0, ctx.sidecar_wheel)
    return observe(ctx, ctx.ensure)


@case("v_subclass_loader_double_in_final_resolution")
def _(ctx):
    ctx.place_good_sidecar()
    StatefulSubclassLoaderFinder.wheel = ctx.sidecar_wheel
    sys.meta_path.insert(0, StatefulSubclassLoaderFinder)
    return observe(ctx, ctx.ensure)


@case("v_subclass_loader_double_in_pre_resolution")
def _(ctx):
    ctx.place_good_sidecar()

    class PreFinder:
        @classmethod
        def find_spec(cls, name, path=None, target=None):
            if name == CORE:
                importer = ZipImporterSubclass(ctx.sidecar_wheel)
                spec = importlib.machinery.ModuleSpec(name, importer, origin=ctx.sidecar_wheel + os.sep + CORE + os.sep + "__init__.py", is_package=True)
                spec.submodule_search_locations = [ctx.sidecar_wheel + os.sep + CORE]
                return spec
            return None

    sys.meta_path.insert(0, PreFinder)
    return observe(ctx, ctx.ensure)


@case("v_loaded_core_with_subclass_loader_double")
def _(ctx):
    ctx.place_good_sidecar()
    importer = ZipImporterSubclass(ctx.sidecar_wheel)
    module = types.ModuleType(CORE)
    spec = importlib.machinery.ModuleSpec(CORE, importer, origin=ctx.sidecar_wheel + os.sep + CORE + os.sep + "__init__.py", is_package=True)
    spec.submodule_search_locations = [ctx.sidecar_wheel + os.sep + CORE]
    module.__spec__ = spec
    sys.modules[CORE] = module
    return observe(ctx, ctx.ensure)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--work", required=True)
    parser.add_argument("--wheel", required=True)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--locator")
    options = parser.parse_args(argv)
    Path(options.work).mkdir(parents=True, exist_ok=True)
    sys.path[:] = [item for item in sys.path if item]
    sys.path = TrackedList(sys.path)
    ctx = Ctx(options)
    result = CASES[options.case](ctx)
    print(MARK + json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
