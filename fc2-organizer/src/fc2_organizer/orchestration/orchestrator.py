"""``BatchOrchestrator``: construction checks, the busy guard and ``preview`` (P4-C8 contract sections 7.2, 7.3).

S2 provides the constructor, the read-only properties and ``async preview(items)``; S3 adds the
synchronous ``execute(preview, *, selection=None, cancel=None)`` (delegated to ``execute.py``); S4 adds
``async preview_retry(previous, *, scope=None)`` (delegated to ``retry.py``). Construction validates only
and performs no network or filesystem access. One ``BatchScheduler(engine, config.metadata)`` is created
here and reused for the orchestrator's lifetime; the engine and the image client belong to the caller (never
built or closed here).

Constructor shape checks never run caller code (S2-R1, finding P4-C8-S2-R-01): ``engine.aggregate`` and
``image_client.get`` are resolved *statically* (the class namespaces along the C-level MRO and the instance
``__dict__`` read through the standard getset descriptor only; no ``getattr`` / ``hasattr``, so no property,
descriptor ``__get__``, ``__getattr__`` or ``__getattribute__`` hook runs) and classified statically: a
function / method, ``staticmethod`` / ``classmethod``, a builtin, an exact ``functools.partial`` or a
callable object (its type's static ``__call__``) is accepted. ``aggregate`` must be async by the Phase 3
boundary's own rule, ``inspect.iscoroutinefunction``, evaluated only on a probe built from exact standard
objects (S2-R2 / S2-R3, findings P4-C8-S2-R1-01, R2-01, R2-02). A property, a custom descriptor or a ``__getattr__``-only attribute cannot be
classified without running it and is an ``OrchestrationConfigError``. The caller's engine is then wrapped in a
private adapter, so the Phase 3 ``BatchScheduler`` inspects P4-C8's own ``aggregate`` and the caller's code
first runs inside ``scheduler.run`` (the metadata stage); ``image_client.get`` first runs inside
``acquire_images`` (the image stage).

Busy-first (section 7.3): one flag guarded by a ``threading.Lock`` is claimed as the very first step of every
operation, before any argument is looked at; a rejected call never releases the holder's claim, and the claim
is released in ``finally`` on every exit path (return, error, resource limit, cancellation, fatal).
"""

from __future__ import annotations

import functools
import inspect
import threading

from fc2_metadata_core.batch import BatchConfigError, BatchScheduler
from fc2_organizer.images import ImageAcquisitionPolicy
from fc2_organizer.orchestration.errors import OrchestrationBusyError, OrchestrationConfigError
from fc2_organizer.orchestration.execute import execute_preview
from fc2_organizer.orchestration.models import (
    MAX_ITEM_IMAGE_BYTES,
    BatchExecutionResult,
    BatchPreview,
    OrchestrationConfig,
)
from fc2_organizer.orchestration.preview import build_preview
from fc2_organizer.orchestration.retry import build_retry_preview
from fc2_organizer.planning import OutputPolicy

__all__ = ["BatchOrchestrator"]

_MISSING = object()
_TYPE_MRO = type.__dict__["__mro__"]  # C-level getters: never consult a metaclass attribute
_TYPE_NAMESPACE = type.__dict__["__dict__"]
_GETSET_DESCRIPTOR = type(_TYPE_NAMESPACE)
_CYCLE = object()  # a wrapper chain that returns to an object already visited: not a finite callable


def _plain_function() -> None:
    return None


class _BoundProbe:
    def method(self) -> None:
        return None


_FUNCTION = type(_plain_function)
_BOUND_METHOD = type(_BoundProbe().method)
_BUILTIN_FUNCTION = type(len)  # also the type of a bound builtin method (e.g. ``[].append``)
_SLOT_WRAPPER = type(_TYPE_NAMESPACE.__get__(object, type)["__init__"])  # C-level ``__call__`` of builtin types
_PARTIAL = functools.partial
_PARTIAL_FUNC = _TYPE_NAMESPACE.__get__(_PARTIAL, type)["func"]  # the C-level member of exact partials


def _class_attribute(cls: type, name: str) -> object:
    for klass in _TYPE_MRO.__get__(cls, type):
        namespace = _TYPE_NAMESPACE.__get__(klass, type)
        if name in namespace:
            return namespace[name]
    return _MISSING


def _has_class_attribute(cls: type, name: str) -> bool:
    return _class_attribute(cls, name) is not _MISSING


