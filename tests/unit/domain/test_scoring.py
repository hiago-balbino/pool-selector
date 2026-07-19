"""Unit tests for availability scoring and Wilson confidence."""

import pytest

from pool_selector.domain.models import PoolId, PoolStats
from pool_selector.domain.reason_classification import ReasonClassification
from pool_selector.domain.scoring import (
    confidence_score,
    is_availability_failure,
    raw_score,
    wilson_lower_bound,
)

POOL_ID = PoolId.parse("pool-r6.xlarge-us-east-1c")


def _stats(total_events: int, availability_failures: int) -> PoolStats:
    return PoolStats(
        pool_id=POOL_ID,
        total_events=total_events,
        availability_failures=availability_failures,
        recent_events=total_events,
    )


def test_raw_score_computes_one_minus_failure_rate() -> None:
    stats = _stats(total_events=10, availability_failures=3)

    assert raw_score(stats) == pytest.approx(0.7)


def test_raw_score_all_events_are_failures_is_zero() -> None:
    stats = _stats(total_events=5, availability_failures=5)

    assert raw_score(stats) == pytest.approx(0.0)


def test_raw_score_zero_total_events_returns_one_without_dividing_by_zero() -> None:
    stats = _stats(total_events=0, availability_failures=0)

    assert raw_score(stats) == pytest.approx(1.0)


def test_raw_score_configurability_changing_availability_failure_category_changes_result() -> None:
    events_reasons = [
        "SPOT_INSTANCE_TERMINATION",
        "TIMED_OUT",
        "TIMED_OUT",
        None,
        None,
        None,
        None,
    ]

    default_config = ReasonClassification()
    extended_config = ReasonClassification(
        availability_failure=frozenset({"SPOT_INSTANCE_TERMINATION", "TIMED_OUT"})
    )

    default_failures = sum(
        1 for reason in events_reasons if is_availability_failure(reason, default_config)
    )
    extended_failures = sum(
        1 for reason in events_reasons if is_availability_failure(reason, extended_config)
    )
    assert default_failures == 1
    assert extended_failures == 3

    stats_default = _stats(total_events=len(events_reasons), availability_failures=default_failures)
    stats_extended = _stats(
        total_events=len(events_reasons), availability_failures=extended_failures
    )

    assert raw_score(stats_default) != raw_score(stats_extended)
    assert raw_score(stats_extended) < raw_score(stats_default)


def test_is_availability_failure_delegates_to_classification_not_hardcoded_string() -> None:
    default_config = ReasonClassification()
    extended_config = ReasonClassification(
        availability_failure=frozenset({"SPOT_INSTANCE_TERMINATION", "TIMED_OUT"})
    )

    assert is_availability_failure("SPOT_INSTANCE_TERMINATION", default_config) is True
    assert is_availability_failure("TIMED_OUT", default_config) is False
    assert is_availability_failure("TIMED_OUT", extended_config) is True


def test_confidence_score_large_sample_beats_small_sample_at_zero_failure_rate() -> None:
    large_sample = _stats(total_events=1000, availability_failures=0)
    small_sample = _stats(total_events=10, availability_failures=0)

    assert confidence_score(large_sample) > confidence_score(small_sample)


def test_confidence_score_wired_to_wilson_lower_bound_of_successes() -> None:
    stats = _stats(total_events=20, availability_failures=5)

    assert confidence_score(stats) == pytest.approx(wilson_lower_bound(15, 20))


def test_wilson_lower_bound_zero_total_returns_zero_without_dividing_by_zero() -> None:
    assert wilson_lower_bound(0, 0) == pytest.approx(0.0)
