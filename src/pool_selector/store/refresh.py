"""Periodic background refresh task.

Reads `DataSource`, parses, aggregates, and updates `StatsStore` on an
interval. On any failure during a refresh cycle (source unavailable,
malformed data surviving the tolerant parser, etc.), the previous valid
aggregate is left untouched, `freshness` does not advance, and the error is
logged rather than raised.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

from pool_selector.domain.recency import RecencyStrategy
from pool_selector.ingestion.aggregator import aggregate
from pool_selector.ingestion.parser import parse_events
from pool_selector.ingestion.source import DataSource
from pool_selector.store.stats_store import StatsStore

logger = logging.getLogger(__name__)


class RefreshTask:
    def __init__(
        self,
        source: DataSource,
        store: StatsStore,
        recency: RecencyStrategy,
        interval_seconds: int,
    ) -> None:
        self._source = source
        self._store = store
        self._recency = recency
        self._interval_seconds = interval_seconds

    def run_once(self) -> None:
        try:
            lines = list(self._source.iter_events())
            events = list(parse_events(lines))
            stats = aggregate(events, self._recency, now=datetime.now(UTC))
            self._store.upsert_stats(stats)
        except Exception:
            logger.exception(
                "refresh cycle failed; keeping last valid aggregate and freshness unchanged"
            )

    async def start(self) -> None:
        while True:
            self.run_once()
            await asyncio.sleep(self._interval_seconds)
