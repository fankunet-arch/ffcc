"""P4-C10 acceptance harness: the real Phase 4 chain over disposable trees (contract sections 5, 12; plan section 5).

Real below the two network boundaries: ``discover_media`` -> real ``MultiSourceEngine`` (scripted ``SourceAdapter``s) ->
real ``BatchOrchestrator`` -> real ``HttpxImageClient`` over ``httpx.MockTransport`` -> real P4-C7 / P4-C6 execution ->
real P4-C8 retry / merge -> real P4-C9 diagnostics. Only the authorized seams of contract section 12.6 are used for fault
injection; the write observer (12.5), the sandbox guard (12.2), the socket trap (SI-20) and the concurrency probes are
transparent call-through wrappers.

Every ``fc2_*`` name is imported at module level (contract section 12.7). All modifying acceptance work happens inside
the ``tmp_path`` tree handed to ``Chain`` (contract section 3.4.2); repository files are only read.
"""

from __future__ import annotations

import asyncio
import builtins
import dataclasses
import io
import os
import socket
import stat
import threading
from collections import Counter
from contextlib import contextmanager
from typing import Callable, Iterable

import httpx
from fc2_metadata_core.aggregation import AggregationConfig, MultiSourceEngine, RetryPolicy, SourceConfig
from fc2_metadata_core.models.source_result import SourceStatus
from fc2_metadata_core.sources.registry import SourceRegistry
from fc2_organizer.diagnostics import (
    PathPolicy,
    build_execution_diagnostics,
    build_preview_diagnostics,
    render_diagnostics_json,
)
from fc2_organizer.discovery import discover_media
from fc2_organizer.execution import _fs as execution_fs
from fc2_organizer.images.transport import HttpxImageClient
from fc2_organizer.materialization import atomic as materialization_atomic
from fc2_organizer.orchestration import (
    BatchExecutionResult,
    BatchOrchestrator,
    BatchPreview,
    OrchestrationConfig,
    merge_retry,
)
from fc2_organizer.orchestration import execute as orchestration_execute
from support.fake_http_client import FakeHttpClient
from support.scripted_adapters import failed as scripted_failed
from support.scripted_adapters import ok as scripted_ok
from support.scripted_adapters import scripted_adapter_class

from . import _corpus
from ._corpus import FAIL_DETAIL, SOURCE_IDS, Film, image_behavior, image_payload
from ._oracles import (
    AcceptanceGateViolation,
    gate_indices_exactly_once,
    gate_no_network,
    gate_no_unreported_temporaries,
    gate_path_within,
    gate_result_accounting,
    gate_snapshots_equal,
    gate_source_not_lost,
    gate_write_paths_contained,
    sha256_file,
    snapshot_tree,
)

__all__ = [
    "WAIT",
    "Sandbox",
    "WriteObserver",
    "SocketTrap",
    "trapped_primitives",
    "FaultInjector",
    "HoldGate",
    "AsyncReverse",
    "ThreadReverse",
    "ScriptedSources",
    "ImageRoutes",
    "ExecProbe",
    "Chain",
    "result_projection",
    "diagnostics_bytes",
]

WAIT = 30.0  # hang protection only: every gate is an event / condition, never a correctness sleep


def _violation(message: str) -> None:
    raise AcceptanceGateViolation(message)


# --------------------------------------------------------------------------- sandbox guard (contract 3.4.2, 12.2)


class Sandbox:
    """The disposable acceptance root. Registered roots must lie inside ``tmp_path``; the guard refuses everything
    else (the repository work tree, the home directory, any other path). Reading repository files is not guarded."""

    def __init__(self, tmp_path) -> None:
        self.root = os.path.realpath(str(tmp_path))
        self._refuse_unsafe_root()
        self.registered: list[str] = []

    def _refuse_unsafe_root(self) -> None:
        """The root must be neither the repository work tree, nor inside it, nor one of its ancestors."""
        repository = os.path.normcase(os.path.realpath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))
        probe = os.path.normcase(self.root)
        if (probe == repository or probe.startswith(repository + os.sep) or repository.startswith(probe + os.sep)
                or os.path.dirname(self.root) == self.root):
            _violation(f"sandbox: {self.root!r} is the repository work tree, lies inside it or contains it")

    def require(self, path: str, what: str = "path") -> str:
        """Assert that ``path`` is inside the disposable root; returns the path unchanged."""
        gate_path_within(os.path.abspath(path), self.root, f"sandbox ({what})")
        return path

    def register_root(self, path: str) -> str:
        self.require(path, "registered root")
        self.registered.append(path)
        return path


