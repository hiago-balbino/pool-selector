"""Integration tests for `RefreshTask`."""

import asyncio
import json
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest

from pool_selector.domain.models import PoolId
from pool_selector.domain.recency import SlidingWindowStrategy
from pool_selector.store.refresh import RefreshTask
from pool_selector.store.stats_store import InMemoryStore


def _line(job_id: str, minutes_ago: float, reason: str | None) -> str:
    finished_at = datetime.now(UTC) - timedelta(minutes=minutes_ago)
    return json.dumps(
        {
            "finished_at": finished_at.isoformat(),
            "job_id": job_id,
            "pool_id": "pool-r6.xlarge-us-east-1a",
            "status": "FAILED" if reason else "SUCCESS",
            "reason": reason,
        }
    )


VALID_LINE = _line("job-1", minutes_ago=5, reason="SPOT_INSTANCE_TERMINATION")
VALID_LINE_2 = _line("job-2", minutes_ago=2, reason=None)


class _WorkingSource:
    """DataSource fake that yields a fixed set of valid JSON lines."""

    def __init__(self, lines: list[str]) -> None:
        self._lines = lines

    def iter_events(self, now: datetime) -> Iterator[str]:
        yield from self._lines


class _FailingSource:
    """DataSource fake simulating an unavailable source (S3/local down)."""

    def iter_events(self, now: datetime) -> Iterator[str]:
        raise ConnectionError("simulated data source outage")
        yield  # pragma: no cover - unreachable, satisfies generator typing


def _recency() -> SlidingWindowStrategy:
    return SlidingWindowStrategy(window_minutes=60)


def test_run_once_success_updates_the_store_stats() -> None:
    store = InMemoryStore()
    task = RefreshTask(
        source=_WorkingSource([VALID_LINE, VALID_LINE_2]),
        store=store,
        recency=_recency(),
        interval_seconds=60,
    )

    task.run_once()

    stats = store.get_stats()
    pool_id = PoolId.parse("pool-r6.xlarge-us-east-1a")
    assert stats[pool_id].total_events == 2
    assert stats[pool_id].availability_failures == 1


def test_run_once_success_advances_freshness() -> None:
    store = InMemoryStore()
    task = RefreshTask(
        source=_WorkingSource([VALID_LINE]),
        store=store,
        recency=_recency(),
        interval_seconds=60,
    )

    task.run_once()

    assert store.get_freshness() is not None


def test_run_once_with_failing_source_keeps_previous_aggregate_intact() -> None:
    store = InMemoryStore()
    successful_task = RefreshTask(
        source=_WorkingSource([VALID_LINE]),
        store=store,
        recency=_recency(),
        interval_seconds=60,
    )
    successful_task.run_once()
    previous_stats = dict(store.get_stats())

    failing_task = RefreshTask(
        source=_FailingSource(), store=store, recency=_recency(), interval_seconds=60
    )
    failing_task.run_once()

    assert store.get_stats() == previous_stats


def test_run_once_with_failing_source_does_not_advance_freshness() -> None:
    store = InMemoryStore()
    successful_task = RefreshTask(
        source=_WorkingSource([VALID_LINE]),
        store=store,
        recency=_recency(),
        interval_seconds=60,
    )
    successful_task.run_once()
    previous_freshness = store.get_freshness()

    failing_task = RefreshTask(
        source=_FailingSource(), store=store, recency=_recency(), interval_seconds=60
    )
    failing_task.run_once()

    assert store.get_freshness() == previous_freshness


def test_run_once_with_failing_source_does_not_raise() -> None:
    store = InMemoryStore()
    task = RefreshTask(
        source=_FailingSource(), store=store, recency=_recency(), interval_seconds=60
    )

    task.run_once()  # must not raise -- test fails if an exception propagates


def test_run_once_with_failing_source_on_first_ever_refresh_leaves_freshness_none() -> None:
    store = InMemoryStore()
    task = RefreshTask(
        source=_FailingSource(), store=store, recency=_recency(), interval_seconds=60
    )

    task.run_once()

    assert store.get_freshness() is None
    assert store.get_stats() == {}


class _CountingSource:
    """DataSource fake that records how many times it was iterated, to prove
    `start()`'s loop body actually re-runs `run_once` on every tick rather
    than executing it once and idling."""

    def __init__(self) -> None:
        self.call_count = 0

    def iter_events(self, now: datetime) -> Iterator[str]:
        self.call_count += 1
        yield from [VALID_LINE]


@pytest.mark.asyncio
async def test_start_runs_run_once_repeatedly_on_every_interval_tick() -> None:
    store = InMemoryStore()
    source = _CountingSource()
    task = RefreshTask(source=source, store=store, recency=_recency(), interval_seconds=0)

    background = asyncio.create_task(task.start())
    try:
        for _ in range(50):
            await asyncio.sleep(0)
            if source.call_count >= 3:
                break
    finally:
        background.cancel()
        with pytest.raises(asyncio.CancelledError):
            await background

    assert source.call_count >= 3
