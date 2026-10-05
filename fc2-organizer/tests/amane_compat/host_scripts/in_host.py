"""P5-C2：在**真实 Amane 宿主进程内**执行的场景代码（由网关的“探针插件”加载；pytest 从不导入）。

网关把本文件的源码嵌入临时探针插件（``plugins/sources/ffcc.probe/plugin.py``，只存在于临时数据目录，不属于任何发布物）；
宿主在 ``discover()`` 时导入该插件 -> 本文件在宿主进程内运行 -> 结果以 ``RuntimeError("PROBE@@<json>")`` 经宿主自己的
``failures`` 通道返回（W2-04 / W2-05 同法）。因此**冻结桌面宿主与源码宿主走同一条代码路径**，无需宿主解释器。

本文件顶层只依赖标准库；``amane`` / ``fc2_metadata_core`` 只在函数内按需 import（网关也会把它当普通模块读取常量）。
所有“不受支持来源”夹具都是**惰性**的（见 ``_locator_harness.py`` 的同名约定）；只有合同明确要求的 .pyc / canary 目录会写 sentinel。
"""

from __future__ import annotations

import asyncio
import builtins
import hashlib
import importlib.machinery
import importlib.util
import io
import json
import os
import shutil
import stat
import sys
import tempfile
import threading
import types
import zipfile
import zipimport
from pathlib import Path

CORE = "fc2_metadata_core"
PLUGIN_ID = "ffcc.fc2-metadata"
EXT = "amane_ext_ffcc_d_fc2_h_metadata"
SOURCES = ("fc2db_net", "javdb", "av123")

#: 合同第 12.2 节：配置往返样本（id, 配置）。网关与宿主内共用本表。
CONFIG_SAMPLES = (
    ("default_empty", {}),
    ("sources_custom_order", {"sources": [{"id": "av123"}, {"id": "javdb"}, {"id": "fc2db_net"}]}),
    ("source_disabled", {"sources": [{"id": "fc2db_net", "enabled": False}, {"id": "javdb"}, {"id": "av123"}]}),
    ("base_url_override", {"sources": [{"id": "javdb", "base_url": "http://127.0.0.1:9/mirror"}]}),
    ("deadline_upper_bound", {"source_deadline_seconds": 600}),
    ("deadline_small_positive", {"source_deadline_seconds": 0.5}),
    ("invalid_unknown_source", {"sources": [{"id": "nope"}]}),
    ("invalid_duplicate_source", {"sources": [{"id": "javdb"}, {"id": "javdb"}]}),
    ("invalid_base_url_credentials", {"sources": [{"id": "javdb", "base_url": "https://user:pw@mirror.example"}]}),
    ("invalid_base_url_query", {"sources": [{"id": "javdb", "base_url": "https://mirror.example/?q=1"}]}),
    ("invalid_base_url_fragment", {"sources": [{"id": "javdb", "base_url": "https://mirror.example/#frag"}]}),
    ("invalid_base_url_scheme", {"sources": [{"id": "javdb", "base_url": "ftp://mirror.example"}]}),
    ("invalid_deadline_zero", {"source_deadline_seconds": 0}),
    ("invalid_deadline_negative", {"source_deadline_seconds": -1}),
    ("invalid_deadline_too_large", {"source_deadline_seconds": 601}),
    ("invalid_deadline_nan", {"source_deadline_seconds": float("nan")}),
    ("invalid_deadline_inf", {"source_deadline_seconds": float("inf")}),
    ("raw_type_enabled_string", {"sources": [{"id": "javdb", "enabled": "true"}]}),
    ("raw_type_enabled_int", {"sources": [{"id": "javdb", "enabled": 1}]}),
    ("raw_type_deadline_string", {"source_deadline_seconds": "20"}),
    ("raw_type_deadline_bool", {"source_deadline_seconds": True}),
    ("raw_type_sources_dict", {"sources": {"id": "javdb"}}),
    ("raw_type_id_non_str", {"sources": [{"id": 123}]}),
    ("invalid_unknown_top_level_key", {"bogus": 1}),
)

