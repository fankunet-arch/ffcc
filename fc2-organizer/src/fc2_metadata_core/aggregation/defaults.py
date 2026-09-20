"""Default aggregation configuration.

This is the **only** module in the aggregation package that names concrete
providers, and it does so as *data*: an ordered tuple of ``SourceConfig``.
The order is the default field priority (highest first). Nothing in
``merge`` / ``policy`` / ``execution`` / ``engine`` branches on a provider id
(a test scans them), so re-ordering, disabling or adding a source is a
configuration change, never an algorithm change.

Default order rationale (Phase 2 evidence, ``docs/SOURCE_STATUS_MATRIX.md``):
Japanese titles + the richest metadata first, English-translated and
fields-poor sources after.
"""

from __future__ import annotations

from fc2_metadata_core.aggregation.config import (
    DEFAULT_MAX_CONCURRENCY,
    AggregationConfig,
    SourceConfig,
)

__all__ = ["DEFAULT_SOURCE_ORDER", "default_aggregation_config"]

DEFAULT_SOURCE_ORDER: tuple[str, ...] = ("fc2db_net", "javdb", "av123")


def default_aggregation_config(*, max_concurrency: int = DEFAULT_MAX_CONCURRENCY) -> AggregationConfig:
    """The three Phase 2 VERIFIED sources in ``DEFAULT_SOURCE_ORDER``, default deadlines."""
    return AggregationConfig(
        sources=tuple(SourceConfig(source_id) for source_id in DEFAULT_SOURCE_ORDER),
        max_concurrency=max_concurrency,
    )