# --------------------------------------------------------------------------- write observer (contract 12.5)

_WRITE_MODE_FLAGS = os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND | getattr(os, "O_EXCL", 0)
_OS_MUTATORS = ("mkdir", "makedirs", "rename", "replace", "remove", "unlink", "rmdir", "link", "symlink")


class WriteObserver:
    """Records every modifying path-bearing call (call-through; return value, exception and order are untouched).
    ``records`` = ``[(operation, (paths...)), ...]`` since the last ``take()``; observation is off while ``paused``."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._records: list[tuple[str, tuple[str, ...]]] = []
        self._paused = 0
        self.total = 0

    @contextmanager
    def paused(self):
        with self._lock:
            self._paused += 1
        try:
            yield
        finally:
            with self._lock:
                self._paused -= 1

    def record(self, operation: str, paths: Iterable[str]) -> None:
        with self._lock:
            if self._paused:
                return
            self.total += 1
            self._records.append((operation, tuple(os.fspath(p) for p in paths)))

    def take(self) -> list[tuple[str, tuple[str, ...]]]:
        with self._lock:
            taken, self._records = self._records, []
        return taken

    # ---- wrappers for builtins.open / io.open / os.open and the os-level mutators

    def wrap_open(self, real):
        def observed_open(file, mode="r", *args, **kwargs):
            if isinstance(file, (str, bytes, os.PathLike)) and any(flag in mode for flag in "wax+"):
                self.record("open(write)", [os.fsdecode(file)])
            return real(file, mode, *args, **kwargs)

        return observed_open

    def wrap_os_open(self, real):
        def observed_os_open(path, flags, *args, **kwargs):
            if flags & _WRITE_MODE_FLAGS:
                self.record("os.open(write)", [os.fsdecode(path)])
            return real(path, flags, *args, **kwargs)

        return observed_os_open

    def wrap_os_mutator(self, name: str, real):
        def observed(*args, **kwargs):
            self.record(f"os.{name}", [os.fsdecode(a) for a in args if isinstance(a, (str, bytes, os.PathLike))])
            return real(*args, **kwargs)

        return observed


# --------------------------------------------------------------------------- socket trap (SI-20)

_LOOPBACK = frozenset({"127.0.0.1", "::1", "localhost"})


class SocketTrap:
    """Any attempt to resolve a name or connect to a non-loopback address raises ``AcceptanceGateViolation`` and is
    recorded in ``hits`` (a production layer that swallows the exception still leaves the evidence). The event loop's own
    loopback socket pair is allowed; ``MockTransport`` and ``FakeHttpClient`` use no socket at all."""

    def __init__(self) -> None:
        self.hits: list[str] = []

    def _trap(self, name: str):
        def trapped(*_args, **_kwargs):
            self.hits.append(name)
            raise AcceptanceGateViolation(f"network primitive used: {name}")

        return trapped

    def _connect(self, name: str, real):
        def connect(sock, address, *args, **kwargs):
            host = address[0] if isinstance(address, tuple) and address else None
            if host in _LOOPBACK:
                return real(sock, address, *args, **kwargs)
            self.hits.append(f"socket.{name}")
            raise AcceptanceGateViolation(f"network primitive used: socket.{name}")

        return connect

    def exercise(self) -> list[str]:
        """Positive control: touch every trapped primitive once (while installed) and return the recorded hits. The
        only place of the C10 tests that names ``socket``-level calls, so the architecture guard can confine it."""
        for call in (lambda: socket.create_connection(("c10-acceptance.invalid", 80), timeout=1),
                     lambda: socket.getaddrinfo("c10-acceptance.invalid", 80),
                     lambda: socket.gethostbyname("c10-acceptance.invalid"),
                     lambda: socket.socket().connect(("203.0.113.1", 9))):
            try:
                call()
            except AcceptanceGateViolation:
                pass
        return list(self.hits)

    def install(self, patches: "PatchSet") -> None:
        for name in ("create_connection", "getaddrinfo", "gethostbyname", "gethostbyname_ex"):
            patches.setattr(socket, name, self._trap(f"socket.{name}"))
        for name in ("connect", "connect_ex"):
            patches.setattr(socket.socket, name, self._connect(name, getattr(socket.socket, name)))


def trapped_primitives() -> list[tuple[object, str]]:
    """The (owner, name) pairs the socket trap replaces while a ``Chain`` is installed (restoration checks)."""
    return [(socket, "create_connection"), (socket, "getaddrinfo"), (socket, "gethostbyname"),
            (socket, "gethostbyname_ex"), (socket.socket, "connect"), (socket.socket, "connect_ex")]


# --------------------------------------------------------------------------- patch bookkeeping


class PatchSet:
    """Attribute replacements of the harness itself, restored in reverse order with an identity check."""

    def __init__(self) -> None:
        self._stack: list[tuple[object, str, object, object]] = []

    def setattr(self, target: object, name: str, value: object) -> object:
        original = getattr(target, name)
        setattr(target, name, value)
        self._stack.append((target, name, original, value))
        return original

    def restore(self) -> None:
        while self._stack:
            target, name, original, installed = self._stack.pop()
            if getattr(target, name) is not installed:
                _violation(f"harness: {name} was replaced by someone else and not restored before the harness ended")
            setattr(target, name, original)


# --------------------------------------------------------------------------- fault injection (contract 12.6)


class FaultInjector:
    """One-shot, per-entry faults through the authorized ``_FS`` seams. A rule names the seam, the operation and the
    exact path (an argument equal to it after normalization); it fires once, only while ``armed``, and the test must
    prove that every rule fired (``assert_all_fired``)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._rules: list[dict] = []
        self.armed = False
        self.fired: list[tuple[str, str, str]] = []

    @staticmethod
    def _key(path: str) -> str:
        return os.path.normcase(os.path.normpath(path))

    def fail(self, seam: str, op: str, path: str, exc: BaseException) -> None:
        assert seam in ("execution", "materialization")
        with self._lock:
            self._rules.append(dict(seam=seam, op=op, path=self._key(path), exc=exc, fired=False))

    def match(self, seam: str, op: str, paths: list[str]) -> BaseException | None:
        if not self.armed:
            return None
        keys = [self._key(p) for p in paths]
        with self._lock:
            for rule in self._rules:
                if (not rule["fired"] and rule["seam"] == seam and rule["op"] == op and rule["path"] in keys):
                    rule["fired"] = True
                    self.fired.append((seam, op, rule["path"]))
                    return rule["exc"]
        return None

    @property
    def pending(self) -> list[dict]:
        return [rule for rule in self._rules if not rule["fired"]]

    def assert_all_fired(self) -> None:
        if self.pending:
            _violation(f"fault injection: {len(self.pending)} injected fault(s) never fired (vacuous injection)")

    def clear_fired(self) -> None:
        with self._lock:
            self._rules = [rule for rule in self._rules if not rule["fired"]]


