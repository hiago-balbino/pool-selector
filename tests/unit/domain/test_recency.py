"""Unit tests for the sliding-window recency strategy."""

from datetime import UTC, datetime, timedelta

from pool_selector.domain.models import JobEvent
from pool_selector.domain.recency import RecencyStrategy, SlidingWindowStrategy

NOW = datetime(2026, 7, 17, 12, 0, tzinfo=UTC)


def _event(minutes_ago: float, job_id: str = "job") -> JobEvent:
    return JobEvent(
        finished_at=NOW - timedelta(minutes=minutes_ago),
        job_id=job_id,
        pool_id="pool-r6.xlarge-us-east-1c",
        status="FAILED",
        reason="SPOT_INSTANCE_TERMINATION",
    )


def test_events_outside_window_excluded_and_within_window_included() -> None:
    old_event = _event(90, job_id="old")
    recent_event = _event(10, job_id="recent")
    strategy = SlidingWindowStrategy(window_minutes=60)

    result = list(strategy.select_window([old_event, recent_event], now=NOW))

    assert [event.job_id for event in result] == ["recent"]


def test_event_exactly_at_window_boundary_is_included() -> None:
    boundary_event = _event(60, job_id="boundary")
    strategy = SlidingWindowStrategy(window_minutes=60)

    result = list(strategy.select_window([boundary_event], now=NOW))

    assert [event.job_id for event in result] == ["boundary"]


def test_event_just_past_window_boundary_is_excluded() -> None:
    past_boundary_event = _event(60.01, job_id="past_boundary")
    strategy = SlidingWindowStrategy(window_minutes=60)

    result = list(strategy.select_window([past_boundary_event], now=NOW))

    assert result == []


def test_different_window_minutes_produce_different_results_for_same_events() -> None:
    events = [_event(20, job_id="a"), _event(50, job_id="b"), _event(100, job_id="c")]

    narrow = SlidingWindowStrategy(window_minutes=30)
    wide = SlidingWindowStrategy(window_minutes=120)

    narrow_ids = {event.job_id for event in narrow.select_window(events, now=NOW)}
    wide_ids = {event.job_id for event in wide.select_window(events, now=NOW)}

    assert narrow_ids == {"a"}
    assert wide_ids == {"a", "b", "c"}
    assert narrow_ids != wide_ids


def test_sliding_window_strategy_satisfies_recency_strategy_protocol() -> None:
    strategy = SlidingWindowStrategy(window_minutes=60)

    assert isinstance(strategy, RecencyStrategy)
