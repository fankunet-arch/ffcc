"""P5-C2：127.0.0.1 回环 HTTP fixture（合同第 11.5 节：宿主见证不访问外部站点）。

由**网关进程**（``tools/run_amane_compat_gate.py``）启动；宿主（源码宿主进程或冻结桌面进程）里的真实 ``WebClient`` 经
``base_url`` 覆盖请求它。只依赖标准库；pytest 从不导入本目录（``host_scripts``）；主进程测试可直接加载它做单元断言。

路由（与 Core 三个来源适配器的 URL 形状一致）::

    /fc2db/work/<digits>/                     -> fc2db_net
    /javdb/search?q=FC2-PPV-<digits>          -> javdb
    /av123/en/v/fc2-ppv-<digits>              -> av123

行为由 ``<digits>`` 决定（见 ``BEHAVIORS``）；``digits`` 是 5..8 位数字，满足 canonical FC2 号。
所有响应都是确定的；请求日志只记录（来源、digits、方法），不记录端口 / 时间 / 绝对路径。
"""

from __future__ import annotations

import re
import threading
import time
from collections import defaultdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

SOURCES = ("fc2db_net", "javdb", "av123")
PREFIX = {"fc2db_net": "/fc2db", "javdb": "/javdb", "av123": "/av123"}
HANG_SECONDS = 30.0

#: digits -> {来源: (状态码, 夹具相对路径 | 固定特殊体)}；未列出的来源 -> 404 空页。
BEHAVIORS: dict[str, dict[str, tuple]] = {
    # 成功：三个来源都命中（字段冲突 / 复数窄化 / 来源归属）
    "4979299": {"fc2db_net": (200, "fc2db_net/work_4979299.html"), "javdb": (200, "javdb/search_hit_4979299.html"), "av123": (200, "av123/detail_4979299.html")},
    # PARTIAL：fc2db 404，其它命中
    "4825061": {"fc2db_net": (404, "fc2db_net/work_404_4825061.html"), "javdb": (200, "javdb/search_hit_4825061.html"), "av123": (200, "av123/detail_4825061.html")},
    # 未命中：全部来源回答“没有这部影片”
    "4824605": {"fc2db_net": (404, "fc2db_net/work_404_4825061.html"), "av123": (404, "av123/detail_404_4824605.html"), "javdb": (200, "javdb/search_no_exact_4824605.html")},
}
_UNIFORM = {
    "90000001": (403, "text:blocked"),
    "90000002": (429, "text:rate limited"),
    "90000003": (200, "hang"),
    "90000004": (200, "hang"),
    "90000005": (503, "text:unavailable"),
    "90000006": (200, "text:<html><body>no usable markup</body></html>"),
    "90000007": (200, "huge"),
    "90000008": (200, "badcharset"),
    "90000009": (302, "redirect"),
    "90000010": (403, "cloudflare"),
}
for _digits, _spec in _UNIFORM.items():
    BEHAVIORS[_digits] = {source: _spec for source in SOURCES}

HUGE_BYTES = 3 * 1024 * 1024
_PATTERNS = (
    ("fc2db_net", re.compile(r"^/fc2db/work/(\d{5,8})/?$")),
    ("javdb", re.compile(r"^/javdb/search$")),
    ("av123", re.compile(r"^/av123/en/v/fc2-ppv-(\d{5,8})$")),
)


class _QuietServer(ThreadingHTTPServer):
    """客户端提前断开（超时 / 取消用例）不是错误：不向 stderr 打印回溯。"""

    def handle_error(self, request, client_address):
        return None