class FsLayer:
    """Installs one wrapper per ``_FS`` seam: write observation, fault injection and forced cross-volume device
    reporting. The wrapped operations call through unchanged when no rule matches."""

    _OBSERVED = {
        "execution": ("mkdir", "rename", "link", "unlink"),
        "materialization": ("publish", "unlink"),
    }
    _PATH_OPS = {
        "execution": ("lstat", "open", "mkdir", "rename", "link", "unlink", "listdir"),
        "materialization": ("lstat", "stat", "open", "publish", "unlink"),
    }

    def __init__(self, observer: WriteObserver, faults: FaultInjector) -> None:
        self.observer = observer
        self.faults = faults
        self.cross_volume: Callable[[os.stat_result], bool] | None = None
        self.cross_volume_calls = 0

    def install(self, patches: PatchSet) -> None:
        for seam, module in (("execution", execution_fs), ("materialization", materialization_atomic)):
            original = module._FS
            replacements = {}
            for op in self._PATH_OPS[seam]:
                replacements[op] = self._wrap(seam, op, getattr(original, op))
            if seam == "execution":
                replacements["device_of"] = self._device_of(original.device_of)
            patches.setattr(module, "_FS", dataclasses.replace(original, **replacements))

    def _wrap(self, seam: str, op: str, real):
        observed = op in self._OBSERVED[seam]

        def wrapped(*args, **kwargs):
            paths = [a for a in args if isinstance(a, str)]
            exc = self.faults.match(seam, op, paths)
            if observed:
                self.observer.record(f"{seam}.{op}", paths)
            elif op == "open" and len(args) > 1 and isinstance(args[1], int) and args[1] & _WRITE_MODE_FLAGS:
                self.observer.record(f"{seam}.open(write)", paths)
            if exc is not None:
                raise exc
            return real(*args, **kwargs)

        return wrapped

    def _device_of(self, real):
        def device_of(st):
            predicate = self.cross_volume
            if predicate is not None and stat.S_ISREG(st.st_mode) and predicate(st):
                self.cross_volume_calls += 1
                return real(st) + 7
            return real(st)

        return device_of