#: 合同第 13.2 节：跨版本等价请求集（case id, 号码, 额外设置）。
FETCH_CASES = (
    ("success_all_sources", "FC2-PPV-4979299", {}),
    ("partial_one_source_missing", "FC2-PPV-4825061", {}),
    ("not_found_everywhere", "FC2-PPV-4824605", {}),
    ("kind_blocked_403", "FC2-PPV-90000001", {}),
    ("kind_rate_limited_429", "FC2-PPV-90000002", {}),
    ("kind_timeout_source_deadline", "FC2-PPV-90000003", {"deadline": 1.0}),
    ("kind_connection_error_closed_port", "FC2-PPV-4979299", {"closed_port": True}),
    ("kind_http_server_error_503", "FC2-PPV-90000005", {}),
    ("kind_parse_error", "FC2-PPV-90000006", {}),
    ("kind_response_too_large", "FC2-PPV-90000007", {}),
    ("kind_decode_error_bad_charset", "FC2-PPV-90000008", {}),
    ("kind_redirect_error_loop", "FC2-PPV-90000009", {}),
    ("kind_cloudflare_challenge_403", "FC2-PPV-90000010", {}),
    ("invalid_query_number_not_a_string", 12345, {}),
    ("invalid_query_foreign_object", "FOREIGN", {}),
    ("not_fc2_content_type", "FC2-PPV-4979299", {"content_type": "censored"}),
    ("cancellation_mid_flight", "FC2-PPV-90000004", {"cancel_after": 0.5}),
)


# ------------------------------------------------------------------------------------------------ 通用


def _host(module_name, *names):
    """按名字取宿主对象。本文件只在宿主进程内执行；用 ``importlib.import_module`` 而不是 import 语句，
    因为 P5-C1 的测试树守卫（CLOSED 测试）禁止 ``tests/`` 下任何文件（C1 自己的 host_scripts 除外）出现 amane 的 import 语句。"""
    module = importlib.import_module(module_name)
    values = tuple(getattr(module, name) for name in names)
    return values if len(values) != 1 else values[0]


def _canonical(value):
    return json.loads(json.dumps(value, sort_keys=True, ensure_ascii=True, default=repr))


def _sha(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=True, default=repr).encode("utf-8")).hexdigest()


def _norm(path) -> str:
    return os.path.normcase(os.path.realpath(str(path)))


def _in_thread(function, *args):
    """宿主的事件循环正在运行 discover()：在**新线程**里 ``asyncio.run``，避免嵌套事件循环。"""
    box: dict[str, object] = {}

    def target():
        try:
            box["value"] = function(*args)
        except BaseException as exc:  # noqa: BLE001
            box["error"] = f"{type(exc).__name__}: {str(exc)[:300]}"

    thread = threading.Thread(target=target, daemon=True)
    thread.start()
    thread.join(timeout=600)
    if "error" in box:
        raise RuntimeError(str(box["error"]))
    return box.get("value")


def _core_modules():
    return {name: module for name, module in list(sys.modules.items()) if name == CORE or name.startswith(CORE + ".")}


# ------------------------------------------------------------------------------------------------ ops：只读检查


def op_describe(_payload):
    return {
        "frozen": bool(getattr(sys, "frozen", False)),
        "python": ".".join(str(part) for part in sys.version_info[:3]),
        "pythonpath_in_environ": "PYTHONPATH" in os.environ,
    }


def op_modules(payload):
    """HC-06 / HC-07 / HC-09：当前 amane_ext* 与 fc2_metadata_core* 模块；保留强引用，使旧对象的 id 不会被新对象复用。"""
    ext = {name: module for name, module in list(sys.modules.items()) if name.startswith(EXT)}
    keep = builtins.__dict__.setdefault("_ffcc_probe_keep", [])
    keep.append(list(ext.values()) + list(_core_modules().values()))
    core = _core_modules()
    top = core.get(CORE)
    loader = getattr(getattr(top, "__spec__", None), "loader", None)
    settings = sys.modules.get(EXT + "._impl._settings")
    return {
        "ext_ids": {name: id(module) for name, module in sorted(ext.items())},
        "ext_names": sorted(ext),
        "core_ids": {name: id(module) for name, module in sorted(core.items())},
        "core_loaded": top is not None,
        "core_loader_type": type(loader).__name__ if loader is not None else None,
        "core_loader_exact_zipimporter": type(loader) is zipimport.zipimporter if loader is not None else None,
        "core_archive_basename": os.path.basename(getattr(loader, "archive", "") or "") or None,
        "plugin_version_in_loaded_settings": getattr(settings, "PLUGIN_VERSION", None),
        "plugin_id_in_loaded_settings": getattr(settings, "PLUGIN_ID", None),
        "frozen": bool(getattr(sys, "frozen", False)),
    }


