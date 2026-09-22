"""P4-C4: ``render_movie_nfo`` performs no filesystem, network, clock, randomness,
environment, locale or cwd access (contract section 13).

Every trap category is first proven to fire (positive controls), so a passing
render under the traps is not vacuous (cf. P4-C3-R-02).
"""

from __future__ import annotations

import builtins
import datetime as dt
import io
import locale
import os
import pathlib
import random
import shutil
import socket
import time
import urllib.request
import uuid

import pytest

import fc2_organizer.nfo.renderer as renderer_module
from fc2_organizer.nfo import (
    NfoInputError,
    NfoMetadataError,
    NfoReleaseDateError,
    NfoXmlCharacterError,
    render_movie_nfo,
)

from ._builders import NON_RENDERED_FIELDS, forge, make_record
from ._guards import SideEffectAttempted, traps

FULL = dict(
    title="A & B 日本語 🎬", plot="p\r\nq", runtime=0, release="2024-02-29", studio="S",
    actors=("a", " ", "b"), tags=("t", "t"), **NON_RENDERED_FIELDS,
)


# ---- positive controls: each trap category really fires -----------------------------------------------------------------


FILESYSTEM_PROBES = {
    "open": lambda p: open(p, "rb"),
    "io.open": lambda p: io.open(p, "rb"),
    "os.stat": lambda p: os.stat(p),
    "os.listdir": lambda p: os.listdir(p),
    "os.scandir": lambda p: os.scandir(p),
    "os.getcwd": lambda p: os.getcwd(),
    "os.path.exists": lambda p: os.path.exists(p),
    "os.path.realpath": lambda p: os.path.realpath(p),
    "os.path.abspath": lambda p: os.path.abspath(p),
    "Path.exists": lambda p: pathlib.Path(p).exists(),
    "Path.resolve": lambda p: pathlib.Path(p).resolve(),
    "Path.read_text": lambda p: pathlib.Path(p).read_text(),
    "Path.cwd": lambda p: pathlib.Path.cwd(),
    "shutil.copy": lambda p: shutil.copy(p, p),
}
NETWORK_PROBES = {
    "socket.socket": lambda: socket.socket(),
    "socket.create_connection": lambda: socket.create_connection(("127.0.0.1", 9)),
    "socket.getaddrinfo": lambda: socket.getaddrinfo("example.invalid", 80),
    "urllib.request.urlopen": lambda: urllib.request.urlopen("http://127.0.0.1:9/"),
}
CLOCK_RANDOM_PROBES = {
    "time.time": lambda: time.time(),
    "time.monotonic": lambda: time.monotonic(),
    "time.perf_counter": lambda: time.perf_counter(),
    "time.localtime": lambda: time.localtime(),
    "datetime.date.today": lambda: dt.date.today(),
    "datetime.datetime.now": lambda: dt.datetime.now(),
    "datetime.datetime.today": lambda: dt.datetime.today(),
    "renderer.date.today": lambda: renderer_module.date.today(),
    "random.random": lambda: random.random(),
    "random.choice": lambda: random.choice([1, 2]),
    "uuid.uuid4": lambda: uuid.uuid4(),
    "uuid.uuid1": lambda: uuid.uuid1(),
    "os.urandom": lambda: os.urandom(4),
}
ENVIRONMENT_PROBES = {
    "os.environ[...]": lambda: os.environ["PATH"],
    "os.environ.get": lambda: os.environ.get("PATH"),
    "os.getenv": lambda: os.getenv("PATH"),
    "locale.getlocale": lambda: locale.getlocale(),
    "locale.getpreferredencoding": lambda: locale.getpreferredencoding(),
}


@pytest.mark.parametrize("name", list(FILESYSTEM_PROBES))
def test_positive_control_filesystem_trap_fires(name, tmp_path):
    target = str(tmp_path / "x")
    with traps("filesystem"):
        with pytest.raises(SideEffectAttempted):
            FILESYSTEM_PROBES[name](target)


@pytest.mark.parametrize("name", list(NETWORK_PROBES))
def test_positive_control_network_trap_fires(name):
    with traps("network"):
        with pytest.raises(SideEffectAttempted):
            NETWORK_PROBES[name]()


def test_positive_control_httpx_trap_fires_when_httpx_is_installed():
    httpx = pytest.importorskip("httpx")
    with traps("network"):
        with httpx.Client() as client, pytest.raises(SideEffectAttempted):
            client.get("http://127.0.0.1:9/")


@pytest.mark.parametrize("name", list(CLOCK_RANDOM_PROBES))
def test_positive_control_clock_and_random_trap_fires(name):
    with traps("clock_random"):
        with pytest.raises(SideEffectAttempted):
            CLOCK_RANDOM_PROBES[name]()


@pytest.mark.parametrize("name", list(ENVIRONMENT_PROBES))
def test_positive_control_environment_trap_fires(name):
    with traps("environment"):
        with pytest.raises(SideEffectAttempted):
            ENVIRONMENT_PROBES[name]()


def test_pure_date_parser_is_not_trapped():
    """``date.fromisoformat`` reads no clock, so it must keep working under the traps."""
    with traps("clock_random"):
        assert renderer_module.date.fromisoformat("2024-02-29") == dt.date(2024, 2, 29)
        with pytest.raises(ValueError):
            renderer_module.date.fromisoformat("2026-02-30")


def test_traps_are_removed_after_the_block():
    with traps():
        pass
    assert builtins.open is io.open and callable(os.getcwd)
    assert renderer_module.date is dt.date and dt.date.today() is not None
    assert os.environ.get("PATH") is not None


# ---- renders under every trap ---------------------------------------------------------------------------------------------


SCENARIOS = {
    "full_render": (lambda: make_record(**FULL), None),
    "minimum_render": (lambda: make_record(), None),
    "invalid_date": (lambda: make_record(release="2026-02-30"), NfoReleaseDateError),
    "invalid_xml_char": (lambda: make_record(plot="a\x00b"), NfoXmlCharacterError),
    "invalid_input": (lambda: None, NfoInputError),
    "forged_shape": (lambda: forge(actors=["a"]), NfoMetadataError),
}


@pytest.mark.parametrize("scenario", list(SCENARIOS))
def test_render_performs_no_io_clock_random_or_environment_access(scenario):
    build, expected_error = SCENARIOS[scenario]
    record = build()  # built outside the traps: only rendering is under test
    with traps():
        if expected_error is None:
            xml = render_movie_nfo(record)
        else:
            with pytest.raises(expected_error):
                render_movie_nfo(record)
    if expected_error is None:
        assert xml.startswith("<?xml") and xml == render_movie_nfo(record)


def test_render_under_traps_equals_render_without_traps():
    record = make_record(**FULL)
    free = render_movie_nfo(record)
    with traps():
        trapped = render_movie_nfo(record)
    assert trapped == free