# --------------------------------------------------------------------------- concurrency gates and probes


class HoldGate:
    """Hold every caller until ``target`` are in flight at once, then release all of them for good (SI-06 gating)."""

    def __init__(self, target: int) -> None:
        self.target = target
        self._event: asyncio.Event | None = None

    async def pass_through(self, active_now: int) -> None:
        if self._event is None:
            self._event = asyncio.Event()
        if active_now >= self.target:
            self._event.set()
        await asyncio.wait_for(self._event.wait(), WAIT)


class AsyncReverse:
    """Hold the first ``n`` callers; once ``n`` have arrived release them one at a time in REVERSE arrival order, each
    only after its predecessor reported ``done`` (S-19: reverses the completion order of an asyncio stage)."""

    def __init__(self, n: int) -> None:
        self.n = n
        self.arrival: list[str] = []
        self.release: list[str] = []
        self._events: dict[str, asyncio.Event] = {}
        self._pending: list[str] = []

    async def enter(self, key: str) -> bool:
        if len(self.arrival) >= self.n:
            return False
        event = asyncio.Event()
        self._events[key] = event
        self.arrival.append(key)
        self._pending.append(key)
        if len(self.arrival) == self.n:
            self._release_next()
        await asyncio.wait_for(event.wait(), WAIT)
        return True

    def done(self, key: str) -> None:
        if key in self._events:
            self._release_next()

    def _release_next(self) -> None:
        if self._pending:
            key = self._pending.pop()
            self.release.append(key)
            self._events[key].set()


class ThreadReverse:
    """The same reversal for the worker threads of the execution stage."""

    def __init__(self, n: int) -> None:
        self.n = n
        self.cond = threading.Condition()
        self.arrival: list[int] = []
        self.release: list[int] = []
        self._pending: list[int] = []
        self._open: set[int] = set()

    def enter(self, key: int) -> bool:
        with self.cond:
            if len(self.arrival) >= self.n:
                return False
            self.arrival.append(key)
            self._pending.append(key)
            if len(self.arrival) == self.n:
                self._release_next()
            if not self.cond.wait_for(lambda: key in self._open, WAIT):
                _violation("reverse gate: a worker was never released")
            return True

    def done(self, key: int) -> None:
        with self.cond:
            if key in self.arrival:
                self._release_next()

    def _release_next(self) -> None:
        if self._pending:
            key = self._pending.pop()
            self.release.append(key)
            self._open.add(key)
            self.cond.notify_all()


