"""`StatsStore` port + `InMemoryStore` adapter.

Concurrency: `InMemoryStore.upsert_stats` never mutates the dict currently in
use. It builds a brand-new, complete dict and reassigns the single `_stats`
attribute reference in one step.
"""

from __future__ import annotations

import threading
from datetime import UTC, datetime
from typing import Protocol, runtime_checkable

from pool_selector.domain.models import PoolId, PoolStats


@runtime_checkable
class StatsStore(Protocol):
    """Common protocol for the aggregated-stats read/write port."""

    def get_stats(self) -> dict[PoolId, PoolStats]:
        """Return the current aggregate (empty dict if never populated)."""
        ...

    def upsert_stats(self, stats: dict[PoolId, PoolStats]) -> None:
        """Atomically replace the current aggregate with `stats`."""
        ...

    def get_freshness(self) -> datetime | None:
        """Return the timestamp of the last successful `upsert_stats`, or `None`."""
        ...


class InMemoryStore:
    def __init__(self) -> None:
        self._stats: dict[PoolId, PoolStats] = {}
        self._freshness: datetime | None = None
        self._write_lock = threading.Lock()

    def get_stats(self) -> dict[PoolId, PoolStats]:
        return self._stats

    def upsert_stats(self, stats: dict[PoolId, PoolStats]) -> None:
        new_stats = dict(stats)
        with self._write_lock:
            self._stats = new_stats
            self._freshness = datetime.now(UTC)

    def get_freshness(self) -> datetime | None:
        return self._freshness