def _static_attribute(obj: object, name: str) -> tuple[object, bool]:
    """``obj.<name>`` resolved without running any caller code -- the non-executing equivalent of
    ``inspect.getattr_static`` (contract section 6 allows no ``inspect`` import). Returns ``(raw, bound)``:
    ``raw`` is the stored object (never a ``__get__`` result), ``bound`` tells whether normal attribute access
    would bind it (it came from the class) or not (the instance ``__dict__``). ``(_MISSING, False)`` when the
    attribute exists only through a hook (``__getattr__`` / ``__getattribute__``) or the instance dict itself
    sits behind an untrusted hook. Precedence follows normal lookup: class data descriptor, instance
    ``__dict__``, class attribute."""
    cls = type(obj)
    class_value = _class_attribute(cls, name)
    if class_value is not _MISSING and (_has_class_attribute(type(class_value), "__set__")
                                        or _has_class_attribute(type(class_value), "__delete__")):
        return class_value, True  # a data descriptor (e.g. a property) always wins
    dict_slot = _class_attribute(cls, "__dict__")
    if dict_slot is not _MISSING:
        owner = dict_slot.__objclass__ if type(dict_slot) is _GETSET_DESCRIPTOR else None
        if owner is None or not any(klass is owner for klass in _TYPE_MRO.__get__(cls, type)):
            return _MISSING, False  # a hand-made / foreign ``__dict__`` hook: not inspected, not trusted
        instance_dict = dict_slot.__get__(obj, cls)  # the C-level instance dict getter
        if type(instance_dict) is dict and name in instance_dict:
            return instance_dict[name], False
    return class_value, True


def _is_trusted_terminal(value: object) -> bool:
    """An exact plain function, or an exact bound method of one: objects the standard library can inspect
    without running any caller code."""
    return type(value) is _FUNCTION or (type(value) is _BOUND_METHOD and type(value.__func__) is _FUNCTION)


def _partial_terminal(value: object) -> object:
    """Follow a chain of exact ``functools.partial`` objects (through the C-level ``func`` member only) to its
    first non-partial object, however long the (finite) chain is. Returns ``_CYCLE`` when the chain returns
    to a partial already visited (identity only: no caller ``__eq__`` / ``__hash__`` runs)."""
    visited: set[int] = set()
    current = value
    while type(current) is _PARTIAL:
        if id(current) in visited:
            return _CYCLE
        visited.add(id(current))
        current = _PARTIAL_FUNC.__get__(current, _PARTIAL)
    return current


def _callable_shape(raw: object, bound: bool) -> tuple[bool, object | None] | None:
    """Static callable-shape classification. ``None``: not provably callable without running caller code.
    Otherwise ``(True, probe)``: ``probe`` is an object built only from exact standard types (function,
    bound method, finite ``functools.partial`` chain ending in one of those) whose async-ness the standard
    library decides (``_is_async``), or ``None`` when the callable is not provably async (builtin, C-level
    ``__call__``, a partial of a non-standard object).

    Shapes: a function (a method when ``bound``), a bound method, ``staticmethod`` / ``classmethod`` (their
    ``__func__``), a builtin, an exact ``functools.partial`` chain of any finite length, and a callable
    object via its type's static ``__call__``. Any other descriptor (``property``, a custom ``__get__``) and
    any wrapper cycle is ``None``. Wrapper layers are unwrapped iteratively with an identity ``visited``
    set -- no depth cap. Never calls, binds or ``getattr``s the candidate.
    """
    visited: set[int] = set()
    current, current_bound = raw, bound
    while True:
        if current is _MISSING or id(current) in visited:
            return None
        visited.add(id(current))
        kind = type(current)
        if kind is _FUNCTION:
            return True, current
        if kind is _BOUND_METHOD:
            function = current.__func__
            if type(function) is _FUNCTION:
                return True, current
            current, current_bound = function, False
            continue
        if kind is staticmethod:
            current, current_bound = current.__func__, False
            continue
        if kind is classmethod:
            if not current_bound:
                return None  # a classmethod object outside a class namespace is not callable
            current, current_bound = current.__func__, False
            continue
        if kind is _BUILTIN_FUNCTION:
            return True, None
        if kind is _PARTIAL:
            terminal = _partial_terminal(current)
            if terminal is _CYCLE:
                return None
            return True, (current if _is_trusted_terminal(terminal) else None)
        if current_bound and _has_class_attribute(kind, "__get__"):
            return None  # a custom (non-data) descriptor: only its ``__get__`` could tell, and it is not run
        call = _class_attribute(kind, "__call__")
        if call is _MISSING:
            return None
        call_kind = type(call)
        if call_kind is _FUNCTION:
            return True, call
        if call_kind is staticmethod or call_kind is classmethod:
            current, current_bound = call.__func__, False
            continue
        if call_kind is _SLOT_WRAPPER:
            return True, None  # a builtin type's C-level ``__call__``
        return None


def _is_async(probe: object | None) -> bool:
    """The Phase 3 boundary's own rule (``inspect.iscoroutinefunction``), applied only to a probe made of
    exact standard objects, so the standard library runs no caller code while deciding."""
    return probe is not None and inspect.iscoroutinefunction(probe) is True


def _shape_of(obj: object, name: str) -> tuple[bool, object | None] | None:
    raw, bound = _static_attribute(obj, name)
    return _callable_shape(raw, bound)