class ScriptedSources:
    """Three scripted ``SourceAdapter`` classes (real ``SourceAdapter`` subclasses) driven by the ``Film`` definitions.

    Observation: fetch counts per ``(source, number)``, the log of fetches, and the number of distinct items with at
    least one fetch in flight (the engine-level in-flight items, SI-06). Gates: ``hold`` (peak) and ``reverse`` (S-19).
    """

    def __init__(self, films: Iterable[Film], *, hold: int = 0, reverse: int = 0) -> None:
        self._films = {film.number: film for film in films if film.number is not None}
        self.fetch_counts: Counter = Counter()
        self.log: list[tuple[str, str]] = []
        self.numbers_called: Counter = Counter()
        self.unscripted: list[str] = []
        self._active: Counter = Counter()
        self.peak_items = 0
        self.completion_order: list[str] = []
        self._hold = HoldGate(hold) if hold else None
        self.reverse = AsyncReverse(reverse) if reverse else None
        self.registry = SourceRegistry()
        for source_id in SOURCE_IDS:
            self.registry.register(source_id, scripted_adapter_class(source_id, self._script_for(source_id)))

    def _script_for(self, source_id: str):
        async def script(number, client):
            return await self._fetch(source_id, number)

        return script

    async def _fetch(self, source_id: str, number: str):
        film = self._films.get(number)
        if film is None:
            self.unscripted.append(number)
            return scripted_failed(source_id, SourceStatus.NOT_FOUND, detail=FAIL_DETAIL)
        call = self.fetch_counts[(source_id, number)]
        self.fetch_counts[(source_id, number)] += 1
        self.log.append((source_id, number))
        self.numbers_called[number] += 1
        outcome = film.outcomes_at(call)[source_id]
        self._active[number] += 1
        self.peak_items = max(self.peak_items, sum(1 for count in self._active.values() if count > 0))
        gated = False
        try:
            await asyncio.sleep(0)
            if self._hold is not None:
                await self._hold.pass_through(sum(1 for count in self._active.values() if count > 0))
            if self.reverse is not None and source_id == SOURCE_IDS[-1]:
                gated = await self.reverse.enter(number)
            if outcome.status == "SUCCESS":
                return scripted_ok(source_id, number, **dict(outcome.fields))
            return scripted_failed(source_id, SourceStatus[outcome.status], detail=FAIL_DETAIL)
        finally:
            self._active[number] -= 1
            if source_id == SOURCE_IDS[-1]:
                self.completion_order.append(number)
            if gated:
                self.reverse.done(number)

    def engine(self, retry_policy: RetryPolicy | None = None) -> MultiSourceEngine:
        policy = retry_policy or RetryPolicy(initial_backoff_seconds=0.0, max_backoff_seconds=0.0)
        config = AggregationConfig(sources=tuple(SourceConfig(source_id) for source_id in SOURCE_IDS),
                                   retry_policy=policy)
        return MultiSourceEngine(config, self.registry, FakeHttpClient())


