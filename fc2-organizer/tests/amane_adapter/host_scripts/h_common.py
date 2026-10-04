"""P5-C1 真实宿主见证的共用工具（**只在真实 Amane v0.15.0 子进程内被执行；pytest 从不导入**）。

* 传输层是**脚本化的 ``WebClient._session``**（真实 ``curl_cffi.requests.Response`` 对象；无真实网络）；
  唯一的网络活动是 H-09 的回环 HTTP 服务器（127.0.0.1，仅用于证明每个 attempt 的 21 个 network hops）。
* ``WebClient`` 的退避 ``asyncio.sleep`` 通过**模块局部代理**替换（只影响 ``amane.net.http``，不改全局 asyncio），
  并记录等待值以核对退避公式 ``attempt * 3 + 2 ± 1``。
"""

from __future__ import annotations

import asyncio
import hashlib
import importlib.util
import json
import shutil
import sys
import threading
from collections import defaultdict
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PLUGIN_ID = "ffcc.fc2-metadata"
AMANE_COMMIT = "45dff2159369883e028a296d775a4598836c1ddd"
HANG = object()


@dataclass(frozen=True)
class Context:
    repo_root: Path
    amane_src: Path
    core_src: Path
    adapter_tree: Path
    work_dir: Path


def prepare_paths(ctx: Context, *, with_core: bool = True) -> None:
    if with_core:
        sys.path.insert(0, str(ctx.core_src))
    sys.path.insert(0, str(ctx.repo_root / "tests"))


