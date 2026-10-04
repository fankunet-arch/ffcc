"""P5-C1 真实宿主见证场景 H-01..H-15（**只在 Python >= 3.14 且已安装 Amane v0.15.0 的子进程内执行**）。

由 ``tools/run_amane_host_witness.py`` 逐场景以独立子进程调用：

    python h_scenarios.py --scenario H-07 --repo-root <fc2-organizer> --amane-src <checkout>
        --core-src <fc2-organizer/src> --adapter-tree <tree> --work-dir <tmp>

每个场景断言失败 -> ``passed = false``。观察值（``observations``）**不含**时间戳 / 耗时 / 端口 / 临时路径，
保证同一环境下的日志可复现。传输层是脚本化的 ``WebClient._session``（无真实网络）；
唯一的网络活动是 H-09 的回环 HTTP 服务器（127.0.0.1）。
"""

from __future__ import annotations

import argparse
import asyncio
import io
import json
import logging
import os
import socket
import subprocess
import sys
import zipfile
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from h_common import (  # noqa: E402
    AMANE_COMMIT,
    HANG,
    PLUGIN_ID,
    SOURCES,
    Context,
    FakeRecorder,
    RedirectLoopServer,
    ScriptedSession,
    discover,
    fixture,
    install_tree,
    invoke,
    load_tool,
    make_host,
    make_response,
    page,
    prepare_paths,
    query,
    runtime_of,
    session_4825061,
    session_4979299,
    session_not_found_4824605,
    stable_json,
    uniform_session,
    url_for,
)

TITLE_4979299 = "夢は小学校の先生。天使のような笑顔と色白美巨乳♡ほのぼの系美女のおじさま２人への体当たり性指導映像。"
SECRET_WORDS = ("token", "secret", "password", "api_key", "cookie", "credential", "dsn")
MODULE_FILES = ("_bridge", "_core_gate", "_number", "_outcome", "_runtime", "_settings")
REDIRECT_HOPS = 21  # R + 1，R = 20（宿主 max_redirects；真实 curl_cffi 实测见 H-09）


def check(condition: object, message: str = "assertion failed") -> None:
    if not condition:
        raise AssertionError(message)


def run(coro):
    return asyncio.run(coro)


# ===================================================================================================== H-01