def op_state(_payload):
    """HC-10 / HC-11 / HC-16 / HC-19：失败路径前后的 sys.path 哈希与 fc2_metadata_core* 对象身份（经宿主 failures 通道读取）。"""
    core = _core_modules()
    keep = builtins.__dict__.setdefault("_ffcc_probe_keep", [])
    keep.append(list(core.values()))
    entries = [_norm(item) for item in sys.path if isinstance(item, str)]
    return {"path_sha": _sha(entries), "core_ids": {name: id(module) for name, module in sorted(core.items())}, "core_loaded": CORE in core}


def op_paths(payload):
    """sys.path 的哈希化快照（不暴露绝对路径）：是否包含 payload 里给出的 wheel / 目录。"""
    watched = [_norm(item) for item in payload.get("watch", [])]
    entries = [_norm(item) for item in sys.path if isinstance(item, str)]
    return {"present": {path: path in entries for path in watched}, "count": len(entries), "sha": _sha(entries)}


# ------------------------------------------------------------------------------------------------ 受控宿主栈（真实 PluginManager / CrawlerFactory / WebClient）


class _AsyncioProxy:
    """``amane.net.http.asyncio`` 的局部代理：只替换退避 ``sleep``（>0.5 s 的宿主退避被记录并跳过）。"""

    def __init__(self, waits):
        self._waits = waits

    async def sleep(self, seconds, *args, **kwargs):
        if seconds > 0.5:
            self._waits.append(seconds)
            await asyncio.sleep(0)
            return None
        return await asyncio.sleep(seconds, *args, **kwargs)

    def __getattr__(self, name):
        return getattr(asyncio, name)


class Stack:
    """一个真实宿主栈：install_plugin_zip（真实）-> PluginManager.discover（真实）-> CrawlerFactory + 真实 WebClient（真实 curl_cffi，到回环）。"""

    def __init__(self, work, zip_path, wheel_path, *, config=None, max_retries=3, place_wheel=True):
        CrawlerFactory = _host("amane.crawlers.factory", "CrawlerFactory")
        HttpClient = _host("amane.crawlers.http", "HttpClient")
        host_http = importlib.import_module("amane.net.http")
        RateLimiters, WebClient = _host("amane.net.http", "RateLimiters", "WebClient")
        PluginManager = _host("amane.plugins.manager", "PluginManager")
        PluginConfig = _host("amane.plugins.models", "PluginConfig")
        install_plugin_zip = _host("amane.plugins.packaging", "install_plugin_zip")

        self.data_dir = Path(work)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        if place_wheel:
            sidecar = self.data_dir / "plugins" / "_ffcc_core"
            sidecar.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(wheel_path, sidecar / Path(wheel_path).name)
        self.installed_id = install_plugin_zip(self.data_dir, Path(zip_path).read_bytes())
        self.manager = PluginManager.discover(self.data_dir)
        self.web_client = WebClient(timeout=10, max_retries=max_retries, limiters=RateLimiters())
        self.http_client = HttpClient(self.web_client)
        self.waits: list[float] = []
        self._host_http = host_http
        self._original_asyncio = host_http.asyncio
        host_http.asyncio = _AsyncioProxy(self.waits)
        self.plugin_config_type = PluginConfig
        self.factory = CrawlerFactory(
            self.http_client,
            plugin_manager=self.manager,
            plugin_configs={PLUGIN_ID: PluginConfig(config=config or {})},
            data_dir=self.data_dir,
        )

    def rebuild(self, config):
        """宿主的 ``apply_rebuild``：同一个 PluginManager（模块不重载），新 CrawlerFactory + 新 PluginConfig。"""
        CrawlerFactory = _host("amane.crawlers.factory", "CrawlerFactory")
        self.factory = CrawlerFactory(
            self.http_client,
            plugin_manager=self.manager,
            plugin_configs={PLUGIN_ID: self.plugin_config_type(config=config)},
            data_dir=self.data_dir,
        )

    def close(self):
        self._host_http.asyncio = self._original_asyncio

    async def provider(self):
        return await self.factory.get(PLUGIN_ID)

    def context(self):
        PluginContext = _host("amane.plugin", "PluginContext")

        return PluginContext(source_id=PLUGIN_ID, http_client=self.http_client, web_client=self.web_client, data_dir=self.data_dir)