def load_tool(ctx: Context, name: str):
    spec = importlib.util.spec_from_file_location(f"witness_tool_{name}", ctx.repo_root / "tools" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def fixture(relative: str) -> str:
    from support.source_fixtures import load_fixture

    return load_fixture(relative)


# --------------------------------------------------------------------------------------------- 真实 Response / 会话


def make_response(status: int, text: str = "", url: str = "https://h.example/", *, content: bytes | None = None,
                  headers: list[tuple[str, str]] | None = None):
    from curl_cffi.requests import Response
    from curl_cffi.requests.headers import Headers

    response = Response()
    response.status_code = status
    response.content = text.encode("utf-8") if content is None else content
    response.url = url
    response.headers = Headers(headers if headers is not None else [("Content-Type", "text/html; charset=utf-8")])
    return response


class ScriptedSession:
    """替换 ``WebClient._session``：每次 ``request`` 记录 URL 并按 URL 的队列返回 / 抛出 / 挂起。"""

    def __init__(self, default=None) -> None:
        self.routes: dict[str, list[object]] = {}
        self.default = default
        self.calls: list[str] = []
        self.kwargs: list[dict[str, object]] = []
        self.in_flight = 0

    def route(self, url: str, *items: object) -> None:
        self.routes[url] = list(items)

    async def request(self, method, url, **kwargs):
        self.calls.append(url)
        self.kwargs.append(dict(kwargs))
        queue = self.routes.get(url)
        item = (queue.pop(0) if len(queue) > 1 else queue[0]) if queue else self.default
        self.in_flight += 1
        try:
            if item is HANG:
                await asyncio.Event().wait()
            if callable(item) and not isinstance(item, BaseException):
                item = item()
            if isinstance(item, BaseException):
                raise item
            return item
        finally:
            self.in_flight -= 1

    async def close(self) -> None:
        return None


class _AsyncioProxy:
    """``amane.net.http.asyncio`` 的局部代理：只替换 ``sleep``，其余原样转发。"""

    def __init__(self, waits: list[float]) -> None:
        self._waits = waits

    async def sleep(self, seconds: float, *args, **kwargs):
        if seconds > 0.5:  # 宿主退避（>= 1 s）：记录并跳过；<= 0.5 s 的让步（如 sleep(0)）保持真实
            self._waits.append(seconds)
            await asyncio.sleep(0)
            return None
        return await asyncio.sleep(seconds, *args, **kwargs)

    def __getattr__(self, name: str):
        return getattr(asyncio, name)


def patch_backoff(waits: list[float]):
    import amane.net.http as host_http

    original = host_http.asyncio
    host_http.asyncio = _AsyncioProxy(waits)  # type: ignore[assignment]

    def restore() -> None:
        host_http.asyncio = original

    return restore


# --------------------------------------------------------------------------------------------- 安装 / 发现 / provider


def install_tree(ctx: Context, data_dir: Path, tree: Path | None = None) -> Path:
    destination = data_dir / "plugins" / "sources" / PLUGIN_ID
    shutil.copytree(tree or ctx.adapter_tree, destination, ignore=shutil.ignore_patterns("__pycache__"))
    return destination


def discover(data_dir: Path):
    from amane.plugins.manager import PluginManager

    return PluginManager.discover(data_dir)


@dataclass
class Host:
    data_dir: Path
    manager: object
    factory: object
    web_client: object
    session: ScriptedSession
    waits: list[float]
    restore: object

    async def provider(self):
        return await self.factory.get(PLUGIN_ID)  # type: ignore[attr-defined]


def make_host(ctx: Context, name: str, *, max_retries: int = 3, config: dict | None = None, session: ScriptedSession | None = None,
              real_session: bool = False) -> Host:
    from amane.crawlers.factory import CrawlerFactory
    from amane.crawlers.http import HttpClient
    from amane.net.http import RateLimiters, WebClient
    from amane.plugins.models import PluginConfig

    data_dir = ctx.work_dir / name
    install_tree(ctx, data_dir)
    manager = discover(data_dir)
    assert PLUGIN_ID in manager.plugin_ids(), [f.error for f in manager.failures]
    web_client = WebClient(timeout=10, max_retries=max_retries, limiters=RateLimiters())
    scripted = session or ScriptedSession()
    if not real_session:
        web_client._session = scripted
    waits: list[float] = []
    restore = patch_backoff(waits)
    factory = CrawlerFactory(
        HttpClient(web_client),
        plugin_manager=manager,
        plugin_configs={PLUGIN_ID: PluginConfig(config=config or {})},
        data_dir=data_dir,
    )
    return Host(data_dir, manager, factory, web_client, scripted, waits, restore)


def runtime_of(adapter) -> object:
    """工厂缓存的 ``_PluginProviderAdapter`` -> 插件的 ``AdapterRuntime``（仅用于见证对象身份与 governor 状态）。"""
    return adapter._provider._runtime


# --------------------------------------------------------------------------------------------- 站点 URL / 场景


FC2DB = "https://fc2db.net/work/{digits}/"
JAVDB = "https://javdb.com/search?q=FC2-PPV-{digits}"
AV123 = "https://123av.com/en/v/fc2-ppv-{digits}"
TEMPLATES = {"fc2db_net": FC2DB, "javdb": JAVDB, "av123": AV123}
SOURCES = ("fc2db_net", "javdb", "av123")


def url_for(source_id: str, digits: str) -> str:
    return TEMPLATES[source_id].format(digits=digits)


def page(session: ScriptedSession, source_id: str, digits: str, relative: str, status: int = 200) -> None:
    url = url_for(source_id, digits)
    session.route(url, make_response(status, fixture(relative), url))


def session_4979299() -> ScriptedSession:
    session = ScriptedSession()
    page(session, "fc2db_net", "4979299", "fc2db_net/work_4979299.html")
    page(session, "javdb", "4979299", "javdb/search_hit_4979299.html")
    page(session, "av123", "4979299", "av123/detail_4979299.html")
    return session


def session_4825061() -> ScriptedSession:
    session = ScriptedSession()
    page(session, "av123", "4825061", "av123/detail_4825061.html")
    page(session, "fc2db_net", "4825061", "fc2db_net/work_404_4825061.html", status=404)
    page(session, "javdb", "4825061", "javdb/search_hit_4825061.html")
    return session


def session_not_found_4824605() -> ScriptedSession:
    session = ScriptedSession()
    page(session, "fc2db_net", "4824605", "fc2db_net/work_404_4825061.html", status=404)
    page(session, "av123", "4824605", "av123/detail_404_4824605.html", status=404)
    page(session, "javdb", "4824605", "javdb/search_no_exact_4824605.html")
    return session


def uniform_session(item) -> ScriptedSession:
    """每个 URL 都返回同一项（响应 / 异常实例 / HANG）。"""
    return ScriptedSession(default=item)


def query(number: str, content_type="fc2"):
    from amane.plugin import ContentType, SearchQuery

    return SearchQuery(number=number, content_type=ContentType(content_type) if isinstance(content_type, str) else content_type)


# --------------------------------------------------------------------------------------------- 真实 invoke_source + 记录器


class FakeRecorder:
    """满足 ``invoke_source`` 对 Recorder 的使用面（``record_site_outcome`` / ``warning`` / ``exception``）。"""

    def __init__(self) -> None:
        self.outcomes: list[tuple[str, str, str | None, int | None, str | None]] = []
        self.logs: list[tuple[str, str]] = []
        self.http: list[dict[str, object]] = []

    def record_http(self, **kwargs) -> None:
        """真实 Recorder 会被 ``WebClient`` 经 ContextVar 调用：每次 ``request()`` 一条（含 ``attempts``）。"""
        self.http.append(kwargs)

    def record_site_outcome(self, *, site, outcome, reason=None, http_status=None, detail=None, **_kw) -> None:
        self.outcomes.append((site, outcome.value, reason.value if reason is not None else None, http_status, detail))

    def warning(self, message, **kw) -> None:
        self.logs.append(("warning", message))

    def exception(self, message, **kw) -> None:
        self.logs.append(("exception", message))

    def info(self, message, **kw) -> None:
        self.logs.append(("info", message))

    debug = error = info


async def invoke(provider, number: str, content_type="fc2"):
    """真实 ``invoke_source``：返回 ``(结果, 记录器)``。"""
    import amane.aggregate  # noqa: F401 - 必须先于 observability.source（Amane 内部循环导入）
    from amane.observability.recorder import _recorder_ctx
    from amane.observability.source import invoke_source

    recorder = FakeRecorder()
    token = _recorder_ctx.set(recorder)
    try:
        result = await invoke_source(PLUGIN_ID, lambda: provider.fetch(query(number, content_type)))
    finally:
        _recorder_ctx.reset(token)
    return result, recorder


# --------------------------------------------------------------------------------------------- 回环重定向服务器


class RedirectLoopServer:
    """无限 302 的回环服务器：统计每个路径的命中数（仅 H-09 的 L3 见证使用；不对外网络）。"""

    def __init__(self) -> None:
        self.hits: dict[str, int] = defaultdict(int)
        owner = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def do_GET(self):  # noqa: N802
                owner.hits[self.path.split("?")[0].split("#")[0].split("/r")[0] or "/"] += 1
                self.send_response(302)
                self.send_header("Location", f"/r{sum(owner.hits.values())}")
                self.send_header("Content-Length", "0")
                self.end_headers()

            def log_message(self, *args):
                return None

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self._server.server_address[1]}"

    @property
    def total(self) -> int:
        return sum(self.hits.values())

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, *exc):
        self._server.shutdown()
        self._server.server_close()
        return False


def stable_json(value) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=True, indent=1)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