def h01(ctx: Context) -> dict:
    import importlib.metadata

    import amane.plugin as plugin

    version = importlib.metadata.version("amane")
    check(version == "0.15.0", f"amane version {version}")
    commit = subprocess.run(["git", "-C", str(ctx.amane_src), "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    check(commit == AMANE_COMMIT, f"amane commit {commit}")
    dirty = subprocess.run(["git", "-C", str(ctx.amane_src), "status", "--porcelain"], capture_output=True, text=True, check=True).stdout.strip()
    check(dirty == "", "the amane checkout must be clean")
    check(ctx.amane_src.resolve() in Path(plugin.__file__).resolve().parents, "amane must be imported from the exact checkout")
    check(sys.version_info >= (3, 14), "Python >= 3.14 required")

    tool = load_tool(ctx, "amane_api_manifest")
    regenerated = tool.render(tool.build_manifest(ctx.amane_src))
    committed = (ctx.repo_root / "adapters" / "amane" / "api_manifest" / "amane_v0.15.0_api_manifest.json").read_text(encoding="utf-8")
    check(regenerated == committed.replace("\r\n", "\n"), "the committed API manifest must equal the regenerated one")
    manifest = json.loads(regenerated)
    missing = [name for name in manifest["plugin_all"] if not hasattr(plugin, name)]
    check(not missing, f"names in the manifest but not importable: {missing}")
    for name in ("FilmSourcePlugin", "FilmSourceProvider", "PluginContext", "SearchQuery", "FetchOptions", "MediaMetadata", "FilmActor",
                 "SourceDescriptor", "SourceCapability", "ContentType", "FailureReason", "SourceError", "RequestError", "WebClient",
                 "PLUGIN_API_VERSION"):
        check(hasattr(plugin, name), name)
    return {
        "python": ".".join(str(part) for part in sys.version_info[:3]),
        "amane_version": version,
        "amane_commit": commit,
        "checkout_clean": True,
        "imported_from_checkout": True,
        "manifest_equals_regenerated": True,
        "plugin_all_count": len(manifest["plugin_all"]),
    }


# ===================================================================================================== H-02


EXPECTED_DESCRIPTOR = {
    "id": PLUGIN_ID,
    "name": "FC2 Metadata (ffcc)",
    "version": "0.1.0",
    "api_version": "1",
    "capabilities": ["film_metadata"],
    "content_types": ["fc2"],
    "metadata_fields": sorted(
        ["title", "plot", "actors", "tags", "release", "runtime", "publisher", "studio", "poster_urls", "thumb_urls", "extrafanart"]
    ),
    "languages": [],
    "urls": ["https://fc2db.net", "https://javdb.com", "https://123av.com"],
    "multi_language": False,
    "rate_limit": None,
}


def _descriptor_dict(descriptor) -> dict:
    return {
        "id": descriptor.id,
        "name": descriptor.name,
        "version": descriptor.version,
        "api_version": descriptor.api_version,
        "capabilities": sorted(descriptor.capabilities),
        "content_types": sorted(descriptor.content_types),
        "metadata_fields": sorted(descriptor.metadata_fields),
        "languages": sorted(descriptor.languages),
        "urls": list(descriptor.urls),
        "multi_language": descriptor.multi_language,
        "rate_limit": descriptor.rate_limit,
    }


def _schema_property_names(node) -> list[str]:
    names: list[str] = []
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "properties" and isinstance(value, dict):
                names.extend(value)
            names.extend(_schema_property_names(value))
    elif isinstance(node, list):
        for item in node:
            names.extend(_schema_property_names(item))
    return names


def h02(ctx: Context) -> dict:
    zip_tool = load_tool(ctx, "build_amane_plugin_zip")
    observations: dict[str, object] = {}
    for label in ("tree", "zip"):
        data_dir = ctx.work_dir / f"h02_{label}"
        if label == "tree":
            install_tree(ctx, data_dir)
        else:
            with zipfile.ZipFile(io.BytesIO(zip_tool.build_zip_bytes(ctx.adapter_tree))) as archive:
                archive.extractall(data_dir / "plugins" / "sources")
        manager = discover(data_dir)
        check(PLUGIN_ID in manager.plugin_ids(), f"{label}: {[f.error for f in manager.failures]}")
        check(not manager.failures, f"{label}: failures")
        actual = _descriptor_dict(manager.descriptor(PLUGIN_ID))
        check(actual == EXPECTED_DESCRIPTOR, f"{label}: descriptor mismatch {actual}")
        schema = manager.plugin_config_schema(PLUGIN_ID)
        names = sorted(set(_schema_property_names(schema)))
        check(names == ["base_url", "enabled", "id", "source_deadline_seconds", "sources"], f"{label}: schema fields {names}")
        check(not any(word in name for name in names for word in SECRET_WORDS), "secret-like configuration field name")
        loaded = sorted(key for key in sys.modules if key.startswith("amane_ext_ffcc_d_fc2_h_metadata"))
        expected_modules = sorted(["amane_ext_ffcc_d_fc2_h_metadata", *(f"amane_ext_ffcc_d_fc2_h_metadata.{m}" for m in MODULE_FILES)])
        check(set(expected_modules) <= set(loaded), f"{label}: sibling modules not loaded as package members: {loaded}")
        check(not (data_dir / "plugins" / "sources" / PLUGIN_ID / "__init__.py").exists(), "no __init__.py")
        observations[label] = {"descriptor": actual, "schema_fields": names, "loaded_modules": loaded}
    return observations


# ===================================================================================================== H-03


def h03(ctx: Context) -> dict:
    from amane.plugins.packaging import install_plugin_path, install_plugin_zip

    tool = load_tool(ctx, "build_amane_plugin_zip")
    payload = tool.build_zip_bytes(ctx.adapter_tree)
    check(tool.build_zip_bytes(ctx.adapter_tree) == payload, "deterministic zip")
    data_dir = ctx.work_dir / "h03"
    installed_id = install_plugin_zip(data_dir, payload)
    check(installed_id == PLUGIN_ID, installed_id)
    directory = data_dir / "plugins" / "sources" / PLUGIN_ID
    check(directory.name == PLUGIN_ID and directory.is_dir(), "installed directory name equals the id")
    names = sorted(p.name for p in directory.iterdir() if p.name != "__pycache__")
    check(names == sorted(f"{m}.py" for m in (*MODULE_FILES, "plugin")), names)
    check(not (data_dir / "plugins" / "sources" / ".staging").exists(), "staging residue")
    manager = discover(data_dir)
    check(PLUGIN_ID in manager.plugin_ids() and not manager.failures, "discover after install")
    check(install_plugin_zip(data_dir, payload) == PLUGIN_ID, "reinstall replaces the tree")
    check(sorted(p.name for p in directory.iterdir() if p.name != "__pycache__") == names, "reinstall result")
    second = ctx.work_dir / "h03_path"
    check(install_plugin_path(second, ctx.adapter_tree) == PLUGIN_ID, "install_plugin_path")
    check(PLUGIN_ID in discover(second).plugin_ids(), "discover after install_plugin_path")
    return {"installed_id": installed_id, "installed_files": names, "zip_sha256": __import__("hashlib").sha256(payload).hexdigest()}


# ===================================================================================================== H-04


def h04(ctx: Context) -> dict:
    from pydantic import ValidationError

    from amane.config.manager import HotSettings
    from amane.plugins.models import PluginConfig

    data_dir = ctx.work_dir / "h04"
    install_tree(ctx, data_dir)
    manager = discover(data_dir)
    check(PLUGIN_ID in manager.plugin_ids(), "plugin discovered")
    model = manager.get(PLUGIN_ID).configuration_model()
    valid = [
        {},
        {"sources": None},
        {"sources": [{"id": "javdb"}]},
        {"sources": [{"id": "av123", "enabled": False}, {"id": "javdb", "base_url": "https://mirror.example/prefix"}]},
        {"source_deadline_seconds": 600},
        {"source_deadline_seconds": 0.5},
    ]
    for config in valid:
        manager.validate_plugin_config(PLUGIN_ID, PluginConfig(config=config))
        model.model_validate(config)
    invalid = [
        {"sources": [{"id": "nope"}]},
        {"sources": [{"id": "javdb"}, {"id": "javdb"}]},
        {"sources": []},
        {"sources": [{"id": "javdb", "enabled": False}]},
        {"sources": [{"id": "javdb", "base_url": "https://user:pw@mirror.example"}]},
        {"sources": [{"id": "javdb", "base_url": "ftp://mirror.example"}]},
        {"sources": [{"id": "javdb", "base_url": "https://mirror.example/?q=1"}]},
        {"sources": [{"id": "javdb", "enabled": "yes"}]},
        {"sources": [{"id": "javdb", "extra": 1}]},
        {"sources": [{"id": 5}]},
        {"source_deadline_seconds": 0},
        {"source_deadline_seconds": -1},
        {"source_deadline_seconds": float("nan")},
        {"source_deadline_seconds": float("inf")},
        {"source_deadline_seconds": 601},
        {"source_deadline_seconds": True},
        {"source_deadline_seconds": "x"},
        {"unknown_field": 1},
    ]
    rejected = 0
    for config in invalid:
        try:
            model.model_validate(config)
        except ValidationError:
            rejected += 1
        else:
            raise AssertionError(f"accepted an invalid configuration: {config}")
    # 宿主路由校验（HotSettings -> PluginManager.validate_hot_settings）
    def hot(**scraping_and_plugins):
        return HotSettings.model_validate(scraping_and_plugins)

    manager.validate_hot_settings(hot(scraping={"content_routes": {"fc2": [PLUGIN_ID]}}))
    manager.validate_hot_settings(hot(scraping={"field_priority": {"title": [PLUGIN_ID]}}))
    manager.validate_hot_settings(hot(plugins={PLUGIN_ID: {"enabled": True, "config": {"sources": [{"id": "javdb"}]}}}))
    for bad in (
        hot(scraping={"content_routes": {"censored": [PLUGIN_ID]}}),
        hot(scraping={"field_priority": {"directors": [PLUGIN_ID]}}),
        hot(plugins={PLUGIN_ID: {"enabled": True, "config": {"sources": [{"id": "nope"}]}}}),
    ):
        try:
            manager.validate_hot_settings(bad)
        except (ValueError, ValidationError):
            pass
        else:
            raise AssertionError("host validation accepted an invalid route / config")
    # P5-C1-L1-01：宿主入口必须与 parse_settings 语义一致——原始的可强制转换字符串（"20" 等）不得先被 Pydantic 转成 20.0。
    from support.amane_config_matrix import CONFIG_MATRIX, RAW_STRING_DEADLINES

    settings_module = sys.modules[type(manager.get(PLUGIN_ID)).__module__ + "._settings"]
    parse_settings, adapter_config_error = settings_module.parse_settings, settings_module.AdapterConfigError

    def accepted_by(call, error_types) -> bool:
        try:
            call()
        except error_types:
            return False
        return True

    for raw in RAW_STRING_DEADLINES:
        check(not accepted_by(lambda: model.model_validate({"source_deadline_seconds": raw}), ValidationError),
              f"the host model must reject the coercible raw string {raw!r}")
        check(not accepted_by(lambda: manager.validate_plugin_config(PLUGIN_ID, PluginConfig(config={"source_deadline_seconds": raw})),
                              (ValidationError, ValueError)), f"validate_plugin_config must reject {raw!r}")
        try:
            manager.validate_hot_settings(hot(plugins={PLUGIN_ID: {"enabled": True, "config": {"source_deadline_seconds": raw}}}))
        except (ValueError, ValidationError):
            pass
        else:
            raise AssertionError(f"HotSettings route accepted the raw string {raw!r}")
    parity_rows = 0
    for label, config, expected in CONFIG_MATRIX:
        host_ok = accepted_by(lambda: model.model_validate(config), ValidationError)
        manager_ok = accepted_by(lambda: manager.validate_plugin_config(PLUGIN_ID, PluginConfig(config=config)), (ValidationError, ValueError))
        parser_ok = accepted_by(lambda: parse_settings(config), adapter_config_error)
        check(host_ok == manager_ok == parser_ok == expected,
              f"host model / validate_plugin_config / parse_settings / expected disagree for {label}: {host_ok} {manager_ok} {parser_ok} {expected}")
        parity_rows += 1
    return {"valid_configurations": len(valid), "rejected_configurations": rejected,
            "route_matrix": "fc2 accepted; censored, directors, bad config rejected",
            "raw_type_matrix": {"rows": parity_rows, "parity": "host model == validate_plugin_config == parse_settings == expected for every row",
                                "raw_strings_rejected": list(RAW_STRING_DEADLINES), "hot_settings_route_rejects_raw_strings": True}}


# ===================================================================================================== H-05


MISSING_MESSAGE = "FC2 Metadata Core 未安装或版本不兼容：请在 Amane 所在的 Python 环境中安装 fc2-metadata-core（缺失模块：{name}）"


def _purge_core_modules() -> None:
    for name in [key for key in sys.modules if key == "fc2_metadata_core" or key.startswith("fc2_metadata_core.")]:
        del sys.modules[name]


def h05(ctx: Context) -> dict:
    import importlib.abc
    import shutil

    from amane.plugins.packaging import install_plugin_path

    class Block(importlib.abc.MetaPathFinder):
        def find_spec(self, name, path=None, target=None):
            if name == "fc2_metadata_core" or name.startswith("fc2_metadata_core."):
                raise ModuleNotFoundError(f"blocked {name}", name=name)
            return None

    blocker = Block()
    sys.meta_path.insert(0, blocker)
    observations: dict[str, object] = {}
    try:
        # (a) Core 缺失
        data_dir = ctx.work_dir / "h05_absent"
        install_tree(ctx, data_dir)
        manager = discover(data_dir)
        expected = MISSING_MESSAGE.format(name="fc2_metadata_core")
        check(manager.plugin_ids() == frozenset(), "partial registration with Core absent")
        check([f.error for f in manager.failures] == [expected], [f.error for f in manager.failures])
        check([f.name for f in manager.failures] == [PLUGIN_ID], "failure is recorded under the directory name")
        try:
            install_plugin_path(ctx.work_dir / "h05_absent_install", ctx.adapter_tree)
        except ValueError as exc:
            check(str(exc) == "插件导入失败: " + expected, str(exc))
        else:
            raise AssertionError("install succeeded without Core")
        observations["core_absent"] = {"discover_error": expected, "registered": [], "install_error": "插件导入失败: " + expected}

        # (b) Core 已安装但缺少公共名字（版本过旧）
        sys.meta_path.remove(blocker)
        _purge_core_modules()
        fake_root = ctx.work_dir / "h05_old_core"
        (fake_root / "fc2_metadata_core" / "aggregation").mkdir(parents=True)
        (fake_root / "fc2_metadata_core" / "__init__.py").write_text("")
        (fake_root / "fc2_metadata_core" / "aggregation" / "__init__.py").write_text("")
        (fake_root / "fc2_metadata_core" / "normalize").mkdir()
        (fake_root / "fc2_metadata_core" / "normalize" / "__init__.py").write_text("")
        sys.path.insert(0, str(fake_root))
        old_dir = ctx.work_dir / "h05_old"
        install_tree(ctx, old_dir)
        manager = discover(old_dir)
        check(manager.plugin_ids() == frozenset() and len(manager.failures) == 1, "partial registration with an old Core")
        error = manager.failures[0].error
        check(error.startswith("FC2 Metadata Core 未安装或版本不兼容：") and "fc2_metadata_core" in error, error)
        observations["core_too_old"] = {"discover_error": error}
        sys.path.remove(str(fake_root))
        _purge_core_modules()

        # (c) 非 Core 的 ImportError 不被误报为 Core 缺失
        sys.path.insert(0, str(ctx.core_src))
        tampered = ctx.work_dir / "h05_tampered_tree"
        shutil.copytree(ctx.adapter_tree, tampered, ignore=shutil.ignore_patterns("__pycache__"))
        number_py = tampered / "_number.py"
        number_py.write_text(number_py.read_text(encoding="utf-8").replace(
            "from fc2_metadata_core.normalize import", "import definitely_missing_support_module_xyz\nfrom fc2_metadata_core.normalize import", 1), encoding="utf-8")
        other_dir = ctx.work_dir / "h05_other"
        install_tree(ctx, other_dir, tampered)
        manager = discover(other_dir)
        check(manager.plugin_ids() == frozenset(), "partial registration")
        check([f.error for f in manager.failures] == ["No module named 'definitely_missing_support_module_xyz'"], [f.error for f in manager.failures])
        observations["non_core_import_error"] = {"discover_error": manager.failures[0].error}
        # 回到正常：Core 可 import 时同一树被注册
        good = ctx.work_dir / "h05_good"
        install_tree(ctx, good)
        check(PLUGIN_ID in discover(good).plugin_ids(), "registered when Core is importable")
        observations["core_present"] = {"registered": [PLUGIN_ID]}
    finally:
        if blocker in sys.meta_path:
            sys.meta_path.remove(blocker)
    return observations


# ===================================================================================================== H-06


def h06(ctx: Context) -> dict:
    async def scenario():
        host = make_host(ctx, "h06", session=session_4979299())
        try:
            adapter = await host.provider()
            check(adapter is not None, "factory returned no provider")
            again = await host.provider()
            check(adapter is again, "the provider must be cached and reused")
            check((await host.factory.get_crawlers([PLUGIN_ID]))[PLUGIN_ID] is adapter, "get_crawlers returns the cached provider")
            runtime = runtime_of(adapter)
            identity = (id(runtime), id(runtime._engine), id(runtime.governor), id(runtime._bridge))
            for _ in range(3):
                outcome, _rec = await invoke(adapter, "FC2-PPV-4979299")
                check(outcome is not None, "fetch should succeed")
            runtime_after = runtime_of(adapter)
            check((id(runtime_after), id(runtime_after._engine), id(runtime_after.governor), id(runtime_after._bridge)) == identity,
                  "the Core engine / governor / bridge must be constructed once")
        finally:
            host.restore()
        built = 0
        for index, config in enumerate(({}, {"sources": [{"id": "javdb"}]}, {"source_deadline_seconds": 600},
                                        {"sources": [{"id": "av123", "base_url": "http://mirror.example:8080/p"}]})):
            other = make_host(ctx, f"h06_cfg{index}", config=config)
            try:
                check(await other.provider() is not None, f"build() failed for a legal configuration {config}")
                built += 1
            finally:
                other.restore()
        bad = make_host(ctx, "h06_bad", config={"sources": [{"id": "nope"}]})
        try:
            check(await bad.factory.get_crawlers([PLUGIN_ID]) == {}, "an invalid configuration must make the source unavailable, not crash the factory")
        finally:
            bad.restore()
        return {"cached_and_reused": True, "engine_constructed_once": True, "legal_configurations_built": built,
                "invalid_configuration_isolated": True}

    return run(scenario())


# ===================================================================================================== H-07 / H-08


GOLDEN_4979299 = {
    "number": "FC2-4979299",
    "title": TITLE_4979299,
    "studio": None,
    "publisher": "KING POWER D",
    "release": "2026-09-19",
    "runtime": 78,
    "actors": [{"name": "春野くるみ", "gender": "unknown"}],
    "plot": None,
    "poster_urls": [],
    "thumb_urls": ["https://fc2db.net/wp-content/uploads/2026/09/1789748439.08.jpg?v=1789754444", "https://c0.jdbstatic.com/covers/qn/QNkPbM.jpg"],
    "trailer_urls": [],
    "score": None,
    "external_id": "4979299",
    "source_url": "https://fc2db.net/work/4979299/",
    "directors": [],
    "series": None,
    "extrafanart": [],
}


def _dump(metadata) -> dict:
    data = metadata.model_dump(mode="json")
    return data


def h07(ctx: Context) -> dict:
    from amane.plugin import MediaMetadata

    async def scenario():
        host = make_host(ctx, "h07", session=session_4979299())
        try:
            adapter = await host.provider()
            result, recorder = await invoke(adapter, "FC2-PPV-4979299")
            check(type(result) is MediaMetadata, type(result))
            data = _dump(result)
            tags = data.pop("tags")
            check(len(tags) == 23 and "オリジナル" in tags and "Amateur" in tags, tags)
            check(data == GOLDEN_4979299, f"golden mismatch: {data}")
            check("fanart_urls" not in MediaMetadata.model_fields and "fanart_urls" not in data, "fanart_urls must be absent")
            check(all(actor["gender"] == "unknown" for actor in data["actors"]), "actor gender must be unknown, never female")
            check(recorder.outcomes == [(PLUGIN_ID, "ok", None, None, None)], recorder.outcomes)
            return {"metadata": {**data, "tags_count": len(tags)}, "outcome": recorder.outcomes}
        finally:
            host.restore()

    return run(scenario())


def _plain_page(url: str, status: int, text: str = "<html><body>nothing</body></html>", **extra):
    return make_response(status, text, url, **extra)


def _failing_case(ctx: Context, name: str, item_factory, *, max_retries: int = 3, config: dict | None = None):
    """三个来源都得到同一种失败；返回 (结果, 记录器, host attempts)。"""

    async def scenario():
        session = ScriptedSession()
        for source_id in SOURCES:
            session.route(url_for(source_id, "4825061"), item_factory(url_for(source_id, "4825061")))
        host = make_host(ctx, name, max_retries=max_retries, session=session, config=config)
        try:
            adapter = await host.provider()
            result, recorder = await invoke(adapter, "FC2-PPV-4825061")
            return result, recorder, len(session.calls)
        finally:
            host.restore()

    return run(scenario())


def _detail(kind: str) -> str:
    return f"FC2 lookup failed: fc2db_net={kind}; javdb={kind}; av123={kind}"


def h08(ctx: Context) -> dict:
    from curl_cffi import CurlError

    observations: dict[str, object] = {}

    async def success_and_partial():
        host = make_host(ctx, "h08_success", session=session_4825061())
        try:
            adapter = await host.provider()
            result, recorder = await invoke(adapter, "FC2-PPV-4825061")
            check(result is not None and result.number == "FC2-4825061", "SUCCESS -> MediaMetadata")
            check(recorder.outcomes == [(PLUGIN_ID, "ok", None, None, None)], recorder.outcomes)
        finally:
            host.restore()
        # PARTIAL：fc2db_net 传输失败，其余来源命中 -> 可用结果 + 恰好一条 WARNING 日志
        session = session_4825061()
        session.route(url_for("fc2db_net", "4825061"), CurlError("boom"))
        host = make_host(ctx, "h08_partial", session=session)
        records: list[logging.LogRecord] = []

        class Capture(logging.Handler):
            def emit(self, record):
                records.append(record)

        logger = logging.getLogger("ffcc.fc2_metadata")
        handler = Capture(level=logging.DEBUG)
        logger.addHandler(handler)
        old_level = logger.level
        logger.setLevel(logging.DEBUG)
        try:
            adapter = await host.provider()
            result, recorder = await invoke(adapter, "FC2-PPV-4825061")
        finally:
            logger.removeHandler(handler)
            logger.setLevel(old_level)
            host.restore()
        check(result is not None and result.number == "FC2-4825061", "PARTIAL -> usable MediaMetadata")
        check(recorder.outcomes == [(PLUGIN_ID, "ok", None, None, None)], recorder.outcomes)
        check([(r.levelno, r.getMessage()) for r in records] == [(logging.WARNING, "partial FC2 result for FC2-4825061: fc2db_net=connection_error")],
              [(r.levelno, r.getMessage()) for r in records])
        observations["success"] = "ok"
        observations["partial"] = {"outcome": recorder.outcomes, "warning": records[0].getMessage()}

        host = make_host(ctx, "h08_notfound", session=session_not_found_4824605())
        try:
            adapter = await host.provider()
            result, recorder = await invoke(adapter, "FC2-PPV-4824605")
            check(result is None, "all NOT_FOUND -> None")
            check(recorder.outcomes == [(PLUGIN_ID, "failed", "no_usable_metadata", None, None)], recorder.outcomes)
            observations["all_not_found"] = recorder.outcomes
        finally:
            host.restore()
        mixed = session_not_found_4824605()
        mixed.route(url_for("javdb", "4824605"), TimeoutError())
        host = make_host(ctx, "h08_mixed", session=mixed)
        try:
            adapter = await host.provider()
            result, recorder = await invoke(adapter, "FC2-PPV-4824605")
            check(result is None, "SourceError is recorded, not returned")
            check(recorder.outcomes == [(PLUGIN_ID, "failed", "timeout", None, "FC2 lookup failed: fc2db_net=not_found; javdb=timeout; av123=not_found")],
                  recorder.outcomes)
            observations["mixed_not_found_and_timeout"] = recorder.outcomes
        finally:
            host.restore()
        # 非 FC2 / 缺号：None 且 0 次请求；外来 query：SourceError(unexpected)
        session = session_4825061()
        host = make_host(ctx, "h08_nonfc2", session=session)
        try:
            adapter = await host.provider()
            for number, content_type in (("ABC-123", "fc2"), ("FC2-PPV-4825061", "censored"), ("", "fc2"), ("FC2-123456789", "fc2")):
                result, recorder = await invoke(adapter, number, content_type)
                check(result is None, number)
                check(recorder.outcomes == [(PLUGIN_ID, "failed", "no_usable_metadata", None, None)], recorder.outcomes)
            check(session.calls == [], "non-FC2 / invalid numbers must send no request")

            class Foreign:
                pass

            from amane.observability.recorder import _recorder_ctx
            from amane.observability.source import invoke_source

            recorder = FakeRecorder()
            token = _recorder_ctx.set(recorder)
            try:
                await invoke_source(PLUGIN_ID, lambda: adapter.fetch(Foreign()))
            finally:
                _recorder_ctx.reset(token)
            check(recorder.outcomes == [(PLUGIN_ID, "failed", "unexpected", None, "invalid search query")], recorder.outcomes)
            check(session.calls == [], "foreign query: no request")
            observations["non_fc2_and_foreign"] = {"requests": 0}
        finally:
            host.restore()

    run(success_and_partial())

    async def engine_exception_boundary():
        """P5-C1-L1-02：provider 边界（不经会消费异常的 invoke_source）必须 ``raise SourceError(UNEXPECTED) from <原始异常对象>``。"""
        from amane.plugin import FailureReason, SourceError

        secret = "SECRET MUST NOT LEAK"
        original = RuntimeError(secret)

        class Boom:
            def __init__(self, error):
                self.error = error

            async def aggregate(self, number):
                raise self.error

        records: list[logging.LogRecord] = []

        class Capture(logging.Handler):
            def emit(self, record):
                records.append(record)

        root = logging.getLogger()
        handler = Capture(level=logging.DEBUG)
        old_level = root.level
        root.addHandler(handler)
        root.setLevel(logging.DEBUG)
        host = make_host(ctx, "h08_cause", session=session_4825061())
        try:
            adapter = await host.provider()
            runtime = runtime_of(adapter)
            runtime._engine = Boom(original)
            try:
                await adapter.fetch(query("FC2-PPV-4825061"))
            except SourceError as caught:
                check(type(caught) is SourceError, type(caught))
                check(caught.reason is FailureReason.UNEXPECTED, caught.reason)
                check(caught.detail == "internal adapter error: RuntimeError", caught.detail)
                check(caught.url is None and caught.http_status is None, (caught.url, caught.http_status))
                check(caught.__cause__ is original, "the SourceError must be raised from the ORIGINAL exception object")
                check(secret not in str(caught) and secret not in repr(caught) and secret not in (caught.detail or ""), "no secret in the SourceError")
            else:
                raise AssertionError("the provider boundary must raise SourceError for an engine exception")
            result, recorder = await invoke(adapter, "FC2-PPV-4825061")
            check(result is None, "SourceError is recorded, not returned")
            check(recorder.outcomes == [(PLUGIN_ID, "failed", "unexpected", None, "internal adapter error: RuntimeError")], recorder.outcomes)
            check(all(secret not in message for _site, message in recorder.logs), recorder.logs)
            # 取消 / 致命异常：原样传播，不被转换成 SourceError
            for fatal in (asyncio.CancelledError(), KeyboardInterrupt(), SystemExit(3)):
                runtime._engine = Boom(fatal)
                try:
                    await adapter.fetch(query("FC2-PPV-4825061"))
                except BaseException as propagated:  # noqa: BLE001 - 见证传播的就是同一个对象
                    check(propagated is fatal and not isinstance(propagated, SourceError), (type(fatal).__name__, propagated))
                else:
                    raise AssertionError(f"{type(fatal).__name__} must propagate")
        finally:
            root.removeHandler(handler)
            root.setLevel(old_level)
            host.restore()
        check(all(secret not in record.getMessage() for record in records), "no log record may contain the secret")
        # fetch 成功路径不受影响：恢复引擎后仍能得到结果
        observations["engine_exception_boundary"] = {
            "source_error": "SourceError(UNEXPECTED, 'internal adapter error: RuntimeError')",
            "cause_is_original_exception_object": True, "url": None, "http_status": None, "secret_in_detail_or_logs": False,
            "invoke_source_records": "unexpected / internal adapter error: RuntimeError",
            "cancelled_keyboard_interrupt_system_exit": "propagated unchanged (same object, not converted)",
        }

    run(engine_exception_boundary())

    kinds: dict[str, object] = {}
    cases = (
        ("blocked_403", lambda url: _plain_page(url, 403), "http_error", "blocked", 3),
        ("rate_limited_429", lambda url: _plain_page(url, 429), "rate_limited", "rate_limited", 3),
        ("server_error_500", lambda url: _plain_page(url, 500), "server_error", "http_server_error", 3),
        ("server_error_503", lambda url: _plain_page(url, 503), "server_error", "http_server_error", 3),
        ("invalid_response_418", lambda url: _plain_page(url, 418), "parse_error", "invalid_response", 3),
        ("timeout", lambda url: TimeoutError(), "timeout", "timeout", 9),
        ("connection_error", lambda url: CurlError("boom"), "network", "connection_error", 9),
        ("generic_transport_600", lambda url: _plain_page(url, 600), "network", "network_error", 3),
        ("decode_error", lambda url: make_response(200, "x", url, headers=[("Content-Type", "text/html; charset=rot13")]), "network", "decode_error", 3),
        ("response_too_large", lambda url: make_response(200, url=url, content=b"a" * (5 * 1024 * 1024 + 1)), "parse_error", "response_too_large", 3),
    )
    for name, factory, reason, kind, attempts in cases:
        result, recorder, calls = _failing_case(ctx, f"h08_{name}", factory)
        check(result is None, name)
        check(recorder.outcomes == [(PLUGIN_ID, "failed", reason, None, _detail(kind))], (name, recorder.outcomes))
        check(calls == attempts, (name, calls))
        kinds[name] = {"reason": reason, "kind": kind, "host_attempts": calls}
    # SOURCE_DEADLINE：挂起 + 很小的来源 deadline
    result, recorder, calls = _failing_case(ctx, "h08_deadline", lambda url: HANG, config={"source_deadline_seconds": 0.2})
    check(recorder.outcomes == [(PLUGIN_ID, "failed", "timeout", None, _detail("source_deadline"))], recorder.outcomes)
    kinds["source_deadline"] = {"reason": "timeout", "kind": "source_deadline"}

    # CIRCUIT_OPEN：同一 provider 连续 3 次最终失败后第 4 次不发请求
    async def breaker():
        session = uniform_session(CurlError("boom"))
        host = make_host(ctx, "h08_breaker", max_retries=1, session=session)
        try:
            adapter = await host.provider()
            for _ in range(3):
                await invoke(adapter, "FC2-PPV-4825061")
            before = len(session.calls)
            result, recorder = await invoke(adapter, "FC2-PPV-4825061")
            check(len(session.calls) == before == 9, (before, len(session.calls)))
            check(recorder.outcomes == [(PLUGIN_ID, "failed", "network", None, _detail("circuit_open"))], recorder.outcomes)
        finally:
            host.restore()

    run(breaker())
    kinds["circuit_open"] = {"reason": "network", "kind": "circuit_open", "requests_after_open": 0}
    observations["failure_kinds"] = kinds
    return observations


# ===================================================================================================== H-09


def _bound_case(ctx: Context, name: str, item, h: int, sources: int = 3):
    async def scenario():
        session = ScriptedSession()
        entries = [{"id": source_id} for source_id in SOURCES[:sources]]
        for source_id in SOURCES[:sources]:
            session.route(url_for(source_id, "4825061"), item if not callable(item) else item(url_for(source_id, "4825061")))
        host = make_host(ctx, name, max_retries=h, session=session, config={"sources": entries})
        try:
            adapter = await host.provider()
            await invoke(adapter, "FC2-PPV-4825061")
            per_source = {source_id: session.calls.count(url_for(source_id, "4825061")) for source_id in SOURCES[:sources]}
            return per_source, len(session.calls), list(host.waits)
        finally:
            host.restore()

    return run(scenario())


def h09(ctx: Context) -> dict:
    from curl_cffi import CurlError

    observations: dict[str, object] = {"status_paths": {}, "transport_paths": {}}
    # --- L2：状态码路径恒为 1 个 host attempt（与 H 无关）
    for status in (200, 403, 404, 429, 503, 500, 599):
        for h in (1, 3, 10):
            per_source, total, waits = _bound_case(ctx, f"h09_status_{status}_{h}", lambda url, s=status: make_response(s, "<html></html>", url), h)
            check(total == 3 and all(count == 1 for count in per_source.values()), (status, h, per_source))
            check(waits == [], (status, h, "no host backoff on the status path"))
        observations["status_paths"][str(status)] = "1 host attempt per source for H in {1,3,10}"
    # --- L2：CurlError / 超时路径恰为 H 个 attempt / 来源（达到上界 S × H）
    for label, item in (("curl_error", CurlError("boom")), ("timeout", TimeoutError())):
        for h in (1, 3, 10):
            per_source, total, waits = _bound_case(ctx, f"h09_{label}_{h}", item, h)
            check(all(count == h for count in per_source.values()) and total == 3 * h, (label, h, per_source))
            check(len(waits) == 3 * (h - 1), (label, h, len(waits)))
            check(all(1.0 <= wait <= 3 * (h - 2) + 3 + 1e-9 for wait in waits), (label, h, "backoff formula attempt*3+2±1"))
            observations["transport_paths"][f"{label}_H{h}"] = {"host_attempts": total, "bound_S_x_H": 3 * h}
    # --- 混合：先 CurlError 再 503（503 在 ok_statuses 内）
    def mixed(url):
        return [CurlError("boom"), make_response(503, "", url)]

    async def mixed_case():
        session = ScriptedSession()
        for source_id in SOURCES:
            url = url_for(source_id, "4825061")
            session.route(url, *mixed(url))
        host = make_host(ctx, "h09_mixed", max_retries=3, session=session)
        try:
            adapter = await host.provider()
            await invoke(adapter, "FC2-PPV-4825061")
            return len(session.calls)
        finally:
            host.restore()

    total = run(mixed_case())
    check(total == 6, total)
    observations["mixed_curl_then_503"] = {"host_attempts": total, "bound": 9}
    # --- 熔断打开：0 次
    async def breaker_case(h: int):
        session = uniform_session(CurlError("boom"))
        host = make_host(ctx, f"h09_breaker_{h}", max_retries=h, session=session)
        try:
            adapter = await host.provider()
            for _ in range(3):
                await invoke(adapter, "FC2-PPV-4825061")
            before = len(session.calls)
            await invoke(adapter, "FC2-PPV-4825061")
            return before, len(session.calls)
        finally:
            host.restore()

    for h in (1, 3):
        before, after = run(breaker_case(h))
        check(before == after == 9 * h, (h, before, after))
    observations["breaker_open"] = "0 host attempts once open"
    # --- 状态码 600：不在 ok_statuses 内 -> RequestError(http_error)，1 个 attempt，由通用 HttpTransportError 兜底
    result, recorder, calls = _failing_case(ctx, "h09_600", lambda url: make_response(600, "", url))
    check(calls == 3 and recorder.outcomes == [(PLUGIN_ID, "failed", "network", None, _detail("network_error"))], (calls, recorder.outcomes))
    observations["status_600"] = {"host_attempts": calls, "reason": "network", "kind": "network_error (generic transport fallback)"}

    # --- L3：回环无限 302 + 真实 curl_cffi：每个 attempt 命中 21 次；TooManyRedirects 被按 H 重试
    def loop_case(name: str, h: int, sources: int):
        async def scenario():
            with RedirectLoopServer() as server:
                entries = [{"id": source_id, "base_url": server.base_url} for source_id in SOURCES[:sources]]
                host = make_host(ctx, name, max_retries=h, real_session=True, config={"sources": entries})
                try:
                    adapter = await host.provider()
                    result, recorder = await invoke(adapter, "FC2-PPV-4825061")
                    check(result is None, "redirect loop must fail")
                    return server.total, recorder.outcomes, list(host.waits)
                finally:
                    host.restore()
                    await host.web_client._session.close()

        return run(scenario())

    hops_table = {}
    for sources, h in ((3, 3), (1, 10), (3, 1)):
        hops, outcomes, waits = loop_case(f"h09_loop_{sources}_{h}", h, sources)
        check(hops == sources * h * REDIRECT_HOPS, (sources, h, hops))
        check(hops <= sources * h * 21, "L3 bound")
        entries = "; ".join(f"{sid}=connection_error" for sid in SOURCES[:sources])
        check(outcomes == [(PLUGIN_ID, "failed", "network", None, f"FC2 lookup failed: {entries}")], outcomes)
        hops_table[f"S{sources}_H{h}"] = {"network_hops": hops, "bound_S_x_H_x_21": sources * h * 21, "hops_per_attempt": REDIRECT_HOPS}
    observations["redirect_loop"] = hops_table
    observations["bounds"] = {"default_S3_H3": {"L1": 3, "L2": 9, "L3": 189}, "maximum_S3_H10": {"L1": 3, "L2": 30, "L3": 630}}
    return observations


# ===================================================================================================== H-10


def h10(ctx: Context) -> dict:
    import inspect
    import time

    from amane.plugin import RequestError, SourceError
    from curl_cffi import CurlError

    async def wiring():
        host = make_host(ctx, "h10_wiring")
        try:
            bridge = runtime_of(await host.provider())._bridge
        finally:
            host.restore()
        base = [klass for klass in type(bridge).__mro__ if klass.__name__ == "AmaneHttpBridge"]
        check(len(base) == 1, "the production bridge must derive from AmaneHttpBridge")
        parameters = list(inspect.signature(base[0].__init__).parameters.values())
        check([(p.name, p.kind.name) for p in parameters] == [("self", "POSITIONAL_OR_KEYWORD"), ("web_client", "POSITIONAL_OR_KEYWORD"),
                                                           ("clock", "KEYWORD_ONLY")], "the frozen constructor signature (web_client, *, clock)")
        check(parameters[2].default is time.monotonic, "clock defaults to time.monotonic")
        check(type(bridge).__init__ is base[0].__init__, "the production subclass must not override the constructor")
        check(type(bridge).host_request_error_types == (RequestError,) and type(bridge).host_source_error_types == (SourceError,),
              "the production bridge maps exactly the host RequestError / SourceError")
        check(base[0].host_request_error_types == () and base[0].host_source_error_types == (), "the base bridge catches nothing by default")
        return {"constructor": "(self, web_client, *, clock=time.monotonic)", "subclass_overrides_constructor": False,
                "host_request_error_types": ["RequestError"], "host_source_error_types": ["SourceError"]}

    table = {"bridge_wiring": run(wiring())}
    for name, factory, reason, kind in (
        ("timeout", lambda url: TimeoutError(), "timeout", "timeout"),
        ("network", lambda url: CurlError("boom"), "network", "connection_error"),
        ("unexpected", lambda url: ValueError("host message that must never be parsed"), "network", "network_error"),
        ("http_error_600", lambda url: make_response(600, "", url), "network", "network_error"),
    ):
        result, recorder, calls = _failing_case(ctx, f"h10_{name}", factory)
        check(recorder.outcomes == [(PLUGIN_ID, "failed", reason, None, _detail(kind))], (name, recorder.outcomes))
        table[name] = {"reason": reason, "kind": kind, "host_attempts": calls}
    check(table["unexpected"]["host_attempts"] == 3, "unexpected errors are not retried by the host (1 attempt / source)")

    async def redirect():
        with RedirectLoopServer() as server:
            entries = [{"id": "javdb", "base_url": server.base_url}]
            host = make_host(ctx, "h10_redirect", max_retries=2, real_session=True, config={"sources": entries})
            try:
                adapter = await host.provider()
                result, recorder = await invoke(adapter, "FC2-PPV-4825061")
                check(recorder.outcomes == [(PLUGIN_ID, "failed", "network", None, "FC2 lookup failed: javdb=connection_error")], recorder.outcomes)
            finally:
                host.restore()
                await host.web_client._session.close()

    run(redirect())
    table["redirect_limit"] = {"reason": "network", "kind": "connection_error (not redirect_error)"}
    return table


# ===================================================================================================== H-11


def h11(ctx: Context) -> dict:
    from amane.observability.recorder import _recorder_ctx

    async def scenario():
        session = uniform_session(HANG)
        host = make_host(ctx, "h11", session=session)
        try:
            adapter = await host.provider()
            recorder = FakeRecorder()
            token = _recorder_ctx.set(recorder)
            try:
                import amane.aggregate  # noqa: F401
                from amane.observability.source import invoke_source

                task = asyncio.create_task(invoke_source(PLUGIN_ID, lambda: adapter.fetch(query("FC2-PPV-4825061"))))
            finally:
                _recorder_ctx.reset(token)
            for _ in range(300):
                await asyncio.sleep(0.01)
                if session.in_flight == 3:
                    break
            check(session.in_flight == 3, f"host requests in flight: {session.in_flight}")
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            else:
                raise AssertionError("cancellation was swallowed")
            check(task.cancelled(), "the task must end cancelled")
            check(recorder.outcomes == [], f"cancellation must not be recorded as a source outcome: {recorder.outcomes}")
            await asyncio.sleep(0)
            check(session.in_flight == 0, "host requests must be cancelled")
            snapshot = runtime_of(adapter).governor.snapshot()
            check(all(h.in_flight == 0 and h.waiting == 0 for h in snapshot.hosts), "governor host permits leaked")
            check(all(b.in_flight == 0 and b.half_open_probes_in_flight == 0 for b in snapshot.breakers), "governor breaker leaked")
            check(len([t for t in asyncio.all_tasks() if t is not asyncio.current_task()]) == 0, "leftover tasks")
            # 调用方 asyncio.timeout：得到 TimeoutError，而不是来源失败
            try:
                async with asyncio.timeout(0.2):
                    await invoke(adapter, "FC2-PPV-4825061")
            except TimeoutError:
                pass
            else:
                raise AssertionError("caller timeout did not propagate")
            await asyncio.sleep(0)
            check(session.in_flight == 0, "host requests after timeout")
            return {"cancelled_error_propagates": True, "recorded_outcomes": 0, "governor_idle": True, "leftover_tasks": 0,
                    "caller_timeout": "TimeoutError"}
        finally:
            host.restore()

    return run(scenario())


# ===================================================================================================== H-12


def h12(ctx: Context) -> dict:
    import amane.aggregate  # noqa: F401
    from amane.aggregate.engine import aggregate
    from amane.plugin import ContentType, SearchQuery

    async def scenario():
        host = make_host(ctx, "h12", session=session_4979299())
        try:
            adapter = await host.provider()
            result = await aggregate(
                SearchQuery(number="FC2-4979299", content_type=ContentType.FC2),
                {PLUGIN_ID: adapter},
                defaultdict(lambda: [PLUGIN_ID]),
            )
            metadata = result.metadata
            check(metadata.title == TITLE_4979299, "aggregated title")
            check(dict(metadata.source_urls) == {PLUGIN_ID: "https://fc2db.net/work/4979299/"}, dict(metadata.source_urls))
            check(dict(metadata.external_ids) == {PLUGIN_ID: "4979299"}, dict(metadata.external_ids))
            check(set(metadata.extrafanart_urls) <= {PLUGIN_ID}, dict(metadata.extrafanart_urls))
            check({str(value) for value in dict(result.field_sources).values()} == {PLUGIN_ID}, dict(result.field_sources))
            check(list(result.failed_sites) == [], list(result.failed_sites))
            return {
                "source_urls_keys": sorted(metadata.source_urls),
                "external_ids_keys": sorted(metadata.external_ids),
                "field_source_ids": sorted({str(value) for value in dict(result.field_sources).values()}),
                "failed_sites": [],
            }
        finally:
            host.restore()

    return run(scenario())


# ===================================================================================================== H-13


def determinism_payload(ctx: Context, tag: str = "x") -> str:
    from curl_cffi import CurlError

    payload: dict[str, object] = {}

    async def scenario():
        host = make_host(ctx, f"h13_{tag}_a", session=session_4979299())
        try:
            adapter = await host.provider()
            result, recorder = await invoke(adapter, "FC2-PPV-4979299")
            payload["success"] = [result.model_dump(mode="json"), recorder.outcomes]
        finally:
            host.restore()
        for key, builder, number in (
            ("not_found", session_not_found_4824605, "FC2-PPV-4824605"),
        ):
            host = make_host(ctx, f"h13_{tag}_{key}", session=builder())
            try:
                adapter = await host.provider()
                result, recorder = await invoke(adapter, number)
                payload[key] = [None if result is None else result.model_dump(mode="json"), recorder.outcomes]
            finally:
                host.restore()
        mixed = session_4825061()
        mixed.route(url_for("fc2db_net", "4825061"), CurlError("boom"))
        mixed.route(url_for("av123", "4825061"), TimeoutError())
        host = make_host(ctx, f"h13_{tag}_partial", session=mixed)
        try:
            adapter = await host.provider()
            result, recorder = await invoke(adapter, "FC2-PPV-4825061")
            payload["partial"] = [result.model_dump(mode="json"), recorder.outcomes]
        finally:
            host.restore()
        host = make_host(ctx, f"h13_{tag}_failure", session=uniform_session(CurlError("boom")))
        try:
            adapter = await host.provider()
            result, recorder = await invoke(adapter, "FC2-PPV-4825061")
            payload["failure"] = [result, recorder.outcomes]
        finally:
            host.restore()

    run(scenario())
    return stable_json(payload)


def h13(ctx: Context) -> dict:
    first = determinism_payload(ctx, "r0")
    for index in (1, 2):
        check(determinism_payload(ctx, f"r{index}") == first, "in-process repeat differs")
    outputs = {}
    for seed in ("0", "1", "2"):
        env = {**os.environ, "PYTHONHASHSEED": seed}
        completed = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), "--emit-determinism", "--repo-root", str(ctx.repo_root), "--amane-src", str(ctx.amane_src),
             "--core-src", str(ctx.core_src), "--adapter-tree", str(ctx.adapter_tree), "--work-dir", str(ctx.work_dir / f"h13_seed{seed}")],
            capture_output=True, env=env, timeout=240,
        )
        check(completed.returncode == 0, completed.stderr.decode("utf-8", "replace")[-800:])
        lines = [line for line in completed.stdout.decode("utf-8").splitlines() if line.startswith("@@PAYLOAD@@")]
        check(len(lines) == 1, "exactly one payload line expected")  # 宿主的 structlog 日志也写 stdout（含时间戳）：只比较标记行
        outputs[seed] = lines[0].encode("utf-8")
    check(outputs["0"] == outputs["1"] == outputs["2"], "PYTHONHASHSEED changes the output")
    check(json.loads(outputs["0"].decode("utf-8")[len("@@PAYLOAD@@"):]) == json.loads(first), "subprocess payload differs from the in-process payload")
    return {"in_process_repeats": 3, "hash_seeds": [0, 1, 2], "payload_sha256": __import__("hashlib").sha256(first.encode()).hexdigest()}