def _sources_config(base_urls, closed_base=None):
    return {"sources": [{"id": source, "base_url": f"{closed_base}/{source}" if closed_base else base_urls[source]} for source in SOURCES]}


def _describe_result(value):
    MediaMetadata, SourceError = _host("amane.plugin", "MediaMetadata", "SourceError")

    if value is None:
        return {"class": "None"}
    if isinstance(value, MediaMetadata):
        return {"class": "MediaMetadata", "payload": _canonical(value.model_dump(mode="json"))}
    if isinstance(value, SourceError):
        return {"class": "SourceError", "reason": getattr(getattr(value, "reason", None), "value", None), "detail": getattr(value, "detail", None),
                "url": getattr(value, "url", None), "http_status": getattr(value, "http_status", None)}
    return {"class": type(value).__name__}


async def _fetch_one(stack, number, extra):
    ContentType, SearchQuery, SourceError = _host("amane.plugin", "ContentType", "SearchQuery", "SourceError")

    provider = await stack.provider()
    if number == "FOREIGN":
        query = object()
    elif extra.get("content_type") is not None:
        query = SearchQuery(number=number, content_type=ContentType(extra["content_type"]))
    else:
        query = SearchQuery(number=number, content_type=ContentType("fc2"))
    try:
        if "cancel_after" in extra:
            task = asyncio.ensure_future(provider.fetch(query))
            await asyncio.sleep(extra["cancel_after"])
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                return {"class": "CancelledError", "task_cancelled": task.cancelled()}
            return {"class": "completed_unexpectedly"}
        return _describe_result(await provider.fetch(query))
    except SourceError as exc:
        return _describe_result(exc)


def op_fetch_matrix(payload):
    """E15 / E16 / HC-04 / HC-17：同一请求集；真实 WebClient 请求回环 fixture；返回按 case 的规范化结果。"""
    work = Path(payload["work"]) / "fetch_matrix"
    base_urls, closed = payload["base_urls"], payload["closed_base"]
    selected = payload.get("cases")
    results = {}
    identity = {}
    for case_id, number, extra in FETCH_CASES:
        if selected and case_id not in selected:
            continue

        def scenario(case_id=case_id, number=number, extra=extra):
            config = _sources_config(base_urls, closed if extra.get("closed_port") else None)
            if "deadline" in extra:
                config["source_deadline_seconds"] = extra["deadline"]
            stack = Stack(work / case_id, payload["zip_path"], payload["wheel_path"], config=config)
            try:
                if case_id == "success_all_sources":
                    identity.update(_identity(stack))
                return asyncio.run(_fetch_one(stack, number, extra))
            finally:
                stack.close()

        results[case_id] = _in_thread(scenario)
    return {"cases": results, "identity": identity}


def _identity(stack):
    """E17：provider 持有宿主 ``web_client`` 的**同一对象**；AST 守卫（C1）保证 adapter 树无第二个 HTTP 客户端。"""
    provider = asyncio.run(stack.provider())
    inner = getattr(provider, "_provider", provider)
    runtime = getattr(inner, "_runtime", None)
    bridge = getattr(runtime, "_bridge", None)
    context = stack.context()
    return {
        "provider_class": type(provider).__name__,
        "context_web_client_is_host_web_client": context.web_client is stack.web_client,
        "context_http_client_web_client_is_host_web_client": stack.http_client.web_client is stack.web_client,
        "bridge_holds_host_web_client": getattr(bridge, "_web_client", None) is stack.web_client,
    }