class ImageRoutes:
    """The ``httpx.MockTransport`` handler: a candidate URL's ``-<behavior>`` token selects the response."""

    def __init__(self, *, hold: int = 0, reverse: int = 0) -> None:
        self.requests: list[str] = []
        self.active = 0
        self.peak = 0
        self._hold = HoldGate(hold) if hold else None
        self.reverse = AsyncReverse(reverse) if reverse else None

    async def handler(self, request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        self.requests.append(url)
        self.active += 1
        self.peak = max(self.peak, self.active)
        gated = False
        try:
            await asyncio.sleep(0)
            if self._hold is not None:
                await self._hold.pass_through(self.active)
            if self.reverse is not None and "/poster0-" in url:
                gated = await self.reverse.enter(url)
            behavior = image_behavior(url)
            if behavior == "ok":
                return httpx.Response(200, headers={"content-type": "image/jpeg"}, content=image_payload(url))
            if behavior == "404":
                return httpx.Response(404, headers={"content-type": "text/html"}, content=b"")
            if behavior == "redir":
                return httpx.Response(302, headers={"location": _corpus.PRIVATE_REDIRECT_TARGET}, content=b"")
            if behavior == "png":
                return httpx.Response(200, headers={"content-type": "image/png"}, content=image_payload(url))
            if behavior == "bad":
                return httpx.Response(200, headers={"content-type": "image/jpeg"}, content=b"not a jpeg at all")
            raise AssertionError(f"unrouted image behavior {behavior!r}")
        finally:
            self.active -= 1
            if gated:
                self.reverse.done(url)


class ExecProbe:
    """Call-through wrapper of ``orchestration.execute.execute_filesystem`` (an authorized seam): counts calls, observes
    the worker concurrency and optionally holds / reverses the workers. ``after`` hooks run after the n-th call."""

    def __init__(self, real, *, hold: int = 0, reverse: int = 0) -> None:
        self.real = real
        self.cond = threading.Condition()
        self.active = 0
        self.peak = 0
        self.calls = 0
        self.target = hold
        self.gathered = False
        self.reverse = ThreadReverse(reverse) if reverse else None
        self.after: dict[int, Callable[[], None]] = {}
        self.seen_paths: list[str] = []

    def __call__(self, preflight):
        with self.cond:
            self.calls += 1
            number = self.calls
            self.active += 1
            self.peak = max(self.peak, self.active)
            self.seen_paths.append(preflight.plan.source_path)
            if self.target:
                if self.active >= self.target:
                    self.gathered = True
                    self.cond.notify_all()
                elif not self.gathered and not self.cond.wait_for(lambda: self.gathered, WAIT):
                    _violation("execution probe: the worker budget was never reached")
        gated = self.reverse.enter(number) if self.reverse is not None else False
        try:
            return self.real(preflight)
        finally:
            with self.cond:
                self.active -= 1
            if gated:
                self.reverse.done(number)
            hook = self.after.get(number)
            if hook is not None:
                hook()


# --------------------------------------------------------------------------- the chain


class Chain:
    """One disposable acceptance tree plus the real chain over it.

    ``with Chain(tmp_path, films, ...) as chain:`` creates ``<tmp_path>/downloads`` (the dirty download tree, one synthetic
    file per film) and ``<tmp_path>/library`` (empty library root), builds the real engine / image client / orchestrator,
    installs the observers (write observer, fault layer, socket trap, execution probe) and removes them on exit.

    ``preview`` / ``preview_retry`` check SI-21 (before / after tree snapshots equal); ``execute`` runs the shared gates
    after every round (SI-01, SI-14, SI-15, SI-19, SI-20, SI-22). Everything else is asserted by the scenario tests.
    """

    def __init__(self, tmp_path, films: Iterable[Film], *, config: OrchestrationConfig | None = None,
                 downloads_name: str = "downloads", library_name: str = "library", hold_items: int = 0,
                 hold_images: int = 0, hold_exec: int = 0, reverse: bool = False, create_tree: bool = True,
                 instrument: bool = True) -> None:
        self.films = list(films)
        self.sandbox = Sandbox(tmp_path)
        self.root = self.sandbox.root
        self.downloads = self.sandbox.register_root(os.path.join(self.root, downloads_name))
        self.library = self.sandbox.register_root(os.path.join(self.root, library_name))
        self.config = config or OrchestrationConfig()
        self.observer = WriteObserver()
        self.faults = FaultInjector()
        self.trap = SocketTrap()
        self.fs = FsLayer(self.observer, self.faults)
        self.patches = PatchSet()
        self.original: dict[str, str] = {}  # source path -> sha256 of the synthetic media
        self.final_paths: dict[str, set[str]] = {}
        self.target_directories: set[str] = set()
        self.reported_temporaries: list[tuple[str, str]] = []
        self.preexisting_temporaries: set[str] = set()
        self.preview_snapshots: list[tuple[dict, dict]] = []
        self.rounds: list[tuple[str, object]] = []
        reverse_items = self.config.metadata.max_in_flight_items if reverse else 0
        self.sources = ScriptedSources(self.films, hold=hold_items, reverse=reverse_items)
        self.routes = ImageRoutes(hold=hold_images, reverse=self.config.image_in_flight_items if reverse else 0)
        self.exec_hold, self.exec_reverse = hold_exec, (self.config.filesystem_workers if reverse else 0)
        self.loop = asyncio.new_event_loop()  # created before the socket trap (the loop owns a loopback socket pair)
        self.client = HttpxImageClient(transport=httpx.MockTransport(self.routes.handler))
        self.engine = self.sources.engine()
        self.exec_probe: ExecProbe | None = None
        self._closed = False
        if create_tree:
            self.write_tree()
        else:
            os.makedirs(self.downloads, exist_ok=True)
            os.makedirs(self.library, exist_ok=True)
        self.orchestrator = BatchOrchestrator(self.engine, self.client, self.sandbox.require(self.library, "library root"),
                                              config=self.config)
        self.instrumented = instrument
        if instrument:
            self._install()

    # ---- lifecycle

    def __enter__(self) -> "Chain":
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            self.loop.run_until_complete(self.client.aclose())
        finally:
            self.loop.close()
            self.patches.restore()

    def _install(self) -> None:
        self.trap.install(self.patches)
        self.fs.install(self.patches)
        real_exec = orchestration_execute.execute_filesystem
        self.exec_probe = ExecProbe(real_exec, hold=self.exec_hold, reverse=self.exec_reverse)
        self.patches.setattr(orchestration_execute, "execute_filesystem", self.exec_probe)
        self.patches.setattr(builtins, "open", self.observer.wrap_open(builtins.open))
        self.patches.setattr(io, "open", builtins.open)
        self.patches.setattr(os, "open", self.observer.wrap_os_open(os.open))
        for name in _OS_MUTATORS:
            if hasattr(os, name):
                self.patches.setattr(os, name, self.observer.wrap_os_mutator(name, getattr(os, name)))

    # ---- the disposable tree

    def source_path(self, film: Film) -> str:
        return os.path.join(self.downloads, *film.relative_source.split("/"))

    def write_tree(self) -> None:
        os.makedirs(self.library, exist_ok=True)
        for film in self.films:
            path = self.source_path(film)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "wb") as handle:
                handle.write(film.content)
            self.original[path] = sha256_file(path)

    def force_cross_volume(self, films: Iterable[Film] | None = None) -> None:
        """``_FS.device_of`` seam: the named films' source files (all when ``None``) report another device than the
        directories, so preflight predicts ``CROSS_VOLUME`` on this single-disk tree (mocked, never native evidence).
        Call before the preview."""
        if films is None:
            self.fs.cross_volume = lambda st: True
            return
        inodes = {os.lstat(self.source_path(film)).st_ino for film in films}
        self.fs.cross_volume = lambda st: st.st_ino in inodes

    @contextmanager
    def user_action(self):
        """The test acts as the user (create / delete files in the disposable tree): not observed, not a violation."""
        with self.observer.paused():
            yield

    def user_write(self, path: str, content: bytes) -> None:
        with self.user_action():
            self.sandbox.require(path, "user write")
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "wb") as handle:
                handle.write(content)

    def user_mkdir(self, path: str) -> None:
        with self.user_action():
            self.sandbox.require(path, "user mkdir")
            os.makedirs(path, exist_ok=True)

    def user_remove_tree(self, path: str) -> None:
        with self.user_action():
            self.sandbox.require(path, "user remove")
            for dirpath, dirnames, filenames in os.walk(path, topdown=False):
                for name in filenames:
                    os.remove(os.path.join(dirpath, name))
                for name in dirnames:
                    os.rmdir(os.path.join(dirpath, name))
            os.rmdir(path)

    def snapshot(self) -> dict:
        return snapshot_tree(self.root)

    # ---- running the chain

    def run(self, coroutine):
        return self.loop.run_until_complete(coroutine)

    def discover(self):
        self.sandbox.require(self.downloads, "discovery root")
        result = discover_media(self.downloads)
        if result.issues:
            _violation(f"discovery reported {len(result.issues)} issue(s) on the synthetic tree")
        return result.items

    def _after_model(self, model) -> None:
        if self.sources.unscripted:
            _violation(f"the engine asked for unscripted numbers: {sorted(set(self.sources.unscripted))[:3]}")
        gate_no_network(self.trap.hits)

    def preview(self, items=None) -> BatchPreview:
        items = self.discover() if items is None else items
        before = self.snapshot()
        preview = self.run(self.orchestrator.preview(items))
        after = self.snapshot()
        self.preview_snapshots.append((before, after))
        gate_snapshots_equal(before, after, "SI-21 preview")  # SI-21
        self._register(preview)
        self.rounds.append(("preview", preview))
        self._after_model(preview)
        return preview

    def preview_retry(self, previous, scope=None) -> BatchPreview:
        before = self.snapshot()
        preview = self.run(self.orchestrator.preview_retry(previous, scope=scope))
        after = self.snapshot()
        self.preview_snapshots.append((before, after))
        gate_snapshots_equal(before, after, "SI-21 preview_retry")  # SI-21
        self._register(preview)
        self.rounds.append(("preview_retry", preview))
        self._after_model(preview)
        return preview

    def _register(self, model) -> None:
        """Remember every source / target path any item names (the allowed sets of SI-15 and SI-01)."""
        for item in model.items:
            source = item.source_path
            final = item.final_media_path
            self.final_paths.setdefault(source, set())
            if final is not None:
                self.final_paths[source].add(final)
            if item.target_directory is not None:
                self.target_directories.add(item.target_directory)

    def execute(self, preview: BatchPreview, *, selection=None, cancel=None, gates: bool = True) -> BatchExecutionResult:
        self.observer.take()  # nothing before this round counts
        self.faults.armed = True
        try:
            result = self.orchestrator.execute(preview, selection=selection, cancel=cancel)
        finally:
            self.faults.armed = False
        self.rounds.append(("execute", result))
        self._register(result)
        for item in result.items:
            execution = item.execution
            if execution is not None:
                self.reported_temporaries.extend(
                    (self._temporary_directory(item, leftover.directory_role.value), leftover.name)
                    for leftover in execution.leftover_temporaries)
        if gates:
            self.round_gates(result)
        return result

    def _temporary_directory(self, item, role: str) -> str:
        target = item.target_directory
        return target if role == "target_directory" else os.path.join(target, "extrafanart")

    def merge(self, previous, retry) -> BatchExecutionResult:
        merged = merge_retry(previous, retry)
        self.rounds.append(("merge", merged))
        self._register(merged)
        gate_result_accounting(merged)
        gate_indices_exactly_once(merged, merged.batch_size)
        return merged

    def round_gates(self, result: BatchExecutionResult) -> None:
        """Shared gates of contract section 7.3, after every execution round."""
        for source, original in self.original.items():
            finals = sorted(self.final_paths.get(source, ()))
            if not finals:
                gate_source_not_lost(source, None, original)
            for final in finals or ():
                gate_source_not_lost(source, final, original)
        gate_no_unreported_temporaries(self.root, self.reported_temporaries, self.preexisting_temporaries)
        records = self.observer.take()
        allowed_files = set(self.original) | {path for paths in self.final_paths.values() for path in paths}
        gate_write_paths_contained(records, sandbox_root=self.root,
                                   allowed_directories=self.target_directories,
                                   allowed_files=allowed_files)
        gate_result_accounting(result)
        if result.is_complete:
            gate_indices_exactly_once(result, result.batch_size)
        gate_no_network(self.trap.hits)