# ===================================================================================================== H-14


def _tree_snapshot(root: Path) -> list[str]:
    return sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if "__pycache__" not in p.parts)


def h14(ctx: Context) -> dict:
    from curl_cffi import CurlError

    async def scenario():
        session = session_4979299()
        host = make_host(ctx, "h14", session=session)
        environ_before = dict(os.environ)
        try:
            initial = _tree_snapshot(host.data_dir)
            adapter = await host.provider()
            created = sorted(set(_tree_snapshot(host.data_dir)) - set(initial))
            check(created == ["plugins/ffcc.fc2-metadata"], f"only the host factory's own plugin directory may appear: {created}")
            before = _tree_snapshot(host.data_dir)
            original = (socket.socket.connect, socket.socket.connect_ex, socket.create_connection, socket.getaddrinfo)

            def blocked(*_a, **_k):
                raise AssertionError("socket activity")

            socket.socket.connect = socket.socket.connect_ex = blocked  # type: ignore[method-assign, assignment]
            socket.create_connection = socket.getaddrinfo = blocked  # type: ignore[assignment]
            try:
                await invoke(adapter, "FC2-PPV-4979299")
                session.route(url_for("javdb", "4979299"), CurlError("boom"))
                await invoke(adapter, "FC2-PPV-4979299")
                await invoke(adapter, "ABC-123")
            finally:
                socket.socket.connect, socket.socket.connect_ex, socket.create_connection, socket.getaddrinfo = original  # type: ignore[method-assign, assignment]
            check(len(session.calls) >= 3, "the fetches really ran")
            check(_tree_snapshot(host.data_dir) == before, "data_dir changed during fetches")
            check(dict(os.environ) == environ_before, "environment changed")
            return {"data_dir_changes_during_fetch": [], "host_created": created, "socket_activity": 0}
        finally:
            host.restore()

    return run(scenario())