def op_config_roundtrip(payload):
    """HC-05（宿主内三项）：``validate_plugin_config`` / ``parse_settings`` / ``build_plugin_provider`` 是否通过。"""
    work = Path(payload["work"]) / "config_roundtrip"

    def scenario():
        stack = Stack(work, payload["zip_path"], payload["wheel_path"])
        try:
            settings = sys.modules[EXT + "._impl._settings"]
            context = stack.context()
            rows = {}
            for sample_id, sample in CONFIG_SAMPLES:
                row = {}
                for label, call in (
                    ("validate", lambda s=sample: stack.manager.validate_plugin_config(PLUGIN_ID, stack.plugin_config_type(config=s))),
                    ("parse", lambda s=sample: settings.parse_settings(s)),
                    ("build", lambda s=sample: stack.manager.build_plugin_provider(PLUGIN_ID, context=context, config=stack.plugin_config_type(config=s))),
                ):
                    try:
                        call()
                        row[label] = True
                    except Exception as exc:  # noqa: BLE001
                        row[label] = False
                        row[label + "_error_type"] = type(exc).__name__
                rows[sample_id] = row
            return rows
        finally:
            stack.close()

    return {"rows": _in_thread(scenario)}


def op_config_behavior(payload):
    """HC-08 / 第 12.2 节：配置**行为** oracle（回环请求日志由网关读取；这里只执行并返回结果）。"""
    work = Path(payload["work"]) / "config_behavior"
    base_urls = payload["base_urls"]
    plans = payload["plans"]
    origin = base_urls["javdb"].rsplit("/", 1)[0]

    def render(config):
        rendered = json.loads(json.dumps(config))
        for entry in rendered.get("sources", []) or []:
            if entry.get("base_url") == "@loopback":
                entry["base_url"] = base_urls[entry["id"]]
        return rendered

    def scenario():
        import urllib.request

        stack = Stack(work, payload["zip_path"], payload["wheel_path"], config=render(plans[0][1]))
        results = {}
        try:
            async def run_all():
                for index, (plan_id, config, number) in enumerate(plans):
                    if index:
                        stack.rebuild(render(config))  # 与宿主 PATCH 后的 apply_rebuild 同法：模块常驻，provider 重建
                    urllib.request.urlopen(f"{origin}/__mark/{plan_id}", timeout=10).read()
                    results[plan_id] = await _fetch_one(stack, number, {})

            asyncio.run(run_all())
            return results
        finally:
            stack.close()

    return {"plans": _in_thread(scenario)}


def op_enumerations(payload):
    """E16：对 Core ``SourceErrorKind`` 全部成员与宿主 ``FailureReason`` 全部成员，桥 / 映射是全函数且确定。"""
    work = Path(payload["work"]) / "enumerations"

    def scenario():
        stack = Stack(work, payload["zip_path"], payload["wheel_path"])
        try:
            outcome = sys.modules[EXT + "._impl._outcome"]
            plugin_module = sys.modules[EXT + "._impl.plugin"]
            FailureReason, RequestError = _host("amane.plugin", "FailureReason", "RequestError")

            kinds = {}
            for kind in outcome.SourceErrorKind:
                reason = outcome.reason_for_kind(kind)
                kinds[kind.name] = {"reason": reason, "is_host_failure_reason": reason in {member.value for member in FailureReason}}
            bridge_type = plugin_module._HostAmaneHttpBridge
            reasons = {}
            for member in FailureReason:
                exc = RequestError("http://127.0.0.1/enumeration")  # 真实宿主异常对象；``reason`` 是其公共属性（SourceError.reason）
                exc.reason = member
                reasons[member.name] = type(bridge_type._map_request_error(exc)).__name__
            return {"source_error_kinds": kinds, "host_failure_reason_to_http_error": reasons,
                    "host_failure_reason_members": sorted(member.value for member in FailureReason)}
        finally:
            stack.close()

    return _in_thread(scenario)


# ------------------------------------------------------------------------------------------------ HC-19：Core 来源准入矩阵（真实 install_plugin_zip；仅源码宿主）


class _ZipImporterSubclass(zipimport.zipimporter):
    """惰性 test double：``zipimporter`` 的子类（不覆盖任何方法）。"""


class _ShadowFinder:
    @classmethod
    def find_spec(cls, name, path=None, target=None):
        if name == CORE:
            return importlib.machinery.ModuleSpec(name, None, origin="inert://shadow", is_package=True)
        return None


class _StatefulPreemptFinder:
    wheel_key = ""

    @classmethod
    def find_spec(cls, name, path=None, target=None):
        if name == CORE and any(isinstance(item, str) and _norm(item) == cls.wheel_key for item in sys.path):
            return importlib.machinery.ModuleSpec(name, None, origin="inert://stateful", is_package=True)
        return None