# --------------------------------------------------------------------------- projections / diagnostics


def _issue(issue):
    return None if issue is None else (issue.stage.value, issue.reason.value, issue.error_type,
                                       None if issue.detail is None else (type(issue.detail).__name__, issue.detail.value))


def result_projection(chain_root: str, model) -> tuple:
    """A tree-independent projection of a ``BatchPreview`` / ``BatchExecutionResult`` for the determinism gates: every
    field that reflects behaviour (index, number, state, issue, warnings, failures, effects, retry kind), paths made
    relative to the acceptance root; ids, seals and lineage tokens (random by design) are excluded."""
    def rel(path):
        return None if path is None else os.path.relpath(path, chain_root).replace(os.sep, "/")

    rows = []
    for item in model.items:
        row = [item.index, item.generation, item.canonical_number, rel(item.source_path), rel(item.final_media_path),
               _issue(item.issue), tuple(w.value for w in item.warnings),
               tuple((f.role.name, f.candidate_index, f.kind.value, f.http_status) for f in item.image_failures),
               item.conflict_with]
        if hasattr(item, "disposition"):
            execution = item.execution
            row += [item.disposition.value, item.retry_kind.value, item.preview_state.value,
                    None if execution is None else (
                        execution.status.value, None if execution.transfer_mode is None else execution.transfer_mode.value,
                        tuple((e.kind.value, rel(e.path), e.sha256, e.size) for e in execution.completed_effects),
                        tuple((t.directory_role.value, t.name) for t in execution.leftover_temporaries),
                        None if execution.failure is None else (execution.failure.step.value, execution.failure.kind.value))]
        else:
            row += [item.state.value, None if item.retry_origin is None else item.retry_origin.value]
        rows.append(tuple(row))
    return (type(model).__name__, model.generation, model.batch_size, tuple(rows))


def diagnostics_bytes(model, path_policy: PathPolicy = PathPolicy.NONE) -> bytes:
    """Build + render the diagnostics of a preview / result through the public P4-C9 API."""
    if isinstance(model, BatchPreview):
        built = build_preview_diagnostics(model, path_policy=path_policy)
    else:
        built = build_execution_diagnostics(model, path_policy=path_policy)
    return render_diagnostics_json(built)
