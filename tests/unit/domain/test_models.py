"""Unit tests for domain models: JobEvent, PoolId, PoolStats and RankedPool."""

from datetime import UTC, datetime

import pytest

from pool_selector.domain.models import (
    JobEvent,
    PoolId,
    PoolIdParseError,
    PoolStats,
    RankedPool,
)


def test_pool_id_parse_happy_path() -> None:
    pool_id = PoolId.parse("pool-r6.xlarge-us-east-1c")

    assert pool_id.instance_type == "r6.xlarge"
    assert pool_id.family == "r6"
    assert pool_id.az == "us-east-1c"


def test_pool_id_parse_multi_segment_az() -> None:
    """AZ segments can contain more than one internal hyphen (e.g. "eu-central-1a").

    maxsplit=2 must keep the whole AZ intact instead of splitting on its
    first hyphen.
    """
    pool_id = PoolId.parse("pool-c5.large-eu-central-1a")

    assert pool_id.instance_type == "c5.large"
    assert pool_id.az == "eu-central-1a"


def test_pool_id_parse_family_derivation_different_instance_type() -> None:
    pool_id = PoolId.parse("pool-m5.2xlarge-us-west-2a")

    assert pool_id.instance_type == "m5.2xlarge"
    assert pool_id.family == "m5"


def test_pool_id_parse_malformed_raises_handled_error_not_generic_exception() -> None:
    with pytest.raises(PoolIdParseError):
        PoolId.parse("pool-r6.xlarge")

    # Confirms it's a specific, catchable error type, not a bare Exception.
    assert issubclass(PoolIdParseError, ValueError)


def test_job_event_construction() -> None:
    event = JobEvent(
        finished_at=datetime(2026, 7, 17, 12, 0, tzinfo=UTC),
        job_id="job-1",
        pool_id="pool-r6.xlarge-us-east-1c",
        status="FAILED",
        reason="SPOT_INSTANCE_TERMINATION",
    )

    assert event.job_id == "job-1"
    assert event.pool_id == "pool-r6.xlarge-us-east-1c"
    assert event.status == "FAILED"
    assert event.reason == "SPOT_INSTANCE_TERMINATION"


def test_pool_stats_construction() -> None:
    pool_id = PoolId.parse("pool-r6.xlarge-us-east-1c")

    stats = PoolStats(
        pool_id=pool_id,
        total_events=10,
        availability_failures=2,
        recent_events=5,
    )

    assert stats.pool_id == pool_id
    assert stats.total_events == 10
    assert stats.availability_failures == 2
    assert stats.recent_events == 5


def test_ranked_pool_construction() -> None:
    pool_id = PoolId.parse("pool-r6.xlarge-us-east-1c")

    ranked = RankedPool(
        pool_id=pool_id,
        score=0.95,
        sample_size=10,
        confidence="normal",
        window="60m sliding",
    )

    assert ranked.pool_id == pool_id
    assert ranked.score == 0.95
    assert ranked.sample_size == 10
    assert ranked.confidence == "normal"
    assert ranked.window == "60m sliding"