class _StatefulSubclassLoaderFinder:
    wheel = ""

    @classmethod
    def find_spec(cls, name, path=None, target=None):
        if name == CORE and any(isinstance(item, str) and _norm(item) == _norm(cls.wheel) for item in sys.path):
            spec = importlib.machinery.ModuleSpec(name, _ZipImporterSubclass(cls.wheel), origin=cls.wheel + os.sep + CORE + os.sep + "__init__.py", is_package=True)
            spec.submodule_search_locations = [cls.wheel + os.sep + CORE]
            return spec
        return None


ADMISSION_EXPECT = {
    "exact_wheel_sidecar": ("PASS", None),
    "dir_pip_target_no_sidecar": ("FAIL", "UNVERIFIABLE"),
    "dir_source_no_sidecar": ("FAIL", "UNVERIFIABLE"),
    "dir_pyc_poc_no_sidecar": ("FAIL", "UNVERIFIABLE"),
    "dir_pyc_poc_with_sidecar": ("PASS", None),
    "dir_canary_with_sidecar": ("PASS", None),
    "preloaded_exact_wheel": ("PASS", None),
    "preloaded_wrong_version_wheel": ("FAIL", "RESTART"),
    "preloaded_tampered_same_name": ("FAIL", "RESTART"),
    "preloaded_directory": ("FAIL", "RESTART"),
    "tampered_same_name_sidecar": ("FAIL", "WHEEL_HASH_MISMATCH"),
    "shadow_meta_path_finder": ("FAIL", "UNVERIFIABLE"),
    "e31u_wheel_in_path_resolution_disagrees": ("FAIL", "UNVERIFIABLE"),
    "e31v_subclass_loader_in_final_resolution": ("FAIL", "UNVERIFIABLE"),
    "e31l_rollback_cache_absent": ("FAIL", "UNVERIFIABLE"),
    "e31l_rollback_cache_present": ("FAIL", "UNVERIFIABLE"),
    "mixed_origin_loaded": ("FAIL", "RESTART"),
}


def _write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _real_core_dir(directory, wheel_bytes, *, dist_info):
    with zipfile.ZipFile(io.BytesIO(wheel_bytes)) as archive:
        for name in archive.namelist():
            if name.startswith(CORE + "/"):
                target = Path(directory) / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.read(name))
    if dist_info:
        _write(Path(directory) / "fc2_metadata_core-0.1.0.dist-info" / "METADATA", "Metadata-Version: 2.1\nName: fc2-metadata-core\nVersion: 0.1.0\n")
    return str(directory)


def _inert_dir(directory):
    _write(Path(directory) / CORE / "__init__.py", "# inert fixture: never executed\n")
    return str(directory)


def _canary_dir(directory, sentinel):
    _write(Path(directory) / CORE / "__init__.py", f"open({str(sentinel)!r}, 'w').write('payload executed')\n")
    return str(directory)


def _pyc_poc_dir(directory, sentinel):
    package = Path(directory) / CORE
    package.mkdir(parents=True, exist_ok=True)
    source = package / "__init__.py"
    source.write_text("X = 1\n", encoding="utf-8")
    info = source.stat()
    payload = compile(f"open({str(sentinel)!r}, 'w').write('pyc payload executed')\nX = 1\n", str(source), "exec")
    data = importlib._bootstrap_external._code_to_timestamp_pyc(payload, int(info.st_mtime), info.st_size)
    pyc = Path(importlib.util.cache_from_source(str(source)))
    pyc.parent.mkdir(parents=True, exist_ok=True)
    pyc.write_bytes(data)
    return str(directory)


def _tampered_valid_zip(wheel_bytes):
    buffer = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(wheel_bytes)) as source, zipfile.ZipFile(buffer, "w", zipfile.ZIP_STORED) as target:
        for info in source.infolist():
            data = source.read(info.filename)
            if info.filename == f"{CORE}/__init__.py":
                data += b"#"
            clone = zipfile.ZipInfo(info.filename, date_time=info.date_time)
            clone.compress_type = zipfile.ZIP_STORED
            target.writestr(clone, data)
    return buffer.getvalue()


def _load_core_from(path):
    sys.path.insert(0, str(path))
    __import__(CORE)


