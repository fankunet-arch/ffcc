"""MultiSourceEngine: canonical number -> configured sources -> AggregationResult.

The engine only *wires* the three separately testable pieces together:

1. ``AggregationConfig`` (validated up front, before any network request),
2. ``execute_sources``  (bounded fan-out, deadlines, isolation -- ``execution.py``),
3. ``merge_source_results`` (pure field-level merge -- ``merge.py``).

It owns no HTTP transport: the caller passes **one** shared
:class:`SourceHttpClient`, so every source runs through the same client
lifecycle (Phase 2 requirement) and the caller decides when to close it.
"""

from __future__ import annotations

import time

from fc2_metadata_core.aggregation.config import AggregationConfig
from fc2_metadata_core.aggregation.execution import SourceTarget, execute_sources
from fc2_metadata_core.aggregation.merge import merge_source_results
from fc2_metadata_core.aggregation.models import AggregationResult
from fc2_metadata_core.aggregation.policy import AggregationConfigError, AggregationPolicy
from fc2_metadata_core.http.client import SourceHttpClient
from fc2_metadata_core.sources.base import require_canonical_number
from fc2_metadata_core.sources.registry import SourceRegistry

__all__ = ["MultiSourceEngine"]


class MultiSourceEngine:
    """Aggregate one canonical FC2 number across the configured sources.

    Construction validates everything that can be validated without a network:
    every enabled ``source_id`` must be registered (:class:`AggregationConfigError`
    otherwise -- listing *all* unknown ids), and every adapter is built through
    the hardened ``registry.create`` boundary (so a misbehaving factory raises a
    ``SourceRegistryError`` subclass here, not mid-lookup). Adapters are
    stateless and reused across lookups.
    """

    def __init__(self, config: AggregationConfig, registry: SourceRegistry, client: SourceHttpClient) -> None:
        if not isinstance(config, AggregationConfig):
            raise AggregationConfigError("config must be an AggregationConfig")
        if not isinstance(registry, SourceRegistry):
            raise AggregationConfigError("registry must be a SourceRegistry")
        if not callable(getattr(client, "get", None)):
            raise AggregationConfigError("client must provide an async get(url, ...) (SourceHttpClient)")

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
            targets.append(SourceTarget(source, registry.create(source.source_id, **kwargs)))

        self._config = config
        self._policy: AggregationPolicy = config.policy()
        self._targets = tuple(targets)
        self._client = client

    @property
    def config(self) -> AggregationConfig:
        return self._config

    @property
    def policy(self) -> AggregationPolicy:
        return self._policy

    async def aggregate(self, number: str) -> AggregationResult:
        """Look ``number`` up on every enabled source and merge the answers.

        Raises ``InvalidCanonicalNumberInputError`` for a non-canonical number
        (a caller bug, before any request). Never raises for a source failing,
        timing out, misbehaving or returning garbage -- those are per-source
        results. A cancellation of the awaiting task propagates unchanged.
        """
        require_canonical_number(number)
        started = time.monotonic()
        results = await execute_sources(
            number, self._targets, self._client, max_concurrency=self._config.max_concurrency
        )
        return merge_source_results(
            number,
            results,
            self._policy,
            disabled_source_ids=self._config.disabled_source_ids,
            elapsed_ms=max(0.0, (time.monotonic() - started) * 1000.0),
        )
