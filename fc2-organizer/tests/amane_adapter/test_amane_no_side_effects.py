"""P5-C1 §23（E19）：无文件系统 / 持久化 / 网络 socket 副作用。静态 AST 守护见 test_amane_architecture_guards。"""

from __future__ import annotations

import ast
import asyncio
import os
import socket
from pathlib import Path

from _amane_scenarios import client_4825061, client_4979299, runtime_for
from fc2_amane_adapter import _settings as _module_under_test
from fc2_amane_adapter._outcome import AdapterFound
from fc2_amane_adapter._runtime import AdapterRuntime
from fc2_amane_adapter._settings import parse_settings

TREE = Path(_module_under_test.__file__).resolve().parent  # 被测模块实际所在的树


def _snapshot(root: Path) -> dict[str, tuple[int, int]]:
    result = {}
    for path in sorted(root.rglob("*")):
        if "__pycache__" in path.parts:
            continue
        stat = path.stat()
        result[str(path.relative_to(root))] = (stat.st_size, stat.st_mtime_ns)
    return result


def _blocked(*_args, **_kwargs):
    raise AssertionError("the adapter must never open a socket connection")


def test_running_every_path_leaves_the_filesystem_environment_and_network_untouched(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    environ_before = dict(os.environ)
    tree_before = _snapshot(TREE)
    cwd_before = _snapshot(tmp_path)

    async def scenario():
        # 事件循环已建立之后再封堵连接（Windows 的 socketpair 仿真需要回环 connect）。
        monkeypatch.setattr(socket.socket, "connect", _blocked)
        monkeypatch.setattr(socket.socket, "connect_ex", _blocked)
        monkeypatch.setattr(socket, "create_connection", _blocked)
        monkeypatch.setattr(socket, "getaddrinfo", _blocked)
        outcomes = []
        for client, number in ((client_4825061(), "FC2-PPV-4825061"), (client_4979299(), "FC2-PPV-4979299")):
            outcomes.append(await AdapterRuntime(parse_settings({}), client).lookup(number, "fc2"))
        outcomes.append(await runtime_for(client_4825061()).lookup("ABC-1", "fc2"))
        return outcomes

    outcomes = asyncio.run(scenario())
    assert isinstance([o for o in outcomes if isinstance(o, AdapterFound)][0], AdapterFound)
    assert dict(os.environ) == environ_before
    assert _snapshot(tmp_path) == cwd_before == {}
    assert _snapshot(TREE) == tree_before


def test_the_plugin_never_uses_the_host_data_dir_or_any_persistence_api():
    source = (TREE / "plugin.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    attributes = {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    assert "data_dir" not in attributes | names
    assert not (attributes | names) & {"open", "write_text", "write_bytes", "mkdir", "Path", "sqlite3", "shelve", "pickle"}


def test_the_adapter_tree_contains_only_python_modules():
    assert {p.suffix for p in TREE.iterdir() if p.is_file()} == {".py"}