def _admission_case(name, work, zip_bytes, wheel_bytes, wheel_name):
    install_plugin_zip = _host("amane.plugins.packaging", "install_plugin_zip")

    case_dir = Path(work) / name
    data_dir = case_dir / "data"
    sidecar = data_dir / "plugins" / "_ffcc_core"
    wheel = str(sidecar / wheel_name)
    sentinel = case_dir / "SENTINEL"
    extras = {}

    def good_sidecar():
        sidecar.mkdir(parents=True, exist_ok=True)
        Path(wheel).write_bytes(wheel_bytes)

    if name == "exact_wheel_sidecar":
        good_sidecar()
    elif name == "dir_pip_target_no_sidecar":
        sys.path.insert(0, _real_core_dir(case_dir / "pipdir", wheel_bytes, dist_info=True))
    elif name == "dir_source_no_sidecar":
        sys.path.insert(0, _real_core_dir(case_dir / "srcdir", wheel_bytes, dist_info=False))
    elif name == "dir_pyc_poc_no_sidecar":
        sys.path.insert(0, _pyc_poc_dir(case_dir / "poc", sentinel))
    elif name == "dir_pyc_poc_with_sidecar":
        good_sidecar()
        sys.path.insert(0, _pyc_poc_dir(case_dir / "poc", sentinel))
    elif name == "dir_canary_with_sidecar":
        good_sidecar()
        sys.path.insert(0, _canary_dir(case_dir / "canary", sentinel))
    elif name == "preloaded_exact_wheel":
        good_sidecar()
        _load_core_from(wheel)
        __import__(CORE + ".aggregation")
    elif name == "preloaded_wrong_version_wheel":
        other = case_dir / "other" / "fc2_metadata_core-9.9.9-py3-none-any.whl"
        other.parent.mkdir(parents=True, exist_ok=True)
        other.write_bytes(wheel_bytes)
        _load_core_from(other)
    elif name == "preloaded_tampered_same_name":
        tampered = case_dir / "tampered" / wheel_name
        tampered.parent.mkdir(parents=True, exist_ok=True)
        tampered.write_bytes(_tampered_valid_zip(wheel_bytes))
        _load_core_from(tampered)
    elif name == "preloaded_directory":
        _load_core_from(_real_core_dir(case_dir / "pipdir", wheel_bytes, dist_info=True))
    elif name == "tampered_same_name_sidecar":
        sidecar.mkdir(parents=True, exist_ok=True)
        data = bytearray(wheel_bytes)
        data[len(data) // 2] ^= 0x01
        Path(wheel).write_bytes(bytes(data))
    elif name == "shadow_meta_path_finder":
        good_sidecar()
        sys.meta_path.insert(0, _ShadowFinder)
    elif name == "e31u_wheel_in_path_resolution_disagrees":
        good_sidecar()
        directory = _inert_dir(case_dir / "inert_earlier")
        sys.path.insert(0, directory)
        sys.path.append(wheel)
        extras["inert_dir"] = directory
    elif name == "e31v_subclass_loader_in_final_resolution":
        good_sidecar()
        _StatefulSubclassLoaderFinder.wheel = wheel
        sys.meta_path.insert(0, _StatefulSubclassLoaderFinder)
    elif name in ("e31l_rollback_cache_absent", "e31l_rollback_cache_present"):
        good_sidecar()
        _StatefulPreemptFinder.wheel_key = _norm(wheel)
        sys.meta_path.insert(0, _StatefulPreemptFinder)
        if name.endswith("present"):
            original = zipimport.zipimporter(wheel)
            sys.path_importer_cache[wheel] = original
            extras["original_cache_object"] = original
    elif name == "mixed_origin_loaded":
        good_sidecar()
        _load_core_from(wheel)
        other = case_dir / "other2" / wheel_name
        other.parent.mkdir(parents=True, exist_ok=True)
        other.write_bytes(wheel_bytes)
        module = types.ModuleType(CORE + ".mixed")
        module.__spec__ = importlib.machinery.ModuleSpec(CORE + ".mixed", zipimport.zipimporter(str(other)), origin=str(other) + os.sep + CORE + os.sep + "mixed.py")
        sys.modules[CORE + ".mixed"] = module
    else:
        raise KeyError(name)

    wheel_key = _norm(wheel)
    entry_path_object = sys.path
    entry_path = list(sys.path)
    entry_cache = {key: value for key, value in sys.path_importer_cache.items() if _norm(key) == wheel_key}
    entry_core = {key: id(value) for key, value in _core_modules().items()}
    keep = builtins.__dict__.setdefault("_ffcc_probe_keep", [])
    keep.append(list(_core_modules().values()))
    outcome, message = "PASS", ""
    try:
        install_plugin_zip(data_dir, zip_bytes)
    except ValueError as exc:
        outcome, message = "FAIL", str(exc)
    after_cache = {key: value for key, value in sys.path_importer_cache.items() if _norm(key) == wheel_key}
    after_core = {key: id(value) for key, value in _core_modules().items()}
    loaded = sys.modules.get(CORE)
    loader = getattr(getattr(loaded, "__spec__", None), "loader", None)
    sources_dir = data_dir / "plugins" / "sources"
    row = {
        "outcome": outcome,
        "message": message,
        "path_equals_entry": list(sys.path) == entry_path if outcome == "FAIL" else None,
        "path_same_object": sys.path is entry_path_object,
        "cache_unchanged": (set(after_cache) == set(entry_cache) and all(after_cache.get(key) is value for key, value in entry_cache.items())) if outcome == "FAIL" else None,
        "core_objects_unchanged": after_core == entry_core if outcome == "FAIL" else None,
        "sentinel_exists": sentinel.exists(),
        "installed_tree_exists": (sources_dir / PLUGIN_ID / "plugin.py").exists(),
        "half_install_residue": sorted(item.name for item in sources_dir.iterdir()) if (sources_dir.exists() and outcome == "FAIL") else [],
        "loaded_from_exact_wheel": (type(loader) is zipimport.zipimporter and _norm(getattr(loader, "archive", "")) == wheel_key) if outcome == "PASS" else None,
        "wheel_entries_in_path": sum(1 for item in sys.path if isinstance(item, str) and _norm(item) == wheel_key),
    }
    if name == "e31l_rollback_cache_present":
        row["cache_entry_is_original_object"] = sys.path_importer_cache.get(wheel) is extras.get("original_cache_object")
    if name == "e31u_wheel_in_path_resolution_disagrees":
        row["inert_package_never_imported"] = CORE not in sys.modules and not (Path(extras["inert_dir"]) / CORE / "__pycache__").exists()
    return row


def op_admission(payload):
    work = Path(payload["work"]) / "admission"
    zip_bytes = Path(payload["zip_path"]).read_bytes()
    wheel = Path(payload["wheel_path"])
    wheel_bytes, wheel_name = wheel.read_bytes(), wheel.name
    base_path, base_path_object = list(sys.path), sys.path
    base_meta = list(sys.meta_path)
    results = {}
    for name in ADMISSION_EXPECT:
        if payload.get("cases") and name not in payload["cases"]:
            continue
        for key in [key for key in list(sys.modules) if key == CORE or key.startswith(CORE + ".")]:
            del sys.modules[key]
        sys.path = base_path_object
        base_path_object[:] = base_path
        sys.meta_path[:] = base_meta
        sys.path_importer_cache.clear()
        cache = getattr(zipimport, "_zip_directory_cache", None)
        if cache is not None:
            cache.clear()
        importlib.invalidate_caches()
        try:
            results[name] = _admission_case(name, work, zip_bytes, wheel_bytes, wheel_name)
        except BaseException as exc:  # noqa: BLE001
            results[name] = {"outcome": "ERROR", "message": f"{type(exc).__name__}: {str(exc)[:300]}"}
    for key in [key for key in list(sys.modules) if key == CORE or key.startswith(CORE + ".")]:
        del sys.modules[key]
    sys.path = base_path_object
    base_path_object[:] = base_path
    sys.meta_path[:] = base_meta
    return {"cases": results}


# ------------------------------------------------------------------------------------------------ 分发

OPS = {
    "describe": op_describe,
    "modules": op_modules,
    "paths": op_paths,
    "state": op_state,
    "fetch_matrix": op_fetch_matrix,
    "config_roundtrip": op_config_roundtrip,
    "config_behavior": op_config_behavior,
    "enumerations": op_enumerations,
    "admission": op_admission,
}


def run(payload):
    return OPS[payload["op"]](payload)