class LoopbackFixture:
    def __init__(self, fixture_root: Path) -> None:
        self.fixture_root = Path(fixture_root)
        self.log: list[tuple[str, str]] = []
        self._lock = threading.Lock()
        self._stop = threading.Event()
        owner = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def do_GET(self) -> None:  # noqa: N802
                owner._handle(self)

            def log_message(self, *args) -> None:
                return None

        self._server = _QuietServer(("127.0.0.1", 0), Handler)
        self._server.daemon_threads = True
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    # ------------------------------------------------------------------ 生命周期
    def start(self) -> "LoopbackFixture":
        self._thread.start()
        return self

    def stop(self) -> None:
        self._stop.set()
        self._server.shutdown()
        self._server.server_close()

    def __enter__(self) -> "LoopbackFixture":
        return self.start()

    def __exit__(self, *exc) -> bool:
        self.stop()
        return False

    @property
    def port(self) -> int:
        return self._server.server_address[1]

    def base_url(self, source_id: str) -> str:
        return f"http://127.0.0.1:{self.port}{PREFIX[source_id]}"

    def reset(self) -> None:
        with self._lock:
            self.log.clear()

    def counts(self) -> dict[str, int]:
        """按来源的请求数（确定性观测；不含端口 / 时间）。"""
        result: dict[str, int] = defaultdict(int)
        with self._lock:
            for source, _digits in self.log:
                result[source] += 1
        return dict(sorted(result.items()))

    def counts_for(self, digits: str) -> dict[str, int]:
        """某个 ``digits`` 在每个来源上的请求数（重定向后续跳转不计入）。"""
        result: dict[str, int] = defaultdict(int)
        with self._lock:
            for source, seen in self.log:
                if seen == digits:
                    result[source] += 1
        return dict(sorted(result.items()))

    def sequence(self) -> list[str]:
        with self._lock:
            return [source for source, _digits in self.log]

    # ------------------------------------------------------------------ 请求处理
    def _identify(self, path: str, query: str) -> tuple[str, str] | None:
        for source, pattern in _PATTERNS:
            match = pattern.match(path)
            if match is None:
                continue
            if source == "javdb":
                values = parse_qs(query).get("q", [""])[0]
                tail = re.fullmatch(r"FC2-PPV-(\d{5,8})", values)
                return (source, tail.group(1)) if tail else None
            return source, match.group(1)
        return None

    def _read(self, relative: str) -> bytes:
        return (self.fixture_root / relative).read_bytes()

    def _reply(self, handler: BaseHTTPRequestHandler, status: int, body: bytes, content_type: str = "text/html; charset=utf-8") -> None:
        handler.send_response(status)
        handler.send_header("Content-Type", content_type)
        handler.send_header("Content-Length", str(len(body)))
        handler.send_header("Connection", "close")
        handler.end_headers()
        try:
            handler.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass

    def _handle(self, handler: BaseHTTPRequestHandler) -> None:
        parts = urlsplit(handler.path)
        if re.fullmatch(r"/(fc2db|javdb|av123)/r\d+", parts.path):  # 重定向环的后续跳转
            with self._lock:
                self.log.append(({"fc2db": "fc2db_net", "javdb": "javdb", "av123": "av123"}[parts.path.split("/")[1]], "redirect-hop"))
            handler.send_response(302)
            handler.send_header("Location", f"{parts.path.split('/r')[0]}/r{len(self.log)}")
            handler.send_header("Content-Length", "0")
            handler.end_headers()
            return
        identified = self._identify(parts.path, parts.query)
        if identified is None:
            self._reply(handler, 404, b"not found", "text/plain; charset=utf-8")
            return
        source, digits = identified
        with self._lock:
            self.log.append((source, digits))
        status, spec = BEHAVIORS.get(digits, {}).get(source, (404, "text:no fixture"))
        if spec == "hang":
            self._stop.wait(HANG_SECONDS)
            self._reply(handler, 200, b"too late")
        elif spec == "huge":
            self._reply(handler, 200, b"A" * HUGE_BYTES)
        elif spec == "badcharset":
            self._reply(handler, 200, b"<html>x</html>", "text/html; charset=x-no-such-charset")
        elif spec == "redirect":
            handler.send_response(302)
            handler.send_header("Location", f"{PREFIX[source]}/r1")
            handler.send_header("Content-Length", "0")
            handler.end_headers()
        elif spec == "cloudflare":
            self._reply(handler, 403, self._read("common/cloudflare_challenge.html"))
        elif spec.startswith("text:"):
            self._reply(handler, status, spec[5:].encode("utf-8"))
        else:
            self._reply(handler, status, self._read(spec))
        time.sleep(0)
