"""Batch configuration (Phase 3 C4). Immutable, validated before any engine call.

``max_in_flight_items`` (M) is the **global cross-item** budget: at most M ``aggregate(number)`` calls exist for a
scheduler at any instant. It is independent of ``AggregationConfig.max_concurrency`` (S), which only bounds the
source executions *inside one* ``aggregate`` call; the theoretical maximum of simultaneous source operations is
``M * S``. There is deliberately no ``continue_on_item_failure`` switch: an ordinary failure of one item is
always isolated (contract §3).
"""

from __future__ import annotations

from dataclasses import dataclass

from fc2_metadata_core.batch.models import BatchConfigError

__all__ = ["BatchConfig", "DEFAULT_MAX_IN_FLIGHT_ITEMS", "MAX_IN_FLIGHT_ITEMS_LIMIT"]

DEFAULT_MAX_IN_FLIGHT_ITEMS = 4
MAX_IN_FLIGHT_ITEMS_LIMIT = 64


@dataclass(frozen=True, slots=True)
class BatchConfig:
    max_in_flight_items: int = DEFAULT_MAX_IN_FLIGHT_ITEMS

    def __post_init__(self) -> None:
        value = self.max_in_flight_items
        if isinstance(value, bool) or not isinstance(value, int) or not (1 <= value <= MAX_IN_FLIGHT_ITEMS_LIMIT):
            raise BatchConfigError(f"max_in_flight_items must be an int in 1..{MAX_IN_FLIGHT_ITEMS_LIMIT}")