# ===================================================================================================== H-15


def h15(ctx: Context) -> dict:
    async def scenario():
        session = session_4979299()
        host = make_host(ctx, "h15", max_retries=0, session=session)
        try:
            adapter = await host.provider()
            result, recorder = await invoke(adapter, "FC2-PPV-4979299")
            check(result is None, "fail closed")
            check(session.calls == [], f"v0.15.0 sends no request when max_retries = 0: {session.calls}")
            check(recorder.outcomes == [(PLUGIN_ID, "failed", "network", None, _detail("connection_error"))], recorder.outcomes)
            return {"host_attempts": 0, "outcome": recorder.outcomes}
        finally:
            host.restore()

    return run(scenario())


SCENARIOS = {
    "H-01": h01, "H-02": h02, "H-03": h03, "H-04": h04, "H-05": h05, "H-06": h06, "H-07": h07, "H-08": h08,
    "H-09": h09, "H-10": h10, "H-11": h11, "H-12": h12, "H-13": h13, "H-14": h14, "H-15": h15,
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario")
    parser.add_argument("--emit-determinism", action="store_true")
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--amane-src", required=True, type=Path)
    parser.add_argument("--core-src", required=True, type=Path)
    parser.add_argument("--adapter-tree", required=True, type=Path)
    parser.add_argument("--work-dir", required=True, type=Path)
    options = parser.parse_args()
    options.work_dir.mkdir(parents=True, exist_ok=True)
    ctx = Context(options.repo_root.resolve(), options.amane_src.resolve(), options.core_src.resolve(),
                  options.adapter_tree.resolve(), options.work_dir.resolve())
    if options.emit_determinism:
        prepare_paths(ctx)
        payload = determinism_payload(ctx, "emit")
        sys.stdout.write("\n@@PAYLOAD@@" + json.dumps(json.loads(payload), sort_keys=True, ensure_ascii=True) + "\n")
        return 0
    prepare_paths(ctx, with_core=options.scenario != "H-05")
    import amane.aggregate  # noqa: F401 - 必须先于 amane.observability.*（Amane 内部循环导入）

    function = SCENARIOS[options.scenario]
    try:
        observations = function(ctx)
        result = {"id": options.scenario, "passed": True, "observations": observations}
    except Exception as exc:  # noqa: BLE001 - 见证运行器：任何失败都记录为 passed = false
        import traceback

        result = {"id": options.scenario, "passed": False, "observations": {}, "failure": f"{type(exc).__name__}: {exc}",
                  "traceback": traceback.format_exc()[-1500:]}
    sys.stdout.write("\n@@WITNESS@@" + json.dumps(result, sort_keys=True, ensure_ascii=True) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
