"""Consumes `JobEvent`s and produces `PoolStats` per pool.

The active `RecencyStrategy` is applied *before* counting, so `total_events`
and `availability_failures` already reflect only the events considered
"now"."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime

from pool_selector.domain.models import JobEvent, PoolId, PoolStats
from pool_selector.domain.reason_classification import DEFAULT_CLASSIFICATION, ReasonClassification
from pool_selector.domain.recency import RecencyStrategy
from pool_selector.domain.scoring import is_availability_failure


def aggregate(
    events: Iterable[JobEvent],
    recency: RecencyStrategy,
    now: datetime,
    reason_classification: ReasonClassification = DEFAULT_CLASSIFICATION,
) -> dict[PoolId, PoolStats]:
    """Aggregate `events` (after applying `recency`) into per-pool `PoolStats`."""
    result: dict[PoolId, PoolStats] = {}
    for event in recency.select_window(events, now):
        pool_id = PoolId.parse(event.pool_id)
        stats = result.get(pool_id)
        if stats is None:
            stats = PoolStats(
                pool_id=pool_id, total_events=0, availability_failures=0, recent_events=0
            )
            result[pool_id] = stats

        stats.total_events += 1
        if is_availability_failure(event.reason, reason_classification):
            stats.availability_failures += 1
        else:
            stats.recent_events += 1

    return result
