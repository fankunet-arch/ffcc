"""I/O, clock, randomness and environment traps for the P4-C4 NFO tests.

``traps()`` is a context manager (``pytest.MonkeyPatch.context``), so the
traps are active only around the code under test -- never while pytest itself
reads ``os.environ`` between test phases. Every trap raises
``SideEffectAttempted``; ``test_nfo_no_side_effects.py`` proves each category
actually fires (positive controls) before relying on it.

``datetime.date.fromisoformat`` is deliberately *not* trapped: it is a pure
parser and reads no clock. ``date.today`` / ``datetime.now`` / ``today`` /
``utcnow`` are trapped by swapping in subclasses whose clock methods raise,
both on the ``datetime`` module and on the renderer module's own ``date``
binding.
"""

from __future__ import annotations

import builtins
import contextlib
import datetime as dt
import io
import locale
import os
import pathlib
import random
import secrets
import shutil
import socket
import time
import urllib.request
import uuid
from collections.abc import Iterator, Mapping

import pytest

import fc2_organizer.nfo.renderer as renderer_module


class SideEffectAttempted(AssertionError):
    pass


def trap(name: str):
    def _raise(*args, **kwargs):
        raise SideEffectAttempted(f"render_movie_nfo called {name}")

    return _raise


def _trap_classmethod(name: str):
    return classmethod(lambda cls, *a, **k: trap(name)())


class TrapDate(dt.date):
    today = _trap_classmethod("date.today")


class TrapDateTime(dt.datetime):
    today = _trap_classmethod("datetime.today")
    now = _trap_classmethod("datetime.now")
    utcnow = _trap_classmethod("datetime.utcnow")


class TrapEnviron(Mapping):
    def __getitem__(self, key):
        trap("os.environ[...]")()

    def __iter__(self):
        trap("iter(os.environ)")()

    def __len__(self):
        trap("len(os.environ)")()

    def get(self, key, default=None):
        trap("os.environ.get")()

    def __contains__(self, key):
        trap("in os.environ")()


FS_OS = [
    "stat", "lstat", "listdir", "scandir", "open", "mkdir", "makedirs", "rename", "replace", "remove", "unlink",
    "rmdir", "removedirs", "chmod", "utime", "symlink", "link", "access", "readlink", "walk", "getcwd", "chdir",
]
FS_OS_PATH = [
    "exists", "lexists", "isfile", "isdir", "islink", "realpath", "abspath", "getsize", "getmtime", "samefile",
]
FS_PATHLIB = [
    "exists", "stat", "lstat", "resolve", "absolute", "cwd", "is_file", "is_dir", "open", "read_text", "read_bytes",
    "write_text", "write_bytes", "mkdir", "touch", "rename", "replace", "unlink", "rmdir", "iterdir", "glob", "rglob",
    "samefile", "symlink_to",
]
FS_SHUTIL = ["move", "copy", "copy2", "copyfile", "copytree", "rmtree"]
CLOCK_TIME = [
    "time", "time_ns", "monotonic", "monotonic_ns", "perf_counter", "perf_counter_ns", "process_time", "localtime",
    "gmtime", "strftime", "ctime", "sleep",
]
RANDOM_FUNCS = ["random", "randint", "randrange", "choice", "choices", "shuffle", "sample", "getrandbits", "uniform"]


def _install_filesystem(m: pytest.MonkeyPatch) -> None:
    for name in FS_OS:
        if hasattr(os, name):
            m.setattr(os, name, trap(f"os.{name}"))
    for name in FS_OS_PATH:
        m.setattr(os.path, name, trap(f"os.path.{name}"))
    for name in FS_PATHLIB:
        if hasattr(pathlib.Path, name):
            m.setattr(pathlib.Path, name, trap(f"Path.{name}"))
    for name in FS_SHUTIL:
        m.setattr(shutil, name, trap(f"shutil.{name}"))
    m.setattr(builtins, "open", trap("open"))
    m.setattr(io, "open", trap("io.open"))


def _install_network(m: pytest.MonkeyPatch) -> None:
    m.setattr(socket, "socket", trap("socket.socket"))
    m.setattr(socket, "create_connection", trap("socket.create_connection"))
    m.setattr(socket, "getaddrinfo", trap("socket.getaddrinfo"))
    m.setattr(urllib.request, "urlopen", trap("urllib.request.urlopen"))
    try:
        import httpx
    except ImportError:  # pragma: no cover
        httpx = None
    if httpx is not None:
        for cls in (httpx.Client, httpx.AsyncClient):
            m.setattr(cls, "send", trap(f"{cls.__name__}.send"))
            m.setattr(cls, "request", trap(f"{cls.__name__}.request"))
    try:
        import requests
    except ImportError:
        requests = None
    if requests is not None:  # pragma: no cover - not a dependency of this project
        m.setattr(requests.Session, "request", trap("requests.Session.request"))


def _install_clock_random(m: pytest.MonkeyPatch) -> None:
    for name in CLOCK_TIME:
        m.setattr(time, name, trap(f"time.{name}"))
    m.setattr(dt, "date", TrapDate)
    m.setattr(dt, "datetime", TrapDateTime)
    m.setattr(renderer_module, "date", TrapDate)
    for name in RANDOM_FUNCS:
        m.setattr(random, name, trap(f"random.{name}"))
    m.setattr(uuid, "uuid1", trap("uuid.uuid1"))
    m.setattr(uuid, "uuid4", trap("uuid.uuid4"))
    m.setattr(os, "urandom", trap("os.urandom"))
    m.setattr(secrets, "token_bytes", trap("secrets.token_bytes"))


def _install_environment(m: pytest.MonkeyPatch) -> None:
    m.setattr(os, "environ", TrapEnviron())
    m.setattr(os, "getenv", trap("os.getenv"))
    for name in ("getlocale", "getpreferredencoding", "setlocale", "localeconv", "getencoding"):
        if hasattr(locale, name):
            m.setattr(locale, name, trap(f"locale.{name}"))


INSTALLERS = {
    "filesystem": _install_filesystem,
    "network": _install_network,
    "clock_random": _install_clock_random,
    "environment": _install_environment,
}


@contextlib.contextmanager
def traps(*categories: str) -> Iterator[None]:
    """Trap the given categories (default: all) for the duration of the block."""
    with pytest.MonkeyPatch.context() as m:
        for category in categories or tuple(INSTALLERS):
            INSTALLERS[category](m)
        yield
