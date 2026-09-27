"""``BatchOrchestrator``: construction checks, the busy guard and ``preview`` (P4-C8 contract sections 7.2, 7.3).

S2 provides the constructor, the read-only properties and ``async preview(items)``; ``execute`` (S3) and
``preview_retry`` (S4) are added by later batches. Construction validates only and performs no network or
filesystem access. One ``BatchScheduler(engine, config.metadata)`` is created here and reused for the
orchestrator's lifetime; the engine and the image client belong to the caller (never built or closed here).

Busy-first (section 7.3): one flag guarded by a ``threading.Lock`` is claimed as the very first step of every
operation, before any argument is looked at; a rejected call never releases the holder's claim, and the claim
is released in ``finally`` on every exit path (return, error, resource limit, cancellation, fatal).
"""

from __future__ import annotations

import threading

from fc2_metadata_core.batch import BatchConfigError, BatchScheduler
from fc2_organizer.images import ImageAcquisitionPolicy
from fc2_organizer.orchestration.errors import OrchestrationBusyError, OrchestrationConfigError
from fc2_organizer.orchestration.models import MAX_ITEM_IMAGE_BYTES, BatchPreview, OrchestrationConfig
from fc2_organizer.orchestration.preview import build_preview
from fc2_organizer.planning import OutputPolicy

__all__ = ["BatchOrchestrator"]


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
        if image_client is None or not callable(getattr(image_client, "get", None)):
            raise OrchestrationConfigError("image_client must provide a callable get (ImageHttpClient)")
        scheduler = None
        try:
            scheduler = BatchScheduler(engine, config.metadata)
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
