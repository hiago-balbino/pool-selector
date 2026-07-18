"""Integration tests for the aggregator, integrating the real
`SlidingWindowStrategy` and `reason_classification`.
"""

from datetime import UTC, datetime, timedelta

from pool_selector.domain.models import JobEvent, PoolId
from pool_selector.domain.reason_classification import ReasonClassification
from pool_selector.domain.recency import SlidingWindowStrategy
from pool_selector.ingestion.aggregator import aggregate

NOW = datetime(2026, 7, 17, 12, 0, tzinfo=UTC)


def _event(
    pool_id: str,
    minutes_ago: float = 0,
    reason: str | None = None,
    job_id: str = "job",
) -> JobEvent:
    return JobEvent(
        finished_at=NOW - timedelta(minutes=minutes_ago),
        job_id=job_id,
        pool_id=pool_id,
        status="FAILED" if reason else "SUCCESS",
        reason=reason,
    )


def test_events_from_multiple_pools_are_aggregated_separately() -> None:
    events = [
        _event("pool-r6.xlarge-us-east-1a", job_id="a1"),
        _event("pool-r6.xlarge-us-east-1a", job_id="a2"),
        _event("pool-c5.large-us-east-1a", job_id="b1"),
    ]
    strategy = SlidingWindowStrategy(window_minutes=60)

    result = aggregate(events, strategy, now=NOW)

    assert result[PoolId.parse("pool-r6.xlarge-us-east-1a")].total_events == 2
    assert result[PoolId.parse("pool-c5.large-us-east-1a")].total_events == 1


def test_events_outside_recency_window_do_not_count_in_aggregate() -> None:
    events = [
        _event("pool-r6.xlarge-us-east-1a", minutes_ago=10, job_id="recent"),
        _event("pool-r6.xlarge-us-east-1a", minutes_ago=90, job_id="old"),
    ]
    strategy = SlidingWindowStrategy(window_minutes=60)

    result = aggregate(events, strategy, now=NOW)

    assert result[PoolId.parse("pool-r6.xlarge-us-east-1a")].total_events == 1


def test_availability_failures_uses_configurable_reason_classification() -> None:
    """Swapping the classification config changes availability_failures with no
    aggregator code change -- proves the config drives the count, not a
    hardcoded reason string."""
    events = [
        _event("pool-r6.xlarge-us-east-1a", reason="TIMED_OUT", job_id="a"),
    ]
    strategy = SlidingWindowStrategy(window_minutes=60)

    default_result = aggregate(events, strategy, now=NOW)
    custom_classification = ReasonClassification(
        availability_failure=frozenset({"TIMED_OUT"}), job_failure=frozenset()
    )
    custom_result = aggregate(
        events, strategy, now=NOW, reason_classification=custom_classification
    )

    assert default_result[PoolId.parse("pool-r6.xlarge-us-east-1a")].availability_failures == 0
    assert custom_result[PoolId.parse("pool-r6.xlarge-us-east-1a")].availability_failures == 1


def test_total_events_counts_all_windowed_events_for_a_pool() -> None:
    events = [
        _event("pool-r6.xlarge-us-east-1a", reason="SPOT_INSTANCE_TERMINATION", job_id="a"),
        _event("pool-r6.xlarge-us-east-1a", reason=None, job_id="b"),
        _event("pool-r6.xlarge-us-east-1a", reason=None, job_id="c"),
    ]
    strategy = SlidingWindowStrategy(window_minutes=60)

    result = aggregate(events, strategy, now=NOW)

    stats = result[PoolId.parse("pool-r6.xlarge-us-east-1a")]
    assert stats.total_events == 3
    assert stats.availability_failures == 1


def test_successful_events_are_not_counted_as_availability_failures() -> None:
    events = [_event("pool-r6.xlarge-us-east-1a", reason=None, job_id="a")]
    strategy = SlidingWindowStrategy(window_minutes=60)

    result = aggregate(events, strategy, now=NOW)

    assert result[PoolId.parse("pool-r6.xlarge-us-east-1a")].availability_failures == 0


def test_empty_events_produce_empty_aggregate() -> None:
    strategy = SlidingWindowStrategy(window_minutes=60)

    result = aggregate([], strategy, now=NOW)

    assert result == {}


def test_recent_events_counts_successes_within_the_window() -> None:
    """PoolStats.recent_events: non-redundant "recent activity without
    failure" signal, distinct from total_events."""
    events = [
        _event("pool-r6.xlarge-us-east-1a", reason="SPOT_INSTANCE_TERMINATION", job_id="fail"),
        _event("pool-r6.xlarge-us-east-1a", reason=None, job_id="ok-1"),
        _event("pool-r6.xlarge-us-east-1a", reason=None, job_id="ok-2"),
    ]
    strategy = SlidingWindowStrategy(window_minutes=60)

    result = aggregate(events, strategy, now=NOW)

    stats = result[PoolId.parse("pool-r6.xlarge-us-east-1a")]
    assert stats.recent_events == 2
