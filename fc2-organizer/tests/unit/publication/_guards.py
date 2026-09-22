"""Guard utilities shared by the P4-C3 publication tests: an object-graph walker
(for the diagnostics-exclusion checks) and filesystem / network API traps."""

from __future__ import annotations

import builtins
import io
import os
import pathlib
import shutil
import socket
import types
import urllib.request
from collections.abc import Mapping
from enum import Enum

from fc2_metadata_core.aggregation import AggregationResult, SourceAttempt, SourceExecutionTrace
from fc2_metadata_core.models import SourceResult

FORBIDDEN_TYPES = (AggregationResult, SourceResult, SourceExecutionTrace, SourceAttempt, BaseException)
FORBIDDEN_ATTRIBUTE_NAMES = {
    "error_detail", "error_kind", "traceback", "__traceback__", "args", "response", "body", "cookie", "cookies",
    "headers", "source_results", "source_execution_traces", "attempts", "final_result",
}


def walk(root: object) -> list[tuple[str, object]]:
    """Every object reachable from ``root`` through attributes / items, with its path."""
    seen: set[int] = set()
    found: list[tuple[str, object]] = []
    stack: list[tuple[str, object]] = [("record", root)]
    while stack:
        path, obj = stack.pop()
        if id(obj) in seen:
            continue
        seen.add(id(obj))
        found.append((path, obj))
        if isinstance(obj, (str, bytes, int, float, bool, type(None), Enum, type)):
            continue
        if isinstance(obj, (tuple, list, frozenset, set)):
            stack.extend((f"{path}[{i}]", item) for i, item in enumerate(obj))
            continue
        if isinstance(obj, (Mapping, types.MappingProxyType)):
            for key, value in obj.items():
                stack.append((f"{path}.key({key!r})", key))
                stack.append((f"{path}[{key!r}]", value))
            continue
        names: list[str] = []
        for klass in type(obj).__mro__:
            slots = klass.__dict__.get("__slots__", ())
            names.extend([slots] if isinstance(slots, str) else slots)
        names.extend(getattr(obj, "__dict__", {}).keys())
        for name in names:
            if hasattr(obj, name):
                stack.append((f"{path}.{name}", getattr(obj, name)))
    return found


class SideEffectAttempted(AssertionError):
    pass


def trap(name):
    def _raise(*args, **kwargs):
        raise SideEffectAttempted(f"prepare_publication called {name}")

    return _raise


FS_OS = [
    "stat", "lstat", "listdir", "scandir", "open", "mkdir", "makedirs", "rename", "replace", "remove", "unlink",
    "rmdir", "removedirs", "chmod", "utime", "symlink", "link", "access", "readlink", "walk",
]
FS_OS_PATH = ["exists", "lexists", "isfile", "isdir", "islink", "realpath", "getsize", "getmtime", "samefile"]
FS_PATHLIB = [
    "exists", "stat", "lstat", "resolve", "is_file", "is_dir", "open", "read_text", "read_bytes", "write_text",
    "write_bytes", "mkdir", "touch", "rename", "replace", "unlink", "rmdir", "iterdir", "glob", "rglob",
    "samefile", "symlink_to",
]
FS_SHUTIL = ["move", "copy", "copy2", "copyfile", "copytree", "rmtree"]


def install_traps(monkeypatch):
    for name in FS_OS:
        if hasattr(os, name):
            monkeypatch.setattr(os, name, trap(f"os.{name}"))
    for name in FS_OS_PATH:
        monkeypatch.setattr(os.path, name, trap(f"os.path.{name}"))
    for name in FS_PATHLIB:
        if hasattr(pathlib.Path, name):
            monkeypatch.setattr(pathlib.Path, name, trap(f"Path.{name}"))
    for name in FS_SHUTIL:
        monkeypatch.setattr(shutil, name, trap(f"shutil.{name}"))
    monkeypatch.setattr(builtins, "open", trap("open"))
    monkeypatch.setattr(io, "open", trap("io.open"))
    # network
    monkeypatch.setattr(socket, "socket", trap("socket.socket"))
    monkeypatch.setattr(socket, "create_connection", trap("socket.create_connection"))
    monkeypatch.setattr(socket, "getaddrinfo", trap("socket.getaddrinfo"))
    monkeypatch.setattr(urllib.request, "urlopen", trap("urllib.request.urlopen"))
    try:
        import httpx
    except ImportError:  # pragma: no cover
        httpx = None
    if httpx is not None:
        for cls in (httpx.Client, httpx.AsyncClient):
            monkeypatch.setattr(cls, "send", trap(f"{cls.__name__}.send"))
            monkeypatch.setattr(cls, "request", trap(f"{cls.__name__}.request"))
    try:
        import requests
    except ImportError:
        requests = None
    if requests is not None:  # pragma: no cover - not a dependency of this project
        monkeypatch.setattr(requests.Session, "request", trap("requests.Session.request"))
