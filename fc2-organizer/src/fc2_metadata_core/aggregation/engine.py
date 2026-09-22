"""MultiSourceEngine: canonical number -> configured sources -> AggregationResult.

The engine only *wires* the three separately testable pieces together:

1. ``AggregationConfig`` (validated up front, before any network request),
2. ``execute_sources_traced`` (bounded fan-out, per-source total deadline, source-local
   retry, isolation, attempt traces -- ``execution.py``),
3. ``merge_source_results`` (pure field-level merge of the **final** results -- ``merge.py``).

It owns no HTTP transport: the caller passes **one** shared
:class:`SourceHttpClient`, so every source runs through the same client
lifecycle (Phase 2 requirement) and the caller decides when to close it.

Optional shared resource control (Phase 3 C5): pass ``governor=`` (a
:class:`~fc2_metadata_core.resource_control.SourceResourceGovernor`) and every engine -- and every
``BatchScheduler`` on top of them -- built with the **same** governor shares one per-host attempt budget and
one per-source circuit breaker. Without it the engine behaves exactly as before.
"""

from __future__ import annotations

import inspect
import time

from fc2_metadata_core.aggregation.config import AggregationConfig, validate_base_url
from fc2_metadata_core.aggregation.execution import SourceTarget, execute_sources_traced
from fc2_metadata_core.aggregation.merge import merge_source_results
from fc2_metadata_core.aggregation.models import AggregationResult
from fc2_metadata_core.aggregation.policy import AggregationConfigError, AggregationPolicy
from fc2_metadata_core.http.client import SourceHttpClient
from fc2_metadata_core.resource_control import SourceResourceGovernor, host_key_for_base_url
from fc2_metadata_core.sources.base import require_canonical_number
from fc2_metadata_core.sources.registry import SourceRegistry

__all__ = ["MultiSourceEngine", "is_async_get"]


def is_async_get(client: object) -> bool:
    """Is ``client.get`` an ``async`` callable (a coroutine function)?

    Decided **without any request**: an ``async def`` function or bound method, a
    ``functools.partial`` of one, an object whose ``__call__`` is ``async def``, and
    ``unittest.mock.AsyncMock`` all qualify. A plain ``def get`` (even one that
    returns a coroutine) does not: the Phase 2 ``SourceHttpClient`` protocol is
    ``async def get(...)``, and a synchronous ``get`` would only fail later, at
    ``await`` time, turning every source into ``INVALID_RESPONSE``.
    """
    get = getattr(client, "get", None)
    if not callable(get):
        return False
    if inspect.iscoroutinefunction(get):
        return True
    return inspect.iscoroutinefunction(getattr(get, "__call__", None))


class MultiSourceEngine:
    """Aggregate one canonical FC2 number across the configured sources.

    Construction validates everything that can be validated without a network:
    every enabled ``source_id`` must be registered (:class:`AggregationConfigError`
    otherwise -- listing *all* unknown ids), and every adapter is built through
    the hardened ``registry.create`` boundary (so a misbehaving factory raises a
    ``SourceRegistryError`` subclass here, not mid-lookup). Adapters are
    stateless and reused across lookups.
    """

    def __init__(
        self,
        config: AggregationConfig,
        registry: SourceRegistry,
        client: SourceHttpClient,
        *,
        governor: SourceResourceGovernor | None = None,
    ) -> None:
        if governor is not None and not isinstance(governor, SourceResourceGovernor):
            raise AggregationConfigError("governor must be a SourceResourceGovernor or None")
        if not isinstance(config, AggregationConfig):
            raise AggregationConfigError("config must be an AggregationConfig")
        if not isinstance(registry, SourceRegistry):
            raise AggregationConfigError("registry must be a SourceRegistry")
        if not is_async_get(client):
            raise AggregationConfigError(
                "client.get must be an async function (SourceHttpClient protocol: "
                "`async def get(url, *, headers=None, timeout=None)`); a synchronous get is rejected "
                "at construction, before any request"
            )

        enabled = config.enabled_sources
        unknown = [source.source_id for source in enabled if source.source_id not in registry]
        if unknown:
            raise AggregationConfigError(
                f"unknown source_id(s) not registered: {unknown!r} "
                f"(registered: {list(registry.source_ids())!r})"
            )
        targets = []
        for source in enabled:
            kwargs = {"base_url": source.base_url} if source.base_url is not None else {}
            adapter = registry.create(source.source_id, **kwargs)
            host = None
            if governor is not None:
                # Host identity comes from the configured/validated base URL the adapter will use -- never from a
                # response. A malformed default URL fails here, before any request.
                try:
                    host = host_key_for_base_url(validate_base_url(adapter.base_url))
                except (AggregationConfigError, ValueError) as exc:
                    raise AggregationConfigError(
                        f"source {source.source_id!r}: cannot derive a host identity for resource control: {exc}"
                    ) from None
            targets.append(SourceTarget(source, adapter, config.retry_policy_for(source.source_id), host))

        self._config = config
        self._policy: AggregationPolicy = config.policy()
        self._targets = tuple(targets)
        self._client = client
        self._governor = governor

    @property
    def config(self) -> AggregationConfig:
        return self._config

    @property
    def policy(self) -> AggregationPolicy:
        return self._policy

    @property
    def governor(self) -> SourceResourceGovernor | None:
        """The shared resource domain this engine runs in (``None`` = no resource control)."""
        return self._governor

    async def aggregate(self, number: str) -> AggregationResult:
        """Look ``number`` up on every enabled source and merge the answers.

        Raises ``InvalidCanonicalNumberInputError`` for a non-canonical number
        (a caller bug, before any request). Never raises for a source failing,
        timing out, misbehaving or returning garbage -- those are per-source
        results. A cancellation of the awaiting task propagates unchanged.
        """
        require_canonical_number(number)
        started = time.monotonic()
        traces = await execute_sources_traced(
            number,
            self._targets,
            self._client,
            max_concurrency=self._config.max_concurrency,
            governor=self._governor,
        )
        return merge_source_results(
            number,
            [trace.final_result for trace in traces],
            self._policy,
            execution_traces=traces,
            disabled_source_ids=self._config.disabled_source_ids,
            elapsed_ms=max(0.0, (time.monotonic() - started) * 1000.0),
        )