class _EngineAdapter:
    """P4-C8's own ``async aggregate(number)`` handed to the Phase 3 scheduler: the scheduler's construction
    checks inspect this method, never the caller's. Awaiting the caller's engine only in ``aggregate`` keeps
    every metadata semantic (results, exceptions, cancellation, concurrency) the scheduler's."""

    __slots__ = ("_engine",)

    def __init__(self, engine: object) -> None:
        self._engine = engine

    async def aggregate(self, number: str):
        return await self._engine.aggregate(number)


class BatchOrchestrator:
    """Batch preview (S2) over one Phase 3 engine and one P4-C5 image client."""

    __slots__ = ("_scheduler", "_image_client", "_library_root", "_output_policy", "_image_policy", "_config",
                 "_lock", "_busy")

    def __init__(self, engine, image_client, library_root, *, output_policy=None, image_policy=None,
                 config=None) -> None:
        if config is None:
            config = OrchestrationConfig()
        elif type(config) is not OrchestrationConfig:
            raise OrchestrationConfigError("config must be None or an exact OrchestrationConfig")
        if type(library_root) is not str or not library_root:
            raise OrchestrationConfigError("library_root must be a non-empty exact str")
        if output_policy is None:
            output_policy = OutputPolicy()
        elif type(output_policy) is not OutputPolicy:
            raise OrchestrationConfigError("output_policy must be None or an exact OutputPolicy")
        if image_policy is None:
            image_policy = ImageAcquisitionPolicy()
        elif type(image_policy) is not ImageAcquisitionPolicy:
            raise OrchestrationConfigError("image_policy must be None or an exact ImageAcquisitionPolicy")
        if image_policy.max_total_bytes > MAX_ITEM_IMAGE_BYTES:
            raise OrchestrationConfigError("image_policy.max_total_bytes must be <= MAX_ITEM_IMAGE_BYTES")
        if _shape_of(image_client, "get") is None:
            raise OrchestrationConfigError("image_client must provide a callable get (ImageHttpClient)")
        aggregate = _shape_of(engine, "aggregate")
        if aggregate is None or not _is_async(aggregate[1]):
            raise OrchestrationConfigError("engine must provide an async aggregate(number) (AggregationEngine)")
        scheduler = None
        try:
            scheduler = BatchScheduler(_EngineAdapter(engine), config.metadata)
        except BatchConfigError:
            pass  # translated below, outside the handler (never chained)
        if scheduler is None:
            raise OrchestrationConfigError("engine must provide an async aggregate(number) (AggregationEngine)")
        self._scheduler = scheduler
        self._image_client = image_client
        self._library_root = library_root
        self._output_policy = output_policy
        self._image_policy = image_policy
        self._config = config
        self._lock = threading.Lock()
        self._busy = False

    # ---- read-only properties

    @property
    def config(self) -> OrchestrationConfig:
        return self._config

    @property
    def library_root(self) -> str:
        return self._library_root

    @property
    def output_policy(self) -> OutputPolicy:
        return self._output_policy

    @property
    def image_policy(self) -> ImageAcquisitionPolicy:
        return self._image_policy

    # ---- busy guard (section 7.3)

    def _claim(self) -> None:
        with self._lock:
            busy = self._busy
            self._busy = True
        if busy:
            raise OrchestrationBusyError("this orchestrator already has an active operation")

    def _release(self) -> None:
        with self._lock:
            self._busy = False

    # ---- operations

    async def preview(self, items) -> BatchPreview:
        """Read-only batch preview (contract section 15.1). Zero filesystem mutation."""
        self._claim()
        try:
            return await build_preview(
                items, scheduler=self._scheduler, image_client=self._image_client,
                library_root=self._library_root, output_policy=self._output_policy,
                image_policy=self._image_policy, image_workers=self._config.image_in_flight_items,
                ledger_limit=self._config.max_retained_artifact_bytes)
        finally:
            self._release()

    def execute(self, preview, *, selection=None, cancel=None) -> BatchExecutionResult:
        """Synchronous bounded execution of a preview (contract section 18). Busy-first; the preview is
        consumed once all argument checks pass. In an event loop call it as
        ``await asyncio.to_thread(orchestrator.execute, ...)`` and stop it with a ``CancellationToken``."""
        self._claim()
        try:
            return execute_preview(
                preview, selection=selection, cancel=cancel, library_root=self._library_root,
                output_policy=self._output_policy, image_policy=self._image_policy,
                retention_budget=self._config.max_retained_artifact_bytes,
                workers=self._config.filesystem_workers)
        finally:
            self._release()

    async def preview_retry(self, previous, *, scope=None) -> BatchPreview:
        """Read-only retry preview of a complete result (contract section 25.4). Busy-first; ``previous`` is
        registered as retried only when the retry preview is returned. Zero filesystem mutation."""
        self._claim()
        try:
            return await build_retry_preview(
                previous, scope=scope, scheduler=self._scheduler, image_client=self._image_client,
                library_root=self._library_root, output_policy=self._output_policy,
                image_policy=self._image_policy, image_workers=self._config.image_in_flight_items,
                retention_budget=self._config.max_retained_artifact_bytes)
        finally:
            self._release()
